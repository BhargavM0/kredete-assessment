import threading
from datetime import datetime
from .models import RunStatus, StepStatus, Step
from .store import get_run, update_run
from . import tools
from .store import find_runs_by_goal

PLANNED_STEPS = ["Plan", "LookupPrevious", "SearchA", "SearchB", "Summarize", "Finalize"]
# LookupPrevious is free: adopting or copying prior work should not charge credits.
STEP_COSTS = {"Plan": 100, "LookupPrevious": 0, "SearchA": 500, "SearchB": 500, "Summarize": 400, "Finalize": 100}

def start(run_id: str):
    t = threading.Thread(target=_run, args=(run_id,), daemon=True)
    t.start()

def _run(run_id: str):
    run = get_run(run_id)
    if not run:
        return
    if run.status == RunStatus.RUNNING:
        return
    def mark_running(r):
        r.status = RunStatus.RUNNING
    update_run(run_id, mark_running)

    for i, step_name in enumerate(PLANNED_STEPS):
        run = get_run(run_id)
        if not run:
            return
        if i >= run.max_steps:
            def _set_max(r):
                r.status = RunStatus.MAX_STEPS_EXCEEDED
            update_run(run_id, _set_max)
            return

        existing_steps = run.steps
        if len(existing_steps) > i and existing_steps[i].status == StepStatus.COMPLETED:
            continue

        def _ensure_step(r):
            if len(r.steps) <= i:
                s = Step(name=step_name, status=StepStatus.PENDING, cost=STEP_COSTS.get(step_name, 0))
                r.steps.append(s)
        update_run(run_id, _ensure_step)

        # Visible 'LookupPrevious' step: check earlier runs with same goal and reuse work
        if step_name == 'LookupPrevious':
            prev_ids = find_runs_by_goal(run.goal)
            prev_ids = [pid for pid in prev_ids if pid != run_id]
            if prev_ids:
                prev = get_run(prev_ids[0])
                if prev:
                    if prev.status == RunStatus.COMPLETED:
                        def _adopt_completed(r):
                            # ensure Plan is preserved (Plan should have run earlier in the loop)
                            plan_idx = None
                            for idx, st in enumerate(r.steps):
                                if st.name == 'Plan':
                                    plan_idx = idx
                                    break
                            if plan_idx is None:
                                # create a completed Plan placeholder
                                plan = Step(name='Plan', status=StepStatus.COMPLETED, cost=STEP_COSTS.get('Plan', 0), output=f"Planned steps for: {r.goal}", started_at=datetime.utcnow(), finished_at=datetime.utcnow())
                                r.steps = [plan]
                                plan_idx = 0
                            s = r.steps[i]
                            # synthesize a compact adoption message (don't re-run searches)
                            details = ' | '.join([f"{ps.name}: {ps.output}" for ps in prev.steps if ps.output])
                            s.output = f"Adopted outputs from completed run {prev.id}: {details}"
                            s.status = StepStatus.COMPLETED
                            s.finished_at = datetime.utcnow()
                            # keep only Plan and LookupPrevious in the visible steps
                            r.steps = r.steps[:plan_idx+1] + [s]
                            # do not charge lookup when adopting a completed run
                            # (no new work was performed)
                            r.status = RunStatus.COMPLETED
                        update_run(run_id, _adopt_completed)
                        return
                    else:
                        def _copy_completed(r):
                            s = r.steps[i]
                            s.output = f"Found previous partial run {prev.id}; copying completed steps"
                            s.status = StepStatus.COMPLETED
                            s.finished_at = datetime.utcnow()
                            # copy completed steps from prev into this run, but do NOT add their costs
                            for s_prev in prev.steps:
                                if s_prev.status != StepStatus.COMPLETED:
                                    continue
                                found = False
                                for rs in r.steps:
                                    if rs.name == s_prev.name:
                                        found = True
                                        if rs.status != StepStatus.COMPLETED:
                                            rs.output = s_prev.output
                                            rs.status = StepStatus.COMPLETED
                                            rs.started_at = s_prev.started_at
                                            rs.finished_at = s_prev.finished_at
                                            rs.error = s_prev.error
                                        break
                                if not found:
                                    # append the completed step as-is (no extra credit added)
                                    r.steps.append(s_prev)
                            # do not charge lookup when copying completed steps from a previous run
                            # (we're reusing previous work)
                        update_run(run_id, _copy_completed)
                        # we've copied completed steps; skip charging/starting LookupPrevious and continue
                        continue

        def _charge_and_start(r):
            s = r.steps[i]
            # charge only if this step hasn't been charged before (supports retries)
            if not getattr(s, 'charged', False):
                r.credits_consumed += s.cost
                s.charged = True
            s.status = StepStatus.RUNNING
            s.started_at = datetime.utcnow()
        update_run(run_id, _charge_and_start)

        try:
            if step_name.startswith('Search'):
                idx = 1 if step_name.endswith('A') else 2
                run = get_run(run_id)
                res = tools.mock_search(run.goal, idx)
                def _complete(r):
                    s = r.steps[i]
                    s.output = res
                    s.status = StepStatus.COMPLETED
                    s.finished_at = datetime.utcnow()
                update_run(run_id, _complete)
            elif step_name == 'Plan':
                run = get_run(run_id)
                out = f"Planned steps for: {run.goal}"
                def _complete(r):
                    s = r.steps[i]
                    s.output = out
                    s.status = StepStatus.COMPLETED
                    s.finished_at = datetime.utcnow()
                update_run(run_id, _complete)
            elif step_name == 'Summarize':
                run = get_run(run_id)
                results = [st.output or '' for st in run.steps if st.name.startswith('Search')]
                summary = tools.mock_summarize(results)
                def _complete(r):
                    s = r.steps[i]
                    s.output = summary
                    s.status = StepStatus.COMPLETED
                    s.finished_at = datetime.utcnow()
                update_run(run_id, _complete)
            elif step_name == 'Finalize':
                run = get_run(run_id)
                out = f"Final report for: {run.goal}"
                def _complete(r):
                    s = r.steps[i]
                    s.output = out
                    s.status = StepStatus.COMPLETED
                    s.finished_at = datetime.utcnow()
                update_run(run_id, _complete)

            # after step completion, continue
        except Exception as e:
            def _fail(r):
                s = r.steps[i]
                s.error = str(e)
                s.status = StepStatus.FAILED
                s.finished_at = datetime.utcnow()
                r.status = RunStatus.FAILED
            update_run(run_id, _fail)
            return

    def _complete_run(r):
        r.status = RunStatus.COMPLETED
    update_run(run_id, _complete_run)

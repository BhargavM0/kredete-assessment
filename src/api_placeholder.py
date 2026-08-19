from uuid import uuid4
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from .models import CreateRunRequest, Run, RunStatus, StepStatus
from .store import save_run, get_run, map_request_to_run, find_run_by_request_hash
from .executor import start

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend static files under /static and expose index at '/'
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("frontend/index.html")


@app.post("/runs", status_code=201)
def create_run(req: CreateRunRequest, force: bool = False):
    # compute a request hash to provide idempotency for identical queries
    key_src = f"{req.goal}|{req.max_steps}"
    req_hash = hashlib.sha256(key_src.encode()).hexdigest()
    if not force:
        existing = find_run_by_request_hash(req_hash)
        if existing:
            existing_run = get_run(existing)
            if existing_run:
                # If the existing run is still in-flight, return it to avoid duplicate execution.
                if existing_run.status in (RunStatus.PENDING, RunStatus.RUNNING):
                    return existing_run
                # If the existing run is completed/failed, proceed to create a fresh run
                # (so the new run can perform a LookupPrevious step and adopt/merge results).

    run_id = str(uuid4())
    now = datetime.utcnow()
    run = Run(id=run_id, goal=req.goal, status=RunStatus.PENDING, steps=[], credits_consumed=0, max_steps=req.max_steps, created_at=now)
    save_run(run)
    # persist mapping from request hash -> run id (idempotency) only when not forcing
    if not force:
        map_request_to_run(req_hash, run_id)
    start(run_id)
    return run


@app.get("/runs/{run_id}")
def get_run_endpoint(run_id: str):
    r = get_run(run_id)
    if not r:
        return {"error": "not found"}
    return r


@app.post("/runs/{run_id}/retry")
def retry_run(run_id: str):
    r = get_run(run_id)
    if not r:
        return {"error": "not found"}
    # only allow retrying failed runs for now
    if r.status != RunStatus.FAILED:
        return {"error": "run not in FAILED state", "run": r}

    # find the first failed step
    failed_idx = None
    for idx, s in enumerate(r.steps):
        if s.status == StepStatus.FAILED:
            failed_idx = idx
            break
    if failed_idx is None:
        return {"error": "no failed step found", "run": r}

    def _prepare_retry(rr):
        # mark steps that already ran as charged so we don't double-charge
        for st in rr.steps:
            if st.status in (StepStatus.COMPLETED, StepStatus.RUNNING, StepStatus.FAILED):
                st.charged = True
        # reset the failed step to pending without altering charged flag
        st = rr.steps[failed_idx]
        st.status = StepStatus.PENDING
        st.error = None
        st.started_at = None
        st.finished_at = None
        rr.status = RunStatus.PENDING

    update_run(run_id, _prepare_retry)
    start(run_id)
    return get_run(run_id)

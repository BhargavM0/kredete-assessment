# Kredete Agent — Minimal Run-Loop Slice

Project summary
- A minimal, demonstrable slice of an autonomous-agent run loop. Accepts a plain-language `goal`, performs a bounded sequence of mocked steps (Plan, LookupPrevious, SearchA, SearchB, Summarize, Finalize), tracks integer credits exactly, handles partial failures, and exposes a tiny frontend to observe runs.

Quick start
- Create and activate a Python venv, install dependencies, then start the server (project includes `scripts/run_local.sh`):


*You can use the UI via "bash scripts/run_local.sh" or use the /runs endpoint directly through bash

```bash
# start server (recommended)
bash scripts/run_local.sh

# or, with an active venv:
uvicorn src.api_placeholder:app --reload --port 8000
```

Open the frontend at http://127.0.0.1:8000/ and use the dev backend panel to inspect runs.


Demo scenarios (commands)

1) Successful run (completes all steps)

```bash
curl -s -X POST 'http://127.0.0.1:8000/runs' \
  -H 'Content-Type: application/json' \
  -d '{"goal":"hello there","max_steps":10}' | jq .
# Expect: run.status COMPLETED, credits_consumed ≈ 1600
```

2) Idempotent retry / LookupPrevious adoption

Run the exact same POST again (simulates client retry or duplicate request):

```bash
curl -s -X POST 'http://127.0.0.1:8000/runs' \
  -H 'Content-Type: application/json' \
  -d '{"goal":"hello there","max_steps":10}' | jq .
# Expect: a fresh run is created that performs a LookupPrevious, adopts previous outputs,
# and does NOT re-run the expensive search/summarize steps (credits reflect minimal additional cost).
```

3) Forced failure and retry (deterministic)

The mocked tools inject a deterministic failure when the query starts with a digit: `SearchB` raises an error.

```bash
# create a failing run
R=$(curl -s -X POST 'http://127.0.0.1:8000/runs' -H 'Content-Type: application/json' -d '{"goal":"1 fail","max_steps":10}')
echo "$R" | jq .
# Inspect the run id and failed step; credits_consumed includes charges up to the failed step.

# retry the failed run (resumes without double-charging)
ID=$(echo "$R" | jq -r .id)
curl -s -X POST "http://127.0.0.1:8000/runs/${ID}/retry" | jq .
# Expect: failed step reset to PENDING, previously charged steps remain charged, no double-charge.
```



Design decisions:
- Loop bounding: `max_steps` limits executed steps; when exceeded run status becomes `MAX_STEPS_EXCEEDED`. (Default is 10)
- Failure handling: when a tool call throws, the step is marked `FAILED`, run becomes `FAILED`, and any credits already charged remain used.
- Idempotency: server computes `sha256(goal|max_steps)` and persists a request->run mapping. To allow fresh runs that can `LookupPrevious`, the server returns an existing run only if it is `PENDING` or `RUNNING`; otherwise it creates a fresh run so `LookupPrevious` can adopt prior results.
- LookupPrevious semantics: adoption of completed runs is free (no lookup charge). Partial runs have their completed steps copied into the new run without additional charging.
- Tradeoff: persistence is a simple JSON-backed store with a lock for this MVP; migrating to SQLite would be preferable for production durability and concurrency.

Architecture (brief)
- FastAPI server (`src/api_placeholder.py`) exposes `/runs` and `/runs/{id}/retry`.
- Background threaded executor (`src/executor.py`) runs steps, updates `credits_consumed`, and persists via `src/store.py`.
- Mocked tool implementations in `src/tools.py` (deterministic failure injection supported).
- Static frontend in `frontend/index.html` that polls the API and shows a dev backend panel.

Files of interest
- `src/executor.py` — bounded executor that runs Plan → SearchA → SearchB → Summarize → Finalize
- `src/tools.py` — mocked tools `mock_search` and `mock_summarize`
- `src/store.py` — in-memory run store
- `frontend/index.html` — chat UI that POSTs runs and polls status



API endpoints

- `POST /runs` — create a run with JSON `{ "goal": "...", "max_steps": 10 }`
- `GET /runs/{id}` — fetch the run state, steps, outputs, and `credits_consumed` (integer units)


AI NOTE
- I primarily used AI for planning and documentation. I researched the requirements, planned the architecture, and laid out steps and segments for AI to complete and verified its work after every step. For example, I instructed it to build the frontend UI and API endpoint and worked on integration, polishing the mock tools, and making every design choice while AI carried out tasks for me. Another thing I used AI for was creating this specific documentation to be technically and organizationally correct. I gave it my reasonings, quick start guide, and summary in plain english and had it make a README file that was accurate and concise.
import threading
import json
import os
import tempfile
from typing import Dict, Optional
from .models import Run

_store_lock = threading.Lock()
_runs: Dict[str, Run] = {}
_request_index: Dict[str, str] = {}

# persistent storage paths (project-root/data)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT_DIR, 'data')
RUNS_FILE = os.path.join(DATA_DIR, 'runs_store.json')
INDEX_FILE = os.path.join(DATA_DIR, 'request_index.json')

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _persist():
    _ensure_data_dir()
    # persist runs
    tmp = tempfile.NamedTemporaryFile('w', delete=False, dir=DATA_DIR)
    try:
        serial = {rid: _runs[rid].dict() for rid in _runs}
        json.dump(serial, tmp, default=str, indent=2)
        tmp.flush(); os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, RUNS_FILE)
    finally:
        if os.path.exists(tmp.name):
            try: os.remove(tmp.name)
            except: pass
    # persist index
    tmp2 = tempfile.NamedTemporaryFile('w', delete=False, dir=DATA_DIR)
    try:
        json.dump(_request_index, tmp2, indent=2)
        tmp2.flush(); os.fsync(tmp2.fileno())
        tmp2.close()
        os.replace(tmp2.name, INDEX_FILE)
    finally:
        if os.path.exists(tmp2.name):
            try: os.remove(tmp2.name)
            except: pass

def _load_persistent():
    _ensure_data_dir()
    # load runs
    if os.path.exists(RUNS_FILE):
        try:
            with open(RUNS_FILE, 'r') as f:
                data = json.load(f)
                for rid, rdict in data.items():
                    try:
                        _runs[rid] = Run.parse_obj(rdict)
                    except Exception:
                        # skip malformed entries
                        continue
        except Exception:
            pass
    # load index
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _request_index.update(data)
        except Exception:
            pass


_load_persistent()


def save_run(run: Run):
    with _store_lock:
        _runs[run.id] = run
        _persist()


def get_run(run_id: str) -> Optional[Run]:
    with _store_lock:
        return _runs.get(run_id)


def update_run(run_id: str, patch_fn):
    with _store_lock:
        run = _runs.get(run_id)
        if not run:
            return None
        patch_fn(run)
        _runs[run_id] = run
        _persist()
        return run


def map_request_to_run(request_hash: str, run_id: str):
    with _store_lock:
        _request_index[request_hash] = run_id
        _persist()


def find_run_by_request_hash(request_hash: str) -> Optional[str]:
    with _store_lock:
        return _request_index.get(request_hash)


def find_runs_by_goal(goal: str):
    """Return list of run ids matching the same goal (case-insensitive, trimmed), newest first."""
    key = goal.strip().lower()
    with _store_lock:
        matches = [rid for rid, r in _runs.items() if (r.goal or '').strip().lower() == key]
        # sort by created_at descending if available
        try:
            matches.sort(key=lambda rid: _runs[rid].created_at or 0, reverse=True)
        except Exception:
            pass
        return matches

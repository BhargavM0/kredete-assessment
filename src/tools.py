import time
from typing import List

def mock_search(query: str, index: int) -> str:
    # deterministic failure injection: if query starts with a digit and this is SearchB (index==2), fail
    time.sleep(0.1)
    if query and query[0].isdigit() and index == 2:
        raise RuntimeError("Sample error: query cannot start with a number")
    return f"Search result {index} for '{query}'"

def mock_summarize(results: List[str]) -> str:
    time.sleep(0.15)
    joined = ' | '.join(results[:3])
    return f"Summary: {joined}"

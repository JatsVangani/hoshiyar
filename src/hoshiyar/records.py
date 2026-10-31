"""One line per finished call in data/calls.jsonl. The fleet page and the drift signal read this file.

JSON Lines, not one big JSON array: appending a line never rewrites the file, so a crash mid-write
loses at most that one call.
"""

import json
import os
import time
from pathlib import Path

from hoshiyar.brain import CallState

CALLS_FILE = Path(os.environ.get("CALLS_FILE", "data/calls.jsonl"))


def save(state: CallState, kind: str) -> dict:
    """Append what this call learned. Seconds-into-call lists stay as they are; the page converts them."""
    record = {
        "driver": state.driver,
        "kind": kind,  # checkin | wakeup
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state.started_at)),
        "duration": round(time.time() - state.started_at, 1),
        "scores": state.scores,
        "mode": state.mode,
        "reply_delays": [(round(t, 1), round(d, 2)) for t, d in state.reply_delays],
        "alerts": state.alerts,
        "unresponsive": state.unresponsive,
        "drift": state.drift,
        "break_taken": state.break_taken,
        "call_id": state.call_id,
        "lang": state.lang,  # the language the call ended in; auto = stayed Hindi, never switched
    }
    CALLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CALLS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def save_missed(driver: str, kind: str, status: str, attempts: int, started_at: float) -> dict:
    """A call that never connected: busy, no-answer or a failed dial, after every redial. Same shape as a
    finished call so the page and the drift signal can read it, plus 'status' and 'attempts'."""
    record = {
        "driver": driver,
        "kind": kind,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started_at)),
        "duration": 0.0,
        "scores": [],
        "mode": "MILD",
        "reply_delays": [],
        "alerts": [],
        "unresponsive": False,
        "drift": "steady",
        "break_taken": False,
        "call_id": None,
        "status": status,  # a finished call has no 'status' key: read it as 'completed'
        "attempts": attempts,
    }
    CALLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CALLS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load(driver: str | None = None) -> list[dict]:
    """All calls, oldest first; optionally one driver's."""
    if not CALLS_FILE.exists():
        return []
    rows = [json.loads(line) for line in CALLS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if driver is None or r["driver"] == driver]
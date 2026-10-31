"""Try Hoshiyar from the fleet page: a visitor books one check-in call to a number they prove is theirs.

The proof is a four-digit code read out on a Vobiz voice call (no SMS: India needs DLT for that) and typed
back on the page. Entries live in data/trials.json for one night. The rules that stop a shared link from
draining the line are all here: Indian mobiles only, one code on the way per number, three wrong codes
and the number is locked for a day, ten minutes to type it, one pending booking per number, a cap per night.
"""

import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

TRIALS_FILE = Path(os.environ.get("TRIALS_FILE", "data/trials.json"))
PER_NIGHT = int(os.environ.get("TRIALS_PER_NIGHT", "20"))  # codes dialled in 24 h before we say no
CODE_TTL = 10 * 60  # seconds the code stays valid
MAX_ATTEMPTS = 3
LOCK = 24 * 3600  # after MAX_ATTEMPTS wrong codes
NIGHT = 24 * 3600  # an entry is forgotten this long after it was due
GRACE = 15 * 60  # a chosen time this far in the past still means "now"; older means tomorrow
MAX_CALLS = 2  # code calls per entry: the first, and one "call again"

_MOBILE = re.compile(r"^[6-9]\d{9}$")


class TrialError(Exception):
    """A refusal to show the visitor, in one sentence."""


class Pending(TrialError):
    """This number already has a code on the way: send the visitor back to that code box, not away."""

    def __init__(self, trial_id: str):
        super().__init__("This number already has a code on the way.")
        self.trial_id = trial_id


def normalize(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return f"+91{digits}" if _MOBILE.match(digits) else None


def masked(phone: str) -> str:
    return f"{phone[:6]}xxx xx{phone[-3:]}"


def load() -> list[dict]:
    """All entries still worth keeping: due less than a night ago, or locked until later."""
    if not TRIALS_FILE.exists():
        return []
    now = time.time()
    rows = json.loads(TRIALS_FILE.read_text(encoding="utf-8"))
    return [r for r in rows if r["due"] + NIGHT > now or r["locked_until"] > now]


def _save(rows: list[dict]) -> None:
    TRIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRIALS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def get(trial_id: str) -> dict | None:
    return next((r for r in load() if r["id"] == trial_id), None)


def due_at(hhmm: str, now: datetime) -> datetime:
    """Today at hh:mm if that is ahead or within GRACE behind us, else tomorrow."""
    h, m = map(int, hhmm.split(":"))
    due = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if (now - due).total_seconds() > GRACE:
        due += timedelta(days=1)
    return due


def create(name: str, phone: str, hhmm: str, now: datetime | None = None) -> dict:
    """Book a code call. Raises TrialError with the sentence to show when the rules say no."""
    now = now or datetime.now()
    name = (name or "").strip()[:40]
    number = normalize(phone)
    if not name:
        raise TrialError("Tell us a name to call you by.")
    if not number:
        raise TrialError("Enter a valid Indian mobile number.")
    try:
        due = due_at(hhmm, now)
    except (ValueError, AttributeError):
        raise TrialError("Pick a time for the call.")
    rows = load()
    t = now.timestamp()
    for r in rows:
        if r["phone"] != number:
            continue
        if r["locked_until"] > t:
            raise TrialError("This number is locked until tomorrow after three wrong codes.")
        if r["verified"] and r["due"] > t:  # booked and still waiting for its call: one at a time
            raise TrialError(f"This number already has a call booked for {r['at']}.")
        if not r["verified"] and r["created"] + CODE_TTL > t and r["wrong_codes"] < MAX_ATTEMPTS:
            raise Pending(r["id"])
    if sum(r["code_calls"] for r in rows if r["created"] + NIGHT > t) >= PER_NIGHT:
        raise TrialError("No more trials tonight. Come back tomorrow.")
    entry = {
        "id": uuid.uuid4().hex[:10], "name": name, "phone": number, "due": due.timestamp(),
        "at": f"{due:%H:%M}", "code": f"{secrets.randbelow(10000):04d}", "created": t,
        "wrong_codes": 0, "code_calls": 0, "verified": False, "locked_until": 0.0,
    }
    _save(rows + [entry])
    return entry


def note_call(trial_id: str) -> dict:
    """Count a code call against the entry and the nightly cap. Raises when it has had its two."""
    rows = load()
    entry = next((r for r in rows if r["id"] == trial_id), None)
    if entry is None or entry["created"] + CODE_TTL < time.time():
        raise TrialError("That code has expired. Start again.")
    if entry["code_calls"] >= MAX_CALLS:
        raise TrialError("We have called twice already. Start again in a few minutes.")
    entry["code_calls"] += 1
    _save(rows)
    return entry


def verify(trial_id: str, code: str) -> dict:
    """Check the typed code. Right: the entry is verified and the scheduler will call. Wrong: raises."""
    rows = load()
    entry = next((r for r in rows if r["id"] == trial_id), None)
    if entry is None:
        raise TrialError("That code has expired. Start again.")
    t = time.time()
    if entry["verified"]:
        return entry
    if entry["locked_until"] > t:
        raise TrialError("This number is locked until tomorrow after three wrong codes.")
    if entry["created"] + CODE_TTL < t:
        raise TrialError("That code has expired. Start again.")
    if (code or "").strip() == entry["code"]:
        entry["verified"] = True
        _save(rows)
        return entry
    entry["wrong_codes"] += 1
    left = MAX_ATTEMPTS - entry["wrong_codes"]
    if left <= 0:
        entry["locked_until"] = t + LOCK
        _save(rows)
        raise TrialError("Three wrong codes. This number is locked until tomorrow.")
    _save(rows)
    raise TrialError(f"Not that code. {left} {'try' if left == 1 else 'tries'} left.")


def speak_text(trial_id: str) -> str:
    """What the code call says. An unknown or stale id gets a polite line instead of a code."""
    entry = get(trial_id)
    if entry is None or entry["created"] + CODE_TTL < time.time():
        return "Hoshiyar here. That code has expired. Please start again on the page."
    return "Hoshiyar here. Your code is " + ", ".join(entry["code"]) + "."


def drivers() -> list[dict]:
    """Verified trials as one-night roster entries, due as an absolute time rather than a daily slot."""
    return [
        {"name": r["name"], "phone": r["phone"], "route": "Trial", "checkins": [r["at"]], "due": r["due"], "trial": True}
        for r in load() if r["verified"]
    ]

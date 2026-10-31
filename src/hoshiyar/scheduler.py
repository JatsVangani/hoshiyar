"""Who gets called when: the nightly check-in rota from data/drivers.json, the wake-up call after a break,
and a redial when the driver does not pick up. Pending wake-ups and placed slots live in data/schedule.json
so a restart neither forgets a wake-up nor calls the same slot twice."""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from hoshiyar import vobiz, trials, records

ROSTER_FILE = Path(os.environ.get("ROSTER_FILE", "data/drivers.json"))
SCHEDULE_FILE = Path(os.environ.get("SCHEDULE_FILE", "data/schedule.json"))
WAKEUP_AFTER = float(os.environ.get("WAKEUP_AFTER", "1200"))  # seconds; set 60 in .env for demos
REDIAL_AFTER = float(os.environ.get("REDIAL_AFTER", "300"))  # seconds before trying a driver again
MAX_ATTEMPTS = 2
TICK = 20.0  # seconds between rota checks
GRACE = 15 * 60  # a slot missed by less than this (server was down) is still called
CALL_TIMEOUT = 30 * 60  # longest we wait for a driver call's hangup

_last_roster: list[dict] = []
CALLS: dict[str, dict] = {}  # request_uuid -> {"kind": "checkin"|"wakeup", "driver": {...}}; bot_phone pops it
_tasks: set[asyncio.Task] = set()  # keep references or asyncio may garbage-collect a sleeping task


def load_roster() -> list[dict]:
    """[{"name", "phone", "route", "checkins": ["23:00", "01:30"]}]. Empty when the file is missing."""
    global _last_roster
    if not ROSTER_FILE.exists():
        return []
    try:
        _last_roster = json.loads(ROSTER_FILE.read_text(encoding="utf-8"))
    except ValueError as e:  # caught mid-edit: keep the last good roster rather than kill the rota
        logger.warning(f"Roster unreadable, keeping the last good one: {e}")
    return _last_roster


def driver_for(phone: str) -> dict:
    """The roster entry for a phone, or a stand-in so a test call to MY_PHONE still has a name."""
    for driver in load_roster():
        if driver["phone"] == phone:
            return driver
    return {"name": phone, "phone": phone, "route": "", "checkins": []}


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def place_call(driver: dict, kind: str) -> str:
    """Dial, wait for the hangup, redial if the driver did not pick up. Returns the final CallStatus."""
    status = "failed"
    started = time.time()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(f"Rota: calling {driver['name']} ({kind}) attempt {attempt}")
        try:
            result = await vobiz.dial(driver["phone"], os.environ["LOCAL_SERVER_URL"])
        except Exception as e:  # 429 concurrency cap, 402 balance, network: all worth a retry
            logger.error(f"Rota: dial failed for {driver['name']}: {e}")
            status = "failed"
        else:
            CALLS[result["request_uuid"]] = {"kind": kind, "driver": driver}
            status = await vobiz.wait_for_hangup(result["request_uuid"], CALL_TIMEOUT)
            CALLS.pop(result["request_uuid"], None)  # still here only if the stream never started
        logger.info(f"Rota: {driver['name']} ({kind}) attempt {attempt}: {status}")
        if status in ("completed", "timeout"):  # timeout = the call is still going after CALL_TIMEOUT
            return status
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(REDIAL_AFTER)
    records.save_missed(driver["name"], kind, status, MAX_ATTEMPTS, started)  # the fleet page must show this
    return status


def schedule_wakeup(driver: dict) -> None:
    """Call the driver back after the break. Written to disk first so a restart does not forget him."""
    due = time.time() + WAKEUP_AFTER
    data = _schedule()
    data["wakeups"].append({"driver": driver, "due": due})
    _save_schedule(data)
    spawn(_wakeup(driver, due))
    logger.info(f"Wake-up call to {driver['name']} in {WAKEUP_AFTER:.0f} s")


async def _wakeup(driver: dict, due: float) -> None:
    await asyncio.sleep(max(0.0, due - time.time()))
    data = _schedule()
    data["wakeups"] = [w for w in data["wakeups"] if (w["driver"]["phone"], w["due"]) != (driver["phone"], due)]
    _save_schedule(data)
    await place_call(driver, "wakeup")


async def run_rota() -> None:
    """Started with the server: re-arm saved wake-ups, then dial each driver at his check-in times."""
    data = _schedule()
    for w in data["wakeups"]:
        spawn(_wakeup(w["driver"], w["due"]))
    logger.info(f"Rota: {len(load_roster())} drivers on the roster, {len(data['wakeups'])} wake-ups re-armed")
    while True:
        tick(datetime.now())
        await asyncio.sleep(TICK)


def tick(now: datetime) -> list[str]:
    """One pass over the roster and tonight's verified trials: start every slot that is due and not yet placed."""
    started = []
    for driver in load_roster():  # re-read every tick: edit the file, no restart needed
        for hhmm in driver.get("checkins", []):
            slot = slot_due(hhmm, now)
            if slot is not None:
                started += _start(driver, slot)
    for driver in trials.drivers():  # a trial is due once, at an absolute time, with the same grace
        due = datetime.fromtimestamp(driver["due"])
        if 0 <= (now - due).total_seconds() <= GRACE:
            started += _start(driver, due)
    return started


def _start(driver: dict, slot: datetime) -> list[str]:
    key = f"{driver['phone']}@{slot:%Y-%m-%d %H:%M}"
    data = _schedule()
    if key in data["placed"]:
        return []
    data["placed"][key] = "calling"
    _save_schedule(data)
    spawn(_rota_call(driver, key))
    return [key]


def slot_due(hhmm: str, now: datetime) -> datetime | None:
    """The most recent hh:mm at or before now, if it is less than GRACE old. Local time."""
    h, m = map(int, hhmm.split(":"))
    slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if slot > now:
        slot -= timedelta(days=1)
    return slot if (now - slot).total_seconds() <= GRACE else None


async def _rota_call(driver: dict, key: str) -> None:
    status = await place_call(driver, "checkin")
    data = _schedule()
    data["placed"][key] = status
    _save_schedule(data)


def _schedule() -> dict:
    if SCHEDULE_FILE.exists():
        return json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    return {"wakeups": [], "placed": {}}


def _save_schedule(data: dict) -> None:
    cutoff = f"{datetime.now() - timedelta(days=2):%Y-%m-%d}"
    data["placed"] = {k: v for k, v in data["placed"].items() if k.split("@")[1] >= cutoff}  # keep two nights
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

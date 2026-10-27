"""Tell the fleet manager: Hoshiyar rings them and reads the alert out """

import os
import asyncio
import uuid
from xml.sax.saxutils import escape
from loguru import logger

from hoshiyar import vobiz

PENDING: dict[str, str] = {} # alert id -> text; /alert/{id} reads it when the manager picks up
TASKS: set[asyncio.Task] = set()

_line = asyncio.Lock() # the manager has one phone: one alert call at a time, or the second one hits busy
_ended = dict[str, str] = {} # request_uuid -> CallStatus from /hangup
_ended_event = asyncio.Event()

ALERT_CALL_TIMEOUT = 120.0 # ring + speech; give up waiting after this and move on
RETRY_AFTER = 30.0 # seconds before a second try when the line was busy or nobody answered

async def notify_fleet(text: str) -> bool:
    """Ring FLEET_PHONE (MY_PHONE if unset) and speak the alert. True when Vobiz queued the call"""
    to = os.environ.get("FLEET_PHONE") or os.environ.get("MY_PHONE")
    logger.warning(f"FLEET ALERT -> {to}: {text}")
    if not to:
        return False
    alert_id = uuid.uuid4().hex
    PENDING[alert_id] = text
    async with _line:
        for attempt in (1, 2):
            try:
                await vobiz.dial(to, os.environ["LOCAL_SERVER_URL"], answer_path=f"/alert/{alert_id}")
            except Exception as e: # the driver's call must never care
                logger.error(f"Fleet alert call failed: {e}")
                return False
            status = await _wait_for_hangup(result["request_uuid"])
            logger.info(f"Fleet alert call {attempt}: {status}")
            if status == "completed":
                return True
            await asyncio.sleep(RETRY_AFTER)
    return False

def call_ended(request_uuid: str, status: str) -> None:
    """server.py calls this from /hangup for every call; alert calls are the ones we are waiting on"""
    _ended[request_uuid] = status
    _ended_event.set()

async def _wait_for_hangup(request_uuid: str) -> str:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + ALERT_CALL_TIMEOUT
    while request_uuid not in _ended:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return "timeout"
        _ended_event.clear()
        try:
            await asyncio.wait_for(_ended_event.wait(), remaining)
        except TimeoutError:
            return "timeout"
        return _ended.pop(request_uuid)

def alert_xml(alert_id: str) -> str:
    """What Vobiz plays when the manager answers: the alert twice, then the call ends by itself."""
    text = PENDING.get(alert_id, "Hoshiyar alert. Please check the fleet page.")
    return f'<Response><Speak voice="MAN" language="en-GB" loop="2">{escape(text)}</Speak></Response>'


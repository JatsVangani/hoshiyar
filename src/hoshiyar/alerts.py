"""Tell the fleet manager: Hoshiyar rings them and reads the alert out """

import os
import uuid
from xml.sax.saxutils import escape

from loguru import logger

from hoshiyar import vobiz

PENDING: dict[str, str] = {} # alert id -> text; /alert/{id} reads it when the manager picks up

async def notify_fleet(text: str) -> bool:
    """Ring FLEET_PHONE (MY_PHONE if unset) and speak the alert. True when Vobiz queued the call"""
    to = os.environ.get("FLEET_PHONE") or os.environ.get("MY_PHONE")
    logger.warning(f"FLEET ALERT -> {to}: {text}")
    if not to:
        return False
    alert_id = uuid.uuid4().hex
    PENDING[alert_id] = text
    try:
        await vobiz.dial(to, os.environ["LOCAL_SERVER_URL"], answer_path=f"/alert/{alert_id}")
    except Exception as e: # the driver's call must never care
        logger.error(f"Fleet alert call failed: {e}")
        return False
    return True

def alert_xml(alert_id: str) -> str:
    """What Vobiz plays when the manager answers: the alert twice, then the call ends by itself"""
    text = PENDING.get(alert_id, "Hoshiyar alert. Please check the fleet page")
    return f'<Response><Speak voice="MAN" language="en-GB" loop="2">{escape(text)}</Speak></Response>'


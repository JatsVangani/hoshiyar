"""Who gets called when. Today: the wake-up call after a break. Later: the nightly check-in rota."""

import asyncio
import os

from loguru import logger

from hoshiyar import vobiz

WAKEUP_AFTER = float(os.environ.get("WAKEUP_AFTER", "1200"))  # seconds; set 60 in .env for demos

CALL_KINDS: dict[str, str] = {}  # call_id -> "wakeup"; bot_phone looks up the kind when the stream starts
from hoshiyar import vobiz

WAKEUP_AFTER = float(os.environ.get("WAKEUP_AFTER", "1200"))  # seconds; set 60 in .env for demos

CALL_KINDS: dict[str, str] = {}  # call_id -> "wakeup"; bot_phone looks up the kind when the stream starts
_tasks: set[asyncio.Task] = set()  # keep references or asyncio may garbage-collect a sleeping task


def schedule_wakeup(phone: str) -> None:
    task = asyncio.create_task(_wakeup(phone))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    logger.info(f"Wake-up call to {phone} in {WAKEUP_AFTER:.0f} s")


async def _wakeup(phone: str) -> None:
    await asyncio.sleep(WAKEUP_AFTER)
    result = await vobiz.dial(phone, os.environ["LOCAL_SERVER_URL"])
    CALL_KINDS[result["request_uuid"]] = "wakeup"
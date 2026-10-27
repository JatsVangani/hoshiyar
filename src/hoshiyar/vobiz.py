"""Thin Vobiz REST cliet: dial out and hang up. Credentials come from the environment"""

import os
import asyncio

import httpx
from loguru import logger

API = "https://api.vobiz.ai/api/v1"

_ended: dict[str, str] = {}  # request_uuid -> CallStatus from /hangup
_ended_event = asyncio.Event()

def _auth() -> tuple[str, dict]:
    auth_id = os.environ["VOBIZ_AUTH_ID"]
    return auth_id, {"X-Auth-ID": auth_id, "X-Auth-Token": os.environ["VOBIZ_AUTH_TOKEN"]}

async def dial(to: str, base_url: str, answer_path: str = "/answer") -> dict:
    """Ring 'to' from our Vobiz number. Vobiz POSTs to {base_url}/answer when they pick up"""
    auth_id, headers = _auth()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{API}/Account/{auth_id}/Call",
            headers=headers,
            json={
                "from": os.environ["VOBIZ_PHONE_NUMBER"],
                "to": to,
                "answer_url": f"{base_url}{answer_path}",
                "answer_method": "POST",
                "hangup_url": f"{base_url}/hangup",
            },
        )
    logger.info(f"Vobiz dial {to}: {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()

async def hangup(call_uuid: str) -> None:
    """End a live call. 204 on success, 404 if it already ended, which is acceptable"""
    auth_id, headers = _auth()
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{API}/Account/{auth_id}/Call/{call_uuid}", headers=headers)
    logger.info(f"Vobiz hangup {call_uuid}: {r.status_code}")

def call_ended(request_uuid: str, status: str) -> None:
    """server.py calls this from /hangup for every call; whoever dialed it may be waiting."""
    _ended[request_uuid] = status
    _ended_event.set()


async def wait_for_hangup(request_uuid: str, timeout: float) -> str:
    """Block until /hangup reports this call over. Returns its CallStatus, or "timeout"."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
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

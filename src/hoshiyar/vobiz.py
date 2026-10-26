"""Thin Vobiz REST cliet: dial out and hang up. Credentials come from the environment"""

import os

import httpx
from loguru import logger

API = "https://api.vobiz.ai/api/v1"

def _auth() -> tuple[str, dict]:
    auth_id = os.environ["VOBIZ_AUTH_ID"]
    return auth_id, {"X-Auth-ID": auth_id, "X-Auth-Token": os.environ["VOBIZ_AUTH_TOKEN"]}

async def dial(to: str, base_url: str) -> dict:
    """Ring 'to' from our Vobiz number. Vobiz POSTs to {base_url}/answer when they pick up"""
    auth_id, headers = _auth()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{API}/Account/{auth_id}/Call",
            headers=headers,
            json={
                "from": os.environ["VOBIZ_PHONE_NUMBER"],
                "to": to,
                "answer_url": f"{base_url}/answer",
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


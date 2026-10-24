"""Thin client for the Bolna API. Everything that talks to Bolna lives here"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE  = "https://api.bolna.ai"
HEADERS = {"Authorization": f"Bearer {os.environ['BOLNA_API_KEY']}"}
TIMEOUT = 15

def me() -> dict:
    """Account check: wallet balance and concurrency"""
    r = httpx.get(f"{BASE}/user/me", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def start_call(agent_id: str, phone: str, user_data: dict | None = None) -> dict:
    """Place an outbound call. user_data keys become {{variables}} in the prompt"""
    body = {"agent_id": agent_id, "recipient_phone_number": phone}
    if user_data:
        body["user_data"] = user_data
    r = httpx.post(f"{BASE}/call", headers=HEADERS, json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_execution(execution_id: str) -> dict:
    """Fetch one call: status, transcript, extracted data, cost"""
    r = httpx.get(f"{BASE}/executions/{execution_id}", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    print(me())
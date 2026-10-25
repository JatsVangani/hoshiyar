"""HTTP front door. Run: uv run python -m hoshiyar.server   (keep `ngrok http 7860` running)"""

import os

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from loguru import logger

from hoshiyar.bot_phone import run_phone_bot

load_dotenv()

app = FastAPI()

VOBIZ_API = "https://api.vobiz.ai/api/v1"


@app.post("/dialout")
async def dialout():
    """Ask Vobiz to ring MY_PHONE. When it picks up, Vobiz POSTs to /answer for instructions."""
    base = os.environ["LOCAL_SERVER_URL"]
    auth_id = os.environ["VOBIZ_AUTH_ID"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{VOBIZ_API}/Account/{auth_id}/Call/",
            headers={
                "X-Auth-ID": auth_id,
                "X-Auth-Token": os.environ["VOBIZ_AUTH_TOKEN"],
            },
            json={
                "from": os.environ["VOBIZ_PHONE_NUMBER"],
                "to": os.environ["MY_PHONE"],
                "answer_url": f"{base}/answer",
                "answer_method": "POST",
                "hangup_url": f"{base}/hangup",
            },
        )
    logger.info(f"Vobiz dial response {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


@app.post("/answer")
async def answer():
    """Vobiz asks: they answered, what now? Answer: stream the audio to our /ws, mu-law 8 kHz."""
    ws_url = os.environ["LOCAL_SERVER_URL"].replace("https://", "wss://") + "/ws"
    xml = (
        "<Response>"
        '<Stream bidirectional="true" keepCallAlive="true" audioTrack="inbound" contentType="audio/x-mulaw;rate=8000">'
        f"{ws_url}</Stream>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


@app.post("/hangup")
async def hangup(request: Request):
    """Vobiz tells us the call ended, with duration and cause. Useful for the logs."""
    logger.info(f"Hangup event: {(await request.body()).decode()}")
    return Response(content="OK")


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """Vobiz opens this socket and streams the caller's audio both ways."""
    await websocket.accept()
    try:
        await run_phone_bot(websocket)
    except Exception as e:
        logger.exception(f"Call failed: {e}")
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
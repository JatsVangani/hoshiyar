"""HTTP front door. Run: uv run python -m hoshiyar.server   (keep `ngrok http 7860` running)"""

import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qs
# import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from loguru import logger

from hoshiyar.bot_phone import run_phone_bot
from hoshiyar import vobiz, alerts, scheduler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    rota = asyncio.create_task(scheduler.run_rota())  # the nightly rota runs for as long as the server does
    yield
    rota.cancel()


app = FastAPI(lifespan=lifespan)

# VOBIZ_API = "https://api.vobiz.ai/api/v1"


@app.post("/dialout")
async def dialout():
    """Ring MY_PHONE now as a check-in, outside the rota. Redials like a rota call if nobody picks up."""
    driver = scheduler.driver_for(os.environ["MY_PHONE"])
    scheduler.spawn(scheduler.place_call(driver, "checkin"))
    return {"calling": driver["name"]}


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

@app.post("/alert/{alert_id}")
async def alert(alert_id: str):
    """The fleet manager picked up: read the alert out loud. Vobiz hangs up when the XML runs out"""
    return Response(content=alerts.alert_xml(alert_id), media_type="application/xml")

@app.post("/hangup")
async def hangup(request: Request):
    """Vobiz tells us the call ended, with duration and cause. Useful for the logs."""
    body = (await request.body()).decode()
    logger.info(f"Hangup event: {body}")
    fields = {k: v[0] for k, v in parse_qs(body).items()}
    vobiz.call_ended(fields.get("RequestUUID", ""), fields.get("CallStatus", ""))
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
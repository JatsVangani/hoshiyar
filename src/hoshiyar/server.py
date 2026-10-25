"""HTTP front door. Run uv run python -m hoshiyar.server """

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
from loguru import logger
from pipecat.runner.types import WebSocketRunnerArguments
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from hoshiyar.bot_phone import run_phone_bot

load_dotenv()

app = FastAPI()

@app.post("/dialout")
async def dialout():
    """Ask Twilio to ring MY_PHONE. When it picks up, Twilio calls back /twiml"""
    to = os.environ["MY_PHONE"]
    client = TwilioClient(os.environ["TWILIO_ACCOUNT_SID"],
                          os.environ["TWILIO_AUTH_TOKEN"])
    call = client.calls.create(
        to=to,
        from_=os.environ["TWILIO_PHONE_NUMBER"],
        url=f"{os.environ['LOCAL_SERVER_URL']}/twiml",
        # url="https://webhooks.twilio.com/v1/Voice/Template/voice_text_to_speech",
        # method="POST",
    )
    logger.info(f"Dialing {to}, call sid {call.sid}")
    return {"call_sid": call.sid, "to": to}

@app.post("/twiml")
async def twiml():
    """Twilio asks: they answered, what now? Answer: stream the audio to our /ws"""
    ws_url = os.environ["LOCAL_SERVER_URL"].replace("https://", "wss://") + "/ws"
    response = VoiceResponse()
    connect = Connect()
    connect.append(Stream(url=ws_url))
    response.append(connect)
    response.pause(length=20)
    return Response(content=str(response), media_type="application/xml")

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """Twilio opens this socket and streams the caller's audio both ways"""
    await websocket.accept()
    try:
        await run_phone_bot(WebSocketRunnerArguments(websocket=websocket))
    except Exception as e:
        logger.exception(f"Call failed: {e}")
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
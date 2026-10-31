"""HTTP front door. Run: uv run python -m hoshiyar.server   (keep `ngrok http 7860` running)"""

import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qs
# import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from loguru import logger

load_dotenv()

from hoshiyar.bot_phone import run_phone_bot
from hoshiyar import vobiz, alerts, scheduler, fleet, trials, home
from urllib.parse import urlencode
from hoshiyar.trials import TrialError, Pending


@asynccontextmanager
async def lifespan(app: FastAPI):
    rota = asyncio.create_task(scheduler.run_rota())  # the nightly rota runs for as long as the server does
    yield
    rota.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")  # the fleet page's illustration

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

@app.get("/", response_class=HTMLResponse)
async def homepage():
    """The landing page: the pitch, and the way in to /fleet."""
    return home.render()


@app.get("/fleet", response_class=HTMLResponse)
async def fleet_page(request: Request):
    """The fleet manager's screen. Open /fleet on the ngrok URL from any phone.

    ?try=<id> opens the Try dialog on the code box, ?done=<id> on the booking, ?err=<text> on a refusal."""
    q = request.query_params
    return fleet.render(try_id=q.get("try"), done_id=q.get("done"), error=q.get("err"))


async def _form(request: Request) -> dict:
    body = (await request.body()).decode()
    return {k: v[0] for k, v in parse_qs(body).items()}


def _back(**params) -> RedirectResponse:
    return RedirectResponse("/fleet" + ("?" + urlencode(params) if params else ""), status_code=303)


async def _code_call(trial_id: str) -> None:
    """Ring the visitor and read the code. Never raises into the request: a failed dial is a log line."""
    entry = trials.get(trial_id)
    try:
        await vobiz.dial(entry["phone"], os.environ["LOCAL_SERVER_URL"], answer_path=f"/otp/{trial_id}")
    except Exception as e:
        logger.error(f"Trial code call to {trials.masked(entry['phone'])} failed: {e}")


@app.post("/try")
async def try_hoshiyar(request: Request):
    """The Try form: book a code call. Refusals go back to the page as ?err=."""
    form = await _form(request)
    try:
        entry = trials.create(form.get("name", ""), form.get("phone", ""), form.get("at", ""), lang=form.get("lang", "auto"))
        trials.note_call(entry["id"])
    except Pending as e:  # they closed the box while the phone was ringing: back to it
        return _back(**{"try": e.trial_id})
    except TrialError as e:
        return _back(err=str(e))
    logger.info(f"Trial: code call to {trials.masked(entry['phone'])} for {entry['name']!r}, call due {entry['at']}")
    scheduler.spawn(_code_call(entry["id"]))
    return _back(**{"try": entry["id"]})


@app.post("/try/{trial_id}/again")
async def try_again(trial_id: str):
    """The visitor did not hear the code: one more call, then they start over."""
    try:
        trials.note_call(trial_id)
    except TrialError as e:
        return _back(err=str(e))
    scheduler.spawn(_code_call(trial_id))
    return _back(**{"try": trial_id})


@app.post("/otp/{trial_id}")
async def otp(trial_id: str):
    """The visitor picked up: read the code twice. Vobiz hangs up when the XML ends."""
    return Response(content=alerts.speak_xml(trials.speak_text(trial_id)), media_type="application/xml")


@app.post("/verify")
async def verify(request: Request):
    """The typed code. Right: the trial joins tonight's rota. Wrong: back to the box with the reason."""
    form = await _form(request)
    trial_id = form.get("id", "")
    try:
        entry = trials.verify(trial_id, form.get("code", ""))
    except TrialError as e:
        if trials.get(trial_id) is None or "locked" in str(e) or "expired" in str(e):
            return _back(err=str(e))
        return _back(**{"try": trial_id, "err": str(e)})
    logger.info(f"Trial verified: {entry['name']!r} {trials.masked(entry['phone'])} at {entry['at']}")
    return _back(done=entry["id"])

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
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=7860)  # the VPS unit sets HOST=127.0.0.1: only Caddy reaches it
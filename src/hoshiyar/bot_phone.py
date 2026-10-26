"""Phone version: one Vobiz call = one pipeline. server.py calls this per WebSocket.

Vobiz speaks Plivo's audio-streaming protocol, so Pipecat's Plivo serializer does the work.
"""

from fastapi import WebSocket
from loguru import logger
from hoshiyar.pipeline import opener_frame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner

from hoshiyar.pipeline import build_pipeline
from hoshiyar import vobiz

PHONE_SAMPLE_RATE = 8000  # mu-law over the telephone network


async def run_phone_bot(websocket: WebSocket):
    # Reads Vobiz's "start" message and pulls out the stream and call ids.
    transport_type, call_data = await parse_telephony_websocket(websocket)
    logger.info(f"Stream started: detected={transport_type} call={call_data['call_id']}")

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=PlivoFrameSerializer(
                stream_id=call_data["stream_id"],
                call_id=call_data["call_id"],
                params=PlivoFrameSerializer.InputParams(auto_hang_up=False),
            ),
        ),
    )

    pipeline, state = build_pipeline(transport, PHONE_SAMPLE_RATE)
    state.call_id = call_data["call_id"]

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=PHONE_SAMPLE_RATE,
            audio_out_sample_rate=PHONE_SAMPLE_RATE,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[MetricsLogObserver()],
    )
    runner = WorkerRunner(handle_sigint=False)  # uvicorn owns Ctrl+C, not us
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await worker.queue_frames([opener_frame()])  # bot speaks first

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.run()
    logger.info(f"Call summary: scores={state.scores} final mode={state.mode}")
    if state.hangup_requested:
        await vobiz.hangup(state.call_id)
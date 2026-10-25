"""Phone version: one Twilio call = one pipeline. server.py calls this per WebSocket"""

from loguru import logger
from pipecat.frames.frames import LLMRunFrame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.runner.types import WebSocketRunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

from hoshiyar.pipeline import build_pipeline

PHONE_SAMPLE_RATE = 8000 # what the telephone network carries

async def run_phone_bot(runner_args: WebSocketRunnerArguments):
    # Reads Twilio's handshake off the socket, picks the Twilio serializer
    # (mu-law 8 kHz <-> PCM) and sets add_wav_header=False for us
    transport = await create_transport(
        runner_args,
        {"twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True)},
    )
    logger.info(f"Call connected to {runner_args.call_data.to_number}")

    worker = PipelineWorker(
        build_pipeline(transport, PHONE_SAMPLE_RATE),
        params=PipelineParams(
            audio_in_sample_rate=PHONE_SAMPLE_RATE,
            audio_out_sample_rate=PHONE_SAMPLE_RATE,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[MetricsLogObserver()],
    )
    runner = WorkerRunner(handle_sigint=False) # uvicorn owns Ctrl+C
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await worker.queue_frames([LLMRunFrame()]) # bot speaks first

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.run()
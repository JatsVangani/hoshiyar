"""
for local : the bare pipeline 
mic -> Sarvam realtime STT -> LLM -> Sarvam TTS -> speaker

No phone , no persona , no logic
Just the five component talking to each other
Run: uv run python -m hoshiyar.bot_local
Stop: Ctrl+C
"""

import asyncio

from dotenv import load_dotenv
from hoshiyar.pipeline import opener_frame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.workers.runner import WorkerRunner

from hoshiyar.pipeline import build_pipeline

load_dotenv()

SAMPLE_RATE = 16000


async def main():
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_enabled=True,
            audio_out_sample_rate=SAMPLE_RATE,
        )
    )

    pipeline, state = build_pipeline(transport, SAMPLE_RATE)
    
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        observers=[MetricsLogObserver()],
    )
    await worker.queue_frames([opener_frame()])

    runner = WorkerRunner()
    await runner.add_workers(worker)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
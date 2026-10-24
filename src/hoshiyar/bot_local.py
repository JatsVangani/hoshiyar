"""
for local : the bare pipeline 
mic -> Sarvam realtime STT -> LLM -> Sarvam TTS -> speaker

No phone , no persona , no logic
Just the five component talking to each other
Run: uv run python -m hoshiyar.bot_local
Stop: Ctrl+C
"""

import asyncio
import os

from dotenv import load_dotenv
from pipecat.frames.frames import LLMRunFrame
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.turns.user_start import ExternalUserTurnStartStrategy
from pipecat.turns.user_stop import ExternalUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner
from pipecat.services.google.llm import GoogleLLMService

load_dotenv()

SAMPLE_RATE = 16000

SYSTEM_PROMPT = (
    "Tum ek dost ho jo Hindi mein baat karta hai."
    "Chhote jawab do, ek ya do vaakya. Devanagari mein likho."
)

def build_pipeline():
    # 1. laptop's mic and speaker
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_enabled=True,
            audio_out_sample_rate=SAMPLE_RATE,
        )
    )

    # 2. Speech to text. Sarvam detects sppech start/stop on its server,
    # so there is no separate VAD in this pipeline
    stt = SarvamRealtimeSTTService(
        api_key=os.environ["SARVAM_API_KEY"],
        settings=SarvamRealtimeSTTService.Settings(
            language="hi-IN",
            mode="transcribe",
            stream_type="fast",
        ),
        should_interrupt=True,
    )

    # 3. The brain
    llm = GoogleLLMService(
        api_key=os.environ["GOOGLE_API_KEY"],
        settings=GoogleLLMService.Settings(
            model="gemini-2.5-flash",
            thinking=GoogleLLMService.ThinkingConfig(thinking_budget=0),
        ),
    )

    # 4. Text to speech
    tts = SarvamTTSService(
        api_key=os.environ["SARVAM_API_KEY"],
        sample_rate=SAMPLE_RATE,
        settings=SarvamTTSService.Settings(
            model="bulbul:v3",
            voice="rahul",
            language="hi-IN",
            min_buffer_size=20,
        ),
    )

    # 5. Memory of the conversation, plus the rules for when a user turn
    # starts and ends "External" means: trust the STT's speech events.
    context = LLMContext([{"role": "system", "cotent": SYSTEM_PROMPT}])
    user_agg, assisant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
             user_turn_strategies=UserTurnStrategies(
                start=[ExternalUserTurnStartStrategy()],
                stop=[ExternalUserTurnStopStrategy(timeout=0.2, wait_for_transcript=True)],
            ),
            user_idle_timeout=12.0,
            user_turn_stop_timeout=3.0,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_agg,
            llm,
            tts,
            transport.output(),
            assisant_agg,
        ]
    )
    return pipeline

async def main():
    worker = PipelineWorker(
        build_pipeline(),
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        observers=[MetricsLogObserver()],
    )

    await worker.queue_frames([LLMRunFrame()])

    runner = WorkerRunner()
    await runner.add_workers(worker)
    await runner.run()

if __name__ == "__main__":
    asyncio.run(main())
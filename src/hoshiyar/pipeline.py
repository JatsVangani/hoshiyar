"""The shared voice pipeline audio in -> Sarvam STT -> Gemini -> Sarvam TTS -> audio out
Transport-agnostic. bot_local.py plugs in the laptop mic, bot_phone.py plugs in a Twilio call
"""

import os

from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_stop import ExternalUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.frames.frames import TTSSpeakFrame

from loguru import logger
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.google.llm import GoogleLLMService

from hoshiyar.brain import OPENER, persona_for, CallState, make_tools, FIRST_NUDGE_AFTER, nudge_for 

from pipecat.turns.user_mute.mute_until_first_bot_complete_user_mute_strategy import (
    MuteUntilFirstBotCompleteUserMuteStrategy,
)

# provider -> (service class, key env var, model env var, default model, extra settings)
LLM_PROVIDERS = {
    "sarvam": (SarvamLLMService, "SARVAM_API_KEY", "SARVAM_MODEL", "gemma4", {}),
    "groq": (GroqLLMService, "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-120b", {}),
    "gemini": (
        GoogleLLMService, "GOOGLE_API_KEY", "GEMINI_MODEL", "gemini-3.6-flash",
        {"thinking": GoogleLLMService.ThinkingConfig(thinking_level="minimal")},
    ),
}

# OPENER = "नमस्ते, मैं होशियार बोल रहा हूँ। आप कैसे हो?"

# SYSTEM_PROMPT = (
#     "Tum Hoshiyar ho, ek dost jo Hindi mein baat karta hai. "
#     f"Call uthte hi tum keh chuke ho: '{OPENER}' Ab uske jawab se baat aage badhao. "
#     "Chhote jawab do, ek ya do vaakya. Devanagari mein likho, koi markdown ya asterisk nahi."
# )

def opener_frame(text: str = OPENER) -> TTSSpeakFrame:
    """The first thing the driver hears, spoken straight from TTS so there is no LLM wait.

    append_to_context=False: the system prompt already tells the model this was said.
    interruptible=False: the driver's reflexive 'hello' on pickup must not cut it off.
    """
    frame = TTSSpeakFrame(text, append_to_context=False)
    frame.interruptible = False
    return frame

def make_llm(kind: str = "checkin"):
    provider = os.environ.get("LLM_PROVIDER", "sarvam").lower()
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {sorted(LLM_PROVIDERS)}, not {provider!r}")
    service, key_var, model_var, default_model, extra = LLM_PROVIDERS[provider]
    model = os.environ.get(model_var, default_model)
    logger.info(f"LLM: {provider} / {model}")
    return service(
        api_key=os.environ[key_var],
        settings=service.Settings(model=model, system_instruction=persona_for(kind), **extra),
    )

def build_pipeline(transport: BaseTransport, sample_rate: int, kind: str = "checkin") -> tuple[Pipeline, CallState]:
    # Speech to text. Sarvam accepts 8000 or 16000 Hz, so we tell it which one.
    stt = SarvamRealtimeSTTService(
        api_key=os.environ["SARVAM_API_KEY"],
        sample_rate=sample_rate,
        settings=SarvamRealtimeSTTService.Settings(
            language="hi-IN",
            mode="transcribe",
            stream_type="fast",
        ),
        should_interrupt=True,
    )

    # The brain. system_instructions lives inside Settings in Pipecat 1.14
    llm = make_llm(kind)

    # Text to speech, generated at the transport's rate so nothing is resampled.
    tts = SarvamTTSService(
        api_key=os.environ["SARVAM_API_KEY"],
        sample_rate=sample_rate,
        settings=SarvamTTSService.Settings(
            model="bulbul:v3",
            voice="rahul",
            language="hi-IN",
            min_buffer_size=30,
        ),
    )

    # Conversation memory plus the turn rules
    # context = LLMContext(
    #     [{"role": "user", "content": "Ek line mein namaste bolo aur poochho main kaisa hoon."}]
    # )
    state = CallState()
    context = LLMContext(tools=make_tools(state))
    
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                start=[MinWordsUserTurnStartStrategy(min_words=3)],
                stop=[ExternalUserTurnStopStrategy(timeout=0.2, wait_for_transcript=True)],
            ),
            user_mute_strategies=[MuteUntilFirstBotCompleteUserMuteStrategy()],
            user_idle_timeout=FIRST_NUDGE_AFTER,
            user_turn_stop_timeout=3.0,
        ),
    )

    @user_agg.event_handler("on_user_turn_idle")
    async def on_user_turn_idle(aggregator):
        line = nudge_for(state)
        logger.info(f"Driver quiet, nudge #{state.unanswered} in {state.mode}: {line}")
        await aggregator.push_frame(TTSSpeakFrame(line)) # goes down through LLM (pass-through) to TTS

    @user_agg.event_handler("on_user_turn_started")
    async def on_user_turn_started(aggregator, strategy):
        state.unanswered = 0
        state.driver_turns += 1

    pipeline =  Pipeline(
        [
            transport.input(),
            stt,
            user_agg,
            llm,
            tts,
            transport.output(),
            assistant_agg,
        ]
    )

    return pipeline, state

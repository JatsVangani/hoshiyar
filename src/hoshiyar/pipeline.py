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
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_stop import ExternalUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.frames.frames import TTSSpeakFrame

from hoshiyar.brain import OPENER, PERSONA, CallState, make_tools

# OPENER = "नमस्ते, मैं होशियार बोल रहा हूँ। आप कैसे हो?"

# SYSTEM_PROMPT = (
#     "Tum Hoshiyar ho, ek dost jo Hindi mein baat karta hai. "
#     f"Call uthte hi tum keh chuke ho: '{OPENER}' Ab uske jawab se baat aage badhao. "
#     "Chhote jawab do, ek ya do vaakya. Devanagari mein likho, koi markdown ya asterisk nahi."
# )

def opener_frame() -> TTSSpeakFrame:
    """The first thing the driver hears, spoken straight from TTS so there is no LLM wait.

    append_to_context=False: the system prompt already tells the model this was said.
    interruptible=False: the driver's reflexive 'hello' on pickup must not cut it off.
    """
    frame = TTSSpeakFrame(OPENER, append_to_context=False)
    frame.interruptible = False
    return frame

def build_pipeline(transport: BaseTransport, sample_rate: int) -> tuple[Pipeline, CallState]:
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
    llm = GoogleLLMService(
        api_key=os.environ["GOOGLE_API_KEY"],
        settings=GoogleLLMService.Settings(
            model="gemini-3.6-flash",
            system_instruction=PERSONA,
            thinking=GoogleLLMService.ThinkingConfig(thinking_level="minimal"),
        ),
    )

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
            user_idle_timeout=12.0,
            user_turn_stop_timeout=3.0,
        ),
    )

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

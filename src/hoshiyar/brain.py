"""The brain: who Hoshiyar is, the 1-to-9 sleepiness check-in, and the three conversation modes."""

import time
from dataclasses import dataclass, field

from loguru import logger
from pipecat.services.llm_service import FunctionCallParams
from pipecat.frames.frames import (
    EndWorkerFrame,
    FunctionCallResultProperties,
    TTSSpeakFrame,
    UserIdleTimeoutUpdateFrame,
)
from pipecat.processors.frame_processor import FrameDirection

OPENER = "नमस्ते, मैं होशियार बोल रहा हूँ। आप कैसे हो?"

PERSONA = (
    "Tum Hoshiyar ho: raat ko truck chala rahe driver ka phone par saathi, jaise cabin mein baitha khalasi. "
    "Hindi mein baat karo, Devanagari mein likho. Koi markdown ya asterisk nahi. "
    "Ek baar mein ek ya do chhote vaakya, kyunki driver gaadi chala raha hai aur sun raha hai, padh nahi raha. "
    "Kabhi lecture mat do. Seedhe, apnepan se, thodi hansi-mazaak ke saath baat karo. "
    f"Call uthte hi tum keh chuke ho: '{OPENER}' "
    "Driver ke pehle jawab ke baad, aaram se poochho: 'Neend to nahi aa rahi? Aankhein bhaari to nahi?' "
    "Driver jo bhi bole, usse khud 1 se 9 ka number nikaalo: ekdum fresh ya nahi aa rahi = 1 ya 2, "
    "theek-thaak = 3 ya 4, thoda thaka ya jamhai = 5 ya 6, neend aa rahi hai ya aankhein bhaari = 7 ya 8, "
    "aankhein band ho rahi hain ya jhapki = 9. Number poochhne ki zaroorat nahi; seedha record_sleepiness call karo. "
    "Sirf tab number poochho jab jawab se kuch samajh hi na aaye. "
    "Tool jo mode bataye, usi hisaab se aage baat karo. "
    "Pehle 'kaise ho' ke jawab ko neend ka score mat maano; score sirf neend waale sawaal ke jawab se nikaalo. "
    "Jab driver alvida kahe, jaise 'bye', 'chalo', 'rakhta hoon', 'band karo', ya saaf lage ki ab baat nahi karni, "
    "toh end_call tool call karo aur farewell mein ek chhoti si vidaai line do. Vidaai alag se mat bolo, sirf tool ke zariye. "
    "'Ruko' ya 'chup' ka matlab call band karna nahi hai: bas 'theek hai' bolo aur phir tab tak kuch mat bolo jab tak driver khud na bole. "
    "Tum sirf driver ke bole hue shabd sunte ho; chheenk, horn, gaana ya shor tumhe sunai nahi dete, toh aisa dawa mat karo. "
    "Taaza khabar, aaj ka match ya score tumhe nahi pata. Jo nahi pata, seedha bolo 'mujhe nahi pata'; kabhi bana kar mat bolo. "
)

MODES = {
    "QUIET": (
        "Driver taaza hai (1 se 3). Mode QUIET: ek line mein 'badhiya' jaisa kuch bolo, zyada baat mat karo. "
        "Bolo ki tum thodi der mein phir haal poochhoge. "
    ),
    "MILD": (
        "Driver thoda thaka hai (4 se 6). Mode MILD: halki-phulki baat karo. Ghar, khaana, gaana, raaste ki baatein. "
        "Har do-teen baaton mein ek sawaal poochho taaki driver bolta rahe. Chai ya paani ka zikr karo. "
        "Gaane ke baare mein baat karo, par gaana gao mat."
    ),
    "HEAVY": (
        "Driver ko neend aa rahi hai (7 se 9). Mode HEAVY: pehle saaf bolo ki agle dhabe ya safe jagah par bees minute rukna chahiye. "
        "Phir driver ko jagaye rakhne ke liye tez sawaal-jawaab karo. Sirf aise sawaal jinka jawab tumhe pakka pata ho: "
        "rajdhaniyan, purani filmein aur gaane, cricket ke purane record, ya driver ki apni gaadi aur raasta "
        "(agla shehar, raftaar, kitne ghante chale). Kal raat ka match ya taaza score kabhi mat poochho. "
        "Chhote sawaal, jaldi-jaldi. Driver ko sochne aur bolne par majboor karo. "
    ),
}

# Seconds of silence after the bot stops talking before it speaks up again.
# A fresh driver is left alone for a while; for a sleepy driver, silence is the alarm.
FIRST_NUDGE_AFTER = 12.0  # before any score: 'can you hear me?'
RECHECK_AFTER = {"QUIET": 90.0, "MILD": 45.0, "HEAVY": 12.0}

CHECK_IN = "नींद तो नहीं आ रही? आँखें भारी तो नहीं?"
NUDGES = {
    "QUIET": "फिर से पूछ रहा हूँ, " + CHECK_IN,
    "MILD": "फिर से पूछ रहा हूँ, " + CHECK_IN,
    "HEAVY": "भाई! सुन रहे हो? बोलो, जवाब दो!",
}
ALARM = "गाड़ी किनारे लगाओ, अभी! भाई, बोलो!"  # HEAVY driver ignored a nudge

def mode_for(score: int) -> str:
    if score <= 3:
        return "QUIET"
    if score <= 6:
        return "MILD"
    return "HEAVY"

@dataclass
class CallState:
    """Everything we learn during one call. Later pieces read this: fatigue, scheduler, fleet page."""

    started_at: float = field(default_factory=time.time)
    scores: list[tuple[float, int]] = field(default_factory=list)  # (seconds into call, score)
    mode: str = "MILD"
    call_id: str | None = None
    hangup_requested: bool = False
    unanswered: int = 0 # nudges in a row the driver has not replied to
    unresponsive: bool = False # HEAVY driver ignored two nudges; the break protocol hooks here
    reply_delays: list[tuple[float, float]] = field(default_factory=list)  # (seconds into call, seconds to first word)

def nudge_for(state: CallState) -> str:
    """What the bot says when the driver has been quiet for the mode's interval."""
    state.unanswered += 1
    if not state.scores:
        return "हैलो, सुनाई दे रहा है? " + CHECK_IN
    if state.mode == "HEAVY" and state.unanswered >= 2:
        state.unresponsive = True
        logger.warning(f"Driver unresponsive: {state.unanswered} HEAVY nudges unanswered")
        return ALARM
    return NUDGES[state.mode]

def make_tools(state: CallState):
    """Build the tool list bound to this call's state."""

    async def record_sleepiness(params: FunctionCallParams, score: int, said: str):
        """Record how sleepy the driver is, inferred from whatever they said about how they feel.

        Args:
            score: Your reading on the 1-to-9 scale. 1 means fully alert, 9 means fighting sleep.
            said: The driver's own words that you based the score on.
        """
        score = max(1, min(9, int(score)))
        state.scores.append((round(time.time() - state.started_at), score))
        state.mode = mode_for(score)
        logger.info(f"Sleepiness {score} ({said!r}) -> mode {state.mode}")
        # The user aggregator sits upstream of the LLM; this retunes its silence timer for the new mode.
        await params.llm.push_frame(
            UserIdleTimeoutUpdateFrame(timeout=RECHECK_AFTER[state.mode]), FrameDirection.UPSTREAM
        )
        await params.result_callback({"recorded": score, "mode": state.mode, "instructions": MODES[state.mode]})

    async def end_call(params: FunctionCallParams, farewell: str):
        """End the call after speaking a short farewell. Use when the driver says goodbye, asks to stop, or is clearly done.

        Args:
            farewell: One short goodbye line in Devanagari Hindi, spoken before hanging up.
        """
        state.hangup_requested = True
        logger.info(f"Bot ending call: {farewell!r}")
        await params.result_callback(
            {"status": "ending"}, properties=FunctionCallResultProperties(run_llm=False)
        )
        await params.llm.push_frame(TTSSpeakFrame(farewell))
        await params.llm.push_frame(EndWorkerFrame(reason="bot ended call"))

    return [record_sleepiness, end_call]
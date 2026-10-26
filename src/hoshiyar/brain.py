"""The brain: who Hoshiyar is, the 1-to-9 sleepiness check-in, and the three conversation modes."""

import time
from dataclasses import dataclass, field

from loguru import logger
from pipecat.services.llm_service import FunctionCallParams

OPENER = "नमस्ते, मैं होशियार बोल रहा हूँ। आप कैसे हो?"

PERSONA = (
    "Tum Hoshiyar ho: raat ko truck chala rahe driver ka phone par saathi, jaise cabin mein baitha khalasi. "
    "Hindi mein baat karo, Devanagari mein likho. Koi markdown ya asterisk nahi. "
    "Ek baar mein ek ya do chhote vaakya, kyunki driver gaadi chala raha hai aur sun raha hai, padh nahi raha. "
    "Kabhi lecture mat do. Seedhe, apnepan se, thodi hansi-mazaak ke saath baat karo. "
    f"Call uthte hi tum keh chuke ho: '{OPENER}' "
    "Driver ke pehle jawab ke baad, aaram se poochho: 'Ek se nau tak, neend kitni aa rahi hai? "
    "Ek matlab ekdum taaza, nau matlab aankhein band ho rahi hain.' "
    "Jab driver number bataye, turant record_sleepiness tool call karo, phir tool jo mode bataye usi hisaab se baat karo. "
    "Agar driver kahe 'ruko', 'chup', 'band karo' ya 'baad mein', toh bas 'theek hai, dhyan se chalana' bolo aur aage se bahut kam bolo."
)

MODES = {
    "QUIET": (
        "Driver taaza hai (1 se 3). Mode QUIET: ek line mein 'badhiya' jaisa kuch bolo, zyada baat mat karo. "
        "Bolo ki tum thodi der mein phir haal poochhoge."
    ),
    "MILD": (
        "Driver thoda thaka hai (4 se 6). Mode MILD: halki-phulki baat karo. Ghar, khaana, gaana, raaste ki baatein. "
        "Har do-teen baaton mein ek sawaal poochho taaki driver bolta rahe. Chai ya paani ka zikr karo."
    ),
    "HEAVY": (
        "Driver ko neend aa rahi hai (7 se 9). Mode HEAVY: pehle saaf bolo ki agle dhabe ya safe jagah par bees minute rukna chahiye. "
        "Phir driver ko jagaye rakhne ke liye tez sawaal-jawaab karo: desh, cricket, filmein, raaste ke shehar. "
        "Chhote sawaal, jaldi-jaldi. Driver ko sochne aur bolne par majboor karo."
    ),
}

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

def make_tools(state: CallState):
    """Build the tool list bound to this call's state."""

    async def record_sleepiness(params: FunctionCallParams, score: int):
        """Record the driver's self-reported sleepiness, right after they say a number from 1 to 9.

        Args:
            score: The number the driver said. 1 means fully alert, 9 means fighting sleep.
        """
        score = max(1, min(9, int(score)))
        state.scores.append((round(time.time() - state.started_at), score))
        state.mode = mode_for(score)
        logger.info(f"Sleepiness {score} -> mode {state.mode}")
        await params.result_callback({"recorded": score, "mode": state.mode, "instructions": MODES[state.mode]})

    return [record_sleepiness]
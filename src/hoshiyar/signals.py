"""Fatigue signals that do not come from words: how long the driver takes to answer."""

import time
from statistics import median

from loguru import logger

from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, UserStartedSpeakingFrame
from pipecat.observers.base_observer import BaseObserver, FramePushed

from hoshiyar.brain import CallState

DRIFT_LEVELS = ("steady", "drifting", "drifted")
MIN_SAMPLES = 4  # fewer than this and a slow answer is just a slow answer


def drift(delays: list[tuple[float, float]]) -> str:
    """How the driver's reply delay has moved over this call.

    Baseline = median of the first three delays, recent = median of the last three. Both an absolute
    and a relative rise are required, so a chatty 0.3 s driver slowing to 1 s is not flagged, and a
    slow 3 s driver slowing to 4 s is not either.
    """
    ys = [d for _, d in delays]
    if len(ys) < MIN_SAMPLES:
        return "steady"
    base, recent = median(ys[:3]), median(ys[-3:])
    if recent >= max(base + 3.0, 2.0 * base):
        return "drifted"
    if recent >= max(base + 1.5, 1.5 * base):
        return "drifting"
    return "steady"

class ReplyDelayObserver(BaseObserver):
    """Seconds from the bot going quiet to the driver's first word. Trending up over a call = fatigue"""

    def __init__(self, state: CallState):
        super().__init__()
        self._state = state
        self._bot_stopped_at: int | None = None # pipeline clock, nanoseconds

    async def on_push_frame(self, data: FramePushed):
        if not data.first_push:
            return
        if isinstance(data.frame, BotStoppedSpeakingFrame):
            self._bot_stopped_at = data.timestamp
        elif isinstance(data.frame, BotStartedSpeakingFrame):
            self._bot_stopped_at = None # the bot spoke again (nudge or next turn); measure fromt the newer stop
        elif isinstance(data.frame, UserStartedSpeakingFrame) and self._bot_stopped_at is not None:
            delay = (data.timestamp - self._bot_stopped_at) / 1e9
            self._state.reply_delays.append((round(time.time() - self._state.started_at), round(delay, 2)))
            self._bot_stopped_at = None
            verdict = drift(self._state.reply_delays)
            if DRIFT_LEVELS.index(verdict) > DRIFT_LEVELS.index(self._state.drift):  # only ever worsens within a call
                self._state.drift = verdict
                logger.warning(f"Reply delay drift: {verdict} after {self._state.reply_delays}")

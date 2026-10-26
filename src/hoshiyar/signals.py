"""Fatigue signals that do not come from words: how long the driver takes to answer."""

import time

from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, UserStartedSpeakingFrame
from pipecat.observers.base_observer import BaseObserver, FramePushed

from hoshiyar.brain import CallState

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

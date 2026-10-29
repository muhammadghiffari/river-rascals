"""Pure prototype cue selection and bounded playback configuration (no engine imports)."""
from __future__ import annotations

import random
from dataclasses import dataclass

MAX_VOICES = 6
MAX_EVENT_VOICES = 2
MAX_ERRORS = 32


@dataclass(frozen=True)
class EventSpec:
    prefix: str
    variations: int
    cooldown: float
    volume: float
    vary_pitch: bool = True


# Conservative gain staging: MAX_VOICES one-shots plus both ambience loops stay below full scale.
# The three paddle cues map onto the rr.core.oar phase machine: DIP -> PULL -> RECOVER.
EVENTS = {
    "paddle_dip": EventSpec("sfx/SFX_PaddleDip", 3, 0.10, 0.10),
    "paddle": EventSpec("sfx/SFX_PaddlePull", 3, 0.12, 0.12),
    "paddle_exit": EventSpec("sfx/SFX_PaddleExit", 3, 0.12, 0.09),
    "splash": EventSpec("sfx/SFX_SplashSmall", 4, 0.20, 0.12),
    "bump_soft": EventSpec("sfx/SFX_RaftBumpSoft", 3, 0.25, 0.12),
    "bump_hard": EventSpec("sfx/SFX_RaftBumpHard", 3, 0.40, 0.16),
    "click": EventSpec("ui/UI_Click", 1, 0.08, 0.10, False),
    "hover": EventSpec("ui/UI_Hover", 1, 0.10, 0.06, False),
}
# docs/06 section 9: pause silences everything except UI, so "paused" carries no loop.
MODE_LOOPS = {
    "menu": (("music/MUS_Menu_01.ogg", 0.25),),
    "playing": (("ambience/AMB_Creek_01.ogg", 0.18), ("sfx/SFX_WaterRushLoop_01.ogg", 0.12)),
    "paused": (),
    "complete": (("music/MUS_Menu_01.ogg", 0.25),),
}


@dataclass(frozen=True)
class Cue:
    path: str
    pitch: float
    volume: float


class AudioPolicy:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng if rng is not None else random.Random()
        self.last_index: dict[str, int] = {}
        self.last_time: dict[str, float] = {}

    def choose(self, event: str, now: float) -> Cue | None:
        if event not in EVENTS:
            raise ValueError(f"Unknown audio event: {event}")
        spec = EVENTS[event]
        if now - self.last_time.get(event, float("-inf")) < spec.cooldown:
            return None
        choices = [i for i in range(1, spec.variations + 1)
                   if spec.variations == 1 or i != self.last_index.get(event)]
        index = self.rng.choice(choices)
        self.last_index[event] = index
        self.last_time[event] = now
        pitch = self.rng.uniform(0.94, 1.06) if spec.vary_pitch else 1.0
        return Cue(f"{spec.prefix}_{index:02d}.ogg", pitch, spec.volume)

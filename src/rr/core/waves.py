"""Deterministic water-surface height. The water shader must mirror this function."""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Wave:
    amplitude: float   # metres
    wavelength: float  # metres
    speed: float       # m/s phase speed
    dir_x: float
    dir_y: float


DEFAULT_WAVES: tuple[Wave, ...] = (
    Wave(0.050, 6.0, 1.2, 1.0, 0.0),
    Wave(0.030, 3.1, 0.9, 0.7, 0.7),
    Wave(0.015, 1.7, 0.6, -0.4, 0.9),
)


def wave_height(x: float, y: float, t: float, base: float = 0.0,
                waves: Sequence[Wave] = DEFAULT_WAVES) -> float:
    h = base
    for w in waves:
        n = math.hypot(w.dir_x, w.dir_y) or 1.0
        k = 2.0 * math.pi / w.wavelength
        phase = k * ((w.dir_x * x + w.dir_y * y) / n - w.speed * t)
        h += w.amplitude * math.sin(phase)
    return h

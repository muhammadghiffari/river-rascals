"""Pure-Python frame-time statistics for benchmarks (no bge/bpy imports).

Public API: :func:`summarize`.

Input policy
------------
``frame_times_s`` is a sequence of per-frame durations in seconds. Every value
must be a finite number strictly greater than zero; anything else (``0``,
negative, ``nan``, ``inf``, ``bool``) raises :class:`ValueError` because a
non-positive interval cannot be turned into an fps figure and silently dropping
samples would make two runs incomparable. ``warmup_s`` must be a finite number
``>= 0``.

Warmup exclusion
----------------
Warmup is applied on *cumulative* frame timing, not on a frame index: frames
are consumed from the start of the run while the accumulated duration is below
``warmup_s``. The frame that crosses the boundary is also consumed, so the first
measured frame always starts at or after ``warmup_s`` of engine time.

Definitions
-----------
``fps_avg``      measured frames / total measured frame time.
``fps_min``      reciprocal of the longest measured frame time.
``p1_low_fps``   reciprocal of the 99th-percentile frame time.
``frame_time_ms`` p50/p95/p99/max of the measured frame times in milliseconds.
``stutter_count`` measured frames whose frame time is *strictly greater* than
                 twice the measured median frame time.

Percentile method
-----------------
Percentiles use linear interpolation between order statistics
(position ``p * (n - 1)`` in the 0-based sorted sample), i.e. the same
"linear"/type-7 rule as ``numpy.percentile(..., method="linear")`` and
``statistics.quantiles(method="inclusive")``. Median is the same rule at
``p = 0.5``.

Degenerate results
------------------
When warmup consumes every frame there is nothing to summarize. Every numeric
field is then ``None`` and ``stutter_count`` is ``0``. ``None`` is used instead
of ``nan``/``inf`` so the result is always valid JSON.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypedDict


class FrameTimeStats(TypedDict):
    """Frame-time percentiles and maximum, in milliseconds."""

    p50: float | None
    p95: float | None
    p99: float | None
    max: float | None


class BenchStats(TypedDict):
    """JSON-compatible summary of a benchmark run."""

    fps_avg: float | None
    fps_min: float | None
    p1_low_fps: float | None
    frame_time_ms: FrameTimeStats
    stutter_count: int
    frames_measured: int
    measured_s: float | None


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    """Return a linearly interpolated percentile of an already sorted sequence."""
    if not sorted_values:
        raise ValueError("percentile of empty sequence")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("percentile must be within [0, 1]")

    position = (len(sorted_values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]

    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def _empty_stats() -> BenchStats:
    """Result shape used when no frame survives the warmup window."""
    return {
        "fps_avg": None,
        "fps_min": None,
        "p1_low_fps": None,
        "frame_time_ms": {"p50": None, "p95": None, "p99": None, "max": None},
        "stutter_count": 0,
        "frames_measured": 0,
        "measured_s": None,
    }


def _validate(frame_times_s: Sequence[float], warmup_s: float) -> None:
    """Reject inputs that cannot produce a meaningful fps figure."""
    if isinstance(warmup_s, bool) or not isinstance(warmup_s, (int, float)):
        raise ValueError("warmup_s must be a number")
    if not math.isfinite(warmup_s) or warmup_s < 0:
        raise ValueError("warmup_s must be finite and non-negative")

    for dt in frame_times_s:
        if isinstance(dt, bool) or not isinstance(dt, (int, float)):
            raise ValueError("frame times must be numbers")
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("frame times must be finite and greater than zero")


def _measured_frames(frame_times_s: Sequence[float], warmup_s: float) -> list[float]:
    """Drop whole leading frames until the cumulative duration reaches ``warmup_s``."""
    elapsed = 0.0
    index = 0
    while index < len(frame_times_s) and elapsed < warmup_s:
        elapsed += frame_times_s[index]
        index += 1
    return list(frame_times_s[index:])


def summarize(frame_times_s: Sequence[float], warmup_s: float = 0.0) -> BenchStats:
    """Summarize ``frame_times_s`` after discarding ``warmup_s`` of engine time.

    See the module docstring for the input policy, the warmup rule and the
    percentile method.
    """
    _validate(frame_times_s, warmup_s)

    remaining = _measured_frames(frame_times_s, warmup_s)
    if not remaining:
        return _empty_stats()

    ordered = sorted(remaining)
    count = len(ordered)
    total_time = math.fsum(ordered)

    median = _percentile(ordered, 0.50)
    p99 = _percentile(ordered, 0.99)
    longest = ordered[-1]

    frame_time_ms: FrameTimeStats = {
        "p50": median * 1000.0,
        "p95": _percentile(ordered, 0.95) * 1000.0,
        "p99": p99 * 1000.0,
        "max": longest * 1000.0,
    }

    return {
        "fps_avg": count / total_time,
        "fps_min": 1.0 / longest,
        "p1_low_fps": 1.0 / p99,
        "frame_time_ms": frame_time_ms,
        "stutter_count": sum(1 for dt in remaining if dt > 2.0 * median),
        "frames_measured": count,
        "measured_s": total_time,
    }

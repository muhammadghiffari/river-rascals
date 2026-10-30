"""Pure-Python smoke-test report assembly (no bge/bpy imports).

The glue component (:mod:`rr.glue.smoke`) measures wall time and frame
intervals inside UPBGE; every decision about what those measurements mean
lives here so it can be unit-tested without an engine.

Two independent signal paths
----------------------------
``frame_times_s``          per-frame durations collected with
                           :func:`time.perf_counter`, summarized by
                           :mod:`rr.core.benchstats` — the authoritative
                           performance statistics (percentiles, 1% low).
``getAverageFrameRate()``  sampled once per second with timestamps; reduced
                           here as an additive *cross-check* only. The engine's
                           own estimate can return one implausible outlier
                           (a ~1e6 fps sample was observed on UPBGE 0.50
                           Linux), so the cross-check reports the median and a
                           post-warmup mean and keeps the sample count and
                           ``max_fps`` visible instead of trusting the
                           whole-run arithmetic mean.

Gate semantics
--------------
``ok`` = performance gate AND, when movement is expected, the movement gate.
The performance gate requires that at least one frame survived warmup
(``fps_avg`` and ``fps_min`` are not ``None``). The movement gate
(``moved_ok``) is only evaluated when ``expect_movement`` is true, so a
static scene (benchmark/menu/physics probe) can pass on performance alone.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

FPS_CROSSCHECK_SOURCE = "bge.logic.getAverageFrameRate() sampled once per second"
FPS_CROSSCHECK_SEMANTICS = (
    "engine's own estimate; it includes engine startup and the warmup window and "
    "cannot produce a 1% low; mean reported post-warmup only, median over all samples"
)

DEFAULT_MOVEMENT_THRESHOLD_M = 1.0


def _validate_warmup(warmup_s: float) -> None:
    if isinstance(warmup_s, bool) or not isinstance(warmup_s, (int, float)):
        raise ValueError("warmup_s must be a number")
    if not math.isfinite(warmup_s) or warmup_s < 0:
        raise ValueError("warmup_s must be finite and non-negative")


def summarize_fps_crosscheck(
    samples: Sequence[tuple[float, float | None]], warmup_s: float
) -> dict:
    """Reduce timestamped engine-fps samples to a robust JSON cross-check.

    ``samples`` is a sequence of ``(elapsed_s, value)`` items. ``value`` may be
    ``None`` or unusable (non-finite / <= 0 / bool) — those are dropped, the
    same policy as the benchmark harness, because the engine's estimate can
    claim exactly 0 or nonsense during startup.
    """
    _validate_warmup(warmup_s)

    base = {
        "source": FPS_CROSSCHECK_SOURCE,
        "samples": 0,
        "post_warmup_samples": 0,
        "min_fps": None,
        "median_fps": None,
        "mean_post_warmup_fps": None,
        "max_fps": None,
        "semantics": FPS_CROSSCHECK_SEMANTICS,
    }

    usable: list[tuple[float, float]] = []
    for item in samples:
        try:
            t, value = item
        except (TypeError, ValueError):
            raise ValueError("cross-check samples must be (elapsed_s, value) pairs") from None
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0:
            raise ValueError("sample times must be finite and non-negative")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        value = float(value)
        if not math.isfinite(value) or value <= 0.0:
            continue
        usable.append((float(t), value))

    if not usable:
        return base

    values = [value for _, value in usable]
    after = [value for t, value in usable if t >= warmup_s]

    base.update(
        samples=len(values),
        post_warmup_samples=len(after),
        min_fps=min(values),
        median_fps=statistics.median(values),
        mean_post_warmup_fps=(math.fsum(after) / len(after)) if after else None,
        max_fps=max(values),  # kept visible: a single ~1e6 outlier must not hide
    )
    return base


def build_smoke_report(
    *,
    seconds: float,
    warmup_s: float,
    frame_time_stats: dict,
    fps_crosscheck: dict,
    distance_moved_m: float,
    expect_movement: bool,
    movement_threshold_m: float = DEFAULT_MOVEMENT_THRESHOLD_M,
) -> dict:
    """Assemble the smoke report and evaluate the two gates.

    ``frame_time_stats`` comes from :func:`rr.core.benchstats.summarize`; its
    semantics (warmup discard, percentiles, stutter count) are unchanged here.
    """
    _validate_warmup(warmup_s)
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be finite and non-negative")
    if (not isinstance(distance_moved_m, (int, float))
            or not math.isfinite(distance_moved_m) or distance_moved_m < 0):
        raise ValueError("distance_moved_m must be finite and non-negative")
    if not isinstance(expect_movement, bool):
        raise ValueError("expect_movement must be a boolean")

    perf_ok = frame_time_stats.get("fps_avg") is not None and frame_time_stats.get("fps_min") is not None
    moved_ok = distance_moved_m > movement_threshold_m if expect_movement else None
    ok = bool(perf_ok) and (moved_ok if expect_movement else True)

    return {
        "seconds": round(float(seconds), 1),
        "warmup_s": float(warmup_s),
        "fps_avg": frame_time_stats.get("fps_avg"),
        "fps_min": frame_time_stats.get("fps_min"),
        "p1_low_fps": frame_time_stats.get("p1_low_fps"),
        "frame_time_ms": frame_time_stats.get("frame_time_ms"),
        "stutter_count": frame_time_stats.get("stutter_count", 0),
        "frames_measured": frame_time_stats.get("frames_measured", 0),
        "measured_s": frame_time_stats.get("measured_s"),
        "fps_crosscheck": fps_crosscheck,
        "expect_movement": expect_movement,
        "distance_moved_m": round(float(distance_moved_m), 2),
        "moved_ok": moved_ok,
        "ok": ok,
    }

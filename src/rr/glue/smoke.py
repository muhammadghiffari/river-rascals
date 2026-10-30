"""SmokeTest component: scripted run that writes a JSON report and quits.

Enable with env vars:  RR_SMOKE=1  RR_SMOKE_SECONDS=20  RR_SMOKE_OUT=smoke_result.json
Optional:              RR_SMOKE_WARMUP=3            warmup seconds discarded from the
                                                    cumulative frame time (default 3)
                       RR_SMOKE_EXPECT_MOVEMENT=0   static scenes: performance gate only
Attach to any always-present object (e.g. the raft). Exit status is read from the JSON.

Performance numbers come from per-frame ``time.perf_counter`` deltas summarized
by :mod:`rr.core.benchstats` (warmup discarded on cumulative frame time, real
percentiles and a 1% low). The once-per-second ``getAverageFrameRate`` samples
are kept only as an additive cross-check (median + post-warmup mean, with the
sample count and ``max_fps`` visible — a ~1e6 fps outlier sample was observed
on UPBGE 0.50 Linux). The report shape is :func:`rr.core.smokestats.build_smoke_report`.
"""
import json
import math
import os
import time
from collections import OrderedDict

import bge

from rr.core.benchstats import summarize
from rr.core.smokestats import build_smoke_report, summarize_fps_crosscheck

DEFAULT_SECONDS = 20.0
DEFAULT_WARMUP_SECONDS = 3.0
DEFAULT_OUT = "smoke_result.json"


def _env_float(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return float(default)
    return float(raw.strip())


def _env_str(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _env_bool(name, default):
    raw = _env_str(name, None)
    if raw is None:
        return bool(default)
    return raw != "0"


def _average_frame_rate():
    """The engine's estimated average fps, or None when unusable (cross-check only)."""
    try:
        value = float(bge.logic.getAverageFrameRate())
    except Exception:  # noqa: BLE001 - cross-check must never abort a smoke run
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None
    return value


class SmokeTest(bge.types.KX_PythonComponent):
    args = OrderedDict([
        ("Seconds", DEFAULT_SECONDS),
        ("Warmup Seconds", DEFAULT_WARMUP_SECONDS),
        ("Expect Movement", True),
    ])

    def start(self, args):
        self.enabled = os.environ.get("RR_SMOKE") == "1"
        if not self.enabled:
            return
        self.duration = _env_float("RR_SMOKE_SECONDS", args["Seconds"])
        self.warmup = _env_float("RR_SMOKE_WARMUP", args["Warmup Seconds"])
        self.expect_movement = _env_bool("RR_SMOKE_EXPECT_MOVEMENT", args["Expect Movement"])
        self.out = _env_str("RR_SMOKE_OUT", DEFAULT_OUT)
        self.t0 = time.time()
        self.prev_frame_tick = None
        self.frame_times = []
        self.fps_samples = []          # (elapsed_s, engine fps or None); cross-check only
        self.next_sample = 1.0
        self.start_pos = tuple(self.object.worldPosition)
        bge.logic.globalDict["rr_autopaddle"] = True
        print("[rr] smoke test started (%.0fs, warmup %.1fs%s)"
              % (self.duration, self.warmup, "" if self.expect_movement else ", static scene"))

    def update(self):
        if not self.enabled:
            return
        el = time.time() - self.t0

        # Per-frame durations for the authoritative statistics. The first update
        # establishes the tick; its delta would include the pre-first-update stall
        # (same rule as rr.glue.bench), so it is not measured.
        tick = time.perf_counter()
        if self.prev_frame_tick is not None:
            dt = tick - self.prev_frame_tick
            if math.isfinite(dt) and dt > 0:
                self.frame_times.append(dt)
        self.prev_frame_tick = tick

        if el >= self.next_sample:
            self.fps_samples.append((el, _average_frame_rate()))
            self.next_sample += 1.0

        if el >= self.duration:
            self._finish(el)

    def _write_report(self, report):
        tmp = self.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, self.out)

    def _finish(self, el):
        end = tuple(self.object.worldPosition)
        moved = sum((a - b) ** 2 for a, b in zip(end, self.start_pos, strict=True)) ** 0.5
        report = build_smoke_report(
            seconds=el,
            warmup_s=self.warmup,
            frame_time_stats=summarize(self.frame_times, self.warmup),
            fps_crosscheck=summarize_fps_crosscheck(self.fps_samples, self.warmup),
            distance_moved_m=moved,
            expect_movement=self.expect_movement,
        )
        self._write_report(report)
        print("[rr] smoke result:", report)
        bge.logic.endGame()

"""BenchRecorder — UPBGE Python Component that measures real frame times.

Attach once to any object that stays active for the whole benchmark scene (the
``BenchRoot`` empty in ``game/bench/*.blend``); the module is re-exported by
``game/rr_components.py`` as ``rr_components.BenchRecorder``.

Configuration (environment variables win over the component's UI arguments):

===========================  =================  ===================================
Variable                     Default            Meaning
===========================  =================  ===================================
``RR_BENCH``                 ``1``              ``0`` disables the component
``RR_BENCH_SECONDS``         ``60``             measured seconds *after* warmup
``RR_BENCH_WARMUP``          ``3``              warmup seconds, excluded
``RR_BENCH_OUT``             ``bench_result.json``  result path (created atomically)
``RR_BENCH_SCENE``           active scene name  scene label for the report
``RR_BENCH_PRESET``          ``None``           quality preset label
``RR_BENCH_RES``             ``None``           requested resolution, e.g. ``1280x720``
===========================  =================  ===================================

Timing uses :func:`time.perf_counter` deltas between component updates; the
warmup window and every statistic come from :func:`rr.core.benchstats.summarize`
(see that module for the metric definitions and the percentile rule). Only
frame durations and the listed metadata are serialized — no environment dump, no
credentials.

The component ends the game once the report is written so ``blenderplayer``
cannot linger after a run.

Frame-rate cross-check
----------------------
Alongside the interval statistics, ``bge.logic.getAverageFrameRate()`` (the
engine's own *estimated* average frame rate) is sampled once per second and its
minimum, average and maximum are recorded under ``fps_crosscheck`` in the
report. That value covers engine startup and the warmup window and cannot yield
a 1% low, so it is a second, independent view of the run: the frame-interval
statistics stay authoritative and are never replaced by it. ``max_fps`` is
recorded as well because this call was observed returning an implausible
~1e6 fps sample on UPBGE 0.50 Linux, which a bare average would hide.

Runtime check: the call exists on UPBGE 0.50 Linux (``blenderplayer``, Blender
5.0.1), returns a positive float once the engine is running, and ramps from the
startup value to the steady rate within the first seconds.

VERIFY: ``bge.logic.getGraphicsCardVendor`` and ``bge.render.getWindowWidth/Height``
were executed against UPBGE 0.50 Linux (see docs/16 P3 notes).
"""

import math
import os
import sys
import time
from collections import OrderedDict

import bge

from rr.core.benchreport import build_report, resolution_label, write_json_atomic
from rr.core.benchstats import summarize

DEFAULT_SECONDS = 60.0
DEFAULT_WARMUP_SECONDS = 3.0
DEFAULT_OUT = "bench_result.json"

#: How often ``getAverageFrameRate()`` is sampled for the cross-check.
FPS_SAMPLE_INTERVAL_S = 1.0

#: Extra wall-clock allowance before a stalled run is force-finished anyway.
HARD_STOP_SLACK_S = 60.0

FPS_CROSSCHECK_SOURCE = "bge.logic.getAverageFrameRate() sampled once per second"
FPS_CROSSCHECK_SEMANTICS = (
    "engine's own estimate; it includes engine startup and the warmup window and "
    "cannot produce a 1% low"
)


def _env_float(name, default):
    """Read an env override as float, falling back to *default* when unset."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return float(default)
    return float(raw)


def _env_str(name, default=None):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


class _EngineProbe:
    """Thin, failure-tolerant wrapper over the few bge calls the report needs.

    Every call is guarded: a missing symbol in a future/other engine build must
    degrade to ``None`` in the report rather than abort the benchmark.
    """

    @staticmethod
    def window_size():
        try:
            return bge.render.getWindowWidth(), bge.render.getWindowHeight()
        except Exception:  # noqa: BLE001 - metadata only
            return None

    @staticmethod
    def display_size():
        try:
            dims = bge.render.getDisplayDimensions()
        except Exception:  # noqa: BLE001 - metadata only
            return None
        try:
            return dims[0], dims[1]
        except (TypeError, IndexError):
            return None

    @staticmethod
    def vendor():
        try:
            return str(bge.logic.getGraphicsCardVendor())
        except Exception:  # noqa: BLE001 - metadata only
            return None

    @staticmethod
    def average_frame_rate():
        """The engine's own estimated average fps, or ``None`` if unusable."""
        try:
            value = float(bge.logic.getAverageFrameRate())
        except Exception:  # noqa: BLE001 - cross-check only
            return None
        if not math.isfinite(value) or value <= 0.0:
            return None
        return value

    @staticmethod
    def engine_name():
        try:
            return "UPBGE " + str(bge.app.version_string)
        except Exception:  # noqa: BLE001 - metadata only
            try:
                return "UPBGE " + ".".join(str(part) for part in bge.app.version)
            except Exception:  # noqa: BLE001 - metadata only
                return None


def _fps_crosscheck(samples):
    """Reduce once-per-second engine fps samples to a JSON-ready cross-check.

    Returns a mapping with the sample count and the minimum/average/maximum of
    the samples, or ``None`` for those three when the engine produced nothing
    usable. The interval statistics are unaffected by this: the cross-check is a
    second, independent view of the same run, not a replacement for it.
    """
    values = [float(value) for value in samples if value is not None]
    if not values:
        return {
            "source": FPS_CROSSCHECK_SOURCE,
            "samples": 0,
            "min_fps": None,
            "avg_fps": None,
            "max_fps": None,
            "semantics": FPS_CROSSCHECK_SEMANTICS,
        }
    return {
        "source": FPS_CROSSCHECK_SOURCE,
        "samples": len(values),
        "min_fps": min(values),
        "avg_fps": math.fsum(values) / len(values),
        # Recorded so a single implausible sample cannot hide inside the average:
        # this call was observed returning a ~1e6 fps outlier on UPBGE 0.50 Linux.
        "max_fps": max(values),
        "semantics": FPS_CROSSCHECK_SEMANTICS,
    }


class BenchRecorder(bge.types.KX_PythonComponent):
    """Sample per-frame durations, then write a JSON benchmark report and quit."""

    args = OrderedDict([
        ("Seconds", DEFAULT_SECONDS),
        ("Warmup Seconds", DEFAULT_WARMUP_SECONDS),
    ])

    def start(self, args):
        self.enabled = _env_str("RR_BENCH", "1") != "0"
        self.finished = False
        self.frame_times = []
        self.fps_samples = []
        self.next_fps_sample = FPS_SAMPLE_INTERVAL_S
        self.previous_at = None

        if not self.enabled:
            print("[rr] benchmark disabled (RR_BENCH=0)")
            return

        try:
            self.duration = _env_float("RR_BENCH_SECONDS", args.get("Seconds", DEFAULT_SECONDS))
            self.warmup = _env_float(
                "RR_BENCH_WARMUP", args.get("Warmup Seconds", DEFAULT_WARMUP_SECONDS)
            )
        except (TypeError, ValueError):
            print("[rr] benchmark error: RR_BENCH_SECONDS/RR_BENCH_WARMUP are not numbers")
            self.enabled = False
            return

        if not (self.duration > 0) or self.warmup < 0:
            print("[rr] benchmark error: duration must be > 0 and warmup >= 0")
            self.enabled = False
            return

        self.out = _env_str("RR_BENCH_OUT", DEFAULT_OUT)
        self.scene_label = _env_str("RR_BENCH_SCENE") or self._scene_name()
        self.preset = _env_str("RR_BENCH_PRESET")
        self.requested_resolution = _env_str("RR_BENCH_RES")

        self.started_at = time.perf_counter()
        self.hard_deadline = self.started_at + self.warmup + self.duration + HARD_STOP_SLACK_S

        print(
            "[rr] benchmark armed: %.1fs measured after %.1fs warmup -> %s"
            % (self.duration, self.warmup, self.out)
        )

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _scene_name():
        try:
            return bge.logic.getCurrentScene().name
        except Exception:  # noqa: BLE001 - metadata only
            return "unknown"

    def update(self):
        if not self.enabled or self.finished:
            return

        now = time.perf_counter()
        if self.previous_at is not None:
            delta = now - self.previous_at
            if delta > 0:
                self.frame_times.append(delta)
        self.previous_at = now

        elapsed = now - self.started_at
        if elapsed >= self.next_fps_sample:
            sample = _EngineProbe.average_frame_rate()
            if sample is not None:
                self.fps_samples.append(sample)
            while self.next_fps_sample <= elapsed:
                self.next_fps_sample += FPS_SAMPLE_INTERVAL_S

        if elapsed >= self.warmup + self.duration or now >= self.hard_deadline:
            self._finish(elapsed)

    def _finish(self, elapsed):
        """Summarize, write the report atomically, then end the game."""
        self.finished = True
        try:
            stats = summarize(self.frame_times, self.warmup)

            width_height = _EngineProbe.window_size()
            actual_resolution = (
                resolution_label(*width_height) if width_height else None
            )
            display = _EngineProbe.display_size()

            notes = [f"measured over {elapsed:.1f}s of engine time from component start"]
            if display:
                notes.append(f"display dimensions reported by the engine: {resolution_label(*display)}")

            crosscheck = _fps_crosscheck(self.fps_samples)
            if crosscheck["samples"]:
                notes.append(
                    "fps_crosscheck is the engine's own getAverageFrameRate() estimate, sampled "
                    "once per second; it includes engine startup and the warmup window, so it "
                    "covers a different window than the interval statistics and cannot produce "
                    "a 1% low - those statistics remain authoritative"
                )
            else:
                notes.append(
                    "bge.logic.getAverageFrameRate() produced no usable samples; the "
                    "fps_crosscheck is missing (the frame-interval statistics are unaffected)"
                )

            report = build_report(
                stats=stats,
                scene_label=self.scene_label,
                preset=self.preset,
                requested_resolution=self.requested_resolution,
                actual_resolution=actual_resolution,
                duration_s=self.duration,
                warmup_s=self.warmup,
                platform=sys.platform,
                engine=_EngineProbe.engine_name(),
                gpu_vendor=_EngineProbe.vendor(),
                fps_crosscheck=crosscheck,
                notes=notes,
            )

            try:
                destination = write_json_atomic(self.out, report)
                print("[rr] benchmark wrote %s" % destination)
            except OSError as exc:
                print("[rr] benchmark error: could not write report: %s" % exc)

            print(
                "[rr] benchmark result: avg %.1f fps, 1%% low %.1f fps, min %.1f fps, "
                "p99 %.1f ms, %d stutters, %d frames"
                % (
                    stats["fps_avg"] or 0.0,
                    stats["p1_low_fps"] or 0.0,
                    stats["fps_min"] or 0.0,
                    (stats["frame_time_ms"]["p99"] or 0.0),
                    stats["stutter_count"],
                    stats["frames_measured"],
                )
            )
            if crosscheck["samples"]:
                print(
                    "[rr] fps cross-check: getAverageFrameRate() min %.1f fps, avg %.1f fps, "
                    "max %.1f fps over %d samples (interval avg %.1f fps - different window, "
                    "see fps_crosscheck.semantics)"
                    % (
                        crosscheck["min_fps"],
                        crosscheck["avg_fps"],
                        crosscheck["max_fps"],
                        crosscheck["samples"],
                        stats["fps_avg"] or 0.0,
                    )
                )
            else:
                print("[rr] fps cross-check: getAverageFrameRate() produced no usable samples")
        finally:
            try:
                bge.logic.endGame()
            except Exception as exc:  # noqa: BLE001 - last resort, never hang the player
                print("[rr] benchmark error: endGame failed: %s" % exc)

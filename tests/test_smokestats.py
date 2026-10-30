"""Unit tests for rr.core.smokestats (pure logic, no engine)."""
import math
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rr.core.smokestats import (  # noqa: E402
    FPS_CROSSCHECK_SEMANTICS,
    FPS_CROSSCHECK_SOURCE,
    build_smoke_report,
    summarize_fps_crosscheck,
)


class CrosscheckTests(unittest.TestCase):
    def test_empty_samples_report_none(self):
        cc = summarize_fps_crosscheck([], 3.0)
        self.assertEqual(cc["samples"], 0)
        self.assertEqual(cc["post_warmup_samples"], 0)
        self.assertIsNone(cc["min_fps"])
        self.assertIsNone(cc["median_fps"])
        self.assertIsNone(cc["mean_post_warmup_fps"])
        self.assertIsNone(cc["max_fps"])
        self.assertEqual(cc["source"], FPS_CROSSCHECK_SOURCE)
        self.assertEqual(cc["semantics"], FPS_CROSSCHECK_SEMANTICS)

    def test_outlier_stays_visible_and_median_is_robust(self):
        # Reproduces the observed case: one ~1e6 sample among 60 steady ones.
        samples = [(float(i), 1_000_000.0 if i == 7 else 59.0) for i in range(1, 61)]
        cc = summarize_fps_crosscheck(samples, warmup_s=3.0)
        self.assertEqual(cc["samples"], 60)
        self.assertEqual(cc["max_fps"], 1_000_000.0)
        self.assertEqual(cc["median_fps"], 59.0)
        self.assertGreater(cc["mean_post_warmup_fps"], 59.0)  # honest, outlier included
        self.assertLess(cc["mean_post_warmup_fps"], 1_000_000.0)

    def test_post_warmup_mean_excludes_pre_warmup_samples(self):
        samples = [(0.5, 15.0), (1.5, 15.0), (3.0, 60.0), (4.0, 60.0)]
        cc = summarize_fps_crosscheck(samples, warmup_s=3.0)
        self.assertEqual(cc["post_warmup_samples"], 2)
        self.assertEqual(cc["mean_post_warmup_fps"], 60.0)
        self.assertEqual(cc["min_fps"], 15.0)  # min is over all samples, post-warmup or not

    def test_boundary_sample_is_post_warmup(self):
        samples = [(2.99, 10.0), (3.0, 50.0)]
        cc = summarize_fps_crosscheck(samples, warmup_s=3.0)
        self.assertEqual(cc["post_warmup_samples"], 1)
        self.assertEqual(cc["mean_post_warmup_fps"], 50.0)

    def test_no_post_warmup_samples_yields_none(self):
        samples = [(1.0, 30.0), (2.0, 40.0)]
        cc = summarize_fps_crosscheck(samples, warmup_s=5.0)
        self.assertIsNone(cc["mean_post_warmup_fps"])
        self.assertEqual(cc["post_warmup_samples"], 0)

    def test_junk_values_are_skipped_like_the_bench_probe(self):
        samples = [(1.0, None), (2.0, 0.0), (3.0, -5.0), (4.0, math.nan),
                   (5.0, math.inf), (6.0, True), (7.0, "60"), (8.0, 62.0)]
        cc = summarize_fps_crosscheck(samples, warmup_s=3.0)
        self.assertEqual(cc["samples"], 1)
        self.assertEqual(cc["median_fps"], 62.0)
        self.assertEqual(cc["max_fps"], 62.0)

    def test_invalid_sample_times_raise(self):
        with self.assertRaises(ValueError):
            summarize_fps_crosscheck([(-1.0, 60.0)], 0.0)
        with self.assertRaises(ValueError):
            summarize_fps_crosscheck([(math.nan, 60.0)], 0.0)
        bad_samples: list[Any] = [math.nan]  # deliberately not a (t, value) pair
        with self.assertRaises(ValueError):
            summarize_fps_crosscheck(bad_samples, 0.0)

    def test_warmup_validation(self):
        bad_warmups: list[Any] = [-1.0, math.nan, math.inf, "3", None, True]
        for bad in bad_warmups:
            with self.assertRaises(ValueError, msg=f"warmup={bad!r}"):
                summarize_fps_crosscheck([], bad)

    def test_median_matches_benchstats_linear_rule(self):
        # Even count: mean of the two middle values (linear interpolation at p=0.5).
        samples = [(float(i), v) for i, v in enumerate([10.0, 20.0, 30.0, 40.0], start=1)]
        cc = summarize_fps_crosscheck(samples, 0.0)
        self.assertEqual(cc["median_fps"], 25.0)


class ReportGateTests(unittest.TestCase):
    def _stats(self, fps=60.0):
        return {
            "fps_avg": fps,
            "fps_min": fps - 5.0,
            "p1_low_fps": fps - 10.0,
            "frame_time_ms": {"p50": 16.6, "p95": 20.0, "p99": 25.0, "max": 33.0},
            "stutter_count": 1,
            "frames_measured": 900,
            "measured_s": 15.0,
        }

    def _empty_stats(self):
        return {
            "fps_avg": None,
            "fps_min": None,
            "p1_low_fps": None,
            "frame_time_ms": {"p50": None, "p95": None, "p99": None, "max": None},
            "stutter_count": 0,
            "frames_measured": 0,
            "measured_s": None,
        }

    def test_moving_scene_with_movement_expected_passes(self):
        report = build_smoke_report(
            seconds=20.0, warmup_s=3.0, frame_time_stats=self._stats(),
            fps_crosscheck={"samples": 17}, distance_moved_m=12.34, expect_movement=True)
        self.assertTrue(report["moved_ok"])
        self.assertTrue(report["ok"])
        self.assertEqual(report["distance_moved_m"], 12.34)
        self.assertEqual(report["warmup_s"], 3.0)

    def test_static_scene_fails_when_movement_is_expected(self):
        report = build_smoke_report(
            seconds=20.0, warmup_s=3.0, frame_time_stats=self._stats(),
            fps_crosscheck={"samples": 17}, distance_moved_m=0.5, expect_movement=True)
        self.assertFalse(report["moved_ok"])
        self.assertFalse(report["ok"])

    def test_static_scene_passes_when_movement_not_expected(self):
        report = build_smoke_report(
            seconds=20.0, warmup_s=3.0, frame_time_stats=self._stats(),
            fps_crosscheck={"samples": 17}, distance_moved_m=0.0, expect_movement=False)
        self.assertIsNone(report["moved_ok"])
        self.assertTrue(report["ok"])

    def test_no_measured_frames_fails_performance_gate(self):
        report = build_smoke_report(
            seconds=2.0, warmup_s=3.0, frame_time_stats=self._empty_stats(),
            fps_crosscheck={"samples": 0}, distance_moved_m=50.0, expect_movement=False)
        self.assertFalse(report["ok"])

    def test_report_shape_contains_benchstats_fields_and_no_p5(self):
        report = build_smoke_report(
            seconds=20.04, warmup_s=3.0, frame_time_stats=self._stats(),
            fps_crosscheck={"samples": 17}, distance_moved_m=1.5, expect_movement=True)
        self.assertEqual(report["seconds"], 20.0)
        for key in ("fps_avg", "fps_min", "p1_low_fps", "frame_time_ms",
                    "stutter_count", "frames_measured", "measured_s", "fps_crosscheck"):
            self.assertIn(key, report)
        self.assertNotIn("fps_p5", report)  # superseded by frame_time_ms percentiles

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            build_smoke_report(seconds=-1.0, warmup_s=3.0, frame_time_stats=self._stats(),
                               fps_crosscheck={}, distance_moved_m=0.0, expect_movement=True)
        with self.assertRaises(ValueError):
            build_smoke_report(seconds=20.0, warmup_s=3.0, frame_time_stats=self._stats(),
                               fps_crosscheck={}, distance_moved_m=-1.0, expect_movement=True)
        with self.assertRaises(ValueError):
            build_smoke_report(seconds=20.0, warmup_s=-0.5, frame_time_stats=self._stats(),
                               fps_crosscheck={}, distance_moved_m=0.0, expect_movement=True)
        not_a_bool: Any = 1  # deliberately the wrong type for expect_movement
        with self.assertRaises(ValueError):
            build_smoke_report(seconds=20.0, warmup_s=3.0, frame_time_stats=self._stats(),
                               fps_crosscheck={}, distance_moved_m=0.0, expect_movement=not_a_bool)


if __name__ == "__main__":
    unittest.main()

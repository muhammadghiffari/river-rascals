"""Unit tests for the pure-Python benchmark statistics."""

import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rr.core.benchstats import summarize  # noqa: E402


class BenchStatsCoreTests(unittest.TestCase):
    def test_basic_statistics(self):
        result = summarize([0.01, 0.02, 0.01, 0.04], warmup_s=0)

        self.assertAlmostEqual(result["fps_avg"], 50.0)
        self.assertAlmostEqual(result["fps_min"], 25.0)
        self.assertAlmostEqual(result["frame_time_ms"]["max"], 40.0)
        self.assertAlmostEqual(result["frame_time_ms"]["p50"], 15.0)
        self.assertEqual(result["frames_measured"], 4)
        self.assertAlmostEqual(result["measured_s"], 0.08)

    def test_warmup_frames_are_excluded(self):
        result = summarize([0.1, 0.1, 0.01, 0.01], warmup_s=0.2)

        self.assertAlmostEqual(result["fps_avg"], 100.0)
        self.assertAlmostEqual(result["fps_min"], 100.0)
        self.assertEqual(result["frames_measured"], 2)

    def test_empty_input(self):
        result = summarize([], warmup_s=0)

        self.assertIsNone(result["fps_avg"])
        self.assertIsNone(result["fps_min"])
        self.assertIsNone(result["p1_low_fps"])
        self.assertIsNone(result["measured_s"])
        self.assertEqual(result["stutter_count"], 0)
        self.assertEqual(result["frames_measured"], 0)
        for key in ("p50", "p95", "p99", "max"):
            self.assertIsNone(result["frame_time_ms"][key])

    def test_one_frame(self):
        result = summarize([0.02], warmup_s=0)

        self.assertAlmostEqual(result["fps_avg"], 50.0)
        self.assertAlmostEqual(result["fps_min"], 50.0)
        self.assertAlmostEqual(result["p1_low_fps"], 50.0)
        self.assertAlmostEqual(result["frame_time_ms"]["p50"], 20.0)
        self.assertAlmostEqual(result["frame_time_ms"]["p99"], 20.0)
        self.assertEqual(result["stutter_count"], 0)

    def test_warmup_longer_than_run(self):
        result = summarize([0.01, 0.02], warmup_s=10)

        self.assertIsNone(result["fps_avg"])
        self.assertIsNone(result["fps_min"])
        self.assertIsNone(result["p1_low_fps"])
        self.assertEqual(result["stutter_count"], 0)
        self.assertEqual(result["frames_measured"], 0)


class BenchStatsWarmupBoundaryTests(unittest.TestCase):
    """The frame that crosses the warmup boundary is consumed by warmup."""

    def test_zero_warmup_keeps_every_frame(self):
        result = summarize([0.01] * 5, warmup_s=0)
        self.assertEqual(result["frames_measured"], 5)

    def test_warmup_equal_to_cumulative_sum_starts_at_next_frame(self):
        # 0.01 + 0.02 == 0.03 exactly => both leading frames are warmup.
        result = summarize([0.01, 0.02, 0.05], warmup_s=0.03)

        self.assertEqual(result["frames_measured"], 1)
        self.assertAlmostEqual(result["fps_avg"], 20.0)
        self.assertAlmostEqual(result["frame_time_ms"]["max"], 50.0)

    def test_warmup_just_below_cumulative_sum_still_consumes_boundary_frame(self):
        # 0.029 < 0.03, so the 0.02 frame is still consumed: measurement starts at 0.05.
        result = summarize([0.01, 0.02, 0.05], warmup_s=0.029)

        self.assertEqual(result["frames_measured"], 1)
        self.assertAlmostEqual(result["frame_time_ms"]["p50"], 50.0)

    def test_warmup_exactly_consuming_every_frame_yields_empty_result(self):
        result = summarize([0.01, 0.02, 0.03], warmup_s=0.06)

        self.assertEqual(result["frames_measured"], 0)
        self.assertIsNone(result["fps_avg"])
        self.assertIsNone(result["frame_time_ms"]["p50"])

    def test_warmup_is_time_based_not_frame_count_based(self):
        # Same frame count, different durations: only the cumulative rule gives these answers.
        slow = summarize([0.10, 0.10, 0.01, 0.01], warmup_s=0.05)
        fast = summarize([0.001, 0.001, 0.01, 0.01], warmup_s=0.0015)

        self.assertEqual(slow["frames_measured"], 3)  # one 0.10 s frame exceeds 0.05 s
        self.assertEqual(fast["frames_measured"], 2)  # two 1 ms frames are needed


class BenchStatsPercentileTests(unittest.TestCase):
    def test_one_percent_low_uses_99th_percentile(self):
        result = summarize([0.01, 0.01, 0.01, 0.03], warmup_s=0)

        # Sorted [0.01, 0.01, 0.01, 0.03]: p99 position = 3 * 0.99 = 2.97
        # => 0.01 + (0.03 - 0.01) * 0.97 = 0.0294 s.
        self.assertAlmostEqual(result["frame_time_ms"]["p99"], 29.4)
        self.assertAlmostEqual(result["p1_low_fps"], 1 / 0.0294)

    def test_p95_uses_linear_interpolation(self):
        result = summarize([0.01, 0.02, 0.03, 0.04, 0.05], warmup_s=0)

        # p95 position = 4 * 0.95 = 3.8 => 0.04 + (0.05 - 0.04) * 0.8 = 0.048 s.
        self.assertAlmostEqual(result["frame_time_ms"]["p95"], 48.0)

    def test_median_of_even_sample_interpolates(self):
        result = summarize([0.01, 0.03], warmup_s=0)
        self.assertAlmostEqual(result["frame_time_ms"]["p50"], 20.0)

    def test_unsorted_input_is_ordered_before_summarizing(self):
        result = summarize([0.05, 0.01, 0.03, 0.02, 0.04], warmup_s=0)
        self.assertAlmostEqual(result["frame_time_ms"]["p50"], 30.0)
        self.assertAlmostEqual(result["fps_min"], 20.0)


class BenchStatsStutterTests(unittest.TestCase):
    def test_stutter_count_uses_twice_the_median(self):
        result = summarize([0.01, 0.01, 0.01, 0.03], warmup_s=0)
        self.assertEqual(result["stutter_count"], 1)

    def test_frame_exactly_twice_the_median_is_not_a_stutter(self):
        # Median of [0.01, 0.01, 0.02] is 0.01; 0.02 is exactly 2x and must not count.
        result = summarize([0.01, 0.01, 0.02], warmup_s=0)
        self.assertAlmostEqual(result["frame_time_ms"]["p50"], 10.0)
        self.assertEqual(result["stutter_count"], 0)

    def test_frame_just_above_twice_the_median_is_a_stutter(self):
        result = summarize([0.01, 0.01, 0.020001], warmup_s=0)
        self.assertEqual(result["stutter_count"], 1)

    def test_stutter_count_only_covers_measured_frames(self):
        # The 0.5 s warmup frame must not be counted as a stutter.
        result = summarize([0.5, 0.01, 0.01, 0.01], warmup_s=0.5)
        self.assertEqual(result["frames_measured"], 3)
        self.assertEqual(result["stutter_count"], 0)

    def test_all_frames_stutter_when_median_is_tiny(self):
        result = summarize([0.001, 0.004, 0.004], warmup_s=0)
        # Median 0.004; threshold 0.008; nothing exceeds it.
        self.assertEqual(result["stutter_count"], 0)


class BenchStatsInputPolicyTests(unittest.TestCase):
    def test_invalid_frame_times_are_rejected(self):
        for frame_times in ([0], [-0.01], [math.inf], [math.nan], [-math.inf]):
            with self.subTest(frame_times=frame_times):
                with self.assertRaises(ValueError):
                    summarize(frame_times, warmup_s=0)

    def test_non_numeric_frame_times_are_rejected(self):
        for frame_times in (["0.01"], [None], [True]):
            with self.subTest(frame_times=frame_times):
                with self.assertRaises(ValueError):
                    summarize(frame_times, warmup_s=0)

    def test_invalid_warmup_is_rejected(self):
        for warmup in (-1, -0.001, math.inf, math.nan):
            with self.subTest(warmup=warmup):
                with self.assertRaises(ValueError):
                    summarize([0.01], warmup_s=warmup)

    def test_invalid_frame_after_measured_window_is_still_rejected(self):
        # Validation covers the whole input, not only the measured tail.
        with self.assertRaises(ValueError):
            summarize([0.01, 0.01, 0], warmup_s=0.015)

    def test_tuple_input_is_accepted(self):
        result = summarize((0.01, 0.02), warmup_s=0)
        self.assertEqual(result["frames_measured"], 2)


class BenchStatsJsonTests(unittest.TestCase):
    def test_result_is_strict_json_compatible(self):
        for frame_times, warmup in (
            ([], 0),
            ([0.02], 0),
            ([0.01, 0.02, 0.01, 0.04], 0),
            ([0.01, 0.02], 10),
        ):
            with self.subTest(frame_times=frame_times, warmup=warmup):
                payload = json.dumps(summarize(frame_times, warmup), allow_nan=False)
                self.assertIsInstance(payload, str)

    def test_no_nan_or_infinity_in_populated_result(self):
        result = summarize([0.016, 0.017, 0.100, 0.016], warmup_s=0)
        for key in ("fps_avg", "fps_min", "p1_low_fps"):
            self.assertTrue(math.isfinite(result[key]), key)
        for key, value in result["frame_time_ms"].items():
            self.assertTrue(math.isfinite(value), key)

    def test_synthetic_steady_run_is_consistent(self):
        # 600 frames at 60 fps: avg fps ~60, min fps == p1 low == 60.
        result = summarize([1 / 60] * 600, warmup_s=0)

        self.assertAlmostEqual(result["fps_avg"], 60.0, places=6)
        self.assertAlmostEqual(result["fps_min"], 60.0, places=6)
        self.assertAlmostEqual(result["p1_low_fps"], 60.0, places=6)
        self.assertAlmostEqual(result["frame_time_ms"]["p99"], 1000 / 60, places=6)
        self.assertEqual(result["stutter_count"], 0)


if __name__ == "__main__":
    unittest.main()

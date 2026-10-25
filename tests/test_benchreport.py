"""Unit tests for benchmark report assembly and atomic JSON writing."""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

# Stub bge before importing glue module so tests run outside UPBGE
if "bge" not in sys.modules:
    _bge_stub = types.ModuleType("bge")
    _bge_stub.types = types.SimpleNamespace(KX_PythonComponent=object)
    sys.modules["bge"] = _bge_stub

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rr.core.benchreport import (  # noqa: E402
    build_report,
    parse_resolution,
    resolution_label,
    utc_now_iso,
    write_json_atomic,
)
from rr.core.benchstats import summarize  # noqa: E402
from rr.glue.bench import _fps_crosscheck  # noqa: E402


def _stats(**overrides):
    base = summarize([0.016] * 10, warmup_s=0)
    base.update(overrides)
    return base


class ResolutionHelperTests(unittest.TestCase):
    def test_label_round_trip(self):
        self.assertEqual(resolution_label(1280, 720), "1280x720")
        self.assertEqual(resolution_label("1366", 768), "1366x768")

    def test_label_rejects_non_positive_and_garbage(self):
        for width, height in ((0, 720), (1280, 0), (-1, 1), (None, 720), ("x", 720)):
            with self.subTest(width=width, height=height):
                self.assertIsNone(resolution_label(width, height))

    def test_parse_accepts_x_and_star(self):
        self.assertEqual(parse_resolution("1280x720"), (1280, 720))
        self.assertEqual(parse_resolution("1366X768"), (1366, 768))
        self.assertEqual(parse_resolution(" 1920 * 1080 "), (1920, 1080))

    def test_parse_rejects_malformed(self):
        for label in (None, "", "1280", "1280x", "axb", "0x720", "1280x0"):
            with self.subTest(label=label):
                self.assertIsNone(parse_resolution(label))


class BuildReportTests(unittest.TestCase):
    def test_ok_only_when_frames_were_measured(self):
        report = build_report(
            stats=_stats(),
            scene_label="empty", preset="low",
            requested_resolution="1280x720", actual_resolution="1280x699",
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine="UPBGE 5.0.1", gpu_vendor="Intel",
        )
        self.assertTrue(report["ok"])

        empty = build_report(
            stats=summarize([], 0),
            scene_label="empty", preset=None,
            requested_resolution=None, actual_resolution=None,
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine=None, gpu_vendor=None,
        )
        self.assertFalse(empty["ok"])

    def test_requested_resolution_never_faked_as_actual(self):
        report = build_report(
            stats=_stats(),
            scene_label="empty", preset=None,
            requested_resolution="1280x720", actual_resolution="1280x699",
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine=None, gpu_vendor=None,
        )
        self.assertEqual(report["requested_resolution"], "1280x720")
        self.assertEqual(report["actual_resolution"], "1280x699")
        self.assertFalse(report["resolution_verified"])
        self.assertTrue(any("NOT verified" in note for note in report["notes"]))

    def test_matching_resolution_is_verified(self):
        report = build_report(
            stats=_stats(),
            scene_label="empty", preset=None,
            requested_resolution="1366x768", actual_resolution="1366x768",
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine=None, gpu_vendor=None,
        )
        self.assertTrue(report["resolution_verified"])

    def test_unknown_resolution_is_explicit(self):
        report = build_report(
            stats=_stats(),
            scene_label="empty", preset=None,
            requested_resolution="1280x720", actual_resolution=None,
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine=None, gpu_vendor=None,
        )
        self.assertIsNone(report["actual_resolution"])
        self.assertFalse(report["resolution_verified"])
        self.assertTrue(any("not observable" in note for note in report["notes"]))

    def test_missing_renderer_is_flagged_not_invented(self):
        report = build_report(
            stats=_stats(),
            scene_label="empty", preset=None,
            requested_resolution=None, actual_resolution=None,
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine=None, gpu_vendor="Intel",
        )
        self.assertIsNone(report["gpu_renderer"])
        self.assertTrue(any("GL_RENDERER" in note for note in report["notes"]))

    def test_report_is_strict_json(self):
        report = build_report(
            stats=_stats(),
            scene_label="bench_100k", preset="low",
            requested_resolution="1280x720", actual_resolution="1280x699",
            duration_s=60.0, warmup_s=3.0, platform="linux",
            engine="UPBGE 5.0.1", gpu_vendor="Intel",
        )
        json.dumps(report, allow_nan=False)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["stats"]["frames_measured"], 10)

    def test_utc_now_iso_shape(self):
        stamp = utc_now_iso()
        self.assertTrue(stamp.endswith("Z"))
        self.assertIn("T", stamp)


class AtomicWriteTests(unittest.TestCase):
    def test_writes_valid_json_and_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "deep" / "result.json"
            written = write_json_atomic(target, {"a": 1})

            self.assertEqual(written, target)
            self.assertEqual(json.loads(target.read_text()), {"a": 1})

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "result.json"
            target.write_text('{"old": true}')
            write_json_atomic(target, {"new": True})
            self.assertEqual(json.loads(target.read_text()), {"new": True})

    def test_leaves_no_temporary_files_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "result.json"
            write_json_atomic(target, {"a": 1})
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["result.json"])

    def test_failed_serialization_keeps_destination_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "result.json"
            target.write_text('{"kept": true}')
            with self.assertRaises(ValueError):
                write_json_atomic(target, {"bad": float("nan")})
            self.assertEqual(json.loads(target.read_text()), {"kept": True})
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["result.json"])


class FpsCrosscheckTests(unittest.TestCase):
    def test_basic_crosscheck_min_avg_max(self):
        result = _fps_crosscheck([58.0, 60.0, 62.0])
        self.assertEqual(result["samples"], 3)
        self.assertAlmostEqual(result["min_fps"], 58.0)
        self.assertAlmostEqual(result["avg_fps"], 60.0)
        self.assertAlmostEqual(result["max_fps"], 62.0)
        self.assertIn("getAverageFrameRate", result["source"])
        self.assertIn("cannot produce a 1% low", result["semantics"])

    def test_empty_and_none_samples(self):
        for empty_input in ([], (), [None], [None, None]):
            with self.subTest(samples=empty_input):
                result = _fps_crosscheck(empty_input)
                self.assertEqual(result["samples"], 0)
                self.assertIsNone(result["min_fps"])
                self.assertIsNone(result["avg_fps"])
                self.assertIsNone(result["max_fps"])

    def test_none_values_are_filtered(self):
        result = _fps_crosscheck([None, 30.0, None, 50.0])
        self.assertEqual(result["samples"], 2)
        self.assertAlmostEqual(result["min_fps"], 30.0)
        self.assertAlmostEqual(result["avg_fps"], 40.0)
        self.assertAlmostEqual(result["max_fps"], 50.0)

    def test_single_sample(self):
        result = _fps_crosscheck([45.5])
        self.assertEqual(result["samples"], 1)
        self.assertAlmostEqual(result["min_fps"], 45.5)
        self.assertAlmostEqual(result["avg_fps"], 45.5)
        self.assertAlmostEqual(result["max_fps"], 45.5)

    def test_outlier_one_million_fps_isolated_in_max(self):
        # Observed UPBGE 0.50 Linux glitch where getAverageFrameRate() spikes to ~1e6 fps.
        # max_fps surfaces the outlier while avg_fps reflects the distortion.
        samples = [60.0, 60.0, 1_000_000.0, 60.0]
        result = _fps_crosscheck(samples)
        self.assertEqual(result["samples"], 4)
        self.assertAlmostEqual(result["min_fps"], 60.0)
        self.assertAlmostEqual(result["max_fps"], 1_000_000.0)
        self.assertAlmostEqual(result["avg_fps"], (180.0 + 1_000_000.0) / 4)

    def test_invalid_sample_types_raise_value_error(self):
        with self.assertRaises(ValueError):
            _fps_crosscheck(["not_a_number"])

    def test_build_report_with_crosscheck(self):
        crosscheck = _fps_crosscheck([60.0, 60.0])
        report = build_report(
            stats=_stats(),
            scene_label="empty",
            preset="low",
            requested_resolution="1280x720",
            actual_resolution="1280x720",
            duration_s=60.0,
            warmup_s=3.0,
            platform="linux",
            engine="UPBGE 5.0.1",
            gpu_vendor="Intel",
            fps_crosscheck=crosscheck,
        )
        self.assertEqual(report["fps_crosscheck"]["samples"], 2)
        self.assertFalse(any("fps_crosscheck is empty" in note for note in report["notes"]))

    def test_build_report_empty_crosscheck_adds_note(self):
        empty_crosscheck = _fps_crosscheck([])
        report = build_report(
            stats=_stats(),
            scene_label="empty",
            preset="low",
            requested_resolution="1280x720",
            actual_resolution="1280x720",
            duration_s=60.0,
            warmup_s=3.0,
            platform="linux",
            engine="UPBGE 5.0.1",
            gpu_vendor="Intel",
            fps_crosscheck=empty_crosscheck,
        )
        self.assertEqual(report["fps_crosscheck"]["samples"], 0)
        self.assertTrue(any("fps_crosscheck is empty" in note for note in report["notes"]))


if __name__ == "__main__":
    unittest.main()

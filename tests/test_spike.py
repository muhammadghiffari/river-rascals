"""Unit tests for rr.core.spike (S-01 result grading)."""
import unittest
from unittest.mock import MagicMock, patch

from rr.core.spike import (
    CHECKS,
    FAIL,
    PASS,
    compute_fps_stats,
    matrix_header,
    matrix_row,
    normalize,
    summarize,
    vector_magnitude,
)


class NormalizeTests(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(normalize(" PASS "), "pass")
        self.assertEqual(normalize("fail"), "fail")
        self.assertEqual(normalize("skip"), "skip")
        self.assertEqual(normalize("maybe"), "")
        self.assertEqual(normalize(None), "")


class SummarizeTests(unittest.TestCase):
    def test_all_pass(self):
        res = summarize({name: "pass" for name in CHECKS})
        self.assertTrue(res["ok"])
        self.assertEqual(res["failed"], [])
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["passed"], list(CHECKS))

    def test_one_failure_blocks(self):
        checks = {name: "pass" for name in CHECKS}
        checks["aud_3d"] = "fail"
        res = summarize(checks)
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed"], ["aud_3d"])

    def test_unsupported_feature_is_skip_not_failure(self):
        checks = {name: "pass" for name in CHECKS}
        checks["overlay"] = "skip"
        res = summarize(checks)
        self.assertTrue(res["ok"])
        self.assertEqual(res["skipped"], ["overlay"])

    def test_unknown_status_blocks(self):
        checks = {name: "pass" for name in CHECKS}
        checks["aud_play"] = "error"
        res = summarize(checks)
        self.assertFalse(res["ok"])
        self.assertEqual(res["missing"], ["aud_play"])
        self.assertEqual(res["passed"].count("aud_play"), 0)

    def test_missing_check_blocks(self):
        checks = {name: "pass" for name in CHECKS if name != "fps"}
        res = summarize(checks)
        self.assertFalse(res["ok"])
        self.assertEqual(res["missing"], ["fps"])


class MatrixRowTests(unittest.TestCase):
    def test_row_cell_count_matches_header(self):
        row = matrix_row("0.50", "P1", {name: "pass" for name in CHECKS}, 61.4)
        self.assertEqual(row.count("|"), matrix_header().count("|"))
        self.assertIn("| 0.50 | P1 |", row)
        self.assertTrue(row.endswith("| 61.4 |"))

    def test_row_marks_fail_skip_and_unknown(self):
        checks = {name: "pass" for name in CHECKS}
        checks["filter2d"] = "fail"
        checks["overlay"] = "skip"
        del checks["aud_3d"]
        cells = matrix_row("0.44", "P3", checks, 24.0).split("|")
        cells = [c.strip() for c in cells]
        # cells[0] and cells[-1] are empty (leading/trailing pipe)
        body = cells[1:-1]
        self.assertEqual(body[0], "0.44")
        self.assertEqual(body[1], "P3")
        self.assertEqual(body[2 + CHECKS.index("filter2d")], "FAIL")
        self.assertEqual(body[2 + CHECKS.index("overlay")], "SKIP")
        self.assertEqual(body[2 + CHECKS.index("aud_3d")], "-")
        self.assertEqual(body[-1], "24.0")


class VectorMagnitudeTests(unittest.TestCase):
    def test_mock_vector_dimension_vs_magnitude(self):
        class MockMathutilsVector:
            """Simulates mathutils.Vector: len() is dimension (3), .length is magnitude."""
            def __init__(self, x: float, y: float, z: float) -> None:
                self._data = (x, y, z)
                self.length = (x * x + y * y + z * z) ** 0.5

            def __len__(self) -> int:
                return 3

            def __getitem__(self, idx: int) -> float:
                return self._data[idx]

        # Stationary object (e.g. dynamic box at rest after falling)
        stationary = MockMathutilsVector(0.0, 0.0, 0.0)
        self.assertEqual(len(stationary), 3, "mathutils.Vector dimension is always 3")
        self.assertEqual(vector_magnitude(stationary), 0.0, "magnitude of stationary vector is 0.0")
        self.assertLess(vector_magnitude(stationary), 0.5, "speed < 0.5 passes with magnitude")
        self.assertFalse(len(stationary) < 0.5, "len(vel) would incorrectly fail speed < 0.5 check")

        # Moving object (speed 0.5)
        moving = MockMathutilsVector(0.3, 0.4, 0.0)
        self.assertEqual(len(moving), 3)
        self.assertAlmostEqual(vector_magnitude(moving), 0.5)

    def test_sequence_magnitude(self):
        self.assertEqual(vector_magnitude((0.0, 0.0, 0.0)), 0.0)
        self.assertAlmostEqual(vector_magnitude([1.0, 2.0, 2.0]), 3.0)
        self.assertEqual(vector_magnitude(None), 0.0)

    def test_invalid_vector(self):
        with self.assertRaises(ValueError):
            vector_magnitude("not_a_vector")
        with self.assertRaises(ValueError):
            vector_magnitude((1.0, 2.0))


class ComputeFpsStatsTests(unittest.TestCase):
    def test_warmup_and_invalid_filtered(self):
        samples = [
            (0.0, 200050.1),  # warmup: discarded by t < 1.0
            (0.5, 60.0),      # warmup: discarded by t < 1.0
            (1.0, float("nan")),  # invalid: non-finite
            (1.5, -5.0),      # invalid: <= 0.0
            (2.0, 0.0),       # invalid: <= 0.0
            (2.5, 60.0),      # valid
            (3.0, 58.0),      # valid
            (3.5, 62.0),      # valid
        ]
        res = compute_fps_stats(samples, warmup_seconds=1.0, min_fps=30.0)
        self.assertEqual(res["status"], PASS)
        self.assertEqual(res["raw_n"], 8)
        self.assertEqual(res["n"], 3)
        self.assertEqual(res["dropped_n"], 5)
        self.assertEqual(res["raw_max"], 200050.1)
        self.assertEqual(res["min"], 58.0)
        self.assertEqual(res["median"], 60.0)
        self.assertEqual(res["avg"], 60.0)

    def test_all_invalid_fails(self):
        samples = [
            (0.0, 120.0),
            (0.5, 120.0),
            (1.0, 0.0),
            (1.5, float("inf")),
        ]
        res = compute_fps_stats(samples, warmup_seconds=1.0, min_fps=30.0)
        self.assertEqual(res["status"], FAIL)
        self.assertEqual(res["n"], 0)
        self.assertEqual(res["raw_n"], 4)
        self.assertEqual(res["dropped_n"], 4)
        self.assertEqual(res["avg"], 0.0)

    def test_empty_samples_fails(self):
        res = compute_fps_stats([])
        self.assertEqual(res["status"], FAIL)
        self.assertEqual(res["n"], 0)
        self.assertEqual(res["raw_n"], 0)
        self.assertEqual(res["dropped_n"], 0)

    def test_below_threshold_fails(self):
        samples = [(1.0, 25.0), (1.5, 27.0)]
        res = compute_fps_stats(samples, warmup_seconds=1.0, min_fps=30.0)
        self.assertEqual(res["status"], FAIL)
        self.assertEqual(res["avg"], 26.0)

    def test_p2_historical_outlier_artifact_handled(self):
        # 1 initial 200050.1 artifact at t=0, followed by 24 samples of 60.0 fps
        samples = [(0.0, 200050.1)] + [(1.0 + i * 0.5, 60.0) for i in range(24)]
        res = compute_fps_stats(samples)
        self.assertEqual(res["status"], PASS)
        self.assertEqual(res["raw_n"], 25)
        self.assertEqual(res["n"], 24)
        self.assertEqual(res["dropped_n"], 1)
        self.assertEqual(res["raw_max"], 200050.1)
        self.assertEqual(res["avg"], 60.0)
        self.assertEqual(res["median"], 60.0)

    def test_median_determines_pass_when_average_below_threshold(self):
        # 4 samples of 35.0 and 1 sample of 5.0:
        # avg = (35*4 + 5)/5 = 145/5 = 29.0 (< 30.0)
        # median = 35.0 (>= 30.0)
        # Must PASS because criterion is median >= min_fps.
        samples = [(1.0, 35.0), (1.5, 35.0), (2.0, 35.0), (2.5, 35.0), (3.0, 5.0)]
        res = compute_fps_stats(samples, warmup_seconds=1.0, min_fps=30.0)
        self.assertEqual(res["status"], PASS, "Must PASS based on median >= 30, even if avg < 30")
        self.assertEqual(res["median"], 35.0)
        self.assertEqual(res["avg"], 29.0)
        self.assertEqual(res["min"], 5.0)
        self.assertEqual(res["raw_max"], 35.0)
        self.assertEqual(res["raw_n"], 5)
        self.assertEqual(res["n"], 5)
        self.assertEqual(res["dropped_n"], 0)

    def test_median_determines_fail_when_average_above_threshold(self):
        # 4 samples of 20.0 and 1 outlier sample of 90.0:
        # avg = (20*4 + 90)/5 = 170/5 = 34.0 (>= 30.0)
        # median = 20.0 (< 30.0)
        # Must FAIL because criterion is median >= min_fps.
        samples = [(1.0, 20.0), (1.5, 20.0), (2.0, 20.0), (2.5, 20.0), (3.0, 90.0)]
        res = compute_fps_stats(samples, warmup_seconds=1.0, min_fps=30.0)
        self.assertEqual(res["status"], FAIL, "Must FAIL based on median < 30, even if avg >= 30")
        self.assertEqual(res["median"], 20.0)
        self.assertEqual(res["avg"], 34.0)
        self.assertEqual(res["min"], 20.0)
        self.assertEqual(res["raw_max"], 90.0)
        self.assertEqual(res["raw_n"], 5)
        self.assertEqual(res["n"], 5)
        self.assertEqual(res["dropped_n"], 0)


class ProbePhysicsSpeedCheckTests(unittest.TestCase):
    def test_probe_physics_uses_magnitude_and_passes_at_rest(self):
        class MockMathutilsVector:
            def __init__(self, x: float, y: float, z: float) -> None:
                self.x = x
                self.y = y
                self.z = z
                self._data = (x, y, z)
                self.length = (x * x + y * y + z * z) ** 0.5

            def __len__(self) -> int:
                return 3

            def __getitem__(self, idx: int) -> float:
                return self._data[idx]

            def __iter__(self):
                return iter(self._data)

        mock_bge = MagicMock()

        class FakeComponent:
            pass

        mock_bge.types.KX_PythonComponent = FakeComponent

        with patch.dict("sys.modules", {"bge": mock_bge}):
            from rr.glue.spike_probe import SpikeProbe

            probe = SpikeProbe.__new__(SpikeProbe)
            probe.start_z = 3.0
            probe.t0 = 100.0
            probe.update_count = 180
            probe.physics_diagnostics = []
            mock_box = MagicMock()
            mock_box.worldPosition = [0.0, 0.0, 0.5]
            mock_box.worldLinearVelocity = MockMathutilsVector(0.0, 0.0, 0.0)
            probe.box = mock_box
            probe.scene = MagicMock()
            probe.scene.objects = {"SpikeBox": mock_box}
            mock_owner = MagicMock()
            mock_owner.name = "SpikeProbeRoot"
            probe.object = mock_owner

            with patch("time.time", return_value=103.0):
                status, note = probe._probe_physics()
            self.assertEqual(status, "pass")
            self.assertIn("|v|=0.00", note)
            self.assertIn("vx=0.00 vy=0.00 vz=0.00", note)
            self.assertIn("updates=180", note)
            self.assertIn("owner=SpikeProbeRoot", note)
            self.assertIn("match=True", note)
            self.assertEqual(len(probe.physics_diagnostics), 1)
            self.assertEqual(probe.physics_diagnostics[0]["tag"], "check")
            self.assertEqual(probe.physics_diagnostics[0]["update_count"], 180)

    def test_probe_tic_rates_separates_setpoint_and_measured(self):
        mock_bge = MagicMock()

        class FakeComponent:
            pass

        mock_bge.types.KX_PythonComponent = FakeComponent
        mock_bge.logic.getLogicTicRate.return_value = 60.0
        mock_bge.logic.getPhysicsTicRate.return_value = 0.0

        with patch.dict("sys.modules", {"bge": mock_bge}):
            from rr.glue.spike_probe import SpikeProbe

            probe = SpikeProbe.__new__(SpikeProbe)
            probe.want_logic = 60.0
            probe.want_physics = 60.0

            status, note = probe._probe_tic_rates()
            self.assertEqual(status, "fail")
            self.assertEqual(probe.measured_logic, 60.0)
            self.assertEqual(probe.measured_physics, 0.0)
            self.assertIn("measured: logic=60.0 physics=0.0", note)
            self.assertIn("setpoint: logic=60 physics=60", note)
            self.assertIn("physics=0.0 — possible causes", note)

    def test_write_json_partial_and_complete(self):
        import json
        import tempfile

        mock_bge = MagicMock()

        class FakeComponent:
            pass

        mock_bge.types.KX_PythonComponent = FakeComponent

        with patch.dict("sys.modules", {"bge": mock_bge}):
            from rr.glue.spike_probe import SpikeProbe

            probe = SpikeProbe.__new__(SpikeProbe)
            probe.machine = "P1"
            probe.want_logic = 60.0
            probe.want_physics = 60.0
            probe.measured_logic = 60.0
            probe.measured_physics = 0.0
            probe.checks = {"component": "pass"}
            probe.notes = ["test note"]
            probe.physics_diagnostics = [{"tag": "check", "update_count": 10}]
            probe.samples = [(0.0, 200050.0), (1.0, 60.0), (1.5, 60.0)]
            probe._version = lambda: "0.50 (Blender 5.0.1)"
            probe._window = lambda: [1920, 1080]

            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp_path = f.name

            with patch.dict("os.environ", {"RR_SPIKE_OUT": tmp_path}):
                # Write partial
                probe._write_json(status="partial")
                with open(tmp_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertEqual(data["status"], "partial")
                self.assertFalse(data["summary"]["ok"])
                self.assertEqual(data["tic"]["setpoint"], {"logic": 60.0, "physics": 60.0})
                self.assertEqual(data["tic"]["measured"], {"logic": 60.0, "physics": 0.0})
                self.assertEqual(data["fps"]["avg"], 60.0)
                self.assertEqual(data["fps"]["raw_max"], 200050.0)
                self.assertEqual(data["fps"]["raw_n"], 3)
                self.assertEqual(data["fps"]["n"], 2)
                self.assertEqual(len(data["physics_diagnostics"]), 1)

                # Write complete
                probe._write_json(status="complete")
                with open(tmp_path, encoding="utf-8") as fh:
                    data_comp = json.load(fh)
                self.assertEqual(data_comp["status"], "complete")

    def test_update_first_call_and_checkpoints_write_partial(self):
        mock_bge = MagicMock()

        class FakeComponent:
            pass

        mock_bge.types.KX_PythonComponent = FakeComponent

        with patch.dict("sys.modules", {"bge": mock_bge}):
            from rr.glue.spike_probe import SpikeProbe

            probe = SpikeProbe.__new__(SpikeProbe)
            probe.done = False
            probe.update_count = 0
            probe.t0 = 100.0
            probe.next_physics_after_check = False
            probe.next_sample = 0.5
            probe.checks = {}
            probe.duration = 12.0
            probe._sample_fps = MagicMock()
            probe._record_physics_diag = MagicMock()
            probe._write_json = MagicMock()
            probe._check = MagicMock()
            probe._finish = MagicMock()

            # First update call at t=100.1 (elapsed=0.1s)
            with patch("time.time", return_value=100.1):
                probe.update()

            self.assertEqual(probe.update_count, 1)
            probe._write_json.assert_called_with(status="partial", log=True)


if __name__ == "__main__":
    unittest.main()

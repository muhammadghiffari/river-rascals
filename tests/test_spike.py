"""Unit tests for rr.core.spike (S-01 result grading)."""
import unittest
from unittest.mock import MagicMock, patch

from rr.core.spike import (
    CHECKS,
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


class ProbePhysicsSpeedCheckTests(unittest.TestCase):
    def test_probe_physics_uses_magnitude_and_passes_at_rest(self):
        class MockMathutilsVector:
            def __init__(self, x: float, y: float, z: float) -> None:
                self._data = (x, y, z)
                self.length = (x * x + y * y + z * z) ** 0.5

            def __len__(self) -> int:
                return 3

            def __getitem__(self, idx: int) -> float:
                return self._data[idx]

        mock_bge = MagicMock()

        class FakeComponent:
            pass

        mock_bge.types.KX_PythonComponent = FakeComponent

        with patch.dict("sys.modules", {"bge": mock_bge}):
            from rr.glue.spike_probe import SpikeProbe

            probe = SpikeProbe.__new__(SpikeProbe)
            probe.start_z = 3.0
            mock_box = MagicMock()
            mock_box.worldPosition.z = 0.5
            mock_box.worldLinearVelocity = MockMathutilsVector(0.0, 0.0, 0.0)
            probe.box = mock_box

            status, note = probe._probe_physics()
            self.assertEqual(status, "pass")
            self.assertIn("|v|=0.00", note)
            self.assertIn("vx=0.00 vy=0.00 vz=0.00", note)


if __name__ == "__main__":
    unittest.main()

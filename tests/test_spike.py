"""Unit tests for rr.core.spike (S-01 result grading)."""
import unittest

from rr.core.spike import CHECKS, matrix_header, matrix_row, normalize, summarize


class NormalizeTests(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(normalize(" PASS "), "pass")
        self.assertEqual(normalize("fail"), "fail")
        self.assertEqual(normalize("skip"), "skip")
        self.assertEqual(normalize("maybe"), "skip")
        self.assertEqual(normalize(None), "skip")


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


if __name__ == "__main__":
    unittest.main()

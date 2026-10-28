"""The asset gate must require evidence that Blender ran the validator."""
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "asset_gate", Path(__file__).resolve().parents[1] / "tools" / "validate_assets.py"
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class AssetGateTests(unittest.TestCase):
    def run_gate(self, stdout: str, returncode: int = 0) -> int:
        result = subprocess.CompletedProcess([], returncode, stdout, "")
        with (
            patch.object(gate, "find_exe", return_value="blender"),
            patch.object(gate.subprocess, "run", return_value=result),
            patch.object(gate.Path, "is_file", return_value=True),
            patch("sys.argv", ["validate_assets", "fixture.blend"]),
        ):
            return gate.main()

    def test_zero_exit_without_validator_output_fails(self):
        self.assertEqual(self.run_gate("Blender quit\n"), 1)

    def test_incomplete_validator_output_fails(self):
        self.assertEqual(self.run_gate("[validate] RF_Raft tris 12/8000\n"), 1)

    def test_completed_clean_validation_passes(self):
        self.assertEqual(self.run_gate("[validate] 0 problem(s)\n"), 0)

    def test_nonzero_exit_and_reported_failure_fail(self):
        self.assertEqual(self.run_gate("[validate] 0 problem(s)\n", 1), 1)
        self.assertEqual(self.run_gate("[validate] FAIL bad name\n[validate] 1 problem(s)\n"), 1)

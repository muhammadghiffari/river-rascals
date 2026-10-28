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
# validate_assets puts tools/ on sys.path, so the shared helper module is importable.
run_game = importlib.import_module("run_game")


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


class HostPathTests(unittest.TestCase):
    """A Windows blender.exe driven from WSL must receive Windows paths.

    Passing `/mnt/c/...` makes Blender fail to open the file, which the gate then
    correctly reports as a failure, so every asset looks broken.
    """

    def test_windows_exe_on_linux_is_translated(self):
        with (
            patch.object(run_game.platform, "system", return_value="Linux"),
            patch.object(run_game.subprocess, "run") as runner,
        ):
            runner.return_value = subprocess.CompletedProcess([], 0, "C:\\repo\\a.blend\n", "")
            self.assertEqual(gate.host_path("/mnt/c/repo/a.blend", "/mnt/c/b/blender.exe"),
                             "C:\\repo\\a.blend")
            self.assertEqual(runner.call_args[0][0][:2], ["wslpath", "-w"])

    def test_native_exe_is_left_alone(self):
        with patch.object(run_game.platform, "system", return_value="Linux"):
            self.assertEqual(gate.host_path("/repo/a.blend", "/usr/bin/blender"), "/repo/a.blend")

    def test_translation_failure_falls_back_to_the_original(self):
        with (
            patch.object(run_game.platform, "system", return_value="Linux"),
            patch.object(run_game.subprocess, "run") as runner,
        ):
            runner.return_value = subprocess.CompletedProcess([], 1, "", "nope")
            self.assertEqual(gate.host_path("/x/a.blend", "blender.exe"), "/x/a.blend")

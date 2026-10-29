"""Tests for subprocess diagnostics in the prototype build runner."""
import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_prototype_scene  # noqa: E402


class BuildRunnerTests(unittest.TestCase):
    def test_tracebacks_are_preserved(self):
        done = subprocess.CompletedProcess(
            [], 1, "", "Traceback (most recent call last):\nAttributeError: bad\n"
        )
        with patch.object(subprocess, "run", return_value=done), contextlib.redirect_stdout(io.StringIO()):
            _, output = build_prototype_scene.run("geometry", ["blender"], "OK")
        self.assertIn("Traceback (most recent call last)", output)
        self.assertIn("AttributeError: bad", output)

    def test_timeout_identifies_pass(self):
        output = io.StringIO()
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("blender", 30)):
            with contextlib.redirect_stdout(output):
                ok, _ = build_prototype_scene.run("logic windowed", ["blender"], "OK")
        self.assertFalse(ok)
        self.assertIn("logic windowed", output.getvalue())
        self.assertIn("timeout", output.getvalue().lower())

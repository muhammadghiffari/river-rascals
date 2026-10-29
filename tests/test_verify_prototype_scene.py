"""Headless regression checks for scene verification."""
import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class SceneVerifierTests(unittest.TestCase):
    def test_wrong_render_engine_is_reported(self):
        settings = SimpleNamespace(fps=60, physics_gravity=9.81, resolution_x=1920,
                                   resolution_y=1080, physics_engine="BULLET", exit_key="ESC")
        scene = SimpleNamespace(name="test", objects=[], game_settings=settings, camera=object(),
                                render=SimpleNamespace(engine="WRONG"))
        bpy = SimpleNamespace(context=SimpleNamespace(scene=scene), data=SimpleNamespace(filepath="test"))
        script = Path(__file__).resolve().parents[1] / "tools/blender/verify_prototype_scene.py"
        output = io.StringIO()
        with patch.dict(sys.modules, {"bpy": bpy}), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit):
                runpy.run_path(str(script))
        self.assertIn("render engine is WRONG", output.getvalue())

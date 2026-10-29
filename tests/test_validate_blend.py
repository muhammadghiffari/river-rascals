"""Exercise the Blender validator with a minimal fake bpy module."""
import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class ImageValidationTests(unittest.TestCase):
    def test_unloaded_image_fails(self):
        image = SimpleNamespace(name="Missing", size=(0, 0))
        bpy = SimpleNamespace(data=SimpleNamespace(objects=[], images=[image]))
        output = io.StringIO()
        script = Path(__file__).resolve().parents[1] / "tools/blender/validate_blend.py"
        with patch.dict(sys.modules, {"bpy": bpy}), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(script))
        self.assertEqual(result.exception.code, 1)
        self.assertIn("image Missing failed to load", output.getvalue())

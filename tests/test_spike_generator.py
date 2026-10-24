"""Generator construction contracts without Blender; runtime checks remain separate."""
import ast
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools/blender/gen_spike_engine.py"


class SpikeGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bpy = MagicMock()
        spec = importlib.util.spec_from_file_location("spike_generator_test", SCRIPT)
        self.generator = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"bpy": self.bpy, "mathutils": MagicMock()}):
            spec.loader.exec_module(self.generator)

    def test_only_component_save_and_quit_operators_remain(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        operators = {
            ast.unparse(node.func) for node in ast.walk(tree)
            if isinstance(node, ast.Call) and ast.unparse(node.func).startswith("bpy.ops.")
        }
        self.assertEqual(operators, {
            "bpy.ops.logic.python_component_register",
            "bpy.ops.wm.save_as_mainfile", "bpy.ops.wm.quit_blender",
        })

    def test_box_dimensions_are_baked_into_outward_faces(self) -> None:
        self.generator.cube_mesh("Test", (20.0, 12.0, 0.2))
        vertices, edges, faces = self.bpy.data.meshes.new.return_value.from_pydata.call_args.args
        self.assertEqual(edges, [])
        for axis, size in enumerate((20.0, 12.0, 0.2)):
            self.assertAlmostEqual(max(v[axis] for v in vertices) - min(v[axis] for v in vertices), size)
        self.assertEqual(len(faces), 6)
        for face in faces:
            a, b, c = (vertices[i] for i in face[:3])
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            normal = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
            self.assertGreater(sum(normal[i] * a[i] for i in range(3)), 0)

    def test_probe_settings_do_not_inherit_startup_timing_or_gravity(self) -> None:
        scene = SimpleNamespace(
            render=SimpleNamespace(fps=24, fps_base=1.001, resolution_percentage=75),
            game_settings=SimpleNamespace(physics_engine="NONE", physics_gravity=0.0, fps=24),
            unit_settings=SimpleNamespace(scale_length=0.01),
            use_gravity=False, gravity=(0.0, 0.0, 0.0),
        )
        self.generator.prepare_scene(scene)
        self.assertEqual((scene.render.fps, scene.render.fps_base), (60, 1.0))
        self.assertEqual((scene.frame_start, scene.frame_end, scene.frame_current), (1, 120, 1))
        self.assertEqual(scene.game_settings.physics_engine, "BULLET")
        self.assertEqual(scene.game_settings.fps, 60)
        self.assertEqual(scene.game_settings.physics_gravity, 9.81)
        self.assertTrue(scene.use_gravity)
        self.assertEqual(scene.gravity, (0.0, 0.0, -9.81))
        self.assertEqual(scene.unit_settings.scale_length, 1.0)
        self.assertEqual(scene.render.resolution_percentage, 75)

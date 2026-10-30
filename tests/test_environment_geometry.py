"""Environment contracts independent of Blender."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rr.core.environment_geometry import PALETTE, bank, bush, palette_uv, pine, river_strip


class EnvironmentGeometryTests(unittest.TestCase):
    def test_shared_palette_contract(self):
        self.assertEqual(PALETTE, (
            "3FB8AF", "1F6F8B", "F4FBFF", "B07A4A", "E0C48A", "2F7D4F", "6FAF5A", "8B8F99",
            "FF6F59", "FFC93C", "8A5A3C", "C28B5A", "5C4033", "D9B38C", "FFF4DC", "2D2A32",
        ))
        for index in range(16):
            self.assertEqual(palette_uv(index), ((index + .5) / 16, .5))
        self.assertEqual(set(pine().colors), {3, 5, 6})
        self.assertEqual(set(bush().colors), {5, 6})
        self.assertEqual(set(bank().colors), {3, 4, 6})

    def test_pines_budget_base_and_sway(self):
        for variant in range(3):
            for lod in (False, True):
                mesh = pine(variant, lod)
                self.assertLessEqual(mesh.triangles, 200 if lod else 800)
                self.assertEqual(min(v[2] for v in mesh.vertices), 0)
                self.assertEqual(min(mesh.sway), 0)
                self.assertEqual(max(mesh.sway), 1)
                self.assertEqual(mesh, pine(variant, lod))

    def test_bush_variants(self):
        meshes = [bush(i) for i in range(3)]
        self.assertNotEqual(meshes[0].vertices, meshes[1].vertices)
        for mesh in meshes:
            self.assertLessEqual(mesh.triangles, 200)
            self.assertEqual(min(v[2] for v in mesh.vertices), 0)

    def test_bank_seams_and_closed_thickness(self):
        for variant in range(4):
            mesh = bank(variant)
            self.assertLessEqual(mesh.triangles, 1500)
            self.assertGreaterEqual(max(v[2] for v in mesh.vertices), .3)
            self.assertEqual(len(mesh.foam), 9)
            self.assertTrue(all(mesh.vertices[i][2] == .3 for i in mesh.foam))
            edges = {}
            for face in mesh.faces:
                for a, b in zip(face, face[1:] + face[:1], strict=True):
                    edge = tuple(sorted((a, b)))
                    edges[edge] = edges.get(edge, 0) + 1
            self.assertTrue(all(count == 2 for count in edges.values()))
            first = [v for v in mesh.vertices if v[1] == 0]
            last = [(x, 0, z) for x, y, z in mesh.vertices if y == mesh.length]
            self.assertEqual(sorted(first), sorted(last))

    def test_flow_uv_and_centerline(self):
        points = ((0., 0.), (0., 4.), (2., 8.))
        mesh = river_strip(points, 8, 4)
        self.assertEqual(len(mesh.vertices), 15)
        for row, (x, y) in enumerate(points):
            self.assertEqual(mesh.vertices[row * 5 + 2], (x, y, 0))
        self.assertAlmostEqual(mesh.uv[-1][1], 4 + math.sqrt(20))
        self.assertLessEqual(mesh.triangles, 3000)
        self.assertTrue(all(mesh.uv[i * 5][1] < mesh.uv[(i + 1) * 5][1] for i in range(2)))

    def test_invalid_inputs(self):
        for points in (((0, 0),), ((0, 0), (0, 0)), ((0, 0), (math.nan, 2))):
            with self.assertRaises(ValueError):
                river_strip(points)
        with self.assertRaises(ValueError):
            river_strip(((0, 0), (0, 4)), width=-1)
        with self.assertRaises(ValueError):
            pine(3)

    def test_all_faces_non_degenerate_and_palette(self):
        meshes = [pine(i) for i in range(3)] + [bush(i) for i in range(3)]
        meshes += [bank(i) for i in range(4)]
        for mesh in meshes:
            self.assertEqual(len(mesh.faces), len(mesh.colors))
            for face in mesh.faces:
                self.assertEqual(len(face), len(set(face)))
                self.assertTrue(all(0 <= i < len(mesh.vertices) for i in face))


if __name__ == "__main__":
    unittest.main()

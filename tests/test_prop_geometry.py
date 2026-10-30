"""Asset contracts independent of Blender."""
import importlib.util
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class PropGeometryTests(unittest.TestCase):
    def geometry(self):
        self.assertIsNotNone(importlib.util.find_spec("rr.core.prop_geometry"),
                             "P0 prop geometry implementation missing")
        from rr.core import prop_geometry
        return prop_geometry

    def test_inventory_budgets_and_valid_surfaces(self):
        g = self.geometry()
        assets = g.build_props()
        self.assertEqual(len(assets), 21)
        self.assertEqual(assets, g.build_props())
        for asset in assets:
            with self.subTest(asset=asset.name):
                self.assertLessEqual(sum(m.tris for m in asset.meshes if not m.collider),
                                     asset.budget)
                visible = [v for m in asset.meshes if not m.collider for v in m.vertices]
                self.assertAlmostEqual(min(v[2] for v in visible), 0)
                for axis in (0, 1):
                    self.assertAlmostEqual(min(v[axis] for v in visible),
                                           -max(v[axis] for v in visible))
                for mesh in asset.meshes:
                    self.assertEqual(len(mesh.faces), len(mesh.colors))
                    for face in mesh.faces:
                        self.assertGreaterEqual(len(face), 3)
                        self.assertEqual(len(set(face)), len(face))
                        for index in face:
                            self.assertLess(index, len(mesh.vertices))
                            self.assertTrue(all(math.isfinite(x) for x in mesh.vertices[index]))
                        a, b, c = (mesh.vertices[i] for i in face[:3])
                        u = [b[i] - a[i] for i in range(3)]
                        v = [c[i] - a[i] for i in range(3)]
                        cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2],
                                 u[0]*v[1]-u[1]*v[0]]
                        self.assertGreater(sum(x*x for x in cross), 1e-14)

    def test_semantic_components_and_clearance(self):
        assets = self.geometry().build_props()
        for a in assets:
            names = " ".join(m.name for m in a.meshes)
            if "Coin" in a.name:
                self.assertIn("Acorn", names)
            if "Buoy" in a.name:
                self.assertIn("Chain", names)
            if "Log" in a.name:
                self.assertIn("Knot", names)
                self.assertEqual(a.collision, "CAPSULE")
            if "Rock" in a.name:
                self.assertEqual(a.collision, "CONVEX_HULL")
                self.assertTrue(any(m.collider for m in a.meshes))
            if "RockLarge" in a.name:
                self.assertTrue(a.name.endswith("_Own"))
                self.assertTrue(any(m.moss for m in a.meshes))
            if "Signpost" in a.name:
                self.assertIn("Arrow", names)
            if "Arch" in a.name or "Gate" in a.name:
                self.assertGreaterEqual(a.clearance, 8)
                self.assertIn("Banner", names)
                self.assertEqual(len(a.bones), 4)
                for m in a.meshes:
                    if "Post" in m.name:
                        self.assertTrue(all(abs(v[0]) >= a.clearance / 2 - 1e-8
                                            for v in m.vertices))
            if "Finish" in a.name:
                self.assertEqual(len(a.sockets), 2)

    def test_rock_colliders_are_closed_convex_hulls(self):
        for asset in self.geometry().build_props():
            if "Rock" not in asset.name:
                continue
            mesh = next(m for m in asset.meshes if m.collider)
            edges = {}
            for face in mesh.faces:
                a, b, c = (mesh.vertices[i] for i in face[:3])
                u = [b[i]-a[i] for i in range(3)]
                v = [c[i]-a[i] for i in range(3)]
                normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2],
                          u[0]*v[1]-u[1]*v[0])
                for vertex in mesh.vertices:
                    self.assertLessEqual(sum(normal[i]*(vertex[i]-a[i]) for i in range(3)),
                                         1e-8, asset.name)
                for i, start in enumerate(face):
                    edge = tuple(sorted((start, face[(i+1) % len(face)])))
                    edges[edge] = edges.get(edge, 0)+1
            self.assertTrue(all(count == 2 for count in edges.values()), asset.name)

    def test_all_component_names_use_asset_bible_characters(self):
        for asset in self.geometry().build_props():
            for mesh in asset.meshes:
                self.assertRegex(mesh.name, r"^PR_[A-Za-z0-9_]+$")
            for name, _ in asset.sockets:
                self.assertRegex(name, r"^Socket_[A-Za-z0-9_]+$")

    def test_shared_palette_contract(self):
        g = self.geometry()
        self.assertEqual(g.PALETTE, ("3FB8AF", "1F6F8B", "F4FBFF", "B07A4A",
                                    "E0C48A", "2F7D4F", "6FAF5A", "8B8F99",
                                    "FF6F59", "FFC93C", "8A5A3C", "C28B5A",
                                    "5C4033", "D9B38C", "FFF4DC", "2D2A32"))
        rim = next(m for m in g.coin().meshes if m.name.endswith("Rim"))
        self.assertEqual(set(rim.colors), {9})


if __name__ == "__main__":
    unittest.main()

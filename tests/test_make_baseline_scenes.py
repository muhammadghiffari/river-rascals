"""Unit tests for the baseline scene generator's pure helpers.

The generator itself must run inside UPBGE (it creates Python Components), but the
arithmetic and naming that decide what gets built are pure and tested here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools", "bench"))

from make_baseline_scenes import (  # noqa: E402
    COMPONENT_MODULE,
    SCENE_FILENAMES,
    SCENES,
    grid_triangles,
    scene_filename,
)


class GridTriangleTests(unittest.TestCase):
    def test_matches_the_documented_targets(self):
        # These two numbers are quoted in docs/16 and in the PR description.
        self.assertEqual(grid_triangles(224), 100352)
        self.assertEqual(grid_triangles(354), 250632)

    def test_formula(self):
        for segments in (1, 2, 10, 224, 354):
            with self.subTest(segments=segments):
                self.assertEqual(grid_triangles(segments), 2 * segments * segments)

    def test_empty_scene_has_no_triangles(self):
        self.assertEqual(grid_triangles(0), 0)


class SceneDefinitionTests(unittest.TestCase):
    def test_three_baseline_scenes_in_order(self):
        self.assertEqual(list(SCENES), ["empty", "100k", "250k"])

    def test_only_the_heavy_scene_casts_shadows(self):
        self.assertFalse(SCENES["empty"][1])
        self.assertFalse(SCENES["100k"][1])
        self.assertTrue(SCENES["250k"][1])

    def test_100k_scene_is_near_100k_triangles(self):
        segments = SCENES["100k"][0]
        self.assertLess(abs(grid_triangles(segments) - 100_000), 5_000)

    def test_250k_scene_is_near_250k_triangles(self):
        segments = SCENES["250k"][0]
        self.assertLess(abs(grid_triangles(segments) - 250_000), 5_000)

    def test_every_scene_has_a_blend_filename(self):
        self.assertEqual(set(SCENE_FILENAMES), set(SCENES))
        for name in SCENE_FILENAMES.values():
            self.assertTrue(name.endswith(".blend"))


class SceneFilenameTests(unittest.TestCase):
    def test_no_suffix_is_the_plain_name(self):
        self.assertEqual(scene_filename("100k"), "bench100k.blend")
        self.assertEqual(scene_filename("empty", ""), "empty.blend")

    def test_suffix_goes_before_the_extension(self):
        self.assertEqual(scene_filename("100k", "_uncapped"), "bench100k_uncapped.blend")
        self.assertEqual(scene_filename("250k", "_uncapped"), "bench250k_shadow_uncapped.blend")

    def test_component_module_points_at_the_shim(self):
        # The scenes live in game/bench/, which has its own rr_components shim.
        self.assertEqual(COMPONENT_MODULE, "rr_components.BenchRecorder")


if __name__ == "__main__":
    unittest.main()

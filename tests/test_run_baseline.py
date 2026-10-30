"""Unit tests for the benchmark runner's pure helpers.

The runner itself shells out to ``blenderplayer``; everything that can be decided
without launching the player is a pure function and is covered here.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "bench"))

from run_baseline import (  # noqa: E402
    build_env,
    launch_flags,
    load_scene_manifest,
    parse_gl_block,
    parse_resolution,
    slugify,
)


class SlugifyTests(unittest.TestCase):
    def test_makes_filesystem_safe_labels(self):
        self.assertEqual(slugify("HP ZBook 14 G2"), "hp_zbook_14_g2")
        self.assertEqual(slugify("p3/zbook:14"), "p3_zbook_14")

    def test_never_empty(self):
        self.assertEqual(slugify("///"), "unknown")

    def test_is_stable(self):
        self.assertEqual(slugify("P3 ZBook"), slugify("P3 ZBook"))


class ResolutionTests(unittest.TestCase):
    def test_parses_common_spellings(self):
        self.assertEqual(parse_resolution("1280x720"), (1280, 720))
        self.assertEqual(parse_resolution("1366X768"), (1366, 768))
        self.assertEqual(parse_resolution(" 1920 * 1080 "), (1920, 1080))

    def test_rejects_garbage(self):
        for bad in ("1280", "1280x", "axb", "0x720", "1280x0", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_resolution(bad)


class LaunchFlagTests(unittest.TestCase):
    def test_windowed_uses_wh(self):
        self.assertEqual(launch_flags("windowed", 1280, 720), ["-w", "1280", "720"])

    def test_fullscreen_uses_f_with_bpp_and_rate(self):
        self.assertEqual(launch_flags("fullscreen", 1366, 768),
                         ["-f", "1366", "768", "32", "60"])

    def test_fixedtime_flag_comes_first(self):
        # blenderplayer requires all flags before the .blend path, and -g must
        # precede the display mode so it is not parsed as a file name.
        flags = launch_flags("fullscreen", 1280, 720, all_frames=True)
        self.assertEqual(flags[:2], ["-g", "fixedtime"])
        self.assertEqual(flags[-5:], ["-f", "1280", "720", "32", "60"])


class GlParseTests(unittest.TestCase):
    SAMPLE = """\
GL_VENDOR: Intel
GL_RENDERER: Mesa Intel(R) HD Graphics 5500 (BDW GT2)
GL_VERSION: 4.6 (Core Profile) Mesa 26.0.8-1ubuntu0.3
GL_SHADING_LANGUAGE_VERSION: 4.60
Supported Extensions...
 GL_ARB_shader_objects supported?       yes.
"""

    def test_extracts_the_gl_block(self):
        parsed = parse_gl_block(self.SAMPLE)
        self.assertEqual(parsed["gl_vendor"], "Intel")
        self.assertEqual(parsed["gl_renderer"], "Mesa Intel(R) HD Graphics 5500 (BDW GT2)")
        self.assertIn("Mesa 26.0.8", parsed["gl_version"])

    def test_missing_block_yields_none_not_a_guess(self):
        parsed = parse_gl_block("no GL output here")
        self.assertIsNone(parsed["gl_renderer"])
        self.assertIsNone(parsed["gl_vendor"])

    def test_empty_output(self):
        parsed = parse_gl_block("")
        self.assertIsNone(parsed["gl_version"])


class EnvTests(unittest.TestCase):
    BASE = {"PATH": "/usr/bin", "HOME": "/home/tester"}

    def test_sets_the_component_contract(self):
        env = build_env(self.BASE, seconds=60, warmup=3, out_path="/tmp/r.json",
                        scene_label="empty", preset="low", resolution="1280x720", dgpu=False)
        self.assertEqual(env["RR_BENCH"], "1")
        self.assertEqual(env["RR_BENCH_SECONDS"], "60")
        self.assertEqual(env["RR_BENCH_WARMUP"], "3")
        self.assertEqual(env["RR_BENCH_OUT"], "/tmp/r.json")
        self.assertEqual(env["RR_BENCH_SCENE"], "empty")
        self.assertEqual(env["RR_BENCH_PRESET"], "low")
        self.assertEqual(env["RR_BENCH_RES"], "1280x720")
        self.assertNotIn("DRI_PRIME", env)

    def test_dgpu_sets_dri_prime(self):
        env = build_env(self.BASE, seconds=10, warmup=1, out_path="/tmp/r.json",
                        scene_label="empty", preset=None, resolution="1280x720", dgpu=True)
        self.assertEqual(env["DRI_PRIME"], "1")

    def test_dgpu_off_clears_a_stale_dri_prime(self):
        base = dict(self.BASE, DRI_PRIME="1")
        env = build_env(base, seconds=10, warmup=1, out_path="/tmp/r.json",
                        scene_label="empty", preset=None, resolution="1280x720", dgpu=False)
        self.assertNotIn("DRI_PRIME", env)

    def test_absent_preset_is_not_serialized(self):
        base = dict(self.BASE, RR_BENCH_PRESET="high")
        env = build_env(base, seconds=10, warmup=1, out_path="/tmp/r.json",
                        scene_label="empty", preset=None, resolution="1280x720", dgpu=False)
        self.assertNotIn("RR_BENCH_PRESET", env)

    def test_does_not_mutate_the_caller_environment(self):
        base = dict(self.BASE)
        build_env(base, seconds=1, warmup=0, out_path="/tmp/r.json", scene_label="x",
                  preset=None, resolution="1280x720", dgpu=True)
        self.assertNotIn("DRI_PRIME", base)
        self.assertNotIn("RR_BENCH", base)


class SceneManifestTests(unittest.TestCase):
    def test_reads_capped_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "scenes.json").write_text(json.dumps({"frame_rate_cap": "vsync=ON"}))
            self.assertEqual(load_scene_manifest(Path(tmp), "")["frame_rate_cap"], "vsync=ON")

    def test_reads_suffixed_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "scenes_uncapped.json").write_text(json.dumps({"frame_rate_cap": "vsync=OFF"}))
            self.assertEqual(load_scene_manifest(Path(tmp), "_uncapped")["frame_rate_cap"], "vsync=OFF")

    def test_missing_manifest_is_empty_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_scene_manifest(Path(tmp), ""), {})

    def test_corrupt_manifest_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "scenes.json").write_text("{not json")
            self.assertEqual(load_scene_manifest(Path(tmp), ""), {})


if __name__ == "__main__":
    unittest.main()

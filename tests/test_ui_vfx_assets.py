"""Unit tests for the UI/VFX asset generator and checker (docs/04 sections 3-5).

Pure helpers (layout, splash sim, wake field, validation math) are tested without
Pillow. End-to-end render+check tests need Pillow and are skipped when it is
missing; generator helpers need numpy and are skipped when numpy is missing.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))

import check_ui_vfx_assets as chk  # noqa: E402

try:  # numpy is needed by the generator module itself
    import numpy as np  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

try:
    from PIL import Image  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

if HAVE_NUMPY:
    import gen_ui_vfx_assets as gen  # noqa: E402


class PowerOfTwoTests(unittest.TestCase):
    def test_powers(self):
        for n in (1, 2, 4, 128, 256, 512, 1024, 2048):
            self.assertTrue(chk.is_power_of_two(n), n)

    def test_non_powers(self):
        for n in (0, -2, 3, 100, 1000, 1023, 1025):
            self.assertFalse(chk.is_power_of_two(n), n)


class DimensionTests(unittest.TestCase):
    def test_valid(self):
        for size in ((128, 128), (256, 256), (512, 512), (1024, 1024), (256, 1024)):
            self.assertEqual(chk.check_dimensions(*size), [], size)

    def test_non_power_of_two(self):
        errs = chk.check_dimensions(100, 1024)
        self.assertTrue(any("not power-of-two" in e for e in errs), errs)

    def test_over_max(self):
        errs = chk.check_dimensions(4096, 4096)
        self.assertTrue(any("exceeds max" in e for e in errs), errs)


class AlphaUsageTests(unittest.TestCase):
    def test_mixed_alpha_is_used(self):
        self.assertEqual(chk.has_used_alpha([0, 128, 255, 255]), [])

    def test_fully_opaque_is_unused_alpha(self):
        errs = chk.has_used_alpha([255] * 10)
        self.assertTrue(any("unused alpha" in e for e in errs), errs)

    def test_fully_transparent(self):
        errs = chk.has_used_alpha([0] * 10)
        self.assertTrue(any("fully transparent" in e for e in errs), errs)


class AtlasMapTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"name": "coin", "x": 0, "y": 0, "w": 128, "h": 128},
            {"name": "fish", "x": 128, "y": 0, "w": 128, "h": 128},
            {"name": "heart_full", "x": 0, "y": 128, "w": 128, "h": 128},
        ]

    def test_valid_layout(self):
        self.assertEqual(chk.atlas_map_errors(self.entries, 256, 256), [])

    def test_out_of_bounds(self):
        self.entries[1]["x"] = 200
        errs = chk.atlas_map_errors(self.entries, 256, 256)
        self.assertTrue(any("out of atlas bounds" in e for e in errs), errs)

    def test_overlap_detected(self):
        self.entries[1] = {"name": "dup", "x": 0, "y": 0, "w": 128, "h": 128}
        errs = chk.atlas_map_errors(self.entries, 256, 256)
        self.assertTrue(any("overlaps" in e for e in errs), errs)

    def test_duplicate_name(self):
        self.entries[2]["name"] = "coin"
        errs = chk.atlas_map_errors(self.entries, 256, 256)
        self.assertTrue(any("duplicate" in e for e in errs), errs)


class SeamTests(unittest.TestCase):
    def _rows(self, n=64, cycles=2.0, amp=50.0):
        import math
        return [[128 + amp * math.cos(2 * math.pi * cycles * i / n) for _ in range(4)]
                for i in range(n)]

    def test_periodic_rows_tile(self):
        m = chk.seam_metrics(self._rows())
        self.assertLessEqual(m["ratio"], chk.SEAM_RATIO_LIMIT, m)
        self.assertEqual(chk.tileable_errors(m), [])

    def test_discontinuity_detected(self):
        # half-integer cycle count: smooth everywhere, but jumps at the wrap
        m = chk.seam_metrics(self._rows(cycles=2.5))
        self.assertGreater(m["ratio"], chk.SEAM_RATIO_LIMIT, m)
        self.assertTrue(chk.tileable_errors(m))


class MinBrightnessTests(unittest.TestCase):
    """min_visible_luminance is informational only, not a gate."""

    def test_bright_pixels_measured(self):
        lum, cnt = chk.min_visible_luminance([(200, 230, 255, 255), (255, 255, 255, 200)])
        self.assertEqual(cnt, 2)
        self.assertEqual(lum, 255)  # max channel per pixel, then min over pixels

    def test_transparent_pixels_ignored(self):
        lum, cnt = chk.min_visible_luminance([(10, 10, 10, 255), (0, 0, 0, 0)])
        self.assertEqual(cnt, 1)
        self.assertEqual(lum, 10)

    def test_no_visible_pixels(self):
        lum, cnt = chk.min_visible_luminance([(10, 10, 10, 0)])
        self.assertEqual((lum, cnt), (255, 0))


class TransparentBleedTests(unittest.TestCase):
    def test_energy_counts_only_transparent_pixels(self):
        energy = chk.transparent_rgb_energy([(10, 20, 30, 0), (100, 100, 100, 255),
                                             (1, 2, 3, 0), (5, 5, 5, 31)])
        self.assertEqual(energy, 10 + 20 + 30 + 1 + 2 + 3)

    def test_zero_energy_passes(self):
        self.assertEqual(chk.transparent_bleed_errors(0, documented=False), [])
        self.assertEqual(chk.transparent_bleed_errors(0, documented=True), [])

    def test_undocumented_energy_fails(self):
        errs = chk.transparent_bleed_errors(78_000, documented=False)
        self.assertTrue(any("raw ADD" in e for e in errs), errs)
        self.assertTrue(any("transparent_rgb_bleed" in e for e in errs), errs)

    def test_documented_bleed_passes(self):
        self.assertEqual(chk.transparent_bleed_errors(78_000, documented=True), [])


class _FakeImage:
    """Stands in for a PIL image in pixel-hash unit tests (no Pillow needed)."""

    def __init__(self, raw: bytes):
        self._raw = raw

    def convert(self, _mode):
        return self

    def tobytes(self) -> bytes:
        return self._raw


class PixelHashTests(unittest.TestCase):
    REF = "a" * 64

    def test_matching_hash_passes(self):
        img = _FakeImage(b"\x00\xff\x00\xff" * 4)
        meta = {"pillow_version": "13.0.0", "numpy_version": "2.5.4",
                "pixel_hash": chk.pixel_sha256(img)}
        self.assertEqual(chk.pixel_hash_errors(img, meta, "test"), [])

    def test_mismatched_hash_fails(self):
        img = _FakeImage(b"\x00\xff\x00\xff" * 4)
        meta = {"pillow_version": "13.0.0", "numpy_version": "2.5.4",
                "pixel_hash": PixelHashTests.REF}
        errs = chk.pixel_hash_errors(img, meta, "test")
        self.assertTrue(any("pixel_hash mismatch" in e for e in errs), errs)

    def test_missing_meta_fails_cleanly(self):
        img = _FakeImage(b"\x00" * 16)
        errs = chk.pixel_hash_errors(img, {}, "test")
        self.assertTrue(any("pixel_hash" in e for e in errs), errs)
        self.assertTrue(any("pillow_version" in e for e in errs), errs)
        self.assertTrue(any("numpy_version" in e for e in errs), errs)


@unittest.skipUnless(HAVE_NUMPY, "numpy is required for generator helpers")
class IconLayoutTests(unittest.TestCase):
    def test_layout_matches_spec(self):
        entries = gen.icon_atlas_layout()
        self.assertEqual(len(entries), 9)
        self.assertEqual(entries[0], {"name": "coin", "x": 0, "y": 0, "w": 128, "h": 128})
        # 8 per row at 128 px -> last of row 0 at x=896, 9th icon wraps to row 1
        self.assertEqual(entries[7]["x"], 896)
        self.assertEqual(entries[8], {"name": "speaker_off", "x": 0, "y": 128,
                                      "w": 128, "h": 128})
        self.assertEqual(chk.atlas_map_errors(entries, 1024, 1024), [])

    def test_layout_refuses_overflow(self):
        with self.assertRaises(ValueError):
            gen.icon_atlas_layout(names=tuple(f"i{n}" for n in range(65)))


@unittest.skipUnless(HAVE_NUMPY, "numpy is required for generator helpers")
class GeometryTests(unittest.TestCase):
    def test_heart_polygon_bounds(self):
        pts = gen.heart_polygon()
        self.assertEqual(len(pts), 72)
        for x, y in pts:
            self.assertGreaterEqual(x, -1.0)
            self.assertLessEqual(x, 1.0)
            self.assertGreaterEqual(y, -1.05)
            self.assertLessEqual(y, 1.0)

    def test_gear_polygon_radii(self):
        pts = gen.gear_polygon()
        self.assertEqual(len(pts), 8 * (7 + 5))
        for x, y in pts:
            r = (x * x + y * y) ** 0.5
            self.assertGreaterEqual(r, 0.62 - 1e-9)
            self.assertLessEqual(r, 0.90 + 1e-9)


@unittest.skipUnless(HAVE_NUMPY, "numpy is required for generator helpers")
class SplashTests(unittest.TestCase):
    def test_droplets_deterministic(self):
        a, b = gen.splash_droplets(), gen.splash_droplets()
        for key in a:
            self.assertTrue((a[key] == b[key]).all(), key)

    def test_field_deterministic(self):
        a = gen.splash_intensity_field(3, 64)
        b = gen.splash_intensity_field(3, 64)
        self.assertTrue((a == b).all())

    def test_field_in_range(self):
        for f in (0, 5, 15):
            field = gen.splash_intensity_field(f, 64)
            self.assertGreaterEqual(field.min(), 0.0)
            self.assertLessEqual(field.max(), 1.0)

    def test_burst_expands_and_fades(self):
        def mean_radius(frame):
            size = 64
            field = gen.splash_intensity_field(frame, size)
            yy, xx = np.mgrid[0:size, 0:size]
            w = field / field.sum()
            return (w * np.hypot(xx - size / 2, yy - size / 2)).sum()

        early, mid = mean_radius(1), mean_radius(8)
        self.assertGreater(mid, early)  # droplets spread further out over time
        # last frame carries (almost) no energy: fully faded
        last = gen.splash_intensity_field(15, 64).sum()
        self.assertLess(last, gen.splash_intensity_field(0, 64).sum() * 0.02)


@unittest.skipUnless(HAVE_NUMPY, "numpy is required for generator helpers")
class WakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.field = gen.wake_intensity_field(256)

    def test_field_in_range(self):
        self.assertGreaterEqual(self.field.min(), 0.0)
        self.assertLessEqual(self.field.max(), 1.0)
        self.assertGreater(self.field.max(), 0.5)  # actually has foam on it

    def test_tileable_both_axes(self):
        for axis in (0, 1):
            rows = self.field if axis == 0 else self.field.T
            m = chk.seam_metrics([list(r) for r in rows])
            self.assertLessEqual(m["ratio"], chk.SEAM_RATIO_LIMIT, (axis, m))

    def test_deterministic(self):
        other = gen.wake_intensity_field(256)
        self.assertTrue((self.field == other).all())


@unittest.skipUnless(HAVE_NUMPY, "numpy is required for generator helpers")
class NumericHelperTests(unittest.TestCase):
    def test_downsample_mean(self):
        arr = np.array([[1.0, 3.0], [5.0, 7.0]])
        self.assertEqual(gen.downsample_mean(arr, 2).item(), 4.0)

    def test_downsample_rejects_bad_factor(self):
        with self.assertRaises(ValueError):
            gen.downsample_mean(np.zeros((3, 3)), 2)

    def test_tint_endpoints(self):
        field = np.array([[0.0, 1.0]])
        rgb = gen.tint_by_intensity(field, (0, 0, 0), (255, 255, 255))
        self.assertEqual(rgb[0, 0].tolist(), [0, 0, 0])
        self.assertEqual(rgb[0, 1].tolist(), [255, 255, 255])


class NamingTests(unittest.TestCase):
    def test_valid_names(self):
        for rel in ("assets/ui/T_UI_IconSet_A.png", "assets/vfx/T_VX_Splash_A.png",
                    "assets/vfx/T_VX_Wake_A.png", "assets/ui/T_Hud_BC.png"):
            self.assertEqual(chk.texture_naming_errors(rel), [], rel)

    def test_bad_pattern(self):
        for rel in ("assets/ui/icons.png", "assets/ui/T_icons.png",
                    "assets/ui/T_UI_IconSet_X.png", "assets/ui/T_UI_IconSet_A.jpg"):
            errs = chk.texture_naming_errors(rel)
            self.assertTrue(any("does not match" in e for e in errs), (rel, errs))

    def test_bad_folder(self):
        errs = chk.texture_naming_errors("assets/textures/T_UI_IconSet_A.png")
        self.assertTrue(any("must live in" in e for e in errs), errs)

    def test_atlas_ref_mismatch(self):
        errs = chk.texture_naming_errors("assets/vfx/T_VX_Splash_A.png",
                                         "T_VX_Splash_v2.png")
        self.assertTrue(any("references" in e for e in errs), errs)

    def test_atlas_ref_match_passes(self):
        self.assertEqual(chk.texture_naming_errors("assets/vfx/T_VX_Splash_A.png",
                                                   "T_VX_Splash_A.png"), [])


class VfxAtlasLimitTests(unittest.TestCase):
    def test_vfx_limit_is_512(self):
        self.assertEqual(chk.VFX_MAX_DIM, 512)  # docs/04 s4: VFX sprite atlas <= 512

    def test_oversized_vfx_atlas_fails(self):
        errs = chk.check_dimensions(1024, 1024, max_dim=chk.VFX_MAX_DIM)
        self.assertTrue(any("exceeds max" in e for e in errs), errs)

    def test_512_passes(self):
        self.assertEqual(chk.check_dimensions(512, 512, max_dim=chk.VFX_MAX_DIM), [])


class CleanFailureTests(unittest.TestCase):
    """A broken PNG must produce a FAIL line, never a traceback (review F3)."""

    FILES = chk.EXPECTED

    def _make_root(self, png_bytes: bytes) -> tempfile.TemporaryDirectory:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        for key, rel in self.FILES.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"{}" if key.endswith("json") else png_bytes)
        return tmp

    def _run(self, png_bytes: bytes):
        tmp = self._make_root(png_bytes)
        try:
            return chk.run_checks(Path(tmp.name))
        finally:
            tmp.cleanup()

    def test_lfs_pointer_fails_cleanly(self):
        pointer = (b"version https://git-lfs.github.com/spec/v1\n"
                   b"oid sha256:deadbeef\nsize 123\n")
        ok, bad = self._run(pointer)
        fails = [line for line in bad if line.startswith("FAIL")]
        self.assertGreaterEqual(len(fails), 3, bad)
        for line in fails:
            self.assertIn("Git LFS pointer", line, line)

    def test_garbage_png_fails_cleanly(self):
        ok, bad = self._run(b"definitely not a png")
        fails = [line for line in bad if line.startswith("FAIL")]
        self.assertGreaterEqual(len(fails), 3, bad)
        for line in fails:
            self.assertTrue("PIL cannot decode" in line or "Pillow is required" in line,
                            line)


@unittest.skipUnless(HAVE_PIL and HAVE_NUMPY, "Pillow + numpy required for rendering")
class EndToEndTests(unittest.TestCase):
    """Generate into a temp dir, then run the checker over the output."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        gen.generate_all(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_checker_finds_no_failures(self):
        ok, bad = chk.run_checks(self.root)
        self.assertEqual([line for line in bad if line.startswith("FAIL")], [],
                         "\n".join(bad))
        self.assertGreater(len([line for line in ok if line.startswith("PASS")]), 10)

    def test_committed_pixels_match_regeneration(self):
        """Committed PNGs must decode to exactly what the generator produces now.

        PNG bytes may differ between zlib/Pillow builds, decoded pixels may not;
        this is the cross-machine reproducibility contract (checked here on this
        machine against whatever is committed).
        """
        repo_root = Path(__file__).resolve().parents[1]
        atlases = (
            ("assets/ui/T_UI_IconSet_A.png", "assets/ui/T_UI_IconSet_A.json"),
            ("assets/vfx/T_VX_Splash_A.png", "assets/vfx/T_VX_Splash_A.json"),
            ("assets/vfx/T_VX_Wake_A.png", "assets/vfx/T_VX_Wake_A.json"),
        )
        for png_rel, json_rel in atlases:
            with Image.open(repo_root / png_rel) as committed:
                committed_hash = chk.pixel_sha256(committed)
            with Image.open(self.root / png_rel) as fresh:
                fresh_hash = chk.pixel_sha256(fresh)
            self.assertEqual(committed_hash, fresh_hash, png_rel)
            recorded = json.loads((repo_root / json_rel).read_text(encoding="utf-8"))
            self.assertEqual(recorded["pixel_hash"], committed_hash, json_rel)

    def test_splash_json_declares_blank_padding_frame(self):
        sp_map = json.loads(
            (self.root / "assets/vfx/T_VX_Splash_A.json").read_text(encoding="utf-8"))
        self.assertEqual(sp_map["frames_used"], 15)
        self.assertTrue(sp_map["last_frame_empty"])

    def test_vfx_transparent_pixels_carry_no_rgb(self):
        """Additive gate: zero RGB energy behind alpha == 0 (raw-ADD safe)."""
        for png_rel in ("assets/vfx/T_VX_Splash_A.png", "assets/vfx/T_VX_Wake_A.png"):
            with Image.open(self.root / png_rel) as img:
                energy = chk.transparent_rgb_energy(chk._rgba_tuples(img.tobytes()))
            self.assertEqual(energy, 0, png_rel)


if __name__ == "__main__":
    unittest.main()

"""Engine-fake tests for rr.glue.smoke (no UPBGE needed).

A stub `bge` module and a scripted 60 Hz clock drive the real component through
start()/update(), so the frame-delta collection, warmup discard, cross-check
sampling, gates and the JSON report are exercised without an engine.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

FRAMES = 1200           # 20 s at 60 Hz
FPS_FRAME = 1.0 / 60.0


class FakeClock:
    def __init__(self):
        self.frame = 0

    def wall(self):
        return self.frame * FPS_FRAME

    def perf(self):
        return self.frame * FPS_FRAME

    def step(self, n=1):
        self.frame += n


def _fake_bge(fps_sequence, ended):
    return SimpleNamespace(
        types=SimpleNamespace(KX_PythonComponent=object),
        logic=SimpleNamespace(
            getAverageFrameRate=fps_sequence,
            globalDict={},
            endGame=lambda: ended.append(True),
        ),
    )


def _load_smoke(fake):
    with patch.dict(sys.modules, {"bge": fake}):
        sys.modules.pop("rr.glue.smoke", None)
        return importlib.import_module("rr.glue.smoke")


class SmokeComponentTests(unittest.TestCase):
    def _run(self, *, fps: float | Callable[[], float] = 59.9, env_extra=None,
             move_to=None, frames=FRAMES):
        ended = []
        fps_fn = fps if callable(fps) else (lambda: fps)
        smoke = _load_smoke(_fake_bge(fps_fn, ended))
        comp = smoke.SmokeTest.__new__(smoke.SmokeTest)
        comp.object = SimpleNamespace(worldPosition=[0.0, 4.0, 0.0])
        clock = FakeClock()
        env = {
            "RR_SMOKE": "1",
            "RR_SMOKE_SECONDS": "20",
            "RR_SMOKE_OUT": str(self.tmp / "smoke_result.json"),
        }
        if env_extra:
            env.update(env_extra)
        with patch.dict(os.environ, env):
            with patch("time.time", side_effect=clock.wall), \
                    patch("time.perf_counter", side_effect=clock.perf):
                args = {"Seconds": 20.0, "Warmup Seconds": 3.0, "Expect Movement": True}
                comp.start(args)
                for frame in range(1, frames + 1):
                    clock.step()
                    if move_to is not None and frame == frames // 2:
                        comp.object.worldPosition = list(move_to)
                    comp.update()
        report = json.loads((self.tmp / "smoke_result.json").read_text())
        return report, ended

    def setUp(self):
        self.tmp_ctx = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_ctx.name)
        self.addCleanup(self.tmp_ctx.cleanup)

    def test_moving_scene_passes_with_benchstats_report(self):
        report, ended = self._run(move_to=(0.0, 9.0, 0.0))
        self.assertEqual(ended, [True])
        self.assertTrue(report["ok"])
        self.assertTrue(report["moved_ok"])
        self.assertTrue(report["expect_movement"])
        self.assertEqual(report["distance_moved_m"], 5.0)
        self.assertEqual(report["seconds"], 20.0)
        self.assertEqual(report["warmup_s"], 3.0)

        # Authoritative frame-interval statistics (no per-second sampling left).
        self.assertAlmostEqual(report["fps_avg"], 60.0, places=1)
        self.assertAlmostEqual(report["fps_min"], 60.0, places=1)
        self.assertAlmostEqual(report["p1_low_fps"], 60.0, places=1)
        self.assertAlmostEqual(report["frame_time_ms"]["p50"], 1000.0 / 60.0, places=1)
        self.assertEqual(report["stutter_count"], 0)
        self.assertEqual(report["frames_measured"], 1199 - 180)  # first delta + 3 s warmup dropped
        self.assertNotIn("fps_p5", report)

        # Additive cross-check stays secondary and visible.
        cc = report["fps_crosscheck"]
        self.assertEqual(cc["samples"], 20)
        self.assertAlmostEqual(cc["median_fps"], 59.9, places=2)
        self.assertAlmostEqual(cc["mean_post_warmup_fps"], 59.9, places=2)
        self.assertAlmostEqual(cc["max_fps"], 59.9, places=2)

    def test_static_scene_fails_only_when_movement_is_expected(self):
        report, _ = self._run()
        self.assertFalse(report["moved_ok"])
        self.assertFalse(report["ok"])

    def test_static_scene_passes_when_expect_movement_is_zero(self):
        report, ended = self._run(env_extra={"RR_SMOKE_EXPECT_MOVEMENT": "0"})
        self.assertEqual(ended, [True])
        self.assertIsNone(report["moved_ok"])
        self.assertTrue(report["ok"])

    def test_warmup_is_configurable(self):
        report, _ = self._run(env_extra={"RR_SMOKE_WARMUP": "0.5"})
        self.assertEqual(report["warmup_s"], 0.5)
        # 30 frames of 1/60 s float-accumulate just below 0.5, so benchstats'
        # boundary-crossing frame is also consumed (documented warmup rule).
        self.assertEqual(report["frames_measured"], 1199 - 31)
        self.assertEqual(report["fps_crosscheck"]["post_warmup_samples"], 20)

    def test_outlier_sample_stays_visible_in_crosscheck(self):
        calls = iter([59.9] + [1_000_000.0] + [59.9] * 100)
        report, _ = self._run(fps=lambda: next(calls))
        cc = report["fps_crosscheck"]
        self.assertEqual(cc["max_fps"], 1_000_000.0)          # visible, not swallowed
        self.assertAlmostEqual(cc["median_fps"], 59.9, places=2)
        self.assertGreater(cc["mean_post_warmup_fps"], 59.9)  # post-warmup mean is honest

    def test_disabled_component_does_nothing(self):
        ended = []
        smoke = _load_smoke(_fake_bge(lambda: 60.0, ended))
        comp = smoke.SmokeTest.__new__(smoke.SmokeTest)
        comp.object = SimpleNamespace(worldPosition=[0.0, 0.0, 0.0])
        with patch.dict(os.environ, {"RR_SMOKE_OUT": str(self.tmp / "smoke_result.json")}):
            comp.start({"Seconds": 20.0, "Warmup Seconds": 3.0, "Expect Movement": True})
            comp.update()
        self.assertEqual(ended, [])
        self.assertFalse((self.tmp / "smoke_result.json").exists())

    def test_legacy_scene_args_only_seconds_still_works(self):
        # Scenes saved before the component grew the later args store only
        # "Seconds"; start() must not KeyError and must use the defaults.
        ended = []
        smoke = _load_smoke(_fake_bge(lambda: 60.0, ended))
        comp = smoke.SmokeTest.__new__(smoke.SmokeTest)
        comp.object = SimpleNamespace(worldPosition=[0.0, 0.0, 0.0])
        clock = FakeClock()
        env = {
            "RR_SMOKE": "1",
            "RR_SMOKE_SECONDS": "20",
            "RR_SMOKE_OUT": str(self.tmp / "smoke_result.json"),
        }
        with patch.dict(os.environ, env):
            with patch("time.time", side_effect=clock.wall), \
                    patch("time.perf_counter", side_effect=clock.perf):
                comp.start({"Seconds": 20.0})
                for _ in range(FRAMES):
                    clock.step()
                    comp.update()
        report = json.loads((self.tmp / "smoke_result.json").read_text())
        self.assertEqual(report["warmup_s"], 3.0)
        self.assertTrue(report["expect_movement"])
        self.assertEqual(ended, [True])

    def test_autopaddle_flag_is_set_for_moving_scenes(self):
        ended = []
        fake = _fake_bge(lambda: 60.0, ended)
        smoke = _load_smoke(fake)
        comp = smoke.SmokeTest.__new__(smoke.SmokeTest)
        comp.object = SimpleNamespace(worldPosition=[0.0, 0.0, 0.0])
        with patch.dict(os.environ, {"RR_SMOKE": "1", "RR_SMOKE_OUT": str(self.tmp / "x.json")}):
            comp.start({"Seconds": 20.0, "Warmup Seconds": 3.0, "Expect Movement": True})
        self.assertTrue(fake.logic.globalDict["rr_autopaddle"])


if __name__ == "__main__":
    unittest.main()

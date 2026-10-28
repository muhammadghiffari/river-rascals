"""Headless policy and adapter tests; no claim of aud runtime verification."""
import importlib.util
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


@unittest.skipUnless(importlib.util.find_spec("numpy"), "offline synthesis requires numpy")
class SynthesisTests(unittest.TestCase):
    def test_deterministic_distinct_faded_mono_takes(self):
        import numpy as np
        from generate_prototype_audio import synthesize

        for kind, duration in [("dip", .4), ("pull", .8), ("exit", .5), ("splash", .6), ("hard", .8)]:
            a = synthesize(kind, duration, 123, rate=8000)
            b = synthesize(kind, duration, 124, rate=8000)
            self.assertEqual(a.shape, (round(duration * 8000),))
            self.assertTrue(np.array_equal(a, synthesize(kind, duration, 123, rate=8000)))
            self.assertFalse(np.array_equal(a, b))
            self.assertTrue(np.isfinite(a).all())
            self.assertLessEqual(float(np.max(np.abs(a))), .61)
            self.assertEqual(float(a[0]), 0)
            self.assertEqual(float(a[-1]), 0)

    def test_loops_continuous_non_silent_stereo(self):
        import numpy as np
        from generate_prototype_audio import synthesize

        for kind in ("rush", "creek"):
            a = synthesize(kind, 8, 45, rate=8000)
            self.assertEqual(a.shape, (64000, 2))
            self.assertLess(float(np.max(np.abs(a[-1] - a[0]))), .015)
            self.assertGreater(float(np.sqrt(np.mean(a[:800] ** 2))), .005)
            self.assertLess(float(np.corrcoef(a.T)[0, 1]), .99)


class AudioPolicyTests(unittest.TestCase):
    def test_policy_no_repeat_and_cooldown(self):
        from rr.core.prototype_audio import AudioPolicy

        policy = AudioPolicy(random.Random(17))
        previous = None
        for now in range(30):
            cue = policy.choose("paddle", now)
            self.assertNotEqual(previous, cue.path)
            self.assertGreaterEqual(cue.pitch, 0.94)
            self.assertLessEqual(cue.pitch, 1.06)
            self.assertIsNone(policy.choose("paddle", now + 0.001))
            previous = cue.path

    def test_unknown_event_rejected(self):
        from rr.core.prototype_audio import AudioPolicy

        with self.assertRaises(ValueError):
            AudioPolicy().choose("typo", 0)


class FakeHandle:
    status = 1

    def stop(self):
        self.status = 0


class FakeDevice:
    def __init__(self):
        self.handles = []

    def lock(self):
        pass

    def unlock(self):
        pass

    def play(self, sound):
        handle = FakeHandle()
        self.handles.append(handle)
        return handle


class AdapterTests(unittest.TestCase):
    def setUp(self):
        from rr.glue.prototype_audio import PrototypeAudio

        self.device = FakeDevice()
        module = SimpleNamespace(Device=lambda: self.device, Sound=lambda path: path)
        with patch.dict(sys.modules, {"aud": module}):
            self.audio = PrototypeAudio(Path(__file__).resolve().parents[1])

    def tearDown(self):
        self.audio.close()

    def test_idempotent_modes_and_close(self):
        self.audio.set_mode("menu")
        self.audio.set_mode("menu")
        self.assertEqual(len(self.device.handles), 1)
        self.audio.set_mode("playing")
        self.assertEqual(self.device.handles[0].status, 0)
        self.assertEqual(len(self.audio.loops), 2)
        self.audio.close()
        self.audio.close()
        self.audio.set_mode("menu")
        self.assertTrue(all(h.status == 0 for h in self.device.handles))

    def test_event_flood_is_bounded_and_counted(self):
        with patch("rr.glue.prototype_audio.time.monotonic", return_value=10):
            for _ in range(100):
                self.audio.event("paddle")
        self.assertEqual(self.audio.event_counts["paddle"], 100)
        self.assertEqual(self.audio.played_counts["paddle"], 1)
        self.assertEqual(self.audio.dropped_counts["paddle"], 99)
        with patch("rr.glue.prototype_audio.time.monotonic", side_effect=range(20, 40)):
            for _ in range(20):
                self.audio.event("paddle")
        self.assertLessEqual(len(self.audio.voices), 2)

    def test_backend_failure_is_observable_noop(self):
        self.device.play = lambda sound: (_ for _ in ()).throw(RuntimeError("test backend failure"))
        self.audio.event("click")
        self.assertEqual(self.audio.error_count, 1)
        self.assertIn("test backend failure", self.audio.errors[-1])
        self.assertEqual(self.audio.played_counts["click"], 0)

    def test_mode_change_clears_one_shots(self):
        self.audio.event("splash")
        self.audio.set_mode("complete")
        self.assertEqual(self.device.handles[0].status, 0)
        self.assertEqual(self.audio.voices, [])


if __name__ == "__main__":
    unittest.main()

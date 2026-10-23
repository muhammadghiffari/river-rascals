"""Unit tests for pure core logic. Run: python -m unittest discover -s tests -v"""
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rr.core.buoyancy import BuoyancyConfig, buoyancy_force, quadratic_drag  # noqa: E402
from rr.core.events import EventBus  # noqa: E402
from rr.core.oar import Oar, OarConfig, OarPhase  # noqa: E402
from rr.core.progress import CheckpointTracker  # noqa: E402
from rr.core.river import River  # noqa: E402
from rr.core.save import SaveData, from_json, read, to_json, write_atomic  # noqa: E402
from rr.core.waves import wave_height  # noqa: E402


def straight_river():
    # Flows toward +Y, 10 m wide, 100 m long.
    return River([(0, 0, 0), (0, 50, 0), (0, 100, 0)], [10, 10, 10], base_speed=2.0, edge_factor=0.4)


class RiverTests(unittest.TestCase):
    def test_length_and_progress(self):
        r = straight_river()
        self.assertAlmostEqual(r.length, 100.0)
        self.assertAlmostEqual(r.progress((0, 25, 0)), 0.25)
        self.assertEqual(r.progress((0, -10, 0)), 0.0)
        self.assertEqual(r.progress((0, 500, 0)), 1.0)

    def test_flow_profile(self):
        r = straight_river()
        centre = r.flow_at((0, 10, 0))
        self.assertAlmostEqual(centre[1], 2.0)
        edge = r.flow_at((4.9, 10, 0))
        self.assertLess(edge[1], centre[1])
        self.assertGreater(edge[1], 0.0)
        self.assertEqual(r.flow_at((6.0, 10, 0)), (0.0, 0.0, 0.0))

    def test_lateral_sign_is_right_of_flow(self):
        r = straight_river()
        self.assertGreater(r.project((3, 10, 0)).lateral, 0)   # +X is right when flowing +Y
        self.assertLess(r.project((-3, 10, 0)).lateral, 0)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            River([(0, 0, 0)], [1])
        with self.assertRaises(ValueError):
            River([(0, 0, 0), (0, 1, 0)], [1])


class BuoyancyTests(unittest.TestCase):
    def test_no_force_above_water(self):
        self.assertEqual(buoyancy_force(0.5, 0.0, 0.0), 0.0)

    def test_force_grows_with_depth_and_is_clamped(self):
        cfg = BuoyancyConfig()
        a = buoyancy_force(-0.05, 0.0, 0.0, cfg)
        b = buoyancy_force(-0.10, 0.0, 0.0, cfg)
        self.assertGreater(b, a)
        self.assertEqual(buoyancy_force(-10.0, 0.0, 0.0, cfg), cfg.max_force)

    def test_never_pulls_down(self):
        self.assertEqual(buoyancy_force(-0.01, 0.0, 50.0), 0.0)

    def test_equilibrium_matches_design(self):
        # 300 kg raft, 6 samples, ~0.12 m draft => sum of forces ~ m*g
        total = 6 * buoyancy_force(-0.12, 0.0, 0.0)
        self.assertAlmostEqual(total, 300 * 9.81, delta=300 * 9.81 * 0.05)

    def test_drag_opposes_velocity(self):
        f = quadratic_drag((0.0, 3.0, 0.0), 10.0)
        self.assertAlmostEqual(f[1], -90.0)


class OarTests(unittest.TestCase):
    def run_hold(self, oar, seconds, dt=1 / 60):
        out = None
        for _ in range(int(seconds / dt)):
            out = oar.update(dt, True)
        return out

    def test_stroke_cycle(self):
        o = Oar(+1)
        self.assertEqual(o.update(0.016, False).phase, OarPhase.IDLE)
        self.assertEqual(o.update(0.016, True).phase, OarPhase.DIP)
        out = self.run_hold(o, 0.5)
        self.assertEqual(out.phase, OarPhase.PULL)
        self.assertGreater(out.thrust, 0)
        o.update(0.016, False)
        self.assertEqual(o.phase, OarPhase.RECOVER)
        for _ in range(30):
            o.update(1 / 60, False)
        self.assertEqual(o.phase, OarPhase.IDLE)

    def test_right_oar_yaws_left_and_left_oar_yaws_right(self):
        right_oar, left_oar = Oar(+1), Oar(-1)
        self.assertGreater(self.run_hold(right_oar, 0.5).torque_z, 0)
        self.assertLess(self.run_hold(left_oar, 0.5).torque_z, 0)

    def test_backpaddle_reverses_thrust(self):
        o = Oar(+1)
        for _ in range(60):
            out = o.update(1 / 60, True, -1.0)
        self.assertLess(out.thrust, 0)

    def test_pull_is_time_limited(self):
        o = Oar(+1, OarConfig(max_pull_time=0.3))
        phases = {o.update(1 / 60, True).phase for _ in range(120)}
        self.assertIn(OarPhase.RECOVER, phases)

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            Oar(0)


class WaveTests(unittest.TestCase):
    def test_bounded_and_deterministic(self):
        total_amp = 0.05 + 0.03 + 0.015
        for i in range(200):
            h = wave_height(i * 0.7, i * 0.3, i * 0.1)
            self.assertLessEqual(abs(h), total_amp + 1e-9)
        self.assertEqual(wave_height(1.0, 2.0, 3.0), wave_height(1.0, 2.0, 3.0))
        self.assertTrue(math.isfinite(wave_height(1e4, 1e4, 1e4)))


class ProgressTests(unittest.TestCase):
    def test_monotonic(self):
        t = CheckpointTracker([30, 10, 20])
        self.assertEqual(t.update(5), [])
        self.assertEqual(t.update(25), [0, 1])
        self.assertEqual(t.update(15), [])          # going back does nothing
        self.assertEqual(t.last_checkpoint_s, 20)
        self.assertFalse(t.finished)
        self.assertEqual(t.update(99), [2])
        self.assertTrue(t.finished)


class EventTests(unittest.TestCase):
    def test_emit_and_unsubscribe(self):
        bus, got = EventBus(), []
        off = bus.subscribe("coin", lambda value: got.append(value))
        self.assertEqual(bus.emit("coin", value=1), 1)
        off()
        self.assertEqual(bus.emit("coin", value=2), 0)
        self.assertEqual(got, [1])


class SaveTests(unittest.TestCase):
    def test_roundtrip_and_migration(self):
        d = SaveData(coins=5, best_times={"ch1": 61.5}, cosmetics=["hat_red"])
        self.assertEqual(from_json(to_json(d)), d)
        old = from_json('{"version": 1, "coins": 3}')
        self.assertEqual(old.version, 2)
        self.assertEqual(old.coins, 3)

    def test_atomic_write_and_corrupt_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "save.json")
            write_atomic(p, SaveData(coins=9))
            self.assertEqual(read(p).coins, 9)
            with open(p, "w") as f:
                f.write("{not json")
            self.assertEqual(read(p).coins, 0)
            self.assertTrue(os.path.exists(p + ".corrupt"))
            self.assertEqual(read(os.path.join(tmp, "missing.json")).coins, 0)


if __name__ == "__main__":
    unittest.main()

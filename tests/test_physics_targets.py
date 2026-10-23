"""Paper-check of docs/07 targets with the real Oar (headless; NOT an UPBGE validation)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rr.core.oar import Oar  # noqa: E402

MASS, YAW_I, C_FWD, C_YAW = 300.0, 400.0, 90.0, 250.0


def simulate(oars, seconds):
    v = w = th = t = 0.0
    dt = 1 / 60
    log = []
    while t < seconds:
        thrust = torque = 0.0
        for o in oars:
            out = o.update(dt, True)
            thrust += out.thrust
            torque += out.torque_z
        v += (thrust - C_FWD * abs(v) * v) / MASS * dt
        w += (torque - C_YAW * w) / YAW_I * dt
        th += w * dt
        t += dt
        log.append((t, v, math.degrees(th)))
    return log


class PhysicsTargets(unittest.TestCase):
    def test_ph03_both_oars_reach_speed_and_go_straight(self):
        log = simulate([Oar(1), Oar(-1)], 10.0)
        first = next(t for t, v, _ in log if v >= 2.0)
        self.assertLessEqual(first, 6.0)
        self.assertGreaterEqual(log[-1][1], 2.0)
        self.assertAlmostEqual(log[-1][2], 0.0, places=6)

    def test_ph04_single_oar_turn(self):
        log = simulate([Oar(1)], 5.0)
        self.assertTrue(90.0 <= log[-1][2] <= 200.0, log[-1][2])


if __name__ == "__main__":
    unittest.main()

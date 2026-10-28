"""Gameplay acceptance tests independent of UPBGE."""
import math
import unittest

from rr.core.prototype import Prototype, PrototypeConfig, controls, forces


class PrototypeTests(unittest.TestCase):
    def test_menu_finish_restart_and_menu(self):
        game = Prototype(PrototypeConfig())
        self.assertEqual(game.mode, "menu")
        game.advance(1, 999)
        self.assertEqual(game.mode, "menu")
        self.assertTrue(game.command("start"))
        game.advance(2, game.cfg.finish_y)
        self.assertEqual(game.mode, "complete")
        self.assertEqual(game.elapsed, 2)
        self.assertTrue(game.command("restart"))
        self.assertEqual((game.mode, game.hull, game.elapsed), ("playing", 5, 0))
        game.command("menu")
        self.assertEqual(game.mode, "menu")

    def test_pause_freezes_time_and_progress(self):
        game = Prototype(PrototypeConfig())
        game.command("start")
        game.command("pause")
        game.advance(3, 999)
        self.assertEqual((game.mode, game.elapsed), ("paused", 0))
        game.command("pause")
        self.assertEqual(game.mode, "playing")

    def test_damage_cooldown_and_forgiving_respawn(self):
        game = Prototype(PrototypeConfig())
        game.command("start")
        self.assertEqual(game.impact(4), 2)
        self.assertEqual(game.impact(4), 0)
        game.advance(1, 10)
        game.impact(4)
        game.advance(1, 10)
        game.impact(4)
        self.assertTrue(game.respawn_pending)
        game.respawned()
        self.assertEqual(game.hull, 5)
        self.assertEqual(game.mode, "playing")

    def test_controls_share_keyboard_and_reverse(self):
        self.assertEqual(controls({"A", "RIGHT", "S"}), (True, True, -1))
        self.assertEqual(controls(set()), (False, False, 1))

    def test_forces_float_bound_and_flow_direction(self):
        cfg = PrototypeConfig()
        force, torque = forces(cfg, 0.31, (0, 0, 0), 0, 0, 0, 0, 0)
        self.assertGreater(force[1], 0)
        self.assertAlmostEqual(force[2], cfg.mass * 9.81, delta=100)
        for velocity in ((100, -100, -100), (0, 2, 0)):
            force, torque = forces(cfg, -100, velocity, 0.7, 20, 700, 350, 5)
            self.assertLessEqual(math.sqrt(sum(v*v for v in force)), cfg.max_force + 1e-6)
            self.assertLessEqual(abs(torque), cfg.max_torque)


if __name__ == "__main__":
    unittest.main()

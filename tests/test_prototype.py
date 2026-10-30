"""Gameplay acceptance tests independent of UPBGE."""
import math
import unittest

from rr.core.prototype import (
    Prototype,
    PrototypeConfig,
    controls,
    forces,
    frame_forces,
    heave,
)


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

    def test_heave_is_the_same_spring_the_playing_path_uses(self):
        cfg = PrototypeConfig()
        velocity = (0.3, -1.0, 0.0)   # below the global force cap, so no scaling
        self.assertEqual(heave(cfg, 0.2, velocity[2], 1.3), forces(cfg, 0.2, velocity, 0, 0, 0, 0, 1.3)[0][2])
        self.assertGreater(heave(cfg, 0.0, 0.0, 0.0), cfg.mass * 9.81)

    def test_heave_runs_in_every_mode_and_thrust_only_while_playing(self):
        """Bullet keeps simulating in menu/paused/complete, so heave must not stop."""
        cfg = PrototypeConfig()
        idle = (0.0, 0.0, 0.0)
        for mode in ("menu", "paused", "complete"):
            world, torque = frame_forces(cfg, mode, 0.31, idle, 0.0, 0.0, 350.0, 350.0, 0.0)
            self.assertAlmostEqual(world[2], cfg.mass * 9.81, delta=100, msg=mode)
            self.assertEqual((world[0], world[1], torque), (0.0, 0.0, 0.0), mode)
        world, torque = frame_forces(cfg, "playing", 0.31, idle, 0.0, 0.0, 350.0, 350.0, 0.0)
        self.assertGreater(world[1], 350.0)   # thrust on top of the current drag
        self.assertGreater(torque, 0.0)

    def test_menu_idle_does_not_free_fall(self):
        """Regression: the raft used to leave the surface in menu/paused/complete.

        Only gravity and the mode-aware force act here, integrated at 60 Hz for
        8 s of menu time the way Bullet would. Measured in UPBGE before the fix:
        z fell from 0.314 to -352.8 m in exactly this window.
        """
        cfg = PrototypeConfig()
        rest = cfg.raft_height / 2.0 - cfg.mass * 9.81 / cfg.stiffness
        z, vz, dt, lowest = rest, 0.0, 1.0 / 60.0, rest
        for frame in range(8 * 60):
            fz = frame_forces(cfg, "menu", z, (0.0, 0.0, vz), 0.0, 0.0, 0.0, 0.0,
                              frame * dt)[0][2]
            vz += (fz / cfg.mass - 9.81) * dt
            z += vz * dt
            lowest = min(lowest, z)
        self.assertGreater(lowest, rest - 2.0 * cfg.wave_amplitude)


if __name__ == "__main__":
    unittest.main()

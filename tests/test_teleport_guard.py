"""Teleport settling behavior without a running engine."""
import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))


class TeleportGuardTests(unittest.TestCase):
    def test_two_frames_then_enabled(self):
        from rr.core.prototype import TeleportGuard

        guard = TeleportGuard()
        guard.reset()
        self.assertFalse(guard.step())
        self.assertFalse(guard.step())
        self.assertTrue(guard.step())

    def test_teleport_zeroes_velocities_and_resets_guard(self):
        with patch.dict(sys.modules, {"bge": SimpleNamespace()}):
            entry = importlib.import_module("prototype_entry")
        session = entry.Session.__new__(entry.Session)
        session.body = SimpleNamespace(worldLinearVelocity=(1, 2, 3), worldAngularVelocity=(1, 2, 3))
        session.cfg = entry.PrototypeConfig()
        from rr.core.prototype import TeleportGuard

        session.teleport_guard = TeleportGuard()
        session.place_body(5)
        self.assertEqual(session.body.worldLinearVelocity, (0, 0, 0))
        self.assertEqual(session.body.worldAngularVelocity, (0, 0, 0))
        self.assertFalse(session.teleport_guard.step())

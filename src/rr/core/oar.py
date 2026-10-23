"""Oar stroke state machine: IDLE -> DIP -> PULL -> RECOVER.

side: +1 = right oar, -1 = left oar.
Right oar pulling pushes forward and yaws the raft LEFT (positive torque_z).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .mathx import clamp


class OarPhase(Enum):
    IDLE = "idle"
    DIP = "dip"
    PULL = "pull"
    RECOVER = "recover"


@dataclass(frozen=True)
class OarConfig:
    dip_time: float = 0.15
    ramp_time: float = 0.20
    max_pull_time: float = 0.90
    recover_time: float = 0.25
    max_thrust: float = 350.0   # N
    lever: float = 1.0          # m, lateral offset of oar from raft centreline


@dataclass(frozen=True)
class OarOutput:
    phase: OarPhase
    thrust: float     # N along raft forward (+Y). Negative = back-paddle
    torque_z: float   # N*m about +Z


class Oar:
    def __init__(self, side: int, cfg: OarConfig = OarConfig()) -> None:
        if side not in (-1, 1):
            raise ValueError("side must be -1 (left) or +1 (right)")
        self.side = side
        self.cfg = cfg
        self.phase = OarPhase.IDLE
        self._t = 0.0

    def _go(self, phase: OarPhase) -> None:
        self.phase = phase
        self._t = 0.0

    def update(self, dt: float, pressed: bool, direction: float = 1.0) -> OarOutput:
        """direction: +1 forward stroke, -1 back-paddle (clamped to [-1, 1])."""
        c = self.cfg
        direction = clamp(direction, -1.0, 1.0)
        self._t += dt
        thrust = 0.0
        if self.phase is OarPhase.IDLE:
            if pressed:
                self._go(OarPhase.DIP)
        elif self.phase is OarPhase.DIP:
            if not pressed:
                self._go(OarPhase.RECOVER)
            elif self._t >= c.dip_time:
                self._go(OarPhase.PULL)
        elif self.phase is OarPhase.PULL:
            if not pressed or self._t >= c.max_pull_time:
                self._go(OarPhase.RECOVER)
            else:
                ramp = clamp(self._t / c.ramp_time, 0.0, 1.0) if c.ramp_time > 0 else 1.0
                thrust = c.max_thrust * ramp * direction
        elif self.phase is OarPhase.RECOVER:
            if self._t >= c.recover_time:
                self._go(OarPhase.IDLE)
        return OarOutput(self.phase, thrust, self.side * c.lever * thrust)

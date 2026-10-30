"""Catalna slice rules and force calculation. No engine dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, cos, sin, sqrt


@dataclass(frozen=True)
class PrototypeConfig:
    mass: float = 300.0
    raft_width: float = 2.428734742079433
    raft_length: float = 4.8
    raft_height: float = 0.8733232985180094
    flow_speed: float = 2.0
    bank_x: float = 11.0
    finish_y: float = 180.0
    start_y: float = 4.0
    stiffness: float = 24000.0
    damping: float = 2700.0
    forward_drag: float = 90.0
    lateral_drag: float = 400.0
    yaw_drag: float = 500.0
    max_force: float = 9000.0
    max_torque: float = 2000.0
    max_speed: float = 12.0
    max_spin: float = 3.0
    wave_amplitude: float = 0.025
    wave_frequency: float = 1.5
    impact_cooldown: float = 0.8
    max_hull: int = 5


def controls(keys: set[str]) -> tuple[bool, bool, int]:
    """Both keyboard layouts drive the same pair of paddles (solo/shared 2P)."""
    return bool(keys & {"A", "LEFT"}), bool(keys & {"D", "RIGHT"}), (
        -1 if keys & {"S", "DOWN"} else 1)


def heave(cfg, z, vz, time):
    """Upward spring-damper force of the equivalent six-sample hull.

    Mode-independent: Bullet integrates gravity in menu, pause and results just
    as it does while playing, so this force is needed in every lifecycle mode
    (`frame_forces` decides that). One heave spring replaces the six samples.
    """
    water = cfg.wave_amplitude * sin(time * cfg.wave_frequency)
    depth = water - (z - cfg.raft_height / 2)
    return max(0.0, min(cfg.max_force, cfg.stiffness * depth - cfg.damping * vz))


def forces(cfg, z, velocity, yaw, spin, thrust, paddle_torque, time):
    """World force + Z torque; Bullet supplies integration and contacts.

    The slice locks roll/pitch; one equivalent six-sample spring provides heave.
    Visual water uses this same spatially uniform low-amplitude wave.
    """
    c, s = cos(yaw), sin(yaw)
    vx, vy, vz = velocity
    local_x = c * vx + s * (vy - cfg.flow_speed)
    local_y = -s * vx + c * (vy - cfg.flow_speed)
    fx = -cfg.lateral_drag * abs(local_x) * local_x
    fy = -cfg.forward_drag * abs(local_y) * local_y + thrust
    fz = heave(cfg, z, vz, time)
    world = (c * fx - s * fy, s * fx + c * fy, fz)
    magnitude = sqrt(sum(value * value for value in world))
    scale = min(1, cfg.max_force / max(magnitude, 1))
    torque = max(-cfg.max_torque, min(cfg.max_torque, paddle_torque - cfg.yaw_drag * spin))
    return tuple(value * scale for value in world), torque


def frame_forces(cfg, mode, z, velocity, yaw, spin, thrust, paddle_torque, time):
    """Mode-aware force step: heave everywhere, thrust and steering only playing.

    Menu, pause and results still simulate the body, so dropping heave there lets
    gravity win and the raft leaves the surface. Measured in UPBGE before this
    split: z fell from 0.314 m to -352.8 m during an 8 s menu idle, while the
    scripted smoke (playing from frame 1) floated at 0.2887..0.3393 m and passed.
    """
    if mode == "playing":
        return forces(cfg, z, velocity, yaw, spin, thrust, paddle_torque, time)
    return (0.0, 0.0, heave(cfg, z, velocity[2], time)), 0.0


class TeleportGuard:
    """Suppress forces for two physics frames following a teleport."""

    def __init__(self) -> None:
        self.remaining = 0

    def reset(self) -> None:
        self.remaining = 2

    def step(self) -> bool:
        """Return whether forces are enabled and consume one frame."""
        if self.remaining:
            self.remaining -= 1
            return False
        return True


class Prototype:
    """Menu/playing/pause/results lifecycle, progress and forgiving damage."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.mode = "menu"
        self.elapsed = 0.0
        self.progress = 0.0
        self.hull = cfg.max_hull
        self.cooldown = 0.0
        self.hits = 0
        self.respawn_pending = False
        self.checkpoint_y = cfg.start_y

    def command(self, action):
        """Return True when the engine body must reset."""
        if action in ("start", "restart"):
            self.__init__(self.cfg)
            self.mode = "playing"
            return True
        if action == "menu":
            self.mode = "menu"
        elif action == "pause" and self.mode in ("playing", "paused"):
            self.mode = "paused" if self.mode == "playing" else "playing"
        return False

    def advance(self, dt, y):
        if self.mode != "playing":
            return
        self.elapsed += dt
        self.cooldown = max(0, self.cooldown - dt)
        self.progress = max(0, min(1, (y - self.cfg.start_y) / (self.cfg.finish_y - self.cfg.start_y)))
        if y > self.cfg.finish_y / 2 and self.checkpoint_y == self.cfg.start_y:
            self.checkpoint_y = self.cfg.finish_y / 2 + 4
            self.hull = self.cfg.max_hull
        if y >= self.cfg.finish_y:
            self.mode = "complete"

    def impact(self, speed):
        if self.mode != "playing" or self.cooldown > 0:
            return 0
        self.hits += 1
        self.cooldown = self.cfg.impact_cooldown
        damage = min(2, max(0, ceil((speed - 1.5) / 1.2)))
        self.hull = max(0, self.hull - damage)
        self.respawn_pending = self.hull == 0
        return damage

    def respawned(self):
        self.respawn_pending = False
        self.hull = self.cfg.max_hull
        self.cooldown = 1.5


def hud_text(game, speed):
    """Single-line status readout. Pure formatting so it is testable without UPBGE."""
    hull = "#" * game.hull + "." * (game.cfg.max_hull - game.hull)
    return (f"{game.mode.upper()}   hull [{hull}]   {game.progress * 100:3.0f}%"
            f"   {game.elapsed:5.1f}s   {speed:4.1f} m/s   bumps {game.hits}")


def prompt_text(game):
    """Centred prompt for the non-playing modes; empty while the slice is running."""
    if game.mode == "menu":
        return ("RIVER RASCALS - Catalna slice\n"
                "ENTER or click to start\n"
                "A / LEFT and D / RIGHT paddle, S reverse\n"
                "P pause, ESC menu, Q quit")
    if game.mode == "paused":
        return "PAUSED\nP resume, ESC menu, Q quit"
    if game.mode == "complete":
        return (f"FINISH in {game.elapsed:.1f}s with {game.hits} bumps\n"
                "ENTER or click to run again\n"
                "ESC menu, Q quit")
    return ""

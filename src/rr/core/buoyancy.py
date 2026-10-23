"""Spring-damper buoyancy and quadratic drag (pure math)."""
from __future__ import annotations

from dataclasses import dataclass

from .mathx import Vec3, clamp, length, mul


@dataclass(frozen=True)
class BuoyancyConfig:
    stiffness: float = 4000.0   # N per metre of submersion, per sample point
    damping: float = 450.0      # N*s/m, per sample point
    max_force: float = 1500.0   # N, clamp per sample point


def buoyancy_force(sample_z: float, water_z: float, vertical_speed: float,
                   cfg: BuoyancyConfig = BuoyancyConfig()) -> float:
    """Upward force (>= 0) for one sample point. Water never pulls down."""
    depth = water_z - sample_z
    if depth <= 0.0:
        return 0.0
    return clamp(cfg.stiffness * depth - cfg.damping * vertical_speed, 0.0, cfg.max_force)


def quadratic_drag(relative_velocity: Vec3, coeff: float) -> Vec3:
    """F = -c * |v| * v"""
    return mul(relative_velocity, -coeff * length(relative_velocity))

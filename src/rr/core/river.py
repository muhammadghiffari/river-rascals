"""River centerline, flow field and progress tracking.

Conventions (see docs/07_PHYSICS_SPEC.md):
  * Blender/UPBGE axes: +X right, +Y forward, +Z up. 1 unit = 1 metre.
  * Flow is evaluated in the XY plane only.
  * lateral > 0 means the point is to the RIGHT of the flow direction.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .mathx import Vec3, clamp, dot, length, mul, normalize, sub


@dataclass(frozen=True)
class RiverSample:
    point: Vec3      # closest point on centerline
    tangent: Vec3    # unit flow direction at that point
    width: float     # full river width at that point
    s: float         # distance along centerline from start (metres)
    lateral: float   # signed offset from centerline (metres)


class River:
    def __init__(
        self,
        points: Sequence[Vec3],
        widths: Sequence[float],
        base_speed: float = 2.0,
        edge_factor: float = 0.35,
    ) -> None:
        if len(points) < 2:
            raise ValueError("River needs at least 2 points")
        if len(points) != len(widths):
            raise ValueError("points and widths must have equal length")
        self.points = [tuple(p) for p in points]
        self.widths = [float(w) for w in widths]
        self.base_speed = float(base_speed)
        self.edge_factor = clamp(edge_factor, 0.0, 1.0)
        self._cum = [0.0]
        for a, b in zip(self.points, self.points[1:], strict=False):
            d = sub(b, a)
            self._cum.append(self._cum[-1] + length((d[0], d[1], 0.0)))
        self.length = self._cum[-1]

    def project(self, p: Vec3) -> RiverSample:
        best = None
        for i in range(len(self.points) - 1):
            a, b = self.points[i], self.points[i + 1]
            ab = (b[0] - a[0], b[1] - a[1], 0.0)
            seg_len2 = ab[0] ** 2 + ab[1] ** 2
            if seg_len2 < 1e-12:
                continue
            ap = (p[0] - a[0], p[1] - a[1], 0.0)
            u = clamp(dot(ap, ab) / seg_len2, 0.0, 1.0)
            cx, cy = a[0] + ab[0] * u, a[1] + ab[1] * u
            d2 = (p[0] - cx) ** 2 + (p[1] - cy) ** 2
            if best is None or d2 < best[0]:
                best = (d2, i, u, cx, cy, ab)
        assert best is not None
        _, i, u, cx, cy, ab = best
        tangent = normalize(ab)
        right = (tangent[1], -tangent[0], 0.0)
        lateral = (p[0] - cx) * right[0] + (p[1] - cy) * right[1]
        width = self.widths[i] + (self.widths[i + 1] - self.widths[i]) * u
        s = self._cum[i] + (self._cum[i + 1] - self._cum[i]) * u
        z = self.points[i][2] + (self.points[i + 1][2] - self.points[i][2]) * u
        return RiverSample((cx, cy, z), tangent, width, s, lateral)

    def flow_at(self, p: Vec3) -> Vec3:
        """Water velocity at p. Fastest mid-river, slower near banks, zero outside."""
        smp = self.project(p)
        half = smp.width * 0.5
        if half <= 0:
            return (0.0, 0.0, 0.0)
        r = abs(smp.lateral) / half
        if r >= 1.0:
            return (0.0, 0.0, 0.0)
        mult = 1.0 - (1.0 - self.edge_factor) * r * r
        return mul(smp.tangent, self.base_speed * mult)

    def progress(self, p: Vec3) -> float:
        """Normalised progress 0..1 along the river."""
        return clamp(self.project(p).s / self.length, 0.0, 1.0) if self.length > 0 else 0.0

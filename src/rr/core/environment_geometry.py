"""Original deterministic environment meshes, metres, +Y flow, +Z up.

Palette indices are per face; river UV V is cumulative centreline distance.
Sway is normalized height, consumed by a separately verified runtime shader.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, isfinite, pi, sin

Vec3 = tuple[float, float, float]
PALETTE = (
    "3FB8AF", "1F6F8B", "F4FBFF", "B07A4A", "E0C48A", "2F7D4F", "6FAF5A", "8B8F99",
    "FF6F59", "FFC93C", "8A5A3C", "C28B5A", "5C4033", "D9B38C", "FFF4DC", "2D2A32",
)


def palette_uv(index: int) -> tuple[float, float]:
    """Canonical P0 vertical-stripe UV, shared with the props asset contract."""
    if index not in range(16):
        raise ValueError("palette index must be in 0..15")
    return ((index + .5) / 16, .5)


@dataclass
class Mesh:
    """Engine-independent indexed polygon mesh and authoring attributes."""

    vertices: list[Vec3] = field(default_factory=list)
    faces: list[tuple[int, ...]] = field(default_factory=list)
    colors: list[int] = field(default_factory=list)
    sway: list[float] = field(default_factory=list)
    foam: list[int] = field(default_factory=list)
    uv: list[tuple[float, float]] = field(default_factory=list)
    length: float = 0

    @property
    def triangles(self) -> int:
        return sum(len(face) - 2 for face in self.faces)

    def face(self, indices: tuple[int, ...], color: int) -> None:
        self.faces.append(indices)
        self.colors.append(color)


def _rings(mesh: Mesh, rings: list[tuple[float, float]], sides: int,
           color: int, offset: Vec3 = (0, 0, 0), phase: float = 0) -> None:
    """Closed faceted lathe; positive radii avoid degenerate tip polygons."""
    start = len(mesh.vertices)
    ox, oy, oz = offset
    for radius, height in rings:
        for i in range(sides):
            angle = 2 * pi * i / sides + phase
            mesh.vertices.append((ox + radius * cos(angle), oy + radius * sin(angle), oz + height))
    mesh.face(tuple(start + i for i in reversed(range(sides))), color)
    for row in range(len(rings) - 1):
        for i in range(sides):
            a, b = start + row * sides + i, start + row * sides + (i + 1) % sides
            mesh.face((a, b, b + sides, a + sides), color)
    mesh.face(tuple(start + (len(rings) - 1) * sides + i for i in range(sides)), color)


def _variant(value: int, count: int) -> None:
    if value not in range(count):
        raise ValueError(f"variant must be in 0..{count - 1}")


def pine(variant: int = 0, lod: bool = False) -> Mesh:
    """Three layered, tapered pine silhouettes with matched LOD heights."""
    _variant(variant, 3)
    mesh = Mesh()
    height = (4.8, 5.6, 4.1)[variant]
    width = (1.25, 1.05, 1.45)[variant]
    sides = 6 if lod else 10
    _rings(mesh, [(.18, 0), (.13, height * .8)], sides, 3)
    for tier in range(3):
        base = height * (.2 + tier * .22)
        radius = width * (1 - tier * .24)
        rings = [(radius, base), (.035, height * (.61 + tier * .195))]
        if not lod:
            rings.insert(1, (radius * .8, base + .25))
        _rings(mesh, rings, sides, 5 + tier % 2, phase=tier * .27)
    top = max(v[2] for v in mesh.vertices)
    mesh.sway = [(v[2] / top) ** 2 for v in mesh.vertices]
    return mesh


def bush(variant: int = 0) -> Mesh:
    """Rounded clumps with broad asymmetric silhouettes, no alpha cards."""
    _variant(variant, 3)
    mesh = Mesh()
    for i in range(3):
        radius = (.52, .64, .45)[(i + variant) % 3]
        _rings(mesh, [(radius * .45, 0), (radius, .35), (radius * .65, .8), (.08, 1.0)],
               6, 5 + i % 2, ((i - 1) * .5, .15 * (i % 2), 0), variant * .3)
    return mesh


def bank(variant: int = 0) -> Mesh:
    """Closed 4/8m tile: sand shore at x=0, turf inland; 0.3m minimum depth.

Ends have identical cross sections for seamless Y tiling. FoamAnchor indices
follow the shoreline; bottom at z=0 gives a base pivot (place at z=-0.3).
"""
    _variant(variant, 4)
    length = 4. if variant < 2 else 8.
    width = 4.
    mesh = Mesh(length=length)
    for row in range(9):
        y = length * row / 8
        bend = 0 if row in (0, 8) else (0, .25, -.25, .4)[variant] * sin(pi * row / 8) ** 2
        for x, z in ((0, .3), (.65, .42), (1.4, .65), (width, .65)):
            mesh.vertices.append((x + (bend if x < width else 0), y, z))
        mesh.foam.append(row * 4)
    for row in range(8):
        for col in range(3):
            a = row * 4 + col
            mesh.face((a, a + 1, a + 5, a + 4), 4 if col == 0 else 6)
    boundary = [0, 1, 2, 3] + [r * 4 + 3 for r in range(1, 9)]
    boundary += [34, 33, 32] + [r * 4 for r in reversed(range(1, 8))]
    bottom = []
    for index in boundary:
        x, y, _ = mesh.vertices[index]
        bottom.append(len(mesh.vertices))
        mesh.vertices.append((x, y, 0))
    for i, a in enumerate(boundary):
        j = (i + 1) % len(boundary)
        mesh.face((boundary[j], a, bottom[i], bottom[j]), 3)
    # Bottom fan retains collinear boundary vertices and avoids ngon triangulation ambiguity.
    center = len(mesh.vertices)
    mesh.vertices.append((width / 2, length / 2, 0))
    for i, a in enumerate(bottom):
        mesh.face((bottom[(i + 1) % len(bottom)], a, center), 3)
    return mesh


def river_strip(points: tuple[tuple[float, float], ...], width: float = 8.,
                across: int = 8) -> Mesh:
    """Ribbon sampled along supplied centreline; no water shader or physics."""
    if len(points) < 2 or across < 2 or not isfinite(width) or width <= 0:
        raise ValueError("need two points, positive width and at least two cross segments")
    if any(not isfinite(c) for point in points for c in point):
        raise ValueError("non-finite centreline")
    if 2 * across * (len(points) - 1) > 3000:
        raise ValueError("river triangle budget exceeded")
    mesh = Mesh()
    distance = 0.
    for row, (x, y) in enumerate(points):
        if row:
            segment = hypot(x - points[row - 1][0], y - points[row - 1][1])
            if segment <= 1e-8:
                raise ValueError("duplicate centreline point")
            distance += segment
        before, after = points[max(row - 1, 0)], points[min(row + 1, len(points) - 1)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        norm = hypot(dx, dy)
        if norm <= 1e-8:
            raise ValueError("reversing centreline tangent")
        for col in range(across + 1):
            lateral = width * (col / across - .5)
            mesh.vertices.append((x + dy / norm * lateral, y - dx / norm * lateral, 0))
            mesh.uv.append((col / across, distance))
        if row:
            for col in range(across):
                a = (row - 1) * (across + 1) + col
                mesh.face((a, a + 1, a + across + 2, a + across + 1), 0)
    mesh.length = distance
    return mesh

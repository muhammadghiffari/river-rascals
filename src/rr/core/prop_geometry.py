"""Original P0 prop meshes; metres, +Y forward, palette indices per face.

No engine dependencies. All components share their asset's base-centre origin.
"""
from dataclasses import dataclass, field
from math import cos, pi, sin

PALETTE = ("3FB8AF", "1F6F8B", "F4FBFF", "B07A4A", "E0C48A", "2F7D4F",
           "6FAF5A", "8B8F99", "FF6F59", "FFC93C", "8A5A3C", "C28B5A",
           "5C4033", "D9B38C", "FFF4DC", "2D2A32")
# Local authoring swatches (wood, rope, pine, moss, rock, coral, gold, foam,
# teal, ink, fur, cream, water, tan, dark fur, pale fur) to the shared atlas.
_SHARED_INDEX = (3, 4, 5, 6, 7, 8, 9, 2, 0, 15, 10, 14, 1, 11, 12, 13)


@dataclass
class Mesh:
    name: str
    vertices: list
    faces: list
    colors: list
    collider: bool = False
    moss: bool = False

    @property
    def tris(self):
        return sum(len(f) - 2 for f in self.faces)


@dataclass
class Prop:
    name: str
    budget: int
    meshes: list = field(default_factory=list)
    collision: str = "NONE"
    clearance: float = 0
    bones: list = field(default_factory=list)
    sockets: list = field(default_factory=list)


def lathe(name, rings, sides, color, centre=(0, 0, 0), axis="Z", scale=(1, 1, 1)):
    """Closed ring surface with outward winding (nonzero ring radii)."""
    vertices = []
    for height, radius in rings:
        for i in range(sides):
            p = (radius*cos(2*pi*i/sides), radius*sin(2*pi*i/sides), height)
            if axis == "X":
                p = (p[2], p[0], p[1])
            elif axis == "Y":
                p = (p[1], p[2], p[0])
            vertices.append(tuple(centre[j] + p[j]*scale[j] for j in range(3)))
    faces = [tuple(reversed(range(sides)))]
    for row in range(len(rings)-1):
        for i in range(sides):
            a, b = row*sides+i, row*sides+(i+1) % sides
            faces.append((a, b, b+sides, a+sides))
    faces.append(tuple(range((len(rings)-1)*sides, len(rings)*sides)))
    return Mesh(name, vertices, faces, [color]*len(faces))


def prism(name, outline, depth, color, y=0):
    """Extrude a counter-clockwise X/Z outline toward Y."""
    n = len(outline)
    vertices = [(x, y+d, z) for d in (-depth/2, depth/2) for x, z in outline]
    faces = [tuple(range(n)), tuple(reversed(range(n, 2*n)))]
    faces += [(i, i+n, (i+1) % n+n, (i+1) % n) for i in range(n)]
    return Mesh(name, vertices, faces, [color]*len(faces))


def box(name, x, z, width, height, depth, color):
    return prism(name, [(x-width/2, z), (x+width/2, z),
                        (x+width/2, z+height), (x-width/2, z+height)], depth, color)


def finish(prop):
    visible = [v for m in prop.meshes if not m.collider for v in m.vertices]
    offset = [(min(v[i] for v in visible)+max(v[i] for v in visible))/2
              for i in (0, 1)] + [min(v[2] for v in visible)]
    def shift(v):
        return tuple(v[i]-offset[i] for i in range(3))
    for mesh in prop.meshes:
        mesh.name = prop.name + "_" + mesh.name.replace("-", "N").replace(".", "_")
        mesh.vertices = [shift(v) for v in mesh.vertices]
        mesh.colors = [_SHARED_INDEX[c] for c in mesh.colors]
    prop.bones = [(name, shift(head), shift(tail)) for name, head, tail in prop.bones]
    prop.sockets = [(name.replace("-", "N"), shift(pos)) for name, pos in prop.sockets]
    assert sum(m.tris for m in prop.meshes if not m.collider) <= prop.budget
    return prop


def coin():
    p = Prop("PR_Coin_01", 200)
    p.meshes.append(lathe("Rim", [(-.075, .32), (-.045, .36), (.045, .36),
                                  (.075, .32)], 12, 6, axis="Y", centre=(0, 0, .36)))
    for side in (-1, 1):
        p.meshes.append(prism(f"AcornNut{side}", [(-.12, .38), (-.09, .25),
                             (0, .19), (.09, .25), (.12, .38)], .025, 1, side*.085))
        p.meshes.append(prism(f"AcornCap{side}", [(-.14, .38), (.14, .38),
                             (.1, .46), (-.1, .46)], .025, 10, side*.085))
        p.meshes.append(prism(f"AcornStem{side}", [(-.02, .46), (.02, .46),
                             (.04, .52), (0, .52)], .025, 10, side*.085))
    return finish(p)


def fish():
    p = Prop("PR_GoldenFish_01", 400)
    p.meshes.append(lathe("Body", [(-.48, .06), (-.25, .25), (.12, .30),
                                  (.43, .16), (.50, .045)], 10, 6, axis="X",
                          centre=(0, 0, .4), scale=(1, .55, 1)))
    for name, outline, color in [
        ("Tail", [(-.45, .40), (-.80, .16), (-.72, .69)], 5),
        ("Dorsal", [(-.2, .62), (.12, .88), (.28, .62)], 1),
        ("Fin", [(-.1, .31), (.23, .15), (.17, .43)], 1),
    ]:
        p.meshes.append(prism(name, outline, .08, color))
    for side in (-1, 1):
        p.meshes.append(lathe(f"Eye{side}", [(-.01, .055), (.01, .055)], 8, 9,
                              centre=(.31, side*.13, .48), axis="Y"))
    return finish(p)


def buoy(variant):
    p = Prop(f"PR_Buoy_{variant:02}", 300, collision="CONVEX_HULL")
    rings = [(0, .18), (.12, .40), (.40, .44), (.65, .32), (.95, .16)]
    body = lathe("Body", rings, 10, 5)
    for i in range(11, 21):
        body.colors[i] = 7
    p.meshes.append(body)
    p.meshes.append(lathe("Cap", [(.95, .18), (1.05+.15*(variant-1), .09)], 8, 5))
    # Two interlocking rectangular hollow links; 48 triangles each.
    for link in range(2):
        z = -.22*(link+1)
        for k, (x, zz, w, h) in enumerate([(-.09, z, .05, .24), (.09, z, .05, .24),
                                         (0, z, .18, .05), (0, z+.19, .18, .05)]):
            m = box(f"Chain{link}_{k}", x, zz, w, h, .05, 9)
            if link:
                m.vertices = [(y, x, z) for x, y, z in m.vertices]
            p.meshes.append(m)
    col = lathe("COL", rings, 8, 0)
    col.collider = True
    p.meshes.append(col)
    return finish(p)


def log(variant):
    length, radius = ((1.8, .25), (2.8, .34), (3.8, .43))[variant-1]
    p = Prop(f"PR_Log_{variant:02}", 600, collision="CAPSULE")
    p.meshes.append(lathe("Bark", [(-length/2, radius*.85), (-length*.42, radius),
                                  (length*.42, radius), (length/2, radius*.85)],
                          12, 0, axis="X", centre=(0, 0, radius)))
    for end in (-1, 1):
        for ring, factor in enumerate((.80, .55, .28)):
            x = end*(length/2+.003*(ring+1))
            p.meshes.append(lathe(f"End{end}_{ring}", [(x, radius*factor),
                                  (x+end*.002, radius*factor)], 12, (1, 10, 1)[ring],
                                  axis="X", centre=(0, 0, radius)))
    for i in (-1, 1):
        p.meshes.append(lathe(f"Knot{i}", [(radius*.75, .12), (radius+ .16, .07)],
                              8, 10, centre=(i*length*.22, 0, radius)))
    r = radius
    col = lathe("COL", [(-length/2, .001), (-length/2+r*.3, r*.707),
                         (-length/2+r, r), (length/2-r, r),
                         (length/2-r*.3, r*.707), (length/2, .001)],
                10, 0, axis="X", centre=(0, 0, radius))
    col.collider = True
    p.meshes.append(col)
    return finish(p)


def rock(size, variant):
    radius, budget = {"Small": (.55, 300), "Med": (1.0, 600), "Large": (1.65, 1200)}[size]
    suffix = "_Own" if size == "Large" else ""
    p = Prop(f"PR_Rock{size}_{variant:02}{suffix}", budget, collision="CONVEX_HULL")
    rings = [(0, .72), (.30, 1), (.85, .84), (1.25, .33)]
    m = lathe("Stone", rings, 9+variant, 4,
              scale=(radius*(1+.07*variant), radius, radius*(.7+.1*variant)))
    # Affine shear preserves convexity while giving each silhouette a lean.
    m.vertices = [(x+.12*variant*z, y+.08*z, z) for x, y, z in m.vertices]
    m.moss = size == "Large"
    p.meshes.append(m)
    p.meshes.append(Mesh("COL", list(m.vertices), list(m.faces), list(m.colors), True))
    return finish(p)


def sign(variant):
    p = Prop(f"PR_Signpost_{variant:02}", 300)
    p.meshes.append(lathe("Post", [(0, .12), (1.8, .10)], 8, 0))
    outline = [(-.65, 1.2), (.28, 1.2), (.28, 1.06), (.72, 1.43),
               (.28, 1.8), (.28, 1.65), (-.65, 1.65)]
    if variant == 2:
        outline = [(-x, z) for x, z in reversed(outline)]
    if variant == 3:
        outline = [(z-1.43, x+1.4) for x, z in reversed(outline)]
    p.meshes.append(prism("Arrow", outline, .18, 1, -.12))
    return finish(p)


def arch(finish_gate=False):
    clearance = 10 if finish_gate else 8
    h = 5 if finish_gate else 4
    p = Prop("PR_FinishGate_01" if finish_gate else "PR_CheckpointArch_01",
             2000 if finish_gate else 1500, clearance=clearance)
    for side in (-1, 1):
        x = side*(clearance/2+.25)
        p.meshes.append(box(f"Post{side}", x, 0, .5, h, .6, 0))
        p.meshes.append(box(f"PostFoot{side}", x, 0, .5, .35, .8, 1))
        for z in (.65, h-.6):
            p.meshes.append(box(f"PostBand{side}_{z}", x, z, .5, .16, .65, 1))
    p.meshes.append(box("Crossbeam", 0, h-.2, clearance+1.3, .4, .5, 0))
    vertices, faces = [], []
    segments = 16
    for i in range(segments+1):
        x = -clearance/2 + clearance*i/segments
        sag = .25*sin(pi*i/segments)
        vertices.extend([(x, -.32, h-.32-sag), (x, -.32, h-1.15-sag)])
    for i in range(segments):
        faces.append((2*i, 2*i+1, 2*i+3, 2*i+2))
    p.meshes.append(Mesh("Banner", vertices, faces,
                         [5 if not finish_gate else (7 if i % 2 else 9)
                          for i in range(segments)]))
    for i in range(4):
        x = -clearance/2 + clearance*i/4
        p.bones.append((f"Flutter{i}", (x, -.32, h-.32),
                        (x+clearance/4, -.32, h-.32)))
    if finish_gate:
        p.sockets = [(f"Socket_Confetti_{side}", (side*(clearance/2+.25), 0, h+.4))
                     for side in (-1, 1)]
    return finish(p)


def build_props():
    return ([coin(), fish()] + [buoy(i) for i in range(1, 3)]
            + [log(i) for i in range(1, 4)]
            + [rock(size, i) for size in ("Small", "Med", "Large") for i in range(1, 4)]
            + [sign(i) for i in range(1, 4)] + [arch(), arch(True)])

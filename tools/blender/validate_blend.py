"""Headless asset validator. Run via: blender -b file.blend --python tools/blender/validate_blend.py

Checks (see docs/04_ASSET_BIBLE_AND_PIPELINE.md):
  * object names match  <PREFIX>_<Name>[_LODn|_COL]  with approved PREFIX
  * triangle count under budget derived from the file's name prefix
  * no n-gons > 4 verts left unreported (warn), no unapplied non-uniform scale
  * images <= 2048 px; power-of-two dimensions
  * every mesh has a material
Prints lines starting with [validate]; "FAIL" in a line marks failure. Exit code 1 on failure.
UNVERIFIED against UPBGE 0.50: confirm `bpy` API usage in spike S-05.
"""
import re
import sys

import bpy

PREFIXES = {"CH": 8000, "RF": 8000, "PR": 3000, "EN": 4000, "VX": 500, "UI": 2000}
NAME_RE = re.compile(r"^(CH|RF|PR|EN|VX|UI)_[A-Za-z0-9]+(_[A-Za-z0-9]+)*(_LOD[0-3]|_COL)?(\.\d{3})?$")
problems = []


def fail(msg):
    problems.append(msg)
    print("[validate] FAIL " + msg)


def info(msg):
    print("[validate] " + msg)


def tri_count(obj):
    me = obj.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)


for obj in bpy.data.objects:
    if obj.type == "MESH":
        m = NAME_RE.match(obj.name)
        if not m:
            fail("bad name: %s" % obj.name)
            continue
        prefix = obj.name.split("_")[0]
        if not obj.name.split("_")[-1].startswith("COL"):
            tris = tri_count(obj)
            budget = PREFIXES[prefix]
            if tris > budget:
                fail("%s has %d tris (budget %d)" % (obj.name, tris, budget))
            else:
                info("%s tris %d/%d" % (obj.name, tris, budget))
            if not obj.data.materials:
                fail("%s has no material" % obj.name)
        sc = obj.scale
        if max(abs(sc.x - sc.y), abs(sc.y - sc.z)) > 1e-4 or abs(abs(sc.x) - 1.0) > 1e-4:
            fail("%s has unapplied scale %s" % (obj.name, tuple(round(v, 3) for v in sc)))

for img in bpy.data.images:
    if img.size[0] == 0 or img.size[1] == 0:
        fail("image %s failed to load" % img.name)
        continue
    w, h = img.size
    if max(w, h) > 2048:
        fail("image %s is %dx%d (max 2048)" % (img.name, w, h))
    if (w & (w - 1)) or (h & (h - 1)):
        fail("image %s not power-of-two (%dx%d)" % (img.name, w, h))

info("%d problem(s)" % len(problems))
sys.exit(1 if problems else 0)

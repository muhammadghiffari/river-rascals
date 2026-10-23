"""RiverLoader: builds rr.core.river.River from empties named RiverPt.000, RiverPt.001, ...

Authoring contract (docs/07_PHYSICS_SPEC.md):
  * One empty per centerline point, ordered by name.
  * Optional game property "width" (float, metres) on each empty. Default 10.
Stored in bge.logic.globalDict["rr_river"].
"""
from collections import OrderedDict

import bge

from rr.core.river import River


class RiverLoader(bge.types.KX_PythonComponent):
    args = OrderedDict([
        ("Base Speed", 2.0),
        ("Edge Factor", 0.35),
        ("Logic Tic Rate", 60),
        ("Physics Tic Rate", 60),
    ])

    def start(self, args):
        bge.logic.setLogicTicRate(float(args["Logic Tic Rate"]))
        bge.logic.setPhysicsTicRate(float(args["Physics Tic Rate"]))
        pts = sorted((o for o in self.object.scene.objects if o.name.startswith("RiverPt.")),
                     key=lambda o: o.name)
        if len(pts) < 2:
            print("[rr] RiverLoader: need >= 2 RiverPt.* empties")
            return
        points = [tuple(o.worldPosition) for o in pts]
        widths = [float(o["width"]) if "width" in o else 10.0 for o in pts]
        bge.logic.globalDict["rr_river"] = River(
            points, widths, args["Base Speed"], args["Edge Factor"])
        print("[rr] river loaded: %d points, %.1f m" % (len(pts), bge.logic.globalDict["rr_river"].length))

    def update(self):
        pass

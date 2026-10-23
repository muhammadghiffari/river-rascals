"""Raft physics + oar input components.

Scene contract:
  * Raft object: dynamic rigid body, children empties named BuoySample.00 .. BuoySample.05.
  * Axes: +Y forward, +X right, +Z up (matches rr.core).
VERIFY in spike S-02: applyForce/applyTorque accumulation per physics step,
KX_GameObject.getVelocity(point) semantics, tic-rate behaviour.
"""
from collections import OrderedDict

import bge
from mathutils import Vector

from rr.core.buoyancy import BuoyancyConfig, buoyancy_force
from rr.core.mathx import clamp
from rr.core.oar import Oar, OarConfig
from rr.core.waves import wave_height


class RaftPhysics(bge.types.KX_PythonComponent):
    args = OrderedDict([
        ("Water Level", 0.0),
        ("Stiffness", 4000.0),
        ("Damping", 450.0),
        ("Max Force", 1500.0),
        ("Forward Drag", 90.0),
        ("Lateral Drag", 400.0),
        ("Yaw Drag", 250.0),
    ])

    def start(self, args):
        self.cfg = BuoyancyConfig(args["Stiffness"], args["Damping"], args["Max Force"])
        self.water_level = args["Water Level"]
        self.fwd_drag = args["Forward Drag"]
        self.lat_drag = args["Lateral Drag"]
        self.yaw_drag = args["Yaw Drag"]
        self.samples = sorted((c for c in self.object.children if c.name.startswith("BuoySample")),
                              key=lambda c: c.name)
        self.t = 0.0
        if not self.samples:
            print("[rr] RaftPhysics: no BuoySample.* children found")

    def update(self):
        obj = self.object
        dt = 1.0 / bge.logic.getLogicTicRate()
        self.t += dt
        com = obj.worldPosition.copy()
        submerged = 0
        for s in self.samples:
            p = s.worldPosition
            water_z = wave_height(p.x, p.y, self.t, self.water_level)
            vz = obj.getVelocity(p).z
            f = buoyancy_force(p.z, water_z, vz, self.cfg)
            if f > 0.0:
                submerged += 1
                force = Vector((0.0, 0.0, f))
                obj.applyForce(force, False)
                obj.applyTorque((p - com).cross(force), False)
        if submerged == 0:
            return
        # Drag relative to the water (flow-aware).
        river = bge.logic.globalDict.get("rr_river")
        flow = Vector(river.flow_at(tuple(com))) if river else Vector((0.0, 0.0, 0.0))
        rel_world = obj.worldLinearVelocity - flow
        rel = obj.worldOrientation.transposed() @ rel_world   # to local axes
        scale = submerged / max(1, len(self.samples))
        drag = Vector((-self.lat_drag * abs(rel.x) * rel.x,
                       -self.fwd_drag * abs(rel.y) * rel.y,
                       0.0)) * scale
        obj.applyForce(drag, True)
        wz = obj.localAngularVelocity.z
        obj.applyTorque((0.0, 0.0, -self.yaw_drag * wz * scale), True)


class RaftOars(bge.types.KX_PythonComponent):
    """Keyboard prototype: A = left oar, D = right oar, S = back-paddle modifier."""
    args = OrderedDict([("Max Thrust", 350.0), ("Lever", 1.0)])

    def start(self, args):
        cfg = OarConfig(max_thrust=args["Max Thrust"], lever=args["Lever"])
        self.left, self.right = Oar(-1, cfg), Oar(+1, cfg)

    def _active(self, key):
        return bge.logic.keyboard.inputs[key].active

    def update(self):
        dt = 1.0 / bge.logic.getLogicTicRate()
        if bge.logic.globalDict.get("rr_autopaddle"):          # used by smoke test
            left = right = True
            direction = 1.0
        else:
            left, right = self._active(bge.events.AKEY), self._active(bge.events.DKEY)
            direction = -1.0 if self._active(bge.events.SKEY) else 1.0
        total_thrust = total_torque = 0.0
        for oar, pressed in ((self.left, left), (self.right, right)):
            out = oar.update(dt, pressed, direction)
            total_thrust += out.thrust
            total_torque += out.torque_z
        self.object.applyForce((0.0, clamp(total_thrust, -2000, 2000), 0.0), True)
        self.object.applyTorque((0.0, 0.0, total_torque), True)

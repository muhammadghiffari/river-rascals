"""SmokeTest component: scripted run that writes a JSON report and quits.

Enable with env vars:  RR_SMOKE=1  RR_SMOKE_SECONDS=20  RR_SMOKE_OUT=smoke_result.json
Attach to any always-present object (e.g. the raft). Exit status is read from the JSON.
"""
import json
import os
import time
from collections import OrderedDict

import bge


class SmokeTest(bge.types.KX_PythonComponent):
    args = OrderedDict([("Seconds", 20.0)])

    def start(self, args):
        self.enabled = os.environ.get("RR_SMOKE") == "1"
        self.duration = float(os.environ.get("RR_SMOKE_SECONDS", args["Seconds"]))
        self.out = os.environ.get("RR_SMOKE_OUT", "smoke_result.json")
        self.t0 = time.time()
        self.samples = []
        self.next_sample = 1.0
        self.start_pos = tuple(self.object.worldPosition)
        if self.enabled:
            bge.logic.globalDict["rr_autopaddle"] = True
            print("[rr] smoke test started (%.0fs)" % self.duration)

    def update(self):
        if not self.enabled:
            return
        el = time.time() - self.t0
        if el >= self.next_sample:
            self.samples.append(bge.logic.getAverageFrameRate())
            self.next_sample += 1.0
        if el >= self.duration:
            end = tuple(self.object.worldPosition)
            moved = sum((a - b) ** 2 for a, b in zip(end, self.start_pos, strict=True)) ** 0.5
            fps = sorted(self.samples) or [0.0]
            report = {
                "seconds": round(el, 1),
                "fps_avg": round(sum(fps) / len(fps), 1),
                "fps_min": round(fps[0], 1),
                "fps_p5": round(fps[max(0, int(len(fps) * 0.05) - 0)], 1),
                "distance_moved_m": round(moved, 2),
                "ok": moved > 1.0 and fps[0] > 0.0,
            }
            with open(self.out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print("[rr] smoke result:", report)
            bge.logic.endGame()

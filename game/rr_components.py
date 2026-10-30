"""Entry shim for UPBGE Python Components.

In the Blender UI, set each component's module to `rr_components.<ClassName>`, e.g.
  rr_components.RiverLoader, rr_components.RaftPhysics, rr_components.RaftOars, rr_components.SmokeTest
This file must live next to the .blend files so it is importable; it adds ../src to sys.path.
"""
import os
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from rr.glue.bench import BenchRecorder  # noqa: E402,F401
from rr.glue.raft import RaftOars, RaftPhysics  # noqa: E402,F401
from rr.glue.river_flow import RiverLoader  # noqa: E402,F401
from rr.glue.smoke import SmokeTest  # noqa: E402,F401

"""Component-module shim for the benchmark scenes in ``game/bench/``.

UPBGE resolves a Python Component's ``module`` against the directory that holds
the ``.blend``. The benchmark scenes live one level below ``game/``, so they see
this file instead of ``game/rr_components.py``. Rather than duplicating the
components, this shim loads the real module from the parent directory under a
private name and re-exports it.

Keep this file tiny: it exists only so ``rr_components.BenchRecorder`` resolves
for ``game/bench/*.blend``.
"""

import importlib.util
import os
import sys

_GAME_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

_spec = importlib.util.spec_from_file_location(
    "rr_components_game", os.path.join(_GAME_DIR, "rr_components.py")
)
if _spec is None or _spec.loader is None:  # pragma: no cover - broken checkout
    raise ImportError("cannot load game/rr_components.py from %s" % _GAME_DIR)

_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

BenchRecorder = _module.BenchRecorder

__all__ = ["BenchRecorder"]

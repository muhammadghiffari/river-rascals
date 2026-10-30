"""Benchmark report assembly and atomic JSON writing (pure Python).

Kept out of ``rr.glue`` so the report shape and the atomic-write contract can be
unit-tested without UPBGE. Nothing here imports ``bge``/``bpy``.

Missing metadata policy: a value the harness could not observe is ``None`` plus a
note in ``notes``. Nothing is inferred — in particular a requested resolution is
never copied into ``actual_resolution``.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

RENDERER_NOTE = (
    "gpu_renderer is read from the player's GL_RENDERER line by the runner; "
    "the engine exposes only the vendor"
)


def resolution_label(width: Any, height: Any) -> str | None:
    """Return ``"<w>x<h>"`` for two positive ints, else ``None``."""
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return f"{w}x{h}"


def parse_resolution(label: str | None) -> tuple[int, int] | None:
    """Parse ``"1280x720"`` into ``(1280, 720)``; ``None`` if malformed."""
    if not label:
        return None
    text = str(label).strip().lower().replace(" ", "")
    for separator in ("x", "*"):
        if separator in text:
            left, _, right = text.partition(separator)
            try:
                width, height = int(left), int(right)
            except ValueError:
                return None
            if width > 0 and height > 0:
                return width, height
            return None
    return None


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_report(
    *,
    stats: Mapping[str, Any],
    scene_label: str,
    preset: str | None,
    requested_resolution: str | None,
    actual_resolution: str | None,
    duration_s: float,
    warmup_s: float,
    platform: str,
    engine: str | None,
    gpu_vendor: str | None,
    gpu_renderer: str | None = None,
    fps_crosscheck: Mapping[str, Any] | None = None,
    notes: list[str] | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the JSON-ready benchmark report.

    ``ok`` is true only when the run produced measured frames.

    ``fps_crosscheck`` is optional and purely additive: it carries the engine's
    own ``getAverageFrameRate()`` samples (minimum and average) next to — never
    in place of — the frame-interval statistics in ``stats``.
    """
    collected = list(notes or [])
    measured_frames = int(stats.get("frames_measured") or 0)
    ok = measured_frames > 0

    if actual_resolution is None:
        collected.append("actual window size was not observable in-engine")
    if requested_resolution and actual_resolution and requested_resolution != actual_resolution:
        collected.append(
            f"requested {requested_resolution} but the engine reported "
            f"{actual_resolution}; the run is NOT verified at the requested size"
        )
    if gpu_renderer is None:
        collected.append(RENDERER_NOTE)
    if fps_crosscheck is not None and not fps_crosscheck.get("samples"):
        collected.append(
            "fps_crosscheck is empty (getAverageFrameRate() returned no usable samples); "
            "the frame-interval statistics are unaffected"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "scene": scene_label,
        "preset": preset,
        "requested_resolution": requested_resolution,
        "actual_resolution": actual_resolution,
        "resolution_verified": bool(
            requested_resolution and actual_resolution
            and requested_resolution == actual_resolution
        ),
        "duration_s": duration_s,
        "warmup_s": warmup_s,
        "platform": platform,
        "engine": engine,
        "gpu_vendor": gpu_vendor,
        "gpu_renderer": gpu_renderer,
        "fps_crosscheck": dict(fps_crosscheck) if fps_crosscheck is not None else None,
        "stats": dict(stats),
        "captured_at": captured_at or utc_now_iso(),
        "notes": collected,
    }


def write_json_atomic(path: str | os.PathLike[str], payload: Mapping[str, Any]) -> Path:
    """Write ``payload`` as JSON to ``path`` atomically.

    The temporary file lives in the destination directory so ``os.replace`` is a
    same-filesystem rename. The destination is only touched once the complete
    document has been flushed and fsync'd, so a killed player never leaves a
    half-written result behind.
    """
    destination = Path(path).expanduser()
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)

    handle, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, destination)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return destination

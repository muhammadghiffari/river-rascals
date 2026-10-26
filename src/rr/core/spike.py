"""Pure helpers for the S-01 engine spike (no bge/bpy imports).

`rr.glue.spike_probe` reports one status per engine feature the pin decision
needs. These helpers grade a run and render one markdown row for
`docs/reports/S-01_engine_decision.md`, so humans paste printed output instead
of re-typing numbers.
"""
from __future__ import annotations

import math
import statistics

PASS = "pass"
FAIL = "fail"
SKIP = "skip"

# Feature order used by the report matrix. Keep in sync with the probe.
CHECKS = (
    "component",
    "tic_rates",
    "physics",
    "aud_play",
    "aud_volume",
    "aud_3d",
    "filter2d",
    "overlay",
    "play_action",
    "fps",
)


def normalize(status: object) -> str:
    """Map a raw probe status to pass/fail/skip; anything else returns ""."""
    text = str(status).strip().lower()
    return text if text in (PASS, FAIL, SKIP) else ""


def summarize(checks: dict[str, str]) -> dict[str, object]:
    """Grade a probe result set.

    ``ok`` is False when any check failed, was never reported, or reported an
    unknown status, so a truncated or garbled run cannot masquerade as a pass.
    """
    status = {name: normalize(checks.get(name)) for name in CHECKS}
    passed = [name for name in CHECKS if status[name] == PASS]
    failed = [name for name in CHECKS if status[name] == FAIL]
    skipped = [name for name in CHECKS if status[name] == SKIP]
    missing = [name for name in CHECKS if status[name] not in (PASS, FAIL, SKIP)]
    return {
        "ok": not failed and not missing,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "missing": missing,
    }


def _cell(status: object) -> str:
    return {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}.get(normalize(status), "-")


def compute_fps_stats(
    samples: list[tuple[float, float] | float],
    warmup_seconds: float = 1.0,
    min_fps: float = 30.0,
) -> dict[str, object]:
    """Compute FPS statistics ignoring initial warmup and invalid samples.

    samples: list of (elapsed_time, fps_value) tuples, or raw float fps values.
    warmup_seconds: initial duration to discard (default 1.0s).
    min_fps: passing threshold for used sample average (default 30.0).
    """
    raw_n = len(samples)
    norm_samples: list[tuple[float, float]] = []
    for s in samples:
        if isinstance(s, (tuple, list)) and len(s) >= 2:
            norm_samples.append((float(s[0]), float(s[1])))
        elif isinstance(s, (int, float)):
            norm_samples.append((warmup_seconds, float(s)))

    finite_raw = [v for _, v in norm_samples if math.isfinite(v)]
    raw_max = max(finite_raw) if finite_raw else 0.0

    used_values = [
        v for t, v in norm_samples
        if t >= warmup_seconds and math.isfinite(v) and v > 0.0
    ]
    used_n = len(used_values)
    dropped_n = raw_n - used_n

    if used_n == 0:
        return {
            "status": FAIL,
            "avg": 0.0,
            "min": 0.0,
            "median": 0.0,
            "n": 0,
            "raw_n": raw_n,
            "dropped_n": dropped_n,
            "raw_max": round(raw_max, 1),
            "note": "no valid fps samples after %.1fs warmup (raw_n=%d dropped=%d raw_max=%.1f)" % (
                warmup_seconds, raw_n, dropped_n, raw_max
            ),
        }

    avg = sum(used_values) / used_n
    min_v = min(used_values)
    med_v = float(statistics.median(used_values))
    status = PASS if avg >= min_fps else FAIL
    note = "avg=%.1f min=%.1f med=%.1f n=%d (raw_n=%d dropped=%d raw_max=%.1f)" % (
        avg, min_v, med_v, used_n, raw_n, dropped_n, raw_max
    )

    return {
        "status": status,
        "avg": round(avg, 1),
        "min": round(min_v, 1),
        "median": round(med_v, 1),
        "n": used_n,
        "raw_n": raw_n,
        "dropped_n": dropped_n,
        "raw_max": round(raw_max, 1),
        "note": note,
    }


def vector_magnitude(vel: object) -> float:
    """Return the Euclidean magnitude |v| of a 3D vector.

    Distinguishes the Euclidean norm from component count: for a 3D mathutils.Vector,
    len(vel) returns 3 (dimension), whereas vel.length returns the magnitude.
    """
    if vel is None:
        return 0.0
    if hasattr(vel, "length"):
        return float(vel.length)  # type: ignore[union-attr]
    try:
        x, y, z = vel[0], vel[1], vel[2]  # type: ignore[index]
        return float((x * x + y * y + z * z) ** 0.5)
    except (IndexError, TypeError) as exc:
        raise ValueError(f"Expected a 3D vector or sequence, got {vel!r}") from exc


def matrix_header() -> str:
    """Markdown header for one run row (feature columns in CHECKS order)."""
    return "| Version | Machine | " + " | ".join(CHECKS) + " | fps_avg |"


def matrix_row(version: str, machine: str, checks: dict[str, str], fps_avg: float) -> str:
    """Markdown row for one engine version on one machine."""
    cells = " | ".join(_cell(checks[name]) if name in checks else "-" for name in CHECKS)
    return "| %s | %s | %s | %.1f |" % (version, machine, cells, float(fps_avg))

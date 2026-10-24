"""Pure helpers for the S-01 engine spike (no bge/bpy imports).

`rr.glue.spike_probe` reports one status per engine feature the pin decision
needs. These helpers grade a run and render one markdown row for
`docs/reports/S-01_engine_decision.md`, so humans paste printed output instead
of re-typing numbers.
"""
from __future__ import annotations

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
    """Map a raw probe status to pass/fail/skip (unknown -> skip)."""
    text = str(status).strip().lower()
    return text if text in (PASS, FAIL, SKIP) else SKIP


def summarize(checks: dict[str, str]) -> dict[str, object]:
    """Grade a probe result set.

    ``ok`` is False when any check failed or was never reported, so a truncated
    run cannot masquerade as a pass.
    """
    passed = [name for name in CHECKS if normalize(checks.get(name, SKIP)) == PASS]
    failed = [name for name in CHECKS if normalize(checks.get(name, SKIP)) == FAIL]
    skipped = [name for name in CHECKS if normalize(checks.get(name, SKIP)) == SKIP]
    missing = [name for name in CHECKS if name not in checks]
    return {
        "ok": not failed and not missing,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "missing": missing,
    }


def _cell(status: object) -> str:
    return {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}.get(normalize(status), "-")


def matrix_header() -> str:
    """Markdown header for one run row (feature columns in CHECKS order)."""
    return "| Version | Machine | " + " | ".join(CHECKS) + " | fps_avg |"


def matrix_row(version: str, machine: str, checks: dict[str, str], fps_avg: float) -> str:
    """Markdown row for one engine version on one machine."""
    cells = " | ".join(_cell(checks[name]) if name in checks else "-" for name in CHECKS)
    return "| %s | %s | %s | %.1f |" % (version, machine, cells, float(fps_avg))

#!/usr/bin/env python3
"""Audio asset gate for ``docs/reference/AUDIO_LIST.csv`` (rules from docs/06 §3, docs/04 §5).

Checks every delivered file against the list row that names it:
  * folder per category (``assets/audio/{sfx,ui,ambience,music}``) and ``<ID>[_NN].ogg`` naming
  * 44.1 kHz; mono for SFX/UI, stereo for ambience/music
  * duration within tolerance of the row's ``duration_s``
  * sample peak <= -3 dBFS for SFX/UI (docs/06 §3)
  * integrated loudness ~ -18 LUFS for music, ~ -24 LUFS for ambience
  * loop rows: seam continuity (sample discontinuity + no fade-to-silence at the wrap)

Missing rows are listed by priority and only fail with ``--fail-missing`` (the list is built
incrementally, so a not-yet-delivered ID must not block unrelated work). Unknown files,
wrong folders, wrong formats or a broken loop always fail.

Usage:
    python tools/check_audio.py                       # validate everything under assets/audio
    python tools/check_audio.py --ids MUS_Ch1_Base    # restrict to some IDs
    python tools/check_audio.py --fail-missing        # release gate: every row must exist
    python tools/check_audio.py --verbose             # print seam/loudness measurements for passes too
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audio_lufs import integrated_lufs, peak_db, rms_db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIST = ROOT / "docs" / "reference" / "AUDIO_LIST.csv"
DEFAULT_ROOT = ROOT / "assets" / "audio"

SR = 44100
CATEGORY_DIR = {"SFX": "sfx", "UI": "ui", "Ambience": "ambience", "Music": "music"}
CHANNELS = {"SFX": 1, "UI": 1, "Ambience": 2, "Music": 2}
# (target LUFS, tolerance LU) per category; docs/06 §3.
LOUDNESS = {"Music": (-18.0, 2.0), "Ambience": (-24.0, 2.0)}
PEAK_LIMIT_DB = -3.0
# A loop may legitimately open on a downbeat and end in a rest (percussive stems), so the seam is
# judged on discontinuity (audible click) and on not fading to digital silence at the wrap.
SEAM_MAX_JUMP = 0.25  # |x[0] - x[-1]| / peak
SEAM_MIN_TAIL_DB = -60.0
SEAM_WINDOW_S = 0.05
_VARIATION_RE = re.compile(r"^(\d{1,2})\s*(?:variations?)?\b")
_NAME_RE = re.compile(r"^(?P<id>[A-Za-z0-9]+_[A-Za-z0-9_]+?)(?:_(?P<var>\d{2}))?$")


@dataclass(frozen=True)
class Entry:
    """One AUDIO_LIST.csv row."""

    id: str
    category: str
    duration_s: float
    loop: bool
    priority: str
    notes: str

    @property
    def folder(self) -> str:
        return CATEGORY_DIR[self.category]

    @property
    def variations(self) -> int:
        """Number of takes the list asks for; 1 when the row does not state a count."""
        match = _VARIATION_RE.match(self.notes.strip())
        return int(match.group(1)) if match else 1


@dataclass
class Report:
    """Accumulated result of validating one file."""

    path: Path
    ok: bool = True
    problems: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def fail(self, problem: str) -> None:
        self.ok = False
        self.problems.append(problem)


def load_entries(list_path: Path) -> list[Entry]:
    """Parse the authoritative audio list."""
    with list_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        Entry(
            id=row["id"],
            category=row["category"],
            duration_s=float(row["duration_s"]),
            loop=row["loop"].strip().lower() == "yes",
            priority=row["priority"],
            notes=(row.get("notes") or "").strip(),
        )
        for row in rows
    ]


def parse_name(stem: str) -> tuple[str, int | None]:
    """Split ``SFX_RaftCreak_02`` into ``("SFX_RaftCreak", 2)``; ``MUS_Ch1_Base`` -> ``(id, None)``."""
    match = _NAME_RE.match(stem)
    if not match:
        return stem, None
    variation = match.group("var")
    return match.group("id"), (int(variation) if variation else None)


def duration_tolerance(expected_s: float) -> float:
    """Allow codec padding/rounding but no real length drift."""
    return max(0.05, 0.03 * expected_s)


def duration_ok(actual_s: float, expected_s: float) -> bool:
    return abs(actual_s - expected_s) <= duration_tolerance(expected_s)


def seam_metrics(samples: np.ndarray, sr: int = SR) -> tuple[float, float]:
    """Return (jump ratio across the loop seam, head/tail RMS delta in dB).

    ``jump`` is ``|x[0] - x[-1]|`` relative to the peak, so it is scale free.
    """
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 0.0:
        return 0.0, 0.0
    jump = float(np.max(np.abs(x[0] - x[-1]))) / peak
    window = max(1, int(round(SEAM_WINDOW_S * sr)))
    head = rms_db(x[:window])
    tail = rms_db(x[-window:])
    return jump, abs(tail - head)


def _load(path: Path) -> tuple[np.ndarray, int, int]:
    """Decode an audio file to ``(frames, channels)`` float64 plus sample rate and channels."""
    try:
        import soundfile  # noqa: PLC0415 - optional dependency, checked with a friendly error
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "soundfile is required to decode OGG Vorbis assets: python -m pip install soundfile"
        ) from exc
    data, sr = soundfile.read(str(path), dtype="float64", always_2d=True)
    return data, int(sr), int(data.shape[1])


def validate_file(path: Path, entry: Entry, root: Path) -> Report:
    """Run every per-file rule for ``path`` against its list row."""
    report = Report(path=path)
    expected_dir = root / entry.folder
    if path.parent.resolve() != expected_dir.resolve():
        report.fail(f"wrong folder: expected {path.parent.name} -> {expected_dir.name}/{entry.folder}")

    data, sr, channels = _load(path)
    duration = data.shape[0] / sr if sr else 0.0

    if sr != SR:
        report.fail(f"sample rate {sr} Hz, expected {SR}")
    if channels != CHANNELS[entry.category]:
        report.fail(f"{channels} channel(s), expected {CHANNELS[entry.category]} for {entry.category}")
    if not duration_ok(duration, entry.duration_s):
        report.fail(
            f"duration {duration:.3f}s, expected {entry.duration_s:.3f}s "
            f"(+/-{duration_tolerance(entry.duration_s):.3f}s)"
        )

    peak = peak_db(data)
    report.info.append(f"peak {peak:.1f} dBFS")
    limit = PEAK_LIMIT_DB
    if peak > limit:
        report.fail(f"peak {peak:.1f} dBFS above {limit:.0f} dBFS ceiling")

    if entry.category in LOUDNESS:
        target, tolerance = LOUDNESS[entry.category]
        loudness = integrated_lufs(data, sr)
        report.info.append(f"{loudness:.1f} LUFS")
        if not abs(loudness - target) <= tolerance:
            report.fail(f"{loudness:.1f} LUFS, expected {target:.0f} +/-{tolerance:.0f} LUFS")

    if entry.loop:
        jump, rms_delta = seam_metrics(data, sr)
        tail = np.asarray(data, dtype=np.float64)[-max(1, int(round(SEAM_WINDOW_S * sr))):]
        tail_db = rms_db(tail)
        report.info.append(f"seam jump {jump:.3f}, head/tail {rms_delta:.1f} dB, tail {tail_db:.1f} dBFS")
        if jump > SEAM_MAX_JUMP:
            report.fail(f"loop seam jump {jump:.3f} > {SEAM_MAX_JUMP} (audible click)")
        if tail_db < SEAM_MIN_TAIL_DB:
            report.fail(f"loop fades to silence at the seam ({tail_db:.1f} dBFS) - tail was cut, not looped")

    return report


def collect_files(root: Path) -> list[Path]:
    """Every audio file under ``root`` (any extension, so strays are reported)."""
    if not root.exists():
        return []
    allowed = {".ogg", ".wav", ".flac", ".mp3"}
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in allowed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", type=Path, default=DEFAULT_LIST, help="AUDIO_LIST.csv path")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="audio asset root")
    parser.add_argument("--ids", nargs="*", default=None, help="restrict checking to these IDs")
    parser.add_argument("--fail-missing", action="store_true", help="fail when a list row has no file")
    parser.add_argument("--verbose", action="store_true", help="print measurements for passing files")
    args = parser.parse_args(argv)

    entries = load_entries(args.list)
    by_id = {entry.id: entry for entry in entries}
    wanted = set(args.ids) if args.ids else None

    files = collect_files(args.root)
    failures = 0
    delivered: dict[str, list[Path]] = {}

    for path in files:
        if path.suffix.lower() != ".ogg":
            print(f"[FAIL] {path.relative_to(ROOT).as_posix()}: not OGG Vorbis (docs/06 §3)")
            failures += 1
            continue
        asset_id, variation = parse_name(path.stem)
        entry = by_id.get(asset_id)
        if entry is None:
            print(f"[FAIL] {path.relative_to(ROOT).as_posix()}: '{asset_id}' is not in AUDIO_LIST.csv")
            failures += 1
            continue
        if wanted is not None and entry.id not in wanted:
            continue
        delivered.setdefault(entry.id, []).append(path)
        if variation is not None and not 1 <= variation <= 99:
            print(f"[FAIL] {path.name}: variation index out of range")
            failures += 1
            continue

        report = validate_file(path, entry, args.root)
        rel = path.relative_to(ROOT).as_posix()
        if report.ok:
            if args.verbose:
                print(f"[ok  ] {rel}: {'; '.join(report.info)}")
            else:
                print(f"[ok  ] {rel}")
        else:
            failures += 1
            print(f"[FAIL] {rel}")
            for problem in report.problems:
                print(f"       - {problem}")

    scope = [e for e in entries if wanted is None or e.id in wanted]
    missing = [e for e in scope if e.id not in delivered]
    over = [
        (entry.id, len(delivered[entry.id]), entry.variations)
        for entry in scope
        if entry.id in delivered and len(delivered[entry.id]) > entry.variations
    ]
    under = [
        (entry.id, len(delivered[entry.id]), entry.variations)
        for entry in scope
        if entry.id in delivered and len(delivered[entry.id]) < entry.variations
    ]

    print()
    print(f"checked {len(files)} file(s) under {args.root.relative_to(ROOT).as_posix()}")
    print(f"delivered {len(scope) - len(missing)}/{len(scope)} listed ID(s)")
    for asset_id, have, need in over:
        print(f"[warn] {asset_id}: {have} files for {need} listed variation(s) - extras ignored")
    for asset_id, have, need in under:
        print(f"[warn] {asset_id}: {have}/{need} variation(s) delivered")
    if missing:
        p0 = [e.id for e in missing if e.priority == "P0"]
        print(f"missing {len(missing)} ID(s), P0: {len(p0)}" + (f" ({', '.join(p0)})" if p0 else ""))
        if args.fail_missing:
            failures += len(missing)

    print(f"{'PASS' if failures == 0 else 'FAIL'}: {failures} problem(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

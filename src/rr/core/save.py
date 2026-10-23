"""Versioned JSON save data with atomic writes."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field

SAVE_VERSION = 2


@dataclass
class SaveData:
    version: int = SAVE_VERSION
    coins: int = 0
    golden_fish: int = 0
    chapters_unlocked: int = 1
    best_times: dict[str, float] = field(default_factory=dict)
    cosmetics: list[str] = field(default_factory=list)
    settings: dict[str, float | int | str | bool] = field(default_factory=dict)


def migrate(raw: dict) -> dict:
    v = int(raw.get("version", 1))
    if v < 2:  # v1 had no 'cosmetics' or 'settings'
        raw.setdefault("cosmetics", [])
        raw.setdefault("settings", {})
        raw["version"] = 2
    return raw


def to_json(data: SaveData) -> str:
    return json.dumps(asdict(data), indent=2, sort_keys=True)


def from_json(text: str) -> SaveData:
    raw = migrate(json.loads(text))
    known = {k: raw[k] for k in SaveData.__dataclass_fields__ if k in raw}
    return SaveData(**known)


def write_atomic(path: str, data: SaveData) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(to_json(data))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read(path: str) -> SaveData:
    if not os.path.exists(path):
        return SaveData()
    try:
        with open(path, encoding="utf-8") as f:
            return from_json(f.read())
    except (json.JSONDecodeError, TypeError, ValueError):
        # Corrupt save: keep a backup, start fresh rather than crash.
        os.replace(path, path + ".corrupt")
        return SaveData()

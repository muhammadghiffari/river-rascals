"""Thin aud adapter. VERIFY: every aud operation until exercised in target UPBGE.

One instance per prototype session; call methods on the game thread. No tick required.
"""
from __future__ import annotations

import time
from collections import Counter, deque
from pathlib import Path

from rr.core.prototype_audio import (
    EVENTS,
    MAX_ERRORS,
    MAX_EVENT_VOICES,
    MAX_VOICES,
    MODE_LOOPS,
    AudioPolicy,
)


class PrototypeAudio:
    def __init__(self, root_path):
        self.root = Path(root_path) / "assets" / "audio"
        self.policy = AudioPolicy()
        self.mode = None
        self.closed = False
        self.device = None
        self.sounds = {}
        self.loops = []
        self.voices = []
        self.event_counts = Counter()
        self.played_counts = Counter()
        self.dropped_counts = Counter()
        self.mode_counts = Counter()
        self.error_count = 0
        self.errors = deque(maxlen=MAX_ERRORS)
        try:
            import aud

            self.aud = aud
            self.device = aud.Device()  # VERIFY: target audio backend availability.
        except Exception as exc:
            self._error("initialize", exc)

    def _error(self, operation, exc):
        self.error_count += 1
        self.errors.append(f"{operation}: {type(exc).__name__}: {exc}")

    def _play(self, path, volume, pitch=1.0, loop=False):
        if self.device is None or self.closed:
            return None
        handle = None
        try:
            if path not in self.sounds:
                self.sounds[path] = self.aud.Sound(str(self.root / path))  # VERIFY: Vorbis decode.
            # VERIFY: lock prevents first samples escaping before gain/loop configuration.
            self.device.lock()
            try:
                handle = self.device.play(self.sounds[path])
                handle.volume = volume
                handle.pitch = pitch
                handle.relative = True
                handle.loop_count = -1 if loop else 0
            finally:
                self.device.unlock()
            return handle
        except Exception as exc:
            if handle is not None:
                self._stop(handle)
            self._error(f"play {path}", exc)
            return None

    def _stop(self, handle):
        try:
            handle.stop()  # VERIFY: invalid handles can be stopped safely.
        except Exception as exc:
            self._error("stop", exc)

    def _clear(self):
        for handle in self.loops:
            self._stop(handle)
        for _, handle in self.voices:
            self._stop(handle)
        self.loops.clear()
        self.voices.clear()

    def set_mode(self, mode):
        if mode not in MODE_LOOPS:
            raise ValueError(f"Unknown audio mode: {mode}")
        if self.closed or mode == self.mode:
            return
        self.mode_counts[mode] += 1
        self._clear()
        self.mode = mode
        for path, volume in MODE_LOOPS[mode]:
            handle = self._play(path, volume, loop=True)
            if handle is not None:
                self.loops.append(handle)

    def event(self, name):
        if name not in EVENTS:
            raise ValueError(f"Unknown audio event: {name}")
        self.event_counts[name] += 1
        if self.closed or self.device is None:
            self.dropped_counts[name] += 1
            return
        try:
            # VERIFY: aud status 0 means invalid/stopped; completed voices auto-release.
            self.voices[:] = [(n, h) for n, h in self.voices if h.status]
        except Exception as exc:
            self._error("voice status", exc)
            self.dropped_counts[name] += 1
            return
        if (len(self.voices) >= MAX_VOICES
                or sum(n == name for n, _ in self.voices) >= MAX_EVENT_VOICES):
            self.dropped_counts[name] += 1
            return
        cue = self.policy.choose(name, time.monotonic())
        handle = self._play(cue.path, cue.volume, cue.pitch) if cue else None
        if handle is None:
            self.dropped_counts[name] += 1
        else:
            self.voices.append((name, handle))
            self.played_counts[name] += 1

    def close(self):
        if self.closed:
            return
        self._clear()
        self.sounds.clear()
        self.device = None
        self.closed = True

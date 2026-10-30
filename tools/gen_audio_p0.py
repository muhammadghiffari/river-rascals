#!/usr/bin/env python3
"""Deterministic, original procedural generator for the P0 audio set.

Everything is synthesised from scratch with numpy (no samples, no third-party audio), then
written as 16-bit WAV with the stdlib ``wave`` module and encoded to OGG Vorbis via soundfile
(docs/06 §3: 44.1 kHz, mono SFX/UI, stereo music, <= -3 dBFS peaks, music ~-18 LUFS, seamless loops).

Determinism: every file is a pure function of ``(asset id, variation index)`` - the RNG seed is
``crc32("<id>:<variation>")``, so re-running the tool reproduces byte-identical audio on the
same numpy/scipy/libsndfile versions.

Formats, lengths and variation counts come from ``docs/reference/AUDIO_LIST.csv``; only the 12 P0
IDs listed in ``ASSETS`` are rendered. Nothing here is wired into the game.

Usage:
    python tools/gen_audio_p0.py                        # render all P0 IDs into assets/audio/
    python tools/gen_audio_p0.py --only MUS_Ch1_Base    # a single ID (repeatable)
    python tools/gen_audio_p0.py --keep-wav C:/tmp/wav  # also keep the lossless masters
    python tools/check_audio.py                         # validate the result
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import wave
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal  # type: ignore[import-untyped]

sys.path.insert(0, str(Path(__file__).parent))
from audio_lufs import integrated_lufs, peak_db  # noqa: E402

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = ROOT / "assets" / "audio"
PROVENANCE = ROOT / "assets" / "PROVENANCE.csv"
TODAY = "2026-10-30"

CATEGORY_DIR = {"SFX": "sfx", "UI": "ui", "Music": "music"}
# docs/06 §3: SFX/UI peaks <= -3 dBFS; we aim lower so the mix has headroom.
SFX_PEAK_DB = -6.0
MUSIC_TARGET_LUFS = {"MUS_Ch1_Base": -18.0, "MUS_Ch1_Rhythm": -19.0}
MUSIC_PEAK_CEILING_DB = -1.0

# ---------------- basic DSP helpers ----------------


def _n(duration_s: float) -> int:
    """Sample count for an exact duration."""
    return int(round(duration_s * SR))


def _time(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def _rng(*key: object) -> np.random.Generator:
    """Deterministic generator seeded from the asset identity."""
    return np.random.default_rng(zlib.crc32(":".join(str(part) for part in key).encode()))


def _fade(x: np.ndarray, fade_in_ms: float = 5.0, fade_out_ms: float = 5.0) -> np.ndarray:
    """Apply the 5 ms edge fades required for trimmed SFX (docs/06 §3)."""
    out = x.copy()
    n_in = min(len(out), int(SR * fade_in_ms / 1000.0))
    n_out = min(len(out), int(SR * fade_out_ms / 1000.0))
    if n_in:
        out[:n_in] *= np.linspace(0.0, 1.0, n_in, endpoint=False)
    if n_out:
        out[-n_out:] *= np.linspace(1.0, 0.0, n_out, endpoint=False)
    return out


def _bandpass(x: np.ndarray, low: float, high: float, order: int = 2) -> np.ndarray:
    nyq = SR * 0.45
    high = min(high, nyq)
    low = min(low, high * 0.95)
    sos = signal.butter(order, [low, high], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _lowpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, min(cutoff, SR * 0.45), btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _highpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, min(cutoff, SR * 0.45), btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _sweep_lowpass(x: np.ndarray, start_hz: float, end_hz: float, blocks: int = 24) -> np.ndarray:
    """Time-varying low pass (block-wise coefficients, filter state carried over)."""
    out = np.empty_like(x)
    edges = np.geomspace(start_hz, end_hz, blocks + 1)
    zi = None
    for index in range(blocks):
        lo, hi = index * len(x) // blocks, (index + 1) * len(x) // blocks
        if hi <= lo:
            continue
        sos = signal.butter(2, min(edges[index], SR * 0.45), btype="low", fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        out[lo:hi], zi = signal.sosfilt(sos, x[lo:hi], zi=zi)
    return out


def _attack_decay(n: int, attack_s: float, decay_s: float) -> np.ndarray:
    t = _time(n)
    return (1.0 - np.exp(-t / max(attack_s, 1e-5))) * np.exp(-t / max(decay_s, 1e-5))


def _add(buffer: np.ndarray, source: np.ndarray, start_s: float, wrap: bool = False) -> None:
    """Mix ``source`` into ``buffer`` at ``start_s``; ``wrap`` keeps loops exactly periodic."""
    size = len(buffer)
    start = int(round(start_s * SR))
    if wrap:
        start %= size
        split = min(len(source), size - start)
        buffer[start:start + split] += source[:split]
        rest = source[split:]
        if len(rest):
            _add(buffer, rest, 0.0, wrap=True)
        return
    if start >= size or start < 0:
        return
    split = min(len(source), size - start)
    buffer[start:start + split] += source[:split]


def _pan(mono: np.ndarray, position: float) -> np.ndarray:
    """Constant-power pan; ``position`` in [-1, 1] maps to (left, right) gains."""
    angle = (np.clip(position, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)


# ---------------- instruments ----------------


def _pluck(freq: float, duration_s: float, rng: np.random.Generator,
           brightness: float = 0.5, tau: float = 0.30, detune: float = 0.0) -> np.ndarray:
    """Additive plucked-string tone (ukulele/guitar family, ukulele register)."""
    n = _n(duration_s)
    t = _time(n)
    out = np.zeros(n)
    partials = min(14, max(1, int(SR * 0.42 / freq)))
    for k in range(1, partials + 1):
        weight = (brightness ** (k - 1)) / k ** 1.15
        partial_tau = tau / (k ** 0.75)
        out += weight * np.sin(2.0 * np.pi * freq * k * t) * np.exp(-t / partial_tau)
    if detune:
        out = 0.6 * out + 0.4 * _pluck(freq * (1.0 + detune), duration_s, rng, brightness, tau)
    return out * (1.0 - np.exp(-t / 0.0015))


def _marimba(freq: float, duration_s: float, rng: np.random.Generator, tau: float = 0.26) -> np.ndarray:
    """Marimba bar: inharmonic partials plus a short mallet click."""
    n = _n(duration_s)
    t = _time(n)
    out = np.zeros(n)
    for ratio, amp, decay in ((1.0, 1.0, 1.0), (3.98, 0.30, 0.34), (9.6, 0.10, 0.16), (15.1, 0.04, 0.09)):
        out += amp * np.sin(2.0 * np.pi * freq * ratio * t) * np.exp(-t / (tau * decay))
    click = _bandpass(rng.standard_normal(n), 1800.0, 5200.0) * np.exp(-t / 0.004) * 0.10
    return (out + click) * (1.0 - np.exp(-t / 0.0012))


def _flute(freq: float, duration_s: float, rng: np.random.Generator) -> np.ndarray:
    """Breathy wooden flute: harmonic body, delayed vibrato, filtered breath noise."""
    n = _n(duration_s)
    t = _time(n)
    vibrato = 1.0 + 0.0045 * np.sin(2.0 * np.pi * 5.1 * t) * np.clip((t - 0.12) / 0.2, 0.0, 1.0)
    phase = 2.0 * np.pi * np.cumsum(freq * vibrato) / SR
    body = np.sin(phase) + 0.17 * np.sin(2.0 * phase) + 0.05 * np.sin(3.0 * phase)
    breath = _bandpass(rng.standard_normal(n), 900.0, 4600.0) * 0.09
    shape = np.minimum(1.0, t / 0.045)
    release = np.clip((t[-1] - t) / 0.09, 0.0, 1.0)
    return (body + breath) * shape * release


def _shaker(rng: np.random.Generator, accent: float = 1.0) -> np.ndarray:
    n = _n(0.09)
    body = _bandpass(rng.standard_normal(n), 4600.0, 10500.0) * _attack_decay(n, 0.003, 0.035)
    return body * accent


def _cajon_bass(rng: np.random.Generator) -> np.ndarray:
    n = _n(0.24)
    t = _time(n)
    pitch = 92.0 * np.exp(-t / 0.05) + 52.0
    phase = 2.0 * np.pi * np.cumsum(pitch) / SR
    thump = np.sin(phase) * np.exp(-t / 0.10)
    click = _bandpass(rng.standard_normal(n), 200.0, 1400.0) * np.exp(-t / 0.010) * 0.25
    return thump + click


def _cajon_slap(rng: np.random.Generator) -> np.ndarray:
    n = _n(0.11)
    body = _bandpass(rng.standard_normal(n), 1100.0, 5200.0) * _attack_decay(n, 0.002, 0.028)
    return body * 0.8


def _clap(rng: np.random.Generator) -> np.ndarray:
    n = _n(0.20)
    out = np.zeros(n)
    for offset, gain in ((0.000, 1.0), (0.009, 0.7), (0.018, 0.5), (0.027, 0.35)):
        burst = _bandpass(rng.standard_normal(n), 900.0, 3400.0) * _attack_decay(n, 0.002, 0.05)
        out += gain * np.roll(burst, int(offset * SR))
    return out * 0.5


def _reverb(x: np.ndarray, wet: float, rng: np.random.Generator, loop: bool = False,
            decay_s: float = 0.55) -> np.ndarray:
    """Cheap convolution reverb; circular for loops so the tail wraps into the loop start."""
    length = _n(1.6)
    t = _time(length)
    impulse = rng.standard_normal(length) * np.exp(-t / decay_s)
    impulse = _lowpass(impulse, 6500.0)
    impulse /= np.sqrt(np.sum(np.square(impulse))) or 1.0
    if loop:
        size = len(x)
        spectrum = np.fft.rfft(x) * np.fft.rfft(impulse, n=size)
        tail = np.fft.irfft(spectrum, n=size)
    else:
        tail = signal.fftconvolve(x, impulse)[: len(x)]
    return (1.0 - wet) * x + wet * tail * np.sqrt(len(x) / max(1, SR))


# ---------------- sound design ----------------


def _sfx_raft_creak(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Stick-slip wood creak with rope tension squeaks (1.2 s)."""
    n = _n(1.2)
    out = np.zeros(n)
    events = [(0.05, 0.42), (0.58, 0.34), (0.95, 0.18)]
    for start, duration in events:
        length = _n(duration)
        t = _time(length)
        rate = rng.uniform(26.0, 48.0)
        slip = np.clip(np.sin(2.0 * np.pi * rate * t + rng.uniform(0, np.pi)), 0.0, 1.0) ** 2
        grain = _bandpass(rng.standard_normal(length), 240.0, 1200.0) * (0.35 + 0.65 * slip)
        groan_freq = 74.0 + 6.0 * variation - 8.0 * t
        groan = np.sin(2.0 * np.pi * np.cumsum(groan_freq) / SR) * (0.4 + 0.6 * slip) * 0.5
        rope = _bandpass(rng.standard_normal(length), 1700.0, 2800.0) * slip * 0.18
        env = _attack_decay(length, 0.03, duration * 0.5)
        _add(out, (grain + groan + rope) * env, start)
    return out


def _sfx_splash_big(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Body plunging into water: thump, broadband plunge, bubbles, hiss (1.2 s)."""
    n = _n(1.2)
    t = _time(n)
    plunge = _sweep_lowpass(rng.standard_normal(n), 9000.0, 600.0, blocks=20)
    plunge *= _attack_decay(n, 0.004, 0.30)
    thump_freq = 88.0 * np.exp(-t / 0.08) + 42.0
    thump = np.sin(2.0 * np.pi * np.cumsum(thump_freq) / SR) * np.exp(-t / 0.18) * 0.8
    out = 0.9 * plunge + thump
    for _ in range(9):
        start = rng.uniform(0.15, 1.05)
        length = _n(rng.uniform(0.02, 0.05))
        bubbles_t = _time(length)
        bubble_freq = rng.uniform(380.0, 1100.0) * (1.0 + 2.2 * bubbles_t)
        bubble = np.sin(2.0 * np.pi * np.cumsum(bubble_freq) / SR) * np.exp(-bubbles_t / 0.012)
        _add(out, bubble * rng.uniform(0.05, 0.16), start)
    hiss = _highpass(rng.standard_normal(n), 600.0) * np.exp(-t / 0.5) * 0.10
    return out + hiss


def _bell(freq: float, duration_s: float, decay_s: float = 0.20) -> np.ndarray:
    """Small metallic bell/chime (coin, sparkle)."""
    n = _n(duration_s)
    t = _time(n)
    out = np.zeros(n)
    for ratio, amp, scale in ((1.0, 1.0, 1.0), (2.76, 0.5, 0.45), (5.40, 0.22, 0.28), (8.93, 0.09, 0.18)):
        out += amp * np.sin(2.0 * np.pi * freq * ratio * t) * np.exp(-t / (decay_s * scale))
    return out * (1.0 - np.exp(-t / 0.0008))


def _sfx_coin_pickup(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Bright ascending two-note coin chime (0.5 s)."""
    n = _n(0.5)
    out = np.zeros(n)
    _add(out, _bell(1318.5, 0.4, 0.11), 0.0)          # E6
    _add(out, _bell(1975.5, 0.4, 0.13), 0.085)        # B6 (fifth up, "ascending")
    _add(out, _bandpass(rng.standard_normal(_n(0.08)), 5000.0, 11000.0) * 0.05, 0.0)
    return out


def _sfx_fish_pickup(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Magical shimmer plus a watery flop and a joyful resolve (0.9 s)."""
    n = _n(0.9)
    out = np.zeros(n)
    for index in range(7):
        length = _n(0.55)
        t = _time(length)
        base = 3200.0 + 520.0 * index + rng.uniform(-120.0, 120.0)
        glide = base * (1.0 + 0.22 * t)
        shimmer = np.sin(2.0 * np.pi * np.cumsum(glide) / SR) * np.exp(-t / 0.22)
        shimmer *= 1.0 + 0.35 * np.sin(2.0 * np.pi * 11.0 * t)
        _add(out, shimmer * 0.10, 0.02 + 0.055 * index)
    flop_t = _n(0.22)
    flop = _bandpass(rng.standard_normal(flop_t), 240.0, 1700.0) * _attack_decay(flop_t, 0.003, 0.06)
    _add(out, flop * 0.55, 0.10)
    _add(out, _marimba(1174.7, 0.45, rng, tau=0.22), 0.34)      # D6
    _add(out, _marimba(1480.0, 0.50, rng, tau=0.24), 0.46)      # F#6
    return out


def _sfx_checkpoint(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Warm three-note fanfare, wooden flute doubled by marimba (1.5 s)."""
    n = _n(1.5)
    out = np.zeros(n)
    notes = ((0.00, 587.33, 0.55), (0.30, 739.99, 0.55), (0.60, 880.00, 0.80))
    for start, freq, length in notes:
        _add(out, _flute(freq, length, rng) * 0.55, start)
        _add(out, _marimba(freq, length + 0.15, rng, tau=0.24) * 0.35, start)
    _add(out, _marimba(1760.0, 0.6, rng, tau=0.26) * 0.20, 0.60)
    for beat in (0.0, 0.30, 0.60):
        _add(out, _shaker(rng, 0.5) * 0.10, beat)
    out = _reverb(out, 0.18, rng)
    return out


def _sfx_finish(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Cozy 3 s chapter-complete sting: guitar strums, flute melody, shaker (D major)."""
    n = _n(3.0)
    out = np.zeros(n)
    chords = ((50, 57, 62, 66), (55, 62, 66, 69), (57, 62, 66, 69), (50, 57, 62, 66))
    for index, chord in enumerate(chords):
        start = 0.12 + index * 0.62
        for string, midi in enumerate(chord):
            _add(out, _pluck(440.0 * 2.0 ** ((midi - 69) / 12.0), 1.4, rng, 0.42, 0.5) * 0.22,
                 start + string * 0.016)
    melody = ((0.30, 587.33, 0.30), (0.60, 739.99, 0.30), (0.92, 880.00, 0.34),
              (1.24, 739.99, 0.30), (1.55, 587.33, 0.40), (1.95, 587.33, 1.0))
    for start, freq, length in melody:
        _add(out, _flute(freq, length, rng) * 0.5, start)
    for start in np.arange(0.55, 2.55, 0.15):
        _add(out, _shaker(rng, 0.35 if int(start * 10) % 2 else 0.75) * 0.09, float(start))
    out = _reverb(out, 0.22, rng, decay_s=0.7)
    return out


def _sfx_otter_chirp(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Playful otter squeak; single or double chirp depending on the variation (0.5 s)."""
    n = _n(0.5)
    out = np.zeros(n)

    def chirp(start: float, length: float, base: float) -> None:
        count = _n(length)
        t = _time(count)
        bump = np.sin(np.pi * np.clip(t / length, 0.0, 1.0))
        freq = base * (1.0 + 0.42 * bump)
        vibrato = 1.0 + 0.03 * np.sin(2.0 * np.pi * 28.0 * t)
        phase = 2.0 * np.pi * np.cumsum(freq * vibrato) / SR
        voice = np.sin(phase) + 0.35 * np.sin(2.0 * phase) + 0.12 * np.sin(3.0 * phase)
        voice = _bandpass(voice, 900.0, 6000.0) * _attack_decay(count, 0.006, length * 0.55)
        _add(out, voice, start)

    base = 1500.0 + 95.0 * variation
    if variation % 3 == 0:
        chirp(0.03, 0.14, base)
        chirp(0.20, 0.16, base * 1.14)
    else:
        chirp(0.03, 0.20 + 0.02 * (variation % 2), base * rng.uniform(0.95, 1.06))
    return out


def _sfx_otter_panic(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Alarmed descending squeal with tremolo (0.8 s)."""
    n = _n(0.8)
    t = _time(n)
    start_freq = 2500.0 + 130.0 * variation
    freq = start_freq * np.exp(-1.15 * t) + 900.0
    tremolo = 1.0 - 0.35 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 18.0 * t))
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    voice = np.tanh(1.6 * (np.sin(phase) + 0.3 * np.sin(2.0 * phase))) * 0.6
    voice *= tremolo * _attack_decay(n, 0.008, 0.34)
    voice = _bandpass(voice, 700.0, 7000.0)
    out = voice.copy()
    _add(out, _bandpass(rng.standard_normal(_n(0.07)), 1500.0, 6000.0) * 0.06, 0.60)
    return out


def _ui_confirm(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Positive two-note marimba blip, C5 -> G5 (0.4 s)."""
    out = np.zeros(_n(0.4))
    _add(out, _marimba(523.25, 0.30, rng, tau=0.16) * 0.8, 0.0)
    _add(out, _marimba(783.99, 0.34, rng, tau=0.18), 0.085)
    return out


def _ui_back(rng: np.random.Generator, variation: int) -> np.ndarray:
    """Soft descending two-note blip, G4 -> D4 (0.3 s)."""
    out = np.zeros(_n(0.3))
    _add(out, _marimba(392.00, 0.18, rng, tau=0.12) * 0.7, 0.0)
    _add(out, _marimba(293.66, 0.24, rng, tau=0.14) * 0.8, 0.07)
    return out


# ---------------- music (MUS_Ch1, 100 BPM, D major, 96 s = 40 bars) ----------------

BPM = 100.0
BEAT = 60.0 / BPM          # 0.6 s
BAR = 4.0 * BEAT           # 2.4 s
BARS = 40
MUSIC_LENGTH = BARS * BAR  # 96.0 s exactly = 40 clean 4/4 bars at 100 BPM

# Ukulele voicings: D, A, Bm, G - one chord per bar, four-bar cycle.
UKULELE = ((62, 66, 69, 74), (57, 61, 64, 69), (59, 62, 66, 71), (55, 59, 62, 67))
CHORD_ROOTS = (62, 57, 59, 55)
PENTATONIC = (62, 64, 66, 69, 71, 74, 76, 78, 81, 83)  # D major pentatonic across two octaves
STRUM_PATTERN = ((0.0, 1.0, "down"), (1.5 * BEAT, 0.62, "up"), (2.5 * BEAT, 0.8, "down"),
                 (3.5 * BEAT, 0.55, "up"))


def _midi_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _render_base() -> np.ndarray:
    """Stem A: ukulele strums + light marimba melody in D major (periodic over 96 s)."""
    rng_strum = _rng("MUS_Ch1_Base", "ukulele")
    rng_melody = _rng("MUS_Ch1_Base", "marimba")
    uke = np.zeros(_n(MUSIC_LENGTH))
    melody = np.zeros(_n(MUSIC_LENGTH))

    for bar in range(BARS):
        bar_start = bar * BAR
        chord = UKULELE[bar % 4]
        for beat_s, accent, direction in STRUM_PATTERN:
            for string, midi in enumerate(chord):
                offset = string * 0.017 if direction == "down" else (3 - string) * 0.017
                voice = _pluck(_midi_hz(midi), 1.5, rng_strum, brightness=0.46, tau=0.42)
                _add(uke, voice * accent * 0.22, bar_start + beat_s + offset, wrap=True)

        # Melody: chord-tone landing on beat 1, pentatonic wandering on the off-beats.
        root = CHORD_ROOTS[bar % 4]
        chord_tones = (root, root + 4, root + 7, root + 12)
        if rng_melody.random() < 0.8:
            note = chord_tones[int(rng_melody.integers(0, 4))] + 12
            _add(melody, _marimba(_midi_hz(note), 0.9, rng_melody) * 0.30, bar_start, wrap=True)
        for slot in range(1, 4):
            if rng_melody.random() < 0.55:
                note = PENTATONIC[int(rng_melody.integers(0, len(PENTATONIC)))]
                accent = 0.26 if slot % 2 else 0.2
                _add(melody, _marimba(_midi_hz(note), 0.8, rng_melody) * accent,
                     bar_start + slot * BEAT + rng_melody.choice([0.0, 0.5 * BEAT]), wrap=True)

    uke_stereo = _pan(_reverb(uke, 0.16, rng_strum, loop=True), -0.28)
    melody_stereo = _pan(_reverb(melody, 0.20, rng_melody, loop=True, decay_s=0.7), 0.30)
    return uke_stereo + melody_stereo


def _render_rhythm() -> np.ndarray:
    """Stem B: shaker, cajon and hand claps locked to the same 100 BPM grid."""
    rng = _rng("MUS_Ch1_Rhythm")
    shaker = np.zeros(_n(MUSIC_LENGTH))
    percussion = np.zeros(_n(MUSIC_LENGTH))

    for bar in range(BARS):
        bar_start = bar * BAR
        for eighth in range(8):
            accent = 1.0 if eighth in (0, 4) else (0.55 if eighth % 2 else 0.75)
            _add(shaker, _shaker(rng, accent) * 0.30, bar_start + eighth * 0.5 * BEAT, wrap=True)
        _add(percussion, _cajon_bass(rng) * 0.55, bar_start, wrap=True)
        _add(percussion, _cajon_slap(rng) * 0.32, bar_start + 1.5 * BEAT, wrap=True)
        _add(percussion, _cajon_slap(rng) * 0.26, bar_start + 3.5 * BEAT, wrap=True)
        _add(percussion, _clap(rng) * 0.22, bar_start + BEAT, wrap=True)
        _add(percussion, _clap(rng) * 0.22, bar_start + 3.0 * BEAT, wrap=True)

    return _pan(_reverb(shaker, 0.12, rng, loop=True), -0.35) + _pan(
        _reverb(percussion, 0.14, rng, loop=True), 0.15
    )


# ---------------- asset table, level control, encoding ----------------


@dataclass(frozen=True)
class Asset:
    """One P0 file to render."""

    id: str
    category: str
    duration_s: float
    variations: int
    loop: bool
    builder: Callable[[np.random.Generator, int], np.ndarray]
    note: str


ASSETS: tuple[Asset, ...] = (
    Asset("SFX_RaftCreak", "SFX", 1.2, 4, False, _sfx_raft_creak, "wooden raft creak"),
    Asset("SFX_SplashBig", "SFX", 1.2, 3, False, _sfx_splash_big, "big splash"),
    Asset("SFX_CoinPickup", "SFX", 0.5, 1, False, _sfx_coin_pickup, "coin chime"),
    Asset("SFX_FishPickup", "SFX", 0.9, 1, False, _sfx_fish_pickup, "golden fish shimmer"),
    Asset("SFX_Checkpoint", "SFX", 1.5, 1, False, _sfx_checkpoint, "checkpoint fanfare"),
    Asset("SFX_Finish", "SFX", 3.0, 1, False, _sfx_finish, "chapter complete sting"),
    Asset("SFX_OtterChirp", "SFX", 0.5, 6, False, _sfx_otter_chirp, "otter chirp"),
    Asset("SFX_OtterPanic", "SFX", 0.8, 4, False, _sfx_otter_panic, "otter panic squeal"),
    Asset("UI_Confirm", "UI", 0.4, 1, False, _ui_confirm, "UI confirm"),
    Asset("UI_Back", "UI", 0.3, 1, False, _ui_back, "UI back"),
    Asset("MUS_Ch1_Base", "Music", MUSIC_LENGTH, 1, True, lambda rng, v: _render_base(),
          "Ch1 calm stem A"),
    Asset("MUS_Ch1_Rhythm", "Music", MUSIC_LENGTH, 1, True, lambda rng, v: _render_rhythm(),
          "Ch1 rhythm stem B"),
)
BY_ID = {asset.id: asset for asset in ASSETS}


def _normalise_sfx(x: np.ndarray, target_peak_db: float = SFX_PEAK_DB) -> np.ndarray:
    peak = float(np.max(np.abs(x))) or 1.0
    return x * (10.0 ** (target_peak_db / 20.0) / peak)


def _normalise_music(x: np.ndarray, target_lufs: float) -> np.ndarray:
    """Loudness-normalise and keep sample peaks under the ceiling (report if that costs loudness)."""
    current = integrated_lufs(x, SR)
    if not np.isfinite(current):
        raise ValueError("music stem measured as silence")
    x = x * 10.0 ** ((target_lufs - current) / 20.0)
    peak = peak_db(x)
    if peak > MUSIC_PEAK_CEILING_DB:
        x = x * 10.0 ** ((MUSIC_PEAK_CEILING_DB - peak) / 20.0)
        print(f"    ! peak-limited: {target_lufs:.1f} LUFS target not reachable "
              f"({integrated_lufs(x, SR):.1f} LUFS after limiting)")
    return x


def write_wav(path: Path, samples: np.ndarray) -> None:
    """Write a 16-bit PCM WAV master (stdlib ``wave``; mono or interleaved stereo)."""
    data = np.asarray(samples, dtype=np.float64)
    if data.ndim == 1:
        data = data[:, None]
    clipped = np.clip(data, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(data.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm.tobytes())


def write_ogg(path: Path, samples: np.ndarray) -> None:
    """Encode Vorbis via libsndfile (docs/06 §3: OGG Vorbis)."""
    try:
        import soundfile  # noqa: PLC0415 - optional encode dependency
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit("soundfile is required to encode OGG: python -m pip install soundfile") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(samples, dtype=np.float32)
    if data.ndim == 1:
        data = data[:, None]
    # Chunked because libsndfile's one-shot Vorbis write overflows the stack on 96 s stereo.
    with soundfile.SoundFile(str(path), "w", samplerate=SR, channels=data.shape[1],
                             format="OGG", subtype="VORBIS") as handle:
        for start in range(0, len(data), 8192):
            handle.write(data[start:start + 8192])


def render(asset: Asset, variation: int) -> np.ndarray:
    """Render one variation at exactly the LIST duration, normalised to spec level."""
    rng = _rng(asset.id, variation)
    expected = _n(asset.duration_s)
    samples = asset.builder(rng, variation)
    if len(samples) != expected:
        raise ValueError(f"{asset.id}: rendered {len(samples)} samples, expected {expected}")
    if samples.ndim == 1:
        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        return _normalise_sfx(_fade(samples))

    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    return _normalise_music(samples, MUSIC_TARGET_LUFS.get(asset.id, -18.0))


def output_path(asset: Asset, variation: int) -> Path:
    """`assets/audio/<category>/<ID>[_NN].ogg` (docs/06 §3 naming, docs/04 §5 folders)."""
    folder = AUDIO_ROOT / CATEGORY_DIR[asset.category]
    if asset.category == "Music":
        return folder / f"{asset.id}.ogg"
    return folder / f"{asset.id}_{variation:02d}.ogg"


def _audio_list_prompts() -> dict[str, str]:
    """generator_prompt column of the authoritative AUDIO_LIST, so provenance quotes it verbatim."""
    path = ROOT / "docs" / "reference" / "AUDIO_LIST.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: row.get("generator_prompt", "") for row in csv.DictReader(handle)}


def provenance_rows(asset: Asset, variation: int, path: Path) -> list[str]:
    """8-column PROVENANCE.csv row for one generated file."""
    asset_id = path.stem
    seed = zlib.crc32(f"{asset.id}:{variation}".encode())
    prompt = _audio_list_prompts().get(asset.id) or asset.note
    notes = (
        f"Original procedural synthesis (numpy additive/subtractive); generator tools/gen_audio_p0.py; "
        f"seed {seed}; AUDIO_LIST prompt: {prompt}; auditioned: false"
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([
        asset_id,
        path.relative_to(ROOT).as_posix(),
        "tools/gen_audio_p0.py",
        "River Rascals team (original synthesis, generated with an AI coding agent)",
        "CC0-1.0 (own work, no third-party audio)",
        notes,
        TODAY,
        "builder (DeepSeek V4.1 Flash)",
    ])
    return buffer.getvalue().splitlines()


def append_provenance(paths: list[tuple[Asset, int, Path]]) -> int:
    """Append rows for assets that are not yet listed; existing rows are left untouched."""
    existing: set[str] = set()
    if PROVENANCE.exists():
        with PROVENANCE.open(newline="", encoding="utf-8") as handle:
            existing = {row["asset_id"] for row in csv.DictReader(handle)}
    lines: list[str] = []
    for asset, variation, path in paths:
        if path.stem in existing:
            continue
        lines.extend(provenance_rows(asset, variation, path))
    if not lines:
        return 0
    needs_newline = PROVENANCE.exists() and PROVENANCE.stat().st_size > 0
    with PROVENANCE.open("a", encoding="utf-8", newline="") as handle:
        if needs_newline:
            with PROVENANCE.open("rb") as probe:
                probe.seek(-1, 2)
                if probe.read(1) != b"\n":
                    handle.write("\n")
        handle.write("\n".join(lines) + "\n")
    return len(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--only", nargs="*", default=None, help="render only these IDs")
    parser.add_argument("--keep-wav", type=Path, default=None, help="also write 16-bit WAV masters here")
    parser.add_argument("--no-provenance", action="store_true", help="do not touch assets/PROVENANCE.csv")
    args = parser.parse_args(argv)

    unknown = [asset_id for asset_id in (args.only or []) if asset_id not in BY_ID]
    if unknown:
        parser.error(f"unknown ID(s): {', '.join(unknown)}")

    rendered: list[tuple[Asset, int, Path]] = []
    for asset in ASSETS:
        if args.only and asset.id not in args.only:
            continue
        for variation in range(1, asset.variations + 1):
            samples = render(asset, variation)
            path = output_path(asset, variation)
            write_ogg(path, samples)
            if args.keep_wav:
                write_wav(args.keep_wav / path.with_suffix(".wav").name, samples)
            rendered.append((asset, variation, path))
            channels = 1 if samples.ndim == 1 else samples.shape[1]
            level = (
                f"{integrated_lufs(samples, SR):.1f} LUFS"
                if samples.ndim == 2
                else f"peak {peak_db(samples):.1f} dBFS"
            )
            print(f"[gen ] {path.relative_to(ROOT).as_posix()}  "
                  f"{len(samples) / SR:.3f}s {channels}ch {level}")

    if not args.no_provenance:
        added = append_provenance(rendered)
        print(f"[prov] {added} provenance row(s) added")

    print(f"{len(rendered)} file(s) rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

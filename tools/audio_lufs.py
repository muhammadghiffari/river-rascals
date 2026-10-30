"""ITU-R BS.1770-4 loudness metering shared by the audio tools.

Pure numpy/scipy offline helpers: K-weighting, gated integrated loudness, sample peak.
Lives in ``tools/`` because it is authoring/QA tooling, never game runtime code
(``src/rr/core`` must stay dependency free).

Reference: ITU-R BS.1770-4 (2015), EBU R128 for the gate layout.
"""
from __future__ import annotations

import numpy as np
from scipy import signal  # type: ignore[import-untyped]

# Silence floor so log10 never sees 0; -240 dBFS is far below any real content.
_EPS = 1e-12
# BS.1770 channel weights: L = R = 1.0 for stereo/left-right layouts.
_CHANNEL_WEIGHTS = (1.0, 1.0, 1.0, 1.41, 1.41)


def db(value: float) -> float:
    """Convert a linear amplitude to dBFS (clamped at -240 dB)."""
    return 20.0 * float(np.log10(max(abs(float(value)), _EPS)))


def peak_db(samples: np.ndarray) -> float:
    """Sample peak of a mono or ``(frames, channels)`` signal in dBFS."""
    x = np.asarray(samples, dtype=np.float64)
    return db(float(np.max(np.abs(x)))) if x.size else float("-inf")


def rms_db(samples: np.ndarray) -> float:
    """RMS level of the whole signal in dBFS."""
    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return float("-inf")
    return db(float(np.sqrt(np.mean(np.square(x)))))


def _k_weighting_sos(sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (shelf_sos, highpass_sos) of the BS.1770 K-weighting filter at ``sr``."""
    # Stage 1: high shelf (+4 dB above ~1.7 kHz).
    f0, gain_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = np.tan(np.pi * f0 / sr)
    vh = 10.0 ** (gain_db / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    shelf_b = np.array([
        (vh + vb * k / q + k * k) / a0,
        2.0 * (k * k - vh) / a0,
        (vh - vb * k / q + k * k) / a0,
    ])
    shelf_a = np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0])

    # Stage 2: 38 Hz high pass (RLB weighting).
    f0, q = 38.13547087602444, 0.5003270373238773
    k = np.tan(np.pi * f0 / sr)
    denom = 1.0 + k / q + k * k
    hp_b = np.array([1.0, -2.0, 1.0])
    hp_a = np.array([1.0, 2.0 * (k * k - 1.0) / denom, (1.0 - k / q + k * k) / denom])

    return (np.array([[*shelf_b, *shelf_a]]), np.array([[*hp_b, *hp_a]]))


def k_weight(samples: np.ndarray, sr: int = 44100) -> np.ndarray:
    """Apply K-weighting along axis 0; accepts mono or ``(frames, channels)``."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    shelf, highpass = _k_weighting_sos(sr)
    # Filter channel by channel: scipy's 2-D handling assumes (channels, frames).
    return np.stack(
        [signal.sosfilt(highpass, signal.sosfilt(shelf, x[:, ch])) for ch in range(x.shape[1])],
        axis=1,
    )


def _block_energies(y: np.ndarray, sr: int, block_s: float, hop_s: float) -> np.ndarray:
    """Mean-square energy per gating block (channels summed with BS.1770 weights)."""
    n_block = max(1, int(round(block_s * sr)))
    n_hop = max(1, int(round(hop_s * sr)))
    if y.shape[0] < n_block:
        return np.array([float(np.sum(np.mean(np.square(y), axis=0) * _CHANNEL_WEIGHTS[: y.shape[1]]))])

    sq = np.square(y)
    cumulative = np.vstack([np.zeros((1, sq.shape[1])), np.cumsum(sq, axis=0)])
    starts = np.arange(0, sq.shape[0] - n_block + 1, n_hop)
    sums = cumulative[starts + n_block] - cumulative[starts]  # (blocks, channels)
    energy = (sums / n_block) @ np.asarray(_CHANNEL_WEIGHTS[: sq.shape[1]])
    return np.asarray(energy, dtype=np.float64)


def integrated_lufs(samples: np.ndarray, sr: int = 44100) -> float:
    """Gated integrated loudness in LUFS (BS.1770-4, 400 ms blocks / 100 ms hop).

    Returns ``-inf`` when every block falls below the -70 LUFS absolute gate.
    """
    y = k_weight(samples, sr)
    energy = _block_energies(y, sr, block_s=0.4, hop_s=0.1)
    if energy.size == 0:
        return float("-inf")

    with np.errstate(divide="ignore"):
        block_lufs = -0.691 + 10.0 * np.log10(np.maximum(energy, _EPS))

    above_absolute = block_lufs > -70.0
    if not np.any(above_absolute):
        return float("-inf")

    relative_gate = -0.691 + 10.0 * np.log10(float(np.mean(energy[above_absolute]))) - 10.0
    keep = above_absolute & (block_lufs > relative_gate)
    if not np.any(keep):
        return float("-inf")

    return float(-0.691 + 10.0 * np.log10(float(np.mean(energy[keep]))))

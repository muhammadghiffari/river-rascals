"""Unit tests for the audio gate helpers (tools/check_audio.py, tools/audio_lufs.py)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import check_audio  # noqa: E402
from audio_lufs import db, integrated_lufs, peak_db, rms_db  # noqa: E402

SR = 44100


def sine(freq: float = 997.0, seconds: float = 3.0, amplitude: float = 0.1) -> np.ndarray:
    t = np.arange(int(round(seconds * SR))) / SR
    return amplitude * np.sin(2.0 * np.pi * freq * t)


class TestLoudness(unittest.TestCase):
    """The gate is only meaningful if the meter matches BS.1770 calibration."""

    def test_bs1770_calibration_1khz(self) -> None:
        # -20 dBFS RMS 997 Hz sine in one channel reads -23.0 LUFS (BS.1770 reference).
        self.assertAlmostEqual(integrated_lufs(sine(amplitude=0.1), SR), -23.0, delta=0.2)

    def test_stereo_is_3lu_hotter_than_mono(self) -> None:
        mono = sine()
        stereo = np.stack([mono, mono], axis=1)
        self.assertAlmostEqual(integrated_lufs(stereo, SR) - integrated_lufs(mono, SR), 3.0, delta=0.1)

    def test_doubling_amplitude_adds_6lu(self) -> None:
        quiet = integrated_lufs(sine(amplitude=0.05), SR)
        loud = integrated_lufs(sine(amplitude=0.1), SR)
        self.assertAlmostEqual(loud - quiet, 6.0, delta=0.1)

    def test_silence_is_negative_infinity(self) -> None:
        self.assertEqual(integrated_lufs(np.zeros(SR * 2), SR), float("-inf"))

    def test_short_signal_below_gate(self) -> None:
        # 20 ms bursts gated out by the 400 ms block -> no gated loudness.
        x = np.zeros(int(0.2 * SR))
        x[: int(0.02 * SR)] = sine(seconds=0.02, amplitude=0.001)
        self.assertEqual(integrated_lufs(x, SR), float("-inf"))

    def test_peak_and_rms(self) -> None:
        self.assertAlmostEqual(peak_db(sine(amplitude=0.5)), db(0.5), places=5)
        self.assertAlmostEqual(rms_db(sine(amplitude=0.5)), db(0.5 / np.sqrt(2.0)), delta=0.1)


class TestListParsing(unittest.TestCase):
    """Rows and file names must map deterministically; wrong names must not slip through."""

    def test_parse_name_with_and_without_variation(self) -> None:
        self.assertEqual(check_audio.parse_name("SFX_RaftCreak_02"), ("SFX_RaftCreak", 2))
        self.assertEqual(check_audio.parse_name("MUS_Ch1_Base"), ("MUS_Ch1_Base", None))
        self.assertEqual(check_audio.parse_name("UI_Back_01"), ("UI_Back", 1))

    def test_variation_count_from_notes(self) -> None:
        def entry(notes: str) -> check_audio.Entry:
            return check_audio.Entry("X_Y", "SFX", 1.0, False, "P0", notes)

        self.assertEqual(entry("4 variations, random pitch").variations, 4)
        self.assertEqual(entry("3").variations, 3)
        self.assertEqual(entry("pitch up on streak").variations, 1)
        self.assertEqual(entry("stem A - always playing").variations, 1)

    def test_duration_tolerance(self) -> None:
        self.assertTrue(check_audio.duration_ok(1.19, 1.2))
        self.assertTrue(check_audio.duration_ok(0.48, 0.5))
        self.assertFalse(check_audio.duration_ok(1.5, 1.2))
        self.assertFalse(check_audio.duration_ok(90.0, 96.0))


class TestSeam(unittest.TestCase):
    """Loop rows are rejected when the wrap-around clicks."""

    def test_continuous_sine_has_clean_seam(self) -> None:
        cycles = 44100 * 2
        period = SR / 220.0
        n = int(round(cycles / period)) * int(round(period))
        x = np.sin(2.0 * np.pi * 220.0 * np.arange(n) / SR)
        jump, delta = check_audio.seam_metrics(x)
        self.assertLess(jump, 0.05)
        self.assertLess(delta, 1.0)

    def test_truncated_loud_tail_fails(self) -> None:
        x = np.zeros(SR)
        x[: SR // 2] = 0.9  # hard cut to silence at the end -> audible click
        jump, delta = check_audio.seam_metrics(x)
        self.assertGreater(jump, check_audio.SEAM_MAX_JUMP)

    def test_fade_to_silence_is_detected(self) -> None:
        # A loop that ends in a 60 ms fade would dip to -inf at the wrap.
        tail = np.zeros(int(0.05 * SR))
        self.assertLess(rms_db(tail), check_audio.SEAM_MIN_TAIL_DB)


class TestListLoads(unittest.TestCase):
    """The shipped list must stay parseable and complete."""

    def test_list_parses_all_rows(self) -> None:
        entries = check_audio.load_entries(check_audio.DEFAULT_LIST)
        self.assertEqual(len(entries), 64)
        ids = {entry.id for entry in entries}
        for asset_id in (
            "SFX_RaftCreak",
            "SFX_SplashBig",
            "SFX_CoinPickup",
            "SFX_FishPickup",
            "SFX_Checkpoint",
            "SFX_Finish",
            "SFX_OtterChirp",
            "SFX_OtterPanic",
            "UI_Confirm",
            "UI_Back",
            "MUS_Ch1_Base",
            "MUS_Ch1_Rhythm",
        ):
            self.assertIn(asset_id, ids)
        music = next(entry for entry in entries if entry.id == "MUS_Ch1_Base")
        self.assertTrue(music.loop)
        self.assertEqual((music.category, music.duration_s), ("Music", 96.0))


if __name__ == "__main__":
    unittest.main()

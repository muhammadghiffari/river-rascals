#!/usr/bin/env python3
"""Original deterministic DSP assets; offline numpy/soundfile + FFmpeg, no runtime dependencies.

Existing files are never overwritten. --validate-only checks delivered Vorbis, not source PCM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 44100
ROOT = Path(__file__).resolve().parents[1]
# path, synthesis family, duration, seed. Seeds are stable across runs.
SPECS = [
    (f"sfx/{prefix}_{i:02d}.ogg", kind, duration, seed + i)
    for prefix, kind, duration, count, seed in [
        ("SFX_PaddleDip", "dip", .4, 3, 100),
        ("SFX_PaddlePull", "pull", .8, 3, 200),
        ("SFX_PaddleExit", "exit", .5, 3, 300),
        ("SFX_SplashSmall", "splash", .6, 4, 400),
        ("SFX_RaftBumpHard", "hard", .8, 3, 500),
        ("SFX_WaterRushLoop", "rush", 8., 1, 600),
        ("AMB_Creek", "creek", 60., 1, 700),
    ]
    for i in range(1, count + 1)
]
SPECS = [(p.replace("sfx/AMB_", "ambience/AMB_"), k, d, s) for p, k, d, s in SPECS]


def noise(rng, n, rate, low, high):
    """FFT-shaped periodic noise: smooth frequency skirts, no DC, no filter reset seam."""
    frequencies = np.fft.rfftfreq(n, 1 / rate)
    spectrum = np.fft.rfft(rng.normal(size=n))
    shape = (frequencies / (frequencies + low)) ** 2 / (1 + (frequencies / high) ** 4)
    spectrum *= shape
    spectrum[0] = 0
    result = np.fft.irfft(spectrum, n=n)
    return result / max(float(np.std(result)), 1e-9)


def droplets(rng, t, count, start, end):
    """Damped, rising-frequency bubble resonances with separate small surface ticks."""
    out = np.zeros_like(t)
    for _ in range(count):
        age = t - rng.uniform(start, end)
        u = np.maximum(age, 0)
        frequency = rng.uniform(420, 1600)
        envelope = (1 - np.exp(-u * 1800)) * np.exp(-u * rng.uniform(35, 80))
        out += rng.uniform(.035, .10) * envelope * np.sin(
            2 * np.pi * frequency * (u + .65 * u * u)) * (age >= 0)
    return out


def synthesize(kind, duration, seed, rate=RATE):
    rng = np.random.default_rng(seed)
    n = round(duration * rate)
    t = np.arange(n) / rate
    if kind in ("rush", "creek"):
        shared = noise(rng, n, rate, 90, 1800)
        channels = []
        for channel in range(2):
            bed = .65 * shared + .35 * noise(rng, n, rate, 140, 3000)
            # Integer-cycle modulation preserves the periodic boundary.
            swell = .72 + .15 * np.sin(2 * np.pi * 3 * t / duration + channel * .3)
            swell += .08 * np.sin(2 * np.pi * 7 * t / duration)
            signal = .12 * bed * swell
            if kind == "creek":
                signal *= .6
                signal += droplets(rng, t, round(duration * 5), .1, duration - .4) * .35
                # Sparse, original two-note bird gestures; no recordings or imitations.
                for onset in np.arange(1.3 + channel * .45, duration - .7, 7.1):
                    u = np.maximum(t - onset, 0)
                    env = np.sin(np.pi * np.clip(u / .22, 0, 1)) ** 2
                    env *= (u < .22) & (t >= onset)
                    signal += .018 * env * np.sin(2 * np.pi * (2100 * u + 850 * u * u))
            # A 10ms local boundary correction retains energy instead of a fade-to-silence seam.
            width = max(2, round(.01 * rate))
            weight = .5 - .5 * np.cos(np.linspace(0, np.pi, width))
            signal[-width:] += (signal[0] - signal[-1]) * weight
            channels.append(signal)
        result = np.column_stack(channels)
        return result * min(1., .60 / max(float(np.max(np.abs(result))), 1e-9))
    water = noise(rng, n, rate, 180, 3300)
    if kind == "hard":
        result = .16 * water * np.exp(-t * 38)
        for frequency, decay, gain in [(95, 11, .5), (187, 17, .24), (433, 23, .13), (930, 45, .08)]:
            f = frequency * rng.uniform(.95, 1.05)
            result += gain * np.sin(2 * np.pi * f * t) * np.exp(-t * decay)
        result += .10 * water * np.exp(-((t - .035) / .009) ** 2)
    elif kind == "pull":
        envelope = np.sin(np.pi * t / duration) ** 1.5
        result = .16 * water * envelope * (1 + .14 * np.sin(2 * np.pi * 11 * t))
        result += droplets(rng, t, 9, .04, duration - .10)
    elif kind in ("dip", "exit", "splash"):
        decay = {"dip": 16, "exit": 22, "splash": 10}[kind]
        result = .23 * water * (1 - np.exp(-t * 170)) * np.exp(-t * decay)
        result += droplets(rng, t, 12 if kind == "splash" else 7, .015, duration - .09)
        if kind == "dip":
            result += .3 * np.sin(2 * np.pi * (170 * t + 220 * t * t)) * np.exp(-t * 28)
    else:
        raise ValueError(f"Unknown synthesis family: {kind}")
    result -= np.mean(result)
    fade = max(2, round(.005 * rate))
    result[:fade] *= np.linspace(0, 1, fade)
    result[-fade:] *= np.linspace(1, 0, fade)
    return result * (.60 / max(float(np.max(np.abs(result))), 1e-9))


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def loudness(exe, path):
    run = subprocess.run([exe, "-hide_banner", "-i", str(path), "-af",
                          "loudnorm=I=-24:TP=-3:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True, check=True)
    match = re.search(r'\{\s*"input_i".*?\}', run.stderr, re.S)
    if match is None:
        raise RuntimeError("FFmpeg did not return loudness measurements")
    return json.loads(match.group())


def measure(path, loop=False):
    data, rate = sf.read(path, always_2d=True)
    info = sf.info(path)
    peak = float(np.max(np.abs(data)))
    seam = float(np.max(np.abs(data[0] - data[-1])))
    step = float(np.quantile(np.abs(np.diff(data, axis=0)), .99))
    return {
        "file": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "codec": f"{info.format}/{info.subtype}", "sample_rate": rate, "channels": data.shape[1],
        "duration_s": len(data) / rate, "peak_dbfs": 20 * math.log10(max(peak, 1e-12)),
        "clipped_samples": int(np.count_nonzero(np.abs(data) >= 1)),
        "finite": bool(np.isfinite(data).all()), "dc": float(np.max(np.abs(np.mean(data, axis=0)))),
        "loop": loop, "seam_jump": seam, "step_p99": step,
        "edge_rms": float(np.sqrt(np.mean(np.concatenate((data[:441], data[-441:])) ** 2))),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    audio = ROOT / "assets/audio"
    exe = ffmpeg_exe()
    if not args.validate_only:
        # Temporary files stay within the authorized worktree; original audio never touched.
        with tempfile.TemporaryDirectory(prefix=".audio-", dir=audio) as temporary:
            wav = Path(temporary) / "render.wav"
            for relative, kind, duration, seed in SPECS:
                target = audio / relative
                if target.exists():
                    continue
                signal = synthesize(kind, duration, seed)
                sf.write(wav, signal, RATE, subtype="FLOAT")
                if kind in ("rush", "creek"):
                    gain = 10 ** ((-24 - float(loudness(exe, wav)["input_i"])) / 20)
                    signal *= min(gain, .60 / float(np.max(np.abs(signal))))
                    sf.write(wav, signal, RATE, subtype="FLOAT")
                target.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-n", "-i", str(wav),
                                "-c:a", "libvorbis", "-q:a", "5", str(target)], check=True)
    specs = {relative: (kind, duration) for relative, kind, duration, _ in SPECS}
    report = []
    for path in sorted(audio.rglob("*.ogg")):
        relative = path.relative_to(audio).as_posix()
        kind, duration = specs.get(relative, ("existing", None))
        loop = kind in ("rush", "creek") or path.stem == "MUS_Menu_01"
        row = measure(path, loop)
        if loop:
            levels = loudness(exe, path)
            row["integrated_lufs"] = float(levels["input_i"])
            row["true_peak_dbfs"] = float(levels["input_tp"])
        checks = [row["codec"] == "OGG/VORBIS", row["sample_rate"] == RATE,
                  row["finite"], row["clipped_samples"] == 0]
        if duration is not None:
            checks += [abs(row["duration_s"] - duration) < 1 / RATE,
                       row["channels"] == (2 if loop else 1), row["peak_dbfs"] <= -3]
        if loop:
            checks += [row["seam_jump"] < .015, row["seam_jump"] < 3 * row["step_p99"],
                       row["edge_rms"] > .001]
        if kind in ("rush", "creek"):
            checks += [abs(row["integrated_lufs"] + 24) <= 1, row["true_peak_dbfs"] <= -3]
        row["passed"] = all(checks)
        report.append(row)
        print(f"{'PASS' if row['passed'] else 'FAIL'} {relative}: {row['duration_s']:.3f}s "
              f"{row['channels']}ch peak={row['peak_dbfs']:.2f}dBFS seam={row['seam_jump']:.6f}")
    missing = sorted(set(specs) - {p.relative_to(audio).as_posix() for p in audio.rglob("*.ogg")})
    result = {"generator": "tools/generate_prototype_audio.py", "sample_rate": RATE,
              "auditioned": False, "missing": missing, "files": report}
    (ROOT / "docs/prototype_audio_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    if missing or not all(row["passed"] for row in report):
        raise SystemExit(1)
    print(f"Validated {len(report)} Vorbis files; {len(SPECS)} original procedural assets. NOT auditioned.")


if __name__ == "__main__":
    main()

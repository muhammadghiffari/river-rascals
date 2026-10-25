#!/usr/bin/env python3
"""Collect a hardware-profile row for ``docs/16_HARDWARE_PROFILES.md``.

Linux uses ``lscpu``, ``/proc/meminfo``, ``lspci -nnk``, ``/etc/os-release``,
``glxinfo -B``, ``xrandr`` and the DMI/DRM sysfs nodes. Windows uses PowerShell
``Get-CimInstance``. Every parser is a pure function over command output so the
whole module is unit-testable on any machine (see ``tests/test_hw_profile.py``).

Two rules the output obeys:

* **No invented numbers.** A value the tools cannot report is ``None`` and is
  rendered as ``not reported`` / ``unverified`` with the reason, never guessed.
* **Installed GPUs are not the GPU in use.** The profiler lists what the machine
  has; the GPU the engine actually rendered on is a measurement, so pass a
  benchmark result with ``--bench-result`` and it is quoted from that file's
  ``gpu_renderer``/``gl_vendor`` fields.

Examples::

    python tools/bench/hw_profile.py --format table
    python tools/bench/hw_profile.py --format json
    python tools/bench/hw_profile.py --format table \\
        --bench-result docs/reports/bench/p3_zbook14g2_empty_1280x720.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

GIB = 1024 ** 3


# -- pure parsers -----------------------------------------------------------

def parse_os_release(text: str) -> dict[str, str]:
    """Parse ``/etc/os-release`` into a key/value dict (quotes stripped)."""
    values: dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def parse_lscpu(text: str) -> dict[str, object]:
    """Extract CPU model, core/thread/socket counts from ``lscpu`` output."""
    fields: dict[str, str] = {}
    for line in (text or "").splitlines():
        key, _, value = line.partition(":")
        if value:
            fields[key.strip()] = value.strip()

    def as_int(key: str):
        try:
            return int(fields.get(key, ""))
        except ValueError:
            return None

    return {
        "model": fields.get("Model name") or None,
        "architecture": fields.get("Architecture") or None,
        "cpus": as_int("CPU(s)"),
        "cores_per_socket": as_int("Core(s) per socket"),
        "sockets": as_int("Socket(s)"),
        "threads_per_core": as_int("Thread(s) per core"),
        "max_mhz": fields.get("CPU max MHz") or None,
    }


def parse_meminfo(text: str) -> dict[str, object]:
    """Total RAM from ``/proc/meminfo`` (reported in kB) as bytes and GiB."""
    match = re.search(r"^MemTotal:\s+(\d+)\s*kB", text or "", re.MULTILINE)
    if not match:
        return {"total_kib": None, "total_bytes": None, "total_gib": None}
    kib = int(match.group(1))
    total_bytes = kib * 1024
    return {
        "total_kib": kib,
        "total_bytes": total_bytes,
        "total_gib": round(total_bytes / GIB, 1),
    }


def parse_lspci_display(text: str) -> list[dict[str, str | None]]:
    """Display-class PCI devices from ``lspci -nnk`` (VGA/3D/Display)."""
    devices: list[dict[str, str | None]] = []
    current: dict[str, str | None] | None = None
    for line in (text or "").splitlines():
        header = re.match(
            r"^(\S+)\s+(VGA compatible controller|3D controller|Display controller)"
            r"\s*(\[[0-9a-fA-F]{4}\])?:\s*(.+)$",
            line,
        )
        if header:
            slot, _klass, _code, description = header.groups()
            ids = re.findall(r"\[([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\]", description)
            current = {
                "slot": slot,
                "description": re.sub(r"\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]", "", description).strip(),
                "pci_id": ids[-1] if ids else None,
                "driver": None,
                "subsystem": None,
            }
            devices.append(current)
            continue
        if current is None:
            continue
        # Any unindented line is a new PCI device block: stop attributing its
        # "Kernel driver in use:" to the display controller above it.
        if line and not line[0].isspace():
            current = None
            continue
        driver = re.match(r"^\s+Kernel driver in use:\s*(.+?)\s*$", line)
        if driver:
            current["driver"] = driver.group(1)
        subsystem = re.match(r"^\s+Subsystem:\s*(.+?)\s*$", line)
        if subsystem:
            current["subsystem"] = subsystem.group(1)
    return devices


def parse_glxinfo_b(text: str) -> dict[str, object]:
    """Renderer identity from ``glxinfo -B`` (vendor/device/version/VRAM claim)."""
    vendor = re.search(r"^\s*Vendor:\s*(.+?)\s*$", text or "", re.MULTILINE)
    device = re.search(r"^\s*Device:\s*(.+?)\s*$", text or "", re.MULTILINE)
    memory = re.search(r"^\s*Video memory:\s*(\d+)\s*MB", text or "", re.MULTILINE)
    unified = re.search(r"^\s*Unified memory:\s*(yes|no)", text or "", re.MULTILINE)
    direct = re.search(r"^direct rendering:\s*(yes|no)", text or "", re.MULTILINE | re.IGNORECASE)
    version = re.search(r"^\s*Version:\s*(.+?)\s*$", text or "", re.MULTILINE)
    return {
        "vendor": vendor.group(1) if vendor else None,
        "device": device.group(1) if device else None,
        "version": version.group(1) if version else None,
        "video_memory_mb": int(memory.group(1)) if memory else None,
        "unified_memory": (unified.group(1).lower() == "yes") if unified else None,
        "direct_rendering": (direct.group(1).lower() == "yes") if direct else None,
    }


def parse_xrandr(text: str) -> list[dict[str, object]]:
    """Connected outputs with their current mode and refresh rate."""
    outputs: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in (text or "").splitlines():
        head = re.match(r"^(\S+)\s+(connected|disconnected)\b(.*)$", line)
        if head:
            name, state, rest = head.groups()
            resolution = re.search(r"(\d+)x(\d+)\+", rest)
            current = {
                "output": name,
                "connected": state == "connected",
                "primary": "primary" in rest,
                "resolution": f"{resolution.group(1)}x{resolution.group(2)}" if resolution else None,
                "refresh_hz": None,
            }
            outputs.append(current)
            continue
        if current is None or not current["connected"]:
            continue
        mode = re.match(r"^\s+(\d+)x(\d+)\s+([\d.]+)(\*?)\+?", line)
        if mode and (mode.group(4) == "*" or current["refresh_hz"] is None):
            current["resolution"] = f"{mode.group(1)}x{mode.group(2)}"
            current["refresh_hz"] = float(mode.group(3))
            if mode.group(4) == "*":
                current["refresh_hz"] = float(mode.group(3))
    return outputs


def parse_dmi(text: str) -> dict[str, str]:
    """Parse ``KEY=value`` blocks emitted for the DMI sysfs nodes."""
    values: dict[str, str] = {}
    for line in (text or "").splitlines():
        key, _, value = line.partition("=")
        if key and value.strip():
            values[key.strip()] = value.strip()
    return values


def parse_power_profile(text: str) -> str | None:
    """Normalise a platform power profile string (``powerprofilesctl get``)."""
    value = (text or "").strip().splitlines()
    if not value:
        return None
    first = value[0].strip()
    return first or None


def bytes_to_gib(value) -> float | None:
    """Convert a byte count to GiB, ``None`` when unusable."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return round(number / GIB, 1)


def parse_vram_bytes(text: str) -> int | None:
    """Parse the integer in an amdgpu ``mem_info_vram_total`` node."""
    try:
        return int((text or "").strip())
    except ValueError:
        return None


def parse_powershell_cim(text: str) -> dict[str, object]:
    """Normalise the JSON emitted by the Windows ``Get-CimInstance`` probe.

    Accepts either a single object or a list (one query or many).
    """
    try:
        payload = json.loads(text or "")
    except ValueError:
        return {}
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return {}

    result: dict[str, object] = {"cpu": None, "gpus": [], "ram_gib": None,
                                 "os": None, "model": None, "display": None}

    totals = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        cpu = item.get("CPU")
        if cpu and not result["cpu"]:
            result["cpu"] = cpu
        gpus = item.get("GPUs")
        if isinstance(gpus, list):
            result["gpus"] = [g for g in gpus if isinstance(g, dict)]
        ram = item.get("RAMBytes")
        if isinstance(ram, (int, float)) and ram > 0:
            totals += int(ram)
        os_name = item.get("OS")
        if os_name:
            result["os"] = os_name
        model = item.get("Model")
        if model:
            result["model"] = model
    if totals:
        result["ram_gib"] = round(totals / GIB, 1)
    return result


# -- collectors -------------------------------------------------------------

def _run(command: list[str], timeout: int = 20) -> str:
    """Run a probe command and return stdout (``""`` when unavailable)."""
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=timeout, check=False)
        return completed.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_linux() -> dict[str, object]:
    """Gather Linux hardware facts from the tools that are installed."""
    os_release = parse_os_release(_read("/etc/os-release"))
    cpu = parse_lscpu(_run(["lscpu"]))
    mem = parse_meminfo(_read("/proc/meminfo"))

    dmi_nodes = {
        "Vendor": "/sys/devices/virtual/dmi/id/sys_vendor",
        "Model": "/sys/devices/virtual/dmi/id/product_name",
        "Version": "/sys/devices/virtual/dmi/id/product_version",
        "Board": "/sys/devices/virtual/dmi/id/board_name",
    }
    dmi = parse_dmi("".join(f"{key}={_read(path).strip()}\n" for key, path in dmi_nodes.items()))

    displays_pci = parse_lspci_display(_run(["lspci", "-nnk"])) if shutil.which("lspci") else []
    glx = parse_glxinfo_b(_run(["glxinfo", "-B"], timeout=30)) if shutil.which("glxinfo") else {}
    xrandr = parse_xrandr(_run(["xrandr", "--current"])) if shutil.which("xrandr") else []
    profile = (parse_power_profile(_run(["powerprofilesctl", "get"]))
               if shutil.which("powerprofilesctl") else None)

    vram: list[dict[str, object]] = []
    for node in sorted(Path("/sys/class/drm").glob("card*/device/mem_info_vram_total")):
        size = parse_vram_bytes(_read(str(node)))
        if size:
            vram.append({"node": str(node), "bytes": size, "gib": bytes_to_gib(size)})

    storage = os.statvfs("/")
    return {
        "platform": "linux",
        "os_release": os_release,
        "dmi": dmi,
        "cpu": cpu,
        "memory": mem,
        "pci_display": displays_pci,
        "glx": glx,
        "xrandr": xrandr,
        "power_profile": profile,
        "vram_nodes": vram,
        "storage": {
            "total_gib": round(storage.f_blocks * storage.f_frsize / GIB, 1),
            "free_gib": round(storage.f_bavail * storage.f_frsize / GIB, 1),
        },
    }


WINDOWS_PROBE = (
    "$ErrorActionPreference='SilentlyContinue';"
    "[pscustomobject]@{"
    "Model=(Get-CimInstance Win32_ComputerSystem | ForEach-Object {$_.Manufacturer + ' ' + $_.Model});"
    "OS=(Get-CimInstance Win32_OperatingSystem | ForEach-Object {$_.Caption + ' ' + $_.Version});"
    "CPU=(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name);"
    "RAMBytes=(Get-CimInstance Win32_ComputerSystem | Select-Object -ExpandProperty TotalPhysicalMemory);"
    "GPUs=@(Get-CimInstance Win32_VideoController | ForEach-Object {"
    "[pscustomobject]@{Name=$_.Name;Driver=$_.DriverVersion;"
    "VRAM=$_.AdapterRAM;Width=$_.CurrentHorizontalResolution;Height=$_.CurrentVerticalResolution;"
    "Refresh=$_.CurrentRefreshRate}})"
    "} | ConvertTo-Json -Depth 4 -Compress"
)


def collect_windows() -> dict[str, object]:
    """Gather Windows hardware facts through PowerShell ``Get-CimInstance``."""
    output = _run(["powershell", "-NoProfile", "-Command", WINDOWS_PROBE], timeout=60)
    parsed = parse_powershell_cim(output)
    parsed["platform"] = "windows"
    parsed["raw"] = output.strip() if output.strip() else None
    return parsed


def collect() -> dict[str, object]:
    """Collect facts for the current platform."""
    if sys.platform.startswith("win"):
        return collect_windows()
    return collect_linux()


# -- rendering --------------------------------------------------------------

def _fmt(value, suffix: str = "") -> str:
    if value is None or value == "":
        return "not reported"
    return f"{value}{suffix}"


def build_fields(facts: dict[str, object], *, tier: str | None = None,
                 bench: dict[str, object] | None = None) -> list[tuple[str, str]]:
    """Turn collected facts into (field, value) rows for the docs/16 table."""
    rows: list[tuple[str, str]] = []

    if facts.get("platform") == "windows":
        gpus = facts.get("gpus") or []
        gpu_text = "; ".join(
            f"{g.get('Name', 'GPU')} (driver {g.get('Driver') or 'not reported'})"
            for g in gpus
        ) or "not reported"
        display = None
        for gpu in gpus:
            if gpu.get("Width") and gpu.get("Height"):
                display = f"{gpu['Width']}x{gpu['Height']}"
                if gpu.get("Refresh"):
                    display += f" @ {gpu['Refresh']} Hz"
                break
        vram = None
        for gpu in gpus:
            gib = bytes_to_gib(gpu.get("VRAM"))
            if gib:
                vram = f"{gib} GiB reported by AdapterRAM (may be capped at 4 GiB on some drivers)"
                break
        rows += [
            ("Model", _fmt(facts.get("model"))),
            ("OS / version", _fmt(facts.get("os"))),
            ("CPU", _fmt(facts.get("cpu"))),
            ("GPU (dedicated/iGPU) + driver", gpu_text),
            ("VRAM / shared", vram or "not reported"),
            ("RAM", _fmt(facts.get("ram_gib"), " GiB")),
            ("Storage free (SSD/HDD)", "not reported"),
            ("Display res/refresh", _fmt(display)),
            ("Power mode used for tests", "not recorded"),
        ]
        if tier:
            rows.insert(0, ("Tier", tier))
        return rows

    cpu = facts.get("cpu") or {}
    mem = facts.get("memory") or {}
    os_release = facts.get("os_release") or {}
    dmi = facts.get("dmi") or {}
    glx = facts.get("glx") or {}
    storage = facts.get("storage") or {}
    pci = facts.get("pci_display") or []

    model_bits = " ".join(filter(None, [dmi.get("Vendor"), dmi.get("Model"), dmi.get("Version")]))
    model_bits = model_bits.strip()
    if dmi.get("Board"):
        model_bits += f", board {dmi['Board']}"

    cpu_text = _fmt(cpu.get("model"))
    cores = cpu.get("cores_per_socket")
    threads = cpu.get("threads_per_core")
    sockets = cpu.get("sockets")
    if cores and threads and sockets:
        cpu_text += f", {sockets * cores} cores / {sockets * cores * threads} threads"

    gpu_parts = []
    for device in pci:
        driver = device.get("driver") or "not reported"
        gpu_parts.append(f"{device.get('description')} ({device.get('pci_id')}, driver {driver})")
    gpu_text = "; ".join(gpu_parts) or "not reported"

    vram_parts = []
    for node in facts.get("vram_nodes") or []:
        vram_parts.append(f"{node.get('gib')} GiB dedicated ({node.get('node')})")
    if glx.get("unified_memory") is not None:
        claim = glx.get("video_memory_mb")
        vram_parts.append(
            "iGPU unified memory"
            + (f", glxinfo reports {claim} MB of shared system RAM" if claim else "")
        )
    vram_text = "; ".join(vram_parts) or "not reported"

    connected = [o for o in (facts.get("xrandr") or []) if o.get("connected")]
    display_text = "; ".join(
        f"{o['output']} {o.get('resolution') or '?'}"
        + (f" @ {o['refresh_hz']:.2f} Hz" if o.get("refresh_hz") else "")
        for o in connected
    ) or "not reported"

    rows += [
        ("Model", model_bits or "not reported"),
        ("OS / version",
         f"{_fmt(os_release.get('PRETTY_NAME'))} ({os_release.get('VERSION_ID', '?')}), "
         f"{cpu.get('architecture') or 'arch not reported'}"),
        ("CPU", cpu_text),
        ("GPU (dedicated/iGPU) + driver", gpu_text),
        ("VRAM / shared", vram_text),
        ("RAM", f"{_fmt(mem.get('total_gib'), ' GiB')} (MemTotal {mem.get('total_kib')} kB)"
                if mem.get("total_kib") else "not reported"),
        ("Storage free (SSD/HDD)",
         f"{storage.get('free_gib')} GiB free of {storage.get('total_gib')} GiB on `/`"
         if storage.get("total_gib") else "not reported"),
        ("Display res/refresh", display_text),
        ("Power mode used for tests", facts.get("power_profile") or "not reported"),
    ]

    if glx.get("device"):
        rows.append((
            "GPU used by UPBGE (measured)",
            bench.get("gpu_renderer") if bench else
            "not measured in this profile run — read the player's GL_RENDERER "
            f"(glxinfo -B on this desktop reports: {glx.get('device')})",
        ))
    if tier:
        rows.insert(0, ("Tier", tier))
    return rows


def render_table(fields: list[tuple[str, str]]) -> str:
    """Markdown rows for the docs/16 table body."""
    width = max((len(name) for name, _ in fields), default=0)
    lines = [f"| {'Field'.ljust(width)} | Value |", f"| {'-' * width} | --- |"]
    lines += [f"| {name.ljust(width)} | {value} |" for name, value in fields]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format", choices=("table", "json"), default="table")
    ap.add_argument("--tier", default=None, help="tier label to add as the first row, e.g. 'C'")
    ap.add_argument("--bench-result", default=None,
                    help="benchmark result JSON whose gpu_renderer is quoted as the GPU actually used")
    args = ap.parse_args(argv)

    facts = collect()

    bench = None
    if args.bench_result:
        try:
            bench = json.loads(Path(args.bench_result).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"[hw] could not read bench result {args.bench_result}: {exc}", file=sys.stderr)
            return 2

    if args.format == "json":
        payload = dict(facts)
        payload["fields"] = build_fields(facts, tier=args.tier, bench=bench)
        payload["bench_result"] = str(args.bench_result) if args.bench_result else None
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(render_table(build_fields(facts, tier=args.tier, bench=bench)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

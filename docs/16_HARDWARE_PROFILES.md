# 16 — Hardware Profiles & Machine Status
Authors did **not** have the exact specs; each owner fills their row in week 1 (F-04/F-05).

| Field | P1 machine | P2 — ASUS V16 (Tier A) | P3 — mid-spec laptop (Tier B) |
|---|---|---|---|
| Model | | ASUS V16 `V3607VH` (baseboard `V3607VH`, SMBIOS reports no system SKU) — **Tier A** | |
| OS / version | | Windows 11 Home Single Language, build `10.0.26300`, 64-bit | |
| CPU | | Intel Core 5 210H, 8 cores / 12 threads, 2.2 GHz (Win32 `MaxClockSpeed`) | |
| GPU (dedicated/iGPU) + driver | | dGPU **NVIDIA GeForce RTX 5050 Laptop GPU**, driver `32.0.16.1071` (2026-06-28); iGPU **Intel(R) Graphics**, driver `32.0.101.7076` (2025-09-12). Neither controller name is enough to tell which one renders UPBGE — check `blender_system_info.cmd` on the first baseline run | |
| VRAM / shared | | 8 GB dedicated dGPU (7.96 GiB, `HardwareInformation.qwMemorySize`; WMI `AdapterRAM` is capped at ~4 GB and is wrong); iGPU shares system RAM | |
| RAM | | 16 GB, single 16 GB DDR5-5600 SO-DIMM (Samsung `M425R2GA3EB0-CWMOM`), running at 5200 MT/s | |
| Storage free (SSD/HDD) | | NVMe `WD PC SN5000S SDEQNSJ-512G-1002` (476.9 GiB): `C:` **20.3 GiB free** of 355.4 GiB; `D:` 96.5 GiB free of 119.9 GiB. `C:` is tight — keep the UPBGE build and LFS cache on `D:` or free space before baseline runs | |
| Display res/refresh | | 1920×1200 panel (`MNG007QX2-2`), 60 Hz (only mode the panel advertises); Windows desktop currently 1536×960 at 150 % scaling | |
| Power mode used for tests | plugged-in, high performance (always record) | **Not yet set up for tests**: measured on battery (`PowerOnline=False`, 60 % charge) with the **Balanced** plan. Before recording baseline fps: plug in the AC adapter and switch to High performance | |

## Baseline scenes (record in each machine's build)
| Scene | Preset | Res | fps avg | fps min | notes |
|---|---|---|---|---|---|
| Empty scene | Low | 1080p | | | |
| 100k tris static | Low | 1080p | | | |
| 250k tris + 1 sun shadow | Low/Med | 1080p | | | |
| Raft + water + 20 props (S-07) | Low/Med/High | 1080p | | | |

## Interpretation rules
- If Tier B average < 30 fps on the 250k-tri scene at Low ⇒ reduce scene budgets in `04` §4 and set 720p/75 % default for Low.
- Laptops throttle: test plugged in, record temps if possible, run ≥ 5 minutes.

## MCP status (P2 fills)
addon works inside UPBGE 0.50: yes (cube create/delete via MCP verified, see PR #65 comment); note: import bge fails in the editor context via MCP (aud imports), runtime import not verified
| Item | Value |
|---|---|
| Blender/UPBGE version | **UPBGE 0.50** portable, Blender base **5.0.1** (`bpy.app.version_string` = `5.0.1`, build hash `9fcf0da621c3`, built 2026-01-03), `%UPBGE_PATH%` = `C:\Users\Radith\Downloads\upbge-0.50-windows-x64\upbge-0.50-windows-x64`. Installer `upbge-0.50-windows-x64.7z` (293,316,768 bytes) **SHA256 `c59198cbe361afa9d78f515751d2a34f3df236f137393111fd8cc4b43e1dce71`** — recomputed locally on 2026-10-24 and matches. `blender.exe` SHA256 `345f0a0b6b8658c42529fd727fd8135fca7715caf969cc064e303d0e3729d181` |
| MCP package + version | `mcp-for-blender` **2.2.4** (PyPI, verified 2026-10-24; `blender-mcp` 2.0.0 is now only a rename shim). Bundled addon `blender_mcp.py` version **1.8**, addon protocol **15**. Run as `uvx mcp-for-blender`, uv 0.11.21 |
| Addon works in UPBGE? | **Loads and registers: yes** (2026-10-24). Installed to `%APPDATA%\UPBGE\Blender\5.0\scripts\addons\blender_mcp.py`; `tools/blender/probe_mcp_addon.py` run headless reports `enable_result = OK`, `has_panel_class/has_start_operator/has_auto_start_property = True`, exit code 0. **Not yet proven**: the socket round-trip and the create-cube/delete-cube MCP call (OpenCode ↔ addon server) — that is the remaining `techart` step of F-04 |
| Fallback used? | None. UPBGE 0.50 is the authoring build; no vanilla-Blender fallback needed so far |
| Issues/workarounds | (1) `install-addon` auto-discovery only scans `%APPDATA%\Blender Foundation\Blender\<ver>`; UPBGE keeps user files under **`%APPDATA%\UPBGE\Blender\5.0`**, so the CLI must be given `--addons-dir` (or `BLENDERMCP_ADDONS_DIR`) explicitly. (2) Env var names in `opencode.json` still apply to 2.2.4: `BLENDER_HOST`/`BLENDER_PORT` are read by the server (`server.py`) and `DISABLE_TELEMETRY` is honoured (`telemetry.py` also accepts `BLENDER_MCP_DISABLE_TELEMETRY`/`MCP_DISABLE_TELEMETRY`) — **no config change needed**. (3) Telemetry is opt-in in 2.2.4 (addon preference "Allow Telemetry", default off) and off again via `DISABLE_TELEMETRY`; the addon additionally runs an update check 5 s after startup (network, not telemetry) which `BLENDERMCP_NO_UPDATE_CHECK=1` suppresses. (4) In the GUI the sidebar button reads **"Connect to MCP server"** (operator `blendermcp.start_server`); `docs/08` §3 was corrected accordingly. (5) `blender.exe` is not on `PATH`, so agents must call `& "$env:UPBGE_PATH\blender.exe"` |

Setup commands used on P2 (2026-10-24, PowerShell, uv 0.11.21):

```powershell
python scripts/check_env.py                       # Result: READY
uvx mcp-for-blender install-addon --addons-dir "$env:APPDATA\UPBGE\Blender\5.0\scripts\addons"
uvx mcp-for-blender addon-paths                   # with BLENDERMCP_ADDONS_DIR set to the line above
& "$env:UPBGE_PATH\blender.exe" -b --factory-startup --python tools/blender/probe_mcp_addon.py   # exit 0
```

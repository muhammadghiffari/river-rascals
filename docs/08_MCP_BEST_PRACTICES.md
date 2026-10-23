# 08 — MCP Best Practices for OpenCode (Blender / UPBGE project)

## 1. Principles
1. **MCP only when a CLI/built-in tool can't do the job.** `git`, `gh`, `python`, file edit/read, grep are built-in or CLI ⇒ cheaper and more reliable than MCP. (We therefore leave the GitHub MCP **disabled**; agents use `gh`.)
2. **Every enabled MCP tool consumes context** (tool schemas are sent each request). Enable the minimum, and **scope tools per agent** (`permission: {"blender_*": "deny"}` globally, `"allow"` only for `techart`; the older `tools` boolean map is deprecated since OpenCode 1.1.1 but still accepted).
3. **Least privilege & isolation.** MCP servers that execute code (Blender) run only on dev machines, on working copies, never with secrets in reach.
4. **Pin and verify.** Record versions; run `opencode mcp list` after changes; re-test after engine/addon upgrades.
5. **Prompt the tool, not the hope**: small steps, ask for scene info after each step, require measured numbers.

## 2. Recommended MCP set
| Server | Purpose | Type | Default | Used by | Notes |
|---|---|---|---|---|---|
| **blender** (`uvx mcp-for-blender`) | create/inspect/modify objects, materials, run bpy, scene info, CC0 asset download hooks | local (stdio) | on for P2's machine, tools gated to `techart` | techart | needs Blender/UPBGE running with addon; see §3 |
| **context7** | up-to-date library docs lookup (Python stdlib, bpy/Blender API pages indexed there, etc.) | remote | on | all coding agents | ask for specific library + topic; do not rely on it for UPBGE-specific APIs unless indexed — otherwise `webfetch` the UPBGE docs |
| github | GitHub issues/PRs | remote (needs token) | **off** | — | enable only if `gh` CLI is unavailable |
Not recommended now: filesystem/git MCPs (redundant), browser/Playwright (no web UI), "sequential-thinking" (reasoning models + effort setting cover it). **Optional future custom MCP `upbge-runner`**: wraps `tools/run_game.py --smoke` and returns JSON + screenshot to agents (build only after M2 if smoke automation becomes a bottleneck).

## 3. Blender MCP setup (P2, ASUS V16)
1. Install `uv` (https://docs.astral.sh/uv/). Verify `uvx --version`.
2. **Package name (verified 2026-10-23)**: the PyPI package `blender-mcp` is now **`mcp-for-blender`** (same project, `ahujasid/blender-mcp` repo). Upstream says existing `blender-mcp` setups keep working, but new installs should use the new name, so `opencode.json` already uses `["uvx","mcp-for-blender"]`. If a future release renames it again, re-check PyPI/GitHub before changing the pin.
3. Install the addon into the **same Blender build you author with** (UPBGE if S-04 passes, else vanilla Blender 4.x/5.x): the addon CLI (`uvx mcp-for-blender install-addon`; `uvx mcp-for-blender addon-paths` lists detected add-on folders) or download `addon.py` → Edit ▸ Preferences ▸ Add-ons ▸ Install → enable "Interface: MCP for Blender". The README lists Blender 3.0+; UPBGE 0.50 (Blender 5.0.1 base) compatibility is **unverified** ⇒ spike S-04.
4. In Blender: 3D View sidebar (N) ▸ MCP for Blender ▸ connect/start server (default `localhost:9876`; the addon and server must use the same `BLENDER_PORT`). Upstream says the add-on starts its server when Blender opens; confirm in the panel. **VERIFY**: the `BLENDER_HOST`/`BLENDER_PORT`/`DISABLE_TELEMETRY` variable names were documented for the old package; confirm they are unchanged for `mcp-for-blender` (S-04).
5. **Disable telemetry**: env `DISABLE_TELEMETRY=true` (already in `opencode.json`) and untick the telemetry/consent option in the addon preferences.
6. Windows quirk: if `uvx` isn't resolved, use `"command": ["cmd","/c","uvx","blender-mcp"]`.
7. Do **not** run `uvx mcp-for-blender` manually in a terminal; OpenCode starts it. Start Blender (addon listening) first, then OpenCode.
8. Verify: `opencode mcp list` shows `blender` connected; in `techart` ask: "get scene info; create a cube named TEST_Cube; delete it".

## 4. Security notes (read!)
- The addon's socket has **no authentication or encryption** — anyone who can reach the port can run Python inside Blender. Keep it on `localhost`, don't forward the port, don't use on shared/public networks, stop the server when not in use.
- `execute_blender_code`-style tools can touch the filesystem. Mitigations: dedicated Blender session; open only the working `.blend`; no credentials in env/home dirs reachable… (assume Python in Blender can read anything the user can) ⇒ **don't keep secrets in plain files on the art machine**; run MCP sessions under a normal user account; commit/checkpoint before long sessions.
- Per-agent gating prevents non-art agents from calling Blender tools. Optional hardening (supported by the `permission` map): set the code-execution tool to `"ask"` for `techart`, e.g. `"permission": {"blender_*": "allow", "blender_execute_blender_code": "ask"}` (check the exact tool name with `opencode mcp list`/the tool picker once connected; last matching rule wins). It slows art flow, so use it for sessions that open untrusted `.blend` files or download third-party assets.
- Third-party assets via MCP (Poly Haven etc.) are CC0 but **still log provenance**; Sketchfab downloads have mixed licences ⇒ avoid unless the licence is verified CC0/CC-BY and attribution is tracked. AI 3D generators (Hyper3D/Hunyuan3D integrations, if enabled) need API keys & terms review: keep **off** by default.

## 5. OpenCode configuration notes
`opencode.json` → `mcp` block (type `local` uses `command` array + `environment`; type `remote` uses `url` and optional `headers`; `enabled` toggles). Remote servers can use OAuth automatically; manage with `opencode mcp list|add|auth|logout|debug`. This block was **loaded and resolved by the real OpenCode CLI (v1.19.4) during the continuation session**; if a future version rejects it, consult that version's docs and fix via PR. Use `{env:VAR}` for secrets in headers.

**Personal overrides (verified with OpenCode 1.19.4):** a project-level `opencode.json` takes precedence over both `~/.config/opencode/opencode.json` and the `OPENCODE_CONFIG` file, so those cannot disable a server the project enables. `opencode.local.json` is **not** read by OpenCode (an earlier draft of this pack was wrong). Use the git-ignored **`.opencode/opencode.jsonc`**, which *is* merged on top: copy `.opencode/opencode.example.jsonc` to `.opencode/opencode.jsonc` (e.g. to set `{"mcp":{"blender":{"enabled":false}}}` on P1's and P3's machines, where Blender is not driven by an agent).

**Provider setup** (`Greg/*` models): the provider is defined per user in `~/.config/opencode/opencode.json`, never in the repo; see `docs/reference/opencode_global_config.example.jsonc`.

## 6. Token & cost hygiene
Keep ≤ 3 MCP servers enabled. Prefer `small_model` for titles/summaries. Start new sessions per task; summarise long sessions into the PR/issue. Avoid giving agents huge tool outputs (ask Blender MCP for summaries, not full scene dumps).

## 7. Troubleshooting
| Symptom | Fix |
|---|---|
| `blender` MCP shows disconnected | Blender not running / addon server not started / port mismatch / firewall blocking localhost |
| Tools missing for techart | Check the `permission` entries (`blender_*`) in `opencode.json`; `opencode mcp list` |
| `uvx` not found | install uv; reopen terminal; Windows `cmd /c` wrapper |
| Old cached server version | `uv cache clean mcp-for-blender blender-mcp` then `uvx --refresh mcp-for-blender` |
| Agent loops on Blender errors | stop, read the Blender console, give the agent the exact traceback and a smaller step |
| Addon incompatible with UPBGE | author in vanilla Blender; append assets into UPBGE scenes (portable-assets rule in 04 §6) |

## 8. Prompt: configure & verify MCP (Agent: builder, deepseek-v4-pro, medium; run on P2's machine)
```text
Goal: get the Blender MCP working with OpenCode on this machine and prove it.
Steps: (1) run scripts/check_env.py; (2) verify uv; (3) re-check PyPI/GitHub for the current Blender MCP package name (expected: `mcp-for-blender`) and install steps; (4) install the addon into the UPBGE build at $UPBGE_PATH (or vanilla Blender if UPBGE fails); (5) confirm the env var names in opencode.json (`BLENDER_HOST`, `BLENDER_PORT`, `DISABLE_TELEMETRY`) still apply to the installed version and fix opencode.json if not; (6) start the addon server; (7) run `opencode mcp list`; (8) as @techart: get scene info, create a cube, apply a material, delete it.
Constraints: telemetry off; no secrets; do not modify files outside the repo and the Blender add-on folder; stop and ask before installing anything system-wide.
Output: a short report in docs/16_HARDWARE_PROFILES.md section "MCP status" with versions, exact commands used, and any workaround needed.
```

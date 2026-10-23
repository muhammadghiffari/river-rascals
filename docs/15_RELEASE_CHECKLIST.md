# 15 — Release Checklist (GO/NO-GO)
Each item needs **evidence** (link, number, screenshot). Any unverified critical item ⇒ NO-GO.

## A. Quality gates
- [ ] CI green on the release commit (link) · [ ] `python -m pytest -q` passes · [ ] ruff clean
- [ ] Asset validation passes on all `.blend` (output attached)
- [ ] Smoke test on Tier A and Tier B meets targets (JSON attached)
- [ ] 60-min soak test: no crash, no memory growth > 200 MB (log attached)
- [ ] Regression checklist (13 §7) complete · [ ] accessibility checklist (13 §8) complete
- [ ] No open S1/S2 bugs; S3 list reviewed and accepted

## B. Content & legal
- [ ] `assets/PROVENANCE.csv` covers every shipped asset file (script check) · [ ] licences compatible with commercial distribution
- [ ] AI-generated assets: tool, plan, date, prompt, terms URL recorded; terms allow commercial use
- [ ] Fonts OFL (or similar) with licence text included in the build · [ ] CREDITS file complete (authors, CC-BY attributions)
- [ ] Title/trademark check done · [ ] age-appropriate content verified

## C. Security & privacy
- [ ] Secret scan over full history clean · [ ] build contains no `.env`, tokens, dev tools, MCP config
- [ ] No network calls in the build (verified by inspection/firewall test) · [ ] save parsing robust (corrupt file test)

## D. Build
- [ ] Version bumped (pyproject, in-game version string), CHANGELOG updated
- [ ] Build produced by `tools/package_build.py` from a clean checkout (steps in §Build below)
- [ ] Clean-machine install/run test (no Blender, no Python) on ≥ 2 machines · [ ] SHA-256 checksum published
- [ ] Size ≤ 1.5 GB · [ ] README/INSTALL/known issues included

## E. Release
- [ ] Release notes (P7.3) · [ ] tag `vX.Y.Z` created by owner after explicit GO · [ ] GitHub Release with zip + checksum
- [ ] Store page assets ready (screenshots, trailer, description) · [ ] post-release feedback channel + bug template ready

## §Build (fill during spike S-06)
```
Engine version/URL/SHA256:
Method used (blenderplayer packaging / publishing addon):
Steps:
1.
Folder structure of the build:
Known issues:
```

## Decision
GO / NO-GO: ____ · Date: ____ · Approved by (human): ____ · Evidence index: ____

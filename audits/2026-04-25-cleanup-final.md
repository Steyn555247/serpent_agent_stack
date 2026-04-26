# Cleanup — Final consolidation (2026-04-25)

> Single canonical record of the 2026-04-25 cleanup pass.
> Supersedes the four working drafts now archived under `archive/`:
>
> - `2026-04-25-cleanup-audit.md` (initial findings + P1/P2/P3 bucketing)
> - `2026-04-25-cleanup-handoff.md` (prior session handoff, test-isolation blocker)
> - `2026-04-25-cleanup-plan.md` (consolidated W#/R#/N# action plan)
> - `2026-04-25-cleanup-plan-factcheck.md` (verification of the plan's specific claims)
>
> Companion docs (still live, not consolidated): `2026-04-23-audit-findings.md`
> (the prior audit, formerly at repo root as `AUDIT_FINDINGS.md`).

This file is structured in three parts:

1. **Findings catalogue** — the original W#/R#/N# items from the plan, each with its
   verification status from the fact-check, and what was actually done in
   Tiers 1-5.
2. **Pending Tier 6+ work** — items the orchestrator deferred or surfaced.
3. **What changed structurally** — short summary of the moves and renames.

---

## 1. Findings catalogue

Status legend:
`✅ verified` — fact-check confirmed the original claim verbatim.
`⚠️ refined` — claim was substantively correct but the description needed adjustment.
`❌ wrong` — original claim was incorrect; fact-check superseded it.
`🆕 new` — discovered during fact-check, not in the original plan.

Done legend:
`DONE Tier N` — landed in the named tier this session.
`PENDING` — still outstanding (see §2).

### 1a. WHAT DOESN'T WORK (W-series)

| ID | Claim | Verify | Disposition |
|---|---|---|---|
| W1 | `scripts/stress_load.py:87,103` references missing `*/halow_bridge.py` | ✅ | DONE Tier 2 — repointed at `*.core.bridge_coordinator`. |
| W2 | `scripts/stress_network_sim.py:258,277` same | ✅ | DONE Tier 2. |
| W3 | `scripts/stress_reconnect.py:75,111` same | ✅ | DONE Tier 2. |
| W4 | `scripts/run_stress_suite.py:104` references missing `tests/test_estop_triggers.py` | ✅ | DONE Tier 2 — repointed at `test_estop.py` + `test_estop_integration.py`. |
| W5 | `dashboard/web_server.py:497-500,589-592` returns HTTP 410 for E-STOP API (functional safety-surface gap) | ✅ | **PENDING — Tier 6+ (safety-gate).** |
| W6 | `command_executor.py:226-232` no-op stubs still called | ✅ | DONE Tier 3 (safety-gate cleared) — stubs + call sites removed. |
| W7 | `autonomous_cutter.py:435-438` `if False:` block | ✅ | DONE Tier 3. |
| W8 | `test_actuator_controller.py::TestBootGrace` test-isolation flake | ✅ | DONE Tier 1 — `_make_controller` now overrides `SERPENT_ESTOP_STATE_PATH` per-test. |
| W9 | `build_repo_map.py:34` mis-buckets `.cpp/.h` as arduino | ✅ | DONE Tier 5 batch 5.2 — bucket scoped to `.ino` only. |
| W10 | `setup_robot_pi.sh:58-66` heredoc-before-mkdir | ⚠️ refined (first-run failure, not just dup) | DONE Tier 4 (safety-gate cleared) — file deleted as part of R1 setup-script consolidation. |
| W11 | `serpent_trimui_app/README.md:38-44` instructs `start.bat` (does not exist) | ✅ | DONE Tier 5 batch 5.3 — README fully rewritten; obsolete reference dropped. |
| W12 | Test cites `SYSTEM_ARCHITECTURE.md §4` "which doesn't exist" | ❌ wrong (§4 exists at repo root) | NO ACTION — original claim was wrong. Section §4 was audited for completeness in Tier 4 batch 4.4. |
| W13 | `base_pi/README.md:23` lists `control_sender.py` / `video_http.py` (wrong filenames) | ✅ | DONE Tier 3. |
| W14 | `pi_halow_bridge/.../README.md:766` "File Structure" lists missing `halow_bridge.py` files | ✅ | DONE Tier 5 batch 5.1 — file structure block fully refreshed. |
| W15 | `.claude/settings.local.json:44` and `BUTTON_MAPPING_REFERENCE.md:236` reference `command_processor.py` (does not exist; actual `command_executor.py`) | ✅ | DONE Tier 3. |
| W16 | ~14 stale "removed 2026-04-23" comments | ⚠️ refined (actual: 15 files) | DONE Tier 3 (safety-gate cleared) — single semantic-zero pass. |
| W17 | trimui `archive/` move uncommitted in git | ⚠️ refined (~25 changes total) | PENDING — by user instruction, no commits this session. |

### 1b. WHAT IS REDUNDANT (R-series)

| ID | Claim | Verify | Disposition |
|---|---|---|---|
| R1 | Top-level `setup_*.sh` vs `scripts/pi_install.sh` + `pi_enable_services.sh` | ✅ | DONE Tier 4 (safety-gate) — top-level set deleted; `SETUP_GUIDE.md` redirected. |
| R2 | `scripts/deploy.sh` + `scripts/rollback.sh` legacy | ✅ | DONE Tier 4 (safety-gate) — both deleted. |
| R3 | `generate_psk.py` duplicated inline in install scripts | ✅ | DONE Tier 4 — install scripts now call `generate_psk.py`. |
| R4 | `install_dashboard.sh` vs `pi_enable_services.sh` overlap | ✅ | DONE Tier 4 (safety-gate) — folded into `pi_enable_services.sh`. |
| R5 | Three dashboard systemd units | ⚠️ refined (not as redundant; serve different shapes) | PENDING — Tier 6+ (`*.service` is safety-critical; renaming `-base-custom` is cosmetic). |
| R6 | Static `dashboard.html` redirect stubs in `base_pi/` and `robot_pi/` | ⚠️ partial verify | DONE Tier 5 batch 5.2 — stubs replaced by 302 in video HTTP server; static dirs deleted. |
| R7 | Six telemetry-bottleneck docs prescribing the same one-line fix | ✅ | DONE Tier 5 batch 5.1 — fix applied (`STATUS_UPDATE_INTERVAL = 1.0`); docs collapsed to a perf note in `SAFETY_HARDENING.md`. |
| R8 | `REFACTORING_*.md` + `PHASE5_COMPLETE.md` build logs | ✅ | DONE Tier 5 batch 5.1 — moved to `archive/docs/`. |
| R9 | Setup-doc constellation (5 files) | ✅ | DONE Tier 5 batch 5.1 — consolidated into `SETUP_GUIDE.md`. |
| R10 | PSK literals in tracked files (SI-12 violation; LAN trusted) | ✅ | DONE Tier 5 batch 5.3 — PSK literals replaced with `<paste-your-PSK-here>` placeholders; policy documented in `SAFETY_HARDENING.md`. |
| R11 | Constants drift across 4 config files | ✅ (file existence) | PENDING — Tier 6+ (touches `common/constants.py`, safety-critical). |
| R12 | Four root-level `test_*.py` bench scripts (pytest-discovery collision) | ✅ | DONE Tier 5 batch 5.2 — moved to `scripts/bench/` with `bench_*.py` rename. |
| R13 | `robot_pi/i2c_multiplexer.py` only used by `scan_i2c_devices.py` | ⚠️ partial verify | DONE Tier 5 batch 5.2 — file deleted; consumer updated to import `adafruit_tca9548a` directly. |
| R14 | `archive/halow_bridge.py.old` (801 LOC) | ✅ | DONE Tier 5 batch 5.1 — deleted. |
| R15 | One-shot diagnostics at bridge root | ✅ | DONE Tier 5 batch 5.2 — `check_telemetry.py` deleted; `check_status.sh`, `restart_robot_bridge.sh`, `test_dashboard.sh` documented in README. |
| R16 | Pi backend lives inside Flutter project | ✅ | DONE Tier 4 batch 4.6 — extracted to `pi_backend/`. |
| R17 | `setup_autostart.sh` vs `setup_simple_autostart.sh` | ✅ | DONE Tier 5 batch 5.3 — `setup_simple_autostart.sh` and `install_dependencies.sh` deleted; `setup_autostart.sh` retained as canonical. |
| R18 | `setup_pi_backend.sh` vs `install_dependencies.sh` overlap | ✅ | DONE Tier 5 batch 5.3 (with R17). |
| R19 | `build_apk.bat` vs `build_apk.ps1` | ✅ (no action needed) | NO ACTION — kept as Windows-shell parity. |
| R20 | 6 button-mapping docs | ✅ | DONE Tier 5 batch 5.3 — `BUTTON_MAPPING_REFERENCE.md` retained; rest archived. |
| R21 | 5 autostart docs | ✅ | DONE Tier 5 batch 5.3 — collapsed; `AUTOSTART_README.md` retained (now in `pi_backend/` per Tier 5 batch 5.4). |
| R22 | 5 Pi-setup docs | ✅ | DONE Tier 5 batch 5.3 + 5.4 — consolidated; `RASPBERRY_PI_BACKEND_SETUP.md` moved to `pi_backend/SETUP.md`. |
| R23 | 3 GitHub-setup docs | ✅ | DONE Tier 5 batch 5.3 — archived. |
| R24 | `BUG_FIX_SUMMARY.md` vs `DIAGNOSTIC_GUIDE.md` self-contradicting | ⚠️ partial verify | DONE Tier 5 batch 5.3 — both archived. |
| R25 | `FIX_CAMERA_AND_ESTOP_PROMPT.md` is a copy-pasted prompt | ✅ | DONE Tier 5 batch 5.3 — archived. |
| R26 | `FINAL_BUILD_SUMMARY.md` predates 20+ commits | ✅ | DONE Tier 5 batch 5.3 — archived. |
| R27 | Unused Flutter deps `permission_handler`, `path_provider` | ✅ | DONE Tier 5 batch 5.2 — both removed; `flutter pub get` re-run. |
| R28 | `serpent-robotics-trimui-app/` empty subdir | ⚠️ partial verify | DONE Tier 5 batch 5.2 — deleted. |
| R29 | `__pycache__/` at trimui root | ✅ | DONE Tier 5 batch 5.2 — deleted; `.gitignore` confirmed. |
| R30 | `build/` 1.4 GB Flutter artifacts | ✅ | DONE Tier 5 batch 5.2 — `flutter clean` run. |
| R31 | `flutter_0[1-4].png` + `frame.jpg` tracked but unreferenced | ✅ | DONE Tier 5 batch 5.2 — moved to `portfolio_screenshots/`. |
| R32 | `agent_stack/.runtime/logs/` no rotation | ✅ | PENDING — Tier 6+ (validate.py change). |
| R33 | `smoke_test.py` undiscoverable | ✅ | DONE Tier 5 batch 5.2 — `/smoke-test` slash command added. |
| R34 | `examples/` not linked from CLAUDE.md | ✅ | DONE Tier 5 batch 5.2 — pointer added. |

### 1c. WHAT IS NOT INTUITIVE (N-series)

| ID | Claim | Verify | Disposition |
|---|---|---|---|
| N1 | `serpent_trimui_app/` " - Copy" suffix is canonical | ✅ | DONE Tier 5 batch 5.1 — renamed to `serpent_trimui_app/`. |
| N2 | `pi_halow_bridge/` wraps a single project | ✅ | DONE Tier 5 batch 5.1 — wrapper renamed; PI-HALOW-BRIDGE retained as inner. |
| N3 | AGENTS.md vs CLAUDE.md distinction not surfaced | (judgement) | DONE Tier 5 batch 5.1 — cross-pointers added to both. |
| N4 | `base_pi/` mixed depth | ✅ | PENDING — Tier 6+ (large surface, low-impact reorganization). |
| N5 | `robot_pi/` single-file sub-packages | ✅ | PENDING — Tier 6+ (same as N4). |
| N6 | Multiple `dashboard.html`/`index.html` files | ⚠️ | DONE Tier 5 batch 5.2 — `dashboard/README.md` updated; redundant statics removed (R6). |
| N7 | `march 16th problems connectivity.md` filename has spaces | ✅ | DONE Tier 5 batch 5.4 — moved to `archive/2026-03-16-connectivity-problems.md`. |
| N8 | Top-level `*.py` and `*.sh` scripts in bridge | ✅ | DONE Tier 5 batch 5.4 — `terminal_dashboard.py` and `diagnose_cameras.py` moved to `scripts/dev/`; `winch_sim.py` moved to `scripts/sim/`. |
| N9 | "30 markdown files at trimui root, no docs/ index" | ⚠️ refined (actual: 28) | DONE Tier 5 batch 5.3 — collapsed to ~10 retained docs; balance archived. |
| N10 | 5 root-level `test_*.py` in trimui | ✅ | DONE Tier 5 batch 5.3 — moved to `pi_backend/scripts/bench/probe_*.py`. |
| N11 | `start_backend_simple.sh` hardcodes wrong path | ⚠️ partial verify | DONE Tier 4 batch 4.6 — script now lives in `pi_backend/`; path made env-driven. |
| N12 | `control_buttons.dart` empty placeholder | ✅ | PENDING — Tier 6+ (operator UI; pairs with W5 dashboard E-STOP). |
| N13 | `lib/models/` empty | ⚠️ partial verify | DONE Tier 5 batch 5.2 — directory removed (or populated, see batch 5.2 record). |
| N14 | Three Python `requirements*.txt` in Flutter project | ✅ | DONE Tier 5 batch 5.3 — moved with R16; `test_requirements.txt` renamed to `requirements_dev.txt`. |
| N15 | "No canonical wire-schema owner" | ❌ wrong | NO ACTION — `SYSTEM_ARCHITECTURE.md §4` is the canonical owner. Tier 4 batch 4.4 audited it for completeness. |
| N16 | "16 Socket.IO events are folklore" | ❌ wrong | NO ACTION — same as N15. |
| N17 | Conventions doc gaps for "where do new things go" | ✅ | DONE Tier 4 + Tier 5 batch 5.1 — pi_backend section added; trimui pointer updated. |
| N18 | `archive/raspberry_pi_*/` footgun (inverted ports) | ⚠️ partial verify | DONE Tier 5 batch 5.4 — moved out of trimui to `pi_backend/archive/`; `REMOVED.md` warning preserved alongside. |

### 1d. NEW findings from fact-check

| ID | Finding | Disposition |
|---|---|---|
| NEW-1 | Repo top has 8 markdown files vs `conventions.md §5` claim of "2" | DONE Tier 5 batch 5.1 — convention §5 updated to enumerate the actual 9 (now 8 after AUDIT_FINDINGS moved out in Tier 5 batch 5.4). |
| NEW-2 | `test/services/backend_service_test.dart` untracked in trimui | PENDING — by user instruction, no commits this session. |
| NEW-3 | trimui `git status` ~25 changes uncommitted | PENDING — user reserves the commit. |
| NEW-4 | `Glob` patterns with literal spaces silently fail | DONE Tier 5 batch 5.1 — note added to `agent_stack/conventions.md` for future agents. |

---

## 2. Pending Tier 6+ work

The orchestrator surfaced 7 deferred items at the end of Tier 5:

1. **W5** (P3, safety-gate) — Dashboard `/api/estop/{engage,clear}` HTTP 410. Either re-wire to `bridge_coordinator._handle_emergency_stop` with SET semantics, or formally retire the routes. Highest-priority remaining safety-surface gap.
2. **R5** (P2, safety-gate) — Rename `serpent-dashboard-base-custom.service` to a meaningful name (or document the variant in `dashboard/README.md`). Service files are gated.
3. **R11** (P2, safety-gate) — Constants drift: have `dashboard/config.py`, `base_pi/config.py`, `robot_pi/config.py` read from `common/constants.py` rather than re-declaring `ROBOT_PI_IP`/`BASE_PI_IP`/`CONTROL_PORT`.
4. **R32** (P2) — Add a "keep last N validator log files" rotation in `validate.py`.
5. **N4 + N5** (P2) — `base_pi/` and `robot_pi/` layout normalisation (mixed flat / `core/` / `telemetry/` depth). Large surface, low impact, defer until next refactor sprint.
6. **N12** (P3) — `lib/widgets/control_buttons.dart` placeholder is paired with W5; do them together.
7. **trimui-commit** (operator) — ~25 uncommitted changes in `serpent_trimui_app/.git`. Per user instruction, this session does no commits. Operator should review and commit at next pass.

Plus the three safety-gated sub-batches of Tier 5 batch 5.4 itself, deferred from this dispatch:

8. **5.4 Phase 2** — `pi_halow_bridge/PI-HALOW-BRIDGE/generate_psk.py` move to `scripts/`.
9. **5.4 Phase 3** — `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/setup_ssd_recording.sh` relocation.
10. **5.4 Phase 4** — `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/systemd/` directory relocation.

All three require `safety-gate` review per `agent_stack/gates/destructive_ops.yaml`.

---

## 3. Structural changes summary

The 2026-04-25 cleanup landed in five tiers, each with one or more batches.

- **Tier 1 — test-isolation blocker fix** (W8). `_make_controller` now isolates SI-1 persistence per test.
- **Tier 2 — broken stress-script repointing** (W1-W4).
- **Tier 3 — safety-gate-cleared semantic-zero doc/comment alignment** (W6, W13, W15, W16). One commit titled "doc: align E-STOP comments with 2026-04-24 rebuild".
- **Tier 4 — setup/install/PSK consolidation** (R1-R4, R10) and the big extraction (R16: pi_backend/). Multiple safety-gate-cleared batches.
- **Tier 5 — long tail.**
  - 5.1 — top-level renames (N1, N2), repo-top cleanup (NEW-1), README/SETUP/SAFETY_HARDENING refresh, archive moves of REFACTORING_*/PHASE5/halow_bridge.old/telemetry-bottleneck constellation.
  - 5.2 — bench-script reorganisation (R12, N10), Flutter dep prune (R27), build-artifact cleanup (R28-R31), `repo_map.py` arduino-bucket fix (W9), agent-stack discoverability (R33, R34), dashboard static stub removal (R6, N6).
  - 5.3 — trimui doc consolidation (R17-R26), PSK redaction (R10 finalize), README rewrite (W11).
  - 5.4 — non-safety-critical relocations (Phase 1 — this dispatch): pi_backend/ doc landing (AUTOSTART_README.md, SETUP.md, archive/raspberry_pi_*/), bridge archive (`2026-03-16-connectivity-problems.md`), `scripts/dev/` and `scripts/sim/` subdirs, repo-top AUDIT_FINDINGS move, `setup_hub_pi.sh` rename.

Three safety-gated sub-batches of 5.4 (Phases 2-4) are deferred to the next session — see §2 items 8-10.

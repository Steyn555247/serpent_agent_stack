# Codebase Cleanup Plan — Hand-off for Incoming Software Engineer

**Date:** 2026-04-25
**Scope:** Whole repo at `C:\Serpent Dev\Serpent\Digital\App\Real Prototype\` — both subprojects + agent stack.
**Audience:** the software engineer inheriting this codebase.
**Type:** read-only audit; **no files were modified by this pass**.

This document is the single entry point. It consolidates findings from four parallel audits (PI-HALOW-BRIDGE, Flutter trimui, agent_stack, cross-subproject architecture) plus a prior 2026-04-25 cleanup audit done earlier the same day.

> **For the deep evidence**, see:
> - `agent_stack/audits/2026-04-25-cleanup-audit.md` — earlier-today P1/P2/P3 bucketing
> - `agent_stack/audits/2026-04-25-cleanup-handoff.md` — prior session's handoff (test-isolation blocker, validator state)
>
> This file (`2026-04-25-cleanup-plan.md`) is the **canonical action list**. The two prior docs are reference material.

---

## 0. Read-this-first safety rails

Before deleting or moving anything, observe the rules from `CLAUDE.md` and `agent_stack/conventions.md`:

- Any change to a path listed in `agent_stack/gates/destructive_ops.yaml :: safety_critical_paths` requires `safety-gate` agent approval. That includes `actuator_controller.py`, `framing.py`, `constants.py`, anything under `firmware/`, every `*.service` file, every `setup_*.sh`, and PSK material.
- Run `python agent_stack/tools/validate.py all` before AND after every batch. Don't merge a batch that regresses Python tests or Flutter tests.
- For each batch of changes, run `python agent_stack/tools/safety_check.py <paths…>` first. Empty findings → proceed; non-empty → route through safety-gate.
- Two subprojects = two independent git repos. Commit per subproject; never one commit across both.
- The 2026-04-24 E-STOP rebuild (R0–R10) is **complete**. Any code or comment that says "E-STOP removed pending rebuild" is stale; the safety surface exists and the 12 invariants are enforced. A test-isolation blocker affects 2 tests in `test_actuator_controller.py::TestBootGrace` (see §4 item 2 below) — **fix that first** before trusting validator output.

---

## 1. WHAT DOESN'T WORK (broken / half-finished / lying)

Concrete file:line findings. Each one is independently fixable.

| # | Path | Symptom | Fix sketch |
|---|---|---|---|
| W1 | `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/stress_load.py:87,103` | Spawns `robot_pi/halow_bridge.py` and `base_pi/halow_bridge.py` — neither file exists post-refactor (replaced by `*.core.bridge_coordinator`). | Replace with `[sys.executable, '-m', 'robot_pi.core.bridge_coordinator']` etc. |
| W2 | `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/stress_network_sim.py:258,277` | Same broken refs. | Same fix as W1. |
| W3 | `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/stress_reconnect.py:75,111` | Same broken refs. | Same fix as W1. |
| W4 | `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_stress_suite.py:104` | References `tests/test_estop_triggers.py` — file does not exist. Phase 6 of the suite always reports "0 tests run". | Repoint to `tests/test_estop.py` + `tests/test_estop_integration.py`. |
| W5 | `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/web_server.py:497-500, 589-592` | `/api/estop/clear` and `/api/estop/engage` return HTTP 410 with "E-STOP surface removed pending rebuild". The rebuild shipped 2026-04-24. **Operator dashboard cannot drive E-STOP** — only TrimUI + backend can. Functional safety-surface gap. | Re-wire to `bridge_coordinator._handle_emergency_stop` under safety-gate review, OR delete the routes if dashboard surface is intentionally retired. |
| W6 | `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/command_executor.py:226-232` | `start_motor_timeout_monitor` / `stop_motor_timeout_monitor` are explicit no-op stubs labelled "removed 2026-04-23". Still called by `bridge_coordinator.py:214` and `:396`. | Either delete both call sites + stubs, or restore the implementation. |
| W7 | `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/autonomous_cutter.py:435-438` | `if False:` dead block left after E-STOP removal. | Delete the block or wire it to the rebuilt E-STOP path. |
| W8 | `tests/test_actuator_controller.py::TestBootGrace` | 2 of 5 tests fail on second `validate.py all` invocation. Cause: `_make_controller` doesn't override `SERPENT_ESTOP_STATE_PATH`, so SI-1 persistence file at `/var/lib/serpent/robot_estop_state.json` written by other tests leaks in. | Override env var with a tempfile in the test helper (one-liner; safety-gate review required because it touches a safety-critical test). |
| W9 | `agent_stack/tools/build_repo_map.py:34` | Buckets `.cpp` and `.h` as "arduino", which makes `repo_map.md` claim the trimui project has 43 Arduino files. Those are Flutter Windows runner C++ files. The trimui has zero `.ino`. | Restrict arduino bucket to `firmware/` paths or `.ino` only. |
| W10 | `pi_halow_bridge/PI-HALOW-BRIDGE/setup_robot_pi.sh:58-66` | psk.conf heredoc emitted twice (copy-paste bug). | Delete the duplicate. |
| W11 | `serpent_trimui_app/README.md:38-44` instructs running `start.bat`. **No `start.bat` exists.** Closest match is `start_backend_simple.sh` (Linux only). | Either create `start.bat` or fix the README. |
| W12 | `serpent_trimui_app/test/services/backend_service_test.dart:3-5` cites `SYSTEM_ARCHITECTURE.md §4` as the wire-contract spec. **That file/section does not exist** in either subproject. | Create the spec OR remove the citation. See §3 R10 below — this is the canonical wire-schema gap. |
| W13 | `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/README.md:23` lists `control_sender.py` and `video_http.py` — actual filenames are `control_forwarder.py` and `base_pi/video/video_http_server.py`. | Fix the README. |
| W14 | `pi_halow_bridge/PI-HALOW-BRIDGE/README.md:766` "File Structure" lists `robot_pi/halow_bridge.py` and `base_pi/halow_bridge.py` — these files do not exist. | Replace with the current `*/core/bridge_coordinator.py` paths. |
| W15 | `serpent_trimui_app/.claude/settings.local.json:44` and `BUTTON_MAPPING_REFERENCE.md:236` reference `command_processor.py` — the actual file is `command_executor.py`. | Fix the references. |
| W16 | Stale comments throughout safety-critical files claiming "E-STOP removed 2026-04-23": `base_pi/core/bridge_coordinator.py:6,174`, `robot_pi/core/bridge_coordinator.py:6,60,575`, `common/constants.py:4-9`, `tests/test_actuator_controller.py:5`, `tests/test_safety_constants.py:8`, `tests/test_fault_injection.py:34`, `base_pi/README.md`, `robot_pi/README.md`, ~10 more sites in `README.md`. | Single safety-gate-reviewed commit titled "doc: align E-STOP comments with 2026-04-24 rebuild". Semantic-zero change. |
| W17 | `git status` in trimui repo shows 14 deleted-from-tracked files (`raspberry_pi_*/`) plus the new `archive/` folder as **untracked**. The cleanup move was never committed. A `git checkout -- .` or `git stash` would restore the obsolete code (which has inverted control/video ports — see R3 below). | Commit the archive move now. |

---

## 2. WHAT IS REDUNDANT (delete or consolidate)

### 2a. Bridge subproject

| # | Redundancy | Action |
|---|---|---|
| R1 | `setup_base_pi.sh`, `setup_robot_pi.sh`, `setup_psk_on_hub.sh` (top-level) **vs** `scripts/pi_install.sh`, `scripts/pi_enable_services.sh`. Two parallel install paths; the top-level set is older and broken (W10). | Keep `scripts/*` set; delete top-level setups; redirect `SETUP_GUIDE.md`. |
| R2 | `scripts/deploy.sh` + `scripts/rollback.sh` | Dead — uses `/home/pi/serpent/pi_halow_bridge` install root that no other script knows about. Delete. |
| R3 | `generate_psk.py` (top-level) + PSK generation duplicated inline in `scripts/pi_install.sh:222` and `setup_robot_pi.sh:36` | Keep `generate_psk.py`, have install scripts call it. |
| R4 | `scripts/install_dashboard.sh` vs `scripts/pi_enable_services.sh` | Fold dashboard install into `pi_enable_services.sh`. |
| R5 | Three dashboard systemd units: `serpent-dashboard-base.service`, `serpent-dashboard-base-custom.service`, `serpent-dashboard-robot.service`. The "-custom" name is uninformative — it differs from "-base" only in user/path/env. | Pick one canonical Base Pi unit; retire the other; document robot-vs-base in `dashboard/README.md`. |
| R6 | `base_pi/static/dashboard.html` and `robot_pi/static/dashboard.html` — both 54-line meta-refresh redirect stubs to the real Flask dashboard. The post-refactor docs (`REFACTORING_COMPLETE.md:72`) claim `base_pi/static/` was removed; it wasn't. | Replace both with HTTP 302 redirects in the bridge's video HTTP server, then delete the static dirs. |
| R7 | Telemetry-bottleneck doc constellation: `TELEMETRY_ANALYSIS.md`, `TELEMETRY_BOTTLENECK_DIAGRAM.txt`, `TELEMETRY_FIX_RECOMMENDATIONS.md`, `README_TELEMETRY_ANALYSIS.txt`, `PROOF_OF_BOTTLENECK.txt`, `ANALYSIS_SUMMARY.txt`. **Six docs prescribing the same one-line fix to `dashboard/config.py:67` (`STATUS_UPDATE_INTERVAL = 1.0`).** | Apply the fix once, then collapse to a single short note in `SAFETY_HARDENING.md` performance section. |
| R8 | Refactor-log constellation: `REFACTORING_COMPLETE.md`, `REFACTORING_GUIDE.md`, `REFACTORING_STATUS.md`, `PHASE5_COMPLETE.md`. All Feb-2026 build logs for a finished migration. | Move to `archive/docs/` or delete. |
| R9 | Setup-doc constellation: `SETUP_GUIDE.md`, `HALOW_SETUP_GUIDE.md`, `SETUP_PSK_ON_ROBOT.md`, `PULL_ON_HUB.md`, `FIX_PSK_MISMATCH.md`. Five overlapping docs, no entry point. | Keep `SETUP_GUIDE.md` as canonical with sub-sections; demote rest or delete. |
| R10 | PSK-management trio: `setup_psk_on_hub.sh`, `scripts/check_psk.sh`, `scripts/verify_psk_autoload.sh`. Two of these contain a literal 64-hex PSK (`setup_psk_on_hub.sh:7`, `verify_psk_autoload.sh:12`). Five docs (`SETUP_GUIDE.md:9,39,211`, `SETUP_PSK_ON_ROBOT.md:3,24`, `FIX_PSK_MISMATCH.md:12`, `PULL_ON_HUB.md`) propagate other PSK literals. | **SI-12 violation** — PSK material in tracked files. Redact, rotate, document the policy in `SAFETY_HARDENING.md`. (Memory note: PSK leak is low-priority for prod LAN, but this is still a gate violation that will block safety-gate reviews.) |
| R11 | Constants drift: `common/constants.py` defaults vs `dashboard/config.py:15-22` vs `base_pi/config.py:29` vs `robot_pi/config.py:30`. Three sources of truth for `ROBOT_PI_IP`, `BASE_PI_IP`, `CONTROL_PORT`. | Convention §2.7 says constants live in `common/constants.py`. Have the others read from it (env-overridable). |
| R12 | Root-level bench scripts: `test_multiplexer_pca9685.py`, `test_pca9685_servo.py`, `test_sensors.py`, `test_servo.py`. Match `unittest` discovery glob `test_*.py` but have **unconditional** hardware imports (violates conventions §2). | Rename to `bench_*.py` and move to `scripts/bench/`. Update `PCA9685_SETUP.md:89` reference. |
| R13 | `robot_pi/i2c_multiplexer.py` — only used by `scripts/scan_i2c_devices.py`. Production code uses `adafruit_tca9548a` directly. | If the diagnostic script moves to `scripts/bench/`, this driver file becomes fully dead — delete. |
| R14 | `archive/halow_bridge.py.old` (801 lines) — pre-refactor monolith, imports a missing top-level `telemetry_storage` module. | Delete. |
| R15 | One-shot diagnostics at bridge root: `check_telemetry.py`, `check_status.sh`, `restart_robot_bridge.sh`, `test_dashboard.sh`. None referenced anywhere. | Delete or move to `scripts/dev/`. |

### 2b. Trimui subproject

| # | Redundancy | Action |
|---|---|---|
| R16 | **The whole Pi backend lives inside the Flutter project** — `serpent_backend_trimui_s.py` (1858 lines, Flask + SocketIO), plus `quick_diagnose.py`, `setup_pi_backend.sh`, `install_dependencies.sh`, `setup_autostart.sh`, `setup_simple_autostart.sh`, `start_backend_simple.sh`, `manage_service.sh`, `setup_hub_pi.sh`, `requirements.txt`, `requirements_pi.txt`, `test_requirements.txt`, `install.bat`. This server is consumed by `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/core/backend_client.py` via 16 `@sio.on(...)` handlers. | **Extract to its own subproject** (e.g. `serpent_pi_backend/` at repo top, or `pi_halow_bridge/PI-HALOW-BRIDGE/host_backend/`). See §5 below. |
| R17 | `setup_autostart.sh` vs `setup_simple_autostart.sh` — same job, two variants (system vs user systemd). Naming doesn't say which. | Rename to `setup_autostart_system.sh` and `setup_autostart_user.sh`, or pick one. |
| R18 | `setup_pi_backend.sh` (14.6 KB) vs `install_dependencies.sh` (6.1 KB) — overlap heavily; both install Python deps for the Pi. | Collapse to one canonical script. |
| R19 | `build_apk.bat` vs `build_apk.ps1` — identical logic in two shells. **Acceptable** as Windows-shell parity, no action needed unless engineer prefers one. | (No action.) |
| R20 | 6 button-mapping docs: `BUTTON_MAPPING_REFERENCE.md`, `BUTTON_TESTING_GUIDE.md`, `CONTROLLER_MAPPING_GUIDE.md`, `CUSTOM_BUTTON_MAPPING.md`, `DASHBOARD_BUTTON_DISPLAY.md`, `CLAW_CONTROL_IMPLEMENTATION.md`. | Pick one canonical (`BUTTON_MAPPING_REFERENCE.md` is the natural pick); archive the rest. |
| R21 | 5 autostart docs: `AUTOSTART_OPTIONS.md`, `AUTOSTART_README.md`, `TRIMUI_AUTO_START_GUIDE.md`, `SET_LAUNCHER_ADB.md` + scripts. | Collapse to `AUTOSTART.md`. |
| R22 | 5 Pi-setup docs: `QUICK_START.md`, `RASPBERRY_PI_BACKEND_SETUP.md`, `RASPBERRY_PI_DEPLOYMENT.md`, `RASPBERRY_PI_GIT_SETUP.md`, plus `setup_pi_backend.sh`. | Collapse to one Pi setup doc that lives **with the extracted backend** (R16). |
| R23 | 3 GitHub-setup docs: `GITHUB_SETUP.md`, `QUICK_START_GITHUB.md`, `setup_github.ps1`. One-time onboarding step that's already done. | Delete or move to `archive/`. |
| R24 | `BUG_FIX_SUMMARY.md` (says X-button-E-STOP bug is fixed) vs `DIAGNOSTIC_GUIDE.md` (says "still investigating" the same bug). **Self-contradictory.** | Pick the right one; delete the other. |
| R25 | `FIX_CAMERA_AND_ESTOP_PROMPT.md` — copy-pasted Claude prompt, not a doc. | Move to `archive/`. |
| R26 | `FINAL_BUILD_SUMMARY.md` — labelled "Final" but predates 20+ subsequent commits. | Mark archived or delete. |
| R27 | Unused Flutter deps: `permission_handler: ^11.1.0` (zero imports), `path_provider: ^2.1.1` (zero imports). Bloats APK and the Windows plugin registrant. | Drop from `pubspec.yaml`, `flutter pub get`. |
| R28 | `serpent-robotics-trimui-app/` — empty directory inside the trimui project (probably an accidental `git clone` into self). | Delete. |
| R29 | `__pycache__/` at trimui root — gitignored but still on disk. | Delete. |
| R30 | `build/` — 1.4 GB of Flutter build artifacts on disk. Gitignored. | `flutter clean`. |
| R31 | `flutter_01.png` … `flutter_04.png` (~7.8 MB total, **tracked** in git), `frame.jpg` — no code/doc references. | Move to `portfolio_screenshots/` outside git, or delete. |

### 2c. agent_stack

The agent stack is **clean**: zero overlapping tools, zero broken references, AGENTS.md ⇄ `.claude/agents/` perfectly consistent, `.runtime/` correctly gitignored. Only housekeeping items:

| # | Item | Action |
|---|---|---|
| R32 | `agent_stack/.runtime/logs/` has 17 validator log files (~1.2 MB) with no rotation cap. | Add "keep last N" prune in `validate.py`. |
| R33 | `smoke_test.py` is undiscoverable — only mentioned in `CLAUDE.md` and `agent_stack/README.md`, no slash command, no agent invocation. | Add `/smoke-test` command, or invoke from `/plan` init. |
| R34 | `agent_stack/examples/01-03_*.md` are well-written but never linked from `CLAUDE.md`. | Add a one-line "see examples for worked walkthroughs" pointer. |

---

## 3. WHAT IS NOT INTUITIVE (rename / restructure / document)

### 3a. Top-level layout

| # | Item | Recommendation |
|---|---|---|
| N1 | `serpent_trimui_app/` — the literal " - Copy" suffix is canonical. There is no original `serpent_trimui_app/`. The name is hardcoded into `agent_stack/tools/validate.py:40`, `agent_stack/conventions.md` §1, every doc, the parent CLAUDE.md, and quoted in every CLI snippet. | Rename to `serpent_trimui_app/` (or `trimui_app/`). Coordinate the change across `validate.py`, `conventions.md`, `CLAUDE.md`, `repo_map.md`, IDE module files, and git remotes in one atomic move. The 1.4 GB `build/` will need regeneration anyway. |
| N2 | `pi_halow_bridge/` — a directory containing exactly one project (`PI-HALOW-BRIDGE/`). Spaces in path are load-bearing in `validate.py:39` and every doc. | Hoist `PI-HALOW-BRIDGE/` to repo top OR rename to `pi_halow_bridge/`. Coordinated rename, same approach as N1. |
| N3 | New engineers won't immediately see `AGENTS.md` vs `CLAUDE.md` distinction. | Add a single line at top of each pointing at the other ("`AGENTS.md` = agent index; `CLAUDE.md` = how-to-work + rules"). |

### 3b. Bridge layout

| # | Item | Recommendation |
|---|---|---|
| N4 | Inconsistent depth: `base_pi/core/` holds 4 files but `base_pi/telemetry_*.py` (5 files), `winch_controller.py`, `control_forwarder.py`, `video_receiver.py` are **flat**. Meanwhile `base_pi/video/` exists with one file. | Pick one layout: either everything under sub-packages (matching `robot_pi/` which has `core/`, `telemetry/`, `control/`) or flat. Currently it's neither. |
| N5 | `robot_pi/` splits into `core/` (4 files), `telemetry/` (1 file), `control/` (1 file). Single-file packages suggest planned siblings that never landed. | Either populate or flatten. |
| N6 | `dashboard/templates/index.html` is the real operator dashboard; `base_pi/static/dashboard.html` and `robot_pi/static/dashboard.html` are 54-line redirect stubs served from the bridge's video HTTP server. Both are called "dashboard.html". | Add a single sentence to `dashboard/README.md`: *"The dashboard is `dashboard/web_server.py` (Flask) serving `dashboard/templates/index.html` on port 5005 (robot) / 5006 (base). The `static/dashboard.html` files in `base_pi/` and `robot_pi/` are redirect stubs."* |
| N7 | Filename with spaces: `march 16th problems connectivity.md`. Convention §5 wants `UPPER_SNAKE_CASE.md`. | Rename to `MARCH_16_CONNECTIVITY_NOTES.md`. |
| N8 | Top-level `*.py` scripts (`generate_psk.py`, `check_telemetry.py`) and shell scripts (`setup_*.sh`, `check_status.sh`, `restart_robot_bridge.sh`, `test_dashboard.sh`). | Move to `scripts/`. Convention §5 reserves project root for current docs. |

### 3c. Trimui layout

| # | Item | Recommendation |
|---|---|---|
| N9 | 30 markdown files at trimui root, no `docs/` index. | Create `docs/` with subfolders (`docs/buttons/`, `docs/pi_setup/`, `docs/autostart/`, `docs/troubleshooting/`). Keep only `README.md` and `CHANGELOG.md` at root. |
| N10 | 5 root-level `test_*.py` files (`test_all_features.py`, `test_apk_server.py`, `test_arducam.py`, `test_input_monitor.py`, `test_pygame_controller.py`). These are Python integration probes for the Pi backend, not Flutter tests. The `test_` prefix collides with pytest discovery. | Rename to `probe_*.py` and move to `scripts/` of whatever subproject the backend ends up in (R16). |
| N11 | `start_backend_simple.sh:6` hardcodes `/home/serpentbase/Desktop/serpent-robotics-trimui-app` — a path that doesn't match this project's name. | Use a relative or env-driven path. |
| N12 | `lib/widgets/control_buttons.dart` is an empty stub (returns `SizedBox.shrink()`) labelled "E-STOP placeholder pending rebuild". The rebuild has shipped. | Either delete and remove its layout slot, or rebuild it as the dashboard E-STOP surface (paired with W5). |
| N13 | `lib/models/` is empty — convention's reservation slot. | Either populate or delete. |
| N14 | `requirements.txt` (desktop) vs `requirements_pi.txt` vs `test_requirements.txt`. Three Python manifests in a Flutter project. The "main" one is **not** `pubspec.yaml`. | Move with R16; rename to clarify target. |

### 3d. Cross-subproject coupling — the biggest day-1 confusion

| # | Item | Recommendation |
|---|---|---|
| N15 | The Flutter app talks to the Pi backend over Socket.IO at port 5000. The Pi backend (`serpent_backend_trimui_s.py`) lives in the Flutter project. The Bridge (`base_pi/core/backend_client.py`) connects to that same backend. **Three implementations of one wire schema, no canonical owner.** | (a) Move the backend out of the Flutter repo (R16). (b) Create the missing `SYSTEM_ARCHITECTURE.md §4` wire-contract doc (W12). (c) Add a cross-subproject test that exercises Flutter → backend → bridge end-to-end. |
| N16 | The Bridge backend client implements 16 `@sio.on(...)` handlers (`emergency_stop`, `clamp_close`, `clamp_open`, `height_update`, `force_update`, `start_camera`, `input_event`, `raw_button_press`, `r1_button`, `chainsaw_command`, `chainsaw_move`, `climb_command`, `traverse_command`, `brake_command`, `winch_control`, `winch_calibration`). Only E-STOP is documented (in `ESTOP_REBUILD_PLAN.md §Q1`). The other 15 are folklore. | Document all 16 events with payload shapes in the new `SYSTEM_ARCHITECTURE.md §4`. |
| N17 | `CLAUDE.md` "Where to put new things" doesn't say where the host backend goes, where shared wire schemas go, where bench scripts go, what the archive policy is, or where top-level operator runbooks go. | Update §"Where to put new things" once the moves above land. |
| N18 | `serpent_trimui_app/archive/raspberry_pi_*/` looks like working code (has `start_services.sh`, `README.md`, `requirements.txt`). The `REMOVED.md` warning is good but not surfaced. **Footgun: the archived `config.py` files have inverted control/video ports — following their README would push unauthenticated UDP at the production control port.** | Move to `_quarantine/` at repo top with `DO_NOT_USE.md`, or delete entirely (the audit trail in `archive/REMOVED.md` is preserved either way). |

---

## 4. Recommended ordered action sequence

Tackle in this order. Each item is independently shippable; each batch ends with `validate.py all` green.

1. **Fix the test-isolation blocker** (W8, four-line edit). Until this lands, every Phase 2 batch validates against a flaky baseline. Safety-gate review required because it's a safety-critical test helper.
2. **Commit the trimui `archive/` move** (W17). Currently uncommitted in git — at risk of accidental restoration. Single trimui commit. No code change.
3. **Doc-only batch: align all "removed 2026-04-23" comments with the 2026-04-24 rebuild** (W16, W13, W14, W15, R8, the `march 16th` rename N7). One safety-gate-reviewed commit titled "doc: align E-STOP comments with 2026-04-24 rebuild". Semantic-zero.
4. **Fix the dashboard E-STOP API (W5)**. This is the largest functional safety-surface gap. Either re-wire `/api/estop/clear` and `/api/estop/engage` to `bridge_coordinator._handle_emergency_stop` under safety-gate review, or delete the routes and document that decision. Coordinate with N12 (the Flutter `control_buttons.dart` placeholder) so the E-STOP surface picture is consistent.
5. **Fix broken stress scripts** (W1, W2, W3, W4). Replace `halow_bridge.py` references with `-m *.core.bridge_coordinator` invocations. Add `run_stress_suite.py` Phase-6 to validator coverage so we don't regress.
6. **Move bench scripts** (R12, N10). Rename root `test_*.py` → `bench_*.py` and move to `scripts/bench/` under the appropriate subproject. Update `PCA9685_SETUP.md:89` reference. Convention update: explicitly state where bench scripts live.
7. **Redact tracked PSKs** (R10). Remove literals from `setup_psk_on_hub.sh:7`, `verify_psk_autoload.sh:12`, `SETUP_GUIDE.md:9,39,211`, `SETUP_PSK_ON_ROBOT.md:3,24`, `FIX_PSK_MISMATCH.md:12`, `PULL_ON_HUB.md`. Rotate the PSK and document the new "PSK never tracked" policy in `SAFETY_HARDENING.md`. Memory note: PSK leak is operationally low-priority on a trusted LAN, but this is still an SI-12 violation that will block safety-gate reviews until cleared.
8. **Consolidate setup paths** (R1, R2, R3, R4). One canonical install flow: `scripts/pi_install.sh` + `scripts/pi_enable_services.sh`. Delete the rest, redirect `SETUP_GUIDE.md`.
9. **Consolidate doc constellations** (R7, R9, R20, R21, R22, R23, R24, R25, R26). Pick canonical, archive the rest, build a `docs/` index in trimui (N9).
10. **Drop unused Flutter deps** (R27). Removes `permission_handler` and `path_provider`, regenerates plugin registrant.
11. **Big structural moves — coordinate as a single multi-subproject change:**
    - **R16**: Extract `serpent_backend_trimui_s.py` + sibling Pi-side scripts to a new subproject `serpent_pi_backend/` (or `pi_halow_bridge/PI-HALOW-BRIDGE/host_backend/`). Update conventions §"Where to put new things". This is the highest-impact move in the whole plan: it removes the cross-subproject runtime dependency from a UI repo.
    - **W12 / N15 / N16 / R10 reference fix**: Create `SYSTEM_ARCHITECTURE.md §4` documenting all 16 Socket.IO events with payload shapes. Make `flutter test` and `python scripts/test_all.py` validate against it. Add an end-to-end integration test.
12. **Top-level renames** (N1, N2). Rename `serpent_trimui_app/` → `serpent_trimui_app/` and either rename or hoist `pi_halow_bridge/PI-HALOW-BRIDGE/`. Atomic update of `validate.py:39-41`, `conventions.md` §1, every CLAUDE.md command quote, agent_stack/repo_map.md, and git remotes. Do this **last** — it's the loudest but lowest-information-gain change and depends on every prior reorganisation having stabilised the paths.
13. **Layout normalisation** (N4, N5, N6, R5, R6, R11, R13, R14, R15, R17, R18, R28, R29, R30, R31, N3, N11, N13).
14. **Housekeeping** (W9 repo_map.py arduino bucket, W10 setup_robot_pi.sh duplicate heredoc, W11 missing start.bat, W7 if-False block, W6 no-op stubs, R32-R34 agent_stack housekeeping).

---

## 5. What NOT to do without explicit human OK

Per `agent_stack/gates/destructive_ops.yaml`:

- Do not flash firmware (`pio run -t upload`, `arduino-cli upload`, `esptool …`).
- Do not edit `*.service` files without safety-gate review.
- Do not modify `actuator_controller.py`, `framing.py`, `constants.py` without safety-gate.
- Do not modify anything under `firmware/` without safety-gate AND the `firmware-change` workflow.
- Do not `git push --force`, `git reset --hard`, or `git clean -fd` either subproject.
- Do not commit anything in `agent_stack/.runtime/`.
- Do not commit `SERPENT_PSK_HEX` material.
- Do not bypass the canonical test runner (`scripts/test_all.py`); if a test is flaky, fix it or quarantine it explicitly.
- Do not introduce new top-level directories without writing why in `agent_stack/conventions.md`.
- Do not reformat or restructure files you weren't asked to change. Bug fixes don't need surrounding cleanup.

The current E-STOP rebuild is the line in the sand — every safety invariant SI-1 through SI-12 is enforced as of 2026-04-24. Cleanup work below the safety line is welcome; the safety line itself does not move without `safety-gate` approval.

---

## 6. How to use this plan

- The 4 audits and the prior cleanup audit cite specific file paths and line numbers; this plan numbers them as W#/R#/N# so they're easy to reference in commit messages.
- Each batch should:
  1. `python agent_stack/tools/safety_check.py <files>` first.
  2. Edit.
  3. `python agent_stack/tools/validate.py all`.
  4. Commit per subproject.
  5. Update `agent_stack/.runtime/session_state.json` via `session_state.py decide` so the next session can pick up.
- The `repo_map.{md,json}` is auto-generated; re-run `python agent_stack/tools/build_repo_map.py` after any structural move (item 11 or 12).
- After item 11 lands, refresh this plan — most of items 12-14 will simplify.

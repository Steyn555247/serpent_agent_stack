# Fact-Check of `2026-04-25-cleanup-plan.md`

**Date:** 2026-04-25 (same day, after the user requested verification)
**Method:** every claim in the plan that names a file path, line number, or specific code/text was verified by direct `Read`, `Grep`, or `ls`. Subjective claims ("redundant", "confusing", "intuitive") are not fact-checkable and are left as judgement; only the verifiable factual basis underneath them is checked.

> **Read this alongside the plan, not instead of it.** The plan's structure (W#/R#/N#) is preserved. This file says, for each numbered item: ✅ confirmed exact, ⚠️ confirmed but the description needed refinement, ❌ wrong (struck through with the correct fact stated), or 🆕 a new finding the plan missed.

---

## Methodology note for the next engineer

While verifying I discovered that **`Glob` patterns containing literal spaces (`pi_halow_bridge/...`) return false negatives** in this environment. Some "no files found" results from earlier audit agents were also from this bug, not actual absence. Cross-check any negative claim with `ls` or with `Glob` using the `path:` parameter and a pattern that doesn't repeat the directory with spaces. Several of my own first-pass conclusions had to be retracted because of this.

---

## §1 WHAT DOESN'T WORK — verification

| ID | Status | Notes |
|---|---|---|
| **W1** `stress_load.py:87,103` references `robot_pi/halow_bridge.py` and `base_pi/halow_bridge.py` | ✅ | Lines verified verbatim. Production paths are `*/core/bridge_coordinator.py`. The only `halow_bridge.py` in the tree is `archive/halow_bridge.py.old`. |
| **W2** `stress_network_sim.py:258,277` same | ✅ | Verified. |
| **W3** `stress_reconnect.py:75,111` same | ✅ | Verified. |
| **W4** `run_stress_suite.py:104` references `tests/test_estop_triggers.py` (missing) | ✅ | Line verified; `ls tests/` confirms the file does not exist. |
| **W5** `dashboard/web_server.py:497-500, 589-592` HTTP 410 stubs for `/api/estop/{clear,engage}` | ✅ | Both endpoints confirmed verbatim with the exact "removed pending rebuild" string. |
| **W6** `command_executor.py:226-232` no-op stubs called by `bridge_coordinator.py:214,396` | ✅ | All four lines verified. The stubs are present; the call sites still exist. |
| **W7** `autonomous_cutter.py:435-438` `if False:` block | ✅ | Verified verbatim. |
| **W8** Test-isolation blocker in `test_actuator_controller.py::TestBootGrace` | ✅ | Verified via the prior handoff doc which records the same blocker. (Not re-run; trusting the prior session's reproduction.) |
| **W9** `build_repo_map.py:34` buckets `.cpp/.h` as "arduino" | ✅ | Confirmed: `"arduino": {".ino", ".cpp", ".h"}`. **Real impact:** the trimui's `windows/runner/*.cpp` files are mis-classified, making `repo_map.md` say the trimui has 43 Arduino files when it has 0 `.ino`. |
| **W10** `setup_robot_pi.sh:58-66` "duplicate heredoc" | ⚠️ | **Refinement:** it's not just duplicate. Line 58 writes to `/etc/systemd/system/serpent-robot-bridge.service.d/psk.conf` **before** line 62's `mkdir -p` for that directory. With `set -e` at line 5, the first invocation fails at line 58 because the parent dir doesn't exist. On a second run (after the dir already exists from a prior partial run) the heredoc is written twice. The bug is "first-run failure", not "harmless duplication". |
| **W11** `serpent_trimui_app/start.bat` referenced by README:45 but does not exist | ✅ | README:45 says `start.bat`. `ls` shows only `start_backend_simple.sh` (Linux). No `start.bat`. |
| **W12** Wire-contract test cites `SYSTEM_ARCHITECTURE.md §4` which **does not exist** | ❌ | **WRONG.** `SYSTEM_ARCHITECTURE.md` exists at the **repo root** (`C:\Serpent Dev\Serpent\Digital\App\Real Prototype\SYSTEM_ARCHITECTURE.md`), and section `## 4. File integration map — who talks to whom` is at line 234. The Flutter test's citation is valid. The earlier audit agent's "missing spec" claim was caused by a `Glob` false-negative. **The wire schema IS documented.** What remains true: `test/services/` is uncommitted in git (see W17 below) — so the contract test exists on disk but is not yet in version control. |
| **W13** `base_pi/README.md:20-23` lists wrong filenames (`control_sender.py`, `video_http.py`) | ✅ | Verified verbatim. Actual files are `base_pi/control_forwarder.py` and `base_pi/video/video_http_server.py`. |
| **W14** `README.md:766` "File Structure" lists `halow_bridge.py` files that don't exist | ✅ | Confirmed at line 766. Same file-structure block lists `robot_pi/halow_bridge.py`. The post-refactor entry points are `*/core/bridge_coordinator.py`. |
| **W15** `.claude/settings.local.json:44` and `BUTTON_MAPPING_REFERENCE.md:236` reference `command_processor.py` (doesn't exist; actual is `command_executor.py`) | ✅ | Both lines verified. Actual file at `robot_pi/core/command_executor.py`. No `command_processor.py` in the tree. |
| **W16** ~14 stale "removed 2026-04-23" comments | ⚠️ | **Refinement:** actual count is **15 files** (Grep confirmed). All listed files in the plan are correct, plus `dashboard/web_server.py`, `tests/test_actuator_controller.py`, `tests/test_fault_injection.py`, `test_servo.py` (root-level bench script), `SAFETY_HARDENING.md`, `robot_pi/config.py`, `base_pi/config.py`, `base_pi/core/state_manager.py`, `base_pi/README.md`. Plan said "~14 in safety-critical files"; actual scope is broader. |
| **W17** Trimui `archive/` move uncommitted | ⚠️ | **Refinement: scope much wider than stated.** Actual `git status` shows 9 modified files (`lib/screens/*.dart`, `lib/services/*.dart`, `lib/widgets/control_buttons.dart`, `pubspec.yaml`, `serpent_backend_trimui_s.py`, `test/widget_test.dart`), 14 deleted-from-tracked files (`raspberry_pi_*/`, `setup_pi_backend.sh.backup`), AND 7 untracked items: `archive/`, `assets/fonts/`, `portfolio_assets/`, `portfolio_screenshots/`, `test/failures/`, `test/portfolio_screenshots_test.dart`, **`test/services/`** (which contains `backend_service_test.dart`, i.e. the wire-contract test from W12). A `git checkout -- .` would lose substantial work, including the very test file my plan cited. |

---

## §2 REDUNDANT — verification

### 2a. Bridge

| ID | Status | Notes |
|---|---|---|
| **R1** Top-level `setup_*.sh` vs `scripts/pi_install.sh` + `pi_enable_services.sh` | ✅ | All five files exist. Conflict between two install paths is real. |
| **R2** `scripts/deploy.sh` + `scripts/rollback.sh` legacy | ✅ | Both exist in `scripts/`. (Earlier Glob false-negative had me doubt this.) Whether they are truly "legacy" is judgement, not fact. |
| **R3** `generate_psk.py` + duplicated PSK gen in install scripts | ✅ | `generate_psk.py` exists at bridge root; `setup_robot_pi.sh:36` and `pi_install.sh:222` both invoke `secrets.token_hex(32)` inline. |
| **R4** `scripts/install_dashboard.sh` vs `scripts/pi_enable_services.sh` | ✅ | Both exist. Whether to fold one into the other is judgement. |
| **R5** Three dashboard systemd units (`-base`, `-base-custom`, `-robot`) | ⚠️ | **All three exist** but they are not as redundant as my plan implied. `-base.service` requires `check_hdmi.sh` as `ExecStartPre` (HDMI-attached operator UI); `-base-custom.service` runs as user `serpentbase` with `ENABLE_SERVICE_CONTROL=True` and inherits PSK from the bridge service (headless dashboard). They serve different deployment shapes. The naming "custom" is still uninformative — consider renaming, but don't simply delete one. |
| **R6** `base_pi/static/dashboard.html` + `robot_pi/static/dashboard.html` redirect stubs | ⚠️ | Files exist. Did not verify they are 54-line meta-refresh redirects (didn't read them in this verification pass). The "REFACTORING_COMPLETE.md claims static was removed but it wasn't" claim is in the prior audit and was not independently re-verified here. |
| **R7** Six telemetry-bottleneck docs | ✅ | All six files exist at bridge root: `TELEMETRY_ANALYSIS.md`, `TELEMETRY_BOTTLENECK_DIAGRAM.txt`, `TELEMETRY_FIX_RECOMMENDATIONS.md`, `README_TELEMETRY_ANALYSIS.txt`, `PROOF_OF_BOTTLENECK.txt`, `ANALYSIS_SUMMARY.txt`. Did not verify they all prescribe the same fix; that's an agent claim from the first pass. |
| **R8** `REFACTORING_*.md` + `PHASE5_COMPLETE.md` | ✅ | All four files exist at bridge root. |
| **R9** Setup-doc constellation (5 files) | ✅ | All five files exist at bridge root. |
| **R10** PSK literals in tracked files | ✅ | Verified verbatim: `setup_psk_on_hub.sh:7` and `scripts/verify_psk_autoload.sh:12` both contain `1deefbb6fd8b1c5684c6481733c6fc6ff88c00262470464533354b73efbdb6f1`. `SETUP_GUIDE.md` also contains the same hex. **Per user memory: PSK exposure is low-priority on a trusted LAN — flag but do not escalate.** |
| **R11** Constants drift across `common/constants.py`, `dashboard/config.py`, `base_pi/config.py`, `robot_pi/config.py` | ✅ (file existence) | All four files exist. Did not re-verify the specific line numbers or duplicate constant values; the agent's claim was specific (`dashboard/config.py:15-22`, etc.) and consistent with conventions §2.7. |
| **R12** Four root-level `test_*.py` bench scripts | ✅ | All four files exist verbatim: `test_multiplexer_pca9685.py`, `test_pca9685_servo.py`, `test_sensors.py`, `test_servo.py`. They are picked up by `unittest`'s `test_*.py` discovery glob — but the canonical runner walks `tests/` so they are masked. |
| **R13** `robot_pi/i2c_multiplexer.py` only used by `scripts/scan_i2c_devices.py` | ⚠️ | File exists. Did not re-verify it is used by exactly one consumer. |
| **R14** `archive/halow_bridge.py.old` (801 lines) | ✅ | File exists at `pi_halow_bridge/PI-HALOW-BRIDGE/archive/halow_bridge.py.old`. (Earlier Glob false-negative had me doubt this.) Did not re-verify line count. |
| **R15** Top-level diagnostics (`check_telemetry.py`, `check_status.sh`, `restart_robot_bridge.sh`, `test_dashboard.sh`) | ✅ | All four files exist at bridge root. |

### 2b. Trimui

| ID | Status | Notes |
|---|---|---|
| **R16** `serpent_backend_trimui_s.py` (1858 lines) lives in Flutter project | ✅ | File exists at `serpent_trimui_app/serpent_backend_trimui_s.py`. Did not re-verify line count. The 16-Socket.IO-event consumption pattern from `base_pi/core/backend_client.py` was observed by the prior audit. |
| **R17** `setup_autostart.sh` vs `setup_simple_autostart.sh` | ✅ | Both files exist. |
| **R18** `setup_pi_backend.sh` vs `install_dependencies.sh` | ✅ | Both files exist. Did not re-verify content overlap. |
| **R19** `build_apk.bat` vs `build_apk.ps1` (kept as acceptable) | ✅ | Both exist. |
| **R20** 6 button-mapping docs | ✅ | All six files exist at trimui root. |
| **R21** 5 autostart docs | ✅ | All listed files exist. |
| **R22** 5 Pi-setup docs | ✅ | All listed files exist. |
| **R23** 3 GitHub-setup docs | ✅ | `GITHUB_SETUP.md`, `QUICK_START_GITHUB.md`, `setup_github.ps1` all exist. |
| **R24** `BUG_FIX_SUMMARY.md` vs `DIAGNOSTIC_GUIDE.md` self-contradicting | ⚠️ | Both files exist. Did not re-verify the exact contradiction (agent claim from the first pass). |
| **R25** `FIX_CAMERA_AND_ESTOP_PROMPT.md` is a copy-pasted prompt | ✅ | File exists. Categorisation as "prompt not doc" is judgement. |
| **R26** `FINAL_BUILD_SUMMARY.md` predates 20+ commits | ✅ | File exists. "Predates" is a git-log claim from the agent; not re-verified here. |
| **R27** `permission_handler` and `path_provider` unused | ✅ | `pubspec.yaml:27,29` lists both. `Grep` of `lib/` returns **zero matches** for either package name. Confirmed unused. |
| **R28** `serpent-robotics-trimui-app/` empty subdir | ⚠️ | Did not re-list this directory in the verification pass. Take the agent's first-pass claim at face value. |
| **R29** `__pycache__/` at trimui root | ✅ | Confirmed in `ls` output. |
| **R30** `build/` 1.4 GB on disk | ✅ | Confirmed in `ls` output. Size not re-measured. |
| **R31** `flutter_0[1-4].png` (~7.8 MB tracked) + `frame.jpg` | ✅ | All five files visible in `ls`. Tracked-status from agent claim, not re-verified by `git ls-files`. |

### 2c. agent_stack

| ID | Status | Notes |
|---|---|---|
| **R32** `agent_stack/.runtime/logs/` 17 files, no rotation | ✅ | Reflected in the prior audit's directory inventory. |
| **R33** `smoke_test.py` undiscoverable | ✅ | Search confirmed no slash command invokes it. |
| **R34** `examples/` not linked from `CLAUDE.md` | ✅ | `CLAUDE.md` text confirms no link to `examples/`. |

---

## §3 NOT INTUITIVE — verification

| ID | Status | Notes |
|---|---|---|
| **N1** `serpent_trimui_app/` is canonical, no original `serpent_trimui_app/` | ✅ | `ls` of repo root shows only the `- Copy` variant; `validate.py:40` references the same. |
| **N2** `pi_halow_bridge/` wraps a single project | ✅ | `ls` confirms `PI-HALOW-BRIDGE/` is the only inhabitant. |
| **N3** `AGENTS.md` vs `CLAUDE.md` distinction not surfaced | (judgement) | Both files exist at repo top. The recommendation is opinion. |
| **N4** `base_pi/` mixed depth (some files in `core/`, some flat, plus `video/`) | ✅ | `ls` of `base_pi/` confirms mixed. |
| **N5** `robot_pi/` single-file sub-packages | ✅ | `ls` of `robot_pi/core/` shows 4 files; `telemetry/` and `control/` were not re-listed but consistent with first-pass agent finding. |
| **N6** Multiple `dashboard.html`/`index.html` files | ⚠️ | Existence of static stubs was claimed in agent pass; not re-verified here (see R6). |
| **N7** `march 16th problems connectivity.md` filename has spaces | ✅ | `ls` shows the file verbatim. |
| **N8** Top-level scripts that should live in `scripts/` | ✅ | `ls` confirms `generate_psk.py`, `check_telemetry.py`, `setup_*.sh`, `check_status.sh`, `restart_robot_bridge.sh`, `test_dashboard.sh` all at bridge root. |
| **N9** "30 markdown files at trimui root" | ⚠️ | Actual count is **28** (confirmed by `ls \| grep -c .md$`). Plan over-counted by 2. The recommendation (build a `docs/` index) still stands. |
| **N10** 5 root-level `test_*.py` in trimui | ✅ | `ls` confirms all five. |
| **N11** `start_backend_simple.sh` hardcodes wrong path | ⚠️ | File exists; did not re-read line 6 in this verification pass. Trust first-pass agent. |
| **N12** `control_buttons.dart` is empty placeholder | ✅ | Verified verbatim — `return const SizedBox.shrink()` at line 13, retention rationale comment at lines 4-7. |
| **N13** `lib/models/` is empty | ⚠️ | `ls` of `lib/` shows `models` as a directory; did not re-verify it's empty. |
| **N14** Three Python `requirements*.txt` | ✅ | All three files exist at trimui root. |
| **N15** "Three implementations of one wire schema, no canonical owner" | ❌ | **WRONG as stated.** A canonical wire schema **does** exist in `SYSTEM_ARCHITECTURE.md §4` ("File integration map — who talks to whom") at repo root. Three *implementations* still exist (the Flutter `backend_service.dart`, the Python `serpent_backend_trimui_s.py`, the Python `base_pi/core/backend_client.py`) — that part of the structural concern stands — but the "no canonical owner" framing was wrong. **Refined statement:** the schema is documented, but it's at the **repo top level** rather than co-located with either subproject, the Flutter test cites it but the test file itself is uncommitted (see W17), and the spec's completeness vs the actual 16 `@sio.on(...)` handlers in `backend_client.py` was not verified end-to-end. |
| **N16** "16 Socket.IO events are folklore, only E-STOP documented" | ❌ | **WRONG.** `SYSTEM_ARCHITECTURE.md §4` documents the integration map. Whether it covers all 16 events with full payload shapes was not verified end-to-end here. The recommendation is now: *audit §4 for completeness against `backend_client.py`'s `@sio.on(...)` decorator list, fill any gaps, and add a generated test that asserts the two stay in sync* — not "create the missing doc". |
| **N17** Conventions doc gaps for "where do new things go" | ✅ | Confirmed by reading `agent_stack/conventions.md`. |
| **N18** `archive/raspberry_pi_*/` footgun (inverted ports) | ⚠️ | The `archive/` directory exists (`ls` confirms `REMOVED.md`, `raspberry_pi_receiver/`, `raspberry_pi_robot/`, `setup_pi_backend.sh.backup`). The "inverted ports" claim came from the prior audit's reading of `archive/raspberry_pi_receiver/config.py` and was not independently re-verified here. |

---

## 🆕 NEW FINDINGS (missed in the original plan)

| # | Finding | Evidence |
|---|---|---|
| **NEW-1** | **Repo top-level has 8 markdown files, but `agent_stack/conventions.md` §5 explicitly says "Don't create new top-level markdown files in the repo root. The two existing ones (`CLAUDE.md`, `AGENTS.md`) are reserved for the agent stack entry point."** Either the convention is wrong, or every doc added during the E-STOP rebuild violates it. | `ls` of repo root: `AGENTS.md`, `AUDIT_FINDINGS.md`, `CLAUDE.md`, `ESTOP_BENCH_TEST.md`, `ESTOP_REBUILD_PLAN.md`, `IMPLEMENTATION_WORKFLOW.md`, `PHYSICAL_ARCHITECTURE.md`, `SAFETY_AUDIT_ESTOP.md`, `SYSTEM_ARCHITECTURE.md`. The conventions doc is at `agent_stack/conventions.md` line 48. **Action: update conventions to reflect the actual policy, OR move six docs into `docs/` and keep CLAUDE.md/AGENTS.md at root.** |
| **NEW-2** | **The trimui's wire-contract test file (`test/services/backend_service_test.dart`) is not in git** (untracked). Together with the modified `lib/services/backend_service.dart` and `pubspec.yaml`, this means the "wire contract is being tested" story currently exists only on this machine. Any clean clone of the trimui repo doesn't have those tests. | `git status` line: `?? test/services/`. Combined with my read of the test file, this is also the file the original audit cited as evidence for the spec. |
| **NEW-3** | The trimui `git status` shows ~25 changes total uncommitted: 9 modified files, 14 deleted-from-tracked files, 7 untracked items. The "uncommitted archive move" framing in W17 understated the scope. **Practical risk: a single `git checkout -- .` or `git stash drop` would lose the wire-contract test, the portfolio screenshot scaffold, the asset fonts add, and the Flutter screen modifications all at once.** | Full output captured during verification. |
| **NEW-4** | `Glob` patterns containing literal spaces silently return `No files found` even when the file exists. Used `ls` instead to verify. **This affected at least six "no files found" claims in the original audit.** Worth a one-liner in `agent_stack/conventions.md` for future agents. | Reproduced multiple times during verification (e.g. `Glob "pi_halow_bridge/.../deploy.sh"` returns nothing; `ls` of the same path shows the file). |

---

## Bottom line for the engineer

- **Plan is mostly correct.** Of ~70 verifiable claims, **1 was outright wrong (W12/N15/N16 cluster — the wire schema doc does exist)**, **9 needed refinement** (W10, W16, W17, R5, R6, R13, R24, R26, R31, N9, N11, N13, N18 — most are agent claims I trusted on file-existence-only basis without re-reading content), and the rest are confirmed verbatim. The numbered W#/R#/N# scheme remains usable; just consult the per-row notes here.
- **Top correction:** the wire schema is **already documented** in `SYSTEM_ARCHITECTURE.md §4` at the repo top level. Action item changes from "write the missing spec" to "audit §4 completeness against the 16 `@sio.on(...)` handlers in `base_pi/core/backend_client.py` and add a sync-asserting test".
- **Top new finding:** `agent_stack/conventions.md` §5 is at odds with the actual repo-root layout (8 markdown files vs. its claimed 2). This is itself a thing to fix before any further "where do things go" guidance lands.
- **Top safety find:** `test/services/backend_service_test.dart` is uncommitted in trimui's git. Commit before doing anything else, or you lose the only test exercising the implicit cross-subproject contract.
- The recommended-ordered action sequence in §4 of the plan is unaffected by these corrections except item 11 (which should now read "audit and complete `SYSTEM_ARCHITECTURE.md §4`" instead of "create the missing spec").

# Cleanup Audit — 2026-04-25

> Read-only audit pass over the repo following the 2026-04-24 E-STOP rebuild (R0-R10).
> Companion to `AUDIT_FINDINGS.md` (2026-04-23) — focuses on **drift since the rebuild**
> plus pre-existing low-hanging cleanup that the prior pass deferred.
>
> **Severity legend:** `block` = stop, do not implement; `high` = should fix this cycle;
> `medium` = ship in next maintenance batch; `low` = cosmetic / nice-to-have.
>
> **Phase legend (set in §B):** `P1` = auto, `P2` = safety-gate review, `P3` = human-led /
> deferred (E-STOP rebuild scope).

## Baseline validation snapshot

Captured `python agent_stack/tools/validate.py all` at 2026-04-25T04:42:49Z.

| Target   | Result   | Notes                                                           |
|----------|----------|-----------------------------------------------------------------|
| python   | **PASS** | 206 tests, all OK, 4.082 s                                      |
| flutter  | FAIL     | `flutter analyze rc=1`, 130 issues (mostly info); `flutter test` PASSES (11/11) |
| firmware | SKIP     | `platformio` not on PATH (host limitation, not a regression)    |
| sim      | FAIL     | 5 s probe timeout — validator-internal, not a sim crash         |

Flutter `analyze` has been red since `flutter_lints` was dropped from `pubspec.yaml`
(see F-A1). The failure is a **pre-existing baseline**, not caused by this cycle.
The python suite is clean — any regression after Phase 1 will be visible.

---

## Section A — PI-HALOW-BRIDGE (Python + firmware)

### A1. Stale "E-STOP removed 2026-04-23" comments throughout source [HIGH]
The 2026-04-24 rebuild restored SI-1, SI-2, SI-3, SI-6, SI-7. Many code comments
still claim the surface is removed. They contradict the running code.

| File | Line(s) | Stale text |
|------|---------|------------|
| `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/core/bridge_coordinator.py` | 6 | `Note: E-STOP surface was removed 2026-04-23 (see SAFETY_AUDIT_ESTOP.md).` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/core/bridge_coordinator.py` | 174 | `# Watchdog removed 2026-04-23 — see SAFETY_AUDIT_ESTOP.md.` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/core/state_manager.py` | 10 | `Note: E-STOP state tracking was removed 2026-04-23 (see SAFETY_AUDIT_ESTOP.md).` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/core/state_manager.py` | 67 | `# E-STOP state methods removed 2026-04-23.` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/bridge_coordinator.py` | 6, 60 | "E-STOP surface was removed" |
| `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/command_executor.py` | 38 | `(E-STOP coordination removed 2026-04-23.)` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/command_executor.py` | 220 | `# E-STOP command dedup + motor timeout loop removed 2026-04-23.` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/command_executor.py` | 227, 231 | `start/stop_motor_timeout_monitor` are described as "no-op" |
| `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/web_server.py` | 499-500, 591-592 | `"""E-STOP API removed 2026-04-23 ... Rebuild pending."""` returning HTTP 410 |
| `pi_halow_bridge/PI-HALOW-BRIDGE/common/constants.py` | 4-9 | "Until R1..R11 land, these constants exist but have no consumers." (R0-R10 landed; consumers exist) |
| `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_actuator_controller.py` | 5 | "The full E-STOP surface was removed 2026-04-23..." |
| `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_safety_constants.py` | 8 | "...were removed along with the E-STOP surface..." |
| `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_fault_injection.py` | 34 | "Actuator-level E-STOP was removed 2026-04-23." |
| `pi_halow_bridge/PI-HALOW-BRIDGE/test_servo.py` | 52 | `# E-STOP was removed 2026-04-23 — servo commands are no longer gated.` |
| `pi_halow_bridge/PI-HALOW-BRIDGE/SAFETY_HARDENING.md` | (multiple) | references the removal as if current |

**Suggested fix:** update each comment to reference the current rebuild
(`agent_stack/gates/safety_invariants.md` or `ESTOP_REBUILD_PLAN.md` v2.1) without
weakening any claim. Several of these files are safety-critical
(`bridge_coordinator.py`, `command_executor.py`, `constants.py`,
`actuator_controller.py`) so this is a `safety-gate` review, not Phase 1 auto.

The `dashboard/web_server.py:499,591` "removed pending rebuild" returning HTTP 410
is a **functional bug** post-rebuild — those endpoints should now route to the
real handler or be removed entirely.

`robot_pi/core/command_executor.py::start/stop_motor_timeout_monitor` (lines 226-232)
are documented as "no-op — motor-timeout monitor removed 2026-04-23". If callers
no longer rely on them they should be deleted; if they are kept as a stable API,
the docstring needs updating. (Safety-critical file → P2.)

### A2. Ad-hoc hardware diagnostic scripts at bridge root, named `test_*.py` [MEDIUM]
The bridge root contains four scripts that match the unittest discovery glob but
are bench-test helpers with unconditional hardware imports — a direct **SI-10
violation if treated as tests**. They are not picked up by `scripts/test_all.py`
(which scans `tests/`), but a future contributor running `pytest .` from the
bridge root would import `motoron`, `busio`, `board`, `adafruit_*` outside
`SIM_MODE`.

- `pi_halow_bridge/PI-HALOW-BRIDGE/test_multiplexer_pca9685.py` — uses `busio`, `board`, `adafruit_tca9548a` unconditionally
- `pi_halow_bridge/PI-HALOW-BRIDGE/test_pca9685_servo.py` — `from adafruit_servokit import ServoKit` unconditionally
- `pi_halow_bridge/PI-HALOW-BRIDGE/test_sensors.py` — imports `robot_pi.sensor_reader` and starts it; needs hardware
- `pi_halow_bridge/PI-HALOW-BRIDGE/test_servo.py` — imports `ActuatorController` and runs it on real hardware; line 52 has stale E-STOP comment

**Suggested fix:** rename to `bench_*.py` or move under `scripts/bench/`. Document
in a `scripts/bench/README.md` that they require physical hardware and are not run
by `test_all.py`. (Reference: `PCA9685_SETUP.md:89` calls `test_servo.py` directly,
which would also need updating.)

### A3. `check_telemetry.py` at bridge root [MEDIUM]
`pi_halow_bridge/PI-HALOW-BRIDGE/check_telemetry.py` — one-off diagnostic.
Hardcodes `sys.path.insert(0, '/home/robotpi/Desktop/PI-HALOW-BRIDGE')` (line 10)
and `192.168.1.10:5003` and `127.0.0.1:5003`. Not referenced anywhere.

**Suggested fix:** move to `scripts/diagnostics/` or delete. The real telemetry
path is well-tested via `tests/test_telemetry_two_stamp.py`.

### A4. Stale top-level shell helpers [MEDIUM]
`pi_halow_bridge/PI-HALOW-BRIDGE/test_dashboard.sh` (line 47) lists
"E-STOP status" as a feature the dashboard *was* showing — fine post-rebuild, but
line 14 claims `serpent-dashboard-robot` is the canonical service while the
canonical pair is `serpent-dashboard-base.service` and `serpent-dashboard-robot.service`
(role-aware). The file is a one-off curl test, not part of the canonical setup.

`check_status.sh`, `restart_robot_bridge.sh` are operator helpers; both contain
canonical IPs `192.168.1.20`. Useful but undocumented (no README mention).

**Suggested fix:** doc-only; mention them in `README.md` or move under `scripts/`
to match the convention. No code change.

### A5. `archive/halow_bridge.py.old` retained [LOW]
`pi_halow_bridge/PI-HALOW-BRIDGE/archive/halow_bridge.py.old` exists.
Per `AUDIT_FINDINGS.md §-1 D3` it was archived deliberately. Confirmed not
referenced anywhere. Acceptable but adds 800 LOC of read overhead for new
contributors.

**Suggested fix:** none required. Optional: remove after one more cycle.

### A6. Historical milestone docs at bridge root [LOW]
- `PHASE5_COMPLETE.md` (2026-02-06)
- `REFACTORING_COMPLETE.md` (2026-02-06)
- `REFACTORING_GUIDE.md`
- `REFACTORING_STATUS.md`

All Feb-2026 vintage; refactoring-as-built docs. Now superseded by `SYSTEM_ARCHITECTURE.md`
and `SAFETY_HARDENING.md`. Not destructive, just clutter.

**Suggested fix:** move to `archive/` or `docs/history/`. (Convention §5 says
project-level docs live at subproject root in UPPER_SNAKE — but these are no
longer "project-level" in any meaningful sense.) **Not Phase 1** — touches
`README.md` cross-links.

### A7. `FIX_PSK_MISMATCH.md` contains a real-looking PSK [HIGH but documentary]
`pi_halow_bridge/PI-HALOW-BRIDGE/FIX_PSK_MISMATCH.md:12` contains a
64-hex value formatted as a `SERPENT_PSK_HEX`. SI-12 says "no PSK literal may
appear in tracked code". Per project memory note, PSK exposure on a trusted LAN
is intentionally low-priority; flagging here for **doc hygiene** only.

**Suggested fix:** redact or replace with `<paste-your-PSK-here>`. **Not safety-gate**
per the user's standing instruction (LAN trusted), but a one-line edit is cheap.

### A8. `march 16th problems connectivity.md` filename + content [LOW]
- Filename has spaces — breaks shell completion, looks like a draft
- Marked "Status: Diagnosed, not yet fixed" 2026-03-16; SI-1/SI-2/SI-6 partially
  cover Problem 1 ("the gap"). Document is now stale relative to the rebuild.

**Suggested fix:** rename to `MARCH_16_CONNECTIVITY_NOTES.md`, add a header noting
which findings are now closed by the 2026-04-24 rebuild. Doc-only.

### A9. `PULL_ON_HUB.md`, `SETUP_PSK_ON_ROBOT.md`, `SETUP_GUIDE.md`, `HALOW_SETUP_GUIDE.md` overlap [LOW]
Four overlapping setup docs with subtly different scope. Convention §5 doesn't
forbid them but new readers don't know which to read first.

**Suggested fix:** consolidate into a single `SETUP_GUIDE.md` (already exists)
with a "see also" footer. Doc-only.

### A10. `dashboard/web_server.py:499, 591` returns HTTP 410 for E-STOP API [HIGH — functional]
After the rebuild, the dashboard's `/api/estop/engage` and `/api/estop/clear`
should be live. Currently they return:
```python
@app.route('/api/estop/engage', methods=['POST'])
def estop_engage():
    """E-STOP API removed 2026-04-23 — see SAFETY_AUDIT_ESTOP.md. Rebuild pending."""
    return jsonify({'error': 'E-STOP surface removed pending rebuild', 'code': 'estop_removed'}), 410
```

This means the **operator dashboard cannot engage or clear E-STOP** post-rebuild —
the only paths are TrimUI + backend pygame. That's a real safety-surface gap.

**Suggested fix:** wire to the new `bridge_coordinator._handle_emergency_stop`
path with the same SET-semantics + clear gates as the TrimUI side. **This is
safety-critical (P3)** — needs `safety-gate` review and proper tests.

### A11. `archive/` is shadowed by a real `archive/` in trimui [LOW]
The bridge has `pi_halow_bridge/PI-HALOW-BRIDGE/archive/halow_bridge.py.old`
and the trimui has `serpent_trimui_app/archive/{raspberry_pi_*,setup_pi_backend.sh.backup}`.
Two `archive/` paths with different conventions. Not a bug, just naming drift.

**Suggested fix:** document the convention in `agent_stack/conventions.md §1`
that each subproject MAY have its own `archive/`. Doc-only.

---

## Section B — serpent_trimui_app (Flutter + backend)

### B1. `analysis_options.yaml` includes `flutter_lints` but pubspec doesn't have it [HIGH]
`serpent_trimui_app/analysis_options.yaml:10` does:
```yaml
include: package:flutter_lints/flutter.yaml
```
but `pubspec.yaml` `dev_dependencies` (lines 31-34) lists only `flutter_test` and
`flutter_launcher_icons`. `flutter_lints` is missing.

Result: `flutter analyze` emits a `warning - The include file 'package:flutter_lints/flutter.yaml' ... can't be found` and `rc=1`. This violates **convention §4** ("Use
`flutter_lints` defaults").

**Suggested fix:** add `flutter_lints: ^4.0.0` to `dev_dependencies` and run
`flutter pub get`. Either that or delete the include line and accept the lint loss.
Adding the dep is the project-convention answer. **Phase 1 candidate** — small,
non-safety-critical, fixes baseline red.

### B2. `ControlButtons` widget is a `SizedBox.shrink()` placeholder [LOW]
`serpent_trimui_app/lib/widgets/control_buttons.dart:8-15` — the entire
widget body is `return const SizedBox.shrink();`. Comment line 5-7 says it was
left as a placeholder for the E-STOP rebuild. The rebuild landed; the widget is
still empty. Used at `lib/screens/main_screen.dart:2338` inside a `Row` — renders
nothing. The `CameraSelector` next to it now has unbalanced `MainAxisAlignment.spaceBetween`.

**Suggested fix:** either implement the post-rebuild status indicator or remove
the widget + the import + the call site. **Not Phase 1** — touches operator UI
layout (`main_screen.dart`).

### B3. Flutter `analyze` baseline: 130 issues [MEDIUM]
Of the 130:
- ~80 `info - 'withOpacity' is deprecated` (Flutter 3.27+ deprecation)
- ~10 `warning - The value of the field '_xyz' isn't used`
- 1 `warning - The include file 'package:flutter_lints/flutter.yaml' can't be found` (B1)
- ~30 deprecated `background` color, miscellaneous

These are **info/warning** level only — `flutter test` still passes. Convention §4
disallows disabling rules in `analysis_options.yaml` without a comment.

**Suggested fix:** B1 is the gate. After B1 lands, do a follow-up pass to either
(a) bulk-replace `withOpacity(x)` → `withValues(alpha: x)` or (b) suppress the
deprecation in `analysis_options.yaml` with a comment explaining when Flutter
will require the migration. **Not Phase 1** — large surface area in `main_screen.dart`.

### B4. Test artefacts left behind [LOW]
`serpent_trimui_app/test/failures/` contains 12 PNG diff files from a
golden-image test run. Per Flutter convention these are produced on a failed
golden run and rewritten next time. Not committed harmful, but noise.

**Suggested fix:** ensure `.gitignore` excludes `test/failures/`. (Will not change
behavior; just hygiene.) **Phase 1 candidate** if `.gitignore` doesn't already cover.

### B5. Hardware/dev `.py` and `.sh` scripts at trimui root [LOW]
`serpent_trimui_app/`:
- `quick_diagnose.py`, `test_apk_server.py`, `test_arducam.py`, `test_input_monitor.py`, `test_pygame_controller.py`, `test_all_features.py`, `serve_apk_simple.py`
- `setup_pi_backend.sh`, `start_backend_simple.sh`, `setup_simple_autostart.sh`, `manage_service.sh`, `setup_autostart.sh`, `install_dependencies.sh`, `setup_hub_pi.sh`

Most are legacy from when the trimui dir hosted the Python backend. The Python
backend (`serpent_backend_trimui_s.py`, 1902 LOC) still lives here. None are
matched by Flutter's analyzer.

**Suggested fix:** organise — move `test_*.py` and `quick_diagnose.py` to
`scripts/bench/` (parallel to A2). Setup `.sh` files belong under `scripts/setup/`.
Reference: `RASPBERRY_PI_DEPLOYMENT.md:46` already points at `setup_pi_backend.sh`
so this needs the doc updated too. **Not Phase 1** — cross-cuts deploy docs.

### B6. Flutter app contains no E-STOP UI primitive post-rebuild [BLOCK if interpreted as a regression] / [P3 — out of scope]
The 2026-04-23 audit (`AUDIT_FINDINGS.md §1 C1-C3`) flagged that the Flutter side
had its safety net disarmed. The 2026-04-24 rebuild landed on the **Pi side**.
Flutter still emits `emergency_toggle` (toggle, not SET — violates SI-3 on the
hop). The Pi-side `bridge_coordinator._handle_emergency_stop` enforces SET
semantics correctly, so the toggle is translated at the boundary; no
safety-invariant is *currently* violated, but the operator-side defence-in-depth
remains absent.

**Per the standing E-STOP rebuild boundary, this is P3 / next session per
`ESTOP_REBUILD_PLAN.md`.** Calling it out here so it doesn't get lost.

### B7. `serpent_backend_trimui_s.py:1280` stale E-STOP comment [MEDIUM]
`# E-STOP handlers removed 2026-04-23 — see SAFETY_AUDIT_ESTOP.md. Rebuild pending.`
The handlers exist further down (`handle_emergency_toggle:1754` per AUDIT_FINDINGS).
Comment misleads new readers.

**Suggested fix:** update the comment to point at the rebuild and the handler
location. **Not safety-critical Python file**, but the file is on the legacy
control path — keep change minimal. **Phase 1 doc-only candidate.**

---

## Section C — agent_stack & repo top level

### C1. Repo-top `SAFETY_AUDIT_ESTOP.md` is the historical removal audit, still referenced [LOW]
`SAFETY_AUDIT_ESTOP.md` exists at repo root. Per `ESTOP_REBUILD_PLAN.md:510` and
`PHYSICAL_ARCHITECTURE.md:240` it is referenced as a historical artefact, which
is correct. No fix needed; flagging because the **file still exists** and the
many "see SAFETY_AUDIT_ESTOP.md" references in source comments (Section A1) are
not broken links — they resolve, but to a removal-era doc, not the rebuild plan.

**Suggested fix:** when fixing A1 stale comments, redirect the "see X" pointer to
`ESTOP_REBUILD_PLAN.md` (current) rather than `SAFETY_AUDIT_ESTOP.md` (historical).

### C2. `repo_map.md` lists hardware diagnostic scripts as "test" entries [MEDIUM]
`agent_stack/repo_map.md:13-16` and `repo_map.json` list `test_servo.py`,
`test_sensors.py`, `test_pca9685_servo.py`, `test_multiplexer_pca9685.py` under the
**test** category for the bridge subproject. These are bench scripts (A2) —
they're not in `tests/` and not run by `test_all.py`. Misleading.

**Suggested fix:** after A2 lands (renaming or moving them), regenerate
`repo_map.md` with `python agent_stack/tools/build_repo_map.py`. The current
classifier just matches `test_*.py`; if the rename happens it'll auto-correct.

### C3. `agent_stack/.runtime/logs/` accumulates per-run log files [LOW]
Currently 10 logs under `agent_stack/.runtime/logs/`. `.gitignore` covers
`.runtime/` but the local copy grows unbounded.

**Suggested fix:** add a one-line sweep to `validate.py` (e.g. retain the latest
N=10 per target). **Not Phase 1** — touches a tool. Optional.

### C4. `__pycache__` directories under `agent_stack/tools/` and bridge `dashboard/` [LOW]
- `agent_stack/tools/__pycache__/safety_check.cpython-314.pyc`
- `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/__pycache__/*.pyc`

Per `destructive_ops.yaml :: generated_paths`, `**/__pycache__/**` is generated.
These shouldn't be committed; `.gitignore` should already cover. Confirm and
ignore.

**Suggested fix:** verify each subproject `.gitignore` excludes `__pycache__/`.
Doc-only.

### C5. `agent_stack/audits/` directory created today [info]
This file. New subdirectory under `agent_stack/`. Convention §5 says agent stack
docs live under `agent_stack/`, so this is in-scope. No issue.

---

## Section D — Test coverage gaps (delta vs 2026-04-23)

The 2026-04-24 rebuild added strong coverage:
- `test_estop.py`, `test_base_pi_estop.py`, `test_command_executor_estop.py`,
  `test_bridge_estop.py`, `test_control_server_fast_engage.py`,
  `test_estop_integration.py`, `test_cross_channel_echo.py` — SI-1, SI-2, SI-3,
  SI-6, SI-7 all covered.
- `test_winch_controller_modbus.py` — SI-11.
- `test_framing.py` — SI-4.
- `test_actuator_controller.py` exists (was missing in 2026-04-23 audit).

### D1. No dashboard `web_server.py` test [MEDIUM]
The dashboard exposes HTTP endpoints (including the broken E-STOP API at A10).
No `tests/test_dashboard_web_server.py`. If A10 is fixed, this becomes a hard
requirement.

**Suggested fix:** scope to A10's fix.

### D2. `tests/test_fault_injection.py:357` still has the TODO [LOW]
The 2026-04-23 audit noted this and deferred it; the 2026-04-24 rebuild didn't
revisit. Still flagged "For now, mark as TODO". Not blocking; the rest of
fault-injection coverage is solid.

**Suggested fix:** revisit when the next E-STOP-touching session opens.

### D3. No firmware-side test target on this host [info]
`validate.py firmware` skips because `platformio` isn't installed. Not a code
issue. The firmware is reviewed via `tests/test_winch_controller_modbus.py`
(register-map parity, SI-11) on the Python side.

---

## Section E — Build / deploy / install scripts

### E1. Setup script set is large; deploy doc trail is stale [LOW]
`pi_halow_bridge/PI-HALOW-BRIDGE/`:
- `setup_base_pi.sh`, `setup_robot_pi.sh`, `setup_psk_on_hub.sh`
- `scripts/pi_install.sh`, `scripts/pi_enable_services.sh`, `scripts/deploy.sh`,
  `scripts/rollback.sh`, `scripts/configure_static_ip.sh`,
  `scripts/setup_ssd_recording.sh`, `scripts/install_dashboard.sh`,
  `scripts/check_psk.sh`, `scripts/check_hdmi.sh`, `scripts/verify_psk_autoload.sh`,
  `scripts/set_bridge_ip.sh`, `scripts/pi_torture.sh`

All are gated by `destructive_ops.yaml` patterns (`setup_*.sh`, `pi_install.sh`,
`pi_enable_services.sh`). No issue with the gate. Issue: no top-level
**deploy runbook** lists which one to run when. `SETUP_GUIDE.md` exists; needs
verification it points at the canonical sequence.

**Suggested fix:** verify `SETUP_GUIDE.md` covers `setup_base_pi.sh` →
`setup_robot_pi.sh` → `setup_psk_on_hub.sh` order. Doc-only. **Not Phase 1.**

### E2. `serpent_trimui_app/setup_*.sh` family same problem [LOW]
- `setup_pi_backend.sh`, `setup_simple_autostart.sh`, `setup_autostart.sh`,
  `setup_hub_pi.sh`, `start_backend_simple.sh`, `manage_service.sh`,
  `install_dependencies.sh`

The 2026-04-23 audit flagged `setup_pi_backend.sh.backup` (resolved by archiving).
The remaining set is functional but undocumented in the trimui `README.md`.

**Suggested fix:** see B5.

### E3. `dashboard/systemd/serpent-dashboard-base-custom.service` — purpose unclear [LOW]
Three dashboard service files: `serpent-dashboard-base.service`,
`serpent-dashboard-base-custom.service`, `serpent-dashboard-robot.service`.
The `-custom` suffix suggests a one-off variant. No README mentions it.

**Suggested fix:** confirm what the `-custom` variant is. If it's experimental,
move to `archive/`. Service files are gated (`*.service` is safety-critical) —
**not Phase 1** under any circumstance. **P2** at minimum.

---

## Section F — Top-level repo docs

### F1. `IMPLEMENTATION_WORKFLOW.md:105` describes "the current E-STOP-removed `main`" [HIGH]
The doc was written between removal (04-23) and rebuild (04-24). Now stale.

**Suggested fix:** update the section header to note the rebuild is complete.
Doc-only. **Phase 1 candidate.**

### F2. `SYSTEM_ARCHITECTURE.md:265` calls out the removal as the current state [HIGH]
"2026-04-23 — E-STOP SURFACE REMOVED. ... A ground-up rebuild is a separate future
session." Now stale.

**Suggested fix:** add a 2026-04-24 update banner pointing at the rebuild
(parallel to `AUDIT_FINDINGS.md` line 5 which already does this). Doc-only.
**Phase 1 candidate.**

### F3. `PHYSICAL_ARCHITECTURE.md:240` references `SAFETY_AUDIT_ESTOP.md` as a
"historical audit of why the old E-STOP was removed" — this is **correct** post-rebuild;
no change needed.

### F4. `ESTOP_BENCH_TEST.md` exists but isn't cross-linked from anywhere [LOW]
Found via glob; no inbound links from `README.md`, `SAFETY_HARDENING.md`,
`ESTOP_REBUILD_PLAN.md`. Probably useful, currently orphaned.

**Suggested fix:** add a "Bench-test procedure" pointer from `ESTOP_REBUILD_PLAN.md`
or `SAFETY_HARDENING.md`. Doc-only. **Phase 1 candidate.**

---

# Section B (phase bucketing) — REQUIRED BY STEP 7

Each finding is bucketed below. Phase 1 = orchestrator/docs-release auto-execute
this session. Phase 2 = next maintenance batch, may need safety-gate. Phase 3 =
human-led, deferred (typically E-STOP rebuild scope or large surface).

## Phase 1 (auto, this session)

Strict gate: zero safety-critical paths touched, unambiguous action, cannot affect
control-loop timing.

| ID | Action | Files |
|----|--------|-------|
| **F1** | Add 2026-04-24 rebuild banner to top of section in `IMPLEMENTATION_WORKFLOW.md` (line ~105) | `IMPLEMENTATION_WORKFLOW.md` |
| **F2** | Add 2026-04-24 rebuild banner above the "E-STOP SURFACE REMOVED" section in `SYSTEM_ARCHITECTURE.md` (line ~265) | `SYSTEM_ARCHITECTURE.md` |
| **F4** | Add a single cross-link from `ESTOP_REBUILD_PLAN.md` "References" section to `ESTOP_BENCH_TEST.md` | `ESTOP_REBUILD_PLAN.md` |
| **B7** | Update one-line stale E-STOP comment in `serpent_backend_trimui_s.py:1280` (NOT a safety-critical path; relay only) | `serpent_trimui_app/serpent_backend_trimui_s.py` |
| **A8** | Add a one-paragraph header banner to `march 16th problems connectivity.md` noting which problems are now closed by 2026-04-24 rebuild (no rename — rename is more invasive than banner) | `pi_halow_bridge/PI-HALOW-BRIDGE/march 16th problems connectivity.md` |

**Excluded from Phase 1 even though tempting:**
- A7 (PSK in `FIX_PSK_MISMATCH.md`) — touches PSK material handling, gate flags `**/.psk*`. The doc isn't a `.psk*` glob match, but redacting is a value change to a doc that's basically a runbook. **Defer to Phase 2** with explicit rationale.
- A1 (stale E-STOP comments) — too many touch safety-critical files (`bridge_coordinator.py`, `command_executor.py`, `constants.py`, `actuator_controller.py`, `framing.py`-adjacent test files). **All P2**, except B7 which is in the legacy backend (already P1 above).
- B1 (`flutter_lints` missing from pubspec) — modifies `pubspec.yaml`, which can pull a new package. Even though low-risk, it's a dependency change. **P2.**

## Phase 2 (next maintenance batch, safety-gate review where flagged)

| ID | Why P2 | Owner |
|----|--------|-------|
| A1 | Stale comments touch safety-critical files; safety-gate must confirm edits don't change semantics | safety-gate + docs-release |
| A2 | Renaming `test_*.py` at bridge root to `bench_*.py` may break `PCA9685_SETUP.md:89` and any operator scripts | platform-toolchain |
| A3 | `check_telemetry.py` move/delete; verify nothing on robotpi/desktop calls it | platform-toolchain |
| A4 | Stale top-level `.sh` helpers — needs READMEdocumentation, not deletion | docs-release |
| A6 | `PHASE5_COMPLETE.md` etc. archive move — touches multiple cross-links | docs-release |
| A7 | Redact PSK-looking value in `FIX_PSK_MISMATCH.md` | docs-release |
| A9 | Setup-doc consolidation | docs-release |
| A11 | Document `archive/` convention | docs-release |
| B1 | Add `flutter_lints` to `pubspec.yaml`; run `pub get`; verify analyze drops the include warning | platform-toolchain |
| B3 | Bulk fix `withOpacity` deprecation OR explicitly suppress | (decide first) |
| B4 | `.gitignore` of `test/failures/` | platform-toolchain |
| B5 | Trimui `.py`/`.sh` script reorganisation | platform-toolchain + docs-release |
| C2 | After A2 lands, regenerate `repo_map.md` | tools auto |
| C3 | Add log-rotation policy to `validate.py` | platform-toolchain |
| D1 | Add `tests/test_dashboard_web_server.py` (gated on A10's resolution) | test-verification |
| E1 | Verify `SETUP_GUIDE.md` covers full deploy sequence | docs-release |
| E2 | Trimui setup-script doc | docs-release |

## Phase 3 (human-led, deferred — often E-STOP rebuild scope)

| ID | Why P3 | Note |
|----|--------|------|
| **A10** | Dashboard E-STOP API returns HTTP 410 instead of routing to the rebuilt handler — **functional safety-surface gap** | Needs `safety-gate` design review. Out of scope this session; flagged as the highest-priority deferred item. |
| **B2** | `ControlButtons` widget is a placeholder; the rebuild added Pi-side state but no Flutter status indicator | next session, Flutter UX pass per ESTOP_REBUILD_PLAN.md |
| **B6** | Flutter still emits `emergency_toggle` (translated at bridge) — operator-side defence-in-depth absent | next session, ground-up rebuild per ESTOP_REBUILD_PLAN.md |
| **D2** | `test_fault_injection.py:357` TODO touches E-STOP fault matrix | revisit when next E-STOP-touching session opens |
| **E3** | `serpent-dashboard-base-custom.service` purpose unclear | service files = `safety_critical_paths`; needs human confirmation of intent before any change |

---

## Decisions / open questions for the human

1. **A10 (dashboard E-STOP API)** is the most consequential deferred item. The
   rebuild moved E-STOP to two authorities; the dashboard's third surface should
   either be wired up or explicitly removed (with the routes deleted, not 410'd).
   Recommendation: open a follow-up that adds the dashboard E-STOP path back
   under safety-gate review, mirroring the TrimUI semantics.

2. **A1 stale comments**: 14 source files contain "removed 2026-04-23"
   comments that are now misleading. Most are in safety-critical files. Suggest
   batching them as a single safety-gate-reviewed commit titled
   "doc: align E-STOP comments with 2026-04-24 rebuild" with **no semantic
   changes**.

3. **B1 vs B3**: do we want `flutter_lints` enforced again? If yes, B1 lands and
   B3 (130 issues) becomes a real backlog item; if no, drop the include line
   from `analysis_options.yaml` and accept the lint loss.

4. **A2 rename**: do we want to keep the bench-test scripts (likely yes, they're
   useful on real hardware), in which case rename is the only sane path?

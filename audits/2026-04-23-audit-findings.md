# Serpent Real Prototype — Audit Findings

> Generated 2026-04-23 by the `debug-triage` agent in a read-only pass over both subprojects. Companion to `SYSTEM_ARCHITECTURE.md`.
>
> **2026-04-24 — E-STOP REBUILD COMPLETE.** The rebuild landed per `ESTOP_REBUILD_PLAN.md` v2.1 (milestones R0–R10). All E-STOP-related findings below (C1, C2, C3, D7, T3, T5, and anything referencing `emergency_toggle` / `estop_clear_progress` / watchdog) are now closed by the rebuild rather than the prior 2026-04-23 removal. The current safety architecture has two authorities (Robot Pi + Base Pi), bidirectional cross-channel echo, two-phase atomic clear, persistent state across reboots, and distributed fast-engage from control-server exception branches. See `agent_stack/gates/safety_invariants.md` for the per-invariant file map.
>
> **2026-04-23 — E-STOP REMOVED (historical).** Original removal note retained for trail: all E-STOP-related findings were initially resolved by *removing* the E-STOP surface wholesale before the rebuild. The audit body is preserved verbatim; §-1 has the rest of the non-E-STOP sweep.

---

## -1. Resolution sweep — 2026-04-23

**Scope:** The user asked for every finding to be fixed *except* anything that touches the Flutter-side E-STOP logic (it is known-quirky and being worked on separately). Safety-gate reviewed and `approve`-d every change that touched a safety-critical path.

### Fixed ✅

| Finding | What was done |
|---|---|
| **C4** watchdog default unsafe | `dashboard/config.py:61` — `DISABLE_WATCHDOG_FOR_LOCAL_TESTING` env default flipped `'True'` → `'False'`; comment expanded to clarify that the robot-side watchdog is unaffected either way. Safety-gate `approve`. |
| **C5 / F1** `raspberry_pi_receiver/` and `raspberry_pi_robot/` with inverted ports | Both moved to `serpent_trimui_app/archive/` with a `REMOVED.md` note explaining why and blocking casual restore. |
| **§2 toggle_cv silent-drop** | `serpent_backend_trimui_s.py` gained a `@socketio.on('toggle_cv')` relay handler that updates `state.cv_enabled` and broadcasts `cv_status`. |
| **§2 gamepad_command silent-drop** | New `@socketio.on('gamepad_command')` relay handler broadcasts to the bridge. |
| **§2 r1_button silent-drop** | New `@socketio.on('r1_button')` relay handler broadcasts; bridge's existing `backend_client.py:168` listener now receives events. |
| **§2 clamp_close / clamp_open not forwarded** | Handlers were emitting `clamp_status` (event name nobody listens for); they now additionally emit `clamp_close` / `clamp_open` so bridge's `backend_client.py:136,141` listeners receive them end-to-end. |
| **§2 `chainsawForce` / `ropeForce` dead camelCase branches** | `backend_service.dart:421-422` cleaned — only `chainsaw_force` / `rope_force` (the real wire names) remain. |
| **D1** archived the obsolete Pi scaffolds | see C5 above. |
| **D2** 460-line commented-duplicate preamble in `serpent_backend_trimui_s.py` | Stripped. File is now 1902 lines (was 2362). Live docstring is line 1. |
| **D3** `halow_bridge.py.old` + stale README pointer | Moved to `PI-HALOW-BRIDGE/archive/`. `base_pi/README.md:13,85` updated to point at `core/bridge_coordinator.py`. |
| **D4** stray `chmod`, `echo`, `sudo`, `600`, `nul` files | Deleted from `PI-HALOW-BRIDGE/` and `serpent_trimui_app/`. **See security note below — these contained a real PSK.** |
| **D6** `setup_pi_backend.sh.backup` | Archived. |
| **T1** `widget_test.dart` pointing at non-existent icon | Rewritten as a real smoke test of `SerpentApp` → `SplashScreen` (no network touched). |
| **T4** no Modbus register-map test | `tests/test_winch_controller_modbus.py` added with 15 assertions locking HR0-2, IR0-8, and the 5 status-flag bit positions on both the Python (`winch_controller.py`) and firmware (`winch_station.ino`) sides. SI-11 now has unit-test coverage. Verified: all 15 pass. |
| **F2** `telemetry_websocket.py` default port collision risk | Default port changed 5005 → 5007 with a comment directing callers to pass `config.DASHBOARD_WS_PORT` explicitly. |
| **F3** `terminal_dashboard.py` hardcoded port 5006 | Now imports `dashboard.config.DASHBOARD_PORT`, with env fallback, so it works on either role. |
| **F5** splash-screen IP hint was emulator loopback | `10.0.2.2:5000` → `192.168.1.10:5000` (canonical Base Pi). |
| **A1** stale `scripts/setup_*.sh` glob in gate | Left in place — harmless (broader glob still catches real setup scripts). Widened gate with four real paths instead. |
| **A2** `sensor_reader.py` unprotected | Added to `destructive_ops.yaml :: safety_critical_paths`. Safety-gate `approve`. |
| **A3** `session_state.json` promised by `CLAUDE.md` but missing | Created at `agent_stack/.runtime/session_state.json` with the v1 schema. Round-trip verified via `smoke_test.py` (9/9 checks on session-state handling). |
| **A4** `dashboard/config.py` not in gate | Added. |
| **A5** `control_forwarder.py`, `telemetry_receiver.py` unprotected | Both added. |
| **§6 items 1-2** clamp TODOs | Resolved by the clamp relay fix above — the TODO was "implement actual clamp control" in the backend; that layer is a relay, so the TODO was misplaced, and actuation now reaches the bridge (actual hardware control is owned by the Robot Pi, already wired). |

### Deferred (E-STOP — per user instruction) 🟡

| Finding | Why deferred |
|---|---|
| **C1** six "DISABLED FOR TESTING" safety blocks in `backend_service.dart` | E-STOP behaviour; user is working on it separately. Pi-side enforcement (SI-2/SI-6) is unchanged. |
| **C2** `emergency_toggle` toggle-semantics violation of SI-3 | Same. |
| **C3** backend `handle_emergency_toggle` cannot ever CLEAR | Same. |
| **§2 `emergency_toggle` legacy handling** | Same. |
| **§2 `estop_clear_progress` no Flutter listener** | Same. |
| **D7** dead `_triggerSafetyEmergencyStop` function | Same. |
| **T3** no `test_actuator_controller.py` | The actuator controller owns E-STOP atomicity; any test here would assert E-STOP semantics the user is mid-changing. Re-open once the E-STOP work lands. |
| **T5** `test_fault_injection.py:357` TODO | Touches the E-STOP fault-injection matrix. |

### Resolved — second sweep 2026-04-23 ✅

All seven "still open" items below were closed after a `repo-architect` reasoning pass + `test-verification` design pass. Resolutions:

| Q | Finding | Resolution |
|---|---|---|
| Q1 | `winch_control` / `chainsaw_command` / etc. never emitted by Flutter | **Reasoning revealed the premise was wrong.** `handle_input_event` at `serpent_backend_trimui_s.py:1369-1629` is the real producer of those events and is driven by Flutter's `sendInputEvent`. The pygame poller only handles camera/fullscreen. Production deploys work fine. No code change. |
| Q2 | 15 `// TODO: Implement` stubs in `main_screen.dart:780-928` | **Deleted** (per Q1, the backend is authoritative). 0 remaining `TODO: Implement` in `lib/screens/main_screen.dart`. |
| Q3 | Dead backend broadcasts | `trimui_button` (line 1292) and `trimui_input` (line 1629) were pure wire-duplicates of `raw_button_press` and `input_event`; **deleted with a marker comment at each removal site**. `claw_command`, `menu_command`, `camera_switch` kept — they have plausible dashboard consumers. |
| Q4 | `usesCleartextTraffic="true"` | **Documented** as an accepted design position in `SYSTEM_ARCHITECTURE.md §5.3`. The threat model treats the LAN as the trust perimeter; TLS alone (without mutual auth) wouldn't stop spoofing, and cert pinning has a bad rotation UX on the TrimUI. The safety boundary is already at the Base Pi HMAC step. |
| Q5 | `BACKEND_URL` defaults to localhost | `base_pi/core/backend_client.py` gained a disconnect-watcher thread that WARNs every 10 s while unreachable (see `_run_disconnect_watcher` / `_start_disconnect_watcher`). `base_pi/README.md` gained one sentence documenting the canonical single-host deploy and the env override for split-host dev. |
| Q6 | Low-priority TODO backlog | `scripts/stress_network_sim.py` — `duplicate_pct` and `reorder_pct` added to `ProxyConfig` and wired into the two previously-stubbed tests, exercising SI-4 replay and seq-monotonicity checks. `base_pi/telemetry_storage.py:331` TODO comment replaced with "intentionally empty — bulk export is not a current requirement". `serpent_backend_trimui_s.py:1185-1192` — 8× "Unmapped (TODO: drive forward)"-style entries normalised to just `'Unmapped'`. `tests/test_fault_injection.py:357` left as-is per E-STOP freeze. |
| Q7 | No `BackendService` contract tests | `lib/services/backend_service.dart` refactored to expose a `SocketLike` duck-type seam via `@visibleForTesting attachSocketHandlers(SocketLike)`. New test file `test/services/backend_service_test.dart` covers 8 behaviours with a hand-rolled `_FakeSocket`: chainsaw_force/rope_force parsing, clamp event-name contract, height/force payload shape, imu/baro partial-update non-clobber, system_state→telemetry override, latency_pong timestamp handling, gamepad_status null-name coercion, pitch-math identity+45° (flags the latent division-by-zero bug in the pitch formula at ±90° via an inline comment). No `mocktail` dep. |

### Still open — E-STOP only

Everything outside the E-STOP surface is now either fixed, reasoned through, or explicitly documented as an accepted design. E-STOP findings (C1, C2, C3, D7, T3, T5, `emergency_toggle`, `estop_clear_progress`) remain deferred per user instruction — being reworked separately.

### Incidentally, during cleanup — PSK found in stray files

The D4 stray files (`chmod`, `echo`, `sudo`, `600`) contained a real `SERPENT_PSK_HEX` value that had been written there by a redirected shell command. Files were deleted as part of the D4 cleanup. Per project stance the LAN is trusted so this is not being treated as an incident; SI-12 ("PSK never in VCS") remains the rule for new code going forward.

---

## 0. Executive summary — what needs attention

1. **The Flutter app has disarmed its own safety net.** Six blocks in `backend_service.dart` — watchdog, E-STOP-on-disconnect, debounce, local override — are commented "DISABLED FOR TESTING". That means the bridge's SI-2/SI-6 defences only fire from the Pi side; the handheld no longer backstops them.
2. **E-STOP is sent as toggle, not SET.** Flutter emits `emergency_toggle` (line 666, 727). The serpent_backend's `handle_emergency_toggle` force-engages. A clear only ever happens through a separate Y-button 5 s hold in `handle_input_event`. The bridge-side `backend_client.py` is doing fragile translation to cover this mismatch.
3. ~~**The Flutter app is a passive UI.**~~ **CORRECTED 2026-04-23:** this claim was wrong. The Flutter app *does* drive actuation — it emits `input_event`/`raw_button_press` to the backend, which maps them to the high-level action events (`winch_control`, `chainsaw_command`, `climb_command`, `brake_command`, `traverse_command`) inside `handle_input_event` at `serpent_backend_trimui_s.py:1369-1629`. The backend's pygame-poller loop only synthesises camera prev/next/fullscreen. Production deploys without a local gamepad on the backend Pi work fine. The 15 `// TODO: Implement` stubs in `main_screen.dart` were *local-echo* code, not the live path — they have been deleted.
4. **`raspberry_pi_receiver/` and `raspberry_pi_robot/` are obsolete scaffolds with inverted port assignments** (control ↔ video swapped). If anyone follows either README, they will mis-wire the safety ports.
5. **Flutter has essentially no tests.** Two test files; the only real one is the Flutter starter-template counter test, which already points at a widget that doesn't exist.
6. **`serpent_backend_trimui_s.py` is 2362 lines, ~40 % commented out**, with the top 474 lines being a commented copy of code that appears live further down. Maintenance hazard.

---

## 1. Critical — immediate safety / runtime risk

| # | Sev | Evidence | Why it matters |
|---|---|---|---|
| **C1** | **P0** | `serpent_trimui_app/lib/services/backend_service.dart:375-376, 386-389, 415-416, 484-503, 641-651, 716-721` — six watchdog / E-STOP-on-disconnect / debounce / local-override blocks all commented "DISABLED FOR TESTING" | Directly violates **SI-2** (comms uncertainty = E-STOP) and **SI-6** (disconnect = E-STOP) on the Flutter hop. The 5 s watchdog `Duration` at `:68` is now vestigial. The bridge still enforces these, but the operator-side is no longer defence-in-depth. |
| **C2** | **P0** | `backend_service.dart:666, 727` — `_socket?.emit('emergency_toggle')` is the only outbound E-STOP primitive | Violates **SI-3** (SET semantics only). `base_pi/core/backend_client.py:93-108` translates `emergency_toggle` as always-ENGAGE; clearing depends on a 2 s suppression window at `backend_client.py:104`. Race, not design. |
| **C3** | **P0** | `serpent_backend_trimui_s.py:1754-1774` — `handle_emergency_toggle` forces `emergency_stop = True` when no `active` field present | There is **no path** in this file that sets `emergency_stop = False` via `emergency_toggle`. Clear only happens through a Y-button 5 s hold in `handle_input_event:1828-1860`. Any non-TrimUI client (dashboard, test harness, future web UI) calling `emergency_toggle` can ENGAGE but cannot ever CLEAR. |
| **C4** | **P1** | `dashboard/config.py:61` — `DISABLE_WATCHDOG_FOR_LOCAL_TESTING` env-var defaults to `'True'` | A safety-impacting flag defaults unsafe. A deploy that forgets to override it leaves the dashboard's watchdog off. Conflicts with **SI-2**. |
| **C5** | **P1** | `serpent_trimui_app/raspberry_pi_receiver/config.py:18-19` (UDP 5001 = video, TCP 5002 = control) vs `common/constants.py:38-40` (5001 control, 5002 video, 5003 telemetry) | If anyone ever runs those forwarder scripts on a Pi in production, the `video_forwarder.py` will blast raw UDP onto the **authenticated control port**. The robot rejects with auth-failure E-STOP (SI-4/SI-6) — but only after exposing the authenticated port to unauthenticated UDP. |

---

## 2. Integration gaps — contract drift across the Flutter ↔ backend ↔ bridge boundary

All three layers string-literal match event names. There is no shared schema. Actual wiring state:

| Event | Emitted by Flutter | Handled by `serpent_backend_trimui_s.py` | Handled by `base_pi/core/backend_client.py` | Status |
|---|---|---|---|---|
| `emergency_toggle` | `backend_service.dart:666, 727` | `:1754` (always-ENGAGE) | `:93` (always-ENGAGE + suppress window) | **Toggle semantics — see C2** |
| `toggle_cv` | `:690` | Commented out `:1710-1714` | Not handled | **Silent drop** |
| `gamepad_command` | `:753` | No handler | Not handled | **Silent drop** |
| `start_camera` | `:608, 734` | `:1694` | `:154` forwards | OK |
| `raw_button_press` | `:758` | `:1744` | `:164` forwards | OK (log-noisy) |
| `input_event` | `:767` | `:1808` + `broadcast=True` re-emit `:2065` | `:160` forwards | **Echo-loop risk** if bridge + backend share a room |
| `r1_button` | `:771` | No handler | `:168` forwards | **Drop in backend** (never reaches bridge because backend doesn't re-emit) |
| `height_update` / `force_update` | `:778, :785` | `:1790, :1799` re-emit | `:146, :150` forwards | OK |
| `clamp_close` / `clamp_open` | `:792, :798` | `:1776, :1783` with TODOs | `:136, :141` forwards | **TODO; no robot-side handler** (grep on `command_executor.py` for "clamp" = 0 hits) |
| `winch_control` | **Never emitted by Flutter** | Emitted by backend's own pygame loop `:2038` | `:198` forwards | **Flutter is not the source** — winch is dead if backend Pi has no local gamepad |
| `chainsaw_command`, `chainsaw_move`, `climb_command`, `brake_command`, `traverse_command` | **Never emitted by Flutter** | Emitted by backend `:1899-2018` | Forwarded `:173-196` | Same pattern — all actuation synthesized by backend pygame, not by Flutter |
| `chainsaw_force` vs `chainsawForce`, `rope_force` vs `ropeForce` | Both accepted `backend_service.dart:421-422` | Producer emits snake_case only (`bridge_coordinator.py:523-524`) | — | **Dead camelCase branch** — tolerated contract drift |
| `estop_clear_progress` | **No listener in Flutter** | Emitted `:1843, :1853-1858` | N/A | Backend broadcasts a 5 s hold progress event; Flutter never subscribes, so UI has no "holding to clear" indicator |
| `trimui_button`, `trimui_input`, `claw_command`, `menu_command`, `camera_switch` | — | Emitted by backend | **No subscribers anywhere** | Dead broadcasts |
| `system_state` | Flutter listens `:408` | Emitted by backend `:1679` on connect only | Bridge doesn't emit | One-shot; `height`/`force` only sync at connect, then drift until next full `telemetry` push |

**Totals:** 5 Flutter→backend events reach no terminal handler. 7 backend→Flutter events have no subscriber. Roughly half the wire contract is either dead or "works by accident".

---

## 3. Dead or confusing code

| # | Sev | Evidence | Why it matters |
|---|---|---|---|
| **D1** | **P1** | `serpent_trimui_app/raspberry_pi_receiver/` and `raspberry_pi_robot/` (entire directories, configs at `receiver/config.py:18-19` and `robot/config.py:13-14`, READMEs 253 LOC each) | Not referenced by any `setup_*.sh`, any `.dart` file, or `serpent_backend_trimui_s.py`. Only hits are self-references and `GITHUB_SETUP.md:228-229`. Describes an obsolete direct-UDP-to-Robot-Pi architecture with **video/control ports inverted vs production**. Live footgun — see C5. |
| **D2** | **P1** | `serpent_backend_trimui_s.py` — 2362 lines, ~938 blank/comment (~40%). Lines 1-474 are a commented-out duplicate of code that still exists live at 480+ | Reading the top half gives a different mental model than the running code. The commented block references `cv_processor`, `camera_manager`, `generate_frames` etc. that still exist below. |
| **D3** | **P2** | `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/halow_bridge.py.old`, referenced by `base_pi/README.md:13, 85` as "Main coordinator" | README is stale. Real entrypoint is `base_pi/core/bridge_coordinator.py`. New contributors read the README and open the wrong file. |
| **D4** | **P2** | Stray files at `pi_halow_bridge/PI-HALOW-BRIDGE/` top level: `chmod`, `echo`, `sudo`, `nul`, `600` (no extensions). Also `serpent_trimui_app/nul` | Artefacts of redirected shell commands (e.g. `chmod 600 ... > chmod`). Noise, but also signals sloppy working-directory hygiene. |
| **D5** | **P2** | `lib/screens/main_screen.dart:780-928` — 15 consecutive `// TODO: Implement <action>` stubs for chainsaw, movement, sticks | Confirms Section 2: Flutter UI is currently a passive display + E-STOP console; real actuation is backend-side. |
| **D6** | **P2** | Overlapping setup scripts: `setup_pi_backend.sh`, `setup_pi_backend.sh.backup`, `manage_service.sh`, `start_backend_simple.sh`, `setup_simple_autostart.sh` | `RASPBERRY_PI_DEPLOYMENT.md:46` points to `setup_pi_backend.sh`; `.backup` unused; unclear which is canonical. |
| **D7** | **P2** | `backend_service.dart:655-667` — `_triggerSafetyEmergencyStop(...)` only callable from the disabled (commented-out) paths | Dead function on a safety-critical class. An auditor reading the class will wrongly infer E-STOP-on-loss is wired. |

---

## 4. Test gaps

| # | Sev | Evidence | Why it matters |
|---|---|---|---|
| **T1** | **P1** | `serpent_trimui_app/test/widget_test.dart:1-30` is the **Flutter starter template** — `tester.tap(find.byIcon(Icons.add))` on `MyApp`, which has no "+" icon | Will error on any `flutter test` as soon as `MyApp` is real. False positive — neither a smoke test nor a placeholder. |
| **T2** | **P1** | `test/` contains only `widget_test.dart` and `portfolio_screenshots_test.dart` | Zero coverage of `BackendService` socket contracts. None of the five safety-critical Flutter behaviours have tests — which matters *more*, not less, given that five of them are currently disabled (C1). |
| **T3** | **P1** | `destructive_ops.yaml:19` lists `robot_pi/actuator_controller.py` as safety-critical. No `test_actuator_controller.py` in `PI-HALOW-BRIDGE/tests/` | SI-1 (boot-latched E-STOP), SI-7 (TOCTOU-safe actuation), motor-speed clamping are only indirectly exercised by `test_estop.py`. |
| **T4** | **P1** | `base_pi/winch_controller.py` is in `destructive_ops.yaml:24`. No dedicated test — only `scripts/winch_sim.py` at integration level | **SI-11** (Modbus register map is THE contract) not verified by unit test. Register map drift between firmware and `winch_controller.py` would go silent. |
| **T5** | **P2** | `tests/test_fault_injection.py:357` — case marked "For now, mark as TODO" | Known fault-coverage gap. |

---

## 5. Configuration hazards

| # | Sev | Evidence | Why it matters |
|---|---|---|---|
| **F1** | **P0** | `raspberry_pi_receiver/config.py:18-19` swaps video/control vs `common/constants.py:38-40` | See C5 / D1. |
| **F2** | **P1** | `dashboard/config.py:5` says "5005 robot, 5006 base"; `:52` selects accordingly. But `base_pi/telemetry_websocket.py:29` hard-codes `port: int = 5005` as default | Base Pi telemetry WS defaults to 5005 (robot dashboard port). If both run with defaults on the Base Pi, they collide. |
| **F3** | **P1** | `scripts/terminal_dashboard.py:34, 135` hard-codes `http://localhost:5006/api/status` | Only works on Base Pi. On Robot Pi (dashboard on 5005), silently returns no data. |
| **F4** | **P2** | `android/app/src/main/AndroidManifest.xml:28` — `android:usesCleartextTraffic="true"` | Load-bearing (backend is plain HTTP on 5000). Justified by current design but hides the absence of transport security on the Flutter↔backend hop — no defence-in-depth at that layer. |
| **F5** | **P2** | `lib/screens/splash_screen.dart:524, 644` — manual-IP hint defaults to `http://10.0.2.2:5000` (Android-emulator loopback) | Production TrimUI is not an emulator; dev-leftover shown to operators. |
| **F6** | **P2** | `base_pi/config.py:35-36` — `BACKEND_URL` defaults to `http://localhost:5000`; `serpent-base-bridge.service:21` also sets localhost | If backend and base bridge are ever split across hosts, both must be overridden. No warning if unreachable for long. |

---

## 6. TODO / FIXME backlog (top items)

| # | Sev | File:line | Extract |
|---|---|---|---|
| 1 | P1 | `serpent_backend_trimui_s.py:1780` | `# TODO: Implement actual clamp control` (in `handle_clamp_close`) |
| 2 | P1 | `serpent_backend_trimui_s.py:1787` | `# TODO: Implement actual clamp control` (in `handle_clamp_open`) |
| 3 | P1 | `lib/screens/main_screen.dart:874-928` | 8× `// TODO: Implement robot up/down/left/right movement` and stick actions |
| 4 | P2 | `lib/screens/main_screen.dart:780-792` | Chainsaw on / left / right — "TODO: Implement" |
| 5 | P2 | `tests/test_fault_injection.py:357` | `# For now, mark as TODO` |
| 6 | P2 | `scripts/stress_network_sim.py:355-356` | `# TODO: implement duplicate`, `# TODO: implement reorder` |
| 7 | P2 | `base_pi/telemetry_storage.py:331` | `# TODO: Implement if needed for analysis/export` |
| 8 | P3 | `serpent_backend_trimui_s.py:1645-1652` | 8× button-mapping entries flagged `'Unmapped (TODO: drive forward)'` etc. |

---

## 7. Agent-stack hygiene

| # | Sev | Evidence | Why it matters |
|---|---|---|---|
| **A1** | **P1** | `destructive_ops.yaml:27` lists `scripts/setup_*.sh`, but production setup scripts live at `PI-HALOW-BRIDGE/setup_base_pi.sh`, `setup_robot_pi.sh`, `setup_psk_on_hub.sh` (matched by the broader `:30` `setup_*.sh` glob) | Both globs eventually catch everything, but the intent→reality gap shows the gate was written with an out-of-date mental model of the tree. |
| **A2** | **P1** | `destructive_ops.yaml:19` protects `robot_pi/actuator_controller.py` but not `robot_pi/sensor_reader.py` | Sensor-reader changes (I²C, IMU) feed telemetry the controller trusts. Should be reviewed similarly. |
| **A3** | **P1** | `CLAUDE.md` claims "State lives in `agent_stack/.runtime/session_state.json`. Read it on entry" — file does not exist; only `.runtime/logs/*.log` are present | Entry-protocol promise the runtime doesn't keep. Any agent following the instruction silently fails its first read. |
| **A4** | **P2** | `dashboard/config.py:61` sets `DISABLE_WATCHDOG_FOR_LOCAL_TESTING` default `'True'`; file is **not** in `destructive_ops.yaml:safety_critical_paths` | A one-line edit could invert the production watchdog default with no gate review. |
| **A5** | **P2** | `destructive_ops.yaml:24` protects `base_pi/winch_controller.py` but not `base_pi/control_forwarder.py` (reconnecting TCP client on the authenticated control path) or `base_pi/telemetry_receiver.py` | Both sit on the authenticated control/telemetry path and can violate SI-4/SI-6 if mis-changed. |

---

## 8. Prioritized action list (suggested order of attack)

The audit is diagnostic; this list just arranges findings by dependency.

### Before any production deploy
1. **C2 + C3** together: rework E-STOP to SET semantics on the Flutter side — emit explicit `emergency_engage` / `emergency_clear` events, remove the translation logic from `backend_client.py`. Add a Flutter-side `emergency_status` listener that reflects authoritative state instead of assuming toggle.
2. **C1**: re-enable the six disabled safety blocks in `backend_service.dart`. If they were disabled because they were flaky, fix the flake; don't leave the primitives off.
3. **C4**: flip `DISABLE_WATCHDOG_FOR_LOCAL_TESTING` default to `'False'`. Move the file under `destructive_ops.yaml` (A4).

### Before any new contributor joins
4. **D1 + C5 + F1**: delete `raspberry_pi_receiver/` and `raspberry_pi_robot/` or move under `archive/` with a REMOVED.md note. They are the single worst footgun on disk.
5. **D2**: strip the top-half commented block from `serpent_backend_trimui_s.py`. Either delete or move to `archive/serpent_backend_pre_<date>.py`.
6. **D3**: delete `halow_bridge.py.old` and update `base_pi/README.md` to point at `core/bridge_coordinator.py`.
7. **A3**: create `agent_stack/.runtime/session_state.json` with the documented schema, or update `CLAUDE.md` to reflect reality.

### Before the next feature cycle
8. **T1 + T2**: rewrite `widget_test.dart`, add real tests for `BackendService` wire contract (at minimum: E-STOP engage/clear round-trip, height/force emit shape, disconnect behaviour).
9. **T3 + T4**: add `test_actuator_controller.py` (SI-1, SI-7, speed clamp) and `test_winch_controller_modbus.py` (SI-11 — register map parity with firmware).
10. **Section 2 integration gaps**: decide which of the 12 ambiguous events are canon, delete the rest, write a single `docs/wire_contract.md` that enumerates the live Flutter↔backend event names with payload shapes. This is the schema the team keeps working around the absence of.
11. **D5 + items 1-4 in §6**: decide whether Flutter should emit winch/chainsaw/climb commands itself (symmetric with the 2 LOC backend emits), or whether the backend-pygame-authoritative model is intentional. Document in the README so future readers stop being confused.

---

*Companion document:* `SYSTEM_ARCHITECTURE.md` — the as-built reference this audit is scoped against.

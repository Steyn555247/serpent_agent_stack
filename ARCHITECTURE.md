# Serpent Architecture — Post-Cleanup Big Picture

> Generated 2026-04-25 after the Tier 1-5 cleanup pass (`audits/2026-04-25-cleanup-final.md`). Single-page orientation for an engineer who just cloned the four repos and needs to see how they fit together.
>
> Companion docs (in this same `agent_stack/` directory): `SYSTEM_ARCHITECTURE.md` (software event flow + timing budget), `PHYSICAL_ARCHITECTURE.md` (hardware compute layers), `gates/safety_invariants.md` (the twelve SI rules), `ESTOP_REBUILD_PLAN.md` (the v2 design that landed 2026-04-24), `IMPLEMENTATION_WORKFLOW.md` (R-milestone delivery pattern), `ESTOP_BENCH_TEST.md` (hardware bench validation), `CLAUDE.md` + `AGENTS.md` (agent-stack entry points).

---

## 1. What this is

Serpent is a tethered, two-chainsaw, rope-climbing tree-pruning robot prototype. The system spans four separately-versioned subprojects working as one. Compute is distributed across the operator (TrimUI handheld + Base Pi) and the robot (Robot Pi + two ESP32 winch stations). The four repos are independently deployable but share a single wire contract documented in `SYSTEM_ARCHITECTURE.md §4`. End-to-end operator-input → motor-PWM latency is ~20-50 ms; safety is enforced by twelve invariants (SI-1…SI-12) all currently green.

---

## 2. The four subprojects

| Name | GitHub | Deploys to | Role |
|---|---|---|---|
| `pi_halow_bridge/PI-HALOW-BRIDGE` | github.com/Steyn555247/PI-HALOW-BRIDGE | Base Pi + Robot Pi | Bidirectional HMAC-authenticated bridge over ALFA HaLow 802.11ah (1 km LOS); also contains the ESP32 winch firmware. |
| `serpent_trimui_app` | github.com/Steyn555247/serpent-robotics-trimui-app | TrimUI Smart Pro S handheld (Android) | Flutter operator UI — joystick capture, video display, telemetry overlay. |
| `pi_backend` | github.com/Steyn555247/pi_backend | Base Pi only | Flask + SocketIO event broker between Flutter UI and Base Pi `BackendClient`. |
| `serpent_agent_stack` (this `agent_stack/`) | github.com/Steyn555247/serpent_agent_stack | Dev workstation only | Orchestrator, safety gates, validation tools, audit history. |

Each subproject has its own `.git`. The repo top level is **not** a git repo — the four trees coexist in a parent directory at dev time. Treat each as an ownership boundary.

---

## 3. Runtime topology

```
TrimUI (Flutter) <==Socket.IO :5000==> pi_backend (Flask+SocketIO on Base Pi)
                                                    |
                                                    v Socket.IO loopback :5000
                                       base_pi/core/backend_client.py
                                       base_pi/core/bridge_coordinator.py
                                                    |
                                       ==HMAC-SHA256 frames + monotonic seq==
                                       TCP 5001 control   (Base -> Robot)
                                       TCP 5002 video     (Robot -> Base, MJPEG)
                                       TCP 5003 telemetry (Robot -> Base, 10 Hz)
                                                    |
                                       ====ALFA HaLow 802.11ah link (1 km LOS)====
                                                    |
                                                    v
                                       robot_pi/control/control_server.py
                                       robot_pi/core/{bridge_coordinator,
                                                      command_executor,
                                                      watchdog_monitor}.py
                                       robot_pi/actuators/actuator_controller.py
                                       robot_pi/sensors/sensor_reader.py
                                                    |
                                       RS-485 Modbus RTU @ 250 kbps
                                                    |
                                       firmware/winch_station/winch_station.ino x 2
                                       (UNIT_ID=1 LEFT, UNIT_ID=2 RIGHT)
```

Link-by-link:

- **TrimUI ↔ pi_backend (TCP 5000, plain HTTP + Socket.IO).** Operator LAN, untrusted at the session layer but inside the trust perimeter by design (see `SYSTEM_ARCHITECTURE.md §5.3`). 18 Socket.IO event handlers in `pi_backend/routes/socket.py`.
- **pi_backend ↔ Base Pi BackendClient (loopback :5000).** The bridge is a Socket.IO *client* of the broker, on the same host. Sub-millisecond.
- **Base Pi ↔ Robot Pi (TCP 5001/5002/5003 over HaLow).** Three sockets, three threads. Control + telemetry are HMAC-SHA256 authenticated with strictly-monotonic 8-byte sequence numbers (SI-4). Video is unauthenticated (content only, never used for actuation per SI-5). HaLow link is ~10 ms typical, 15 Mbps peak, 1 km LOS.
- **Robot Pi ↔ ESP32 winches (RS-485 Modbus RTU, 250 kbps).** Robot Pi is the Modbus master in the canonical two-Pi topology. Holding registers HR0/HR1/HR2 = speed/enable/tension setpoint; input registers IR0-IR8 = encoders + ADC + status flags. The wire is at the Base Pi end of the rope (because that is where the winches are physically anchored — see `PHYSICAL_ARCHITECTURE.md` for the wired-RS-485 layout reasoning).

**Watchdog.** Two independent Pi-level watchdogs run at 10 Hz with `WATCHDOG_TIMEOUT_S=5.0` and `STARTUP_GRACE_S=30.0` (SI-2): `robot_pi/core/watchdog_monitor.py::WatchdogMonitor` and `base_pi/core/base_watchdog.py::BaseWatchdog`. If either link goes silent for >5 s, that authority engages E-STOP and cross-channel-echoes the engagement to the other authority. Below the Pi watchdogs, every ESP32 has a 500 ms firmware command watchdog (SI-8) and every Motoron has a ~1.5 s I²C command watchdog — these are hardware-effective and keep working even if the Pis crash.

---

## 4. Deployment matrix

| Component | Base Pi | Robot Pi | TrimUI | Dev workstation | Notes |
|---|---|---|---|---|---|
| `pi_halow_bridge` repo | clone | clone | — | clone | Monorepo cloned on **both** Pis. Each Pi enables only its own systemd unit (`serpent-base-bridge.service` on Base, `serpent-robot-bridge.service` on Robot). |
| `pi_backend` repo | clone | — | — | clone | Runs `setup_pi_backend.sh` + `setup_autostart.sh` on Base Pi. User-systemd. |
| `serpent_trimui_app` repo | — | — | APK install | clone | `build_apk.bat` / `build_apk.ps1` on dev workstation; ADB push to TrimUI. Auto-launches on boot via `BootReceiver.kt` + LEANBACK HOME intent. |
| `serpent_agent_stack` (this) | — | — | — | clone | Orchestrator, validation tools, audit history. Never deployed to a Pi. |
| ESP32 winch firmware | — | — | — | flash via PlatformIO | `firmware/winch_station/` inside the bridge repo. Two physical boards, same binary, `-D UNIT_ID=1` or `-D UNIT_ID=2` build flag. |
| PSK material (`/etc/serpent/psk`) | generated | generated | — | — | `scripts/generate_psk.py --hex-only` invoked by `pi_install.sh`; root-owned 0600 systemd drop-in. Never in VCS (SI-12). |

---

## 5. Communication contract

### 5.1 Socket.IO events (TrimUI ↔ pi_backend ↔ Base Pi BackendClient)

Full schema (event name + payload shape) lives in `SYSTEM_ARCHITECTURE.md §4`. The 18 handlers registered in `pi_backend/routes/socket.py`:

`connect`, `disconnect`, `start_camera`, `connect_gamepad`, `latency_ping`, `winch_calibration`, `raw_button_press`, `clamp_close`, `clamp_open`, `gamepad_command`, `r1_button`, `emergency_stop`, `toggle_cv`, `height_update`, `force_update`, `input_event`, `telemetry`, `controller_telemetry`.

Wire format is unauthenticated JSON over Socket.IO. Re-signing happens at the Base Pi `BackendClient`, not on the TrimUI.

### 5.2 HMAC frames (Base Pi ↔ Robot Pi)

`SecureFramer` in `pi_halow_bridge/PI-HALOW-BRIDGE/common/framing.py`. Frame layout: `length(2) + seq(8) + hmac(32) + payload`. SHA-256 MAC over `seq || payload` with the 32-byte PSK. Replay rejected via strictly-monotonic seq. `MAX_FRAME_SIZE = 16 KiB` (SI-9). SI-4 enforced; tests in `tests/test_framing.py` and `tests/test_fault_injection.py`.

### 5.3 Modbus RTU (Robot Pi ↔ ESP32 winches)

Register map documented in **both** `firmware/winch_station/winch_station.ino` and `base_pi/winch/winch_controller.py` — they must change in lockstep (SI-11, locked in by `tests/test_winch_controller_modbus.py`):

| Reg | Dir | Meaning |
|---|---|---|
| HR0 | R/W int16 | Winch speed -1000..+1000 |
| HR1 | R/W uint16 | Enable (0/1) |
| HR2 | R/W uint16 | Tension setpoint override (0 = keep EEPROM) |
| IR0/1, IR2/3, IR4/5 | R int32 BE | Encoder counts (winch + 2 tension motors) |
| IR6, IR7 | R uint16 | Tension ADC (0-4095) |
| IR8 | R uint16 | Status flags: SLACK / OVERTENSION / STALL / WATCHDOG / TENSION_ARMED |

500 ms firmware command watchdog (SI-8) zeros motors if HR0 stops being written.

### 5.4 PSK distribution

Never in VCS (SI-12). `scripts/generate_psk.py --hex-only` produces a 64-char hex string; `pi_install.sh` writes it to `/etc/serpent/psk` (root:root, 0600) and creates a systemd drop-in that exports `SERPENT_PSK_HEX` to the bridge service. Same PSK on both Pis. Rotation = re-run install on both Pis with the same value.

---

## 6. Safety architecture

Twelve invariants (`agent_stack/gates/safety_invariants.md`), all green as of the 2026-04-24 E-STOP rebuild:

| Category | Invariants | What it guarantees |
|---|---|---|
| Persistence | SI-1 | Robot fails safe by default; E-STOP state survives reboots via `/var/lib/serpent/{robot,winch}_estop_state.json`. |
| Watchdog | SI-2, SI-6 | Two 5 s Pi watchdogs + distributed fast-engage from `control_server.py` exception branches. |
| Framing | SI-4, SI-9 | HMAC-SHA256 + monotonic seq on every control/telemetry frame; per-message size capped before allocation. |
| Gating | SI-3, SI-7 | E-STOP uses SET semantics with three-gate clear (confirm string + control_age ≤ 1.5 s + control_connected); single `_lock` covers flag-check + hardware-write atomically. |
| Priority | SI-5 | Control runs on its own socket/thread; video never blocks control. |
| Hardware-import | SI-10 | `motoron` / `RPi.GPIO` / `adafruit_*` only import when `SIM_MODE != "true"`. |
| Firmware | SI-8, SI-11 | ≤500 ms ESP32 command watchdog; Modbus register map is the contract between firmware and Python. |
| PSK | SI-12 | PSK material never in VCS; loaded from environment / `/etc/serpent/psk`. |

**Two E-STOP authorities** (per the 2026-04-24 R0-R10 rebuild): Robot Pi `ActuatorController` (covers Motoron-driven motors + servos) and Base Pi `WinchController` (covers RS-485 ESP32 winches). They cross-channel-echo state via the existing telemetry path, share a wire format (`{engage, reason, source, confirm?, ts_ms}`), and persist independently. See `ESTOP_REBUILD_PLAN.md` for design and `ESTOP_BENCH_TEST.md` for the hardware validation runbook.

---

## 7. Development workflow (agent_stack governance)

The agent stack drives changes through five Claude Code slash commands plus specialist sub-agents:

| Command | What it does |
|---|---|
| `/plan <task>` | Orchestrator decomposes the task into specialist work items; writes a plan into `agent_stack/.runtime/session_state.json`. |
| `/implement` | Specialists (`firmware-embedded`, `platform-toolchain`, `test-verification`, `debug-triage`, `docs-release`, `repo-architect`) execute their assigned items. |
| `/safety-check` | `safety-gate` agent reviews any diff touching `agent_stack/gates/destructive_ops.yaml :: safety_critical_paths`. Required before commit on safety-critical paths. |
| `/validate` | `python agent_stack/tools/validate.py all` runs five targets: python tests (PI-HALOW-BRIDGE `unittest`), flutter analyze + test, firmware smoke, SIM_MODE bridge run, pi_backend probes. |
| `/smoke-test` | `python agent_stack/tools/smoke_test.py` self-checks the agent stack itself. |

Workflow templates live in `workflows/` (`feature.md`, `bugfix.md`, `firmware_change.md`, `refactor.md`, `release.md`). State hand-off between agents is one file: `agent_stack/.runtime/session_state.json` — read on entry, append decisions, never silently overwrite.

---

## 8. Where to find what

| I want to… | Files to touch (in order) |
|---|---|
| Add a Socket.IO event | `pi_backend/routes/socket.py` + `base_pi/core/backend_client.py` + `serpent_trimui_app/lib/services/backend_service.dart` |
| Add a sensor | `robot_pi/sensors/sensor_reader.py` + `robot_pi/telemetry_sender.py` |
| Change the wire format | `SYSTEM_ARCHITECTURE.md §4` first (canonical contract owner), then 3-side updates |
| Add a safety invariant | `agent_stack/gates/safety_invariants.md` + `safety-gate` review |
| Add a workflow | `agent_stack/workflows/<name>.md` matching the existing shape |
| Flash firmware | `/firmware-change` skill (never auto-flashes; requires explicit human confirm per `destructive_ops.yaml`) |
| Run tests | `python agent_stack/tools/validate.py all` |
| I broke something | `/triage` skill (routes to `debug-triage` agent) |
| Find any module | `agent_stack/repo_map.md` (regenerate with `tools/build_repo_map.py`) |
| Understand a hardware question | `PHYSICAL_ARCHITECTURE.md` |
| Understand event/timing flow | `SYSTEM_ARCHITECTURE.md` |
| Validate the agent stack itself | `python agent_stack/tools/smoke_test.py` |

---

## 9. Cleanup history

The 2026-04-25 cleanup pass (`audits/2026-04-25-cleanup-final.md`) ran in five tiers and resolved most of the W#/R#/N# items surfaced by the prior `2026-04-23-audit-findings.md`. Tier 1 fixed the test-isolation blocker (W8). Tier 2 repointed broken stress scripts (W1-W4). Tier 3 aligned doc/comment drift with the 2026-04-24 E-STOP rebuild (W6, W13, W15, W16). Tier 4 consolidated setup/install/PSK scripts and extracted `pi_backend/` from the Flutter source tree (R1-R4, R10, R16). Tier 5 covered the long tail — top-level renames (`pi_halow_bridge/`, `serpent_trimui_app/`, removing the " - Copy" suffix), bench-script reorganisation, Flutter dep prune, build-artifact cleanup, doc consolidation, and dashboard static stub removal. Seven Tier 6+ items (W5 dashboard E-STOP, R5 service rename, R11 constants drift, R32 log rotation, N4/N5 layout normalisation, N12 control_buttons placeholder, plus three safety-gated 5.4 sub-batches) remain pending; see §2 of the cleanup-final audit.

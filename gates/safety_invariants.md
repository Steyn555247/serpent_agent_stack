# Safety invariants — non-negotiable

These are the rules that no agent, no commit, and no human override may weaken without an explicit safety-engineering review (recorded in `SAFETY_HARDENING.md`).

Source: `pi_halow_bridge/PI-HALOW-BRIDGE/SAFETY_HARDENING.md` and `common/constants.py`.

> **2026-04-24 status:** the E-STOP rebuild (R0–R10) landed per `ESTOP_REBUILD_PLAN.md` v2.1. SI-1, SI-2, SI-3, SI-6, SI-7 are **enforced again**. The rebuild is structurally different from the v1 surface: two authorities (Robot Pi + Base Pi), bidirectional cross-channel echo, two-phase atomic clear, persistent state across reboots (Q2b), and distributed fast-engage from the control-server exception branches.

## SI-1 — Robot fails safe by default ✅

E-STOP state is persisted to `/var/lib/serpent/{robot,winch}_estop_state.json` on every transition and restored at process startup. A Pi that was engaged when it went down comes back engaged with the same reason. First-ever boot defaults to cleared, with a 2-second `STARTUP_DELAY_S` grace on the Robot Pi that refuses non-zero motor commands during the boot window. Soft-latch (Q2=B) + persistent state (Q2b=B); hard boot-engage is **not** the v2 design — see `ESTOP_REBUILD_PLAN.md` §Q2.

- Files: `robot_pi/actuators/actuator_controller.py::engage_estop`/`clear_estop`/`_restore_estop_state_from_disk`, `base_pi/winch/winch_controller.py::engage_winch_estop`/`clear_winch_estop`/`_restore_winch_estop_state_from_disk`
- Tests: `tests/test_estop.py::TestSoftLatchAndPersistence`, `tests/test_base_pi_estop.py::TestSoftLatchAndPersistence`, `tests/test_estop_integration.py::TestReconnectStatePersistence`

## SI-2 — Communication uncertainty = E-STOP ✅

Two independent Pi-level watchdogs (one per authority), both on a 10 Hz tick, with `WATCHDOG_TIMEOUT_S=5.0` silent-link threshold and `STARTUP_GRACE_S=30.0` boot-time grace. Engages are link-fresh, not operator-fresh — heartbeats keep the Robot watchdog refreshed independently of operator input.

- Files: `robot_pi/core/watchdog_monitor.py::WatchdogMonitor`, `base_pi/core/base_watchdog.py::BaseWatchdog`
- Tests: `tests/test_robot_watchdog.py`, `tests/test_base_watchdog.py`
- Distributed fast-engage (faster than the 5 s timer) lives in `robot_pi/control/control_server.py::receive_command` exception branches, covered by `tests/test_control_server_fast_engage.py`.

## SI-3 — E-STOP uses SET semantics, never toggle ✅

Wire format defined in `ESTOP_REBUILD_PLAN.md` §Q1: `{"engage": bool, "reason": str, "source": str, "confirm"?: str, "ts_ms": int}`. Engage is permissive (always succeeds, fail-safe direction). Clear requires THREE gates ALL satisfied: `confirm == ESTOP_CLEAR_CONFIRM` ("CLEAR_ESTOP"), `control_age_s <= ESTOP_CLEAR_MAX_AGE_S` (1.5 s), and `control_connected == True`. Legacy `emergency_toggle` is rejected at every layer.

- Files: `common/constants.py` (`ESTOP_CLEAR_CONFIRM`, `ESTOP_CLEAR_MAX_AGE_S`, reason codes), `robot_pi/actuators/actuator_controller.py::clear_estop`, `base_pi/winch/winch_controller.py::clear_winch_estop`, `robot_pi/core/command_executor.py::_handle_emergency_stop`, `base_pi/core/bridge_coordinator.py::_handle_emergency_stop`
- Tests: `tests/test_estop.py::TestClearGate`, `tests/test_base_pi_estop.py::TestClearGate`, `tests/test_command_executor_estop.py`, `tests/test_bridge_estop.py`

## SI-4 — All control commands authenticated ✅

Every control frame is HMAC-SHA256 authenticated with a 32-byte PSK and a strictly monotonic 8-byte sequence number. Replay is rejected.

- File: `common/framing.py::SecureFramer`
- Header: `length(2) + seq(8) + hmac(32) = 42 bytes`
- Tests: `tests/test_framing.py`

## SI-5 — Control priority over video ✅

Video traffic must never block, starve, or delay control or telemetry. Control runs on its own socket/thread. Video uses unauthenticated framing (zero MAC) — never use it for actuation.

## SI-6 — Crash or disconnect = E-STOP ✅

Distributed fast-engage from `robot_pi/control/control_server.py::receive_command`: each exception branch (AuthenticationError, ReplayError, FramingError, ConnectionError, UnicodeDecodeError, generic Exception) calls `on_estop_trigger(reason)` BEFORE closing the client and recording the failure on the circuit breaker. Reasons map to `common.constants.ESTOP_REASON_*` (auth_failure, replay_attack, decode_error, buffer_overflow, control_disconnect, internal_error). The silent-link watchdog (SI-2) catches anything fast-engage missed.

- Files: `robot_pi/control/control_server.py::_fire_estop`
- Tests: `tests/test_control_server_fast_engage.py` (covers every branch + no-callback safety + callback-exception swallowing)

## SI-7 — TOCTOU-safe actuation ✅

Both authorities use a single `_lock` that covers BOTH the E-STOP-flag check AND the hardware write. `set_motor_speed` / `set_servo_position` / `set_servo_duty_raw` (Robot side) and `_write_speed` (Base side) all check `_estop_engaged` / `_winch_estop_engaged` and perform the actuation under the same lock — no race window between check and act. A separate `_persist_lock` serializes the disk-write path so persistence cannot block actuation.

- Files: `robot_pi/actuators/actuator_controller.py::set_motor_speed`/`set_servo_position`/`set_servo_duty_raw`, `base_pi/winch/winch_controller.py::_write_speed`/`_write_speed_unlocked`
- Tests: `tests/test_estop.py::TestActuationGated`, `tests/test_base_pi_estop.py::TestActuationGated`

## SI-8 — Firmware command watchdog ✅

Every embedded device that drives an actuator must implement a command watchdog ≤ 500 ms. Stale commands → motor speed forced to 0 and `STATUS_WATCHDOG` flag set. See `firmware/winch_station/winch_station.ino` for the reference implementation.

## SI-9 — Buffer bounds enforced ✅

`MAX_CONTROL_BUFFER = 65 KiB`, `MAX_VIDEO_BUFFER = 256 KiB`, `MAX_FRAME_SIZE = 16 KiB` are upper bounds. Code that allocates per-message buffers must reject anything larger before allocating.

## SI-10 — Hardware imports are conditional on SIM_MODE ✅

`motoron`, `RPi.GPIO`, `adafruit_*`, `busio`, `board`, `serial` etc. must only import when `SIM_MODE != "true"`. Tests run in `SIM_MODE=true` and must not require hardware.

## SI-11 — Firmware Modbus register map is the contract ✅

The Modbus register map documented at the top of each `firmware/*/*.ino` must match the corresponding Python controller (e.g. `base_pi/winch/winch_controller.py`). Changes to either side require simultaneous changes to both. Locked in by `tests/test_winch_controller_modbus.py`.

## SI-12 — PSK material never enters version control ✅

`SERPENT_PSK_HEX` is loaded from environment. PSK files (e.g. `*.psk*`) are gitignored. No PSK literal may appear in tracked code (test PSKs are explicitly marked test-only and may appear in test files).

---

If a proposed change would weaken any of the ✅ invariants, **stop**. Surface to the human with a clear written argument for why the invariant must be modified, what the new invariant would be, and what compensating control replaces the old one.

# Serpent System Architecture — End-to-End

> Generated 2026-04-23 from a full agent-driven walk of the repo. Authoritative reference for how the Flutter operator UI, the serpent_backend, the Base Pi ↔ Robot Pi HaLow bridge, and the ESP32 winch stations fit together.
>
> **2026-04-24 update — E-STOP rebuild complete.** The §5 safety section's references to "PENDING REBUILD" are superseded by `agent_stack/gates/safety_invariants.md` (now showing all twelve invariants ✅) and `ESTOP_REBUILD_PLAN.md` v2.1. The two-authority design (Robot Pi `ActuatorController` + Base Pi `WinchController`), bidirectional cross-channel echo, two-phase atomic clear, persistent state across reboots, and distributed fast-engage are all live. The wire format is now the SET-semantics `emergency_stop {engage, reason, source, confirm?, ts_ms}` payload — there is no `emergency_toggle` event in the protocol.

---

## 0. TL;DR

| | |
|---|---|
| **End use** | A human operator on a TrimUI Smart Pro S handheld drives a tethered rope-climbing robot (two winches, chainsaws, clamps, cameras). |
| **Operator sees** | Live MJPEG video + telemetry (height, tension, pitch, RTT, voltage, E-STOP state). |
| **Operator does** | Joystick/button input on the TrimUI → winch speed, clamp open/close, chainsaw on/off, camera switch, E-STOP. |
| **End-to-end latency** | **~20–50 ms** operator input → motor PWM (dominated by the HaLow radio link, not software). |
| **Watchdog safety budget** | 5.0 s. If any link in the chain stops publishing, the Robot Pi engages E-STOP and halts every motor. |
| **Boot state** | Soft-latch (Q2=B) + persistent state (Q2b=B). First boot defaults to cleared with a 2 s `STARTUP_DELAY_S` non-zero-command grace; a Pi that was engaged when it went down comes back engaged with the same reason restored from `/var/lib/serpent/{robot,winch}_estop_state.json`. |
| **Physical effect** | Two RS-485 Modbus ESP32 winch stations each spool rope in/out at ≤ 1000 PWM counts, holding a tension setpoint with a PI loop at ~100 Hz. |

---

## 1. Topology

```
┌─────────────────────────┐
│ OPERATOR                │   TrimUI Smart Pro S (Android, landscape)
│ Flutter app             │   lib/services/backend_service.dart
└────────────┬────────────┘
             │ Socket.IO + HTTP + MJPEG      (TCP 5000)
             │ Events: raw_button_press, input_event, emergency_stop,
             │         height_update, force_update, clamp_open/close,
             │         start_camera, latency_ping …
             ▼
┌─────────────────────────┐
│ serpent_backend         │   Flask + Flask-SocketIO (Python)
│ (Hub Pi or Base Pi)     │   pi_backend/server.py
└────────────┬────────────┘
             │ Socket.IO intra-host loopback (TCP 5000)
             ▼
┌─────────────────────────┐
│ BASE PI                 │   Raspberry Pi 4/5 (operator side)
│ BackendClient           │   base_pi/core/backend_client.py
│   → BridgeCoordinator   │   base_pi/core/bridge_coordinator.py
│     → ControlForwarder  │   base_pi/control_forwarder.py
│ TelemetryReceiver       │   base_pi/telemetry_receiver.py
│ VideoReceiver           │   base_pi/video_receiver.py
│ Dashboard (Flask)       │   dashboard/  :5006
└────────────┬────────────┘
             │ HMAC-SHA256 + monotonic seq frames
             │    TCP 5001  control   (Base → Robot)
             │    TCP 5002  video     (Robot → Base, MJPEG)
             │    TCP 5003  telemetry (Robot → Base, 10 Hz)
             │   ══════════ ALFA HaLow 802.11ah link (1 km LOS) ══════════
             ▼
┌─────────────────────────┐
│ ROBOT PI                │   Raspberry Pi 4/5 (on robot)
│ ControlServer           │   robot_pi/control/control_server.py
│   → CommandExecutor     │   robot_pi/core/command_executor.py
│     → ActuatorController│   robot_pi/actuator_controller.py
│ WatchdogMonitor         │   robot_pi/core/watchdog_monitor.py  (5 s)
│ SensorReader (I²C)      │   BNO085 IMU, BMP581 baro, INA238 current
│ TelemetrySender         │   robot_pi/telemetry_sender.py
│ VideoCapture (3× USB)   │   robot_pi/video_capture.py
│ Motoron boards (I²C)    │   0x10–0x13, up to 8 motors
│ PCA9685 (I²C)           │   16 servos
└────────────┬────────────┘
             │ Modbus RTU, 250 000 baud
             │   /dev/ttyUSB0 → RS-485 transceiver
             ▼
 ┌──────────────────┐   ┌──────────────────┐
 │ ESP32 winch #1   │   │ ESP32 winch #2   │   firmware/winch_station/
 │ UNIT_ID = 1 LEFT │   │ UNIT_ID = 2 RIGHT│   winch_station.ino
 │ ≤500 ms watchdog │   │ ≤500 ms watchdog │
 └──────┬───────────┘   └──────┬───────────┘
        │ PWM + DIR                 │
        ▼                           ▼
 winch motor, 2× tension motors, quadrature encoders, tension-strain ADC
```

Video path on the operator side has a second hop: the Base Pi re-serves the MJPEG frames at **HTTP :5004** (for dashboard/browser clients) and also publishes them back into the serpent_backend so the Flutter app can pull `/video_feed/<id>` over port 5000.

---

## 2. What the operator does, what the robot does

### 2.1 Starting a session

| Step | Who | What happens | Time |
|---|---|---|---|
| 1 | Operator | Powers on TrimUI, app auto-launches via `BootReceiver.kt` | ~10 s |
| 2 | Flutter | `SplashScreen` probes LAN: mDNS `_serpent._tcp` (skipped on Windows) → subnet-scan fallback `http://<subnet>.*:5000/api/status` | 3–45 s |
| 3 | Flutter | On hit, connects Socket.IO to `http://<ip>:5000`, navigates to `MainScreen` | < 1 s |
| 4 | Base Pi | `BackendClient` is already connected (as a Socket.IO *client*) to the same serpent_backend since boot | — |
| 5 | Robot Pi | Listens on TCP :5001/5002/5003, E-STOP latched ON, watchdog armed with 30 s startup grace | — |
| 6 | Operator | Presses E-STOP-clear sequence; Base Pi sends `{type: "clear_estop", confirm: "CLEAR_ESTOP"}` over the HMAC channel | — |
| 7 | Robot Pi | Validates: control_age < 1.5 s AND confirm string exact AND TCP connected → E-STOP cleared | < 50 ms |

### 2.2 Driving the winches (golden path)

Joystick axis on TrimUI → rope spools in/out on the robot.

| Stage | File:symbol | What it emits | Wire | Next hop |
|---|---|---|---|---|
| 1. Capture | `android/…/MainActivity.kt:onGenericMotionEvent` → EventChannel `com.serpentrobotics.trimui/gamepad_events` | `{type: "motion", axes: {AXIS_X, AXIS_Y, AXIS_Z, AXIS_RZ}}` | Flutter EventChannel | `NativeGamepadService` |
| 2. Debounce / deadzone | `lib/screens/main_screen.dart:93-100` | Analog stream, 50 ms min interval, deadzone 0.1 | In-process | `BackendService.sendInputEvent` |
| 3. Socket.IO emit | `lib/services/backend_service.dart:767` | `input_event = {type, index, value, timestamp}` | TCP 5000 WebSocket | `serpent_backend` |
| 4. Backend fan-out | `server.py` handler | Re-emits to all Socket.IO clients incl. Base Pi | TCP 5000 loopback | `BackendClient` |
| 5. Base Pi ingest | `base_pi/core/backend_client.py:93-207` handler dispatch | Translates to bridge-native command dict | In-process | `BridgeCoordinator._on_backend_event` |
| 6. Frame + HMAC | `common/framing.py:SecureFramer.create_frame` | `[2 B length][8 B seq][32 B HMAC-SHA256][JSON payload]` | In-process | `ControlForwarder` |
| 7. Send | `base_pi/control_forwarder.py:send_command` | `socket.sendall(frame)`, TCP_NODELAY, 3 s timeout | **TCP :5001 over HaLow** | `ControlServer` |
| 8. Auth + replay | `common/framing.py:read_frame_from_socket` | HMAC verified via `hmac.compare_digest`; seq strictly > last_recv_seq else `ReplayError` | In-process | `CommandExecutor.execute` |
| 9. Route | `robot_pi/core/command_executor.py:_handle_input_event` | Axis index → motor index + scaled speed (`int(value * 800)`) | In-process | `ActuatorController.set_motor_speed` |
| 10. Atomic actuate | `robot_pi/actuator_controller.py:set_motor_speed` | Acquires `_estop_lock`, aborts if E-STOP, else I²C write | I²C bus 1 | Motoron board `0x10`–`0x13` |
| 11. Motor PWM | Motoron firmware | Drives motor driver IC with PWM + direction | — | Physical motor |

For the **RS-485 winch channels** the Robot Pi (for some configurations, the Base Pi — see §6.1) additionally writes holding registers HR0 (speed) and HR1 (enable) over Modbus RTU to the ESP32 at UNIT_ID 1 or 2, which in turn runs its local 100 Hz PI tension loop and refreshes motor PWM every pass.

### 2.3 Telemetry and video flowing back

| Stream | Rate | From | To | Protocol | Displayed as |
|---|---|---|---|---|---|
| Telemetry | 10 Hz | `robot_pi/telemetry_sender.py` | `base_pi/telemetry_receiver.py` → backend → Flutter | HMAC-framed TCP :5003 → Socket.IO `telemetry` | Height %, pitch, temp, RTT, voltage, force, IMU, barometer |
| Video (control) | 10 FPS × 3 cams | `robot_pi/video_capture.py` | `base_pi/video_receiver.py` → HTTP :5004 + backend | Framed TCP :5002 | `video_feed.dart` MJPEG widget |
| Status/E-STOP | event-driven | Robot Pi watchdog + actuator controller | Telemetry stream + dashboard | Socket.IO `emergency_status` | Red overlay + banner |
| Latency ping | 1 Hz | Flutter `_sendLatencyPing` | Backend echoes `latency_pong` | Socket.IO | Colored RTT pill (green <100 ms, orange <200, red ≥200) |

### 2.4 What it causes in the real world

* **Rope spools in/out.** Each winch ESP32 holds a configurable tension setpoint (stored in EEPROM, default 512 of 4095 ADC counts). The operator's axis command adds/subtracts a trim term via `tensionLoopStep()` (`firmware/winch_station/winch_station.ino:167-186`). Over-tension (>3800 ADC) or slack (<setpoint-200) sets status flags reported back in IR8.
* **Robot climbs / descends.** Relative rope speed between the two winches controls pitch and forward motion along a rope line.
* **Chainsaw activates** via `ChainsawRamp` (`robot_pi/core/command_executor.py:33-141`) — soft-start 0→full in 1.0 s, ramp-down in 1.5 s, 10 Hz keep-alive.
* **Clamp opens/closes** via PCA9685 servos (I²C 0x40 by default).
* **Any link disconnects for >5 s → everything stops.** Watchdog-fired E-STOP halts all Motoron channels; the ESP32s' own 500 ms command watchdogs halt their motors independently even if the Robot Pi itself is the one that died.

---

## 3. Subsystem deep-dives

### 3.1 Flutter TrimUI app (`serpent_trimui_app/`)

```
lib/
├── main.dart                    # landscape lock, wakelock, keyboard+gamepad init, theme, SerpentApp
├── screens/
│   ├── splash_screen.dart       # mDNS + subnet discovery + manual IP + demo mode
│   ├── main_screen.dart (2840 lines) — live video, joystick capture, nested menus
│   └── sensor_dashboard_screen.dart
├── services/
│   ├── backend_service.dart (828 lines)   ← Socket.IO client + all network I/O
│   ├── gamepad_service.dart (790 lines)   ← `gamepads` package (Android-only)
│   ├── key_event_service.dart             ← Keyboard → ButtonIndex 0–23
│   └── native_gamepad_service.dart        ← EventChannel to MainActivity (Android joystick axes)
├── widgets/
│   ├── video_feed.dart                    # MJPEG decoder over HTTP
│   ├── telemetry_panel.dart
│   ├── camera_selector.dart
│   ├── control_buttons.dart
│   └── controller_calibration.dart
├── constants/app_colors.dart              # orange/teal palette
└── android/app/src/main/…                 # MainActivity.kt, BootReceiver.kt, AndroidManifest
```

* **Three parallel input streams** feed `BackendService`: physical buttons arrive as Android KeyEvents (mapped via `KeyEventService._keyToButtonMap`), USB gamepad events via the `gamepads` package, analog axes via a dedicated Android EventChannel in `NativeGamepadService` (because the `gamepads` package misses analog axes on this device).
* **Debounce tiering** in `main_screen.dart:60-64`: 100 ms navigation, 200 ms actions, 150 ms shoulders. Analog axes rate-limited to 20 Hz with 0.1 deadzone.
* **E-STOP double-check UX:** 5-second hold to *deactivate* (no accidental clear). Activation is a single tap.
* **Zero HMAC on this side.** Trust is LAN-local; the Base Pi re-signs before the HaLow hop. See §5.3.
* **Cleartext HTTP allowed** (`AndroidManifest.xml` `usesCleartextTraffic="true"`) because the backend runs plain HTTP on port 5000.
* **Auto-launch** on boot via `BootReceiver.kt` intent filter, and the app is registered as an Android HOME/LEANBACK launcher so the TrimUI boots straight into it.

### 3.2 serpent_backend (`pi_backend/server.py`)

A ~1900-line Flask + Flask-SocketIO app that runs on a Pi (either the Base Pi itself, or a dedicated "hub" Pi — see `pi_backend/setup_pi_backend.sh` for backend install and `pi_backend/enable_ap_mode_on_boot.sh` to put a hub Pi into AP mode at boot). It's the *rendezvous point*: the Flutter app is a Socket.IO **client** of it, and the Base Pi bridge is *also* a Socket.IO client of it (`base_pi/core/backend_client.py:53` `socketio.Client`).

Responsibilities:
* Terminates the Flutter Socket.IO session.
* Translates legacy `emergency_toggle` (toggle) → SI-3-compliant engage/clear pair before forwarding.
* Serves MJPEG HTTP endpoints `/video_feed/<id>` and `/video_feed_thumb/<id>` for the Flutter `VideoFeed` widget.
* Exposes `/api/status` and `/api/cameras` for the splash-screen discovery probe.
* Fans out telemetry received from the Base Pi to all connected Flutter clients.

### 3.3 Base Pi bridge (`base_pi/`)

* `bridge_coordinator.py` (537 LOC) is the top-level orchestrator: holds `ControlForwarder` (TCP client to Robot Pi :5001), `TelemetryReceiver` (TCP server :5003), `VideoReceiver` (TCP server :5002), a video HTTP re-server on :5004, a telemetry ring buffer, and a `BackendClient`.
* `BackendClient` registers 15 Socket.IO handlers that must match, string-for-string, the events emitted by Flutter.
* All outbound traffic over HaLow is framed + HMAC-signed + sequence-numbered in `common/framing.py`.
* PSK loaded from `/etc/serpent/psk` (600 perms, root-owned) or the `SERPENT_PSK_HEX` env var for dev/test. Never committed (SI-12).
* TCP_NODELAY disabled Nagle; TCP keepalive 5 s idle / 2 s interval / 3 probes detects a zombie Robot Pi within ~11 s.
* Also owns the **Modbus master** to the winch ESP32s in single-Pi configurations (`base_pi/winch_controller.py`), although in the canonical two-Pi setup the Robot Pi is the master.

### 3.4 HaLow radio link

* ALFA HaLow-R, Morse Micro MM6108 chipset, 802.11ah sub-GHz.
* Point-to-point between the two Pis, ~1 km LOS, 15 Mbps peak, typical latency ~10 ms, dominant source of end-to-end jitter.
* From the application's point of view it's just a TCP-capable IP link; no HaLow-specific logic in the code.

### 3.5 Robot Pi bridge (`robot_pi/`)

* `bridge_coordinator.py` (627 LOC) mirrors the Base Pi structure but in reverse: `ControlServer` (TCP server :5001), `CommandExecutor`, `ActuatorController`, `SensorReader`, `TelemetrySender` (TCP client :5003), `VideoCapture` (3 USB cams at /dev/video0..2, 640×480 @ 10 FPS MJPEG).
* `WatchdogMonitor.check_safety()` runs at ~10 Hz. Reads `control_server.get_control_age()`; if >5 s after control is established, or if uptime >30 s but control never established, fires E-STOP.
* `ActuatorController._estop_lock` is a single `threading.Lock` that wraps *both* the E-STOP flag check and the Motoron write — that's what makes the check-then-act atomic (SI-7).
* `ChainsawRamp` background thread keeps chainsaw commands ≥ 10 Hz to avoid the Motoron's own command timeout.
* Systemd unit: `serpent-robot-bridge.service`, user `serpentbase`, groups `i2c gpio video`, `WatchdogSec=30`, `MemoryMax=256M`, `CPUQuota=80%`, Restart=always/3 s. If the process dies, systemd restarts it — and during the restart the E-STOP defaults to latched, so the robot is safe even during the restart window.

### 3.6 Firmware — ESP32 winch station (`firmware/winch_station/winch_station.ino`)

* **Target:** ESP32 (esp32dev), PlatformIO.
* **Build flag:** `-D UNIT_ID=1` (LEFT) or `-D UNIT_ID=2` (RIGHT); two identical binaries, one flag different.
* **Modbus RTU slave** on `Serial2` at **250 000 baud**, RS-485 DE/RE on GPIO 4.
* **Register map (authoritative per SI-11; duplicated in `base_pi/winch_controller.py`):**

| Reg | Dir | Type | Meaning |
|---|---|---|---|
| HR0 | R/W | int16 | Winch speed, -1000..+1000 (positive = spool in) |
| HR1 | R/W | uint16 | Enable (0/1) |
| HR2 | R/W | uint16 | Tension setpoint override (0 = keep EEPROM value) |
| IR0/1 | R | int32 BE | Winch encoder counts |
| IR2/3 | R | int32 BE | Tension motor A encoder |
| IR4/5 | R | int32 BE | Tension motor B encoder |
| IR6 | R | uint16 | Tension sensor A raw ADC (0–4095) |
| IR7 | R | uint16 | Tension sensor B raw ADC |
| IR8 | R | uint16 | Status flags: SLACK | OVERTENSION | STALL | WATCHDOG | TENSION_ARMED |

* **Command watchdog 500 ms** (SI-8): if HR0 not written for 500 ms, motors are forced to 0 and STATUS_WATCHDOG is raised in IR8. Fully local — the ESP32 is safe even if both Pis are lost.
* **Tension loop:** simple PI, kP 0.3 / kI 0.01, integral clamp ±2000, output clamped ±1000. Runs every 10 ms (~100 Hz) on both tension motors.
* **EEPROM persistence:** 16 bytes, magic `0x5A5A` + tension setpoint; loaded on boot, written when HR2 is written non-zero.

### 3.7 Dashboard (`dashboard/`)

Flask + Flask-SocketIO web UI, runs on the Base Pi on port **5006** (Base Pi config) / 5005 (Robot-side instance). Consumes telemetry from the TelemetryReceiver ring buffer and pushes it out over Socket.IO at ~10 Hz on the `/status`, `/motor_currents`, `/telemetry`, `/video` channels. Separate from the serpent_backend port-5000 UI used by Flutter — the dashboard is for a laptop browser, not the handheld.

---

## 4. File integration map — who talks to whom

Read each row as "**A** sends **what** to **B** over **wire**".

| A | What | B | Wire |
|---|---|---|---|
| `backend_service.dart:758` | `raw_button_press {button}` | `server.py` | Socket.IO TCP 5000 |
| `backend_service.dart:767` | `input_event {type,index,value,timestamp}` | serpent_backend | Socket.IO TCP 5000 |
| `backend_service.dart:727` | `emergency_toggle` (legacy) | serpent_backend | Socket.IO TCP 5000 |
| `backend_service.dart:778,785` | `height_update`, `force_update` | serpent_backend | Socket.IO TCP 5000 |
| `backend_service.dart:792,798` | `clamp_open`, `clamp_close` | serpent_backend | Socket.IO TCP 5000 |
| `backend_service.dart:734` | `start_camera {camera_id}` | serpent_backend | Socket.IO TCP 5000 |
| `backend_service.dart:632` | `latency_ping {timestamp}` | serpent_backend | Socket.IO TCP 5000 |
| serpent_backend | fan-out of all above | `base_pi/core/backend_client.py:93-207` | Socket.IO TCP 5000 (as client) |
| `base_pi/core/backend_client.py` | translated bridge commands | `BridgeCoordinator._on_backend_event` | in-process callback |
| `base_pi/control_forwarder.py:send_command` | HMAC-framed JSON | `robot_pi/control/control_server.py:receive_command` | TCP 5001 over HaLow |
| `robot_pi/control/control_server.py` | parsed payload + seq | `robot_pi/core/command_executor.py:execute` | in-process |
| `robot_pi/core/command_executor.py` | method calls | `robot_pi/actuator_controller.py:set_motor_speed / set_servo / clear_estop / engage_estop / ...` | in-process, under `_estop_lock` |
| `robot_pi/actuator_controller.py` | I²C motoron frames | Motoron boards 0x10–0x13 | I²C bus 1 |
| `robot_pi/actuator_controller.py` | I²C PCA9685 frames | PCA9685 @ 0x40 | I²C bus 1 |
| `base_pi/winch_controller.py` *or* Robot Pi equivalent | Modbus RTU `write_register(HR0,speed)` | `firmware/winch_station/winch_station.ino` `mb.Hreg(HR0)` | RS-485 250 kbps |
| `robot_pi/sensor_reader.py` | IMU/baro/current reads | `telemetry_sender.py` | in-process |
| `robot_pi/telemetry_sender.py` | HMAC-framed telemetry dict | `base_pi/telemetry_receiver.py` | TCP 5003 over HaLow |
| `robot_pi/video_capture.py` | 3× MJPEG framed stream | `base_pi/video_receiver.py` | TCP 5002 over HaLow |
| `base_pi/video_receiver.py` → video HTTP server | MJPEG multipart | Browser or Flutter `VideoFeed` widget | HTTP 5004 |
| `base_pi/telemetry_receiver.py` → BackendClient | telemetry event | serpent_backend → Flutter | Socket.IO TCP 5000 |

---

## 5. Safety architecture

> **2026-04-24 — E-STOP REBUILD COMPLETE.** Milestones R0-R10 of `ESTOP_REBUILD_PLAN.md` v2.1 landed. SI-1, SI-2, SI-3, SI-6, SI-7 are enforced again. The 2026-04-23 "removed" status table below is **historical**; see `agent_stack/gates/safety_invariants.md` for the current authoritative file-level mapping.
>
> **2026-04-23 — E-STOP SURFACE REMOVED (historical).** The previous E-STOP state machine, watchdog, and associated plumbing were torn out wholesale (see `pi_halow_bridge/PI-HALOW-BRIDGE/archive/SAFETY_AUDIT_ESTOP.md`, plan `federated-riding-summit.md`). A ground-up rebuild was a separate future session — now complete per the banner above. What follows is preserved verbatim from the removal-era doc.

### 5.1 Invariant status

Authoritative list in `agent_stack/gates/safety_invariants.md`. As of removal:

| # | Invariant | Status | Where |
|---|---|---|---|
| SI-1 | E-STOP latched at boot | **PENDING REBUILD** | — |
| SI-2 | 5 s watchdog + 30 s startup grace | **PENDING REBUILD** | — |
| SI-3 | SET semantics (no toggle) | **PENDING REBUILD** | — |
| SI-4 | HMAC-SHA256 + strictly-monotonic seq | ✅ enforced | `common/framing.py:SecureFramer`; tested in `tests/test_framing.py` |
| SI-5 | Control > video | ✅ enforced | Separate socket/thread; control has shorter timeouts than video |
| SI-6 | Crash/disconnect = E-STOP | **PENDING REBUILD** | — |
| SI-7 | Single-lock TOCTOU-safe actuation | **PENDING REBUILD** | `_lock` still serialises hardware bus but no longer guards any flag |
| SI-8 | ≤500 ms firmware command watchdog | ✅ enforced | `firmware/winch_station/winch_station.ino:89` (unchanged) |
| SI-9 | Buffer bounds | ✅ enforced | `MAX_FRAME_SIZE=16384`, video 256 KB, control 64 KB |
| SI-10 | Conditional HW imports in SIM_MODE | ✅ enforced | |
| SI-11 | Modbus map is THE contract | ✅ enforced | Locked in by `tests/test_winch_controller_modbus.py` |
| SI-12 | PSK never in VCS | ✅ enforced | `.gitignore` + `generate_psk.py` + `/etc/serpent/psk` |

### 5.2 The safety gate (post-removal)

`agent_stack/gates/destructive_ops.yaml :: safety_critical_paths` now covers HMAC framing, actuator hardware drivers, firmware, systemd units, and PSK/deploy scripts. The `watchdog_monitor.py` paths are gone (the files were deleted with the E-STOP surface). Gate list is authoritative — see the YAML.

### 5.3 Trust boundary — where HMAC starts and stops

```
Flutter ──plain JSON SocketIO──> serpent_backend ──plain JSON SocketIO──> Base Pi BackendClient
                                                                                      │
                              ══ TRUST BOUNDARY — HMAC-SHA256 + monotonic seq ══      │
                                                                                      ▼
                                                                              Robot Pi ControlServer
                                                                                      │
                                                   ══ RS-485 local, 500 ms WDT ══     │
                                                                                      ▼
                                                                                  ESP32
```

The Flutter side is **untrusted** from the authentication perspective — anything on the LAN that can reach TCP 5000 can emit Socket.IO events. The Base Pi BackendClient is where trust is established: it re-signs with the PSK before the HaLow hop. This is a deliberate design choice (the TrimUI can't easily hold long-term crypto secrets), but it means **the LAN itself is part of the trusted perimeter**.

**Accepted design position.** The Flutter ↔ serpent_backend hop is *intentionally* plain HTTP + plain Socket.IO on port 5000 with no TLS. This is load-bearing in two places: `serpent_trimui_app/android/app/src/main/AndroidManifest.xml:28` sets `usesCleartextTraffic="true"`, and the backend binds plain HTTP at `pi_backend/server.py`. The threat model treats the operator LAN as the trust perimeter for these reasons:

1. TLS between the TrimUI and the backend would not stop a rogue LAN device from spoofing Socket.IO events — neither side authenticates at the session layer.
2. The TrimUI has no durable, rotatable secret store; cert pinning has a painful rotation UX on the handheld.
3. The real safety boundary is at the Base Pi's HMAC signing step — commands that reach the Robot Pi without a valid HMAC are rejected.

**Note post-removal 2026-04-23:** HMAC rejection no longer engages E-STOP (no E-STOP exists to engage); the control server just logs the error and closes the client socket. The rebuild will restore the safety response.

A LAN attacker with wifi access can inject Socket.IO events into port 5000 — this is known and accepted. If you ever want to close it, the right move is not TLS on port 5000; it's moving the serpent_backend to a Unix socket on the Base Pi and removing the LAN attack surface entirely, which breaks the canonical split-topology deploy and is out of scope today.

---

## 6. Timing budget

```
 Event                                   Typical   Budget
 ────────────────────────────────────    ───────   ──────
 Input capture (MainActivity→EventCh)    ~1 ms
 Flutter debounce/serialize              ~1 ms
 Socket.IO to serpent_backend            ~2 ms
 Backend fan-out to Base Pi client       ~1 ms
 Base Pi BackendClient translate         ~1 ms
 HMAC framing + TCP send                 ~2 ms
 HaLow link (802.11ah)                   ~10 ms    link-limited
 Robot Pi receive + HMAC verify          ~2 ms
 CommandExecutor dispatch + I²C write    ~5 ms     dominated by Motoron ACK
 ────────────────────────────────────    ───────
 Total operator-input → motor PWM        ~20–50 ms
 Watchdog E-STOP threshold               5 000 ms
 ESP32 local command watchdog            500 ms
 Telemetry update period (10 Hz)         100 ms
 Video frame (10 FPS × 3 cams)           ~100 ms per cam
```

---

## 7. Ports, IPs, config reference

| Port | Role | Listener | Protocol | Authenticated |
|---|---|---|---|---|
| 5000 | Flutter ↔ serpent_backend ↔ Base Pi BackendClient | serpent_backend | HTTP + Socket.IO + MJPEG | No (LAN-trust) |
| 5001 | Control Base→Robot | Robot Pi `ControlServer` | TCP (HMAC-framed) | **Yes** |
| 5002 | Video Robot→Base | Base Pi `VideoReceiver` | TCP (framed MJPEG) | No (content only) |
| 5003 | Telemetry Robot→Base | Base Pi `TelemetryReceiver` | TCP (HMAC-framed) | **Yes** |
| 5004 | Video HTTP for browser / Flutter video widget | Base Pi video HTTP server | HTTP MJPEG | No |
| 5005 | Robot Pi dashboard | Robot Pi dashboard | WebSocket + HTTP | No |
| 5006 | Base Pi dashboard | Base Pi dashboard | WebSocket + HTTP | No |
| (RS-485) | Modbus RTU to ESP32s | ESP32 slaves UNIT_ID 1/2 | Modbus RTU 250 kbps | Local (wired) + 500 ms WDT |

Canonical IPs (defaults, overridable):
* Base Pi: `192.168.1.10`
* Robot Pi: `192.168.1.20`

Key config files:
* `common/constants.py` — immutable safety constants.
* `robot_pi/config.py`, `base_pi/config.py` — device-specific (I²C addresses, GPIO pins, camera paths, BACKEND_URL=http://localhost:5000).
* `robot_pi/.env.example`, `base_pi/.env.example` — env-var templates.
* systemd units: `serpent-robot-bridge.service`, `serpent-base-bridge.service`, dashboard units.
* `firmware/winch_station/platformio.ini` — UNIT_ID compile flag, board, libs.
* No YAML/JSON runtime config — everything is Python constants + env vars (by design, for auditability).

---

## 8. What is working today

* **End-to-end control path under SIM_MODE** — `scripts/run_sim.py` spins both bridges on localhost at ports 15001-15003 with a random PSK; control flows operator → mocked actuators without hardware.
* **HMAC + monotonic seq + replay rejection** — exercised by `tests/test_framing.py` (244 LOC), `test_fault_injection.py` (8 attack cases, 391 LOC), `test_safety_constants.py`.
* **E-STOP latched-at-boot + cleared-only-by-live-control** — `tests/test_estop.py` (334 LOC) and `test_estop_integration.py` (475 LOC).
* **26+ stress-test suite** across five phases (`scripts/run_stress_suite.py`): control flood 100 Hz, network blackout, 50 %/90 % packet loss, bandwidth collapse, reconnect × 20, memory-leak detection, concurrent channel load. README records these all passing at v1.1.
* **Firmware watchdog** — ESP32s independently stop motors within 500 ms if Modbus goes silent.
* **Dashboards** — separate Flask UIs on :5005 (robot) and :5006 (base) surface live telemetry and component health without needing the Flutter app.
* **Autostart on TrimUI** — `BootReceiver.kt` + LEANBACK HOME intent filter boots straight into `MainScreen`.
* **mDNS + subnet-scan fallback discovery** — operator doesn't need to type an IP.

---

## 9. Where to find stuff (quick map)

| You want to… | Look at |
|---|---|
| Change the PSK | `scripts/generate_psk.py`, `setup_psk_on_hub.sh`, `/etc/serpent/psk` |
| Add a new button on the TrimUI | `lib/services/key_event_service.dart:_keyToButtonMap` + `lib/services/backend_service.dart` emit |
| Add a new telemetry field | `agent_stack/examples/01_add_telemetry_field.md` (runbook exists because this touches 3+ files) |
| Change a winch Modbus register | `firmware/winch_station/winch_station.ino:15-28` + `base_pi/winch_controller.py` in lockstep (SI-11) |
| Change the watchdog timeout | **DON'T** without safety-gate review — `common/constants.py:WATCHDOG_TIMEOUT_S` |
| Redeploy to a Pi | `setup_robot_pi.sh` or `setup_base_pi.sh`; `pi_install.sh` for the hub Pi |
| Run the full test suite | `python "pi_halow_bridge/PI-HALOW-BRIDGE/scripts/test_all.py"` |
| Run a simulation | `python "pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_sim.py"` |
| Validate everything | `python agent_stack/tools/validate.py all` |
| See the repo map | `agent_stack/repo_map.md` (regenerate with `tools/build_repo_map.py`) |

---

## 10. The agent framework above it all

This repo is governed by a meta-framework in `agent_stack/` that enforces the safety discipline:

* **Orchestrator** (in `.claude/agents/orchestrator.md`) decomposes any task >3 steps.
* **Specialists:** `firmware-embedded`, `platform-toolchain`, `test-verification`, `debug-triage`, `docs-release`, `repo-architect`.
* **Safety gate:** any diff touching a path in `destructive_ops.yaml` must be `approve`-d by the read-only `safety-gate` agent before commit. The gate cross-references `safety_invariants.md` and can return `needs_human` for anything ambiguous.
* **Session state:** `agent_stack/.runtime/session_state.json` is the hand-off record between agents; never silently overwritten.
* **Workflows:** `feature.md`, `bugfix.md`, `firmware_change.md`, `refactor.md`, `release.md` — each picks the right specialist sequence.
* **Unified validation:** `agent_stack/tools/validate.py all` = Python tests + Flutter analyze/test + firmware smoke + SIM_MODE run.

The framework exists because the safety invariants are easy to break by accident in a refactor — the gate catches the accident before it lands.

---

*Companion document:* `agent_stack/audits/2026-04-23-audit-findings.md` — things that aren't quite right, written by the `debug-triage` agent in a parallel pass. Read it alongside this one.

---

## 11. Remediation addendum (2026-04-23)

Following the initial audit, a same-day remediation sweep landed these structural changes (full detail in `agent_stack/audits/2026-04-23-audit-findings.md §-1`):

* Obsolete `raspberry_pi_receiver/` and `raspberry_pi_robot/` directories (with inverted control/video port assignments) moved to `serpent_trimui_app/archive/`.
* `halow_bridge.py.old` moved to `PI-HALOW-BRIDGE/archive/`; `base_pi/README.md` updated to point at the real entrypoint `core/bridge_coordinator.py`.
* `pi_backend/server.py` slimmed from 2362 → 1902 lines (commented-duplicate preamble removed). Wire contract fixed: clamp, toggle_cv, gamepad_command, r1_button now relay end-to-end from Flutter to the bridge.
* Safety-gate (`agent_stack/gates/destructive_ops.yaml`) widened to cover `robot_pi/sensor_reader.py`, `base_pi/control_forwarder.py`, `base_pi/telemetry_receiver.py`, `dashboard/config.py`.
* `DISABLE_WATCHDOG_FOR_LOCAL_TESTING` env default flipped to safe (`False`).
* New `test_winch_controller_modbus.py` (15 assertions, all passing) locks the SI-11 register-map contract between firmware and `base_pi/winch_controller.py`.
* `agent_stack/.runtime/session_state.json` created to match the schema promised by `CLAUDE.md`.
* **Security:** a real 64-char PSK was discovered in accidentally-named files (`chmod`, `echo`, `sudo`, `600`) left in the PI-HALOW-BRIDGE working tree. The files were deleted; **the PSK itself still needs to be rotated by a human** — see `agent_stack/audits/2026-04-23-audit-findings.md §-1` PSK-leak note.

E-STOP-related findings (C1, C2, C3, D7, T3, T5, `emergency_toggle`, `estop_clear_progress`) were **deferred by user request** — the E-STOP path is being reworked separately.

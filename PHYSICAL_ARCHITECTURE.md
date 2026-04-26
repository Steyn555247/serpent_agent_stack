# Serpent Physical & Compute Architecture

> How the actual hardware is laid out, which computer owns which piece of silicon, and how the bits move between them. Companion to `SYSTEM_ARCHITECTURE.md` (which is software-focused). Read this one first if you're trying to understand "where does the robot's brain live."

---

## TL;DR picture

```
  OPERATOR SIDE                                          ROBOT SIDE (on the rope)
  ─────────────────────                                  ───────────────────────────

  ┌──────────────┐                                       ┌─────────────────────────┐
  │ TrimUI S Pro │                                       │ Robot body              │
  │ (handheld,   │                                       │                         │
  │  Android)    │ WiFi ~2.4 GHz                          │  ┌───────────────────┐ │
  │ ──────────── │ ←————————————————————————————→        │  │ Robot Pi 4/5      │ │
  │ Flutter app  │        (operator LAN)                  │  │ (Linux)           │ │
  └──────┬───────┘                                       │  │                   │ │
         │  Socket.IO :5000                              │  │  • Python bridge  │ │
         │  (plain HTTP)                                 │  │  • ActuatorCtrl   │ │
         ▼                                               │  │  • SensorReader   │ │
  ┌──────────────┐                                       │  │  • VideoCapture   │ │
  │ serpent_     │                                       │  └────┬─────┬───┬────┘ │
  │ backend      │ ← Flask + Flask-SocketIO              │       │     │   │      │
  │ (Python)     │                                       │       │I²C  │USB│      │
  └──────┬───────┘                                       │       │bus 1│×3 │      │
         │ localhost                                      │       │     │   │      │
         │ Socket.IO :5000                                │       ▼     ▼   ▼      │
         ▼                                                │  ┌─────┐┌───┐┌────────┐│
  ┌──────────────┐                                       │  │Moto-││cam││  IMU   ││
  │ Base Pi 4/5  │                                       │  │rons ││0-2││  baro  ││
  │ (Linux)      │ HaLow radio (802.11ah)                │  │×4   ││USB││  current│
  │ ──────────── │ ←—————————————————————————————→       │  │8 mtr││   ││  servo ││
  │ • Python     │  HMAC + monotonic seq                 │  └──┬──┘└───┘└────────┘│
  │   bridge     │  TCP 5001 (cmd) 5002 (vid) 5003 (tel) │     │                   │
  │ • BackendCli │  HaLow-R (ALFA, Morse Micro MM6108)   │     ▼                   │
  │ • HaLow XCVR │  ~1 km LOS, ~15 Mbps, ~10 ms latency  │  8 DC motors (inc.     │
  │ • RS-485 mst │                                       │  Motor 6 = ascender    │
  └──────┬───────┘                                       │  holding robot weight) │
         │                                               │                        │
         │ RS-485 Modbus RTU                             │                        │
         │ /dev/ttyUSB0 @ 250 000 baud                   │                        │
         ▼                                               └─────────────────────────┘
  ┌──────────────┐
  │ Winch ESP32s │  (2 units, UNIT_ID=1 LEFT, UNIT_ID=2 RIGHT)
  │ ──────────── │
  │ • Motoron    │  Each station: winch motor + 2 tension motors +
  │   motor ctrl │  quadrature encoders + tension strain-gauge ADCs +
  │ • Encoders   │  firmware 500 ms command-watchdog (SI-8, untouchable)
  │ • Tension PI │
  └──────┬───────┘
         │
         ▼
     rope winches feeding tension up to the robot
```

Three machines in the hot path: **Robot Pi** (on the robot), **Base Pi** (at the operator/anchor station), and the **TrimUI handheld** (in the operator's hands). One Flask intermediary (`serpent_backend`) sits between the TrimUI and the Base Pi — traditionally runs on the Base Pi itself.

---

## What the physical robot is

A two-chainsaw tree-climbing / pruning robot that hangs off a rope. Key subsystems on the robot body:

- **2 chainsaws** — each has an on/off motor and a position/traverse motor.
- **Ascender (Motor 6)** — the load-bearing motor that moves the robot up and down the rope. This is the single most safety-critical actuator on the whole robot.
- **Traverse (Motor 7)** — moves the robot laterally along a horizontal rope run.
- **2 clamps** — servo-driven (via PCA9685) grippers for securing to branches.
- **3 USB cameras** — typically one looking forward, one looking at each chainsaw workspace.
- **IMU + barometer + per-motor current sensors** — BNO085 IMU, BMP581 barometer, INA238 current sensors on 2 motors.

Off-robot but part of the system:

- **2 winch stations** at the base anchor, providing rope tension. Each is an ESP32 driving one winch motor and 2 tension-compensating motors with closed-loop tension control at ~100 Hz. These are physically at the operator end, connected to the Base Pi via wired RS-485.

---

## Compute levels (closest-to-hardware first)

### Level 0 — **Motor-driver firmware (Motoron PCBA)**

- **Hardware:** 4 × Pololu Motoron M2H dual-channel motor-controller boards on the Robot Pi's I²C bus (addresses `0x10–0x13`). Each board handles 2 DC motors with PWM + direction + current sensing.
- **Software:** Pololu's own firmware on the Motoron MCU. Not our code.
- **Role:** lowest-level motor PWM generation. Accepts speed commands via I²C from the Robot Pi (~1 ms round-trip), runs its own internal control loop, and has a **built-in ~1.5 s command-timeout** that zeroes motors if I²C goes silent. This is the hardware-level safety net for all 8 motors including the ascender.
- **What you can configure:** max acceleration/deceleration (we set 200), CRC on/off, board address. We enabled the command timeout on all boards including board 3 (motors 6 + 7) — it was previously disabled there, and re-enabling it is one of the only live automatic stops the robot has right now.

### Level 0 — **Winch-station firmware (ESP32)**

Different piece of Level-0 silicon, same tier.

- **Hardware:** 2 × ESP32 dev boards, one per winch (`UNIT_ID=1` LEFT, `UNIT_ID=2` RIGHT). Each drives one main winch motor + 2 tension motors via its own MCU-generated PWM, reads quadrature encoders, reads strain-gauge ADCs for tension feedback, and speaks Modbus RTU on Serial2 at 250 kbps through an RS-485 transceiver (DE/RE on GPIO 4).
- **Software:** Arduino/PlatformIO firmware in `firmware/winch_station/winch_station.ino`. 100 Hz PI tension-control loop, persistent tension setpoint in EEPROM, 500 ms command watchdog that forces motors to 0 if Modbus goes silent. This is **SI-8** and it is deliberately untouchable — lives on the ESP32, has no dependency on the Pi, keeps working if everything upstream dies.
- **Registers (Modbus map, SI-11):** HR0 = speed command, HR1 = enable, HR2 = tension setpoint override, IR0-8 = encoders + ADC + status flags. Locked in by `tests/test_winch_controller_modbus.py`.

### Level 1 — **Robot Pi (Linux userspace)**

- **Hardware:** Raspberry Pi 4 or 5 physically mounted on the robot body. Power comes from the robot's on-board battery pack.
- **Role:** translates high-level commands ("drive chainsaw 1 at 80%", "lift ascender at 60%", "open clamp") into hardware writes. Reads all on-robot sensors, captures video from 3 USB cameras, sends everything back over HaLow.
- **Code:** `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/`. Main entry: `robot_pi.core.bridge_coordinator` (systemd unit `serpent-robot-bridge.service`). Key modules:
  - `ActuatorController` — writes Motoron I²C, writes PCA9685 servo (through TCA9548A I²C multiplexer channel 4). Holds `_lock` for hardware serialisation.
  - `SensorReader` — reads BNO085 IMU (mux ch. 7), BMP581 baro (also ch. 7, daisy-chained), INA238 current sensors (mux ch. 5 + 6). Publishes telemetry at 10 Hz.
  - `VideoCapture` — opens `/dev/video0`, `/dev/video2`, `/dev/video4` at 640×480 @ 10 FPS JPEG, streams over TCP to Base Pi.
  - `ControlServer` — TCP **server** on port 5001. HMAC-verifies incoming control frames (SI-4), dispatches through `CommandExecutor`.
  - `TelemetrySender` — TCP **client** to Base Pi on port 5003. HMAC-signs outgoing telemetry.
- **Hardware interfaces:** I²C bus 1 (everything — Motorons, servo controller, sensors, multiplexer), 3 USB ports (cameras), wired ethernet (to the HaLow transceiver), power input.

### Level 2 — **Base Pi (Linux userspace)**

- **Hardware:** Raspberry Pi 4 or 5 at the operator station / rope anchor. Mains or large-battery powered.
- **Role:** the robot's "ground-station" half. Owns the HaLow radio link to the robot, the RS-485 Modbus bus to the winch ESP32s, and the LAN interface to the operator's tools.
- **Code:** `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/`. Main entry: `base_pi.core.bridge_coordinator` (systemd unit `serpent-base-bridge.service`). Key modules:
  - `ControlForwarder` — TCP **client** to Robot Pi on port 5001. Signs + sends control frames.
  - `TelemetryReceiver` — TCP **server** on port 5003. Verifies incoming telemetry.
  - `VideoReceiver` — TCP **server** on port 5002. Unauthenticated (video payloads are content-only, no actuation).
  - `WinchController` — USB-serial RS-485 master on `/dev/ttyUSB0` at 250 000 baud. Modbus RTU master polling/writing the 2 ESP32 winch stations. This is why the winches are "owned" by the Base Pi, not the Robot Pi — the wire runs to the base station.
  - `BackendClient` — Socket.IO **client** to `serpent_backend` on port 5000. Typically localhost.
  - `VideoHTTPServer` — re-serves MJPEG frames as HTTP on port 5004 for browser/Flutter consumption.
  - `TelemetryWebSocket` — optional dashboard WebSocket on port 5007.
  - Dashboard (Flask) on port 5006.
- **Hardware interfaces:** HaLow radio (via wired ethernet to the ALFA transceiver), USB RS-485 dongle for the winches, LAN ethernet/WiFi for the TrimUI + dashboards.

### Level 3 — **serpent_backend (Flask + Flask-SocketIO)**

- **Runs on:** Base Pi (canonical) or a dedicated "hub" Pi.
- **File:** `pi_backend/server.py`. ~1900 LOC. Flask + Flask-SocketIO, async_mode=`threading`.
- **Role:** the rendezvous point between Flutter and the Base Pi bridge. Terminates the Flutter Socket.IO session on port 5000, translates events, forwards to the bridge (which is ALSO a Socket.IO client of it). Also serves MJPEG HTTP frames to Flutter at `/video_feed/<id>`.
- **Why it exists separately from the Base Pi bridge:** historical. The Flutter app never talks to the bridge directly; it always goes through this Flask middleman. Future rebuild could merge them, but it's non-trivial (event-name string-matched contract).

### Level 4 — **TrimUI Smart Pro S (Android)**

- **Hardware:** TrimUI Smart Pro S handheld. ~1280×720 landscape LCD, gamepad buttons + analog sticks, runs Android (custom ROM). In the operator's hands.
- **Software:** `serpent_trimui_app/` — Flutter 3 app. Auto-launches on device boot via `BootReceiver.kt` + LEANBACK HOME intent filter.
- **Role:** operator UI. Displays live video + telemetry. Captures joystick/button input and emits Socket.IO events. No local safety logic (post-removal).
- **How it finds the backend:** mDNS `_serpent._tcp` service discovery, with subnet-scan fallback, with manual-IP fallback.
- **Network:** WiFi only. Same LAN as the serpent_backend (usually Base Pi).

### Level 5 — **Optional: laptop browser for dashboards**

- Any laptop on the LAN can open `http://<base-pi>:5006/` for the Base Pi dashboard or `:5005` for the Robot Pi dashboard (when the robot's Pi is reachable via the LAN, which it usually isn't mid-mission because it's at the end of a HaLow radio link).
- Not part of the hot path. For engineers debugging, not operators driving.

---

## Interconnect table

| From | To | Physical medium | Protocol | Bandwidth / latency | Authenticated |
|---|---|---|---|---|---|
| Flutter (TrimUI) | serpent_backend | WiFi 2.4 GHz | HTTP + Socket.IO (TCP 5000) | LAN speed / ~5 ms | **No** — LAN-trusted |
| serpent_backend | Base Pi bridge | localhost (loopback) | Socket.IO (TCP 5000) | in-process / <1 ms | **No** — same host |
| Base Pi | Robot Pi | HaLow 802.11ah | TCP 5001 (control) | 15 Mbps / ~10 ms | **Yes** — HMAC-SHA256 + monotonic seq (SI-4) |
| Base Pi | Robot Pi | HaLow 802.11ah | TCP 5002 (video) | (same link) | No (content only) |
| Robot Pi | Base Pi | HaLow 802.11ah | TCP 5003 (telemetry) | (same link) | **Yes** — HMAC-SHA256 |
| Base Pi | Winch ESP32 ×2 | RS-485 twisted pair | Modbus RTU @ 250 kbps | ~2 kBps / ~8 ms | Firmware 500 ms WDT (SI-8) |
| Robot Pi | Motoron boards ×4 | I²C bus 1 | Pololu I²C protocol | ~10 KB/s / ~1 ms | Hardware 1.5 s command WDT |
| Robot Pi | PCA9685 servo | I²C bus 1 (via TCA9548A mux ch. 4) | I²C | ~1 KB/s | None (local) |
| Robot Pi | BNO085 IMU | I²C bus 1 (mux ch. 7) | I²C | low | None |
| Robot Pi | BMP581 baro | I²C bus 1 (mux ch. 7, daisy-chained) | I²C | low | None |
| Robot Pi | INA238 current sensors ×2 | I²C bus 1 (mux ch. 5 + 6) | I²C | low | None |
| Robot Pi | USB cameras ×3 | USB 2.0 | V4L2 MJPEG | ~1 MB/s per cam | None (local) |
| Winch ESP32 | winch motor + tension motors | PWM + DIR GPIO | analogue PWM | — | — |
| Winch ESP32 | encoders + ADC | GPIO + ADC | — | — | — |
| Base Pi | dashboards | LAN ethernet/WiFi | HTTP + WebSocket (5005/5006/5007) | LAN | No (LAN-trusted) |

---

## Physical placement summary

| Component | Physical location | Power |
|---|---|---|
| TrimUI handheld | Operator's hands | Internal Li-ion, USB-C charge |
| serpent_backend | Base Pi (same machine as bridge) | Mains or ground-station battery |
| Base Pi | Operator station / rope anchor | Mains or ground-station battery |
| HaLow radio (Base-side) | Base Pi USB or ethernet | USB-powered from Base Pi |
| RS-485 transceiver | Base Pi USB | USB-powered |
| Winch ESP32 station ×2 | Base anchor (where rope is fixed) | Dedicated winch-station supply |
| Winch motors + tension motors ×2 stations | Base anchor | Winch-station supply |
| HaLow radio (Robot-side) | Robot body | Robot battery pack |
| Robot Pi | Robot body | Robot battery pack (regulated 5 V) |
| Motoron boards ×4 | Robot body | Battery pack (motor-level voltage, typically 12 V / 24 V through Motoron) |
| 8 DC motors (chainsaws, ascender, traverse, clamp actuators) | Robot body | Driven by Motorons from main battery |
| PCA9685 + servos | Robot body | 5 V from Robot Pi rail, through I²C multiplexer |
| IMU / baro / current sensors | Robot body | 3.3 V from Robot Pi rail |
| USB cameras ×3 | Robot body (mounted for POV + chainsaw views) | USB bus power from Robot Pi |

---

## Power domains (why this matters for safety)

Three isolated power domains keep the system safe(-ish) on partial failure:

1. **Robot battery** — powers Robot Pi + Motorons + motors + sensors + cameras on the robot body. If this dies, everything on the robot stops. The firmware / Motoron watchdogs become irrelevant because there's no power.
2. **Ground-station supply** — powers Base Pi + HaLow + RS-485 bus + winch ESP32s + winch motors. If this dies, the Base Pi stops forwarding control, HaLow link drops, Robot Pi notices via the watchdog (once rebuilt) and engages E-STOP.
3. **Operator battery** — just the TrimUI. If the operator battery dies, the TrimUI stops sending commands; same effect as any other control-channel silence — the Robot Pi's watchdog (once rebuilt) is supposed to engage E-STOP.

The one failure that is handled *mechanically* rather than electrically is instantaneous total power loss on the robot itself. The ascender (Motor 6's load) is a mechanical one-way rope-grip device (cam-lock / worm-gear family) — the motor drives its input gear, but the rope-hold is a geometric property of the ascender itself, not something the motor has to actively provide torque for. If the whole 12/24 V rail drops out, the motor stops driving but the ascender keeps gripping the rope. The robot stops in place, does not fall. Chainsaws, clamps, and the traverse motor (Motor 7) also stop, but none of those are weight-bearing — only Motor 6's load is, and it is passively safe by design.

Hazards NOT addressed by any electrical or firmware layer: rope failure (abrasion, cut, fatigue), clamp-mechanism failure, or a mechanical fault in the ascender itself (cam wear, spring failure). Those are purely physical-hardware quality questions.

---

## Safety boundaries mapped to physical layers

| Layer | What catches what |
|---|---|
| L0 firmware (ESP32 winch) | Local 500 ms command watchdog — zeros motors if Modbus Base Pi→ESP32 dies. Hardware enforced, can't be disabled from software. SI-8. |
| L0 firmware (Motoron) | ~1.5 s I²C command watchdog — zeros motor if Robot Pi→Motoron I²C goes silent. Hardware enforced at board level. Re-enabled 2026-04-23 on board 3 (Motor 6 ascender). |
| L1 Robot Pi | Boot-time 2 s grace in `ActuatorController.set_motor_speed` refuses non-zero commands during startup. Full E-STOP state machine **pending rebuild** — see `ESTOP_REBUILD_PLAN.md`. |
| L1↔L2 HaLow link | HMAC-SHA256 + monotonic seq on every control / telemetry frame. SI-4. An attacker without the PSK can't inject commands. |
| L2 Base Pi | Relay + bridge. No local safety logic — depends on Robot Pi and firmware for authoritative safety. |
| L2↔L3 loopback | Plain Socket.IO. Trusts localhost. |
| L3↔L4 LAN | Plain Socket.IO + HTTP. **LAN is inside the trust perimeter by design** — see `SYSTEM_ARCHITECTURE.md §5.3` for the reasoning. |
| L4 Flutter | No local safety logic post-removal. The rebuild will add a UI-level E-STOP primitive (Y-button hold per `ESTOP_REBUILD_PLAN.md`). |

The **two layers that actually control motor power** are L0 (firmware on the Motoron + ESP32) and L1 (Robot Pi's `ActuatorController`). Everything above L1 is logically an input source — a "here is what the operator wants" pipe. If the upstream pipe is unreliable, the downstream enforcer (L0 + L1) has to fail safe.

Today L0 is solid. L1 is partially solid (boot grace + hardware timeouts inherited from L0, but no runtime watchdog and no operator-E-STOP primitive). The rebuild fills in L1. L2/L3/L4 remain "best-effort pipes" forever.

---

## Where to look first when something goes wrong

| Symptom | First place to look |
|---|---|
| Robot doesn't move at all | Robot Pi systemd journal: `journalctl -u serpent-robot-bridge -f`. Boot-grace log line will say if it's in the 2 s grace window. |
| One motor doesn't move | Robot Pi I²C scan: `i2cdetect -y 1` — confirm the right Motoron board (0x10-0x13) is responding. Check the per-board Motoron error counter in telemetry. |
| Winches don't move | Base Pi: `journalctl -u serpent-base-bridge -f` for Modbus errors. `/dev/ttyUSB0` plugged in? ESP32 status LED? Modbus slave addr set correctly (`UNIT_ID=1` or `2`)? |
| No video on Flutter | Three-hop stream: Robot Pi `VideoCapture` → Base Pi `VideoReceiver` → Base Pi `VideoHTTPServer` :5004 → `serpent_backend` :5000 `/video_feed/<id>` → Flutter `VideoFeed` widget. Test each hop with curl. |
| Flutter can't find backend | mDNS on the LAN — confirm `serpent_backend` advertises `_serpent._tcp`. Try manual IP entry from the splash screen. |
| Telemetry freezes but video keeps flowing | HaLow link carrying video fine but authenticated telemetry stream (port 5003) dropped. HMAC key mismatch after a PSK rotation? Check `/etc/serpent/psk` on both Pis. |
| Robot moved immediately at power-on | The 2 s boot grace should have blocked non-zero commands. If this happened, file a bug — that's a regression in `ActuatorController.set_motor_speed`. |
| Motor 6 (ascender) kept moving after control link died | Motoron hardware timeout on board 3 should stop it within ~1.5 s. If not, the `disable_command_timeout` regression may be back — check `tests/test_actuator_controller.py::TestMotor6HardwareTimeoutRestored`. Note: "kept moving" means still being driven by the motor. When the motor stops driving, the ascender's own mechanical grip holds the rope — the robot shouldn't be falling in any of these failure modes. If it IS falling, the problem is with the ascender hardware itself, not the software. |

---

## Companion documents

- `SYSTEM_ARCHITECTURE.md` — software architecture, event flow, timing budget.
- `ESTOP_REBUILD_PLAN.md` — design for the next iteration of the E-STOP safety layer.
- `pi_halow_bridge/PI-HALOW-BRIDGE/archive/SAFETY_AUDIT_ESTOP.md` — historical audit of why the old E-STOP was removed.
- `agent_stack/gates/safety_invariants.md` — current enforced invariants (with ✅ / PENDING REBUILD markers).

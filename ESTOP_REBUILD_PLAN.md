# E-STOP Rebuild Plan (v2 — physical-layer informed)

> **As-built note (post-R10, 2026-04-25):** the as-built E-STOP test files are `tests/test_estop.py`, `tests/test_base_pi_estop.py`, and `tests/test_estop_integration.py`. References below to `test_estop_triggers.py` reflect the original design draft — the file was renamed to `test_estop_integration.py` during R10. `test_reconnect_handshake.py` was not split out as a separate file; reconnect coverage lives inside `test_estop_integration.py`. The body of this plan is preserved verbatim as a point-in-time design record.

**Status:** Design draft, not yet approved.
**Supersedes:** removed system documented in `pi_halow_bridge/PI-HALOW-BRIDGE/archive/SAFETY_AUDIT_ESTOP.md` + removal plan `C:\Users\steyn\.claude\plans\federated-riding-summit.md`.
**Revision:** v2 — rewritten 2026-04-23 after `PHYSICAL_ARCHITECTURE.md` surfaced the firmware-vs-Pi-vs-operator layering. v1 treated E-STOP as a single motor-stop mechanism. v2 recognises that motors are already stopped by L0 firmware watchdogs and scopes the Pi-level E-STOP to what it's actually for: **state latching + cross-channel coordination**.

---

## Key insight from the physical architecture

Motors are not stopped by software. They're stopped by **Level-0 firmware** that sits between the Pi and the motor driver. Two independent firmware layers do this:

- **Motoron command watchdog** — ~1.5 s. Lives on each Motoron MCU, on the Robot Pi's I²C bus. If the Robot Pi stops writing speed commands, the Motoron itself zeroes the motor. This is the only thing stopping Motor 6 (the ascender holding the robot's weight). Restored 2026-04-23 on board 3.
- **ESP32 winch firmware watchdog** — 500 ms. Lives on the winch ESP32s, on the Base Pi's RS-485 bus. If the Base Pi stops writing HR0, the ESP32 zeroes the winch motor. Independent from the Motoron.

Both are **hardware-effective**. They keep working when the Pi is bricked, the OS panics, the Python process OOMs, or any software layer fails. They are strictly faster and more reliable than anything software can do on the Pi.

**Consequence for the rebuild:** a 5-second Pi-level watchdog timeout is not a motor-stop deadline. By the time the 5-second Pi watchdog fires, the firmware watchdogs have already been zeroing motors for 3.5 seconds (Motoron) or 4.5 seconds (ESP32). What the Pi watchdog is actually for is:

1. **State latching** — record that an anomalous condition occurred so that when commands resume, motors don't silently start moving again. The motor is stopped *right now* by firmware; the Pi's job is to make sure it stays stopped until a human intervenes.
2. **Operator notification** — surface the event in telemetry / UI so the operator knows something went wrong.
3. **Cross-channel coordination** — when one channel fails (HaLow to Robot, RS-485 to winches, or both), ensure the OTHER channel's E-STOP latches too so the operator sees a unified "everything stopped" state.

**This reframing fixes the old plan's biggest structural error**, which treated the Pi watchdog as a parallel motor-stop to the firmware watchdog. The old design had them racing each other with no clean role split; the new one makes the layering explicit.

---

## Split by power domain and by link

Three independent failure domains (from `PHYSICAL_ARCHITECTURE.md`), each with its own E-STOP reaction:

| Domain | Physical | What fails here | Who detects + latches |
|---|---|---|---|
| Robot body | Robot Pi, Motorons, 8 motors, sensors, cameras | HaLow link loss, auth failure, Pi software crash | Robot Pi watchdog + Motoron firmware (1.5 s fallback) |
| Winches (at base) | Base Pi, RS-485, 2 ESP32s, winch + tension motors | RS-485 bus fault, ESP32 firmware hang | Base Pi watchdog + ESP32 firmware (500 ms fallback) |
| Operator | TrimUI, serpent_backend, WiFi to backend | TrimUI dead, WiFi drop, backend crash | No local safety reaction possible — the Pi-side watchdogs catch it via "no control received" |

**Two independent Pi-level watchdogs, not one.** The Robot Pi's watchdog and the Base Pi's watchdog run in parallel, each watching its own link. When either fires, it tells the other via the existing telemetry stream — see §4 on cross-channel echo.

This is a real correction vs. v1. v1 assumed a single unified watchdog. In the physical topology, the winches have a completely separate command path (RS-485) that *doesn't traverse HaLow*. If HaLow dies, the winch command path is unaffected. Conversely if RS-485 dies, HaLow keeps working. Two channels, two watchdogs.

---

## Decisions summary (v2)

| # | Question | Answer | Changed from v1? |
|---|---|---|---|
| Q1 | Wire semantics | **One event `emergency_stop {engage, reason, confirm?, source?}` — SET only, never toggle.** `source` is new: `"operator"` / `"robot_watchdog"` / `"base_watchdog"` / `"firmware_winch"` so downstream can reason about who-said-what. | Added `source` |
| Q2 | Boot latch policy | **Hard latch on both Pis. `SERPENT_DEV_MODE=1` env var skips.** Robot Pi and Base Pi each boot with their own E-STOP engaged. | Added Base-Pi side |
| Q3 | Watchdog scope | **Two Pi-level watchdogs (Robot + Base), each monitoring their own link. Both hybrid: distributed fast-engage on errors + single background thread for silent-link timeout.** | Split into two watchdogs |
| Q4 | Reconnect handshake | **Robot is authoritative for on-robot state; Base Pi is authoritative for winch state. Each stamps its authoritative status into the telemetry stream it owns. Upstream layers adopt, never re-emit.** | Split into two authorities |
| Q5 | Cross-channel echo | **NEW v2:** if one authority engages, the other adopts within one telemetry cycle (~100 ms). Operator-initiated engage goes to both simultaneously, not sequentially. | New question |
| Q6 | Clear authorization | **NEW v2:** engage is permissive (any LAN source); clear requires confirm string + fresh HaLow control + operator-hold proof. Asymmetric, fail-safe direction is cheap, fail-unsafe direction is expensive. | New question |
| Q7 | Tests | Reuse `test_estop.py` / `test_estop_triggers.py`; add `test_base_pi_estop.py` for the new winch-side watchdog; keep `test_framing.py` and `test_actuator_controller.py`. | Added winch-side test |

**Three decisions still need your sign-off:** Q2 (hard-latch?), Q2b (persist state across reboots?), Q6 (require operator-hold proof on clear?).

---

## Architecture (v2)

```
  ┌──────────────────────┐
  │ Flutter TrimUI       │
  │                      │
  │  displays:           │
  │  - robot_estop       │ ◄─ from telemetry (Robot Pi authoritative)
  │  - winch_estop       │ ◄─ from telemetry (Base Pi authoritative)
  │                      │
  │  emits:              │
  │  - emergency_stop    │ ─► both engage paths simultaneously
  └──────────┬───────────┘
             │ Socket.IO :5000 (LAN-trusted, asymmetric auth — see Q6)
             ▼
  ┌──────────────────────┐
  │ serpent_backend      │ ── passes through verbatim; no local state
  └──────────┬───────────┘
             │ localhost Socket.IO :5000
             ▼
  ┌────────────────────────────────────────────────────────────────┐
  │ Base Pi                                                         │
  │                                                                 │
  │  BackendClient                                                  │
  │    ├─ on emergency_stop(engage, reason) ─►                      │
  │    │    │                                                       │
  │    │    ├─ forward to Robot Pi via HaLow (HMAC)                │
  │    │    │                                                       │
  │    │    └─ also apply to local WinchController ◄── cross-channel
  │    │                                                            │
  │  WinchController                                                │
  │    ├─ _winch_estop_engaged (boot=True) ◄── SI-1 Base-side     │
  │    ├─ engage_winch_estop(reason)                                │
  │    ├─ clear_winch_estop(confirm, ...)                          │
  │    └─ atomic check-and-actuate under _lock (SI-7)              │
  │                                                                 │
  │  BaseWatchdog                                                   │
  │    ├─ 5 s timeout on RS-485 freshness ─► engage_winch_estop     │
  │    ├─ 5 s timeout on HaLow telemetry ─► engage_winch_estop      │
  │    │   (because if we can't hear the robot, we might be isolated;
  │    │    fail-safe is to stop winches too)                        │
  │    └─ telemetry subscriber: if robot_estop changes ─► mirror    │
  │                                                                 │
  │  TelemetrySender (upstream — aggregates winch + robot status)   │
  │    └─ includes winch_estop {engaged, reason} authoritatively    │
  │    └─ passes through robot_estop from Robot Pi untouched        │
  └──────────┬──────────────────────────────┬───────────────────────┘
             │ HaLow TCP 5001 (HMAC)        │ RS-485 Modbus @ 250 kbps
             │ control + telemetry          │
             ▼                              ▼
  ┌──────────────────────┐        ┌──────────────────────┐
  │ Robot Pi             │        │ 2 × Winch ESP32      │
  │                      │        │                      │
  │ ControlServer        │        │ firmware 500 ms      │
  │  ├─ HMAC+seq         │        │ watchdog (SI-8)      │
  │  └─ on auth error ─► │        │  ├─ stale HR0 → 0    │
  │     engage_estop     │        │  └─ STATUS_WATCHDOG  │
  │                      │        │                      │
  │ CommandExecutor      │        │ Motoron registers ─► │
  │  └─ emergency_stop ─►│        │ winch + 2 tension    │
  │     actuator_ctrl    │        │ motors               │
  │                      │        └──────────────────────┘
  │ ActuatorController   │
  │  ├─ _estop_engaged   │ ◄── SI-1 (Robot-side)
  │  │  (boot=True)      │
  │  ├─ engage_estop()   │
  │  ├─ clear_estop()    │
  │  └─ atomic lock (SI-7)
  │                      │
  │ RobotWatchdog        │
  │  ├─ 5 s control_age ─► engage_estop("watchdog")
  │  ├─ startup grace 30s│
  │  └─ fast-engage on   │
  │     control_server   │
  │     exception branches│
  │                      │
  │ TelemetrySender ────►│ stamps robot_estop authoritatively
  │                      │
  │ Motoron boards ──────┼─► motor_controller firmware ~1.5 s WDT
  │ (I²C)                │   (SI-8-adjacent, per-board hardware stop)
  └──────────────────────┘
```

**Three authorities, three domains, three independent fail-safes:**

1. **Robot Pi `ActuatorController`** is authoritative for the 8 on-robot motors + the clamp servo. Its E-STOP state is mirrored into telemetry.
2. **Base Pi `WinchController`** is authoritative for the 2 winches. Its E-STOP state is mirrored into telemetry.
3. **Firmware on Motorons + ESP32s** is the always-on fail-safe that doesn't depend on Pi software being alive. Neither Pi authority can turn these off.

---

## Q1 — Wire semantics

**Single event, same structure on every hop:**

```json
{
  "type": "emergency_stop",
  "data": {
    "engage": true,
    "reason": "operator_command",
    "confirm": "CLEAR_ESTOP",
    "source": "operator",
    "ts_ms": 1729012345000
  }
}
```

Rules:
- Legacy `emergency_toggle` (no payload) is **rejected** — log, drop, do not translate.
- `engage=false` requires `confirm == "CLEAR_ESTOP"` exact match. Defined once in `common/constants.py`.
- `source` string: `"operator"` (human pressed the button), `"robot_watchdog"`, `"base_watchdog"`, `"firmware_winch"`, `"boot_default"`, `"auth_failure"`, `"replay_attack"`, `"disconnect"`, `"internal_error"`. Everyone logs and can reason about who said what.

**Target behavior by source:**

| Source of engage | Applied to Robot Pi? | Applied to Base Pi winches? |
|---|---|---|
| `operator` | Yes | Yes (simultaneous) |
| `robot_watchdog` | Yes (self) | Yes (via cross-channel echo, ~100 ms later) |
| `base_watchdog` | Yes (via cross-channel echo) | Yes (self) |
| `auth_failure` / `replay_attack` (on Robot control channel) | Yes | Yes (cross-channel — if attacker in-link, assume winches also compromised) |
| `firmware_winch` (reported via ESP32 STATUS_WATCHDOG bit) | Yes (cross-channel) | Yes (already stopped by firmware) |

The cross-channel echo is the v2 improvement. In v1, if the robot watchdog fired, only the robot engaged. If RS-485 happened to still work, the winches would keep spinning. That's a real failure mode — operator sees "EMERGENCY STOP" overlay and assumes everything stopped, but the winches haven't. v2 makes every engage unified at the `ActuatorController` + `WinchController` level, regardless of which side detected it.

---

## Q2 — Boot latch ⚠ (your call)

**Chosen: soft-latch with persistent state** (Q2 = B, Q2b = B). Neither Pi boots engaged *by default* — the 2-second startup grace handles the narrow boot-time window where a stale command could arrive. But last-known state IS restored from disk, so a Pi that was engaged when it went down comes back up engaged with the same reason. First-ever boot = cleared.

**`SERPENT_DEV_MODE=1`** env var in both `serpent-robot-bridge.service` and `serpent-base-bridge.service` skips the boot latch for bench work. Production systemd units must not set it.

**Q2b — persistence across reboot:** if the Pi reboots mid-engage (power blip, kernel panic), does it come back engaged or default-engaged? Two flavors:

- **Default-engaged** (simpler): every boot starts from the same state. Operator must clear. Natural consequence: boot = reset, and "engaged" is never "persisted" across restarts, it's just always the initial state.
- **Persistent** (stronger): the last engage reason is written to `/var/lib/serpent/estop_state` and read at boot. If the last-known state was "engaged by operator_command", the Pi comes up engaged with that specific reason. If last-known was "cleared normally", same default-engaged behavior. Prevents a sneaky bug where "reboot clears E-STOP".

Your call. Recommend **default-engaged** — simpler, and hard-latch already ensures boot never silently comes up actuating. Persistence adds an on-disk write path that itself needs SI-gate review.

---

## Q3 — Watchdog scope (two watchdogs, not one)

**Robot Pi watchdog** — new `robot_pi/core/watchdog_monitor.py` (rewritten from the deleted version):
- 10 Hz tick
- Engages `robot_estop` with `reason="watchdog_timeout"` if `control_age > 5 s` after startup grace (30 s)
- Fast-engage points (distributed): `control_server.py` exception branches call `on_estop_trigger` with specific reasons (`auth_failure`, `replay_attack`, `disconnect`, `decode_error`) before `close_client()`

> **Important — watchdog semantic is link-fresh, NOT operator-fresh.** `control_age` is updated by the Robot Pi's `ControlServer` whenever any authenticated frame arrives — including `MSG_PING` heartbeats that the Base Pi's `bridge_coordinator` sends every 200 ms (`HEARTBEAT_INTERVAL_S`) independently of Flutter. Operator idling on the joystick does not starve the watchdog; only a broken HaLow link, a dead Base Pi, or a failed auth does. The rebuild must preserve this decoupling — do NOT tie heartbeats to operator input events. If anyone introduces a PR that replaces the heartbeat with "only send when the operator does something," the watchdog becomes operator-fresh and the 5 s threshold becomes hostile to normal work.

### Pre-watchdog "degraded link" UI indicator

A 5-second silent gap → instant E-STOP engage is harsh if the operator never sees it coming. To soften this without weakening the watchdog, surface link health *before* the 5-second threshold is hit:

- Robot Pi already stamps `control_age_ms` into every telemetry frame (`bridge_coordinator.py` has this today).
- Flutter / dashboard read `control_age_ms` and render a banner when the age crosses an early threshold:

| `control_age_ms` | UI |
|---|---|
| < 1000 | no banner (healthy) |
| 1000 – 2500 | small info pill: `link jitter ({age} ms)` |
| 2500 – 5000 | **orange banner: "LINK DEGRADED — E-STOP will engage in {5000 – age} ms"** |
| ≥ 5000 | (watchdog has fired; red E-STOP overlay takes over) |

The orange banner gives the operator ~2.5 seconds of warning before E-STOP engages. In practice this is enough time to see "reposition the HaLow antenna" or "step closer" and act on it, rather than being surprised by the full red E-STOP overlay with no preamble.

No change to the watchdog itself — it still engages at 5 s. The banner is pure UI, fed from telemetry the Robot Pi already stamps. It lives alongside (not inside) the E-STOP state machine — it's an operator-awareness tool, not a safety interlock.

Fold into milestone **R9** (Flutter UI) plus a small widget update to the Base Pi dashboard so browser-dashboard operators see the same indicator.

**Base Pi watchdog** — new `base_pi/core/base_watchdog.py` (never existed in v1):
- 10 Hz tick
- Engages `winch_estop` with `reason="rs485_timeout"` if RS-485 Modbus poll fails for >5 s (no response from ESP32)
- Engages `winch_estop` with `reason="halow_silent"` if no telemetry from Robot Pi for >5 s (isolated from robot → fail safe on winches too)
- Fast-engage points: `winch_controller.py` exception branches on Modbus read failures
- Telemetry subscriber: if incoming telemetry reports `robot_estop.engaged=true`, mirror into `winch_estop` within one tick

**Why 5 s instead of firmware-like 500 ms:** the firmware watchdogs already catch fast failures. 5 s is the human-observable threshold (operator notices "it's not moving" within 2-3 seconds; by 5 s we want the state latched so resume doesn't happen silently). Matching the firmware timer would be wasteful — motors already zero at 500 ms / 1.5 s from the firmware side.

---

## Q4 — Reconnect handshake (split authorities)

Two authorities, two stamps in telemetry:

```json
{
  "type": "telemetry",
  "robot_estop": {
    "engaged": true,
    "reason": "boot_default",
    "source": "boot",
    "engaged_at_ms": 1729012345000
  },
  "winch_estop": {
    "engaged": true,
    "reason": "boot_default",
    "source": "boot",
    "engaged_at_ms": 1729012345000
  },
  ...
}
```

- `robot_estop` is filled by the Robot Pi (authoritative for 8 motors).
- `winch_estop` is filled by the Base Pi (authoritative for 2 winches), AFTER it passes the robot_estop through unchanged.
- Flutter's `BackendService` reads both, updates two getters, renders two overlays (or one if they match).

**Reconnect semantics:**
- On HaLow reconnect (Base Pi's `ControlForwarder` reconnects to Robot Pi): Robot Pi's next telemetry frame stamps `robot_estop` authoritatively. Base Pi adopts.
- On RS-485 recovery (Base Pi regains winch poll success after an outage): Base Pi reads ESP32 IR8 STATUS flags; if STATUS_WATCHDOG was raised during the outage, Base Pi keeps `winch_estop` engaged. Operator must explicitly clear.
- On Socket.IO reconnect (Flutter reconnects to backend): Flutter drops its local cached `emergencyStop` state and waits for the next telemetry frame from the Base Pi, which carries both authoritative stamps. Flutter never displays its own cached state during the reconnection gap — it displays "state unknown" (or the overlay defaults to engaged for UI safety).

---

## Q5 — Cross-channel echo (new in v2, BIDIRECTIONAL)

When one authority engages, the other follows within one tick (~100 ms). **Mirroring is bidirectional** (v2.1 correction — v2 had this as one-way).

```
operator presses Y on TrimUI
    │
    ▼
Flutter emits emergency_stop {engage: true, source: "operator"}
    │
    ▼
Base Pi BackendClient receives
    │
    ├─► forwards to Robot Pi over HaLow  ──► Robot Pi engages robot_estop
    │
    └─► locally calls WinchController.engage_winch_estop("operator")
```

If the HaLow link is dead the moment the operator presses, the local winch engagement still happens. Worst case: robot doesn't hear the command, but the Motoron watchdog (1.5 s) catches it anyway because the Base Pi's `ControlForwarder` is no longer sending heartbeats. Winches stop via Base Pi local action + ESP32 firmware watchdog as belt-and-braces.

### Mirroring rules (both directions)

- **Robot → Winch:** if the Robot Pi's telemetry reports `robot_estop.engaged=true` and the Base Pi's last-mirrored source was different (or `None`), the Base Pi engages `winch_estop` with `reason="robot_mirror"` and `source="robot_watchdog"` (or whatever upstream reason was). Motivation: if the robot watchdog fires, the operator has lost their link — winches should not keep paying out rope.
- **Winch → Robot:** if the Base Pi's `winch_estop` engages (from local watchdog or RS-485 fault) and the Robot Pi is reachable, the Base Pi forwards an authenticated `emergency_stop {engage: true, source: "winch_mirror"}` over HaLow. Motivation: if rope tension management has stopped, the robot should not keep climbing.

### Feedback-loop prevention

Each authority tracks `_last_mirrored_from: Optional[str]` — the source of the most recent state change that was *mirrored in* from the other side. When a mirror arrives:

- If `state == current state`: no-op (idempotent).
- If the mirror's source was our own most recent outgoing change: drop (don't re-engage ourselves).
- Otherwise: apply the mirror, record `_last_mirrored_from`.

Clears do **not** cross-echo — only engages. Clears are operator-initiated actions that go to both authorities via the operator's single `emergency_stop {engage: false}` message, not via mirror. This prevents the ping-pong where Robot clears → Base mirrors clear → Robot sees clear-from-base-mirror and re-interprets etc.

### Reconnect-storm protection

On HaLow reconnect, the Robot Pi re-stamps `robot_estop` in the next telemetry frame. The Base Pi's mirror logic must not treat each reconnect as a fresh engage event (otherwise flaky HaLow → winches engage-clear-engage-clear). The rule:

- Track `_last_seen_robot_estop_generation: int` — increments only when Robot Pi records a genuine state transition, not on every telemetry tick.
- Or simpler: only mirror when `robot_estop.engaged` *transitions* (was False, now True). Static re-reads are ignored.

### Atomic clear across both authorities (two-phase)

Engage echoes across authorities asymmetrically (mirror logic above). **Clear does not echo — but it DOES need to be atomic across both.** If the operator clears and one authority succeeds while the other fails, the system ends up in a split state (robot cleared, winch still engaged) which is confusing and unsafe.

Protocol:

1. Operator's single `emergency_stop {engage: false, confirm: "CLEAR_ESTOP"}` arrives at the Base Pi BackendClient.
2. BackendClient forwards to Robot Pi over HaLow AND calls `WinchController.clear_winch_estop()` locally, in parallel. Each returns `(ok: bool, reason_if_fail: str)`.
3. **If both succeed:** state flows out via telemetry as normal, UI shows cleared. Done.
4. **If either fails:** the succeeded side is rolled back. Specifically:
   - If Robot cleared but Winch failed: Base Pi immediately re-engages Winch (it's already engaged; this is a no-op) **and** sends `emergency_stop {engage: true, reason: "clear_partial_failure", source: "base_rollback"}` back to the Robot Pi to re-engage it. The robot ends up re-engaged with a reason field the UI can explain.
   - If Winch cleared but Robot failed (HaLow error, auth failure on the clear frame): Base Pi immediately re-engages Winch locally and reports `"clear_partial_failure"` via telemetry.
5. The UI shows `CLEAR PARTIAL — ROBOT ✗ (reason: ...), WINCH ✓ (rolled back)` or similar. Operator knows exactly what to fix before trying again.

This is effectively a two-phase commit (prepare-both → either both-commit-or-both-rollback). The common case (both succeed) is the fast path. The failure-rollback path is additional complexity worth carrying — without it, "clear only partially worked" is a state the operator has no good model for.

Add to `tests/test_estop_triggers.py` the split-success scenarios:
- `test_clear_robot_ok_winch_fails_reengages_both`
- `test_clear_winch_ok_robot_fails_reengages_both`

---

## Q6 — Clear authorization (new in v2)

**Engage is permissive** — anyone on the LAN who can emit to `serpent_backend` can force-engage E-STOP. That's fine: engaging is always fail-safe. We actively want "low friction to stop."

**Clear is strict** — three independent checks, ALL required:

1. **Confirm string** — `confirm == "CLEAR_ESTOP"`. This is not secret (it's in the code), so it's not an access gate. It's a "you must know you're doing this" gate.
2. **Fresh HaLow control** — `control_age_s <= 1.5 s` on the Robot Pi side. Means the legitimate operator is actively driving *right now*. An attacker who has LAN access but isn't actually in the operator's chair can't clear.
3. **Operator-hold proof** — (optional, see below) a short-lived token (valid ~500 ms) that the Flutter app generates only when the Y button has actually been held for 5 seconds. The token is a HMAC (different PSK) over `{nonce, ts_ms}` generated by Flutter and forwarded along with the clear. Without this, an attacker with LAN access during an active operator session could still race a silent clear.

**Q6 is your call:** is #3 worth implementing, or does #2 (fresh control) cover the threat model adequately?

Arguments for #3:
- Tight threat model: worst-case is a LAN-attacker issuing a silent clear during an operator-engaged E-STOP, which could enable a continued-motion attack.
- The operator-hold proof is tied to physical UI state. Can't be spoofed without compromising the TrimUI device.

Arguments against #3:
- Requires a second PSK on the TrimUI (violates the "no durable crypto on handheld" stance from `SYSTEM_ARCHITECTURE.md §5.3`).
- Complexity cost; one more thing to debug when clear doesn't work.
- #2 (fresh control) already requires the attacker to time their inject during a tiny operator-active + engaged window.

Recommend: **skip #3 for v1 of the rebuild; add if a real field incident motivates it.** Ship with #1 + #2, document the threat model.

---

## Invariants rebuilt (mapped to physical layers)

| # | Invariant | Robot Pi site | Base Pi site |
|---|---|---|---|
| SI-1 | Startup-safe actuation (soft-latch + persistent state per Q2/Q2b) | `ActuatorController.__init__` reads `/var/lib/serpent/robot_estop_state.json`; `set_motor_speed` enforces the 2 s startup grace that's already there | `WinchController.__init__` reads `/var/lib/serpent/winch_estop_state.json`; 2 s startup grace on the Base side too |
| SI-2 | Watchdog 5 s + 30 s grace | `robot_pi/core/watchdog_monitor.py` | `base_pi/core/base_watchdog.py` (new in v2) |
| SI-3 | SET semantics | `command_executor._handle_emergency_stop` | `backend_client` + `bridge_coordinator` |
| SI-6 | Crash/disconnect = E-STOP | `control_server` exception branches | `winch_controller` RS-485 error branches (new in v2) |
| SI-7 | TOCTOU-safe actuation | `ActuatorController._lock` wraps check + hw write | `WinchController._lock` wraps check + Modbus write (new in v2) |

SI-4 (HMAC), SI-5 (control>video), SI-8 (firmware WDT), SI-9 (buffer bounds), SI-10 (SIM_MODE), SI-11 (Modbus contract), SI-12 (PSK) are unchanged.

---

## Milestones (v2 — ~2.5 days focused work)

Each independently mergeable.

| # | Milestone | Files | Effort | safety-gate? |
|---|---|---|---|---|
| R0 | Re-add E-STOP constants | `common/constants.py` — `ESTOP_REASON_*`, `ESTOP_CLEAR_CONFIRM`, `ESTOP_CLEAR_MAX_AGE_S`, `WATCHDOG_TIMEOUT_S`, `STARTUP_GRACE_S`, `MSG_EMERGENCY_STOP` | XS | yes |
| **R1** | **Robot-side ActuatorController state machine** | `robot_pi/actuator_controller.py` — flag, lock, engage/clear, boot latch, atomic actuation, **plus `_estop_history` ring buffer** (last 100 transitions: `{engaged, reason, source, ts_ms}`) + `get_estop_history()` + `get_estop_info()` methods. Needed for post-incident reconstruction. | M | yes |
| **R1b** | **Base-side WinchController state machine (NEW in v2)** | `base_pi/winch_controller.py` — mirror of R1 for winches, **including its own `_estop_history` ring buffer**. | M | yes |
| R2 | Unit tests for R1 + R1b | `tests/test_estop.py` (robot), `tests/test_base_pi_estop.py` (winch) | S | no |
| **R3** | **Robot watchdog** | `robot_pi/core/watchdog_monitor.py` | S | yes |
| **R3b** | **Base watchdog (NEW in v2)** | `base_pi/core/base_watchdog.py` — RS-485 + HaLow-telemetry subscribers | S | yes |
| R4 | Robot command-executor E-STOP handler | `robot_pi/core/command_executor.py` | S | yes |
| R4b | Base-side `emergency_stop` handler | `base_pi/core/backend_client.py`, `base_pi/core/bridge_coordinator.py` — forwards to Robot Pi AND locally engages WinchController | S | yes |
| R5 | ControlServer distributed fast-engage | `robot_pi/control/control_server.py` | S | yes |
| **R6** | **Telemetry two-stamp authoritative status** | `robot_pi/telemetry/telemetry_sender.py` (stamps `robot_estop`); `base_pi/telemetry_receiver.py` + `base_pi/core/bridge_coordinator.py` (forwards robot_estop + stamps `winch_estop`) | S | no |
| R7 | Cross-channel echo subscriber on Base Pi | `base_pi/core/base_watchdog.py` or similar — mirror `robot_estop` into `winch_estop` on incoming telemetry | XS | yes |
| R8 | serpent_backend relay | `pi_backend/server.py` — verbatim relay, no local state | XS | no |
| R9 | Flutter UI + dashboard UI | **Flutter:** `lib/services/backend_service.dart` — `robotEstop` + `winchEstop` getters (read from telemetry, never emit from telemetry), plus `controlAgeMs` getter for the degraded-link indicator, plus a client-side "NO TELEMETRY" timeout (grey banner if no telemetry frame received for >3 s — separate from the orange "LINK DEGRADED" banner since if telemetry stops entirely, `controlAgeMs` becomes stale). `sendEngage()` / `sendClear()` methods emit canonical `emergency_stop` events. `lib/screens/main_screen.dart` — Y-press engage + 5 s hold clear + unified E-STOP overlay (engaged domains listed in detail panel) + orange "LINK DEGRADED" banner when `controlAgeMs` ∈ [2500, 5000) + grey "NO TELEMETRY" banner on client-side timeout. **Dashboard:** reinstate `/api/estop/engage`, `/api/estop/clear`, and **`/api/estop/history`** endpoints in `dashboard/web_server.py`. Engage/clear route through `socketio.emit('emergency_stop', ...)` (same relay Flutter uses), NOT direct in-process calls. History endpoint returns the last N entries from the authoritative `ActuatorController._estop_history` + `WinchController._estop_history` (JSON). Dashboard widget shows the same degraded-link + no-telemetry banners Flutter does. Dashboard clear UX must also require a deliberate act (5-second press-and-hold with progress bar, or typing `CLEAR_ESTOP` in a confirm field) — not a one-click button. | M | no |
| R10 | Integration test | `tests/test_estop_triggers.py` (SIM_MODE), `tests/test_reconnect_handshake.py` (new) | M | no |
| R11 | Doc refresh | `safety_invariants.md` → flip SI-1/2/3/6/7 back to ✅, update banners in READMEs, add new §5 to `SYSTEM_ARCHITECTURE.md` | S | yes (gate edit) |

Total milestones: **14** (was 11 in v1, 3 new: R1b, R3b, R7). Net effort estimate: **~2.5 days** of focused work, + field testing.

---

## Physical deployment checklist (new in v2)

Before any new version of the E-STOP system is trusted in field, the following **physical** items must be verified, independently from the software:

1. **Ascender mechanical integrity.** The ascender (Motor 6's load) is a mechanical one-way rope-grip device — the motor drives its input gear, but the rope-hold is geometric, not torque-based. So instantaneous battery loss is *not* a fall hazard: motor stops driving, ascender keeps gripping, robot stops in place. This is much better safety behaviour than a torque-based hold would be. **What this checklist item is actually checking** is the mechanical integrity of the ascender itself (cam wear, spring fatigue, gearbox play) — if that fails, no electrical layer can help. Standard pre-deployment mechanical inspection (visual + load test) is the mitigation here, same as any rope-rated hardware.
2. **Winch-station power isolation.** Verify the winch ESP32s are on their own power rail, independent from the Base Pi. If they share the Base Pi's supply, a Base Pi brown-out takes out both simultaneously and the ESP32 firmware watchdog never fires (because ESP32 is also dead).
3. **HaLow link distance validation.** E-STOP depends on HaLow being at most 5 seconds silent before the Robot-Pi watchdog engages. If field distances push HaLow to the edge of its range, occasional blackouts > 5 s become expected, meaning E-STOP would engage frequently and operators would start clearing it reflexively (dulling the safety signal). Field-test HaLow margin before every deployment.
4. **Operator-hold safety culture.** The Y-button 5-second hold is a UX convention, not enforced by hardware. The operator has to actually complete the hold without accidentally pressing something else. Document this in any pre-flight checklist.
5. **Motor 7 (traverse) passive-lock verification.** Motor 6 (ascender) is known to drive a mechanical one-way grip — power loss doesn't drop the robot. **Verify whether Motor 7 has the same property.** If the traverse drive is a similar worm-gear / cam-lock arrangement, losing power mid-traverse holds position. If it's a direct gearbox that can free-wheel backwards under side load, losing power could cause the robot to swing along its traverse cable. This is a physical-hardware inspection, not software.

These are not code milestones. They are **pre-conditions for the rebuild to actually be safe in the real world.** The code changes can ship without them, but field-use cannot.

### Operational behaviour worth knowing

Things that are correct by design but will surprise operators if not documented:

- **`systemctl restart serpent-base-bridge` = 5-second E-STOP cycle.** Any restart of the Base Pi bridge (config change, software update, debugging) kills the HaLow heartbeat for 2-3 seconds. The Robot Pi's watchdog fires at 5 s, engaging E-STOP. Operator has to clear after every restart. This is correct fail-safe behaviour — the bridge restarting is indistinguishable, from the Robot Pi's perspective, from a genuine link failure — but in practice it means "every config change costs an E-STOP cycle." Plan for it in ops workflows; don't try to suppress it in code (that would defeat the watchdog).
- **Same applies to `systemctl restart serpent-robot-bridge`.** Bridge dies → no telemetry → Base Pi's own watchdog fires → winch E-STOP engages. On restart the Robot Pi comes up hard-latched (SI-1) and needs operator clear anyway.
- **Both Pis come up E-STOP-engaged on every boot.** First operator action of every session is a deliberate clear. Feature, not bug.

---

## What the rebuild does NOT protect against

Worth naming explicitly so no one misreads the coverage:

- **Instantaneous Robot-body power loss.** Battery disconnect, fuse blow, short circuit. Nothing software or firmware can do. Only a mechanical brake helps.
- **Mechanical failures.** Rope break, clamp failure, gearbox strip. E-STOP cannot prevent any of these; it can only react after the fact (and only if the robot is still powered).
- **Operator error during active control.** If the operator is mid-cut and slips the wrong button, the robot obediently executes. E-STOP is a separate primitive, not a general "undo."
- **Watchdog false-negatives in a degraded mode.** If HaLow is flapping (1-2 s outages), the watchdog's 5 s threshold may never trigger — the system is technically healthy by its own metric but the operator is definitely not in control. Telemetry + UI should surface "link quality degraded" as a distinct alert.
- **Persistent-state tampering.** If Q2b is implemented with on-disk persistence, anyone with root on the Pi could hand-edit `/var/lib/serpent/estop_state`. This is the usual "root = everything" caveat and is not the E-STOP system's job to defend.

---

## Decisions (resolved)

| # | Question | Decision |
|---|---|---|
| Q2 | Hard-latch or soft-latch at boot? | ✅ **Soft-latch.** No hard boot-engage. The 2-second `STARTUP_DELAY_S` grace in `ActuatorController.set_motor_speed` is the boot-time protection. |
| Q2b | Persist E-STOP state across reboots? | ✅ **Yes — properly integrated.** Last-known state written to disk on every transition; restored at boot. If engaged when the Pi went down, it comes up engaged with the reason preserved. |
| Q6 | Operator-hold proof token for clear? | ✅ **Skip.** The three existing checks (confirm string + fresh control + control connected) are enough under the LAN-trusted threat model. |
| Q8 | Dashboard E-STOP path | ✅ **Socket.IO relay** (same as Flutter) — not in-process calls |
| Q9 | Degraded-link UI banner before 5 s watchdog | ✅ Add in R9 — orange banner at `control_age` ∈ [2.5, 5.0 s] |

### How Q2 + Q2b combine

Boot-time behaviour is determined by the on-disk state file plus the 2-second grace:

| Previous shutdown state | State file contents | Boot behaviour |
|---|---|---|
| First-ever boot (fresh install) | file doesn't exist | `_estop_engaged = False`, 2 s grace refuses non-zero commands for first 2 s |
| Shutdown while cleared | `{engaged: false, ...}` | `_estop_engaged = False`, 2 s grace applies |
| Shutdown while engaged (any reason) | `{engaged: true, reason: ..., ...}` | `_estop_engaged = True`, reason preserved, motors refused until operator clears |
| State file corrupt / permission error | invalid JSON | `_estop_engaged = False` (safe default per Q2), WARN logged, original file renamed to `.corrupt` for forensics |

### "Properly integrated" requirements for persistence

State file location: `/var/lib/serpent/robot_estop_state.json` (Robot Pi), `/var/lib/serpent/winch_estop_state.json` (Base Pi). `StateDirectory=serpent` added to both systemd units.

Schema (v1):
```json
{
  "version": 1,
  "engaged": true,
  "reason": "watchdog_timeout",
  "source": "robot_watchdog",
  "engaged_at_ms": 1729012345000,
  "last_written_at_ms": 1729012345123
}
```

Write path (atomic):
1. Serialize dict to JSON string.
2. Write to `<path>.tmp` (same directory, same filesystem for `os.replace` atomicity).
3. `f.flush()` then `os.fsync(f.fileno())`.
4. `os.replace(<path>.tmp, <path>)` — atomic rename on POSIX.
5. `os.fsync(dir_fd)` on the parent directory (optional but safest).

Read path (tolerant):
- File doesn't exist → return default `{engaged: False}`. No WARN (expected on first boot).
- JSON decode error → log WARN, rename file to `<path>.corrupt.<ts>`, return default.
- Schema version mismatch → log WARN, same treatment.
- Permission error → log ERROR, return default.
- Valid: return the dict verbatim for construction.

Write triggers: **every state transition** in `engage_estop()` and `clear_estop()`. Also `_estop_history` ring-buffer writes do NOT trigger a disk write (they're in-memory only — the persistent state is just the current head of the state machine, not the audit trail).

Implementation: both `ActuatorController` (robot) and `WinchController` (base) get the same treatment. Tests cover: fresh boot / normal engage-persist-reboot-restored / clear-persist-reboot-restored / corrupted file / permission denied / schema mismatch.

---

## What's deliberately out of scope

- **No TLS on the Flutter↔backend hop.** LAN-trust model stays (`SYSTEM_ARCHITECTURE.md §5.3`).
- **No PSK rotation.** User policy: LAN is trusted.
- **No additional invariants** beyond SI-1/2/3/6/7 restoration (plus their Base-Pi mirrors).
- **No mechanical brake design** for Motor 6 — flagged as a physical-side prerequisite; the rebuild cannot substitute for it.
- **No Flutter dep upgrade.**

---

## Companion documents

- `SYSTEM_ARCHITECTURE.md` — software architecture, event flow, timing budget.
- `PHYSICAL_ARCHITECTURE.md` — hardware, compute levels, interconnects, power domains. **Source of the v2 insights.**
- `pi_halow_bridge/PI-HALOW-BRIDGE/archive/SAFETY_AUDIT_ESTOP.md` — audit of why the old E-STOP was removed.
- `agent_stack/audits/2026-04-23-audit-findings.md` — broader audit findings (non-E-STOP).
- `ESTOP_BENCH_TEST.md` — bench-test procedure for verifying R0-R10 behaviour without HaLow / wireless link.
- `agent_stack/gates/safety_invariants.md` — current enforced invariants (flip back to ✅ after R11).

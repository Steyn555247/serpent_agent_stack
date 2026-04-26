# E-STOP Bench Test Runbook

> Walk-through for validating the E-STOP rebuild (R0–R11 + wiring fixes) on real hardware. Print this, sign it, keep it in the project folder.
>
> **Tester:** _____________ &nbsp;&nbsp; **Date:** _____________ &nbsp;&nbsp; **Pi pair S/N:** _____________
>
> Walk the sections in order. Don't skip ahead — later tests assume earlier ones passed. If a check fails, **stop**, mark it FAIL, note what you saw, and don't proceed until it's fixed.

---

## 0. Before you start

### 0.1 What you need

- Both Pis powered, on the HaLow network, with PSKs configured.
- `server.py` running on the Hub Pi (or whatever runs the backend).
- TrimUI handheld with the latest Flutter APK installed.
- Two SSH terminals open: one to Robot Pi, one to Base Pi.
- A spare keyboard or operator next to the rope-grip ascender — physical safety stays primary; this E-STOP is software backup.
- Watch / phone timer.

### 0.2 Stop conditions

**Halt the test session immediately** if any of these happen:

- Motors run for more than 1 second after E-STOP engaged.
- Operator clears E-STOP and motors do NOT resume within 2 s.
- Either Pi crashes or `serpent-{robot,base}-bridge.service` enters `failed` state.
- The robot drops on the rope (mechanical ascender failure — unrelated to this test, but stop and inspect).
- Any unexpected motor twitch during boot or while idle.

### 0.3 What to record

For every test, write down:

- **Pass/Fail** checkbox.
- **Time-to-engage / time-to-clear** in milliseconds where the test asks.
- Anything weird you saw, even if the test "passed".
- Exact log line or screenshot if anything red appears.

---

## 1. Deployment pre-flight

> One-time before the first test. Skip if already deployed since the wiring fixes (2026-04-25 commit).

### 1.1 Verify the right code is on the Pis

On **Robot Pi**:

```bash
cd ~/PI-HALOW-BRIDGE
git log --oneline -5
grep -n "watchdog_monitor.start" robot_pi/core/bridge_coordinator.py
grep -n "on_estop_trigger=self._on_control_server_estop" robot_pi/core/bridge_coordinator.py
```

Expected: both `grep` lines return a match. If they don't, the wiring fixes weren't deployed.

On **Base Pi**:

```bash
cd ~/PI-HALOW-BRIDGE
grep -n "BaseWatchdog" base_pi/core/bridge_coordinator.py
grep -n "_get_rs485_age_s\|_get_halow_age_s" base_pi/core/bridge_coordinator.py
```

Expected: at least 2 matches per grep.

| ☐ | 1.1 right code on both Pis |

### 1.2 systemd service files have StateDirectory

On both Pis:

```bash
sudo systemctl cat serpent-robot-bridge serpent-base-bridge 2>/dev/null | grep -E "StateDirectory|ReadWritePaths"
```

Expected: each service shows `StateDirectory=serpent` AND `ReadWritePaths` containing `/var/lib/serpent`.

If missing, copy the unit file from the repo and `sudo systemctl daemon-reload`.

| ☐ | 1.2 StateDirectory present on both services |

### 1.3 `/var/lib/serpent/` exists with right ownership

On both Pis:

```bash
ls -la /var/lib/serpent/
```

Expected: directory exists, owned by `serpentbase:serpentbase` (or whatever User= in your service), mode `0750` or `0755`.

If empty, that's fine — files are created on first transition.
If missing, restart the service: `sudo systemctl restart serpent-robot-bridge` (or base) — `StateDirectory=` creates it.
If owned by `root`, the service `User=` doesn't match — fix the unit file before continuing.

| ☐ | 1.3 /var/lib/serpent exists, correct owner |

### 1.4 PSK is configured

On both Pis:

```bash
sudo systemctl show serpent-robot-bridge -p Environment | grep -i psk || echo "NO PSK in main env"
sudo cat /etc/systemd/system/serpent-robot-bridge.service.d/*.conf 2>/dev/null | grep -i psk
```

Expected: `SERPENT_PSK_HEX=` set somewhere (drop-in is fine). PSK must be the **same 64-char hex string** on both Pis. If they differ, every control frame will fail HMAC and the watchdog will fire E-STOP within 5 s — looks identical to a broken system.

| ☐ | 1.4 PSKs match on both Pis |

### 1.5 IP addresses

```bash
# Robot Pi
sudo systemctl show serpent-robot-bridge -p Environment | grep BASE_PI_IP
ip addr show | grep "inet "

# Base Pi  
sudo systemctl show serpent-base-bridge -p Environment | grep ROBOT_PI_IP
ip addr show | grep "inet "
```

Expected: each Pi's `*_PI_IP` env var matches the OTHER Pi's actual IP on the HaLow interface.

| ☐ | 1.5 cross-Pi IPs configured correctly |

---

## 2. Cold-boot test

Power-cycle BOTH Pis. Don't start the bridges manually — let systemd do it.

### 2.1 Both services come up

```bash
# Robot Pi
sudo systemctl status serpent-robot-bridge

# Base Pi
sudo systemctl status serpent-base-bridge
```

Expected: both `active (running)` within 30 s of boot. If either is `failed`, run `journalctl -u serpent-{robot,base}-bridge -n 100` and stop.

| ☐ | 2.1 both services active |

### 2.2 Boot-state log lines

```bash
# On Robot Pi
sudo journalctl -u serpent-robot-bridge -b | grep -i "ActuatorController initialized"

# On Base Pi
sudo journalctl -u serpent-base-bridge -b | grep -i "WinchController initialized"
```

Expected log fragment (Robot):
```
ActuatorController initialized: 4 Motoron boards, 8 active motors,
E-STOP: cleared (reason=None, restored_from=/var/lib/serpent/robot_estop_state.json)
```

Expected log fragment (Base):
```
WinchController initialized (...) E-STOP: cleared (reason=None,
 restored_from=/var/lib/serpent/winch_estop_state.json)
```

If `E-STOP: engaged` on first boot, persistence restored from a previous session — that's correct behaviour, just clear via the TrimUI before continuing.

| ☐ | 2.2 expected boot log lines present |

### 2.3 Watchdogs running

```bash
# Robot Pi
sudo journalctl -u serpent-robot-bridge -b | grep "RobotWatchdog"

# Base Pi
sudo journalctl -u serpent-base-bridge -b | grep "BaseWatchdog"
```

Expected: at least one `*Watchdog initialized` and one `*Watchdog started` line per Pi. If neither shows, the wiring is missing — stop.

| ☐ | 2.3 both watchdogs started |

### 2.4 Operator sees telemetry

On the TrimUI: launch the Flutter app. Within ~10 s, the video feed should appear and the bottom telemetry strip should update (voltage, RTT, control_age).

| ☐ | 2.4 operator UI receives telemetry |

### 2.5 Free movement test

If E-STOP banner is showing on the Flutter UI, press CLEAR.

Then briefly drive each motor:
- Stick → Motor 0 (claw) — small motion, return to neutral.
- L2/R2 (chainsaw on/off) — **DON'T do this if blade is on actual wood.** Tap once and release.
- Dpad Down → Motor 6 (ascender descent) — confirm robot doesn't slip; the mechanical grip holds it.

Expected: motors respond within ~50 ms of input. No spurious E-STOP.

| ☐ | 2.5 free motor control works after clear |

---

## 3. Operator E-STOP engage / clear

### 3.1 Y-button engage

On the TrimUI, press **Y**. Start the timer.

Expected (within 200 ms):
- Red full-screen overlay appears with `EMERGENCY STOP` text.
- All motors stop (including any that were running).
- Banner shows `robot=ENGAGED · winch=ENGAGED`.
- Reason shown: `operator_command`.

Robot Pi log (`journalctl -u serpent-robot-bridge -f`):
```
emergency_stop ENGAGE accepted (reason=operator_command, source=operator)
E-STOP ENGAGED — reason=operator_command, source=operator
```

Base Pi log:
```
emergency_stop ENGAGE forwarded to Robot Pi (reason=operator_command, source=operator)
WINCH E-STOP ENGAGED — reason=operator_command, source=operator
```

Time from Y-press to red overlay: _____ ms (target: < 300 ms)

| ☐ | 3.1 Y-button engages both authorities |

### 3.2 Motor refusal during engage

While engaged, push every joystick / button on the TrimUI for 2 seconds.

Expected: NO motor movement. Robot Pi logs show `Motor X: command refused — E-STOP engaged` at DEBUG (won't show by default; promote to DEBUG with `-p debug` if curious).

| ☐ | 3.2 all motor commands refused during engage |

### 3.3 CLEAR button

Tap the white CLEAR button on the overlay. Start the timer.

Expected (within 500 ms):
- Red overlay disappears.
- Banner reverts to normal telemetry strip.

Robot Pi log:
```
emergency_stop CLEAR accepted (source=operator)
E-STOP CLEARED — prev_reason=operator_command, source=operator
```

Base Pi log:
```
emergency_stop CLEAR forwarded to Robot Pi (source=operator)
WINCH E-STOP CLEARED — prev_reason=operator_command, source=operator
```

Time from CLEAR tap to overlay gone: _____ ms (target: < 500 ms)

| ☐ | 3.3 CLEAR works, both authorities cleared |

### 3.4 Resume motor control after clear

Push joystick again — motors should respond normally within ~50 ms.

| ☐ | 3.4 motors resume after clear |

### 3.5 Bad-confirm clear (negative test)

Engage E-STOP again (Y-button). Then on the Base Pi, manually emit a clear with the WRONG confirm string:

```bash
# On Base Pi, manually inject via socketio-client (or curl if dashboard exposes it)
python3 -c "
import socketio
sio = socketio.Client()
sio.connect('http://localhost:5000')
sio.emit('emergency_stop', {'engage': False, 'confirm': 'WRONG', 'source': 'test'})
import time; time.sleep(0.2)
sio.disconnect()
"
```

Expected: TrimUI overlay STAYS RED. Robot Pi log shows:
```
E-STOP clear refused: confirm string mismatch (got 'WRONG', source=test)
```

| ☐ | 3.5 bad-confirm clear refused |

Then press CLEAR (correct path) to recover.

---

## 4. Watchdog tests

### 4.1 Robot watchdog — kill Base Pi bridge

With both Pis idle and clear, on the **Base Pi**:

```bash
sudo systemctl stop serpent-base-bridge
```

Start the timer. Operator-side: TrimUI link-age banner should appear.

Expected timeline:
- ~1 s: orange "link jitter" pill appears on TrimUI.
- ~2.5 s: orange "LINK DEGRADED — E-STOP in N ms" banner with countdown.
- ~5–6 s: red E-STOP overlay; `robot_estop` reason shows `watchdog_timeout`.

Robot Pi log:
```
RobotWatchdog: control silent (age=5.0Xs > 5.0s) — engaging E-STOP.
E-STOP ENGAGED — reason=watchdog_timeout, source=robot_watchdog
```

| ☐ | 4.1a degraded-link banner appears at ~2.5 s |
| ☐ | 4.1b watchdog engages at ~5–6 s |

Restart Base Pi bridge, clear via TrimUI, verify motors resume.

```bash
sudo systemctl start serpent-base-bridge
```

| ☐ | 4.1c clean recovery after Base restart |

### 4.2 Base watchdog — pull RS-485 cable

Engage clear state. Physically disconnect the RS-485 cable from the Base Pi.

Start timer.

Expected:
- ~5 s: Base Pi watchdog fires; winch E-STOP engages with `reason=rs485_timeout`.
- ~5.1 s: Cross-channel echo forwards to Robot Pi; robot E-STOP engages with `reason=winch_mirror`.
- TrimUI shows red overlay.

Base Pi log:
```
BaseWatchdog: RS-485 silent (age=5.0Xs > 5.0s) — engaging winch E-STOP.
WINCH E-STOP ENGAGED — reason=rs485_timeout, source=base_watchdog
Cross-channel echo Winch→Robot: forwarded (local_reason=rs485_timeout, source=base_watchdog)
```

Robot Pi log:
```
emergency_stop ENGAGE accepted (reason=winch_mirror, source=base_watchdog)
E-STOP ENGAGED — reason=winch_mirror, source=base_watchdog
```

| ☐ | 4.2a base watchdog fires at ~5 s |
| ☐ | 4.2b cross-channel echo reaches robot within ~200 ms |

Reconnect RS-485, clear via TrimUI, verify recovery.

| ☐ | 4.2c clean recovery after RS-485 reconnect |

### 4.3 30-second startup grace

Power-cycle ONLY the Robot Pi. Do not start the Base Pi bridge or the operator UI yet (so no control will be received).

Start timer at the moment Robot Pi boots.

Expected:
- Seconds 0–30: nothing fires. Robot Pi log shows nothing about watchdog engagement.
- Second ~31: watchdog fires with `reason=startup_no_control`.

Robot Pi log:
```
RobotWatchdog: startup grace elapsed without establishing control
 (uptime=3X.Xs >= grace=30.0s) — engaging E-STOP.
E-STOP ENGAGED — reason=startup_no_control, source=robot_watchdog
```

If the watchdog fires earlier than 30 s, the grace is broken — stop.
If the watchdog never fires, the watchdog isn't running — stop.

| ☐ | 4.3 startup grace honoured (~30 s, not before) |

Start Base Pi bridge, clear via TrimUI.

---

## 5. Distributed fast-engage (R5)

These tests need a way to inject malformed frames. Skip if you don't have the test client; the unit-test coverage is comprehensive.

### 5.1 Auth failure

Configure a deliberately wrong PSK on a separate test client and try to send a control frame.

Expected: Robot Pi engages within ~100 ms (much faster than 5 s watchdog).

Robot Pi log:
```
Authentication failed: <details>
E-STOP ENGAGED — reason=auth_failure, source=control_server
```

| ☐ | 5.1 auth failure engages within ~100 ms |

### 5.2 Replay attack

Capture a valid control frame and replay it (sequence number is now stale).

Expected: Robot Pi engages immediately with `reason=replay_attack`.

| ☐ | 5.2 replay engages immediately |

(Skip if no test rig — covered by `test_control_server_fast_engage.py`.)

---

## 6. Two-phase atomic clear

### 6.1 Happy path

(Same as 3.3 — already covered.)

| ☐ | 6.1 happy path two-phase clear works (re-tick from 3.3) |

### 6.2 Split-success rollback

Engage E-STOP. Now stage a partial-failure: kill RS-485 (so winch clear will fail) but leave HaLow up.

Press CLEAR on the TrimUI.

Expected sequence:
1. Local pre-flight passes (HaLow telemetry is fresh).
2. Phase 1: clear forwarded to Robot Pi → Robot Pi clears.
3. Phase 2: local winch clear ATTEMPTS but the Modbus write fails / the gate refuses.
4. Rollback fires: local winch re-engaged with `reason=clear_partial_failure`, Robot Pi re-engaged via forward.
5. TrimUI shows red overlay again with `reason=clear_partial_failure`.

Base Pi log:
```
emergency_stop CLEAR forwarded to Robot Pi (source=operator)
Two-phase clear: LOCAL winch clear refused — re-engaging both authorities
 with reason=clear_partial_failure
WINCH E-STOP ENGAGED — reason=clear_partial_failure, source=base_two_phase_clear
```

Robot Pi log (after the rollback forward arrives):
```
emergency_stop ENGAGE accepted (reason=clear_partial_failure, source=base_two_phase_clear)
E-STOP ENGAGED — reason=clear_partial_failure, source=base_two_phase_clear
```

| ☐ | 6.2a phase 1 clear forward observed |
| ☐ | 6.2b phase 2 winch clear refused |
| ☐ | 6.2c rollback re-engages BOTH authorities |
| ☐ | 6.2d UI shows reason=clear_partial_failure |

Reconnect RS-485, press CLEAR — full recovery.

---

## 7. Persistence across reboot (Q2b)

### 7.1 Engaged state survives Robot Pi reboot

Engage E-STOP via Y-button. Do NOT clear.

Reboot the Robot Pi: `sudo reboot`.

Wait for the Robot Pi to come back up (60–90 s).

Expected: Robot Pi log on first boot shows:
```
E-STOP restored from disk: engaged (reason=operator_command,
 source=operator, engaged_at_ms=<timestamp from before reboot>)
ActuatorController initialized: ... E-STOP: engaged (reason=operator_command, ...)
```

TrimUI shows the red overlay immediately on telemetry recovery.

| ☐ | 7.1 robot_estop persisted across reboot |

### 7.2 Engaged state survives Base Pi reboot

Same test, Base Pi side. Engage, reboot Base, verify `winch_estop` restored.

| ☐ | 7.2 winch_estop persisted across reboot |

### 7.3 Cleared state persists too

Clear E-STOP. Reboot a Pi. Verify it comes up cleared, not engaged. (Soft-latch only, not hard-latch.)

| ☐ | 7.3 cleared state persists (no spurious re-engage on reboot) |

### 7.4 Inspect the state file

```bash
sudo cat /var/lib/serpent/robot_estop_state.json
sudo cat /var/lib/serpent/winch_estop_state.json
```

Expected JSON:
```json
{
  "version": 1,
  "engaged": false,
  "reason": null,
  "source": null,
  "engaged_at_ms": null,
  "last_written_at_ms": <recent epoch ms>
}
```

| ☐ | 7.4 state files are valid JSON, schema version 1 |

---

## 8. Audit trail

While running an operator session, accumulate a few engage/clear cycles (do tests 3 + 4 above; that's ~6 transitions).

Then on the Robot Pi (and Base Pi):

```bash
# If /api/estop/history endpoint is wired in dashboard:
curl http://<robot-pi-ip>:<dashboard-port>/api/estop/history | python3 -m json.tool

# Or via SSH + Python:
python3 -c "
from robot_pi.actuator_controller import ActuatorController
# (this won't share state with the running service — see plan note)
"
```

If the API isn't wired (R9 partial), the in-process history is only readable from inside the bridge. Tail the journal instead:

```bash
sudo journalctl -u serpent-robot-bridge --since "1 hour ago" | grep -E "E-STOP (ENGAGED|CLEARED)"
```

Expected: one log line per transition, with reason + source visible. Number of transitions matches what you did.

| ☐ | 8 audit trail entries match session activity |

---

## 9. Stress / soak

### 9.1 30-minute idle

Set the system to idle (clear E-STOP, no operator input). Walk away for 30 minutes.

Expected: ZERO spurious engagements. Log should be quiet aside from periodic heartbeat / telemetry.

| ☐ | 9.1 30 minutes idle, no spurious engages |

### 9.2 Engage/clear cycle stress

Press Y, tap CLEAR, repeat — 20 cycles in 60 seconds.

Expected:
- Every engage reaches both authorities.
- Every clear succeeds (telemetry stays fresh under this rate).
- No state-file corruption (`cat /var/lib/serpent/*.json` still parses).
- History buffer caps at 100 entries.

| ☐ | 9.2 20 rapid cycles, no corruption |

### 9.3 Concurrent engage paths

While operator is pressing Y rapidly, briefly disconnect RS-485 to make the base watchdog fire too.

Expected: both engage paths converge on the same engaged state. No deadlock, no log flood, no exception traces.

| ☐ | 9.3 concurrent engage paths converge |

---

## 10. Sign-off

### Result summary

| Section | Pass / Fail | Notes |
|---|---|---|
| 1. Pre-flight | | |
| 2. Cold boot | | |
| 3. Operator engage/clear | | |
| 4. Watchdog | | |
| 5. Fast-engage | | |
| 6. Two-phase clear | | |
| 7. Persistence | | |
| 8. Audit trail | | |
| 9. Stress | | |

### Approval

E-STOP rebuild may go to **field operations** if **all** sections pass and there are zero unexplained anomalies.

If any section fails, file a bug with:
- Section number that failed
- Exact log lines from both Pis around the failure window
- TrimUI screenshot if visual
- Whether the failure was reproducible

Tester: ___________________ &nbsp;&nbsp; Date: ___________ &nbsp;&nbsp; Time: ___________

Approval (do NOT skip): ___________________ (only if every box checked)

---

## Appendix A — Useful one-liners

```bash
# Live tail both Pi logs at once (run on a third machine with SSH access):
ssh robot 'sudo journalctl -u serpent-robot-bridge -f' &
ssh base 'sudo journalctl -u serpent-base-bridge -f' &

# Filter to E-STOP events only:
sudo journalctl -u serpent-robot-bridge -f | grep -E "ENGAGED|CLEARED|watchdog|E-STOP"

# Watch state files in real time (refresh every 0.5 s):
watch -n 0.5 'sudo cat /var/lib/serpent/robot_estop_state.json'

# Force a watchdog fire (useful for re-running test 4.1):
sudo systemctl stop serpent-base-bridge && sleep 7 && sudo systemctl start serpent-base-bridge

# Verify the new wiring is live:
sudo journalctl -u serpent-robot-bridge -b | grep "RobotWatchdog initialized"
sudo journalctl -u serpent-base-bridge -b | grep "BaseWatchdog initialized"
```

## Appendix B — Known-good log fragments

Capture these once, attach to the sign-off. They are the ground truth for "this is what passing looks like" and you'll thank yourself the next time the system gets weird.

- Cold boot — first 50 lines of each service.
- Engage event — Robot + Base journal output between Y-press and overlay.
- Clear event — Robot + Base journal output between CLEAR-tap and motors-resume.
- Watchdog fire — Robot journal showing "control silent" line and engage.
- Persistence round-trip — `/var/lib/serpent/*.json` content before reboot, after reboot.

## Appendix C — What to do if tests fail mid-session

1. **DO NOT continue testing.** A failed safety test is the system telling you something is wrong.
2. Engage E-STOP via Y-button (it should still work even if the test that just failed was about clearing).
3. Power down both Pis.
4. Note exactly what test number failed, what you observed, what the logs said.
5. Roll back to the previous-known-good commit if the field deployment is time-sensitive:
   ```bash
   git log --oneline -10  # find the last-good SHA
   git checkout <sha>
   sudo systemctl restart serpent-{robot,base}-bridge
   ```
6. File the bug with the failure capture before re-running.

The plan's golden rule: **don't ship to production until the previous milestone has been field-tested for at least one operator session without spurious engages or rollbacks.** If section 9.1 fails, that rule says you don't ship.

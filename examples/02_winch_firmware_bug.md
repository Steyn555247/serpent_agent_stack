# Example 2 — Winch ESP32 firmware bug (embedded + safety-critical)

This walkthrough shows how a firmware fix moves through the stack with the safety-gate in the loop.

## Request

> "Operator reports the LEFT winch motor sometimes keeps spinning for ~1 second after the controller drops connection. Watchdog should stop it within 500ms."

## Trace

### `/triage operator says left winch keeps spinning ~1s after controller drop, expected <500ms`
debug-triage:
- Reproduces by killing the host-side `winch_controller.py` process while the bridge is in sim.
- Greps `firmware/winch_station/winch_station.ino` for `WATCHDOG_MS` → finds `#define WATCHDOG_MS 500`.
- Greps for `lastCmdMs` → finds the watchdog check in `loop()`. Notices that `lastCmdMs` is only updated on writes to HR 0 (speed register), not on writes to HR 1 (enable register). Operator who hits "stop" sets enable=0 — that DOES NOT refresh the watchdog.
- Trigger condition: enable-register write without a paired speed-register write within the prior 500ms window.

Triage report recommends: `firmware-embedded` (with `safety-gate` review).

### `/firmware-change broaden cmd watchdog refresh to also fire on HR 1 (enable) writes`
Orchestrator picks `workflows/firmware_change.md`. Routes to `firmware-embedded`.

firmware-embedded:
1. Reads `winch_station.ino` end-to-end. Notes the relevant code at the `mb.onSetHreg(0, ...)` line.
2. Edits the Modbus callback: instead of registering the `onCmdUpdate` callback only on HR 0, register it on HR 0 *and* HR 1.
3. Updates the comment header: "watchdog refresh fires on writes to HR 0 (speed) or HR 1 (enable)".
4. No host-side change (host-side is unchanged contract).
5. Updates `firmware/winch_station/README.md` with the new behaviour.
6. Resource budget: +1 callback registration, ~16 bytes flash.
7. Runs `validate.py firmware` → SKIP (PlatformIO not on this host); documents the build command.

### Mandatory safety-gate review
safety-gate reads the diff end-to-end. Walks SI-1 through SI-12:
- SI-8 (firmware command watchdog ≤500ms): **strengthened** — now refreshes on more events. ok.
- SI-11 (Modbus map contract): **unchanged** — register meanings preserved. ok.
- All other invariants: N/A.

Verdict: `approve`.

### Final report (orchestrator)
```
Files changed:
  pi_halow_bridge/PI-HALOW-BRIDGE/firmware/winch_station/winch_station.ino  (+3 / -1)
  pi_halow_bridge/PI-HALOW-BRIDGE/firmware/winch_station/README.md          (+4)
Validator:
  firmware: SKIPPED (PlatformIO not installed; run on dev machine before flashing)
  python:   PASSED (no host-side change to test)
Safety-gate: APPROVED (SI-8 strengthened; no other invariants affected)

Human action required — flash both stations:
  pio run -d "pi_halow_bridge/PI-HALOW-BRIDGE/firmware/winch_station" -e winch_left  -t upload
  pio run -d "pi_halow_bridge/PI-HALOW-BRIDGE/firmware/winch_station" -e winch_right -t upload

Verification after flash:
  Set up sim: python "pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_sim.py"
  Toggle enable=0 with no speed write; confirm motor stops within 500ms via the dashboard.
```

## Lesson

Firmware changes always involve safety-gate. The agent never auto-flashes — the destructive-ops gate blocks it. Resource budget and Modbus contract are inspected explicitly.

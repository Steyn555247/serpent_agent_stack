# Workflow: Firmware change

Use for any change under `firmware/`. Always invokes safety-gate. Never auto-flashes.

## Steps

1. **Plan** — orchestrator
   - Confirm the change is firmware-scoped and identify the host-side counterpart (e.g. `base_pi/winch/winch_controller.py`).
   - Write plan to session_state. Run `safety_check.py --paths firmware/...`.

2. **Implement firmware** — `firmware-embedded`
   - Edit the `.ino` (preserve the pin-define block and comment header).
   - Update host-side controller in lockstep (Modbus map contract).
   - Update `firmware/<station>/README.md` with any new register, pin, or library dep.
   - State the resource budget delta in the report.

3. **Build** — `python agent_stack/tools/validate.py firmware`
   - If PlatformIO not installed, validator returns SKIP. Document this; the human must build before flashing.

4. **Host-side simulation** — `python agent_stack/tools/validate.py sim --sim-seconds 30`
   - Confirms the host-side controller still works against the simulated station.

5. **Safety gate** — `safety-gate` (mandatory for firmware changes)
   - Verdict must be `approve`.

6. **Docs** — `docs-release`
   - Update `firmware/<station>/README.md` and the relevant top-level safety/architecture doc if the change is user-visible.

7. **Flash plan (human action)** — orchestrator
   - Output the exact flash commands. Do not execute.
   - Example for winch_station:
     ```
     pio run -d "pi_halow_bridge/PI-HALOW-BRIDGE/firmware/winch_station" -e winch_left  -t upload
     pio run -d "pi_halow_bridge/PI-HALOW-BRIDGE/firmware/winch_station" -e winch_right -t upload
     ```

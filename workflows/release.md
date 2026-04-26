# Workflow: Release

Use when preparing a deployable version of a subproject.

## Steps

1. **Validate** — orchestrator
   - `python agent_stack/tools/validate.py all` must pass (or document accepted skips).
   - Stress: `python "pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_stress_suite.py" --quick` for the bridge.

2. **Safety review** — `safety-gate`
   - Verify all SI-1..SI-12 invariants hold against current main.

3. **Release notes** — `docs-release`
   - Append to the canonical release doc for the subproject (e.g. `RELEASE_NOTES.md` if one exists; or append to the subproject README under a "Releases" section).
   - List: changes since last release, safety-relevant items, deploy steps, rollback steps.

4. **Build artifacts (human action)** — orchestrator outputs commands
   - Bridge: tag the subproject's git, capture commit SHA.
   - Firmware: build all stations (`pio run` per env, no `-t upload`).
   - Flutter: `build_apk.bat` produces APK; capture the path.

5. **Deploy plan (human action)** — orchestrator outputs commands
   - Pi: documented in `RASPBERRY_PI_DEPLOYMENT.md`. Do not execute.
   - Firmware: flash commands from firmware_change.md step 7.
   - TrimUI: `adb install <apk>`. Do not execute.

6. **Smoke check after deploy (human action)** — checklist
   - Robot Pi: `sudo systemctl status serpent-robot-bridge`
   - Base Pi: `sudo systemctl status serpent-base-bridge`
   - Operator: launch TrimUI app, confirm connection, confirm E-STOP latched on first boot, verify clear sequence works.

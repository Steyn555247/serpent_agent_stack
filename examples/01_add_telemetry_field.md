# Example 1 — Add a telemetry field (software, non-safety-critical)

This walkthrough shows how a routine, non-safety-critical change moves through the stack.

## Request

> "Add a `cpu_temp_c` field to the telemetry payload sent from Robot Pi to Base Pi."

## Trace

### `/plan add cpu_temp_c to robot telemetry payload`
Orchestrator:
1. Reads `conventions.md`, `repo_map.md`, `safety_invariants.md`.
2. Classifies: PI-HALOW-BRIDGE only; layer = python; safety-critical files? `safety_check.py --paths "pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/telemetry/telemetry_sender.py" "pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/sensors/sensor_reader.py"` → **no findings**, proceed.
3. Picks `workflows/feature.md`.
4. Writes plan via `session_state.py`:
   - step 1 (repo-architect): confirm `sensor_reader.py` is the right place to read CPU temp
   - step 2 (default impl): add `cpu_temp_c` to sensor read + telemetry payload
   - step 3 (test-verification): test that telemetry dict includes the field in SIM_MODE
   - step 4 (validate): `validate.py python`
   - step 5 (docs-release): update `TELEMETRY_UPDATE_SUMMARY.md`

### `/implement`
Orchestrator executes step 1 → step 5. No safety-gate involvement (no safety-critical file touched). Final report:
```
Files changed:
  pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/sensors/sensor_reader.py (+8 lines)
  pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/telemetry/telemetry_sender.py (+2 lines)
  pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_telemetry_payload.py  (NEW, 35 lines)
  pi_halow_bridge/PI-HALOW-BRIDGE/TELEMETRY_UPDATE_SUMMARY.md      (+12 lines)
Validator: python PASSED (49 tests, 0 failures, 0 errors)
Safety-gate: not invoked (no safety-critical files touched)
Open blockers: none
Next step: human can review the diff and commit.
```

## Lesson

Routine changes pass through the stack quickly. The only friction is:
- `safety_check.py` runs on the planned paths (cheap).
- A regression test is added (mandatory per `feature.md`).
- A doc update lands in the canonical doc, not a new file.

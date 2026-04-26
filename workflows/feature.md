# Workflow: Feature

Use when adding new functionality. Picked by the orchestrator.

## Steps

1. **Plan** — orchestrator
   - Identify subprojects, layers, and any safety-critical files touched.
   - Write the plan to session_state.
   - Run `safety_check.py` on the planned paths.

2. **Architecture check** — `repo-architect`
   - Confirm placement matches `conventions.md`.
   - Identify importers / dependents.

3. **Implement (per subproject)**
   - Python bridge → main implementation in the right `{robot_pi,base_pi,common}/` module.
   - Embedded → `firmware-embedded` (firmware) + matching host-side controller change.
   - Flutter → main implementation in `lib/{services,screens,widgets,models,constants}/`.
   - All file paths get sanity-checked: `python agent_stack/tools/safety_check.py --paths <files>`.

4. **Tests** — `test-verification`
   - At least one new test that fails before the change and passes after.
   - For safety-adjacent changes, mirror the existing tests/test_estop*.py / test_framing.py pattern.

5. **Validate** — orchestrator
   - `python agent_stack/tools/validate.py python` (and `flutter` if relevant)
   - For embedded: `python agent_stack/tools/validate.py firmware`
   - End-to-end smoke: `python agent_stack/tools/validate.py sim --sim-seconds 15`

6. **Safety gate (if safety-critical files touched)** — `safety-gate`
   - Verdict must be `approve` before proceeding.

7. **Docs** — `docs-release`
   - Update the canonical doc for the area (per `docs-release` repo touchpoints).

8. **Final report** — orchestrator
   - Summarise to the human.

# Workflow: Bug fix

Use when fixing a defect. Smaller than the feature workflow.

## Steps

1. **Triage** — `debug-triage`
   - Reproduce and locate the root cause.
   - Output the trigger condition and the recommended specialist.

2. **Failing regression test FIRST** — `test-verification`
   - Add a test that captures the bug. Confirm it FAILS on current code.

3. **Fix** — the recommended specialist (firmware-embedded, platform-toolchain, or default to direct edit by orchestrator if simple)
   - Smallest possible change. No surrounding cleanup.

4. **Validate** — `python agent_stack/tools/validate.py python` (or relevant target)
   - The new test must now PASS. No previously-passing test may have regressed.

5. **Safety gate (if safety-critical file touched)** — `safety-gate`

6. **Docs** — `docs-release`
   - Append to the relevant `*_FIX*.md` or `BUG_FIX_SUMMARY.md` (existing convention).

7. **Final report** — orchestrator

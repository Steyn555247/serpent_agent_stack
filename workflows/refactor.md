# Workflow: Refactor

Use when restructuring code without changing behavior. Higher bar for tests + safety-gate.

## Steps

1. **Architecture proposal** — `repo-architect`
   - Document current layout, proposed layout, dependency direction, blast radius. No edits.

2. **Human approval gate** — orchestrator
   - Refactor proposals over ~10 files OR any cross-subproject refactor require explicit human approval before implementation begins.

3. **Test coverage check first** — `test-verification`
   - The behaviors being preserved must already have tests. If not, add tests before touching source.

4. **Implement** — orchestrator (or delegated)
   - One coherent commit per logical move. Do not mix moves with behavior changes.

5. **Validate** — `python agent_stack/tools/validate.py all`
   - Every previously-passing test must still pass. Any regression aborts the refactor.

6. **Safety gate (if any safety-critical file moved or renamed)** — `safety-gate`

7. **Docs** — `docs-release`
   - Update any doc that references moved paths.

8. **Final report** — orchestrator
   - Include before/after dependency direction.

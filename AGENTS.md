# Agents — index

This file is the human-readable index of the specialist agents. Definitions live in `.claude/agents/<name>.md` and are auto-discovered by Claude Code.

| Agent | File | Tools | Owns |
|---|---|---|---|
| orchestrator | `.claude/agents/orchestrator.md` | Read, Grep, Glob, Edit, Write, Bash, Agent | Decomposing work, routing, plan + session_state |
| repo-architect | `.claude/agents/repo-architect.md` | Read, Grep, Glob | Module boundaries, dependency graph, refactor proposals |
| firmware-embedded | `.claude/agents/firmware-embedded.md` | Read, Grep, Glob, Edit, Write, Bash | `firmware/`, drivers, RTOS/bare-metal, Modbus, timing |
| platform-toolchain | `.claude/agents/platform-toolchain.md` | Read, Grep, Glob, Edit, Write, Bash | Build, PlatformIO, systemd, install/deploy scripts |
| test-verification | `.claude/agents/test-verification.md` | Read, Grep, Glob, Edit, Write, Bash | `tests/`, sim, stress, fault injection, regression |
| debug-triage | `.claude/agents/debug-triage.md` | Read, Grep, Glob, Bash | Logs, crashes, watchdog trips, postmortems |
| docs-release | `.claude/agents/docs-release.md` | Read, Grep, Glob, Edit, Write | READMEs, runbooks, changelogs, release notes |
| safety-gate | `.claude/agents/safety-gate.md` | Read, Grep, Glob | Reviewing any change touching safety-critical files |

## Routing cheat sheet

| Symptom / request | Start with |
|---|---|
| "Add feature X" / "implement Y" | `orchestrator` (will decompose) |
| "Why is the watchdog tripping?" | `debug-triage` |
| "Add tension calibration register to ESP32" | `firmware-embedded` (then `safety-gate`) |
| "Pi service won't start after reboot" | `platform-toolchain` (then `debug-triage`) |
| "Coverage gap in framing.py" | `test-verification` |
| "Reorganize dashboard module" | `repo-architect` (proposal only — no edits without approval) |
| "Update SAFETY_HARDENING.md for v1.2" | `docs-release` |
| "Diff touches `actuator_controller.py`" | **always** `safety-gate` review before commit |

## When to escalate to human

Any agent that hits one of these conditions must stop and surface to the human, not improvise:

- The proposed change matches a destructive-op pattern (`agent_stack/gates/destructive_ops.yaml`).
- A safety invariant in `agent_stack/gates/safety_invariants.md` would be weakened.
- A test that previously passed now fails and the cause is non-obvious.
- An assumption about hardware behavior cannot be verified in simulation.
- Two specialists return conflicting recommendations.

# agent_stack/

The executable substrate the Claude Code agents shell out to. The agent prompts themselves live in `.claude/agents/` so Claude Code auto-discovers them.

## Contents

### Cross-cutting docs (moved here from repo root 2026-04-25)

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Claude Code entry point — read first |
| `AGENTS.md` | Specialist agent index |
| `ARCHITECTURE.md` | Post-cleanup big-picture overview of the 4 subprojects |
| `SYSTEM_ARCHITECTURE.md` | Cross-subproject software event flow + timing budget |
| `PHYSICAL_ARCHITECTURE.md` | Cross-subproject hardware compute layers + power domains |
| `ESTOP_REBUILD_PLAN.md` | v2.1 design for the 2026-04-24 E-STOP rebuild (R0-R10) |
| `ESTOP_BENCH_TEST.md` | Hardware bench-test runbook for the rebuilt E-STOP |
| `IMPLEMENTATION_WORKFLOW.md` | Cross-subproject delivery workflow for R-milestones |

### Stack internals

| Path | Purpose |
|---|---|
| `conventions.md` | Repo conventions every agent must respect |
| `repo_map.md` / `repo_map.json` | Module map. Regenerate with `tools/build_repo_map.py` |
| `workflows/` | Reusable task templates the orchestrator picks from |
| `gates/destructive_ops.yaml` | Patterns that gate destructive ops |
| `gates/safety_invariants.md` | Non-negotiable safety rules (SI-1 through SI-12) |
| `audits/` | Audit findings + cleanup records (2026-04-23, 2026-04-25) |
| `tools/build_repo_map.py` | Walks the repo, emits the maps |
| `tools/validate.py` | Unified validator: python tests, flutter analyze, firmware build, sim |
| `tools/safety_check.py` | Scans a proposed diff/command set against the gates |
| `tools/session_state.py` | Read/write `.runtime/session_state.json` (orchestrator handoff) |
| `tools/smoke_test.py` | Validates the agent stack itself |
| `examples/` | Worked example workflows for reference |
| `.runtime/` | Gitignored — session state and tool logs |

## Design rules

1. **Tools are the only place imperative behavior lives.** Agent prompts call them; they don't reimplement.
2. **Every tool has `--help`, stable exit codes, and JSON output (when `--json` is passed).**
3. **No tool ever performs a destructive op without `--confirm` AND a matching destructive-op approval in the call.**
4. **Logs go to `.runtime/logs/<tool>-<UTC>.jsonl`.** Never write logs into the repo proper.
5. **State is one file:** `.runtime/session_state.json`. Use `session_state.py` to read/write — never edit directly.

## Common operations

```bash
# Health-check the stack itself
python agent_stack/tools/smoke_test.py

# Refresh the repo map (after large structural changes)
python agent_stack/tools/build_repo_map.py

# Validate everything runnable on this host
python agent_stack/tools/validate.py all --json

# Check whether a planned set of changes touches anything destructive
python agent_stack/tools/safety_check.py --paths path1 path2 --commands "git push" "pio run -t upload"
```

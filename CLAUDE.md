# Serpent Real Prototype — Claude Code entry point

> **New to this repo? Start with [SYSTEM_SETUP.md](../SYSTEM_SETUP.md).**

This repo contains the production prototype of the Serpent rope-climbing robot stack:

- **`pi_halow_bridge/PI-HALOW-BRIDGE/`** — Python 3 safety-critical bridge between Base Pi and Robot Pi over ALFA HaLow 802.11ah, plus ESP32 winch-station firmware (Arduino/PlatformIO). Mature `unittest` suite under `tests/`, simulation under `scripts/run_sim.py`, stress under `scripts/run_stress_suite.py`. **All control paths must remain fail-safe** — see `pi_halow_bridge/PI-HALOW-BRIDGE/SAFETY_HARDENING.md`.
- **`serpent_trimui_app/`** — Flutter 3 operator UI for the TrimUI Smart Pro S handheld controller. `flutter analyze` + `flutter test`. Deploys as APK via ADB.
- **`pi_backend/`** — Pi-side Flask + SocketIO backend that brokers TrimUI Flutter UI ↔ PI-HALOW-BRIDGE Base Pi BackendClient. Flask + flask-socketio. No test suite yet; integration probes under `scripts/bench/probe_*.py`.

The repo top level is **not** a git repo; each subproject has its own `.git`. Treat each subproject as an ownership boundary.

## How to work in this repo with Claude Code

1. **Read these first**, in this order:
   - `agent_stack/conventions.md` — non-negotiable repo conventions
   - `agent_stack/repo_map.md` — current module map
   - `agent_stack/gates/safety_invariants.md` — safety invariants you must not violate
2. **Use the orchestrator for non-trivial work.** Invoke via `/plan <task>` or by calling the `orchestrator` subagent. The orchestrator decomposes work and routes to specialists.
3. **Always run the safety gate before any change to safety-critical files.** See `agent_stack/gates/destructive_ops.yaml` for the full list. The `safety-gate` agent must approve.
4. **Validate with one entrypoint:** `python agent_stack/tools/validate.py all` (or a specific target).
5. **State lives in** `agent_stack/.runtime/session_state.json`. Read it on entry, append decisions, never silently overwrite.

## Specialist agents (full list in `AGENTS.md`)

| Agent | When to use |
|---|---|
| `orchestrator` | Any task with more than ~3 steps or that crosses subprojects |
| `repo-architect` | Module boundaries, dependencies, refactors |
| `firmware-embedded` | ESP32/`firmware/` changes, drivers, ISR/timing/Modbus |
| `platform-toolchain` | Build, PlatformIO, systemd services, deploy scripts, Pi/venv setup |
| `test-verification` | New tests, sim/stress changes, regression coverage |
| `debug-triage` | Failures, crashes, watchdog trips, comms drops |
| `docs-release` | Markdown docs, READMEs, release notes |
| `safety-gate` | **Required reviewer** for any safety-critical diff |

## Common commands

```bash
# Validate everything that can run on this host
python agent_stack/tools/validate.py all

# Run only the bridge unit tests (uses repo's own runner)
python "pi_halow_bridge/PI-HALOW-BRIDGE/scripts/test_all.py"

# Run the bridge in simulation
python "pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_sim.py"

# Flutter analyze + test
cd "serpent_trimui_app" && flutter analyze && flutter test

# Regenerate the repo map (run after large structural changes)
python agent_stack/tools/build_repo_map.py

# Check the agent stack itself is healthy
python agent_stack/tools/smoke_test.py
```

See `agent_stack/examples/` for worked walk-throughs (telemetry field, firmware bug, dart lint).

## Hard rules

- **Never auto-execute a destructive op.** Anything matched by `agent_stack/gates/destructive_ops.yaml` requires explicit human confirmation. This includes flashing firmware, pushing to a Pi, modifying systemd unit files, force-pushing git, or editing PSK material.
- **Never weaken a safety invariant.** All twelve invariants (SI-1 … SI-12) are enforced as of 2026-04-24. The E-STOP rebuild (R0–R10) shipped per `ESTOP_REBUILD_PLAN.md` v2.1; see `agent_stack/gates/safety_invariants.md` for the file-level mapping. Changes that touch any safety invariant must go through `safety-gate`.
- **Never bypass the test runner.** If a test is flaky, fix it or quarantine it in a tracked entry — don't skip silently.
- **Don't introduce new top-level directories** without writing why in `agent_stack/conventions.md`.
- **Don't reformat or restructure files you weren't asked to change.** Bug fixes don't need surrounding cleanup.

## Where to put new things

- New Python module for the bridge → inside `pi_halow_bridge/PI-HALOW-BRIDGE/{robot_pi,base_pi,common,dashboard}/` matching its role.
- New ESP32 sketch → `pi_halow_bridge/PI-HALOW-BRIDGE/firmware/<station_name>/<station_name>.ino` with a sibling `README.md` documenting wiring + PlatformIO env.
- New Flutter widget/service → `serpent_trimui_app/lib/{widgets,services,screens,models,constants}/` matching its role.
- New test → mirror the source path under the subproject's `tests/` (or `test/` for Flutter), use `test_*.py` for Python so the existing discovery picks it up.
- New script that's part of the agent stack → `agent_stack/tools/`.
- New script that's part of the bridge runtime → `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/`.

## When to ask for human review vs. proceed

Proceed autonomously when: the change is non-safety-critical, has a unit test, all validation passes, and no destructive-op pattern fires.

Ask the human when: editing a file under `agent_stack/gates/destructive_ops.yaml`'s "safety-critical paths" list, proposing a new top-level directory, modifying systemd units, or any time the safety-gate agent returns `needs_human`.

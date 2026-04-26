# Repo conventions

These are the rules every agent must follow. Violating any of these is a regression even if tests pass.

## 1. Subproject ownership

The repo top level is **not** a single git repo. Three ownership boundaries:

- `pi_halow_bridge/PI-HALOW-BRIDGE/` — own git repo
- `serpent_trimui_app/` — own git repo
- `pi_backend/` — Pi-side Flask + SocketIO event broker (no `.git/` on initial extraction; operator may init one when ready)

Do not assume a top-level `git` command will work. Each subproject's `.git` is independent.

When a change spans subprojects, write a single plan but produce **separate commits** per subproject.

### Why pi_backend is a separate subproject

`pi_backend/` is the Pi-side Flask + SocketIO backend that brokers TrimUI Flutter UI events to the PI-HALOW-BRIDGE Base Pi BackendClient. Extracted from `serpent_trimui_app/` 2026-04-25 (R16, Tier 4 batch 4.6) because a 1858-line Python network service does not belong in a Flutter project's source tree (ownership-boundary clarity). It has its own requirements, deployment scripts, and is independently version-controlled (no `.git/` inside on initial extraction; the operator may init one when ready).

### Where to put new things in pi_backend

- New Python module for the broker → `pi_backend/` (top-level for now; subdivide once a clear module boundary emerges).
- New deployment script → `pi_backend/` next to the existing `setup_*.sh` / `manage_service.sh`.
- New manual integration probe → `pi_backend/scripts/bench/probe_*.py` (matching the existing pattern).
- New requirements pin → extend `requirements.txt` (Pi deployment) or `requirements_dev.txt` (probes), whichever the dependency targets.

### pi_backend is NOT safety-gated

`pi_backend/` is a Flask + SocketIO event broker, not a safety surface. It does not command actuators, hold the watchdog, generate or hold PSK material, or sit on the E-STOP path — those all live in `pi_halow_bridge/PI-HALOW-BRIDGE/`. Accordingly, **no path under `pi_backend/` is listed in `agent_stack/gates/destructive_ops.yaml` `safety_critical_paths`**, and edits to `pi_backend/` files do not require `safety-gate` review. Standard test/validation discipline still applies.

## 2. Python (PI-HALOW-BRIDGE)

- **Test runner is `unittest`**, not pytest. `scripts/test_all.py` discovers `tests/test_*.py`. New tests must be discoverable by the existing runner. (`run_stress_suite.py` happens to call pytest as well, which works because `unittest.TestCase` classes are pytest-compatible — but the **canonical** runner is `test_all.py`.)
- All tests must work in `SIM_MODE=true`. Never require physical hardware in unit tests.
- `SIM_MODE` is set with `os.environ['SIM_MODE'] = 'true'` *before* importing modules that branch on it. Follow the pattern in existing tests.
- `SERPENT_PSK_HEX` must be set for any test that uses `SecureFramer`. Use the deterministic test PSK from `scripts/test_all.py` for reproducibility, or `secrets.token_hex(32)` for non-deterministic tests.
- Hardware imports (`motoron`, `RPi.GPIO`, `adafruit_*`, `busio`, `board`) are **conditional** — they only import when `SIM_MODE` is false. Maintain that pattern; never make a hardware import unconditional.
- All safety-critical modules (`actuator_controller.py`, `framing.py`, anything under `core/` that touches E-STOP) use a **single lock per concern** for atomicity. Don't introduce a second lock without coordinating.
- New constants belong in `common/constants.py`. Do not duplicate magic numbers across modules.

## 3. Embedded (firmware/)

- One subdirectory per "station" (e.g. `firmware/winch_station/`). Each contains a single `.ino`, a `README.md`, and a documented PlatformIO env in the README.
- Default to a **command watchdog** (≤500 ms) on every actuator path. If the firmware loses host comms, motors must be commanded to 0.
- Modbus register maps must be documented in **both** the `.ino` (as a comment block at the top) and the corresponding Python controller (e.g. `base_pi/winch/winch_controller.py`). Changes to the map require updating both.
- Pin assignments live as `#define` at the top of the `.ino`, not scattered. Document them in the comment header.
- Don't enable WiFi/BLE on the ESP32 unless required — it conflicts with ADC2 pins.
- EEPROM use must be guarded by a magic word (see `EEPROM_MAGIC` pattern) so cold-flashed devices fall back to safe defaults.

## 4. Flutter (serpent_trimui_app)

- Use `flutter_lints` defaults. Don't disable rules in `analysis_options.yaml` without a comment explaining why.
- Services that hold global state belong in `lib/services/` and are constructed once in `main.dart`.
- Long-lived background work uses Dart isolates or platform channels — not raw `Timer.periodic` for input polling (that's what `native_gamepad_service` exists for).
- New screens go under `lib/screens/`; new reusable widgets under `lib/widgets/`. Don't put screens in `widgets/`.
- The TrimUI deploys via ADB-installed APK. Do not break the existing build target (`build_apk.bat` / `build_apk.ps1`).

## 5. Documentation

- Project-level docs (architecture, safety, releases) live under each subproject's root, in `UPPER_SNAKE_CASE.md`. This matches existing convention (e.g. `SAFETY_HARDENING.md`).
- Component-level READMEs (`firmware/winch_station/README.md`) live next to the component.
- Agent stack docs live under `agent_stack/`.
- Repo-root markdown is restricted to the following enumerated inventory of 7 files:
  - `AGENTS.md` — agent-stack entry point (reserved)
  - `CLAUDE.md` — agent-stack entry point (reserved)
  - `ESTOP_BENCH_TEST.md` — multi-host safety bench procedure
  - `ESTOP_REBUILD_PLAN.md` — multi-host safety rebuild plan
  - `IMPLEMENTATION_WORKFLOW.md` — cross-subproject delivery workflow
  - `PHYSICAL_ARCHITECTURE.md` — cross-subproject physical layout
  - `SYSTEM_ARCHITECTURE.md` — cross-subproject system map
  - (Historical audit findings live under `agent_stack/audits/` — e.g. `2026-04-23-audit-findings.md` — not at repo root. The frozen `SAFETY_AUDIT_ESTOP.md` incident record was moved to `pi_halow_bridge/PI-HALOW-BRIDGE/archive/` 2026-04-25.)
- Allowed root-level docs are limited to two categories: agent-stack entry points (`CLAUDE.md`, `AGENTS.md`), and safety-, architecture-, or rebuild-plan documents that span both subprojects in `UPPER_SNAKE_CASE.md` (e.g. `SYSTEM_ARCHITECTURE.md` for cross-subproject map, `ESTOP_REBUILD_PLAN.md` / `ESTOP_BENCH_TEST.md` for multi-host safety work).
- Adding a new root-level markdown file requires updating this convention's enumerated list above and stating which cross-subproject concern it documents. Otherwise it belongs under a subproject root or `agent_stack/`.
- Subproject-internal docs (only relevant to one of `pi_halow_bridge/PI-HALOW-BRIDGE/` or `serpent_trimui_app/`) stay in that subproject's root, never at repo top.

## 6. Logging

- Python: use `common/logging_config.py` setup. Never call `logging.basicConfig` from a module.
- Safety-relevant log lines must include the role (`[robot_pi]`, `[base_pi]`) so multi-host log streams stay parseable.
- Agent tools log to `agent_stack/.runtime/logs/`. Never to the repo proper.

## 7. Commits

- Each subproject gets its own commits. Do not try to commit across both at once.
- Do not commit anything in `agent_stack/.runtime/`.
- Never commit `SERPENT_PSK_HEX` material or anything under `pi_halow_bridge/PI-HALOW-BRIDGE/.psk*`.
- Commit messages: short subject (≤72 chars), body explains *why*. Match the existing tone in `git log`.

## 8. Destructive operations

The patterns in `agent_stack/gates/destructive_ops.yaml` are blocking. They include:

- Flashing firmware (`pio run -t upload`, `arduino-cli upload`, `esptool`)
- Editing systemd service files (`*.service`)
- Modifying `setup_*.sh`, `pi_install.sh`, `pi_enable_services.sh`
- Changing PSK material or `SERPENT_PSK_HEX` handling
- `git push --force`, `git reset --hard`, `git clean -fd`
- Any change to `actuator_controller.py`, `framing.py`, `constants.py` (safety-critical Python)
- Any change under `firmware/`

Such ops require explicit human confirmation, never autonomous execution.

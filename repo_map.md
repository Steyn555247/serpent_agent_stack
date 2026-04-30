# Repo map

_Generated 2026-04-28T03:01:16+00:00 by `agent_stack/tools/build_repo_map.py`. Do not edit by hand — re-run the tool._

## Subprojects

### `agent_stack/`  (unknown)

- Has own `.git`: **True**
- Files by language: python=5, config=1, docs=26

### `pi_backend/`  (python)

- Has own `.git`: **True**
- Files by language: python=19, shell=8, docs=8

### `pi_halow_bridge/PI-HALOW-BRIDGE/`  (python+embedded)

- Has own `.git`: **True**
- Files by language: python=128, arduino=1, shell=8, docs=15
- **test**:
  - `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/test_all.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_actuator_controller.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_actuator_controller_dead_motoron_channels.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_autonomous_cutter_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_base_pi_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_base_watchdog.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_base_watchdog_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_bridge_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_bridge_wiring.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_command_executor_chainsaw_routes_to_stepper.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_command_executor_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_command_executor_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_control_server_fast_engage.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_control_server_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_cross_channel_echo.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_dashboard_field_control.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_dashboard_field_control_integration.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_display_panel.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_estop_integration.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_fault_counters.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_fault_injection.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_framing.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_host_metrics.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_link_dropout.py`
  - …and 11 more
- **sim**:
  - `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_sim.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/run_stress_suite.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/sim/winch_sim.py`
- **service**:
  - `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/systemd/serpent-dashboard-hdmi.service`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/systemd/serpent-dashboard-headless.service`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/systemd/serpent-dashboard-robot.service`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/systemd/serpent-base-bridge.service`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/systemd/serpent-robot-bridge.service`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/systemd/serpent-robot-display.service`

### `serpent_trimui_app/`  (flutter)

- Has own `.git`: **True**
- Files by language: python=1, dart=17, config=2, docs=18
- **build**:
  - `serpent_trimui_app/build_apk.bat`
  - `serpent_trimui_app/build_apk.ps1`
  - `serpent_trimui_app/pubspec.yaml`

## Safety-critical files

- `pi_halow_bridge/PI-HALOW-BRIDGE/base_pi/winch/winch_controller.py`
- `pi_halow_bridge/PI-HALOW-BRIDGE/common/constants.py`
- `pi_halow_bridge/PI-HALOW-BRIDGE/common/framing.py`
- `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/actuators/actuator_controller.py`
- `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/control/control_server.py`
- `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/command_executor.py`
- `pi_halow_bridge/PI-HALOW-BRIDGE/robot_pi/core/watchdog_monitor.py`

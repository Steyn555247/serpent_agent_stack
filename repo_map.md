# Repo map

_Generated 2026-04-26T14:10:17+00:00 by `agent_stack/tools/build_repo_map.py`. Do not edit by hand — re-run the tool._

## Subprojects

### `pi_backend/`  (python)

- Has own `.git`: **False**
- Files by language: python=19, shell=8, docs=6

### `pi_halow_bridge/PI-HALOW-BRIDGE/`  (python+embedded)

- Has own `.git`: **True**
- Files by language: python=108, arduino=1, shell=8, docs=12
- **test**:
  - `pi_halow_bridge/PI-HALOW-BRIDGE/scripts/test_all.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_actuator_controller.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_autonomous_cutter_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_base_pi_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_base_watchdog.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_base_watchdog_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_bridge_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_bridge_wiring.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_command_executor_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_command_executor_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_control_server_fast_engage.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_control_server_observability_tick.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_cross_channel_echo.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_estop.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_estop_integration.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_fault_counters.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_fault_injection.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_framing.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_host_metrics.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_link_dropout.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_loop_health.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_robot_watchdog.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_safety_constants.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_telemetry_two_stamp.py`
  - `pi_halow_bridge/PI-HALOW-BRIDGE/tests/test_transition_logger.py`
  - …and 2 more
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

### `serpent_trimui_app/`  (flutter)

- Has own `.git`: **True**
- Files by language: python=1, dart=17, config=2, docs=16
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

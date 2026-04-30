# SPI display remediation closure (2026-04-28)

Remediation against commit `c198f49` (the SPI display landing). Resolves
the 10 showstoppers + 7 majors raised in the post-landing audit and the
test-collection regression that dropped the python validator from 355 to
308 collected tests.

## Sequencing
- Workflow template: `agent_stack/workflows/bugfix.md` (extended; three
  safety-gate checkpoints).
- Plan: 16 steps, four safety-gate checkpoints (3, 6, 9, 12).
- Session state: `agent_stack/.runtime/session_state.json`.

## Showstoppers resolved
1. **Validator regression (308 vs 355)**. `dashboard/web_server.py` had
   two definitions of `api_estop_clear` (and `api_estop_engage`) at lines
   886 vs 944. Flask `add_url_rule` raised `AssertionError` at module
   import, breaking test loading. Removed the simpler IPC-direct
   robot_pi-role variants (944-995); kept the canonical 3-gate base_pi
   variants that go through the backend (which enforces SI-3
   confirm/age/connected).
2. **Bridge snapshot writer too narrow**. `bridge_coordinator.py:773-786`
   only emitted `state ∈ {ready, estop}`; the display never saw cutting,
   startup_timeout, or boot_grace. Added `_build_robot_status_snapshot`
   helper that reads existing accessors lock-free and emits the full
   schema. No new lock, no widening of E-STOP trigger surface, no PSK
   leakage — confirmed by safety-gate (verdict: APPROVE, recorded in
   session_state.json).
3. **Display fonts re-loaded each paint**. `_paint_text` etc. opened
   `ImageFont.truetype` on every call — burned ~30 % CPU on a Pi 4. Added
   `_font_cache: dict[(path,size)] -> ImageFont`; truetype is now called
   at most once per (path,size) tuple.
4. **Boot splash didn't use brand assets**. Replaced text-only fallback
   with `LOGO_BRIGHT.png` paste + Orbitron Bold for SERPENT/ROBOTICS.
   Resilient to missing assets (falls back to text on FileNotFoundError).
5. **ALARM red colliding with ORANGE in RGB565**. Audit M3 — bumped
   ALARM from `(255,59,15)` to `(255,24,24)` so e-stop and cutting
   screens are unmistakably distinct.
6. **SPI backoff never reset on success**. Successful `device.display(img)`
   now resets `_spi_error_count` and `_spi_backoff_until` to 0.
7. **Null-estop crash**. `_select_screen` now uses `status.get('estop') or
   {}` style guards so a partially populated snapshot doesn't
   AttributeError.
8. **No SPI re-open ladder**. Added `_SPI_REOPEN_AFTER=10` (consecutive)
   close+reopen, and `_SPI_HARD_FAIL_AFTER=20` (total) re-raise so
   systemd `Restart=on-failure` recycles the unit.
9. **Edge-trigger lied**. The docstring claimed "edge-triggered immediate
   redraw on state transition" but `tick()` redrew unconditionally. Now
   actually edge-triggered: skip `_render_screen` when the screen id is
   unchanged AND the heartbeat tick is not due. Force a redraw every 5
   ticks so the heartbeat dot animates.
10. **Validator regression hid display-test collection**. Side-effect of
    #1; now `tests/test_display_panel.py` is collected (36 cases) and
    `tests/test_pi_install_smoke.py` adds 13 install-time invariants.

## Majors resolved
1. **`enable --now` ordering** with display-before-bridge. Per Q2: kept
   `enable --now` and added `log_info "Display will show BRIDGE STALE
   until the bridge service is enabled in step 2"` immediately after.
2. **GPIO backend on Bookworm/Trixie**. `RPi.GPIO>=0.7.1` doesn't drive
   the kernel chardev. Replaced with `rpi-lgpio>=0.6` (drop-in for
   `RPi.GPIO`, calls `lgpio` underneath). No client code changes.
3. **Pillow / luma.lcd unbounded pins**. Now `luma.lcd>=2.10,<3` and
   `Pillow>=10.4,<12` so a major upstream bump doesn't silently break
   the rendering primitives.
4. **Display unit hardcoded `serpentbase`**. Removed literal
   `User=serpentbase` and `WorkingDirectory=/home/serpentbase/...` from
   the shipped unit. `pi_install.sh` now writes
   `/etc/systemd/system/serpent-robot-display.service.d/override.conf`
   with `User=$SUDO_USER`, `WorkingDirectory=$PROJECT_ROOT`, and the
   correct `ExecStart=$VENV_PYTHON -m robot_pi.io` BEFORE enabling.
5. **`MemoryMax=64M`** too tight. Bumped to 128M (audit M3) — Pillow +
   luma.lcd + cached fonts + Orbitron splash push working set above 64M
   on warm restarts.
6. **`RuntimeDirectoryPreserve` missing**. Added `RuntimeDirectoryPreserve=yes`
   to BOTH service files so /run/serpent IPC files (robot_status.json,
   autocut_*) survive a unit restart. Persistent E-STOP state still lives
   in `StateDirectory=serpent` (/var/lib/serpent) — unchanged.
7. **`pi_install.sh` not idempotent**. `ln -s` was inside an
   `if [ ! -L … ]` branch. Now `ln -sf` and `daemon-reload` both run
   unconditionally. `enable --now` is itself idempotent.

## Out of scope
- `serpent_trimui_app/test/widget_test.dart` flutter regression — pre-
  existing, independent of the python validator. Flagged as a separate
  follow-up.
- `pi_backend` Flask `api_estop_clear` collision — misattribution; the
  collision was in `pi_halow_bridge/PI-HALOW-BRIDGE/dashboard/web_server.py`,
  fixed by step 2.
- Any `stash@{0}` uncommitted edits in the pi_halow_bridge worktree —
  not touched.

## Validator delta
- Pre: 308 collected, 6 errors, 2 failures.
- Post: 383 collected, 0 errors, 0 failures.
- Delta vs the 355 baseline: +28 net new tests
  (+15 in `test_display_panel.py` extended schema / edge-trigger / render
  contract, +13 in the new `test_pi_install_smoke.py`).

## Safety-gate verdicts
- Step 3 (Workstream A pre-edit): APPROVE.
- Step 6 (Workstream A post-edit): APPROVE.
- Step 9 (Workstream C pre-edit): APPROVE.
- Step 12 (Workstream C post-edit / DEPLOY GATE): APPROVE.

## Human actions still required
- Review the diff in `pi_halow_bridge/PI-HALOW-BRIDGE/`
  (`dashboard/web_server.py`, `robot_pi/core/bridge_coordinator.py`,
  `robot_pi/io/{display_panel,theme}.py`, `robot_pi/io/__init__.py`,
  `robot_pi/requirements.txt`, `robot_pi/README.md`,
  `systemd/serpent-robot-{bridge,display}.service`,
  `scripts/pi_install.sh`, `SAFETY_HARDENING.md`,
  `tests/test_{display_panel,pi_install_smoke}.py`).
- Per repo memory `no_commits_no_pushes`, the orchestrator did NOT commit
  or push. Operator decides when to land these.
- Operator runs `sudo bash scripts/pi_install.sh --robot` on the Pi to
  pick up the new display unit (drop-in is written at install time).
- After install, verify the display drop-in landed:
  `cat /etc/systemd/system/serpent-robot-display.service.d/override.conf`
  shows the operator's `User=` and the venv `ExecStart=`.

## Memory candidates worth flagging (NOT auto-saved)
- `display_advisory_schema_extended` — record that the snapshot now
  carries warn/cutting/boot_grace, and confirm display crash != E-STOP
  remains the rule.
- `bookworm_gpio_backend` — note that the Robot Pi requires
  `rpi-lgpio` (not `RPi.GPIO`) on Bookworm and later; pi_install.sh now
  drops the system `python3-rpi.gpio` apt package.

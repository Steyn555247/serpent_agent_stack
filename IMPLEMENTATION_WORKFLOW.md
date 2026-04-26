# E-STOP Rebuild Implementation Workflow

> How to execute `ESTOP_REBUILD_PLAN.md` (v2.1) through the existing agent stack. Answers **who does what, when, and with what approval** for each of the 16 R-milestones.

---

## Three blocking decisions

Before R1 can start, you need to answer these (all in `ESTOP_REBUILD_PLAN.md` §"Decisions waiting on you"):

| # | Question | My recommendation |
|---|---|---|
| Q2 | Hard-latch or soft-latch at boot? | Hard-latch on both Pis + `SERPENT_DEV_MODE=1` escape |
| Q2b | Persist E-STOP state across reboots? | No — default-engaged at boot |
| Q6 | Operator-hold proof token for clear? | No — skip for v1 |

**R0 (constants) is not blocked by these** — it's pure additive. Everything R1 onwards is blocked until they're answered.

---

## Per-milestone owner + review pattern

Each R-milestone has one of three shapes:

### Shape A — safety-critical code (most R milestones)

Files touched are listed in `agent_stack/gates/destructive_ops.yaml :: safety_critical_paths`:
- `common/constants.py`, `common/framing.py`
- `robot_pi/actuator_controller.py`, `robot_pi/core/command_executor.py`, `robot_pi/control/control_server.py`
- `base_pi/winch_controller.py`, `base_pi/control_forwarder.py`, `base_pi/telemetry_receiver.py`
- `firmware/**`, `*.service`, PSK scripts

**Workflow:**

1. **Draft in main context** (Claude writes the code with full editing).
2. **`safety-gate` agent reviews the diff** before commit. Invoke via `Skill: safety-check` or the `safety-gate` sub-agent with the specific file list.
3. Safety-gate returns `approve` / `needs_revision` / `needs_human`.
   - `approve` → land.
   - `needs_revision` → fix, re-review.
   - `needs_human` → stop, surface to you.
4. After landing, run `python agent_stack/tools/smoke_test.py` + `python pi_halow_bridge/PI-HALOW-BRIDGE/scripts/test_all.py`. Both must stay green.

**Applies to:** R0, R1, R1b, R3, R3b, R4, R4b, R5, R7.

### Shape B — tests / docs / non-safety code

Files NOT in `safety_critical_paths`:
- `tests/**` (except when the test file imports safety-critical code — still not gated)
- `serpent_trimui_app/**` (Flutter side is not gated)
- `pi_backend/server.py` (backend relay, not gated)
- `base_pi/core/{backend_client,bridge_coordinator,state_manager}.py` (relay-layer, not gated)
- `dashboard/**`
- `SYSTEM_ARCHITECTURE.md`, `agent_stack/audits/2026-04-23-audit-findings.md`, README banners

**Workflow:**

1. Draft in main context.
2. Run the test suite.
3. Land.

No safety-gate required. Invoke safety-gate voluntarily if the change *feels* safety-adjacent, but don't block on it.

**Applies to:** R2, R6, R8, R9, R10.

### Shape C — gate config / invariant doc edit

Files: `agent_stack/gates/destructive_ops.yaml`, `agent_stack/gates/safety_invariants.md`.

**Workflow:**

1. Draft the edit.
2. **safety-gate MUST approve** — it's reviewing changes to its own rules.
3. After landing, the next thing committed goes through the updated gate.

**Applies to:** R11 (doc refresh flips invariants back to ✅).

---

## Rollback per milestone

Each milestone is designed to be independently mergeable. If milestone R<n> ships to a field Pi and misbehaves:

```bash
# On the affected Pi:
sudo systemctl stop serpent-robot-bridge  # or serpent-base-bridge
cd /opt/serpent  # or wherever the repo lives
git log --oneline -20  # find the last-good commit (the one before R<n>)
git checkout <last-good-sha>
sudo systemctl start serpent-robot-bridge  # will boot-latch, operator clears normally
```

Concrete rollback boundaries:
- **R0 reverts cleanly** — just deletes added constants. No dependents yet.
- **R1 / R1b revert cleanly** — callers won't exist yet (R4/R4b haven't shipped).
- **R4 / R4b revert** — requires also reverting or stubbing R7 (cross-channel echo) if it shipped first, since R7 depends on the Base-side emergency_stop handler.
- **R9 (UI) reverts cleanly** — Flutter APK rollback is `adb install -d` of the prior APK; dashboard HTML rollback is a single git checkout.
- **R11 (doc refresh) reverts cleanly** — docs only; flipping invariants back to PENDING REBUILD if R10 field-tests fail.

**Golden rule:** do not ship R<n> to production until R<n-1> has been field-tested for at least one operator session without spurious engages or rollbacks.

---

## Branch strategy

> **Update 2026-04-24:** the rebuild landed; milestones R0-R10 are merged. The
> "current E-STOP-removed `main`" wording below is the original 2026-04-23
> framing and is retained for historical context only.

Recommend a single long-lived feature branch `estop-rebuild-v2` off the current E-STOP-removed `main`. Each R-milestone is one commit on that branch, with a merge to main when the whole thing is field-validated (or in small groups of milestones if that's lower-risk to ship).

Rationale: the rebuild crosses many files; merging milestone-by-milestone to main would have half-finished state for days. Feature branch keeps main stable, integration visible to any other work.

Tag each milestone commit: `estop-rebuild-r0`, `estop-rebuild-r1`, etc. Makes rollback targets explicit.

---

## Field-acceptance criteria (R10 + R11 gate)

Before merging the feature branch to main, the rebuild must pass:

1. **All tests green:** `python agent_stack/tools/smoke_test.py` 92/92; `scripts/test_all.py` all pass including the new `test_estop.py`, `test_base_pi_estop.py`, `test_estop_integration.py`.
2. **Flutter analyze:** 0 errors.
3. **Flutter test:** all green.
4. **Validator:** `python agent_stack/tools/validate.py all` exits 0.
5. **Bench E-STOP scenarios (manual, on real Pi pair):**
   - Cold boot both Pis → both come up engaged → operator clears via TrimUI → motors move.
   - Engage via TrimUI → robot stops, winch stops. Clear → both resume.
   - Engage via dashboard (Base Pi browser) → same.
   - Kill Base Pi bridge (`systemctl stop`) → Robot Pi watchdog fires at 5 s → both engaged. Restart Base Pi → operator clears → back to normal.
   - Pull RS-485 cable → Base Pi watchdog fires → winch engages → robot mirrors → both engaged. Reconnect → operator clears.
   - Inject one malformed frame over HaLow → Robot Pi control_server fast-engage fires → both engaged.
6. **One operator session of ≥ 30 minutes** with no spurious engages (no watchdog fires the operator didn't cause).
7. **Split-success clear tested:** deliberately fail one side's clear (e.g., unplug RS-485 during a clear attempt) → two-phase rollback fires → both end up re-engaged with `reason="clear_partial_failure"`.
8. **Audit trail verified:** after a test session with multiple engage/clear cycles, `/api/estop/history` returns entries matching the session log.

---

## Agent assignments per milestone shape

| Milestone | Owner | Review |
|---|---|---|
| R0 | Claude (main ctx) | safety-gate |
| R1 | Claude (main ctx — safety-critical; lots of state) | safety-gate |
| R1b | Claude (main ctx) | safety-gate |
| R2 | Claude or `test-verification` agent | — |
| R3 | Claude (safety-gate) | safety-gate |
| R3b | Claude (safety-gate) | safety-gate |
| R4 | Claude (safety-gate) | safety-gate |
| R4b | Claude (two-phase clear is gnarly; do in main ctx) | safety-gate |
| R5 | Claude (safety-gate) | safety-gate |
| R6 | Claude (telemetry fields, non-gated) | — |
| R7 | Claude (safety-gate) | safety-gate |
| R8 | Claude (serpent_backend not gated) | — |
| R9 | `test-verification` can scaffold Flutter tests; Claude does the UI + dashboard changes | — |
| R10 | `test-verification` agent — comprehensive integration matrix | — |
| R11 | `docs-release` agent | safety-gate (gate edit) |

**Rule of thumb for agent delegation:** if it's multi-file and clearly scoped, agent. If it's one-or-two-file and safety-critical, Claude in main ctx where safety-gate review is tighter. Per the `agent_spawning_discipline.md` memory: don't delegate small edits.

---

## Mid-course correction protocol

If during implementation we discover a design gap in the plan (e.g., R4b reveals that the two-phase clear rollback has a subtle race), the workflow is:

1. **Stop execution** of the current milestone.
2. **Flag the issue** in user-visible chat.
3. **Update `ESTOP_REBUILD_PLAN.md`** to reflect the new understanding.
4. **Update affected later milestones** in this workflow doc.
5. **Resume** only after the plan is updated and the user has ack'd.

Don't power through a plan bug; correct the plan first.

---

## What's done before R0 starts (the PREP phase)

- [x] Audit + architecture docs written (`SYSTEM_ARCHITECTURE.md`, `PHYSICAL_ARCHITECTURE.md`, `pi_halow_bridge/PI-HALOW-BRIDGE/archive/SAFETY_AUDIT_ESTOP.md`)
- [x] Old E-STOP surface removed (11 milestones M0-M10)
- [x] `ESTOP_REBUILD_PLAN.md` v2.1 drafted with physical-layer informed design
- [x] Ascender physical safety understood (mechanical one-way grip)
- [x] Red-team pass + fixes landed (bidirectional echo, audit trail, atomic clear, restart-awareness, Motor 7 verification flag)
- [x] Implementation tasks created (R0-R11 + PREP)
- [x] This workflow doc written
- [ ] Q2 / Q2b / Q6 answered (blocks R1)
- [ ] R0 executed (blocks R1 but doesn't need Q answers)

## After R0

The feature branch exists, the constants are available, and everything R1+ is blocked waiting on the three decisions. When you answer those, I can execute R1 onwards in the order specified in the milestone table.

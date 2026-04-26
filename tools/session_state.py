#!/usr/bin/env python3
"""
Read/write the orchestrator session state.

Single source of truth for cross-agent handoff:
    agent_stack/.runtime/session_state.json

Schema (all keys optional except `version`):
{
  "version": 1,
  "task": "<one-line summary of what the user asked>",
  "started_utc": "...",
  "updated_utc": "...",
  "plan": [
    {"id": 1, "step": "...", "owner": "<agent-name>", "status": "pending|in_progress|done|blocked"}
  ],
  "current_step": <int>,
  "decisions": [
    {"utc": "...", "by": "<agent>", "decision": "...", "rationale": "..."}
  ],
  "blockers": [
    {"utc": "...", "by": "<agent>", "blocker": "...", "needs": "human|specialist:<name>"}
  ],
  "open_questions": ["..."],
  "agent_history": [
    {"utc": "...", "agent": "...", "in": "...", "out": "..."}
  ]
}

Subcommands:
    init      Initialise (overwrites existing — use --force to confirm)
    show      Print current state
    set-task  Replace the task summary
    add-step  Append a plan step
    advance   Mark current step done, advance to next
    decide    Append a decision
    block     Append a blocker (and pause current step)
    note      Append an agent_history entry
    clear     Reset to empty (with --force)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = REPO_ROOT / "agent_stack" / ".runtime" / "session_state.json"
SCHEMA_VERSION = 1


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def empty_state() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "task": "",
        "started_utc": utc_now(),
        "updated_utc": utc_now(),
        "plan": [],
        "current_step": 0,
        "decisions": [],
        "blockers": [],
        "open_questions": [],
        "agent_history": [],
    }


def load() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return empty_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"session_state.json is corrupt: {e}")
    if data.get("version") != SCHEMA_VERSION:
        raise SystemExit(
            f"session_state.json is schema v{data.get('version')} but tool expects v{SCHEMA_VERSION}"
        )
    return data


def save(data: dict[str, Any]) -> None:
    data["updated_utc"] = utc_now()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    if STATE_PATH.exists() and not args.force:
        print(f"refusing to overwrite {STATE_PATH} without --force", file=sys.stderr)
        return 1
    state = empty_state()
    if args.task:
        state["task"] = args.task
    save(state)
    print(f"initialised {STATE_PATH}")
    return 0


def cmd_show(_: argparse.Namespace) -> int:
    print(json.dumps(load(), indent=2))
    return 0


def cmd_set_task(args: argparse.Namespace) -> int:
    state = load()
    state["task"] = args.task
    save(state)
    return 0


def cmd_add_step(args: argparse.Namespace) -> int:
    state = load()
    next_id = (max((s["id"] for s in state["plan"]), default=0) + 1)
    state["plan"].append({
        "id": next_id,
        "step": args.step,
        "owner": args.owner,
        "status": "pending",
    })
    save(state)
    print(f"added step {next_id}")
    return 0


def cmd_advance(_: argparse.Namespace) -> int:
    state = load()
    plan = state["plan"]
    cur = state["current_step"]
    if cur < len(plan):
        plan[cur]["status"] = "done"
    state["current_step"] = cur + 1
    if state["current_step"] < len(plan):
        plan[state["current_step"]]["status"] = "in_progress"
    save(state)
    print(f"advanced to step {state['current_step']}/{len(plan)}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    state = load()
    state["decisions"].append({
        "utc": utc_now(),
        "by": args.by,
        "decision": args.decision,
        "rationale": args.rationale or "",
    })
    save(state)
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    state = load()
    state["blockers"].append({
        "utc": utc_now(),
        "by": args.by,
        "blocker": args.blocker,
        "needs": args.needs,
    })
    cur = state["current_step"]
    if cur < len(state["plan"]):
        state["plan"][cur]["status"] = "blocked"
    save(state)
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    state = load()
    state["agent_history"].append({
        "utc": utc_now(),
        "agent": args.agent,
        "in": args.input,
        "out": args.output,
    })
    save(state)
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    if not args.force:
        print("refusing to clear without --force", file=sys.stderr)
        return 1
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    print("cleared")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--task", default=""); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("show"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("set-task"); s.add_argument("task"); s.set_defaults(fn=cmd_set_task)
    s = sub.add_parser("add-step"); s.add_argument("step"); s.add_argument("--owner", default=""); s.set_defaults(fn=cmd_add_step)
    s = sub.add_parser("advance"); s.set_defaults(fn=cmd_advance)
    s = sub.add_parser("decide"); s.add_argument("--by", required=True); s.add_argument("--decision", required=True); s.add_argument("--rationale", default=""); s.set_defaults(fn=cmd_decide)
    s = sub.add_parser("block"); s.add_argument("--by", required=True); s.add_argument("--blocker", required=True); s.add_argument("--needs", required=True); s.set_defaults(fn=cmd_block)
    s = sub.add_parser("note"); s.add_argument("--agent", required=True); s.add_argument("--input", required=True); s.add_argument("--output", required=True); s.set_defaults(fn=cmd_note)
    s = sub.add_parser("clear"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_clear)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Smoke-test the agent stack itself.

Verifies:
  - Required directories and files exist
  - Each .claude/agents/*.md has the required frontmatter (name, description, tools)
  - Each .claude/commands/*.md has frontmatter (description)
  - Every workflow referenced from a slash command exists
  - Every agent name referenced from AGENTS.md / CLAUDE.md / commands exists as a definition
  - destructive_ops.yaml loads cleanly via safety_check's loader
  - build_repo_map.py runs and produces non-empty output
  - session_state.py round-trips a small state mutation
  - Repo map's safety-critical files match the gate file's safety_critical_paths globs

Exit codes:
  0  all checks passed
  1  one or more checks failed
"""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STACK_ROOT = REPO_ROOT / "agent_stack"
CLAUDE = REPO_ROOT / ".claude"

EXPECTED_AGENTS = {
    "orchestrator", "repo-architect", "firmware-embedded", "platform-toolchain",
    "test-verification", "debug-triage", "docs-release", "safety-gate",
}

EXPECTED_COMMANDS = {
    "plan", "implement", "firmware-change", "validate",
    "triage", "repo-map", "safety-check", "release-notes",
}

EXPECTED_WORKFLOWS = {"feature", "bugfix", "firmware_change", "refactor", "release"}

REQUIRED_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "agent_stack/README.md",
    "agent_stack/conventions.md",
    "agent_stack/gates/safety_invariants.md",
    "agent_stack/gates/destructive_ops.yaml",
    "agent_stack/tools/build_repo_map.py",
    "agent_stack/tools/validate.py",
    "agent_stack/tools/safety_check.py",
    "agent_stack/tools/session_state.py",
    "agent_stack/tools/smoke_test.py",
    "agent_stack/.runtime/.gitignore",
]


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: int = 0

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passes += 1
            print(f"  PASS  {label}")
        else:
            self.failures.append(f"{label} — {detail}")
            print(f"  FAIL  {label}: {detail}")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip()
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


def main() -> int:
    c = Checker()
    print("=" * 60)
    print("agent_stack smoke test")
    print("=" * 60)

    # 1. Required files exist
    print("\n[1] Required files exist")
    for rel in REQUIRED_FILES:
        c.check(f"file: {rel}", (REPO_ROOT / rel).exists(), "missing")

    # 2. All expected agents present + frontmatter valid
    print("\n[2] Agent definitions")
    agents_dir = CLAUDE / "agents"
    seen_agents: set[str] = set()
    for agent_file in agents_dir.glob("*.md"):
        name = agent_file.stem
        seen_agents.add(name)
        fm = parse_frontmatter(agent_file)
        c.check(f"agent {name}: frontmatter has 'name'", "name" in fm)
        c.check(f"agent {name}: frontmatter name matches filename",
                fm.get("name") == name, f"got {fm.get('name')!r}")
        c.check(f"agent {name}: frontmatter has 'description'",
                bool(fm.get("description")))
        c.check(f"agent {name}: frontmatter has 'tools'",
                bool(fm.get("tools")))
    for missing in EXPECTED_AGENTS - seen_agents:
        c.check(f"agent {missing}: present", False, "definition missing")

    # 3. All expected commands present + frontmatter valid
    print("\n[3] Slash commands")
    cmd_dir = CLAUDE / "commands"
    seen_cmds: set[str] = set()
    for cmd_file in cmd_dir.glob("*.md"):
        name = cmd_file.stem
        seen_cmds.add(name)
        fm = parse_frontmatter(cmd_file)
        c.check(f"command /{name}: frontmatter has 'description'",
                bool(fm.get("description")))
    for missing in EXPECTED_COMMANDS - seen_cmds:
        c.check(f"command /{missing}: present", False, "definition missing")

    # 4. All expected workflows exist
    print("\n[4] Workflow templates")
    wf_dir = STACK_ROOT / "workflows"
    seen_wf = {p.stem for p in wf_dir.glob("*.md")}
    for w in EXPECTED_WORKFLOWS:
        c.check(f"workflow {w}.md", w in seen_wf, "missing")

    # 5. Cross-references: agent names in AGENTS.md / CLAUDE.md / commands all resolve
    print("\n[5] Cross-references")
    for src in (REPO_ROOT / "AGENTS.md", REPO_ROOT / "CLAUDE.md"):
        text = src.read_text(encoding="utf-8")
        for agent in EXPECTED_AGENTS:
            c.check(f"{src.name} mentions {agent}",
                    agent in text, f"{agent} not referenced in {src.name}")
    # Commands that reference subagent_type
    for cmd_file in cmd_dir.glob("*.md"):
        text = cmd_file.read_text(encoding="utf-8")
        for m in re.findall(r"subagent_type:\s*([a-z\-]+)", text):
            c.check(f"command /{cmd_file.stem} references known agent {m}",
                    m in EXPECTED_AGENTS, f"unknown agent {m}")

    # 6. destructive_ops.yaml loads via safety_check loader
    print("\n[6] Gate file loads")
    spec = importlib.util.spec_from_file_location(
        "safety_check", STACK_ROOT / "tools" / "safety_check.py")
    sc = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    try:
        spec.loader.exec_module(sc)  # type: ignore[union-attr]
        gate = sc.load_gate()
        c.check("destructive_ops.yaml parses", True)
        c.check("safety_critical_paths is non-empty", len(gate["safety_critical_paths"]) > 0)
        c.check("destructive_commands is non-empty", len(gate["destructive_commands"]) > 0)
    except Exception as e:  # noqa: BLE001
        c.check("destructive_ops.yaml parses", False, str(e))
        gate = {"safety_critical_paths": [], "destructive_commands": [], "sensitive_commands": [],
                "generated_paths": [], "never_commit_paths": []}

    # 7. build_repo_map.py runs and produces non-empty output
    print("\n[7] Repo map regenerates")
    rc = subprocess.run([sys.executable, str(STACK_ROOT / "tools" / "build_repo_map.py")],
                        cwd=str(REPO_ROOT), capture_output=True, text=True)
    c.check("build_repo_map.py exits 0", rc.returncode == 0, rc.stderr)
    c.check("repo_map.json exists", (STACK_ROOT / "repo_map.json").exists())
    c.check("repo_map.md exists", (STACK_ROOT / "repo_map.md").exists())
    if (STACK_ROOT / "repo_map.json").exists():
        data = json.loads((STACK_ROOT / "repo_map.json").read_text(encoding="utf-8"))
        c.check("repo_map.json has subprojects", len(data.get("subprojects", [])) >= 1)
        c.check("repo_map.json detected safety-critical files",
                len(data.get("safety_critical_files", [])) >= 1)

        # 8. Every safety-critical file the map detected matches at least one gate pattern
        print("\n[8] Map vs gate consistency")
        unmatched = []
        for f in data["safety_critical_files"]:
            if not any(fnmatch.fnmatch(f, pat) for pat in gate["safety_critical_paths"]):
                unmatched.append(f)
        c.check("every detected safety-critical file matches a gate pattern",
                not unmatched, f"unmatched: {unmatched}")

    # 9. session_state.py round-trip
    print("\n[9] session_state round-trip")
    state_path = STACK_ROOT / ".runtime" / "session_state.json"
    backup = state_path.read_text(encoding="utf-8") if state_path.exists() else None
    try:
        rc = subprocess.run([sys.executable, str(STACK_ROOT / "tools" / "session_state.py"),
                             "init", "--task", "smoke", "--force"],
                            cwd=str(REPO_ROOT), capture_output=True, text=True)
        c.check("session_state.py init", rc.returncode == 0, rc.stderr)
        rc = subprocess.run([sys.executable, str(STACK_ROOT / "tools" / "session_state.py"),
                             "add-step", "smoke step", "--owner", "orchestrator"],
                            cwd=str(REPO_ROOT), capture_output=True, text=True)
        c.check("session_state.py add-step", rc.returncode == 0, rc.stderr)
        rc = subprocess.run([sys.executable, str(STACK_ROOT / "tools" / "session_state.py"),
                             "show"], cwd=str(REPO_ROOT), capture_output=True, text=True)
        c.check("session_state.py show", rc.returncode == 0, rc.stderr)
        if rc.returncode == 0:
            data = json.loads(rc.stdout)
            c.check("session_state task set", data.get("task") == "smoke")
            c.check("session_state plan has 1 step", len(data.get("plan", [])) == 1)
    finally:
        # Restore the user's prior state, if any.
        if backup is not None:
            state_path.write_text(backup, encoding="utf-8")
        elif state_path.exists():
            state_path.unlink()

    # Summary
    print("\n" + "=" * 60)
    total = c.passes + len(c.failures)
    print(f"smoke test: {c.passes}/{total} checks passed")
    if c.failures:
        print(f"FAILURES ({len(c.failures)}):")
        for f in c.failures:
            print(f"  - {f}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

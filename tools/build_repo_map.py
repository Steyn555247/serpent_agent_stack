#!/usr/bin/env python3
"""
Build a machine + human readable repo map.

Walks the repo from the agent_stack parent and emits:
  - agent_stack/repo_map.json  (machine-readable)
  - agent_stack/repo_map.md    (human-readable, committable)

The map captures:
  - subprojects (directories with their own .git or recognisable build root)
  - language buckets (.py / .dart / .ino / .sh / .yaml)
  - per-subproject test entrypoints, build entrypoints, sim entrypoints
  - safety-critical files (matched by name)

Designed to be re-run after structural changes. Output is deterministic.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STACK_ROOT = REPO_ROOT / "agent_stack"

LANG_EXTS = {
    "python":  {".py"},
    "dart":    {".dart"},
    "arduino": {".ino"},
    "shell":   {".sh"},
    "config":  {".yaml", ".yml", ".toml", ".ini"},
    "docs":    {".md"},
}

SAFETY_PATTERNS = [
    "actuator_controller.py",
    "framing.py",
    "constants.py",
    "watchdog_monitor.py",
    "command_executor.py",
    "winch_controller.py",
    "control_server.py",
]

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", "build", ".dart_tool", ".idea",
    ".gradle", ".pub-cache", "venv", ".venv", ".runtime",
}


def is_subproject(path: Path) -> bool:
    """A directory is a 'subproject' if it has its own .git OR a recognisable build root."""
    if (path / ".git").exists():
        return True
    if (path / "pubspec.yaml").exists():
        return True
    if (path / "pyproject.toml").exists():
        return True
    # Python project root marker (e.g. pi_backend/, which has no .git on initial extraction
    # but is a stand-alone deployable Python service with its own requirements).
    if (path / "requirements.txt").exists():
        return True
    return False


def find_subprojects(root: Path, max_depth: int = 3) -> list[Path]:
    """Walk up to max_depth levels and collect every directory that looks like a subproject.

    Stops descending into a directory once it qualifies as a subproject (don't recurse
    into a subproject's children — those are owned by it).
    """
    found: list[Path] = []

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return
        for child in sorted(d.iterdir()):
            if not child.is_dir() or child.name in IGNORE_DIRS:
                continue
            if is_subproject(child):
                found.append(child)
                continue  # do not descend into a known subproject
            walk(child, depth + 1)

    walk(root, 1)
    return found


def language_counts(root: Path) -> dict[str, int]:
    counts = {lang: 0 for lang in LANG_EXTS}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            for lang, exts in LANG_EXTS.items():
                if ext in exts:
                    counts[lang] += 1
                    break
    return counts


def find_safety_critical(root: Path) -> list[str]:
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if fn in SAFETY_PATTERNS:
                rel = Path(dirpath, fn).relative_to(REPO_ROOT)
                hits.append(str(rel).replace("\\", "/"))
    return sorted(hits)


def find_entrypoints(sub: Path) -> dict[str, list[str]]:
    """Detect build/test/sim entrypoints per subproject."""
    out: dict[str, list[str]] = {"build": [], "test": [], "sim": [], "service": []}
    for p in sub.rglob("*"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        name = p.name.lower()
        if name in {"pubspec.yaml", "platformio.ini"}:
            out["build"].append(rel)
        if name in {"build_apk.bat", "build_apk.ps1"}:
            out["build"].append(rel)
        if name == "test_all.py" or name.startswith("test_") and name.endswith(".py"):
            out["test"].append(rel)
        if name in {"run_sim.py", "winch_sim.py", "run_stress_suite.py"}:
            out["sim"].append(rel)
        if name.endswith(".service"):
            out["service"].append(rel)
    for k in out:
        out[k] = sorted(set(out[k]))
    return out


def detect_subproject_kind(sub: Path) -> str:
    if (sub / "pubspec.yaml").exists():
        return "flutter"
    if (sub / "firmware").exists() or (sub / "robot_pi").exists() or (sub / "base_pi").exists():
        return "python+embedded"
    if (sub / "pyproject.toml").exists():
        return "python"
    if (sub / "requirements.txt").exists():
        return "python"
    return "unknown"


def build_map() -> dict[str, Any]:
    subs = find_subprojects(REPO_ROOT)
    data: dict[str, Any] = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "repo_root": str(REPO_ROOT).replace("\\", "/"),
        "subprojects": [],
        "safety_critical_files": find_safety_critical(REPO_ROOT),
    }
    for sub in subs:
        rel = str(sub.relative_to(REPO_ROOT)).replace("\\", "/")
        data["subprojects"].append({
            "path": rel,
            "kind": detect_subproject_kind(sub),
            "language_counts": language_counts(sub),
            "entrypoints": find_entrypoints(sub),
            "has_own_git": (sub / ".git").exists(),
        })
    return data


def render_md(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Repo map")
    lines.append("")
    lines.append(f"_Generated {data['generated_utc']} by `agent_stack/tools/build_repo_map.py`. Do not edit by hand — re-run the tool._")
    lines.append("")
    lines.append("## Subprojects")
    lines.append("")
    for sub in data["subprojects"]:
        lines.append(f"### `{sub['path']}/`  ({sub['kind']})")
        lines.append("")
        lines.append(f"- Has own `.git`: **{sub['has_own_git']}**")
        lc = sub["language_counts"]
        nonzero = {k: v for k, v in lc.items() if v}
        if nonzero:
            lines.append("- Files by language: " + ", ".join(f"{k}={v}" for k, v in nonzero.items()))
        ep = sub["entrypoints"]
        for category, items in ep.items():
            if not items:
                continue
            lines.append(f"- **{category}**:")
            for item in items[:25]:
                lines.append(f"  - `{item}`")
            if len(items) > 25:
                lines.append(f"  - …and {len(items) - 25} more")
        lines.append("")
    lines.append("## Safety-critical files")
    lines.append("")
    if not data["safety_critical_files"]:
        lines.append("_(none detected)_")
    else:
        for path in data["safety_critical_files"]:
            lines.append(f"- `{path}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-only", action="store_true",
                        help="Only emit JSON, skip the markdown render.")
    parser.add_argument("--stdout", action="store_true",
                        help="Print to stdout instead of writing files.")
    args = parser.parse_args()

    data = build_map()
    md = render_md(data)

    if args.stdout:
        if args.json_only:
            print(json.dumps(data, indent=2))
        else:
            print(md)
        return 0

    STACK_ROOT.mkdir(exist_ok=True)
    (STACK_ROOT / "repo_map.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not args.json_only:
        (STACK_ROOT / "repo_map.md").write_text(md, encoding="utf-8")
    print(f"Wrote {STACK_ROOT / 'repo_map.json'}")
    if not args.json_only:
        print(f"Wrote {STACK_ROOT / 'repo_map.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

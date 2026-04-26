#!/usr/bin/env python3
"""
Safety check — gate scanner.

Given a set of file paths and/or shell command strings, report which ones match
patterns in agent_stack/gates/destructive_ops.yaml.

Usage:
    safety_check.py --paths file1 file2 ...
    safety_check.py --commands "git push --force" "pio run -t upload"
    safety_check.py --paths file1 --commands "rm -rf foo" --json

Exit codes:
    0   nothing destructive
    1   destructive findings present
    2   gate file missing or malformed
    3   internal error

Findings include the matched pattern and a category:
    - safety_critical_path  : touching a safety-critical file
    - generated_path        : modifying a generated/runtime path
    - never_commit_path     : touching a file that must not be committed
    - destructive_command   : running a destructive shell command
    - sensitive_command     : running a flagged-but-allowed shell command
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE_PATH = REPO_ROOT / "agent_stack" / "gates" / "destructive_ops.yaml"


def _load_yaml_minimal(text: str) -> dict[str, Any]:
    """Tiny dependency-free loader for our specific gate file format.

    Supports: top-level mapping; list-of-strings values; comments; quoted strings.
    Does NOT support: nested mappings beyond one level, multi-line strings, anchors.
    Sufficient for `destructive_ops.yaml`.
    """
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    def strip_quotes(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] == '"':
            inner = s[1:-1]
            # Interpret YAML double-quoted escapes we actually use.
            return (inner
                    .replace(r"\\", "\x00").replace(r"\"", '"').replace(r"\n", "\n")
                    .replace("\x00", "\\"))
        if len(s) >= 2 and s[0] == s[-1] and s[0] == "'":
            return s[1:-1].replace("''", "'")
        return s

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        # list item under current key
        if line.startswith(" ") or line.startswith("\t"):
            if current_list is None:
                continue
            stripped = line.strip()
            if stripped.startswith("- "):
                current_list.append(strip_quotes(stripped[2:]))
            continue
        # top-level "key:" or "key: scalar"
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                current_key = key
                current_list = []
                data[key] = current_list
            else:
                data[key] = strip_quotes(val)
                current_key, current_list = None, None
    return data


def load_gate() -> dict[str, list[str]]:
    if not GATE_PATH.exists():
        raise SystemExit(f"gate file missing: {GATE_PATH}")
    raw = GATE_PATH.read_text(encoding="utf-8")
    parsed = _load_yaml_minimal(raw)
    out: dict[str, list[str]] = {}
    for key in ("safety_critical_paths", "generated_paths", "never_commit_paths",
                "destructive_commands", "sensitive_commands"):
        v = parsed.get(key, [])
        if not isinstance(v, list):
            raise SystemExit(f"gate file malformed: '{key}' should be a list")
        out[key] = [str(x) for x in v]
    return out


def _normalize_path(p: str) -> str:
    """Convert any user-supplied path to a repo-relative POSIX string."""
    pp = Path(p)
    if pp.is_absolute():
        try:
            pp = pp.relative_to(REPO_ROOT)
        except ValueError:
            pass
    return str(pp).replace("\\", "/")


def check_paths(paths: list[str], gate: dict[str, list[str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for p in paths:
        norm = _normalize_path(p)
        for category, key in (
            ("safety_critical_path", "safety_critical_paths"),
            ("generated_path", "generated_paths"),
            ("never_commit_path", "never_commit_paths"),
        ):
            for pattern in gate[key]:
                if fnmatch.fnmatch(norm, pattern):
                    findings.append({"category": category, "input": p, "matched": pattern})
                    break  # first match per category is enough
    return findings


def check_commands(commands: list[str], gate: dict[str, list[str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for cmd in commands:
        for category, key in (
            ("destructive_command", "destructive_commands"),
            ("sensitive_command", "sensitive_commands"),
        ):
            for pattern in gate[key]:
                try:
                    if re.search(pattern, cmd):
                        findings.append({"category": category, "input": cmd, "matched": pattern})
                        break
                except re.error as e:
                    findings.append({"category": "gate_regex_error", "input": pattern,
                                     "error": str(e)})
    return findings


def render_human(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "safety_check: no destructive findings"
    lines = [f"safety_check: {len(findings)} finding(s)"]
    for f in findings:
        lines.append(f"  [{f['category']}] {f['input']!r} matched {f.get('matched','')!r}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--paths", nargs="*", default=[], help="File paths to check.")
    p.add_argument("--commands", nargs="*", default=[], help="Shell command strings to check.")
    p.add_argument("--json", action="store_true", help="Emit JSON.")
    args = p.parse_args()

    try:
        gate = load_gate()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"safety_check: gate load error: {e}", file=sys.stderr)
        return 2

    findings = []
    findings += check_paths(args.paths, gate)
    findings += check_commands(args.commands, gate)

    # Treat sensitive_command as info, not blocking.
    blocking = [f for f in findings if f["category"] not in ("sensitive_command",)]

    if args.json:
        print(json.dumps({
            "findings": findings,
            "blocking_count": len(blocking),
            "ok": len(blocking) == 0,
        }, indent=2))
    else:
        print(render_human(findings))

    return 0 if not blocking else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"safety_check: internal error: {e}", file=sys.stderr)
        sys.exit(3)

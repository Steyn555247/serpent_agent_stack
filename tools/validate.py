#!/usr/bin/env python3
"""
Unified validator. Single entrypoint for the agent stack.

Subcommands:
  python      Run PI-HALOW-BRIDGE unittest suite (via scripts/test_all.py)
  flutter     Run flutter analyze + flutter test in the TrimUI app
  firmware    Build firmware/winch_station with PlatformIO if available
  sim         Run the bridge simulator for N seconds; assert no crash
  pi_backend  Run pi_backend tests if present; otherwise NO_TESTS_DEFINED
  all         Run every target available on this host

Exit codes (per target and aggregate):
  0   passed
  1   one or more targets failed
  2   target was skipped (tool missing, target not present)
  3   internal validator error

When --json is passed, a structured report is printed at the end.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STACK_ROOT = REPO_ROOT / "agent_stack"
LOG_DIR = STACK_ROOT / ".runtime" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

BRIDGE = REPO_ROOT / "pi_halow_bridge" / "PI-HALOW-BRIDGE"
TRIMUI = REPO_ROOT / "serpent_trimui_app"
FIRMWARE = BRIDGE / "firmware" / "winch_station"
PI_BACKEND = REPO_ROOT / "pi_backend"


def utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_log(name: str, content: str) -> Path:
    path = LOG_DIR / f"{name}-{utc_stamp()}.log"
    path.write_text(content, encoding="utf-8", errors="replace")
    _prune_logs(name)
    return path


def _prune_logs(name: str, keep: int = 10) -> None:
    """Keep only the most recent `keep` logs matching `{name}-*.log`.

    Ranks by mtime descending; unlinks the tail. Best-effort: any I/O error
    during prune is swallowed so a transient FS issue can't fail validation.
    """
    try:
        candidates = sorted(
            LOG_DIR.glob(f"{name}-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in candidates[keep:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except OSError:
        pass


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None,
         timeout_s: int = 600) -> tuple[int, str]:
    """Run a subprocess. Return (returncode, combined_output)."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def target_python() -> dict[str, Any]:
    """Run the bridge's own unittest runner."""
    runner = BRIDGE / "scripts" / "test_all.py"
    if not runner.exists():
        return {"target": "python", "status": "skipped", "code": 2,
                "reason": f"missing {runner}"}
    if not shutil.which(sys.executable):
        return {"target": "python", "status": "skipped", "code": 2,
                "reason": "python interpreter not available"}
    start = time.time()
    rc, out = _run([sys.executable, str(runner)], cwd=BRIDGE, timeout_s=900)
    log = write_log("validate-python", out)
    return {
        "target": "python",
        "status": "passed" if rc == 0 else "failed",
        "code": 0 if rc == 0 else 1,
        "duration_s": round(time.time() - start, 2),
        "log": str(log).replace("\\", "/"),
        "tail": out.splitlines()[-20:],
    }


def target_flutter() -> dict[str, Any]:
    if not TRIMUI.exists():
        return {"target": "flutter", "status": "skipped", "code": 2,
                "reason": f"missing {TRIMUI}"}
    if not shutil.which("flutter") and not shutil.which("flutter.bat"):
        return {"target": "flutter", "status": "skipped", "code": 2,
                "reason": "flutter SDK not on PATH"}
    flutter = "flutter.bat" if os.name == "nt" and shutil.which("flutter.bat") else "flutter"
    start = time.time()
    out_combined: list[str] = []
    rc_total = 0
    for sub in (["analyze"], ["test"]):
        rc, out = _run([flutter, *sub], cwd=TRIMUI, timeout_s=600)
        out_combined.append(f"--- flutter {' '.join(sub)} (rc={rc}) ---\n{out}")
        if rc != 0:
            rc_total = rc
    log = write_log("validate-flutter", "\n".join(out_combined))
    return {
        "target": "flutter",
        "status": "passed" if rc_total == 0 else "failed",
        "code": 0 if rc_total == 0 else 1,
        "duration_s": round(time.time() - start, 2),
        "log": str(log).replace("\\", "/"),
        "tail": "\n".join(out_combined).splitlines()[-20:],
    }


def target_firmware() -> dict[str, Any]:
    if not FIRMWARE.exists():
        return {"target": "firmware", "status": "skipped", "code": 2,
                "reason": f"missing {FIRMWARE}"}
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio:
        return {"target": "firmware", "status": "skipped", "code": 2,
                "reason": "platformio not on PATH (install with `pip install platformio`)"}
    if not (FIRMWARE / "platformio.ini").exists():
        return {"target": "firmware", "status": "skipped", "code": 2,
                "reason": "no platformio.ini in firmware/winch_station/"}
    start = time.time()
    rc, out = _run([pio, "run", "-d", str(FIRMWARE)], cwd=FIRMWARE, timeout_s=600)
    log = write_log("validate-firmware", out)
    return {
        "target": "firmware",
        "status": "passed" if rc == 0 else "failed",
        "code": 0 if rc == 0 else 1,
        "duration_s": round(time.time() - start, 2),
        "log": str(log).replace("\\", "/"),
        "tail": out.splitlines()[-20:],
    }


def target_sim(seconds: int = 8) -> dict[str, Any]:
    """Run the bridge simulator for N seconds. Pass = both processes stay alive."""
    sim = BRIDGE / "scripts" / "run_sim.py"
    if not sim.exists():
        return {"target": "sim", "status": "skipped", "code": 2,
                "reason": f"missing {sim}"}
    start = time.time()
    proc = subprocess.Popen(
        [sys.executable, str(sim)],
        cwd=str(BRIDGE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        try:
            out, _ = proc.communicate(timeout=seconds)
        except subprocess.TimeoutExpired:
            # Expected: sim runs forever, we tear it down after `seconds`.
            # On Windows, communicate() after kill() can re-raise
            # TimeoutExpired because OS reap is delayed; use the canonical
            # terminate-then-communicate-with-fallback pattern (the final
            # communicate() has no timeout — just wait for the kill to take).
            proc.terminate()
            try:
                out, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()
            ok = True
            rc = 0
        else:
            # sim exited on its own — that's a failure unless rc==0
            ok = proc.returncode == 0
            rc = proc.returncode
    except Exception as e:  # noqa: BLE001
        return {"target": "sim", "status": "failed", "code": 3,
                "reason": f"sim launch error: {e}",
                "duration_s": round(time.time() - start, 2)}
    log = write_log("validate-sim", out or "")
    return {
        "target": "sim",
        "status": "passed" if ok else "failed",
        "code": 0 if ok else 1,
        "duration_s": round(time.time() - start, 2),
        "log": str(log).replace("\\", "/"),
        "exited_early": rc != 0 and rc is not None and proc.returncode != 0,
        "tail": (out or "").splitlines()[-20:],
    }


def target_pi_backend() -> dict[str, Any]:
    """Run pi_backend tests if present. Otherwise emit NO_TESTS_DEFINED (skip, not fail)."""
    if not PI_BACKEND.exists():
        return {"target": "pi_backend", "status": "skipped", "code": 2,
                "reason": f"missing {PI_BACKEND}"}
    runner = PI_BACKEND / "scripts" / "test_all.py"
    tests_dir = PI_BACKEND / "tests"
    if runner.exists():
        if not shutil.which(sys.executable):
            return {"target": "pi_backend", "status": "skipped", "code": 2,
                    "reason": "python interpreter not available"}
        start = time.time()
        rc, out = _run([sys.executable, str(runner)], cwd=PI_BACKEND, timeout_s=600)
        log = write_log("validate-pi_backend", out)
        return {
            "target": "pi_backend",
            "status": "passed" if rc == 0 else "failed",
            "code": 0 if rc == 0 else 1,
            "duration_s": round(time.time() - start, 2),
            "log": str(log).replace("\\", "/"),
            "tail": out.splitlines()[-20:],
        }
    if tests_dir.exists() and any(tests_dir.glob("test_*.py")):
        if not shutil.which(sys.executable):
            return {"target": "pi_backend", "status": "skipped", "code": 2,
                    "reason": "python interpreter not available"}
        start = time.time()
        rc, out = _run([sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir),
                        "-p", "test_*.py", "-v"], cwd=PI_BACKEND, timeout_s=600)
        log = write_log("validate-pi_backend", out)
        return {
            "target": "pi_backend",
            "status": "passed" if rc == 0 else "failed",
            "code": 0 if rc == 0 else 1,
            "duration_s": round(time.time() - start, 2),
            "log": str(log).replace("\\", "/"),
            "tail": out.splitlines()[-20:],
        }
    return {"target": "pi_backend", "status": "skipped", "code": 2,
            "reason": "NO_TESTS_DEFINED (no scripts/test_all.py and no tests/test_*.py)"}


TARGETS = {
    "python":     target_python,
    "flutter":    target_flutter,
    "firmware":   target_firmware,
    "sim":        target_sim,
    "pi_backend": target_pi_backend,
}


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [r["status"] for r in results]
    if "failed" in statuses:
        agg = "failed"
        code = 1
    elif all(s == "skipped" for s in statuses):
        agg = "skipped"
        code = 2
    else:
        agg = "passed"
        code = 0
    return {
        "aggregate_status": agg,
        "aggregate_code": code,
        "results": results,
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }


def render_human(report: dict[str, Any]) -> str:
    lines = [f"validate.py — {report['aggregate_status'].upper()} (code {report['aggregate_code']})"]
    for r in report["results"]:
        marker = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}[r["status"]]
        dur = f"{r.get('duration_s', 0)}s"
        extra = f" — {r.get('reason', '')}" if r["status"] == "skipped" else ""
        lines.append(f"  [{marker}] {r['target']:<8} {dur}{extra}")
        if r["status"] == "failed" and r.get("tail"):
            lines.append("    last lines:")
            for line in r["tail"][-10:]:
                lines.append(f"      {line}")
            if r.get("log"):
                lines.append(f"    full log: {r['log']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", choices=[*TARGETS.keys(), "all"],
                        help="Which target to validate.")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON report to stdout.")
    parser.add_argument("--sim-seconds", type=int, default=8,
                        help="How long to run the sim target (default 8s).")
    args = parser.parse_args()

    if args.target == "all":
        targets = list(TARGETS.keys())
    else:
        targets = [args.target]

    results: list[dict[str, Any]] = []
    for t in targets:
        if t == "sim":
            results.append(target_sim(args.sim_seconds))
        else:
            results.append(TARGETS[t]())

    report = aggregate(results)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report))

    return report["aggregate_code"]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nvalidate.py interrupted")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        print(f"validate.py internal error: {e}", file=sys.stderr)
        sys.exit(3)

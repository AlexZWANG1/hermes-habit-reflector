#!/usr/bin/env python3
"""Hermes cron hook · 每天 4am 触发.

放在 ~/.hermes/hooks/on_cron.py 路径, Hermes 的 cron 调度器自动调用.
内部判断是否到点 / 是否 idle / 是否 cold-start, 满足才跑 reflector.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


def get_hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


def installed_at(state: dict) -> datetime:
    """When did the reflector first see the system? Used for cold-start week."""
    iso = state.get("installed_at")
    if not iso:
        now = datetime.now(timezone.utc).isoformat()
        state["installed_at"] = now
        return datetime.fromisoformat(now)
    return datetime.fromisoformat(iso)


def hours_since_last_run(state: dict) -> float:
    last = state.get("last_run_at")
    if not last:
        return 999.0
    return (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600.0


def is_user_idle_hours(threshold_hours: float = 1.0) -> bool:
    """Crude idle check: assume idle between 02:00-06:00 local time."""
    h = datetime.now().hour
    return 2 <= h <= 6


def message_count_last_30d(state_db_path: Path) -> int:
    """Count messages in the last 30 days."""
    if not state_db_path.exists():
        return 0
    import sqlite3
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
    conn = sqlite3.connect(str(state_db_path))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE timestamp >= ?", (cutoff,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else 0


def should_run(hermes_home: Path) -> tuple[bool, str]:
    """Return (should_run, reason)."""
    state_file = hermes_home / "habit_memory" / ".state.json"
    state = load_state(state_file)
    installed = installed_at(state)
    save_state(state_file, state)

    # Cold start: 第 1 周不跑
    days_since_install = (datetime.now(timezone.utc) - installed).days
    if days_since_install < 7:
        return False, f"cold_start week 1 (installed {days_since_install}d ago)"

    # idle check
    if not is_user_idle_hours():
        return False, "user not in idle window (02:00-06:00)"

    # interval check
    if hours_since_last_run(state) < 20:
        return False, f"only {hours_since_last_run(state):.1f}h since last run"

    # data sufficiency
    n = message_count_last_30d(hermes_home / "state.db")
    if n < 50:
        return False, f"only {n} messages in last 30d (<50)"

    return True, "all conditions met"


def main():
    logging.basicConfig(level=logging.INFO, format="[reflector-cron] %(message)s")
    hermes_home = get_hermes_home()
    state_file = hermes_home / "habit_memory" / ".state.json"

    ok, reason = should_run(hermes_home)
    print(f"[reflector-cron] should_run={ok} reason={reason}")
    if not ok:
        return

    # determine cold-start cap (first 2 successful runs cap at 0.84)
    state = load_state(state_file)
    successful_runs = state.get("successful_runs", 0)
    cold_start = successful_runs < 2

    # invoke CLI
    import subprocess
    cli_path = Path(__file__).parent.parent / "src" / "cli.py"
    cmd = [
        sys.executable, "-m", "src.cli", "run",
        "--real-api",
    ]
    if cold_start:
        cmd.append("--cold-start")

    print(f"[reflector-cron] invoking: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(cli_path.parent.parent), capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(f"[reflector-cron] ERROR (rc={res.returncode}):\n{res.stderr}")
        return

    # update state
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    state["successful_runs"] = successful_runs + 1
    save_state(state_file, state)
    print(f"[reflector-cron] done (run #{successful_runs + 1})")


if __name__ == "__main__":
    main()

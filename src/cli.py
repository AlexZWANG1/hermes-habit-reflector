"""CLI · python -m src.cli ..."""
from __future__ import annotations
import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .distiller import distill
from .promoter import promote_claims
from .render import write_daily_memory
from .blacklist import Blacklist


def get_hermes_home() -> Path:
    """Return $HERMES_HOME or ~/.hermes."""
    import os
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def setup_paths(reflector_root: Path):
    """Standard layout under reflector_root."""
    return {
        "habit_memory": reflector_root / "habit_memory",
        "candidates": reflector_root / "habit_memory" / "candidates",
        "rejected": reflector_root / "habit_memory" / "rejected",
        "backups": reflector_root / "habit_memory" / "backups",
        "blacklist": reflector_root / "habit_memory" / "rejected" / "_blacklist.json",
        "user_md": reflector_root / "memories" / "USER.md",
        "log": reflector_root / "logs" / "reflector.log",
    }


def cmd_run(args):
    """Run a full distill + promote cycle. Defaults to dry-run unless --real-api."""
    reflector_root = get_hermes_home() if not args.fixture else Path(args.work_dir or "./_workdir")
    p = setup_paths(reflector_root)
    for d in (p["habit_memory"], p["candidates"], p["rejected"], p["backups"], p["log"].parent):
        d.mkdir(parents=True, exist_ok=True)

    blacklist = Blacklist(p["blacklist"])

    fixture_path = Path(args.fixture) if args.fixture else None
    state_db_path = reflector_root / "state.db"
    cold_cap = 0.84 if args.cold_start else 1.0

    print(f"\n=== Hermes Habit Reflector · run ===")
    print(f"  reflector_root: {reflector_root}")
    print(f"  fixture: {fixture_path}")
    print(f"  dry_run: {not args.real_api}")
    print(f"  cold_start_cap: {cold_cap}\n")

    claims = distill(
        state_db_path=state_db_path,
        window_days=args.window_days,
        blacklist=blacklist,
        dry_run=not args.real_api,
        fixture_path=fixture_path,
        cold_start_cap=cold_cap,
    )
    print(f"Distilled {len(claims)} claims:")
    for c in claims:
        print(f"  · [{c.classification}] conf={c.confidence:.2f} · {c.claim[:60]}...")

    # Read fixture for session/message counts (real path would read state_db)
    if fixture_path and fixture_path.exists():
        msgs = json.loads(fixture_path.read_text())
        session_count = len({m["session_id"] for m in msgs})
        total_messages = len(msgs)
    else:
        session_count = 0
        total_messages = 0

    out_md = write_daily_memory(
        claims,
        p["habit_memory"],
        window_days=args.window_days,
        session_count=session_count,
        total_messages=total_messages,
    )
    print(f"\n✓ Wrote habit_memory: {out_md}")

    summary = promote_claims(
        claims,
        user_md_path=p["user_md"],
        candidates_dir=p["candidates"],
        backups_dir=p["backups"],
    )
    print(f"\nPromotion summary:")
    for k, v in summary.items():
        print(f"  · {k}: {v}")

    print(f"\n=== done ===\n")


def cmd_dry_run(args):
    args.real_api = False
    args.cold_start = False
    cmd_run(args)


def cmd_reject(args):
    p = setup_paths(get_hermes_home() if not args.work_dir else Path(args.work_dir))
    blacklist = Blacklist(p["blacklist"])

    # Find the claim in pending or USER.md
    for f in p["candidates"].glob("*.pending.json"):
        data = json.loads(f.read_text())
        if data.get("id") == args.claim_id:
            blacklist.add(
                classification=data["classification"],
                key_phrase=args.key_phrase or data["claim"][:30].lower(),
                reason=args.reason or "user reject",
            )
            f.unlink()
            print(f"✓ Rejected pending claim {args.claim_id}; blacklisted '{args.key_phrase or '...'}'")
            return

    # If in USER.md, remove the entry
    if p["user_md"].exists():
        lines = p["user_md"].read_text().splitlines()
        new_lines = []
        skip_next = False
        removed = False
        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue
            if args.claim_id in line:
                removed = True
                # skip the next continuation line ([conf ... ])
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("[conf"):
                    skip_next = True
                continue
            new_lines.append(line)
        if removed:
            p["user_md"].write_text("\n".join(new_lines))
            blacklist.add(
                classification="preference",
                key_phrase=args.key_phrase or args.claim_id,
                reason=args.reason or "user reject",
            )
            print(f"✓ Removed claim {args.claim_id} from USER.md; blacklisted")
            return

    print(f"✗ Claim {args.claim_id} not found in pending or USER.md")
    sys.exit(1)


def cmd_rollback(args):
    p = setup_paths(get_hermes_home() if not args.work_dir else Path(args.work_dir))
    backup_path = p["backups"] / f"{args.date}-USER.md.bak"
    if not backup_path.exists():
        print(f"✗ No backup at {backup_path}")
        sys.exit(1)

    p["user_md"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, p["user_md"])
    print(f"✓ Restored USER.md from {backup_path}")


def cmd_status(args):
    p = setup_paths(get_hermes_home() if not args.work_dir else Path(args.work_dir))
    print(f"\n=== Habit Reflector Status ===")
    print(f"  reflector root: {p['user_md'].parent.parent}")

    if p["user_md"].exists():
        n_entries = p["user_md"].read_text().count("\n- ")
        size = p["user_md"].stat().st_size
        print(f"  USER.md: {size} chars, {n_entries} entries")
    else:
        print(f"  USER.md: not yet created")

    pending = list(p["candidates"].glob("*.pending.json"))
    print(f"  pending review: {len(pending)}")
    for f in pending:
        d = json.loads(f.read_text())
        print(f"    · {d['id']}: {d['claim'][:60]}... (conf {d['confidence']:.2f})")

    candidates = list(p["candidates"].glob("*.candidate"))
    print(f"  skill candidates: {len(candidates)}")
    for f in candidates:
        print(f"    · {f.stem}")

    blacklist = Blacklist(p["blacklist"])
    print(f"  blacklist entries: {len(blacklist.all())}")

    daily = sorted(p["habit_memory"].glob("*.md"), reverse=True)[:5]
    print(f"  recent habit_memory files ({len(daily)}):")
    for f in daily:
        print(f"    · {f.name}")
    print()


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(prog="hermes-habit-reflector")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run
    p_run = sub.add_parser("run", help="Run distill + promote (defaults to dry-run)")
    p_run.add_argument("--real-api", action="store_true", help="Use real Anthropic API (else canned)")
    p_run.add_argument("--fixture", help="Use messages JSON fixture instead of state.db")
    p_run.add_argument("--work-dir", help="Override reflector root (for testing)")
    p_run.add_argument("--window-days", type=int, default=30)
    p_run.add_argument("--cold-start", action="store_true", help="Cap confidence at 0.84")
    p_run.set_defaults(func=cmd_run)

    # dry-run (alias)
    p_dry = sub.add_parser("dry-run", help="Run with canned response (no API call)")
    p_dry.add_argument("--fixture", required=False)
    p_dry.add_argument("--work-dir")
    p_dry.add_argument("--window-days", type=int, default=30)
    p_dry.set_defaults(func=cmd_dry_run)

    # reject
    p_rej = sub.add_parser("reject", help="Reject a claim + add to blacklist")
    p_rej.add_argument("claim_id")
    p_rej.add_argument("--key-phrase", help="Key phrase to blacklist (default: claim id)")
    p_rej.add_argument("--reason")
    p_rej.add_argument("--work-dir")
    p_rej.set_defaults(func=cmd_reject)

    # rollback
    p_rb = sub.add_parser("rollback", help="Restore USER.md from a date's backup")
    p_rb.add_argument("date", help="YYYY-MM-DD")
    p_rb.add_argument("--work-dir")
    p_rb.set_defaults(func=cmd_rollback)

    # status
    p_st = sub.add_parser("status", help="Show current reflector state")
    p_st.add_argument("--work-dir")
    p_st.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

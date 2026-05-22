"""Render · 把 List[Claim] 写成 habit_memory/YYYY-MM-DD.md."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from .schema import Claim


def render_habit_memory_md(
    claims: list[Claim],
    *,
    window_days: int,
    session_count: int,
    total_messages: int,
    distiller_cost_usd: float = 0.0,
    distiller_model: str = "claude-haiku-4-5",
) -> str:
    """Render a single day's habit_memory file."""
    now = datetime.now(timezone.utc)
    head = (
        "---\n"
        f"generated_at: {now.isoformat()}\n"
        f"window_days: {window_days}\n"
        f"session_count: {session_count}\n"
        f"total_messages: {total_messages}\n"
        f"distiller_model: {distiller_model}\n"
        f"distiller_cost_usd: {distiller_cost_usd:.4f}\n"
        f"schema_version: 1\n"
        "---\n\n"
    )
    if not claims:
        return head + "## No habits distilled\nNo durable patterns found in this window.\n"

    body_parts = []
    for c in claims:
        ev_lines = "\n".join(
            f"  - {e.session_id}:t{e.turn_n} \"{e.excerpt}\""
            for e in c.evidence
        )
        body_parts.append(
            f"## Habit · {c.classification} · id {c.id}\n"
            f"claim: {c.claim}\n"
            f"classification: {c.classification}\n"
            f"confidence: {c.confidence:.2f}\n"
            f"decay_at: {c.decay_at}\n"
            f"intervention: {c.intervention or '(none)'}\n"
            f"evidence:\n{ev_lines}\n"
        )

    summary = (
        "\n---\n\n"
        "## Summary\n"
        f"- Total claims: {len(claims)}\n"
        f"- Auto-promote candidates (conf ≥0.85): {sum(1 for c in claims if c.confidence >= 0.85)}\n"
        f"- Review queue (0.70 ≤ conf < 0.85): {sum(1 for c in claims if 0.70 <= c.confidence < 0.85)}\n"
        f"- Habit skill candidates: {sum(1 for c in claims if c.classification == 'habit')}\n"
    )

    return head + "\n".join(body_parts) + summary


def write_daily_memory(
    claims: list[Claim],
    habit_memory_dir: Path,
    **kwargs,
) -> Path:
    """Write today's habit_memory file."""
    habit_memory_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    out_path = habit_memory_dir / f"{today}.md"
    out_path.write_text(render_habit_memory_md(claims, **kwargs))
    return out_path

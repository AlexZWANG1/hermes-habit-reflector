"""Distiller · 读 messages → Haiku → 解析 List[Claim]."""
from __future__ import annotations
import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .schema import Claim, EvidenceRef, compute_confidence
from .blacklist import Blacklist

logger = logging.getLogger(__name__)


DISTILL_PROMPT_TEMPLATE = """You are a behavioral analyst examining a user's actual conversation
history with an AI agent (Hermes). Your job is to extract DURABLE
PATTERNS, not transient task state.

A pattern qualifies as a "habit" only if BOTH:
- (a) appears in ≥5 distinct turns across the window, AND
- (b) appears in ≥3 distinct sessions

Classifications:
- preference: stable user style (format, verbosity, tool choice)
- habit: high-frequency recurring task pattern (≥5 sessions)
- task: current ongoing task state (DO NOT include — short-lived)
- constraint: hard limit user explicitly stated

For each pattern output:
- claim (one sentence)
- classification
- evidence: 3+ {{session_id, turn_n, excerpt}}
- times_appeared (int)
- distinct_sessions (int)
- last_seen_within_days (int)
- user_explicit_confirmed (bool)
- intervention (concrete instruction for agent; optional)

DO NOT output current task state.
DO NOT output anything user explicitly told agent to forget.
DO NOT generate claims with <3 evidence items.
DO NOT generate claims matching this blacklist:
{blacklist}

Output strict JSON: {{"claims": [...]}}.

Conversation window (last {window_days} days):
{messages_text}
"""


def read_messages_from_state_db(db_path: Path, window_days: int) -> list[dict]:
    """Read messages from Hermes' state.db.

    Schema is from hermes_state.py: messages table with
    (session_id, role, content, timestamp, turn_n).
    """
    if not db_path.exists():
        logger.warning("state.db not found at %s; returning empty list", db_path)
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).timestamp()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT session_id, role, content, timestamp
            FROM messages
            WHERE timestamp >= ?
            ORDER BY session_id, timestamp ASC
            """,
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    out = []
    last_session = None
    turn_n = 0
    for r in rows:
        if r["session_id"] != last_session:
            last_session = r["session_id"]
            turn_n = 0
        turn_n += 1
        out.append({
            "session_id": r["session_id"],
            "role": r["role"],
            "content": r["content"],
            "timestamp": r["timestamp"],
            "turn_n": turn_n,
        })
    return out


def read_messages_from_fixture(fixture_path: Path) -> list[dict]:
    """For testing: load messages from a JSON fixture."""
    return json.loads(fixture_path.read_text())


def render_messages_for_prompt(messages: list[dict], max_chars: int = 80000) -> str:
    """Render messages compactly. Truncate to max_chars."""
    parts = []
    cur_session = None
    for m in messages:
        if m["session_id"] != cur_session:
            cur_session = m["session_id"]
            parts.append(f"\n=== session {cur_session[:12]} ===")
        role_short = "U" if m["role"] == "user" else "A"
        content = m["content"].replace("\n", " ").strip()
        if len(content) > 300:
            content = content[:297] + "..."
        parts.append(f"[t{m['turn_n']} {role_short}] {content}")
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[-max_chars:]  # 保留最新部分
    return text


def call_distiller_model(prompt: str, model: str = "claude-haiku-4-5", *,
                          dry_run: bool = False) -> dict:
    """Call the Anthropic Messages API.

    For dry_run=True, returns a canned response that exercises the parser.
    For production, uses the anthropic SDK. Network calls go here.
    """
    if dry_run:
        return _canned_response()

    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic SDK not installed. Run `pip install anthropic` or use --dry-run."
        )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    # 模型输出可能含 markdown code fence ```json ... ```
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


def _canned_response() -> dict:
    """Hard-coded response for dry-run (exercises the parser + downstream)."""
    return {
        "claims": [
            {
                "claim": "用户强偏好结构化输出（表格 + bullet）而非 prose",
                "classification": "preference",
                "evidence": [
                    {"session_id": "s_dry_001", "turn_n": 1, "excerpt": "用表格"},
                    {"session_id": "s_dry_002", "turn_n": 3, "excerpt": "改成 bullet"},
                    {"session_id": "s_dry_003", "turn_n": 1, "excerpt": "// 表格列出"},
                    {"session_id": "s_dry_004", "turn_n": 2, "excerpt": "table please"},
                    {"session_id": "s_dry_005", "turn_n": 1, "excerpt": "bullet 不要 prose"},
                ],
                "times_appeared": 14,
                "distinct_sessions": 8,
                "last_seen_within_days": 2,
                "user_explicit_confirmed": True,
                "intervention": "session 启动时优先使用表格 + bullet 格式输出",
            },
            {
                "claim": "高频任务：读 paper → 出表格 critique（候选 skill）",
                "classification": "habit",
                "evidence": [
                    {"session_id": "s_dry_010", "turn_n": 1, "excerpt": "看 SWE-bench Pro paper"},
                    {"session_id": "s_dry_011", "turn_n": 1, "excerpt": "看 METR paper"},
                    {"session_id": "s_dry_012", "turn_n": 1, "excerpt": "读一下这篇 论文"},
                ],
                "times_appeared": 6,
                "distinct_sessions": 5,
                "last_seen_within_days": 3,
                "user_explicit_confirmed": False,
                "intervention": "promote 为 skill: paper-summary-table",
            },
            {
                "claim": "工作日上午 10-13 点出现短 session 高密度（4-6 turn 完成）",
                "classification": "preference",
                "evidence": [
                    {"session_id": "s_dry_020", "turn_n": 4, "excerpt": "完成"},
                    {"session_id": "s_dry_021", "turn_n": 5, "excerpt": "搞定"},
                    {"session_id": "s_dry_022", "turn_n": 4, "excerpt": "OK"},
                ],
                "times_appeared": 12,
                "distinct_sessions": 9,
                "last_seen_within_days": 5,
                "user_explicit_confirmed": False,
                "intervention": "白天 session 启动时偏好短回答 + 跳过预热",
            },
        ]
    }


def parse_claims(raw: dict, blacklist: Optional[Blacklist] = None) -> list[Claim]:
    """Parse Haiku response → List[Claim] with confidence recomputed locally."""
    claims = []
    for c in raw.get("claims", []):
        # Recompute confidence locally — don't trust model's self-assessment
        confidence = compute_confidence(
            times_appeared=c.get("times_appeared", 0),
            distinct_sessions=c.get("distinct_sessions", 0),
            last_seen_within_days=c.get("last_seen_within_days", 999),
            user_explicit_confirmed=c.get("user_explicit_confirmed", False),
        )
        # Apply blacklist
        if blacklist is not None:
            blocked = blacklist.is_blocked(c["classification"], c["claim"])
            if blocked:
                logger.info("Claim blocked by blacklist (matched '%s'): %s", blocked, c["claim"])
                continue
        # Build evidence
        evidence = [EvidenceRef(**e) for e in c.get("evidence", [])]
        if len(evidence) < 3:
            logger.warning("Dropping claim with <3 evidence: %s", c.get("claim"))
            continue
        try:
            claim = Claim(
                claim=c["claim"],
                classification=c["classification"],
                evidence=evidence,
                confidence=confidence,
                intervention=c.get("intervention"),
            )
            claims.append(claim)
        except (ValueError, KeyError) as e:
            logger.warning("Failed to build Claim from %r: %s", c, e)
    return claims


def distill(
    state_db_path: Path,
    *,
    window_days: int = 30,
    blacklist: Optional[Blacklist] = None,
    dry_run: bool = False,
    fixture_path: Optional[Path] = None,
    cold_start_cap: float = 1.0,  # 1.0 = no cap; 0.84 = cold-start cap
) -> list[Claim]:
    """Top-level pipeline. Returns parsed Claims (possibly capped)."""
    if fixture_path is not None:
        messages = read_messages_from_fixture(fixture_path)
    else:
        messages = read_messages_from_state_db(state_db_path, window_days)
    logger.info("Loaded %d messages across %d sessions", len(messages),
                len({m["session_id"] for m in messages}))

    if len(messages) < 10:
        logger.warning("Too few messages (%d < 10); skipping distill", len(messages))
        return []

    blacklist_text = "(empty)" if blacklist is None else json.dumps(blacklist.all(), ensure_ascii=False)
    prompt = DISTILL_PROMPT_TEMPLATE.format(
        window_days=window_days,
        messages_text=render_messages_for_prompt(messages),
        blacklist=blacklist_text,
    )
    raw = call_distiller_model(prompt, dry_run=dry_run)
    claims = parse_claims(raw, blacklist=blacklist)

    # Apply cold-start cap if requested
    if cold_start_cap < 1.0:
        for c in claims:
            if c.confidence > cold_start_cap:
                c.confidence = cold_start_cap

    return claims

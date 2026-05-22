"""Promoter · 把 claim 写入 USER.md / candidates / pending."""
from __future__ import annotations
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .schema import Claim

logger = logging.getLogger(__name__)

AUTO_PROMOTE_THRESHOLD = 0.85
QUEUE_FOR_REVIEW_THRESHOLD = 0.70


def render_user_md_entry(claim: Claim) -> str:
    """Render a single USER.md line."""
    sessions = len({e.session_id for e in claim.evidence})
    return (
        f"- {claim.claim}\n"
        f"  [conf {claim.confidence:.2f} · {sessions} sessions · "
        f"decay {claim.decay_at} · id {claim.id}]"
    )


def backup_user_md(user_md_path: Path, backups_dir: Path) -> Path:
    """Copy USER.md to backups/ before modifying."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    backup_path = backups_dir / f"{today}-USER.md.bak"
    if user_md_path.exists():
        shutil.copy2(user_md_path, backup_path)
        logger.info("Backed up USER.md → %s", backup_path)
    return backup_path


def append_to_user_md(user_md_path: Path, claim: Claim, max_chars: int = 1375) -> bool:
    """Append a claim entry to USER.md, respecting Hermes' 1375 char limit.

    Returns True if appended, False if budget exceeded.
    """
    entry = render_user_md_entry(claim)
    existing = user_md_path.read_text() if user_md_path.exists() else ""

    # Skip exact duplicate
    if claim.id in existing:
        logger.info("Claim %s already in USER.md; skipping", claim.id)
        return False

    new_content = (existing + "\n" + entry) if existing else entry
    if len(new_content) > max_chars:
        logger.warning(
            "USER.md char budget exceeded (%d > %d); rejecting claim %s",
            len(new_content), max_chars, claim.id,
        )
        return False

    user_md_path.parent.mkdir(parents=True, exist_ok=True)
    user_md_path.write_text(new_content)
    logger.info("Promoted claim %s → USER.md (conf %.2f)", claim.id, claim.confidence)
    return True


def write_pending(claim: Claim, candidates_dir: Path) -> Path:
    """Write a mid-confidence claim to candidates/ for next-session user review."""
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / f"{claim.id}.pending.json"
    path.write_text(claim.to_json())
    logger.info("Queued claim %s for review (conf %.2f)", claim.id, claim.confidence)
    return path


def write_skill_candidate(claim: Claim, candidates_dir: Path) -> Path:
    """If claim is a `habit` classification, write a skill-candidate marker for Curator."""
    candidates_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "-" for c in claim.claim.lower())[:60].strip("-")
    path = candidates_dir / f"{safe_name}.candidate"
    payload = {
        "claim_id": claim.id,
        "claim": claim.claim,
        "intervention": claim.intervention,
        "evidence_count": len(claim.evidence),
        "confidence": claim.confidence,
        "created_at": claim.created_at,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    logger.info("Wrote skill candidate %s for Curator pickup", path.name)
    return path


def promote_claims(
    claims: list[Claim],
    *,
    user_md_path: Path,
    candidates_dir: Path,
    backups_dir: Path,
    auto_threshold: float = AUTO_PROMOTE_THRESHOLD,
    review_threshold: float = QUEUE_FOR_REVIEW_THRESHOLD,
) -> dict:
    """Promote claims by confidence bucket.

    Returns a summary dict with counts.
    """
    summary = {
        "promoted_to_usermd": 0,
        "queued_for_review": 0,
        "dropped_low_conf": 0,
        "skill_candidates": 0,
        "budget_rejected": 0,
    }

    if any(c.confidence >= auto_threshold for c in claims):
        backup_user_md(user_md_path, backups_dir)

    for claim in claims:
        # Skill candidate writeout is orthogonal to promotion bucket
        if claim.classification == "habit":
            write_skill_candidate(claim, candidates_dir)
            summary["skill_candidates"] += 1

        if claim.confidence >= auto_threshold:
            if append_to_user_md(user_md_path, claim):
                summary["promoted_to_usermd"] += 1
            else:
                summary["budget_rejected"] += 1
        elif claim.confidence >= review_threshold:
            write_pending(claim, candidates_dir)
            summary["queued_for_review"] += 1
        else:
            summary["dropped_low_conf"] += 1

    return summary

"""Claim dataclass + 序列化"""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional


CLASSIFICATIONS = ("preference", "habit", "task", "constraint")
DEFAULT_DECAY_DAYS = {
    "preference": 90,
    "habit": 30,
    "task": 7,
    "constraint": 180,
}


@dataclass
class EvidenceRef:
    session_id: str
    turn_n: int
    excerpt: str  # ≤80 char

    def __post_init__(self) -> None:
        if len(self.excerpt) > 80:
            self.excerpt = self.excerpt[:77] + "..."


@dataclass
class Claim:
    """A single behavioral pattern extracted by the distiller."""

    claim: str
    classification: str
    evidence: list[EvidenceRef]
    confidence: float
    intervention: Optional[str] = None
    decay_at: Optional[str] = None
    source: str = "reflector"
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_reinforced: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"classification must be in {CLASSIFICATIONS}, got {self.classification}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if len(self.evidence) < 3:
            raise ValueError(f"a Claim requires ≥3 evidence items, got {len(self.evidence)}")
        if self.decay_at is None:
            days = DEFAULT_DECAY_DAYS[self.classification]
            self.decay_at = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence"] = [asdict(e) for e in self.evidence]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        evidence = [EvidenceRef(**e) for e in d.pop("evidence", [])]
        return cls(evidence=evidence, **d)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.decay_at < now.date().isoformat()


def compute_confidence(
    *,
    times_appeared: int,
    distinct_sessions: int,
    last_seen_within_days: int,
    user_explicit_confirmed: bool = False,
) -> float:
    """3 信号 + 起步 0.1; 显式 user 确认 +0.25 上限 1.0."""
    score = 0.10
    if times_appeared >= 5:
        score += 0.25
    if distinct_sessions >= 3:
        score += 0.25
    if last_seen_within_days <= 7:
        score += 0.25
    if user_explicit_confirmed:
        score += 0.25
    return min(score, 1.0)

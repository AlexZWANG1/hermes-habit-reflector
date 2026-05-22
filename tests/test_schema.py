"""Unit tests · schema.py."""
import pytest
from datetime import datetime, timezone, timedelta
from src.schema import Claim, EvidenceRef, compute_confidence


def make_evidence(n=3):
    return [
        EvidenceRef(session_id=f"s{i}", turn_n=1, excerpt=f"用表格 #{i}")
        for i in range(n)
    ]


def test_claim_requires_3_evidence():
    with pytest.raises(ValueError, match="≥3 evidence"):
        Claim(
            claim="test",
            classification="preference",
            evidence=make_evidence(2),
            confidence=0.9,
        )


def test_claim_validates_classification():
    with pytest.raises(ValueError, match="classification"):
        Claim(
            claim="test",
            classification="unknown",
            evidence=make_evidence(3),
            confidence=0.9,
        )


def test_claim_validates_confidence_range():
    with pytest.raises(ValueError, match="confidence"):
        Claim(
            claim="test",
            classification="preference",
            evidence=make_evidence(3),
            confidence=1.5,
        )


def test_claim_auto_assigns_decay():
    c = Claim(
        claim="test",
        classification="preference",
        evidence=make_evidence(3),
        confidence=0.9,
    )
    # preference 默认 90 天
    expected = (datetime.now(timezone.utc) + timedelta(days=90)).date().isoformat()
    assert c.decay_at == expected


def test_compute_confidence_all_signals():
    c = compute_confidence(
        times_appeared=5,
        distinct_sessions=3,
        last_seen_within_days=7,
        user_explicit_confirmed=False,
    )
    assert c == 0.85


def test_compute_confidence_with_explicit():
    c = compute_confidence(
        times_appeared=5,
        distinct_sessions=3,
        last_seen_within_days=7,
        user_explicit_confirmed=True,
    )
    assert c == 1.0


def test_compute_confidence_partial():
    c = compute_confidence(
        times_appeared=2,    # not ≥5
        distinct_sessions=4,
        last_seen_within_days=3,
        user_explicit_confirmed=False,
    )
    # 起步 0.1 + sessions 0.25 + recency 0.25 = 0.6
    assert c == pytest.approx(0.6)


def test_claim_roundtrip():
    c1 = Claim(
        claim="用户偏好表格",
        classification="preference",
        evidence=make_evidence(3),
        confidence=0.9,
        intervention="始终用表格输出",
    )
    d = c1.to_dict()
    c2 = Claim.from_dict(d)
    assert c2.claim == c1.claim
    assert len(c2.evidence) == 3
    assert c2.confidence == 0.9

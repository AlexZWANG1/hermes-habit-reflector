"""端到端 dry-run · 验证 demo 能跑通."""
import json
import tempfile
from pathlib import Path

import pytest

from src.distiller import distill
from src.promoter import promote_claims
from src.render import write_daily_memory
from src.blacklist import Blacklist


@pytest.fixture
def fixture_path():
    return Path(__file__).parent.parent / "examples" / "14-session-fixture.json"


@pytest.fixture
def work_dir(tmp_path):
    """Temporary reflector work dir per test."""
    d = tmp_path / "reflector"
    (d / "habit_memory" / "candidates").mkdir(parents=True)
    (d / "habit_memory" / "rejected").mkdir(parents=True)
    (d / "habit_memory" / "backups").mkdir(parents=True)
    (d / "memories").mkdir(parents=True)
    return d


def test_dry_run_full_pipeline(fixture_path, work_dir):
    """端到端: 读 fixture → distill (canned) → render → promote."""
    blacklist = Blacklist(work_dir / "habit_memory" / "rejected" / "_blacklist.json")

    claims = distill(
        state_db_path=work_dir / "state.db",  # 不存在, 会用 fixture_path
        window_days=30,
        blacklist=blacklist,
        dry_run=True,
        fixture_path=fixture_path,
    )

    assert len(claims) >= 3, f"expected ≥3 claims, got {len(claims)}"

    # 至少 1 条 conf ≥0.85 (canned response 有)
    high_conf = [c for c in claims if c.confidence >= 0.85]
    assert len(high_conf) >= 1, "expected at least 1 high-confidence claim"

    # 至少 1 条 habit 分类 (canned response 含 paper-summary habit)
    habits = [c for c in claims if c.classification == "habit"]
    assert len(habits) >= 1, "expected at least 1 habit-class claim"

    # 渲染日报
    out_md = write_daily_memory(
        claims,
        work_dir / "habit_memory",
        window_days=30,
        session_count=14,
        total_messages=29,
    )
    assert out_md.exists()
    content = out_md.read_text()
    assert "schema_version: 1" in content
    assert "## Habit" in content
    assert "evidence:" in content

    # Promote
    summary = promote_claims(
        claims,
        user_md_path=work_dir / "memories" / "USER.md",
        candidates_dir=work_dir / "habit_memory" / "candidates",
        backups_dir=work_dir / "habit_memory" / "backups",
    )

    assert summary["promoted_to_usermd"] >= 1, f"expected ≥1 promoted, got {summary}"
    assert summary["skill_candidates"] >= 1, f"expected ≥1 skill candidate, got {summary}"

    user_md = (work_dir / "memories" / "USER.md").read_text()
    assert "conf 0." in user_md
    assert len(user_md) <= 1375, f"USER.md exceeded char limit: {len(user_md)} > 1375"


def test_blacklist_filters(fixture_path, work_dir):
    """blacklist 命中的 claim 不应出现在结果里."""
    blacklist = Blacklist(work_dir / "habit_memory" / "rejected" / "_blacklist.json")
    blacklist.add("preference", "表格", reason="user does not want this rule")

    claims = distill(
        state_db_path=work_dir / "state.db",
        blacklist=blacklist,
        dry_run=True,
        fixture_path=fixture_path,
    )

    for c in claims:
        if c.classification == "preference":
            assert "表格" not in c.claim, f"blacklist failed: {c.claim}"


def test_cold_start_caps_confidence(fixture_path, work_dir):
    """cold_start_cap=0.84 时所有 conf 不超过 0.84."""
    claims = distill(
        state_db_path=work_dir / "state.db",
        dry_run=True,
        fixture_path=fixture_path,
        cold_start_cap=0.84,
    )

    for c in claims:
        assert c.confidence <= 0.84, f"cold-start cap failed: {c.confidence}"


def test_usermd_char_budget(fixture_path, work_dir):
    """promote 后 USER.md 不超过 1375 字符."""
    blacklist = Blacklist(work_dir / "habit_memory" / "rejected" / "_blacklist.json")
    claims = distill(
        state_db_path=work_dir / "state.db",
        blacklist=blacklist,
        dry_run=True,
        fixture_path=fixture_path,
    )
    promote_claims(
        claims,
        user_md_path=work_dir / "memories" / "USER.md",
        candidates_dir=work_dir / "habit_memory" / "candidates",
        backups_dir=work_dir / "habit_memory" / "backups",
    )
    user_md = (work_dir / "memories" / "USER.md").read_text()
    assert len(user_md) <= 1375

"""hermes-habit-reflector · 给 Hermes Agent 加的第 6 层自学习模块.

每天凌晨 4 点 retrospective 蒸馏 30 天对话历史, 抽取稳定 user habit,
自动写入 USER.md 或队列等用户审.

使用:
  python -m src.cli dry-run --fixture examples/14-session-fixture.json
  python -m src.cli run                       # 真跑, 接 Anthropic SDK
  python -m src.cli reject <claim_id>
  python -m src.cli rollback 2026-05-22
"""

__version__ = "0.1.0"

from .schema import Claim, EvidenceRef, compute_confidence
from .distiller import distill
from .promoter import promote_claims
from .blacklist import Blacklist
from .render import write_daily_memory

__all__ = [
    "Claim",
    "EvidenceRef",
    "compute_confidence",
    "distill",
    "promote_claims",
    "Blacklist",
    "write_daily_memory",
]

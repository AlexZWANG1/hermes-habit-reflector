#!/usr/bin/env python3
"""
Verbose trace · 展示 Reflector 跑一次的完整 input/output.

每一阶段都打印:
- 上一阶段进来的 input
- 这一阶段做了什么
- 输出给下一阶段的 output

跑法:
  python3 scripts/trace_pipeline.py
"""
import sys
import os
import json
from pathlib import Path

# Ensure imports work from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.distiller import (
    read_messages_from_fixture,
    render_messages_for_prompt,
    DISTILL_PROMPT_TEMPLATE,
    call_distiller_model,
    parse_claims,
)
from src.blacklist import Blacklist
from src.schema import compute_confidence
from src.render import render_habit_memory_md, write_daily_memory
from src.promoter import promote_claims, render_user_md_entry


def banner(title: str, width: int = 78) -> None:
    print()
    print("═" * width)
    print(f" {title}")
    print("═" * width)


def section(title: str, width: int = 78) -> None:
    print()
    print("─" * width)
    print(f"  {title}")
    print("─" * width)


def main():
    repo = Path(__file__).parent.parent
    fixture_path = repo / "examples" / "14-session-fixture.json"
    work_dir = Path("/tmp/trace-run")

    # Clean
    import shutil
    if work_dir.exists():
        shutil.rmtree(work_dir)
    for sub in ("memories", "habit_memory/candidates", "habit_memory/rejected", "habit_memory/backups"):
        (work_dir / sub).mkdir(parents=True)

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 1 · INPUT · 从 fixture 读出来的原始 messages")
    # ──────────────────────────────────────────────────────────────
    print(f"  来源: {fixture_path}")
    print(f"  这就是 Reflector 平时在生产环境从 ~/.hermes/state.db 读的内容,")
    print(f"  本次 demo 用 fixture 模拟. 真实跑 sqlite3 SELECT * FROM messages.")

    messages = read_messages_from_fixture(fixture_path)
    print()
    print(f"  → 共读出 {len(messages)} 条 messages, 跨 {len({m['session_id'] for m in messages})} 个 session")
    print()
    print("  前 5 条样本 (全 27 条结构相同):")
    for m in messages[:5]:
        print(f"    session={m['session_id'][:20]:20s} role={m['role']:9s} turn={m['turn_n']} content={m['content'][:50]!r}")
    print(f"    ... ({len(messages) - 5} 条略)")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 2 · TRANSFORM · 把 messages 压缩成 prompt 友好格式")
    # ──────────────────────────────────────────────────────────────
    print("  逻辑: render_messages_for_prompt() 把 messages 平铺成:")
    print("    === session <id> ===")
    print("    [t1 U] <content>")
    print("    [t2 A] <content>")
    print("    ...")
    print("  目的: 让模型看到 session 边界 + role + turn 编号 + content")

    rendered_text = render_messages_for_prompt(messages)
    print()
    print(f"  → 压缩后总长: {len(rendered_text)} 字符")
    print()
    print("  前 600 字符预览:")
    print("  " + "─" * 70)
    for line in rendered_text[:600].split("\n"):
        print(f"  │ {line}")
    print("  " + "─" * 70)
    print(f"  ... (省略 {len(rendered_text) - 600} 字符)")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 3 · INPUT · 完整 distill prompt (喂给 Haiku 4.5)")
    # ──────────────────────────────────────────────────────────────
    print("  逻辑: 把 DISTILL_PROMPT_TEMPLATE 用 window_days/blacklist/messages_text 填空.")
    print("  blacklist 这次是空的, 所以填 '(empty)'.")

    prompt = DISTILL_PROMPT_TEMPLATE.format(
        window_days=30,
        messages_text=rendered_text,
        blacklist="(empty)",
    )
    print()
    print(f"  → 完整 prompt 总长: {len(prompt)} 字符 (~{len(prompt) // 4} tokens 估)")
    print()
    print("  ╔════ Prompt 完整内容 (除 messages 部分截断) ════════════════════════╗")
    print()
    # 显示 prompt 但截断中间太长的 messages 部分
    head, _, tail = prompt.partition("Conversation window (last 30 days):")
    print(head + "Conversation window (last 30 days):")
    print()
    print(f"  [27 条 messages 渲染后的 {len(rendered_text)} 字符插在这里]")
    print(f"  [上面 STAGE 2 的输出整体灌进来]")
    print()
    print("  ╚═══════════════════════════════════════════════════════════════════╝")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 4 · OUTPUT · Haiku 模拟返回 (dry-run · canned response)")
    # ──────────────────────────────────────────────────────────────
    print("  真跑时这里是 anthropic SDK 调 Haiku 4.5 的返回 JSON.")
    print("  dry-run 模式用硬编码 canned 响应 (源码 distiller._canned_response()).")
    print()
    print("  这次返回的完整 JSON:")
    raw_response = call_distiller_model(prompt, dry_run=True)
    print()
    print(json.dumps(raw_response, ensure_ascii=False, indent=2))

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 5 · TRANSFORM · parser 解析 + confidence 本地重算")
    # ──────────────────────────────────────────────────────────────
    print("  关键设计: model 返回的是 raw 信号数 (times_appeared, distinct_sessions ...)")
    print("  confidence 用本地公式重算 (compute_confidence), 不信模型自评.")
    print()
    print("  公式:")
    print("    起步                                +0.10")
    print("    times_appeared >= 5                +0.25")
    print("    distinct_sessions >= 3             +0.25")
    print("    last_seen_within_days <= 7         +0.25")
    print("    user_explicit_confirmed == True    +0.25  (可选)")
    print("    ─────────────────────────────────")
    print("    最高                                1.00")

    blacklist = Blacklist(work_dir / "habit_memory" / "rejected" / "_blacklist.json")
    claims = parse_claims(raw_response, blacklist=blacklist)

    print()
    print(f"  → 解析出 {len(claims)} 条 Claim 对象")
    print()
    for i, c in enumerate(claims, 1):
        section(f"Claim #{i}")
        print(f"  id:             {c.id}")
        print(f"  classification: {c.classification}")
        print(f"  claim:          {c.claim}")
        print()
        # 重算 confidence 拆解
        signals = raw_response["claims"][i-1]
        print("  Confidence 拆解 (从模型 raw 信号本地重算):")
        print(f"    起步                                                 +0.10")
        if signals.get("times_appeared", 0) >= 5:
            print(f"    times_appeared={signals['times_appeared']} ≥ 5                              +0.25")
        else:
            print(f"    times_appeared={signals['times_appeared']} < 5                              +0.00")
        if signals.get("distinct_sessions", 0) >= 3:
            print(f"    distinct_sessions={signals['distinct_sessions']} ≥ 3                            +0.25")
        else:
            print(f"    distinct_sessions={signals['distinct_sessions']} < 3                            +0.00")
        if signals.get("last_seen_within_days", 999) <= 7:
            print(f"    last_seen_within_days={signals['last_seen_within_days']} ≤ 7                       +0.25")
        else:
            print(f"    last_seen_within_days={signals['last_seen_within_days']} > 7                       +0.00")
        if signals.get("user_explicit_confirmed", False):
            print(f"    user_explicit_confirmed=True                         +0.25")
        else:
            print(f"    user_explicit_confirmed=False                        +0.00")
        print(f"    ─────────────────────────────────────────────")
        print(f"    最终 confidence:                                     {c.confidence:.2f}")
        print()
        print(f"  decay_at:       {c.decay_at}  (preference→90d / habit→30d / task→7d)")
        print(f"  intervention:   {c.intervention}")
        print(f"  evidence ({len(c.evidence)} 条):")
        for e in c.evidence:
            print(f"    · {e.session_id}:t{e.turn_n}  \"{e.excerpt}\"")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 6 · OUTPUT · 渲染日报 habit_memory/YYYY-MM-DD.md")
    # ──────────────────────────────────────────────────────────────
    print("  逻辑: render.write_daily_memory() 把 List[Claim] 渲染成 markdown.")

    daily_path = write_daily_memory(
        claims,
        work_dir / "habit_memory",
        window_days=30,
        session_count=len({m["session_id"] for m in messages}),
        total_messages=len(messages),
    )

    print()
    print(f"  → 写到: {daily_path}")
    print(f"  → 大小: {daily_path.stat().st_size} 字节")
    print()
    print("  完整文件内容:")
    print("  ╔" + "═" * 70 + "╗")
    for line in daily_path.read_text().splitlines():
        print(f"  ║ {line:<69s}║")
    print("  ╚" + "═" * 70 + "╝")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 7 · OUTPUT · promote 按置信度分流到 USER.md / candidates")
    # ──────────────────────────────────────────────────────────────
    print("  逻辑: promote_claims() 按 confidence 分桶:")
    print("    conf ≥ 0.85           → 备份 USER.md + 追加")
    print("    0.7 ≤ conf < 0.85     → 写 candidates/<id>.pending.json")
    print("    conf < 0.7            → 仅留日报, 不进 USER.md")
    print("    classification=habit  → 额外写 candidates/<name>.candidate")
    print()
    for c in claims:
        decision = "🟢 进 USER.md (auto)" if c.confidence >= 0.85 \
            else "🟡 进 candidates (待审)" if c.confidence >= 0.70 \
            else "⚪ drop"
        skill_mark = " + 🎯 写 skill candidate" if c.classification == "habit" else ""
        print(f"    Claim {c.id[:8]} (conf {c.confidence:.2f}, {c.classification})  →  {decision}{skill_mark}")

    summary = promote_claims(
        claims,
        user_md_path=work_dir / "memories" / "USER.md",
        candidates_dir=work_dir / "habit_memory" / "candidates",
        backups_dir=work_dir / "habit_memory" / "backups",
    )

    print()
    print(f"  → Promotion summary: {summary}")

    section("写到磁盘的所有文件")
    for p in sorted(work_dir.rglob("*")):
        if p.is_file():
            size = p.stat().st_size
            print(f"    {size:>6d} bytes  {p.relative_to(work_dir)}")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 8 · 最终产物 · USER.md 完整内容")
    # ──────────────────────────────────────────────────────────────
    user_md_path = work_dir / "memories" / "USER.md"
    print(f"  路径: {user_md_path}")
    print(f"  大小: {user_md_path.stat().st_size} 字节 (上限 1375)")
    print()
    print("  ╔" + "═" * 70 + "╗")
    for line in user_md_path.read_text().splitlines():
        print(f"  ║ {line:<69s}║")
    print("  ╚" + "═" * 70 + "╝")
    print()
    print("  ➜ 这就是 Hermes agent 下次启动时, 自动看到的 USER.md 全内容.")

    # ──────────────────────────────────────────────────────────────
    banner("STAGE 9 · 最终产物 · skill candidate (给 Curator 看的)")
    # ──────────────────────────────────────────────────────────────
    candidates = list((work_dir / "habit_memory" / "candidates").glob("*.candidate"))
    for cf in candidates:
        print(f"  路径: {cf}")
        print()
        for line in cf.read_text().splitlines():
            print(f"    {line}")

    print()
    banner("✅ Pipeline 完整跑完 · 每个阶段的 input/output 你都看到了")
    print()


if __name__ == "__main__":
    main()

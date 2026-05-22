# Hermes Habit Reflector · 设计 Spec

> 给 Hermes Agent 增加的第 6 层自学习模块。零侵入加载，<b>专门填补"USER.md/MEMORY.md 没有 retrospective 通道"这一空白</b>。
>
> 撰写：2026-05-23 · 与用户对齐后定稿

---

## 1. 问题陈述

Hermes 现有 5 层自学习全部是 **prospective** 的——agent 在当下事件（nudge / flush / 工具调用完 / 对话压缩 / Curator 7 天）触发时凭感觉决定记什么。

具体后果：

1. **稳定偏好被重复纠正**：用户 14 次说"用表格"，agent 没记进 USER.md（nudge 错过、或 agent 写了别的）
2. **高频短任务沉淀不下来**：4-5 turn 完成的任务卡在 ≥5 tool_call + 任务成功的 skill 创建门槛上
3. **USER 本被临时任务占满**：500 字小本子被 "用户在做笔试题" 这种 task state 占走，挤掉了 stable preference

**根因**：5 层里没有任何一层负责"回头看过去 N 天的实际对话历史，找反复出现的稳定模式"。

---

## 2. 设计目标

| # | 目标 | 约束 |
|---|---|---|
| 1 | **零侵入** | L1-L5 一行不改。通过 cron + 现有 `memory_tool.add()` 接口接入 |
| 2 | **可审计** | 每条 claim 必须带 evidence（session/turn 引用），用户能 dispute |
| 3 | **自动 decay** | 每条带 `decay_at` 字段。preference 90 天 / habit 30 天 / task 7 天 |
| 4 | **便宜** | 用 Haiku 4.5 跑 distill，预算 ≤$1/天 · ≤$30/月 |
| 5 | **跟 Curator 解耦** | 两个独立 cron。Reflector 写 candidate skill 标记；Curator 决定建不建 |
| 6 | **冷启动安全** | 装好后第 1 周不跑；第一份输出强制人审；2-3 次后才解锁自动 promote |

---

## 3. 反目标（明确不做）

- ❌ 不接 Screenpipe / AirJelly（虽是灵感来源，但 Reflector 必须能<b>独立运行</b>）
- ❌ 不替换现有的 nudge / flush 通道
- ❌ 不发明新协议
- ❌ 不自动改 MEMORY.md（task 类的还是 agent 当场写；Reflector 只写 USER.md）
- ❌ 不自动创建 skill（只标 candidate，由 Curator 决定）

---

## 4. 架构

### 4.1 文件位置

```
~/.hermes/
├── memories/
│   ├── MEMORY.md             # Hermes 原生 · agent 当下写 · 不动
│   ├── USER.md               # Hermes 原生 · Reflector 会写入 ≥0.85 conf 条目
│   └── ...
├── habit_memory/             # ★ 新增 · Reflector 输出目录
│   ├── 2026-05-23.md         # 每天一份蒸馏笔记
│   ├── 2026-05-24.md
│   ├── candidates/           # 待 Curator 评估的 skill 候选
│   │   └── paper-summary-table.candidate
│   ├── rejected/             # 用户拒绝的 claim 黑名单
│   │   └── _blacklist.json
│   └── backups/              # 写入 USER.md 前的备份
│       └── 2026-05-23-USER.md.bak
└── hooks/
    └── on_cron.py            # ★ 新增 · 每天 4am 触发
```

### 4.2 模块组成

| 文件 | 职责 | LoC 估 |
|---|---|---|
| `src/distiller.py` | 读 messages 表 → 调 Haiku → 解析 claims | ~80 |
| `src/promoter.py` | 高 conf claim 写入 USER.md · 中 conf 入待审 queue | ~60 |
| `src/blacklist.py` | 加载/写黑名单（用户 reject 过的 claim 类型） | ~30 |
| `src/schema.py` | Claim dataclass + 序列化 | ~40 |
| `src/render.py` | 渲染 habit_memory/&lt;date&gt;.md | ~40 |
| `hooks/on_cron.py` | cron 入口，dispatcher | ~20 |
| `examples/` | 一份 demo 输入 + 期望输出 | — |
| `tests/` | pytest unit tests | ~100 |

总计 ~370 行 Python。

### 4.3 数据流

```
[每天 04:00 cron]
        │
        ▼
on_cron.py
        │
        ├── 检查 idle ≥1h ? 否 → 跳过
        ├── 检查 距上次 ≥20h ? 否 → 跳过
        ├── 检查 cold start week 1 ? 是 → 跳过
        │
        ▼
distiller.py
        │
        ├── 读 ~/.hermes/state.db (messages 表，过去 30 天)
        ├── 过滤 ≥3 session 才跑 (cold start guard)
        ├── 应用 blacklist 过滤
        ├── 渲染 distill prompt
        ├── 调 Haiku 4.5
        ├── 解析输出 → List[Claim]
        │
        ▼
render.py → 写 habit_memory/2026-05-23.md
        │
        ▼
promoter.py
        │
        ├── conf ≥0.85 → memory_tool.add("user", entry) · 备份 USER.md
        ├── 0.7 ≤ conf < 0.85 → 写 candidates/<id>.pending
        ├── conf < 0.7 → 仅留 habit_memory/<date>.md
        │
        ▼
完成 · log to ~/.hermes/logs/reflector.log
```

---

## 5. Claim Schema

```python
@dataclass
class Claim:
    id: str                           # uuid
    claim: str                        # 一句话结论
    classification: str               # "preference" | "habit" | "task" | "constraint"
    evidence: list[EvidenceRef]       # 至少 3 个 session/turn 引用
    confidence: float                 # 0.0 - 1.0
    decay_at: str                     # ISO date
    intervention: str | None          # 给 agent 的指令（可选）
    source: str = "reflector"         # "reflector" | "agent" | "user"
    created_at: str                   # ISO date
    last_reinforced: str              # ISO date

@dataclass
class EvidenceRef:
    session_id: str
    turn_n: int
    excerpt: str                      # ≤80 char 摘录
```

### 5.1 Confidence 怎么算

3 个信号每个 +0.25 + 起步 0.1 = 最高 0.85；满足 4 个信号（多一个 explicit user 确认）可达 1.0：

| 信号 | 给分 |
|---|---|
| 出现 ≥5 次 | +0.25 |
| 跨 ≥3 个不同 session | +0.25 |
| 最近 7 天内还在出现 | +0.25 |
| 用户曾 explicit 确认（"是的我喜欢 X"）| +0.25 |
| **起步** | +0.10 |

### 5.2 Decay 默认

| classification | 默认 decay_at |
|---|---|
| `preference` | now + 90 days |
| `habit` | now + 30 days |
| `task` | now + 7 days |
| `constraint` | now + 180 days |

每次 reinforce（新 session 又出现）自动 reset decay。

---

## 6. Distill Prompt（设计冻结）

```
SYSTEM:
You are a behavioral analyst examining a user's actual conversation
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
- evidence: 3+ {session_id, turn_n, excerpt}
- confidence (0.0-1.0)
- decay_at (date)
- intervention (concrete instruction for agent; optional)

DO NOT output current task state.
DO NOT output anything user explicitly told agent to forget.
DO NOT generate claims with < 3 evidence items.

Output strict JSON matching schema.json.

USER:
<session data window 30 days>
```

---

## 7. 触发逻辑

### 7.1 Cron 条件（全满足才跑）

```python
def should_run() -> bool:
    if is_cold_start_week_1(): return False
    if not user_idle_at_least_hours(1): return False
    if hours_since_last_run() < 20: return False
    if message_count_last_30d() < 50: return False  # 数据太少
    return True
```

### 7.2 Cold Start 三阶段

| 阶段 | 行为 |
|---|---|
| Week 1 (装上后 7 天) | 完全不跑，攒数据 |
| Week 2 第 1 次 | 跑，但所有 conf 上限封顶 0.84（强制 ≥0.85 自动写入失效）→ 全部入 pending queue 让用户审 |
| Week 3+ | 正常运行，conf ≥0.85 自动写入 USER.md |

---

## 8. 错了怎么撤

```python
# 用户 reject 一条 claim
reflector reject <claim_id>
# 效果：
# 1. 从 USER.md 删
# 2. 把 claim 的 classification + 主关键词 加入 blacklist
# 3. 下次 distiller 跑时这类 claim 不再生成

# 用户 edit 一条 claim
reflector edit <claim_id> --new "..."
# 效果：confidence 重置 1.0，source 改成 "user"

# 全量回滚到昨天
reflector rollback 2026-05-22
# 从 backups/2026-05-22-USER.md.bak 恢复
```

---

## 9. 跟 Curator 的协调

两个独立 cron，不阻塞：

| | Reflector | Curator |
|---|---|---|
| 频率 | 每天 4am | 每 7 天 |
| 对象 | USER.md / MEMORY.md | ~/.hermes/skills/ |
| 输出 | claims + candidate skill 标记 | keep/patch/archive 决策 |
| 关联 | <b>Reflector 标 candidate, Curator 决建</b> | 同左 |

具体：当 Reflector 发现某个高频 task pattern（≥5 session、≥5 turn 同模式），写一份 <code>~/.hermes/habit_memory/candidates/&lt;name&gt;.candidate</code>。Curator 下次跑时读这个 dir，<b>独立判断</b>是否要建成 skill。

---

## 10. 评估假说

笔试可以用这 3 条做 demo：

| 假说 | 怎么验证 |
|---|---|
| H1: 装上 Reflector 后，重复纠正频率下降 ≥50% | session N 之后"用表格"被纠正次数下降 |
| H2: 高频短任务被识别为 candidate skill 的时间从"永不"降到"5-10 个 session" | 跟踪 candidates/ 目录的产出速度 |
| H3: USER.md 中 preference 类条目占比从 &lt;30% 升到 ≥80% | 比对装前装后 USER.md 内容分类 |

---

## 11. 成本

| | 频率 | 单次成本 | 月成本 |
|---|---|---|---|
| Distiller | 每天 1 次 | $0.40 (Haiku 4.5) | ~$12 |
| Promoter | 每天 1 次 | $0 (纯文件 IO) | $0 |
| Cold start backup | 装上一次 | $0 | $0 |
| **总计** | | | **~$12/月** |

---

## 12. 接 Hermes 的 hook（无侵入）

只在 `~/.hermes/config.yaml` 加一节：

```yaml
habit_reflector:
  enabled: true
  cron_hour: 4              # 凌晨 4 点
  window_days: 30
  min_idle_hours: 1
  min_messages_in_window: 50
  cold_start_weeks: 1

  distiller:
    model: "claude-haiku-4-5"
    max_input_tokens: 400000
    max_cost_per_run_usd: 1.0
    prompt_path: "src/distill_prompt.txt"

  promotion:
    auto_promote_threshold: 0.85
    queue_for_review_threshold: 0.7
    require_user_review_first_n_runs: 2

  safety:
    backup_usermd_before_promote: true
    keep_backups: 14
```

Hermes 现有的 hook 系统会读 `~/.hermes/hooks/on_cron.py`，每天 cron 时调用。

---

## 13. 不在 v1 做（写进 roadmap）

- ❌ Cross-user habit aggregation（隐私 + scope）
- ❌ Embedding-based retrieval（YAGNI，BM25 over markdown 已够）
- ❌ Real-time（vs daily batch）reflector
- ❌ Reflector 自主创建 skill（仍由 Curator 决建）
- ❌ Honcho 集成（独立运行优先）

---

## 14. 出口标准（认为 demo 跑通）

1. 跑 `python -m habit_reflector dry-run --fixture examples/14-session-fixture/`
2. 应输出一份 `habit_memory/2026-05-23.md` 含 ≥3 条 claim
3. 至少 1 条 conf ≥0.85（应进 USER.md backup）
4. 至少 1 条 0.7-0.85（应入 candidates/）
5. 至少 1 条标 candidate skill
6. 没有 crash，全程 log 清晰


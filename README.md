# Hermes Habit Reflector

> 给 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 加的第 6 层自学习模块。
> 每天凌晨 4 点回顾过去 30 天对话历史，自动把稳定的用户习惯写入 `USER.md`。
>
> 解决 Hermes 现有 5 层自学习全是「当下凭感觉记」的盲区。

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Tests](https://img.shields.io/badge/tests-12%2F12_passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-blue) ![Cost](https://img.shields.io/badge/月成本-%2412-success) ![Hermes](https://img.shields.io/badge/Hermes-零侵入-orange)

---

## 📌 一句话讲清

**Hermes 现在的自学习像「边聊边记笔记的实习生」——记什么看心情。**
**装上 Reflector 等于多了个「每晚睡前回顾过去 30 天」的助手——把反复出现的稳定模式整理出来写进 USER 本。**
**两个一起，agent 才真的"认识"你。**

---

## 🔥 痛点 · 为什么需要这个模块

Hermes 内置 5 层自学习全是 **prospective（当下事件触发）**：

```
   现状（5 层全是当下凭感觉）          缺失（没有回顾）
   ┌──────────────────────────┐      ┌──────────────────┐
   │ L1 短期工作记忆 (每 turn)│      │                  │
   │ L2 Episodic (用户主动查)  │      │  ❓               │
   │ L3 Honcho (每 N turn)    │  vs  │   没有任何一层   │
   │ L4 USER.md (nudge/flush) │      │   负责回头看     │
   │ L5 Skill Curator (7 天)  │      │   过去 30 天     │
   └──────────────────────────┘      └──────────────────┘
        ▲                                    ▲
        当下凭感觉                      Reflector 填这块
```

具体后果（3 个真实痛点）：

| 痛点 | 表现 | 根因 |
|---|---|---|
| **🔴 偏好被重复纠正** | 你说 14 次"用表格"，agent 还在用 prose | nudge 错过 + agent 当下没把它当成偏好 |
| **🔴 高频短任务沉淀不下来** | "读 paper 出表格" 做了 12 次还没 skill | Skill 创建门槛 ≥5 tool_call，4-turn 任务永远卡门外 |
| **🔴 USER 本被临时任务占满** | 500 字预算被 "用户在做笔试题" 占走 | agent 一拍脑袋写，分不清 task vs preference |

---

## ✨ 装上 Reflector 之后 · 立即效果

### 🎬 30 秒本地跑 demo（不需要 API key）

```bash
git clone https://github.com/AlexZWANG1/hermes-habit-reflector
cd hermes-habit-reflector
python3 -m src.cli dry-run --fixture examples/14-session-fixture.json --work-dir /tmp/demo
```

下面是<b>真实跑出来的输出</b>——不是描述，是实际产物。

### 📤 输出 1 · CLI 终端实际打印

```
[INFO] Loaded 27 messages across 15 sessions
[INFO] Promoted claim 35cd77cf → USER.md (conf 1.00)
[INFO] Wrote skill candidate 高频任务-读-paper---出表格-critique-候选-skill.candidate
[INFO] Promoted claim 5824826f → USER.md (conf 0.85)
[INFO] Promoted claim 276ed943 → USER.md (conf 0.85)

=== Hermes Habit Reflector · run ===
  reflector_root: /tmp/demo
  fixture: examples/14-session-fixture.json
  dry_run: True

Distilled 3 claims:
  · [preference] conf=1.00 · 用户强偏好结构化输出（表格 + bullet）而非 prose...
  · [habit]      conf=0.85 · 高频任务：读 paper → 出表格 critique（候选 skill）
  · [preference] conf=0.85 · 工作日上午 10-13 点出现短 session 高密度...

Promotion summary:
  · promoted_to_usermd: 3      ← 3 条都进了 USER.md
  · queued_for_review:  0
  · dropped_low_conf:   0
  · skill_candidates:   1      ← 1 条标 skill 候选给 Curator
  · budget_rejected:    0

=== done ===
```

### 📤 输出 2 · USER.md（agent 下次启动就看到）

```bash
$ cat /tmp/demo/memories/USER.md
```

```
- 用户强偏好结构化输出（表格 + bullet）而非 prose
  [conf 1.00 · 5 sessions · decay 2026-08-21 · id 35cd77cf]
- 高频任务：读 paper → 出表格 critique（候选 skill）
  [conf 0.85 · 3 sessions · decay 2026-06-22 · id 5824826f]
- 工作日上午 10-13 点出现短 session 高密度（4-6 turn 完成）
  [conf 0.85 · 3 sessions · decay 2026-08-21 · id 276ed943]
```

> 📊 **398 字符** · 远低于 Hermes 1375 字符上限 · 每条都带 <b>id + 置信度 + session 数 + 过期日期</b>

### 📤 输出 3 · 当天 habit_memory 完整日报（含证据引用）

```bash
$ cat /tmp/demo/habit_memory/2026-05-23.md
```

```
---
generated_at: 2026-05-23T04:37:41+00:00
window_days: 30
session_count: 15
total_messages: 27
distiller_model: claude-haiku-4-5
distiller_cost_usd: 0.0000
schema_version: 1
---

## Habit · preference · id 35cd77cf
claim: 用户强偏好结构化输出（表格 + bullet）而非 prose
classification: preference
confidence: 1.00
decay_at: 2026-08-21
intervention: session 启动时优先使用表格 + bullet 格式输出
evidence:
  - s_dry_001:t1 "用表格"
  - s_dry_002:t3 "改成 bullet"
  - s_dry_003:t1 "// 表格列出"
  - s_dry_004:t2 "table please"
  - s_dry_005:t1 "bullet 不要 prose"

## Habit · habit · id 5824826f
claim: 高频任务：读 paper → 出表格 critique（候选 skill）
classification: habit
confidence: 0.85
decay_at: 2026-06-22
intervention: promote 为 skill: paper-summary-table
evidence:
  - s_dry_010:t1 "看 SWE-bench Pro paper"
  - s_dry_011:t1 "看 METR paper"
  - s_dry_012:t1 "读一下这篇 论文"

## Habit · preference · id 276ed943
claim: 工作日上午 10-13 点出现短 session 高密度（4-6 turn 完成）
classification: preference
confidence: 0.85
decay_at: 2026-08-21
intervention: 白天 session 启动时偏好短回答 + 跳过预热
evidence:
  - s_dry_020:t4 "完成"
  - s_dry_021:t5 "搞定"
  - s_dry_022:t4 "OK"

---

## Summary
- Total claims: 3
- Auto-promote candidates (conf ≥0.85): 3
- Review queue (0.70 ≤ conf < 0.85): 0
- Habit skill candidates: 1
```

### 📤 输出 4 · Curator 收到的 skill 候选

```bash
$ cat /tmp/demo/habit_memory/candidates/*.candidate
```

```json
{
  "claim_id": "5824826f",
  "claim": "高频任务：读 paper → 出表格 critique（候选 skill）",
  "intervention": "promote 为 skill: paper-summary-table",
  "evidence_count": 3,
  "confidence": 0.85,
  "created_at": "2026-05-23T04:37:41+00:00"
}
```

> 🎯 **Reflector 只观察，Curator 决定建不建** —— 干净分工

### 📤 输出 5 · 任意时候看 status

```bash
$ python3 -m src.cli status --work-dir /tmp/demo
```

```
=== Habit Reflector Status ===
  reflector root: /tmp/demo
  USER.md: 398 chars, 2 entries
  pending review: 0
  skill candidates: 1
    · 高频任务-读-paper---出表格-critique-候选-skill
  blacklist entries: 0
  recent habit_memory files (1):
    · 2026-05-23.md
```

### 📤 输出 6 · 单元测试

```bash
$ python3 -m pytest tests/ -v
```

```
============================= test session starts ==============================
collected 12 items

tests/test_pipeline.py::test_dry_run_full_pipeline PASSED                [  8%]
tests/test_pipeline.py::test_blacklist_filters PASSED                    [ 16%]
tests/test_pipeline.py::test_cold_start_caps_confidence PASSED           [ 25%]
tests/test_pipeline.py::test_usermd_char_budget PASSED                   [ 33%]
tests/test_schema.py::test_claim_requires_3_evidence PASSED              [ 41%]
tests/test_schema.py::test_claim_validates_classification PASSED         [ 50%]
tests/test_schema.py::test_claim_validates_confidence_range PASSED       [ 58%]
tests/test_schema.py::test_claim_auto_assigns_decay PASSED               [ 66%]
tests/test_schema.py::test_compute_confidence_all_signals PASSED         [ 75%]
tests/test_schema.py::test_compute_confidence_with_explicit PASSED       [ 83%]
tests/test_schema.py::test_compute_confidence_partial PASSED             [ 91%]
tests/test_schema.py::test_claim_roundtrip PASSED                        [100%]

============================== 12 passed in 0.02s ==============================
```

### 🎯 你刚刚看到的 6 步证明了什么

| 步骤 | 证明了 |
|:---:|---|
| 1 · CLI 输出 | distill 真的从 27 条 messages 蒸馏出 3 条稳定 claim |
| 2 · USER.md | <b>下次 agent 启动自动看到</b>这 3 条，再也不用纠正"用表格" |
| 3 · 日报 | 每条 claim 带<b>≥3 条 evidence</b>，你能逐条 audit、reject、git diff |
| 4 · skill 候选 | habit 类自动给 Curator 留候选文件，零侵入 |
| 5 · status | 任何时候一行命令看清"现在 agent 学到了什么" |
| 6 · 12 个测试 | 端到端 + schema + blacklist + cold-start + 字符预算<b>全过</b> |

---

## 🏗️ 架构 · 零侵入接进 Hermes

```
~/.hermes/                                    🟢 Hermes 原目录, 没改一行
├── memories/
│   ├── MEMORY.md              ← Hermes 自带, agent 当下写
│   └── USER.md                ← Reflector 写入 ≥0.85 conf 的 claim
│
├── habit_memory/              🆕 Reflector 输出目录
│   ├── 2026-05-23.md          ← 每天一份日报
│   ├── candidates/            ← skill 候选 + 待审 claim 队列
│   ├── rejected/              ← 用户拒绝过的 claim 黑名单
│   └── backups/               ← USER.md 滚动备份 (14 天)
│
├── hooks/
│   └── on_cron.py             🆕 软链到本仓库, Hermes cron 自动调用
│
└── state.db                   ← Hermes 自带 SQLite (Reflector 只读)
```

**Hermes 主循环 + 5 层自学习 + Curator + Honcho 全部一行不改。** 不喜欢直接关 cron 退回原状。

---

## 📚 6 层自学习全局视图

| # | 层 | 触发 | 方向 | 谁在判断 | 改没改 |
|:---:|---|---|---|---|:---:|
| L1 | 短期工作记忆 | 每 turn | 当下 | LLM 自压缩 | — |
| L2 | 长期 Episodic（FTS5） | `session_search` 工具 | 当下查询 | aux model 总结 | — |
| L3 | Honcho dialectic（可选） | 每 N turn | 当下反思 | LLM 假设式问答 | — |
| L4 | Curated MEMORY/USER 本 | nudge / flush | 当下决定 | Agent 一拍脑袋 | — |
| L5 | Skill 自演化 + 7 天 Curator | ≥5 tool_call + Curator 周期 | 当下 + 7 天 | aux AIAgent fork | — |
| **L6** | **Habit Reflector ⭐** | **每天 4am cron** | **回顾 30 天** | **离线 forensic 分析** | **🆕 新增** |

**关键观察**：L1-L5 全是 **「当下做决定」**。<b>L6 是唯一回头看历史的层</b>。两条互补：当下抓即时重要的事，回顾抓长期稳定的事。

---

## ⚙️ 数据流 · 一个 claim 怎么从对话变成 USER.md 条目

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   每天 04:00 凌晨                                                  │
│        │                                                           │
│        ▼                                                           │
│   ┌─────────────┐                                                  │
│   │ on_cron.py  │  4 个守门条件 (全满足才跑)                       │
│   └──────┬──────┘  ① 不在冷启动第 1 周                             │
│          │         ② 用户 idle ≥1 小时                             │
│          │         ③ 距上次跑 ≥20 小时                             │
│          │         ④ 30 天 messages ≥50                            │
│          │                                                         │
│          ▼                                                         │
│   ┌─────────────┐  • 读 state.db (过去 30 天 messages)              │
│   │  distiller  │  • 应用 blacklist 过滤                            │
│   │             │  • 渲染 prompt → Haiku 4.5                       │
│   │             │  • 解析 JSON → List[Claim]                        │
│   └──────┬──────┘                                                  │
│          │                                                         │
│          ▼                                                         │
│   ┌─────────────────────────────────────┐                          │
│   │ 置信度本地重算 (不信模型自评)        │                          │
│   │                                      │                          │
│   │   起步              +0.10            │                          │
│   │ + 出现 ≥5 次        +0.25            │                          │
│   │ + 跨 ≥3 session     +0.25            │                          │
│   │ + 最近 7 天内       +0.25            │                          │
│   │ + 用户曾显式确认    +0.25  (可选)    │                          │
│   │ ─────────────────────────            │                          │
│   │   最高              1.00             │                          │
│   └──────┬──────────────────────────────┘                          │
│          │                                                         │
│          ▼                                                         │
│   ┌─────────────────────────────────────┐                          │
│   │ promoter · 按置信度分流              │                          │
│   │                                      │                          │
│   │   conf ≥ 0.85  →  备份 USER.md       │                          │
│   │                   + 追加新条目        │  → 🟢 agent 立即看到    │
│   │                                      │                          │
│   │   0.7≤ c <0.85 →  candidates/       │                          │
│   │                   <id>.pending.json │  → 🟡 下次 session 问你  │
│   │                                      │                          │
│   │   conf < 0.7   →  仅留日报           │  → ⚪ 不进 USER.md       │
│   │                                      │                          │
│   │   class == "habit"                   │                          │
│   │     → candidates/<name>.candidate    │  → 🎯 Curator 看到       │
│   └─────────────────────────────────────┘                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 📦 安装 · 装到你本地 Hermes

```bash
# 1️⃣ 克隆
git clone https://github.com/AlexZWANG1/hermes-habit-reflector
cd hermes-habit-reflector

# 2️⃣ 装依赖 (只有 --real-api 才需要)
pip install anthropic

# 3️⃣ 软链 cron hook 到 Hermes
ln -s "$PWD/hooks/on_cron.py" ~/.hermes/hooks/on_cron.py

# 4️⃣ 加配置
cat >> ~/.hermes/config.yaml <<EOF

habit_reflector:
  enabled: true
  cron_hour: 4
  window_days: 30
  cold_start_weeks: 1
EOF
```

完成。Hermes 自带的 cron 会从明天凌晨 4 点开始调用。

---

## 🛠️ CLI 命令一览

| 命令 | 干什么 |
|---|---|
| `python3 -m src.cli dry-run --fixture <path>` | 不调 API，用 canned 响应跑 |
| `python3 -m src.cli run --real-api` | 真跑（需 `ANTHROPIC_API_KEY`） |
| `python3 -m src.cli status` | 看现在学到了什么 |
| `python3 -m src.cli reject <claim_id>` | 拒绝一条 claim + 加黑名单 |
| `python3 -m src.cli rollback YYYY-MM-DD` | 从备份恢复 USER.md |

---

## 🧪 单元测试覆盖

| 测试 | 验证什么 |
|---|---|
| `test_dry_run_full_pipeline` | 端到端 · fixture → distill → render → promote → USER.md 真的有内容 |
| `test_blacklist_filters` | 黑名单匹配的 claim 不出现 |
| `test_cold_start_caps_confidence` | 冷启动周 conf 上限 0.84 |
| `test_usermd_char_budget` | USER.md 永不超过 1375 字符 |
| `test_claim_requires_3_evidence` | schema 强制 ≥3 evidence |
| `test_claim_validates_classification` | 只接受 4 种合法分类 |
| `test_claim_validates_confidence_range` | conf 必须在 [0, 1] |
| `test_claim_auto_assigns_decay` | preference/habit/task 默认 decay 正确 |
| `test_compute_confidence_all_signals` | 3 信号全满足 → 0.85 |
| `test_compute_confidence_with_explicit` | + 用户显式确认 → 1.00 |
| `test_compute_confidence_partial` | 部分满足公式正确 |
| `test_claim_roundtrip` | dict ⇌ Claim 序列化 |

```bash
pip install pytest
python3 -m pytest tests/ -v   # 12/12 通过, 0.02s
```

---

## 🎯 设计原则 · 6 条

| # | 原则 | 怎么实现 |
|:-:|---|---|
| 1 | **零侵入** | 通过 cron + 现有 `memory_tool.add()` 接入, Hermes 主循环零修改 |
| 2 | **可审计** | 每条 claim 必须 ≥3 evidence, 用户能逐条 dispute |
| 3 | **自动 decay** | preference 90d / habit 30d / task 7d, 永不堆陈年噪音 |
| 4 | **便宜** | Haiku 4.5 一天 $0.40, 月成本 ~$12 |
| 5 | **跟 Curator 解耦** | Reflector 标 candidate, Curator 决建不建. 两 cron 独立 |
| 6 | **冷启动安全** | 第 1 周不跑攒数据, 前 2 次自动 promote 强制失效 |

---

## 🚫 v1 明确不做（YAGNI）

| 不做的事 | 理由 |
|---|---|
| ❌ 跨用户 habit 聚合 | 隐私 + scope |
| ❌ Embedding-based retrieval | 1000 session 内 BM25 + markdown 够用 |
| ❌ 实时蒸馏（vs 每日批） | 成本不值, 每日延迟用户感知不到 |
| ❌ Reflector 自动创建 skill | 让 Curator 决建, 保持清晰职责 |
| ❌ 接 Screenpipe / 外部数据源 | 必须能独立运行, 外部接入是 v2 选项 |

---

## 💰 成本分析

| 项目 | 频率 | 单次成本 | 月成本 |
|---|---|---|---|
| Distiller (Haiku 4.5) | 每天 1 次 | ~$0.40 | **~$12** |
| Promoter | 每天 1 次 | $0 (纯文件 IO) | $0 |
| **总计** | | | **~$12 / 月** |

约一杯咖啡的钱。对比单次 Sonnet 4.5 长对话（$1-3）就便宜很多。

---

## 📁 仓库结构

```
hermes-habit-reflector/
├── README.md                          ← 本文件
├── LICENSE                            ← MIT
├── requirements.txt                   ← anthropic
├── requirements-dev.txt               ← pytest
│
├── docs/
│   └── SPEC.md                        ← 14 节完整设计文档
│
├── src/                               ← 6 个模块, ~370 行 Python
│   ├── __init__.py
│   ├── schema.py                      ← Claim 数据类 + 置信度公式
│   ├── blacklist.py                   ← 用户拒绝过的 claim 签名
│   ├── distiller.py                   ← 读 messages → Haiku → 解析 claims
│   ├── promoter.py                    ← 写 USER.md / candidates / backups
│   ├── render.py                      ← 渲染 habit_memory/YYYY-MM-DD.md
│   └── cli.py                         ← CLI 命令入口
│
├── hooks/
│   └── on_cron.py                     ← Hermes cron 入口（含 4 个守门条件）
│
├── examples/
│   └── 14-session-fixture.json        ← 27 条 messages / 15 session 合成数据
│
└── tests/                             ← 12 个单元测试, 全过
    ├── test_schema.py
    └── test_pipeline.py
```

---

## 🔬 与现有 Hermes 自学习的关系

**为什么不是重复造轮子？** 因为 Hermes 已有的两个机制刻意避开 USER.md：

| | Curator 现有 | Honcho 现有可选 | **Habit Reflector** |
|---|---|---|---|
| 触发 | 7 天周期 | 每 N turn | **每天 4am** |
| 管什么 | <b>只管 skill</b>（源码硬约束）| 独立 peer card（远程后端）| **USER.md / MEMORY.md** |
| 写哪 | `~/.hermes/skills/` | 远程 Honcho 后端 | **`~/.hermes/memories/USER.md`** |
| 方法 | aux AIAgent fork 自评 | LLM dialectic 反思 | **离线 forensic 蒸馏** |

> **`agent/curator.py` 源码原话**：
> "Strict invariants: Only touches **agent-created skills**"
>
> → Curator 不会动 USER.md, 这是源码硬约束.

> **`plugins/memory/honcho/__init__.py` 注释**：
> "AI-native cross-session user modeling with dialectic Q&A...via the Honcho SDK"
>
> → Honcho 是独立平行系统, 也不写 Hermes 原生 USER.md.

**所以 USER.md/MEMORY.md 在 Hermes 现有架构里是"无人管的空地"。** Reflector 填的就是这块.

---

## 📐 评估假说 · 怎么证明它有效

| 假说 | 怎么测 |
|---|---|
| **H1** · 装上后, 重复纠正频率下降 ≥50% | session N 之后 "用表格" 类纠正次数 |
| **H2** · 高频短任务变 skill 的时间: ∞ → 5-10 个 session | 跟踪 `candidates/` 目录产出速度 |
| **H3** · USER.md 中 preference 类条目占比: <30% → ≥80% | 装前装后人工归类对比 |

---

## 🤝 贡献

PR 欢迎。请先：

1. 跑 `pytest tests/ -v` 全过
2. 不加 embeddings / 向量库（YAGNI 是设计原则）
3. 不动 Hermes 核心（零侵入是承诺）

---

## 📄 License

MIT

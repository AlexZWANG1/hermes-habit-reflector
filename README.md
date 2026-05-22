# Hermes Habit Reflector

> Hermes Agent 的第 6 层自学习模块。每天凌晨 4 点 retrospective 蒸馏过去 30 天对话历史，
> 抽取稳定 user habit，自动写入 USER.md 或队列等用户审。
>
> **零侵入**：通过 cron + 现有 `memory_tool.add()` 接口接入，Hermes 主循环、5 层自学习一行不改。

---

## 这是什么

Hermes 现有自学习全部是 **prospective**——agent 当下凭感觉决定记什么。这导致：

- 用户 14 次说"用表格"，agent 没记进 USER.md
- 4 turn 完成的高频任务，触发不了 ≥5 tool_call 的 skill 创建门槛
- USER.md 500 字被"用户在做笔试题"这种 task state 占满

Reflector 加上 **retrospective** 通道：

| | 现有 Hermes | + Habit Reflector |
|---|---|---|
| 触发方式 | 当下事件（nudge / flush / 工具结束）| **每天凌晨 4 点** |
| 数据来源 | 当前 session 对话 | **过去 30 天完整对话历史** |
| 判断者 | Agent 当下感觉 | **离线小模型 forensic 分析** |
| 写入对象 | MEMORY.md（agent 写）| **USER.md（≥0.85 conf 自动 promote）+ skill candidates** |

---

## 安装

```bash
git clone https://github.com/zane/hermes-habit-reflector
cd hermes-habit-reflector
pip install anthropic              # for real-api mode
pip install pytest                 # for tests

# 软链 cron hook 进 Hermes
ln -s "$PWD/hooks/on_cron.py" ~/.hermes/hooks/on_cron.py
```

把以下加进 `~/.hermes/config.yaml`：

```yaml
habit_reflector:
  enabled: true
  cron_hour: 4
  window_days: 30
  cold_start_weeks: 1
```

---

## 用法

### Dry-run（推荐先跑这个）

不调真 API，用 canned 响应 + fixture：

```bash
python -m src.cli dry-run --fixture examples/14-session-fixture.json --work-dir /tmp/reflector-test
```

预期输出：
- 3 条 claims
- 1 条 conf ≥0.85 自动写入 USER.md
- 1 条 0.7-0.85 进 candidates/ 待用户审
- 1 条 habit 分类，生成 skill candidate

### 真跑

```bash
export ANTHROPIC_API_KEY=...
python -m src.cli run --real-api
```

### 状态查看

```bash
python -m src.cli status
```

### 拒绝一条错的 claim

```bash
python -m src.cli reject <claim_id> --key-phrase "表格" --reason "我其实不是每次都要表格"
```

效果：从 USER.md 删除 + 把 "表格" 加进 blacklist，下次 distiller 不再生成类似 claim。

### 回滚 USER.md

```bash
python -m src.cli rollback 2026-05-22
```

---

## 架构

```
~/.hermes/                                    Hermes home
├── memories/
│   ├── MEMORY.md         ← 原生 · agent 当下写
│   └── USER.md           ← Reflector 写入 ≥0.85 conf 条目
├── habit_memory/         ← Reflector 输出目录
│   ├── 2026-05-23.md     ← 每天一份日报
│   ├── candidates/       ← skill 候选 + pending review 队列
│   ├── rejected/         ← blacklist
│   └── backups/          ← USER.md 写入前的 14 天滚动备份
├── hooks/
│   └── on_cron.py        ← cron 入口 (本仓库)
└── state.db              ← Hermes 原生 SQLite (Reflector 只读)
```

---

## 数据流

```
[每天 04:00 cron] → on_cron.py
    │
    ├── 检查 cold-start week 1? 是 → 跳过
    ├── 检查 idle ≥1h? 否 → 跳过
    ├── 检查 距上次 ≥20h? 否 → 跳过
    ├── 检查 30 天 messages ≥50? 否 → 跳过
    │
    ▼
distiller.distill()
    │
    ├── 读 ~/.hermes/state.db (messages 表)
    ├── 应用 blacklist 过滤
    ├── 渲染 distill prompt → 调 Haiku 4.5
    ├── 解析 JSON → list[Claim]
    │
    ▼
render.write_daily_memory()
    │
    └── 写 habit_memory/2026-05-23.md (含 evidence + confidence + decay)
    │
    ▼
promoter.promote_claims()
    │
    ├── conf ≥0.85 → backup USER.md + memory_tool.add()
    ├── 0.7 ≤ conf < 0.85 → 写 candidates/<id>.pending.json
    ├── conf < 0.7 → 仅留日报
    └── classification == "habit" → 写 candidates/<name>.candidate (给 Curator 看)
```

---

## 设计原则

1. **零侵入**：Hermes 主循环、5 层自学习一行不改
2. **可审计**：每条 claim 必须 ≥3 evidence，用户能 dispute
3. **自动 decay**：preference 90d / habit 30d / task 7d
4. **便宜**：Haiku 4.5 跑 distill，月成本 ~$12
5. **跟 Curator 解耦**：Reflector 标 candidate skill，Curator 决定建不建
6. **冷启动安全**：装上第 1 周不跑；前 2 次自动 promote 失效

---

## 跟现有 Hermes 自学习的关系

| 层 | 触发 | 对象 | Reflector 怎么 interact |
|---|---|---|---|
| L1 短期工作记忆 | 每 turn | messages | 不动 |
| L2 长期 Episodic | session_search | SQLite | **Reflector 读** |
| L3 Dialectic Honcho | 每 N turn | Honcho 后端 | 不动（独立运行）|
| L4 Curated MEMORY/USER | nudge/flush | USER.md / MEMORY.md | **Reflector 写 USER.md** |
| L5 Skill 自演化 | ≥5 tool_call + Curator | skills/ | **Reflector 写 candidates/ 标 → Curator 决建**|
| **L6 Habit Reflector (NEW)** | **每天 cron** | **habit_memory/** | — |

---

## 评估假说

| 假说 | 测量 |
|---|---|
| H1: 重复纠正频率下降 ≥50% | session N 之后 "用表格" 类纠正出现次数 |
| H2: 高频短任务变 skill 的时间 ∞ → 5-10 个 session | 跟踪 candidates/ 目录产出 |
| H3: USER.md 中 preference 类占比 <30% → ≥80% | 装前装后对比 |

---

## 跑单元测试

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## License

MIT

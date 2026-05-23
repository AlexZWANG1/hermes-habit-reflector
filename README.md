# Hermes Habit Reflector

> A 6th self-learning layer for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
> Distills 30 days of conversation history every night → auto-promotes stable user habits to `USER.md`.

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![tests](https://img.shields.io/badge/tests-12%2F12_passing-brightgreen) ![license](https://img.shields.io/badge/license-MIT-blue) ![cost](https://img.shields.io/badge/runtime_cost-%2412%2Fmonth-success)

---

## Why this exists

Hermes' existing 5 self-learning layers are all **prospective** — the agent decides what to remember *in the moment* (via `nudge` at turn 10, or `flush` at session end). This misses:

- **Stable preferences get forgotten.** You say "use a table" 14 times across 14 sessions; the agent re-discovers it from scratch each session because USER.md was empty or filled with stale task notes.
- **High-frequency short tasks never become skills.** Hermes' skill creation needs `≥5 tool_call + agent self-judges success`. A 4-turn "read paper, give me a table" task hits this gate exactly never.
- **USER.md (500 chars) fills with task state, not preferences.** "User is working on the SOTA harness exam" is noise. "User prefers structured output" is signal.

**The missing piece**: a **retrospective** layer that looks at the *actual conversation history*, not the agent's in-the-moment guess.

---

## What it does (30-second demo)

```bash
git clone https://github.com/zane/hermes-habit-reflector
cd hermes-habit-reflector
python3 -m src.cli dry-run --fixture examples/14-session-fixture.json --work-dir /tmp/demo
```

You'll see this:

```
Distilled 3 claims:
  · [preference] conf=1.00 · 用户强偏好结构化输出（表格 + bullet）...
  · [habit]      conf=0.85 · 高频任务：读 paper → 出表格 critique（候选 skill）
  · [preference] conf=0.85 · 工作日上午 10-13 点出现短 session 高密度...

Promotion summary:
  · promoted_to_usermd: 3
  · skill_candidates:   1
```

And `cat /tmp/demo/memories/USER.md`:

```
- 用户强偏好结构化输出（表格 + bullet）而非 prose
  [conf 1.00 · 5 sessions · decay 2026-08-21 · id 35cd77cf]
- 高频任务：读 paper → 出表格 critique（候选 skill）
  [conf 0.85 · 3 sessions · decay 2026-06-22 · id 5824826f]
- 工作日上午 10-13 点出现短 session 高密度（4-6 turn 完成）
  [conf 0.85 · 3 sessions · decay 2026-08-21 · id 276ed943]
```

Every entry carries **evidence** (which session/turn supports it), **confidence** (recomputed locally from signal counts, not trusted from the model), and **decay** (auto-expires preference at 90d / habit at 30d / task at 7d).

---

## Architecture · zero-touch into Hermes

```
~/.hermes/                                    Hermes home (unchanged)
├── memories/
│   ├── MEMORY.md              ← Hermes native, agent writes
│   └── USER.md                ← Reflector writes ≥0.85 conf claims
├── habit_memory/              ← NEW · Reflector output dir
│   ├── 2026-05-23.md          ← Daily distillation report
│   ├── candidates/            ← Skill candidates + pending review queue
│   ├── rejected/              ← User-rejected claim blacklist
│   └── backups/               ← USER.md rolling backups (14d)
├── hooks/
│   └── on_cron.py             ← NEW · Symlinked from this repo
└── state.db                   ← Hermes native (Reflector reads only)
```

**Hermes' 5 existing self-learning layers are not modified.** L1-L5 don't even know L6 exists.

---

## The 6 self-learning layers (where Reflector sits)

| # | Layer | Trigger | Direction |
|---|---|---|---|
| L1 | Short-term working memory | every turn | now |
| L2 | Long-term Episodic (FTS5) | `session_search` tool | now-query |
| L3 | Dialectic (Honcho plugin, optional) | every N turns | now-reflect |
| L4 | Curated MEMORY.md / USER.md | `nudge` / `flush` | now-decide |
| L5 | Skill auto-evolution + 7-day Curator | ≥5 tool_call + Curator interval | now + 7-day |
| **L6** | **Habit Reflector ⭐** | **daily 4am cron** | **retrospective 30d** |

The Reflector is the only layer that **looks back at history**. Everything else is in-the-moment.

---

## How a claim gets to USER.md (data flow)

```
┌─────────────────┐
│  cron 04:00     │
└────────┬────────┘
         ▼
    ┌─────────┐    cold-start week? idle ≥1h? ≥20h since last? ≥50 msg/30d?
    │ on_cron │──→ NO any → exit
    └────┬────┘
         ▼
    ┌──────────┐  read messages from state.db (last 30d, blacklist-filtered)
    │ distill  │──→ render prompt → Haiku 4.5 → parse JSON claims
    └────┬─────┘
         ▼
    ┌──────────────────────┐  every claim must have ≥3 evidence refs
    │ confidence = compute │  3 signals: ≥5 occurrences + ≥3 sessions + ≤7d ago
    │   (locally, not LLM) │  +0.25 each, base 0.10, optional user_confirmed +0.25
    └────┬─────────────────┘
         ▼
    ┌──────────────────────────────────────────────┐
    │ promoter buckets by confidence:              │
    │   conf ≥0.85  →  backup USER.md + append     │
    │   0.7≤c<0.85  →  candidates/<id>.pending     │
    │   conf <0.7   →  drop (still in daily report)│
    │                                              │
    │ classification == "habit"                    │
    │   →  candidates/<name>.candidate             │
    │      (Curator picks up next 7-day run)       │
    └──────────────────────────────────────────────┘
```

---

## Install (when you actually want to run it on your Hermes)

```bash
# 1. Clone
git clone https://github.com/zane/hermes-habit-reflector
cd hermes-habit-reflector

# 2. Install runtime dep (only needed for --real-api mode)
pip install anthropic

# 3. Link cron hook into Hermes
ln -s "$PWD/hooks/on_cron.py" ~/.hermes/hooks/on_cron.py

# 4. Add config
cat >> ~/.hermes/config.yaml <<EOF

habit_reflector:
  enabled: true
  cron_hour: 4
  window_days: 30
  cold_start_weeks: 1
EOF
```

That's it. Hermes' built-in cron will pick up the hook starting tomorrow 4am.

---

## CLI commands

```bash
python3 -m src.cli dry-run --fixture examples/14-session-fixture.json  # no API call
python3 -m src.cli run --real-api                                       # real run (needs ANTHROPIC_API_KEY)
python3 -m src.cli status                                               # show pending / candidates / blacklist
python3 -m src.cli reject <claim_id> --key-phrase "..." --reason "..."  # blacklist + remove from USER.md
python3 -m src.cli rollback 2026-05-22                                  # restore USER.md from backup
```

---

## Testing

```bash
pip install pytest
python3 -m pytest tests/ -v
```

Expected: `12 passed in 0.02s`.

Test coverage:

| Test | Asserts |
|---|---|
| `test_dry_run_full_pipeline` | end-to-end: fixture → distill → render → promote → USER.md exists |
| `test_blacklist_filters` | blacklisted claim doesn't appear in output |
| `test_cold_start_caps_confidence` | week-1/2 confidence capped at 0.84 |
| `test_usermd_char_budget` | USER.md never exceeds Hermes' 1375-char limit |
| `test_claim_requires_3_evidence` | schema enforces evidence count |
| `test_claim_validates_classification` | only 4 valid classifications accepted |
| `test_compute_confidence_*` | 3 signals + explicit confirmation formula |
| `test_claim_roundtrip` | dict ⇌ Claim serialization |

---

## Design choices worth knowing

1. **Confidence is recomputed locally, not trusted from the model.** The model reports `times_appeared` / `distinct_sessions` / `last_seen_within_days` as raw counts. We compute confidence from a fixed formula — so the model can't "talk up" claims.

2. **Cold-start week 1 doesn't run.** Hermes needs to accumulate ≥50 messages first. Otherwise the distiller would seize on noise.

3. **First 2 successful runs cap confidence at 0.84.** This forces every claim through user-review queue, so the first habits the user sees are vetted.

4. **Reflector doesn't create skills.** It writes `candidates/<name>.candidate` markers. The existing 7-day Curator picks them up and decides whether to actually create the skill. Two cron jobs, clean separation.

5. **No embeddings, no vector DB.** BM25-style keyword retrieval on local SQLite is enough for ~1000 sessions. YAGNI for embeddings until you have 100k+ sessions per user.

6. **Honors blacklist.** When you `reject <claim_id>`, the matching `(classification, key_phrase)` pair goes to a blacklist. Next distiller run filters claims through it before parsing.

---

## What's NOT in v1 (deliberate non-goals)

- ❌ Cross-user habit aggregation (privacy + scope)
- ❌ Embedding-based retrieval (YAGNI until 100k+ sessions)
- ❌ Real-time reflector (batch is fine; cost matters)
- ❌ Reflector auto-creates skills (only Curator does)
- ❌ Bridge to Screenpipe / external systems (must stand alone)

---

## Cost

Distiller runs once per day, reading 30 days of conversation. With Haiku 4.5 ($1 / $5 per MTok):

- Input: ~400k tokens (compressed 30d window) × $1 = $0.40
- Output: ~3k tokens × $5 = $0.015
- **Total: ~$0.40/day · ~$12/month**

Roughly one cup of coffee. Compare to a single Sonnet 4.5 long session ($1-3 just for that one chat).

---

## Project structure

```
hermes-habit-reflector/
├── README.md                          ← This file
├── LICENSE                            ← MIT
├── requirements.txt                   ← anthropic
├── requirements-dev.txt               ← pytest
│
├── docs/
│   └── SPEC.md                        ← Full 14-section design spec
│
├── src/                               ← 6 modules, ~370 lines Python
│   ├── __init__.py
│   ├── schema.py                      ← Claim + EvidenceRef + confidence formula
│   ├── blacklist.py                   ← User-rejected claim signatures
│   ├── distiller.py                   ← Read messages → Haiku → parse claims
│   ├── promoter.py                    ← Write USER.md / candidates / backups
│   ├── render.py                      ← Render habit_memory/YYYY-MM-DD.md
│   └── cli.py                         ← dry-run / run / status / reject / rollback
│
├── hooks/
│   └── on_cron.py                     ← Hermes cron entry point
│
├── examples/
│   └── 14-session-fixture.json        ← 27-message synthetic conversation
│
└── tests/                             ← 12 unit tests, all passing
    ├── test_schema.py
    └── test_pipeline.py
```

---

## Background research

This module was designed as part of a broader SOTA Agent Harness study. See [`docs/SPEC.md`](docs/SPEC.md) for the full design rationale, including:

- How Hermes' 5 existing self-learning layers actually work (with source-level references to `tools/memory_tool.py`, `agent/curator.py`, `plugins/memory/honcho/`)
- Why neither Curator nor Honcho fill this gap (strict invariant: Curator only touches skills; Honcho is a parallel system with its own peer card backend, doesn't write USER.md)
- 3 evaluation hypotheses for v1
- Reflector vs Honcho dialectic vs Curator: what's actually different

---

## Contributing

This is a research prototype, not a production system. PRs welcome but please:

1. Run `pytest tests/ -v` before opening PR
2. Don't add embeddings / vector DB (intentional YAGNI)
3. Don't modify Hermes core (zero-touch invariant)

---

## License

MIT

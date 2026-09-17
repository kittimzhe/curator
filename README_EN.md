# 🧭 InsightLoom

**English** | [简体中文](README.md)

> Weave your saved information into actionable insight.

**InsightLoom** is a self-hosted personal knowledge workbench: drop articles, papers, links, and notes into your inbox, and a team of **visible agents** will triage, summarize, cross-link, and adversarially review them — then generate a daily digest. **Nothing is written to your knowledge base until you approve it.**

> Planned website domain: `insightloomapp.com`

![screenshot](docs/screenshot-p0.png)

## Why InsightLoom

Existing "AI second brain" tools (e.g., khoj) are mostly **passive retrieval**: you ask, they answer. InsightLoom differs by **active processing**:

- 🔍 **Visible pipeline**: open the UI and watch the Classifier, Summarizer, Linker, and Skeptic process your reading queue in real time
- ⚔️ **Adversarial review**: the Skeptic red-teams the Summarizer's output — overgeneralization and hallucination get flagged
- ✅ **Human approval**: agents only submit *proposals*; not a single byte touches your knowledge base before you approve
- 📄 **Zero lock-in**: your knowledge is plain Markdown files on disk (open them directly in Obsidian); SQLite only holds process state
- 🔌 **Any model**: OpenAI-compatible protocol, DeepSeek by default, switch to local Ollama — and it runs without any API key (mock mode)

## Agent Pipeline

```
              ┌──────────┐
              │ 🏷️ Classifier │ depth=read_later
              │            │──────────────────────┐
              └────┬───────┘                       ▼
                   │ depth=deep              ┌───────────┐
          ┌────────┴────────┐                │ 📦 Assembler│
          ▼ (fan-out, parallel)              │            │
   ┌────────────┐   ┌────────────┐           └─────┬─────┘
   │ 📝 Summarizer│   │ 🔗 Linker  │                 │
   └──────┬─────┘   └──────┬─────┘                 │
          └──────┬──────────┘                       │
                 ▼                                  │
          ┌────────────┐                            │
          │ ⚔️ Skeptic │  (fan-in: reviews after both finish)
          └──────┬─────┘                            │
                 └──────────────────────────────────┘
                          ⬇ human approval
                   vault/xxx.md (frontmatter + [[wiki-links]])
```

- The **Classifier** routes by content depth: short items take the "read later" fast lane; substantial content triggers deep processing (tokens spent only where needed)
- The **Summarizer** and **Linker** work in parallel; the Linker has hallucination guards and only cites notes that actually exist
- The **Skeptic** waits for both, then adversarially reviews the summary against the source (verdict: pass / questioned)
- The **Assembler** produces a structured proposal (frontmatter + summary + `[[wiki-links]]` + review record) and queues it for approval

## Getting Started

```bash
# Requires Python 3.10+ (uv recommended)
uv venv --python 3.12 .venv
UV_CACHE_DIR=/tmp/uv-cache uv pip install --python .venv/bin/python \
    fastapi "uvicorn[standard]" langgraph langchain-core openai python-dotenv

# Mock mode (no API key needed — experience the full pipeline)
CURATOR_LLM_MOCK=1 .venv/bin/uvicorn server.app:app --port 8300
# Open http://127.0.0.1:8300

# Real mode (DeepSeek — a few dollars goes a long way)
CURATOR_LLM_API_KEY=sk-xxx .venv/bin/uvicorn server.app:app --port 8300
# Or any OpenAI-compatible provider:
CURATOR_LLM_API_KEY=sk-xxx CURATOR_LLM_BASE_URL=https://api.openai.com/v1 \
CURATOR_LLM_MODEL=gpt-4o-mini .venv/bin/uvicorn server.app:app
```

## Project Structure

```
curator/
├── server/
│   ├── app.py        # FastAPI: inbox/state/approval APIs + static hosting
│   ├── pipeline.py   # LangGraph agent pipeline (classify → parallel → adversarial review → propose)
│   ├── llm.py        # OpenAI-compatible wrapper + mock mode
│   └── store.py      # SQLite process state + vault Markdown writer
├── web/index.html    # Three-panel workbench UI (Inbox / Agent Activity / Approvals)
├── vault/            # Your knowledge base (plain Markdown, Obsidian-compatible)
└── data/             # SQLite + logs (generated at runtime)
```

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/inbox` | Submit content `{title, content, url?}`, triggers the pipeline |
| GET | `/api/state` | Aggregated state (items/events/proposals/vault/LLM) |
| POST | `/api/proposals/{id}/approve` | Approve a proposal → write to vault |
| POST | `/api/proposals/{id}/reject` | Reject a proposal |
| POST | `/api/garden/run` | 🌻 Run the Gardener scan (findings + link proposals) |
| GET | `/api/digest` | Daily digest: 24h stats + vault health + findings |
| GET | `/api/health` | Health check + LLM status |

## Roadmap

> Full product blueprint (5-layer architecture / user journey / milestones) in **Chinese**: [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md)

- [x] **P0** Core loop: inbox → 5-agent pipeline → approval → vault
- [x] **P1a** 🌻 Gardener agent: vault scan for orphan/stale/thin notes, link suggestions through the same approval queue (auto-appends `[[wiki-links]]` on approval) + daily digest page
- [x] **P1c** Retrieval layer: local vector store (Chroma + local ONNX embeddings, no cloud API) + semantic search `/api/search` + semantic Linker + RAG Q&A `/api/ask` (with citations); approved notes are auto-indexed
- [ ] **P1b** Knowledge graph view (link visualization), React frontend
- [ ] **P2** Docker one-command deploy, capture endpoints (bookmarklet → browser extension → Telegram bot), demo GIF, public launch
- [ ] **P3** Local model support (Ollama), checkpointer time-travel, RSS/email capture, multi-user

## Launch Checklist

- Minimal launch checklist: **[`docs/LAUNCH_MIN_CHECKLIST.md`](docs/LAUNCH_MIN_CHECKLIST.md)**

## Current Execution Logs

- Competition tracking ( Cup / Residency): **[`docs/COMPETITION__CUP_2026.md`](docs/COMPETITION__CUP_2026.md)**
- Initialization adjustments: **[`docs/INIT_ADJUSTMENTS.md`](docs/INIT_ADJUSTMENTS.md)**
- Pitch deck template: **[`docs/BP_OUTLINE.md`](docs/BP_OUTLINE.md)**

## Design Decision Records (ADR summary)

1. **Why Markdown instead of a database for knowledge?** — Zero lock-in is the #1 adoption driver; process state (SQLite) is strictly separated from the knowledge itself (files), so you can take your files and leave anytime
2. **Why approval-based instead of agents writing directly?** — Human-in-the-loop as a product feature, not a technical concept; trust is existential for a personal knowledge base
3. **Why does the Linker filter hallucinated references?** — LLMs cite notes that don't exist; every agent output passes three gates before touching disk (filter / adversarial review / human approval)

## License

MIT

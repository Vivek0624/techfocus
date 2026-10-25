# Architecture

```
 Browser (localhost:3000)                 MacBook only (127.0.0.1)
 ┌──────────────────────┐   REST/JSON   ┌───────────────────────────────────────────────┐
 │ Next.js App Router   │ ────────────▶ │ FastAPI  services/api                          │
 │ apps/web             │               │  routers/   core · content · agents_ig         │
 │ no secrets           │ ◀──────────── │  services/  analytics · queries                │
 └──────────────────────┘               │  instagram/ client (graph.instagram.com)       │
                                        │             service (sync, tokens, publish)    │
                                        │  agents/    tools → registry → orchestrator    │
                                        │             providers: mock | bedrock | agentcore
                                        │  SQLite via SQLAlchemy + Alembic (Postgres-ready)
                                        └────────┬──────────────┬──────────────┬─────────┘
                                                 │              │              │
                                     Meta OAuth + Graph   Amazon Bedrock   AgentCore Runtime
                                     (Instagram Login)    (Strands, local) (remote, optional)
```

## Boundaries
- **Frontend ↔ backend:** only the documented REST API (`/api/docs`). The browser holds no tokens or keys.
- **Backend ↔ agents:** agents get a `ToolContext` and may call only the tools listed for them. Tools go through
  the service layer; there is no SQL, shell, filesystem or network tool.
- **Writes:** agent tools can create drafts, planned experiments, *proposed* calendar items and *pending*
  approval requests. Publishing exists only in `instagram/service.execute_publish`, which refuses anything
  without an approved approval request, refuses duplicates, and writes an `external_write_audit` row.
- **Demo vs real:** every metric row has `source` (`demo`/`manual`/`instagram_api`) and content rows have
  `is_demo`. Queries select one partition; they never mix.

## Data
21 tables (see `services/api/app/models.py`): settings, accounts, encrypted tokens, OAuth states, account and
media snapshots (unique per day → no duplicates), media, content ideas (+ full Reel package JSON), assets,
calendar items, approvals, publishing jobs (unique per calendar item → no double publish), personas,
experiments + observations, agent definitions, runs, tool-call audit, external-write audit, growth plans, daily
tasks, research sources, learning records.

## Orchestration
See agent-design.md. Workflows are fixed sequences (deterministic). Specialists never call each other.

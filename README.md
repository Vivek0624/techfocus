# Vivek TechFocus — AI Growth Manager

A local-first dashboard for running the `@vivek_techfocus` Instagram account: growth tracking toward the 10,000
follower target, a content library, a Reel Studio, a calendar with approval-gated publishing, experiments, and
eight AI agents (Strands Agents on Amazon Bedrock, deployable to AgentCore).

It works with no credentials at all (clearly labelled **demo mode**). Connect Instagram and it switches to real,
source-labelled data. It never invents metrics, and nothing is ever posted without your explicit approval.

```
 Browser ─▶ Next.js (apps/web, :3000) ─REST─▶ FastAPI (services/api, :8000) ─▶ SQLite
                                                  │  agents: mock | Strands+Bedrock | AgentCore
                                                  └─▶ Instagram Graph API (Instagram Login, OAuth)
```
More: [architecture](docs/architecture.md) · [agents](docs/agent-design.md) · [API capabilities](docs/api-capabilities.md) ·
[metrics](docs/metrics.md) · [security](docs/security.md) · [troubleshooting](docs/troubleshooting.md)

## Prerequisites (macOS)
- Python 3.11+ (3.13 used) and [uv](https://docs.astral.sh/uv/) — `brew install uv`
- Node.js 20+ (22 used) and npm
- Optional: AWS CLI v2 (Bedrock / AgentCore), a Meta developer account (Instagram)

## Install and run
```bash
make install          # Python venv + npm packages
./dev.sh              # migrates the DB, starts API + web, waits for health, prints URLs
./stop.sh             # stops both
```
- Dashboard: http://localhost:3000
- API: http://localhost:8000 · OpenAPI docs: http://localhost:8000/api/docs

The first `./dev.sh` copies `.env.example` to `.env` (settings) and `.env.secrets.example` to `.env.secrets` (keys). Both are git-ignored; only the `.example` files are committed. Both servers bind to 127.0.0.1 only.

## Demo mode
Starts automatically. The synthetic account is named `demo_techfocus (SYNTHETIC)`, every metric carries a
`DEMO` badge, and an amber banner stays on screen. **Settings → Reset demo data** rebuilds it without touching
real records. Agent "simulate failure" lets you see error states.

First thing to do: **Settings → Growth target** — 10,000 followers, 30 days, your real starting count (339) and
start date. Until Instagram is connected you can also enter daily follower counts by hand on the Instagram
page (stored as `manual`).

## Connect Instagram
Full guide: [docs/instagram-setup.md](docs/instagram-setup.md). Short version:
1. Make the account a Creator account.
2. Create a Meta app (Instagram API with Instagram Login), add redirect URI
   `http://localhost:8000/api/instagram/callback`, add yourself as an Instagram tester.
3. `make key` → put it in `.env.secrets` as `TOKEN_ENCRYPTION_KEY`; add `META_APP_ID`, `META_APP_SECRET` there too.
4. `./stop.sh && ./dev.sh` → Instagram Connection → Connect → log in on instagram.com.

## AI agents
| mode | set in `.env` | needs |
| --- | --- | --- |
| mock (default) | `AGENT_MODE=mock` | nothing; deterministic, grounded in your data |
| local Bedrock | `AGENT_MODE=bedrock`, `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID` | model access enabled in that region |
| AgentCore | `AGENT_MODE=agentcore`, `AGENTCORE_RUNTIME_ARN` | a deployed runtime (`make build-agentcore`, then the AgentCore CLI) |

Setup, IAM policies, costs and teardown: [docs/aws-setup.md](docs/aws-setup.md). Nothing is provisioned automatically.

## Tests and checks
```bash
make test        # backend pytest + frontend vitest
make lint        # ruff + eslint
make typecheck   # mypy + tsc
make evals       # agent evaluation suite (mock by default)
```

## Security and cost notes
- Secrets live only in `.env.secrets` (git-ignored, file mode 600); Instagram tokens are Fernet-encrypted at rest; logs are redacted.
- Publishing: request approval → approve in the UI → backend re-checks everything → audit log. Agents cannot publish.
- No automated following, liking, commenting or messaging.
- Mock mode and local use cost nothing. Bedrock is billed per token; AgentCore, S3 and scheduling only if you deploy them.
- Before exposing this beyond your Mac, read [docs/security.md](docs/security.md). Vercel notes: [infra/vercel](infra/vercel/README.md).

## About the 10k-in-30-days goal
From 339 followers that needs ~320 net followers a day. The app tracks it honestly (required vs actual pace) and
shows scenarios as arithmetic, not predictions.

Compatibility checked 2026-10-22: Meta Instagram Platform docs, Strands Agents 1.62, bedrock-agentcore 1.24,
FastAPI 0.159, SQLAlchemy 2.1, Next.js 16.

# TechFocus: AI Instagram Growth Manager

A local-first app that helps the `@vivek_techfocus` Instagram account decide what to post next and learn from
its own results. It pulls real numbers from Instagram, explains them in plain words, and uses AI to write hooks,
captions and Reel scripts.

- **Home:** your next Reel (topic, hook, why, best time to post) and a step-by-step guide
- **Ideas:** a notebook for trying angles: add, edit, duplicate, archive, board and week views
- **Create:** AI hooks, captions, full Reel scripts, one idea turned into 5 formats
- **Insights:** the coach (what to repeat, fix, stop), audience, comments, posting times
- **Profile:** connect Instagram; **Settings:** your voice, import your Instagram data, glossary

It runs with no keys at all, using sample data marked **Demo**. Numbers always come from Instagram or your own entries,
never invented, and nothing is posted without your approval.

```
Browser ─▶ Next.js (apps/web, :3001) ─REST─▶ FastAPI (services/api, :8001) ─▶ SQLite (services/api/data/app.db)
                                                 ├─▶ Instagram API with Instagram Login (OAuth callback on https :8443)
                                                 └─▶ AI model: Gemini (free) | OpenAI | Claude | Bedrock | Ollama | off
```

## 1. Prerequisites (macOS)

```bash
brew install uv node@22
```
- Python 3.13 is installed by `uv` automatically; Node.js 20+ is needed.
- Don't use `sudo` for anything in this project.

## 2. Get the code

```bash
git clone https://github.com/Vivek0624/techfocus.git
cd techfocus
git checkout dev
git checkout -b <your-name>        # e.g. tanmay (see "Working as a team" below)
```

## 3. Install and run

```bash
make install     # Python environment + npm packages (first time, a few minutes)
./dev.sh         # creates .env and .env.secrets from the templates, migrates the DB, starts everything
```

Open **http://localhost:3001**. Stop with `./stop.sh`. Restart after changing `.env` / `.env.secrets`:

```bash
./stop.sh; ./dev.sh
```

| What | URL |
| --- | --- |
| App | http://localhost:3001 |
| API + docs | http://localhost:8001/api/docs |
| Instagram login callback | https://localhost:8443 |

Logs: `logs/api.log`, `logs/web.log`.

## 4. Settings and keys

There are two files. Both are **git-ignored**, so never commit them, and don't paste keys into chat or Slack.

| File | Holds | Template |
| --- | --- | --- |
| `.env` | ports, model name, modes (no secrets) | `.env.example` |
| `.env.secrets` | API keys, Meta app secret, encryption key | `.env.secrets.example` |

### AI (free Gemini): optional, without it the app uses built-in templates
1. Go to https://aistudio.google.com → **Get API key** → create a key.
2. In `.env.secrets`: `OPENAI_API_KEY=<your Gemini key>`. Gemini is used through its OpenAI-compatible API.
3. `.env` already has `AGENT_MODE=openai`, the Gemini URL and `OPENAI_MODEL_ID=gemini-flash-lite-latest`
   (fast; `gemini-flash-latest` writes better but takes about a minute).
4. Restart. In **Create → Hooks**, results come from AI when it works and from templates when it doesn't.

Other options (set `AGENT_MODE` in `.env`, keys in `.env.secrets`):
- `mock`: no AI
- `anthropic`: `ANTHROPIC_API_KEY`
- `openai` (real OpenAI): remove `OPENAI_BASE_URL`
- `bedrock`: AWS keys and `BEDROCK_MODEL_ID`
- `ollama`: a local model, no key

### Encryption key (needed before connecting Instagram)
```bash
make key
```
Put the printed value in `.env.secrets` as `TOKEN_ENCRYPTION_KEY=...`.

### Connect Instagram (optional; only the account owner needs this)
1. The Instagram account must be a **Creator** or **Business** account.
2. At developers.facebook.com, create an app with the use case **"Manage messaging & content on Instagram"**,
   then go to **API setup with Instagram login**:
   - Copy the **Instagram app ID** and **Instagram app secret** into `.env.secrets` as `META_APP_ID` and
     `META_APP_SECRET`. These are not the Facebook App ID at the top of the dashboard.
   - Under **Business login settings**, add the redirect URI `https://localhost:8443/api/instagram/callback`.
   - Add the account as an **Instagram tester** and accept the invite in the Instagram app.
3. Restart, open **Profile → Connect**, and log in on instagram.com.
4. After login, the browser warns about the localhost certificate (it's self-signed on your Mac). Click **Advanced →
   Proceed**.

Full guide: [docs/instagram-setup.md](docs/instagram-setup.md). Each person's Instagram data stays in their own local
database, which is never committed.

### Your saved and liked Reels (optional)
Instagram's API can't read saved posts. In the Instagram app, go to **Accounts Center → Your information and
permissions → Download your information**. Choose Saved, Likes and Followers, **JSON** format, all time. Upload the
.zip in **Settings → Import my data**.

## 5. Working as a team (hackathon)

Branches:

| Branch | Purpose |
| --- | --- |
| `main` | stable, demo-ready. Only updated from `dev`. |
| `dev` | integration: everyone's work comes together here |
| `vivek`, `tanmay`, `<name>` | one branch per person |

Daily flow:
```bash
git checkout <your-name>
git pull origin dev                 # get everyone's latest work
# ...make changes...
git add -A && git commit -m "what you changed"
git push -u origin <your-name>
```
Then on GitHub, open a **Pull request from `<your-name>` into `dev`**. When `dev` is working, someone opens a PR
from `dev` into `main`.

Rules that keep everyone safe:
- Never push straight to `main`.
- Run the checks below before opening a PR.
- If two people edit the same file, pull `dev` often, because small merges are easier.
- Never commit `.env`, `.env.secrets`, the `data/` folder or `logs/`; they're already ignored. Check with
  `git status` before committing.

## 6. Tests and checks

```bash
make test        # backend (pytest) + frontend (vitest)
make lint        # ruff + eslint
make typecheck   # mypy + tsc
```

## 7. Troubleshooting

| Problem | Fix |
| --- | --- |
| "Port 8001 is already in use" | `./stop.sh`, or change `API_PORT` / `WEB_PORT` in `.env` (also update `WEB_ORIGIN`, `NEXT_PUBLIC_API_URL`) |
| "Backend not installed" | `make install` |
| Permission errors / files owned by root | Something was run with `sudo`. Run `sudo chown -R $(whoami) .` once, and never use sudo here again. |
| Instagram "Invalid platform app" | You used the Facebook App ID; use the **Instagram** app ID from "API setup with Instagram login" |
| Instagram "Invalid redirect_uri" | The redirect URI in Meta must be exactly `https://localhost:8443/api/instagram/callback` |
| AI results say "template" | Check `OPENAI_API_KEY` in `.env.secrets` and restart; the free tier has a daily limit |

More: [architecture](docs/architecture.md) · [agents](docs/agent-design.md) · [API capabilities](docs/api-capabilities.md) ·
[metrics](docs/metrics.md) · [security](docs/security.md) · [troubleshooting](docs/troubleshooting.md)

## Security notes
- Secrets live only in `.env.secrets` (git-ignored, file mode 600). Instagram tokens are encrypted in the database,
  and logs are redacted.
- Servers listen on 127.0.0.1 only (your Mac).
- Publishing needs your approval in the UI, and every external write is audited. There is no automated following,
  liking, commenting or messaging.

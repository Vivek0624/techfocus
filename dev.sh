#!/usr/bin/env bash
# Start API + web on localhost, wait for health, print URLs. Stop with ./stop.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example (demo mode)."; }
[ -f .env.secrets ] || { cp .env.secrets.example .env.secrets; chmod 600 .env.secrets; echo "Created .env.secrets (empty). Add your keys there."; }
set -a; source .env; source .env.secrets; set +a
API_PORT="${API_PORT:-8000}"; WEB_PORT="${WEB_PORT:-3000}"
mkdir -p .run logs

[ -x services/api/.venv/bin/uvicorn ] || { echo "Backend not installed. Run: make install"; exit 1; }
[ -d apps/web/node_modules ] || { echo "Frontend not installed. Run: make install"; exit 1; }

if [ "$(id -u)" = "0" ]; then echo "Don't run this with sudo. Run ./dev.sh as your normal user."; exit 1; fi
for p in "$API_PORT" "$WEB_PORT" ${HTTPS_CALLBACK_PORT:-}; do
  # lsof only lists our own processes without sudo, so also probe the port directly.
  if lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || nc -z 127.0.0.1 "$p" >/dev/null 2>&1; then
    owner=$(ps -o user= -p "$(pgrep -f -- "--port $p|-p $p" | head -1)" 2>/dev/null | tr -d ' ')
    echo "Port $p is already in use${owner:+ by user '$owner'}."
    [ "$owner" = "root" ] && echo "It was started with sudo. Stop it with: sudo pkill -f 'port $p|-p $p'"
    echo "Otherwise run ./stop.sh, or change the port in .env."
    exit 1
  fi
done

( cd services/api && .venv/bin/alembic upgrade head >/dev/null )
( cd services/api && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" \
    > "$ROOT/logs/api.log" 2>&1 & echo $! > "$ROOT/.run/api.pid" )
# Meta only accepts https redirect URIs, so the OAuth callback also gets a local https listener
# (self-signed cert, localhost only). Same app and database as the http API.
if [ -n "${HTTPS_CALLBACK_PORT:-}" ]; then
  if [ ! -f .certs/localhost.pem ]; then
    mkdir -p .certs
    openssl req -x509 -newkey rsa:2048 -nodes -days 825 -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
      -keyout .certs/localhost-key.pem -out .certs/localhost.pem >/dev/null 2>&1
    chmod 600 .certs/localhost-key.pem
  fi
  ( cd services/api && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$HTTPS_CALLBACK_PORT" \
      --ssl-keyfile "$ROOT/.certs/localhost-key.pem" --ssl-certfile "$ROOT/.certs/localhost.pem" \
      > "$ROOT/logs/api-https.log" 2>&1 & echo $! > "$ROOT/.run/api-https.pid" )
fi
# If a previous `sudo` run left an unwritable .next, build into .next-local instead.
NEXT_DIST_DIR=".next"
if [ -e apps/web/.next ] && [ -n "$(find apps/web/.next ! -user "$(id -u)" -print -quit 2>/dev/null)" ]; then
  NEXT_DIST_DIR=".next-local"
  echo "Note: apps/web/.next is owned by another user (old sudo run). Using .next-local."
  echo "      Clean up later with: sudo rm -rf apps/web/.next"
fi
( cd apps/web && NEXT_DIST_DIR="$NEXT_DIST_DIR" NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:$API_PORT}" \
    nohup npx next dev -H 127.0.0.1 -p "$WEB_PORT" > "$ROOT/logs/web.log" 2>&1 & echo $! > "$ROOT/.run/web.pid" )

wait_for() { for _ in $(seq 1 60); do curl -fs $1 >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }
if wait_for "http://127.0.0.1:$API_PORT/api/health"; then echo "API   ✓ http://localhost:$API_PORT  (docs: /api/docs)"
else echo "API failed to start — see logs/api.log"; fi
if wait_for "http://127.0.0.1:$WEB_PORT"; then echo "Web   ✓ http://localhost:$WEB_PORT"
else echo "Web failed to start — see logs/web.log"; fi
[ -n "${HTTPS_CALLBACK_PORT:-}" ] && wait_for "-k https://127.0.0.1:$HTTPS_CALLBACK_PORT/api/health" \
  && echo "OAuth ✓ https://localhost:$HTTPS_CALLBACK_PORT  (Instagram login callback)"
curl -s "http://127.0.0.1:$API_PORT/api/health" && echo

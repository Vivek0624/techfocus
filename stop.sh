#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
for svc in web api api-https; do
  f="$ROOT/.run/$svc.pid"
  if [ -f "$f" ]; then
    pid=$(cat "$f")
    pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null && echo "stopped $svc ($pid)"
    rm -f "$f"
  fi
done
set -a; [ -f "$ROOT/.env" ] && source "$ROOT/.env"; [ -f "$ROOT/.env.secrets" ] && source "$ROOT/.env.secrets"; set +a
for p in "${API_PORT:-8000}" "${WEB_PORT:-3000}" ${HTTPS_CALLBACK_PORT:-}; do
  pids=$(lsof -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$pids" ] && kill $pids 2>/dev/null && echo "freed port $p"
done
# Give stopped servers a moment to release their ports.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  nc -z 127.0.0.1 "${API_PORT:-8000}" >/dev/null 2>&1 || nc -z 127.0.0.1 "${WEB_PORT:-3000}" >/dev/null 2>&1 || break
  sleep 0.5
done
for p in "${API_PORT:-8000}" "${WEB_PORT:-3000}"; do
  if nc -z 127.0.0.1 "$p" >/dev/null 2>&1; then
    echo "Port $p is still in use by a process this user can't stop (probably started with sudo)."
    echo "  sudo pkill -f 'port $p|-p $p'"
  fi
done
true

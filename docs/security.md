# Security

## Local boundary (v1)
- API and web bind to **127.0.0.1**. Nothing is reachable from your Wi-Fi network.
- No login in local mode: anyone with access to your Mac user session can use the dashboard.
- CORS allows only `WEB_ORIGIN`.

## Secrets
- All secrets live in `.env` (git-ignored) and are read server-side by `pydantic-settings`. The browser gets only
  `NEXT_PUBLIC_API_URL`. `/api/settings` reports *whether* a secret is set, never its value.
- Instagram tokens are encrypted with Fernet (AES-128-CBC + HMAC) using `TOKEN_ENCRYPTION_KEY`, which is never
  stored in the database. A stolen `app.db` alone does not reveal tokens.
- Logs are JSON and pass through a redactor for `access_token=`, `client_secret=`, bearer tokens and raw IG/EAA tokens.
- Clients never see stack traces: unhandled errors return `{"error":"internal error"}`.

## OAuth
`state` is 32 random bytes, stored server-side, single use, 10-minute TTL, compared in constant time.

## Key rotation and backup
1. `make key` → new key. 2. `.env`: `TOKEN_ENCRYPTION_KEY=<new>,<old>`. 3. `make rotate-keys`.
4. Remove `<old>`. Back up `.env` (password manager) separately from `services/api/data/app.db`
   (e.g. Time Machine). Losing the key means reconnecting Instagram; no other data is lost.

## External writes
Publishing requires: an approval request → explicit human approval in the UI → backend check in
`execute_publish` (status approved, not demo, public https asset, caption limits, no existing job, scope granted).
Each attempt is written to `external_write_audit`. Agents have no publish/comment/message tool at all.
No following, liking, commenting or DMs are automated.

## Before exposing to the internet
Set `APP_ENV=production` (enables mandatory `API_AUTH_TOKEN` bearer auth), terminate TLS, move to Postgres,
put secrets in AWS Secrets Manager, use HTTPS redirect URIs, keep the token only server-side (proxy from the
frontend server, not the browser), add per-user auth if anyone else will use it, and rate-limit the API.

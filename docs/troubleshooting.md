# Troubleshooting

| symptom | fix |
| --- | --- |
| `Port 8000 is busy` | `./stop.sh`, or change `API_PORT` / `NEXT_PUBLIC_API_URL` in `.env` |
| Web shows "cannot reach API" | `curl localhost:8000/api/health`; check `logs/api.log`; `NEXT_PUBLIC_API_URL` must match |
| Connect button says 503 | `META_APP_ID`, `META_APP_SECRET`, `TOKEN_ENCRYPTION_KEY` missing in `.env` |
| `invalid_state` after login | the login took >10 min or the page was reloaded; click Connect again |
| `Invalid redirect_uri` from Instagram | the URI in the Meta dashboard must match `META_REDIRECT_URI` exactly. If localhost is refused, use an HTTPS tunnel you control and set both to that URL |
| "Insufficient developer role" | add the account as an Instagram tester and accept the invite |
| Sync 409 "personal account" | switch to a Creator account in the Instagram app, reconnect |
| follows/unfollows "unavailable" | expected under 100 followers |
| Metrics blank for 1–2 days | Meta insights lag up to 48 h |
| Agent failed: credentials/model access | see aws-setup.md Mode B; enable the model in that region |
| Agent stuck "cancelling" | a model call is finishing; it flips to cancelled when the worker stops (≤ timeout) |
| Publish 422 "public https" | upload the video to S3/public host, paste the https URL as the asset |
| Reset everything demo | Settings → Reset demo data (real records are kept) |
| Fresh start | `./stop.sh && rm services/api/data/app.db && ./dev.sh` (deletes real data too) |

# Connect your Instagram account

You never give this app your Instagram password. You log in on instagram.com and Meta hands the app a token.

## 1. Make the account professional
Instagram app → Settings → Account type and tools → Switch to professional account → **Creator**.

## 2. Create a Meta app (one time, ~10 min)
1. https://developers.facebook.com/apps → Create app → use case **"Manage messaging & content on Instagram"**
   (Instagram API with Instagram Login). App type Business.
2. In the app: **Instagram → API setup with Instagram business login**.
3. Under *Set up Instagram business login* → Business login settings → **OAuth redirect URIs**, add exactly:
   `http://localhost:8000/api/instagram/callback`
   (If Meta rejects `http://localhost`, run the API behind an HTTPS tunnel you control and use that URL in both
   places; see troubleshooting.md.)
4. Under **Roles → Instagram testers**, add `vivek_techfocus`, then accept the invite in the Instagram app
   (Settings → Website permissions → Apps and websites → Tester invites). Development-mode apps only work for testers.
5. Copy the **Instagram app ID** and **Instagram app secret** (not the Facebook app ID).

## 3. Configure locally
```bash
services/api/.venv/bin/python scripts/gen_key.py   # copy output
```
In `.env`: `META_APP_ID=…`, `META_APP_SECRET=…`, `TOKEN_ENCRYPTION_KEY=<generated>`. Restart (`./stop.sh && ./dev.sh`).

## 4. Connect
Dashboard → Instagram Connection → **Connect Instagram** → log in on instagram.com → allow the permissions.
You return to the dashboard; the first sync runs automatically. The page shows each permission and whether it was granted.

## 5. Test real API access
- **Sync now** on the Instagram page, or `curl -X POST localhost:8000/api/instagram/sync`.
- `curl localhost:8000/api/instagram/status` should show `"connected": true` and the token expiry.
- Overview switches from DEMO to live data labelled `instagram_api`.

## Notes
- Under 100 followers, follows/unfollows insights are not returned; the dashboard shows them as unavailable.
- Tokens last 60 days and are refreshed automatically when <10 days remain (on sync).
- Disconnect deletes the local token; also remove the app in Instagram → Settings → Apps and websites.
- Publishing needs `instagram_business_content_publish` and a **public https** video URL (see aws-setup.md → S3).
  Without those, use the per-item **Manual post checklist**.

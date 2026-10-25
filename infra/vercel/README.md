# Optional: frontend on Vercel (not done automatically)

Only `apps/web` can go to Vercel. The FastAPI backend and agents cannot run there unchanged
(long-running agent threads, local SQLite, the in-process scheduler).

1. Deploy the API somewhere persistent (AWS App Runner / ECS Fargate / a small EC2), with
   `APP_ENV=production`, `API_AUTH_TOKEN`, Postgres via `DATABASE_URL`, secrets in AWS Secrets Manager.
2. Set `WEB_ORIGIN=https://<your-vercel-domain>` on the API (CORS) and update `META_REDIRECT_URI`
   to `https://<api-domain>/api/instagram/callback` in both `.env` and the Meta app dashboard.
3. In Vercel: root directory `apps/web`, env `NEXT_PUBLIC_API_URL=https://<api-domain>`.
4. Do not put `API_AUTH_TOKEN` in `NEXT_PUBLIC_*`. Put the API behind an authenticating proxy
   (e.g. a Next.js route handler that holds the token server-side, plus Vercel password protection),
   because anything in the browser bundle is public.
5. Videos for publishing must live on public HTTPS storage (S3), never on the server's disk.

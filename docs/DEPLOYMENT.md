# GitHub, Vercel, Railway and Telegram

Verified against the official platform documentation on 15 October 2026. These are setup instructions; no hosting-account deployment was performed during implementation.

## Repository and database

Create an empty GitHub repository. Commit the contents of this project root, not a parent containing another `GEF_system` directory. `app.py`, `requirements.txt`, `pyproject.toml`, `gef/`, `migrations/` and `static/` belong at the repository root. `.env` and runtime databases are ignored.

Provision PostgreSQL. Use TLS and a reachable URL. For a Vercel function use a public/pooled PostgreSQL URL, not a Railway-private hostname. This application uses the psycopg driver and `NullPool`; let a provider-side pool bound aggregate serverless connections. For migrations, use the provider's direct/session-mode connection URL if its transaction pool does not support migration operations. Never run schema migrations concurrently from multiple deployments.

All commands below run from the repository root with the project's Python environment active. Keep secrets in environment settings or a git-ignored local `.env`, never command history/URLs committed to Git.

## Vercel

1. Create/import a Vercel project from GitHub and select the root directory containing `app.py`. Use FastAPI/native Python framework detection. The supported entrypoint is `app.py` exporting `app`; no `uvicorn.run()` is called on import.
2. Use Python 3.12 (`.python-version` and `pyproject.toml`). Dependencies are pinned in `requirements.txt`. No frontend build step is needed.
3. Set **Production** variables: `APP_ENV=production`, `DATABASE_URL`, a unique `SESSION_SECRET` (32+ characters), and `APP_ORIGIN` to the exact public production HTTPS origin. Configure desired providers. Do not paste a localhost URL.
4. Explicitly apply `alembic upgrade head` against that same database from a secure local/CI operator session. Provision the first admin with `python manage.py create-admin --username your_admin`. The CLI prompts for a password and prints a one-time recovery code; save it securely. Do not run this automatically on cold start.
5. Deploy. Inspect `/health/live` and `/health/ready`. An unavailable/unmigrated database must fail readiness. Check `/`, `/profile`, `/admin`, `/api/stations`, `/static/js/app.js`, and a deliberately missing asset/API (should remain 404).
6. After you know the final domain, confirm/update `APP_ORIGIN` and redeploy if necessary. Configure optional custom domains before using them as the Mini App launch origin.

This project deliberately avoids legacy `builds` and broad rewrites. Current native FastAPI detection serves the one app and supports its static mount. Static assets remain under `/static`; index navigation is restricted to the explicit application routes. Runtime persistence uses PostgreSQL, not a function directory or `/tmp`.

Preview deployments can be protected by Vercel's deployment protection. Telegram cannot bypass a Vercel sign-in/protection wall just because the URL uses HTTPS. Use the **public production URL** for bot launch configuration; do not put a deployment-bypass secret into client code. For previews, use an isolated database and matching preview-specific origin/secret. Do not accidentally expose production admin provisioning variables to previews.

Official references:
- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes/python

## Railway

1. Create a project, deploy from the GitHub repository, and attach PostgreSQL. The included Dockerfile is the build source.
2. Set `DATABASE_URL` from the PostgreSQL service reference. Railway's internal URL is usable for this Railway service; use the public URL for local operator commands or Vercel access.
3. Set `APP_ENV=production`, a unique `SESSION_SECRET`, `APP_ORIGIN`, and optional providers. If the final domain is not generated yet, generate it in service networking, copy its HTTPS origin into `APP_ORIGIN`, and redeploy before testing account writes.
4. `railway.toml` runs `alembic upgrade head` in the **pre-deploy step**, not inside application import/startup. Back up production data before later schema upgrades. Keep a single controlled migration job when scaling replicas.
5. Docker starts `uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers`. Railway supplies `PORT`. Readiness is `/health/ready`, with a 60-second health timeout and bounded restart policy.
6. In a secure operator session using the correct reachable database environment, run `python manage.py create-admin --username your_admin` once. A Railway one-off command/shell can also run it; avoid logging real provisioning passwords.
7. Open the generated HTTPS domain. Sign in, add a station, choose its coordinates, publish, and confirm another visible browser sees it within 25 seconds. Redeploy and verify persistence.

No volume is required for accounts/stations/avatars: PostgreSQL stores them. Container filesystem contents are disposable. Do not turn SQLite into the production database by mounting a local data directory.

Official reference: https://docs.railway.com/guides/fastapi

## Telegram Mini App

1. Create/select your own bot with the official BotFather account. Keep its token server-side. `@WebShadoWin` is only the configured support contact; it does not identify the Mini App bot.
2. In BotFather configure the bot's menu button/Web App with the **public production HTTPS URL**. Alternatively use a bot message's `web_app` button pointing at that URL. No long-polling bot process is required to launch this web app.
3. Optionally set `TELEGRAM_BOT_TOKEN` in the server environment. The frontend sends raw `initData` to `/api/telegram/verify`; the server validates HMAC and a five-minute freshness limit. This is verification only, not an application login/account-link flow. App membership continues to use the implemented username/password accounts. `initDataUnsafe` never grants a role.
4. Test iOS, Android, Desktop and web clients. SDK initialization is progressive; ordinary browsers do not require Telegram. Capability checks guard LocationManager, viewport and theme features. Your explicit local theme preference wins.
5. The location adapter can use supported Telegram LocationManager requests as a bounded fallback. Continuous foreground updates still require browser `watchPosition`. If the client cannot provide continuous updates, use external navigation. Background/screen-locked navigation is not guaranteed.
6. Verify session cookies on each target client. They are HttpOnly, SameSite=Lax and Secure on HTTPS. A browser that blocks third-party iframe cookies may need opening the production app directly or a client that supports the shared-origin WebView session. Do not weaken session security or accept arbitrary Telegram IDs to bypass this.

Official SDK/auth/location reference: https://core.telegram.org/bots/webapps

## Release check

- `/health/ready` succeeds with the production database.
- One administrator is provisioned, no universal password exists, and no secrets are committed.
- A normal user gets 401/403 from admin APIs.
- A newly published station appears in both cards and map with correct category filters.
- Provider URLs, attribution, rate limits, domain restrictions and production service plans are configured.
- Real devices confirm HTTPS location, road routing, foreground tracking and cookie behavior.
- Live public station data is entered; DEMO data is never mistaken for actual operational records.
- The manual checklist has recorded pass/fail results; an untested item is left unverified.

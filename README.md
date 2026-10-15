# GEF_system

A complete shared-origin station finder for Uzbekistan: **HTML, CSS, JavaScript ES modules, Python FastAPI, SQLAlchemy, PostgreSQL and Leaflet**. One Python application serves the interface and `/api/*` on either Vercel or Railway. There is no mandatory separate frontend deployment or JavaScript build.

O‘zbekcha tez boshlash: [docs/START_UZ.md](docs/START_UZ.md).

## Start locally

Use Python **3.12**. From this repository's root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py init-local
alembic upgrade head
python manage.py create-admin --username your_admin
python manage.py seed-demo --confirm-demo
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv`, then use `\.venv\Scripts\Activate.ps1` (or call `\.venv\Scripts\python.exe` directly). Open **http://localhost:8000**. Sign in through Profile with the administrator account you just created, then open **Admin panel** or `/admin`.

`init-local` explicitly creates a git-ignored `.env` with a fresh secret; it refuses to overwrite an existing file. `seed-demo` is optional and **development-only**. Its 12 fictional entries are marked DEMO; it fabricates no users, visits or ratings. Skip it for an empty real application. SQLite is supported only for development/tests; production refuses SQLite.

If port 8000 is occupied, use `python manage.py init-local --port 8080` on a fresh checkout, or set `APP_ORIGIN=http://localhost:8080` in the existing `.env`, then start Uvicorn on port 8080. A LAN HTTP address is generally not a secure browser context: phone geolocation needs the deployed HTTPS site, even when your laptop's localhost works.

Road routing and reverse geocoding require configured external services. Without them, stations/maps remain usable, coordinates are shown for the origin, and Yandex Maps handoff works. Read [provider setup](#maps-routing-and-addresses); these integrations are implemented, but an actual provider must be selected. AI station questions work from the database without an external model key.

## Architecture

```text
app.py                      Vercel/Railway entrypoint; HTTP security, assets, health
gef/config.py               Server settings and browser-safe configuration
gef/db.py, models.py        Lazy database access and relational data models
gef/schemas.py              Server validation and category-specific rules
gef/security.py             Argon2id, sessions, CSRF, recovery, durable rate limits
gef/stations.py             Hours, distances, filters, pricing and pressure ranking
gef/providers.py            Road-routing and reverse-geocoding adapters/cache
gef/assistant.py            Database station answers plus optional LLM wording
gef/api.py                  Public, account and admin APIs
static/index.html           Semantic application shell
static/styles.css           Responsive light/dark interface
static/js/                  Focused map/location/navigation/account/admin modules
static/locales/             Complete uz.json, ru.json and en.json dictionaries
static/vendor/leaflet/      Bundled Leaflet 1.9.4 and marker assets
migrations/                 Explicit versioned Alembic migration
manage.py                   Local setup, initial admin, DEMO seed, cleanup
Dockerfile, railway.toml    Railway build/start/migration/health configuration
requirements*.txt           Pinned runtime dependencies and development tests
```

Nothing creates directories, database files, tables, demo data or network connections at module import. Connections are created lazily, use `NullPool`, and are closed at request completion. Production should use a **PostgreSQL pooled URL** appropriate to serverless concurrency. Database connect timeout is 5 seconds; PostgreSQL statement timeout is 10 seconds. Migration execution is an explicit CLI/pre-deployment action, never a cold-start hook.

The only browser-local records are guest favorites and language/theme preferences. Users, avatars, sessions, recovery hashes, stations/products, favorites, visits/ratings, support, audit events and provider caches are relational database records.

## Functionality

- Four public sections: Home, Favorites, AI Assistant, Profile. Phone bottom navigation; desktop sidebar; adaptable tablet/TV layout.
- Real Leaflet maps, an independent admin coordinate picker, draggable marker, accuracy circle, manual origin selection and map resize recovery.
- Four categories with category-specific prices/units: Fuel, Metan, Propan, Elektr. Gas pressure and EV power/connectors remain distinct.
- Open-now combines with default, cheapest or nearest sorting. Fuel comparisons use the selected grade; EV comparisons use the selected billing unit. Unknown/unavailable prices rank after known available prices.
- Tashkent-time weekly hours, overnight intervals, 24/7 and temporary overrides. Opening hours and product availability are independent.
- Default Fuel/Elektr ranking: confirmed visits, mean rating, rating count, station ID. Gas: fresh pressure in the chosen unit first, then the same visit/rating ordering. No conversion between incompatible gas pressure units is silently applied.
- Road geometry, distance, duration and maneuvers from an OSRM-compatible driving service. Foreground GPS following, user-pan pause, recenter, accuracy-aware rerouting, stop and external-navigation handoff.
- Account-specific idempotent favorites; guest favorites merge at sign-in. Ratings require a server-recorded station visit; newly submitted 4/5 stars add a favorite, and manual deletion is respected until a later qualifying submission.
- Real registration/password login, secure cookies, logout, one-time recovery, names/avatar/password settings, support history and admin support management.
- Database-grounded assistant in Uzbek, Russian or English; optional OpenAI-compatible language model. The response explicitly reports `database` or `llm` mode; station cards always come from the database.
- Admin draft/publish/edit/unpublish/soft-delete, per-category product editor, map picker, safe user list and audit log. Immediate local refresh plus visible-tab public polling every 25 seconds; no persistent process or WebSocket dependency.

## Configuration

Copy/modify `.env.example`, or use `init-local`. Production settings belong in the host dashboard. **Never commit `.env`, database files or real secrets.** `python manage.py generate-secret` produces a suitable secret.

| Setting | Required / default | Source and purpose |
| --- | --- | --- |
| `APP_ENV` | `development`; set `production` on hosts | Enforces PostgreSQL, HTTPS origin and secure cookies |
| `DATABASE_URL` | Required | Local SQLite URL in development; external PostgreSQL URL in production |
| `SESSION_SECRET` | Required, at least 32 characters | Unique generated secret for hashing opaque session/recovery material |
| `APP_ORIGIN` | Production: required HTTPS origin | Exact scheme + domain, no path or trailing slash; CSRF origin check |
| `SESSION_DAYS` | `7` | Session cookie/database expiry |
| `TILE_URL` | OSM HTTPS raster URL | Browser-safe tile template `{z}/{x}/{y}` from your provider |
| `TILE_ATTRIBUTION` | `© OpenStreetMap contributors` | Required visible provider credit; standard OSM credit is linked |
| `TILE_FALLBACK_URL` | Empty | Optional compatible authorized HTTPS fallback; Retry switches providers |
| `TILE_FALLBACK_ATTRIBUTION` | Empty | Required credit when a fallback is configured |
| `GEOCODING_URL` | Empty | Actual Nominatim-compatible service base; add `/reverse` automatically |
| `GEOCODING_MIN_INTERVAL` | `1` second, minimum 1 | Global DB-backed time lease between upstream geocoding requests |
| `PROVIDER_USER_AGENT` | `GEF_system/1.0` | Set an identifiable application/contact agent for upstream services |
| `ROUTING_URL` | Empty | Actual OSRM-compatible service base with the driving profile |
| `ROUTING_API_KEY` | Empty | Optional server-side Bearer token for your compatible routing gateway |
| `ROUTING_MIN_INTERVAL` | `1` second, minimum 1 | Global minimum interval between uncached upstream route requests |
| `PRESSURE_FRESH_HOURS` | `6` | Freshness threshold for gas ranking/readout labels |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Optional OpenAI-compatible chat-completions base |
| `AI_API_KEY` | Empty | Optional server-only model provider key |
| `AI_MODEL` | `gpt-4.1-mini` | A model supported by your configured provider |
| `TELEGRAM_BOT_TOKEN` | Empty | Optional BotFather token for raw `initData` verification |
| `SUPPORT_CHAT_URL` | `https://t.me/WebShadoWin` | Browser-safe support contact, independent of the Mini App bot |
| `ADMIN_USERNAME` | Empty; optional CLI input | Used only by explicit `create-admin` command |
| `ADMIN_PASSWORD` | Empty; optional CLI input | Prefer the CLI hidden prompt; remove any provisioning variable afterward |
| `PORT` | Host-provided; Docker fallback `8000` | Railway HTTP binding, always `0.0.0.0` |

Frontend API requests always use the shared-origin `/api` path. No build-time API host setting, localhost URL or private key is embedded in the interface. `/api/config` exposes only intentionally public settings; server secrets are omitted.

## Deploy from GitHub

Full steps: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

**Vercel:** import this root directory as a FastAPI project. Native detection finds `app.py:app`; this project intentionally needs **no legacy `builds`/catch-all `vercel.json`**. Set a public/pooled PostgreSQL URL, `APP_ENV=production`, a generated `SESSION_SECRET`, and the exact production `APP_ORIGIN`. Run `alembic upgrade head` explicitly against that database before production traffic, then run `create-admin` once. Do not use a Railway `*.railway.internal` address from Vercel. Do not use SQLite or upload folders in the function bundle.

**Railway:** import the repository, attach PostgreSQL, set environment variables, and let Railway use the Dockerfile. `railway.toml` runs `alembic upgrade head` as a controlled pre-deploy command and checks `/health/ready`. Generate a public domain, set `APP_ORIGIN` to its HTTPS origin, redeploy with that setting, and provision the admin once. The server binds the supplied `PORT`.

The files are deployment-ready source, **not evidence that either account has been deployed**. Configure the production database/provider URLs and verify on the resulting HTTPS domain.

## Maps, routing and addresses

Leaflet code/CSS/icons are bundled, so map-library startup does not depend on a CDN. Map tiles are still external. OSM's community tile server is best effort, has no SLA, and is not unlimited production infrastructure. Keep attribution visible; honor normal browser caching/Referer; no bulk prefetch/offline downloading. For production traffic, choose an appropriate OSM-derived tile service, restrict any public token to your domain, and configure a permitted fallback. Review the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).

For roads, set `ROUTING_URL` to a real hosted or self-hosted **OSRM-compatible** API. The adapter requests `/route/v1/driving/{lon},{lat};{lon},{lat}?geometries=geojson&steps=true&overview=full`. A provider requiring a different protocol needs an explicit adapter; an arbitrary directions URL is not interchangeable. A small, manual development review can use `https://router.project-osrm.org`, subject to the [official demo-server policy](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server), no SLA, maximum request limits and route limits. Do not rely on that public demo for production navigation. Requests are globally spaced, cached for two minutes and bounded by timeouts.

For street addresses, configure your own or a contracted **Nominatim-compatible** reverse-geocoder. The app adds `/reverse`, caches results for seven days, and uses a global request lease plus a 30-second client throttle. No public geocoder is enabled automatically. If an operator deliberately selects public Nominatim, they must review its [usage policy](https://operations.osmfoundation.org/policies/nominatim/), identify the application, obey the absolute global 1 request/second ceiling, avoid continuous/bulk tracking usage, and be responsible for compliance. Prefer a suitable production provider for live navigation. Coordinates remain usable when address lookup fails.

Tile/map providers do **not** supply current fuel prices or dispensing pressure. Those values come from explicit administrator entries; unknown values remain unavailable.

## Security and privacy

Passwords use Argon2id; raw passwords are never stored/returned. Session cookies are random, HttpOnly, SameSite=Lax, and Secure on HTTPS/production. Only keyed session hashes are stored; writes require a custom request header, same-origin checks and an authenticated per-session CSRF token. CORS is not enabled. Deploy one origin. Test cookies on the actual Telegram WebViews; third-party iframe browser policies can differ.

Recovery uses a 256-bit secret shown once, stored only as a keyed hash, row-locked for one-time use; reset revokes all sessions and issues a replacement code. Change-password also revokes other sessions and rotates the recovery code. Login, registration, recovery, password change, AI, route, support and rating operations have durable database-backed rate limits. Proxy client-IP handling must be trusted correctly; the app never blindly reads a user-supplied forwarded-IP header. Accounts also have their own login limit. Add platform-level abuse protection for public traffic.

Avatars are validated/decoded, bounded to 2 MB and 16 million pixels, re-encoded as a 256×256 WebP with no original metadata, and stored in PostgreSQL. Admin APIs enforce role checks on the server. Soft deletion preserves historical references. User/admin listings never expose hashes, recovery secrets or session tokens.

Only route/account/destination IDs and timestamps are retained for visit confirmation; complete GPS tracks and raw routing origins are not stored in route sessions. Provider caches hold short-lived rounded origin/destination route geometry and reverse-geocoder responses; run `cleanup` periodically to remove expired records. Browser-reported location can be falsified: an active live route, fresh accuracy-bounded proximity, user confirmation and cooldown are **best-effort**, not fraud-proof physical attendance verification. Manual origins cannot confirm visits. Navigation sessions must be active for at least 45 seconds; repeated station visits within 12 hours do not inflate counts.

## Verification

```bash
pip install -r requirements-dev.txt
pytest -q
node --test tests/geometry.test.mjs
```

Python tests cover database-backed application behavior with a migrated **SQLite test database**, authentication/CSRF/authorization, publication and idempotence, ranking/units/hours, recovery/session revocation, favorites/ratings/visits, support/avatars, import-time read-only behavior, missing database, provider failures, Telegram HMAC verification, and locale/asset integrity. Node tests cover actual route-distance projection/progress. PostgreSQL migration SQL can be generated offline with `alembic upgrade head --sql` using a PostgreSQL URL; this is not a live PostgreSQL integration test.

See [manual device/location checklist](docs/MANUAL_CHECKLIST.md), [API contract](docs/API.md), and [implementation report](docs/IMPLEMENTATION_REPORT.md). Live GPS, permission dialogs, Telegram capabilities, map-tile delivery, visual device widths, production database connectivity and hosted deployments require real-device/hosting verification. None are simulated as successful tests.

Maintenance: run `python manage.py cleanup` through a host scheduled command or an operator session. It removes expired sessions/cache and old unconfirmed route records without requiring a permanent worker.

## Troubleshooting

| Symptom | Check / recovery |
| --- | --- |
| Import-time 500 / read-only filesystem | Deploy this root with `app.py`; no old code calling `mkdir`, SQLite or upload writes on import. Inspect platform import logs without exposing secrets. |
| Database setup error or readiness failure | Set the correct reachable PostgreSQL URL, SSL/pooling options, `SESSION_SECRET` and `APP_ORIGIN`; explicitly run migrations. Liveness can pass while readiness fails. |
| Blank map | Confirm Leaflet CSS/JS/assets resolve, map has nonzero height, HTTPS tiles/attribution are valid, and network/provider limits allow tiles. Retry; the list remains usable. |
| Map blank after changing pages | Map instances are reused; `ResizeObserver` and page transitions call `invalidateSize`. Verify no custom CSS hides/collapses the container. |
| Wrong location / no permission | Use HTTPS, enable OS/browser/Telegram location permission and device location service. The map's browsing center is not your position. Retry or choose a manual origin. |
| No route / wrong ordering | Set a compatible routing service. Leaflet takes `[lat, lon]`; OSRM takes `lon,lat`. No straight-line replacement is shown as a road route. |
| Admin 401/403 | Sign in with the explicitly provisioned admin; browser state cannot promote users. Verify session/CSRF and exact same-origin deployment. |
| Saved station absent | Confirm publication, selected category/grade/open filters and coordinates. Wait at most 25 seconds in another visible tab or refresh. Drafts are private. |
| Telegram sign-in cookie problem | Use the production HTTPS origin, check cookie restrictions in the actual Telegram client; avoid protected preview links. Verify `APP_ORIGIN` exactly matches. |
| Language appears unchanged | Check locale JSON loads without cached old assets; all dictionaries share the same keys. Station descriptions show an explicit available-language fallback. |
| AI provider unavailable | The database fallback still answers supported station questions. Check actual provider key/model; it does not infer missing stock/pressure. |
| Port shows an old project | Stop the old server or use a different port and matching `APP_ORIGIN`. Run commands from this repository root. |

Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

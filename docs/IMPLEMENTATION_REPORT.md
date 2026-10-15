# Implementation report — GEF_system

Date: 15 October 2026.

## Delivered

A real, organized shared-origin application in HTML/CSS/JavaScript and Python FastAPI, with SQLAlchemy relational records and an explicit Alembic migration. Root `app.py` supports Vercel's native FastAPI entrypoint; a Dockerfile and Railway pre-deploy/health configuration support Railway. The repository includes pinned dependencies, `.env.example`, management commands, English deployment/API documentation, an Uzbek quick-start guide, automated tests and a manual device checklist.

The public UI includes exactly Home, Favorites, AI Assistant and Profile; the administrator interface is separate and server-authorized. It includes responsive CSS for phone bottom navigation, desktop sidebar and larger layouts, light/dark themes, and three complete locale dictionaries with **341 keys each**. Leaflet 1.9.4 is bundled with its license and marker assets.

## Implementation and verification boundaries

| Area | Implemented behavior | Verification |
| --- | --- | --- |
| Accounts and sessions | Real registration/login/logout, Argon2id, session expiry, CSRF/origin checks, role enforcement | Automated migrated-database API tests passed; actual Telegram cookie behavior remains manual |
| Recovery | One-time hashed code, replacement code, session revocation, attempt limits | Automated tests passed |
| Admin publication | Transactional create/edit/draft/publish/unpublish/soft-delete, idempotency, user/support/audit views | Automated API workflows passed; visual picker interaction remains manual |
| Public data | Category/grade/unit filters, opening hours, ranking, pagination, shared marker results | Automated business/API tests passed |
| Persistence | Accounts, stations, products, avatars, favorites, ratings, visits, support and audit stored in SQL | Restart/independent-client and clean-checkout tests passed with SQLite; production PostgreSQL not connected |
| Mapping | Leaflet sizes, resize observation, page-return invalidation, separate picker, tile retry/fallback, spatial grouping | Assets/IDs/imports verified; actual map display/provider delivery and device sizes require browser QA |
| Location | Permission-based real position, freshness/accuracy handling, manual origin, bounded address lookup, Telegram fallback | Implementation and static checks completed; no physical GPS or permission-dialog test performed |
| Road navigation | OSRM-compatible geometry/maneuvers, foreground watch/follow, pan pause/recenter, rerouting, stop and Yandex handoff | Adapter geometry/coordinate tests used controlled responses; pure distance/progress tests passed; no real road trip performed |
| Visits/ratings/favorites | Exact-station route/proximity confirmation, cooldown/deduplication, one current rating and explicit favorite behavior | Automated business/API tests passed; browser proximity remains best effort |
| AI | Same station/ranking database, multilingual deterministic fallback, optional OpenAI-compatible provider | Real database fallback tested; external paid model not called |
| Telegram | Progressive SDK, safe areas/viewport/theme, capability-checked LocationManager and server raw-data verification | HMAC/freshness/privilege tests passed; actual client/device SDK flows remain manual |
| Deployment | Read-only/network-free import, lazy NullPool DB access, explicit migrations, liveness/readiness | Automated import, missing/unreachable database tests passed; PostgreSQL SQL generated offline; no Vercel/Railway deployment performed |

## Checks actually run

- **28 Python tests passed** using the delivered pinned runtime and a fresh migrated SQLite database per test. Coverage includes clean-checkout CLI initialization, admin provisioning, DEMO seed and independent process restarts; access control, CSRF, real login, one-time recovery, publication/idempotence, missing/deleted references, ratings/favorites, support/avatars, opening schedules, pressure freshness, compatible price comparisons, route geometry/arrival rules, provider failures, durable limits, Telegram signatures and locale/asset completeness.
- **3 Node tests passed** for the actual side-effect-free route geometry functions: geodesic distance, segment projection/progress and perpendicular off-route distance.
- All application JavaScript modules passed `node --check`; Python source passed compilation/parsing. HTML static IDs were checked for duplicates and linked assets/module imports were checked for existence.
- Alembic generated valid PostgreSQL upgrade SQL in offline mode. That verifies dialect generation, not connectivity or a live PostgreSQL transaction/pool deployment.
- One nonfailing upstream test-harness deprecation warning was emitted: the installed Starlette version deprecates its current httpx TestClient transport in favor of httpx2. Application tests still pass with the pinned dependencies.

No browser preview/server was started in this environment because supported browser QA infrastructure was unavailable. No screenshots or visual/device pass results are claimed. The supplied manual checklist deliberately leaves those checks unverified.

## Precise external setup still required

1. Choose Vercel or Railway, import the root repository, and configure the production HTTPS origin.
2. Provision reachable PostgreSQL; use the appropriate pooled URL for serverless and a suitable migration connection. Set `APP_ENV=production`, `DATABASE_URL`, a fresh `SESSION_SECRET` and `APP_ORIGIN`.
3. Run the explicit migration, provision an initial administrator once, and enter actual station data. No real prices/pressure/station feed or universal admin credential is bundled.
4. Configure a production-suitable HTTPS tile provider/fallback with required attribution. Community tiles remain best effort and subject to policy.
5. Select a real OSRM-compatible driving service in `ROUTING_URL`. Configure an authorized Nominatim-compatible reverse geocoder if street addresses are wanted. Without these, the UI honestly offers coordinates and external navigation, not a fake road route.
6. Optionally configure a compatible AI provider/model key. The database assistant works without it.
7. For a Telegram Mini App, configure your own bot's Web App/menu button with the public production URL; optionally set its server token for launch-data verification. The existing support contact is separate.
8. Run the delivered manual checklist on actual devices, including GPS, permission failures, WebView cookies, all requested widths, map resizing and foreground route tracking.

## Practical limits

- Web navigation requires real foreground location updates and is not guaranteed while backgrounded or screen-locked. Heading is only used when device data supports it; movement is never simulated.
- Browser location can be spoofed; visit confirmation is an accuracy-aware application heuristic, not fraud-proof attendance verification. It retains account/route/station events, not full GPS histories. Short-lived provider geometry/address caches are removed by the explicit cleanup command.
- Driving time excludes live traffic. No offline maps, proprietary Yandex traffic or background-navigation guarantees are claimed.
- Supported database AI questions are interpreted deterministically; the optional model is supplied only retrieved facts. Real service keys/accounts were unavailable for a live model call.
- Public matching markers are capped at 1,000, with an on-screen notice for larger result sets. Catalog ranking currently executes on database-filtered records in Python; very large catalogs should use indexed SQL/spatial ranking.
- Avatars use bounded database storage. No local runtime upload folders or SQLite production storage are used.
- The optional DEMO command creates clearly fictional records only in development. Its prices and coordinates are review fixtures, not verified operational information.

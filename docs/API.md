# API contract

Interactive OpenAPI documentation: `/docs`; machine-readable schema: `/openapi.json`.

All APIs share the application origin under `/api`. Requests return JSON, except the avatar image. Errors use:

```json
{"error":{"code":"VALIDATION_ERROR","fields":{"latitude":"less_than_equal"}}}
```

Error codes are stable and translated by the interface. Validation responses omit raw input/passwords and stack traces. Status codes distinguish validation (422), unauthenticated (401), forbidden (403), missing (404), conflict (409), rate limit (429), external failure (502), and unavailable setup/database/provider (503).

Every non-GET API call requires `X-GEF-Request: 1`; browser Origin must match `APP_ORIGIN`. Account-owned mutations also require `X-CSRF-Token` from sign-in or `GET /api/me`. Cookies are same-origin HttpOnly sessions. CORS is disabled. `/routes` permits guests, but requires CSRF when creating authenticated route state. No endpoint accepts a client-assigned role or a different user's account ID for account operations.

| Method / path | Behavior / important inputs |
| --- | --- |
| `GET /api/config` | Public configuration and setup/provider availability flags; no secrets |
| `POST /api/auth/register` | First/last name, unique username, password/confirmation, confirmed checkbox; creates session and one-time recovery code |
| `POST /api/auth/login` | Real database authentication; returns safe user and CSRF token |
| `POST /api/auth/logout` | Revokes current session and expires cookie |
| `POST /api/auth/recover` | Username, one-time recovery code and new password; revokes all sessions and returns replacement code |
| `GET /api/me` | Safe current user or null; session CSRF token |
| `PATCH /api/me` | First and last names for the current account |
| `PATCH /api/me/preferences` | `language`: uz/ru/en, `theme`: light/dark |
| `POST /api/me/password` | Current password and new password; revokes other sessions and rotates recovery |
| `POST /api/me/avatar` | Multipart `file`; validated JPEG/PNG/WebP up to 2 MB, re-encoded into PostgreSQL |
| `GET /api/me/avatar` | Current account's private WebP image |
| `GET /api/stations` | Category, grade, sort, open-now, comparison unit, pressure unit, paired origin coordinates, query, pagination |
| `GET /api/stations/{id}` | One published non-deleted station with server aggregates/products |
| `GET /api/favorites` | Own favorites; unpublished/deleted references are labeled unavailable |
| `PUT /api/favorites/{id}` | Idempotent own favorite insertion for a public station |
| `DELETE /api/favorites/{id}` | Removes only the current account's association |
| `POST /api/stations/{id}/rating` | 1–5 stars; requires a confirmed visit to this station; one updatable rating per account/station |
| `POST /api/routes` | Origin `latitude`, `longitude`, `origin_kind`, destination `station_id`; optional existing `route_id` on reroute |
| `POST /api/navigation/{id}/start` | Activates an account-owned real route session |
| `POST /api/navigation/{id}/stop` | Stops/finishes an account-owned route session |
| `POST /api/visits` | Route ID, live position/accuracy/timestamp and explicit arrival confirmation; no manual-origin visits |
| `GET /api/geocode` | Latitude/longitude and language; bounded cached reverse lookup |
| `POST /api/assistant` | Message, language, optional origin; database station cards and explicit response mode |
| `GET /api/support` | Own support requests/statuses |
| `POST /api/support` | Persists own support message before returning confirmation |
| `POST /api/telegram/verify` | Optional raw launch-data HMAC/freshness verification; never grants app/admin login |
| `GET /api/admin/stations` | Administrator-only paginated drafts/publications with search/category/status |
| `POST /api/admin/stations` | Transactional create/publish with idempotency `request_key` |
| `PUT /api/admin/stations/{id}` | Validated edit/publish/unpublish; full station/products payload |
| `DELETE /api/admin/stations/{id}` | Audited soft deletion; historical references survive |
| `GET /api/admin/users` | Safe recorded account/login/activity list, paginated |
| `GET /api/admin/support` | All support submissions, paginated |
| `PATCH /api/admin/support/{id}` | Status: new/in_progress/resolved, audited |
| `GET /api/admin/audit` | Safe paginated event history |
| `GET /health/live` | Import/process liveness, does not require a database |
| `GET /health/ready` | Database query and expected Alembic revision; unavailable database yields 503 |

Station list returns `items`, `total`, `page`, `per_page`, `comparison_unit`, `pressure_unit`, plus `map_items` (first 1,000 matching positions) and `map_limit`. Cards paginate nine per page. Marker positions are filtered/ranked by the same service. The interface tells users when the map limit is reached. Narrow the query for larger datasets. Spatial marker grouping is applied for dense maps at low zoom. Listing currently ranks matching records in Python after database filtering; use indexed SQL/PostGIS ranking if the catalog grows substantially beyond a regional station catalog.

Prices use decimal database columns and nullable values. Category/unit validation: Fuel→liter; Metan→m³; Propan→liter; Elektr→kWh/minute/session. Pressure requires a gas category, unit and timezone-aware nonfuture measurement timestamp. EV fields are rejected on nongrid categories. Opening hours use weekday keys `0`=Monday through `6`=Sunday, each holding zero or more `[HH:MM, HH:MM]` intervals. An end before start is overnight. Blank days are closed. Explicit closed/open overrides take precedence over normal/24h hours.

Routing never substitutes a line between endpoints. Origin coordinates are sent transiently to the configured routing service; route-session records retain no raw origin. The short-lived provider cache stores returned geometry; expired entries should be cleaned. Successful arrival requires an active account-owned live route lasting at least 45 seconds and at most 6 hours, a position timestamp within 60 seconds, accuracy at most 100 m, proximity within an accuracy-aware 40–100 m threshold, explicit confirmation and a 12-hour per-station cooldown. Browser data can be forged; this is not cryptographic physical-attendance proof.

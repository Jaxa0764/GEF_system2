# Manual acceptance checklist

These checks require an actual browser/device and deployed HTTPS environment. They have **not** been marked passed by automated API tests. Record the client/device, date, URL and result for each tested item.

## Deployment and persistence

- [ ] Clean checkout runs the README commands without an existing `.env`, database or frontend build.
- [ ] Production Vercel imports `app.py` with a read-only application filesystem and responds at the public HTTPS URL.
- [ ] Production Railway uses the supplied `PORT`; pre-deploy migration and readiness succeed.
- [ ] `/health/live` is alive during a database outage, while `/health/ready` fails with 503.
- [ ] Station/account/avatar/favorite/rating/support records survive process restart and redeploy using PostgreSQL.
- [ ] `/admin`, assets, page refresh, missing JavaScript and unknown API routes return appropriate responses.

## Layout and access

- [ ] Inspect widths **320, 375, 768, 1024, 1440, 1920 and 3840 px** in portrait/landscape as applicable.
- [ ] Phone navigation stays below the content; desktop navigation is on the left.
- [ ] Content order on Home is address → map → categories → filters → readable cards.
- [ ] No horizontal overflow, clipped forms, covered buttons or zero-height maps.
- [ ] Nine-card desktop pagination adapts to two/one columns, rather than shrinking text.
- [ ] TV/keyboard/remote focus is visible; all actions can be reached without a mouse.
- [ ] Dialog focus/close works; reduced-motion preference does not break loading or interactions.
- [ ] Light/dark theme covers cards, forms, profile, chat, admin and Leaflet popups; tile labels remain readable.
- [ ] Switch UZB/RU/ENG on each page and in the admin editor. Existing route, form values and selected filters remain intact.

## Administrator end to end

- [ ] A guest and a normal user receive 401/403 for direct admin APIs and `/admin`.
- [ ] Provision an admin through the CLI, sign in, add a station, and choose a position with map click.
- [ ] Drag the picker marker; edit latitude/longitude; verify both remain synchronized.
- [ ] Save location returns to the editor without publishing; invalid/incomplete inputs disable Publish.
- [ ] Draft stays out of public results and AI; publish appears on the right category/map without redeployment.
- [ ] A second visible client receives the update within 25 seconds; hidden tabs stop polling and refresh on return.
- [ ] Retried/double-submitted publish produces one station.
- [ ] Product prices, pressure units/time, EV connectors/power, schedules and availability update correctly.
- [ ] Unpublish/delete removes public results; favorite/history references remain safe. Delete requires confirmation.
- [ ] Safe user list shows actual login/activity timestamps, not invented online presence.
- [ ] Support submissions reach admin; status changes appear in the sender's history and audit log.

## Maps and real location

- [ ] Map renders on first load, returning from another section, device rotation and resizing.
- [ ] The public map and admin picker keep separate Leaflet instances.
- [ ] Normal and fallback tile attribution are visible; a blocked tile provider shows retry while lists remain usable.
- [ ] Initial browsing center is never shown as the user's position.
- [ ] Granted permission resumes a real location; ungranted permission uses the visible user action.
- [ ] Denied permission, disabled location service, timeout, no location capability, stale and poor readings each have a recovery path.
- [ ] The marker uses returned coordinates and an accuracy circle; compare with the device's map app.
- [ ] Manual origin is explicitly labeled and can be used when a TV/desktop has no GPS.
- [ ] Reverse-geocoder failure preserves usable coordinates and stations.

## Routing and arrival

- [ ] Configure an actual authorized OSRM-compatible routing service and a production-suitable tile provider.
- [ ] Selecting Home, map popup, Favorites Start or AI result opens Home and prepares the same route implementation.
- [ ] Displayed route follows returned roads; distance/time come from the provider, never a straight line labeled as driving distance.
- [ ] Start obtains a fresh live origin if the preview origin was manual/stale.
- [ ] In the foreground, real movement updates the user marker; no simulated movement or heading is used.
- [ ] User pan pauses follow; Recenter resumes it; Stop clears watchPosition and obsolete route state.
- [ ] Meaningful off-route movement with sufficient accuracy triggers a rate-limited reroute; small GPS jitter does not.
- [ ] Hidden/foreground transitions stop/resume tracking appropriately; unsupported clients offer external navigation.
- [ ] Provider failures show retry plus a valid Yandex Maps handoff, and do not claim active navigation.
- [ ] After a live route of at least 45 seconds, actual proximity and confirmation create one visit for the exact station.
- [ ] Manual routes, low-quality/stale/remote positions and duplicate arrivals cannot count as confirmed visits.
- [ ] Rating happens after stopping/arrival. Four/five stars add a favorite; manual removal stays removed on reload; a later qualifying rating can add it again.

## Accounts and Telegram

- [ ] Incorrect/nonexistent credentials fail. Registration requires all requested fields, matching passwords and the checkbox.
- [ ] Recovery code is shown once; one use resets the password, revokes all old sessions and issues a new code.
- [ ] Avatar upload accepts bounded real images and displays the processed result after reload/redeploy.
- [ ] Guest favorites are labeled as local and merge safely on sign-in; accounts cannot see each other's data.
- [ ] BotFather button launches the **public production** HTTPS app; it does not open a protected preview.
- [ ] Telegram iOS/Android/Desktop/web clients load and maintain password sign-in sessions.
- [ ] Safe areas, viewport changes, theme preference and BackButton behave correctly.
- [ ] Supported LocationManager requests use real data; clients without continuous location offer external navigation.
- [ ] Raw initData verification checks freshness and signature; no client Telegram identity grants admin rights.

## Failures and external setup

- [ ] Slow/offline API requests resolve into bounded loading/error/retry states, with no false save confirmation.
- [ ] Without an AI key, supported questions use real station records and are labeled database mode.
- [ ] With an AI key, the configured provider/model is tested; provider timeout falls back to database mode.
- [ ] All production station data is administrator-supplied; fictional DEMO entries are absent or unmistakably labeled during review.

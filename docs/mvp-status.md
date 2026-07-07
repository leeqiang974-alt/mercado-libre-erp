# MVP Skeleton Status

Verified on: 2026-07-07

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Local AI review policy with Claude/NVIDIA provider stubs.
- Mercado Libre OAuth authorization URL, callback, and token exchange skeleton.
- Mercado Libre non-FULL payload builder.
- Publishing validation gates for human approval, listing type availability, and FULL exclusion.
- Guarded Mercado Libre publish execution adapter that posts to `/items` only when live publishing is explicitly enabled.
- API flow for URL/HTML import, review, publish preview, and guarded publish execution.
- React MVP shell for import, draft review, publishing readiness, and store authorization link startup.
- Docker Compose services for PostgreSQL and Redis.

Not connected yet:

- Persisted Amazon collection jobs.
- Persisted Mercado Libre OAuth token references.
- Production credential vault or encryption for Mercado Libre tokens.
- Live Claude API.
- Live NVIDIA NIM API.
- Persistent PostgreSQL migrations.

Next production phase:

- Add persisted drafts and publish jobs.
- Add Mercado Libre metadata refresh for categories, attributes, listing types, and shipping options.
- Replace AI stubs with real provider clients behind the same interfaces.
- Replace direct publish-route access token input with authorized store token references.

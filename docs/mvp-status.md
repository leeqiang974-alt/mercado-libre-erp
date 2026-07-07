# MVP Skeleton Status

Verified on: 2026-07-07

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Local AI review policy with Claude/NVIDIA provider stubs.
- Mercado Libre OAuth authorization URL, callback, and token exchange skeleton.
- Persisted connected stores with token references instead of exposing raw tokens.
- Persisted product drafts for HTML snapshot imports.
- Mercado Libre non-FULL payload builder.
- Publishing validation gates for human approval, listing type availability, and FULL exclusion.
- Guarded Mercado Libre publish execution adapter that posts to `/items` only when live publishing is explicitly enabled.
- Guarded publish execution API now uses `store_id` rather than accepting access tokens from the frontend.
- API flow for URL/HTML import, persisted drafts, persisted stores, review, publish preview, and guarded publish execution.
- React MVP shell for import, saved draft list, publishing readiness, connected store list, and store authorization link startup.
- Docker Compose services for PostgreSQL and Redis.

Not connected yet:

- Persisted Amazon collection jobs.
- Production credential vault or encryption for Mercado Libre tokens.
- Live Claude API.
- Live NVIDIA NIM API.
- Persistent PostgreSQL migrations.

Next production phase:

- Add persisted drafts and publish jobs.
- Persist URL collection persistence, not only HTML snapshot persistence.
- Add Mercado Libre metadata refresh for categories, attributes, listing types, and shipping options.
- Replace AI stubs with real provider clients behind the same interfaces.
- Replace token-reference placeholder with encrypted token storage and refresh-token rotation.

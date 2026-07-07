# MVP Skeleton Status

Verified on: 2026-07-07

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Persisted Amazon URL collection results as source products, including manual-action and failed collection states.
- Local AI review policy.
- Claude Messages API review adapter with safe fallback when no API key or parse failure occurs.
- NVIDIA NIM/OpenAI-compatible chat review adapter with safe fallback when no API key or parse failure occurs.
- Mercado Libre OAuth authorization URL, callback, and token exchange skeleton.
- Persisted connected stores with token references instead of exposing raw tokens.
- Encrypted Mercado Libre access/refresh token credential storage for connected stores.
- Persisted product drafts for HTML snapshot imports.
- Persisted product drafts for successful URL collections.
- Mercado Libre metadata proxy for listing types, category prediction, and category attributes.
- Mercado Libre non-FULL payload builder.
- Publishing validation gates for human approval, listing type availability, and FULL exclusion.
- Guarded Mercado Libre publish execution adapter that posts to `/items` only when live publishing is explicitly enabled.
- Guarded publish execution API now uses `store_id` rather than accepting access tokens from the frontend.
- Guarded publish execution resolves encrypted store access tokens server-side.
- Persisted publish jobs for blocked, failed, and published execution attempts.
- Publish job list API for reviewing status, errors, item IDs, and permalinks.
- Persisted local, Claude, and NVIDIA review results for saved drafts.
- Review history API and frontend refresh control for saved draft audit trails.
- API flow for URL/HTML import, persisted source products, persisted drafts, persisted stores, review, metadata, publish preview, and guarded publish execution.
- React MVP shell for import, saved draft list, Claude/NVIDIA review buttons, publishing metadata lookup, publish job list, publishing readiness, connected store list, and store authorization link startup.
- Docker Compose services for PostgreSQL and Redis.

Not connected yet:

- Background Amazon collection jobs and queueing.
- Production credential vault or encryption for Mercado Libre tokens.
- Persistent PostgreSQL migrations.

Next production phase:

- Add Mercado Libre metadata refresh for categories, attributes, listing types, and shipping options.
- Add publish job retry controls and worker-backed asynchronous execution.
- Add provider prompt versioning and review-model version analytics.
- Add refresh-token rotation before token expiry.

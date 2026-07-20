# MVP Skeleton Status

Verified on: 2026-07-20

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Amazon URL collection job model, single/batch create, list/run APIs, and frontend queue controls with per-row validation and duplicate reporting.
- Batch intake canonicalizes Amazon domain/ASIN identities, limits each request to 100 URLs, and serializes deduplication on both PostgreSQL and SQLite so concurrent operator requests reuse the same job by default.
- Backend collection worker CLI for processing pending Amazon URL collection jobs in batches.
- Persisted Amazon URL collection results as source products, including manual-action and failed collection states.
- Local AI review policy.
- Claude Messages API review adapter that reports missing credentials or provider failures without local fallback.
- NVIDIA NIM/OpenAI-compatible chat review adapter that reports missing credentials or provider failures without local fallback.
- Mercado Libre OAuth authorization URL, callback, and token exchange skeleton.
- Persisted connected stores with token references instead of exposing raw tokens.
- Encrypted Mercado Libre access/refresh token credential storage for connected stores.
- Refresh-token rotation for Mercado Libre credentials before publish execution.
- Persisted product drafts for HTML snapshot imports.
- Persisted product drafts for successful URL collections.
- Mercado Libre metadata proxy for listing types, category prediction, and category attributes.
- Mercado Libre metadata cache and refresh APIs for listing types and category attributes.
- Persisted Mercado Libre draft listing configuration for category, listing type, fulfillment, and attributes.
- Persisted operator approval records for draft publish gates.
- Mercado Libre non-FULL payload builder.
- Publish preview from saved draft listing configuration.
- Publishing validation gates for human approval, listing type availability, and FULL exclusion.
- Guarded Mercado Libre publish execution adapter that posts to `/items` only when live publishing is explicitly enabled.
- Guarded publish execution API now uses `store_id` rather than accepting access tokens from the frontend.
- Guarded publish execution resolves encrypted store access tokens server-side.
- OAuth callback resolves and persists the seller's real Mercado Libre `site_id`; enqueue, direct execution, and workers enforce store/site matching.
- Guarded publish execution from saved draft listing configuration.
- Queued publish execution from saved draft listing configuration.
- Backend publish worker CLI for processing pending publish jobs in batches.
- Persisted publish jobs for blocked, failed, and published execution attempts.
- Publish job list API for reviewing status, errors, item IDs, and permalinks.
- Publish job retry API and frontend retry control for blocked or failed jobs, preserving original job history and audit trail.
- Audit event log for AI review and publish execution actions, with frontend audit page.
- Alembic baseline migration for the current backend schema.
- Persisted local, Claude, and NVIDIA review results for saved drafts.
- Combined Claude + NVIDIA behavioral audit endpoint with strictest-result aggregation and orchestration audit events.
- Review history API and frontend refresh control for saved draft audit trails.
- API flow for URL/HTML import, persisted source products, persisted drafts, persisted stores, review, metadata, publish preview, and guarded publish execution.
- React MVP shell for import, saved draft list, Claude/NVIDIA review buttons, publishing metadata lookup, publish job list, publishing readiness, connected store list, and store authorization link startup.
- Docker Compose services for PostgreSQL, Redis, backend API, collection worker, and publish worker.
- Compose migration gate (`alembic upgrade head`) plus database/Redis/API health checks and restart policies.

Not connected yet:

- The local runtime has no Mercado Libre, Claude, or NVIDIA production credentials, so no real Mercado Libre item has been published yet.
- Production-grade external KMS or secrets manager for Mercado Libre token encryption keys.

Verification for this change:

- Backend suite: 148 passed, with 2 PostgreSQL-only tests skipped in the default run.
- Docker PostgreSQL integration run: 2 passed, including concurrent request deduplication.
- Frontend production build passed.
- Desktop and mobile browser smoke passed for all 18 sites, Classic/Premium controls, batch result rows, overflow, console errors, and failed responses.

Next production phase:

- Add Mercado Libre shipping options metadata refresh.
- Add provider prompt versioning and review-model version analytics.
- Persist and index normalized Amazon product identities, then paginate collection history to keep lookup and polling costs bounded as the queue grows.

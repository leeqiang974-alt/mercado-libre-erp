# MVP Skeleton Status

Verified on: 2026-07-20

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Amazon URL collection job model, single/batch create, list/run APIs, and frontend queue controls with per-row validation and duplicate reporting.
- Batch intake persists and indexes canonical Amazon domain/ASIN identities, limits each request to 100 URLs, and serializes deduplication on both PostgreSQL and SQLite so concurrent operator requests reuse the same job by default.
- Collection queue polling is bounded to the latest 100 jobs by default and supports limit/offset pagination; URL collection and manual HTML snapshot inputs keep independent state.
- Backend collection worker CLI for processing pending Amazon URL collection jobs in batches.
- Persisted Amazon URL collection results as source products, including manual-action and failed collection states.
- Structured Amazon source snapshots persist the full collected title, price, brand, bullets, description, image gallery, technical details, and discovered ASIN variants instead of reducing the source record to a URL/status shell.
- Collection history exposes a lightweight source summary and a lazy-loaded review panel for the full image gallery and variant evidence on desktop and mobile.
- Operators can create an idempotent, site-specific draft from any discovered Amazon variant; the draft retains its source ASIN/attributes and prefers variant-specific images.
- Saved drafts expose their Amazon ASIN and variant attributes so operators can distinguish otherwise identical titles.
- Verified Mercado Libre category metadata produces conservative Amazon-to-Mercado Libre attribute suggestions; exact enumerated matches preserve `value_id`, ambiguous list values require manual entry, and mapped optional attributes remain editable.
- Listing configuration and publish validation enforce both `required` and `catalog_required` attributes, reject unknown category IDs and invalid enumerated value IDs when verified definitions are present, and translate common attribute failures into operator-facing messages.
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
- Authorized-store shipping preferences API with explicit non-FULL filtering and operator-selectable shipping mode/logistic type.
- Versioned listing configuration binds site, authorized store, Classic/Premium choice, and non-FULL shipping; changing delivery invalidates prior AI review and approval.
- Saved-draft preview and enqueue re-fetch the authorized store's current shipping preferences and fail closed when the selected non-FULL option was removed or the provider cannot be verified; execution performs the same check again before `/items`.
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
- Review results persist provider model, versioned safety prompt identifier, execution duration, provider status, and creation time; provider failures are audited without being presented as successful reviews.
- Review history API and frontend refresh control for saved draft audit trails.
- Desktop and mobile review history expose Claude, NVIDIA, and aggregate model/prompt/duration metadata without exposing API keys or raw prompts.
- API flow for URL/HTML import, persisted source products, persisted drafts, persisted stores, review, metadata, publish preview, and guarded publish execution.
- React MVP shell for import, saved draft list, Claude/NVIDIA review buttons, publishing metadata lookup, publish job list, publishing readiness, connected store list, and store authorization link startup.
- Docker Compose services for PostgreSQL, Redis, backend API, collection worker, and publish worker.
- Compose migration gate (`alembic upgrade head`) plus database/Redis/API health checks and restart policies.

Not connected yet:

- The local runtime has no Mercado Libre, Claude, or NVIDIA production credentials, so no real Mercado Libre item has been published yet.
- Production-grade external KMS or secrets manager for Mercado Libre token encryption keys.

Verification for this change:

- Backend suite: 187 passed, with 5 PostgreSQL-only tests skipped in the default run.
- Docker PostgreSQL integration run: 5 passed, including concurrent collection, publish-job, and source-variant draft deduplication plus atomic draft-version invalidation under simultaneous edits.
- PostgreSQL migrations through `20260720_0018` recovered legacy source ASINs from Amazon URLs, preserved duplicate unclassified legacy drafts with a partial identity index, backfilled collection identities and existing draft source ASINs, indexed site/identity lookup, added versioned store/shipping delivery fields, review execution metadata, structured source snapshots, and source-variant draft bindings.
- The complete Alembic chain upgraded to head and downgraded to base successfully on a disposable D-drive SQLite database.
- Frontend production build passed.
- Desktop and mobile browser smoke passed for all 18 sites, Classic/Premium controls, two verified non-FULL shipping options, provider review metadata rows, batch result rows, three source images, three source variants, variant draft creation, three category attribute suggestions, required-attribute save gates, saved configuration readiness, overflow, console errors, and failed responses.

Next production phase:

- Add provider usage/cost telemetry, rate-limit handling, and operator-controlled review retry policy.

# MVP Skeleton Status

Verified on: 2026-07-21

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Amazon URL collection job model, single/batch create, list/run APIs, and frontend queue controls with per-row validation and duplicate reporting.
- Batch intake persists and indexes canonical Amazon domain/ASIN identities, limits each request to 100 URLs, and serializes deduplication on both PostgreSQL and SQLite so concurrent operator requests reuse the same job by default.
- Collection queue polling is bounded to the latest 100 jobs by default and supports limit/offset pagination; URL collection and manual HTML snapshot inputs keep independent state.
- Backend collection worker CLI for processing pending Amazon URL collection jobs in batches.
- The collection worker treats a candidate removed after queue selection as a lost claim, rolls back, and continues polling instead of restarting the process.
- Persisted Amazon URL collection results as source products, including manual-action and failed collection states.
- Structured Amazon source snapshots persist the full collected title, price, brand, bullets, description, image gallery, technical details, and discovered ASIN variants instead of reducing the source record to a URL/status shell.
- Amazon `colorImages`/`colorToAsin` page data supplies high-resolution galleries before DOM thumbnails, including single-quoted JavaScript objects and maximum-area `main` image maps; displayed-ASIN validation prevents redirected pages from contaminating the requested product, and each discovered color ASIN receives only its own authoritative script gallery.
- JSON5-style Amazon script objects with unquoted keys, comments, trailing commas, and JavaScript `undefined` values retain their variant dimensions and per-ASIN image galleries instead of being discarded.
- Collection history exposes a lightweight source summary and a lazy-loaded review panel for the full image gallery and variant evidence on desktop and mobile.
- Operators can create an idempotent, site-specific draft from any discovered Amazon variant; the draft retains its source ASIN/attributes and prefers variant-specific images.
- Non-selected Amazon variants can be queued for an independent page collection from the source review. The API preserves the Amazon country domain, validates snapshot membership, reuses the canonical site/ASIN/Mercado Libre-site task, and lets the resulting source and draft retain that variant's own price, images, and measurements.
- Source review can queue up to 100 missing variants in one locked batch, reporting created/reused/selected counts. Duplicate ASIN rows collapse with selected precedence, and ID-based status polling keeps batch tasks current even when they fall outside the latest-100 queue window.
- Saved drafts expose their Amazon ASIN and variant attributes so operators can distinguish otherwise identical titles.
- Amazon specification tables and detail bullets produce structured item/package weights and product/package dimensions while retaining the original label/value; source review exposes this evidence on desktop and mobile.
- Every numbered Amazon technical-specification table is scanned. Composite dimension rows can also supply an inline item/package weight, while a dedicated weight row always takes precedence regardless of HTML row order.
- Structured measurements recognize conservative localized labels and units for Spanish, Brazilian Portuguese, German, French, Italian, Dutch, and Japanese Amazon detail tables. Latin diacritics are normalized without altering non-Latin scripts.
- Selected-page measurements can suggest explicit Mercado Libre weight and dimension attributes only for the selected Amazon ASIN, preventing a sibling variant from inheriting unverified logistics data.
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
- Amazon source amount/currency remain read-only evidence in the pricing workspace. Saved pricing is recalculated against that evidence and the selected site's currency, and is required at persisted AI review, preview, queue, retry, worker, and direct publish boundaries.
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
- Local marketplace publishing follows Mercado Libre's two-stage contract: `/items` is created without a description, then plain text is sent to `/items/{item_id}/description`. Ambiguous description responses are read back; rejected or unverified descriptions close the new item and retain its id so item creation is never retried.
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
- Review results persist provider model, versioned safety prompt identifier, execution duration, provider status, provider-reported input/output/total token usage, request ID, and creation time; provider failures are audited without being presented as successful reviews.
- Review history API and frontend refresh control for saved draft audit trails.
- Desktop and mobile review history expose Claude, NVIDIA, and aggregate model/prompt/duration/token metadata and provider request IDs without exposing API keys or raw prompts.
- Provider errors preserve HTTP status, retryability, `Retry-After`, and request ID. Rate-limited reviews return HTTP 429 and wait for an explicit operator retry; the application does not automatically resend paid review requests.
- Claude/NVIDIA review output is validated against the versioned `meli-safety-v4` contract. Missing or extra fields, unknown decisions/risk levels, and mistyped values are provider failures rather than implicit low-risk passes; system-level instructions require evidence-bounded review across restricted goods, claims, brand risk, contradictions, required listing evidence, personal data, and local-market uncertainty while treating marketplace fields as untrusted data. Saved-draft reviews require and include the reconciled pricing formula plus authorized-store, site, category, Classic/Premium, attribute, and non-FULL shipping configuration without exposing store tokens or API keys.
- Successful paid provider calls remain as `completed_stale` historical evidence when a concurrent draft edit invalidates them; they are visible in history but cannot satisfy the current-version combined publish gate.
- Monetary AI cost is deliberately not inferred from token counts until a versioned provider/model price configuration is supplied.
- API flow for URL/HTML import, persisted source products, persisted drafts, persisted stores, review, metadata, publish preview, and guarded publish execution.
- React MVP shell for import, saved draft list, Claude/NVIDIA review buttons, publishing metadata lookup, publish job list, publishing readiness, connected store list, and store authorization link startup.
- Operator integration settings for encrypted Mercado Libre App, Claude, and NVIDIA credentials. Secret inputs are write-only, status responses never return values, and store authorization remains disabled until both Mercado Libre App fields are configured.
- API routes and the publish worker resolve database-backed credentials on each execution, with environment variables used only when no database override exists; updates do not require a service restart.
- Operator-triggered connection diagnostics verify Claude/NVIDIA credential and configured-model visibility, identify missing/invalid/rate-limited provider access, and reconcile each connected Mercado Libre store against `/users/me`. The endpoint never publishes, never runs automatically on page load, and returns normalized status without secrets or raw provider bodies; NVIDIA model visibility is not presented as proof of inference quota.
- Docker Compose services for PostgreSQL, Redis, backend API, collection worker, and publish worker, with PostgreSQL and Redis data bind-mounted under the D-drive project tree. The migration, API, collection, and publishing processes share one backend image rather than exporting four duplicate Playwright images.
- Compose migration gate (`alembic upgrade head`) plus database/Redis/API health checks and restart policies.

Not connected yet:

- The local runtime has no Mercado Libre, Claude, or NVIDIA production credentials, so no real Mercado Libre item has been published yet.
- Production-grade external KMS or secrets manager for Mercado Libre token encryption keys.

Verification for this change:

- Backend suite: 284 passed, with 7 PostgreSQL-only tests skipped in the default run.
- Isolated Docker PostgreSQL integration run: 7 passed, including serialized refresh-token rotation, concurrent collection, publish-job, and source-variant draft deduplication, atomic draft-version invalidation, and a final publish-evidence row lock that blocks concurrent draft changes until publication completes.
- PostgreSQL migrations through `20260720_0021` recovered legacy source ASINs from Amazon URLs, preserved duplicate unclassified legacy drafts with a partial identity index, backfilled collection identities and existing draft source ASINs, indexed site/identity lookup, added versioned store/shipping delivery fields, review execution metadata, structured source snapshots, source-variant draft bindings, structured source measurements, provider usage/request telemetry, and encrypted integration credentials.
- The complete Alembic chain upgraded to head and downgraded to base successfully on a disposable D-drive SQLite database.
- Frontend production build passed.
- Docker Compose dry-run schedules one backend image build, and the running API, collection worker, and publish worker share the same image SHA. A container-level smoke imported `json5` and parsed a commented JSON5 gallery successfully.
- Desktop and mobile browser smoke passed for all 18 sites, Classic/Premium controls, two verified non-FULL shipping options, read-only Amazon source price/currency, provider review metadata/token/request-ID rows, four write-only integration credential controls, explicit connection diagnostics, credential-gated store authorization, batch result rows, three source images, three source variants, domain-aware single/bulk variant collection, disabled existing-task states, terminal status refresh with no subsequent polling, two source measurements, variant draft creation, three category attribute suggestions, required-attribute save gates, saved configuration readiness, overflow, console errors, and failed responses.
- A live local PostgreSQL/API/browser integration smoke inserted a temporary collected source, read its structured measurements through the running backend, rendered both cards in the real frontend, and removed the test records afterward.
- A live local PostgreSQL/API/browser integration smoke persisted temporary provider token/request telemetry, read it through the running backend, rendered it in review history, and removed the draft, review, and audit records afterward.
- A live local PostgreSQL/API/browser integration smoke creates a temporary database, applies all migrations, starts an isolated API, verifies four ciphertext-only credential rows and status-only UI rendering, then terminates the API and drops the database without touching production credential rows.
- An isolated PostgreSQL/API smoke applies all migrations, creates a unique Amazon source variant, verifies country-domain preservation and idempotent task reuse through a temporary API, then drops the database without exposing the task to the production collection worker.

Next production phase:

- Configure production Claude/NVIDIA credentials, execute a real combined review, and reconcile the recorded token/request telemetry with provider consoles.
- Add a versioned, operator-maintained provider/model price table before calculating monetary AI cost.

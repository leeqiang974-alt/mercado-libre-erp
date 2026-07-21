# MVP Skeleton Status

Verified on: 2026-07-21

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Playwright-backed Amazon URL collection adapter with manual-action handling for CAPTCHA/challenge pages.
- Playwright collection uses storefront-specific locale and language headers, waits for title/primary-price/main-image evidence, and exits challenge pages early. Price extraction is scoped to the main product area so a recommendation price cannot be mistaken for source evidence when Amazon omits the product DOM.
- Amazon URL collection job model, single/batch create, list/run APIs, and frontend queue controls with per-row validation and duplicate reporting.
- CSV/XLSX file imports read a recognized URL column or a headerless first column and feed the same 100-row validation, canonicalization, duplicate detection, and queue path as pasted URLs.
- Manual HTML snapshots can resolve the exact challenged collection job after normalized Amazon URL and target-site matching. The operator source, draft, completed queue linkage, and audit event commit atomically under a job row lock; the source remains explicitly labeled as not independently fetched.
- Batch intake persists and indexes canonical Amazon domain/ASIN identities, limits each request to 100 URLs, and serializes deduplication on both PostgreSQL and SQLite so concurrent operator requests reuse the same job by default.
- Collection queue polling is bounded to the latest 100 jobs by default and supports limit/offset pagination; URL collection and manual HTML snapshot inputs keep independent state.
- Backend collection worker CLI for processing pending Amazon URL collection jobs in batches.
- The collection worker treats a candidate removed after queue selection as a lost claim, rolls back, and continues polling instead of restarting the process.
- Persisted Amazon URL collection results as source products, including manual-action and failed collection states.
- Structured Amazon source snapshots persist the full collected title, price, brand, bullets, description, image gallery, technical details, and discovered ASIN variants instead of reducing the source record to a URL/status shell.
- Amazon `colorImages`/`colorToAsin` page data supplies high-resolution galleries before DOM thumbnails, including single-quoted JavaScript objects and maximum-area `main` image maps; displayed-ASIN validation prevents redirected pages from contaminating the requested product, and each discovered color ASIN receives only its own authoritative script gallery.
- JSON5-style Amazon script objects with unquoted keys, comments, trailing commas, and JavaScript `undefined` values retain their variant dimensions and per-ASIN image galleries instead of being discarded.
- Collection history exposes a lightweight source summary and a lazy-loaded review panel for the full image gallery and variant evidence on desktop and mobile.
- Operators can create an idempotent, site-specific draft from the Amazon variant actually displayed by the collected page; the draft retains its source ASIN/attributes and page evidence.
- Non-selected Amazon variants must be queued for an independent page collection from the source review before they can become drafts. The API preserves the Amazon country domain, validates snapshot membership, reuses the canonical domain/ASIN/Mercado Libre-site task, and resolves only the draft bound to that completed variant page; parent-page titles, prices, descriptions, and measurements cannot be relabeled as sibling-ASIN evidence.
- Source review can queue up to 100 missing variants in one locked batch, reporting created/reused/selected counts. Duplicate ASIN rows collapse with selected precedence, and ID-based status polling keeps batch tasks current even when they fall outside the latest-100 queue window.
- Saved drafts expose their Amazon ASIN and variant attributes so operators can distinguish otherwise identical titles.
- Saved drafts can edit title, description, brand, and up to 12 product image URLs without changing Amazon source-price evidence or bypassing listing configuration. Every real content change atomically advances `content_version`, invalidates old AI review/approval evidence, and uses optimistic concurrency so a stale browser cannot overwrite a newer edit.
- Pricing and listing-configuration write responses return the committed draft content version in the same response. The frontend therefore cannot report a successful write as failed merely because a follow-up draft read timed out, and it blocks version-changing actions while listing-content edits are unsaved.
- Amazon specification tables and detail bullets produce structured item/package weights and product/package dimensions while retaining the original label/value; source review exposes this evidence on desktop and mobile.
- Every numbered Amazon technical-specification table is scanned. Composite dimension rows can also supply an inline item/package weight, while a dedicated weight row always takes precedence regardless of HTML row order.
- Structured measurements recognize conservative localized labels and units for Spanish, Brazilian Portuguese, German, French, Italian, Dutch, and Japanese Amazon detail tables. Latin diacritics are normalized without altering non-Latin scripts.
- Selected-page measurements can suggest explicit Mercado Libre weight and dimension attributes only for the selected Amazon ASIN, preventing a sibling variant from inheriting unverified logistics data.
- Existing drafts whose source ASIN and claimed variant ASIN do not match are rejected by listing-configuration and shared review/publish gates until the exact variant page is collected.
- Verified Mercado Libre category metadata produces conservative Amazon-to-Mercado Libre attribute suggestions; exact enumerated matches preserve `value_id`, ambiguous list values require manual entry, and mapped optional attributes remain editable.
- Listing configuration and publish validation enforce both `required` and `catalog_required` attributes, reject unknown category IDs and invalid enumerated value IDs when verified definitions are present, and translate common attribute failures into operator-facing messages.
- Local AI review policy.
- Claude Messages API review adapter that reports missing credentials or provider failures without local fallback.
- NVIDIA NIM/OpenAI-compatible chat review adapter that reports missing credentials or provider failures without local fallback.
- Mercado Libre OAuth authorization URL, callback, and token exchange skeleton.
- OAuth authorization supports all 18 configured sites through their marketplace-specific authorization domains. The selected site is signed into `state`; callbacks reject a seller from a different site before any store token is persisted.
- Persisted connected stores with token references instead of exposing raw tokens.
- Encrypted Mercado Libre access/refresh token credential storage for connected stores.
- Refresh-token rotation for Mercado Libre credentials before publish execution.
- Persisted product drafts for HTML snapshot imports.
- Persisted product drafts for successful URL collections.
- Amazon source amount/currency remain read-only evidence in the pricing workspace. Saved pricing is recalculated against that evidence and the selected site's currency, and is required at persisted AI review, preview, queue, retry, worker, and direct publish boundaries.
- Mercado Libre metadata proxy for listing types, category prediction, and category attributes.
- Authorized seller/category listing eligibility uses `/users/{seller_id}/available_listing_types`, filters out non-Classic/Premium offers, preserves Mercado Libre's site-specific names, and caches exact store/category evidence for 15 minutes.
- Listing configuration rejects cross-site categories and cannot be saved until the selected authorized seller is verified for the chosen category and commercial type. Direct execution, enqueue, retry, and publish workers reuse the same eligibility gate.
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
- Batch publish intake accepts up to 50 saved drafts after an explicit publication acknowledgement. Each draft independently reuses the latest persisted review, human approval, authorized store/site, seller listing-type eligibility, category attributes, and current non-FULL shipping gates; exact jobs are idempotently reused, while ready job rows and their audit events commit atomically.
- Batch publish preflight checks up to 50 selected drafts with the exact same evaluator used by queue intake, reports per-draft blockers before acknowledgement, and creates no publish jobs or publish audit events. Frontend results are bound to the selected draft set and ignore superseded responses so an old check cannot enable a changed selection.
- Backend publish worker CLI for processing pending publish jobs in batches.
- Persisted publish jobs for blocked, failed, and published execution attempts.
- Publish job list API for reviewing status, errors, item IDs, and permalinks.
- Publish job history is bounded and paginated, includes queued/started/completed timestamps, and the frontend polls only while pending or validating jobs exist. Terminal rows expose the Mercado Libre item id, permalink, normalized errors, manual refresh, and retry controls; polling stops when every visible job is terminal.
- Pending publish jobs can be cancelled through a two-step operator action before a worker claims them. Cancellation locks the same job row used by worker claims, records one atomic audit event, releases the exact draft configuration for a later requeue, and refuses validating or terminal work with a conflict instead of interrupting an in-flight Mercado Libre request.
- Publish job retry API and frontend retry control for blocked or failed jobs, preserving original job history and audit trail.
- Audit event log for AI review and publish execution actions, with frontend audit page.
- Alembic baseline migration for the current backend schema.
- Persisted local, Claude, and NVIDIA review results for saved drafts.
- Combined Claude + NVIDIA behavioral audit endpoint with strictest-result aggregation and orchestration audit events.
- Batch combined-review intake requires explicit provider-cost acknowledgement, queues only independently ready drafts, deduplicates active work, and leaves every result subject to its own human approval. The review worker stops a pass on provider throttling and defers untouched jobs without automatically retrying a charged attempt.
- Review results persist provider model, versioned safety prompt identifier, execution duration, provider status, provider-reported input/output/total token usage, request ID, and creation time; provider failures are audited without being presented as successful reviews.
- Review history API and frontend refresh control for saved draft audit trails.
- Desktop and mobile review history expose Claude, NVIDIA, and aggregate model/prompt/duration/token metadata and provider request IDs without exposing API keys or raw prompts.
- Provider errors preserve HTTP status, retryability, `Retry-After`, and request ID. Rate-limited reviews return HTTP 429 and wait for an explicit operator retry; the application does not automatically resend paid review requests.
- Claude/NVIDIA review output is validated against the versioned `meli-safety-v4` contract. Missing or extra fields, unknown decisions/risk levels, and mistyped values are provider failures rather than implicit low-risk passes; system-level instructions require evidence-bounded review across restricted goods, claims, brand risk, contradictions, required listing evidence, personal data, and local-market uncertainty while treating marketplace fields as untrusted data. Saved-draft reviews require and include the reconciled pricing formula plus authorized-store, site, category, Classic/Premium, attribute, and non-FULL shipping configuration without exposing store tokens or API keys.
- Successful paid provider calls remain as `completed_stale` historical evidence when a concurrent draft edit invalidates them; they are visible in history but cannot satisfy the current-version combined publish gate.
- Operators maintain append-only input/output prices per million tokens for exact Claude and NVIDIA model IDs. Review history snapshots the price row, currency, and estimated amount; missing usage or pricing remains explicitly unavailable.
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

- Backend suite: 375 passed, with 13 environment-specific tests skipped in the default run.
- Isolated Docker PostgreSQL integration run: 8 passed, including serialized manual-snapshot recovery and refresh-token rotation, concurrent collection, publish-job, and source-variant draft deduplication, atomic draft-version invalidation, and a final publish-evidence row lock that blocks concurrent draft changes until publication completes.
- A dedicated disposable PostgreSQL run verified that pending-job cancellation and worker claiming are mutually exclusive; its migrated database was dropped after the test and PostgreSQL reported zero matching temporary databases.
- PostgreSQL migrations through `20260721_0028` recovered legacy source ASINs from Amazon URLs, preserved duplicate unclassified legacy drafts with a partial identity index, backfilled collection identities and existing draft source ASINs, indexed site/identity lookup, added versioned store/shipping delivery fields, high-precision review execution costs, structured source snapshots, source-variant draft bindings, structured source measurements, provider usage/request telemetry, encrypted integration credentials, unique active provider/model pricing, persistent Amazon throttling, explicit inventory confirmation, and queued combined reviews.
- The complete Alembic chain upgraded to head and downgraded to base successfully on a disposable D-drive SQLite database.
- Frontend production build passed.
- Docker Compose dry-run schedules one backend image build, and the running API, collection worker, and publish worker share the same image SHA. A container-level smoke imported `json5` and parsed a commented JSON5 gallery successfully.
- Desktop and mobile browser smoke passed for all 18 sites, Classic/Premium controls, two verified non-FULL shipping options, read-only Amazon source price/currency, provider review metadata/token/request-ID rows, four write-only integration credential controls, explicit connection diagnostics, credential-gated store authorization, batch result rows, bound manual-snapshot job recovery with URL/site detachment, three source images, three source variants, domain-aware single/bulk variant collection, disabled existing-task states, terminal status refresh with no subsequent polling, two source measurements, variant draft creation, three category attribute suggestions, required-attribute save gates, saved configuration readiness, overflow, console errors, and failed responses.
- A live local PostgreSQL/API/browser integration smoke inserted a temporary collected source, read its structured measurements through the running backend, rendered both cards in the real frontend, and removed the test records afterward.
- A live local PostgreSQL/API/browser integration smoke persisted temporary provider token/request telemetry, read it through the running backend, rendered it in review history, and removed the draft, review, and audit records afterward.
- A live local PostgreSQL/API/browser integration smoke creates a temporary database, applies all migrations, starts an isolated API, verifies four ciphertext-only credential rows and status-only UI rendering, then terminates the API and drops the database without touching production credential rows.
- An isolated PostgreSQL/API smoke applies all migrations, creates a unique Amazon source variant, verifies country-domain preservation and idempotent task reuse through a temporary API, then drops the database without exposing the task to the production collection worker.

Next production phase:

- Configure production Claude/NVIDIA credentials, execute a real combined review, and reconcile the recorded token/request telemetry with provider consoles.
- Configure current Claude/NVIDIA model prices before the first paid review so cost snapshots are available from the first live run.

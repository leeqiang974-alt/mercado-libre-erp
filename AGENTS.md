# Project Delivery Rules

## Definition of Done

- Do not describe infrastructure, API shapes, mocked tests, or UI shells as a finished product.
- A capability is "implemented" only when it is reachable from the operator UI, persists real data, exposes failures clearly, and is verified through the running application.
- Keep demo/sample data out of default operator workflows. Demo modes must be explicitly labeled and isolated.
- Report external integrations as connected only when real credentials are configured and a live, non-destructive verification succeeds.
- Report publishing as complete only after an authorized Mercado Libre store can create a real non-FULL item through the guarded workflow.

## Required Operator Workflow

1. Add one or more real Amazon product URLs.
2. Collect and review source data, including images, variants, source price/currency, and collection failures.
3. Choose an authorized Mercado Libre store and its actual site.
4. Map category, required attributes, condition, stock, listing type (classic/premium), and non-FULL fulfillment.
5. Apply an explicit cost, exchange-rate, fee, margin, and rounding policy to calculate the target price.
6. Run Claude planning/review and NVIDIA behavioral/compliance review with provider status visible; local fallback must be labeled as fallback.
7. Approve, queue, publish, and inspect the returned item id, permalink, and error details.

## Product Truthfulness

- The UI must show integration readiness for Mercado Libre, Claude, NVIDIA, live publishing, database, and workers.
- Never silently substitute local review for Claude or NVIDIA and present it as provider output.
- Keep Amazon source currency separate from Mercado Libre target currency; never relabel an unconverted source price.
- Treat Amazon source amount/currency as read-only evidence. A persisted pricing formula must match that evidence, the Mercado Libre site currency, and the current draft target price; enforce this before persisted AI review, preview, queue, retry, worker, and direct execution.
- FULL fulfillment remains excluded. A site-level listing-type catalog is display metadata only; save and publish gates require fresh `available_listing_types` evidence for the exact authorized seller and category. Recheck the same store/category/type binding in direct execution and publish workers before `/items`.
- Treat Mercado Libre category attributes as verified only when the cache explicitly records `verified: true`; cache presence, non-empty definitions, and legacy saved configurations must never bypass category validation at save, review, preview, queue, retry, worker, or execute boundaries.
- Treat a lost or ambiguous Mercado Libre create-item response as an unknown outcome that requires store reconciliation; never retry it automatically.
- For local Mercado Libre marketplace items, create `/items` without `description`, then upload plain text through `/items/{item_id}/description`. Reconcile ambiguous description responses with GET; if the approved description cannot be proven, close the new item, retain its item id, and never create a replacement automatically.
- Claude and NVIDIA review responses are a publish gate, so parse them through a versioned strict schema. Missing fields, extra fields, unknown decisions or risk levels, and wrong value types must fail as `invalid_response`; never default an unrecognized provider result to `pass` or `low`.
- Send AI safety policy as a system instruction and marketplace fields as separately delimited untrusted user data. Persisted provider reviews require a current connected store, matching site, and allowlisted non-FULL shipping; revalidate that context under a store row lock when saving and again whenever an aggregate review is used for approval or publishing.
- Treat operator-provided Amazon HTML as a manual source. Require the requested ASIN to match a strong page identity signal, and never label it as independently collected.
- When an operator snapshot resolves a collection job, require a matching normalized Amazon URL, target site, and `needs_manual_action` state under a job row lock. Persist the operator source, draft, completed job linkage, and audit event atomically; concurrent submissions must create at most one draft.
- Preserve Amazon measurement labels and raw values as source evidence. Never copy selected-page measurements to a different ASIN variant; only map dimensions or weights when the draft is bound to the page's selected ASIN.
- Scope Amazon price extraction to the main product purchase area or an explicitly adjacent legacy title/price structure. A generic page-wide price must never become source-price evidence, even when the product title is present.
- Live publishing requires PostgreSQL row locking. SQLite is allowed only while live publishing is disabled.
- Every write that can invalidate review or approval must atomically increment the draft content version in the database. Verify shared write paths with a real PostgreSQL concurrent-session test so simultaneous pricing, listing, store, or shipping edits cannot preserve a stale review.
- Every semantic change to the Claude/NVIDIA review prompt or required response contract must increment `REVIEW_PROMPT_VERSION` and update persistence/history tests. Store the version identifier, model, duration, and provider status; never persist API keys, authorization headers, or full provider prompts/responses in review metadata.
- Preserve provider-reported input/output/total token usage and request IDs as execution evidence. Do not infer monetary cost without an explicit versioned price configuration. Surface 429 retry timing to the operator and never automatically resend a paid review request.
- Provider model prices are operator-maintained append-only versions. Capture the active exact-model price before sending each provider request, then snapshot that row, currency, and estimated amount with the response; later price changes must not recalculate in-flight or historical reviews, and missing price/token evidence must remain unknown rather than zero.
- Every paid Claude/NVIDIA review must hold one persistent execution lease per draft across queued and synchronous entry points. Bind provider-stage results to that review job, retain the same lease after provider or worker interruption, and require a new operator cost acknowledgement before manually retrying the same job so completed stages are reused rather than charged twice. Persist provider Retry-After windows across failed, retried, and newly queued jobs.
- Persist Mercado Libre, Claude, and NVIDIA integration credentials only as encrypted values. Read APIs and audit events may expose configured status and changed key names, never credential values. API routes and workers must resolve the same database-backed credentials at execution time; an explicitly saved empty value disables the environment fallback.
- Run integration-credential smoke tests against a migrated temporary database and isolated API process. Never snapshot, overwrite, or restore credential rows in the operator database; verify isolation by comparing production row counts before and after and checking that no temporary database remains.
- Run any smoke test that creates a consumable collection or publish job against a migrated temporary database and isolated API process. Never insert then delete test jobs in the operator queue because a live worker can claim them; verify the production worker restart count is unchanged and no temporary database remains.
- Integration diagnostics must be operator-triggered and non-publishing. Return normalized status codes only; never expose credentials, authorization headers, or raw provider response bodies. Claude/NVIDIA model-list success proves credential validity and configured-model visibility, not successful paid inference or account quota. Follow bounded provider pagination before reporting a configured model unavailable. Mercado Libre application status requires at least one currently connected store, and store verification must reconcile `/users/me` seller and site identity.
- Any Mercado Libre access-token refresh must serialize on the `TokenCredential` row and recheck expiry after acquiring the lock. Verify refresh-token rotation with concurrent sessions on real PostgreSQL so diagnostics, metadata reads, workers, and direct publishing cannot consume the same refresh token twice.
- Mercado Libre OAuth authorization must use the marketplace domain for the selected site. Bind that site into the signed OAuth state and reject the callback before token persistence when `/users/me.site_id` differs from the requested site.
- Every browser-based Amazon collection path must reserve a per-marketplace-domain request slot through persistent database coordination. CAPTCHA challenges require exponential backoff that survives worker restarts; never issue an immediate second page request inside one job. Reuse collected evidence only for the exact normalized Amazon domain and ASIN, and expose deferred execution time to the operator.
- Amazon collection must not infer sale condition or available inventory. Require the operator to confirm inventory and choose the verified category-specific `ITEM_CONDITION` before AI review or publishing. Keep Amazon source price/currency separate from target price/currency; never backfill one from the other.

## Verification

- Backend unit tests and frontend builds are necessary but not sufficient.
- Verify the main workflow in the running browser at desktop and mobile sizes.
- Record what was tested with real integrations, what used fixtures, and what remains blocked by missing credentials.

## Storage Placement

- Keep project source, databases, Docker bind mounts, browser profiles, and generated artifacts under `D:\amazon-meli-publisher`; place shared tool caches in dedicated D-drive cache directories.
- Do not create project data or generated output on C. System-installed runtimes may remain on C, but their project-specific temp/output paths must be redirected to D when configurable.
- Verify storage changes through resolved host paths, Docker mount inspection, and a write test from the affected container or process.

## Work Continuity And Reporting

- Continue implementation through coding, verification, review, and commit. Do not stop after one subsystem while meaningful credential-independent product work remains.
- Progress reports must distinguish long-lived services, currently executing commands, active review agents, and completed code. Never present container uptime as active development time.

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
- FULL fulfillment remains excluded. Supported listing choices come from live Mercado Libre metadata for the authorized store site.
- Treat a lost or ambiguous Mercado Libre create-item response as an unknown outcome that requires store reconciliation; never retry it automatically.
- Treat operator-provided Amazon HTML as a manual source. Require the requested ASIN to match a strong page identity signal, and never label it as independently collected.
- Live publishing requires PostgreSQL row locking. SQLite is allowed only while live publishing is disabled.

## Verification

- Backend unit tests and frontend builds are necessary but not sufficient.
- Verify the main workflow in the running browser at desktop and mobile sizes.
- Record what was tested with real integrations, what used fixtures, and what remains blocked by missing credentials.

## Storage Placement

- Keep project source, databases, Docker bind mounts, browser profiles, and generated artifacts under `D:\amazon-meli-publisher`; place shared tool caches in dedicated D-drive cache directories.
- Do not create project data or generated output on C. System-installed runtimes may remain on C, but their project-specific temp/output paths must be redirected to D when configurable.
- Verify storage changes through resolved host paths, Docker mount inspection, and a write test from the affected container or process.

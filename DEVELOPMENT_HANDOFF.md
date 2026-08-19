# Amazon to Mercado Libre Publisher - Development Handoff

This file is the handoff brief for the next developer or coding agent.
Read it together with `AGENTS.md` before changing code.

## Global Selling Price References

- For this CBT store, `/marketplace/benchmarks/items/{CBT_ITEM}/details` returns
  `400 Invalid site id for item`. Price references are issued for active market
  child items (for example `MLB...`) under the remote marketplace shadow seller,
  not for a CBT parent item. Query `/marketplace/users/{CBT_SELLER}` first and
  use each Remote marketplace `user_id` with `/marketplace/benchmarks/user/{USER_ID}/items`.
- The list response is not a parent-item mapping. Build and persist an explicit
  CBT-parent to market-child mapping before showing a price reference in the
  parent-item table. Do not treat an empty benchmark as zero fees or zero profit.

## Product Truth

This repository is an in-progress MVP for an Amazon-to-Mercado Libre listing
workflow. It is not a finished ERP.

The intended first workflow is:

```text
Amazon product URL or HTML snapshot
  -> collect and review source evidence
  -> select exact Amazon variant
  -> create Mercado Libre draft
  -> configure site/category/attributes/price/shipping
  -> Claude + NVIDIA review
  -> human approval
  -> publish to an authorized Mercado Libre store
  -> verify item and description
```

Do not report live publishing as complete until a real authorized store creates
one real non-FULL item through the guarded workflow.

## Fixed Business Requirements

- Amazon has no API integration. Collect from the product page with Playwright
  or accept an operator-provided HTML snapshot when Amazon presents a challenge.
- Mercado Libre uses its API for metadata, OAuth, item creation, and description.
- Support all configured Mercado Libre sites.
- Exclude `FULL` fulfillment everywhere: UI, validation, preview, queue, worker,
  payload construction, and execution.
- For each selected site, allow the seller's verified `Classic` and `Premium`
  listing types when Mercado Libre makes them available for that seller/category.
- A listing type catalog is not seller authorization. Re-check the exact
  authorized store, site, category, listing type, attributes, and shipping before
  publish execution.
- Never publish without current human approval and a valid Claude/NVIDIA review.
- Amazon source price and currency are read-only evidence. Target pricing must
  use an explicit cost, exchange-rate, fee, tax, margin, and rounding formula.
- Never use a sibling Amazon ASIN's title, price, images, measurements, or
  variants as evidence for the selected ASIN.
- Keep all project data, Docker bind mounts, browser data, and generated output
  under `D:\\amazon-meli-publisher`. Do not move project output to C drive.

## Current Repository

Project root:

```text
D:\\amazon-meli-publisher\\.worktrees\\mvp-skeleton
```

Important areas:

- `backend/app/services/amazon/`: Amazon parsing, normalization, and collection.
- `backend/app/services/meli/`: Mercado Libre metadata, payload, and publishing.
- `backend/app/services/publish_jobs.py`: publish queue state and idempotency.
- `backend/app/api/routes/publishing.py`: guarded direct/retry/reconcile routes.
- `backend/app/workers/`: collection, review, and publish workers.
- `backend/app/models/`: persisted source, draft, review, store, credential, and job models.
- `backend/tests/`: backend behavior and integration-oriented tests.
- `frontend/src/pages/`: operator UI pages.
- `docker-compose.yml`: local services and D-drive bind mounts.
- `docs/mvp-status.md`: detailed capability and verification record.
- `docs/product-gap-audit.md`: honest product gap list.
- `docs/superpowers/specs/2026-07-07-amazon-meli-publisher-design.md`: approved design.

## Already Implemented

- Amazon URL and HTML snapshot intake with challenge/manual-action states.
- Amazon source persistence with title, price, currency, bullets, description,
  images, technical specifications, dimensions, weights, and ASIN variants.
- Exact variant evidence checks. A discovered sibling ASIN must be collected
  independently before it can become a draft.
- CSV/XLSX URL intake, duplicate detection, bounded collection queues, and a
  collection worker.
- Persistent drafts with editable content and optimistic content-version checks.
- Mercado Libre OAuth/store persistence with encrypted token credentials.
- Site-aware category and attribute metadata lookup.
- Verified seller/category listing eligibility for Classic/Premium.
- Explicit non-FULL shipping preference selection and revalidation.
- Pricing formula persistence and publish/review gates.
- Local, Claude, and NVIDIA review adapters with strict review output validation.
- Human approval records and audit events.
- Direct and queued publishing through an authorized `store_id`; the frontend
  must never supply an access token.
- Publish job history, retry, cancellation of still-pending jobs, and worker
  processing.
- Two-stage Mercado Libre local listing flow: create `/items` first, then send
  plain text to `/items/{item_id}/description`.
- Unknown `/items` outcomes are quarantined. Each attempt has a unique frozen
  `seller_custom_field`; automatic retry is forbidden.
- Operator reconciliation searches the authorized seller by exact SKU and
  accepts one match only after identity, site, category, listing type, shipping,
  open status, and description all match the frozen request.
- Docker Compose services for PostgreSQL, Redis, API, frontend, and workers.

## Not Completed / Not Proven

- No real Mercado Libre credentials are configured in the current environment.
- No real Mercado Libre item has been published yet.
- Claude and NVIDIA live inference has not been proven with production keys.
- Automated external-provider tests use mocks and do not prove live API behavior.
- External KMS/secrets-manager integration is not production-grade yet.
- This is not a full ERP: orders, inventory, purchasing, warehouse, logistics
  reconciliation, after-sales, finance, role permissions, alerts, reporting,
  backup/recovery operations, and production observability still need work.

## Non-Negotiable Safety Rules

- Never seed or delete test publish jobs in the operator database. Use an
  isolated migrated temporary database for consumable queue tests.
- Live publishing requires PostgreSQL row locks. SQLite is for non-live tests
  only.
- Treat a timeout, connection drop, or HTTP 408 after `/items` as unknown, not a
  normal retryable failure.
- Never close a job as published from an item ID alone. Verify the exact item
  identity and frozen commercial fields.
- If an item search returns zero or multiple exact-SKU matches, keep the job
  blocked for operator reconciliation.
- If an item is found but its identity is wrong, clear the stored item ID and
  keep the job unresolved; do not create a replacement automatically.
- If the description cannot be proven to match, close the created item, retain
  its item ID, and do not retry item creation.
- Never expose API keys, OAuth tokens, refresh tokens, authorization headers, or
  full provider prompts/responses in API responses, logs, or documentation.
- Do not call the system an ERP or claim production-ready publishing without
  evidence from the running application and a real account test.

## Local Startup

Run from the project root:

```powershell
cd D:\\amazon-meli-publisher\\.worktrees\\mvp-skeleton
docker compose up -d --build
docker compose ps
```

URLs:

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`

Expected services:

- `postgres`, `redis`, `backend`, `frontend`
- `collection_worker`, `review_worker`, `publish_worker`

Verify that PostgreSQL and Redis mounts resolve under the project `data` folder
on D drive. Do not use `docker compose down -v` unless the operator explicitly
requests deletion of local database volumes.

## Verification Commands

```powershell
cd D:\\amazon-meli-publisher\\.worktrees\\mvp-skeleton\\backend
pytest -q
ruff check app tests

cd ..\\frontend
npm run build

cd ..
docker compose ps
docker compose logs --since 10m collection_worker publish_worker review_worker
git status --short
```

Before declaring a change complete, also inspect the running frontend at desktop
and mobile widths. Confirm no console errors, horizontal overflow, or controls
that escape their panel. Do not insert demo jobs into the operator queue for
browser testing.

## Recommended Next Phase

1. Finish and verify the current unknown-publication reconciliation change.
   Run the complete backend suite, Ruff, frontend build, Docker smoke checks,
   and browser smoke checks. Update `docs/mvp-status.md` with the actual counts.
2. Configure a dedicated test Mercado Libre application and one authorized test
   seller. Run a controlled non-FULL Classic or Premium publication, then verify
   item ID, permalink, listing type, shipping, status, and description.
3. Configure Claude and NVIDIA credentials through the write-only integration
   settings. Run one real combined review and reconcile request IDs and token
   usage with provider consoles.
4. Add production hardening: external KMS, structured monitoring, backups,
   restore drills, rate-limit dashboards, error alerts, and deployment controls.
5. Only after the listing workflow is stable, expand toward ERP modules such as
   inventory, orders, purchasing, warehouse, logistics, after-sales, finance,
   roles, and reporting.

## Handoff Rules For The Next Agent

- Read this file and `AGENTS.md` before editing.
- Inspect `git status` first and preserve unrelated uncommitted changes.
- Treat the current branch as an unfinished working tree; do not assume the
  documented test count is current until tests are rerun.
- Keep changes small and behavior-driven. Add tests for every publish-state or
  external-side-effect change.
- Continue through implementation, verification, review, and commit when the
  work is credential-independent. Do not stop after merely starting services.
- Report separately: long-lived Docker services, commands currently running,
  completed tests/reviews, and genuinely unfinished product capabilities.

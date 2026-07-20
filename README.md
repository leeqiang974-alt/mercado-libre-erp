# Amazon Mercado Libre Publisher

Local-first MVP for collecting Amazon product page data, preparing Mercado Libre drafts, reviewing drafts with Claude/NVIDIA providers, and publishing approved non-FULL listings through Mercado Libre API adapters.

Project root: `D:\amazon-meli-publisher`

## Local Backend

```powershell
cd D:\amazon-meli-publisher\.worktrees\mvp-skeleton\backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Health check: `http://127.0.0.1:8000/health`

## Local Frontend

```powershell
cd D:\amazon-meli-publisher\.worktrees\mvp-skeleton\frontend
npm install
npm run dev
```

Frontend: `http://127.0.0.1:5173`

## Local Services

```powershell
cd D:\amazon-meli-publisher\.worktrees\mvp-skeleton
docker compose up -d
docker compose up -d backend collection_worker publish_worker
```

Compose automatically waits for PostgreSQL, runs `alembic upgrade head` through the one-shot `migrate` service, and only then starts the API and workers. PostgreSQL and Redis persist through project-local bind mounts under `data/` on D drive; the API and both workers have health/restart safeguards for long-running local deployments.

## Database Migrations

```powershell
cd D:\amazon-meli-publisher\.worktrees\mvp-skeleton\backend
python -m alembic upgrade head
```

## Collection Worker

```powershell
cd D:\amazon-meli-publisher\.worktrees\mvp-skeleton\backend
python -m app.worker --limit 10
python -m app.worker --loop --interval 30 --limit 10
python -m app.worker --queue publish --limit 10
python -m app.worker --queue publish --loop --interval 30 --limit 10
```

## Safety Rules

- Amazon collection starts from user-provided pages or HTML snapshots.
- Mercado Libre FULL fulfillment is excluded.
- AI providers never receive Mercado Libre tokens.
- No publish request is sent unless a human approval flag is present.
- Publish execution uses an authorized store id and backend-encrypted Mercado Libre token, not a frontend-provided access token.

## Current MVP Capabilities

- Import an Amazon HTML snapshot and optionally save it as a draft.
- Collect an Amazon URL through the backend Playwright adapter; challenge pages are marked for manual action.
- Queue up to 100 Amazon product URLs per batch with indexed Amazon domain/ASIN identities, duplicate detection, per-row outcomes, and a bounded recent-job history.
- Run queued Amazon URL collection jobs through a backend worker CLI.
- Run API, collection worker, and publish worker services through Docker Compose.
- Persist successful URL collections as source products and product drafts.
- Persist reviewable Amazon source snapshots with the original image gallery, bullets, technical details, and discovered ASIN variants.
- Parse and persist reviewable item/package weight and product/package dimensions from Amazon specification tables and detail bullets, retaining the original label and value.
- Review collected source evidence from the collection queue and create idempotent, site-specific drafts from individual Amazon variants.
- Match saved Amazon ASIN attributes such as color, size, and brand against verified Mercado Libre category metadata, preserve exact `value_id` values, and require operator confirmation before saving the listing configuration.
- Suggest selected-ASIN weight and dimensional evidence only for explicit Mercado Libre weight/length/width/height attributes; measurements are never inherited by a different Amazon variant.
- Persist failed/manual-action URL collections as source products for later handling.
- List saved drafts.
- Generate a Mercado Libre OAuth authorization URL and persist the connected store callback as a token reference.
- Store Mercado Libre access/refresh tokens encrypted in the backend token vault.
- Refresh expiring Mercado Libre access tokens with encrypted refresh tokens before publishing.
- List connected stores.
- Fetch Mercado Libre listing types, category predictions, and category attributes through backend metadata routes.
- Cache Mercado Libre listing types and category attributes, with explicit refresh endpoints.
- Save Mercado Libre category, listing type, fulfillment, and attribute values as draft listing configuration.
- Persist operator approval for drafts before publish-from-draft execution.
- Load verified non-FULL shipping options from the authorized store, bind the operator's selection to the versioned draft, and build the validated Mercado Libre item payload.
- Preview publishing from saved draft listing configuration.
- Execute a guarded publish adapter only when `ALLOW_LIVE_PUBLISH=true`.
- Execute guarded publishing directly from saved draft listing configuration.
- Queue saved draft publishing as pending jobs for the backend publish worker.
- Resolve encrypted store tokens server-side for guarded publish execution.
- Bind each authorized store to the `site_id` returned by Mercado Libre seller profile lookup and reject cross-site publish attempts.
- Sign and expire Mercado Libre OAuth state values before accepting a callback.
- Manage the current database schema through an Alembic baseline migration.
- Persist publish attempts as jobs with blocked/published/failed status, errors, item id, and permalink.
- List publish jobs from the frontend.
- Retry blocked or failed publish jobs from saved draft configuration while preserving the original job history.
- Run local, Claude, or NVIDIA review from the backend review API.
- Run a combined behavioral audit that executes NVIDIA pre-screening and Claude deep review, aggregates the strictest decision, and feeds that result into the publish gate.
- Persist local, Claude, and NVIDIA review results against saved product drafts.
- Persist and list audit events for AI review and publish execution actions.
- List review history for a saved product draft from the frontend.
- Use Claude/NVIDIA provider adapters only when their API keys are configured. Missing keys or provider failures are surfaced explicitly and cannot satisfy the combined publish-review gate.

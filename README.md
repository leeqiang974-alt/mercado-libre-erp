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
```

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
- Queue Amazon URL collection jobs, run queued jobs, and list job status/history.
- Run queued Amazon URL collection jobs through a backend worker CLI.
- Persist successful URL collections as source products and product drafts.
- Persist failed/manual-action URL collections as source products for later handling.
- List saved drafts.
- Generate a Mercado Libre OAuth authorization URL and persist the connected store callback as a token reference.
- Store Mercado Libre access/refresh tokens encrypted in the backend token vault.
- List connected stores.
- Fetch Mercado Libre listing types, category predictions, and category attributes through backend metadata routes.
- Save Mercado Libre category, listing type, fulfillment, and attribute values as draft listing configuration.
- Build and validate non-FULL Mercado Libre item payloads.
- Preview publishing from saved draft listing configuration.
- Execute a guarded publish adapter only when `ALLOW_LIVE_PUBLISH=true`.
- Execute guarded publishing directly from saved draft listing configuration.
- Resolve encrypted store tokens server-side for guarded publish execution.
- Manage the current database schema through an Alembic baseline migration.
- Persist publish attempts as jobs with blocked/published/failed status, errors, item id, and permalink.
- List publish jobs from the frontend.
- Run local, Claude, or NVIDIA review from the backend review API.
- Persist local, Claude, and NVIDIA review results against saved product drafts.
- Persist and list audit events for AI review and publish execution actions.
- List review history for a saved product draft from the frontend.
- Use Claude/NVIDIA provider adapters when `CLAUDE_API_KEY` or `NVIDIA_API_KEY` is configured; otherwise they safely fall back to local policy.

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

## Safety Rules

- Amazon collection starts from user-provided pages or HTML snapshots.
- Mercado Libre FULL fulfillment is excluded.
- AI providers never receive Mercado Libre tokens.
- No publish request is sent unless a human approval flag is present.
- Publish execution uses an authorized store id and backend token reference, not a frontend-provided access token.

## Current MVP Capabilities

- Import an Amazon HTML snapshot and optionally save it as a draft.
- Collect an Amazon URL through the backend Playwright adapter; challenge pages are marked for manual action.
- Persist successful URL collections as source products and product drafts.
- Persist failed/manual-action URL collections as source products for later handling.
- List saved drafts.
- Generate a Mercado Libre OAuth authorization URL and persist the connected store callback as a token reference.
- List connected stores.
- Fetch Mercado Libre listing types, category predictions, and category attributes through backend metadata routes.
- Build and validate non-FULL Mercado Libre item payloads.
- Execute a guarded publish adapter only when `ALLOW_LIVE_PUBLISH=true`.

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

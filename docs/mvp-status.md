# MVP Skeleton Status

Verified on: 2026-07-07

Implemented:

- FastAPI health endpoint.
- Amazon HTML parser and normalizer.
- Local AI review policy with Claude/NVIDIA provider stubs.
- Mercado Libre non-FULL payload builder.
- Publishing validation gates for human approval, listing type availability, and FULL exclusion.
- API flow for import, review, and publish preview.
- React MVP shell for import, draft review, and publishing readiness.
- Docker Compose services for PostgreSQL and Redis.

Not connected yet:

- Live Amazon browser collection.
- Live Mercado Libre OAuth and item publishing.
- Live Claude API.
- Live NVIDIA NIM API.
- Persistent PostgreSQL migrations.

Next production phase:

- Add Playwright live collector with manual challenge state.
- Add Mercado Libre OAuth callback and metadata fetch.
- Add persisted drafts and publish jobs.
- Replace AI stubs with real provider clients behind the same interfaces.

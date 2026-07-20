# Product Gap Audit

Updated: 2026-07-20

## Honest Current State

The repository contains an operational local workflow for Amazon URL collection and verified HTML snapshots, persisted draft review and approval, authorized Mercado Libre stores, guarded non-FULL publishing, and background jobs. Live external execution still depends on operator-supplied Mercado Libre, Claude, and NVIDIA credentials.

## Verified Real Behavior

- Docker API, frontend, PostgreSQL, Redis, collection worker, and publish worker run with localhost-only ports.
- PostgreSQL data is bind-mounted under the project on D drive; Docker Desktop's WSL disk is configured under `D:\\DockerDesktop\\wsl`.
- Amazon URL jobs persist success, manual-action, timeout, and failure outcomes. Operator HTML snapshots require a matching Amazon ASIN and complete core product fields.
- Mercado Libre publishing supports all configured sites and Classic/Premium offers while excluding FULL logistics before and after item creation.
- Publish outcomes that may have created an item but cannot be confirmed are quarantined for manual reconciliation and cannot be retried automatically.
- Claude and NVIDIA failures are explicit. Only the latest persisted combined behavioral audit can satisfy approval and publishing gates.
- PostgreSQL and clean SQLite migrations, backend tests, frontend production build, and desktop/mobile browser smoke checks pass.

## Missing or Misleading Behavior

- Amazon collection does not provide a reliable source market/currency contract, complete image set, variants, SKU dimensions, or shipping weight.
- Amazon page structure and anti-automation challenges can still require an operator-provided HTML snapshot.
- Store authorization, live metadata, AI providers, and live publishing are unconfigured in the running environment.
- Automated end-to-end tests mock external Amazon, AI, and Mercado Libre behavior; they prove internal orchestration, not live integration.
- No real Mercado Libre item has been published from this environment, so production credentials, seller shipping preferences, category metadata, and post-publication reconciliation still need a controlled account test.

## Recovery Priorities

1. Configure a test Mercado Libre application and authorize one seller account for a controlled non-FULL publication.
2. Configure Claude and NVIDIA credentials, run a real combined review, and retain provider/audit evidence.
3. Verify live listing-type, category-attribute, shipping-preference, and post-publication responses for every target site used by the operator.
4. Expand Amazon fidelity for variants, dimensions, weight, and complete image sets where the source page exposes them.

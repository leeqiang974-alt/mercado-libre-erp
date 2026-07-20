# Product Gap Audit

Updated: 2026-07-21

## Honest Current State

The repository contains an operational local workflow for Amazon URL collection and verified HTML snapshots, persisted draft review and approval, authorized Mercado Libre stores, guarded non-FULL publishing, and background jobs. Live external execution still depends on operator-supplied Mercado Libre, Claude, and NVIDIA credentials.

## Verified Real Behavior

- Docker API, frontend, PostgreSQL, Redis, collection worker, and publish worker run with localhost-only ports.
- PostgreSQL and Redis data are bind-mounted under the project on D drive; Docker Desktop's WSL disk is configured under `D:\\DockerDesktop\\wsl`.
- Amazon URL jobs persist success, manual-action, timeout, and failure outcomes. Operator HTML snapshots require a matching Amazon ASIN and complete core product fields.
- A validated operator snapshot can now close its exact challenged queue item and atomically link the replacement source plus draft; URL/site mismatches and concurrent duplicate resolutions fail without partial records.
- Mercado Libre publishing supports all configured sites and Classic/Premium offers while excluding FULL logistics before and after item creation.
- Classic/Premium eligibility is fetched from Mercado Libre for the exact authorized seller and category. The verified result retains provider names, expires after 15 minutes, blocks cross-site categories, and is rechecked by synchronous and queued publish gates rather than treating the site catalog as seller permission.
- Publish outcomes that may have created an item but cannot be confirmed are quarantined for manual reconciliation and cannot be retried automatically.
- Claude and NVIDIA failures are explicit. Only the latest persisted combined behavioral audit can satisfy approval and publishing gates.
- Claude and NVIDIA output follows a versioned strict schema. Unknown decisions or risk levels, missing/extra fields, and wrong types fail closed instead of being aggregated as a pass.
- Saved provider reviews carry reconciled pricing and complete listing context. Safety policy is isolated in a system message, marketplace content is delimited as untrusted user data, and connected-store/site/non-FULL logistics are revalidated under lock before review persistence and whenever an aggregate review is used.
- Explicit non-publishing diagnostics normalize Claude/NVIDIA credential and configured-model visibility plus Mercado Libre seller/site identity without returning secrets or provider bodies. An expiring Mercado Libre token may be refreshed as credential maintenance; model-list success is intentionally not treated as proof of paid inference quota.
- Claude/NVIDIA model prices are operator-maintained append-only versions. Provider reviews retain the exact price row and estimated currency amount, while unknown usage or missing prices remain unpriced instead of being inferred.
- Refresh-token rotation is serialized on the credential row and rechecks expiry after locking, preventing diagnostics and publishing paths from consuming the same Mercado Libre refresh token concurrently.
- PostgreSQL and clean SQLite migrations, backend tests, frontend production build, and desktop/mobile browser smoke checks pass.

## Missing or Misleading Behavior

- Amazon collection now reads high-resolution `colorImages` galleries and binds `colorToAsin` groups without cross-variant image leakage, including JSON5-style script objects. Discovered variants can be independently queued to obtain their own page evidence, composite technical rows retain inline weights, and major regional labels/units are normalized conservatively. Complete evidence still cannot be guaranteed for undocumented embedded formats or unrecognized locale-specific labels; selected-page measurements are never copied to sibling variants.
- Amazon page structure and anti-automation challenges can still require an operator-provided HTML snapshot.
- Store authorization, live metadata, AI providers, and live publishing are unconfigured in the running environment; encrypted credentials can now be entered and checked from the Stores workspace without restarting API or workers.
- Automated end-to-end tests mock external Amazon, AI, and Mercado Libre behavior; they prove internal orchestration, not live integration.
- No real Mercado Libre item has been published from this environment, so production credentials, seller shipping preferences, category metadata, and post-publication reconciliation still need a controlled account test.

## Recovery Priorities

1. Configure a test Mercado Libre application and authorize one seller account for a controlled non-FULL publication.
2. Configure Claude and NVIDIA credentials, run a real combined review, and retain provider/audit evidence.
3. Verify live seller/category listing-type, category-attribute, shipping-preference, and post-publication responses for every target site used by the operator.
4. Continue expanding Amazon fidelity for undocumented embedded formats, remaining locale-specific labels/units, and page-specific per-variant evidence.

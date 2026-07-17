# Product Gap Audit

Updated: 2026-07-15

## Honest Current State

The repository contains a working technical skeleton: Amazon HTML parsing, persistent drafts and jobs, Mercado Libre OAuth and publishing adapters, AI provider adapters, and Docker services. It is not yet a usable end-to-end operator product.

## Verified Real Behavior

- Docker API, PostgreSQL, Redis, collection worker, and publish worker run.
- A real Amazon URL produced a persisted draft with title, description, brand, price, and one image.
- Database migrations and local validation tests pass.

## Missing or Misleading Behavior

- The default import screen is populated with a fake Amazon URL and Bottle HTML.
- Amazon collection does not provide a reliable source market/currency contract, complete image set, variants, SKU dimensions, or shipping weight.
- The collected source price is copied into a target draft without a conversion and pricing policy.
- There is no operational pricing workflow for exchange rate, marketplace fees, shipping, tax, target margin, and rounding.
- Store authorization, live metadata, AI providers, and live publishing are unconfigured in the running environment.
- Claude and NVIDIA silently fall back to local rules, which can make provider review appear more complete than it is.
- The UI is a set of forms and JSON blocks, not a queue-oriented workflow for bulk collection, mapping, approval, and publishing.
- Automated end-to-end tests mock external Amazon, AI, and Mercado Libre behavior; they prove internal orchestration, not live integration.

## Recovery Priorities

1. Replace the demo-first UI with an operational dashboard and integration readiness checks.
2. Build real single and batch Amazon URL intake with persistent collection status and draft inspection.
3. Introduce source-product fidelity and an explicit pricing calculation model.
4. Bind mapping and listing choices to an authorized Mercado Libre store/site.
5. Make AI provider identity, failures, and fallback behavior explicit.
6. Complete one real non-FULL publication in a test-safe Mercado Libre account and retain evidence.

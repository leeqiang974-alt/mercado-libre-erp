# Amazon to Mercado Libre Publisher Design

Date: 2026-07-07
Status: Approved for implementation planning
Project location: D:\amazon-meli-publisher

## 1. Goal

Build a system that collects product data from Amazon pages, converts it into publishable Mercado Libre product drafts, runs AI-assisted quality and behavior review through Claude and NVIDIA, and publishes approved products through the Mercado Libre API into authorized stores.

The first production path is:

Amazon product page URL or batch URL import -> page collector -> normalized product draft -> category and attribute mapping -> Claude/NVIDIA review -> human approval -> Mercado Libre API publishing.

The system must support Mercado Libre site selection across supported sites, except FULL fulfillment publishing. For each supported site, the operator can choose available non-FULL listing modes such as classic and premium where the site/account/category supports them.

## 2. Non-Goals For The First Version

- No automatic publishing without human approval.
- No Amazon Product Advertising API dependency, because the user cannot call Amazon API and Amazon PA-API is not a reliable first-version dependency.
- No attempt to bypass Amazon, Mercado Libre, or marketplace anti-abuse controls.
- No direct access by Claude or NVIDIA to Mercado Libre access tokens.
- No FULL fulfillment workflow in the first version.
- No price war automation, automatic brand impersonation, or restricted product bypass.

## 3. Product Scope

### 3.1 Amazon Collection

The first version collects from Amazon product pages instead of Amazon API.

Supported input:

- Single Amazon product URL.
- Batch URL import through CSV/XLSX.
- Optional ASIN field if present in the import file.

Collected fields:

- Source URL and ASIN when visible or derivable.
- Title.
- Main image and gallery image URLs.
- Bullet points.
- Description or product overview.
- Brand and manufacturer when visible.
- Price, currency, coupon marker, and availability text when visible.
- Variant options such as color, size, style, pack quantity, and selected variant URL.
- Technical details table.
- Product dimensions and weight when visible.
- Breadcrumb/category hints.

Collector requirements:

- Use a browser automation collector with strict rate limits, retry backoff, and cache.
- Keep raw HTML/screenshot evidence only when needed for debugging and audit.
- Detect bot challenge, CAPTCHA, blocked pages, missing content, and unavailable products.
- Stop and mark a collection task as "needs manual action" when Amazon blocks or challenges the request.
- Never implement credential theft, CAPTCHA solving, proxy abuse, or user-session extraction without explicit user-controlled browser login.

### 3.2 Mercado Libre Publishing

Publishing uses Mercado Libre API through authorized seller stores.

Supported behavior:

- OAuth authorization per store.
- Site selection for supported Mercado Libre sites.
- Exclude FULL fulfillment workflows.
- Allow the operator to choose non-FULL listing types exposed by the site/account/category, including classic and premium when available.
- Validate category, required attributes, price, currency, stock, pictures, condition, warranty, shipping mode, and listing type before publish.
- Create draft previews before final publish.
- Record publish result, item ID, permalink, site, listing type, seller account, request summary, and error response.

The publishing layer must not hard-code one country. The MVP default can be MLM (Mexico), but the design must allow other sites by configuration.

Important interpretation: "FULL" is treated as excluded fulfillment/logistics behavior, not as a normal listing type. Classic/premium are listing choices only when Mercado Libre returns them as valid for the current site/account/category.

### 3.3 AI Review And Planning

Claude and NVIDIA participate in planning, review, and quality gates, but they do not directly publish products.

Claude responsibilities:

- Review title and description for misleading claims, restricted claims, brand misuse, unsafe wording, and missing human-check requirements.
- Rewrite title, bullets, and description in the target site language with conservative marketplace-safe phrasing.
- Produce structured review JSON with status, risk level, reasons, suggested edits, and required human actions.
- Review planned publisher actions before execution when a batch is high-risk or changes many listings.

NVIDIA responsibilities:

- Batch classification and attribute extraction.
- Optional image/text risk pre-screening.
- Fast category or feature suggestions where local/private inference is preferred.
- Large batch pre-filtering before Claude performs deeper review.

AI boundary:

- AI output is advisory and structured.
- The backend enforces policy gates.
- Tokens and publish credentials never leave the backend credential vault.
- Any AI recommendation that changes price, category, brand, condition, warranty, or publish status requires human confirmation.

## 4. Architecture

### 4.1 Services

Frontend web app:

- Import Amazon URLs.
- Monitor collection tasks.
- Review normalized drafts.
- Edit mapping, category, attributes, price, listing type, and shipping options.
- Display Claude/NVIDIA review results.
- Approve or reject publishing.
- Manage Mercado Libre store authorization.

Backend API:

- Authentication and operator roles.
- Mercado Libre OAuth and token refresh.
- Product draft CRUD.
- Amazon collection task management.
- Category/attribute mapping.
- AI review orchestration.
- Publish validation and publish execution.
- Audit logs and export.

Worker queue:

- Amazon page collection jobs.
- Image downloading and normalization jobs.
- Category prediction jobs.
- Claude review jobs.
- NVIDIA batch review jobs.
- Mercado Libre publish jobs.

Database:

- Stores.
- OAuth tokens.
- Source products.
- Product drafts.
- Draft variants.
- Images.
- Category mappings.
- Review results.
- Publish jobs.
- Audit events.

Storage:

- Local development storage under D:\amazon-meli-publisher\data.
- Production-ready abstraction for object storage later.

## 5. Data Flow

1. Operator imports Amazon product URLs manually or through a file.
2. Backend creates source product records and collection jobs.
3. Collector opens Amazon pages with controlled rate limits and extracts structured data.
4. Normalizer converts Amazon data into internal product draft format.
5. Category mapper suggests Mercado Libre site category and required attributes.
6. NVIDIA batch pre-screen extracts attributes and flags obvious risks.
7. Claude performs deeper compliance and language review.
8. Operator reviews the draft, edits required fields, chooses site and listing type, and approves.
9. Publisher validates against Mercado Libre API requirements.
10. Publisher uploads or links pictures as required by Mercado Libre.
11. Publisher creates the item/listing through the Mercado Libre API.
12. System stores item ID, result, audit trail, and errors.

## 6. Data Model Draft

Store:

- id
- marketplace = "mercadolibre"
- site_id
- seller_id
- display_name
- oauth_status
- token_reference
- created_at
- updated_at

SourceProduct:

- id
- source = "amazon_page"
- source_url
- asin
- raw_status
- collected_at
- collection_error
- raw_snapshot_reference

ProductDraft:

- id
- source_product_id
- target_site_id
- target_category_id
- title
- description
- brand
- condition
- price
- currency
- stock
- listing_type_id
- shipping_profile
- status
- risk_status

DraftVariant:

- id
- product_draft_id
- option_name
- option_value
- sku
- price_delta
- stock
- image_id

ReviewResult:

- id
- product_draft_id
- provider
- model
- risk_level
- decision
- reasons_json
- suggested_changes_json
- created_at

PublishJob:

- id
- product_draft_id
- store_id
- requested_by
- status
- request_summary_json
- response_summary_json
- meli_item_id
- permalink
- created_at
- completed_at

AuditEvent:

- id
- actor_type
- actor_id
- action
- entity_type
- entity_id
- before_json
- after_json
- created_at

## 7. Validation And Safety Gates

Blocking gates before publish:

- Missing authorized Mercado Libre store.
- Expired or invalid OAuth token.
- Unsupported target site.
- FULL fulfillment selected or inferred.
- Listing type not returned as valid for the selected site/account/category.
- Missing category.
- Missing required category attributes.
- Missing image.
- Missing price, currency, stock, condition, or title.
- AI review decision is "block".
- AI review decision is "needs_human_review" and no operator has approved.
- Brand/IP risk is unresolved.
- Amazon collection status is blocked, incomplete, or challenge-only.

Warnings that require operator acknowledgement:

- Price was collected from Amazon but may include coupon, promotion, shipping, tax, or availability ambiguity.
- Product has medical, safety, cosmetic, battery, trademark, or regulated language.
- Product category confidence is low.
- Variant mapping is incomplete.
- Image quality is low or image source is uncertain.

## 8. API Integration Notes

Mercado Libre:

- Use OAuth authorization code flow.
- Store refresh tokens securely.
- Encapsulate site APIs behind a MercadoLibreClient.
- Fetch valid categories, attributes, listing types, and shipping options dynamically.
- Validate payload before item creation.
- Keep request/response summaries in audit logs without storing secrets.

Amazon:

- Use page collection only in the first version.
- Use throttling, cache, and manual intervention states.
- Avoid API-specific assumptions.
- Keep the collector as a replaceable source adapter so Amazon API, approved data feeds, or supplier spreadsheets can be added later.

Claude:

- Use structured JSON output.
- Prompts must include marketplace-safe review rubrics.
- Store prompt version and model version for audit.

NVIDIA:

- Use NIM-compatible inference behind an abstraction.
- Make model provider configurable.
- Use batch jobs for extraction/classification where possible.

## 9. Suggested Technology Stack

Recommended stack:

- Backend: Python FastAPI.
- Worker: Celery or RQ.
- Frontend: React + Vite.
- Database: PostgreSQL.
- Cache/queue: Redis.
- Browser collector: Playwright.
- ORM/migrations: SQLAlchemy + Alembic.
- Secrets: environment variables for local development, vault-compatible abstraction for production.
- Packaging: Docker Compose for local services.

Reasoning:

- Python is strong for scraping, data normalization, AI orchestration, and marketplace automation.
- FastAPI gives a clean API surface.
- Playwright is a proven browser automation layer.
- PostgreSQL handles audit-heavy workflow data better than a lightweight file database.

## 10. Development Phases

Phase 1: Foundation

- Create monorepo under D:\amazon-meli-publisher.
- Backend, frontend, database, queue, and configuration skeleton.
- Define product draft schema and audit schema.
- Create seed site configuration.

Phase 2: Amazon Page Collector

- Single URL collector.
- Batch URL import.
- Extract title/images/bullets/description/price/variants/specs.
- Cache and failure states.

Phase 3: Mercado Libre Authorization And Metadata

- OAuth flow.
- Store list and token refresh.
- Site/category/listing type metadata fetch.
- Required attribute fetch and validation.

Phase 4: Draft Review Workflow

- Draft editor.
- Category/attribute mapping UI.
- NVIDIA batch suggestions.
- Claude structured review.
- Human approval gate.

Phase 5: Publishing

- Payload builder.
- Non-FULL listing type selection.
- API publish job.
- Publish result tracking.
- Retry and error display.

Phase 6: Hardening

- Role-based permissions.
- Stronger audit logs.
- Batch controls.
- Export reports.
- Monitoring and alerting.

## 11. Testing Strategy

Unit tests:

- Amazon parser normalization.
- Mercado Libre payload builder.
- Listing type/FULL exclusion logic.
- Required attribute validation.
- AI review JSON schema validation.

Integration tests:

- OAuth callback using mocked Mercado Libre responses.
- Category and listing type metadata fetch with recorded fixtures.
- Publish job with mocked API success/failure.
- Collector behavior for normal, missing, blocked, and variant Amazon pages.

End-to-end tests:

- Import URL -> collect -> draft -> AI review -> manual approval -> mocked publish.
- Batch import with partial failures.
- Store authorization expired token refresh path.

Manual acceptance tests:

- Operator can choose site.
- Operator can choose classic/premium when valid.
- Operator cannot choose FULL.
- Operator sees Claude/NVIDIA review before publishing.
- No publish request is sent before human approval.

## 12. Open Decisions Before Implementation

The design can proceed with defaults, but these should be confirmed during implementation planning:

- First target site default: MLM (Mexico), unless user chooses another.
- Whether "pre" means Mercado Libre premium listing mode; the implementation will label it as premium in English UI unless the user prefers "pre".
- Whether the first collector should use the user's interactive browser session or a clean Playwright browser profile.
- Whether local development should use Docker Desktop or native Windows services for PostgreSQL/Redis.
- Which Claude model and NVIDIA model endpoint will be used in production.

## 13. Source References

- Mercado Libre Developers: https://developers.mercadolibre.com/
- Mercado Libre Global Selling product publishing: https://global-selling.mercadolibre.com/devsite/devsite/fully-managed-product-publishing
- Amazon Product Advertising API documentation and migration notice: https://webservices.amazon.com/paapi5/documentation/
- Claude tool use and structured tool workflows: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
- NVIDIA NIM large language model API reference: https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html

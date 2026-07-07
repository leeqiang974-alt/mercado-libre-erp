# Amazon Mercado Libre Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MVP that collects Amazon page data, creates Mercado Libre product drafts, runs AI review gates, and publishes approved listings through a Mercado Libre API abstraction while excluding FULL fulfillment.

**Architecture:** Use a D-drive monorepo with a FastAPI backend, Playwright collector module, SQLAlchemy models, mocked external service adapters by default, and a React/Vite frontend. External systems are isolated behind provider interfaces so Amazon page collection, Claude, NVIDIA NIM, and Mercado Libre API can be tested without live credentials.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Playwright, React, Vite, TypeScript, Redis-ready worker boundaries, PostgreSQL-ready schema with SQLite fallback for local tests.

---

## File Structure

Create this structure under `D:\amazon-meli-publisher`:

```text
backend/
  app/
    main.py
    core/config.py
    core/security.py
    db/base.py
    db/session.py
    models/store.py
    models/source_product.py
    models/product_draft.py
    models/review_result.py
    models/publish_job.py
    models/audit_event.py
    schemas/imports.py
    schemas/drafts.py
    schemas/reviews.py
    schemas/publishing.py
    services/amazon/collector.py
    services/amazon/parser.py
    services/amazon/normalizer.py
    services/ai/review_policy.py
    services/ai/claude_client.py
    services/ai/nvidia_client.py
    services/meli/client.py
    services/meli/metadata.py
    services/meli/payload_builder.py
    services/meli/publisher.py
    api/routes/imports.py
    api/routes/drafts.py
    api/routes/reviews.py
    api/routes/publishing.py
    api/routes/stores.py
  tests/
    test_imports.py
    test_amazon_parser.py
    test_review_policy.py
    test_meli_payload_builder.py
    test_publish_gates.py
  pyproject.toml
  alembic.ini
frontend/
  package.json
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    api/client.ts
    pages/ImportPage.tsx
    pages/DraftsPage.tsx
    pages/DraftDetailPage.tsx
    pages/PublishingPage.tsx
    pages/StoresPage.tsx
    components/Layout.tsx
docs/
  superpowers/specs/2026-07-07-amazon-meli-publisher-design.md
  superpowers/plans/2026-07-07-amazon-meli-publisher-implementation.md
.env.example
.gitignore
README.md
docker-compose.yml
```

## Task 1: Backend Project Skeleton

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/tests/test_health.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Create the backend dependency file**

Create `backend/pyproject.toml`:

```toml
[project]
name = "amazon-meli-publisher-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.7.0",
  "pydantic-settings>=2.3.0",
  "sqlalchemy>=2.0.30",
  "alembic>=1.13.1",
  "httpx>=0.27.0",
  "playwright>=1.44.0",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "pytest-asyncio>=0.23.7",
  "ruff>=0.5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Add backend configuration**

Create `backend/app/core/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Amazon Mercado Libre Publisher"
    database_url: str = "sqlite:///./dev.db"
    meli_client_id: str = ""
    meli_client_secret: str = ""
    meli_redirect_uri: str = "http://localhost:8000/api/stores/meli/callback"
    claude_api_key: str = ""
    nvidia_api_key: str = ""
    default_site_id: str = "MLM"
    allow_live_publish: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Add database session setup**

Create `backend/app/db/session.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Create `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Add FastAPI app and health endpoint**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
```

- [ ] **Step 5: Add the first failing/passing test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 6: Add environment and repo docs**

Create `.env.example`:

```dotenv
DATABASE_URL=sqlite:///./dev.db
MELI_CLIENT_ID=
MELI_CLIENT_SECRET=
MELI_REDIRECT_URI=http://localhost:8000/api/stores/meli/callback
CLAUDE_API_KEY=
NVIDIA_API_KEY=
DEFAULT_SITE_ID=MLM
ALLOW_LIVE_PUBLISH=false
```

Create `.gitignore`:

```gitignore
.env
*.pyc
__pycache__/
.pytest_cache/
.ruff_cache/
backend/dev.db
backend/.venv/
frontend/node_modules/
frontend/dist/
data/
```

Create `README.md`:

```markdown
# Amazon Mercado Libre Publisher

Local-first MVP for collecting Amazon product page data, preparing Mercado Libre drafts, reviewing drafts with Claude/NVIDIA providers, and publishing approved non-FULL listings through Mercado Libre API adapters.

Project root: `D:\amazon-meli-publisher`
```

- [ ] **Step 7: Run backend skeleton tests**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
python -m pip install -e ".[dev]"
pytest tests/test_health.py -v
```

Expected: one passing test.

- [ ] **Step 8: Commit**

```powershell
cd D:\amazon-meli-publisher
git add .env.example .gitignore README.md backend
git commit -m "feat: add backend skeleton"
```

## Task 2: Domain Models And Draft Schema

**Files:**
- Create: `backend/app/models/store.py`
- Create: `backend/app/models/source_product.py`
- Create: `backend/app/models/product_draft.py`
- Create: `backend/app/models/review_result.py`
- Create: `backend/app/models/publish_job.py`
- Create: `backend/app/models/audit_event.py`
- Modify: `backend/app/db/base.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write model smoke tests**

Create `backend/tests/test_models.py`:

```python
from app.models.product_draft import ProductDraft, ProductDraftStatus
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.review_result import ReviewDecision
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.store import Store


def test_domain_models_expose_expected_defaults():
    store = Store(site_id="MLM", seller_id="seller-1", display_name="Demo")
    source = SourceProduct(source_url="https://www.amazon.com/dp/B000TEST")
    draft = ProductDraft(title="Demo", target_site_id="MLM")
    job = PublishJob(product_draft_id=1, store_id=1, requested_by="operator")

    assert store.marketplace == "mercadolibre"
    assert source.raw_status == SourceProductStatus.PENDING
    assert draft.status == ProductDraftStatus.DRAFT
    assert job.status == PublishJobStatus.PENDING
    assert ReviewDecision.NEEDS_HUMAN_REVIEW.value == "needs_human_review"
```

- [ ] **Step 2: Implement store model**

Create `backend/app/models/store.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(40), default="mercadolibre")
    site_id: Mapped[str] = mapped_column(String(8), index=True)
    seller_id: Mapped[str] = mapped_column(String(80), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    oauth_status: Mapped[str] = mapped_column(String(40), default="not_connected")
    token_reference: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 3: Implement source product model**

Create `backend/app/models/source_product.py`:

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceProductStatus(str, Enum):
    PENDING = "pending"
    COLLECTED = "collected"
    NEEDS_MANUAL_ACTION = "needs_manual_action"
    FAILED = "failed"


class SourceProduct(Base):
    __tablename__ = "source_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), default="amazon_page")
    source_url: Mapped[str] = mapped_column(Text)
    asin: Mapped[str] = mapped_column(String(20), default="")
    raw_status: Mapped[SourceProductStatus] = mapped_column(default=SourceProductStatus.PENDING)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collection_error: Mapped[str] = mapped_column(Text, default="")
    raw_snapshot_reference: Mapped[str] = mapped_column(Text, default="")
```

- [ ] **Step 4: Implement draft model**

Create `backend/app/models/product_draft.py`:

```python
from enum import Enum

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductDraftStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class ProductDraft(Base):
    __tablename__ = "product_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_product_id: Mapped[int | None] = mapped_column(ForeignKey("source_products.id"), nullable=True)
    target_site_id: Mapped[str] = mapped_column(String(8), default="MLM")
    target_category_id: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str] = mapped_column(String(120), default="")
    condition: Mapped[str] = mapped_column(String(40), default="new")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    listing_type_id: Mapped[str] = mapped_column(String(40), default="")
    shipping_profile: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[ProductDraftStatus] = mapped_column(default=ProductDraftStatus.DRAFT)
    risk_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
```

- [ ] **Step 5: Implement review, publish, and audit models**

Create `backend/app/models/review_result.py`:

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewDecision(str, Enum):
    PASS = "pass"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    BLOCK = "block"


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(ForeignKey("product_drafts.id"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120), default="")
    risk_level: Mapped[str] = mapped_column(String(40))
    decision: Mapped[ReviewDecision] = mapped_column()
    reasons_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    suggested_changes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Create `backend/app/models/publish_job.py`:

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublishJobStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    PUBLISHED = "published"
    FAILED = "failed"
    BLOCKED = "blocked"


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(ForeignKey("product_drafts.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    requested_by: Mapped[str] = mapped_column(String(120))
    status: Mapped[PublishJobStatus] = mapped_column(default=PublishJobStatus.PENDING)
    request_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    response_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    meli_item_id: Mapped[str] = mapped_column(String(80), default="")
    permalink: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

Create `backend/app/models/audit_event.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    before_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 6: Import models in base module**

Modify `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.audit_event import AuditEvent  # noqa: E402,F401
from app.models.product_draft import ProductDraft  # noqa: E402,F401
from app.models.publish_job import PublishJob  # noqa: E402,F401
from app.models.review_result import ReviewResult  # noqa: E402,F401
from app.models.source_product import SourceProduct  # noqa: E402,F401
from app.models.store import Store  # noqa: E402,F401
```

- [ ] **Step 7: Run model tests**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
pytest tests/test_models.py -v
```

Expected: one passing test.

- [ ] **Step 8: Commit**

```powershell
cd D:\amazon-meli-publisher
git add backend/app/models backend/app/db/base.py backend/tests/test_models.py
git commit -m "feat: add marketplace domain models"
```

## Task 3: Amazon Page Parser And Normalizer

**Files:**
- Create: `backend/app/services/amazon/parser.py`
- Create: `backend/app/services/amazon/normalizer.py`
- Create: `backend/app/schemas/drafts.py`
- Create: `backend/tests/test_amazon_parser.py`

- [ ] **Step 1: Write parser tests**

Create `backend/tests/test_amazon_parser.py`:

```python
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html


HTML = """
<html>
  <span id="productTitle">  Stainless Water Bottle  </span>
  <span class="a-price"><span class="a-offscreen">$19.99</span></span>
  <div id="bylineInfo">Brand: TrailPro</div>
  <div id="feature-bullets"><ul><li>Leak proof lid</li><li>24 oz capacity</li></ul></div>
  <div id="productDescription"><p>Keeps drinks cold.</p></div>
  <img id="landingImage" src="https://example.com/main.jpg" />
  <table id="productDetails_techSpec_section_1">
    <tr><th>Item Weight</th><td>1.2 pounds</td></tr>
  </table>
</html>
"""


def test_parse_amazon_html_extracts_core_fields():
    parsed = parse_amazon_html(HTML, "https://www.amazon.com/dp/B000TEST")
    assert parsed["title"] == "Stainless Water Bottle"
    assert parsed["price"]["amount"] == 19.99
    assert parsed["brand"] == "TrailPro"
    assert parsed["images"] == ["https://example.com/main.jpg"]
    assert "Leak proof lid" in parsed["bullets"]
    assert parsed["technical_details"]["Item Weight"] == "1.2 pounds"


def test_normalize_amazon_product_creates_draft_defaults():
    parsed = parse_amazon_html(HTML, "https://www.amazon.com/dp/B000TEST")
    draft = normalize_amazon_product(parsed, target_site_id="MLM")
    assert draft.title == "Stainless Water Bottle"
    assert draft.target_site_id == "MLM"
    assert draft.currency == "USD"
    assert draft.stock == 1
```

- [ ] **Step 2: Add draft schema**

Create `backend/app/schemas/drafts.py`:

```python
from pydantic import BaseModel, Field


class ProductDraftCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    brand: str = ""
    target_site_id: str = "MLM"
    target_category_id: str = ""
    condition: str = "new"
    price: float | None = None
    currency: str = ""
    stock: int = 0
    listing_type_id: str = ""
    image_urls: list[str] = []
```

- [ ] **Step 3: Implement parser**

Create `backend/app/services/amazon/parser.py`:

```python
import re
from bs4 import BeautifulSoup


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _parse_price(value: str) -> dict:
    match = re.search(r"([A-Z$]*)([0-9]+(?:[.,][0-9]{2})?)", value)
    if not match:
        return {"amount": None, "currency": ""}
    symbol = match.group(1)
    amount = float(match.group(2).replace(",", "."))
    currency = "USD" if "$" in symbol or symbol == "" else symbol
    return {"amount": amount, "currency": currency}


def parse_amazon_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("#productTitle"))
    price = _parse_price(_text(soup.select_one(".a-price .a-offscreen")))
    byline = _text(soup.select_one("#bylineInfo"))
    brand = byline.replace("Brand:", "").replace("Visit the", "").replace("Store", "").strip()
    bullets = [_text(item) for item in soup.select("#feature-bullets li") if _text(item)]
    description = _text(soup.select_one("#productDescription"))
    images = []
    landing = soup.select_one("#landingImage")
    if landing and landing.get("src"):
        images.append(landing["src"])
    technical_details = {}
    for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr"):
        key = _text(row.select_one("th"))
        value = _text(row.select_one("td"))
        if key and value:
            technical_details[key] = value
    return {
        "source_url": source_url,
        "title": title,
        "price": price,
        "brand": brand,
        "bullets": bullets,
        "description": description,
        "images": images,
        "technical_details": technical_details,
    }
```

- [ ] **Step 4: Add BeautifulSoup dependency**

Modify `backend/pyproject.toml` dependencies to include:

```toml
  "beautifulsoup4>=4.12.3",
```

- [ ] **Step 5: Implement normalizer**

Create `backend/app/services/amazon/normalizer.py`:

```python
from app.schemas.drafts import ProductDraftCreate


def normalize_amazon_product(parsed: dict, target_site_id: str) -> ProductDraftCreate:
    description_parts = []
    if parsed.get("description"):
        description_parts.append(parsed["description"])
    if parsed.get("bullets"):
        description_parts.append("\n".join(f"- {bullet}" for bullet in parsed["bullets"]))
    if parsed.get("technical_details"):
        description_parts.append(
            "\n".join(f"{key}: {value}" for key, value in parsed["technical_details"].items())
        )
    price = parsed.get("price", {})
    return ProductDraftCreate(
        title=parsed.get("title", ""),
        description="\n\n".join(description_parts),
        brand=parsed.get("brand", ""),
        target_site_id=target_site_id,
        price=price.get("amount"),
        currency=price.get("currency", ""),
        stock=1,
        image_urls=parsed.get("images", []),
    )
```

- [ ] **Step 6: Run parser tests**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
python -m pip install -e ".[dev]"
pytest tests/test_amazon_parser.py -v
```

Expected: two passing tests.

- [ ] **Step 7: Commit**

```powershell
cd D:\amazon-meli-publisher
git add backend/pyproject.toml backend/app/schemas/drafts.py backend/app/services/amazon backend/tests/test_amazon_parser.py
git commit -m "feat: parse and normalize Amazon pages"
```

## Task 4: Review Policy And AI Provider Stubs

**Files:**
- Create: `backend/app/schemas/reviews.py`
- Create: `backend/app/services/ai/review_policy.py`
- Create: `backend/app/services/ai/claude_client.py`
- Create: `backend/app/services/ai/nvidia_client.py`
- Create: `backend/tests/test_review_policy.py`

- [ ] **Step 1: Write review tests**

Create `backend/tests/test_review_policy.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.services.ai.review_policy import review_draft_locally


def test_review_blocks_missing_required_publish_fields():
    draft = ProductDraftCreate(title="", target_site_id="MLM", stock=0)
    result = review_draft_locally(draft)
    assert result.decision == "block"
    assert "missing_title" in result.reason_codes


def test_review_requires_human_for_sensitive_claims():
    draft = ProductDraftCreate(
        title="Pain cure supplement",
        description="This product cures pain and treats disease.",
        target_site_id="MLM",
        price=10,
        currency="USD",
        stock=1,
        image_urls=["https://example.com/a.jpg"],
    )
    result = review_draft_locally(draft)
    assert result.decision == "needs_human_review"
    assert "regulated_claim" in result.reason_codes


def test_review_passes_basic_complete_draft():
    draft = ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof water bottle.",
        target_site_id="MLM",
        price=19.99,
        currency="USD",
        stock=2,
        image_urls=["https://example.com/a.jpg"],
    )
    result = review_draft_locally(draft)
    assert result.decision == "pass"
```

- [ ] **Step 2: Add review schema**

Create `backend/app/schemas/reviews.py`:

```python
from pydantic import BaseModel


class ReviewResponse(BaseModel):
    provider: str
    decision: str
    risk_level: str
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = {}
```

- [ ] **Step 3: Implement local policy**

Create `backend/app/services/ai/review_policy.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse


SENSITIVE_TERMS = ["cure", "treats disease", "guaranteed", "official brand", "replica"]


def review_draft_locally(draft: ProductDraftCreate) -> ReviewResponse:
    reason_codes: list[str] = []
    reasons: list[str] = []
    if not draft.title.strip():
        reason_codes.append("missing_title")
        reasons.append("Title is required before publishing.")
    if not draft.price:
        reason_codes.append("missing_price")
        reasons.append("Price is required before publishing.")
    if not draft.currency:
        reason_codes.append("missing_currency")
        reasons.append("Currency is required before publishing.")
    if draft.stock < 1:
        reason_codes.append("missing_stock")
        reasons.append("Stock must be at least 1 before publishing.")
    if not draft.image_urls:
        reason_codes.append("missing_image")
        reasons.append("At least one image is required before publishing.")
    text = f"{draft.title} {draft.description}".lower()
    if any(term in text for term in SENSITIVE_TERMS):
        reason_codes.append("regulated_claim")
        reasons.append("Draft contains claims or brand language that require human review.")
    if any(code.startswith("missing_") for code in reason_codes):
        decision = "block"
        risk_level = "high"
    elif reason_codes:
        decision = "needs_human_review"
        risk_level = "medium"
    else:
        decision = "pass"
        risk_level = "low"
    return ReviewResponse(
        provider="local_policy",
        decision=decision,
        risk_level=risk_level,
        reason_codes=reason_codes,
        reasons=reasons,
        suggested_changes={},
    )
```

- [ ] **Step 4: Add Claude and NVIDIA adapter stubs**

Create `backend/app/services/ai/claude_client.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.review_policy import review_draft_locally


class ClaudeReviewClient:
    def review_draft(self, draft: ProductDraftCreate) -> ReviewResponse:
        result = review_draft_locally(draft)
        return result.model_copy(update={"provider": "claude_stub"})
```

Create `backend/app/services/ai/nvidia_client.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.review_policy import review_draft_locally


class NvidiaReviewClient:
    def pre_screen_draft(self, draft: ProductDraftCreate) -> ReviewResponse:
        result = review_draft_locally(draft)
        return result.model_copy(update={"provider": "nvidia_stub"})
```

- [ ] **Step 5: Run review tests**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
pytest tests/test_review_policy.py -v
```

Expected: three passing tests.

- [ ] **Step 6: Commit**

```powershell
cd D:\amazon-meli-publisher
git add backend/app/schemas/reviews.py backend/app/services/ai backend/tests/test_review_policy.py
git commit -m "feat: add AI review policy gates"
```

## Task 5: Mercado Libre Payload Builder And FULL Exclusion

**Files:**
- Create: `backend/app/schemas/publishing.py`
- Create: `backend/app/services/meli/payload_builder.py`
- Create: `backend/tests/test_meli_payload_builder.py`

- [ ] **Step 1: Write payload builder tests**

Create `backend/tests/test_meli_payload_builder.py`:

```python
import pytest

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.meli.payload_builder import build_item_payload


def complete_draft():
    return ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof bottle.",
        target_site_id="MLM",
        target_category_id="MLM123",
        price=19.99,
        currency="USD",
        stock=3,
        listing_type_id="gold_special",
        image_urls=["https://example.com/a.jpg"],
    )


def test_build_item_payload_maps_required_fields():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special", fulfillment="not_full"),
    )
    assert payload["title"] == "Stainless Water Bottle"
    assert payload["listing_type_id"] == "gold_special"
    assert payload["available_quantity"] == 3
    assert payload["pictures"][0]["source"] == "https://example.com/a.jpg"


def test_build_item_payload_rejects_full_fulfillment():
    with pytest.raises(ValueError, match="FULL fulfillment is excluded"):
        build_item_payload(
            draft=complete_draft(),
            listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special", fulfillment="full"),
        )
```

- [ ] **Step 2: Add publishing schema**

Create `backend/app/schemas/publishing.py`:

```python
from pydantic import BaseModel


class ListingChoice(BaseModel):
    site_id: str
    listing_type_id: str
    fulfillment: str = "not_full"


class PublishValidationResult(BaseModel):
    allowed: bool
    errors: list[str]
```

- [ ] **Step 3: Implement payload builder**

Create `backend/app/services/meli/payload_builder.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice


def build_item_payload(draft: ProductDraftCreate, listing_choice: ListingChoice) -> dict:
    if listing_choice.fulfillment.lower() == "full":
        raise ValueError("FULL fulfillment is excluded from this system.")
    if listing_choice.site_id != draft.target_site_id:
        raise ValueError("Listing choice site must match draft target site.")
    if not listing_choice.listing_type_id:
        raise ValueError("Listing type is required.")
    return {
        "site_id": draft.target_site_id,
        "title": draft.title,
        "category_id": draft.target_category_id,
        "price": draft.price,
        "currency_id": draft.currency,
        "available_quantity": draft.stock,
        "buying_mode": "buy_it_now",
        "condition": draft.condition,
        "listing_type_id": listing_choice.listing_type_id,
        "description": {"plain_text": draft.description},
        "pictures": [{"source": url} for url in draft.image_urls],
    }
```

- [ ] **Step 4: Run payload tests**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
pytest tests/test_meli_payload_builder.py -v
```

Expected: two passing tests.

- [ ] **Step 5: Commit**

```powershell
cd D:\amazon-meli-publisher
git add backend/app/schemas/publishing.py backend/app/services/meli/payload_builder.py backend/tests/test_meli_payload_builder.py
git commit -m "feat: build non-full Mercado Libre payloads"
```

## Task 6: Publish Gates And Mercado Libre Client Adapter

**Files:**
- Create: `backend/app/services/meli/client.py`
- Create: `backend/app/services/meli/metadata.py`
- Create: `backend/app/services/meli/publisher.py`
- Create: `backend/tests/test_publish_gates.py`

- [ ] **Step 1: Write publishing gate tests**

Create `backend/tests/test_publish_gates.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.ai.review_policy import review_draft_locally
from app.services.meli.publisher import validate_publish_request


def valid_draft():
    return ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof bottle.",
        target_site_id="MLM",
        target_category_id="MLM123",
        price=19.99,
        currency="USD",
        stock=3,
        image_urls=["https://example.com/a.jpg"],
    )


def test_publish_gate_allows_reviewed_classic_listing():
    result = validate_publish_request(
        draft=valid_draft(),
        review=review_draft_locally(valid_draft()),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special", fulfillment="not_full"),
        valid_listing_type_ids=["gold_special", "gold_pro"],
        human_approved=True,
    )
    assert result.allowed is True
    assert result.errors == []


def test_publish_gate_blocks_invalid_listing_type():
    result = validate_publish_request(
        draft=valid_draft(),
        review=review_draft_locally(valid_draft()),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_full", fulfillment="not_full"),
        valid_listing_type_ids=["gold_special", "gold_pro"],
        human_approved=True,
    )
    assert result.allowed is False
    assert "listing_type_not_available" in result.errors


def test_publish_gate_blocks_without_human_approval():
    result = validate_publish_request(
        draft=valid_draft(),
        review=review_draft_locally(valid_draft()),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special", fulfillment="not_full"),
        valid_listing_type_ids=["gold_special"],
        human_approved=False,
    )
    assert result.allowed is False
    assert "human_approval_required" in result.errors
```

- [ ] **Step 2: Implement Mercado Libre client**

Create `backend/app/services/meli/client.py`:

```python
import httpx


class MercadoLibreClient:
    def __init__(self, access_token: str = "", base_url: str = "https://api.mercadolibre.com"):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
```

- [ ] **Step 3: Implement metadata helper**

Create `backend/app/services/meli/metadata.py`:

```python
from app.services.meli.client import MercadoLibreClient


async def fetch_listing_type_ids(client: MercadoLibreClient, site_id: str) -> list[str]:
    data = await client.get(f"/sites/{site_id}/listing_types")
    return [item["id"] for item in data if item.get("id")]
```

- [ ] **Step 4: Implement publisher validation**

Create `backend/app/services/meli/publisher.py`:

```python
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.payload_builder import build_item_payload


def validate_publish_request(
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
    valid_listing_type_ids: list[str],
    human_approved: bool,
) -> PublishValidationResult:
    errors: list[str] = []
    if not human_approved:
        errors.append("human_approval_required")
    if listing_choice.fulfillment.lower() == "full":
        errors.append("full_fulfillment_excluded")
    if listing_choice.listing_type_id not in valid_listing_type_ids:
        errors.append("listing_type_not_available")
    if review.decision == "block":
        errors.append("ai_review_blocked")
    if review.decision == "needs_human_review" and not human_approved:
        errors.append("ai_review_needs_human_review")
    try:
        build_item_payload(draft, listing_choice)
    except ValueError as exc:
        errors.append(str(exc))
    return PublishValidationResult(allowed=not errors, errors=errors)
```

- [ ] **Step 5: Run publishing gate tests**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
pytest tests/test_publish_gates.py -v
```

Expected: three passing tests.

- [ ] **Step 6: Commit**

```powershell
cd D:\amazon-meli-publisher
git add backend/app/services/meli backend/tests/test_publish_gates.py
git commit -m "feat: enforce Mercado Libre publishing gates"
```

## Task 7: API Routes For Import, Review, And Publish Preview

**Files:**
- Create: `backend/app/api/routes/imports.py`
- Create: `backend/app/api/routes/reviews.py`
- Create: `backend/app/api/routes/publishing.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_flow.py`

- [ ] **Step 1: Write API flow tests**

Create `backend/tests/test_api_flow.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_import_review_publish_preview_flow():
    client = TestClient(app)
    imported = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST",
            "html": "<span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
            "target_site_id": "MLM",
        },
    )
    assert imported.status_code == 200
    draft = imported.json()
    assert draft["title"] == "Bottle"

    reviewed = client.post("/api/reviews/local", json=draft)
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "pass"

    preview = client.post(
        "/api/publishing/preview",
        json={
            "draft": draft,
            "review": reviewed.json(),
            "listing_choice": {"site_id": "MLM", "listing_type_id": "gold_special", "fulfillment": "not_full"},
            "valid_listing_type_ids": ["gold_special", "gold_pro"],
            "human_approved": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["allowed"] is True
```

- [ ] **Step 2: Add import route**

Create `backend/app/api/routes/imports.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html

router = APIRouter(prefix="/api/imports", tags=["imports"])


class AmazonHtmlImport(BaseModel):
    source_url: str
    html: str
    target_site_id: str = "MLM"


@router.post("/amazon-html", response_model=ProductDraftCreate)
def import_amazon_html(payload: AmazonHtmlImport) -> ProductDraftCreate:
    parsed = parse_amazon_html(payload.html, payload.source_url)
    return normalize_amazon_product(parsed, payload.target_site_id)
```

- [ ] **Step 3: Add review route**

Create `backend/app/api/routes/reviews.py`:

```python
from fastapi import APIRouter

from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.review_policy import review_draft_locally

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/local", response_model=ReviewResponse)
def review_local(draft: ProductDraftCreate) -> ReviewResponse:
    return review_draft_locally(draft)
```

- [ ] **Step 4: Add publishing preview route**

Create `backend/app/api/routes/publishing.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.publisher import validate_publish_request

router = APIRouter(prefix="/api/publishing", tags=["publishing"])


class PublishPreviewRequest(BaseModel):
    draft: ProductDraftCreate
    review: ReviewResponse
    listing_choice: ListingChoice
    valid_listing_type_ids: list[str]
    human_approved: bool


@router.post("/preview", response_model=PublishValidationResult)
def publish_preview(payload: PublishPreviewRequest) -> PublishValidationResult:
    return validate_publish_request(
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=payload.valid_listing_type_ids,
        human_approved=payload.human_approved,
    )
```

- [ ] **Step 5: Register routes**

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes import imports, publishing, reviews
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(imports.router)
app.include_router(reviews.router)
app.include_router(publishing.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
```

- [ ] **Step 6: Run API flow test**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
pytest tests/test_api_flow.py -v
```

Expected: one passing test.

- [ ] **Step 7: Commit**

```powershell
cd D:\amazon-meli-publisher
git add backend/app/api backend/app/main.py backend/tests/test_api_flow.py
git commit -m "feat: expose import review publish preview APIs"
```

## Task 8: Frontend MVP

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/pages/ImportPage.tsx`
- Create: `frontend/src/pages/DraftsPage.tsx`
- Create: `frontend/src/pages/PublishingPage.tsx`

- [ ] **Step 1: Create frontend package**

Create `frontend/package.json`:

```json
{
  "name": "amazon-meli-publisher-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "vite": "^5.3.0",
    "typescript": "^5.5.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0"
  }
}
```

- [ ] **Step 2: Create TypeScript config, HTML, and React entry**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

Create `frontend/index.html`:

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 3: Add API client**

Create `frontend/src/api/client.ts`:

```ts
const API_BASE = "http://127.0.0.1:8000";

export type ProductDraft = {
  title: string;
  description: string;
  brand: string;
  target_site_id: string;
  target_category_id: string;
  condition: string;
  price: number | null;
  currency: string;
  stock: number;
  listing_type_id: string;
  image_urls: string[];
};

export async function importAmazonHtml(sourceUrl: string, html: string, targetSiteId: string) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-html`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, html, target_site_id: targetSiteId }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraft>;
}

export async function reviewDraft(draft: ProductDraft) {
  const response = await fetch(`${API_BASE}/api/reviews/local`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
```

- [ ] **Step 4: Add app shell**

Create `frontend/src/App.tsx`:

```tsx
import { useState } from "react";
import { Layout } from "./components/Layout";
import { ImportPage } from "./pages/ImportPage";
import { DraftsPage } from "./pages/DraftsPage";
import { PublishingPage } from "./pages/PublishingPage";
import type { ProductDraft } from "./api/client";

export function App() {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [review, setReview] = useState<any>(null);
  const [page, setPage] = useState("import");

  return (
    <Layout page={page} onPageChange={setPage}>
      {page === "import" && <ImportPage onDraft={setDraft} onReview={setReview} />}
      {page === "drafts" && <DraftsPage draft={draft} review={review} />}
      {page === "publishing" && <PublishingPage draft={draft} review={review} />}
    </Layout>
  );
}
```

Create `frontend/src/components/Layout.tsx`:

```tsx
import { Upload, FileText, Send } from "lucide-react";

const tabs = [
  { id: "import", label: "Import", icon: Upload },
  { id: "drafts", label: "Drafts", icon: FileText },
  { id: "publishing", label: "Publish", icon: Send },
];

export function Layout({ page, onPageChange, children }: { page: string; onPageChange: (page: string) => void; children: React.ReactNode }) {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Amazon Meli</h1>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button className={page === tab.id ? "active" : ""} key={tab.id} onClick={() => onPageChange(tab.id)} title={tab.label}>
              <Icon size={18} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </aside>
      <main>{children}</main>
    </div>
  );
}
```

- [ ] **Step 5: Add pages**

Create `frontend/src/pages/ImportPage.tsx`:

```tsx
import { useState } from "react";
import { importAmazonHtml, reviewDraft, type ProductDraft } from "../api/client";

export function ImportPage({ onDraft, onReview }: { onDraft: (draft: ProductDraft) => void; onReview: (review: any) => void }) {
  const [sourceUrl, setSourceUrl] = useState("https://www.amazon.com/dp/B000TEST");
  const [targetSiteId, setTargetSiteId] = useState("MLM");
  const [html, setHtml] = useState("<span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />");
  const [status, setStatus] = useState("");

  async function runImport() {
    setStatus("Importing");
    const draft = await importAmazonHtml(sourceUrl, html, targetSiteId);
    const review = await reviewDraft(draft);
    onDraft(draft);
    onReview(review);
    setStatus(`Draft ready: ${review.decision}`);
  }

  return (
    <section className="panel">
      <h2>Amazon Page Import</h2>
      <label>Source URL<input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></label>
      <label>Site<input value={targetSiteId} onChange={(event) => setTargetSiteId(event.target.value)} /></label>
      <label>HTML Snapshot<textarea value={html} onChange={(event) => setHtml(event.target.value)} /></label>
      <button onClick={runImport}>Import and Review</button>
      <p>{status}</p>
    </section>
  );
}
```

Create `frontend/src/pages/DraftsPage.tsx`:

```tsx
export function DraftsPage({ draft, review }: { draft: any; review: any }) {
  return (
    <section className="panel">
      <h2>Draft Review</h2>
      {!draft && <p>No draft imported yet.</p>}
      {draft && <pre>{JSON.stringify({ draft, review }, null, 2)}</pre>}
    </section>
  );
}
```

Create `frontend/src/pages/PublishingPage.tsx`:

```tsx
export function PublishingPage({ draft, review }: { draft: any; review: any }) {
  const ready = draft && review?.decision === "pass";
  return (
    <section className="panel">
      <h2>Publish Queue</h2>
      <p>{ready ? "Ready for non-FULL Mercado Libre publish preview." : "Import and pass review before publishing."}</p>
      <button disabled={!ready}>Create Publish Preview</button>
    </section>
  );
}
```

- [ ] **Step 6: Add CSS**

Create `frontend/src/style.css`:

```css
body {
  margin: 0;
  font-family: Inter, Segoe UI, Arial, sans-serif;
  background: #f6f7f9;
  color: #1f2933;
}
.app {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}
.sidebar {
  background: #111827;
  color: white;
  padding: 20px;
}
.sidebar h1 {
  font-size: 20px;
  margin: 0 0 24px;
}
.sidebar button {
  width: 100%;
  display: flex;
  gap: 10px;
  align-items: center;
  border: 0;
  border-radius: 6px;
  padding: 10px;
  color: white;
  background: transparent;
  cursor: pointer;
}
.sidebar button.active {
  background: #2563eb;
}
main {
  padding: 24px;
}
.panel {
  max-width: 980px;
}
label {
  display: grid;
  gap: 6px;
  margin: 14px 0;
  font-weight: 600;
}
input,
textarea {
  border: 1px solid #ccd2da;
  border-radius: 6px;
  padding: 10px;
  font: inherit;
}
textarea {
  min-height: 160px;
}
button {
  border: 0;
  border-radius: 6px;
  padding: 10px 14px;
  background: #2563eb;
  color: white;
  cursor: pointer;
}
button:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
pre {
  background: white;
  border: 1px solid #dde3ea;
  border-radius: 6px;
  padding: 16px;
  overflow: auto;
}
```

- [ ] **Step 7: Build frontend**

Run:

```powershell
cd D:\amazon-meli-publisher\frontend
npm install
npm run build
```

Expected: Vite build completes and creates `frontend/dist`.

- [ ] **Step 8: Commit**

```powershell
cd D:\amazon-meli-publisher
git add frontend
git commit -m "feat: add frontend MVP shell"
```

## Task 9: Docker Compose And Local Runbook

**Files:**
- Create: `docker-compose.yml`
- Modify: `README.md`

- [ ] **Step 1: Add Docker Compose**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: meli
      POSTGRES_PASSWORD: meli
      POSTGRES_DB: amazon_meli
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

- [ ] **Step 2: Expand README**

Modify `README.md`:

```markdown
# Amazon Mercado Libre Publisher

Local-first MVP for collecting Amazon product page data, preparing Mercado Libre drafts, reviewing drafts with Claude/NVIDIA providers, and publishing approved non-FULL listings through Mercado Libre API adapters.

Project root: `D:\amazon-meli-publisher`

## Local Backend

```powershell
cd D:\amazon-meli-publisher\backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Health check: `http://127.0.0.1:8000/health`

## Local Frontend

```powershell
cd D:\amazon-meli-publisher\frontend
npm install
npm run dev
```

Frontend: `http://127.0.0.1:5173`

## Local Services

```powershell
cd D:\amazon-meli-publisher
docker compose up -d
```

## Safety Rules

- Amazon collection starts from user-provided pages or HTML snapshots.
- Mercado Libre FULL fulfillment is excluded.
- AI providers never receive Mercado Libre tokens.
- No publish request is sent unless a human approval flag is present.
```

- [ ] **Step 3: Commit**

```powershell
cd D:\amazon-meli-publisher
git add docker-compose.yml README.md
git commit -m "docs: add local runbook"
```

## Task 10: Final Verification For MVP Skeleton

**Files:**
- No new files.
- Verify all created files.

- [ ] **Step 1: Run backend test suite**

Run:

```powershell
cd D:\amazon-meli-publisher\backend
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd D:\amazon-meli-publisher\frontend
npm run build
```

Expected: Vite build succeeds.

- [ ] **Step 3: Confirm git state**

Run:

```powershell
cd D:\amazon-meli-publisher
git status --short
```

Expected: no output.

- [ ] **Step 4: Record MVP status**

Create `docs/mvp-status.md`:

```markdown
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
```

- [ ] **Step 5: Commit final status**

```powershell
cd D:\amazon-meli-publisher
git add docs/mvp-status.md
git commit -m "docs: record MVP skeleton verification scope"
```

## Self-Review Notes

- Spec coverage: The plan covers Amazon page/HTML collection, normalized drafts, AI review gates, Mercado Libre non-FULL listing type validation, human approval, frontend review flow, and local runbook.
- Intentional MVP boundary: Live OAuth, live item creation, Playwright browsing, PostgreSQL migrations, Claude live API, and NVIDIA live API are isolated behind interfaces and listed as the next production phase. This keeps the first implementation testable without credentials while moving directly toward the requested system.
- Safety coverage: FULL fulfillment is blocked in the payload builder and publish gate. AI providers are stubs/adapters and never receive Mercado Libre credentials. Publishing preview requires human approval.

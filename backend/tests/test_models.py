from app.models.product_draft import ProductDraft, ProductDraftStatus
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.review_result import ReviewDecision
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.store import Store
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_domain_models_expose_expected_defaults():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    store = Store(site_id="MLM", seller_id="seller-1", display_name="Demo")
    source = SourceProduct(source_url="https://www.amazon.com/dp/B000TEST01")
    draft = ProductDraft(title="Demo", target_site_id="MLM")
    job = PublishJob(product_draft_id=1, store_id=1, requested_by="operator")

    with Session(engine) as session:
        session.add_all([store, source, draft, job])
        session.flush()

    assert store.marketplace == "mercadolibre"
    assert source.raw_status == SourceProductStatus.PENDING
    assert draft.status == ProductDraftStatus.DRAFT
    assert job.status == PublishJobStatus.PENDING
    assert ReviewDecision.NEEDS_HUMAN_REVIEW.value == "needs_human_review"

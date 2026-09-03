from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft import ProductDraft
from app.models.registry import import_all_models
from app.schemas.draft_category import DraftCategoryUpdate
from app.services.draft_categories import confirm_draft_category
from app.services.meli.metadata_cache import category_details_key


def test_category_confirmation_uses_current_locked_draft_after_background_version_bump():
    """A cached category click must not fail because collection changed media first."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with session_factory() as db:
        draft = ProductDraft(title="Cable organizer", target_site_id="CBT", content_version=2)
        db.add(draft)
        db.add(
            MeliMetadataCache(
                cache_key=category_details_key("CBT123"),
                payload_json={"verified": True, "leaf": True},
            )
        )
        db.commit()

        updated, _, _ = confirm_draft_category(
            db,
            draft.id,
            DraftCategoryUpdate(
                # This is intentionally stale: the page loaded before a background
                # collector/normalizer incremented the content version.
                expected_content_version=1,
                target_site_id="CBT",
                category_id="CBT123",
            ),
        )

        assert updated.target_category_id == "CBT123"
        assert updated.content_version == 3

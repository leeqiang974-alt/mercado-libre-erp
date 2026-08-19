from sqlalchemy.dialects import postgresql

from app.models.collection_job import CollectionJob


def test_collection_status_does_not_compile_as_postgresql_native_enum():
    statement = CollectionJob.__table__.insert().values(
        source_url="https://amazon.com/dp/B000TEST01",
        target_site_id="MLM",
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "::collectionjobstatus" not in compiled

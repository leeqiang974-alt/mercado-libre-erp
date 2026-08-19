from sqlalchemy.dialects import postgresql

from app.models.collection_job import CollectionJob, CollectionJobStatus


def test_collection_status_does_not_compile_as_postgresql_native_enum():
    statement = CollectionJob.__table__.insert().values(
        source_url="https://amazon.com/dp/B000TEST01",
        target_site_id="MLM",
        status=CollectionJobStatus.PENDING,
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "::collectionjobstatus" not in compiled


def test_collection_status_type_accepts_legacy_uppercase_values():
    column = CollectionJob.__table__.c.status.type
    assert column.process_result_value("NEEDS_MANUAL_ACTION", None) == CollectionJobStatus.NEEDS_MANUAL_ACTION
    assert column.process_bind_param(CollectionJobStatus.PENDING, None) == "pending"

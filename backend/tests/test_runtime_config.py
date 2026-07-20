import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_live_publish_requires_postgresql_locking():
    with pytest.raises(ValidationError, match="Live publishing requires PostgreSQL"):
        Settings(database_url="sqlite:///./dev.db", allow_live_publish=True)


def test_job_timeout_must_finish_before_stale_recovery():
    with pytest.raises(ValidationError, match="timeout must be shorter"):
        Settings(job_execution_timeout_seconds=900, job_stale_after_seconds=900)

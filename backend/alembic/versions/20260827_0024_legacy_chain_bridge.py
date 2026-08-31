"""Compatibility bridge for an existing production alembic marker.

An earlier server deployment recorded ``20260827_0024`` but the corresponding
source revision is no longer present in the repository. Production already
has the schema it represented, so this no-op bridge lets Alembic load the
existing marker and continue from the current extension-claim migration.
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260827_0024"
down_revision: str | None = "20260831_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The legacy schema was already applied on the production database.
    pass


def downgrade() -> None:
    pass

"""Initial revision for Auto-DJ schema tracking."""
from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Baseline revision does not create objects; tables are managed via metadata."""
    pass


def downgrade() -> None:
    pass

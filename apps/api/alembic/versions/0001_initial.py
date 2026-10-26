"""Initial integrity platform schema."""
from alembic import op
from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    op.execute("INSERT INTO audit_head (id, head_hash, sequence_number) VALUES (1, repeat('0', 64), 0) ON CONFLICT (id) DO NOTHING")


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

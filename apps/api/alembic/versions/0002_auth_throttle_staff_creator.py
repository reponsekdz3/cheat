"""Add persistent login throttling and staff review separation."""
from alembic import op

revision = "0002_auth_throttle_staff_creator"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS supports both installations that already used the early dynamic
    # baseline and clean installs where that baseline created these objects already.
    op.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id UUID PRIMARY KEY,
            email_key VARCHAR(64) NOT NULL,
            ip_key VARCHAR(64) NOT NULL,
            succeeded BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_login_attempt_email_created ON login_attempts (email_key, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_login_attempt_ip_created ON login_attempts (ip_key, created_at)")
    op.execute("""
        ALTER TABLE staff_members
        ADD COLUMN IF NOT EXISTS created_by UUID NULL REFERENCES users(id)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE staff_members DROP COLUMN IF EXISTS created_by")
    op.execute("DROP TABLE IF EXISTS login_attempts")

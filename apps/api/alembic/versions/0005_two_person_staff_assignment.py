"""Require a separate reviewer for each new staff assignment."""
from alembic import op

revision = "0005_two_person_staff_assignment"
down_revision = "0004_candidate_password_rotation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE staff_assignments
        ADD COLUMN IF NOT EXISTS created_by UUID NULL REFERENCES users(id)
    """)
    op.execute("""
        ALTER TABLE staff_assignments
        ADD COLUMN IF NOT EXISTS reviewed_by UUID NULL REFERENCES users(id)
    """)
    op.execute("""
        ALTER TABLE staff_assignments
        ADD COLUMN IF NOT EXISTS status VARCHAR(24) NOT NULL DEFAULT 'APPROVED'
    """)
    op.execute("""
        ALTER TABLE staff_assignments
        ADD COLUMN IF NOT EXISTS approval_note VARCHAR(500)
    """)
    op.execute("""
        ALTER TABLE staff_assignments
        ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ
    """)
    op.execute("ALTER TABLE staff_assignments ALTER COLUMN approved_by DROP NOT NULL")
    op.execute("UPDATE staff_assignments SET created_by = approved_by WHERE created_by IS NULL")
    op.execute("ALTER TABLE staff_assignments ALTER COLUMN created_by SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE staff_assignments ALTER COLUMN approved_by SET NOT NULL")
    op.execute("ALTER TABLE staff_assignments DROP COLUMN IF EXISTS reviewed_at")
    op.execute("ALTER TABLE staff_assignments DROP COLUMN IF EXISTS approval_note")
    op.execute("ALTER TABLE staff_assignments DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE staff_assignments DROP COLUMN IF EXISTS reviewed_by")
    op.execute("ALTER TABLE staff_assignments DROP COLUMN IF EXISTS created_by")

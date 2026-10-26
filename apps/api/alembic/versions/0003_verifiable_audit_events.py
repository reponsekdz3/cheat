"""Add sequence numbering and payload-verifiable audit events."""
from alembic import op
from sqlalchemy import text

revision = "0003_verifiable_audit_events"
down_revision = "0002_auth_throttle_staff_creator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE audit_head
        ADD COLUMN IF NOT EXISTS sequence_number INTEGER NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE audit_events
        ADD COLUMN IF NOT EXISTS sequence_number INTEGER
    """)
    op.execute("""
        ALTER TABLE audit_events
        ADD COLUMN IF NOT EXISTS hash_version INTEGER NOT NULL DEFAULT 1
    """)

    # Preserve order using the hash links themselves, not potentially tied timestamps.
    connection = op.get_bind()
    rows = connection.execute(text(
        "SELECT id, previous_hash, event_hash FROM audit_events"
    )).mappings().all()
    by_previous: dict[str, dict] = {}
    for row in rows:
        prior = row["previous_hash"]
        if prior in by_previous:
            raise RuntimeError("Audit chain contains a fork; migration stopped for manual investigation")
        by_previous[prior] = dict(row)

    previous = "0" * 64
    sequence = 0
    visited: set[str] = set()
    while previous in by_previous:
        row = by_previous[previous]
        event_id = str(row["id"])
        if event_id in visited:
            raise RuntimeError("Audit chain contains a cycle; migration stopped for manual investigation")
        sequence += 1
        connection.execute(
            text("UPDATE audit_events SET sequence_number = :seq WHERE id = :event_id"),
            {"seq": sequence, "event_id": row["id"]},
        )
        visited.add(event_id)
        previous = row["event_hash"]

    if len(visited) != len(rows):
        raise RuntimeError("Audit chain has orphaned entries; migration stopped without reordering history")

    op.execute("ALTER TABLE audit_events ALTER COLUMN sequence_number SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_audit_events_sequence_number ON audit_events (sequence_number)")
    op.execute("""
        UPDATE audit_head
        SET sequence_number = COALESCE((SELECT MAX(sequence_number) FROM audit_events), 0)
        WHERE id = 1
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_events_sequence_number")
    op.execute("ALTER TABLE audit_events DROP COLUMN IF EXISTS hash_version")
    op.execute("ALTER TABLE audit_events DROP COLUMN IF EXISTS sequence_number")
    op.execute("ALTER TABLE audit_head DROP COLUMN IF EXISTS sequence_number")

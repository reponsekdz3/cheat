from app.audit import _event_hash, _event_payload, order_custody_events
from app.models import AuditEvent, AuditHead, LoginAttempt


def test_audit_payload_hash_is_deterministic_and_detects_tampering():
    payload = _event_payload(
        sequence_number=1,
        actor_user_id="actor-1",
        action="test.action",
        entity_type="test",
        entity_id="1",
        detail={"state": "original"},
        occurred_at="2026-10-26T10:00:00+00:00",
        previous_hash="0" * 64,
    )
    first = _event_hash(payload)
    assert first == _event_hash(dict(payload))
    altered = dict(payload)
    altered["detail"] = {"state": "changed"}
    assert first != _event_hash(altered)


def test_audit_schema_has_monotonic_sequence_and_hash_version():
    assert "sequence_number" in AuditHead.__table__.columns
    assert "sequence_number" in AuditEvent.__table__.columns
    assert "hash_version" in AuditEvent.__table__.columns


def test_login_attempt_does_not_store_raw_email_or_ip():
    columns = set(LoginAttempt.__table__.columns.keys())
    assert {"email_key", "ip_key", "succeeded", "created_at"}.issubset(columns)
    assert "email" not in columns and "ip_address" not in columns


def test_custody_chain_orders_by_predecessor_not_timestamp():
    zero = "0" * 64

    class Event:
        def __init__(self, previous_hash, event_hash, name):
            self.previous_hash = previous_hash
            self.event_hash = event_hash
            self.name = name

    second = Event("first", "second", "second")
    first = Event(zero, "first", "first")
    ordered, valid = order_custody_events([second, first])
    assert valid
    assert [event.name for event in ordered] == ["first", "second"]

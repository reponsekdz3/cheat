import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, AuditHead, User


def _event_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event_payload(
    *, sequence_number: int, actor_user_id: str | None, action: str,
    entity_type: str, entity_id: str, detail: dict[str, Any],
    occurred_at: str, previous_hash: str,
) -> dict[str, Any]:
    return {
        "sequence_number": sequence_number,
        "actor_user_id": actor_user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "detail": detail,
        "occurred_at": occurred_at,
        "previous_hash": previous_hash,
    }


async def append_audit(
    session: AsyncSession,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    # Lock the single chain head so concurrent writers cannot fork the sequence.
    head = await session.scalar(select(AuditHead).where(AuditHead.id == 1).with_for_update())
    if head is None:
        raise HTTPException(status_code=503, detail="Audit chain is not initialized")
    safe_detail = detail or {}
    occurred = datetime.now(timezone.utc)
    sequence = head.sequence_number + 1
    payload = _event_payload(
        sequence_number=sequence,
        actor_user_id=str(actor.id) if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=safe_detail,
        occurred_at=occurred.isoformat(),
        previous_hash=head.head_hash,
    )
    event_hash = _event_hash(payload)
    event = AuditEvent(
        sequence_number=sequence,
        hash_version=2,
        created_at=occurred,
        actor_user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=safe_detail,
        previous_hash=head.head_hash,
        event_hash=event_hash,
    )
    session.add(event)
    head.sequence_number = sequence
    head.head_hash = event_hash
    await session.flush()
    return event


async def audit_chain_status(session: AsyncSession) -> dict[str, Any]:
    head = await session.scalar(select(AuditHead).where(AuditHead.id == 1))
    events = list((await session.scalars(
        select(AuditEvent).order_by(AuditEvent.sequence_number.asc())
    )).all())
    if head is None:
        return {"initialized": False, "valid": False, "event_count": len(events)}

    previous_hash = "0" * 64
    legacy_unverified = 0
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence_number != expected_sequence or event.previous_hash != previous_hash:
            return {
                "initialized": True, "valid": False, "event_count": len(events),
                "broken_event_id": str(event.id), "broken_sequence": event.sequence_number,
            }
        if event.hash_version >= 2:
            payload = _event_payload(
                sequence_number=event.sequence_number,
                actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                detail=event.detail,
                occurred_at=event.created_at.astimezone(timezone.utc).isoformat(),
                previous_hash=event.previous_hash,
            )
            if _event_hash(payload) != event.event_hash:
                return {
                    "initialized": True, "valid": False, "event_count": len(events),
                    "broken_event_id": str(event.id), "broken_sequence": event.sequence_number,
                    "reason": "event payload hash mismatch",
                }
        else:
            legacy_unverified += 1
        previous_hash = event.event_hash

    valid = head.sequence_number == len(events) and previous_hash == head.head_hash
    return {
        "initialized": True,
        "valid": valid,
        "event_count": len(events),
        "sequence_number": head.sequence_number,
        "legacy_events_linkage_only": legacy_unverified,
        "head_hash": head.head_hash,
        "note": "Verifies ordered links and payload hashes for version 2 events. Legacy events are link-checked only; externally anchor checkpoints to detect privileged rewrites.",
    }

def order_custody_events(events: list[Any]) -> tuple[list[Any], bool]:
    """Order custody events by predecessor hash, independent of timestamp precision."""
    by_previous: dict[str, Any] = {}
    for event in events:
        if event.previous_hash in by_previous:
            return [], False
        by_previous[event.previous_hash] = event
    ordered: list[Any] = []
    previous = "0" * 64
    while previous in by_previous:
        event = by_previous.pop(previous)
        ordered.append(event)
        previous = event.event_hash
    return ordered, not by_previous and len(ordered) == len(events)



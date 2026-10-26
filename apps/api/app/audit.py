import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, AuditHead, User


async def append_audit(
    session: AsyncSession, actor: User | None, action: str, entity_type: str,
    entity_id: str, detail: dict[str, Any] | None = None,
) -> AuditEvent:
    head = await session.scalar(select(AuditHead).where(AuditHead.id == 1).with_for_update())
    if head is None:
        raise HTTPException(status_code=503, detail="Audit chain is not initialized")
    safe_detail = detail or {}
    occurred_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "actor_user_id": str(actor.id) if actor else None, "action": action,
        "entity_type": entity_type, "entity_id": entity_id, "detail": safe_detail,
        "occurred_at": occurred_at, "previous_hash": head.head_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    event = AuditEvent(
        actor_user_id=actor.id if actor else None, action=action, entity_type=entity_type,
        entity_id=entity_id, detail=safe_detail, previous_hash=head.head_hash, event_hash=event_hash,
    )
    session.add(event)
    head.head_hash = event_hash
    await session.flush()
    return event


async def audit_chain_status(session: AsyncSession) -> dict[str, Any]:
    head = await session.scalar(select(AuditHead).where(AuditHead.id == 1))
    events = list((await session.scalars(select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id))).all())
    if head is None:
        return {"initialized": False, "valid": False, "event_count": len(events)}
    previous = "0" * 64
    for event in events:
        if event.previous_hash != previous:
            return {"initialized": True, "valid": False, "event_count": len(events), "broken_event_id": str(event.id)}
        previous = event.event_hash
    return {
        "initialized": True, "valid": previous == head.head_hash, "event_count": len(events),
        "head_hash": head.head_hash,
        "note": "Linkage check only; anchor hashes in separate immutable storage for stronger tamper evidence.",
    }

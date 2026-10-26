from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import append_audit, audit_chain_status
from app.config import settings
from app.database import SessionLocal, engine, get_session
from app.integrity import MODEL_VERSION, analyze_answer_patterns
from app.models import (
    AnswerSubmission, AuditHead, Candidate, CaseAppeal, CustodyEvent, Examination,
    IntegrityCase, IntegrityFinding, LoginAttempt, PaperBatch, StaffAssignment, StaffMember, User,
)
from app.schemas import (
    AnswerSubmissionCreate, AppealCreate, AppealResolution, AssignmentCreate, CandidateCreate,
    CandidateOutput, CandidatePortalLink, CaseDecision, CaseFromFinding, CustodyEventCreate, ExaminationCreate,
    ExaminationOutput, FindingOutput, LoginOutput, PaperBatchCreate, StaffCreate, StaffOutput,
    UserCreate, UserOutput,
)
from app.security import ROLES, create_access_token, current_user, hash_password, require_roles, verify_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Alembic runs before the service starts. This initializes only the singleton audit head.
    async with SessionLocal() as session:
        if await session.get(AuditHead, 1) is None:
            session.add(AuditHead(id=1, head_hash="0" * 64))
            await session.commit()
    yield
    await engine.dispose()


app = FastAPI(
    title="Rwanda Examination Integrity API",
    version="0.1.0",
    description="Exam operations and investigation support. Algorithmic leads never decide misconduct.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


async def commit_or_conflict(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Record conflicts with an existing unique or integrity constraint") from error



@app.exception_handler(IntegrityError)
async def integrity_conflict_handler(_: Request, __: IntegrityError) -> JSONResponse:
    # Flush-time as well as commit-time unique/FK violations should be safe API conflicts,
    # not internal error pages that disclose database details.
    return JSONResponse(status_code=409, content={"detail": "Record conflicts with an existing unique or integrity constraint"})


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def readiness(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        await session.execute(select(1))
        head = await session.get(AuditHead, 1)
        if head is None:
            raise HTTPException(status_code=503, detail="Audit chain not initialized")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ready"}


@app.post("/auth/token", response_model=LoginOutput, tags=["identity"])
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    normalized_email = form.username.strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    key = settings.login_hash_secret.encode("utf-8")
    email_key = hmac.new(key, ("email:" + normalized_email).encode("utf-8"), hashlib.sha256).hexdigest()
    ip_key = hmac.new(key, ("ip:" + ip_address).encode("utf-8"), hashlib.sha256).hexdigest()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    email_failures = int(await session.scalar(select(func.count(LoginAttempt.id)).where(
        LoginAttempt.email_key == email_key, LoginAttempt.succeeded.is_(False), LoginAttempt.created_at >= cutoff
    )) or 0)
    ip_failures = int(await session.scalar(select(func.count(LoginAttempt.id)).where(
        LoginAttempt.ip_key == ip_key, LoginAttempt.succeeded.is_(False), LoginAttempt.created_at >= cutoff
    )) or 0)
    if email_failures >= 8 or ip_failures >= 30:
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again later.")

    user = await session.scalar(select(User).where(User.email == normalized_email))
    valid = user is not None and user.is_active and verify_password(form.password, user.password_hash)
    session.add(LoginAttempt(email_key=email_key, ip_key=ip_key, succeeded=bool(valid)))
    if not valid:
        await session.commit()
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    assert user is not None
    token = create_access_token(user)
    await append_audit(session, user, "auth.login", "user", str(user.id), {"result": "success"})
    await session.commit()
    return LoginOutput(access_token=token, expires_in=settings.access_token_minutes * 60)


@app.get("/auth/me", response_model=UserOutput, tags=["identity"])
async def who_am_i(user: User = Depends(current_user)) -> User:
    return user


@app.post("/admin/users", response_model=UserOutput, status_code=201, tags=["identity"])
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN"))):
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="Unsupported role")
    if payload.role in {"SUPER_ADMIN", "ADMIN"} and actor.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only a super administrator can grant administrative roles")
    user = User(email=str(payload.email).lower(), full_name=payload.full_name, password_hash=hash_password(payload.password), role=payload.role)
    session.add(user)
    await session.flush()
    await append_audit(session, actor, "identity.user.created", "user", str(user.id), {"role": user.role})
    await commit_or_conflict(session)
    return user


@app.post("/examinations", response_model=ExaminationOutput, status_code=201, tags=["examinations"])
async def create_examination(payload: ExaminationCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS"))):
    exam = Examination(**payload.model_dump(), created_by=actor.id)
    session.add(exam)
    await session.flush()
    await append_audit(session, actor, "examination.created", "examination", str(exam.id), {"code": exam.code})
    await commit_or_conflict(session)
    return exam


@app.get("/examinations", response_model=list[ExaminationOutput], tags=["examinations"])
async def list_examinations(limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session), _: User = Depends(current_user)):
    return list((await session.scalars(select(Examination).order_by(Examination.exam_date.desc()).limit(limit))).all())


@app.post("/candidates", response_model=CandidateOutput, status_code=201, tags=["candidates"])
async def create_candidate(payload: CandidateCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS"))):
    exam = await session.get(Examination, payload.examination_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found")
    candidate = Candidate(**payload.model_dump())
    session.add(candidate)
    await session.flush()
    await append_audit(session, actor, "candidate.registered", "candidate", str(candidate.id), {"examination_id": str(exam.id), "school_code": candidate.school_code})
    await commit_or_conflict(session)
    return candidate


@app.post("/candidates/{candidate_id}/portal-access", status_code=201, tags=["candidates"])
async def link_candidate_portal(
    candidate_id: UUID,
    payload: CandidatePortalLink,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS")),
):
    candidate = await session.get(Candidate, candidate_id)
    user = await session.get(User, payload.user_id)
    if candidate is None or user is None:
        raise HTTPException(status_code=404, detail="Candidate or portal user not found")
    if user.role != "CANDIDATE":
        raise HTTPException(status_code=422, detail="Linked user must have the CANDIDATE role")
    if candidate.portal_user_id is not None:
        raise HTTPException(status_code=409, detail="Candidate already has a linked portal account")
    candidate.portal_user_id = user.id
    await append_audit(
        session, actor, "candidate.portal.linked", "candidate", str(candidate.id),
        {"portal_user_id": str(user.id), "verification_reference": payload.verification_reference},
    )
    await session.commit()
    return {"candidate_id": str(candidate.id), "portal_user_id": str(user.id), "status": "LINKED"}


@app.get("/candidates", response_model=list[CandidateOutput], tags=["candidates"])
async def list_candidates(
    examination_id: UUID,
    centre_code: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS", "INVESTIGATOR", "REVIEWER", "AUDITOR", "MARKER")),
):
    query = select(Candidate).where(Candidate.examination_id == examination_id)
    if centre_code:
        query = query.where(Candidate.centre_code == centre_code)
    return list((await session.scalars(query.order_by(Candidate.registration_number).limit(limit))).all())


@app.patch("/candidates/{candidate_id}/attendance", response_model=CandidateOutput, tags=["candidates"])
async def mark_attendance(
    candidate_id: UUID, attendance_status: str, session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS")),
):
    allowed = {"PRESENT", "ABSENT", "EXCUSED", "REQUIRES_REVIEW"}
    if attendance_status not in allowed:
        raise HTTPException(status_code=422, detail=f"attendance_status must be one of {sorted(allowed)}")
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.attendance_status = attendance_status
    await append_audit(session, actor, "candidate.attendance.updated", "candidate", str(candidate.id), {"attendance_status": attendance_status})
    await session.commit()
    return candidate


@app.post("/staff", response_model=StaffOutput, status_code=201, tags=["staff"])
async def create_staff(payload: StaffCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS"))):
    data = payload.model_dump()
    data["eligible"] = False
    data["eligibility_note"] = None
    staff = StaffMember(**data, eligibility_checked_by=None, created_by=actor.id)
    session.add(staff)
    await session.flush()
    await append_audit(session, actor, "staff.registered", "staff_member", str(staff.id), {"staff_reference": staff.staff_reference})
    await commit_or_conflict(session)
    return staff


@app.get("/staff", response_model=list[StaffOutput], tags=["staff"])
async def list_staff(limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session), _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS", "AUDITOR"))):
    return list((await session.scalars(select(StaffMember).order_by(StaffMember.full_name).limit(limit))).all())


@app.patch("/staff/{staff_id}/eligibility", response_model=StaffOutput, tags=["staff"])
async def set_staff_eligibility(
    staff_id: UUID, eligible: bool, note: str, session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS")),
):
    if len(note.strip()) < 5 or len(note) > 500:
        raise HTTPException(status_code=422, detail="A 5-500 character review note is required")
    staff = await session.get(StaffMember, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    if staff.created_by is not None and staff.created_by == actor.id:
        raise HTTPException(status_code=409, detail="Eligibility reviewer must be different from the staff-record creator")
    staff.eligible = eligible
    staff.eligibility_checked_by = actor.id
    staff.eligibility_checked_at = datetime.now(timezone.utc)
    staff.eligibility_note = note.strip()
    await append_audit(session, actor, "staff.eligibility.reviewed", "staff_member", str(staff.id), {"eligible": eligible, "note": note.strip()})
    await session.commit()
    return staff


@app.post("/staff-assignments", status_code=201, tags=["staff"])
async def assign_staff(payload: AssignmentCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS"))):
    exam, staff = await session.get(Examination, payload.examination_id), await session.get(StaffMember, payload.staff_id)
    if exam is None or staff is None:
        raise HTTPException(status_code=404, detail="Examination or staff member not found")
    if not staff.eligible:
        raise HTTPException(status_code=409, detail="Staff eligibility must be verified before assignment")
    if staff.employing_school_code.casefold() == payload.centre_code.casefold():
        raise HTTPException(status_code=409, detail="Staff cannot invigilate at their employing school centre")
    assignment = StaffAssignment(**payload.model_dump(), approved_by=actor.id)
    session.add(assignment)
    await session.flush()
    await append_audit(session, actor, "staff.assignment.created", "staff_assignment", str(assignment.id), {"examination_id": str(exam.id), "centre_code": payload.centre_code, "room_code": payload.room_code})
    await commit_or_conflict(session)
    return {"id": str(assignment.id), "status": "ASSIGNED", "staff_id": str(staff.id), "examination_id": str(exam.id)}


@app.post("/paper-batches", status_code=201, tags=["chain-of-custody"])
async def create_paper_batch(payload: PaperBatchCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS"))):
    if await session.get(Examination, payload.examination_id) is None:
        raise HTTPException(status_code=404, detail="Examination not found")
    batch = PaperBatch(**payload.model_dump(), status="PREPARED")
    session.add(batch)
    await session.flush()
    await append_audit(session, actor, "paper_batch.created", "paper_batch", str(batch.id), {"batch_code": batch.batch_code, "paper_count": batch.paper_count})
    await commit_or_conflict(session)
    return {"id": str(batch.id), "batch_code": batch.batch_code, "status": batch.status}


CUSTODY_TRANSITIONS = {
    "PREPARED": {"SEALED"}, "SEALED": {"DISPATCHED"}, "DISPATCHED": {"RECEIVED"},
    "RECEIVED": {"OPENED"}, "OPENED": {"RETURNED"}, "RETURNED": {"RECONCILED"}, "RECONCILED": set(),
}


@app.post("/paper-batches/{batch_id}/events", status_code=201, tags=["chain-of-custody"])
async def add_custody_event(
    batch_id: UUID, payload: CustodyEventCreate, session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS")),
):
    batch = await session.scalar(select(PaperBatch).where(PaperBatch.id == batch_id).with_for_update())
    if batch is None:
        raise HTTPException(status_code=404, detail="Paper batch not found")
    if payload.event_type not in CUSTODY_TRANSITIONS.get(batch.status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid custody transition from {batch.status} to {payload.event_type}")
    event_body = {"batch_id": str(batch.id), "event_type": payload.event_type, "location_code": payload.location_code, "notes": payload.notes, "performed_by": str(actor.id), "previous_hash": batch.last_event_hash}
    event_hash = hashlib.sha256(json.dumps(event_body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    event = CustodyEvent(batch_id=batch.id, event_type=payload.event_type, location_code=payload.location_code, notes=payload.notes, performed_by=actor.id, previous_hash=batch.last_event_hash, event_hash=event_hash)
    session.add(event)
    batch.last_event_hash = event_hash
    batch.status = payload.event_type
    await append_audit(session, actor, "paper_custody.event", "paper_batch", str(batch.id), {"event_type": payload.event_type, "location_code": payload.location_code, "event_hash": event_hash})
    await session.commit()
    return {"id": str(event.id), "batch_id": str(batch.id), "status": batch.status, "previous_hash": event.previous_hash, "event_hash": event.event_hash}


@app.get("/paper-batches/{batch_id}/events", tags=["chain-of-custody"])
async def list_custody_events(batch_id: UUID, session: AsyncSession = Depends(get_session), _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS", "INVESTIGATOR", "AUDITOR"))):
    events = list((await session.scalars(select(CustodyEvent).where(CustodyEvent.batch_id == batch_id).order_by(CustodyEvent.created_at, CustodyEvent.id))).all())
    return [{"id": str(e.id), "event_type": e.event_type, "location_code": e.location_code, "performed_by": str(e.performed_by), "previous_hash": e.previous_hash, "event_hash": e.event_hash, "created_at": e.created_at} for e in events]


@app.get("/paper-batches/{batch_id}/verify", tags=["chain-of-custody"])
async def verify_custody_chain(
    batch_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS", "INVESTIGATOR", "AUDITOR")),
):
    batch = await session.get(PaperBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Paper batch not found")
    events = list((await session.scalars(
        select(CustodyEvent).where(CustodyEvent.batch_id == batch_id).order_by(CustodyEvent.created_at, CustodyEvent.id)
    )).all())
    previous = "0" * 64
    for event in events:
        event_body = {
            "batch_id": str(event.batch_id),
            "event_type": event.event_type,
            "location_code": event.location_code,
            "notes": event.notes,
            "performed_by": str(event.performed_by),
            "previous_hash": event.previous_hash,
        }
        expected_hash = hashlib.sha256(json.dumps(event_body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if event.previous_hash != previous or event.event_hash != expected_hash:
            return {"batch_id": str(batch.id), "valid": False, "event_count": len(events), "broken_event_id": str(event.id)}
        previous = event.event_hash
    valid = previous == batch.last_event_hash
    return {
        "batch_id": str(batch.id), "valid": valid, "event_count": len(events),
        "batch_status": batch.status, "head_matches": valid,
        "note": "Verifies event payload hashes, predecessor links and batch head; retain independent signed checkpoints for protection against privileged database rewrites.",
    }


@app.post("/answer-submissions", status_code=201, tags=["integrity-analysis"])
async def submit_answers(payload: AnswerSubmissionCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "EXAM_OPERATIONS", "MARKER"))):
    candidate, exam = await session.get(Candidate, payload.candidate_id), await session.get(Examination, payload.examination_id)
    if candidate is None or exam is None or candidate.examination_id != exam.id:
        raise HTTPException(status_code=422, detail="Candidate must be registered for this examination")
    submission = AnswerSubmission(**payload.model_dump(), submitted_by=actor.id)
    session.add(submission)
    await session.flush()
    await append_audit(session, actor, "answer_script.ingested", "answer_submission", str(submission.id), {"examination_id": str(exam.id), "candidate_id": str(candidate.id), "response_count": len(payload.responses)})
    await commit_or_conflict(session)
    return {"id": str(submission.id), "status": "INGESTED", "response_count": len(payload.responses)}


@app.post("/integrity/analyze/{examination_id}", tags=["integrity-analysis"])
async def analyze_examination(
    examination_id: UUID, min_shared_questions: int = Query(default=4, ge=2, le=50),
    similarity_threshold: float = Query(default=0.85, ge=0.5, le=1.0),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "INVESTIGATOR")),
):
    if await session.get(Examination, examination_id) is None:
        raise HTTPException(status_code=404, detail="Examination not found")
    rows = list((await session.scalars(select(AnswerSubmission).where(AnswerSubmission.examination_id == examination_id))).all())
    if len(rows) < 2:
        raise HTTPException(status_code=422, detail="At least two submitted scripts are required for cohort analysis")
    leads = analyze_answer_patterns([{"candidate_id": str(row.candidate_id), "responses": row.responses} for row in rows], min_shared_questions=min_shared_questions, similarity_threshold=similarity_threshold)
    persisted = []
    for lead in leads:
        a, b = UUID(lead["candidate_a_id"]), UUID(lead["candidate_b_id"])
        exists = await session.scalar(select(IntegrityFinding.id).where(
            IntegrityFinding.examination_id == examination_id,
            IntegrityFinding.candidate_a_id == a, IntegrityFinding.candidate_b_id == b,
            IntegrityFinding.model_version == MODEL_VERSION,
        ).limit(1))
        if exists:
            continue
        finding = IntegrityFinding(examination_id=examination_id, candidate_a_id=a, candidate_b_id=b, similarity_score=lead["similarity_score"], model_version=MODEL_VERSION, evidence=lead["evidence"], status="NEEDS_REVIEW")
        session.add(finding)
        persisted.append(finding)
    await session.flush()
    await append_audit(session, actor, "integrity.analysis.completed", "examination", str(examination_id), {"scripts_analyzed": len(rows), "new_review_leads": len(persisted), "model_version": MODEL_VERSION})
    await session.commit()
    return {
        "examination_id": str(examination_id), "scripts_analyzed": len(rows), "new_review_leads": len(persisted),
        "model_version": MODEL_VERSION, "decision_policy": "Triage only. Human evidence review is mandatory.",
        "findings": [FindingOutput.model_validate(item).model_dump(mode="json") for item in persisted],
    }


@app.get("/integrity/findings", response_model=list[FindingOutput], tags=["integrity-analysis"])
async def list_findings(
    examination_id: UUID | None = None, limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "INVESTIGATOR", "REVIEWER", "AUDITOR")),
):
    query = select(IntegrityFinding).order_by(IntegrityFinding.created_at.desc()).limit(limit)
    if examination_id:
        query = query.where(IntegrityFinding.examination_id == examination_id)
    return list((await session.scalars(query)).all())


@app.get("/my/cases", tags=["case-management"])
async def list_my_cases(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles("CANDIDATE")),
):
    cases = list((await session.scalars(
        select(IntegrityCase)
        .join(Candidate, Candidate.id == IntegrityCase.affected_candidate_id)
        .where(Candidate.portal_user_id == actor.id)
        .order_by(IntegrityCase.created_at.desc())
    )).all())
    return [
        {"id": str(c.id), "finding_id": str(c.finding_id), "status": c.status,
         "outcome": c.outcome, "decision_notes": c.decision_notes,
         "created_at": c.created_at, "decided_at": c.decided_at}
        for c in cases
    ]


@app.post("/cases/from-finding/{finding_id}", status_code=201, tags=["case-management"])
async def open_case(finding_id: UUID, payload: CaseFromFinding, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "INVESTIGATOR"))):
    finding = await session.get(IntegrityFinding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Integrity finding not found")
    if payload.affected_candidate_id not in {finding.candidate_a_id, finding.candidate_b_id}:
        raise HTTPException(status_code=422, detail="Affected candidate must appear in the finding")
    case = IntegrityCase(finding_id=finding.id, affected_candidate_id=payload.affected_candidate_id, created_by=actor.id, status="OPEN")
    session.add(case)
    finding.status = "CASE_OPENED"
    await session.flush()
    await append_audit(session, actor, "case.opened", "integrity_case", str(case.id), {"finding_id": str(finding.id), "affected_candidate_id": str(case.affected_candidate_id)})
    await session.commit()
    return {"id": str(case.id), "status": case.status, "finding_id": str(finding.id)}


@app.get("/cases", tags=["case-management"])
async def list_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500), session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "INVESTIGATOR", "REVIEWER", "APPEALS_OFFICER", "AUDITOR")),
):
    query = select(IntegrityCase).order_by(IntegrityCase.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(IntegrityCase.status == status_filter)
    cases = list((await session.scalars(query)).all())
    return [{"id": str(c.id), "finding_id": str(c.finding_id), "affected_candidate_id": str(c.affected_candidate_id), "status": c.status, "outcome": c.outcome, "created_at": c.created_at, "decided_at": c.decided_at} for c in cases]


@app.post("/cases/{case_id}/decision", tags=["case-management"])
async def decide_case(case_id: UUID, payload: CaseDecision, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "REVIEWER"))):
    allowed = {"CONFIRMED", "NOT_SUBSTANTIATED", "INSUFFICIENT_EVIDENCE"}
    if payload.outcome not in allowed:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(allowed)}")
    case = await session.get(IntegrityCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.created_by == actor.id:
        raise HTTPException(status_code=409, detail="Case opener cannot decide the same case")
    if case.status in {"DECIDED", "CLOSED"}:
        raise HTTPException(status_code=409, detail="Case already has a decision")
    case.status, case.outcome, case.decision_notes = "DECIDED", payload.outcome, payload.evidence_summary
    case.decided_by, case.decided_at = actor.id, datetime.now(timezone.utc)
    await append_audit(session, actor, "case.decided", "integrity_case", str(case.id), {"outcome": payload.outcome, "finding_id": str(case.finding_id)})
    await session.commit()
    return {"id": str(case.id), "status": case.status, "outcome": case.outcome, "decided_at": case.decided_at}


@app.post("/cases/{case_id}/appeals", status_code=201, tags=["case-management"])
async def submit_appeal(case_id: UUID, payload: AppealCreate, session: AsyncSession = Depends(get_session), actor: User = Depends(current_user)):
    case = await session.get(IntegrityCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status not in {"DECIDED", "APPEALED"}:
        raise HTTPException(status_code=409, detail="Appeals are accepted after a decision")
    candidate = await session.get(Candidate, case.affected_candidate_id)
    if actor.role not in {"SUPER_ADMIN", "ADMIN", "APPEALS_OFFICER"} and (candidate is None or candidate.portal_user_id != actor.id):
        raise HTTPException(status_code=403, detail="Account is not verified as the affected candidate or authorized representative")
    appeal = CaseAppeal(case_id=case.id, appellant_user_id=actor.id, statement=payload.statement)
    session.add(appeal)
    case.status = "APPEALED"
    await session.flush()
    await append_audit(session, actor, "case.appeal.submitted", "integrity_case", str(case.id), {"appeal_id": str(appeal.id), "statement_length": len(payload.statement)})
    await session.commit()
    return {"id": str(appeal.id), "case_id": str(case.id), "status": appeal.status}


@app.post("/appeals/{appeal_id}/resolution", tags=["case-management"])
async def resolve_appeal(appeal_id: UUID, payload: AppealResolution, session: AsyncSession = Depends(get_session), actor: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "APPEALS_OFFICER"))):
    if payload.status not in {"UPHELD", "REMANDED", "DECISION_OVERTURNED"}:
        raise HTTPException(status_code=422, detail="Unsupported appeal resolution")
    appeal = await session.get(CaseAppeal, appeal_id)
    if appeal is None:
        raise HTTPException(status_code=404, detail="Appeal not found")
    case = await session.get(IntegrityCase, appeal.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Associated case not found")
    if case.decided_by == actor.id:
        raise HTTPException(status_code=409, detail="Original decision-maker cannot decide an appeal")
    appeal.status, appeal.resolution_notes = payload.status, payload.notes
    case.status = "CLOSED" if payload.status == "UPHELD" else "IN_REVIEW"
    if payload.status == "DECISION_OVERTURNED":
        case.outcome = "NOT_SUBSTANTIATED"
    await append_audit(session, actor, "case.appeal.resolved", "case_appeal", str(appeal.id), {"status": payload.status, "case_id": str(case.id)})
    await session.commit()
    return {"appeal_id": str(appeal.id), "status": appeal.status, "case_status": case.status}


@app.get("/audit/status", tags=["audit"])
async def get_audit_status(session: AsyncSession = Depends(get_session), _: User = Depends(require_roles("SUPER_ADMIN", "ADMIN", "AUDITOR"))):
    return await audit_chain_status(session)

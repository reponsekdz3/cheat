from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)




class LoginAttempt(Base, TimestampMixin):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempt_email_created", "email_key", "created_at"),
        Index("ix_login_attempt_ip_created", "ip_key", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    email_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_key: Mapped[str] = mapped_column(String(64), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Examination(Base, TimestampMixin):
    __tablename__ = "examinations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    level: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    exam_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PLANNED", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("examination_id", "registration_number", name="uq_candidate_exam_registration"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    examination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    registration_number: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    school_code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    centre_code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    room_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    seat_number: Mapped[str | None] = mapped_column(String(24), nullable=True)
    attendance_status: Mapped[str] = mapped_column(String(24), default="UNMARKED", nullable=False)
    portal_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class StaffMember(Base, TimestampMixin):
    __tablename__ = "staff_members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    staff_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    employing_school_code: Mapped[str] = mapped_column(String(80), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    eligibility_checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    eligibility_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eligibility_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class StaffAssignment(Base, TimestampMixin):
    __tablename__ = "staff_assignments"
    __table_args__ = (UniqueConstraint("examination_id", "staff_id", name="uq_exam_staff_assignment"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    examination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="RESTRICT"), index=True)
    centre_code: Mapped[str] = mapped_column(String(80), nullable=False)
    room_code: Mapped[str] = mapped_column(String(40), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(40), default="INVIGILATOR", nullable=False)
    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


class PaperBatch(Base, TimestampMixin):
    __tablename__ = "paper_batches"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    examination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    batch_code: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    destination_centre_code: Mapped[str] = mapped_column(String(80), nullable=False)
    paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seal_identifier: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PREPARED", nullable=False)
    last_event_hash: Mapped[str] = mapped_column(String(64), default=lambda: "0" * 64, nullable=False)


class CustodyEvent(Base, TimestampMixin):
    __tablename__ = "custody_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("paper_batches.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    location_code: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(800), nullable=True)
    performed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class AnswerSubmission(Base, TimestampMixin):
    __tablename__ = "answer_submissions"
    __table_args__ = (UniqueConstraint("examination_id", "candidate_id", name="uq_answer_candidate_exam"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    examination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    responses: Mapped[dict] = mapped_column(JSON, nullable=False)
    script_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


class IntegrityFinding(Base, TimestampMixin):
    __tablename__ = "integrity_findings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    examination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    candidate_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    candidate_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="NEEDS_REVIEW", nullable=False)


class IntegrityCase(Base, TimestampMixin):
    __tablename__ = "integrity_cases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("integrity_findings.id", ondelete="RESTRICT"), index=True)
    affected_candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="RESTRICT"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseAppeal(Base, TimestampMixin):
    __tablename__ = "case_appeals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("integrity_cases.id", ondelete="CASCADE"), index=True)
    appellant_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditHead(Base):
    __tablename__ = "audit_head"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    head_hash: Mapped[str] = mapped_column(String(64), nullable=False, default=lambda: "0" * 64)


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

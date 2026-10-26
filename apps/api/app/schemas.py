from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)
    role: str


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class ExaminationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    title: str = Field(min_length=3, max_length=240)
    level: str = Field(min_length=2, max_length=40)
    subject: str = Field(min_length=2, max_length=120)
    exam_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ExaminationOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    title: str
    level: str
    subject: str
    exam_date: str
    status: str
    created_at: datetime


class CandidateCreate(BaseModel):
    examination_id: UUID
    registration_number: str = Field(min_length=2, max_length=100)
    full_name: str = Field(min_length=2, max_length=180)
    school_code: str = Field(min_length=1, max_length=80)
    centre_code: str = Field(min_length=1, max_length=80)
    room_code: str | None = Field(default=None, max_length=40)
    seat_number: str | None = Field(default=None, max_length=24)


class CandidateOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    examination_id: UUID
    registration_number: str
    full_name: str
    school_code: str
    centre_code: str
    room_code: str | None
    seat_number: str | None
    attendance_status: str


class StaffCreate(BaseModel):
    staff_reference: str = Field(min_length=2, max_length=100)
    full_name: str = Field(min_length=2, max_length=180)
    employing_school_code: str = Field(min_length=1, max_length=80)
    eligible: bool = False
    eligibility_note: str | None = Field(default=None, max_length=500)


class StaffOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    staff_reference: str
    full_name: str
    employing_school_code: str
    eligible: bool
    eligibility_checked_at: datetime | None
    eligibility_note: str | None


class EligibilityUpdate(BaseModel):
    eligible: bool
    note: str = Field(min_length=5, max_length=500)


class AssignmentCreate(BaseModel):
    examination_id: UUID
    staff_id: UUID
    centre_code: str = Field(min_length=1, max_length=80)
    room_code: str = Field(min_length=1, max_length=40)
    assignment_type: str = "INVIGILATOR"


class PaperBatchCreate(BaseModel):
    examination_id: UUID
    batch_code: str = Field(min_length=2, max_length=120)
    destination_centre_code: str = Field(min_length=1, max_length=80)
    paper_count: int = Field(gt=0, le=100000)
    seal_identifier: str = Field(min_length=4, max_length=160)


class CustodyEventCreate(BaseModel):
    event_type: str
    location_code: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=800)


class AnswerSubmissionCreate(BaseModel):
    examination_id: UUID
    candidate_id: UUID
    responses: dict[str, Any] = Field(min_length=1, max_length=300)
    script_reference: str | None = Field(default=None, max_length=200)

    @field_validator("responses")
    @classmethod
    def validate_response_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        for question, answer in value.items():
            if not question or len(question) > 100:
                raise ValueError("Question identifiers must be 1-100 characters")
            if not isinstance(answer, (str, int, float, bool)) and answer is not None:
                raise ValueError("Responses must be scalar values or null")
            if isinstance(answer, str) and len(answer) > 10000:
                raise ValueError("A response cannot exceed 10000 characters")
        return value


class CaseFromFinding(BaseModel):
    affected_candidate_id: UUID


class CaseDecision(BaseModel):
    outcome: str
    evidence_summary: str = Field(min_length=20, max_length=10000)


class AppealCreate(BaseModel):
    statement: str = Field(min_length=20, max_length=10000)


class AppealResolution(BaseModel):
    status: str
    notes: str = Field(min_length=10, max_length=10000)


class FindingOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    examination_id: UUID
    candidate_a_id: UUID
    candidate_b_id: UUID
    similarity_score: float
    model_version: str
    evidence: dict
    status: str
    created_at: datetime

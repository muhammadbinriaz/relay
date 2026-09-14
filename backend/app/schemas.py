from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    org_id: UUID
    org_slug: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    name: str

    model_config = {"from_attributes": True}


class OrgOut(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserOut
    org: OrgOut
    role: str


class WorkflowCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    graph: dict[str, Any]


class WorkflowOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    version: int
    is_active: bool
    graph: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    definition_id: UUID | None = None
    slug: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    trigger_type: str = "manual"


class StepOut(BaseModel):
    id: UUID
    step_key: str
    step_type: str
    sequence: int
    status: str
    attempt: int
    max_attempts: int
    error: str | None
    output: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: UUID
    definition_id: UUID
    status: str
    trigger_type: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    current_step_key: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[StepOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: UUID
    run_id: UUID
    step_id: UUID
    status: str
    title: str
    payload: dict[str, Any]
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str | None = None


class AuditOut(BaseModel):
    id: UUID
    event_type: str
    message: str
    data: dict[str, Any]
    run_id: UUID | None
    step_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeadLetterOut(BaseModel):
    id: UUID
    run_id: UUID
    step_id: UUID
    reason: str
    payload: dict[str, Any]
    created_at: datetime
    replayed_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    api_key: str
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    redis: str
    database: str

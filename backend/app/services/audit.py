from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def write_audit(
    db: Session,
    *,
    org_id: UUID,
    event_type: str,
    message: str,
    data: dict[str, Any] | None = None,
    actor_user_id: UUID | None = None,
    run_id: UUID | None = None,
    step_id: UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        org_id=org_id,
        actor_user_id=actor_user_id,
        run_id=run_id,
        step_id=step_id,
        event_type=event_type,
        message=message,
        data=data or {},
    )
    db.add(event)
    return event

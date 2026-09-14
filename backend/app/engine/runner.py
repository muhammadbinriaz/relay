from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.engine.graph import WorkflowGraph
from app.models.workflow import RunStatus, RunStep, StepStatus, TriggerType, WorkflowDefinition, WorkflowRun
from app.services.audit import write_audit
from app.services.queue import enqueue_step, incr_metric


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_run(
    db: Session,
    *,
    org_id: UUID,
    definition: WorkflowDefinition,
    input_data: dict[str, Any],
    trigger_type: TriggerType = TriggerType.manual,
    created_by: UUID | None = None,
) -> WorkflowRun:
    graph = WorkflowGraph.model_validate(definition.graph)
    ordered = graph.ordered_from_entry()

    run = WorkflowRun(
        org_id=org_id,
        definition_id=definition.id,
        status=RunStatus.pending,
        trigger_type=trigger_type,
        input=input_data,
        created_by=created_by,
        current_step_key=ordered[0].key if ordered else None,
    )
    db.add(run)
    db.flush()

    first_step_id: UUID | None = None
    for idx, step_def in enumerate(ordered):
        status = StepStatus.ready if idx == 0 else StepStatus.pending
        step = RunStep(
            run_id=run.id,
            org_id=org_id,
            step_key=step_def.key,
            step_type=step_def.type,
            sequence=idx,
            status=status,
            max_attempts=step_def.max_attempts,
            idempotency_key=f"{run.id}:{step_def.key}:0",
            input=None,
        )
        db.add(step)
        db.flush()
        if idx == 0:
            first_step_id = step.id

    write_audit(
        db,
        org_id=org_id,
        event_type="run.created",
        message=f"Run created for workflow {definition.slug}",
        data={"definition_id": str(definition.id), "trigger": trigger_type.value},
        actor_user_id=created_by,
        run_id=run.id,
    )
    db.commit()
    db.refresh(run)

    if first_step_id:
        enqueue_step(str(first_step_id))
        incr_metric("runs_created")

    return run


def advance_after_step(
    db: Session,
    *,
    run: WorkflowRun,
    completed_step: RunStep,
    definition: WorkflowDefinition,
    rejected: bool = False,
) -> None:
    graph = WorkflowGraph.model_validate(definition.graph)
    smap = graph.step_map()
    step_def = smap.get(completed_step.step_key)
    if not step_def:
        run.status = RunStatus.failed
        run.error = f"Unknown step {completed_step.step_key}"
        run.finished_at = _utcnow()
        return

    next_key = step_def.on_reject if rejected else step_def.next
    if rejected and not next_key:
        run.status = RunStatus.cancelled
        run.output = {"rejected": True, "at_step": completed_step.step_key}
        run.finished_at = _utcnow()
        write_audit(
            db,
            org_id=run.org_id,
            event_type="run.cancelled",
            message="Run cancelled after rejection",
            run_id=run.id,
            step_id=completed_step.id,
        )
        return

    if not next_key:
        run.status = RunStatus.completed
        run.output = completed_step.output or {}
        # roll up last meaningful outputs
        outputs = {s.step_key: s.output for s in run.steps if s.output}
        run.output = outputs
        run.finished_at = _utcnow()
        run.current_step_key = None
        write_audit(
            db,
            org_id=run.org_id,
            event_type="run.completed",
            message="Run completed successfully",
            run_id=run.id,
        )
        incr_metric("runs_completed")
        return

    next_step = next((s for s in run.steps if s.step_key == next_key), None)
    if not next_step:
        run.status = RunStatus.failed
        run.error = f"Next step '{next_key}' missing on run"
        run.finished_at = _utcnow()
        return

    # carry forward context: previous outputs + run input
    ctx: dict[str, Any] = {"run_input": run.input or {}}
    for s in sorted(run.steps, key=lambda x: x.sequence):
        if s.output:
            ctx[s.step_key] = s.output
    next_step.input = ctx
    next_step.status = StepStatus.ready
    next_step.idempotency_key = f"{run.id}:{next_step.step_key}:{next_step.attempt}"
    run.current_step_key = next_step.step_key
    if run.status == RunStatus.waiting_approval:
        run.status = RunStatus.running
    elif run.status == RunStatus.pending:
        run.status = RunStatus.running
        run.started_at = run.started_at or _utcnow()

    db.flush()
    enqueue_step(str(next_step.id))


def new_attempt_idempotency(run_id: UUID, step_key: str, attempt: int) -> str:
    return f"{run_id}:{step_key}:{attempt}"


def make_run_id() -> uuid.UUID:
    return uuid.uuid4()

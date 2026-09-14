from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.connectors.handlers import execute_step
from app.db import SessionLocal
from app.engine.graph import WorkflowGraph
from app.engine.runner import advance_after_step, new_attempt_idempotency
from app.models.workflow import (
    ApprovalStatus,
    ApprovalTask,
    DeadLetter,
    RunStatus,
    RunStep,
    StepStatus,
    WorkflowDefinition,
    WorkflowRun,
)
from app.services.audit import write_audit
from app.services.queue import enqueue_step, get_redis, incr_metric

logger = logging.getLogger("relay.worker")
settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def reclaim_expired_leases(db: Session) -> int:
    now = _utcnow()
    steps = (
        db.query(RunStep)
        .filter(
            RunStep.status.in_([StepStatus.leased, StepStatus.running]),
            RunStep.lease_expires_at.isnot(None),
            RunStep.lease_expires_at < now,
        )
        .all()
    )
    count = 0
    for step in steps:
        step.status = StepStatus.ready
        step.lease_owner = None
        step.lease_expires_at = None
        write_audit(
            db,
            org_id=step.org_id,
            event_type="step.lease_reclaimed",
            message=f"Reclaimed expired lease on {step.step_key}",
            run_id=step.run_id,
            step_id=step.id,
            data={"previous_owner": settings.worker_id},
        )
        enqueue_step(str(step.id))
        count += 1
    if count:
        db.commit()
    return count


def promote_due_retries(db: Session) -> int:
    now = _utcnow()
    steps = (
        db.query(RunStep)
        .filter(RunStep.status == StepStatus.pending, RunStep.next_retry_at.isnot(None), RunStep.next_retry_at <= now)
        .all()
    )
    for step in steps:
        step.status = StepStatus.ready
        step.next_retry_at = None
        enqueue_step(str(step.id))
    if steps:
        db.commit()
    return len(steps)


def claim_step(db: Session, step_id: UUID) -> RunStep | None:
    step = (
        db.query(RunStep)
        .filter(RunStep.id == step_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not step:
        return None
    if step.status not in (StepStatus.ready, StepStatus.pending):
        return None
    if step.next_retry_at and step.next_retry_at > _utcnow():
        return None

    step.status = StepStatus.leased
    step.lease_owner = settings.worker_id
    step.lease_expires_at = _utcnow() + timedelta(seconds=settings.lease_seconds)
    step.attempt += 1
    step.idempotency_key = new_attempt_idempotency(step.run_id, step.step_key, step.attempt)
    step.started_at = _utcnow()
    step.error = None
    db.commit()
    db.refresh(step)
    return step


def heartbeat(db: Session, step: RunStep) -> None:
    if step.lease_owner != settings.worker_id:
        return
    step.lease_expires_at = _utcnow() + timedelta(seconds=settings.lease_seconds)
    db.commit()


async def process_step(step_id: UUID) -> None:
    db = SessionLocal()
    try:
        step = claim_step(db, step_id)
        if not step:
            return

        run = (
            db.query(WorkflowRun)
            .options(joinedload(WorkflowRun.steps), joinedload(WorkflowRun.definition))
            .filter(WorkflowRun.id == step.run_id)
            .first()
        )
        if not run:
            return

        definition: WorkflowDefinition = run.definition
        graph = WorkflowGraph.model_validate(definition.graph)
        step_def = graph.step_map().get(step.step_key)
        if not step_def:
            await _fail_permanent(db, run, step, f"Step def missing: {step.step_key}")
            return

        if run.status in (RunStatus.pending,):
            run.status = RunStatus.running
            run.started_at = run.started_at or _utcnow()

        step.status = StepStatus.running
        db.commit()

        context = step.input or {"run_input": run.input or {}}
        if "run_input" not in context:
            context["run_input"] = run.input or {}

        write_audit(
            db,
            org_id=step.org_id,
            event_type="step.started",
            message=f"Started {step.step_key} attempt {step.attempt}",
            run_id=run.id,
            step_id=step.id,
        )
        db.commit()

        try:
            heartbeat(db, step)
            result = await execute_step(step.step_type, step_def.config, context, run_id=run.id)
        except Exception as exc:
            await _handle_failure(db, run, step, definition, exc)
            return

        if result.needs_approval:
            step.status = StepStatus.waiting_approval
            step.output = result.output
            step.lease_owner = None
            step.lease_expires_at = None
            run.status = RunStatus.waiting_approval
            approval = ApprovalTask(
                org_id=run.org_id,
                run_id=run.id,
                step_id=step.id,
                status=ApprovalStatus.pending,
                title=result.approval_title,
                payload=result.approval_payload,
            )
            db.add(approval)
            write_audit(
                db,
                org_id=run.org_id,
                event_type="approval.requested",
                message=result.approval_title,
                run_id=run.id,
                step_id=step.id,
                data=result.approval_payload,
            )
            db.commit()
            incr_metric("approvals_requested")
            return

        step.status = StepStatus.completed
        step.output = result.output
        step.finished_at = _utcnow()
        step.lease_owner = None
        step.lease_expires_at = None
        step.checkpoint = {"completed_attempt": step.attempt}
        write_audit(
            db,
            org_id=run.org_id,
            event_type="step.completed",
            message=f"Completed {step.step_key}",
            run_id=run.id,
            step_id=step.id,
            data={"output_keys": list((result.output or {}).keys())},
        )
        db.commit()

        # reload with steps
        db.refresh(run)
        run = (
            db.query(WorkflowRun)
            .options(joinedload(WorkflowRun.steps), joinedload(WorkflowRun.definition))
            .filter(WorkflowRun.id == run.id)
            .first()
        )
        assert run is not None
        completed = next(s for s in run.steps if s.id == step.id)
        advance_after_step(db, run=run, completed_step=completed, definition=definition)
        db.commit()
        incr_metric("steps_completed")
    finally:
        db.close()


async def _handle_failure(
    db: Session,
    run: WorkflowRun,
    step: RunStep,
    definition: WorkflowDefinition,
    exc: Exception,
) -> None:
    err = f"{type(exc).__name__}: {exc}"
    step.error = err
    step.lease_owner = None
    step.lease_expires_at = None
    logger.warning("step_failed %s %s", step.step_key, err)
    write_audit(
        db,
        org_id=run.org_id,
        event_type="step.failed",
        message=err,
        run_id=run.id,
        step_id=step.id,
        data={"traceback": traceback.format_exc()[-2000:]},
    )

    if step.attempt < step.max_attempts:
        delay = min(60, 2 ** step.attempt)
        step.status = StepStatus.pending
        step.next_retry_at = _utcnow() + timedelta(seconds=delay)
        write_audit(
            db,
            org_id=run.org_id,
            event_type="step.retry_scheduled",
            message=f"Retry in {delay}s (attempt {step.attempt}/{step.max_attempts})",
            run_id=run.id,
            step_id=step.id,
        )
        db.commit()
        incr_metric("steps_retried")
        return

    await _fail_permanent(db, run, step, err)


async def _fail_permanent(db: Session, run: WorkflowRun, step: RunStep, reason: str) -> None:
    step.status = StepStatus.dead_lettered
    step.finished_at = _utcnow()
    step.error = reason
    dlq = DeadLetter(
        org_id=run.org_id,
        run_id=run.id,
        step_id=step.id,
        reason=reason,
        payload={"step_key": step.step_key, "attempt": step.attempt, "input": step.input},
    )
    db.add(dlq)
    run.status = RunStatus.failed
    run.error = reason
    run.finished_at = _utcnow()
    write_audit(
        db,
        org_id=run.org_id,
        event_type="step.dead_lettered",
        message=reason,
        run_id=run.id,
        step_id=step.id,
    )
    db.commit()
    incr_metric("dead_letters")


async def worker_loop() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logger.info("worker_starting id=%s", settings.worker_id)
    client = get_redis()

    while True:
        db = SessionLocal()
        try:
            reclaim_expired_leases(db)
            promote_due_retries(db)
        finally:
            db.close()

        item = client.brpop(settings.redis_queue_key, timeout=max(1, int(settings.poll_interval_seconds)))
        if not item:
            await asyncio.sleep(0.1)
            continue
        _, step_id = item
        try:
            await process_step(UUID(step_id))
        except Exception:
            logger.exception("process_step_crash step_id=%s", step_id)
            await asyncio.sleep(0.5)


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import AuthContext, get_current_auth
from app.config import get_settings
from app.db import get_db
from app.engine.graph import WorkflowGraph
from app.engine.runner import advance_after_step, create_run
from app.models.audit import AuditEvent
from app.models.workflow import (
    ApprovalStatus,
    ApprovalTask,
    DeadLetter,
    RunStatus,
    RunStep,
    StepStatus,
    TriggerType,
    WorkflowDefinition,
    WorkflowRun,
)
from app.schemas import (
    ApprovalDecision,
    ApprovalOut,
    AuditOut,
    DeadLetterOut,
    RunCreate,
    RunOut,
    StepOut,
    WorkflowCreate,
    WorkflowOut,
)
from app.services.audit import write_audit
from app.services.queue import enqueue_step, incr_metric
from app.services.ratelimit import rate_limit

router = APIRouter(prefix="/api", tags=["workflows"])
settings = get_settings()


def _run_out(run: WorkflowRun) -> RunOut:
    steps = [
        StepOut(
            id=s.id,
            step_key=s.step_key,
            step_type=s.step_type,
            sequence=s.sequence,
            status=s.status.value,
            attempt=s.attempt,
            max_attempts=s.max_attempts,
            error=s.error,
            output=s.output,
            started_at=s.started_at,
            finished_at=s.finished_at,
        )
        for s in sorted(run.steps, key=lambda x: x.sequence)
    ]
    return RunOut(
        id=run.id,
        definition_id=run.definition_id,
        status=run.status.value,
        trigger_type=run.trigger_type.value,
        input=run.input or {},
        output=run.output,
        error=run.error,
        current_step_key=run.current_step_key,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        steps=steps,
    )


@router.get("/workflows", response_model=list[WorkflowOut])
def list_workflows(db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth)):
    rows = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.org_id == auth.org.id, WorkflowDefinition.is_active.is_(True))
        .order_by(WorkflowDefinition.created_at.desc())
        .all()
    )
    return [WorkflowOut.model_validate(r) for r in rows]


@router.post("/workflows", response_model=WorkflowOut, status_code=201)
def create_workflow(
    body: WorkflowCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
):
    WorkflowGraph.model_validate(body.graph)
    existing = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.org_id == auth.org.id, WorkflowDefinition.slug == body.slug)
        .order_by(WorkflowDefinition.version.desc())
        .first()
    )
    version = (existing.version + 1) if existing else 1
    wf = WorkflowDefinition(
        org_id=auth.org.id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        version=version,
        graph=body.graph,
    )
    db.add(wf)
    write_audit(
        db,
        org_id=auth.org.id,
        event_type="workflow.created",
        message=f"Created workflow {body.slug} v{version}",
        actor_user_id=auth.user.id if auth.user else None,
        data={"slug": body.slug, "version": version},
    )
    db.commit()
    db.refresh(wf)
    return WorkflowOut.model_validate(wf)


@router.get("/workflows/{workflow_id}", response_model=WorkflowOut)
def get_workflow(workflow_id: UUID, db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth)):
    wf = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.id == workflow_id, WorkflowDefinition.org_id == auth.org.id)
        .first()
    )
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return WorkflowOut.model_validate(wf)


@router.post("/runs", response_model=RunOut, status_code=201)
def start_run(body: RunCreate, db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth)):
    q = db.query(WorkflowDefinition).filter(WorkflowDefinition.org_id == auth.org.id, WorkflowDefinition.is_active.is_(True))
    if body.definition_id:
        definition = q.filter(WorkflowDefinition.id == body.definition_id).first()
    elif body.slug:
        definition = (
            q.filter(WorkflowDefinition.slug == body.slug).order_by(WorkflowDefinition.version.desc()).first()
        )
    else:
        raise HTTPException(400, "Provide definition_id or slug")
    if not definition:
        raise HTTPException(404, "Workflow not found")

    try:
        trigger = TriggerType(body.trigger_type)
    except ValueError as exc:
        raise HTTPException(400, "Invalid trigger_type") from exc

    run = create_run(
        db,
        org_id=auth.org.id,
        definition=definition,
        input_data=body.input,
        trigger_type=trigger,
        created_by=auth.user.id if auth.user else None,
    )
    run = (
        db.query(WorkflowRun)
        .options(joinedload(WorkflowRun.steps))
        .filter(WorkflowRun.id == run.id)
        .first()
    )
    assert run is not None
    return _run_out(run)


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth), limit: int = 50):
    runs = (
        db.query(WorkflowRun)
        .options(joinedload(WorkflowRun.steps))
        .filter(WorkflowRun.org_id == auth.org.id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [_run_out(r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: UUID, db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth)):
    run = (
        db.query(WorkflowRun)
        .options(joinedload(WorkflowRun.steps))
        .filter(WorkflowRun.id == run_id, WorkflowRun.org_id == auth.org.id)
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")
    return _run_out(run)


@router.post("/webhooks/{slug}", response_model=RunOut, status_code=201)
async def webhook_trigger(
    slug: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
):
    rate_limit(request, key="webhook", limit=60, window_seconds=60)
    definition = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.org_id == auth.org.id,
            WorkflowDefinition.slug == slug,
            WorkflowDefinition.is_active.is_(True),
        )
        .order_by(WorkflowDefinition.version.desc())
        .first()
    )
    if not definition:
        raise HTTPException(404, "Workflow not found")
    run = create_run(
        db,
        org_id=auth.org.id,
        definition=definition,
        input_data=payload,
        trigger_type=TriggerType.webhook,
        created_by=auth.user.id if auth.user else None,
    )
    run = db.query(WorkflowRun).options(joinedload(WorkflowRun.steps)).filter(WorkflowRun.id == run.id).first()
    assert run is not None
    return _run_out(run)


@router.post("/runs/csv", response_model=RunOut, status_code=201)
async def csv_upload_run(
    file: UploadFile = File(...),
    slug: str = "ops-intake",
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
):
    definition = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.org_id == auth.org.id,
            WorkflowDefinition.slug == slug,
            WorkflowDefinition.is_active.is_(True),
        )
        .order_by(WorkflowDefinition.version.desc())
        .first()
    )
    if not definition:
        raise HTTPException(404, "Workflow not found")
    text = (await file.read()).decode("utf-8")
    run = create_run(
        db,
        org_id=auth.org.id,
        definition=definition,
        input_data={"csv_text": text},
        trigger_type=TriggerType.csv_upload,
        created_by=auth.user.id if auth.user else None,
    )
    run = db.query(WorkflowRun).options(joinedload(WorkflowRun.steps)).filter(WorkflowRun.id == run.id).first()
    assert run is not None
    return _run_out(run)


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth)):
    rows = (
        db.query(ApprovalTask)
        .filter(ApprovalTask.org_id == auth.org.id, ApprovalTask.status == ApprovalStatus.pending)
        .order_by(ApprovalTask.created_at.asc())
        .all()
    )
    return [ApprovalOut.model_validate(r) for r in rows]


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalOut)
def decide_approval(
    approval_id: UUID,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
):
    from datetime import datetime, timezone

    approval = (
        db.query(ApprovalTask)
        .filter(ApprovalTask.id == approval_id, ApprovalTask.org_id == auth.org.id)
        .first()
    )
    if not approval:
        raise HTTPException(404, "Approval not found")
    if approval.status != ApprovalStatus.pending:
        raise HTTPException(400, "Already decided")

    run = (
        db.query(WorkflowRun)
        .options(joinedload(WorkflowRun.steps), joinedload(WorkflowRun.definition))
        .filter(WorkflowRun.id == approval.run_id)
        .first()
    )
    step = db.query(RunStep).filter(RunStep.id == approval.step_id).first()
    if not run or not step:
        raise HTTPException(404, "Run/step missing")

    approved = body.decision == "approve"
    approval.status = ApprovalStatus.approved if approved else ApprovalStatus.rejected
    approval.decision_note = body.note
    approval.decided_by = auth.user.id if auth.user else None
    approval.decided_at = datetime.now(timezone.utc)

    step.status = StepStatus.completed
    step.output = {
        "decision": body.decision,
        "note": body.note,
        "payload": approval.payload,
    }
    step.finished_at = datetime.now(timezone.utc)

    write_audit(
        db,
        org_id=auth.org.id,
        event_type="approval.decided",
        message=f"Approval {body.decision}",
        actor_user_id=auth.user.id if auth.user else None,
        run_id=run.id,
        step_id=step.id,
        data={"decision": body.decision},
    )
    db.flush()

    advance_after_step(
        db,
        run=run,
        completed_step=step,
        definition=run.definition,
        rejected=not approved,
    )
    db.commit()
    db.refresh(approval)
    incr_metric("approvals_decided")
    return ApprovalOut.model_validate(approval)


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
    run_id: UUID | None = None,
    limit: int = 100,
):
    q = db.query(AuditEvent).filter(AuditEvent.org_id == auth.org.id)
    if run_id:
        q = q.filter(AuditEvent.run_id == run_id)
    rows = q.order_by(AuditEvent.created_at.desc()).limit(min(limit, 200)).all()
    return [AuditOut.model_validate(r) for r in rows]


@router.get("/dead-letters", response_model=list[DeadLetterOut])
def list_dead_letters(db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_auth)):
    rows = (
        db.query(DeadLetter)
        .filter(DeadLetter.org_id == auth.org.id)
        .order_by(DeadLetter.created_at.desc())
        .limit(100)
        .all()
    )
    return [DeadLetterOut.model_validate(r) for r in rows]


@router.post("/dead-letters/{dlq_id}/replay", response_model=DeadLetterOut)
def replay_dead_letter(
    dlq_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
):
    from datetime import datetime, timezone

    dlq = db.query(DeadLetter).filter(DeadLetter.id == dlq_id, DeadLetter.org_id == auth.org.id).first()
    if not dlq:
        raise HTTPException(404, "Not found")
    if dlq.replayed_at:
        raise HTTPException(400, "Already replayed")

    step = db.query(RunStep).filter(RunStep.id == dlq.step_id).first()
    run = db.query(WorkflowRun).filter(WorkflowRun.id == dlq.run_id).first()
    if not step or not run:
        raise HTTPException(404, "Step/run missing")

    step.status = StepStatus.ready
    step.attempt = 0
    step.error = None
    step.next_retry_at = None
    step.finished_at = None
    run.status = RunStatus.running
    run.error = None
    run.finished_at = None
    dlq.replayed_at = datetime.now(timezone.utc)
    write_audit(
        db,
        org_id=auth.org.id,
        event_type="dead_letter.replayed",
        message="Dead letter replayed",
        actor_user_id=auth.user.id if auth.user else None,
        run_id=run.id,
        step_id=step.id,
    )
    db.commit()
    enqueue_step(str(step.id))
    db.refresh(dlq)
    return DeadLetterOut.model_validate(dlq)


@router.get("/exports/{filename}")
def download_export(filename: str, auth: AuthContext = Depends(get_current_auth)):
    if "/" in filename or ".." in filename or not filename.endswith(".csv"):
        raise HTTPException(400, "Invalid filename")
    path = Path(settings.export_dir) / filename
    if not path.exists():
        raise HTTPException(404, "Export not found")
    return FileResponse(path, filename=filename, media_type="text/csv")

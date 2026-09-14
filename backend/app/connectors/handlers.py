from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from app.config import get_settings
from app.services.queue import post_slack

logger = logging.getLogger("relay.connectors")
settings = get_settings()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StepResult:
    def __init__(
        self,
        output: dict[str, Any] | None = None,
        *,
        needs_approval: bool = False,
        approval_title: str | None = None,
        approval_payload: dict[str, Any] | None = None,
    ):
        self.output = output or {}
        self.needs_approval = needs_approval
        self.approval_title = approval_title or "Approval required"
        self.approval_payload = approval_payload or {}


async def execute_step(step_type: str, config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    handlers = {
        "csv.ingest": handle_csv_ingest,
        "data.validate": handle_validate,
        "human.approve": handle_human_approve,
        "csv.export": handle_csv_export,
        "slack.notify": handle_slack_notify,
        "hubspot.upsert": handle_hubspot_upsert,
        "http.webhook": handle_http_webhook,
        "email.stub": handle_email_stub,
    }
    handler = handlers.get(step_type)
    if not handler:
        raise ValueError(f"Unknown step type: {step_type}")
    return await handler(config, context, run_id=run_id)


def _rows_from_context(context: dict[str, Any], source_field: str = "rows") -> list[dict[str, Any]]:
    run_input = context.get("run_input") or {}
    if source_field in run_input:
        rows = run_input[source_field]
        if isinstance(rows, list):
            return rows
    if "ingest" in context and isinstance(context["ingest"].get("rows"), list):
        return context["ingest"]["rows"]
    if "csv_text" in run_input:
        return _parse_csv_text(run_input["csv_text"])
    return []


def _parse_csv_text(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


async def handle_csv_ingest(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    source_field = config.get("source_field", "rows")
    rows = _rows_from_context(context, source_field)
    if not rows:
        run_input = context.get("run_input") or {}
        if run_input.get("use_fixture"):
            rows = _fixture_rows()
    if not rows:
        raise ValueError("No rows to ingest. Provide input.rows, input.csv_text, or use_fixture=true.")
    return StepResult(output={"rows": rows, "count": len(rows)})


def _fixture_rows() -> list[dict[str, Any]]:
    return [
        {"name": "Aisha Khan", "email": "aisha@acme.test", "company": "Acme Labs", "title": "Ops Lead"},
        {"name": "Ben Ortiz", "email": "ben@northwind.test", "company": "Northwind", "title": "Coordinator"},
        {"name": "Bad Row", "email": "not-an-email", "company": "", "title": "N/A"},
        {"name": "Chen Wei", "email": "chen@globex.test", "company": "Globex", "title": "Analyst"},
        {"name": "Dana Lee", "email": "  DANA@initech.test ", "company": "Initech", "title": "Manager"},
    ]


async def handle_validate(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    required = config.get("required_fields") or ["email", "name"]
    normalize_email = bool(config.get("normalize_email", True))
    rows = []
    if "ingest" in context:
        rows = context["ingest"].get("rows") or []
    else:
        rows = _rows_from_context(context)

    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        if normalize_email and isinstance(cleaned.get("email"), str):
            cleaned["email"] = cleaned["email"].lower()
        missing = [f for f in required if not cleaned.get(f)]
        email = cleaned.get("email")
        if email and not EMAIL_RE.match(str(email)):
            missing.append("email_format")
        if missing:
            errors.append({"index": idx, "row": cleaned, "issues": missing})
        else:
            valid.append(cleaned)

    return StepResult(
        output={
            "valid_rows": valid,
            "invalid_rows": errors,
            "valid_count": len(valid),
            "invalid_count": len(errors),
            "summary": f"{len(valid)} valid / {len(errors)} invalid of {len(rows)}",
        }
    )


async def handle_human_approve(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    validate_out = context.get("validate") or {}
    payload = {
        "summary": validate_out.get("summary"),
        "valid_count": validate_out.get("valid_count", 0),
        "invalid_count": validate_out.get("invalid_count", 0),
        "sample_valid": (validate_out.get("valid_rows") or [])[:5],
        "sample_invalid": (validate_out.get("invalid_rows") or [])[:5],
    }
    return StepResult(
        output={"awaiting": True},
        needs_approval=True,
        approval_title=config.get("title") or "Approve batch",
        approval_payload=payload,
    )


async def handle_csv_export(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    validate_out = context.get("validate") or {}
    rows = validate_out.get("valid_rows") or []
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"run-{run_id}.csv"

    fieldnames = list(rows[0].keys()) if rows else ["name", "email", "company", "title"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return StepResult(
        output={
            "path": str(path),
            "filename": path.name,
            "row_count": len(rows),
            "download_hint": f"/api/exports/{path.name}",
        }
    )


async def handle_slack_notify(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    validate_out = context.get("validate") or {}
    export_out = context.get("export") or {}
    template = config.get("message_template") or "Relay run {run_id} finished ({valid_count} rows)."
    text = template.format(
        run_id=str(run_id),
        valid_count=validate_out.get("valid_count", 0),
        invalid_count=validate_out.get("invalid_count", 0),
        export=export_out.get("filename", ""),
    )
    result = await post_slack(text)
    return StepResult(output={"notified": True, "slack": result, "text": text})


async def handle_hubspot_upsert(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    """Upsert contacts by email. Stubs when HUBSPOT_ACCESS_TOKEN is unset."""
    validate_out = context.get("validate") or {}
    rows = validate_out.get("valid_rows") or []
    token = settings.hubspot_access_token.strip()
    skip_if_unconfigured = bool(config.get("skip_if_unconfigured", True))

    if not token:
        if skip_if_unconfigured:
            logger.info("hubspot_stub run_id=%s rows=%s", run_id, len(rows))
            return StepResult(
                output={
                    "stub": True,
                    "skipped": True,
                    "reason": "HUBSPOT_ACCESS_TOKEN not configured",
                    "row_count": len(rows),
                }
            )
        raise ValueError("HUBSPOT_ACCESS_TOKEN required for hubspot.upsert")

    # HubSpot batch upsert — max 100 per request
    inputs = []
    for row in rows[:100]:
        email = row.get("email")
        if not email:
            continue
        props = {
            "email": email,
            "firstname": (row.get("name") or "").split(" ", 1)[0] or email,
            "lastname": " ".join((row.get("name") or "").split(" ")[1:]) or "Relay",
            "company": row.get("company") or "",
            "jobtitle": row.get("title") or "",
        }
        inputs.append(
            {
                "idProperty": "email",
                "id": email,
                "properties": props,
            }
        )

    if not inputs:
        return StepResult(output={"upserted": 0, "message": "No emails to upsert"})

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"inputs": inputs},
        )
        if resp.status_code >= 400:
            raise ValueError(f"HubSpot upsert failed ({resp.status_code}): {resp.text[:500]}")
        body = resp.json()

    return StepResult(
        output={
            "upserted": len(inputs),
            "status_code": resp.status_code,
            "results": len(body.get("results") or []),
        }
    )


async def handle_http_webhook(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    url = config.get("url")
    if not url:
        raise ValueError("http.webhook requires config.url")
    payload = {
        "run_id": str(run_id),
        "context_keys": list(context.keys()),
        "validate": context.get("validate"),
        "export": context.get("export"),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        body: Any
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text[:500]}
    return StepResult(output={"status_code": resp.status_code, "body": body})


async def handle_email_stub(config: dict[str, Any], context: dict[str, Any], *, run_id: UUID) -> StepResult:
    to = config.get("to") or "ops@example.com"
    subject = config.get("subject") or f"Relay run {run_id}"
    logger.info("email_stub", extra={"to": to, "subject": subject, "run_id": str(run_id)})
    return StepResult(output={"stub": True, "to": to, "subject": subject})

"""Seed admin org, user, API key, and Ops Intake workflow."""

from __future__ import annotations

import logging
import secrets

from sqlalchemy.orm import Session

from app.auth.security import hash_api_key, hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.engine.graph import OPS_INTAKE_GRAPH
from app.models.auth import ApiKey, Membership, MembershipRole, Organization, User
from app.models.workflow import WorkflowDefinition
from app.services.audit import write_audit

logger = logging.getLogger("relay.seed")
settings = get_settings()


def seed(db: Session) -> None:
    org = db.query(Organization).filter(Organization.slug == "demo").first()
    if not org:
        org = Organization(name="Relay Demo", slug="demo")
        db.add(org)
        db.flush()
        logger.info("created_org demo")

    user = db.query(User).filter(User.email == settings.admin_email.lower()).first()
    if not user:
        user = User(
            email=settings.admin_email.lower(),
            name=settings.admin_name,
            hashed_password=hash_password(settings.admin_password),
        )
        db.add(user)
        db.flush()
        logger.info("created_admin %s", settings.admin_email)

    membership = (
        db.query(Membership)
        .filter(Membership.org_id == org.id, Membership.user_id == user.id)
        .first()
    )
    if not membership:
        db.add(
            Membership(org_id=org.id, user_id=user.id, role=MembershipRole.owner)
        )

    existing_key = db.query(ApiKey).filter(ApiKey.org_id == org.id, ApiKey.name == "demo").first()
    if not existing_key:
        raw = f"rl_demo_{secrets.token_hex(16)}"
        db.add(
            ApiKey(
                org_id=org.id,
                name="demo",
                key_prefix=raw[:12],
                key_hash=hash_api_key(raw),
                notes=f"Seeded demo key — rotate in production. Prefixed value stored only at seed time in logs.",
            )
        )
        logger.info("seeded_api_key_prefix=%s (full key only in first seed log if printed)", raw[:12])
        # Intentionally not printing full key in production logs; local demo can read from CLIENT_DEMO
        write_audit(
            db,
            org_id=org.id,
            event_type="seed.api_key",
            message="Demo API key created",
            data={"prefix": raw[:12]},
        )

    wf = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.org_id == org.id, WorkflowDefinition.slug == "ops-intake")
        .first()
    )
    if not wf:
        db.add(
            WorkflowDefinition(
                org_id=org.id,
                name="Ops Intake Pipeline",
                slug="ops-intake",
                description="CSV/webhook intake → validate → human approve → export CSV → Slack notify. Zero paid API keys required.",
                version=1,
                graph=OPS_INTAKE_GRAPH,
                is_active=True,
            )
        )
        write_audit(
            db,
            org_id=org.id,
            event_type="seed.workflow",
            message="Seeded ops-intake workflow",
            actor_user_id=user.id,
        )
        logger.info("seeded_workflow ops-intake")

    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        seed(db)
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

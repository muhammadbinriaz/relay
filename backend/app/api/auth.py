from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext, get_current_auth
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_api_key,
    verify_password,
)
from app.db import get_db
from app.models.auth import ApiKey, Membership, MembershipRole, Organization, User
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    LoginRequest,
    MeResponse,
    OrgOut,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id)
        .order_by(Membership.created_at.asc())
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership")

    org = db.query(Organization).filter(Organization.id == membership.org_id).first()
    assert org is not None

    access = create_access_token(str(user.id), {"org_id": str(org.id), "role": membership.role.value})
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh, org_id=org.id, org_slug=org.slug)


@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No organization")
    org = db.query(Organization).filter(Organization.id == membership.org_id).first()
    assert org is not None
    access = create_access_token(str(user.id), {"org_id": str(org.id), "role": membership.role.value})
    new_refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=new_refresh, org_id=org.id, org_slug=org.slug)


@router.get("/me", response_model=MeResponse)
def me(auth: AuthContext = Depends(get_current_auth)) -> MeResponse:
    if not auth.user or not auth.membership:
        raise HTTPException(status_code=400, detail="API keys cannot call /me")
    return MeResponse(
        user=UserOut.model_validate(auth.user),
        org=OrgOut.model_validate(auth.org),
        role=auth.membership.role.value,
    )


@router.post("/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> ApiKeyCreated:
    if auth.via != "jwt" or not auth.membership:
        raise HTTPException(status_code=403, detail="JWT required")
    if auth.membership.role not in (MembershipRole.owner, MembershipRole.admin):
        raise HTTPException(status_code=403, detail="Admin required")

    raw = f"rl_{uuid4().hex}{uuid4().hex[:8]}"
    key = ApiKey(
        org_id=auth.org.id,
        name=body.name,
        key_prefix=raw[:12],
        key_hash=hash_api_key(raw),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return ApiKeyCreated(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        api_key=raw,
        created_at=key.created_at,
    )

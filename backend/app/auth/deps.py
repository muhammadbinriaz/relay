from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.auth.security import decode_token, verify_api_key
from app.db import get_db
from app.models.auth import ApiKey, Membership, MembershipRole, Organization, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User | None
    org: Organization
    membership: Membership | None
    via: str  # jwt | api_key


def _membership_for(db: Session, user_id: UUID, org_id: UUID) -> Membership | None:
    return (
        db.query(Membership)
        .options(joinedload(Membership.organization))
        .filter(Membership.user_id == user_id, Membership.org_id == org_id)
        .first()
    )


def get_current_auth(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
) -> AuthContext:
    if x_api_key:
        prefix = x_api_key[:12]
        candidates = (
            db.query(ApiKey)
            .options(joinedload(ApiKey.organization))
            .filter(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True), ApiKey.revoked_at.is_(None))
            .all()
        )
        for key in candidates:
            if verify_api_key(x_api_key, key.key_hash):
                return AuthContext(user=None, org=key.organization, membership=None, via="api_key")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    org_id = x_org_id or payload.get("org_id")
    if not user_id or not org_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing org context")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    membership = _membership_for(db, UUID(user_id), UUID(org_id))
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this org")

    return AuthContext(user=user, org=membership.organization, membership=membership, via="jwt")


def require_roles(*roles: MembershipRole):
    def _dep(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if auth.via == "api_key":
            return auth
        if not auth.membership or auth.membership.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return auth

    return _dep

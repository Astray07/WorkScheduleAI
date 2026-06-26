from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.signed_actor_tokens import (
    SignedActorTokenError,
    verify_actor_token,
)
from work_schedule_ai.db.models import Membership


RBAC_ROLES = ["owner", "admin", "scheduler", "viewer", "employee", "member"]
ADMIN_ROLES = frozenset({"owner", "admin", "scheduler"})
READ_ROLES = frozenset({"owner", "admin", "scheduler", "viewer"})
TRUSTED_UPSTREAM_HEADER_ACTOR_MODE = "trusted_upstream_header"
SIGNED_ACTOR_TOKEN_MODE = "signed_actor_token"


@dataclass(frozen=True)
class ActorContext:
    user_id: str | None
    role: str
    auth_required: bool


def is_auth_required() -> bool:
    return os.environ.get("WORKSCHEDULEAI_AUTH_REQUIRED") == "1"


def is_trusted_upstream_auth_configured() -> bool:
    return os.environ.get("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH") == "1"


def is_signed_actor_auth_configured() -> bool:
    return bool(os.environ.get("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET"))


def actor_extraction_mode() -> str:
    if is_signed_actor_auth_configured():
        return SIGNED_ACTOR_TOKEN_MODE
    return TRUSTED_UPSTREAM_HEADER_ACTOR_MODE


def enforce_organization_access(
    db_session: Session,
    request: Request,
    organization_id: str,
) -> ActorContext:
    auth_required = is_auth_required()
    user_id = request.headers.get("X-User-Id")
    if not auth_required:
        actor = ActorContext(user_id=user_id, role="admin", auth_required=False)
        db_session.info["actor_context"] = actor
        return actor
    if is_signed_actor_auth_configured():
        actor_user_id = _user_id_from_signed_actor_token(request, organization_id)
        if actor_user_id is not None:
            return _actor_from_membership(
                db_session=db_session,
                organization_id=organization_id,
                user_id=actor_user_id,
            )
        if not is_trusted_upstream_auth_configured():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Authorization Bearer actor token is required.",
                    "field": "Authorization",
                },
            )
    if not is_trusted_upstream_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TRUSTED_UPSTREAM_AUTH_REQUIRED",
                "message": (
                    "Organization-scoped auth requires a configured trusted "
                    "upstream before X-User-Id can be accepted."
                ),
                "field": "WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH",
            },
        )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "X-User-Id header is required when auth is enabled.",
                "field": "X-User-Id",
            },
        )
    return _actor_from_membership(
        db_session=db_session,
        organization_id=organization_id,
        user_id=user_id,
    )


def _user_id_from_signed_actor_token(
    request: Request,
    organization_id: str,
) -> str | None:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_ACTOR_TOKEN",
                "message": "Authorization must be a Bearer actor token.",
                "field": "Authorization",
            },
        )
    try:
        claims = verify_actor_token(
            token,
            secret=os.environ.get("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", ""),
            organization_id=organization_id,
        )
    except SignedActorTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_ACTOR_TOKEN",
                "message": str(exc),
                "field": "Authorization",
            },
        ) from exc
    return claims.user_id


def _actor_from_membership(
    *,
    db_session: Session,
    organization_id: str,
    user_id: str,
) -> ActorContext:
    membership = db_session.execute(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ORGANIZATION_ACCESS_DENIED",
                "message": "User is not a member of this organization.",
                "field": "organization_id",
            },
        )
    actor = ActorContext(
        user_id=user_id,
        role=membership.role,
        auth_required=True,
    )
    db_session.info["actor_context"] = actor
    return actor


def current_actor(db_session: Session) -> ActorContext:
    actor = db_session.info.get("actor_context")
    if isinstance(actor, ActorContext):
        return actor
    return ActorContext(user_id=None, role="admin", auth_required=False)


def require_roles(
    db_session: Session,
    allowed_roles: set[str] | frozenset[str],
) -> ActorContext:
    actor = current_actor(db_session)
    if not actor.auth_required:
        return actor
    if actor.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ROLE_NOT_ALLOWED",
                "message": "User role is not allowed for this operation.",
                "field": "role",
            },
        )
    return actor

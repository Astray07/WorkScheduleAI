from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session, set_tenant_context
from work_schedule_ai.api.passwords import DUMMY_PASSWORD_HASH, verify_password
from work_schedule_ai.api.security import (
    SIGNED_ACTOR_SECRET_MIN_LENGTH,
    is_signed_actor_secret_strong,
)
from work_schedule_ai.api.signed_actor_tokens import (
    SignedActorTokenError,
    sign_actor_token,
    verify_actor_token,
)
from work_schedule_ai.db.models import Membership, User, utc_now


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)
    organization_id: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_at: datetime
    organization_id: str
    user_id: str
    role: str


class SessionResponse(BaseModel):
    organization_id: str
    user_id: str
    email: str
    name: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    db_session: Session = Depends(get_db_session),
) -> LoginResponse:
    secret = _signed_actor_secret()
    set_tenant_context(db_session, request.organization_id)
    users = list(
        db_session.execute(
            select(User)
            .where(func.lower(User.email) == request.email.strip().lower())
            .limit(2)
        ).scalars()
    )
    if len(users) != 1:
        verify_password(request.password, DUMMY_PASSWORD_HASH)
        raise _invalid_credentials()
    user = users[0]
    if not verify_password(request.password, user.password_hash):
        raise _invalid_credentials()
    membership = _membership_or_forbidden(
        db_session=db_session,
        organization_id=request.organization_id,
        user_id=user.id,
    )
    now = utc_now()
    expires_at = now + timedelta(hours=8)
    token = sign_actor_token(
        secret=secret,
        organization_id=request.organization_id,
        user_id=user.id,
        issued_at=now,
        expires_at=expires_at,
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        organization_id=request.organization_id,
        user_id=user.id,
        role=membership.role,
    )


@router.get("/session", response_model=SessionResponse)
def session_context(
    organization_id: str = Query(min_length=1),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db_session: Session = Depends(get_db_session),
) -> SessionResponse:
    set_tenant_context(db_session, organization_id)
    claims = _claims_from_authorization(
        authorization=authorization,
        organization_id=organization_id,
    )
    membership = _membership_or_forbidden(
        db_session=db_session,
        organization_id=organization_id,
        user_id=claims.user_id,
    )
    user = db_session.get(User, claims.user_id)
    if user is None:
        raise _invalid_actor_token("token user does not exist")
    return SessionResponse(
        organization_id=organization_id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
    )


def _claims_from_authorization(*, authorization: str | None, organization_id: str):
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Authorization Bearer actor token is required.",
                "field": "Authorization",
            },
        )
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        raise _invalid_actor_token("Authorization must be a Bearer actor token.")
    try:
        return verify_actor_token(
            token,
            secret=_signed_actor_secret(),
            organization_id=organization_id,
        )
    except SignedActorTokenError as exc:
        raise _invalid_actor_token(str(exc)) from exc


def _membership_or_forbidden(
    *,
    db_session: Session,
    organization_id: str,
    user_id: str,
) -> Membership:
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
    return membership


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "INVALID_CREDENTIALS",
            "message": "Email or password is invalid.",
            "field": "email",
        },
    )


def _invalid_actor_token(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "INVALID_ACTOR_TOKEN",
            "message": message,
            "field": "Authorization",
        },
    )


def _signed_actor_secret() -> str:
    secret = os.environ.get("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SIGNED_ACTOR_SECRET_REQUIRED",
                "message": "Login sessions require WORKSCHEDULEAI_SIGNED_ACTOR_SECRET.",
                "field": "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET",
            },
        )
    if not is_signed_actor_secret_strong(secret):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SIGNED_ACTOR_SECRET_WEAK",
                "message": (
                    "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET must be at least "
                    f"{SIGNED_ACTOR_SECRET_MIN_LENGTH} characters."
                ),
                "field": "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET",
            },
        )
    return secret

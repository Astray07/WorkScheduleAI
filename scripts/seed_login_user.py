from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from scripts.seed_demo import DEMO_ORGANIZATION_ID
from work_schedule_ai.api.dependencies import SessionLocal
from work_schedule_ai.api.passwords import hash_password
from work_schedule_ai.db.models import Membership, Organization, User


DEFAULT_EMAIL = "demo.admin@example.com"
DEFAULT_NAME = "Demo Admin"
DEFAULT_ORGANIZATION_NAME = "WorkScheduleAI Demo Clinic"
DEFAULT_ROLE = "admin"
VALID_ROLES = {"owner", "admin", "scheduler", "viewer", "employee", "member"}


@dataclass(frozen=True)
class SeedLoginUserSummary:
    organization_id: str
    user_id: str
    email: str
    role: str
    password_source: str
    temporary_password: str | None
    status: str


def seed_login_user(db_session: Session) -> SeedLoginUserSummary:
    organization_id = _env("WORKSCHEDULEAI_SEED_LOGIN_ORGANIZATION_ID", DEMO_ORGANIZATION_ID)
    organization_name = _env(
        "WORKSCHEDULEAI_SEED_LOGIN_ORGANIZATION_NAME",
        DEFAULT_ORGANIZATION_NAME,
    )
    email = _env("WORKSCHEDULEAI_SEED_LOGIN_EMAIL", DEFAULT_EMAIL).strip().lower()
    name = _env("WORKSCHEDULEAI_SEED_LOGIN_NAME", DEFAULT_NAME)
    role = _env("WORKSCHEDULEAI_SEED_LOGIN_ROLE", DEFAULT_ROLE)
    if role not in VALID_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    password = os.environ.get("WORKSCHEDULEAI_SEED_LOGIN_PASSWORD")
    password_source = "environment"
    if not password:
        password = secrets.token_urlsafe(24)
        password_source = "generated"

    _ensure_organization(db_session, organization_id, organization_name)
    user = _upsert_user(db_session, email=email, name=name, password=password)
    _upsert_membership(
        db_session,
        organization_id=organization_id,
        user_id=user.id,
        role=role,
    )
    db_session.commit()
    return SeedLoginUserSummary(
        organization_id=organization_id,
        user_id=user.id,
        email=email,
        role=role,
        password_source=password_source,
        temporary_password=password if password_source == "generated" else None,
        status="seeded",
    )


def main() -> None:
    with SessionLocal() as session:
        summary = seed_login_user(session)
    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _ensure_organization(
    db_session: Session,
    organization_id: str,
    organization_name: str,
) -> None:
    if db_session.get(Organization, organization_id) is not None:
        return
    db_session.add(
        Organization(
            id=organization_id,
            name=organization_name,
            timezone="Asia/Seoul",
        )
    )


def _upsert_user(
    db_session: Session,
    *,
    email: str,
    name: str,
    password: str,
) -> User:
    users = list(
        db_session.execute(
            select(User).where(func.lower(User.email) == email.lower()).limit(2)
        ).scalars()
    )
    if len(users) > 1:
        raise ValueError(f"Ambiguous user email: {email}")
    password_hash = hash_password(password)
    if users:
        user = users[0]
        user.email = email
        user.name = name
        user.password_hash = password_hash
        return user
    user = User(
        id=_user_id_for_email(email),
        email=email,
        name=name,
        password_hash=password_hash,
    )
    db_session.add(user)
    return user


def _upsert_membership(
    db_session: Session,
    *,
    organization_id: str,
    user_id: str,
    role: str,
) -> None:
    membership = db_session.execute(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        db_session.add(
            Membership(
                organization_id=organization_id,
                user_id=user_id,
                role=role,
            )
        )
        return
    membership.role = role


def _user_id_for_email(email: str) -> str:
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    return f"user_seed_{digest}"


if __name__ == "__main__":
    main()

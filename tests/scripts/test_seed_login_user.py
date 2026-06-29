from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from scripts.seed_demo import DEMO_ORGANIZATION_ID
from scripts.seed_login_user import (
    DEFAULT_EMAIL,
    DEFAULT_ROLE,
    seed_login_user,
)
from work_schedule_ai.api.passwords import verify_password
from work_schedule_ai.db.models import Base, Membership, Organization, User


def test_seed_login_user_creates_demo_admin(monkeypatch, db_session: Session):
    monkeypatch.setenv("WORKSCHEDULEAI_SEED_LOGIN_PASSWORD", "demo-password")

    summary = seed_login_user(db_session)

    user = db_session.execute(select(User)).scalar_one()
    membership = db_session.execute(select(Membership)).scalar_one()
    organization = db_session.get(Organization, DEMO_ORGANIZATION_ID)
    assert organization is not None
    assert summary.organization_id == DEMO_ORGANIZATION_ID
    assert summary.email == DEFAULT_EMAIL
    assert summary.role == DEFAULT_ROLE
    assert summary.password_source == "environment"
    assert summary.temporary_password is None
    assert user.email == DEFAULT_EMAIL
    assert verify_password("demo-password", user.password_hash) is True
    assert membership.organization_id == DEMO_ORGANIZATION_ID
    assert membership.user_id == user.id
    assert membership.role == DEFAULT_ROLE


def test_seed_login_user_generates_temporary_password(monkeypatch, db_session: Session):
    monkeypatch.delenv("WORKSCHEDULEAI_SEED_LOGIN_PASSWORD", raising=False)

    summary = seed_login_user(db_session)

    user = db_session.execute(select(User)).scalar_one()
    assert summary.password_source == "generated"
    assert summary.temporary_password
    assert verify_password(summary.temporary_password, user.password_hash) is True


def test_seed_login_user_updates_existing_membership(monkeypatch, db_session: Session):
    monkeypatch.setenv("WORKSCHEDULEAI_SEED_LOGIN_PASSWORD", "first-password")
    seed_login_user(db_session)
    monkeypatch.setenv("WORKSCHEDULEAI_SEED_LOGIN_PASSWORD", "second-password")
    monkeypatch.setenv("WORKSCHEDULEAI_SEED_LOGIN_ROLE", "scheduler")

    summary = seed_login_user(db_session)

    users = db_session.execute(select(User)).scalars().all()
    membership = db_session.execute(select(Membership)).scalar_one()
    assert len(users) == 1
    assert summary.role == "scheduler"
    assert verify_password("second-password", users[0].password_hash) is True
    assert membership.role == "scheduler"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

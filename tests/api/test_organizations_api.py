from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Organization, Role


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


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_organization_returns_default_roles(client: TestClient):
    response = client.post(
        "/organizations",
        json={"name": "Demo Clinic", "timezone": "Asia/Seoul"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("org_")
    assert payload["name"] == "Demo Clinic"
    assert payload["timezone"] == "Asia/Seoul"
    assert payload["data_version"] == 1
    assert [role["name"] for role in payload["default_roles"]] == ["사수", "부사수"]
    assert all(role["id"].startswith("role_") for role in payload["default_roles"])


def test_create_organization_persists_organization_and_roles(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations",
        json={"name": "Demo Clinic", "timezone": "Asia/Seoul"},
    )

    assert response.status_code == 201
    assert db_session.query(Organization).count() == 1
    assert db_session.query(Role).count() == 2
    assert [role.name for role in db_session.query(Role).order_by(Role.name)] == [
        "부사수",
        "사수",
    ]


def test_auth_required_rejects_public_organization_bootstrap_without_persistence(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")

    response = client.post(
        "/organizations",
        json={"name": "Demo Clinic", "timezone": "Asia/Seoul"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "ORGANIZATION_BOOTSTRAP_LOCKED"
    assert db_session.query(Organization).count() == 0
    assert db_session.query(Role).count() == 0


def test_create_organization_rejects_empty_name(client: TestClient):
    response = client.post(
        "/organizations",
        json={"name": "", "timezone": "Asia/Seoul"},
    )

    assert response.status_code == 422

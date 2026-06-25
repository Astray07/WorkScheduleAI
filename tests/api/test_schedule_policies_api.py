from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Organization


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
        session.add(Organization(id="org_1", name="Demo Clinic", timezone="Asia/Seoul"))
        session.commit()
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


def test_get_policy_creates_default_policy(client: TestClient):
    response = client.get("/organizations/org_1/schedule-policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "기본 정책"
    assert payload["min_rest_hours"] == 11
    assert payload["max_consecutive_shifts"] == 5
    assert payload["max_shifts_per_week"] == 5
    assert payload["default_unfilled_requirement_weight"] == 900
    assert payload["unfilled_policy"] == "soft_penalty"


def test_update_policy_persists_operating_constraints(client: TestClient):
    response = client.put(
        "/organizations/org_1/schedule-policy",
        json={
            "name": "파일럿 정책",
            "min_rest_hours": 10,
            "max_consecutive_shifts": 4,
            "max_shifts_per_week": 5,
            "weekend_shift_limit_per_month": 4,
            "night_shift_limit_per_month": 6,
            "default_unfilled_requirement_weight": 950,
            "weight_workload_imbalance": 120,
            "weight_pair_avoid_violation": 80,
            "unfilled_policy": "soft_penalty",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "파일럿 정책"
    assert payload["min_rest_hours"] == 10
    assert payload["max_consecutive_shifts"] == 4
    assert payload["unfilled_policy"] == "soft_penalty"

    get_response = client.get("/organizations/org_1/schedule-policy")
    assert get_response.json()["name"] == "파일럿 정책"


def test_policy_rejects_hard_unfilled_policy(client: TestClient):
    response = client.put(
        "/organizations/org_1/schedule-policy",
        json={
            "name": "잘못된 정책",
            "min_rest_hours": 11,
            "max_consecutive_shifts": 5,
            "max_shifts_per_week": 5,
            "weekend_shift_limit_per_month": 4,
            "night_shift_limit_per_month": 6,
            "default_unfilled_requirement_weight": 900,
            "weight_workload_imbalance": 100,
            "weight_pair_avoid_violation": 60,
            "unfilled_policy": "hard_constraint",
        },
    )

    assert response.status_code == 422

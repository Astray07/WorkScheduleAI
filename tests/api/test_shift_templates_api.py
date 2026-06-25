from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db import models as db_models
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
        session.add(Organization(id="org_1", name="Demo Clinic", timezone="Asia/Seoul"))
        session.add_all(
            [
                Role(id="role_senior", organization_id="org_1", name="사수"),
                Role(id="role_junior", organization_id="org_1", name="부사수"),
            ]
        )
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


def test_create_shift_type_with_role_requirements(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "crosses_midnight": False,
            "active": True,
            "active_weekdays": [0, 1, 2, 3, 4],
            "requirements": [
                {"role_id": "role_senior", "required_count": 1},
                {"role_id": "role_junior", "required_count": 1},
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("shift_type_")
    assert payload["name"] == "주간 근무"
    assert payload["local_start_time"] == "09:00"
    assert payload["local_end_time"] == "18:00"
    assert payload["active_weekdays"] == [0, 1, 2, 3, 4]
    assert [item["role_name"] for item in payload["requirements"]] == [
        "사수",
        "부사수",
    ]
    shift_type = db_session.query(db_models.ShiftType).one()
    assert shift_type.active_weekdays == "0,1,2,3,4"
    assert db_session.query(db_models.ShiftRequirement).count() == 2


def test_list_shift_types_returns_requirements(client: TestClient):
    create_response = client.post(
        "/organizations/org_1/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "requirements": [
                {"role_id": "role_senior", "required_count": 1},
                {"role_id": "role_junior", "required_count": 1},
            ],
        },
    )
    assert create_response.status_code == 201

    response = client.get("/organizations/org_1/shift-types")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "주간 근무"
    assert payload[0]["active_weekdays"] == [0, 1, 2, 3, 4, 5, 6]
    assert [item["required_count"] for item in payload[0]["requirements"]] == [1, 1]


def test_create_shift_type_rejects_unknown_role(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "requirements": [
                {"role_id": "role_missing", "required_count": 1},
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_ROLE_ID"
    assert db_session.query(db_models.ShiftRequirement).count() == 0


def test_create_shift_type_rejects_duplicate_name(
    client: TestClient,
    db_session: Session,
):
    request = {
        "name": "주간 근무",
        "local_start_time": "09:00",
        "local_end_time": "18:00",
        "timezone": "Asia/Seoul",
        "requirements": [
            {"role_id": "role_senior", "required_count": 1},
        ],
    }

    first_response = client.post("/organizations/org_1/shift-types", json=request)
    second_response = client.post("/organizations/org_1/shift-types", json=request)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["code"] == "SHIFT_TYPE_DUPLICATE"
    assert db_session.query(db_models.ShiftType).count() == 1


def test_create_shift_type_rejects_invalid_active_weekdays(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/shift-types",
        json={
            "name": "잘못된 요일",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "active_weekdays": [0, 7],
            "requirements": [
                {"role_id": "role_senior", "required_count": 1},
            ],
        },
    )

    assert response.status_code == 422
    assert db_session.query(db_models.ShiftType).count() == 0

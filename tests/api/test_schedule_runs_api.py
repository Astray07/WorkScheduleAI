from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    Base,
    Employee,
    EmployeeRole,
    Organization,
    Role,
    ScheduleInputSnapshot,
    ScheduleRun,
)


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
        _seed_p0_organization(session)
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


def test_create_schedule_run_persists_run_and_snapshot(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/schedule-runs",
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "template": "one_shift_per_day",
            "deterministic_mode": True,
            "timeout_seconds": 30,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"].startswith("run_")
    assert payload["organization_id"] == "org_1"
    assert payload["period_start"] == "2026-07-01"
    assert payload["period_end"] == "2026-07-07"
    assert payload["status"] == "succeeded"
    assert payload["solver_status"] == "not_started"
    assert payload["solution_quality"] == "feasible_not_proven_optimal"
    assert payload["current_attempt_no"] == 1
    assert payload["recalculation_count"] == 0
    assert payload["input_snapshot_hash"]
    assert payload["progress"]["phase"] == "completed"
    assert payload["llm_explanation"] == {
        "status": "fallback",
        "text": "서버 템플릿으로 mock 근무표 설명을 생성했습니다.",
        "source": "server_template",
    }
    assert db_session.query(ScheduleRun).count() == 1
    assert db_session.query(ScheduleInputSnapshot).count() == 1


def test_create_schedule_run_is_idempotent_with_same_key(
    client: TestClient,
    db_session: Session,
):
    headers = {"Idempotency-Key": "schedule-run-key-1"}
    first_response = client.post(
        "/organizations/org_1/schedule-runs",
        headers=headers,
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    second_response = client.post(
        "/organizations/org_1/schedule-runs",
        headers=headers,
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["id"] == first_response.json()["id"]
    assert db_session.query(ScheduleRun).count() == 1
    assert db_session.query(ScheduleInputSnapshot).count() == 1


def test_create_schedule_run_rejects_period_longer_than_31_days(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-08-01"},
    )

    assert response.status_code == 422
    assert db_session.query(ScheduleRun).count() == 0


def test_get_schedule_run_returns_persisted_status(client: TestClient):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]

    response = client.get(f"/organizations/org_1/schedule-runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["id"] == run_id
    assert response.json()["status"] == "succeeded"


def test_get_schedule_run_result_returns_one_week_mock_grid(client: TestClient):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]

    response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule_run_id"] == run_id
    assert payload["status"] == "succeeded"
    assert payload["solution_quality"] == "feasible_not_proven_optimal"
    assert payload["current_attempt_no"] == 1
    assert payload["recalculation_count"] == 0
    assert payload["read_only"] is False
    assert payload["publication"] is None
    assert len(payload["slots"]) == 7
    assert len(payload["requirements"]) == 14
    assert len(payload["assignments"]) == 13
    assert payload["issues"] == [
        {
            "id": "issue_mock_unfilled_1",
            "slot_id": "slot_2026_07_01_day",
            "role_id": "role_junior",
            "type": "unfilled_requirement",
            "missing_count": 1,
            "severity": "high",
            "reason_code": "NO_AVAILABLE_CANDIDATE",
            "display_message": "부사수 1명이 미배정입니다.",
            "attempt_no": 1,
            "related_proposal_ids": ["proposal_mock_time_off_1"],
        }
    ]
    assert payload["proposals"][0]["id"] == "proposal_mock_time_off_1"
    assert payload["proposals"][0]["type"] == "approve_time_off_override"
    assert payload["proposals"][0]["status"] == "suggested"
    assert payload["score_summary"]["soft"] == 100
    assert payload["llm_explanation"]["source"] == "server_template"


def _seed_p0_organization(session: Session) -> None:
    session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
    session.add_all(
        [
            Role(id="role_senior", organization_id="org_1", name="사수"),
            Role(id="role_junior", organization_id="org_1", name="부사수"),
        ]
    )
    employees = [
        Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim"),
        Employee(id="emp_2", organization_id="org_1", employee_code="E002", name="Lee"),
        Employee(id="emp_3", organization_id="org_1", employee_code="E003", name="Park"),
        Employee(id="emp_4", organization_id="org_1", employee_code="E004", name="Choi"),
    ]
    session.add_all(employees)
    session.flush()
    employee_roles = []
    for employee in employees:
        employee_roles.append(
            EmployeeRole(
                id=f"employee_role_{employee.id}_senior",
                organization_id="org_1",
                employee_id=employee.id,
                role_id="role_senior",
            )
        )
        employee_roles.append(
            EmployeeRole(
                id=f"employee_role_{employee.id}_junior",
                organization_id="org_1",
                employee_id=employee.id,
                role_id="role_junior",
            )
        )
    session.add_all(employee_roles)
    session.commit()

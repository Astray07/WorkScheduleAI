from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Assignment, Base, Employee, Organization, Role, ScheduleRun, ShiftSlot


def test_compliance_warnings_detect_weekly_hours_over_52(client: TestClient):
    response = client.get("/organizations/org_1/schedule-runs/run_1/compliance-warnings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["legal_disclaimer"]
    assert any(warning["code"] == "WEEKLY_HOURS_OVER_52" for warning in payload["warnings"])
    assert any(warning["publish_blocking"] for warning in payload["warnings"])


def test_compliance_warning_override_records_reason(client: TestClient):
    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/compliance-warning-overrides",
        json={"warning_code": "WEEKLY_HOURS_OVER_52", "reason": "운영자 검토 완료"},
    )

    assert response.status_code == 201
    assert response.json()["warning_code"] == "WEEKLY_HOURS_OVER_52"


def test_compliance_warning_override_rejects_non_current_warning(client: TestClient):
    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/compliance-warning-overrides",
        json={"warning_code": "NOT_PRESENT", "reason": "없는 경고"},
    )

    assert response.status_code == 422


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
        session.add_all(
            [
                Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"),
                Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim"),
                Role(id="role_1", organization_id="org_1", name="사수"),
                ScheduleRun(
                    id="run_1",
                    organization_id="org_1",
                    period_start=date(2026, 7, 1),
                    period_end=date(2026, 7, 7),
                    template="one_shift_per_day",
                    deterministic_mode=True,
                    timeout_seconds=30,
                    status="succeeded",
                    solver_status="cp_sat_optimal",
                    solution_quality="optimal",
                    current_attempt_no=1,
                    recalculation_count=0,
                ),
            ]
        )
        for day in range(6, 13):
            slot_id = f"slot_{day}"
            session.add(
                ShiftSlot(
                    id=slot_id,
                    organization_id="org_1",
                    schedule_run_id="run_1",
                    shift_type_id=None,
                    local_date=date(2026, 7, day),
                    label="장시간 근무",
                    starts_at=f"2026-07-{day:02d}T09:00:00+09:00",
                    ends_at=f"2026-07-{day:02d}T18:00:00+09:00",
                    timezone="Asia/Seoul",
                    status="generated",
                    attempt_no=1,
                )
            )
            session.add(
                Assignment(
                    id=f"assignment_{day}",
                    organization_id="org_1",
                    schedule_run_id="run_1",
                    shift_slot_id=slot_id,
                    role_id="role_1",
                    employee_id="emp_1",
                    employee_name="Kim",
                    source="solver",
                    locked_by_user=False,
                    warning_state="none",
                    warning_message=None,
                    attempt_no=1,
                )
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

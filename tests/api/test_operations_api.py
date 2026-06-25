from collections.abc import Generator
from datetime import date, timedelta
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    Assignment,
    AuditLog,
    Base,
    Employee,
    Organization,
    Role,
    ScheduleRun,
    ShiftSlot,
    utc_now,
)


def test_schedule_run_metrics_reports_status_counts_and_durations(
    client: TestClient,
    db_session: Session,
):
    now = utc_now()
    db_session.add_all(
        [
            _run("run_queued", "queued"),
            _run("run_running", "running", started_at=now - timedelta(seconds=30)),
            _run(
                "run_succeeded",
                "succeeded",
                started_at=now - timedelta(seconds=20),
                finished_at=now,
            ),
            _run(
                "run_failed",
                "failed",
                started_at=now - timedelta(seconds=40),
                finished_at=now - timedelta(seconds=10),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/operations/schedule-runs/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 4
    assert payload["active_runs"] == 2
    assert payload["status_counts"] == {
        "queued": 1,
        "running": 1,
        "succeeded": 1,
        "infeasible": 0,
        "failed": 1,
        "canceled": 0,
    }
    assert payload["completed_average_duration_seconds"] == 25.0


def test_readiness_reports_database_and_redis_status(client: TestClient):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "redis": "not_configured",
    }


def test_organization_audit_logs_returns_recent_entries(
    client: TestClient,
    db_session: Session,
):
    now = utc_now()
    db_session.add_all(
        [
            AuditLog(
                id="audit_old",
                organization_id="org_1",
                actor_user_id=None,
                action="manual_assignment_saved",
                target_type="assignment",
                target_id="assignment_1",
                metadata_json=json.dumps({"schedule_run_id": "run_1"}),
                created_at=now - timedelta(minutes=10),
            ),
            AuditLog(
                id="audit_new",
                organization_id="org_1",
                actor_user_id="user_1",
                action="publication_created",
                target_type="schedule_publication",
                target_id="publication_1",
                metadata_json=json.dumps({"schedule_run_id": "run_1"}),
                created_at=now,
            ),
            AuditLog(
                id="audit_other_org",
                organization_id="org_2",
                actor_user_id=None,
                action="manual_assignment_saved",
                target_type="assignment",
                target_id="assignment_other",
                metadata_json="{}",
                created_at=now + timedelta(minutes=1),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/operations/organizations/org_1/audit-logs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_id"] == "org_1"
    assert [entry["id"] for entry in payload["entries"]] == [
        "audit_new",
        "audit_old",
    ]
    assert payload["entries"][0]["action"] == "publication_created"
    assert payload["entries"][0]["metadata"] == {"schedule_run_id": "run_1"}
    assert payload["entries"][0]["actor_user_id"] == "user_1"


def test_fairness_summary_counts_assignments_for_run(
    client: TestClient,
    db_session: Session,
):
    db_session.add_all(
        [
            Employee(
                id="emp_1",
                organization_id="org_1",
                employee_code="E001",
                name="김민준",
                active=True,
            ),
            Employee(
                id="emp_2",
                organization_id="org_1",
                employee_code="E002",
                name="이서연",
                active=True,
            ),
            Employee(
                id="emp_3",
                organization_id="org_1",
                employee_code="E003",
                name="박지훈",
                active=True,
            ),
            Role(id="role_1", organization_id="org_1", name="사수"),
            _run("run_1", "succeeded"),
            _run("run_other", "succeeded"),
            ShiftSlot(
                id="slot_1",
                organization_id="org_1",
                schedule_run_id="run_1",
                shift_type_id=None,
                local_date=date(2026, 7, 1),
                label="주간 근무",
                starts_at="2026-07-01T09:00:00+09:00",
                ends_at="2026-07-01T18:00:00+09:00",
                timezone="Asia/Seoul",
                status="generated",
                attempt_no=1,
            ),
            ShiftSlot(
                id="slot_2",
                organization_id="org_1",
                schedule_run_id="run_1",
                shift_type_id=None,
                local_date=date(2026, 7, 2),
                label="주간 근무",
                starts_at="2026-07-02T09:00:00+09:00",
                ends_at="2026-07-02T18:00:00+09:00",
                timezone="Asia/Seoul",
                status="generated",
                attempt_no=1,
            ),
            ShiftSlot(
                id="slot_other",
                organization_id="org_1",
                schedule_run_id="run_other",
                shift_type_id=None,
                local_date=date(2026, 7, 3),
                label="주간 근무",
                starts_at="2026-07-03T09:00:00+09:00",
                ends_at="2026-07-03T18:00:00+09:00",
                timezone="Asia/Seoul",
                status="generated",
                attempt_no=1,
            ),
            _assignment("assignment_1", "run_1", "slot_1", "emp_1", "김민준"),
            _assignment("assignment_2", "run_1", "slot_2", "emp_1", "김민준"),
            _assignment("assignment_other", "run_other", "slot_other", "emp_2", "이서연"),
        ]
    )
    db_session.commit()

    response = client.get(
        "/operations/organizations/org_1/fairness/summary",
        params={"schedule_run_id": "run_1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_id"] == "org_1"
    assert payload["schedule_run_id"] == "run_1"
    assert payload["employee_count"] == 3
    assert payload["total_assignments"] == 2
    assert payload["average_assignments"] == pytest.approx(0.667)
    assert payload["min_assignments"] == 0
    assert payload["max_assignments"] == 2
    assert payload["spread"] == 2
    assert [
        (row["employee_code"], row["employee_name"], row["assignment_count"])
        for row in payload["rows"]
    ] == [
        ("E001", "김민준", 2),
        ("E002", "이서연", 0),
        ("E003", "박지훈", 0),
    ]


def _run(
    run_id: str,
    status: str,
    *,
    started_at=None,
    finished_at=None,
) -> ScheduleRun:
    return ScheduleRun(
        id=run_id,
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status=status,
        solver_status=None,
        solution_quality="unknown",
        current_attempt_no=1,
        recalculation_count=0,
        started_at=started_at,
        finished_at=finished_at,
    )


def _assignment(
    assignment_id: str,
    run_id: str,
    slot_id: str,
    employee_id: str,
    employee_name: str,
) -> Assignment:
    return Assignment(
        id=assignment_id,
        organization_id="org_1",
        schedule_run_id=run_id,
        shift_slot_id=slot_id,
        role_id="role_1",
        employee_id=employee_id,
        employee_name=employee_name,
        source="solver",
        locked_by_user=False,
        warning_state="none",
        warning_message=None,
        attempt_no=1,
    )


def _seed(session: Session) -> None:
    session.add_all(
        [
            Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"),
            Organization(id="org_2", name="Clinic B", timezone="Asia/Seoul"),
        ]
    )
    session.commit()


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
        _seed(session)
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

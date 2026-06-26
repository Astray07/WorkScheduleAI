from collections.abc import Generator
from datetime import date
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.compliance import (
    ComplianceAssignment,
    compliance_warning_instance_key,
    evaluate_compliance_warnings,
)
from work_schedule_ai.db.models import (
    Assignment,
    AuditLog,
    Base,
    ComplianceWarningOverride,
    Employee,
    Organization,
    Role,
    ScheduleRun,
    ShiftSlot,
)


def test_compliance_warnings_detect_weekly_hours_over_52(client: TestClient):
    response = client.get("/organizations/org_1/schedule-runs/run_1/compliance-warnings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["legal_disclaimer"]
    assert any(warning["code"] == "WEEKLY_HOURS_OVER_52" for warning in payload["warnings"])
    assert any(warning["publish_blocking"] for warning in payload["warnings"])
    weekly_warning = _weekly_warning(payload["warnings"])
    assert weekly_warning["employee_id"] == "emp_1"
    assert weekly_warning["slot_id"] is None
    assert weekly_warning["week_key"] == "2026-W28"
    assert weekly_warning["snapshot_hash"]
    assert weekly_warning["instance_key"]


def test_compliance_warning_override_records_instance_reason_and_actor(
    client: TestClient,
    db_session: Session,
):
    warning = _current_weekly_warning(client)

    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/compliance-warning-overrides",
        json={
            "warning_code": warning["code"],
            "employee_id": warning["employee_id"],
            "slot_id": warning["slot_id"],
            "week_key": warning["week_key"],
            "snapshot_hash": warning["snapshot_hash"],
            "reason": "운영자 검토 완료",
            "created_by_user_id": "manager_1",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["warning_code"] == "WEEKLY_HOURS_OVER_52"
    assert payload["employee_id"] == "emp_1"
    assert payload["slot_id"] is None
    assert payload["week_key"] == "2026-W28"
    assert payload["snapshot_hash"] == warning["snapshot_hash"]

    override = db_session.query(ComplianceWarningOverride).one()
    assert override.employee_id == "emp_1"
    assert override.slot_id == ""
    assert override.week_key == "2026-W28"
    assert override.snapshot_hash == warning["snapshot_hash"]
    assert override.created_by_user_id == "manager_1"

    audit_log = db_session.query(AuditLog).one()
    assert audit_log.actor_user_id == "manager_1"
    audit_metadata = json.loads(audit_log.metadata_json)
    assert audit_metadata["warning_code"] == "WEEKLY_HOURS_OVER_52"
    assert audit_metadata["employee_id"] == "emp_1"
    assert audit_metadata["week_key"] == "2026-W28"
    assert audit_metadata["snapshot_hash"] == warning["snapshot_hash"]
    assert audit_metadata["reason"] == "운영자 검토 완료"


def test_compliance_warning_override_rejects_non_current_warning(client: TestClient):
    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/compliance-warning-overrides",
        json={"warning_code": "NOT_PRESENT", "reason": "없는 경고"},
    )

    assert response.status_code == 422


def test_compliance_warning_override_rejects_mismatched_instance(client: TestClient):
    warning = _current_weekly_warning(client)

    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/compliance-warning-overrides",
        json={
            "warning_code": warning["code"],
            "employee_id": "emp_missing",
            "slot_id": warning["slot_id"],
            "week_key": warning["week_key"],
            "snapshot_hash": warning["snapshot_hash"],
            "reason": "다른 직원 경고에는 적용되면 안 됩니다.",
        },
    )

    assert response.status_code == 422


def test_compliance_warning_instance_key_uses_structural_identity():
    first_key = compliance_warning_instance_key(
        warning_code="A|B",
        employee_id="C",
        slot_id=None,
        week_key=None,
        snapshot_hash="snapshot",
    )
    second_key = compliance_warning_instance_key(
        warning_code="A",
        employee_id="B|C",
        slot_id=None,
        week_key=None,
        snapshot_hash="snapshot",
    )

    assert first_key != second_key


def test_compliance_rules_flag_consecutive_night_work_as_review_warning():
    warnings = evaluate_compliance_warnings(
        [
            ComplianceAssignment(
                employee_id="emp_1",
                employee_name="Kim",
                slot_id="night_1",
                local_date="2026-07-01",
                label="야간",
                starts_at="2026-07-01T22:00:00+09:00",
                ends_at="2026-07-02T06:00:00+09:00",
            ),
            ComplianceAssignment(
                employee_id="emp_1",
                employee_name="Kim",
                slot_id="night_2",
                local_date="2026-07-02",
                label="야간",
                starts_at="2026-07-02T22:00:00+09:00",
                ends_at="2026-07-03T06:00:00+09:00",
            ),
        ]
    )

    warning = next(
        item for item in warnings if item.code == "CONSECUTIVE_NIGHT_SHIFTS_REVIEW"
    )
    assert warning.severity == "warning"
    assert warning.publish_blocking is False
    assert warning.employee_id == "emp_1"
    assert warning.slot_id == "night_2"
    assert "운영 검토" in warning.message
    assert "위반" not in warning.message


def _current_weekly_warning(client: TestClient) -> dict:
    response = client.get("/organizations/org_1/schedule-runs/run_1/compliance-warnings")
    assert response.status_code == 200
    return _weekly_warning(response.json()["warnings"])


def _weekly_warning(warnings: list[dict]) -> dict:
    return next(
        warning
        for warning in warnings
        if warning["code"] == "WEEKLY_HOURS_OVER_52"
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

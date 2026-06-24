from collections.abc import Generator
from datetime import date
from io import BytesIO
import zipfile

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
    OverrideApproval,
    Role,
    Assignment,
    ScheduleIssue,
    ScheduleRecalculationRequest,
    ScheduleInputSnapshot,
    RelaxationProposal,
    ScheduleRun,
    ShiftSlot,
    ShiftRequirement,
    ShiftType,
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
            "text": "서버 템플릿으로 근무표 설명을 생성했습니다.",
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


def test_create_schedule_run_rejects_same_idempotency_key_with_different_snapshot(
    client: TestClient,
    db_session: Session,
):
    headers = {"Idempotency-Key": "schedule-run-key-2"}
    first_response = client.post(
        "/organizations/org_1/schedule-runs",
        headers=headers,
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    second_response = client.post(
        "/organizations/org_1/schedule-runs",
        headers=headers,
        json={"period_start": "2026-07-08", "period_end": "2026-07-14"},
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["code"] == (
        "SCHEDULE_RUN_IDEMPOTENCY_CONFLICT"
    )
    assert db_session.query(ScheduleRun).count() == 1


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


def test_cancel_queued_schedule_run_marks_canceled(
    client: TestClient,
    db_session: Session,
):
    run = ScheduleRun(
        id="run_cancel_1",
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="queued",
        solver_status=None,
        solution_quality="unknown",
        current_attempt_no=1,
        recalculation_count=0,
    )
    db_session.add(run)
    db_session.commit()

    response = client.post("/organizations/org_1/schedule-runs/run_cancel_1/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert db_session.query(ScheduleRun).filter_by(id="run_cancel_1").one().status == (
        "canceled"
    )


def test_cancel_succeeded_schedule_run_returns_conflict(client: TestClient):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]

    response = client.post(f"/organizations/org_1/schedule-runs/{run_id}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_RUN_NOT_CANCELABLE"


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


def test_approve_relaxation_proposal_records_override_without_recalculation(
    client: TestClient,
    db_session: Session,
):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/relaxation-proposals/proposal_mock_time_off_1/approve",
        json={
            "reason": "관리자 승인",
            "notification_required": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("override_")
    assert payload["schedule_run_id"] == run_id
    assert payload["relaxation_proposal_id"] == "proposal_mock_time_off_1"
    assert payload["type"] == "approve_time_off_override"
    assert payload["notification_required"] is True
    assert db_session.query(OverrideApproval).count() == 1
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    assert run.recalculation_count == 0


def test_approved_relaxation_proposal_is_marked_approved_in_result(
    client: TestClient,
):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]
    client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/relaxation-proposals/proposal_mock_time_off_1/approve",
        json={
            "reason": "관리자 승인",
            "notification_required": True,
        },
    )

    response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")

    assert response.status_code == 200
    assert response.json()["proposals"][0]["status"] == "approved"


def test_approve_relaxation_proposal_rejects_duplicate_approval(
    client: TestClient,
    db_session: Session,
):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]
    url = (
        f"/organizations/org_1/schedule-runs/{run_id}"
        "/relaxation-proposals/proposal_mock_time_off_1/approve"
    )
    first_response = client.post(
        url,
        json={
            "reason": "관리자 승인",
            "notification_required": True,
        },
    )
    second_response = client.post(
        url,
        json={
            "reason": "중복 승인",
            "notification_required": True,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert db_session.query(OverrideApproval).count() == 1


def test_approve_relaxation_proposal_rejects_unknown_proposal(
    client: TestClient,
    db_session: Session,
):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/relaxation-proposals/proposal_missing/approve",
        json={
            "reason": "관리자 승인",
            "notification_required": True,
        },
    )

    assert response.status_code == 404
    assert db_session.query(OverrideApproval).count() == 0


def test_recalculate_with_approved_override_increments_recalculation_count_only(
    client: TestClient,
    db_session: Session,
):
    run_id = _create_run_and_approve_mock_proposal(client)

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 완화안을 반영합니다."},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"] == run_id
    assert payload["recalculation_count"] == 1
    assert payload["current_attempt_no"] == 1
    assert db_session.query(ScheduleRecalculationRequest).count() == 1
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    assert run.recalculation_count == 1
    assert run.current_attempt_no == 1


def test_recalculate_resolves_mock_unfilled_issue_after_approval(client: TestClient):
    run_id = _create_run_and_approve_mock_proposal(client)
    client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 완화안을 반영합니다."},
    )

    response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recalculation_count"] == 1
    assert payload["current_attempt_no"] == 1
    assert payload["issues"] == []
    assert payload["proposals"] == []
    assert len(payload["assignments"]) == 14


def test_recalculate_without_approved_override_returns_conflict(
    client: TestClient,
    db_session: Session,
):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인 없이 재계산합니다."},
    )

    assert response.status_code == 409
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    assert run.recalculation_count == 0
    assert db_session.query(ScheduleRecalculationRequest).count() == 0


def test_recalculate_is_idempotent_with_same_key(
    client: TestClient,
    db_session: Session,
):
    run_id = _create_run_and_approve_mock_proposal(client)
    headers = {"Idempotency-Key": "recalculate-key-1"}

    first_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        headers=headers,
        json={"reason": "승인된 완화안을 반영합니다."},
    )
    second_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        headers=headers,
        json={"reason": "중복 호출입니다."},
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert first_response.json()["recalculation_count"] == 1
    assert second_response.json()["recalculation_count"] == 1
    assert db_session.query(ScheduleRecalculationRequest).count() == 1


def test_recalculate_rejects_fourth_recalculation(
    client: TestClient,
    db_session: Session,
):
    run_id = _create_run_and_approve_mock_proposal(client)
    for round_no in range(1, 4):
        response = client.post(
            f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
            json={"reason": f"재계산 {round_no}"},
        )
        assert response.status_code == 202

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "4회차 재계산"},
    )

    assert response.status_code == 409
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    assert run.recalculation_count == 3
    assert db_session.query(ScheduleRecalculationRequest).count() == 3


def test_schedule_run_result_uses_shift_template_solver_path(
    client: TestClient,
    db_session: Session,
):
    _create_day_shift_type(db_session)
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    run_id = create_response.json()["id"]

    assert create_response.json()["solver_status"].startswith("cp_sat_")
    assert db_session.query(ShiftSlot).count() == 1
    assert db_session.query(Assignment).count() == 2
    assert db_session.query(ScheduleIssue).count() == 0
    assert db_session.query(RelaxationProposal).count() == 0

    response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["slots"]) == 1
    assert payload["slots"][0]["label"] == "주간 근무"
    assert len(payload["requirements"]) == 2
    assert len(payload["assignments"]) == 2
    assert payload["issues"] == []
    assert {
        assignment["role_id"] for assignment in payload["assignments"]
    } == {"role_senior", "role_junior"}


def test_schedule_run_result_maps_solver_unfilled_issue(client: TestClient):
    create_response = client.post(
        "/organizations",
        json={"name": "Unfilled Clinic", "timezone": "Asia/Seoul"},
    )
    organization = create_response.json()
    organization_id = organization["id"]
    senior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "사수"
    )
    junior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "부사수"
    )
    employee_response = client.post(
        f"/organizations/{organization_id}/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": 1,
                    "employee_code": "E001",
                    "name": "Only Senior",
                    "role_names": ["사수"],
                }
            ],
        },
    )
    assert employee_response.status_code == 200
    shift_type_response = client.post(
        f"/organizations/{organization_id}/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "requirements": [
                {"role_id": senior_role_id, "required_count": 1},
                {"role_id": junior_role_id, "required_count": 1},
            ],
        },
    )
    assert shift_type_response.status_code == 201
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    run_id = run_response.json()["id"]

    response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["assignments"]) == 1
    assert payload["issues"][0]["type"] == "unfilled_requirement"
    assert payload["issues"][0]["role_id"] == junior_role_id
    assert payload["issues"][0]["missing_count"] == 1


def test_publish_schedule_run_creates_publication_and_marks_result_read_only(
    client: TestClient,
):
    run_id, result_payload = _create_recalculated_result(client)

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": result_payload[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": result_payload["issue_snapshot_hash"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("publication_")
    assert payload["organization_id"] == "org_1"
    assert payload["schedule_run_id"] == run_id
    assert payload["period_start"] == "2026-07-01"
    assert payload["period_end"] == "2026-07-07"
    assert payload["status"] == "published"
    assert (
        payload["assignment_snapshot_hash"]
        == result_payload["assignment_snapshot_hash"]
    )
    assert payload["issue_snapshot_hash"] == result_payload["issue_snapshot_hash"]

    result_response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")
    assert result_response.status_code == 200
    published_result = result_response.json()
    assert published_result["read_only"] is True
    assert published_result["publication"]["id"] == payload["id"]


def test_publish_schedule_run_rejects_overlapping_active_publication(
    client: TestClient,
):
    first_run_id, first_result = _create_recalculated_result(client)
    first_publish_response = client.post(
        f"/organizations/org_1/schedule-runs/{first_run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": first_result[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": first_result["issue_snapshot_hash"],
        },
    )
    assert first_publish_response.status_code == 201

    second_run_id, second_result = _create_recalculated_result(client)
    response = client.post(
        f"/organizations/org_1/schedule-runs/{second_run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": second_result[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": second_result["issue_snapshot_hash"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PUBLICATION_PERIOD_OVERLAP"


def test_publish_schedule_run_rejects_stale_snapshot_hash(client: TestClient):
    run_id, result_payload = _create_recalculated_result(client)

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": "stale-assignment-hash",
            "expected_issue_snapshot_hash": result_payload["issue_snapshot_hash"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_RESULT_STALE"


def test_download_schedule_publication_excel_returns_workbook(client: TestClient):
    run_id, result_payload = _create_recalculated_result(client)
    publish_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": result_payload[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": result_payload["issue_snapshot_hash"],
        },
    )
    publication_id = publish_response.json()["id"]

    response = client.get(
        f"/organizations/org_1/schedule-publications/{publication_id}/excel"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers["content-disposition"]
    with zipfile.ZipFile(BytesIO(response.content)) as workbook:
        assert "[Content_Types].xml" in workbook.namelist()
        assert "xl/workbook.xml" in workbook.namelist()
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "local_date" in sheet_xml
    assert "role_name" in sheet_xml
    assert "Kim" in sheet_xml


def test_publication_excel_uses_immutable_published_snapshot(
    client: TestClient,
    db_session: Session,
):
    run_id, result_payload = _create_recalculated_result(client)
    publish_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": result_payload[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": result_payload["issue_snapshot_hash"],
        },
    )
    publication_id = publish_response.json()["id"]
    employee = db_session.query(Employee).filter_by(name="Kim").one()
    employee.name = "Changed Name"
    db_session.commit()

    response = client.get(
        f"/organizations/org_1/schedule-publications/{publication_id}/excel"
    )

    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Kim" in sheet_xml
    assert "Changed Name" not in sheet_xml


def _create_recalculated_result(client: TestClient) -> tuple[str, dict]:
    run_id = _create_run_and_approve_mock_proposal(client)
    recalculate_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 완화안을 반영합니다."},
    )
    assert recalculate_response.status_code == 202
    result_response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert "assignment_snapshot_hash" in result_payload
    assert "issue_snapshot_hash" in result_payload
    return run_id, result_payload


def _create_run_and_approve_mock_proposal(client: TestClient) -> str:
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]
    approval_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/relaxation-proposals/proposal_mock_time_off_1/approve",
        json={
            "reason": "관리자 승인",
            "notification_required": True,
        },
    )
    assert approval_response.status_code == 201
    return run_id


def _create_day_shift_type(session: Session) -> None:
    shift_type = ShiftType(
        id="shift_type_day",
        organization_id="org_1",
        name="주간 근무",
        local_start_time="09:00",
        local_end_time="18:00",
        timezone="Asia/Seoul",
        crosses_midnight=False,
        active=True,
    )
    requirements = [
        ShiftRequirement(
            id="shift_requirement_senior",
            organization_id="org_1",
            shift_type_id="shift_type_day",
            role_id="role_senior",
            required_count=1,
        ),
        ShiftRequirement(
            id="shift_requirement_junior",
            organization_id="org_1",
            shift_type_id="shift_type_day",
            role_id="role_junior",
            required_count=1,
        ),
    ]
    session.add(shift_type)
    session.add_all(requirements)
    session.commit()


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

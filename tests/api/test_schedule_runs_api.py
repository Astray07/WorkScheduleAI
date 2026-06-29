from collections.abc import Generator
from contextlib import nullcontext
from datetime import date, datetime, timezone
from io import BytesIO
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.routes import schedule_runs as schedule_runs_module
from work_schedule_ai.api.security import ActorContext
from work_schedule_ai.compliance import (
    ComplianceWarning,
    compliance_warning_instance_key,
)
from work_schedule_ai.db.models import (
    Base,
    ComplianceWarningOverride,
    Employee,
    EmployeeRole,
    Organization,
    OverrideApproval,
    Role,
    Assignment,
    ScheduleIssue,
    DemandDriver,
    ScheduleRecalculationRequest,
    ScheduleInputSnapshot,
    SchedulePublication,
    RelaxationProposal,
    ScheduleRun,
    SolverDiagnosticEvent,
    ShiftSlot,
    ShiftRequirement,
    ShiftType,
)
from work_schedule_ai.worker.queue import (
    InMemoryScheduleRunQueue,
    get_schedule_run_queue,
    set_schedule_run_queue,
)
from work_schedule_ai.worker.schedule_worker import process_next_schedule_run


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(
        engine,
        "connect",
        lambda dbapi_connection, _connection_record: dbapi_connection.execute(
            "PRAGMA foreign_keys=ON"
        ),
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_p0_organization(session)
        yield session


@pytest.fixture
def schedule_queue() -> Generator[InMemoryScheduleRunQueue, None, None]:
    queue = InMemoryScheduleRunQueue()
    set_schedule_run_queue(queue)
    yield queue
    set_schedule_run_queue(None)


@pytest.fixture
def client(
    db_session: Session,
    schedule_queue: InMemoryScheduleRunQueue,
) -> Generator[TestClient, None, None]:
    app = create_app()
    app.state.test_db_session = db_session

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
    assert payload["status"] == "queued"
    assert payload["solver_status"] is None
    assert payload["solution_quality"] == "unknown"
    assert payload["current_attempt_no"] == 1
    assert payload["recalculation_count"] == 0
    assert payload["input_snapshot_hash"]
    assert payload["progress"]["phase"] == "queued"
    assert payload["issues"] == []
    assert payload["proposals"] == []
    assert payload["llm_explanation"] == {
        "status": "fallback",
            "text": "서버 템플릿으로 근무표 설명을 생성했습니다.",
        "source": "server_template",
    }
    assert db_session.query(ScheduleRun).count() == 1
    assert db_session.query(ScheduleInputSnapshot).count() == 1


def test_create_schedule_run_enqueues_without_inline_solver_execution(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    enqueued_jobs: list[tuple[str, str | None]] = []

    def fail_inline_execution(*args, **kwargs):
        raise AssertionError("ScheduleRun must not execute in the API process")

    def record_enqueue(
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        enqueued_jobs.append((schedule_run_id, organization_id))

    monkeypatch.setattr(
        schedule_runs_module,
        "execute_schedule_run",
        fail_inline_execution,
        raising=False,
    )
    monkeypatch.setattr(
        schedule_runs_module,
        "enqueue_schedule_run",
        record_enqueue,
        raising=False,
    )

    response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert enqueued_jobs == [(payload["id"], "org_1")]


def test_schedule_run_solver_request_includes_demand_staffing_targets(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    _create_day_shift_type(db_session)
    db_session.add(
        DemandDriver(
            id="demand_1",
            organization_id="org_1",
            local_date=date(2026, 7, 1),
            segment="shift_type_day",
            demand_count=100,
            required_staff_count=1,
            source="test",
        )
    )
    db_session.commit()
    captured_requests = []
    original_solve_schedule = schedule_runs_module.solve_schedule

    def record_solver_request(request):
        captured_requests.append(request)
        return original_solve_schedule(request)

    monkeypatch.setattr(schedule_runs_module, "solve_schedule", record_solver_request)

    response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    assert response.status_code == 202
    _process_next_schedule_run(client)

    assert len(captured_requests) == 1
    assert [
        (target.slot_id, target.target_staff_count)
        for target in captured_requests[0].staffing_targets
    ] == [("slot_2026_07_01_shift_type_day", 1)]


def test_create_schedule_run_is_idempotent_with_same_key(
    client: TestClient,
    db_session: Session,
    schedule_queue: InMemoryScheduleRunQueue,
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
    job = schedule_queue.dequeue(timeout_seconds=0)
    assert job is not None
    assert job.schedule_run_id == first_response.json()["id"]
    assert job.organization_id == "org_1"
    replay_job = schedule_queue.dequeue(timeout_seconds=0)
    assert replay_job is not None
    assert replay_job.schedule_run_id == first_response.json()["id"]
    assert replay_job.organization_id == "org_1"
    assert schedule_queue.dequeue(timeout_seconds=0) is None


def test_create_schedule_run_reenqueues_after_idempotent_enqueue_failure(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def flaky_enqueue(
        schedule_run_id: str,
        *,
        organization_id: str | None = None,
    ) -> None:
        del organization_id
        calls.append(schedule_run_id)
        if len(calls) == 1:
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr(schedule_runs_module, "enqueue_schedule_run", flaky_enqueue)
    headers = {"Idempotency-Key": "schedule-run-key-redis-retry"}

    with pytest.raises(RuntimeError, match="redis unavailable"):
        client.post(
            "/organizations/org_1/schedule-runs",
            headers=headers,
            json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
        )

    second_response = client.post(
        "/organizations/org_1/schedule-runs",
        headers=headers,
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )

    assert second_response.status_code == 202
    assert calls == [second_response.json()["id"], second_response.json()["id"]]
    assert db_session.query(ScheduleRun).count() == 1


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
    assert response.json()["status"] == "queued"


def test_list_schedule_runs_returns_history_counts(
    client: TestClient,
    db_session: Session,
):
    _seed_run_history_comparison(db_session)

    response = client.get("/organizations/org_1/schedule-runs")

    assert response.status_code == 200
    payload = response.json()
    assert [run["id"] for run in payload["runs"][:2]] == [
        "run_history_candidate",
        "run_history_base",
    ]
    candidate = payload["runs"][0]
    assert candidate["assignment_count"] == 3
    assert candidate["issue_count"] == 1
    assert candidate["manual_locked_count"] == 1
    assert candidate["recalculation_count"] == 1


def test_compare_schedule_runs_returns_assignment_issue_fairness_and_lock_changes(
    client: TestClient,
    db_session: Session,
):
    _seed_run_history_comparison(db_session)

    response = client.get(
        "/organizations/org_1/schedule-runs/compare",
        params={
            "base_run_id": "run_history_base",
            "candidate_run_id": "run_history_candidate",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["base_run_id"] == "run_history_base"
    assert payload["candidate_run_id"] == "run_history_candidate"
    assert payload["summary"] == {
        "assignment_added_count": 2,
        "assignment_removed_count": 2,
        "assignment_unchanged_count": 1,
        "manual_lock_maintained_count": 1,
        "issue_added_count": 1,
        "issue_resolved_count": 1,
        "fairness_changed_employee_count": 2,
    }

    removed = next(
        row
        for row in payload["assignment_changes"]
        if row["change_type"] == "removed" and row["employee_id"] == "emp_1"
    )
    assert removed["slot_id"] == "slot_day_1"
    assert removed["role_name"] == "사수"
    assert removed["before_locked_by_user"] is False
    assert removed["after_locked_by_user"] is None

    maintained = next(
        row
        for row in payload["assignment_changes"]
        if row["change_type"] == "unchanged" and row["employee_id"] == "emp_2"
    )
    assert maintained["manual_lock_maintained"] is True
    assert maintained["before_source"] == "manual"
    assert maintained["after_source"] == "manual"

    issue_changes = {
        (row["change_type"], row["slot_id"], row["role_name"]): row
        for row in payload["issue_changes"]
    }
    assert issue_changes[("resolved", "slot_day_1", "사수")]["missing_delta"] == -1
    assert issue_changes[("added", "slot_day_2", "사수")]["missing_delta"] == 2

    fairness = {row["employee_id"]: row for row in payload["fairness_changes"]}
    assert fairness["emp_1"]["assignment_delta"] == -1
    assert fairness["emp_4"]["assignment_delta"] == 1


def test_compare_schedule_runs_rejects_run_from_another_organization(
    client: TestClient,
    db_session: Session,
):
    _seed_run_history_comparison(db_session)
    db_session.add(Organization(id="org_other", name="Other", timezone="Asia/Seoul"))
    db_session.add(
        ScheduleRun(
            id="run_other",
            organization_id="org_other",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 1),
            template="one_shift_per_day",
            deterministic_mode=True,
            timeout_seconds=30,
            status="succeeded",
            solver_status="cp_sat_optimal",
            solution_quality="optimal",
            current_attempt_no=1,
            recalculation_count=0,
        )
    )
    db_session.commit()

    response = client.get(
        "/organizations/org_1/schedule-runs/compare",
        params={
            "base_run_id": "run_history_base",
            "candidate_run_id": "run_other",
        },
    )

    assert response.status_code == 404


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
    _process_next_schedule_run(client)

    response = client.post(f"/organizations/org_1/schedule-runs/{run_id}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_RUN_NOT_CANCELABLE"


def test_get_schedule_run_result_returns_one_week_mock_grid(client: TestClient):
    create_response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-07"},
    )
    run_id = create_response.json()["id"]
    _process_next_schedule_run(client)

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
    _process_next_schedule_run(client)

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
    _process_next_schedule_run(client)
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
    _process_next_schedule_run(client)
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
    assert payload["status"] == "queued"
    assert payload["progress"]["phase"] == "queued"
    assert payload["recalculation_count"] == 1
    assert payload["current_attempt_no"] == 1
    assert db_session.query(ScheduleRecalculationRequest).count() == 1
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    assert run.recalculation_count == 1
    assert run.current_attempt_no == 1


def test_recalculate_enqueues_without_inline_solver_execution(
    client: TestClient,
    schedule_queue: InMemoryScheduleRunQueue,
    monkeypatch: pytest.MonkeyPatch,
):
    run_id = _create_run_and_approve_mock_proposal(client)

    def reject_inline_execution(db_session: Session, schedule_run: ScheduleRun) -> None:
        raise AssertionError("recalculation must be processed by the worker")

    monkeypatch.setattr(
        schedule_runs_module,
        "_execute_schedule_run_artifacts",
        reject_inline_execution,
    )

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 완화안을 큐에서 반영합니다."},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["progress"]["phase"] == "queued"
    assert payload["recalculation_count"] == 1
    job = schedule_queue.dequeue(timeout_seconds=0)
    assert job is not None
    assert job.schedule_run_id == run_id
    assert job.organization_id == "org_1"
    assert schedule_queue.dequeue(timeout_seconds=0) is None


def test_recalculating_result_hides_previous_persisted_artifacts(client: TestClient):
    run_id = _create_run_and_approve_mock_proposal(client)
    initial_response = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result")
    assert initial_response.status_code == 200
    assert initial_response.json()["issues"] != []

    recalculate_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 완화안을 큐에서 반영합니다."},
    )

    assert recalculate_response.status_code == 202
    queued_result_response = client.get(
        f"/organizations/org_1/schedule-runs/{run_id}/result"
    )
    assert queued_result_response.status_code == 200
    queued_result = queued_result_response.json()
    assert queued_result["status"] == "queued"
    assert queued_result["assignments"] == []
    assert queued_result["issues"] == []
    assert queued_result["proposals"] == []


def test_recalculate_resolves_mock_unfilled_issue_after_approval(client: TestClient):
    run_id = _create_run_and_approve_mock_proposal(client)
    client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 완화안을 반영합니다."},
    )
    _process_next_schedule_run(client)

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


def test_recalculate_reenqueues_idempotent_queued_run(
    client: TestClient,
    schedule_queue: InMemoryScheduleRunQueue,
):
    run_id = _create_run_and_approve_mock_proposal(client)
    headers = {"Idempotency-Key": "recalculate-key-requeue"}

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
    first_job = schedule_queue.dequeue(timeout_seconds=0)
    replay_job = schedule_queue.dequeue(timeout_seconds=0)
    assert first_job is not None
    assert replay_job is not None
    assert first_job.schedule_run_id == run_id
    assert replay_job.schedule_run_id == run_id


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
        _process_next_schedule_run(client)

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "4회차 재계산"},
    )

    assert response.status_code == 409
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    assert run.recalculation_count == 3
    assert db_session.query(ScheduleRecalculationRequest).count() == 3


def test_recalculate_rejects_published_schedule_run(
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
    assert publish_response.status_code == 201
    run = db_session.query(ScheduleRun).filter_by(id=run_id).one()
    previous_recalculation_count = run.recalculation_count
    previous_assignment_count = db_session.query(Assignment).filter_by(
        schedule_run_id=run_id
    ).count()

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/recalculate",
        json={"reason": "발행 후 재계산을 시도합니다."},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_RUN_ALREADY_PUBLISHED"
    db_session.refresh(run)
    assert run.recalculation_count == previous_recalculation_count
    assert db_session.query(Assignment).filter_by(
        schedule_run_id=run_id
    ).count() == previous_assignment_count


def test_time_off_override_applies_only_to_approved_employee_slot(
    client: TestClient,
):
    organization = _create_role_scoped_organization(client, name="Scoped Clinic")
    organization_id = organization["organization_id"]
    employees_by_code = organization["employees_by_code"]
    junior_role_id = organization["junior_role_id"]
    client.post(
        f"/organizations/{organization_id}/unavailabilities",
        json={
            "employee_id": employees_by_code["E002"]["id"],
            "type": "vacation",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-03T00:00:00+09:00",
            "override_allowed": True,
        },
    )
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-02"},
    )
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)
    initial_result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    assert [issue["role_id"] for issue in initial_result["issues"]] == [
        junior_role_id,
        junior_role_id,
    ]
    first_proposal = initial_result["proposals"][0]

    approval_response = client.post(
        (
            f"/organizations/{organization_id}/schedule-runs/{run_id}"
            f"/relaxation-proposals/{first_proposal['id']}/approve"
        ),
        json={"reason": "첫날 휴가 예외만 승인", "notification_required": True},
    )
    assert approval_response.status_code == 201
    recalculate_response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/recalculate",
        json={"reason": "승인된 단일 slot 예외 반영"},
    )
    assert recalculate_response.status_code == 202
    _process_next_schedule_run(client)

    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()

    assert len(result["issues"]) == 1
    assert result["issues"][0]["slot_id"].startswith("slot_2026_07_02")
    assert result["issues"][0]["role_id"] == junior_role_id
    assert all(
        assignment["employee_id"] != employees_by_code["E002"]["id"]
        or assignment["slot_id"].startswith("slot_2026_07_01")
        for assignment in result["assignments"]
    )


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
    _process_next_schedule_run(client)

    run = db_session.get(ScheduleRun, run_id)
    assert run.solver_status.startswith("cp_sat_")
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


def test_schedule_run_worker_path_distributes_larger_mixed_role_case(client: TestClient):
    create_response = client.post(
        "/organizations",
        json={"name": "Fairness Clinic", "timezone": "Asia/Seoul"},
    )
    assert create_response.status_code == 201
    organization = create_response.json()
    organization_id = organization["id"]
    senior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "사수"
    )
    junior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "부사수"
    )
    names = [
        "Kim",
        "Lee",
        "Park",
        "Choi",
        "Jung",
        "Kang",
        "Cho",
        "Yoon",
        "Jang",
        "Lim",
        "Han",
        "Oh",
    ]
    employee_response = client.post(
        f"/organizations/{organization_id}/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": index,
                    "employee_code": f"E{index:03d}",
                    "name": names[index - 1],
                    "role_names": (
                        ["사수"]
                        if index % 4 == 1
                        else ["부사수"]
                        if index % 4 == 2
                        else ["사수", "부사수"]
                    ),
                    "max_shifts_per_week": 5,
                }
                for index in range(1, 13)
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
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-14",
            "template": "one_shift_per_day",
            "deterministic_mode": True,
            "timeout_seconds": 30,
        },
    )
    assert run_response.status_code == 202
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)

    result_response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )
    assert result_response.status_code == 200
    payload = result_response.json()
    assignment_counts: dict[str, int] = {}
    for assignment in payload["assignments"]:
        assignment_counts[assignment["employee_id"]] = (
            assignment_counts.get(assignment["employee_id"], 0) + 1
        )

    assert payload["issues"] == []
    assert len(payload["assignments"]) == 28
    assert max(assignment_counts.values()) <= 3
    assert sum(count > 0 for count in assignment_counts.values()) >= 10


def test_schedule_run_worker_path_distributes_default_demo_with_vacation_and_pair(
    client: TestClient,
):
    create_response = client.post(
        "/organizations",
        json={"name": "Default Demo Fairness Clinic", "timezone": "Asia/Seoul"},
    )
    assert create_response.status_code == 201
    organization = create_response.json()
    organization_id = organization["id"]
    senior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "사수"
    )
    junior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "부사수"
    )
    names = [
        "Kim",
        "Lee",
        "Park",
        "Choi",
        "Jung",
        "Kang",
        "Cho",
        "Yoon",
        "Jang",
        "Lim",
        "Han",
        "Oh",
    ]
    employee_response = client.post(
        f"/organizations/{organization_id}/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                {
                    "row_no": index,
                    "employee_code": f"E{index:03d}",
                    "name": names[index - 1],
                    "role_names": (
                        ["사수"]
                        if index % 4 == 1
                        else ["부사수"]
                        if index % 4 == 2
                        else ["사수", "부사수"]
                    ),
                    "max_shifts_per_week": 5,
                }
                for index in range(1, 13)
            ],
        },
    )
    assert employee_response.status_code == 200
    employees_by_code = {
        employee["employee_code"]: employee
        for employee in employee_response.json()["employees"]
    }
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
    unavailability_response = client.post(
        f"/organizations/{organization_id}/unavailabilities",
        json={
            "employee_id": employees_by_code["E002"]["id"],
            "type": "vacation",
            "starts_at": "2026-07-02T00:00:00+09:00",
            "ends_at": "2026-07-03T00:00:00+09:00",
            "override_allowed": True,
            "note": "Default demo vacation",
        },
    )
    assert unavailability_response.status_code == 201
    pair_response = client.post(
        f"/organizations/{organization_id}/pair-constraints",
        json={
            "employee_a_id": employees_by_code["E001"]["id"],
            "employee_b_id": employees_by_code["E002"]["id"],
            "type": "blocked",
            "severity": "high",
            "override_allowed": True,
            "active": True,
        },
    )
    assert pair_response.status_code == 201
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-14",
            "template": "one_shift_per_day",
            "deterministic_mode": True,
            "timeout_seconds": 30,
        },
    )
    assert run_response.status_code == 202
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)

    result_response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )
    assert result_response.status_code == 200
    payload = result_response.json()
    assignment_counts: dict[str, int] = {}
    for assignment in payload["assignments"]:
        assignment_counts[assignment["employee_name"]] = (
            assignment_counts.get(assignment["employee_name"], 0) + 1
        )

    assert payload["issues"] == []
    assert len(payload["assignments"]) == 28
    assert max(assignment_counts.values()) <= 3
    assert sum(count > 0 for count in assignment_counts.values()) >= 10


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
    _process_next_schedule_run(client)

    response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["assignments"]) == 1
    assert payload["issues"][0]["type"] == "unfilled_requirement"
    assert payload["issues"][0]["role_id"] == junior_role_id
    assert payload["issues"][0]["missing_count"] == 1
    assert payload["proposals"][0]["type"] == "mark_manual_review"
    assert payload["proposals"][0]["impact_preview"]["unavailable_reasons"] == [
        "NO_TIME_OFF_OVERRIDE_CANDIDATE"
    ]
    assert "휴가" not in payload["proposals"][0]["display_summary"]


def test_solver_proposes_multiple_time_off_override_candidates(client: TestClient):
    create_response = client.post(
        "/organizations",
        json={"name": "Multi Candidate Clinic", "timezone": "Asia/Seoul"},
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
                _employee_row(1, "E001", "Senior", ["사수"]),
                _employee_row(2, "E002", "Junior A", ["부사수"]),
                _employee_row(3, "E003", "Junior B", ["부사수"]),
            ],
        },
    )
    employees_by_code = {
        employee["employee_code"]: employee
        for employee in employee_response.json()["employees"]
    }
    for employee_code in ("E002", "E003"):
        response = client.post(
            f"/organizations/{organization_id}/unavailabilities",
            json={
                "employee_id": employees_by_code[employee_code]["id"],
                "type": "vacation",
                "starts_at": "2026-07-01T00:00:00+09:00",
                "ends_at": "2026-07-02T00:00:00+09:00",
                "override_allowed": True,
            },
        )
        assert response.status_code == 201
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
    _process_next_schedule_run(client)

    payload = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()

    assert [proposal["type"] for proposal in payload["proposals"]] == [
        "approve_time_off_override",
        "approve_time_off_override",
    ]
    assert {
        proposal["impact_preview"]["resolved_issue_ids"][0]
        for proposal in payload["proposals"]
    } == {payload["issues"][0]["id"]}
    assert {proposal["group_id"] for proposal in payload["proposals"]} == {
        f"group_{payload['issues'][0]['id']}"
    }
    assert all(proposal["requires_proposal_ids"] == [] for proposal in payload["proposals"])
    assert all(
        proposal["impact_preview"]["unavailable_reasons"] == []
        for proposal in payload["proposals"]
    )


def test_solver_unfilled_issue_persists_diagnostic_events(
    client: TestClient,
    db_session: Session,
):
    create_response = client.post(
        "/organizations",
        json={"name": "Diagnostic Clinic", "timezone": "Asia/Seoul"},
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
    _process_next_schedule_run(client)

    events = (
        db_session.query(SolverDiagnosticEvent)
        .filter_by(schedule_run_id=run_id)
        .order_by(SolverDiagnosticEvent.event_type)
        .all()
    )

    assert [event.event_type for event in events] == [
        "infeasibility_core",
        "manual_review",
    ]
    assert events[0].role_id == junior_role_id
    assert events[0].constraint_type == "unfilled_requirement"
    assert json.loads(events[0].metadata_json)["missing_count"] == 1
    assert events[1].constraint_type == "no_relaxation_candidate"
    assert json.loads(events[1].metadata_json)["unavailable_reasons"] == [
        "NO_TIME_OFF_OVERRIDE_CANDIDATE"
    ]


def test_manual_edit_validation_rejects_ineligible_employee(client: TestClient):
    create_response = client.post(
        "/organizations",
        json={"name": "Manual Edit Clinic", "timezone": "Asia/Seoul"},
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
    employee_id = employee_response.json()["employees"][0]["id"]
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
    _process_next_schedule_run(client)
    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()

    response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/manual-edits/validate",
        json={
            "slot_id": result["slots"][0]["id"],
            "role_id": junior_role_id,
            "employee_id": employee_id,
            "locked_by_user": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["blocking_errors"] == [
        {
            "field": "employee_id",
            "code": "EMPLOYEE_ROLE_MISMATCH",
            "message": "Employee is not eligible for the requested role.",
        }
    ]
    assert payload["warnings"] == []


def test_save_manual_edit_persists_assignment_and_audit_log(
    client: TestClient,
    db_session: Session,
):
    organization = _create_role_scoped_organization(client, name="Manual Save Clinic")
    organization_id = organization["organization_id"]
    employees_by_code = organization["employees_by_code"]
    junior_role_id = organization["junior_role_id"]
    response = client.post(
        f"/organizations/{organization_id}/unavailabilities",
        json={
            "employee_id": employees_by_code["E002"]["id"],
            "type": "vacation",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "override_allowed": True,
        },
    )
    assert response.status_code == 201
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)
    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    issue = result["issues"][0]

    response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/manual-edits",
        json={
            "slot_id": issue["slot_id"],
            "role_id": junior_role_id,
            "employee_id": employees_by_code["E002"]["id"],
            "locked_by_user": True,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slot_id"] == issue["slot_id"]
    assert payload["role_id"] == junior_role_id
    assert payload["employee_id"] == employees_by_code["E002"]["id"]
    assert payload["source"] == "manual"
    assert payload["locked_by_user"] is True
    assert payload["warning_state"] == "manual_warning"
    refreshed = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    assert refreshed["issues"] == []
    assert any(
        assignment["id"] == payload["id"]
        and assignment["source"] == "manual"
        and assignment["locked_by_user"] is True
        for assignment in refreshed["assignments"]
    )

    audit_rows = (
        db_session.execute(
            text(
                "select action, target_type, target_id, metadata_json "
                "from audit_logs"
            )
        )
        .mappings()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0]["action"] == "manual_assignment_saved"
    assert audit_rows[0]["target_type"] == "assignment"
    assert audit_rows[0]["target_id"] == payload["id"]
    audit_metadata = json.loads(audit_rows[0]["metadata_json"])
    assert audit_metadata["schedule_run_id"] == run_id
    assert audit_metadata["slot_id"] == issue["slot_id"]
    assert audit_metadata["warning_codes"] == ["UNAVAILABILITY_CONFLICT"]


def test_save_manual_edit_rechecks_employee_tenant_scope_at_write_site(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    organization = _create_role_scoped_organization(client, name="Manual Tenant Guard Clinic")
    organization_id = organization["organization_id"]
    junior_role_id = organization["junior_role_id"]
    db_session.add(Organization(id="org_other", name="Other Clinic", timezone="Asia/Seoul"))
    db_session.flush()
    db_session.add(
        Employee(
            id="emp_other",
            organization_id="org_other",
            employee_code="X001",
            name="Cross Tenant Employee",
        )
    )
    db_session.commit()
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)
    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    slot_id = result["slots"][0]["id"]

    def validation_bypass(**_kwargs):
        return schedule_runs_module.ManualEditValidationResponse(
            valid=True,
            blocking_errors=[],
            warnings=[],
        )

    monkeypatch.setattr(
        schedule_runs_module,
        "_validate_manual_edit_request",
        validation_bypass,
    )
    before_count = db_session.query(Assignment).filter_by(
        organization_id=organization_id,
        employee_id="emp_other",
    ).count()

    response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/manual-edits",
        json={
            "slot_id": slot_id,
            "role_id": junior_role_id,
            "employee_id": "emp_other",
            "locked_by_user": True,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "EMPLOYEE_NOT_FOUND"
    assert db_session.query(Assignment).filter_by(
        organization_id=organization_id,
        employee_id="emp_other",
    ).count() == before_count


def test_save_manual_edit_preserves_other_assignments_for_multi_count_requirement(
    client: TestClient,
):
    create_response = client.post(
        "/organizations",
        json={"name": "Multi Count Manual Clinic", "timezone": "Asia/Seoul"},
    )
    organization = create_response.json()
    organization_id = organization["id"]
    senior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "사수"
    )
    employee_response = client.post(
        f"/organizations/{organization_id}/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                _employee_row(1, "E001", "Kim", ["사수"]),
                _employee_row(2, "E002", "Lee", ["사수"]),
                _employee_row(3, "E003", "Park", ["사수"]),
            ],
        },
    )
    employees_by_code = {
        employee["employee_code"]: employee
        for employee in employee_response.json()["employees"]
    }
    shift_type_response = client.post(
        f"/organizations/{organization_id}/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "requirements": [
                {"role_id": senior_role_id, "required_count": 2},
            ],
        },
    )
    assert shift_type_response.status_code == 201
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)
    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    slot_id = result["slots"][0]["id"]
    before_assignments = [
        assignment
        for assignment in result["assignments"]
        if assignment["slot_id"] == slot_id and assignment["role_id"] == senior_role_id
    ]
    assert len(before_assignments) == 2
    unassigned_employee_id = next(
        employee["id"]
        for employee in employees_by_code.values()
        if employee["id"] not in {assignment["employee_id"] for assignment in before_assignments}
    )

    response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/manual-edits",
        json={
            "slot_id": slot_id,
            "role_id": senior_role_id,
            "employee_id": unassigned_employee_id,
            "locked_by_user": True,
        },
    )

    assert response.status_code == 201
    refreshed = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    after_assignments = [
        assignment
        for assignment in refreshed["assignments"]
        if assignment["slot_id"] == slot_id and assignment["role_id"] == senior_role_id
    ]
    assert len(after_assignments) == 2
    assert response.json()["employee_id"] in {
        assignment["employee_id"] for assignment in after_assignments
    }


def test_schedule_policy_weekly_cap_is_used_by_solver_path(client: TestClient):
    create_response = client.post(
        "/organizations",
        json={"name": "Policy Solver Clinic", "timezone": "Asia/Seoul"},
    )
    organization = create_response.json()
    organization_id = organization["id"]
    senior_role_id = next(
        role["id"] for role in organization["default_roles"] if role["name"] == "사수"
    )
    employee_response = client.post(
        f"/organizations/{organization_id}/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                _employee_row(1, "E001", "Kim", ["사수"]),
                _employee_row(2, "E002", "Lee", ["사수"]),
            ],
        },
    )
    assert employee_response.status_code == 200
    policy_response = client.put(
        f"/organizations/{organization_id}/schedule-policy",
        json={
            "name": "엄격한 주간 제한",
            "min_rest_hours": 0,
            "max_consecutive_shifts": 5,
            "max_shifts_per_week": 1,
            "weekend_shift_limit_per_month": 31,
            "night_shift_limit_per_month": 31,
            "default_unfilled_requirement_weight": 900,
            "weight_workload_imbalance": 100,
            "weight_pair_avoid_violation": 60,
            "unfilled_policy": "soft_penalty",
        },
    )
    assert policy_response.status_code == 200
    shift_type_response = client.post(
        f"/organizations/{organization_id}/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "requirements": [
                {"role_id": senior_role_id, "required_count": 1},
            ],
        },
    )
    assert shift_type_response.status_code == 201
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-03"},
    )
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)

    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()

    assert len(result["assignments"]) == 2
    assert len(result["issues"]) == 1
    issue = result["issues"][0]
    assert issue["role_id"] == senior_role_id
    assert issue["type"] == "unfilled_requirement"
    assert issue["missing_count"] == 1
    assert issue["display_message"] == "사수 1명이 미배정입니다."


def test_recalculate_preserves_manual_locked_assignment(client: TestClient):
    organization = _create_role_scoped_organization(client, name="Manual Lock Clinic")
    organization_id = organization["organization_id"]
    employees_by_code = organization["employees_by_code"]
    junior_role_id = organization["junior_role_id"]
    response = client.post(
        f"/organizations/{organization_id}/unavailabilities",
        json={
            "employee_id": employees_by_code["E002"]["id"],
            "type": "vacation",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "override_allowed": True,
        },
    )
    assert response.status_code == 201
    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-01"},
    )
    run_id = run_response.json()["id"]
    _process_next_schedule_run(client)
    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    issue = result["issues"][0]
    proposal_id = result["proposals"][0]["id"]
    approval_response = client.post(
        (
            f"/organizations/{organization_id}/schedule-runs/{run_id}"
            f"/relaxation-proposals/{proposal_id}/approve"
        ),
        json={"reason": "manual lock regression setup", "notification_required": True},
    )
    assert approval_response.status_code == 201
    manual_response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/manual-edits",
        json={
            "slot_id": issue["slot_id"],
            "role_id": junior_role_id,
            "employee_id": employees_by_code["E002"]["id"],
            "locked_by_user": True,
        },
    )
    assert manual_response.status_code == 201

    recalculate_response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/recalculate",
        json={"reason": "preserve manual lock"},
    )

    assert recalculate_response.status_code == 202
    _process_next_schedule_run(client)
    result = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    ).json()
    matching_assignments = [
        assignment
        for assignment in result["assignments"]
        if assignment["slot_id"] == issue["slot_id"]
        and assignment["role_id"] == junior_role_id
    ]
    assert matching_assignments == [
        {
            **manual_response.json(),
            "attempt_no": 1,
        }
    ]


def test_manual_edit_validation_rejects_published_schedule_run(client: TestClient):
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
    assert publish_response.status_code == 201
    result = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result").json()

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/manual-edits/validate",
        json={
            "slot_id": result["slots"][0]["id"],
            "role_id": "role_senior",
            "employee_id": "emp_1",
            "locked_by_user": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_RUN_ALREADY_PUBLISHED"


def test_save_manual_edit_rejects_published_schedule_run(client: TestClient):
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
    assert publish_response.status_code == 201
    result = client.get(f"/organizations/org_1/schedule-runs/{run_id}/result").json()

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/manual-edits",
        json={
            "slot_id": result["slots"][0]["id"],
            "role_id": "role_senior",
            "employee_id": "emp_1",
            "locked_by_user": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_RUN_ALREADY_PUBLISHED"


def test_schedule_input_snapshot_includes_generated_slots_and_requirements(
    client: TestClient,
    db_session: Session,
):
    _create_day_shift_type(db_session)

    response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-01", "period_end": "2026-07-02"},
    )

    assert response.status_code == 202
    snapshot = db_session.query(ScheduleInputSnapshot).one()
    payload = json.loads(snapshot.payload_json)
    assert [slot["id"] for slot in payload["generated_shift_slots"]] == [
        "slot_2026_07_01_shift_type_day",
        "slot_2026_07_02_shift_type_day",
    ]
    assert len(payload["generated_schedule_requirements"]) == 4
    assert {
        requirement["slot_id"]
        for requirement in payload["generated_schedule_requirements"]
    } == {
        "slot_2026_07_01_shift_type_day",
        "slot_2026_07_02_shift_type_day",
    }


def test_schedule_input_snapshot_respects_shift_type_weekdays_and_cross_midnight(
    client: TestClient,
    db_session: Session,
):
    weekday_response = client.post(
        "/organizations/org_1/shift-types",
        json={
            "name": "평일 오전",
            "local_start_time": "06:00",
            "local_end_time": "14:00",
            "timezone": "Asia/Seoul",
            "active_weekdays": [0, 1, 2, 3, 4],
            "requirements": [
                {"role_id": "role_senior", "required_count": 1},
                {"role_id": "role_junior", "required_count": 1},
            ],
        },
    )
    weekend_response = client.post(
        "/organizations/org_1/shift-types",
        json={
            "name": "주말 야간",
            "local_start_time": "22:00",
            "local_end_time": "06:00",
            "timezone": "Asia/Seoul",
            "crosses_midnight": True,
            "active_weekdays": [5, 6],
            "requirements": [
                {"role_id": "role_senior", "required_count": 1},
                {"role_id": "role_junior", "required_count": 1},
            ],
        },
    )
    assert weekday_response.status_code == 201
    assert weekend_response.status_code == 201

    response = client.post(
        "/organizations/org_1/schedule-runs",
        json={"period_start": "2026-07-03", "period_end": "2026-07-06"},
    )

    assert response.status_code == 202
    snapshot = db_session.query(ScheduleInputSnapshot).one()
    payload = json.loads(snapshot.payload_json)
    slot_pairs = [
        (slot["local_date"], slot["label"], slot["starts_at"], slot["ends_at"])
        for slot in payload["generated_shift_slots"]
    ]
    assert slot_pairs == [
        ("2026-07-03", "평일 오전", "2026-07-03T06:00:00+09:00", "2026-07-03T14:00:00+09:00"),
        ("2026-07-04", "주말 야간", "2026-07-04T22:00:00+09:00", "2026-07-05T06:00:00+09:00"),
        ("2026-07-05", "주말 야간", "2026-07-05T22:00:00+09:00", "2026-07-06T06:00:00+09:00"),
        ("2026-07-06", "평일 오전", "2026-07-06T06:00:00+09:00", "2026-07-06T14:00:00+09:00"),
    ]
    assert len(payload["generated_schedule_requirements"]) == 8


def test_publish_schedule_run_creates_publication_and_marks_result_read_only(
    client: TestClient,
    db_session: Session,
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

    audit_rows = (
        db_session.execute(
            text(
                "select action, target_type, target_id, metadata_json "
                "from audit_logs"
            )
        )
        .mappings()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0]["action"] == "publication_created"
    assert audit_rows[0]["target_type"] == "schedule_publication"
    assert audit_rows[0]["target_id"] == payload["id"]
    audit_metadata = json.loads(audit_rows[0]["metadata_json"])
    assert audit_metadata["schedule_run_id"] == run_id
    assert audit_metadata["assignment_snapshot_hash"] == payload["assignment_snapshot_hash"]


def test_publish_schedule_run_records_authenticated_actor_in_audit_log(
    client: TestClient,
    db_session: Session,
):
    run_id, result_payload = _create_recalculated_result(client)
    db_session.info["actor_context"] = ActorContext(
        user_id="user_scheduler",
        role="scheduler",
        auth_required=True,
    )

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
    audit_actor = db_session.execute(
        text(
            "select actor_user_id from audit_logs "
            "where action = 'publication_created'"
        )
    ).scalar_one()
    assert audit_actor == "user_scheduler"


def test_schedule_run_without_active_shift_type_marks_assignments_as_fallback(
    client: TestClient,
):
    _run_id, result_payload = _create_recalculated_result(client)

    assert result_payload["assignments"]
    assert {assignment["source"] for assignment in result_payload["assignments"]} == {
        "fallback"
    }


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


def test_publish_schedule_run_replaces_overlapping_publication_when_requested(
    client: TestClient,
    db_session: Session,
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
    first_publication_id = first_publish_response.json()["id"]

    second_run_id, second_result = _create_recalculated_result(client)
    response = client.post(
        f"/organizations/org_1/schedule-runs/{second_run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": second_result[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": second_result["issue_snapshot_hash"],
            "replace_overlapping_publication": True,
        },
    )

    assert response.status_code == 201
    second_publication_id = response.json()["id"]
    publications = db_session.execute(
        select(SchedulePublication).where(
            SchedulePublication.organization_id == "org_1"
        )
    ).scalars().all()
    statuses_by_id = {publication.id: publication.status for publication in publications}
    assert statuses_by_id[first_publication_id] == "archived"
    assert statuses_by_id[second_publication_id] == "published"
    assert [
        publication.id
        for publication in publications
        if publication.status == "published"
    ] == [second_publication_id]


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


def test_publish_schedule_run_requires_each_blocking_compliance_instance(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    run_id, result_payload = _create_recalculated_result(client)
    snapshot_hash = "compliance_snapshot_for_test"
    warnings = [
        ComplianceWarning(
            code="WEEKLY_HOURS_OVER_52",
            severity="blocking",
            publish_blocking=True,
            employee_id="emp_1",
            employee_name="Kim",
            slot_id=None,
            week_key="2026-W28",
            snapshot_hash=snapshot_hash,
            instance_key=compliance_warning_instance_key(
                warning_code="WEEKLY_HOURS_OVER_52",
                employee_id="emp_1",
                slot_id=None,
                week_key="2026-W28",
                snapshot_hash=snapshot_hash,
            ),
            message="주간 예정 근무 시간이 52시간을 초과합니다.",
            hours=63,
        ),
        ComplianceWarning(
            code="WEEKLY_HOURS_OVER_52",
            severity="blocking",
            publish_blocking=True,
            employee_id="emp_2",
            employee_name="Lee",
            slot_id=None,
            week_key="2026-W28",
            snapshot_hash=snapshot_hash,
            instance_key=compliance_warning_instance_key(
                warning_code="WEEKLY_HOURS_OVER_52",
                employee_id="emp_2",
                slot_id=None,
                week_key="2026-W28",
                snapshot_hash=snapshot_hash,
            ),
            message="주간 예정 근무 시간이 52시간을 초과합니다.",
            hours=63,
        ),
    ]
    monkeypatch.setattr(
        schedule_runs_module,
        "_compliance_warnings_for_artifacts",
        lambda _artifacts: warnings,
    )
    db_session.add(
        ComplianceWarningOverride(
            id="compliance_override_1",
            organization_id="org_1",
            schedule_run_id=run_id,
            warning_code="WEEKLY_HOURS_OVER_52",
            employee_id="emp_1",
            slot_id="",
            week_key="2026-W28",
            snapshot_hash=snapshot_hash,
            reason="emp_1 warning reviewed",
        )
    )
    db_session.commit()

    response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": result_payload[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": result_payload["issue_snapshot_hash"],
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "COMPLIANCE_OVERRIDE_REQUIRED"
    assert detail["warning_instances"] == [
        {
            "warning_code": "WEEKLY_HOURS_OVER_52",
            "employee_id": "emp_2",
            "slot_id": None,
            "week_key": "2026-W28",
            "snapshot_hash": snapshot_hash,
        }
    ]


def test_publish_schedule_run_accepts_current_compliance_override_instance(
    client: TestClient,
    db_session: Session,
):
    run_id, _result_payload = _create_recalculated_result(client)
    db_session.query(Assignment).filter_by(
        organization_id="org_1",
        schedule_run_id=run_id,
    ).delete(synchronize_session=False)
    slots = (
        db_session.query(ShiftSlot)
        .filter_by(organization_id="org_1", schedule_run_id=run_id)
        .order_by(ShiftSlot.local_date, ShiftSlot.id)
        .all()
    )
    for slot in slots:
        slot.label = "장시간 근무"
        slot.starts_at = f"{slot.local_date.isoformat()}T00:00:00+09:00"
        slot.ends_at = f"{slot.local_date.isoformat()}T20:00:00+09:00"
    db_session.add_all(
        [
            Assignment(
                id=f"{run_id}__compliance_assignment_{index}",
                organization_id="org_1",
                schedule_run_id=run_id,
                shift_slot_id=slot.id,
                role_id="role_senior",
                employee_id="emp_1",
                employee_name="Kim",
                source="solver",
                locked_by_user=False,
                warning_state="none",
                warning_message=None,
                attempt_no=1,
            )
            for index, slot in enumerate(slots, start=1)
        ]
    )
    db_session.commit()

    refreshed_result_response = client.get(
        f"/organizations/org_1/schedule-runs/{run_id}/result"
    )
    assert refreshed_result_response.status_code == 200
    refreshed_result = refreshed_result_response.json()
    warnings_response = client.get(
        f"/organizations/org_1/schedule-runs/{run_id}/compliance-warnings"
    )
    assert warnings_response.status_code == 200
    warning = next(
        item
        for item in warnings_response.json()["warnings"]
        if item["code"] == "WEEKLY_HOURS_OVER_52"
    )
    override_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/compliance-warning-overrides",
        json={
            "warning_code": warning["code"],
            "employee_id": warning["employee_id"],
            "slot_id": warning["slot_id"],
            "week_key": warning["week_key"],
            "snapshot_hash": warning["snapshot_hash"],
            "reason": "현재 warning instance 검토 완료",
        },
    )
    assert override_response.status_code == 201

    publish_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": refreshed_result[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": refreshed_result["issue_snapshot_hash"],
        },
    )

    assert publish_response.status_code == 201


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
    assert "local_date" not in sheet_xml
    assert "role_name" not in sheet_xml
    assert "publication_id" not in sheet_xml
    assert "warning_state" not in sheet_xml
    assert "일자" in sheet_xml
    assert "근무" in sheet_xml
    assert "역할" in sheet_xml
    assert "직원명" in sheet_xml
    assert "배정 방식" in sheet_xml
    assert "주의 사항" in sheet_xml
    assert "기본 배정" in sheet_xml
    assert "없음" in sheet_xml
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
    _process_next_schedule_run(client)
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
    _process_next_schedule_run(client)
    approval_response = client.post(
        f"/organizations/org_1/schedule-runs/{run_id}/relaxation-proposals/proposal_mock_time_off_1/approve",
        json={
            "reason": "관리자 승인",
            "notification_required": True,
        },
    )
    assert approval_response.status_code == 201
    return run_id


def _create_role_scoped_organization(client: TestClient, name: str) -> dict:
    organization_response = client.post(
        "/organizations",
        json={"name": name, "timezone": "Asia/Seoul"},
    )
    assert organization_response.status_code == 201
    organization = organization_response.json()
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
                    "name": "Kim",
                    "role_names": ["사수"],
                },
                {
                    "row_no": 2,
                    "employee_code": "E002",
                    "name": "Lee",
                    "role_names": ["부사수"],
                },
                {
                    "row_no": 3,
                    "employee_code": "E003",
                    "name": "Park",
                    "role_names": ["사수"],
                },
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
    return {
        "organization_id": organization_id,
        "senior_role_id": senior_role_id,
        "junior_role_id": junior_role_id,
        "employees_by_code": {
            employee["employee_code"]: employee
            for employee in employee_response.json()["employees"]
        },
    }


def _employee_row(
    row_no: int,
    employee_code: str,
    name: str,
    role_names: list[str],
) -> dict:
    return {
        "row_no": row_no,
        "employee_code": employee_code,
        "name": name,
        "role_names": role_names,
    }


def _process_next_schedule_run(client: TestClient) -> None:
    processed = process_next_schedule_run(
        queue=get_schedule_run_queue(),
        db_session_factory=lambda: nullcontext(client.app.state.test_db_session),
        executor=schedule_runs_module._execute_schedule_run_artifacts,
        dequeue_timeout_seconds=0,
    )
    assert processed is True


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
    session.flush()
    session.add_all(requirements)
    session.commit()


def _seed_run_history_comparison(session: Session) -> None:
    base_created_at = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    candidate_created_at = datetime(2026, 7, 1, 9, 5, tzinfo=timezone.utc)
    runs = [
        ScheduleRun(
            id="run_history_base",
            organization_id="org_1",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 2),
            template="one_shift_per_day",
            deterministic_mode=True,
            timeout_seconds=30,
            status="succeeded",
            solver_status="cp_sat_feasible",
            solution_quality="feasible_not_proven_optimal",
            current_attempt_no=1,
            recalculation_count=0,
            created_at=base_created_at,
            updated_at=base_created_at,
            started_at=base_created_at,
            finished_at=base_created_at,
        ),
        ScheduleRun(
            id="run_history_candidate",
            organization_id="org_1",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 2),
            template="one_shift_per_day",
            deterministic_mode=True,
            timeout_seconds=30,
            status="succeeded",
            solver_status="cp_sat_optimal",
            solution_quality="optimal",
            current_attempt_no=2,
            recalculation_count=1,
            created_at=candidate_created_at,
            updated_at=candidate_created_at,
            started_at=candidate_created_at,
            finished_at=candidate_created_at,
        ),
    ]
    session.add_all(runs)
    session.flush()

    slots = []
    for run in runs:
        for day_index in range(1, 3):
            local_date = date(2026, 7, day_index)
            slots.append(
                ShiftSlot(
                    id=f"{run.id}__slot_day_{day_index}",
                    organization_id="org_1",
                    schedule_run_id=run.id,
                    shift_type_id=None,
                    local_date=local_date,
                    label=f"{local_date.isoformat()} 주간",
                    starts_at=f"{local_date.isoformat()}T09:00:00+09:00",
                    ends_at=f"{local_date.isoformat()}T17:00:00+09:00",
                    timezone="Asia/Seoul",
                    status="generated",
                    attempt_no=run.current_attempt_no,
                )
            )
    session.add_all(slots)
    session.flush()

    session.add_all(
        [
            Assignment(
                id="run_history_base__assign_emp_1_day_1",
                organization_id="org_1",
                schedule_run_id="run_history_base",
                shift_slot_id="run_history_base__slot_day_1",
                role_id="role_senior",
                employee_id="emp_1",
                employee_name="Kim",
                source="solver",
                locked_by_user=False,
                warning_state="none",
                warning_message=None,
                attempt_no=1,
            ),
            Assignment(
                id="run_history_base__assign_emp_2_day_1",
                organization_id="org_1",
                schedule_run_id="run_history_base",
                shift_slot_id="run_history_base__slot_day_1",
                role_id="role_junior",
                employee_id="emp_2",
                employee_name="Lee",
                source="manual",
                locked_by_user=True,
                warning_state="manual_warning",
                warning_message="수동 고정",
                attempt_no=1,
            ),
            Assignment(
                id="run_history_base__assign_emp_3_day_2",
                organization_id="org_1",
                schedule_run_id="run_history_base",
                shift_slot_id="run_history_base__slot_day_2",
                role_id="role_senior",
                employee_id="emp_3",
                employee_name="Park",
                source="solver",
                locked_by_user=False,
                warning_state="none",
                warning_message=None,
                attempt_no=1,
            ),
            Assignment(
                id="run_history_candidate__assign_emp_3_day_1",
                organization_id="org_1",
                schedule_run_id="run_history_candidate",
                shift_slot_id="run_history_candidate__slot_day_1",
                role_id="role_senior",
                employee_id="emp_3",
                employee_name="Park",
                source="solver",
                locked_by_user=False,
                warning_state="none",
                warning_message=None,
                attempt_no=2,
            ),
            Assignment(
                id="run_history_candidate__assign_emp_2_day_1",
                organization_id="org_1",
                schedule_run_id="run_history_candidate",
                shift_slot_id="run_history_candidate__slot_day_1",
                role_id="role_junior",
                employee_id="emp_2",
                employee_name="Lee",
                source="manual",
                locked_by_user=True,
                warning_state="manual_warning",
                warning_message="수동 고정",
                attempt_no=2,
            ),
            Assignment(
                id="run_history_candidate__assign_emp_4_day_2",
                organization_id="org_1",
                schedule_run_id="run_history_candidate",
                shift_slot_id="run_history_candidate__slot_day_2",
                role_id="role_senior",
                employee_id="emp_4",
                employee_name="Choi",
                source="solver",
                locked_by_user=False,
                warning_state="none",
                warning_message=None,
                attempt_no=2,
            ),
        ]
    )
    session.add_all(
        [
            ScheduleIssue(
                id="run_history_base__issue_unfilled_day_1",
                organization_id="org_1",
                schedule_run_id="run_history_base",
                shift_slot_id="run_history_base__slot_day_1",
                role_id="role_senior",
                type="unfilled_requirement",
                missing_count=1,
                severity="medium",
                reason_code="unfilled_requirement",
                display_message="사수 1명이 부족합니다.",
                related_proposal_ids_json="[]",
                attempt_no=1,
            ),
            ScheduleIssue(
                id="run_history_candidate__issue_unfilled_day_2",
                organization_id="org_1",
                schedule_run_id="run_history_candidate",
                shift_slot_id="run_history_candidate__slot_day_2",
                role_id="role_senior",
                type="unfilled_requirement",
                missing_count=2,
                severity="high",
                reason_code="unfilled_requirement",
                display_message="사수 2명이 부족합니다.",
                related_proposal_ids_json="[]",
                attempt_no=2,
            ),
        ]
    )
    session.commit()


def _seed_p0_organization(session: Session) -> None:
    session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
    session.flush()
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

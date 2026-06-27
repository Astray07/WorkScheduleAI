from collections.abc import Generator
from datetime import date, datetime, timezone

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session, set_tenant_context
from work_schedule_ai.api.security import enforce_organization_access
from work_schedule_ai.api.signed_actor_tokens import sign_actor_token
from work_schedule_ai.db.models import (
    Base,
    Assignment,
    AuditLog,
    ComplianceWarningOverride,
    Employee,
    EmployeeRequest,
    EmployeeUserLink,
    DemandDriver,
    Membership,
    Organization,
    OverrideApproval,
    RagDocument,
    RagDocumentChunk,
    Role,
    ScheduleInputSnapshot,
    SchedulePolicy,
    SchedulePublication,
    PublicationNotification,
    ScheduleRecalculationRequest,
    ScheduleRun,
    ShiftType,
    Unavailability,
    User,
)


TEST_ACTOR_SECRET = "test-actor-secret-with-at-least-32-bytes"


def _enable_trusted_header_auth(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH", "1")


def test_auth_required_rejects_missing_actor(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client()

    response = client.get("/organizations/org_1/roles")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_auth_required_rejects_untrusted_header_actor(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.delenv("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH", raising=False)
    client = _client(seed_membership=True)

    response = client.get(
        "/organizations/org_1/roles",
        headers={"X-User-Id": "user_scheduler"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "TRUSTED_UPSTREAM_AUTH_REQUIRED"


def test_auth_required_allows_member(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client(seed_membership=True)

    response = client.get(
        "/organizations/org_1/roles",
        headers={"X-User-Id": "user_scheduler"},
    )

    assert response.status_code == 200


def test_auth_required_allows_signed_actor_without_trusted_upstream(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    monkeypatch.delenv("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH", raising=False)
    client = _client(seed_membership=True)
    token = sign_actor_token(
        secret=TEST_ACTOR_SECRET,
        organization_id="org_1",
        user_id="user_scheduler",
    )

    response = client.get(
        "/organizations/org_1/roles",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_auth_required_rejects_tampered_signed_actor(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client(seed_membership=True)
    token = sign_actor_token(
        secret=TEST_ACTOR_SECRET,
        organization_id="org_1",
        user_id="user_scheduler",
    )
    header, payload, signature = token.split(".")
    tampered = f"{header}.A{payload[1:]}.{signature}"

    response = client.get(
        "/organizations/org_1/roles",
        headers={"Authorization": f"Bearer {tampered}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_ACTOR_TOKEN"


def test_auth_required_rejects_signed_actor_for_other_organization(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client(seed_membership=True)
    token = sign_actor_token(
        secret=TEST_ACTOR_SECRET,
        organization_id="org_2",
        user_id="user_scheduler",
    )

    response = client.get(
        "/organizations/org_1/roles",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_ACTOR_TOKEN"


def test_auth_required_rejects_viewer_mutation(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client(seed_membership=True, role="viewer", user_id="user_viewer")

    response = client.post(
        "/organizations/org_1/demand-drivers",
        headers={"X-User-Id": "user_viewer"},
        json={
            "local_date": "2026-07-01",
            "segment": "day",
            "demand_count": 100,
            "required_staff_count": 4,
            "source": "manual",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


@pytest.mark.parametrize(
    ("role", "user_id", "method", "path", "payload", "count_model"),
    [
        (
            "viewer",
            "user_viewer",
            "PUT",
            "/organizations/org_1/schedule-policy",
            {
                "name": "viewer policy edit",
                "min_rest_hours": 11,
                "max_consecutive_shifts": 5,
                "max_shifts_per_week": 5,
                "weekend_shift_limit_per_month": 4,
                "night_shift_limit_per_month": 6,
                "default_unfilled_requirement_weight": 900,
                "weight_workload_imbalance": 100,
                "weight_pair_avoid_violation": 60,
                "unfilled_policy": "soft_penalty",
            },
            SchedulePolicy,
        ),
        (
            "viewer",
            "user_viewer",
            "POST",
            "/organizations/org_1/demand-drivers",
            {
                "local_date": "2026-07-01",
                "segment": "day",
                "demand_count": 100,
                "required_staff_count": 4,
                "source": "manual",
            },
            DemandDriver,
        ),
        (
            "employee",
            "user_employee",
            "POST",
            "/organizations/org_1/imports/apply",
            {
                "type": "employees",
                "format": "delimited",
                "mode": "upsert",
                "content": "employee_code,name,roles,max_shifts_per_week\nE003,Park,사수,5",
            },
            Employee,
        ),
        (
            "member",
            "user_member",
            "POST",
            "/organizations/org_1/shift-types",
            {
                "name": "저녁 근무",
                "local_start_time": "18:00",
                "local_end_time": "22:00",
                "timezone": "Asia/Seoul",
                "crosses_midnight": False,
                "active_weekdays": [0, 1, 2, 3, 4],
                "active": True,
                "requirements": [
                    {
                        "role_id": "role_senior",
                        "required_count": 1,
                        "unfilled_weight_override": None,
                    }
                ],
            },
            ShiftType,
        ),
        (
            "viewer",
            "user_viewer",
            "POST",
            "/organizations/org_1/employees/bulk-paste",
            {
                "mode": "upsert",
                "rows": [
                    {
                        "row_no": 1,
                        "employee_code": "E004",
                        "name": "Choi",
                        "role_names": ["사수"],
                        "max_shifts_per_week": 5,
                    }
                ],
            },
            Employee,
        ),
        (
            "viewer",
            "user_viewer",
            "POST",
            "/organizations/org_1/rag/documents",
            {
                "source_type": "organization_policy",
                "document_title": "저권한 생성 금지",
                "checked_at": "2026-06-26",
                "chunks": ["저권한 사용자는 RAG 문서를 생성할 수 없습니다."],
            },
            RagDocument,
        ),
    ],
)
def test_auth_required_rejects_low_privilege_reference_mutations(
    monkeypatch,
    role: str,
    user_id: str,
    method: str,
    path: str,
    payload: dict,
    count_model,
):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role=role,
        user_id=user_id,
        seed_reference_data=True,
    )
    before_count = session.query(count_model).count()

    response = client.request(
        method,
        path,
        headers={"X-User-Id": user_id},
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    assert session.query(count_model).count() == before_count


@pytest.mark.parametrize(
    ("method", "path", "payload", "count_model"),
    [
        (
            "POST",
            "/organizations/org_1/schedule-runs",
            {
                "period_start": "2026-07-01",
                "period_end": "2026-07-07",
            },
            ScheduleRun,
        ),
        (
            "POST",
            "/organizations/org_1/schedule-runs/run_1/manual-edits",
            {
                "slot_id": "slot_1",
                "role_id": "role_senior",
                "employee_id": "emp_1",
                "locked_by_user": True,
            },
            Assignment,
        ),
        (
            "POST",
            (
                "/organizations/org_1/schedule-runs/run_1/"
                "relaxation-proposals/proposal_1/approve"
            ),
            {
                "reason": "저권한 승인 금지",
                "notification_required": False,
            },
            OverrideApproval,
        ),
        (
            "POST",
            "/organizations/org_1/schedule-runs/run_1/recalculate",
            {"reason": "저권한 재계산 금지"},
            ScheduleRecalculationRequest,
        ),
        (
            "POST",
            "/organizations/org_1/schedule-runs/run_1/publications",
            {
                "expected_assignment_snapshot_hash": "assignment_hash",
                "expected_issue_snapshot_hash": "issue_hash",
            },
            SchedulePublication,
        ),
    ],
)
def test_auth_required_rejects_viewer_schedule_run_mutations_without_persistence(
    monkeypatch,
    method: str,
    path: str,
    payload: dict,
    count_model,
):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
        seed_reference_data=True,
        seed_schedule_run=True,
    )
    before_count = session.query(count_model).count()
    before_run_count = session.query(ScheduleRun).count()
    before_snapshot_count = session.query(ScheduleInputSnapshot).count()

    response = client.request(
        method,
        path,
        headers={"X-User-Id": "user_viewer"},
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    assert session.query(count_model).count() == before_count
    assert session.query(ScheduleRun).count() == before_run_count
    assert session.query(ScheduleInputSnapshot).count() == before_snapshot_count


def test_auth_required_rejects_viewer_cancel_without_state_change(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
        seed_schedule_run=True,
    )
    run = session.get(ScheduleRun, "run_1")
    assert run is not None
    before_status = run.status
    before_solver_status = run.solver_status
    before_solution_quality = run.solution_quality
    before_canceled_at = run.canceled_at

    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/cancel",
        headers={"X-User-Id": "user_viewer"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    session.refresh(run)
    assert run.status == before_status
    assert run.solver_status == before_solver_status
    assert run.solution_quality == before_solution_quality
    assert run.canceled_at == before_canceled_at


def test_auth_required_viewer_policy_read_does_not_create_policy(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
    )

    response = client.get(
        "/organizations/org_1/schedule-policy",
        headers={"X-User-Id": "user_viewer"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "기본 정책"
    assert session.query(SchedulePolicy).count() == 0


def test_auth_required_viewer_can_list_rag_documents_but_cannot_delete(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
    )
    _seed_rag_document(session)

    list_response = client.get(
        "/organizations/org_1/rag/documents",
        headers={"X-User-Id": "user_viewer"},
    )
    delete_response = client.delete(
        "/organizations/org_1/rag/documents/rag_doc_1",
        headers={"X-User-Id": "user_viewer"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["documents"][0]["document_title"] == "RAG 문서"
    assert delete_response.status_code == 403
    assert delete_response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


def test_auth_required_employee_cannot_list_rag_documents(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="employee",
        user_id="user_employee",
    )
    _seed_rag_document(session)

    response = client.get(
        "/organizations/org_1/rag/documents",
        headers={"X-User-Id": "user_employee"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


def test_auth_required_viewer_cannot_export_audit_logs(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
    )

    response = client.get(
        "/operations/organizations/org_1/audit-logs/export",
        headers={"X-User-Id": "user_viewer"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


def test_auth_required_viewer_cannot_dispatch_publication_notifications(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
        seed_reference_data=True,
        seed_schedule_run=True,
    )
    publication = SchedulePublication(
        id="publication_1",
        organization_id="org_1",
        schedule_run_id="run_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        status="published",
        assignment_snapshot_hash="assignment_hash",
        issue_snapshot_hash="issue_hash",
    )
    notification = PublicationNotification(
        id="notification_1",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        notification_type="published",
        channel="in_app",
        status="pending_recorded",
    )
    session.add_all([publication, notification])
    session.commit()

    response = client.post(
        "/operations/organizations/org_1/publication-notifications/dispatch",
        headers={"X-User-Id": "user_viewer"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    session.refresh(notification)
    assert notification.status == "pending_recorded"
    assert notification.delivery_attempts == 0
    assert notification.delivered_at is None
    assert notification.last_delivery_error is None


def test_auth_required_restricts_employee_request_to_linked_employee(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client(
        seed_membership=True,
        role="employee",
        user_id="user_employee",
        seed_employee_link=True,
    )

    own_response = client.post(
        "/organizations/org_1/employee-requests",
        headers={"X-User-Id": "user_employee"},
        json={
            "employee_id": "emp_1",
            "type": "unavailable",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "note": "개인 일정",
        },
    )
    other_response = client.post(
        "/organizations/org_1/employee-requests",
        headers={"X-User-Id": "user_employee"},
        json={
            "employee_id": "emp_2",
            "type": "unavailable",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "note": "다른 직원 요청",
        },
    )

    assert own_response.status_code == 201
    assert own_response.json()["requested_by_user_id"] == "user_employee"
    assert other_response.status_code == 403
    assert other_response.json()["detail"]["code"] == "EMPLOYEE_LINK_REQUIRED"


@pytest.mark.parametrize(
    ("role", "user_id", "action"),
    [
        ("viewer", "user_viewer", "approve"),
        ("member", "user_member", "reject"),
        ("employee", "user_employee", "approve"),
    ],
)
def test_auth_required_rejects_low_privilege_employee_request_review_without_persistence(
    monkeypatch,
    role: str,
    user_id: str,
    action: str,
):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role=role,
        user_id=user_id,
        seed_reference_data=True,
    )
    employee_request = EmployeeRequest(
        id="employee_request_1",
        organization_id="org_1",
        employee_id="emp_1",
        requested_by_user_id=None,
        type="unavailable",
        status="pending",
        starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        note="개인 일정",
    )
    session.add(employee_request)
    session.commit()
    before_unavailability_count = session.query(Unavailability).count()
    before_audit_count = session.query(AuditLog).count()

    response = client.post(
        f"/organizations/org_1/employee-requests/{employee_request.id}/{action}",
        headers={"X-User-Id": user_id},
        json={"reviewed_by_user_id": user_id, "reason": "저권한 검토 금지"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    session.refresh(employee_request)
    assert employee_request.status == "pending"
    assert employee_request.manager_reason is None
    assert employee_request.reviewed_by_user_id is None
    assert employee_request.reviewed_at is None
    assert employee_request.source_unavailability_id is None
    assert session.query(Unavailability).count() == before_unavailability_count
    assert session.query(AuditLog).count() == before_audit_count


def test_auth_required_rejects_viewer_compliance_override_without_persistence(
    monkeypatch,
):
    _enable_trusted_header_auth(monkeypatch)
    client, session = _client_and_session(
        seed_membership=True,
        role="viewer",
        user_id="user_viewer",
        seed_schedule_run=True,
    )
    before_override_count = session.query(ComplianceWarningOverride).count()
    before_audit_count = session.query(AuditLog).count()

    response = client.post(
        "/organizations/org_1/schedule-runs/run_1/compliance-warning-overrides",
        headers={"X-User-Id": "user_viewer"},
        json={
            "warning_code": "WEEKLY_HOURS_OVER_52",
            "employee_id": "emp_1",
            "slot_id": None,
            "week_key": "2026-W28",
            "snapshot_hash": "snapshot",
            "reason": "저권한 예외 승인 금지",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    assert session.query(ComplianceWarningOverride).count() == before_override_count
    assert session.query(AuditLog).count() == before_audit_count


def test_auth_required_disables_global_metrics(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client(seed_membership=True)

    response = client.get("/operations/schedule-runs/metrics")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "TENANT_SCOPE_REQUIRED"


def test_security_release_gate_reports_auth_mode(monkeypatch):
    _enable_trusted_header_auth(monkeypatch)
    client = _client(seed_membership=True)

    response = client.get("/operations/security/release-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_required"] is True
    assert payload["rbac_roles"] == ["owner", "admin", "scheduler", "viewer", "employee", "member"]
    assert payload["tenant_context_hook"] is True
    assert payload["actor_extraction_mode"] == "trusted_upstream_header"
    assert payload["public_saas_ready"] is False
    assert any("X-User-Id" in warning for warning in payload["warnings"])


def test_security_release_gate_keeps_signed_actor_mode_not_public_ready(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    monkeypatch.delenv("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH", raising=False)
    client = _client(seed_membership=True)

    response = client.get("/operations/security/release-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_required"] is True
    assert payload["actor_extraction_mode"] == "signed_actor_token"
    assert payload["public_saas_ready"] is False
    assert any("organization bootstrap" in warning for warning in payload["warnings"])


def test_security_release_gate_rejects_weak_signed_actor_secret(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", "short-secret")
    monkeypatch.delenv("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH", raising=False)
    client = _client(seed_membership=True)

    response = client.get("/operations/security/release-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_extraction_mode"] == "trusted_upstream_header"
    assert payload["public_saas_ready"] is False
    assert any("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET" in warning for warning in payload["warnings"])


def test_security_release_gate_rejects_weak_employee_link_secret(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    monkeypatch.setenv("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET", "short-secret")
    monkeypatch.delenv("WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH", raising=False)
    client = _client(seed_membership=True)

    response = client.get("/operations/security/release-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["public_saas_ready"] is False
    assert any("WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET" in warning for warning in payload["warnings"])


def _client(
    seed_membership: bool = False,
    role: str = "scheduler",
    user_id: str = "user_scheduler",
    seed_employee_link: bool = False,
    seed_reference_data: bool = False,
    seed_schedule_run: bool = False,
) -> TestClient:
    client, _session = _client_and_session(
        seed_membership=seed_membership,
        role=role,
        user_id=user_id,
        seed_employee_link=seed_employee_link,
        seed_reference_data=seed_reference_data,
        seed_schedule_run=seed_schedule_run,
    )
    return client


def _client_and_session(
    seed_membership: bool = False,
    role: str = "scheduler",
    user_id: str = "user_scheduler",
    seed_employee_link: bool = False,
    seed_reference_data: bool = False,
    seed_schedule_run: bool = False,
) -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
    if seed_membership:
        session.add(User(id=user_id, email=f"{user_id}@example.com", name=user_id))
        session.add(
            Membership(
                organization_id="org_1",
                user_id=user_id,
                role=role,
            )
        )
    if seed_reference_data or seed_employee_link:
        session.add_all(
            [
                Role(id="role_senior", organization_id="org_1", name="사수"),
                Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim"),
                Employee(id="emp_2", organization_id="org_1", employee_code="E002", name="Lee"),
            ]
        )
    if seed_employee_link:
        session.add_all(
            [
                EmployeeUserLink(
                    id="link_1",
                    organization_id="org_1",
                    employee_id="emp_1",
                    user_id=user_id,
                    status="linked",
                ),
            ]
        )
    if seed_schedule_run:
        session.add(
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
            )
        )
    session.commit()
    app = create_app()

    def override_session(request: Request) -> Generator[Session, None, None]:
        organization_id = request.path_params.get("organization_id")
        if organization_id:
            set_tenant_context(session, organization_id)
            enforce_organization_access(session, request, organization_id)
        yield session

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app), session


def _seed_rag_document(session: Session) -> None:
    session.add(
        RagDocument(
            id="rag_doc_1",
            organization_id="org_1",
            source_type="organization_policy",
            document_title="RAG 문서",
            checked_at=date(2026, 6, 26),
            content_hash="hash_1",
        )
    )
    session.add(
        RagDocumentChunk(
            id="rag_chunk_1",
            organization_id="org_1",
            document_id="rag_doc_1",
            chunk_index=0,
            excerpt="근무표 설명 근거입니다.",
        )
    )
    session.commit()

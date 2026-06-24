from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import (
    Base,
    Employee,
    EmployeeRole,
    Membership,
    Organization,
    OverrideApproval,
    PairConstraint,
    Role,
    ScheduleRecalculationRequest,
    ScheduleRun,
    ScheduleInputSnapshot,
    Unavailability,
    User,
    normalize_pair_employee_ids,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def test_employee_code_is_unique_within_organization(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    employee = Employee(
        id="emp_1",
        organization_id="org_1",
        employee_code="E001",
        name="Kim",
    )
    duplicate = Employee(
        id="emp_2",
        organization_id="org_1",
        employee_code="E001",
        name="Lee",
    )
    session.add(org)
    session.commit()

    session.add(employee)
    session.commit()

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_employee_code_can_repeat_across_organizations(session):
    org_1 = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    org_2 = Organization(id="org_2", name="Clinic B", timezone="Asia/Seoul")
    employee_1 = Employee(
        id="emp_1",
        organization_id="org_1",
        employee_code="E001",
        name="Kim",
    )
    employee_2 = Employee(
        id="emp_2",
        organization_id="org_2",
        employee_code="E001",
        name="Lee",
    )

    session.add_all([org_1, org_2])
    session.commit()

    session.add_all([employee_1, employee_2])
    session.commit()

    assert session.query(Employee).count() == 2


def test_role_name_is_unique_within_organization(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    role = Role(id="role_1", organization_id="org_1", name="사수")
    duplicate = Role(id="role_2", organization_id="org_1", name="사수")
    session.add(org)
    session.commit()

    session.add(role)
    session.commit()

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_role_name_can_repeat_across_organizations(session):
    org_1 = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    org_2 = Organization(id="org_2", name="Clinic B", timezone="Asia/Seoul")
    role_1 = Role(id="role_1", organization_id="org_1", name="사수")
    role_2 = Role(id="role_2", organization_id="org_2", name="사수")

    session.add_all([org_1, org_2])
    session.commit()

    session.add_all([role_1, role_2])
    session.commit()

    assert session.query(Role).count() == 2


def test_employee_role_assignment_cannot_be_duplicated(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    employee = Employee(
        id="emp_1",
        organization_id="org_1",
        employee_code="E001",
        name="Kim",
    )
    role = Role(id="role_1", organization_id="org_1", name="사수")
    assignment = EmployeeRole(
        id="employee_role_1",
        organization_id="org_1",
        employee_id="emp_1",
        role_id="role_1",
    )
    duplicate = EmployeeRole(
        id="employee_role_2",
        organization_id="org_1",
        employee_id="emp_1",
        role_id="role_1",
    )
    session.add(org)
    session.commit()

    session.add_all([employee, role])
    session.commit()

    session.add(assignment)
    session.commit()

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_pair_constraint_normalizes_employee_order(session):
    org, employee_a, employee_b = _organization_with_two_employees()
    pair = PairConstraint.create(
        id="pair_1",
        organization_id="org_1",
        employee_a_id=employee_b.id,
        employee_b_id=employee_a.id,
        type="blocked",
        severity="high",
        override_allowed=True,
    )

    session.add(org)
    session.commit()

    session.add_all([employee_a, employee_b])
    session.commit()

    session.add(pair)
    session.commit()

    assert pair.normalized_employee_a_id == "emp_a"
    assert pair.normalized_employee_b_id == "emp_b"


def test_inverse_pair_constraint_duplicate_is_rejected(session):
    org, employee_a, employee_b = _organization_with_two_employees()
    pair = PairConstraint.create(
        id="pair_1",
        organization_id="org_1",
        employee_a_id=employee_a.id,
        employee_b_id=employee_b.id,
        type="blocked",
        severity="high",
        override_allowed=True,
    )
    inverse_duplicate = PairConstraint.create(
        id="pair_2",
        organization_id="org_1",
        employee_a_id=employee_b.id,
        employee_b_id=employee_a.id,
        type="blocked",
        severity="high",
        override_allowed=True,
    )
    session.add(org)
    session.commit()

    session.add_all([employee_a, employee_b])
    session.commit()

    session.add(pair)
    session.commit()

    session.add(inverse_duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_pair_constraint_rejects_self_pair_before_db_insert():
    with pytest.raises(ValueError, match="cannot reference the same employee"):
        normalize_pair_employee_ids("emp_a", "emp_a")


def test_membership_is_unique_per_organization_user(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    user = User(id="user_1", email="admin@example.com", name="Admin")
    membership = Membership(organization_id="org_1", user_id="user_1", role="admin")
    duplicate = Membership(organization_id="org_1", user_id="user_1", role="admin")
    session.add_all([org, user])
    session.commit()

    session.add(membership)
    session.commit()
    session.expunge(membership)

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_unavailability_rejects_unknown_type(session):
    org, employee = _organization_with_employee()
    unavailability = Unavailability(
        id="unavailability_1",
        organization_id="org_1",
        employee_id="emp_1",
        type="sick_leave",
        starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        override_allowed=False,
    )
    session.add(org)
    session.commit()

    session.add(employee)
    session.commit()

    session.add(unavailability)

    with pytest.raises(IntegrityError):
        session.commit()


def test_unavailability_rejects_non_positive_time_range(session):
    org, employee = _organization_with_employee()
    unavailability = Unavailability(
        id="unavailability_1",
        organization_id="org_1",
        employee_id="emp_1",
        type="vacation",
        starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        override_allowed=False,
    )
    session.add(org)
    session.commit()

    session.add(employee)
    session.commit()

    session.add(unavailability)

    with pytest.raises(IntegrityError):
        session.commit()


def test_schedule_run_rejects_unknown_status(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    run = ScheduleRun(
        id="run_1",
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="done",
        solver_status="not_started",
        solution_quality="unknown",
        current_attempt_no=1,
        recalculation_count=0,
    )
    session.add(org)
    session.commit()

    session.add(run)

    with pytest.raises(IntegrityError):
        session.commit()


def test_schedule_run_rejects_recalculation_count_over_three(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    run = ScheduleRun(
        id="run_1",
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="succeeded",
        solver_status="not_started",
        solution_quality="feasible_not_proven_optimal",
        current_attempt_no=1,
        recalculation_count=4,
    )
    session.add(org)
    session.commit()

    session.add(run)

    with pytest.raises(IntegrityError):
        session.commit()


def test_schedule_input_snapshot_is_unique_per_schedule_run(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    run = ScheduleRun(
        id="run_1",
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="succeeded",
        solver_status="not_started",
        solution_quality="feasible_not_proven_optimal",
        current_attempt_no=1,
        recalculation_count=0,
    )
    snapshot = ScheduleInputSnapshot(
        id="snapshot_1",
        organization_id="org_1",
        schedule_run_id="run_1",
        snapshot_hash="hash_1",
        payload_json="{}",
    )
    duplicate = ScheduleInputSnapshot(
        id="snapshot_2",
        organization_id="org_1",
        schedule_run_id="run_1",
        snapshot_hash="hash_2",
        payload_json="{}",
    )
    session.add(org)
    session.commit()

    session.add(run)
    session.commit()

    session.add(snapshot)
    session.commit()

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_override_approval_is_unique_per_schedule_run_proposal(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    run = _schedule_run()
    approval = OverrideApproval(
        id="override_1",
        organization_id="org_1",
        schedule_run_id="run_1",
        relaxation_proposal_id="proposal_1",
        type="approve_time_off_override",
        notification_required=True,
        reason="Approved for P0 test",
    )
    duplicate = OverrideApproval(
        id="override_2",
        organization_id="org_1",
        schedule_run_id="run_1",
        relaxation_proposal_id="proposal_1",
        type="approve_time_off_override",
        notification_required=False,
        reason="Duplicate",
    )
    session.add(org)
    session.commit()

    session.add(run)
    session.commit()

    session.add(approval)
    session.commit()

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_schedule_recalculation_request_is_unique_per_run_idempotency_key(session):
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    run = _schedule_run()
    recalc = ScheduleRecalculationRequest(
        id="recalc_1",
        organization_id="org_1",
        schedule_run_id="run_1",
        idempotency_key="recalculate-key-1",
        reason="Approved override",
        recalculation_count=1,
    )
    duplicate = ScheduleRecalculationRequest(
        id="recalc_2",
        organization_id="org_1",
        schedule_run_id="run_1",
        idempotency_key="recalculate-key-1",
        reason="Duplicate",
        recalculation_count=1,
    )
    session.add(org)
    session.commit()

    session.add(run)
    session.commit()

    session.add(recalc)
    session.commit()

    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def _organization_with_two_employees():
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    employee_a = Employee(
        id="emp_a",
        organization_id="org_1",
        employee_code="E001",
        name="Kim",
    )
    employee_b = Employee(
        id="emp_b",
        organization_id="org_1",
        employee_code="E002",
        name="Lee",
    )
    return org, employee_a, employee_b


def _organization_with_employee():
    org = Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    employee = Employee(
        id="emp_1",
        organization_id="org_1",
        employee_code="E001",
        name="Kim",
    )
    return org, employee


def _schedule_run():
    return ScheduleRun(
        id="run_1",
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="succeeded",
        solver_status="not_started",
        solution_quality="feasible_not_proven_optimal",
        current_attempt_no=1,
        recalculation_count=0,
    )

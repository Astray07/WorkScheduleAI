from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import SessionLocal
from work_schedule_ai.api.routes.schedule_runs import (
    _execute_schedule_run_artifacts,
    _artifact_hashes,
    _result_artifacts_for_run,
    _result_snapshot_payload,
)
from work_schedule_ai.db.models import (
    Employee,
    EmployeeRole,
    Organization,
    OverrideApproval,
    PairConstraint,
    Role,
    ScheduleInputSnapshot,
    SchedulePublication,
    ScheduleRecalculationRequest,
    ScheduleRun,
    ShiftRequirement,
    ShiftType,
    Unavailability,
    utc_now,
)


DEMO_ORGANIZATION_ID = "org_demo_p0"
DEMO_RUN_ID = "run_demo_p0_recalculated"
DEMO_PUBLICATION_ID = "publication_demo_p0"

_KST = timezone(timedelta(hours=9))
_PERIOD_START = date(2026, 7, 1)
_PERIOD_END = date(2026, 7, 7)


@dataclass(frozen=True)
class SeedSummary:
    organization_id: str
    schedule_run_id: str
    publication_id: str
    employee_count: int
    status: str


def seed_demo(db_session: Session) -> SeedSummary:
    organization = _upsert_organization(db_session)
    roles = _upsert_roles(db_session, organization.id)
    employees = _upsert_employees(db_session, organization.id)
    _upsert_employee_roles(db_session, organization.id, roles, employees)
    _upsert_shift_type(db_session, organization.id, roles)
    _upsert_unavailability(db_session, organization.id, employees["E002"].id)
    _upsert_pair_constraint(
        db_session,
        organization.id,
        employees["E001"].id,
        employees["E002"].id,
    )
    run = _upsert_schedule_run(db_session, organization.id)
    snapshot = _upsert_input_snapshot(
        db_session,
        organization.id,
        run.id,
        employee_ids=[employee.id for employee in employees.values()],
        role_ids=[role.id for role in roles.values()],
    )
    run.input_snapshot_hash = snapshot.snapshot_hash
    _upsert_override_approval(db_session, organization.id, run.id)
    _upsert_recalculation_request(db_session, organization.id, run.id)
    db_session.flush()
    _execute_schedule_run_artifacts(db_session, run)
    artifacts = _result_artifacts_for_run(run, db_session)
    hashes = _artifact_hashes(artifacts)
    publication = _upsert_publication(
        db_session,
        organization.id,
        run.id,
        hashes.assignment_snapshot_hash,
        hashes.issue_snapshot_hash,
        result_snapshot_json=json.dumps(
            _result_snapshot_payload(artifacts),
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    db_session.commit()
    return SeedSummary(
        organization_id=organization.id,
        schedule_run_id=run.id,
        publication_id=publication.id,
        employee_count=len(employees),
        status="seeded",
    )


def main() -> None:
    with SessionLocal() as session:
        summary = seed_demo(session)
    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))


def _upsert_organization(db_session: Session) -> Organization:
    organization = db_session.get(Organization, DEMO_ORGANIZATION_ID)
    if organization is None:
        organization = Organization(
            id=DEMO_ORGANIZATION_ID,
            name="WorkScheduleAI Demo Clinic",
            timezone="Asia/Seoul",
        )
        db_session.add(organization)
    else:
        organization.name = "WorkScheduleAI Demo Clinic"
        organization.timezone = "Asia/Seoul"
    return organization


def _upsert_roles(db_session: Session, organization_id: str) -> dict[str, Role]:
    roles = {
        "사수": Role(
            id="role_demo_senior",
            organization_id=organization_id,
            name="사수",
            description="P0 demo senior role",
        ),
        "부사수": Role(
            id="role_demo_junior",
            organization_id=organization_id,
            name="부사수",
            description="P0 demo assistant role",
        ),
    }
    for role in roles.values():
        existing = db_session.get(Role, role.id)
        if existing is None:
            db_session.add(role)
        else:
            existing.name = role.name
            existing.description = role.description
    return {
        role.name: db_session.get(Role, role.id) or role for role in roles.values()
    }


def _upsert_employees(
    db_session: Session,
    organization_id: str,
) -> dict[str, Employee]:
    employees = {
        "E001": "Kim",
        "E002": "Lee",
        "E003": "Park",
        "E004": "Choi",
    }
    result: dict[str, Employee] = {}
    for index, (employee_code, name) in enumerate(employees.items(), start=1):
        employee_id = f"emp_demo_{index:03d}"
        employee = db_session.get(Employee, employee_id)
        if employee is None:
            employee = Employee(
                id=employee_id,
                organization_id=organization_id,
                employee_code=employee_code,
                name=name,
                active=True,
                max_shifts_per_week=5,
            )
            db_session.add(employee)
        else:
            employee.employee_code = employee_code
            employee.name = name
            employee.active = True
            employee.max_shifts_per_week = 5
        result[employee_code] = employee
    return result


def _upsert_employee_roles(
    db_session: Session,
    organization_id: str,
    roles: dict[str, Role],
    employees: dict[str, Employee],
) -> None:
    role_names_by_employee_code = {
        "E001": ["사수"],
        "E002": ["부사수"],
        "E003": ["사수"],
        "E004": ["사수"],
    }
    for employee in employees.values():
        for role_name in role_names_by_employee_code[employee.employee_code]:
            role = roles[role_name]
            link_id = f"employee_role_demo_{employee.employee_code}_{role.id}"
            link = db_session.get(EmployeeRole, link_id)
            if link is None:
                db_session.add(
                    EmployeeRole(
                        id=link_id,
                        organization_id=organization_id,
                        employee_id=employee.id,
                        role_id=role.id,
                        priority=100,
                        active=True,
                    )
                )
            else:
                link.employee_id = employee.id
                link.role_id = role.id
                link.priority = 100
                link.active = True


def _upsert_shift_type(
    db_session: Session,
    organization_id: str,
    roles: dict[str, Role],
) -> None:
    shift_type = db_session.get(ShiftType, "shift_type_demo_day")
    if shift_type is None:
        shift_type = ShiftType(
            id="shift_type_demo_day",
            organization_id=organization_id,
            name="주간 근무",
            local_start_time="09:00",
            local_end_time="18:00",
            timezone="Asia/Seoul",
            crosses_midnight=False,
            active=True,
        )
        db_session.add(shift_type)
    else:
        shift_type.name = "주간 근무"
        shift_type.local_start_time = "09:00"
        shift_type.local_end_time = "18:00"
        shift_type.timezone = "Asia/Seoul"
        shift_type.crosses_midnight = False
        shift_type.active = True
    db_session.flush()

    for role_name, role in roles.items():
        requirement_id = f"shift_requirement_demo_{role.id}"
        requirement = db_session.get(ShiftRequirement, requirement_id)
        if requirement is None:
            db_session.add(
                ShiftRequirement(
                    id=requirement_id,
                    organization_id=organization_id,
                    shift_type_id=shift_type.id,
                    role_id=role.id,
                    required_count=1,
                    unfilled_weight_override=None,
                )
            )
        else:
            requirement.shift_type_id = shift_type.id
            requirement.role_id = role.id
            requirement.required_count = 1
            requirement.unfilled_weight_override = None


def _upsert_unavailability(
    db_session: Session,
    organization_id: str,
    employee_id: str,
) -> None:
    unavailability = db_session.get(Unavailability, "unavail_demo_vacation_1")
    starts_at = datetime(2026, 7, 1, 0, 0, tzinfo=_KST)
    ends_at = datetime(2026, 7, 2, 0, 0, tzinfo=_KST)
    if unavailability is None:
        db_session.add(
            Unavailability(
                id="unavail_demo_vacation_1",
                organization_id=organization_id,
                employee_id=employee_id,
                type="vacation",
                starts_at=starts_at,
                ends_at=ends_at,
                override_allowed=True,
                note="P0 demo vacation",
            )
        )
    else:
        unavailability.employee_id = employee_id
        unavailability.starts_at = starts_at
        unavailability.ends_at = ends_at
        unavailability.override_allowed = True
        unavailability.note = "P0 demo vacation"


def _upsert_pair_constraint(
    db_session: Session,
    organization_id: str,
    employee_a_id: str,
    employee_b_id: str,
) -> None:
    pair_constraint = db_session.get(PairConstraint, "pair_demo_blocked_1")
    if pair_constraint is None:
        db_session.add(
            PairConstraint.create(
                id="pair_demo_blocked_1",
                organization_id=organization_id,
                employee_a_id=employee_a_id,
                employee_b_id=employee_b_id,
                type="blocked",
                severity="high",
                override_allowed=True,
                active=True,
            )
        )
    else:
        normalized_a, normalized_b = sorted((employee_a_id, employee_b_id))
        pair_constraint.employee_a_id = employee_a_id
        pair_constraint.employee_b_id = employee_b_id
        pair_constraint.normalized_employee_a_id = normalized_a
        pair_constraint.normalized_employee_b_id = normalized_b
        pair_constraint.type = "blocked"
        pair_constraint.severity = "high"
        pair_constraint.override_allowed = True
        pair_constraint.active = True


def _upsert_schedule_run(db_session: Session, organization_id: str) -> ScheduleRun:
    now = utc_now()
    run = db_session.get(ScheduleRun, DEMO_RUN_ID)
    if run is None:
        run = ScheduleRun(
            id=DEMO_RUN_ID,
            organization_id=organization_id,
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            template="one_shift_per_day",
            deterministic_mode=True,
            timeout_seconds=30,
            status="succeeded",
            solver_status="not_started",
            solution_quality="feasible_not_proven_optimal",
            current_attempt_no=1,
            recalculation_count=1,
            started_at=now,
            finished_at=now,
            updated_at=now,
        )
        db_session.add(run)
    else:
        run.status = "succeeded"
        run.solver_status = "not_started"
        run.solution_quality = "feasible_not_proven_optimal"
        run.current_attempt_no = 1
        run.recalculation_count = 1
        run.started_at = run.started_at or now
        run.finished_at = run.finished_at or now
        run.updated_at = now
    return run


def _upsert_input_snapshot(
    db_session: Session,
    organization_id: str,
    schedule_run_id: str,
    *,
    employee_ids: list[str],
    role_ids: list[str],
) -> ScheduleInputSnapshot:
    payload = {
        "organization_id": organization_id,
        "period_start": _PERIOD_START.isoformat(),
        "period_end": _PERIOD_END.isoformat(),
        "template": "one_shift_per_day",
        "deterministic_mode": True,
        "timeout_seconds": 30,
        "employee_ids": sorted(employee_ids),
        "role_ids": sorted(role_ids),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    snapshot_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    snapshot = db_session.execute(
        select(ScheduleInputSnapshot).where(
            ScheduleInputSnapshot.schedule_run_id == schedule_run_id
        )
    ).scalar_one_or_none()
    if snapshot is None:
        snapshot = ScheduleInputSnapshot(
            id="snapshot_demo_p0",
            organization_id=organization_id,
            schedule_run_id=schedule_run_id,
            snapshot_hash=snapshot_hash,
            payload_json=payload_json,
        )
        db_session.add(snapshot)
    else:
        snapshot.snapshot_hash = snapshot_hash
        snapshot.payload_json = payload_json
    return snapshot


def _upsert_override_approval(
    db_session: Session,
    organization_id: str,
    schedule_run_id: str,
) -> None:
    approval = db_session.get(OverrideApproval, "override_demo_p0_1")
    if approval is None:
        db_session.add(
            OverrideApproval(
                id="override_demo_p0_1",
                organization_id=organization_id,
                schedule_run_id=schedule_run_id,
                relaxation_proposal_id="proposal_mock_time_off_1",
                type="approve_time_off_override",
                notification_required=True,
                reason="P0 demo approval",
            )
        )
    else:
        approval.relaxation_proposal_id = "proposal_mock_time_off_1"
        approval.type = "approve_time_off_override"
        approval.notification_required = True
        approval.reason = "P0 demo approval"


def _upsert_recalculation_request(
    db_session: Session,
    organization_id: str,
    schedule_run_id: str,
) -> None:
    recalculation = db_session.get(ScheduleRecalculationRequest, "recalc_demo_p0_1")
    if recalculation is None:
        db_session.add(
            ScheduleRecalculationRequest(
                id="recalc_demo_p0_1",
                organization_id=organization_id,
                schedule_run_id=schedule_run_id,
                idempotency_key="seed-demo-recalc",
                reason="Seeded approved relaxation proposal",
                recalculation_count=1,
            )
        )
    else:
        recalculation.idempotency_key = "seed-demo-recalc"
        recalculation.reason = "Seeded approved relaxation proposal"
        recalculation.recalculation_count = 1


def _upsert_publication(
    db_session: Session,
    organization_id: str,
    schedule_run_id: str,
    assignment_snapshot_hash: str,
    issue_snapshot_hash: str,
    result_snapshot_json: str,
) -> SchedulePublication:
    now = utc_now()
    publication = db_session.get(SchedulePublication, DEMO_PUBLICATION_ID)
    if publication is None:
        publication = SchedulePublication(
            id=DEMO_PUBLICATION_ID,
            organization_id=organization_id,
            schedule_run_id=schedule_run_id,
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            status="published",
            assignment_snapshot_hash=assignment_snapshot_hash,
            issue_snapshot_hash=issue_snapshot_hash,
            result_snapshot_json=result_snapshot_json,
            published_at=now,
            created_at=now,
        )
        db_session.add(publication)
    else:
        publication.status = "published"
        publication.assignment_snapshot_hash = assignment_snapshot_hash
        publication.issue_snapshot_hash = issue_snapshot_hash
        publication.result_snapshot_json = result_snapshot_json
    return publication


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.security import (
    ADMIN_ROLES,
    RBAC_ROLES,
    READ_ROLES,
    actor_extraction_mode,
    is_auth_required,
    is_trusted_upstream_auth_configured,
    require_roles,
)
from work_schedule_ai.db.models import (
    Assignment,
    AuditLog,
    Employee,
    Role,
    SchedulePublication,
    ScheduleRun,
    ShiftSlot,
)


router = APIRouter(prefix="/operations", tags=["operations"])


SCHEDULE_RUN_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "infeasible",
    "failed",
    "canceled",
)


class ScheduleRunMetricsResponse(BaseModel):
    total_runs: int
    active_runs: int
    status_counts: dict[str, int]
    completed_average_duration_seconds: float | None


class AuditLogEntryResponse(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    organization_id: str
    entries: list[AuditLogEntryResponse]


class FairnessEmployeeRow(BaseModel):
    employee_id: str
    employee_code: str
    employee_name: str
    assignment_count: int
    delta_from_average: float


class FairnessSummaryResponse(BaseModel):
    organization_id: str
    schedule_run_id: str | None
    employee_count: int
    total_assignments: int
    average_assignments: float
    min_assignments: int
    max_assignments: int
    spread: int
    rows: list[FairnessEmployeeRow]


class LongTermFairnessEmployeeRow(BaseModel):
    employee_id: str
    employee_code: str
    employee_name: str
    assignment_count: int
    night_count: int
    weekend_count: int
    role_counts: dict[str, int]
    delta_from_average: float


class LongTermFairnessResponse(BaseModel):
    organization_id: str
    source: Literal["publications", "runs"]
    period_start: date | None
    period_end: date | None
    schedule_count: int
    publication_count: int
    run_count: int
    employee_count: int
    total_assignments: int
    average_assignments: float
    min_assignments: int
    max_assignments: int
    spread: int
    rows: list[LongTermFairnessEmployeeRow]


class SecurityReleaseGateResponse(BaseModel):
    auth_required: bool
    rbac_roles: list[str]
    tenant_context_hook: bool
    audit_export_available: bool
    actor_extraction_mode: str
    public_saas_ready: bool
    warnings: list[str]


@router.get(
    "/schedule-runs/metrics",
    response_model=ScheduleRunMetricsResponse,
)
def get_schedule_run_metrics(
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunMetricsResponse:
    if is_auth_required():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_SCOPE_REQUIRED",
                "message": "Global schedule run metrics are disabled when auth is enabled.",
                "field": "organization_id",
            },
        )
    runs = list(db_session.execute(select(ScheduleRun)).scalars())
    status_counts = {status: 0 for status in SCHEDULE_RUN_STATUSES}
    durations: list[float] = []
    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        if run.started_at is not None and run.finished_at is not None:
            durations.append((run.finished_at - run.started_at).total_seconds())

    return ScheduleRunMetricsResponse(
        total_runs=len(runs),
        active_runs=sum(status_counts[status] for status in ("queued", "running")),
        status_counts=status_counts,
        completed_average_duration_seconds=(
            round(sum(durations) / len(durations), 3) if durations else None
        ),
    )


@router.get(
    "/security/release-gate",
    response_model=SecurityReleaseGateResponse,
)
def get_security_release_gate() -> SecurityReleaseGateResponse:
    auth_required = is_auth_required()
    trusted_upstream_auth = is_trusted_upstream_auth_configured()
    actor_mode = actor_extraction_mode()
    warnings = []
    if not auth_required:
        warnings.append("WORKSCHEDULEAI_AUTH_REQUIRED is not enabled.")
    if actor_mode == "trusted_upstream_header" and not trusted_upstream_auth:
        warnings.append(
            "WORKSCHEDULEAI_TRUSTED_UPSTREAM_AUTH is not enabled; "
            "X-User-Id is only a trusted-upstream development contract."
        )
    if actor_mode == "trusted_upstream_header":
        warnings.append(
            "Actor extraction still relies on trusted X-User-Id header mode; "
            "JWT/session or signed actor verification is not implemented."
        )
    return SecurityReleaseGateResponse(
        auth_required=auth_required,
        rbac_roles=RBAC_ROLES,
        tenant_context_hook=True,
        audit_export_available=True,
        actor_extraction_mode=actor_mode,
        public_saas_ready=not warnings,
        warnings=warnings,
    )


@router.get(
    "/organizations/{organization_id}/audit-logs",
    response_model=AuditLogListResponse,
)
def get_organization_audit_logs(
    organization_id: str,
    limit: int = 20,
    db_session: Session = Depends(get_db_session),
) -> AuditLogListResponse:
    require_roles(db_session, ADMIN_ROLES)
    bounded_limit = min(max(limit, 1), 100)
    logs = list(
        db_session.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(bounded_limit)
        ).scalars()
    )
    return AuditLogListResponse(
        organization_id=organization_id,
        entries=[
            AuditLogEntryResponse(
                id=log.id,
                actor_user_id=log.actor_user_id,
                action=log.action,
                target_type=log.target_type,
                target_id=log.target_id,
                metadata=_parse_metadata(log.metadata_json),
                created_at=log.created_at,
            )
            for log in logs
        ],
    )


@router.get(
    "/organizations/{organization_id}/fairness/long-term",
    response_model=LongTermFairnessResponse,
)
def get_organization_long_term_fairness(
    organization_id: str,
    period_start: date | None = None,
    period_end: date | None = None,
    source: Literal["publications", "runs"] = "publications",
    db_session: Session = Depends(get_db_session),
) -> LongTermFairnessResponse:
    require_roles(db_session, READ_ROLES)
    if period_start is not None and period_end is not None and period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_start must be on or before period_end",
        )
    employees = _active_employees(organization_id, db_session)
    role_names = _role_names_by_id(organization_id, db_session)
    counts = _empty_long_term_counts(employees)
    if source == "publications":
        publication_count, run_count = _aggregate_publication_fairness(
            organization_id,
            period_start,
            period_end,
            role_names,
            counts,
            db_session,
        )
    else:
        publication_count, run_count = _aggregate_run_fairness(
            organization_id,
            period_start,
            period_end,
            role_names,
            counts,
            db_session,
        )
    rows = _long_term_fairness_rows(employees, counts)
    total_assignments = sum(row.assignment_count for row in rows)
    employee_count = len(employees)
    average = round(total_assignments / employee_count, 3) if employee_count else 0.0
    rows = [
        row.model_copy(
            update={
                "delta_from_average": round(row.assignment_count - average, 3),
            }
        )
        for row in rows
    ]
    rows.sort(key=lambda row: (-abs(row.delta_from_average), -row.assignment_count, row.employee_code))
    min_assignments = min((row.assignment_count for row in rows), default=0)
    max_assignments = max((row.assignment_count for row in rows), default=0)
    return LongTermFairnessResponse(
        organization_id=organization_id,
        source=source,
        period_start=period_start,
        period_end=period_end,
        schedule_count=publication_count if source == "publications" else run_count,
        publication_count=publication_count,
        run_count=run_count,
        employee_count=employee_count,
        total_assignments=total_assignments,
        average_assignments=average,
        min_assignments=min_assignments,
        max_assignments=max_assignments,
        spread=max_assignments - min_assignments,
        rows=rows,
    )


@router.get(
    "/organizations/{organization_id}/fairness/summary",
    response_model=FairnessSummaryResponse,
)
def get_organization_fairness_summary(
    organization_id: str,
    schedule_run_id: str | None = None,
    db_session: Session = Depends(get_db_session),
) -> FairnessSummaryResponse:
    require_roles(db_session, READ_ROLES)
    employees = list(
        db_session.execute(
            select(Employee)
            .where(Employee.organization_id == organization_id, Employee.active.is_(True))
            .order_by(Employee.employee_code)
        ).scalars()
    )
    counts = {employee.id: 0 for employee in employees}
    assignment_query = select(Assignment).where(
        Assignment.organization_id == organization_id,
    )
    if schedule_run_id is not None:
        assignment_query = assignment_query.where(
            Assignment.schedule_run_id == schedule_run_id,
        )
    for assignment in db_session.execute(assignment_query).scalars():
        if assignment.employee_id in counts:
            counts[assignment.employee_id] += 1

    employee_count = len(employees)
    total_assignments = sum(counts.values())
    average = round(total_assignments / employee_count, 3) if employee_count else 0.0
    min_assignments = min(counts.values()) if counts else 0
    max_assignments = max(counts.values()) if counts else 0

    rows = [
        FairnessEmployeeRow(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            employee_name=employee.name,
            assignment_count=counts[employee.id],
            delta_from_average=round(counts[employee.id] - average, 3),
        )
        for employee in employees
    ]
    rows.sort(key=lambda row: (-row.assignment_count, row.employee_code))

    return FairnessSummaryResponse(
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        employee_count=employee_count,
        total_assignments=total_assignments,
        average_assignments=average,
        min_assignments=min_assignments,
        max_assignments=max_assignments,
        spread=max_assignments - min_assignments,
        rows=rows,
    )


def _active_employees(
    organization_id: str,
    db_session: Session,
) -> list[Employee]:
    return list(
        db_session.execute(
            select(Employee)
            .where(Employee.organization_id == organization_id, Employee.active.is_(True))
            .order_by(Employee.employee_code)
        ).scalars()
    )


def _role_names_by_id(
    organization_id: str,
    db_session: Session,
) -> dict[str, str]:
    return {
        role.id: role.name
        for role in db_session.execute(
            select(Role).where(Role.organization_id == organization_id)
        ).scalars()
    }


def _empty_long_term_counts(
    employees: list[Employee],
) -> dict[str, dict[str, Any]]:
    return {
        employee.id: {
            "assignment_count": 0,
            "night_count": 0,
            "weekend_count": 0,
            "role_counts": {},
        }
        for employee in employees
    }


def _aggregate_publication_fairness(
    organization_id: str,
    period_start: date | None,
    period_end: date | None,
    role_names: dict[str, str],
    counts: dict[str, dict[str, Any]],
    db_session: Session,
) -> tuple[int, int]:
    query = select(SchedulePublication).where(
        SchedulePublication.organization_id == organization_id,
        SchedulePublication.status == "published",
    )
    if period_start is not None:
        query = query.where(SchedulePublication.period_end >= period_start)
    if period_end is not None:
        query = query.where(SchedulePublication.period_start <= period_end)
    publications = db_session.execute(query).scalars()
    included_publication_ids: set[str] = set()
    for publication in publications:
        try:
            snapshot = json.loads(publication.result_snapshot_json or "{}")
        except json.JSONDecodeError:
            continue
        slots = {
            slot.get("id"): slot
            for slot in snapshot.get("slots", [])
            if isinstance(slot, dict) and slot.get("id")
        }
        for assignment in snapshot.get("assignments", []):
            if not isinstance(assignment, dict):
                continue
            slot = slots.get(assignment.get("slot_id"))
            if slot is None:
                continue
            slot_date = _snapshot_slot_date(slot)
            if not _date_in_period(slot_date, period_start, period_end):
                continue
            if _add_long_term_assignment(
                counts=counts,
                employee_id=str(assignment.get("employee_id", "")),
                role_name=role_names.get(
                    str(assignment.get("role_id", "")),
                    str(assignment.get("role_id", "")),
                ),
                slot_date=slot_date,
                label=str(slot.get("label", "")),
                starts_at=str(slot.get("starts_at", "")),
            ):
                included_publication_ids.add(publication.id)
    return len(included_publication_ids), 0


def _aggregate_run_fairness(
    organization_id: str,
    period_start: date | None,
    period_end: date | None,
    role_names: dict[str, str],
    counts: dict[str, dict[str, Any]],
    db_session: Session,
) -> tuple[int, int]:
    query = (
        select(Assignment, ShiftSlot)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(ScheduleRun, Assignment.schedule_run_id == ScheduleRun.id)
        .where(
            Assignment.organization_id == organization_id,
            ShiftSlot.organization_id == organization_id,
            ScheduleRun.organization_id == organization_id,
            ScheduleRun.status.in_(("succeeded", "infeasible")),
        )
    )
    if period_start is not None:
        query = query.where(ShiftSlot.local_date >= period_start)
    if period_end is not None:
        query = query.where(ShiftSlot.local_date <= period_end)
    included_run_ids: set[str] = set()
    for assignment, slot in db_session.execute(query):
        if _add_long_term_assignment(
            counts=counts,
            employee_id=assignment.employee_id,
            role_name=role_names.get(assignment.role_id, assignment.role_id),
            slot_date=slot.local_date,
            label=slot.label,
            starts_at=slot.starts_at,
        ):
            included_run_ids.add(assignment.schedule_run_id)
    return 0, len(included_run_ids)


def _add_long_term_assignment(
    *,
    counts: dict[str, dict[str, Any]],
    employee_id: str,
    role_name: str,
    slot_date: date,
    label: str,
    starts_at: str,
) -> bool:
    employee_counts = counts.get(employee_id)
    if employee_counts is None:
        return False
    employee_counts["assignment_count"] += 1
    if _is_night_slot(label, starts_at):
        employee_counts["night_count"] += 1
    if slot_date.weekday() >= 5:
        employee_counts["weekend_count"] += 1
    role_counts = employee_counts["role_counts"]
    role_counts[role_name] = role_counts.get(role_name, 0) + 1
    return True


def _long_term_fairness_rows(
    employees: list[Employee],
    counts: dict[str, dict[str, Any]],
) -> list[LongTermFairnessEmployeeRow]:
    rows: list[LongTermFairnessEmployeeRow] = []
    for employee in employees:
        employee_counts = counts[employee.id]
        rows.append(
            LongTermFairnessEmployeeRow(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                employee_name=employee.name,
                assignment_count=int(employee_counts["assignment_count"]),
                night_count=int(employee_counts["night_count"]),
                weekend_count=int(employee_counts["weekend_count"]),
                role_counts=dict(sorted(employee_counts["role_counts"].items())),
                delta_from_average=0.0,
            )
        )
    return rows


def _snapshot_slot_date(slot: dict[str, Any]) -> date:
    value = slot.get("local_date")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _date_in_period(
    value: date,
    period_start: date | None,
    period_end: date | None,
) -> bool:
    if period_start is not None and value < period_start:
        return False
    if period_end is not None and value > period_end:
        return False
    return True


def _is_night_slot(label: str, starts_at: str) -> bool:
    if "야간" in label:
        return True
    start_time = _time_part(starts_at)
    return bool(start_time and (start_time >= "18:00" or start_time < "06:00"))


def _time_part(value: str) -> str | None:
    if "T" not in value:
        return None
    return value.split("T", 1)[1][:5]


def _parse_metadata(raw_metadata: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_metadata)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}

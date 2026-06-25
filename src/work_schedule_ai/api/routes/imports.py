from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.routes.policies import DEFAULT_POLICY
from work_schedule_ai.db.models import (
    Employee,
    EmployeeRole,
    Organization,
    PairConstraint,
    Role,
    SchedulePolicy,
    Unavailability,
    utc_now,
)


router = APIRouter(prefix="/organizations", tags=["imports"])

ImportType = Literal["employees", "unavailabilities", "pair_constraints", "policy"]

EMPLOYEE_MAX_SHIFTS_PER_WEEK_RANGE = (0, 31)
POLICY_INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "min_rest_hours": (0, 48),
    "max_consecutive_shifts": (1, 31),
    "max_shifts_per_week": (1, 31),
    "weekend_shift_limit_per_month": (0, 31),
    "night_shift_limit_per_month": (0, 31),
    "default_unfilled_requirement_weight": (0, 10000),
    "weight_workload_imbalance": (0, 10000),
    "weight_pair_avoid_violation": (0, 10000),
}


class ImportRequest(BaseModel):
    type: ImportType
    content: str = Field(min_length=1)


class ImportApplyRequest(ImportRequest):
    mode: Literal["upsert"] = "upsert"


class ImportErrorResponse(BaseModel):
    code: str
    message: str
    field: str | None = None
    row_no: int | None = None


class ImportPreviewResponse(BaseModel):
    type: ImportType
    valid: bool
    rows: list[dict[str, str]]
    errors: list[ImportErrorResponse]
    applied_count: int = 0


REQUIRED_COLUMNS: dict[ImportType, tuple[str, ...]] = {
    "employees": ("employee_code", "name", "roles", "max_shifts_per_week"),
    "unavailabilities": (
        "employee_code",
        "type",
        "starts_at",
        "ends_at",
        "override_allowed",
    ),
    "pair_constraints": (
        "employee_code_a",
        "employee_code_b",
        "type",
        "severity",
        "override_allowed",
    ),
    "policy": ("key", "value"),
}


@router.post(
    "/{organization_id}/imports/preview",
    response_model=ImportPreviewResponse,
)
def preview_import(
    organization_id: str,
    request: ImportRequest,
    db_session: Session = Depends(get_db_session),
) -> ImportPreviewResponse:
    _get_organization_or_404(organization_id, db_session)
    rows = _parse_rows(request.content)
    errors = _validate_rows(
        organization_id=organization_id,
        import_type=request.type,
        rows=rows,
        db_session=db_session,
    )
    return ImportPreviewResponse(
        type=request.type,
        valid=not errors,
        rows=rows,
        errors=errors,
    )


@router.post(
    "/{organization_id}/imports/apply",
    response_model=ImportPreviewResponse,
)
def apply_import(
    organization_id: str,
    request: ImportApplyRequest,
    db_session: Session = Depends(get_db_session),
) -> ImportPreviewResponse:
    preview = preview_import(
        organization_id=organization_id,
        request=ImportRequest(type=request.type, content=request.content),
        db_session=db_session,
    )
    if not preview.valid:
        return preview

    if request.type == "employees":
        applied_count = _apply_employee_rows(organization_id, preview.rows, db_session)
    elif request.type == "unavailabilities":
        applied_count = _apply_unavailability_rows(
            organization_id,
            preview.rows,
            db_session,
        )
    elif request.type == "pair_constraints":
        applied_count = _apply_pair_rows(organization_id, preview.rows, db_session)
    else:
        applied_count = _apply_policy_rows(organization_id, preview.rows, db_session)

    db_session.commit()
    preview.applied_count = applied_count
    return preview


def _parse_rows(content: str) -> list[dict[str, str]]:
    stripped = content.strip()
    if not stripped:
        return []
    first_line = stripped.splitlines()[0]
    delimiter = "\t" if "\t" in first_line else ","
    reader = csv.DictReader(StringIO(stripped), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({key: (value or "").strip() for key, value in row.items() if key})
    return rows


def _validate_rows(
    *,
    organization_id: str,
    import_type: ImportType,
    rows: list[dict[str, str]],
    db_session: Session,
) -> list[ImportErrorResponse]:
    errors: list[ImportErrorResponse] = []
    if not rows:
        return [
            ImportErrorResponse(
                code="NO_ROWS",
                message="Import content must include at least one data row.",
            )
        ]

    required_columns = REQUIRED_COLUMNS[import_type]
    present_columns = set(rows[0])
    for column in required_columns:
        if column not in present_columns:
            errors.append(
                ImportErrorResponse(
                    code="MISSING_COLUMN",
                    message="Required column is missing.",
                    field=column,
                    row_no=1,
                )
            )
    if errors:
        return errors

    validators = {
        "employees": _validate_employee_row,
        "unavailabilities": _validate_unavailability_row,
        "pair_constraints": _validate_pair_row,
        "policy": _validate_policy_row,
    }
    for index, row in enumerate(rows, start=1):
        errors.extend(
            validators[import_type](
                organization_id,
                index,
                row,
                db_session,
            )
        )
    return errors


def _validate_employee_row(
    organization_id: str,
    row_no: int,
    row: dict[str, str],
    db_session: Session,
) -> list[ImportErrorResponse]:
    errors = _required_value_errors(row_no, row, ("employee_code", "name", "roles"))
    roles = _role_names(row.get("roles", ""))
    role_by_name = _role_by_name(organization_id, db_session)
    if roles and any(role_name not in role_by_name for role_name in roles):
        errors.append(
            _row_error(row_no, "roles", "UNKNOWN_ROLE", "Unknown role name.")
        )
    if row.get("max_shifts_per_week"):
        errors.extend(
            _integer_range_errors(
                row_no=row_no,
                field="max_shifts_per_week",
                raw_value=row["max_shifts_per_week"],
                bounds=EMPLOYEE_MAX_SHIFTS_PER_WEEK_RANGE,
            )
        )
    return errors


def _validate_unavailability_row(
    organization_id: str,
    row_no: int,
    row: dict[str, str],
    db_session: Session,
) -> list[ImportErrorResponse]:
    errors = _required_value_errors(
        row_no,
        row,
        ("employee_code", "type", "starts_at", "ends_at", "override_allowed"),
    )
    if row.get("employee_code") and _employee_by_code(
        organization_id,
        db_session,
    ).get(row["employee_code"]) is None:
        errors.append(
            _row_error(row_no, "employee_code", "UNKNOWN_EMPLOYEE", "Unknown employee code.")
        )
    if row.get("type") not in {"vacation", "business_trip", "training", "personal"}:
        errors.append(_row_error(row_no, "type", "INVALID_TYPE", "Invalid type."))
    starts_at = _parse_datetime(row.get("starts_at", ""))
    ends_at = _parse_datetime(row.get("ends_at", ""))
    if row.get("starts_at") and starts_at is None:
        errors.append(_row_error(row_no, "starts_at", "INVALID_DATETIME", "Invalid starts_at."))
    if row.get("ends_at") and ends_at is None:
        errors.append(_row_error(row_no, "ends_at", "INVALID_DATETIME", "Invalid ends_at."))
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        errors.append(_row_error(row_no, "ends_at", "INVALID_RANGE", "ends_at must be after starts_at."))
    if row.get("override_allowed") and _parse_bool(row["override_allowed"]) is None:
        errors.append(_row_error(row_no, "override_allowed", "INVALID_BOOLEAN", "Invalid boolean."))
    return errors


def _validate_pair_row(
    organization_id: str,
    row_no: int,
    row: dict[str, str],
    db_session: Session,
) -> list[ImportErrorResponse]:
    errors = _required_value_errors(
        row_no,
        row,
        ("employee_code_a", "employee_code_b", "type", "severity", "override_allowed"),
    )
    employee_by_code = _employee_by_code(organization_id, db_session)
    employee_a = employee_by_code.get(row.get("employee_code_a", ""))
    employee_b = employee_by_code.get(row.get("employee_code_b", ""))
    if row.get("employee_code_a") and employee_a is None:
        errors.append(_row_error(row_no, "employee_code_a", "UNKNOWN_EMPLOYEE", "Unknown employee code."))
    if row.get("employee_code_b") and employee_b is None:
        errors.append(_row_error(row_no, "employee_code_b", "UNKNOWN_EMPLOYEE", "Unknown employee code."))
    if employee_a is not None and employee_b is not None and employee_a.id == employee_b.id:
        errors.append(_row_error(row_no, "employee_code_b", "SELF_PAIR", "Pair must use two employees."))
    if row.get("type") not in {"blocked", "avoid", "prefer"}:
        errors.append(_row_error(row_no, "type", "INVALID_TYPE", "Invalid type."))
    if row.get("severity") not in {"low", "medium", "high", "critical"}:
        errors.append(_row_error(row_no, "severity", "INVALID_SEVERITY", "Invalid severity."))
    if row.get("override_allowed") and _parse_bool(row["override_allowed"]) is None:
        errors.append(_row_error(row_no, "override_allowed", "INVALID_BOOLEAN", "Invalid boolean."))
    return errors


def _validate_policy_row(
    organization_id: str,
    row_no: int,
    row: dict[str, str],
    db_session: Session,
) -> list[ImportErrorResponse]:
    _ = organization_id, db_session
    errors = _required_value_errors(row_no, row, ("key", "value"))
    allowed_keys = set(DEFAULT_POLICY)
    if row.get("key") and row["key"] not in allowed_keys:
        errors.append(_row_error(row_no, "key", "UNKNOWN_POLICY_KEY", "Unknown policy key."))
    if row.get("key") == "unfilled_policy" and row.get("value") != "soft_penalty":
        errors.append(_row_error(row_no, "value", "INVALID_POLICY", "미배정은 soft_penalty만 지원합니다."))
    if row.get("key") in POLICY_INTEGER_RANGES:
        errors.extend(
            _integer_range_errors(
                row_no=row_no,
                field="value",
                raw_value=row.get("value", ""),
                bounds=POLICY_INTEGER_RANGES[row["key"]],
                label=row["key"],
            )
        )
    return errors


def _integer_range_errors(
    *,
    row_no: int,
    field: str,
    raw_value: str,
    bounds: tuple[int, int],
    label: str | None = None,
) -> list[ImportErrorResponse]:
    value = _parse_int(raw_value)
    display_name = label or field
    if value is None:
        return [
            _row_error(
                row_no,
                field,
                "INVALID_INTEGER",
                f"{display_name} must be an integer.",
            )
        ]
    minimum, maximum = bounds
    if value < minimum or value > maximum:
        return [
            _row_error(
                row_no,
                field,
                "INVALID_RANGE",
                f"{display_name} must be between {minimum} and {maximum}.",
            )
        ]
    return []


def _required_value_errors(
    row_no: int,
    row: dict[str, str],
    fields: tuple[str, ...],
) -> list[ImportErrorResponse]:
    return [
        _row_error(row_no, field, "REQUIRED", "Required value is missing.")
        for field in fields
        if not row.get(field)
    ]


def _apply_employee_rows(
    organization_id: str,
    rows: list[dict[str, str]],
    db_session: Session,
) -> int:
    role_by_name = _role_by_name(organization_id, db_session)
    employees_by_code = _employee_by_code(organization_id, db_session)
    applied_count = 0
    for row in rows:
        employee = employees_by_code.get(row["employee_code"])
        if employee is None:
            employee = Employee(
                id=_new_id("emp"),
                organization_id=organization_id,
                employee_code=row["employee_code"],
                name=row["name"],
                active=True,
                max_shifts_per_week=_parse_int(row.get("max_shifts_per_week", "")),
            )
            db_session.add(employee)
            db_session.flush()
            employees_by_code[employee.employee_code] = employee
        else:
            employee.name = row["name"]
            employee.active = True
            employee.max_shifts_per_week = _parse_int(row.get("max_shifts_per_week", ""))
            db_session.query(EmployeeRole).filter_by(
                organization_id=organization_id,
                employee_id=employee.id,
            ).delete()
        db_session.add_all(
            [
                EmployeeRole(
                    id=_new_id("employee_role"),
                    organization_id=organization_id,
                    employee_id=employee.id,
                    role_id=role_by_name[role_name].id,
                )
                for role_name in _role_names(row["roles"])
            ]
        )
        applied_count += 1
    return applied_count


def _apply_unavailability_rows(
    organization_id: str,
    rows: list[dict[str, str]],
    db_session: Session,
) -> int:
    employee_by_code = _employee_by_code(organization_id, db_session)
    for row in rows:
        db_session.add(
            Unavailability(
                id=_new_id("unavailability"),
                organization_id=organization_id,
                employee_id=employee_by_code[row["employee_code"]].id,
                type=row["type"],
                starts_at=_parse_datetime(row["starts_at"]),
                ends_at=_parse_datetime(row["ends_at"]),
                override_allowed=bool(_parse_bool(row["override_allowed"])),
                note="Imported",
            )
        )
    return len(rows)


def _apply_pair_rows(
    organization_id: str,
    rows: list[dict[str, str]],
    db_session: Session,
) -> int:
    employee_by_code = _employee_by_code(organization_id, db_session)
    applied_count = 0
    for row in rows:
        employee_a = employee_by_code[row["employee_code_a"]]
        employee_b = employee_by_code[row["employee_code_b"]]
        pair_constraint = PairConstraint.create(
            id=_new_id("pair"),
            organization_id=organization_id,
            employee_a_id=employee_a.id,
            employee_b_id=employee_b.id,
            type=row["type"],
            severity=row["severity"],
            override_allowed=bool(_parse_bool(row["override_allowed"])),
            active=True,
        )
        existing = db_session.execute(
            select(PairConstraint).where(
                PairConstraint.organization_id == organization_id,
                PairConstraint.normalized_employee_a_id == pair_constraint.normalized_employee_a_id,
                PairConstraint.normalized_employee_b_id == pair_constraint.normalized_employee_b_id,
                PairConstraint.type == pair_constraint.type,
            )
        ).scalar_one_or_none()
        if existing is None:
            db_session.add(pair_constraint)
        else:
            existing.severity = row["severity"]
            existing.override_allowed = bool(_parse_bool(row["override_allowed"]))
            existing.active = True
        applied_count += 1
    return applied_count


def _apply_policy_rows(
    organization_id: str,
    rows: list[dict[str, str]],
    db_session: Session,
) -> int:
    policy = db_session.execute(
        select(SchedulePolicy).where(SchedulePolicy.organization_id == organization_id)
    ).scalar_one_or_none()
    values = DEFAULT_POLICY.copy()
    if policy is not None:
        values.update(
            {
                "name": policy.name,
                "min_rest_hours": policy.min_rest_hours,
                "max_consecutive_shifts": policy.max_consecutive_shifts,
                "max_shifts_per_week": policy.max_shifts_per_week,
                "weekend_shift_limit_per_month": policy.weekend_shift_limit_per_month,
                "night_shift_limit_per_month": policy.night_shift_limit_per_month,
                "default_unfilled_requirement_weight": policy.default_unfilled_requirement_weight,
                "weight_workload_imbalance": policy.weight_workload_imbalance,
                "weight_pair_avoid_violation": policy.weight_pair_avoid_violation,
                "unfilled_policy": policy.unfilled_policy,
            }
        )
    for row in rows:
        key = row["key"]
        values[key] = row["value"] if key in {"name", "unfilled_policy"} else int(row["value"])
    if policy is None:
        policy = SchedulePolicy(
            id=_new_id("schedule_policy"),
            organization_id=organization_id,
            **values,
        )
        db_session.add(policy)
    else:
        for key, value in values.items():
            setattr(policy, key, value)
        policy.updated_at = utc_now()
    return len(rows)


def _role_names(raw_value: str) -> list[str]:
    delimiter = "|" if "|" in raw_value else ";"
    return [role_name.strip() for role_name in raw_value.split(delimiter) if role_name.strip()]


def _role_by_name(
    organization_id: str,
    db_session: Session,
) -> dict[str, Role]:
    roles = db_session.execute(
        select(Role).where(Role.organization_id == organization_id)
    ).scalars()
    return {role.name: role for role in roles}


def _employee_by_code(
    organization_id: str,
    db_session: Session,
) -> dict[str, Employee]:
    employees = db_session.execute(
        select(Employee).where(Employee.organization_id == organization_id)
    ).scalars()
    return {employee.employee_code: employee for employee in employees}


def _parse_bool(raw_value: str) -> bool | None:
    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "허용"}:
        return True
    if normalized in {"false", "0", "no", "n", "불가"}:
        return False
    return None


def _parse_int(raw_value: str) -> int | None:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(raw_value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _row_error(
    row_no: int,
    field: str,
    code: str,
    message: str,
) -> ImportErrorResponse:
    return ImportErrorResponse(
        code=code,
        message=message,
        field=field,
        row_no=row_no,
    )


def _get_organization_or_404(
    organization_id: str,
    db_session: Session,
) -> Organization:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return organization


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

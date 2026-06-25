from __future__ import annotations

import base64
import csv
from datetime import datetime
from io import BytesIO, StringIO
import posixpath
import re
from typing import Literal
from uuid import uuid4
import zipfile
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy import delete, select
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
    ShiftRequirement,
    ShiftType,
    Unavailability,
    utc_now,
)


router = APIRouter(prefix="/organizations", tags=["imports"])

ImportType = Literal[
    "employees",
    "unavailabilities",
    "pair_constraints",
    "policy",
    "shift_types",
]
ImportFormat = Literal["delimited", "xlsx"]

EMPLOYEE_MAX_SHIFTS_PER_WEEK_RANGE = (0, 31)
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
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
    content: str = ""
    format: ImportFormat = "delimited"
    content_base64: str | None = None
    sheet_name: str | None = None

    @model_validator(mode="after")
    def validate_content_for_format(self):
        if self.format == "delimited" and not self.content.strip():
            raise ValueError("content is required for delimited imports")
        if self.format == "xlsx" and not self.content_base64:
            raise ValueError("content_base64 is required for xlsx imports")
        return self


class ImportApplyRequest(ImportRequest):
    mode: Literal["upsert"] = "upsert"


class ImportErrorResponse(BaseModel):
    code: str
    message: str
    sheet: str | None = None
    field: str | None = None
    column: str | None = None
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
    "shift_types": (
        "shift_type",
        "local_start_time",
        "local_end_time",
        "timezone",
        "crosses_midnight",
        "active_weekdays",
        "active",
        "role_name",
        "required_count",
        "unfilled_weight_override",
    ),
}


@router.post(
    "/{organization_id}/imports/preview",
    response_model=ImportPreviewResponse,
    response_model_exclude_none=True,
)
def preview_import(
    organization_id: str,
    request: ImportRequest,
    db_session: Session = Depends(get_db_session),
) -> ImportPreviewResponse:
    _get_organization_or_404(organization_id, db_session)
    rows, sheet_name, row_numbers, header_row_no, include_column = _parse_import_rows(request)
    errors = _validate_rows(
        organization_id=organization_id,
        import_type=request.type,
        rows=rows,
        db_session=db_session,
        sheet_name=sheet_name,
        row_numbers=row_numbers,
        header_row_no=header_row_no,
        include_column=include_column,
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
    response_model_exclude_none=True,
)
def apply_import(
    organization_id: str,
    request: ImportApplyRequest,
    db_session: Session = Depends(get_db_session),
) -> ImportPreviewResponse:
    preview = preview_import(
        organization_id=organization_id,
        request=ImportRequest(
            type=request.type,
            content=request.content,
            format=request.format,
            content_base64=request.content_base64,
            sheet_name=request.sheet_name,
        ),
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
    elif request.type == "policy":
        applied_count = _apply_policy_rows(organization_id, preview.rows, db_session)
    else:
        applied_count = _apply_shift_type_rows(organization_id, preview.rows, db_session)

    db_session.commit()
    preview.applied_count = applied_count
    return preview


def _parse_import_rows(
    request: ImportRequest,
) -> tuple[list[dict[str, str]], str | None, list[int] | None, int, bool]:
    if request.format == "xlsx":
        sheet_name = request.sheet_name or request.type
        rows, row_numbers, header_row_no = _parse_xlsx_rows(
            request.content_base64,
            sheet_name,
        )
        return rows, sheet_name, row_numbers, header_row_no, True
    return _parse_rows(request.content), None, None, 1, False


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


def _parse_xlsx_rows(
    content_base64: str | None,
    sheet_name: str,
) -> tuple[list[dict[str, str]], list[int], int]:
    if not content_base64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "XLSX_CONTENT_REQUIRED",
                "message": "content_base64 is required for xlsx imports.",
                "field": "content_base64",
            },
        )
    try:
        workbook_bytes = base64.b64decode(content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_XLSX_BASE64",
                "message": "content_base64 must be valid base64.",
                "field": "content_base64",
            },
        ) from exc

    try:
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook:
            worksheet_path = _xlsx_worksheet_path(workbook, sheet_name)
            shared_strings = _xlsx_shared_strings(workbook)
            table = _xlsx_worksheet_table(workbook, worksheet_path, shared_strings)
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_XLSX_FILE",
                "message": "Uploaded content is not a readable .xlsx file.",
                "field": "content_base64",
            },
        ) from exc

    if not table:
        return [], [], 1
    header_row_no, header_values = table[0]
    headers = [header.strip() for header in header_values]
    rows: list[dict[str, str]] = []
    row_numbers: list[int] = []
    for row_no, values in table[1:]:
        if not any(value.strip() for value in values):
            continue
        rows.append(
            {
                header: (values[index] if index < len(values) else "").strip()
                for index, header in enumerate(headers)
                if header
            }
        )
        row_numbers.append(row_no)
    return rows, row_numbers, header_row_no


def _xlsx_worksheet_path(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    relationships = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    target_by_id = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships
    }
    for sheet in workbook_xml.findall(f".//{_xlsx_tag('sheet')}"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        relationship_id = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if relationship_id is None or relationship_id not in target_by_id:
            break
        target = target_by_id[relationship_id]
        if target.startswith("/"):
            return target.lstrip("/")
        return posixpath.normpath(posixpath.join("xl", target))
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "XLSX_SHEET_NOT_FOUND",
            "message": f"Sheet '{sheet_name}' was not found.",
            "field": "sheet_name",
        },
    )


def _xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    shared_xml = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in shared_xml.findall(f".//{_xlsx_tag('si')}"):
        values.append("".join(text.text or "" for text in item.findall(f".//{_xlsx_tag('t')}")))
    return values


def _xlsx_worksheet_table(
    workbook: zipfile.ZipFile,
    worksheet_path: str,
    shared_strings: list[str],
) -> list[tuple[int, list[str]]]:
    worksheet_xml = ET.fromstring(workbook.read(worksheet_path))
    rows: list[tuple[int, list[str]]] = []
    for row in worksheet_xml.findall(f".//{_xlsx_tag('row')}"):
        row_number = _parse_int(row.attrib.get("r", "")) or len(rows) + 1
        values_by_index: dict[int, str] = {}
        for cell in row.findall(_xlsx_tag("c")):
            cell_ref = cell.attrib.get("r", "")
            column_index = _xlsx_column_index(cell_ref)
            if column_index is None:
                column_index = len(values_by_index) + 1
            values_by_index[column_index] = _xlsx_cell_value(cell, shared_strings)
        if values_by_index:
            max_index = max(values_by_index)
            rows.append(
                (
                    row_number,
                    [values_by_index.get(index, "") for index in range(1, max_index + 1)],
                )
            )
    return rows


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(f".//{_xlsx_tag('t')}"))

    value_element = cell.find(_xlsx_tag("v"))
    raw_value = value_element.text if value_element is not None else ""
    if cell_type == "s" and raw_value:
        index = _parse_int(raw_value)
        if index is not None and 0 <= index < len(shared_strings):
            return shared_strings[index]
    return raw_value or ""


def _xlsx_tag(name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/spreadsheetml/2006/main}}{name}"


def _xlsx_column_index(cell_ref: str) -> int | None:
    match = re.match(r"([A-Z]+)", cell_ref)
    if match is None:
        return None
    index = 0
    for letter in match.group(1):
        index = index * 26 + (ord(letter) - 64)
    return index


def _validate_rows(
    *,
    organization_id: str,
    import_type: ImportType,
    rows: list[dict[str, str]],
    db_session: Session,
    sheet_name: str | None = None,
    row_numbers: list[int] | None = None,
    header_row_no: int = 1,
    include_column: bool = False,
) -> list[ImportErrorResponse]:
    errors: list[ImportErrorResponse] = []
    if not rows:
        return [
            ImportErrorResponse(
                code="NO_ROWS",
                message="Import content must include at least one data row.",
                sheet=sheet_name,
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
                    sheet=sheet_name,
                    field=column,
                    column=column if include_column else None,
                    row_no=header_row_no,
                )
            )
    if errors:
        return errors

    validators = {
        "employees": _validate_employee_row,
        "unavailabilities": _validate_unavailability_row,
        "pair_constraints": _validate_pair_row,
        "policy": _validate_policy_row,
        "shift_types": _validate_shift_type_row,
    }
    for index, row in enumerate(rows):
        row_no = row_numbers[index] if row_numbers is not None else index + 1
        row_errors = validators[import_type](
                organization_id,
                row_no,
                row,
                db_session,
        )
        errors.extend(_with_import_context(row_errors, sheet_name, include_column))
    if import_type == "shift_types":
        errors.extend(
            _with_import_context(
                _validate_shift_type_batch(rows, row_numbers),
                sheet_name,
                include_column,
            )
        )
    return errors


def _with_import_context(
    errors: list[ImportErrorResponse],
    sheet_name: str | None,
    include_column: bool,
) -> list[ImportErrorResponse]:
    for error in errors:
        error.sheet = sheet_name
        if include_column and error.field is not None:
            error.column = error.field
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


def _validate_shift_type_row(
    organization_id: str,
    row_no: int,
    row: dict[str, str],
    db_session: Session,
) -> list[ImportErrorResponse]:
    errors = _required_value_errors(
        row_no,
        row,
        (
            "shift_type",
            "local_start_time",
            "local_end_time",
            "timezone",
            "crosses_midnight",
            "active_weekdays",
            "active",
            "role_name",
            "required_count",
        ),
    )
    role_by_name = _role_by_name(organization_id, db_session)
    if row.get("role_name") and row["role_name"] not in role_by_name:
        errors.append(_row_error(row_no, "role_name", "UNKNOWN_ROLE", "Unknown role name."))

    starts_at = row.get("local_start_time", "")
    ends_at = row.get("local_end_time", "")
    if starts_at and not _valid_local_time(starts_at):
        errors.append(_row_error(row_no, "local_start_time", "INVALID_TIME", "Invalid local_start_time."))
    if ends_at and not _valid_local_time(ends_at):
        errors.append(_row_error(row_no, "local_end_time", "INVALID_TIME", "Invalid local_end_time."))
    if starts_at and ends_at and starts_at == ends_at:
        errors.append(
            _row_error(
                row_no,
                "local_end_time",
                "INVALID_TIME_RANGE",
                "local_start_time and local_end_time must differ.",
            )
        )

    if row.get("crosses_midnight") and _parse_bool(row["crosses_midnight"]) is None:
        errors.append(_row_error(row_no, "crosses_midnight", "INVALID_BOOLEAN", "Invalid boolean."))
    if row.get("active") and _parse_bool(row["active"]) is None:
        errors.append(_row_error(row_no, "active", "INVALID_BOOLEAN", "Invalid boolean."))
    if row.get("active_weekdays") and _parse_active_weekdays(row["active_weekdays"]) is None:
        errors.append(
            _row_error(
                row_no,
                "active_weekdays",
                "INVALID_WEEKDAYS",
                "active_weekdays must contain unique values between 0 and 6.",
            )
        )
    if row.get("required_count"):
        errors.extend(
            _integer_range_errors(
                row_no=row_no,
                field="required_count",
                raw_value=row["required_count"],
                bounds=(1, 20),
            )
        )
    if row.get("unfilled_weight_override"):
        errors.extend(
            _integer_range_errors(
                row_no=row_no,
                field="unfilled_weight_override",
                raw_value=row["unfilled_weight_override"],
                bounds=(0, 10000),
            )
        )
    return errors


def _validate_shift_type_batch(
    rows: list[dict[str, str]],
    row_numbers: list[int] | None = None,
) -> list[ImportErrorResponse]:
    errors: list[ImportErrorResponse] = []
    seen: set[tuple[str, str]] = set()
    definition_by_shift_type: dict[str, tuple[str, ...]] = {}
    for index, row in enumerate(rows):
        row_no = row_numbers[index] if row_numbers is not None else index + 1
        shift_type = row.get("shift_type", "")
        definition = _shift_type_definition_key(row)
        if shift_type and shift_type in definition_by_shift_type:
            if definition_by_shift_type[shift_type] != definition:
                errors.append(
                    _row_error(
                        row_no,
                        "shift_type",
                        "CONFLICTING_SHIFT_TYPE_DEFINITION",
                        "Rows for the same shift_type must use the same shift definition.",
                    )
                )
        elif shift_type:
            definition_by_shift_type[shift_type] = definition

        key = (row.get("shift_type", ""), row.get("role_name", ""))
        if not all(key):
            continue
        if key in seen:
            errors.append(
                _row_error(
                    row_no,
                    "role_name",
                    "DUPLICATE_REQUIREMENT",
                    "shift_type and role_name must be unique within the import.",
                )
            )
        seen.add(key)
    return errors


def _shift_type_definition_key(row: dict[str, str]) -> tuple[str, ...]:
    weekdays = _parse_active_weekdays(row.get("active_weekdays", ""))
    return (
        row.get("local_start_time", ""),
        row.get("local_end_time", ""),
        row.get("timezone", ""),
        str(_parse_bool(row.get("crosses_midnight", ""))),
        _serialize_active_weekdays(weekdays or []),
        str(_parse_bool(row.get("active", ""))),
    )


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


def _apply_shift_type_rows(
    organization_id: str,
    rows: list[dict[str, str]],
    db_session: Session,
) -> int:
    role_by_name = _role_by_name(organization_id, db_session)
    existing_shift_types = {
        shift_type.name: shift_type
        for shift_type in db_session.execute(
            select(ShiftType).where(ShiftType.organization_id == organization_id)
        ).scalars()
    }
    rows_by_shift_type: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        rows_by_shift_type.setdefault(row["shift_type"], []).append(row)

    for shift_type_name, shift_rows in rows_by_shift_type.items():
        first_row = shift_rows[0]
        shift_type = existing_shift_types.get(shift_type_name)
        if shift_type is None:
            shift_type = ShiftType(
                id=_new_id("shift_type"),
                organization_id=organization_id,
                name=shift_type_name,
                local_start_time=first_row["local_start_time"],
                local_end_time=first_row["local_end_time"],
                timezone=first_row["timezone"],
                crosses_midnight=bool(_parse_bool(first_row["crosses_midnight"])),
                active_weekdays=_serialize_active_weekdays(
                    _parse_active_weekdays(first_row["active_weekdays"]) or []
                ),
                active=bool(_parse_bool(first_row["active"])),
            )
            db_session.add(shift_type)
            db_session.flush()
            existing_shift_types[shift_type_name] = shift_type
        else:
            shift_type.local_start_time = first_row["local_start_time"]
            shift_type.local_end_time = first_row["local_end_time"]
            shift_type.timezone = first_row["timezone"]
            shift_type.crosses_midnight = bool(_parse_bool(first_row["crosses_midnight"]))
            shift_type.active_weekdays = _serialize_active_weekdays(
                _parse_active_weekdays(first_row["active_weekdays"]) or []
            )
            shift_type.active = bool(_parse_bool(first_row["active"]))

        db_session.execute(
            delete(ShiftRequirement).where(
                ShiftRequirement.organization_id == organization_id,
                ShiftRequirement.shift_type_id == shift_type.id,
            )
        )
        db_session.add_all(
            [
                ShiftRequirement(
                    id=_new_id("shift_requirement"),
                    organization_id=organization_id,
                    shift_type_id=shift_type.id,
                    role_id=role_by_name[row["role_name"]].id,
                    required_count=int(row["required_count"]),
                    unfilled_weight_override=_parse_int(row.get("unfilled_weight_override", "")),
                )
                for row in shift_rows
            ]
        )
    return len(rows)


def _role_names(raw_value: str) -> list[str]:
    delimiter = "|" if "|" in raw_value else ";"
    return [role_name.strip() for role_name in raw_value.split(delimiter) if role_name.strip()]


def _parse_active_weekdays(raw_value: str) -> list[int] | None:
    delimiter = "|" if "|" in raw_value else ";" if ";" in raw_value else ","
    weekdays: list[int] = []
    for part in raw_value.split(delimiter):
        value = _parse_int(part.strip())
        if value is None or value < 0 or value > 6 or value in weekdays:
            return None
        weekdays.append(value)
    return sorted(weekdays) if weekdays else None


def _serialize_active_weekdays(weekdays: list[int]) -> str:
    return ",".join(str(day) for day in sorted(weekdays))


def _valid_local_time(raw_value: str) -> bool:
    if not TIME_PATTERN.match(raw_value):
        return False
    hour, minute = raw_value.split(":")
    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


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

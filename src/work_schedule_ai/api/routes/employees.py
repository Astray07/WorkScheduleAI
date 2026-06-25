from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Employee, EmployeeRole, Organization, Role


router = APIRouter(prefix="/organizations", tags=["employees"])


class EmployeeBulkPasteRow(BaseModel):
    row_no: int = Field(ge=1)
    employee_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    role_names: list[str]
    max_shifts_per_week: int | None = Field(default=None, ge=0)


class EmployeeBulkPasteRequest(BaseModel):
    mode: Literal["validate_only", "upsert"]
    rows: list[EmployeeBulkPasteRow] = Field(min_length=1, max_length=100)


class FieldError(BaseModel):
    code: str
    message: str
    field: str | None = None
    row_no: int | None = Field(default=None, ge=1)


class EmployeeResponse(BaseModel):
    id: str
    employee_code: str
    name: str
    active: bool
    role_ids: list[str]


class EmployeeBulkPasteResponse(BaseModel):
    valid: bool
    created_count: int
    updated_count: int
    errors: list[FieldError]
    employees: list[EmployeeResponse]


class EmployeeDetailResponse(BaseModel):
    id: str
    employee_code: str
    name: str
    active: bool
    role_ids: list[str]
    role_names: list[str]
    max_shifts_per_week: int | None


class EmployeeUpdateRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    active: bool = True
    role_names: list[str]
    max_shifts_per_week: int | None = Field(default=None, ge=0)


@router.post(
    "/{organization_id}/employees/bulk-paste",
    response_model=EmployeeBulkPasteResponse,
)
def bulk_paste_employees(
    organization_id: str,
    request: EmployeeBulkPasteRequest,
    db_session: Session = Depends(get_db_session),
) -> EmployeeBulkPasteResponse:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    roles = db_session.execute(
        select(Role).where(Role.organization_id == organization_id)
    ).scalars()
    role_by_name = {role.name: role for role in roles}
    errors = _validate_rows(request.rows, role_by_name)
    if errors:
        return EmployeeBulkPasteResponse(
            valid=False,
            created_count=0,
            updated_count=0,
            errors=errors,
            employees=[],
        )

    if request.mode == "validate_only":
        return EmployeeBulkPasteResponse(
            valid=True,
            created_count=0,
            updated_count=0,
            errors=[],
            employees=[],
        )

    return _upsert_employees(
        organization_id=organization_id,
        rows=request.rows,
        role_by_name=role_by_name,
        db_session=db_session,
    )


@router.get(
    "/{organization_id}/employees",
    response_model=list[EmployeeDetailResponse],
)
def list_employees(
    organization_id: str,
    db_session: Session = Depends(get_db_session),
) -> list[EmployeeDetailResponse]:
    _get_organization_or_404(organization_id, db_session)
    employees = list(
        db_session.execute(
            select(Employee)
            .where(Employee.organization_id == organization_id)
            .order_by(Employee.employee_code)
        ).scalars()
    )
    return [
        _employee_detail_response(organization_id, employee, db_session)
        for employee in employees
    ]


@router.patch(
    "/{organization_id}/employees/{employee_id}",
    response_model=EmployeeDetailResponse,
)
def update_employee(
    organization_id: str,
    employee_id: str,
    request: EmployeeUpdateRequest,
    db_session: Session = Depends(get_db_session),
) -> EmployeeDetailResponse:
    _get_organization_or_404(organization_id, db_session)
    employee = db_session.get(Employee, employee_id)
    if employee is None or employee.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")

    duplicate = db_session.execute(
        select(Employee).where(
            Employee.organization_id == organization_id,
            Employee.employee_code == request.employee_code,
            Employee.id != employee_id,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMPLOYEE_CODE_DUPLICATE",
                "message": "employee_code already exists in the organization.",
                "field": "employee_code",
            },
        )

    roles = db_session.execute(
        select(Role).where(Role.organization_id == organization_id)
    ).scalars()
    role_by_name = {role.name: role for role in roles}
    unknown_roles = [
        role_name for role_name in request.role_names if role_name not in role_by_name
    ]
    if unknown_roles:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNKNOWN_ROLE",
                "message": "role_names contains a role that does not exist.",
                "field": "role_names",
            },
        )

    employee.employee_code = request.employee_code
    employee.name = request.name
    employee.active = request.active
    employee.max_shifts_per_week = request.max_shifts_per_week
    db_session.execute(
        delete(EmployeeRole).where(
            EmployeeRole.organization_id == organization_id,
            EmployeeRole.employee_id == employee.id,
        )
    )
    db_session.add_all(
        [
            EmployeeRole(
                id=_new_id("employee_role"),
                organization_id=organization_id,
                employee_id=employee.id,
                role_id=role_by_name[role_name].id,
            )
            for role_name in dict.fromkeys(request.role_names)
        ]
    )
    db_session.commit()
    return _employee_detail_response(organization_id, employee, db_session)


@router.delete(
    "/{organization_id}/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_employee(
    organization_id: str,
    employee_id: str,
    db_session: Session = Depends(get_db_session),
) -> Response:
    _get_organization_or_404(organization_id, db_session)
    employee = db_session.get(Employee, employee_id)
    if employee is None or employee.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.active = False
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validate_rows(
    rows: list[EmployeeBulkPasteRow],
    role_by_name: dict[str, Role],
) -> list[FieldError]:
    errors: list[FieldError] = []
    seen_employee_codes: set[str] = set()
    for row in rows:
        if row.employee_code in seen_employee_codes:
            errors.append(
                FieldError(
                    code="DUPLICATE_EMPLOYEE_CODE",
                    message="employee_code is duplicated in the pasted rows.",
                    field="employee_code",
                    row_no=row.row_no,
                )
            )
        else:
            seen_employee_codes.add(row.employee_code)

        if any(role_name not in role_by_name for role_name in row.role_names):
            errors.append(
                FieldError(
                    code="UNKNOWN_ROLE",
                    message="role_names contains a role that does not exist.",
                    field="role_names",
                    row_no=row.row_no,
                )
            )
    return errors


def _upsert_employees(
    *,
    organization_id: str,
    rows: list[EmployeeBulkPasteRow],
    role_by_name: dict[str, Role],
    db_session: Session,
) -> EmployeeBulkPasteResponse:
    employee_codes = [row.employee_code for row in rows]
    existing_employees = db_session.execute(
        select(Employee).where(
            Employee.organization_id == organization_id,
            Employee.employee_code.in_(employee_codes),
        )
    ).scalars()
    employee_by_code = {
        employee.employee_code: employee for employee in existing_employees
    }

    created_count = 0
    updated_count = 0
    employee_responses: list[EmployeeResponse] = []

    for row in rows:
        role_ids = _role_ids_for_row(row, role_by_name)
        employee = employee_by_code.get(row.employee_code)
        if employee is None:
            employee = Employee(
                id=_new_id("emp"),
                organization_id=organization_id,
                employee_code=row.employee_code,
                name=row.name,
                active=True,
                max_shifts_per_week=row.max_shifts_per_week,
            )
            db_session.add(employee)
            employee_by_code[row.employee_code] = employee
            created_count += 1
        else:
            employee.name = row.name
            employee.active = True
            employee.max_shifts_per_week = row.max_shifts_per_week
            db_session.execute(
                delete(EmployeeRole).where(
                    EmployeeRole.organization_id == organization_id,
                    EmployeeRole.employee_id == employee.id,
                )
            )
            updated_count += 1

        db_session.add_all(
            [
                EmployeeRole(
                    id=_new_id("employee_role"),
                    organization_id=organization_id,
                    employee_id=employee.id,
                    role_id=role_id,
                )
                for role_id in role_ids
            ]
        )
        employee_responses.append(
            EmployeeResponse(
                id=employee.id,
                employee_code=employee.employee_code,
                name=employee.name,
                active=employee.active,
                role_ids=role_ids,
            )
        )

    db_session.commit()
    return EmployeeBulkPasteResponse(
        valid=True,
        created_count=created_count,
        updated_count=updated_count,
        errors=[],
        employees=employee_responses,
    )


def _role_ids_for_row(
    row: EmployeeBulkPasteRow,
    role_by_name: dict[str, Role],
) -> list[str]:
    return [role_by_name[role_name].id for role_name in dict.fromkeys(row.role_names)]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


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


def _employee_detail_response(
    organization_id: str,
    employee: Employee,
    db_session: Session,
) -> EmployeeDetailResponse:
    roles = list(
        db_session.execute(
            select(Role, EmployeeRole)
            .join(EmployeeRole, EmployeeRole.role_id == Role.id)
            .where(
                EmployeeRole.organization_id == organization_id,
                EmployeeRole.employee_id == employee.id,
                EmployeeRole.active.is_(True),
            )
            .order_by(Role.name)
        ).all()
    )
    return EmployeeDetailResponse(
        id=employee.id,
        employee_code=employee.employee_code,
        name=employee.name,
        active=employee.active,
        role_ids=[role.id for role, _role_link in roles],
        role_names=[role.name for role, _role_link in roles],
        max_shifts_per_week=employee.max_shifts_per_week,
    )

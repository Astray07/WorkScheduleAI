from __future__ import annotations

import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    Organization,
    Role,
    ShiftRequirement,
    ShiftType,
)


router = APIRouter(prefix="/organizations", tags=["shift-types"])

TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
DEFAULT_ACTIVE_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]


class ShiftRequirementCreateRequest(BaseModel):
    role_id: str
    required_count: int = Field(ge=1, le=20)
    unfilled_weight_override: int | None = Field(default=None, ge=0)


class ShiftTypeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    local_start_time: str = Field(pattern=TIME_PATTERN.pattern)
    local_end_time: str = Field(pattern=TIME_PATTERN.pattern)
    timezone: str = Field(min_length=1, max_length=80)
    crosses_midnight: bool = False
    active_weekdays: list[int] = Field(
        default_factory=lambda: DEFAULT_ACTIVE_WEEKDAYS.copy(),
        min_length=1,
        max_length=7,
    )
    active: bool = True
    requirements: list[ShiftRequirementCreateRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_shift_times_and_roles(self):
        if self.local_start_time == self.local_end_time:
            raise ValueError("local_start_time and local_end_time must differ")
        if len(set(self.active_weekdays)) != len(self.active_weekdays):
            raise ValueError("active_weekdays cannot contain duplicates")
        if any(day < 0 or day > 6 for day in self.active_weekdays):
            raise ValueError("active_weekdays values must be between 0 and 6")
        self.active_weekdays = sorted(self.active_weekdays)
        seen_role_ids: set[str] = set()
        for requirement in self.requirements:
            if requirement.role_id in seen_role_ids:
                raise ValueError("requirements cannot repeat role_id")
            seen_role_ids.add(requirement.role_id)
        return self


class ShiftRequirementResponse(BaseModel):
    id: str
    role_id: str
    role_name: str
    required_count: int
    unfilled_weight_override: int | None


class ShiftTypeResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    local_start_time: str
    local_end_time: str
    timezone: str
    crosses_midnight: bool
    active_weekdays: list[int]
    active: bool
    requirements: list[ShiftRequirementResponse]


@router.post(
    "/{organization_id}/shift-types",
    response_model=ShiftTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_shift_type(
    organization_id: str,
    request: ShiftTypeCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> ShiftTypeResponse:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    duplicate = db_session.execute(
        select(ShiftType).where(
            ShiftType.organization_id == organization_id,
            ShiftType.name == request.name,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SHIFT_TYPE_DUPLICATE",
                "message": "Shift type name already exists in the organization.",
                "field": "name",
            },
        )

    role_ids = [requirement.role_id for requirement in request.requirements]
    roles = list(
        db_session.execute(
            select(Role).where(
                Role.organization_id == organization_id,
                Role.id.in_(role_ids),
            )
        ).scalars()
    )
    role_by_id = {role.id: role for role in roles}
    if set(role_by_id) != set(role_ids):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_ROLE_ID",
                "message": "All requirement role_id values must belong to the organization.",
                "field": "requirements.role_id",
            },
        )

    shift_type = ShiftType(
        id=_new_id("shift_type"),
        organization_id=organization_id,
        name=request.name,
        local_start_time=request.local_start_time,
        local_end_time=request.local_end_time,
        timezone=request.timezone,
        crosses_midnight=request.crosses_midnight,
        active_weekdays=_serialize_active_weekdays(request.active_weekdays),
        active=request.active,
    )
    db_session.add(shift_type)
    db_session.flush()

    requirements = [
        ShiftRequirement(
            id=_new_id("shift_requirement"),
            organization_id=organization_id,
            shift_type_id=shift_type.id,
            role_id=requirement.role_id,
            required_count=requirement.required_count,
            unfilled_weight_override=requirement.unfilled_weight_override,
        )
        for requirement in request.requirements
    ]
    db_session.add_all(requirements)
    db_session.commit()

    return _shift_type_response(shift_type, requirements, role_by_id)


@router.get(
    "/{organization_id}/shift-types",
    response_model=list[ShiftTypeResponse],
)
def list_shift_types(
    organization_id: str,
    db_session: Session = Depends(get_db_session),
) -> list[ShiftTypeResponse]:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    shift_types = list(
        db_session.execute(
            select(ShiftType)
            .where(ShiftType.organization_id == organization_id)
            .order_by(ShiftType.name)
        ).scalars()
    )
    if not shift_types:
        return []

    shift_type_ids = [shift_type.id for shift_type in shift_types]
    requirements = list(
        db_session.execute(
            select(ShiftRequirement).where(
                ShiftRequirement.organization_id == organization_id,
                ShiftRequirement.shift_type_id.in_(shift_type_ids),
            )
        ).scalars()
    )
    role_ids = {requirement.role_id for requirement in requirements}
    roles = list(
        db_session.execute(
            select(Role).where(
                Role.organization_id == organization_id,
                Role.id.in_(role_ids),
            )
        ).scalars()
    )
    role_by_id = {role.id: role for role in roles}
    requirements_by_shift_type: dict[str, list[ShiftRequirement]] = {
        shift_type.id: [] for shift_type in shift_types
    }
    for requirement in requirements:
        requirements_by_shift_type[requirement.shift_type_id].append(requirement)

    return [
        _shift_type_response(
            shift_type,
            sorted(
                requirements_by_shift_type[shift_type.id],
                key=lambda requirement: role_by_id[requirement.role_id].name,
            ),
            role_by_id,
        )
        for shift_type in shift_types
    ]


def _shift_type_response(
    shift_type: ShiftType,
    requirements: list[ShiftRequirement],
    role_by_id: dict[str, Role],
) -> ShiftTypeResponse:
    return ShiftTypeResponse(
        id=shift_type.id,
        organization_id=shift_type.organization_id,
        name=shift_type.name,
        local_start_time=shift_type.local_start_time,
        local_end_time=shift_type.local_end_time,
        timezone=shift_type.timezone,
        crosses_midnight=shift_type.crosses_midnight,
        active_weekdays=_parse_active_weekdays(shift_type.active_weekdays),
        active=shift_type.active,
        requirements=[
            ShiftRequirementResponse(
                id=requirement.id,
                role_id=requirement.role_id,
                role_name=role_by_id[requirement.role_id].name,
                required_count=requirement.required_count,
                unfilled_weight_override=requirement.unfilled_weight_override,
            )
            for requirement in requirements
        ],
    )


def _serialize_active_weekdays(weekdays: list[int]) -> str:
    return ",".join(str(day) for day in sorted(weekdays))


def _parse_active_weekdays(raw_weekdays: str | None) -> list[int]:
    if not raw_weekdays:
        return DEFAULT_ACTIVE_WEEKDAYS.copy()
    parsed: list[int] = []
    for value in raw_weekdays.split(","):
        try:
            day = int(value)
        except ValueError:
            continue
        if 0 <= day <= 6 and day not in parsed:
            parsed.append(day)
    return sorted(parsed) or DEFAULT_ACTIVE_WEEKDAYS.copy()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

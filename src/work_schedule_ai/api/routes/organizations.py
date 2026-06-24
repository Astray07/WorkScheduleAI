from uuid import uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session, set_tenant_context
from work_schedule_ai.db.models import Organization, Role


router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(min_length=1, max_length=80)


class RoleResponse(BaseModel):
    id: str
    name: str


class OrganizationResponse(BaseModel):
    id: str
    name: str
    timezone: str
    data_version: int
    default_roles: list[RoleResponse]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    request: OrganizationCreateRequest,
    db_session: Session = Depends(get_db_session),
) -> OrganizationResponse:
    organization = Organization(
        id=_new_id("org"),
        name=request.name,
        timezone=request.timezone,
    )
    db_session.add(organization)
    db_session.flush()
    set_tenant_context(db_session, organization.id)

    default_roles = [
        Role(id=_new_id("role"), organization_id=organization.id, name="사수"),
        Role(id=_new_id("role"), organization_id=organization.id, name="부사수"),
    ]
    db_session.add_all(default_roles)
    db_session.commit()
    db_session.refresh(organization)

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        timezone=organization.timezone,
        data_version=organization.data_version,
        default_roles=[
            RoleResponse(id=role.id, name=role.name) for role in default_roles
        ],
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

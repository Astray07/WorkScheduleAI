from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.security import ADMIN_ROLES, READ_ROLES, require_roles
from work_schedule_ai.db.models import DemandDriver, LaborBudget, Organization


router = APIRouter(prefix="/organizations", tags=["demand-cost"])


class DemandDriverRequest(BaseModel):
    local_date: date
    segment: str = Field(min_length=1, max_length=80)
    demand_count: int = Field(ge=0)
    required_staff_count: int = Field(ge=0)
    source: str = Field(min_length=1, max_length=80)


class DemandDriverResponse(DemandDriverRequest):
    id: str
    organization_id: str


class LaborBudgetRequest(BaseModel):
    period_start: date
    period_end: date
    budget_amount_cents: int = Field(ge=0)
    currency: str = Field(min_length=1, max_length=12)


class LaborBudgetResponse(LaborBudgetRequest):
    id: str
    organization_id: str


class DemandCostPreviewResponse(BaseModel):
    organization_id: str
    period_start: date
    period_end: date
    required_staff_count: int
    planned_staff_count: int
    staffing_variance_count: int
    staffing_status: str
    under_staffed_count: int
    over_staffed_count: int
    planned_cost_cents: int
    budget_amount_cents: int | None
    budget_variance_cents: int | None
    budget_status: str


@router.post(
    "/{organization_id}/demand-drivers",
    response_model=DemandDriverResponse,
    status_code=201,
)
def create_demand_driver(
    organization_id: str,
    request: DemandDriverRequest,
    db_session: Session = Depends(get_db_session),
) -> DemandDriverResponse:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    driver = DemandDriver(
        id=_new_id("demand"),
        organization_id=organization_id,
        local_date=request.local_date,
        segment=request.segment,
        demand_count=request.demand_count,
        required_staff_count=request.required_staff_count,
        source=request.source,
    )
    db_session.add(driver)
    db_session.commit()
    return _demand_response(driver)


@router.post(
    "/{organization_id}/labor-budgets",
    response_model=LaborBudgetResponse,
    status_code=201,
)
def create_labor_budget(
    organization_id: str,
    request: LaborBudgetRequest,
    db_session: Session = Depends(get_db_session),
) -> LaborBudgetResponse:
    require_roles(db_session, ADMIN_ROLES)
    _get_organization_or_404(organization_id, db_session)
    if request.period_end < request.period_start:
        raise HTTPException(status_code=422, detail="period_end must be on or after period_start")
    budget = LaborBudget(
        id=_new_id("budget"),
        organization_id=organization_id,
        period_start=request.period_start,
        period_end=request.period_end,
        budget_amount_cents=request.budget_amount_cents,
        currency=request.currency,
    )
    db_session.add(budget)
    db_session.commit()
    return _budget_response(budget)


@router.get(
    "/{organization_id}/demand-cost-preview",
    response_model=DemandCostPreviewResponse,
)
def get_demand_cost_preview(
    organization_id: str,
    period_start: date,
    period_end: date,
    planned_staff_count: int = Query(default=0, ge=0),
    hourly_rate_cents: int = Query(default=0, ge=0),
    hours_per_shift: int = Query(default=8, ge=0),
    db_session: Session = Depends(get_db_session),
) -> DemandCostPreviewResponse:
    require_roles(db_session, READ_ROLES)
    _get_organization_or_404(organization_id, db_session)
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="period_end must be on or after period_start")
    drivers = list(
        db_session.execute(
            select(DemandDriver).where(
                DemandDriver.organization_id == organization_id,
                DemandDriver.local_date >= period_start,
                DemandDriver.local_date <= period_end,
            )
        ).scalars()
    )
    required_staff_count = sum(driver.required_staff_count for driver in drivers)
    staffing_variance = planned_staff_count - required_staff_count
    planned_cost_cents = planned_staff_count * hourly_rate_cents * hours_per_shift
    budget = db_session.execute(
        select(LaborBudget)
        .where(
            LaborBudget.organization_id == organization_id,
            LaborBudget.period_start <= period_end,
            LaborBudget.period_end >= period_start,
        )
        .order_by(LaborBudget.created_at.desc(), LaborBudget.id.desc())
    ).scalars().first()
    budget_amount = budget.budget_amount_cents if budget is not None else None
    budget_variance = (
        budget_amount - planned_cost_cents if budget_amount is not None else None
    )
    return DemandCostPreviewResponse(
        organization_id=organization_id,
        period_start=period_start,
        period_end=period_end,
        required_staff_count=required_staff_count,
        planned_staff_count=planned_staff_count,
        staffing_variance_count=staffing_variance,
        staffing_status=_staffing_status(staffing_variance),
        under_staffed_count=max(required_staff_count - planned_staff_count, 0),
        over_staffed_count=max(planned_staff_count - required_staff_count, 0),
        planned_cost_cents=planned_cost_cents,
        budget_amount_cents=budget_amount,
        budget_variance_cents=budget_variance,
        budget_status=(
            "no_budget"
            if budget_amount is None
            else "over_budget"
            if planned_cost_cents > budget_amount
            else "within_budget"
        ),
    )


def _staffing_status(staffing_variance: int) -> str:
    if staffing_variance < 0:
        return "under_staffed"
    if staffing_variance > 0:
        return "over_staffed"
    return "matched"


def _get_organization_or_404(
    organization_id: str,
    db_session: Session,
) -> Organization:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _demand_response(driver: DemandDriver) -> DemandDriverResponse:
    return DemandDriverResponse(
        id=driver.id,
        organization_id=driver.organization_id,
        local_date=driver.local_date,
        segment=driver.segment,
        demand_count=driver.demand_count,
        required_staff_count=driver.required_staff_count,
        source=driver.source,
    )


def _budget_response(budget: LaborBudget) -> LaborBudgetResponse:
    return LaborBudgetResponse(
        id=budget.id,
        organization_id=budget.organization_id,
        period_start=budget.period_start,
        period_end=budget.period_end,
        budget_amount_cents=budget.budget_amount_cents,
        currency=budget.currency,
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

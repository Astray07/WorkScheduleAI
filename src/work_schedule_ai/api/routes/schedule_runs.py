from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import (
    Employee,
    Organization,
    OverrideApproval,
    Role,
    ScheduleRecalculationRequest,
    ScheduleInputSnapshot,
    ScheduleRun,
    utc_now,
)


router = APIRouter(prefix="/organizations", tags=["schedule-runs"])

LLM_FALLBACK = {
    "status": "fallback",
    "text": "서버 템플릿으로 mock 근무표 설명을 생성했습니다.",
    "source": "server_template",
}


class ScheduleRunCreateRequest(BaseModel):
    period_start: date
    period_end: date
    template: Literal[
        "one_shift_per_day",
        "morning_afternoon_night",
        "on_call",
        "custom",
    ] = "one_shift_per_day"
    deterministic_mode: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=120)

    @model_validator(mode="after")
    def validate_period_length(self):
        day_count = (self.period_end - self.period_start).days + 1
        if day_count < 1:
            raise ValueError("period_end must be on or after period_start")
        if day_count > 31:
            raise ValueError("ScheduleRun period cannot exceed 31 days")
        return self


class ApproveRelaxationProposalRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    notification_required: bool


class OverrideApprovalResponse(BaseModel):
    id: str
    schedule_run_id: str
    relaxation_proposal_id: str
    type: str
    notification_required: bool
    created_at: datetime


class RecalculateScheduleRunRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ScheduleRunProgress(BaseModel):
    phase: str
    message: str
    started_at: datetime | None
    timeout_seconds: int


class ScoreSummary(BaseModel):
    hard: int
    approvable: int
    soft: int
    severity_label: str


class LLMExplanation(BaseModel):
    status: str
    text: str | None
    source: str


class ImpactPreview(BaseModel):
    resolved_issue_ids: list[str]
    new_warning_count: int


class ScheduleIssueResponse(BaseModel):
    id: str
    slot_id: str | None
    role_id: str | None
    type: str
    missing_count: int
    severity: str
    reason_code: str
    display_message: str
    attempt_no: int
    related_proposal_ids: list[str] = Field(default_factory=list)


class RelaxationProposalResponse(BaseModel):
    id: str
    group_id: str | None
    requires_proposal_ids: list[str]
    type: str
    severity: str
    affected_slot_id: str | None
    display_summary: str
    impact_preview: ImpactPreview
    status: str
    attempt_no: int
    llm_explanation: LLMExplanation


class ScheduleRunResponse(BaseModel):
    id: str
    organization_id: str
    period_start: date
    period_end: date
    status: str
    solver_status: str | None
    solution_quality: str
    current_attempt_no: int
    recalculation_count: int
    input_snapshot_hash: str | None
    progress: ScheduleRunProgress
    score_summary: ScoreSummary
    issues: list[ScheduleIssueResponse]
    proposals: list[RelaxationProposalResponse]
    llm_explanation: LLMExplanation
    updated_at: datetime


class ShiftSlotResponse(BaseModel):
    id: str
    local_date: date
    label: str
    starts_at: str
    ends_at: str


class ShiftRequirementResponse(BaseModel):
    id: str
    slot_id: str
    role_id: str
    role_name: str
    required_count: int


class AssignmentResponse(BaseModel):
    id: str
    slot_id: str
    role_id: str
    employee_id: str
    employee_name: str
    source: str
    locked_by_user: bool
    warning_state: str
    warning_message: str | None = None
    attempt_no: int


class ScheduleRunResultResponse(BaseModel):
    schedule_run_id: str
    status: str
    solution_quality: str
    current_attempt_no: int
    recalculation_count: int
    read_only: bool
    publication: None
    slots: list[ShiftSlotResponse]
    requirements: list[ShiftRequirementResponse]
    assignments: list[AssignmentResponse]
    issues: list[ScheduleIssueResponse]
    proposals: list[RelaxationProposalResponse]
    score_summary: ScoreSummary
    llm_explanation: LLMExplanation


@router.post(
    "/{organization_id}/schedule-runs",
    response_model=ScheduleRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_schedule_run(
    organization_id: str,
    request: ScheduleRunCreateRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    organization = db_session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if idempotency_key is not None:
        existing_run = db_session.execute(
            select(ScheduleRun).where(
                ScheduleRun.organization_id == organization_id,
                ScheduleRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_run is not None:
            return _schedule_run_response(existing_run, db_session)

    run_id = _new_id("run")
    snapshot_payload = _build_snapshot_payload(
        organization_id=organization_id,
        request=request,
        db_session=db_session,
    )
    snapshot_hash = _snapshot_hash(snapshot_payload)
    now = utc_now()
    run = ScheduleRun(
        id=run_id,
        organization_id=organization_id,
        period_start=request.period_start,
        period_end=request.period_end,
        template=request.template,
        deterministic_mode=request.deterministic_mode,
        timeout_seconds=request.timeout_seconds,
        status="succeeded",
        solver_status="not_started",
        solution_quality="feasible_not_proven_optimal",
        current_attempt_no=1,
        recalculation_count=0,
        input_snapshot_hash=snapshot_hash,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=now,
    )
    snapshot = ScheduleInputSnapshot(
        id=_new_id("snapshot"),
        organization_id=organization_id,
        schedule_run_id=run_id,
        snapshot_hash=snapshot_hash,
        payload_json=json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True),
    )
    db_session.add_all([run, snapshot])
    db_session.commit()

    return _schedule_run_response(run, db_session)


@router.get(
    "/{organization_id}/schedule-runs/{schedule_run_id}",
    response_model=ScheduleRunResponse,
)
def get_schedule_run(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    return _schedule_run_response(run, db_session)


@router.get(
    "/{organization_id}/schedule-runs/{schedule_run_id}/result",
    response_model=ScheduleRunResultResponse,
)
def get_schedule_run_result(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResultResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    artifacts = _mock_result_artifacts(run, db_session)
    return ScheduleRunResultResponse(
        schedule_run_id=run.id,
        status=run.status,
        solution_quality=run.solution_quality,
        current_attempt_no=run.current_attempt_no,
        recalculation_count=run.recalculation_count,
        read_only=False,
        publication=None,
        slots=artifacts.slots,
        requirements=artifacts.requirements,
        assignments=artifacts.assignments,
        issues=artifacts.issues,
        proposals=artifacts.proposals,
        score_summary=artifacts.score_summary,
        llm_explanation=_llm_explanation(),
    )


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve",
    response_model=OverrideApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def approve_relaxation_proposal(
    organization_id: str,
    schedule_run_id: str,
    proposal_id: str,
    request: ApproveRelaxationProposalRequest,
    db_session: Session = Depends(get_db_session),
) -> OverrideApprovalResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)
    artifacts = _mock_result_artifacts(run, db_session)
    proposal = next(
        (candidate for candidate in artifacts.proposals if candidate.id == proposal_id),
        None,
    )
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RelaxationProposal not found",
        )

    existing_approval = db_session.execute(
        select(OverrideApproval).where(
            OverrideApproval.organization_id == organization_id,
            OverrideApproval.schedule_run_id == schedule_run_id,
            OverrideApproval.relaxation_proposal_id == proposal_id,
        )
    ).scalar_one_or_none()
    if existing_approval is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RELAXATION_PROPOSAL_ALREADY_APPROVED",
                "message": "Relaxation proposal is already approved.",
                "field": "proposal_id",
            },
        )

    approval = OverrideApproval(
        id=_new_id("override"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        relaxation_proposal_id=proposal_id,
        type=proposal.type,
        notification_required=request.notification_required,
        reason=request.reason,
        created_at=utc_now(),
    )
    db_session.add(approval)
    db_session.commit()

    return OverrideApprovalResponse(
        id=approval.id,
        schedule_run_id=approval.schedule_run_id,
        relaxation_proposal_id=approval.relaxation_proposal_id,
        type=approval.type,
        notification_required=approval.notification_required,
        created_at=approval.created_at,
    )


@router.post(
    "/{organization_id}/schedule-runs/{schedule_run_id}/recalculate",
    response_model=ScheduleRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def recalculate_schedule_run(
    organization_id: str,
    schedule_run_id: str,
    request: RecalculateScheduleRunRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    db_session: Session = Depends(get_db_session),
) -> ScheduleRunResponse:
    run = _get_schedule_run_or_404(organization_id, schedule_run_id, db_session)

    if idempotency_key is not None:
        existing_request = db_session.execute(
            select(ScheduleRecalculationRequest).where(
                ScheduleRecalculationRequest.organization_id == organization_id,
                ScheduleRecalculationRequest.schedule_run_id == schedule_run_id,
                ScheduleRecalculationRequest.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_request is not None:
            return _schedule_run_response(run, db_session)

    approved_override_count = db_session.execute(
        select(OverrideApproval.id).where(
            OverrideApproval.organization_id == organization_id,
            OverrideApproval.schedule_run_id == schedule_run_id,
        )
    ).first()
    if approved_override_count is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NO_APPROVED_OVERRIDE",
                "message": "At least one approved override is required to recalculate.",
                "field": "schedule_run_id",
            },
        )

    if run.recalculation_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RECALCULATION_LIMIT_EXCEEDED",
                "message": "recalculation_count cannot exceed 3.",
                "field": "recalculation_count",
            },
        )

    run.recalculation_count += 1
    run.updated_at = utc_now()
    run.status = "succeeded"
    run.solver_status = "not_started"
    run.solution_quality = "feasible_not_proven_optimal"
    recalculation_request = ScheduleRecalculationRequest(
        id=_new_id("recalc"),
        organization_id=organization_id,
        schedule_run_id=schedule_run_id,
        idempotency_key=idempotency_key,
        reason=request.reason,
        recalculation_count=run.recalculation_count,
    )
    db_session.add(recalculation_request)
    db_session.commit()

    return _schedule_run_response(run, db_session)


class _MockArtifacts(BaseModel):
    slots: list[ShiftSlotResponse]
    requirements: list[ShiftRequirementResponse]
    assignments: list[AssignmentResponse]
    issues: list[ScheduleIssueResponse]
    proposals: list[RelaxationProposalResponse]
    score_summary: ScoreSummary


def _get_schedule_run_or_404(
    organization_id: str,
    schedule_run_id: str,
    db_session: Session,
) -> ScheduleRun:
    run = db_session.execute(
        select(ScheduleRun).where(
            ScheduleRun.organization_id == organization_id,
            ScheduleRun.id == schedule_run_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ScheduleRun not found",
        )
    return run


def _schedule_run_response(
    run: ScheduleRun,
    db_session: Session,
) -> ScheduleRunResponse:
    artifacts = _mock_result_artifacts(run, db_session)
    return ScheduleRunResponse(
        id=run.id,
        organization_id=run.organization_id,
        period_start=run.period_start,
        period_end=run.period_end,
        status=run.status,
        solver_status=run.solver_status,
        solution_quality=run.solution_quality,
        current_attempt_no=run.current_attempt_no,
        recalculation_count=run.recalculation_count,
        input_snapshot_hash=run.input_snapshot_hash,
        progress=ScheduleRunProgress(
            phase="completed",
            message="Mock schedule result is ready.",
            started_at=run.started_at,
            timeout_seconds=run.timeout_seconds,
        ),
        score_summary=artifacts.score_summary,
        issues=artifacts.issues,
        proposals=artifacts.proposals,
        llm_explanation=_llm_explanation(),
        updated_at=run.updated_at,
    )


def _mock_result_artifacts(
    run: ScheduleRun,
    db_session: Session,
) -> _MockArtifacts:
    roles = list(
        db_session.execute(
            select(Role).where(Role.organization_id == run.organization_id)
        ).scalars()
    )
    roles.sort(key=lambda role: ({"사수": 0, "부사수": 1}.get(role.name, 100), role.name))
    employees = list(
        db_session.execute(
            select(Employee).where(
                Employee.organization_id == run.organization_id,
                Employee.active.is_(True),
            )
        ).scalars()
    )
    employees.sort(key=lambda employee: employee.employee_code)

    slots = _mock_slots(run)
    requirements: list[ShiftRequirementResponse] = []
    assignments: list[AssignmentResponse] = []
    assignment_no = 1
    should_resolve_unfilled = _should_resolve_mock_unfilled(run, db_session)
    skipped_unfilled = False
    for slot in slots:
        for role in roles:
            requirement = ShiftRequirementResponse(
                id=f"req_{slot.id}_{role.id}",
                slot_id=slot.id,
                role_id=role.id,
                role_name=role.name,
                required_count=1,
            )
            requirements.append(requirement)
            if role.name == "부사수" and not skipped_unfilled and not should_resolve_unfilled:
                skipped_unfilled = True
                continue
            if not employees:
                continue
            employee = employees[(assignment_no - 1) % len(employees)]
            assignments.append(
                AssignmentResponse(
                    id=f"assign_mock_{assignment_no}",
                    slot_id=slot.id,
                    role_id=role.id,
                    employee_id=employee.id,
                    employee_name=employee.name,
                    source="solver",
                    locked_by_user=False,
                    warning_state="none",
                    warning_message=None,
                    attempt_no=run.current_attempt_no,
                )
            )
            assignment_no += 1

    issues = _mock_issues(run, roles, slots, skipped_unfilled)
    approved_proposal_ids = set(
        db_session.execute(
            select(OverrideApproval.relaxation_proposal_id).where(
                OverrideApproval.organization_id == run.organization_id,
                OverrideApproval.schedule_run_id == run.id,
            )
        ).scalars()
    )
    proposals = _mock_proposals(run, issues, approved_proposal_ids)
    score_summary = ScoreSummary(
        hard=0,
        approvable=0,
        soft=100 if issues else 0,
        severity_label="high" if issues else "none",
    )
    return _MockArtifacts(
        slots=slots,
        requirements=requirements,
        assignments=assignments,
        issues=issues,
        proposals=proposals,
        score_summary=score_summary,
    )


def _should_resolve_mock_unfilled(
    run: ScheduleRun,
    db_session: Session,
) -> bool:
    if run.recalculation_count <= 0:
        return False
    approved_override = db_session.execute(
        select(OverrideApproval.id).where(
            OverrideApproval.organization_id == run.organization_id,
            OverrideApproval.schedule_run_id == run.id,
        )
    ).first()
    return approved_override is not None


def _mock_slots(run: ScheduleRun) -> list[ShiftSlotResponse]:
    slots: list[ShiftSlotResponse] = []
    current_date = run.period_start
    while current_date <= run.period_end:
        date_token = current_date.isoformat().replace("-", "_")
        slots.append(
            ShiftSlotResponse(
                id=f"slot_{date_token}_day",
                local_date=current_date,
                label="주간 근무",
                starts_at=f"{current_date.isoformat()}T09:00:00+09:00",
                ends_at=f"{current_date.isoformat()}T18:00:00+09:00",
            )
        )
        current_date += timedelta(days=1)
    return slots


def _mock_issues(
    run: ScheduleRun,
    roles: list[Role],
    slots: list[ShiftSlotResponse],
    skipped_unfilled: bool,
) -> list[ScheduleIssueResponse]:
    junior_role = next((role for role in roles if role.name == "부사수"), None)
    if junior_role is None or not slots or not skipped_unfilled:
        return []
    return [
        ScheduleIssueResponse(
            id="issue_mock_unfilled_1",
            slot_id=slots[0].id,
            role_id=junior_role.id,
            type="unfilled_requirement",
            missing_count=1,
            severity="high",
            reason_code="NO_AVAILABLE_CANDIDATE",
            display_message="부사수 1명이 미배정입니다.",
            attempt_no=run.current_attempt_no,
            related_proposal_ids=["proposal_mock_time_off_1"],
        )
    ]


def _mock_proposals(
    run: ScheduleRun,
    issues: list[ScheduleIssueResponse],
    approved_proposal_ids: set[str],
) -> list[RelaxationProposalResponse]:
    if not issues:
        return []
    proposal_id = "proposal_mock_time_off_1"
    return [
        RelaxationProposalResponse(
            id=proposal_id,
            group_id=None,
            requires_proposal_ids=[],
            type="approve_time_off_override",
            severity="high",
            affected_slot_id=issues[0].slot_id,
            display_summary="휴가 중인 후보 1명을 예외 승인하면 미배정을 해소할 수 있습니다.",
            impact_preview=ImpactPreview(
                resolved_issue_ids=[issues[0].id],
                new_warning_count=1,
            ),
            status="approved" if proposal_id in approved_proposal_ids else "suggested",
            attempt_no=run.current_attempt_no,
            llm_explanation=_llm_explanation(),
        )
    ]


def _build_snapshot_payload(
    *,
    organization_id: str,
    request: ScheduleRunCreateRequest,
    db_session: Session,
) -> dict[str, object]:
    employee_ids = db_session.execute(
        select(Employee.id).where(Employee.organization_id == organization_id)
    ).scalars()
    role_ids = db_session.execute(
        select(Role.id).where(Role.organization_id == organization_id)
    ).scalars()
    return {
        "organization_id": organization_id,
        "period_start": request.period_start.isoformat(),
        "period_end": request.period_end.isoformat(),
        "template": request.template,
        "deterministic_mode": request.deterministic_mode,
        "timeout_seconds": request.timeout_seconds,
        "employee_ids": sorted(employee_ids),
        "role_ids": sorted(role_ids),
    }


def _snapshot_hash(snapshot_payload: dict[str, object]) -> str:
    encoded = json.dumps(
        snapshot_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _llm_explanation() -> LLMExplanation:
    return LLMExplanation(**LLM_FALLBACK)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

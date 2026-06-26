from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pydantic import BaseModel


LEGAL_DISCLAIMER = (
    "이 결과는 법률 자동 판단이 아니라 운영 검토를 돕는 경고입니다. "
    "최종 판단은 조직 정책과 최신 법령 검토를 기준으로 해야 합니다."
)


class ComplianceAssignment(BaseModel):
    employee_id: str
    employee_name: str
    slot_id: str
    local_date: str
    label: str
    starts_at: str
    ends_at: str


class ComplianceWarning(BaseModel):
    code: str
    severity: str
    publish_blocking: bool
    employee_id: str | None
    employee_name: str | None
    slot_id: str | None
    message: str
    hours: float | None = None


def evaluate_compliance_warnings(
    assignments: list[ComplianceAssignment],
    *,
    min_rest_hours: int = 11,
) -> list[ComplianceWarning]:
    warnings: list[ComplianceWarning] = []
    warnings.extend(_weekly_hours_warnings(assignments))
    warnings.extend(_minimum_rest_warnings(assignments, min_rest_hours))
    warnings.extend(_night_and_weekend_warnings(assignments))
    return warnings


def _weekly_hours_warnings(
    assignments: list[ComplianceAssignment],
) -> list[ComplianceWarning]:
    hours_by_employee_week: dict[tuple[str, str, int], float] = defaultdict(float)
    names: dict[str, str] = {}
    for assignment in assignments:
        start = _parse_datetime(assignment.starts_at)
        end = _parse_datetime(assignment.ends_at)
        week_key = start.isocalendar()
        hours_by_employee_week[
            (assignment.employee_id, str(week_key.year), week_key.week)
        ] += (end - start).total_seconds() / 3600
        names[assignment.employee_id] = assignment.employee_name
    warnings = []
    for (employee_id, _year, _week), hours in hours_by_employee_week.items():
        if hours > 52:
            warnings.append(
                ComplianceWarning(
                    code="WEEKLY_HOURS_OVER_52",
                    severity="blocking",
                    publish_blocking=True,
                    employee_id=employee_id,
                    employee_name=names.get(employee_id),
                    slot_id=None,
                    message="주간 예정 근무 시간이 52시간을 초과합니다.",
                    hours=round(hours, 2),
                )
            )
    return warnings


def _minimum_rest_warnings(
    assignments: list[ComplianceAssignment],
    min_rest_hours: int,
) -> list[ComplianceWarning]:
    by_employee: dict[str, list[ComplianceAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_employee[assignment.employee_id].append(assignment)
    warnings = []
    for employee_id, employee_assignments in by_employee.items():
        sorted_assignments = sorted(
            employee_assignments,
            key=lambda item: _parse_datetime(item.starts_at),
        )
        for previous, current in zip(sorted_assignments, sorted_assignments[1:]):
            rest_hours = (
                _parse_datetime(current.starts_at) - _parse_datetime(previous.ends_at)
            ).total_seconds() / 3600
            if rest_hours < min_rest_hours:
                warnings.append(
                    ComplianceWarning(
                        code="MIN_REST_UNDER_POLICY",
                        severity="warning",
                        publish_blocking=False,
                        employee_id=employee_id,
                        employee_name=current.employee_name,
                        slot_id=current.slot_id,
                        message="정책상 최소 휴식 시간보다 짧은 간격이 있습니다.",
                        hours=round(rest_hours, 2),
                    )
                )
    return warnings


def _night_and_weekend_warnings(
    assignments: list[ComplianceAssignment],
) -> list[ComplianceWarning]:
    warnings = []
    for assignment in assignments:
        start = _parse_datetime(assignment.starts_at)
        if "야간" in assignment.label or start.hour >= 22 or start.hour < 6:
            warnings.append(
                ComplianceWarning(
                    code="NIGHT_WORK_REVIEW",
                    severity="info",
                    publish_blocking=False,
                    employee_id=assignment.employee_id,
                    employee_name=assignment.employee_name,
                    slot_id=assignment.slot_id,
                    message="야간 근무 수당/휴식 검토가 필요한 슬롯입니다.",
                )
            )
        if start.weekday() >= 5:
            warnings.append(
                ComplianceWarning(
                    code="WEEKEND_OR_HOLIDAY_REVIEW",
                    severity="info",
                    publish_blocking=False,
                    employee_id=assignment.employee_id,
                    employee_name=assignment.employee_name,
                    slot_id=assignment.slot_id,
                    message="휴일 또는 주말 근무 검토가 필요한 슬롯입니다.",
                )
            )
    return warnings


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

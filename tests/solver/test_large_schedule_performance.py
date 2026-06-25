import os
from collections import defaultdict
from datetime import date, datetime
from time import perf_counter

import pytest

from work_schedule_ai.solver.large_cases import (
    make_high_constraint_large_schedule_request,
    make_large_schedule_request,
)
from work_schedule_ai.solver.ortools_solver import solve_schedule


def test_solver_handles_100_employees_31_days_with_stable_runtime():
    request = make_large_schedule_request(employee_count=100, day_count=31)

    started_at = perf_counter()
    result = solve_schedule(request)
    elapsed_seconds = perf_counter() - started_at

    assert result.status == "succeeded"
    assert result.issues == []
    assert len(result.assignments) == 62
    assert elapsed_seconds < 10


def test_solver_handles_50_employees_31_days_general_regression():
    request = make_large_schedule_request(employee_count=50, day_count=31)

    result = solve_schedule(request)

    assert result.status == "succeeded"
    assert result.issues == []
    assert len(result.assignments) == 62


def test_high_constraint_large_schedule_request_defines_constraints():
    request = make_high_constraint_large_schedule_request(employee_count=100, day_count=31)

    assert len(request.employees) == 100
    assert len(request.slots) == 31
    assert len(request.requirements) == 62
    assert request.blocked_pairs
    assert request.avoid_pairs
    assert request.global_max_shifts_per_week == 3
    assert request.max_consecutive_shifts == 2
    assert request.min_rest_hours == 11
    assert request.weekend_shift_limit_per_month == 1
    assert request.night_shift_limit_per_month == 2
    assert any(employee.unavailable_slot_ids for employee in request.employees)
    assert any(slot.is_weekend for slot in request.slots)
    assert any(slot.is_night for slot in request.slots)
    assert all(slot.starts_at and slot.ends_at for slot in request.slots)


@pytest.mark.skipif(
    os.environ.get("RUN_SOLVER_HARDENING_BENCHMARK") != "1",
    reason="set RUN_SOLVER_HARDENING_BENCHMARK=1 to run solver hardening benchmark",
)
def test_solver_handles_high_constraint_100_employees_31_days_with_diagnostics():
    request = make_high_constraint_large_schedule_request(employee_count=100, day_count=31)

    started_at = perf_counter()
    result = solve_schedule(request)
    elapsed_seconds = perf_counter() - started_at

    print(
        "HIGH_CONSTRAINT_BENCHMARK "
        f"elapsed_seconds={elapsed_seconds:.3f} "
        f"status={result.status} "
        f"solver_status={result.solver_status} "
        f"assignments={len(result.assignments)} "
        f"issues={len(result.issues)}"
    )
    assert result.status in {"succeeded", "infeasible"}
    assert result.status != "failed"
    assert elapsed_seconds < request.timeout_seconds + 5
    if result.status == "succeeded":
        _assert_expected_soft_unfilled_issue(result)
        _assert_result_respects_solver_constraints(request, result)


def _assert_expected_soft_unfilled_issue(result):
    assert result.issues == [
        {
            "requirement_id": "req_slot_2026-07-31_role_senior",
            "slot_id": "slot_2026-07-31",
            "role_id": "role_senior",
            "type": "unfilled_requirement",
            "missing_count": 2,
            "severity": "high",
        }
    ]


def _assert_result_respects_solver_constraints(request, result):
    employees_by_id = {employee.id: employee for employee in request.employees}
    slots_by_id = {slot.id: slot for slot in request.slots}
    requirements_by_id = {
        requirement.id: requirement
        for requirement in request.requirements
    }
    assigned_by_slot: dict[str, set[str]] = defaultdict(set)
    assigned_by_employee_week: dict[tuple[str, tuple[int, int]], int] = defaultdict(int)
    assigned_dates_by_employee: dict[str, set[date]] = defaultdict(set)
    assigned_weekend_by_employee_month: dict[tuple[str, str], int] = defaultdict(int)
    assigned_night_by_employee_month: dict[tuple[str, str], int] = defaultdict(int)
    assignment_count_by_requirement: dict[str, int] = defaultdict(int)
    slots_by_employee: dict[str, list[object]] = defaultdict(list)

    for assignment in result.assignments:
        employee = employees_by_id[assignment.employee_id]
        requirement = requirements_by_id[assignment.requirement_id]
        slot = slots_by_id[assignment.slot_id]
        assert requirement.role_id in employee.role_ids
        assert assignment.slot_id not in employee.unavailable_slot_ids
        assert assignment.role_id == requirement.role_id
        assigned_by_slot[assignment.slot_id].add(assignment.employee_id)
        assignment_count_by_requirement[assignment.requirement_id] += 1
        local_date = date.fromisoformat(slot.local_date)
        week_key = local_date.isocalendar()[:2]
        assigned_by_employee_week[(assignment.employee_id, week_key)] += 1
        assigned_dates_by_employee[assignment.employee_id].add(local_date)
        slots_by_employee[assignment.employee_id].append(slot)
        if slot.is_weekend:
            assigned_weekend_by_employee_month[
                (assignment.employee_id, slot.local_date[:7])
            ] += 1
        if slot.is_night:
            assigned_night_by_employee_month[
                (assignment.employee_id, slot.local_date[:7])
            ] += 1

    for requirement in request.requirements:
        assert assignment_count_by_requirement[requirement.id] <= requirement.required_count

    for blocked_pair in request.blocked_pairs:
        employee_a_id, employee_b_id = blocked_pair.normalized()
        for employee_ids in assigned_by_slot.values():
            assert not {employee_a_id, employee_b_id}.issubset(employee_ids)

    for (employee_id, _week_key), count in assigned_by_employee_week.items():
        employee = employees_by_id[employee_id]
        weekly_cap = employee.max_shifts_per_week or request.global_max_shifts_per_week
        if weekly_cap is not None:
            assert count <= weekly_cap

    for employee_id, assigned_dates in assigned_dates_by_employee.items():
        sorted_dates = sorted(assigned_dates)
        consecutive_count = 1
        for previous_date, current_date in zip(sorted_dates, sorted_dates[1:]):
            if (current_date - previous_date).days == 1:
                consecutive_count += 1
            else:
                consecutive_count = 1
            assert consecutive_count <= request.max_consecutive_shifts

    for count in assigned_weekend_by_employee_month.values():
        assert count <= request.weekend_shift_limit_per_month

    for count in assigned_night_by_employee_month.values():
        assert count <= request.night_shift_limit_per_month

    for employee_slots in slots_by_employee.values():
        for first_index, first_slot in enumerate(employee_slots):
            for second_slot in employee_slots[first_index + 1:]:
                first_start = datetime.fromisoformat(first_slot.starts_at)
                first_end = datetime.fromisoformat(first_slot.ends_at)
                second_start = datetime.fromisoformat(second_slot.starts_at)
                second_end = datetime.fromisoformat(second_slot.ends_at)
                if first_start <= second_start:
                    rest_hours = (second_start - first_end).total_seconds() / 3600
                else:
                    rest_hours = (first_start - second_end).total_seconds() / 3600
                assert rest_hours >= request.min_rest_hours

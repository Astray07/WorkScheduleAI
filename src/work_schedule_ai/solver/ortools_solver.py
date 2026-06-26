from __future__ import annotations

from collections import defaultdict
from datetime import date
from datetime import datetime

from ortools.sat.python import cp_model

from work_schedule_ai.solver.models import (
    EmployeeInput,
    ScheduleAssignment,
    ScheduleRequirementInput,
    SolveScheduleRequest,
    SolveScheduleResult,
)


ROTATION_TIE_BREAKER_WEIGHT = 1_000
FAIRNESS_OVER_TARGET_WEIGHT = 50_000
ADJACENT_DAY_REPEAT_WEIGHT = 20_000


def solve_schedule(request: SolveScheduleRequest) -> SolveScheduleResult:
    employees = sorted(request.employees, key=lambda employee: employee.id)
    slots = sorted(request.slots, key=lambda slot: (slot.local_date, slot.id))
    requirements = sorted(
        request.requirements,
        key=lambda requirement: (
            _slot_index(slots, requirement.slot_id),
            requirement.role_id,
            requirement.id,
        ),
    )
    employee_index = {employee.id: index for index, employee in enumerate(employees)}
    slot_index = {slot.id: index for index, slot in enumerate(slots)}
    local_date_by_slot_id = {
        slot.id: date.fromisoformat(slot.local_date)
        for slot in slots
    }
    week_key_by_slot_id = {slot.id: _week_key(slot.local_date) for slot in slots}
    role_ids = sorted({requirement.role_id for requirement in requirements})
    role_index = {role_id: index for index, role_id in enumerate(role_ids)}

    model = cp_model.CpModel()
    assignment_vars: dict[tuple[str, str], cp_model.IntVar] = {}
    vars_by_employee_slot: dict[tuple[str, str], list[cp_model.IntVar]] = defaultdict(list)
    vars_by_slot: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    vars_by_requirement: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    vars_by_employee_slot_for_pair: dict[tuple[str, str], list[cp_model.IntVar]] = (
        defaultdict(list)
    )
    vars_by_employee_week: dict[tuple[str, tuple[int, int]], list[cp_model.IntVar]] = (
        defaultdict(list)
    )
    vars_by_employee_date: dict[tuple[str, date], list[cp_model.IntVar]] = (
        defaultdict(list)
    )
    vars_by_employee_weekend_month: dict[tuple[str, str], list[cp_model.IntVar]] = (
        defaultdict(list)
    )
    vars_by_employee_night_month: dict[tuple[str, str], list[cp_model.IntVar]] = (
        defaultdict(list)
    )

    for requirement in requirements:
        for employee in employees:
            if requirement.role_id not in employee.role_ids:
                continue
            if requirement.slot_id in employee.unavailable_slot_ids:
                continue
            variable = model.NewBoolVar(
                f"assign_{requirement.id}_{employee.id}"
            )
            assignment_vars[(requirement.id, employee.id)] = variable
            vars_by_requirement[requirement.id].append(variable)
            vars_by_slot[requirement.slot_id].append(variable)
            vars_by_employee_slot[(employee.id, requirement.slot_id)].append(variable)
            vars_by_employee_slot_for_pair[(employee.id, requirement.slot_id)].append(
                variable
            )
            vars_by_employee_week[
                (employee.id, week_key_by_slot_id[requirement.slot_id])
            ].append(variable)
            vars_by_employee_date[
                (employee.id, local_date_by_slot_id[requirement.slot_id])
            ].append(variable)
            slot = next(slot for slot in slots if slot.id == requirement.slot_id)
            month_key = slot.local_date[:7]
            if slot.is_weekend:
                vars_by_employee_weekend_month[(employee.id, month_key)].append(variable)
            if slot.is_night:
                vars_by_employee_night_month[(employee.id, month_key)].append(variable)

    unfilled_vars: dict[str, cp_model.IntVar] = {}
    objective_terms: list[cp_model.LinearExpr] = []
    for requirement in requirements:
        unfilled = model.NewIntVar(
            0,
            requirement.required_count,
            f"unfilled_{requirement.id}",
        )
        unfilled_vars[requirement.id] = unfilled
        model.Add(
            sum(vars_by_requirement[requirement.id]) + unfilled
            == requirement.required_count
        )
        objective_terms.append(unfilled * requirement.unfilled_weight * 100_000)

    for staffing_target in request.staffing_targets:
        variables = vars_by_slot[staffing_target.slot_id]
        max_staff_count = sum(
            requirement.required_count
            for requirement in requirements
            if requirement.slot_id == staffing_target.slot_id
        )
        assigned_count = model.NewIntVar(
            0,
            max_staff_count,
            f"assigned_staff_count_{staffing_target.slot_id}",
        )
        model.Add(assigned_count == sum(variables))
        under_target = model.NewIntVar(
            0,
            max(staffing_target.target_staff_count, 0),
            f"under_staffing_target_{staffing_target.slot_id}",
        )
        over_target = model.NewIntVar(
            0,
            max(max_staff_count - staffing_target.target_staff_count, 0),
            f"over_staffing_target_{staffing_target.slot_id}",
        )
        model.Add(staffing_target.target_staff_count - assigned_count <= under_target)
        model.Add(assigned_count - staffing_target.target_staff_count <= over_target)
        objective_terms.append(
            under_target * max(staffing_target.under_staffing_penalty, 0)
        )
        objective_terms.append(
            over_target * max(staffing_target.over_staffing_penalty, 0)
        )

    for variables in vars_by_employee_slot.values():
        model.Add(sum(variables) <= 1)

    for blocked_pair in request.blocked_pairs:
        employee_a_id, employee_b_id = blocked_pair.normalized()
        for slot in slots:
            variables = (
                vars_by_employee_slot_for_pair[(employee_a_id, slot.id)]
                + vars_by_employee_slot_for_pair[(employee_b_id, slot.id)]
            )
            if variables:
                model.Add(sum(variables) <= 1)

    for avoid_pair in request.avoid_pairs:
        employee_a_id, employee_b_id = avoid_pair.normalized()
        for slot in slots:
            variables_a = vars_by_employee_slot_for_pair[(employee_a_id, slot.id)]
            variables_b = vars_by_employee_slot_for_pair[(employee_b_id, slot.id)]
            if not variables_a or not variables_b:
                continue
            assigned_a = model.NewBoolVar(f"avoid_a_{employee_a_id}_{slot.id}")
            assigned_b = model.NewBoolVar(f"avoid_b_{employee_b_id}_{slot.id}")
            violation = model.NewBoolVar(
                f"avoid_violation_{employee_a_id}_{employee_b_id}_{slot.id}"
            )
            model.Add(sum(variables_a) >= assigned_a)
            model.Add(sum(variables_a) <= len(variables_a) * assigned_a)
            model.Add(sum(variables_b) >= assigned_b)
            model.Add(sum(variables_b) <= len(variables_b) * assigned_b)
            model.Add(violation <= assigned_a)
            model.Add(violation <= assigned_b)
            model.Add(violation >= assigned_a + assigned_b - 1)
            objective_terms.append(violation * avoid_pair.weight)

    employee_by_id = {employee.id: employee for employee in employees}
    for (employee_id, _week_key_value), variables in vars_by_employee_week.items():
        employee = employee_by_id[employee_id]
        weekly_cap = (
            employee.max_shifts_per_week
            if employee.max_shifts_per_week is not None
            else request.global_max_shifts_per_week
        )
        if weekly_cap is None:
            continue
        model.Add(sum(variables) <= weekly_cap)

    if request.weekend_shift_limit_per_month is not None:
        for variables in vars_by_employee_weekend_month.values():
            model.Add(sum(variables) <= request.weekend_shift_limit_per_month)

    if request.night_shift_limit_per_month is not None:
        for variables in vars_by_employee_night_month.values():
            model.Add(sum(variables) <= request.night_shift_limit_per_month)

    for requirement in requirements:
        for employee in employees:
            variable = assignment_vars.get((requirement.id, employee.id))
            if variable is None:
                continue
            preferred_employee_index = (
                slot_index[requirement.slot_id] + role_index[requirement.role_id]
            ) % max(len(employees), 1)
            rotation_distance = (
                employee_index[employee.id] - preferred_employee_index
            ) % max(len(employees), 1)
            tie_breaker = (
                rotation_distance * ROTATION_TIE_BREAKER_WEIGHT
                + employee_index[employee.id]
            )
            objective_terms.append(variable * tie_breaker)

    fair_assignment_target = _fair_assignment_target(requirements, employees)
    for employee in employees:
        variables = [
            variable
            for (requirement_id, employee_id), variable in assignment_vars.items()
            if employee_id == employee.id
        ]
        if not variables:
            continue
        assignment_count = model.NewIntVar(
            0,
            len(variables),
            f"assignment_count_{employee.id}",
        )
        model.Add(assignment_count == sum(variables))
        over_target = model.NewIntVar(
            0,
            len(variables),
            f"assignment_over_target_{employee.id}",
        )
        model.Add(assignment_count - fair_assignment_target <= over_target)
        objective_terms.append(over_target * request.fairness_over_target_weight)

    assigned_by_employee_date: dict[tuple[str, date], cp_model.IntVar] = {}
    for (employee_id, local_date), variables in vars_by_employee_date.items():
        assigned_on_date = model.NewBoolVar(
            f"assigned_{employee_id}_{local_date.isoformat()}"
        )
        model.Add(sum(variables) >= assigned_on_date)
        model.Add(sum(variables) <= len(variables) * assigned_on_date)
        assigned_by_employee_date[(employee_id, local_date)] = assigned_on_date

    unique_dates = sorted({slot.local_date for slot in slots})
    parsed_dates = [date.fromisoformat(local_date) for local_date in unique_dates]
    if request.max_consecutive_shifts is not None and request.max_consecutive_shifts > 0:
        for employee in employees:
            for sequence in _consecutive_date_sequences(parsed_dates):
                window_size = request.max_consecutive_shifts + 1
                for start_index in range(0, len(sequence) - window_size + 1):
                    window = sequence[start_index : start_index + window_size]
                    variables = [
                        assigned_by_employee_date[(employee.id, current_date)]
                        for current_date in window
                        if (employee.id, current_date) in assigned_by_employee_date
                    ]
                    if variables:
                        model.Add(sum(variables) <= request.max_consecutive_shifts)

    if request.min_rest_hours is not None and request.min_rest_hours > 0:
        _add_min_rest_constraints(
            model=model,
            employees=employees,
            slots=slots,
            vars_by_employee_slot=vars_by_employee_slot,
            min_rest_hours=request.min_rest_hours,
        )

    for employee in employees:
        for first_date, second_date in zip(parsed_dates, parsed_dates[1:]):
            if (second_date - first_date).days != 1:
                continue
            first_assigned = assigned_by_employee_date.get((employee.id, first_date))
            second_assigned = assigned_by_employee_date.get((employee.id, second_date))
            if first_assigned is None or second_assigned is None:
                continue
            adjacent_repeat = model.NewBoolVar(
                "adjacent_repeat_"
                f"{employee.id}_{first_date.isoformat()}_{second_date.isoformat()}"
            )
            model.Add(adjacent_repeat <= first_assigned)
            model.Add(adjacent_repeat <= second_assigned)
            model.Add(adjacent_repeat >= first_assigned + second_assigned - 1)
            objective_terms.append(adjacent_repeat * ADJACENT_DAY_REPEAT_WEIGHT)

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = request.timeout_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = request.random_seed

    status = solver.Solve(model)
    if status == cp_model.INFEASIBLE:
        return SolveScheduleResult(
            status="infeasible",
            solver_status="cp_sat_infeasible",
            solution_quality="infeasible",
            assignments=[],
            issues=[],
        )
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return SolveScheduleResult(
            status="failed",
            solver_status="cp_sat_unknown",
            solution_quality="unknown",
            assignments=[],
            issues=[],
        )

    assignments = _extract_assignments(
        assignment_vars=assignment_vars,
        requirements=requirements,
        solver=solver,
    )
    issues = _extract_issues(
        requirements=requirements,
        solver=solver,
        unfilled_vars=unfilled_vars,
    )
    return SolveScheduleResult(
        status="succeeded",
        solver_status=(
            "cp_sat_optimal" if status == cp_model.OPTIMAL else "cp_sat_feasible"
        ),
        solution_quality=(
            "optimal"
            if status == cp_model.OPTIMAL
            else "feasible_not_proven_optimal"
        ),
        assignments=assignments,
        issues=issues,
    )


def _extract_assignments(
    *,
    assignment_vars: dict[tuple[str, str], cp_model.IntVar],
    requirements: list[ScheduleRequirementInput],
    solver: cp_model.CpSolver,
) -> list[ScheduleAssignment]:
    requirement_by_id = {requirement.id: requirement for requirement in requirements}
    assignments: list[ScheduleAssignment] = []
    for requirement_id, employee_id in sorted(assignment_vars):
        variable = assignment_vars[(requirement_id, employee_id)]
        if solver.Value(variable) != 1:
            continue
        requirement = requirement_by_id[requirement_id]
        assignments.append(
            ScheduleAssignment(
                slot_id=requirement.slot_id,
                role_id=requirement.role_id,
                employee_id=employee_id,
                requirement_id=requirement_id,
            )
        )
    return sorted(
        assignments,
        key=lambda assignment: (
            assignment.slot_id,
            assignment.role_id,
            assignment.employee_id,
        ),
    )


def _extract_issues(
    *,
    requirements: list[ScheduleRequirementInput],
    solver: cp_model.CpSolver,
    unfilled_vars: dict[str, cp_model.IntVar],
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for requirement in requirements:
        missing_count = solver.Value(unfilled_vars[requirement.id])
        if missing_count <= 0:
            continue
        issues.append(
            {
                "requirement_id": requirement.id,
                "slot_id": requirement.slot_id,
                "role_id": requirement.role_id,
                "type": "unfilled_requirement",
                "missing_count": missing_count,
                "severity": "high",
            }
        )
    return issues


def _slot_index(slots: list[object], slot_id: str) -> int:
    for index, slot in enumerate(slots):
        if getattr(slot, "id") == slot_id:
            return index
    return len(slots)


def _week_key(local_date_text: str) -> tuple[int, int]:
    local_date = date.fromisoformat(local_date_text)
    iso_year, iso_week, _ = local_date.isocalendar()
    return iso_year, iso_week


def _consecutive_date_sequences(dates: list[date]) -> list[list[date]]:
    sequences: list[list[date]] = []
    current_sequence: list[date] = []
    for current_date in dates:
        if not current_sequence:
            current_sequence = [current_date]
            continue
        if (current_date - current_sequence[-1]).days == 1:
            current_sequence.append(current_date)
            continue
        sequences.append(current_sequence)
        current_sequence = [current_date]
    if current_sequence:
        sequences.append(current_sequence)
    return sequences


def _add_min_rest_constraints(
    *,
    model: cp_model.CpModel,
    employees: list[EmployeeInput],
    slots: list[object],
    vars_by_employee_slot: dict[tuple[str, str], list[cp_model.IntVar]],
    min_rest_hours: int,
) -> None:
    dated_slots = [
        (
            slot,
            datetime.fromisoformat(slot.starts_at),
            datetime.fromisoformat(slot.ends_at),
        )
        for slot in slots
        if getattr(slot, "starts_at", None) and getattr(slot, "ends_at", None)
    ]
    for employee in employees:
        for index, (first_slot, first_start, first_end) in enumerate(dated_slots):
            for second_slot, second_start, second_end in dated_slots[index + 1 :]:
                if first_start <= second_start:
                    earlier_slot, earlier_end = first_slot, first_end
                    later_slot, later_start = second_slot, second_start
                else:
                    earlier_slot, earlier_end = second_slot, second_end
                    later_slot, later_start = first_slot, first_start
                rest_hours = (later_start - earlier_end).total_seconds() / 3600
                if rest_hours >= min_rest_hours:
                    continue
                variables = (
                    vars_by_employee_slot[(employee.id, earlier_slot.id)]
                    + vars_by_employee_slot[(employee.id, later_slot.id)]
                )
                if variables:
                    model.Add(sum(variables) <= 1)


def _fair_assignment_target(
    requirements: list[ScheduleRequirementInput],
    employees: list[EmployeeInput],
) -> int:
    if not employees:
        return 0
    total_required = sum(requirement.required_count for requirement in requirements)
    return max(1, (total_required + len(employees) - 1) // len(employees))

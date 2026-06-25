from __future__ import annotations

from collections import defaultdict
from datetime import date

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

    employee_by_id = {employee.id: employee for employee in employees}
    for (employee_id, _week_key_value), variables in vars_by_employee_week.items():
        employee = employee_by_id[employee_id]
        if employee.max_shifts_per_week is None:
            continue
        model.Add(sum(variables) <= employee.max_shifts_per_week)

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
        objective_terms.append(over_target * FAIRNESS_OVER_TARGET_WEIGHT)

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


def _fair_assignment_target(
    requirements: list[ScheduleRequirementInput],
    employees: list[EmployeeInput],
) -> int:
    if not employees:
        return 0
    total_required = sum(requirement.required_count for requirement in requirements)
    return max(1, (total_required + len(employees) - 1) // len(employees))

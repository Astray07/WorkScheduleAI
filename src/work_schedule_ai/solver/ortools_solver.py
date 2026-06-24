from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from work_schedule_ai.solver.models import (
    ScheduleAssignment,
    ScheduleRequirementInput,
    SolveScheduleRequest,
    SolveScheduleResult,
)


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
    role_ids = sorted({requirement.role_id for requirement in requirements})
    role_index = {role_id: index for index, role_id in enumerate(role_ids)}

    model = cp_model.CpModel()
    assignment_vars: dict[tuple[str, str], cp_model.IntVar] = {}
    vars_by_employee_slot: dict[tuple[str, str], list[cp_model.IntVar]] = defaultdict(list)
    vars_by_requirement: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    vars_by_employee_slot_for_pair: dict[tuple[str, str], list[cp_model.IntVar]] = (
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

    for requirement in requirements:
        for employee in employees:
            variable = assignment_vars.get((requirement.id, employee.id))
            if variable is None:
                continue
            tie_breaker = (
                slot_index[requirement.slot_id] * 10_000
                + role_index[requirement.role_id] * 1_000
                + employee_index[employee.id]
            )
            objective_terms.append(variable * tie_breaker)

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

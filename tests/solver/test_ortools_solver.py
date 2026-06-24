from work_schedule_ai.solver.models import (
    BlockedPair,
    EmployeeInput,
    ScheduleRequirementInput,
    ScheduleSlotInput,
    SolveScheduleRequest,
)
from work_schedule_ai.solver.ortools_solver import solve_schedule


def test_solver_assigns_golden_case_without_issues():
    request = _golden_request()

    result = solve_schedule(request)

    assert result.status == "succeeded"
    assert result.solver_status in {"cp_sat_optimal", "cp_sat_feasible"}
    assert result.solution_quality in {"optimal", "feasible_not_proven_optimal"}
    assert len(result.assignments) == 14
    assert result.issues == []
    assert {
        (assignment.slot_id, assignment.role_id)
        for assignment in result.assignments
    } == {
        (requirement.slot_id, requirement.role_id)
        for requirement in request.requirements
    }


def test_solver_respects_role_eligibility_and_unavailability():
    request = _golden_request(
        unavailable_by_employee={"emp_1": {"slot_2026_07_01_day"}},
    )

    result = solve_schedule(request)

    assert result.issues == []
    assert all(
        not (
            assignment.employee_id == "emp_1"
            and assignment.slot_id == "slot_2026_07_01_day"
        )
        for assignment in result.assignments
    )
    assert all(
        _employee_can_work_role(request, assignment.employee_id, assignment.role_id)
        for assignment in result.assignments
    )


def test_solver_respects_blocked_pair_per_slot():
    request = _golden_request(blocked_pairs=[BlockedPair("emp_1", "emp_2")])

    result = solve_schedule(request)

    assignments_by_slot: dict[str, set[str]] = {}
    for assignment in result.assignments:
        assignments_by_slot.setdefault(assignment.slot_id, set()).add(
            assignment.employee_id
        )
    assert all(
        not {"emp_1", "emp_2"}.issubset(employee_ids)
        for employee_ids in assignments_by_slot.values()
    )


def test_solver_reports_unfilled_requirement_as_soft_issue():
    request = SolveScheduleRequest(
        employees=[
            EmployeeInput(
                id="emp_senior",
                role_ids=frozenset({"role_senior"}),
                unavailable_slot_ids=frozenset(),
            )
        ],
        slots=[ScheduleSlotInput(id="slot_2026_07_01_day", local_date="2026-07-01")],
        requirements=[
            ScheduleRequirementInput(
                id="req_senior",
                slot_id="slot_2026_07_01_day",
                role_id="role_senior",
                required_count=1,
                unfilled_weight=100,
            ),
            ScheduleRequirementInput(
                id="req_junior",
                slot_id="slot_2026_07_01_day",
                role_id="role_junior",
                required_count=1,
                unfilled_weight=100,
            ),
        ],
        blocked_pairs=[],
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    assert result.status == "succeeded"
    assert len(result.assignments) == 1
    assert result.issues == [
        {
            "requirement_id": "req_junior",
            "slot_id": "slot_2026_07_01_day",
            "role_id": "role_junior",
            "type": "unfilled_requirement",
            "missing_count": 1,
            "severity": "high",
        }
    ]


def test_solver_is_deterministic_for_same_input():
    request = _golden_request()

    first = solve_schedule(request)
    second = solve_schedule(request)

    assert [
        (assignment.slot_id, assignment.role_id, assignment.employee_id)
        for assignment in first.assignments
    ] == [
        (assignment.slot_id, assignment.role_id, assignment.employee_id)
        for assignment in second.assignments
    ]


def _golden_request(
    *,
    unavailable_by_employee: dict[str, set[str]] | None = None,
    blocked_pairs: list[BlockedPair] | None = None,
) -> SolveScheduleRequest:
    unavailable_by_employee = unavailable_by_employee or {}
    slots = [
        ScheduleSlotInput(
            id=f"slot_2026_07_{day:02d}_day",
            local_date=f"2026-07-{day:02d}",
        )
        for day in range(1, 8)
    ]
    requirements = [
        ScheduleRequirementInput(
            id=f"req_{slot.id}_{role_id}",
            slot_id=slot.id,
            role_id=role_id,
            required_count=1,
            unfilled_weight=100,
        )
        for slot in slots
        for role_id in ("role_senior", "role_junior")
    ]
    employees = [
        EmployeeInput(
            id="emp_1",
            role_ids=frozenset({"role_senior"}),
            unavailable_slot_ids=frozenset(unavailable_by_employee.get("emp_1", set())),
        ),
        EmployeeInput(
            id="emp_2",
            role_ids=frozenset({"role_junior"}),
            unavailable_slot_ids=frozenset(unavailable_by_employee.get("emp_2", set())),
        ),
        EmployeeInput(
            id="emp_3",
            role_ids=frozenset({"role_senior", "role_junior"}),
            unavailable_slot_ids=frozenset(unavailable_by_employee.get("emp_3", set())),
        ),
        EmployeeInput(
            id="emp_4",
            role_ids=frozenset({"role_senior", "role_junior"}),
            unavailable_slot_ids=frozenset(unavailable_by_employee.get("emp_4", set())),
        ),
    ]
    return SolveScheduleRequest(
        employees=employees,
        slots=slots,
        requirements=requirements,
        blocked_pairs=blocked_pairs or [],
        timeout_seconds=5,
        random_seed=1,
    )


def _employee_can_work_role(
    request: SolveScheduleRequest,
    employee_id: str,
    role_id: str,
) -> bool:
    employee = next(candidate for candidate in request.employees if candidate.id == employee_id)
    return role_id in employee.role_ids

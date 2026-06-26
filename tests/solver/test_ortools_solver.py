from datetime import date

from work_schedule_ai.solver.models import (
    AvoidPair,
    BlockedPair,
    EmployeeInput,
    ScheduleRequirementInput,
    ScheduleSlotInput,
    SolveScheduleRequest,
    StaffingTargetPenalty,
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


def test_solver_balances_assignments_across_equivalent_employees():
    request = SolveScheduleRequest(
        employees=[
            EmployeeInput(id=f"emp_{index}", role_ids=frozenset({"role_any"}))
            for index in range(1, 5)
        ],
        slots=[
            ScheduleSlotInput(
                id=f"slot_2026_07_0{index}_day",
                local_date=f"2026-07-0{index}",
            )
            for index in range(1, 5)
        ],
        requirements=[
            ScheduleRequirementInput(
                id=f"req_{index}",
                slot_id=f"slot_2026_07_0{index}_day",
                role_id="role_any",
                required_count=1,
                unfilled_weight=100,
            )
            for index in range(1, 5)
        ],
        blocked_pairs=[],
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    assignment_counts = {
        employee.id: sum(
            1
            for assignment in result.assignments
            if assignment.employee_id == employee.id
        )
        for employee in request.employees
    }
    assert result.issues == []
    assert sorted(assignment_counts.values()) == [1, 1, 1, 1]


def test_solver_applies_explicit_staffing_target_penalty():
    base_request = SolveScheduleRequest(
        employees=[
            EmployeeInput(id="emp_1", role_ids=frozenset({"role_any"})),
            EmployeeInput(id="emp_2", role_ids=frozenset({"role_any"})),
        ],
        slots=[ScheduleSlotInput(id="slot_1", local_date="2026-07-01")],
        requirements=[
            ScheduleRequirementInput(
                id="req_1",
                slot_id="slot_1",
                role_id="role_any",
                required_count=2,
                unfilled_weight=0,
            )
        ],
        blocked_pairs=[],
        timeout_seconds=5,
        random_seed=1,
    )
    one_staff_request = SolveScheduleRequest(
        **{
            **base_request.__dict__,
            "staffing_targets": [
                StaffingTargetPenalty(
                    slot_id="slot_1",
                    target_staff_count=1,
                    under_staffing_penalty=1_000_000,
                    over_staffing_penalty=1_000_000,
                )
            ],
        }
    )
    two_staff_request = SolveScheduleRequest(
        **{
            **base_request.__dict__,
            "staffing_targets": [
                StaffingTargetPenalty(
                    slot_id="slot_1",
                    target_staff_count=2,
                    under_staffing_penalty=1_000_000,
                    over_staffing_penalty=1_000_000,
                )
            ],
        }
    )

    one_staff_result = solve_schedule(one_staff_request)
    two_staff_result = solve_schedule(two_staff_request)

    assert len(one_staff_result.assignments) == 1
    assert len(two_staff_result.assignments) == 2


def test_solver_respects_employee_weekly_shift_cap():
    request = SolveScheduleRequest(
        employees=[
            EmployeeInput(
                id="emp_limited",
                role_ids=frozenset({"role_any"}),
                max_shifts_per_week=2,
            ),
            EmployeeInput(id="emp_available", role_ids=frozenset({"role_any"})),
        ],
        slots=[
            ScheduleSlotInput(
                id=f"slot_2026_07_{day:02d}_day",
                local_date=f"2026-07-{day:02d}",
            )
            for day in range(6, 13)
        ],
        requirements=[
            ScheduleRequirementInput(
                id=f"req_{day}",
                slot_id=f"slot_2026_07_{day:02d}_day",
                role_id="role_any",
                required_count=1,
                unfilled_weight=100,
            )
            for day in range(6, 13)
        ],
        blocked_pairs=[],
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    limited_assignments = [
        assignment
        for assignment in result.assignments
        if assignment.employee_id == "emp_limited"
    ]
    assert result.issues == []
    assert len(limited_assignments) <= 2


def test_solver_respects_global_weekly_shift_cap_when_employee_has_no_override():
    request = SolveScheduleRequest(
        employees=[
            EmployeeInput(id="emp_limited", role_ids=frozenset({"role_any"})),
            EmployeeInput(id="emp_available", role_ids=frozenset({"role_any"})),
        ],
        slots=[
            ScheduleSlotInput(
                id=f"slot_2026_07_{day:02d}_day",
                local_date=f"2026-07-{day:02d}",
            )
            for day in range(6, 13)
        ],
        requirements=[
            ScheduleRequirementInput(
                id=f"req_{day}",
                slot_id=f"slot_2026_07_{day:02d}_day",
                role_id="role_any",
                required_count=1,
                unfilled_weight=100,
            )
            for day in range(6, 13)
        ],
        blocked_pairs=[],
        global_max_shifts_per_week=4,
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    assignment_counts = {
        employee.id: sum(
            1
            for assignment in result.assignments
            if assignment.employee_id == employee.id
        )
        for employee in request.employees
    }
    assert result.issues == []
    assert max(assignment_counts.values()) <= 4


def test_solver_respects_max_consecutive_shifts():
    request = SolveScheduleRequest(
        employees=[
            EmployeeInput(id="emp_1", role_ids=frozenset({"role_any"})),
            EmployeeInput(id="emp_2", role_ids=frozenset({"role_any"})),
        ],
        slots=[
            ScheduleSlotInput(
                id=f"slot_2026_07_0{day}_day",
                local_date=f"2026-07-0{day}",
            )
            for day in range(1, 5)
        ],
        requirements=[
            ScheduleRequirementInput(
                id=f"req_{day}",
                slot_id=f"slot_2026_07_0{day}_day",
                role_id="role_any",
                required_count=1,
                unfilled_weight=100,
            )
            for day in range(1, 5)
        ],
        blocked_pairs=[],
        max_consecutive_shifts=1,
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    date_by_slot_id = {
        slot.id: date.fromisoformat(slot.local_date)
        for slot in request.slots
    }
    assigned_dates_by_employee: dict[str, list[date]] = {
        employee.id: [] for employee in request.employees
    }
    for assignment in result.assignments:
        assigned_dates_by_employee[assignment.employee_id].append(
            date_by_slot_id[assignment.slot_id]
        )
    assert result.issues == []
    assert all(
        (second - first).days > 1
        for dates in assigned_dates_by_employee.values()
        for first, second in zip(sorted(dates), sorted(dates)[1:])
    )


def test_solver_penalizes_avoid_pair_when_alternative_exists():
    request = SolveScheduleRequest(
        employees=[
            EmployeeInput(id="emp_1", role_ids=frozenset({"role_any"})),
            EmployeeInput(id="emp_2", role_ids=frozenset({"role_any"})),
            EmployeeInput(id="emp_3", role_ids=frozenset({"role_any"})),
        ],
        slots=[ScheduleSlotInput(id="slot_2026_07_01_day", local_date="2026-07-01")],
        requirements=[
            ScheduleRequirementInput(
                id="req_1",
                slot_id="slot_2026_07_01_day",
                role_id="role_any",
                required_count=2,
                unfilled_weight=100,
            )
        ],
        blocked_pairs=[],
        avoid_pairs=[AvoidPair("emp_1", "emp_2", weight=1_000_000)],
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    assigned_employee_ids = {assignment.employee_id for assignment in result.assignments}
    assert result.issues == []
    assert not {"emp_1", "emp_2"}.issubset(assigned_employee_ids)


def test_solver_spreads_larger_mixed_role_demo_case():
    employees = []
    for index in range(1, 13):
        if index % 4 == 1:
            role_ids = frozenset({"role_senior"})
        elif index % 4 == 2:
            role_ids = frozenset({"role_junior"})
        else:
            role_ids = frozenset({"role_senior", "role_junior"})
        employees.append(
            EmployeeInput(
                id=f"emp_{index:03d}",
                role_ids=role_ids,
                max_shifts_per_week=5,
            )
        )
    slots = [
        ScheduleSlotInput(
            id=f"slot_2026_07_{day:02d}_day",
            local_date=f"2026-07-{day:02d}",
        )
        for day in range(1, 15)
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
    request = SolveScheduleRequest(
        employees=employees,
        slots=slots,
        requirements=requirements,
        blocked_pairs=[],
        timeout_seconds=5,
        random_seed=1,
    )

    result = solve_schedule(request)

    assignment_counts = {
        employee.id: sum(
            1
            for assignment in result.assignments
            if assignment.employee_id == employee.id
        )
        for employee in request.employees
    }
    assert result.issues == []
    assert max(assignment_counts.values()) <= 3
    assert sum(count > 0 for count in assignment_counts.values()) >= 10


def test_solver_discourages_adjacent_day_repeat_assignments():
    employees = []
    for index in range(1, 13):
        if index % 4 == 1:
            role_ids = frozenset({"role_senior"})
        elif index % 4 == 2:
            role_ids = frozenset({"role_junior"})
        else:
            role_ids = frozenset({"role_senior", "role_junior"})
        employees.append(
            EmployeeInput(
                id=f"emp_{index:03d}",
                role_ids=role_ids,
                unavailable_slot_ids=(
                    frozenset(
                        {
                            "slot_2026_07_02_day",
                            "slot_2026_07_03_day",
                            "slot_2026_07_04_day",
                        }
                    )
                    if index == 2
                    else frozenset()
                ),
                max_shifts_per_week=5,
            )
        )
    slots = [
        ScheduleSlotInput(
            id=f"slot_2026_07_{day:02d}_day",
            local_date=f"2026-07-{day:02d}",
        )
        for day in range(1, 32)
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
    request = SolveScheduleRequest(
        employees=employees,
        slots=slots,
        requirements=requirements,
        blocked_pairs=[BlockedPair("emp_001", "emp_002")],
        timeout_seconds=30,
        random_seed=1,
    )

    result = solve_schedule(request)

    date_by_slot_id = {
        slot.id: date.fromisoformat(slot.local_date)
        for slot in request.slots
    }
    assigned_dates_by_employee: dict[str, list[date]] = {
        employee.id: [] for employee in request.employees
    }
    for assignment in result.assignments:
        assigned_dates_by_employee[assignment.employee_id].append(
            date_by_slot_id[assignment.slot_id]
        )
    adjacent_pairs = {
        employee_id: [
            (first, second)
            for first, second in zip(sorted(dates), sorted(dates)[1:])
            if (second - first).days == 1
        ]
        for employee_id, dates in assigned_dates_by_employee.items()
    }

    assert result.issues == []
    assert all(not pairs for pairs in adjacent_pairs.values())


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

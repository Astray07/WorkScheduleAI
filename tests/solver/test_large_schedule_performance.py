from time import perf_counter

from work_schedule_ai.solver.large_cases import make_large_schedule_request
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

from work_schedule_ai.contracts import (
    CORE_M0_SCHEMAS,
    P0_REQUIRED_PATHS,
    contracts_dir,
    fixture_names,
    load_fixture,
    load_openapi_contract,
    missing_core_schemas,
    missing_p0_paths,
)


def test_contracts_dir_prefers_runtime_working_directory(monkeypatch, tmp_path):
    runtime_contracts_dir = tmp_path / "docs" / "contracts"
    runtime_contracts_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert contracts_dir() == runtime_contracts_dir


def test_openapi_contract_contains_p0_paths():
    contract = load_openapi_contract()

    assert missing_p0_paths(contract) == []
    assert len(P0_REQUIRED_PATHS) == 12


def test_openapi_contract_contains_core_schemas():
    contract = load_openapi_contract()

    assert missing_core_schemas(contract) == []
    assert "ScheduleRunResponse" in CORE_M0_SCHEMAS
    assert "ScheduleRunResultResponse" in CORE_M0_SCHEMAS


def test_fixture_set_contains_p0_states():
    names = fixture_names()

    assert names == [
        "p0-result-after-recalculation.json",
        "p0-result-before-relaxation.json",
        "p0-schedule-run-running.json",
    ]


def test_running_fixture_is_pollable_schedule_run():
    payload = load_fixture("p0-schedule-run-running.json")

    assert payload["status"] == "running"
    assert payload["current_attempt_no"] == 1
    assert payload["recalculation_count"] == 0
    assert payload["issues"] == []
    assert payload["proposals"] == []


def test_issue_fixture_exposes_unfilled_requirement_and_proposal():
    payload = load_fixture("p0-result-before-relaxation.json")

    assert payload["status"] == "infeasible"
    assert payload["read_only"] is False
    assert payload["issues"][0]["type"] == "unfilled_requirement"
    assert payload["issues"][0]["missing_count"] == 1
    assert payload["proposals"][0]["type"] == "approve_pair_constraint_override"
    assert payload["proposals"][0]["status"] == "suggested"


def test_recalculated_fixture_keeps_counters_distinct():
    payload = load_fixture("p0-result-after-recalculation.json")

    assert payload["status"] == "succeeded"
    assert payload["current_attempt_no"] == 2
    assert payload["recalculation_count"] == 1
    assert payload["issues"] == []
    assert any(
        assignment["source"] == "override"
        and assignment["warning_state"] == "approved_override"
        for assignment in payload["assignments"]
    )

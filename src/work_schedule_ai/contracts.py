import json
from pathlib import Path
from typing import Any


P0_REQUIRED_PATHS = [
    "/organizations",
    "/organizations/{organization_id}/employees/bulk-paste",
    "/organizations/{organization_id}/unavailabilities",
    "/organizations/{organization_id}/pair-constraints",
    "/organizations/{organization_id}/schedule-runs",
    "/organizations/{organization_id}/schedule-runs/{schedule_run_id}",
    "/organizations/{organization_id}/schedule-runs/{schedule_run_id}/result",
    "/organizations/{organization_id}/schedule-runs/{schedule_run_id}/manual-edits/validate",
    "/organizations/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve",
    "/organizations/{organization_id}/schedule-runs/{schedule_run_id}/recalculate",
    "/organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications",
    "/organizations/{organization_id}/schedule-publications/{publication_id}/excel",
]

CORE_M0_SCHEMAS = [
    "ScheduleRunStatus",
    "SolutionQuality",
    "SolverStatus",
    "Severity",
    "IssueType",
    "ReasonCode",
    "RelaxationProposalType",
    "RelaxationProposalStatus",
    "AssignmentSource",
    "WarningState",
    "PublicationStatus",
    "ScheduleRunResponse",
    "ScheduleRunResultResponse",
    "ScheduleIssue",
    "RelaxationProposal",
    "SchedulePublication",
]


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def contracts_dir() -> Path:
    return repository_root() / "docs" / "contracts"


def load_openapi_contract() -> dict[str, Any]:
    return _load_json(contracts_dir() / "openapi.m0.json")


def fixture_names() -> list[str]:
    fixture_dir = contracts_dir() / "fixtures"
    return sorted(path.name for path in fixture_dir.glob("*.json"))


def load_fixture(name: str) -> dict[str, Any]:
    if name not in fixture_names():
        raise FileNotFoundError(f"Unknown contract fixture: {name}")
    return _load_json(contracts_dir() / "fixtures" / name)


def missing_p0_paths(contract: dict[str, Any]) -> list[str]:
    paths = contract.get("paths", {})
    return [path for path in P0_REQUIRED_PATHS if path not in paths]


def missing_core_schemas(contract: dict[str, Any]) -> list[str]:
    schemas = contract.get("components", {}).get("schemas", {})
    return [schema for schema in CORE_M0_SCHEMAS if schema not in schemas]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return payload


from collections.abc import Generator
from io import BytesIO
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base


def test_p0_vertical_slice_recalculates_publishes_and_downloads_excel(
    client: TestClient,
):
    organization_response = client.post(
        "/organizations",
        json={"name": "P0 Clinic", "timezone": "Asia/Seoul"},
    )
    assert organization_response.status_code == 201
    organization = organization_response.json()
    organization_id = organization["id"]

    employee_response = client.post(
        f"/organizations/{organization_id}/employees/bulk-paste",
        json={
            "mode": "upsert",
            "rows": [
                _employee_row(1, "E001", "Kim", ["사수"]),
                _employee_row(2, "E002", "Lee", ["부사수"]),
                _employee_row(3, "E003", "Park", ["사수"]),
                _employee_row(4, "E004", "Choi", ["사수"]),
            ],
        },
    )
    assert employee_response.status_code == 200
    employee_payload = employee_response.json()
    assert employee_payload["created_count"] == 4
    employees_by_code = {
        employee["employee_code"]: employee
        for employee in employee_payload["employees"]
    }

    unavailability_response = client.post(
        f"/organizations/{organization_id}/unavailabilities",
        json={
            "employee_id": employees_by_code["E002"]["id"],
            "type": "vacation",
            "starts_at": "2026-07-01T00:00:00+09:00",
            "ends_at": "2026-07-02T00:00:00+09:00",
            "override_allowed": True,
            "note": "P0 demo vacation",
        },
    )
    assert unavailability_response.status_code == 201

    pair_response = client.post(
        f"/organizations/{organization_id}/pair-constraints",
        json={
            "employee_a_id": employees_by_code["E001"]["id"],
            "employee_b_id": employees_by_code["E002"]["id"],
            "type": "blocked",
            "severity": "high",
            "override_allowed": True,
            "active": True,
        },
    )
    assert pair_response.status_code == 201

    shift_type_response = client.post(
        f"/organizations/{organization_id}/shift-types",
        json={
            "name": "주간 근무",
            "local_start_time": "09:00",
            "local_end_time": "18:00",
            "timezone": "Asia/Seoul",
            "requirements": [
                {
                    "role_id": next(
                        role["id"]
                        for role in organization["default_roles"]
                        if role["name"] == "사수"
                    ),
                    "required_count": 1,
                },
                {
                    "role_id": next(
                        role["id"]
                        for role in organization["default_roles"]
                        if role["name"] == "부사수"
                    ),
                    "required_count": 1,
                },
            ],
        },
    )
    assert shift_type_response.status_code == 201

    run_response = client.post(
        f"/organizations/{organization_id}/schedule-runs",
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
            "template": "one_shift_per_day",
            "deterministic_mode": True,
            "timeout_seconds": 30,
        },
    )
    assert run_response.status_code == 202
    assert run_response.json()["solver_status"].startswith("cp_sat_")
    run_id = run_response.json()["id"]

    initial_result_response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )
    assert initial_result_response.status_code == 200
    initial_result = initial_result_response.json()
    assert initial_result["read_only"] is False
    assert len(initial_result["issues"]) == 1
    assert initial_result["issues"][0]["type"] == "unfilled_requirement"
    proposal_id = initial_result["proposals"][0]["id"]

    approval_response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/relaxation-proposals/{proposal_id}/approve",
        json={
            "reason": "P0 demo approval",
            "notification_required": True,
        },
    )
    assert approval_response.status_code == 201

    recalculation_response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/recalculate",
        json={"reason": "Apply approved relaxation proposal"},
    )
    assert recalculation_response.status_code == 202
    assert recalculation_response.json()["recalculation_count"] == 1
    assert recalculation_response.json()["current_attempt_no"] == 1

    recalculated_result_response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )
    assert recalculated_result_response.status_code == 200
    recalculated_result = recalculated_result_response.json()
    assert recalculated_result["issues"] == []
    assert recalculated_result["proposals"] == []
    assert len(recalculated_result["assignments"]) == 14

    publication_response = client.post(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/publications",
        json={
            "expected_assignment_snapshot_hash": recalculated_result[
                "assignment_snapshot_hash"
            ],
            "expected_issue_snapshot_hash": recalculated_result[
                "issue_snapshot_hash"
            ],
        },
    )
    assert publication_response.status_code == 201
    publication = publication_response.json()
    assert publication["status"] == "published"
    assert publication["schedule_run_id"] == run_id

    published_result_response = client.get(
        f"/organizations/{organization_id}/schedule-runs/{run_id}/result"
    )
    assert published_result_response.status_code == 200
    published_result = published_result_response.json()
    assert published_result["read_only"] is True
    assert published_result["publication"]["id"] == publication["id"]

    excel_response = client.get(
        f"/organizations/{organization_id}/schedule-publications/{publication['id']}/excel"
    )
    assert excel_response.status_code == 200
    assert excel_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    with zipfile.ZipFile(BytesIO(excel_response.content)) as workbook:
        assert "xl/worksheets/sheet1.xml" in workbook.namelist()
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "publication_id" in sheet_xml
    assert "local_date" in sheet_xml
    assert "Lee" in sheet_xml


def _employee_row(
    row_no: int,
    employee_code: str,
    name: str,
    role_names: list[str],
) -> dict:
    return {
        "row_no": row_no,
        "employee_code": employee_code,
        "name": name,
        "role_names": role_names,
        "max_shifts_per_week": 5,
    }


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

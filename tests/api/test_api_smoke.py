from fastapi.testclient import TestClient

from work_schedule_ai.api.app import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_m0_contract_summary_reports_no_missing_contract_items():
    client = TestClient(create_app())

    response = client.get("/contracts/m0/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["missing_paths"] == []
    assert payload["missing_schemas"] == []
    assert payload["path_count"] >= 12
    assert payload["schema_count"] >= 16
    assert payload["fixture_names"] == [
        "p0-result-after-recalculation.json",
        "p0-result-before-relaxation.json",
        "p0-schedule-run-running.json",
    ]


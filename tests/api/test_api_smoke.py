from fastapi.testclient import TestClient

from work_schedule_ai.api.app import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_version_exposes_deployment_and_solver_policy(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    monkeypatch.setenv("RAILWAY_GIT_BRANCH", "feature/test")
    client = TestClient(create_app())

    response = client.get("/health/version")

    assert response.status_code == 200
    assert response.json() == {
        "app_env": "staging",
        "railway_environment": None,
        "railway_service": None,
        "railway_deployment_id": None,
        "git_commit": "abc123",
        "git_branch": "feature/test",
        "solver_policy_version": "weekly_cap_fairness_v1",
    }


def test_cors_allows_configured_frontend_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://frontend.example")
    client = TestClient(create_app())

    response = client.options(
        "/health",
        headers={
            "Origin": "https://frontend.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://frontend.example"
    )


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

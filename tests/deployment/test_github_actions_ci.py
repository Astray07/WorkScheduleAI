from pathlib import Path


def test_backend_ci_postgres_uses_dedicated_host_port():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "55432:5432" in workflow
    assert (
        "TEST_POSTGRES_URL: "
        "postgresql+psycopg://postgres:postgres@127.0.0.1:55432/postgres"
    ) in workflow
    assert "postgres:postgres@localhost:5432/postgres" not in workflow


def test_backend_ci_starts_postgres_with_explicit_docker_health_check():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "docker run --name work-schedule-ai-postgres" in workflow
    assert "POSTGRES_HOST_AUTH_METHOD=trust" in workflow
    assert "docker exec work-schedule-ai-postgres pg_isready" in workflow
    assert "docker logs work-schedule-ai-postgres" in workflow


def test_backend_ci_verifies_postgres_connection_before_pytest():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "Verify PostgreSQL connection" in workflow
    assert "with engine.connect() as connection" in workflow
    assert 'connection.execute(text("SELECT 1"))' in workflow

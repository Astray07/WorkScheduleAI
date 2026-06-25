from pathlib import Path


def test_backend_ci_postgres_uses_dedicated_host_port():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "55432:5432" in workflow
    assert (
        "TEST_POSTGRES_URL: "
        "postgresql+psycopg://postgres:postgres@127.0.0.1:55432/postgres"
    ) in workflow
    assert "postgres:postgres@localhost:5432/postgres" not in workflow

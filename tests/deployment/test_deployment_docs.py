from pathlib import Path


def test_railway_docs_include_postgres_rls_signoff_command():
    docs = Path("docs/deployment/railway.md").read_text(encoding="utf-8")

    assert "TEST_POSTGRES_URL" in docs
    assert "tests\\db\\test_postgresql_rls_integration.py" in docs


def test_railway_docs_include_service_variable_checklist():
    docs = Path("docs/deployment/railway.md").read_text(encoding="utf-8")

    assert "API service variable checklist" in docs
    assert "Worker service variable checklist" in docs
    assert "Frontend service variable checklist" in docs
    assert "WORKSCHEDULEAI_EMPLOYEE_LINK_SECRET" in docs
    assert "VITE_API_BASE_URL" in docs


def test_railway_docs_include_multi_worker_lease_rule():
    docs = Path("docs/deployment/railway.md").read_text(encoding="utf-8")

    assert "Multi-worker rule" in docs
    assert "WORKSCHEDULEAI_QUEUE_LEASE_SECONDS" in docs
    assert "maximum solver timeout" in docs

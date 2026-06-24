from work_schedule_ai.db.url import normalize_database_url


def test_normalize_database_url_rewrites_railway_postgres_scheme_to_psycopg():
    assert (
        normalize_database_url("postgres://user:pass@example.railway.internal:5432/db")
        == "postgresql+psycopg://user:pass@example.railway.internal:5432/db"
    )


def test_normalize_database_url_rewrites_plain_postgresql_scheme_to_psycopg():
    assert (
        normalize_database_url("postgresql://user:pass@example.railway.internal:5432/db")
        == "postgresql+psycopg://user:pass@example.railway.internal:5432/db"
    )


def test_normalize_database_url_keeps_existing_driver_and_sqlite_urls():
    assert (
        normalize_database_url(
            "postgresql+psycopg://user:pass@example.railway.internal:5432/db"
        )
        == "postgresql+psycopg://user:pass@example.railway.internal:5432/db"
    )
    assert normalize_database_url("sqlite:///work_schedule_ai.sqlite3") == (
        "sqlite:///work_schedule_ai.sqlite3"
    )

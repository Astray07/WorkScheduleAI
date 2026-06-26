import os
from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from work_schedule_ai.db.url import normalize_database_url
from work_schedule_ai.api.security import enforce_organization_access

DATABASE_URL = normalize_database_url(
    os.environ.get("DATABASE_URL", "sqlite:///work_schedule_ai.sqlite3")
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_db_session(request: Request) -> Generator[Session, None, None]:
    with SessionLocal() as session:
        organization_id = request.path_params.get("organization_id")
        if organization_id:
            set_tenant_context(session, organization_id)
            enforce_organization_access(session, request, organization_id)
        yield session


def set_tenant_context(session: Session, organization_id: str) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    session.execute(
        text(
            "SELECT set_config("
            "'app.current_organization_id', :organization_id, true)"
        ),
        {"organization_id": organization_id},
    )

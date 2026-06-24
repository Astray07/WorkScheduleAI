import os
from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///work_schedule_ai.sqlite3")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_db_session(request: Request) -> Generator[Session, None, None]:
    with SessionLocal() as session:
        organization_id = request.path_params.get("organization_id")
        if organization_id:
            set_tenant_context(session, organization_id)
        yield session


def set_tenant_context(session: Session, organization_id: str) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SET LOCAL app.current_organization_id = :organization_id"),
        {"organization_id": organization_id},
    )

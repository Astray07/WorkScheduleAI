import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///work_schedule_ai.sqlite3")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


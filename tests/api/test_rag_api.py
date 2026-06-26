from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Organization, RagQueryAudit


def test_rag_query_returns_tenant_scoped_evidence_and_audit(client: TestClient, db_session: Session):
    ingest_response = client.post(
        "/organizations/org_1/rag/documents",
        json={
            "source_type": "organization_policy",
            "document_title": "근무표 작성 규칙",
            "checked_at": "2026-06-26",
            "chunks": ["야간 근무 다음 날에는 최소 11시간 휴식을 권장합니다."],
        },
    )
    assert ingest_response.status_code == 201
    other_response = client.post(
        "/organizations/org_2/rag/documents",
        json={
            "source_type": "organization_policy",
            "document_title": "다른 조직 규칙",
            "checked_at": "2026-06-26",
            "chunks": ["이 근거는 org_1에 보이면 안 됩니다."],
        },
    )
    assert other_response.status_code == 201

    query_response = client.post(
        "/organizations/org_1/rag/query",
        json={"query": "야간 휴식", "purpose": "schedule_explanation"},
    )

    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["status"] == "grounded"
    assert payload["evidence"][0]["document_title"] == "근무표 작성 규칙"
    assert "다른 조직" not in str(payload)
    assert db_session.query(RagQueryAudit).count() == 1


def test_rag_ingest_rejects_unknown_source_type(client: TestClient):
    response = client.post(
        "/organizations/org_1/rag/documents",
        json={
            "source_type": "unknown",
            "document_title": "출처 미상",
            "checked_at": "2026-06-26",
            "chunks": ["검증되지 않은 문서입니다."],
        },
    )

    assert response.status_code == 422


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
        session.add_all(
            [
                Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"),
                Organization(id="org_2", name="Clinic B", timezone="Asia/Seoul"),
            ]
        )
        session.commit()
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

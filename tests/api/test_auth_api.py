from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
import base64
import hashlib

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session, set_tenant_context
from work_schedule_ai.api.routes import auth as auth_route
from work_schedule_ai.api.security import enforce_organization_access
from work_schedule_ai.api.signed_actor_tokens import verify_actor_token
from work_schedule_ai.db.models import Base, Membership, Organization, User


TEST_ACTOR_SECRET = "test-actor-secret-with-at-least-32-bytes"


def test_login_issues_signed_actor_token_for_valid_member(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["organization_id"] == "org_1"
    assert payload["user_id"] == "user_scheduler"
    assert payload["role"] == "scheduler"
    claims = verify_actor_token(
        payload["access_token"],
        secret=TEST_ACTOR_SECRET,
        organization_id="org_1",
    )
    assert claims.user_id == "user_scheduler"


def test_login_rejects_invalid_password(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "wrong-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_user_without_password_hash(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "pending@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_ambiguous_case_insensitive_email(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client(seed_duplicate_email=True)

    response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_weak_signed_actor_secret(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", "short-secret")
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "SIGNED_ACTOR_SECRET_WEAK"
    assert detail["message"] == auth_route.LOGIN_CONFIGURATION_MESSAGE
    assert detail["field"] == "login"
    assert "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET" not in detail["message"]


def test_login_rejects_missing_signed_actor_secret_without_env_name(monkeypatch):
    monkeypatch.delenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", raising=False)
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "SIGNED_ACTOR_SECRET_REQUIRED"
    assert detail["message"] == auth_route.LOGIN_CONFIGURATION_MESSAGE
    assert detail["field"] == "login"
    assert "WORKSCHEDULEAI_SIGNED_ACTOR_SECRET" not in detail["message"]


def test_login_sets_tenant_context_from_request_body(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    tenant_context_calls: list[str] = []
    monkeypatch.setattr(
        auth_route,
        "set_tenant_context",
        lambda _session, organization_id: tenant_context_calls.append(organization_id),
        raising=False,
    )
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 200
    assert tenant_context_calls == ["org_1"]


def test_login_rejects_user_without_organization_membership(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client()

    response = client.post(
        "/auth/login",
        json={
            "email": "outsider@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ORGANIZATION_ACCESS_DENIED"


def test_session_returns_actor_context_from_signed_token(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    client = _client()
    login_response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/session?organization_id=org_1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": "org_1",
        "user_id": "user_scheduler",
        "email": "scheduler@example.com",
        "name": "Scheduler",
        "role": "scheduler",
    }


def test_session_sets_tenant_context_from_query(monkeypatch):
    monkeypatch.setenv("WORKSCHEDULEAI_SIGNED_ACTOR_SECRET", TEST_ACTOR_SECRET)
    tenant_context_calls: list[str] = []
    monkeypatch.setattr(
        auth_route,
        "set_tenant_context",
        lambda _session, organization_id: tenant_context_calls.append(organization_id),
        raising=False,
    )
    client = _client()
    login_response = client.post(
        "/auth/login",
        json={
            "email": "scheduler@example.com",
            "password": "correct-password",
            "organization_id": "org_1",
        },
    )
    token = login_response.json()["access_token"]
    tenant_context_calls.clear()

    response = client.get(
        "/auth/session?organization_id=org_1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert tenant_context_calls == ["org_1"]


def _client(*, seed_duplicate_email: bool = False) -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul"))
    session.add_all(
        [
            User(
                id="user_scheduler",
                email="scheduler@example.com",
                name="Scheduler",
                password_hash=_test_password_hash("correct-password"),
            ),
            User(
                id="user_outsider",
                email="outsider@example.com",
                name="Outsider",
                password_hash=_test_password_hash("correct-password"),
            ),
            User(
                id="user_pending",
                email="pending@example.com",
                name="Pending",
                password_hash=None,
            ),
        ]
    )
    if seed_duplicate_email:
        session.add(
            User(
                id="user_scheduler_upper",
                email="Scheduler@example.com",
                name="Duplicate Scheduler",
                password_hash=_test_password_hash("correct-password"),
            )
        )
    session.add_all(
        [
            Membership(
                organization_id="org_1",
                user_id="user_scheduler",
                role="scheduler",
            ),
            Membership(
                organization_id="org_1",
                user_id="user_pending",
                role="scheduler",
            ),
        ]
    )
    session.commit()
    app = create_app()

    def override_session(request: Request) -> Generator[Session, None, None]:
        organization_id = request.path_params.get("organization_id")
        if organization_id:
            set_tenant_context(session, organization_id)
            enforce_organization_access(session, request, organization_id)
        yield session

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def _test_password_hash(password: str) -> str:
    salt = b"test-salt"
    iterations = 100_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )

from datetime import datetime, timedelta, timezone

import pytest

from work_schedule_ai.api.signed_employee_links import (
    EmployeeDeepLinkTokenError,
    sign_employee_deep_link,
    verify_employee_deep_link,
)


def test_signed_employee_deep_link_round_trips_expected_claims():
    expires_at = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
    token = sign_employee_deep_link(
        secret="test-secret-with-at-least-32-bytes",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=expires_at,
        issued_at=datetime(2026, 6, 26, 0, 0, tzinfo=timezone.utc),
    )

    claims = verify_employee_deep_link(
        token,
        secret="test-secret-with-at-least-32-bytes",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        now=datetime(2026, 6, 26, 1, 0, tzinfo=timezone.utc),
    )

    assert claims.scope == "employee_publication_link"
    assert claims.organization_id == "org_1"
    assert claims.publication_id == "publication_1"
    assert claims.employee_id == "emp_1"
    assert claims.expires_at == expires_at


def test_signed_employee_deep_link_rejects_weak_signing_secret():
    with pytest.raises(ValueError, match="at least 32 characters"):
        sign_employee_deep_link(
            secret="short-secret",
            organization_id="org_1",
            publication_id="publication_1",
            employee_id="emp_1",
            expires_at=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        )


def test_signed_employee_deep_link_verification_rejects_weak_secret():
    with pytest.raises(EmployeeDeepLinkTokenError) as error:
        verify_employee_deep_link(
            "malformed",
            secret="short-secret",
            organization_id="org_1",
            publication_id="publication_1",
            employee_id="emp_1",
        )

    assert error.value.code == "SECRET_WEAK"


def test_signed_employee_deep_link_rejects_tampering():
    token = sign_employee_deep_link(
        secret="test-secret-with-at-least-32-bytes",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    header, payload, signature = token.split(".")
    replacement = "A" if payload[0] != "A" else "B"
    tampered = f"{header}.{replacement}{payload[1:]}.{signature}"

    with pytest.raises(EmployeeDeepLinkTokenError) as error:
        verify_employee_deep_link(
            tampered,
            secret="test-secret-with-at-least-32-bytes",
            organization_id="org_1",
            publication_id="publication_1",
            employee_id="emp_1",
            now=datetime(2026, 6, 26, tzinfo=timezone.utc),
        )

    assert error.value.code == "INVALID_SIGNATURE"


def test_signed_employee_deep_link_rejects_expired_token():
    token = sign_employee_deep_link(
        secret="test-secret-with-at-least-32-bytes",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=datetime(2026, 6, 26, 1, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(EmployeeDeepLinkTokenError) as error:
        verify_employee_deep_link(
            token,
            secret="test-secret-with-at-least-32-bytes",
            organization_id="org_1",
            publication_id="publication_1",
            employee_id="emp_1",
            now=datetime(2026, 6, 26, 1, 0, 1, tzinfo=timezone.utc),
        )

    assert error.value.code == "TOKEN_EXPIRED"


def test_signed_employee_deep_link_rejects_cross_employee_reuse():
    token = sign_employee_deep_link(
        secret="test-secret-with-at-least-32-bytes",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with pytest.raises(EmployeeDeepLinkTokenError) as error:
        verify_employee_deep_link(
            token,
            secret="test-secret-with-at-least-32-bytes",
            organization_id="org_1",
            publication_id="publication_1",
            employee_id="emp_2",
        )

    assert error.value.code == "CLAIMS_MISMATCH"

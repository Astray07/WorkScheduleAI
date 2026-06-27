from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json


SCOPE = "employee_publication_link"
EMPLOYEE_LINK_SECRET_MIN_LENGTH = 32


@dataclass(frozen=True)
class EmployeeDeepLinkClaims:
    scope: str
    organization_id: str
    publication_id: str
    employee_id: str
    expires_at: datetime
    issued_at: datetime | None


class EmployeeDeepLinkTokenError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def sign_employee_deep_link(
    *,
    secret: str,
    organization_id: str,
    publication_id: str,
    employee_id: str,
    expires_at: datetime,
    issued_at: datetime | None = None,
) -> str:
    if not secret:
        raise ValueError("secret is required")
    if not is_employee_link_secret_strong(secret):
        raise ValueError(
            f"secret must be at least {EMPLOYEE_LINK_SECRET_MIN_LENGTH} characters"
        )
    header = {"alg": "HS256", "typ": SCOPE, "v": 1}
    payload = {
        "scope": SCOPE,
        "organization_id": organization_id,
        "publication_id": publication_id,
        "employee_id": employee_id,
        "exp": _timestamp(expires_at),
    }
    if issued_at is not None:
        payload["iat"] = _timestamp(issued_at)
    encoded_header = _base64url_json(header)
    encoded_payload = _base64url_json(payload)
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = _sign(signing_input, secret)
    return f"{signing_input}.{_base64url_encode(signature)}"


def verify_employee_deep_link(
    token: str,
    *,
    secret: str,
    organization_id: str,
    publication_id: str,
    employee_id: str,
    now: datetime | None = None,
) -> EmployeeDeepLinkClaims:
    if not secret:
        raise EmployeeDeepLinkTokenError("SECRET_REQUIRED", "secret is required")
    if not is_employee_link_secret_strong(secret):
        raise EmployeeDeepLinkTokenError(
            "SECRET_WEAK",
            f"secret must be at least {EMPLOYEE_LINK_SECRET_MIN_LENGTH} characters",
        )
    parts = token.split(".")
    if len(parts) != 3:
        raise EmployeeDeepLinkTokenError("MALFORMED_TOKEN", "token must have three parts")
    encoded_header, encoded_payload, encoded_signature = parts
    signing_input = f"{encoded_header}.{encoded_payload}"
    try:
        supplied_signature = _base64url_decode(encoded_signature)
    except ValueError as exc:
        raise EmployeeDeepLinkTokenError(
            "MALFORMED_TOKEN",
            "token signature is not valid base64url",
        ) from exc
    expected_signature = _sign(signing_input, secret)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise EmployeeDeepLinkTokenError("INVALID_SIGNATURE", "token signature is invalid")
    try:
        header = _base64url_json_decode(encoded_header)
        payload = _base64url_json_decode(encoded_payload)
    except ValueError as exc:
        raise EmployeeDeepLinkTokenError("MALFORMED_TOKEN", "token payload is invalid") from exc
    if header.get("typ") != SCOPE or payload.get("scope") != SCOPE:
        raise EmployeeDeepLinkTokenError("CLAIMS_MISMATCH", "token scope is invalid")
    if (
        payload.get("organization_id") != organization_id
        or payload.get("publication_id") != publication_id
        or payload.get("employee_id") != employee_id
    ):
        raise EmployeeDeepLinkTokenError("CLAIMS_MISMATCH", "token claims do not match")
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise EmployeeDeepLinkTokenError("MALFORMED_TOKEN", "token expiry is invalid")
    current_time = _to_utc(now or datetime.now(timezone.utc))
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    if current_time >= expires_at:
        raise EmployeeDeepLinkTokenError("TOKEN_EXPIRED", "token has expired")
    issued_at = payload.get("iat")
    return EmployeeDeepLinkClaims(
        scope=SCOPE,
        organization_id=organization_id,
        publication_id=publication_id,
        employee_id=employee_id,
        expires_at=expires_at,
        issued_at=(
            datetime.fromtimestamp(issued_at, tz=timezone.utc)
            if isinstance(issued_at, int)
            else None
        ),
    )


def is_employee_link_secret_strong(secret: str | None) -> bool:
    return bool(secret and len(secret) >= EMPLOYEE_LINK_SECRET_MIN_LENGTH)


def is_employee_link_secret_configured_but_weak(secret: str | None) -> bool:
    return bool(secret and not is_employee_link_secret_strong(secret))


def _sign(signing_input: str, secret: str) -> bytes:
    return hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _base64url_json(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _base64url_encode(encoded)


def _base64url_json_decode(value: str) -> dict[str, object]:
    decoded = _base64url_decode(value)
    parsed = json.loads(decoded.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("expected object")
    return parsed


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _timestamp(value: datetime) -> int:
    return int(_to_utc(value).timestamp())


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

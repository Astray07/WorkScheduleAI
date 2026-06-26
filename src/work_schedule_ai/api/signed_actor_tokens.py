from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json


SCOPE = "work_schedule_ai_actor"


@dataclass(frozen=True)
class SignedActorClaims:
    organization_id: str
    user_id: str
    expires_at: datetime
    issued_at: datetime | None


class SignedActorTokenError(ValueError):
    pass


def sign_actor_token(
    *,
    secret: str,
    organization_id: str,
    user_id: str,
    expires_at: datetime | None = None,
    issued_at: datetime | None = None,
) -> str:
    if not secret:
        raise ValueError("secret is required")
    now = _to_utc(issued_at or datetime.now(timezone.utc))
    expiry = _to_utc(expires_at or (now + timedelta(hours=1)))
    header = {"alg": "HS256", "typ": SCOPE, "v": 1}
    payload = {
        "scope": SCOPE,
        "organization_id": organization_id,
        "user_id": user_id,
        "iat": _timestamp(now),
        "exp": _timestamp(expiry),
    }
    encoded_header = _base64url_json(header)
    encoded_payload = _base64url_json(payload)
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = _sign(signing_input, secret)
    return f"{signing_input}.{_base64url_encode(signature)}"


def verify_actor_token(
    token: str,
    *,
    secret: str,
    organization_id: str,
    now: datetime | None = None,
) -> SignedActorClaims:
    if not secret:
        raise SignedActorTokenError("secret is required")
    parts = token.split(".")
    if len(parts) != 3:
        raise SignedActorTokenError("token must have three parts")
    encoded_header, encoded_payload, encoded_signature = parts
    signing_input = f"{encoded_header}.{encoded_payload}"
    try:
        supplied_signature = _base64url_decode(encoded_signature)
        header = _base64url_json_decode(encoded_header)
        payload = _base64url_json_decode(encoded_payload)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SignedActorTokenError("token is malformed") from exc
    expected_signature = _sign(signing_input, secret)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise SignedActorTokenError("token signature is invalid")
    if header.get("typ") != SCOPE or payload.get("scope") != SCOPE:
        raise SignedActorTokenError("token scope is invalid")
    if payload.get("organization_id") != organization_id:
        raise SignedActorTokenError("token organization does not match")
    user_id = payload.get("user_id")
    exp = payload.get("exp")
    if not isinstance(user_id, str) or not isinstance(exp, int):
        raise SignedActorTokenError("token claims are invalid")
    current_time = _to_utc(now or datetime.now(timezone.utc))
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    if current_time >= expires_at:
        raise SignedActorTokenError("token has expired")
    iat = payload.get("iat")
    return SignedActorClaims(
        organization_id=organization_id,
        user_id=user_id,
        expires_at=expires_at,
        issued_at=(
            datetime.fromtimestamp(iat, tz=timezone.utc)
            if isinstance(iat, int)
            else None
        ),
    )


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

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets


ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 210_000
MIN_ITERATIONS = 100_000
MAX_ITERATIONS = 600_000
DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$100000$dGVzdC1kdW1teS1zYWx0"
    "$bWlpYpfadSrvi4aSVUr4ko_YscUguKTJl5knN-hI22g="
)


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = _pbkdf2(password=password, salt=salt, iterations=iterations)
    return "$".join(
        [
            ALGORITHM,
            str(iterations),
            _b64_encode(salt),
            _b64_encode(digest),
        ]
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    parts = password_hash.split("$")
    if len(parts) != 4:
        return False
    algorithm, iterations_text, encoded_salt, encoded_digest = parts
    if algorithm != ALGORITHM:
        return False
    try:
        iterations = int(iterations_text)
        salt = _b64_decode(encoded_salt)
        expected_digest = _b64_decode(encoded_digest)
    except (binascii.Error, ValueError, TypeError):
        return False
    if iterations < MIN_ITERATIONS or iterations > MAX_ITERATIONS:
        return False
    if not salt or len(expected_digest) != hashlib.sha256().digest_size:
        return False
    supplied_digest = _pbkdf2(password=password, salt=salt, iterations=iterations)
    return hmac.compare_digest(supplied_digest, expected_digest)


def _pbkdf2(*, password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))

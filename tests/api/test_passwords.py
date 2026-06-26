from __future__ import annotations

from work_schedule_ai.api.passwords import hash_password, verify_password


def test_verify_password_rejects_malformed_hashes():
    assert verify_password("secret", "not-a-password-hash") is False
    assert verify_password("secret", "pbkdf2_sha256$100000$not-base64!!$also-bad") is False
    assert verify_password("secret", "unknown$100000$c2FsdA==$ZGlnZXN0") is False


def test_verify_password_rejects_unsafe_iteration_counts():
    safe_hash = hash_password("secret", iterations=100_000)
    _algorithm, _iterations, encoded_salt, encoded_digest = safe_hash.split("$")

    assert verify_password("secret", f"pbkdf2_sha256$0${encoded_salt}${encoded_digest}") is False
    assert verify_password("secret", f"pbkdf2_sha256$999999999${encoded_salt}${encoded_digest}") is False


def test_verify_password_accepts_valid_hash():
    password_hash = hash_password("secret", iterations=100_000)

    assert verify_password("secret", password_hash) is True
    assert verify_password("wrong", password_hash) is False

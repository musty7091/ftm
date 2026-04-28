from __future__ import annotations

import pytest

from app.models.enums import UserRole
from app.services.auth_service import (
    AuthServiceError,
    AuthenticatedUser,
    hash_password,
    verify_password,
)


def test_hash_password_returns_hash_different_from_plain_password() -> None:
    plain_password = "GuvenliSifre123"

    password_hash = hash_password(plain_password)

    assert isinstance(password_hash, str)
    assert password_hash != plain_password
    assert password_hash.startswith("$2")


def test_verify_password_accepts_correct_password() -> None:
    plain_password = "GuvenliSifre123"
    password_hash = hash_password(plain_password)

    assert verify_password(plain_password, password_hash) is True


def test_verify_password_rejects_wrong_password() -> None:
    plain_password = "GuvenliSifre123"
    wrong_password = "YanlisSifre123"
    password_hash = hash_password(plain_password)

    assert verify_password(wrong_password, password_hash) is False


def test_verify_password_returns_false_for_invalid_hash() -> None:
    assert verify_password("GuvenliSifre123", "bozuk-hash") is False


def test_hash_password_raises_for_empty_password() -> None:
    with pytest.raises(AuthServiceError):
        hash_password("")


def test_verify_password_raises_for_empty_password() -> None:
    password_hash = hash_password("GuvenliSifre123")

    with pytest.raises(AuthServiceError):
        verify_password("", password_hash)


def test_authenticated_user_dataclass_fields() -> None:
    user = AuthenticatedUser(
        id=1,
        username="admin",
        full_name="Sistem Yöneticisi",
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True,
    )

    assert user.id == 1
    assert user.username == "admin"
    assert user.full_name == "Sistem Yöneticisi"
    assert user.email == "admin@example.com"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
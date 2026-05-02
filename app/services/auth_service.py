from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import (
    PasswordValidationError,
    hash_password as core_hash_password,
    verify_password as core_verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.services.permission_service import (
    Permission,
    PermissionServiceError,
    has_permission,
    normalize_role,
    require_permission,
)


class AuthServiceError(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    full_name: str
    email: Optional[str]
    role: UserRole
    is_active: bool


def _clean_identifier(identifier: str) -> str:
    cleaned_identifier = (identifier or "").strip()

    if not cleaned_identifier:
        raise AuthServiceError("Kullanıcı adı / e-posta boş olamaz.")

    return cleaned_identifier


def _clean_password(password: str) -> str:
    cleaned_password = password or ""

    if not cleaned_password:
        raise AuthServiceError("Şifre boş olamaz.")

    return cleaned_password


def hash_password(password: str) -> str:
    cleaned_password = _clean_password(password)

    try:
        return core_hash_password(cleaned_password)
    except PasswordValidationError as exc:
        raise AuthServiceError(str(exc)) from exc


def verify_password(password: str, password_hash: str | bytes) -> bool:
    try:
        cleaned_password = _clean_password(password)
    except AuthServiceError:
        return False

    if isinstance(password_hash, bytes):
        cleaned_password_hash = password_hash.decode("utf-8", errors="ignore")
    else:
        cleaned_password_hash = str(password_hash or "")

    return core_verify_password(
        cleaned_password,
        cleaned_password_hash,
    )


def _user_to_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=normalize_role(user.role),
        is_active=user.is_active,
    )


def get_user_by_identifier(
    session: Session,
    *,
    identifier: str,
) -> Optional[User]:
    cleaned_identifier = _clean_identifier(identifier)
    lowered_identifier = cleaned_identifier.lower()

    statement = select(User).where(
        or_(
            func.lower(User.username) == lowered_identifier,
            func.lower(User.email) == lowered_identifier,
        )
    )

    return session.execute(statement).scalar_one_or_none()


def _write_login_success_log(
    session: Session,
    *,
    user: User,
) -> None:
    write_audit_log(
        session,
        user_id=user.id,
        action="LOGIN_SUCCESS",
        entity_type="User",
        entity_id=user.id,
        description=f"Kullanıcı giriş yaptı: {user.username}",
        old_values=None,
        new_values={
            "user_id": user.id,
            "username": user.username,
            "role": normalize_role(user.role).value,
        },
    )


def _write_login_failed_log(
    session: Session,
    *,
    identifier: str,
    user: Optional[User],
    reason: str,
) -> None:
    write_audit_log(
        session,
        user_id=user.id if user else None,
        action="LOGIN_FAILED",
        entity_type="User",
        entity_id=user.id if user else None,
        description=f"Kullanıcı giriş denemesi başarısız. Kullanıcı: {identifier} | Sebep: {reason}",
        old_values=None,
        new_values={
            "identifier": identifier,
            "user_id": user.id if user else None,
            "username": user.username if user else None,
            "reason": reason,
        },
    )


def authenticate_user(
    session: Session,
    *,
    identifier: str,
    password: str,
) -> AuthenticatedUser:
    cleaned_identifier = _clean_identifier(identifier)
    cleaned_password = _clean_password(password)

    user = get_user_by_identifier(
        session,
        identifier=cleaned_identifier,
    )

    if user is None:
        _write_login_failed_log(
            session,
            identifier=cleaned_identifier,
            user=None,
            reason="USER_NOT_FOUND",
        )
        raise AuthServiceError("Kullanıcı adı/e-posta veya şifre hatalı.")

    if not user.is_active:
        _write_login_failed_log(
            session,
            identifier=cleaned_identifier,
            user=user,
            reason="USER_PASSIVE",
        )
        raise AuthServiceError("Bu kullanıcı pasif durumda. Giriş yapılamaz.")

    password_is_valid = verify_password(
        cleaned_password,
        user.password_hash,
    )

    if not password_is_valid:
        _write_login_failed_log(
            session,
            identifier=cleaned_identifier,
            user=user,
            reason="INVALID_PASSWORD",
        )
        raise AuthServiceError("Kullanıcı adı/e-posta veya şifre hatalı.")

    _write_login_success_log(
        session,
        user=user,
    )

    return _user_to_authenticated_user(user)


def user_has_permission(
    user: AuthenticatedUser,
    permission: Permission | str,
) -> bool:
    return has_permission(user.role, permission)


def require_user_permission(
    user: AuthenticatedUser,
    permission: Permission | str,
) -> None:
    try:
        require_permission(user.role, permission)
    except PermissionServiceError as exc:
        raise AuthServiceError(str(exc)) from exc
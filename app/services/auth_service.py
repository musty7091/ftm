from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import (
    PasswordValidationError,
    hash_password as core_hash_password,
    verify_password as core_verify_password,
)
from app.models.audit_log import AuditLog
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


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 10
LOGIN_FAILED_QUERY_LIMIT = 500
LOGIN_LOCK_WINDOW = timedelta(minutes=LOGIN_LOCK_MINUTES)
COUNTABLE_FAILED_REASONS = {"USER_NOT_FOUND", "INVALID_PASSWORD"}


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


@dataclass(frozen=True)
class LoginLockStatus:
    is_locked: bool
    failed_count: int
    lock_until: Optional[datetime]
    remaining_minutes: int


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _datetime_to_text(value: Any) -> Optional[str]:
    normalized_value = _as_utc(value)

    if normalized_value is None:
        return None

    return normalized_value.isoformat(timespec="seconds")


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _same_text(left: Any, right: Any) -> bool:
    return str(left or "").strip().lower() == str(right or "").strip().lower()


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


def _audit_log_matches_login_identifier(
    log: AuditLog,
    *,
    identifier: str,
    user: Optional[User],
) -> bool:
    values = _safe_dict(log.new_values)

    if user is not None:
        if log.user_id == user.id or log.entity_id == user.id:
            return True

        if values.get("user_id") == user.id:
            return True

        if _same_text(values.get("username"), user.username):
            return True

        if user.email and _same_text(values.get("identifier"), user.email):
            return True

        return _same_text(values.get("identifier"), identifier)

    return _same_text(values.get("identifier"), identifier)


def _is_countable_failed_login(log: AuditLog) -> bool:
    values = _safe_dict(log.new_values)
    reason = str(values.get("reason") or "").strip()

    return reason in COUNTABLE_FAILED_REASONS


def _get_login_lock_status(
    session: Session,
    *,
    identifier: str,
    user: Optional[User],
) -> LoginLockStatus:
    now = _utc_now()
    window_start = now - LOGIN_LOCK_WINDOW

    statement = (
        select(AuditLog)
        .where(
            AuditLog.action == "LOGIN_FAILED",
            AuditLog.entity_type == "User",
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(LOGIN_FAILED_QUERY_LIMIT)
    )

    if user is not None:
        statement = statement.where(
            or_(
                AuditLog.user_id == user.id,
                AuditLog.entity_id == user.id,
            )
        )

    logs = session.execute(statement).scalars().all()

    failed_count = 0
    newest_failed_at: Optional[datetime] = None

    for log in logs:
        if not _is_countable_failed_login(log):
            continue

        if not _audit_log_matches_login_identifier(
            log,
            identifier=identifier,
            user=user,
        ):
            continue

        created_at = _as_utc(log.created_at)

        if created_at is None:
            continue

        if created_at < window_start:
            continue

        failed_count += 1

        if newest_failed_at is None or created_at > newest_failed_at:
            newest_failed_at = created_at

    if failed_count < MAX_FAILED_LOGIN_ATTEMPTS or newest_failed_at is None:
        return LoginLockStatus(
            is_locked=False,
            failed_count=failed_count,
            lock_until=None,
            remaining_minutes=0,
        )

    lock_until = newest_failed_at + LOGIN_LOCK_WINDOW

    if lock_until <= now:
        return LoginLockStatus(
            is_locked=False,
            failed_count=failed_count,
            lock_until=None,
            remaining_minutes=0,
        )

    remaining_seconds = max(1, int((lock_until - now).total_seconds()))
    remaining_minutes = max(1, ceil(remaining_seconds / 60))

    return LoginLockStatus(
        is_locked=True,
        failed_count=failed_count,
        lock_until=lock_until,
        remaining_minutes=remaining_minutes,
    )


def _lock_status_after_current_failure(
    *,
    previous_failed_count: int,
) -> LoginLockStatus:
    lock_until = _utc_now() + LOGIN_LOCK_WINDOW

    return LoginLockStatus(
        is_locked=True,
        failed_count=previous_failed_count + 1,
        lock_until=lock_until,
        remaining_minutes=LOGIN_LOCK_MINUTES,
    )


def _login_locked_message(lock_status: LoginLockStatus) -> str:
    remaining_minutes = max(1, lock_status.remaining_minutes)

    return (
        "Çok fazla hatalı giriş denemesi yapıldı. "
        f"Lütfen yaklaşık {remaining_minutes} dakika sonra tekrar deneyin."
    )


def _write_login_success_log(
    session: Session,
    *,
    user: User,
    previous_last_login_at: Any,
) -> None:
    write_audit_log(
        session,
        user_id=user.id,
        action="LOGIN_SUCCESS",
        entity_type="User",
        entity_id=user.id,
        description=f"Kullanıcı giriş yaptı: {user.username}",
        old_values={
            "last_login_at": _datetime_to_text(previous_last_login_at),
        },
        new_values={
            "user_id": user.id,
            "username": user.username,
            "role": normalize_role(user.role).value,
            "last_login_at": _datetime_to_text(user.last_login_at),
        },
    )


def _write_login_failed_log(
    session: Session,
    *,
    identifier: str,
    user: Optional[User],
    reason: str,
    extra_values: Optional[dict[str, Any]] = None,
) -> None:
    new_values = {
        "identifier": identifier,
        "user_id": user.id if user else None,
        "username": user.username if user else None,
        "reason": reason,
    }

    if extra_values:
        new_values.update(extra_values)

    write_audit_log(
        session,
        user_id=user.id if user else None,
        action="LOGIN_FAILED",
        entity_type="User",
        entity_id=user.id if user else None,
        description=f"Kullanıcı giriş denemesi başarısız. Kullanıcı: {identifier} | Sebep: {reason}",
        old_values=None,
        new_values=new_values,
    )


def _commit_failed_login_log(session: Session) -> None:
    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        raise AuthServiceError(
            "Giriş denemesi güvenlik günlüğüne kaydedilemedi. "
            "Lütfen uygulamayı yeniden başlatıp tekrar deneyin."
        ) from exc


def _raise_login_failed(
    session: Session,
    *,
    identifier: str,
    user: Optional[User],
    reason: str,
    message: str,
    extra_values: Optional[dict[str, Any]] = None,
) -> None:
    _write_login_failed_log(
        session,
        identifier=identifier,
        user=user,
        reason=reason,
        extra_values=extra_values,
    )
    _commit_failed_login_log(session)

    raise AuthServiceError(message)


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

    lock_status = _get_login_lock_status(
        session,
        identifier=cleaned_identifier,
        user=user,
    )

    if lock_status.is_locked:
        _raise_login_failed(
            session,
            identifier=cleaned_identifier,
            user=user,
            reason="LOGIN_LOCKED",
            message=_login_locked_message(lock_status),
            extra_values={
                "failed_count_in_window": lock_status.failed_count,
                "lock_minutes": LOGIN_LOCK_MINUTES,
                "lock_until": _datetime_to_text(lock_status.lock_until),
            },
        )

    if user is None:
        projected_lock_status = _lock_status_after_current_failure(
            previous_failed_count=lock_status.failed_count,
        )
        login_message = "Kullanıcı adı/e-posta veya şifre hatalı."
        extra_values = {
            "failed_count_in_window": lock_status.failed_count + 1,
            "max_failed_login_attempts": MAX_FAILED_LOGIN_ATTEMPTS,
            "lock_triggered": lock_status.failed_count + 1 >= MAX_FAILED_LOGIN_ATTEMPTS,
        }

        if lock_status.failed_count + 1 >= MAX_FAILED_LOGIN_ATTEMPTS:
            login_message = _login_locked_message(projected_lock_status)
            extra_values["lock_minutes"] = LOGIN_LOCK_MINUTES
            extra_values["lock_until"] = _datetime_to_text(projected_lock_status.lock_until)

        _raise_login_failed(
            session,
            identifier=cleaned_identifier,
            user=None,
            reason="USER_NOT_FOUND",
            message=login_message,
            extra_values=extra_values,
        )

    if not user.is_active:
        _raise_login_failed(
            session,
            identifier=cleaned_identifier,
            user=user,
            reason="USER_PASSIVE",
            message="Bu kullanıcı pasif durumda. Giriş yapılamaz.",
        )

    password_is_valid = verify_password(
        cleaned_password,
        user.password_hash,
    )

    if not password_is_valid:
        projected_lock_status = _lock_status_after_current_failure(
            previous_failed_count=lock_status.failed_count,
        )
        login_message = "Kullanıcı adı/e-posta veya şifre hatalı."
        extra_values = {
            "failed_count_in_window": lock_status.failed_count + 1,
            "max_failed_login_attempts": MAX_FAILED_LOGIN_ATTEMPTS,
            "lock_triggered": lock_status.failed_count + 1 >= MAX_FAILED_LOGIN_ATTEMPTS,
        }

        if lock_status.failed_count + 1 >= MAX_FAILED_LOGIN_ATTEMPTS:
            login_message = _login_locked_message(projected_lock_status)
            extra_values["lock_minutes"] = LOGIN_LOCK_MINUTES
            extra_values["lock_until"] = _datetime_to_text(projected_lock_status.lock_until)

        _raise_login_failed(
            session,
            identifier=cleaned_identifier,
            user=user,
            reason="INVALID_PASSWORD",
            message=login_message,
            extra_values=extra_values,
        )

    previous_last_login_at = user.last_login_at
    user.last_login_at = _utc_now()

    _write_login_success_log(
        session,
        user=user,
        previous_last_login_at=previous_last_login_at,
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

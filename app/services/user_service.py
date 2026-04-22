from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, normalize_username, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.services.permission_service import Permission, normalize_role, require_permission


class UserServiceError(ValueError):
    pass


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise UserServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    cleaned_value = (value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _validate_full_name(full_name: str) -> str:
    cleaned_full_name = _clean_required_text(full_name, "Ad soyad")

    if len(cleaned_full_name) < 3:
        raise UserServiceError("Ad soyad en az 3 karakter olmalıdır.")

    if len(cleaned_full_name) > 150:
        raise UserServiceError("Ad soyad en fazla 150 karakter olmalıdır.")

    return cleaned_full_name


def _validate_email(email: Optional[str]) -> Optional[str]:
    cleaned_email = _clean_optional_text(email)

    if cleaned_email is None:
        return None

    cleaned_email = cleaned_email.lower()

    if "@" not in cleaned_email or "." not in cleaned_email:
        raise UserServiceError("E-posta adresi geçerli görünmüyor.")

    if len(cleaned_email) > 150:
        raise UserServiceError("E-posta en fazla 150 karakter olmalıdır.")

    return cleaned_email


def _validate_password(password: str) -> str:
    cleaned_password = password or ""

    if len(cleaned_password) < 8:
        raise UserServiceError("Şifre en az 8 karakter olmalıdır.")

    has_letter = any(character.isalpha() for character in cleaned_password)
    has_digit = any(character.isdigit() for character in cleaned_password)

    if not has_letter or not has_digit:
        raise UserServiceError("Şifre en az bir harf ve en az bir rakam içermelidir.")

    return cleaned_password


def _role_value(role: UserRole | str) -> str:
    normalized_role = normalize_role(role)

    return normalized_role.value


def _user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": _role_value(user.role),
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
    }


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    normalized_username = normalize_username(username)

    statement = select(User).where(User.username == normalized_username)

    return session.execute(statement).scalar_one_or_none()


def get_user_by_email(session: Session, email: Optional[str]) -> Optional[User]:
    cleaned_email = _validate_email(email)

    if cleaned_email is None:
        return None

    statement = select(User).where(func.lower(User.email) == cleaned_email.lower())

    return session.execute(statement).scalar_one_or_none()


def get_user_by_username_or_email(
    session: Session,
    *,
    username: str,
    email: Optional[str],
) -> Optional[User]:
    normalized_username = normalize_username(username)
    cleaned_email = _validate_email(email)

    conditions = [
        User.username == normalized_username,
    ]

    if cleaned_email is not None:
        conditions.append(func.lower(User.email) == cleaned_email.lower())

    statement = select(User).where(or_(*conditions))

    return session.execute(statement).scalar_one_or_none()


def create_user(
    session: Session,
    *,
    username: str,
    full_name: str,
    email: Optional[str],
    password: str,
    role: UserRole | str,
    created_by_user_id: Optional[int],
    must_change_password: bool = False,
) -> User:
    normalized_username = normalize_username(username)
    cleaned_full_name = _validate_full_name(full_name)
    cleaned_email = _validate_email(email)
    cleaned_password = _validate_password(password)
    cleaned_role = normalize_role(role)

    existing_user = get_user_by_username_or_email(
        session,
        username=normalized_username,
        email=cleaned_email,
    )

    if existing_user is not None:
        if existing_user.username.lower() == normalized_username.lower():
            raise UserServiceError(f"Bu kullanıcı adı zaten kayıtlı: {normalized_username}")

        if cleaned_email and existing_user.email and existing_user.email.lower() == cleaned_email.lower():
            raise UserServiceError(f"Bu e-posta zaten kayıtlı: {cleaned_email}")

        raise UserServiceError("Aynı kullanıcı adı veya e-posta ile kullanıcı zaten var.")

    password_hash = hash_password(cleaned_password)

    user = User(
        username=normalized_username,
        full_name=cleaned_full_name,
        email=cleaned_email,
        password_hash=password_hash,
        role=cleaned_role,
        is_active=True,
        must_change_password=must_change_password,
    )

    session.add(user)
    session.flush()

    write_audit_log(
        session,
        user_id=created_by_user_id,
        action="USER_CREATED",
        entity_type="User",
        entity_id=user.id,
        description=f"Kullanıcı oluşturuldu: {user.username}",
        old_values=None,
        new_values=_user_to_dict(user),
    )

    return user


def create_user_by_admin(
    session: Session,
    *,
    acting_user: Any,
    username: str,
    full_name: str,
    email: Optional[str],
    password: str,
    role: UserRole | str,
    must_change_password: bool = True,
) -> User:
    require_permission(acting_user.role, Permission.USER_CREATE)

    return create_user(
        session,
        username=username,
        full_name=full_name,
        email=email,
        password=password,
        role=role,
        created_by_user_id=acting_user.id,
        must_change_password=must_change_password,
    )


def change_user_role(
    session: Session,
    *,
    acting_user: Any,
    target_user_id: int,
    new_role: UserRole | str,
) -> User:
    require_permission(acting_user.role, Permission.USER_UPDATE_ROLE)

    target_user = session.get(User, target_user_id)

    if target_user is None:
        raise UserServiceError(f"Kullanıcı bulunamadı. Kullanıcı ID: {target_user_id}")

    cleaned_new_role = normalize_role(new_role)

    old_values = _user_to_dict(target_user)

    target_user.role = cleaned_new_role

    session.flush()

    write_audit_log(
        session,
        user_id=acting_user.id,
        action="USER_ROLE_CHANGED",
        entity_type="User",
        entity_id=target_user.id,
        description=f"Kullanıcı rolü değiştirildi: {target_user.username} / Yeni rol: {cleaned_new_role.value}",
        old_values=old_values,
        new_values=_user_to_dict(target_user),
    )

    return target_user


def deactivate_user(
    session: Session,
    *,
    acting_user: Any,
    target_user_id: int,
) -> User:
    require_permission(acting_user.role, Permission.USER_DEACTIVATE)

    if acting_user.id == target_user_id:
        raise UserServiceError("Kendi kullanıcını pasifleştiremezsin.")

    target_user = session.get(User, target_user_id)

    if target_user is None:
        raise UserServiceError(f"Kullanıcı bulunamadı. Kullanıcı ID: {target_user_id}")

    if not target_user.is_active:
        raise UserServiceError("Bu kullanıcı zaten pasif.")

    old_values = _user_to_dict(target_user)

    target_user.is_active = False

    session.flush()

    write_audit_log(
        session,
        user_id=acting_user.id,
        action="USER_DEACTIVATED",
        entity_type="User",
        entity_id=target_user.id,
        description=f"Kullanıcı pasifleştirildi: {target_user.username}",
        old_values=old_values,
        new_values=_user_to_dict(target_user),
    )

    return target_user


def reactivate_user(
    session: Session,
    *,
    acting_user: Any,
    target_user_id: int,
) -> User:
    require_permission(acting_user.role, Permission.USER_REACTIVATE)

    target_user = session.get(User, target_user_id)

    if target_user is None:
        raise UserServiceError(f"Kullanıcı bulunamadı. Kullanıcı ID: {target_user_id}")

    if target_user.is_active:
        raise UserServiceError("Bu kullanıcı zaten aktif.")

    old_values = _user_to_dict(target_user)

    target_user.is_active = True

    session.flush()

    write_audit_log(
        session,
        user_id=acting_user.id,
        action="USER_REACTIVATED",
        entity_type="User",
        entity_id=target_user.id,
        description=f"Kullanıcı yeniden aktif edildi: {target_user.username}",
        old_values=old_values,
        new_values=_user_to_dict(target_user),
    )

    return target_user


def authenticate_user(session: Session, *, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(session, username)

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import settings
from app.db.session import Base, engine, session_scope
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.permission_service import Permission, get_permissions_for_role


class LocalDatabaseSetupServiceError(ValueError):
    pass


@dataclass(frozen=True)
class LocalDatabaseSetupStatus:
    database_engine: str
    database_url: str
    sqlite_database_path: str
    sqlite_parent_folder_exists: bool
    sqlite_database_file_exists: bool
    table_count: int
    missing_table_names: list[str]
    admin_user_exists: bool
    role_permission_row_count: int
    is_ready_for_login: bool


@dataclass(frozen=True)
class CreateInitialAdminResult:
    user_id: int
    username: str
    full_name: str
    email: str | None
    role: str
    must_change_password: bool


def ensure_sqlite_mode() -> None:
    if not settings.is_sqlite:
        raise LocalDatabaseSetupServiceError(
            "Bu işlem yalnızca DATABASE_ENGINE=sqlite modunda çalışır."
        )


def get_sqlite_database_path() -> Path:
    ensure_sqlite_mode()

    return settings.sqlite_database_path


def ensure_sqlite_parent_folder() -> Path:
    sqlite_database_path = get_sqlite_database_path()
    sqlite_database_path.parent.mkdir(parents=True, exist_ok=True)

    return sqlite_database_path.parent


def create_all_tables() -> None:
    ensure_sqlite_mode()
    ensure_sqlite_parent_folder()

    Base.metadata.create_all(bind=engine)


def get_expected_table_names() -> set[str]:
    return set(Base.metadata.tables.keys())


def get_created_table_names() -> set[str]:
    ensure_sqlite_mode()

    inspector = inspect(engine)

    return set(inspector.get_table_names())


def get_missing_table_names() -> list[str]:
    expected_table_names = get_expected_table_names()
    created_table_names = get_created_table_names()

    return sorted(expected_table_names.difference(created_table_names))


def ensure_default_role_permissions(session: Session) -> int:
    created_count = 0

    for role in UserRole:
        default_permissions = get_permissions_for_role(role)

        for permission in Permission:
            existing_row = session.execute(
                select(RolePermission).where(
                    RolePermission.role == role,
                    RolePermission.permission == permission.value,
                )
            ).scalar_one_or_none()

            expected_allowed = permission in default_permissions

            if existing_row is None:
                session.add(
                    RolePermission(
                        role=role,
                        permission=permission.value,
                        is_allowed=expected_allowed,
                    )
                )
                created_count += 1
                continue

            existing_row.is_allowed = expected_allowed

    session.flush()

    return created_count


def admin_user_exists(session: Session) -> bool:
    existing_admin_user = session.execute(
        select(User).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
    ).scalar_one_or_none()

    return existing_admin_user is not None


def get_role_permission_row_count(session: Session) -> int:
    rows = session.execute(select(RolePermission)).scalars().all()

    return len(rows)


def prepare_sqlite_database() -> LocalDatabaseSetupStatus:
    ensure_sqlite_mode()
    ensure_sqlite_parent_folder()
    create_all_tables()

    with session_scope() as session:
        ensure_default_role_permissions(session)
        current_admin_user_exists = admin_user_exists(session)
        role_permission_row_count = get_role_permission_row_count(session)

    return get_local_database_setup_status(
        admin_user_exists_value=current_admin_user_exists,
        role_permission_row_count_value=role_permission_row_count,
    )


def get_local_database_setup_status(
    *,
    admin_user_exists_value: bool | None = None,
    role_permission_row_count_value: int | None = None,
) -> LocalDatabaseSetupStatus:
    ensure_sqlite_mode()

    sqlite_database_path = settings.sqlite_database_path
    expected_table_names = get_expected_table_names()

    try:
        created_table_names = get_created_table_names()
    except Exception:
        created_table_names = set()

    missing_table_names = sorted(expected_table_names.difference(created_table_names))

    if admin_user_exists_value is None or role_permission_row_count_value is None:
        try:
            with session_scope() as session:
                if admin_user_exists_value is None:
                    admin_user_exists_value = admin_user_exists(session)

                if role_permission_row_count_value is None:
                    role_permission_row_count_value = get_role_permission_row_count(session)
        except Exception:
            admin_user_exists_value = False if admin_user_exists_value is None else admin_user_exists_value
            role_permission_row_count_value = (
                0
                if role_permission_row_count_value is None
                else role_permission_row_count_value
            )

    table_count = len(created_table_names)

    is_ready_for_login = (
        not missing_table_names
        and bool(admin_user_exists_value)
        and int(role_permission_row_count_value or 0) > 0
    )

    return LocalDatabaseSetupStatus(
        database_engine=settings.database_engine,
        database_url=settings.database_url,
        sqlite_database_path=str(sqlite_database_path),
        sqlite_parent_folder_exists=sqlite_database_path.parent.exists(),
        sqlite_database_file_exists=sqlite_database_path.exists(),
        table_count=table_count,
        missing_table_names=missing_table_names,
        admin_user_exists=bool(admin_user_exists_value),
        role_permission_row_count=int(role_permission_row_count_value or 0),
        is_ready_for_login=is_ready_for_login,
    )


def create_initial_admin_user(
    *,
    username: str,
    full_name: str,
    password: str,
    email: str | None = None,
    must_change_password: bool = False,
) -> CreateInitialAdminResult:
    ensure_sqlite_mode()

    cleaned_username = _clean_required_text(username, "Kullanıcı adı")
    cleaned_full_name = _clean_required_text(full_name, "Ad soyad")
    cleaned_password = _clean_required_text(password, "Şifre")
    cleaned_email = _clean_optional_text(email)

    if len(cleaned_password) < 6:
        raise LocalDatabaseSetupServiceError("ADMIN şifresi en az 6 karakter olmalıdır.")

    prepare_sqlite_database()

    with session_scope() as session:
        if admin_user_exists(session):
            raise LocalDatabaseSetupServiceError(
                "Aktif ADMIN kullanıcısı zaten var. İlk ADMIN tekrar oluşturulamaz."
            )

        existing_username = session.execute(
            select(User).where(User.username == cleaned_username)
        ).scalar_one_or_none()

        if existing_username is not None:
            raise LocalDatabaseSetupServiceError(
                "Bu kullanıcı adı zaten kullanılıyor."
            )

        if cleaned_email:
            existing_email = session.execute(
                select(User).where(User.email == cleaned_email)
            ).scalar_one_or_none()

            if existing_email is not None:
                raise LocalDatabaseSetupServiceError(
                    "Bu e-posta adresi zaten kullanılıyor."
                )

        admin_user = User(
            username=cleaned_username,
            full_name=cleaned_full_name,
            email=cleaned_email,
            password_hash=hash_password(cleaned_password),
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=must_change_password,
        )

        session.add(admin_user)
        session.flush()

        return CreateInitialAdminResult(
            user_id=int(admin_user.id),
            username=str(admin_user.username),
            full_name=str(admin_user.full_name),
            email=admin_user.email,
            role=UserRole.ADMIN.value,
            must_change_password=bool(admin_user.must_change_password),
        )


def _clean_required_text(value: Any, field_name: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise LocalDatabaseSetupServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Any) -> str | None:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return None

    return cleaned_value


__all__ = [
    "LocalDatabaseSetupServiceError",
    "LocalDatabaseSetupStatus",
    "CreateInitialAdminResult",
    "ensure_sqlite_mode",
    "get_sqlite_database_path",
    "ensure_sqlite_parent_folder",
    "create_all_tables",
    "get_expected_table_names",
    "get_created_table_names",
    "get_missing_table_names",
    "ensure_default_role_permissions",
    "admin_user_exists",
    "get_role_permission_row_count",
    "prepare_sqlite_database",
    "get_local_database_setup_status",
    "create_initial_admin_user",
]
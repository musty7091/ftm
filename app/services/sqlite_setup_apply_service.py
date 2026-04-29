from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.session import Base
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.models.user import User
from app.services.app_settings_service import update_app_settings
from app.services.auth_service import hash_password
from app.services.permission_service import Permission, get_permissions_for_role
from app.services.setup_service import (
    save_sqlite_setup_config,
    resolve_sqlite_database_path,
)


class SqliteSetupApplyServiceError(ValueError):
    pass


@dataclass(frozen=True)
class SqliteSetupApplyResult:
    sqlite_database_path: str
    table_count: int
    role_permission_row_count: int
    admin_user_id: int
    admin_username: str
    company_name: str
    setup_config_saved: bool
    app_settings_saved: bool


def apply_sqlite_initial_setup(
    *,
    sqlite_database_path: str,
    company_name: str,
    company_address: str,
    company_phone: str,
    company_email: str,
    admin_username: str,
    admin_full_name: str,
    admin_password: str,
    admin_email: str | None,
) -> SqliteSetupApplyResult:
    cleaned_sqlite_database_path = _clean_required_text(
        sqlite_database_path,
        "SQLite veritabanı yolu",
    )
    cleaned_company_name = _clean_required_text(
        company_name,
        "Firma adı",
    )
    cleaned_company_address = _clean_optional_text(company_address)
    cleaned_company_phone = _clean_optional_text(company_phone)
    cleaned_company_email = _clean_optional_text(company_email)
    cleaned_admin_username = _clean_required_text(
        admin_username,
        "ADMIN kullanıcı adı",
    )
    cleaned_admin_full_name = _clean_required_text(
        admin_full_name,
        "ADMIN ad soyad",
    )
    cleaned_admin_password = _clean_required_text(
        admin_password,
        "ADMIN şifre",
    )
    cleaned_admin_email = _clean_optional_text(admin_email)

    if len(cleaned_admin_password) < 6:
        raise SqliteSetupApplyServiceError(
            "ADMIN şifresi en az 6 karakter olmalıdır."
        )

    sqlite_path = resolve_sqlite_database_path(cleaned_sqlite_database_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{sqlite_path.as_posix()}",
        future=True,
        connect_args={
            "check_same_thread": False,
        },
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        try:
            role_permission_row_count = _ensure_default_role_permissions(session)
            admin_user = _create_initial_admin_user(
                session=session,
                username=cleaned_admin_username,
                full_name=cleaned_admin_full_name,
                password=cleaned_admin_password,
                email=cleaned_admin_email,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise

    inspector = inspect(engine)
    table_count = len(inspector.get_table_names())

    save_sqlite_setup_config(
        sqlite_database_path=cleaned_sqlite_database_path,
        setup_completed=True,
    )

    update_app_settings(
        company_name=cleaned_company_name,
        company_address=cleaned_company_address,
        company_phone=cleaned_company_phone,
        company_email=cleaned_company_email,
        backup_folder="backups",
        export_folder="exports",
        log_folder="logs",
        control_mail_enabled=True,
        control_mail_to="",
        report_footer_note="FTM tarafından oluşturulmuştur.",
    )

    return SqliteSetupApplyResult(
        sqlite_database_path=str(sqlite_path),
        table_count=table_count,
        role_permission_row_count=role_permission_row_count,
        admin_user_id=int(admin_user.id),
        admin_username=str(admin_user.username),
        company_name=cleaned_company_name,
        setup_config_saved=True,
        app_settings_saved=True,
    )


def _ensure_default_role_permissions(session: Session) -> int:
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
                continue

            existing_row.is_allowed = expected_allowed

    session.flush()

    rows = session.execute(select(RolePermission)).scalars().all()

    return len(rows)


def _create_initial_admin_user(
    *,
    session: Session,
    username: str,
    full_name: str,
    password: str,
    email: str | None,
) -> User:
    existing_admin_user = session.execute(
        select(User).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
    ).scalar_one_or_none()

    if existing_admin_user is not None:
        raise SqliteSetupApplyServiceError(
            "Aktif ADMIN kullanıcısı zaten var. İlk kurulum tekrar uygulanamaz."
        )

    existing_username = session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if existing_username is not None:
        raise SqliteSetupApplyServiceError(
            "Bu kullanıcı adı zaten kullanılıyor."
        )

    if email:
        existing_email = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

        if existing_email is not None:
            raise SqliteSetupApplyServiceError(
                "Bu e-posta adresi zaten kullanılıyor."
            )

    admin_user = User(
        username=username,
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
    )

    session.add(admin_user)
    session.flush()

    return admin_user


def _clean_required_text(value: Any, field_name: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise SqliteSetupApplyServiceError(f"{field_name} boş olamaz.")

    return cleaned_value


def _clean_optional_text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "SqliteSetupApplyServiceError",
    "SqliteSetupApplyResult",
    "apply_sqlite_initial_setup",
]
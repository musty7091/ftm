from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.session import Base
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.models.user import User
from app.services.app_settings_service import (
    app_settings_file_path,
    load_app_settings,
    update_app_settings,
)
from app.services.auth_service import AuthServiceError, hash_password
from app.services.permission_service import Permission, get_permissions_for_role
from app.services.setup_service import (
    load_setup_config,
    resolve_sqlite_database_path,
    save_sqlite_setup_config,
    setup_config_file_path,
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

    if cleaned_admin_password.lower() == cleaned_admin_username.lower():
        raise SqliteSetupApplyServiceError(
            "ADMIN şifresi kullanıcı adıyla aynı olamaz."
        )

    try:
        admin_password_hash = hash_password(cleaned_admin_password)
    except AuthServiceError as exc:
        raise SqliteSetupApplyServiceError(str(exc)) from exc

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

    try:
        Base.metadata.create_all(bind=engine)

        with SessionLocal() as session:
            try:
                role_permission_row_count = _ensure_default_role_permissions(session)
                admin_user = _create_initial_admin_user(
                    session=session,
                    username=cleaned_admin_username,
                    full_name=cleaned_admin_full_name,
                    password_hash=admin_password_hash,
                    email=cleaned_admin_email,
                )
                session.flush()

                admin_user_id = int(admin_user.id)
                admin_username_value = str(admin_user.username)

                session.commit()
            except Exception:
                session.rollback()
                raise

        _mark_fresh_sqlite_database_as_current_schema(engine=engine)

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

        _verify_sqlite_initial_setup(
            sqlite_path=sqlite_path,
            expected_sqlite_database_path=cleaned_sqlite_database_path,
            expected_company_name=cleaned_company_name,
            expected_company_address=cleaned_company_address,
            expected_company_phone=cleaned_company_phone,
            expected_company_email=cleaned_company_email,
            expected_admin_user_id=admin_user_id,
            expected_admin_username=admin_username_value,
            expected_admin_full_name=cleaned_admin_full_name,
            expected_admin_email=cleaned_admin_email,
            expected_role_permission_row_count=role_permission_row_count,
            session_factory=SessionLocal,
        )

        return SqliteSetupApplyResult(
            sqlite_database_path=str(sqlite_path),
            table_count=table_count,
            role_permission_row_count=role_permission_row_count,
            admin_user_id=admin_user_id,
            admin_username=admin_username_value,
            company_name=cleaned_company_name,
            setup_config_saved=True,
            app_settings_saved=True,
        )

    finally:
        engine.dispose()


def _mark_fresh_sqlite_database_as_current_schema(*, engine: Any) -> None:
    """
    Fresh install sırasında Base.metadata.create_all güncel modellerle temiz DB oluşturur.

    Bu durumda migration SQL'lerini tekrar çalıştırmak doğru değildir; çünkü güncel
    kolonlar zaten oluşmuştur. Bu yardımcı fonksiyon, yeni oluşturulan temiz DB'yi
    migration sistemi açısından güncel kabul edilecek şekilde işaretler:

    - schema_migrations tablosunu oluşturur.
    - Mevcut bütün migration tanımlarını başarılı uygulanmış gibi kaydeder.
    - PRAGMA user_version değerini CURRENT_SCHEMA_VERSION seviyesine getirir.
    """

    try:
        from app.services.database_migration_service import (
            CURRENT_SCHEMA_VERSION,
            MIGRATIONS,
            MIGRATION_TRACKING_TABLE,
        )

        applied_at = datetime.now().isoformat(timespec="seconds")

        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.exec_driver_sql("PRAGMA busy_timeout = 10000")

            connection.exec_driver_sql(
                f"""
                CREATE TABLE IF NOT EXISTS {MIGRATION_TRACKING_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_id TEXT NOT NULL UNIQUE,
                    migration_name TEXT NOT NULL,
                    target_version INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TEXT NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_message TEXT
                )
                """
            )

            for migration in MIGRATIONS:
                connection.exec_driver_sql(
                    f"""
                    INSERT OR REPLACE INTO {MIGRATION_TRACKING_TABLE} (
                        migration_id,
                        migration_name,
                        target_version,
                        checksum,
                        applied_at,
                        execution_time_ms,
                        success,
                        error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        migration.migration_id,
                        migration.name,
                        migration.target_version,
                        migration.checksum,
                        applied_at,
                        0,
                        1,
                        None,
                    ),
                )

            connection.exec_driver_sql(
                f"PRAGMA user_version = {int(CURRENT_SCHEMA_VERSION)}"
            )

    except Exception as exc:
        raise SqliteSetupApplyServiceError(
            "Fresh install veritabanı migration takip bilgisi işaretlenemedi. "
            "Veritabanı oluşturuldu ancak schema versiyonu güncel olarak kaydedilemedi. "
            f"Hata: {exc}"
        ) from exc


def _verify_sqlite_initial_setup(
    *,
    sqlite_path: Path,
    expected_sqlite_database_path: str,
    expected_company_name: str,
    expected_company_address: str,
    expected_company_phone: str,
    expected_company_email: str,
    expected_admin_user_id: int,
    expected_admin_username: str,
    expected_admin_full_name: str,
    expected_admin_email: str,
    expected_role_permission_row_count: int,
    session_factory: sessionmaker[Session],
) -> None:
    if not sqlite_path.exists():
        raise SqliteSetupApplyServiceError(
            f"SQLite veritabanı dosyası oluşturulamadı: {sqlite_path}"
        )

    if not sqlite_path.is_file():
        raise SqliteSetupApplyServiceError(
            f"SQLite veritabanı yolu dosya değil: {sqlite_path}"
        )

    if sqlite_path.stat().st_size <= 0:
        raise SqliteSetupApplyServiceError(
            f"SQLite veritabanı dosyası boş görünüyor: {sqlite_path}"
        )

    _verify_fresh_sqlite_database_schema_marker(sqlite_path=sqlite_path)

    current_setup_config_file = setup_config_file_path()

    if not current_setup_config_file.exists():
        raise SqliteSetupApplyServiceError(
            f"Kurulum ayar dosyası oluşturulamadı: {current_setup_config_file}"
        )

    setup_config = load_setup_config()

    if not setup_config.setup_completed:
        raise SqliteSetupApplyServiceError(
            "Kurulum ayar dosyasında setup_completed=true değeri doğrulanamadı."
        )

    if setup_config.database_engine != "sqlite":
        raise SqliteSetupApplyServiceError(
            "Kurulum ayar dosyasında veritabanı tipi SQLite olarak doğrulanamadı."
        )

    if setup_config.sqlite_database_path != expected_sqlite_database_path:
        raise SqliteSetupApplyServiceError(
            "Kurulum ayar dosyasındaki SQLite yolu beklenen değerle uyuşmuyor.\n\n"
            f"Beklenen: {expected_sqlite_database_path}\n"
            f"Bulunan: {setup_config.sqlite_database_path}"
        )

    resolved_config_sqlite_path = resolve_sqlite_database_path(
        setup_config.sqlite_database_path
    )

    if resolved_config_sqlite_path != sqlite_path:
        raise SqliteSetupApplyServiceError(
            "Kurulum ayar dosyasındaki SQLite yolu gerçek veritabanı dosyasıyla uyuşmüyor.\n\n"
            f"Beklenen: {sqlite_path}\n"
            f"Bulunan: {resolved_config_sqlite_path}"
        )

    current_app_settings_file = app_settings_file_path()

    if not current_app_settings_file.exists():
        raise SqliteSetupApplyServiceError(
            f"Uygulama ayar dosyası oluşturulamadı: {current_app_settings_file}"
        )

    app_settings = load_app_settings()

    if app_settings.company_name != expected_company_name:
        raise SqliteSetupApplyServiceError(
            "Uygulama ayar dosyasındaki firma adı beklenen değerle uyuşmüyor."
        )

    if app_settings.company_address != expected_company_address:
        raise SqliteSetupApplyServiceError(
            "Uygulama ayar dosyasındaki firma adresi beklenen değerle uyuşmüyor."
        )

    if app_settings.company_phone != expected_company_phone:
        raise SqliteSetupApplyServiceError(
            "Uygulama ayar dosyasındaki firma telefonu beklenen değerle uyuşmüyor."
        )

    if app_settings.company_email != expected_company_email:
        raise SqliteSetupApplyServiceError(
            "Uygulama ayar dosyasındaki firma e-posta adresi beklenen değerle uyuşmüyor."
        )

    with session_factory() as session:
        admin_user = session.execute(
            select(User).where(User.id == expected_admin_user_id)
        ).scalar_one_or_none()

        if admin_user is None:
            raise SqliteSetupApplyServiceError(
                "İlk ADMIN kullanıcısı veritabanında doğrulanamadı."
            )

        if admin_user.username != expected_admin_username:
            raise SqliteSetupApplyServiceError(
                "İlk ADMIN kullanıcı adı beklenen değerle uyuşmüyor."
            )

        if admin_user.full_name != expected_admin_full_name:
            raise SqliteSetupApplyServiceError(
                "İlk ADMIN ad soyad bilgisi beklenen değerle uyuşmüyor."
            )

        if admin_user.email != (expected_admin_email or None):
            raise SqliteSetupApplyServiceError(
                "İlk ADMIN e-posta bilgisi beklenen değerle uyuşmüyor."
            )

        if admin_user.role != UserRole.ADMIN:
            raise SqliteSetupApplyServiceError(
                "İlk ADMIN kullanıcısının rolü ADMIN olarak doğrulanamadı."
            )

        if not admin_user.is_active:
            raise SqliteSetupApplyServiceError(
                "İlk ADMIN kullanıcısı aktif olarak doğrulanamadı."
            )

        active_admin_count = session.execute(
            select(User).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        ).scalars().all()

        if len(active_admin_count) != 1:
            raise SqliteSetupApplyServiceError(
                "İlk kurulum sonrası aktif ADMIN kullanıcı sayısı 1 olmalıdır."
            )

        role_permission_rows = session.execute(
            select(RolePermission)
        ).scalars().all()

        actual_role_permission_row_count = len(role_permission_rows)

        if actual_role_permission_row_count != expected_role_permission_row_count:
            raise SqliteSetupApplyServiceError(
                "Rol/yetki satır sayısı beklenen değerle uyuşmuyor.\n\n"
                f"Beklenen: {expected_role_permission_row_count}\n"
                f"Bulunan: {actual_role_permission_row_count}"
            )

        minimum_required_role_permission_count = len(UserRole) * len(Permission)

        if actual_role_permission_row_count < minimum_required_role_permission_count:
            raise SqliteSetupApplyServiceError(
                "Rol/yetki kurulumu eksik görünüyor.\n\n"
                f"Beklenen minimum: {minimum_required_role_permission_count}\n"
                f"Bulunan: {actual_role_permission_row_count}"
            )

        admin_allowed_permission_rows = [
            row
            for row in role_permission_rows
            if row.role == UserRole.ADMIN and row.is_allowed
        ]

        if len(admin_allowed_permission_rows) != len(Permission):
            raise SqliteSetupApplyServiceError(
                "ADMIN rolünün tüm yetkilere sahip olduğu doğrulanamadı."
            )


def _verify_fresh_sqlite_database_schema_marker(*, sqlite_path: Path) -> None:
    try:
        from app.services.database_migration_service import (
            CURRENT_SCHEMA_VERSION,
            MIGRATIONS,
            MIGRATION_TRACKING_TABLE,
        )

        engine = create_engine(
            f"sqlite:///{sqlite_path.as_posix()}",
            future=True,
            connect_args={
                "check_same_thread": False,
            },
        )

        try:
            with engine.connect() as connection:
                table_exists = connection.exec_driver_sql(
                    """
                    SELECT COUNT(*)
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = ?
                    """,
                    (MIGRATION_TRACKING_TABLE,),
                ).scalar_one()

                if int(table_exists or 0) != 1:
                    raise SqliteSetupApplyServiceError(
                        f"{MIGRATION_TRACKING_TABLE} tablosu oluşturulamadı."
                    )

                user_version = connection.exec_driver_sql(
                    "PRAGMA user_version"
                ).scalar_one()

                if int(user_version or 0) != int(CURRENT_SCHEMA_VERSION):
                    raise SqliteSetupApplyServiceError(
                        "SQLite user_version beklenen schema seviyesiyle uyuşmuyor.\n\n"
                        f"Beklenen: {CURRENT_SCHEMA_VERSION}\n"
                        f"Bulunan: {user_version}"
                    )

                migration_count = connection.exec_driver_sql(
                    f"""
                    SELECT COUNT(*)
                    FROM {MIGRATION_TRACKING_TABLE}
                    WHERE success = 1
                    """
                ).scalar_one()

                if int(migration_count or 0) != len(MIGRATIONS):
                    raise SqliteSetupApplyServiceError(
                        "Fresh install migration takip kayıt sayısı beklenen değerle uyuşmuyor.\n\n"
                        f"Beklenen: {len(MIGRATIONS)}\n"
                        f"Bulunan: {migration_count}"
                    )

        finally:
            engine.dispose()

    except SqliteSetupApplyServiceError:
        raise
    except Exception as exc:
        raise SqliteSetupApplyServiceError(
            "Fresh install veritabanı schema marker doğrulaması yapılamadı. "
            f"Hata: {exc}"
        ) from exc


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
    password_hash: str,
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
        password_hash=password_hash,
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
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import settings
from app.db.session import engine
from app.services.backup_service import BackupServiceError, create_database_backup


class DatabaseMigrationServiceError(RuntimeError):
    pass


MIGRATION_TRACKING_TABLE = "schema_migrations"
CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DatabaseMigration:
    migration_id: str
    name: str
    target_version: int
    statements: tuple[str, ...]
    description: str = ""

    @property
    def checksum(self) -> str:
        checksum_source = "\n".join(
            [
                self.migration_id,
                self.name,
                str(self.target_version),
                self.description,
                *self.statements,
            ]
        )

        return hashlib.sha256(checksum_source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AppliedMigrationInfo:
    migration_id: str
    migration_name: str
    target_version: int
    checksum: str
    applied_at: str
    execution_time_ms: int
    success: bool
    error_message: str | None


@dataclass(frozen=True)
class DatabaseMigrationStatus:
    database_engine: str
    database_path: str
    database_file_exists: bool
    tracking_table_exists: bool
    current_user_version: int
    expected_schema_version: int
    applied_migration_count: int
    pending_migration_ids: list[str]
    is_up_to_date: bool


@dataclass(frozen=True)
class DatabaseMigrationResult:
    database_path: str
    backup_file: str | None
    applied_migration_ids: list[str]
    current_user_version: int
    expected_schema_version: int
    message: str


MIGRATIONS: tuple[DatabaseMigration, ...] = (
    DatabaseMigration(
        migration_id="20260502_0001_baseline_schema_tracking",
        name="Baseline schema tracking",
        target_version=1,
        statements=(
            "SELECT 1",
        ),
        description=(
            "FTM SQLite veritabanı için migration takip sisteminin başlangıç kaydı."
        ),
    ),
)


def ensure_sqlite_mode() -> None:
    if not settings.is_sqlite:
        raise DatabaseMigrationServiceError(
            "Migration sistemi şu anda yalnızca SQLite Local modu için aktiftir."
        )


def get_database_migration_status() -> DatabaseMigrationStatus:
    ensure_sqlite_mode()
    _validate_migration_definitions()

    database_path = _sqlite_database_path()
    expected_schema_version = _expected_schema_version()

    if not database_path.exists() or not database_path.is_file():
        return DatabaseMigrationStatus(
            database_engine=settings.database_engine,
            database_path=str(database_path),
            database_file_exists=False,
            tracking_table_exists=False,
            current_user_version=0,
            expected_schema_version=expected_schema_version,
            applied_migration_count=0,
            pending_migration_ids=[],
            is_up_to_date=False,
        )

    with engine.connect() as connection:
        current_user_version = _get_sqlite_user_version(connection)
        tracking_table_exists = _tracking_table_exists(connection)

        if tracking_table_exists:
            applied_migrations = _get_applied_migrations(connection)
            _verify_applied_migration_checksums(applied_migrations)
        else:
            applied_migrations = []

        pending_migrations = _get_pending_migrations_from_applied(applied_migrations)

    pending_migration_ids = [
        migration.migration_id
        for migration in pending_migrations
    ]

    is_up_to_date = (
        tracking_table_exists
        and not pending_migration_ids
        and current_user_version >= expected_schema_version
    )

    return DatabaseMigrationStatus(
        database_engine=settings.database_engine,
        database_path=str(database_path),
        database_file_exists=True,
        tracking_table_exists=tracking_table_exists,
        current_user_version=current_user_version,
        expected_schema_version=expected_schema_version,
        applied_migration_count=len(applied_migrations),
        pending_migration_ids=pending_migration_ids,
        is_up_to_date=is_up_to_date,
    )


def run_database_migrations(*, require_backup: bool = True) -> DatabaseMigrationResult:
    ensure_sqlite_mode()
    _validate_migration_definitions()

    database_path = _sqlite_database_path()

    if not database_path.exists() or not database_path.is_file():
        raise DatabaseMigrationServiceError(
            f"Migration çalıştırılamadı. SQLite veritabanı dosyası bulunamadı:\n{database_path}"
        )

    status_before = get_database_migration_status()

    if status_before.is_up_to_date:
        return DatabaseMigrationResult(
            database_path=str(database_path),
            backup_file=None,
            applied_migration_ids=[],
            current_user_version=status_before.current_user_version,
            expected_schema_version=status_before.expected_schema_version,
            message="Veritabanı şeması güncel. Çalıştırılacak migration yok.",
        )

    backup_file_text: str | None = None

    if require_backup:
        backup_file_text = _create_safe_backup_before_migration()

    applied_migration_ids: list[str] = []

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.exec_driver_sql("PRAGMA busy_timeout = 10000")

            _ensure_tracking_table(connection)

            applied_migrations = _get_applied_migrations(connection)
            _verify_applied_migration_checksums(applied_migrations)

            pending_migrations = _get_pending_migrations_from_applied(applied_migrations)

            for migration in pending_migrations:
                _apply_single_migration(
                    connection=connection,
                    migration=migration,
                )
                applied_migration_ids.append(migration.migration_id)
                _set_sqlite_user_version(connection, migration.target_version)

        status_after = get_database_migration_status()

        return DatabaseMigrationResult(
            database_path=str(database_path),
            backup_file=backup_file_text,
            applied_migration_ids=applied_migration_ids,
            current_user_version=status_after.current_user_version,
            expected_schema_version=status_after.expected_schema_version,
            message=(
                "Migration işlemi başarıyla tamamlandı. "
                f"Uygulanan migration sayısı: {len(applied_migration_ids)}"
            ),
        )

    except Exception as exc:
        backup_note = ""

        if backup_file_text:
            backup_note = f"\n\nMigration öncesi alınan güvenli yedek:\n{backup_file_text}"

        raise DatabaseMigrationServiceError(
            "Migration işlemi başarısız oldu. "
            "Veritabanı güncellemesi tamamlanamadı."
            f"{backup_note}\n\nHata:\n{exc}"
        ) from exc


def _sqlite_database_path() -> Path:
    sqlite_path = settings.sqlite_database_path

    if sqlite_path.is_absolute():
        return sqlite_path

    return Path.cwd() / sqlite_path


def _expected_schema_version() -> int:
    if not MIGRATIONS:
        return 0

    return max(migration.target_version for migration in MIGRATIONS)


def _validate_migration_definitions() -> None:
    migration_ids: set[str] = set()
    target_versions: set[int] = set()
    previous_target_version = 0

    for migration in MIGRATIONS:
        migration_id = str(migration.migration_id or "").strip()
        migration_name = str(migration.name or "").strip()

        if not migration_id:
            raise DatabaseMigrationServiceError("Migration ID boş olamaz.")

        if not migration_name:
            raise DatabaseMigrationServiceError(
                f"Migration adı boş olamaz. Migration ID: {migration_id}"
            )

        if migration_id in migration_ids:
            raise DatabaseMigrationServiceError(
                f"Tekrarlanan migration ID bulundu: {migration_id}"
            )

        if migration.target_version <= 0:
            raise DatabaseMigrationServiceError(
                f"Migration target_version sıfırdan büyük olmalıdır: {migration_id}"
            )

        if migration.target_version in target_versions:
            raise DatabaseMigrationServiceError(
                f"Tekrarlanan migration target_version bulundu: {migration.target_version}"
            )

        if migration.target_version <= previous_target_version:
            raise DatabaseMigrationServiceError(
                "Migration listesi target_version değerine göre küçükten büyüğe sıralı olmalıdır."
            )

        migration_ids.add(migration_id)
        target_versions.add(migration.target_version)
        previous_target_version = migration.target_version


def _tracking_table_exists(connection: Any) -> bool:
    row = connection.exec_driver_sql(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (MIGRATION_TRACKING_TABLE,),
    ).first()

    return row is not None


def _ensure_tracking_table(connection: Any) -> None:
    connection.exec_driver_sql(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TRACKING_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_id TEXT NOT NULL UNIQUE,
            migration_name TEXT NOT NULL,
            target_version INTEGER NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            execution_time_ms INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT
        )
        """
    )

    connection.exec_driver_sql(
        f"""
        CREATE INDEX IF NOT EXISTS ix_{MIGRATION_TRACKING_TABLE}_migration_id
        ON {MIGRATION_TRACKING_TABLE} (migration_id)
        """
    )

    connection.exec_driver_sql(
        f"""
        CREATE INDEX IF NOT EXISTS ix_{MIGRATION_TRACKING_TABLE}_target_version
        ON {MIGRATION_TRACKING_TABLE} (target_version)
        """
    )


def _get_sqlite_user_version(connection: Any) -> int:
    row = connection.exec_driver_sql("PRAGMA user_version").first()

    if row is None:
        return 0

    try:
        return int(row[0] or 0)
    except (TypeError, ValueError):
        return 0


def _set_sqlite_user_version(connection: Any, version: int) -> None:
    clean_version = int(version)

    if clean_version < 0:
        raise DatabaseMigrationServiceError("SQLite user_version negatif olamaz.")

    connection.exec_driver_sql(f"PRAGMA user_version = {clean_version}")


def _get_applied_migrations(connection: Any) -> list[AppliedMigrationInfo]:
    if not _tracking_table_exists(connection):
        return []

    rows = connection.exec_driver_sql(
        f"""
        SELECT
            migration_id,
            migration_name,
            target_version,
            checksum,
            applied_at,
            execution_time_ms,
            success,
            error_message
        FROM {MIGRATION_TRACKING_TABLE}
        ORDER BY target_version ASC, id ASC
        """
    ).mappings().all()

    result: list[AppliedMigrationInfo] = []

    for row in rows:
        result.append(
            AppliedMigrationInfo(
                migration_id=str(row["migration_id"]),
                migration_name=str(row["migration_name"]),
                target_version=int(row["target_version"]),
                checksum=str(row["checksum"]),
                applied_at=str(row["applied_at"]),
                execution_time_ms=int(row["execution_time_ms"] or 0),
                success=bool(row["success"]),
                error_message=(
                    None
                    if row["error_message"] is None
                    else str(row["error_message"])
                ),
            )
        )

    return result


def _verify_applied_migration_checksums(
    applied_migrations: list[AppliedMigrationInfo],
) -> None:
    migration_map = {
        migration.migration_id: migration
        for migration in MIGRATIONS
    }

    for applied_migration in applied_migrations:
        expected_migration = migration_map.get(applied_migration.migration_id)

        if expected_migration is None:
            continue

        if applied_migration.checksum != expected_migration.checksum:
            raise DatabaseMigrationServiceError(
                "Daha önce uygulanmış bir migration dosyası değiştirilmiş görünüyor.\n\n"
                f"Migration ID: {applied_migration.migration_id}\n"
                "Bu güvenlik nedeniyle durduruldu."
            )


def _get_pending_migrations_from_applied(
    applied_migrations: list[AppliedMigrationInfo],
) -> list[DatabaseMigration]:
    applied_ids = {
        migration.migration_id
        for migration in applied_migrations
        if migration.success
    }

    return [
        migration
        for migration in MIGRATIONS
        if migration.migration_id not in applied_ids
    ]


def _apply_single_migration(
    *,
    connection: Any,
    migration: DatabaseMigration,
) -> None:
    started_at = perf_counter()

    for statement in migration.statements:
        clean_statement = str(statement or "").strip()

        if not clean_statement:
            continue

        connection.exec_driver_sql(clean_statement)

    execution_time_ms = int((perf_counter() - started_at) * 1000)

    _record_successful_migration(
        connection=connection,
        migration=migration,
        execution_time_ms=execution_time_ms,
    )


def _record_successful_migration(
    *,
    connection: Any,
    migration: DatabaseMigration,
    execution_time_ms: int,
) -> None:
    connection.exec_driver_sql(
        f"""
        INSERT INTO {MIGRATION_TRACKING_TABLE} (
            migration_id,
            migration_name,
            target_version,
            checksum,
            applied_at,
            execution_time_ms,
            success,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
        """,
        (
            migration.migration_id,
            migration.name,
            migration.target_version,
            migration.checksum,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            int(execution_time_ms),
        ),
    )


def _create_safe_backup_before_migration() -> str:
    try:
        backup_result = create_database_backup()

    except BackupServiceError as exc:
        raise DatabaseMigrationServiceError(
            f"Migration öncesi otomatik yedek alınamadı:\n{exc}"
        ) from exc

    except Exception as exc:
        raise DatabaseMigrationServiceError(
            f"Migration öncesi otomatik yedek alınırken beklenmeyen hata oluştu:\n{exc}"
        ) from exc

    if not backup_result.success or backup_result.backup_file is None:
        raise DatabaseMigrationServiceError(
            "Migration öncesi otomatik yedek alınamadı. "
            f"Yedekleme mesajı: {backup_result.message}"
        )

    return str(backup_result.backup_file)


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MIGRATION_TRACKING_TABLE",
    "DatabaseMigration",
    "AppliedMigrationInfo",
    "DatabaseMigrationStatus",
    "DatabaseMigrationResult",
    "DatabaseMigrationServiceError",
    "ensure_sqlite_mode",
    "get_database_migration_status",
    "run_database_migrations",
]
from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.runtime_paths import ensure_runtime_folders
from app.services.backup_service import (
    format_backup_size,
    list_database_backups,
)
from app.services.backup_standard_service import (
    BACKUP_STANDARD_MIN_SCHEMA_VERSION,
    BACKUP_STANDARD_SCHEMA_MIGRATIONS_TABLE,
    validate_backup_against_standard,
)


SQLITE_RESTORE_TEST_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
SQLITE_RESTORE_TEST_FILE_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
SQLITE_RESTORE_TEST_FOLDER_NAME = "restore_tests"
SQLITE_RESTORE_TEST_LOG_FILE_NAME = "restore_test_log.txt"
SQLITE_RESTORE_TEST_KEEP_LATEST_FILES = 10


class SQLiteRestoreTestServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SQLiteRestoreTestResult:
    backup_file: Path
    test_database_file: Path
    backup_size_bytes: int
    backup_size_text: str
    test_database_size_bytes: int
    test_database_size_text: str
    backup_sha256: str
    sqlite_quick_check: str
    sqlite_user_version: int
    sqlite_table_count: int
    has_schema_migrations_table: bool
    started_at: str
    finished_at: str
    success: bool
    message: str


def run_latest_sqlite_restore_test() -> SQLiteRestoreTestResult:
    backup_files = list_database_backups()

    if not backup_files:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore testi için yedek dosyası bulunamadı. Önce yeni bir yedek alın."
        )

    latest_backup = backup_files[0]

    return run_sqlite_restore_test(latest_backup.file_path)


def run_sqlite_restore_test(
    backup_file: str | Path,
) -> SQLiteRestoreTestResult:
    """
    SQLite yedeğini aktif veritabanına dokunmadan test eder.

    Bu fonksiyon gerçek restore yapmaz.
    Yedek dosyasını ayrı bir test dosyasına kopyalar ve test kopyasını doğrular.
    """

    _ensure_sqlite_mode()

    started_at_dt = datetime.now()
    started_at = started_at_dt.strftime(SQLITE_RESTORE_TEST_DATE_FORMAT)

    backup_path = Path(backup_file)

    validation_result = validate_backup_against_standard(
        backup_path,
        require_metadata=True,
        require_schema_migrations=True,
        min_schema_version=BACKUP_STANDARD_MIN_SCHEMA_VERSION,
    )

    if not validation_result.success:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore testi başlatılamadı. Seçilen yedek FTM güvenli yedek "
            "standardını karşılamıyor."
        )

    restore_test_folder = _restore_test_folder()
    restore_test_folder.mkdir(parents=True, exist_ok=True)

    test_database_file = _build_restore_test_database_file(
        restore_test_folder=restore_test_folder,
        backup_file=backup_path,
    )

    try:
        shutil.copy2(backup_path, test_database_file)

    except OSError as exc:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore test dosyası oluşturulamadı.\n\n"
            f"Kaynak yedek:\n{backup_path}\n\n"
            f"Test dosyası:\n{test_database_file}"
        ) from exc

    inspection_result = _inspect_sqlite_test_database(test_database_file)

    quick_check = inspection_result["quick_check"]
    user_version = inspection_result["user_version"]
    table_count = inspection_result["table_count"]
    has_schema_migrations = inspection_result["has_schema_migrations_table"]

    if quick_check.lower() != "ok":
        raise SQLiteRestoreTestServiceError(
            f"SQLite restore test quick_check başarısız: {quick_check}"
        )

    if user_version < BACKUP_STANDARD_MIN_SCHEMA_VERSION:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore test user_version beklenen seviyenin altında. "
            f"Mevcut: {user_version}, Minimum: {BACKUP_STANDARD_MIN_SCHEMA_VERSION}"
        )

    if table_count <= 0:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore test veritabanında kullanıcı tablosu bulunamadı."
        )

    if not has_schema_migrations:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore test veritabanında schema_migrations tablosu bulunamadı."
        )

    finished_at_dt = datetime.now()
    finished_at = finished_at_dt.strftime(SQLITE_RESTORE_TEST_DATE_FORMAT)

    test_database_size_bytes = test_database_file.stat().st_size

    result = SQLiteRestoreTestResult(
        backup_file=backup_path,
        test_database_file=test_database_file,
        backup_size_bytes=validation_result.backup_size_bytes,
        backup_size_text=validation_result.backup_size_text,
        test_database_size_bytes=test_database_size_bytes,
        test_database_size_text=format_backup_size(test_database_size_bytes),
        backup_sha256=validation_result.sha256,
        sqlite_quick_check=quick_check,
        sqlite_user_version=user_version,
        sqlite_table_count=table_count,
        has_schema_migrations_table=has_schema_migrations,
        started_at=started_at,
        finished_at=finished_at,
        success=True,
        message=(
            "SQLite restore testi başarıyla tamamlandı. "
            "Aktif veritabanına dokunulmadı."
        ),
    )

    _write_restore_test_log(_build_restore_test_log_line(result))
    _cleanup_old_restore_test_files(restore_test_folder)

    return result


def get_sqlite_restore_test_summary_lines(
    result: SQLiteRestoreTestResult,
) -> list[str]:
    return [
        "FTM SQLite Restore Test Sonucu",
        "-" * 48,
        f"Başlangıç: {result.started_at}",
        f"Bitiş: {result.finished_at}",
        f"Test edilen yedek: {result.backup_file}",
        f"Oluşturulan test veritabanı: {result.test_database_file}",
        f"Yedek boyutu: {result.backup_size_text}",
        f"Test DB boyutu: {result.test_database_size_text}",
        f"Yedek SHA256: {result.backup_sha256}",
        f"SQLite quick_check: {result.sqlite_quick_check}",
        f"SQLite user_version: {result.sqlite_user_version}",
        f"SQLite tablo sayısı: {result.sqlite_table_count}",
        (
            "schema_migrations tablosu: "
            f"{'Var' if result.has_schema_migrations_table else 'Yok'}"
        ),
        f"Sonuç: {'BAŞARILI' if result.success else 'BAŞARISIZ'}",
        f"Mesaj: {result.message}",
    ]


def _ensure_sqlite_mode() -> None:
    if not settings.is_sqlite:
        raise SQLiteRestoreTestServiceError(
            "SQLite restore test servisi yalnızca SQLite Local modda çalışır."
        )


def _restore_test_folder() -> Path:
    runtime_paths = ensure_runtime_folders()

    return runtime_paths.backups_folder / SQLITE_RESTORE_TEST_FOLDER_NAME


def _build_restore_test_database_file(
    *,
    restore_test_folder: Path,
    backup_file: Path,
) -> Path:
    timestamp = datetime.now().strftime(SQLITE_RESTORE_TEST_FILE_TIMESTAMP_FORMAT)
    backup_stem = backup_file.stem

    return restore_test_folder / f"{backup_stem}_restore_test_{timestamp}.db"


def _inspect_sqlite_test_database(sqlite_file: Path) -> dict[str, object]:
    if not sqlite_file.exists() or not sqlite_file.is_file():
        raise SQLiteRestoreTestServiceError(
            f"SQLite restore test dosyası bulunamadı:\n{sqlite_file}"
        )

    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(f"file:{sqlite_file}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row

        quick_check_row = connection.execute("PRAGMA quick_check").fetchone()
        quick_check = str(quick_check_row[0] if quick_check_row else "").strip()

        user_version_row = connection.execute("PRAGMA user_version").fetchone()
        user_version = int(user_version_row[0] if user_version_row else 0)

        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        table_names = [
            str(row["name"])
            for row in table_rows
        ]

        return {
            "quick_check": quick_check,
            "user_version": user_version,
            "table_count": len(table_names),
            "has_schema_migrations_table": (
                BACKUP_STANDARD_SCHEMA_MIGRATIONS_TABLE in table_names
            ),
        }

    except sqlite3.Error as exc:
        raise SQLiteRestoreTestServiceError(
            f"SQLite restore test veritabanı incelenemedi:\n{sqlite_file}"
        ) from exc

    finally:
        if connection is not None:
            connection.close()


def _write_restore_test_log(message: str) -> None:
    runtime_paths = ensure_runtime_folders()
    log_file = runtime_paths.logs_folder / SQLITE_RESTORE_TEST_LOG_FILE_NAME

    try:
        with log_file.open("a", encoding="utf-8") as file:
            file.write(message)
            file.write("\n")

    except OSError as exc:
        raise SQLiteRestoreTestServiceError(
            f"SQLite restore test log dosyası yazılamadı:\n{log_file}"
        ) from exc


def _build_restore_test_log_line(result: SQLiteRestoreTestResult) -> str:
    return (
        f"{result.finished_at} | SQLite restore test başarılı | "
        f"Yedek: {result.backup_file} | "
        f"Test DB: {result.test_database_file} | "
        f"Boyut: {result.test_database_size_text} | "
        f"Tablo: {result.sqlite_table_count} | "
        f"user_version: {result.sqlite_user_version} | "
        f"quick_check: {result.sqlite_quick_check}"
    )


def _cleanup_old_restore_test_files(restore_test_folder: Path) -> None:
    test_files = sorted(
        [
            file_path
            for file_path in restore_test_folder.glob("*_restore_test_*.db")
            if file_path.is_file()
        ],
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )

    for old_file in test_files[SQLITE_RESTORE_TEST_KEEP_LATEST_FILES:]:
        try:
            old_file.unlink()

        except OSError:
            continue


__all__ = [
    "SQLITE_RESTORE_TEST_DATE_FORMAT",
    "SQLITE_RESTORE_TEST_FILE_TIMESTAMP_FORMAT",
    "SQLITE_RESTORE_TEST_FOLDER_NAME",
    "SQLITE_RESTORE_TEST_LOG_FILE_NAME",
    "SQLITE_RESTORE_TEST_KEEP_LATEST_FILES",
    "SQLiteRestoreTestServiceError",
    "SQLiteRestoreTestResult",
    "run_latest_sqlite_restore_test",
    "run_sqlite_restore_test",
    "get_sqlite_restore_test_summary_lines",
]
from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.backup_service import (
    BackupServiceError,
    BackupResult,
    create_database_backup,
    format_backup_size,
    list_database_backups,
)
from app.services.backup_standard_service import (
    BackupStandardValidationResult,
    get_backup_standard_summary_lines,
    validate_backup_against_standard,
)


RESTORE_STANDARD_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RestoreStandardServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RestoreSafetyPlan:
    restore_backup_file: Path
    active_database_file: Path
    pre_restore_safety_backup_file: Path
    restore_backup_size_bytes: int
    restore_backup_size_text: str
    restore_backup_sha256: str
    restore_backup_user_version: int | None
    restore_backup_table_count: int | None
    backup_validation_success: bool
    backup_validation_summary: str
    created_at: str
    message: str


@dataclass(frozen=True)
class RestoreExecutionResult:
    restore_backup_file: Path
    active_database_file: Path
    pre_restore_safety_backup_file: Path
    restored_database_size_bytes: int
    restored_database_size_text: str
    restored_at: str
    success: bool
    message: str


def build_restore_safety_plan(
    restore_backup_file: str | Path,
    *,
    require_metadata: bool = True,
    require_schema_migrations: bool = True,
) -> RestoreSafetyPlan:
    """
    Restore öncesi güvenlik planı oluşturur.

    Bu fonksiyon mevcut veritabanının üzerine yazmaz.
    Sadece:
    - restore edilecek yedeği doğrular,
    - mevcut aktif veritabanını tespit eder,
    - restore öncesi güvenlik yedeği alır,
    - plan sonucu döndürür.
    """

    _ensure_sqlite_mode()

    restore_backup_path = Path(restore_backup_file)
    active_database_file = _active_sqlite_database_file()

    if not active_database_file.exists() or not active_database_file.is_file():
        raise RestoreStandardServiceError(
            f"Aktif SQLite veritabanı dosyası bulunamadı:\n{active_database_file}"
        )

    if _same_file_safely(restore_backup_path, active_database_file):
        raise RestoreStandardServiceError(
            "Restore edilecek dosya aktif veritabanı dosyasıyla aynı olamaz."
        )

    validation_result = validate_backup_against_standard(
        restore_backup_path,
        require_metadata=require_metadata,
        require_schema_migrations=require_schema_migrations,
    )

    if not validation_result.success:
        validation_lines = get_backup_standard_summary_lines(validation_result)
        raise RestoreStandardServiceError(
            "Restore planı oluşturulamadı. Seçilen yedek FTM güvenli yedek "
            "standardını karşılamıyor.\n\n"
            + "\n".join(validation_lines)
        )

    safety_backup_result = _create_pre_restore_safety_backup()

    if not safety_backup_result.success or safety_backup_result.backup_file is None:
        raise RestoreStandardServiceError(
            "Restore öncesi güvenlik yedeği alınamadı.\n\n"
            f"Yedekleme mesajı:\n{safety_backup_result.message}"
        )

    safety_backup_file = safety_backup_result.backup_file

    if _same_file_safely(restore_backup_path, safety_backup_file):
        raise RestoreStandardServiceError(
            "Restore edilecek yedek dosyası ile restore öncesi alınan güvenlik "
            "yedeği aynı dosya olamaz."
        )

    return RestoreSafetyPlan(
        restore_backup_file=restore_backup_path,
        active_database_file=active_database_file,
        pre_restore_safety_backup_file=safety_backup_file,
        restore_backup_size_bytes=validation_result.backup_size_bytes,
        restore_backup_size_text=validation_result.backup_size_text,
        restore_backup_sha256=validation_result.sha256,
        restore_backup_user_version=validation_result.sqlite_user_version,
        restore_backup_table_count=validation_result.sqlite_table_count,
        backup_validation_success=validation_result.success,
        backup_validation_summary=validation_result.summary_message,
        created_at=datetime.now().strftime(RESTORE_STANDARD_DATE_FORMAT),
        message=(
            "Restore güvenlik planı hazırlandı. "
            "Mevcut veritabanına henüz dokunulmadı."
        ),
    )


def build_latest_backup_restore_safety_plan() -> RestoreSafetyPlan:
    backup_files = list_database_backups()

    if not backup_files:
        raise RestoreStandardServiceError(
            "Restore planı için yedek dosyası bulunamadı. Önce yeni bir yedek alın."
        )

    latest_backup = backup_files[0]

    return build_restore_safety_plan(latest_backup.file_path)


def execute_sqlite_restore_from_plan(
    restore_plan: RestoreSafetyPlan,
    *,
    confirm_restore: bool = False,
) -> RestoreExecutionResult:
    """
    SQLite restore işlemini çalıştırır.

    Güvenlik nedeniyle confirm_restore=True verilmeden çalışmaz.
    Bu fonksiyon P0.9.4 adımında kullanılacak şekilde hazırlandı.
    """

    _ensure_sqlite_mode()

    if not confirm_restore:
        raise RestoreStandardServiceError(
            "Restore işlemi güvenlik nedeniyle durduruldu. "
            "Gerçek restore için confirm_restore=True gereklidir."
        )

    active_database_file = restore_plan.active_database_file
    restore_backup_file = restore_plan.restore_backup_file

    if not restore_backup_file.exists() or not restore_backup_file.is_file():
        raise RestoreStandardServiceError(
            f"Restore edilecek yedek dosyası bulunamadı:\n{restore_backup_file}"
        )

    if not restore_plan.pre_restore_safety_backup_file.exists():
        raise RestoreStandardServiceError(
            "Restore öncesi güvenlik yedeği bulunamadı. Restore işlemi durduruldu.\n\n"
            f"Beklenen güvenlik yedeği:\n{restore_plan.pre_restore_safety_backup_file}"
        )

    validation_result = validate_backup_against_standard(restore_backup_file)

    if not validation_result.success:
        raise RestoreStandardServiceError(
            "Restore işlemi durduruldu. Restore edilecek yedek artık güvenli "
            "standarda uygun görünmüyor."
        )

    _copy_sqlite_backup_over_active_database(
        source_backup_file=restore_backup_file,
        active_database_file=active_database_file,
    )

    restored_size = active_database_file.stat().st_size

    return RestoreExecutionResult(
        restore_backup_file=restore_backup_file,
        active_database_file=active_database_file,
        pre_restore_safety_backup_file=restore_plan.pre_restore_safety_backup_file,
        restored_database_size_bytes=restored_size,
        restored_database_size_text=format_backup_size(restored_size),
        restored_at=datetime.now().strftime(RESTORE_STANDARD_DATE_FORMAT),
        success=True,
        message="SQLite restore işlemi başarıyla tamamlandı.",
    )


def get_restore_safety_plan_summary_lines(
    restore_plan: RestoreSafetyPlan,
) -> list[str]:
    return [
        "FTM Restore Güvenlik Planı",
        "-" * 44,
        f"Plan tarihi: {restore_plan.created_at}",
        f"Aktif veritabanı: {restore_plan.active_database_file}",
        f"Restore edilecek yedek: {restore_plan.restore_backup_file}",
        (
            "Restore öncesi güvenlik yedeği: "
            f"{restore_plan.pre_restore_safety_backup_file}"
        ),
        f"Yedek boyutu: {restore_plan.restore_backup_size_text}",
        f"Yedek SHA256: {restore_plan.restore_backup_sha256}",
        (
            "Yedek SQLite user_version: "
            f"{'-' if restore_plan.restore_backup_user_version is None else restore_plan.restore_backup_user_version}"
        ),
        (
            "Yedek tablo sayısı: "
            f"{'-' if restore_plan.restore_backup_table_count is None else restore_plan.restore_backup_table_count}"
        ),
        (
            "Yedek standart doğrulama: "
            f"{'BAŞARILI' if restore_plan.backup_validation_success else 'BAŞARISIZ'}"
        ),
        f"Doğrulama özeti: {restore_plan.backup_validation_summary}",
        "",
        f"Mesaj: {restore_plan.message}",
    ]


def get_restore_execution_summary_lines(
    result: RestoreExecutionResult,
) -> list[str]:
    return [
        "FTM SQLite Restore Sonucu",
        "-" * 44,
        f"Restore tarihi: {result.restored_at}",
        f"Restore edilen yedek: {result.restore_backup_file}",
        f"Aktif veritabanı: {result.active_database_file}",
        (
            "Restore öncesi güvenlik yedeği: "
            f"{result.pre_restore_safety_backup_file}"
        ),
        f"Yeni aktif DB boyutu: {result.restored_database_size_text}",
        f"Sonuç: {'BAŞARILI' if result.success else 'BAŞARISIZ'}",
        f"Mesaj: {result.message}",
    ]


def _ensure_sqlite_mode() -> None:
    if not settings.is_sqlite:
        raise RestoreStandardServiceError(
            "Restore standard servisi şu anda yalnızca SQLite Local modu için aktiftir."
        )


def _active_sqlite_database_file() -> Path:
    sqlite_path = settings.sqlite_database_path

    if sqlite_path.is_absolute():
        return sqlite_path

    return Path.cwd() / sqlite_path


def _create_pre_restore_safety_backup() -> BackupResult:
    try:
        return create_database_backup()

    except BackupServiceError as exc:
        raise RestoreStandardServiceError(
            f"Restore öncesi güvenlik yedeği alınamadı:\n{exc}"
        ) from exc

    except Exception as exc:
        raise RestoreStandardServiceError(
            f"Restore öncesi güvenlik yedeği alınırken beklenmeyen hata oluştu:\n{exc}"
        ) from exc


def _copy_sqlite_backup_over_active_database(
    *,
    source_backup_file: Path,
    active_database_file: Path,
) -> None:
    _validate_sqlite_file_can_be_opened_readonly(source_backup_file)

    active_database_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(source_backup_file, active_database_file)

    except OSError as exc:
        raise RestoreStandardServiceError(
            "SQLite restore sırasında dosya kopyalama işlemi başarısız oldu.\n\n"
            f"Kaynak yedek:\n{source_backup_file}\n\n"
            f"Hedef aktif veritabanı:\n{active_database_file}"
        ) from exc

    _validate_sqlite_file_can_be_opened_readonly(active_database_file)


def _validate_sqlite_file_can_be_opened_readonly(sqlite_file: Path) -> None:
    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(f"file:{sqlite_file}?mode=ro", uri=True)
        quick_check_row = connection.execute("PRAGMA quick_check").fetchone()
        quick_check_value = str(quick_check_row[0] if quick_check_row else "").strip()

        if quick_check_value.lower() != "ok":
            raise RestoreStandardServiceError(
                f"SQLite dosya bütünlük kontrolü başarısız: {quick_check_value}"
            )

    except sqlite3.Error as exc:
        raise RestoreStandardServiceError(
            f"SQLite dosyası salt okunur modda doğrulanamadı: {sqlite_file}"
        ) from exc

    finally:
        if connection is not None:
            connection.close()


def _same_file_safely(first_path: Path, second_path: Path) -> bool:
    try:
        return first_path.resolve() == second_path.resolve()

    except OSError:
        return str(first_path) == str(second_path)


__all__ = [
    "RESTORE_STANDARD_DATE_FORMAT",
    "RestoreStandardServiceError",
    "RestoreSafetyPlan",
    "RestoreExecutionResult",
    "build_restore_safety_plan",
    "build_latest_backup_restore_safety_plan",
    "execute_sqlite_restore_from_plan",
    "get_restore_safety_plan_summary_lines",
    "get_restore_execution_summary_lines",
]
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.runtime_paths import ensure_runtime_folders
from app.services.database_migration_service import (
    DatabaseMigrationResult,
    DatabaseMigrationServiceError,
    DatabaseMigrationStatus,
    assert_database_migration_readiness,
    get_database_migration_status,
    run_database_migrations,
)


STARTUP_UPDATE_SERVICE_VERSION = "1.0.0"

STARTUP_UPDATE_EVENT_LOG_FILE_NAME = "startup_update_events.jsonl"

STATUS_FIRST_INSTALL_REQUIRED = "first_install_required"
STATUS_UP_TO_DATE = "up_to_date"
STATUS_UPDATED = "updated"
STATUS_FAILED = "failed"


class StartupUpdateServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class StartupUpdateResult:
    status: str
    should_continue_to_app: bool
    database_path: str
    database_file_exists: bool
    migration_was_required: bool
    migration_was_run: bool
    backup_file: str | None
    applied_migration_ids: list[str]
    current_schema_version: int
    expected_schema_version: int
    quick_check_result: str | None
    message: str
    error_message: str | None
    elapsed_ms: int


def run_startup_update_gate(*, raise_on_failure: bool = False) -> StartupUpdateResult:
    """
    FTM açılışında çalıştırılacak otomatik güvenli güncelleme kapısı.

    Hedef:
        - Runtime klasörlerini hazırlar.
        - Veritabanı yoksa ilk kurulum akışına izin verir.
        - Veritabanı varsa bütünlük kontrolü yapar.
        - DB schema eskiyse otomatik yedek alarak migration çalıştırır.
        - Migration sonrası bütünlük ve schema doğrulaması yapar.
        - Başarısızlıkta uygulamanın normal veri girişine devam etmesini engelleyecek sonuç döndürür.

    Bu fonksiyon müşteri için tek tık güncelleme mantığının servis katmanıdır.
    UI/giriş dosyası bu sonucu okuyup uygulamayı açmalı veya güvenli hata göstermelidir.
    """

    started_at = perf_counter()
    runtime_paths = ensure_runtime_folders()
    database_path = runtime_paths.database_file
    log_file = runtime_paths.logs_folder / STARTUP_UPDATE_EVENT_LOG_FILE_NAME

    try:
        if not database_path.exists() or not database_path.is_file():
            result = StartupUpdateResult(
                status=STATUS_FIRST_INSTALL_REQUIRED,
                should_continue_to_app=True,
                database_path=str(database_path),
                database_file_exists=False,
                migration_was_required=False,
                migration_was_run=False,
                backup_file=None,
                applied_migration_ids=[],
                current_schema_version=0,
                expected_schema_version=0,
                quick_check_result=None,
                message=(
                    "Veritabanı bulunamadı. Bu durum ilk kurulum için normaldir. "
                    "Uygulama ilk kurulum akışına devam edebilir."
                ),
                error_message=None,
                elapsed_ms=_elapsed_ms(started_at),
            )
            _write_startup_update_event(log_file=log_file, result=result)
            return result

        quick_check_before = _run_sqlite_quick_check(database_path)

        if quick_check_before.lower() != "ok":
            raise StartupUpdateServiceError(
                "SQLite quick_check başarısız oldu. "
                "Veritabanı migration öncesinde güvenli görünmüyor.\n\n"
                f"Sonuç: {quick_check_before}\n"
                f"Veritabanı: {database_path}"
            )

        status_before = get_database_migration_status()

        if status_before.is_up_to_date:
            ready_status = assert_database_migration_readiness()
            quick_check_after = _run_sqlite_quick_check(database_path)

            if quick_check_after.lower() != "ok":
                raise StartupUpdateServiceError(
                    "SQLite quick_check başarısız oldu. "
                    "Veritabanı güncel görünüyor ancak bütünlük kontrolünden geçmedi.\n\n"
                    f"Sonuç: {quick_check_after}\n"
                    f"Veritabanı: {database_path}"
                )

            result = StartupUpdateResult(
                status=STATUS_UP_TO_DATE,
                should_continue_to_app=True,
                database_path=str(database_path),
                database_file_exists=True,
                migration_was_required=False,
                migration_was_run=False,
                backup_file=None,
                applied_migration_ids=[],
                current_schema_version=ready_status.current_user_version,
                expected_schema_version=ready_status.expected_schema_version,
                quick_check_result=quick_check_after,
                message="Veritabanı güncel. Migration gerekli değil.",
                error_message=None,
                elapsed_ms=_elapsed_ms(started_at),
            )
            _write_startup_update_event(log_file=log_file, result=result)
            return result

        migration_result = run_database_migrations(require_backup=True)
        quick_check_after = _run_sqlite_quick_check(database_path)

        if quick_check_after.lower() != "ok":
            raise StartupUpdateServiceError(
                "Migration tamamlandı ancak SQLite quick_check başarısız oldu.\n\n"
                f"Sonuç: {quick_check_after}\n"
                f"Veritabanı: {database_path}\n"
                f"Migration yedeği: {migration_result.backup_file}"
            )

        ready_status = assert_database_migration_readiness()

        result = StartupUpdateResult(
            status=STATUS_UPDATED,
            should_continue_to_app=True,
            database_path=str(database_path),
            database_file_exists=True,
            migration_was_required=True,
            migration_was_run=True,
            backup_file=migration_result.backup_file,
            applied_migration_ids=list(migration_result.applied_migration_ids),
            current_schema_version=ready_status.current_user_version,
            expected_schema_version=ready_status.expected_schema_version,
            quick_check_result=quick_check_after,
            message=(
                "Veritabanı otomatik olarak güncellendi. "
                f"Uygulanan migration sayısı: {len(migration_result.applied_migration_ids)}"
            ),
            error_message=None,
            elapsed_ms=_elapsed_ms(started_at),
        )
        _write_startup_update_event(log_file=log_file, result=result)
        return result

    except Exception as exc:
        result = _build_failure_result(
            database_path=database_path,
            started_at=started_at,
            exc=exc,
        )
        _write_startup_update_event(log_file=log_file, result=result)

        if raise_on_failure:
            raise StartupUpdateServiceError(result.error_message or result.message) from exc

        return result


def assert_startup_update_gate_ready() -> StartupUpdateResult:
    """
    Açılış kapısını çalıştırır ve başarısızlıkta exception yükseltir.

    UI giriş dosyasında basit kullanım:
        result = assert_startup_update_gate_ready()
    """

    return run_startup_update_gate(raise_on_failure=True)


def startup_update_result_as_dict(result: StartupUpdateResult) -> dict[str, Any]:
    return asdict(result)


def startup_update_result_to_text(result: StartupUpdateResult) -> str:
    lines = [
        f"Durum: {result.status}",
        f"Devam: {'Evet' if result.should_continue_to_app else 'Hayır'}",
        f"Veritabanı: {result.database_path}",
        f"DB var mı: {'Evet' if result.database_file_exists else 'Hayır'}",
        f"Migration gerekli miydi: {'Evet' if result.migration_was_required else 'Hayır'}",
        f"Migration çalıştı mı: {'Evet' if result.migration_was_run else 'Hayır'}",
        f"Yedek: {result.backup_file or '-'}",
        f"Uygulanan migration: {', '.join(result.applied_migration_ids) if result.applied_migration_ids else '-'}",
        f"Schema: {result.current_schema_version} / {result.expected_schema_version}",
        f"quick_check: {result.quick_check_result or '-'}",
        f"Süre: {result.elapsed_ms} ms",
        f"Mesaj: {result.message}",
    ]

    if result.error_message:
        lines.append(f"Hata: {result.error_message}")

    return "\n".join(lines)


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _run_sqlite_quick_check(database_path: Path) -> str:
    if not database_path.exists() or not database_path.is_file():
        raise StartupUpdateServiceError(
            f"SQLite quick_check çalıştırılamadı. Veritabanı bulunamadı: {database_path}"
        )

    try:
        with sqlite3.connect(str(database_path)) as connection:
            row = connection.execute("PRAGMA quick_check;").fetchone()
    except sqlite3.Error as exc:
        raise StartupUpdateServiceError(
            "SQLite quick_check sırasında hata oluştu.\n\n"
            f"Veritabanı: {database_path}\n"
            f"Hata: {exc}"
        ) from exc

    if not row:
        raise StartupUpdateServiceError(
            "SQLite quick_check sonuç döndürmedi.\n\n"
            f"Veritabanı: {database_path}"
        )

    return str(row[0])


def _build_failure_result(
    *,
    database_path: Path,
    started_at: float,
    exc: Exception,
) -> StartupUpdateResult:
    current_schema_version = 0
    expected_schema_version = 0
    quick_check_result: str | None = None
    database_file_exists = database_path.exists() and database_path.is_file()

    try:
        if database_file_exists:
            quick_check_result = _run_sqlite_quick_check(database_path)
    except Exception:
        quick_check_result = None

    try:
        status = get_database_migration_status()
        current_schema_version = status.current_user_version
        expected_schema_version = status.expected_schema_version
        database_file_exists = status.database_file_exists
    except Exception:
        pass

    error_message = str(exc)

    return StartupUpdateResult(
        status=STATUS_FAILED,
        should_continue_to_app=False,
        database_path=str(database_path),
        database_file_exists=database_file_exists,
        migration_was_required=False,
        migration_was_run=False,
        backup_file=_extract_backup_file_from_error_message(error_message),
        applied_migration_ids=[],
        current_schema_version=current_schema_version,
        expected_schema_version=expected_schema_version,
        quick_check_result=quick_check_result,
        message=(
            "Otomatik veritabanı güncelleme kontrolü başarısız oldu. "
            "Uygulama normal veri girişine devam etmemelidir."
        ),
        error_message=error_message,
        elapsed_ms=_elapsed_ms(started_at),
    )


def _extract_backup_file_from_error_message(error_message: str) -> str | None:
    marker = "Migration öncesi alınan güvenli yedek:"
    marker_index = error_message.find(marker)

    if marker_index < 0:
        return None

    after_marker = error_message[marker_index + len(marker) :].strip()

    if not after_marker:
        return None

    first_line = after_marker.splitlines()[0].strip()

    return first_line or None


def _write_startup_update_event(
    *,
    log_file: Path,
    result: StartupUpdateResult,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "event": "startup_update_gate",
        "service_version": STARTUP_UPDATE_SERVICE_VERSION,
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        **startup_update_result_as_dict(result),
    }

    log_file.open("a", encoding="utf-8").write(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )


__all__ = [
    "STARTUP_UPDATE_SERVICE_VERSION",
    "STATUS_FIRST_INSTALL_REQUIRED",
    "STATUS_UP_TO_DATE",
    "STATUS_UPDATED",
    "STATUS_FAILED",
    "StartupUpdateServiceError",
    "StartupUpdateResult",
    "run_startup_update_gate",
    "assert_startup_update_gate_ready",
    "startup_update_result_as_dict",
    "startup_update_result_to_text",
]

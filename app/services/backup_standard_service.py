from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.backup_service import (
    BackupServiceError,
    BackupValidationResult,
    calculate_file_sha256,
    format_backup_size,
    list_database_backups,
    validate_backup_file,
)


BACKUP_STANDARD_MIN_SCHEMA_VERSION = 1
BACKUP_STANDARD_SCHEMA_MIGRATIONS_TABLE = "schema_migrations"


class BackupStandardServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupStandardCheck:
    name: str
    success: bool
    message: str


@dataclass(frozen=True)
class BackupStandardValidationResult:
    backup_file: Path
    metadata_file: Path
    backup_size_bytes: int
    backup_size_text: str
    sha256: str
    database_engine: str
    sqlite_user_version: int | None
    sqlite_table_count: int | None
    sqlite_quick_check: str
    success: bool
    checks: list[BackupStandardCheck]
    warnings: list[str]

    @property
    def failed_checks(self) -> list[BackupStandardCheck]:
        return [
            check
            for check in self.checks
            if not check.success
        ]

    @property
    def success_check_count(self) -> int:
        return len(
            [
                check
                for check in self.checks
                if check.success
            ]
        )

    @property
    def failed_check_count(self) -> int:
        return len(self.failed_checks)

    @property
    def summary_message(self) -> str:
        if self.success:
            return (
                "Yedek dosyası FTM güvenli yedek standardına uygun görünüyor. "
                f"Başarılı kontrol: {self.success_check_count}"
            )

        return (
            "Yedek dosyası FTM güvenli yedek standardını karşılamıyor. "
            f"Başarısız kontrol: {self.failed_check_count}"
        )


def metadata_file_for_backup(backup_file: str | Path) -> Path:
    backup_path = Path(backup_file)

    return backup_path.with_suffix(f"{backup_path.suffix}.meta.json")


def validate_backup_against_standard(
    backup_file: str | Path,
    *,
    require_metadata: bool = True,
    require_schema_migrations: bool = True,
    min_schema_version: int = BACKUP_STANDARD_MIN_SCHEMA_VERSION,
) -> BackupStandardValidationResult:
    backup_path = Path(backup_file)
    metadata_file = metadata_file_for_backup(backup_path)
    checks: list[BackupStandardCheck] = []
    warnings: list[str] = []

    backup_validation = _run_basic_backup_validation(
        backup_path=backup_path,
        checks=checks,
    )

    metadata = _read_metadata_file(
        metadata_file=metadata_file,
        checks=checks,
        require_metadata=require_metadata,
    )

    actual_sha256 = ""
    actual_size = 0

    if backup_path.exists() and backup_path.is_file():
        actual_size = backup_path.stat().st_size
        actual_sha256 = calculate_file_sha256(backup_path)

    _check_metadata_integrity(
        metadata=metadata,
        actual_sha256=actual_sha256,
        actual_size=actual_size,
        checks=checks,
        warnings=warnings,
    )

    sqlite_user_version: int | None = None
    sqlite_table_count: int | None = None
    sqlite_quick_check = ""

    if settings.is_sqlite:
        if backup_validation is not None and backup_validation.success:
            checks.append(
                BackupStandardCheck(
                    name="engine_match",
                    success=True,
                    message="Uygulama SQLite modda ve yedek SQLite kontrolüne alındı.",
                )
            )
        else:
            checks.append(
                BackupStandardCheck(
                    name="engine_match",
                    success=False,
                    message=(
                        "Uygulama SQLite modda ancak yedek dosyasının SQLite uyumu "
                        "temel doğrulamada onaylanamadı."
                    ),
                )
            )

        sqlite_result = _inspect_sqlite_backup_file(
            backup_path=backup_path,
            require_schema_migrations=require_schema_migrations,
            min_schema_version=min_schema_version,
            checks=checks,
        )

        sqlite_user_version = sqlite_result["user_version"]
        sqlite_table_count = sqlite_result["table_count"]
        sqlite_quick_check = sqlite_result["quick_check"]

    else:
        warnings.append(
            "Bu standart doğrulama adımı şu anda SQLite Local kurulum için hazırlanmıştır."
        )

    success = all(check.success for check in checks)

    return BackupStandardValidationResult(
        backup_file=backup_path,
        metadata_file=metadata_file,
        backup_size_bytes=actual_size,
        backup_size_text=format_backup_size(actual_size),
        sha256=actual_sha256,
        database_engine=str(settings.database_engine),
        sqlite_user_version=sqlite_user_version,
        sqlite_table_count=sqlite_table_count,
        sqlite_quick_check=sqlite_quick_check,
        success=success,
        checks=checks,
        warnings=warnings,
    )


def validate_latest_backup_against_standard() -> BackupStandardValidationResult:
    backup_files = list_database_backups()

    if not backup_files:
        raise BackupStandardServiceError(
            "Doğrulanacak yedek dosyası bulunamadı. Önce yeni bir yedek alın."
        )

    latest_backup = backup_files[0]

    return validate_backup_against_standard(latest_backup.file_path)


def get_backup_standard_summary_lines(
    result: BackupStandardValidationResult,
) -> list[str]:
    lines = [
        "FTM Güvenli Yedek Standardı Kontrolü",
        "-" * 52,
        f"Yedek dosyası: {result.backup_file}",
        f"Metadata dosyası: {result.metadata_file}",
        f"Veritabanı motoru: {result.database_engine}",
        f"Yedek boyutu: {result.backup_size_text}",
        f"SHA256: {result.sha256}",
        f"SQLite quick_check: {result.sqlite_quick_check or '-'}",
        (
            "SQLite user_version: "
            f"{'-' if result.sqlite_user_version is None else result.sqlite_user_version}"
        ),
        (
            "SQLite tablo sayısı: "
            f"{'-' if result.sqlite_table_count is None else result.sqlite_table_count}"
        ),
        "",
        f"Genel sonuç: {'BAŞARILI' if result.success else 'BAŞARISIZ'}",
        result.summary_message,
        "",
        "Kontroller:",
    ]

    for check in result.checks:
        prefix = "✅" if check.success else "❌"
        lines.append(f"{prefix} {check.name}: {check.message}")

    if result.warnings:
        lines.append("")
        lines.append("Uyarılar:")

        for warning in result.warnings:
            lines.append(f"- {warning}")

    return lines


def _run_basic_backup_validation(
    *,
    backup_path: Path,
    checks: list[BackupStandardCheck],
) -> BackupValidationResult | None:
    try:
        validation = validate_backup_file(backup_path)

    except BackupServiceError as exc:
        checks.append(
            BackupStandardCheck(
                name="basic_backup_validation",
                success=False,
                message=str(exc),
            )
        )
        return None

    checks.append(
        BackupStandardCheck(
            name="basic_backup_validation",
            success=validation.success,
            message=validation.message,
        )
    )

    return validation


def _read_metadata_file(
    *,
    metadata_file: Path,
    checks: list[BackupStandardCheck],
    require_metadata: bool,
) -> dict[str, Any]:
    if not metadata_file.exists():
        checks.append(
            BackupStandardCheck(
                name="metadata_exists",
                success=not require_metadata,
                message=(
                    "Yedek metadata dosyası bulunamadı."
                    if require_metadata
                    else "Yedek metadata dosyası bulunamadı ancak bu kontrolde zorunlu değil."
                ),
            )
        )
        return {}

    if not metadata_file.is_file():
        checks.append(
            BackupStandardCheck(
                name="metadata_exists",
                success=False,
                message="Metadata yolu dosya değil.",
            )
        )
        return {}

    try:
        loaded_data = json.loads(metadata_file.read_text(encoding="utf-8"))

    except json.JSONDecodeError as exc:
        checks.append(
            BackupStandardCheck(
                name="metadata_json_valid",
                success=False,
                message=f"Metadata JSON formatı bozuk: {exc}",
            )
        )
        return {}

    except OSError as exc:
        checks.append(
            BackupStandardCheck(
                name="metadata_readable",
                success=False,
                message=f"Metadata dosyası okunamadı: {exc}",
            )
        )
        return {}

    if not isinstance(loaded_data, dict):
        checks.append(
            BackupStandardCheck(
                name="metadata_json_valid",
                success=False,
                message="Metadata JSON kök değeri nesne değil.",
            )
        )
        return {}

    checks.append(
        BackupStandardCheck(
            name="metadata_exists",
            success=True,
            message="Yedek metadata dosyası mevcut.",
        )
    )

    checks.append(
        BackupStandardCheck(
            name="metadata_json_valid",
            success=True,
            message="Metadata JSON formatı geçerli.",
        )
    )

    return loaded_data


def _check_metadata_integrity(
    *,
    metadata: dict[str, Any],
    actual_sha256: str,
    actual_size: int,
    checks: list[BackupStandardCheck],
    warnings: list[str],
) -> None:
    if not metadata:
        warnings.append(
            "Metadata okunamadığı için SHA256 / boyut / motor karşılaştırması yapılamadı."
        )
        return

    metadata_sha256 = str(metadata.get("sha256") or "").strip()
    metadata_size_raw = metadata.get("backup_size_bytes")
    metadata_engine = str(metadata.get("database_engine") or "").strip()

    checks.append(
        BackupStandardCheck(
            name="metadata_sha256_match",
            success=bool(metadata_sha256) and metadata_sha256 == actual_sha256,
            message=(
                "Metadata SHA256 değeri dosyanın gerçek SHA256 değeriyle uyumlu."
                if metadata_sha256 == actual_sha256
                else "Metadata SHA256 değeri gerçek dosya SHA256 değeriyle uyumsuz."
            ),
        )
    )

    try:
        metadata_size = int(metadata_size_raw)
    except (TypeError, ValueError):
        metadata_size = -1

    checks.append(
        BackupStandardCheck(
            name="metadata_size_match",
            success=metadata_size == actual_size,
            message=(
                "Metadata dosya boyutu gerçek dosya boyutuyla uyumlu."
                if metadata_size == actual_size
                else "Metadata dosya boyutu gerçek dosya boyutuyla uyumsuz."
            ),
        )
    )

    if metadata_engine:
        checks.append(
            BackupStandardCheck(
                name="metadata_engine_match",
                success=metadata_engine == str(settings.database_engine),
                message=(
                    "Metadata veritabanı motoru mevcut çalışma modu ile uyumlu."
                    if metadata_engine == str(settings.database_engine)
                    else (
                        "Metadata veritabanı motoru mevcut çalışma modu ile uyumsuz. "
                        f"Metadata: {metadata_engine}, Mevcut: {settings.database_engine}"
                    )
                ),
            )
        )
    else:
        checks.append(
            BackupStandardCheck(
                name="metadata_engine_match",
                success=False,
                message="Metadata içinde database_engine alanı bulunamadı.",
            )
        )


def _inspect_sqlite_backup_file(
    *,
    backup_path: Path,
    require_schema_migrations: bool,
    min_schema_version: int,
    checks: list[BackupStandardCheck],
) -> dict[str, Any]:
    result = {
        "quick_check": "",
        "user_version": None,
        "table_count": None,
    }

    if not backup_path.exists() or not backup_path.is_file():
        checks.append(
            BackupStandardCheck(
                name="sqlite_open_readonly",
                success=False,
                message="SQLite yedek dosyası bulunamadığı için açılamadı.",
            )
        )
        return result

    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row

        checks.append(
            BackupStandardCheck(
                name="sqlite_open_readonly",
                success=True,
                message="SQLite yedek dosyası salt okunur modda açıldı.",
            )
        )

        quick_check_row = connection.execute("PRAGMA quick_check").fetchone()
        quick_check_value = str(quick_check_row[0] if quick_check_row else "").strip()
        result["quick_check"] = quick_check_value

        checks.append(
            BackupStandardCheck(
                name="sqlite_quick_check",
                success=quick_check_value.lower() == "ok",
                message=(
                    "SQLite PRAGMA quick_check sonucu OK."
                    if quick_check_value.lower() == "ok"
                    else f"SQLite PRAGMA quick_check sonucu beklenen gibi değil: {quick_check_value}"
                ),
            )
        )

        user_version_row = connection.execute("PRAGMA user_version").fetchone()
        user_version = int(user_version_row[0] if user_version_row else 0)
        result["user_version"] = user_version

        checks.append(
            BackupStandardCheck(
                name="sqlite_user_version",
                success=user_version >= min_schema_version,
                message=(
                    f"SQLite user_version yeterli: {user_version}"
                    if user_version >= min_schema_version
                    else (
                        "SQLite user_version beklenen minimum seviyenin altında. "
                        f"Mevcut: {user_version}, Minimum: {min_schema_version}"
                    )
                ),
            )
        )

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

        result["table_count"] = len(table_names)

        checks.append(
            BackupStandardCheck(
                name="sqlite_table_count",
                success=len(table_names) > 0,
                message=(
                    f"SQLite yedek içinde {len(table_names)} adet kullanıcı tablosu bulundu."
                    if table_names
                    else "SQLite yedek içinde kullanıcı tablosu bulunamadı."
                ),
            )
        )

        has_schema_migrations = BACKUP_STANDARD_SCHEMA_MIGRATIONS_TABLE in table_names

        checks.append(
            BackupStandardCheck(
                name="sqlite_schema_migrations_table",
                success=has_schema_migrations or not require_schema_migrations,
                message=(
                    "schema_migrations tablosu yedek içinde mevcut."
                    if has_schema_migrations
                    else (
                        "schema_migrations tablosu yedek içinde bulunamadı."
                        if require_schema_migrations
                        else "schema_migrations tablosu bulunamadı ancak bu kontrolde zorunlu değil."
                    )
                ),
            )
        )

    except sqlite3.Error as exc:
        checks.append(
            BackupStandardCheck(
                name="sqlite_integrity",
                success=False,
                message=f"SQLite yedek dosyası incelenirken hata oluştu: {exc}",
            )
        )

    finally:
        if connection is not None:
            connection.close()

    return result


__all__ = [
    "BACKUP_STANDARD_MIN_SCHEMA_VERSION",
    "BACKUP_STANDARD_SCHEMA_MIGRATIONS_TABLE",
    "BackupStandardServiceError",
    "BackupStandardCheck",
    "BackupStandardValidationResult",
    "metadata_file_for_backup",
    "validate_backup_against_standard",
    "validate_latest_backup_against_standard",
    "get_backup_standard_summary_lines",
]
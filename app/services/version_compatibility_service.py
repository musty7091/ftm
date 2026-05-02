from __future__ import annotations

from dataclasses import dataclass

from app.core.version import get_app_version_info
from app.services.database_migration_service import (
    DatabaseMigrationServiceError,
    DatabaseMigrationStatus,
    get_database_migration_status,
)


class DatabaseVersionCompatibilityError(RuntimeError):
    def __init__(
        self,
        user_message: str,
        technical_message: str | None = None,
    ) -> None:
        super().__init__(technical_message or user_message)
        self.user_message = user_message
        self.technical_message = technical_message or user_message


@dataclass(frozen=True)
class DatabaseVersionCompatibilityStatus:
    app_name: str
    app_version: str
    app_database_schema_version: int
    min_supported_database_schema_version: int
    migration_expected_schema_version: int
    database_current_schema_version: int
    database_path: str
    database_file_exists: bool
    tracking_table_exists: bool
    migration_is_up_to_date: bool
    pending_migration_ids: list[str]
    version_definition_is_consistent: bool
    database_is_supported: bool
    database_is_not_newer_than_app: bool
    is_compatible: bool
    blocking_reasons: list[str]
    warnings: list[str]

    @property
    def summary_text(self) -> str:
        if self.is_compatible:
            return (
                "Uygulama ve veritabanı sürüm uyumu sağlıklı. "
                f"Uygulama: v{self.app_version}, "
                f"DB schema: v{self.database_current_schema_version}"
            )

        return (
            "Uygulama ve veritabanı sürüm uyumu sağlanamadı. "
            f"Engel sayısı: {len(self.blocking_reasons)}"
        )


def get_database_version_compatibility_status() -> DatabaseVersionCompatibilityStatus:
    app_version_info = get_app_version_info()

    try:
        migration_status = get_database_migration_status()

    except DatabaseMigrationServiceError as exc:
        raise DatabaseVersionCompatibilityError(
            user_message=(
                "Veritabanı sürüm kontrolü yapılamadı.\n\n"
                "Uygulama güvenli şekilde devam edemiyor. "
                "Lütfen destek ekibiyle iletişime geçin."
            ),
            technical_message=str(exc),
        ) from exc

    blocking_reasons: list[str] = []
    warnings: list[str] = []

    version_definition_is_consistent = (
        app_version_info.database_schema_version
        == migration_status.expected_schema_version
    )

    database_is_supported = (
        migration_status.current_user_version
        >= app_version_info.min_supported_database_schema_version
    )

    database_is_not_newer_than_app = (
        migration_status.current_user_version
        <= app_version_info.database_schema_version
    )

    if not migration_status.database_file_exists:
        blocking_reasons.append(
            "Veritabanı dosyası bulunamadı."
        )

    if not migration_status.tracking_table_exists:
        blocking_reasons.append(
            "Migration takip tablosu bulunamadı."
        )

    if migration_status.pending_migration_ids:
        blocking_reasons.append(
            "Bekleyen veritabanı güncellemesi var: "
            + ", ".join(migration_status.pending_migration_ids)
        )

    if not migration_status.is_up_to_date:
        blocking_reasons.append(
            "Veritabanı migration durumuna göre güncel değil."
        )

    if not version_definition_is_consistent:
        blocking_reasons.append(
            "Uygulama sürüm dosyasındaki DB schema versiyonu ile "
            "migration sisteminin beklediği DB schema versiyonu uyumsuz."
        )

    if not database_is_supported:
        blocking_reasons.append(
            "Veritabanı bu uygulama sürümü için desteklenen minimum "
            "şema sürümünden daha eski."
        )

    if not database_is_not_newer_than_app:
        blocking_reasons.append(
            "Veritabanı bu uygulama sürümünden daha yeni görünüyor. "
            "Eski uygulama sürümüyle yeni veritabanı açılmamalıdır."
        )

    if migration_status.current_user_version == 0:
        warnings.append(
            "SQLite PRAGMA user_version değeri 0 görünüyor."
        )

    if not migration_status.tracking_table_exists:
        warnings.append(
            "Migration takip tablosu henüz oluşmamış görünüyor."
        )

    is_compatible = not blocking_reasons

    return DatabaseVersionCompatibilityStatus(
        app_name=app_version_info.app_name,
        app_version=app_version_info.app_version,
        app_database_schema_version=app_version_info.database_schema_version,
        min_supported_database_schema_version=(
            app_version_info.min_supported_database_schema_version
        ),
        migration_expected_schema_version=(
            migration_status.expected_schema_version
        ),
        database_current_schema_version=(
            migration_status.current_user_version
        ),
        database_path=migration_status.database_path,
        database_file_exists=migration_status.database_file_exists,
        tracking_table_exists=migration_status.tracking_table_exists,
        migration_is_up_to_date=migration_status.is_up_to_date,
        pending_migration_ids=migration_status.pending_migration_ids,
        version_definition_is_consistent=version_definition_is_consistent,
        database_is_supported=database_is_supported,
        database_is_not_newer_than_app=database_is_not_newer_than_app,
        is_compatible=is_compatible,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
    )


def assert_database_version_is_compatible() -> DatabaseVersionCompatibilityStatus:
    compatibility_status = get_database_version_compatibility_status()

    if compatibility_status.is_compatible:
        return compatibility_status

    blocking_text = "\n".join(
        f"- {reason}"
        for reason in compatibility_status.blocking_reasons
    )

    raise DatabaseVersionCompatibilityError(
        user_message=(
            "Uygulama ve veritabanı sürümü uyumlu değil.\n\n"
            "Güvenlik nedeniyle uygulama başlatılamıyor.\n\n"
            f"{blocking_text}"
        ),
        technical_message=compatibility_status.summary_text,
    )


def get_database_version_compatibility_lines() -> list[str]:
    compatibility_status = get_database_version_compatibility_status()

    lines = [
        "FTM Sürüm / Veritabanı Uyumluluk Kontrolü",
        "-" * 48,
        f"Uygulama: {compatibility_status.app_name}",
        f"Uygulama sürümü: {compatibility_status.app_version}",
        (
            "Uygulamanın beklediği DB schema: "
            f"v{compatibility_status.app_database_schema_version}"
        ),
        (
            "Desteklenen minimum DB schema: "
            f"v{compatibility_status.min_supported_database_schema_version}"
        ),
        (
            "Migration sisteminin hedef DB schema: "
            f"v{compatibility_status.migration_expected_schema_version}"
        ),
        (
            "Mevcut veritabanı DB schema: "
            f"v{compatibility_status.database_current_schema_version}"
        ),
        f"Veritabanı yolu: {compatibility_status.database_path}",
        (
            "Veritabanı dosyası var mı: "
            f"{_yes_no(compatibility_status.database_file_exists)}"
        ),
        (
            "Migration takip tablosu var mı: "
            f"{_yes_no(compatibility_status.tracking_table_exists)}"
        ),
        (
            "Migration güncel mi: "
            f"{_yes_no(compatibility_status.migration_is_up_to_date)}"
        ),
        (
            "Sürüm tanımları tutarlı mı: "
            f"{_yes_no(compatibility_status.version_definition_is_consistent)}"
        ),
        (
            "Veritabanı minimum sürümü karşılıyor mu: "
            f"{_yes_no(compatibility_status.database_is_supported)}"
        ),
        (
            "Veritabanı uygulamadan yeni değil mi: "
            f"{_yes_no(compatibility_status.database_is_not_newer_than_app)}"
        ),
        (
            "Genel uyumluluk: "
            f"{'UYUMLU' if compatibility_status.is_compatible else 'UYUMSUZ'}"
        ),
    ]

    if compatibility_status.pending_migration_ids:
        lines.append("")
        lines.append("Bekleyen migration kayıtları:")
        lines.extend(
            f"- {migration_id}"
            for migration_id in compatibility_status.pending_migration_ids
        )

    if compatibility_status.blocking_reasons:
        lines.append("")
        lines.append("Engelleyen nedenler:")
        lines.extend(
            f"- {reason}"
            for reason in compatibility_status.blocking_reasons
        )

    if compatibility_status.warnings:
        lines.append("")
        lines.append("Uyarılar:")
        lines.extend(
            f"- {warning}"
            for warning in compatibility_status.warnings
        )

    lines.append("")
    lines.append(compatibility_status.summary_text)

    return lines


def _yes_no(value: bool) -> str:
    return "Evet" if value else "Hayır"


__all__ = [
    "DatabaseVersionCompatibilityError",
    "DatabaseVersionCompatibilityStatus",
    "get_database_version_compatibility_status",
    "assert_database_version_is_compatible",
    "get_database_version_compatibility_lines",
]
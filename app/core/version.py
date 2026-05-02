from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


APP_CODE = "FTM"
APP_NAME = "FTM Finans Takip Merkezi"
APP_VERSION = "0.7.0"
APP_RELEASE_STAGE = "P0"
APP_RELEASE_CHANNEL = "local-desktop"
APP_BUILD_DATE = "2026-05-02"

DATABASE_SCHEMA_VERSION = 1
MIN_SUPPORTED_DATABASE_SCHEMA_VERSION = 1

RELEASE_NOTES = (
    "P0.6 SQLite migration/update sistemi eklendi.",
    "Migration takip tablosu ve PRAGMA user_version kontrolü devreye alındı.",
    "Migration öncesi otomatik yedekleme altyapısı hazırlandı.",
    "P0.7 sürüm/DB uyum kontrolü hazırlık adımı başlatıldı.",
)


@dataclass(frozen=True)
class AppVersionInfo:
    app_code: str
    app_name: str
    app_version: str
    release_stage: str
    release_channel: str
    build_date: str
    database_schema_version: int
    min_supported_database_schema_version: int
    release_notes: tuple[str, ...]

    @property
    def full_version_text(self) -> str:
        return (
            f"{self.app_name} "
            f"v{self.app_version} "
            f"({self.release_stage} / {self.release_channel})"
        )

    @property
    def database_schema_text(self) -> str:
        return (
            f"DB schema v{self.database_schema_version} "
            f"(minimum desteklenen v{self.min_supported_database_schema_version})"
        )


def get_app_version_info() -> AppVersionInfo:
    return AppVersionInfo(
        app_code=APP_CODE,
        app_name=APP_NAME,
        app_version=APP_VERSION,
        release_stage=APP_RELEASE_STAGE,
        release_channel=APP_RELEASE_CHANNEL,
        build_date=APP_BUILD_DATE,
        database_schema_version=DATABASE_SCHEMA_VERSION,
        min_supported_database_schema_version=MIN_SUPPORTED_DATABASE_SCHEMA_VERSION,
        release_notes=RELEASE_NOTES,
    )


def get_app_version_text() -> str:
    return get_app_version_info().full_version_text


def get_database_schema_version() -> int:
    return DATABASE_SCHEMA_VERSION


def get_min_supported_database_schema_version() -> int:
    return MIN_SUPPORTED_DATABASE_SCHEMA_VERSION


def get_release_summary_lines() -> list[str]:
    version_info = get_app_version_info()

    return [
        f"Uygulama: {version_info.app_name}",
        f"Sürüm: {version_info.app_version}",
        f"Aşama: {version_info.release_stage}",
        f"Kanal: {version_info.release_channel}",
        f"Build tarihi: {version_info.build_date}",
        f"DB schema: {version_info.database_schema_text}",
        "Notlar:",
        *[f"- {note}" for note in version_info.release_notes],
    ]


def get_machine_readable_version_info() -> dict[str, object]:
    version_info = get_app_version_info()

    return {
        "app_code": version_info.app_code,
        "app_name": version_info.app_name,
        "app_version": version_info.app_version,
        "release_stage": version_info.release_stage,
        "release_channel": version_info.release_channel,
        "build_date": version_info.build_date,
        "database_schema_version": version_info.database_schema_version,
        "min_supported_database_schema_version": (
            version_info.min_supported_database_schema_version
        ),
        "release_notes": list(version_info.release_notes),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


__all__ = [
    "APP_CODE",
    "APP_NAME",
    "APP_VERSION",
    "APP_RELEASE_STAGE",
    "APP_RELEASE_CHANNEL",
    "APP_BUILD_DATE",
    "DATABASE_SCHEMA_VERSION",
    "MIN_SUPPORTED_DATABASE_SCHEMA_VERSION",
    "RELEASE_NOTES",
    "AppVersionInfo",
    "get_app_version_info",
    "get_app_version_text",
    "get_database_schema_version",
    "get_min_supported_database_schema_version",
    "get_release_summary_lines",
    "get_machine_readable_version_info",
]
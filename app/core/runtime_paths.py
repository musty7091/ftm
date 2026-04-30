from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_FOLDER_NAME = "FTM"

DATA_FOLDER_NAME = "data"
CONFIG_FOLDER_NAME = "config"
BACKUPS_FOLDER_NAME = "backups"
EXPORTS_FOLDER_NAME = "exports"
LOGS_FOLDER_NAME = "logs"

DATABASE_FILE_NAME = "ftm_local.db"
APP_SETTINGS_FILE_NAME = "app_settings.json"
LICENSE_FILE_NAME = "license.json"


@dataclass(frozen=True)
class RuntimePaths:
    root_folder: Path
    data_folder: Path
    config_folder: Path
    backups_folder: Path
    exports_folder: Path
    logs_folder: Path
    database_file: Path
    app_settings_file: Path
    license_file: Path


def is_packaged_app() -> bool:
    """
    Program PyInstaller ile .exe olarak paketlenmiş mi kontrol eder.

    Geliştirme sırasında:
        False

    .exe çalışırken:
        True
    """

    return bool(getattr(sys, "frozen", False))


def get_local_app_data_folder() -> Path:
    """
    Windows üzerinde kullanıcıya ait güvenli uygulama veri klasörünü bulur.

    Normalde şu klasörü hedefler:
        C:\\Users\\KULLANICI_ADI\\AppData\\Local

    Eğer ortam değişkenleri okunamazsa güvenli bir yedek yol üretir.
    """

    local_app_data = os.getenv("LOCALAPPDATA", "").strip()

    if local_app_data:
        return Path(local_app_data)

    app_data = os.getenv("APPDATA", "").strip()

    if app_data:
        return Path(app_data)

    if os.name == "nt":
        return Path.home() / "AppData" / "Local"

    return Path.home() / ".local" / "share"


def get_runtime_root_folder() -> Path:
    """
    FTM uygulamasının müşterinin bilgisayarındaki ana çalışma klasörünü döndürür.

    Varsayılan hedef:
        C:\\Users\\KULLANICI_ADI\\AppData\\Local\\FTM

    Test veya özel kurulum gerektiğinde FTM_RUNTIME_DIR ortam değişkeni ile
    farklı bir klasör de verilebilir.
    """

    custom_runtime_dir = os.getenv("FTM_RUNTIME_DIR", "").strip()

    if custom_runtime_dir:
        return Path(custom_runtime_dir).expanduser().resolve()

    return get_local_app_data_folder() / APP_FOLDER_NAME


def get_runtime_paths() -> RuntimePaths:
    """
    FTM için kullanılacak tüm önemli klasör ve dosya yollarını hazırlar.

    Bu fonksiyon sadece yolları hesaplar.
    Klasör oluşturmaz.
    """

    root_folder = get_runtime_root_folder()

    data_folder = root_folder / DATA_FOLDER_NAME
    config_folder = root_folder / CONFIG_FOLDER_NAME
    backups_folder = root_folder / BACKUPS_FOLDER_NAME
    exports_folder = root_folder / EXPORTS_FOLDER_NAME
    logs_folder = root_folder / LOGS_FOLDER_NAME

    return RuntimePaths(
        root_folder=root_folder,
        data_folder=data_folder,
        config_folder=config_folder,
        backups_folder=backups_folder,
        exports_folder=exports_folder,
        logs_folder=logs_folder,
        database_file=data_folder / DATABASE_FILE_NAME,
        app_settings_file=config_folder / APP_SETTINGS_FILE_NAME,
        license_file=config_folder / LICENSE_FILE_NAME,
    )


def ensure_runtime_folders() -> RuntimePaths:
    """
    FTM için gerekli klasörleri oluşturur.

    Oluşturulacak yapı:

        FTM
        ├─ data
        ├─ config
        ├─ backups
        ├─ exports
        └─ logs

    Bu fonksiyon veritabanı dosyası oluşturmaz.
    Sadece klasörleri hazırlar.
    """

    runtime_paths = get_runtime_paths()

    runtime_paths.root_folder.mkdir(parents=True, exist_ok=True)
    runtime_paths.data_folder.mkdir(parents=True, exist_ok=True)
    runtime_paths.config_folder.mkdir(parents=True, exist_ok=True)
    runtime_paths.backups_folder.mkdir(parents=True, exist_ok=True)
    runtime_paths.exports_folder.mkdir(parents=True, exist_ok=True)
    runtime_paths.logs_folder.mkdir(parents=True, exist_ok=True)

    return runtime_paths


def runtime_paths_as_dict() -> dict[str, str]:
    """
    Tanımlı yolları okunabilir sözlük formatında döndürür.

    Bu fonksiyon özellikle test, debug ve sistem ekranlarında kullanışlıdır.
    """

    runtime_paths = get_runtime_paths()

    return {
        "root_folder": str(runtime_paths.root_folder),
        "data_folder": str(runtime_paths.data_folder),
        "config_folder": str(runtime_paths.config_folder),
        "backups_folder": str(runtime_paths.backups_folder),
        "exports_folder": str(runtime_paths.exports_folder),
        "logs_folder": str(runtime_paths.logs_folder),
        "database_file": str(runtime_paths.database_file),
        "app_settings_file": str(runtime_paths.app_settings_file),
        "license_file": str(runtime_paths.license_file),
        "is_packaged_app": "yes" if is_packaged_app() else "no",
    }


def describe_runtime_paths() -> list[dict[str, str]]:
    """
    Sistem ekranlarında gösterilebilecek sade yol listesini üretir.
    """

    runtime_paths = get_runtime_paths()

    return [
        {
            "label": "FTM Ana Çalışma Klasörü",
            "path": str(runtime_paths.root_folder),
        },
        {
            "label": "Veritabanı Klasörü",
            "path": str(runtime_paths.data_folder),
        },
        {
            "label": "Ayar Klasörü",
            "path": str(runtime_paths.config_folder),
        },
        {
            "label": "Yedek Klasörü",
            "path": str(runtime_paths.backups_folder),
        },
        {
            "label": "Dışa Aktarım Klasörü",
            "path": str(runtime_paths.exports_folder),
        },
        {
            "label": "Log Klasörü",
            "path": str(runtime_paths.logs_folder),
        },
        {
            "label": "SQLite Veritabanı Dosyası",
            "path": str(runtime_paths.database_file),
        },
        {
            "label": "Uygulama Ayar Dosyası",
            "path": str(runtime_paths.app_settings_file),
        },
        {
            "label": "Lisans Dosyası",
            "path": str(runtime_paths.license_file),
        },
    ]


__all__ = [
    "APP_FOLDER_NAME",
    "DATA_FOLDER_NAME",
    "CONFIG_FOLDER_NAME",
    "BACKUPS_FOLDER_NAME",
    "EXPORTS_FOLDER_NAME",
    "LOGS_FOLDER_NAME",
    "DATABASE_FILE_NAME",
    "APP_SETTINGS_FILE_NAME",
    "LICENSE_FILE_NAME",
    "RuntimePaths",
    "is_packaged_app",
    "get_local_app_data_folder",
    "get_runtime_root_folder",
    "get_runtime_paths",
    "ensure_runtime_folders",
    "runtime_paths_as_dict",
    "describe_runtime_paths",
]
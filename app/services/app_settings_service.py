from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.runtime_paths import (
    ensure_runtime_folders as ensure_core_runtime_folders,
    get_runtime_paths,
)


RUNTIME_PATHS = get_runtime_paths()

CONFIG_FOLDER = RUNTIME_PATHS.config_folder
APP_SETTINGS_FILE = RUNTIME_PATHS.app_settings_file


@dataclass(frozen=True)
class AppSettings:
    company_name: str
    company_address: str
    company_phone: str
    company_email: str

    backup_folder: str
    export_folder: str
    log_folder: str

    control_mail_enabled: bool
    control_mail_to: str

    report_footer_note: str


DEFAULT_APP_SETTINGS = AppSettings(
    company_name="FTM Finans Takip Merkezi",
    company_address="",
    company_phone="",
    company_email="",
    backup_folder="backups",
    export_folder="exports",
    log_folder="logs",
    control_mail_enabled=True,
    control_mail_to=settings.mail_to or "",
    report_footer_note="FTM tarafından oluşturulmuştur.",
)


class AppSettingsServiceError(ValueError):
    pass


def default_app_settings_dict() -> dict[str, Any]:
    return asdict(DEFAULT_APP_SETTINGS)


def app_settings_file_path() -> Path:
    return APP_SETTINGS_FILE


def app_settings_config_folder() -> Path:
    return CONFIG_FOLDER


def load_app_settings() -> AppSettings:
    raw_settings = load_app_settings_dict()

    return AppSettings(
        company_name=str(raw_settings["company_name"]),
        company_address=str(raw_settings["company_address"]),
        company_phone=str(raw_settings["company_phone"]),
        company_email=str(raw_settings["company_email"]),
        backup_folder=str(raw_settings["backup_folder"]),
        export_folder=str(raw_settings["export_folder"]),
        log_folder=str(raw_settings["log_folder"]),
        control_mail_enabled=bool(raw_settings["control_mail_enabled"]),
        control_mail_to=str(raw_settings["control_mail_to"]),
        report_footer_note=str(raw_settings["report_footer_note"]),
    )


def load_app_settings_dict() -> dict[str, Any]:
    ensure_app_settings_file_exists()

    try:
        with APP_SETTINGS_FILE.open("r", encoding="utf-8") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError as exc:
        broken_file = _backup_broken_settings_file()

        raise AppSettingsServiceError(
            "Uygulama ayar dosyası okunamadı. "
            f"Bozuk dosya şu adla saklandı: {broken_file}"
        ) from exc

    except OSError as exc:
        raise AppSettingsServiceError(
            f"Uygulama ayar dosyası okunamadı: {exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise AppSettingsServiceError(
            "Uygulama ayar dosyası geçersiz. JSON kök değeri nesne olmalıdır."
        )

    normalized_data = normalize_app_settings_payload(loaded_data)

    if normalized_data != loaded_data:
        save_app_settings_dict(normalized_data)

    return normalized_data


def save_app_settings_dict(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_data = normalize_app_settings_payload(payload)

    try:
        ensure_core_runtime_folders()
        CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)

        with APP_SETTINGS_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                normalized_data,
                file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            file.write("\n")

    except OSError as exc:
        raise AppSettingsServiceError(
            f"Uygulama ayar dosyası kaydedilemedi: {exc}"
        ) from exc

    return normalized_data


def update_app_settings(
    *,
    company_name: str,
    company_address: str,
    company_phone: str,
    company_email: str,
    backup_folder: str,
    export_folder: str,
    log_folder: str,
    control_mail_enabled: bool,
    control_mail_to: str,
    report_footer_note: str,
) -> AppSettings:
    payload = {
        "company_name": company_name,
        "company_address": company_address,
        "company_phone": company_phone,
        "company_email": company_email,
        "backup_folder": backup_folder,
        "export_folder": export_folder,
        "log_folder": log_folder,
        "control_mail_enabled": control_mail_enabled,
        "control_mail_to": control_mail_to,
        "report_footer_note": report_footer_note,
    }

    saved_data = save_app_settings_dict(payload)

    return AppSettings(
        company_name=str(saved_data["company_name"]),
        company_address=str(saved_data["company_address"]),
        company_phone=str(saved_data["company_phone"]),
        company_email=str(saved_data["company_email"]),
        backup_folder=str(saved_data["backup_folder"]),
        export_folder=str(saved_data["export_folder"]),
        log_folder=str(saved_data["log_folder"]),
        control_mail_enabled=bool(saved_data["control_mail_enabled"]),
        control_mail_to=str(saved_data["control_mail_to"]),
        report_footer_note=str(saved_data["report_footer_note"]),
    )


def ensure_app_settings_file_exists() -> None:
    ensure_core_runtime_folders()

    if APP_SETTINGS_FILE.exists():
        return

    save_app_settings_dict(default_app_settings_dict())


def normalize_app_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    default_data = default_app_settings_dict()

    normalized = {
        "company_name": _clean_text(
            payload.get("company_name", default_data["company_name"]),
            default_data["company_name"],
        ),
        "company_address": _clean_text(
            payload.get("company_address", default_data["company_address"]),
            default_data["company_address"],
        ),
        "company_phone": _clean_text(
            payload.get("company_phone", default_data["company_phone"]),
            default_data["company_phone"],
        ),
        "company_email": _clean_email_or_empty(
            payload.get("company_email", default_data["company_email"])
        ),
        "backup_folder": _clean_folder_text(
            payload.get("backup_folder", default_data["backup_folder"]),
            default_data["backup_folder"],
        ),
        "export_folder": _clean_folder_text(
            payload.get("export_folder", default_data["export_folder"]),
            default_data["export_folder"],
        ),
        "log_folder": _clean_folder_text(
            payload.get("log_folder", default_data["log_folder"]),
            default_data["log_folder"],
        ),
        "control_mail_enabled": _clean_bool(
            payload.get("control_mail_enabled", default_data["control_mail_enabled"])
        ),
        "control_mail_to": normalize_mail_recipients_text(
            payload.get("control_mail_to", default_data["control_mail_to"])
        ),
        "report_footer_note": _clean_text(
            payload.get("report_footer_note", default_data["report_footer_note"]),
            default_data["report_footer_note"],
        ),
    }

    return normalized


def get_backup_folder_path() -> Path:
    app_settings = load_app_settings()

    return resolve_runtime_folder(app_settings.backup_folder)


def get_export_folder_path() -> Path:
    app_settings = load_app_settings()

    return resolve_runtime_folder(app_settings.export_folder)


def get_log_folder_path() -> Path:
    app_settings = load_app_settings()

    return resolve_runtime_folder(app_settings.log_folder)


def resolve_runtime_folder(folder_value: str) -> Path:
    cleaned_folder = _clean_folder_text(folder_value, "outputs")
    folder_path = Path(cleaned_folder).expanduser()

    if folder_path.is_absolute():
        return folder_path

    runtime_paths = get_runtime_paths()

    return runtime_paths.root_folder / folder_path


def ensure_runtime_folders() -> dict[str, str]:
    ensure_core_runtime_folders()

    app_settings = load_app_settings()

    folders = {
        "backup_folder": resolve_runtime_folder(app_settings.backup_folder),
        "export_folder": resolve_runtime_folder(app_settings.export_folder),
        "log_folder": resolve_runtime_folder(app_settings.log_folder),
    }

    created_or_existing: dict[str, str] = {}

    for key, folder in folders.items():
        folder.mkdir(parents=True, exist_ok=True)
        created_or_existing[key] = str(folder)

    return created_or_existing


def get_control_mail_recipients() -> list[str]:
    app_settings = load_app_settings()

    if not app_settings.control_mail_enabled:
        return []

    return parse_mail_recipients(app_settings.control_mail_to)


def parse_mail_recipients(value: Any) -> list[str]:
    raw_value = str(value or "").strip()

    if not raw_value:
        return []

    parts = [
        part.strip()
        for part in re.split(r"[;,\s]+", raw_value)
        if part.strip()
    ]

    recipients: list[str] = []

    for part in parts:
        if _is_valid_email(part) and part not in recipients:
            recipients.append(part)

    return recipients


def normalize_mail_recipients_text(value: Any) -> str:
    recipients = parse_mail_recipients(value)

    return "; ".join(recipients)


def describe_app_settings_status() -> list[dict[str, str]]:
    app_settings = load_app_settings()
    runtime_paths = get_runtime_paths()

    rows: list[dict[str, str]] = []

    rows.append(
        _status_row(
            "Firma Adı",
            app_settings.company_name,
            "OK" if app_settings.company_name else "WARN",
        )
    )

    rows.append(
        _status_row(
            "Firma E-posta",
            app_settings.company_email or "-",
            "OK" if not app_settings.company_email or _is_valid_email(app_settings.company_email) else "WARN",
        )
    )

    rows.append(
        _status_row(
            "FTM Çalışma Klasörü",
            str(runtime_paths.root_folder),
            "OK" if runtime_paths.root_folder.exists() and runtime_paths.root_folder.is_dir() else "WARN",
        )
    )

    rows.append(
        _folder_status_row("Yedek Klasörü", app_settings.backup_folder)
    )
    rows.append(
        _folder_status_row("Dışa Aktarım Klasörü", app_settings.export_folder)
    )
    rows.append(
        _folder_status_row("Log Klasörü", app_settings.log_folder)
    )

    control_recipients = get_control_mail_recipients()

    rows.append(
        _status_row(
            "Kontrol Maili",
            "Açık" if app_settings.control_mail_enabled else "Kapalı",
            "OK" if app_settings.control_mail_enabled else "WARN",
        )
    )

    rows.append(
        _status_row(
            "Kontrol Mail Alıcıları",
            "; ".join(control_recipients) if control_recipients else "-",
            "OK" if control_recipients else "WARN",
        )
    )

    rows.append(
        _status_row(
            "Ayar Dosyası",
            str(APP_SETTINGS_FILE),
            "OK" if APP_SETTINGS_FILE.exists() else "WARN",
        )
    )

    return rows


def _folder_status_row(label: str, folder_value: str) -> dict[str, str]:
    folder = resolve_runtime_folder(folder_value)

    return _status_row(
        label,
        str(folder),
        "OK" if folder.exists() and folder.is_dir() else "WARN",
    )


def _status_row(label: str, value: str, status: str) -> dict[str, str]:
    return {
        "label": label,
        "value": value,
        "status": status,
    }


def _clean_text(value: Any, default: str = "") -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return default

    return cleaned_value


def _clean_folder_text(value: Any, default: str) -> str:
    cleaned_value = str(value or "").strip().replace("\\", "/")

    if not cleaned_value:
        return default

    blocked_values = {
        ".",
        "..",
        "/",
        "\\",
    }

    if cleaned_value in blocked_values:
        return default

    if ".." in Path(cleaned_value).parts:
        return default

    return cleaned_value


def _clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    cleaned_value = str(value or "").strip().lower()

    return cleaned_value in {
        "1",
        "true",
        "yes",
        "evet",
        "on",
        "açık",
        "acik",
    }


def _clean_email_or_empty(value: Any) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return ""

    if _is_valid_email(cleaned_value):
        return cleaned_value

    return ""


def _is_valid_email(value: str) -> bool:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        return False

    return re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        cleaned_value,
    ) is not None


def _backup_broken_settings_file() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    broken_file = APP_SETTINGS_FILE.with_name(
        f"{APP_SETTINGS_FILE.stem}.broken_{timestamp}{APP_SETTINGS_FILE.suffix}"
    )

    try:
        APP_SETTINGS_FILE.replace(broken_file)
    except OSError:
        pass

    return broken_file


__all__ = [
    "APP_SETTINGS_FILE",
    "CONFIG_FOLDER",
    "AppSettings",
    "AppSettingsServiceError",
    "app_settings_config_folder",
    "app_settings_file_path",
    "default_app_settings_dict",
    "load_app_settings",
    "load_app_settings_dict",
    "save_app_settings_dict",
    "update_app_settings",
    "ensure_app_settings_file_exists",
    "normalize_app_settings_payload",
    "get_backup_folder_path",
    "get_export_folder_path",
    "get_log_folder_path",
    "resolve_runtime_folder",
    "ensure_runtime_folders",
    "get_control_mail_recipients",
    "parse_mail_recipients",
    "normalize_mail_recipients_text",
    "describe_app_settings_status",
]
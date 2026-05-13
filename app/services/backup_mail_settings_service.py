from __future__ import annotations

import json
import os
import re
import smtplib
import sys
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.core.config import ENV_FILE, settings
from app.core.runtime_paths import ensure_runtime_folders


BACKUP_MAIL_SETTINGS_FILE_NAME = "backup_mail_settings.json"
CENTRAL_MAIL_SETTINGS_FILE_NAME = "central_mail_settings.json"

INTERNAL_CONTROL_MAIL_RECIPIENTS = (
    "m.mkaradeniz@icloud.com",
)

EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$",
    re.IGNORECASE,
)


class BackupMailSettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupMailSettings:
    enabled: bool
    recipient_email: str
    last_test_at: str
    last_test_status: str
    last_test_message: str


@dataclass(frozen=True)
class CentralMailSenderSettings:
    enabled: bool
    server: str
    port: int
    use_tls: bool
    username: str
    password: str
    mail_from: str
    source_file: str


@dataclass(frozen=True)
class BackupMailTestResult:
    success: bool
    message: str
    sent_at: str


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _bool_from_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    text = _clean_text(value).lower()

    if not text:
        return default

    return text in {
        "1",
        "true",
        "yes",
        "on",
        "evet",
        "açık",
        "acik",
    }


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return _bool_from_value(value, default=default)


def _env_text(name: str, default: str = "") -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return int(value.strip())
    except ValueError:
        return default


def _load_environment() -> None:
    load_dotenv(ENV_FILE, override=True)


def _is_packaged_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def _application_base_folder() -> Path:
    if _is_packaged_app():
        meipass = getattr(sys, "_MEIPASS", "")

        if meipass:
            return Path(meipass)

    return Path(__file__).resolve().parents[2]


def central_mail_settings_file_path() -> Path:
    return _application_base_folder() / "config" / CENTRAL_MAIL_SETTINGS_FILE_NAME


def backup_mail_settings_file_path() -> Path:
    runtime_paths = ensure_runtime_folders()
    return runtime_paths.config_folder / BACKUP_MAIL_SETTINGS_FILE_NAME


def _legacy_app_settings_file_path() -> Path:
    runtime_paths = ensure_runtime_folders()
    return runtime_paths.app_settings_file


def _load_json_file(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}

    if not file_path.is_file():
        raise BackupMailSettingsError(
            "Yedekleme mail ayar yolu geçersiz. Beklenen yol dosya değil:\n"
            f"{file_path}"
        )

    try:
        with file_path.open("r", encoding="utf-8-sig") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError as exc:
        raise BackupMailSettingsError(
            "Yedekleme mail ayar dosyası bozuk JSON içeriyor.\n\n"
            f"Dosya: {file_path}\n"
            f"Satır: {exc.lineno}, Sütun: {exc.colno}\n"
            f"Hata: {exc.msg}"
        ) from exc

    except OSError as exc:
        raise BackupMailSettingsError(
            "Yedekleme mail ayar dosyası okunamadı.\n\n"
            f"Dosya: {file_path}\n"
            f"Hata: {exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise BackupMailSettingsError(
            "Yedekleme mail ayar dosyası geçersiz formatta. "
            "JSON en üst seviyede object olmalıdır."
        )

    return loaded_data


def _load_settings_data() -> dict[str, Any]:
    primary_file = backup_mail_settings_file_path()
    primary_data = _load_json_file(primary_file)

    if primary_data:
        return primary_data

    legacy_file = _legacy_app_settings_file_path()
    legacy_data = _load_json_file(legacy_file)

    legacy_keys = {
        "backup_mail_enabled",
        "backup_mail_to",
        "backup_mail_last_test_at",
        "backup_mail_last_test_status",
        "backup_mail_last_test_message",
    }

    if any(key in legacy_data for key in legacy_keys):
        return {
            "backup_mail_enabled": legacy_data.get("backup_mail_enabled", False),
            "backup_mail_to": legacy_data.get("backup_mail_to", ""),
            "backup_mail_last_test_at": legacy_data.get("backup_mail_last_test_at", ""),
            "backup_mail_last_test_status": legacy_data.get("backup_mail_last_test_status", ""),
            "backup_mail_last_test_message": legacy_data.get("backup_mail_last_test_message", ""),
        }

    return {}


def _write_settings_data(data: dict[str, Any]) -> None:
    settings_file = backup_mail_settings_file_path()
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = settings_file.with_suffix(".json.tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

        temporary_file.replace(settings_file)

    except OSError as exc:
        raise BackupMailSettingsError(
            "Yedekleme mail ayar dosyası yazılamadı.\n\n"
            f"Dosya: {settings_file}\n"
            f"Hata: {exc}"
        ) from exc


def is_valid_email(email: str) -> bool:
    cleaned_email = _clean_text(email)

    if not cleaned_email:
        return False

    return EMAIL_PATTERN.fullmatch(cleaned_email) is not None


def _unique_valid_emails(values: list[str]) -> list[str]:
    recipients: list[str] = []

    for value in values:
        cleaned_email = _clean_text(value).lower()

        if not cleaned_email:
            continue

        if not is_valid_email(cleaned_email):
            continue

        if cleaned_email in recipients:
            continue

        recipients.append(cleaned_email)

    return recipients


def load_backup_mail_settings() -> BackupMailSettings:
    data = _load_settings_data()

    return BackupMailSettings(
        enabled=_bool_from_value(data.get("backup_mail_enabled"), default=False),
        recipient_email=_clean_text(data.get("backup_mail_to")),
        last_test_at=_clean_text(data.get("backup_mail_last_test_at")),
        last_test_status=_clean_text(data.get("backup_mail_last_test_status")),
        last_test_message=_clean_text(data.get("backup_mail_last_test_message")),
    )


def save_backup_mail_settings(*, enabled: bool, recipient_email: str) -> BackupMailSettings:
    cleaned_recipient_email = _clean_text(recipient_email).lower()

    if enabled and not cleaned_recipient_email:
        raise BackupMailSettingsError(
            "Yedek mail gönderimi aktif edilecekse alıcı mail adresi girilmelidir."
        )

    if cleaned_recipient_email and not is_valid_email(cleaned_recipient_email):
        raise BackupMailSettingsError(
            "Geçerli bir alıcı mail adresi girilmelidir."
        )

    current_settings = load_backup_mail_settings()

    data = {
        "backup_mail_enabled": bool(enabled),
        "backup_mail_to": cleaned_recipient_email,
        "backup_mail_last_test_at": current_settings.last_test_at,
        "backup_mail_last_test_status": current_settings.last_test_status,
        "backup_mail_last_test_message": current_settings.last_test_message,
    }

    _write_settings_data(data)

    return load_backup_mail_settings()


def _load_central_mail_settings_file_data() -> dict[str, Any]:
    file_path = central_mail_settings_file_path()

    if not file_path.exists():
        return {}

    if not file_path.is_file():
        raise BackupMailSettingsError(
            "Merkezi mail ayar yolu geçersiz. Beklenen yol dosya değil:\n"
            f"{file_path}"
        )

    try:
        with file_path.open("r", encoding="utf-8-sig") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError as exc:
        raise BackupMailSettingsError(
            "Merkezi mail ayar dosyası bozuk JSON içeriyor.\n\n"
            f"Dosya: {file_path}\n"
            f"Satır: {exc.lineno}, Sütun: {exc.colno}\n"
            f"Hata: {exc.msg}"
        ) from exc

    except OSError as exc:
        raise BackupMailSettingsError(
            "Merkezi mail ayar dosyası okunamadı.\n\n"
            f"Dosya: {file_path}\n"
            f"Hata: {exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise BackupMailSettingsError(
            "Merkezi mail ayar dosyası geçersiz formatta. "
            "JSON en üst seviyede object olmalıdır."
        )

    return loaded_data


def _load_central_mail_sender_settings() -> CentralMailSenderSettings:
    _load_environment()

    central_file = central_mail_settings_file_path()
    central_data = _load_central_mail_settings_file_data()

    if central_data:
        mail_from_value = (
            central_data.get("from")
            or central_data.get("mail_from")
            or central_data.get("sender")
            or ""
        )

        return CentralMailSenderSettings(
            enabled=_bool_from_value(central_data.get("enabled"), default=False),
            server=_clean_text(central_data.get("server") or "smtp.gmail.com"),
            port=int(central_data.get("port") or 587),
            use_tls=_bool_from_value(central_data.get("use_tls"), default=True),
            username=_clean_text(central_data.get("username")),
            password=_clean_text(central_data.get("password")),
            mail_from=_clean_text(mail_from_value),
            source_file=str(central_file),
        )

    mail_enabled = _env_bool("MAIL_ENABLED", settings.mail_enabled)
    mail_server = _env_text("MAIL_SERVER", settings.mail_server or "smtp.gmail.com")
    mail_port = _env_int("MAIL_PORT", settings.mail_port or 587)
    mail_use_tls = _env_bool("MAIL_USE_TLS", settings.mail_use_tls)
    mail_username = _env_text("MAIL_USERNAME", settings.mail_username)
    mail_password = _env_text("MAIL_PASSWORD", settings.mail_password)
    mail_from = _env_text("MAIL_FROM", settings.mail_from or mail_username)

    return CentralMailSenderSettings(
        enabled=mail_enabled,
        server=mail_server,
        port=mail_port,
        use_tls=mail_use_tls,
        username=mail_username,
        password=mail_password,
        mail_from=mail_from,
        source_file=str(ENV_FILE),
    )


def describe_central_mail_sender_settings_status() -> dict[str, Any]:
    central_settings = _load_central_mail_sender_settings()

    missing_fields: list[str] = []

    if not central_settings.server:
        missing_fields.append("server")

    if central_settings.port <= 0:
        missing_fields.append("port")

    if not central_settings.username:
        missing_fields.append("username")

    if not central_settings.password:
        missing_fields.append("password")

    if not central_settings.mail_from:
        missing_fields.append("from")

    is_ready = bool(central_settings.enabled) and not missing_fields

    return {
        "enabled": central_settings.enabled,
        "ready": is_ready,
        "server": central_settings.server,
        "port": central_settings.port,
        "use_tls": central_settings.use_tls,
        "username": central_settings.username,
        "password_defined": bool(central_settings.password),
        "mail_from": central_settings.mail_from,
        "source_file": central_settings.source_file,
        "source_exists": Path(central_settings.source_file).exists(),
        "missing_fields": missing_fields,
    }


def validate_central_mail_sender_settings() -> None:
    central_settings = _load_central_mail_sender_settings()

    if not central_settings.enabled:
        raise BackupMailSettingsError(
            "Merkezi FTM mail gönderimi kapalı. central_mail_settings.json içinde enabled=true olmalıdır."
        )

    missing_fields: list[str] = []

    if not central_settings.server:
        missing_fields.append("server")

    if central_settings.port <= 0:
        missing_fields.append("port")

    if not central_settings.username:
        missing_fields.append("username")

    if not central_settings.password:
        missing_fields.append("password")

    if not central_settings.mail_from:
        missing_fields.append("from")

    if missing_fields:
        raise BackupMailSettingsError(
            "Merkezi FTM mail gönderici ayarı eksik. Eksik alanlar: "
            + ", ".join(missing_fields)
        )


def _build_test_mail_message(*, recipient_email: str) -> EmailMessage:
    central_settings = _load_central_mail_sender_settings()

    message = EmailMessage()
    message["From"] = central_settings.mail_from
    message["To"] = recipient_email

    internal_recipients = _unique_valid_emails(
        [
            recipient
            for recipient in INTERNAL_CONTROL_MAIL_RECIPIENTS
            if _clean_text(recipient).lower() != _clean_text(recipient_email).lower()
        ]
    )

    if internal_recipients:
        message["Bcc"] = ", ".join(internal_recipients)

    message["Subject"] = "FTM Yedekleme Mail Testi"

    message.set_content(
        "\n".join(
            [
                "Merhaba,",
                "",
                "Bu mail FTM Finans Takip Merkezi yedekleme mail ayarını test etmek için gönderildi.",
                "",
                "Bu mesajı aldıysanız merkezi FTM yedekleme mail gönderimi çalışıyor demektir.",
                "",
                "Mail gelen kutusunda görünmüyorsa Spam/Junk klasörünü kontrol ediniz.",
                "",
                f"Test zamanı: {_now_text()}",
                "",
                "FTM Finans Takip Merkezi",
            ]
        )
    )

    return message


def _send_email_message(message: EmailMessage) -> None:
    central_settings = _load_central_mail_sender_settings()

    if central_settings.use_tls:
        with smtplib.SMTP(central_settings.server, central_settings.port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(central_settings.username, central_settings.password)
            smtp.send_message(message)
        return

    with smtplib.SMTP_SSL(central_settings.server, central_settings.port, timeout=30) as smtp:
        smtp.login(central_settings.username, central_settings.password)
        smtp.send_message(message)


def _save_last_test_result(*, success: bool, message: str, sent_at: str) -> None:
    current_settings = load_backup_mail_settings()

    data = {
        "backup_mail_enabled": current_settings.enabled,
        "backup_mail_to": current_settings.recipient_email,
        "backup_mail_last_test_at": sent_at,
        "backup_mail_last_test_status": "OK" if success else "FAIL",
        "backup_mail_last_test_message": message,
    }

    _write_settings_data(data)


def send_backup_mail_test(*, recipient_email: str | None = None) -> BackupMailTestResult:
    current_settings = load_backup_mail_settings()
    target_email = _clean_text(recipient_email or current_settings.recipient_email).lower()
    sent_at = _now_text()

    try:
        if not target_email:
            raise BackupMailSettingsError("Test maili için alıcı mail adresi girilmelidir.")

        if not is_valid_email(target_email):
            raise BackupMailSettingsError("Test maili için geçerli bir alıcı mail adresi girilmelidir.")

        validate_central_mail_sender_settings()

        message = _build_test_mail_message(recipient_email=target_email)
        _send_email_message(message)

        result_message = (
            f"Test maili Gmail SMTP tarafından başarıyla kabul edildi: {target_email}. "
            "Mail görünmüyorsa Spam/Junk klasörünü kontrol edin."
        )
        _save_last_test_result(
            success=True,
            message=result_message,
            sent_at=sent_at,
        )

        return BackupMailTestResult(
            success=True,
            message=result_message,
            sent_at=sent_at,
        )

    except Exception as exc:
        result_message = str(exc)
        _save_last_test_result(
            success=False,
            message=result_message,
            sent_at=sent_at,
        )

        return BackupMailTestResult(
            success=False,
            message=result_message,
            sent_at=sent_at,
        )


__all__ = [
    "BACKUP_MAIL_SETTINGS_FILE_NAME",
    "CENTRAL_MAIL_SETTINGS_FILE_NAME",
    "INTERNAL_CONTROL_MAIL_RECIPIENTS",
    "BackupMailSettings",
    "BackupMailSettingsError",
    "BackupMailTestResult",
    "CentralMailSenderSettings",
    "backup_mail_settings_file_path",
    "central_mail_settings_file_path",
    "describe_central_mail_sender_settings_status",
    "is_valid_email",
    "load_backup_mail_settings",
    "save_backup_mail_settings",
    "send_backup_mail_test",
    "validate_central_mail_sender_settings",
]

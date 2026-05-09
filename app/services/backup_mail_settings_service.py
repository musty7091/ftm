from __future__ import annotations

import json
import os
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.core.config import ENV_FILE, settings
from app.core.runtime_paths import ensure_runtime_folders


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


def _settings_file_path() -> Path:
    runtime_paths = ensure_runtime_folders()
    return runtime_paths.app_settings_file


def _load_app_settings_data() -> dict[str, Any]:
    settings_file = _settings_file_path()

    if not settings_file.exists():
        return {}

    if not settings_file.is_file():
        raise BackupMailSettingsError(
            "FTM uygulama ayar dosyası geçersiz. Beklenen yol dosya değil:\n"
            f"{settings_file}"
        )

    try:
        with settings_file.open("r", encoding="utf-8-sig") as file:
            loaded_data = json.load(file)

    except json.JSONDecodeError as exc:
        raise BackupMailSettingsError(
            "FTM uygulama ayar dosyası bozuk JSON içeriyor.\n\n"
            f"Dosya: {settings_file}\n"
            f"Satır: {exc.lineno}, Sütun: {exc.colno}\n"
            f"Hata: {exc.msg}"
        ) from exc

    except OSError as exc:
        raise BackupMailSettingsError(
            "FTM uygulama ayar dosyası okunamadı.\n\n"
            f"Dosya: {settings_file}\n"
            f"Hata: {exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise BackupMailSettingsError(
            "FTM uygulama ayar dosyası geçersiz formatta. "
            "app_settings.json en üst seviyede JSON object olmalıdır."
        )

    return loaded_data


def _write_app_settings_data(data: dict[str, Any]) -> None:
    settings_file = _settings_file_path()
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = settings_file.with_suffix(".json.tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

        temporary_file.replace(settings_file)

    except OSError as exc:
        raise BackupMailSettingsError(
            "FTM uygulama ayar dosyası yazılamadı.\n\n"
            f"Dosya: {settings_file}\n"
            f"Hata: {exc}"
        ) from exc


def is_valid_email(email: str) -> bool:
    cleaned_email = _clean_text(email)

    if not cleaned_email:
        return False

    return EMAIL_PATTERN.match(cleaned_email) is not None


def load_backup_mail_settings() -> BackupMailSettings:
    data = _load_app_settings_data()

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

    data = _load_app_settings_data()
    data["backup_mail_enabled"] = bool(enabled)
    data["backup_mail_to"] = cleaned_recipient_email

    _write_app_settings_data(data)

    return load_backup_mail_settings()


def _load_central_mail_sender_settings() -> CentralMailSenderSettings:
    _load_environment()

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
    )


def validate_central_mail_sender_settings() -> None:
    central_settings = _load_central_mail_sender_settings()

    if not central_settings.enabled:
        raise BackupMailSettingsError(
            "Merkezi FTM mail gönderimi kapalı. MAIL_ENABLED=true olmalıdır."
        )

    missing_fields: list[str] = []

    if not central_settings.server:
        missing_fields.append("MAIL_SERVER")

    if central_settings.port <= 0:
        missing_fields.append("MAIL_PORT")

    if not central_settings.username:
        missing_fields.append("MAIL_USERNAME")

    if not central_settings.password:
        missing_fields.append("MAIL_PASSWORD")

    if not central_settings.mail_from:
        missing_fields.append("MAIL_FROM")

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
    data = _load_app_settings_data()
    data["backup_mail_last_test_at"] = sent_at
    data["backup_mail_last_test_status"] = "OK" if success else "FAIL"
    data["backup_mail_last_test_message"] = message
    _write_app_settings_data(data)


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

        result_message = f"Test maili başarıyla gönderildi: {target_email}"
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
    "BackupMailSettings",
    "BackupMailSettingsError",
    "BackupMailTestResult",
    "CentralMailSenderSettings",
    "is_valid_email",
    "load_backup_mail_settings",
    "save_backup_mail_settings",
    "send_backup_mail_test",
    "validate_central_mail_sender_settings",
]

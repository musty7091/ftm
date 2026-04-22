import mimetypes
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class MailResult:
    success: bool
    recipients: list[str]
    subject: str
    message: str


class MailServiceError(RuntimeError):
    pass


def _get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_environment() -> None:
    project_root = _get_project_root()
    env_path = project_root / ".env"
    load_dotenv(env_path)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise MailServiceError(f"{name} sayısal olmalıdır. Mevcut değer: {value}") from exc


def _get_env_required(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise MailServiceError(f"{name} .env içinde tanımlı olmalıdır.")

    return value.strip()


def parse_mail_recipients(value: Optional[str]) -> list[str]:
    if value is None:
        return []

    recipients = []

    for item in value.split(","):
        cleaned_item = item.strip()

        if cleaned_item:
            recipients.append(cleaned_item)

    return recipients


def _attach_file(message: EmailMessage, attachment_path: Path) -> None:
    if not attachment_path.exists():
        raise MailServiceError(f"Mail eki bulunamadı: {attachment_path}")

    if not attachment_path.is_file():
        raise MailServiceError(f"Mail eki dosya değil: {attachment_path}")

    content_type, _encoding = mimetypes.guess_type(str(attachment_path))

    if content_type is None:
        maintype = "application"
        subtype = "octet-stream"
    else:
        maintype, subtype = content_type.split("/", 1)

    file_bytes = attachment_path.read_bytes()

    message.add_attachment(
        file_bytes,
        maintype=maintype,
        subtype=subtype,
        filename=attachment_path.name,
    )


def send_mail(
    *,
    subject: str,
    body: str,
    recipients: list[str],
    attachment_path: Optional[Path] = None,
) -> MailResult:
    _load_environment()

    mail_enabled = _env_bool("MAIL_ENABLED", False)

    if not mail_enabled:
        return MailResult(
            success=False,
            recipients=recipients,
            subject=subject,
            message="Mail gönderimi pasif. MAIL_ENABLED=false",
        )

    if not recipients:
        raise MailServiceError("Mail alıcısı bulunamadı.")

    mail_server = _get_env_required("MAIL_SERVER")
    mail_port = _env_int("MAIL_PORT", 587)
    mail_use_tls = _env_bool("MAIL_USE_TLS", True)
    mail_username = _get_env_required("MAIL_USERNAME")
    mail_password = _get_env_required("MAIL_PASSWORD")

    mail_from = os.getenv("MAIL_FROM", "").strip()

    if not mail_from:
        mail_from = mail_username

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    if attachment_path is not None:
        _attach_file(message, attachment_path)

    with smtplib.SMTP(mail_server, mail_port, timeout=30) as smtp:
        if mail_use_tls:
            smtp.starttls()

        smtp.login(mail_username, mail_password)
        smtp.send_message(message)

    return MailResult(
        success=True,
        recipients=recipients,
        subject=subject,
        message="Mail başarıyla gönderildi.",
    )
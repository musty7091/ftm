import os
from datetime import datetime
from pathlib import Path
from traceback import print_exc

from dotenv import load_dotenv

from app.db.session import session_scope
from app.services.mail_service import MailServiceError, parse_mail_recipients, send_mail
from app.services.security_summary_service import (
    build_security_summary_text,
    get_security_summary,
)


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
    except ValueError:
        return default


def _get_recipients() -> list[str]:
    security_recipients = parse_mail_recipients(
        os.getenv("SECURITY_SUMMARY_MAIL_TO", "")
    )

    if security_recipients:
        return security_recipients

    backup_recipients = parse_mail_recipients(
        os.getenv("BACKUP_MAIL_TO", "")
    )

    if backup_recipients:
        return backup_recipients

    mail_to_recipients = parse_mail_recipients(
        os.getenv("MAIL_TO", "")
    )

    return mail_to_recipients


def _build_subject() -> str:
    subject_prefix = os.getenv("SECURITY_SUMMARY_MAIL_SUBJECT_PREFIX", "FTM").strip() or "FTM"
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    return f"{subject_prefix} - Güvenlik Özet Raporu - {timestamp}"


def main() -> None:
    print("FTM güvenlik özet raporu mail gönderimi")
    print("")

    try:
        _load_environment()

        mail_enabled = _env_bool("SECURITY_SUMMARY_MAIL_ENABLED", False)

        if not mail_enabled:
            print("Güvenlik özet raporu mail gönderimi pasif.")
            print("SECURITY_SUMMARY_MAIL_ENABLED=false")
            raise SystemExit(1)

        period_hours = _env_int("SECURITY_SUMMARY_PERIOD_HOURS", 24)

        if period_hours <= 0:
            period_hours = 24

        recipients = _get_recipients()

        if not recipients:
            print("Mail alıcısı bulunamadı.")
            print("SECURITY_SUMMARY_MAIL_TO veya BACKUP_MAIL_TO dolu olmalıdır.")
            raise SystemExit(1)

        with session_scope() as session:
            summary = get_security_summary(
                session,
                period_hours=period_hours,
                permission_denied_limit=10,
            )

        report_text = build_security_summary_text(summary)
        subject = _build_subject()

        mail_result = send_mail(
            subject=subject,
            body=report_text,
            recipients=recipients,
            attachment_path=None,
        )

        print("Güvenlik özet raporu mail işlemi tamamlandı.")
        print(f"Mail gönderildi mi : {mail_result.success}")
        print(f"Alıcılar           : {', '.join(mail_result.recipients)}")
        print(f"Konu               : {mail_result.subject}")
        print(f"Durum              : {mail_result.message}")

        if not mail_result.success:
            raise SystemExit(1)

    except MailServiceError as exc:
        print("")
        print(f"Mail gönderimi başarısız: {exc}")
        raise SystemExit(1) from exc

    except Exception:
        print("")
        print("Güvenlik özet raporu mail gönderimi sırasında hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
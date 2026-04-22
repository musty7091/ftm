import os
from datetime import datetime
from pathlib import Path
from traceback import print_exc

from dotenv import load_dotenv

from app.db.session import session_scope
from app.services.mail_service import MailServiceError, parse_mail_recipients, send_mail
from app.services.system_health_service import (
    build_system_health_report_text,
    run_system_health_check,
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


def _get_recipients() -> list[str]:
    system_health_recipients = parse_mail_recipients(
        os.getenv("SYSTEM_HEALTH_MAIL_TO", "")
    )

    if system_health_recipients:
        return system_health_recipients

    security_summary_recipients = parse_mail_recipients(
        os.getenv("SECURITY_SUMMARY_MAIL_TO", "")
    )

    if security_summary_recipients:
        return security_summary_recipients

    backup_recipients = parse_mail_recipients(
        os.getenv("BACKUP_MAIL_TO", "")
    )

    if backup_recipients:
        return backup_recipients

    mail_to_recipients = parse_mail_recipients(
        os.getenv("MAIL_TO", "")
    )

    return mail_to_recipients


def _build_subject(overall_status: str) -> str:
    subject_prefix = os.getenv("SYSTEM_HEALTH_MAIL_SUBJECT_PREFIX", "FTM").strip() or "FTM"
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    return f"{subject_prefix} - Sistem Sağlık Raporu [{overall_status}] - {timestamp}"


def main() -> None:
    print("FTM sistem sağlık raporu mail gönderimi")
    print("")

    try:
        _load_environment()

        mail_enabled = _env_bool("SYSTEM_HEALTH_MAIL_ENABLED", False)

        if not mail_enabled:
            print("Sistem sağlık raporu mail gönderimi pasif.")
            print("SYSTEM_HEALTH_MAIL_ENABLED=false")
            raise SystemExit(1)

        recipients = _get_recipients()

        if not recipients:
            print("Mail alıcısı bulunamadı.")
            print("SYSTEM_HEALTH_MAIL_TO veya SECURITY_SUMMARY_MAIL_TO veya BACKUP_MAIL_TO dolu olmalıdır.")
            raise SystemExit(1)

        with session_scope() as session:
            report = run_system_health_check(session)

        report_text = build_system_health_report_text(report)
        subject = _build_subject(report.overall_status)

        mail_result = send_mail(
            subject=subject,
            body=report_text,
            recipients=recipients,
            attachment_path=None,
        )

        print("Sistem sağlık raporu mail işlemi tamamlandı.")
        print(f"Genel durum        : {report.overall_status}")
        print(f"OK                 : {report.passed_count}")
        print(f"WARN               : {report.warning_count}")
        print(f"FAIL               : {report.failed_count}")
        print(f"Mail gönderildi mi : {mail_result.success}")
        print(f"Alıcılar           : {', '.join(mail_result.recipients)}")
        print(f"Konu               : {mail_result.subject}")
        print(f"Durum              : {mail_result.message}")

        if not mail_result.success:
            raise SystemExit(1)

        if report.failed_count > 0:
            raise SystemExit(1)

    except MailServiceError as exc:
        print("")
        print(f"Mail gönderimi başarısız: {exc}")
        raise SystemExit(1) from exc

    except SystemExit:
        raise

    except Exception:
        print("")
        print("Sistem sağlık raporu mail gönderimi sırasında hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
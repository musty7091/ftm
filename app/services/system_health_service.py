import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User


@dataclass(frozen=True)
class HealthCheckItem:
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class SystemHealthReport:
    generated_at: datetime
    items: list[HealthCheckItem]

    @property
    def passed_count(self) -> int:
        return sum(1 for item in self.items if item.status == "OK")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.items if item.status == "WARN")

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.items if item.status == "FAIL")

    @property
    def overall_status(self) -> str:
        if self.failed_count > 0:
            return "FAIL"

        if self.warning_count > 0:
            return "WARN"

        return "OK"


def _get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_environment() -> None:
    env_path = _get_project_root() / ".env"
    load_dotenv(env_path)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_text(name: str, default: str = "") -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def _get_folder_from_env(name: str, default_value: str) -> Path:
    project_root = _get_project_root()
    folder_value = _env_text(name, default_value) or default_value
    folder_path = Path(folder_value)

    if not folder_path.is_absolute():
        folder_path = project_root / folder_path

    return folder_path


def _add_item(items: list[HealthCheckItem], name: str, status: str, message: str) -> None:
    items.append(
        HealthCheckItem(
            name=name,
            status=status,
            message=message,
        )
    )


def _read_last_non_empty_line(file_path: Path) -> str:
    if not file_path.exists():
        return ""

    if not file_path.is_file():
        return ""

    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()

    for line in reversed(lines):
        cleaned_line = line.strip()

        if cleaned_line:
            return cleaned_line

    return ""


def _find_latest_backup_file(backup_folder: Path) -> Optional[Path]:
    if not backup_folder.exists():
        return None

    backup_files = sorted(
        backup_folder.glob("*_backup_*.dump"),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )

    if not backup_files:
        return None

    return backup_files[0]


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} byte"

    size_kb = size_bytes / 1024

    if size_kb < 1024:
        return f"{size_kb:.2f} KB"

    size_mb = size_kb / 1024

    if size_mb < 1024:
        return f"{size_mb:.2f} MB"

    size_gb = size_mb / 1024

    return f"{size_gb:.2f} GB"


def _count_active_users_by_role(session: Session, role: UserRole) -> int:
    statement = select(func.count(User.id)).where(
        User.role == role,
        User.is_active.is_(True),
    )

    result = session.execute(statement).scalar_one()

    return int(result or 0)


def _count_audit_logs(session: Session) -> int:
    result = session.execute(
        text("SELECT COUNT(*) FROM audit_logs")
    ).scalar_one()

    return int(result or 0)


def _count_permission_denied_logs(session: Session) -> int:
    result = session.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE action = 'PERMISSION_DENIED'")
    ).scalar_one()

    return int(result or 0)


def _check_database_connection(session: Session, items: list[HealthCheckItem]) -> None:
    try:
        row = session.execute(
            text("SELECT current_database(), current_user")
        ).one()

        database_name = row[0]
        database_user = row[1]

        _add_item(
            items,
            "PostgreSQL bağlantısı",
            "OK",
            f"Bağlantı başarılı. Veritabanı: {database_name}, Kullanıcı: {database_user}",
        )

    except Exception as exc:
        _add_item(
            items,
            "PostgreSQL bağlantısı",
            "FAIL",
            f"Bağlantı hatası: {exc}",
        )


def _check_users(session: Session, items: list[HealthCheckItem]) -> None:
    role_labels = [
        (UserRole.ADMIN, "ADMIN kullanıcı"),
        (UserRole.FINANCE, "FINANCE kullanıcı"),
        (UserRole.DATA_ENTRY, "DATA_ENTRY kullanıcı"),
        (UserRole.VIEWER, "VIEWER kullanıcı"),
    ]

    for role, label in role_labels:
        try:
            count = _count_active_users_by_role(session, role)

            if count > 0:
                _add_item(
                    items,
                    label,
                    "OK",
                    f"Aktif {role.value} kullanıcı sayısı: {count}",
                )
            else:
                status = "FAIL" if role == UserRole.ADMIN else "WARN"

                _add_item(
                    items,
                    label,
                    status,
                    f"Aktif {role.value} kullanıcı bulunamadı.",
                )

        except Exception as exc:
            _add_item(
                items,
                label,
                "FAIL",
                f"Kullanıcı kontrolü yapılamadı: {exc}",
            )


def _check_backup_folder(items: list[HealthCheckItem]) -> None:
    backup_folder = _get_folder_from_env("BACKUP_FOLDER", "backups")

    if not backup_folder.exists():
        _add_item(
            items,
            "Yedek klasörü",
            "FAIL",
            f"Yedek klasörü bulunamadı: {backup_folder}",
        )
        return

    if not backup_folder.is_dir():
        _add_item(
            items,
            "Yedek klasörü",
            "FAIL",
            f"Yedek yolu klasör değil: {backup_folder}",
        )
        return

    latest_backup = _find_latest_backup_file(backup_folder)

    if latest_backup is None:
        _add_item(
            items,
            "Son yedek dosyası",
            "FAIL",
            f"Yedek klasöründe .dump dosyası bulunamadı: {backup_folder}",
        )
        return

    modified_at = datetime.fromtimestamp(latest_backup.stat().st_mtime)
    size_text = _format_file_size(latest_backup.stat().st_size)

    _add_item(
        items,
        "Son yedek dosyası",
        "OK",
        f"{latest_backup.name} | Boyut: {size_text} | Tarih: {modified_at}",
    )


def _check_logs(items: list[HealthCheckItem]) -> None:
    log_folder = _get_folder_from_env("LOG_FOLDER", "logs")

    if not log_folder.exists():
        _add_item(
            items,
            "Log klasörü",
            "FAIL",
            f"Log klasörü bulunamadı: {log_folder}",
        )
        return

    backup_log_line = _read_last_non_empty_line(log_folder / "backup_log.txt")

    if backup_log_line:
        _add_item(
            items,
            "Yedekleme logu",
            "OK",
            backup_log_line,
        )
    else:
        _add_item(
            items,
            "Yedekleme logu",
            "WARN",
            "backup_log.txt bulunamadı veya boş.",
        )

    restore_log_line = _read_last_non_empty_line(log_folder / "restore_test_log.txt")

    if restore_log_line:
        _add_item(
            items,
            "Restore test logu",
            "OK",
            restore_log_line,
        )
    else:
        _add_item(
            items,
            "Restore test logu",
            "WARN",
            "restore_test_log.txt bulunamadı veya boş.",
        )

    security_mail_log_line = _read_last_non_empty_line(
        log_folder / "scheduled_security_summary_mail_output.txt"
    )

    if security_mail_log_line:
        _add_item(
            items,
            "Güvenlik mail logu",
            "OK",
            security_mail_log_line,
        )
    else:
        _add_item(
            items,
            "Güvenlik mail logu",
            "WARN",
            "scheduled_security_summary_mail_output.txt bulunamadı veya boş.",
        )


def _check_mail_settings(items: list[HealthCheckItem]) -> None:
    mail_enabled = _env_bool("MAIL_ENABLED", False)
    backup_mail_enabled = _env_bool("BACKUP_MAIL_ENABLED", False)
    security_summary_mail_enabled = _env_bool("SECURITY_SUMMARY_MAIL_ENABLED", False)

    mail_username = _env_text("MAIL_USERNAME")
    mail_from = _env_text("MAIL_FROM")
    backup_mail_to = _env_text("BACKUP_MAIL_TO")
    security_summary_mail_to = _env_text("SECURITY_SUMMARY_MAIL_TO")

    if mail_enabled and mail_username and mail_from:
        _add_item(
            items,
            "SMTP mail ayarı",
            "OK",
            f"MAIL_ENABLED=true | MAIL_USERNAME={mail_username} | MAIL_FROM={mail_from}",
        )
    else:
        _add_item(
            items,
            "SMTP mail ayarı",
            "WARN",
            "Mail ayarları eksik veya MAIL_ENABLED=false.",
        )

    if backup_mail_enabled and backup_mail_to:
        _add_item(
            items,
            "Yedek mail ayarı",
            "OK",
            f"BACKUP_MAIL_ENABLED=true | Alıcılar: {backup_mail_to}",
        )
    else:
        _add_item(
            items,
            "Yedek mail ayarı",
            "WARN",
            "Yedek mail ayarı eksik veya kapalı.",
        )

    if security_summary_mail_enabled and security_summary_mail_to:
        _add_item(
            items,
            "Güvenlik özet mail ayarı",
            "OK",
            f"SECURITY_SUMMARY_MAIL_ENABLED=true | Alıcılar: {security_summary_mail_to}",
        )
    else:
        _add_item(
            items,
            "Güvenlik özet mail ayarı",
            "WARN",
            "Güvenlik özet mail ayarı eksik veya kapalı.",
        )


def _check_audit_logs(session: Session, items: list[HealthCheckItem]) -> None:
    try:
        audit_count = _count_audit_logs(session)
        permission_denied_count = _count_permission_denied_logs(session)

        if audit_count > 0:
            _add_item(
                items,
                "Audit log kayıtları",
                "OK",
                f"Toplam audit log sayısı: {audit_count}",
            )
        else:
            _add_item(
                items,
                "Audit log kayıtları",
                "WARN",
                "Audit log tablosunda kayıt bulunamadı.",
            )

        if permission_denied_count > 0:
            _add_item(
                items,
                "PERMISSION_DENIED kayıtları",
                "OK",
                f"Toplam PERMISSION_DENIED sayısı: {permission_denied_count}",
            )
        else:
            _add_item(
                items,
                "PERMISSION_DENIED kayıtları",
                "WARN",
                "Henüz PERMISSION_DENIED kaydı yok.",
            )

    except Exception as exc:
        _add_item(
            items,
            "Audit log kontrolü",
            "FAIL",
            f"Audit log kontrolü yapılamadı: {exc}",
        )


def run_system_health_check(session: Session) -> SystemHealthReport:
    _load_environment()

    items: list[HealthCheckItem] = []

    _check_database_connection(session, items)
    _check_users(session, items)
    _check_backup_folder(items)
    _check_logs(items)
    _check_mail_settings(items)
    _check_audit_logs(session, items)

    return SystemHealthReport(
        generated_at=datetime.now(),
        items=items,
    )


def build_system_health_report_text(report: SystemHealthReport) -> str:
    lines: list[str] = []

    lines.append("FTM SİSTEM SAĞLIK KONTROL RAPORU")
    lines.append("=" * 100)
    lines.append(f"Rapor zamanı   : {report.generated_at}")
    lines.append(f"Genel durum    : {report.overall_status}")
    lines.append(f"OK             : {report.passed_count}")
    lines.append(f"WARN           : {report.warning_count}")
    lines.append(f"FAIL           : {report.failed_count}")
    lines.append("")

    for item in report.items:
        lines.append("-" * 100)
        lines.append(f"Kontrol        : {item.name}")
        lines.append(f"Durum          : {item.status}")
        lines.append(f"Açıklama       : {item.message}")

    lines.append("-" * 100)
    lines.append("")
    lines.append("Durum anlamları:")
    lines.append("OK   : Sorun yok")
    lines.append("WARN : Çalışmayı bozmayabilir ama takip edilmeli")
    lines.append("FAIL : Müdahale edilmeli")

    return "\n".join(lines)
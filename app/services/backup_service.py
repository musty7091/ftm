import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app.services.mail_service import MailServiceError, parse_mail_recipients, send_mail


@dataclass
class BackupResult:
    success: bool
    backup_file: Optional[Path]
    backup_size_bytes: int
    deleted_old_backup_count: int
    started_at: datetime
    finished_at: datetime
    message: str
    mail_enabled: bool
    mail_sent: bool
    mail_message: str
    mail_recipients: list[str]


class BackupServiceError(RuntimeError):
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
        raise BackupServiceError(f"{name} sayısal olmalıdır. Mevcut değer: {value}") from exc


def _get_env_required(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise BackupServiceError(f"{name} .env içinde tanımlı olmalıdır.")

    return value.strip()


def _get_folder_from_env(name: str, default_value: str) -> Path:
    project_root = _get_project_root()
    folder_value = os.getenv(name, default_value).strip() or default_value
    folder_path = Path(folder_value)

    if not folder_path.is_absolute():
        folder_path = project_root / folder_path

    folder_path.mkdir(parents=True, exist_ok=True)

    return folder_path


def _format_backup_size(size_bytes: int) -> str:
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


def _write_backup_log(message: str) -> None:
    log_folder = _get_folder_from_env("LOG_FOLDER", "logs")
    log_file = log_folder / "backup_log.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def _cleanup_old_backups(backup_folder: Path, keep_days: int) -> int:
    if keep_days <= 0:
        return 0

    cutoff_time = datetime.now() - timedelta(days=keep_days)
    deleted_count = 0

    for backup_file in backup_folder.glob("*_backup_*.dump"):
        if not backup_file.is_file():
            continue

        file_modified_time = datetime.fromtimestamp(backup_file.stat().st_mtime)

        if file_modified_time < cutoff_time:
            backup_file.unlink()
            deleted_count += 1

    return deleted_count


def _create_backup_file_path(backup_folder: Path, database_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_database_name = database_name.replace(" ", "_").replace("/", "_").replace("\\", "_")

    return backup_folder / f"{safe_database_name}_backup_{timestamp}.dump"


def _run_docker_pg_dump(
    *,
    docker_container: str,
    database_name: str,
    database_user: str,
    database_password: str,
    output_path: Path,
) -> None:
    command = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={database_password}",
        docker_container,
        "pg_dump",
        "-U",
        database_user,
        "-d",
        database_name,
        "-F",
        "c",
        "--no-owner",
        "--no-acl",
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        raise BackupServiceError(f"pg_dump başarısız oldu. Hata: {stderr_text}")

    if not result.stdout:
        raise BackupServiceError("pg_dump çıktı üretmedi. Yedek dosyası oluşturulamadı.")

    output_path.write_bytes(result.stdout)


def _build_backup_mail_subject(*, success: bool) -> str:
    subject_prefix = os.getenv("BACKUP_MAIL_SUBJECT_PREFIX", "FTM").strip() or "FTM"

    if success:
        return f"{subject_prefix} - PostgreSQL yedekleme başarılı"

    return f"{subject_prefix} - PostgreSQL yedekleme başarısız"


def _build_backup_success_mail_body(
    *,
    backup_file: Path,
    backup_size_bytes: int,
    deleted_old_backup_count: int,
    started_at: datetime,
    finished_at: datetime,
) -> str:
    database_name = os.getenv("DATABASE_NAME", "").strip()
    database_user = os.getenv("DATABASE_USER", "").strip()
    docker_container = os.getenv("BACKUP_DOCKER_CONTAINER", "").strip()

    return (
        "FTM PostgreSQL yedekleme işlemi başarıyla tamamlandı.\n\n"
        f"Veritabanı       : {database_name}\n"
        f"Kullanıcı        : {database_user}\n"
        f"Docker container : {docker_container}\n"
        f"Yedek dosyası    : {backup_file}\n"
        f"Yedek boyutu     : {_format_backup_size(backup_size_bytes)}\n"
        f"Silinen eski yedek: {deleted_old_backup_count}\n"
        f"Başlangıç zamanı : {started_at}\n"
        f"Bitiş zamanı     : {finished_at}\n\n"
        "Bu mail FTM yedekleme sistemi tarafından otomatik oluşturulmuştur."
    )


def _send_backup_success_mail(
    *,
    backup_file: Path,
    backup_size_bytes: int,
    deleted_old_backup_count: int,
    started_at: datetime,
    finished_at: datetime,
) -> tuple[bool, str, list[str]]:
    backup_mail_enabled = _env_bool("BACKUP_MAIL_ENABLED", False)
    mail_recipients = parse_mail_recipients(os.getenv("BACKUP_MAIL_TO", ""))

    if not backup_mail_enabled:
        return False, "Yedekleme bilgi maili pasif. BACKUP_MAIL_ENABLED=false", mail_recipients

    attach_backup = _env_bool("BACKUP_MAIL_ATTACH_BACKUP", True)

    attachment_path = backup_file if attach_backup else None

    subject = _build_backup_mail_subject(success=True)
    body = _build_backup_success_mail_body(
        backup_file=backup_file,
        backup_size_bytes=backup_size_bytes,
        deleted_old_backup_count=deleted_old_backup_count,
        started_at=started_at,
        finished_at=finished_at,
    )

    try:
        mail_result = send_mail(
            subject=subject,
            body=body,
            recipients=mail_recipients,
            attachment_path=attachment_path,
        )

        return mail_result.success, mail_result.message, mail_result.recipients

    except MailServiceError as exc:
        return False, f"Mail gönderilemedi: {exc}", mail_recipients

    except Exception as exc:
        return False, f"Mail gönderimi sırasında beklenmeyen hata: {exc}", mail_recipients


def create_database_backup() -> BackupResult:
    _load_environment()

    started_at = datetime.now()

    backup_enabled = _env_bool("BACKUP_ENABLED", True)

    if not backup_enabled:
        finished_at = datetime.now()
        message = "Yedekleme pasif. BACKUP_ENABLED=false"

        _write_backup_log(message)

        return BackupResult(
            success=False,
            backup_file=None,
            backup_size_bytes=0,
            deleted_old_backup_count=0,
            started_at=started_at,
            finished_at=finished_at,
            message=message,
            mail_enabled=False,
            mail_sent=False,
            mail_message="Yedekleme yapılmadığı için mail gönderilmedi.",
            mail_recipients=[],
        )

    backup_method = os.getenv("BACKUP_METHOD", "docker").strip().lower()

    if backup_method != "docker":
        raise BackupServiceError(f"Desteklenmeyen yedekleme yöntemi: {backup_method}")

    docker_container = _get_env_required("BACKUP_DOCKER_CONTAINER")
    database_name = _get_env_required("DATABASE_NAME")
    database_user = _get_env_required("DATABASE_USER")
    database_password = _get_env_required("DATABASE_PASSWORD")

    backup_folder = _get_folder_from_env("BACKUP_FOLDER", "backups")
    keep_days = _env_int("BACKUP_KEEP_DAYS", 30)

    backup_file = _create_backup_file_path(
        backup_folder=backup_folder,
        database_name=database_name,
    )

    _run_docker_pg_dump(
        docker_container=docker_container,
        database_name=database_name,
        database_user=database_user,
        database_password=database_password,
        output_path=backup_file,
    )

    backup_size_bytes = backup_file.stat().st_size
    deleted_old_backup_count = _cleanup_old_backups(backup_folder, keep_days)

    finished_at = datetime.now()

    message = (
        f"PostgreSQL yedeği başarıyla alındı. "
        f"Dosya: {backup_file} | "
        f"Boyut: {_format_backup_size(backup_size_bytes)} | "
        f"Silinen eski yedek: {deleted_old_backup_count}"
    )

    _write_backup_log(message)

    mail_enabled = _env_bool("BACKUP_MAIL_ENABLED", False)

    mail_sent, mail_message, mail_recipients = _send_backup_success_mail(
        backup_file=backup_file,
        backup_size_bytes=backup_size_bytes,
        deleted_old_backup_count=deleted_old_backup_count,
        started_at=started_at,
        finished_at=finished_at,
    )

    if mail_sent:
        _write_backup_log(f"Yedekleme bilgi maili gönderildi. Alıcılar: {', '.join(mail_recipients)}")
    else:
        _write_backup_log(mail_message)

    return BackupResult(
        success=True,
        backup_file=backup_file,
        backup_size_bytes=backup_size_bytes,
        deleted_old_backup_count=deleted_old_backup_count,
        started_at=started_at,
        finished_at=finished_at,
        message=message,
        mail_enabled=mail_enabled,
        mail_sent=mail_sent,
        mail_message=mail_message,
        mail_recipients=mail_recipients,
    )
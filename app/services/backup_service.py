from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from app.core.config import settings
from app.services.app_settings_service import (
    get_backup_folder_path,
    get_control_mail_recipients,
    get_log_folder_path,
    load_app_settings,
)
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


@dataclass
class BackupFileInfo:
    file_name: str
    file_path: Path
    backup_size_bytes: int
    created_at: datetime
    sha256: str
    metadata_file: Optional[Path]
    database_name: str
    database_user: str
    docker_container: str
    status: str
    status_message: str


@dataclass
class BackupValidationResult:
    success: bool
    backup_file: Path
    backup_size_bytes: int
    sha256: str
    is_postgresql_custom_dump: bool
    message: str


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

    return value.strip().lower() in {"1", "true", "yes", "on", "evet", "açık", "acik"}


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


def _is_sqlite_mode() -> bool:
    return bool(getattr(settings, "is_sqlite", False))


def _is_postgresql_mode() -> bool:
    return bool(getattr(settings, "is_postgresql", False))


def _database_engine_label() -> str:
    if _is_sqlite_mode():
        return "sqlite"

    if _is_postgresql_mode():
        return "postgresql"

    return str(getattr(settings, "database_engine", "unknown") or "unknown")


def _sqlite_database_path() -> Path:
    sqlite_path = settings.sqlite_database_path

    if sqlite_path.is_absolute():
        return sqlite_path

    return _get_project_root() / sqlite_path


def _get_folder_from_env(name: str, default_value: str) -> Path:
    project_root = _get_project_root()
    folder_value = os.getenv(name, default_value).strip() or default_value
    folder_path = Path(folder_value)

    if not folder_path.is_absolute():
        folder_path = project_root / folder_path

    folder_path.mkdir(parents=True, exist_ok=True)

    return folder_path


def _get_backup_folder() -> Path:
    try:
        backup_folder = get_backup_folder_path()
        backup_folder.mkdir(parents=True, exist_ok=True)

        return backup_folder

    except Exception:
        return _get_folder_from_env("BACKUP_FOLDER", "backups")


def _get_log_folder() -> Path:
    try:
        log_folder = get_log_folder_path()
        log_folder.mkdir(parents=True, exist_ok=True)

        return log_folder

    except Exception:
        return _get_folder_from_env("LOG_FOLDER", "logs")


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


def format_backup_size(size_bytes: int) -> str:
    return _format_backup_size(size_bytes)


def _write_backup_log(message: str) -> None:
    log_folder = _get_log_folder()
    log_file = log_folder / "backup_log.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def _backup_file_patterns_for_current_engine() -> list[str]:
    if _is_sqlite_mode():
        return [
            "*_backup_*.db",
            "*_backup_*.sqlite",
            "*_backup_*.sqlite3",
        ]

    return [
        "*_backup_*.dump",
    ]


def _cleanup_old_backups(backup_folder: Path, keep_days: int) -> int:
    if keep_days <= 0:
        return 0

    cutoff_time = datetime.now() - timedelta(days=keep_days)
    deleted_count = 0

    for pattern in _backup_file_patterns_for_current_engine():
        for backup_file in backup_folder.glob(pattern):
            if not backup_file.is_file():
                continue

            file_modified_time = datetime.fromtimestamp(backup_file.stat().st_mtime)

            if file_modified_time < cutoff_time:
                metadata_file = _metadata_file_for_backup(backup_file)

                backup_file.unlink()
                deleted_count += 1

                if metadata_file.exists():
                    try:
                        metadata_file.unlink()
                    except OSError:
                        pass

    return deleted_count


def _create_backup_file_path(
    *,
    backup_folder: Path,
    database_name: str,
    suffix: str,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_database_name = _safe_filename(database_name)

    return backup_folder / f"{safe_database_name}_backup_{timestamp}{suffix}"


def _metadata_file_for_backup(backup_file: Path) -> Path:
    return backup_file.with_suffix(f"{backup_file.suffix}.meta.json")


def _safe_filename(value: str) -> str:
    cleaned_value = str(value or "").strip()

    safe_chars: list[str] = []

    for char in cleaned_value:
        if char.isalnum() or char in {"_", "-"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")

    result = "".join(safe_chars).strip("_")

    return result or "database"


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


def _run_sqlite_backup(
    *,
    source_database_path: Path,
    output_path: Path,
) -> None:
    if not source_database_path.exists():
        raise BackupServiceError(
            f"SQLite veritabanı dosyası bulunamadı: {source_database_path}"
        )

    if not source_database_path.is_file():
        raise BackupServiceError(
            f"SQLite veritabanı yolu dosya değil: {source_database_path}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_connection: sqlite3.Connection | None = None
    backup_connection: sqlite3.Connection | None = None

    try:
        source_connection = sqlite3.connect(str(source_database_path))
        backup_connection = sqlite3.connect(str(output_path))

        with backup_connection:
            source_connection.backup(backup_connection)

    except sqlite3.Error as exc:
        raise BackupServiceError(f"SQLite yedekleme başarısız oldu: {exc}") from exc

    finally:
        if backup_connection is not None:
            backup_connection.close()

        if source_connection is not None:
            source_connection.close()

    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise BackupServiceError("SQLite yedek dosyası oluşturulamadı veya boş oluştu.")


def _build_backup_mail_subject(*, success: bool) -> str:
    subject_prefix = os.getenv("BACKUP_MAIL_SUBJECT_PREFIX", "FTM").strip() or "FTM"
    engine_label = "SQLite" if _is_sqlite_mode() else "PostgreSQL"

    if success:
        return f"{subject_prefix} - {engine_label} yedekleme başarılı"

    return f"{subject_prefix} - {engine_label} yedekleme başarısız"


def _build_backup_success_mail_body(
    *,
    backup_file: Path,
    backup_size_bytes: int,
    deleted_old_backup_count: int,
    started_at: datetime,
    finished_at: datetime,
    backup_sha256: str,
) -> str:
    if _is_sqlite_mode():
        sqlite_path = _sqlite_database_path()

        return (
            "FTM SQLite yedekleme işlemi başarıyla tamamlandı.\n\n"
            f"Veritabanı dosyası : {sqlite_path}\n"
            f"Yedek dosyası      : {backup_file}\n"
            f"Yedek boyutu       : {_format_backup_size(backup_size_bytes)}\n"
            f"SHA256             : {backup_sha256}\n"
            f"Silinen eski yedek : {deleted_old_backup_count}\n"
            f"Başlangıç zamanı   : {started_at}\n"
            f"Bitiş zamanı       : {finished_at}\n\n"
            "Bu mail FTM yedekleme sistemi tarafından otomatik oluşturulmuştur."
        )

    database_name = os.getenv("DATABASE_NAME", "").strip()
    database_user = os.getenv("DATABASE_USER", "").strip()
    docker_container = os.getenv("BACKUP_DOCKER_CONTAINER", "").strip()

    return (
        "FTM PostgreSQL yedekleme işlemi başarıyla tamamlandı.\n\n"
        f"Veritabanı        : {database_name}\n"
        f"Kullanıcı         : {database_user}\n"
        f"Docker container  : {docker_container}\n"
        f"Yedek dosyası     : {backup_file}\n"
        f"Yedek boyutu      : {_format_backup_size(backup_size_bytes)}\n"
        f"SHA256            : {backup_sha256}\n"
        f"Silinen eski yedek: {deleted_old_backup_count}\n"
        f"Başlangıç zamanı  : {started_at}\n"
        f"Bitiş zamanı      : {finished_at}\n\n"
        "Bu mail FTM yedekleme sistemi tarafından otomatik oluşturulmuştur."
    )


def _get_backup_mail_recipients() -> list[str]:
    app_setting_recipients = get_control_mail_recipients()

    if app_setting_recipients:
        return app_setting_recipients

    return parse_mail_recipients(os.getenv("BACKUP_MAIL_TO", ""))


def _is_backup_mail_enabled() -> bool:
    try:
        app_settings = load_app_settings()

        if not app_settings.control_mail_enabled:
            return False

    except Exception:
        pass

    return _env_bool("BACKUP_MAIL_ENABLED", True)


def _send_backup_success_mail(
    *,
    backup_file: Path,
    backup_size_bytes: int,
    deleted_old_backup_count: int,
    started_at: datetime,
    finished_at: datetime,
    backup_sha256: str,
) -> tuple[bool, str, list[str]]:
    backup_mail_enabled = _is_backup_mail_enabled()
    mail_recipients = _get_backup_mail_recipients()

    if not backup_mail_enabled:
        return False, "Yedekleme bilgi maili pasif.", mail_recipients

    if not mail_recipients:
        return False, "Yedekleme bilgi maili için alıcı tanımlı değil.", mail_recipients

    attach_backup = _env_bool("BACKUP_MAIL_ATTACH_BACKUP", True)
    attachment_path = backup_file if attach_backup else None

    subject = _build_backup_mail_subject(success=True)
    body = _build_backup_success_mail_body(
        backup_file=backup_file,
        backup_size_bytes=backup_size_bytes,
        deleted_old_backup_count=deleted_old_backup_count,
        started_at=started_at,
        finished_at=finished_at,
        backup_sha256=backup_sha256,
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


def calculate_file_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def _is_postgresql_custom_dump(file_path: Path) -> bool:
    try:
        with file_path.open("rb") as file:
            header = file.read(5)

        return header == b"PGDMP"

    except OSError:
        return False


def _is_sqlite_database_file(file_path: Path) -> bool:
    try:
        with file_path.open("rb") as file:
            header = file.read(16)

        return header == b"SQLite format 3\x00"

    except OSError:
        return False


def _write_backup_metadata(
    *,
    backup_file: Path,
    backup_size_bytes: int,
    backup_sha256: str,
    deleted_old_backup_count: int,
    started_at: datetime,
    finished_at: datetime,
    mail_enabled: bool,
    mail_sent: bool,
    mail_message: str,
    mail_recipients: list[str],
) -> Path:
    metadata_file = _metadata_file_for_backup(backup_file)

    if _is_sqlite_mode():
        database_name = _sqlite_database_path().name
        database_user = "local"
        docker_container = ""
        source_database_path = str(_sqlite_database_path())
    else:
        database_name = os.getenv("DATABASE_NAME", "").strip()
        database_user = os.getenv("DATABASE_USER", "").strip()
        docker_container = os.getenv("BACKUP_DOCKER_CONTAINER", "").strip()
        source_database_path = ""

    metadata = {
        "backup_file": str(backup_file),
        "backup_size_bytes": backup_size_bytes,
        "backup_size_text": _format_backup_size(backup_size_bytes),
        "sha256": backup_sha256,
        "database_engine": _database_engine_label(),
        "is_postgresql_custom_dump": _is_postgresql_custom_dump(backup_file),
        "is_sqlite_database_file": _is_sqlite_database_file(backup_file),
        "deleted_old_backup_count": deleted_old_backup_count,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "database_name": database_name,
        "database_user": database_user,
        "docker_container": docker_container,
        "source_database_path": source_database_path,
        "mail_enabled": mail_enabled,
        "mail_sent": mail_sent,
        "mail_message": mail_message,
        "mail_recipients": mail_recipients,
    }

    with metadata_file.open("w", encoding="utf-8") as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")

    return metadata_file


def _read_backup_metadata(metadata_file: Path) -> dict[str, Any]:
    if not metadata_file.exists():
        return {}

    try:
        with metadata_file.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

    except Exception:
        return {}

    return {}


def _create_disabled_backup_result(
    *,
    started_at: datetime,
    message: str,
) -> BackupResult:
    finished_at = datetime.now()

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


def _create_postgresql_database_backup(*, started_at: datetime) -> BackupResult:
    backup_method = os.getenv("BACKUP_METHOD", "docker").strip().lower()

    if backup_method != "docker":
        raise BackupServiceError(f"Desteklenmeyen yedekleme yöntemi: {backup_method}")

    docker_container = _get_env_required("BACKUP_DOCKER_CONTAINER")
    database_name = _get_env_required("DATABASE_NAME")
    database_user = _get_env_required("DATABASE_USER")
    database_password = _get_env_required("DATABASE_PASSWORD")

    backup_folder = _get_backup_folder()
    keep_days = _env_int("BACKUP_KEEP_DAYS", 30)

    backup_file = _create_backup_file_path(
        backup_folder=backup_folder,
        database_name=database_name,
        suffix=".dump",
    )

    try:
        _run_docker_pg_dump(
            docker_container=docker_container,
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
            output_path=backup_file,
        )

    except Exception:
        if backup_file.exists():
            try:
                backup_file.unlink()
            except OSError:
                pass

        raise

    backup_size_bytes = backup_file.stat().st_size
    backup_sha256 = calculate_file_sha256(backup_file)
    deleted_old_backup_count = _cleanup_old_backups(backup_folder, keep_days)

    finished_at = datetime.now()

    message = (
        f"PostgreSQL yedeği başarıyla alındı. "
        f"Dosya: {backup_file} | "
        f"Boyut: {_format_backup_size(backup_size_bytes)} | "
        f"Silinen eski yedek: {deleted_old_backup_count}"
    )

    _write_backup_log(message)

    mail_enabled = _is_backup_mail_enabled()

    mail_sent, mail_message, mail_recipients = _send_backup_success_mail(
        backup_file=backup_file,
        backup_size_bytes=backup_size_bytes,
        deleted_old_backup_count=deleted_old_backup_count,
        started_at=started_at,
        finished_at=finished_at,
        backup_sha256=backup_sha256,
    )

    if mail_sent:
        _write_backup_log(f"Yedekleme bilgi maili gönderildi. Alıcılar: {', '.join(mail_recipients)}")
    else:
        _write_backup_log(mail_message)

    try:
        _write_backup_metadata(
            backup_file=backup_file,
            backup_size_bytes=backup_size_bytes,
            backup_sha256=backup_sha256,
            deleted_old_backup_count=deleted_old_backup_count,
            started_at=started_at,
            finished_at=finished_at,
            mail_enabled=mail_enabled,
            mail_sent=mail_sent,
            mail_message=mail_message,
            mail_recipients=mail_recipients,
        )

    except Exception as exc:
        _write_backup_log(f"Yedek metadata dosyası yazılamadı: {exc}")

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


def _create_sqlite_database_backup(*, started_at: datetime) -> BackupResult:
    sqlite_database_path = _sqlite_database_path()

    backup_folder = _get_backup_folder()
    keep_days = _env_int("BACKUP_KEEP_DAYS", 30)

    backup_file = _create_backup_file_path(
        backup_folder=backup_folder,
        database_name=sqlite_database_path.stem or "ftm_local",
        suffix=".db",
    )

    try:
        _run_sqlite_backup(
            source_database_path=sqlite_database_path,
            output_path=backup_file,
        )

    except Exception:
        if backup_file.exists():
            try:
                backup_file.unlink()
            except OSError:
                pass

        raise

    backup_size_bytes = backup_file.stat().st_size
    backup_sha256 = calculate_file_sha256(backup_file)
    deleted_old_backup_count = _cleanup_old_backups(backup_folder, keep_days)

    finished_at = datetime.now()

    message = (
        f"SQLite yedeği başarıyla alındı. "
        f"Kaynak: {sqlite_database_path} | "
        f"Dosya: {backup_file} | "
        f"Boyut: {_format_backup_size(backup_size_bytes)} | "
        f"Silinen eski yedek: {deleted_old_backup_count}"
    )

    _write_backup_log(message)

    mail_enabled = _is_backup_mail_enabled()

    mail_sent, mail_message, mail_recipients = _send_backup_success_mail(
        backup_file=backup_file,
        backup_size_bytes=backup_size_bytes,
        deleted_old_backup_count=deleted_old_backup_count,
        started_at=started_at,
        finished_at=finished_at,
        backup_sha256=backup_sha256,
    )

    if mail_sent:
        _write_backup_log(f"Yedekleme bilgi maili gönderildi. Alıcılar: {', '.join(mail_recipients)}")
    else:
        _write_backup_log(mail_message)

    try:
        _write_backup_metadata(
            backup_file=backup_file,
            backup_size_bytes=backup_size_bytes,
            backup_sha256=backup_sha256,
            deleted_old_backup_count=deleted_old_backup_count,
            started_at=started_at,
            finished_at=finished_at,
            mail_enabled=mail_enabled,
            mail_sent=mail_sent,
            mail_message=mail_message,
            mail_recipients=mail_recipients,
        )

    except Exception as exc:
        _write_backup_log(f"Yedek metadata dosyası yazılamadı: {exc}")

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


def create_database_backup() -> BackupResult:
    _load_environment()

    started_at = datetime.now()

    backup_enabled = _env_bool("BACKUP_ENABLED", True)

    if not backup_enabled:
        return _create_disabled_backup_result(
            started_at=started_at,
            message="Yedekleme pasif. BACKUP_ENABLED=false",
        )

    if _is_sqlite_mode():
        return _create_sqlite_database_backup(started_at=started_at)

    return _create_postgresql_database_backup(started_at=started_at)


def list_database_backups() -> list[BackupFileInfo]:
    _load_environment()

    backup_folder = _get_backup_folder()

    if not backup_folder.exists():
        return []

    backup_files: list[Path] = []

    for pattern in _backup_file_patterns_for_current_engine():
        backup_files.extend(
            [
                backup_file
                for backup_file in backup_folder.glob(pattern)
                if backup_file.is_file()
            ]
        )

    backup_files = sorted(
        backup_files,
        key=lambda backup_file: backup_file.stat().st_mtime,
        reverse=True,
    )

    results: list[BackupFileInfo] = []

    for backup_file in backup_files:
        metadata_file = _metadata_file_for_backup(backup_file)
        metadata = _read_backup_metadata(metadata_file)

        backup_size_bytes = backup_file.stat().st_size
        created_at = datetime.fromtimestamp(backup_file.stat().st_mtime)

        sha256_value = str(metadata.get("sha256") or "")

        status = "OK"
        status_message = "Yedek dosyası mevcut."

        if backup_size_bytes <= 0:
            status = "WARN"
            status_message = "Yedek dosyası boş görünüyor."
        elif _is_sqlite_mode():
            if not _is_sqlite_database_file(backup_file):
                status = "WARN"
                status_message = "Dosya var ancak SQLite veritabanı başlığı doğrulanamadı."
            else:
                status_message = "SQLite yedek dosyası doğrulanabilir görünüyor."
        elif not _is_postgresql_custom_dump(backup_file):
            status = "WARN"
            status_message = "Dosya var ancak PostgreSQL custom dump başlığı doğrulanamadı."

        if _is_sqlite_mode():
            database_name = str(metadata.get("database_name") or _sqlite_database_path().name)
            database_user = str(metadata.get("database_user") or "local")
            docker_container = str(metadata.get("docker_container") or "SQLite Local")
        else:
            database_name = str(metadata.get("database_name") or os.getenv("DATABASE_NAME", ""))
            database_user = str(metadata.get("database_user") or os.getenv("DATABASE_USER", ""))
            docker_container = str(metadata.get("docker_container") or os.getenv("BACKUP_DOCKER_CONTAINER", ""))

        results.append(
            BackupFileInfo(
                file_name=backup_file.name,
                file_path=backup_file,
                backup_size_bytes=backup_size_bytes,
                created_at=created_at,
                sha256=sha256_value,
                metadata_file=metadata_file if metadata_file.exists() else None,
                database_name=database_name,
                database_user=database_user,
                docker_container=docker_container,
                status=status,
                status_message=status_message,
            )
        )

    return results


def validate_backup_file(backup_file: str | Path) -> BackupValidationResult:
    backup_path = Path(backup_file)

    if not backup_path.exists():
        raise BackupServiceError(f"Yedek dosyası bulunamadı: {backup_path}")

    if not backup_path.is_file():
        raise BackupServiceError(f"Yedek yolu dosya değil: {backup_path}")

    backup_size_bytes = backup_path.stat().st_size

    if backup_size_bytes <= 0:
        raise BackupServiceError(f"Yedek dosyası boş görünüyor: {backup_path}")

    backup_sha256 = calculate_file_sha256(backup_path)
    is_custom_dump = _is_postgresql_custom_dump(backup_path)
    is_sqlite_file = _is_sqlite_database_file(backup_path)

    if is_custom_dump:
        return BackupValidationResult(
            success=True,
            backup_file=backup_path,
            backup_size_bytes=backup_size_bytes,
            sha256=backup_sha256,
            is_postgresql_custom_dump=True,
            message="Yedek dosyası mevcut, boş değil ve PostgreSQL custom dump başlığı doğrulandı.",
        )

    if is_sqlite_file:
        return BackupValidationResult(
            success=True,
            backup_file=backup_path,
            backup_size_bytes=backup_size_bytes,
            sha256=backup_sha256,
            is_postgresql_custom_dump=False,
            message="Yedek dosyası mevcut, boş değil ve SQLite veritabanı başlığı doğrulandı.",
        )

    return BackupValidationResult(
        success=False,
        backup_file=backup_path,
        backup_size_bytes=backup_size_bytes,
        sha256=backup_sha256,
        is_postgresql_custom_dump=False,
        message="Yedek dosyası mevcut ancak PostgreSQL custom dump veya SQLite veritabanı başlığı doğrulanamadı.",
    )


def backup_result_to_dict(result: BackupResult) -> dict[str, Any]:
    payload = asdict(result)

    payload["backup_file"] = str(result.backup_file) if result.backup_file else None
    payload["started_at"] = result.started_at.isoformat(timespec="seconds")
    payload["finished_at"] = result.finished_at.isoformat(timespec="seconds")

    return payload


def backup_file_info_to_dict(info: BackupFileInfo) -> dict[str, Any]:
    payload = asdict(info)

    payload["file_path"] = str(info.file_path)
    payload["created_at"] = info.created_at.isoformat(timespec="seconds")
    payload["metadata_file"] = str(info.metadata_file) if info.metadata_file else None

    return payload


__all__ = [
    "BackupResult",
    "BackupFileInfo",
    "BackupValidationResult",
    "BackupServiceError",
    "create_database_backup",
    "list_database_backups",
    "validate_backup_file",
    "calculate_file_sha256",
    "format_backup_size",
    "backup_result_to_dict",
    "backup_file_info_to_dict",
]
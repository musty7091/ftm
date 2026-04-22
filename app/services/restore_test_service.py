import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class RestoreTestResult:
    success: bool
    backup_file: Path
    restore_database_name: str
    table_count: int
    key_table_counts: dict[str, int]
    started_at: datetime
    finished_at: datetime
    message: str


class RestoreTestServiceError(RuntimeError):
    pass


def _get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_environment() -> None:
    project_root = _get_project_root()
    env_path = project_root / ".env"
    load_dotenv(env_path)


def _get_env_required(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RestoreTestServiceError(f"{name} .env içinde tanımlı olmalıdır.")

    return value.strip()


def _get_folder_from_env(name: str, default_value: str) -> Path:
    project_root = _get_project_root()
    folder_value = os.getenv(name, default_value).strip() or default_value
    folder_path = Path(folder_value)

    if not folder_path.is_absolute():
        folder_path = project_root / folder_path

    folder_path.mkdir(parents=True, exist_ok=True)

    return folder_path


def _write_restore_test_log(message: str) -> None:
    log_folder = _get_folder_from_env("LOG_FOLDER", "logs")
    log_file = log_folder / "restore_test_log.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def _find_latest_backup_file(backup_folder: Path) -> Path:
    backup_files = sorted(
        backup_folder.glob("*_backup_*.dump"),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )

    if not backup_files:
        raise RestoreTestServiceError(f"Yedek dosyası bulunamadı. Klasör: {backup_folder}")

    return backup_files[0]


def _run_docker_command(
    command: list[str],
    *,
    input_bytes: Optional[bytes] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _run_psql_command(
    *,
    docker_container: str,
    database_user: str,
    database_password: str,
    database_name: str,
    sql: str,
) -> str:
    command = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={database_password}",
        docker_container,
        "psql",
        "-U",
        database_user,
        "-d",
        database_name,
        "-t",
        "-A",
        "-c",
        sql,
    ]

    result = _run_docker_command(command)

    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        raise RestoreTestServiceError(f"psql komutu başarısız oldu. Hata: {stderr_text}")

    return result.stdout.decode("utf-8", errors="replace").strip()


def _drop_and_create_restore_database(
    *,
    docker_container: str,
    database_user: str,
    database_password: str,
    restore_database_name: str,
) -> None:
    drop_sql = f'DROP DATABASE IF EXISTS "{restore_database_name}";'
    create_sql = f'CREATE DATABASE "{restore_database_name}";'

    _run_psql_command(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name="postgres",
        sql=drop_sql,
    )

    _run_psql_command(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name="postgres",
        sql=create_sql,
    )


def _restore_backup_file(
    *,
    docker_container: str,
    database_user: str,
    database_password: str,
    restore_database_name: str,
    backup_file: Path,
) -> None:
    command = [
        "docker",
        "exec",
        "-i",
        "-e",
        f"PGPASSWORD={database_password}",
        docker_container,
        "pg_restore",
        "-U",
        database_user,
        "-d",
        restore_database_name,
        "--no-owner",
        "--no-acl",
    ]

    backup_bytes = backup_file.read_bytes()

    result = _run_docker_command(
        command,
        input_bytes=backup_bytes,
    )

    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        raise RestoreTestServiceError(f"pg_restore başarısız oldu. Hata: {stderr_text}")


def _get_public_table_count(
    *,
    docker_container: str,
    database_user: str,
    database_password: str,
    database_name: str,
) -> int:
    sql = """
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';
    """

    result = _run_psql_command(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name=database_name,
        sql=sql,
    )

    return int(result)


def _table_exists(
    *,
    docker_container: str,
    database_user: str,
    database_password: str,
    database_name: str,
    table_name: str,
) -> bool:
    sql = f"""
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = '{table_name}';
    """

    result = _run_psql_command(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name=database_name,
        sql=sql,
    )

    return int(result) > 0


def _get_table_row_count(
    *,
    docker_container: str,
    database_user: str,
    database_password: str,
    database_name: str,
    table_name: str,
) -> int:
    if not _table_exists(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name=database_name,
        table_name=table_name,
    ):
        return -1

    sql = f'SELECT COUNT(*) FROM "{table_name}";'

    result = _run_psql_command(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name=database_name,
        sql=sql,
    )

    return int(result)


def test_latest_backup_restore() -> RestoreTestResult:
    _load_environment()

    started_at = datetime.now()

    docker_container = _get_env_required("BACKUP_DOCKER_CONTAINER")
    database_user = _get_env_required("DATABASE_USER")
    database_password = _get_env_required("DATABASE_PASSWORD")

    restore_database_name = os.getenv("RESTORE_TEST_DATABASE_NAME", "ftm_restore_test").strip() or "ftm_restore_test"

    backup_folder = _get_folder_from_env("BACKUP_FOLDER", "backups")
    latest_backup_file = _find_latest_backup_file(backup_folder)

    _drop_and_create_restore_database(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        restore_database_name=restore_database_name,
    )

    _restore_backup_file(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        restore_database_name=restore_database_name,
        backup_file=latest_backup_file,
    )

    table_count = _get_public_table_count(
        docker_container=docker_container,
        database_user=database_user,
        database_password=database_password,
        database_name=restore_database_name,
    )

    key_tables = [
        "users",
        "banks",
        "bank_accounts",
        "bank_transactions",
        "bank_transfers",
        "business_partners",
        "issued_checks",
        "received_checks",
        "pos_devices",
        "pos_settlements",
        "audit_logs",
    ]

    key_table_counts: dict[str, int] = {}

    for table_name in key_tables:
        key_table_counts[table_name] = _get_table_row_count(
            docker_container=docker_container,
            database_user=database_user,
            database_password=database_password,
            database_name=restore_database_name,
            table_name=table_name,
        )

    finished_at = datetime.now()

    if table_count <= 0:
        raise RestoreTestServiceError("Restore test veritabanında tablo bulunamadı.")

    message = (
        f"Yedekten geri dönüş testi başarılı. "
        f"Yedek dosyası: {latest_backup_file} | "
        f"Test veritabanı: {restore_database_name} | "
        f"Tablo sayısı: {table_count}"
    )

    _write_restore_test_log(message)

    return RestoreTestResult(
        success=True,
        backup_file=latest_backup_file,
        restore_database_name=restore_database_name,
        table_count=table_count,
        key_table_counts=key_table_counts,
        started_at=started_at,
        finished_at=finished_at,
        message=message,
    )
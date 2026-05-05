from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.runtime_paths import ensure_runtime_folders


SQLITE_BACKUP_PATTERNS = [
    "*_backup_*.db",
    "*_backup_*.sqlite",
    "*_backup_*.sqlite3",
]

KEY_TABLE_NAMES = [
    "users",
    "role_permissions",
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


@dataclass(frozen=True)
class SqliteRestoreTestResult:
    success: bool
    backup_file: Path
    test_database_file: Path
    backup_size_bytes: int
    backup_size_text: str
    table_count: int
    user_version: int
    quick_check_result: str
    key_table_counts: dict[str, int]
    started_at: datetime
    finished_at: datetime
    message: str


class SqliteRestoreTestError(RuntimeError):
    pass


def main() -> None:
    args = _parse_args()

    try:
        result = test_latest_sqlite_backup_restore(
            backup_file=Path(args.backup_file).expanduser() if args.backup_file else None,
            keep_test_database=bool(args.keep_test_database),
            quiet=bool(args.quiet),
        )

        if args.json:
            print(
                json.dumps(
                    sqlite_restore_test_result_to_dict(result),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        print("")
        print("FTM SQLITE RESTORE TEST RAPORU")
        print("-" * 72)
        print(f"Durum              : {'BAŞARILI' if result.success else 'BAŞARISIZ'}")
        print(f"Yedek dosyası      : {result.backup_file}")
        print(f"Test veritabanı    : {result.test_database_file}")
        print(f"Yedek boyutu       : {result.backup_size_text}")
        print(f"Tablo sayısı       : {result.table_count}")
        print(f"user_version       : {result.user_version}")
        print(f"quick_check        : {result.quick_check_result}")
        print(f"Başlangıç          : {result.started_at}")
        print(f"Bitiş              : {result.finished_at}")
        print("")
        print("Önemli tablo kayıt sayıları")
        print("-" * 72)

        for table_name, row_count in result.key_table_counts.items():
            if row_count < 0:
                print(f"{table_name:<28}: tablo yok")
            else:
                print(f"{table_name:<28}: {row_count}")

        print("")
        print(result.message)
        print("")

    except Exception as exc:
        error_message = f"SQLite restore test başarısız: {exc}"

        try:
            _write_restore_test_log(error_message)
        except Exception:
            pass

        print("")
        print("FTM SQLITE RESTORE TEST BAŞARISIZ")
        print("-" * 72)
        print(type(exc).__name__)
        print(exc)
        print("")

        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "FTM SQLite yedek dosyasını canlı veritabanına dokunmadan ayrı bir "
            "restore_tests klasöründe açar ve doğrular."
        )
    )

    parser.add_argument(
        "--backup-file",
        default="",
        help=(
            "Test edilecek belirli yedek dosyası. Boş bırakılırsa en son SQLite "
            "yedek dosyası otomatik seçilir."
        ),
    )

    parser.add_argument(
        "--keep-test-database",
        action="store_true",
        help=(
            "Test veritabanını işlem sonunda saklar. Varsayılan davranış zaten "
            "saklamaktır; bu parametre okunabilirlik için korunur."
        ),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Sonucu JSON formatında yazdırır.",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Ara bilgi çıktılarını azaltır.",
    )

    return parser.parse_args()


def test_latest_sqlite_backup_restore(
    *,
    backup_file: Path | None = None,
    keep_test_database: bool = True,
    quiet: bool = False,
) -> SqliteRestoreTestResult:
    if not settings.is_sqlite:
        raise SqliteRestoreTestError(
            "Bu komut yalnızca SQLite modunda çalışır. "
            f"Mevcut veritabanı modu: {settings.database_engine}"
        )

    started_at = datetime.now()
    runtime_paths = ensure_runtime_folders()

    selected_backup_file = backup_file or _find_latest_sqlite_backup_file(
        runtime_paths.backups_folder
    )

    selected_backup_file = selected_backup_file.expanduser().resolve()

    _validate_sqlite_backup_file(selected_backup_file)

    restore_tests_folder = runtime_paths.backups_folder / "restore_tests"
    restore_tests_folder.mkdir(parents=True, exist_ok=True)

    test_database_file = _build_restore_test_database_path(
        restore_tests_folder=restore_tests_folder,
        backup_file=selected_backup_file,
    )

    if not quiet:
        print(f"Yedek dosyası seçildi : {selected_backup_file}")
        print(f"Test DB oluşturuluyor : {test_database_file}")

    shutil.copy2(selected_backup_file, test_database_file)

    backup_size_bytes = selected_backup_file.stat().st_size
    backup_size_text = _format_file_size(backup_size_bytes)

    validation_data = _validate_restored_sqlite_database(test_database_file)

    finished_at = datetime.now()

    message = (
        f"SQLite restore test başarılı | "
        f"Yedek: {selected_backup_file} | "
        f"Test DB: {test_database_file} | "
        f"Boyut: {backup_size_text} | "
        f"Tablo: {validation_data['table_count']} | "
        f"user_version: {validation_data['user_version']} | "
        f"quick_check: {validation_data['quick_check_result']}"
    )

    _write_restore_test_log(message)

    return SqliteRestoreTestResult(
        success=True,
        backup_file=selected_backup_file,
        test_database_file=test_database_file,
        backup_size_bytes=backup_size_bytes,
        backup_size_text=backup_size_text,
        table_count=int(validation_data["table_count"]),
        user_version=int(validation_data["user_version"]),
        quick_check_result=str(validation_data["quick_check_result"]),
        key_table_counts=dict(validation_data["key_table_counts"]),
        started_at=started_at,
        finished_at=finished_at,
        message=message,
    )


def _find_latest_sqlite_backup_file(backup_folder: Path) -> Path:
    if not backup_folder.exists():
        raise SqliteRestoreTestError(
            f"Yedek klasörü bulunamadı: {backup_folder}"
        )

    if not backup_folder.is_dir():
        raise SqliteRestoreTestError(
            f"Yedek yolu klasör değil: {backup_folder}"
        )

    backup_files: list[Path] = []

    for pattern in SQLITE_BACKUP_PATTERNS:
        backup_files.extend(
            [
                file_path
                for file_path in backup_folder.glob(pattern)
                if file_path.is_file()
            ]
        )

    backup_files = sorted(
        backup_files,
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )

    if not backup_files:
        raise SqliteRestoreTestError(
            f"SQLite yedek dosyası bulunamadı. Klasör: {backup_folder}"
        )

    return backup_files[0]


def _validate_sqlite_backup_file(backup_file: Path) -> None:
    if not backup_file.exists():
        raise SqliteRestoreTestError(
            f"Yedek dosyası bulunamadı: {backup_file}"
        )

    if not backup_file.is_file():
        raise SqliteRestoreTestError(
            f"Yedek yolu dosya değil: {backup_file}"
        )

    if backup_file.stat().st_size <= 0:
        raise SqliteRestoreTestError(
            f"Yedek dosyası boş görünüyor: {backup_file}"
        )

    try:
        with backup_file.open("rb") as file:
            header = file.read(16)

    except OSError as exc:
        raise SqliteRestoreTestError(
            f"Yedek dosyası okunamadı: {backup_file} | Hata: {exc}"
        ) from exc

    if header != b"SQLite format 3\x00":
        raise SqliteRestoreTestError(
            "Yedek dosyası SQLite veritabanı başlığı taşımıyor. "
            f"Dosya: {backup_file}"
        )


def _build_restore_test_database_path(
    *,
    restore_tests_folder: Path,
    backup_file: Path,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_stem = _safe_file_stem(backup_file.stem)
    suffix = backup_file.suffix or ".db"

    return restore_tests_folder / f"{backup_stem}_restore_test_{timestamp}{suffix}"


def _validate_restored_sqlite_database(test_database_file: Path) -> dict[str, Any]:
    if not test_database_file.exists():
        raise SqliteRestoreTestError(
            f"Test veritabanı oluşturulamadı: {test_database_file}"
        )

    if test_database_file.stat().st_size <= 0:
        raise SqliteRestoreTestError(
            f"Test veritabanı boş görünüyor: {test_database_file}"
        )

    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(str(test_database_file))
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")

        quick_check_rows = [
            str(row[0])
            for row in connection.execute("PRAGMA quick_check").fetchall()
        ]

        if not quick_check_rows:
            raise SqliteRestoreTestError(
                "SQLite quick_check sonuç üretmedi."
            )

        quick_check_result = "; ".join(quick_check_rows)

        if any(row.strip().lower() != "ok" for row in quick_check_rows):
            raise SqliteRestoreTestError(
                f"SQLite quick_check başarısız: {quick_check_result}"
            )

        user_version = int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        )

        table_names = [
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        ]

        table_count = len(table_names)

        if table_count <= 0:
            raise SqliteRestoreTestError(
                "Restore test veritabanında uygulama tablosu bulunamadı."
            )

        key_table_counts: dict[str, int] = {}

        for table_name in KEY_TABLE_NAMES:
            if table_name not in table_names:
                key_table_counts[table_name] = -1
                continue

            key_table_counts[table_name] = _count_table_rows(
                connection=connection,
                table_name=table_name,
            )

        return {
            "quick_check_result": quick_check_result,
            "user_version": user_version,
            "table_count": table_count,
            "key_table_counts": key_table_counts,
        }

    except sqlite3.Error as exc:
        raise SqliteRestoreTestError(
            f"SQLite restore test veritabanı doğrulanamadı: {exc}"
        ) from exc

    finally:
        if connection is not None:
            connection.close()


def _count_table_rows(
    *,
    connection: sqlite3.Connection,
    table_name: str,
) -> int:
    safe_table_name = _quote_sqlite_identifier(table_name)

    result = connection.execute(
        f"SELECT COUNT(*) FROM {safe_table_name}"
    ).fetchone()

    return int(result[0] or 0)


def _quote_sqlite_identifier(value: str) -> str:
    cleaned_value = str(value or "").strip()

    if not cleaned_value:
        raise SqliteRestoreTestError("SQLite tablo adı boş olamaz.")

    return '"' + cleaned_value.replace('"', '""') + '"'


def _write_restore_test_log(message: str) -> None:
    runtime_paths = ensure_runtime_folders()
    log_file = runtime_paths.logs_folder / "restore_test_log.txt"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"{timestamp} | {message}\n")


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


def _safe_file_stem(value: str) -> str:
    cleaned_value = str(value or "").strip()

    safe_chars: list[str] = []

    for char in cleaned_value:
        if char.isalnum() or char in {"_", "-"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")

    result = "".join(safe_chars).strip("_")

    return result or "sqlite_backup"


def sqlite_restore_test_result_to_dict(
    result: SqliteRestoreTestResult,
) -> dict[str, Any]:
    payload = asdict(result)

    payload["backup_file"] = str(result.backup_file)
    payload["test_database_file"] = str(result.test_database_file)
    payload["started_at"] = result.started_at.isoformat(timespec="seconds")
    payload["finished_at"] = result.finished_at.isoformat(timespec="seconds")

    return payload


if __name__ == "__main__":
    main()
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.backup_service import (
    BackupServiceError,
    calculate_file_sha256,
    format_backup_size,
    validate_backup_file,
)


def test_format_backup_size_for_bytes() -> None:
    assert format_backup_size(512) == "512 byte"


def test_format_backup_size_for_kilobytes() -> None:
    assert format_backup_size(1024) == "1.00 KB"


def test_format_backup_size_for_megabytes() -> None:
    assert format_backup_size(1024 * 1024) == "1.00 MB"


def test_calculate_file_sha256_returns_expected_hash(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.txt"
    test_content = b"FTM backup test content"

    test_file.write_bytes(test_content)

    expected_hash = hashlib.sha256(test_content).hexdigest()

    assert calculate_file_sha256(test_file) == expected_hash


def test_validate_backup_file_raises_for_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.dump"

    with pytest.raises(BackupServiceError):
        validate_backup_file(missing_file)


def test_validate_backup_file_raises_for_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.dump"
    empty_file.write_bytes(b"")

    with pytest.raises(BackupServiceError):
        validate_backup_file(empty_file)


def test_validate_backup_file_returns_warning_for_non_postgresql_dump(
    tmp_path: Path,
) -> None:
    fake_file = tmp_path / "not_postgresql.dump"
    fake_file.write_bytes(b"this is not a postgresql custom dump")

    result = validate_backup_file(fake_file)

    assert result.success is False
    assert result.backup_file == fake_file
    assert result.backup_size_bytes > 0
    assert result.is_postgresql_custom_dump is False
    assert "PostgreSQL custom dump" in result.message


def test_validate_backup_file_accepts_postgresql_custom_dump_header(
    tmp_path: Path,
) -> None:
    fake_dump_file = tmp_path / "postgresql_custom.dump"
    fake_dump_file.write_bytes(b"PGDMP fake dump content for test")

    result = validate_backup_file(fake_dump_file)

    assert result.success is True
    assert result.backup_file == fake_dump_file
    assert result.backup_size_bytes > 0
    assert result.is_postgresql_custom_dump is True
    assert result.sha256 == calculate_file_sha256(fake_dump_file)
from __future__ import annotations

from pathlib import Path

import pytest

import app.services.setup_service as setup_service


def _configure_setup_service_for_temp_folder(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    config_folder = tmp_path / "config"
    config_file = config_folder / "app_setup.json"

    monkeypatch.setattr(setup_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(setup_service, "SETUP_CONFIG_FOLDER", config_folder)
    monkeypatch.setattr(setup_service, "SETUP_CONFIG_FILE", config_file)

    return config_file


def test_load_setup_config_returns_default_when_file_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = _configure_setup_service_for_temp_folder(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    loaded_config = setup_service.load_setup_config()

    assert config_file.exists() is False
    assert loaded_config.setup_completed is False
    assert loaded_config.database_engine == "sqlite"
    assert loaded_config.sqlite_database_path == "data/ftm_local.db"


def test_save_sqlite_setup_config_writes_file_and_builds_sqlite_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = _configure_setup_service_for_temp_folder(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    saved_config = setup_service.save_sqlite_setup_config(
        sqlite_database_path="data/demo_ftm.db",
        setup_completed=True,
    )

    expected_sqlite_path = tmp_path / "data" / "demo_ftm.db"
    database_url = setup_service.build_database_url_from_setup_config(saved_config)

    assert config_file.exists() is True
    assert saved_config.setup_completed is True
    assert saved_config.database_engine == "sqlite"
    assert saved_config.sqlite_database_path == "data/demo_ftm.db"
    assert saved_config.created_at
    assert saved_config.updated_at
    assert database_url == f"sqlite:///{expected_sqlite_path.as_posix()}"


def test_save_postgresql_setup_config_writes_file_and_builds_postgresql_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = _configure_setup_service_for_temp_folder(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    saved_config = setup_service.save_postgresql_setup_config(
        database_host="192.168.1.100",
        database_port=5432,
        database_name="ftm_db",
        database_user="ftm_user",
        database_password="p@ ss",
        setup_completed=True,
    )

    database_url = setup_service.build_database_url_from_setup_config(saved_config)

    assert config_file.exists() is True
    assert saved_config.setup_completed is True
    assert saved_config.database_engine == "postgresql"
    assert saved_config.database_host == "192.168.1.100"
    assert saved_config.database_port == 5432
    assert saved_config.database_name == "ftm_db"
    assert saved_config.database_user == "ftm_user"
    assert saved_config.database_password == "p@ ss"
    assert database_url == "postgresql+psycopg://ftm_user:p%40+ss@192.168.1.100:5432/ftm_db"


def test_normalize_setup_config_blocks_parent_directory_sqlite_path() -> None:
    payload = setup_service.default_setup_config_dict()
    payload["sqlite_database_path"] = "../danger.db"

    normalized_payload = setup_service.normalize_setup_config_payload(payload)

    assert normalized_payload["sqlite_database_path"] == "data/ftm_local.db"


def test_normalize_setup_config_rejects_invalid_database_engine() -> None:
    payload = setup_service.default_setup_config_dict()
    payload["database_engine"] = "oracle"

    with pytest.raises(setup_service.SetupServiceError):
        setup_service.normalize_setup_config_payload(payload)


def test_validate_sqlite_setup_config_requires_existing_parent_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_setup_service_for_temp_folder(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    payload = setup_service.default_setup_config_dict()
    payload["setup_completed"] = True
    payload["database_engine"] = "sqlite"
    payload["sqlite_database_path"] = "data/ftm_local.db"

    with pytest.raises(setup_service.SetupServiceError):
        setup_service.validate_setup_config_for_completion(payload)

    data_folder = tmp_path / "data"
    data_folder.mkdir(parents=True, exist_ok=True)

    setup_service.validate_setup_config_for_completion(payload)


def test_validate_postgresql_setup_config_requires_password() -> None:
    payload = setup_service.default_setup_config_dict()
    payload["setup_completed"] = True
    payload["database_engine"] = "postgresql"
    payload["database_host"] = "localhost"
    payload["database_port"] = 5432
    payload["database_name"] = "ftm_db"
    payload["database_user"] = "ftm_user"
    payload["database_password"] = ""

    with pytest.raises(setup_service.SetupServiceError):
        setup_service.validate_setup_config_for_completion(payload)


def test_reset_setup_config_writes_default_not_completed_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = _configure_setup_service_for_temp_folder(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    setup_service.save_sqlite_setup_config(
        sqlite_database_path="data/demo_ftm.db",
        setup_completed=True,
    )

    reset_config = setup_service.reset_setup_config()

    assert config_file.exists() is True
    assert reset_config.setup_completed is False
    assert reset_config.database_engine == "sqlite"
    assert reset_config.sqlite_database_path == "data/ftm_local.db"
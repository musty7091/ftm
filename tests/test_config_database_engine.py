from __future__ import annotations

from pathlib import Path

import pytest

import app.core.config as config


DATABASE_ENV_KEYS = [
    "DATABASE_ENGINE",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "SQLITE_DATABASE_PATH",
]


def _clear_database_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in DATABASE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_database_engine_prefers_explicit_postgresql_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)

    monkeypatch.setenv("DATABASE_ENGINE", "postgresql")

    assert config._get_database_engine() == "postgresql"


def test_database_engine_prefers_explicit_sqlite_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)

    monkeypatch.setenv("DATABASE_ENGINE", "sqlite")

    assert config._get_database_engine() == "sqlite"


def test_database_engine_uses_postgresql_when_required_env_values_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)
    monkeypatch.setattr(config, "SETUP_CONFIG_DATA", {})

    monkeypatch.setenv("DATABASE_HOST", "localhost")
    monkeypatch.setenv("DATABASE_NAME", "ftm_db")
    monkeypatch.setenv("DATABASE_USER", "ftm_user")
    monkeypatch.setenv("DATABASE_PASSWORD", "ftm_password")

    assert config._get_database_engine() == "postgresql"


def test_database_engine_uses_completed_sqlite_setup_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)

    monkeypatch.setattr(
        config,
        "SETUP_CONFIG_DATA",
        {
            "setup_completed": True,
            "database_engine": "sqlite",
            "sqlite_database_path": "data/demo_ftm.db",
        },
    )

    assert config._get_database_engine() == "sqlite"


def test_database_engine_defaults_to_sqlite_when_no_env_and_no_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)
    monkeypatch.setattr(config, "SETUP_CONFIG_DATA", {})

    assert config._get_database_engine() == "sqlite"


def test_invalid_database_engine_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)

    monkeypatch.setenv("DATABASE_ENGINE", "oracle")

    with pytest.raises(RuntimeError):
        config._get_database_engine()


def test_sqlite_database_path_uses_setup_config_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_env(monkeypatch)

    monkeypatch.setattr(
        config,
        "SETUP_CONFIG_DATA",
        {
            "setup_completed": True,
            "database_engine": "sqlite",
            "sqlite_database_path": "data/demo_ftm.db",
        },
    )

    sqlite_path = config._get_sqlite_database_path()

    assert sqlite_path == config.BASE_DIR / "data" / "demo_ftm.db"


def test_sqlite_database_path_prefers_env_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_database_env(monkeypatch)

    sqlite_file = tmp_path / "custom_ftm.db"

    monkeypatch.setattr(
        config,
        "SETUP_CONFIG_DATA",
        {
            "setup_completed": True,
            "database_engine": "sqlite",
            "sqlite_database_path": "data/demo_ftm.db",
        },
    )
    monkeypatch.setenv("SQLITE_DATABASE_PATH", str(sqlite_file))

    sqlite_path = config._get_sqlite_database_path()

    assert sqlite_path == sqlite_file


def test_settings_builds_sqlite_database_url(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "ftm_local.db"

    settings = config.Settings(
        app_name="FTM",
        app_env="test",
        app_debug=True,
        database_engine="sqlite",
        database_host="",
        database_port=0,
        database_name="ftm_local",
        database_user="",
        database_password="",
        database_echo=False,
        sqlite_database_path=sqlite_file,
        backup_folder=tmp_path / "backups",
        export_folder=tmp_path / "exports",
        log_folder=tmp_path / "logs",
        mail_enabled=False,
        mail_server="smtp.gmail.com",
        mail_port=587,
        mail_use_tls=True,
        mail_username="",
        mail_password="",
        mail_from="",
        mail_to="",
    )

    assert settings.is_sqlite is True
    assert settings.is_postgresql is False
    assert settings.database_url == f"sqlite:///{sqlite_file.as_posix()}"


def test_settings_builds_postgresql_database_url(tmp_path: Path) -> None:
    settings = config.Settings(
        app_name="FTM",
        app_env="test",
        app_debug=True,
        database_engine="postgresql",
        database_host="localhost",
        database_port=5433,
        database_name="ftm_db",
        database_user="ftm user",
        database_password="p@ ss",
        database_echo=False,
        sqlite_database_path=tmp_path / "ftm_local.db",
        backup_folder=tmp_path / "backups",
        export_folder=tmp_path / "exports",
        log_folder=tmp_path / "logs",
        mail_enabled=False,
        mail_server="smtp.gmail.com",
        mail_port=587,
        mail_use_tls=True,
        mail_username="",
        mail_password="",
        mail_from="",
        mail_to="",
    )

    assert settings.is_sqlite is False
    assert settings.is_postgresql is True
    assert settings.database_url == "postgresql+psycopg://ftm+user:p%40+ss@localhost:5433/ftm_db"
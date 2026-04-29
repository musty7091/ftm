from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.services.app_settings_service as app_settings_service
import app.services.setup_service as setup_service
import app.ui.setup_wizard_preview as setup_wizard_preview
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.models.user import User
from app.services.auth_service import verify_password
from app.services.permission_service import Permission
from app.ui.setup_wizard_dialog import SetupWizardPayload


def _configure_temp_setup_paths(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, Path]:
    config_folder = tmp_path / "config"
    setup_config_file = config_folder / "app_setup.json"
    app_settings_file = config_folder / "app_settings.json"

    monkeypatch.setattr(setup_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(setup_service, "SETUP_CONFIG_FOLDER", config_folder)
    monkeypatch.setattr(setup_service, "SETUP_CONFIG_FILE", setup_config_file)

    monkeypatch.setattr(app_settings_service, "CONFIG_FOLDER", config_folder)
    monkeypatch.setattr(app_settings_service, "APP_SETTINGS_FILE", app_settings_file)

    return {
        "config_folder": config_folder,
        "setup_config_file": setup_config_file,
        "app_settings_file": app_settings_file,
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assert isinstance(data, dict)

    return data


def _build_valid_sqlite_payload() -> SetupWizardPayload:
    return SetupWizardPayload(
        database_engine="sqlite",
        sqlite_database_path="data/preview_test_ftm.db",
        database_host="localhost",
        database_port=0,
        database_name="ftm_db",
        database_user="ftm_user",
        database_password="",
        company_name="Preview Test Firma",
        company_address="Girne",
        company_phone="05338463131",
        company_email="firma@ftm.com",
        admin_username="admin",
        admin_full_name="Sistem Yöneticisi",
        admin_password="123456",
        admin_email="admin@ftm.com",
    )


def _disable_message_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        setup_wizard_preview.QMessageBox,
        "information",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        setup_wizard_preview.QMessageBox,
        "critical",
        lambda *args, **kwargs: None,
    )


def test_setup_wizard_preview_applies_sqlite_setup_after_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_temp_setup_paths(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    _disable_message_boxes(monkeypatch)

    monkeypatch.setattr(
        setup_wizard_preview,
        "_confirm_sqlite_real_setup",
        lambda *, dialog, payload: True,
    )

    payload = _build_valid_sqlite_payload()

    result = setup_wizard_preview._apply_sqlite_setup(
        dialog=None,  # type: ignore[arg-type]
        payload=payload,
    )

    sqlite_file = tmp_path / "data" / "preview_test_ftm.db"

    assert result is not None
    assert sqlite_file.exists() is True
    assert result.sqlite_database_path == str(sqlite_file)
    assert result.table_count > 0
    assert result.role_permission_row_count == len(UserRole) * len(Permission)
    assert result.admin_user_id == 1
    assert result.admin_username == "admin"
    assert result.company_name == "Preview Test Firma"
    assert result.setup_config_saved is True
    assert result.app_settings_saved is True

    setup_config_data = _read_json_file(paths["setup_config_file"])

    assert setup_config_data["setup_completed"] is True
    assert setup_config_data["database_engine"] == "sqlite"
    assert setup_config_data["sqlite_database_path"] == "data/preview_test_ftm.db"

    app_settings_data = _read_json_file(paths["app_settings_file"])

    assert app_settings_data["company_name"] == "Preview Test Firma"
    assert app_settings_data["company_address"] == "Girne"
    assert app_settings_data["company_phone"] == "05338463131"
    assert app_settings_data["company_email"] == "firma@ftm.com"

    engine = create_engine(
        f"sqlite:///{sqlite_file.as_posix()}",
        future=True,
        connect_args={
            "check_same_thread": False,
        },
    )

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    with TestSessionLocal() as session:
        admin_user = session.execute(
            select(User).where(User.username == "admin")
        ).scalar_one()

        role_permission_rows = session.execute(
            select(RolePermission)
        ).scalars().all()

    assert admin_user.full_name == "Sistem Yöneticisi"
    assert admin_user.email == "admin@ftm.com"
    assert admin_user.role == UserRole.ADMIN
    assert admin_user.is_active is True
    assert admin_user.password_hash != "123456"
    assert verify_password("123456", admin_user.password_hash) is True
    assert len(role_permission_rows) == len(UserRole) * len(Permission)


def test_setup_wizard_preview_does_not_apply_sqlite_setup_when_confirmation_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_temp_setup_paths(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    _disable_message_boxes(monkeypatch)

    monkeypatch.setattr(
        setup_wizard_preview,
        "_confirm_sqlite_real_setup",
        lambda *, dialog, payload: False,
    )

    payload = _build_valid_sqlite_payload()

    result = setup_wizard_preview._apply_sqlite_setup(
        dialog=None,  # type: ignore[arg-type]
        payload=payload,
    )

    sqlite_file = tmp_path / "data" / "preview_test_ftm.db"

    assert result is None
    assert sqlite_file.exists() is False
    assert paths["setup_config_file"].exists() is False
    assert paths["app_settings_file"].exists() is False
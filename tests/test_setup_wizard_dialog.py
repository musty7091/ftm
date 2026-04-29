from __future__ import annotations

from typing import Any

import pytest

from app.ui.setup_wizard_dialog import SetupWizardDialog, SetupWizardPayload


def _fill_valid_admin_passwords(dialog: SetupWizardDialog) -> None:
    dialog.admin_password_input.setText("123456")
    dialog.admin_password_repeat_input.setText("123456")


def test_setup_wizard_dialog_can_be_created(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "FTM İlk Kurulum Sihirbazı"
    assert dialog._selected_database_engine() == "sqlite"
    assert dialog.sqlite_database_path_input.text() == "data/ftm_local.db"
    assert dialog.admin_username_input.text() == "admin"


def test_setup_wizard_builds_valid_sqlite_payload(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    _fill_valid_admin_passwords(dialog)

    dialog.database_engine_combo.setCurrentIndex(0)
    dialog.sqlite_database_path_input.setText("data/test_ftm.db")
    dialog.company_name_input.setText("Test Firma")
    dialog.company_phone_input.setText("0392 000 00 00")
    dialog.company_email_input.setText("firma@example.com")
    dialog.admin_username_input.setText("admin")
    dialog.admin_full_name_input.setText("Sistem Yöneticisi")
    dialog.admin_email_input.setText("admin@example.com")

    payload = dialog._build_payload()

    assert isinstance(payload, SetupWizardPayload)
    assert payload.database_engine == "sqlite"
    assert payload.sqlite_database_path == "data/test_ftm.db"
    assert payload.database_host == "localhost"
    assert payload.database_port == 0
    assert payload.database_name == "ftm_db"
    assert payload.database_user == "ftm_user"
    assert payload.database_password == ""
    assert payload.company_name == "Test Firma"
    assert payload.company_phone == "0392 000 00 00"
    assert payload.company_email == "firma@example.com"
    assert payload.admin_username == "admin"
    assert payload.admin_full_name == "Sistem Yöneticisi"
    assert payload.admin_email == "admin@example.com"
    assert payload.admin_password == "123456"


def test_setup_wizard_builds_valid_postgresql_payload(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    _fill_valid_admin_passwords(dialog)

    dialog.database_engine_combo.setCurrentIndex(1)
    dialog.database_host_input.setText("192.168.1.100")
    dialog.database_port_input.setText("5432")
    dialog.database_name_input.setText("ftm_db")
    dialog.database_user_input.setText("ftm_user")
    dialog.database_password_input.setText("ftm_password")
    dialog.company_name_input.setText("Test Firma")
    dialog.admin_username_input.setText("admin")
    dialog.admin_full_name_input.setText("Sistem Yöneticisi")

    payload = dialog._build_payload()

    assert isinstance(payload, SetupWizardPayload)
    assert payload.database_engine == "postgresql"
    assert payload.database_host == "192.168.1.100"
    assert payload.database_port == 5432
    assert payload.database_name == "ftm_db"
    assert payload.database_user == "ftm_user"
    assert payload.database_password == "ftm_password"
    assert payload.company_name == "Test Firma"
    assert payload.admin_username == "admin"
    assert payload.admin_full_name == "Sistem Yöneticisi"
    assert payload.admin_password == "123456"


def test_setup_wizard_rejects_password_mismatch(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    dialog.admin_password_input.setText("123456")
    dialog.admin_password_repeat_input.setText("654321")

    with pytest.raises(ValueError, match="ADMIN şifreleri aynı olmalıdır"):
        dialog._build_payload()


def test_setup_wizard_rejects_short_admin_password(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    dialog.admin_password_input.setText("123")
    dialog.admin_password_repeat_input.setText("123")

    with pytest.raises(ValueError, match="ADMIN şifresi en az 6 karakter"):
        dialog._build_payload()


def test_setup_wizard_rejects_parent_directory_sqlite_path(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    _fill_valid_admin_passwords(dialog)

    dialog.database_engine_combo.setCurrentIndex(0)
    dialog.sqlite_database_path_input.setText("../danger.db")

    with pytest.raises(ValueError, match="SQLite veritabanı yolunda"):
        dialog._build_payload()


def test_setup_wizard_rejects_invalid_postgresql_port(qtbot: Any) -> None:
    dialog = SetupWizardDialog()

    qtbot.addWidget(dialog)

    _fill_valid_admin_passwords(dialog)

    dialog.database_engine_combo.setCurrentIndex(1)
    dialog.database_host_input.setText("localhost")
    dialog.database_port_input.setText("port-degil")
    dialog.database_name_input.setText("ftm_db")
    dialog.database_user_input.setText("ftm_user")
    dialog.database_password_input.setText("ftm_password")

    with pytest.raises(ValueError, match="PostgreSQL port sayısal olmalıdır"):
        dialog._build_payload()
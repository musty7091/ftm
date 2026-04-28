from __future__ import annotations

from app.core.config import BASE_DIR
from app.services.app_settings_service import (
    default_app_settings_dict,
    normalize_app_settings_payload,
    normalize_mail_recipients_text,
    parse_mail_recipients,
    resolve_runtime_folder,
)


REQUIRED_APP_SETTINGS_KEYS = {
    "company_name",
    "company_address",
    "company_phone",
    "company_email",
    "backup_folder",
    "export_folder",
    "log_folder",
    "control_mail_enabled",
    "control_mail_to",
    "report_footer_note",
}


def test_default_app_settings_dict_has_required_keys() -> None:
    settings_dict = default_app_settings_dict()

    missing_keys = REQUIRED_APP_SETTINGS_KEYS.difference(settings_dict.keys())

    assert missing_keys == set()


def test_parse_mail_recipients_accepts_multiple_separators() -> None:
    raw_value = "mustafa@example.com; muhasebe@example.com, kontrol@example.com"

    recipients = parse_mail_recipients(raw_value)

    assert recipients == [
        "mustafa@example.com",
        "muhasebe@example.com",
        "kontrol@example.com",
    ]


def test_parse_mail_recipients_removes_invalid_and_duplicate_values() -> None:
    raw_value = (
        "mustafa@example.com; "
        "gecersiz-mail; "
        "mustafa@example.com; "
        "kontrol@example.com"
    )

    recipients = parse_mail_recipients(raw_value)

    assert recipients == [
        "mustafa@example.com",
        "kontrol@example.com",
    ]


def test_normalize_mail_recipients_text_uses_semicolon_separator() -> None:
    raw_value = "mustafa@example.com, kontrol@example.com"

    normalized_text = normalize_mail_recipients_text(raw_value)

    assert normalized_text == "mustafa@example.com; kontrol@example.com"


def test_normalize_app_settings_payload_cleans_invalid_company_email() -> None:
    payload = default_app_settings_dict()
    payload["company_email"] = "gecersiz-mail-adresi"

    normalized_payload = normalize_app_settings_payload(payload)

    assert normalized_payload["company_email"] == ""


def test_normalize_app_settings_payload_uses_default_for_empty_folder_values() -> None:
    payload = default_app_settings_dict()
    payload["backup_folder"] = ""
    payload["export_folder"] = ""
    payload["log_folder"] = ""

    normalized_payload = normalize_app_settings_payload(payload)

    assert normalized_payload["backup_folder"] == "backups"
    assert normalized_payload["export_folder"] == "exports"
    assert normalized_payload["log_folder"] == "logs"


def test_normalize_app_settings_payload_blocks_parent_directory_folder_values() -> None:
    payload = default_app_settings_dict()
    payload["backup_folder"] = "../danger"
    payload["export_folder"] = "exports"
    payload["log_folder"] = "logs"

    normalized_payload = normalize_app_settings_payload(payload)

    assert normalized_payload["backup_folder"] == "backups"


def test_resolve_runtime_folder_returns_base_dir_for_relative_folder() -> None:
    folder_path = resolve_runtime_folder("backups")

    assert folder_path == BASE_DIR / "backups"


def test_resolve_runtime_folder_uses_outputs_for_blocked_folder_value() -> None:
    folder_path = resolve_runtime_folder("../danger")

    assert folder_path == BASE_DIR / "outputs"
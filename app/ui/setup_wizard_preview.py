from __future__ import annotations

import sys
from dataclasses import asdict

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.services.sqlite_setup_apply_service import (
    SqliteSetupApplyServiceError,
    SqliteSetupApplyResult,
    apply_sqlite_initial_setup,
)
from app.ui.setup_wizard_dialog import SetupWizardDialog, SetupWizardPayload


def _masked_payload_dict(payload: SetupWizardPayload) -> dict:
    payload_dict = asdict(payload)

    if payload_dict.get("database_password"):
        payload_dict["database_password"] = "********"

    if payload_dict.get("admin_password"):
        payload_dict["admin_password"] = "********"

    return payload_dict


def _print_payload(payload: SetupWizardPayload) -> None:
    payload_dict = _masked_payload_dict(payload)

    print("")
    print("=" * 80)
    print("FTM Kurulum Sihirbazı Sonucu")
    print("=" * 80)

    print("")
    print("Yerel Veritabanı")
    print("-" * 80)
    print(f"database_engine       : {payload_dict['database_engine']}")
    print(f"sqlite_database_path  : {payload_dict['sqlite_database_path']}")

    print("")
    print("Firma")
    print("-" * 80)
    print(f"company_name          : {payload_dict['company_name']}")
    print(f"company_address       : {payload_dict['company_address']}")
    print(f"company_phone         : {payload_dict['company_phone']}")
    print(f"company_email         : {payload_dict['company_email']}")

    print("")
    print("İlk ADMIN")
    print("-" * 80)
    print(f"admin_username        : {payload_dict['admin_username']}")
    print(f"admin_full_name       : {payload_dict['admin_full_name']}")
    print(f"admin_email           : {payload_dict['admin_email']}")
    print(f"admin_password        : {payload_dict['admin_password']}")

    print("")
    print("=" * 80)
    print("Kurulum bilgileri okundu.")
    print("=" * 80)
    print("")


def _print_sqlite_apply_result(result: SqliteSetupApplyResult) -> None:
    print("")
    print("=" * 80)
    print("FTM SQLite Kurulum Sonucu")
    print("=" * 80)

    print("")
    print("Oluşturulan / Güncellenen Bilgiler")
    print("-" * 80)
    print(f"sqlite_database_path          : {result.sqlite_database_path}")
    print(f"table_count                   : {result.table_count}")
    print(f"role_permission_row_count     : {result.role_permission_row_count}")
    print(f"admin_user_id                 : {result.admin_user_id}")
    print(f"admin_username                : {result.admin_username}")
    print(f"company_name                  : {result.company_name}")
    print(f"setup_config_saved            : {result.setup_config_saved}")
    print(f"app_settings_saved            : {result.app_settings_saved}")

    print("")
    print("=" * 80)
    print("SQLite kurulumu başarıyla tamamlandı.")
    print("=" * 80)
    print("")


def _confirm_sqlite_real_setup(
    *,
    dialog: SetupWizardDialog,
    payload: SetupWizardPayload,
) -> bool:
    message = (
        "SQLite kurulumu gerçek olarak uygulanacak.\n\n"
        "Bu işlem şunları yapacak:\n"
        "- AppData\\Local\\FTM\\config\\app_setup.json dosyasını yazacak\n"
        "- AppData\\Local\\FTM\\config\\app_settings.json dosyasını yazacak\n"
        "- SQLite veritabanı dosyasını oluşturacak\n"
        "- Veritabanı tablolarını oluşturacak\n"
        "- Rol / yetki kayıtlarını oluşturacak\n"
        "- İlk ADMIN kullanıcısını oluşturacak\n\n"
        f"SQLite dosyası:\n{payload.sqlite_database_path}\n\n"
        "Devam etmek istiyor musun?"
    )

    answer = QMessageBox.question(
        dialog,
        "SQLite Kurulum Onayı",
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )

    return answer == QMessageBox.Yes


def _apply_sqlite_setup(
    *,
    dialog: SetupWizardDialog,
    payload: SetupWizardPayload,
) -> SqliteSetupApplyResult | None:
    if payload.database_engine != "sqlite":
        QMessageBox.warning(
            dialog,
            "Geçersiz Veritabanı Tipi",
            (
                "FTM artık yalnızca SQLite local desktop kurulumunu destekler.\n\n"
                f"Gelen değer: {payload.database_engine}"
            ),
        )
        return None

    if not _confirm_sqlite_real_setup(dialog=dialog, payload=payload):
        print("")
        print("SQLite kurulumu kullanıcı tarafından iptal edildi.")
        print("Herhangi bir kurulum işlemi uygulanmadı.")
        print("")
        return None

    try:
        result = apply_sqlite_initial_setup(
            sqlite_database_path=payload.sqlite_database_path,
            company_name=payload.company_name,
            company_address=payload.company_address,
            company_phone=payload.company_phone,
            company_email=payload.company_email,
            admin_username=payload.admin_username,
            admin_full_name=payload.admin_full_name,
            admin_password=payload.admin_password,
            admin_email=payload.admin_email,
        )

    except SqliteSetupApplyServiceError as exc:
        QMessageBox.critical(
            dialog,
            "SQLite Kurulumu Başarısız",
            f"SQLite kurulumu tamamlanamadı:\n\n{exc}",
        )
        raise

    except Exception as exc:
        QMessageBox.critical(
            dialog,
            "SQLite Kurulumu Beklenmeyen Hata",
            f"SQLite kurulumu sırasında beklenmeyen bir hata oluştu:\n\n{exc}",
        )
        raise

    _print_sqlite_apply_result(result)

    QMessageBox.information(
        dialog,
        "SQLite Kurulumu Tamamlandı",
        "SQLite kurulumu başarıyla tamamlandı.\n\n"
        "Oluşturulanlar:\n"
        "- AppData\\Local\\FTM\\config\\app_setup.json\n"
        "- AppData\\Local\\FTM\\config\\app_settings.json\n"
        "- SQLite veritabanı dosyası\n"
        "- Veritabanı tabloları\n"
        "- Rol / yetki kayıtları\n"
        "- İlk ADMIN kullanıcısı\n\n"
        "Detayları PowerShell ekranında görebilirsin.",
    )

    return result


def main() -> None:
    app = QApplication(sys.argv)

    dialog = SetupWizardDialog()

    result = dialog.exec()

    if result != QDialog.Accepted:
        print("")
        print("Kurulum sihirbazı iptal edildi. Herhangi bir işlem yapılmadı.")
        print("")
        sys.exit(0)

    try:
        payload = dialog.get_payload()
    except Exception as exc:
        QMessageBox.critical(
            dialog,
            "Kurulum Bilgileri Okunamadı",
            f"Kurulum bilgileri okunurken hata oluştu:\n\n{exc}",
        )
        sys.exit(1)

    _print_payload(payload)

    try:
        setup_result = _apply_sqlite_setup(
            dialog=dialog,
            payload=payload,
        )
    except Exception:
        sys.exit(1)

    if setup_result is None:
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
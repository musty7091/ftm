from __future__ import annotations

import sys
from dataclasses import asdict

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

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
    print("FTM Kurulum Sihirbazı Önizleme Sonucu")
    print("=" * 80)

    print("")
    print("Veritabanı")
    print("-" * 80)
    print(f"database_engine       : {payload_dict['database_engine']}")
    print(f"sqlite_database_path  : {payload_dict['sqlite_database_path']}")
    print(f"database_host         : {payload_dict['database_host']}")
    print(f"database_port         : {payload_dict['database_port']}")
    print(f"database_name         : {payload_dict['database_name']}")
    print(f"database_user         : {payload_dict['database_user']}")
    print(f"database_password     : {payload_dict['database_password']}")

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
    print("Not: Bu önizleme dosyası hiçbir ayarı kaydetmez ve veritabanı oluşturmaz.")
    print("=" * 80)
    print("")


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

    QMessageBox.information(
        dialog,
        "Önizleme Tamamlandı",
        "Kurulum sihirbazı bilgileri başarıyla okundu.\n\n"
        "Bu önizleme hiçbir ayarı kaydetmedi ve veritabanı oluşturmadı.\n"
        "Detayları PowerShell ekranında görebilirsin.",
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
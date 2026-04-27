from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.security_system.shared import build_tab_page


def build_system_settings_tab() -> QWidget:
    return build_tab_page(
        section_title="Sistem Ayarları",
        section_body=(
            "Şirket bilgileri, varsayılan para birimi, uygulama davranışları ve genel "
            "sistem tercihleri bu sekmede yönetilecek."
        ),
        cards=[
            (
                "Şirket Bilgileri",
                "Raporlarda kullanılacak şirket adı, adres ve iletişim bilgileri burada olacak.",
                "Planlandı",
                "info",
            ),
            (
                "Genel Ayarlar",
                "Varsayılan para birimi, rapor klasörü ve sistem tercihleri burada düzenlenecek.",
                "Planlandı",
                "warning",
            ),
            (
                "Sağlık Kontrolü",
                "Veritabanı, dosya yolu ve temel sistem kontrolleri burada görünecek.",
                "Planlandı",
                "success",
            ),
        ],
    )


__all__ = [
    "build_system_settings_tab",
]
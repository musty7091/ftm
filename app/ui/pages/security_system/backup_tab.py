from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.security_system.shared import build_tab_page


def build_backup_tab() -> QWidget:
    return build_tab_page(
        section_title="Yedekleme ve Geri Yükleme",
        section_body=(
            "Veritabanı yedekleme, yedek dosya doğrulama, geri yükleme testi ve güvenli "
            "saklama ayarları bu sekmede ele alınacak."
        ),
        cards=[
            (
                "Manuel Yedekleme",
                "ADMIN tek tuşla güvenli yedek alabilecek.",
                "Planlandı",
                "success",
            ),
            (
                "Geri Yükleme Testi",
                "Yedek dosyanın gerçekten çalışıp çalışmadığı test edilecek.",
                "Planlandı",
                "warning",
            ),
            (
                "Yedek Geçmişi",
                "Alınan yedeklerin tarihi, konumu ve sonucu listelenecek.",
                "Planlandı",
                "info",
            ),
        ],
    )


__all__ = [
    "build_backup_tab",
]
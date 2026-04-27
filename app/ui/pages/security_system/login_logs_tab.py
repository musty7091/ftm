from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.security_system.shared import build_tab_page


def build_login_logs_tab() -> QWidget:
    return build_tab_page(
        section_title="Giriş Kayıtları",
        section_body=(
            "Başarılı ve başarısız giriş denemeleri, kilitlenen kullanıcılar ve son giriş "
            "bilgileri bu sekmede izlenecek."
        ),
        cards=[
            (
                "Başarılı Girişler",
                "Kim, ne zaman giriş yaptı bilgisi burada listelenecek.",
                "Planlandı",
                "info",
            ),
            (
                "Başarısız Denemeler",
                "Hatalı şifre ve yetkisiz giriş denemeleri burada izlenecek.",
                "Planlandı",
                "risk",
            ),
            (
                "Kilit Politikası",
                "Çok sayıda hatalı girişte kullanıcıyı geçici kilitleme yapısı burada yönetilecek.",
                "Planlandı",
                "warning",
            ),
        ],
    )


__all__ = [
    "build_login_logs_tab",
]
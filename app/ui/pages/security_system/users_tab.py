from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.security_system.shared import build_tab_page


def build_users_tab() -> QWidget:
    return build_tab_page(
        section_title="Kullanıcı Yönetimi",
        section_body=(
            "Bu sekmede kullanıcı ekleme, kullanıcı düzenleme, kullanıcı pasif/aktif yapma, "
            "şifre sıfırlama ve rol değiştirme işlemleri yer alacak."
        ),
        cards=[
            (
                "Kullanıcı Listesi",
                "Sistemde kayıtlı kullanıcıların tablo halinde listeleneceği alan.",
                "Hazırlanıyor",
                "info",
            ),
            (
                "Yeni Kullanıcı",
                "ADMIN yetkisiyle yeni kullanıcı oluşturma formu bu alana eklenecek.",
                "Planlandı",
                "success",
            ),
            (
                "Şifre Sıfırlama",
                "Kullanıcı şifresini güvenli şekilde yenileme işlemi burada olacak.",
                "Planlandı",
                "warning",
            ),
        ],
    )


__all__ = [
    "build_users_tab",
]
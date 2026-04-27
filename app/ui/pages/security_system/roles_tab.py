from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.security_system.shared import build_tab_page


def build_roles_tab() -> QWidget:
    return build_tab_page(
        section_title="Roller ve Yetkiler",
        section_body=(
            "Bu sekmede ADMIN, FINANCE, DATA_ENTRY ve VIEWER rollerinin hangi modüllere "
            "erişebileceği sade bir tabloyla gösterilecek."
        ),
        cards=[
            (
                "Rol Matrisi",
                "Hangi rolün hangi sayfayı görebileceğini gösteren yetki tablosu.",
                "Hazırlanıyor",
                "info",
            ),
            (
                "Menü Yetkileri",
                "Sol menüde görünen modüllerin role göre kontrol edildiği alan.",
                "Aktif",
                "success",
            ),
            (
                "Kritik Yetkiler",
                "Silme, iptal, düzeltme ve yönetici işlemleri ayrıca sınırlandırılacak.",
                "Planlandı",
                "warning",
            ),
        ],
    )


__all__ = [
    "build_roles_tab",
]
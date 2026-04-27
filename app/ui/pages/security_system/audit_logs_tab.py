from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.ui.pages.security_system.shared import build_tab_page


def build_audit_logs_tab() -> QWidget:
    return build_tab_page(
        section_title="İşlem Kayıtları",
        section_body=(
            "Banka, çek, POS, cari kart ve kullanıcı yönetimi gibi kritik işlemlerde "
            "kim ne yaptı sorusunun cevabı burada tutulacak."
        ),
        cards=[
            (
                "Audit Log",
                "Kritik ekleme, güncelleme, silme ve iptal işlemleri burada listelenecek.",
                "Hazırlanıyor",
                "info",
            ),
            (
                "Kullanıcı İzleme",
                "Kullanıcı bazlı işlem geçmişi filtreleri bu alana eklenecek.",
                "Planlandı",
                "success",
            ),
            (
                "Riskli İşlemler",
                "Silme, iptal ve tutar değişikliği gibi işlemler ayrı takip edilecek.",
                "Planlandı",
                "risk",
            ),
        ],
    )


__all__ = [
    "build_audit_logs_tab",
]
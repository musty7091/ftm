from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def build_discount_reports_tab(
    *,
    on_discount_batch_report_click: Callable[[], None] | None = None,
    on_financing_cost_report_click: Callable[[], None] | None = None,
) -> QWidget:
    return build_planned_reports_tab(
        title_text="İskonto / Maliyet Raporları",
        subtitle_text=(
            "İskonto işlemlerinde oluşan faiz, komisyon, BSMV, toplam maliyet, "
            "net banka tutarı, ortalama vade ve kullanılan çekler bu rapor üzerinden takip edilir."
        ),
        reports=[
            (
                "İskonto Maliyet Raporu",
                (
                    "Seçilen iskonto paketinin veya belirli dönem içindeki iskonto işlemlerinin "
                    "faiz, komisyon, BSMV, toplam maliyet, net banka tutarı, ortalama vade, "
                    "maliyet oranı ve kullanılan çeklerini gösterir."
                ),
                "Rapor Al",
                "Aktif",
                on_financing_cost_report_click,
            ),
        ],
    )


def build_excel_reports_tab() -> QWidget:
    return build_planned_reports_tab(
        title_text="Excel Aktarım",
        subtitle_text="PDF raporların yanında ham verilerin Excel olarak dışa aktarılması burada yönetilecek.",
        reports=[
            (
                "Çek Listesi Excel",
                "Alınan ve yazılan çekleri filtreli Excel dosyasına aktarır.",
                "Yakında",
                "Planlandı",
                None,
            ),
            (
                "Banka Hareketleri Excel",
                "Banka giriş/çıkış hareketlerini Excel olarak dışa aktarır.",
                "Yakında",
                "Planlandı",
                None,
            ),
            (
                "POS Mutabakat Excel",
                "POS mutabakat kayıtlarını Excel olarak dışa aktarır.",
                "Yakında",
                "Planlandı",
                None,
            ),
            (
                "İskonto Maliyet Excel",
                "İskonto maliyetlerini, faiz, komisyon, BSMV ve net banka tutarlarını Excel olarak verir.",
                "Yakında",
                "Planlandı",
                None,
            ),
        ],
    )


def build_planned_reports_tab(
    *,
    title_text: str,
    subtitle_text: str,
    reports: Sequence[tuple[str, str, str, str, Callable[[], None] | None]],
) -> QWidget:
    tab = QWidget()

    layout = QVBoxLayout(tab)
    layout.setContentsMargins(12, 14, 12, 12)
    layout.setSpacing(12)

    card = QFrame()
    card.setObjectName("PlannedReportsCard")

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 16, 18, 16)
    card_layout.setSpacing(14)

    title = QLabel(title_text)
    title.setObjectName("ReportSectionTitle")

    subtitle = QLabel(subtitle_text)
    subtitle.setObjectName("ReportSubTitle")
    subtitle.setWordWrap(True)

    card_layout.addWidget(title)
    card_layout.addWidget(subtitle)

    for report_title, report_body, button_text, badge_text, callback in reports:
        card_layout.addWidget(
            build_planned_report_box(
                title_text=report_title,
                body_text=report_body,
                button_text=button_text,
                badge_text=badge_text,
                callback=callback,
            )
        )

    layout.addWidget(card)
    layout.addStretch(1)

    return tab


def build_planned_report_box(
    *,
    title_text: str,
    body_text: str,
    button_text: str = "Yakında",
    badge_text: str = "Planlandı",
    callback: Callable[[], None] | None = None,
) -> QWidget:
    box = QFrame()
    box.setObjectName("PlannedReportBox")

    layout = QHBoxLayout(box)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(12)

    text_box = QVBoxLayout()
    text_box.setSpacing(4)

    title = QLabel(title_text)
    title.setObjectName("ReportPlannedTitle")

    body = QLabel(body_text)
    body.setObjectName("ReportPlannedBody")
    body.setWordWrap(True)

    text_box.addWidget(title)
    text_box.addWidget(body)

    badge = QLabel(badge_text)

    button = QPushButton(button_text)

    if callback is None:
        badge.setObjectName("ReportPlannedBadge")
        button.setObjectName("PlannedButton")
        button.setEnabled(False)
    else:
        badge.setObjectName("ReportActiveBadge")
        button.setObjectName("QuickReportButton")
        button.setEnabled(True)
        button.clicked.connect(callback)

    layout.addLayout(text_box, 1)
    layout.addWidget(badge, 0, Qt.AlignVCenter)
    layout.addWidget(button, 0, Qt.AlignVCenter)

    return box


__all__ = [
    "build_discount_reports_tab",
    "build_excel_reports_tab",
    "build_planned_reports_tab",
    "build_planned_report_box",
]
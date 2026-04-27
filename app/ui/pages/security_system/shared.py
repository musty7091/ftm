from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


SECURITY_SYSTEM_PAGE_STYLE = """
QFrame#SecuritySystemHero {
    background-color: rgba(15, 23, 42, 0.78);
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#SecuritySystemCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#SecuritySystemInfoBox {
    background-color: rgba(15, 23, 42, 0.64);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QFrame#SecuritySystemWarningBox {
    background-color: rgba(120, 53, 15, 0.25);
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 14px;
}

QFrame#SecuritySystemSuccessBox {
    background-color: rgba(6, 78, 59, 0.25);
    border: 1px solid rgba(16, 185, 129, 0.42);
    border-radius: 14px;
}

QFrame#SecuritySystemRiskBox {
    background-color: rgba(127, 29, 29, 0.25);
    border: 1px solid rgba(239, 68, 68, 0.42);
    border-radius: 14px;
}

QLabel#SecuritySystemTitle {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 900;
}

QLabel#SecuritySystemSectionTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#SecuritySystemSubTitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SecuritySystemCardTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
    background-color: transparent;
    border: none;
}

QLabel#SecuritySystemCardBody {
    color: #94a3b8;
    font-size: 12px;
    background-color: transparent;
    border: none;
}

QLabel#SecuritySystemBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 4px 8px;
}

QLabel#SecuritySystemAdminBadge {
    color: #d1fae5;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(6, 78, 59, 0.34);
    border: 1px solid rgba(16, 185, 129, 0.42);
    border-radius: 8px;
    padding: 4px 8px;
}

QTabWidget#SecuritySystemTabs {
    background-color: #0f172a;
    border: none;
}

QTabWidget#SecuritySystemTabs::pane {
    border: 1px solid #24324a;
    border-radius: 16px;
    background-color: #0f172a;
    top: -1px;
}

QTabWidget#SecuritySystemTabs::tab-bar {
    alignment: left;
    background-color: #0f172a;
}

QTabBar {
    background-color: #0f172a;
}

QTabBar::tab {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-bottom: none;
    padding: 10px 16px;
    min-width: 125px;
    font-weight: 800;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-bottom: none;
}

QTabBar::tab:hover {
    background-color: #334155;
    color: #ffffff;
}

QPushButton#SecuritySystemPassiveButton {
    background-color: #1f2937;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 800;
}

QPushButton#SecuritySystemPassiveButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}
"""


def build_security_tab_page(
    *,
    section_title: str,
    section_body: str,
    cards: list[tuple[str, str, str, str]],
    footer_text: str,
) -> QWidget:
    page = QWidget()

    layout = QVBoxLayout(page)
    layout.setContentsMargins(12, 14, 12, 12)
    layout.setSpacing(12)

    card = QFrame()
    card.setObjectName("SecuritySystemCard")

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 16, 18, 16)
    card_layout.setSpacing(14)

    title = QLabel(section_title)
    title.setObjectName("SecuritySystemSectionTitle")

    body = QLabel(section_body)
    body.setObjectName("SecuritySystemSubTitle")
    body.setWordWrap(True)

    card_layout.addWidget(title)
    card_layout.addWidget(body)

    grid = QGridLayout()
    grid.setSpacing(12)

    for index, item in enumerate(cards):
        item_title, item_body, badge_text, card_type = item

        grid.addWidget(
            build_security_info_box(
                title_text=item_title,
                body_text=item_body,
                badge_text=badge_text,
                card_type=card_type,
            ),
            index // 3,
            index % 3,
        )

    card_layout.addLayout(grid)

    footer = QLabel(footer_text)
    footer.setObjectName("SecuritySystemSubTitle")
    footer.setWordWrap(True)

    passive_button = QPushButton("Bu bölüm adım adım gerçek veriye bağlanacak")
    passive_button.setObjectName("SecuritySystemPassiveButton")
    passive_button.setEnabled(False)

    card_layout.addWidget(footer)
    card_layout.addWidget(passive_button, 0, Qt.AlignRight)

    layout.addWidget(card)
    layout.addStretch(1)

    return page


def build_tab_page(
    *,
    section_title: str,
    section_body: str,
    cards: list[tuple[str, str, str, str]],
) -> QWidget:
    return build_security_tab_page(
        section_title=section_title,
        section_body=section_body,
        cards=cards,
        footer_text=(
            "Bu sekme şu anda modüler iskelet olarak hazırlanmıştır. "
            "Gerçek tablo, form ve veritabanı bağlantıları sonraki adımlarda tek tek eklenecek."
        ),
    )


def build_security_info_box(
    *,
    title_text: str,
    body_text: str,
    badge_text: str,
    card_type: str,
) -> QWidget:
    box = QFrame()
    box.setObjectName(_info_box_object_name(card_type))

    layout = QVBoxLayout(box)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    header_row = QHBoxLayout()
    header_row.setSpacing(8)

    title = QLabel(title_text)
    title.setObjectName("SecuritySystemCardTitle")
    title.setWordWrap(True)

    badge = QLabel(badge_text)
    badge.setObjectName("SecuritySystemBadge")

    header_row.addWidget(title, 1)
    header_row.addWidget(badge, 0, Qt.AlignTop)

    body = QLabel(body_text)
    body.setObjectName("SecuritySystemCardBody")
    body.setWordWrap(True)

    layout.addLayout(header_row)
    layout.addWidget(body)
    layout.addStretch(1)

    return box


def _info_box_object_name(card_type: str) -> str:
    normalized_type = str(card_type or "info").strip().lower()

    if normalized_type == "success":
        return "SecuritySystemSuccessBox"

    if normalized_type == "warning":
        return "SecuritySystemWarningBox"

    if normalized_type == "risk":
        return "SecuritySystemRiskBox"

    return "SecuritySystemInfoBox"


__all__ = [
    "SECURITY_SYSTEM_PAGE_STYLE",
    "build_security_tab_page",
    "build_tab_page",
    "build_security_info_box",
]
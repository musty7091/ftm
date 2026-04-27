from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QVBoxLayout, QWidget


def build_check_reports_tab(reports_page: Any) -> QWidget:
    tab = QWidget()

    layout = QVBoxLayout(tab)
    layout.setContentsMargins(12, 14, 12, 12)
    layout.setSpacing(12)

    layout.addWidget(reports_page._build_quick_check_reports_card())
    layout.addWidget(reports_page._build_custom_check_reports_card())
    layout.addStretch(1)

    return tab


__all__ = [
    "build_check_reports_tab",
]
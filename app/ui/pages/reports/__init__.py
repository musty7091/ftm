from __future__ import annotations

from app.ui.pages.reports.bank_reports_tab import build_bank_reports_tab
from app.ui.pages.reports.check_reports_tab import build_check_reports_tab
from app.ui.pages.reports.planned_reports_tab import (
    build_discount_reports_tab,
    build_excel_reports_tab,
    build_planned_reports_tab,
)
from app.ui.pages.reports.pos_reports_tab import build_pos_reports_tab

__all__ = [
    "build_bank_reports_tab",
    "build_check_reports_tab",
    "build_discount_reports_tab",
    "build_excel_reports_tab",
    "build_planned_reports_tab",
    "build_pos_reports_tab",
]
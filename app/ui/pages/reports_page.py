from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.reports.bank_movement_report_data import BankMovementReportFilter
from app.reports.bank_movement_report_pdf import create_bank_movement_report_pdf
from app.reports.check_due_report_data import CheckDueReportFilter
from app.reports.check_due_report_pdf import create_check_due_report_pdf
from app.reports.check_due_report_excel import create_check_due_report_excel
from app.reports.pos_settlement_report_data import PosSettlementReportFilter
from app.reports.discount_batch_report_data import (
    DiscountBatchReportFilter,
    list_discount_batch_options,
)
from app.reports.discount_batch_report_pdf import create_discount_batch_report_pdf
from app.reports.financing_cost_report_data import FinancingCostReportFilter
from app.reports.financing_cost_report_pdf import create_financing_cost_report_pdf
from app.reports.financing_cost_report_excel import create_financing_cost_report_excel
from app.reports.pos_settlement_report_pdf import create_pos_settlement_report_pdf
from app.reports.risk_check_report_data import RiskCheckReportFilter
from app.reports.risk_check_report_pdf import create_risk_check_report_pdf
from app.ui.pages.reports import (
    build_discount_reports_tab,
    build_excel_reports_tab,
)
from app.ui.pages.reports.check_excel_filter_dialog import get_check_excel_filter_selection

REPORTS_PAGE_STYLE = """
QFrame#ReportsInfoStrip {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid #24324a;
    border-radius: 16px;
}

QTabWidget#ReportsTabs {
    background-color: #0f172a;
    border: none;
}

QTabWidget#ReportsTabs::pane {
    border: 1px solid #24324a;
    border-radius: 16px;
    background-color: #0f172a;
    top: -1px;
}

QTabWidget#ReportsTabs::tab-bar {
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
    padding: 10px 18px;
    min-width: 130px;
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

QTabBar::scroller {
    background-color: #0f172a;
}

QTabBar QToolButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 6px;
}

QFrame#QuickReportsCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#CustomReportsCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#ReportFilterPanel {
    background-color: rgba(15, 23, 42, 0.82);
    border: 1px solid rgba(51, 65, 85, 0.88);
    border-radius: 14px;
}

QFrame#PlannedReportsCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#QuickReportBox {
    background-color: rgba(15, 23, 42, 0.62);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QFrame#RiskQuickReportBox {
    background-color: rgba(127, 29, 29, 0.25);
    border: 1px solid rgba(239, 68, 68, 0.42);
    border-radius: 14px;
}

QFrame#PlannedReportBox {
    background-color: rgba(15, 23, 42, 0.56);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 12px;
}

QLabel#ReportTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 900;
}

QLabel#ReportSectionTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#ReportSubTitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#ReportFieldLabel {
    color: #bfdbfe;
    font-size: 12px;
    font-weight: 700;
}

QLabel#ReportSmallInfo {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#QuickReportTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
    background-color: transparent;
    border: none;
}

QLabel#QuickReportBody {
    color: #94a3b8;
    font-size: 12px;
    background-color: transparent;
    border: none;
}

QLabel#ReportActiveBadge {
    color: #d1fae5;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(6, 78, 59, 0.34);
    border: 1px solid rgba(16, 185, 129, 0.42);
    border-radius: 8px;
    padding: 4px 7px;
}

QLabel#ReportPlannedTitle {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 900;
    background-color: transparent;
    border: none;
}

QLabel#ReportPlannedBody {
    color: #94a3b8;
    font-size: 12px;
    background-color: transparent;
    border: none;
}

QLabel#ReportPlannedBadge {
    color: #bfdbfe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.38);
    border-radius: 8px;
    padding: 4px 7px;
}

QComboBox,
QDateEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 7px 10px;
    font-size: 12px;
}

QComboBox:hover,
QDateEdit:hover {
    border: 1px solid #475569;
}

QComboBox:focus,
QDateEdit:focus {
    border: 1px solid #3b82f6;
}

QComboBox::drop-down,
QDateEdit::drop-down {
    border: none;
    width: 26px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
}

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 8px;
    color: #e5e7eb;
    background-color: #111827;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QPushButton#QuickReportButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 9px 14px;
    font-weight: 900;
}

QPushButton#QuickReportButton:hover {
    background-color: #1d4ed8;
}

QPushButton#BankReportButton {
    background-color: rgba(6, 95, 70, 0.82);
    color: #ffffff;
    border: 1px solid rgba(16, 185, 129, 0.68);
    border-radius: 12px;
    padding: 9px 14px;
    font-weight: 900;
}

QPushButton#BankReportButton:hover {
    background-color: rgba(5, 150, 105, 0.92);
}

QPushButton#PosReportButton {
    background-color: rgba(124, 58, 237, 0.82);
    color: #ffffff;
    border: 1px solid rgba(167, 139, 250, 0.72);
    border-radius: 12px;
    padding: 9px 14px;
    font-weight: 900;
}

QPushButton#PosReportButton:hover {
    background-color: rgba(109, 40, 217, 0.94);
}

QPushButton#RiskReportButton {
    background-color: rgba(127, 29, 29, 0.78);
    color: #ffffff;
    border: 1px solid rgba(239, 68, 68, 0.72);
    border-radius: 12px;
    padding: 9px 14px;
    font-weight: 900;
}

QPushButton#RiskReportButton:hover {
    background-color: rgba(153, 27, 27, 0.92);
}

QPushButton#CustomReportButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 9px 18px;
    font-weight: 900;
}

QPushButton#CustomReportButton:hover {
    background-color: #1d4ed8;
}

QPushButton#CustomBankReportButton {
    background-color: rgba(6, 95, 70, 0.82);
    color: #ffffff;
    border: 1px solid rgba(16, 185, 129, 0.68);
    border-radius: 12px;
    padding: 9px 18px;
    font-weight: 900;
}

QPushButton#CustomBankReportButton:hover {
    background-color: rgba(5, 150, 105, 0.92);
}

QPushButton#CustomPosReportButton {
    background-color: rgba(124, 58, 237, 0.82);
    color: #ffffff;
    border: 1px solid rgba(167, 139, 250, 0.72);
    border-radius: 12px;
    padding: 9px 18px;
    font-weight: 900;
}

QPushButton#CustomPosReportButton:hover {
    background-color: rgba(109, 40, 217, 0.94);
}

QPushButton#ReportQuickButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 700;
}

QPushButton#ReportQuickButton:hover {
    background-color: #334155;
    color: #ffffff;
}

QPushButton#PlannedButton {
    background-color: #1f2937;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 800;
}

QPushButton#PlannedButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}
"""


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def _safe_file_name_text(value: str) -> str:
    text = str(value or "").strip()

    replacements = {
        " ": "_",
        "/": "-",
        "\\": "-",
        ":": "-",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    while "__" in text:
        text = text.replace("__", "_")

    return text.strip("_") or "FTM_Rapor"


def _default_reports_folder() -> Path:
    documents_folder = Path.home() / "Documents"
    reports_folder = documents_folder / "FTM Raporlar"

    return reports_folder


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


def _username_text(current_user: Any | None) -> str:
    if current_user is None:
        return "FTM Kullanıcısı"

    for attribute_name in ("username", "name", "full_name", "email"):
        value = getattr(current_user, attribute_name, None)

        if value:
            return str(value)

    return "FTM Kullanıcısı"


def _created_by_text(current_user: Any | None) -> str:
    username = _username_text(current_user)
    role = _role_text(getattr(current_user, "role", None))

    if role:
        return f"{username} / {role}"

    return username


def _current_month_range() -> tuple[date, date]:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        next_month = date(today.year, today.month + 1, 1)
        end_date = next_month - timedelta(days=1)

    return start_date, end_date


def _current_year_range() -> tuple[date, date]:
    today = date.today()

    return date(today.year, 1, 1), date(today.year, 12, 31)


class ReportsPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.setStyleSheet(REPORTS_PAGE_STYLE)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        self._build_page()

    def _create_next_30_days_check_due_report_excel(self) -> None:
        try:
            default_start_date, default_end_date = _current_month_range()

            selected_filters = get_check_excel_filter_selection(
                self,
                default_start_date=default_start_date,
                default_end_date=default_end_date,
            )

            if selected_filters is None:
                return

            default_folder = _default_reports_folder()
            default_file_name = (
                f"{_safe_file_name_text('Cek_Listesi_Raporu')}_"
                f"{selected_filters.start_date.strftime('%Y%m%d')}_"
                f"{selected_filters.end_date.strftime('%Y%m%d')}_"
                f"{selected_filters.check_type}_"
                f"{selected_filters.status_group}_"
                f"{selected_filters.currency_code}.xlsx"
            )
            default_file_path = default_folder / default_file_name

            selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "Çek Listesi Excel Dosyasını Kaydet",
                str(default_file_path),
                "Excel Dosyası (*.xlsx)",
            )

            if not selected_file_path:
                return

            output_path = Path(selected_file_path)

            if output_path.suffix.lower() != ".xlsx":
                output_path = output_path.with_suffix(".xlsx")

            created_excel_path = create_check_due_report_excel(
                output_path=output_path,
                report_filter=CheckDueReportFilter(
                    start_date=selected_filters.start_date,
                    end_date=selected_filters.end_date,
                    check_type=selected_filters.check_type,
                    status_group=selected_filters.status_group,
                    currency_code=selected_filters.currency_code,
                ),
                created_by=_created_by_text(self.current_user),
            )

            QMessageBox.information(
                self,
                "Excel Oluşturuldu",
                f"Çek Listesi Excel dosyası başarıyla oluşturuldu:\n\n"
                f"Dönem: {selected_filters.start_date.strftime('%d.%m.%Y')} - "
                f"{selected_filters.end_date.strftime('%d.%m.%Y')}\n"
                f"Çek Türü: {selected_filters.check_type}\n"
                f"Durum: {selected_filters.status_group}\n"
                f"Para Birimi: {selected_filters.currency_code}\n\n"
                f"{created_excel_path}",
            )

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(created_excel_path))
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Excel Oluşturulamadı",
                f"Çek Listesi Excel dosyası oluşturulurken hata oluştu:\n\n{exc}",
            )

    def _create_discount_cost_report_excel(self) -> None:
        try:
            report_type = self._select_discount_cost_report_type()

            if report_type is None:
                return

            if report_type == "PACKAGE":
                self._create_package_based_discount_cost_report_excel()
                return

            if report_type == "CURRENT_MONTH":
                self._create_current_month_discount_cost_report_excel()
                return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Excel Oluşturulamadı",
                f"İskonto Maliyet Excel dosyası oluşturulurken hata oluştu:\n\n{exc}",
            )

    def _create_package_based_discount_cost_report_excel(self) -> None:
        selected_batch_option = self._select_current_month_discount_batch_option()

        if selected_batch_option is None:
            return

        start_date = selected_batch_option.discount_date
        end_date = selected_batch_option.discount_date

        default_folder = _default_reports_folder()
        default_file_name = (
            f"{_safe_file_name_text('Iskonto_Maliyet_Raporu')}_"
            f"Paket_{selected_batch_option.batch_id}_"
            f"{selected_batch_option.discount_date.strftime('%Y%m%d')}.xlsx"
        )
        default_file_path = default_folder / default_file_name

        selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "İskonto Maliyet Excel Dosyasını Kaydet",
            str(default_file_path),
            "Excel Dosyası (*.xlsx)",
        )

        if not selected_file_path:
            return

        output_path = Path(selected_file_path)

        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")

        created_excel_path = create_financing_cost_report_excel(
            output_path=output_path,
            report_filter=FinancingCostReportFilter(
                start_date=start_date,
                end_date=end_date,
                bank_id=None,
                bank_account_id=None,
                discount_batch_id=selected_batch_option.batch_id,
                currency_code="ALL",
            ),
            created_by=_created_by_text(self.current_user),
        )

        QMessageBox.information(
            self,
            "Excel Oluşturuldu",
            f"İskonto Maliyet Excel dosyası başarıyla oluşturuldu:\n\n"
            f"Paket No: {selected_batch_option.batch_id}\n"
            f"{created_excel_path}",
        )

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(created_excel_path))
        )

    def _create_current_month_discount_cost_report_excel(self) -> None:
        start_date, end_date = _current_month_range()

        default_folder = _default_reports_folder()
        default_file_name = (
            f"{_safe_file_name_text('Aylik_Iskonto_Maliyet_Raporu')}_"
            f"{start_date.strftime('%Y%m%d')}_"
            f"{end_date.strftime('%Y%m%d')}.xlsx"
        )
        default_file_path = default_folder / default_file_name

        selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Aylık İskonto Maliyet Excel Dosyasını Kaydet",
            str(default_file_path),
            "Excel Dosyası (*.xlsx)",
        )

        if not selected_file_path:
            return

        output_path = Path(selected_file_path)

        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")

        created_excel_path = create_financing_cost_report_excel(
            output_path=output_path,
            report_filter=FinancingCostReportFilter(
                start_date=start_date,
                end_date=end_date,
                bank_id=None,
                bank_account_id=None,
                discount_batch_id=None,
                currency_code="ALL",
            ),
            created_by=_created_by_text(self.current_user),
        )

        QMessageBox.information(
            self,
            "Excel Oluşturuldu",
            f"Aylık İskonto Maliyet Excel dosyası başarıyla oluşturuldu:\n\n"
            f"Dönem: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
            f"{created_excel_path}",
        )

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(created_excel_path))
        )

    def _create_current_month_discount_cost_report_pdf(self) -> None:
        start_date, end_date = _current_month_range()

        default_folder = _default_reports_folder()
        default_file_name = (
            f"{_safe_file_name_text('Aylik_Iskonto_Maliyet_Raporu')}_"
            f"{start_date.strftime('%Y%m%d')}_"
            f"{end_date.strftime('%Y%m%d')}.pdf"
        )
        default_file_path = default_folder / default_file_name

        selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Aylık İskonto Maliyet Raporunu Kaydet",
            str(default_file_path),
            "PDF Dosyası (*.pdf)",
        )

        if not selected_file_path:
            return

        output_path = Path(selected_file_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        created_pdf_path = create_financing_cost_report_pdf(
            output_path=output_path,
            report_filter=FinancingCostReportFilter(
                start_date=start_date,
                end_date=end_date,
                bank_id=None,
                bank_account_id=None,
                discount_batch_id=None,
                currency_code="ALL",
            ),
            created_by=_created_by_text(self.current_user),
        )

        QMessageBox.information(
            self,
            "Rapor Oluşturuldu",
            f"Aylık İskonto Maliyet Raporu başarıyla oluşturuldu:\n\n"
            f"Dönem: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
            f"{created_pdf_path}",
        )

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(created_pdf_path))
        )

    def _create_package_based_discount_cost_report_pdf(self) -> None:
        selected_batch_option = self._select_current_month_discount_batch_option()

        if selected_batch_option is None:
            return

        start_date = selected_batch_option.discount_date
        end_date = selected_batch_option.discount_date

        default_folder = _default_reports_folder()
        default_file_name = (
            f"{_safe_file_name_text('Iskonto_Maliyet_Raporu')}_"
            f"Paket_{selected_batch_option.batch_id}_"
            f"{selected_batch_option.discount_date.strftime('%Y%m%d')}.pdf"
        )
        default_file_path = default_folder / default_file_name

        selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "İskonto Maliyet Raporunu Kaydet",
            str(default_file_path),
            "PDF Dosyası (*.pdf)",
        )

        if not selected_file_path:
            return

        output_path = Path(selected_file_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        created_pdf_path = create_financing_cost_report_pdf(
            output_path=output_path,
            report_filter=FinancingCostReportFilter(
                start_date=start_date,
                end_date=end_date,
                bank_id=None,
                bank_account_id=None,
                discount_batch_id=selected_batch_option.batch_id,
                currency_code="ALL",
            ),
            created_by=_created_by_text(self.current_user),
        )

        QMessageBox.information(
            self,
            "Rapor Oluşturuldu",
            f"İskonto Maliyet Raporu başarıyla oluşturuldu:\n\n"
            f"Paket No: {selected_batch_option.batch_id}\n"
            f"{created_pdf_path}",
        )

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(created_pdf_path))
        )

    def _select_discount_cost_report_type(self) -> str | None:
        report_types = [
            "Paket Bazlı Rapor",
            "Bu Ayın Toplam Maliyet Raporu",
        ]

        selected_text, is_selected = QInputDialog.getItem(
            self,
            "İskonto Maliyet Raporu",
            "Almak istediğin rapor tipini seç:",
            report_types,
            0,
            False,
        )

        if not is_selected or not selected_text:
            return None

        if selected_text == "Paket Bazlı Rapor":
            return "PACKAGE"

        if selected_text == "Bu Ayın Toplam Maliyet Raporu":
            return "CURRENT_MONTH"

        return None

    def _build_page(self) -> None:
        self.main_layout.addWidget(self._build_info_strip())
        self.main_layout.addWidget(self._build_tabs(), 1)

    def _build_info_strip(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("ReportsInfoStrip")

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("Rapor Merkezi")
        title.setObjectName("ReportTitle")

        body = QLabel(
            "Raporlar sekmeler halinde düzenlendi. Çek, banka ve POS raporları aktif; iskonto ve Excel raporları sırayla eklenecek."
        )
        body.setObjectName("ReportSubTitle")
        body.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(body)

        status = QLabel("Aktif: Çek + Risk + Banka + POS Raporları")
        status.setObjectName("ReportActiveBadge")

        layout.addLayout(title_box, 1)
        layout.addWidget(status, 0, Qt.AlignRight | Qt.AlignVCenter)

        return strip

    def _build_tabs(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setObjectName("ReportsTabs")
        tabs.setDocumentMode(True)

        tabs.addTab(self._build_check_reports_tab(), "Çek Raporları")
        tabs.addTab(self._build_bank_reports_tab(), "Banka Raporları")
        tabs.addTab(self._build_pos_reports_tab(), "POS Raporları")
        tabs.addTab(self._build_discount_reports_tab(), "İskonto Raporları")
        tabs.addTab(self._build_excel_reports_tab(), "Excel Aktarım")

        return tabs

    def _build_check_reports_tab(self) -> QWidget:
        tab = QWidget()

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_quick_check_reports_card())
        layout.addWidget(self._build_custom_check_reports_card())
        layout.addStretch(1)

        return tab

    def _build_bank_reports_tab(self) -> QWidget:
        tab = QWidget()

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_quick_bank_reports_card())
        layout.addWidget(self._build_custom_bank_reports_card())
        layout.addStretch(1)

        return tab

    def _build_pos_reports_tab(self) -> QWidget:
        tab = QWidget()

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_quick_pos_reports_card())
        layout.addWidget(self._build_custom_pos_reports_card())
        layout.addStretch(1)

        return tab

    def _build_discount_reports_tab(self) -> QWidget:
        return build_discount_reports_tab(
            on_discount_batch_report_click=self._create_current_month_discount_batch_report_pdf,
            on_financing_cost_report_click=self._create_current_month_financing_cost_report_pdf,
        )

    def _build_excel_reports_tab(self) -> QWidget:
        return build_excel_reports_tab(
            on_financing_cost_excel_click=self._create_discount_cost_report_excel,
            on_check_due_excel_click=self._create_next_30_days_check_due_report_excel,
        )

    def _build_quick_check_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("QuickReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("Hızlı Çek Raporları")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel(
            "En sık kullanılan çek raporlarını tek tuşla oluştur. Bugün, yarın, haftalık, aylık ve risk raporları doğrudan PDF üretir."
        )
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        grid = QGridLayout()
        grid.setSpacing(12)

        today = date.today()
        tomorrow = today + timedelta(days=1)
        current_month_start, current_month_end = _current_month_range()
        current_year_start, current_year_end = _current_year_range()

        quick_reports = [
            ("Bugünün Çekleri", "Sadece bugün vadeli alınan ve yazılan çekler.", "Bugün Rapor Al", today, today, "Bugunun_Cekleri"),
            ("Yarının Çekleri", "Yarın vadeli alınan ve yazılan çekler.", "Yarın Rapor Al", tomorrow, tomorrow, "Yarinin_Cekleri"),
            ("3 Günlük Çek Raporu", "Bugünden başlayarak 3 günlük vade görünümü.", "3 Günlük Rapor Al", today, today + timedelta(days=3), "3_Gunluk_Cek_Raporu"),
            ("7 Günlük Çek Raporu", "Önümüzdeki 7 gün içindeki çek hareketleri.", "7 Günlük Rapor Al", today, today + timedelta(days=7), "7_Gunluk_Cek_Raporu"),
            ("15 Günlük Çek Raporu", "Yakın vade planlaması için 15 günlük rapor.", "15 Günlük Rapor Al", today, today + timedelta(days=15), "15_Gunluk_Cek_Raporu"),
            ("30 Günlük Çek Raporu", "Aylık nakit akış görünümü için 30 günlük çek raporu.", "30 Günlük Rapor Al", today, today + timedelta(days=30), "30_Gunluk_Cek_Raporu"),
            ("Bu Ayın Çek Raporu", "Ay başından ay sonuna kadar tüm çek hareketleri.", "Bu Ay Rapor Al", current_month_start, current_month_end, "Bu_Ayin_Cek_Raporu"),
            ("Bu Yılın Çek Raporu", "Yıl içindeki alınan ve yazılan tüm çekler.", "Bu Yıl Rapor Al", current_year_start, current_year_end, "Bu_Yilin_Cek_Raporu"),
        ]

        for index, report in enumerate(quick_reports):
            grid.addWidget(
                self._build_quick_due_report_box(
                    title_text=report[0],
                    body_text=report[1],
                    button_text=report[2],
                    start_date=report[3],
                    end_date=report[4],
                    file_label=report[5],
                ),
                index // 3,
                index % 3,
            )

        grid.addWidget(
            self._build_quick_risk_report_box(
                title_text="Riskli / Problemli Çekler",
                body_text="Problemli, riskli ve vadesi geçmiş bekleyen çekler.",
                button_text="Risk Raporu Al",
                start_date=current_year_start,
                end_date=current_year_end,
                file_label="Riskli_Problemli_Cekler",
            ),
            2,
            2,
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(grid)

        return card

    def _select_current_month_discount_batch_option(self):
        start_date, end_date = _current_month_range()

        options = list_discount_batch_options(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            currency_code="ALL",
        )

        if not options:
            QMessageBox.information(
                self,
                "İskonto Paketi Bulunamadı",
                "Bu ay için kayıtlı iskonto paketi bulunamadı.\n\n"
                "Finansman Maliyeti Raporu alabilmek için önce iskonto paketi oluşturulmuş olmalı.",
            )
            return None

        option_texts = [
            option.display_text
            for option in options
        ]

        selected_text, is_selected = QInputDialog.getItem(
            self,
            "İskonto Paketi Seç",
            "Finansman maliyeti raporu almak istediğin iskonto paketini seç:",
            option_texts,
            0,
            False,
        )

        if not is_selected or not selected_text:
            return None

        for option in options:
            if option.display_text == selected_text:
                return option

        QMessageBox.warning(
            self,
            "Paket Seçilemedi",
            "Seçilen iskonto paketi bulunamadı. Lütfen tekrar deneyin.",
        )
        return None

    def _build_quick_bank_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("QuickReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("Hızlı Banka Raporları")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel(
            "Banka hareketlerini tek tuşla raporla. Giriş, çıkış, planlanan, gerçekleşen ve POS kaynaklı hareketleri ayrı ayrı alabilirsin."
        )
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        grid = QGridLayout()
        grid.setSpacing(12)

        today = date.today()
        current_month_start, current_month_end = _current_month_range()
        current_year_start, current_year_end = _current_year_range()

        quick_reports = [
            ("Bugünkü Banka Hareketleri", "Bugün yapılan banka giriş, çıkış ve transferleri.", "Bugün Rapor Al", today, today, "Bugunku_Banka_Hareketleri", "ALL", "ALL", "ALL", "ALL"),
            ("Bu Ay Banka Hareketleri", "Ay içindeki tüm banka hareketleri.", "Bu Ay Rapor Al", current_month_start, current_month_end, "Bu_Ay_Banka_Hareketleri", "ALL", "ALL", "ALL", "ALL"),
            ("Bu Yıl Banka Hareketleri", "Yıl içindeki tüm banka hareketleri.", "Bu Yıl Rapor Al", current_year_start, current_year_end, "Bu_Yil_Banka_Hareketleri", "ALL", "ALL", "ALL", "ALL"),
            ("Bu Ay Banka Girişleri", "Sadece banka hesabına giren tutarlar.", "Giriş Raporu Al", current_month_start, current_month_end, "Bu_Ay_Banka_Girisleri", "IN", "ALL", "ALL", "ALL"),
            ("Bu Ay Banka Çıkışları", "Sadece banka hesabından çıkan tutarlar.", "Çıkış Raporu Al", current_month_start, current_month_end, "Bu_Ay_Banka_Cikislari", "OUT", "ALL", "ALL", "ALL"),
            ("Gerçekleşen Banka Hareketleri", "Bu ay gerçekleşmiş banka hareketleri.", "Gerçekleşen Rapor Al", current_month_start, current_month_end, "Gerceklesen_Banka_Hareketleri", "ALL", "REALIZED", "ALL", "ALL"),
            ("Planlanan Banka Hareketleri", "Bu ay planlanan banka hareketleri.", "Planlanan Rapor Al", current_month_start, current_month_end, "Planlanan_Banka_Hareketleri", "ALL", "PLANNED", "ALL", "ALL"),
            ("POS Kaynaklı Banka Hareketleri", "POS yatışı kaynaklı banka hareketleri.", "POS Banka Raporu Al", current_month_start, current_month_end, "POS_Kaynakli_Banka_Hareketleri", "ALL", "ALL", "ALL", "POS_SETTLEMENT"),
        ]

        for index, report in enumerate(quick_reports):
            grid.addWidget(
                self._build_quick_bank_report_box(
                    title_text=report[0],
                    body_text=report[1],
                    button_text=report[2],
                    start_date=report[3],
                    end_date=report[4],
                    file_label=report[5],
                    direction=report[6],
                    status=report[7],
                    currency_code=report[8],
                    source_type=report[9],
                ),
                index // 3,
                index % 3,
            )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(grid)

        return card

    def _build_quick_pos_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("QuickReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("Hızlı POS Raporları")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel(
            "POS mutabakatlarını tek tuşla raporla. Bekleyen, gerçekleşen, fark oluşan ve iptal edilen POS kayıtlarını ayrı ayrı alabilirsin."
        )
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        grid = QGridLayout()
        grid.setSpacing(12)

        today = date.today()
        current_month_start, current_month_end = _current_month_range()
        current_year_start, current_year_end = _current_year_range()

        quick_reports = [
            ("Bugünkü POS Raporu", "Bugünkü POS satış ve yatış beklentileri.", "Bugün POS Rapor Al", today, today, "Bugunku_POS_Raporu", "ALL", "ALL"),
            ("Bu Ay POS Raporu", "Ay içindeki tüm POS mutabakat kayıtları.", "Bu Ay POS Rapor Al", current_month_start, current_month_end, "Bu_Ay_POS_Raporu", "ALL", "ALL"),
            ("Bu Yıl POS Raporu", "Yıl içindeki tüm POS mutabakat kayıtları.", "Bu Yıl POS Rapor Al", current_year_start, current_year_end, "Bu_Yil_POS_Raporu", "ALL", "ALL"),
            ("Bekleyen POS Yatışları", "Henüz gerçekleşmemiş POS yatış kayıtları.", "Bekleyen POS Rapor Al", current_month_start, current_month_end, "Bekleyen_POS_Yatislari", "PLANNED", "ALL"),
            ("Gerçekleşen POS Yatışları", "Bankaya gerçekleşmiş POS yatış kayıtları.", "Gerçekleşen POS Rapor Al", current_month_start, current_month_end, "Gerceklesen_POS_Yatislari", "REALIZED", "ALL"),
            ("Farklı POS Mutabakatı", "Beklenen ve gerçekleşen tutar arasında fark olan POS kayıtları.", "Fark POS Rapor Al", current_month_start, current_month_end, "Farkli_POS_Mutabakati", "MISMATCH", "ALL"),
            ("İptal POS Kayıtları", "İptal edilmiş POS mutabakat kayıtları.", "İptal POS Rapor Al", current_month_start, current_month_end, "Iptal_POS_Kayitlari", "CANCELLED", "ALL"),
            ("TRY POS Raporu", "Sadece TRY para birimindeki POS kayıtları.", "TRY POS Rapor Al", current_month_start, current_month_end, "TRY_POS_Raporu", "ALL", "TRY"),
        ]

        for index, report in enumerate(quick_reports):
            grid.addWidget(
                self._build_quick_pos_report_box(
                    title_text=report[0],
                    body_text=report[1],
                    button_text=report[2],
                    start_date=report[3],
                    end_date=report[4],
                    file_label=report[5],
                    status=report[6],
                    currency_code=report[7],
                ),
                index // 3,
                index % 3,
            )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(grid)

        return card

    def _build_quick_due_report_box(self, *, title_text: str, body_text: str, button_text: str, start_date: date, end_date: date, file_label: str) -> QWidget:
        return self._build_report_box(
            title_text=title_text,
            body_text=body_text,
            button_text=button_text,
            start_date=start_date,
            end_date=end_date,
            button_object_name="QuickReportButton",
            callback=lambda: self._create_quick_due_report_pdf(start_date=start_date, end_date=end_date, file_label=file_label),
        )

    def _build_quick_bank_report_box(self, *, title_text: str, body_text: str, button_text: str, start_date: date, end_date: date, file_label: str, direction: str, status: str, currency_code: str, source_type: str) -> QWidget:
        return self._build_report_box(
            title_text=title_text,
            body_text=body_text,
            button_text=button_text,
            start_date=start_date,
            end_date=end_date,
            button_object_name="BankReportButton",
            callback=lambda: self._create_quick_bank_report_pdf(
                start_date=start_date,
                end_date=end_date,
                file_label=file_label,
                direction=direction,
                status=status,
                currency_code=currency_code,
                source_type=source_type,
            ),
        )

    def _create_current_month_discount_batch_report_pdf(self) -> None:
        try:
            start_date, end_date = _current_month_range()

            default_folder = _default_reports_folder()
            default_file_name = (
                f"{_safe_file_name_text('Iskonto_Paketleri_Raporu')}_"
                f"{start_date.strftime('%Y%m%d')}_"
                f"{end_date.strftime('%Y%m%d')}.pdf"
            )
            default_file_path = default_folder / default_file_name

            selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "İskonto Paketleri Raporunu Kaydet",
                str(default_file_path),
                "PDF Dosyası (*.pdf)",
            )

            if not selected_file_path:
                return

            output_path = Path(selected_file_path)

            if output_path.suffix.lower() != ".pdf":
                output_path = output_path.with_suffix(".pdf")

            created_pdf_path = create_discount_batch_report_pdf(
                output_path=output_path,
                report_filter=DiscountBatchReportFilter(
                    start_date=start_date,
                    end_date=end_date,
                    bank_id=None,
                    bank_account_id=None,
                    currency_code="ALL",
                ),
                created_by=_created_by_text(self.current_user),
            )

            QMessageBox.information(
                self,
                "Rapor Oluşturuldu",
                f"İskonto Paketleri Raporu başarıyla oluşturuldu:\n\n{created_pdf_path}",
            )

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(created_pdf_path))
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Rapor Oluşturulamadı",
                f"İskonto Paketleri Raporu oluşturulurken hata oluştu:\n\n{exc}",
            )

    def _create_current_month_financing_cost_report_pdf(self) -> None:
        try:
            report_type = self._select_discount_cost_report_type()

            if report_type is None:
                return

            if report_type == "PACKAGE":
                self._create_package_based_discount_cost_report_pdf()
                return

            if report_type == "CURRENT_MONTH":
                self._create_current_month_discount_cost_report_pdf()
                return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Rapor Oluşturulamadı",
                f"İskonto Maliyet Raporu oluşturulurken hata oluştu:\n\n{exc}",
            )

    def _build_quick_pos_report_box(self, *, title_text: str, body_text: str, button_text: str, start_date: date, end_date: date, file_label: str, status: str, currency_code: str) -> QWidget:
        return self._build_report_box(
            title_text=title_text,
            body_text=body_text,
            button_text=button_text,
            start_date=start_date,
            end_date=end_date,
            button_object_name="PosReportButton",
            callback=lambda: self._create_quick_pos_report_pdf(
                start_date=start_date,
                end_date=end_date,
                file_label=file_label,
                status=status,
                currency_code=currency_code,
            ),
        )

    def _build_quick_risk_report_box(self, *, title_text: str, body_text: str, button_text: str, start_date: date, end_date: date, file_label: str) -> QWidget:
        box = QFrame()
        box.setObjectName("RiskQuickReportBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("QuickReportTitle")
        title.setWordWrap(True)

        body = QLabel(body_text)
        body.setObjectName("QuickReportBody")
        body.setWordWrap(True)

        period = QLabel(f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
        period.setObjectName("ReportSmallInfo")

        button = QPushButton(button_text)
        button.setObjectName("RiskReportButton")
        button.setMinimumHeight(38)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda checked=False: self._create_quick_risk_report_pdf(
                start_date=start_date,
                end_date=end_date,
                file_label=file_label,
            )
        )

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(period)
        layout.addStretch(1)
        layout.addWidget(button)

        return box

    def _build_report_box(self, *, title_text: str, body_text: str, button_text: str, start_date: date, end_date: date, button_object_name: str, callback) -> QWidget:
        box = QFrame()
        box.setObjectName("QuickReportBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("QuickReportTitle")
        title.setWordWrap(True)

        body = QLabel(body_text)
        body.setObjectName("QuickReportBody")
        body.setWordWrap(True)

        period = QLabel(f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
        period.setObjectName("ReportSmallInfo")

        button = QPushButton(button_text)
        button.setObjectName(button_object_name)
        button.setMinimumHeight(38)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda checked=False: callback())

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(period)
        layout.addStretch(1)
        layout.addWidget(button)

        return box

    def _build_custom_check_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CustomReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("Özel Tarih Aralıklı Çek Raporu")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel("Hazır butonlar yetmediğinde tarih aralığını, çek türünü, durumunu ve para birimini kendin seç.")
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.custom_due_pdf_button = QPushButton("Özel PDF Oluştur")
        self.custom_due_pdf_button.setObjectName("CustomReportButton")
        self.custom_due_pdf_button.setMinimumHeight(42)
        self.custom_due_pdf_button.setMinimumWidth(170)
        self.custom_due_pdf_button.clicked.connect(self._create_custom_due_pdf)

        header_row.addLayout(title_box, 1)
        header_row.addWidget(self.custom_due_pdf_button, 0, Qt.AlignTop)

        layout.addLayout(header_row)
        layout.addWidget(self._build_custom_due_filter_panel())

        return card

    def _build_custom_bank_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CustomReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("Özel Tarih Aralıklı Banka Hareket Raporu")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel("Tarih aralığına, giriş/çıkış yönüne, işlem durumuna, para birimine ve kaynak türüne göre banka hareket raporu oluştur.")
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.custom_bank_pdf_button = QPushButton("Banka PDF Oluştur")
        self.custom_bank_pdf_button.setObjectName("CustomBankReportButton")
        self.custom_bank_pdf_button.setMinimumHeight(42)
        self.custom_bank_pdf_button.setMinimumWidth(180)
        self.custom_bank_pdf_button.clicked.connect(self._create_custom_bank_pdf)

        header_row.addLayout(title_box, 1)
        header_row.addWidget(self.custom_bank_pdf_button, 0, Qt.AlignTop)

        layout.addLayout(header_row)
        layout.addWidget(self._build_custom_bank_filter_panel())

        return card

    def _build_custom_pos_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CustomReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("Özel Tarih Aralıklı POS Mutabakat Raporu")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel("Tarih aralığına, POS durumuna ve para birimine göre POS mutabakat raporu oluştur.")
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.custom_pos_pdf_button = QPushButton("POS PDF Oluştur")
        self.custom_pos_pdf_button.setObjectName("CustomPosReportButton")
        self.custom_pos_pdf_button.setMinimumHeight(42)
        self.custom_pos_pdf_button.setMinimumWidth(170)
        self.custom_pos_pdf_button.clicked.connect(self._create_custom_pos_pdf)

        header_row.addLayout(title_box, 1)
        header_row.addWidget(self.custom_pos_pdf_button, 0, Qt.AlignTop)

        layout.addLayout(header_row)
        layout.addWidget(self._build_custom_pos_filter_panel())

        return card

    def _build_custom_due_filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ReportFilterPanel")

        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)

        today = QDate.currentDate()

        self.custom_start_date_edit = QDateEdit()
        self.custom_start_date_edit.setMinimumHeight(38)
        self.custom_start_date_edit.setCalendarPopup(True)
        self.custom_start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.custom_start_date_edit.setDate(today)

        self.custom_end_date_edit = QDateEdit()
        self.custom_end_date_edit.setMinimumHeight(38)
        self.custom_end_date_edit.setCalendarPopup(True)
        self.custom_end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.custom_end_date_edit.setDate(today.addDays(30))

        self.custom_check_type_combo = QComboBox()
        self.custom_check_type_combo.setMinimumHeight(38)
        self.custom_check_type_combo.addItem("Tümü", "ALL")
        self.custom_check_type_combo.addItem("Sadece Alınan Çekler", "RECEIVED")
        self.custom_check_type_combo.addItem("Sadece Yazılan Çekler", "ISSUED")

        self.custom_status_group_combo = QComboBox()
        self.custom_status_group_combo.setMinimumHeight(38)
        self.custom_status_group_combo.addItem("Tümü", "ALL")
        self.custom_status_group_combo.addItem("Bekleyen", "PENDING")
        self.custom_status_group_combo.addItem("Sonuçlanan", "CLOSED")
        self.custom_status_group_combo.addItem("Problemli", "PROBLEM")

        self.custom_currency_combo = QComboBox()
        self.custom_currency_combo.setMinimumHeight(38)
        self.custom_currency_combo.addItem("Tümü", "ALL")
        self.custom_currency_combo.addItem("TRY", "TRY")
        self.custom_currency_combo.addItem("USD", "USD")
        self.custom_currency_combo.addItem("EUR", "EUR")
        self.custom_currency_combo.addItem("GBP", "GBP")

        quick_date_row = QHBoxLayout()
        quick_date_row.setSpacing(8)

        today_button = self._build_quick_button("Bugün")
        today_button.clicked.connect(self._set_custom_today)

        tomorrow_button = self._build_quick_button("Yarın")
        tomorrow_button.clicked.connect(self._set_custom_tomorrow)

        next_7_button = self._build_quick_button("7 Gün")
        next_7_button.clicked.connect(self._set_custom_next_7_days)

        next_30_button = self._build_quick_button("30 Gün")
        next_30_button.clicked.connect(self._set_custom_next_30_days)

        current_month_button = self._build_quick_button("Bu Ay")
        current_month_button.clicked.connect(self._set_custom_current_month)

        current_year_button = self._build_quick_button("Bu Yıl")
        current_year_button.clicked.connect(self._set_custom_current_year)

        quick_date_row.addWidget(today_button)
        quick_date_row.addWidget(tomorrow_button)
        quick_date_row.addWidget(next_7_button)
        quick_date_row.addWidget(next_30_button)
        quick_date_row.addWidget(current_month_button)
        quick_date_row.addWidget(current_year_button)
        quick_date_row.addStretch(1)

        layout.addWidget(self._build_field_label("Başlangıç Tarihi"), 0, 0)
        layout.addWidget(self.custom_start_date_edit, 1, 0)

        layout.addWidget(self._build_field_label("Bitiş Tarihi"), 0, 1)
        layout.addWidget(self.custom_end_date_edit, 1, 1)

        layout.addWidget(self._build_field_label("Çek Türü"), 0, 2)
        layout.addWidget(self.custom_check_type_combo, 1, 2)

        layout.addWidget(self._build_field_label("Durum"), 2, 0)
        layout.addWidget(self.custom_status_group_combo, 3, 0)

        layout.addWidget(self._build_field_label("Para Birimi"), 2, 1)
        layout.addWidget(self.custom_currency_combo, 3, 1)

        layout.addWidget(self._build_field_label("Hızlı Tarih"), 2, 2)
        layout.addLayout(quick_date_row, 3, 2)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 2)

        return panel

    def _build_custom_bank_filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ReportFilterPanel")

        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)

        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)

        if today.month() == 12:
            last_day = QDate(today.year(), 12, 31)
        else:
            last_day = QDate(today.year(), today.month() + 1, 1).addDays(-1)

        self.bank_start_date_edit = QDateEdit()
        self.bank_start_date_edit.setMinimumHeight(38)
        self.bank_start_date_edit.setCalendarPopup(True)
        self.bank_start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.bank_start_date_edit.setDate(first_day)

        self.bank_end_date_edit = QDateEdit()
        self.bank_end_date_edit.setMinimumHeight(38)
        self.bank_end_date_edit.setCalendarPopup(True)
        self.bank_end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.bank_end_date_edit.setDate(last_day)

        self.bank_direction_combo = QComboBox()
        self.bank_direction_combo.setMinimumHeight(38)
        self.bank_direction_combo.addItem("Tümü", "ALL")
        self.bank_direction_combo.addItem("Sadece Girişler", "IN")
        self.bank_direction_combo.addItem("Sadece Çıkışlar", "OUT")

        self.bank_status_combo = QComboBox()
        self.bank_status_combo.setMinimumHeight(38)
        self.bank_status_combo.addItem("Tümü", "ALL")
        self.bank_status_combo.addItem("Gerçekleşen", "REALIZED")
        self.bank_status_combo.addItem("Planlanan", "PLANNED")
        self.bank_status_combo.addItem("İptal Edilen", "CANCELLED")

        self.bank_currency_combo = QComboBox()
        self.bank_currency_combo.setMinimumHeight(38)
        self.bank_currency_combo.addItem("Tümü", "ALL")
        self.bank_currency_combo.addItem("TRY", "TRY")
        self.bank_currency_combo.addItem("USD", "USD")
        self.bank_currency_combo.addItem("EUR", "EUR")
        self.bank_currency_combo.addItem("GBP", "GBP")

        self.bank_source_type_combo = QComboBox()
        self.bank_source_type_combo.setMinimumHeight(38)
        self.bank_source_type_combo.addItem("Tümü", "ALL")
        self.bank_source_type_combo.addItem("Açılış Bakiyesi", "OPENING_BALANCE")
        self.bank_source_type_combo.addItem("Nakit Yatırma", "CASH_DEPOSIT")
        self.bank_source_type_combo.addItem("Banka Transferi", "BANK_TRANSFER")
        self.bank_source_type_combo.addItem("Yazılan Çek", "ISSUED_CHECK")
        self.bank_source_type_combo.addItem("Alınan Çek", "RECEIVED_CHECK")
        self.bank_source_type_combo.addItem("POS Yatışı", "POS_SETTLEMENT")
        self.bank_source_type_combo.addItem("Manuel Düzeltme", "MANUAL_ADJUSTMENT")
        self.bank_source_type_combo.addItem("Diğer", "OTHER")

        quick_date_row = QHBoxLayout()
        quick_date_row.setSpacing(8)

        today_button = self._build_quick_button("Bugün")
        today_button.clicked.connect(self._set_bank_today)

        current_month_button = self._build_quick_button("Bu Ay")
        current_month_button.clicked.connect(self._set_bank_current_month)

        current_year_button = self._build_quick_button("Bu Yıl")
        current_year_button.clicked.connect(self._set_bank_current_year)

        quick_date_row.addWidget(today_button)
        quick_date_row.addWidget(current_month_button)
        quick_date_row.addWidget(current_year_button)
        quick_date_row.addStretch(1)

        layout.addWidget(self._build_field_label("Başlangıç Tarihi"), 0, 0)
        layout.addWidget(self.bank_start_date_edit, 1, 0)

        layout.addWidget(self._build_field_label("Bitiş Tarihi"), 0, 1)
        layout.addWidget(self.bank_end_date_edit, 1, 1)

        layout.addWidget(self._build_field_label("Yön"), 0, 2)
        layout.addWidget(self.bank_direction_combo, 1, 2)

        layout.addWidget(self._build_field_label("Durum"), 2, 0)
        layout.addWidget(self.bank_status_combo, 3, 0)

        layout.addWidget(self._build_field_label("Para Birimi"), 2, 1)
        layout.addWidget(self.bank_currency_combo, 3, 1)

        layout.addWidget(self._build_field_label("Kaynak Türü"), 2, 2)
        layout.addWidget(self.bank_source_type_combo, 3, 2)

        layout.addWidget(self._build_field_label("Hızlı Tarih"), 4, 0)
        layout.addLayout(quick_date_row, 5, 0, 1, 3)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        return panel

    def _build_custom_pos_filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ReportFilterPanel")

        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)

        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)

        if today.month() == 12:
            last_day = QDate(today.year(), 12, 31)
        else:
            last_day = QDate(today.year(), today.month() + 1, 1).addDays(-1)

        self.pos_start_date_edit = QDateEdit()
        self.pos_start_date_edit.setMinimumHeight(38)
        self.pos_start_date_edit.setCalendarPopup(True)
        self.pos_start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.pos_start_date_edit.setDate(first_day)

        self.pos_end_date_edit = QDateEdit()
        self.pos_end_date_edit.setMinimumHeight(38)
        self.pos_end_date_edit.setCalendarPopup(True)
        self.pos_end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.pos_end_date_edit.setDate(last_day)

        self.pos_status_combo = QComboBox()
        self.pos_status_combo.setMinimumHeight(38)
        self.pos_status_combo.addItem("Tümü", "ALL")
        self.pos_status_combo.addItem("Planlanan", "PLANNED")
        self.pos_status_combo.addItem("Gerçekleşen", "REALIZED")
        self.pos_status_combo.addItem("Fark Var", "MISMATCH")
        self.pos_status_combo.addItem("İptal Edilen", "CANCELLED")

        self.pos_currency_combo = QComboBox()
        self.pos_currency_combo.setMinimumHeight(38)
        self.pos_currency_combo.addItem("Tümü", "ALL")
        self.pos_currency_combo.addItem("TRY", "TRY")
        self.pos_currency_combo.addItem("USD", "USD")
        self.pos_currency_combo.addItem("EUR", "EUR")
        self.pos_currency_combo.addItem("GBP", "GBP")

        quick_date_row = QHBoxLayout()
        quick_date_row.setSpacing(8)

        today_button = self._build_quick_button("Bugün")
        today_button.clicked.connect(self._set_pos_today)

        current_month_button = self._build_quick_button("Bu Ay")
        current_month_button.clicked.connect(self._set_pos_current_month)

        current_year_button = self._build_quick_button("Bu Yıl")
        current_year_button.clicked.connect(self._set_pos_current_year)

        quick_date_row.addWidget(today_button)
        quick_date_row.addWidget(current_month_button)
        quick_date_row.addWidget(current_year_button)
        quick_date_row.addStretch(1)

        layout.addWidget(self._build_field_label("Başlangıç Tarihi"), 0, 0)
        layout.addWidget(self.pos_start_date_edit, 1, 0)

        layout.addWidget(self._build_field_label("Bitiş Tarihi"), 0, 1)
        layout.addWidget(self.pos_end_date_edit, 1, 1)

        layout.addWidget(self._build_field_label("Durum"), 0, 2)
        layout.addWidget(self.pos_status_combo, 1, 2)

        layout.addWidget(self._build_field_label("Para Birimi"), 2, 0)
        layout.addWidget(self.pos_currency_combo, 3, 0)

        layout.addWidget(self._build_field_label("Hızlı Tarih"), 2, 1)
        layout.addLayout(quick_date_row, 3, 1, 1, 2)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        return panel

    def _build_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ReportFieldLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        return label

    def _build_quick_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("ReportQuickButton")
        button.setMinimumHeight(36)
        button.setCursor(Qt.PointingHandCursor)

        return button

    def _set_custom_today(self) -> None:
        today = QDate.currentDate()
        self.custom_start_date_edit.setDate(today)
        self.custom_end_date_edit.setDate(today)

    def _set_custom_tomorrow(self) -> None:
        tomorrow = QDate.currentDate().addDays(1)
        self.custom_start_date_edit.setDate(tomorrow)
        self.custom_end_date_edit.setDate(tomorrow)

    def _set_custom_next_7_days(self) -> None:
        today = QDate.currentDate()
        self.custom_start_date_edit.setDate(today)
        self.custom_end_date_edit.setDate(today.addDays(7))

    def _set_custom_next_30_days(self) -> None:
        today = QDate.currentDate()
        self.custom_start_date_edit.setDate(today)
        self.custom_end_date_edit.setDate(today.addDays(30))

    def _set_custom_current_month(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        last_day = first_day.addMonths(1).addDays(-1)
        self.custom_start_date_edit.setDate(first_day)
        self.custom_end_date_edit.setDate(last_day)

    def _set_custom_current_year(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), 1, 1)
        last_day = QDate(today.year(), 12, 31)
        self.custom_start_date_edit.setDate(first_day)
        self.custom_end_date_edit.setDate(last_day)

    def _set_bank_today(self) -> None:
        today = QDate.currentDate()
        self.bank_start_date_edit.setDate(today)
        self.bank_end_date_edit.setDate(today)

    def _set_bank_current_month(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        last_day = first_day.addMonths(1).addDays(-1)
        self.bank_start_date_edit.setDate(first_day)
        self.bank_end_date_edit.setDate(last_day)

    def _set_bank_current_year(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), 1, 1)
        last_day = QDate(today.year(), 12, 31)
        self.bank_start_date_edit.setDate(first_day)
        self.bank_end_date_edit.setDate(last_day)

    def _set_pos_today(self) -> None:
        today = QDate.currentDate()
        self.pos_start_date_edit.setDate(today)
        self.pos_end_date_edit.setDate(today)

    def _set_pos_current_month(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        last_day = first_day.addMonths(1).addDays(-1)
        self.pos_start_date_edit.setDate(first_day)
        self.pos_end_date_edit.setDate(last_day)

    def _set_pos_current_year(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), 1, 1)
        last_day = QDate(today.year(), 12, 31)
        self.pos_start_date_edit.setDate(first_day)
        self.pos_end_date_edit.setDate(last_day)

    def _build_custom_due_report_filter(self) -> CheckDueReportFilter:
        start_date = _qdate_to_date(self.custom_start_date_edit.date())
        end_date = _qdate_to_date(self.custom_end_date_edit.date())

        if end_date < start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

        return CheckDueReportFilter(
            start_date=start_date,
            end_date=end_date,
            check_type=str(self.custom_check_type_combo.currentData() or "ALL"),
            status_group=str(self.custom_status_group_combo.currentData() or "ALL"),
            currency_code=str(self.custom_currency_combo.currentData() or "ALL"),
        )

    def _build_custom_bank_report_filter(self) -> BankMovementReportFilter:
        start_date = _qdate_to_date(self.bank_start_date_edit.date())
        end_date = _qdate_to_date(self.bank_end_date_edit.date())

        if end_date < start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

        return BankMovementReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            direction=str(self.bank_direction_combo.currentData() or "ALL"),
            status=str(self.bank_status_combo.currentData() or "ALL"),
            currency_code=str(self.bank_currency_combo.currentData() or "ALL"),
            source_type=str(self.bank_source_type_combo.currentData() or "ALL"),
        )

    def _build_custom_pos_report_filter(self) -> PosSettlementReportFilter:
        start_date = _qdate_to_date(self.pos_start_date_edit.date())
        end_date = _qdate_to_date(self.pos_end_date_edit.date())

        if end_date < start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

        return PosSettlementReportFilter(
            start_date=start_date,
            end_date=end_date,
            pos_device_id=None,
            bank_id=None,
            bank_account_id=None,
            status=str(self.pos_status_combo.currentData() or "ALL"),
            currency_code=str(self.pos_currency_combo.currentData() or "ALL"),
        )

    def _suggested_pdf_path(self, *, file_label: str, start_date: date, end_date: date) -> str:
        reports_folder = _default_reports_folder()
        reports_folder.mkdir(parents=True, exist_ok=True)

        start_text = start_date.strftime("%Y-%m-%d")
        end_text = end_date.strftime("%Y-%m-%d")

        file_name = _safe_file_name_text(
            f"FTM_{file_label}_{start_text}_{end_text}.pdf"
        )

        return str(reports_folder / file_name)

    def _create_quick_due_report_pdf(self, *, start_date: date, end_date: date, file_label: str) -> None:
        report_filter = CheckDueReportFilter(
            start_date=start_date,
            end_date=end_date,
            check_type="ALL",
            status_group="ALL",
            currency_code="ALL",
        )

        self._create_due_pdf_with_filter(
            report_filter=report_filter,
            file_label=file_label,
            dialog_title="Çek Raporu PDF Kaydet",
            success_message="Çek raporu başarıyla oluşturuldu.",
        )

    def _create_quick_bank_report_pdf(self, *, start_date: date, end_date: date, file_label: str, direction: str, status: str, currency_code: str, source_type: str) -> None:
        report_filter = BankMovementReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            direction=direction,
            status=status,
            currency_code=currency_code,
            source_type=source_type,
        )

        self._create_bank_pdf_with_filter(
            report_filter=report_filter,
            file_label=file_label,
            dialog_title="Banka Hareket Raporu PDF Kaydet",
            success_message="Banka hareket raporu başarıyla oluşturuldu.",
        )

    def _create_quick_pos_report_pdf(self, *, start_date: date, end_date: date, file_label: str, status: str, currency_code: str) -> None:
        report_filter = PosSettlementReportFilter(
            start_date=start_date,
            end_date=end_date,
            pos_device_id=None,
            bank_id=None,
            bank_account_id=None,
            status=status,
            currency_code=currency_code,
        )

        self._create_pos_pdf_with_filter(
            report_filter=report_filter,
            file_label=file_label,
            dialog_title="POS Mutabakat Raporu PDF Kaydet",
            success_message="POS mutabakat raporu başarıyla oluşturuldu.",
        )

    def _create_quick_risk_report_pdf(self, *, start_date: date, end_date: date, file_label: str) -> None:
        report_filter = RiskCheckReportFilter(
            start_date=start_date,
            end_date=end_date,
            check_type="ALL",
            risk_type="ALL",
            currency_code="ALL",
        )

        self._create_risk_pdf_with_filter(
            report_filter=report_filter,
            file_label=file_label,
            dialog_title="Riskli / Problemli Çek Raporu PDF Kaydet",
            success_message="Riskli / Problemli Çek Raporu başarıyla oluşturuldu.",
        )

    def _create_custom_due_pdf(self) -> None:
        try:
            report_filter = self._build_custom_due_report_filter()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        check_type = str(report_filter.check_type or "ALL").upper()

        if check_type == "RECEIVED":
            file_label = "Tarih_Aralikli_Alinan_Cek_Raporu"
        elif check_type == "ISSUED":
            file_label = "Tarih_Aralikli_Yazilan_Cek_Raporu"
        else:
            file_label = "Tarih_Aralikli_Cek_Raporu"

        self._create_due_pdf_with_filter(
            report_filter=report_filter,
            file_label=file_label,
            dialog_title="Tarih Aralıklı Çek Raporu PDF Kaydet",
            success_message="Tarih aralıklı çek raporu başarıyla oluşturuldu.",
        )

    def _create_custom_bank_pdf(self) -> None:
        try:
            report_filter = self._build_custom_bank_report_filter()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        self._create_bank_pdf_with_filter(
            report_filter=report_filter,
            file_label="Tarih_Aralikli_Banka_Hareket_Raporu",
            dialog_title="Tarih Aralıklı Banka Hareket Raporu PDF Kaydet",
            success_message="Tarih aralıklı banka hareket raporu başarıyla oluşturuldu.",
        )

    def _create_custom_pos_pdf(self) -> None:
        try:
            report_filter = self._build_custom_pos_report_filter()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        self._create_pos_pdf_with_filter(
            report_filter=report_filter,
            file_label="Tarih_Aralikli_POS_Mutabakat_Raporu",
            dialog_title="Tarih Aralıklı POS Mutabakat Raporu PDF Kaydet",
            success_message="Tarih aralıklı POS mutabakat raporu başarıyla oluşturuldu.",
        )

    def _create_due_pdf_with_filter(self, *, report_filter: CheckDueReportFilter, file_label: str, dialog_title: str, success_message: str) -> None:
        suggested_path = self._suggested_pdf_path(
            file_label=file_label,
            start_date=report_filter.start_date,
            end_date=report_filter.end_date,
        )

        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            suggested_path,
            "PDF Dosyası (*.pdf)",
        )

        if not selected_path:
            return

        output_path = Path(selected_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        try:
            created_path = create_check_due_report_pdf(
                output_path=output_path,
                report_filter=report_filter,
                created_by=_created_by_text(self.current_user),
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF oluşturulamadı", f"Rapor oluşturulurken hata oluştu:\n\n{exc}")
            return

        self._ask_open_created_pdf(title="PDF oluşturuldu", message=success_message, created_path=created_path)

    def _create_bank_pdf_with_filter(self, *, report_filter: BankMovementReportFilter, file_label: str, dialog_title: str, success_message: str) -> None:
        suggested_path = self._suggested_pdf_path(
            file_label=file_label,
            start_date=report_filter.start_date,
            end_date=report_filter.end_date,
        )

        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            suggested_path,
            "PDF Dosyası (*.pdf)",
        )

        if not selected_path:
            return

        output_path = Path(selected_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        try:
            created_path = create_bank_movement_report_pdf(
                output_path=output_path,
                report_filter=report_filter,
                created_by=_created_by_text(self.current_user),
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF oluşturulamadı", f"Banka hareket raporu oluşturulurken hata oluştu:\n\n{exc}")
            return

        self._ask_open_created_pdf(title="PDF oluşturuldu", message=success_message, created_path=created_path)

    def _create_pos_pdf_with_filter(self, *, report_filter: PosSettlementReportFilter, file_label: str, dialog_title: str, success_message: str) -> None:
        suggested_path = self._suggested_pdf_path(
            file_label=file_label,
            start_date=report_filter.start_date,
            end_date=report_filter.end_date,
        )

        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            suggested_path,
            "PDF Dosyası (*.pdf)",
        )

        if not selected_path:
            return

        output_path = Path(selected_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        try:
            created_path = create_pos_settlement_report_pdf(
                output_path=output_path,
                report_filter=report_filter,
                created_by=_created_by_text(self.current_user),
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF oluşturulamadı", f"POS mutabakat raporu oluşturulurken hata oluştu:\n\n{exc}")
            return

        self._ask_open_created_pdf(title="PDF oluşturuldu", message=success_message, created_path=created_path)

    def _create_risk_pdf_with_filter(self, *, report_filter: RiskCheckReportFilter, file_label: str, dialog_title: str, success_message: str) -> None:
        suggested_path = self._suggested_pdf_path(
            file_label=file_label,
            start_date=report_filter.start_date,
            end_date=report_filter.end_date,
        )

        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            suggested_path,
            "PDF Dosyası (*.pdf)",
        )

        if not selected_path:
            return

        output_path = Path(selected_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        try:
            created_path = create_risk_check_report_pdf(
                output_path=output_path,
                report_filter=report_filter,
                created_by=_created_by_text(self.current_user),
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF oluşturulamadı", f"Risk raporu oluşturulurken hata oluştu:\n\n{exc}")
            return

        self._ask_open_created_pdf(title="PDF oluşturuldu", message=success_message, created_path=created_path)

    def _ask_open_created_pdf(self, *, title: str, message: str, created_path: str) -> None:
        answer = QMessageBox.question(
            self,
            title,
            (
                f"{message}\n\n"
                f"Dosya:\n{created_path}\n\n"
                "Şimdi açmak ister misin?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(created_path).resolve())))
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.session import session_scope
from app.models.credit_facility import BankAccountCreditLimit
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    calculate_credit_limit_period_report,
    create_credit_limit_period_interest_transaction,
)
from app.reports.credit_limit_period_pdf_report import (
    CreditLimitPeriodPdfReportError,
    create_credit_limit_period_pdf_report,
)
from app.ui.components.no_wheel_widgets import NoWheelDateEdit


CREDIT_LIMIT_PERIOD_REPORT_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QWidget#CreditLimitPeriodReportWrapper,
QWidget#CreditLimitPeriodReportBody {
    background-color: #0f172a;
}

QScrollArea#CreditLimitPeriodReportScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea#CreditLimitPeriodReportScrollArea > QWidget,
QScrollArea#CreditLimitPeriodReportScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

QFrame#SummaryCard {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 14px;
}

QLabel#DialogTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
}

QLabel#DialogSubtitle,
QLabel#DialogHelp,
QLabel#MutedLabel {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#MetricLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 800;
}

QLabel#MetricValue {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QDateEdit {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 9px;
    padding: 8px 10px;
    min-height: 28px;
}

QDateEdit:focus {
    border: 1px solid #3b82f6;
}

QDateEdit::drop-down {
    background-color: #0f172a;
    border-left: 1px solid #334155;
    width: 24px;
}

QCalendarWidget QWidget {
    background-color: #111827;
    color: #e5e7eb;
}

QCalendarWidget QToolButton {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px;
    margin: 2px;
}

QCalendarWidget QToolButton:hover {
    background-color: #2563eb;
}

QCalendarWidget QMenu {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
}

QCalendarWidget QSpinBox {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}

QCalendarWidget QAbstractItemView:enabled {
    background-color: #0f172a;
    color: #e5e7eb;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QCalendarWidget QAbstractItemView:disabled {
    color: #64748b;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 900;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#ExportButton {
    background-color: #16a34a;
    color: #ffffff;
    border: 1px solid #22c55e;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 900;
}

QPushButton#ExportButton:hover {
    background-color: #15803d;
}

QPushButton#InterestButton {
    background-color: #7c3aed;
    color: #ffffff;
    border: 1px solid #a855f7;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 900;
}

QPushButton#InterestButton:hover {
    background-color: #6d28d9;
}

QPushButton#SecondaryButton {
    background-color: #172033;
    color: #cbd5e1;
    border: 1px solid #24324a;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 900;
}

QPushButton#SecondaryButton:hover {
    background-color: #1e293b;
    color: #ffffff;
}

QTableWidget#ReportTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#ReportTable::item {
    padding: 6px;
    border: none;
}

QHeaderView::section {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 8px;
    font-weight: 900;
}

QTableCornerButton::section {
    background-color: #1f2937;
    border: 1px solid #334155;
}

QScrollBar:vertical {
    background-color: #0f172a;
    width: 10px;
    margin: 0px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #334155;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #475569;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
    border: none;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}
"""


class CreditLimitPeriodReportDialog(QDialog):
    def __init__(
        self,
        *,
        current_user: Any | None = None,
        credit_limit_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.current_user = current_user
        self.credit_limit_id = int(credit_limit_id)
        self._credit_limit_title = ""
        self._currency_code = "TRY"

        self.setWindowTitle("Kredili / Limitli Mevduat Dönem Raporu")
        self.resize(1180, 780)
        self.setMinimumSize(980, 640)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(CREDIT_LIMIT_PERIOD_REPORT_DIALOG_STYLE)

        self.title_label = QLabel("Dönem Raporu / Faiz Hesapla")
        self.title_label.setObjectName("DialogTitle")

        self.subtitle_label = QLabel(
            "Seçili limitli hesabın dönem içi kullanımlarını, ödemelerini, T+1 ödeme valörünü ve günlük faiz hesabını gösterir. "
            "Hesaplanan faiz istenirse tahakkuk hareketi olarak kaydedilebilir; bu işlem banka hesabından para düşmez."
        )
        self.subtitle_label.setObjectName("DialogSubtitle")
        self.subtitle_label.setWordWrap(True)

        today = date.today()
        first_day = date(today.year, today.month, 1)
        next_month_year = today.year + 1 if today.month == 12 else today.year
        next_month = 1 if today.month == 12 else today.month + 1
        next_month_first_day = date(next_month_year, next_month, 1)
        last_day = date.fromordinal(next_month_first_day.toordinal() - 1)

        self.period_start_input = NoWheelDateEdit()
        self.period_start_input.setCalendarPopup(True)
        self.period_start_input.setDisplayFormat("dd.MM.yyyy")
        self.period_start_input.setDate(QDate(first_day.year, first_day.month, first_day.day))

        self.period_end_input = NoWheelDateEdit()
        self.period_end_input.setCalendarPopup(True)
        self.period_end_input.setDisplayFormat("dd.MM.yyyy")
        self.period_end_input.setDate(QDate(last_day.year, last_day.month, last_day.day))

        self.refresh_button = QPushButton("Raporu Hesapla")
        self.refresh_button.setObjectName("PrimaryButton")
        self.refresh_button.clicked.connect(self.refresh_report)

        self.save_interest_button = QPushButton("Faizi Kaydet")
        self.save_interest_button.setObjectName("InterestButton")
        self.save_interest_button.clicked.connect(self.save_interest_accrual)

        self.export_pdf_button = QPushButton("PDF Oluştur")
        self.export_pdf_button.setObjectName("ExportButton")
        self.export_pdf_button.clicked.connect(self.create_pdf_report)

        self.close_button = QPushButton("Kapat")
        self.close_button.setObjectName("SecondaryButton")
        self.close_button.clicked.connect(self.accept)

        self.limit_name_value_label = self._metric_value_label("-")
        self.period_value_label = self._metric_value_label("-")
        self.limit_amount_value_label = self._metric_value_label("0,00")
        self.interest_rate_value_label = self._metric_value_label("0,000000")
        self.opening_debt_value_label = self._metric_value_label("0,00")
        self.usage_total_value_label = self._metric_value_label("0,00")
        self.payment_total_value_label = self._metric_value_label("0,00")
        self.ending_debt_value_label = self._metric_value_label("0,00")
        self.calculated_interest_value_label = self._metric_value_label("0,00")
        self.total_period_debt_value_label = self._metric_value_label("0,00")

        self.movements_table = self._build_table(
            [
                "İşlem Tarihi",
                "Faize Etki Tarihi",
                "Tür",
                "Tutar",
                "Durum",
                "Referans",
                "Açıklama",
            ]
        )
        self.daily_interest_table = self._build_table(
            [
                "Tarih",
                "Faize Esas Borç",
                "Günlük Faiz",
            ]
        )

        self._build_ui()
        self._load_credit_limit_header()
        self.refresh_report()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 18)
        root_layout.setSpacing(12)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        controls_layout.addWidget(self._plain_label("Dönem Başlangıcı"))
        controls_layout.addWidget(self.period_start_input)
        controls_layout.addWidget(self._plain_label("Dönem Bitişi"))
        controls_layout.addWidget(self.period_end_input)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.save_interest_button)
        controls_layout.addWidget(self.export_pdf_button)
        controls_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("CreditLimitPeriodReportScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        wrapper = QWidget()
        wrapper.setObjectName("CreditLimitPeriodReportWrapper")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 8, 8, 8)
        wrapper_layout.setSpacing(12)

        wrapper_layout.addWidget(self._build_summary_card())

        movements_title = QLabel("Dönem Hareketleri")
        movements_title.setObjectName("SectionTitle")
        wrapper_layout.addWidget(movements_title)
        wrapper_layout.addWidget(self.movements_table, 1)

        daily_title = QLabel("Günlük Faiz Dökümü")
        daily_title.setObjectName("SectionTitle")
        wrapper_layout.addWidget(daily_title)
        wrapper_layout.addWidget(self.daily_interest_table, 1)

        help_label = QLabel(
            "Not: Limit kullanımı aynı gün faize girer. Limit ödemesi bankaların valör uygulamasına uygun şekilde ertesi gün borçtan düşer. "
            "Bu nedenle aynı gün kullanılıp kapatılan limit için en az 1 günlük faiz oluşabilir. "
            "Faizi Kaydet işlemi yalnızca faiz tahakkuku oluşturur; banka hesabından otomatik para çıkışı yapmaz."
        )
        help_label.setObjectName("DialogHelp")
        help_label.setWordWrap(True)
        wrapper_layout.addWidget(help_label)

        scroll_area.setWidget(wrapper)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)

        root_layout.addWidget(self.title_label)
        root_layout.addWidget(self.subtitle_label)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(scroll_area, 1)
        root_layout.addLayout(button_layout)

    def _build_summary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("SummaryCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        title = QLabel("Dönem Özeti")
        title.setObjectName("SectionTitle")

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        self._add_metric(grid, 0, 0, "Limit Hesabı", self.limit_name_value_label)
        self._add_metric(grid, 0, 1, "Dönem", self.period_value_label)
        self._add_metric(grid, 0, 2, "Limit", self.limit_amount_value_label)
        self._add_metric(grid, 0, 3, "Faiz Oranı", self.interest_rate_value_label)

        self._add_metric(grid, 2, 0, "Dönem Başı Borç", self.opening_debt_value_label)
        self._add_metric(grid, 2, 1, "Dönem Kullanımı", self.usage_total_value_label)
        self._add_metric(grid, 2, 2, "Dönem Ödemesi", self.payment_total_value_label)
        self._add_metric(grid, 2, 3, "Dönem Sonu Ana Para", self.ending_debt_value_label)

        self._add_metric(grid, 4, 0, "Hesaplanan Faiz", self.calculated_interest_value_label)
        self._add_metric(grid, 4, 1, "Toplam Dönem Borcu", self.total_period_debt_value_label)

        layout.addWidget(title)
        layout.addLayout(grid)

        return card

    def _add_metric(
        self,
        grid: QGridLayout,
        row: int,
        column: int,
        label_text: str,
        value_label: QLabel,
    ) -> None:
        label = QLabel(label_text)
        label.setObjectName("MetricLabel")
        grid.addWidget(label, row, column)
        grid.addWidget(value_label, row + 1, column)

    def _metric_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MetricValue")
        return label

    def _plain_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MutedLabel")
        return label

    def _build_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setObjectName("ReportTable")
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        return table

    def _load_credit_limit_header(self) -> None:
        try:
            with session_scope() as session:
                credit_limit = session.get(BankAccountCreditLimit, self.credit_limit_id)

                if credit_limit is None:
                    raise CreditFacilityServiceError(
                        f"Kredili / limitli hesap bulunamadı. ID: {self.credit_limit_id}"
                    )

                bank_account = credit_limit.bank_account
                bank_name = "-"
                account_name = "-"

                if bank_account is not None:
                    account_name = bank_account.account_name or "-"
                    if getattr(bank_account, "bank", None) is not None:
                        bank_name = bank_account.bank.name or "-"

                self._currency_code = credit_limit.currency_code.value
                self._credit_limit_title = f"{bank_name} / {account_name} / {credit_limit.limit_name}"
                self.limit_name_value_label.setText(self._credit_limit_title)

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Limit Bilgisi Yüklenemedi",
                f"Kredili / limitli hesap bilgisi yüklenirken hata oluştu:\n\n{exc}",
            )
            self.reject()

    def save_interest_accrual(self) -> None:
        period_start = self._selected_date(self.period_start_input)
        period_end = self._selected_date(self.period_end_input)

        if period_end < period_start:
            QMessageBox.warning(
                self,
                "Geçersiz Dönem",
                "Dönem bitiş tarihi başlangıç tarihinden eski olamaz.",
            )
            return

        try:
            with session_scope() as session:
                report = calculate_credit_limit_period_report(
                    session,
                    credit_limit_id=self.credit_limit_id,
                    period_start=period_start,
                    period_end=period_end,
                )
                calculated_interest = self._to_decimal(report.get("calculated_interest_total"))

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Faiz Hesaplanamadı",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Faiz tahakkuku ön kontrolü yapılırken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        if calculated_interest <= Decimal("0.00"):
            QMessageBox.information(
                self,
                "Kaydedilecek Faiz Yok",
                "Seçili dönem için kaydedilecek faiz tutarı oluşmamış.",
            )
            return

        period_text = f"{self._format_date(period_start)} - {self._format_date(period_end)}"
        question = (
            f"Seçili dönem için {self._format_money(calculated_interest)} faiz tahakkuku oluşturulacak.\n\n"
            f"Dönem: {period_text}\n\n"
            "Bu işlem banka hesabından para düşmez. Sadece kredili / limitli hesap üzerinde faiz borcu oluşturur.\n\n"
            "Devam etmek istiyor musun?"
        )

        answer = QMessageBox.question(
            self,
            "Faizi Kaydet",
            question,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        try:
            with session_scope() as session:
                transaction = create_credit_limit_period_interest_transaction(
                    session,
                    credit_limit_id=self.credit_limit_id,
                    period_start=period_start,
                    period_end=period_end,
                    transaction_date=period_end,
                    notes=None,
                    created_by_user_id=self._current_user_id(),
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Faiz Kaydedilemedi",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Faiz tahakkuku kaydedilirken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Faiz Kaydedildi",
            (
                "Dönem faizi tahakkuk hareketi olarak kaydedildi.\n\n"
                f"Tutar: {self._format_money(transaction.amount)}\n"
                "Not: Bu işlem banka hesabından para düşmedi. Ödeme ayrıca Limit Öde işlemiyle yapılmalıdır."
            ),
        )
        self.refresh_report()

    def create_pdf_report(self) -> None:
        period_start = self._selected_date(self.period_start_input)
        period_end = self._selected_date(self.period_end_input)

        if period_end < period_start:
            QMessageBox.warning(
                self,
                "Geçersiz Dönem",
                "Dönem bitiş tarihi başlangıç tarihinden eski olamaz.",
            )
            return

        default_filename = self._default_pdf_filename(period_start, period_end)
        default_path = Path.home() / default_filename

        selected_file_path, _ = QFileDialog.getSaveFileName(
            self,
            "PDF Raporu Kaydet",
            str(default_path),
            "PDF Dosyası (*.pdf)",
        )

        if not selected_file_path:
            return

        output_path = Path(selected_file_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        try:
            generated_path = create_credit_limit_period_pdf_report(
                output_path=output_path,
                credit_limit_id=self.credit_limit_id,
                period_start=period_start,
                period_end=period_end,
                created_by=self._current_user_display_name(),
            )

        except CreditLimitPeriodPdfReportError as exc:
            QMessageBox.warning(
                self,
                "PDF Oluşturulamadı",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"PDF raporu oluşturulurken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "PDF Raporu Oluşturuldu",
            f"Kredili / limitli mevduat dönem raporu başarıyla oluşturuldu.\n\nDosya:\n{generated_path}",
        )

    def _default_pdf_filename(self, period_start: date, period_end: date) -> str:
        title = self._credit_limit_title or "Kredili Limitli Mevduat"
        safe_title = self._safe_filename_part(title)
        start_text = period_start.strftime("%Y%m%d")
        end_text = period_end.strftime("%Y%m%d")
        return f"FTM_Kredili_Limitli_Mevduat_Raporu_{safe_title}_{start_text}_{end_text}.pdf"

    def _safe_filename_part(self, value: Any) -> str:
        text = str(value or "").strip()

        if not text:
            return "Rapor"

        replacements = {
            "ç": "c",
            "Ç": "C",
            "ğ": "g",
            "Ğ": "G",
            "ı": "i",
            "İ": "I",
            "ö": "o",
            "Ö": "O",
            "ş": "s",
            "Ş": "S",
            "ü": "u",
            "Ü": "U",
        }

        for source, target in replacements.items():
            text = text.replace(source, target)

        text = re.sub(r"[^A-Za-z0-9_-]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")

        if not text:
            return "Rapor"

        return text[:80]

    def _current_user_display_name(self) -> str:
        if self.current_user is None:
            return "FTM Kullanıcısı"

        for attribute_name in ("full_name", "name", "username", "email"):
            value = getattr(self.current_user, attribute_name, None)

            if value:
                return str(value)

        user_id = getattr(self.current_user, "id", None)

        if user_id is not None:
            return f"Kullanıcı ID: {user_id}"

        return "FTM Kullanıcısı"

    def _current_user_id(self) -> int | None:
        if self.current_user is None:
            return None

        user_id = getattr(self.current_user, "id", None)

        if user_id is None:
            return None

        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    def refresh_report(self) -> None:
        period_start = self._selected_date(self.period_start_input)
        period_end = self._selected_date(self.period_end_input)

        if period_end < period_start:
            QMessageBox.warning(
                self,
                "Geçersiz Dönem",
                "Dönem bitiş tarihi başlangıç tarihinden eski olamaz.",
            )
            return

        try:
            with session_scope() as session:
                report = calculate_credit_limit_period_report(
                    session,
                    credit_limit_id=self.credit_limit_id,
                    period_start=period_start,
                    period_end=period_end,
                )

        except CreditFacilityServiceError as exc:
            QMessageBox.warning(
                self,
                "Rapor Hesaplanamadı",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Dönem raporu hesaplanırken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        self._currency_code = str(report.get("currency_code") or self._currency_code)
        self._populate_summary(report)
        self._populate_movements_table(report.get("movement_rows", []))
        self._populate_daily_interest_table(report.get("daily_rows", []))

    def _populate_summary(self, report: dict[str, Any]) -> None:
        period_start = report.get("period_start")
        period_end = report.get("period_end")
        calculated_interest = self._to_decimal(report.get("calculated_interest_total"))
        ending_principal = self._to_decimal(report.get("ending_interest_basis_debt"))
        total_period_debt = ending_principal + calculated_interest

        self.limit_name_value_label.setText(self._credit_limit_title or str(report.get("limit_name") or "-"))
        self.period_value_label.setText(
            f"{self._format_date(period_start)} - {self._format_date(period_end)}"
        )
        self.limit_amount_value_label.setText(self._format_money(report.get("limit_amount")))
        self.interest_rate_value_label.setText(
            f"% {self._format_rate(report.get('monthly_interest_rate'))}"
        )
        self.opening_debt_value_label.setText(self._format_money(report.get("opening_interest_basis_debt")))
        self.usage_total_value_label.setText(self._format_money(report.get("period_usage_total")))
        self.payment_total_value_label.setText(self._format_money(report.get("period_payment_total")))
        self.ending_debt_value_label.setText(self._format_money(ending_principal))
        self.calculated_interest_value_label.setText(self._format_money(calculated_interest))
        self.total_period_debt_value_label.setText(self._format_money(total_period_debt))

    def _populate_movements_table(self, rows: list[dict[str, Any]]) -> None:
        table_rows: list[list[Any]] = []

        sorted_rows = sorted(
            rows,
            key=lambda item: (
                item.get("transaction_date") or date.min,
                item.get("effective_date") or date.min,
                int(item.get("id") or 0),
            ),
        )

        for row in sorted_rows:
            table_rows.append(
                [
                    self._format_date(row.get("transaction_date")),
                    self._format_date(row.get("effective_date")),
                    self._transaction_type_text(row.get("transaction_type")),
                    self._format_money(row.get("amount"), currency_code=row.get("currency_code")),
                    self._transaction_status_text(row.get("status")),
                    row.get("reference_no") or "-",
                    row.get("description") or "-",
                ]
            )

        self._fill_table(
            table=self.movements_table,
            rows=table_rows,
            empty_message="Bu dönemde limit hareketi bulunamadı.",
        )

    def _populate_daily_interest_table(self, rows: list[dict[str, Any]]) -> None:
        table_rows: list[list[Any]] = []

        for row in rows:
            table_rows.append(
                [
                    self._format_date(row.get("date")),
                    self._format_money(row.get("interest_basis_debt"), currency_code=row.get("currency_code")),
                    self._format_money(row.get("daily_interest"), currency_code=row.get("currency_code")),
                ]
            )

        self._fill_table(
            table=self.daily_interest_table,
            rows=table_rows,
            empty_message="Seçili dönem için günlük faiz satırı oluşmadı.",
        )

    def _fill_table(
        self,
        *,
        table: QTableWidget,
        rows: list[list[Any]],
        empty_message: str,
    ) -> None:
        table.clearSpans()
        table.clearSelection()

        if not rows:
            table.setRowCount(1)
            empty_item = QTableWidgetItem(empty_message)
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
            empty_item.setForeground(QColor("#94a3b8"))
            empty_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(0, 0, empty_item)
            table.setSpan(0, 0, 1, table.columnCount())

            for column_index in range(1, table.columnCount()):
                hidden_item = QTableWidgetItem("")
                hidden_item.setFlags(hidden_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(0, column_index, hidden_item)

            table.resizeRowsToContents()
            return

        table.setRowCount(len(rows))

        for row_index, row_values in enumerate(rows):
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                upper_value = str(value).strip().upper()
                if upper_value in {"AKTIF", "KULLANIM", "LIMIT KULLANIMI"}:
                    item.setForeground(QColor("#22c55e"))
                elif upper_value in {"ÖDEME", "LIMIT ÖDEMESI", "LİMİT ÖDEMESİ"}:
                    item.setForeground(QColor("#38bdf8"))
                elif upper_value in {"IPTAL", "İPTAL"}:
                    item.setForeground(QColor("#ef4444"))

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _selected_date(self, date_edit: NoWheelDateEdit) -> date:
        qdate = date_edit.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _to_decimal(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value

        if value is None:
            return Decimal("0.00")

        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0.00")

    def _format_money(self, value: Any, *, currency_code: Any | None = None) -> str:
        amount = self._to_decimal(value)
        text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{text} {currency_code or self._currency_code}"

    def _format_rate(self, value: Any) -> str:
        amount = self._to_decimal(value)
        text = f"{amount:,.6f}".replace(",", "X").replace(".", ",").replace("X", ".")
        text = text.rstrip("0").rstrip(",")
        return text or "0"

    def _format_date(self, value: Any) -> str:
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")

        if value is None:
            return "-"

        return str(value)

    def _transaction_type_text(self, value: Any) -> str:
        mapping = {
            "USAGE": "Limit Kullanımı",
            "PAYMENT": "Limit Ödemesi",
            "INTEREST": "Faiz Tahakkuku",
            "FEE": "Masraf",
            "ADJUSTMENT": "Düzeltme",
        }
        return mapping.get(str(value or ""), str(value or "-"))

    def _transaction_status_text(self, value: Any) -> str:
        mapping = {
            "ACTIVE": "Aktif",
            "CANCELLED": "İptal",
        }
        return mapping.get(str(value or ""), str(value or "-"))


__all__ = [
    "CreditLimitPeriodReportDialog",
]

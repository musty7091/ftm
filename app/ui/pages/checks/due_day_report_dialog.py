from datetime import date, datetime
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.checks.due_day_report_data import (
    DueDayCheckRow,
    DueDayCurrencyLine,
    DueDayReportData,
    build_currency_totals_text,
    load_due_day_report_data,
)


DUE_DAY_REPORT_DIALOG_STYLE = """
QDialog {
    background-color: #0f172a;
}

QScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

QWidget#DueDayReportContent {
    background-color: #0f172a;
}

QFrame#ReportHeaderCard,
QFrame#ReportCard {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 18px;
}

QFrame#ReportMetricCard {
    background-color: #0b1220;
    border: 1px solid #24324a;
    border-radius: 14px;
}

QFrame#ReportMetricPositive {
    background-color: rgba(6, 78, 59, 0.22);
    border: 1px solid rgba(16, 185, 129, 0.32);
    border-radius: 14px;
}

QFrame#ReportMetricNegative {
    background-color: rgba(127, 29, 29, 0.20);
    border: 1px solid rgba(239, 68, 68, 0.32);
    border-radius: 14px;
}

QFrame#ReportMetricWarning {
    background-color: rgba(120, 53, 15, 0.23);
    border: 1px solid rgba(245, 158, 11, 0.34);
    border-radius: 14px;
}

QLabel {
    background-color: transparent;
}

QLabel#ReportTitle {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 700;
}

QLabel#ReportSubtitle {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 450;
}

QLabel#ReportSectionTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 650;
}

QLabel#ReportMetricTitle {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 500;
}

QLabel#ReportMetricValue {
    color: #f8fafc;
    font-size: 17px;
    font-weight: 650;
}

QLabel#ReportMetricHint {
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 450;
}

QLabel#ReportPositiveText {
    color: #a7f3d0;
    font-size: 17px;
    font-weight: 650;
}

QLabel#ReportNegativeText {
    color: #fecaca;
    font-size: 17px;
    font-weight: 650;
}

QLabel#ReportWarningText {
    color: #fde68a;
    font-size: 13px;
    font-weight: 550;
}

QLabel#ReportMutedText {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 450;
}

QLabel#ReportWarningLine {
    background-color: rgba(120, 53, 15, 0.22);
    color: #fde68a;
    border: 1px solid rgba(245, 158, 11, 0.28);
    border-radius: 10px;
    padding: 7px 9px;
    font-size: 12px;
    font-weight: 500;
}

QTableWidget {
    background-color: #0b1220;
    color: #e5e7eb;
    border: 1px solid #1e293b;
    border-radius: 12px;
    gridline-color: #1f2937;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 5px;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #f8fafc;
    border: none;
    border-right: 1px solid #334155;
    padding: 7px;
    font-weight: 600;
}

QTabWidget#ReportTabs::pane {
    border: 1px solid #1e293b;
    background-color: #0b1220;
    border-radius: 12px;
    top: -1px;
}

QTabBar::tab {
    background-color: #172033;
    color: #94a3b8;
    border: 1px solid #24324a;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 8px 16px;
    margin-right: 5px;
    min-width: 120px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QTabBar::tab:hover:!selected {
    background-color: #1e293b;
    color: #e5e7eb;
}

QPushButton#ReportPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 650;
    text-align: center;
}

QPushButton#ReportPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#ReportSecondaryButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 550;
    text-align: center;
}

QPushButton#ReportSecondaryButton:hover {
    background-color: #334155;
    color: #ffffff;
}

QPushButton#ReportDisabledButton {
    background-color: #111827;
    color: #64748b;
    border: 1px solid #1f2937;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 550;
    text-align: center;
}
"""


def _filter_label(value: str) -> str:
    normalized_value = str(value or "").strip().upper()

    if normalized_value == "ALL":
        return "Tümü"

    if normalized_value == "RECEIVED":
        return "Alınan Çekler"

    if normalized_value == "ISSUED":
        return "Yazılan Çekler"

    if normalized_value == "PENDING":
        return "Bekleyen"

    if normalized_value == "CLOSED":
        return "Sonuçlanan"

    if normalized_value == "PROBLEM":
        return "Problemli / Riskli"

    if normalized_value == "OVERDUE":
        return "Vadesi Geçmiş"

    if normalized_value == "TODAY":
        return "Seçili Gün"

    return normalized_value or "-"


def _net_total_style_name(currency_lines: list[DueDayCurrencyLine]) -> str:
    if not currency_lines:
        return "ReportMetricCard"

    if len(currency_lines) != 1:
        return "ReportMetricCard"

    net_total = currency_lines[0].net_total

    if net_total > Decimal("0.00"):
        return "ReportMetricPositive"

    if net_total < Decimal("0.00"):
        return "ReportMetricNegative"

    return "ReportMetricCard"


def _net_total_label_style_name(currency_lines: list[DueDayCurrencyLine]) -> str:
    if not currency_lines:
        return "ReportMetricValue"

    if len(currency_lines) != 1:
        return "ReportMetricValue"

    net_total = currency_lines[0].net_total

    if net_total > Decimal("0.00"):
        return "ReportPositiveText"

    if net_total < Decimal("0.00"):
        return "ReportNegativeText"

    return "ReportMetricValue"


def _combined_net_text(currency_lines: list[DueDayCurrencyLine]) -> str:
    if not currency_lines:
        return "0,00 TL"

    return " / ".join(currency_line.net_total_text for currency_line in currency_lines)


def _combined_incoming_text(currency_lines: list[DueDayCurrencyLine]) -> str:
    if not currency_lines:
        return "0,00 TL"

    return " / ".join(currency_line.incoming_total_text for currency_line in currency_lines)


def _combined_outgoing_text(currency_lines: list[DueDayCurrencyLine]) -> str:
    if not currency_lines:
        return "0,00 TL"

    return " / ".join(currency_line.outgoing_total_text for currency_line in currency_lines)


def _row_color(row: DueDayCheckRow) -> QColor:
    if row.status_group == "PROBLEM":
        return QColor("#fbbf24")

    if row.status_group == "CLOSED":
        return QColor("#94a3b8")

    if row.check_type == "RECEIVED":
        return QColor("#a7f3d0")

    if row.check_type == "ISSUED":
        return QColor("#fecaca")

    return QColor("#e5e7eb")


class DueDayReportDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        report_date: date | datetime | str,
        check_type_filter: str | None = "ALL",
        status_filter: str | None = "ALL",
    ) -> None:
        super().__init__(parent)

        self.report_data = load_due_day_report_data(
            report_date,
            check_type_filter=check_type_filter,
            status_filter=status_filter,
        )

        self.setWindowTitle(f"Seçili Gün Çek Raporu - {self.report_data.report_date_text}")
        self.resize(1180, 760)
        self.setMinimumSize(980, 620)
        self.setModal(True)
        self.setStyleSheet(DUE_DAY_REPORT_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("DueDayReportContent")

        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(22, 22, 22, 16)
        self.content_layout.setSpacing(14)

        self._build_content()

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)
        root_layout.addWidget(self._build_footer())

    def _build_content(self) -> None:
        self.content_layout.addWidget(self._build_header_card())

        if self.report_data.error_message:
            self.content_layout.addWidget(self._build_error_card())
            return

        self.content_layout.addWidget(self._build_summary_card())
        self.content_layout.addWidget(self._build_financial_effect_card())
        self.content_layout.addWidget(self._build_warnings_card())
        self.content_layout.addWidget(self._build_tables_card(), 1)

    def _build_header_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportHeaderCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(5)

        title = QLabel("FTM - Seçili Gün Çek Raporu")
        title.setObjectName("ReportTitle")

        subtitle = QLabel(
            f"Tarih: {self.report_data.report_date_text} | "
            f"Oluşturma: {self.report_data.generated_at_text} | "
            f"Çek türü: {_filter_label(self.report_data.check_type_filter)} | "
            f"Durum: {_filter_label(self.report_data.status_filter)}"
        )
        subtitle.setObjectName("ReportSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return card

    def _build_error_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportMetricNegative")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("Rapor verisi okunamadı")
        title.setObjectName("ReportSectionTitle")

        body = QLabel(self.report_data.error_message or "-")
        body.setObjectName("ReportNegativeText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

        return card

    def _build_summary_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Günlük Özet")
        title.setObjectName("ReportSectionTitle")

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metrics.setColumnStretch(0, 1)
        metrics.setColumnStretch(1, 1)
        metrics.setColumnStretch(2, 1)
        metrics.setColumnStretch(3, 1)

        metrics.addWidget(
            self._build_metric_card(
                title="Toplam Kayıt",
                value=str(self.report_data.total_count),
                hint=(
                    f"Alınan: {self.report_data.received_count} | "
                    f"Yazılan: {self.report_data.issued_count}"
                ),
            ),
            0,
            0,
        )

        metrics.addWidget(
            self._build_metric_card(
                title="Bekleyen",
                value=str(self.report_data.pending_count),
                hint="Vadesi açık işlem etkisi",
            ),
            0,
            1,
        )

        metrics.addWidget(
            self._build_metric_card(
                title="Sonuçlanan",
                value=str(self.report_data.closed_count),
                hint="Tahsil / ödeme / iptal / ciro vb.",
            ),
            0,
            2,
        )

        metrics.addWidget(
            self._build_metric_card(
                title="Uyarı",
                value=str(self.report_data.problem_count + self.report_data.overdue_count),
                hint=(
                    f"Problem: {self.report_data.problem_count} | "
                    f"Vadesi geçmiş: {self.report_data.overdue_count}"
                ),
                object_name="ReportMetricWarning"
                if self.report_data.problem_count + self.report_data.overdue_count > 0
                else "ReportMetricCard",
            ),
            0,
            3,
        )

        layout.addWidget(title)
        layout.addLayout(metrics)

        return card

    def _build_financial_effect_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Finansal Etki")
        title.setObjectName("ReportSectionTitle")

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metrics.setColumnStretch(0, 1)
        metrics.setColumnStretch(1, 1)
        metrics.setColumnStretch(2, 1)

        metrics.addWidget(
            self._build_metric_card(
                title="Giriş Etkisi",
                value=_combined_incoming_text(self.report_data.currency_lines),
                hint="Seçili gün alınan çek toplamı",
                object_name="ReportMetricPositive"
                if self.report_data.received_count > 0
                else "ReportMetricCard",
                value_object_name="ReportPositiveText"
                if self.report_data.received_count > 0
                else "ReportMetricValue",
            ),
            0,
            0,
        )

        metrics.addWidget(
            self._build_metric_card(
                title="Çıkış Etkisi",
                value=_combined_outgoing_text(self.report_data.currency_lines),
                hint="Seçili gün yazılan çek toplamı",
                object_name="ReportMetricNegative"
                if self.report_data.issued_count > 0
                else "ReportMetricCard",
                value_object_name="ReportNegativeText"
                if self.report_data.issued_count > 0
                else "ReportMetricValue",
            ),
            0,
            1,
        )

        metrics.addWidget(
            self._build_metric_card(
                title="Net Etki",
                value=_combined_net_text(self.report_data.currency_lines),
                hint="Kur çevrimi yapılmadan para birimi bazlı net",
                object_name=_net_total_style_name(self.report_data.currency_lines),
                value_object_name=_net_total_label_style_name(self.report_data.currency_lines),
            ),
            0,
            2,
        )

        currency_table = self._build_currency_table()
        self._fill_currency_table(currency_table)

        layout.addWidget(title)
        layout.addLayout(metrics)
        layout.addWidget(currency_table)

        return card

    def _build_warnings_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Uyarılar / Kısa Yorum")
        title.setObjectName("ReportSectionTitle")

        layout.addWidget(title)

        if not self.report_data.warning_messages:
            info = QLabel("Seçili gün için özel uyarı bulunmuyor.")
            info.setObjectName("ReportMutedText")
            layout.addWidget(info)
            return card

        for warning_message in self.report_data.warning_messages:
            warning_label = QLabel(warning_message)
            warning_label.setObjectName("ReportWarningLine")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        return card

    def _build_tables_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Çek Listeleri")
        title.setObjectName("ReportSectionTitle")

        tabs = QTabWidget()
        tabs.setObjectName("ReportTabs")

        received_table = self._build_check_table()
        issued_table = self._build_check_table()

        self._fill_check_table(received_table, self.report_data.received_rows)
        self._fill_check_table(issued_table, self.report_data.issued_rows)

        tabs.addTab(
            received_table,
            f"Alınan Çekler ({self.report_data.received_count})",
        )
        tabs.addTab(
            issued_table,
            f"Yazılan Çekler ({self.report_data.issued_count})",
        )

        layout.addWidget(title)
        layout.addWidget(tabs, 1)

        return card

    def _build_metric_card(
        self,
        *,
        title: str,
        value: str,
        hint: str,
        object_name: str = "ReportMetricCard",
        value_object_name: str = "ReportMetricValue",
    ) -> QWidget:
        card = QFrame()
        card.setObjectName(object_name)
        card.setMinimumHeight(86)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("ReportMetricTitle")
        title_label.setWordWrap(True)

        value_label = QLabel(value)
        value_label.setObjectName(value_object_name)
        value_label.setWordWrap(True)

        hint_label = QLabel(hint)
        hint_label.setObjectName("ReportMetricHint")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)

        return card

    def _build_currency_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            [
                "Para Birimi",
                "Giriş",
                "Çıkış",
                "Net",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(30)
        table.verticalHeader().setMinimumSectionSize(28)
        table.setMinimumHeight(90)
        table.setMaximumHeight(150)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        return table

    def _fill_currency_table(self, table: QTableWidget) -> None:
        rows = self.report_data.currency_lines

        table.setRowCount(len(rows))

        for row_index, currency_line in enumerate(rows):
            values = [
                currency_line.currency_code,
                currency_line.incoming_total_text,
                currency_line.outgoing_total_text,
                currency_line.net_total_text,
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 1:
                    item.setForeground(QColor("#a7f3d0"))
                elif column_index == 2:
                    item.setForeground(QColor("#fecaca"))
                elif column_index == 3:
                    if currency_line.net_total > Decimal("0.00"):
                        item.setForeground(QColor("#a7f3d0"))
                    elif currency_line.net_total < Decimal("0.00"):
                        item.setForeground(QColor("#fecaca"))
                    else:
                        item.setForeground(QColor("#e5e7eb"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index in {1, 2, 3}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                table.setItem(row_index, column_index, item)

        for row_index in range(table.rowCount()):
            table.setRowHeight(row_index, 30)

    def _build_check_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            [
                "Tür",
                "Taraf",
                "Banka / Hesap",
                "Çek No",
                "İşlem Tarihi",
                "Kalan",
                "Tutar",
                "Durum",
                "Açıklama",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(32)
        table.verticalHeader().setMinimumSectionSize(28)
        table.setMinimumHeight(250)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Stretch)

        return table

    def _fill_check_table(
        self,
        table: QTableWidget,
        rows: list[DueDayCheckRow],
    ) -> None:
        table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            type_text = "Alınan" if row.check_type == "RECEIVED" else "Yazılan"
            description_parts: list[str] = []

            if row.reference_no:
                description_parts.append(f"Ref: {row.reference_no}")

            if row.description:
                description_parts.append(row.description)

            description_text = " | ".join(description_parts) if description_parts else "-"

            values = [
                type_text,
                row.party_name,
                row.bank_text,
                row.check_number,
                row.transaction_date_text,
                row.remaining_day_text,
                row.amount_text,
                row.status_text,
                description_text,
            ]

            color = _row_color(row)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setForeground(color)

                if column_index == 6:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip(
                    "\n".join(
                        [
                            f"Tür: {type_text}",
                            f"Taraf: {row.party_name}",
                            f"Banka / Hesap: {row.bank_text}",
                            f"Çek No: {row.check_number}",
                            f"İşlem Tarihi: {row.transaction_date_text}",
                            f"Vade: {row.due_date_text}",
                            f"Kalan: {row.remaining_day_text}",
                            f"Tutar: {row.amount_text}",
                            f"Durum: {row.status_text}",
                            f"Referans: {row.reference_no or '-'}",
                            f"Açıklama: {row.description or '-'}",
                        ]
                    )
                )

                table.setItem(row_index, column_index, item)

        for row_index in range(table.rowCount()):
            table.setRowHeight(row_index, 32)

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("ReportHeaderCard")
        footer.setMaximumHeight(62)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(10)

        info_label = QLabel("PDF çıktısı sonraki adımda eklenecek.")
        info_label.setObjectName("ReportMutedText")

        pdf_button = QPushButton("PDF Hazırla")
        pdf_button.setObjectName("ReportDisabledButton")
        pdf_button.setMinimumHeight(36)
        pdf_button.setEnabled(False)

        close_button = QPushButton("Kapat")
        close_button.setObjectName("ReportSecondaryButton")
        close_button.setMinimumHeight(36)
        close_button.clicked.connect(self.accept)

        layout.addWidget(info_label, 1)
        layout.addWidget(pdf_button)
        layout.addWidget(close_button)

        return footer

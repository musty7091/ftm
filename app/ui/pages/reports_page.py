from __future__ import annotations

from datetime import date
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
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.reports.check_due_report_data import CheckDueReportFilter
from app.reports.check_due_report_pdf import create_check_due_report_pdf


REPORTS_PAGE_STYLE = """
QFrame#ReportsInfoStrip {
    background-color: rgba(15, 23, 42, 0.72);
    border: 1px solid #24324a;
    border-radius: 16px;
}

QFrame#ReportMainCard {
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
    background-color: rgba(15, 23, 42, 0.62);
    border: 1px solid #24324a;
    border-radius: 16px;
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

QPushButton#ReportPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 12px;
    padding: 9px 18px;
    font-weight: 900;
}

QPushButton#ReportPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#ReportPrimaryButton:disabled {
    background-color: #334155;
    color: #94a3b8;
    border: 1px solid #475569;
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


class ReportsPage(QWidget):
    def __init__(self, current_user: Any | None = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.setStyleSheet(REPORTS_PAGE_STYLE)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        self._build_page()

    def _build_page(self) -> None:
        self.main_layout.addWidget(self._build_info_strip())
        self.main_layout.addWidget(self._build_check_due_report_card())
        self.main_layout.addWidget(self._build_planned_reports_card())
        self.main_layout.addStretch(1)

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
            "A4 baskı düzenine uygun, kayıt yeri seçilebilir profesyonel PDF raporları burada oluşturulur."
        )
        body.setObjectName("ReportSubTitle")
        body.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(body)

        status = QLabel("Aktif rapor: Vade Bazlı Çek Raporu")
        status.setObjectName("ReportPlannedBadge")

        layout.addLayout(title_box, 1)
        layout.addWidget(status, 0, Qt.AlignRight | Qt.AlignVCenter)

        return strip

    def _build_check_due_report_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ReportMainCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("Vade Bazlı Çek Raporu")
        title.setObjectName("ReportTitle")

        subtitle = QLabel(
            "Alınan ve yazılan çekleri tarih aralığına, durumuna, türüne ve para birimine göre filtreleyerek A4 yatay PDF raporu oluşturur."
        )
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.pdf_button = QPushButton("PDF Oluştur")
        self.pdf_button.setObjectName("ReportPrimaryButton")
        self.pdf_button.setMinimumHeight(42)
        self.pdf_button.setMinimumWidth(150)
        self.pdf_button.clicked.connect(self._create_check_due_pdf)

        header_row.addLayout(title_box, 1)
        header_row.addWidget(self.pdf_button, 0, Qt.AlignTop)

        filter_panel = self._build_filter_panel()

        hint = QLabel(
            "PDF oluştururken kayıt yeri sorulur. Varsayılan klasör: Belgeler > FTM Raporlar"
        )
        hint.setObjectName("ReportSmallInfo")
        hint.setWordWrap(True)

        layout.addLayout(header_row)
        layout.addWidget(filter_panel)
        layout.addWidget(hint)

        return card

    def _build_filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ReportFilterPanel")

        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)

        today = QDate.currentDate()

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setMinimumHeight(38)
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.start_date_edit.setDate(today)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setMinimumHeight(38)
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.end_date_edit.setDate(today.addDays(30))

        self.check_type_combo = QComboBox()
        self.check_type_combo.setMinimumHeight(38)
        self.check_type_combo.addItem("Tümü", "ALL")
        self.check_type_combo.addItem("Sadece Alınan Çekler", "RECEIVED")
        self.check_type_combo.addItem("Sadece Yazılan Çekler", "ISSUED")

        self.status_group_combo = QComboBox()
        self.status_group_combo.setMinimumHeight(38)
        self.status_group_combo.addItem("Tümü", "ALL")
        self.status_group_combo.addItem("Bekleyen", "PENDING")
        self.status_group_combo.addItem("Sonuçlanan", "CLOSED")
        self.status_group_combo.addItem("Problemli", "PROBLEM")

        self.currency_combo = QComboBox()
        self.currency_combo.setMinimumHeight(38)
        self.currency_combo.addItem("Tümü", "ALL")
        self.currency_combo.addItem("TRY", "TRY")
        self.currency_combo.addItem("USD", "USD")
        self.currency_combo.addItem("EUR", "EUR")
        self.currency_combo.addItem("GBP", "GBP")

        quick_date_row = QHBoxLayout()
        quick_date_row.setSpacing(8)

        next_30_button = self._build_quick_button("Bugün + 30 Gün")
        next_30_button.clicked.connect(self._set_next_30_days)

        current_month_button = self._build_quick_button("Bu Ay")
        current_month_button.clicked.connect(self._set_current_month)

        current_year_button = self._build_quick_button("Bu Yıl")
        current_year_button.clicked.connect(self._set_current_year)

        quick_date_row.addWidget(next_30_button)
        quick_date_row.addWidget(current_month_button)
        quick_date_row.addWidget(current_year_button)
        quick_date_row.addStretch(1)

        layout.addWidget(self._build_field_label("Başlangıç Tarihi"), 0, 0)
        layout.addWidget(self.start_date_edit, 1, 0)

        layout.addWidget(self._build_field_label("Bitiş Tarihi"), 0, 1)
        layout.addWidget(self.end_date_edit, 1, 1)

        layout.addWidget(self._build_field_label("Çek Türü"), 0, 2)
        layout.addWidget(self.check_type_combo, 1, 2)

        layout.addWidget(self._build_field_label("Durum"), 2, 0)
        layout.addWidget(self.status_group_combo, 3, 0)

        layout.addWidget(self._build_field_label("Para Birimi"), 2, 1)
        layout.addWidget(self.currency_combo, 3, 1)

        layout.addWidget(self._build_field_label("Hızlı Tarih"), 2, 2)
        layout.addLayout(quick_date_row, 3, 2)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 2)

        return panel

    def _build_planned_reports_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("PlannedReportsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title = QLabel("Planlanan Raporlar")
        title.setObjectName("ReportTitle")

        note = QLabel("Sıradaki raporlar bu standart şablon üzerinden eklenecek.")
        note.setObjectName("ReportSmallInfo")

        title_row.addWidget(title)
        title_row.addWidget(note, 1)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(
            self._build_coming_report_box(
                "Riskli / Problemli Çek",
                "Karşılıksız, riskli ve vadesi geçmiş çeklerin ayrı risk listesi.",
            ),
            0,
            0,
        )

        grid.addWidget(
            self._build_coming_report_box(
                "İskonto Maliyeti",
                "Faiz, komisyon, BSMV, toplam kesinti ve net ele geçen tutar analizi.",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_coming_report_box(
                "Banka Bakiye",
                "Banka ve para birimi bazlı bakiye, giriş, çıkış ve net durum raporu.",
            ),
            0,
            2,
        )

        grid.addWidget(
            self._build_coming_report_box(
                "POS Mutabakat",
                "Beklenen, gerçekleşen, fark ve banka bazlı POS yatış raporu.",
            ),
            0,
            3,
        )

        layout.addLayout(title_row)
        layout.addLayout(grid)

        return card

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

    def _build_coming_report_box(self, title_text: str, body_text: str) -> QWidget:
        box = QFrame()
        box.setObjectName("PlannedReportBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(title_text)
        title.setObjectName("ReportPlannedTitle")
        title.setWordWrap(True)

        body = QLabel(body_text)
        body.setObjectName("ReportPlannedBody")
        body.setWordWrap(True)

        status = QLabel("Planlandı")
        status.setObjectName("ReportPlannedBadge")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addWidget(status, 0, Qt.AlignLeft)

        return box

    def _set_next_30_days(self) -> None:
        today = QDate.currentDate()

        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today.addDays(30))

    def _set_current_month(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        last_day = first_day.addMonths(1).addDays(-1)

        self.start_date_edit.setDate(first_day)
        self.end_date_edit.setDate(last_day)

    def _set_current_year(self) -> None:
        today = QDate.currentDate()
        first_day = QDate(today.year(), 1, 1)
        last_day = QDate(today.year(), 12, 31)

        self.start_date_edit.setDate(first_day)
        self.end_date_edit.setDate(last_day)

    def _build_report_filter(self) -> CheckDueReportFilter:
        start_date = _qdate_to_date(self.start_date_edit.date())
        end_date = _qdate_to_date(self.end_date_edit.date())

        if end_date < start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

        return CheckDueReportFilter(
            start_date=start_date,
            end_date=end_date,
            check_type=str(self.check_type_combo.currentData() or "ALL"),
            status_group=str(self.status_group_combo.currentData() or "ALL"),
            currency_code=str(self.currency_combo.currentData() or "ALL"),
        )

    def _suggested_pdf_path(self, report_filter: CheckDueReportFilter) -> str:
        reports_folder = _default_reports_folder()
        reports_folder.mkdir(parents=True, exist_ok=True)

        start_text = report_filter.start_date.strftime("%Y-%m-%d")
        end_text = report_filter.end_date.strftime("%Y-%m-%d")

        file_name = _safe_file_name_text(
            f"FTM_Vade_Bazli_Cek_Raporu_{start_text}_{end_text}.pdf"
        )

        return str(reports_folder / file_name)

    def _create_check_due_pdf(self) -> None:
        try:
            report_filter = self._build_report_filter()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Eksik veya hatalı bilgi",
                str(exc),
            )
            return

        suggested_path = self._suggested_pdf_path(report_filter)

        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Vade Bazlı Çek Raporu PDF Kaydet",
            suggested_path,
            "PDF Dosyası (*.pdf)",
        )

        if not selected_path:
            return

        output_path = Path(selected_path)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        self.pdf_button.setEnabled(False)
        self.pdf_button.setText("Oluşturuluyor...")

        try:
            created_path = create_check_due_report_pdf(
                output_path=output_path,
                report_filter=report_filter,
                created_by=_created_by_text(self.current_user),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "PDF oluşturulamadı",
                f"Rapor oluşturulurken hata oluştu:\n\n{exc}",
            )
            self.pdf_button.setEnabled(True)
            self.pdf_button.setText("PDF Oluştur")
            return

        self.pdf_button.setEnabled(True)
        self.pdf_button.setText("PDF Oluştur")

        answer = QMessageBox.question(
            self,
            "PDF oluşturuldu",
            (
                "Vade Bazlı Çek Raporu başarıyla oluşturuldu.\n\n"
                f"Dosya:\n{created_path}\n\n"
                "Şimdi açmak ister misin?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(created_path).resolve()))
            )
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
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
from sqlalchemy import select

from app.db.session import session_scope
from app.models.business_partner import BusinessPartner
from app.reports.partner_statement_data import PartnerStatementFilter
from app.reports.partner_statement_report import create_partner_statement_report_pdf
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES


@dataclass(frozen=True)
class PartnerStatementPartnerOption:
    partner_id: int
    name: str
    partner_type: str
    partner_type_text: str
    is_active: bool
    status_text: str


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def _partner_type_text(value: Any) -> str:
    normalized_value = (
        value.value if hasattr(value, "value") else str(value or "")
    ).strip().upper()

    if normalized_value == "CUSTOMER":
        return "Müşteri"

    if normalized_value == "SUPPLIER":
        return "Tedarikçi"

    if normalized_value == "BOTH":
        return "Müşteri / Tedarikçi"

    if normalized_value == "OTHER":
        return "Diğer"

    return normalized_value or "-"


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

    return text.strip("_") or "Cari_Hareket_Raporu"


def _default_reports_folder() -> Path:
    return Path.home() / "Documents" / "FTM Raporlar"


def _current_year_start() -> QDate:
    today = QDate.currentDate()
    return QDate(today.year(), 1, 1)


def _current_date() -> QDate:
    return QDate.currentDate()


class PartnerStatementReportDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        created_by: str,
    ) -> None:
        super().__init__(parent)

        self.created_by = created_by
        self.partner_options = self._load_partner_options()
        self.partner_lookup = {
            partner.partner_id: partner
            for partner in self.partner_options
        }

        self.setWindowTitle("Cari Hareket Raporu")
        self.resize(780, 420)
        self.setMinimumSize(720, 380)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(
            BANK_DIALOG_STYLES
            + """
            QWidget#DialogContent {
                background-color: #0f172a;
            }

            QFrame#InfoCard {
                background-color: #111827;
                border: 1px solid #24324a;
                border-radius: 16px;
            }

            QLabel#DialogTitle {
                color: #f8fafc;
                font-size: 18px;
                font-weight: 900;
            }

            QLabel#DialogSubtitle {
                color: #94a3b8;
                font-size: 12px;
            }

            QLabel#FieldLabel {
                color: #bfdbfe;
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#InfoText {
                color: #cbd5e1;
                font-size: 12px;
            }

            QComboBox,
            QDateEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 7px 10px;
                font-size: 12px;
                min-height: 34px;
            }

            QComboBox:hover,
            QDateEdit:hover {
                border: 1px solid #475569;
            }

            QComboBox:focus,
            QDateEdit:focus {
                border: 1px solid #3b82f6;
            }

            QComboBox QAbstractItemView {
                background-color: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                outline: 0;
            }

            QPushButton#PrimaryButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 900;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #1d4ed8;
            }

            QPushButton#SecondaryButton {
                background-color: #1f2937;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 800;
            }

            QPushButton#SecondaryButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("DialogContent")

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Cari Hareket Raporu")
        title.setObjectName("DialogTitle")

        subtitle = QLabel(
            "Seçilen cari için alınan çekler, alınan çek hareketleri, yazılan çekler ve yazılan çek ödeme/iptal bilgilerini açıklamalı PDF raporu olarak üretir."
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        form_card = QFrame()
        form_card.setObjectName("InfoCard")

        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(10)
        form_layout.setColumnStretch(0, 2)
        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(2, 1)

        self.partner_combo = QComboBox()
        self.partner_combo.setMinimumHeight(38)
        self.partner_combo.currentIndexChanged.connect(self._update_partner_info)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.start_date_edit.setDate(_current_year_start())
        self.start_date_edit.setMinimumHeight(38)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.end_date_edit.setDate(_current_date())
        self.end_date_edit.setMinimumHeight(38)

        form_layout.addWidget(self._field_label("Cari"), 0, 0)
        form_layout.addWidget(self._field_label("Başlangıç"), 0, 1)
        form_layout.addWidget(self._field_label("Bitiş"), 0, 2)

        form_layout.addWidget(self.partner_combo, 1, 0)
        form_layout.addWidget(self.start_date_edit, 1, 1)
        form_layout.addWidget(self.end_date_edit, 1, 2)

        self.info_label = QLabel("")
        self.info_label.setObjectName("InfoText")
        self.info_label.setWordWrap(True)
        form_layout.addWidget(self.info_label, 2, 0, 1, 3)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Vazgeç")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self.reject)

        self.create_button = QPushButton("Cari PDF Al")
        self.create_button.setObjectName("PrimaryButton")
        self.create_button.setMinimumHeight(40)
        self.create_button.clicked.connect(self._create_report)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.create_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(form_card)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        root_layout.addWidget(content)

        self._fill_partner_combo()
        self._update_partner_info()

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _load_partner_options(self) -> list[PartnerStatementPartnerOption]:
        with session_scope() as session:
            statement = select(BusinessPartner).order_by(BusinessPartner.name.asc())
            partners = list(session.execute(statement).scalars().all())

            results: list[PartnerStatementPartnerOption] = []

            for partner in partners:
                partner_type_value = (
                    partner.partner_type.value
                    if hasattr(partner.partner_type, "value")
                    else str(partner.partner_type or "")
                ).strip().upper()

                results.append(
                    PartnerStatementPartnerOption(
                        partner_id=partner.id,
                        name=partner.name,
                        partner_type=partner_type_value,
                        partner_type_text=_partner_type_text(partner.partner_type),
                        is_active=bool(partner.is_active),
                        status_text="Aktif" if partner.is_active else "Pasif",
                    )
                )

            return results

    def _fill_partner_combo(self) -> None:
        self.partner_combo.blockSignals(True)

        try:
            self.partner_combo.clear()

            if not self.partner_options:
                self.partner_combo.addItem("Cari kart bulunamadı", None)
                self.create_button.setEnabled(False)
                return

            self.partner_combo.addItem("Cari seçiniz", None)

            for partner in self.partner_options:
                self.partner_combo.addItem(
                    f"{partner.name} / {partner.partner_type_text} / {partner.status_text}",
                    partner.partner_id,
                )
        finally:
            self.partner_combo.blockSignals(False)

    def _selected_partner_id(self) -> int | None:
        value = self.partner_combo.currentData()

        if value in {None, ""}:
            return None

        try:
            normalized_value = int(value)
        except (TypeError, ValueError):
            return None

        if normalized_value <= 0:
            return None

        return normalized_value

    def _selected_partner(self) -> PartnerStatementPartnerOption | None:
        partner_id = self._selected_partner_id()

        if partner_id is None:
            return None

        return self.partner_lookup.get(partner_id)

    def _update_partner_info(self) -> None:
        partner = self._selected_partner()

        if partner is None:
            self.info_label.setText(
                "Cari seçildiğinde rapor dönemindeki çek kayıtları ve çek hareketleri PDF olarak hazırlanır."
            )
            self.create_button.setEnabled(False)
            return

        self.info_label.setText(
            f"Seçili cari: {partner.name}\n"
            f"Tip: {partner.partner_type_text} | Durum: {partner.status_text}\n"
            "Rapor; alınan çekler, alınan çek hareketleri, yazılan çekler ve yazılan çek ödeme/iptal bilgilerini içerir."
        )
        self.create_button.setEnabled(True)

    def _validate_selection(self) -> tuple[PartnerStatementPartnerOption, date, date]:
        partner = self._selected_partner()

        if partner is None:
            raise ValueError("Cari seçilmelidir.")

        start_date = _qdate_to_date(self.start_date_edit.date())
        end_date = _qdate_to_date(self.end_date_edit.date())

        if end_date < start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz.")

        return partner, start_date, end_date

    def _create_report(self) -> None:
        try:
            partner, start_date, end_date = self._validate_selection()

            default_folder = _default_reports_folder()
            default_file_name = (
                f"Cari_Hareket_Raporu_"
                f"{_safe_file_name_text(partner.name)}_"
                f"{start_date.strftime('%Y%m%d')}_"
                f"{end_date.strftime('%Y%m%d')}.pdf"
            )
            default_file_path = default_folder / default_file_name

            selected_file_path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "Cari Hareket PDF Dosyasını Kaydet",
                str(default_file_path),
                "PDF Dosyası (*.pdf)",
            )

            if not selected_file_path:
                return

            output_path = Path(selected_file_path)

            if output_path.suffix.lower() != ".pdf":
                output_path = output_path.with_suffix(".pdf")

            created_pdf_path = create_partner_statement_report_pdf(
                output_path=output_path,
                report_filter=PartnerStatementFilter(
                    partner_id=partner.partner_id,
                    start_date=start_date,
                    end_date=end_date,
                ),
                created_by=self.created_by,
            )

            QMessageBox.information(
                self,
                "PDF Oluşturuldu",
                f"Cari Hareket Raporu başarıyla oluşturuldu:\n\n"
                f"Cari: {partner.name}\n"
                f"Dönem: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
                f"{created_pdf_path}",
            )

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(created_pdf_path)))
            self.accept()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "PDF Oluşturulamadı",
                f"Cari Hareket Raporu oluşturulurken hata oluştu:\n\n{exc}",
            )


def open_partner_statement_report_dialog(
    *,
    parent: QWidget | None,
    created_by: str,
) -> None:
    dialog = PartnerStatementReportDialog(
        parent=parent,
        created_by=created_by,
    )
    dialog.exec()

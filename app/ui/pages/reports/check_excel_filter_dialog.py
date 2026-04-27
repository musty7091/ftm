from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class CheckExcelFilterSelection:
    start_date: date
    end_date: date
    check_type: str
    status_group: str
    currency_code: str


class CheckExcelFilterDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        default_start_date: date,
        default_end_date: date,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Çek Listesi Excel Filtreleri")
        self.setMinimumWidth(560)
        self.setModal(True)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.start_date_edit.setDate(
            QDate(
                default_start_date.year,
                default_start_date.month,
                default_start_date.day,
            )
        )

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.end_date_edit.setDate(
            QDate(
                default_end_date.year,
                default_end_date.month,
                default_end_date.day,
            )
        )

        self.check_type_combo = QComboBox()
        self.check_type_combo.addItem("Tümü", "ALL")
        self.check_type_combo.addItem("Alınan Çekler", "RECEIVED")
        self.check_type_combo.addItem("Yazılan Çekler", "ISSUED")

        self.status_group_combo = QComboBox()
        self.status_group_combo.addItem("Tümü", "ALL")
        self.status_group_combo.addItem("Bekleyen", "PENDING")
        self.status_group_combo.addItem("Sonuçlanan", "CLOSED")
        self.status_group_combo.addItem("Problemli", "PROBLEM")

        self.currency_combo = QComboBox()
        self.currency_combo.addItem("Tümü", "ALL")
        self.currency_combo.addItem("TRY", "TRY")
        self.currency_combo.addItem("USD", "USD")
        self.currency_combo.addItem("EUR", "EUR")
        self.currency_combo.addItem("GBP", "GBP")

        self.selected_filters: CheckExcelFilterSelection | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        title = QLabel("Çek Listesi Excel Filtreleri")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel(
            "Excel dosyasına aktarılacak çekleri tarih, çek türü, durum ve para birimine göre filtreleyebilirsin."
        )
        subtitle.setObjectName("ReportSubTitle")
        subtitle.setWordWrap(True)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        panel = QFrame()
        panel.setObjectName("ReportFilterPanel")

        form_layout = QGridLayout(panel)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)

        form_layout.addWidget(self._field_label("Başlangıç Tarihi"), 0, 0)
        form_layout.addWidget(self.start_date_edit, 0, 1)

        form_layout.addWidget(self._field_label("Bitiş Tarihi"), 0, 2)
        form_layout.addWidget(self.end_date_edit, 0, 3)

        form_layout.addWidget(self._field_label("Çek Türü"), 1, 0)
        form_layout.addWidget(self.check_type_combo, 1, 1)

        form_layout.addWidget(self._field_label("Durum"), 1, 2)
        form_layout.addWidget(self.status_group_combo, 1, 3)

        form_layout.addWidget(self._field_label("Para Birimi"), 2, 0)
        form_layout.addWidget(self.currency_combo, 2, 1)

        main_layout.addWidget(panel)

        info = QLabel(
            "Not: Banka filtresini bir sonraki adımda ayrıca ekleyeceğiz. "
            "Çünkü banka filtresi için çek veri motorunu da genişletmemiz gerekiyor."
        )
        info.setObjectName("ReportSmallInfo")
        info.setWordWrap(True)

        main_layout.addWidget(info)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setObjectName("PlannedButton")
        cancel_button.clicked.connect(self.reject)

        ok_button = QPushButton("Excel Oluştur")
        ok_button.setObjectName("QuickReportButton")
        ok_button.clicked.connect(self._accept_filters)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)

        main_layout.addLayout(button_layout)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ReportFieldLabel")

        return label

    def _qdate_to_date(self, qdate: QDate) -> date:
        return date(qdate.year(), qdate.month(), qdate.day())

    def _accept_filters(self) -> None:
        start_date = self._qdate_to_date(self.start_date_edit.date())
        end_date = self._qdate_to_date(self.end_date_edit.date())

        if end_date < start_date:
            QMessageBox.warning(
                self,
                "Tarih Hatası",
                "Bitiş tarihi başlangıç tarihinden küçük olamaz.",
            )
            return

        self.selected_filters = CheckExcelFilterSelection(
            start_date=start_date,
            end_date=end_date,
            check_type=str(self.check_type_combo.currentData() or "ALL"),
            status_group=str(self.status_group_combo.currentData() or "ALL"),
            currency_code=str(self.currency_combo.currentData() or "ALL"),
        )

        self.accept()


def get_check_excel_filter_selection(
    parent: QWidget | None,
    *,
    default_start_date: date,
    default_end_date: date,
) -> CheckExcelFilterSelection | None:
    dialog = CheckExcelFilterDialog(
        parent,
        default_start_date=default_start_date,
        default_end_date=default_end_date,
    )

    if dialog.exec() != QDialog.Accepted:
        return None

    return dialog.selected_filters


__all__ = [
    "CheckExcelFilterSelection",
    "CheckExcelFilterDialog",
    "get_check_excel_filter_selection",
]
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
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount


@dataclass(frozen=True)
class BankMovementExcelFilterSelection:
    start_date: date
    end_date: date
    bank_id: int | None
    bank_account_id: int | None
    direction: str
    status: str
    currency_code: str
    source_type: str


@dataclass(frozen=True)
class _BankOption:
    bank_id: int
    bank_name: str


@dataclass(frozen=True)
class _BankAccountOption:
    bank_account_id: int
    bank_id: int
    bank_name: str
    account_name: str


class BankMovementExcelFilterDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        default_start_date: date,
        default_end_date: date,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Banka Hareketleri Excel Filtreleri")
        self.setMinimumWidth(680)
        self.setModal(True)

        self.bank_options: list[_BankOption] = []
        self.bank_account_options: list[_BankAccountOption] = []

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

        self.bank_combo = QComboBox()
        self.bank_account_combo = QComboBox()

        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Tümü", "ALL")
        self.direction_combo.addItem("Giriş", "IN")
        self.direction_combo.addItem("Çıkış", "OUT")

        self.status_combo = QComboBox()
        self.status_combo.addItem("Tümü", "ALL")
        self.status_combo.addItem("Planlandı", "PLANNED")
        self.status_combo.addItem("Gerçekleşti", "REALIZED")
        self.status_combo.addItem("İptal Edildi", "CANCELLED")

        self.currency_combo = QComboBox()
        self.currency_combo.addItem("Tümü", "ALL")
        self.currency_combo.addItem("TRY", "TRY")
        self.currency_combo.addItem("USD", "USD")
        self.currency_combo.addItem("EUR", "EUR")
        self.currency_combo.addItem("GBP", "GBP")

        self.source_type_combo = QComboBox()
        self.source_type_combo.addItem("Tümü", "ALL")
        self.source_type_combo.addItem("Açılış Bakiyesi", "OPENING_BALANCE")
        self.source_type_combo.addItem("Nakit Yatırma", "CASH_DEPOSIT")
        self.source_type_combo.addItem("Banka Transferi", "BANK_TRANSFER")
        self.source_type_combo.addItem("Yazılan Çek", "ISSUED_CHECK")
        self.source_type_combo.addItem("Alınan Çek", "RECEIVED_CHECK")
        self.source_type_combo.addItem("POS Yatışı", "POS_SETTLEMENT")
        self.source_type_combo.addItem("Manuel Düzeltme", "MANUAL_ADJUSTMENT")
        self.source_type_combo.addItem("Diğer", "OTHER")

        self.selected_filters: BankMovementExcelFilterSelection | None = None

        self._load_bank_options()
        self._build_ui()
        self._fill_bank_combo()
        self._fill_bank_account_combo(bank_id=None)

        self.bank_combo.currentIndexChanged.connect(self._on_bank_changed)

    def _load_bank_options(self) -> None:
        self.bank_options = []
        self.bank_account_options = []

        with session_scope() as session:
            bank_statement = select(Bank).order_by(Bank.name.asc())
            banks = session.execute(bank_statement).scalars().all()

            for bank in banks:
                self.bank_options.append(
                    _BankOption(
                        bank_id=int(bank.id),
                        bank_name=str(bank.name),
                    )
                )

            account_statement = (
                select(BankAccount, Bank)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .order_by(
                    Bank.name.asc(),
                    BankAccount.account_name.asc(),
                    BankAccount.id.asc(),
                )
            )
            account_rows = session.execute(account_statement).all()

            for bank_account, bank in account_rows:
                self.bank_account_options.append(
                    _BankAccountOption(
                        bank_account_id=int(bank_account.id),
                        bank_id=int(bank.id),
                        bank_name=str(bank.name),
                        account_name=str(bank_account.account_name),
                    )
                )

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        title = QLabel("Banka Hareketleri Excel Filtreleri")
        title.setObjectName("ReportSectionTitle")

        subtitle = QLabel(
            "Excel dosyasına aktarılacak banka hareketlerini tarih, banka, hesap, yön, durum, kaynak ve para birimine göre filtreleyebilirsin."
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

        form_layout.addWidget(self._field_label("Banka"), 1, 0)
        form_layout.addWidget(self.bank_combo, 1, 1)

        form_layout.addWidget(self._field_label("Banka Hesabı"), 1, 2)
        form_layout.addWidget(self.bank_account_combo, 1, 3)

        form_layout.addWidget(self._field_label("Yön"), 2, 0)
        form_layout.addWidget(self.direction_combo, 2, 1)

        form_layout.addWidget(self._field_label("Durum"), 2, 2)
        form_layout.addWidget(self.status_combo, 2, 3)

        form_layout.addWidget(self._field_label("Para Birimi"), 3, 0)
        form_layout.addWidget(self.currency_combo, 3, 1)

        form_layout.addWidget(self._field_label("Kaynak Türü"), 3, 2)
        form_layout.addWidget(self.source_type_combo, 3, 3)

        main_layout.addWidget(panel)

        info = QLabel(
            "Not: Banka seçersen hesap listesi sadece o bankaya ait hesaplarla daralır. "
            "Banka seçmezsen tüm hesaplar üzerinden rapor alınır."
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

    def _fill_bank_combo(self) -> None:
        self.bank_combo.clear()
        self.bank_combo.addItem("Tüm Bankalar", None)

        for bank_option in self.bank_options:
            self.bank_combo.addItem(
                bank_option.bank_name,
                bank_option.bank_id,
            )

    def _fill_bank_account_combo(self, bank_id: int | None) -> None:
        self.bank_account_combo.clear()
        self.bank_account_combo.addItem("Tüm Hesaplar", None)

        for account_option in self.bank_account_options:
            if bank_id is not None and account_option.bank_id != bank_id:
                continue

            self.bank_account_combo.addItem(
                f"{account_option.bank_name} / {account_option.account_name}",
                account_option.bank_account_id,
            )

    def _on_bank_changed(self) -> None:
        selected_bank_id = self.bank_combo.currentData()

        if selected_bank_id is None:
            self._fill_bank_account_combo(bank_id=None)
            return

        self._fill_bank_account_combo(bank_id=int(selected_bank_id))

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

        bank_id_value = self.bank_combo.currentData()
        bank_account_id_value = self.bank_account_combo.currentData()

        self.selected_filters = BankMovementExcelFilterSelection(
            start_date=start_date,
            end_date=end_date,
            bank_id=None if bank_id_value is None else int(bank_id_value),
            bank_account_id=None if bank_account_id_value is None else int(bank_account_id_value),
            direction=str(self.direction_combo.currentData() or "ALL"),
            status=str(self.status_combo.currentData() or "ALL"),
            currency_code=str(self.currency_combo.currentData() or "ALL"),
            source_type=str(self.source_type_combo.currentData() or "ALL"),
        )

        self.accept()


def get_bank_movement_excel_filter_selection(
    parent: QWidget | None,
    *,
    default_start_date: date,
    default_end_date: date,
) -> BankMovementExcelFilterSelection | None:
    dialog = BankMovementExcelFilterDialog(
        parent,
        default_start_date=default_start_date,
        default_end_date=default_end_date,
    )

    if dialog.exec() != QDialog.Accepted:
        return None

    return dialog.selected_filters


__all__ = [
    "BankMovementExcelFilterSelection",
    "BankMovementExcelFilterDialog",
    "get_bank_movement_excel_filter_selection",
]
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck
from app.models.enums import IssuedCheckStatus
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.ui_helpers import tr_money


@dataclass
class PayableIssuedCheckOption:
    issued_check_id: int
    supplier_name: str
    bank_name: str
    account_name: str
    currency_code: str
    current_balance: Decimal
    check_number: str
    amount: Decimal
    issue_date: date
    due_date: date
    status: str
    reference_no: str | None


def _format_decimal_tr(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except Exception:
        amount = Decimal("0.00")

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code == "TRY":
        return tr_money(value)

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def _issued_status_text(status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "PREPARED":
        return "Hazırlandı"

    if normalized_status == "GIVEN":
        return "Verildi"

    if normalized_status == "PAID":
        return "Ödendi"

    if normalized_status == "CANCELLED":
        return "İptal"

    if normalized_status == "RISK":
        return "Risk"

    return normalized_status


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class IssuedCheckPayDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.payable_checks = self._load_payable_checks()
        self.check_lookup = {
            payable_check.issued_check_id: payable_check
            for payable_check in self.payable_checks
        }
        self.filtered_check_ids: list[int] = []
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Yazılan Çek Ödendi")
        self.resize(1060, 720)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(BANK_DIALOG_STYLES)
        self.setSizeGripEnabled(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Yazılan Çek Ödendi")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Açık durumdaki yazılan çeki ödeme işlemine çevirir. "
            "Arama ve vade filtresiyle kaydı hızlı bulabilir, satır seçerek ödeme işlemini tamamlayabilirsin."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(40)
        self.search_input.setPlaceholderText("Tedarikçi / çek no / referans / banka / hesap ara")
        self.search_input.textChanged.connect(self._apply_filters)

        self.due_filter_combo = QComboBox()
        self.due_filter_combo.setMinimumHeight(40)
        self.due_filter_combo.addItem("Gecikenler + 7 Gün İçinde", "OVERDUE_AND_NEXT_7_DAYS")
        self.due_filter_combo.addItem("Gecikenler", "OVERDUE")
        self.due_filter_combo.addItem("Bugün Vadeli", "TODAY")
        self.due_filter_combo.addItem("7 Gün İçinde", "NEXT_7_DAYS")
        self.due_filter_combo.addItem("30 Gün İçinde", "NEXT_30_DAYS")
        self.due_filter_combo.addItem("Tümü", "ALL")
        self.due_filter_combo.currentIndexChanged.connect(self._apply_filters)

        filter_layout.addWidget(self.search_input, 3)
        filter_layout.addWidget(self.due_filter_combo, 1)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(8)
        self.checks_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Tedarikçi",
                "Çek No",
                "Keşide",
                "Vade",
                "Tutar",
                "Banka / Hesap",
                "Bakiye",
            ]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setAlternatingRowColors(False)
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.setMinimumHeight(250)
        self.checks_table.setWordWrap(False)
        self.checks_table.setTextElideMode(Qt.ElideRight)
        self.checks_table.verticalHeader().setDefaultSectionSize(34)
        self.checks_table.verticalHeader().setMinimumSectionSize(30)
        self.checks_table.itemSelectionChanged.connect(self._update_selected_check_info)

        checks_header = self.checks_table.horizontalHeader()
        checks_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(6, QHeaderView.Stretch)
        checks_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)
        form_layout.addRow("Seçili çek", self.info_label)

        self.balance_warning_label = QLabel("")
        self.balance_warning_label.setObjectName("MutedText")
        self.balance_warning_label.setWordWrap(True)
        form_layout.addRow("", self.balance_warning_label)

        self.payment_date_edit = QDateEdit()
        self.payment_date_edit.setMinimumHeight(38)
        self.payment_date_edit.setCalendarPopup(True)
        self.payment_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.payment_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Ödeme tarihi", self.payment_date_edit)

        self.reference_no_combo = QComboBox()
        self.reference_no_combo.setEditable(True)
        self.reference_no_combo.setMinimumHeight(38)
        self.reference_no_combo.setInsertPolicy(QComboBox.NoInsert)
        form_layout.addRow("Referans no", self.reference_no_combo)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(88)
        form_layout.addRow("Açıklama", self.description_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("Ödemeyi Kaydet")
        self.cancel_button = QPushButton("Vazgeç")

        self.save_button.setMinimumHeight(40)
        self.cancel_button.setMinimumHeight(40)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(4)
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.results_info_label)
        main_layout.addWidget(self.checks_table)
        main_layout.addSpacing(4)
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(8)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._apply_filters()

    def _load_payable_checks(self) -> list[PayableIssuedCheckOption]:
        with session_scope() as session:
            statement = (
                select(IssuedCheck, BusinessPartner, BankAccount, Bank)
                .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
                .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .where(
                    IssuedCheck.status.in_(
                        [
                            IssuedCheckStatus.PREPARED,
                            IssuedCheckStatus.GIVEN,
                            IssuedCheckStatus.RISK,
                        ]
                    ),
                    IssuedCheck.paid_transaction_id.is_(None),
                    BankAccount.is_active.is_(True),
                    Bank.is_active.is_(True),
                )
                .order_by(IssuedCheck.due_date.asc(), IssuedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            results: list[PayableIssuedCheckOption] = []

            for issued_check, supplier, bank_account, bank in rows:
                balance_summary = get_bank_account_balance_summary(
                    session,
                    bank_account_id=bank_account.id,
                )

                currency_code = (
                    bank_account.currency_code.value
                    if hasattr(bank_account.currency_code, "value")
                    else str(bank_account.currency_code)
                )

                status_value = (
                    issued_check.status.value
                    if hasattr(issued_check.status, "value")
                    else str(issued_check.status)
                )

                results.append(
                    PayableIssuedCheckOption(
                        issued_check_id=issued_check.id,
                        supplier_name=supplier.name,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=currency_code,
                        current_balance=Decimal(str(balance_summary["current_balance"])),
                        check_number=issued_check.check_number,
                        amount=Decimal(str(issued_check.amount)),
                        issue_date=issued_check.issue_date,
                        due_date=issued_check.due_date,
                        status=status_value,
                        reference_no=issued_check.reference_no,
                    )
                )

            return results

    def has_payable_checks(self) -> bool:
        return bool(self.payable_checks)

    def get_missing_data_message(self) -> str:
        return "Ödeme yapılabilecek açık durumdaki yazılan çek kaydı bulunamadı."

    def _matches_search(self, payable_check: PayableIssuedCheckOption, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        searchable_text = " | ".join(
            [
                str(payable_check.issued_check_id),
                payable_check.supplier_name,
                payable_check.check_number,
                payable_check.reference_no or "",
                payable_check.bank_name,
                payable_check.account_name,
                payable_check.issue_date.strftime("%d.%m.%Y"),
                payable_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(payable_check.amount, payable_check.currency_code),
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _matches_due_filter(self, payable_check: PayableIssuedCheckOption, filter_key: str) -> bool:
        today = date.today()
        due_date = payable_check.due_date

        if filter_key == "OVERDUE_AND_NEXT_7_DAYS":
            return due_date < today or due_date <= today + timedelta(days=7)

        if filter_key == "OVERDUE":
            return due_date < today

        if filter_key == "TODAY":
            return due_date == today

        if filter_key == "NEXT_7_DAYS":
            return today <= due_date <= today + timedelta(days=7)

        if filter_key == "NEXT_30_DAYS":
            return today <= due_date <= today + timedelta(days=30)

        return True

    def _apply_filters(self) -> None:
        search_text = self.search_input.text().strip()
        filter_key = str(self.due_filter_combo.currentData() or "ALL").strip().upper()

        filtered_checks = [
            payable_check
            for payable_check in self.payable_checks
            if self._matches_search(payable_check, search_text)
            and self._matches_due_filter(payable_check, filter_key)
        ]

        filtered_checks.sort(
            key=lambda payable_check: (
                payable_check.due_date,
                payable_check.supplier_name.lower(),
                payable_check.check_number.lower(),
                payable_check.issued_check_id,
            )
        )

        self.filtered_check_ids = [payable_check.issued_check_id for payable_check in filtered_checks]

        self._fill_table(filtered_checks)
        self._update_results_info_label(len(filtered_checks))
        self._select_first_row_if_available()
        self._update_selected_check_info()

    def _fill_table(self, filtered_checks: list[PayableIssuedCheckOption]) -> None:
        self.checks_table.setRowCount(len(filtered_checks))

        today = date.today()

        for row_index, payable_check in enumerate(filtered_checks):
            values = [
                str(payable_check.issued_check_id),
                payable_check.supplier_name,
                payable_check.check_number,
                payable_check.issue_date.strftime("%d.%m.%Y"),
                payable_check.due_date.strftime("%d.%m.%Y"),
                _format_currency_amount(payable_check.amount, payable_check.currency_code),
                f"{payable_check.bank_name} / {payable_check.account_name}",
                _format_currency_amount(payable_check.current_balance, payable_check.currency_code),
            ]

            is_overdue = payable_check.due_date < today
            is_due_soon = today <= payable_check.due_date <= today + timedelta(days=7)
            has_balance_problem = payable_check.current_balance < payable_check.amount

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if is_overdue:
                    item.setForeground(QColor("#f59e0b"))
                elif has_balance_problem:
                    item.setForeground(QColor("#f87171"))
                elif is_due_soon:
                    item.setForeground(QColor("#38bdf8"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index in {5, 7}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 0:
                    item.setData(Qt.UserRole, payable_check.issued_check_id)

                tooltip_lines = [
                    f"ID: {payable_check.issued_check_id}",
                    f"Tedarikçi: {payable_check.supplier_name}",
                    f"Çek No: {payable_check.check_number}",
                    f"Durum: {_issued_status_text(payable_check.status)}",
                    f"Keşide: {payable_check.issue_date.strftime('%d.%m.%Y')}",
                    f"Vade: {payable_check.due_date.strftime('%d.%m.%Y')}",
                    f"Tutar: {_format_currency_amount(payable_check.amount, payable_check.currency_code)}",
                    f"Banka / Hesap: {payable_check.bank_name} / {payable_check.account_name}",
                    f"Güncel Bakiye: {_format_currency_amount(payable_check.current_balance, payable_check.currency_code)}",
                ]

                if payable_check.reference_no:
                    tooltip_lines.append(f"Referans No: {payable_check.reference_no}")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        self.checks_table.resizeRowsToContents()

    def _update_results_info_label(self, filtered_count: int) -> None:
        total_count = len(self.payable_checks)

        if total_count == 0:
            self.results_info_label.setText("Ödeme yapılabilecek açık yazılan çek kaydı bulunamadı.")
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Filtreye uygun kayıt bulunamadı. Arama metnini veya vade filtresini değiştir."
            )
            return

        self.results_info_label.setText(
            f"Toplam {total_count} açık çek içinden {filtered_count} kayıt listeleniyor. "
            "Liste vade tarihine göre sıralıdır."
        )

    def _select_first_row_if_available(self) -> None:
        if self.checks_table.rowCount() <= 0:
            self.checks_table.clearSelection()
            return

        self.checks_table.setCurrentCell(0, 0)
        self.checks_table.selectRow(0)

    def _selected_check_from_table(self) -> PayableIssuedCheckOption | None:
        current_row = self.checks_table.currentRow()

        if current_row < 0:
            return None

        id_item = self.checks_table.item(current_row, 0)

        if id_item is None:
            return None

        issued_check_id = id_item.data(Qt.UserRole)

        try:
            normalized_issued_check_id = int(issued_check_id)
        except (TypeError, ValueError):
            return None

        return self.check_lookup.get(normalized_issued_check_id)

    def _update_selected_check_info(self) -> None:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            self.info_label.setText("Ödeme için önce listeden bir çek seçmelisin.")
            self.balance_warning_label.setText("")
            self.reference_no_combo.clear()
            self.save_button.setEnabled(False)
            return

        self.info_label.setText(
            f"Tedarikçi: {selected_check.supplier_name}\n"
            f"Banka / Hesap: {selected_check.bank_name} / {selected_check.account_name}\n"
            f"Durum: {_issued_status_text(selected_check.status)}\n"
            f"Keşide: {selected_check.issue_date.strftime('%d.%m.%Y')} | "
            f"Vade: {selected_check.due_date.strftime('%d.%m.%Y')}\n"
            f"Çek tutarı: {_format_currency_amount(selected_check.amount, selected_check.currency_code)}\n"
            f"Güncel hesap bakiyesi: {_format_currency_amount(selected_check.current_balance, selected_check.currency_code)}"
        )

        if selected_check.current_balance < selected_check.amount:
            self.balance_warning_label.setText(
                "Uyarı: Seçili banka hesabının güncel bakiyesi çek tutarını karşılamıyor. "
                "Bu durumda servis katmanı ödeme işlemini reddedecektir."
            )
        else:
            self.balance_warning_label.setText(
                "Bakiye kontrolü olumlu görünüyor. Son karar yine servis katmanındaki gerçek bakiyeye göre verilir."
            )

        self.reference_no_combo.clear()

        if selected_check.reference_no:
            self.reference_no_combo.addItem(selected_check.reference_no)

        self.reference_no_combo.setEditText(selected_check.reference_no or "")
        self.save_button.setEnabled(True)

    def _build_payload(self) -> dict[str, Any]:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            raise ValueError("Ödeme yapılacak çek seçilmelidir.")

        payment_date = _qdate_to_date(self.payment_date_edit.date())
        reference_no = self.reference_no_combo.currentText().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "issued_check_id": selected_check.issued_check_id,
            "payment_date": payment_date,
            "reference_no": reference_no or None,
            "description": description or None,
        }

    def accept(self) -> None:
        try:
            self.payload = self._build_payload()
        except Exception as exc:
            QMessageBox.warning(self, "Eksik veya hatalı bilgi", str(exc))
            return

        super().accept()

    def get_payload(self) -> dict[str, Any]:
        if self.payload is None:
            self.payload = self._build_payload()

        return self.payload
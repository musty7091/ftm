from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
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
)
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck
from app.models.enums import IssuedCheckStatus
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import format_currency_amount, issued_status_text


@dataclass
class CancellableIssuedCheckOption:
    issued_check_id: int
    supplier_name: str
    bank_name: str
    bank_account_name: str
    check_number: str
    issue_date: date
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None


class IssuedCheckCancelDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.cancellable_checks = self._load_cancellable_checks()
        self.check_lookup = {
            cancellable_check.issued_check_id: cancellable_check
            for cancellable_check in self.cancellable_checks
        }

        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Yazılan Çek İptal Et")
        self.resize(1080, 720)
        self.setMinimumSize(920, 620)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(
            BANK_DIALOG_STYLES
            + """
            QScrollArea {
                background-color: #0f172a;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background-color: #0f172a;
            }

            QWidget#DialogContent {
                background-color: #0f172a;
            }

            QTableWidget {
                background-color: #0b1220;
                color: #e5e7eb;
                border: 1px solid #1e293b;
                border-radius: 12px;
                gridline-color: #1e293b;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }

            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #1e293b;
            }

            QHeaderView::section {
                background-color: #1e293b;
                color: #e5e7eb;
                border: none;
                padding: 8px;
                font-weight: 700;
            }
            """
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content_widget = QWidget()
        content_widget.setObjectName("DialogContent")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Yazılan Çek İptal Et")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Ödenmemiş ve banka hareketi oluşmamış yazılan çekleri iptal edebilirsin. "
            "Ödenmiş çek iptal edilmez; bunun için ileride ters kayıt / geri alma mantığı ayrıca kurulacak."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(40)
        self.search_input.setPlaceholderText("Tedarikçi / çek no / banka / referans ara")
        self.search_input.textChanged.connect(self._apply_filters)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(8)
        self.checks_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Tedarikçi",
                "Banka / Hesap",
                "Çek No",
                "Keşide",
                "Vade",
                "Tutar",
                "Durum",
            ]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setAlternatingRowColors(False)
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.setMinimumHeight(280)
        self.checks_table.setWordWrap(False)
        self.checks_table.setTextElideMode(Qt.ElideRight)
        self.checks_table.verticalHeader().setDefaultSectionSize(34)
        self.checks_table.verticalHeader().setMinimumSectionSize(30)
        self.checks_table.itemSelectionChanged.connect(self._update_selected_check_info)

        checks_header = self.checks_table.horizontalHeader()
        checks_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(2, QHeaderView.Stretch)
        checks_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
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

        self.cancel_reason_input = QTextEdit()
        self.cancel_reason_input.setPlaceholderText("İptal nedenini yazınız. Örn: Çek kullanılmadı, hatalı düzenlendi, mükerrer kayıt vb.")
        self.cancel_reason_input.setFixedHeight(110)
        form_layout.addRow("İptal nedeni", self.cancel_reason_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("Çeki İptal Et")
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
        main_layout.addWidget(self.search_input)
        main_layout.addWidget(self.results_info_label)
        main_layout.addWidget(self.checks_table)
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(8)
        main_layout.addLayout(button_layout)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        self._apply_filters()

    def _load_cancellable_checks(self) -> list[CancellableIssuedCheckOption]:
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
                )
                .order_by(IssuedCheck.due_date.asc(), IssuedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            results: list[CancellableIssuedCheckOption] = []

            for issued_check, supplier, bank_account, bank in rows:
                currency_code = (
                    issued_check.currency_code.value
                    if hasattr(issued_check.currency_code, "value")
                    else str(issued_check.currency_code)
                )

                status_value = (
                    issued_check.status.value
                    if hasattr(issued_check.status, "value")
                    else str(issued_check.status)
                )

                results.append(
                    CancellableIssuedCheckOption(
                        issued_check_id=issued_check.id,
                        supplier_name=supplier.name,
                        bank_name=bank.name,
                        bank_account_name=bank_account.account_name,
                        check_number=issued_check.check_number,
                        issue_date=issued_check.issue_date,
                        due_date=issued_check.due_date,
                        amount=Decimal(str(issued_check.amount)),
                        currency_code=currency_code,
                        status=status_value,
                        reference_no=issued_check.reference_no,
                        description=issued_check.description,
                    )
                )

            return results

    def has_cancellable_checks(self) -> bool:
        return bool(self.cancellable_checks)

    def get_missing_data_message(self) -> str:
        return "İptal edilebilir durumda yazılan çek kaydı bulunamadı."

    def _matches_search(self, cancellable_check: CancellableIssuedCheckOption, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        searchable_text = " | ".join(
            [
                str(cancellable_check.issued_check_id),
                cancellable_check.supplier_name,
                cancellable_check.bank_name,
                cancellable_check.bank_account_name,
                cancellable_check.check_number,
                cancellable_check.issue_date.strftime("%d.%m.%Y"),
                cancellable_check.due_date.strftime("%d.%m.%Y"),
                format_currency_amount(cancellable_check.amount, cancellable_check.currency_code),
                issued_status_text(cancellable_check.status),
                cancellable_check.reference_no or "",
                cancellable_check.description or "",
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _apply_filters(self) -> None:
        search_text = self.search_input.text().strip()

        filtered_checks = [
            cancellable_check
            for cancellable_check in self.cancellable_checks
            if self._matches_search(cancellable_check, search_text)
        ]

        filtered_checks.sort(
            key=lambda cancellable_check: (
                cancellable_check.due_date,
                cancellable_check.supplier_name.lower(),
                cancellable_check.check_number.lower(),
                cancellable_check.issued_check_id,
            )
        )

        self._fill_table(filtered_checks)
        self._update_results_info_label(len(filtered_checks))
        self._select_first_row_if_available()
        self._update_selected_check_info()

    def _fill_table(self, filtered_checks: list[CancellableIssuedCheckOption]) -> None:
        self.checks_table.setRowCount(len(filtered_checks))

        today = date.today()

        for row_index, cancellable_check in enumerate(filtered_checks):
            bank_account_text = f"{cancellable_check.bank_name} / {cancellable_check.bank_account_name}"

            values = [
                str(cancellable_check.issued_check_id),
                cancellable_check.supplier_name,
                bank_account_text,
                cancellable_check.check_number,
                cancellable_check.issue_date.strftime("%d.%m.%Y"),
                cancellable_check.due_date.strftime("%d.%m.%Y"),
                format_currency_amount(cancellable_check.amount, cancellable_check.currency_code),
                issued_status_text(cancellable_check.status),
            ]

            is_overdue = cancellable_check.due_date < today
            is_due_soon = today <= cancellable_check.due_date <= today + timedelta(days=7)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 0:
                    item.setData(Qt.UserRole, cancellable_check.issued_check_id)

                if cancellable_check.status == "RISK":
                    item.setForeground(QColor("#fbbf24"))
                elif is_overdue:
                    item.setForeground(QColor("#f59e0b"))
                elif is_due_soon:
                    item.setForeground(QColor("#38bdf8"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 6:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                tooltip_lines = [
                    f"ID: {cancellable_check.issued_check_id}",
                    f"Tedarikçi: {cancellable_check.supplier_name}",
                    f"Banka / Hesap: {bank_account_text}",
                    f"Çek No: {cancellable_check.check_number}",
                    f"Durum: {issued_status_text(cancellable_check.status)}",
                    f"Keşide: {cancellable_check.issue_date.strftime('%d.%m.%Y')}",
                    f"Vade: {cancellable_check.due_date.strftime('%d.%m.%Y')}",
                    f"Tutar: {format_currency_amount(cancellable_check.amount, cancellable_check.currency_code)}",
                ]

                if cancellable_check.reference_no:
                    tooltip_lines.append(f"Referans No: {cancellable_check.reference_no}")

                if cancellable_check.description:
                    tooltip_lines.append(f"Açıklama: {cancellable_check.description}")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        self.checks_table.resizeRowsToContents()

    def _update_results_info_label(self, filtered_count: int) -> None:
        total_count = len(self.cancellable_checks)

        if total_count == 0:
            self.results_info_label.setText("İptal edilebilir durumda yazılan çek kaydı bulunamadı.")
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Filtreye uygun kayıt bulunamadı. Arama metnini değiştir."
            )
            return

        self.results_info_label.setText(
            f"Toplam {total_count} iptal edilebilir yazılan çek içinden {filtered_count} kayıt listeleniyor. "
            "Liste vade tarihine göre sıralıdır."
        )

    def _select_first_row_if_available(self) -> None:
        if self.checks_table.rowCount() <= 0:
            self.checks_table.clearSelection()
            return

        self.checks_table.setCurrentCell(0, 0)
        self.checks_table.selectRow(0)

    def _selected_check_from_table(self) -> CancellableIssuedCheckOption | None:
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
            self.info_label.setText("İptal için önce listeden bir yazılan çek seçmelisin.")
            self.save_button.setEnabled(False)
            return

        self.info_label.setText(
            f"Tedarikçi: {selected_check.supplier_name}\n"
            f"Banka / Hesap: {selected_check.bank_name} / {selected_check.bank_account_name}\n"
            f"Çek No: {selected_check.check_number}\n"
            f"Durum: {issued_status_text(selected_check.status)}\n"
            f"Keşide: {selected_check.issue_date.strftime('%d.%m.%Y')} | "
            f"Vade: {selected_check.due_date.strftime('%d.%m.%Y')}\n"
            f"Çek tutarı: {format_currency_amount(selected_check.amount, selected_check.currency_code)}"
        )

        self.save_button.setEnabled(True)

    def _build_payload(self) -> dict[str, Any]:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            raise ValueError("İptal edilecek yazılan çek seçilmelidir.")

        cancel_reason = self.cancel_reason_input.toPlainText().strip()

        if not cancel_reason:
            raise ValueError("İptal nedeni boş olamaz.")

        if len(cancel_reason) < 5:
            raise ValueError("İptal nedeni en az 5 karakter olmalıdır.")

        return {
            "issued_check_id": selected_check.issued_check_id,
            "cancel_reason": cancel_reason,
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
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDateEdit,
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
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import ReceivedCheck
from app.models.enums import ReceivedCheckStatus
from app.ui.pages.banks.bank_dialog_styles import BANK_DIALOG_STYLES
from app.ui.pages.checks.checks_data import format_currency_amount, received_status_text


@dataclass
class BounceableReceivedCheckOption:
    received_check_id: int
    customer_name: str
    drawer_bank_name: str
    collection_bank_name: str | None
    collection_bank_account_name: str | None
    check_number: str
    received_date: date
    due_date: date
    amount: Decimal
    currency_code: str
    status: str
    reference_no: str | None
    description: str | None


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


class ReceivedCheckBounceDialog(QDialog):
    def __init__(self, *, parent: QWidget | None) -> None:
        super().__init__(parent)

        self.bounceable_checks = self._load_bounceable_checks()
        self.check_lookup = {
            bounceable_check.received_check_id: bounceable_check
            for bounceable_check in self.bounceable_checks
        }

        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Alınan Çeki Karşılıksız İşaretle")
        self.resize(1120, 760)
        self.setMinimumSize(940, 640)
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

        title = QLabel("Alınan Çeki Karşılıksız İşaretle")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Portföyde, bankaya verilmiş veya tahsilde olan alınan çekleri karşılıksız olarak işaretleyebilirsin. "
            "Tahsil edilmiş, ciro edilmiş, iskonto edilmiş, iade edilmiş veya iptal edilmiş çekler bu listede görünmez."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(40)
        self.search_input.setPlaceholderText("Müşteri / çek no / banka / referans ara")
        self.search_input.textChanged.connect(self._apply_filters)

        self.results_info_label = QLabel("")
        self.results_info_label.setObjectName("MutedText")
        self.results_info_label.setWordWrap(True)

        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(9)
        self.checks_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Müşteri",
                "Keşideci Banka",
                "Tahsil Hesabı",
                "Çek No",
                "Alınış",
                "Vade",
                "Tutar",
                "Durum",
            ]
        )
        self.checks_table.verticalHeader().setVisible(False)
        self.checks_table.setAlternatingRowColors(False)
        self.checks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.checks_table.setMinimumHeight(300)
        self.checks_table.setWordWrap(False)
        self.checks_table.setTextElideMode(Qt.ElideRight)
        self.checks_table.verticalHeader().setDefaultSectionSize(34)
        self.checks_table.verticalHeader().setMinimumSectionSize(30)
        self.checks_table.itemSelectionChanged.connect(self._update_selected_check_info)

        checks_header = self.checks_table.horizontalHeader()
        checks_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(3, QHeaderView.Stretch)
        checks_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        checks_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.info_label = QLabel("")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)
        form_layout.addRow("Seçili çek", self.info_label)

        self.bounce_date_edit = QDateEdit()
        self.bounce_date_edit.setMinimumHeight(38)
        self.bounce_date_edit.setCalendarPopup(True)
        self.bounce_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.bounce_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Karşılıksız tarihi", self.bounce_date_edit)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(38)
        self.reference_no_input.setPlaceholderText("İsteğe bağlı referans no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Açıklama yazınız. Örn: Bankadan karşılıksız bilgisi geldi, müşteriyle görüşülecek vb."
        )
        self.description_input.setFixedHeight(110)
        form_layout.addRow("Açıklama", self.description_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("Karşılıksız İşaretle")
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

    def _load_bounceable_checks(self) -> list[BounceableReceivedCheckOption]:
        with session_scope() as session:
            collection_bank_account_alias = aliased(BankAccount)
            collection_bank_alias = aliased(Bank)

            statement = (
                select(
                    ReceivedCheck,
                    BusinessPartner,
                    collection_bank_account_alias,
                    collection_bank_alias,
                )
                .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
                .outerjoin(
                    collection_bank_account_alias,
                    ReceivedCheck.collection_bank_account_id == collection_bank_account_alias.id,
                )
                .outerjoin(
                    collection_bank_alias,
                    collection_bank_account_alias.bank_id == collection_bank_alias.id,
                )
                .where(
                    ReceivedCheck.status.in_(
                        [
                            ReceivedCheckStatus.PORTFOLIO,
                            ReceivedCheckStatus.GIVEN_TO_BANK,
                            ReceivedCheckStatus.IN_COLLECTION,
                        ]
                    ),
                    ReceivedCheck.collected_transaction_id.is_(None),
                )
                .order_by(ReceivedCheck.due_date.asc(), ReceivedCheck.id.asc())
            )

            rows = session.execute(statement).all()

            results: list[BounceableReceivedCheckOption] = []

            for received_check, customer, collection_bank_account, collection_bank in rows:
                currency_code = (
                    received_check.currency_code.value
                    if hasattr(received_check.currency_code, "value")
                    else str(received_check.currency_code)
                )

                status_value = (
                    received_check.status.value
                    if hasattr(received_check.status, "value")
                    else str(received_check.status)
                )

                results.append(
                    BounceableReceivedCheckOption(
                        received_check_id=received_check.id,
                        customer_name=customer.name,
                        drawer_bank_name=received_check.drawer_bank_name,
                        collection_bank_name=collection_bank.name if collection_bank else None,
                        collection_bank_account_name=(
                            collection_bank_account.account_name if collection_bank_account else None
                        ),
                        check_number=received_check.check_number,
                        received_date=received_check.received_date,
                        due_date=received_check.due_date,
                        amount=Decimal(str(received_check.amount)),
                        currency_code=currency_code,
                        status=status_value,
                        reference_no=received_check.reference_no,
                        description=received_check.description,
                    )
                )

            return results

    def has_bounceable_checks(self) -> bool:
        return bool(self.bounceable_checks)

    def get_missing_data_message(self) -> str:
        return "Karşılıksız işaretlenebilecek açık alınan çek kaydı bulunamadı."

    def _matches_search(self, bounceable_check: BounceableReceivedCheckOption, search_text: str) -> bool:
        if not search_text:
            return True

        normalized_search_text = search_text.strip().lower()

        collection_text = (
            f"{bounceable_check.collection_bank_name} / {bounceable_check.collection_bank_account_name}"
            if bounceable_check.collection_bank_name and bounceable_check.collection_bank_account_name
            else ""
        )

        searchable_text = " | ".join(
            [
                str(bounceable_check.received_check_id),
                bounceable_check.customer_name,
                bounceable_check.drawer_bank_name,
                collection_text,
                bounceable_check.check_number,
                bounceable_check.received_date.strftime("%d.%m.%Y"),
                bounceable_check.due_date.strftime("%d.%m.%Y"),
                format_currency_amount(bounceable_check.amount, bounceable_check.currency_code),
                received_status_text(bounceable_check.status),
                bounceable_check.reference_no or "",
                bounceable_check.description or "",
            ]
        ).lower()

        return normalized_search_text in searchable_text

    def _apply_filters(self) -> None:
        search_text = self.search_input.text().strip()

        filtered_checks = [
            bounceable_check
            for bounceable_check in self.bounceable_checks
            if self._matches_search(bounceable_check, search_text)
        ]

        filtered_checks.sort(
            key=lambda bounceable_check: (
                bounceable_check.due_date,
                bounceable_check.customer_name.lower(),
                bounceable_check.check_number.lower(),
                bounceable_check.received_check_id,
            )
        )

        self._fill_table(filtered_checks)
        self._update_results_info_label(len(filtered_checks))
        self._select_first_row_if_available()
        self._update_selected_check_info()

    def _fill_table(self, filtered_checks: list[BounceableReceivedCheckOption]) -> None:
        self.checks_table.setRowCount(len(filtered_checks))

        today = date.today()

        for row_index, bounceable_check in enumerate(filtered_checks):
            collection_text = (
                f"{bounceable_check.collection_bank_name} / {bounceable_check.collection_bank_account_name}"
                if bounceable_check.collection_bank_name and bounceable_check.collection_bank_account_name
                else "-"
            )

            values = [
                str(bounceable_check.received_check_id),
                bounceable_check.customer_name,
                bounceable_check.drawer_bank_name,
                collection_text,
                bounceable_check.check_number,
                bounceable_check.received_date.strftime("%d.%m.%Y"),
                bounceable_check.due_date.strftime("%d.%m.%Y"),
                format_currency_amount(bounceable_check.amount, bounceable_check.currency_code),
                received_status_text(bounceable_check.status),
            ]

            is_overdue = bounceable_check.due_date < today
            is_due_soon = today <= bounceable_check.due_date <= today + timedelta(days=7)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column_index == 0:
                    item.setData(Qt.UserRole, bounceable_check.received_check_id)

                if is_overdue:
                    item.setForeground(QColor("#f59e0b"))
                elif is_due_soon:
                    item.setForeground(QColor("#38bdf8"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 7:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                tooltip_lines = [
                    f"ID: {bounceable_check.received_check_id}",
                    f"Müşteri: {bounceable_check.customer_name}",
                    f"Keşideci Banka: {bounceable_check.drawer_bank_name}",
                    f"Tahsil Hesabı: {collection_text}",
                    f"Çek No: {bounceable_check.check_number}",
                    f"Durum: {received_status_text(bounceable_check.status)}",
                    f"Alınış: {bounceable_check.received_date.strftime('%d.%m.%Y')}",
                    f"Vade: {bounceable_check.due_date.strftime('%d.%m.%Y')}",
                    f"Tutar: {format_currency_amount(bounceable_check.amount, bounceable_check.currency_code)}",
                ]

                if bounceable_check.reference_no:
                    tooltip_lines.append(f"Referans No: {bounceable_check.reference_no}")

                if bounceable_check.description:
                    tooltip_lines.append(f"Açıklama: {bounceable_check.description}")

                item.setToolTip("\n".join(tooltip_lines))
                self.checks_table.setItem(row_index, column_index, item)

        self.checks_table.resizeRowsToContents()

    def _update_results_info_label(self, filtered_count: int) -> None:
        total_count = len(self.bounceable_checks)

        if total_count == 0:
            self.results_info_label.setText(
                "Karşılıksız işaretlenebilecek açık alınan çek kaydı bulunamadı."
            )
            return

        if filtered_count == 0:
            self.results_info_label.setText(
                "Filtreye uygun kayıt bulunamadı. Arama metnini değiştir."
            )
            return

        self.results_info_label.setText(
            f"Toplam {total_count} uygun alınan çek içinden {filtered_count} kayıt listeleniyor. "
            "Liste vade tarihine göre sıralıdır."
        )

    def _select_first_row_if_available(self) -> None:
        if self.checks_table.rowCount() <= 0:
            self.checks_table.clearSelection()
            return

        self.checks_table.setCurrentCell(0, 0)
        self.checks_table.selectRow(0)

    def _selected_check_from_table(self) -> BounceableReceivedCheckOption | None:
        current_row = self.checks_table.currentRow()

        if current_row < 0:
            return None

        id_item = self.checks_table.item(current_row, 0)

        if id_item is None:
            return None

        received_check_id = id_item.data(Qt.UserRole)

        try:
            normalized_received_check_id = int(received_check_id)
        except (TypeError, ValueError):
            return None

        return self.check_lookup.get(normalized_received_check_id)

    def _update_selected_check_info(self) -> None:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            self.info_label.setText("Karşılıksız işaretlemek için önce listeden bir alınan çek seçmelisin.")
            self.save_button.setEnabled(False)
            return

        collection_text = (
            f"{selected_check.collection_bank_name} / {selected_check.collection_bank_account_name}"
            if selected_check.collection_bank_name and selected_check.collection_bank_account_name
            else "-"
        )

        self.info_label.setText(
            f"Müşteri: {selected_check.customer_name}\n"
            f"Keşideci Banka: {selected_check.drawer_bank_name}\n"
            f"Tahsil Hesabı: {collection_text}\n"
            f"Çek No: {selected_check.check_number}\n"
            f"Durum: {received_status_text(selected_check.status)}\n"
            f"Alınış: {selected_check.received_date.strftime('%d.%m.%Y')} | "
            f"Vade: {selected_check.due_date.strftime('%d.%m.%Y')}\n"
            f"Çek tutarı: {format_currency_amount(selected_check.amount, selected_check.currency_code)}"
        )

        if selected_check.reference_no and not self.reference_no_input.text().strip():
            self.reference_no_input.setText(selected_check.reference_no)

        self.save_button.setEnabled(True)

    def _build_payload(self) -> dict[str, Any]:
        selected_check = self._selected_check_from_table()

        if selected_check is None:
            raise ValueError("Karşılıksız işaretlenecek alınan çek seçilmelidir.")

        bounce_date = _qdate_to_date(self.bounce_date_edit.date())
        reference_no = self.reference_no_input.text().strip()
        description = self.description_input.toPlainText().strip()

        if not description:
            raise ValueError("Açıklama boş olamaz.")

        if len(description) < 5:
            raise ValueError("Açıklama en az 5 karakter olmalıdır.")

        return {
            "received_check_id": selected_check.received_check_id,
            "bounce_date": bounce_date,
            "reference_no": reference_no or None,
            "description": description,
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
from dataclasses import dataclass
from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.enums import BankTransactionStatus, FinancialSourceType, TransactionDirection
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    create_bank_transaction,
    get_bank_account_balance_summary,
)
from app.ui.components.info_card import InfoCard
from app.ui.components.summary_card import SummaryCard
from app.ui.ui_helpers import clear_layout, decimal_or_zero, tr_money, tr_number
from app.utils.decimal_utils import money


@dataclass
class BankAccountRow:
    bank_id: int
    bank_account_id: int
    bank_name: str
    account_name: str
    currency_code: str
    opening_balance: Any
    incoming_total: Any
    outgoing_total: Any
    current_balance: Any
    is_active: bool


@dataclass
class BanksPageData:
    bank_accounts: list[BankAccountRow]
    total_try_balance: Any
    active_account_count: int
    error_message: str | None = None


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


def _format_currency_amount(value: Any, currency_code: str) -> str:
    if currency_code == "TRY":
        return tr_money(value)

    return f"{value} {currency_code}"


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def load_banks_page_data() -> BanksPageData:
    try:
        with session_scope() as session:
            statement = (
                select(BankAccount, Bank)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .order_by(Bank.name, BankAccount.account_name)
            )

            rows = session.execute(statement).all()

            bank_accounts: list[BankAccountRow] = []
            total_try_balance = decimal_or_zero("0.00")
            active_account_count = 0

            for bank_account, bank in rows:
                summary = get_bank_account_balance_summary(
                    session,
                    bank_account_id=bank_account.id,
                )

                current_balance = decimal_or_zero(summary["current_balance"])

                if bank_account.is_active:
                    active_account_count += 1

                if summary["currency_code"] == "TRY" and bank_account.is_active:
                    total_try_balance += current_balance

                bank_accounts.append(
                    BankAccountRow(
                        bank_id=bank.id,
                        bank_account_id=bank_account.id,
                        bank_name=bank.name,
                        account_name=bank_account.account_name,
                        currency_code=summary["currency_code"],
                        opening_balance=summary["opening_balance"],
                        incoming_total=summary["incoming_total"],
                        outgoing_total=summary["outgoing_total"],
                        current_balance=summary["current_balance"],
                        is_active=bank_account.is_active,
                    )
                )

            return BanksPageData(
                bank_accounts=bank_accounts,
                total_try_balance=total_try_balance,
                active_account_count=active_account_count,
            )

    except Exception as exc:
        return BanksPageData(
            bank_accounts=[],
            total_try_balance=decimal_or_zero("0.00"),
            active_account_count=0,
            error_message=str(exc),
        )


class BankTransactionDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        bank_accounts: list[BankAccountRow],
    ) -> None:
        super().__init__(parent)

        self.bank_accounts = bank_accounts
        self.account_lookup = {
            bank_account.bank_account_id: bank_account
            for bank_account in self.bank_accounts
        }
        self.payload: dict[str, Any] | None = None

        self.setWindowTitle("Banka Hareketi Oluştur")
        self.resize(600, 560)
        self._apply_dialog_styles()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        title = QLabel("Banka Hareketi Oluştur")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Seçilen banka hesabına giriş veya çıkış hareketi ekler. "
            "Kayıt mevcut yetki ve audit sistemi üzerinden oluşturulur."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)

        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        self._fill_account_combo()
        form_layout.addRow("Banka hesabı", self.account_combo)

        self.direction_combo = QComboBox()
        self.direction_combo.setMinimumHeight(38)
        self.direction_combo.addItem("Giriş / Tahsilat", TransactionDirection.IN.value)
        self.direction_combo.addItem("Çıkış / Ödeme", TransactionDirection.OUT.value)
        form_layout.addRow("Hareket yönü", self.direction_combo)

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(38)
        self.status_combo.addItem("Gerçekleşti", BankTransactionStatus.REALIZED.value)
        self.status_combo.addItem("Planlandı", BankTransactionStatus.PLANNED.value)
        form_layout.addRow("Durum", self.status_combo)

        self.transaction_date_edit = QDateEdit()
        self.transaction_date_edit.setMinimumHeight(38)
        self.transaction_date_edit.setCalendarPopup(True)
        self.transaction_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.transaction_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("İşlem tarihi", self.transaction_date_edit)

        self.amount_input = QLineEdit()
        self.amount_input.setMinimumHeight(42)
        self.amount_input.setPlaceholderText("Örn: 12500,50")
        form_layout.addRow("Tutar", self.amount_input)

        self.reference_no_input = QLineEdit()
        self.reference_no_input.setMinimumHeight(42)
        self.reference_no_input.setPlaceholderText("Dekont / fiş / açıklama no")
        form_layout.addRow("Referans no", self.reference_no_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("İsteğe bağlı açıklama")
        self.description_input.setFixedHeight(105)
        form_layout.addRow("Açıklama", self.description_input)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = QPushButton("Kaydet")
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
        main_layout.addLayout(form_layout)
        main_layout.addStretch(1)
        main_layout.addLayout(button_layout)

    def _apply_dialog_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0f172a;
                color: #e5e7eb;
            }

            QLabel {
                color: #e5e7eb;
                font-size: 13px;
            }

            QLabel#SectionTitle {
                color: #f8fafc;
                font-size: 20px;
                font-weight: 700;
            }

            QLabel#MutedText {
                color: #94a3b8;
                font-size: 13px;
            }

            QLineEdit,
            QTextEdit,
            QComboBox,
            QDateEdit {
                background-color: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 8px 12px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                font-size: 13px;
            }

            QLineEdit:focus,
            QTextEdit:focus,
            QComboBox:focus,
            QDateEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #0b1220;
            }

            QLineEdit::placeholder,
            QTextEdit::placeholder {
                color: #64748b;
            }

            QComboBox::drop-down,
            QDateEdit::drop-down {
                border: none;
                width: 30px;
            }

            QComboBox QAbstractItemView {
                background-color: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                outline: 0;
                padding: 6px;
            }

            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 6px 10px;
                color: #f8fafc;
                background-color: #111827;
            }

            QComboBox QAbstractItemView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }

            QCalendarWidget QWidget {
                background-color: #111827;
                color: #f8fafc;
            }

            QCalendarWidget QToolButton {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }

            QCalendarWidget QMenu {
                background-color: #111827;
                color: #f8fafc;
            }

            QCalendarWidget QSpinBox {
                background-color: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
            }

            QCalendarWidget QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }

            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 8px 16px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #334155;
                border-color: #475569;
            }

            QPushButton:pressed {
                background-color: #0f172a;
            }

            QPushButton:disabled {
                background-color: #1f2937;
                color: #64748b;
                border-color: #334155;
            }
            """
        )

    def _fill_account_combo(self) -> None:
        self.account_combo.clear()

        for bank_account in self.bank_accounts:
            balance_text = _format_currency_amount(
                bank_account.current_balance,
                bank_account.currency_code,
            )

            text = (
                f"{bank_account.bank_name} / "
                f"{bank_account.account_name} / "
                f"{bank_account.currency_code} / "
                f"Güncel: {balance_text}"
            )

            self.account_combo.addItem(text, bank_account.bank_account_id)

    def _selected_bank_account(self) -> BankAccountRow:
        bank_account_id = self.account_combo.currentData()

        try:
            normalized_bank_account_id = int(bank_account_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Geçerli bir banka hesabı seçilmelidir.") from exc

        bank_account = self.account_lookup.get(normalized_bank_account_id)

        if bank_account is None:
            raise ValueError("Seçilen banka hesabı bulunamadı.")

        return bank_account

    def _build_payload(self) -> dict[str, Any]:
        bank_account = self._selected_bank_account()

        amount_text = self.amount_input.text().strip()
        cleaned_amount = money(amount_text, field_name="Banka hareket tutarı")

        if cleaned_amount <= decimal_or_zero("0.00"):
            raise ValueError("Banka hareket tutarı sıfırdan büyük olmalıdır.")

        direction_value = str(self.direction_combo.currentData()).strip().upper()
        status_value = str(self.status_combo.currentData()).strip().upper()

        reference_no = self.reference_no_input.text().strip()
        description = self.description_input.toPlainText().strip()

        return {
            "bank_account_id": bank_account.bank_account_id,
            "transaction_date": _qdate_to_date(self.transaction_date_edit.date()),
            "value_date": None,
            "direction": direction_value,
            "status": status_value,
            "amount": cleaned_amount,
            "currency_code": bank_account.currency_code,
            "source_type": FinancialSourceType.MANUAL_ADJUSTMENT.value,
            "source_id": None,
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


class BanksPage(QWidget):
    def __init__(self, current_user: Any) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = _role_text(getattr(current_user, "role", None))
        self.data = load_banks_page_data()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(16)

        self._render_page()

    def _render_page(self) -> None:
        clear_layout(self.main_layout)

        if self.data.error_message:
            self.main_layout.addWidget(self._build_error_card())
            return

        self.main_layout.addLayout(self._build_summary_cards())
        self.main_layout.addWidget(self._build_accounts_table_card(), 1)
        self.main_layout.addLayout(self._build_action_area())

    def _reload_page_data(self) -> None:
        self.data = load_banks_page_data()
        self._render_page()

    def _build_error_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardRisk")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("Banka verileri okunamadı")
        title.setObjectName("SectionTitle")

        body = QLabel(self.data.error_message or "-")
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

        return card

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        total_accounts = len(self.data.bank_accounts)

        grid.addWidget(
            SummaryCard(
                "AKTİF TRY BAKİYE",
                tr_money(self.data.total_try_balance),
                "Aktif TRY banka hesaplarının toplam güncel bakiyesi",
                "highlight",
            ),
            0,
            0,
        )

        grid.addWidget(
            SummaryCard(
                "AKTİF HESAP",
                tr_number(self.data.active_account_count),
                "Aktif banka hesabı sayısı",
                "success",
            ),
            0,
            1,
        )

        grid.addWidget(
            SummaryCard(
                "TOPLAM HESAP",
                tr_number(total_accounts),
                "Aktif ve pasif tüm banka hesapları",
                "normal",
            ),
            0,
            2,
        )

        return grid

    def _build_accounts_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Banka Hesapları")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Banka hesaplarının açılış, giriş, çıkış ve güncel bakiye görünümü."
        )
        subtitle.setObjectName("MutedText")

        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            [
                "Banka ID",
                "Hesap ID",
                "Banka",
                "Hesap",
                "Para Birimi",
                "Açılış",
                "Giriş",
                "Çıkış",
                "Güncel",
            ]
        )

        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self._fill_accounts_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _fill_accounts_table(self, table: QTableWidget) -> None:
        table.setRowCount(len(self.data.bank_accounts))

        for row_index, account in enumerate(self.data.bank_accounts):
            values = [
                str(account.bank_id),
                str(account.bank_account_id),
                account.bank_name,
                account.account_name,
                account.currency_code,
                self._format_money(account.opening_balance, account.currency_code),
                self._format_money(account.incoming_total, account.currency_code),
                self._format_money(account.outgoing_total, account.currency_code),
                self._format_money(account.current_balance, account.currency_code),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if account.is_active:
                    item.setForeground(QColor("#e5e7eb"))
                else:
                    item.setForeground(QColor("#64748b"))

                if column_index in {5, 6, 7, 8}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index == 8:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _format_money(self, value: Any, currency_code: str) -> str:
        return _format_currency_amount(value, currency_code)

    def _build_action_area(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        grid.addWidget(self._build_operation_card(), 0, 0)

        if self.current_role == "ADMIN":
            grid.addWidget(self._build_admin_management_card(), 0, 1)
        else:
            grid.addWidget(self._build_limited_access_card(), 0, 1)

        return grid

    def _build_operation_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Operasyon Alanı")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Banka hareketi ve transfer işlemleri bu alandan bağlanacak. "
            "Bu işlemler mevcut servislerde yetki kontrolüyle korunuyor."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        add_transaction_button = QPushButton("Banka Hareketi Oluştur")
        add_transaction_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        add_transaction_button.clicked.connect(self._open_create_bank_transaction_dialog)

        transfer_button = QPushButton("Banka Transferi Oluştur")
        transfer_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})

        cancel_button = QPushButton("İptal İşlemleri")
        cancel_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(add_transaction_button)
        layout.addWidget(transfer_button)
        layout.addWidget(cancel_button)

        return card

    def _open_create_bank_transaction_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        active_bank_accounts = [
            bank_account
            for bank_account in self.data.bank_accounts
            if bank_account.is_active
        ]

        if not active_bank_accounts:
            QMessageBox.information(
                self,
                "Banka hesabı yok",
                "Hareket oluşturmak için en az bir aktif banka hesabı gerekir.",
            )
            return

        dialog = BankTransactionDialog(
            parent=self,
            bank_accounts=active_bank_accounts,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                bank_transaction = create_bank_transaction(
                    session,
                    bank_account_id=payload["bank_account_id"],
                    transaction_date=payload["transaction_date"],
                    value_date=payload["value_date"],
                    direction=payload["direction"],
                    status=payload["status"],
                    amount=payload["amount"],
                    currency_code=payload["currency_code"],
                    source_type=payload["source_type"],
                    source_id=payload["source_id"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_transaction_id = bank_transaction.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Banka hareketi oluşturuldu",
                f"Banka hareketi başarıyla oluşturuldu. Hareket ID: {created_transaction_id}",
            )

        except BankTransactionServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka hareketi oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Banka hareketi oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _build_admin_management_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardHighlight")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Banka Tanım Yönetimi")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Bu alan sadece ADMIN rolünde görünür. Banka ve banka hesabı tanımları "
            "sistemin temel ayarları olduğu için sınırlı erişimle korunur."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        add_bank_button = QPushButton("Banka Ekle")
        add_account_button = QPushButton("Banka Hesabı Ekle")
        edit_bank_button = QPushButton("Banka / Hesap Düzenle")
        deactivate_account_button = QPushButton("Hesap Pasifleştir")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(add_bank_button)
        layout.addWidget(add_account_button)
        layout.addWidget(edit_bank_button)
        layout.addWidget(deactivate_account_button)

        return card

    def _build_limited_access_card(self) -> QWidget:
        if self.current_role == "VIEWER":
            return InfoCard(
                "Görüntüleme Modu",
                "Bu kullanıcı banka hesaplarını ve bakiyeleri görüntüleyebilir. "
                "İşlem oluşturma ve tanım yönetimi yetkisi yoktur.",
                "VIEWER rolü sadece izler; yanlışlıkla para hareketi başlatamaz.",
            )

        if self.current_role == "FINANCE":
            return InfoCard(
                "Finans Operasyon Modu",
                "Bu kullanıcı banka hareketi ve transfer operasyonları yapabilir. "
                "Ancak banka tanımı veya hesap düzenleme işlemleri ADMIN yetkisindedir.",
                "Operasyon ayrı, sistem tanımı ayrı tutulur.",
            )

        return InfoCard(
            "Sınırlı Erişim",
            "Bu rol için banka tanım yönetimi kapalıdır.",
            "Yetki sınırları arayüzde de korunur.",
        )
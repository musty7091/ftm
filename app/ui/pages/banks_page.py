from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.session import session_scope
from app.services.bank_definition_service import (
    BankDefinitionServiceError,
    create_bank,
    create_bank_account,
    deactivate_bank_account,
    reactivate_bank_account,
    update_bank,
    update_bank_account,
)
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    cancel_bank_transaction,
    create_bank_transaction,
)
from app.services.bank_transfer_service import (
    BankTransferServiceError,
    cancel_bank_transfer,
    create_bank_transfer,
)
from app.ui.components.info_card import InfoCard
from app.ui.components.summary_card import SummaryCard
from app.ui.pages.banks.bank_account_deactivate_dialog import BankAccountDeactivateDialog
from app.ui.pages.banks.bank_account_dialog import BankAccountDialog
from app.ui.pages.banks.bank_admin_data import load_admin_banks
from app.ui.pages.banks.bank_cancel_dialog import BankCancelDialog
from app.ui.pages.banks.bank_definition_dialog import BankDefinitionDialog
from app.ui.pages.banks.bank_manage_dialog import BankManageDialog
from app.ui.pages.banks.bank_transaction_dialog import BankTransactionDialog
from app.ui.pages.banks.bank_transfer_dialog import BankTransferDialog
from app.ui.pages.banks.banks_data import (
    _format_currency_amount,
    load_banks_page_data,
)
from app.ui.ui_helpers import clear_layout, tr_money, tr_number


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


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
            "Banka hareketi, banka transferi ve iptal işlemleri bu alandan yapılır. "
            "Tüm işlemler servis katmanındaki yetki ve audit kontrollerinden geçer."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        add_transaction_button = QPushButton("Banka Hareketi Oluştur")
        add_transaction_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        add_transaction_button.clicked.connect(self._open_create_bank_transaction_dialog)

        transfer_button = QPushButton("Banka Transferi Oluştur")
        transfer_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        transfer_button.clicked.connect(self._open_create_bank_transfer_dialog)

        cancel_button = QPushButton("İptal İşlemleri")
        cancel_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        cancel_button.clicked.connect(self._open_cancel_bank_operation_dialog)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(add_transaction_button)
        layout.addWidget(transfer_button)
        layout.addWidget(cancel_button)

        return card

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
        add_bank_button.clicked.connect(self._open_create_bank_dialog)

        add_account_button = QPushButton("Banka Hesabı Ekle")
        add_account_button.clicked.connect(self._open_create_bank_account_dialog)

        edit_bank_button = QPushButton("Banka / Hesap Düzenle")
        edit_bank_button.clicked.connect(self._open_manage_bank_dialog)

        deactivate_account_button = QPushButton("Hesap Pasifleştir / Aktifleştir")
        deactivate_account_button.clicked.connect(self._open_deactivate_bank_account_dialog)

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

    def _ensure_admin_role(self) -> bool:
        if self.current_role != "ADMIN":
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN yetkisi gerekir.",
            )
            return False

        return True

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

    def _open_create_bank_transfer_dialog(self) -> None:
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

        if len(active_bank_accounts) < 2:
            QMessageBox.information(
                self,
                "Yetersiz banka hesabı",
                "Transfer oluşturmak için en az iki aktif banka hesabı gerekir.",
            )
            return

        currency_account_counts: dict[str, int] = {}

        for bank_account in active_bank_accounts:
            currency_account_counts[bank_account.currency_code] = (
                currency_account_counts.get(bank_account.currency_code, 0) + 1
            )

        has_transferable_currency = any(
            account_count >= 2
            for account_count in currency_account_counts.values()
        )

        if not has_transferable_currency:
            QMessageBox.information(
                self,
                "Uygun hesap yok",
                "Transfer için aynı para biriminde en az iki aktif banka hesabı gerekir.",
            )
            return

        dialog = BankTransferDialog(
            parent=self,
            bank_accounts=active_bank_accounts,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                bank_transfer = create_bank_transfer(
                    session,
                    from_bank_account_id=payload["from_bank_account_id"],
                    to_bank_account_id=payload["to_bank_account_id"],
                    transfer_date=payload["transfer_date"],
                    value_date=payload["value_date"],
                    amount=payload["amount"],
                    status=payload["status"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_transfer_id = bank_transfer.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Banka transferi oluşturuldu",
                f"Banka transferi başarıyla oluşturuldu. Transfer ID: {created_transfer_id}",
            )

        except BankTransferServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka transferi oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Banka transferi oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_cancel_bank_operation_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        dialog = BankCancelDialog(parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        operation_type = payload["operation_type"]
        entity_id = payload["entity_id"]
        cancel_reason = payload["cancel_reason"]

        try:
            with session_scope() as session:
                if operation_type == "BANK_TRANSACTION":
                    cancelled_transaction = cancel_bank_transaction(
                        session,
                        bank_transaction_id=entity_id,
                        cancel_reason=cancel_reason,
                        cancelled_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    cancelled_id = cancelled_transaction.id
                    success_title = "Banka hareketi iptal edildi"
                    success_message = (
                        f"Banka hareketi başarıyla iptal edildi. Hareket ID: {cancelled_id}"
                    )

                elif operation_type == "BANK_TRANSFER":
                    cancelled_transfer = cancel_bank_transfer(
                        session,
                        transfer_id=entity_id,
                        cancelled_by_user_id=getattr(self.current_user, "id", None),
                        cancel_reason=cancel_reason,
                        acting_user=self.current_user,
                    )

                    cancelled_id = cancelled_transfer.id
                    success_title = "Banka transferi iptal edildi"
                    success_message = (
                        f"Banka transferi başarıyla iptal edildi. Transfer ID: {cancelled_id}"
                    )

                else:
                    raise ValueError("Geçersiz iptal işlem türü.")

            self._reload_page_data()

            QMessageBox.information(
                self,
                success_title,
                success_message,
            )

        except BankTransactionServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka hareketi iptal edilemedi",
                str(exc),
            )
        except BankTransferServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka transferi iptal edilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"İptal işlemi yapılırken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_create_bank_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        dialog = BankDefinitionDialog(
            parent=self,
            mode="create",
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                bank = create_bank(
                    session,
                    name=payload["name"],
                    short_name=payload["short_name"],
                    notes=payload["notes"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_bank_id = bank.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Banka oluşturuldu",
                f"Banka başarıyla oluşturuldu. Banka ID: {created_bank_id}",
            )

        except BankDefinitionServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Banka oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_create_bank_account_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        active_banks = load_admin_banks(include_passive=False)

        if not active_banks:
            QMessageBox.information(
                self,
                "Aktif banka yok",
                "Banka hesabı oluşturmak için önce en az bir aktif banka tanımı gerekir.",
            )
            return

        dialog = BankAccountDialog(
            parent=self,
            mode="create",
            banks=active_banks,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                bank_account = create_bank_account(
                    session,
                    bank_id=payload["bank_id"],
                    account_name=payload["account_name"],
                    account_type=payload["account_type"],
                    currency_code=payload["currency_code"],
                    iban=payload["iban"],
                    branch_name=payload["branch_name"],
                    branch_code=payload["branch_code"],
                    account_no=payload["account_no"],
                    opening_balance=payload["opening_balance"],
                    opening_date=payload["opening_date"],
                    notes=payload["notes"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_bank_account_id = bank_account.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Banka hesabı oluşturuldu",
                f"Banka hesabı başarıyla oluşturuldu. Hesap ID: {created_bank_account_id}",
            )

        except BankDefinitionServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka hesabı oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Banka hesabı oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_manage_bank_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        dialog = BankManageDialog(parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()
        edit_type = payload["edit_type"]
        data = payload["data"]

        try:
            with session_scope() as session:
                if edit_type == "BANK":
                    bank = update_bank(
                        session,
                        bank_id=data["bank_id"],
                        name=data["name"],
                        short_name=data["short_name"],
                        notes=data["notes"],
                        is_active=data["is_active"],
                        updated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    updated_id = bank.id
                    success_title = "Banka güncellendi"
                    success_message = (
                        f"Banka başarıyla güncellendi. Banka ID: {updated_id}"
                    )

                elif edit_type == "BANK_ACCOUNT":
                    bank_account = update_bank_account(
                        session,
                        bank_account_id=data["bank_account_id"],
                        bank_id=data["bank_id"],
                        account_name=data["account_name"],
                        account_type=data["account_type"],
                        currency_code=data["currency_code"],
                        iban=data["iban"],
                        branch_name=data["branch_name"],
                        branch_code=data["branch_code"],
                        account_no=data["account_no"],
                        opening_balance=data["opening_balance"],
                        opening_date=data["opening_date"],
                        notes=data["notes"],
                        is_active=data["is_active"],
                        updated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    updated_id = bank_account.id
                    success_title = "Banka hesabı güncellendi"
                    success_message = (
                        f"Banka hesabı başarıyla güncellendi. Hesap ID: {updated_id}"
                    )

                else:
                    raise ValueError("Geçersiz düzenleme işlem türü.")

            self._reload_page_data()

            QMessageBox.information(
                self,
                success_title,
                success_message,
            )

        except BankDefinitionServiceError as exc:
            QMessageBox.warning(
                self,
                "Tanım güncellenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Tanım güncellenirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_deactivate_bank_account_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        dialog = BankAccountDeactivateDialog(parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        operation_type = payload["operation_type"]
        bank_account_id = payload["bank_account_id"]
        reason = payload["reason"]

        try:
            with session_scope() as session:
                if operation_type == "DEACTIVATE":
                    bank_account = deactivate_bank_account(
                        session,
                        bank_account_id=bank_account_id,
                        deactivate_reason=reason,
                        deactivated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    changed_bank_account_id = bank_account.id
                    success_title = "Banka hesabı pasifleştirildi"
                    success_message = (
                        f"Banka hesabı başarıyla pasifleştirildi. Hesap ID: {changed_bank_account_id}"
                    )

                elif operation_type == "REACTIVATE":
                    bank_account = reactivate_bank_account(
                        session,
                        bank_account_id=bank_account_id,
                        reactivate_reason=reason,
                        reactivated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    changed_bank_account_id = bank_account.id
                    success_title = "Banka hesabı aktifleştirildi"
                    success_message = (
                        f"Banka hesabı başarıyla aktifleştirildi. Hesap ID: {changed_bank_account_id}"
                    )

                else:
                    raise ValueError("Geçersiz hesap durum işlemi.")

            self._reload_page_data()

            QMessageBox.information(
                self,
                success_title,
                success_message,
            )

        except BankDefinitionServiceError as exc:
            QMessageBox.warning(
                self,
                "Banka hesabı durumu değiştirilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Banka hesabı durumu değiştirilirken beklenmeyen bir hata oluştu:\n{exc}",
            )
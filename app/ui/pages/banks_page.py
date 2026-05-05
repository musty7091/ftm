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
from app.services.permission_service import Permission
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
from app.ui.permission_ui import (
    apply_any_permission_to_button,
    apply_permission_to_button,
    user_has_any_permission,
    user_has_permission,
)
from app.ui.ui_helpers import clear_layout, tr_number


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


def _currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return (CURRENCY_DISPLAY_ORDER.index(normalized_currency_code), normalized_currency_code)

    return (999, normalized_currency_code)


class BanksPage(QWidget):
    def __init__(self, current_user: Any) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = _role_text(getattr(current_user, "role", None))
        self.data = load_banks_page_data()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        self._render_page()

    def _render_page(self) -> None:
        clear_layout(self.main_layout)

        if self.data.error_message:
            self.main_layout.addWidget(self._build_error_card())
            return

        self.main_layout.addLayout(self._build_summary_cards())
        self.main_layout.addWidget(self._build_accounts_table_card(), 1)
        self.main_layout.addLayout(self._build_action_area(), 0)

    def _reload_page_data(self) -> None:
        self.data = load_banks_page_data()
        self._render_page()

    def _build_error_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardRisk")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Banka verileri okunamadı")
        title.setObjectName("SectionTitle")

        body = QLabel(self.data.error_message or "-")
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

        return card

    def _build_active_currency_totals_text(self) -> str:
        if not self.data.active_currency_totals:
            return "Kayıt yok"

        lines: list[str] = []

        for currency_code in sorted(
            self.data.active_currency_totals.keys(),
            key=_currency_sort_key,
        ):
            lines.append(
                f"{currency_code}: {_format_currency_amount(self.data.active_currency_totals[currency_code], currency_code)}"
            )

        return "\n".join(lines)

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)

        grid.addWidget(
            self._build_active_bank_balances_card(),
            0,
            0,
        )

        grid.addWidget(
            self._build_account_status_card(),
            0,
            1,
        )

        return grid
    
    def _build_active_bank_balances_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardHighlight")
        card.setMinimumHeight(112)
        card.setMaximumHeight(132)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("AKTİF BANKA BAKİYELERİ")
        title.setObjectName("CardTitle")

        balances_grid = QGridLayout()
        balances_grid.setHorizontalSpacing(18)
        balances_grid.setVerticalSpacing(4)
        balances_grid.setColumnStretch(0, 1)
        balances_grid.setColumnStretch(1, 1)

        if not self.data.active_currency_totals:
            empty_label = QLabel("Kayıt yok")
            empty_label.setObjectName("CardValue")
            balances_grid.addWidget(empty_label, 0, 0, 1, 2)

        else:
            sorted_currency_codes = sorted(
                self.data.active_currency_totals.keys(),
                key=_currency_sort_key,
            )

            for index, currency_code in enumerate(sorted_currency_codes):
                row_index = index // 2
                column_index = index % 2

                amount_text = _format_currency_amount(
                    self.data.active_currency_totals[currency_code],
                    currency_code,
                )

                value_label = QLabel(f"{currency_code}: {amount_text}")
                value_label.setObjectName("CardValue")
                value_label.setWordWrap(False)
                value_label.setToolTip(f"{currency_code}: {amount_text}")

                balances_grid.addWidget(value_label, row_index, column_index)

        hint = QLabel("Aktif banka hesaplarının para birimi bazlı güncel toplamı")
        hint.setObjectName("CardHint")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addLayout(balances_grid)
        layout.addWidget(hint)

        return card

    def _build_account_status_card(self) -> QWidget:
        total_accounts = len(self.data.bank_accounts)

        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(112)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("HESAP DURUMU")
        title.setObjectName("CardTitle")

        metrics_layout = QGridLayout()
        metrics_layout.setSpacing(10)
        metrics_layout.setColumnStretch(0, 1)
        metrics_layout.setColumnStretch(1, 1)
        metrics_layout.setColumnStretch(2, 1)

        metrics_layout.addWidget(
            self._build_compact_metric(
                "AKTİF",
                tr_number(self.data.active_account_count),
                "Hesap",
            ),
            0,
            0,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "PASİF",
                tr_number(self.data.passive_account_count),
                "Hesap",
            ),
            0,
            1,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "TOPLAM",
                tr_number(total_accounts),
                "Hesap",
            ),
            0,
            2,
        )

        hint = QLabel("Banka hesabı durum özeti.")
        hint.setObjectName("CardHint")
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addLayout(metrics_layout)
        layout.addWidget(hint)

        return card

    def _build_compact_metric(self, title_text: str, value_text: str, hint_text: str) -> QWidget:
        box = QWidget()

        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        title = QLabel(title_text)
        title.setObjectName("CardTitle")
        title.setAlignment(Qt.AlignCenter)

        value = QLabel(value_text)
        value.setObjectName("CardValue")
        value.setAlignment(Qt.AlignCenter)

        hint = QLabel(hint_text)
        hint.setObjectName("CardHint")
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)

        return box

    def _build_accounts_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(260)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Banka Hesapları")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Aktif ve pasif banka hesaplarının para birimi, giriş, çıkış ve güncel bakiye görünümü."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

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
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setMinimumHeight(170)

        table.setColumnHidden(0, True)
        table.setColumnHidden(1, True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        self._fill_accounts_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _accounts_table_height(self) -> int:
        row_count = len(self.data.bank_accounts)

        if row_count <= 0:
            return 135

        calculated_height = 78 + (row_count * 38)

        if calculated_height < 145:
            return 145

        if calculated_height > 315:
            return 315

        return calculated_height

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

                item.setToolTip(
                    "\n".join(
                        [
                            f"Banka ID: {account.bank_id}",
                            f"Hesap ID: {account.bank_account_id}",
                            f"Banka: {account.bank_name}",
                            f"Hesap: {account.account_name}",
                            f"Para Birimi: {account.currency_code}",
                            f"Güncel: {self._format_money(account.current_balance, account.currency_code)}",
                            f"Durum: {'Aktif' if account.is_active else 'Pasif'}",
                        ]
                    )
                )

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _format_money(self, value: Any, currency_code: str) -> str:
        return _format_currency_amount(value, currency_code)

    def _has_permission(self, permission: Permission) -> bool:
        return user_has_permission(
            current_user=self.current_user,
            permission=permission,
        )

    def _has_any_permission(self, permissions: tuple[Permission, ...]) -> bool:
        return user_has_any_permission(
            current_user=self.current_user,
            permissions=permissions,
        )

    def _has_bank_definition_management_access(self) -> bool:
        return self._has_any_permission(
            (
                Permission.BANK_CREATE,
                Permission.BANK_UPDATE,
                Permission.BANK_ACCOUNT_CREATE,
                Permission.BANK_ACCOUNT_UPDATE,
                Permission.BANK_ACCOUNT_DEACTIVATE,
                Permission.BANK_ACCOUNT_REACTIVATE,
            )
        )

    def _ensure_permission(
        self,
        permission: Permission,
        message: str,
    ) -> bool:
        if self._has_permission(permission):
            return True

        QMessageBox.warning(
            self,
            "Yetkisiz işlem",
            message,
        )
        return False

    def _ensure_any_permission(
        self,
        permissions: tuple[Permission, ...],
        message: str,
    ) -> bool:
        if self._has_any_permission(permissions):
            return True

        QMessageBox.warning(
            self,
            "Yetkisiz işlem",
            message,
        )
        return False

    def _build_action_area(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._build_operation_card(), 0, 0)

        if self._has_bank_definition_management_access():
            grid.addWidget(self._build_admin_management_card(), 0, 1)
        else:
            grid.addWidget(self._build_limited_access_card(), 0, 1)

        return grid

    def _build_operation_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        title = QLabel("Günlük Banka İşlemleri")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Banka hareketi, transfer ve iptal işlemlerini bu alandan yönetebilirsin."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        add_transaction_button = QPushButton("Banka Hareketi Oluştur")
        add_transaction_button.clicked.connect(self._open_create_bank_transaction_dialog)
        apply_permission_to_button(
            add_transaction_button,
            current_user=self.current_user,
            permission=Permission.BANK_TRANSACTION_CREATE,
            tooltip_when_denied="Banka hareketi oluşturma yetkin yok.",
        )

        transfer_button = QPushButton("Banka Transferi Oluştur")
        transfer_button.clicked.connect(self._open_create_bank_transfer_dialog)
        apply_permission_to_button(
            transfer_button,
            current_user=self.current_user,
            permission=Permission.BANK_TRANSFER_CREATE,
            tooltip_when_denied="Banka transferi oluşturma yetkin yok.",
        )

        cancel_button = QPushButton("Hareket / Transfer İptali")
        cancel_button.clicked.connect(self._open_cancel_bank_operation_dialog)
        apply_any_permission_to_button(
            cancel_button,
            current_user=self.current_user,
            permissions=(
                Permission.BANK_TRANSACTION_CANCEL,
                Permission.BANK_TRANSFER_CANCEL,
            ),
            tooltip_when_denied="Banka hareketi veya banka transferi iptal etme yetkin yok.",
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(4)
        layout.addWidget(add_transaction_button)
        layout.addWidget(transfer_button)
        layout.addWidget(cancel_button)

        return card

    def _build_admin_management_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardHighlight")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        title = QLabel("Banka ve Hesap Tanımları")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Banka ve banka hesabı tanımlarını bu alandan ekleyebilir veya güncelleyebilirsin."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        add_bank_button = QPushButton("Banka Ekle")
        add_bank_button.clicked.connect(self._open_create_bank_dialog)
        apply_permission_to_button(
            add_bank_button,
            current_user=self.current_user,
            permission=Permission.BANK_CREATE,
            tooltip_when_denied="Banka ekleme yetkin yok.",
        )

        add_account_button = QPushButton("Banka Hesabı Ekle")
        add_account_button.clicked.connect(self._open_create_bank_account_dialog)
        apply_permission_to_button(
            add_account_button,
            current_user=self.current_user,
            permission=Permission.BANK_ACCOUNT_CREATE,
            tooltip_when_denied="Banka hesabı ekleme yetkin yok.",
        )

        edit_bank_button = QPushButton("Banka / Hesap Düzenle")
        edit_bank_button.clicked.connect(self._open_manage_bank_dialog)
        apply_any_permission_to_button(
            edit_bank_button,
            current_user=self.current_user,
            permissions=(
                Permission.BANK_UPDATE,
                Permission.BANK_ACCOUNT_UPDATE,
            ),
            tooltip_when_denied="Banka veya banka hesabı düzenleme yetkin yok.",
        )

        deactivate_account_button = QPushButton("Hesap Pasifleştir / Aktifleştir")
        deactivate_account_button.clicked.connect(self._open_deactivate_bank_account_dialog)
        apply_any_permission_to_button(
            deactivate_account_button,
            current_user=self.current_user,
            permissions=(
                Permission.BANK_ACCOUNT_DEACTIVATE,
                Permission.BANK_ACCOUNT_REACTIVATE,
            ),
            tooltip_when_denied="Banka hesabı pasifleştirme veya aktifleştirme yetkin yok.",
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(4)
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
                "Bu kullanıcı sadece kendisine verilen banka işlem yetkilerini kullanabilir. "
                "Banka tanımı veya hesap düzenleme işlemleri ayrıca yetkilendirilir.",
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
        if not self._ensure_permission(
            Permission.BANK_TRANSACTION_CREATE,
            "Banka hareketi oluşturmak için BANK_TRANSACTION_CREATE yetkisi gerekir.",
        ):
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
        if not self._ensure_permission(
            Permission.BANK_TRANSFER_CREATE,
            "Banka transferi oluşturmak için BANK_TRANSFER_CREATE yetkisi gerekir.",
        ):
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
        if not self._ensure_any_permission(
            (
                Permission.BANK_TRANSACTION_CANCEL,
                Permission.BANK_TRANSFER_CANCEL,
            ),
            "İptal işlemleri için BANK_TRANSACTION_CANCEL veya BANK_TRANSFER_CANCEL yetkisi gerekir.",
        ):
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
                    if not self._ensure_permission(
                        Permission.BANK_TRANSACTION_CANCEL,
                        "Banka hareketi iptal etmek için BANK_TRANSACTION_CANCEL yetkisi gerekir.",
                    ):
                        return

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
                    if not self._ensure_permission(
                        Permission.BANK_TRANSFER_CANCEL,
                        "Banka transferi iptal etmek için BANK_TRANSFER_CANCEL yetkisi gerekir.",
                    ):
                        return

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
        if not self._ensure_permission(
            Permission.BANK_CREATE,
            "Banka oluşturmak için BANK_CREATE yetkisi gerekir.",
        ):
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
        if not self._ensure_permission(
            Permission.BANK_ACCOUNT_CREATE,
            "Banka hesabı oluşturmak için BANK_ACCOUNT_CREATE yetkisi gerekir.",
        ):
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
        if not self._ensure_any_permission(
            (
                Permission.BANK_UPDATE,
                Permission.BANK_ACCOUNT_UPDATE,
            ),
            "Banka veya banka hesabı düzenlemek için BANK_UPDATE veya BANK_ACCOUNT_UPDATE yetkisi gerekir.",
        ):
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
                    if not self._ensure_permission(
                        Permission.BANK_UPDATE,
                        "Banka düzenlemek için BANK_UPDATE yetkisi gerekir.",
                    ):
                        return

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
                    if not self._ensure_permission(
                        Permission.BANK_ACCOUNT_UPDATE,
                        "Banka hesabı düzenlemek için BANK_ACCOUNT_UPDATE yetkisi gerekir.",
                    ):
                        return

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
                    raise ValueError("Geçersiz düzenleme türü.")

            self._reload_page_data()

            QMessageBox.information(
                self,
                success_title,
                success_message,
            )

        except BankDefinitionServiceError as exc:
            QMessageBox.warning(
                self,
                "Güncelleme yapılamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Güncelleme sırasında beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_deactivate_bank_account_dialog(self) -> None:
        if not self._ensure_any_permission(
            (
                Permission.BANK_ACCOUNT_DEACTIVATE,
                Permission.BANK_ACCOUNT_REACTIVATE,
            ),
            "Banka hesabı pasifleştirmek veya aktifleştirmek için gerekli yetkin yok.",
        ):
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
                    if not self._ensure_permission(
                        Permission.BANK_ACCOUNT_DEACTIVATE,
                        "Banka hesabı pasifleştirmek için BANK_ACCOUNT_DEACTIVATE yetkisi gerekir.",
                    ):
                        return

                    bank_account = deactivate_bank_account(
                        session,
                        bank_account_id=bank_account_id,
                        deactivate_reason=reason,
                        deactivated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    result_title = "Banka hesabı pasifleştirildi"
                    result_message = (
                        f"Banka hesabı başarıyla pasifleştirildi. Hesap ID: {bank_account.id}"
                    )

                elif operation_type == "REACTIVATE":
                    if not self._ensure_permission(
                        Permission.BANK_ACCOUNT_REACTIVATE,
                        "Banka hesabı aktifleştirmek için BANK_ACCOUNT_REACTIVATE yetkisi gerekir.",
                    ):
                        return

                    bank_account = reactivate_bank_account(
                        session,
                        bank_account_id=bank_account_id,
                        reactivate_reason=reason,
                        reactivated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    result_title = "Banka hesabı aktifleştirildi"
                    result_message = (
                        f"Banka hesabı başarıyla aktifleştirildi. Hesap ID: {bank_account.id}"
                    )

                else:
                    raise ValueError("Geçersiz hesap işlem türü.")

            self._reload_page_data()

            QMessageBox.information(
                self,
                result_title,
                result_message,
            )

        except BankDefinitionServiceError as exc:
            QMessageBox.warning(
                self,
                "Hesap durumu değiştirilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Hesap durumu değiştirilirken beklenmeyen bir hata oluştu:\n{exc}",
            )
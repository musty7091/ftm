from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.db.session import session_scope
from app.services.check_service import (
    CheckServiceError,
    collect_received_check,
    create_issued_check,
    create_received_check,
    pay_issued_check,
    send_received_check_to_bank,
)
from app.ui.components.info_card import InfoCard
from app.ui.components.summary_card import SummaryCard
from app.ui.pages.checks.checks_data import (
    build_currency_totals_text,
    format_currency_amount,
    issued_status_text,
    load_checks_page_data,
    received_status_text,
)
from app.ui.pages.checks.issued_check_create_dialog import IssuedCheckCreateDialog
from app.ui.pages.checks.issued_check_pay_dialog import IssuedCheckPayDialog
from app.ui.pages.checks.received_check_collect_dialog import ReceivedCheckCollectDialog
from app.ui.pages.checks.received_check_create_dialog import ReceivedCheckCreateDialog
from app.ui.pages.checks.received_check_send_to_bank_dialog import ReceivedCheckSendToBankDialog
from app.ui.ui_helpers import clear_layout, tr_number


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


class ChecksPage(QWidget):
    def __init__(self, current_user: Any) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = _role_text(getattr(current_user, "role", None))
        self.data = load_checks_page_data()

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
        self.main_layout.addWidget(self._build_checks_tabs(), 1)

    def _reload_page_data(self) -> None:
        self.data = load_checks_page_data()
        self._render_page()

    def _build_error_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardRisk")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("Çek verileri okunamadı")
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
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 1)

        grid.addWidget(
            SummaryCard(
                "YAZILAN ÇEK YÜKÜ",
                build_currency_totals_text(self.data.pending_issued_currency_totals),
                f"{tr_number(self.data.pending_issued_count)} açık yazılan çek",
                "risk",
            ),
            0,
            0,
        )

        grid.addWidget(
            SummaryCard(
                "ALINAN ÇEK PORTFÖYÜ",
                build_currency_totals_text(self.data.pending_received_currency_totals),
                f"{tr_number(self.data.pending_received_count)} açık alınan çek",
                "success",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_check_status_card(),
            0,
            2,
        )

        return grid

    def _build_check_status_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(145)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("ÇEK DURUMU")
        title.setObjectName("CardTitle")

        metrics_layout = QGridLayout()
        metrics_layout.setSpacing(10)

        metrics_layout.addWidget(
            self._build_compact_metric(
                "7 GÜN / YAZILAN",
                tr_number(self.data.issued_due_soon_count),
                "Vade",
            ),
            0,
            0,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "7 GÜN / ALINAN",
                tr_number(self.data.received_due_soon_count),
                "Vade",
            ),
            0,
            1,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "YAZILAN RİSK",
                tr_number(self.data.issued_problem_count),
                "Kayıt",
            ),
            1,
            0,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "ALINAN PROBLEM",
                tr_number(self.data.received_problem_count),
                "Kayıt",
            ),
            1,
            1,
        )

        hint = QLabel("Yaklaşan vade ve problemli çek kayıt özeti.")
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
        layout.setSpacing(2)

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

    def _build_checks_tabs(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.setObjectName("ChecksTabs")
        tabs.setDocumentMode(False)

        tabs.setStyleSheet(
            """
            QTabWidget#ChecksTabs::pane {
                border: 1px solid #1e293b;
                background-color: #0b1220;
                border-radius: 12px;
                top: -1px;
            }

            QTabBar::tab {
                background-color: #172033;
                color: #94a3b8;
                border: 1px solid #24324a;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 10px 18px;
                margin-right: 6px;
                min-width: 120px;
                font-weight: 600;
            }

            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #ffffff;
            }

            QTabBar::tab:hover:!selected {
                background-color: #1e293b;
                color: #e5e7eb;
            }
            """
        )

        tabs.addTab(self._build_overview_tab(), "Genel Görünüm")
        tabs.addTab(self._build_issued_checks_tab(), "Yazılan Çekler")
        tabs.addTab(self._build_received_checks_tab(), "Alınan Çekler")

        layout.addWidget(tabs)

        return card

    def _build_overview_tab(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(16)

        layout.addLayout(self._build_overview_status_cards())
        layout.addLayout(self._build_overview_action_area())
        layout.addStretch()

        return page

    def _build_overview_status_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(
            self._build_small_status_card(
                "AÇIK YAZILAN ÇEK",
                tr_number(self.data.pending_issued_count),
                "Kayıt",
            ),
            0,
            0,
        )

        grid.addWidget(
            self._build_small_status_card(
                "AÇIK ALINAN ÇEK",
                tr_number(self.data.pending_received_count),
                "Kayıt",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_small_status_card(
                "YAKLAŞAN VADE",
                tr_number(self.data.issued_due_soon_count + self.data.received_due_soon_count),
                "Toplam",
            ),
            0,
            2,
        )

        grid.addWidget(
            self._build_small_status_card(
                "PROBLEMLİ ÇEK",
                tr_number(self.data.issued_problem_count + self.data.received_problem_count),
                "Kayıt",
            ),
            0,
            3,
        )

        return grid

    def _build_small_status_card(self, title_text: str, value_text: str, hint_text: str) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(115)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title = QLabel(title_text)
        title.setObjectName("CardTitle")

        value = QLabel(value_text)
        value.setObjectName("CardValue")

        hint = QLabel(hint_text)
        hint.setObjectName("CardHint")

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(value)
        layout.addWidget(hint)

        return card

    def _build_overview_action_area(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        grid.addWidget(self._build_operation_card(), 0, 0)

        if self.current_role == "ADMIN":
            grid.addWidget(self._build_admin_hint_card(), 0, 1)
        else:
            grid.addWidget(self._build_role_hint_card(), 0, 1)

        return grid

    def _build_issued_checks_tab(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(14)

        layout.addWidget(
            self._build_issued_checks_card(
                rows=self.data.issued_checks,
                title="Yazılan Çekler",
                subtitle="Tedarikçilere yazılan çeklerin vade, durum ve banka hesabı görünümü.",
            ),
            1,
        )

        return page

    def _build_received_checks_tab(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(14)

        layout.addWidget(
            self._build_received_checks_card(
                rows=self.data.received_checks,
                title="Alınan Çekler",
                subtitle="Müşterilerden alınan çeklerin çek bankası, tahsil hesabı, vade ve durum görünümü.",
            ),
            1,
        )

        return page

    def _configure_table_for_compact_view(self, table: QTableWidget) -> None:
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setDefaultSectionSize(34)
        table.verticalHeader().setMinimumSectionSize(30)
        table.horizontalHeader().setMinimumSectionSize(70)
        table.horizontalHeader().setStretchLastSection(False)

    def _build_issued_checks_card(
        self,
        *,
        rows: list[Any],
        title: str,
        subtitle: str,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MutedText")
        subtitle_label.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            [
                "ID",
                "Tedarikçi",
                "Banka / Hesap",
                "Çek No",
                "Keşide",
                "Vade",
                "Tutar",
                "Durum",
                "Referans",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setMinimumHeight(420)

        self._configure_table_for_compact_view(table)
        self._fill_issued_checks_table(table, rows)
        self._configure_issued_table_columns(table)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(table, 1)

        return card

    def _configure_issued_table_columns(self, table: QTableWidget) -> None:
        header = table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        table.setColumnWidth(2, 260)

    def _fill_issued_checks_table(self, table: QTableWidget, rows: list[Any]) -> None:
        table.setRowCount(len(rows))

        for row_index, issued_check in enumerate(rows):
            values = [
                str(issued_check.issued_check_id),
                issued_check.supplier_name,
                f"{issued_check.bank_name} / {issued_check.bank_account_name}",
                issued_check.check_number,
                issued_check.issue_date_text,
                issued_check.due_date_text,
                format_currency_amount(issued_check.amount, issued_check.currency_code),
                issued_status_text(issued_check.status),
                issued_check.reference_no or "-",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if issued_check.status == "RISK":
                    item.setForeground(QColor("#fbbf24"))
                elif issued_check.status == "CANCELLED":
                    item.setForeground(QColor("#64748b"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 6:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip(str(value))
                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _build_received_checks_card(
        self,
        *,
        rows: list[Any],
        title: str,
        subtitle: str,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MutedText")
        subtitle_label.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
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
                "Referans",
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setMinimumHeight(420)

        self._configure_table_for_compact_view(table)
        self._fill_received_checks_table(table, rows)
        self._configure_received_table_columns(table)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(table, 1)

        return card

    def _configure_received_table_columns(self, table: QTableWidget) -> None:
        header = table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        table.setColumnWidth(3, 280)

    def _fill_received_checks_table(self, table: QTableWidget, rows: list[Any]) -> None:
        table.setRowCount(len(rows))

        for row_index, received_check in enumerate(rows):
            collection_text = (
                f"{received_check.collection_bank_name} / {received_check.collection_bank_account_name}"
                if received_check.collection_bank_name and received_check.collection_bank_account_name
                else "-"
            )

            values = [
                str(received_check.received_check_id),
                received_check.customer_name,
                received_check.drawer_bank_name,
                collection_text,
                received_check.check_number,
                received_check.received_date_text,
                received_check.due_date_text,
                format_currency_amount(received_check.amount, received_check.currency_code),
                received_status_text(received_check.status),
                received_check.reference_no or "-",
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if received_check.status in {"BOUNCED", "RETURNED"}:
                    item.setForeground(QColor("#fbbf24"))
                elif received_check.status == "CANCELLED":
                    item.setForeground(QColor("#64748b"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 7:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip(str(value))
                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _build_operation_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Operasyon Alanı")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Yazılan ve alınan çek operasyonları bu alandan yürütülecek. "
            "Ana ekranda liste kalabalığı yok; operasyon odakta."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        create_issued_button = QPushButton("Yazılan Çek Oluştur")
        create_issued_button.setEnabled(self.current_role in {"ADMIN", "FINANCE", "DATA_ENTRY"})
        create_issued_button.clicked.connect(self._open_create_issued_check_dialog)

        pay_issued_button = QPushButton("Yazılan Çek Ödendi")
        pay_issued_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        pay_issued_button.clicked.connect(self._open_pay_issued_check_dialog)

        create_received_button = QPushButton("Alınan Çek Oluştur")
        create_received_button.setEnabled(self.current_role in {"ADMIN", "FINANCE", "DATA_ENTRY"})
        create_received_button.clicked.connect(self._open_create_received_check_dialog)

        send_received_to_bank_button = QPushButton("Alınan Çeki Bankaya Tahsile Ver")
        send_received_to_bank_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        send_received_to_bank_button.clicked.connect(self._open_send_received_check_to_bank_dialog)

        collect_received_button = QPushButton("Alınan Çek Tahsil Et")
        collect_received_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})
        collect_received_button.clicked.connect(self._open_collect_received_check_dialog)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(8)
        layout.addWidget(create_issued_button)
        layout.addWidget(pay_issued_button)
        layout.addWidget(create_received_button)
        layout.addWidget(send_received_to_bank_button)
        layout.addWidget(collect_received_button)
        layout.addStretch()

        return card

    def _open_create_issued_check_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE", "DATA_ENTRY"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN, FINANCE veya DATA_ENTRY yetkisi gerekir.",
            )
            return

        dialog = IssuedCheckCreateDialog(parent=self)

        if not dialog.has_required_data():
            QMessageBox.information(
                self,
                "Kayıt için gerekli tanım eksik",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                issued_check = create_issued_check(
                    session,
                    supplier_id=payload["supplier_id"],
                    bank_account_id=payload["bank_account_id"],
                    check_number=payload["check_number"],
                    issue_date=payload["issue_date"],
                    due_date=payload["due_date"],
                    amount=payload["amount"],
                    status=payload["status"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_issued_check_id = issued_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Yazılan çek oluşturuldu",
                f"Yazılan çek başarıyla oluşturuldu. Çek ID: {created_issued_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Yazılan çek oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Yazılan çek oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_pay_issued_check_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        dialog = IssuedCheckPayDialog(parent=self)

        if not dialog.has_payable_checks():
            QMessageBox.information(
                self,
                "Ödenecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                issued_check = pay_issued_check(
                    session,
                    issued_check_id=payload["issued_check_id"],
                    payment_date=payload["payment_date"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    paid_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                paid_issued_check_id = issued_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Yazılan çek ödendi",
                f"Yazılan çek ödeme işlemi başarıyla tamamlandı. Çek ID: {paid_issued_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Yazılan çek ödenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Yazılan çek ödenirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_create_received_check_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE", "DATA_ENTRY"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN, FINANCE veya DATA_ENTRY yetkisi gerekir.",
            )
            return

        dialog = ReceivedCheckCreateDialog(parent=self)

        if not dialog.has_required_data():
            QMessageBox.information(
                self,
                "Kayıt için gerekli tanım eksik",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                received_check = create_received_check(
                    session,
                    customer_id=payload["customer_id"],
                    collection_bank_account_id=payload["collection_bank_account_id"],
                    drawer_bank_name=payload["drawer_bank_name"],
                    drawer_branch_name=payload["drawer_branch_name"],
                    check_number=payload["check_number"],
                    received_date=payload["received_date"],
                    due_date=payload["due_date"],
                    amount=payload["amount"],
                    currency_code=payload["currency_code"],
                    status=payload["status"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_received_check_id = received_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Alınan çek oluşturuldu",
                f"Alınan çek başarıyla oluşturuldu. Çek ID: {created_received_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Alınan çek oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Alınan çek oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_send_received_check_to_bank_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        dialog = ReceivedCheckSendToBankDialog(parent=self)

        if not dialog.has_sendable_checks():
            QMessageBox.information(
                self,
                "Gönderilecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                received_check = send_received_check_to_bank(
                    session,
                    received_check_id=payload["received_check_id"],
                    collection_bank_account_id=payload["collection_bank_account_id"],
                    sent_date=payload["sent_date"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    moved_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                changed_received_check_id = received_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Çek bankaya gönderildi",
                f"Alınan çek bankaya tahsile başarıyla verildi. Çek ID: {changed_received_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Çek bankaya gönderilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Çek bankaya tahsile gönderilirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_collect_received_check_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        dialog = ReceivedCheckCollectDialog(parent=self)

        if not dialog.has_collectable_checks():
            QMessageBox.information(
                self,
                "Tahsil edilecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                received_check = collect_received_check(
                    session,
                    received_check_id=payload["received_check_id"],
                    collection_bank_account_id=payload["collection_bank_account_id"],
                    collection_date=payload["collection_date"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    collected_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                collected_received_check_id = received_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Alınan çek tahsil edildi",
                f"Alınan çek tahsil işlemi başarıyla tamamlandı. Çek ID: {collected_received_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Alınan çek tahsil edilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Alınan çek tahsil edilirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _build_admin_hint_card(self) -> QWidget:
        return InfoCard(
            "Yönetim Hazırlığı",
            "Bu giriş sekmesi artık sadece özet ve operasyon alanına odaklanır. Çek listeleri ayrı sekmelere taşındı.",
            "Kalabalık çıktı, kontrol kaldı.",
        )

    def _build_role_hint_card(self) -> QWidget:
        if self.current_role == "VIEWER":
            return InfoCard(
                "Görüntüleme Modu",
                "Bu kullanıcı çek kayıtlarını görüntüleyebilir. İşlem butonları sonraki adımda yetki bazlı açılacak.",
                "Şimdilik sadece seyirci koltuğu.",
            )

        if self.current_role == "FINANCE":
            return InfoCard(
                "Finans Operasyon Modu",
                "Bu kullanıcı çek ödeme ve tahsil işlemlerini sonraki adımda kullanabilecek.",
                "Çek sahnesi hazırlanıyor.",
            )

        if self.current_role == "DATA_ENTRY":
            return InfoCard(
                "Veri Giriş Modu",
                "Bu kullanıcı çek kayıtlarını girecek; ödeme ve tahsil işlemleri finans yetkisinde olacak.",
                "Veriyi girer, kasayı devirmez.",
            )

        return InfoCard(
            "Sınırlı Erişim",
            "Bu rol için çek yönetim işlemleri sınırlıdır.",
            "Yetki sınırları burada da korunur.",
        )
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
from app.services.pos_device_service import (
    PosDeviceServiceError,
    create_pos_device,
    deactivate_pos_device,
    reactivate_pos_device,
    update_pos_device,
)
from app.services.pos_settlement_service import (
    PosSettlementServiceError,
    cancel_pos_settlement,
    create_pos_settlement,
    realize_pos_settlement,
)
from app.ui.components.info_card import InfoCard
from app.ui.components.summary_card import SummaryCard
from app.ui.pages.pos.pos_admin_data import load_admin_pos_bank_accounts
from app.ui.pages.pos.pos_cancel_dialog import PosCancelDialog
from app.ui.pages.pos.pos_data import (
    build_currency_totals_text,
    format_currency_amount,
    format_rate_percent,
    load_pos_page_data,
    status_text,
)
from app.ui.pages.pos.pos_device_dialog import PosDeviceDialog
from app.ui.pages.pos.pos_device_toggle_dialog import PosDeviceToggleDialog
from app.ui.pages.pos.pos_history_dialog import PosHistoryDialog
from app.ui.pages.pos.pos_manage_dialog import PosManageDialog
from app.ui.pages.pos.pos_realize_dialog import PosRealizeDialog
from app.ui.pages.pos.pos_settlement_dialog import PosSettlementDialog
from app.ui.ui_helpers import clear_layout, tr_number


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


class PosPage(QWidget):
    def __init__(self, current_user: Any) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = _role_text(getattr(current_user, "role", None))
        self.data = load_pos_page_data()

        self.difference_settlement_by_row: dict[int, Any] = {}
        self.settlement_by_row: dict[int, Any] = {}
        self.selected_settlement: Any | None = None

        self.settlement_table: QTableWidget | None = None
        self.selected_record_info_label: QLabel | None = None
        self.create_settlement_button: QPushButton | None = None
        self.realize_settlement_button: QPushButton | None = None
        self.cancel_settlement_button: QPushButton | None = None
        self.history_button: QPushButton | None = None

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(16)

        self._render_page()

    def _render_page(self) -> None:
        clear_layout(self.main_layout)

        self.difference_settlement_by_row = {}
        self.settlement_by_row = {}
        self.selected_settlement = None
        self.settlement_table = None
        self.selected_record_info_label = None
        self.create_settlement_button = None
        self.realize_settlement_button = None
        self.cancel_settlement_button = None
        self.history_button = None

        if self.data.error_message:
            self.main_layout.addWidget(self._build_error_card())
            return

        self.main_layout.addLayout(self._build_summary_cards())
        self.main_layout.addWidget(self._build_settlement_table_card(), 1)
        self.main_layout.addLayout(self._build_action_area())
        self._refresh_operation_controls()

    def _reload_page_data(self) -> None:
        self.data = load_pos_page_data()
        self._render_page()

    def _build_error_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardRisk")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel("POS verileri okunamadı")
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
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        grid.addWidget(
            SummaryCard(
                "BEKLEYEN POS YATIŞLARI",
                build_currency_totals_text(self.data.planned_currency_totals),
                "Planlanan POS net yatış toplamı",
                "highlight",
            ),
            0,
            0,
        )

        grid.addWidget(
            SummaryCard(
                "SON GERÇEKLEŞEN POS",
                build_currency_totals_text(self.data.realized_currency_totals),
                f"Son {self.data.visible_realized_days} gün gerçekleşen POS net yatış toplamı",
                "success",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_pos_status_card(),
            0,
            2,
        )

        return grid

    def _build_pos_status_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(145)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("POS DURUMU")
        title.setObjectName("CardTitle")

        metrics_layout = QGridLayout()
        metrics_layout.setSpacing(10)

        metrics_layout.addWidget(
            self._build_compact_metric(
                "AKTİF",
                tr_number(self.data.active_device_count),
                "Cihaz",
            ),
            0,
            0,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "PASİF",
                tr_number(self.data.passive_device_count),
                "Cihaz",
            ),
            0,
            1,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "BEKLEYEN",
                tr_number(self.data.planned_settlement_count),
                "Yatış",
            ),
            1,
            0,
        )

        metrics_layout.addWidget(
            self._build_compact_metric(
                "FARK",
                tr_number(self.data.mismatch_settlement_count),
                "Kayıt",
            ),
            1,
            1,
        )

        hint = QLabel("POS cihazı ve güncel mutabakat kayıt özeti.")
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

    def _build_settlement_table_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Güncel POS Mutabakat Kayıtları")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            f"Bu listede planlanan kayıtlar, fark olan kayıtlar ve son "
            f"{self.data.visible_realized_days} gün içinde gerçekleşen POS yatışları görünür. "
            f"Eski gerçekleşen kayıtlar Geçmiş İşlemler / Filtreler alanından çağrılabilir."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        table = QTableWidget()
        table.setColumnCount(12)
        table.setHorizontalHeaderLabels(
            [
                "ID",
                "POS",
                "Terminal",
                "Banka",
                "Hesap",
                "İşlem Tarihi",
                "Beklenen Yatış",
                "Brüt",
                "Komisyon",
                "Net",
                "Durum",
                "Fark",
            ]
        )

        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(11, QHeaderView.Fixed)
        table.setColumnWidth(11, 72)
        table.setMinimumHeight(250)
        table.cellClicked.connect(
            lambda row, column: self._handle_settlement_table_cell_clicked(row, column)
        )
        table.itemSelectionChanged.connect(self._handle_settlement_table_selection_changed)

        self.settlement_table = table
        self._fill_settlement_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _fill_settlement_table(self, table: QTableWidget) -> None:
        self.difference_settlement_by_row = {}
        self.settlement_by_row = {}
        self.selected_settlement = None

        table.setRowCount(len(self.data.pos_settlements))

        for row_index, settlement in enumerate(self.data.pos_settlements):
            self.settlement_by_row[row_index] = settlement

            commission_text = (
                f"{format_currency_amount(settlement.commission_amount, settlement.currency_code)} "
                f"({format_rate_percent(settlement.commission_rate)})"
            )

            values = [
                str(settlement.pos_settlement_id),
                settlement.pos_device_name,
                settlement.terminal_no or "-",
                settlement.bank_name,
                settlement.bank_account_name,
                settlement.transaction_date_text,
                settlement.expected_settlement_date_text,
                format_currency_amount(settlement.gross_amount, settlement.currency_code),
                commission_text,
                format_currency_amount(settlement.net_amount, settlement.currency_code),
                status_text(settlement.status),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)

                if settlement.status == "CANCELLED":
                    item.setForeground(QColor("#64748b"))
                elif settlement.status == "MISMATCH":
                    item.setForeground(QColor("#fbbf24"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index in {7, 8, 9}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                if column_index in {9, 10}:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)

                table.setItem(row_index, column_index, item)

            self._set_difference_cell(
                table=table,
                row_index=row_index,
                settlement=settlement,
            )

        table.resizeRowsToContents()

    def _set_difference_cell(
        self,
        *,
        table: QTableWidget,
        row_index: int,
        settlement: Any,
    ) -> None:
        if settlement.status != "MISMATCH":
            item = QTableWidgetItem("-")
            item.setForeground(QColor("#64748b"))
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_index, 11, item)
            return

        self.difference_settlement_by_row[row_index] = settlement

        item = QTableWidgetItem("Detay")
        item.setToolTip("Fark detayını göster")
        item.setTextAlignment(Qt.AlignCenter)

        font = QFont()
        font.setBold(True)
        font.setUnderline(True)
        item.setFont(font)

        item.setForeground(QColor("#38bdf8"))
        table.setItem(row_index, 11, item)

    def _handle_settlement_table_cell_clicked(self, row: int, column: int) -> None:
        if column == 11:
            settlement = self.difference_settlement_by_row.get(row)

            if settlement is not None:
                self._show_difference_detail(settlement)
                return

        settlement = self.settlement_by_row.get(row)
        self.selected_settlement = settlement
        self._refresh_operation_controls()

    def _handle_settlement_table_selection_changed(self) -> None:
        if self.settlement_table is None:
            self.selected_settlement = None
            self._refresh_operation_controls()
            return

        selected_indexes = self.settlement_table.selectionModel().selectedRows()

        if not selected_indexes:
            self.selected_settlement = None
            self._refresh_operation_controls()
            return

        selected_row_index = selected_indexes[0].row()
        self.selected_settlement = self.settlement_by_row.get(selected_row_index)
        self._refresh_operation_controls()

    def _planned_settlements_for_action(self) -> list[Any]:
        if self.selected_settlement is not None and self.selected_settlement.status == "PLANNED":
            return [self.selected_settlement]

        return [
            settlement
            for settlement in self.data.pos_settlements
            if settlement.status == "PLANNED"
        ]

    def _refresh_operation_controls(self) -> None:
        planned_settlements = [
            settlement
            for settlement in self.data.pos_settlements
            if settlement.status == "PLANNED"
        ]
        has_any_planned = len(planned_settlements) > 0

        if self.create_settlement_button is not None:
            self.create_settlement_button.setEnabled(
                self.current_role in {"ADMIN", "FINANCE", "DATA_ENTRY"}
            )

        if self.realize_settlement_button is not None:
            self.realize_settlement_button.setEnabled(
                self.current_role in {"ADMIN", "FINANCE"} and has_any_planned
            )

            if self.selected_settlement is not None and self.selected_settlement.status == "PLANNED":
                self.realize_settlement_button.setText("Seçili POS Yatışını Gerçekleştir")
            else:
                self.realize_settlement_button.setText("POS Yatışını Gerçekleştir")

        if self.cancel_settlement_button is not None:
            self.cancel_settlement_button.setEnabled(
                self.current_role in {"ADMIN", "FINANCE"} and has_any_planned
            )

            if self.selected_settlement is not None and self.selected_settlement.status == "PLANNED":
                self.cancel_settlement_button.setText("Seçili POS Kaydını İptal Et")
            else:
                self.cancel_settlement_button.setText("POS Kaydı İptal Et")

        if self.history_button is not None:
            self.history_button.setEnabled(True)

        if self.selected_record_info_label is not None:
            if self.selected_settlement is None:
                self.selected_record_info_label.setText(
                    "Seçili kayıt yok. Satır seçmezsen Gerçekleştir / İptal işlemleri "
                    "uygun planlanan kayıt listesini açar."
                )
            elif self.selected_settlement.status == "PLANNED":
                self.selected_record_info_label.setText(
                    f"Seçili kayıt: #{self.selected_settlement.pos_settlement_id} / "
                    f"{self.selected_settlement.pos_device_name} / "
                    f"{status_text(self.selected_settlement.status)} / "
                    f"{format_currency_amount(self.selected_settlement.net_amount, self.selected_settlement.currency_code)}. "
                    f"İşlem butonları bu kayda odaklanır."
                )
            else:
                self.selected_record_info_label.setText(
                    f"Seçili kayıt: #{self.selected_settlement.pos_settlement_id} / "
                    f"{self.selected_settlement.pos_device_name} / "
                    f"{status_text(self.selected_settlement.status)}. "
                    f"Bu kayıt planlanan durumda değil. Gerçekleştir / İptal butonları "
                    f"uygun planlanan kayıt listesini açar."
                )

    def _show_difference_detail(self, settlement: Any) -> None:
        expected_net_amount_text = format_currency_amount(
            settlement.net_amount,
            settlement.currency_code,
        )

        actual_net_source = (
            settlement.actual_net_amount
            if settlement.actual_net_amount is not None
            else settlement.net_amount
        )

        actual_net_amount_text = format_currency_amount(
            actual_net_source,
            settlement.currency_code,
        )

        difference_amount_text = format_currency_amount(
            settlement.difference_amount,
            settlement.currency_code,
        )

        difference_reason = (
            settlement.difference_reason.strip()
            if settlement.difference_reason
            else "Fark açıklaması girilmemiş."
        )

        detail_text = (
            f"POS: {settlement.pos_device_name}\n"
            f"Terminal: {settlement.terminal_no or '-'}\n"
            f"Banka: {settlement.bank_name}\n"
            f"Hesap: {settlement.bank_account_name}\n\n"
            f"İşlem Tarihi: {settlement.transaction_date_text}\n"
            f"Beklenen Yatış Tarihi: {settlement.expected_settlement_date_text}\n"
            f"Gerçekleşen Yatış Tarihi: {settlement.realized_settlement_date_text or '-'}\n\n"
            f"Beklenen Net: {expected_net_amount_text}\n"
            f"Gerçekleşen Net: {actual_net_amount_text}\n"
            f"Fark: {difference_amount_text}\n\n"
            f"Açıklama:\n{difference_reason}"
        )

        QMessageBox.information(
            self,
            f"POS Fark Detayı - Kayıt ID: {settlement.pos_settlement_id}",
            detail_text,
        )

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
            "POS satış/yatış kayıtları ve gerçekleşen yatış mutabakatı bu alandan yönetilecek."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        self.create_settlement_button = QPushButton("POS Yatış Kaydı Oluştur")
        self.create_settlement_button.clicked.connect(self._open_create_pos_settlement_dialog)

        self.realize_settlement_button = QPushButton("POS Yatışını Gerçekleştir")
        self.realize_settlement_button.clicked.connect(self._open_realize_pos_settlement_dialog)

        self.cancel_settlement_button = QPushButton("POS Kaydı İptal Et")
        self.cancel_settlement_button.clicked.connect(self._open_cancel_pos_settlement_dialog)

        self.history_button = QPushButton("Geçmiş İşlemler / Filtreler")
        self.history_button.clicked.connect(self._open_pos_history_dialog)

        self.selected_record_info_label = QLabel("")
        self.selected_record_info_label.setObjectName("MutedText")
        self.selected_record_info_label.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(self.create_settlement_button)
        layout.addWidget(self.realize_settlement_button)
        layout.addWidget(self.cancel_settlement_button)
        layout.addWidget(self.history_button)
        layout.addSpacing(8)
        layout.addWidget(self.selected_record_info_label)

        return card

    def _build_admin_management_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardHighlight")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("POS Tanım Yönetimi")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Bu alan sadece ADMIN rolünde görünür. POS cihazı tanımları ve banka hesabı bağlantıları burada yönetilecek."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        add_device_button = QPushButton("POS Cihazı Ekle")
        add_device_button.clicked.connect(self._open_create_pos_device_dialog)

        edit_device_button = QPushButton("POS Cihazı Düzenle")
        edit_device_button.clicked.connect(self._open_manage_pos_device_dialog)

        deactivate_device_button = QPushButton("POS Cihazı Pasifleştir / Aktifleştir")
        deactivate_device_button.clicked.connect(self._open_toggle_pos_device_dialog)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(add_device_button)
        layout.addWidget(edit_device_button)
        layout.addWidget(deactivate_device_button)

        return card

    def _build_limited_access_card(self) -> QWidget:
        if self.current_role == "VIEWER":
            return InfoCard(
                "Görüntüleme Modu",
                "Bu kullanıcı POS kayıtlarını ve mutabakat durumunu görüntüleyebilir. İşlem oluşturma yetkisi yoktur.",
                "VIEWER rolü sadece izler; POS kaydı başlatamaz.",
            )

        if self.current_role == "FINANCE":
            return InfoCard(
                "Finans Operasyon Modu",
                "Bu kullanıcı POS yatışlarını gerçekleştirebilir ve iptal edebilir. POS cihazı tanımları ADMIN yetkisindedir.",
                "Mutabakat finansın işi, cihaz tanımı adminin işi.",
            )

        if self.current_role == "DATA_ENTRY":
            return InfoCard(
                "Veri Giriş Modu",
                "Bu kullanıcı POS satış/yatış kaydı oluşturabilir. Gerçekleştirme ve iptal işlemleri finans yetkisindedir.",
                "Veriyi girer, kasayı bozmaz.",
            )

        return InfoCard(
            "Sınırlı Erişim",
            "Bu rol için POS yönetim işlemleri sınırlıdır.",
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

    def _open_pos_history_dialog(self) -> None:
        dialog = PosHistoryDialog(
            parent=self,
            pos_devices=self.data.pos_devices,
        )
        dialog.exec()

    def _open_create_pos_settlement_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE", "DATA_ENTRY"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN, FINANCE veya DATA_ENTRY yetkisi gerekir.",
            )
            return

        active_pos_devices = [
            pos_device
            for pos_device in self.data.pos_devices
            if pos_device.is_active
        ]

        if not active_pos_devices:
            QMessageBox.information(
                self,
                "Aktif POS cihazı yok",
                "POS yatış kaydı oluşturmak için en az bir aktif POS cihazı gerekir.",
            )
            return

        dialog = PosSettlementDialog(
            parent=self,
            pos_devices=active_pos_devices,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                pos_settlement = create_pos_settlement(
                    session,
                    pos_device_id=payload["pos_device_id"],
                    transaction_date=payload["transaction_date"],
                    gross_amount=payload["gross_amount"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_pos_settlement_id = pos_settlement.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "POS yatış kaydı oluşturuldu",
                f"POS yatış kaydı başarıyla oluşturuldu. Kayıt ID: {created_pos_settlement_id}",
            )

        except PosSettlementServiceError as exc:
            QMessageBox.warning(
                self,
                "POS yatış kaydı oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"POS yatış kaydı oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_realize_pos_settlement_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        planned_settlements = self._planned_settlements_for_action()

        if not planned_settlements:
            QMessageBox.information(
                self,
                "Planlanan kayıt yok",
                "Gerçekleştirilecek planlanan POS yatış kaydı bulunamadı.",
            )
            return

        dialog = PosRealizeDialog(
            parent=self,
            planned_settlements=planned_settlements,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                pos_settlement = realize_pos_settlement(
                    session,
                    pos_settlement_id=payload["pos_settlement_id"],
                    realized_settlement_date=payload["realized_settlement_date"],
                    actual_net_amount=payload["actual_net_amount"],
                    difference_reason=payload["difference_reason"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    realized_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                realized_settlement_id = pos_settlement.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "POS yatışı işlendi",
                f"POS yatış kaydı işlendi. Kayıt ID: {realized_settlement_id}",
            )

        except PosSettlementServiceError as exc:
            QMessageBox.warning(
                self,
                "POS yatışı işlenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"POS yatışı işlenirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_cancel_pos_settlement_dialog(self) -> None:
        if self.current_role not in {"ADMIN", "FINANCE"}:
            QMessageBox.warning(
                self,
                "Yetkisiz işlem",
                "Bu işlem için ADMIN veya FINANCE yetkisi gerekir.",
            )
            return

        planned_settlements = self._planned_settlements_for_action()

        if not planned_settlements:
            QMessageBox.information(
                self,
                "Planlanan kayıt yok",
                "İptal edilecek planlanan POS kaydı bulunamadı.",
            )
            return

        dialog = PosCancelDialog(
            parent=self,
            planned_settlements=planned_settlements,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                pos_settlement = cancel_pos_settlement(
                    session,
                    pos_settlement_id=payload["pos_settlement_id"],
                    cancel_reason=payload["cancel_reason"],
                    cancelled_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                cancelled_settlement_id = pos_settlement.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "POS kaydı iptal edildi",
                f"POS kaydı başarıyla iptal edildi. Kayıt ID: {cancelled_settlement_id}",
            )

        except PosSettlementServiceError as exc:
            QMessageBox.warning(
                self,
                "POS kaydı iptal edilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"POS kaydı iptal edilirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_create_pos_device_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        active_bank_accounts = load_admin_pos_bank_accounts(include_passive=False)

        if not active_bank_accounts:
            QMessageBox.information(
                self,
                "Aktif banka hesabı yok",
                "POS cihazı oluşturmak için önce en az bir aktif banka hesabı gerekir.",
            )
            return

        dialog = PosDeviceDialog(
            parent=self,
            mode="create",
            bank_accounts=active_bank_accounts,
        )

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                pos_device = create_pos_device(
                    session,
                    bank_account_id=payload["bank_account_id"],
                    name=payload["name"],
                    terminal_no=payload["terminal_no"],
                    commission_rate=payload["commission_rate"],
                    settlement_delay_days=payload["settlement_delay_days"],
                    currency_code=payload["currency_code"],
                    notes=payload["notes"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_pos_device_id = pos_device.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "POS cihazı oluşturuldu",
                f"POS cihazı başarıyla oluşturuldu. POS ID: {created_pos_device_id}",
            )

        except PosDeviceServiceError as exc:
            QMessageBox.warning(
                self,
                "POS cihazı oluşturulamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"POS cihazı oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_manage_pos_device_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        dialog = PosManageDialog(parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()
        edit_type = payload["edit_type"]
        data = payload["data"]

        try:
            with session_scope() as session:
                if edit_type != "POS_DEVICE":
                    raise ValueError("Geçersiz POS düzenleme türü.")

                pos_device = update_pos_device(
                    session,
                    pos_device_id=data["pos_device_id"],
                    bank_account_id=data["bank_account_id"],
                    name=data["name"],
                    terminal_no=data["terminal_no"],
                    commission_rate=data["commission_rate"],
                    settlement_delay_days=data["settlement_delay_days"],
                    currency_code=data["currency_code"],
                    notes=data["notes"],
                    is_active=data["is_active"],
                    updated_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                updated_pos_device_id = pos_device.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "POS cihazı güncellendi",
                f"POS cihazı başarıyla güncellendi. POS ID: {updated_pos_device_id}",
            )

        except PosDeviceServiceError as exc:
            QMessageBox.warning(
                self,
                "POS cihazı güncellenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"POS cihazı güncellenirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_toggle_pos_device_dialog(self) -> None:
        if not self._ensure_admin_role():
            return

        dialog = PosDeviceToggleDialog(parent=self)

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        operation_type = payload["operation_type"]
        pos_device_id = payload["pos_device_id"]
        reason = payload["reason"]

        try:
            with session_scope() as session:
                if operation_type == "DEACTIVATE":
                    pos_device = deactivate_pos_device(
                        session,
                        pos_device_id=pos_device_id,
                        deactivate_reason=reason,
                        deactivated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    changed_pos_device_id = pos_device.id
                    success_title = "POS cihazı pasifleştirildi"
                    success_message = (
                        f"POS cihazı başarıyla pasifleştirildi. POS ID: {changed_pos_device_id}"
                    )

                elif operation_type == "REACTIVATE":
                    pos_device = reactivate_pos_device(
                        session,
                        pos_device_id=pos_device_id,
                        reactivate_reason=reason,
                        reactivated_by_user_id=getattr(self.current_user, "id", None),
                        acting_user=self.current_user,
                    )

                    changed_pos_device_id = pos_device.id
                    success_title = "POS cihazı aktifleştirildi"
                    success_message = (
                        f"POS cihazı başarıyla aktifleştirildi. POS ID: {changed_pos_device_id}"
                    )

                else:
                    raise ValueError("Geçersiz POS durum işlemi.")

            self._reload_page_data()

            QMessageBox.information(
                self,
                success_title,
                success_message,
            )

        except PosDeviceServiceError as exc:
            QMessageBox.warning(
                self,
                "POS cihazı durumu değiştirilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"POS cihazı durumu değiştirilirken beklenmeyen bir hata oluştu:\n{exc}",
            )
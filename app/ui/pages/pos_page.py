from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
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

from app.ui.components.info_card import InfoCard
from app.ui.components.summary_card import SummaryCard
from app.ui.pages.pos.pos_data import (
    build_currency_totals_text,
    format_currency_amount,
    format_rate_percent,
    load_pos_page_data,
    status_text,
)
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
        self.main_layout.addWidget(self._build_settlement_table_card(), 1)
        self.main_layout.addLayout(self._build_action_area())

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
            f"Eski gerçekleşen kayıtlar ileride Geçmiş İşlemler filtresinden çağrılacak."
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
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(11, QHeaderView.Fixed)
        table.setColumnWidth(11, 72)
        table.setMinimumHeight(250)
        table.cellClicked.connect(
            lambda row, column: self._handle_settlement_table_cell_clicked(row, column)
        )

        self._fill_settlement_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _fill_settlement_table(self, table: QTableWidget) -> None:
        self.difference_settlement_by_row = {}
        table.setRowCount(len(self.data.pos_settlements))

        for row_index, settlement in enumerate(self.data.pos_settlements):
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
        if column != 11:
            return

        settlement = self.difference_settlement_by_row.get(row)

        if settlement is None:
            return

        self._show_difference_detail(settlement)

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

        create_settlement_button = QPushButton("POS Yatış Kaydı Oluştur")
        create_settlement_button.setEnabled(self.current_role in {"ADMIN", "FINANCE", "DATA_ENTRY"})

        realize_settlement_button = QPushButton("POS Yatışını Gerçekleştir")
        realize_settlement_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})

        cancel_settlement_button = QPushButton("POS Kaydı İptal Et")
        cancel_settlement_button.setEnabled(self.current_role in {"ADMIN", "FINANCE"})

        history_button = QPushButton("Geçmiş İşlemler / Filtreler")
        history_button.setEnabled(False)
        history_button.setToolTip("Bu alan bir sonraki adımda tarih ve durum filtresiyle aktif edilecek.")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(create_settlement_button)
        layout.addWidget(realize_settlement_button)
        layout.addWidget(cancel_settlement_button)
        layout.addWidget(history_button)

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
        edit_device_button = QPushButton("POS Cihazı Düzenle")
        deactivate_device_button = QPushButton("POS Cihazı Pasifleştir / Aktifleştir")

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
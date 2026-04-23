from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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
        self.main_layout.addWidget(self._build_issued_checks_card(), 1)
        self.main_layout.addWidget(self._build_received_checks_card(), 1)
        self.main_layout.addLayout(self._build_action_area())

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

    def _build_issued_checks_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Yazılan Çekler")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Tedarikçilere yazılan çeklerin vade, durum ve banka hesabı görünümü."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

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
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(240)

        self._fill_issued_checks_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _fill_issued_checks_table(self, table: QTableWidget) -> None:
        table.setRowCount(len(self.data.issued_checks))

        for row_index, issued_check in enumerate(self.data.issued_checks):
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

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _build_received_checks_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Alınan Çekler")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Müşterilerden alınan çeklerin çek bankası, tahsil hesabı, vade ve durum görünümü."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

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
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(240)

        self._fill_received_checks_table(table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(table, 1)

        return card

    def _fill_received_checks_table(self, table: QTableWidget) -> None:
        table.setRowCount(len(self.data.received_checks))

        for row_index, received_check in enumerate(self.data.received_checks):
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

                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()

    def _build_action_area(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(16)

        grid.addWidget(self._build_operation_card(), 0, 0)

        if self.current_role == "ADMIN":
            grid.addWidget(self._build_admin_hint_card(), 0, 1)
        else:
            grid.addWidget(self._build_role_hint_card(), 0, 1)

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
            "Yazılan ve alınan çek işlemleri bir sonraki adımda gerçek formlara bağlanacak."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)

        create_issued_button = QPushButton("Yazılan Çek Oluştur")
        create_issued_button.setEnabled(False)

        pay_issued_button = QPushButton("Yazılan Çek Ödendi")
        pay_issued_button.setEnabled(False)

        create_received_button = QPushButton("Alınan Çek Oluştur")
        create_received_button.setEnabled(False)

        collect_received_button = QPushButton("Alınan Çek Tahsil Et")
        collect_received_button.setEnabled(False)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addWidget(create_issued_button)
        layout.addWidget(pay_issued_button)
        layout.addWidget(create_received_button)
        layout.addWidget(collect_received_button)

        return card

    def _build_admin_hint_card(self) -> QWidget:
        return InfoCard(
            "Yönetim Hazırlığı",
            "Çek ekranı artık gerçek veriyle çalışıyor. Sonraki adımda yazılan/alınan çek formları ve tahsil/ödeme işlemleri bağlanacak.",
            "Temel atıldı; sıra kas gücünde.",
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
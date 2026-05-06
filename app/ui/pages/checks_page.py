from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.db.session import session_scope
from app.services.check_service import (
    CheckServiceError,
    cancel_issued_check,
    collect_received_check,
    create_issued_check,
    create_received_check,
    discount_received_check,
    mark_received_check_bounced,
    mark_received_check_returned,
    pay_issued_check,
    send_received_check_to_bank,
)

from app.services.received_check_discount_batch_service import (
    ReceivedCheckDiscountBatchServiceError,
    create_received_check_discount_batch,
)
from app.services.permission_service import Permission

try:
    from app.services.check_service import endorse_received_check
except ImportError:
    endorse_received_check = None

from app.ui.pages.checks.checks_data import (
    DEFAULT_CHECK_TABLE_PAGE_SIZE,
    build_currency_totals_text,
    format_currency_amount,
    issued_status_text,
    load_checks_page_data,
    load_issued_checks_table_data,
    load_received_checks_table_data,
    received_status_text as base_received_status_text,
)
from app.ui.pages.checks.issued_check_create_dialog import IssuedCheckCreateDialog
from app.ui.pages.checks.issued_check_detail_dialog import IssuedCheckDetailDialog
from app.ui.pages.checks.issued_check_cancel_dialog import IssuedCheckCancelDialog
from app.ui.pages.checks.issued_check_pay_dialog import IssuedCheckPayDialog
from app.ui.pages.checks.received_check_collect_dialog import ReceivedCheckCollectDialog
from app.ui.pages.checks.received_check_create_dialog import ReceivedCheckCreateDialog
from app.ui.pages.checks.received_check_bounce_dialog import ReceivedCheckBounceDialog
from app.ui.pages.checks.received_check_return_dialog import ReceivedCheckReturnDialog
from app.ui.pages.checks.checks_report_dialog import ChecksReportDialog
from app.ui.pages.checks.received_check_detail_dialog import ReceivedCheckDetailDialog
from app.ui.pages.checks.received_check_discount_dialog import ReceivedCheckDiscountDialog
from app.ui.pages.checks.received_check_discount_batch_dialog import ReceivedCheckDiscountBatchDialog
from app.ui.pages.checks.received_check_discount_batches_dialog import ReceivedCheckDiscountBatchesDialog
from app.ui.pages.checks.received_check_send_to_bank_dialog import ReceivedCheckSendToBankDialog

try:
    from app.ui.pages.checks.received_check_endorse_dialog import ReceivedCheckEndorseDialog
except ImportError:
    ReceivedCheckEndorseDialog = None

from app.ui.permission_ui import (
    apply_any_permission_to_button,
    apply_permission_to_button,
    user_has_any_permission,
    user_has_permission,
)
from app.ui.ui_helpers import clear_layout, decimal_or_zero, tr_number


CHECK_LIST_PAGE_SIZE = DEFAULT_CHECK_TABLE_PAGE_SIZE


ISSUED_OPEN_STATUSES = {
    "PREPARED",
    "GIVEN",
}

ISSUED_PROBLEM_STATUSES = {
    "RISK",
}

ISSUED_CLOSED_STATUSES = {
    "PAID",
    "CANCELLED",
}

RECEIVED_OPEN_STATUSES = {
    "PORTFOLIO",
    "GIVEN_TO_BANK",
    "IN_COLLECTION",
}

RECEIVED_PROBLEM_STATUSES = {
    "BOUNCED",
}

RECEIVED_CLOSED_STATUSES = {
    "COLLECTED",
    "ENDORSED",
    "DISCOUNTED",
    "RETURNED",
    "CANCELLED",
}


FILTER_OPTIONS = [
    ("OPEN", "Açık Çekler"),
    ("PROBLEM", "Problemli"),
    ("CLOSED", "Sonuçlananlar"),
    ("ALL", "Tümü"),
]


ISSUED_TABLE_SORT_COLUMNS = {
    0: ("id", "ID"),
    1: ("supplier_name", "Tedarikçi"),
    2: ("bank_account", "Banka / Hesap"),
    3: ("check_number", "Çek No"),
    4: ("issue_date", "Keşide"),
    5: ("due_date", "Vade"),
    6: ("amount", "Tutar"),
    7: ("status", "Durum"),
    8: ("reference_no", "Referans"),
}


RECEIVED_TABLE_SORT_COLUMNS = {
    0: ("id", "ID"),
    1: ("customer_name", "Müşteri"),
    2: ("drawer_bank_name", "Keşideci Banka"),
    3: ("collection_account", "Tahsil Hesabı"),
    4: ("check_number", "Çek No"),
    5: ("received_date", "Alınış"),
    6: ("due_date", "Vade"),
    7: ("amount", "Tutar"),
    8: ("status", "Durum"),
    9: ("reference_no", "Referans"),
}


SORT_DEFAULT_DIRECTIONS = {
    "id": "ASC",
    "supplier_name": "ASC",
    "customer_name": "ASC",
    "bank_account": "ASC",
    "drawer_bank_name": "ASC",
    "collection_account": "ASC",
    "check_number": "ASC",
    "issue_date": "ASC",
    "received_date": "ASC",
    "due_date": "ASC",
    "amount": "DESC",
    "status": "ASC",
    "reference_no": "ASC",
}


def _role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


def _normalize_search_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _sort_direction_symbol(sort_direction: str) -> str:
    return "↓" if str(sort_direction or "").strip().upper() == "DESC" else "↑"


def received_status_text(status: str) -> str:
    normalized_status = str(status or "").strip().upper()

    if normalized_status == "DISCOUNTED":
        return "İskontoya Verildi"

    return base_received_status_text(status)


class ChecksPage(QWidget):
    def __init__(self, current_user: Any) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = _role_text(getattr(current_user, "role", None))
        self.data = load_checks_page_data()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

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

    def _build_error_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardRisk")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

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
        grid.setSpacing(10)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 2)

        grid.addWidget(
            self._build_simple_summary_card(
                title="YAZILAN ÇEK YÜKÜ",
                value=build_currency_totals_text(self.data.pending_issued_currency_totals),
                hint=f"{tr_number(self.data.pending_issued_count)} açık yazılan çek",
                card_type="risk",
            ),
            0,
            0,
        )

        grid.addWidget(
            self._build_simple_summary_card(
                title="ALINAN ÇEK PORTFÖYÜ",
                value=build_currency_totals_text(self.data.pending_received_currency_totals),
                hint=f"{tr_number(self.data.pending_received_count)} açık alınan çek",
                card_type="success",
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

    def _build_simple_summary_card(
        self,
        *,
        title: str,
        value: str,
        hint: str,
        card_type: str,
    ) -> QWidget:
        card = QFrame()

        if card_type == "risk":
            card.setObjectName("CardRisk")
        elif card_type == "success":
            card.setObjectName("CardSuccess")
        else:
            card.setObjectName("Card")

        card.setMinimumHeight(124)
        card.setMaximumHeight(132)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")
        value_label.setWordWrap(True)

        hint_label = QLabel(hint)
        hint_label.setObjectName("CardHint")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)

        return card

    def _build_check_status_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(124)
        card.setMaximumHeight(132)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("ÇEK DURUMU")
        title.setObjectName("CardTitle")

        metrics_layout = QGridLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(14)
        metrics_layout.setVerticalSpacing(8)
        metrics_layout.setColumnStretch(0, 1)
        metrics_layout.setColumnStretch(1, 1)

        metrics_layout.addWidget(
            self._build_status_line(
                "7 Gün / Yazılan",
                tr_number(self.data.issued_due_soon_count),
            ),
            0,
            0,
        )

        metrics_layout.addWidget(
            self._build_status_line(
                "7 Gün / Alınan",
                tr_number(self.data.received_due_soon_count),
            ),
            0,
            1,
        )

        metrics_layout.addWidget(
            self._build_status_line(
                "Yazılan Risk",
                tr_number(self.data.issued_problem_count),
            ),
            1,
            0,
        )

        metrics_layout.addWidget(
            self._build_status_line(
                "Alınan Problem",
                tr_number(self.data.received_problem_count),
            ),
            1,
            1,
        )

        layout.addWidget(title)
        layout.addLayout(metrics_layout)

        return card

    def _build_status_line(self, title_text: str, value_text: str) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            """
            QFrame {
                background-color: rgba(15, 23, 42, 0.32);
                border: 1px solid rgba(148, 163, 184, 0.18);
                border-radius: 8px;
            }
            """
        )

        layout = QHBoxLayout(box)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setStyleSheet(
            """
            QLabel {
                color: #bfdbfe;
                font-size: 11px;
                font-weight: 700;
                border: none;
                background-color: transparent;
            }
            """
        )

        value = QLabel(value_text)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: 800;
                border: none;
                background-color: transparent;
            }
            """
        )

        layout.addWidget(title, 1)
        layout.addWidget(value)

        return box

    def _build_checks_tabs(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

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
                padding: 8px 16px;
                margin-right: 5px;
                min-width: 112px;
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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        layout.addLayout(self._build_overview_status_cards())
        layout.addLayout(self._build_overview_action_area())
        layout.addStretch()

        return page

    def _build_overview_status_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)
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
        card.setMinimumHeight(88)
        card.setMaximumHeight(96)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

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
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)

        grid.addWidget(self._build_operation_card(), 0, 0)

        return grid

    def _build_admin_hint_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Admin Yetkisi")
        title.setObjectName("SectionTitle")

        body = QLabel(
            "Bu kullanıcı ADMIN rolünde olduğu için çek oluşturma, ödeme, tahsil, bankaya gönderme, "
            "ciro ve iskonto/kırdırma işlemlerinin tamamını çalıştırabilir."
        )
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch()

        return card

    def _build_role_hint_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Rol Bilgisi")
        title.setObjectName("SectionTitle")

        body = QLabel(
            f"Aktif rol: {self.current_role or '-'}\n"
            "Butonlar role_permissions tablosundaki gerçek yetkilere göre açılır veya pasif kalır. "
            "Yetkisiz denemeler servis tarafında da engellenir."
        )
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch()

        return card

    def _build_issued_checks_tab(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

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
        table.setSortingEnabled(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.verticalHeader().setMinimumSectionSize(32)
        table.horizontalHeader().setMinimumSectionSize(60)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionsClickable(True)
        table.horizontalHeader().setSortIndicatorShown(True)

    def _filter_issued_rows(self, rows: list[Any], filter_key: str) -> list[Any]:
        normalized_filter_key = str(filter_key or "OPEN").strip().upper()

        if normalized_filter_key == "OPEN":
            return [
                issued_check
                for issued_check in rows
                if str(issued_check.status or "").strip().upper() in ISSUED_OPEN_STATUSES
            ]

        if normalized_filter_key == "PROBLEM":
            return [
                issued_check
                for issued_check in rows
                if str(issued_check.status or "").strip().upper() in ISSUED_PROBLEM_STATUSES
            ]

        if normalized_filter_key == "CLOSED":
            return [
                issued_check
                for issued_check in rows
                if str(issued_check.status or "").strip().upper() in ISSUED_CLOSED_STATUSES
            ]

        return rows

    def _filter_received_rows(self, rows: list[Any], filter_key: str) -> list[Any]:
        normalized_filter_key = str(filter_key or "OPEN").strip().upper()

        if normalized_filter_key == "OPEN":
            return [
                received_check
                for received_check in rows
                if str(received_check.status or "").strip().upper() in RECEIVED_OPEN_STATUSES
            ]

        if normalized_filter_key == "PROBLEM":
            return [
                received_check
                for received_check in rows
                if str(received_check.status or "").strip().upper() in RECEIVED_PROBLEM_STATUSES
            ]

        if normalized_filter_key == "CLOSED":
            return [
                received_check
                for received_check in rows
                if str(received_check.status or "").strip().upper() in RECEIVED_CLOSED_STATUSES
            ]

        return rows

    def _issued_row_matches_search(self, issued_check: Any, search_text: str) -> bool:
        normalized_search_text = _normalize_search_text(search_text)

        if not normalized_search_text:
            return True

        searchable_text = " | ".join(
            [
                str(issued_check.issued_check_id),
                issued_check.supplier_name,
                issued_check.bank_name,
                issued_check.bank_account_name,
                issued_check.check_number,
                issued_check.issue_date_text,
                issued_check.due_date_text,
                format_currency_amount(issued_check.amount, issued_check.currency_code),
                issued_status_text(issued_check.status),
                issued_check.reference_no or "",
                issued_check.description or "",
            ]
        )

        return normalized_search_text in _normalize_search_text(searchable_text)

    def _received_row_matches_search(self, received_check: Any, search_text: str) -> bool:
        normalized_search_text = _normalize_search_text(search_text)

        if not normalized_search_text:
            return True

        collection_text = (
            f"{received_check.collection_bank_name} / {received_check.collection_bank_account_name}"
            if received_check.collection_bank_name and received_check.collection_bank_account_name
            else ""
        )

        searchable_text = " | ".join(
            [
                str(received_check.received_check_id),
                received_check.customer_name,
                received_check.drawer_bank_name,
                collection_text,
                received_check.check_number,
                received_check.received_date_text,
                received_check.due_date_text,
                format_currency_amount(received_check.amount, received_check.currency_code),
                received_status_text(received_check.status),
                received_check.reference_no or "",
                received_check.description or "",
            ]
        )

        return normalized_search_text in _normalize_search_text(searchable_text)

    def _style_filter_buttons(self, buttons: dict[str, QPushButton], active_key: str) -> None:
        normalized_active_key = str(active_key or "OPEN").strip().upper()

        for filter_key, button in buttons.items():
            if filter_key == normalized_active_key:
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        border: 1px solid #3b82f6;
                        border-radius: 9px;
                        padding: 6px 12px;
                        font-weight: 700;
                    }

                    QPushButton:hover {
                        background-color: #1d4ed8;
                    }
                    """
                )
            else:
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #172033;
                        color: #cbd5e1;
                        border: 1px solid #24324a;
                        border-radius: 9px;
                        padding: 6px 12px;
                        font-weight: 600;
                    }

                    QPushButton:hover {
                        background-color: #1e293b;
                        color: #ffffff;
                    }
                    """
                )

    def _build_table_tools_layout(
        self,
        *,
        search_input: QLineEdit,
        filter_buttons: dict[str, QPushButton],
        result_label: QLabel,
        previous_button: QPushButton,
        next_button: QPushButton,
    ) -> QVBoxLayout:
        tools_layout = QVBoxLayout()
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(7)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = QLabel("Ara")
        search_label.setObjectName("MutedText")

        search_input.setMinimumHeight(34)
        search_input.setPlaceholderText("Müşteri / tedarikçi / çek no / banka / referans ara")

        result_label.setObjectName("MutedText")
        result_label.setWordWrap(True)

        search_row.addWidget(search_label)
        search_row.addWidget(search_input, 1)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(7)

        for filter_key, filter_text in FILTER_OPTIONS:
            button = QPushButton(filter_text)
            button.setMinimumHeight(32)
            filter_buttons[filter_key] = button
            filter_row.addWidget(button)

        filter_row.addStretch(1)

        previous_button.setText("Önceki")
        next_button.setText("Sonraki")
        previous_button.setMinimumHeight(32)
        next_button.setMinimumHeight(32)

        previous_button.setStyleSheet(
            """
            QPushButton {
                background-color: #172033;
                color: #cbd5e1;
                border: 1px solid #24324a;
                border-radius: 9px;
                padding: 6px 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #1e293b;
                color: #ffffff;
            }

            QPushButton:disabled {
                background-color: #111827;
                color: #475569;
                border: 1px solid #1e293b;
            }
            """
        )

        next_button.setStyleSheet(previous_button.styleSheet())

        filter_row.addWidget(previous_button)
        filter_row.addWidget(next_button)

        tools_layout.addLayout(search_row)
        tools_layout.addLayout(filter_row)
        tools_layout.addWidget(result_label)

        return tools_layout

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
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(9)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MutedText")
        subtitle_label.setWordWrap(True)

        search_input = QLineEdit()
        result_label = QLabel("")
        selected_summary_label = QLabel("")
        selected_summary_label.setObjectName("MutedText")
        selected_summary_label.setWordWrap(True)
        previous_button = QPushButton()
        next_button = QPushButton()
        filter_buttons: dict[str, QPushButton] = {}

        tools_layout = self._build_table_tools_layout(
            search_input=search_input,
            filter_buttons=filter_buttons,
            result_label=result_label,
            previous_button=previous_button,
            next_button=next_button,
        )

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
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.doubleClicked.connect(lambda _index: self._open_issued_check_detail_from_table(table))
        table.setMinimumHeight(260)

        self._configure_table_for_compact_view(table)
        self._configure_issued_table_columns(table)

        selected_action_panel = self._build_issued_selection_action_panel(table)

        state = {
            "filter_key": "OPEN",
            "page_index": 0,
            "sort_key": "due_date",
            "sort_direction": "ASC",
            "sort_column_index": 5,
            "sort_label": "Vade",
        }

        def refresh_selection_summary() -> None:
            self._refresh_selected_checks_summary(
                table=table,
                summary_label=selected_summary_label,
                empty_text="Seçili yazılan çek yok. Çoklu seçim için Ctrl veya Shift ile satır seçebilirsin.",
                selected_prefix="Seçili yazılan çek",
            )

        def refresh_table() -> None:
            filter_key = str(state["filter_key"])
            page_index = int(state["page_index"])
            search_text = search_input.text().strip()
            sort_key = str(state["sort_key"])
            sort_direction = str(state["sort_direction"])
            sort_column_index = int(state["sort_column_index"])

            table_data = load_issued_checks_table_data(
                search_text=search_text,
                filter_key=filter_key,
                sort_key=sort_key,
                sort_direction=sort_direction,
                page_index=page_index,
                page_size=CHECK_LIST_PAGE_SIZE,
            )

            if table_data.error_message:
                self._fill_issued_checks_table(table, [])
                refresh_selection_summary()
                previous_button.setEnabled(False)
                next_button.setEnabled(False)
                result_label.setText(f"Çek listesi okunamadı: {table_data.error_message}")
                return

            state["page_index"] = table_data.page_index
            self._fill_issued_checks_table(table, table_data.rows)
            refresh_selection_summary()
            self._style_filter_buttons(filter_buttons, filter_key)

            table.horizontalHeader().setSortIndicator(
                sort_column_index,
                Qt.DescendingOrder if sort_direction == "DESC" else Qt.AscendingOrder,
            )

            previous_button.setEnabled(table_data.page_index > 0)
            next_button.setEnabled(table_data.page_index + 1 < table_data.total_pages)

            if table_data.total_count == 0:
                result_label.setText(
                    f"{self._filter_label(filter_key)}: filtreye uygun kayıt bulunamadı. "
                    f"Sıralama: {state['sort_label']} {_sort_direction_symbol(sort_direction)}"
                )
            else:
                start_index = table_data.page_index * table_data.page_size + 1
                end_index = start_index + len(table_data.rows) - 1
                result_label.setText(
                    f"{self._filter_label(filter_key)}: {start_index}-{end_index} / "
                    f"{table_data.total_count} kayıt gösteriliyor. "
                    f"Sayfa: {table_data.page_index + 1}/{table_data.total_pages}. "
                    f"Toplam: {build_currency_totals_text(table_data.currency_totals)} | "
                    f"Sıralama: {state['sort_label']} {_sort_direction_symbol(sort_direction)}"
                )

        def change_filter(filter_key: str) -> None:
            state["filter_key"] = filter_key
            state["page_index"] = 0
            refresh_table()

        def search_changed() -> None:
            state["page_index"] = 0
            refresh_table()

        def previous_page() -> None:
            state["page_index"] = max(0, int(state["page_index"]) - 1)
            refresh_table()

        def next_page() -> None:
            state["page_index"] = int(state["page_index"]) + 1
            refresh_table()

        def change_sort(column_index: int) -> None:
            if column_index not in ISSUED_TABLE_SORT_COLUMNS:
                return

            sort_key, sort_label = ISSUED_TABLE_SORT_COLUMNS[column_index]

            if state["sort_key"] == sort_key:
                state["sort_direction"] = "DESC" if state["sort_direction"] == "ASC" else "ASC"
            else:
                state["sort_key"] = sort_key
                state["sort_direction"] = SORT_DEFAULT_DIRECTIONS.get(sort_key, "ASC")

            state["sort_column_index"] = column_index
            state["sort_label"] = sort_label
            state["page_index"] = 0
            refresh_table()

        for filter_key, button in filter_buttons.items():
            button.clicked.connect(lambda checked=False, selected_filter_key=filter_key: change_filter(selected_filter_key))

        search_input.textChanged.connect(lambda _text: search_changed())
        previous_button.clicked.connect(previous_page)
        next_button.clicked.connect(next_page)
        table.horizontalHeader().sectionClicked.connect(change_sort)
        table.itemSelectionChanged.connect(refresh_selection_summary)

        refresh_table()

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addLayout(tools_layout)
        layout.addWidget(selected_summary_label)
        layout.addWidget(selected_action_panel)
        layout.addWidget(table, 1)

        return card

    def _build_context_action_button(
        self,
        text: str,
        callback: Any,
        *,
        button_type: str = "normal",
        required_permission: Permission | None = None,
        required_permissions: tuple[Permission, ...] | None = None,
        tooltip_when_denied: str = "Bu işlem için mevcut rolün yetkili değil.",
    ) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumHeight(34)
        button.setCursor(Qt.PointingHandCursor)

        if button_type == "risk":
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(127, 29, 29, 0.40);
                    color: #fee2e2;
                    border: 1px solid rgba(239, 68, 68, 0.52);
                    border-radius: 9px;
                    padding: 7px 11px;
                    font-weight: 700;
                }

                QPushButton:hover {
                    background-color: rgba(153, 27, 27, 0.68);
                    color: #ffffff;
                }

                QPushButton:disabled {
                    background-color: #111827;
                    color: #475569;
                    border: 1px solid #1e293b;
                }
                """
            )
        elif button_type == "success":
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(6, 78, 59, 0.40);
                    color: #d1fae5;
                    border: 1px solid rgba(16, 185, 129, 0.48);
                    border-radius: 9px;
                    padding: 7px 11px;
                    font-weight: 700;
                }

                QPushButton:hover {
                    background-color: rgba(5, 150, 105, 0.60);
                    color: #ffffff;
                }

                QPushButton:disabled {
                    background-color: #111827;
                    color: #475569;
                    border: 1px solid #1e293b;
                }
                """
            )
        elif button_type == "primary":
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: 1px solid #3b82f6;
                    border-radius: 9px;
                    padding: 7px 11px;
                    font-weight: 800;
                }

                QPushButton:hover {
                    background-color: #1d4ed8;
                }

                QPushButton:disabled {
                    background-color: #111827;
                    color: #475569;
                    border: 1px solid #1e293b;
                }
                """
            )
        else:
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #172033;
                    color: #cbd5e1;
                    border: 1px solid #24324a;
                    border-radius: 9px;
                    padding: 7px 11px;
                    font-weight: 650;
                }

                QPushButton:hover {
                    background-color: #1e293b;
                    color: #ffffff;
                }

                QPushButton:disabled {
                    background-color: #111827;
                    color: #475569;
                    border: 1px solid #1e293b;
                }
                """
            )

        if required_permissions is not None:
            apply_any_permission_to_button(
                button,
                current_user=self.current_user,
                permissions=required_permissions,
                tooltip_when_denied=tooltip_when_denied,
            )
        elif required_permission is not None:
            apply_permission_to_button(
                button,
                current_user=self.current_user,
                permission=required_permission,
                tooltip_when_denied=tooltip_when_denied,
            )

        button.clicked.connect(lambda checked=False: callback())

        return button

    def _build_context_panel_frame(
        self,
        *,
        title_text: str,
        hint_text: str,
        buttons: list[QPushButton],
    ) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        panel.setStyleSheet(
            """
            QFrame#Card {
                background-color: rgba(15, 23, 42, 0.48);
                border: 1px solid #24324a;
                border-radius: 12px;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")

        hint = QLabel(hint_text)
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        for button in buttons:
            button_row.addWidget(button)

        button_row.addStretch(1)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(button_row)

        return panel

    def _require_selected_checks(
        self,
        *,
        table: QTableWidget,
        title: str,
        message: str,
    ) -> list[int]:
        selected_ids = self._selected_check_ids_from_table(table)

        if not selected_ids:
            QMessageBox.information(
                self,
                title,
                message,
            )
            return []

        return selected_ids

    def _open_issued_selected_detail(self, table: QTableWidget) -> None:
        selected_ids = self._require_selected_checks(
            table=table,
            title="Yazılan çek seçilmedi",
            message="Detayını açmak için bir yazılan çek seçmelisin.",
        )

        if not selected_ids:
            return

        if len(selected_ids) != 1:
            QMessageBox.information(
                self,
                "Tek çek seçilmeli",
                "Detay ekranı için aynı anda sadece bir yazılan çek seçmelisin.",
            )
            return

        dialog = IssuedCheckDetailDialog(
            issued_check_id=selected_ids[0],
            parent=self,
        )
        dialog.exec()

    def _open_received_selected_detail(self, table: QTableWidget) -> None:
        selected_ids = self._require_selected_checks(
            table=table,
            title="Alınan çek seçilmedi",
            message="Detayını açmak için bir alınan çek seçmelisin.",
        )

        if not selected_ids:
            return

        if len(selected_ids) != 1:
            QMessageBox.information(
                self,
                "Tek çek seçilmeli",
                "Detay ekranı için aynı anda sadece bir alınan çek seçmelisin.",
            )
            return

        dialog = ReceivedCheckDetailDialog(
            received_check_id=selected_ids[0],
            parent=self,
        )
        dialog.exec()

    def _open_existing_dialog_for_selected_checks(
        self,
        *,
        table: QTableWidget,
        no_selection_title: str,
        no_selection_message: str,
        action: Any,
    ) -> None:
        selected_ids = self._require_selected_checks(
            table=table,
            title=no_selection_title,
            message=no_selection_message,
        )

        if not selected_ids:
            return

        action()

    def _build_issued_selection_action_panel(self, table: QTableWidget) -> QWidget:
        buttons = [
            self._build_context_action_button(
                "Detay Aç",
                lambda: self._open_issued_selected_detail(table),
                button_type="primary",
            ),
            self._build_context_action_button(
                "Ödeme Ekranını Aç",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Yazılan çek seçilmedi",
                    no_selection_message="Ödeme işlemi için önce en az bir yazılan çek seçmelisin.",
                    action=self._open_pay_issued_check_dialog,
                ),
                button_type="risk",
                required_permission=Permission.ISSUED_CHECK_PAY,
                tooltip_when_denied="Yazılan çek ödeme yetkin yok.",
            ),
            self._build_context_action_button(
                "İptal Ekranını Aç",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Yazılan çek seçilmedi",
                    no_selection_message="İptal işlemi için önce en az bir yazılan çek seçmelisin.",
                    action=self._open_cancel_issued_check_dialog,
                ),
                button_type="normal",
                required_permission=Permission.ISSUED_CHECK_CANCEL,
                tooltip_when_denied="Yazılan çek iptal etme yetkin yok.",
            ),
            self._build_context_action_button(
                "Seçimi Temizle",
                table.clearSelection,
                button_type="normal",
            ),
        ]

        return self._build_context_panel_frame(
            title_text="Seçili Yazılan Çek İşlemleri",
            hint_text=(
                "Bu panel seçili yazılan çeklere göre çalışır. Bu adımda güvenli şekilde mevcut ödeme/iptal "
                "ekranları açılır; seçili çekleri doğrudan toplu işleme gönderme sonraki adımda eklenecek."
            ),
            buttons=buttons,
        )

    def _build_received_selection_action_panel(self, table: QTableWidget) -> QWidget:
        buttons = [
            self._build_context_action_button(
                "Detay Aç",
                lambda: self._open_received_selected_detail(table),
                button_type="primary",
            ),
            self._build_context_action_button(
                "Bankaya Ver",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Alınan çek seçilmedi",
                    no_selection_message="Bankaya verme işlemi için önce en az bir alınan çek seçmelisin.",
                    action=self._open_send_received_check_to_bank_dialog,
                ),
                button_type="success",
                required_permission=Permission.RECEIVED_CHECK_SEND_TO_BANK,
                tooltip_when_denied="Alınan çeki bankaya gönderme yetkin yok.",
            ),
            self._build_context_action_button(
                "Ciro Et",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Alınan çek seçilmedi",
                    no_selection_message="Ciro işlemi için önce en az bir alınan çek seçmelisin.",
                    action=self._open_endorse_received_check_dialog,
                ),
                button_type="success",
                required_permission=Permission.RECEIVED_CHECK_ENDORSE,
                tooltip_when_denied="Alınan çeki ciro etme yetkin yok.",
            ),
            self._build_context_action_button(
                "İskonto / Kırdır",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Alınan çek seçilmedi",
                    no_selection_message="İskonto işlemi için önce en az bir alınan çek seçmelisin.",
                    action=self._open_discount_received_check_dialog,
                ),
                button_type="success",
                required_permission=Permission.RECEIVED_CHECK_DISCOUNT,
                tooltip_when_denied="Alınan çeki iskonto etme yetkin yok.",
            ),
            self._build_context_action_button(
                "Tahsil Et",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Alınan çek seçilmedi",
                    no_selection_message="Tahsil işlemi için önce en az bir alınan çek seçmelisin.",
                    action=self._open_collect_received_check_dialog,
                ),
                button_type="success",
                required_permission=Permission.RECEIVED_CHECK_COLLECT,
                tooltip_when_denied="Alınan çek tahsil etme yetkin yok.",
            ),
            self._build_context_action_button(
                "Karşılıksız",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Alınan çek seçilmedi",
                    no_selection_message="Karşılıksız işaretleme için önce en az bir alınan çek seçmelisin.",
                    action=self._open_bounce_received_check_dialog,
                ),
                button_type="risk",
                required_permission=Permission.RECEIVED_CHECK_CANCEL,
                tooltip_when_denied="Alınan çeki problemli/karşılıksız işaretleme yetkin yok.",
            ),
            self._build_context_action_button(
                "İade",
                lambda: self._open_existing_dialog_for_selected_checks(
                    table=table,
                    no_selection_title="Alınan çek seçilmedi",
                    no_selection_message="İade işlemi için önce en az bir alınan çek seçmelisin.",
                    action=self._open_return_received_check_dialog,
                ),
                button_type="normal",
                required_permission=Permission.RECEIVED_CHECK_CANCEL,
                tooltip_when_denied="Alınan çeki iade işaretleme yetkin yok.",
            ),
            self._build_context_action_button(
                "Seçimi Temizle",
                table.clearSelection,
                button_type="normal",
            ),
        ]

        return self._build_context_panel_frame(
            title_text="Seçili Alınan Çek İşlemleri",
            hint_text=(
                "Bu panel seçili alınan çeklere göre çalışır. Bu adımda mevcut sağlam işlem ekranları açılır; "
                "seçili çek ID'lerini doğrudan toplu işleme taşıma sonraki adımda yapılacak."
            ),
            buttons=buttons,
        )

    def _filter_label(self, filter_key: str) -> str:
        normalized_filter_key = str(filter_key or "OPEN").strip().upper()

        for option_key, option_text in FILTER_OPTIONS:
            if option_key == normalized_filter_key:
                return option_text

        return "Tümü"

    def _selected_row_indexes_from_table(self, table: QTableWidget) -> list[int]:
        selection_model = table.selectionModel()

        if selection_model is None:
            return []

        return sorted(
            {
                selected_index.row()
                for selected_index in selection_model.selectedRows()
                if selected_index.row() >= 0
            }
        )

    def _selected_check_ids_from_table(self, table: QTableWidget) -> list[int]:
        selected_ids: list[int] = []

        for row_index in self._selected_row_indexes_from_table(table):
            id_item = table.item(row_index, 0)

            if id_item is None:
                continue

            check_id = id_item.data(Qt.UserRole)

            if check_id in {None, ""}:
                check_id = id_item.text()

            try:
                selected_ids.append(int(check_id))
            except (TypeError, ValueError):
                continue

        return selected_ids

    def _refresh_selected_checks_summary(
        self,
        *,
        table: QTableWidget,
        summary_label: QLabel,
        empty_text: str,
        selected_prefix: str,
    ) -> None:
        selected_rows = self._selected_row_indexes_from_table(table)

        if not selected_rows:
            summary_label.setText(empty_text)
            return

        currency_totals: dict[str, Any] = {}

        for row_index in selected_rows:
            id_item = table.item(row_index, 0)

            if id_item is None:
                continue

            amount = id_item.data(Qt.UserRole + 1)
            currency_code = str(id_item.data(Qt.UserRole + 2) or "").strip().upper()

            if not currency_code:
                continue

            currency_totals[currency_code] = decimal_or_zero(
                currency_totals.get(currency_code, "0.00")
            ) + decimal_or_zero(amount)

        summary_label.setText(
            f"{selected_prefix}: {tr_number(len(selected_rows))} kayıt | "
            f"Toplam: {build_currency_totals_text(currency_totals)}"
        )

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

        table.setColumnWidth(2, 240)

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

                if column_index == 0:
                    item.setData(Qt.UserRole, issued_check.issued_check_id)
                    item.setData(Qt.UserRole + 1, issued_check.amount)
                    item.setData(Qt.UserRole + 2, issued_check.currency_code)

                if issued_check.status == "RISK":
                    item.setForeground(QColor("#fbbf24"))
                elif issued_check.status == "CANCELLED":
                    item.setForeground(QColor("#64748b"))
                elif issued_check.status == "PAID":
                    item.setForeground(QColor("#22c55e"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 6:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip(str(value))
                table.setItem(row_index, column_index, item)

        for row_index in range(table.rowCount()):
            table.setRowHeight(row_index, 34)

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
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(9)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MutedText")
        subtitle_label.setWordWrap(True)

        search_input = QLineEdit()
        result_label = QLabel("")
        selected_summary_label = QLabel("")
        selected_summary_label.setObjectName("MutedText")
        selected_summary_label.setWordWrap(True)
        previous_button = QPushButton()
        next_button = QPushButton()
        filter_buttons: dict[str, QPushButton] = {}

        tools_layout = self._build_table_tools_layout(
            search_input=search_input,
            filter_buttons=filter_buttons,
            result_label=result_label,
            previous_button=previous_button,
            next_button=next_button,
        )

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
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.doubleClicked.connect(lambda _index: self._open_received_check_detail_from_table(table))
        table.setMinimumHeight(260)

        self._configure_table_for_compact_view(table)
        self._configure_received_table_columns(table)

        selected_action_panel = self._build_received_selection_action_panel(table)

        state = {
            "filter_key": "OPEN",
            "page_index": 0,
            "sort_key": "due_date",
            "sort_direction": "ASC",
            "sort_column_index": 6,
            "sort_label": "Vade",
        }

        def refresh_selection_summary() -> None:
            self._refresh_selected_checks_summary(
                table=table,
                summary_label=selected_summary_label,
                empty_text="Seçili alınan çek yok. Çoklu seçim için Ctrl veya Shift ile satır seçebilirsin.",
                selected_prefix="Seçili alınan çek",
            )

        def refresh_table() -> None:
            filter_key = str(state["filter_key"])
            page_index = int(state["page_index"])
            search_text = search_input.text().strip()
            sort_key = str(state["sort_key"])
            sort_direction = str(state["sort_direction"])
            sort_column_index = int(state["sort_column_index"])

            table_data = load_received_checks_table_data(
                search_text=search_text,
                filter_key=filter_key,
                sort_key=sort_key,
                sort_direction=sort_direction,
                page_index=page_index,
                page_size=CHECK_LIST_PAGE_SIZE,
            )

            if table_data.error_message:
                self._fill_received_checks_table(table, [])
                refresh_selection_summary()
                previous_button.setEnabled(False)
                next_button.setEnabled(False)
                result_label.setText(f"Çek listesi okunamadı: {table_data.error_message}")
                return

            state["page_index"] = table_data.page_index
            self._fill_received_checks_table(table, table_data.rows)
            refresh_selection_summary()
            self._style_filter_buttons(filter_buttons, filter_key)

            table.horizontalHeader().setSortIndicator(
                sort_column_index,
                Qt.DescendingOrder if sort_direction == "DESC" else Qt.AscendingOrder,
            )

            previous_button.setEnabled(table_data.page_index > 0)
            next_button.setEnabled(table_data.page_index + 1 < table_data.total_pages)

            if table_data.total_count == 0:
                result_label.setText(
                    f"{self._filter_label(filter_key)}: filtreye uygun kayıt bulunamadı. "
                    f"Sıralama: {state['sort_label']} {_sort_direction_symbol(sort_direction)}"
                )
            else:
                start_index = table_data.page_index * table_data.page_size + 1
                end_index = start_index + len(table_data.rows) - 1
                result_label.setText(
                    f"{self._filter_label(filter_key)}: {start_index}-{end_index} / "
                    f"{table_data.total_count} kayıt gösteriliyor. "
                    f"Sayfa: {table_data.page_index + 1}/{table_data.total_pages}. "
                    f"Toplam: {build_currency_totals_text(table_data.currency_totals)} | "
                    f"Sıralama: {state['sort_label']} {_sort_direction_symbol(sort_direction)}"
                )

        def change_filter(filter_key: str) -> None:
            state["filter_key"] = filter_key
            state["page_index"] = 0
            refresh_table()

        def search_changed() -> None:
            state["page_index"] = 0
            refresh_table()

        def previous_page() -> None:
            state["page_index"] = max(0, int(state["page_index"]) - 1)
            refresh_table()

        def next_page() -> None:
            state["page_index"] = int(state["page_index"]) + 1
            refresh_table()

        def change_sort(column_index: int) -> None:
            if column_index not in RECEIVED_TABLE_SORT_COLUMNS:
                return

            sort_key, sort_label = RECEIVED_TABLE_SORT_COLUMNS[column_index]

            if state["sort_key"] == sort_key:
                state["sort_direction"] = "DESC" if state["sort_direction"] == "ASC" else "ASC"
            else:
                state["sort_key"] = sort_key
                state["sort_direction"] = SORT_DEFAULT_DIRECTIONS.get(sort_key, "ASC")

            state["sort_column_index"] = column_index
            state["sort_label"] = sort_label
            state["page_index"] = 0
            refresh_table()

        for filter_key, button in filter_buttons.items():
            button.clicked.connect(lambda checked=False, selected_filter_key=filter_key: change_filter(selected_filter_key))

        search_input.textChanged.connect(lambda _text: search_changed())
        previous_button.clicked.connect(previous_page)
        next_button.clicked.connect(next_page)
        table.horizontalHeader().sectionClicked.connect(change_sort)
        table.itemSelectionChanged.connect(refresh_selection_summary)

        refresh_table()

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addLayout(tools_layout)
        layout.addWidget(selected_summary_label)
        layout.addWidget(selected_action_panel)
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

        table.setColumnWidth(3, 260)

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

                if column_index == 0:
                    item.setData(Qt.UserRole, received_check.received_check_id)
                    item.setData(Qt.UserRole + 1, received_check.amount)
                    item.setData(Qt.UserRole + 2, received_check.currency_code)

                if received_check.status in {"BOUNCED", "RETURNED"}:
                    item.setForeground(QColor("#fbbf24"))
                elif received_check.status == "CANCELLED":
                    item.setForeground(QColor("#64748b"))
                elif received_check.status == "DISCOUNTED":
                    item.setForeground(QColor("#38bdf8"))
                elif received_check.status == "COLLECTED":
                    item.setForeground(QColor("#22c55e"))
                elif received_check.status == "ENDORSED":
                    item.setForeground(QColor("#e5e7eb"))
                else:
                    item.setForeground(QColor("#e5e7eb"))

                if column_index == 7:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip(str(value))
                table.setItem(row_index, column_index, item)

        for row_index in range(table.rowCount()):
            table.setRowHeight(row_index, 34)

    def _selected_issued_check_id_from_table(self, table: QTableWidget) -> int | None:
        current_row = table.currentRow()

        if current_row < 0:
            return None

        id_item = table.item(current_row, 0)

        if id_item is None:
            return None

        issued_check_id = id_item.data(Qt.UserRole)

        if issued_check_id in {None, ""}:
            issued_check_id = id_item.text()

        try:
            return int(issued_check_id)
        except (TypeError, ValueError):
            return None


    def _open_issued_check_detail_from_table(self, table: QTableWidget) -> None:
        issued_check_id = self._selected_issued_check_id_from_table(table)

        if issued_check_id is None:
            QMessageBox.warning(
                self,
                "Çek seçilemedi",
                "Detayını görüntülemek için geçerli bir yazılan çek satırı seçmelisin.",
            )
            return

        dialog = IssuedCheckDetailDialog(
            issued_check_id=issued_check_id,
            parent=self,
        )
        dialog.exec()

    def _selected_received_check_id_from_table(self, table: QTableWidget) -> int | None:
        current_row = table.currentRow()

        if current_row < 0:
            return None

        id_item = table.item(current_row, 0)

        if id_item is None:
            return None

        received_check_id = id_item.data(Qt.UserRole)

        if received_check_id in {None, ""}:
            received_check_id = id_item.text()

        try:
            return int(received_check_id)
        except (TypeError, ValueError):
            return None


    def _open_received_check_detail_from_table(self, table: QTableWidget) -> None:
        received_check_id = self._selected_received_check_id_from_table(table)

        if received_check_id is None:
            QMessageBox.warning(
                self,
                "Çek seçilemedi",
                "Detayını görüntülemek için geçerli bir alınan çek satırı seçmelisin.",
            )
            return

        dialog = ReceivedCheckDetailDialog(
            received_check_id=received_check_id,
            parent=self,
        )
        dialog.exec()

    def _open_checks_report_dialog(self) -> None:
        if not self._ensure_any_permission(
            (
                Permission.REPORT_VIEW_ALL,
                Permission.REPORT_VIEW_LIMITED,
            ),
            "Çek rapor özetini açmak için rapor görüntüleme yetkisi gerekir.",
        ):
            return

        dialog = ChecksReportDialog(parent=self)
        dialog.exec()

    def _open_discount_batches_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_DISCOUNT,
            "İskonto paketlerini görüntülemek için RECEIVED_CHECK_DISCOUNT yetkisi gerekir.",
        ):
            return

        dialog = ReceivedCheckDiscountBatchesDialog(parent=self)
        dialog.exec()

    def _build_operation_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel("Operasyon Alanı")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Çek işlemleri burada gruplandırılmıştır. Önce işlem türünü seç, ardından açılan pencerede ilgili çeki veya bilgileri tamamla."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        groups_grid = QGridLayout()
        groups_grid.setSpacing(12)
        groups_grid.setColumnStretch(0, 1)
        groups_grid.setColumnStretch(1, 1)
        groups_grid.setColumnStretch(2, 1)

        def run_first_available_action(
            action_title: str,
            candidate_method_names: list[str],
        ) -> None:
            for method_name in candidate_method_names:
                method = getattr(self, method_name, None)

                if callable(method):
                    method()
                    return

            QMessageBox.warning(
                self,
                "İşlem bulunamadı",
                (
                    f"'{action_title}' işlemi için mevcut bir ekran fonksiyonu bulunamadı.\n\n"
                    "Bu durum genellikle fonksiyon adının farklı olmasından kaynaklanır. "
                    "Mevcut çek işlem fonksiyonları korunmuştur; sadece bu butonun bağlantı adı kontrol edilmelidir."
                ),
            )

        def build_operation_button(
            button_text: str,
            candidate_method_names: list[str],
            *,
            button_type: str = "normal",
            required_permission: Permission | None = None,
            required_permissions: tuple[Permission, ...] | None = None,
            denied_tooltip: str = "Bu işlem için mevcut rolün yetkili değil.",
        ) -> QPushButton:
            button = QPushButton(button_text)
            button.setMinimumHeight(36)
            button.setCursor(Qt.PointingHandCursor)

            if button_type == "risk":
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: rgba(127, 29, 29, 0.44);
                        color: #fee2e2;
                        border: 1px solid rgba(239, 68, 68, 0.55);
                        border-radius: 10px;
                        padding: 8px 12px;
                        text-align: left;
                        font-weight: 700;
                    }

                    QPushButton:hover {
                        background-color: rgba(153, 27, 27, 0.70);
                        color: #ffffff;
                    }
                    """
                )
            elif button_type == "success":
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: rgba(6, 78, 59, 0.42);
                        color: #d1fae5;
                        border: 1px solid rgba(16, 185, 129, 0.50);
                        border-radius: 10px;
                        padding: 8px 12px;
                        text-align: left;
                        font-weight: 700;
                    }

                    QPushButton:hover {
                        background-color: rgba(5, 150, 105, 0.62);
                        color: #ffffff;
                    }
                    """
                )
            elif button_type == "primary":
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        border: 1px solid #3b82f6;
                        border-radius: 10px;
                        padding: 8px 12px;
                        text-align: left;
                        font-weight: 800;
                    }

                    QPushButton:hover {
                        background-color: #1d4ed8;
                    }
                    """
                )
            else:
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #172033;
                        color: #cbd5e1;
                        border: 1px solid #24324a;
                        border-radius: 10px;
                        padding: 8px 12px;
                        text-align: left;
                        font-weight: 650;
                    }

                    QPushButton:hover {
                        background-color: #1e293b;
                        color: #ffffff;
                    }
                    """
                )

            if required_permissions is not None:
                apply_any_permission_to_button(
                    button,
                    current_user=self.current_user,
                    permissions=required_permissions,
                    tooltip_when_denied=denied_tooltip,
                )
            elif required_permission is not None:
                apply_permission_to_button(
                    button,
                    current_user=self.current_user,
                    permission=required_permission,
                    tooltip_when_denied=denied_tooltip,
                )

            button.clicked.connect(
                lambda checked=False, current_button_text=button_text, current_candidate_method_names=candidate_method_names: run_first_available_action(
                    current_button_text,
                    current_candidate_method_names,
                )
            )

            return button

        def build_operation_group(
            group_title: str,
            group_subtitle: str,
            buttons: list[QPushButton],
        ) -> QWidget:
            group_card = QFrame()
            group_card.setObjectName("Card")

            group_card.setStyleSheet(
                """
                QFrame#Card {
                    background-color: rgba(15, 23, 42, 0.58);
                    border: 1px solid #24324a;
                    border-radius: 14px;
                }
                """
            )

            group_layout = QVBoxLayout(group_card)
            group_layout.setContentsMargins(14, 12, 14, 12)
            group_layout.setSpacing(8)

            title_label = QLabel(group_title)
            title_label.setObjectName("SectionTitle")

            subtitle_label = QLabel(group_subtitle)
            subtitle_label.setObjectName("MutedText")
            subtitle_label.setWordWrap(True)

            group_layout.addWidget(title_label)
            group_layout.addWidget(subtitle_label)
            group_layout.addSpacing(4)

            for button in buttons:
                group_layout.addWidget(button)

            group_layout.addStretch(1)

            return group_card

        report_group = build_operation_group(
            "Rapor & Paketler",
            "Çek raporları ve iskonto paketleri bu bölümden yönetilir.",
            [
                build_operation_button(
                    "Çek Rapor Özeti",
                    [
                        "_open_checks_report_dialog",
                        "_open_check_report_dialog",
                        "_show_checks_report_dialog",
                        "_show_check_report_dialog",
                        "_open_checks_report",
                        "_show_checks_report",
                    ],
                    button_type="primary",
                    required_permissions=(Permission.REPORT_VIEW_ALL, Permission.REPORT_VIEW_LIMITED),
                    denied_tooltip="Çek rapor özetini açmak için rapor görüntüleme yetkin yok.",
                ),
                build_operation_button(
                    "İskonto Paketleri",
                    [
                        "_open_received_check_discount_batches_dialog",
                        "_open_discount_batches_dialog",
                        "_show_received_check_discount_batches_dialog",
                        "_show_discount_batches_dialog",
                        "_open_discount_batches",
                        "_show_discount_batches",
                    ],
                    button_type="primary",
                    required_permission=Permission.RECEIVED_CHECK_DISCOUNT,
                    denied_tooltip="İskonto paketlerini görüntülemek için iskonto yetkin yok.",
                ),
            ],
        )

        issued_group = build_operation_group(
            "Yazılan Çek İşlemleri",
            "Tedarikçilere verilen çeklerin oluşturma, ödeme ve iptal işlemleri.",
            [
                build_operation_button(
                    "Yazılan Çek Oluştur",
                    [
                        "_open_issued_check_create_dialog",
                        "_show_issued_check_create_dialog",
                        "_create_issued_check",
                        "_open_create_issued_check_dialog",
                    ],
                    button_type="risk",
                    required_permission=Permission.ISSUED_CHECK_CREATE,
                    denied_tooltip="Yazılan çek oluşturma yetkin yok.",
                ),
                build_operation_button(
                    "Yazılan Çek Ödendi",
                    [
                        "_open_issued_check_pay_dialog",
                        "_show_issued_check_pay_dialog",
                        "_pay_issued_check",
                        "_open_pay_issued_check_dialog",
                    ],
                    button_type="risk",
                    required_permission=Permission.ISSUED_CHECK_PAY,
                    denied_tooltip="Yazılan çek ödeme yetkin yok.",
                ),
                build_operation_button(
                    "Yazılan Çek İptal Et",
                    [
                        "_open_issued_check_cancel_dialog",
                        "_show_issued_check_cancel_dialog",
                        "_cancel_issued_check",
                        "_open_cancel_issued_check_dialog",
                    ],
                    button_type="normal",
                    required_permission=Permission.ISSUED_CHECK_CANCEL,
                    denied_tooltip="Yazılan çek iptal etme yetkin yok.",
                ),
            ],
        )

        received_group = build_operation_group(
            "Alınan Çek İşlemleri",
            "Müşterilerden alınan çeklerin tahsil, banka, ciro, iskonto ve problem işlemleri.",
            [
                build_operation_button(
                    "Alınan Çek Oluştur",
                    [
                        "_open_received_check_create_dialog",
                        "_show_received_check_create_dialog",
                        "_create_received_check",
                        "_open_create_received_check_dialog",
                    ],
                    button_type="success",
                    required_permission=Permission.RECEIVED_CHECK_CREATE,
                    denied_tooltip="Alınan çek oluşturma yetkin yok.",
                ),
                build_operation_button(
                    "Alınan Çeki Bankaya Tahsile Ver",
                    [
                        "_open_received_check_send_to_bank_dialog",
                        "_show_received_check_send_to_bank_dialog",
                        "_send_received_check_to_bank",
                        "_open_send_received_check_to_bank_dialog",
                    ],
                    button_type="success",
                    required_permission=Permission.RECEIVED_CHECK_SEND_TO_BANK,
                    denied_tooltip="Alınan çeki bankaya gönderme yetkin yok.",
                ),
                build_operation_button(
                    "Alınan Çeki Kullan / Ciro Et",
                    [
                        "_open_received_check_endorse_dialog",
                        "_show_received_check_endorse_dialog",
                        "_endorse_received_check",
                        "_open_endorse_received_check_dialog",
                    ],
                    button_type="success",
                    required_permission=Permission.RECEIVED_CHECK_ENDORSE,
                    denied_tooltip="Alınan çeki ciro etme yetkin yok.",
                ),
                build_operation_button(
                    "Alınan Çekleri İskontoya Ver / Kırdır",
                    [
                        "_open_discount_received_check_dialog",
                        "_open_received_check_discount_batch_dialog",
                        "_show_received_check_discount_batch_dialog",
                        "_discount_received_checks_batch",
                        "_open_discount_received_checks_batch_dialog",
                        "_open_received_check_discount_dialog",
                        "_show_received_check_discount_dialog",
                        "_discount_received_check",
                    ],
                    button_type="success",
                    required_permission=Permission.RECEIVED_CHECK_DISCOUNT,
                    denied_tooltip="Alınan çeki iskonto etme yetkin yok.",
                ),
                build_operation_button(
                    "Alınan Çek Tahsil Et",
                    [
                        "_open_received_check_collect_dialog",
                        "_show_received_check_collect_dialog",
                        "_collect_received_check",
                        "_open_collect_received_check_dialog",
                    ],
                    button_type="success",
                    required_permission=Permission.RECEIVED_CHECK_COLLECT,
                    denied_tooltip="Alınan çek tahsil etme yetkin yok.",
                ),
                build_operation_button(
                    "Alınan Çeki Karşılıksız İşaretle",
                    [
                        "_open_received_check_bounce_dialog",
                        "_show_received_check_bounce_dialog",
                        "_mark_received_check_bounced",
                        "_open_bounce_received_check_dialog",
                    ],
                    button_type="risk",
                    required_permission=Permission.RECEIVED_CHECK_CANCEL,
                    denied_tooltip="Alınan çeki problemli/karşılıksız işaretleme yetkin yok.",
                ),
                build_operation_button(
                    "Alınan Çeki İade İşaretle",
                    [
                        "_open_received_check_return_dialog",
                        "_show_received_check_return_dialog",
                        "_mark_received_check_returned",
                        "_open_return_received_check_dialog",
                    ],
                    button_type="normal",
                    required_permission=Permission.RECEIVED_CHECK_CANCEL,
                    denied_tooltip="Alınan çeki iade işaretleme yetkin yok.",
                ),
            ],
        )

        groups_grid.addWidget(received_group, 0, 0)
        groups_grid.addWidget(issued_group, 0, 1)
        groups_grid.addWidget(report_group, 0, 2)

        layout.addLayout(groups_grid)

        return card

    def _open_create_issued_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.ISSUED_CHECK_CREATE,
            "Yazılan çek oluşturmak için ISSUED_CHECK_CREATE yetkisi gerekir.",
        ):
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
        if not self._ensure_permission(
            Permission.ISSUED_CHECK_PAY,
            "Yazılan çek ödemek için ISSUED_CHECK_PAY yetkisi gerekir.",
        ):
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
    def _open_cancel_issued_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.ISSUED_CHECK_CANCEL,
            "Yazılan çek iptal etmek için ISSUED_CHECK_CANCEL yetkisi gerekir.",
        ):
            return

        dialog = IssuedCheckCancelDialog(parent=self)

        if not dialog.has_cancellable_checks():
            QMessageBox.information(
                self,
                "İptal edilecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                issued_check = cancel_issued_check(
                    session,
                    issued_check_id=payload["issued_check_id"],
                    cancel_reason=payload["cancel_reason"],
                    cancelled_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                cancelled_issued_check_id = issued_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Yazılan çek iptal edildi",
                f"Yazılan çek başarıyla iptal edildi. Çek ID: {cancelled_issued_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Yazılan çek iptal edilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Yazılan çek iptal edilirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_create_received_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_CREATE,
            "Alınan çek oluşturmak için RECEIVED_CHECK_CREATE yetkisi gerekir.",
        ):
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
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_SEND_TO_BANK,
            "Alınan çeki bankaya göndermek için RECEIVED_CHECK_SEND_TO_BANK yetkisi gerekir.",
        ):
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

    def _open_endorse_received_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_ENDORSE,
            "Alınan çeki ciro etmek için RECEIVED_CHECK_ENDORSE yetkisi gerekir.",
        ):
            return

        if ReceivedCheckEndorseDialog is None or endorse_received_check is None:
            QMessageBox.information(
                self,
                "Ciro modülü hazır değil",
                "Alınan çeki kullan / ciro et dialog dosyası veya servis fonksiyonu bulunamadı.",
            )
            return

        dialog = ReceivedCheckEndorseDialog(parent=self)

        if hasattr(dialog, "has_endorsable_checks") and not dialog.has_endorsable_checks():
            QMessageBox.information(
                self,
                "Ciro edilecek çek bulunamadı",
                dialog.get_missing_data_message()
                if hasattr(dialog, "get_missing_data_message")
                else "Ciro edilebilir alınan çek kaydı bulunamadı.",
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                received_check = endorse_received_check(
                    session,
                    received_check_id=payload["received_check_id"],
                    endorse_date=payload["endorse_date"],
                    counterparty_text=payload["counterparty_text"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    endorsed_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                endorsed_received_check_id = received_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Alınan çek ciro edildi",
                f"Alınan çek kullan / ciro et işlemi başarıyla tamamlandı. Çek ID: {endorsed_received_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Alınan çek ciro edilemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Alınan çek ciro edilirken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_discount_received_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_DISCOUNT,
            "Alınan çeki iskonto etmek için RECEIVED_CHECK_DISCOUNT yetkisi gerekir.",
        ):
            return

        dialog = ReceivedCheckDiscountBatchDialog(parent=self)

        if not dialog.has_discountable_checks():
            QMessageBox.information(
                self,
                "İskontoya verilecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                batch = create_received_check_discount_batch(
                    session,
                    bank_account_id=payload["bank_account_id"],
                    received_check_ids=payload["received_check_ids"],
                    discount_date=payload["discount_date"],
                    annual_interest_rate=payload["annual_interest_rate"],
                    commission_rate=payload["commission_rate"],
                    bsiv_rate=payload["bsiv_rate"],
                    day_basis=payload["day_basis"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    created_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                created_batch_id = batch.id
                selected_check_count = len(payload["received_check_ids"])

            self._reload_page_data()

            QMessageBox.information(
                self,
                "İskonto paketi oluşturuldu",
                f"Çoklu çek iskonto paketi başarıyla oluşturuldu.\n"
                f"Paket ID: {created_batch_id}\n"
                f"Çek sayısı: {selected_check_count}",
            )

        except ReceivedCheckDiscountBatchServiceError as exc:
            QMessageBox.warning(
                self,
                "İskonto paketi oluşturulamadı",
                str(exc),
            )
        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "İskonto işlemi tamamlanamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Çoklu çek iskonto paketi oluşturulurken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _open_collect_received_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_COLLECT,
            "Alınan çek tahsil etmek için RECEIVED_CHECK_COLLECT yetkisi gerekir.",
        ):
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

    def _open_bounce_received_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_CANCEL,
            "Alınan çeki karşılıksız işaretlemek için RECEIVED_CHECK_CANCEL yetkisi gerekir.",
        ):
            return

        dialog = ReceivedCheckBounceDialog(parent=self)

        if not dialog.has_bounceable_checks():
            QMessageBox.information(
                self,
                "Karşılıksız işaretlenecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                received_check = mark_received_check_bounced(
                    session,
                    received_check_id=payload["received_check_id"],
                    bounce_date=payload["bounce_date"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    bounced_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                bounced_received_check_id = received_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Alınan çek karşılıksız işaretlendi",
                f"Alınan çek başarıyla karşılıksız işaretlendi. Çek ID: {bounced_received_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Alınan çek karşılıksız işaretlenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Alınan çek karşılıksız işaretlenirken beklenmeyen bir hata oluştu:\n{exc}",
            )
    
    def _open_return_received_check_dialog(self) -> None:
        if not self._ensure_permission(
            Permission.RECEIVED_CHECK_CANCEL,
            "Alınan çeki iade işaretlemek için RECEIVED_CHECK_CANCEL yetkisi gerekir.",
        ):
            return

        dialog = ReceivedCheckReturnDialog(parent=self)

        if not dialog.has_returnable_checks():
            QMessageBox.information(
                self,
                "İade işaretlenecek çek bulunamadı",
                dialog.get_missing_data_message(),
            )
            return

        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.get_payload()

        try:
            with session_scope() as session:
                received_check = mark_received_check_returned(
                    session,
                    received_check_id=payload["received_check_id"],
                    return_date=payload["return_date"],
                    counterparty_text=payload["counterparty_text"],
                    reference_no=payload["reference_no"],
                    description=payload["description"],
                    returned_by_user_id=getattr(self.current_user, "id", None),
                    acting_user=self.current_user,
                )

                returned_received_check_id = received_check.id

            self._reload_page_data()

            QMessageBox.information(
                self,
                "Alınan çek iade işaretlendi",
                f"Alınan çek başarıyla iade işaretlendi. Çek ID: {returned_received_check_id}",
            )

        except CheckServiceError as exc:
            QMessageBox.warning(
                self,
                "Alınan çek iade işaretlenemedi",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen hata",
                f"Alınan çek iade işaretlenirken beklenmeyen bir hata oluştu:\n{exc}",
            )
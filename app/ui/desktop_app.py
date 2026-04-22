import sys
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.components.status_badge import create_health_badge, create_user_badge
from app.ui.dashboard_data import load_dashboard_data
from app.ui.navigation import (
    ALL_NAV_ITEMS,
    count_hidden_pages_for_role,
    get_allowed_pages_for_role,
    role_to_text,
    username_to_text,
)
from app.ui.pages.banks_page import BanksPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.placeholder_page import AccessDeniedPage, PlaceholderPage
from app.ui.styles import APP_STYLE
from app.ui.ui_helpers import clear_layout


PAGE_SUBTITLES = {
    "Genel Bakış": "Banka, POS, çek, güvenlik ve sistem sağlığını tek ekranda izle.",
    "Bankalar": "Banka hesapları, bakiyeler, hareketler ve transfer yönetimi.",
    "POS Mutabakat": "Beklenen POS yatışları, gerçekleşen tutarlar ve fark analizleri burada olacak.",
    "Çek Yönetimi": "Yazılan çekler, alınan çekler, vade takvimi ve çek riskleri burada yönetilecek.",
    "Cari Kartlar": "Müşteri ve tedarikçi kartları burada listelenecek.",
    "Raporlar": "Finansal Excel, POS mutabakat, risk ve transfer öneri raporları burada olacak.",
    "Güvenlik": "Kullanıcılar, roller, audit log ve yetkisiz işlem denemeleri burada izlenecek.",
    "Sistem": "Yedekleme, restore testi, sağlık kontrolü ve mail durumları burada yönetilecek.",
    "Erişim Yok": "Bu ekran için mevcut rolün yetkili değil.",
}


class FtmDesktopWindow(QMainWindow):
    def __init__(self, current_user: Optional[Any] = None) -> None:
        super().__init__()

        self.current_user = current_user
        self.current_role = role_to_text(current_user.role if current_user else None)
        self.current_username = username_to_text(current_user)

        self.setWindowTitle(
            f"FTM Finans Kontrol Paneli - {self.current_username} ({self.current_role})"
        )

        self.resize(1450, 900)
        self.setMinimumSize(1180, 720)

        self.allowed_pages = get_allowed_pages_for_role(self.current_role)
        self.current_page = (
            "Genel Bakış"
            if "Genel Bakış" in self.allowed_pages
            else self.allowed_pages[0]
        )

        self.nav_buttons: dict[str, QPushButton] = {}
        self.dashboard_data = load_dashboard_data()

        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        sidebar = self._build_sidebar()

        self.content = QWidget()
        self.content.setObjectName("ContentViewport")
        self.content.setMinimumWidth(880)

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)

        self.content_scroll_area = QScrollArea()
        self.content_scroll_area.setObjectName("ContentScrollArea")
        self.content_scroll_area.setWidgetResizable(True)
        self.content_scroll_area.setFrameShape(QFrame.NoFrame)
        self.content_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.content_scroll_area.setWidget(self.content)

        self.content_scroll_area.setStyleSheet(
            """
            QScrollArea#ContentScrollArea {
                background-color: #0f172a;
                border: none;
            }

            QScrollArea#ContentScrollArea > QWidget {
                background-color: #0f172a;
            }

            QWidget#ContentViewport {
                background-color: #0f172a;
            }

            QScrollBar:vertical {
                background-color: #0f172a;
                width: 10px;
                margin: 0px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background-color: #334155;
                min-height: 30px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #475569;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
                border: none;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
            """
        )

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.content_scroll_area, 1)

        self.render_current_page()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(285)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        logo_box = self._build_logo_box()
        layout.addWidget(logo_box)

        for title in ALL_NAV_ITEMS:
            if title not in self.allowed_pages:
                continue

            button = QPushButton(title)
            button.clicked.connect(
                lambda checked=False, page_title=title: self.set_page(page_title)
            )

            self.nav_buttons[title] = button
            layout.addWidget(button)

        layout.addStretch()

        hidden_count = count_hidden_pages_for_role(self.current_role)

        footer = QLabel(
            f"v0.5 UI Modular\n"
            f"Rol bazlı menü aktif.\n"
            f"Gizlenen bölüm: {hidden_count}"
        )
        footer.setObjectName("MutedText")
        footer.setWordWrap(True)

        layout.addWidget(footer)

        self.update_selected_nav_button()

        return sidebar

    def _build_logo_box(self) -> QWidget:
        logo_box = QFrame()
        logo_box.setObjectName("LogoBox")

        logo_layout = QVBoxLayout(logo_box)
        logo_layout.setContentsMargins(18, 18, 18, 18)
        logo_layout.setSpacing(2)

        logo_title = QLabel("FTM")
        logo_title.setObjectName("LogoTitle")

        logo_subtitle = QLabel("Finans Takip Merkezi")
        logo_subtitle.setObjectName("LogoSubtitle")

        user_text = QLabel(f"{self.current_username} / {self.current_role}")
        user_text.setObjectName("MutedText")

        logo_layout.addWidget(logo_title)
        logo_layout.addWidget(logo_subtitle)
        logo_layout.addSpacing(8)
        logo_layout.addWidget(user_text)

        return logo_box

    def update_selected_nav_button(self) -> None:
        for page_title, button in self.nav_buttons.items():
            if page_title == self.current_page:
                button.setObjectName("PrimaryButton")
            else:
                button.setObjectName("")

            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def set_page(self, page_title: str) -> None:
        if page_title not in self.allowed_pages:
            self.current_page = "Erişim Yok"
        else:
            self.current_page = page_title

        self.update_selected_nav_button()
        self.render_current_page()

    def render_current_page(self) -> None:
        clear_layout(self.content_layout)

        if self.current_page == "Genel Bakış":
            self.dashboard_data = load_dashboard_data()

        self.content_layout.addWidget(self._build_top_bar())

        if self.current_page == "Erişim Yok":
            self.content_layout.addWidget(
                AccessDeniedPage(
                    username=self.current_username,
                    role=self.current_role,
                ),
                1,
            )
            self.content_scroll_area.verticalScrollBar().setValue(0)
            return

        if self.current_page == "Genel Bakış":
            self.content_layout.addWidget(
                DashboardPage(
                    dashboard_data=self.dashboard_data,
                ),
                1,
            )
            self.content_scroll_area.verticalScrollBar().setValue(0)
            return

        if self.current_page == "Bankalar":
            self.content_layout.addWidget(
                BanksPage(
                    current_user=self.current_user,
                ),
                1,
            )
            self.content_scroll_area.verticalScrollBar().setValue(0)
            return

        self.content_layout.addWidget(
            PlaceholderPage(
                page_title=self.current_page,
            ),
            1,
        )

        self.content_scroll_area.verticalScrollBar().setValue(0)

    def _build_top_bar(self) -> QWidget:
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_bar.setMinimumHeight(105)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        title = QLabel(self.current_page)
        title.setObjectName("PageTitle")

        subtitle = QLabel(self._page_subtitle())
        subtitle.setObjectName("PageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        user_badge = create_user_badge(
            username=self.current_username,
            role=self.current_role,
        )

        health_badge = create_health_badge(
            status=self.dashboard_data.health_status,
        )

        refresh_button = QPushButton("Verileri Yenile")
        refresh_button.setObjectName("RefreshButton")
        refresh_button.setFixedWidth(150)
        refresh_button.clicked.connect(self.refresh_dashboard)

        layout.addLayout(title_box, 1)
        layout.addWidget(user_badge)
        layout.addWidget(health_badge)
        layout.addWidget(refresh_button)

        return top_bar

    def _page_subtitle(self) -> str:
        return PAGE_SUBTITLES.get(
            self.current_page,
            "FTM modül ekranı.",
        )

    def refresh_dashboard(self) -> None:
        self.dashboard_data = load_dashboard_data()
        self.render_current_page()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)

    window = FtmDesktopWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
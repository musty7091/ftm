from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.ui.components.summary_card import SummaryCard


PLACEHOLDER_TEXTS = {
    "Bankalar": (
        "Bu ekranda banka hesapları, banka hareketleri ve transferler gerçek tablolarla yönetilecek. "
        "Hedefimiz: hareket ekleme, iptal, bakiye izleme ve transferleri tek panelde toplamak."
    ),
    "POS Mutabakat": (
        "Bu ekranda beklenen POS yatışları, gerçekleşen yatışlar, fark nedenleri ve POS mutabakat raporu görünecek. "
        "Banka ile beklenen tutar arasındaki farkları burada avlayacağız."
    ),
    "Çek Yönetimi": (
        "Bu ekranda yazılan çekler, alınan çekler, ödeme/tahsilat durumu, iptal işlemleri ve vade yaklaşan riskler listelenecek."
    ),
    "Cari Kartlar": (
        "Bu ekranda müşteri ve tedarikçi kartları yönetilecek. Cari türü, vergi bilgileri, telefon, e-posta ve adres kayıtları burada olacak."
    ),
    "Raporlar": (
        "Bu ekranda finansal Excel raporu, POS mutabakat raporu, risk raporu ve transfer önerileri tek yerden alınacak."
    ),
    "Güvenlik": (
        "Bu ekranda kullanıcılar, roller, yetkisiz işlem denemeleri ve audit log kayıtları izlenecek. "
        "Kim ne yaptı, kim ne yapmaya çalıştı burada görünecek."
    ),
    "Sistem": (
        "Bu ekranda yedekleme, restore testi, güvenlik maili, sistem sağlık raporu ve otomasyon durumları yönetilecek."
    ),
}


class PlaceholderPage(QWidget):
    def __init__(self, page_title: str) -> None:
        super().__init__()

        self.page_title = page_title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        page = QFrame()
        page.setObjectName("Card")

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(34, 30, 34, 30)
        page_layout.setSpacing(18)

        big_title = QLabel(f"{self.page_title} Modülü")
        big_title.setObjectName("BigTitle")

        body = QLabel(self._placeholder_body_text())
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        mini_grid = QGridLayout()
        mini_grid.setSpacing(16)

        mini_grid.addWidget(
            SummaryCard(
                "MODÜL DURUMU",
                "Hazırlanıyor",
                "Bu ekran bir sonraki adımlarda gerçek tablo ve formlarla bağlanacak.",
                "highlight",
            ),
            0,
            0,
        )

        mini_grid.addWidget(
            SummaryCard(
                "ARKA PLAN",
                "Hazır",
                "Bu modülün servisleri büyük ölçüde zaten çalışıyor.",
                "success",
            ),
            0,
            1,
        )

        mini_grid.addWidget(
            SummaryCard(
                "GÜVENLİK",
                "Aktif",
                "Rol, yetki ve audit log kontrolleri korunacak.",
                "normal",
            ),
            0,
            2,
        )

        page_layout.addWidget(big_title)
        page_layout.addWidget(body)
        page_layout.addLayout(mini_grid)
        page_layout.addStretch()

        layout.addWidget(page, 1)

    def _placeholder_body_text(self) -> str:
        return PLACEHOLDER_TEXTS.get(
            self.page_title,
            "Bu modül bir sonraki adımlarda gerçek ekran olarak bağlanacak.",
        )


class AccessDeniedPage(QWidget):
    def __init__(self, username: str, role: str) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        page = QFrame()
        page.setObjectName("CardRisk")

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(34, 30, 34, 30)
        page_layout.setSpacing(18)

        title = QLabel("Erişim Yetkiniz Yok")
        title.setObjectName("BigTitle")

        body = QLabel(
            f"{username} / {role} rolü bu ekrana erişemez.\n\n"
            "Gerekirse ADMIN kullanıcısı rol veya yetki düzenlemesi yapmalıdır."
        )
        body.setObjectName("MutedText")
        body.setWordWrap(True)

        page_layout.addWidget(title)
        page_layout.addWidget(body)
        page_layout.addStretch()

        layout.addWidget(page, 1)
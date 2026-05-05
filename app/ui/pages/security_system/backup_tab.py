from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.config import settings
from app.services.backup_service import (
    BackupServiceError,
    create_database_backup,
    format_backup_size,
    list_database_backups,
    validate_backup_file,
)
from app.services.restore_standard_service import (
    RestoreStandardServiceError,
    build_restore_safety_plan,
    execute_sqlite_restore_from_plan,
    get_restore_execution_summary_lines,
    get_restore_safety_plan_summary_lines,
)
from app.services.permission_service import Permission
from app.ui.permission_ui import (
    set_widget_permission,
    user_has_permission,
)


BACKUP_TAB_STYLE = """
QFrame#BackupCard {
    background-color: #111827;
    border: 1px solid #24324a;
    border-radius: 18px;
}

QFrame#BackupInfoCard {
    background-color: rgba(15, 23, 42, 0.66);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 14px;
}

QFrame#BackupSuccessCard {
    background-color: rgba(6, 78, 59, 0.26);
    border: 1px solid rgba(16, 185, 129, 0.38);
    border-radius: 14px;
}

QFrame#BackupWarningCard {
    background-color: rgba(120, 53, 15, 0.26);
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 14px;
}

QFrame#BackupRiskCard {
    background-color: rgba(127, 29, 29, 0.26);
    border: 1px solid rgba(248, 113, 113, 0.42);
    border-radius: 14px;
}

QLabel#BackupTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 900;
}

QLabel#BackupSectionTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 900;
}

QLabel#BackupSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#BackupBadge {
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(30, 64, 175, 0.32);
    border: 1px solid rgba(59, 130, 246, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#BackupOkBadge {
    color: #d1fae5;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(6, 78, 59, 0.34);
    border: 1px solid rgba(16, 185, 129, 0.42);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#BackupWarnBadge {
    color: #fde68a;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(120, 53, 15, 0.36);
    border: 1px solid rgba(245, 158, 11, 0.48);
    border-radius: 8px;
    padding: 5px 9px;
}

QLabel#BackupFailBadge {
    color: #fecaca;
    font-size: 11px;
    font-weight: 800;
    background-color: rgba(127, 29, 29, 0.40);
    border: 1px solid rgba(248, 113, 113, 0.52);
    border-radius: 8px;
    padding: 5px 9px;
}

QPushButton#BackupPrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#BackupPrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#BackupSuccessButton {
    background-color: #047857;
    color: #ffffff;
    border: 1px solid #10b981;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#BackupSuccessButton:hover {
    background-color: #059669;
}

QPushButton#BackupWarningButton {
    background-color: #92400e;
    color: #ffffff;
    border: 1px solid #f59e0b;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#BackupWarningButton:hover {
    background-color: #b45309;
}

QPushButton#BackupDangerButton {
    background-color: #991b1b;
    color: #ffffff;
    border: 1px solid #ef4444;
    border-radius: 11px;
    padding: 8px 14px;
    font-weight: 900;
}

QPushButton#BackupDangerButton:hover {
    background-color: #b91c1c;
}

QPushButton:disabled {
    background-color: rgba(30, 41, 59, 0.55);
    color: #64748b;
    border: 1px solid rgba(100, 116, 139, 0.32);
}

QTableWidget#BackupTable {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget#BackupTable::item {
    padding: 6px;
    border: none;
}

QHeaderView::section {
    background-color: #1f2937;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 8px;
    font-weight: 900;
}

QTableCornerButton::section {
    background-color: #1f2937;
    border: 1px solid #334155;
}
"""


def _is_sqlite_mode() -> bool:
    return bool(getattr(settings, "is_sqlite", False))


def _backup_table_headers() -> list[str]:
    if _is_sqlite_mode():
        return [
            "Dosya",
            "Boyut",
            "Oluşturma",
            "Veritabanı Dosyası",
            "Mod",
            "Kaynak",
            "Durum",
            "Dosya Yolu",
        ]

    return [
        "Dosya",
        "Boyut",
        "Oluşturma",
        "Veritabanı",
        "Kullanıcı",
        "Container",
        "Durum",
        "Dosya Yolu",
    ]


def _backup_subtitle_text() -> str:
    if _is_sqlite_mode():
        return (
            "Bu sekmeden FTM Local / SQLite veritabanının güvenli .db yedeği alınır, "
            "mevcut SQLite yedekleri listelenir ve seçili yedeğin temel dosya doğrulaması yapılır. "
            "Yedekleme harici veritabanı sunucusu gerektirmez."
        )

    return (
        "Bu sekmeden manuel SQLite yedeği alınır, mevcut yedekler listelenir "
        "ve seçili yedeğin temel dosya doğrulaması yapılır. Geri yükleme işlemi şimdilik "
        "otomatik çalıştırılmaz; önce güvenli doğrulama yapılır."
    )


def _manual_backup_card_body() -> str:
    if _is_sqlite_mode():
        return (
            "Aktif SQLite veritabanı dosyasının zaman damgalı .db yedeği alınır. "
            "Yedek dosyası backups klasörüne kaydedilir."
        )

    return "Aktif SQLite veritabanı dosyasının zaman damgalı .db yedeği alınır."


def _validation_card_body() -> str:
    if _is_sqlite_mode():
        return (
            "Seçili SQLite .db yedeğinin varlığı, boyutu, SHA256 değeri ve SQLite dosya başlığı kontrol edilir."
        )

    return "Seçili dosyanın varlığı, boyutu, SHA256 değeri ve dump başlığı kontrol edilir."


def _restore_card_body() -> str:
    if _is_sqlite_mode():
        return (
            "Seçili SQLite yedeği önce FTM güvenli yedek standardına göre doğrulanır. "
            "Restore öncesi aktif veritabanının otomatik güvenlik yedeği alınır. "
            "Gerçek geri yükleme için çift onay ve elle GERİ YÜKLE onayı gerekir."
        )

    return (
        "Bu güvenli geri yükleme akışı SQLite Local yedekleri için hazırlanmıştır. "
        "SQLite Local restore akışı güvenli standartla ayrıca yönetilir."
    )


def _backup_hint_text() -> str:
    if _is_sqlite_mode():
        return (
            "Not: SQLite Local modda yedekleme, aktif .db veritabanı dosyasının güvenli kopyasını alır. "
            "Harici veritabanı sunucusu gerekmez. "
            "Yedek klasörü Sistem Ayarları ekranındaki risksiz ayardan gelir."
        )

    return (
        "Not: Yedekleme SQLite yerel veri dosyası üzerinden çalışır. "
        "Yedek klasörü Sistem Ayarları ekranındaki risksiz ayardan gelir. "
        "Yedek klasörü ise Sistem Ayarları ekranındaki risksiz ayardan gelir."
    )


def _manual_backup_confirm_text() -> str:
    if _is_sqlite_mode():
        return (
            "SQLite veritabanı yedeği alınacak.\n\n"
            "Bu işlem aktif .db veritabanı dosyasının güvenli bir kopyasını oluşturur.\n"
            "Harici veritabanı sunucusu kullanılmaz.\n\n"
            "Devam etmek istiyor musun?"
        )

    return (
        "Veritabanı yedeği alınacak.\n\n"
        "Bu işlem birkaç saniye sürebilir. Devam etmek istiyor musun?"
    )


def _validation_file_type_text(*, message: str, is_postgresql_custom_dump: bool) -> str:
    if is_postgresql_custom_dump:
        return "Eski desteklenmeyen yedek formatı"

    if "SQLite" in message:
        return "SQLite veritabanı dosyası"

    return "Bilinmiyor"


class BackupTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet(BACKUP_TAB_STYLE)

        self.backup_infos: list[Any] = []

        self.total_backup_label = QLabel("Yedek: 0")
        self.total_backup_label.setObjectName("BackupBadge")

        self.last_backup_label = QLabel("Son yedek: Yok")
        self.last_backup_label.setObjectName("BackupWarnBadge")

        self.validation_status_label = QLabel("Doğrulama: Bekliyor")
        self.validation_status_label.setObjectName("BackupBadge")

        self.backup_button = QPushButton("Manuel Yedek Al")
        self.backup_button.setObjectName("BackupSuccessButton")
        self.backup_button.clicked.connect(self.create_backup)

        self.refresh_button = QPushButton("Yedekleri Yenile")
        self.refresh_button.setObjectName("BackupPrimaryButton")
        self.refresh_button.clicked.connect(self.load_backups)

        self.validate_button = QPushButton("Seçili Yedeği Doğrula")
        self.validate_button.setObjectName("BackupWarningButton")
        self.validate_button.clicked.connect(self.validate_selected_backup)

        self.restore_button = QPushButton("Yedekten Geri Yükle")
        self.restore_button.setObjectName("BackupDangerButton")
        self.restore_button.clicked.connect(self.restore_selected_backup)

        self.backup_table = QTableWidget()
        self.backup_table.setObjectName("BackupTable")
        self.backup_table.setColumnCount(8)
        self.backup_table.setHorizontalHeaderLabels(_backup_table_headers())
        self.backup_table.setAlternatingRowColors(True)
        self.backup_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.backup_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.backup_table.verticalHeader().setVisible(False)

        header = self.backup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        self._build_ui()

        self.load_backups()
        QTimer.singleShot(0, self.apply_permissions)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("BackupCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title = QLabel("Yedekleme ve Geri Yükleme Testi")
        title.setObjectName("BackupTitle")

        title_row.addWidget(title, 1)
        title_row.addWidget(self.total_backup_label, 0, Qt.AlignVCenter)
        title_row.addWidget(self.last_backup_label, 0, Qt.AlignVCenter)
        title_row.addWidget(self.validation_status_label, 0, Qt.AlignVCenter)

        subtitle = QLabel(_backup_subtitle_text())
        subtitle.setObjectName("BackupSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addLayout(title_row)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(self._build_summary_cards())
        card_layout.addLayout(self._build_actions())
        card_layout.addWidget(self.backup_table, 1)

        main_layout.addWidget(card, 1)

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(
            self._build_small_card(
                title="Manuel Yedekleme",
                body=_manual_backup_card_body(),
                object_name="BackupSuccessCard",
            ),
            0,
            0,
        )

        grid.addWidget(
            self._build_small_card(
                title="Yedek Doğrulama",
                body=_validation_card_body(),
                object_name="BackupWarningCard",
            ),
            0,
            1,
        )

        grid.addWidget(
            self._build_small_card(
                title="Geri Yükleme",
                body=_restore_card_body(),
                object_name="BackupInfoCard",
            ),
            0,
            2,
        )

        return grid

    def _build_small_card(
        self,
        *,
        title: str,
        body: str,
        object_name: str,
    ) -> QWidget:
        card = QFrame()
        card.setObjectName(object_name)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("BackupSectionTitle")

        body_label = QLabel(body)
        body_label.setObjectName("BackupSubtitle")
        body_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addStretch(1)

        return card

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        hint = QLabel(_backup_hint_text())
        hint.setObjectName("BackupSubtitle")
        hint.setWordWrap(True)

        layout.addWidget(hint, 1)
        layout.addWidget(self.refresh_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.validate_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.restore_button, 0, Qt.AlignVCenter)
        layout.addWidget(self.backup_button, 0, Qt.AlignVCenter)

        return layout

    def apply_permissions(self) -> None:
        can_run_backup = user_has_permission(
            current_user=self._current_user(),
            permission=Permission.BACKUP_RUN,
        )

        can_run_restore_test = user_has_permission(
            current_user=self._current_user(),
            permission=Permission.RESTORE_TEST_RUN,
        )

        can_run_restore = user_has_permission(
            current_user=self._current_user(),
            permission=Permission.RESTORE_RUN,
        )

        set_widget_permission(
            self.backup_button,
            allowed=can_run_backup,
            tooltip_when_denied="Manuel yedek almak için BACKUP_RUN yetkisi gerekir.",
        )

        set_widget_permission(
            self.validate_button,
            allowed=can_run_restore_test,
            tooltip_when_denied="Yedek doğrulama testi için RESTORE_TEST_RUN yetkisi gerekir.",
        )

        set_widget_permission(
            self.restore_button,
            allowed=can_run_restore,
            tooltip_when_denied="Yedekten geri yükleme için RESTORE_RUN yetkisi gerekir.",
        )

    def load_backups(self) -> None:
        try:
            self.backup_infos = list_database_backups()
            self._fill_backup_table()
            self._update_summary_badges()

        except BackupServiceError as exc:
            QMessageBox.warning(
                self,
                "Yedekler Okunamadı",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Yedek listesi okunurken hata oluştu:\n\n{exc}",
            )

    def create_backup(self) -> None:
        if not self._ensure_backup_permission():
            return

        answer = QMessageBox.question(
            self,
            "Manuel Yedek Alınsın mı?",
            _manual_backup_confirm_text(),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self.backup_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            result = create_database_backup()

            message = (
                f"{result.message}\n\n"
                f"Dosya: {result.backup_file}\n"
                f"Boyut: {format_backup_size(result.backup_size_bytes)}\n"
                f"Silinen eski yedek: {result.deleted_old_backup_count}\n"
                f"Mail: {result.mail_message}"
            )

            QMessageBox.information(
                self,
                "Yedekleme Tamamlandı",
                message,
            )

            self.validation_status_label.setText("Doğrulama: Yeni yedek alındı")
            self.validation_status_label.setObjectName("BackupOkBadge")
            self._refresh_widget_style(self.validation_status_label)

            self.load_backups()

        except BackupServiceError as exc:
            QMessageBox.warning(
                self,
                "Yedekleme Başarısız",
                str(exc),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Yedekleme sırasında beklenmeyen hata oluştu:\n\n{exc}",
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.apply_permissions()

    def validate_selected_backup(self) -> None:
        if not self._ensure_restore_test_permission():
            return

        selected_backup_path = self._selected_backup_file_path()

        if selected_backup_path is None:
            QMessageBox.warning(
                self,
                "Yedek Seçilmedi",
                "Doğrulamak için listeden bir yedek dosyası seçmelisin.",
            )
            return

        try:
            result = validate_backup_file(selected_backup_path)

            if result.success:
                self.validation_status_label.setText("Doğrulama: OK")
                self.validation_status_label.setObjectName("BackupOkBadge")
            else:
                self.validation_status_label.setText("Doğrulama: WARN")
                self.validation_status_label.setObjectName("BackupWarnBadge")

            self._refresh_widget_style(self.validation_status_label)

            file_type_text = _validation_file_type_text(
                message=result.message,
                is_postgresql_custom_dump=result.is_postgresql_custom_dump,
            )

            QMessageBox.information(
                self,
                "Yedek Doğrulama Sonucu",
                f"{result.message}\n\n"
                f"Dosya: {result.backup_file}\n"
                f"Boyut: {format_backup_size(result.backup_size_bytes)}\n"
                f"SHA256: {result.sha256}\n"
                f"Dosya Tipi: {file_type_text}",
            )

            self.load_backups()

        except BackupServiceError as exc:
            self.validation_status_label.setText("Doğrulama: FAIL")
            self.validation_status_label.setObjectName("BackupFailBadge")
            self._refresh_widget_style(self.validation_status_label)

            QMessageBox.warning(
                self,
                "Yedek Doğrulanamadı",
                str(exc),
            )
        except Exception as exc:
            self.validation_status_label.setText("Doğrulama: FAIL")
            self.validation_status_label.setObjectName("BackupFailBadge")
            self._refresh_widget_style(self.validation_status_label)

            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Yedek doğrulama sırasında beklenmeyen hata oluştu:\n\n{exc}",
            )

    def restore_selected_backup(self) -> None:
        if not self._ensure_restore_permission():
            return

        if not _is_sqlite_mode():
            QMessageBox.warning(
                self,
                "Geri Yükleme Desteklenmiyor",
                "Bu güvenli geri yükleme akışı şu anda yalnızca SQLite Local mod için aktiftir.",
            )
            return

        selected_backup_path = self._selected_backup_file_path()

        if selected_backup_path is None:
            QMessageBox.warning(
                self,
                "Yedek Seçilmedi",
                "Geri yüklemek için listeden bir yedek dosyası seçmelisin.",
            )
            return

        first_answer = QMessageBox.warning(
            self,
            "Yedekten Geri Yükleme - İlk Onay",
            "Seçili yedek aktif veritabanının üzerine geri yüklenecek.\n\n"
            "Bu işlem mevcut canlı verileri seçili yedekteki verilerle değiştirir.\n"
            "İşlemden önce aktif veritabanının otomatik güvenlik yedeği alınacaktır.\n\n"
            f"Seçili yedek:\n{selected_backup_path}\n\n"
            "Devam etmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if first_answer != QMessageBox.Yes:
            return

        self.restore_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            restore_plan = build_restore_safety_plan(selected_backup_path)

        except RestoreStandardServiceError as exc:
            QMessageBox.warning(
                self,
                "Restore Planı Oluşturulamadı",
                str(exc),
            )
            return

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Restore güvenlik planı oluşturulurken beklenmeyen hata oluştu:\n\n{exc}",
            )
            return

        finally:
            QApplication.restoreOverrideCursor()
            self.apply_permissions()

        plan_summary = "\n".join(get_restore_safety_plan_summary_lines(restore_plan))

        second_answer = QMessageBox.warning(
            self,
            "Yedekten Geri Yükleme - Son Kontrol",
            f"{plan_summary}\n\n"
            "Bu işlemden sonra uygulamayı kapatıp yeniden başlatman gerekecek.\n\n"
            "Geri yüklemeye devam etmek istiyor musun?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if second_answer != QMessageBox.Yes:
            return

        typed_text, ok = QInputDialog.getText(
            self,
            "Elle Onay Gerekli",
            "Gerçek geri yüklemeyi başlatmak için aşağıya aynen GERİ YÜKLE yaz:",
        )

        if not ok:
            return

        if str(typed_text or "").strip() != "GERİ YÜKLE":
            QMessageBox.warning(
                self,
                "Onay Metni Hatalı",
                "Geri yükleme başlatılmadı. Devam etmek için GERİ YÜKLE metni aynen yazılmalıdır.",
            )
            return

        self.restore_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            result = execute_sqlite_restore_from_plan(
                restore_plan,
                confirm_restore=True,
            )

            result_summary = "\n".join(get_restore_execution_summary_lines(result))

            QMessageBox.information(
                self,
                "Yedekten Geri Yükleme Tamamlandı",
                f"{result_summary}\n\n"
                "Önemli: Uygulamayı şimdi kapatıp yeniden başlatmalısın. "
                "Açık ekranlarda eski veriler görünüyor olabilir.",
            )

            self.validation_status_label.setText("Restore: Tamamlandı")
            self.validation_status_label.setObjectName("BackupOkBadge")
            self._refresh_widget_style(self.validation_status_label)
            self.load_backups()

        except RestoreStandardServiceError as exc:
            self.validation_status_label.setText("Restore: FAIL")
            self.validation_status_label.setObjectName("BackupFailBadge")
            self._refresh_widget_style(self.validation_status_label)

            QMessageBox.warning(
                self,
                "Yedekten Geri Yükleme Başarısız",
                str(exc),
            )

        except Exception as exc:
            self.validation_status_label.setText("Restore: FAIL")
            self.validation_status_label.setObjectName("BackupFailBadge")
            self._refresh_widget_style(self.validation_status_label)

            QMessageBox.critical(
                self,
                "Beklenmeyen Hata",
                f"Yedekten geri yükleme sırasında beklenmeyen hata oluştu:\n\n{exc}",
            )

        finally:
            QApplication.restoreOverrideCursor()
            self.apply_permissions()

    def _fill_backup_table(self) -> None:
        self.backup_table.setRowCount(len(self.backup_infos))

        for row_index, backup_info in enumerate(self.backup_infos):
            if _is_sqlite_mode():
                values = [
                    backup_info.file_name,
                    format_backup_size(backup_info.backup_size_bytes),
                    backup_info.created_at.strftime("%d.%m.%Y %H:%M:%S"),
                    backup_info.database_name or "-",
                    backup_info.database_user or "local",
                    backup_info.docker_container or "SQLite Local",
                    backup_info.status,
                    str(backup_info.file_path),
                ]
            else:
                values = [
                    backup_info.file_name,
                    format_backup_size(backup_info.backup_size_bytes),
                    backup_info.created_at.strftime("%d.%m.%Y %H:%M:%S"),
                    backup_info.database_name or "-",
                    backup_info.database_user or "-",
                    backup_info.docker_container or "-",
                    backup_info.status,
                    str(backup_info.file_path),
                ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column_index == 0:
                    item.setData(Qt.UserRole, str(backup_info.file_path))

                if backup_info.status == "OK":
                    item.setForeground(QColor("#e5e7eb"))
                elif backup_info.status == "WARN":
                    item.setForeground(QColor("#fbbf24"))
                else:
                    item.setForeground(QColor("#f87171"))

                if column_index in {1, 6}:
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                item.setToolTip(str(value))
                self.backup_table.setItem(row_index, column_index, item)

        self.backup_table.resizeRowsToContents()

    def _update_summary_badges(self) -> None:
        total_count = len(self.backup_infos)
        self.total_backup_label.setText(f"Yedek: {total_count}")

        if not self.backup_infos:
            self.last_backup_label.setText("Son yedek: Yok")
            self.last_backup_label.setObjectName("BackupWarnBadge")
            self._refresh_widget_style(self.last_backup_label)
            return

        latest_backup = self.backup_infos[0]
        latest_text = latest_backup.created_at.strftime("%d.%m.%Y %H:%M")

        self.last_backup_label.setText(f"Son yedek: {latest_text}")

        if latest_backup.status == "OK":
            self.last_backup_label.setObjectName("BackupOkBadge")
        elif latest_backup.status == "WARN":
            self.last_backup_label.setObjectName("BackupWarnBadge")
        else:
            self.last_backup_label.setObjectName("BackupFailBadge")

        self._refresh_widget_style(self.last_backup_label)

    def _selected_backup_file_path(self) -> Path | None:
        current_row = self.backup_table.currentRow()

        if current_row < 0:
            return None

        first_item = self.backup_table.item(current_row, 0)

        if first_item is None:
            return None

        file_path = first_item.data(Qt.UserRole)

        if not file_path:
            return None

        return Path(str(file_path))

    def _ensure_backup_permission(self) -> bool:
        if user_has_permission(
            current_user=self._current_user(),
            permission=Permission.BACKUP_RUN,
        ):
            return True

        QMessageBox.warning(
            self,
            "Yetkisiz işlem",
            "Manuel yedek almak için BACKUP_RUN yetkisi gerekir.",
        )
        return False

    def _ensure_restore_test_permission(self) -> bool:
        if user_has_permission(
            current_user=self._current_user(),
            permission=Permission.RESTORE_TEST_RUN,
        ):
            return True

        QMessageBox.warning(
            self,
            "Yetkisiz işlem",
            "Yedek doğrulama testi için RESTORE_TEST_RUN yetkisi gerekir.",
        )
        return False

    def _ensure_restore_permission(self) -> bool:
        if user_has_permission(
            current_user=self._current_user(),
            permission=Permission.RESTORE_RUN,
        ):
            return True

        QMessageBox.warning(
            self,
            "Yetkisiz işlem",
            "Yedekten geri yükleme için RESTORE_RUN yetkisi gerekir.",
        )
        return False

    def _current_user(self) -> Any | None:
        window = self.window()

        if window is None:
            return None

        return getattr(window, "current_user", None)

    def _refresh_widget_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


def build_backup_tab() -> QWidget:
    return BackupTab()


__all__ = [
    "BackupTab",
    "build_backup_tab",
]
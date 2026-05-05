# FTM UI tema ve stylesheet dosyası

APP_STYLE = """
QMainWindow {
    background-color: #0b1120;
}

QWidget {
    color: #e5e7eb;
    font-family: Segoe UI;
    font-size: 13px;
}

#AppRoot {
    background-color: #0b1120;
}

#ContentViewport {
    background-color: #0b1120;
}

#Sidebar {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

#LogoBox {
    background-color: #131c2e;
    border: 1px solid #243247;
    border-radius: 16px;
}

#LogoTitle {
    color: #f8fafc;
    font-size: 27px;
    font-weight: 850;
}

#LogoSubtitle {
    color: #9aa7bb;
    font-size: 12px;
    font-weight: 600;
}

#TopBar {
    background-color: #111827;
    border: 1px solid #243247;
    border-radius: 16px;
}

#PageTitle {
    color: #f8fafc;
    font-size: 23px;
    font-weight: 850;
}

#PageSubtitle {
    color: #9aa7bb;
    font-size: 12px;
    font-weight: 500;
}

#SectionTitle {
    color: #f1f5f9;
    font-size: 16px;
    font-weight: 800;
}

#BigTitle {
    color: #f8fafc;
    font-size: 28px;
    font-weight: 900;
}

#MutedText {
    color: #9aa7bb;
}

#UserBadge {
    background-color: #172033;
    color: #dbe4f0;
    border: 1px solid #2a3a52;
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 750;
}

#HealthOk {
    background-color: #0d2a26;
    color: #b7f7d6;
    border: 1px solid #1d7f68;
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 750;
}

#HealthWarn {
    background-color: #32220b;
    color: #fde68a;
    border: 1px solid #a16207;
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 750;
}

#HealthFail {
    background-color: #33191d;
    color: #fecaca;
    border: 1px solid #9f3131;
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 750;
}

QPushButton {
    background-color: #172033;
    color: #d7deea;
    border: 1px solid #2a3a52;
    border-radius: 12px;
    padding: 9px 13px;
    text-align: left;
    font-weight: 650;
}

QPushButton:hover {
    background-color: #1d2a40;
    color: #ffffff;
    border: 1px solid #3b4d68;
}

QPushButton:pressed {
    background-color: #111a2a;
    color: #e5e7eb;
    border: 1px solid #475569;
}

QPushButton:disabled {
    background-color: #111827;
    color: #64748b;
    border: 1px solid #1f2937;
}

QPushButton#PrimaryButton {
    background-color: #1e3a5f;
    color: #f8fafc;
    border: 1px solid #2f6da3;
    text-align: left;
    font-weight: 800;
}

QPushButton#PrimaryButton:hover {
    background-color: #24537f;
    border: 1px solid #3b82b8;
}

QPushButton#PrimaryButton:pressed {
    background-color: #16324f;
}

QPushButton#RefreshButton {
    background-color: #1e3a5f;
    color: #f8fafc;
    border: 1px solid #2f6da3;
    text-align: center;
    font-weight: 800;
}

QPushButton#RefreshButton:hover {
    background-color: #24537f;
    border: 1px solid #3b82b8;
}

QPushButton#RefreshButton:pressed {
    background-color: #16324f;
}

QFrame#Card {
    background-color: #131c2e;
    border: 1px solid #243247;
    border-radius: 16px;
}

QFrame#CardHighlight {
    background-color: #14263d;
    border: 1px solid #2f6da3;
    border-radius: 16px;
}

QFrame#CardRisk {
    background-color: #2a1a1d;
    border: 1px solid #8f3438;
    border-radius: 16px;
}

QFrame#CardSuccess {
    background-color: #102a27;
    border: 1px solid #1f7a68;
    border-radius: 16px;
}

#CardTitle {
    color: #a7b2c5;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.4px;
}

#CardValue {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 900;
}

#CardHint {
    color: #9aa7bb;
    font-size: 11px;
    font-weight: 500;
}

QTableWidget {
    background-color: #111827;
    alternate-background-color: #131c2e;
    border: 1px solid #243247;
    border-radius: 14px;
    gridline-color: #243247;
    selection-background-color: #214d76;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 7px;
    border-bottom: 1px solid #1e293b;
}

QTableWidget::item:selected {
    background-color: #214d76;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #182235;
    color: #d7deea;
    border: none;
    border-right: 1px solid #243247;
    border-bottom: 1px solid #243247;
    padding: 8px;
    font-size: 12px;
    font-weight: 800;
}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QDateEdit,
QSpinBox,
QDoubleSpinBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #2a3a52;
    border-radius: 11px;
    padding: 8px 11px;
    selection-background-color: #214d76;
    selection-color: #ffffff;
}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82b8;
    background-color: #111827;
}

QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled,
QComboBox:disabled,
QDateEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    background-color: #111827;
    color: #64748b;
    border: 1px solid #1f2937;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #2a3a52;
    selection-background-color: #214d76;
    selection-color: #ffffff;
    outline: none;
}

QTabWidget::pane {
    background-color: #111827;
    border: 1px solid #243247;
    border-radius: 14px;
    top: -1px;
}

QTabBar::tab {
    background-color: #131c2e;
    color: #9aa7bb;
    border: 1px solid #243247;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 9px 14px;
    margin-right: 3px;
    font-weight: 700;
}

QTabBar::tab:selected {
    background-color: #1e3a5f;
    color: #ffffff;
    border: 1px solid #2f6da3;
    border-bottom: none;
}

QTabBar::tab:hover {
    background-color: #1d2a40;
    color: #ffffff;
}

QScrollBar:vertical {
    background-color: #0b1120;
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

QScrollBar:horizontal {
    background-color: #0b1120;
    height: 10px;
    margin: 0px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #334155;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #475569;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
    background: none;
    border: none;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

QMessageBox {
    background-color: #111827;
}

QMessageBox QLabel {
    color: #e5e7eb;
}

QToolTip {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 6px;
}
"""


LOGIN_STYLE = """
QDialog {
    background-color: #0b1120;
}

#LoginOuterCard {
    background-color: #131c2e;
    border: 1px solid #243247;
    border-radius: 22px;
}

#LoginLogo {
    color: #f8fafc;
    font-size: 33px;
    font-weight: 900;
}

#LoginTitle {
    color: #f8fafc;
    font-size: 21px;
    font-weight: 850;
}

#LoginSubtitle {
    color: #9aa7bb;
    font-size: 13px;
    font-weight: 500;
}

#LoginLabel {
    color: #d7deea;
    font-weight: 750;
}

QLineEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #2a3a52;
    border-radius: 12px;
    padding: 11px 13px;
    font-size: 14px;
    selection-background-color: #214d76;
    selection-color: #ffffff;
}

QLineEdit:focus {
    border: 1px solid #3b82b8;
    background-color: #111827;
}

QPushButton#LoginButton {
    background-color: #1e3a5f;
    color: #ffffff;
    border: 1px solid #2f6da3;
    border-radius: 14px;
    padding: 12px 17px;
    font-size: 14px;
    font-weight: 850;
    text-align: center;
}

QPushButton#LoginButton:hover {
    background-color: #24537f;
    border: 1px solid #3b82b8;
}

QPushButton#LoginButton:pressed {
    background-color: #16324f;
}

QPushButton#CancelButton {
    background-color: #172033;
    color: #d7deea;
    border: 1px solid #2a3a52;
    border-radius: 14px;
    padding: 12px 17px;
    font-size: 14px;
    font-weight: 750;
    text-align: center;
}

QPushButton#CancelButton:hover {
    background-color: #1d2a40;
    color: #ffffff;
    border: 1px solid #3b4d68;
}

QPushButton#CancelButton:pressed {
    background-color: #111a2a;
}

#LoginFooter {
    color: #7f8da3;
    font-size: 12px;
}
"""


def get_application_stylesheet() -> str:
    return APP_STYLE + LOGIN_STYLE
# FTM UI tema ve stylesheet dosyası
APP_STYLE = """
QMainWindow {
    background-color: #0f172a;
}

QWidget {
    color: #e5e7eb;
    font-family: Segoe UI;
    font-size: 13px;
}

#Sidebar {
    background-color: #111827;
    border-right: 1px solid #1f2937;
}

#LogoBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 18px;
}

#LogoTitle {
    color: #f8fafc;
    font-size: 28px;
    font-weight: 800;
}

#LogoSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

#TopBar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 18px;
}

#PageTitle {
    color: #f8fafc;
    font-size: 24px;
    font-weight: 800;
}

#PageSubtitle {
    color: #94a3b8;
    font-size: 13px;
}

#SectionTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 700;
}

#BigTitle {
    color: #f8fafc;
    font-size: 30px;
    font-weight: 900;
}

#MutedText {
    color: #94a3b8;
}

#UserBadge {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 8px 14px;
    font-weight: 700;
}

#HealthOk {
    background-color: #064e3b;
    color: #d1fae5;
    border: 1px solid #10b981;
    border-radius: 14px;
    padding: 8px 14px;
    font-weight: 700;
}

#HealthWarn {
    background-color: #713f12;
    color: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 14px;
    padding: 8px 14px;
    font-weight: 700;
}

#HealthFail {
    background-color: #7f1d1d;
    color: #fee2e2;
    border: 1px solid #ef4444;
    border-radius: 14px;
    padding: 8px 14px;
    font-weight: 700;
}

QPushButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    color: #ffffff;
    border: 1px solid #475569;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    color: white;
    border: 1px solid #3b82f6;
    text-align: left;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#RefreshButton {
    background-color: #2563eb;
    color: white;
    border: 1px solid #3b82f6;
    text-align: center;
}

QPushButton#RefreshButton:hover {
    background-color: #1d4ed8;
}

QFrame#Card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 20px;
}

QFrame#CardHighlight {
    background-color: #172554;
    border: 1px solid #2563eb;
    border-radius: 20px;
}

QFrame#CardRisk {
    background-color: #3f1d1d;
    border: 1px solid #dc2626;
    border-radius: 20px;
}

QFrame#CardSuccess {
    background-color: #052e2b;
    border: 1px solid #0f766e;
    border-radius: 20px;
}

#CardTitle {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
}

#CardValue {
    color: #f8fafc;
    font-size: 24px;
    font-weight: 900;
}

#CardHint {
    color: #94a3b8;
    font-size: 12px;
}

QTableWidget {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 18px;
    gridline-color: #1f2937;
    selection-background-color: #2563eb;
    selection-color: white;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #cbd5e1;
    border: none;
    padding: 10px;
    font-weight: 700;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #1f2937;
}
"""


LOGIN_STYLE = """
QDialog {
    background-color: #0f172a;
}

#LoginOuterCard {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 26px;
}

#LoginLogo {
    color: #f8fafc;
    font-size: 34px;
    font-weight: 900;
}

#LoginTitle {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 800;
}

#LoginSubtitle {
    color: #94a3b8;
    font-size: 13px;
}

#LoginLabel {
    color: #cbd5e1;
    font-weight: 700;
}

QLineEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 12px 14px;
    font-size: 14px;
}

QLineEdit:focus {
    border: 1px solid #3b82f6;
}

QPushButton#LoginButton {
    background-color: #2563eb;
    color: white;
    border: 1px solid #3b82f6;
    border-radius: 16px;
    padding: 13px 18px;
    font-size: 14px;
    font-weight: 800;
    text-align: center;
}

QPushButton#LoginButton:hover {
    background-color: #1d4ed8;
}

QPushButton#CancelButton {
    background-color: #1f2937;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 13px 18px;
    font-size: 14px;
    font-weight: 700;
    text-align: center;
}

QPushButton#CancelButton:hover {
    background-color: #334155;
}

#LoginFooter {
    color: #64748b;
    font-size: 12px;
}
"""


def get_application_stylesheet() -> str:
    return APP_STYLE + LOGIN_STYLE
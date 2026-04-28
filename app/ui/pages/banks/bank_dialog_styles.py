BANK_DIALOG_STYLES = """
QDialog {
    background-color: #0f172a;
    color: #e5e7eb;
}

QDialog QWidget {
    background-color: #0f172a;
    color: #e5e7eb;
}

QScrollArea {
    background-color: #0f172a;
    border: none;
}

QScrollArea > QWidget {
    background-color: #0f172a;
}

QScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

QLabel {
    color: #e5e7eb;
    font-size: 13px;
    background-color: transparent;
}

QLabel#SectionTitle {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 700;
    background-color: transparent;
}

QLabel#MutedText {
    color: #94a3b8;
    font-size: 13px;
    background-color: transparent;
}

QLineEdit,
QTextEdit,
QComboBox,
QDateEdit {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    font-size: 13px;
}

QLineEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QDateEdit:focus {
    border: 1px solid #38bdf8;
    background-color: #0b1220;
}

QLineEdit::placeholder,
QTextEdit::placeholder {
    color: #64748b;
}

QComboBox::drop-down,
QDateEdit::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: 0;
    padding: 6px;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 6px 10px;
    color: #f8fafc;
    background-color: #111827;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QCalendarWidget QWidget {
    background-color: #111827;
    color: #f8fafc;
}

QCalendarWidget QToolButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}

QCalendarWidget QMenu {
    background-color: #111827;
    color: #f8fafc;
}

QCalendarWidget QSpinBox {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #334155;
}

QCalendarWidget QAbstractItemView {
    background-color: #0f172a;
    color: #f8fafc;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QTableWidget {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #334155;
    border-radius: 12px;
    gridline-color: #1e293b;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #111827;
}

QTableWidget::item {
    padding: 6px;
    border: none;
    background-color: transparent;
}

QTableWidget::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 8px;
    font-weight: 700;
}

QTableCornerButton::section {
    background-color: #1e293b;
    border: 1px solid #334155;
}

QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton:disabled {
    background-color: #1f2937;
    color: #64748b;
    border-color: #334155;
}
"""
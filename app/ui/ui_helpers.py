from decimal import Decimal
from typing import Any

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout


def tr_money(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except Exception:
        amount = Decimal("0.00")

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"{formatted} TL"


def tr_number(value: Any) -> str:
    try:
        number = int(value)
    except Exception:
        number = 0

    return f"{number:,}".replace(",", ".")


def decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def clear_layout(layout: QVBoxLayout | QGridLayout | QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)

        widget = item.widget()

        if widget is not None:
            widget.deleteLater()
            continue

        child_layout = item.layout()

        if child_layout is not None:
            clear_layout(child_layout)
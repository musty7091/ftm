from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate


def qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())


def safe_file_name_text(value: str) -> str:
    text = str(value or "").strip()

    replacements = {
        " ": "_",
        "/": "-",
        "\\": "-",
        ":": "-",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    while "__" in text:
        text = text.replace("__", "_")

    return text.strip("_") or "FTM_Rapor"


def default_reports_folder() -> Path:
    documents_folder = Path.home() / "Documents"
    reports_folder = documents_folder / "FTM Raporlar"

    return reports_folder


def role_text(role: Any) -> str:
    if hasattr(role, "value"):
        return str(role.value)

    return str(role or "").strip().upper()


def username_text(current_user: Any | None) -> str:
    if current_user is None:
        return "FTM Kullanıcısı"

    for attribute_name in ("username", "name", "full_name", "email"):
        value = getattr(current_user, attribute_name, None)

        if value:
            return str(value)

    return "FTM Kullanıcısı"


def created_by_text(current_user: Any | None) -> str:
    username = username_text(current_user)
    role = role_text(getattr(current_user, "role", None))

    if role:
        return f"{username} / {role}"

    return username


def current_month_range() -> tuple[date, date]:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        next_month = date(today.year, today.month + 1, 1)
        end_date = next_month - timedelta(days=1)

    return start_date, end_date


def current_year_range() -> tuple[date, date]:
    today = date.today()

    return date(today.year, 1, 1), date(today.year, 12, 31)


def _qdate_to_date(qdate: QDate) -> date:
    return qdate_to_date(qdate)


def _safe_file_name_text(value: str) -> str:
    return safe_file_name_text(value)


def _default_reports_folder() -> Path:
    return default_reports_folder()


def _role_text(role: Any) -> str:
    return role_text(role)


def _username_text(current_user: Any | None) -> str:
    return username_text(current_user)


def _created_by_text(current_user: Any | None) -> str:
    return created_by_text(current_user)


def _current_month_range() -> tuple[date, date]:
    return current_month_range()


def _current_year_range() -> tuple[date, date]:
    return current_year_range()


__all__ = [
    "qdate_to_date",
    "safe_file_name_text",
    "default_reports_folder",
    "role_text",
    "username_text",
    "created_by_text",
    "current_month_range",
    "current_year_range",
    "_qdate_to_date",
    "_safe_file_name_text",
    "_default_reports_folder",
    "_role_text",
    "_username_text",
    "_created_by_text",
    "_current_month_range",
    "_current_year_range",
]
from typing import Any

from app.models.enums import UserRole


ALL_NAV_ITEMS = [
    "Genel Bakış",
    "Bankalar",
    "POS Mutabakat",
    "Çek Yönetimi",
    "Müşteri / Tedarikçi Kartları",
    "Raporlar",
    "Güvenlik",
    "Sistem",
]


ROLE_PAGE_MAP: dict[str, list[str]] = {
    "ADMIN": [
        "Genel Bakış",
        "Bankalar",
        "POS Mutabakat",
        "Çek Yönetimi",
        "Müşteri / Tedarikçi Kartları",
        "Raporlar",
        "Güvenlik",
        "Sistem",
    ],
    "FINANCE": [
        "Genel Bakış",
        "Bankalar",
        "POS Mutabakat",
        "Çek Yönetimi",
        "Müşteri / Tedarikçi Kartları",
        "Raporlar",
    ],
    "DATA_ENTRY": [
        "Genel Bakış",
        "POS Mutabakat",
        "Çek Yönetimi",
        "Müşteri / Tedarikçi Kartları",
        "Raporlar",
    ],
    "VIEWER": [
        "Genel Bakış",
        "Bankalar",
        "POS Mutabakat",
        "Çek Yönetimi",
        "Müşteri / Tedarikçi Kartları",
        "Raporlar",
    ],
}


def role_to_text(role: Any) -> str:
    if role is None:
        return "ADMIN"

    if isinstance(role, UserRole):
        return role.value

    if hasattr(role, "value"):
        return str(role.value)

    return str(role).strip().upper()


def username_to_text(user: Any) -> str:
    if user is None:
        return "preview"

    username = getattr(user, "username", None)

    if username:
        return str(username)

    return "preview"


def get_allowed_pages_for_role(role: Any) -> list[str]:
    role_text = role_to_text(role)
    pages = ROLE_PAGE_MAP.get(role_text)

    if not pages:
        return ["Genel Bakış"]

    return pages


def count_hidden_pages_for_role(role: Any) -> int:
    allowed_pages = get_allowed_pages_for_role(role)

    return len([item for item in ALL_NAV_ITEMS if item not in allowed_pages])


def can_access_page(role: Any, page_title: str) -> bool:
    allowed_pages = get_allowed_pages_for_role(role)

    return page_title in allowed_pages
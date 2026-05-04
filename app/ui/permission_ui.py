from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtWidgets import QPushButton, QWidget

from app.db.session import session_scope
from app.models.enums import UserRole
from app.services.permission_service import (
    Permission,
    PermissionServiceError,
    has_all_permissions_from_db,
    has_any_permission_from_db,
    has_permission_from_db,
    normalize_role,
)


NO_PERMISSION_TOOLTIP = "Bu işlem için mevcut rolün yetkili değil."


def user_role_text(current_user: Any | None) -> str:
    if current_user is None:
        return UserRole.VIEWER.value

    role = getattr(current_user, "role", None)

    if role is None:
        return UserRole.VIEWER.value

    if hasattr(role, "value"):
        return str(role.value).strip().upper()

    return str(role).strip().upper()


def user_id_value(current_user: Any | None) -> int | None:
    if current_user is None:
        return None

    user_id = getattr(current_user, "id", None)

    if user_id is None:
        return None

    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def user_has_permission(
    current_user: Any | None,
    permission: Permission | str,
) -> bool:
    role_text = user_role_text(current_user)

    try:
        normalized_role = normalize_role(role_text)
    except PermissionServiceError:
        return False

    if normalized_role == UserRole.ADMIN:
        return True

    try:
        with session_scope() as session:
            return has_permission_from_db(
                session,
                normalized_role,
                permission,
                fallback_to_code_defaults=False,
            )
    except Exception:
        return False


def user_has_any_permission(
    current_user: Any | None,
    permissions: Iterable[Permission | str],
) -> bool:
    role_text = user_role_text(current_user)

    try:
        normalized_role = normalize_role(role_text)
    except PermissionServiceError:
        return False

    if normalized_role == UserRole.ADMIN:
        return True

    try:
        with session_scope() as session:
            return has_any_permission_from_db(
                session,
                normalized_role,
                permissions,
                fallback_to_code_defaults=False,
            )
    except Exception:
        return False


def user_has_all_permissions(
    current_user: Any | None,
    permissions: Iterable[Permission | str],
) -> bool:
    role_text = user_role_text(current_user)

    try:
        normalized_role = normalize_role(role_text)
    except PermissionServiceError:
        return False

    if normalized_role == UserRole.ADMIN:
        return True

    try:
        with session_scope() as session:
            return has_all_permissions_from_db(
                session,
                normalized_role,
                permissions,
                fallback_to_code_defaults=False,
            )
    except Exception:
        return False


def set_widget_permission(
    widget: QWidget,
    *,
    allowed: bool,
    tooltip_when_denied: str = NO_PERMISSION_TOOLTIP,
) -> None:
    widget.setEnabled(allowed)

    if allowed:
        widget.setToolTip("")
    else:
        widget.setToolTip(tooltip_when_denied)


def apply_permission_to_button(
    button: QPushButton,
    *,
    current_user: Any | None,
    permission: Permission | str,
    tooltip_when_denied: str = NO_PERMISSION_TOOLTIP,
) -> bool:
    allowed = user_has_permission(
        current_user=current_user,
        permission=permission,
    )

    set_widget_permission(
        button,
        allowed=allowed,
        tooltip_when_denied=tooltip_when_denied,
    )

    return allowed


def apply_any_permission_to_button(
    button: QPushButton,
    *,
    current_user: Any | None,
    permissions: Iterable[Permission | str],
    tooltip_when_denied: str = NO_PERMISSION_TOOLTIP,
) -> bool:
    allowed = user_has_any_permission(
        current_user=current_user,
        permissions=permissions,
    )

    set_widget_permission(
        button,
        allowed=allowed,
        tooltip_when_denied=tooltip_when_denied,
    )

    return allowed


def apply_all_permissions_to_button(
    button: QPushButton,
    *,
    current_user: Any | None,
    permissions: Iterable[Permission | str],
    tooltip_when_denied: str = NO_PERMISSION_TOOLTIP,
) -> bool:
    allowed = user_has_all_permissions(
        current_user=current_user,
        permissions=permissions,
    )

    set_widget_permission(
        button,
        allowed=allowed,
        tooltip_when_denied=tooltip_when_denied,
    )

    return allowed


__all__ = [
    "NO_PERMISSION_TOOLTIP",
    "user_role_text",
    "user_id_value",
    "user_has_permission",
    "user_has_any_permission",
    "user_has_all_permissions",
    "set_widget_permission",
    "apply_permission_to_button",
    "apply_any_permission_to_button",
    "apply_all_permissions_to_button",
]
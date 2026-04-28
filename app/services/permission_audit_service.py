from typing import Any, Optional

from app.db.session import session_scope
from app.services.audit_service import write_audit_log
from app.services.permission_service import (
    Permission,
    PermissionServiceError,
    normalize_permission,
    require_permission_from_db,
)


def _role_value(acting_user: Any) -> str:
    role = getattr(acting_user, "role", None)

    if role is None:
        return "-"

    if hasattr(role, "value"):
        return str(role.value)

    return str(role)


def _username_value(acting_user: Any) -> str:
    username = getattr(acting_user, "username", None)

    if username:
        return str(username)

    return "-"


def _user_id_value(acting_user: Any) -> Optional[int]:
    user_id = getattr(acting_user, "id", None)

    if user_id is None:
        return None

    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def log_permission_denied(
    *,
    acting_user: Any,
    permission: Permission | str,
    attempted_action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    normalized_permission = normalize_permission(permission)

    user_id = _user_id_value(acting_user)
    username = _username_value(acting_user)
    role = _role_value(acting_user)

    audit_entity_type = entity_type or "Permission"
    audit_details = details or {}

    description = (
        f"Yetkisiz işlem denemesi. "
        f"Kullanıcı: {username} | "
        f"Rol: {role} | "
        f"Yetki: {normalized_permission.value} | "
        f"İşlem: {attempted_action}"
    )

    with session_scope() as session:
        write_audit_log(
            session,
            user_id=user_id,
            action="PERMISSION_DENIED",
            entity_type=audit_entity_type,
            entity_id=entity_id,
            description=description,
            old_values=None,
            new_values={
                "user_id": user_id,
                "username": username,
                "role": role,
                "required_permission": normalized_permission.value,
                "attempted_action": attempted_action,
                "entity_type": audit_entity_type,
                "entity_id": entity_id,
                "details": audit_details,
            },
        )

        session.flush()


def require_permission_with_audit(
    *,
    acting_user: Any,
    permission: Permission | str,
    attempted_action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> int:
    normalized_permission = normalize_permission(permission)

    user_id = _user_id_value(acting_user)

    if user_id is None:
        raise PermissionServiceError("İşlem yapan kullanıcı bilgisi geçerli değil.")

    try:
        with session_scope() as session:
            require_permission_from_db(
                session,
                getattr(acting_user, "role", None),
                normalized_permission,
                fallback_to_code_defaults=True,
            )

    except PermissionServiceError as exc:
        log_permission_denied(
            acting_user=acting_user,
            permission=normalized_permission,
            attempted_action=attempted_action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

        raise PermissionServiceError(str(exc)) from exc

    return user_id


__all__ = [
    "log_permission_denied",
    "require_permission_with_audit",
]
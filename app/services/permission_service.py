from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.role_permission import RolePermission


class PermissionServiceError(ValueError):
    pass


class Permission(StrEnum):
    USER_CREATE = "USER_CREATE"
    USER_UPDATE_ROLE = "USER_UPDATE_ROLE"
    USER_DEACTIVATE = "USER_DEACTIVATE"
    USER_REACTIVATE = "USER_REACTIVATE"
    USER_VIEW = "USER_VIEW"

    BANK_CREATE = "BANK_CREATE"
    BANK_UPDATE = "BANK_UPDATE"
    BANK_ACCOUNT_CREATE = "BANK_ACCOUNT_CREATE"
    BANK_ACCOUNT_UPDATE = "BANK_ACCOUNT_UPDATE"
    BANK_ACCOUNT_DEACTIVATE = "BANK_ACCOUNT_DEACTIVATE"
    BANK_ACCOUNT_REACTIVATE = "BANK_ACCOUNT_REACTIVATE"

    POS_DEVICE_CREATE = "POS_DEVICE_CREATE"
    POS_DEVICE_UPDATE = "POS_DEVICE_UPDATE"
    POS_DEVICE_DEACTIVATE = "POS_DEVICE_DEACTIVATE"
    POS_DEVICE_REACTIVATE = "POS_DEVICE_REACTIVATE"

    BUSINESS_PARTNER_CREATE = "BUSINESS_PARTNER_CREATE"
    BUSINESS_PARTNER_VIEW = "BUSINESS_PARTNER_VIEW"

    BANK_TRANSACTION_CREATE = "BANK_TRANSACTION_CREATE"
    BANK_TRANSACTION_CANCEL = "BANK_TRANSACTION_CANCEL"
    BANK_TRANSACTION_VIEW = "BANK_TRANSACTION_VIEW"

    BANK_TRANSFER_CREATE = "BANK_TRANSFER_CREATE"
    BANK_TRANSFER_REALIZE = "BANK_TRANSFER_REALIZE"
    BANK_TRANSFER_CANCEL = "BANK_TRANSFER_CANCEL"
    BANK_TRANSFER_VIEW = "BANK_TRANSFER_VIEW"

    ISSUED_CHECK_CREATE = "ISSUED_CHECK_CREATE"
    ISSUED_CHECK_PAY = "ISSUED_CHECK_PAY"
    ISSUED_CHECK_CANCEL = "ISSUED_CHECK_CANCEL"
    ISSUED_CHECK_VIEW = "ISSUED_CHECK_VIEW"

    RECEIVED_CHECK_CREATE = "RECEIVED_CHECK_CREATE"
    RECEIVED_CHECK_SEND_TO_BANK = "RECEIVED_CHECK_SEND_TO_BANK"
    RECEIVED_CHECK_COLLECT = "RECEIVED_CHECK_COLLECT"
    RECEIVED_CHECK_ENDORSE = "RECEIVED_CHECK_ENDORSE"
    RECEIVED_CHECK_DISCOUNT = "RECEIVED_CHECK_DISCOUNT"
    RECEIVED_CHECK_CANCEL = "RECEIVED_CHECK_CANCEL"
    RECEIVED_CHECK_VIEW = "RECEIVED_CHECK_VIEW"

    POS_SETTLEMENT_CREATE = "POS_SETTLEMENT_CREATE"
    POS_SETTLEMENT_REALIZE = "POS_SETTLEMENT_REALIZE"
    POS_SETTLEMENT_CANCEL = "POS_SETTLEMENT_CANCEL"
    POS_SETTLEMENT_VIEW = "POS_SETTLEMENT_VIEW"

    REPORT_VIEW_ALL = "REPORT_VIEW_ALL"
    REPORT_EXPORT_ALL = "REPORT_EXPORT_ALL"
    REPORT_VIEW_LIMITED = "REPORT_VIEW_LIMITED"
    REPORT_EXPORT_LIMITED = "REPORT_EXPORT_LIMITED"

    AUDIT_LOG_VIEW = "AUDIT_LOG_VIEW"

    BACKUP_RUN = "BACKUP_RUN"
    RESTORE_TEST_RUN = "RESTORE_TEST_RUN"
    RESTORE_RUN = "RESTORE_RUN"

    SYSTEM_SETTINGS_VIEW = "SYSTEM_SETTINGS_VIEW"
    SYSTEM_SETTINGS_UPDATE = "SYSTEM_SETTINGS_UPDATE"


ADMIN_PERMISSIONS = frozenset(
    permission for permission in Permission
)


FINANCE_PERMISSIONS = frozenset(
    {
        Permission.BUSINESS_PARTNER_CREATE,
        Permission.BUSINESS_PARTNER_VIEW,
        Permission.BANK_TRANSACTION_CREATE,
        Permission.BANK_TRANSACTION_CANCEL,
        Permission.BANK_TRANSACTION_VIEW,
        Permission.BANK_TRANSFER_CREATE,
        Permission.BANK_TRANSFER_REALIZE,
        Permission.BANK_TRANSFER_CANCEL,
        Permission.BANK_TRANSFER_VIEW,
        Permission.ISSUED_CHECK_CREATE,
        Permission.ISSUED_CHECK_PAY,
        Permission.ISSUED_CHECK_CANCEL,
        Permission.ISSUED_CHECK_VIEW,
        Permission.RECEIVED_CHECK_CREATE,
        Permission.RECEIVED_CHECK_SEND_TO_BANK,
        Permission.RECEIVED_CHECK_COLLECT,
        Permission.RECEIVED_CHECK_ENDORSE,
        Permission.RECEIVED_CHECK_DISCOUNT,
        Permission.RECEIVED_CHECK_CANCEL,
        Permission.RECEIVED_CHECK_VIEW,
        Permission.POS_SETTLEMENT_CREATE,
        Permission.POS_SETTLEMENT_REALIZE,
        Permission.POS_SETTLEMENT_CANCEL,
        Permission.POS_SETTLEMENT_VIEW,
        Permission.REPORT_VIEW_ALL,
        Permission.REPORT_EXPORT_ALL,
    }
)


DATA_ENTRY_PERMISSIONS = frozenset(
    {
        Permission.BUSINESS_PARTNER_CREATE,
        Permission.BUSINESS_PARTNER_VIEW,
        Permission.ISSUED_CHECK_CREATE,
        Permission.ISSUED_CHECK_VIEW,
        Permission.RECEIVED_CHECK_CREATE,
        Permission.RECEIVED_CHECK_VIEW,
        Permission.POS_SETTLEMENT_CREATE,
        Permission.POS_SETTLEMENT_VIEW,
        Permission.REPORT_VIEW_LIMITED,
        Permission.REPORT_EXPORT_LIMITED,
    }
)


VIEWER_PERMISSIONS = frozenset(
    {
        Permission.BUSINESS_PARTNER_VIEW,
        Permission.BANK_TRANSACTION_VIEW,
        Permission.BANK_TRANSFER_VIEW,
        Permission.ISSUED_CHECK_VIEW,
        Permission.RECEIVED_CHECK_VIEW,
        Permission.POS_SETTLEMENT_VIEW,
        Permission.REPORT_VIEW_ALL,
        Permission.REPORT_EXPORT_ALL,
    }
)


ROLE_PERMISSION_MAP: dict[UserRole, frozenset[Permission]] = {
    UserRole.ADMIN: ADMIN_PERMISSIONS,
    UserRole.FINANCE: FINANCE_PERMISSIONS,
    UserRole.DATA_ENTRY: DATA_ENTRY_PERMISSIONS,
    UserRole.VIEWER: VIEWER_PERMISSIONS,
}


def normalize_role(role: UserRole | str) -> UserRole:
    if isinstance(role, UserRole):
        return role

    try:
        return UserRole(str(role).strip().upper())
    except ValueError as exc:
        raise PermissionServiceError(f"Geçersiz kullanıcı rolü: {role}") from exc


def normalize_permission(permission: Permission | str) -> Permission:
    if isinstance(permission, Permission):
        return permission

    try:
        return Permission(str(permission).strip().upper())
    except ValueError as exc:
        raise PermissionServiceError(f"Geçersiz yetki: {permission}") from exc


def get_permissions_for_role(role: UserRole | str) -> frozenset[Permission]:
    normalized_role = normalize_role(role)

    return ROLE_PERMISSION_MAP.get(normalized_role, frozenset())


def has_permission(role: UserRole | str, permission: Permission | str) -> bool:
    normalized_permission = normalize_permission(permission)
    role_permissions = get_permissions_for_role(role)

    return normalized_permission in role_permissions


def has_any_permission(role: UserRole | str, permissions: Iterable[Permission | str]) -> bool:
    return any(has_permission(role, permission) for permission in permissions)


def has_all_permissions(role: UserRole | str, permissions: Iterable[Permission | str]) -> bool:
    return all(has_permission(role, permission) for permission in permissions)


def require_permission(role: UserRole | str, permission: Permission | str) -> None:
    normalized_role = normalize_role(role)
    normalized_permission = normalize_permission(permission)

    if not has_permission(normalized_role, normalized_permission):
        raise PermissionServiceError(
            f"Bu işlem için yetkiniz yok. Rol: {normalized_role.value}, Yetki: {normalized_permission.value}"
        )


def get_role_permission_names(role: UserRole | str) -> list[str]:
    permissions = get_permissions_for_role(role)

    return sorted(permission.value for permission in permissions)


def get_all_role_permission_matrix() -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {}

    for role in UserRole:
        matrix[role.value] = get_role_permission_names(role)

    return matrix


def get_permissions_for_role_from_db(
    session: Session,
    role: UserRole | str,
    *,
    fallback_to_code_defaults: bool = True,
) -> frozenset[Permission]:
    normalized_role = normalize_role(role)

    statement = select(RolePermission).where(
        RolePermission.role == normalized_role,
    )

    rows = session.execute(statement).scalars().all()

    if not rows:
        if fallback_to_code_defaults:
            return get_permissions_for_role(normalized_role)

        return frozenset()

    allowed_permissions: set[Permission] = set()

    for row in rows:
        if not bool(row.is_allowed):
            continue

        try:
            allowed_permissions.add(normalize_permission(row.permission))
        except PermissionServiceError:
            continue

    return frozenset(allowed_permissions)


def has_permission_from_db(
    session: Session,
    role: UserRole | str,
    permission: Permission | str,
    *,
    fallback_to_code_defaults: bool = True,
) -> bool:
    normalized_permission = normalize_permission(permission)

    role_permissions = get_permissions_for_role_from_db(
        session,
        role,
        fallback_to_code_defaults=fallback_to_code_defaults,
    )

    return normalized_permission in role_permissions


def has_any_permission_from_db(
    session: Session,
    role: UserRole | str,
    permissions: Iterable[Permission | str],
    *,
    fallback_to_code_defaults: bool = True,
) -> bool:
    return any(
        has_permission_from_db(
            session,
            role,
            permission,
            fallback_to_code_defaults=fallback_to_code_defaults,
        )
        for permission in permissions
    )


def has_all_permissions_from_db(
    session: Session,
    role: UserRole | str,
    permissions: Iterable[Permission | str],
    *,
    fallback_to_code_defaults: bool = True,
) -> bool:
    return all(
        has_permission_from_db(
            session,
            role,
            permission,
            fallback_to_code_defaults=fallback_to_code_defaults,
        )
        for permission in permissions
    )


def require_permission_from_db(
    session: Session,
    role: UserRole | str,
    permission: Permission | str,
    *,
    fallback_to_code_defaults: bool = True,
) -> None:
    normalized_role = normalize_role(role)
    normalized_permission = normalize_permission(permission)

    if not has_permission_from_db(
        session,
        normalized_role,
        normalized_permission,
        fallback_to_code_defaults=fallback_to_code_defaults,
    ):
        raise PermissionServiceError(
            f"Bu işlem için yetkiniz yok. Rol: {normalized_role.value}, Yetki: {normalized_permission.value}"
        )


def get_role_permission_names_from_db(
    session: Session,
    role: UserRole | str,
    *,
    fallback_to_code_defaults: bool = True,
) -> list[str]:
    permissions = get_permissions_for_role_from_db(
        session,
        role,
        fallback_to_code_defaults=fallback_to_code_defaults,
    )

    return sorted(permission.value for permission in permissions)


def get_all_role_permission_matrix_from_db(
    session: Session,
    *,
    fallback_to_code_defaults: bool = True,
) -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {}

    for role in UserRole:
        matrix[role.value] = get_role_permission_names_from_db(
            session,
            role,
            fallback_to_code_defaults=fallback_to_code_defaults,
        )

    return matrix


__all__ = [
    "PermissionServiceError",
    "Permission",
    "ADMIN_PERMISSIONS",
    "FINANCE_PERMISSIONS",
    "DATA_ENTRY_PERMISSIONS",
    "VIEWER_PERMISSIONS",
    "ROLE_PERMISSION_MAP",
    "normalize_role",
    "normalize_permission",
    "get_permissions_for_role",
    "has_permission",
    "has_any_permission",
    "has_all_permissions",
    "require_permission",
    "get_role_permission_names",
    "get_all_role_permission_matrix",
    "get_permissions_for_role_from_db",
    "has_permission_from_db",
    "has_any_permission_from_db",
    "has_all_permissions_from_db",
    "require_permission_from_db",
    "get_role_permission_names_from_db",
    "get_all_role_permission_matrix_from_db",
]
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.services.audit_service import write_audit_log
from app.services.permission_service import (
    Permission,
    get_permissions_for_role,
    normalize_role,
)


def _role_text(role: UserRole | str) -> str:
    if isinstance(role, UserRole):
        return role.value

    if hasattr(role, "value"):
        return str(role.value)

    return str(role).strip().upper()


def _permission_text(permission: Permission | str) -> str:
    if isinstance(permission, Permission):
        return permission.value

    if hasattr(permission, "value"):
        return str(permission.value)

    return str(permission).strip().upper()


def count_role_permissions(session: Session) -> int:
    count_statement = select(func.count(RolePermission.id))

    count_value = session.execute(count_statement).scalar_one()

    return int(count_value or 0)


def initialize_default_role_permissions(
    session: Session,
    *,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    """
    Mevcut kod tarafındaki varsayılan rol/yetki yapısını role_permissions tablosuna yükler.

    Önemli:
    - Var olan kayıtları değiştirmez.
    - Eksik kayıtları ekler.
    - Bu nedenle ileride ekrandan yapılan özel yetki değişikliklerini bozmaz.
    """

    created_count = 0
    kept_count = 0

    for role in UserRole:
        default_permissions = get_permissions_for_role(role)

        existing_statement = select(RolePermission).where(
            RolePermission.role == role,
        )
        existing_rows = session.execute(existing_statement).scalars().all()

        existing_by_permission = {
            str(row.permission): row
            for row in existing_rows
        }

        for permission in Permission:
            permission_value = permission.value

            if permission_value in existing_by_permission:
                kept_count += 1
                continue

            role_permission = RolePermission(
                role=role,
                permission=permission_value,
                is_allowed=permission in default_permissions,
            )

            session.add(role_permission)
            created_count += 1

    session.flush()

    total_after = count_role_permissions(session)

    if created_count > 0:
        write_audit_log(
            session,
            user_id=actor_user_id,
            action="ROLE_PERMISSIONS_INITIALIZED",
            entity_type="RolePermission",
            entity_id=None,
            description="Varsayılan rol yetkileri veritabanına yüklendi.",
            old_values=None,
            new_values={
                "created_count": created_count,
                "kept_count": kept_count,
                "total_after": total_after,
            },
        )

    return {
        "created_count": created_count,
        "kept_count": kept_count,
        "total_after": total_after,
    }


def reset_role_permissions_to_code_defaults(
    session: Session,
    *,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    """
    role_permissions tablosunu kod tarafındaki varsayılan yetkilere geri döndürür.

    Bu fonksiyon ileride yönetim ekranında "Varsayılana Döndür" gibi kontrollü bir işlem için kullanılabilir.
    Günlük kullanımda initialize_default_role_permissions tercih edilmelidir.
    """

    old_matrix = get_role_permission_matrix(session)

    created_count = 0
    updated_count = 0
    unchanged_count = 0

    for role in UserRole:
        default_permissions = get_permissions_for_role(role)

        existing_statement = select(RolePermission).where(
            RolePermission.role == role,
        )
        existing_rows = session.execute(existing_statement).scalars().all()

        existing_by_permission = {
            str(row.permission): row
            for row in existing_rows
        }

        for permission in Permission:
            permission_value = permission.value
            expected_is_allowed = permission in default_permissions

            existing_row = existing_by_permission.get(permission_value)

            if existing_row is None:
                role_permission = RolePermission(
                    role=role,
                    permission=permission_value,
                    is_allowed=expected_is_allowed,
                )

                session.add(role_permission)
                created_count += 1
                continue

            if bool(existing_row.is_allowed) != expected_is_allowed:
                existing_row.is_allowed = expected_is_allowed
                updated_count += 1
                continue

            unchanged_count += 1

    session.flush()

    new_matrix = get_role_permission_matrix(session)

    if created_count > 0 or updated_count > 0:
        write_audit_log(
            session,
            user_id=actor_user_id,
            action="ROLE_PERMISSIONS_RESET_TO_DEFAULTS",
            entity_type="RolePermission",
            entity_id=None,
            description="Rol yetkileri kod tarafındaki varsayılan değerlere döndürüldü.",
            old_values=old_matrix,
            new_values=new_matrix,
        )

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "unchanged_count": unchanged_count,
        "total_after": count_role_permissions(session),
    }


def get_allowed_permission_values_for_role(
    session: Session,
    role: UserRole | str,
) -> set[str]:
    normalized_role = normalize_role(role)

    statement = select(RolePermission).where(
        RolePermission.role == normalized_role,
        RolePermission.is_allowed.is_(True),
    )

    rows = session.execute(statement).scalars().all()

    if not rows:
        return {
            permission.value
            for permission in get_permissions_for_role(normalized_role)
        }

    return {
        str(row.permission)
        for row in rows
        if row.permission
    }


def get_allowed_permissions_for_role_from_db(
    session: Session,
    role: UserRole | str,
) -> frozenset[Permission]:
    permission_values = get_allowed_permission_values_for_role(
        session,
        role,
    )

    permissions: set[Permission] = set()

    for permission_value in permission_values:
        try:
            permissions.add(Permission(permission_value))
        except ValueError:
            continue

    return frozenset(permissions)


def get_role_permission_matrix(session: Session) -> dict[str, dict[str, bool]]:
    matrix: dict[str, dict[str, bool]] = {
        role.value: {}
        for role in UserRole
    }

    statement = select(RolePermission).order_by(
        RolePermission.role.asc(),
        RolePermission.permission.asc(),
    )

    rows = session.execute(statement).scalars().all()

    for row in rows:
        role_value = _role_text(row.role)
        permission_value = _permission_text(row.permission)

        if role_value not in matrix:
            matrix[role_value] = {}

        matrix[role_value][permission_value] = bool(row.is_allowed)

    return matrix


__all__ = [
    "count_role_permissions",
    "initialize_default_role_permissions",
    "reset_role_permissions_to_code_defaults",
    "get_allowed_permission_values_for_role",
    "get_allowed_permissions_for_role_from_db",
    "get_role_permission_matrix",
]
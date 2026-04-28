from __future__ import annotations

import pytest

from app.models.enums import UserRole
from app.services.permission_service import Permission, get_permissions_for_role
from app.ui.desktop_app import PAGE_PERMISSION_MAP
from app.ui.pages.security_system.roles_tab import ADMIN_ONLY_PERMISSIONS


EXPECTED_ADMIN_ONLY_PERMISSIONS = {
    Permission.USER_VIEW,
    Permission.USER_CREATE,
    Permission.USER_UPDATE_ROLE,
    Permission.USER_DEACTIVATE,
    Permission.USER_REACTIVATE,
    Permission.AUDIT_LOG_VIEW,
    Permission.BACKUP_RUN,
    Permission.RESTORE_TEST_RUN,
    Permission.SYSTEM_SETTINGS_VIEW,
    Permission.SYSTEM_SETTINGS_UPDATE,
}


NON_ADMIN_ROLES = [
    UserRole.FINANCE,
    UserRole.DATA_ENTRY,
    UserRole.VIEWER,
]


def test_admin_has_all_permissions() -> None:
    admin_permissions = get_permissions_for_role(UserRole.ADMIN)

    assert admin_permissions == frozenset(Permission)


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_non_admin_roles_do_not_have_admin_only_permissions_by_default(
    role: UserRole,
) -> None:
    role_permissions = get_permissions_for_role(role)

    forbidden_permissions = set(role_permissions).intersection(EXPECTED_ADMIN_ONLY_PERMISSIONS)

    assert forbidden_permissions == set()


def test_roles_tab_admin_only_permissions_match_expected_policy() -> None:
    assert ADMIN_ONLY_PERMISSIONS == EXPECTED_ADMIN_ONLY_PERMISSIONS


def test_security_system_page_is_not_in_non_admin_page_permission_map() -> None:
    assert "Güvenlik ve Sistem" not in PAGE_PERMISSION_MAP


def test_all_admin_only_permissions_exist_in_permission_enum() -> None:
    all_permissions = set(Permission)

    missing_permissions = EXPECTED_ADMIN_ONLY_PERMISSIONS.difference(all_permissions)

    assert missing_permissions == set()
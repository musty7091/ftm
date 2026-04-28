from __future__ import annotations

import importlib

import pytest


IMPORTANT_MODULES = [
    "app.core.config",
    "app.db.session",
    "app.models.enums",
    "app.models.user",
    "app.models.role_permission",
    "app.services.auth_service",
    "app.services.audit_service",
    "app.services.permission_service",
    "app.services.permission_audit_service",
    "app.services.app_settings_service",
    "app.services.backup_service",
    "app.ui.navigation",
    "app.ui.permission_ui",
    "app.ui.desktop_app",
    "app.ui.secure_desktop_app",
    "app.ui.pages.security_system_page",
    "app.ui.pages.security_system",
    "app.ui.pages.security_system.users_tab",
    "app.ui.pages.security_system.roles_tab",
    "app.ui.pages.security_system.login_logs_tab",
    "app.ui.pages.security_system.audit_logs_tab",
    "app.ui.pages.security_system.system_settings_tab",
    "app.ui.pages.security_system.backup_tab",
]


@pytest.mark.parametrize("module_name", IMPORTANT_MODULES)
def test_important_modules_can_be_imported(module_name: str) -> None:
    imported_module = importlib.import_module(module_name)

    assert imported_module is not None
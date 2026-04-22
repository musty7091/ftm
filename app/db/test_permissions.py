from app.models.enums import UserRole
from app.services.permission_service import (
    Permission,
    PermissionServiceError,
    get_role_permission_names,
    has_permission,
    require_permission,
)


def _print_role_permissions(role: UserRole) -> None:
    print(f"{role.value} yetkileri")
    print("-" * 80)

    permissions = get_role_permission_names(role)

    for permission in permissions:
        print(f"- {permission}")

    print("")


def _print_permission_check(role: UserRole, permission: Permission) -> None:
    result = has_permission(role, permission)
    result_text = "VAR" if result else "YOK"

    print(f"{role.value} -> {permission.value}: {result_text}")


def main() -> None:
    print("FTM rol / yetki testi")
    print("=" * 80)
    print("")

    for role in UserRole:
        _print_role_permissions(role)

    print("Kritik yetki kontrolleri")
    print("=" * 80)

    _print_permission_check(UserRole.ADMIN, Permission.USER_CREATE)
    _print_permission_check(UserRole.FINANCE, Permission.USER_CREATE)
    _print_permission_check(UserRole.DATA_ENTRY, Permission.POS_SETTLEMENT_REALIZE)
    _print_permission_check(UserRole.FINANCE, Permission.POS_SETTLEMENT_REALIZE)
    _print_permission_check(UserRole.VIEWER, Permission.REPORT_VIEW_ALL)
    _print_permission_check(UserRole.VIEWER, Permission.BANK_TRANSACTION_CREATE)

    print("")
    print("require_permission testleri")
    print("=" * 80)

    try:
        require_permission(UserRole.FINANCE, Permission.POS_SETTLEMENT_REALIZE)
        print("FINANCE POS yatış gerçekleştirme yetkisi: BAŞARILI")
    except PermissionServiceError as exc:
        print(f"Beklenmeyen hata: {exc}")

    try:
        require_permission(UserRole.DATA_ENTRY, Permission.POS_SETTLEMENT_REALIZE)
        print("DATA_ENTRY POS yatış gerçekleştirme yetkisi: HATALI OLARAK GEÇTİ")
    except PermissionServiceError as exc:
        print(f"DATA_ENTRY POS yatış gerçekleştirme yetkisi engellendi: {exc}")


if __name__ == "__main__":
    main()
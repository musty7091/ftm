from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.enums import UserRole
from app.models.role_permission import RolePermission
from app.services.permission_service import Permission, get_permissions_for_role


@dataclass(frozen=True)
class RolePermissionRepairResult:
    expected_role_count: int
    expected_permission_count: int
    expected_total_count: int
    existing_total_count_before: int
    added_count: int
    existing_total_count_after: int
    dry_run: bool


def main() -> None:
    args = _parse_args()

    result = repair_role_permissions(
        dry_run=bool(args.dry_run),
        verbose=not bool(args.quiet),
    )

    print("")
    print("FTM ROL / YETKİ MATRİSİ ONARIM RAPORU")
    print("-" * 72)
    print(f"Rol sayısı              : {result.expected_role_count}")
    print(f"Rol başına yetki        : {result.expected_permission_count}")
    print(f"Beklenen toplam kayıt   : {result.expected_total_count}")
    print(f"Önceki mevcut kayıt     : {result.existing_total_count_before}")
    print(f"Eklenen kayıt           : {result.added_count}")
    print(f"Sonraki mevcut kayıt    : {result.existing_total_count_after}")
    print(f"Dry-run                 : {'EVET' if result.dry_run else 'HAYIR'}")
    print("")

    if result.dry_run:
        print("Dry-run modunda veritabanına yazma yapılmadı.")
    elif result.added_count == 0:
        print("Rol/yetki matrisi zaten eksiksiz görünüyor.")
    else:
        print("Eksik rol/yetki kayıtları başarıyla eklendi.")

    print("")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "FTM role_permissions tablosundaki eksik rol/yetki kayıtlarını "
            "Permission enum ve kod varsayılanlarına göre tamamlar."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Eksikleri gösterir ancak veritabanına kayıt eklemez.",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Satır satır detay çıktısını azaltır.",
    )

    return parser.parse_args()


def repair_role_permissions(
    *,
    dry_run: bool = False,
    verbose: bool = True,
) -> RolePermissionRepairResult:
    expected_roles = list(UserRole)
    expected_permissions = list(Permission)
    expected_total_count = len(expected_roles) * len(expected_permissions)

    added_count = 0

    with session_scope() as session:
        existing_rows = session.execute(
            select(RolePermission)
        ).scalars().all()

        existing_total_count_before = len(existing_rows)

        existing_keys = {
            (
                _normalize_role_value(row.role),
                str(row.permission or "").strip().upper(),
            )
            for row in existing_rows
        }

        for role in expected_roles:
            default_allowed_permissions = get_permissions_for_role(role)

            for permission in expected_permissions:
                key = (role.value, permission.value)

                if key in existing_keys:
                    if verbose:
                        print(f"[SKIP] {role.value} / {permission.value} zaten var.")
                    continue

                is_allowed = permission in default_allowed_permissions

                if dry_run:
                    if verbose:
                        print(
                            f"[DRY ] {role.value} / {permission.value} "
                            f"eklenecek | is_allowed={is_allowed}"
                        )
                    added_count += 1
                    continue

                session.add(
                    RolePermission(
                        role=role,
                        permission=permission.value,
                        is_allowed=is_allowed,
                    )
                )

                existing_keys.add(key)
                added_count += 1

                if verbose:
                    print(
                        f"[ADD ] {role.value} / {permission.value} "
                        f"eklendi | is_allowed={is_allowed}"
                    )

        if dry_run:
            existing_total_count_after = existing_total_count_before
        else:
            session.flush()

            existing_total_count_after = len(
                session.execute(
                    select(RolePermission)
                ).scalars().all()
            )

    return RolePermissionRepairResult(
        expected_role_count=len(expected_roles),
        expected_permission_count=len(expected_permissions),
        expected_total_count=expected_total_count,
        existing_total_count_before=existing_total_count_before,
        added_count=added_count,
        existing_total_count_after=existing_total_count_after,
        dry_run=dry_run,
    )


def _normalize_role_value(role: object) -> str:
    if isinstance(role, UserRole):
        return role.value

    return str(role or "").strip().upper()


if __name__ == "__main__":
    main()
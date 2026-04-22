from getpass import getpass

from app.db.session import session_scope
from app.services.auth_service import (
    AuthServiceError,
    authenticate_user,
    require_user_permission,
    user_has_permission,
)
from app.services.permission_service import Permission


def main() -> None:
    print("FTM kullanıcı giriş testi")
    print("")

    identifier = input("Kullanıcı adı veya e-posta: ").strip()
    password = getpass("Şifre: ")

    try:
        with session_scope() as session:
            authenticated_user = authenticate_user(
                session,
                identifier=identifier,
                password=password,
            )

            session.flush()

            print("")
            print("Giriş başarılı.")
            print(f"Kullanıcı ID : {authenticated_user.id}")
            print(f"Kullanıcı adı: {authenticated_user.username}")
            print(f"Ad soyad     : {authenticated_user.full_name}")
            print(f"E-posta      : {authenticated_user.email or '-'}")
            print(f"Rol          : {authenticated_user.role.value}")
            print(f"Aktif mi     : {authenticated_user.is_active}")
            print("")

            print("Örnek yetki kontrolleri:")
            print(f"- USER_CREATE              : {user_has_permission(authenticated_user, Permission.USER_CREATE)}")
            print(f"- POS_SETTLEMENT_CREATE    : {user_has_permission(authenticated_user, Permission.POS_SETTLEMENT_CREATE)}")
            print(f"- POS_SETTLEMENT_REALIZE   : {user_has_permission(authenticated_user, Permission.POS_SETTLEMENT_REALIZE)}")
            print(f"- REPORT_VIEW_ALL          : {user_has_permission(authenticated_user, Permission.REPORT_VIEW_ALL)}")
            print(f"- BACKUP_RUN               : {user_has_permission(authenticated_user, Permission.BACKUP_RUN)}")
            print("")

            require_user_permission(
                authenticated_user,
                Permission.REPORT_VIEW_ALL,
            )

            print("REPORT_VIEW_ALL yetki testi başarılı.")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
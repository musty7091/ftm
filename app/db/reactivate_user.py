from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.user_service import UserServiceError, reactivate_user


def _role_value(role: UserRole | str) -> str:
    if isinstance(role, UserRole):
        return role.value

    return str(role)


def _show_users() -> None:
    with session_scope() as session:
        users = session.execute(select(User).order_by(User.id)).scalars().all()

        if not users:
            print("Kayıtlı kullanıcı bulunamadı.")
            return

        print("")
        print("Kullanıcılar:")
        print("-" * 90)

        for user in users:
            print(
                f"ID:{user.id} | "
                f"Kullanıcı:{user.username} | "
                f"Ad Soyad:{user.full_name} | "
                f"E-posta:{user.email or '-'} | "
                f"Rol:{_role_value(user.role)} | "
                f"Aktif:{user.is_active}"
            )

        print("-" * 90)


def _ask_required_int(label: str) -> int:
    while True:
        value = input(f"{label}: ").strip()

        if not value:
            print(f"{label} boş olamaz.")
            continue

        if not value.isdigit():
            print(f"{label} sayı olmalıdır.")
            continue

        return int(value)


def main() -> None:
    print("FTM kullanıcı yeniden aktif etme")
    print("")
    print("Bu işlem için ADMIN kullanıcısı ile giriş yapılmalıdır.")
    print("")

    admin_identifier = input("Admin kullanıcı adı veya e-posta: ").strip()
    admin_password = getpass("Admin şifre: ")

    try:
        with session_scope() as session:
            acting_user = authenticate_user(
                session,
                identifier=admin_identifier,
                password=admin_password,
            )

            session.flush()

            print("")
            print(f"Admin doğrulandı: {acting_user.username} / {acting_user.role.value}")

        _show_users()

        target_user_id = _ask_required_int("Yeniden aktif edilecek kullanıcı ID")

        confirmation = input(
            f"Kullanıcı ID {target_user_id} yeniden aktif edilecek. Onaylıyor musun? [EVET/hayır]: "
        ).strip()

        if confirmation != "EVET":
            print("İşlem iptal edildi.")
            return

        with session_scope() as session:
            reactivated_user = reactivate_user(
                session,
                acting_user=acting_user,
                target_user_id=target_user_id,
            )

            session.flush()

            print("")
            print("Kullanıcı başarıyla yeniden aktif edildi.")
            print(f"Kullanıcı ID : {reactivated_user.id}")
            print(f"Kullanıcı adı: {reactivated_user.username}")
            print(f"Ad soyad     : {reactivated_user.full_name}")
            print(f"E-posta      : {reactivated_user.email or '-'}")
            print(f"Rol          : {_role_value(reactivated_user.role)}")
            print(f"Aktif mi     : {reactivated_user.is_active}")

    except AuthServiceError as exc:
        print("")
        print(f"Admin doğrulama başarısız: {exc}")
        raise SystemExit(1) from exc

    except UserServiceError as exc:
        print("")
        print(f"Kullanıcı yeniden aktif etme işlemi başarısız: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.user_service import UserServiceError, deactivate_user


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
    print("FTM kullanıcı pasifleştirme")
    print("")
    print("Bu işlem için ADMIN kullanıcısı ile giriş yapılmalıdır.")
    print("Not: Kullanıcı silinmez, sadece pasifleştirilir.")
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

        target_user_id = _ask_required_int("Pasifleştirilecek kullanıcı ID")

        confirmation = input(
            f"Kullanıcı ID {target_user_id} pasifleştirilecek. Onaylıyor musun? [EVET/hayır]: "
        ).strip()

        if confirmation != "EVET":
            print("İşlem iptal edildi.")
            return

        with session_scope() as session:
            deactivated_user = deactivate_user(
                session,
                acting_user=acting_user,
                target_user_id=target_user_id,
            )

            session.flush()

            print("")
            print("Kullanıcı başarıyla pasifleştirildi.")
            print(f"Kullanıcı ID : {deactivated_user.id}")
            print(f"Kullanıcı adı: {deactivated_user.username}")
            print(f"Ad soyad     : {deactivated_user.full_name}")
            print(f"E-posta      : {deactivated_user.email or '-'}")
            print(f"Rol          : {_role_value(deactivated_user.role)}")
            print(f"Aktif mi     : {deactivated_user.is_active}")

    except AuthServiceError as exc:
        print("")
        print(f"Admin doğrulama başarısız: {exc}")
        raise SystemExit(1) from exc

    except UserServiceError as exc:
        print("")
        print(f"Kullanıcı pasifleştirme işlemi başarısız: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
from getpass import getpass

from sqlalchemy import func, select

from app.db.session import session_scope
from app.models.enums import UserRole
from app.models.user import User
from app.services.user_service import UserServiceError, create_user


def _ask_required_text(label: str, default_value: str = "") -> str:
    while True:
        if default_value:
            value = input(f"{label} [{default_value}]: ").strip() or default_value
        else:
            value = input(f"{label}: ").strip()

        if value:
            return value

        print(f"{label} boş olamaz.")


def _ask_optional_text(label: str, default_value: str = "") -> str:
    if default_value:
        return input(f"{label} [{default_value}]: ").strip() or default_value

    return input(f"{label}: ").strip()


def _ask_password_twice() -> str:
    while True:
        password = getpass("Şifre: ")
        password_again = getpass("Şifre tekrar: ")

        if password != password_again:
            print("Şifreler aynı değil. Tekrar deneyin.")
            continue

        return password


def main() -> None:
    with session_scope() as session:
        user_count = session.execute(select(func.count(User.id))).scalar_one()

        if user_count > 0:
            print("Sistemde zaten kullanıcı var.")
            print("İlk admin oluşturma işlemi tekrar çalıştırılamaz.")
            return

        print("FTM ilk admin kullanıcısı oluşturulacak.")
        print("")

        username = _ask_required_text("Kullanıcı adı", "admin")
        full_name = _ask_required_text("Ad soyad", "FTM Admin")
        email = _ask_optional_text("E-posta")
        password = _ask_password_twice()

        try:
            user = create_user(
                session,
                username=username,
                full_name=full_name,
                email=email,
                password=password,
                role=UserRole.ADMIN,
                created_by_user_id=None,
                must_change_password=False,
            )
        except UserServiceError as exc:
            print(f"Kullanıcı oluşturulamadı: {exc}")
            raise SystemExit(1) from exc

        session.flush()

        print("")
        print("İlk admin kullanıcısı başarıyla oluşturuldu.")
        print(f"Kullanıcı ID : {user.id}")
        print(f"Kullanıcı adı: {user.username}")
        print(f"Rol         : {user.role.value}")


if __name__ == "__main__":
    main()
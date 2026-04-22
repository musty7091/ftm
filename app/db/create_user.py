from getpass import getpass

from app.db.session import session_scope
from app.models.enums import UserRole
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.user_service import UserServiceError, create_user_by_admin


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
        password = getpass("Yeni kullanıcı şifresi: ")
        password_again = getpass("Yeni kullanıcı şifresi tekrar: ")

        if password != password_again:
            print("Şifreler eşleşmiyor.")
            continue

        return password


def _select_role() -> UserRole:
    roles = [
        UserRole.ADMIN,
        UserRole.FINANCE,
        UserRole.DATA_ENTRY,
        UserRole.VIEWER,
    ]

    print("")
    print("Kullanıcı rolü seç:")

    for index, role in enumerate(roles, start=1):
        print(f"{index}. {role.value}")

    while True:
        value = input("Seçim [2 - FINANCE]: ").strip() or "2"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(roles):
            return roles[selected_index - 1]

        print("Geçersiz seçim.")


def main() -> None:
    print("FTM yeni kullanıcı oluşturma")
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

            username = _ask_required_text("Yeni kullanıcı adı")
            full_name = _ask_required_text("Ad soyad")
            email = _ask_optional_text("E-posta")
            role = _select_role()
            password = _ask_password_twice()

            new_user = create_user_by_admin(
                session,
                acting_user=acting_user,
                username=username,
                full_name=full_name,
                email=email,
                password=password,
                role=role,
                must_change_password=True,
            )

            session.flush()

            print("")
            print("Yeni kullanıcı başarıyla oluşturuldu.")
            print(f"Kullanıcı ID : {new_user.id}")
            print(f"Kullanıcı adı: {new_user.username}")
            print(f"Ad soyad     : {new_user.full_name}")
            print(f"E-posta      : {new_user.email or '-'}")
            print(f"Rol          : {new_user.role.value}")
            print(f"Aktif mi     : {new_user.is_active}")
            print(f"Şifre değişimi zorunlu mu: {new_user.must_change_password}")

    except AuthServiceError as exc:
        print("")
        print(f"Admin doğrulama başarısız: {exc}")
        raise SystemExit(1) from exc

    except UserServiceError as exc:
        print("")
        print(f"Kullanıcı oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
from sqlalchemy import select

from app.db.session import session_scope
from app.models.user import User
from app.models.enums import UserRole


def main() -> None:
    print("FTM kullanıcı listesi")
    print("")

    with session_scope() as session:
        statement = select(User).order_by(User.id)

        users = session.execute(statement).scalars().all()

        if not users:
            print("Kayıtlı kullanıcı bulunamadı.")
            return

        for user in users:
            role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)

            print(
                f"ID:{user.id} | "
                f"Kullanıcı:{user.username} | "
                f"Ad Soyad:{user.full_name} | "
                f"E-posta:{user.email or '-'} | "
                f"Rol:{role_value} | "
                f"Aktif:{user.is_active}"
            )


if __name__ == "__main__":
    main()
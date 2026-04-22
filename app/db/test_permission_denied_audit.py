from getpass import getpass

from app.db.session import session_scope
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.permission_audit_service import require_permission_with_audit
from app.services.permission_service import Permission, PermissionServiceError


def main() -> None:
    print("FTM yetkisiz işlem audit log testi")
    print("")
    print("Bu test için DATA_ENTRY veya VIEWER kullanıcı ile giriş yap.")
    print("Örnek: melek / DATA_ENTRY")
    print("")

    identifier = input("Kullanıcı adı veya e-posta: ").strip()
    password = getpass("Şifre: ")

    try:
        with session_scope() as session:
            acting_user = authenticate_user(
                session,
                identifier=identifier,
                password=password,
            )

            session.flush()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")
        print("")
        print("Test edilen yetki: BANK_TRANSACTION_CREATE")
        print("Bu yetki DATA_ENTRY ve VIEWER rollerinde olmamalı.")
        print("")

        try:
            require_permission_with_audit(
                acting_user=acting_user,
                permission=Permission.BANK_TRANSACTION_CREATE,
                attempted_action="TEST_BANK_TRANSACTION_CREATE",
                entity_type="BankTransaction",
                entity_id=None,
                details={
                    "test_source": "app.db.test_permission_denied_audit",
                    "expected_result": "PERMISSION_DENIED",
                },
            )

            print("Bu kullanıcıda BANK_TRANSACTION_CREATE yetkisi var.")
            print("Bu testte PERMISSION_DENIED kaydı oluşmadı.")

        except PermissionServiceError as exc:
            print("Yetkisiz işlem doğru şekilde engellendi.")
            print(f"Hata: {exc}")
            print("")
            print("Audit log içinde PERMISSION_DENIED kaydı oluşmuş olmalı.")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
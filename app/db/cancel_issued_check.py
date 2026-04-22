from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.check import IssuedCheck
from app.models.enums import IssuedCheckStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.check_service import CheckServiceError, cancel_issued_check


def _login_user():
    print("İşlem yapacak kullanıcı ile giriş yap")
    identifier = input("Kullanıcı adı veya e-posta: ").strip()
    password = getpass("Şifre: ")

    with session_scope() as session:
        authenticated_user = authenticate_user(
            session,
            identifier=identifier,
            password=password,
        )

        session.flush()

        return authenticated_user


def _show_cancellable_issued_checks() -> None:
    with session_scope() as session:
        statement = (
            select(IssuedCheck, BankAccount, Bank)
            .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(
                IssuedCheck.status.notin_(
                    [
                        IssuedCheckStatus.PAID,
                        IssuedCheckStatus.CANCELLED,
                    ]
                )
            )
            .order_by(IssuedCheck.due_date, IssuedCheck.id)
        )

        rows = session.execute(statement).all()

        if not rows:
            print("İptal edilebilir yazılan çek bulunamadı.")
            return

        print("")
        print("İptal edilebilir yazılan çekler:")
        print("")

        for check, bank_account, bank in rows:
            print(
                f"ID:{check.id} | "
                f"No:{check.check_number} | "
                f"Banka:{bank.name} / {bank_account.account_name} | "
                f"Vade:{check.due_date} | "
                f"Tutar:{check.amount} {check.currency_code.value} | "
                f"Durum:{check.status.value}"
            )


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


def _ask_required_text(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()

        if value:
            return value

        print(f"{label} boş olamaz.")


def main() -> None:
    print("FTM yazılan çek iptal etme")
    print("")
    print("Not: Ödenmiş çek bu işlemle iptal edilemez.")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        _show_cancellable_issued_checks()

        issued_check_id = _ask_required_int("İptal edilecek yazılan çek ID")
        cancel_reason = _ask_required_text("İptal nedeni")

        confirmation = input(
            f"Yazılan çek ID {issued_check_id} iptal edilecek. Onaylıyor musun? [EVET/hayır]: "
        ).strip()

        if confirmation != "EVET":
            print("İşlem iptal edildi.")
            return

        with session_scope() as session:
            check = cancel_issued_check(
                session,
                issued_check_id=issued_check_id,
                cancel_reason=cancel_reason,
                acting_user=acting_user,
            )

            session.flush()

            print("")
            print("Yazılan çek başarıyla iptal edildi.")
            print(f"Çek ID        : {check.id}")
            print(f"Çek no        : {check.check_number}")
            print(f"Yeni durum    : {check.status.value}")
            print(f"İptal nedeni  : {check.cancel_reason}")
            print(f"İşlemi yapan  : {acting_user.username}")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except CheckServiceError as exc:
        print("")
        print(f"Yazılan çek iptal edilemedi: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
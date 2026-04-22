from datetime import date
from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.check import IssuedCheck
from app.models.enums import IssuedCheckStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.check_service import CheckServiceError, pay_issued_check


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


def _ask_optional_text(label: str, default_value: str = "") -> str:
    if default_value:
        return input(f"{label} [{default_value}]: ").strip() or default_value

    return input(f"{label}: ").strip()


def _ask_date(label: str, default_value: date) -> date:
    while True:
        value = input(f"{label} [{default_value.isoformat()}]: ").strip() or default_value.isoformat()

        try:
            return date.fromisoformat(value)
        except ValueError:
            print(f"{label} YYYY-MM-DD formatında olmalıdır.")


def _show_payable_issued_checks() -> None:
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
            print("Ödenebilir yazılan çek bulunamadı.")
            return

        print("")
        print("Ödenebilir yazılan çekler:")
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


def _get_bank_account_id_for_check(issued_check_id: int) -> int:
    with session_scope() as session:
        check = session.get(IssuedCheck, issued_check_id)

        if check is None:
            raise CheckServiceError(f"Yazılan çek bulunamadı. Çek ID: {issued_check_id}")

        return check.bank_account_id


def _print_balance_summary(bank_account_id: int, title: str) -> None:
    with session_scope() as session:
        summary = get_bank_account_balance_summary(
            session,
            bank_account_id=bank_account_id,
        )

        print(title)
        print(f"Hesap ID       : {summary['bank_account_id']}")
        print(f"Hesap adı      : {summary['account_name']}")
        print(f"Para birimi    : {summary['currency_code']}")
        print(f"Güncel bakiye  : {summary['current_balance']}")
        print("")


def main() -> None:
    print("FTM yazılan çek ödeme")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        _show_payable_issued_checks()

        issued_check_id = _ask_required_int("Ödenecek çek ID")
        payment_date = _ask_date("Ödeme tarihi", date.today())
        reference_no = _ask_optional_text("Banka referans no")
        description = _ask_optional_text("Açıklama")

        bank_account_id = _get_bank_account_id_for_check(issued_check_id)

        print("")
        _print_balance_summary(bank_account_id, "Çek ödemesi öncesi banka bakiyesi:")

        with session_scope() as session:
            check = pay_issued_check(
                session,
                issued_check_id=issued_check_id,
                payment_date=payment_date,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("Yazılan çek başarıyla ödendi.")
            print(f"Çek ID            : {check.id}")
            print(f"Çek no            : {check.check_number}")
            print(f"Yeni durum        : {check.status.value}")
            print(f"Banka hareket ID  : {check.paid_transaction_id}")
            print(f"Tutar             : {check.amount} {check.currency_code.value}")
            print(f"İşlemi yapan      : {acting_user.username}")
            print("")

        _print_balance_summary(bank_account_id, "Çek ödemesi sonrası banka bakiyesi:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except CheckServiceError as exc:
        print("")
        print(f"Yazılan çek ödenemedi: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.models.enums import BankTransactionStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import (
    BankTransactionServiceError,
    cancel_bank_transaction,
    get_bank_account_balance_summary,
)


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


def _show_cancellable_bank_transactions() -> None:
    with session_scope() as session:
        statement = (
            select(BankTransaction, BankAccount, Bank)
            .join(BankAccount, BankTransaction.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(BankTransaction.status != BankTransactionStatus.CANCELLED)
            .order_by(BankTransaction.id)
        )

        rows = session.execute(statement).all()

        if not rows:
            print("İptal edilebilir banka hareketi bulunamadı.")
            return

        print("")
        print("Banka hareketleri:")
        print("")

        for bank_transaction, bank_account, bank in rows:
            print(
                f"ID:{bank_transaction.id} | "
                f"{bank.name} / {bank_account.account_name} | "
                f"{bank_transaction.transaction_date} | "
                f"{bank_transaction.direction.value} | "
                f"{bank_transaction.status.value} | "
                f"{bank_transaction.amount} {bank_transaction.currency_code.value} | "
                f"Ref: {bank_transaction.reference_no or '-'}"
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


def _get_bank_account_id_for_transaction(bank_transaction_id: int) -> int:
    with session_scope() as session:
        bank_transaction = session.get(BankTransaction, bank_transaction_id)

        if bank_transaction is None:
            raise BankTransactionServiceError(f"Banka hareketi bulunamadı. Hareket ID: {bank_transaction_id}")

        return bank_transaction.bank_account_id


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
    print("FTM banka hareketi iptal etme")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        _show_cancellable_bank_transactions()

        bank_transaction_id = _ask_required_int("İptal edilecek hareket ID")
        cancel_reason = _ask_required_text("İptal nedeni")

        bank_account_id = _get_bank_account_id_for_transaction(bank_transaction_id)

        print("")
        _print_balance_summary(bank_account_id, "İptal öncesi banka bakiyesi:")

        with session_scope() as session:
            cancelled_transaction = cancel_bank_transaction(
                session,
                bank_transaction_id=bank_transaction_id,
                cancel_reason=cancel_reason,
                acting_user=acting_user,
            )

            session.flush()

            print("Banka hareketi başarıyla iptal edildi.")
            print(f"Hareket ID       : {cancelled_transaction.id}")
            print(f"Yeni durum       : {cancelled_transaction.status.value}")
            print(f"İptal nedeni     : {cancelled_transaction.cancel_reason}")
            print(f"İşlemi yapan     : {acting_user.username}")
            print("")

        _print_balance_summary(bank_account_id, "İptal sonrası banka bakiyesi:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except BankTransactionServiceError as exc:
        print("")
        print(f"Banka hareketi iptal edilemedi: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
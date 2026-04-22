from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transfer import BankTransfer
from app.models.enums import BankTransferStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.bank_transfer_service import BankTransferServiceError, cancel_bank_transfer


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


def _show_cancellable_transfers() -> None:
    with session_scope() as session:
        from_account_alias = BankAccount
        from_bank_alias = Bank

        statement = (
            select(BankTransfer)
            .where(BankTransfer.status != BankTransferStatus.CANCELLED)
            .order_by(BankTransfer.id)
        )

        transfers = session.execute(statement).scalars().all()

        if not transfers:
            print("İptal edilebilir banka transferi bulunamadı.")
            return

        print("")
        print("İptal edilebilir banka transferleri:")
        print("-" * 100)

        for transfer in transfers:
            from_account = session.get(from_account_alias, transfer.from_bank_account_id)
            to_account = session.get(BankAccount, transfer.to_bank_account_id)

            from_bank = session.get(from_bank_alias, from_account.bank_id) if from_account else None
            to_bank = session.get(Bank, to_account.bank_id) if to_account else None

            from_label = (
                f"{from_bank.name} / {from_account.account_name}"
                if from_bank and from_account
                else f"Hesap ID:{transfer.from_bank_account_id}"
            )

            to_label = (
                f"{to_bank.name} / {to_account.account_name}"
                if to_bank and to_account
                else f"Hesap ID:{transfer.to_bank_account_id}"
            )

            print(
                f"ID:{transfer.id} | "
                f"{from_label} -> {to_label} | "
                f"Tarih:{transfer.transfer_date} | "
                f"Tutar:{transfer.amount} {transfer.currency_code.value} | "
                f"Durum:{transfer.status.value} | "
                f"Ref:{transfer.reference_no or '-'}"
            )

        print("-" * 100)


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


def _get_transfer_account_ids(transfer_id: int) -> tuple[int, int]:
    with session_scope() as session:
        transfer = session.get(BankTransfer, transfer_id)

        if transfer is None:
            raise BankTransferServiceError(f"Banka transferi bulunamadı. Transfer ID: {transfer_id}")

        return transfer.from_bank_account_id, transfer.to_bank_account_id


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
    print("FTM banka transferi iptal etme")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        _show_cancellable_transfers()

        transfer_id = _ask_required_int("İptal edilecek transfer ID")
        cancel_reason = _ask_required_text("İptal nedeni")

        from_bank_account_id, to_bank_account_id = _get_transfer_account_ids(transfer_id)

        print("")
        _print_balance_summary(from_bank_account_id, "İptal öncesi çıkış hesabı bakiyesi:")
        _print_balance_summary(to_bank_account_id, "İptal öncesi giriş hesabı bakiyesi:")

        with session_scope() as session:
            cancelled_transfer = cancel_bank_transfer(
                session,
                transfer_id=transfer_id,
                cancel_reason=cancel_reason,
                acting_user=acting_user,
            )

            session.flush()

            print("Banka transferi başarıyla iptal edildi.")
            print(f"Transfer ID      : {cancelled_transfer.id}")
            print(f"Yeni durum       : {cancelled_transfer.status.value}")
            print(f"İptal nedeni     : {cancelled_transfer.cancel_reason}")
            print(f"İşlemi yapan     : {acting_user.username}")
            print("")

        _print_balance_summary(from_bank_account_id, "İptal sonrası çıkış hesabı bakiyesi:")
        _print_balance_summary(to_bank_account_id, "İptal sonrası giriş hesabı bakiyesi:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except BankTransferServiceError as exc:
        print("")
        print(f"Banka transferi iptal edilemedi: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
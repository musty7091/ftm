from datetime import date
from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.enums import BankTransferStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.bank_transfer_service import BankTransferServiceError, create_bank_transfer
from app.utils.decimal_utils import DecimalParseError, money


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


def _ask_money(label: str, default_value: str = "0") -> object:
    while True:
        value = input(f"{label} [{default_value}]: ").strip() or default_value

        try:
            return money(value, field_name=label)
        except DecimalParseError as exc:
            print(exc)


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


def _load_bank_accounts() -> list[tuple[BankAccount, Bank]]:
    with session_scope() as session:
        statement = (
            select(BankAccount, Bank)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(BankAccount.is_active.is_(True))
            .order_by(Bank.name, BankAccount.account_name)
        )

        rows = session.execute(statement).all()

        return [(bank_account, bank) for bank_account, bank in rows]


def _select_bank_account(label: str, excluded_bank_account_id: int | None = None) -> int:
    rows = _load_bank_accounts()

    if not rows:
        raise SystemExit("Aktif banka hesabı bulunamadı. Önce banka hesabı oluşturmalısın.")

    filtered_rows = []

    for bank_account, bank in rows:
        if excluded_bank_account_id is not None and bank_account.id == excluded_bank_account_id:
            continue

        filtered_rows.append((bank_account, bank))

    if not filtered_rows:
        raise SystemExit("Seçilebilir başka aktif banka hesabı bulunamadı.")

    print("")
    print(label)

    for index, row in enumerate(filtered_rows, start=1):
        bank_account, bank = row
        print(
            f"{index}. ID:{bank_account.id} | "
            f"{bank.name} / {bank_account.account_name} | "
            f"{bank_account.currency_code.value}"
        )

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(filtered_rows):
            selected_bank_account, _selected_bank = filtered_rows[selected_index - 1]
            return selected_bank_account.id

        print("Geçersiz seçim.")


def _select_status() -> BankTransferStatus:
    print("")
    print("Transfer durumu seç:")
    print("1. PLANNED - Planlandı")
    print("2. REALIZED - Gerçekleşti")

    while True:
        value = input("Seçim [2 - REALIZED]: ").strip() or "2"

        if value == "1":
            return BankTransferStatus.PLANNED

        if value == "2":
            return BankTransferStatus.REALIZED

        print("Geçersiz seçim.")


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
    print("FTM banka transferi oluşturma")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        from_bank_account_id = _select_bank_account("Çıkış yapılacak banka hesabı seç:")
        to_bank_account_id = _select_bank_account(
            "Giriş yapılacak banka hesabı seç:",
            excluded_bank_account_id=from_bank_account_id,
        )

        transfer_date = _ask_date("Transfer tarihi", date.today())

        value_date_input = input("Valör tarihi (YYYY-MM-DD, boş bırakılabilir): ").strip()
        value_date = date.fromisoformat(value_date_input) if value_date_input else None

        amount = _ask_money("Transfer tutarı", "0")
        status = _select_status()
        reference_no = _ask_optional_text("Referans no")
        description = _ask_optional_text("Açıklama")

        print("")
        _print_balance_summary(from_bank_account_id, "Transfer öncesi çıkış hesabı bakiyesi:")
        _print_balance_summary(to_bank_account_id, "Transfer öncesi giriş hesabı bakiyesi:")

        with session_scope() as session:
            bank_transfer = create_bank_transfer(
                session,
                from_bank_account_id=from_bank_account_id,
                to_bank_account_id=to_bank_account_id,
                transfer_date=transfer_date,
                value_date=value_date,
                amount=amount,
                status=status,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("Banka transferi başarıyla kaydedildi.")
            print(f"Transfer ID          : {bank_transfer.id}")
            print(f"Çıkış hesap ID       : {bank_transfer.from_bank_account_id}")
            print(f"Giriş hesap ID       : {bank_transfer.to_bank_account_id}")
            print(f"Transfer tarihi      : {bank_transfer.transfer_date}")
            print(f"Valör tarihi         : {bank_transfer.value_date or '-'}")
            print(f"Tutar                : {bank_transfer.amount} {bank_transfer.currency_code.value}")
            print(f"Durum                : {bank_transfer.status.value}")
            print(f"Çıkış hareket ID     : {bank_transfer.outgoing_transaction_id}")
            print(f"Giriş hareket ID     : {bank_transfer.incoming_transaction_id}")
            print(f"İşlemi yapan         : {acting_user.username}")
            print("")

        _print_balance_summary(from_bank_account_id, "Transfer sonrası çıkış hesabı bakiyesi:")
        _print_balance_summary(to_bank_account_id, "Transfer sonrası giriş hesabı bakiyesi:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except BankTransferServiceError as exc:
        print("")
        print(f"Banka transferi oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
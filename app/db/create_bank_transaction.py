from datetime import date
from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.enums import (
    BankTransactionStatus,
    FinancialSourceType,
    TransactionDirection,
)
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import BankTransactionServiceError, create_bank_transaction, get_bank_account_balance_summary
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


def _select_bank_account() -> int:
    rows = _load_bank_accounts()

    if not rows:
        raise SystemExit("Aktif banka hesabı bulunamadı. Önce banka hesabı oluşturmalısın.")

    print("")
    print("Banka hesabı seç:")

    for index, row in enumerate(rows, start=1):
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

        if 1 <= selected_index <= len(rows):
            selected_bank_account, _selected_bank = rows[selected_index - 1]
            return selected_bank_account.id

        print("Geçersiz seçim.")


def _select_direction() -> TransactionDirection:
    print("")
    print("Hareket yönü seç:")
    print("1. IN - Giriş")
    print("2. OUT - Çıkış")

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if value == "1":
            return TransactionDirection.IN

        if value == "2":
            return TransactionDirection.OUT

        print("Geçersiz seçim.")


def _select_status() -> BankTransactionStatus:
    print("")
    print("Hareket durumu seç:")
    print("1. PLANNED")
    print("2. REALIZED")
    print("3. CANCELLED")

    while True:
        value = input("Seçim [2 - REALIZED]: ").strip() or "2"

        if value == "1":
            return BankTransactionStatus.PLANNED

        if value == "2":
            return BankTransactionStatus.REALIZED

        if value == "3":
            return BankTransactionStatus.CANCELLED

        print("Geçersiz seçim.")


def _select_source_type() -> FinancialSourceType:
    source_types = [
        FinancialSourceType.OPENING_BALANCE,
        FinancialSourceType.CASH_DEPOSIT,
        FinancialSourceType.BANK_TRANSFER,
        FinancialSourceType.ISSUED_CHECK,
        FinancialSourceType.RECEIVED_CHECK,
        FinancialSourceType.POS_SETTLEMENT,
        FinancialSourceType.MANUAL_ADJUSTMENT,
        FinancialSourceType.OTHER,
    ]

    print("")
    print("Kaynak türü seç:")

    for index, source_type in enumerate(source_types, start=1):
        print(f"{index}. {source_type.value}")

    while True:
        value = input("Seçim [7 - MANUAL_ADJUSTMENT]: ").strip() or "7"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(source_types):
            return source_types[selected_index - 1]

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
    print("FTM banka hareketi oluşturma")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        bank_account_id = _select_bank_account()

        transaction_date = _ask_date("İşlem tarihi", date.today())
        value_date_input = input("Valör tarihi (YYYY-MM-DD, boş bırakılabilir): ").strip()
        value_date = date.fromisoformat(value_date_input) if value_date_input else None

        direction = _select_direction()
        status = _select_status()
        amount = _ask_money("Tutar", "0")
        source_type = _select_source_type()
        reference_no = _ask_optional_text("Referans no")
        description = _ask_optional_text("Açıklama")

        print("")
        _print_balance_summary(bank_account_id, "Banka hareketi öncesi bakiye:")

        with session_scope() as session:
            bank_account = session.get(BankAccount, bank_account_id)

            if bank_account is None:
                raise BankTransactionServiceError(f"Banka hesabı bulunamadı. Hesap ID: {bank_account_id}")

            bank_transaction = create_bank_transaction(
                session,
                bank_account_id=bank_account_id,
                transaction_date=transaction_date,
                value_date=value_date,
                direction=direction,
                status=status,
                amount=amount,
                currency_code=bank_account.currency_code,
                source_type=source_type,
                source_id=None,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("Banka hareketi başarıyla kaydedildi.")
            print(f"Hareket ID       : {bank_transaction.id}")
            print(f"Hesap ID         : {bank_transaction.bank_account_id}")
            print(f"Yön              : {bank_transaction.direction.value}")
            print(f"Durum            : {bank_transaction.status.value}")
            print(f"Tutar            : {bank_transaction.amount} {bank_transaction.currency_code.value}")
            print(f"Kaynak           : {bank_transaction.source_type.value}")
            print(f"İşlemi yapan     : {acting_user.username}")
            print("")

        _print_balance_summary(bank_account_id, "Banka hareketi sonrası bakiye:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except BankTransactionServiceError as exc:
        print("")
        print(f"Banka hareketi oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
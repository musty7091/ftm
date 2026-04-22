from datetime import date
from typing import Optional

from sqlalchemy import select

from app.db.session import session_scope
from app.models.enums import BankAccountType, CurrencyCode
from app.models.user import User
from app.services.bank_service import BankServiceError, create_bank_account, get_or_create_bank
from app.utils.decimal_utils import DecimalParseError, money


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


def _ask_money(label: str, default_value: str = "0") -> object:
    while True:
        value = input(f"{label} [{default_value}]: ").strip() or default_value

        try:
            return money(value, field_name=label)
        except DecimalParseError as exc:
            print(exc)


def _ask_optional_date(label: str) -> Optional[date]:
    value = input(f"{label} (YYYY-MM-DD, boş bırakılabilir): ").strip()

    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} YYYY-MM-DD formatında olmalıdır.") from exc


def _select_bank_account_type() -> BankAccountType:
    options = list(BankAccountType)

    print("")
    print("Hesap türü seç:")

    for index, option in enumerate(options, start=1):
        print(f"{index}. {option.value}")

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(options):
            return options[selected_index - 1]

        print("Geçersiz seçim.")


def _select_currency_code() -> CurrencyCode:
    options = list(CurrencyCode)

    print("")
    print("Para birimi seç:")

    for index, option in enumerate(options, start=1):
        print(f"{index}. {option.value}")

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(options):
            return options[selected_index - 1]

        print("Geçersiz seçim.")


def _get_admin_user_id() -> Optional[int]:
    with session_scope() as session:
        user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()

        if user is None:
            return None

        return user.id


def main() -> None:
    print("FTM banka ve banka hesabı oluşturma")
    print("")

    bank_name = _ask_required_text("Banka adı", "Garanti Bankası")
    bank_short_name = _ask_optional_text("Banka kısa adı", "Garanti")
    bank_notes = _ask_optional_text("Banka notu")

    account_name = _ask_required_text("Hesap adı", "TL Vadesiz Hesap")
    account_type = _select_bank_account_type()
    currency_code = _select_currency_code()

    iban = _ask_optional_text("IBAN")
    branch_name = _ask_optional_text("Şube adı")
    branch_code = _ask_optional_text("Şube kodu")
    account_no = _ask_optional_text("Hesap no")
    opening_balance = _ask_money("Açılış bakiyesi", "0")
    opening_date = _ask_optional_date("Açılış tarihi")
    account_notes = _ask_optional_text("Hesap notu")

    admin_user_id = _get_admin_user_id()

    try:
        with session_scope() as session:
            bank = get_or_create_bank(
                session,
                name=bank_name,
                short_name=bank_short_name,
                notes=bank_notes,
                created_by_user_id=admin_user_id,
            )

            bank_account = create_bank_account(
                session,
                bank_id=bank.id,
                account_name=account_name,
                account_type=account_type,
                currency_code=currency_code,
                iban=iban,
                branch_name=branch_name,
                branch_code=branch_code,
                account_no=account_no,
                opening_balance=opening_balance,
                opening_date=opening_date,
                notes=account_notes,
                created_by_user_id=admin_user_id,
            )

            session.flush()

            print("")
            print("Banka ve banka hesabı başarıyla kaydedildi.")
            print(f"Banka ID       : {bank.id}")
            print(f"Banka          : {bank.name}")
            print(f"Hesap ID       : {bank_account.id}")
            print(f"Hesap adı      : {bank_account.account_name}")
            print(f"Hesap türü     : {bank_account.account_type.value}")
            print(f"Para birimi    : {bank_account.currency_code.value}")
            print(f"Açılış bakiyesi: {bank_account.opening_balance}")

    except BankServiceError as exc:
        print("")
        print(f"Kayıt yapılamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
from datetime import date
from getpass import getpass
from typing import Optional

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.enums import BusinessPartnerType, CurrencyCode, ReceivedCheckStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.check_service import CheckServiceError, create_received_check
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


def _ask_required_text(label: str) -> str:
    while True:
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


def _ask_date(label: str, default_value: date) -> date:
    while True:
        value = input(f"{label} [{default_value.isoformat()}]: ").strip() or default_value.isoformat()

        try:
            return date.fromisoformat(value)
        except ValueError:
            print(f"{label} YYYY-MM-DD formatında olmalıdır.")


def _load_customers() -> list[BusinessPartner]:
    with session_scope() as session:
        statement = (
            select(BusinessPartner)
            .where(
                BusinessPartner.is_active.is_(True),
                BusinessPartner.partner_type.in_(
                    [
                        BusinessPartnerType.CUSTOMER,
                        BusinessPartnerType.BOTH,
                    ]
                ),
            )
            .order_by(BusinessPartner.name)
        )

        return list(session.execute(statement).scalars().all())


def _select_customer() -> int:
    customers = _load_customers()

    if not customers:
        raise SystemExit("Aktif müşteri cari kartı bulunamadı.")

    print("")
    print("Müşteri seç:")

    for index, customer in enumerate(customers, start=1):
        print(f"{index}. ID:{customer.id} | {customer.name} | {customer.partner_type.value}")

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(customers):
            return customers[selected_index - 1].id

        print("Geçersiz seçim.")


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


def _select_collection_bank_account() -> Optional[int]:
    rows = _load_bank_accounts()

    print("")
    print("Tahsil edilecek banka hesabı seç:")
    print("0. Şimdilik seçme / portföyde kalsın")

    if not rows:
        print("Aktif banka hesabı bulunamadı. Çek portföyde kalacak.")
        return None

    for index, row in enumerate(rows, start=1):
        bank_account, bank = row
        print(
            f"{index}. ID:{bank_account.id} | "
            f"{bank.name} / {bank_account.account_name} | "
            f"{bank_account.currency_code.value}"
        )

    while True:
        value = input("Seçim [0]: ").strip() or "0"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if selected_index == 0:
            return None

        if 1 <= selected_index <= len(rows):
            selected_bank_account, _selected_bank = rows[selected_index - 1]
            return selected_bank_account.id

        print("Geçersiz seçim.")


def _select_currency_code() -> CurrencyCode:
    currencies = [
        CurrencyCode.TRY,
        CurrencyCode.USD,
        CurrencyCode.EUR,
        CurrencyCode.GBP,
    ]

    print("")
    print("Para birimi seç:")

    for index, currency in enumerate(currencies, start=1):
        print(f"{index}. {currency.value}")

    while True:
        value = input("Seçim [1 - TRY]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(currencies):
            return currencies[selected_index - 1]

        print("Geçersiz seçim.")


def _select_received_check_status() -> ReceivedCheckStatus:
    statuses = [
        ReceivedCheckStatus.PORTFOLIO,
        ReceivedCheckStatus.GIVEN_TO_BANK,
        ReceivedCheckStatus.IN_COLLECTION,
    ]

    print("")
    print("Çek durumu seç:")

    for index, status in enumerate(statuses, start=1):
        print(f"{index}. {status.value}")

    while True:
        value = input("Seçim [1 - PORTFOLIO]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(statuses):
            return statuses[selected_index - 1]

        print("Geçersiz seçim.")


def main() -> None:
    print("FTM aldığımız müşteri çeki oluşturma")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        customer_id = _select_customer()
        collection_bank_account_id = _select_collection_bank_account()

        drawer_bank_name = _ask_required_text("Çeki veren banka")
        drawer_branch_name = _ask_optional_text("Çeki veren şube")
        check_number = _ask_required_text("Çek numarası")
        received_date = _ask_date("Alış tarihi", date.today())
        due_date = _ask_date("Vade tarihi", date.today())
        amount = _ask_money("Çek tutarı", "0")
        currency_code = _select_currency_code()
        status = _select_received_check_status()
        reference_no = _ask_optional_text("Referans no")
        description = _ask_optional_text("Açıklama")

        with session_scope() as session:
            check = create_received_check(
                session,
                customer_id=customer_id,
                collection_bank_account_id=collection_bank_account_id,
                drawer_bank_name=drawer_bank_name,
                drawer_branch_name=drawer_branch_name,
                check_number=check_number,
                received_date=received_date,
                due_date=due_date,
                amount=amount,
                currency_code=currency_code,
                status=status,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("")
            print("Alınan müşteri çeki başarıyla kaydedildi.")
            print(f"Çek ID       : {check.id}")
            print(f"Çek no       : {check.check_number}")
            print(f"Çeki veren   : {check.drawer_bank_name}")
            print(f"Tutar        : {check.amount} {check.currency_code.value}")
            print(f"Vade tarihi  : {check.due_date}")
            print(f"Durum        : {check.status.value}")
            print(f"Kaydı yapan  : {acting_user.username}")
            print("")
            print("Not: Bu işlem banka bakiyesini değiştirmedi. Çek tahsil edilince banka hareketi oluşacak.")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except CheckServiceError as exc:
        print("")
        print(f"Alınan çek oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
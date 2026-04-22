from datetime import date
from getpass import getpass

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.enums import BusinessPartnerType, IssuedCheckStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.check_service import CheckServiceError, create_issued_check
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


def _load_suppliers() -> list[BusinessPartner]:
    with session_scope() as session:
        statement = (
            select(BusinessPartner)
            .where(
                BusinessPartner.is_active.is_(True),
                BusinessPartner.partner_type.in_(
                    [
                        BusinessPartnerType.SUPPLIER,
                        BusinessPartnerType.BOTH,
                    ]
                ),
            )
            .order_by(BusinessPartner.name)
        )

        return list(session.execute(statement).scalars().all())


def _select_supplier() -> int:
    suppliers = _load_suppliers()

    if not suppliers:
        raise SystemExit("Aktif tedarikçi cari kartı bulunamadı.")

    print("")
    print("Tedarikçi seç:")

    for index, supplier in enumerate(suppliers, start=1):
        print(f"{index}. ID:{supplier.id} | {supplier.name} | {supplier.partner_type.value}")

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(suppliers):
            return suppliers[selected_index - 1].id

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


def _select_bank_account() -> int:
    rows = _load_bank_accounts()

    if not rows:
        raise SystemExit("Aktif banka hesabı bulunamadı.")

    print("")
    print("Çekin yazılacağı banka hesabı seç:")

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


def _select_issued_check_status() -> IssuedCheckStatus:
    print("")
    print("Çek durumu seç:")
    print("1. PREPARED")
    print("2. GIVEN")

    while True:
        value = input("Seçim [2 - GIVEN]: ").strip() or "2"

        if value == "1":
            return IssuedCheckStatus.PREPARED

        if value == "2":
            return IssuedCheckStatus.GIVEN

        print("Geçersiz seçim.")


def main() -> None:
    print("FTM yazdığımız çek oluşturma")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        supplier_id = _select_supplier()
        bank_account_id = _select_bank_account()

        check_number = _ask_required_text("Çek numarası")
        issue_date = _ask_date("Düzenleme tarihi", date.today())
        due_date = _ask_date("Vade tarihi", date.today())
        amount = _ask_money("Çek tutarı", "0")
        status = _select_issued_check_status()
        reference_no = _ask_optional_text("Referans no")
        description = _ask_optional_text("Açıklama")

        with session_scope() as session:
            check = create_issued_check(
                session,
                supplier_id=supplier_id,
                bank_account_id=bank_account_id,
                check_number=check_number,
                issue_date=issue_date,
                due_date=due_date,
                amount=amount,
                status=status,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("")
            print("Yazdığımız çek başarıyla kaydedildi.")
            print(f"Çek ID       : {check.id}")
            print(f"Çek no       : {check.check_number}")
            print(f"Tutar        : {check.amount} {check.currency_code.value}")
            print(f"Vade tarihi  : {check.due_date}")
            print(f"Durum        : {check.status.value}")
            print(f"Kaydı yapan  : {acting_user.username}")
            print("")
            print("Not: Bu işlem banka bakiyesini değiştirmedi. Çek ödenince banka hareketi oluşacak.")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except CheckServiceError as exc:
        print("")
        print(f"Yazılan çek oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
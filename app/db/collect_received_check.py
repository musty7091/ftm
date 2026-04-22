from datetime import date
from getpass import getpass
from typing import Optional

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.check import ReceivedCheck
from app.models.enums import ReceivedCheckStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.check_service import CheckServiceError, collect_received_check


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


def _show_collectable_received_checks() -> None:
    with session_scope() as session:
        statement = (
            select(ReceivedCheck)
            .where(
                ReceivedCheck.status.notin_(
                    [
                        ReceivedCheckStatus.COLLECTED,
                        ReceivedCheckStatus.CANCELLED,
                        ReceivedCheckStatus.BOUNCED,
                        ReceivedCheckStatus.RETURNED,
                        ReceivedCheckStatus.ENDORSED,
                    ]
                )
            )
            .order_by(ReceivedCheck.due_date, ReceivedCheck.id)
        )

        checks = session.execute(statement).scalars().all()

        if not checks:
            print("Tahsil edilebilir alınan çek bulunamadı.")
            return

        print("")
        print("Tahsil edilebilir alınan çekler:")
        print("")

        for check in checks:
            collection_account_text = "-"

            if check.collection_bank_account_id:
                bank_account = session.get(BankAccount, check.collection_bank_account_id)

                if bank_account:
                    bank = session.get(Bank, bank_account.bank_id)
                    collection_account_text = (
                        f"{bank.name} / {bank_account.account_name}"
                        if bank
                        else bank_account.account_name
                    )

            print(
                f"ID:{check.id} | "
                f"No:{check.check_number} | "
                f"Çeki Veren Banka:{check.drawer_bank_name} | "
                f"Tahsil Hesabı:{collection_account_text} | "
                f"Vade:{check.due_date} | "
                f"Tutar:{check.amount} {check.currency_code.value} | "
                f"Durum:{check.status.value}"
            )


def _get_received_check_info(received_check_id: int) -> tuple[Optional[int], str]:
    with session_scope() as session:
        check = session.get(ReceivedCheck, received_check_id)

        if check is None:
            raise CheckServiceError(f"Alınan çek bulunamadı. Çek ID: {received_check_id}")

        return check.collection_bank_account_id, check.currency_code.value


def _load_bank_accounts_by_currency(currency_code: str) -> list[tuple[BankAccount, Bank]]:
    with session_scope() as session:
        statement = (
            select(BankAccount, Bank)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(
                BankAccount.is_active.is_(True),
                BankAccount.currency_code == currency_code,
            )
            .order_by(Bank.name, BankAccount.account_name)
        )

        rows = session.execute(statement).all()

        return [(bank_account, bank) for bank_account, bank in rows]


def _select_collection_bank_account(
    *,
    existing_bank_account_id: Optional[int],
    currency_code: str,
) -> Optional[int]:
    rows = _load_bank_accounts_by_currency(currency_code)

    print("")
    print("Tahsilat banka hesabı seç:")

    if existing_bank_account_id is not None:
        print(f"0. Mevcut seçili tahsilat hesabını kullan | Hesap ID:{existing_bank_account_id}")
    else:
        print("0. Mevcut tahsilat hesabı yok")

    if not rows:
        raise CheckServiceError(f"{currency_code} para biriminde aktif banka hesabı bulunamadı.")

    for index, row in enumerate(rows, start=1):
        bank_account, bank = row
        print(
            f"{index}. ID:{bank_account.id} | "
            f"{bank.name} / {bank_account.account_name} | "
            f"{bank_account.currency_code.value}"
        )

    while True:
        default_value = "0" if existing_bank_account_id is not None else "1"
        value = input(f"Seçim [{default_value}]: ").strip() or default_value

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if selected_index == 0 and existing_bank_account_id is not None:
            return None

        if selected_index == 0 and existing_bank_account_id is None:
            print("Mevcut tahsilat hesabı yok. Lütfen banka hesabı seç.")
            continue

        if 1 <= selected_index <= len(rows):
            selected_bank_account, _selected_bank = rows[selected_index - 1]
            return selected_bank_account.id

        print("Geçersiz seçim.")


def _resolve_balance_account_id(
    *,
    selected_bank_account_id: Optional[int],
    existing_bank_account_id: Optional[int],
) -> int:
    final_bank_account_id = selected_bank_account_id or existing_bank_account_id

    if final_bank_account_id is None:
        raise CheckServiceError("Tahsilat banka hesabı seçilmelidir.")

    return final_bank_account_id


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
    print("FTM alınan çek tahsilatı")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        _show_collectable_received_checks()

        received_check_id = _ask_required_int("Tahsil edilecek çek ID")
        collection_date = _ask_date("Tahsilat tarihi", date.today())

        existing_bank_account_id, currency_code = _get_received_check_info(received_check_id)

        selected_bank_account_id = _select_collection_bank_account(
            existing_bank_account_id=existing_bank_account_id,
            currency_code=currency_code,
        )

        final_bank_account_id = _resolve_balance_account_id(
            selected_bank_account_id=selected_bank_account_id,
            existing_bank_account_id=existing_bank_account_id,
        )

        reference_no = _ask_optional_text("Banka referans no")
        description = _ask_optional_text("Açıklama")

        print("")
        _print_balance_summary(final_bank_account_id, "Çek tahsilatı öncesi banka bakiyesi:")

        with session_scope() as session:
            check = collect_received_check(
                session,
                received_check_id=received_check_id,
                collection_bank_account_id=selected_bank_account_id,
                collection_date=collection_date,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("Alınan çek başarıyla tahsil edildi.")
            print(f"Çek ID            : {check.id}")
            print(f"Çek no            : {check.check_number}")
            print(f"Yeni durum        : {check.status.value}")
            print(f"Banka hareket ID  : {check.collected_transaction_id}")
            print(f"Tutar             : {check.amount} {check.currency_code.value}")
            print(f"İşlemi yapan      : {acting_user.username}")
            print("")

        _print_balance_summary(final_bank_account_id, "Çek tahsilatı sonrası banka bakiyesi:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except CheckServiceError as exc:
        print("")
        print(f"Alınan çek tahsil edilemedi: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
from typing import Optional

from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.user import User
from app.services.pos_service import PosServiceError, create_pos_device


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


def _ask_commission_rate(label: str, default_value: str = "0") -> str:
    while True:
        value = input(f"{label} [{default_value}]: ").strip() or default_value

        normalized_value = value.replace(",", ".")

        try:
            numeric_value = float(normalized_value)
        except ValueError:
            print(f"{label} sayısal olmalıdır.")
            continue

        if numeric_value < 0:
            print(f"{label} negatif olamaz.")
            continue

        if numeric_value > 100:
            print(f"{label} 100'den büyük olamaz.")
            continue

        return value


def _ask_int(label: str, default_value: str = "1") -> int:
    while True:
        value = input(f"{label} [{default_value}]: ").strip() or default_value

        if not value.isdigit():
            print(f"{label} sayı olmalıdır.")
            continue

        int_value = int(value)

        if int_value < 0:
            print(f"{label} negatif olamaz.")
            continue

        return int_value


def _get_admin_user_id() -> Optional[int]:
    with session_scope() as session:
        user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()

        if user is None:
            return None

        return user.id


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
    print("POS yatışının bağlanacağı banka hesabı seç:")

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


def main() -> None:
    print("FTM POS cihazı oluşturma")
    print("")

    bank_account_id = _select_bank_account()

    name = _ask_required_text("POS adı", "Garanti POS")
    terminal_no = _ask_optional_text("Terminal no")
    commission_rate = _ask_commission_rate("Komisyon oranı (%)", "1,99")
    settlement_delay_days = _ask_int("Kaç gün sonra hesaba geçer", "1")
    notes = _ask_optional_text("Not")

    admin_user_id = _get_admin_user_id()

    try:
        with session_scope() as session:
            pos_device = create_pos_device(
                session,
                bank_account_id=bank_account_id,
                name=name,
                terminal_no=terminal_no,
                commission_rate=commission_rate,
                settlement_delay_days=settlement_delay_days,
                notes=notes,
                created_by_user_id=admin_user_id,
            )

            session.flush()

            print("")
            print("POS cihazı başarıyla oluşturuldu.")
            print(f"POS ID              : {pos_device.id}")
            print(f"POS adı             : {pos_device.name}")
            print(f"Terminal no         : {pos_device.terminal_no or '-'}")
            print(f"Komisyon oranı      : {pos_device.commission_rate}%")
            print(f"Hesaba geçiş günü   : {pos_device.settlement_delay_days}")
            print(f"Para birimi         : {pos_device.currency_code.value}")

    except PosServiceError as exc:
        print("")
        print(f"POS cihazı oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
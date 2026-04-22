from datetime import date

from getpass import getpass
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.pos import PosDevice
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.pos_service import PosServiceError, create_pos_settlement
from app.utils.decimal_utils import DecimalParseError, money


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


def _load_pos_devices() -> list[tuple[PosDevice, BankAccount, Bank]]:
    with session_scope() as session:
        statement = (
            select(PosDevice, BankAccount, Bank)
            .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(PosDevice.is_active.is_(True))
            .order_by(Bank.name, PosDevice.name)
        )

        rows = session.execute(statement).all()

        return [(pos_device, bank_account, bank) for pos_device, bank_account, bank in rows]


def _select_pos_device() -> int:
    rows = _load_pos_devices()

    if not rows:
        raise SystemExit("Aktif POS cihazı bulunamadı. Önce POS cihazı oluşturmalısın.")

    print("")
    print("POS cihazı seç:")

    for index, row in enumerate(rows, start=1):
        pos_device, bank_account, bank = row
        print(
            f"{index}. ID:{pos_device.id} | "
            f"{pos_device.name} | "
            f"{bank.name} / {bank_account.account_name} | "
            f"Komisyon: %{pos_device.commission_rate} | "
            f"Yatış günü: {pos_device.settlement_delay_days}"
        )

    while True:
        value = input("Seçim [1]: ").strip() or "1"

        if not value.isdigit():
            print("Lütfen sayı gir.")
            continue

        selected_index = int(value)

        if 1 <= selected_index <= len(rows):
            selected_pos_device, _bank_account, _bank = rows[selected_index - 1]
            return selected_pos_device.id

        print("Geçersiz seçim.")


def main() -> None:
    print("FTM POS satış / beklenen yatış kaydı oluşturma")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        pos_device_id = _select_pos_device()
        transaction_date = _ask_date("POS işlem tarihi", date.today())
        gross_amount = _ask_money("Brüt POS tutarı", "0")
        reference_no = _ask_optional_text("Referans no")
        description = _ask_optional_text("Açıklama")

        with session_scope() as session:
            pos_settlement = create_pos_settlement(
                session,
                pos_device_id=pos_device_id,
                transaction_date=transaction_date,
                gross_amount=gross_amount,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("")
            print("POS yatış kaydı başarıyla oluşturuldu.")
            print(f"POS yatış ID          : {pos_settlement.id}")
            print(f"POS cihaz ID          : {pos_settlement.pos_device_id}")
            print(f"İşlem tarihi          : {pos_settlement.transaction_date}")
            print(f"Beklenen yatış tarihi : {pos_settlement.expected_settlement_date}")
            print(f"Brüt tutar            : {pos_settlement.gross_amount} {pos_settlement.currency_code.value}")
            print(f"Komisyon oranı        : %{pos_settlement.commission_rate}")
            print(f"Komisyon tutarı       : {pos_settlement.commission_amount} {pos_settlement.currency_code.value}")
            print(f"Net yatacak tutar     : {pos_settlement.net_amount} {pos_settlement.currency_code.value}")
            print(f"Durum                 : {pos_settlement.status.value}")
            print(f"Kaydı oluşturan       : {acting_user.username}")
            print("")
            print("Not: Bu işlem banka bakiyesini değiştirmedi. POS yatışı gerçekleşince banka hareketi oluşacak.")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except PosServiceError as exc:
        print("")
        print(f"POS yatış kaydı oluşturulamadı: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
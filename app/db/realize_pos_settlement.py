from datetime import date

from getpass import getpass
from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.pos import PosDevice, PosSettlement
from app.models.enums import PosSettlementStatus
from app.services.auth_service import AuthServiceError, authenticate_user
from app.services.bank_transaction_service import get_bank_account_balance_summary
from app.services.pos_service import PosServiceError, realize_pos_settlement
from app.utils.decimal_utils import DecimalParseError, money


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


def _ask_money(label: str, default_value: str) -> object:
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


def _show_realizable_pos_settlements() -> None:
    with session_scope() as session:
        statement = (
            select(PosSettlement, PosDevice, BankAccount, Bank)
            .join(PosDevice, PosSettlement.pos_device_id == PosDevice.id)
            .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .where(
                PosSettlement.status.notin_(
                    [
                        PosSettlementStatus.REALIZED,
                        PosSettlementStatus.MISMATCH,
                        PosSettlementStatus.CANCELLED,
                    ]
                )
            )
            .order_by(PosSettlement.expected_settlement_date, PosSettlement.id)
        )

        rows = session.execute(statement).all()

        if not rows:
            print("Gerçekleştirilebilir POS yatış kaydı bulunamadı.")
            return

        print("")
        print("Gerçekleştirilebilir POS yatış kayıtları:")
        print("")

        for pos_settlement, pos_device, bank_account, bank in rows:
            print(
                f"ID:{pos_settlement.id} | "
                f"POS:{pos_device.name} | "
                f"Banka:{bank.name} / {bank_account.account_name} | "
                f"İşlem:{pos_settlement.transaction_date} | "
                f"Beklenen:{pos_settlement.expected_settlement_date} | "
                f"Brüt:{pos_settlement.gross_amount} {pos_settlement.currency_code.value} | "
                f"Komisyon:{pos_settlement.commission_amount} | "
                f"Beklenen Net:{pos_settlement.net_amount} | "
                f"Durum:{pos_settlement.status.value}"
            )


def _get_pos_settlement_info(pos_settlement_id: int) -> tuple[int, str]:
    with session_scope() as session:
        statement = (
            select(BankAccount.id, PosSettlement.net_amount)
            .join(PosDevice, BankAccount.id == PosDevice.bank_account_id)
            .join(PosSettlement, PosDevice.id == PosSettlement.pos_device_id)
            .where(PosSettlement.id == pos_settlement_id)
        )

        row = session.execute(statement).one_or_none()

        if row is None:
            raise PosServiceError(f"POS yatış kaydına bağlı banka hesabı bulunamadı. POS yatış ID: {pos_settlement_id}")

        bank_account_id, expected_net_amount = row

        return bank_account_id, str(expected_net_amount)


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
    print("FTM POS yatışı gerçekleşti")
    print("")

    try:
        acting_user = _login_user()

        print("")
        print(f"Giriş başarılı: {acting_user.username} / {acting_user.role.value}")

        _show_realizable_pos_settlements()

        pos_settlement_id = _ask_required_int("Gerçekleşen POS yatış ID")
        realized_date = _ask_date("Gerçekleşen yatış tarihi", date.today())

        bank_account_id, expected_net_amount = _get_pos_settlement_info(pos_settlement_id)

        actual_net_amount = _ask_money("Bankaya gerçekten yatan tutar", expected_net_amount)
        difference_reason = _ask_optional_text("Fark nedeni varsa yaz")
        reference_no = _ask_optional_text("Banka referans no")
        description = _ask_optional_text("Açıklama")

        print("")
        _print_balance_summary(bank_account_id, "POS yatışı öncesi banka bakiyesi:")

        with session_scope() as session:
            realized_settlement = realize_pos_settlement(
                session,
                pos_settlement_id=pos_settlement_id,
                realized_settlement_date=realized_date,
                actual_net_amount=actual_net_amount,
                difference_reason=difference_reason,
                reference_no=reference_no,
                description=description,
                acting_user=acting_user,
            )

            session.flush()

            print("POS yatışı başarıyla işlendi.")
            print(f"POS yatış ID            : {realized_settlement.id}")
            print(f"Yeni durum              : {realized_settlement.status.value}")
            print(f"Gerçekleşen tarih       : {realized_settlement.realized_settlement_date}")
            print(f"Banka hareket ID        : {realized_settlement.bank_transaction_id}")
            print(f"Beklenen net tutar      : {realized_settlement.net_amount} {realized_settlement.currency_code.value}")
            print(f"Gerçek yatan tutar      : {realized_settlement.actual_net_amount} {realized_settlement.currency_code.value}")
            print(f"Fark                    : {realized_settlement.difference_amount} {realized_settlement.currency_code.value}")
            print(f"Fark nedeni             : {realized_settlement.difference_reason or '-'}")
            print(f"İşlemi yapan kullanıcı  : {acting_user.username}")
            print("")

        _print_balance_summary(bank_account_id, "POS yatışı sonrası banka bakiyesi:")

    except AuthServiceError as exc:
        print("")
        print(f"Giriş başarısız: {exc}")
        raise SystemExit(1) from exc

    except PosServiceError as exc:
        print("")
        print(f"POS yatışı gerçekleştirilemedi: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
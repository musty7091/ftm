from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.services.bank_transaction_service import get_bank_account_balance_summary


def main() -> None:
    with session_scope() as session:
        statement = (
            select(BankAccount, Bank)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .order_by(Bank.name, BankAccount.account_name)
        )

        rows = session.execute(statement).all()

        if not rows:
            print("Kayıtlı banka hesabı bulunamadı.")
            return

        print("FTM banka bakiye özeti")
        print("")

        for row in rows:
            bank_account, bank = row

            summary = get_bank_account_balance_summary(
                session,
                bank_account_id=bank_account.id,
            )

            print(f"Banka           : {bank.name}")
            print(f"Hesap           : {bank_account.account_name}")
            print(f"Para birimi     : {summary['currency_code']}")
            print(f"Açılış bakiyesi : {summary['opening_balance']}")
            print(f"Toplam giriş    : {summary['incoming_total']}")
            print(f"Toplam çıkış    : {summary['outgoing_total']}")
            print(f"Güncel bakiye   : {summary['current_balance']}")
            print("-" * 50)


if __name__ == "__main__":
    main()
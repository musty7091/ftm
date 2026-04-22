from sqlalchemy import select

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.pos import PosDevice, PosSettlement


def main() -> None:
    print("FTM POS yatış listesi")
    print("")

    with session_scope() as session:
        statement = (
            select(PosSettlement, PosDevice, BankAccount, Bank)
            .join(PosDevice, PosSettlement.pos_device_id == PosDevice.id)
            .join(BankAccount, PosDevice.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .order_by(PosSettlement.expected_settlement_date, PosSettlement.id)
        )

        rows = session.execute(statement).all()

        if not rows:
            print("Kayıtlı POS yatış kaydı bulunamadı.")
            return

        for pos_settlement, pos_device, bank_account, bank in rows:
            print(
                f"ID:{pos_settlement.id} | "
                f"POS:{pos_device.name} | "
                f"Banka:{bank.name} / {bank_account.account_name} | "
                f"İşlem:{pos_settlement.transaction_date} | "
                f"Beklenen:{pos_settlement.expected_settlement_date} | "
                f"Gerçekleşen:{pos_settlement.realized_settlement_date or '-'} | "
                f"Brüt:{pos_settlement.gross_amount} {pos_settlement.currency_code.value} | "
                f"Komisyon:{pos_settlement.commission_amount} | "
                f"Beklenen Net:{pos_settlement.net_amount} | "
                f"Gerçek Net:{pos_settlement.actual_net_amount or '-'} | "
                f"Fark:{pos_settlement.difference_amount} | "
                f"Durum:{pos_settlement.status.value} | "
                f"Banka Hareket ID:{pos_settlement.bank_transaction_id or '-'} | "
                f"Fark Nedeni:{pos_settlement.difference_reason or '-'}"
            )


if __name__ == "__main__":
    main()
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.business_partner import BusinessPartner
from app.models.check import IssuedCheck, ReceivedCheck


def _list_issued_checks() -> None:
    with session_scope() as session:
        statement = (
            select(IssuedCheck, BusinessPartner, BankAccount, Bank)
            .join(BusinessPartner, IssuedCheck.supplier_id == BusinessPartner.id)
            .join(BankAccount, IssuedCheck.bank_account_id == BankAccount.id)
            .join(Bank, BankAccount.bank_id == Bank.id)
            .order_by(IssuedCheck.due_date, IssuedCheck.id)
        )

        rows = session.execute(statement).all()

        print("YAZDIĞIMIZ ÇEKLER")
        print("-" * 80)

        if not rows:
            print("Kayıt yok.")
            print("")
            return

        for check, supplier, bank_account, bank in rows:
            print(
                f"ID:{check.id} | "
                f"No:{check.check_number} | "
                f"Tedarikçi:{supplier.name} | "
                f"Banka:{bank.name} / {bank_account.account_name} | "
                f"Vade:{check.due_date} | "
                f"Tutar:{check.amount} {check.currency_code.value} | "
                f"Durum:{check.status.value}"
            )

        print("")


def _list_received_checks() -> None:
    with session_scope() as session:
        collection_account_alias = aliased(BankAccount)
        collection_bank_alias = aliased(Bank)

        statement = (
            select(
                ReceivedCheck,
                BusinessPartner,
                collection_account_alias,
                collection_bank_alias,
            )
            .join(BusinessPartner, ReceivedCheck.customer_id == BusinessPartner.id)
            .outerjoin(
                collection_account_alias,
                ReceivedCheck.collection_bank_account_id == collection_account_alias.id,
            )
            .outerjoin(
                collection_bank_alias,
                collection_account_alias.bank_id == collection_bank_alias.id,
            )
            .order_by(ReceivedCheck.due_date, ReceivedCheck.id)
        )

        rows = session.execute(statement).all()

        print("ALDIĞIMIZ MÜŞTERİ ÇEKLERİ")
        print("-" * 80)

        if not rows:
            print("Kayıt yok.")
            print("")
            return

        for check, customer, collection_account, collection_bank in rows:
            if collection_account and collection_bank:
                collection_text = f"{collection_bank.name} / {collection_account.account_name}"
            else:
                collection_text = "Portföyde / banka seçilmedi"

            print(
                f"ID:{check.id} | "
                f"No:{check.check_number} | "
                f"Müşteri:{customer.name} | "
                f"Çeki Veren Banka:{check.drawer_bank_name} | "
                f"Tahsil Hesabı:{collection_text} | "
                f"Vade:{check.due_date} | "
                f"Tutar:{check.amount} {check.currency_code.value} | "
                f"Durum:{check.status.value}"
            )

        print("")


def main() -> None:
    print("FTM çek listesi")
    print("")

    _list_issued_checks()
    _list_received_checks()


if __name__ == "__main__":
    main()
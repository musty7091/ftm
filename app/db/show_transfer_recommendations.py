from datetime import date
from decimal import Decimal

from app.db.session import session_scope
from app.services.transfer_recommendation_service import get_all_transfer_recommendations


def _format_money(value: object) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _print_recommendations(report: dict) -> None:
    recommendations = report["recommendations"]
    unresolved_risks = report["unresolved_risks"]
    unused_surpluses = report["unused_surpluses"]

    if recommendations:
        print("TRANSFER ÖNERİLERİ")
        print("-" * 80)

        for index, recommendation in enumerate(recommendations, start=1):
            print(f"{index}. Öneri")
            print(f"   Çıkış hesabı : {recommendation['from_account_label']}")
            print(f"   Giriş hesabı : {recommendation['to_account_label']}")
            print(
                f"   Tutar        : "
                f"{_format_money(recommendation['amount'])} {recommendation['currency_code']}"
            )
            print(f"   Sebep        : {recommendation['reason']}")
            print("")

    else:
        print("Transfer önerisi yok.")
        print("")

    if unresolved_risks:
        print("KAPANMAYAN RİSKLER")
        print("-" * 80)

        for risk in unresolved_risks:
            print(f"Hesap        : {risk['account_label']}")
            print(f"Kalan açık   : {_format_money(risk['remaining_need'])} {risk['currency_code']}")
            print("Aksiyon      : Dış kaynak, nakit yatırma veya ek tahsilat gerekiyor.")
            print("")

    else:
        print("Kapanmayan risk yok.")
        print("")

    if unused_surpluses:
        print("TRANSFERDEN SONRA KALAN FAZLALAR")
        print("-" * 80)

        for surplus in unused_surpluses:
            available_amount = surplus["available_amount"]

            if available_amount <= Decimal("0.00"):
                continue

            print(f"Hesap        : {surplus['account_label']}")
            print(f"Kalan fazla  : {_format_money(available_amount)} {surplus['currency_code']}")
            print("")

    else:
        print("Transferden sonra kullanılabilir fazla görünmüyor.")
        print("")


def main() -> None:
    as_of_date = date.today()

    with session_scope() as session:
        all_reports = get_all_transfer_recommendations(
            session,
            as_of_date=as_of_date,
        )

    print("FTM transfer öneri raporu")
    print(f"Rapor tarihi: {as_of_date}")
    print("=" * 80)
    print("")
    print("Not: Bu rapor sadece öneri üretir. Gerçek banka transferi oluşturmaz.")
    print("=" * 80)
    print("")

    for horizon_days, report in all_reports.items():
        print(f"{horizon_days} GÜNLÜK TRANSFER ÖNERİSİ")
        print("=" * 80)
        _print_recommendations(report)
        print("")


if __name__ == "__main__":
    main()
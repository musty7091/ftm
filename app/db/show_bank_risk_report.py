from datetime import date

from app.db.session import session_scope
from app.services.risk_service import get_all_bank_risk_summaries


def _format_money(value: object) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _print_row(summary: dict) -> None:
    print(f"Banka / Hesap       : {summary['bank_name']} / {summary['account_name']}")
    print(f"Para birimi         : {summary['currency_code']}")
    print(f"Güncel bakiye       : {_format_money(summary['current_balance'])}")
    print(f"Yazdığımız çekler   : {_format_money(summary['pending_issued_checks_total'])}")
    print(f"Beklenen müşteri çeki: {_format_money(summary['expected_received_checks_total'])}")
    print(f"Tahmini bakiye      : {_format_money(summary['projected_balance'])}")
    print(f"Durum               : {summary['risk_status']}")
    print("-" * 70)


def main() -> None:
    as_of_date = date.today()

    with session_scope() as session:
        all_summaries = get_all_bank_risk_summaries(
            session,
            as_of_date=as_of_date,
        )

    print("FTM banka bazlı çek risk raporu")
    print(f"Rapor tarihi: {as_of_date}")
    print("=" * 70)
    print("")

    for horizon_days, summaries in all_summaries.items():
        print(f"{horizon_days} GÜNLÜK RİSK")
        print("=" * 70)

        if not summaries:
            print("Aktif banka hesabı bulunamadı.")
            print("")
            continue

        for summary in summaries:
            _print_row(summary)

        print("")


if __name__ == "__main__":
    main()
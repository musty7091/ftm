from datetime import date

from app.db.session import session_scope
from app.services.pos_report_service import get_pos_reconciliation_report


def _format_money(value: object) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ask_date(label: str, default_value: date) -> date:
    while True:
        value = input(f"{label} [{default_value.isoformat()}]: ").strip() or default_value.isoformat()

        try:
            return date.fromisoformat(value)
        except ValueError:
            print(f"{label} YYYY-MM-DD formatında olmalıdır.")


def _first_day_of_month(today: date) -> date:
    return date(today.year, today.month, 1)


def _print_currency_totals(title: str, totals: dict[str, object]) -> None:
    print(title)
    print("-" * 80)

    if not totals:
        print("Kayıt yok.")
        print("")
        return

    for currency_code, amount in totals.items():
        print(f"{currency_code}: {_format_money(amount)}")

    print("")


def _print_overall_summary(report: dict) -> None:
    overall_totals = report["overall_totals"]

    print("GENEL POS ÖZETİ")
    print("=" * 80)

    _print_currency_totals("Brüt POS toplamı", overall_totals["gross_total"])
    _print_currency_totals("Komisyon toplamı", overall_totals["commission_total"])
    _print_currency_totals("Beklenen net toplam", overall_totals["expected_net_total"])
    _print_currency_totals("Gerçek yatan toplam", overall_totals["actual_net_total"])
    _print_currency_totals("Fark toplamı", overall_totals["difference_total"])


def _print_status_summary(report: dict) -> None:
    totals_by_status = report["totals_by_status"]

    print("DURUM BAZLI POS ÖZETİ")
    print("=" * 80)

    if not totals_by_status:
        print("Kayıt yok.")
        print("")
        return

    for status, totals in totals_by_status.items():
        print(f"Durum: {status}")
        print(f"Brüt toplam        : {_format_money(totals['gross_total'])}")
        print(f"Komisyon toplamı   : {_format_money(totals['commission_total'])}")
        print(f"Beklenen net toplam: {_format_money(totals['expected_net_total'])}")
        print(f"Gerçek yatan toplam: {_format_money(totals['actual_net_total'])}")
        print(f"Fark toplamı       : {_format_money(totals['difference_total'])}")
        print("-" * 80)

    print("")


def _print_bank_summary(report: dict) -> None:
    totals_by_bank = report["totals_by_bank"]

    print("BANKA BAZLI POS ÖZETİ")
    print("=" * 80)

    if not totals_by_bank:
        print("Kayıt yok.")
        print("")
        return

    for bank_label, totals in totals_by_bank.items():
        print(f"Banka / Hesap      : {bank_label}")
        print(f"Brüt toplam        : {_format_money(totals['gross_total'])}")
        print(f"Komisyon toplamı   : {_format_money(totals['commission_total'])}")
        print(f"Beklenen net toplam: {_format_money(totals['expected_net_total'])}")
        print(f"Gerçek yatan toplam: {_format_money(totals['actual_net_total'])}")
        print(f"Fark toplamı       : {_format_money(totals['difference_total'])}")
        print("-" * 80)

    print("")


def _print_mismatch_rows(report: dict) -> None:
    mismatch_rows = report["mismatch_rows"]

    print("FARKLI / MISMATCH POS YATIŞLARI")
    print("=" * 80)

    if not mismatch_rows:
        print("Farklı POS yatışı yok.")
        print("")
        return

    for row in mismatch_rows:
        print(
            f"ID:{row['id']} | "
            f"POS:{row['pos_label']} | "
            f"Banka:{row['bank_label']} | "
            f"İşlem:{row['transaction_date']} | "
            f"Beklenen:{row['expected_settlement_date']} | "
            f"Gerçekleşen:{row['realized_settlement_date']} | "
            f"Beklenen Net:{_format_money(row['expected_net_amount'])} {row['currency_code']} | "
            f"Gerçek Net:{_format_money(row['actual_net_amount'])} {row['currency_code']} | "
            f"Fark:{_format_money(row['difference_amount'])} {row['currency_code']} | "
            f"Neden:{row['difference_reason'] or '-'}"
        )

    print("")


def _print_detail_rows(report: dict) -> None:
    detail_rows = report["detail_rows"]

    print("TÜM POS YATIŞ DETAYLARI")
    print("=" * 80)

    if not detail_rows:
        print("Kayıt yok.")
        print("")
        return

    for row in detail_rows:
        print(
            f"ID:{row['id']} | "
            f"POS:{row['pos_label']} | "
            f"Banka:{row['bank_label']} | "
            f"İşlem:{row['transaction_date']} | "
            f"Beklenen:{row['expected_settlement_date']} | "
            f"Gerçekleşen:{row['realized_settlement_date'] or '-'} | "
            f"Brüt:{_format_money(row['gross_amount'])} {row['currency_code']} | "
            f"Komisyon:{_format_money(row['commission_amount'])} | "
            f"Beklenen Net:{_format_money(row['expected_net_amount'])} | "
            f"Gerçek Net:{_format_money(row['actual_net_amount'])} | "
            f"Fark:{_format_money(row['difference_amount'])} | "
            f"Durum:{row['status']}"
        )

    print("")


def main() -> None:
    today = date.today()

    print("FTM POS mutabakat raporu")
    print("")

    start_date = _ask_date("Başlangıç tarihi", _first_day_of_month(today))
    end_date = _ask_date("Bitiş tarihi", today)

    with session_scope() as session:
        report = get_pos_reconciliation_report(
            session,
            start_date=start_date,
            end_date=end_date,
        )

    print("")
    print(f"Rapor dönemi: {start_date} - {end_date}")
    print("=" * 80)
    print("")

    _print_overall_summary(report)
    _print_status_summary(report)
    _print_bank_summary(report)
    _print_mismatch_rows(report)
    _print_detail_rows(report)


if __name__ == "__main__":
    main()
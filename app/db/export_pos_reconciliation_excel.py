from datetime import date
from traceback import print_exc

from app.db.session import session_scope
from app.reports.pos_reconciliation_excel_exporter import export_pos_reconciliation_to_excel


def _first_day_of_month(today: date) -> date:
    return date(today.year, today.month, 1)


def _ask_date(label: str, default_value: date) -> date:
    while True:
        value = input(f"{label} [{default_value.isoformat()}]: ").strip() or default_value.isoformat()

        try:
            return date.fromisoformat(value)
        except ValueError:
            print(f"{label} YYYY-MM-DD formatında olmalıdır.")


def main() -> None:
    today = date.today()

    print("FTM POS Mutabakat Excel raporu oluşturma")
    print("")

    start_date = _ask_date("Başlangıç tarihi", _first_day_of_month(today))
    end_date = _ask_date("Bitiş tarihi", today)

    if end_date < start_date:
        print("")
        print("Rapor oluşturulamadı: Bitiş tarihi başlangıç tarihinden önce olamaz.")
        raise SystemExit(1)

    try:
        with session_scope() as session:
            output_path = export_pos_reconciliation_to_excel(
                session,
                start_date=start_date,
                end_date=end_date,
            )

        print("")
        print("POS Mutabakat Excel raporu başarıyla oluşturuldu.")
        print(f"Dosya yolu: {output_path}")

    except Exception:
        print("")
        print("POS Mutabakat Excel raporu oluşturulurken hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
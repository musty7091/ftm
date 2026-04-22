from traceback import print_exc

from app.db.session import session_scope
from app.reports.excel_exporter import export_financial_reports_to_excel


def main() -> None:
    print("FTM Excel raporu oluşturma işlemi başladı...")

    try:
        with session_scope() as session:
            output_path = export_financial_reports_to_excel(session)

        print("")
        print("FTM Excel raporu başarıyla oluşturuldu.")
        print(f"Dosya yolu: {output_path}")

    except Exception:
        print("")
        print("Excel raporu oluşturulurken hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
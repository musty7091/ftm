from traceback import print_exc

from app.db.session import session_scope
from app.services.security_summary_service import (
    build_security_summary_text,
    get_security_summary,
)


def _ask_period_hours() -> int:
    value = input("Kaç saatlik güvenlik özeti? [24]: ").strip() or "24"

    if not value.isdigit():
        print("Geçersiz değer. Varsayılan 24 saat kullanılacak.")
        return 24

    period_hours = int(value)

    if period_hours <= 0:
        return 24

    return period_hours


def main() -> None:
    print("FTM güvenlik özet raporu")
    print("")

    try:
        period_hours = _ask_period_hours()

        with session_scope() as session:
            summary = get_security_summary(
                session,
                period_hours=period_hours,
                permission_denied_limit=10,
            )

        report_text = build_security_summary_text(summary)

        print("")
        print(report_text)

    except Exception:
        print("")
        print("Güvenlik özet raporu oluşturulurken hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
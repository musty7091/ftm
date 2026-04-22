from traceback import print_exc

from app.db.session import session_scope
from app.services.system_health_service import (
    build_system_health_report_text,
    run_system_health_check,
)


def main() -> None:
    print("FTM sistem sağlık kontrolü")
    print("")

    try:
        with session_scope() as session:
            report = run_system_health_check(session)

        report_text = build_system_health_report_text(report)

        print(report_text)

        if report.failed_count > 0:
            raise SystemExit(1)

    except SystemExit:
        raise

    except Exception:
        print("")
        print("Sistem sağlık kontrolü sırasında hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
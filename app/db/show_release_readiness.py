from __future__ import annotations

from app.services.release_readiness_service import (
    build_release_readiness_report_text,
    run_release_readiness_check,
)


def main() -> None:
    print("FTM mevcut ortam sağlık kontrolü başlatıldı...")
    print()

    try:
        report = run_release_readiness_check()
        report_text = build_release_readiness_report_text(report)

        print(report_text)

        print()

        if report.is_environment_usable:
            print("SONUÇ: Mevcut FTM ortamı kullanılabilir görünüyor.")
        else:
            print("SONUÇ: Mevcut FTM ortamı kullanılmamalı. FAIL kontroller düzeltilmeli.")

    except Exception as exc:
        print("Mevcut ortam sağlık kontrolü sırasında hata oluştu.")
        print()
        print(type(exc).__name__)
        print(exc)
        raise


if __name__ == "__main__":
    main()
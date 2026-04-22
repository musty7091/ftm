import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


MENU_ITEMS = [
    {
        "key": "1",
        "title": "Kullanıcı listesini göster",
        "module": "app.db.list_users",
        "category": "KULLANICI YÖNETİMİ",
    },
    {
        "key": "2",
        "title": "Yeni kullanıcı oluştur",
        "module": "app.db.create_user",
        "category": "KULLANICI YÖNETİMİ",
    },
    {
        "key": "3",
        "title": "Kullanıcı rol değiştir",
        "module": "app.db.change_user_role",
        "category": "KULLANICI YÖNETİMİ",
    },
    {
        "key": "4",
        "title": "Kullanıcı pasifleştir",
        "module": "app.db.deactivate_user",
        "category": "KULLANICI YÖNETİMİ",
    },
    {
        "key": "5",
        "title": "Pasif kullanıcıyı yeniden aktif et",
        "module": "app.db.reactivate_user",
        "category": "KULLANICI YÖNETİMİ",
    },
    {
        "key": "6",
        "title": "Banka bakiye özetini göster",
        "module": "app.db.show_bank_balances",
        "category": "BANKA İŞLEMLERİ",
    },
    {
        "key": "7",
        "title": "Banka hareketi oluştur",
        "module": "app.db.create_bank_transaction",
        "category": "BANKA İŞLEMLERİ",
    },
    {
        "key": "8",
        "title": "Banka hareketi iptal et",
        "module": "app.db.cancel_bank_transaction",
        "category": "BANKA İŞLEMLERİ",
    },
    {
        "key": "9",
        "title": "Banka transferi oluştur",
        "module": "app.db.create_bank_transfer",
        "category": "BANKA TRANSFERLERİ",
    },
    {
        "key": "10",
        "title": "Banka transferi iptal et",
        "module": "app.db.cancel_bank_transfer",
        "category": "BANKA TRANSFERLERİ",
    },
    {
        "key": "11",
        "title": "POS beklenen yatış kaydı oluştur",
        "module": "app.db.create_pos_settlement",
        "category": "POS İŞLEMLERİ",
    },
    {
        "key": "12",
        "title": "POS yatışını gerçekleştir",
        "module": "app.db.realize_pos_settlement",
        "category": "POS İŞLEMLERİ",
    },
    {
        "key": "13",
        "title": "Yazılan çek oluştur",
        "module": "app.db.create_issued_check",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "14",
        "title": "Yazılan çek öde",
        "module": "app.db.pay_issued_check",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "15",
        "title": "Yazılan çek iptal et",
        "module": "app.db.cancel_issued_check",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "16",
        "title": "Alınan çek oluştur",
        "module": "app.db.create_received_check",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "17",
        "title": "Alınan çek tahsil et",
        "module": "app.db.collect_received_check",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "18",
        "title": "Alınan çek iptal et",
        "module": "app.db.cancel_received_check",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "19",
        "title": "Çek listesini göster",
        "module": "app.db.list_checks",
        "category": "ÇEK İŞLEMLERİ",
    },
    {
        "key": "20",
        "title": "PostgreSQL yedeği al",
        "module": "app.db.backup_database",
        "category": "YEDEKLEME / GÜVENLİK",
    },
    {
        "key": "21",
        "title": "Yedekten geri dönüş testi yap",
        "module": "app.db.test_backup_restore",
        "category": "YEDEKLEME / GÜVENLİK",
    },
    {
        "key": "22",
        "title": "Güvenlik özet raporunu göster",
        "module": "app.db.show_security_summary",
        "category": "YEDEKLEME / GÜVENLİK",
    },
    {
        "key": "23",
        "title": "Güvenlik özet raporunu mail gönder",
        "module": "app.db.send_security_summary_mail",
        "category": "YEDEKLEME / GÜVENLİK",
    },
    {
        "key": "24",
        "title": "Yetkisiz işlem denemelerini listele",
        "module": "app.db.list_permission_denied_logs",
        "category": "YEDEKLEME / GÜVENLİK",
    },
    {
        "key": "25",
        "title": "Sistem sağlık kontrolü yap",
        "module": "app.db.system_health_check",
        "category": "SİSTEM SAĞLIĞI",
    },
    {
        "key": "26",
        "title": "Sistem sağlık raporunu mail gönder",
        "module": "app.db.send_system_health_mail",
        "category": "SİSTEM SAĞLIĞI",
    },
    {
        "key": "27",
        "title": "Finansal Excel raporu oluştur",
        "module": "app.db.export_financial_reports_excel",
        "category": "RAPORLAR",
    },
]


def clear_screen() -> None:
    print("\n" * 3)


def print_quick_health_panel() -> None:
    print("SİSTEM DURUMU")
    print("-" * 90)

    try:
        from app.db.session import session_scope
        from app.services.system_health_service import run_system_health_check

        with session_scope() as session:
            report = run_system_health_check(session)

        print(f"Genel durum : {report.overall_status}")
        print(f"OK          : {report.passed_count}")
        print(f"WARN        : {report.warning_count}")
        print(f"FAIL        : {report.failed_count}")

        problem_items = [
            item for item in report.items
            if item.status in {"WARN", "FAIL"}
        ]

        if problem_items:
            print("")
            print("Dikkat isteyen kontroller:")

            for item in problem_items[:5]:
                print(f"- {item.status} | {item.name}: {item.message}")

            if len(problem_items) > 5:
                print(f"- Ayrıca {len(problem_items) - 5} kayıt daha var. Detay için 25. seçeneği çalıştır.")

        else:
            print("Kısa özet   : Tüm temel kontroller OK.")

    except Exception as exc:
        print("Genel durum : OKUNAMADI")
        print(f"Açıklama    : Mini sağlık kontrolü alınamadı: {exc}")
        print("Detay için 25. seçeneği çalıştır.")

    print("-" * 90)
    print("")


def print_header() -> None:
    print("=" * 90)
    print("FTM YÖNETİM MENÜSÜ")
    print("=" * 90)
    print("Bu ekran mevcut komutları tek yerden çalıştırır.")
    print("Her işlem kendi içinde kullanıcı girişi ve yetki kontrolü yapar.")
    print("=" * 90)
    print("")
    print_quick_health_panel()


def print_menu() -> None:
    current_category = None

    for item in MENU_ITEMS:
        category = item["category"]

        if category != current_category:
            current_category = category
            print("")
            print(category)
            print("-" * 90)

        print(f"{item['key']:>2}. {item['title']}")

    print("")
    print(" 0. Çıkış")
    print("")


def find_menu_item(selection: str) -> dict[str, str] | None:
    cleaned_selection = selection.strip()

    for item in MENU_ITEMS:
        if item["key"] == cleaned_selection:
            return item

    return None


def run_module(module_name: str) -> int:
    command = [
        sys.executable,
        "-m",
        module_name,
    ]

    print("")
    print("=" * 90)
    print(f"Çalıştırılıyor: python -m {module_name}")
    print("=" * 90)
    print("")

    completed_process = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )

    print("")
    print("=" * 90)

    if completed_process.returncode == 0:
        print("İşlem tamamlandı.")
    else:
        print(f"İşlem hata kodu ile tamamlandı: {completed_process.returncode}")

    print("=" * 90)

    return int(completed_process.returncode)


def wait_for_enter() -> None:
    print("")
    input("Menüye dönmek için Enter'a bas...")


def main() -> None:
    while True:
        clear_screen()
        print_header()
        print_menu()

        selection = input("Seçim: ").strip()

        if selection == "0":
            print("")
            print("FTM yönetim menüsünden çıkılıyor.")
            return

        selected_item = find_menu_item(selection)

        if selected_item is None:
            print("")
            print("Geçersiz seçim.")
            wait_for_enter()
            continue

        run_module(selected_item["module"])
        wait_for_enter()


if __name__ == "__main__":
    main()
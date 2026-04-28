from traceback import print_exc

from app.services.restore_test_service import (
    test_latest_backup_restore as run_latest_backup_restore,
)


def main() -> None:
    print("FTM yedekten geri dönüş testi başladı...")
    print("")
    print("Not: Bu işlem canlı ftm_db veritabanına dokunmaz.")
    print("Test restore veritabanı: ftm_restore_test")
    print("")

    try:
        result = run_latest_backup_restore()

        print("Yedekten geri dönüş testi başarılı.")
        print(f"Kullanılan yedek dosyası : {result.backup_file}")
        print(f"Test veritabanı          : {result.restore_database_name}")
        print(f"Tablo sayısı             : {result.table_count}")
        print(f"Başlangıç zamanı         : {result.started_at}")
        print(f"Bitiş zamanı             : {result.finished_at}")
        print("")
        print("Ana tablo kayıt sayıları:")

        for table_name, row_count in result.key_table_counts.items():
            if row_count < 0:
                print(f"- {table_name}: tablo yok")
            else:
                print(f"- {table_name}: {row_count}")

        print("")
        print("Log dosyası              : logs\\restore_test_log.txt")

    except Exception:
        print("Yedekten geri dönüş testi sırasında hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
from traceback import print_exc

from app.services.backup_service import create_database_backup


def _format_backup_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} byte"

    size_kb = size_bytes / 1024

    if size_kb < 1024:
        return f"{size_kb:.2f} KB"

    size_mb = size_kb / 1024

    if size_mb < 1024:
        return f"{size_mb:.2f} MB"

    size_gb = size_mb / 1024

    return f"{size_gb:.2f} GB"


def main() -> None:
    print("FTM PostgreSQL yedekleme işlemi başladı...")
    print("")

    try:
        result = create_database_backup()

        if not result.success:
            print("Yedekleme yapılmadı.")
            print(result.message)
            raise SystemExit(1)

        print("PostgreSQL yedeği başarıyla alındı.")
        print(f"Yedek dosyası       : {result.backup_file}")
        print(f"Yedek boyutu        : {_format_backup_size(result.backup_size_bytes)}")
        print(f"Silinen eski yedek  : {result.deleted_old_backup_count}")
        print(f"Başlangıç zamanı    : {result.started_at}")
        print(f"Bitiş zamanı        : {result.finished_at}")
        print("")
        print("Mail bilgisi:")
        print(f"Mail aktif mi       : {result.mail_enabled}")
        print(f"Mail gönderildi mi  : {result.mail_sent}")
        print(f"Mail alıcıları      : {', '.join(result.mail_recipients) if result.mail_recipients else '-'}")
        print(f"Mail durumu         : {result.mail_message}")
        print("")
        print("Log dosyası         : logs\\backup_log.txt")

    except Exception:
        print("Yedekleme sırasında hata oluştu.")
        print("Hata detayı:")
        print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
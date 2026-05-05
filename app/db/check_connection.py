from app.core.config import settings
from app.db.session import check_database_connection


def main() -> None:
    result = check_database_connection()

    print("FTM SQLite bağlantısı başarılı.")
    print("")
    print("Yerel veritabanı bilgisi:")
    print(f"DB Motoru       : {result['database_engine']}")
    print(f"SQLite Dosyası  : {settings.sqlite_database_path}")
    print(f"DB URL          : {result['database_url']}")
    print("")
    print("SQLite çalışma bilgisi:")
    print(f"Veri dosyası    : {result['database_name']}")
    print(f"Çalışma modu    : {result['server_port']}")
    print(f"Kullanıcı       : {result['user_name']}")
    print(f"Sürüm           : {result['version_text']}")


if __name__ == "__main__":
    main()
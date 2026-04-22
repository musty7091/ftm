from app.core.config import settings
from app.db.session import check_database_connection


def main() -> None:
    result = check_database_connection()

    print("FTM PostgreSQL bağlantısı başarılı.")
    print("")
    print("Uygulamanın bağlandığı adres:")
    print(f"Host       : {settings.database_host}")
    print(f"Dış Port   : {settings.database_port}")
    print(f"Veritabanı : {settings.database_name}")
    print(f"Kullanıcı  : {settings.database_user}")
    print("")
    print("PostgreSQL sunucu bilgisi:")
    print(f"Veritabanı : {result['database_name']}")
    print(f"Kullanıcı  : {result['user_name']}")
    print(f"İç Port    : {result['server_port']}")
    print(f"Sürüm      : {result['version_text']}")


if __name__ == "__main__":
    main()
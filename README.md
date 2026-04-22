# FTM - Finansal Takip Merkezi

FTM, çok banka, çok hesap, çek, POS, nakit, transfer ve finansal risk takibi için geliştirilen Windows masaüstü finans yönetim uygulamasıdır.

## Teknoloji

- Python 3.12
- PySide6
- PostgreSQL
- SQLAlchemy
- Alembic
- Decimal
- pytest
- PyInstaller

## Temel Prensipler

- Bakiye doğrudan değiştirilmez.
- Finansal hareketler kayıt altına alınır.
- Para hesaplarında Decimal kullanılır.
- Kritik işlemler audit log'a yazılır.
- Silme yerine iptal mantığı kullanılır.
- Planlanan ve gerçekleşen hareketler ayrı tutulur.
- Raporlar hareket kayıtlarından üretilir.
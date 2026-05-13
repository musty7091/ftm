# FTM Finans Takip Merkezi

**FTM Finans Takip Merkezi**, işletmelerin günlük finans hareketlerini, banka hesaplarını, çeklerini, POS yatışlarını, kredi kartlarını, limitli/kredili hesaplarını, risklerini, yedeklerini, lisans durumunu ve raporlarını takip etmek için geliştirilen Windows masaüstü finans yönetim uygulamasıdır.

Bu proje özellikle muhasebe ve finans operasyonlarında kullanılan verilerin düzenli, izlenebilir, güvenli ve raporlanabilir şekilde yönetilmesini hedefler.

---

## Proje Durumu

FTM aktif geliştirme aşamasındadır.

Mevcut hedef:

- Yerel çalışan Windows masaüstü uygulaması
- SQLite tabanlı local desktop veri saklama
- Finansal tutarlılık ve Decimal para hesapları
- Audit log ile kritik işlem izlenebilirliği
- Lisans kontrollü ticari kullanım
- Yedekleme / restore güvenliği
- Excel / PDF raporlama altyapısı
- PyInstaller ile EXE paketleme
- Pilot müşteri öncesi kalite seviyesine yükseltme

> Not: Bu repo geliştirme ve ürünleştirme sürecindedir. Ticari dağıtım öncesinde release paketi, private key güvenliği, fresh install testi, backup/restore testi ve build standardı mutlaka doğrulanmalıdır.

---

## Ana Özellikler

### Finansal Takip

- Çok banka ve çok hesap takibi
- TL, USD, EUR, GBP gibi farklı para birimlerinde banka hesapları
- Nakit / kasa takibi
- Banka giriş ve çıkış hareketleri
- Transfer ve bakiye yönetimi
- Gerçekleşen ve planlanan hareket ayrımı
- Hesap bazlı bakiye özeti

### Çek Yönetimi

- Yazılan çek takibi
- Alınan çek takibi
- Çek vade kontrolü
- Çek ödeme / tahsilat süreçleri
- İptal ve durum yönetimi
- Portföy, tahsil, banka, iade ve problemli çek senaryoları

### POS Yönetimi

- POS cihazları
- Beklenen POS yatışları
- Gerçekleşen POS yatışları
- Komisyon / net yatış takibi
- POS kaynaklı banka hareketleri

### Kredi Kartı Modülü

- Banka bazlı kredi kartı tanımı
- Kart limiti takibi
- Harcama kaydı
- Kullanılabilir limit kontrolü
- Kredi kartı ödeme kaydı
- Harcama iptal bilgisi
- Oluşturan / iptal eden kullanıcı altyapısı
- Kredi kartı işlemlerinde audit log

Ürün kararı olarak kredi kartı modülü TL çalışır. Kredi kartı harcamaları ve kredi kartı ödemeleri TL kabul edilir.

### Kredili / Limitli Hesap Modülü

- Banka hesabına bağlı limit tanımı
- Limit tutarı
- Kullanılan limit
- Ana para borcu
- Faiz borcu
- Masraf borcu
- Toplam borç
- Kullanılabilir limit
- Ödeme dağılımı
- Hareket iptali
- Audit bilgisi

### Raporlama

- Excel finansal raporları
- Banka bakiye raporları
- Risk raporları
- Transfer önerileri
- Yazılan çek raporu
- Alınan çek raporu
- Kredi kartı özeti
- Kredi kartı harcamaları
- Kredi kartı ödemeleri
- Limitli hesap özeti
- Limitli hesap hareketleri
- PDF raporlama altyapısı

### Güvenlik ve İzlenebilirlik

- Kullanıcı doğrulama
- Şifre hashleme
- Login deneme sınırlama
- Yetki kontrol altyapısı
- Kritik işlemlerde audit log
- Silme yerine iptal mantığı
- Lisans kontrolü
- Saat geri alma kontrolü
- Runtime dosyalarının repo dışında saklanması

---

## Teknoloji Yığını

- Python 3.12
- PySide6
- SQLite
- SQLAlchemy
- Decimal
- openpyxl
- reportlab
- pytest
- pytest-qt
- bcrypt
- cryptography
- PyInstaller

---

## Mimari Yaklaşım

FTM, yerel masaüstü uygulaması olarak tasarlanmıştır.

Genel yaklaşım:

- Uygulama Windows bilgisayarda çalışır.
- Finansal veriler kullanıcının bilgisayarındaki local SQLite veritabanında saklanır.
- Runtime dosyaları proje klasörü içinde değil, kullanıcıya ait güvenli uygulama klasöründe tutulur.
- Finansal hareketler doğrudan bakiye değiştirmek yerine hareket kayıtları üzerinden yönetilir.
- Raporlar hareket kayıtlarından üretilir.
- Kritik işlemler audit log’a yazılır.
- Riskli işlemlerde silme yerine iptal mantığı kullanılır.
- Lisans doğrulaması Ed25519 imzalı lisans dosyasıyla yapılır.

---

## Klasör Yapısı

Genel repo yapısı:

```text
ftm/
├─ app/
│  ├─ assets/
│  │  └─ branding/
│  ├─ core/
│  ├─ db/
│  ├─ models/
│  ├─ reports/
│  ├─ services/
│  ├─ ui/
│  └─ utils/
├─ migrations/
├─ tests/
├─ tools/
├─ README.md
├─ requirements.txt
└─ .gitignore
```

Önemli alanlar:

| Klasör / Dosya | Açıklama |
|---|---|
| `app/core/` | Ayarlar, runtime yolları, güvenlik, versiyon ve marka bilgileri |
| `app/db/` | Veritabanı bağlantısı, session yönetimi ve yardımcı DB komutları |
| `app/models/` | SQLAlchemy modelleri |
| `app/services/` | İş kuralları ve servis katmanı |
| `app/reports/` | Excel / PDF rapor üretimi |
| `app/ui/` | PySide6 arayüz dosyaları |
| `app/assets/branding/` | Logo ve uygulama ikonları |
| `tools/` | Geliştirici / lisans / bakım araçları |
| `tests/` | Test altyapısı |
| `.gitignore` | Runtime, build, lisans ve hassas dosyaları repodan dışlama kuralları |

---

## Runtime Veri Yolları

FTM runtime dosyalarını proje klasörü içinde değil, kullanıcının Windows profilindeki local uygulama klasöründe tutar.

Varsayılan çalışma klasörü:

```text
%LOCALAPPDATA%\FTM
```

Beklenen runtime yapı:

```text
%LOCALAPPDATA%\FTM
├─ data
│  └─ ftm_local.db
├─ config
│  ├─ app_settings.json
│  ├─ app_setup.json
│  ├─ license.json
│  ├─ device_identity.json
│  └─ license_clock_state.json
├─ backups
├─ exports
└─ logs
```

Önemli runtime dosyaları:

| Dosya | Açıklama |
|---|---|
| `%LOCALAPPDATA%\FTM\data\ftm_local.db` | SQLite veritabanı |
| `%LOCALAPPDATA%\FTM\config\license.json` | Aktif lisans dosyası |
| `%LOCALAPPDATA%\FTM\config\app_setup.json` | İlk kurulum bilgileri |
| `%LOCALAPPDATA%\FTM\config\app_settings.json` | Uygulama ayarları |
| `%LOCALAPPDATA%\FTM\config\device_identity.json` | Cihaz kimliği yedek mekanizması |
| `%LOCALAPPDATA%\FTM\config\license_clock_state.json` | Lisans saat kontrol durumu |
| `%LOCALAPPDATA%\FTM\backups` | Yedek dosyaları |
| `%LOCALAPPDATA%\FTM\exports` | Excel / PDF dışa aktarımlar |
| `%LOCALAPPDATA%\FTM\logs` | Log dosyaları |

Test veya özel kurulum sırasında runtime klasörü `FTM_RUNTIME_DIR` ortam değişkeni ile değiştirilebilir.

Örnek:

```powershell
$env:FTM_RUNTIME_DIR="C:\FTM_TEST_RUNTIME"
```

---

## Geliştirici Kurulumu

### 1. Repoyu Klonla

```powershell
git clone https://github.com/musty7091/ftm.git
cd ftm
```

### 2. Sanal Ortam Oluştur

```powershell
py -3.12 -m venv .venv
```

### 3. Sanal Ortamı Aktif Et

```powershell
.\.venv\Scripts\activate
```

### 4. Bağımlılıkları Kur

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Kurulumu Kontrol Et

```powershell
python --version
pip list
```

Beklenen Python sürümü:

```text
Python 3.12.x
```

---

## Uygulamayı Çalıştırma

FTM PySide6 tabanlı masaüstü uygulamadır.

Geliştirme ortamında uygulama, repodaki aktif ana giriş dosyası üzerinden çalıştırılır.

> Önemli not: Bu README, ana uygulama giriş komutunu bilinçli olarak sabitlemez. Çünkü ticari dağıtım öncesi P0 adımında tek ve resmi bir giriş komutu / run script standardı oluşturulmalıdır. Bu netleşmeden README’ye uydurma başlatma komutu yazmak doğru değildir.

Satış öncesi önerilen standart:

```powershell
python -m app
```

veya

```powershell
python run_app.py
```

Bu komutlardan biri proje içinde resmi standart haline getirilmeli ve README buna göre güncellenmelidir.

---

## İlk Kurulum Akışı

İlk müşteri kurulumunda beklenen akış:

1. Uygulama açılır.
2. Runtime klasörleri oluşturulur.
3. SQLite veritabanı hazırlanır.
4. İlk kullanıcı / yönetici kurulumu yapılır.
5. Lisans dosyası kontrol edilir.
6. Lisans yoksa uygulama açılabilir, ancak veri girişi kısıtlanır.
7. Geçerli Ed25519 imzalı lisans yüklendikten sonra veri girişi aktif olur.
8. Migration kontrolü yapılır.
9. Schema güncel değilse migration çalıştırılır.
10. Kritik güncellemelerden önce yedek alınır.

---

## Veritabanı

FTM mevcut ürün kararında SQLite local desktop modunda çalışır.

Varsayılan veritabanı:

```text
%LOCALAPPDATA%\FTM\data\ftm_local.db
```

SQLite bağlantısında hedeflenen güvenilirlik ayarları:

- Foreign key kontrolü açık
- WAL journal mode
- Busy timeout
- Local dosya tabanlı çalışma
- Runtime klasörü içinde veri saklama

---

## Migration Sistemi

FTM, SQLite veritabanı için özel migration sistemi kullanır.

Migration sisteminin amacı:

- Veritabanı şemasını versiyonlamak
- Eski veritabanlarını güvenli şekilde güncellemek
- Migration geçmişini kayıt altında tutmak
- Migration öncesi yedek almak
- Veritabanı schema sürümü ile uygulama sürümünü uyumlu tutmak

Mevcut hedef schema seviyesi:

```text
DB schema v8
```

Migration takip tablosu:

```text
schema_migrations
```

SQLite schema versiyon kontrolü:

```text
PRAGMA user_version
```

Satış öncesi her release için kontrol edilmesi gerekenler:

- Veritabanı dosyası var mı?
- `schema_migrations` tablosu var mı?
- `PRAGMA user_version` beklenen seviyede mi?
- Bekleyen migration var mı?
- Migration checksum kayıtları tutarlı mı?
- Migration öncesi yedek alındı mı?
- Migration sonrası uygulama açılıyor mu?

---

## Finansal Doğruluk Prensipleri

FTM finansal doğruluk için şu prensipleri hedefler:

- Para hesaplarında `float` kullanılmaz.
- Para hesaplarında `Decimal` kullanılır.
- Para alanları iki ondalık hassasiyetle yönetilir.
- Faiz / oran alanları ayrı hassasiyetle tutulur.
- Bakiye doğrudan değiştirilmez.
- Bakiye, hareket kayıtlarından hesaplanır.
- Silme yerine iptal mantığı tercih edilir.
- İptal edilen hareketler geçmiş izlenebilirliği için korunur.
- Kritik işlemler audit log’a yazılır.
- Para birimi uyumsuzluğu engellenir.
- Gerçekleşmiş çıkış hareketleri bakiye kontrolünden geçer.

Örnek finansal kontroller:

- Banka hesabı para birimi ile hareket para birimi aynı olmalıdır.
- Gerçekleşmiş banka çıkışı hesabı eksiye düşürmemelidir.
- Kredi kartı harcaması kullanılabilir limiti aşmamalıdır.
- Kredi kartı modülü TL çalışmalıdır.
- Limitli hesap ödemelerinde ana para / faiz / masraf dağılımı ayrı takip edilmelidir.

---

## Lisanslama Sistemi

FTM lisans sistemi Ed25519 imzalı lisans dosyalarına dayanır.

Temel kurallar:

- Eski v1 / imzasız lisanslar desteklenmez.
- Sadece version 2 Ed25519 imzalı lisanslar kabul edilir.
- Uygulama içinde yalnızca public key bulunur.
- Private key müşteri paketinde bulunmamalıdır.
- Private key repoya eklenmemelidir.
- Lisans cihaz koduna bağlıdır.
- Lisans başlangıç ve bitiş tarihi kontrol edilir.
- Süresi dolmuş lisans veri girişini engeller.
- Saat geri alma şüphesi veri girişini engeller.

Lisans durumları:

| Durum | Anlamı |
|---|---|
| Lisans Yok | Uygulama açılır, veri girişi engellenir |
| Lisans Aktif | Uygulama ve veri girişi aktiftir |
| Lisans Yakında Bitecek | Uygulama çalışır, kullanıcı uyarılır |
| Lisans Süresi Doldu | Uygulama açılır, veri girişi engellenir |
| Cihaz Uyumsuz | Lisans bu bilgisayara ait değildir |
| İmza Geçersiz | Lisans değiştirilmiş veya sahte olabilir |
| Bilgisayar Tarihi Şüpheli | Saat geri alma riski vardır |

---

## Private Key Güvenlik Politikası

Private key, FTM’nin ticari lisans güvenliğinin anahtarıdır.

Kesin kurallar:

- Private key asla GitHub reposuna eklenmez.
- Private key asla müşteri bilgisayarına gönderilmez.
- Private key asla müşteri EXE paketine dahil edilmez.
- Private key asla `dist/`, `release_packages/` veya installer klasörüne kopyalanmaz.
- Private key sadece lisans üretici bilgisayarda saklanır.
- Private key yedeklenirken güvenli ve erişimi sınırlı ortam kullanılmalıdır.

Repo ve paket içinde bulunmaması gereken örnek dosyalar:

```text
*.pem
*.key
*.p12
*.pfx
*.ftmlic
license.json
ftm_local.db
device_identity.json
license_clock_state.json
```

Release öncesi kontrol:

```powershell
git status
git log --all -p -- "*.pem"
git log --all -p -- "*.key"
git log --all -p -- "*.ftmlic"
```

Ek öneri:

```powershell
gitleaks detect --source .
```

---

## Yedekleme

FTM için yedekleme kritik bir güvenlik katmanıdır.

Yedekleme hedefleri:

- Kullanıcının finansal verisini korumak
- Migration öncesi geri dönüş noktası oluşturmak
- Restore testleri ile yedeklerin gerçekten çalıştığını kanıtlamak
- Müşteri destek sürecinde veri kaybını önlemek

Varsayılan yedek klasörü:

```text
%LOCALAPPDATA%\FTM\backups
```

Yedekleme standartları:

- Yedek dosyası tarih/saat bilgisi içermelidir.
- Yedek dosyası hash ile doğrulanmalıdır.
- Bozuk yedek restore edilmemelidir.
- Restore öncesi mevcut veritabanının ayrıca yedeği alınmalıdır.
- Restore sonrası SQLite bütünlük kontrolü yapılmalıdır.
- Restore sonrası schema versiyonu kontrol edilmelidir.

---

## Restore

Restore işlemi yüksek riskli işlemdir.

Restore sırasında uygulanması gereken kurallar:

1. Kullanıcı açık şekilde uyarılmalıdır.
2. Restore edilecek yedek dosyası doğrulanmalıdır.
3. Mevcut veritabanının otomatik yedeği alınmalıdır.
4. Yanlış formatlı dosyalar reddedilmelidir.
5. Restore sonrası veritabanı bütünlüğü kontrol edilmelidir.
6. Restore sonrası migration durumu kontrol edilmelidir.
7. Uygulama yeniden başlatılmalıdır.

Restore testi minimum olarak şunları doğrulamalıdır:

- Yedek dosyası var
- Dosya boyutu beklenen aralıkta
- Hash doğru
- SQLite `quick_check` başarılı
- Schema seviyesi beklenen değerde
- Kritik tablolar okunabiliyor
- Uygulama restore sonrası açılıyor

---

## Audit Log

FTM kritik işlemleri audit log’a yazar.

Audit log hedefleri:

- Kim yaptı?
- Ne yaptı?
- Hangi kayıt üzerinde yaptı?
- Eski değer neydi?
- Yeni değer ne oldu?
- Ne zaman oldu?
- İptal sebebi neydi?

Audit log kullanılan örnek işlemler:

- Kullanıcı girişi
- Başarısız login denemesi
- Banka hareketi oluşturma
- Banka hareketi iptal etme
- Kredi kartı oluşturma
- Kredi kartı güncelleme
- Kredi kartı harcaması oluşturma
- Kredi kartı harcaması iptal etme
- Kredi kartı ödeme işlemleri
- Limitli hesap hareketleri
- Yetkisiz işlem denemeleri

> Not: Mevcut audit log yapısı işlem geçmişini izlemek için kullanılır. İleri fazda audit log bütünlüğü için hash-chain veya benzeri değişiklik tespit mekanizması eklenmesi önerilir.

---

## Kullanıcı ve Şifre Güvenliği

FTM kullanıcı doğrulama sistemi içerir.

Şifre politikası:

- Şifre boş olamaz.
- Minimum uzunluk kontrolü yapılır.
- Bcrypt byte sınırı kontrol edilir.
- Şifrede harf ve rakam aranır.
- Şifreler bcrypt ile hashlenir.
- Düz metin şifre saklanmaz.

Login güvenliği:

- Başarısız girişler audit log’a yazılır.
- Çok sayıda başarısız denemede geçici kilit uygulanır.
- Başarılı giriş tarihi kaydedilir.
- Pasif kullanıcı giriş yapamaz.

---

## Raporlama

FTM rapor altyapısı finansal hareketlerden rapor üretmeyi hedefler.

Excel raporları için beklenen sayfalar:

- Banka bakiyeleri
- Risk özetleri
- Transfer önerileri
- Yazılan çekler
- Alınan çekler
- Kredi kartı özeti
- Kredi kartı harcamaları
- Kredi kartı ödemeleri
- Limitli hesap özeti
- Limitli hesap hareketleri

Raporlama prensipleri:

- Raporlar kaynak hareketlerden üretilmelidir.
- İptal edilen kayıtlar rapor politikasına göre açık şekilde ayrılmalıdır.
- Para birimi bilgisi kaybolmamalıdır.
- Excel sayfaları okunabilir kolon başlıklarına sahip olmalıdır.
- Finansal toplamlar Decimal mantığıyla hesaplanmalıdır.

---

## Testler

Test çalıştırma:

```powershell
pytest
```

Daha detaylı çıktı:

```powershell
pytest -v
```

Belirli bir test dosyası:

```powershell
pytest tests/test_dosya_adi.py -v
```

Satış öncesi minimum test başlıkları:

| Alan | Test |
|---|---|
| Fresh install | Boş runtime klasöründe ilk açılış |
| Migration | Eski DB’den güncel schema’ya geçiş |
| Backup | Yedek alma ve doğrulama |
| Restore | Yedekten geri dönme ve bütünlük kontrolü |
| Lisans | Yok, geçersiz, süresi dolmuş, farklı cihaz, sahte imza |
| Saat kontrolü | Clock rollback tespiti |
| Banka | Bakiye, giriş, çıkış, iptal |
| Çek | Yazılan / alınan çek oluşturma, ödeme, tahsil, iptal |
| POS | Beklenen ve gerçekleşen POS yatışları |
| Kredi kartı | Limit aşımı, ödeme, iptal |
| Limitli hesap | Ana para, faiz, masraf, ödeme dağılımı |
| Raporlama | Excel / PDF üretimi |
| UI | Küçük ekran, lisans ekranı, hata mesajları |

---

## Build / EXE Üretimi

FTM PyInstaller ile EXE paketlenebilir.

Genel build ilkeleri:

- Build temiz sanal ortamda yapılmalıdır.
- `dist/` ve `build/` klasörleri repoya eklenmemelidir.
- Runtime DB dosyaları pakete dahil edilmemelidir.
- Log dosyaları pakete dahil edilmemelidir.
- Yedek dosyaları pakete dahil edilmemelidir.
- Lisans dosyaları pakete dahil edilmemelidir.
- Private key kesinlikle pakete dahil edilmemelidir.
- Marka asset dosyaları pakete dahil edilmelidir.
- EXE başka bir Windows bilgisayarda test edilmelidir.

Satış öncesi önerilen build standardı:

```powershell
pyinstaller --clean --noconfirm --windowed --name FTM <ana_giris_dosyasi.py>
```

> Not: `<ana_giris_dosyasi.py>` alanı P0 paketleme standardı sırasında netleştirilmelidir. Ticari dağıtım öncesi bu komut tek ve resmi build script haline getirilmelidir.

Build sonrası kontrol listesi:

```text
dist/
├─ FTM.exe
└─ gerekli uygulama dosyaları
```

Paket içinde olmaması gerekenler:

```text
.env
*.db
*.sqlite
*.sqlite3
*.pem
*.key
*.ftmlic
license.json
device_identity.json
license_clock_state.json
logs/
backups/
exports/
```

---

## .gitignore Politikası

Repo şu dosyaları içermemelidir:

- Sanal ortamlar
- Python cache dosyaları
- Log dosyaları
- Yedekler
- Export dosyaları
- SQLite veritabanları
- Runtime config dosyaları
- Lisans dosyaları
- Private key dosyaları
- Build çıktıları
- Release paket çıktıları
- Test cache dosyaları

Özellikle şu dosyalar repoya girmemelidir:

```text
.env
*.db
*.sqlite
*.sqlite3
*.pem
*.key
*.ftmlic
license.json
app_settings.json
app_setup.json
```

---

## Müşteri Kurulum Notları

Müşteri kurulumu için hedef akış:

1. Müşteriye sadece uygulama kurulum paketi verilir.
2. Private key veya lisans üretici araç verilmez.
3. Müşteri bilgisayarında uygulama açılır.
4. Cihaz kodu alınır.
5. Lisans üretici bilgisayarda bu cihaz koduna göre `.ftmlic` oluşturulur.
6. Müşteri uygulamasına lisans yüklenir.
7. Uygulama veri girişine açılır.
8. İlk yedek alınır.
9. Test kayıtlarıyla temel modüller doğrulanır.
10. Müşteriye yedek alma / restore uyarıları anlatılır.

Müşteriye anlatılması gereken kritik noktalar:

- Veritabanı müşterinin bilgisayarında saklanır.
- Düzenli yedek alınmalıdır.
- Bilgisayar tarihiyle oynanması lisansı kilitleyebilir.
- Lisans başka bilgisayarda çalışmaz.
- Uygulama klasöründeki runtime dosyaları bilinçsizce silinmemelidir.
- Backup klasörü düzenli olarak harici diske veya güvenli ortama kopyalanmalıdır.

---

## Satış Öncesi Kontrol Listesi

Ticari satıştan önce tamamlanması gereken zorunlu kontroller:

### P0 - Satıştan Önce Zorunlu

- [ ] Fresh install testi yapıldı
- [ ] Boş bilgisayarda uygulama açıldı
- [ ] Runtime klasörleri doğru oluştu
- [ ] SQLite veritabanı doğru oluştu
- [ ] DB schema v8 doğrulandı
- [ ] Migration sistemi test edildi
- [ ] Migration öncesi yedek alındığı doğrulandı
- [ ] Backup alma testi başarılı
- [ ] Restore testi başarılı
- [ ] Bozuk yedek reddedildi
- [ ] Lisans yokken veri girişi engellendi
- [ ] Geçerli lisansla veri girişi açıldı
- [ ] Sahte imzalı lisans reddedildi
- [ ] Farklı cihaz lisansı reddedildi
- [ ] Süresi dolmuş lisans veri girişini engelledi
- [ ] Saat geri alma kontrolü çalıştı
- [ ] Private key release paketinde yok
- [ ] Runtime DB release paketinde yok
- [ ] Log / backup / export dosyaları release paketinde yok
- [ ] EXE başka bilgisayarda test edildi
- [ ] README güncel
- [ ] Kullanıcıya yedekleme talimatı hazır

### P1 - Pilot Müşteriden Önce

- [ ] Kredi kartı uçtan uca test edildi
- [ ] Limitli hesap uçtan uca test edildi
- [ ] Ana para / faiz / masraf dağılımı test edildi
- [ ] Çek ödeme / tahsilat senaryoları test edildi
- [ ] POS yatış senaryoları test edildi
- [ ] Excel raporları kontrol edildi
- [ ] PDF raporları kontrol edildi
- [ ] UI küçük ekran testi yapıldı
- [ ] Hata mesajları sadeleştirildi
- [ ] Support bundle veya destek paketi hazırlandı

### P2 - Ürünü Güçlendiren İyileştirmeler

- [ ] Audit log export
- [ ] Audit bütünlük kontrolü
- [ ] Otomatik yedek hatırlatma
- [ ] Müşteri kullanım kılavuzu
- [ ] Demo veri seti
- [ ] Standart rapor şablonları
- [ ] Installer iyileştirmesi

### P3 - Gelecek Faz

- [ ] DB encryption
- [ ] Hash-chain audit log
- [ ] Otomatik güncelleme
- [ ] Kod imzalı installer
- [ ] Çok firma desteği
- [ ] Bulut yedekleme opsiyonu

---

## Bilinen Sınırlamalar

Mevcut ürün kararları ve sınırlamalar:

- Kredi kartı modülü TL çalışır.
- Kredi kartı için dövizli kart / dövizli harcama desteklenmez.
- SQLite local desktop mimarisi hedeflenmiştir.
- Multi-user network çalışma bu fazın hedefi değildir.
- Private key müşteri paketinde bulunmamalıdır.
- Audit log mevcut haliyle izlenebilirlik sağlar; ileri fazda bütünlük koruması güçlendirilmelidir.
- Build / çalıştırma komutu satış öncesi P0’da tek standart haline getirilmelidir.
- Müşteri bilgisayarında düzenli yedekleme operasyonel olarak önemlidir.

---

## Güvenlik Uyarısı

Bu repo public olduğu için gerçek müşteri verisi, gerçek lisans dosyası, private key, canlı veritabanı, gerçek `.env` dosyası, yedek dosyası veya ticari sır içeren çıktı dosyaları repoya eklenmemelidir.

Kesinlikle repoya eklenmemesi gerekenler:

```text
.env
license.json
*.ftmlic
*.pem
*.key
*.db
*.sqlite
*.sqlite3
backups/
exports/
logs/
release_packages/
pilot_packages/
```

---

## Geliştirme Prensipleri

FTM geliştirilirken şu kurallar korunmalıdır:

- Büyük refactor yerine küçük ve kontrollü değişiklik yapılır.
- Fonksiyon, sınıf ve dosya isimleri gereksiz yere değiştirilmez.
- Para hesaplarında `Decimal` dışına çıkılmaz.
- Finansal işlem silinmez, iptal edilir.
- Kritik işlem audit log’a yazılır.
- Migration gerektiren değişiklikler açıkça belirtilir.
- Her değişiklik test edilebilir olmalıdır.
- Satış öncesi kalite, hızlı özellik eklemekten daha önemlidir.

---

## Roadmap

### P0 - Satış Öncesi Güvenli Temel

- README ve teknik dokümantasyon
- Private key güvenliği
- Fresh install standardı
- Migration v8 doğrulama
- Backup / restore doğrulama
- Release paketi hijyeni
- Build standardı
- Secret scanning

### P1 - Pilot Müşteri Hazırlığı

- Kredi kartı tam test seti
- Limitli hesap tam test seti
- Çek / POS / banka işlem testleri
- UI küçük ekran iyileştirmeleri
- Excel / PDF rapor doğrulama
- Destek paketi

### P2 - Ürün Kalitesini Güçlendirme

- Audit export
- Audit bütünlük kontrolü
- Otomatik yedek hatırlatma
- Demo veri seti
- Kullanıcı kılavuzu
- Kurumsal rapor şablonları

### P3 - İleri Seviye Ürünleşme

- DB encryption
- Kod imzalı installer
- Otomatik güncelleme
- Çok firma desteği
- Bulut yedekleme opsiyonu
- Lisans yönetim paneli

---

## Kısa Özet

FTM; banka, çek, POS, kredi kartı, limitli hesap, raporlama, lisanslama, yedekleme ve audit log özelliklerini tek bir Windows masaüstü finans uygulamasında toplamayı hedefler.

Ana hedef, finansal doğruluğu ve kullanıcı güvenini merkeze alan, ticari olarak satılabilir bir masaüstü finans takip ürünü oluşturmaktır.

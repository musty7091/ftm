# FTM Lisans Güvenlik Politikası

Bu dosya, **FTM Finans Takip Merkezi** projesinde lisans üretimi, private key güvenliği, müşteri kurulumu ve release paketi güvenliği için uygulanacak resmi çalışma kurallarını tanımlar.

Bu politikanın amacı, FTM uygulamasının ticari lisanslama kontrolünü korumak ve private key sızıntısı riskini en aza indirmektir.

---

## 1. Temel Güvenlik Kararı

FTM lisans üretimi **sadece Mustafa'nın kişisel bilgisayarında** yapılacaktır.

Müşteri bilgisayarında lisans üretici uygulama çalıştırılmayacaktır.

Müşteri bilgisayarına şu dosyalar hiçbir şartta kopyalanmayacaktır:

- FTM Licence Maker uygulaması
- Ed25519 private key dosyası
- Private key içeren klasörler
- Lisans üretim araçları
- Geliştirici araçları
- Kaynak kod
- Test / debug araçları

Müşteri bilgisayarına sadece şunlar götürülebilir:

- FTM kurulum dosyası
- Kurulum notları
- Oluşturulmuş müşteri lisans dosyası
- Kullanıcıya verilecek kullanım / destek dokümanları

---

## 2. Lisanslama Modeli

FTM, Ed25519 imzalı lisans dosyalarıyla çalışır.

Genel yapı:

- Uygulama içinde sadece public key bulunur.
- Private key sadece lisans üretim bilgisayarında bulunur.
- Lisans dosyası cihaz koduna göre üretilir.
- Lisans dosyası imzalanır.
- FTM uygulaması lisans dosyasını public key ile doğrular.
- Sahte, değiştirilmiş veya farklı cihaza ait lisanslar geçersiz kabul edilir.

---

## 3. Private Key Nedir?

Private key, FTM lisans sisteminin en kritik gizli anahtarıdır.

Private key'e sahip olan kişi teorik olarak geçerli lisans üretebilir.

Bu nedenle private key:

- Müşteriye verilmez.
- Müşteri bilgisayarında çalıştırılmaz.
- USB kurulum paketine konulmaz.
- GitHub reposuna eklenmez.
- E-posta ile gönderilmez.
- WhatsApp / Telegram / benzeri kanallarla paylaşılmaz.
- Bulut senkronizasyon klasörlerinde tutulmaz.
- Şifresiz olarak taşınmaz.
- Yedeksiz bırakılmaz.

---

## 4. Nihai Operasyon Kararı

FTM için tercih edilen güvenli operasyon modeli şudur:

### 4.1 Müşteri Kurulum Dosyası

Müşteriye götürülecek kurulum paketi içinde sadece uygulama kurulumu bulunur.

Örnek yapı:

    FTM_CUSTOMER_INSTALL/
    ├─ FTM_Setup.exe
    ├─ FTM_Kurulum_Notlari.txt
    ├─ version.txt
    └─ checksums.txt

Bu pakette aşağıdakiler kesinlikle bulunmaz:

    FTM_Licence_Maker.exe
    keys/
    tools/
    *.pem
    *.key
    *.ftmlic
    license.json
    ftm_local.db
    *.db
    logs/
    backups/
    exports/

### 4.2 Lisans Üretim Bilgisayarı

Lisans üretimi sadece Mustafa'nın kişisel bilgisayarında yapılır.

Bu bilgisayarda bulunabilecek güvenli yapı:

    C:\FTM_LICENSE_ADMIN
    ├─ FTM_Licence_Maker.exe
    ├─ keys
    │  └─ ftm_license_ed25519_private_encrypted.pem
    ├─ output
    ├─ logs
    └─ README_LISANS_URETME.txt

Bu klasör müşteriyle paylaşılmaz.

---

## 5. Satış Günü Güvenli Lisans Akışı

### 5.1 Müşteri Bilgisayarında Yapılacaklar

1. Müşteri bilgisayarına FTM kurulur.
2. FTM ilk kez açılır.
3. Uygulama cihaz kodunu gösterir.
4. Cihaz kodu not alınır.

Örnek cihaz kodu:

    FTM-XXXX-XXXX-XXXX-XXXX-XXXX

Müşteri bilgisayarında yapılmayacaklar:

- Licence Maker çalıştırılmaz.
- Private key takılmaz.
- Private key kopyalanmaz.
- Geliştirici klasörü açılmaz.
- Kaynak kod kopyalanmaz.

### 5.2 Mustafa'nın Kişisel Bilgisayarında Yapılacaklar

1. FTM Licence Maker açılır.
2. Müşteri firma adı girilir.
3. Müşteri cihaz kodu girilir.
4. Lisans türü seçilir.
5. Lisans başlangıç ve bitiş tarihi belirlenir.
6. Private key parolası girilir.
7. Lisans dosyası oluşturulur.
8. Lisans dosyası output klasörüne kaydedilir.
9. Lisans üretim logu kayıt altına alınır.

Örnek lisans dosyası:

    ABC_MARKET_annual_FTM-XXXX-XXXX-XXXX-XXXX-XXXX_20260513.ftmlic

### 5.3 Lisans Dosyasının Müşteri Bilgisayarına Aktarılması

Müşteri bilgisayarına sadece oluşturulan `.ftmlic` lisans dosyası aktarılır.

Aktarım için tercih edilen yöntemler:

1. Temiz ve ayrı bir transfer USB'si
2. Güvenli e-posta
3. Güvenli dosya paylaşımı
4. Yerinde kurulumda Mustafa'nın kontrolündeki geçici transfer medyası

Transfer medyasında sadece ilgili müşteriye ait lisans dosyası bulunmalıdır.

Transfer medyasında bulunmaması gerekenler:

    FTM_Licence_Maker.exe
    keys/
    *.pem
    *.key
    tools/
    source/
    *.db

---

## 6. Private Key Saklama Standardı

Private key şifreli saklanmalıdır.

Hedef private key dosyası:

    ftm_license_ed25519_private_encrypted.pem

Şifresiz private key dosyası kalıcı kullanımda tutulmamalıdır.

Riskli dosya:

    ftm_license_ed25519_private.pem

Private key saklama önerisi:

    C:\FTM_LICENSE_ADMIN\keys\ftm_license_ed25519_private_encrypted.pem

Private key yedeği en az bir güvenli offline ortamda tutulmalıdır.

Yedekleme önerileri:

- Şifreli harici disk
- BitLocker ile şifrelenmiş USB
- Fiziksel kasa
- Güvenli offline yedek
- Erişimi sınırlı kişisel arşiv

Private key şu ortamlarda tutulmamalıdır:

- Public GitHub repo
- Müşteri USB'si
- Müşteri bilgisayarı
- Ortak şirket bilgisayarı
- Google Drive / OneDrive otomatik senkronizasyon klasörü
- Masaüstünde açık klasör
- WhatsApp / e-posta eki
- Build çıktısı klasörü
- Installer klasörü

---

## 7. Licence Maker Güvenlik Kuralları

FTM Licence Maker yalnızca lisans üretim bilgisayarında çalıştırılır.

Licence Maker için hedef güvenlik davranışları:

- Şifresiz private key kabul edilmemeli.
- Private key parola ile açılmalı.
- Parola bellekte gereğinden uzun tutulmamalı.
- Private key müşteri paketine dahil edilmemeli.
- Lisans üretim işlemi loglanmalı.
- Hatalı parola açık ama güvenli mesajla reddedilmeli.
- Public key fingerprint gösterilmeli.
- Üretilen lisans dosyası sadece output klasörüne yazılmalı.
- Kullanıcıya private key'in müşteriye verilmemesi gerektiği açıkça gösterilmeli.

---

## 8. Müşteri Kurulum USB Politikası

Müşteri kurulum USB'si düşük riskli olacak şekilde hazırlanmalıdır.

İçerebilir:

    FTM_Setup.exe
    FTM_Kurulum_Notlari.txt
    version.txt
    checksums.txt

İçeremez:

    FTM_Licence_Maker.exe
    ftm_license_ed25519_private.pem
    ftm_license_ed25519_private_encrypted.pem
    keys/
    tools/
    *.ftmlic
    license.json
    *.db
    *.sqlite
    *.sqlite3
    logs/
    backups/
    exports/
    source/
    .env

Müşteri kurulum USB'si kaybolursa:

- Kurulum dosyası yayılmış olabilir.
- Private key bulunmadığı için lisans sistemi kırılmış sayılmaz.
- Yine de USB içeriği kontrol edilmeli.
- Kurulum dosyasının sürümü ve checksum bilgisi kayıt altına alınmalıdır.

---

## 9. Lisans Transfer USB Politikası

Lisans transfer USB'si, yalnızca oluşturulmuş lisans dosyasını müşteriye aktarmak için kullanılabilir.

İçerebilir:

    ABC_MARKET_annual_FTM-XXXX-XXXX-XXXX-XXXX-XXXX_20260513.ftmlic

İçeremez:

    FTM_Licence_Maker.exe
    keys/
    *.pem
    *.key
    tools/
    source/
    *.db
    license.json

Transfer tamamlandıktan sonra:

- Lisans dosyası müşteri bilgisayarına yüklenir.
- Transfer USB'si kontrol edilir.
- Gerekiyorsa USB temizlenir.
- Üretilen lisansın bir kopyası Mustafa'nın lisans arşivinde tutulur.

---

## 10. Release Paketi Güvenlik Kontrolü

Müşteri release paketi hazırlanmadan önce güvenlik kontrolü yapılmalıdır.

Kontrol edilecek yasaklı dosya ve klasörler:

    *.pem
    *.key
    *.p12
    *.pfx
    *.ftmlic
    license.json
    device_identity.json
    license_clock_state.json
    *.db
    *.sqlite
    *.sqlite3
    .env
    logs/
    backups/
    exports/
    keys/
    tools/
    source/
    FTM_Licence_Maker.exe

Beklenen sonuç:

    OK - Müşteri paketi güvenli görünüyor.

Riskli sonuç:

    FAIL - Müşteri paketinde hassas dosya bulundu.

FAIL sonucu alınırsa paket müşteriye götürülmez.

---

## 11. Lisans Üretim Logu

Her lisans üretimi kayıt altına alınmalıdır.

Log içinde bulunabilecek bilgiler:

- Üretim tarihi
- Firma adı
- Cihaz kodu
- Lisans tipi
- Başlangıç tarihi
- Bitiş tarihi
- Oluşturulan dosya adı
- Public key fingerprint
- Licence Maker sürümü

Log içinde bulunmaması gereken bilgiler:

- Private key içeriği
- Private key parolası
- Ham sistem kimliği
- Müşterinin gereksiz kişisel verileri
- Şifreler

Örnek log alanları:

    generated_at
    company_name
    device_code
    license_type
    starts_at
    expires_at
    output_file
    public_key_fingerprint
    maker_version

---

## 12. USB Kaybolursa Ne Yapılacak?

### 12.1 Müşteri Kurulum USB'si Kaybolursa

Eğer USB içinde sadece müşteri kurulum paketi varsa:

- Kritik lisans anahtarı sızmış sayılmaz.
- Yeni kurulum USB'si hazırlanır.
- Eski USB içeriği ve sürümü not edilir.
- Eğer kurulum dosyası public hale geldiyse lisanssız veri girişi engeli kontrol edilir.

### 12.2 Lisans Transfer USB'si Kaybolursa

Eğer USB içinde sadece `.ftmlic` dosyası varsa:

- İlgili lisans sadece bağlı olduğu cihazda çalışır.
- Yine de hangi müşteriye ait olduğu kayıt altına alınır.
- Müşteri bilgilendirilir.
- Gerekirse yeni lisans oluşturulur.

### 12.3 Private Key İçeren Ortam Kaybolursa

Bu en kritik senaryodur.

Aşağıdaki işlemler yapılmalıdır:

1. Private key sızıntısı şüphesi kabul edilir.
2. Mevcut key çifti riskli kabul edilir.
3. Yeni Ed25519 key çifti oluşturma planı hazırlanır.
4. Uygulama public key güncelleme süreci planlanır.
5. Eski lisansların geçiş stratejisi belirlenir.
6. Yeni lisans üretim süreci başlatılır.
7. Olay kayıt altına alınır.

Private key içeren ortamın kaybolması P0 güvenlik olayıdır.

---

## 13. Kişisel Bilgisayar Güvenlik Kuralları

Mustafa'nın lisans üretim bilgisayarı için önerilen minimum güvenlik kuralları:

- Windows kullanıcı şifresi güçlü olmalı.
- Disk şifreleme aktif olmalı.
- Antivirüs / Windows Defender aktif olmalı.
- Bilinmeyen USB'ler bu bilgisayara takılmamalı.
- Private key klasörü standart kullanıcıların erişimine kapalı olmalı.
- Licence Maker klasörü düzenli yedeklenmeli.
- Bilgisayar ortak kullanımda bırakılmamalı.
- Uzak masaüstü / AnyDesk / TeamViewer gibi erişimler kontrollü kullanılmalı.
- Private key parolası tarayıcıya veya düz metin dosyasına kaydedilmemeli.
- Lisans üretim klasörü bulut senkronizasyon dışında tutulmalı.

---

## 14. Private Key Parola Kuralları

Private key parolası güçlü olmalıdır.

Minimum öneri:

- En az 16 karakter
- Büyük harf
- Küçük harf
- Rakam
- Özel karakter
- Tahmin edilemeyen ifade
- Başka sistemlerde kullanılmayan parola

Parola saklama önerisi:

- Güvenilir parola yöneticisi
- Fiziksel kapalı zarf
- Güvenli kasa
- Tek kopyaya bağlı kalmayan kontrollü yedek

Parola saklanmaması gereken yerler:

- Masaüstü not dosyası
- WhatsApp mesajı
- E-posta
- GitHub
- Kod dosyası
- README
- Telefon notları
- Tarayıcı otomatik doldurma

---

## 15. Key Rotation Planı

Private key sızıntısı şüphesi oluşursa key rotation gerekir.

Key rotation şu anlama gelir:

- Yeni Ed25519 private/public key çifti oluşturulur.
- Uygulama içine yeni public key eklenir.
- Yeni sürüm yayınlanır.
- Yeni lisanslar yeni private key ile üretilir.
- Eski lisanslar için geçiş planı yapılır.

Bu işlem zor olduğu için private key ilk günden sıkı korunmalıdır.

---

## 16. Satış Günü Kontrol Listesi

Müşteriye gitmeden önce:

- FTM kurulum paketi hazır mı?
- Kurulum USB'sinde yasaklı dosya yok mu?
- Checksum dosyası var mı?
- Version dosyası var mı?
- Kişisel bilgisayarda Licence Maker çalışıyor mu?
- Private key dosyası şifreli mi?
- Private key parolası biliniyor mu?
- Output klasörü hazır mı?
- Lisans transfer yöntemi hazır mı?
- İlk yedek alma adımı planlandı mı?

Müşteri yanında:

- FTM kurulumu yapıldı mı?
- Cihaz kodu doğru alındı mı?
- Lisans Mustafa'nın kişisel bilgisayarında üretildi mi?
- Sadece `.ftmlic` dosyası müşteri bilgisayarına aktarıldı mı?
- Lisans uygulamada doğrulandı mı?
- Veri girişi açıldı mı?
- İlk yedek alındı mı?
- Müşteriye yedekleme uyarısı anlatıldı mı?

Kurulumdan sonra:

- Üretilen lisans dosyası arşivlendi mi?
- Lisans üretim logu kontrol edildi mi?
- Müşteri adı / cihaz kodu kayıt altına alındı mı?
- Transfer USB'si temizlendi mi?
- Kurulum notu güncellendi mi?

---

## 17. Bu Politikanın Uygulanacağı Dosyalar

Bu politika özellikle aşağıdaki alanları ilgilendirir:

    tools/ftm_license_maker.py
    tools/encrypt_license_private_key.py
    tools/check_release_package_safety.py
    app/services/license_service.py
    app/services/license_public_key.py
    app/core/runtime_paths.py
    README.md
    docs/QUALITY_BASELINE.md
    docs/LICENSE_SECURITY_POLICY.md

---

## 18. ADIM 2 Teknik Yol Haritası

Bu güvenlik politikası kabul edildikten sonra uygulanacak teknik adımlar:

### ADIM 2.2 - Private Key Encryption Helper

Yeni dosya:

    tools/encrypt_license_private_key.py

Amaç:

- Mevcut şifresiz private key dosyasını alır.
- Kullanıcıdan güçlü parola ister.
- Şifreli private key dosyası üretir.
- Public key fingerprint gösterir.
- Şifresiz key dosyasının kalıcı kullanımda tutulmaması gerektiğini bildirir.

### ADIM 2.3 - Licence Maker Güvenlik Güncellemesi

Etkilenecek dosya:

    tools/ftm_license_maker.py

Amaç:

- Şifreli private key kullanmak.
- Parola istemek.
- Şifresiz private key'i reddetmek.
- Lisans üretim logu yazmak.
- Güvenlik uyarılarını göstermek.

### ADIM 2.4 - Release Package Safety Checker

Yeni dosya:

    tools/check_release_package_safety.py

Amaç:

- Müşteri kurulum klasörünü taramak.
- Hassas dosya sızıntısı varsa build/release sürecini durdurmak.
- Temiz paket için OK sonucu vermek.

### ADIM 2.5 - Kalite Skoru Güncellemesi

Etkilenecek dosya:

    docs/QUALITY_BASELINE.md

Amaç:

- Güvenlik, lisanslama ve paketleme puanlarını kanıtlı şekilde güncellemek.
- Yapılan işlerin tarih ve test sonuçlarını kayıt altına almak.

---

## 19. Sonuç

FTM lisans güvenliği için ana prensip şudur:

**Private key müşteriye gitmez. Licence Maker müşteri bilgisayarında çalışmaz. Lisans sadece Mustafa'nın kişisel bilgisayarında üretilir. Müşteriye yalnızca imzalı lisans dosyası verilir.**

Bu prensip korunduğu sürece FTM'nin ticari lisans kontrolü güçlü kalır.

Private key sızarsa lisans sistemi ticari değerini kaybeder. Bu nedenle private key, ürünün kasasıdır. Kasa müşteriye götürülmez; müşteriye sadece onun kapısını açan imzalı anahtar verilir.

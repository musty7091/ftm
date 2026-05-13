# FTM Kalite Skor Defteri

Bu dosya, **FTM Finans Takip Merkezi** projesinin satışa hazırlık seviyesini ölçmek, takip etmek ve geliştirme sürecini kontrol altında tutmak için hazırlanmıştır.

Amaç, projeyi sadece “çalışıyor” seviyesinde bırakmak değil; güvenli, test edilebilir, desteklenebilir ve ticari olarak satılabilir bir masaüstü finans uygulaması haline getirmektir.

---

## 1. Başlangıç Tarihi

İlk kalite baz çizgisi:

```text
13 Mayıs 2026
```

Bu tarih itibarıyla proje çalışır durumdadır; ancak satış öncesi kalite, güvenlik, kurulum, lisanslama, yedekleme, restore, paketleme ve kullanıcı deneyimi açısından güçlendirme çalışmaları devam etmektedir.

---

## 2. Başlangıç Skorları

| Başlık | Başlangıç Puanı |
|---|---:|
| Teknik temel | 76 / 100 |
| Finansal doğruluk | 78 / 100 |
| Güvenlik | 68 / 100 |
| Kullanıcı deneyimi | 65 / 100 |
| Raporlama | 72 / 100 |
| Lisanslama / ticari kontrol | 74 / 100 |
| Paketleme / dağıtım | 58 / 100 |
| Genel satışa hazır olma | 63 / 100 |

---

## 3. Güncel Skorlar

Son güncelleme:

```text
13 Mayıs 2026 - ADIM 2.5
```

| Başlık | Başlangıç | Güncel | Değişim |
|---|---:|---:|---:|
| Teknik temel | 76 / 100 | 76 / 100 | 0 |
| Finansal doğruluk | 78 / 100 | 78 / 100 | 0 |
| Güvenlik | 68 / 100 | 76 / 100 | +8 |
| Kullanıcı deneyimi | 65 / 100 | 65 / 100 | 0 |
| Raporlama | 72 / 100 | 72 / 100 | 0 |
| Lisanslama / ticari kontrol | 74 / 100 | 83 / 100 | +9 |
| Paketleme / dağıtım | 58 / 100 | 65 / 100 | +7 |
| Genel satışa hazır olma | 63 / 100 | 68 / 100 | +5 |

Bu güncelleme, lisans private key güvenliği ve müşteri release paketi güvenlik kontrolü tarafında tamamlanan kanıtlı işler nedeniyle yapılmıştır.

---

## 4. Skorların Anlamı

| Puan Aralığı | Anlam |
|---:|---|
| 0 - 39 | Kritik seviyede eksik. Ticari kullanım için uygun değil. |
| 40 - 59 | Çalışan ama riskli seviye. Demo dışında kullanılmamalı. |
| 60 - 69 | Temel yapı var; satış öncesi önemli eksikler devam ediyor. |
| 70 - 79 | Pilot müşteri için yaklaşan seviye. Kontrollü kullanım düşünülebilir. |
| 80 - 89 | Güçlü ürünleşme seviyesi. Satış öncesi güven artar. |
| 90 - 100 | Profesyonel ve sürdürülebilir ticari ürün seviyesi. |

---

## 5. Genel Değerlendirme

FTM, mevcut durumda güçlü bir teknik temele sahiptir.

Olumlu taraflar:

- SQLite local desktop mimarisi netleşmiştir.
- Runtime dosyaları kullanıcı klasöründe tutulmaktadır.
- Para hesaplarında Decimal yaklaşımı benimsenmiştir.
- Kritik işlemler için audit log altyapısı vardır.
- Lisanslama Ed25519 imzalı lisans yapısına geçmiştir.
- DB schema v8 seviyesine ulaşmıştır.
- Kredi kartı ve limitli hesap modülleri gelişmiştir.
- Excel rapor altyapısı genişletilmiştir.
- Lisans üretimi encrypted private key kullanımına geçirilmiştir.
- Müşteri release paketi için hassas dosya sızıntı kontrol aracı eklenmiştir.

Satış öncesi dikkat isteyen taraflar:

- Şifresiz eski private key günlük kullanımdan kesin olarak kaldırılmalıdır.
- Fresh install testi standart hale getirilmelidir.
- Backup / restore roundtrip testi kanıtlanmalıdır.
- Release paketinin gerçek build çıktısı üzerinde güvenlik kontrolü yapılmalıdır.
- Build / EXE üretim standardı netleştirilmelidir.
- Kredi kartı ve limitli hesap modülleri için kritik finans testleri artırılmalıdır.
- Kullanıcı deneyimi ve hata mesajları pilot müşteri seviyesine yükseltilmelidir.

---

## 6. Kategori Bazlı Kalite Kriterleri

### 6.1 Teknik Temel

Başlangıç puanı:

```text
76 / 100
```

Güncel puan:

```text
76 / 100
```

Puanı artıracak kriterler:

- Resmi uygulama giriş komutu netleşmeli.
- Fresh install akışı test edilmeli.
- Migration sistemi temiz veritabanı ve eski veritabanı üzerinde doğrulanmalı.
- Runtime klasörleri her senaryoda güvenli şekilde oluşmalı.
- Sistem sağlık kontrolü net ve anlaşılır olmalı.
- Kod içinde eski PostgreSQL / yeni SQLite karışıklığı azaltılmalı.
- Gereksiz bağımlılıklar gözden geçirilmeli.
- Build standardı tekrar üretilebilir hale getirilmeli.

Hedef:

```text
85 / 100
```

---

### 6.2 Finansal Doğruluk

Başlangıç puanı:

```text
78 / 100
```

Güncel puan:

```text
78 / 100
```

Puanı artıracak kriterler:

- Para hesaplarında float kullanılmadığı doğrulanmalı.
- Decimal dönüşümleri tek standarttan yürümeli.
- Banka hareketi bakiye kontrolü test edilmeli.
- Kredi kartı limit aşımı testi yapılmalı.
- Kredi kartı ödeme / iptal senaryoları test edilmeli.
- Limitli hesap ana para / faiz / masraf dağılımı test edilmeli.
- Çek ödeme ve tahsilat senaryoları test edilmeli.
- POS beklenen / gerçekleşen yatış tutarlılığı test edilmeli.
- Raporlardaki toplamlar kaynak hareketlerle karşılaştırılmalı.

Hedef:

```text
88 / 100
```

---

### 6.3 Güvenlik

Başlangıç puanı:

```text
68 / 100
```

Güncel puan:

```text
76 / 100
```

Puan artışının nedeni:

- Lisans güvenlik politikası yazıldı.
- Lisans üretimi Mustafa'nın kişisel bilgisayarı merkezli operasyon modeline bağlandı.
- Private key'in müşteri bilgisayarında çalıştırılmaması kuralı netleşti.
- Şifresiz Ed25519 private key için encrypted PEM üretim aracı eklendi.
- Encrypted private key başarıyla oluşturuldu.
- Encrypted private key parola ile doğrulandı.
- Licence Maker encrypted private key kullanacak şekilde güncellendi.
- Licence Maker private key parolası olmadan lisans üretmeyecek hale getirildi.
- Müşteri release paketi için hassas dosya sızıntı kontrol aracı eklendi.
- Temiz ve riskli test paketleriyle safety checker davranışı doğrulandı.

Devam eden güvenlik işleri:

- Şifresiz eski private key dosyası günlük kullanımdan kaldırılmalı.
- Secret scanning yapılmalı.
- Backup / restore güvenlik testleri yapılmalı.
- Audit log bütünlük kontrolü ileri fazda güçlendirilmeli.
- Gerçek release klasörü üzerinde safety checker çalıştırılmalı.

Hedef:

```text
82 / 100
```

---

### 6.4 Kullanıcı Deneyimi

Başlangıç puanı:

```text
65 / 100
```

Güncel puan:

```text
65 / 100
```

Puanı artıracak kriterler:

- İlk kurulum ekranı sade ve anlaşılır olmalı.
- Lisans yok / geçersiz / süresi dolmuş durumları net anlatılmalı.
- Restore ve yedekleme ekranları kullanıcıyı doğru yönlendirmeli.
- Küçük ekranlarda arayüz taşmamalı.
- Hata mesajları teknik panik yaratmamalı.
- Rapor export sonrası kullanıcı dosyayı kolay bulmalı.
- Kritik işlemlerde onay mesajları açık olmalı.
- Günlük kullanım akışı muhasebeci mantığıyla sadeleşmeli.

Not:

Licence Maker arayüzünde encrypted key ve parola akışı iyileştirildi; ancak ana uygulama kullanıcı deneyimi henüz ayrı bir turda ölçülmediği için bu kategori puanı artırılmamıştır.

Hedef:

```text
80 / 100
```

---

### 6.5 Raporlama

Başlangıç puanı:

```text
72 / 100
```

Güncel puan:

```text
72 / 100
```

Puanı artıracak kriterler:

- Excel rapor sayfaları kontrol edilmeli.
- Kredi kartı ve limitli hesap raporları finansal olarak doğrulanmalı.
- İptal edilen kayıtların raporda nasıl gösterileceği standartlaşmalı.
- Para birimi ayrımı net olmalı.
- PDF rapor tasarımı kurumsal hale getirilmeli.
- Raporlarda toplamlar güvenilir şekilde hesaplanmalı.
- Rapor dosya adları tarih ve içerik bilgisi taşımalı.
- Export klasörü kullanıcıya açık şekilde gösterilmeli.

Hedef:

```text
84 / 100
```

---

### 6.6 Lisanslama / Ticari Kontrol

Başlangıç puanı:

```text
74 / 100
```

Güncel puan:

```text
83 / 100
```

Puan artışının nedeni:

- Lisans üretimi artık kişisel lisans bilgisayarı operasyonuna bağlandı.
- Müşteri bilgisayarında Licence Maker çalıştırılmaması kuralı yazılı hale getirildi.
- Private key müşteri paketinden ayrıldı.
- Private key encrypted PEM formatına geçirildi.
- Licence Maker encrypted key ve parola ile lisans üretir hale getirildi.
- Eski aktif lisans dosyaları temizlendi.
- Uygulama lisanssız durumda `missing | Lisans Yok | False | False` sonucunu verdi.
- Yeni lisans encrypted private key ile üretildi.
- Yeni lisans uygulamada başarıyla doğrulandı.
- Lisans üretimi log dosyasına kayıt atacak hale getirildi.

Devam eden lisanslama işleri:

- Licence Maker'ın EXE paketlemesi ayrıca hazırlanmalı.
- Lisans üretim logu gerçek müşteri senaryosunda kontrol edilmeli.
- Key rotation planı ileride teknik olarak desteklenmeli.
- Lisans yükleme ekranı ana uygulamada müşteri dostu şekilde tekrar gözden geçirilmeli.

Hedef:

```text
88 / 100
```

---

### 6.7 Paketleme / Dağıtım

Başlangıç puanı:

```text
58 / 100
```

Güncel puan:

```text
65 / 100
```

Puan artışının nedeni:

- Müşteri paketi ile lisans üretici paketinin ayrılması gerektiği yazılı hale getirildi.
- Müşteri paketinde bulunmaması gereken dosyalar net tanımlandı.
- `tools/check_release_package_safety.py` aracı eklendi.
- Araç, temiz klasörde OK sonucu verecek şekilde test edildi.
- Araç, private key içeren riskli klasörde FAIL sonucu verecek şekilde test edildi.
- Olmayan klasör için ERROR vererek sessiz geçmemesi doğrulandı.

Devam eden paketleme işleri:

- Resmi build komutu netleşmeli.
- Gerçek PyInstaller build klasörü üzerinde safety checker çalıştırılmalı.
- Müşteri kurulum USB şablonu oluşturulmalı.
- Licence Maker müşteri paketinden kesin olarak ayrı tutulmalı.
- Build sonrası checksum üretimi standart hale getirilmeli.

Hedef:

```text
78 / 100
```

---

### 6.8 Genel Satışa Hazır Olma

Başlangıç puanı:

```text
63 / 100
```

Güncel puan:

```text
68 / 100
```

Puan artışının nedeni:

- Lisans private key güvenliği ciddi şekilde güçlendirildi.
- Lisans üretim operasyonu müşteri bilgisayarından ayrıldı.
- Yeni encrypted key ile lisans üretimi başarıyla test edildi.
- Uygulamanın eski lisanslardan temizlenip yeni lisansla doğrulandığı görüldü.
- Müşteri release paketinde hassas dosya sızıntısını yakalayacak araç eklendi.

Devam eden satış öncesi ana işler:

- Fresh install testi
- Backup / restore roundtrip testi
- Migration v8 doğrulama
- Resmi çalıştırma komutu
- Resmi build komutu
- Gerçek release paketi oluşturma ve safety checker testi
- Kredi kartı kritik testleri
- Limitli hesap kritik testleri

Hedef:

```text
80 / 100
```

---

## 7. ADIM 2 Kanıtları

### 7.1 Encrypted Private Key Oluşturma

Komut:

```powershell
python tools\encrypt_license_private_key.py --input "C:\FTM_PRIVATE_KEYS\ftm_license_ed25519_private.pem" --output "C:\FTM_LICENSE_ADMIN\keys\ftm_license_ed25519_private_encrypted.pem"
```

Başarılı çıktı özeti:

```text
OK - Encrypted private key başarıyla oluşturuldu.
```

Fingerprint:

```text
73D2C269-1E5816AF-F4FC3669-D5187EB2-13D88335-EFF9A505-C9AF07C7-F0AD3C7A
```

### 7.2 Encrypted Private Key Doğrulama

Komut:

```powershell
python tools\encrypt_license_private_key.py --verify "C:\FTM_LICENSE_ADMIN\keys\ftm_license_ed25519_private_encrypted.pem"
```

Başarılı çıktı özeti:

```text
OK - Encrypted private key parola ile başarıyla açıldı.
```

Fingerprint:

```text
73D2C269-1E5816AF-F4FC3669-D5187EB2-13D88335-EFF9A505-C9AF07C7-F0AD3C7A
```

### 7.3 Eski Lisansları Temizleme

`%LOCALAPPDATA%\FTM\config` içindeki eski aktif lisans dosyaları silindi.

Korunması gereken dosya:

```text
license_clock_state.json
```

Doğrulama sonucu:

```text
missing | Lisans Yok | False | False | Lisans dosyası bulunamadı. Uygulama açılabilir ancak veri girişi için imzalı lisans gereklidir.
```

### 7.4 Yeni Lisans Üretimi ve Doğrulama

Yeni lisans, encrypted private key ile üretildi.

Durum:

```text
Başarılı
```

Not:

7 günlük test lisansı kullanılırsa lisans durumu `expiring_soon` olabilir. Bu başarısızlık değildir; 30 günlük uyarı eşiği nedeniyle normaldir.

### 7.5 Release Package Safety Checker

Eklenen dosya:

```text
tools/check_release_package_safety.py
```

Temiz klasör testi:

```powershell
python tools\check_release_package_safety.py --path "C:\FTM_CUSTOMER_INSTALL"
```

Beklenen sonuç:

```text
SONUÇ: OK - Müşteri paketi güvenli görünüyor.
```

Riskli klasör testi:

```powershell
python tools\check_release_package_safety.py --path "C:\FTM_CUSTOMER_INSTALL_BAD"
```

Beklenen sonuç:

```text
SONUÇ: FAIL - Müşteri paketinde hassas veya yasaklı dosya bulundu.
```

Olmayan klasör testi:

```text
SONUÇ: ERROR
Kontrol edilecek yol bulunamadı.
```

Bu davranış doğru kabul edilmiştir; araç olmayan klasörü sessizce geçmiş saymaz.

---

## 8. P0 - Satıştan Önce Mutlaka Çözülmesi Gerekenler

| Durum | İş | Açıklama |
|---|---|---|
| Tamamlandı | README profesyonel taslak | Projenin güncel durumu için yeni README hazırlandı. |
| Tamamlandı | Kalite skor defteri | Başlangıç skorları ve kalite hedefleri kayıt altına alındı. |
| Tamamlandı | Lisans güvenlik politikası | Private key, müşteri paketi ve lisans üretim kuralları yazılı hale getirildi. |
| Tamamlandı | Encrypted private key helper | Şifresiz private key'den encrypted PEM üreten araç eklendi ve test edildi. |
| Tamamlandı | Licence Maker encrypted key geçişi | Licence Maker encrypted private key ve parola ile çalışacak hale getirildi. |
| Tamamlandı | Release package safety checker | Müşteri paketinde hassas dosya sızıntısı aracı eklendi ve test edildi. |
| Devam Ediyor | Şifresiz private key günlük kullanımdan kaldırma | Encrypted key çalışıyor; eski şifresiz key günlük kullanımdan kesin kaldırılmalı. |
| Bekliyor | Fresh install testi | Temiz bilgisayarda ilk kurulum ve ilk açılış doğrulanmalı. |
| Bekliyor | Backup / restore roundtrip testi | Yedek al, restore et, veritabanını doğrula. |
| Bekliyor | Gerçek release paketi hijyeni | Gerçek build çıktısı üzerinde safety checker çalıştırılmalı. |
| Bekliyor | Migration v8 doğrulama | Yeni ve eski veritabanı senaryolarında schema v8 doğrulanmalı. |
| Bekliyor | Resmi çalıştırma komutu | Geliştirme ortamı için tek giriş komutu belirlenmeli. |
| Bekliyor | Resmi build komutu | PyInstaller build süreci sabitlenmeli. |
| Bekliyor | Secret scanning | Public repo geçmişi hassas bilgi açısından taranmalı. |

---

## 9. P1 - Pilot Müşteriden Önce Çözülmesi Gerekenler

| Durum | İş | Açıklama |
|---|---|---|
| Bekliyor | Kredi kartı testleri | Limit, harcama, ödeme, iptal senaryoları test edilmeli. |
| Bekliyor | Limitli hesap testleri | Ana para, faiz, masraf ve ödeme dağılımı test edilmeli. |
| Bekliyor | Çek testleri | Yazılan ve alınan çek süreçleri uçtan uca test edilmeli. |
| Bekliyor | POS testleri | Beklenen ve gerçekleşen yatışlar doğrulanmalı. |
| Bekliyor | Excel rapor doğrulama | Rapor sayfaları ve toplamlar kontrol edilmeli. |
| Bekliyor | PDF rapor doğrulama | Kurumsal rapor çıktısı test edilmeli. |
| Bekliyor | Küçük ekran UI testi | Laptop ekranlarında taşma / sıkışma olmamalı. |
| Bekliyor | Hata mesajı standardı | Kullanıcıya sade, net ve güven veren mesajlar gösterilmeli. |
| Bekliyor | Destek paketi | Log, sürüm, runtime yol bilgisi ve sistem durumu destek için paketlenmeli. |

---

## 10. P2 - Ürünü Güçlendiren İyileştirmeler

| Durum | İş | Açıklama |
|---|---|---|
| Bekliyor | Audit export | Kritik işlem geçmişi Excel/PDF olarak dışa aktarılabilmeli. |
| Bekliyor | Audit bütünlük kontrolü | Audit log değişikliklerine karşı hash-chain veya benzeri yapı değerlendirilmeli. |
| Bekliyor | Otomatik yedek hatırlatma | Kullanıcı düzenli yedek almaya yönlendirilmeli. |
| Bekliyor | Demo veri seti | Satış demo ve test senaryoları için örnek veri hazırlanmalı. |
| Bekliyor | Kullanıcı kılavuzu | Müşteri için sade kullanım dokümanı hazırlanmalı. |
| Bekliyor | Kurumsal rapor şablonları | PDF ve Excel rapor tasarımları güçlendirilmeli. |

---

## 11. P3 - İleri Seviye / Gelecek Faz

| Durum | İş | Açıklama |
|---|---|---|
| Bekliyor | DB encryption | SQLite veritabanı dosyası şifreleme seçeneği değerlendirilmeli. |
| Bekliyor | Kod imzalı installer | Windows güven uyarıları azaltılmalı. |
| Bekliyor | Otomatik güncelleme | Yeni sürümlerin kontrollü dağıtımı sağlanmalı. |
| Bekliyor | Çok firma desteği | Tek uygulamada birden fazla işletme yönetimi değerlendirilmeli. |
| Bekliyor | Bulut yedekleme | İsteğe bağlı güvenli bulut yedekleme opsiyonu değerlendirilmeli. |
| Bekliyor | Lisans yönetim paneli | Lisans üretimi ve müşteri takibi merkezi panelden yapılabilir hale getirilmeli. |

---

## 12. Güncelleme Geçmişi

| Tarih | Sürüm / Aşama | Değişiklik | Etki |
|---|---|---|---|
| 2026-05-13 | Başlangıç | İlk kalite skorları kayıt altına alındı. | Ölçülebilir satışa hazırlık takibi başladı. |
| 2026-05-13 | ADIM 1 | `docs/QUALITY_BASELINE.md` oluşturuldu. | Kalite, güvenlik, paketleme ve satışa hazırlık hedefleri netleşti. |
| 2026-05-13 | ADIM 2.1 | `docs/LICENSE_SECURITY_POLICY.md` oluşturuldu. | Lisans üretim operasyonu yazılı güvenlik politikasına bağlandı. |
| 2026-05-13 | ADIM 2.2 | `tools/encrypt_license_private_key.py` eklendi. | Şifresiz private key'den encrypted PEM üretimi sağlandı. |
| 2026-05-13 | ADIM 2.3 | `tools/ftm_license_maker.py` encrypted key kullanacak şekilde güncellendi. | Licence Maker private key parolası olmadan lisans üretemez hale geldi. |
| 2026-05-13 | ADIM 2.4 | `tools/check_release_package_safety.py` eklendi. | Müşteri paketinde hassas dosya sızıntısı kontrol edilebilir hale geldi. |
| 2026-05-13 | ADIM 2.5 | Kalite skorları güncellendi. | Güvenlik, lisanslama, paketleme ve genel satışa hazırlık puanları kanıtlı şekilde artırıldı. |

---

## 13. Skor Güncelleme Kuralları

Skorlar rastgele artırılmaz.

Bir puanın artması için aşağıdaki şartlardan en az biri sağlanmalıdır:

- İlgili risk tamamen kapatılmış olmalı.
- Test komutu çalıştırılmış ve sonucu doğrulanmış olmalı.
- Dokümantasyon güncellenmiş olmalı.
- Release / kurulum / restore gibi süreçler gerçek dosyalarla denenmiş olmalı.
- Kritik finansal senaryo uçtan uca doğrulanmış olmalı.
- Güvenlik riski teknik olarak azaltılmış olmalı.
- Müşteri kullanımında sorun çıkaracak belirsizlik giderilmiş olmalı.

Skor artırımı yapılırken şu bilgiler yazılmalıdır:

```text
Tarih:
İlgili kategori:
Eski puan:
Yeni puan:
Yapılan iş:
Etkilenen dosyalar:
Test:
Sonuç:
```

---

## 14. ADIM 2 Skor Güncelleme Kaydı

Tarih:

```text
2026-05-13
```

İlgili kategoriler:

```text
Güvenlik
Lisanslama / ticari kontrol
Paketleme / dağıtım
Genel satışa hazır olma
```

Eski puanlar:

```text
Güvenlik: 68
Lisanslama / ticari kontrol: 74
Paketleme / dağıtım: 58
Genel satışa hazır olma: 63
```

Yeni puanlar:

```text
Güvenlik: 76
Lisanslama / ticari kontrol: 83
Paketleme / dağıtım: 65
Genel satışa hazır olma: 68
```

Yapılan iş:

```text
Lisans üretim private key güvenliği encrypted PEM modeline geçirildi.
Licence Maker encrypted private key ve parola ile çalışacak hale getirildi.
Müşteri paketinde hassas dosya sızıntılarını yakalayan safety checker eklendi.
Eski aktif lisanslar temizlenip yeni lisans encrypted private key ile üretildi ve doğrulandı.
```

Etkilenen dosyalar:

```text
docs/LICENSE_SECURITY_POLICY.md
tools/encrypt_license_private_key.py
tools/ftm_license_maker.py
tools/check_release_package_safety.py
docs/QUALITY_BASELINE.md
```

Test:

```text
Encrypted private key oluşturma testi
Encrypted private key doğrulama testi
Licence Maker ile yeni lisans üretimi
Eski lisansların temizlenmesi sonrası missing lisans kontrolü
Yeni lisansın check_license ile doğrulanması
Release safety checker temiz klasör testi
Release safety checker riskli klasör testi
```

Sonuç:

```text
Başarılı
```

---

## 15. Mevcut Hedef

Kısa vadeli hedef:

```text
Genel satışa hazır olma: 68 / 100 -> 75 / 100
```

Bu hedefe ulaşmak için öncelikli işler:

1. Fresh install testi
2. Backup / restore roundtrip testi
3. Migration v8 doğrulama
4. Resmi çalıştırma komutu
5. Resmi build komutu
6. Gerçek release paketi üzerinde safety checker testi
7. Kredi kartı kritik testleri
8. Limitli hesap kritik testleri
9. Secret scanning
10. Şifresiz eski private key'in günlük kullanımdan kesin kaldırılması

Orta vadeli hedef:

```text
Genel satışa hazır olma: 80 / 100
```

Bu seviyeye ulaşıldığında FTM, kontrollü pilot müşteri kurulumuna daha güvenli şekilde hazırlanmış kabul edilir.

---

## 16. Özet

Bu dosya FTM projesinin kalite defteridir.

Buradaki puanlar, hedefler ve yapılacak işler düzenli olarak güncellenmelidir.

ADIM 2 sonunda FTM'nin lisans güvenliği önemli ölçüde güçlenmiştir. Private key artık encrypted PEM formatına alınmış, Licence Maker parola ile çalışacak hale getirilmiş ve müşteri paketinde hassas dosya sızıntısını yakalayacak kontrol aracı eklenmiştir.

Amaç; projeyi aceleyle satmak değil, güven veren, desteklenebilir, finansal olarak doğru çalışan ve ticari değeri olan bir masaüstü finans uygulamasına dönüştürmektir.

# FTM Kalite Skor Defteri

Bu dosya, **FTM Finans Takip Merkezi** projesinin satışa hazırlık seviyesini ölçmek, takip etmek ve geliştirme sürecini kontrol altında tutmak için hazırlanmıştır.

Amaç, projeyi sadece “çalışıyor” seviyesinde bırakmak değil; güvenli, test edilebilir, desteklenebilir ve ticari olarak satılabilir bir masaüstü finans uygulaması haline getirmektir.

---

## 1. Başlangıç Tarihi

İlk kalite baz çizgisi:

13 Mayıs 2026

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

## 3. Skorların Anlamı

| Puan Aralığı | Anlam |
|---:|---|
| 0 - 39 | Kritik seviyede eksik. Ticari kullanım için uygun değil. |
| 40 - 59 | Çalışan ama riskli seviye. Demo dışında kullanılmamalı. |
| 60 - 69 | Temel yapı var; satış öncesi önemli eksikler devam ediyor. |
| 70 - 79 | Pilot müşteri için yaklaşan seviye. Kontrollü kullanım düşünülebilir. |
| 80 - 89 | Güçlü ürünleşme seviyesi. Satış öncesi güven artar. |
| 90 - 100 | Profesyonel ve sürdürülebilir ticari ürün seviyesi. |

---

## 4. Genel Değerlendirme

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

Satış öncesi dikkat isteyen taraflar:

- Private key güvenliği kesin kurala bağlanmalıdır.
- Fresh install testi standart hale getirilmelidir.
- Backup / restore roundtrip testi kanıtlanmalıdır.
- Release paketinin hassas dosya sızdırmadığı doğrulanmalıdır.
- Build / EXE üretim standardı netleştirilmelidir.
- Kredi kartı ve limitli hesap modülleri için kritik finans testleri artırılmalıdır.
- Kullanıcı deneyimi ve hata mesajları pilot müşteri seviyesine yükseltilmelidir.

---

## 5. Kategori Bazlı Kalite Kriterleri

### 5.1 Teknik Temel

Başlangıç puanı:

76 / 100

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

85 / 100

---

### 5.2 Finansal Doğruluk

Başlangıç puanı:

78 / 100

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

88 / 100

---

### 5.3 Güvenlik

Başlangıç puanı:

68 / 100

Puanı artıracak kriterler:

- Private key repo dışında tutulmalı.
- Private key release paketine girmemeli.
- Lisans üretici araç müşteri paketinden ayrılmalı.
- Secret scanning yapılmalı.
- Şifre politikası test edilmeli.
- Login lockout testi yapılmalı.
- Audit log kapsamı genişletilmeli.
- Restore işlemi kötü dosyaya karşı korunmalı.
- Runtime dosyalarının yanlışlıkla silinmesi veya bozulması durumunda güvenli hata mesajları verilmeli.
- Saat geri alma kontrolü test edilmeli.

Hedef:

82 / 100

---

### 5.4 Kullanıcı Deneyimi

Başlangıç puanı:

65 / 100

Puanı artıracak kriterler:

- İlk kurulum ekranı sade ve anlaşılır olmalı.
- Lisans yok / geçersiz / süresi dolmuş durumları net anlatılmalı.
- Restore ve yedekleme ekranları kullanıcıyı doğru yönlendirmeli.
- Küçük ekranlarda arayüz taşmamalı.
- Hata mesajları teknik panik yaratmamalı.
- Rapor export sonrası kullanıcı dosyayı kolay bulmalı.
- Kritik işlemlerde onay mesajları açık olmalı.
- Günlük kullanım akışı muhasebeci mantığıyla sadeleşmeli.

Hedef:

80 / 100

---

### 5.5 Raporlama

Başlangıç puanı:

72 / 100

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

84 / 100

---

### 5.6 Lisanslama / Ticari Kontrol

Başlangıç puanı:

74 / 100

Puanı artıracak kriterler:

- Ed25519 imzalı lisans akışı test edilmeli.
- Sahte imzalı lisans reddedilmeli.
- Farklı cihaz lisansı reddedilmeli.
- Süresi dolmuş lisans veri girişini engellemeli.
- Saat geri alma senaryosu test edilmeli.
- Private key müşteri paketinden kesin ayrılmalı.
- Licence Maker aracı ayrı ve güvenli süreçle yönetilmeli.
- Lisans yükleme ekranı müşteri açısından sade olmalı.

Hedef:

88 / 100

---

### 5.7 Paketleme / Dağıtım

Başlangıç puanı:

58 / 100

Puanı artıracak kriterler:

- Resmi build komutu netleşmeli.
- Tekrarlanabilir PyInstaller build script oluşturulmalı.
- Build sonrası hassas dosya kontrolü yapılmalı.
- EXE başka bir bilgisayarda test edilmeli.
- Runtime klasörleri müşteri bilgisayarında doğru oluşmalı.
- Private key, DB, lisans, log, export ve yedek dosyaları pakete girmemeli.
- Marka ikonları ve rapor logoları pakete doğru dahil edilmeli.
- Kurulum / güncelleme / kaldırma akışı yazılı hale getirilmeli.

Hedef:

78 / 100

---

### 5.8 Genel Satışa Hazır Olma

Başlangıç puanı:

63 / 100

Puanı artıracak kriterler:

- P0 maddeleri tamamlanmalı.
- Fresh install kanıtlanmalı.
- Backup / restore kanıtlanmalı.
- Lisans ve private key güvenliği netleşmeli.
- Paketleme standardı oluşmalı.
- Pilot müşteri kurulumu belgelenmeli.
- README ve kalite dokümanları güncel olmalı.
- Finansal kritik testler geçmeli.

Hedef:

80 / 100

---

## 6. P0 - Satıştan Önce Mutlaka Çözülmesi Gerekenler

| Durum | İş | Açıklama |
|---|---|---|
| Bekliyor | Private key güvenlik standardı | Private key repoda, build paketinde veya müşteri bilgisayarında bulunmamalı. |
| Bekliyor | Fresh install testi | Temiz bilgisayarda ilk kurulum ve ilk açılış doğrulanmalı. |
| Bekliyor | Backup / restore roundtrip testi | Yedek al, restore et, veritabanını doğrula. |
| Bekliyor | Release paket hijyeni | DB, log, yedek, lisans ve private key paket dışı kalmalı. |
| Bekliyor | Migration v8 doğrulama | Yeni ve eski veritabanı senaryolarında schema v8 doğrulanmalı. |
| Bekliyor | Resmi çalıştırma komutu | Geliştirme ortamı için tek giriş komutu belirlenmeli. |
| Bekliyor | Resmi build komutu | PyInstaller build süreci sabitlenmeli. |
| Bekliyor | Secret scanning | Public repo geçmişi hassas bilgi açısından taranmalı. |
| Tamamlandı | README profesyonel taslak | Projenin güncel durumu için yeni README hazırlandı. |
| Tamamlandı | Kalite skor defteri | Başlangıç skorları ve kalite hedefleri kayıt altına alındı. |

---

## 7. P1 - Pilot Müşteriden Önce Çözülmesi Gerekenler

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

## 8. P2 - Ürünü Güçlendiren İyileştirmeler

| Durum | İş | Açıklama |
|---|---|---|
| Bekliyor | Audit export | Kritik işlem geçmişi Excel/PDF olarak dışa aktarılabilmeli. |
| Bekliyor | Audit bütünlük kontrolü | Audit log değişikliklerine karşı hash-chain veya benzeri yapı değerlendirilmeli. |
| Bekliyor | Otomatik yedek hatırlatma | Kullanıcı düzenli yedek almaya yönlendirilmeli. |
| Bekliyor | Demo veri seti | Satış demo ve test senaryoları için örnek veri hazırlanmalı. |
| Bekliyor | Kullanıcı kılavuzu | Müşteri için sade kullanım dokümanı hazırlanmalı. |
| Bekliyor | Kurumsal rapor şablonları | PDF ve Excel rapor tasarımları güçlendirilmeli. |

---

## 9. P3 - İleri Seviye / Gelecek Faz

| Durum | İş | Açıklama |
|---|---|---|
| Bekliyor | DB encryption | SQLite veritabanı dosyası şifreleme seçeneği değerlendirilmeli. |
| Bekliyor | Kod imzalı installer | Windows güven uyarıları azaltılmalı. |
| Bekliyor | Otomatik güncelleme | Yeni sürümlerin kontrollü dağıtımı sağlanmalı. |
| Bekliyor | Çok firma desteği | Tek uygulamada birden fazla işletme yönetimi değerlendirilmeli. |
| Bekliyor | Bulut yedekleme | İsteğe bağlı güvenli bulut yedekleme opsiyonu değerlendirilmeli. |
| Bekliyor | Lisans yönetim paneli | Lisans üretimi ve müşteri takibi merkezi panelden yapılabilir hale getirilmeli. |

---

## 10. Güncelleme Geçmişi

| Tarih | Sürüm / Aşama | Değişiklik | Etki |
|---|---|---|---|
| 2026-05-13 | Başlangıç | İlk kalite skorları kayıt altına alındı. | Ölçülebilir satışa hazırlık takibi başladı. |
| 2026-05-13 | ADIM 1 | docs/QUALITY_BASELINE.md oluşturuldu. | Kalite, güvenlik, paketleme ve satışa hazırlık hedefleri netleşti. |

---

## 11. Skor Güncelleme Kuralları

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

- Tarih
- İlgili kategori
- Eski puan
- Yeni puan
- Yapılan iş
- Etkilenen dosyalar
- Test
- Sonuç

---

## 12. Mevcut Hedef

Kısa vadeli hedef:

Genel satışa hazır olma: 63 / 100 -> 75 / 100

Bu hedefe ulaşmak için öncelikli işler:

1. Private key güvenlik standardı
2. Release paketi sızıntı kontrolü
3. Fresh install testi
4. Backup / restore roundtrip testi
5. Migration v8 doğrulama
6. Resmi çalıştırma ve build komutu
7. Kredi kartı kritik testleri
8. Limitli hesap kritik testleri

Orta vadeli hedef:

Genel satışa hazır olma: 80 / 100

Bu seviyeye ulaşıldığında FTM, kontrollü pilot müşteri kurulumuna daha güvenli şekilde hazırlanmış kabul edilir.

---

## 13. Özet

Bu dosya FTM projesinin kalite defteridir.

Buradaki puanlar, hedefler ve yapılacak işler düzenli olarak güncellenmelidir.

Amaç; projeyi aceleyle satmak değil, güven veren, desteklenebilir, finansal olarak doğru çalışan ve ticari değeri olan bir masaüstü finans uygulamasına dönüştürmektir.

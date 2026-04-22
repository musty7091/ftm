# FTM - Finansal Yazılım Kuralları

Bu belge, FTM uygulamasının geliştirilmesi sırasında uyulacak zorunlu kuralları içerir.

## 1. Bakiye doğrudan değiştirilmez

Banka, kasa veya hesap bakiyesi doğrudan artırılıp azaltılmaz.

Doğru yöntem:

- Açılış bakiyesi tanımlanır.
- Finansal hareketler kaydedilir.
- Güncel bakiye bu hareketlerden hesaplanır.

## 2. Para hesaplarında float kullanılmaz

Para alanlarında Python float tipi kullanılmaz.

Zorunlu kullanım:

- Python tarafında Decimal
- PostgreSQL tarafında Numeric(18, 2)
- Kur ve oranlarda Numeric(18, 6)

## 3. Finansal kayıtlar silinmez

Finansal kayıtlar veritabanından fiziksel olarak silinmez.

Bunun yerine:

- iptal edildi olarak işaretlenir
- iptal tarihi yazılır
- iptal eden kullanıcı yazılır
- iptal nedeni yazılır

## 4. Audit log zorunludur

Kritik işlemler audit log kaydı oluşturur.

Örnek işlemler:

- çek eklendi
- çek ödendi yapıldı
- müşteri çeki hesaba geçti
- POS yatışı gerçekleşti
- banka transferi tamamlandı
- kayıt iptal edildi
- manuel düzeltme yapıldı

## 5. Planlanan ve gerçekleşen hareketler ayrıdır

Çek yazılması, müşteri çeki alınması veya POS satışı banka bakiyesini hemen değiştirmez.

Banka bakiyesi yalnızca gerçekleşen hareketlerden etkilenir.

## 6. Her hareketin kaynağı olur

Her finansal hareketin kaynak tipi ve kaynak numarası olur.

Örnek:

- issued_check
- received_check
- pos_settlement
- cash_deposit
- bank_transfer
- manual_adjustment

## 7. Bankalar arası transfer çift kayıtlıdır

Bir bankadan diğer bankaya transfer yapılırken:

- çıkan banka için çıkış hareketi
- giren banka için giriş hareketi

oluşturulur.

Bu iki kayıt tek veritabanı transaction içinde kaydedilir.

## 8. Durum alanları serbest metin değildir

Durumlar sabit enum değerleriyle tutulur.

Kullanıcı ekranda Türkçe açıklama görür, veritabanında sabit kod saklanır.

## 9. Tarih alanları ayrı tutulur

Kayıt tarihi, işlem tarihi, vade tarihi, beklenen gerçekleşme tarihi ve gerçekleşme tarihi ayrı alanlardır.

## 10. Kullanıcı yetkileri ilk sürümden itibaren uygulanır

Roller:

- Admin
- Finans Yetkilisi
- Kayıt Personeli
- Sadece Görüntüleme

## 11. Yedekleme zorunludur

Uygulama yedekleme desteğiyle geliştirilecektir.

Hedefler:

- manuel yedekleme
- otomatik günlük yedekleme
- yedek alındığında bilgi maili
- yedek hata verirse uyarı

## 12. Excel desteği olacaktır

Sistem Excel'e veri aktarabilecektir.

İlk hedef raporlar:

- banka risk raporu
- çek vade raporu
- beklenen tahsilat raporu
- POS mutabakat raporu
- günlük nakit raporu

## 13. Test yazılacaktır

Finansal hesaplama yapan servisler pytest ile test edilecektir.

Özellikle:

- Decimal hesapları
- banka risk hesapları
- transfer işlemleri
- çek vade hesapları
- bakiye hesaplama servisleri

test edilecektir.

## 14. Kodlama düzeni

Her geliştirme adımında:

- çalışan yapı korunur
- gereksiz refactor yapılmaz
- dosya isimleri keyfi değiştirilmez
- finansal mantık bozulmaz
- test adımları belirtilir
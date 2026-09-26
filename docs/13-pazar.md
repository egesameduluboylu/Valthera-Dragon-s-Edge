# 13. Maceracı Pazarı

Oyuncular çantalarındaki eşyaları birbirine satar. Pazar kasabadaki **Han**'da, Hancı Bulut'un
İlan Panosu'ndadır. Amaç: nadir ve benzersiz eşyalara ulaşmanın ikinci bir yolu ve altın için
anlamlı bir harcama yeri.

## İki Mod

| Mod | Ne zaman | Kim satar / alır |
|-----|----------|------------------|
| Çevrimdışı | `data/online.json` boş | Panoda kurgusal maceracıların ilanları; oyuncunun ilanlarını kurgusal alıcılar alır |
| Çevrimiçi | Supabase adresi ve anahtarı girilmiş | Gerçek oyuncular (sunucu: `server/`) |

Ekran ve kurallar iki modda aynıdır. Kod tarafında ikisi aynı çağrıları sunar
(`LocalMarket`, `SupabaseMarket`), `GameState.market` hangisinin kullanılacağını seçer.

## Kurallar

Sayılar `data/market.json` içinde.

- **İlan ücreti:** fiyatın %5'i, en az 5 altın. İlan verilirken ödenir, geri verilmez (panoyu çöpten korur).
- **Vergi:** satıldığında fiyatın %10'u kesilir; kalan satıcının postasına düşer.
- **Fiyat:** en az eşyanın parçalama değeri (parçalamaktan ucuza satılamaz), en fazla 1.000.000.
- **Önerilen fiyat:** tüccar fiyatı; benzersiz eşyalarda x2.5.
- **Aynı anda en fazla 5 ilan.** Kuşanılı eşya satılamaz; ilan verilen eşya çantadan çıkar.
- **Günlük sınırlar (çevrimiçi):** oyuncu başına 24 saatte en fazla 20 ilan, 30 satın alma ve toplam
  200.000 altınlık alım (bkz. Güvenlik sınırları).
- **Süre:** çevrimiçi 48 saat, çevrimdışı 3 koşu. Satılmayan eşya postaya geri gelir.
- **Geri çekme:** ilan panodan indirilir, eşya postaya gelir; ücret iade edilmez.
- **Posta:** satış altınları, geri gelen ve geri çekilen eşyalar burada bekler. "Al" ile çantaya/altına eklenir
  (eşya için çantada yer gerekir).

### Çevrimdışı Simülasyon

- Pano 8 ilan tutar. Her koşudan sonra en eski 3 ilan kalkar, yenileri gelir.
- Kurgusal ilanlar en az Nadir'dir, %12 ihtimalle benzersiz eşyadır. Fiyatları önerilen fiyatın 0.85-1.6 katı.
- Oyuncunun ilanı her koşudan sonra şu ihtimalle satılır:
  `clamp(1.2 - 0.6 * fiyat / önerilen_fiyat, %5, %90)`. Yani önerilen fiyata %60, iki katına %5.
- Kasabaya dönüşte satış ve iadeler bir pencereyle bildirilir.

## Ekran

Han → "Maceracı Pazarı" sayfası; üstte Hancı Bulut ve bir konuşma balonu (hata ve sonuç mesajları da buradan),
dört sekme:

1. **Satın Al:** slot ve "Benzersiz" filtreleri, ucuz/pahalı sıralama. Her ilan kartı: eşya, kuşanılana göre
   karşılaştırma, satıcı adı, fiyatlı "Satın Al" butonu.
2. **Sat:** çanta ızgarası; seçilen eşya için önerilen fiyat, %5/%25 adımlarla fiyat ayarı, ilan ücreti ve
   vergiden sonra eline geçecek tutar, "İlana Koy".
3. **İlanlarım:** fiyat, kalan süre, "Geri Çek".
4. **Posta:** kalem kalem "Al" ve "Hepsini Al"; sekme adında bekleyen sayısı.

## Benzersiz Eşyalar

Sabit adlı, sabit nadirlikli, özel etkili eşyalar. Belirli kaynaklardan küçük bir ihtimalle düşer (normal
ganimete ek olarak) ve pazarda en değerli mallardır. Ayrıntılar ve düşme oranları: [05](05-ilerleme-ve-ekipman.md).

## Sunucu (Supabase)

- Oyuncu, cihaz başına **anonim hesapla** girer (e-posta yok). Pazarda görünen ad: profildeki oyuncu adı.
- Tablolar: `players`, `listings`, `mailbox`, `market_config`. İstemci tabloları **sadece okuyabilir**
  (satır düzeyi güvenlik); her değişiklik güvenli sunucu fonksiyonlarıyla yapılır:
  `market_join`, `market_browse`, `market_my_listings`, `market_create_listing`, `market_cancel_listing`,
  `market_buy`, `market_mailbox`, `market_claim`.
- `validate_item`, satılan eşyayı oyunun kurallarıyla kontrol eder: taban ve nadirlik var mı, benzersiz eşyanın
  nadirliği doğru mu, seviye 1-20, güçlendirme 0-10, ek özellik sayısı nadirliğe uygun mu, değerler aralıkta mı.
  Kurallar `data/` dosyalarından üretilen `market_config` tablosundan okunur.
- Aynı ilanı iki kişi aynı anda alamaz: satın alma tek bir `update ... where status = 'active'` ile yapılır.
- Bir oyuncunun ilan verme ve satın alma işlemleri sırayla çalışır (oyuncu başına `pg_advisory_xact_lock`), böylece
  aynı anda gönderilen istekler 5 ilan ve günlük sınırları aşamaz.
- Fonksiyonlar yalnızca giriş yapmış oyunculara (`authenticated`) açıktır; `anon` ve `PUBLIC` çalıştıramaz.
- **Postadan alma tekrarlanabilir:** oyun her "Al" için bir işlem kimliği üretir ve sunucuya sormadan önce kayda
  yazar. Sunucu bu kimliği posta satırına (alma makbuzu) işler; cevap yolda kaybolursa aynı kimlikle tekrar
  sorulunca aynı ödülü yeniden döner. Oyun ödülü ekler ve kimliği aynı kayıtta siler; Posta sekmesi açılınca
  yarım kalan almalar tamamlanır. Böylece altın ve eşya kaybolmaz, iki kez de gelmez.

## Güvenlik sınırları

Altın ve çanta şimdilik **cihazdaki kayıtta** duruyor; sunucu oyuncunun gerçekte neye sahip olduğunu bilmez.
Bu yüzden kayıt dosyasını düzenleyen biri pazara kendi uydurduğu (ama kurallara uyan) bir eşyayı koyabilir ve
kendine yazdığı altınla alım yapabilir. Asıl çözüm kaydı sunucuya taşımak (bulut kayıt, M6); o zamana kadar
sunucu zararı şu önlemlerle sınırlar:

- **Eşya kuralları:** `validate_item` her eşyayı `data/` kurallarıyla denetler (taban, nadirlik, seviye,
  güçlendirme, ek özellik sayısı; her ek özellik `{id, value}` biçiminde, değeri sayı ve aralık içinde olmalı).
  İmkânsız eşyalar reddedilir.
- **Her eşya bir kez:** oyun her eşyayı kayıt kimliği + çanta kimliğiyle gönderir; aynı satıcı aynı eşyayı
  (satılmış, geri çekilmiş ya da süresi dolmuş olsa bile) ikinci kez ilana koyamaz. Eski bir kaydı geri yükleyip
  satılmış eşyayı tekrar satmak böylece engellenir. Cevabı kaybolan bir ilan isteği tekrarlanırsa aynı ilan döner.
- **Günlük ilan sınırı:** satıcı başına 24 saatte `max_listings_per_day` (20) ilan.
- **Günlük alım sınırı:** alıcı başına 24 saatte `max_buys_per_day` (30) alım ve toplam `max_buy_gold_per_day`
  (200.000) altın. Sahte altınla pazardan boşaltılabilecek mal bununla sınırlı kalır.
- **Kendi ilanını alamazsın:** sunucu, satıcısı alıcının kendisi olan ilanı reddeder.

Kalan açıklar: çanta kimliğini değiştiren biri uydurduğu eşyayı yine satabilir, sahte altınla günlük sınır içinde
alım yapabilir ve birden fazla anonim hesap açarak sınırları çoğaltabilir. Bunları ancak sunucu tarafında tutulan
envanter ve altın (bulut kayıt) kapatır.

Kurulum adımları: [server/README.md](../server/README.md).

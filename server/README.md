# Valthera sunucusu (Supabase)

Oyuncular arası pazar bu klasördeki Supabase veritabanı fonksiyonlarıyla çalışır
(tasarım: `docs/13-pazar.md`). `data/online.json` boşken oyun **çevrimdışı pazarı**
kullanır (kurgusal maceracılar); doldurulunca aynı ekran gerçek oyuncularla çalışır.

## Kurulum (bir kez, ~5 dakika)

1. https://supabase.com adresinde ücretsiz hesap aç, **New project** ile bir proje oluştur
   (bölge olarak sana yakın olanı seç, örn. Frankfurt).
2. **Authentication → Sign In / Providers** altında **Allow anonymous sign-ins** seçeneğini aç.
   Oyuncular e-posta girmeden, cihaz başına bir anonim hesapla bağlanır.
3. **SQL Editor**'de sırayla şu dosyaların içeriğini yapıştırıp çalıştır:
   - `supabase/migrations/0001_market.sql` (tablolar, güvenlik kuralları, pazar fonksiyonları)
   - `supabase/migrations/0002_market_config.sql` (eşya kuralları; `data/` içinden üretilir)
4. **Project Settings → API** sayfasından **Project URL** ve **anon public** anahtarını al,
   `data/online.json` içine yaz:
   ```json
   {"supabase_url": "https://xxxx.supabase.co", "supabase_anon_key": "eyJ..."}
   ```
   anon anahtarı herkese açık olacak şekilde tasarlanmıştır; güvenliği satır düzeyi
   güvenlik (RLS) ve sunucu fonksiyonları sağlar. **service_role** anahtarını asla
   oyuna koyma.

`data/items.json` veya `data/market.json` değişirse `python3 tools/market/seed_catalog.py`
çalıştırıp yeni `0002_market_config.sql` dosyasını SQL Editor'de tekrar çalıştır.

## Testler

- `server/tests/run.sh`: migrasyonları geçici bir yerel PostgreSQL'e kurar ve iki oyuncuyla
  ilan verme, satın alma, vergi, posta (tekrarlanan alma), süre dolması, hileli eşya reddi,
  günlük sınırlar, `anon` erişim engeli ve doğrudan tablo yazma engelini dener; sonra aynı
  anda gönderilen 20 ilan isteğinin 5 ilan sınırını aşmadığını kontrol eder.
- `server/tests/run_client_check.sh <godot>`: oyunun `SupabaseMarket` istemcisini,
  Supabase API'sini taklit eden `mock_gateway.py` üzerinden aynı veritabanına bağlayıp uçtan
  uca dener (anonim giriş, süresi dolmuş kayıtlı jetonla yeniden bağlanma, alım-satım, cevabı
  kaybolan posta almanın tamamlanması).

İkisi de GitHub Actions'ta her PR'da çalışır.

## Bilinen sınır

Altın ve çanta şimdilik cihazdaki kayıtta duruyor. Sunucu, satılan her eşyanın oyun
kurallarına uygun olduğunu kontrol eder, aynı eşyanın ikinci kez satılmasını engeller ve
günlük ilan/alım sınırları koyar, ama kayıt dosyasını düzenleyen biri kendine altın
yazabilir. Ayrıntılar: `docs/13-pazar.md` → "Güvenlik sınırları". Tam hile koruması için
kayıt da sunucuya taşınmalı (bulut kayıt); bu, yayın öncesi kilometre taşında (docs/12, M6)
planlı.

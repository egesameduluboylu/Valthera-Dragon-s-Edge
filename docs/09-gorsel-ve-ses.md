# 09. Görsel ve Ses

## Sanat Yönü

- **2D, yandan görünüm, piksel sanat** (karakterler 32x32 veya 48x48, 4 kat büyütülerek gösterilir).
  - Neden: Tek kişi için en hızlı üretilen stil, ücretsiz kaynakları bol, mobilde net görünür.
- Sıcak ve doygun renk paleti; her zindanın kendi baskın rengi (Mahzen: yeşil-gri, Mağara: mor, Geçit: buz mavisi...).
- Arayüz: koyu kahve/ahşap çerçeveler, parşömen panelleri; fantastik ama okunaklı.
- Yazı tipi: Türkçe karakter (ç, ğ, ı, ö, ş, ü) destekleyen piksel font. Adaylar: "Pixel Operator", "m5x7" (Türkçe desteği kontrol edilmeli).

## Asset Kaynakları (Demo için)

Hepsi ticari kullanıma uygun lisanslar; kullanmadan önce her paketin lisansı tekrar kontrol edilecek.

| İhtiyaç | Kaynak |
|---------|--------|
| Karakter ve düşman spriteları | itch.io: "0x72 Dungeon Tileset II", Kenney "Tiny Dungeon" |
| Arayüz | Kenney "UI Pack: Pixel Adventure" |
| İkonlar (yetenek, eşya) | itch.io: "Shikashi's Fantasy Icons Pack" |
| Efektler | itch.io piksel VFX paketleri, Godot parçacık sistemi |
| Arka planlar | Basit katmanlı piksel arka planlar (kendimiz, zindan başına 1) |

Kullanılan her asset `assets/CREDITS.md` dosyasına lisansıyla birlikte yazılır.

## Animasyon Listesi (Karakter Başına)

Bekleme (4 kare), Saldırı (4-6 kare), Büyü (4 kare), Hasar alma (2 kare), Ölüm (4-6 kare).
Eksik animasyonlar Godot Tween ile taklit edilir (ileri atılma, sarsılma, solma).

## Ses

- **Müzik:** Kasaba (sakin, akustik), Zindan (gerilimli döngü), Patron (hızlı), Zafer ve Yenilgi jingle'ları.
  - Kaynak: OpenGameArt, "Abstraction" müzik paketleri, veya ücretsiz lisanslı chiptune.
- **Efektler:** Kılıç, büyü, zehir, kritik, kombo, eşya düşmesi (nadirliğe göre farklı), buton tıklama.
  - Kaynak: Kenney "RPG Audio", sfxr/jsfxr ile üretilmiş retro efektler.
- Ses dosyaları: müzik `.ogg`, efektler `.wav`.

## Teknik Görsel Kurallar

- Doku filtresi: **Nearest** (piksel sanat bulanıklaşmasın).
- Piksel mükemmel ölçekleme: tam sayı katları (4x).
- Aynı anda ekranda en fazla ~200 parçacık (düşük seviye telefonlar için).

# 09. Görsel ve Ses

## Sanat Yönü

- **2D, yandan görünüm, çizgi film (flash cartoon) stili:** Kalın mürekkep çizgileri, düz renkler ve hücre gölgelendirme. DragonFable'ın Flash dönemi görünümüne en yakın stil bu.
- Oyuncu sağa, düşmanlar sola bakar. Karakterler 256x256 çiziliyor, ekranda 200-270 px boyutunda gösteriliyor.
- Sıcak ve doygun renk paleti. Her zindanın kendi baskın rengi var (Mahzen: gri taş ve meşale turuncusu, Mağara: mor, Geçit: buz mavisi...).
- Arayüz: koyu ahşap paneller, altın çerçeveler. Butonlar kabarık görünüyor; basınca içe göçüyor.
- Yazı tipleri (ikisi de OFL lisanslı, Türkçe karakterleri destekliyor):
  - **Nunito** (kalın): tüm arayüz metinleri
  - **Cinzel**: başlıklar, sınıf adı, "KOMBO" ve "ZAFER" yazıları

## Assetler Nasıl Üretiliyor

Engelli asset sitelerine ve lisans takibine bağımlı kalmamak için görseller **koddan üretiliyor**:

```bash
python3 -m pip install pillow
python3 tools/art/generate.py          # tüm görseller
python3 tools/art/generate.py sprites  # sadece karakterler
```

| Dosya | İçerik |
|-------|--------|
| `tools/art/painter.py` | Çizim altyapısı: süper örnekleme, otomatik gölge ve ışık, mürekkep çizgisi |
| `tools/art/characters.py` | Savaşçı, Mahzen Faresi, İskelet Muhafız, Mantar Büyücü |
| `tools/art/backgrounds.py` | Çürük Mahzen arka planı (tuğla duvar, kemer, meşaleler, fıçılar) |
| `tools/art/icons.py` | Yetenek, niyet ve durum ikonları |

Yeni bir düşman eklemek için `characters.py` içine bir fonksiyon yazıp `SPRITES` sözlüğüne eklemek yeterli. Oyuna sonradan elle çizilmiş veya satın alınmış assetler eklenirse aynı dosya yollarına konabilir. Bu durumda `assets/CREDITS.md` dosyasına lisanslarıyla birlikte yazılmalı.

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

- Doku filtresi: **Linear** (çizgi film stili yumuşak kenar ister).
- Aynı anda ekranda en fazla ~200 parçacık (düşük seviye telefonlar için).

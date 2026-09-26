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

Bütün sesler koddan üretilir (`tools/audio`, `python3 tools/audio/generate.py`), dışarıdan dosya yok. Aynı kod her seferinde aynı dosyaları yazar.

- **Müzik** (`assets/audio/music/`, 22 kHz mono WAV, kusursuz döngü): Kasaba (G majör, lavta ve flüt), Zindan (D minör, loş), Savaş (A minör, 132 bpm), Patron (D minör, taiko ve koro), Son (kasaba ezgisinin 3/4 hâli). Sahne değişince 0.6 sn geçişle değişir.
- **Efektler** (`assets/audio/sfx/`, 36 dosya): arayüz tıklama/açma/kapama, satın alma, kuşanma, güçlendirme, parçalama; kılıç, hançer, ateş, buz, yıldırım, gölge, zehir, duman; vuruş, kritik, ıska, kombo, düşman saldırısı ve ölümü, patron fazı, zafer, yenilgi, seviye atlama, yıldız, kapı, sandık.
- `Audio` autoload'u çalar (8 ses kanalı). Müzikle uyumlu sesler (yıldız, altın, iyileşme...) perdesi oynatılmadan çalınır; seviye atlama sesi zafer müziği bitince gelir.
- Titreşim: vuruş alınca, kombo, patron fazı ve demircide. Ayarlardan kapatılabilir.

## Teknik Görsel Kurallar

- Doku filtresi: **Linear** (çizgi film stili yumuşak kenar ister).
- Aynı anda ekranda en fazla ~200 parçacık (düşük seviye telefonlar için).

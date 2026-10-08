# 16 · Yatay ekran, canlı sahneler ve animasyon

Bu belge 0.8 sürümüyle gelen görsel yenilemeyi anlatır. ege'nin örnek görseli hedeftir: boyanmış
bir harabe, ışık hüzmeleri, havada toz ve kıvılcım, nefes alan karakterler, altta süslü bir savaş
paneli (yuvarlak portre, can/mana çubukları, kırmızı "Saldırı" şeridi, numaralı yetenek kareleri,
sağda düşman isim plakası).

## Ekran

- Oyun artık **yatay**: tasarım boyutu 1280 x 720, `stretch = canvas_items`, `aspect = expand`.
  Geniş telefonlarda (19.5:9) sahne yana doğru uzar, arayüz köşelere yapışır.
- Android yönü `sensor_landscape` (telefon iki yöne de çevrilebilir).
- Savaş sahnesi: zemin çizgisi y = 532, alt panel y = 560'tan başlar.

## Canlı arka planlar (`Backdrop`)

`assets/backgrounds/v2/<zindan>/` ve `assets/town/v2/` klasörlerinde 1920 x 1080 katmanlar vardır:

| Dosya | İçerik | Hareket |
|---|---|---|
| `far.png` | gökyüzü, uzak duvarlar | yavaş kayma (6 px) |
| `mid.png` | ana sahne, zemin | 3 px kayma |
| `near.png` | ön plan çerçevesi (sütun, sarmaşık) | ters yönde 9 px |
| `rays.png` | ışık hüzmeleri (toplamalı) | sallanır, parlaklığı dalgalanır |
| `glow.png` | meşale, lav, pencere ışığı (toplamalı) | titrer, bloom verir |
| `fx.json` | parçacık alanları ve `ground_y` | – |

`fx.json` anahtarları: `dust`, `embers`, `sparks`, `spores`, `snow`, `ash`, `leaves` (dikdörtgen
`[x, y, g, y]`), `drips`, `smoke`, `torches` (nokta `[x, y]`). `ground_y` resimdeki zemin çizgisidir;
kod bunu ekrandaki zemine oturtur, böylece karakterlerin ayağı her ekran oranında zemine basar.

Katman yoksa eski tek resim (`backgrounds/<id>.png`) kullanılır ve üzerine toz eklenir.

## Işıma (bloom)

Savaş sahnesi HDR açık bir `SubViewport` içinde çizilir. `WorldEnvironment` ışıması
(eşik 1.0, toplamalı) yalnızca rengi 1.0'ın üstünde olan şeyleri parlatır: büyüler, kıvılcımlar,
vuruş parlamaları, lav. Arayüz bu viewport'un dışında kaldığı için renkleri bozulmaz.
Ayarlar > **Efektler** kapalıyken HDR ve ışıma kapanır, parçacıklar azalır (zayıf telefonlar için).

## Animasyonlu karakterler (`Puppet`)

Her kahraman, ejder ve canavar parçalı bir kukladır (DragonFable/Flash tarzı "cut-out").
Parçalar `assets/rigs/<id>/` altında PNG olarak durur, `rig.json` nasıl birleştiklerini söyler:

```json
{"canvas": [512, 512], "feet": [256, 470], "facing": "right", "kind": "biped",
 "parts": [{"name": "torso", "png": "torso.png", "parent": "", "role": "torso",
            "pivot": [256, 330], "rect": [180, 220, 150, 140], "z": 10, "blend": "mix"}]}
```

- `pivot` parçanın döndüğü eklem noktasıdır (tuval pikseli), `parent` bağlı olduğu parça.
- `role` hareketi seçer: `root torso head jaw hair cape arm_front_upper arm_front_lower weapon
  arm_back_upper arm_back_lower offhand leg_* tail wing_front wing_back float extra fx`.
- `blend: add` olan parçalar (göz ışığı, alev, büyü küresi) nabız gibi parlar.

Oyun bu parçaları kodla oynatır; ayrı kare kare animasyon çizmeye gerek yoktur:

| Durum | Hareket |
|---|---|
| bekleme | nefes (gövde), kafa sallanması, pelerin/saç/kuyruk dalgası, kanat çırpma, süzülme |
| saldırı | geri çekilme → ileri atılma ve vuruş (silah kolu savrulur) |
| büyü | kollar kalkar, el parlar, mermi fırlar |
| savunma | kalkan öne, gövde çöker |
| hasar | geri sarsılma, beyaz parlama |
| ölüm | yana devrilme ve solma |

Ayarlar > **Animasyonlar** kapalıyken kuklalar sabit durur (yalnızca vuruş sarsıntısı kalır).
Kuklası olmayan bir canavar eski tek resmiyle çizilir.

Parçalar `tools/art/rig.py` ile üretilir: `RigBuilder` her parçayı tam tuval boyutunda çizip
kırpar, `rig.json`'u yazar ve eski oyun içi resmi (`sprites/...`) aynı pozdan düz olarak kaydeder.
`pose_sheet()` bir kuklanın dört pozunu (dinlenme, hazırlık, vuruş, hasar) tek sayfada gösterir;
yeni bir kukla eklerken önce bu sayfaya bakın.

## Savaş efektleri (`BattleFx`)

Element renkleri HDR'dir (1.0 üstü): fiziksel beyaz, ateş turuncu, buz açık mavi, şimşek mor-beyaz,
gölge mor, zehir yeşil, kutsal altın. Her vuruş: parlama + element kıvılcımları; yakın dövüşte
bir kılıç yayı; büyülerde kuyruklu küre; ejder nefesi parçacık konisi. Kritik vuruşlar daha büyük
ve ekranı sarsar.

## Savaş paneli

Alttaki süslü şerit örnek görselle aynı sırayı izler:

1. Yuvarlak portre madalyonu, seviye rozeti, sınıf adı ve durum simgeleri
2. Kırmızı can ve mavi kaynak (öfke/mana/enerji) çubukları
3. Kırmızı **Saldırı** şeridi (sınıfın ilk yeteneği) ve 1-5 numaralı yetenek kareleri
   (bekleme süresi gölgesi, maliyet rozeti)
4. Hedef düşmanın isim plakası: portre, seviye, can çubuğu
5. Yuvarlak **Savun** ve **İksir** düğmeleri

Panel kaplamaları `assets/ui/v2/` altındadır; yoksa kod aynı düzeni düz renkli kutularla çizer.

## Diğer ekranlar

- **Kasaba**: tek geniş, canlı resim (bacalarda duman, pencerelerde ışık, kuşlar). Binalar resmin
  içindedir; `hotspots.json` her binanın dokunma alanını ve tabela yerini verir. Üst şeritte
  portre, seviye, ejder ve para; sağ altta **Zindana Gir**, sol altta **Çanta**.
- **Zindan haritası**: zindanın katmanları karartılmış arka plan olur. Solda kahraman kartı ve
  Kaçış, ortada kapılar, üstte oda izi.
- **Paneller** (çanta, demirci, tüccar, pazar, sınıf ustası, ayarlar, ejder): iki sütunlu düzen,
  solda liste veya ızgara, sağda seçilen şeyin ayrıntısı.
- **Hikaye**: konuşan karakter solda ayakta, konuşma balonu sağında.

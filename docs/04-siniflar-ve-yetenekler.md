# 04. Sınıflar ve Yetenekler

## Genel Kurallar

- Oyun 3 sınıfla açılır: **Savaşçı**, **Büyücü**, **Haydut**. İlk sınıf oyuncu seçer, diğerleri kasabadaki Sınıf Ustası'ndan açılır (ilk zindan bitince).
- Her sınıfın kendi seviyesi vardır (1-20, sonraki sürümlerde 30).
- Her sınıfın 8 yeteneği vardır; savaşa **4 tanesi** takılır.
- Ekipman sınıflar arasında paylaşılır, ancak silahlar sınıfa özeldir (kılıç, asa, hançer).
- Yeteneklerin bekleme süresi (tur cinsinden) ve kaynak maliyeti vardır.

## Sınıf Kaynakları

| Sınıf | Kaynak | Başlangıç | Maks | Nasıl kazanılır |
|-------|--------|-----------|------|-----------------|
| Savaşçı | Öfke | 20 | 100 | Vurunca +10, hasar alınca +15, Savun +20 |
| Büyücü | Mana | 100 | 100 | Her tur +15, Savun +30 |
| Haydut | Enerji | 60 | 100 | Her tur +25, Savun +40 |

## Başlangıç İstatistikleri (Seviye 1) ve Seviye Başına Artış

| Sınıf | CAN | SAL | SAV | HIZ | KRT |
|-------|-----|-----|-----|-----|-----|
| Savaşçı | 120 (+12) | 12 (+2) | 15 (+2) | 8 (+0.5) | %5 |
| Büyücü | 80 (+8) | 15 (+2.5) | 6 (+1) | 10 (+0.5) | %8 |
| Haydut | 95 (+9) | 13 (+2) | 9 (+1.5) | 14 (+1) | %15 |

---

## Savaşçı: "Kalkan kır, kafa kır."

Dayanıklı, Öfke biriktirip büyük vuruşlar yapan sınıf. Kombosu: Zırh Kırık ve Sersem.

| Açılış Sv. | Yetenek | Rol | Maliyet | Bekleme | Güç | Etki |
|---|---|---|---|---|---|---|
| 1 | Kılıç Darbesi | Nötr | 0 | 0 | 1.0 | Temel saldırı, +10 Öfke |
| 1 | Kalkan Kır | Hazırlayıcı | 0 | 2 | 0.6 | Zırh Kırık uygular |
| 2 | Ağır Vuruş | Bitirici (Zırh Kırık) | 30 Öfke | 0 | 1.4 | Kombo: 1.8 kat ve Sersem |
| 4 | Savaş Narası | Nötr | 20 Öfke | 4 | - | 2 tur Güçlenmiş |
| 6 | Kanatan Kesik | Hazırlayıcı | 0 | 1 | 0.8 | Kanama uygular |
| 9 | İnfaz | Bitirici (Sersem) | 40 Öfke | 3 | 1.6 | Kombo: 2 kat; hedef %25 canın altındaysa 3 kat |
| 12 | Demir Duvar | Nötr | 0 | 4 | - | Maks. CAN'ın %25'i kadar Kalkan |
| 16 | Kasırga | Bitirici (Kanama) | 60 Öfke | 3 | 0.9 | Tüm düşmanlara; kanayanlara 1.7 kat |

## Büyücü: "Önce yak, sonra patlat."

Kırılgan ama yüksek hasarlı. Element zayıflıklarını en iyi kullanan sınıf. Kombosu: Yanma, Donma, Yıldırım zinciri.

| Açılış Sv. | Yetenek | Rol | Maliyet | Bekleme | Güç | Etki |
|---|---|---|---|---|---|---|
| 1 | Büyü Oku | Nötr | 0 | 0 | 0.9 | Gölge hasarı, +5 Mana |
| 1 | Ateş Topu | Hazırlayıcı | 20 Mana | 0 | 1.0 | Ateş, Yanma uygular |
| 2 | Alev Patlaması | Bitirici (Yanma) | 30 Mana | 1 | 1.2 | Kombo: 2 kat, Yanma'yı tüketir |
| 4 | Buz Mızrağı | Hazırlayıcı | 20 Mana | 0 | 0.9 | Buz, 1 yığın Donma |
| 6 | Mana Kalkanı | Nötr | 25 Mana | 3 | - | 30 + SAL kadar Kalkan |
| 9 | Paramparça | Bitirici (Donma) | 35 Mana | 2 | 1.3 | Kombo: yığın başına +0.5 kat |
| 12 | Zincirleme Şimşek | Nötr | 40 Mana | 2 | 0.8 | Yıldırım, tüm düşmanlar |
| 16 | Meteor | Bitirici (Yanma) | 70 Mana | 5 | 2.0 | Tüm düşmanlar; yananlara 1.5 kat |

## Haydut: "Zehirle, bekle, bitir."

Hızlı, kritik ağırlıklı. Birden fazla yetenek kullanabilen tek sınıf. Kombosu: Zehir yığınları ve kritik.

Özel mekanik: **Seri.** Haydut bir turda Enerjisi yettiği sürece **2 yetenek** kullanabilir (ikinci yeteneğin maliyeti +10 Enerji).

| Açılış Sv. | Yetenek | Rol | Maliyet | Bekleme | Güç | Etki |
|---|---|---|---|---|---|---|
| 1 | Hançer Darbesi | Nötr | 10 Enerji | 0 | 0.8 | Temel saldırı |
| 1 | Zehirli Bıçak | Hazırlayıcı | 20 Enerji | 0 | 0.6 | 2 yığın Zehir |
| 2 | Sırttan Bıçak | Bitirici (Zehir) | 35 Enerji | 1 | 1.2 | Kombo: kesin kritik |
| 4 | Duman Bombası | Nötr | 30 Enerji | 4 | - | 2 tur KAÇ +%40 |
| 6 | Göz Boyama | Hazırlayıcı | 15 Enerji | 2 | 0.3 | Sersem uygular (patronlarda %50 şans) |
| 9 | Zehir Patlaması | Bitirici (Zehir) | 40 Enerji | 2 | 0.5 | Kalan tüm zehir hasarını anında verir |
| 12 | Bıçak Yağmuru | Nötr | 45 Enerji | 3 | 0.5 x4 | Rastgele hedeflere 4 vuruş |
| 16 | Gölge Adım | Bitirici (Sersem) | 50 Enerji | 4 | 2.2 | Kombo: 3 kat, Enerji iade |

---

## Yetenek Geliştirme (Sonraki Sürüm)

Her yetenek 3 kademeye kadar geliştirilebilir (Sınıf Ustası, altın + yetenek kitabı):
Kademe 2: güç +%15. Kademe 3: ek etki (örneğin Ateş Topu 2 hedefe sıçrar).

## Denge Notları

- Kombo yapan oyuncu, kombo yapmayandan ortalama %50-70 daha hızlı savaş bitirmeli.
- Aynı seviyede bir sıradan düşman 3-4 turda ölmeli; patron 8-12 turda.
- Tüm sayılar ilk test sonrasında `data/` klasöründeki dosyalardan ayarlanacak (bkz. 10-teknik-tasarim.md).

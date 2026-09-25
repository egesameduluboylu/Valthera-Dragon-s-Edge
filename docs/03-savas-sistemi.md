# 03. Savaş Sistemi

## Genel Yapı

- Sıra tabanlı. Oyuncu tek karakter, karşısında 1 ila 3 düşman.
- Her tur: önce oyuncu hareket eder, sonra düşmanlar HIZ değerine göre sırayla hareket eder.
- Oyuncu turu başında sınıf kaynağı yenilenir ve durum etkileri işler.

## Temel İstatistikler

| İstatistik | Kısaltma | Açıklama |
|-----------|----------|----------|
| Can | CAN | 0 olunca karakter ölür |
| Saldırı | SAL | Fiziksel ve büyü hasarının tabanı |
| Savunma | SAV | Gelen hasarı azaltır |
| Hız | HIZ | Düşmanlar arasında sırayı belirler, kaçınma şansını etkiler |
| Kritik Şansı | KRT | Yüzde; kritik vuruş 1.5 kat hasar |
| Kaçınma | KAÇ | Yüzde; saldırıyı tamamen boşa çıkarma şansı (en fazla %30) |

## Hasar Formülü

```
ham_hasar   = SAL * yetenek_gücü
azaltma     = 100 / (100 + hedef_SAV)
element     = hedefin element çarpanı (0.5 / 1.0 / 1.5)
kritik      = 1.5 (kritik olursa) veya 1.0
rastgelelik = 0.9 ile 1.1 arası rastgele
kombo       = bitirici bonusu (aşağıda), yoksa 1.0

hasar = max(1, yuvarla(ham_hasar * azaltma * element * kritik * rastgelelik * kombo))
```

Örnek: SAL 20, yetenek gücü 1.2, hedef SAV 25, element nötr, kritik yok:
`20 * 1.2 * (100/125) = 19.2` civarı hasar.

## Elementler

Fiziksel, Ateş, Buz, Yıldırım, Gölge.
Her düşmanın her element için bir çarpanı vardır: **zayıf (1.5)**, **nötr (1.0)** veya **dirençli (0.5)**.
Zayıflıklar düşman bilgi panelinde ilk karşılaşmadan sonra görünür hâle gelir.

## Durum Etkileri

| Durum | Etki | Süre |
|-------|------|------|
| Kanama | Tur başında SAL'ın %30'u kadar fiziksel hasar | 3 tur |
| Yanma | Tur başında maks. CAN'ın %5'i kadar ateş hasarı | 3 tur |
| Donma | Hedefin HIZ'ı yarıya iner, 3 yığında 1 tur dondurur | 2 tur |
| Sersem | Hedef bir sonraki turunu kaçırır | 1 tur |
| Zırh Kırık | Hedefin SAV'ı %50 azalır | 2 tur |
| Zehir | Tur başında yığın başına 3 hasar, en fazla 5 yığın | 4 tur |
| Kalkan | Belirtilen miktarda hasarı emer | Tur sonuna / kırılana kadar |
| Güçlenmiş | SAL %25 artar | 2 tur |

Aynı durum tekrar uygulanırsa süre yenilenir (Zehir ve Donma hariç, onlar yığılır).

## Kombo Sistemi: Hazırlayıcı ve Bitirici

Oyunun kalbi burası. Her yeteneğin bir rolü vardır:

- **Hazırlayıcı:** Hedefe bir durum uygular (örneğin Zırh Kırık, Yanma, Zehir).
- **Bitirici:** Hedefte belirli bir durum varsa bonus etki kazanır ve genellikle o durumu tüketir.
- **Nötr:** Tek başına işe yarar, kombo ile ilişkisi yoktur.

Kural: Bitirici doğru durumu bulursa hasarı en az **1.5 kat** olur ve ekranda "KOMBO!" yazısı çıkar.
Ardışık kombolarda kombo sayacı artar (x2, x3...) ve her kombo ek %10 hasar verir. Kombo olmayan bir yetenek kullanılınca sayaç sıfırlanır.

Örnek zincir (Savaşçı):
1. **Kalkan Kır** → hedefe Zırh Kırık uygular.
2. **Ağır Vuruş** → hedef Zırh Kırık ise 1.8 kat hasar ve Sersem uygular. KOMBO x1.
3. **İnfaz** → hedef Sersem ise 2 kat hasar. KOMBO x2 (+%10).

## Düşman Niyeti

Her düşmanın kafasının üstünde bir sonraki hamlesini gösteren ikon ve sayı vardır:

| İkon | Anlamı |
|------|--------|
| Kılıç + sayı | Saldırı ve tahmini hasar |
| Kalkan | Savunma, kalkan kazanacak |
| Yıldız | Kendini veya müttefikini güçlendirecek |
| Kafatası | Oyuncuya durum etkisi uygulayacak |
| Ünlem | Özel veya güçlü hamle (patronlar) |

Niyet, oyuncunun turu başında belirlenir ve o tur değişmez (Sersem gibi etkiler hariç).

## Savunma ve İksir

- Yetenek slotlarına ek olarak her zaman iki buton vardır:
  - **Savun:** O tur gelen hasarı %50 azaltır, sınıf kaynağından ekstra kazandırır.
  - **Çanta:** İksir kullanmak turu harcar. Koşuya en fazla 3 iksir götürülebilir.

## Savaşın Sonu

- Tüm düşmanlar ölünce: deneyim, altın ve ganimet gösterilir.
- Oyuncu ölünce: koşu biter (bkz. 02-oyun-dongusu.md, ölüm kuralları).
- Savaş içinde kaçmak yok; kaçış yalnızca odalar arasında mümkün.

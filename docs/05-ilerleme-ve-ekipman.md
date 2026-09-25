# 05. İlerleme ve Ekipman

## Deneyim ve Seviye

- Seviye aralığı: 1-20 (ilk sürüm).
- Bir sonraki seviye için gereken deneyim:

```
gereken_xp(sv) = yuvarla(50 * sv ^ 1.5)
```

| Sv | Gereken XP | Toplam |
|----|-----------|--------|
| 1→2 | 50 | 50 |
| 2→3 | 141 | 191 |
| 5→6 | 559 | ~1.300 |
| 10→11 | 1.581 | ~7.000 |
| 19→20 | 4.141 | ~40.000 |

- Düşman deneyimi: `taban_xp * düşman_seviyesi`. Sıradan düşman taban 10, elit 25, patron 100.
- Oyuncudan 5+ seviye düşük düşmanlar %20 deneyim verir (kasmayı caydırmak için).
- Deneyim sadece aktif sınıfa gider.

## Ekipman Slotları

| Slot | Ana istatistik | Not |
|------|----------------|-----|
| Silah | SAL | Sınıfa özel: Kılıç (Savaşçı), Asa (Büyücü), Hançer (Haydut) |
| Zırh | CAN, SAV | Tüm sınıflar |
| Kask | SAV, KRT | Tüm sınıflar |
| Aksesuar | Değişken | Yüzük veya kolye, özel etkiler |

## Nadirlik

| Nadirlik | Renk | Ek özellik sayısı | Düşme oranı |
|----------|------|-------------------|-------------|
| Sıradan | Gri | 0 | %60 |
| Nadir | Mavi | 1 | %30 |
| Epik | Mor | 2 | %9 |
| Efsanevi | Turuncu | 2 + benzersiz etki | %1 (sadece patron) |

Ek özellik havuzu: +CAN, +SAL, +SAV, +HIZ, +KRT, +KAÇ, element direnci, "Savaş başında X Kalkan", "Kombo hasarı +%10" vb.

Efsanevi örnekleri:
- **Kemik Kral'ın Tacı (Kask):** Düşman öldürünce 10 CAN yenile.
- **Sonsuz Kor (Asa):** Yanma etkisi 1 tur daha uzun sürer.
- **Fısıltı (Hançer):** Seri ile kullanılan ikinci yetenek bedava.

## Eşya Gücü

- Eşyanın seviyesi, düştüğü zindanın seviyesidir.
- Ana istatistik: `taban * (1 + 0.12 * eşya_seviyesi) * nadirlik_çarpanı`
  (Sıradan 1.0, Nadir 1.15, Epik 1.3, Efsanevi 1.5)

## Demirci: Güçlendirme

- Eşyalar +1'den +10'a kadar güçlendirilir. Her kademe ana istatistiğe +%8.
- Maliyet: `altın = 20 * eşya_seviyesi * (kademe + 1)` ve +6'dan sonra "Ejder Pulu" malzemesi.
- Başarısızlık yok (oyuncuyu üzmemek için). Kademe 10 bir eşyayı üst nadirliğe yükseltmez.
- **Parçala:** İstenmeyen eşyalar altın ve malzemeye dönüştürülür.

## Para Birimleri

| Birim | Nasıl kazanılır | Ne için harcanır |
|-------|-----------------|------------------|
| Altın | Düşmanlar, sandıklar, parçalama | Güçlendirme, tüccar, iksir |
| Ejder Pulu | Elit ve patron düşmanlar | +6 ve üzeri güçlendirme |
| Kristal | Günlük görevler, başarımlar, (isteğe bağlı) satın alma | Kozmetik, ekstra çanta alanı |

## Çanta

- Başlangıçta 30 eşya alanı. Kristal ile +10'ar genişletilebilir.
- Çanta doluyken yeni ganimet otomatik parçalanır (oyuncuya bildirilir).

## Zindan Yıldızları

Her zindan için 3 yıldız:
1. Zindanı bitir.
2. Hiç iksir kullanmadan bitir.
3. Canın %50'sinin üstünde bitir.

3 yıldız alınan zindan "Zor" modunu açar (düşmanlar +3 seviye, daha iyi ganimet).

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

Kuşanma seviyesi: eşya seviyesinin 2 altına kadar (Sv 5 eşya, Sv 3 karakterde giyilir). Pazardan çok
yüksek seviyeli eşya alınsa bile hemen giyilemez.

Efsanevi örnekleri:
- **Kemik Kral'ın Tacı (Kask):** Düşman öldürünce 10 CAN yenile.
- **Sonsuz Kor (Asa):** Yanma etkisi 1 tur daha uzun sürer.
- **Fısıltı (Hançer):** Seri ile kullanılan ikinci yetenek bedava.

## Eşya Gücü

- Eşyanın seviyesi, düştüğü zindanın seviyesidir.
- Ana istatistik: `taban * (1 + 0.12 * eşya_seviyesi) * nadirlik_çarpanı`
  (Sıradan 1.0, Nadir 1.15, Epik 1.3, Efsanevi 1.5)
- CAN ve Kalkan tam sayıya yuvarlanır; SAL ve SAV ondalıklı kalır ki her güçlendirme görünsün.

## Demirci: Güçlendirme

- Eşyalar +1'den +10'a kadar güçlendirilir. Her kademe ana istatistiğe +%8.
- Maliyet: `altın = 20 * eşya_seviyesi * (kademe + 1)` ve +6'dan sonra "Ejder Pulu" malzemesi.
- Başarısızlık yok (oyuncuyu üzmemek için). Kademe 10 bir eşyayı üst nadirliğe yükseltmez.
- **Parçala:** İstenmeyen eşyalar altın ve malzemeye dönüştürülür:
  `altın = 6 * eşya_seviyesi * (nadirlik_sırası + 1) + 10 * kademe`, Epik 1, Efsanevi 2 Ejder Pulu.
  Kuşanılı eşya parçalanamaz.

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

## Çürük Mahzen Eşyaları (M3)

Tüm sayılar `data/items.json` içinde.

| Eşya | Slot | Ana istatistik | En düşük seviye |
|------|------|----------------|-----------------|
| Paslı Kılıç (başlangıç) | Silah (Savaşçı) | SAL 1 | 1 |
| Demir Kılıç | Silah (Savaşçı) | SAL 4 | 2 |
| Kemik Satır | Silah (Savaşçı) | SAL 5 | 3 |
| Deri Zırh | Zırh | CAN 12, SAV 2 | 1 |
| Zincir Zırh | Zırh | CAN 16, SAV 4 | 2 |
| Deri Başlık | Kask | SAV 2, KRT %1 | 1 |
| Demir Miğfer | Kask | SAV 3, KRT %2 | 2 |
| Bakır Yüzük | Aksesuar | SAL 1, CAN 5 | 1 |
| Kemik Muska | Aksesuar | SAV 1, CAN 8 | 1 |
| Kemik Kral'ın Tacı | Kask (efsanevi) | SAV 4, KRT %3, öldürünce 10 CAN | sadece Kemik Kral |

Paslı Kılıç bilerek zayıf: yeni bir Savaşçı ilk koşuların yaklaşık yarısını bitirir (bot testi),
ilk birkaç ganimetle bu oran belirgin şekilde artar.

Ek özellik aralıkları (seviye ile büyüyenler `*`): CAN 4-8*, SAL 1-2*, SAV 1-3*, HIZ 0.5-1, KRT %1-3,
KAÇ %1-2, Savaş başında 5-10* Kalkan, Kombo hasarı +%5-10. Bir eşyada aynı ek özellik iki kez çıkmaz.

### Ganimet Tablosu

| Kaynak | Eşya şansı | En düşük nadirlik | Ejder Pulu |
|--------|-----------|-------------------|------------|
| Sıradan savaş | %35 | Sıradan | - |
| Hazine sandığı | %100 | Sıradan | - |
| Taklitçi | %100 | Nadir | - |
| Elit (Bekçi) | %100 | Nadir | 1 |
| Kemik Kral | %100 (efsanevi mümkün) + %5 Tacı | Nadir | 2 |
| Konuşan Kurukafa (doğru cevap) | %100 | Nadir | - |

Silahlar sadece aktif sınıfın silahlarından çıkar. Ölünce ganimet kalır, altının yarısı gider.

### Tüccar (Madam Pırıl)

- Can İksiri 25 altın; en fazla 6 iksir taşınır. Kasabaya dönünce stok ücretsiz olarak 3'e tamamlanır.
- Her koşudan sonra 3 yeni eşya gelir (seviye: bitirilen zindanların en yükseği). Fiyat = parçalama değeri x 4.

### Benzersiz Eşyalar (Çürük Mahzen)

Sabit adlı ve nadirlikli, özel etkili eşyalar. Normal ganimete ek olarak kendi küçük ihtimalleriyle düşer,
pazarda önerilen fiyatları x2.5'tir.

| Eşya | Nadirlik | Slot | Özel etki | Kaynak |
|------|----------|------|-----------|--------|
| Fare Dişi Kolye | Epik | Aksesuar | Vuruşlar %25 ihtimalle Kanama | Sıradan savaş %2 |
| Spor Pelerini | Epik | Zırh | Alınan hasarın %20'si saldırana yansır | Sıradan savaş %2 |
| Taklitçi Dişi Yüzük | Epik | Aksesuar | Bulunan altın +%30 | Taklitçi %15 |
| Bekçi Baltası | Epik | Silah (Savaşçı) | Her savaşta ilk saldırı +%50 | Elit %12 |
| Kemik Kral'ın Tacı | Efsanevi | Kask | Öldürünce 10 can | Kemik Kral %6 |
| Kral Katili | Efsanevi | Silah (Savaşçı) | Hasarın %12'si kadar can çalma, canın %30 altındayken +%30 hasar | Kemik Kral %4 |

Yeni zindanlar kendi benzersiz eşyalarını getirir (Sonsuz Kor, Fısıltı vb.).

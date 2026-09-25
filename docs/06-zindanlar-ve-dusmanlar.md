# 06. Zindanlar ve Düşmanlar

## Zindan Yapısı

Her zindan 5 odadan oluşur. Oda 5 her zaman patrondur; ilk 4 oda aşağıdaki tiplerden rastgele seçilir (en az 2 savaş odası garanti).

| Oda tipi | Olasılık | Açıklama |
|----------|----------|----------|
| Savaş | %55 | 1-3 sıradan düşman |
| Elit | %15 | 1 elit düşman (daha güçlü, Ejder Pulu düşürür). Oda 3 veya 4'te çıkabilir |
| Hazine | %10 | Sandık: altın ve bir eşya; %20 ihtimalle Taklitçi (sandık canavarı) |
| Olay | %12 | Metin tabanlı seçim (aşağıda) |
| Dinlenme | %8 | Canın %30'unu yenile veya bir yeteneğin bekleme süresini sıfırla |

Odalar arasında oyuncu bir sonraki odanın **tipini görür** ve iki kapıdan birini seçebilir (dallanma). Bu, risk ve ödül seçimini oyuncuya bırakır.

## Olay Odası Örnekleri

- **Şüpheli Çeşme:** İç → %60 canın tamamı yenilenir, %40 Zehir. / Geç.
- **Kayıp Tüccar:** 50 altına rastgele bir iksir satar.
- **Konuşan Kurukafa:** Bir bilmece sorar; doğru cevap bir Nadir eşya verir. (Esprili diyalog.)
- **Lanetli Sunak:** 20 CAN ver → bu koşu boyunca SAL +%15.

## Zindan Listesi (İlk Sürüm)

| # | Zindan | Seviye | Tema | Patron |
|---|--------|--------|------|--------|
| 1 | Çürük Mahzen | 1-3 | Fareler, iskeletler | Kemik Kral |
| 2 | Mantar Mağarası | 4-6 | Mantarlar, sümüklüler, zehir | Ana Spor |
| 3 | Buzlu Geçit | 7-10 | Kurtlar, buz ruhları | Soğuk Nefes (genç buz ejderi) |
| 4 | Yanık Kale | 11-15 | Kültistler, ateş iblisleri | Kor Rahibe |
| 5 | Ejder Yuvası | 16-20 | Ejder tarikatı, ejderler | Kül Kanat |

Demo sadece **Çürük Mahzen**'i içerir.

## Düşman Tasarımı Kuralları

- Her düşmanın **1 belirgin davranışı** vardır; oyuncu 2 karşılaşmada öğrenebilmeli.
- Her düşmanın en az bir element zayıflığı olur.
- Niyetler basit bir desenle döner (örneğin Saldır, Saldır, Savun) veya koşula bağlıdır.

## Çürük Mahzen Düşmanları

Değerler seviye 1 içindir. Seviye başına: CAN +%15, SAL +%10, SAV +%10.

### Mahzen Faresi (sıradan)
- CAN 30, SAL 8, SAV 5, HIZ 12
- Zayıf: Ateş. Dirençli: -
- Davranış: Genelde 2-3'lü gelir. Desen: Isır, Isır, Kemir (Kanama uygular).
- Espri: "Peynir sandığın şey başka bir şeydi."

### İskelet Muhafız (sıradan)
- CAN 45, SAL 10, SAV 20, HIZ 6
- Zayıf: Fiziksel ezici (Zırh Kırık altında ekstra %25 hasar alır), Ateş. Dirençli: Zehir (bağışık), Gölge
- Davranış: Desen: Kalkan Kaldır (15 Kalkan), Kılıç Salla, Kılıç Salla.

### Mantar Büyücü (sıradan)
- CAN 35, SAL 12, SAV 8, HIZ 9
- Zayıf: Ateş. Dirençli: Zehir
- Davranış: Başka düşman varsa önce onlara Güçlenmiş verir; yalnız kalırsa Spor Bulutu (2 yığın Zehir) atar.

### Mahzen Bekçisi (elit)
- CAN 110, SAL 15, SAV 25, HIZ 7
- Zayıf: Yıldırım. Dirençli: Fiziksel
- Davranış: Her 3 turda bir Ağır Balta (2 kat hasar, niyet ünlemle gösterilir). Oyuncu o tur Savun kullanırsa Bekçi 1 tur Sersem kalır.

### Taklitçi (sürpriz)
- CAN 60, SAL 14, SAV 15, HIZ 10
- Davranış: İlk tur her zaman Yut (büyük saldırı). Yenilirse 2 kat ganimet verir.

## Patron: Kemik Kral

- CAN 300, SAL 16, SAV 22, HIZ 8, Seviye 3
- Zayıf: Ateş, Fiziksel ezici. Dirençli: Zehir (bağışık), Gölge
- **Faz 1 (CAN %100-50):**
  - Desen: Asa Vuruşu, Kemik Çağır (1 İskelet Muhafız çağırır, sahada en fazla 2), Asa Vuruşu, Taç Işığı (kendine 30 Kalkan).
- **Faz 2 (CAN %50 altı):** "Yeter! Artık ciddiyim... sanırım."
  - SAL +%30. Yeni hamle: **Kemik Fırtınası** (1 tur önceden ünlemle uyarır, oyuncuya 3 vuruş).
  - Çağırdığı iskeletler öldüğünde Kral'a 20 CAN verir (öncelik sorusu yaratır).
- Ödül: 100 XP, 150 altın, garanti Nadir eşya, %5 Kemik Kral'ın Tacı.

## Zorluk Ölçekleme

- Zindan düşmanlarının seviyesi: zindan aralığında, oda numarasıyla artar (Oda 1 = alt sınır, patron = üst sınır).
- Zor mod: tüm düşmanlar +3 seviye, düşme oranları: Nadir %40, Epik %15.

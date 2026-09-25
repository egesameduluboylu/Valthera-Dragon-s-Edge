# 02. Oyun Döngüsü

## Anlık Döngü (Bir Tur, 5-10 saniye)

1. Düşmanların niyet ikonlarına bak (saldırı, savunma, büyü, güçlenme).
2. 4 yetenekten birini seç ve hedefi seç (tek düşman varsa hedef otomatik).
3. Animasyonu izle: hasar sayıları, durum etkileri, kombo yazısı.
4. Düşmanlar sırayla hamlelerini yapar.
5. Yeni tur başlar, kaynaklar (mana, enerji) yenilenir.

## Oturum Döngüsü (Bir Koşu, 3-7 dakika)

```
Kasaba -> Zindan seç -> Oda 1 -> Oda 2 -> ... -> Patron -> Ödül ekranı -> Kasaba
```

- Her zindan 5 odadan oluşur (detay: 06-zindanlar-ve-dusmanlar.md).
- Odalar arasında can kısmen yenilenmez; iksir ve olay odaları önemli.
- Oyuncu her odadan sonra "Devam et" veya "Kaçış" seçebilir.
  - **Kaçış:** Toplanan ganimetin tamamı korunur ama patron ödülü alınmaz.
  - **Ölüm:** Toplanan altının %50'si ve tüm eşyalar kaybedilir, deneyim korunur.

## Uzun Vadeli Döngü (Günler, Haftalar)

1. Deneyim kazan, sınıf seviyesini yükselt, yeni yetenek aç.
2. Ekipman topla, demircide güçlendir.
3. Yeni zindanların kilidini aç (her zindan bir öncekinin patronunu yenince açılır).
4. Diğer sınıfları dene; ekipman sınıflar arasında paylaşılır, seviyeler ayrıdır.
5. Günlük görevler (sonraki sürümler) ile küçük ödüller.

## Motivasyon Kancaları

- **Yakın hedef:** "Bir sonraki seviyede yeni yetenek" her zaman görünür.
- **Ganimet heyecanı:** Nadir eşya düştüğünde özel efekt ve ses.
- **Ustalık:** Her zindanın yıldız puanı (hasar almadan bitirmek, belirli tur sayısında bitirmek).

# 08. Arayüz ve Ekranlar

## Genel Kurallar

- Dikey ekran, referans çözünürlük **720 x 1280**, ölçekleme "canvas_items" + "expand".
- Etkileşimli öğeler en az **88 px** yüksekliğinde (parmakla rahat dokunuş).
- Önemli butonlar ekranın alt %45'inde.
- Her ekrandan en fazla 2 dokunuşla kasabaya dönülebilir (savaş hariç).

## Ekran Akışı

```
Açılış -> Ana Menü -> (ilk kez) Sınıf Seçimi -> Giriş Diyaloğu
                    -> Kasaba
Kasaba -> Zindan Kapısı -> Zindan Haritası -> Savaş / Olay / Hazine / Dinlenme
       -> Demirci | Tüccar | Sınıf Ustası | Çanta
Zindan Haritası -> Patron -> Ödül Ekranı -> Kasaba
Savaş -> Yenilgi Ekranı -> Kasaba
```

## Savaş Ekranı Yerleşimi

```
+----------------------------------+
| [Duraklat]        Oda 3/5        |  Üst çubuk
|                                  |
|   [niyet]  [niyet]  [niyet]      |
|   Düşman1  Düşman2  Düşman3      |  Düşman alanı (%35)
|   ███░░░   ██████   ████░░       |  Can çubukları + durum ikonları
|                                  |
|         KOMBO x2!                |  Geri bildirim alanı
|                                  |
|   Oyuncu (sırtı dönük)           |  Oyuncu alanı (%15)
|   CAN ██████████░░  120/140      |
|   ÖFKE ████░░░░░░    40/100      |
+----------------------------------+
| [Yetenek 1] [Yetenek 2]          |
| [Yetenek 3] [Yetenek 4]          |  Aksiyon alanı (%35)
| [Savun]            [Çanta]       |
+----------------------------------+
```

- Yetenek butonları: ikon, isim, maliyet, bekleme sayacı. Kullanılamıyorsa gri.
- **Kombo ipucu:** Hedefte bir bitiricinin aradığı durum varsa o yeteneğin butonu parlar. (Öğrenmeyi kolaylaştıran en önemli arayüz özelliği.)
- Butona **basılı tutmak** yetenek açıklamasını gösterir.
- Birden fazla düşman varsa: önce yeteneğe dokun, sonra hedefe dokun. Tek hedefli yeteneklerde son seçilen hedef hatırlanır.
- Düşmana basılı tutmak: istatistik, zayıflık ve durum paneli.

## Diğer Ekranlar

- **Kasaba:** Tek ekran, binalar dokunulabilir (dokununca hafifçe esner). Üstte kasaba adı, altın, Ejder Pulu, iksir, sınıf/seviye ve XP çubuğu. Altta sabit çubuk: Çanta ve "Zindana Gir". Açılmamış binalar (Sınıf Ustası, Han) soluk ve "Yakında" yazılı. Zindan Kapısı'nda Bekçi Tozlu zindan kartını gösterir (seviye aralığı, koşu sayısı, temizlendi yıldızı, yanına alınacak iksir). Yarım kalan koşu varsa açılışta "Devam Et / Kasabaya Dön" sorulur.
- **Demirci / Tüccar:** Üstte NPC portresi ve konuşma balonu. Demircide seçilen eşyanın bir sonraki kademesi mevcut hâline göre yeşil oklarla gösterilir, altında altın/pul maliyeti ve "Güçlendir". Tüccarda iksir satırı ve 3 eşya kartı; her kart kuşanılı eşyaya göre karşılaştırmalı, fiyat butonu sağda.
- **Zindan Haritası:** Üstte zindan adı ve 5 odalık iz (geçilen odaların ikonları, sonda patron tacı). Altında oyuncu kartı: can, XP, iksir ve altın. Ortada iki kapı kartı: kapı çizimi, oda ikonu, oda adı, kısa ipucu ve savaş odalarında seviye/düşman sayısı. Son odada tek, kırmızı parlayan patron kapısı. Altta "Kaç" butonu (onay ister). Hazine, olay ve dinlenme odaları çizimli bir panelde açılır; koşu sonunda özet paneli çıkar.
- **Çanta / Karakter:** Üstte karakter ve ekipmanla birlikte istatistikleri, altında 4 ekipman slotu (boş slotta soluk siluet), ortada seçilen eşyanın kartı, altta 5 sütunlu çanta ızgarası (yeni ganimet en üstte). Eşyaya dokununca karşılaştırma kartı (yeşil ▲ / kırmızı ▼ farklar), "Kuşan" ve "Parçala" (onay ister). Eşya çerçevesi nadirlik renginde; epik ve efsanevi hafifçe parlar, güçlendirme "+N" rozetiyle gösterilir.
- **Ganimet:** Savaştan sonra bulunan eşya, nadirlik renginde çerçeveli bir kartla haritanın üstünde belirir. Hazine ve Kurukafa eşyayı kendi panelinde gösterir. Koşu özetinde bulunan eşyalar sıralanır; çanta doluysa kaç eşyanın parçalandığı yazılır.
- **Ödül Ekranı:** Kazanılan XP çubuğu dolar, eşyalar tek tek kart olarak açılır (nadirlik rengiyle).

## Geri Bildirim (Oyun Hissi)

- Hasar sayıları yukarı zıplayıp kaybolur; kritik büyük ve sarı.
- Vuruşta 0.05 sn ekran titremesi ve düşman beyaz yanıp söner.
- Kombo yazısı ekran ortasında büyüyerek belirir, kombo sayısıyla renk değişir.
- Telefon titreşimi (ayarlardan kapatılabilir) kritik ve kombo vuruşlarında.

## Eğitim (Tutorial)

Ayrı bir eğitim bölümü yok. İlk savaş yönlendirmeli:
1. Tur 1: Sadece Kalkan Kır aktif, ok ile gösterilir.
2. Tur 2: Ağır Vuruş parlar, "Zırhı kırılmış düşmana Ağır Vuruş çok daha fazla hasar verir!"
3. Tur 3'ten sonra serbest.
İlk karşılaşmalarda niyet ikonları için tek satırlık açıklama balonu çıkar.

## Ayarlar

Müzik ve efekt ses seviyesi, titreşim, savaş hızı (1x / 1.5x / 2x), dil.

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

- **Kasaba:** Tek ekran, binalar dokunulabilir. Altta sabit çubuk: Çanta, Karakter, Ayarlar.
- **Zindan Haritası:** Dikey, aşağıdan yukarı ilerleyen düğüm yolu. Her adımda iki kapı ikonu.
- **Çanta / Karakter:** Solda karakter ve 4 ekipman slotu, altta ızgara envanter. Eşyaya dokununca karşılaştırma kartı (yeşil/kırmızı farklar).
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

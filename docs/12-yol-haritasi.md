# 12. Yol Haritası

Her kilometre taşının sonunda oynanabilir bir sürüm olur. Sıra önemlidir: önce savaş eğlenceli olmalı.

## M0: Kurulum
- [x] Godot projesi, klasör yapısı (bkz. 10-teknik-tasarim.md), `.gitignore`
- [x] Autoload iskeletleri: DataDB, GameState, EventBus
- [x] Test çalıştırıcı ve GitHub Actions
- [ ] Android dışa aktarma ayarı, telefonda boş sahne açılıyor

## M1: Savaş Prototipi (En Önemli)
Hedef: Savaşçı, 2 fareye karşı, düz renkli kutularla bile eğlenceli mi?
- [x] `Stats`, `Combatant`, `StatusEffect` sınıfları (yetenekler şimdilik JSON sözlüğü olarak kullanılıyor)
- [x] `DamageCalc` ve testleri
- [x] `CombatEngine` tur akışı ve olay listesi
- [x] `EnemyAI` desen tipi, niyet üretimi
- [x] Savaşçının yetenekleri (prototipte 4 tanesi takılı), tüm durum etkileri
- [x] Kombo sistemi ve testleri
- [x] Basit savaş ekranı: can çubukları, 4 yetenek butonu, niyet ikonları, hasar sayıları
- **Çıkış ölçütü:** Kombo yapmak, yapmamaktan belirgin şekilde iyi hissettiriyor.

## M2: Zindan Koşusu
- [x] `DungeonRun`: 5 oda, dallanan kapılar (oda üretimi koşu sınıfının içinde)
- [x] Zindan haritası ekranı
- [x] Olay, hazine ve dinlenme odaları
- [x] Çürük Mahzen'in tüm düşmanları ve Kemik Kral (2 faz)
- [x] Koşu özeti, XP ve seviye atlama (eşyalı ödül ekranı M3'te)
- [x] Koşu içi kaçış ve ölüm kuralları

## M3: Kasaba ve Ekipman
- [ ] Kasaba ekranı ve binalar
- [ ] `LootGen`: nadirlik, ek özellikler
- [ ] Çanta, ekipman giyme, karşılaştırma kartı
- [ ] Demirci: güçlendirme ve parçalama
- [ ] Tüccar: iksir
- [ ] `SaveManager`: kayıt ve koşu kurtarma

## M4: Görsel ve His (Demo Tamam)
- [x] Savaş ekranı görselleri: karakterler, düşmanlar, arka plan, ikonlar, arayüz teması
- [x] Temel animasyonlar: bekleme salınımı, saldırı atılması, vurulma, ölüm
- [x] Zindan haritası, kapılar, oda ikonları, olay çizimleri, Bekçi / Taklitçi / Kemik Kral
- [ ] Diğer zindanlar ve ekranlar için görseller
- [ ] Ses ve müzik
- [x] Ekran titremesi, kombo efektleri
- [ ] Titreşim
- [ ] Yönlendirmeli ilk savaş (tutorial)
- [ ] Giriş ve Kemik Kral diyalogları
- **DEMO:** 1 sınıf, 1 zindan, 3 düşman + elit + patron. 5-10 kişiye test ettir.

## M5: İçerik Genişlemesi
- [ ] Büyücü ve Haydut (Seri mekaniği dahil)
- [ ] Sınıf Ustası: sınıf değiştirme, yetenek seçme
- [ ] Zindan 2 ve 3 (Mantar Mağarası, Buzlu Geçit)
- [ ] Zindan yıldızları ve Zor mod
- [ ] Denge turu (test verilerine göre `data/` ayarları)

## M6: Yayın
- [ ] Zindan 4 ve 5, hikâyenin sonu
- [ ] Ayarlar, dil altyapısı, erişilebilirlik (yazı boyutu)
- [ ] Google Play kapalı test, geri bildirim
- [ ] Gelir modeli (bkz. 11-gelir-modeli.md)
- [ ] Google Play yayını, ardından iOS

## Sonrası (Sezon 2 Fikirleri)
- Ejder yoldaş: hikâye sonundaki yumurtadan çıkan ve savaşta yardım eden ejder
- 4. sınıf: Ejder Şövalyesi
- Haftalık meydan okuma zindanları
- Yetenek kademe geliştirmeleri

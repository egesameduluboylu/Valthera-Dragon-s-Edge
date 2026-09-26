# 12. Yol Haritası

Her kilometre taşının sonunda oynanabilir bir sürüm olur. Sıra önemlidir: önce savaş eğlenceli olmalı.

## M0: Kurulum
- [x] Godot projesi, klasör yapısı (bkz. 10-teknik-tasarim.md), `.gitignore`
- [x] Autoload iskeletleri: DataDB, GameState, EventBus
- [x] Test çalıştırıcı ve GitHub Actions
- [x] Android dışa aktarma ayarı (bkz. 14-yayin.md)

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
- [x] Kasaba ekranı ve binalar (Zindan Kapısı, Demirci, Tüccar; Sınıf Ustası ve Han "Yakında")
- [x] Eşya üretimi (`Items`): 10 temel eşya, nadirlik, ek özellikler, Kemik Kral'ın Tacı
- [x] Zindandan ganimet: savaş, elit, patron, hazine ve Konuşan Kurukafa
- [x] Çanta, ekipman giyme, karşılaştırma kartı
- [x] Demirci: güçlendirme (+6'dan sonra Ejder Pulu) ve parçalama
- [x] Tüccar: iksir ve her koşudan sonra yenilenen 3 eşya
- [x] `SaveManager` + `Profile`: otomatik kayıt ve yarım kalan koşuyu kurtarma

## M3.5: Pazar ve Benzersiz Eşyalar
- [x] 6 benzersiz eşya ve özel etkileri (can çalma, diken, ilk vuruş, kanama, altın bulma, düşük canda hasar)
- [x] Kuşanma seviyesi
- [x] Maceracı Pazarı: çevrimdışı simülasyon + Supabase ile oyuncular arası (bkz. 13-pazar.md)
- [x] Sunucu testleri (yerel PostgreSQL) ve istemci uçtan uca testi CI'da
- [x] Görsel kalite geçişi: yeniden çizilen karakterler, arka planlar ve işlenmiş arayüz çerçeveleri

## M4: Görsel ve His (Demo Tamam)
- [x] Savaş ekranı görselleri: karakterler, düşmanlar, arka plan, ikonlar, arayüz teması
- [x] Temel animasyonlar: bekleme salınımı, saldırı atılması, vurulma, ölüm
- [x] Zindan haritası, kapılar, oda ikonları, olay çizimleri, Bekçi / Taklitçi / Kemik Kral
- [x] Diğer zindanlar ve ekranlar için görseller
- [x] Ses ve müzik (kodla üretilen efektler ve müzik, `tools/audio`)
- [x] Ekran titremesi, kombo efektleri
- [x] Titreşim
- [x] Yönlendirmeli ilk savaş (Nara ipuçları)
- [x] Giriş ve Kemik Kral diyalogları (tüm zindanların giriş ve bitiş sahneleri)
- **DEMO:** 1 sınıf, 1 zindan, 3 düşman + elit + patron. 5-10 kişiye test ettir.

## M5: İçerik Genişlemesi
- [x] Büyücü ve Haydut (Seri mekaniği dahil)
- [x] Sınıf Ustası: sınıf değiştirme, yetenek seçme
- [x] Zindan 2 ve 3 (Mantar Mağarası, Buzlu Geçit)
- [x] Zindan yıldızları ve Zor mod
- [x] Denge turu (bot testleriyle `data/` ayarları)

## M6: Yayın
- [x] Zindan 4 ve 5, hikâyenin sonu
- [x] Ayarlar: ses, titreşim, savaş hızı, dil (Türkçe ve İngilizce)
- [x] Erişilebilirlik (yazı boyutu)
- [x] Ejder yoldaş: hikâye sonundaki yumurtadan çıkan, büyüyen ve savaşta nefes üfleyen ejder (bkz. 15-ejder-yoldas.md)
- [x] Duman testi: her ekranı gerçek dokunuşlarla baştan sona oynayan CI testi (`tests/smoke`)
- [ ] Google Play kapalı test, geri bildirim
- [ ] Gelir modeli (bkz. 11-gelir-modeli.md)
- [ ] Google Play yayını, ardından iOS

## Sonrası (Sezon 2 Fikirleri)

- 4. sınıf: Ejder Şövalyesi
- Haftalık meydan okuma zindanları
- Yetenek kademe geliştirmeleri

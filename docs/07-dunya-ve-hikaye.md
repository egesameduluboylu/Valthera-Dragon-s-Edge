# 07. Dünya ve Hikâye

## Ton

DragonFable gibi: fantastik ama kendini fazla ciddiye almayan. Kötü adamlar biraz beceriksiz,
kasaba halkı tuhaf, ama ana hikâyenin gerçek bir tehlikesi var. Diyaloglar kısa (en fazla 3 balon).

## Dünya: Valthera

Yüz yıl önce ejderler bir gecede ortadan kayboldu. Onlarla birlikte büyünün çoğu da gitti.
Şimdi zindanlar, ejderlerin bıraktığı büyü artıklarıyla canlanan yaratıklarla dolu.

## Kasaba: Kıvılcımköy

Oyuncunun merkezi. Tek ekranlık, dokunulabilir binalardan oluşur:

| Bina | Karakter | İşlev |
|------|----------|-------|
| Zindan Kapısı | Bekçi Tozlu | Zindan seçimi |
| Demirci | Usta Örs (sağır, bağırarak konuşur) | Güçlendirme, parçalama |
| Tüccar | Madam Pırıl | İksir ve eşya satışı |
| Sınıf Ustası | Yaşlı Kaan | Sınıf öğrenme ve değiştirme, yetenek seçimi |
| Han | Hancı Bulut | Hikâye, günlük görevler (sonra) |

## Ana Karakterler

- **Oyuncu:** Kıvılcımköy'e yeni gelmiş bir maceracı. Konuşmaz (sadece seçimlerle cevap verir).
- **Nara:** Genç bir ejder bilimci. Ejderlerin kaybolmasını araştırıyor, oyuncuyu görevlere yönlendirir.
- **Kül Kanat:** Ejder tarikatının lideri; aslında son ejderin kendisi. Ana kötü (ya da öyle görünen).
- **Kemik Kral:** İlk patron. Aslında sadece mahzende yalnız kalmış, taç takmayı seven bir iskelet.

## Ana Hikâye (5 Bölüm)

1. **Çürük Mahzen:** Nara'nın laboratuvarı hanın mahzeninde. İskeletler ortalığı basmış. Kemik Kral yenilince üzerinden parlayan bir **ejder pulu** çıkar.
2. **Mantar Mağarası:** Pul, mağaradaki bir ejder kalıntısını gösterir. Ana Spor bu kalıntıyla beslenmektedir.
3. **Buzlu Geçit:** Oyuncu ilk canlı ejderle, Soğuk Nefes ile karşılaşır. Ejderler tamamen yok olmamış; saklanıyorlar.
4. **Yanık Kale:** Ejder tarikatı, ejderleri zorla uyandırmak için ritüel yapıyor. Kor Rahibe bunu yönetiyor.
5. **Ejder Yuvası:** Kül Kanat ile yüzleşme. Kül Kanat ejderleri korumak için insanları uzak tuttuğunu söyler. Son: Kül Kanat yenilir, oyuncuya bir **ejder yumurtası** emanet eder. (İkinci sezonun kancası: ejder yoldaş sistemi.)

## Hikâye Anlatımı

- Her zindanın başında ve sonunda kısa bir diyalog sahnesi (karakter portresi + metin balonu).
- Patronların savaş içinde 1-2 repliği var (faz geçişlerinde).
- Tüm metinler `data/text/tr.json` içinde tutulur (ileride İngilizce çeviri için).
- Sahneler `data/story.json` içinde: oyunun girişi (kasabaya ilk gelişte), her zindanın girişi (ilk koşuda) ve sonu (ilk temizlemede). Her sahne bir kez oynar ve kayıtta hatırlanır; "Geç" ile atlanabilir.
- Oyunun sonu: Kül Kanat'ın son repliklerinden sonra "Son... Şimdilik" ekranı ve Ejder Yumurtası.

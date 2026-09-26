# 15. Ejder Yoldaş

Hikâyenin sonunda Kül Kanat oyuncuya son ejder yumurtasını emanet eder (bkz. 07). Bu yumurtadan
çıkan yavru, oyuncunun savaşlarda yanında dövüşen yoldaşı olur. DragonFable'daki ejder yoldaşın
cep sürümüdür: oyunun sonrası için yeni bir hedef ve Zor mod koşularına bir sebep.

## Akış

1. **Yumurta:** Ejder Yuvası ilk kez temizlenince **Ejder Yumurtası** (efsanevi aksesuar) çantaya
   gelir. Yumurta başka her eşya gibi takılabilir, parçalanabilir veya pazarda satılabilir; pazardan
   yumurta alan oyuncu da kendi ejderini çıkarabilir.
2. **Kuluçka:** Kasaba başlığında oyuncu portresinin yanında bir **yuva** butonu belirir (çantada
   yumurta varken veya kuluçka başlamışsa). Yuva panelinde Nara, yumurtayı kuluçkaya yatırmayı
   önerir. "Kuluçkaya Yatır" yumurtayı çantadan alır (takılıysa çıkarır). Bu geri alınamaz; panel
   onay ister.
3. **Isınma:** Yumurta her biten zindan koşusunda (temizlenen, kaçılan veya ölünen) bir ısınır.
   **3 koşu** sonra çatlamaya hazırdır; yuva butonu parlar.
4. **Çıkış:** Yuva panelinde "Yumurta Çatlıyor!" basılınca kısa bir sahne oynar (Nara ve yavru),
   sonra oyuncu ejderin soyunu seçer. Seçim kalıcıdır.
5. **Büyüme:** Ejder, oyuncunun koşularda kazandığı deneyimin **2 katını** alır ve kendi
   seviyesiyle büyür (en fazla 20, oyuncuyla aynı eğri: 05). Seviye 8'de **Genç**, 15'te
   **Yetişkin** olur; her evrede görünüşü değişir ve nefesi güçlenir.

## Soylar

| Soy | Varsayılan ad | Nefes hasarı | Ek etki |
|-----|---------------|--------------|---------|
| Ateş | Köz | ateş | Yanma (2 tur) |
| Ayaz | Kırağı | buz | Donma, 1 yığın (3 yığında sersemletir) |
| Zehir | Sarmaşık | gölge | Zehir, 2 yığın (3 tur) |

Ek etkinin tutma şansı evreye göre artar: Yavru %50, Genç %75, Yetişkin %100. Patronlar
şans tabanlı etkilere normal kurallarla direnebilir (03).

## Savaşta

- Ejder hedef alınamaz ve hasar almaz; oyuncunun arkasında durur.
- Oyuncunun her turu bitince (yetenek, savunma veya iksir) ejderin **nefes sayacı** bir dolar.
  Sayaç **3** olunca ejder bütün düşmanlara nefes üfler ve sayaç sıfırlanır. Sayaç savaştan
  savaşa taşınmaz.
- Nefes hasarı normal hasar formülüyle hesaplanır (03): ejderin saldırısı × evre gücü; düşmanın
  savunması ve element çarpanları geçerlidir, ıskalayabilir, kritik vurabilir (%5).
- Ejder saldırısı: 20 + 1,5 × (seviye − 1). Evre gücü: Yavru 0,6, Genç 0,8, Yetişkin 1,0.
- Can çalma, öldürünce iyileşme gibi oyuncu ekipman etkileri ejder vuruşlarında çalışmaz.
- Savaş ekranında ejderin altında 3 noktalı sayaç görünür; nefes anında ejder öne atılır, ekran
  soy renginde parlar ve düşmanların üstünde hasar sayıları çıkar.

Denge notu: Yetişkin ejder 2 düşmanlı bir savaşta oyuncunun hasarına yaklaşık %20-40 ekler.
Yavru belirgin ama küçük bir yardımdır; ilk büyüme birkaç koşuda gelir.

## Veri

`data/companion.json`: kuluçka koşu sayısı, deneyim çarpanı, sayaç, saldırı büyümesi, evreler
(`from` seviyesi, `power`, `status_chance`) ve soylar (hasar elementi, ek etki, varsayılan ad
anahtarı, görsel yolu). Ejder çizimleri `assets/sprites/companion/<soy>_<evre>.png`,
yuva çizimleri `egg_nest.png` ve `egg_nest_cracked.png` (`tools/art/companion.py`).

## Kayıt

Profilde `companion`:
- `{}`: ejder yok.
- `{"state": "egg", "warmth": 0..3}`: kuluçkada.
- `{"state": "hatched", "element": "fire", "name": "Köz", "level": 1, "xp": 0}`: çıktı.

Koşu başlarken ejderin o anki hâli (`element`, `level`) koşuya kopyalanır ve yarım kalan koşu
kaydına yazılır; koşu sırasında kazanılan ejder deneyimi koşu bitince profile eklenir.
Bozuk veya bilinmeyen değerler yüklemede temizlenir (bilinmeyen soy: ejder yok sayılmaz,
Ateş'e düşer; seviye 1-20 aralığına çekilir).

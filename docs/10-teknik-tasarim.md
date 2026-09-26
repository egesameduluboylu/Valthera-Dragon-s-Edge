# 10. Teknik Tasarım

## Teknoloji

- **Motor:** Godot 4.x (en güncel kararlı sürüm), **GDScript**
- **Hedef:** Android (API 24+) önce, sonra iOS
- **Renderer:** Compatibility (eski telefonlarda en geniş destek)
- **Test:** `tests/run_tests.gd` içindeki küçük test çalıştırıcı (eklenti gerektirmez), GitHub Actions ile her PR'da çalışır
- **Sürüm kontrolü:** Git + GitHub, `.gitignore` Godot şablonu (`.godot/` klasörü hariç tutulur)

## Temel Mimari İlkesi

**Oyun mantığı ile görüntü ayrıdır.** Savaş hesaplamaları sahne ağacına bağlı olmayan saf
GDScript sınıflarında (`RefCounted`) yapılır. Sahneler sadece sonucu gösterir.
Bu sayede savaş sistemi arayüz olmadan test edilebilir ve denge ayarı kolaylaşır.

```
[Veri (JSON)] -> [DataDB] -> [Mantık: CombatEngine] --olaylar--> [Sunum: BattleScene]
                                     ^                                   |
                                     +-------- oyuncu komutları ---------+
```

## Klasör Yapısı

```
valthera-dragons-edge/
├── project.godot
├── docs/                    # Bu dokümanlar
├── data/                    # Tüm oyun verisi (JSON), kodsuz denge ayarı
│   ├── classes.json
│   ├── skills.json
│   ├── statuses.json
│   ├── enemies.json
│   ├── dungeons.json
│   ├── items.json           # taban eşyalar ve ek özellik havuzu
│   ├── events.json          # olay odaları
│   └── text/tr.json
├── assets/
│   ├── sprites/  ui/  icons/  vfx/  fonts/  audio/
│   └── CREDITS.md
├── src/
│   ├── autoload/            # Tekil servisler
│   │   ├── data_db.gd       # JSON'ları yükler, id ile erişim
│   │   ├── game_state.gd    # Oyuncu profili, aktif sınıf, çanta, altın
│   │   ├── save_manager.gd  # Kaydet/yükle
│   │   ├── event_bus.gd     # Global sinyaller
│   │   └── audio_manager.gd
│   ├── core/                # Saf mantık, sahneden bağımsız
│   │   ├── stats.gd
│   │   ├── combatant.gd     # Oyuncu ve düşmanın ortak tabanı
│   │   ├── skill.gd
│   │   ├── status_effect.gd
│   │   ├── damage_calc.gd
│   │   ├── combat_engine.gd # Tur yönetimi, durum makinesi
│   │   ├── enemy_ai.gd      # Niyet seçimi, desenler
│   │   ├── progression.gd   # XP eğrisi, seviye atlama
│   │   ├── dungeon_run.gd   # Bir zindan koşusu: kapılar, odalar, ödüller
│   │   └── loot_gen.gd
│   ├── scenes/
│   │   ├── main_menu/  town/  dungeon/  battle/  inventory/  reward/
│   └── ui/                  # Tekrar kullanılan bileşenler (buton, can çubuğu, eşya kartı)
└── tests/
    ├── run_tests.gd         # godot --headless -s res://tests/run_tests.gd
    ├── test_case.gd         # assert yardımcıları
    ├── test_damage_calc.gd
    ├── test_combat_engine.gd
    ├── test_boss_and_items.gd
    ├── test_dungeon_run.gd
    ├── test_data_integrity.gd  # metin anahtarı, görsel yolu, id kontrolü
    └── test_enemy_ai.gd
```

## Autoload'lar

| Ad | Sorumluluk |
|----|-----------|
| `DataDB` | Açılışta `data/*.json` dosyalarını okur; `DataDB.skill("warrior_heavy_strike")` gibi erişim |
| `GameState` | Oturum boyunca oyuncu verisi. Değiştiğinde `EventBus` üzerinden sinyal |
| `SaveManager` | `user://save.json` dosyasına yazar/okur, sürüm alanı ile göç (migration) |
| `EventBus` | `gold_changed`, `item_added`, `level_up` vb. global sinyaller |
| `AudioManager` | Müzik geçişleri, efekt havuzu |

## Veri Formatı Örnekleri

`data/skills.json`:
```json
{
  "warrior_shield_break": {
    "class": "warrior",
    "name_key": "skill.shield_break",
    "unlock_level": 1,
    "role": "setup",
    "cost": 0,
    "cooldown": 2,
    "power": 0.6,
    "element": "physical",
    "target": "single_enemy",
    "apply_status": [{"id": "armor_break", "turns": 2}]
  },
  "warrior_heavy_strike": {
    "class": "warrior",
    "name_key": "skill.heavy_strike",
    "unlock_level": 2,
    "role": "finisher",
    "cost": 30,
    "cooldown": 0,
    "power": 1.4,
    "element": "physical",
    "target": "single_enemy",
    "combo": {
      "requires_status": "armor_break",
      "multiplier": 1.8,
      "consume": true,
      "apply_status": [{"id": "stun", "turns": 1}]
    }
  }
}
```

`data/enemies.json`:
```json
{
  "cellar_rat": {
    "name_key": "enemy.cellar_rat",
    "sprite": "res://assets/sprites/enemies/rat.png",
    "base": {"hp": 30, "atk": 8, "def": 5, "spd": 12, "crit": 0.05},
    "elements": {"fire": 1.5},
    "xp": 10,
    "gold": [3, 6],
    "ai": {
      "type": "pattern",
      "moves": ["bite", "bite", "gnaw"]
    }
  }
}
```

## Savaş Motoru Durum Makinesi

```
BATTLE_START
   -> TURN_START (durum etkileri işler, kaynak yenilenir, düşman niyetleri belirlenir)
   -> PLAYER_INPUT (komut bekler: yetenek + hedef / savun / çanta)
   -> PLAYER_ACTION (hasar, durumlar, kombo)
   -> ENEMY_ACTIONS (HIZ sırasına göre)
   -> CHECK_END -> (bitmediyse) TURN_START
   -> VICTORY / DEFEAT
```

`CombatEngine` her oyuncu komutunu (`use_skill`, `defend`) oyuncunun yeniden seçim yapması gereken
ana kadar işletir ve olan her şeyi sıralı bir **olay listesi** olarak döndürür. Savaş sahnesi bu listeyi
tek tek oynatır (hasar sayısı, titreme, kombo yazısı). Olay tipleri `src/core/combat_engine.gd` başında
listelenmiştir: `turn_start`, `intents`, `damage`, `status_applied`, `combo`, `battle_end` vb.

```gdscript
var engine := CombatEngine.from_data(DataDB.data, "warrior", 1, "prototype")
var events := engine.start()
events = engine.use_skill("warrior_shield_break", "e0")
```

Rastgelelik tek bir `RandomNumberGenerator` üzerinden, tohum (seed) verilebilir. Testlerde sabit tohum kullanılır.

`DungeonRun` da aynı şekilde saf mantıktır. Harita sahnesi (`src/scenes/dungeon`) kapıları ondan alır,
savaş odalarında `make_battle()` ile motoru kurar ve savaş sahnesini `setup(engine, background)` ile açar.
Savaş bitince sahne `finished` sinyali verir, harita da sonucu `finish_battle(engine)` ile koşuya işler.

```gdscript
var run := DungeonRun.new(DataDB.data, "rotten_cellar", "warrior", 1)
run.start()                 # iki kapı
var room := run.enter(0)    # savaş, hazine, olay, dinlenme veya patron
var engine := run.make_battle()
```

## Kayıt Sistemi

- Dosya: `user://save.json`, her önemli olaydan sonra otomatik kayıt (savaş bitişi, eşya alımı, kasabaya dönüş).
- Koşu ortasında uygulama kapanırsa: koşu durumu (`run_state`) ayrıca kaydedilir, açılışta "Koşuya devam et?" sorulur.
- Şema:

```json
{
  "version": 1,
  "active_class": "warrior",
  "classes": {"warrior": {"level": 3, "xp": 120, "equipped_skills": ["..."]}},
  "gold": 250, "dragon_scales": 2, "crystals": 0,
  "equipment": {"weapon": "item_uid_1", "armor": null, "helm": null, "accessory": null},
  "inventory": [{"uid": "item_uid_1", "base": "rusty_sword", "rarity": "rare", "level": 2, "upgrade": 1, "affixes": []}],
  "dungeons": {"rotten_cellar": {"cleared": true, "stars": 2}},
  "settings": {"music": 0.8, "sfx": 1.0, "vibration": true, "battle_speed": 1.5},
  "run_state": null
}
```

## Performans Hedefleri

- Orta seviye Android telefonda 60 FPS, düşük seviyede 30 FPS
- APK boyutu < 100 MB
- Soğuk açılış < 4 saniye

## Kod Kuralları

- Dosya ve değişken isimleri İngilizce, `snake_case`; sınıflar `PascalCase` (Godot standardı).
- Oyuncuya görünen tüm metinler `tr.json` üzerinden; kod içinde sabit Türkçe metin yok.
- Tüm sayılar `data/` içinde; kod içinde sihirli sayı yok.
- Her `core/` sınıfı için en az bir test.

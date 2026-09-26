# Ses üretici (tools/audio)

Oyunun tüm ses efektleri ve müzikleri koddan sentezlenir (dış asset yok). Çıktı
tamamen deterministiktir: sabit seed'ler, aynı komut her seferinde bayt bayt aynı
dosyaları üretir.

## Yeniden üretme

```sh
python3 -m pip install numpy        # tek bağımlılık
python3 tools/audio/generate.py     # hepsini üretir + doğrular (~20 sn)
python3 tools/audio/generate.py --only hit town   # sadece bazıları
python3 tools/audio/generate.py --verify          # sadece kontrol
```

Müzik uzunluğu değişirse Godot loop noktalarını güncelleyin:

```sh
godot --headless --import                      # .import dosyaları yoksa önce bir kez
python3 tools/audio/generate.py --godot-loops  # music/*.wav.import: loop_mode=2 (Forward), 0..frame sayısı
godot --headless --import                      # yeni ayarlarla tekrar import
```

Not: Godot'nun WAV importer'ında `edit/loop_mode` değerleri şöyle: 0 = Detect From WAV,
1 = Disabled, **2 = Forward**, 3 = Ping-Pong, 4 = Backward.

## Dosyalar

| Modül | İçerik |
|---|---|
| `generate.py` | Giriş noktası: render, mastering (EQ, loudness, limiter), doğrulama, Godot loop yaması |
| `dsp.py` | numpy DSP: osilatörler, FFT/SVF filtreler, reverb, loudness (LUFS benzeri), limiter, WAV yazma |
| `instruments.py` | Karplus-Strong telli, flüt, brass, pad, koro, çan; davul/perküsyon sesleri |
| `sfx.py` | 36 ses efektinin tasarımı (`SFX` tablosu: fonksiyon, seed, loudness trim) |
| `music.py` | Döngüsel sequencer + 5 parça (akor/melodi notaları burada) |

## Format

- SFX: `assets/audio/sfx/<ad>.wav`, 44.1 kHz, 16-bit mono, tepe ≈ -1 dBFS, 200 ms'lik
  pencerede yaklaşık eşit (telefon hoparlörüne göre ağırlıklı) loudness, 100 Hz altı kesik.
- Müzik: `assets/audio/music/<ad>.wav`, 22.05 kHz, 16-bit mono, ≈ -16 LUFS (SFX'in açıkça
  altında), tepe ≤ -1.5 dBFS. Her parça tam bir döngü uzunluğunda dairesel bir tampona
  render edilir; nota kuyrukları, eko ve reverb başa sarılır, yani loop dikişsizdir.

### Ses efektleri

| Dosya | Süre | Açıklama |
|---|---|---|
| ui_click | 0.12 s | yumuşak tahta tık |
| ui_open / ui_close | 0.34 / 0.30 s | kağıt/tahta panel whoosh + tık |
| coin | 0.50 s | altın para şıngırtısı |
| buy | 0.90 s | paralar + kasa "ka-ching" çanı |
| equip | 0.45 s | deri + metal takırtı |
| upgrade | 1.05 s | örs çekici + kıvılcım |
| salvage | 0.85 s | kırılma + paralar |
| level_up | 1.20 s | yükselen parlak arpej fanfarı |
| star | 0.60 s | tek parıltı çanı |
| door_open | 1.20 s | ağır tahta kapı gıcırtısı |
| chest_open | 1.05 s | kapak + parıltı |
| potion | 0.95 s | lıkır lıkır + köpüklü iyileşme |
| heal | 1.00 s | yumuşak yükselen parıltı |
| shield | 0.90 s | metalik parıltılı baloncuk |
| hit | 0.30 s | etli darbe |
| crit | 0.65 s | ağır darbe + çınlama |
| miss | 0.35 s | boşa savuruş |
| combo | 0.85 s | darbe + yükselen çan |
| slash | 0.38 s | kılıç savuruşu |
| stab | 0.26 s | hızlı hançer saplama |
| magic_fire / magic_ice / magic_lightning / magic_shadow | 0.95 / 0.95 / 0.85 / 1.00 s | alev whoomph / kristal çıtırtı / zap / karanlık whoosh |
| poison | 0.90 s | köpüklü tıslama |
| smoke | 0.70 s | puf |
| enemy_attack | 0.60 s | hırıltılı homurtu (filtreli gürültü + alçak ton) |
| enemy_death | 0.95 s | puf + inen ton |
| player_hurt | 0.35 s | kısa "oof" gümlemesi (ses yok) |
| boss_phase | 1.20 s | derin bum + gürleme + uğursuz akor |
| victory | 1.50 s | kısa zafer fanfarı |
| defeat | 1.50 s | kısa hüzünlü inen cümle |
| summon | 1.20 s | ürkütücü yükselen swell |
| stun | 0.95 s | sersem kuş cıvıltısı |
| status_bad | 0.80 s | alçak titrek debuff |

### Müzik (döngü)

| Dosya | Süre | Ton / tempo | Karakter |
|---|---|---|---|
| town | 40.00 s | G majör, 96 bpm, 4/4, 16 ölçü | ud arpejleri, flüt melodisi, def/tef |
| dungeon | 36.00 s | D minör, 80 bpm, 4/4, 12 ölçü | drone, seyrek arp + eko, damla sesleri, koro |
| battle | 43.64 s | A minör, 132 bpm, 4/4, 24 ölçü | sürükleyici bas, davul, brass motif |
| boss | 41.14 s | D minör, 140 bpm, 4/4, 24 ölçü | taiko, gallop bas, "ah" korosu, oktavlı brass |
| ending | 36.00 s | G majör, 80 bpm, 3/4, 16 ölçü | kasabanın motifi, arp, yaylılar, celesta |

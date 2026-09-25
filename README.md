# Valthera: Dragon's Edge

DragonFable'dan ilham alan, sıra tabanlı savaş odaklı, tek elle oynanan bir mobil RPG.
Godot 4 ve GDScript ile geliştiriliyor.

- Tasarım dokümanları: [docs/00-README.md](docs/00-README.md)
- Yol haritası: [docs/12-yol-haritasi.md](docs/12-yol-haritasi.md)

## Çalıştırma

1. [Godot 4.5](https://godotengine.org/download) indir.
2. Godot'da **Import** ile bu klasördeki `project.godot` dosyasını aç.
3. **F5** ile çalıştır. Şimdilik açılışta savaş prototipi başlar (Savaşçı, Mahzen Faresi ve İskelet Muhafız'a karşı).

## Testler

```bash
godot --headless --import
godot --headless -s res://tests/run_tests.gd
```

Savaş kuralları `src/core/` altında sahneden bağımsız yazıldı; tüm denge sayıları `data/*.json` içinde.

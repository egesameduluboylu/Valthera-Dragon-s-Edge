# 14. Yayın (Android)

## Hazır Olanlar

- `export_presets.cfg`: "Android" ön ayarı. Paket adı `com.egesameduluboylu.valthera`, sürüm 0.5 (kod 1), dikey ekran, internet ve titreşim izni, arm64-v8a ve armeabi-v7a.
- Uygulama ikonu ve açılış ekranı: `assets/brand/`, koddan üretilir (`python3 tools/art/brand.py`).
- `project.godot` içinde `import_etc2_astc=true` (Android dışa aktarma bunu ister).
- Anahtar deposu (keystore) şifreleri bu dosyada **yok**. Godot 4 bunları `.godot/export_credentials.cfg` içinde tutar ve o klasör git'e girmez.

## Kendi Bilgisayarında APK Almak

1. Godot 4.5'i aç, Editor > Manage Export Templates ile şablonları indir.
2. Android Studio'yu (veya yalnızca komut satırı araçlarını) kur. Editor Settings > Export > Android > Android SDK Path alanına SDK klasörünü yaz.
3. Project > Export > Android > Export Project. Deneme için "Export With Debug" yeterli; Godot kendi debug anahtarıyla imzalar.
4. APK'yı telefona at ve kur (Ayarlar > Güvenlik > Bilinmeyen kaynaklar izni gerekebilir).

## Google Play İçin

- Play Store APK değil **AAB** ister: ön ayarda `gradle_build/use_gradle_build=true` ve `gradle_build/export_format=1` (AAB) seçilir. Bunun için Android SDK ve Project > Install Android Build Template gerekir.
- Yayın anahtarı: `keytool -genkey -v -keystore valthera-release.keystore -alias valthera -keyalg RSA -keysize 2048 -validity 10000`. Bu dosyayı ve şifresini güvenli bir yerde sakla; kaybolursa güncelleme yayınlanamaz. Repoya koyma.
- Her yeni sürümde `version/code` bir artırılır, `version/name` ve `project.godot` içindeki `config/version` güncellenir.
- Kapalı test için Play Console > Test > Kapalı test kanalına AAB yüklenir, test edenlerin e-postaları eklenir.

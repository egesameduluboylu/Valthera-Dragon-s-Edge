extends Node
## The player's settings (docs/08): sound, vibration, battle speed and language. They live
## in their own file, so wiping the save keeps them. Loaded before DataDB and Audio.

signal changed(key: String)

const PATH := "user://settings.json"
const SPEEDS := [1.0, 1.5, 2.0]
## Languages with a data/text/<id>.json file; the first is the fallback for missing keys.
const LANGUAGES := ["tr", "en"]

var music: float = 0.7
var sfx: float = 0.9
var vibration: bool = true
var battle_speed: float = 1.0
var language: String = ""


func _ready() -> void:
	load_file()
	if language == "":
		language = "tr" if OS.get_locale_language() == "tr" else "en"


func set_value(key: String, value: Variant) -> void:
	match key:
		"music", "sfx":
			value = clampf(float(value), 0.0, 1.0)
		"battle_speed":
			value = float(value) if SPEEDS.has(float(value)) else 1.0
		"language":
			value = str(value) if LANGUAGES.has(str(value)) else LANGUAGES[0]
	set(key, value)
	save_file()
	changed.emit(key)


func load_file() -> void:
	if not FileAccess.file_exists(PATH):
		return
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	if not d is Dictionary:
		return
	music = clampf(float(d.get("music", music)), 0.0, 1.0)
	sfx = clampf(float(d.get("sfx", sfx)), 0.0, 1.0)
	vibration = bool(d.get("vibration", vibration))
	var speed := float(d.get("battle_speed", battle_speed))
	battle_speed = speed if SPEEDS.has(speed) else 1.0
	var lang := str(d.get("language", ""))
	language = lang if LANGUAGES.has(lang) else ""


func save_file() -> void:
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"music": music, "sfx": sfx, "vibration": vibration,
				"battle_speed": battle_speed, "language": language}))

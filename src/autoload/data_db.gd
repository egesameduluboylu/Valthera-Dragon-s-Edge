extends Node
## Loads all JSON game data once and serves it by id.

var data: Dictionary = {}
var text: Dictionary = {}


func _ready() -> void:
	data = DataLoader.load_game_data()
	load_text(Settings.language)


## Loads the text for `lang`; keys it lacks fall back to the first language (Turkish).
func load_text(lang: String) -> void:
	text = DataLoader.load_json("res://data/text/%s.json" % Settings.LANGUAGES[0])
	if lang != Settings.LANGUAGES[0] and FileAccess.file_exists("res://data/text/%s.json" % lang):
		text.merge(DataLoader.load_json("res://data/text/%s.json" % lang), true)


func skill(id: String) -> Dictionary:
	return data["skills"].get(id, {})


func enemy(id: String) -> Dictionary:
	return data["enemies"].get(id, {})


func status(id: String) -> Dictionary:
	return data["statuses"].get(id, {})


## The companion dragon's name: the one the player gave it, or its element's default name.
func dragon_name(state: Dictionary) -> String:
	var n: String = state.get("name", "")
	if n != "":
		return n
	return t(data["companion"]["elements"].get(state.get("element", ""), {}).get("default_name_key", "dragon.title"))


## Player-facing text. Missing keys show up as the key itself so they are easy to spot.
func t(key: String) -> String:
	return text.get(key, key)


## Text with {name} placeholders filled from `args`.
func tf(key: String, args: Dictionary) -> String:
	return t(key).format(args)

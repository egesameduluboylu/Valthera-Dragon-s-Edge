extends TestCase
## Catches broken references in the JSON data: missing text, art or ids.

const TEXT_KEYS := ["name_key", "desc_key", "title_key", "text_key", "label_key", "line_key"]
const PATH_KEYS := ["sprite", "icon", "background", "map_background"]


func test_every_text_key_and_asset_exists() -> void:
	var data := game_data()
	var text := DataLoader.load_json("res://data/text/tr.json")
	for file in data:
		_walk(data[file], file, text)


func test_dungeon_references_exist() -> void:
	var data := game_data()
	for id in data["dungeons"]:
		var d: Dictionary = data["dungeons"][id]
		var groups: Array = d["combat_pool"] + d["elite_pool"] + [{"enemies": d["boss"]}] \
				+ [{"enemies": d["treasure"]["mimic"]}]
		for g in groups:
			for enemy_id in g["enemies"]:
				assert_true(data["enemies"].has(enemy_id), "%s: enemy %s" % [id, enemy_id])
		for ev in d["events"]:
			assert_true(data["events"].has(ev), "%s: event %s" % [id, ev])
	for id in data["events"]:
		assert_true(ResourceLoader.exists("res://assets/events/%s.png" % data["events"][id]["art"]), id)


func test_every_intent_and_status_has_an_icon() -> void:
	var data := game_data()
	for id in data["statuses"]:
		assert_true(ResourceLoader.exists("res://assets/icons/statuses/%s.png" % id), id)
	for id in data["enemies"]:
		for move_id in data["enemies"][id]["moves"]:
			var t: String = data["enemies"][id]["moves"][move_id].get("type", "attack")
			var icon: String = {"multi_attack": "attack", "buff_ally": "buff"}.get(t, t)
			assert_true(ResourceLoader.exists("res://assets/icons/intents/%s.png" % icon), "%s.%s" % [id, move_id])


func _walk(value: Variant, where: String, text: Dictionary) -> void:
	if value is Dictionary:
		for k in value:
			var v: Variant = value[k]
			if k in TEXT_KEYS and v is String and v != "":
				assert_true(text.has(v), "%s: missing text %s" % [where, v])
			elif k in PATH_KEYS and v is String:
				assert_true(ResourceLoader.exists(v), "%s: missing file %s" % [where, v])
			else:
				_walk(v, "%s.%s" % [where, k], text)
	elif value is Array:
		for v in value:
			_walk(v, where, text)


func test_item_data_is_consistent() -> void:
	var items: Dictionary = game_data()["items"]
	for id in items["bases"]:
		assert_true(items["bases"][id]["slot"] in Items.SLOTS, id)
	for id in items["rarity_order"]:
		assert_true(items["rarities"].has(id), id)
	for spec in items["starter"]:
		assert_true(items["bases"].has(spec["base"]), spec["base"])
	for id in items["affixes"]:
		var perk: bool = not id in items["stats"]
		var key: String = ("perk." if perk else "stat.") + id
		assert_eq(items["affixes"][id]["name_key"], key)
	var loot: Dictionary = game_data()["dungeons"]["rotten_cellar"]["loot"]
	for kind in loot:
		var unique: Dictionary = loot[kind].get("unique", {})
		if not unique.is_empty():
			assert_true(items["bases"].has(unique["base"]), unique["base"])


func test_town_art_exists() -> void:
	for id in ["background", "gate", "smith", "merchant", "class_master", "inn", "npc_smith", "npc_merchant", "npc_keeper",
			"npc_innkeeper", "npc_class_master"]:
		assert_true(ResourceLoader.exists("res://assets/town/%s.png" % id), id)
	for id in ["bag", "scale"]:
		assert_true(ResourceLoader.exists("res://assets/icons/items/%s.png" % id), id)


## Tutorial hints (src/ui/tutorial.gd) build their text key from the flag id, and there is
## one class hint per class. Read from the source, since the script needs autoloads.
func test_every_tutorial_hint_has_text() -> void:
	var text := DataLoader.load_json("res://data/text/tr.json")
	var src := FileAccess.get_file_as_string("res://src/ui/tutorial.gd")
	var re := RegEx.create_from_string("\"(tut_[a-z_]+)\"")
	var flags: Array = []
	for m in re.search_all(src):
		if not flags.has(m.get_string(1)):
			flags.append(m.get_string(1))
	assert_true(flags.size() >= 5, "found the FLAGS list")
	for id in game_data()["classes"]:
		assert_true(flags.has("tut_class_" + id), "class hint for " + id)
	for id in flags:
		assert_true(text.has("tut." + id.trim_prefix("tut_")), id)
	for key in ["tut.next", "tut.skip", "npc.nara"]:
		assert_true(text.has(key), key)
	assert_true(ResourceLoader.exists("res://assets/ui/skin/gear_normal.png"), "gear button")
	assert_true(ResourceLoader.exists("res://assets/ui/skin/knob.png"), "slider knob")


## Every language file has the Turkish keys and the same {placeholders} and % tokens.
func test_translations_match_turkish() -> void:
	var tr_text := DataLoader.load_json("res://data/text/tr.json")
	var re := RegEx.create_from_string("\\{[a-z_0-9]+\\}|%[ds%]")
	for lang in ["en"]:
		var other := DataLoader.load_json("res://data/text/%s.json" % lang)
		for key in tr_text:
			if not other.has(key):
				assert_true(false, "%s missing %s" % [lang, key])
				continue
			var a: Array = re.search_all(tr_text[key]).map(func(m: RegExMatch) -> String: return m.get_string())
			var b: Array = re.search_all(other[key]).map(func(m: RegExMatch) -> String: return m.get_string())
			a.sort()
			b.sort()
			assert_eq(b, a, "%s %s placeholders" % [lang, key])


## Every sound the code asks for exists (src/autoload/audio.gd skips missing files quietly).
func test_every_played_sound_exists() -> void:
	var re := RegEx.create_from_string("Audio\\.play\\(\"([a-z_]*[a-z])\"")
	var names := {}
	for dir in ["res://src/scenes/battle", "res://src/scenes/dungeon", "res://src/scenes/town", "res://src/ui",
			"res://src/autoload"]:
		for f in DirAccess.get_files_at(dir):
			if f.ends_with(".gd"):
				for m in re.search_all(FileAccess.get_file_as_string(dir + "/" + f)):
					names[m.get_string(1)] = true
	for id in game_data()["skills"]:
		var element: String = game_data()["skills"][id].get("element", "physical")
		if element != "physical":
			names["magic_" + element] = true
	for n in ["level_up", "stab", "slash", "smoke", "shield"]:
		names[n] = true
	assert_true(names.size() > 20, "found the sounds")
	for n in names:
		assert_true(ResourceLoader.exists("res://assets/audio/sfx/%s.wav" % n), n)
	for track in ["town", "dungeon", "battle", "boss", "ending"]:
		assert_true(ResourceLoader.exists("res://assets/audio/music/%s.wav" % track), track)


func test_every_companion_sprite_exists() -> void:
	var defs: Dictionary = game_data()["companion"]
	for element in defs["elements"]:
		for stage in defs["stages"]:
			var path := Companion.SPRITE % [element, stage["id"]]
			assert_true(ResourceLoader.exists(path), path)
	for path in ["res://assets/sprites/companion/egg_nest.png", "res://assets/sprites/companion/egg_nest_cracked.png"]:
		assert_true(ResourceLoader.exists(path), path)
	for element in defs["elements"]:
		var status: String = defs["elements"][element]["status"]["id"]
		assert_true(game_data()["statuses"].has(status), "%s: status %s" % [element, status])

extends TestCase
## Catches broken references in the JSON data: missing text, art or ids.

const TEXT_KEYS := ["name_key", "desc_key", "title_key", "text_key", "label_key", "line_key"]
const PATH_KEYS := ["sprite", "icon", "background"]


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
			"npc_innkeeper"]:
		assert_true(ResourceLoader.exists("res://assets/town/%s.png" % id), id)
	for id in ["bag", "scale"]:
		assert_true(ResourceLoader.exists("res://assets/icons/items/%s.png" % id), id)

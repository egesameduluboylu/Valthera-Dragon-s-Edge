class_name DataLoader
extends RefCounted
## Reads JSON data files. Kept free of autoloads so core logic and tests can use it directly.


static func load_json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("DataLoader: cannot open %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("DataLoader: %s is not a JSON object" % path)
		return {}
	return parsed


## Loads every game data file into one dictionary.
static func load_game_data(root: String = "res://data") -> Dictionary:
	return {
		"classes": load_json(root + "/classes.json"),
		"skills": load_json(root + "/skills.json"),
		"statuses": load_json(root + "/statuses.json"),
		"enemies": load_json(root + "/enemies.json"),
		"encounters": load_json(root + "/encounters.json"),
		"dungeons": load_json(root + "/dungeons.json"),
		"events": load_json(root + "/events.json"),
		"items": load_json(root + "/items.json"),
	}

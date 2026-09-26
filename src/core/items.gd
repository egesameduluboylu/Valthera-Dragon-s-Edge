class_name Items
extends RefCounted
## Equipment rules (docs/05): item stats, loot rolls, the smith's upgrade and salvage
## prices, and applying worn gear to a combatant. Items are plain dictionaries so they
## save as JSON as-is:
##   {uid, base, rarity, level, upgrade, affixes: [{id, value}]}
## `defs` is items.json.

const SLOTS := ["weapon", "armor", "helm", "accessory"]
const INT_STATS := ["hp", "start_shield"]


## A saved item made safe to use (docs/10): known base, known rarity (else common),
## whole-number level and upgrade, and only affixes with a known id and a finite number.
## Returns {} when the item can't be kept. Keeps `uid` only when it is a non-empty string.
static func clean(item: Variant, defs: Dictionary) -> Dictionary:
	if not item is Dictionary or not defs["bases"].has(str(item.get("base", ""))):
		return {}
	var out := {"base": str(item["base"]),
			"rarity": item.get("rarity", "") if defs["rarities"].has(item.get("rarity", "")) else "common",
			"level": maxi(1, int(as_number(item.get("level"), 1))),
			"upgrade": clampi(int(as_number(item.get("upgrade"), 0)), 0, int(defs.get("max_upgrade", 10))),
			"affixes": []}
	var uid: Variant = item.get("uid")
	if uid is String and uid != "":
		out["uid"] = uid
	var affixes: Variant = item.get("affixes", [])
	if affixes is Array:
		for a in affixes:
			if is_valid_affix(a, defs):
				out["affixes"].append({"id": str(a["id"]), "value": float(a["value"])})
	return out


## `v` as a float when it is a finite number, else `fallback`.
static func as_number(v: Variant, fallback: float) -> float:
	if (v is float or v is int) and is_finite(float(v)):
		return float(v)
	return fallback


## Main stats of an item: base * (1 + 0.12 * level) * rarity multiplier * (1 + 0.08 * upgrade).
## HP and shields are whole numbers; attack and defence keep decimals so every smith
## upgrade shows.
static func main_stats(item: Dictionary, defs: Dictionary) -> Dictionary:
	var base: Dictionary = defs["bases"][item["base"]]
	var rarity: Dictionary = defs["rarities"][item["rarity"]]
	var mult := (1.0 + float(defs["level_growth"]) * int(item["level"])) * float(rarity["mult"]) \
			* (1.0 + float(defs["upgrade_growth"]) * int(item.get("upgrade", 0)))
	var out := {}
	for stat in base["main"]:
		out[stat] = _round_stat(stat, float(base["main"][stat]) * mult)
	return out


## Main stats plus affixes, stats only (perks like start_shield are left out).
static func total_stats(item: Dictionary, defs: Dictionary) -> Dictionary:
	var out := main_stats(item, defs)
	for a in item.get("affixes", []):
		if not is_valid_affix(a, defs):
			continue
		if a["id"] in defs["stats"]:
			out[a["id"]] = _round_stat(a["id"], float(out.get(a["id"], 0)) + float(a["value"]))
	return out


## Special effects: affix perks plus the base's unique effect (legendaries).
static func perks(item: Dictionary, defs: Dictionary) -> Dictionary:
	var out := {}
	for a in item.get("affixes", []):
		if not is_valid_affix(a, defs):
			continue
		if not a["id"] in defs["stats"]:
			out[a["id"]] = float(out.get(a["id"], 0)) + float(a["value"])
	var unique: Dictionary = defs["bases"][item["base"]].get("unique", {})
	for k in unique:
		out[k] = float(out.get(k, 0)) + float(unique[k])
	return out


## An affix is {id, value} with a known id and a finite number as its value. Edited or
## broken saves can hold anything else; such affixes are ignored (and dropped on load).
static func is_valid_affix(a: Variant, defs: Dictionary) -> bool:
	if not a is Dictionary or not defs["affixes"].has(str(a.get("id", ""))):
		return false
	var v: Variant = a.get("value")
	return (v is float or v is int) and is_finite(float(v))


## Adds worn items to a combatant's stats and perks.
static func apply_equipment(c: Combatant, items: Array, defs: Dictionary) -> void:
	for item in items:
		var s := total_stats(item, defs)
		c.stats.hp += int(s.get("hp", 0))
		c.stats.atk += float(s.get("atk", 0))
		c.stats.def += float(s.get("def", 0))
		c.stats.spd += float(s.get("spd", 0))
		c.stats.crit += float(s.get("crit", 0))
		c.stats.dodge = minf(c.stats.dodge + float(s.get("dodge", 0)), 0.3)
		var p := perks(item, defs)
		for k in p:
			c.perks[k] = float(c.perks.get(k, 0)) + float(p[k])


## Sum of the stats of several items, for comparison cards.
static func sum_stats(items: Array, defs: Dictionary) -> Dictionary:
	var out := {}
	for item in items:
		var s := total_stats(item, defs)
		for k in s:
			out[k] = _round_stat(k, float(out.get(k, 0)) + float(s[k]))
	return out


# ---------------------------------------------------------------- loot

## Rolls one item. opts:
##   class_id      only weapons of this class (other slots are shared)
##   min_rarity    e.g. "rare" for elites and bosses
##   legendary     true lets legendary roll (bosses only, docs/05)
##   base          force a base (e.g. the Bone Crown)
##   rarity        force a rarity
static func roll(defs: Dictionary, level: int, rng: RandomNumberGenerator, opts: Dictionary = {}) -> Dictionary:
	var base_id: String = opts.get("base", "")
	if base_id == "":
		var pool: Array = []
		for id in defs["bases"]:
			var b: Dictionary = defs["bases"][id]
			if b.get("drop_only", false) or int(b.get("min_level", 1)) > level:
				continue
			if b.has("class") and opts.has("class_id") and b["class"] != opts["class_id"]:
				continue
			pool.append(id)
		base_id = pool[rng.randi_range(0, pool.size() - 1)]
	var rarity: String = opts.get("rarity", defs["bases"][base_id].get("rarity", ""))
	if rarity == "":
		rarity = _roll_rarity(defs, rng, opts.get("min_rarity", "common"), opts.get("legendary", false))
	var item := {"base": base_id, "rarity": rarity, "level": level, "upgrade": 0, "affixes": []}
	var ids: Array = defs["affixes"].keys()
	for i in int(defs["rarities"][rarity]["affixes"]):
		if ids.is_empty():
			break
		var id: String = ids.pop_at(rng.randi_range(0, ids.size() - 1))
		item["affixes"].append({"id": id, "value": affix_value(defs, id, level, rng)})
	return item


static func affix_value(defs: Dictionary, id: String, level: int, rng: RandomNumberGenerator) -> float:
	var a: Dictionary = defs["affixes"][id]
	var v := rng.randf_range(float(a["range"][0]), float(a["range"][1]))
	if a.get("scales", false):
		v *= 1.0 + float(defs["level_growth"]) * level
	return _round_stat(id, v)


static func _roll_rarity(defs: Dictionary, rng: RandomNumberGenerator, min_rarity: String, legendary: bool) -> String:
	var order: Array = defs["rarity_order"]
	var lo := order.find(min_rarity)
	var total := 0
	for i in range(lo, order.size()):
		var r: Dictionary = defs["rarities"][order[i]]
		if r.get("boss_only", false) and not legendary:
			continue
		total += int(r["weight"])
	var pick := rng.randi_range(1, total)
	for i in range(lo, order.size()):
		var r: Dictionary = defs["rarities"][order[i]]
		if r.get("boss_only", false) and not legendary:
			continue
		pick -= int(r["weight"])
		if pick <= 0:
			return order[i]
	return order[lo]


# ---------------------------------------------------------------- smith and shop

## Cost of the next upgrade: gold = 20 * level * (upgrade + 1), plus 1 dragon scale from +6.
## Empty when the item is at the cap.
static func upgrade_cost(item: Dictionary, defs: Dictionary) -> Dictionary:
	var next := int(item.get("upgrade", 0)) + 1
	if next > int(defs["max_upgrade"]):
		return {}
	var scales := 1 if next >= int(defs["scales_from_upgrade"]) else 0
	return {"gold": 20 * int(item["level"]) * next, "scales": scales}


## What salvaging gives back: some gold, plus scales for epic and legendary items.
static func salvage_value(item: Dictionary, defs: Dictionary) -> Dictionary:
	var tier: int = defs["rarity_order"].find(item["rarity"])
	var gold := 6 * int(item["level"]) * (tier + 1) + 10 * int(item.get("upgrade", 0))
	return {"gold": gold, "scales": maxi(0, tier - 1)}


static func shop_price(item: Dictionary, defs: Dictionary) -> int:
	return salvage_value(item, defs)["gold"] * 4


## Named items with a fixed rarity and a special effect (docs/05 "Benzersiz Eşyalar").
static func is_unique(item: Dictionary, defs: Dictionary) -> bool:
	return defs["bases"][item["base"]].has("unique")


## Level needed to wear an item: a little below the item's own level.
static func wear_level(item: Dictionary, defs: Dictionary) -> int:
	return maxi(1, int(item["level"]) - int(defs.get("wear_level_slack", 0)))


static func rarity_color(item: Dictionary, defs: Dictionary) -> String:
	return defs["rarities"][item["rarity"]]["color"]


static func _round_stat(stat: String, v: float) -> float:
	if stat in INT_STATS:
		return float(maxi(1, roundi(v)))
	return snappedf(v, 0.001)

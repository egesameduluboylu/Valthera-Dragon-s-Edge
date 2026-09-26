class_name Profile
extends RefCounted
## Everything that is saved between sessions (docs/10 "Kayıt Sistemi"): class progress,
## currencies, the bag, worn gear, the merchant's stock and an unfinished run.
## Pure logic, so the town screens and tests share the same rules; GameState wraps one
## Profile and saves it after every change.

const VERSION := 1
const POTION_PRICE := 25
const FREE_POTIONS := 3
const MAX_POTIONS := 6
const SHOP_SIZE := 3

var data: Dictionary
var active_class: String = "warrior"
var classes: Dictionary = {}          # class_id -> {level, xp}
var gold: int = 0
var scales: int = 0
var potions: int = FREE_POTIONS
var inventory: Array = []             # item dictionaries, see Items
var equipment: Dictionary = {}        # slot -> item uid or ""
var shop: Array = []                  # items for sale at the merchant
var dungeons: Dictionary = {}         # dungeon_id -> {runs, cleared}
var run_state: Dictionary = {}        # DungeonRun.to_dict() between rooms, or {}
var market: Dictionary = {}           # offline marketplace: board, own listings, mailbox (LocalMarket)
var player_name: String = ""          # shown on the player's market listings
var next_uid: int = 1


func _init(p_data: Dictionary) -> void:
	data = p_data
	for slot in Items.SLOTS:
		equipment[slot] = ""


## A fresh save: level 1 warrior wearing the starter gear from items.json.
static func new_game(p_data: Dictionary, rng: RandomNumberGenerator = null) -> Profile:
	var p := Profile.new(p_data)
	p.classes = {"warrior": {"level": 1, "xp": 0}}
	for spec in p_data["items"].get("starter", []):
		var item := {"base": spec["base"], "rarity": spec["rarity"], "level": int(spec["level"]),
				"upgrade": 0, "affixes": []}
		p.add_item(item)
		p.equip(item["uid"])
	var r := rng if rng != null else RandomNumberGenerator.new()
	p.restock_shop(r)
	p.player_name = "Maceracı %04d" % r.randi_range(1, 9999)
	LocalMarket.new(p)._turn_over_board(r)
	return p


func defs() -> Dictionary:
	return data["items"]


func level() -> int:
	return int(classes.get(active_class, {}).get("level", 1))


func class_xp() -> int:
	return int(classes.get(active_class, {}).get("xp", 0))


func set_progress(new_level: int, new_xp: int) -> void:
	classes[active_class] = {"level": new_level, "xp": new_xp}


func add_xp(amount: int) -> int:
	var r := Progression.add_xp(level(), class_xp(), amount)
	set_progress(r["level"], r["xp"])
	return r["gained_levels"]


# ---------------------------------------------------------------- bag and gear

func bag_size() -> int:
	return int(defs().get("bag_size", 30))


## Items in the bag that are not worn.
func bag_items() -> Array:
	var worn := equipment.values()
	return inventory.filter(func(i: Dictionary) -> bool: return not i["uid"] in worn)


func get_item(uid: String) -> Dictionary:
	for i in inventory:
		if i["uid"] == uid:
			return i
	return {}


## Adds an item and gives it a uid. With a full bag the item is salvaged instead
## (docs/05). Returns {added: bool, salvaged: {gold, scales}}.
func add_item(item: Dictionary) -> Dictionary:
	item["uid"] = "i%d" % next_uid
	next_uid += 1
	if bag_items().size() >= bag_size():
		var v := Items.salvage_value(item, defs())
		gold += v["gold"]
		scales += v["scales"]
		return {"added": false, "salvaged": v}
	inventory.append(item)
	return {"added": true, "salvaged": {}}


func slot_of(item: Dictionary) -> String:
	return defs()["bases"][item["base"]]["slot"]


func can_equip(item: Dictionary) -> bool:
	return equip_block_reason(item) == ""


## "" when the item can be worn, else "class" or "level".
func equip_block_reason(item: Dictionary) -> String:
	var base: Dictionary = defs()["bases"][item["base"]]
	if base.has("class") and base["class"] != active_class:
		return "class"
	if Items.wear_level(item, defs()) > level():
		return "level"
	return ""


func equipped(slot: String) -> Dictionary:
	return get_item(equipment.get(slot, ""))


func equipped_items() -> Array:
	var out: Array = []
	for slot in Items.SLOTS:
		var item := equipped(slot)
		if not item.is_empty():
			out.append(item)
	return out


func is_equipped(uid: String) -> bool:
	return uid != "" and uid in equipment.values()


## Wears an item; whatever was in that slot goes back to the bag.
func equip(uid: String) -> bool:
	var item := get_item(uid)
	if item.is_empty() or not can_equip(item):
		return false
	equipment[slot_of(item)] = uid
	return true


func unequip(slot: String) -> bool:
	if equipment.get(slot, "") == "" or bag_items().size() >= bag_size():
		return false
	equipment[slot] = ""
	return true


## Breaks down a bag item into gold and scales. Worn items must be taken off first.
func salvage(uid: String) -> Dictionary:
	var item := get_item(uid)
	if item.is_empty() or is_equipped(uid):
		return {}
	var v := Items.salvage_value(item, defs())
	gold += v["gold"]
	scales += v["scales"]
	inventory.erase(item)
	return v


func can_upgrade(uid: String) -> bool:
	var cost := Items.upgrade_cost(get_item(uid), defs()) if not get_item(uid).is_empty() else {}
	return not cost.is_empty() and gold >= cost["gold"] and scales >= cost["scales"]


## The smith never fails (docs/05).
func upgrade(uid: String) -> bool:
	if not can_upgrade(uid):
		return false
	var item := get_item(uid)
	var cost := Items.upgrade_cost(item, defs())
	gold -= cost["gold"]
	scales -= cost["scales"]
	item["upgrade"] = int(item.get("upgrade", 0)) + 1
	return true


## The active class at its level wearing its gear, for the character sheet.
func player() -> Combatant:
	var class_def: Dictionary = data["classes"][active_class]
	var c := Combatant.make_player(active_class, class_def, level(), [])
	Items.apply_equipment(c, equipped_items(), defs())
	c.hp = c.max_hp()
	return c


## Summed stats of the worn gear, optionally with `swap` worn instead of its slot's item.
func gear_stats(swap: Dictionary = {}) -> Dictionary:
	var worn := equipped_items()
	if not swap.is_empty():
		worn = worn.filter(func(i: Dictionary) -> bool: return slot_of(i) != slot_of(swap))
		worn.append(swap)
	return Items.sum_stats(worn, defs())


# ---------------------------------------------------------------- merchant

func buy_potion() -> bool:
	if gold < POTION_PRICE or potions >= MAX_POTIONS:
		return false
	gold -= POTION_PRICE
	potions += 1
	return true


## Three new items for the merchant, at the highest level of the dungeons cleared so far.
func restock_shop(rng: RandomNumberGenerator) -> void:
	shop.clear()
	var lv := clampi(level(), 1, shop_level())
	for i in SHOP_SIZE:
		shop.append(Items.roll(defs(), lv, rng, {"class_id": active_class}))


func shop_level() -> int:
	var lv := 1
	for id in dungeons:
		if dungeons[id].get("cleared", false):
			lv = maxi(lv, int(data["dungeons"][id].get("level_max", 1)))
		else:
			lv = maxi(lv, int(data["dungeons"][id].get("level_min", 1)))
	return lv


func buy_shop_item(index: int) -> bool:
	if index < 0 or index >= shop.size() or bag_items().size() >= bag_size():
		return false
	var price := Items.shop_price(shop[index], defs())
	if gold < price:
		return false
	gold -= price
	add_item(shop.pop_at(index))
	return true


# ---------------------------------------------------------------- dungeon runs

## Starts a run with the worn gear and the potion stock.
func start_run(dungeon_id: String, rng: RandomNumberGenerator = null) -> DungeonRun:
	var gear: Array = []
	for item in equipped_items():
		gear.append(item.duplicate(true))
	var run := DungeonRun.new(data, dungeon_id, active_class, level(), class_xp(), rng, gear)
	run.potions = potions
	return run


## Banks a finished run. Returns what happened to the loot:
## {added: [items], salvaged: {gold, scales, count}}.
func apply_run(run: DungeonRun, rng: RandomNumberGenerator = null) -> Dictionary:
	set_progress(run.level, run.class_xp)
	gold += run.gold_earned
	scales += run.scales_earned
	var added: Array = []
	var salvaged := {"gold": 0, "scales": 0, "count": 0}
	for item in run.loot:
		var r := add_item(item)
		if r["added"]:
			added.append(item)
		else:
			salvaged["gold"] += r["salvaged"]["gold"]
			salvaged["scales"] += r["salvaged"]["scales"]
			salvaged["count"] += 1
	potions = maxi(run.potions, FREE_POTIONS)   # Nara refills the basics in town
	var d: Dictionary = dungeons.get(run.dungeon_id, {"runs": 0, "cleared": false})
	d["runs"] = int(d["runs"]) + 1
	if run.outcome == "cleared":
		d["cleared"] = true
	dungeons[run.dungeon_id] = d
	run_state = {}
	restock_shop(rng if rng != null else RandomNumberGenerator.new())
	return {"added": added, "salvaged": salvaged}


# ---------------------------------------------------------------- save format

func to_dict() -> Dictionary:
	return {
		"version": VERSION,
		"active_class": active_class,
		"classes": classes.duplicate(true),
		"gold": gold, "dragon_scales": scales, "potions": potions,
		"equipment": equipment.duplicate(),
		"inventory": inventory.duplicate(true),
		"shop": shop.duplicate(true),
		"dungeons": dungeons.duplicate(true),
		"run_state": run_state.duplicate(true),
		"market": market.duplicate(true),
		"player_name": player_name,
		"next_uid": next_uid,
	}


static func from_dict(p_data: Dictionary, d: Dictionary) -> Profile:
	var p := Profile.new(p_data)
	p.active_class = d.get("active_class", "warrior")
	p.classes = d.get("classes", {"warrior": {"level": 1, "xp": 0}})
	for id in p.classes:   # JSON numbers load as floats
		p.classes[id] = {"level": int(p.classes[id].get("level", 1)), "xp": int(p.classes[id].get("xp", 0))}
	p.gold = int(d.get("gold", 0))
	p.scales = int(d.get("dragon_scales", 0))
	p.potions = int(d.get("potions", FREE_POTIONS))
	for slot in Items.SLOTS:
		var uid: Variant = d.get("equipment", {}).get(slot, "")
		p.equipment[slot] = uid if uid is String else ""
	p.inventory = _clean_items(d.get("inventory", []), p_data)
	p.shop = _clean_items(d.get("shop", []), p_data)
	var dungeons_: Variant = d.get("dungeons", {})
	if dungeons_ is Dictionary:
		for id in dungeons_:
			if p_data["dungeons"].has(id) and dungeons_[id] is Dictionary:
				p.dungeons[id] = {"runs": int(dungeons_[id].get("runs", 0)),
						"cleared": bool(dungeons_[id].get("cleared", false))}
	p.run_state = d.get("run_state", {}) if d.get("run_state") is Dictionary else {}
	p.next_uid = int(d.get("next_uid", p.inventory.size() + 1))
	p.player_name = str(d.get("player_name", "Maceracı"))
	p.market = _clean_market(d.get("market", {}), p_data)
	return p


static func _clean_market(m: Variant, p_data: Dictionary) -> Dictionary:
	if not m is Dictionary or not m.has("board"):
		return {}
	var out := {"next_id": int(m.get("next_id", 1)), "board": [], "listings": [], "mailbox": []}
	for key in ["board", "listings", "mailbox"]:
		for e in m.get(key, []):
			if not e is Dictionary:
				continue
			if e.has("item"):
				var cleaned := _clean_items([e["item"]], p_data)
				if cleaned.is_empty():
					continue
				e["item"] = cleaned[0]
			for k in ["price", "gold", "runs_left"]:
				if e.has(k):
					e[k] = int(e[k])
			out[key].append(e)
	return out


## Drops items whose base no longer exists and restores int fields.
static func _clean_items(items: Array, p_data: Dictionary) -> Array:
	var out: Array = []
	for i in items:
		if not i is Dictionary or not p_data["items"]["bases"].has(i.get("base", "")):
			continue
		i["level"] = int(i.get("level", 1))
		i["upgrade"] = int(i.get("upgrade", 0))
		if not p_data["items"]["rarities"].has(i.get("rarity", "")):
			i["rarity"] = "common"
		out.append(i)
	return out

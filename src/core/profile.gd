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
const LOADOUT_SIZE := 4

var data: Dictionary
var active_class: String = "warrior"
var classes: Dictionary = {}          # unlocked class_id -> {level, xp}
var loadouts: Dictionary = {}         # class_id -> the 4 skill ids taken into battle
var gold: int = 0
var scales: int = 0
var potions: int = FREE_POTIONS
var inventory: Array = []             # item dictionaries, see Items
var equipment: Dictionary = {}        # slot -> item uid or ""
var shop: Array = []                  # items for sale at the merchant
var dungeons: Dictionary = {}         # dungeon_id -> {runs, cleared, stars: [3 bools], hard_cleared}
var run_state: Dictionary = {}        # DungeonRun.to_dict() between rooms, or {}
var market: Dictionary = {}           # offline marketplace: board, own listings, mailbox (LocalMarket)
var player_name: String = ""          # shown on the player's market listings
var story_seen: Array = []            # story.json scene ids already shown
var save_id: String = ""              # random per new game; the online market keys listed items by it
var online_claims: Dictionary = {}    # online mailbox id -> claim op id, until the reward is applied
var next_uid: int = 1


func _init(p_data: Dictionary) -> void:
	data = p_data
	for slot in Items.SLOTS:
		equipment[slot] = ""


## A fresh save: a level 1 hero of the chosen class wearing the starter gear from
## items.json and the class's starter weapon.
static func new_game(p_data: Dictionary, rng: RandomNumberGenerator = null, class_id: String = "warrior") -> Profile:
	var p := Profile.new(p_data)
	p.active_class = class_id
	p.classes = {class_id: {"level": 1, "xp": 0}}
	for spec in p_data["items"].get("starter", []):
		if p_data["items"]["bases"][spec["base"]].get("slot", "") == "weapon":
			continue
		var item := {"base": spec["base"], "rarity": spec["rarity"], "level": int(spec["level"]),
				"upgrade": 0, "affixes": []}
		p.add_item(item)
		p.equip(item["uid"])
	p._give_starter_weapon(class_id)
	var r := rng if rng != null else RandomNumberGenerator.new()
	p.restock_shop(r)
	p.player_name = "Maceracı %04d" % r.randi_range(1, 9999)
	p.save_id = _new_save_id()
	LocalMarket.new(p)._turn_over_board(r)
	return p


func defs() -> Dictionary:
	return data["items"]


# ---------------------------------------------------------------- classes and skills

## True the first time a story scene should play; marks it as seen.
func take_story(scene_id: String) -> bool:
	if story_seen.has(scene_id):
		return false
	story_seen.append(scene_id)
	return true


func is_unlocked(class_id: String) -> bool:
	return classes.has(class_id)


## Why the Class Master won't teach a class yet: "unlocked", "locked" (clear the first
## dungeon first) or "" when it can be learned now.
func class_unlock_block(class_id: String) -> String:
	if is_unlocked(class_id):
		return "unlocked"
	var need: String = data["classes"][class_id].get("unlock_after", "")
	if need != "" and not dungeons.get(need, {}).get("cleared", false):
		return "locked"
	return ""


func unlock_class(class_id: String) -> bool:
	if class_unlock_block(class_id) != "":
		return false
	classes[class_id] = {"level": 1, "xp": 0}
	_give_starter_weapon(class_id)
	return true


## Makes another unlocked class the active one. Its level, skills and weapon come with
## it; armour and trinkets are shared (docs/04).
func switch_class(class_id: String) -> bool:
	if not is_unlocked(class_id) or not run_state.is_empty():
		return false
	active_class = class_id
	var weapon := equipped("weapon")
	if not weapon.is_empty() and not can_equip(weapon):
		equipment["weapon"] = ""
	if equipped("weapon").is_empty():
		var best := {}
		for item in bag_items():
			if slot_of(item) == "weapon" and can_equip(item) \
					and (best.is_empty() or Items.total_stats(item, defs()).get("atk", 0) > Items.total_stats(best, defs()).get("atk", 0)):
				best = item
		if not best.is_empty():
			equipment["weapon"] = best["uid"]
	return true


func _give_starter_weapon(class_id: String) -> void:
	var base: String = data["classes"][class_id].get("starter_weapon", "")
	if base == "":
		return
	var item := {"base": base, "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}
	add_item(item)
	if active_class == class_id and equipped("weapon").is_empty():
		equip(item["uid"])


## Skills of the active class that its level has unlocked, in data order.
func unlocked_skills(class_id: String = "") -> Array[String]:
	var cls := class_id if class_id != "" else active_class
	var lv := int(classes.get(cls, {}).get("level", 1))
	var out: Array[String] = []
	for id in data["skills"]:
		var d: Dictionary = data["skills"][id]
		if d.get("class", "") == cls and int(d.get("unlock_level", 1)) <= lv:
			out.append(id)
	return out


## The 4 skills taken into battle: the saved choice (dropping anything no longer
## valid), topped up from the starter skills.
func loadout(class_id: String = "") -> Array[String]:
	var cls := class_id if class_id != "" else active_class
	var usable := unlocked_skills(cls)
	var out: Array[String] = []
	for id in loadouts.get(cls, []):
		if usable.has(id) and not out.has(id) and out.size() < LOADOUT_SIZE:
			out.append(id)
	for id in data["classes"][cls].get("starter_skills", []) + usable:
		if out.size() >= LOADOUT_SIZE:
			break
		if usable.has(id) and not out.has(id):
			out.append(id)
	return out


## Swaps skill `new_id` into the active loadout at `slot` (0-3). If it is already in
## the loadout the two slots trade places.
func set_loadout_slot(slot: int, new_id: String) -> bool:
	if slot < 0 or slot >= LOADOUT_SIZE or not unlocked_skills().has(new_id):
		return false
	var cur := loadout()
	var old := cur.find(new_id)
	if old >= 0:
		cur[old] = cur[slot]
	cur[slot] = new_id
	loadouts[active_class] = cur
	return true


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
	var c := Combatant.make_player(active_class, class_def, level(), loadout())
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

## Dungeons open one after another: each needs the one before it cleared.
func dungeon_unlocked(dungeon_id: String) -> bool:
	var need: String = data["dungeons"][dungeon_id].get("unlock_after", "")
	return need == "" or dungeon_cleared(need)


func dungeon_cleared(dungeon_id: String) -> bool:
	return dungeons.get(dungeon_id, {}).get("cleared", false)


func dungeon_stars(dungeon_id: String) -> Array:
	return dungeons.get(dungeon_id, {}).get("stars", [false, false, false])


## Hard mode opens once all three stars are earned (docs/05).
func hard_unlocked(dungeon_id: String) -> bool:
	return not dungeon_stars(dungeon_id).has(false)


## Starts a run with the worn gear and the potion stock.
func start_run(dungeon_id: String, rng: RandomNumberGenerator = null, hard: bool = false) -> DungeonRun:
	var gear: Array = []
	for item in equipped_items():
		gear.append(item.duplicate(true))
	var run := DungeonRun.new(data, dungeon_id, active_class, level(), class_xp(), rng, gear, loadout())
	run.potions = potions
	run.hard = hard and hard_unlocked(dungeon_id)
	return run


## Banks a finished run. Returns what happened to the loot and the stars:
## {added: [items], salvaged: {gold, scales, count}, new_stars: [indexes], reward: item or {}}.
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
	var first_clear: bool = run.outcome == "cleared" and not d.get("cleared", false)
	if run.outcome == "cleared":
		d["cleared"] = true
		if run.hard:
			d["hard_cleared"] = true
	var stars: Array = d.get("stars", [false, false, false]).duplicate()
	var new_stars: Array = []
	var earned := run.stars()
	for i in 3:
		if earned[i] and not stars[i]:
			stars[i] = true
			new_stars.append(i)
	d["stars"] = stars
	dungeons[run.dungeon_id] = d
	# The story's last gift (docs/07): the dragon egg on the first clear of the lair.
	var reward := {}
	var spec: Dictionary = data["dungeons"][run.dungeon_id].get("first_clear_reward", {})
	if first_clear and not spec.is_empty():
		reward = Items.roll(defs(), int(data["dungeons"][run.dungeon_id].get("level_max", 1)),
				rng if rng != null else RandomNumberGenerator.new(), {"base": spec["base"]})
		add_item(reward)
	run_state = {}
	restock_shop(rng if rng != null else RandomNumberGenerator.new())
	return {"added": added, "salvaged": salvaged, "new_stars": new_stars, "first_clear": first_clear, "reward": reward}


# ---------------------------------------------------------------- save format

func to_dict() -> Dictionary:
	return {
		"version": VERSION,
		"active_class": active_class,
		"classes": classes.duplicate(true),
		"loadouts": loadouts.duplicate(true),
		"gold": gold, "dragon_scales": scales, "potions": potions,
		"equipment": equipment.duplicate(),
		"inventory": inventory.duplicate(true),
		"shop": shop.duplicate(true),
		"dungeons": dungeons.duplicate(true),
		"run_state": run_state.duplicate(true),
		"market": market.duplicate(true),
		"player_name": player_name,
		"story_seen": story_seen.duplicate(),
		"save_id": save_id,
		"online_claims": online_claims.duplicate(),
		"next_uid": next_uid,
	}


static func from_dict(p_data: Dictionary, d: Dictionary) -> Profile:
	var p := Profile.new(p_data)
	var classes_: Variant = d.get("classes", {})
	if classes_ is Dictionary:
		for id in classes_:   # JSON numbers load as floats
			if p_data["classes"].has(id) and classes_[id] is Dictionary:
				p.classes[id] = {"level": int(classes_[id].get("level", 1)), "xp": int(classes_[id].get("xp", 0))}
	if p.classes.is_empty():
		p.classes = {"warrior": {"level": 1, "xp": 0}}
	p.active_class = str(d.get("active_class", "warrior"))
	if not p.classes.has(p.active_class):
		p.active_class = p.classes.keys()[0]
	var loadouts_: Variant = d.get("loadouts", {})
	if loadouts_ is Dictionary:
		for id in loadouts_:
			if p.classes.has(id) and loadouts_[id] is Array:
				p.loadouts[id] = loadouts_[id].map(func(x: Variant) -> String: return str(x))
	p.gold = int(d.get("gold", 0))
	p.scales = int(d.get("dragon_scales", 0))
	p.potions = int(d.get("potions", FREE_POTIONS))
	p.next_uid = maxi(1, int(Items.as_number(d.get("next_uid"), 1)))
	p.inventory = p._clean_inventory(d.get("inventory", []))
	p.shop = _clean_items(d.get("shop", []), p_data)
	# Rebuild what is worn: each slot keeps an item only if it exists, fits that
	# slot and class, and isn't already worn somewhere else.
	var saved_eq: Variant = d.get("equipment", {})
	for slot in Items.SLOTS:
		var uid: Variant = saved_eq.get(slot, "") if saved_eq is Dictionary else ""
		var item := p.get_item(uid) if uid is String and uid != "" else {}
		var ok: bool = not item.is_empty() and p.slot_of(item) == slot and p.can_equip(item) \
				and not uid in p.equipment.values()
		p.equipment[slot] = uid if ok else ""
	var dungeons_: Variant = d.get("dungeons", {})
	if dungeons_ is Dictionary:
		for id in dungeons_:
			if p_data["dungeons"].has(id) and dungeons_[id] is Dictionary:
				var stars_: Variant = dungeons_[id].get("stars", [])
				var stars: Array = []
				for i in 3:
					stars.append(stars_ is Array and i < stars_.size() and bool(stars_[i]))
				p.dungeons[id] = {"runs": int(dungeons_[id].get("runs", 0)),
						"cleared": bool(dungeons_[id].get("cleared", false)), "stars": stars,
						"hard_cleared": bool(dungeons_[id].get("hard_cleared", false))}
	p.run_state = d.get("run_state", {}) if d.get("run_state") is Dictionary else {}
	p.player_name = str(d.get("player_name", "Maceracı"))
	var seen: Variant = d.get("story_seen", [])
	if seen is Array:
		p.story_seen = seen.map(func(x: Variant) -> String: return str(x))
	p.market = _clean_market(d.get("market", {}), p_data)
	p.save_id = str(d.get("save_id", ""))
	if p.save_id == "":
		p.save_id = _new_save_id()
	var claims: Variant = d.get("online_claims", {})
	if claims is Dictionary:
		for id in claims:
			p.online_claims[str(id)] = str(claims[id])
	return p


## Its own random source, so seeded game rolls stay the same.
static func _new_save_id() -> String:
	return Crypto.new().generate_random_bytes(8).hex_encode()


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


## Drops broken items (Items.clean) and gives every bag item a unique uid: missing or
## repeated ones get a fresh id, and next_uid moves past every id in use.
func _clean_inventory(items: Variant) -> Array:
	var out := _clean_items(items, data)
	for i in out:
		var n := String(i.get("uid", "")).trim_prefix("i")
		if n.is_valid_int():
			next_uid = maxi(next_uid, int(n) + 1)
	var seen := {}
	for i in out:
		if not i.has("uid") or seen.has(i["uid"]):
			i["uid"] = "i%d" % next_uid
			next_uid += 1
		seen[i["uid"]] = true
	return out


## Drops items that can't be used any more (see Items.clean).
static func _clean_items(items: Variant, p_data: Dictionary) -> Array:
	var out: Array = []
	if not items is Array:
		return out
	for i in items:
		var item := Items.clean(i, p_data["items"])
		if not item.is_empty():
			out.append(item)
	return out

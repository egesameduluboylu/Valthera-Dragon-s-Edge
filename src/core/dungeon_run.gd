class_name DungeonRun
extends RefCounted
## One trip through a dungeon (docs/02, docs/06). Pure logic like CombatEngine: the map
## scene asks it for door choices, builds battles through it, and reports results back.
##
## Flow:
##   start() -> choices (two doors, or the boss door in the last room)
##   enter(i) -> the room dictionary; then, depending on room.type:
##     combat / elite / boss: make_battle() ... finish_battle(engine)
##     treasure: open_treasure()  (may turn into a mimic battle)
##     event:    choose_event(i)
##     rest:     rest("heal" | "potion")
##   next_room() -> new choices, or escape() between rooms.

signal leveled_up(level: int)

enum State { CHOOSING, IN_ROOM, FINISHED }

var data: Dictionary
var dungeon_id: String
var def: Dictionary
var rng: RandomNumberGenerator

var player: Combatant
var class_id: String
var level: int
var class_xp: int
var potions: int
var atk_percent: float = 0.0

var room_number: int = 0
var state: State = State.CHOOSING
var choices: Array = []
var room: Dictionary = {}
## Room types in the order they were entered, for the map trail and the summary.
var history: Array[String] = []
## "" while running, then "cleared", "escaped" or "died".
var outcome: String = ""

var gold_earned: int = 0
var xp_earned: int = 0
var gold_lost: int = 0
var kills: int = 0


func _init(p_data: Dictionary, p_dungeon_id: String, p_class_id: String, p_level: int,
		p_class_xp: int = 0, p_rng: RandomNumberGenerator = null) -> void:
	data = p_data
	dungeon_id = p_dungeon_id
	def = data["dungeons"][dungeon_id]
	rng = p_rng if p_rng != null else RandomNumberGenerator.new()
	class_id = p_class_id
	level = p_level
	class_xp = p_class_xp
	potions = int(def.get("potions", 3))
	var class_def: Dictionary = data["classes"][class_id]
	player = Combatant.make_player(class_id, class_def, level, class_def.get("prototype_skills", []))


func room_count() -> int:
	return int(def.get("rooms", 5))


func is_boss_room() -> bool:
	return room_number == room_count()


func start() -> Array:
	room_number = 1
	_roll_choices()
	return choices


func next_room() -> Array:
	if state != State.IN_ROOM or not room.get("done", false) or is_boss_room():
		return []
	room_number += 1
	_roll_choices()
	return choices


## Picks door i and returns the room behind it.
func enter(index: int) -> Dictionary:
	if state != State.CHOOSING or index < 0 or index >= choices.size():
		return {}
	room = choices[index].duplicate(true)
	room["done"] = false
	state = State.IN_ROOM
	history.append(room["type"])
	return room


## Leaves between rooms: loot is kept, but the boss reward is lost (docs/02).
func escape() -> void:
	if outcome != "" or (state == State.IN_ROOM and not room.get("done", false)):
		return
	_finish("escaped")


func can_escape() -> bool:
	return outcome == "" and (state == State.CHOOSING or room.get("done", false))


# ---------------------------------------------------------------- battles

func make_battle() -> CombatEngine:
	var engine := CombatEngine.for_enemies(data, player, room.get("enemies", []), int(room.get("level", 1)), rng)
	engine.potions = potions
	return engine


## Takes the result of a finished battle. Returns {xp, gold, levels, healed}.
func finish_battle(engine: CombatEngine) -> Dictionary:
	potions = engine.potions
	player.statuses.clear()
	player.shield = 0
	player.defending = false
	player.cooldowns.clear()
	player.resource = int(player.resource_rules.get("resource_start", 0))
	if not engine.victory:
		_finish("died")
		return {"xp": 0, "gold": 0, "levels": 0}
	for e in engine.enemies:
		if e.summoner == "":
			kills += 1
	var xp := engine.reward_xp
	var gold := engine.reward_gold
	gold_earned += gold
	var levels := _gain_xp(xp)
	# Catching your breath after a won fight (docs/06); the boss room ends the run anyway.
	var healed := _heal(roundi(player.max_hp() * float(def.get("victory_heal_percent", 0.0))))
	room["done"] = true
	if room["type"] == "boss":
		_finish("cleared")
	return {"xp": xp, "gold": gold, "levels": levels, "healed": healed}


# ---------------------------------------------------------------- non-combat rooms

## Opens the chest. Returns {mimic} or {gold, potion}. A mimic turns the room into a battle.
func open_treasure() -> Dictionary:
	if room.get("type", "") != "treasure" or room.get("done", false):
		return {}
	var t: Dictionary = def.get("treasure", {})
	if rng.randf() < float(t.get("mimic_chance", 0.0)):
		room["type"] = "combat"
		room["mimic"] = true
		room["enemies"] = t.get("mimic", ["mimic"])
		return {"mimic": true}
	var range_: Array = t.get("gold", [0, 0])
	var gold := rng.randi_range(int(range_[0]), int(range_[1]))
	var potion := rng.randf() < float(t.get("potion_chance", 0.0))
	gold_earned += gold
	if potion:
		potions += 1
	room["done"] = true
	return {"mimic": false, "gold": gold, "potion": potion}


func rest(option: String) -> Dictionary:
	if room.get("type", "") != "rest" or room.get("done", false):
		return {}
	var r: Dictionary = def.get("rest", {})
	var result := {}
	if option == "potion":
		potions += int(r.get("potions", 1))
		result["potions"] = int(r.get("potions", 1))
	else:
		result["heal"] = _heal(roundi(player.max_hp() * float(r.get("heal_percent", 0.3))))
	room["done"] = true
	return result


func event_def() -> Dictionary:
	return data["events"].get(room.get("event", ""), {})


## Whether event choice i can be picked (e.g. enough gold for the merchant).
func event_choice_available(index: int) -> bool:
	var choices_: Array = event_def().get("choices", [])
	if index < 0 or index >= choices_.size():
		return false
	var req: Dictionary = choices_[index].get("requires", {})
	return gold_earned >= int(req.get("gold", 0))


## Resolves event choice i. Returns {text_key, effects, changes} where changes holds what
## actually happened (hp, gold, potions, atk_percent).
func choose_event(index: int) -> Dictionary:
	if room.get("type", "") != "event" or room.get("done", false) or not event_choice_available(index):
		return {}
	var outcomes: Array = event_def()["choices"][index].get("outcomes", [])
	var pick: Dictionary = _weighted(outcomes)
	var effects: Dictionary = pick.get("effects", {})
	var changes := {}
	if effects.has("heal_percent"):
		changes["hp"] = _heal(roundi(player.max_hp() * float(effects["heal_percent"])))
	if effects.has("hp_percent"):
		changes["hp"] = _hurt(roundi(player.max_hp() * -float(effects["hp_percent"])))
	if effects.has("hp"):
		changes["hp"] = _hurt(-int(effects["hp"]))
	if effects.has("gold"):
		gold_earned += int(effects["gold"])
		changes["gold"] = int(effects["gold"])
	if effects.has("potions"):
		potions += int(effects["potions"])
		changes["potions"] = int(effects["potions"])
	if effects.has("atk_percent"):
		atk_percent += float(effects["atk_percent"])
		_rebuild_stats()
		changes["atk_percent"] = float(effects["atk_percent"])
	room["done"] = true
	return {"text_key": pick.get("text_key", ""), "effects": effects, "changes": changes}


# ---------------------------------------------------------------- internals

func _roll_choices() -> void:
	state = State.CHOOSING
	room = {}
	choices = []
	if is_boss_room():
		choices.append({"type": "boss", "enemies": def.get("boss", []), "level": int(def.get("level_max", 1))})
		return
	var first := _roll_type([])
	var second := _roll_type([first])
	for t in [first, second]:
		choices.append(_make_room(t))


## Rolls a room type by weight, avoiding `exclude` when another type is possible.
func _roll_type(exclude: Array) -> String:
	var weights: Dictionary = def.get("room_weights", {"combat": 1}).duplicate()
	if room_number not in def.get("elite_rooms", []):
		weights.erase("elite")
	# Guarantee the minimum number of battles before the boss (docs/06).
	var fights := history.count("combat") + history.count("elite")
	var rooms_left := room_count() - room_number   # non-boss rooms left, this one included
	if fights + rooms_left <= int(def.get("min_combat_rooms", 0)):
		for k in weights.keys():
			if k != "combat" and k != "elite":
				weights.erase(k)
	for k in exclude:
		if weights.size() > 1:
			weights.erase(k)
	var total := 0
	for k in weights:
		total += int(weights[k])
	var roll := rng.randi_range(1, total)
	for k in weights:
		roll -= int(weights[k])
		if roll <= 0:
			return k
	return "combat"


func _make_room(type: String) -> Dictionary:
	var r := {"type": type, "level": room_level()}
	match type:
		"combat":
			var pool: Array = def.get("combat_pool", []).filter(
					func(c: Dictionary) -> bool: return int(c.get("min_room", 1)) <= room_number)
			r["enemies"] = pool[rng.randi_range(0, pool.size() - 1)]["enemies"]
		"elite":
			var pool: Array = def.get("elite_pool", [])
			r["enemies"] = pool[rng.randi_range(0, pool.size() - 1)]["enemies"]
		"event":
			var evs: Array = def.get("events", [])
			r["event"] = evs[rng.randi_range(0, evs.size() - 1)]
	return r


## Enemy level grows with the room number across the dungeon's range.
func room_level() -> int:
	var lo := int(def.get("level_min", 1))
	var hi := int(def.get("level_max", lo))
	var t := float(room_number - 1) / float(maxi(room_count() - 1, 1))
	return lo + floori((hi - lo) * t)


func _weighted(items: Array) -> Dictionary:
	var total := 0
	for it in items:
		total += int(it.get("weight", 1))
	var roll := rng.randi_range(1, maxi(total, 1))
	for it in items:
		roll -= int(it.get("weight", 1))
		if roll <= 0:
			return it
	return items[0] if not items.is_empty() else {}


func _heal(amount: int) -> int:
	var before := player.hp
	player.hp = mini(player.max_hp(), player.hp + amount)
	return player.hp - before


## Events never kill: HP stops at 1.
func _hurt(amount: int) -> int:
	var before := player.hp
	player.hp = maxi(1, player.hp - amount)
	return player.hp - before


func _gain_xp(amount: int) -> int:
	xp_earned += amount
	var r := Progression.add_xp(level, class_xp, amount)
	class_xp = r["xp"]
	if r["gained_levels"] > 0:
		level = r["level"]
		_rebuild_stats()
		leveled_up.emit(level)
	return r["gained_levels"]


## Recomputes stats for the current level and run bonuses; HP grows with max HP.
func _rebuild_stats() -> void:
	var class_def: Dictionary = data["classes"][class_id]
	var old_max := player.max_hp()
	player.level = level
	player.stats = Stats.from_dict(class_def.get("base", {}), class_def.get("per_level", {}), level)
	player.stats.atk *= 1.0 + atk_percent
	player.hp = clampi(player.hp + player.max_hp() - old_max, 1, player.max_hp())


func _finish(result: String) -> void:
	outcome = result
	state = State.FINISHED
	if result == "died":
		# Death costs half the gold found on this run; XP is kept (docs/02).
		gold_lost = gold_earned / 2
		gold_earned -= gold_lost

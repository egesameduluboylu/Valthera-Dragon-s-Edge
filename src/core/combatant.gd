class_name Combatant
extends RefCounted
## Shared runtime state for the player and enemies during a battle.

var uid: String
var def_id: String
var name_key: String
var is_player: bool = false
var level: int = 1
var stats: Stats
var hp: int
var shield: int = 0
var defending: bool = false

# Class resource (player only).
var resource_id: String = ""
var resource: int = 0
var resource_max: int = 0
var resource_rules: Dictionary = {}

var skills: Array[String] = []
## Equipment effects (docs/05): start_shield, combo_damage, heal_on_kill.
var perks: Dictionary = {}
var cooldowns: Dictionary = {}          # skill_id -> turns left
var statuses: Dictionary = {}           # status_id -> StatusEffect
var elements: Dictionary = {}           # element -> damage multiplier taken
var immune: Array = []

# Enemy only.
var moves: Dictionary = {}
var ai: Dictionary = {}
var ai_index: int = 0
var ai_phase: int = 0
var on_ally_death: Dictionary = {}
## uid of the enemy that summoned this one; summons crumble when it dies.
var summoner: String = ""
var intent: Dictionary = {}
var xp_reward: int = 0
var gold_range: Array = [0, 0]


static func make_player(class_id: String, class_def: Dictionary, level: int, skill_ids: Array) -> Combatant:
	var c := Combatant.new()
	c.uid = "p"
	c.def_id = class_id
	c.name_key = class_def.get("name_key", class_id)
	c.is_player = true
	c.level = level
	c.stats = Stats.from_dict(class_def.get("base", {}), class_def.get("per_level", {}), level)
	c.hp = c.stats.hp
	c.resource_id = class_def.get("resource", "")
	c.resource_max = int(class_def.get("resource_max", 100))
	c.resource = int(class_def.get("resource_start", 0))
	c.resource_rules = class_def
	for id in skill_ids:
		c.skills.append(String(id))
	return c


static func make_enemy(uid_: String, enemy_id: String, enemy_def: Dictionary, level: int) -> Combatant:
	var c := Combatant.new()
	c.uid = uid_
	c.def_id = enemy_id
	c.name_key = enemy_def.get("name_key", enemy_id)
	c.level = level
	c.stats = Stats.for_enemy(enemy_def.get("base", {}), level)
	c.hp = c.stats.hp
	c.elements = enemy_def.get("elements", {})
	c.immune = enemy_def.get("immune", [])
	c.moves = enemy_def.get("moves", {})
	c.ai = enemy_def.get("ai", {})
	c.on_ally_death = enemy_def.get("on_ally_death", {})
	c.xp_reward = int(enemy_def.get("xp", 0)) * level
	c.gold_range = enemy_def.get("gold", [0, 0])
	return c


func is_alive() -> bool:
	return hp > 0


func max_hp() -> int:
	return stats.hp


func hp_ratio() -> float:
	return float(hp) / float(maxi(stats.hp, 1))


func has_status(status_id: String) -> bool:
	return statuses.has(status_id)


func get_status(status_id: String) -> StatusEffect:
	return statuses.get(status_id)


## Stat after status multipliers. status_defs is the statuses.json dictionary.
func effective_atk(status_defs: Dictionary) -> float:
	return stats.atk * _status_mult("atk_mult", status_defs)


func effective_def(status_defs: Dictionary) -> float:
	return stats.def * _status_mult("def_mult", status_defs)


func effective_spd(status_defs: Dictionary) -> float:
	return stats.spd * _status_mult("spd_mult", status_defs)


func element_mult(element: String) -> float:
	return float(elements.get(element, 1.0))


func _status_mult(key: String, status_defs: Dictionary) -> float:
	var m := 1.0
	for id in statuses:
		var d: Dictionary = status_defs.get(id, {})
		if d.has(key):
			m *= float(d[key])
	return m

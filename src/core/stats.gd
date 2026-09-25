class_name Stats
extends RefCounted
## Base combat stats of a combatant. Buffs and debuffs are applied on top by Combatant.

var hp: int = 1
var atk: float = 1.0
var def: float = 0.0
var spd: float = 1.0
var crit: float = 0.0
var dodge: float = 0.0


## Builds stats from a "base" dictionary plus optional per-level growth.
static func from_dict(base: Dictionary, per_level: Dictionary = {}, level: int = 1) -> Stats:
	var s := Stats.new()
	var lv := float(maxi(level, 1) - 1)
	s.hp = roundi(float(base.get("hp", 1)) + float(per_level.get("hp", 0)) * lv)
	s.atk = float(base.get("atk", 1)) + float(per_level.get("atk", 0)) * lv
	s.def = float(base.get("def", 0)) + float(per_level.get("def", 0)) * lv
	s.spd = float(base.get("spd", 1)) + float(per_level.get("spd", 0)) * lv
	s.crit = float(base.get("crit", 0)) + float(per_level.get("crit", 0)) * lv
	s.dodge = minf(float(base.get("dodge", 0)) + float(per_level.get("dodge", 0)) * lv, 0.3)
	return s


## Enemy scaling from docs/06: HP +15%, ATK +10%, DEF +10% per level above 1.
static func for_enemy(base: Dictionary, level: int) -> Stats:
	var s := from_dict(base)
	var lv := float(maxi(level, 1) - 1)
	s.hp = roundi(s.hp * (1.0 + 0.15 * lv))
	s.atk *= 1.0 + 0.10 * lv
	s.def *= 1.0 + 0.10 * lv
	return s

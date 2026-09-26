class_name Companion
extends RefCounted
## The companion dragon (docs/15): hatching, growth and its battle stand-in.
## Pure logic over data/companion.json; the profile keeps the state as a plain dictionary:
##   {}                                                   no dragon
##   {"state": "egg", "warmth": n}                        in the nest
##   {"state": "hatched", "element", "name", "level", "xp"}

const UID := "dragon"
const SPRITE := "res://assets/sprites/companion/%s_%s.png"


## The growth stage for a level: the last stage whose "from" level is reached.
static func stage(defs: Dictionary, level: int) -> Dictionary:
	var out: Dictionary = defs["stages"][0]
	for s in defs["stages"]:
		if level >= int(s["from"]):
			out = s
	return out


static func atk(defs: Dictionary, level: int) -> float:
	return float(defs["atk_base"]) + float(defs["atk_per_level"]) * (level - 1)


static func sprite(element: String, level: int, defs: Dictionary) -> String:
	return SPRITE % [element, stage(defs, level)["id"]]


## Breath damage against a target with no defense, no crit (for the panel).
static func breath_estimate(defs: Dictionary, level: int) -> int:
	return roundi(atk(defs, level) * float(stage(defs, level)["power"]))


static func is_hatched(state: Dictionary) -> bool:
	return state.get("state", "") == "hatched"


## What a run carries into battle: {} when there is no hatched dragon.
static func battle_spec(state: Dictionary) -> Dictionary:
	if not is_hatched(state):
		return {}
	return {"element": state["element"], "level": state["level"]}


## The dragon as a combatant that only attacks: it is never targeted and has no turn of its own.
static func combatant(defs: Dictionary, spec: Dictionary) -> Combatant:
	var level := int(spec.get("level", 1))
	var c := Combatant.new()
	c.uid = UID
	c.def_id = str(spec.get("element", "fire"))
	c.name_key = "dragon.title"
	c.level = level
	c.stats = Stats.new()
	c.stats.hp = 1
	c.stats.atk = atk(defs, level)
	c.stats.crit = float(defs.get("crit", 0.0))
	c.hp = 1
	return c


## Adds run XP (times xp_mult). Returns the levels gained.
static func add_xp(defs: Dictionary, state: Dictionary, run_xp: int) -> int:
	if not is_hatched(state) or run_xp <= 0:
		return 0
	var r := Progression.add_xp(int(state["level"]), int(state["xp"]), roundi(run_xp * float(defs["xp_mult"])))
	state["level"] = r["level"]
	state["xp"] = r["xp"]
	return r["gained_levels"]


## A saved companion state checked against the data; anything unreadable becomes {}.
static func clean(defs: Dictionary, d: Variant) -> Dictionary:
	if not d is Dictionary:
		return {}
	match d.get("state", ""):
		"egg":
			return {"state": "egg", "warmth": clampi(int(Items.as_number(d.get("warmth"), 0)), 0,
					int(defs["hatch_runs"]))}
		"hatched":
			var element := str(d.get("element", ""))
			if not defs["elements"].has(element):
				element = defs["elements"].keys()[0]
			return {"state": "hatched", "element": element,
					"name": str(d.get("name", "")).strip_edges().left(16),
					"level": clampi(int(Items.as_number(d.get("level"), 1)), 1, Progression.MAX_LEVEL),
					"xp": maxi(0, int(Items.as_number(d.get("xp"), 0)))}
	return {}

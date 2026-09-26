class_name Progression
extends RefCounted
## Class XP and levels (docs/05).

const MAX_LEVEL := 20


## XP needed to go from `level` to level + 1.
static func xp_to_next(level: int) -> int:
	return roundi(50.0 * pow(float(level), 1.5))


## Adds XP and returns {level, xp, gained_levels}. XP is the progress inside the level.
static func add_xp(level: int, xp: int, amount: int) -> Dictionary:
	var lv := level
	var cur := xp + amount
	var gained := 0
	while lv < MAX_LEVEL and cur >= xp_to_next(lv):
		cur -= xp_to_next(lv)
		lv += 1
		gained += 1
	if lv >= MAX_LEVEL:
		cur = 0
	return {"level": lv, "xp": cur, "gained_levels": gained}

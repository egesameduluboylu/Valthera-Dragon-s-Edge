class_name EnemyAI
extends RefCounted
## Picks enemy moves. Every behaviour is simple enough to learn in two fights (docs/06).
##
## AI types (enemies.json "ai"):
##   pattern  {pattern: [move, ...]}                 cycles through the list
##   support  {buff_move, solo_move}                 buffs an unbuffed ally, else attacks
##   phased   {phases: [{min_hp, pattern, ...}]}     a pattern per HP phase (bosses)
## A summon move is skipped while its enemy is already at "max_alive".


## Returns the move id the enemy will use next turn.
static func choose_move(e: Combatant, allies_alive: Array[Combatant], status_defs: Dictionary) -> String:
	match e.ai.get("type", "pattern"):
		"support":
			var buff_move: String = e.ai.get("buff_move", "")
			var buff_status := _first_status_id(e.moves.get(buff_move, {}))
			for ally in allies_alive:
				if ally != e and not ally.has_status(buff_status):
					return buff_move
			return e.ai.get("solo_move", buff_move)
		"phased":
			var phases: Array = e.ai.get("phases", [])
			if phases.is_empty():
				return ""
			return _from_pattern(e, phases[mini(e.ai_phase, phases.size() - 1)].get("pattern", []), allies_alive)
		_:
			return _from_pattern(e, e.ai.get("pattern", []), allies_alive)


## Next usable move in the pattern, starting at ai_index. Advances ai_index past skipped moves.
static func _from_pattern(e: Combatant, pattern: Array, allies_alive: Array[Combatant]) -> String:
	if pattern.is_empty():
		return e.moves.keys()[0] if not e.moves.is_empty() else ""
	for i in pattern.size():
		var move_id: String = pattern[posmod(e.ai_index + i, pattern.size())]
		if _usable(e.moves.get(move_id, {}), allies_alive):
			e.ai_index += i
			return move_id
	return pattern[posmod(e.ai_index, pattern.size())]


static func _usable(move: Dictionary, allies_alive: Array[Combatant]) -> bool:
	if move.get("type", "") != "summon":
		return true
	var count := 0
	for a in allies_alive:
		if a.def_id == move.get("enemy", ""):
			count += 1
	return count < int(move.get("max_alive", 1))


## Ally without the buff first; falls back to the caster itself.
static func pick_buff_target(e: Combatant, allies_alive: Array[Combatant], move: Dictionary,
		rng: RandomNumberGenerator) -> Combatant:
	var status_id := _first_status_id(move)
	var candidates: Array[Combatant] = []
	for ally in allies_alive:
		if ally != e and not ally.has_status(status_id):
			candidates.append(ally)
	if candidates.is_empty():
		return e
	return candidates[rng.randi_range(0, candidates.size() - 1)]


static func _first_status_id(move: Dictionary) -> String:
	var specs: Array = move.get("apply_status", [])
	return specs[0].get("id", "") if not specs.is_empty() else ""

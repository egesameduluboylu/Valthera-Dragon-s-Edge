class_name EnemyAI
extends RefCounted
## Picks enemy moves. Every behaviour is simple enough to learn in two fights (docs/06).


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
		_:
			var pattern: Array = e.ai.get("pattern", [])
			if pattern.is_empty():
				return e.moves.keys()[0] if not e.moves.is_empty() else ""
			return pattern[e.ai_index % pattern.size()]


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

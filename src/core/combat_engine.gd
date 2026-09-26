class_name CombatEngine
extends RefCounted
## Turn-based battle rules (docs/03). Pure logic: no nodes, no autoloads.
##
## Each command (start, use_skill, defend) runs the battle forward until the player
## has to choose again, and returns the list of events that happened, in order.
## The battle scene plays those events back as animations.
##
## Event shapes (all have "type"):
##   turn_start {turn}
##   intents {intents: {uid: intent}}
##   skill {source, skill}
##   enemy_move {source, move, move_type}
##   damage {source, target, amount, absorbed, hp, crit, combo, dot}
##   miss {source, target}
##   death {target}
##   status_applied {target, status, turns, stacks}
##   status_removed {target, status}
##   immune {target, status}
##   shield {target, amount, total}
##   resource {target, value}
##   defend {target}
##   skip {target}
##   combo {count}
##   heal {target, amount, hp}
##   item {source, item}
##   summon {source, uid, enemy_id}
##   phase {source, phase, line_key}
##   battle_end {victory, xp, gold}

const COMBO_CHAIN_BONUS := 0.10
const DEFEND_DAMAGE_MULT := 0.5
const POTION_HEAL_PERCENT := 0.35

var skill_defs: Dictionary
var status_defs: Dictionary
## enemies.json, needed when a boss summons adds mid-battle.
var enemy_defs: Dictionary = {}
var rng: RandomNumberGenerator

var player: Combatant
var enemies: Array[Combatant] = []
var turn: int = 0
var combo_count: int = 0
var potions: int = 0
var finished: bool = false
var victory: bool = false
var reward_xp: int = 0
var reward_gold: int = 0

var _acting: Combatant = null
var _events: Array = []
var _next_uid: int = 0


func _init(p_skill_defs: Dictionary, p_status_defs: Dictionary, p_rng: RandomNumberGenerator = null) -> void:
	skill_defs = p_skill_defs
	status_defs = p_status_defs
	rng = p_rng if p_rng != null else RandomNumberGenerator.new()


## Convenience builder: player of class_id vs. an encounter from encounters.json.
static func from_data(data: Dictionary, class_id: String, level: int, encounter_id: String,
		p_rng: RandomNumberGenerator = null) -> CombatEngine:
	var class_def: Dictionary = data["classes"][class_id]
	var engine := CombatEngine.new(data["skills"], data["statuses"], p_rng)
	var p := Combatant.make_player(class_id, class_def, level, class_def.get("prototype_skills", []))
	var enc: Dictionary = data["encounters"][encounter_id]
	return CombatEngine.for_enemies(data, p, enc["enemies"], int(enc.get("level", 1)), p_rng)


## A prepared player (e.g. carrying HP between dungeon rooms) against enemy ids.
static func for_enemies(data: Dictionary, p: Combatant, enemy_ids: Array, level: int,
		p_rng: RandomNumberGenerator = null) -> CombatEngine:
	var engine := CombatEngine.new(data["skills"], data["statuses"], p_rng)
	engine.enemy_defs = data["enemies"]
	var foes: Array[Combatant] = []
	for enemy_id in enemy_ids:
		foes.append(Combatant.make_enemy("e%d" % foes.size(), enemy_id, data["enemies"][enemy_id], level))
	engine.setup(p, foes)
	return engine


func setup(p_player: Combatant, p_enemies: Array[Combatant]) -> void:
	player = p_player
	enemies = p_enemies
	_next_uid = enemies.size()


# ---------------------------------------------------------------- public API

func start() -> Array:
	_events = []
	_start_round()
	return _flush()


func get_combatant(uid: String) -> Combatant:
	if player.uid == uid:
		return player
	for e in enemies:
		if e.uid == uid:
			return e
	return null


func alive_enemies() -> Array[Combatant]:
	var out: Array[Combatant] = []
	for e in enemies:
		if e.is_alive():
			out.append(e)
	return out


## Why a skill can't be used right now, or "" if it can.
func skill_block_reason(skill_id: String) -> String:
	if finished:
		return "finished"
	if not player.skills.has(skill_id):
		return "not_equipped"
	var def: Dictionary = skill_defs.get(skill_id, {})
	if int(player.cooldowns.get(skill_id, 0)) > 0:
		return "cooldown"
	if player.resource < int(def.get("cost", 0)):
		return "resource"
	return ""


func can_use(skill_id: String) -> bool:
	return skill_block_reason(skill_id) == ""


## True when the skill is a finisher and the target carries the status it looks for.
func combo_ready(skill_id: String, target: Combatant) -> bool:
	var combo: Dictionary = skill_defs.get(skill_id, {}).get("combo", {})
	return not combo.is_empty() and target != null and target.has_status(combo.get("requires_status", ""))


func use_skill(skill_id: String, target_uid: String = "") -> Array:
	_events = []
	if not can_use(skill_id):
		return []
	var def: Dictionary = skill_defs[skill_id]
	var targets := _resolve_targets(def, target_uid)
	if targets.is_empty():
		return []

	_acting = player
	_spend_resource(int(def.get("cost", 0)))
	var cd := int(def.get("cooldown", 0))
	if cd > 0:
		player.cooldowns[skill_id] = cd
	_emit({"type": "skill", "source": player.uid, "skill": skill_id})
	_perform_skill(def, targets)
	_end_player_turn(skill_id)
	return _flush()


## Drinks a potion: heals POTION_HEAL_PERCENT of max HP and uses the turn.
func use_potion() -> Array:
	_events = []
	if finished or potions <= 0 or player.hp >= player.max_hp():
		return []
	_acting = player
	potions -= 1
	combo_count = 0
	_emit({"type": "item", "source": player.uid, "item": "potion"})
	_heal(player, roundi(player.max_hp() * POTION_HEAL_PERCENT))
	_end_player_turn("")
	return _flush()


func defend() -> Array:
	_events = []
	if finished:
		return []
	_acting = player
	player.defending = true
	combo_count = 0
	_emit({"type": "defend", "target": player.uid})
	_gain_resource(int(player.resource_rules.get("resource_on_defend", 0)))
	_end_player_turn("")
	return _flush()


# ---------------------------------------------------------------- round flow

func _start_round() -> void:
	turn += 1
	_emit({"type": "turn_start", "turn": turn})
	_acting = player
	player.shield = 0
	player.defending = false
	_tick_dots(player)
	if _check_end():
		return
	_gain_resource(int(player.resource_rules.get("resource_per_turn", 0)))
	_update_intents()


func _end_player_turn(used_skill: String) -> void:
	for id in player.cooldowns.keys():
		if id != used_skill and player.cooldowns[id] > 0:
			player.cooldowns[id] -= 1
	_decay_statuses(player)
	if _check_end():
		return
	_enemy_phase()
	if _check_end():
		return
	_start_round()


func _enemy_phase() -> void:
	var order := alive_enemies()
	order.sort_custom(func(a: Combatant, b: Combatant) -> bool:
		return a.effective_spd(status_defs) > b.effective_spd(status_defs))
	for e in order:
		if not e.is_alive() or not player.is_alive():
			continue
		_acting = e
		e.shield = 0
		_tick_dots(e)
		if not e.is_alive():
			continue
		var stun := e.get_status("stun")
		if stun != null and not stun.skipped:
			stun.skipped = true
			e.ai_index = maxi(e.ai_index, 0)
			_emit({"type": "skip", "target": e.uid})
		else:
			_perform_enemy_move(e)
			e.ai_index += 1
		_decay_statuses(e)
	_acting = null


func _check_end() -> bool:
	if finished:
		return true
	if not player.is_alive():
		finished = true
		victory = false
		_emit({"type": "battle_end", "victory": false, "xp": 0, "gold": 0})
		return true
	if alive_enemies().is_empty():
		finished = true
		victory = true
		var xp := 0
		var gold := 0
		for e in enemies:
			xp += e.xp_reward
			gold += rng.randi_range(int(e.gold_range[0]), int(e.gold_range[1]))
		reward_xp = xp
		reward_gold = gold
		_emit({"type": "battle_end", "victory": true, "xp": xp, "gold": gold})
		return true
	return false


# ---------------------------------------------------------------- player skills

func _resolve_targets(def: Dictionary, target_uid: String) -> Array[Combatant]:
	var out: Array[Combatant] = []
	match def.get("target", "single_enemy"):
		"self":
			out.append(player)
		"all_enemies":
			out = alive_enemies()
		_:
			var t := get_combatant(target_uid)
			if t == null or t.is_player or not t.is_alive():
				var alive := alive_enemies()
				if alive.is_empty():
					return out
				t = alive[0]
			out.append(t)
	return out


func _perform_skill(def: Dictionary, targets: Array[Combatant]) -> void:
	var power := float(def.get("power", 0.0))
	var element: String = def.get("element", "physical")
	var combo: Dictionary = def.get("combo", {})
	var any_combo := false
	var any_hit := false

	for t in targets:
		if t == player:
			for spec in def.get("apply_status", []):
				_apply_status(player, spec, player)
			var pct := float(def.get("shield_max_hp_percent", 0.0))
			if pct > 0.0:
				_add_shield(player, roundi(player.max_hp() * pct))
			continue

		var is_combo := not combo.is_empty() and t.has_status(combo.get("requires_status", ""))
		var mult := 1.0
		if is_combo:
			mult = float(combo.get("multiplier", 1.0))
			if combo.has("low_hp_threshold") and t.hp_ratio() < float(combo["low_hp_threshold"]):
				mult = float(combo.get("low_hp_multiplier", mult))
			mult *= 1.0 + COMBO_CHAIN_BONUS * combo_count

		var hit := true
		if power > 0.0:
			var r := DamageCalc.roll(player, t, power, element, status_defs, rng, mult)
			if r["miss"]:
				hit = false
				_emit({"type": "miss", "source": player.uid, "target": t.uid})
			else:
				_deal_damage(player, t, r["amount"], r["crit"], is_combo, false)
		if not hit:
			continue
		any_hit = true
		if is_combo:
			any_combo = true
			if combo.get("consume", false):
				_remove_status(t, combo["requires_status"])
		if not t.is_alive():
			continue
		if is_combo:
			for spec in combo.get("apply_status", []):
				_apply_status(t, spec, player)
		for spec in def.get("apply_status", []):
			_apply_status(t, spec, player)

	if power > 0.0 and any_hit:
		_gain_resource(int(player.resource_rules.get("resource_on_hit", 0)))
	if any_combo:
		combo_count += 1
		_emit({"type": "combo", "count": combo_count})
	else:
		combo_count = 0


# ---------------------------------------------------------------- enemies

func _update_intents() -> void:
	var intents := {}
	for e in alive_enemies():
		e.intent = _choose_intent(e)
		intents[e.uid] = e.intent
	_emit({"type": "intents", "intents": intents})


func _choose_intent(e: Combatant) -> Dictionary:
	var stun := e.get_status("stun")
	if stun != null and not stun.skipped:
		return {"move": "", "type": "stunned"}
	var move_id := EnemyAI.choose_move(e, alive_enemies(), status_defs)
	var move: Dictionary = e.moves.get(move_id, {})
	var intent := {"move": move_id, "type": move.get("type", "attack")}
	match intent["type"]:
		"attack", "multi_attack":
			intent["type"] = "attack"
			intent["estimate"] = DamageCalc.estimate(e, player, float(move.get("power", 1.0)),
					move.get("element", "physical"), status_defs)
			intent["hits"] = int(move.get("hits", 1))
			intent["heavy"] = move.get("heavy", false)
			if move.has("apply_status"):
				intent["debuff"] = true
		"shield":
			intent["estimate"] = int(move.get("amount", 0))
	return intent


func _perform_enemy_move(e: Combatant) -> void:
	var move_id: String = e.intent.get("move", "")
	if move_id == "":
		move_id = EnemyAI.choose_move(e, alive_enemies(), status_defs)
	var move: Dictionary = e.moves.get(move_id, {})
	var move_type: String = move.get("type", "attack")
	_emit({"type": "enemy_move", "source": e.uid, "move": move_id, "move_type": move_type})
	match move_type:
		"attack", "multi_attack":
			for i in int(move.get("hits", 1)):
				if player.is_alive():
					_enemy_hit(e, move)
			if move.get("stun_self_if_defended", false) and player.defending and e.is_alive():
				# Blocking a telegraphed heavy blow staggers the attacker (docs/06).
				_apply_status(e, {"id": "stun", "turns": 1}, player)
		"summon":
			var enemy_id: String = move.get("enemy", "")
			if enemy_defs.has(enemy_id):
				var add := Combatant.make_enemy("e%d" % _next_uid, enemy_id, enemy_defs[enemy_id], e.level)
				_next_uid += 1
				# Summoned adds give nothing, so a boss fight can't be farmed.
				add.xp_reward = 0
				add.gold_range = [0, 0]
				add.summoner = e.uid
				enemies.append(add)
				_emit({"type": "summon", "source": e.uid, "uid": add.uid, "enemy_id": enemy_id})
		"shield":
			_add_shield(e, int(move.get("amount", 0)))
		"buff_ally":
			var target := EnemyAI.pick_buff_target(e, alive_enemies(), move, rng)
			for spec in move.get("apply_status", []):
				_apply_status(target, spec, e)


func _enemy_hit(e: Combatant, move: Dictionary) -> void:
	var r := DamageCalc.roll(e, player, float(move.get("power", 1.0)),
			move.get("element", "physical"), status_defs, rng)
	if r["miss"]:
		_emit({"type": "miss", "source": e.uid, "target": player.uid})
		return
	var amount: int = r["amount"]
	if player.defending:
		amount = maxi(1, roundi(amount * DEFEND_DAMAGE_MULT))
	_deal_damage(e, player, amount, r["crit"], false, false)
	if player.is_alive():
		for spec in move.get("apply_status", []):
			_apply_status(player, spec, e)


## Bosses with a "phased" AI switch pattern when their HP drops below a threshold.
func _check_phase(e: Combatant) -> void:
	if e.ai.get("type", "") != "phased" or not e.is_alive():
		return
	var phases: Array = e.ai.get("phases", [])
	while e.ai_phase < phases.size() - 1 and e.hp_ratio() < float(phases[e.ai_phase].get("min_hp", 0.0)):
		e.ai_phase += 1
		# The move already shown as the intent still happens; the new pattern starts
		# from its first move on the following turn (after the usual +1).
		e.ai_index = -1
		var phase: Dictionary = phases[e.ai_phase]
		_emit({"type": "phase", "source": e.uid, "phase": e.ai_phase, "line_key": phase.get("line_key", "")})
		for spec in phase.get("on_enter_status", []):
			_apply_status(e, spec, e)


func _on_enemy_death(dead: Combatant) -> void:
	for e in alive_enemies():
		if e.summoner == dead.uid:
			e.hp = 0
			e.statuses.clear()
			e.shield = 0
			_emit({"type": "death", "target": e.uid})
	for e in alive_enemies():
		var heal := int(e.on_ally_death.get("heal", 0))
		if heal > 0:
			_heal(e, heal)


func _heal(target: Combatant, amount: int) -> void:
	var before := target.hp
	target.hp = mini(target.max_hp(), target.hp + amount)
	_emit({"type": "heal", "target": target.uid, "amount": target.hp - before, "hp": target.hp})


# ---------------------------------------------------------------- effects

func _deal_damage(source: Combatant, target: Combatant, amount: int, crit: bool, combo: bool, dot: bool) -> void:
	var absorbed := 0
	if not dot and target.shield > 0:
		absorbed = mini(target.shield, amount)
		target.shield -= absorbed
	var dealt := amount - absorbed
	target.hp = maxi(0, target.hp - dealt)
	_emit({"type": "damage", "source": source.uid if source else "", "target": target.uid,
			"amount": dealt, "absorbed": absorbed, "hp": target.hp,
			"crit": crit, "combo": combo, "dot": dot})
	if target.is_player and dealt > 0 and target.is_alive():
		_gain_resource(int(player.resource_rules.get("resource_on_damaged", 0)))
	if not target.is_alive():
		target.statuses.clear()
		target.shield = 0
		_emit({"type": "death", "target": target.uid})
		if not target.is_player:
			_on_enemy_death(target)
	elif not target.is_player:
		_check_phase(target)


func _apply_status(target: Combatant, spec: Dictionary, source: Combatant) -> void:
	var id: String = spec.get("id", "")
	var d: Dictionary = status_defs.get(id, {})
	if d.is_empty() or not target.is_alive():
		return
	if target.immune.has(id):
		_emit({"type": "immune", "target": target.uid, "status": id})
		return
	var turns := int(spec.get("turns", 1))
	var add_stacks := int(spec.get("stacks", 1))
	var s := target.get_status(id)
	if s != null and d.get("stacks", false):
		# Stackable statuses gain stacks but keep their remaining duration (docs/03).
		s.stacks = mini(s.stacks + add_stacks, int(d.get("max_stacks", 99)))
	else:
		s = StatusEffect.new(id, turns, mini(add_stacks, int(d.get("max_stacks", 99))))
		target.statuses[id] = s
	s.fresh = target == _acting
	if d.get("dot", "") == "atk_percent" and source != null:
		s.dot_amount = maxi(1, roundi(source.effective_atk(status_defs) * float(d.get("dot_value", 0))))
	_emit({"type": "status_applied", "target": target.uid, "status": id, "turns": s.turns, "stacks": s.stacks})

	var stun_at := int(d.get("stun_at_stacks", 0))
	if stun_at > 0 and s.stacks >= stun_at:
		_remove_status(target, id)
		_apply_status(target, {"id": "stun", "turns": 2}, source)


func _remove_status(target: Combatant, id: String) -> void:
	if target.statuses.erase(id):
		_emit({"type": "status_removed", "target": target.uid, "status": id})


func _add_shield(target: Combatant, amount: int) -> void:
	target.shield += amount
	_emit({"type": "shield", "target": target.uid, "amount": amount, "total": target.shield})


func _tick_dots(c: Combatant) -> void:
	for id in c.statuses.keys():
		if not c.is_alive():
			return
		var s: StatusEffect = c.statuses[id]
		var d: Dictionary = status_defs.get(id, {})
		var amount := 0
		match d.get("dot", ""):
			"atk_percent":
				amount = s.dot_amount
			"max_hp_percent":
				amount = maxi(1, roundi(c.max_hp() * float(d.get("dot_value", 0))))
			"per_stack":
				amount = int(d.get("dot_value", 0)) * s.stacks
		if amount > 0:
			_deal_damage(null, c, amount, false, false, true)


## Called at the end of the owner's turn. A status applied during the owner's own turn
## skips its first decay, so "turns" always counts the owner's following turns.
func _decay_statuses(c: Combatant) -> void:
	for id in c.statuses.keys():
		var s: StatusEffect = c.statuses[id]
		if s.fresh:
			s.fresh = false
			continue
		s.turns -= 1
		if s.turns <= 0:
			_remove_status(c, id)


func _gain_resource(amount: int) -> void:
	if amount == 0 or player.resource_max <= 0:
		return
	var before := player.resource
	player.resource = clampi(player.resource + amount, 0, player.resource_max)
	if player.resource != before:
		_emit({"type": "resource", "target": player.uid, "value": player.resource})


func _spend_resource(amount: int) -> void:
	if amount <= 0:
		return
	player.resource -= amount
	_emit({"type": "resource", "target": player.uid, "value": player.resource})


func _emit(ev: Dictionary) -> void:
	_events.append(ev)


func _flush() -> Array:
	var out := _events
	_events = []
	return out

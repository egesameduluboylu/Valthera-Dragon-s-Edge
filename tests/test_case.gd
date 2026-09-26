class_name TestCase
extends RefCounted
## Minimal assertion base for tests/run_tests.gd. Each test file extends this and
## defines methods starting with "test_".

var failures: Array[String] = []
var _current: String = ""


func assert_true(cond: bool, msg: String = "") -> void:
	if not cond:
		_fail("expected true. " + msg)


func assert_false(cond: bool, msg: String = "") -> void:
	if cond:
		_fail("expected false. " + msg)


func assert_eq(actual: Variant, expected: Variant, msg: String = "") -> void:
	if actual != expected:
		_fail("expected %s, got %s. %s" % [str(expected), str(actual), msg])


func assert_between(actual: float, lo: float, hi: float, msg: String = "") -> void:
	if actual < lo or actual > hi:
		_fail("expected %s..%s, got %s. %s" % [lo, hi, actual, msg])


func _fail(msg: String) -> void:
	failures.append("%s: %s" % [_current, msg])


# ---- shared fixtures

static func game_data() -> Dictionary:
	return DataLoader.load_game_data()


static func seeded_rng(seed_value: int = 1) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	return rng


## Warrior vs. the given enemy ids, with crit and dodge disabled so numbers are exact
## except for the 0.9-1.1 variance.
static func make_engine(enemy_ids: Array, seed_value: int = 1) -> CombatEngine:
	var data := game_data()
	var class_def: Dictionary = data["classes"]["warrior"]
	var engine := CombatEngine.new(data["skills"], data["statuses"], seeded_rng(seed_value))
	engine.enemy_defs = data["enemies"]
	var p := Combatant.make_player("warrior", class_def, 1, class_def["starter_skills"])
	p.stats.crit = 0.0
	p.stats.dodge = 0.0
	var foes: Array[Combatant] = []
	for i in enemy_ids.size():
		var e := Combatant.make_enemy("e%d" % i, enemy_ids[i], data["enemies"][enemy_ids[i]], 1)
		e.stats.crit = 0.0
		e.stats.dodge = 0.0
		foes.append(e)
	engine.setup(p, foes)
	return engine


static func events_of(events: Array, type: String) -> Array:
	return events.filter(func(ev: Dictionary) -> bool: return ev["type"] == type)


## Combo bot for any class: the warrior loop below, or the Mage's burn/freeze loop, or
## the Rogue's poison loop using both Flurry actions.
static func class_bot_turn(engine: CombatEngine) -> void:
	match engine.player.def_id:
		"mage":
			_mage_bot_turn(engine)
		"rogue":
			_rogue_bot_turn(engine)
			if engine.in_flurry():
				_rogue_bot_turn(engine)
				if engine.in_flurry():
					engine.end_turn()
		_:
			bot_turn(engine)


static func _bot_target(engine: CombatEngine) -> Combatant:
	var alive := engine.alive_enemies()
	for e in alive:
		if e.is_boss:
			return e
	return alive[0]


static func _mage_bot_turn(engine: CombatEngine) -> void:
	if engine.player.hp_ratio() < 0.35 and engine.potions > 0:
		engine.use_potion()
		return
	if engine.alive_enemies().is_empty():
		return
	var t := _bot_target(engine)
	for s in ["mage_meteor", "mage_flame_burst", "mage_shatter"]:
		if engine.can_use(s) and engine.combo_ready(s, t):
			engine.use_skill(s, t.uid)
			return
	var fire_ok := t.element_mult("fire") >= 1.0 and not t.immune.has("burn")
	if engine.can_use("mage_mana_shield") and engine.player.hp_ratio() < 0.6:
		engine.use_skill("mage_mana_shield")
	elif engine.can_use("mage_chain_lightning") and engine.alive_enemies().size() >= 2:
		engine.use_skill("mage_chain_lightning")
	elif fire_ok and not t.has_status("burn") and engine.can_use("mage_fireball"):
		engine.use_skill("mage_fireball", t.uid)
	elif (not fire_ok or engine.player.resource >= 50) and not t.immune.has("freeze") and engine.can_use("mage_ice_lance"):
		engine.use_skill("mage_ice_lance", t.uid)
	elif engine.can_use("mage_arcane_bolt"):
		engine.use_skill("mage_arcane_bolt", t.uid)
	else:
		engine.defend()


static func _rogue_bot_turn(engine: CombatEngine) -> void:
	if not engine.in_flurry() and engine.player.hp_ratio() < 0.35 and engine.potions > 0:
		engine.use_potion()
		return
	if engine.alive_enemies().is_empty():
		return
	var t := _bot_target(engine)
	var heavy := false
	for e in engine.alive_enemies():
		heavy = heavy or e.intent.get("heavy", false)
	var poisonable := not t.immune.has("poison")
	if heavy and engine.can_use("rogue_smoke_bomb"):
		engine.use_skill("rogue_smoke_bomb")
	elif engine.can_use("rogue_backstab") and engine.combo_ready("rogue_backstab", t):
		engine.use_skill("rogue_backstab", t.uid)
	elif poisonable and (not t.has_status("poison") or t.get_status("poison").stacks < 4) and engine.can_use("rogue_poison_blade"):
		engine.use_skill("rogue_poison_blade", t.uid)
	elif not poisonable and not t.has_status("stun") and engine.can_use("rogue_blind"):
		engine.use_skill("rogue_blind", t.uid)
	elif engine.can_use("rogue_stab"):
		engine.use_skill("rogue_stab", t.uid)
	elif not engine.in_flurry():
		engine.defend()


## Simple combo bot for balance tests: potion when low, otherwise the combo loop on the
## boss (or the first enemy), cleaning up adds with Slash while setups are on cooldown.
static func bot_turn(engine: CombatEngine) -> void:
	if engine.player.hp_ratio() < 0.35 and engine.potions > 0:
		engine.use_potion()
		return
	var alive := engine.alive_enemies()
	if alive.is_empty():
		return
	var target: Combatant = alive[0]
	var add: Combatant = null
	for e in alive:
		if e.def_id == "bone_king":
			target = e
		elif e != target and add == null:
			add = e
	if engine.can_use("warrior_execute") and engine.combo_ready("warrior_execute", target):
		engine.use_skill("warrior_execute", target.uid)
	elif engine.can_use("warrior_heavy_strike") and engine.combo_ready("warrior_heavy_strike", target):
		engine.use_skill("warrior_heavy_strike", target.uid)
	elif engine.can_use("warrior_shield_break"):
		engine.use_skill("warrior_shield_break", target.uid)
	elif add != null and target.def_id == "bone_king":
		engine.use_skill("warrior_slash", add.uid)
	else:
		engine.use_skill("warrior_slash", target.uid)

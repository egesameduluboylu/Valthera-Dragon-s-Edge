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
	var p := Combatant.make_player("warrior", class_def, 1, class_def["prototype_skills"])
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

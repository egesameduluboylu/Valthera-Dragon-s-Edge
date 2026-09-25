extends TestCase


func test_docs_example() -> void:
	# docs/03: SAL 20, power 1.2, SAV 25 -> 19.2 -> 19
	assert_eq(DamageCalc.compute(20.0, 1.2, 25.0, 1.0, 1.0, 1.0, 1.0), 19)


func test_minimum_one_damage() -> void:
	assert_eq(DamageCalc.compute(1.0, 0.1, 1000.0, 0.5, 1.0, 0.9, 1.0), 1)


func test_element_crit_and_extra_multipliers() -> void:
	var base := DamageCalc.compute(20.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0)
	assert_eq(base, 20)
	assert_eq(DamageCalc.compute(20.0, 1.0, 0.0, 1.5, 1.0, 1.0, 1.0), 30, "weakness")
	assert_eq(DamageCalc.compute(20.0, 1.0, 0.0, 1.0, 1.5, 1.0, 1.0), 30, "crit")
	assert_eq(DamageCalc.compute(20.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.8), 36, "combo")


func test_armor_break_halves_defense() -> void:
	var engine := make_engine(["skeleton_guard"])
	var e := engine.enemies[0]
	var before := e.effective_def(engine.status_defs)
	e.statuses["armor_break"] = StatusEffect.new("armor_break", 2)
	assert_eq(e.effective_def(engine.status_defs), before * 0.5)


func test_roll_stays_within_variance() -> void:
	var engine := make_engine(["cellar_rat"])
	var p := engine.player
	var e := engine.enemies[0]
	var expected := DamageCalc.estimate(p, e, 1.0, "physical", engine.status_defs)
	for i in 50:
		var r := DamageCalc.roll(p, e, 1.0, "physical", engine.status_defs, engine.rng)
		assert_false(r["miss"])
		assert_between(r["amount"], floor(expected * 0.9) - 1, ceil(expected * 1.1) + 1)

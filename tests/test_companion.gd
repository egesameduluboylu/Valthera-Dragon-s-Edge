extends TestCase
## The companion dragon (docs/15): nest, warmth, hatching, growth, saving and the breath.


func _profile_with_egg(seed_value: int = 1) -> Profile:
	var p := Profile.new_game(game_data(), seeded_rng(seed_value))
	var egg := {"base": "dragon_egg", "rarity": "legendary", "level": 1, "upgrade": 0, "affixes": []}
	p.add_item(egg)
	return p


func _finish_run(p: Profile, outcome: String = "escaped", xp: int = 0) -> Dictionary:
	var run := p.start_run("rotten_cellar", seeded_rng(5))
	run.outcome = outcome
	run.xp_earned = xp
	return p.apply_run(run, seeded_rng(5))


func _hatched(element: String, level: int) -> Profile:
	var p := _profile_with_egg()
	p.nest_egg()
	p.companion["warmth"] = 3
	p.hatch(element)
	p.companion["level"] = level
	return p


func test_nesting_takes_the_egg_even_when_worn() -> void:
	var p := _profile_with_egg()
	var uid := p.egg_uid()
	assert_true(p.equip(uid))
	assert_true(p.can_nest())
	assert_true(p.nest_egg())
	assert_eq(p.companion, {"state": "egg", "warmth": 0})
	assert_true(p.get_item(uid).is_empty(), "the egg left the inventory")
	assert_eq(p.equipment["accessory"], "", "and its slot")
	assert_false(p.can_nest(), "only one dragon")


func test_no_egg_no_nest() -> void:
	var p := Profile.new_game(game_data(), seeded_rng(1))
	assert_false(p.can_nest())
	assert_false(p.nest_egg())


func test_three_runs_warm_the_egg_whatever_their_outcome() -> void:
	var p := _profile_with_egg()
	p.nest_egg()
	assert_true(_finish_run(p, "died")["egg_warmed"])
	_finish_run(p, "escaped")
	assert_false(p.egg_ready())
	assert_false(p.hatch("fire"), "not ready yet")
	_finish_run(p, "cleared")
	assert_true(p.egg_ready())
	assert_false(_finish_run(p)["egg_warmed"], "warmth stops at the hatch count")
	assert_false(p.hatch("lava"), "unknown element")
	assert_true(p.hatch("frost"))
	assert_eq(p.companion["element"], "frost")
	assert_eq(p.companion["level"], 1)


func test_the_dragon_grows_with_double_run_xp() -> void:
	var p := _hatched("fire", 1)
	var r := _finish_run(p, "cleared", 60)
	# 120 XP: level 1 needs 50, level 2 needs 141
	assert_eq(r["dragon_levels"], 1)
	assert_eq(p.companion["level"], 2)
	assert_eq(p.companion["xp"], 70)


func test_stages_follow_the_level() -> void:
	var defs: Dictionary = game_data()["companion"]
	assert_eq(Companion.stage(defs, 1)["id"], "hatchling")
	assert_eq(Companion.stage(defs, 8)["id"], "young")
	assert_eq(Companion.stage(defs, 20)["id"], "adult")
	assert_eq(Companion.sprite("venom", 15, defs), "res://assets/sprites/companion/venom_adult.png")


func test_companion_survives_save_and_bad_values_are_cleaned() -> void:
	var p := _hatched("venom", 9)
	var back := Profile.from_dict(game_data(), JSON.parse_string(JSON.stringify(p.to_dict())))
	assert_eq(back.companion, p.companion)
	var d := p.to_dict()
	d["companion"] = {"state": "hatched", "element": "lava", "level": 99, "xp": -5, "name": 42}
	var cleaned := Profile.from_dict(game_data(), d).companion
	assert_eq(cleaned["element"], "fire")
	assert_eq(cleaned["level"], Progression.MAX_LEVEL)
	assert_eq(cleaned["xp"], 0)
	d["companion"] = {"state": "egg", "warmth": 50}
	assert_eq(Profile.from_dict(game_data(), d).companion["warmth"], 3)
	d["companion"] = "dragon"
	assert_eq(Profile.from_dict(game_data(), d).companion, {})


func test_runs_carry_the_dragon_into_battles_and_saves() -> void:
	var p := _hatched("fire", 12)
	var run := p.start_run("rotten_cellar", seeded_rng(2))
	assert_eq(run.companion, {"element": "fire", "level": 12})
	run.start()
	var fight := -1
	for i in run.choices.size():
		if run.choices[i]["type"] in ["combat", "elite"]:
			fight = i
	var back := DungeonRun.from_dict(game_data(), JSON.parse_string(JSON.stringify(run.to_dict())))
	assert_eq(back.companion, run.companion, "resumed runs keep the dragon")
	if fight >= 0:
		run.enter(fight)
		var engine := run.make_battle()
		assert_true(engine.companion != null)
		assert_eq(engine.companion.level, 12)
	var egg_only := _profile_with_egg()
	egg_only.nest_egg()
	assert_eq(egg_only.start_run("rotten_cellar", seeded_rng(2)).companion, {}, "an egg does not fight")


func test_breath_hits_every_enemy_on_the_third_turn() -> void:
	var data := game_data()
	var engine := make_engine(["cellar_rat", "cellar_rat"])
	for e in engine.enemies:
		e.hp = 5000
		e.stats.hp = 5000
	engine.player.hp = 5000
	engine.player.stats.hp = 5000
	engine.set_companion(Companion.combatant(data["companion"], {"element": "fire", "level": 15}), data["companion"])
	engine.companion.stats.crit = 0.0
	engine.start()
	var charges: Array = []
	var breaths := 0
	for turn in 3:
		var events := engine.defend()
		for ev in events_of(events, "companion_charge"):
			charges.append(ev["charge"])
		breaths += events_of(events, "companion_breath").size()
		if turn == 2:
			var hits := events_of(events, "damage").filter(func(ev: Dictionary) -> bool: return ev["source"] == Companion.UID)
			var misses := events_of(events, "miss").filter(func(ev: Dictionary) -> bool: return ev["source"] == Companion.UID)
			assert_eq(hits.size() + misses.size(), 2, "both enemies breathed on")
			# adult fire dragon always burns what it hits
			var burns := events_of(events, "status_applied").filter(func(ev: Dictionary) -> bool: return ev["status"] == "burn")
			assert_eq(burns.size(), hits.size())
	assert_eq(charges, [1, 2, 0])
	assert_eq(breaths, 1)


func test_breath_damage_uses_the_formula() -> void:
	var defs: Dictionary = game_data()["companion"]
	# adult at 15: atk 20 + 1.5 * 14 = 41, power 1.0
	assert_eq(Companion.breath_estimate(defs, 15), 41)
	assert_eq(Companion.breath_estimate(defs, 1), 12)


func test_a_breath_can_win_the_battle() -> void:
	var data := game_data()
	var engine := make_engine(["cellar_rat"])
	engine.set_companion(Companion.combatant(data["companion"], {"element": "venom", "level": 20}), data["companion"])
	engine.companion.stats.crit = 0.0
	engine.player.hp = 5000
	engine.player.stats.hp = 5000
	engine.enemies[0].hp = 1
	engine.enemies[0].stats.dodge = 0.0
	engine.start()
	engine.defend()
	engine.defend()
	var events := engine.defend()
	assert_true(engine.finished and engine.victory)
	assert_eq(events_of(events, "battle_end").size(), 1)

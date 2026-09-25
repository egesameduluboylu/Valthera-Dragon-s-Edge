extends TestCase


func test_start_emits_turn_and_intents() -> void:
	var engine := make_engine(["cellar_rat", "skeleton_guard"])
	var ev := engine.start()
	assert_eq(ev[0]["type"], "turn_start")
	var intents: Array = events_of(ev, "intents")
	assert_eq(intents.size(), 1)
	assert_eq(intents[0]["intents"]["e0"]["move"], "bite")
	assert_eq(intents[0]["intents"]["e1"]["move"], "raise_shield")
	assert_true(intents[0]["intents"]["e0"]["estimate"] > 0)


func test_shield_break_then_heavy_strike_is_a_combo() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].stats.hp = 500
	engine.enemies[0].hp = 500
	engine.start()
	engine.use_skill("warrior_shield_break", "e0")
	assert_true(engine.enemies[0].has_status("armor_break"), "armor break still on during next player turn")
	assert_true(engine.combo_ready("warrior_heavy_strike", engine.enemies[0]))

	var ev := engine.use_skill("warrior_heavy_strike", "e0")
	var dmg: Array = events_of(ev, "damage")
	assert_true(dmg[0]["combo"], "heavy strike flagged as combo")
	assert_eq(events_of(ev, "combo")[0]["count"], 1)
	assert_false(engine.enemies[0].has_status("armor_break"), "combo consumed armor break")
	assert_eq(events_of(ev, "skip").size(), 1, "stunned rat skips its action")
	assert_true(engine.enemies[0].has_status("stun"), "stun visible for the next player turn")


func test_combo_chain_into_execute() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].stats.hp = 1000
	engine.enemies[0].hp = 1000
	engine.player.resource = 100
	engine.start()
	engine.use_skill("warrior_shield_break", "e0")
	engine.use_skill("warrior_heavy_strike", "e0")
	var ev := engine.use_skill("warrior_execute", "e0")
	assert_eq(events_of(ev, "combo")[0]["count"], 2)
	# Execute: power 1.6, combo x2.0, chain bonus +10% -> 3.52x ATK before defence.
	var expected := DamageCalc.compute(engine.player.stats.atk, 1.6, engine.enemies[0].stats.def, 1.0, 1.0, 1.0, 2.0 * 1.1)
	assert_between(events_of(ev, "damage")[0]["amount"], expected * 0.89, expected * 1.11)


func test_combo_hits_harder_than_plain_attack() -> void:
	var plain := make_engine(["cellar_rat"], 7)
	plain.enemies[0].hp = 1000
	plain.start()
	plain.use_skill("warrior_slash", "e0")
	plain.use_skill("warrior_slash", "e0")
	var plain_dmg := 1000 - plain.enemies[0].hp

	var combo := make_engine(["cellar_rat"], 7)
	combo.enemies[0].hp = 1000
	combo.start()
	combo.use_skill("warrior_shield_break", "e0")
	combo.use_skill("warrior_heavy_strike", "e0")
	var combo_dmg := 1000 - combo.enemies[0].hp
	assert_true(combo_dmg >= plain_dmg * 1.5, "combo %d vs plain %d" % [combo_dmg, plain_dmg])


func test_non_combo_skill_resets_counter() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.start()
	engine.use_skill("warrior_shield_break", "e0")
	engine.use_skill("warrior_heavy_strike", "e0")
	assert_eq(engine.combo_count, 1)
	engine.use_skill("warrior_slash", "e0")
	assert_eq(engine.combo_count, 0)


func test_cooldown_blocks_for_listed_turns() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.start()
	engine.use_skill("warrior_shield_break", "e0")   # cooldown 2
	assert_eq(engine.skill_block_reason("warrior_shield_break"), "cooldown")
	engine.use_skill("warrior_slash", "e0")
	assert_eq(engine.skill_block_reason("warrior_shield_break"), "cooldown")
	engine.use_skill("warrior_slash", "e0")
	assert_true(engine.can_use("warrior_shield_break"))


func test_not_enough_rage() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.player.resource = 0
	engine.start()
	assert_eq(engine.skill_block_reason("warrior_heavy_strike"), "resource")
	assert_eq(engine.use_skill("warrior_heavy_strike", "e0"), [])


func test_rage_generation() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.start()
	var start: int = engine.player.resource
	engine.use_skill("warrior_slash", "e0")
	# +10 for hitting, +15 for being bitten.
	assert_eq(engine.player.resource, start + 25)


func test_defend_halves_damage_and_gives_rage() -> void:
	var a := make_engine(["cellar_rat"], 3)
	a.start()
	a.use_skill("warrior_shield_break", "e0")
	var hit_plain := a.player.max_hp() - a.player.hp

	var b := make_engine(["cellar_rat"], 3)
	b.start()
	var start_rage: int = b.player.resource
	b.defend()
	var hit_defended := b.player.max_hp() - b.player.hp
	assert_true(hit_defended <= ceili(hit_plain * 0.5) + 1, "defended %d vs plain %d" % [hit_defended, hit_plain])
	assert_eq(b.player.resource, start_rage + 20 + 15)


func test_skeleton_shield_absorbs_then_expires() -> void:
	var engine := make_engine(["skeleton_guard"])
	engine.enemies[0].hp = 1000
	engine.start()
	engine.defend()   # skeleton raises a 15 shield, which lasts through the player's next turn
	assert_eq(engine.enemies[0].shield, 15)
	var ev := engine.use_skill("warrior_slash", "e0")
	var hit: Dictionary = events_of(ev, "damage")[0]
	assert_eq(hit["absorbed"], mini(15, hit["amount"] + hit["absorbed"]))
	assert_true(hit["absorbed"] > 0)
	assert_eq(engine.enemies[0].shield, 0, "shield resets when the skeleton acts again")


func test_skeleton_immune_to_bleed() -> void:
	var engine := make_engine(["skeleton_guard", "cellar_rat"])
	engine.start()
	engine.player.skills.append("warrior_rending_cut")
	var ev := engine.use_skill("warrior_rending_cut", "e0")
	assert_eq(events_of(ev, "immune").size(), 1)
	assert_false(engine.enemies[0].has_status("bleed"))


func test_rat_gnaw_bleeds_player() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.start()
	engine.defend()
	engine.defend()
	var ev := engine.defend()   # third move in the pattern is gnaw
	assert_eq(events_of(ev, "enemy_move")[0]["move"], "gnaw")
	assert_true(engine.player.has_status("bleed"))
	var next := engine.defend()
	var dots := events_of(next, "damage").filter(func(d: Dictionary) -> bool: return d["dot"])
	assert_eq(dots.size(), 1, "bleed ticks at the start of the player's turn")


func test_victory_rewards() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1
	engine.start()
	var ev := engine.use_skill("warrior_slash", "e0")
	var end: Array = events_of(ev, "battle_end")
	assert_eq(end.size(), 1)
	assert_true(end[0]["victory"])
	assert_eq(end[0]["xp"], 10)
	assert_between(end[0]["gold"], 3, 6)
	assert_eq(engine.use_skill("warrior_slash", "e0"), [], "no actions after the battle ends")


func test_defeat() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.player.hp = 1
	engine.start()
	var ev := engine.defend()
	var end: Array = events_of(ev, "battle_end")
	assert_eq(end.size(), 1)
	assert_false(end[0]["victory"])
	assert_true(engine.finished)


func test_invalid_target_falls_back_to_first_alive_enemy() -> void:
	var engine := make_engine(["cellar_rat", "cellar_rat"])
	engine.enemies[0].hp = 0
	engine.start()
	var ev := engine.use_skill("warrior_slash", "e0")
	assert_eq(events_of(ev, "damage")[0]["target"], "e1")


func test_prototype_battle_is_winnable_by_comboing() -> void:
	# Smoke test of the real encounter: a simple combo-first strategy should win.
	var won := 0
	for seed_value in range(1, 21):
		var engine := CombatEngine.from_data(game_data(), "warrior", 1, "prototype", seeded_rng(seed_value))
		engine.start()
		var guard := 0
		while not engine.finished and guard < 60:
			guard += 1
			var target := engine.alive_enemies()[0]
			var order := ["warrior_execute", "warrior_heavy_strike", "warrior_shield_break", "warrior_slash"]
			var acted := false
			for s in order:
				if engine.can_use(s) and (engine.combo_ready(s, target) or s == "warrior_shield_break" or s == "warrior_slash"):
					engine.use_skill(s, target.uid)
					acted = true
					break
			if not acted:
				engine.defend()
		if engine.victory:
			won += 1
	assert_true(won >= 15, "won %d/20" % won)

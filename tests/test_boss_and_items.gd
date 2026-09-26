extends TestCase
## M2 mechanics: elites, the Bone King's phases and summons, multi-hit moves and potions.


func test_warden_heavy_axe_staggers_itself_when_blocked() -> void:
	var engine := make_engine(["cellar_warden"])
	engine.enemies[0].hp = 1000
	engine.start()
	engine.defend()   # chain_swing
	engine.defend()   # chain_swing
	var ev := engine.defend()   # heavy_axe into a raised guard
	var stuns := events_of(ev, "status_applied").filter(
			func(e: Dictionary) -> bool: return e["target"] == "e0" and e["status"] == "stun")
	assert_eq(stuns.size(), 1, "warden should stagger itself")
	assert_eq(engine.enemies[0].intent["type"], "stunned")


func test_warden_heavy_axe_does_not_stagger_when_not_blocked() -> void:
	var engine := make_engine(["cellar_warden"])
	engine.enemies[0].hp = 1000
	engine.player.stats.hp = 1000
	engine.player.hp = 1000
	engine.start()
	engine.use_skill("warrior_slash", "e0")
	engine.use_skill("warrior_slash", "e0")
	engine.use_skill("warrior_slash", "e0")
	assert_false(engine.enemies[0].has_status("stun"))


func test_multi_attack_hits_several_times() -> void:
	var engine := make_engine(["bone_king"])
	var king := engine.enemies[0]
	king.ai_phase = 1   # phase 2 opens with bone_storm
	engine.start()
	assert_eq(king.intent["move"], "bone_storm")
	assert_eq(king.intent["hits"], 3)
	var ev := engine.defend()
	var hits := events_of(ev, "damage").filter(func(e: Dictionary) -> bool: return e["target"] == "p")
	assert_eq(hits.size(), 3)


func test_boss_summons_until_cap() -> void:
	var engine := make_engine(["bone_king"])
	engine.enemies[0].hp = 5000
	engine.enemies[0].stats.hp = 5000
	engine.player.stats.hp = 5000
	engine.player.hp = 5000
	engine.start()
	var summons := 0
	for i in 16:
		summons += events_of(engine.defend(), "summon").size()
	assert_eq(engine.alive_enemies().size(), 3, "king + two skeletons")
	assert_eq(summons, 2, "no summon past max_alive")
	var ids := {}
	for e in engine.enemies:
		ids[e.uid] = true
	assert_eq(ids.size(), engine.enemies.size(), "summoned uids are unique")


func test_summoned_adds_give_no_rewards() -> void:
	var engine := make_engine(["bone_king"])
	engine.start()
	engine.defend()   # staff_strike
	var ev := engine.defend()   # summon_bones
	var summon: Dictionary = events_of(ev, "summon")[0]
	var add := engine.get_combatant(summon["uid"])
	assert_eq(add.def_id, "skeleton_guard")
	assert_eq(add.xp_reward, 0)
	assert_eq(add.gold_range, [0, 0])


func test_summons_crumble_when_the_boss_dies() -> void:
	var engine := make_engine(["bone_king"])
	engine.start()
	engine.defend()
	engine.defend()   # summon_bones
	assert_eq(engine.alive_enemies().size(), 2)
	engine.enemies[0].hp = 1
	var ev := engine.use_skill("warrior_slash", "e0")
	assert_eq(events_of(ev, "death").size(), 2)
	assert_true(engine.finished and engine.victory)


func test_boss_heals_when_an_ally_dies() -> void:
	var engine := make_engine(["bone_king", "cellar_rat"])
	var king := engine.enemies[0]
	engine.start()
	king.hp = 100
	engine.enemies[1].hp = 1
	var ev := engine.use_skill("warrior_slash", "e1")
	var heals := events_of(ev, "heal").filter(func(e: Dictionary) -> bool: return e["target"] == "e0")
	assert_eq(heals.size(), 1)
	assert_eq(heals[0]["amount"], 20)


func test_boss_changes_phase_below_half_hp() -> void:
	var engine := make_engine(["bone_king"])
	var king := engine.enemies[0]
	engine.start()
	var shown_move: String = king.intent["move"]
	king.hp = roundi(king.max_hp() * 0.5) + 2
	var ev := engine.use_skill("warrior_slash", "e0")
	var phases := events_of(ev, "phase")
	assert_eq(phases.size(), 1)
	assert_eq(phases[0]["line_key"], "boss.bone_king.phase2")
	assert_true(king.has_status("enraged"))
	var moves := events_of(ev, "enemy_move")
	assert_eq(moves[0]["move"], shown_move, "the telegraphed move still happens")
	assert_eq(king.intent["move"], "bone_storm", "phase 2 opens with its first move, telegraphed")


func test_phase_change_happens_once() -> void:
	var engine := make_engine(["bone_king"])
	var king := engine.enemies[0]
	king.stats.hp = 5000
	king.hp = 2400
	engine.start()
	var count := 0
	for i in 3:
		count += events_of(engine.use_skill("warrior_slash", "e0"), "phase").size()
	assert_eq(count, 1)
	assert_eq(king.ai_phase, 1)


func test_potion_heals_and_uses_turn() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.potions = 2
	engine.start()
	engine.player.hp = 20
	var ev := engine.use_potion()
	assert_eq(engine.potions, 1)
	assert_eq(events_of(ev, "item").size(), 1)
	var heal: Dictionary = events_of(ev, "heal")[0]
	assert_eq(heal["amount"], roundi(engine.player.max_hp() * CombatEngine.POTION_HEAL_PERCENT))
	assert_eq(events_of(ev, "enemy_move").size(), 1, "drinking uses the turn")


func test_potion_refused_at_full_hp_or_none_left() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.start()
	engine.player.hp = 10
	assert_eq(engine.use_potion(), [], "no potions")
	engine.potions = 1
	engine.player.hp = engine.player.max_hp()
	assert_eq(engine.use_potion(), [], "full HP")
	assert_eq(engine.potions, 1)


func test_boss_is_beatable_with_combos() -> void:
	# A level 2 warrior (where a first run usually is by room 5) with 3 potions should
	# usually beat the level 3 king when playing the combos (docs/06).
	var wins := 0
	for s in 40:
		var data := game_data()
		var p := Combatant.make_player("warrior", data["classes"]["warrior"], 2,
				data["classes"]["warrior"]["starter_skills"])
		var engine := CombatEngine.for_enemies(data, p, ["bone_king"], 3, seeded_rng(s))
		engine.potions = 3
		engine.start()
		var guard := 0
		while not engine.finished and guard < 80:
			guard += 1
			bot_turn(engine)
		if engine.victory:
			wins += 1
	assert_true(wins >= 24, "won %d / 40" % wins)


extends TestCase
## Mage and Rogue skills (docs/04), Flurry, class unlocks, switching and loadouts.


## `class_id` at level 1 with its starter skills vs. the given enemies; crit and dodge
## are off so numbers are exact except for the 0.9-1.1 variance.
func _engine(class_id: String, enemy_ids: Array, seed_value: int = 1, skills: Array = []) -> CombatEngine:
	var data := game_data()
	var class_def: Dictionary = data["classes"][class_id]
	var engine := CombatEngine.new(data["skills"], data["statuses"], seeded_rng(seed_value))
	engine.enemy_defs = data["enemies"]
	var p := Combatant.make_player(class_id, class_def, 1, skills if not skills.is_empty() else class_def["starter_skills"])
	p.stats.crit = 0.0
	var foes: Array[Combatant] = []
	for i in enemy_ids.size():
		var e := Combatant.make_enemy("e%d" % i, enemy_ids[i], data["enemies"][enemy_ids[i]], 1)
		e.stats.crit = 0.0
		e.stats.dodge = 0.0
		e.stats.hp = 1000
		e.hp = 1000
		foes.append(e)
	engine.setup(p, foes)
	return engine


func _play_run(class_id: String, s: int) -> String:
	var profile := Profile.new_game(game_data(), seeded_rng(s), class_id)
	var run := profile.start_run("rotten_cellar", seeded_rng(s))
	run.start()
	while run.outcome == "":
		var room := run.enter(0)
		match room["type"]:
			"treasure":
				run.open_treasure()
			"event":
				var i := 0
				while not run.event_choice_available(i):
					i += 1
				run.choose_event(i)
			"rest":
				run.rest("heal")
		if run.room["type"] in ["combat", "elite", "boss"]:
			var engine := run.make_battle()
			engine.start()
			var guard := 0
			while not engine.finished and guard < 80:
				guard += 1
				class_bot_turn(engine)
			run.finish_battle(engine)
		if run.outcome == "":
			run.next_room()
	return run.outcome


# ---------------------------------------------------------------- mage

func test_mage_mana_regenerates_each_turn() -> void:
	var engine := _engine("mage", ["cellar_rat"])
	engine.start()
	assert_eq(engine.player.resource, 100, "starts full")
	engine.use_skill("mage_fireball", "e0")   # -20, then +15 at the next turn
	assert_eq(engine.player.resource, 95)
	engine.use_skill("mage_arcane_bolt", "e0")   # +5 on use, +15 next turn
	assert_eq(engine.player.resource, 100)


func test_fireball_then_flame_burst_combo_consumes_burn() -> void:
	var engine := _engine("mage", ["cellar_rat"])
	engine.start()
	engine.use_skill("mage_fireball", "e0")
	assert_true(engine.enemies[0].has_status("burn"))
	assert_true(engine.combo_ready("mage_flame_burst", engine.enemies[0]))
	var ev := engine.use_skill("mage_flame_burst", "e0")
	assert_true(events_of(ev, "damage")[0]["combo"])
	assert_false(engine.enemies[0].has_status("burn"))


func test_shatter_grows_with_freeze_stacks() -> void:
	var one := _engine("mage", ["skeleton_guard"], 5, ["mage_shatter"])
	one.start()
	one._apply_status(one.enemies[0], {"id": "freeze", "turns": 3}, one.player)
	var hit1: int = events_of(one.use_skill("mage_shatter", "e0"), "damage")[0]["amount"]
	var two := _engine("mage", ["skeleton_guard"], 5, ["mage_shatter"])
	two.start()
	for i in 2:
		two._apply_status(two.enemies[0], {"id": "freeze", "turns": 3}, two.player)
	var hit2: int = events_of(two.use_skill("mage_shatter", "e0"), "damage")[0]["amount"]
	# 1.5 + 0.5 per stack: 2.0x vs 2.5x, same rng.
	assert_between(float(hit2) / hit1, 1.2, 1.3)
	assert_false(two.enemies[0].has_status("freeze"))


func test_mana_shield_is_thirty_plus_attack() -> void:
	var engine := _engine("mage", ["cellar_rat"], 1, ["mage_mana_shield"])
	engine.start()
	var ev := engine.use_skill("mage_mana_shield")
	assert_eq(events_of(ev, "shield")[0]["amount"], 30 + roundi(engine.player.stats.atk))


func test_chain_lightning_hits_every_enemy() -> void:
	var engine := _engine("mage", ["cellar_rat", "skeleton_guard", "cellar_rat"], 1, ["mage_chain_lightning"])
	engine.start()
	var ev := engine.use_skill("mage_chain_lightning")
	assert_eq(events_of(ev, "damage").filter(func(d: Dictionary) -> bool: return d["source"] == "p").size(), 3)


# ---------------------------------------------------------------- rogue

func test_flurry_gives_a_second_skill_for_ten_more_energy() -> void:
	var engine := _engine("rogue", ["cellar_rat"])
	engine.start()
	var ev := engine.use_skill("rogue_stab", "e0")
	assert_eq(events_of(ev, "flurry").size(), 1)
	assert_eq(events_of(ev, "enemy_move").size(), 0, "enemies wait for the second action")
	assert_true(engine.in_flurry())
	assert_eq(engine.player.resource, 50)
	assert_eq(engine.skill_cost("rogue_stab"), 20)
	ev = engine.use_skill("rogue_stab", "e0")
	assert_eq(engine.player.resource, 30 + 30, "second stab cost 20, then +30 at the next turn")
	assert_eq(events_of(ev, "enemy_move").size(), 1)
	assert_false(engine.in_flurry())
	assert_eq(engine.skill_cost("rogue_stab"), 10)


func test_end_turn_and_defend_during_flurry() -> void:
	var engine := _engine("rogue", ["cellar_rat"])
	engine.start()
	engine.use_skill("rogue_stab", "e0")
	var ev := engine.defend()
	assert_eq(events_of(ev, "defend").size(), 0, "defend mid-flurry just ends the turn")
	assert_eq(engine.player.resource, 50 + 30)
	assert_eq(engine.turn, 2)
	engine.use_skill("rogue_stab", "e0")
	ev = engine.end_turn()
	assert_eq(events_of(ev, "enemy_move").size(), 1)
	assert_eq(engine.end_turn(), [], "nothing to end outside a flurry")


func test_no_flurry_when_nothing_is_affordable() -> void:
	var engine := _engine("rogue", ["cellar_rat"])
	engine.start()
	engine.player.resource = 20
	var ev := engine.use_skill("rogue_stab", "e0")   # 10 left, every skill now costs 20+
	assert_eq(events_of(ev, "flurry").size(), 0)
	assert_eq(events_of(ev, "enemy_move").size(), 1)


func test_cooldown_skill_cannot_repeat_in_flurry() -> void:
	var engine := _engine("rogue", ["cellar_rat"], 1, ["rogue_stab", "rogue_smoke_bomb"])
	engine.start()
	engine.player.resource = 100
	engine.use_skill("rogue_smoke_bomb")
	assert_eq(engine.skill_block_reason("rogue_smoke_bomb"), "cooldown")
	engine.use_skill("rogue_stab", "e0")
	assert_eq(int(engine.player.cooldowns["rogue_smoke_bomb"]), 4, "no tick in the turn it was used")


func test_backstab_crits_on_stunned_undead_too() -> void:
	var engine := _engine("rogue", ["skeleton_guard"])
	engine.start()
	engine.player.resource = 100
	engine.use_skill("rogue_poison_blade", "e0")
	assert_false(engine.combo_ready("rogue_backstab", engine.enemies[0]), "skeletons shrug off poison")
	engine.end_turn()
	engine.use_skill("rogue_blind", "e0")
	var ev := engine.use_skill("rogue_backstab", "e0")
	assert_true(events_of(ev, "damage")[0]["crit"])
	assert_true(engine.enemies[0].has_status("stun"), "backstab leaves the stun for Shadow Step")


func test_backstab_on_poisoned_target_always_crits() -> void:
	for s in range(1, 8):
		var engine := _engine("rogue", ["cellar_rat"], s)
		engine.start()
		engine.player.resource = 100
		engine.use_skill("rogue_poison_blade", "e0")
		var ev := engine.use_skill("rogue_backstab", "e0")
		var hit: Dictionary = events_of(ev, "damage")[0]
		assert_true(hit["crit"] and hit["combo"], "seed %d" % s)
		assert_true(engine.enemies[0].has_status("poison"), "backstab keeps the poison")


func test_poison_scales_with_attack() -> void:
	var engine := _engine("rogue", ["cellar_rat"])
	engine.start()
	engine.player.stats.atk = 40
	engine._apply_status(engine.enemies[0], {"id": "poison", "turns": 4, "stacks": 2}, engine.player)
	assert_eq(engine._dot_amount(engine.enemies[0], "poison"), 20, "0.25 x 40 per stack")
	var weak := _engine("rogue", ["cellar_rat"])
	weak.player.stats.atk = 4
	weak._apply_status(weak.enemies[0], {"id": "poison", "turns": 4, "stacks": 2}, weak.player)
	assert_eq(weak._dot_amount(weak.enemies[0], "poison"), 6, "never below 3 per stack")


func test_poison_burst_deals_the_remaining_poison_at_once() -> void:
	var engine := _engine("rogue", ["cellar_rat"], 1, ["rogue_poison_burst"])
	engine.start()
	engine._apply_status(engine.enemies[0], {"id": "poison", "turns": 3, "stacks": 4}, engine.player)
	var per_turn := engine._dot_amount(engine.enemies[0], "poison")
	var ev := engine.use_skill("rogue_poison_burst", "e0")
	var burst: Array = events_of(ev, "damage").filter(func(d: Dictionary) -> bool: return d["dot"] and d["combo"])
	assert_eq(burst.size(), 1)
	assert_eq(burst[0]["amount"], per_turn * 3)
	assert_false(engine.enemies[0].has_status("poison"))


func test_smoke_bomb_makes_the_rogue_hard_to_hit() -> void:
	var engine := _engine("rogue", ["cellar_rat"], 1, ["rogue_smoke_bomb"])
	engine.start()
	engine.use_skill("rogue_smoke_bomb")
	assert_between(engine.player.effective_dodge(engine.status_defs), 0.399, 0.401)
	var misses := 0
	for s in 200:
		var e := _engine("rogue", ["cellar_rat"], s)
		e._apply_status(e.player, {"id": "evasive", "turns": 2}, e.player)
		if DamageCalc.roll(e.enemies[0], e.player, 1.0, "physical", e.status_defs, e.rng)["miss"]:
			misses += 1
	assert_between(misses, 60, 100)


func test_blind_only_sometimes_works_on_bosses() -> void:
	var stunned := 0
	for s in 40:
		var engine := _engine("rogue", ["bone_king"], s, ["rogue_blind"])
		engine.start()
		var ev := engine.use_skill("rogue_blind", "e0")
		if engine.enemies[0].has_status("stun"):
			stunned += 1
		else:
			assert_eq(events_of(ev, "resist").size(), 1)
	assert_between(stunned, 10, 30)
	var rat := _engine("rogue", ["cellar_rat"], 1, ["rogue_blind"])
	rat.start()
	rat.use_skill("rogue_blind", "e0")
	assert_true(rat.enemies[0].has_status("stun"), "normal enemies are always blinded")


func test_blade_rain_hits_four_times() -> void:
	var engine := _engine("rogue", ["cellar_rat", "cellar_rat"], 3, ["rogue_blade_rain"])
	engine.start()
	engine.player.resource = 100
	var ev := engine.use_skill("rogue_blade_rain")
	var hits := events_of(ev, "damage").filter(func(d: Dictionary) -> bool: return d["source"] == "p")
	var misses := events_of(ev, "miss").filter(func(d: Dictionary) -> bool: return d["source"] == "p")
	assert_eq(hits.size() + misses.size(), 4)


func test_shadow_step_refunds_energy_on_combo() -> void:
	var engine := _engine("rogue", ["cellar_rat"], 1, ["rogue_shadow_step", "rogue_blind"])
	engine.start()
	engine.player.resource = 100
	engine._apply_status(engine.enemies[0], {"id": "stun", "turns": 2}, engine.player)
	var ev := engine.use_skill("rogue_shadow_step", "e0")
	assert_true(events_of(ev, "damage")[0]["combo"])
	assert_eq(engine.player.resource, 100, "the 50 energy came back")


# ---------------------------------------------------------------- balance

func test_every_class_can_clear_its_first_run() -> void:
	# Same bar as the warrior: a fresh level 1 hero playing its combos clears a fair
	# share of first runs, but not most.
	for class_id in ["mage", "rogue"]:
		var cleared := 0
		for s in 30:
			if _play_run(class_id, s) == "cleared":
				cleared += 1
		assert_between(cleared, 9, 21, "%s cleared %d / 30" % [class_id, cleared])


# ---------------------------------------------------------------- profile

func test_new_game_as_another_class() -> void:
	var p := Profile.new_game(game_data(), seeded_rng(1), "rogue")
	assert_eq(p.active_class, "rogue")
	assert_eq(p.equipped("weapon")["base"], "rusty_dagger")
	assert_eq(p.loadout(), ["rogue_stab", "rogue_poison_blade", "rogue_backstab", "rogue_blind"])


func test_class_master_unlocks_after_the_first_dungeon() -> void:
	var p := Profile.new_game(game_data(), seeded_rng(1))
	assert_eq(p.class_unlock_block("mage"), "locked")
	assert_false(p.unlock_class("mage"))
	p.dungeons["rotten_cellar"] = {"runs": 1, "cleared": true}
	assert_true(p.unlock_class("mage"))
	assert_eq(p.class_unlock_block("mage"), "unlocked")
	assert_eq(p.active_class, "warrior", "unlocking doesn't switch")
	var staff := p.bag_items().filter(func(i: Dictionary) -> bool: return i["base"] == "apprentice_staff")
	assert_eq(staff.size(), 1, "the Class Master hands over a staff")


func test_switching_class_swaps_the_weapon_and_keeps_armour() -> void:
	var p := Profile.new_game(game_data(), seeded_rng(1))
	var armor := {"base": "leather_armor", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}
	p.add_item(armor)
	p.equip(armor["uid"])
	p.dungeons["rotten_cellar"] = {"runs": 1, "cleared": true}
	p.unlock_class("mage")
	assert_true(p.switch_class("mage"))
	assert_eq(p.level(), 1)
	assert_eq(p.equipped("weapon")["base"], "apprentice_staff")
	assert_eq(p.equipped("armor")["uid"], armor["uid"])
	assert_eq(p.player().resource_id, "mana")
	assert_true(p.switch_class("warrior"))
	assert_eq(p.equipped("weapon")["base"], "rusty_sword")
	assert_false(p.switch_class("rogue"), "locked classes can't be picked")


func test_loadout_swaps_and_respects_unlock_levels() -> void:
	var p := Profile.new_game(game_data(), seeded_rng(1))
	assert_false(p.set_loadout_slot(0, "warrior_battle_cry"), "level 3 skill at level 1")
	p.set_progress(6, 0)
	assert_true(p.unlocked_skills().has("warrior_rending_cut"))
	assert_true(p.set_loadout_slot(3, "warrior_rending_cut"))
	assert_eq(p.loadout()[3], "warrior_rending_cut")
	assert_true(p.set_loadout_slot(0, "warrior_rending_cut"), "already in: the two slots trade")
	assert_eq(p.loadout()[0], "warrior_rending_cut")
	assert_eq(p.loadout()[3], "warrior_slash")
	var back := Profile.from_dict(game_data(), JSON.parse_string(JSON.stringify(p.to_dict())))
	assert_eq(back.loadout(), p.loadout())
	var run := back.start_run("rotten_cellar", seeded_rng(1))
	assert_eq(Array(run.player.skills), Array(p.loadout()))


func test_resumed_run_keeps_its_skills() -> void:
	var p := Profile.new_game(game_data(), seeded_rng(1))
	p.set_progress(3, 0)
	p.set_loadout_slot(1, "warrior_battle_cry")
	var run := p.start_run("rotten_cellar", seeded_rng(2))
	run.start()
	var back := DungeonRun.from_dict(game_data(), JSON.parse_string(JSON.stringify(run.to_dict())))
	assert_eq(Array(back.player.skills), Array(run.player.skills))

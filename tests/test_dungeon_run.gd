extends TestCase
## DungeonRun: room rolls, persistence between rooms, non-combat rooms and run endings.


func _run(seed_value: int = 1, level: int = 1) -> DungeonRun:
	var run := DungeonRun.new(game_data(), "rotten_cellar", "warrior", level, 0, seeded_rng(seed_value))
	run.start()
	return run


## Forces the current room to be `type` (for testing one room kind at a time).
func _enter_as(run: DungeonRun, room: Dictionary) -> Dictionary:
	run.choices = [room]
	return run.enter(0)


func _win(run: DungeonRun) -> Dictionary:
	var engine := run.make_battle()
	engine.start()
	for e in engine.enemies:
		e.hp = 1
	while not engine.finished:
		engine.use_skill("warrior_slash", engine.alive_enemies()[0].uid)
	return run.finish_battle(engine)


func test_xp_curve_matches_docs() -> void:
	assert_eq(Progression.xp_to_next(1), 50)
	assert_eq(Progression.xp_to_next(2), 141)
	assert_eq(Progression.xp_to_next(5), 559)
	var r := Progression.add_xp(1, 40, 160)
	assert_eq(r["level"], 3)
	assert_eq(r["xp"], 9)
	assert_eq(r["gained_levels"], 2)


func test_two_doors_then_boss_door_in_last_room() -> void:
	for s in 30:
		var run := _run(s)
		for room_no in range(1, 5):
			assert_eq(run.choices.size(), 2)
			var types := [run.choices[0]["type"], run.choices[1]["type"]]
			assert_true(types[0] != types[1] or types[0] == "combat", "doors differ unless a fight is forced")
			var room := run.enter(0)
			room["done"] = true
			run.room["done"] = true
			run.next_room()
		assert_eq(run.room_number, 5)
		assert_eq(run.choices.size(), 1)
		assert_eq(run.choices[0]["type"], "boss")
		assert_eq(run.choices[0]["level"], 3)


func test_elites_only_in_rooms_three_and_four() -> void:
	for s in 60:
		var run := _run(s)
		for room_no in range(1, 5):
			for c in run.choices:
				if c["type"] == "elite":
					assert_true(room_no in [3, 4], "elite in room %d" % room_no)
			run.enter(0)
			run.room["done"] = true
			run.next_room()


func test_at_least_two_battles_before_the_boss() -> void:
	for s in 80:
		var run := _run(s)
		# Always pick a non-combat door when there is one.
		for room_no in range(1, 5):
			var pick := 0
			for i in run.choices.size():
				if run.choices[i]["type"] not in ["combat", "elite"]:
					pick = i
			run.enter(pick)
			run.room["done"] = true
			run.next_room()
		var fights := run.history.count("combat") + run.history.count("elite")
		assert_true(fights >= 2, "seed %d: %s" % [s, str(run.history)])


func test_room_level_rises_through_the_dungeon() -> void:
	var run := _run()
	var levels := []
	for n in range(1, 6):
		run.room_number = n
		levels.append(run.room_level())
	assert_eq(levels, [1, 1, 2, 2, 3])


func test_hp_and_potions_carry_between_rooms() -> void:
	var run := _run()
	_enter_as(run, {"type": "combat", "enemies": ["cellar_rat"], "level": 1})
	var engine := run.make_battle()
	assert_true(engine.player == run.player, "same player object")
	assert_eq(engine.potions, 3)
	engine.start()
	engine.player.hp -= 30
	engine.use_potion()
	engine.enemies[0].hp = 1
	while not engine.finished:
		engine.use_skill("warrior_slash", "e0")
	var hp_after := engine.player.hp
	run.finish_battle(engine)
	assert_eq(run.potions, 2)
	assert_eq(run.player.hp, mini(run.player.max_hp(), hp_after + 24), "HP carries over, plus the 20% breather")
	assert_true(run.player.statuses.is_empty(), "statuses cleared after battle")
	assert_eq(run.player.resource, 20, "rage resets to its start value")


func test_battle_rewards_and_level_up() -> void:
	var run := _run()
	var levels := []
	run.leveled_up.connect(func(lv: int) -> void: levels.append(lv))
	_enter_as(run, {"type": "combat", "enemies": ["cellar_rat", "cellar_rat", "cellar_rat"], "level": 2})
	var engine := run.make_battle()
	engine.start()
	for e in engine.enemies:
		e.hp = 1
	while not engine.finished:
		engine.use_skill("warrior_slash", engine.alive_enemies()[0].uid)
	var hp_before := engine.player.hp
	var r := run.finish_battle(engine)
	assert_eq(r["xp"], 60)
	assert_eq(r["levels"], 1)
	assert_eq(levels, [2])
	assert_eq(run.level, 2)
	assert_eq(run.class_xp, 10)
	assert_eq(run.player.max_hp(), 132)
	assert_eq(run.player.hp, mini(132, hp_before + 12 + 26), "max HP gain plus the 20% breather")
	assert_eq(r["healed"], mini(132, hp_before + 12 + 26) - (hp_before + 12))
	assert_true(run.gold_earned > 0)


func test_death_halves_gold_and_keeps_xp() -> void:
	var run := _run()
	run.gold_earned = 41
	run.xp_earned = 30
	_enter_as(run, {"type": "combat", "enemies": ["cellar_rat"], "level": 1})
	var engine := run.make_battle()
	engine.start()
	engine.player.hp = 1
	engine.defend()
	assert_true(engine.finished and not engine.victory)
	run.finish_battle(engine)
	assert_eq(run.outcome, "died")
	assert_eq(run.gold_earned, 21)
	assert_eq(run.gold_lost, 20)
	assert_eq(run.xp_earned, 30)


func test_escape_only_between_rooms() -> void:
	var run := _run()
	_enter_as(run, {"type": "combat", "enemies": ["cellar_rat"], "level": 1})
	assert_false(run.can_escape())
	run.escape()
	assert_eq(run.outcome, "")
	_win(run)
	assert_true(run.can_escape())
	var gold := run.gold_earned
	run.escape()
	assert_eq(run.outcome, "escaped")
	assert_eq(run.gold_earned, gold, "loot is kept")


func test_boss_victory_clears_the_dungeon() -> void:
	var run := _run()
	_enter_as(run, {"type": "boss", "enemies": ["bone_king"], "level": 3})
	run.room_number = 5
	_win(run)
	assert_eq(run.outcome, "cleared")
	assert_eq(run.next_room(), [], "no room after the boss")


func test_treasure_gives_gold_or_a_mimic() -> void:
	var mimics := 0
	for s in 100:
		var run := _run(s)
		_enter_as(run, {"type": "treasure", "level": 1})
		var r := run.open_treasure()
		if r["mimic"]:
			mimics += 1
			assert_eq(run.room["type"], "combat")
			assert_eq(run.room["enemies"], ["mimic"])
			assert_false(run.room["done"])
		else:
			assert_between(r["gold"], 15, 30)
			assert_true(run.room["done"])
			assert_eq(run.open_treasure(), {}, "a chest opens once")
	assert_between(mimics, 8, 35)


func test_rest_heals_or_gives_a_potion() -> void:
	var run := _run()
	_enter_as(run, {"type": "rest", "level": 1})
	run.player.hp = 20
	var r := run.rest("heal")
	assert_eq(r["heal"], 36)
	assert_eq(run.player.hp, 56)
	assert_eq(run.rest("potion"), {}, "one rest per room")

	var run2 := _run()
	_enter_as(run2, {"type": "rest", "level": 1})
	run2.rest("potion")
	assert_eq(run2.potions, 4)


func test_merchant_needs_gold() -> void:
	var run := _run()
	_enter_as(run, {"type": "event", "event": "lost_merchant", "level": 1})
	assert_false(run.event_choice_available(0))
	assert_eq(run.choose_event(0), {})
	run.gold_earned = 70
	var r := run.choose_event(0)
	assert_eq(r["changes"]["gold"], -50)
	assert_eq(run.gold_earned, 20)
	assert_eq(run.potions, 4)


func test_skull_riddle() -> void:
	var run := _run()
	_enter_as(run, {"type": "event", "event": "talking_skull", "level": 1})
	var r := run.choose_event(1)
	assert_eq(r["text_key"], "event.skull.right")
	assert_eq(run.gold_earned, 60)


func test_altar_trades_hp_for_attack_and_never_kills() -> void:
	var run := _run()
	_enter_as(run, {"type": "event", "event": "cursed_altar", "level": 1})
	run.player.hp = 10
	var atk := run.player.stats.atk
	run.choose_event(0)
	assert_eq(run.player.hp, 1)
	assert_between(run.player.stats.atk, atk * 1.149, atk * 1.151)


func test_first_runs_are_usually_survivable() -> void:
	# A fresh level 1 warrior playing the combos (never defending), always taking the
	# first door, should clear a good share of runs; the boss is where most runs end.
	var cleared := 0
	for s in 30:
		var run := _run(s)
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
					bot_turn(engine)
				run.finish_battle(engine)
			if run.outcome == "":
				run.next_room()
		if run.outcome == "cleared":
			cleared += 1
	assert_true(cleared >= 9, "cleared %d / 30" % cleared)

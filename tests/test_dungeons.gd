extends TestCase
## Dungeons 2-5 (docs/06): unlock chain, stars, Hard mode, the story and a balance check.


func _profile(level: int = 1, class_id: String = "warrior") -> Profile:
	var p := Profile.new_game(game_data(), seeded_rng(1), class_id)
	p.set_progress(level, 0)
	return p


## Plays a whole run with the combo bot, taking the first door every time.
func _play(run: DungeonRun) -> void:
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
			while not engine.finished and guard < 100:
				guard += 1
				class_bot_turn(engine)
			run.finish_battle(engine)
		if run.outcome == "":
			run.next_room()


## A hero at the dungeon's lowest level with a rare item of that level in every slot.
func _geared(level: int, class_id: String, rng: RandomNumberGenerator) -> Profile:
	var data := game_data()
	var p := Profile.new_game(data, rng, class_id)
	p.set_progress(level, 0)
	for slot in Items.SLOTS:
		var pool: Array = []
		for b in data["items"]["bases"]:
			var bd: Dictionary = data["items"]["bases"][b]
			if bd["slot"] == slot and not bd.get("drop_only", false) and bd.get("class", class_id) == class_id:
				pool.append(b)
		var item := Items.roll(data["items"], level, rng, {"base": pool[rng.randi_range(0, pool.size() - 1)], "rarity": "rare"})
		p.add_item(item)
		p.equipment[slot] = item["uid"]
	return p


func test_every_dungeon_is_complete() -> void:
	var data := game_data()
	var prev := ""
	for id in data["dungeons"]:
		var d: Dictionary = data["dungeons"][id]
		assert_eq(d.get("unlock_after", ""), prev, "%s opens after the one before" % id)
		prev = id
		var ids: Array = d["boss"].duplicate()
		for c in d["combat_pool"] + d["elite_pool"]:
			ids.append_array(c["enemies"])
		for e in ids:
			assert_true(data["enemies"].has(e), "%s: enemy %s" % [id, e])
		assert_true(data["enemies"][d["boss"][0]].get("boss", false), "%s boss flagged" % id)
		for kind in d["loot"]:
			for u in d["loot"][kind].get("uniques", []):
				assert_true(data["items"]["bases"].has(u["base"]), "%s: unique %s" % [id, u["base"]])
		assert_true(data["story"]["scenes"].has(id + "_intro"), id + " intro")
		assert_true(data["story"]["scenes"].has(id + "_outro"), id + " outro")


func test_every_story_line_has_text_and_a_speaker() -> void:
	var data := game_data()
	var text := DataLoader.load_json("res://data/text/tr.json")
	for scene in data["story"]["scenes"]:
		for line in data["story"]["scenes"][scene]:
			assert_true(data["story"]["speakers"].has(line[0]), "%s: speaker %s" % [scene, line[0]])
			var key := StoryText.line_key(scene, line[0], int(line[1]))
			assert_true(text.has(key), key)


func test_dungeons_open_one_after_another() -> void:
	var p := _profile()
	assert_true(p.dungeon_unlocked("rotten_cellar"))
	assert_false(p.dungeon_unlocked("mushroom_cave"))
	p.dungeons["rotten_cellar"] = {"runs": 1, "cleared": true, "stars": [true, false, false]}
	assert_true(p.dungeon_unlocked("mushroom_cave"))
	assert_false(p.dungeon_unlocked("frozen_pass"))


func test_stars_are_earned_and_kept() -> void:
	var p := _profile(3)
	var run := p.start_run("rotten_cellar", seeded_rng(4))
	run.outcome = "cleared"
	run.potions_used = 1
	run.end_hp_ratio = 0.8
	var r := p.apply_run(run, seeded_rng(4))
	assert_eq(p.dungeon_stars("rotten_cellar"), [true, false, true])
	assert_eq(r["new_stars"], [0, 2])
	assert_true(r["first_clear"])
	var again := p.start_run("rotten_cellar", seeded_rng(5))
	again.outcome = "cleared"
	again.end_hp_ratio = 0.2
	r = p.apply_run(again, seeded_rng(5))
	assert_eq(p.dungeon_stars("rotten_cellar"), [true, true, true], "no potions this time")
	assert_eq(r["new_stars"], [1])
	assert_false(r["first_clear"])
	assert_true(p.hard_unlocked("rotten_cellar"))


func test_potions_used_counts_drinks_in_battle() -> void:
	var run := DungeonRun.new(game_data(), "rotten_cellar", "warrior", 1, 0, seeded_rng(2))
	run.start()
	run.choices = [run._make_room("combat")]
	run.enter(0)
	var engine := run.make_battle()
	engine.start()
	engine.player.hp = 10
	engine.use_potion()
	for e in engine.enemies:
		e.hp = 1
	while not engine.finished:
		engine.use_skill("warrior_slash", engine.alive_enemies()[0].uid)
	run.finish_battle(engine)
	assert_eq(run.potions_used, 1)


func test_hard_mode_needs_three_stars_and_raises_levels() -> void:
	var p := _profile(5)
	assert_false(p.start_run("rotten_cellar", seeded_rng(1), true).hard, "locked without 3 stars")
	p.dungeons["rotten_cellar"] = {"runs": 3, "cleared": true, "stars": [true, true, true]}
	var hard := p.start_run("rotten_cellar", seeded_rng(1), true)
	var normal := p.start_run("rotten_cellar", seeded_rng(1))
	assert_true(hard.hard)
	hard.start()
	normal.start()
	assert_eq(hard.room_level(), normal.room_level() + DungeonRun.HARD_LEVELS)
	var back := DungeonRun.from_dict(game_data(), JSON.parse_string(JSON.stringify(hard.to_dict())))
	assert_true(back.hard, "hard mode survives a save")


func test_the_lair_gives_the_dragon_egg_once() -> void:
	var p := _profile(16)
	for id in ["rotten_cellar", "mushroom_cave", "frozen_pass", "burnt_keep"]:
		p.dungeons[id] = {"runs": 1, "cleared": true, "stars": [true, false, false]}
	var run := p.start_run("dragon_lair", seeded_rng(3))
	run.outcome = "cleared"
	var r := p.apply_run(run, seeded_rng(3))
	assert_eq(r["reward"].get("base", ""), "dragon_egg")
	assert_eq(r["reward"]["rarity"], "legendary")
	assert_eq(p.bag_items().filter(func(i: Dictionary) -> bool: return i["base"] == "dragon_egg").size(), 1)
	var again := p.start_run("dragon_lair", seeded_rng(4))
	again.outcome = "cleared"
	assert_true(p.apply_run(again, seeded_rng(4))["reward"].is_empty())


func test_story_scenes_play_once() -> void:
	var p := _profile()
	assert_true(p.take_story("rotten_cellar_intro"))
	assert_false(p.take_story("rotten_cellar_intro"))
	var back := Profile.from_dict(game_data(), JSON.parse_string(JSON.stringify(p.to_dict())))
	assert_false(back.take_story("rotten_cellar_intro"), "remembered in the save")


func test_on_hit_perks_apply_their_status() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.player.perks["burn_on_hit"] = 1.0
	engine.start()
	engine.use_skill("warrior_slash", "e0")
	assert_true(engine.enemies[0].has_status("burn"))


func test_later_dungeons_are_fair_for_a_geared_hero() -> void:
	# A warrior at each dungeon's lowest level with rare gear of that level should
	# clear most runs, but not every one.
	for id in ["mushroom_cave", "frozen_pass", "burnt_keep", "dragon_lair"]:
		var lv := int(game_data()["dungeons"][id]["level_min"])
		var cleared := 0
		for s in 20:
			var rng := seeded_rng(s + 100)
			var run := _geared(lv, "warrior", rng).start_run(id, rng)
			_play(run)
			if run.outcome == "cleared":
				cleared += 1
		assert_between(cleared, 8, 20, "%s cleared %d / 20" % [id, cleared])

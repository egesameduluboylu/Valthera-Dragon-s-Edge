extends TestCase
## Profile (docs/05, docs/10): the bag, the smith, the merchant, banking runs and saving.


func _profile(seed_value: int = 1) -> Profile:
	return Profile.new_game(game_data(), seeded_rng(seed_value))


func _give(p: Profile, base: String, rarity: String = "common", level: int = 1) -> Dictionary:
	var item := {"base": base, "rarity": rarity, "level": level, "upgrade": 0, "affixes": []}
	p.add_item(item)
	return item


func test_new_game_wears_the_starter_sword() -> void:
	var p := _profile()
	assert_eq(p.level(), 1)
	assert_eq(p.potions, Profile.FREE_POTIONS)
	assert_eq(p.equipped("weapon")["base"], "rusty_sword")
	assert_eq(p.bag_items().size(), 0)
	assert_eq(p.shop.size(), Profile.SHOP_SIZE)


func test_equip_swaps_the_old_item_back_to_the_bag() -> void:
	var p := _profile()
	var old := p.equipped("weapon")
	var sword := _give(p, "iron_sword", "rare", 2)
	assert_true(p.equip(sword["uid"]))
	assert_eq(p.equipped("weapon"), sword)
	assert_eq(p.bag_items(), [old])
	assert_true(p.unequip("weapon"))
	assert_eq(p.equipped("weapon"), {})
	assert_eq(p.bag_items().size(), 2)


func test_other_class_weapons_cannot_be_worn() -> void:
	var p := _profile()
	var sword := _give(p, "iron_sword")
	p.active_class = "mage"
	assert_false(p.equip(sword["uid"]))


func test_salvage_pays_out_and_refuses_worn_items() -> void:
	var p := _profile()
	var ring := _give(p, "copper_ring", "epic", 2)
	assert_eq(p.salvage(p.equipped("weapon")["uid"]), {})
	assert_eq(p.salvage(ring["uid"]), {"gold": 36, "scales": 1})
	assert_eq(p.gold, 36)
	assert_eq(p.scales, 1)
	assert_true(p.get_item(ring["uid"]).is_empty())


func test_full_bag_salvages_new_loot() -> void:
	var p := _profile()
	for i in p.bag_size():
		_give(p, "copper_ring")
	var r := p.add_item({"base": "bone_amulet", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []})
	assert_false(r["added"])
	assert_eq(p.gold, 6)
	assert_eq(p.bag_items().size(), p.bag_size())


func test_smith_upgrades_until_money_runs_out() -> void:
	var p := _profile()
	var uid: String = p.equipped("weapon")["uid"]
	assert_false(p.upgrade(uid), "upgraded with no gold")
	p.gold = 20 + 40
	assert_true(p.upgrade(uid))
	assert_true(p.upgrade(uid))
	assert_eq(p.gold, 0)
	assert_eq(p.get_item(uid)["upgrade"], 2)
	# From +6 the smith also wants a dragon scale.
	p.get_item(uid)["upgrade"] = 5
	p.gold = 1000
	assert_false(p.upgrade(uid))
	p.scales = 1
	assert_true(p.upgrade(uid))
	assert_eq(p.scales, 0)


func test_merchant_sells_potions_up_to_the_cap() -> void:
	var p := _profile()
	p.gold = 1000
	while p.buy_potion():
		pass
	assert_eq(p.potions, Profile.MAX_POTIONS)
	assert_eq(p.gold, 1000 - Profile.POTION_PRICE * (Profile.MAX_POTIONS - Profile.FREE_POTIONS))


func test_merchant_item_goes_to_the_bag() -> void:
	var p := _profile()
	var item: Dictionary = p.shop[0]
	assert_false(p.buy_shop_item(0), "bought with no gold")
	p.gold = Items.shop_price(item, p.defs())
	assert_true(p.buy_shop_item(0))
	assert_eq(p.gold, 0)
	assert_eq(p.shop.size(), Profile.SHOP_SIZE - 1)
	assert_true(item in p.bag_items())


func test_runs_use_the_worn_gear_and_potion_stock() -> void:
	var p := _profile()
	p.potions = 5
	var run := p.start_run("rotten_cellar", seeded_rng(1))
	var bare := DungeonRun.new(game_data(), "rotten_cellar", "warrior", 1, 0, seeded_rng(1))
	assert_eq(run.potions, 5)
	assert_eq(run.player.stats.atk, bare.player.stats.atk + 1)


func test_banking_a_run_keeps_loot_gold_and_progress() -> void:
	var p := _profile()
	var run := p.start_run("rotten_cellar", seeded_rng(2))
	run.start()
	run.gold_earned = 40
	run.scales_earned = 2
	run.level = 2
	run.class_xp = 10
	run.potions = 0
	run.loot = [{"base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": []}]
	run.escape()
	var r := p.apply_run(run, seeded_rng(2))
	assert_eq(p.gold, 40)
	assert_eq(p.scales, 2)
	assert_eq(p.level(), 2)
	assert_eq(p.class_xp(), 10)
	assert_eq(p.potions, Profile.FREE_POTIONS, "potions refill in town")
	assert_eq(r["added"].size(), 1)
	assert_eq(p.bag_items().size(), 1)
	assert_eq(p.dungeons["rotten_cellar"], {"runs": 1, "cleared": false})


func test_boss_and_elite_rooms_drop_loot_and_scales() -> void:
	var data := game_data()
	var elite_items := 0
	for s in 20:
		var run := DungeonRun.new(data, "rotten_cellar", "warrior", 1, 0, seeded_rng(s))
		run.start()
		var drop := run._drop("elite")
		assert_eq(drop["scales"], 1)
		elite_items += drop["items"].size()
		for item in drop["items"]:
			assert_true(item["rarity"] != "common")
	assert_eq(elite_items, 20)


func test_save_round_trip() -> void:
	var p := _profile(4)
	p.gold = 123
	p.scales = 2
	var ring := _give(p, "copper_ring", "rare", 2)
	ring["affixes"] = [{"id": "crit", "value": 0.02}]
	p.equip(ring["uid"])
	p.dungeons["rotten_cellar"] = {"runs": 3, "cleared": true}
	var json := JSON.stringify(p.to_dict())
	var back := Profile.from_dict(game_data(), JSON.parse_string(json))
	assert_eq(JSON.stringify(back.to_dict()), JSON.stringify(p.to_dict()))
	assert_eq(back.equipped("accessory")["affixes"][0]["value"], 0.02)
	assert_eq(typeof(back.get_item(ring["uid"])["level"]), TYPE_INT)
	# New items keep getting fresh uids after loading.
	var added := _give(back, "bone_amulet")
	assert_true(back.get_item(added["uid"]) == added and added["uid"] != ring["uid"])


func test_broken_save_data_is_cleaned() -> void:
	var d := {"gold": "12", "inventory": [{"base": "gone_item", "rarity": "rare"}, "junk",
			{"uid": "i9", "base": "copper_ring", "rarity": "shiny", "level": 2.0}],
			"equipment": {"weapon": null, "accessory": "i9"}, "run_state": null}
	var p := Profile.from_dict(game_data(), d)
	assert_eq(p.gold, 12)
	assert_eq(p.inventory.size(), 1)
	assert_eq(p.inventory[0]["rarity"], "common")
	assert_eq(p.equipped("accessory")["uid"], "i9")
	assert_eq(p.equipment["weapon"], "")
	assert_eq(p.run_state, {})


func test_run_state_resumes_between_rooms() -> void:
	var p := _profile()
	var run := p.start_run("rotten_cellar", seeded_rng(9))
	run.start()
	run.enter(0)
	assert_eq(run.to_dict(), {}, "saved mid-room")
	run.room["done"] = true
	run.next_room()
	run.player.hp = 17
	run.gold_earned = 33
	run.loot = [{"base": "iron_helm", "rarity": "rare", "level": 1, "upgrade": 0, "affixes": []}]
	var saved: Dictionary = JSON.parse_string(JSON.stringify(run.to_dict()))
	var back := DungeonRun.from_dict(game_data(), saved)
	assert_eq(back.room_number, 2)
	assert_eq(back.player.hp, 17)
	assert_eq(back.player.max_hp(), run.player.max_hp())
	assert_eq(back.player.stats.atk, run.player.stats.atk)
	assert_eq(back.gold_earned, 33)
	assert_eq(back.loot.size(), 1)
	assert_eq(back.history, run.history)
	assert_eq(back.choices.size(), 2)
	# The random stream continues where it stopped.
	assert_eq(back.rng.randi(), run.rng.randi())
	assert_false(back.enter(0).is_empty())

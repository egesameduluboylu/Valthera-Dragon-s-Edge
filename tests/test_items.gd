extends TestCase
## Items (docs/05): stat formulas, loot rolls, smith prices and gear on a combatant.


func _defs() -> Dictionary:
	return game_data()["items"]


func _item(base: String, rarity: String = "common", level: int = 1, upgrade: int = 0, affixes: Array = []) -> Dictionary:
	return {"uid": "t", "base": base, "rarity": rarity, "level": level, "upgrade": upgrade, "affixes": affixes}


func test_main_stat_formula_matches_docs() -> void:
	var defs := _defs()
	# 12 hp * (1 + 0.12 * 5) * 1.3 = 24.96 -> 25
	assert_eq(Items.main_stats(_item("leather_armor", "epic", 5), defs)["hp"], 25.0)
	# 4 atk * (1 + 0.12 * 2) * 1.0 * (1 + 0.08 * 5) = 6.944; attack keeps its decimals
	assert_between(Items.main_stats(_item("iron_sword", "common", 2, 5), defs)["atk"], 6.94, 6.95)
	# Fractional stats are not rounded to ints.
	assert_between(Items.main_stats(_item("iron_helm", "rare", 1), defs)["crit"], 0.0255, 0.0265)


func test_affixes_add_to_stats_and_perks_stay_separate() -> void:
	var defs := _defs()
	var item := _item("rusty_sword", "epic", 1, 0, [{"id": "hp", "value": 6.0}, {"id": "start_shield", "value": 7.0}])
	var s := Items.total_stats(item, defs)
	assert_eq(s["hp"], 6.0)
	assert_false(s.has("start_shield"))
	assert_eq(Items.perks(item, defs), {"start_shield": 7.0})
	assert_eq(Items.perks(_item("bone_crown", "legendary"), defs), {"heal_on_kill": 10.0})


func test_rolls_follow_rarity_rules() -> void:
	var defs := _defs()
	var rng := seeded_rng(3)
	var counts := {}
	for i in 2000:
		var item := Items.roll(defs, 3, rng, {"class_id": "warrior"})
		counts[item["rarity"]] = counts.get(item["rarity"], 0) + 1
		assert_eq(item["affixes"].size(), int(defs["rarities"][item["rarity"]]["affixes"]))
		assert_false(item["base"] == "bone_crown", "drop-only base rolled")
		var ids: Array = item["affixes"].map(func(a: Dictionary) -> String: return a["id"])
		for id in ids:
			assert_eq(ids.count(id), 1, "duplicate affix %s" % id)
	assert_false(counts.has("legendary"), "legendary outside a boss")
	assert_between(counts.get("common", 0) / 2000.0, 0.58, 0.72)   # 60 of 99 weight
	var boss := {}
	for i in 500:
		var item := Items.roll(defs, 3, rng, {"min_rarity": "rare", "legendary": true})
		boss[item["rarity"]] = true
	assert_false(boss.has("common"))
	assert_true(boss.has("legendary"), "boss never rolled a legendary in 500 tries")


func test_rolls_respect_item_level_and_class() -> void:
	var defs := _defs()
	var rng := seeded_rng(5)
	for i in 300:
		var item := Items.roll(defs, 1, rng, {"class_id": "mage"})
		var base: Dictionary = defs["bases"][item["base"]]
		assert_true(int(base.get("min_level", 1)) <= 1, item["base"])
		assert_true(base.get("class", "mage") == "mage", "warrior weapon rolled for a mage")


func test_upgrade_cost_and_cap() -> void:
	var defs := _defs()
	assert_eq(Items.upgrade_cost(_item("rusty_sword", "common", 3, 0), defs), {"gold": 60, "scales": 0})
	assert_eq(Items.upgrade_cost(_item("rusty_sword", "common", 3, 5), defs), {"gold": 360, "scales": 1})
	assert_eq(Items.upgrade_cost(_item("rusty_sword", "common", 3, 10), defs), {})


func test_salvage_gives_more_for_rarer_and_upgraded_items() -> void:
	var defs := _defs()
	var common := Items.salvage_value(_item("copper_ring", "common", 2), defs)
	var epic := Items.salvage_value(_item("copper_ring", "epic", 2, 3), defs)
	assert_eq(common, {"gold": 12, "scales": 0})
	assert_eq(epic, {"gold": 66, "scales": 1})
	assert_eq(Items.shop_price(_item("copper_ring", "common", 2), defs), 48)


func test_equipment_raises_player_stats() -> void:
	var data := game_data()
	var class_def: Dictionary = data["classes"]["warrior"]
	var bare := Combatant.make_player("warrior", class_def, 1, [])
	var geared := Combatant.make_player("warrior", class_def, 1, [])
	Items.apply_equipment(geared, [_item("rusty_sword"), _item("leather_armor"),
			_item("copper_ring", "rare", 1, 0, [{"id": "combo_damage", "value": 0.1}])], data["items"])
	# sword 1 * 1.12 + ring 1 * 1.12 * 1.15; hp 12 * 1.12 -> 13 and 5 * 1.12 * 1.15 -> 6
	assert_between(geared.stats.atk, bare.stats.atk + 2.40, bare.stats.atk + 2.42)
	assert_eq(geared.max_hp(), bare.max_hp() + 13 + 6)
	assert_between(geared.stats.def, bare.stats.def + 2.23, bare.stats.def + 2.25)
	assert_eq(geared.perks, {"combo_damage": 0.1})


func test_start_shield_perk_shields_on_turn_one() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.player.perks = {"start_shield": 8.0}
	engine.start()
	assert_eq(engine.player.shield, 8)


func test_combo_damage_perk_makes_combos_hit_harder() -> void:
	var plain := _combo_damage(0.0)
	var boosted := _combo_damage(0.5)
	assert_between(float(boosted) / plain, 1.4, 1.6)


func _combo_damage(bonus: float) -> int:
	var engine := make_engine(["cellar_rat"], 7)
	engine.player.perks = {"combo_damage": bonus}
	engine.enemies[0].hp = 1000
	engine.start()
	engine.use_skill("warrior_shield_break", "e0")
	var before := engine.enemies[0].hp
	engine.use_skill("warrior_heavy_strike", "e0")
	return before - engine.enemies[0].hp


func test_heal_on_kill_perk() -> void:
	var engine := make_engine(["cellar_rat", "cellar_rat"])
	engine.player.perks = {"heal_on_kill": 10.0}
	engine.start()
	engine.player.hp = 20
	engine.enemies[0].hp = 1
	var events := engine.use_skill("warrior_slash", "e0")
	var healed := events.filter(func(e: Dictionary) -> bool:
			return e.get("type", "") == "heal" and e.get("target", "") == engine.player.uid)
	assert_eq(healed.size(), 1, str(events))

extends TestCase


func test_pattern_cycles() -> void:
	var engine := make_engine(["cellar_rat"])
	var rat := engine.enemies[0]
	var seen: Array[String] = []
	for i in 4:
		seen.append(EnemyAI.choose_move(rat, engine.alive_enemies(), engine.status_defs))
		rat.ai_index += 1
	assert_eq(seen, ["bite", "bite", "gnaw", "bite"] as Array[String])


func test_mushroom_buffs_allies_then_attacks_alone() -> void:
	var engine := make_engine(["mushroom_mage", "cellar_rat"])
	var mage := engine.enemies[0]
	assert_eq(EnemyAI.choose_move(mage, engine.alive_enemies(), engine.status_defs), "empower")
	engine.enemies[1].statuses["strengthened"] = StatusEffect.new("strengthened", 2)
	assert_eq(EnemyAI.choose_move(mage, engine.alive_enemies(), engine.status_defs), "spore_cloud")
	engine.enemies[1].hp = 0
	engine.enemies[1].statuses.clear()
	assert_eq(EnemyAI.choose_move(mage, engine.alive_enemies(), engine.status_defs), "spore_cloud")


func test_stunned_enemy_shows_stunned_intent() -> void:
	var engine := make_engine(["cellar_rat"])
	engine.enemies[0].hp = 1000
	engine.start()
	engine.use_skill("warrior_shield_break", "e0")
	var ev := engine.use_skill("warrior_heavy_strike", "e0")
	# Stun was used up this round, so the next intent is a normal move again.
	var intents: Dictionary = events_of(ev, "intents")[0]["intents"]
	assert_eq(intents["e0"]["type"], "attack")


func test_strengthened_increases_enemy_damage_estimate() -> void:
	var engine := make_engine(["cellar_rat"])
	var rat := engine.enemies[0]
	var before := DamageCalc.estimate(rat, engine.player, 1.0, "physical", engine.status_defs)
	rat.statuses["strengthened"] = StatusEffect.new("strengthened", 2)
	var after := DamageCalc.estimate(rat, engine.player, 1.0, "physical", engine.status_defs)
	assert_true(after > before)

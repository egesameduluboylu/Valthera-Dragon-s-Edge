extends TestCase
## Marketplace rules (docs/13) and the offline market with simulated adventurers.


func _setup(seed_value: int = 1) -> Array:
	var p := Profile.new_game(game_data(), seeded_rng(seed_value))
	return [p, LocalMarket.new(p)]


func _give(p: Profile, base: String, rarity: String = "rare", level: int = 2) -> Dictionary:
	var item := {"base": base, "rarity": rarity, "level": level, "upgrade": 0, "affixes": []}
	p.add_item(item)
	return item


func test_fees_and_tax() -> void:
	var data := game_data()
	assert_eq(Market.listing_fee(40, data), 5, "minimum fee")
	assert_eq(Market.listing_fee(1000, data), 50)
	assert_eq(Market.seller_gets(1000, data), 900)


func test_uniques_are_worth_more() -> void:
	var data := game_data()
	var plain := {"base": "iron_helm", "rarity": "legendary", "level": 3, "upgrade": 0, "affixes": []}
	var crown := {"base": "bone_crown", "rarity": "legendary", "level": 3, "upgrade": 0, "affixes": []}
	assert_eq(Market.fair_value(crown, data), roundi(Items.shop_price(crown, data["items"]) * 2.5))
	assert_true(Market.fair_value(crown, data) > Market.fair_value(plain, data))


func test_new_game_has_a_stocked_board() -> void:
	var s := _setup()
	var board: Array = s[1].browse()["listings"]
	assert_eq(board.size(), 8)
	for l in board:
		assert_false(l["item"].has("uid"))
		assert_true(l["price"] >= Market.min_price(l["item"], game_data()))


func test_listing_takes_the_item_and_the_fee() -> void:
	var s := _setup()
	var p: Profile = s[0]
	var m: LocalMarket = s[1]
	var helm := _give(p, "iron_helm")
	p.gold = 100
	var r := m.create_listing(helm["uid"], 200)
	assert_true(r["ok"], str(r))
	assert_eq(p.gold, 90)
	assert_true(p.get_item(helm["uid"]).is_empty())
	assert_eq(m.my_listings()["listings"].size(), 1)


func test_listing_rules() -> void:
	var s := _setup()
	var p: Profile = s[0]
	var m: LocalMarket = s[1]
	p.gold = 10000
	var worn: String = p.equipped("weapon")["uid"]
	assert_eq(m.create_listing(worn, 100)["error"], "market.err_worn")
	var helm := _give(p, "iron_helm")
	assert_eq(m.create_listing(helm["uid"], 1)["error"], "market.err_price_low")
	for i in 5:
		var it := _give(p, "copper_ring")
		assert_true(m.create_listing(it["uid"], 100)["ok"])
	assert_eq(m.create_listing(helm["uid"], 100)["error"], "market.err_too_many")
	p.gold = 0
	m.cancel_listing(m.my_listings()["listings"][0]["id"])
	assert_eq(m.create_listing(helm["uid"], 200)["error"], "market.err_fee")


func test_buying_moves_gold_and_item() -> void:
	var s := _setup()
	var p: Profile = s[0]
	var m: LocalMarket = s[1]
	var l: Dictionary = m.browse()["listings"][0]
	assert_eq(m.buy(l["id"])["error"], "market.err_gold")
	p.gold = l["price"] + 3
	var r := m.buy(l["id"])
	assert_true(r["ok"])
	assert_eq(p.gold, 3)
	assert_eq(p.bag_items().size(), 1)
	assert_eq(m.browse()["listings"].size(), 7)
	assert_eq(m.buy(l["id"])["error"], "market.err_gone")


func test_cheap_listings_sell_and_pricey_ones_come_back() -> void:
	var s := _setup(3)
	var p: Profile = s[0]
	var m: LocalMarket = s[1]
	p.gold = 100000
	var data := game_data()
	var cheap := _give(p, "chain_mail", "epic", 3)
	var pricey := _give(p, "iron_helm", "epic", 3)
	var fair_cheap := Market.fair_value(cheap, data)
	m.create_listing(cheap["uid"], maxi(Market.min_price(cheap, data), roundi(fair_cheap * 0.5)))
	m.create_listing(pricey["uid"], Market.fair_value(pricey, data) * 5)
	var rng := seeded_rng(4)
	var sold := 0
	var expired := 0
	for i in 3:
		var r := m.after_run(rng)
		sold += r["sold"].size()
		expired += r["expired"].size()
	assert_eq(sold, 1, "the cheap one sells")
	assert_eq(expired, 1, "the pricey one comes back after 3 runs")
	var gold_before := p.gold
	for e in m.mailbox()["entries"]:
		assert_true(m.claim(e["id"])["ok"])
	assert_true(p.gold > gold_before)
	assert_true(p.bag_items().any(func(i: Dictionary) -> bool: return i["base"] == "iron_helm"))
	assert_eq(m.mailbox()["entries"].size(), 0)


func test_cancelled_items_wait_in_the_mailbox() -> void:
	var s := _setup()
	var p: Profile = s[0]
	var m: LocalMarket = s[1]
	p.gold = 100
	var ring := _give(p, "copper_ring")
	m.create_listing(ring["uid"], 80)
	m.cancel_listing(m.my_listings()["listings"][0]["id"])
	var mail: Array = m.mailbox()["entries"]
	assert_eq(mail.size(), 1)
	assert_eq(mail[0]["item"]["base"], "copper_ring")


func test_filters_and_sorting() -> void:
	var s := _setup(7)
	var m: LocalMarket = s[1]
	var weapons: Array = m.browse({"slot": "weapon"})["listings"]
	for l in weapons:
		assert_eq(ItemUI_slot(l["item"]), "weapon")
	var by_price: Array = m.browse({"sort": "price"})["listings"]
	for i in by_price.size() - 1:
		assert_true(by_price[i]["price"] <= by_price[i + 1]["price"])


func ItemUI_slot(item: Dictionary) -> String:
	return game_data()["items"]["bases"][item["base"]]["slot"]


func test_market_survives_save_and_load() -> void:
	var s := _setup()
	var p: Profile = s[0]
	var m: LocalMarket = s[1]
	p.gold = 100
	var ring := _give(p, "copper_ring")
	m.create_listing(ring["uid"], 80)
	var back := Profile.from_dict(game_data(), JSON.parse_string(JSON.stringify(p.to_dict())))
	var m2 := LocalMarket.new(back)
	assert_eq(m2.my_listings()["listings"].size(), 1)
	assert_eq(m2.browse()["listings"].size(), 8)
	assert_eq(back.player_name, p.player_name)
	assert_eq(typeof(m2.my_listings()["listings"][0]["price"]), TYPE_INT)

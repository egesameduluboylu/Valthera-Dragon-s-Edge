extends SceneTree
## End-to-end check of SupabaseMarket against server/tests/mock_gateway.py (a local
## PostgreSQL with the real migrations). Run by server/tests/run_client_check.sh.

var failures := 0


func _check(cond: bool, msg: String) -> void:
	if not cond:
		failures += 1
		print("FAIL ", msg)


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var url := OS.get_environment("MARKET_URL")
	var data := DataLoader.load_game_data()
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	# two players on two "phones"
	var a := Profile.new_game(data, rng)
	a.player_name = "Satıcı Ayşe"
	var b := Profile.new_game(data, rng)
	b.player_name = "Alıcı Mert"
	var ma := SupabaseMarket.new(a, url, "anon")
	var mb := SupabaseMarket.new(b, url, "anon")
	root.add_child(ma)
	root.add_child(mb)
	ma._session = {}
	mb._session = {}

	var helm := {"base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 1, "affixes": [{"id": "crit", "value": 0.02}]}
	a.add_item(helm)
	a.gold = 100
	var r: Dictionary = await ma.create_listing(helm["uid"], 300)
	_check(r.get("ok", false), "create %s" % r)
	_check(a.gold == 85, "fee paid, gold %d" % a.gold)
	_check(a.get_item(helm["uid"]).is_empty(), "item left the bag")

	r = await mb.browse({"slot": "helm"})
	_check(r.get("ok", false) and r["listings"].size() == 1, "browse %s" % r)
	var listing: Dictionary = r["listings"][0]
	_check(listing["seller"] == "Satıcı Ayşe", "seller name")
	r = await mb.buy(str(listing["id"]), int(listing["price"]))
	_check(r.get("error", "") == "market.err_gold", "b can't afford: %s" % r)
	b.gold = 500
	r = await mb.buy(str(listing["id"]), int(listing["price"]))
	_check(r.get("ok", false), "buy %s" % r)
	_check(b.gold == 200, "b paid, gold %d" % b.gold)
	_check(b.bag_items().any(func(i: Dictionary) -> bool: return i["base"] == "iron_helm" and i["level"] is int), "b got the helm")

	# token expiry is handled by refreshing, also for a saved token when the game starts
	# (market_join is the first call then)
	await _post(url + "/_test/expire_tokens")
	mb._joined_as = ""
	r = await mb.my_listings()
	_check(r.get("ok", false), "join with an expired saved token %s" % r)
	r = await ma.mailbox()
	_check(r.get("ok", false) and r["entries"].size() == 1, "mailbox after refresh %s" % r)

	# a claim whose answer is lost is finished the next time the mailbox is opened
	var saves := [0]
	ma.save_profile = func() -> void: saves[0] += 1
	var mail_id := str(r["entries"][0]["id"])
	a.online_claims[mail_id] = "lost-answer-op-1"
	r = await ma._rpc("market_claim", {"p_id": mail_id, "p_op": "lost-answer-op-1"})
	_check(r.get("ok", false) and a.gold == 85, "server paid, game did not see it: %s, gold %d" % [r, a.gold])
	r = await ma.mailbox()
	_check(r.get("ok", false) and r["entries"].is_empty(), "claimed mail gone %s" % r)
	_check(a.gold == 85 + 270 and a.online_claims.is_empty(), "resumed claim paid once, gold %d" % a.gold)
	_check(saves[0] == 1, "reward and pending id saved together, saves %d" % saves[0])
	r = await ma.mailbox()
	_check(a.gold == 85 + 270, "no second payment, gold %d" % a.gold)

	# a normal claim: the op id is saved before asking and cleared with the reward
	var ring := {"base": "copper_ring", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}
	a.add_item(ring)
	r = await ma.create_listing(ring["uid"], 50)
	_check(r.get("ok", false), "list ring %s" % r)
	r = await ma.cancel_listing(str(r["listing"]["id"]))
	_check(r.get("ok", false), "cancel ring %s" % r)
	r = await ma.mailbox()
	_check(r.get("ok", false) and r["entries"].size() == 1, "ring in mail %s" % r)
	saves[0] = 0
	r = await ma.claim(str(r["entries"][0]["id"]))
	_check(r.get("ok", false) and a.online_claims.is_empty() and saves[0] == 2, "claim ring %s, saves %d" % [r, saves[0]])
	_check(a.bag_items().any(func(i: Dictionary) -> bool: return i["base"] == "copper_ring"), "ring back in the bag")

	# a cheater's item is refused and stays in the bag
	var fake := {"base": "kingslayer", "rarity": "legendary", "level": 20, "upgrade": 10,
			"affixes": [{"id": "atk", "value": 999.0}, {"id": "crit", "value": 0.5}]}
	a.add_item(fake)
	r = await ma.create_listing(fake["uid"], 5000)
	_check(r.get("error", "") == "market.err_bad_item", "fake refused %s" % r)
	_check(not a.get_item(fake["uid"]).is_empty(), "fake still in bag")

	print("online client check: %s" % ("OK" if failures == 0 else "%d failures" % failures))
	quit(1 if failures > 0 else 0)


func _post(u: String) -> void:
	var req := HTTPRequest.new()
	root.add_child(req)
	req.request(u, ["apikey: anon"], HTTPClient.METHOD_POST, "{}")
	await req.request_completed
	req.queue_free()

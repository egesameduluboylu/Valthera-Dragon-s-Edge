class_name LocalMarket
extends RefCounted
## The marketplace without a server (docs/13): other adventurers are simulated. Their
## listings sit on the board and change after every run; the player's own listings may
## sell to them after a run, depending on the price. Sales and unsold items wait in the
## mailbox. Everything is stored in Profile.market, so it is saved with the profile.
##
## Same calls as the online market; every call returns a dictionary with "ok" and, on
## failure, "error" (a text key).

var profile: Profile
var data: Dictionary


func _init(p_profile: Profile) -> void:
	profile = p_profile
	data = p_profile.data
	if not profile.market.has("board"):
		profile.market = {"board": [], "listings": [], "mailbox": [], "next_id": 1}


func is_online() -> bool:
	return false


func _cfg() -> Dictionary:
	return data["market"]["offline"]


func _next_id() -> String:
	var id := "m%d" % int(profile.market["next_id"])
	profile.market["next_id"] = int(profile.market["next_id"]) + 1
	return id


# ---------------------------------------------------------------- browsing

## filter: {slot, rarity, unique, sort: "price" | "price_desc" | "newest"}
func browse(filter: Dictionary = {}) -> Dictionary:
	var out: Array = []
	for l in profile.market["board"]:
		if Market.matches(l, filter, data["items"]):
			out.append(l)
	Market.sort_listings(out, filter.get("sort", "price"))
	return {"ok": true, "listings": out}


func my_listings() -> Dictionary:
	return {"ok": true, "listings": profile.market["listings"].duplicate()}


func mailbox() -> Dictionary:
	return {"ok": true, "entries": profile.market["mailbox"].duplicate()}


# ---------------------------------------------------------------- selling

func create_listing(uid: String, price: int) -> Dictionary:
	var item := profile.get_item(uid)
	if item.is_empty():
		return _fail("market.err_no_item")
	if profile.is_equipped(uid):
		return _fail("market.err_worn")
	if profile.market["listings"].size() >= int(data["market"]["max_listings"]):
		return _fail("market.err_too_many")
	var err := Market.price_error(item, price, data)
	if err != "":
		return _fail(err)
	var fee := Market.listing_fee(price, data)
	if profile.gold < fee:
		return _fail("market.err_fee")
	profile.gold -= fee
	profile.inventory.erase(item)
	var listing := {"id": _next_id(), "seller": profile.player_name, "item": Market.listed_copy(item),
			"price": price, "runs_left": int(_cfg()["listing_runs"]), "mine": true}
	profile.market["listings"].append(listing)
	return {"ok": true, "listing": listing, "fee": fee}


## Takes a listing down; the item goes to the mailbox. The fee is not refunded.
func cancel_listing(id: String) -> Dictionary:
	var l := _find(profile.market["listings"], id)
	if l.is_empty():
		return _fail("market.err_gone")
	profile.market["listings"].erase(l)
	_mail({"kind": "item", "item": l["item"], "note": "market.mail_cancelled"})
	return {"ok": true}


# ---------------------------------------------------------------- buying

func buy(id: String, _price: int = -1) -> Dictionary:
	var l := _find(profile.market["board"], id)
	if l.is_empty():
		return _fail("market.err_gone")
	if profile.gold < int(l["price"]):
		return _fail("market.err_gold")
	if profile.bag_items().size() >= profile.bag_size():
		return _fail("market.err_bag")
	profile.gold -= int(l["price"])
	profile.market["board"].erase(l)
	var item: Dictionary = l["item"].duplicate(true)
	profile.add_item(item)
	return {"ok": true, "item": item}


# ---------------------------------------------------------------- mailbox

func claim(id: String) -> Dictionary:
	var m := _find(profile.market["mailbox"], id)
	if m.is_empty():
		return _fail("market.err_gone")
	if m["kind"] == "item":
		if profile.bag_items().size() >= profile.bag_size():
			return _fail("market.err_bag")
		var item: Dictionary = m["item"].duplicate(true)
		profile.add_item(item)
		profile.market["mailbox"].erase(m)
		return {"ok": true, "item": item}
	profile.gold += int(m.get("gold", 0))
	profile.market["mailbox"].erase(m)
	return {"ok": true, "gold": int(m.get("gold", 0))}


# ---------------------------------------------------------------- time passing

## Called after every run: the player's listings may sell or expire, and the board
## gets some new items from other adventurers. Returns {sold: [listings], expired: [...]}.
func after_run(rng: RandomNumberGenerator) -> Dictionary:
	var sold: Array = []
	var expired: Array = []
	for l in profile.market["listings"].duplicate():
		if rng.randf() < Market.sell_chance(l["item"], int(l["price"]), data):
			sold.append(l)
			profile.market["listings"].erase(l)
			_mail({"kind": "gold", "gold": Market.seller_gets(int(l["price"]), data), "item": l["item"],
					"buyer": _trader(rng), "note": "market.mail_sold"})
			continue
		l["runs_left"] = int(l["runs_left"]) - 1
		if l["runs_left"] <= 0:
			expired.append(l)
			profile.market["listings"].erase(l)
			_mail({"kind": "item", "item": l["item"], "note": "market.mail_expired"})
	_turn_over_board(rng)
	return {"sold": sold, "expired": expired}


## Drops the oldest few board listings and fills back up to board_size.
func _turn_over_board(rng: RandomNumberGenerator) -> void:
	var board: Array = profile.market["board"]
	var drop := mini(int(_cfg()["board_turnover"]), board.size())
	if board.size() >= int(_cfg()["board_size"]):
		for i in drop:
			board.pop_front()
	while board.size() < int(_cfg()["board_size"]):
		board.append(_trader_listing(rng))


func _trader_listing(rng: RandomNumberGenerator) -> Dictionary:
	var defs: Dictionary = data["items"]
	var lv := clampi(profile.level(), 1, profile.shop_level() + 1)
	var item: Dictionary
	var uniques: Array = []
	for id in defs["bases"]:
		var b: Dictionary = defs["bases"][id]
		if b.has("unique") and b.get("class", profile.active_class) == profile.active_class:
			uniques.append(id)
	if not uniques.is_empty() and rng.randf() < float(_cfg()["unique_chance"]):
		item = Items.roll(defs, lv, rng, {"base": uniques[rng.randi_range(0, uniques.size() - 1)]})
	else:
		item = Items.roll(defs, lv, rng, {"class_id": profile.active_class, "min_rarity": _cfg()["rarity_floor"]})
	item.erase("uid")
	var spread: Array = _cfg()["price_spread"]
	var price := roundi(Market.fair_value(item, data) * rng.randf_range(float(spread[0]), float(spread[1])))
	return {"id": _next_id(), "seller": _trader(rng), "item": item, "price": maxi(price, Market.min_price(item, data))}


func _trader(rng: RandomNumberGenerator) -> String:
	var names: Array = data["market"]["trader_names"]
	return names[rng.randi_range(0, names.size() - 1)]


func _mail(entry: Dictionary) -> void:
	entry["id"] = _next_id()
	profile.market["mailbox"].append(entry)


static func _find(list: Array, id: String) -> Dictionary:
	for x in list:
		if str(x["id"]) == id:
			return x
	return {}


static func _fail(key: String) -> Dictionary:
	return {"ok": false, "error": key}

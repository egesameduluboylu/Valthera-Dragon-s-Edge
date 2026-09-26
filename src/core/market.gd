class_name Market
extends RefCounted
## Player marketplace rules (docs/13): prices, fees, tax and listing checks. Shared by
## the offline market (LocalMarket) and mirrored by the server functions in
## server/supabase, so both give the same answers.
##
## A listing is {id, seller, item, price, mine?}; the item carries no uid while listed.


## A fair price for an item: the merchant's price, more for named unique items.
static func fair_value(item: Dictionary, data: Dictionary) -> int:
	var v := Items.shop_price(item, data["items"])
	if Items.is_unique(item, data["items"]):
		v = roundi(v * float(data["market"].get("unique_value_mult", 1.0)))
	return maxi(1, v)


## Paid when listing, not refunded: keeps the board from filling with junk.
static func listing_fee(price: int, data: Dictionary) -> int:
	var m: Dictionary = data["market"]
	return maxi(int(m.get("min_listing_fee", 0)), roundi(price * float(m.get("listing_fee_percent", 0))))


## What the seller receives when the item sells.
static func seller_gets(price: int, data: Dictionary) -> int:
	return price - roundi(price * float(data["market"].get("tax_percent", 0)))


static func min_price(item: Dictionary, data: Dictionary) -> int:
	return maxi(1, Items.salvage_value(item, data["items"])["gold"])


static func max_price(data: Dictionary) -> int:
	return int(data["market"].get("max_price", 1000000))


## "" when `price` is allowed for `item`, else an error key.
static func price_error(item: Dictionary, price: int, data: Dictionary) -> String:
	if price < min_price(item, data):
		return "market.err_price_low"
	if price > max_price(data):
		return "market.err_price_high"
	return ""


## A copy of the item that is safe to publish (no uid).
static func listed_copy(item: Dictionary) -> Dictionary:
	var c := item.duplicate(true)
	c.erase("uid")
	return c


## Offline only: chance that a player's listing sells after one run, by how the price
## compares to the fair value.
static func sell_chance(item: Dictionary, price: int, data: Dictionary) -> float:
	var sc: Dictionary = data["market"]["offline"]["sell_chance"]
	var ratio := float(price) / float(fair_value(item, data))
	return clampf(float(sc["base"]) - float(sc["per_ratio"]) * ratio, float(sc["min"]), float(sc["max"]))


static func matches(listing: Dictionary, filter: Dictionary, defs: Dictionary) -> bool:
	var item: Dictionary = listing["item"]
	if filter.get("slot", "") != "" and defs["bases"][item["base"]]["slot"] != filter["slot"]:
		return false
	if filter.get("rarity", "") != "" and item["rarity"] != filter["rarity"]:
		return false
	if filter.get("unique", false) and not Items.is_unique(item, defs):
		return false
	return true


static func sort_listings(listings: Array, sort: String) -> void:
	match sort:
		"price_desc":
			listings.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["price"] > b["price"])
		"newest":
			listings.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return str(a["id"]) > str(b["id"]))
		_:
			listings.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["price"] < b["price"])

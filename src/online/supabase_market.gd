class_name SupabaseMarket
extends Node
## The online marketplace (docs/13): the same calls as LocalMarket, served by the
## Supabase functions in server/supabase. Players sign in anonymously the first time;
## the session is kept in user://online_session.json. Every call is a coroutine:
##   var r: Dictionary = await market.browse({"slot": "weapon"})
##
## The server owns listings and the mailbox; the local profile only changes after the
## server said ok (the item leaves the bag when it is listed, gold is paid on a buy and
## added on a claim).

const SESSION_PATH := "user://online_session.json"
const TIMEOUT := 12.0

var profile: Profile
var data: Dictionary
var url: String
var anon_key: String
var _session: Dictionary = {}     # access_token, refresh_token, user_id
var _joined_as: String = ""


func _init(p_profile: Profile, p_url: String, p_anon_key: String) -> void:
	profile = p_profile
	data = p_profile.data
	url = p_url.trim_suffix("/")
	anon_key = p_anon_key
	_load_session()


func is_online() -> bool:
	return true


# ---------------------------------------------------------------- market calls

func browse(filter: Dictionary = {}) -> Dictionary:
	return await _rpc("market_browse", {"p_slot": filter.get("slot", ""), "p_rarity": filter.get("rarity", ""),
			"p_unique": filter.get("unique", false), "p_sort": filter.get("sort", "price"), "p_limit": 40, "p_offset": 0})


func my_listings() -> Dictionary:
	return await _rpc("market_my_listings", {})


func mailbox() -> Dictionary:
	return await _rpc("market_mailbox", {})


func create_listing(uid: String, price: int) -> Dictionary:
	var item := profile.get_item(uid)
	if item.is_empty():
		return _fail("market.err_no_item")
	if profile.is_equipped(uid):
		return _fail("market.err_worn")
	var err := Market.price_error(item, price, data)
	if err != "":
		return _fail(err)
	var fee := Market.listing_fee(price, data)
	if profile.gold < fee:
		return _fail("market.err_fee")
	var r := await _rpc("market_create_listing", {"p_item": Market.listed_copy(item), "p_price": price})
	if r.get("ok", false):
		# The item may have changed while we waited; take exactly what was listed.
		var still := profile.get_item(uid)
		if not still.is_empty():
			profile.inventory.erase(still)
		profile.gold -= int(r.get("fee", fee))
	return r


func cancel_listing(id: String) -> Dictionary:
	return await _rpc("market_cancel_listing", {"p_id": id})


func buy(id: String, price: int = -1) -> Dictionary:
	if price >= 0 and profile.gold < price:
		return _fail("market.err_gold")
	if profile.bag_items().size() >= profile.bag_size():
		return _fail("market.err_bag")
	var r := await _rpc("market_buy", {"p_id": id})
	if r.get("ok", false):
		profile.gold -= int(r.get("price", maxi(price, 0)))
		var item: Dictionary = r["item"]
		_clean(item)
		profile.add_item(item)
		r["item"] = item
	return r


func claim(id: String) -> Dictionary:
	if profile.bag_items().size() >= profile.bag_size():
		# Items need room; gold doesn't, but we can't tell which one it is before asking.
		var box := await mailbox()
		for e in box.get("entries", []):
			if str(e["id"]) == id and e["kind"] == "item":
				return _fail("market.err_bag")
	var r := await _rpc("market_claim", {"p_id": id})
	if r.get("ok", false):
		if r.has("gold"):
			profile.gold += int(r["gold"])
		if r.get("item") is Dictionary:
			var item: Dictionary = r["item"]
			_clean(item)
			profile.add_item(item)
	return r


## Online listings sell to real players; nothing happens between runs.
func after_run(_rng: RandomNumberGenerator) -> Dictionary:
	return {"sold": [], "expired": []}


# ---------------------------------------------------------------- plumbing

func _rpc(fn: String, body: Dictionary) -> Dictionary:
	var ready := await _ensure_session()
	if not ready.get("ok", false):
		return ready
	var r := await _call_rpc(fn, body)
	if r.get("_status", 0) == 401:
		_session.erase("access_token")
		var again := await _refresh()
		if not again.get("ok", false):
			return again
		r = await _call_rpc(fn, body)
	r.erase("_status")
	return r


func _call_rpc(fn: String, body: Dictionary) -> Dictionary:
	var res := await _http("/rest/v1/rpc/" + fn, body, _session.get("access_token", ""))
	if res["status"] == 401:
		return {"ok": false, "error": "market.err_auth", "_status": 401}
	if res["status"] < 200 or res["status"] >= 300 or not res["json"] is Dictionary:
		return {"ok": false, "error": "market.err_offline", "_status": res["status"]}
	var out: Dictionary = res["json"]
	out["_status"] = res["status"]
	return out


func _ensure_session() -> Dictionary:
	if _session.get("access_token", "") == "":
		var r: Dictionary
		if _session.get("refresh_token", "") != "":
			r = await _refresh()
		else:
			r = await _sign_up()
		if not r.get("ok", false):
			return r
	if _joined_as != profile.player_name:
		var j := await _call_rpc("market_join", {"p_name": profile.player_name})
		if not j.get("ok", false):
			return j
		_joined_as = profile.player_name
	return {"ok": true}


## Anonymous sign-in (Supabase: POST /auth/v1/signup with no email).
func _sign_up() -> Dictionary:
	var res := await _http("/auth/v1/signup", {"data": {"name": profile.player_name}}, "")
	return _take_session(res)


func _refresh() -> Dictionary:
	if _session.get("refresh_token", "") == "":
		return await _sign_up()
	var res := await _http("/auth/v1/token?grant_type=refresh_token", {"refresh_token": _session["refresh_token"]}, "")
	if res["status"] == 400 or res["status"] == 401:
		_session = {}
		return await _sign_up()
	return _take_session(res)


func _take_session(res: Dictionary) -> Dictionary:
	if res["status"] < 200 or res["status"] >= 300 or not res["json"] is Dictionary \
			or not res["json"].has("access_token"):
		return _fail("market.err_offline")
	_session = {"access_token": res["json"]["access_token"], "refresh_token": res["json"].get("refresh_token", ""),
			"user_id": res["json"].get("user", {}).get("id", "")}
	_joined_as = ""
	_save_session()
	return {"ok": true}


## POSTs JSON; returns {status, json}. status 0 means no connection.
func _http(path: String, body: Dictionary, token: String) -> Dictionary:
	var req := HTTPRequest.new()
	req.timeout = TIMEOUT
	add_child(req)
	var headers := ["Content-Type: application/json", "apikey: " + anon_key,
			"Authorization: Bearer " + (token if token != "" else anon_key)]
	var err := req.request(url + path, headers, HTTPClient.METHOD_POST, JSON.stringify(body))
	if err != OK:
		req.queue_free()
		return {"status": 0, "json": null}
	var result: Array = await req.request_completed
	req.queue_free()
	var text: String = (result[3] as PackedByteArray).get_string_from_utf8()
	return {"status": int(result[1]) if int(result[0]) == HTTPRequest.RESULT_SUCCESS else 0,
			"json": JSON.parse_string(text) if text != "" else null}


func _load_session() -> void:
	if FileAccess.file_exists(SESSION_PATH):
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(SESSION_PATH))
		if d is Dictionary:
			_session = d


func _save_session() -> void:
	var f := FileAccess.open(SESSION_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(_session))


## JSON numbers come back as floats.
static func _clean(item: Dictionary) -> void:
	item["level"] = int(item.get("level", 1))
	item["upgrade"] = int(item.get("upgrade", 0))
	item.erase("uid")


static func _fail(key: String) -> Dictionary:
	return {"ok": false, "error": key}

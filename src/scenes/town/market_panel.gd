class_name MarketPanel
extends Control
## The adventurers' market at the inn (docs/13): buy from other players, list your own
## items, manage listings and collect sales from the mailbox. Talks to GameState.market,
## which is the offline LocalMarket or the online SupabaseMarket; every call is awaited.

signal closed

const TABS := ["buy", "sell", "mine", "mail"]
const FILTERS := [["", "market.all"], ["weapon", "slot.weapon"], ["armor", "slot.armor"],
		["helm", "slot.helm"], ["accessory", "slot.accessory"], ["unique", "market.uniques"]]

var _content: VBoxContainer
var _tabs_row: HBoxContainer
var _body: VBoxContainer
var _npc_holder: VBoxContainer
var _tab: String = "buy"
var _filter: String = ""
var _sort: String = "price"
var _selected: String = ""
var _price: int = 0
var _busy: bool = false
var _mail_count: int = 0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("market.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	_npc_holder = VBoxContainer.new()
	_content.add_child(_npc_holder)
	_say(DataDB.t("market.line_online" if _market().is_online() else "market.line_offline"))
	_tabs_row = HBoxContainer.new()
	_tabs_row.add_theme_constant_override("separation", 8)
	_content.add_child(_tabs_row)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_content.add_child(scroll)
	_body = VBoxContainer.new()
	_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_body.add_theme_constant_override("separation", 12)
	scroll.add_child(_body)
	_refresh_mail_count()
	show_tab("buy")


func _market() -> Variant:
	return GameState.market


func _profile() -> Profile:
	return GameState.profile


func _say(line: String) -> void:
	for c in _npc_holder.get_children():
		c.queue_free()
	_npc_holder.add_child(UIKit.npc_row("res://assets/town/npc_innkeeper.png", DataDB.t("market.npc"), line))


func _draw_tabs() -> void:
	for c in _tabs_row.get_children():
		c.queue_free()
	for id in TABS:
		var text := DataDB.t("market.tab_" + id)
		if id == "mail" and _mail_count > 0:
			text += " (%d)" % _mail_count
		var b := UIKit.button(text, "", show_tab.bind(id), 22)
		b.custom_minimum_size.y = 64
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if id == _tab:
			UIKit.primary(b)
		_tabs_row.add_child(b)


func show_tab(id: String) -> void:
	_tab = id
	_selected = ""
	_draw_tabs()
	await _redraw()


func _clear_body() -> void:
	for c in _body.get_children():
		c.queue_free()


func _loading() -> void:
	_clear_body()
	var l := UIKit.label(DataDB.t("market.loading"), 22, UITheme.TEXT_MUTED)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_body.add_child(l)


func _redraw() -> void:
	match _tab:
		"buy":
			await _draw_buy()
		"sell":
			_draw_sell()
		"mine":
			await _draw_mine()
		"mail":
			await _draw_mail()


func _error(r: Dictionary) -> void:
	_say(DataDB.t(r.get("error", "market.err_offline")))


func _changed() -> void:
	GameState.changed()


# ---------------------------------------------------------------- buy

func _draw_buy() -> void:
	_loading()
	var filter := {"sort": _sort}
	if _filter == "unique":
		filter["unique"] = true
	elif _filter != "":
		filter["slot"] = _filter
	var r: Dictionary = await _market().browse(filter)
	if _tab != "buy":
		return
	_clear_body()
	var chips := HFlowContainer.new()
	chips.add_theme_constant_override("h_separation", 8)
	chips.add_theme_constant_override("v_separation", 8)
	_body.add_child(chips)
	for f in FILTERS:
		var id: String = f[0]
		var b := UIKit.button(DataDB.t(f[1]), "", func() -> void:
			_filter = id
			_draw_buy(), 20)
		b.custom_minimum_size = Vector2(0, 56)
		if id == _filter:
			UIKit.primary(b)
		chips.add_child(b)
	var sort := UIKit.button(DataDB.t("market.sort_cheap" if _sort == "price" else "market.sort_pricey"), "",
			func() -> void:
				_sort = "price_desc" if _sort == "price" else "price"
				_draw_buy(), 20)
	sort.custom_minimum_size = Vector2(0, 56)
	chips.add_child(sort)
	if not r.get("ok", false):
		_error(r)
		return
	var listings: Array = r["listings"]
	if listings.is_empty():
		_body.add_child(_muted(DataDB.t("market.empty")))
	for l in listings:
		_body.add_child(_listing_row(l))


func _listing_row(l: Dictionary) -> PanelContainer:
	var p := _profile()
	var item: Dictionary = l["item"]
	_fix(item)
	var card := _card()
	var v: VBoxContainer = card.get_child(0)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	v.add_child(h)
	h.add_child(ItemUI.tile(item, 100))
	var d := ItemUI.details(item, p.equipped(p.slot_of(item)) if p.equip_block_reason(item) != "class" else null)
	d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(d)
	var foot := HBoxContainer.new()
	v.add_child(foot)
	var seller := UIKit.label(DataDB.tf("market.seller", {"name": l.get("seller", "?")}), 20, UITheme.TEXT_MUTED)
	seller.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foot.add_child(seller)
	var price := int(l["price"])
	var id := str(l["id"])
	var b := UIKit.primary(UIKit.button("%s  %d" % [DataDB.t("market.buy"), price], ItemUI.ITEM_GOLD, func() -> void:
		_buy(id, price, item), 22))
	b.custom_minimum_size = Vector2(220, 64)
	b.disabled = p.gold < price or l.get("mine", false)
	foot.add_child(b)
	return card


func _buy(id: String, price: int, item: Dictionary) -> void:
	if _busy:
		return
	_busy = true
	var r: Dictionary = await _market().buy(id, price)
	_busy = false
	if not r.get("ok", false):
		_error(r)
	else:
		Audio.play("buy")
		_say(DataDB.tf("market.bought", {"item": ItemUI.item_name(item)}))
		_changed()
	await _draw_buy()


# ---------------------------------------------------------------- sell

func _draw_sell() -> void:
	_clear_body()
	var p := _profile()
	var sel := p.get_item(_selected)
	if sel.is_empty():
		_body.add_child(_muted(DataDB.t("market.sell_pick")))
	else:
		_body.add_child(_sell_card(sel))
	var grid := GridContainer.new()
	grid.columns = 5
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	_body.add_child(grid)
	var items := p.bag_items()
	items.reverse()
	for item in items:
		var uid: String = item["uid"]
		var b := ItemUI.tile_button(item, 112, func() -> void:
			_selected = uid
			_price = Market.fair_value(p.get_item(uid), DataDB.data)
			_draw_sell())
		if uid == _selected:
			b.modulate = Color(1.3, 1.25, 1.0)
		grid.add_child(b)


func _sell_card(item: Dictionary) -> PanelContainer:
	var data := DataDB.data
	var card := _card()
	var v: VBoxContainer = card.get_child(0)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	v.add_child(h)
	h.add_child(ItemUI.tile(item, 100))
	var d := ItemUI.details(item)
	d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(d)
	var fair := Market.fair_value(item, data)
	_price = clampi(_price, Market.min_price(item, data), Market.max_price(data))
	v.add_child(UIKit.label(DataDB.tf("market.fair", {"v": fair}), 20, UITheme.TEXT_MUTED))
	# price stepper
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	v.add_child(row)
	for step in [-0.25, -0.05]:
		row.add_child(_step_button(step, item))
	var price := UIKit.counter(ItemUI.ITEM_GOLD, str(_price), UITheme.GOLD, 44)
	price.custom_minimum_size.x = 170
	price.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(price)
	for step in [0.05, 0.25]:
		row.add_child(_step_button(step, item))
	var fee := Market.listing_fee(_price, data)
	var tax := roundi(float(data["market"]["tax_percent"]) * 100)
	v.add_child(UIKit.label(DataDB.tf("market.fee", {"v": fee}), 20, UITheme.TEXT if _profile().gold >= fee else ItemUI.DOWN))
	v.add_child(UIKit.label(DataDB.tf("market.you_get", {"v": Market.seller_gets(_price, data), "tax": tax}), 20, ItemUI.UP))
	var uid: String = item["uid"]
	var go := UIKit.primary(UIKit.button(DataDB.t("market.list"), "", func() -> void: _list(uid, item)))
	go.disabled = _profile().gold < fee
	v.add_child(go)
	return card


func _step_button(step: float, item: Dictionary) -> Button:
	var b := UIKit.button(("+" if step > 0 else "−") + str(roundi(absf(step) * 100)) + "%", "", func() -> void:
		var fair := Market.fair_value(item, DataDB.data)
		_price = maxi(1, _price + roundi(fair * step))
		_draw_sell(), 20)
	b.custom_minimum_size = Vector2(84, 60)
	return b


func _list(uid: String, item: Dictionary) -> void:
	if _busy:
		return
	_busy = true
	var r: Dictionary = await _market().create_listing(uid, _price)
	_busy = false
	if not r.get("ok", false):
		_error(r)
		return
	_say(DataDB.tf("market.listed", {"item": ItemUI.item_name(item)}))
	_changed()
	_selected = ""
	_draw_sell()


# ---------------------------------------------------------------- my listings

func _draw_mine() -> void:
	_loading()
	var r: Dictionary = await _market().my_listings()
	if _tab != "mine":
		return
	_clear_body()
	if not r.get("ok", false):
		_error(r)
		return
	var listings: Array = r["listings"]
	if listings.is_empty():
		_body.add_child(_muted(DataDB.t("market.no_listings")))
	for l in listings:
		var item: Dictionary = l["item"]
		_fix(item)
		var card := _card()
		var v: VBoxContainer = card.get_child(0)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		v.add_child(h)
		h.add_child(ItemUI.tile(item, 88))
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(info)
		info.add_child(UIKit.label(ItemUI.item_name(item), 26, ItemUI.color(item)))
		info.add_child(UIKit.counter(ItemUI.ITEM_GOLD, str(int(l["price"])), UITheme.GOLD, 30))
		var when := DataDB.tf("market.runs_left", {"n": int(l.get("runs_left", 0))}) if l.has("runs_left") \
				else DataDB.tf("market.expires", {"h": _hours_left(str(l.get("expires_at", "")))})
		info.add_child(UIKit.label(when, 19, UITheme.TEXT_MUTED))
		var id := str(l["id"])
		var cancel := UIKit.button(DataDB.t("market.cancel"), "", func() -> void: _cancel(id), 22)
		cancel.custom_minimum_size = Vector2(160, 64)
		cancel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(cancel)
		_body.add_child(card)


func _hours_left(iso: String) -> int:
	if iso == "":
		return 0
	var t := Time.get_unix_time_from_datetime_string(iso.substr(0, 19))
	return maxi(0, ceili((t - Time.get_unix_time_from_system()) / 3600.0))


func _cancel(id: String) -> void:
	if _busy:
		return
	_busy = true
	var r: Dictionary = await _market().cancel_listing(id)
	_busy = false
	if not r.get("ok", false):
		_error(r)
	_changed()
	await _refresh_mail_count()
	await _draw_mine()


# ---------------------------------------------------------------- mailbox

func _draw_mail() -> void:
	_loading()
	var r: Dictionary = await _market().mailbox()
	if _tab != "mail":
		return
	_clear_body()
	if not r.get("ok", false):
		_error(r)
		return
	var entries: Array = r["entries"]
	_mail_count = entries.size()
	_draw_tabs()
	if entries.is_empty():
		_body.add_child(_muted(DataDB.t("market.mail_empty")))
		return
	var all := UIKit.primary(UIKit.button(DataDB.t("market.claim_all"), "", func() -> void: _claim_all(entries)))
	_body.add_child(all)
	for e in entries:
		var item: Dictionary = e.get("item", {}) if e.get("item") is Dictionary else {}
		if not item.is_empty():
			_fix(item)
		var card := _card()
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		card.get_child(0).add_child(h)
		if e["kind"] == "gold":
			h.add_child(UIKit.icon(ItemUI.ITEM_GOLD, 72))
		else:
			h.add_child(ItemUI.tile(item, 88))
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(info)
		var name_ := ItemUI.item_name(item) if not item.is_empty() else ""
		info.add_child(UIKit.wrapped(DataDB.tf(str(e.get("note", "")), {"item": name_, "buyer": e.get("buyer", "?")}), 21))
		if e["kind"] == "gold":
			info.add_child(UIKit.counter(ItemUI.ITEM_GOLD, "+%d" % int(e.get("gold", 0)), UITheme.GOLD, 30))
		var id := str(e["id"])
		var take := UIKit.button(DataDB.t("market.claim"), "", func() -> void: _claim(id), 22)
		take.custom_minimum_size = Vector2(120, 64)
		take.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(take)
		_body.add_child(card)


func _claim(id: String) -> void:
	if _busy:
		return
	_busy = true
	var r: Dictionary = await _market().claim(id)
	_busy = false
	if not r.get("ok", false):
		_error(r)
	_changed()
	await _draw_mail()


func _claim_all(entries: Array) -> void:
	if _busy:
		return
	_busy = true
	for e in entries:
		var r: Dictionary = await _market().claim(str(e["id"]))
		if not r.get("ok", false):
			_error(r)
			break
	_busy = false
	_changed()
	await _draw_mail()


func _refresh_mail_count() -> void:
	var r: Dictionary = await _market().mailbox()
	_mail_count = r.get("entries", []).size() if r.get("ok", false) else 0
	if is_inside_tree():
		_draw_tabs()


# ---------------------------------------------------------------- bits

func _card() -> PanelContainer:
	var card := PanelContainer.new()
	var st := UITheme.skin_panel("dark")
	card.add_theme_stylebox_override("panel", st)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	card.add_child(v)
	return card


func _muted(text: String) -> Label:
	var l := UIKit.wrapped(text, 22, UITheme.TEXT_MUTED)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return l


## Items from JSON (server or save) carry float numbers.
static func _fix(item: Dictionary) -> void:
	item["level"] = int(item.get("level", 1))
	item["upgrade"] = int(item.get("upgrade", 0))
	if not item.has("affixes"):
		item["affixes"] = []

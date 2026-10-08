class_name MerchantPanel
extends Control
## Madam Pırıl's stall (docs/07): health potions up to the carry cap, and three items
## that change after every run.

signal closed

var _content: VBoxContainer
var _side: VBoxContainer       # left column: Madam Pırıl, the potion stall and the restock note
var _list: VBoxContainer       # right column: this run's items, scrolling
var _npc_line: String = ""


## Landscape: Madam Pırıl and the potions on the left, the three items for sale on the right.
func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("merchant.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	_npc_line = DataDB.t("merchant.line")
	var cols := UIKit.split(_content, 0.38)
	_side = cols[0]
	_list = UIKit.scroll_list(cols[1], 12)
	refresh()


func refresh() -> void:
	for c in _side.get_children():
		c.queue_free()
	for c in _list.get_children():
		c.queue_free()
	var p := GameState.profile
	_side.add_child(UIKit.npc_row("res://assets/town/npc_merchant.png", DataDB.t("merchant.npc"), _npc_line))

	# potions: a tall card under the NPC, its button along the bottom
	var pot := _card()
	_side.add_child(pot)
	var pv := VBoxContainer.new()
	pv.add_theme_constant_override("separation", 10)
	pot.add_child(pv)
	var ph := HBoxContainer.new()
	ph.add_theme_constant_override("separation", 12)
	pv.add_child(ph)
	ph.add_child(UIKit.icon("res://assets/icons/items/potion.png", 88))
	var pt := VBoxContainer.new()
	pt.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pt.alignment = BoxContainer.ALIGNMENT_CENTER
	ph.add_child(pt)
	pt.add_child(UIKit.label(DataDB.t("merchant.potion"), 26, UITheme.TEXT))
	pt.add_child(UIKit.counter("res://assets/icons/items/potion.png", "%d/%d" % [p.potions, Profile.MAX_POTIONS],
			UITheme.TEXT if p.potions < Profile.MAX_POTIONS else UITheme.GOLD, 30))
	pv.add_child(UIKit.wrapped(DataDB.tf("merchant.potion_desc", {"max": Profile.MAX_POTIONS}), 20, UITheme.TEXT_MUTED))
	var buy_pot := _price_button(Profile.POTION_PRICE, func() -> void:
		if p.buy_potion():
			Audio.play("buy")
			GameState.changed()
			refresh())
	buy_pot.disabled = p.gold < Profile.POTION_PRICE or p.potions >= Profile.MAX_POTIONS
	if p.potions >= Profile.MAX_POTIONS:
		buy_pot.text = DataDB.t("merchant.too_many")
		buy_pot.icon = null
	buy_pot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pv.add_child(buy_pot)
	var gap := Control.new()
	gap.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_side.add_child(gap)
	var note := UIKit.wrapped(DataDB.t("merchant.restock"), 20, UITheme.TEXT_MUTED)
	note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_side.add_child(note)

	# items
	for i in p.shop.size():
		var item: Dictionary = p.shop[i]
		var r := _card()
		_list.add_child(r)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 14)
		r.add_child(h)
		var t := ItemUI.tile(item, 100)
		t.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(t)
		var d := ItemUI.details(item, p.equipped(p.slot_of(item)) if p.can_equip(item) else null)
		d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(d)
		var price := Items.shop_price(item, ItemUI.defs())
		var index := i
		var buy := _price_button(price, func() -> void: _buy(index))
		buy.disabled = p.gold < price or p.bag_items().size() >= p.bag_size()
		if p.bag_items().size() >= p.bag_size():
			buy.text = DataDB.t("bag.full")
			buy.icon = null
		h.add_child(buy)
	if p.shop.is_empty():
		var sold := UIKit.label(DataDB.t("merchant.sold_out"), 26, UITheme.TEXT_MUTED)
		sold.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		sold.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		sold.custom_minimum_size.y = 200
		_list.add_child(sold)


func _buy(index: int) -> void:
	var p := GameState.profile
	var item: Dictionary = p.shop[index]
	if not p.buy_shop_item(index):
		return
	Audio.play("buy")
	_npc_line = DataDB.tf("merchant.bought", {"item": ItemUI.item_name(item)})
	GameState.changed()
	refresh()


## A dark card for one thing on sale.
func _card() -> PanelContainer:
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	return card


func _price_button(price: int, on_press: Callable) -> Button:
	var b := UIKit.primary(UIKit.button(str(price), ItemUI.ITEM_GOLD, on_press, 26))
	b.custom_minimum_size = Vector2(140, 76)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return b

class_name MerchantPanel
extends Control
## Madam Pırıl's stall (docs/07): health potions up to the carry cap, and three items
## that change after every run.

signal closed

var _content: VBoxContainer
var _list: VBoxContainer
var _npc_line: String = ""


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("merchant.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	_npc_line = DataDB.t("merchant.line")
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_content.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 12)
	scroll.add_child(_list)
	refresh()


func refresh() -> void:
	for c in _list.get_children():
		c.queue_free()
	var p := GameState.profile
	_list.add_child(UIKit.npc_row("res://assets/town/npc_merchant.png", DataDB.t("merchant.npc"), _npc_line))

	# potions
	var pot := _row()
	var ph: HBoxContainer = pot.get_child(0)
	ph.add_child(UIKit.icon("res://assets/icons/items/potion.png", 96))
	var pv := VBoxContainer.new()
	pv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ph.add_child(pv)
	pv.add_child(UIKit.label("%s  (%d/%d)" % [DataDB.t("merchant.potion"), p.potions, Profile.MAX_POTIONS], 26, UITheme.TEXT))
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
	ph.add_child(buy_pot)

	# items
	for i in p.shop.size():
		var item: Dictionary = p.shop[i]
		var r := _row()
		var h: HBoxContainer = r.get_child(0)
		h.add_child(ItemUI.tile(item, 104))
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
		_list.add_child(sold)
	var note := UIKit.wrapped(DataDB.t("merchant.restock"), 20, UITheme.TEXT_MUTED)
	note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_list.add_child(note)


func _buy(index: int) -> void:
	var p := GameState.profile
	var item: Dictionary = p.shop[index]
	if not p.buy_shop_item(index):
		return
	Audio.play("buy")
	_npc_line = DataDB.tf("merchant.bought", {"item": ItemUI.item_name(item)})
	GameState.changed()
	refresh()


## A wooden row card holding an HBoxContainer.
func _row() -> PanelContainer:
	var card := PanelContainer.new()
	var st := UITheme.skin_panel("dark")
	card.add_theme_stylebox_override("panel", st)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	card.add_child(h)
	_list.add_child(card)
	return card


func _price_button(price: int, on_press: Callable) -> Button:
	var b := UIKit.primary(UIKit.button(str(price), ItemUI.ITEM_GOLD, on_press, 26))
	b.custom_minimum_size = Vector2(140, 76)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return b

class_name SmithPanel
extends Control
## Usta Örs, the smith (docs/05): pick any item, see what the next level does and pay
## gold (and a dragon scale from +6) to upgrade it. Upgrades never fail.

signal closed

const COLUMNS := 5
const TILE := 112

var _content: VBoxContainer
var _npc: HBoxContainer
var _card: PanelContainer
var _grid: GridContainer
var _selected: String = ""


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("smith.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	_npc = UIKit.npc_row("res://assets/town/npc_smith.png", DataDB.t("smith.npc"), DataDB.t("smith.line"))
	_content.add_child(_npc)
	_card = PanelContainer.new()
	var st := UITheme.skin_panel("dark")
	_card.add_theme_stylebox_override("panel", st)
	_card.custom_minimum_size.y = 300
	_content.add_child(_card)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_content.add_child(scroll)
	_grid = GridContainer.new()
	_grid.columns = COLUMNS
	_grid.add_theme_constant_override("h_separation", 10)
	_grid.add_theme_constant_override("v_separation", 10)
	scroll.add_child(_grid)
	# start on the weapon, the upgrade that matters most
	_selected = GameState.profile.equipped("weapon").get("uid", "")
	refresh()


func refresh() -> void:
	var p := GameState.profile
	if p.get_item(_selected).is_empty():
		_selected = ""
	for c in _grid.get_children():
		c.queue_free()
	var items := p.equipped_items()
	var bag := p.bag_items()
	bag.reverse()
	items.append_array(bag)
	for item in items:
		var uid: String = item["uid"]
		var b := ItemUI.tile_button(item, TILE, func() -> void:
			_selected = uid
			refresh(), "", p.is_equipped(uid))
		if uid == _selected:
			b.modulate = Color(1.3, 1.25, 1.0)
		_grid.add_child(b)
	_draw_card()


func _draw_card() -> void:
	for c in _card.get_children():
		c.queue_free()
	var p := GameState.profile
	var item := p.get_item(_selected)
	if item.is_empty():
		var hint := UIKit.wrapped(DataDB.t("smith.pick"), 22, UITheme.TEXT_MUTED)
		hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_card.add_child(hint)
		return
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	_card.add_child(v)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	v.add_child(row)
	row.add_child(ItemUI.tile(item, 110, "", p.is_equipped(_selected)))
	var cost := Items.upgrade_cost(item, ItemUI.defs())
	if cost.is_empty():
		var d := ItemUI.details(item)
		d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(d)
		v.add_child(UIKit.label(DataDB.t("smith.maxed"), 24, UITheme.GOLD))
		return
	# Preview: the item one level up, compared with how it is now.
	var next := item.duplicate(true)
	next["upgrade"] = int(item.get("upgrade", 0)) + 1
	var d := ItemUI.details(next, item)
	d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(d)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 12)
	v.add_child(buttons)
	var price := HBoxContainer.new()
	price.add_theme_constant_override("separation", 10)
	price.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	price.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.add_child(price)
	price.add_child(UIKit.counter(ItemUI.ITEM_GOLD, str(cost["gold"]),
			UITheme.GOLD if p.gold >= cost["gold"] else ItemUI.DOWN, 34))
	if cost["scales"] > 0:
		price.add_child(UIKit.counter("res://assets/icons/items/scale.png", str(cost["scales"]),
				Color("7fd4ff") if p.scales >= cost["scales"] else ItemUI.DOWN, 34))
	var label := DataDB.t("smith.upgrade")
	if p.gold < cost["gold"]:
		label = DataDB.t("smith.need_gold")
	elif p.scales < cost["scales"]:
		label = DataDB.t("smith.need_scales")
	var up := UIKit.primary(UIKit.button(label, "", _upgrade))
	up.disabled = not p.can_upgrade(_selected)
	up.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	up.size_flags_stretch_ratio = 1.4
	buttons.add_child(up)


func _upgrade() -> void:
	var p := GameState.profile
	if not p.upgrade(_selected):
		return
	GameState.changed()
	var item := p.get_item(_selected)
	_content.remove_child(_npc)
	_npc.queue_free()
	_npc = UIKit.npc_row("res://assets/town/npc_smith.png", DataDB.t("smith.npc"),
			DataDB.tf("smith.done", {"item": UITheme.caps(DataDB.t(ItemUI.base_of(item)["name_key"])), "n": item["upgrade"]}))
	_content.add_child(_npc)
	_content.move_child(_npc, 0)
	refresh()
	# a little hammer-strike flash on the card
	_card.modulate = Color(1.8, 1.5, 1.0)
	create_tween().tween_property(_card, "modulate", Color.WHITE, 0.35)

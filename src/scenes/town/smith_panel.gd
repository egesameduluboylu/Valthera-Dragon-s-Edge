class_name SmithPanel
extends Control
## Usta Örs, the smith (docs/05): pick any item, see what the next level does and pay
## gold (and a dragon scale from +6) to upgrade it. Upgrades never fail.

signal closed

const COLUMNS := 4          # grid columns at the narrowest (1280 px) screen; more fit on wider ones
const TILE := 96
const SEP := 10

var _content: VBoxContainer
var _left: VBoxContainer          # NPC row and the item grid; the card fills the right column
var _npc: HBoxContainer
var _card: PanelContainer
var _grid: GridContainer
var _grid_scroll: ScrollContainer
var _selected: String = ""


## Landscape: Usta Örs and every item on the left, the upgrade card on the right.
func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("smith.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	var cols := UIKit.split(_content, 0.5)
	_left = cols[0]
	_npc = UIKit.npc_row("res://assets/town/npc_smith.png", DataDB.t("smith.npc"), DataDB.t("smith.line"))
	_left.add_child(_npc)
	_grid_scroll = ScrollContainer.new()
	_grid_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_grid_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_left.add_child(_grid_scroll)
	_grid = GridContainer.new()
	_grid.columns = COLUMNS
	_grid.add_theme_constant_override("h_separation", SEP)
	_grid.add_theme_constant_override("v_separation", SEP)
	_grid_scroll.add_child(_grid)
	_grid_scroll.resized.connect(_fit_grid)
	_card = PanelContainer.new()
	_card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	_card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cols[1].add_child(_card)
	# start on the weapon, the upgrade that matters most
	_selected = GameState.profile.equipped("weapon").get("uid", "")
	refresh()


## As many grid columns as the left column holds; the spare width goes into the gaps.
func _fit_grid() -> void:
	var w := _grid_scroll.size.x - 14.0
	var cols := clampi(int((w + SEP) / (TILE + SEP)), COLUMNS, 10)
	var gap := clampi(int((w - cols * TILE) / (cols - 1)), SEP, 30)
	if cols != _grid.columns:
		_grid.columns = cols
	_grid.add_theme_constant_override("h_separation", gap)
	_grid.add_theme_constant_override("v_separation", gap)


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
		hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_card.add_child(hint)
		return
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	_card.add_child(v)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(row)
	var t := ItemUI.tile(item, 110, "", p.is_equipped(_selected))
	t.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(t)
	var cost := Items.upgrade_cost(item, ItemUI.defs())
	if cost.is_empty():
		var d := ItemUI.details(item)
		d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(d)
		var maxed := UIKit.label(DataDB.t("smith.maxed"), 26, UITheme.GOLD)
		maxed.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(maxed)
		return
	# Preview: the item one level up, compared with how it is now.
	var next := item.duplicate(true)
	next["upgrade"] = int(item.get("upgrade", 0)) + 1
	var d := ItemUI.details(next, item)
	d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(d)
	# cost over the button, both along the bottom of the card
	v.add_child(UIKit.hsep(2, Color(UITheme.GOLD_DARK, 0.5)))
	var price := HBoxContainer.new()
	price.add_theme_constant_override("separation", 24)
	price.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(price)
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
	v.add_child(up)


func _upgrade() -> void:
	var p := GameState.profile
	if not p.upgrade(_selected):
		return
	Audio.play("upgrade")
	Audio.vibrate(40)
	GameState.changed()
	var item := p.get_item(_selected)
	_left.remove_child(_npc)
	_npc.queue_free()
	_npc = UIKit.npc_row("res://assets/town/npc_smith.png", DataDB.t("smith.npc"),
			DataDB.tf("smith.done", {"item": UITheme.caps(DataDB.t(ItemUI.base_of(item)["name_key"])), "n": item["upgrade"]}))
	_left.add_child(_npc)
	_left.move_child(_npc, 0)
	refresh()
	# a little hammer-strike flash on the card
	_card.modulate = Color(1.8, 1.5, 1.0)
	create_tween().tween_property(_card, "modulate", Color.WHITE, 0.35)

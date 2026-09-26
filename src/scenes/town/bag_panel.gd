class_name BagPanel
extends Control
## Bag and character sheet (docs/08): the four worn slots, the character's stats with
## gear, the bag grid, and a card for the tapped item with equip / salvage.

signal closed

const COLUMNS := 5
const TILE := 112

var _content: VBoxContainer
var _selected: String = ""       # uid of the tapped item
var _stats_box: GridContainer
var _slots_row: HBoxContainer
var _card: PanelContainer
var _grid: GridContainer
var _count: Label


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("bag.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	_build()
	refresh()


func _profile() -> Profile:
	return GameState.profile


func _build() -> void:
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 16)
	_content.add_child(top)
	var portrait := UIKit.icon(DataDB.data["classes"][_profile().active_class].get("sprite", ""), 170)
	top.add_child(portrait)
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 4)
	top.add_child(right)
	right.add_child(UIKit.label("%s  ·  %s" % [DataDB.t("class." + _profile().active_class),
			DataDB.t("ui.level") % _profile().level()], 26, UITheme.GOLD))
	_stats_box = GridContainer.new()
	_stats_box.columns = 4
	_stats_box.add_theme_constant_override("h_separation", 12)
	_stats_box.add_theme_constant_override("v_separation", 2)
	right.add_child(_stats_box)

	_slots_row = HBoxContainer.new()
	_slots_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_slots_row.add_theme_constant_override("separation", 14)
	_content.add_child(_slots_row)

	_card = PanelContainer.new()
	var st := UITheme.skin_panel("dark")
	_card.add_theme_stylebox_override("panel", st)
	_card.custom_minimum_size.y = 250
	_content.add_child(_card)

	var head := HBoxContainer.new()
	_content.add_child(head)
	var t := UIKit.title(DataDB.t("bag.title"), 26)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(t)
	_count = UIKit.label("", 22, UITheme.TEXT_MUTED)
	head.add_child(_count)

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_content.add_child(scroll)
	_grid = GridContainer.new()
	_grid.columns = COLUMNS
	_grid.add_theme_constant_override("h_separation", 10)
	_grid.add_theme_constant_override("v_separation", 10)
	_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_grid)


func refresh() -> void:
	var p := _profile()
	if _selected != "" and p.get_item(_selected).is_empty():
		_selected = ""
	# stats
	for c in _stats_box.get_children():
		c.queue_free()
	var me := p.player()
	var values := {"hp": me.max_hp(), "atk": me.stats.atk, "def": me.stats.def, "spd": me.stats.spd,
			"crit": me.stats.crit, "dodge": me.stats.dodge}
	for stat in ["hp", "atk", "def", "spd", "crit", "dodge"]:
		_stats_box.add_child(UIKit.label(DataDB.t("stat." + stat), 20, UITheme.TEXT_MUTED))
		_stats_box.add_child(UIKit.label(ItemUI.stat_value(stat, float(values[stat])), 22, UITheme.TEXT))
	# worn slots
	for c in _slots_row.get_children():
		c.queue_free()
	for slot in Items.SLOTS:
		var item := p.equipped(slot)
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", 2)
		_slots_row.add_child(v)
		var uid: String = item.get("uid", "")
		var b := ItemUI.tile_button(item, 132, func() -> void: _select(uid), slot)
		if uid != "" and uid == _selected:
			b.modulate = Color(1.25, 1.2, 1.0)
		v.add_child(b)
		var l := UIKit.label(DataDB.t("slot." + slot), 18, UITheme.TEXT_MUTED)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(l)
	# bag grid
	for c in _grid.get_children():
		c.queue_free()
	var items := p.bag_items()
	_count.text = DataDB.tf("bag.count", {"n": items.size(), "max": p.bag_size()})
	# newest first, so fresh loot is at the top
	items.reverse()
	for item in items:
		var uid: String = item["uid"]
		var b := ItemUI.tile_button(item, TILE, func() -> void: _select(uid))
		if uid == _selected:
			b.modulate = Color(1.3, 1.25, 1.0)
		_grid.add_child(b)
	for i in maxi(0, COLUMNS * 2 - items.size()):
		_grid.add_child(ItemUI.tile({}, TILE))
	_draw_card()


func _select(uid: String) -> void:
	_selected = "" if uid == _selected else uid
	refresh()


func _draw_card() -> void:
	for c in _card.get_children():
		c.queue_free()
	var p := _profile()
	var item := p.get_item(_selected)
	if item.is_empty():
		var hint := UIKit.wrapped(DataDB.t("bag.empty") if p.inventory.is_empty() else DataDB.t("smith.pick"), 22,
				UITheme.TEXT_MUTED)
		hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_card.add_child(hint)
		return
	var worn := p.is_equipped(_selected)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	_card.add_child(v)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	v.add_child(row)
	row.add_child(ItemUI.tile(item, 110))
	var compare: Variant = null if worn else p.equipped(p.slot_of(item))
	var d := ItemUI.details(item, compare)
	d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(d)
	if compare != null:
		var cap := UIKit.label(DataDB.t("bag.compare"), 18, UITheme.TEXT_MUTED)
		cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		d.add_child(cap)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 12)
	v.add_child(buttons)
	if worn:
		var off := UIKit.button(DataDB.t("bag.unequip"), "", func() -> void:
			if p.unequip(p.slot_of(item)):
				GameState.changed()
			refresh())
		off.disabled = p.bag_items().size() >= p.bag_size()
		off.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		buttons.add_child(off)
	else:
		var why := p.equip_block_reason(item)
		var label := DataDB.t("bag.equip")
		if why == "class":
			label = DataDB.t("bag.wrong_class")
		elif why == "level":
			label = DataDB.tf("bag.low_level", {"n": Items.wear_level(item, ItemUI.defs())})
		var on := UIKit.primary(UIKit.button(label, "",
				func() -> void:
					if p.equip(_selected):
						GameState.changed()
					refresh()))
		on.disabled = not p.can_equip(item)
		on.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		buttons.add_child(on)
		var sal := UIKit.button(DataDB.t("bag.salvage"), ItemUI.ITEM_GOLD, func() -> void: _confirm_salvage(item))
		sal.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		buttons.add_child(sal)


func _confirm_salvage(item: Dictionary) -> void:
	var v := Items.salvage_value(item, ItemUI.defs())
	var scales := DataDB.tf("bag.salvage_scales", {"n": v["scales"]}) if v["scales"] > 0 else ""
	var parts := UIKit.dialog(DataDB.t("bag.salvage"),
			DataDB.tf("bag.salvage_confirm", {"item": ItemUI.item_name(item), "gold": v["gold"], "scales": scales}))
	add_child(parts[0])
	var body: VBoxContainer = parts[1]
	body.add_child(ItemUI.tile(item, 96))
	body.get_child(0).size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	body.add_child(row)
	var no := UIKit.button(DataDB.t("ui.cancel"), "", func() -> void: parts[0].queue_free())
	no.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(no)
	var yes := UIKit.primary(UIKit.button(DataDB.t("bag.salvage"), ItemUI.ITEM_GOLD, func() -> void:
		if not GameState.profile.salvage(item["uid"]).is_empty():
			GameState.changed()
		parts[0].queue_free()
		refresh()))
	yes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(yes)

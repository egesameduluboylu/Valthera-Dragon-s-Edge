class_name BagPanel
extends Control
## Bag and character sheet (docs/08): the four worn slots, the character's stats with
## gear, the bag grid, and a card for the tapped item with equip / salvage.

signal closed

const COLUMNS := 4          # bag grid columns at the narrowest (1280 px) screen; more fit on wider ones
const TILE := 88
const SLOT_TILE := 92
const SEP := 8

var _content: VBoxContainer
var _selected: String = ""       # uid of the tapped item
var _stats_box: GridContainer
var _slots_row: HBoxContainer    # the paper doll: [weapon, armour] portrait [helm, accessory]
var _slot_cols: Array = []
var _card: PanelContainer
var _grid: GridContainer
var _grid_scroll: ScrollContainer
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


## Landscape: three columns. Character (paper doll + stats) | bag grid | tapped item card.
func _build() -> void:
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 18)
	_content.add_child(row)

	# character column
	var hero := VBoxContainer.new()
	hero.add_theme_constant_override("separation", 8)
	row.add_child(hero)
	hero.add_child(_column_head(DataDB.t("bag.stats"), null))
	var doll := PanelContainer.new()
	doll.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	doll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hero.add_child(doll)
	var dv := VBoxContainer.new()
	dv.add_theme_constant_override("separation", 4)
	doll.add_child(dv)
	var who := UIKit.label("%s  ·  %s" % [DataDB.t("class." + _profile().active_class),
			DataDB.t("ui.level") % _profile().level()], 24, UITheme.GOLD)
	who.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	dv.add_child(who)
	_slots_row = HBoxContainer.new()
	_slots_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_slots_row.add_theme_constant_override("separation", 6)
	_slots_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	dv.add_child(_slots_row)
	_slot_cols.clear()
	for i in 2:
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 10)
		col.alignment = BoxContainer.ALIGNMENT_CENTER
		_slot_cols.append(col)
	_slots_row.add_child(_slot_cols[0])
	var portrait := UIKit.icon(DataDB.data["classes"][_profile().active_class].get("sprite", ""), 0)
	portrait.custom_minimum_size = Vector2(150, 0)
	portrait.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_slots_row.add_child(portrait)
	_slots_row.add_child(_slot_cols[1])
	_stats_box = GridContainer.new()
	_stats_box.columns = 4
	_stats_box.add_theme_constant_override("h_separation", 16)
	_stats_box.add_theme_constant_override("v_separation", 2)
	_stats_box.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	dv.add_child(_stats_box)

	# bag column
	var bag := VBoxContainer.new()
	bag.add_theme_constant_override("separation", 8)
	bag.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bag.size_flags_stretch_ratio = 1.0
	row.add_child(bag)
	_count = UIKit.label("", 22, UITheme.TEXT_MUTED)
	bag.add_child(_column_head(DataDB.t("bag.title"), _count))
	_grid_scroll = ScrollContainer.new()
	_grid_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_grid_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	bag.add_child(_grid_scroll)
	_grid = GridContainer.new()
	_grid.columns = COLUMNS
	_grid.add_theme_constant_override("h_separation", SEP)
	_grid.add_theme_constant_override("v_separation", SEP)
	_grid_scroll.add_child(_grid)
	_grid_scroll.custom_minimum_size.x = COLUMNS * (TILE + SEP) + 12
	_grid_scroll.resized.connect(_fit_grid)

	# item card column
	_card = PanelContainer.new()
	_card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_card.size_flags_stretch_ratio = 0.85
	_card.custom_minimum_size.x = 380
	row.add_child(_card)


## A small gold caption over a column, with an optional note on the right.
func _column_head(text: String, note: Control) -> HBoxContainer:
	var head := HBoxContainer.new()
	var t := UIKit.title(text, 24)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(t)
	if note != null:
		head.add_child(note)
	return head


## As many grid columns as the bag column holds (wider phones show more per row); the
## spare width goes into the gaps so the grid spans the column.
func _fit_grid() -> void:
	var w := _grid_scroll.size.x - 14.0
	var cols := clampi(int((w + SEP) / (TILE + SEP)), COLUMNS, 10)
	var gap := clampi(int((w - cols * TILE) / (cols - 1)), SEP, 20)
	if cols != _grid.columns:
		_grid.columns = cols
	_grid.add_theme_constant_override("h_separation", gap)
	_grid.add_theme_constant_override("v_separation", gap)


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
	# worn slots, two on each side of the portrait
	for col in _slot_cols:
		for c in col.get_children():
			c.queue_free()
	var i := 0
	for slot in Items.SLOTS:
		var item := p.equipped(slot)
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", 0)
		_slot_cols[0 if i < 2 else 1].add_child(v)
		i += 1
		var uid: String = item.get("uid", "")
		var b := ItemUI.tile_button(item, SLOT_TILE, func() -> void: _select(uid), slot)
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
	# empty frames up to the bag's size, so the free room is visible
	for n in maxi(0, p.bag_size() - items.size()):
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
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(row)
	var t := ItemUI.tile(item, 96)
	t.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(t)
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
						Audio.play("equip")
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
			Audio.play("salvage")
			GameState.changed()
		parts[0].queue_free()
		refresh()))
	yes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(yes)

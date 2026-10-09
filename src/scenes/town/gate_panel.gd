class_name GatePanel
extends Control
## Bekçi Tozlu at the Dungeon Gate (docs/08): every dungeon with its level range, stars
## and runs. Each opens once the one before it is cleared; three stars open Hard mode.

signal closed
signal enter(dungeon_id: String, hard: bool)

const ART := "res://assets/town/%s.png"
const POTION_ICON := "res://assets/icons/items/potion.png"

var _list: VBoxContainer


## Landscape: the keeper, the potion count and the Hard-mode rule on the left; every
## dungeon as one wide row on the right, scrolled to the one the keeper points at.
func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("town.gate.title"), func() -> void: closed.emit())
	add_child(parts[0])
	var content: VBoxContainer = parts[1]
	var cols := UIKit.split(content, 0.36)
	var side: VBoxContainer = cols[0]
	side.add_child(UIKit.npc_row(ART % "npc_keeper", DataDB.t("town.gate.keeper"), _keeper_line()))
	var info := PanelContainer.new()
	info.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	side.add_child(info)
	var iv := VBoxContainer.new()
	iv.add_theme_constant_override("separation", 10)
	info.add_child(iv)
	iv.add_child(UIKit.counter(POTION_ICON, DataDB.tf("town.gate.potions", {"n": GameState.profile.potions}),
			UITheme.TEXT, 30))
	# the Hard-mode rule, once for all dungeons (each card shows only its own stars)
	iv.add_child(UIKit.hsep(2, Color(UITheme.GOLD_DARK, 0.5)))
	var hard_head := HBoxContainer.new()
	hard_head.add_theme_constant_override("separation", 8)
	iv.add_child(hard_head)
	hard_head.add_child(UIKit.icon("res://assets/icons/rooms/elite.png", 34))
	hard_head.add_child(UIKit.title(DataDB.t("town.gate.hard"), 24))
	iv.add_child(UIKit.wrapped(DataDB.t("town.gate.hard_hint"), 20, UITheme.TEXT_MUTED))
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	cols[1].add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 10)
	scroll.add_child(_list)
	var focus: Control = null
	var p := GameState.profile
	for id in DataDB.data["dungeons"]:
		var card := _card(id)
		_list.add_child(card)
		if focus == null and p.dungeon_unlocked(id) and not p.dungeon_cleared(id):
			focus = card
	if focus != null:
		(func() -> void:
			await get_tree().process_frame
			if is_instance_valid(focus):
				scroll.ensure_control_visible(focus)).call_deferred()


## The keeper points at the newest dungeon the player hasn't cleared yet.
func _keeper_line() -> String:
	var p := GameState.profile
	for id in DataDB.data["dungeons"]:
		if p.dungeon_unlocked(id) and not p.dungeon_cleared(id):
			return DataDB.t("town.gate.line." + id)
	return DataDB.t("town.gate.line.done")


## One dungeon as a row: thumbnail | name, levels, stars, runs | Enter and Hard buttons.
func _card(id: String) -> PanelContainer:
	var p := GameState.profile
	var d: Dictionary = DataDB.data["dungeons"][id]
	var unlocked := p.dungeon_unlocked(id)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	card.add_child(row)
	var thumb := UIKit.icon(d.get("background", ""), 0)
	thumb.custom_minimum_size = Vector2(124, 124)
	thumb.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	thumb.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if not unlocked:
		thumb.modulate = Color(0.3, 0.28, 0.3)
	row.add_child(thumb)
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.alignment = BoxContainer.ALIGNMENT_CENTER
	info.add_theme_constant_override("separation", 2)
	row.add_child(info)
	info.add_child(UIKit.title(DataDB.t(d["name_key"]), 26, UITheme.GOLD if unlocked else UITheme.TEXT_MUTED))
	info.add_child(UIKit.label(DataDB.tf("town.gate.levels", {"a": int(d["level_min"]), "b": int(d["level_max"])}),
			21, UITheme.TEXT))
	if not unlocked:
		var need: String = d.get("unlock_after", "")
		info.add_child(UIKit.wrapped(DataDB.tf("town.gate.locked",
				{"dungeon": DataDB.t(DataDB.data["dungeons"][need]["name_key"])}), 19, UITheme.TEXT_MUTED))
		return card
	var stats: Dictionary = p.dungeons.get(id, {})
	info.add_child(_stars_row(p.dungeon_stars(id)))
	var runs_text := DataDB.tf("town.gate.runs", {"n": stats.get("runs", 0)})
	if stats.get("hard_cleared", false):
		runs_text += "  ·  " + DataDB.t("town.gate.hard_cleared")
	info.add_child(UIKit.label(runs_text, 19, UITheme.TEXT_MUTED))
	var buttons := VBoxContainer.new()
	buttons.add_theme_constant_override("separation", 8)
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.custom_minimum_size.x = 250
	row.add_child(buttons)
	var go := UIKit.primary(UIKit.button(DataDB.t("town.gate.enter"), "res://assets/icons/rooms/combat.png",
			func() -> void: enter.emit(id, false), 24))
	go.custom_minimum_size.y = 68
	buttons.add_child(go)
	if p.hard_unlocked(id):
		var hard := UIKit.button(DataDB.t("town.gate.hard"), "res://assets/icons/rooms/elite.png",
				func() -> void: enter.emit(id, true), 24)
		hard.custom_minimum_size.y = 64
		buttons.add_child(hard)
	return card


func _stars_row(stars: Array) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 6)
	for i in stars.size():
		var s := UIKit.label("★" if stars[i] else "☆", 26, UITheme.GOLD if stars[i] else UITheme.TEXT_MUTED)
		s.tooltip_text = DataDB.t("town.gate.star%d" % (i + 1))
		s.mouse_filter = Control.MOUSE_FILTER_PASS
		h.add_child(s)
	return h

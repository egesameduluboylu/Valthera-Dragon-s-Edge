class_name DragonPanel
extends Control
## Nara's nest (docs/15): put the dragon egg in the nest, watch it warm up over runs,
## hatch it and pick its blood, then follow the companion as it grows.

signal closed

const NEST := "res://assets/sprites/companion/egg_nest.png"
const NEST_CRACKED := "res://assets/sprites/companion/egg_nest_cracked.png"
const NARA := "res://assets/town/npc_nara.png"

var _content: VBoxContainer
## Left column under Nara: the nest, the egg or the dragon, as large as fits.
var _stage: VBoxContainer
## Right column card: the words and the buttons.
var _body: VBoxContainer


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("dragon.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	refresh()


func refresh() -> void:
	for c in _content.get_children():
		c.queue_free()
	var p := GameState.profile
	var state: Dictionary = p.companion
	var line_key := "dragon.nara.can_nest"
	if state.get("state", "") == "egg":
		line_key = "dragon.nara.ready" if p.egg_ready() else "dragon.nara.egg"
	elif Companion.is_hatched(state):
		line_key = "dragon.nara.hatched"
	# landscape: Nara and the nest on the left, the details and actions on the right
	var cols := UIKit.split(_content, 0.44)
	_stage = cols[0]
	_stage.add_child(UIKit.npc_row(NARA, DataDB.t("npc.nara"),
			DataDB.tf(line_key, {"name": DataDB.dragon_name(state)})))
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cols[1].add_child(card)
	_body = VBoxContainer.new()
	_body.add_theme_constant_override("separation", 12)
	card.add_child(_body)
	if Companion.is_hatched(state):
		_show_dragon(state)
	elif state.get("state", "") == "egg":
		_show_egg(p)
	else:
		_show_nest_offer()


## Art in the left column: it takes the height left under Nara's line.
func _art(path: String, height: int) -> TextureRect:
	# a plain holder, so the bob and wobble tweens are not undone by the column's layout
	var holder := Control.new()
	holder.custom_minimum_size = Vector2(0, height)
	holder.size_flags_vertical = Control.SIZE_EXPAND_FILL
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(holder)
	var art := UIKit.icon(path, 0)
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.add_child(art)
	return art


func _centered(text: String, font_size: int, color: Color = UITheme.TEXT) -> Label:
	var l := UIKit.wrapped(text, font_size, color)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return l


# ---------------------------------------------------------------- egg

func _show_nest_offer() -> void:
	_art(NEST, 260)
	_body.alignment = BoxContainer.ALIGNMENT_CENTER
	_body.add_child(_centered(DataDB.t("item.dragon_egg.desc"), 24, UITheme.TEXT_MUTED))
	_body.add_child(UIKit.spacer(12))
	var b := UIKit.primary(UIKit.button(DataDB.t("dragon.nest.button"), "", _confirm_nest, 28))
	_body.add_child(b)


func _confirm_nest() -> void:
	var parts := UIKit.dialog(DataDB.t("dragon.nest.button"), DataDB.t("dragon.nest.confirm"), NEST)
	add_child(parts[0])
	var body: VBoxContainer = parts[1]
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	body.add_child(row)
	var no := UIKit.button(DataDB.t("ui.cancel"), "", func() -> void: parts[0].queue_free())
	no.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(no)
	var yes := UIKit.primary(UIKit.button(DataDB.t("dragon.nest.yes"), "", func() -> void:
		parts[0].queue_free()
		if GameState.profile.nest_egg():
			Audio.play("equip")
			GameState.changed()
		refresh()))
	yes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(yes)


func _show_egg(p: Profile) -> void:
	var ready := p.egg_ready()
	var art := _art(NEST_CRACKED if ready else NEST, 260)
	_body.alignment = BoxContainer.ALIGNMENT_CENTER
	var need := int(DataDB.data["companion"]["hatch_runs"])
	var warmth := int(p.companion["warmth"])
	_body.add_child(_warmth_row(warmth, need))
	_body.add_child(_centered(DataDB.tf("dragon.warmth", {"n": warmth, "max": need}), 26, UITheme.GOLD))
	if not ready:
		_body.add_child(_centered(DataDB.t("dragon.warmth_hint"), 22, UITheme.TEXT_MUTED))
		return
	_body.add_child(UIKit.spacer(12))
	# the egg wobbles while it waits
	art.resized.connect(func() -> void: art.pivot_offset = Vector2(art.size.x * 0.5, art.size.y))
	var tw := art.create_tween().set_loops()
	tw.tween_property(art, "rotation", 0.04, 0.12)
	tw.tween_property(art, "rotation", -0.04, 0.12)
	tw.tween_property(art, "rotation", 0.0, 0.1)
	tw.tween_interval(0.9)
	_body.add_child(UIKit.primary(UIKit.button(DataDB.t("dragon.hatch.button"), "", _hatch_scene, 30)))


func _warmth_row(warmth: int, need: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 14)
	for i in need:
		var pip := Panel.new()
		pip.custom_minimum_size = Vector2(40, 40)
		var st := StyleBoxFlat.new()
		st.set_corner_radius_all(20)
		st.set_border_width_all(4)
		st.border_color = UITheme.GOLD_DARK
		st.bg_color = Color("ff9a3c") if i < warmth else Color(0.12, 0.09, 0.1)
		if i < warmth:
			st.shadow_color = Color(1.0, 0.55, 0.2, 0.6)
			st.shadow_size = 8
		pip.add_theme_stylebox_override("panel", st)
		row.add_child(pip)
	return row


func _hatch_scene() -> void:
	if StoryDialog.has_scene("dragon_hatch"):
		GameState.profile.take_story("dragon_hatch")
		var dlg := StoryDialog.new("dragon_hatch")
		add_child(dlg)
		await dlg.finished
	_choose_element()


func _choose_element() -> void:
	for c in _body.get_children():
		c.queue_free()
	_body.alignment = BoxContainer.ALIGNMENT_BEGIN
	var defs: Dictionary = DataDB.data["companion"]
	_body.add_child(UIKit.title(DataDB.t("dragon.choose.title"), 30))
	_body.add_child(UIKit.wrapped(DataDB.t("dragon.choose.text"), 20, UITheme.TEXT_MUTED))
	var list := UIKit.scroll_list(_body)
	for id in defs["elements"]:
		var el: Dictionary = defs["elements"][id]
		var row := PanelContainer.new()
		row.add_theme_stylebox_override("panel", UITheme.skin_panel("parchment"))
		list.add_child(row)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		row.add_child(h)
		h.add_child(UIKit.icon(Companion.SPRITE % [id, "hatchling"], 88))
		var v := VBoxContainer.new()
		v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		v.alignment = BoxContainer.ALIGNMENT_CENTER
		h.add_child(v)
		# the blood with the dragon's name beside it, the breath effect under them
		var top := HBoxContainer.new()
		top.add_theme_constant_override("separation", 10)
		v.add_child(top)
		top.add_child(UIKit.label(DataDB.t(el["name_key"]), 26, Color(el["color"]).darkened(0.45)))
		var dname := UIKit.label("·  " + DataDB.t(el["default_name_key"]), 22, Color("7a3a1a"))
		dname.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		top.add_child(dname)
		v.add_child(UIKit.wrapped(DataDB.t("dragon.effect." + id), 20, UITheme.INK))
		var pick := UIKit.primary(UIKit.button(DataDB.t("dragon.choose.pick"), "", func() -> void: _hatch(id), 22))
		pick.custom_minimum_size = Vector2(150, 64)
		pick.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(pick)


func _hatch(element: String) -> void:
	if not GameState.profile.hatch(element):
		return
	GameState.changed()
	Audio.play("level_up", 0.0)
	Audio.vibrate(120)
	refresh()
	_toast(DataDB.tf("dragon.hatched", {"name": DataDB.dragon_name(GameState.profile.companion)}))


func _toast(text: String) -> void:
	var l := UITheme.stage_label(UIKit.label(text, 40, UITheme.COMBO), 40, UITheme.COMBO)
	add_child(l)
	l.reset_size()
	l.position = Vector2((size.x - l.size.x) * 0.5, 180)
	var tw := l.create_tween()
	tw.tween_property(l, "position:y", 140.0, 1.4)
	tw.parallel().tween_property(l, "modulate:a", 0.0, 0.5).set_delay(1.2)
	tw.tween_callback(l.queue_free)


# ---------------------------------------------------------------- hatched

func _show_dragon(state: Dictionary) -> void:
	var defs: Dictionary = DataDB.data["companion"]
	var level := int(state["level"])
	var element: String = state["element"]
	var el: Dictionary = defs["elements"][element]
	var stage := Companion.stage(defs, level)
	var art := _art(Companion.sprite(element, level, defs), 260)
	_body.alignment = BoxContainer.ALIGNMENT_CENTER
	var bob := art.create_tween().set_loops()
	bob.tween_property(art, "position:y", -8.0, 1.0).as_relative().set_trans(Tween.TRANS_SINE)
	bob.tween_property(art, "position:y", 8.0, 1.0).as_relative().set_trans(Tween.TRANS_SINE)
	var name_ := UIKit.title(DataDB.dragon_name(state), 36)
	name_.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_body.add_child(name_)
	_body.add_child(_centered("%s  ·  %s" % [DataDB.t(el["name_key"]),
			DataDB.tf("dragon.level", {"n": level, "stage": DataDB.t("dragon.stage." + stage["id"])})], 24,
			Color(el["color"])))
	var xp := ProgressBar.new()
	xp.show_percentage = false
	xp.custom_minimum_size.y = 16
	xp.add_theme_stylebox_override("fill", UITheme.skin_bar_fill("xp"))
	xp.max_value = maxi(1, Progression.xp_to_next(level))
	xp.value = int(state["xp"]) if level < Progression.MAX_LEVEL else xp.max_value
	_body.add_child(xp)
	_body.add_child(UITheme.divider())
	var facts := [
		DataDB.tf("dragon.breath", {"dmg": Companion.breath_estimate(defs, level)}),
		DataDB.tf("dragon.charge", {"n": int(defs["charge_needed"])}),
		DataDB.t("dragon.effect." + element),
		DataDB.tf("dragon.chance", {"n": roundi(float(stage["status_chance"]) * 100)}),
	]
	for f in facts:
		_body.add_child(UIKit.wrapped("•  " + f, 22))
	var next := _next_stage(defs, level)
	var growth := DataDB.t("dragon.max_stage") if next.is_empty() else DataDB.tf("dragon.next_stage",
			{"n": int(next["from"]), "stage": DataDB.t("dragon.stage." + next["id"])})
	_body.add_child(UIKit.wrapped(growth + "  " + DataDB.t("dragon.xp_hint"), 20, UITheme.TEXT_MUTED))


func _next_stage(defs: Dictionary, level: int) -> Dictionary:
	for s in defs["stages"]:
		if int(s["from"]) > level:
			return s
	return {}

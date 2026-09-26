class_name Tutorial
extends Control
## One coach hint (docs/09): dims the screen except a gold frame around `target`, and Nara
## explains it in a small bubble. A tap anywhere closes it. Each hint shows once; the flags
## live in Profile.story_seen, so "Replay tutorial" in settings only has to erase them.

signal finished

## Every hint id, in the order they usually appear.
const FLAGS := ["tut_intent", "tut_skills", "tut_class_warrior", "tut_class_mage", "tut_class_rogue",
		"tut_combo", "tut_defend"]
const PORTRAIT := "res://assets/town/npc_nara.png"
const PAD := 10.0

var _id: String
var _target: Control
var _frame: Panel
var _done: bool = false


func _init(hint_id: String, target: Control) -> void:
	_id = hint_id
	_target = target


## Marks every hint as seen, e.g. when the player taps "Skip tutorial".
static func skip_all(p: Profile) -> void:
	for id in FLAGS:
		p.take_story(id)


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var hole := Rect2(_target.get_global_rect()).grow(PAD) if _target != null else Rect2()
	# four dark strips around the hole, so the target stays bright
	var view := Rect2(Vector2.ZERO, Vector2(720, 1280))
	for r in _around(view, hole):
		var dim := ColorRect.new()
		dim.color = Color(0, 0, 0, 0.62)
		dim.position = r.position
		dim.size = r.size
		dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(dim)
	if hole.has_area():
		_frame = Panel.new()
		var st := StyleBoxFlat.new()
		st.bg_color = Color(0, 0, 0, 0)
		st.border_color = UITheme.COMBO
		st.set_border_width_all(5)
		st.set_corner_radius_all(18)
		st.shadow_color = Color(UITheme.COMBO, 0.55)
		st.shadow_size = 14
		_frame.add_theme_stylebox_override("panel", st)
		_frame.position = hole.position
		_frame.size = hole.size
		_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_frame)
		var tw := create_tween().set_loops()
		tw.tween_property(_frame, "modulate:a", 0.45, 0.55).set_trans(Tween.TRANS_SINE)
		tw.tween_property(_frame, "modulate:a", 1.0, 0.55).set_trans(Tween.TRANS_SINE)
	_build_bubble(hole)
	modulate.a = 0.0
	create_tween().tween_property(self, "modulate:a", 1.0, 0.2)


func _build_bubble(hole: Rect2) -> void:
	var box := PanelContainer.new()
	box.add_theme_stylebox_override("panel", UITheme.skin_panel("parchment"))
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	box.add_child(h)
	if ResourceLoader.exists(PORTRAIT):
		var face := UIKit.icon(PORTRAIT, 120)
		face.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		h.add_child(face)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 6)
	h.add_child(v)
	v.add_child(UIKit.label(DataDB.t("npc.nara"), 26, Color("7a3a1a")))
	var text := UIKit.wrapped(DataDB.t("tut." + _id.trim_prefix("tut_")), 24, UITheme.INK)
	text.custom_minimum_size.x = 480
	v.add_child(text)
	var bottom := HBoxContainer.new()
	v.add_child(bottom)
	var skip := UIKit.button(DataDB.t("tut.skip"), "", func() -> void:
		Tutorial.skip_all(GameState.profile)
		GameState.changed()
		_close(), 18)
	skip.custom_minimum_size = Vector2(0, 48)
	bottom.add_child(skip)
	var hint := UIKit.label(DataDB.t("tut.next") + "  ▸", 20, Color("7a5a3a"))
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bottom.add_child(hint)
	box.size = Vector2(688, 0)
	box.position.x = 16
	_place.call_deferred(box, hole)


## Puts the bubble on the far side of the hole, so it never covers the target.
## Deferred, because the wrapped text only knows its height after a layout pass.
func _place(box: Control, hole: Rect2) -> void:
	var h := box.get_combined_minimum_size().y
	box.size.y = h
	if hole.has_area() and hole.get_center().y > 640:
		box.position.y = maxf(20.0, hole.position.y - 30 - h)
	else:
		box.position.y = minf(1280.0 - 20 - h, (hole.end.y + 30) if hole.has_area() else 400.0)


func _around(view: Rect2, hole: Rect2) -> Array[Rect2]:
	if not hole.has_area():
		return [view]
	hole = hole.intersection(view)
	return [
		Rect2(0, 0, view.size.x, hole.position.y),
		Rect2(0, hole.end.y, view.size.x, view.size.y - hole.end.y),
		Rect2(0, hole.position.y, hole.position.x, hole.size.y),
		Rect2(hole.end.x, hole.position.y, view.size.x - hole.end.x, hole.size.y),
	]


func _gui_input(event: InputEvent) -> void:
	var pressed: bool = (event is InputEventMouseButton and event.pressed) \
			or (event is InputEventScreenTouch and event.pressed)
	if pressed:
		accept_event()
		_close()


func _close() -> void:
	if _done:
		return
	_done = true
	Audio.play("ui_click")
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.15)
	tw.tween_callback(func() -> void:
		finished.emit()
		queue_free())

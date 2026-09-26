class_name StoryDialog
extends Control
## A short story scene (docs/07): a portrait, a name and a speech bubble at the bottom
## of the screen, one line per tap. Emits `finished` after the last line or on Skip.

signal finished

var _lines: Array = []
var _index: int = -1
var _scene_id: String = ""
var _portrait: TextureRect
var _name: Label
var _text: Label


## True when story.json has this scene.
static func has_scene(scene_id: String) -> bool:
	return DataDB.data.get("story", {}).get("scenes", {}).has(scene_id)


func _init(scene_id: String = "") -> void:
	_scene_id = scene_id
	_lines = DataDB.data.get("story", {}).get("scenes", {}).get(scene_id, [])


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dim)
	_portrait = TextureRect.new()
	_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_portrait.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_portrait.position = Vector2(10, 1280 - 690)
	_portrait.size = Vector2(360, 360)
	_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_portrait)
	var box := PanelContainer.new()
	box.add_theme_stylebox_override("panel", UITheme.skin_panel("parchment"))
	box.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	box.offset_left = 16
	box.offset_right = -16
	box.offset_top = -350
	box.offset_bottom = -40
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	box.add_child(v)
	_name = UIKit.label("", 28, Color("7a3a1a"))
	v.add_child(_name)
	_text = UIKit.wrapped("", 26, UITheme.INK)
	_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(_text)
	var hint := UIKit.label(DataDB.t("story.continue") + "  ▸", 20, Color("7a5a3a"))
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	v.add_child(hint)
	var skip := UIKit.button(DataDB.t("story.skip"), "", func() -> void: _end(), 22)
	skip.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	skip.position = Vector2(720 - 150, 30)
	skip.size = Vector2(130, 60)
	add_child(skip)
	_advance()


func _gui_input(event: InputEvent) -> void:
	var pressed: bool = (event is InputEventMouseButton and event.pressed) \
			or (event is InputEventScreenTouch and event.pressed)
	if pressed:
		accept_event()
		_advance()


func _advance() -> void:
	_index += 1
	if _index >= _lines.size():
		_end()
		return
	var speaker: String = _lines[_index][0]
	var n := int(_lines[_index][1])
	var sp: Dictionary = DataDB.data["story"]["speakers"].get(speaker, {})
	_name.text = DataDB.t(sp.get("name_key", speaker))
	_text.text = DataDB.t(StoryText.line_key(_scene_id, speaker, n))
	var path: String = sp.get("portrait", "")
	_portrait.texture = load(path) if ResourceLoader.exists(path) else null
	# enemies face left in their sprites; flip them so everyone looks at the bubble
	_portrait.flip_h = speaker not in ["nara", "keeper", "kaan"]
	_text.visible_ratio = 0.0
	create_tween().tween_property(_text, "visible_ratio", 1.0, 0.35)


func _end() -> void:
	if _index == 99999:
		return
	_index = 99999
	finished.emit()
	queue_free()

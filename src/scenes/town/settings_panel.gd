class_name SettingsPanel
extends Control
## Settings (docs/09): music and sound volume, vibration, replaying the tutorial and
## wiping the save. Sound settings live in Audio's own file, so a reset keeps them.

signal closed
## Emitted after the save was wiped; the town reloads itself.
signal reset_done

const VERSION := "0.5"


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("settings.title"), func() -> void: closed.emit())
	add_child(parts[0])
	var content: VBoxContainer = parts[1]
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	content.add_child(card)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 18)
	card.add_child(v)
	v.add_child(_slider_row("settings.music", Audio.music_volume, Audio.set_music_volume))
	v.add_child(_slider_row("settings.sfx", Audio.sfx_volume, func(x: float) -> void:
		Audio.set_sfx_volume(x)
		Audio.play("ui_click", 0.0)))
	v.add_child(_toggle_row())
	content.add_child(UITheme.divider())
	var tut := UIKit.button(DataDB.t("settings.tutorial"), "", _replay_tutorial, 24)
	content.add_child(tut)
	var reset := UIKit.button(DataDB.t("settings.reset"), "", _confirm_reset, 24)
	reset.add_theme_color_override("font_color", Color("ff9a8a"))
	content.add_child(reset)
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(spacer)
	var ver := UIKit.label(DataDB.tf("settings.version", {"v": VERSION}), 18, UITheme.TEXT_MUTED)
	ver.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	content.add_child(ver)


func _slider_row(key: String, value: float, on_change: Callable) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	var head := HBoxContainer.new()
	v.add_child(head)
	var name_ := UIKit.label(DataDB.t(key), 26)
	name_.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(name_)
	var pct := UIKit.label("%d%%" % roundi(value * 100), 24, UITheme.GOLD)
	head.add_child(pct)
	var s := HSlider.new()
	s.min_value = 0.0
	s.max_value = 1.0
	s.step = 0.05
	s.value = value
	s.custom_minimum_size.y = 52
	var track := UITheme.skin_bar_bg()
	track.content_margin_top = 10
	track.content_margin_bottom = 10
	s.add_theme_stylebox_override("slider", track)
	s.add_theme_stylebox_override("grabber_area", UITheme.skin_bar_fill("gold"))
	s.add_theme_stylebox_override("grabber_area_highlight", UITheme.skin_bar_fill("gold"))
	var knob: Texture2D = load(UITheme.SKIN_PATH % "knob")
	s.add_theme_icon_override("grabber", knob)
	s.add_theme_icon_override("grabber_highlight", knob)
	# only save once the finger lifts; the label follows the drag
	s.value_changed.connect(func(x: float) -> void: pct.text = "%d%%" % roundi(x * 100))
	s.drag_ended.connect(func(_changed: bool) -> void: on_change.call(s.value))
	s.gui_input.connect(func(e: InputEvent) -> void:
		# a tap on the track (no drag) should still apply
		if e is InputEventMouseButton and not e.pressed:
			on_change.call(s.value))
	v.add_child(s)
	return v


func _toggle_row() -> HBoxContainer:
	var h := HBoxContainer.new()
	var name_ := UIKit.label(DataDB.t("settings.vibration"), 26)
	name_.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(name_)
	var b := UIKit.button("", "", func() -> void: pass, 22)
	b.toggle_mode = true
	b.button_pressed = Audio.vibration
	b.custom_minimum_size = Vector2(150, 60)
	var paint := func() -> void:
		b.text = DataDB.t("settings.on" if b.button_pressed else "settings.off")
		if b.button_pressed:
			UIKit.primary(b)
		else:
			for st in ["normal", "hover", "pressed", "hover_pressed"]:
				b.add_theme_stylebox_override(st, UITheme.skin_button("normal" if st != "pressed" else "pressed"))
	paint.call()
	b.toggled.connect(func(on: bool) -> void:
		Audio.set_vibration(on)
		paint.call()
		Audio.vibrate(60))
	h.add_child(b)
	return h


func _replay_tutorial() -> void:
	var p := GameState.profile
	for id in Tutorial.FLAGS:
		p.story_seen.erase(id)
	GameState.changed()
	var parts := UIKit.dialog(DataDB.t("settings.tutorial"), DataDB.t("settings.tutorial_done"))
	add_child(parts[0])
	var body: VBoxContainer = parts[1]
	body.add_child(UIKit.primary(UIKit.button(DataDB.t("ui.continue"), "", func() -> void: parts[0].queue_free())))


func _confirm_reset() -> void:
	var parts := UIKit.dialog(DataDB.t("settings.reset"), DataDB.t("settings.reset_confirm"))
	add_child(parts[0])
	var body: VBoxContainer = parts[1]
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	body.add_child(row)
	var no := UIKit.primary(UIKit.button(DataDB.t("ui.cancel"), "", func() -> void: parts[0].queue_free()))
	no.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(no)
	var yes := UIKit.button(DataDB.t("settings.reset_yes"), "", func() -> void:
		GameState.reset_game()
		reset_done.emit())
	yes.add_theme_color_override("font_color", Color("ff9a8a"))
	yes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(yes)

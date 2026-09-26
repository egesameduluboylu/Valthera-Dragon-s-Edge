class_name SettingsPanel
extends Control
## Settings (docs/08): music and sound volume, vibration, battle speed, language,
## replaying the tutorial and wiping the save. Values live in the Settings autoload.

signal closed
## Emitted after the save was wiped or the language changed; the town rebuilds itself.
signal reload

## Language names are shown in their own language.
const LANGUAGE_NAMES := {"tr": "Türkçe", "en": "English"}
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
	v.add_child(_slider_row("settings.music", Settings.music, func(x: float) -> void: Settings.set_value("music", x)))
	v.add_child(_slider_row("settings.sfx", Settings.sfx, func(x: float) -> void:
		Settings.set_value("sfx", x)
		Audio.play("ui_click", 0.0)))
	v.add_child(_toggle_row())
	var speeds: Array = []
	for sp in Settings.SPEEDS:
		speeds.append([sp, ("%.1fx" % sp).replace(".0x", "x")])
	v.add_child(_choice_row("settings.speed", speeds, Settings.battle_speed, func(x: Variant) -> void:
		Settings.set_value("battle_speed", x)))
	var langs: Array = []
	for id in Settings.LANGUAGES:
		langs.append([id, LANGUAGE_NAMES.get(id, id)])
	v.add_child(_choice_row("settings.language", langs, Settings.language, func(x: Variant) -> void:
		if x != Settings.language:
			Settings.set_value("language", x)
			DataDB.load_text(x)
			reload.emit()))
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
	b.button_pressed = Settings.vibration
	b.custom_minimum_size = Vector2(150, 60)
	var paint := func() -> void:
		b.text = DataDB.t("settings.on" if b.button_pressed else "settings.off")
		if b.button_pressed:
			UIKit.primary(b)
		else:
			UITheme.plain_button(b)
	paint.call()
	b.toggled.connect(func(on: bool) -> void:
		Settings.set_value("vibration", on)
		paint.call()
		Audio.vibrate(60))
	h.add_child(b)
	return h


## A label and a row of buttons, one per option ([value, text]); the current one is lit.
func _choice_row(key: String, options: Array, current: Variant, on_pick: Callable) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	v.add_child(UIKit.label(DataDB.t(key), 26))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	v.add_child(row)
	var buttons: Array[Button] = []
	for opt in options:
		var b := UIKit.button(opt[1], "", func() -> void: pass, 22)
		b.custom_minimum_size.y = 58
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(b)
		buttons.append(b)
	var paint := func(value: Variant) -> void:
		for i in buttons.size():
			if options[i][0] == value:
				UIKit.primary(buttons[i])
			else:
				UITheme.plain_button(buttons[i])
	paint.call(current)
	for i in buttons.size():
		var value: Variant = options[i][0]
		buttons[i].pressed.connect(func() -> void:
			paint.call(value)
			on_pick.call(value))
	return v


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
		reload.emit())
	yes.add_theme_color_override("font_color", Color("ff9a8a"))
	yes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(yes)

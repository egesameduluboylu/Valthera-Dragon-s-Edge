class_name SettingsPanel
extends Control
## Settings (docs/08): music and sound volume, vibration, effects, animations, battle speed,
## language, text size, replaying the tutorial and wiping the save. Values live in the Settings autoload.

signal closed
## Emitted after the save was wiped or the language or text size changed; the town rebuilds itself.
signal reload

## Language names are shown in their own language.
const LANGUAGE_NAMES := {"tr": "Türkçe", "en": "English"}
const VERSION := "0.8"


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("settings.title"), func() -> void: closed.emit())
	add_child(parts[0])
	var content: VBoxContainer = parts[1]
	# landscape: sound and switches on the left, choices and the save tools on the right
	var cols := UIKit.split(content, 0.5)
	var left := _card(cols[0])
	left.add_child(_slider_row("settings.music", Settings.music, func(x: float) -> void: Settings.set_value("music", x)))
	left.add_child(_slider_row("settings.sfx", Settings.sfx, func(x: float) -> void:
		Settings.set_value("sfx", x)
		Audio.play("ui_click", 0.0)))
	var gap := Control.new()
	gap.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_child(gap)
	left.add_child(UITheme.divider())
	left.add_child(_toggle_row("settings.vibration", "", Settings.vibration, func(on: bool) -> void:
		Settings.set_value("vibration", on)
		Audio.vibrate(60)))
	left.add_child(_toggle_row("settings.effects", "settings.effects_hint", Settings.effects, func(on: bool) -> void:
		Settings.set_value("effects", on)))
	left.add_child(_toggle_row("settings.animations", "settings.animations_hint", Settings.animations,
			func(on: bool) -> void: Settings.set_value("animations", on)))
	var right := _card(cols[1])
	var speeds: Array = []
	for sp in Settings.SPEEDS:
		speeds.append([sp, ("%.1fx" % sp).replace(".0x", "x")])
	right.add_child(_choice_row("settings.speed", speeds, Settings.battle_speed, func(x: Variant) -> void:
		Settings.set_value("battle_speed", x)))
	var sizes: Array = []
	for i in Settings.TEXT_SCALES.size():
		sizes.append([Settings.TEXT_SCALES[i], DataDB.t("settings.text_size.%d" % i)])
	right.add_child(_choice_row("settings.text_size", sizes, Settings.text_scale, func(x: Variant) -> void:
		if x != Settings.text_scale:
			Settings.set_value("text_scale", x)
			reload.emit()))
	var langs: Array = []
	for id in Settings.LANGUAGES:
		langs.append([id, LANGUAGE_NAMES.get(id, id)])
	right.add_child(_choice_row("settings.language", langs, Settings.language, func(x: Variant) -> void:
		if x != Settings.language:
			Settings.set_value("language", x)
			DataDB.load_text(x)
			reload.emit()))
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(spacer)
	right.add_child(UITheme.divider())
	var tools := HBoxContainer.new()
	tools.add_theme_constant_override("separation", 12)
	right.add_child(tools)
	var tut := UIKit.button(DataDB.t("settings.tutorial"), "", _replay_tutorial, 22)
	tut.custom_minimum_size.y = 68
	tut.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tools.add_child(tut)
	var reset := UIKit.button(DataDB.t("settings.reset"), "", _confirm_reset, 22)
	reset.custom_minimum_size.y = 68
	reset.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reset.add_theme_color_override("font_color", Color("ff9a8a"))
	tools.add_child(reset)
	var ver := UIKit.label(DataDB.tf("settings.version", {"v": VERSION}), 18, UITheme.TEXT_MUTED)
	ver.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	right.add_child(ver)


## A dark card in `column`; returns the VBox to fill.
func _card(column: VBoxContainer) -> VBoxContainer:
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(card)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	card.add_child(v)
	return v


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


## A name (with an optional muted hint under it) and an on/off button.
func _toggle_row(key: String, hint_key: String, value: bool, on_toggle: Callable) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	var names := VBoxContainer.new()
	names.add_theme_constant_override("separation", 0)
	names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	names.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(names)
	names.add_child(UIKit.label(DataDB.t(key), 26))
	if hint_key != "":
		names.add_child(UIKit.label(DataDB.t(hint_key), 18, UITheme.TEXT_MUTED))
	var b := UIKit.button("", "", func() -> void: pass, 22)
	b.toggle_mode = true
	b.button_pressed = value
	b.custom_minimum_size = Vector2(150, 64)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var paint := func() -> void:
		b.text = DataDB.t("settings.on" if b.button_pressed else "settings.off")
		if b.button_pressed:
			UIKit.primary(b)
		else:
			UITheme.plain_button(b)
	paint.call()
	b.toggled.connect(func(on: bool) -> void:
		on_toggle.call(on)
		paint.call())
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
		b.custom_minimum_size.y = 64
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

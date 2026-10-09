class_name UIKit
extends RefCounted
## Small builders shared by the town screens, so every panel looks the same.

const ITEM_ICON := "res://assets/icons/items/%s.png"


static func label(text: String, font_size: int = 26, color: Color = UITheme.TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", UITheme.fs(font_size))
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## Cinzel title with an ink outline. Text is upper-cased with the Turkish İ rule.
static func title(text: String, font_size: int = 40, color: Color = UITheme.GOLD) -> Label:
	var l := label(UITheme.caps(text), font_size, color)
	l.add_theme_font_override("font", UITheme.title_font())
	l.add_theme_color_override("font_outline_color", UITheme.INK)
	l.add_theme_constant_override("outline_size", maxi(6, font_size / 5))
	return l


static func wrapped(text: String, font_size: int = 24, color: Color = UITheme.TEXT) -> Label:
	var l := label(text, font_size, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


static func button(text: String, icon_path: String, on_press: Callable, font_size: int = 28) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size.y = 80
	b.add_theme_font_size_override("font_size", UITheme.fs(font_size))
	if icon_path != "":
		b.icon = load(icon_path)
		b.add_theme_constant_override("icon_max_width", 42)
	b.pressed.connect(func() -> void: Audio.play("ui_click"))
	b.pressed.connect(on_press)
	return b


## A gold "main action" button.
static func primary(b: Button) -> Button:
	return UITheme.primary_button(b)


static func icon(path: String, px: int) -> TextureRect:
	var t := TextureRect.new()
	t.texture = load(path)
	t.custom_minimum_size = Vector2(px, px)
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return t


## Icon followed by a number, e.g. gold in a header.
static func counter(icon_path: String, text: String, color: Color = UITheme.TEXT, px: int = 36) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 4)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(icon(icon_path, px))
	var l := label(text, int(px * 0.75), color)
	l.add_theme_color_override("font_outline_color", UITheme.INK)
	l.add_theme_constant_override("outline_size", 5)
	h.add_child(l)
	return h


static func counter_label(c: HBoxContainer) -> Label:
	return c.get_child(1)


static func hsep(height: int = 2, color: Color = UITheme.GOLD_DARK) -> ColorRect:
	var r := ColorRect.new()
	r.color = color
	r.custom_minimum_size.y = height
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


static func spacer(px: int, vertical: bool = true) -> Control:
	var c := Control.new()
	if vertical:
		c.custom_minimum_size.y = px
	else:
		c.custom_minimum_size.x = px
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


## A speech bubble next to an NPC portrait: [portrait][name + line].
static func npc_row(portrait_path: String, npc_name: String, line: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	if ResourceLoader.exists(portrait_path):
		row.add_child(icon(portrait_path, 118))
	var bubble := PanelContainer.new()
	bubble.add_theme_stylebox_override("panel", UITheme.skin_panel("parchment"))
	bubble.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bubble.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(bubble)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	bubble.add_child(v)
	v.add_child(label(npc_name, 22, Color("7a3a1a")))
	v.add_child(wrapped(line, 22, UITheme.INK))
	return row


## Full-screen town panel: dark backdrop, wooden sheet with a title bar and a close
## button. Returns [root, content] where content is a VBoxContainer to fill. The screen is
## landscape (docs/16): content is wide and short (about 1220 x 580 on a 1280 x 720 screen),
## so lay panels out side by side, see split().
static func sheet(title_text: String, on_close: Callable) -> Array:
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(dim)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 24)
	margin.add_theme_constant_override("margin_top", 12)
	margin.add_theme_constant_override("margin_bottom", 12)
	root.add_child(margin)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UITheme.skin_panel("wood"))
	margin.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	panel.add_child(v)
	var bar := HBoxContainer.new()
	v.add_child(bar)
	var t := title(title_text, 34)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(t)
	Audio.play("ui_open")
	var close := UITheme.close_button(button("", "", func() -> void:
		Audio.play("ui_close")
		on_close.call()), 58)
	bar.add_child(close)
	v.add_child(UITheme.divider())
	var content := VBoxContainer.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 10)
	v.add_child(content)
	panel.resized.connect(func() -> void: panel.pivot_offset = panel.size * 0.5)
	panel.scale = Vector2(0.96, 0.96)
	panel.modulate.a = 0.0
	var tw := panel.create_tween().set_parallel()
	tw.tween_property(panel, "scale", Vector2.ONE, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(panel, "modulate:a", 1.0, 0.18)
	return [root, content]


## Two columns side by side inside `parent` (a sheet's content): returns [left, right]
## VBoxContainers. `left_ratio` is the left column's share of the width. With `scroll`,
## each column scrolls on its own when its content is taller than the screen.
static func split(parent: Control, left_ratio: float = 0.42, scroll: bool = false) -> Array:
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 18)
	parent.add_child(row)
	var out: Array = []
	for ratio in [left_ratio, 1.0 - left_ratio]:
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 10)
		col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col.size_flags_vertical = Control.SIZE_EXPAND_FILL
		if scroll:
			var sc := ScrollContainer.new()
			sc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
			sc.size_flags_stretch_ratio = ratio
			sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
			sc.add_child(col)
			row.add_child(sc)
		else:
			col.size_flags_stretch_ratio = ratio
			row.add_child(col)
		out.append(col)
	return out


## A VBoxContainer inside a vertical ScrollContainer that fills `parent`.
static func scroll_list(parent: Control, separation: int = 10) -> VBoxContainer:
	var sc := ScrollContainer.new()
	sc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(sc)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", separation)
	sc.add_child(list)
	return list


## Small dialog in the middle of the screen. Returns [root, body] where body takes buttons.
static func dialog(title_text: String, text: String, art_path: String = "") -> Array:
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.65)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UITheme.skin_panel("wood"))
	panel.custom_minimum_size = Vector2(640, 0)
	center.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	panel.add_child(v)
	var t := title(title_text, 36)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(t)
	if art_path != "" and ResourceLoader.exists(art_path):
		var art := icon(art_path, 0)
		art.custom_minimum_size = Vector2(0, 190)
		v.add_child(art)
	if text != "":
		var body_text := wrapped(text, 24)
		body_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		body_text.custom_minimum_size.x = 580
		v.add_child(body_text)
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	v.add_child(body)
	panel.resized.connect(func() -> void: panel.pivot_offset = panel.size * 0.5)
	panel.scale = Vector2(0.85, 0.85)
	panel.modulate.a = 0.0
	var tw := panel.create_tween().set_parallel()
	tw.tween_property(panel, "scale", Vector2.ONE, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(panel, "modulate:a", 1.0, 0.2)
	return [root, body]

class_name UITheme
extends RefCounted
## Shared look for every screen: dark wood panels, gold trim, Nunito body text and
## Cinzel titles (docs/09). Built in code so colours live in one place.
##
## Two layers of styles live here:
## - flat styles (panel(), badge(), bar_fill()) return StyleBoxFlat that callers tweak;
## - the textured skin (skin_*(), tile_frame(), ...) returns StyleBoxTexture built from the
##   painted 9-slice PNGs in assets/ui/skin/ (tools/art/ui_skin.py). build() uses the skin
##   for every Button, ProgressBar and Panel/PanelContainer by default.

const WOOD := Color("2b1d17")
const WOOD_LIGHT := Color("4a3326")
const WOOD_DARK := Color("1b120e")
const GOLD := Color("d9a84e")
const GOLD_DARK := Color("8a6428")
const PARCHMENT := Color("f1e2c0")
const INK := Color("1c1418")
const TEXT := Color("f6ead2")
const TEXT_MUTED := Color("a8998a")
const HP := Color("d8413a")
const HP_PLAYER := Color("4fbf5a")
const RAGE := Color("f08a24")
const COMBO := Color("ffd24a")

const SKIN_PATH := "res://assets/ui/skin/%s.png"
## Per texture: texture margins [l, t, r, b], default content margins [l, t, r, b],
## expand margins [l, t, r, b] (shadow painted outside the box) and whether the middle
## tiles (true) or stretches (false; buttons still tile horizontally so the grain does not
## smear). Texture margins must match tools/art/ui_skin.py.
const SKIN := {
	"button": [[26, 16, 26, 24], [18, 10, 18, 16], [0, 0, 0, 0], false],
	"button_pressed": [[26, 16, 26, 24], [18, 14, 18, 12], [0, 0, 0, 0], false],
	"panel_wood": [[64, 64, 64, 64], [24, 24, 24, 24], [8, 8, 8, 8], true],
	"panel_parchment": [[26, 26, 26, 26], [16, 14, 16, 14], [5, 5, 5, 5], true],
	"panel_dark": [[20, 20, 20, 20], [14, 12, 14, 12], [0, 0, 0, 0], true],
	"header": [[0, 8, 0, 20], [18, 12, 18, 14], [0, 0, 0, 8], true],
	"footer": [[0, 20, 0, 8], [18, 16, 18, 22], [0, 8, 0, 0], true],
	"bar": [[8, 6, 8, 6], [0, 0, 0, 0], [0, 0, 0, 0], false],
	"tile": [[24, 24, 24, 24], [18, 18, 18, 18], [0, 0, 0, 0], false],
	"close": [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], false],
}
const PANEL_KINDS := ["wood", "parchment", "dark", "header", "footer"]
const BAR_FILLS := ["hp", "player", "xp", "rage", "gold", "white"]
const RARITIES := ["common", "rare", "epic", "legendary", "empty"]

static var _body_font: Font
static var _title_font: Font


static func body_font() -> Font:
	if _body_font == null:
		_body_font = _variation("res://assets/fonts/Nunito.ttf", 800)
	return _body_font


static func title_font() -> Font:
	if _title_font == null:
		_title_font = _variation("res://assets/fonts/Cinzel.ttf", 900)
	return _title_font


static func build() -> Theme:
	var t := Theme.new()
	t.default_font = body_font()
	t.default_font_size = 26

	t.set_color("font_color", "Label", TEXT)
	t.set_color("font_outline_color", "Label", INK)
	t.set_constant("outline_size", "Label", 0)

	for state in ["normal", "hover", "pressed", "disabled"]:
		t.set_stylebox(state, "Button", skin_button(state))
	t.set_stylebox("hover_pressed", "Button", skin_button("pressed"))
	t.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	t.set_color("font_color", "Button", TEXT)
	t.set_color("font_hover_color", "Button", Color.WHITE)
	t.set_color("font_pressed_color", "Button", GOLD)
	t.set_color("font_hover_pressed_color", "Button", GOLD)
	t.set_color("font_focus_color", "Button", TEXT)
	t.set_color("font_disabled_color", "Button", Color("8a7e74"))
	t.set_color("font_outline_color", "Button", INK)
	t.set_constant("outline_size", "Button", 4)
	t.set_constant("h_separation", "Button", 12)

	t.set_stylebox("panel", "PanelContainer", skin_panel("wood"))
	t.set_stylebox("panel", "Panel", skin_panel("wood"))

	t.set_stylebox("background", "ProgressBar", skin_bar_bg())
	t.set_stylebox("fill", "ProgressBar", skin_bar_fill("hp"))
	return t


static func panel(bg: Color = WOOD, border: Color = GOLD_DARK, radius: int = 16) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(3)
	s.set_corner_radius_all(radius)
	s.set_content_margin_all(14)
	s.shadow_color = Color(0, 0, 0, 0.45)
	s.shadow_size = 6
	s.shadow_offset = Vector2(0, 3)
	return s


static func badge(bg: Color = Color(0.08, 0.05, 0.07, 0.82)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = GOLD_DARK
	s.set_border_width_all(2)
	s.set_corner_radius_all(14)
	s.content_margin_left = 8
	s.content_margin_right = 10
	s.content_margin_top = 2
	s.content_margin_bottom = 2
	return s


static func bar_fill(color: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.set_corner_radius_all(7)
	s.border_color = color.lightened(0.35)
	s.border_width_top = 3
	# sit inside the rim of the textured groove (skin_bar_bg) instead of covering it
	s.expand_margin_left = -2
	s.expand_margin_top = -2
	s.expand_margin_right = -2
	s.expand_margin_bottom = -3
	return s


# ------------------------------------------------------------------ textured skin

## Wood-plank button skin. state: "normal", "hover", "pressed" or "disabled";
## primary gives the gold "main action" plank (no separate disabled look: it falls back
## to the plain disabled plank).
static func skin_button(state: String = "normal", primary: bool = false) -> StyleBoxTexture:
	var file := "button_%s" % state
	if state == "disabled":
		file = "button_disabled"
	elif primary:
		file = "button_primary_%s" % state
	return _skin(file, "button_pressed" if state == "pressed" else "button")


## Turns a Button into a gold "main action" button (normal/hover/pressed skins and a font
## colour that stays readable on gold). Returns the button for chaining.
static func primary_button(b: Button) -> Button:
	for state in ["normal", "hover", "pressed"]:
		b.add_theme_stylebox_override(state, skin_button(state, true))
	b.add_theme_stylebox_override("hover_pressed", skin_button("pressed", true))
	b.add_theme_color_override("font_color", Color.WHITE)
	b.add_theme_color_override("font_hover_color", Color("fff6dc"))
	b.add_theme_color_override("font_pressed_color", PARCHMENT)
	b.add_theme_color_override("font_hover_pressed_color", PARCHMENT)
	b.add_theme_color_override("font_outline_color", Color("3a1e08"))
	b.add_theme_constant_override("outline_size", 6)
	return b


## Panel skin. kind: "wood" (framed sheet with gold corners), "parchment" (speech bubbles,
## notes), "dark" (inset card inside a wood panel), "header" / "footer" (full-width bars
## with the gold trim on their inner edge). Unknown kinds fall back to "wood".
static func skin_panel(kind: String = "wood") -> StyleBoxTexture:
	if not kind in PANEL_KINDS:
		kind = "wood"
	var key: String = kind if kind in ["header", "footer"] else "panel_" + kind
	return _skin(key, key)


## Inset dark groove behind every ProgressBar.
static func skin_bar_bg() -> StyleBoxTexture:
	return _skin("bar_bg", "bar")


## Glossy bar fill. color_name: "hp" (red), "player" (green), "xp" (blue), "rage"
## (orange), "gold" or "white" (tint it with modulate_color, see skin_bar_fill_tinted).
static func skin_bar_fill(color_name: String = "hp") -> StyleBoxTexture:
	if not color_name in BAR_FILLS:
		color_name = "hp"
	return _skin("bar_" + color_name, "bar")


## Glossy bar fill in any colour (the white fill, tinted).
static func skin_bar_fill_tinted(color: Color) -> StyleBoxTexture:
	var s := _skin("bar_white", "bar")
	s.modulate_color = color
	return s


## 128 px item frame for a rarity ("common", "rare", "epic", "legendary", "empty") with a
## transparent centre: lay it over the icon and scale it uniformly with the tile.
static func tile_frame(rarity: String) -> Texture2D:
	if not rarity in RARITIES:
		rarity = "common"
	return load(SKIN_PATH % ("tile_" + rarity))


## The same frame with a dark, rarity-tinted well behind the icon, as a 9-slice style for a
## PanelContainer (best for tiles of 80 px and up; smaller tiles should use tile_frame).
static func skin_tile(rarity: String) -> StyleBoxTexture:
	if not rarity in RARITIES:
		rarity = "common"
	return _skin("tile_%s_filled" % rarity, "tile")


## Round brass medallion with an X. state: "normal", "hover" or "pressed". The texture is
## stretched whole, so keep the button square (close_button() does).
static func skin_close(state: String = "normal") -> StyleBoxTexture:
	if not state in ["normal", "hover", "pressed"]:
		state = "normal"
	return _skin("close_" + state, "close")


## Makes `b` the round brass close button (the X is painted, so the text is cleared).
static func close_button(b: Button, px: int = 72) -> Button:
	b.text = ""
	b.icon = null
	b.custom_minimum_size = Vector2(px, px)
	b.size_flags_horizontal = Control.SIZE_SHRINK_END
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	for state in ["normal", "hover", "pressed"]:
		b.add_theme_stylebox_override(state, skin_close(state))
	b.add_theme_stylebox_override("hover_pressed", skin_close("pressed"))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	return b


## Ornate gold divider: two fading lines around a small gem. Stretches horizontally.
static func divider() -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 0)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.custom_minimum_size.y = 24
	for part in ["left", "center", "right"]:
		var tex: Texture2D = load(SKIN_PATH % ("divider_" + part))
		if part == "center":
			var c := TextureRect.new()
			c.texture = tex
			c.mouse_filter = Control.MOUSE_FILTER_IGNORE
			row.add_child(c)
			continue
		var n := NinePatchRect.new()
		n.texture = tex
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.custom_minimum_size = Vector2(40, 24)
		n.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if part == "left":
			n.patch_margin_left = 80
		else:
			n.patch_margin_right = 80
		row.add_child(n)
	return row


## Builds a StyleBoxTexture from assets/ui/skin/<file>.png with the margins of SKIN[key].
## Always a fresh instance, so callers may change its margins or modulate_color.
static func _skin(file: String, key: String) -> StyleBoxTexture:
	var spec: Array = SKIN[key]
	var s := StyleBoxTexture.new()
	var path := SKIN_PATH % file
	if ResourceLoader.exists(path):
		s.texture = load(path)
	var tm: Array = spec[0]
	var cm: Array = spec[1]
	var em: Array = spec[2]
	for i in 4:
		s.set_texture_margin(i as Side, tm[i])
		s.set_content_margin(i as Side, cm[i])
		s.set_expand_margin(i as Side, em[i])
	if spec[3]:
		s.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT
		s.axis_stretch_vertical = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT
	elif key.begins_with("button"):
		# the grain repeats along the plank instead of smearing on wide buttons
		s.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT
	return s


## Upper-cases Turkish text for Cinzel titles. Cinzel draws lowercase as small caps, which
## turns "i" into a dotless "I", so titles are upper-cased with the Turkish i -> İ rule.
static func caps(text: String) -> String:
	return text.replace("i", "İ").to_upper()


## Outline + size overrides so stage text stays readable over the background.
static func stage_label(l: Label, font_size: int, color: Color = TEXT) -> Label:
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", INK)
	l.add_theme_constant_override("outline_size", maxi(4, font_size / 5))
	return l


static func _variation(path: String, weight: int) -> Font:
	var base: FontFile = load(path)
	var v := FontVariation.new()
	v.base_font = base
	v.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): weight}
	return v

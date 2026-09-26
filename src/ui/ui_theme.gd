class_name UITheme
extends RefCounted
## Shared look for every screen: dark wood panels, gold trim, Nunito body text and
## Cinzel titles (docs/09). Built in code so colours live in one place.

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

	t.set_stylebox("normal", "Button", _button(WOOD_LIGHT, GOLD_DARK))
	t.set_stylebox("hover", "Button", _button(WOOD_LIGHT.lightened(0.12), GOLD))
	t.set_stylebox("pressed", "Button", _button(WOOD_LIGHT.darkened(0.2), GOLD, true))
	t.set_stylebox("disabled", "Button", _button(Color("2e2724"), Color("4a4038")))
	t.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	t.set_color("font_color", "Button", TEXT)
	t.set_color("font_hover_color", "Button", Color.WHITE)
	t.set_color("font_pressed_color", "Button", GOLD)
	t.set_color("font_disabled_color", "Button", Color("7a6e64"))
	t.set_color("font_outline_color", "Button", INK)
	t.set_constant("outline_size", "Button", 4)
	t.set_constant("h_separation", "Button", 12)

	t.set_stylebox("panel", "PanelContainer", panel())
	t.set_stylebox("panel", "Panel", panel())

	var bar_bg := StyleBoxFlat.new()
	bar_bg.bg_color = Color("140d10")
	bar_bg.set_corner_radius_all(8)
	bar_bg.set_border_width_all(2)
	bar_bg.border_color = INK
	t.set_stylebox("background", "ProgressBar", bar_bg)
	t.set_stylebox("fill", "ProgressBar", bar_fill(HP))
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


static func _button(bg: Color, border: Color, pressed: bool = false) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(3)
	# thick bottom edge reads as a raised button; pressed moves it to the top
	s.border_width_bottom = 3 if pressed else 7
	s.border_width_top = 7 if pressed else 3
	s.set_corner_radius_all(16)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s


static func _variation(path: String, weight: int) -> Font:
	var base: FontFile = load(path)
	var v := FontVariation.new()
	v.base_font = base
	v.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): weight}
	return v

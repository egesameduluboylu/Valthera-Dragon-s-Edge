class_name ItemUI
extends RefCounted
## How items look everywhere: the rarity-framed slot, names in rarity colour, stat lines
## and the comparison card (docs/08 "Çanta / Karakter").

const EMPTY_ICON := {
	"weapon": "rusty_sword", "armor": "leather_armor", "helm": "leather_cap", "accessory": "copper_ring",
}
const ITEM_GOLD := "res://assets/icons/items/gold.png"
const UP := Color("7dff8a")
const DOWN := Color("ff7a6a")


static func defs() -> Dictionary:
	return DataDB.data["items"]


static func base_of(item: Dictionary) -> Dictionary:
	return defs()["bases"][item["base"]]


static func color(item: Dictionary) -> Color:
	return Color(Items.rarity_color(item, defs()))


static func item_name(item: Dictionary) -> String:
	var n := DataDB.t(base_of(item)["name_key"])
	var up := int(item.get("upgrade", 0))
	return n + (" +%d" % up if up > 0 else "")


## "Nadir · Kask · Sv 2"
static func subtitle(item: Dictionary) -> String:
	return "%s  ·  %s  ·  %s" % [DataDB.t("rarity." + item["rarity"]), DataDB.t("slot." + base_of(item)["slot"]),
			DataDB.t("ui.level") % int(item["level"])]


static func stat_value(stat: String, value: float) -> String:
	if stat in ["crit", "dodge"]:
		return ("%" + _num(value * 100.0)).replace(".", ",")
	if stat in Items.INT_STATS:
		return str(roundi(value))
	return _num(value).replace(".", ",")


static func _num(v: float) -> String:
	return str(snappedf(v, 0.1)).trim_suffix(".0")


static func perk_text(id: String, value: float) -> String:
	var shown := str(roundi(value * 100.0)) if id in defs().get("percent_perks", []) else str(roundi(value))
	return DataDB.tf("perk." + id, {"v": shown})


## The square item tile: rarity frame, icon and the +N badge. `item` may be empty,
## then a faded slot silhouette is shown for `slot`.
static func tile(item: Dictionary, px: int, slot: String = "", worn: bool = false) -> PanelContainer:
	var p := PanelContainer.new()
	p.custom_minimum_size = Vector2(px, px)
	p.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var st := UITheme.skin_tile("empty" if item.is_empty() else item["rarity"])
	st.set_content_margin_all(maxi(6, px / 7))
	p.add_theme_stylebox_override("panel", st)
	var holder := Control.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(holder)
	var ic := TextureRect.new()
	ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ic.set_anchors_preset(Control.PRESET_FULL_RECT)
	ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(ic)
	if item.is_empty():
		if slot != "":
			ic.texture = load(defs()["bases"][EMPTY_ICON[slot]]["icon"])
			ic.modulate = Color(0.35, 0.3, 0.28, 0.45)
		return p
	ic.texture = load(base_of(item)["icon"])
	var up := int(item.get("upgrade", 0))
	if up > 0:
		var badge := UIKit.label("+%d" % up, maxi(16, px / 4), UITheme.COMBO)
		badge.add_theme_color_override("font_outline_color", UITheme.INK)
		badge.add_theme_constant_override("outline_size", 6)
		badge.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
		badge.grow_horizontal = Control.GROW_DIRECTION_BEGIN
		badge.grow_vertical = Control.GROW_DIRECTION_BEGIN
		holder.add_child(badge)
	if worn:
		var mark := UIKit.label("✔", maxi(16, px / 4), UP)
		mark.add_theme_color_override("font_outline_color", UITheme.INK)
		mark.add_theme_constant_override("outline_size", 6)
		mark.position = Vector2(-2, -6)
		holder.add_child(mark)
	return p


## A tile inside a flat button, so it can be tapped.
static func tile_button(item: Dictionary, px: int, on_press: Callable, slot: String = "", worn: bool = false) -> Button:
	var b := Button.new()
	b.flat = true
	b.custom_minimum_size = Vector2(px, px)
	for s in ["normal", "hover", "pressed", "focus"]:
		b.add_theme_stylebox_override(s, StyleBoxEmpty.new())
	var t := tile(item, px, slot, worn)
	t.set_anchors_preset(Control.PRESET_FULL_RECT)
	b.add_child(t)
	b.pressed.connect(on_press)
	b.button_down.connect(func() -> void: t.modulate = Color(1.25, 1.25, 1.25))
	b.button_up.connect(func() -> void: t.modulate = Color.WHITE)
	return b


## Name, subtitle and stat lines. With `compare` (the item worn in that slot, or {} for
## an empty slot) each stat shows the difference in green or red.
static func details(item: Dictionary, compare: Variant = null) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var n := UIKit.label(item_name(item), 30, color(item))
	n.add_theme_color_override("font_outline_color", UITheme.INK)
	n.add_theme_constant_override("outline_size", 6)
	v.add_child(n)
	var sub := subtitle(item)
	if Items.is_unique(item, defs()):
		sub = DataDB.t("item.unique") + "  ·  " + sub
	v.add_child(UIKit.label(sub, 20, UITheme.TEXT_MUTED))
	var mine := Items.total_stats(item, defs())
	var theirs: Dictionary = {} if compare == null or (compare as Dictionary).is_empty() else Items.total_stats(compare, defs())
	for stat in defs()["stats"]:
		if not mine.has(stat) and not (compare != null and theirs.has(stat)):
			continue
		var value := float(mine.get(stat, 0))
		var row := HBoxContainer.new()
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var k := UIKit.label(DataDB.t("stat." + stat), 23, UITheme.TEXT)
		k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(k)
		row.add_child(UIKit.label(stat_value(stat, value), 23, UITheme.TEXT if mine.has(stat) else UITheme.TEXT_MUTED))
		if compare != null:
			var diff := value - float(theirs.get(stat, 0))
			var d := UIKit.label("", 21, UP if diff > 0 else DOWN)
			d.custom_minimum_size.x = 96
			d.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			if absf(diff) > 0.0001:
				d.text = ("▲ " if diff > 0 else "▼ ") + stat_value(stat, absf(diff))
			row.add_child(d)
		v.add_child(row)
	var perks := Items.perks(item, defs())
	for id in perks:
		var l := UIKit.wrapped("✦ " + perk_text(id, perks[id]), 22, Color("ffcf6a"))
		v.add_child(l)
	var desc_key: String = base_of(item).get("desc_key", "")
	if desc_key != "":
		var flavor := UIKit.wrapped(DataDB.t(desc_key), 19, Color("c9b79a"))
		v.add_child(flavor)
	var need := Items.wear_level(item, defs())
	if need > 1 and GameState.profile != null and need > GameState.profile.level():
		v.add_child(UIKit.label(DataDB.tf("item.wear_level", {"n": need}), 20, DOWN))
	return v

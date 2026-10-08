extends Control
## Kıvılcımköy, the hub (docs/07, docs/08): tap a building to open its screen. The
## Dungeon Gate starts a run; the smith, the merchant and the bag change the profile
## through GameState, which saves after each change.

const DUNGEON_SCENE := "res://src/scenes/dungeon/dungeon.tscn"
const ART := "res://assets/town/%s.png"
const ITEM_ICON := "res://assets/icons/items/%s.png"
const TOWN_DIR := "res://assets/town/v2"
## Where each building is tapped. The painted landscape town (docs/16) brings its own spots in
## assets/town/v2/hotspots.json (1920 x 1080 pixels); without it the old building sprites are
## lined up across the screen at these fractions of its size.
const BUILDINGS := {
	"gate": {"rect": Rect2(0.38, 0.14, 0.24, 0.5), "name": "town.dungeon"},
	"smith": {"rect": Rect2(0.03, 0.36, 0.2, 0.38), "name": "town.smith"},
	"class_master": {"rect": Rect2(0.2, 0.46, 0.18, 0.3), "name": "town.class_master"},
	"merchant": {"rect": Rect2(0.62, 0.38, 0.2, 0.36), "name": "town.merchant"},
	"inn": {"rect": Rect2(0.79, 0.44, 0.19, 0.32), "name": "town.market"},
}

var _level_label: Label
var _portrait: TextureRect
var _xp_bar: ProgressBar
var _gold: HBoxContainer
var _scales: HBoxContainer
var _potions: HBoxContainer
var _bag_count: Label
var _dragon_button: Button
var _dragon_glow: Tween
var _overlay: Control
var _fade: ColorRect
var _backdrop: Backdrop
var _busy: bool = false


func _ready() -> void:
	Audio.music("town")
	theme = UITheme.build()
	_build()
	_refresh()
	EventBus.profile_changed.connect(_refresh)
	_fade.color.a = 1.0
	_fade_to(0.0)
	if GameState.run == null and not GameState.profile.run_state.is_empty():
		_ask_resume()
	elif StoryDialog.has_scene("game_intro") and GameState.profile.take_story("game_intro"):
		GameState.changed()
		add_child(StoryDialog.new("game_intro"))
	else:
		_market_news()


# ---------------------------------------------------------------- screens

func open_panel(kind: String) -> void:
	if _busy:
		return
	_close_overlay()
	var panel: Control
	match kind:
		"gate":
			_show_gate()
			return
		"smith":
			panel = SmithPanel.new()
		"merchant":
			panel = MerchantPanel.new()
		"bag":
			panel = BagPanel.new()
		"inn":
			panel = MarketPanel.new()
		"class_master":
			panel = ClassMasterPanel.new()
		"dragon":
			panel = DragonPanel.new()
		"settings":
			var sp := SettingsPanel.new()
			sp.reload.connect(func() -> void: get_tree().reload_current_scene())
			panel = sp
		_:
			return
	panel.closed.connect(_close_overlay)
	_overlay.add_child(panel)
	_overlay.visible = true


func _show_gate() -> void:
	var gate := GatePanel.new()
	gate.closed.connect(_close_overlay)
	gate.enter.connect(_enter_dungeon)
	_overlay.add_child(gate)
	_overlay.visible = true


func _enter_dungeon(dungeon_id: String, hard: bool) -> void:
	if _busy:
		return
	_busy = true
	GameState.run = null
	GameState.next_dungeon = dungeon_id
	GameState.next_hard = hard
	await _fade_to(1.0)
	get_tree().change_scene_to_file(DUNGEON_SCENE)


func _ask_resume() -> void:
	var saved := GameState.saved_run()
	if saved == null:
		GameState.discard_run()
		return
	var name_ := DataDB.t(saved.def.get("name_key", ""))
	var parts := UIKit.dialog(DataDB.t("resume.title"),
			DataDB.tf("resume.text", {"dungeon": name_, "room": saved.room_number}), "res://assets/ui/door.png")
	_overlay.add_child(parts[0])
	_overlay.visible = true
	var body: VBoxContainer = parts[1]
	body.add_child(UIKit.primary(UIKit.button(DataDB.t("resume.continue"), "", func() -> void:
		if _busy:
			return
		_busy = true
		GameState.resume_run()
		await _fade_to(1.0)
		get_tree().change_scene_to_file(DUNGEON_SCENE))))
	body.add_child(UIKit.button(DataDB.t("resume.abandon"), "", func() -> void:
		GameState.discard_run()
		_close_overlay()))


## Tells the player what sold on the market while they were in the dungeon.
func _market_news() -> void:
	var news: Dictionary = GameState.market_news
	GameState.market_news = {}
	var lines: Array = []
	if news.get("sold", []).size() > 0:
		lines.append(DataDB.tf("market.news_sold", {"n": news["sold"].size()}))
	if news.get("expired", []).size() > 0:
		lines.append(DataDB.tf("market.news_expired", {"n": news["expired"].size()}))
	if lines.is_empty():
		return
	var parts := UIKit.dialog(DataDB.t("market.title"), "\n".join(lines), ART % "npc_innkeeper")
	_overlay.add_child(parts[0])
	_overlay.visible = true
	var body: VBoxContainer = parts[1]
	body.add_child(UIKit.primary(UIKit.button(DataDB.t("market.tab_mail"), "", func() -> void:
		_close_overlay()
		open_panel("inn"))))
	body.add_child(UIKit.button(DataDB.t("bag.close"), "", _close_overlay))


func _close_overlay() -> void:
	for c in _overlay.get_children():
		c.queue_free()
	_overlay.visible = false
	_refresh()


# ---------------------------------------------------------------- drawing

func _refresh() -> void:
	var p := GameState.profile
	_level_label.text = "%s  ·  %s" % [DataDB.t("class." + p.active_class), DataDB.t("ui.level") % p.level()]
	_portrait.texture = load(DataDB.data["classes"][p.active_class].get("sprite", ""))
	_xp_bar.max_value = Progression.xp_to_next(p.level())
	_xp_bar.value = p.class_xp()
	UIKit.counter_label(_gold).text = str(p.gold)
	UIKit.counter_label(_scales).text = str(p.scales)
	UIKit.counter_label(_potions).text = str(p.potions)
	_bag_count.text = DataDB.tf("bag.count", {"n": p.bag_items().size(), "max": p.bag_size()})
	_refresh_dragon(p)


func _refresh_dragon(p: Profile) -> void:
	var state: Dictionary = p.companion
	_dragon_button.visible = not state.is_empty() or p.can_nest()
	if not _dragon_button.visible:
		return
	var path := "res://assets/icons/items/gear/dragon_egg.png"
	if Companion.is_hatched(state):
		path = Companion.sprite(state["element"], int(state["level"]), DataDB.data["companion"])
	_dragon_button.icon = load(path) if ResourceLoader.exists(path) else null
	# something to do at the nest: an egg to put in, or one about to hatch
	var calling := p.can_nest() or p.egg_ready()
	if _dragon_glow != null:
		_dragon_glow.kill()
		_dragon_glow = null
		_dragon_button.scale = Vector2.ONE
	if calling:
		_dragon_glow = _dragon_button.create_tween().set_loops()
		_dragon_glow.tween_property(_dragon_button, "scale", Vector2(1.15, 1.15), 0.45).set_trans(Tween.TRANS_SINE)
		_dragon_glow.tween_property(_dragon_button, "scale", Vector2.ONE, 0.45).set_trans(Tween.TRANS_SINE)


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var view := get_viewport_rect().size
	var sky := ColorRect.new()
	sky.color = Color("2a1a2e")
	sky.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(sky)
	# the painted town, alive: drifting clouds, sun rays, chimney smoke, flickering windows
	_backdrop = Backdrop.new()
	_backdrop.density = 1.0 if Settings.effects else 0.4
	_backdrop.setup(TOWN_DIR, "res://assets/town/background.png", view, view.y * 0.72)
	add_child(_backdrop)
	var spots := _hotspots(view)
	for id in BUILDINGS:
		add_child(_building(id, spots[id], not _backdrop.has_layers()))

	_build_header()
	_build_bottom()

	_overlay = Control.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	add_child(_overlay)
	_fade = ColorRect.new()
	_fade.color = Color(0, 0, 0, 0)
	_fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade.mouse_filter = Control.MOUSE_FILTER_STOP
	_fade.visible = false
	add_child(_fade)


## {id: {"rect": Rect2, "label": Vector2}} in screen pixels.
func _hotspots(view: Vector2) -> Dictionary:
	var out := {}
	var path := TOWN_DIR.path_join("hotspots.json")
	var parsed: Variant = null
	if _backdrop.has_layers() and FileAccess.file_exists(path):
		parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	for id in BUILDINGS:
		var spot: Dictionary = parsed.get(id, {}) if parsed is Dictionary else {}
		if spot.has("rect"):
			var r: Array = spot["rect"]
			var a := _backdrop.to_view(Vector2(r[0], r[1]))
			var b := _backdrop.to_view(Vector2(r[0] + r[2], r[1] + r[3]))
			var label: Array = spot.get("label", [r[0] + r[2] * 0.5, r[1] + r[3]])
			out[id] = {"rect": Rect2(a, b - a), "label": _backdrop.to_view(Vector2(label[0], label[1]))}
		else:
			var f: Rect2 = BUILDINGS[id]["rect"]
			var rect := Rect2(f.position * view, f.size * view)
			out[id] = {"rect": rect, "label": Vector2(rect.get_center().x, rect.end.y - 10)}
	return out


## A tappable building. With the painted town the art is part of the backdrop, so the
## button is invisible and lights the building up while pressed; without it the old
## building sprite is drawn in the button.
func _building(id: String, spot: Dictionary, with_sprite: bool) -> Control:
	var rect: Rect2 = spot["rect"]
	var def: Dictionary = BUILDINGS[id]
	var holder := Control.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	var b := Button.new()
	b.flat = true
	b.position = rect.position
	b.size = rect.size
	for s in ["normal", "hover", "pressed", "focus", "disabled"]:
		b.add_theme_stylebox_override(s, StyleBoxEmpty.new())
	holder.add_child(b)
	# a soft light that swells on the building when it is pressed
	var light := TextureRect.new()
	light.texture = BattleFx.dot()
	light.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	light.stretch_mode = TextureRect.STRETCH_SCALE
	light.size = rect.size * 1.1
	light.position = -rect.size * 0.05
	light.modulate = Color(1.0, 0.85, 0.5, 0.0)
	light.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	light.material = add
	b.add_child(light)
	var sprite := TextureRect.new()
	if with_sprite and ResourceLoader.exists(ART % id):
		sprite.texture = load(ART % id)
	sprite.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	sprite.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	sprite.size = rect.size
	sprite.pivot_offset = Vector2(rect.size.x * 0.5, rect.size.y)
	sprite.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(sprite)
	# name plaque
	var plaque := PanelContainer.new()
	var st := UITheme.panel(Color(UITheme.WOOD, 0.9), UITheme.GOLD, 12)
	st.content_margin_top = 2
	st.content_margin_bottom = 2
	st.content_margin_left = 14
	st.content_margin_right = 14
	plaque.add_theme_stylebox_override("panel", st)
	plaque.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plaque.add_child(UIKit.title(DataDB.t(def["name"]), 20, UITheme.GOLD))
	holder.add_child(plaque)
	plaque.reset_size()
	var label: Vector2 = spot["label"]
	var psize := plaque.get_combined_minimum_size()
	plaque.position = Vector2(label.x - psize.x * 0.5, minf(label.y - psize.y * 0.5, get_viewport_rect().size.y - 150))
	b.pressed.connect(func() -> void:
		var tw := b.create_tween()
		tw.tween_property(sprite, "scale", Vector2(1.05, 0.96), 0.08)
		tw.parallel().tween_property(light, "modulate:a", 0.45, 0.08)
		tw.tween_property(sprite, "scale", Vector2.ONE, 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tw.parallel().tween_property(light, "modulate:a", 0.0, 0.25)
		await tw.finished
		open_panel(id))
	b.button_down.connect(func() -> void: light.modulate.a = 0.35)
	b.button_up.connect(func() -> void: light.modulate.a = 0.0)
	if id == "gate":
		# the gate's plaque glows a little so it reads as "tap me"
		var tw := plaque.create_tween().set_loops()
		tw.tween_property(plaque, "modulate", Color(1.25, 1.15, 0.95), 1.2).set_trans(Tween.TRANS_SINE)
		tw.tween_property(plaque, "modulate", Color.WHITE, 1.2).set_trans(Tween.TRANS_SINE)
	return holder


func _build_header() -> void:
	var header := PanelContainer.new()
	var hs := UITheme.skin_panel("header")
	hs.content_margin_top = 8
	hs.content_margin_bottom = 8
	hs.content_margin_left = 16
	hs.content_margin_right = 16
	header.add_theme_stylebox_override("panel", hs)
	header.set_anchors_preset(Control.PRESET_TOP_WIDE)
	add_child(header)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 12)
	header.add_child(top)
	_portrait = UIKit.icon(DataDB.data["classes"][GameState.active_class].get("sprite", ""), 58)
	top.add_child(_portrait)
	var pv := VBoxContainer.new()
	pv.custom_minimum_size.x = 250
	pv.add_theme_constant_override("separation", 4)
	pv.alignment = BoxContainer.ALIGNMENT_CENTER
	top.add_child(pv)
	_level_label = UIKit.label("", 22)
	pv.add_child(_level_label)
	_xp_bar = ProgressBar.new()
	_xp_bar.show_percentage = false
	_xp_bar.custom_minimum_size.y = 12
	_xp_bar.add_theme_stylebox_override("fill", UITheme.skin_bar_fill("xp"))
	pv.add_child(_xp_bar)
	# the companion dragon's nest (docs/15): shows up once the player owns the egg
	_dragon_button = UIKit.button("", "", func() -> void: open_panel("dragon"))
	_dragon_button.flat = true
	_dragon_button.custom_minimum_size = Vector2(64, 64)
	_dragon_button.expand_icon = true
	_dragon_button.tooltip_text = DataDB.t("town.dragon")
	_dragon_button.pivot_offset = Vector2(32, 32)
	top.add_child(_dragon_button)
	var t := UIKit.title(DataDB.t("town.name"), 34)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	top.add_child(t)
	_gold = UIKit.counter(ITEM_ICON % "gold", "0", UITheme.GOLD, 32)
	top.add_child(_gold)
	top.add_child(UIKit.spacer(10, false))
	_scales = UIKit.counter(ITEM_ICON % "scale", "0", Color("7fd4ff"), 32)
	top.add_child(_scales)
	top.add_child(UIKit.spacer(10, false))
	_potions = UIKit.counter(ITEM_ICON % "potion", "0", UITheme.TEXT, 32)
	top.add_child(_potions)
	top.add_child(UIKit.spacer(10, false))
	var gear := UITheme.close_button(UIKit.button("", "", func() -> void: open_panel("settings")), 52, "gear")
	gear.tooltip_text = DataDB.t("town.settings")
	top.add_child(gear)


func _build_bottom() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	row.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	row.offset_left = 18
	row.offset_right = -18
	row.offset_top = -92
	row.offset_bottom = -14
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(row)
	var bag := UIKit.button(DataDB.t("town.bag"), ITEM_ICON % "bag", func() -> void: open_panel("bag"))
	bag.custom_minimum_size.x = 250
	row.add_child(bag)
	_bag_count = UIKit.label("", 18, UITheme.TEXT_MUTED)
	_bag_count.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_bag_count.position = Vector2(-66, 4)
	bag.add_child(_bag_count)
	var gap := Control.new()
	gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(gap)
	var go := UIKit.primary(UIKit.button(DataDB.t("town.gate.enter"), "res://assets/icons/rooms/combat.png",
			func() -> void: open_panel("gate")))
	go.custom_minimum_size.x = 320
	row.add_child(go)


func _fade_to(alpha: float) -> void:
	_fade.visible = true
	var tw := create_tween()
	tw.tween_property(_fade, "color:a", alpha, 0.25)
	await tw.finished
	_fade.visible = alpha > 0.0

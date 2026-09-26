extends Control
## Kıvılcımköy, the hub (docs/07, docs/08): tap a building to open its screen. The
## Dungeon Gate starts a run; the smith, the merchant and the bag change the profile
## through GameState, which saves after each change.

const DUNGEON_SCENE := "res://src/scenes/dungeon/dungeon.tscn"
const ART := "res://assets/town/%s.png"
const ITEM_ICON := "res://assets/icons/items/%s.png"
## Building sprites and their spots on the 720x1280 background (tools/art/town.py).
const BUILDINGS := {
	"gate": {"rect": Rect2(210, 250, 300, 310), "name": "town.dungeon"},
	"smith": {"rect": Rect2(20, 560, 320, 300), "name": "town.smith"},
	"merchant": {"rect": Rect2(380, 560, 320, 300), "name": "town.merchant"},
	"class_master": {"rect": Rect2(20, 880, 320, 240), "name": "town.class_master"},
	"inn": {"rect": Rect2(380, 880, 320, 240), "name": "town.market"},
}

var _level_label: Label
var _portrait: TextureRect
var _xp_bar: ProgressBar
var _gold: HBoxContainer
var _scales: HBoxContainer
var _potions: HBoxContainer
var _bag_count: Label
var _overlay: Control
var _fade: ColorRect
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
		"settings":
			var sp := SettingsPanel.new()
			sp.reset_done.connect(func() -> void: get_tree().reload_current_scene())
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


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var sky := ColorRect.new()
	sky.color = Color("2a1a2e")
	sky.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(sky)
	# The town is drawn for 720x1280 and centred; taller screens show more sky/ground.
	var world := Control.new()
	world.set_anchors_preset(Control.PRESET_CENTER)
	world.custom_minimum_size = Vector2(720, 1280)
	world.position = Vector2(-360, -640)
	world.size = Vector2(720, 1280)
	add_child(world)
	if ResourceLoader.exists(ART % "background"):
		var bg := TextureRect.new()
		bg.texture = load(ART % "background")
		bg.size = Vector2(720, 1280)
		world.add_child(bg)
	for id in BUILDINGS:
		world.add_child(_building(id, BUILDINGS[id]))

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


func _building(id: String, def: Dictionary) -> Control:
	var rect: Rect2 = def["rect"]
	var locked: bool = def.get("locked", false)
	var b := Button.new()
	b.flat = true
	b.position = rect.position
	b.size = rect.size
	for s in ["normal", "hover", "pressed", "focus", "disabled"]:
		b.add_theme_stylebox_override(s, StyleBoxEmpty.new())
	var sprite := TextureRect.new()
	if ResourceLoader.exists(ART % id):
		sprite.texture = load(ART % id)
	sprite.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	sprite.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	sprite.size = rect.size
	sprite.pivot_offset = Vector2(rect.size.x * 0.5, rect.size.y)
	sprite.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if locked:
		sprite.modulate = Color(0.55, 0.5, 0.55)
	b.add_child(sprite)
	# name plaque
	var plaque := PanelContainer.new()
	var st := UITheme.panel(Color(UITheme.WOOD, 0.92), UITheme.GOLD if not locked else Color("5a4a3e"), 14)
	st.content_margin_top = 4
	st.content_margin_bottom = 4
	st.content_margin_left = 14
	st.content_margin_right = 14
	plaque.add_theme_stylebox_override("panel", st)
	plaque.mouse_filter = Control.MOUSE_FILTER_IGNORE
	plaque.add_child(UIKit.title(DataDB.t(def["name"]), 24, UITheme.GOLD if not locked else UITheme.TEXT_MUTED))
	b.add_child(plaque)
	plaque.reset_size()
	var plaque_y := rect.size.y - 34 if id != "gate" else rect.size.y - 20
	plaque.position = Vector2((rect.size.x - plaque.get_combined_minimum_size().x) * 0.5, plaque_y)
	if locked:
		var soon := UIKit.label(DataDB.t("town.locked"), 18, UITheme.TEXT_MUTED)
		soon.add_theme_color_override("font_outline_color", UITheme.INK)
		soon.add_theme_constant_override("outline_size", 6)
		soon.position = Vector2(plaque.position.x + 8, plaque_y - 26)
		b.add_child(soon)
		b.disabled = true
	else:
		b.pressed.connect(func() -> void:
			var tw := sprite.create_tween()
			tw.tween_property(sprite, "scale", Vector2(1.06, 0.95), 0.08)
			tw.tween_property(sprite, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			await tw.finished
			open_panel(id))
		b.button_down.connect(func() -> void: sprite.modulate = Color(1.2, 1.15, 1.05))
		b.button_up.connect(func() -> void: sprite.modulate = Color.WHITE)
	if id == "gate":
		# the gate breathes a little so it reads as "tap me"
		var tw := sprite.create_tween().set_loops()
		tw.tween_property(sprite, "scale", Vector2(1.015, 1.015), 1.4).set_trans(Tween.TRANS_SINE)
		tw.tween_property(sprite, "scale", Vector2.ONE, 1.4).set_trans(Tween.TRANS_SINE)
	return b


func _build_header() -> void:
	var header := PanelContainer.new()
	var hs := UITheme.skin_panel("header")
	hs.content_margin_top = 14
	hs.content_margin_bottom = 12
	hs.content_margin_left = 18
	hs.content_margin_right = 18
	header.add_theme_stylebox_override("panel", hs)
	header.set_anchors_preset(Control.PRESET_TOP_WIDE)
	add_child(header)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	header.add_child(v)
	var top := HBoxContainer.new()
	v.add_child(top)
	var t := UIKit.title(DataDB.t("town.name"), 38)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(t)
	_gold = UIKit.counter(ITEM_ICON % "gold", "0", UITheme.GOLD, 34)
	top.add_child(_gold)
	top.add_child(UIKit.spacer(12, false))
	_scales = UIKit.counter(ITEM_ICON % "scale", "0", Color("7fd4ff"), 34)
	top.add_child(_scales)
	top.add_child(UIKit.spacer(12, false))
	_potions = UIKit.counter(ITEM_ICON % "potion", "0", UITheme.TEXT, 34)
	top.add_child(_potions)
	top.add_child(UIKit.spacer(12, false))
	var gear := UITheme.close_button(UIKit.button("", "", func() -> void: open_panel("settings")), 56, "gear")
	gear.tooltip_text = DataDB.t("town.settings")
	top.add_child(gear)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	v.add_child(row)
	_portrait = UIKit.icon(DataDB.data["classes"][GameState.active_class].get("sprite", ""), 64)
	row.add_child(_portrait)
	var pv := VBoxContainer.new()
	pv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pv.add_theme_constant_override("separation", 4)
	row.add_child(pv)
	_level_label = UIKit.label("", 24)
	pv.add_child(_level_label)
	_xp_bar = ProgressBar.new()
	_xp_bar.show_percentage = false
	_xp_bar.custom_minimum_size.y = 14
	_xp_bar.add_theme_stylebox_override("fill", UITheme.skin_bar_fill("xp"))
	pv.add_child(_xp_bar)


func _build_bottom() -> void:
	var bar := PanelContainer.new()
	var st := UITheme.skin_panel("footer")
	st.content_margin_top = 12
	st.content_margin_bottom = 26
	st.content_margin_left = 18
	st.content_margin_right = 18
	bar.add_theme_stylebox_override("panel", st)
	bar.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	bar.grow_vertical = Control.GROW_DIRECTION_BEGIN
	add_child(bar)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	bar.add_child(row)
	var bag := UIKit.button(DataDB.t("town.bag"), ITEM_ICON % "bag", func() -> void: open_panel("bag"))
	bag.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(bag)
	_bag_count = UIKit.label("", 18, UITheme.TEXT_MUTED)
	_bag_count.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_bag_count.position = Vector2(-70, 4)
	bag.add_child(_bag_count)
	var go := UIKit.primary(UIKit.button(DataDB.t("town.gate.enter"), "res://assets/icons/rooms/combat.png",
			func() -> void: open_panel("gate")))
	go.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(go)


func _fade_to(alpha: float) -> void:
	_fade.visible = true
	var tw := create_tween()
	tw.tween_property(_fade, "color:a", alpha, 0.25)
	await tw.finished
	_fade.visible = alpha > 0.0

extends Control
## Battle screen. All rules live in CombatEngine; this script draws state and plays
## the engine's events back as animations (docs/08, docs/10).

const STAGE_HEIGHT := 700
const EVENT_DELAY := 0.35
const PLAYER_RECT := Rect2(20, 360, 270, 270)
## Enemy sprite rects on the stage for 1, 2 and 3 enemies.
const ENEMY_SLOTS := {
	1: [Rect2(400, 330, 240, 240)],
	2: [Rect2(300, 340, 200, 200), Rect2(505, 340, 200, 200)],
	3: [Rect2(285, 360, 150, 150), Rect2(430, 300, 150, 150), Rect2(565, 360, 150, 150)],
}

var engine: CombatEngine
var selected_target: String = ""
var busy: bool = false

var _stage: Control
var _turn_label: Label
var _combo_label: Label
var _log_label: Label
var _enemy_views: Dictionary = {}   # uid -> view dictionary, see _build_enemy_view
var _player_view: Dictionary = {}
var _skill_grid: GridContainer
var _skill_buttons: Dictionary = {} # skill_id -> Button
var _defend_button: Button
var _result_layer: Control
var _result_title: Label
var _result_body: Label
var _log_lines: Array[String] = []
var _idle_tweens: Array[Tween] = []


func _ready() -> void:
	theme = UITheme.build()
	_build_ui()
	_new_battle()


func _new_battle() -> void:
	engine = CombatEngine.from_data(DataDB.data, GameState.active_class, 1, "prototype")
	selected_target = engine.enemies[0].uid
	_log_lines.clear()
	_log_label.text = ""
	_result_layer.visible = false
	_combo_label.modulate.a = 0.0
	_build_player_view()
	_build_enemy_views()
	_build_skill_buttons()
	_play(engine.start())


# ---------------------------------------------------------------- input

func _on_skill_pressed(skill_id: String) -> void:
	if busy:
		return
	_play(engine.use_skill(skill_id, selected_target))


func _on_defend_pressed() -> void:
	if busy:
		return
	_play(engine.defend())


func _on_enemy_input(event: InputEvent, uid: String) -> void:
	var pressed: bool = (event is InputEventMouseButton and event.pressed) or (event is InputEventScreenTouch and event.pressed)
	if pressed and engine.get_combatant(uid).is_alive():
		selected_target = uid
		_refresh()


# ---------------------------------------------------------------- event playback

func _play(events: Array) -> void:
	busy = true
	_refresh_buttons()
	for ev in events:
		var wait := _apply_event(ev)
		if wait > 0.0:
			await get_tree().create_timer(wait).timeout
	var current := engine.get_combatant(selected_target)
	if current == null or not current.is_alive():
		var alive := engine.alive_enemies()
		selected_target = alive[0].uid if not alive.is_empty() else ""
	busy = false
	_refresh()


## Draws one event and returns how long to pause after it.
func _apply_event(ev: Dictionary) -> float:
	match ev["type"]:
		"turn_start":
			_turn_label.text = DataDB.t("ui.turn") % ev["turn"]
			return 0.0
		"intents":
			for uid in ev["intents"]:
				_set_intent(_enemy_views[uid], ev["intents"][uid])
			return 0.0
		"skill":
			_log(DataDB.t(DataDB.skill(ev["skill"]).get("name_key", "")))
			_lunge(_player_view["sprite"], 1.0)
			return 0.15
		"enemy_move":
			var e := engine.get_combatant(ev["source"])
			var view: Dictionary = _enemy_views[ev["source"]]
			view["intent"].visible = false
			_log("%s: %s" % [DataDB.t(e.name_key), _move_label(ev["move_type"])])
			if ev["move_type"] == "attack":
				_lunge(view["sprite"], -1.0)
			else:
				_pulse(view["sprite"])
			return 0.2
		"damage":
			var view := _view_of(ev["target"])
			var c := engine.get_combatant(ev["target"])
			view["hp_bar"].value = ev["hp"]
			view["hp_label"].text = "%d / %d" % [ev["hp"], c.max_hp()]
			var txt := str(ev["amount"])
			var col := Color.WHITE
			var font_size := 44
			if ev["dot"]:
				col = Color("ff8a7a")
				font_size = 34
			if ev["crit"]:
				txt += "!"
				col = Color("ffe14a")
				font_size = 58
			if ev["combo"]:
				col = UITheme.COMBO
				font_size = 60
			if ev["absorbed"] > 0:
				_float_text(view, "(%d)" % ev["absorbed"], Color("8fc4ff"), 30, -50)
			_float_text(view, txt, col, font_size)
			_hit_flash(view["sprite"])
			if ev["target"] == "p":
				_shake()
			return EVENT_DELAY
		"miss":
			_float_text(_view_of(ev["target"]), DataDB.t("ui.miss"), Color("c8c8c8"), 34)
			return EVENT_DELAY
		"death":
			_die(_view_of(ev["target"]))
			return 0.3
		"status_applied", "status_removed", "shield":
			var view := _view_of(ev["target"])
			_fill_status_row(view["statuses"], engine.get_combatant(ev["target"]))
			if ev["type"] == "status_applied":
				_float_text(view, DataDB.t("status." + ev["status"]), Color("d9b8ff"), 28, 60)
				return 0.15
			if ev["type"] == "shield":
				_float_text(view, "+%d" % ev["amount"], Color("8fc4ff"), 36)
				return 0.2
			return 0.0
		"immune":
			_float_text(_view_of(ev["target"]), "%s -" % DataDB.t("status." + ev["status"]), Color("a0a0a0"), 28, 60)
			return 0.15
		"resource":
			_player_view["res_bar"].value = ev["value"]
			_player_view["res_label"].text = "%s %d / %d" % [DataDB.t("resource." + engine.player.resource_id), ev["value"], engine.player.resource_max]
			return 0.0
		"skip":
			_float_text(_view_of(ev["target"]), DataDB.t("status.stun"), Color("fff08a"), 36)
			_log("%s: %s" % [DataDB.t(engine.get_combatant(ev["target"]).name_key), DataDB.t("ui.skip")])
			return EVENT_DELAY
		"combo":
			_show_combo(ev["count"])
			return 0.3
		"battle_end":
			_show_result(ev)
			return 0.0
	return 0.0


# ---------------------------------------------------------------- refresh

func _refresh() -> void:
	for e in engine.enemies:
		var v: Dictionary = _enemy_views[e.uid]
		v["hp_bar"].value = e.hp
		v["hp_label"].text = "%d / %d" % [e.hp, e.max_hp()]
		_fill_status_row(v["statuses"], e)
		var selected := e.uid == selected_target and e.is_alive()
		v["ring"].visible = selected
		v["arrow"].visible = selected
		if e.is_alive() and not e.intent.is_empty():
			_set_intent(v, e.intent)
	var p := engine.player
	_player_view["hp_bar"].value = p.hp
	_player_view["hp_label"].text = "%d / %d" % [p.hp, p.max_hp()]
	_player_view["res_bar"].value = p.resource
	_player_view["res_label"].text = "%s %d / %d" % [DataDB.t("resource." + p.resource_id), p.resource, p.resource_max]
	_fill_status_row(_player_view["statuses"], p)
	_refresh_buttons()


func _refresh_buttons() -> void:
	var target := engine.get_combatant(selected_target)
	for id in _skill_buttons:
		var b: Button = _skill_buttons[id]
		var def := DataDB.skill(id)
		var reason := engine.skill_block_reason(id)
		var line2 := ""
		if reason == "cooldown":
			line2 = DataDB.t("ui.cooldown") % engine.player.cooldowns[id]
		elif int(def.get("cost", 0)) > 0:
			line2 = "%d %s" % [def["cost"], DataDB.t("resource." + engine.player.resource_id)]
		b.text = DataDB.t(def.get("name_key", id)) + ("\n" + line2 if line2 != "" else "")
		b.disabled = busy or reason != ""
		# Combo hint (docs/08): a finisher glows when the target has what it needs.
		var ready := not b.disabled and engine.combo_ready(id, target)
		b.modulate = Color(1.08, 1.04, 0.92) if ready else Color.WHITE
		b.get_meta("glow").visible = ready
	_defend_button.disabled = busy or engine.finished


func _set_intent(view: Dictionary, intent: Dictionary) -> void:
	var type: String = intent.get("type", "")
	var icon := type
	var text := ""
	match type:
		"attack":
			text = str(intent.get("estimate", 0))
		"shield":
			text = str(intent.get("estimate", 0))
		"buff_ally":
			icon = "buff"
	view["intent_icon"].texture = load("res://assets/icons/intents/%s.png" % icon)
	view["intent_label"].text = text
	view["intent_label"].visible = text != ""
	view["intent_debuff"].visible = intent.get("debuff", false)
	view["intent"].visible = type != ""


func _fill_status_row(row: HBoxContainer, c: Combatant) -> void:
	for child in row.get_children():
		child.queue_free()
	if c.shield > 0:
		row.add_child(_status_chip("shield_status", str(c.shield)))
	for id in c.statuses:
		var s: StatusEffect = c.statuses[id]
		row.add_child(_status_chip(id, "x%d" % s.stacks if s.stacks > 1 else str(s.turns)))


func _status_chip(icon_id: String, text: String) -> Control:
	var box := HBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var icon := TextureRect.new()
	icon.texture = load("res://assets/icons/statuses/%s.png" % icon_id)
	icon.custom_minimum_size = Vector2(34, 34)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.tooltip_text = DataDB.t("status." + icon_id)
	box.add_child(icon)
	box.add_child(UITheme.stage_label(_label(text), 20))
	return box


# ---------------------------------------------------------------- text helpers

func _move_label(move_type: String) -> String:
	match move_type:
		"attack":
			return DataDB.t("intent.attack")
		"shield":
			return DataDB.t("intent.shield")
		"buff_ally":
			return DataDB.t("intent.buff")
	return move_type


func _view_of(uid: String) -> Dictionary:
	return _player_view if uid == "p" else _enemy_views[uid]


func _log(line: String) -> void:
	_log_lines.append(line)
	while _log_lines.size() > 2:
		_log_lines.pop_front()
	_log_label.text = "  •  ".join(_log_lines)


# ---------------------------------------------------------------- juice

func _float_text(view: Dictionary, text: String, color: Color, font_size: int, x_offset: float = 0.0) -> void:
	var sprite: Control = view["sprite"]
	var l := UITheme.stage_label(_label(text), font_size, color)
	l.add_theme_font_override("font", UITheme.body_font())
	_stage.add_child(l)
	l.reset_size()
	var anchor := sprite.get_global_rect()
	l.global_position = Vector2(anchor.get_center().x - l.size.x * 0.5 + x_offset, anchor.position.y + anchor.size.y * 0.2)
	l.pivot_offset = l.size * 0.5
	l.scale = Vector2(0.6, 0.6)
	var tw := create_tween().set_parallel()
	tw.tween_property(l, "scale", Vector2.ONE, 0.12).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "position:y", l.position.y - 90, 0.8).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "modulate:a", 0.0, 0.4).set_delay(0.45)
	tw.chain().tween_callback(l.queue_free)


func _hit_flash(sprite: Control) -> void:
	sprite.modulate = Color(1.0, 0.35, 0.35)
	create_tween().tween_property(sprite, "modulate", Color.WHITE, 0.25)


func _lunge(sprite: Control, dir: float) -> void:
	var home: float = sprite.get_meta("home_x")
	var tw := create_tween()
	tw.tween_property(sprite, "position:x", home + 70.0 * dir, 0.1).set_ease(Tween.EASE_OUT)
	tw.tween_property(sprite, "position:x", home, 0.18).set_ease(Tween.EASE_IN_OUT)


func _pulse(sprite: Control) -> void:
	var tw := create_tween()
	tw.tween_property(sprite, "scale", Vector2(1.08, 1.08), 0.1)
	tw.tween_property(sprite, "scale", Vector2.ONE, 0.15)


func _die(view: Dictionary) -> void:
	var root: Control = view["root"]
	var tw := create_tween().set_parallel()
	tw.tween_property(root, "modulate:a", 0.0, 0.5)
	tw.tween_property(root, "position:y", root.position.y + 24, 0.5)


func _shake() -> void:
	var tw := create_tween()
	for i in 5:
		tw.tween_property(_stage, "position", Vector2(randf_range(-10, 10), randf_range(-8, 8)), 0.03)
	tw.tween_property(_stage, "position", Vector2.ZERO, 0.03)


func _idle_bob(sprite: Control, delay: float) -> void:
	var tw := create_tween().set_loops()
	var base_y := sprite.position.y
	tw.tween_interval(delay)
	tw.tween_property(sprite, "position:y", base_y - 6, 0.9).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(sprite, "position:y", base_y, 0.9).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_idle_tweens.append(tw)


func _show_combo(count: int) -> void:
	_combo_label.text = DataDB.t("ui.combo") % count
	_combo_label.reset_size()
	_combo_label.position.x = (_stage.size.x - _combo_label.size.x) * 0.5
	_combo_label.pivot_offset = _combo_label.size * 0.5
	_combo_label.scale = Vector2(0.3, 0.3)
	_combo_label.modulate = Color.WHITE
	_combo_label.rotation = -0.08
	var tw := create_tween()
	tw.tween_property(_combo_label, "scale", Vector2(1.2, 1.2), 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(_combo_label, "scale", Vector2.ONE, 0.1)
	tw.tween_property(_combo_label, "modulate:a", 0.0, 0.5).set_delay(0.7)


func _show_result(ev: Dictionary) -> void:
	if ev["victory"]:
		_result_title.text = DataDB.t("ui.victory")
		_result_title.add_theme_color_override("font_color", UITheme.GOLD)
		_result_body.text = DataDB.t("ui.rewards") % [ev["xp"], ev["gold"]]
		GameState.add_rewards(ev["xp"], ev["gold"])
	else:
		_result_title.text = DataDB.t("ui.defeat")
		_result_title.add_theme_color_override("font_color", UITheme.HP)
		_result_body.text = DataDB.t("ui.defeat_hint")
	_result_layer.visible = true
	_result_layer.modulate.a = 0.0
	create_tween().tween_property(_result_layer, "modulate:a", 1.0, 0.3)


# ---------------------------------------------------------------- layout

func _build_ui() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = UITheme.WOOD_DARK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var col := VBoxContainer.new()
	col.set_anchors_preset(Control.PRESET_FULL_RECT)
	col.add_theme_constant_override("separation", 0)
	add_child(col)

	# ---- stage
	_stage = Control.new()
	_stage.custom_minimum_size.y = STAGE_HEIGHT
	_stage.clip_contents = true
	col.add_child(_stage)
	var bg_tex := TextureRect.new()
	bg_tex.texture = load(DataDB.data["encounters"]["prototype"].get("background", ""))
	bg_tex.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg_tex.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	bg_tex.set_anchors_preset(Control.PRESET_FULL_RECT)
	_stage.add_child(bg_tex)

	var top := HBoxContainer.new()
	top.position = Vector2(20, 24)
	top.size = Vector2(680, 60)
	var turn_badge := PanelContainer.new()
	turn_badge.add_theme_stylebox_override("panel", UITheme.badge())
	_turn_label = UITheme.stage_label(_label(""), 28)
	turn_badge.add_child(_turn_label)
	top.add_child(turn_badge)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(spacer)
	var restart := Button.new()
	restart.text = DataDB.t("ui.restart")
	restart.add_theme_font_size_override("font_size", 22)
	restart.pressed.connect(func() -> void:
		if not busy:
			_new_battle())
	top.add_child(restart)
	_stage.add_child(top)

	_combo_label = UITheme.stage_label(_label(""), 72, UITheme.COMBO)
	_combo_label.add_theme_font_override("font", UITheme.title_font())
	_combo_label.position.y = 190
	_stage.add_child(_combo_label)

	# ---- bottom panel
	var bottom := PanelContainer.new()
	bottom.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var bottom_style := UITheme.panel(UITheme.WOOD, UITheme.GOLD, 0)
	bottom_style.border_width_left = 0
	bottom_style.border_width_right = 0
	bottom_style.border_width_bottom = 0
	bottom_style.border_width_top = 4
	bottom_style.set_content_margin_all(22)
	bottom_style.content_margin_top = 16
	bottom.add_theme_stylebox_override("panel", bottom_style)
	col.add_child(bottom)

	var bcol := VBoxContainer.new()
	bcol.add_theme_constant_override("separation", 12)
	bottom.add_child(bcol)

	var info := HBoxContainer.new()
	info.add_theme_constant_override("separation", 14)
	bcol.add_child(info)
	var name_col := VBoxContainer.new()
	name_col.custom_minimum_size.x = 170
	var name_label := _label(DataDB.t("class." + GameState.active_class))
	name_label.add_theme_font_override("font", UITheme.title_font())
	name_label.add_theme_font_size_override("font_size", 28)
	name_label.add_theme_color_override("font_color", UITheme.GOLD)
	name_col.add_child(name_label)
	var level_label := _label(DataDB.t("ui.level") % 1)
	level_label.add_theme_color_override("font_color", UITheme.TEXT_MUTED)
	level_label.add_theme_font_size_override("font_size", 20)
	name_col.add_child(level_label)
	info.add_child(name_col)
	var bars := VBoxContainer.new()
	bars.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bars.add_theme_constant_override("separation", 6)
	info.add_child(bars)
	var hp := _labeled_bar(UITheme.HP_PLAYER, 30)
	var res := _labeled_bar(UITheme.RAGE, 24)
	bars.add_child(hp[0])
	bars.add_child(res[0])
	var player_statuses := HBoxContainer.new()
	player_statuses.custom_minimum_size.y = 34
	player_statuses.add_theme_constant_override("separation", 10)
	bcol.add_child(player_statuses)
	_player_view = {"hp_bar": hp[1], "hp_label": hp[2], "res_bar": res[1], "res_label": res[2],
			"statuses": player_statuses}

	_log_label = _label("")
	_log_label.add_theme_color_override("font_color", UITheme.TEXT_MUTED)
	_log_label.add_theme_font_size_override("font_size", 20)
	_log_label.clip_text = true
	bcol.add_child(_log_label)

	_skill_grid = GridContainer.new()
	_skill_grid.columns = 2
	_skill_grid.add_theme_constant_override("h_separation", 14)
	_skill_grid.add_theme_constant_override("v_separation", 14)
	bcol.add_child(_skill_grid)

	_defend_button = Button.new()
	_defend_button.text = DataDB.t("ui.defend")
	_defend_button.icon = load("res://assets/icons/intents/shield.png")
	_defend_button.custom_minimum_size.y = 84
	_defend_button.add_theme_font_size_override("font_size", 28)
	_defend_button.pressed.connect(_on_defend_pressed)
	bcol.add_child(_defend_button)

	_build_result_layer()


func _build_result_layer() -> void:
	_result_layer = Control.new()
	_result_layer.set_anchors_preset(Control.PRESET_FULL_RECT)
	_result_layer.mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_result_layer.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_result_layer.add_child(center)
	var panel := PanelContainer.new()
	var style := UITheme.panel(UITheme.WOOD, UITheme.GOLD, 22)
	style.set_content_margin_all(36)
	panel.add_theme_stylebox_override("panel", style)
	panel.custom_minimum_size = Vector2(540, 0)
	center.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 24)
	panel.add_child(v)
	_result_title = UITheme.stage_label(_label(""), 64)
	_result_title.add_theme_font_override("font", UITheme.title_font())
	_result_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_result_title)
	_result_body = _label("")
	_result_body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_result_body.add_theme_font_size_override("font_size", 30)
	v.add_child(_result_body)
	var again := Button.new()
	again.text = DataDB.t("ui.try_again")
	again.custom_minimum_size.y = 84
	again.add_theme_font_size_override("font_size", 30)
	again.pressed.connect(_new_battle)
	v.add_child(again)
	_result_layer.visible = false
	add_child(_result_layer)


func _build_player_view() -> void:
	if _player_view.has("root"):
		_player_view["root"].queue_free()
	var root := Control.new()
	root.position = PLAYER_RECT.position
	root.size = PLAYER_RECT.size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sprite := _sprite(DataDB.data["classes"][GameState.active_class].get("sprite", ""), PLAYER_RECT.size)
	root.add_child(sprite)
	_stage.add_child(root)
	_stage.move_child(root, 1)
	_player_view["root"] = root
	_player_view["sprite"] = sprite


func _build_enemy_views() -> void:
	for tw in _idle_tweens:
		tw.kill()
	_idle_tweens.clear()
	for v in _enemy_views.values():
		v["root"].queue_free()
	_enemy_views.clear()
	_idle_bob(_player_view["sprite"], 0.0)
	var slots: Array = ENEMY_SLOTS[clampi(engine.enemies.size(), 1, 3)]
	for i in engine.enemies.size():
		var e := engine.enemies[i]
		var view := _build_enemy_view(e, slots[i])
		_enemy_views[e.uid] = view
		_idle_bob(view["sprite"], 0.25 * (i + 1))


func _build_enemy_view(e: Combatant, rect: Rect2) -> Dictionary:
	var root := Control.new()
	root.position = rect.position
	root.size = rect.size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(root)
	_stage.move_child(root, 1)

	# selection ring under the feet and a bobbing arrow above the intent badge
	var ring := Panel.new()
	var ring_style := StyleBoxFlat.new()
	ring_style.bg_color = Color(UITheme.COMBO, 0.18)
	ring_style.border_color = UITheme.COMBO
	ring_style.set_border_width_all(4)
	ring_style.set_corner_radius_all(100)
	ring.add_theme_stylebox_override("panel", ring_style)
	ring.position = Vector2(rect.size.x * 0.12, rect.size.y * 0.84)
	ring.size = Vector2(rect.size.x * 0.76, rect.size.y * 0.14)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(ring)

	var sprite := _sprite(DataDB.enemy(e.def_id).get("sprite", ""), rect.size)
	sprite.mouse_filter = Control.MOUSE_FILTER_STOP
	sprite.gui_input.connect(_on_enemy_input.bind(e.uid))
	root.add_child(sprite)

	var intent := PanelContainer.new()
	intent.add_theme_stylebox_override("panel", UITheme.badge())
	intent.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var ih := HBoxContainer.new()
	ih.add_theme_constant_override("separation", 4)
	intent.add_child(ih)
	var intent_icon := TextureRect.new()
	intent_icon.custom_minimum_size = Vector2(38, 38)
	intent_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	intent_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ih.add_child(intent_icon)
	var intent_label := UITheme.stage_label(_label(""), 28, Color("ffb0a0"))
	ih.add_child(intent_label)
	var intent_debuff := TextureRect.new()
	intent_debuff.texture = load("res://assets/icons/intents/debuff.png")
	intent_debuff.custom_minimum_size = Vector2(30, 30)
	intent_debuff.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	intent_debuff.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ih.add_child(intent_debuff)
	intent.position = Vector2(rect.size.x * 0.5 - 50, -34)
	root.add_child(intent)

	var arrow := TextureRect.new()
	arrow.texture = load("res://assets/icons/ui/target.png")
	arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	arrow.position = Vector2(rect.size.x * 0.5 - 24, -76)
	root.add_child(arrow)
	var atw := create_tween().set_loops()
	atw.tween_property(arrow, "position:y", -66.0, 0.45).set_trans(Tween.TRANS_SINE)
	atw.tween_property(arrow, "position:y", -76.0, 0.45).set_trans(Tween.TRANS_SINE)
	_idle_tweens.append(atw)

	var info := VBoxContainer.new()
	info.position = Vector2(0, rect.size.y + 2)
	info.size = Vector2(rect.size.x, 0)
	info.add_theme_constant_override("separation", 2)
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(info)
	var name_label := UITheme.stage_label(_label(DataDB.t(e.name_key)), 22)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info.add_child(name_label)
	var hp := _labeled_bar(UITheme.HP, 22)
	info.add_child(hp[0])
	hp[1].max_value = e.max_hp()
	var statuses := HBoxContainer.new()
	statuses.alignment = BoxContainer.ALIGNMENT_CENTER
	statuses.custom_minimum_size.y = 34
	info.add_child(statuses)

	return {"root": root, "sprite": sprite, "ring": ring, "arrow": arrow, "intent": intent,
			"intent_icon": intent_icon, "intent_label": intent_label, "intent_debuff": intent_debuff,
			"hp_bar": hp[1], "hp_label": hp[2], "statuses": statuses}


func _build_skill_buttons() -> void:
	for child in _skill_grid.get_children():
		child.queue_free()
	_skill_buttons.clear()
	_player_view["hp_bar"].max_value = engine.player.max_hp()
	_player_view["res_bar"].max_value = engine.player.resource_max
	for id in engine.player.skills:
		var def := DataDB.skill(id)
		var b := Button.new()
		b.custom_minimum_size = Vector2(0, 116)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.add_theme_font_size_override("font_size", 24)
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.icon = load(def.get("icon", "res://assets/icons/skills/slash.png"))
		b.expand_icon = false
		b.add_theme_constant_override("icon_max_width", 76)
		b.tooltip_text = DataDB.t(def.get("desc_key", ""))
		b.pressed.connect(_on_skill_pressed.bind(id))
		var glow := Panel.new()
		var gs := StyleBoxFlat.new()
		gs.bg_color = Color(0, 0, 0, 0)
		gs.border_color = UITheme.COMBO
		gs.set_border_width_all(4)
		gs.set_corner_radius_all(18)
		gs.set_expand_margin_all(4)
		gs.shadow_color = Color(UITheme.COMBO, 0.6)
		gs.shadow_size = 10
		glow.add_theme_stylebox_override("panel", gs)
		glow.set_anchors_preset(Control.PRESET_FULL_RECT)
		glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
		glow.visible = false
		b.add_child(glow)
		b.set_meta("glow", glow)
		var gtw := create_tween().set_loops()
		gtw.tween_property(glow, "modulate:a", 0.35, 0.5).set_trans(Tween.TRANS_SINE)
		gtw.tween_property(glow, "modulate:a", 1.0, 0.5).set_trans(Tween.TRANS_SINE)
		_idle_tweens.append(gtw)
		_skill_grid.add_child(b)
		_skill_buttons[id] = b


func _sprite(path: String, rect_size: Vector2) -> TextureRect:
	var t := TextureRect.new()
	t.texture = load(path)
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	t.size = rect_size
	t.pivot_offset = Vector2(rect_size.x * 0.5, rect_size.y)
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	t.set_meta("home_x", 0.0)
	return t


## Returns [container, bar, label]: a progress bar with its value written inside.
func _labeled_bar(color: Color, height: int) -> Array:
	var holder := Control.new()
	holder.custom_minimum_size.y = height
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.set_anchors_preset(Control.PRESET_FULL_RECT)
	bar.add_theme_stylebox_override("fill", UITheme.bar_fill(color))
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(bar)
	var l := UITheme.stage_label(_label(""), int(height * 0.7))
	l.set_anchors_preset(Control.PRESET_FULL_RECT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	holder.add_child(l)
	return [holder, bar, l]


func _label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l

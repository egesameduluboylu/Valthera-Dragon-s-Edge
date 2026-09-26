extends Control
## M1 prototype battle screen: coloured boxes instead of sprites.
## All rules live in CombatEngine; this script only draws state and plays back events.

const EVENT_DELAY := 0.35
const ENEMY_COLORS := {
	"cellar_rat": Color(0.55, 0.38, 0.25),
	"skeleton_guard": Color(0.85, 0.85, 0.78),
	"mushroom_mage": Color(0.55, 0.35, 0.7),
}
const COMBO_COLOR := Color(1.0, 0.8, 0.25)

var engine: CombatEngine
var selected_target: String = ""
var busy: bool = false

var _turn_label: Label
var _combo_label: Label
var _log_label: Label
var _enemy_row: HBoxContainer
var _enemy_views: Dictionary = {}   # uid -> {panel, box, intent, hp_bar, hp_label, status}
var _player_view: Dictionary = {}
var _skill_grid: GridContainer
var _skill_buttons: Dictionary = {} # skill_id -> Button
var _defend_button: Button
var _result_panel: PanelContainer
var _result_label: Label
var _log_lines: Array[String] = []


func _ready() -> void:
	_build_ui()
	_new_battle()


func _new_battle() -> void:
	engine = CombatEngine.from_data(DataDB.data, GameState.active_class, 1, "prototype")
	selected_target = engine.enemies[0].uid
	_log_lines.clear()
	_result_panel.visible = false
	_combo_label.text = ""
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
	if not engine.get_combatant(selected_target) or not engine.get_combatant(selected_target).is_alive():
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
				_enemy_views[uid]["intent"].text = _intent_text(ev["intents"][uid])
			return 0.0
		"skill":
			_log(DataDB.t(DataDB.skill(ev["skill"]).get("name_key", "")))
			return 0.1
		"enemy_move":
			var e := engine.get_combatant(ev["source"])
			_log("%s: %s" % [DataDB.t(e.name_key), _move_label(ev["move_type"])])
			_nudge(_view_of(ev["source"])["box"], 1.0)
			return 0.15
		"damage":
			var view := _view_of(ev["target"])
			view["hp_bar"].value = ev["hp"]
			view["hp_label"].text = "%d / %d" % [ev["hp"], engine.get_combatant(ev["target"]).max_hp()]
			var txt := str(ev["amount"])
			var col := Color.WHITE
			if ev["dot"]:
				col = Color(0.9, 0.4, 0.4)
			if ev["crit"]:
				txt += "!"
				col = Color(1.0, 0.9, 0.2)
			if ev["combo"]:
				col = COMBO_COLOR
			if ev["absorbed"] > 0:
				_float_text(view["box"], "(%d)" % ev["absorbed"], Color(0.6, 0.8, 1.0), -30)
			_float_text(view["box"], txt, col, 0, 44 if ev["crit"] or ev["combo"] else 32)
			_flash(view["box"])
			if ev["target"] == "p":
				_shake()
			return EVENT_DELAY
		"miss":
			_float_text(_view_of(ev["target"])["box"], DataDB.t("ui.miss"), Color(0.7, 0.7, 0.7))
			return EVENT_DELAY
		"death":
			var view: Dictionary = _view_of(ev["target"])
			var box: Control = view.get("panel", view["box"])
			create_tween().tween_property(box, "modulate:a", 0.25, 0.3)
			return 0.2
		"status_applied":
			_float_text(_view_of(ev["target"])["box"], DataDB.t("status." + ev["status"]), Color(0.8, 0.6, 1.0), 40, 22)
			return 0.15
		"immune":
			_float_text(_view_of(ev["target"])["box"], "%s -" % DataDB.t("status." + ev["status"]), Color(0.6, 0.6, 0.6), 40, 22)
			return 0.15
		"shield":
			var sv := _view_of(ev["target"])
			_float_text(sv["box"], "+%d" % ev["amount"], Color(0.5, 0.75, 1.0))
			sv["status"].text = _status_text(engine.get_combatant(ev["target"]))
			return 0.2
		"resource":
			_player_view["res_bar"].value = ev["value"]
			return 0.0
		"skip":
			_float_text(_view_of(ev["target"])["box"], DataDB.t("status.stun"), Color(1.0, 1.0, 0.5))
			_log("%s: %s" % [DataDB.t(engine.get_combatant(ev["target"]).name_key), DataDB.t("ui.skip")])
			return EVENT_DELAY
		"combo":
			_show_combo(ev["count"])
			return 0.25
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
		v["status"].text = _status_text(e)
		v["style"].border_color = COMBO_COLOR if e.uid == selected_target and e.is_alive() else Color(0, 0, 0, 0)
		if not e.is_alive():
			v["intent"].text = ""
	var p := engine.player
	_player_view["hp_bar"].value = p.hp
	_player_view["hp_label"].text = "%d / %d" % [p.hp, p.max_hp()]
	_player_view["res_bar"].value = p.resource
	_player_view["res_label"].text = "%s %d / %d" % [DataDB.t("resource." + p.resource_id), p.resource, p.resource_max]
	_player_view["status"].text = _status_text(p)
	_refresh_buttons()


func _refresh_buttons() -> void:
	var target := engine.get_combatant(selected_target)
	for id in _skill_buttons:
		var b: Button = _skill_buttons[id]
		var def := DataDB.skill(id)
		var reason := engine.skill_block_reason(id)
		var line2 := ""
		if reason == "cooldown":
			line2 = "Bekleme %d" % engine.player.cooldowns[id]
		elif int(def.get("cost", 0)) > 0:
			line2 = "%d %s" % [def["cost"], DataDB.t("resource." + engine.player.resource_id)]
		b.text = DataDB.t(def.get("name_key", id)) + ("\n" + line2 if line2 != "" else "")
		b.disabled = busy or reason != ""
		# Combo hint (docs/08): a finisher glows when the target has what it needs.
		b.modulate = COMBO_COLOR if (not b.disabled and engine.combo_ready(id, target)) else Color.WHITE
	_defend_button.disabled = busy or engine.finished


# ---------------------------------------------------------------- text helpers

func _intent_text(intent: Dictionary) -> String:
	match intent.get("type", ""):
		"attack":
			var s := "%s %d" % [DataDB.t("intent.attack"), intent.get("estimate", 0)]
			return s + " +" + DataDB.t("intent.debuff") if intent.get("debuff", false) else s
		"shield":
			return "%s %d" % [DataDB.t("intent.shield"), intent.get("estimate", 0)]
		"buff_ally":
			return DataDB.t("intent.buff")
		"stunned":
			return DataDB.t("intent.stunned")
	return ""


func _move_label(move_type: String) -> String:
	match move_type:
		"attack":
			return DataDB.t("intent.attack")
		"shield":
			return DataDB.t("intent.shield")
		"buff_ally":
			return DataDB.t("intent.buff")
	return move_type


func _status_text(c: Combatant) -> String:
	var parts: Array[String] = []
	if c.shield > 0:
		parts.append("%s %d" % [DataDB.t("ui.shield"), c.shield])
	for id in c.statuses:
		var s: StatusEffect = c.statuses[id]
		var label := DataDB.t("status." + id)
		parts.append("%s x%d (%d)" % [label, s.stacks, s.turns] if s.stacks > 1 else "%s (%d)" % [label, s.turns])
	return "  ".join(parts)


func _view_of(uid: String) -> Dictionary:
	return _player_view if uid == "p" else _enemy_views[uid]


func _log(line: String) -> void:
	_log_lines.append(line)
	while _log_lines.size() > 4:
		_log_lines.pop_front()
	_log_label.text = "\n".join(_log_lines)


# ---------------------------------------------------------------- juice

func _float_text(anchor: Control, text: String, color: Color, x_offset: float = 0.0, font_size: int = 32) -> void:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", Color.BLACK)
	l.add_theme_constant_override("outline_size", 6)
	add_child(l)
	l.global_position = anchor.global_position + Vector2(anchor.size.x * 0.5 - 20 + x_offset, 10)
	var tw := create_tween().set_parallel()
	tw.tween_property(l, "position:y", l.position.y - 70, 0.7)
	tw.tween_property(l, "modulate:a", 0.0, 0.7).set_delay(0.3)
	tw.chain().tween_callback(l.queue_free)


func _flash(box: Control) -> void:
	box.modulate = Color(3, 3, 3)
	create_tween().tween_property(box, "modulate", Color.WHITE, 0.15)


func _nudge(box: Control, dir: float) -> void:
	var tw := create_tween()
	tw.tween_property(box, "position:y", box.position.y + 18 * dir, 0.08)
	tw.tween_property(box, "position:y", box.position.y, 0.1)


func _shake() -> void:
	var tw := create_tween()
	for i in 4:
		tw.tween_property(self, "position", Vector2(randf_range(-8, 8), randf_range(-8, 8)), 0.025)
	tw.tween_property(self, "position", Vector2.ZERO, 0.025)


func _show_combo(count: int) -> void:
	_combo_label.text = DataDB.t("ui.combo") % count
	_combo_label.pivot_offset = _combo_label.size * 0.5
	_combo_label.scale = Vector2(0.4, 0.4)
	_combo_label.modulate = Color.WHITE
	var tw := create_tween()
	tw.tween_property(_combo_label, "scale", Vector2(1.15, 1.15), 0.15)
	tw.tween_property(_combo_label, "scale", Vector2.ONE, 0.1)
	tw.tween_property(_combo_label, "modulate:a", 0.0, 0.6).set_delay(0.6)


func _show_result(ev: Dictionary) -> void:
	var text := DataDB.t("ui.victory") if ev["victory"] else DataDB.t("ui.defeat")
	if ev["victory"]:
		text += "\n" + DataDB.t("ui.rewards") % [ev["xp"], ev["gold"]]
		GameState.add_rewards(ev["xp"], ev["gold"])
	_result_label.text = text
	_result_panel.visible = true


# ---------------------------------------------------------------- layout

func _build_ui() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.12, 0.1, 0.14)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 24)
	margin.add_theme_constant_override("margin_top", 40)
	margin.add_theme_constant_override("margin_bottom", 32)
	add_child(margin)

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 16)
	margin.add_child(col)

	var top := HBoxContainer.new()
	_turn_label = _label("", 30)
	_turn_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(_turn_label)
	var restart := Button.new()
	restart.text = DataDB.t("ui.restart")
	restart.add_theme_font_size_override("font_size", 26)
	restart.pressed.connect(func() -> void:
		if not busy:
			_new_battle())
	top.add_child(restart)
	col.add_child(top)

	_enemy_row = HBoxContainer.new()
	_enemy_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_enemy_row.add_theme_constant_override("separation", 16)
	_enemy_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(_enemy_row)

	_combo_label = _label("", 56)
	_combo_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_combo_label.add_theme_color_override("font_color", COMBO_COLOR)
	_combo_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_combo_label.add_theme_constant_override("outline_size", 10)
	col.add_child(_combo_label)

	_log_label = _label("", 22)
	_log_label.custom_minimum_size.y = 120
	_log_label.add_theme_color_override("font_color", Color(0.75, 0.75, 0.75))
	col.add_child(_log_label)

	col.add_child(_build_player_view())

	_skill_grid = GridContainer.new()
	_skill_grid.columns = 2
	_skill_grid.add_theme_constant_override("h_separation", 12)
	_skill_grid.add_theme_constant_override("v_separation", 12)
	col.add_child(_skill_grid)

	_defend_button = Button.new()
	_defend_button.text = DataDB.t("ui.defend")
	_defend_button.custom_minimum_size.y = 96
	_defend_button.add_theme_font_size_override("font_size", 30)
	_defend_button.pressed.connect(_on_defend_pressed)
	col.add_child(_defend_button)

	_result_panel = PanelContainer.new()
	_result_panel.set_anchors_preset(Control.PRESET_CENTER)
	_result_panel.custom_minimum_size = Vector2(520, 260)
	_result_panel.position = Vector2(-260, -130)
	_result_label = _label("", 44)
	_result_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_result_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_result_panel.add_child(_result_label)
	_result_panel.visible = false
	add_child(_result_panel)


func _build_enemy_views() -> void:
	for child in _enemy_row.get_children():
		child.queue_free()
	_enemy_views.clear()
	for e in engine.enemies:
		var panel := PanelContainer.new()
		panel.custom_minimum_size = Vector2(200, 0)
		panel.mouse_filter = Control.MOUSE_FILTER_STOP
		panel.gui_input.connect(_on_enemy_input.bind(e.uid))
		var style := StyleBoxFlat.new()
		style.bg_color = Color(0.18, 0.16, 0.2)
		style.set_border_width_all(4)
		style.set_corner_radius_all(8)
		style.set_content_margin_all(8)
		panel.add_theme_stylebox_override("panel", style)
		var v := VBoxContainer.new()
		v.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_theme_constant_override("separation", 6)
		panel.add_child(v)

		var intent := _label("", 24)
		intent.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		intent.add_theme_color_override("font_color", Color(1.0, 0.55, 0.45))
		v.add_child(intent)

		var box := ColorRect.new()
		box.color = ENEMY_COLORS.get(e.def_id, Color(0.6, 0.2, 0.2))
		box.custom_minimum_size = Vector2(150, 150)
		box.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_child(box)

		var name_label := _label(DataDB.t(e.name_key), 22)
		name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(name_label)
		var hp_bar := _bar(e.max_hp(), Color(0.8, 0.2, 0.2))
		v.add_child(hp_bar)
		var hp_label := _label("", 20)
		hp_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(hp_label)
		var status := _label("", 18)
		status.autowrap_mode = TextServer.AUTOWRAP_WORD
		status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(status)

		_enemy_row.add_child(panel)
		_enemy_views[e.uid] = {"panel": panel, "style": style, "box": box, "intent": intent,
				"hp_bar": hp_bar, "hp_label": hp_label, "status": status}


func _build_player_view() -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	var box := ColorRect.new()
	box.color = Color(0.3, 0.5, 0.85)
	box.custom_minimum_size = Vector2(90, 90)
	row.add_child(box)
	var bars := VBoxContainer.new()
	bars.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bars.add_child(_label(DataDB.t("class." + GameState.active_class), 24))
	var hp_bar := _bar(100, Color(0.25, 0.75, 0.3))
	bars.add_child(hp_bar)
	var hp_label := _label("", 20)
	bars.add_child(hp_label)
	var res_bar := _bar(100, Color(0.9, 0.5, 0.15))
	bars.add_child(res_bar)
	var res_label := _label("", 20)
	bars.add_child(res_label)
	row.add_child(bars)
	v.add_child(row)
	var status := _label("", 20)
	v.add_child(status)
	_player_view = {"box": box, "hp_bar": hp_bar, "hp_label": hp_label,
			"res_bar": res_bar, "res_label": res_label, "status": status}
	return v


func _build_skill_buttons() -> void:
	for child in _skill_grid.get_children():
		child.queue_free()
	_skill_buttons.clear()
	_player_view["hp_bar"].max_value = engine.player.max_hp()
	_player_view["res_bar"].max_value = engine.player.resource_max
	for id in engine.player.skills:
		var b := Button.new()
		b.custom_minimum_size = Vector2(0, 110)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.add_theme_font_size_override("font_size", 26)
		b.tooltip_text = DataDB.t(DataDB.skill(id).get("desc_key", ""))
		b.pressed.connect(_on_skill_pressed.bind(id))
		_skill_grid.add_child(b)
		_skill_buttons[id] = b


func _label(text: String, font_size: int) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _bar(max_value: int, color: Color) -> ProgressBar:
	var b := ProgressBar.new()
	b.max_value = max_value
	b.value = max_value
	b.show_percentage = false
	b.custom_minimum_size.y = 18
	b.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fill := StyleBoxFlat.new()
	fill.bg_color = color
	b.add_theme_stylebox_override("fill", fill)
	return b

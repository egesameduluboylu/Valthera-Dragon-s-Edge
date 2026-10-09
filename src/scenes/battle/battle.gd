extends Control
## Battle screen. All rules live in CombatEngine; this script draws state and plays
## the engine's events back as animations (docs/08, docs/10).
##
## Standalone it runs the "prototype" encounter. Inside a dungeon run the map scene
## calls setup() with a prepared engine and waits for `finished`.

signal finished(engine: CombatEngine)

const EVENT_DELAY := 0.35
## Landscape stage (docs/16): the fighters stand on this line; the HUD covers the screen
## below HUD_TOP. X positions are fractions of the stage width, so wider phones spread out.
const GROUND := 532.0
const HUD_TOP := 560.0
const HERO := {"x": 0.235, "y": 0.0, "box": Vector2(300, 330)}
## The companion dragon (docs/15) hovers behind the hero, above their shoulder.
const DRAGON := {"x": 0.1, "y": -70.0, "box": Vector2(190, 180)}
## Enemy feet [x fraction, y offset] and figure box for 1, 2 and 3 enemies.
const ENEMY_SLOTS := {
	1: [[0.74, 0.0]],
	2: [[0.635, 6.0], [0.855, -8.0]],
	3: [[0.575, 12.0], [0.735, -22.0], [0.895, 12.0]],
}
const ENEMY_BOX := {1: Vector2(340, 350), 2: Vector2(280, 300), 3: Vector2(220, 240)}
## With a boss on the field: the boss on the right, up to two adds in front of it.
const BOSS := [0.77, 8.0]
const BOSS_BOX := Vector2(480, 460)
const BOSS_ADDS := [[0.555, 14.0], [0.585, -60.0]]
const ADD_BOX := Vector2(180, 190)

var engine: CombatEngine
var selected_target: String = ""
var busy: bool = false
## True when a dungeon run owns this battle (no restart, rewards handled by the run).
var run_mode: bool = false
var background: String = ""

var _stage: Control
var _stage_size := Vector2(1280, 720)
var _viewport: SubViewport
var _backdrop: Backdrop
var _fx: Control                    # effects drawn over the fighters
var _plate: Dictionary = {}         # the HUD's target nameplate: root, portrait, name, hp_bar, hp_label, level
var _turn_label: Label
var _combo_label: Label
var _log_label: Label
var _enemy_views: Dictionary = {}   # uid -> view dictionary, see _build_enemy_view
var _player_view: Dictionary = {}
var _dragon_view: Dictionary = {}  # root, sprite, pips (Array of Panel)
var _skill_grid: Control
var _skill_buttons: Dictionary = {} # skill_id -> Button
var _defend_button: Button
var _potion_button: Button
var _level_label: Label
var _restart_button: Button
var _result_button: Button
var _flash: ColorRect
var _result_layer: Control
var _result_title: Label
var _result_body: Label
var _log_lines: Array[String] = []
var _last_skill := ""
var _idle_tweens: Array[Tween] = []


## Call before adding the scene to the tree to play a battle prepared elsewhere.
func setup(p_engine: CombatEngine, p_background: String) -> void:
	engine = p_engine
	background = p_background
	run_mode = true


func _ready() -> void:
	# battle speed setting: timers and tweens all follow the engine's time scale
	Engine.time_scale = Settings.battle_speed
	theme = UITheme.build()
	if background == "":
		background = DataDB.data["encounters"]["prototype"].get("background", "")
	_build_ui()
	if run_mode:
		_start_battle()
	else:
		_new_battle()


func _exit_tree() -> void:
	Engine.time_scale = 1.0


func _new_battle() -> void:
	engine = CombatEngine.from_data(DataDB.data, GameState.active_class, GameState.level(), "prototype")
	_start_battle()


func _start_battle() -> void:
	var boss := engine.enemies.any(func(e: Combatant) -> bool: return e.is_boss)
	Audio.music("boss" if boss else "battle")
	selected_target = engine.alive_enemies()[0].uid
	_restart_button.visible = not run_mode
	_level_label.text = str(engine.player.level)
	_log_lines.clear()
	_log_label.text = ""
	_result_layer.visible = false
	_combo_label.modulate.a = 0.0
	_build_player_view()
	_build_dragon_view()
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


func _on_potion_pressed() -> void:
	if busy:
		return
	_play(engine.use_potion())


func _on_result_pressed() -> void:
	if run_mode:
		finished.emit(engine)
	else:
		_new_battle()


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
	_refresh()
	await _coach()
	busy = false
	_refresh()


# ---------------------------------------------------------------- tutorial

## Shows the first-battle hints that fit this moment, one after another (docs/09).
func _coach() -> void:
	if engine.finished or GameState.profile == null:
		return
	var hint := _next_hint()
	while not hint.is_empty():
		GameState.profile.take_story(hint[0])
		GameState.save()
		var t := Tutorial.new(hint[0], hint[1])
		add_child(t)
		await t.finished
		hint = _next_hint()


## [hint id, control to frame] for the next unseen hint that applies now, or [].
func _next_hint() -> Array:
	var seen: Array = GameState.profile.story_seen
	var want := func(id: String) -> bool: return not seen.has(id)
	if want.call("tut_intent"):
		for e in engine.alive_enemies():
			var view: Dictionary = _enemy_views.get(e.uid, {})
			if not view.is_empty() and view["intent"].visible:
				return ["tut_intent", view["intent"]]
	if want.call("tut_skills"):
		return ["tut_skills", _skill_grid]
	if want.call("tut_dragon") and not _dragon_view.is_empty():
		return ["tut_dragon", _dragon_view["root"]]
	var class_hint := "tut_class_" + engine.player.def_id
	if want.call(class_hint) and Tutorial.FLAGS.has(class_hint):
		return [class_hint, _player_view["res_bar"]]
	if want.call("tut_combo"):
		# buttons are still disabled here (busy), so ask the engine instead of the glow
		var target := engine.get_combatant(selected_target)
		for id in _skill_buttons:
			if engine.skill_block_reason(id) == "" and engine.combo_ready(id, target):
				return ["tut_combo", _skill_buttons[id]]
	if want.call("tut_defend") and engine.player.hp * 2 < engine.player.max_hp():
		return ["tut_defend", _defend_button.get_parent()]
	return []


## Sound and vibration for one event (docs/09).
func _sfx(ev: Dictionary) -> void:
	match ev["type"]:
		"skill":
			var def := DataDB.skill(ev["skill"])
			var element: String = def.get("element", "physical")
			if def.get("target", "") == "self":
				Audio.play("smoke" if ev["skill"] == "rogue_smoke_bomb" else "shield")
			elif element == "physical":
				Audio.play("stab" if engine.player.def_id == "rogue" else "slash")
			else:
				Audio.play("magic_" + element)
		"enemy_move":
			if ev["move_type"] in ["attack", "multi_attack"]:
				Audio.play("enemy_attack")
		"damage":
			if ev["dot"]:
				return
			if ev["target"] == "p":
				Audio.play("player_hurt")
				Audio.vibrate(60 if ev["crit"] else 35)
			else:
				Audio.play("crit" if ev["crit"] else "hit")
		"miss":
			Audio.play("miss")
		"death":
			if ev["target"] != "p":
				Audio.play("enemy_death")
		"status_applied":
			if ev["status"] == "stun":
				Audio.play("stun")
			elif ev["status"] == "poison":
				Audio.play("poison")
			elif ev["target"] == "p":
				Audio.play("status_bad")
		"heal":
			if ev["amount"] > 0:
				Audio.play("heal")
		"item":
			Audio.play("potion")
		"summon":
			Audio.play("summon")
		"phase":
			Audio.play("boss_phase", 0.0)
			Audio.vibrate(250)
		"combo":
			Audio.play("combo", 0.0)
			Audio.vibrate(50)
		"flurry":
			Audio.play("star")
		"companion_breath":
			Audio.play({"fire": "magic_fire", "frost": "magic_ice", "venom": "poison"}.get(ev["element"], "magic_fire"), 0.0)
			Audio.vibrate(45)
		"battle_end":
			Audio.play("victory" if ev["victory"] else "defeat", 0.0)


## Draws one event and returns how long to pause after it.
func _apply_event(ev: Dictionary) -> float:
	_sfx(ev)
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
			return _player_skill_fx(ev["skill"])
		"enemy_move":
			var e := engine.get_combatant(ev["source"])
			var view: Dictionary = _enemy_views[ev["source"]]
			view["intent"].visible = false
			_log("%s: %s" % [DataDB.t(e.name_key), _move_label(ev["move_type"])])
			var pup := _puppet(view)
			if ev["move_type"] in ["attack", "multi_attack"]:
				if pup != null:
					pup.play("attack")
					return 0.3
				_lunge(view["sprite"], -1.0)
			elif pup != null:
				pup.play("cast")
				BattleFx.flash(_fx, _body_center(view), Color(1.8, 1.2, 2.2, 0.8), 80.0, 0.45)
			else:
				_pulse(view["sprite"])
			return 0.2
		"damage":
			var view := _view_of(ev["target"])
			var c := engine.get_combatant(ev["target"])
			view["hp_bar"].value = ev["hp"]
			view["hp_label"].text = "%d / %d" % [ev["hp"], c.max_hp()]
			_refresh_plate()
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
			if not ev["dot"]:
				var element := "physical"
				var melee := true
				if ev["target"] != "p" and ev["source"] == "p" and _last_skill != "":
					element = DataDB.skill(_last_skill).get("element", "physical")
					melee = element == "physical"
				elif ev["source"] == Companion.UID and engine.companion != null:
					element = DataDB.data["companion"]["elements"][engine.companion.def_id].get("damage_element", "fire")
					melee = false
				BattleFx.impact(_fx, _body_center(view), element, ev["crit"], melee)
			var pup := _puppet(view)
			if pup != null:
				pup.play("hit")
			if ev["target"] == "p" or ev["crit"]:
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
				var pup := _puppet(view)
				if pup != null:
					pup.play("defend")
				BattleFx.flash(_fx, _body_center(view), Color(0.9, 1.5, 2.4, 0.9), 110.0, 0.5)
				return 0.2
			return 0.0
		"immune":
			_float_text(_view_of(ev["target"]), "%s -" % DataDB.t("status." + ev["status"]), Color("a0a0a0"), 28, 60)
			return 0.15
		"resist":
			_float_text(_view_of(ev["target"]), DataDB.t("battle.resist"), Color("a0a0a0"), 32, 60)
			return 0.2
		"flurry":
			# Rogue "Seri": the turn goes on, so say so before the player picks again.
			_show_banner(DataDB.t("battle.flurry"), Color("ffd35a"), 44, UITheme.body_font())
			return 0.25
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
		"heal":
			var view := _view_of(ev["target"])
			var c := engine.get_combatant(ev["target"])
			view["hp_bar"].value = ev["hp"]
			view["hp_label"].text = "%d / %d" % [ev["hp"], c.max_hp()]
			if ev["amount"] > 0:
				_float_text(view, "+%d" % ev["amount"], Color("7dff8a"), 40)
			return 0.3
		"item":
			_log(DataDB.t("item." + ev["item"]))
			_pulse(_player_view["sprite"])
			_refresh_buttons()
			return 0.15
		"summon":
			var add := engine.get_combatant(ev["uid"])
			_enemy_views[add.uid] = _build_enemy_view(add, Rect2())
			_layout_enemies(true)
			_pulse(_enemy_views[ev["source"]]["sprite"])
			_log("%s: %s" % [DataDB.t(engine.get_combatant(ev["source"]).name_key), DataDB.t("intent.summon")])
			return 0.45
		"phase":
			_fill_status_row(_enemy_views[ev["source"]]["statuses"], engine.get_combatant(ev["source"]))
			_screen_flash(Color(1, 0.1, 0.1, 0.45))
			_shake()
			if ev["line_key"] != "":
				# Body font: Cinzel has no dotted capital İ for Turkish lines.
				_show_banner(DataDB.t(ev["line_key"]), Color("ff7060"), 40, UITheme.body_font())
			return 1.1
		"companion_charge":
			_paint_pips(ev["charge"])
			if ev["charge"] > 0 and not _dragon_view.is_empty():
				_pulse(_dragon_view["pips"][ev["charge"] - 1])
				return 0.12
			return 0.0
		"companion_breath":
			var color := Color(DataDB.data["companion"]["elements"][ev["element"]].get("color", "#ffcc66"))
			_paint_pips(engine.companion_charge_needed())
			var dpup := _puppet(_dragon_view)
			if dpup != null:
				dpup.play("attack")
			else:
				_lunge(_dragon_view["sprite"], 1.0)
			var mouth := _body_center(_dragon_view) + Vector2(60, -30)
			var aim := Vector2(_stage_size.x * 0.74, GROUND - 150)
			BattleFx.breath(_fx, mouth, aim, Color(color * 2.2, 1.0), 0.55)
			_screen_flash(Color(color, 0.4))
			_show_banner(DataDB.tf("dragon.breath_banner", {"name": DataDB.dragon_name(GameState.profile.companion)}),
					color.lightened(0.3), 46, UITheme.body_font())
			_log(DataDB.t("dragon.breath_log"))
			return 0.45
		"battle_end":
			_show_result(ev)
			return 0.0
	return 0.0


# ---------------------------------------------------------------- refresh

func _refresh() -> void:
	for e in engine.enemies:
		if not _enemy_views.has(e.uid):
			continue
		var v: Dictionary = _enemy_views[e.uid]
		v["hp_bar"].value = e.hp
		v["hp_label"].text = "%d / %d" % [e.hp, e.max_hp()]
		_fill_status_row(v["statuses"], e)
		var selected := e.uid == selected_target and e.is_alive()
		v["ring"].visible = selected
		v["arrow"].visible = selected
		if e.is_alive() and not e.intent.is_empty():
			_set_intent(v, e.intent)
	_refresh_plate()
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
		var cost := engine.skill_cost(id)
		b.disabled = busy or reason != ""
		if b.has_meta("ribbon"):
			var line := DataDB.t(def.get("name_key", id))
			if reason == "cooldown":
				line += "  " + DataDB.t("ui.cooldown") % engine.player.cooldowns[id]
			elif cost > 0:
				line += "  %d" % cost
			b.text = line
			# long names with a cost or cooldown get a smaller font so the banner never clips them
			b.add_theme_font_size_override("font_size", UITheme.fs(20 if line.length() <= 13 else (18 if line.length() <= 17 else 16)))
		else:
			var cd: Label = b.get_meta("cd")
			cd.text = str(engine.player.cooldowns[id]) if reason == "cooldown" else ""
			b.get_meta("shade").visible = reason != ""
			b.get_meta("cost").text = str(cost) if cost > 0 else ""
		# Combo hint (docs/08): a finisher glows when the target has what it needs.
		var ready := not b.disabled and engine.combo_ready(id, target)
		b.modulate = Color(1.08, 1.04, 0.92) if ready else Color.WHITE
		b.get_meta("glow").visible = ready
	_defend_button.disabled = busy or engine.finished
	# Mid-Flurry the defend button ends the turn instead (no defend bonus).
	_defend_button.get_meta("caption").text = DataDB.t("ui.end_turn") if engine.in_flurry() else DataDB.t("ui.defend")
	_defend_button.tooltip_text = _defend_button.get_meta("caption").text
	_potion_button.get_meta("caption").text = "%s x%d" % [DataDB.t("ui.potion"), engine.potions]
	_potion_button.disabled = busy or engine.finished or engine.potions <= 0 \
			or engine.player.hp >= engine.player.max_hp()
	_potion_button.get_meta("icon").modulate = Color(1, 1, 1, 0.45 if _potion_button.disabled else 1.0)


## The HUD nameplate follows the selected enemy.
func _refresh_plate() -> void:
	var e := engine.get_combatant(selected_target)
	var root: Control = _plate["root"]
	root.visible = e != null and e.is_alive()
	if not root.visible:
		return
	if _plate["uid"] != e.uid:
		_plate["uid"] = e.uid
		_plate["name"].text = DataDB.t(e.name_key)
		_set_portrait(_plate["portrait"], DataDB.enemy(e.def_id).get("sprite", ""), e.def_id)
		_plate["level"].text = str(e.level)
	_plate["hp_bar"].max_value = e.max_hp()
	_plate["hp_bar"].value = e.hp
	_plate["hp_label"].text = "%d / %d" % [e.hp, e.max_hp()]


func _set_intent(view: Dictionary, intent: Dictionary) -> void:
	var type: String = intent.get("type", "")
	var icon := type
	var text := ""
	var color := Color("ffb0a0")
	match type:
		"attack":
			text = str(intent.get("estimate", 0))
			if int(intent.get("hits", 1)) > 1:
				text += "x%d" % intent["hits"]
			if intent.get("heavy", false):
				text += "!"
				color = Color("ff5a4a")
		"shield":
			text = str(intent.get("estimate", 0))
		"buff_ally":
			icon = "buff"
	view["intent_icon"].texture = load("res://assets/icons/intents/%s.png" % icon)
	view["intent_label"].text = text
	view["intent_label"].add_theme_color_override("font_color", color)
	view["intent_label"].visible = text != ""
	view["intent_debuff"].visible = intent.get("debuff", false)
	view["intent"].visible = type != ""


func _fill_status_row(row: HBoxContainer, c: Combatant) -> void:
	for child in row.get_children():
		child.queue_free()
	if c.shield > 0:
		row.add_child(_status_chip("shield_status", str(c.shield), "ui.shield"))
	for id in c.statuses:
		var s: StatusEffect = c.statuses[id]
		# Stacked effects show both the stacks and the turns left, e.g. "x2·4". Boss rage
		# and similar lasting effects (90+ turns) show no timer.
		var turns := str(s.turns) if s.turns < 90 else ""
		var text := turns
		if s.stacks > 1:
			text = "x%d·%s" % [s.stacks, turns] if turns != "" else "x%d" % s.stacks
		row.add_child(_status_chip(id, text, "status." + id))


func _status_chip(icon_id: String, text: String, tooltip_key: String) -> Control:
	var box := HBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var icon := TextureRect.new()
	icon.texture = load("res://assets/icons/statuses/%s.png" % icon_id)
	icon.custom_minimum_size = Vector2(34, 34)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.tooltip_text = DataDB.t(tooltip_key)
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
		"multi_attack":
			return DataDB.t("intent.attack")
		"summon":
			return DataDB.t("intent.summon")
	return move_type


func _view_of(uid: String) -> Dictionary:
	return _player_view if uid == "p" else _enemy_views[uid]


func _log(line: String) -> void:
	_log_lines.append(line)
	while _log_lines.size() > 2:
		_log_lines.pop_front()
	_log_label.text = "  •  ".join(_log_lines)


# ---------------------------------------------------------------- juice

## The hero's move for a skill: a swing for weapon skills, a cast with flying spells for
## magic, a guard for self skills. Returns how long to wait before the hits land.
func _player_skill_fx(skill_id: String) -> float:
	_last_skill = skill_id
	var def := DataDB.skill(skill_id)
	var element: String = def.get("element", "physical")
	var target: String = def.get("target", "single_enemy")
	var pup := _puppet(_player_view)
	if target == "self":
		if pup != null:
			pup.play("cast")
		BattleFx.flash(_fx, _body_center(_player_view), Color(BattleFx.color("holy"), 0.8), 120.0, 0.5)
		return 0.25
	if element == "physical":
		if pup == null:
			_lunge(_player_view["sprite"], 1.0)
			return 0.15
		pup.play("attack")
		return 0.3
	if pup != null:
		pup.play("cast")
	var from := _body_center(_player_view) + Vector2(80, -50)
	var views: Array = []
	if target in ["all_enemies", "random_enemies"]:
		for e in engine.alive_enemies():
			if _enemy_views.has(e.uid):
				views.append(_enemy_views[e.uid])
	elif _enemy_views.has(selected_target):
		views.append(_enemy_views[selected_target])
	var col := BattleFx.color(element)
	for v in views:
		BattleFx.projectile(_fx, from, _body_center(v), col, 0.3)
	BattleFx.flash(_fx, from, Color(col, 0.9), 50.0, 0.3)
	return 0.42


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
	# above 1.0 the stage's bloom makes the hit flare
	sprite.modulate = Color(2.4, 1.2, 1.1) if Settings.effects else Color(1.0, 0.35, 0.35)
	create_tween().tween_property(sprite, "modulate", Color.WHITE, 0.3)


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
	var pup := _puppet(view)
	var tw := create_tween().set_parallel()
	if pup != null:
		pup.play("die")
		BattleFx.burst(_fx, _body_center(view), Color(1.3, 1.1, 1.0, 0.8), 30, 220.0, 16.0, 0.9, -80.0)
		tw.tween_property(root, "modulate:a", 0.0, 0.7).set_delay(0.2)
		tw.tween_property(root, "position:y", root.position.y + 30, 0.9).set_delay(0.1)
		return
	tw.tween_property(root, "modulate:a", 0.0, 0.5)
	tw.tween_property(root, "position:y", root.position.y + 24, 0.5)


func _shake() -> void:
	var tw := create_tween()
	for i in 5:
		tw.tween_property(_stage, "position", Vector2(randf_range(-10, 10), randf_range(-8, 8)), 0.03)
	tw.tween_property(_stage, "position", Vector2.ZERO, 0.03)


## Bound to the sprite, so the loop dies with it when a view is rebuilt.
func _idle_bob(sprite: Control, delay: float) -> void:
	if sprite.has_meta("puppet"):
		return  # puppets breathe on their own
	var tw := sprite.create_tween().set_loops()
	var base_y := sprite.position.y
	tw.tween_interval(delay)
	tw.tween_property(sprite, "position:y", base_y - 6, 0.9).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(sprite, "position:y", base_y, 0.9).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_idle_tweens.append(tw)


func _show_combo(count: int) -> void:
	_show_banner(DataDB.t("ui.combo") % count, UITheme.COMBO, 72, UITheme.title_font())


func _show_banner(text: String, color: Color, font_size: int, font: Font) -> void:
	_combo_label.text = text
	_combo_label.add_theme_font_override("font", font)
	_combo_label.add_theme_color_override("font_color", color)
	_combo_label.add_theme_font_size_override("font_size", UITheme.fs(font_size))
	_combo_label.size = Vector2.ZERO
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


func _screen_flash(color: Color) -> void:
	_flash.color = color
	_flash.visible = true
	var tw := create_tween()
	tw.tween_property(_flash, "color:a", 0.0, 0.6)
	tw.tween_callback(func() -> void: _flash.visible = false)


func _show_result(ev: Dictionary) -> void:
	if ev["victory"]:
		_result_title.text = DataDB.t("ui.victory")
		_result_title.add_theme_color_override("font_color", UITheme.GOLD)
		_result_body.text = DataDB.t("ui.rewards") % [ev["xp"], ev["gold"]]
		if not run_mode:
			GameState.add_rewards(ev["xp"], ev["gold"])
	else:
		_result_title.text = DataDB.t("ui.defeat")
		_result_title.add_theme_color_override("font_color", UITheme.HP)
		_result_body.text = DataDB.t("ui.defeat_hint")
	_result_button.text = DataDB.t("ui.continue") if run_mode else DataDB.t("ui.try_again")
	_result_layer.visible = true
	_result_layer.modulate.a = 0.0
	create_tween().tween_property(_result_layer, "modulate:a", 1.0, 0.3)


# ---------------------------------------------------------------- layout

func _build_ui() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_stage_size = get_viewport_rect().size
	var bg := ColorRect.new()
	bg.color = Color("0c0a0d")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# ---- stage: an HDR viewport with bloom, so fire, magic and glows really shine
	var holder := SubViewportContainer.new()
	holder.stretch = true
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	holder.size = _stage_size
	add_child(holder)
	_viewport = SubViewport.new()
	_viewport.use_hdr_2d = Settings.effects
	_viewport.handle_input_locally = true
	_viewport.size = _stage_size
	holder.add_child(_viewport)
	if Settings.effects:
		var env := Environment.new()
		env.background_mode = Environment.BG_CANVAS
		env.glow_enabled = true
		env.glow_intensity = 0.75
		env.glow_strength = 1.0
		env.glow_hdr_threshold = 1.0
		env.glow_blend_mode = Environment.GLOW_BLEND_MODE_ADDITIVE
		for level in 7:
			env.set_glow_level(level, 1.0 if level in [1, 3, 5] else 0.0)
		var we := WorldEnvironment.new()
		we.environment = env
		_viewport.add_child(we)

	_stage = Control.new()
	_stage.size = _stage_size
	_stage.mouse_filter = Control.MOUSE_FILTER_PASS
	_viewport.add_child(_stage)
	_backdrop = Backdrop.new()
	_backdrop.density = 1.0 if Settings.effects else 0.4
	_backdrop.setup(_backdrop_dir(), background, _stage_size, GROUND)
	_stage.add_child(_backdrop)
	_fx = Control.new()
	_fx.size = _stage_size
	_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fx.z_index = 20
	_stage.add_child(_fx)

	var top := HBoxContainer.new()
	top.position = Vector2(16, 12)
	top.size = Vector2(_stage_size.x - 32, 50)
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.z_index = 30
	var turn_badge := PanelContainer.new()
	turn_badge.add_theme_stylebox_override("panel", UITheme.v2_box("turn_badge", [26, 6, 26, 8], UITheme.badge(), 0.5))
	_turn_label = UITheme.stage_label(_label(""), 24, UITheme.GOLD)
	_turn_label.add_theme_font_override("font", UITheme.title_font())
	turn_badge.add_child(_turn_label)
	top.add_child(turn_badge)
	_log_label = UITheme.stage_label(_label(""), 20, Color("e8dcc4"))
	_log_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_log_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_log_label.clip_text = true
	top.add_child(_log_label)
	_restart_button = Button.new()
	_restart_button.text = DataDB.t("ui.restart")
	_restart_button.add_theme_font_size_override("font_size", UITheme.fs(20))
	_restart_button.pressed.connect(func() -> void:
		if not busy:
			_new_battle())
	top.add_child(_restart_button)
	_stage.add_child(top)

	_combo_label = UITheme.stage_label(_label(""), 72, UITheme.COMBO)
	_combo_label.add_theme_font_override("font", UITheme.title_font())
	_combo_label.position.y = 130
	_combo_label.z_index = 30
	_stage.add_child(_combo_label)

	_flash = ColorRect.new()
	_flash.size = _stage_size
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_flash.visible = false
	_flash.z_index = 25
	_stage.add_child(_flash)

	_build_hud()
	_build_result_layer()


func _backdrop_dir() -> String:
	# res://assets/backgrounds/rotten_cellar.png -> res://assets/backgrounds/v2/rotten_cellar
	if background == "":
		return ""
	return background.get_base_dir().path_join("v2").path_join(background.get_file().get_basename())


## The bottom bar (docs/16): portrait medallion and bars on the left, the attack ribbon and
## skill slots in the middle, the target's nameplate, Defend and Potion on the right.
func _build_hud() -> void:
	var w := _stage_size.x
	var hud := Control.new()
	hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(hud)
	var bar := Panel.new()
	var fallback := UITheme.slate(0, 0, Color(0.07, 0.065, 0.08, 0.97))
	fallback.border_width_top = 3
	bar.add_theme_stylebox_override("panel", UITheme.v2_box("hud_bar", [0, 0, 0, 0], fallback))
	bar.position = Vector2(0, HUD_TOP)
	bar.size = Vector2(w, _stage_size.y - HUD_TOP)
	bar.mouse_filter = Control.MOUSE_FILTER_STOP
	hud.add_child(bar)

	# ---- player: medallion, name, statuses, bars
	var cls: String = GameState.active_class
	var medallion := _medallion(150, DataDB.data["classes"][cls].get("sprite", ""), cls, false)
	medallion["root"].position = Vector2(12, HUD_TOP - 12)
	hud.add_child(medallion["root"])
	_level_label = medallion["level"]
	var info := VBoxContainer.new()
	info.position = Vector2(172, HUD_TOP + 20)
	info.size = Vector2(clampf(w * 0.2, 240.0, 320.0), 140)
	info.add_theme_constant_override("separation", 5)
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(info)
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 10)
	name_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_child(name_row)
	var name_label := _label(UITheme.caps(DataDB.t("class." + cls)))
	name_label.add_theme_font_override("font", UITheme.title_font())
	name_label.add_theme_font_size_override("font_size", UITheme.fs(22))
	name_label.add_theme_color_override("font_color", UITheme.GOLD)
	name_row.add_child(name_label)
	var player_statuses := HBoxContainer.new()
	player_statuses.custom_minimum_size.y = 30
	player_statuses.add_theme_constant_override("separation", 6)
	name_row.add_child(player_statuses)
	var hp := _labeled_bar(UITheme.HP, 30, "hp")
	var res_color := Color(DataDB.data["classes"][cls].get("resource_color", "#c8412f"))
	var res := _labeled_bar(res_color, 24, {"warrior": "rage", "mage": "mana", "rogue": "energy"}.get(cls, "mana"))
	info.add_child(hp[0])
	info.add_child(res[0])
	_player_view = {"hp_bar": hp[1], "hp_label": hp[2], "res_bar": res[1], "res_label": res[2],
			"statuses": player_statuses}

	# ---- skills: the first skill is the big attack ribbon, the rest are numbered slots
	# (as in the reference: the red attack banner, then the numbered squares, all in the bar)
	_skill_grid = Control.new()
	var grid_x := info.position.x + info.size.x + 14
	_skill_grid.position = Vector2(grid_x, HUD_TOP + 24)
	_skill_grid.size = Vector2(w - 190 - grid_x, _stage_size.y - HUD_TOP - 14)
	_skill_grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(_skill_grid)

	# ---- right: target nameplate, Defend and Potion
	var right := w - 16
	_plate = _nameplate()
	_plate["root"].position = Vector2(right - 430, HUD_TOP - 50)
	hud.add_child(_plate["root"])
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 10)
	actions.alignment = BoxContainer.ALIGNMENT_END
	actions.position = Vector2(right - 170, HUD_TOP + 22)
	actions.size = Vector2(170, 120)
	hud.add_child(actions)
	_defend_button = _round_button("icon_defend", "res://assets/icons/intents/shield.png")
	_defend_button.pressed.connect(_on_defend_pressed)
	actions.add_child(_defend_button.get_meta("box"))
	_potion_button = _round_button("icon_potion", "res://assets/icons/items/potion.png")
	_potion_button.pressed.connect(_on_potion_pressed)
	actions.add_child(_potion_button.get_meta("box"))


## A round portrait in a gold frame with a level badge. Returns {root, portrait, level}.
func _medallion(px: int, flat: String, rig_id: String, mirror: bool) -> Dictionary:
	var root := Control.new()
	root.custom_minimum_size = Vector2(px, px)
	root.size = Vector2(px, px)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var portrait := TextureRect.new()
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_SCALE
	portrait.position = Vector2(px, px) * 0.1
	portrait.size = Vector2(px, px) * 0.8
	portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var mat := ShaderMaterial.new()
	mat.shader = load("res://src/ui/fx/portrait.gdshader")
	mat.set_shader_parameter("mirror", mirror)
	portrait.material = mat
	root.add_child(portrait)
	_set_portrait(portrait, flat, rig_id)
	var frame := TextureRect.new()
	var frame_tex := UITheme.v2("portrait_frame")
	if frame_tex != null:
		frame.texture = frame_tex
		frame.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		frame.stretch_mode = TextureRect.STRETCH_SCALE
		frame.size = Vector2(px, px)
	else:
		var ring := Panel.new()
		var st := StyleBoxFlat.new()
		st.bg_color = Color(0, 0, 0, 0)
		st.border_color = UITheme.GOLD
		st.set_border_width_all(maxi(4, px / 22))
		st.set_corner_radius_all(px)
		st.shadow_color = Color(0, 0, 0, 0.6)
		st.shadow_size = 6
		ring.add_theme_stylebox_override("panel", st)
		ring.position = portrait.position - Vector2(3, 3)
		ring.size = portrait.size + Vector2(6, 6)
		ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(ring)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(frame)
	var badge := PanelContainer.new()
	var badge_px := px * 0.3
	var badge_tex := UITheme.v2("level_badge")
	var bst: StyleBox
	if badge_tex != null:
		var t := StyleBoxTexture.new()
		t.texture = badge_tex
		bst = t
	else:
		var f := UITheme.slate(int(badge_px), 3)
		f.set_content_margin_all(0)
		bst = f
	badge.add_theme_stylebox_override("panel", bst)
	badge.custom_minimum_size = Vector2(badge_px, badge_px)
	badge.position = Vector2(0, px - badge_px)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(badge)
	var level := UITheme.stage_label(_label(""), int(badge_px * 0.44), UITheme.PARCHMENT)
	level.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	level.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	badge.add_child(level)
	return {"root": root, "portrait": portrait, "level": level}


## Shows a character's head in a round portrait: the rig's head part when there is one,
## otherwise the top of the flat picture.
func _set_portrait(portrait: TextureRect, flat: String, rig_id: String) -> void:
	var mat: ShaderMaterial = portrait.material
	var head := "res://assets/rigs/%s/head.png" % rig_id
	if Puppet.has_rig(rig_id) and ResourceLoader.exists(head):
		portrait.texture = load(head)
		mat.set_shader_parameter("center", Vector2(0.5, 0.5))
		mat.set_shader_parameter("zoom", 1.05)
	elif flat != "" and ResourceLoader.exists(flat):
		portrait.texture = load(flat)
		mat.set_shader_parameter("center", Vector2(0.5, 0.3))
		mat.set_shader_parameter("zoom", 2.0)


## The HUD's panel for the selected enemy: name, HP and a round portrait with its level.
func _nameplate() -> Dictionary:
	var root := Control.new()
	root.size = Vector2(430, 96)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UITheme.v2_box("nameplate", [24, 8, 22, 10], UITheme.slate(10, 2), 0.5))
	panel.position = Vector2(0, 14)
	panel.size = Vector2(350, 66)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(v)
	var name_label := UITheme.stage_label(_label(""), 20, UITheme.PARCHMENT)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	name_label.clip_text = true
	v.add_child(name_label)
	var hp := _labeled_bar(UITheme.HP, 24, "enemy")
	v.add_child(hp[0])
	var med := _medallion(96, "", "", true)
	med["root"].position = Vector2(334, 0)
	root.add_child(med["root"])
	return {"root": root, "portrait": med["portrait"], "level": med["level"], "name": name_label,
			"hp_bar": hp[1], "hp_label": hp[2], "uid": ""}


## A round gold-rimmed button with an icon and a caption under it. The caption label is
## the button's meta "caption"; its holder (to add to a container) is meta "box".
func _round_button(icon_name: String, fallback_icon: String) -> Button:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	var b := Button.new()
	b.custom_minimum_size = Vector2(86, 86)
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var tex := UITheme.v2("round_button")
	if tex != null:
		for state in ["normal", "hover", "disabled"]:
			var st := StyleBoxTexture.new()
			st.texture = tex
			if state == "disabled":
				st.modulate_color = Color(0.55, 0.55, 0.55)
			b.add_theme_stylebox_override(state, st)
		var pressed := StyleBoxTexture.new()
		pressed.texture = UITheme.v2("round_button_pressed") if UITheme.v2("round_button_pressed") != null else tex
		b.add_theme_stylebox_override("pressed", pressed)
		b.add_theme_stylebox_override("hover_pressed", pressed)
	else:
		for state in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
			var st := UITheme.slate(43, 3)
			if state in ["pressed", "hover_pressed"]:
				st.bg_color = Color(0.16, 0.12, 0.08)
			b.add_theme_stylebox_override(state, st)
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	var icon := TextureRect.new()
	var itex := UITheme.v2(icon_name)
	icon.texture = itex if itex != null else load(fallback_icon)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.set_anchors_preset(Control.PRESET_FULL_RECT)
	icon.offset_left = 16
	icon.offset_top = 16
	icon.offset_right = -16
	icon.offset_bottom = -16
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(icon)
	box.add_child(b)
	var caption := UITheme.stage_label(_label(""), 17, UITheme.PARCHMENT)
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(caption)
	b.set_meta("caption", caption)
	b.set_meta("icon", icon)
	b.set_meta("box", box)
	return b


# ---------------------------------------------------------------- fighters

## Feet position on the stage for a slot [x fraction, y offset].
func _feet(slot: Array) -> Vector2:
	return Vector2(_stage_size.x * slot[0], GROUND + slot[1])


func _rect_for(slot: Array, box: Vector2) -> Rect2:
	var feet := _feet(slot)
	return Rect2(feet - Vector2(box.x * 0.5, box.y), box)


func _build_player_view() -> void:
	if _player_view.has("root"):
		_player_view["root"].queue_free()
	var rect := _rect_for([HERO["x"], HERO["y"]], HERO["box"])
	var root := Control.new()
	root.position = rect.position
	root.size = rect.size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var cls: String = GameState.active_class
	var sprite := _figure(DataDB.data["classes"][cls].get("sprite", ""), engine.player.def_id, rect.size)
	root.add_child(sprite)
	_stage.add_child(root)
	_stage.move_child(root, 1)
	_player_view["root"] = root
	_player_view["sprite"] = sprite
	_level_label.text = str(engine.player.level)


func _build_dragon_view() -> void:
	if _dragon_view.has("root"):
		_dragon_view["root"].queue_free()
	_dragon_view = {}
	if engine.companion == null:
		return
	var defs: Dictionary = DataDB.data["companion"]
	var stage_id: String = Companion.stage(defs, engine.companion.level)["id"]
	var rect := _rect_for([DRAGON["x"], DRAGON["y"]], DRAGON["box"])
	var root := Control.new()
	root.position = rect.position
	root.size = rect.size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sprite := _figure(Companion.sprite(engine.companion.def_id, engine.companion.level, defs),
			"companion_%s_%s" % [engine.companion.def_id, stage_id], rect.size)
	root.add_child(sprite)
	var pips := HBoxContainer.new()
	pips.add_theme_constant_override("separation", 8)
	pips.alignment = BoxContainer.ALIGNMENT_CENTER
	pips.position = Vector2(0, rect.size.y + 4)
	pips.size = Vector2(rect.size.x, 22)
	pips.z_index = 5
	root.add_child(pips)
	var list: Array = []
	for i in engine.companion_charge_needed():
		var pip := Panel.new()
		pip.custom_minimum_size = Vector2(20, 20)
		pips.add_child(pip)
		list.append(pip)
	_stage.add_child(root)
	# behind the player, so the hero stays in front
	_stage.move_child(root, 1)
	_dragon_view = {"root": root, "sprite": sprite, "pips": list}
	_paint_pips(engine.companion_charge)
	_idle_bob(sprite, 0.45)


func _paint_pips(charge: int) -> void:
	if _dragon_view.is_empty():
		return
	var color := Color(DataDB.data["companion"]["elements"][engine.companion.def_id].get("color", "#ffcc66"))
	for i in _dragon_view["pips"].size():
		var st := StyleBoxFlat.new()
		st.set_corner_radius_all(10)
		st.set_border_width_all(3)
		st.border_color = UITheme.GOLD if i < charge else UITheme.GOLD_DARK
		st.bg_color = Color(color * 1.6, 1.0) if i < charge else Color("2a2226")
		if i < charge:
			st.shadow_color = Color(color, 0.6)
			st.shadow_size = 6
		_dragon_view["pips"][i].add_theme_stylebox_override("panel", st)


func _build_enemy_views() -> void:
	for tw in _idle_tweens:
		tw.kill()
	_idle_tweens.clear()
	for v in _enemy_views.values():
		v["root"].queue_free()
	_enemy_views.clear()
	_idle_bob(_player_view["sprite"], 0.0)
	for e in engine.enemies:
		_enemy_views[e.uid] = _build_enemy_view(e, Rect2())
	_layout_enemies(false)


## Places the living enemies' views in their slots. A view is rebuilt when its slot
## changes, because the figure, ring and plate are laid out from the rect.
func _layout_enemies(animate: bool) -> void:
	var alive := engine.alive_enemies()
	var boss: Combatant = null
	for e in alive:
		if DataDB.enemy(e.def_id).get("boss", false):
			boss = e
	var rects := {}
	if boss != null:
		rects[boss.uid] = _rect_for(BOSS, BOSS_BOX)
		var i := 0
		for e in alive:
			if e != boss and i < BOSS_ADDS.size():
				rects[e.uid] = _rect_for(BOSS_ADDS[i], ADD_BOX)
				i += 1
	else:
		var count := clampi(alive.size(), 1, 3)
		var slots: Array = ENEMY_SLOTS[count]
		for i in mini(alive.size(), 3):
			rects[alive[i].uid] = _rect_for(slots[i], ENEMY_BOX[count])
	var n := 0
	for uid in rects:
		var rect: Rect2 = rects[uid]
		var old: Dictionary = _enemy_views[uid]
		if old["rect"] == rect:
			continue
		var fresh: bool = old["rect"] == Rect2()
		old["root"].queue_free()
		var view := _build_enemy_view(engine.get_combatant(uid), rect)
		_enemy_views[uid] = view
		_idle_bob(view["sprite"], 0.25 * (n + 1))
		n += 1
		if animate and fresh:
			var root: Control = view["root"]
			root.modulate.a = 0.0
			root.scale = Vector2(0.6, 0.6)
			root.pivot_offset = rect.size * Vector2(0.5, 1.0)
			var tw := create_tween().set_parallel()
			tw.tween_property(root, "modulate:a", 1.0, 0.3)
			tw.tween_property(root, "scale", Vector2.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		var e := engine.get_combatant(uid)
		if not e.intent.is_empty():
			_set_intent(view, e.intent)
	# nearer fighters (lower feet) draw over farther ones
	var order: Array = rects.keys()
	order.sort_custom(func(a: String, b: String) -> bool: return rects[a].end.y < rects[b].end.y)
	for uid in order:
		_stage.move_child(_enemy_views[uid]["root"], _stage.get_child_count() - 1)
	_stage.move_child(_fx, _stage.get_child_count() - 1)


func _build_enemy_view(e: Combatant, rect: Rect2) -> Dictionary:
	var root := Control.new()
	root.position = rect.position
	root.size = rect.size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.visible = rect.size != Vector2.ZERO
	_stage.add_child(root)
	_stage.move_child(root, 1)

	# a glowing ellipse under the feet of the selected enemy
	var ring := TextureRect.new()
	ring.texture = BattleFx.dot()
	ring.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ring.stretch_mode = TextureRect.STRETCH_SCALE
	ring.modulate = Color(1.6, 1.25, 0.5, 0.75)
	ring.position = Vector2(rect.size.x * 0.1, rect.size.y - rect.size.y * 0.07)
	ring.size = Vector2(rect.size.x * 0.8, rect.size.y * 0.14)
	ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(ring)
	var rtw := ring.create_tween().set_loops()
	rtw.tween_property(ring, "modulate:a", 0.35, 0.7).set_trans(Tween.TRANS_SINE)
	rtw.tween_property(ring, "modulate:a", 0.8, 0.7).set_trans(Tween.TRANS_SINE)
	_idle_tweens.append(rtw)

	var sprite := _figure(DataDB.enemy(e.def_id).get("sprite", ""), e.def_id, rect.size)
	sprite.mouse_filter = Control.MOUSE_FILTER_STOP
	sprite.gui_input.connect(_on_enemy_input.bind(e.uid))
	root.add_child(sprite)
	var figure_h: float = sprite.get_meta("figure_h")

	# name plate, HP and statuses above the head, the intent badge above that
	var plate_w := clampf(rect.size.x * 0.8, 150.0, 230.0)
	var info := VBoxContainer.new()
	info.position = Vector2((rect.size.x - plate_w) * 0.5, rect.size.y - figure_h - 62)
	info.size = Vector2(plate_w, 0)
	info.add_theme_constant_override("separation", 1)
	info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.z_index = 10
	root.add_child(info)
	var name_label := UITheme.stage_label(_label(DataDB.t(e.name_key)), 18)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info.add_child(name_label)
	var hp := _labeled_bar(UITheme.HP, 18, "enemy")
	info.add_child(hp[0])
	hp[1].max_value = e.max_hp()
	var statuses := HBoxContainer.new()
	statuses.alignment = BoxContainer.ALIGNMENT_CENTER
	statuses.custom_minimum_size.y = 28
	statuses.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_child(statuses)

	var intent := PanelContainer.new()
	intent.add_theme_stylebox_override("panel", UITheme.badge())
	intent.mouse_filter = Control.MOUSE_FILTER_IGNORE
	intent.z_index = 10
	var ih := HBoxContainer.new()
	ih.add_theme_constant_override("separation", 4)
	intent.add_child(ih)
	var intent_icon := TextureRect.new()
	intent_icon.custom_minimum_size = Vector2(32, 32)
	intent_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	intent_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ih.add_child(intent_icon)
	var intent_label := UITheme.stage_label(_label(""), 24, Color("ffb0a0"))
	ih.add_child(intent_label)
	var intent_debuff := TextureRect.new()
	intent_debuff.texture = load("res://assets/icons/intents/debuff.png")
	intent_debuff.custom_minimum_size = Vector2(26, 26)
	intent_debuff.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	intent_debuff.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ih.add_child(intent_debuff)
	intent.position = Vector2(rect.size.x * 0.5 - 44, info.position.y - 44)
	root.add_child(intent)

	var arrow := TextureRect.new()
	arrow.texture = load("res://assets/icons/ui/target.png")
	arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	arrow.custom_minimum_size = Vector2(40, 40)
	arrow.size = Vector2(40, 40)
	arrow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	arrow.position = Vector2(rect.size.x * 0.5 + 52, info.position.y - 40)
	arrow.z_index = 10
	root.add_child(arrow)
	var atw := arrow.create_tween().set_loops()
	atw.tween_property(arrow, "position:y", arrow.position.y + 8, 0.45).set_trans(Tween.TRANS_SINE)
	atw.tween_property(arrow, "position:y", arrow.position.y, 0.45).set_trans(Tween.TRANS_SINE)
	_idle_tweens.append(atw)

	return {"root": root, "rect": rect, "sprite": sprite, "ring": ring, "arrow": arrow, "intent": intent,
			"intent_icon": intent_icon, "intent_label": intent_label, "intent_debuff": intent_debuff,
			"hp_bar": hp[1], "hp_label": hp[2], "statuses": statuses}


## A fighter's body inside a box: the animated puppet when its rig exists, otherwise the
## flat picture. The returned control keeps its feet at the box's bottom centre; its meta
## "puppet" is the Puppet (or null) and "figure_h" the drawn height.
func _figure(flat: String, rig_id: String, box: Vector2) -> Control:
	var c := Control.new()
	c.size = box
	c.pivot_offset = Vector2(box.x * 0.5, box.y)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.set_meta("home_x", 0.0)
	if Settings.animations and Puppet.has_rig(rig_id):
		var p := Puppet.new(rig_id)
		var k := p.fit_scale(box)
		p.scale = Vector2(k, k)
		p.position = Vector2(box.x * 0.5, box.y)
		c.add_child(p)
		c.set_meta("puppet", p)
		c.set_meta("figure_h", p.height * k)
		return c
	var t := TextureRect.new()
	if flat != "" and ResourceLoader.exists(flat):
		t.texture = load(flat)
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	t.size = box
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.add_child(t)
	c.set_meta("figure_h", box.y * 0.86)
	return c


func _puppet(view: Dictionary) -> Puppet:
	if view.is_empty() or not view.has("sprite"):
		return null
	var s: Control = view["sprite"]
	return s.get_meta("puppet") if s.has_meta("puppet") else null


## Middle of a fighter's body on the stage, for effects and flying spells.
func _body_center(view: Dictionary) -> Vector2:
	var s: Control = view["sprite"]
	var r := s.get_global_rect()
	var h: float = s.get_meta("figure_h", r.size.y)
	return Vector2(r.get_center().x, r.end.y - h * 0.5)


func _build_skill_buttons() -> void:
	for child in _skill_grid.get_children():
		child.queue_free()
	_skill_buttons.clear()
	_player_view["hp_bar"].max_value = engine.player.max_hp()
	_player_view["res_bar"].max_value = engine.player.resource_max
	var skills: Array = engine.player.skills
	var rest := maxi(0, skills.size() - 1)
	var ribbon_w := 290.0
	var gap := 10.0
	# the squares share what the banner leaves, up to 84 px each
	var slot := clampf((_skill_grid.size.x - ribbon_w - 18 - maxi(0, rest - 1) * gap) / maxf(1, rest), 60.0, 84.0)
	var row_w := ribbon_w + 18 + rest * slot + maxi(0, rest - 1) * gap
	var x0 := maxf(0.0, (_skill_grid.size.x - row_w) * 0.5)
	for i in skills.size():
		var id: String = skills[i]
		var def := DataDB.skill(id)
		var b := Button.new()
		b.tooltip_text = DataDB.t(def.get("desc_key", ""))
		b.pressed.connect(_on_skill_pressed.bind(id))
		b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
		var glow := Panel.new()
		var gs := StyleBoxFlat.new()
		gs.bg_color = Color(0, 0, 0, 0)
		gs.border_color = UITheme.COMBO
		gs.set_border_width_all(4)
		gs.set_corner_radius_all(12)
		gs.set_expand_margin_all(5)
		gs.shadow_color = Color(UITheme.COMBO, 0.7)
		gs.shadow_size = 12
		glow.add_theme_stylebox_override("panel", gs)
		glow.set_anchors_preset(Control.PRESET_FULL_RECT)
		glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
		glow.visible = false
		b.set_meta("glow", glow)
		var gtw := create_tween().set_loops()
		gtw.tween_property(glow, "modulate:a", 0.35, 0.5).set_trans(Tween.TRANS_SINE)
		gtw.tween_property(glow, "modulate:a", 1.0, 0.5).set_trans(Tween.TRANS_SINE)
		_idle_tweens.append(gtw)
		if i == 0:
			_ribbon(b, def)
			b.size = Vector2(ribbon_w, 84)
			b.custom_minimum_size = b.size
			b.position = Vector2(x0, (slot - 84) * 0.5 + 4)
		else:
			_slot(b, def, i)
			b.position = Vector2(x0 + ribbon_w + 18 + (i - 1) * (slot + gap), 4)
			b.size = Vector2(slot, slot)
		b.add_child(glow)
		_skill_grid.add_child(b)
		_skill_buttons[id] = b


## The big crimson "attack" banner for the class's first skill.
func _ribbon(b: Button, _def: Dictionary) -> void:
	# the reference's banner carries only its word, the skill icon would crowd it
	b.expand_icon = true
	b.add_theme_constant_override("icon_max_width", 30)
	b.add_theme_font_override("font", UITheme.title_font())
	b.add_theme_font_size_override("font_size", UITheme.fs(20))
	b.clip_text = true
	b.add_theme_color_override("font_color", Color("fff1d6"))
	b.add_theme_color_override("font_outline_color", Color("3a0c08"))
	b.add_theme_constant_override("outline_size", 6)
	var fallback := StyleBoxFlat.new()
	fallback.bg_color = Color("8e1c19")
	fallback.border_color = UITheme.GOLD
	fallback.set_border_width_all(3)
	fallback.set_corner_radius_all(8)
	fallback.shadow_color = Color(0, 0, 0, 0.55)
	fallback.shadow_size = 8
	var pressed_fb: StyleBoxFlat = fallback.duplicate()
	pressed_fb.bg_color = Color("6a1210")
	var disabled_fb: StyleBoxFlat = fallback.duplicate()
	disabled_fb.bg_color = Color("4a2826")
	disabled_fb.border_color = UITheme.GOLD_DARK
	var c := [28, 6, 28, 8]
	b.add_theme_stylebox_override("normal", UITheme.v2_box("ribbon_button", c, fallback, 0.5))
	b.add_theme_stylebox_override("hover", UITheme.v2_box("ribbon_button", c, fallback, 0.5))
	b.add_theme_stylebox_override("pressed", UITheme.v2_box("ribbon_button_pressed", c, pressed_fb, 0.5))
	b.add_theme_stylebox_override("hover_pressed", UITheme.v2_box("ribbon_button_pressed", c, pressed_fb, 0.5))
	b.add_theme_stylebox_override("disabled", UITheme.v2_box("ribbon_button_disabled", c, disabled_fb, 0.5))
	b.set_meta("ribbon", true)


## A square skill slot: the painted icon, its number, cost and name.
func _slot(b: Button, def: Dictionary, number: int) -> void:
	var frame := StyleBoxFlat.new()
	frame.bg_color = Color(0.05, 0.05, 0.07)
	frame.border_color = UITheme.GOLD_DARK
	frame.set_border_width_all(3)
	frame.set_corner_radius_all(6)
	for state in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
		b.add_theme_stylebox_override(state, frame)
	var icon := TextureRect.new()
	icon.texture = load(def.get("icon", "res://assets/icons/skills/slash.png"))
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	icon.set_anchors_preset(Control.PRESET_FULL_RECT)
	icon.offset_left = 4
	icon.offset_top = 4
	icon.offset_right = -4
	icon.offset_bottom = -4
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(icon)
	var frame_tex := UITheme.v2("skill_slot")
	if frame_tex != null:
		var f := TextureRect.new()
		f.texture = frame_tex
		f.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		f.stretch_mode = TextureRect.STRETCH_SCALE
		f.set_anchors_preset(Control.PRESET_FULL_RECT)
		f.offset_left = -6
		f.offset_top = -6
		f.offset_right = 6
		f.offset_bottom = 6
		f.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(f)
	var num := UITheme.stage_label(_label(str(number)), 16, UITheme.GOLD)
	num.position = Vector2(4, 0)
	b.add_child(num)
	var cost := UITheme.stage_label(_label(""), 16, Color("9fd0ff"))
	cost.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	cost.position = Vector2(0, 62)
	cost.size = Vector2(82, 22)
	b.add_child(cost)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.55)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shade.visible = false
	b.add_child(shade)
	var cd := UITheme.stage_label(_label(""), 34, Color.WHITE)
	cd.set_anchors_preset(Control.PRESET_FULL_RECT)
	cd.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cd.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	b.add_child(cd)
	var name_label := UITheme.stage_label(_label(DataDB.t(def.get("name_key", ""))), 14, UITheme.PARCHMENT)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.clip_text = true
	name_label.position = Vector2(-10, 90)
	name_label.size = Vector2(108, 20)
	b.add_child(name_label)
	b.set_meta("cost", cost)
	b.set_meta("cd", cd)
	b.set_meta("shade", shade)


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
	var style := UITheme.skin_panel("wood")
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
	_result_body.add_theme_font_size_override("font_size", UITheme.fs(30))
	v.add_child(_result_body)
	_result_button = Button.new()
	_result_button.custom_minimum_size.y = 84
	_result_button.add_theme_font_size_override("font_size", UITheme.fs(30))
	_result_button.pressed.connect(_on_result_pressed)
	v.add_child(_result_button)
	_result_layer.visible = false
	add_child(_result_layer)


## Returns [container, bar, label]: a progress bar with its value written inside. kind picks
## the landscape kit's fill ("hp", "mana", "rage", "energy", "enemy", "xp").
func _labeled_bar(color: Color, height: int, kind: String = "") -> Array:
	var holder := Control.new()
	holder.custom_minimum_size.y = height
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.set_anchors_preset(Control.PRESET_FULL_RECT)
	var fill := UITheme.skin_bar_fill_tinted(color)
	var fill_tex := UITheme.v2("bar_fill_" + kind) if kind != "" else null
	if fill_tex != null:
		fill = UITheme.v2_box("bar_fill_" + kind, [0, 0, 0, 0], fill, 0.5)
	bar.add_theme_stylebox_override("fill", fill)
	var back_tex := UITheme.v2("bar_back")
	if back_tex != null:
		bar.add_theme_stylebox_override("background", UITheme.v2_box("bar_back", [0, 0, 0, 0], null, 0.5))
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(bar)
	var frame_tex := UITheme.v2("bar_frame")
	if frame_tex != null:
		var frame := NinePatchRect.new()
		frame.texture = UITheme.v2_scaled("bar_frame", 0.5)
		frame.patch_margin_left = 10
		frame.patch_margin_right = 10
		frame.patch_margin_top = 8
		frame.patch_margin_bottom = 8
		frame.set_anchors_preset(Control.PRESET_FULL_RECT)
		frame.offset_left = -3
		frame.offset_top = -3
		frame.offset_right = 3
		frame.offset_bottom = 3
		frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
		holder.add_child(frame)
	var l := UITheme.stage_label(_label(""), int(height * 0.68))
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

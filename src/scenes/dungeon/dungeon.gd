extends Control
## Dungeon map: pick one of two doors per room, resolve the room, repeat until the boss
## (docs/02, docs/06, docs/08). All rules live in DungeonRun; this script draws them.
## The run comes from GameState: a fresh one, or one resumed from the save file.

const BATTLE_SCENE := preload("res://src/scenes/battle/battle.tscn")
const TOWN_SCENE := "res://src/scenes/town/town.tscn"
const ROOM_ICON := "res://assets/icons/rooms/%s.png"
const ITEM_ICON := "res://assets/icons/items/%s.png"
const EVENT_ART := "res://assets/events/%s.png"
const ROOM_ART := {"treasure": "chest", "rest": "campfire"}

var run: DungeonRun

var _root: VBoxContainer
var _title: Label
var _room_label: Label
var _trail: HBoxContainer
var _hp_bar: ProgressBar
var _hp_label: Label
var _xp_bar: ProgressBar
var _level_label: Label
var _potion_label: Label
var _gold_label: Label
var _prompt: Label
var _doors: HBoxContainer
var _escape_button: Button
var _toast_box: VBoxContainer
var _modal_layer: Control
var _fade: ColorRect
var _battle: Control
var _busy: bool = false


func _ready() -> void:
	Audio.music("dungeon")
	theme = UITheme.build()
	# the layout reads the dungeon's backgrounds, so the run has to exist first
	run = _current_run()
	_build_ui()
	_new_run()


## The run the town handed over (new or resumed), or a fresh one after "Run again".
func _current_run() -> DungeonRun:
	return GameState.run if GameState.run != null else GameState.start_run(GameState.next_dungeon, GameState.next_hard)


func _new_run() -> void:
	run = _current_run()
	run.leveled_up.connect(_on_level_up)
	if run.room_number == 0:
		run.start()
	_close_modal()
	_refresh()
	_show_doors()
	if run.history.is_empty():
		await _play_story(run.dungeon_id + "_intro")


## Plays a story scene once per save (docs/07) and waits for it to end.
func _play_story(scene_id: String) -> void:
	if not StoryDialog.has_scene(scene_id) or not GameState.profile.take_story(scene_id):
		return
	GameState.changed()
	var dlg := StoryDialog.new(scene_id)
	add_child(dlg)
	await dlg.finished


# ---------------------------------------------------------------- flow

func _on_door_pressed(index: int, card: Control) -> void:
	if _busy:
		return
	_busy = true
	Audio.play("door_open")
	var tw := create_tween().set_parallel()
	card.pivot_offset = card.size * 0.5
	tw.tween_property(card, "scale", Vector2(1.12, 1.12), 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	await tw.finished
	await _fade_to(1.0)
	var room := run.enter(index)
	_refresh()
	match room["type"]:
		"combat", "elite", "boss":
			_start_battle()
		"treasure":
			_show_treasure()
		"event":
			_show_event()
		"rest":
			_show_rest()
	await _fade_to(0.0)
	_busy = false


func _start_battle() -> void:
	_battle = BATTLE_SCENE.instantiate()
	_battle.setup(run.make_battle(), run.def.get("background", ""))
	_battle.finished.connect(_on_battle_finished)
	add_child(_battle)
	move_child(_battle, _fade.get_index())


func _on_battle_finished(engine: CombatEngine) -> void:
	if _busy:
		return
	_busy = true
	await _fade_to(1.0)
	_battle.queue_free()
	_battle = null
	Audio.music("dungeon")
	var result := run.finish_battle(engine)
	_refresh()
	if run.outcome != "":
		_show_summary()
	else:
		_next_room()
		if result.get("healed", 0) > 0:
			_toast(DataDB.t("map.breather") % result["healed"], Color("7dff8a"))
		_loot_toasts(result.get("items", []), result.get("scales", 0))
	await _fade_to(0.0)
	_busy = false


func _next_room() -> void:
	_close_modal()
	run.next_room()
	_refresh()
	_show_doors()


func _on_level_up(level: int) -> void:
	_toast(DataDB.t("map.level_up") % level, UITheme.COMBO, 44)


func _on_escape_pressed() -> void:
	if _busy or not run.can_escape():
		return
	if run.history.is_empty():
		# Nothing happened yet: just walk back to town.
		_busy = true
		GameState.cancel_run()
		await _fade_to(1.0)
		get_tree().change_scene_to_file(TOWN_SCENE)
		return
	var body := _modal(DataDB.t("map.escape"), "", DataDB.t("map.escape_confirm"))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	body.add_child(row)
	var stay := _button(DataDB.t("map.escape_no"), "", func() -> void: _close_modal())
	stay.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(stay)
	var go := _button(DataDB.t("map.escape_yes"), ITEM_ICON % "flee", func() -> void:
		run.escape()
		_show_summary())
	go.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(go)


# ---------------------------------------------------------------- rooms without battles

func _show_treasure() -> void:
	var body := _modal(DataDB.t("treasure.title"), EVENT_ART % ROOM_ART["treasure"], DataDB.t("treasure.text"))
	body.add_child(_button(DataDB.t("treasure.open"), ROOM_ICON % "treasure", func() -> void:
		var r := run.open_treasure()
		Audio.play("chest_open")
		if r.get("mimic", false):
			_set_modal_text(DataDB.t("treasure.mimic"), Color("ff6a5a"))
			_clear_modal_buttons()
			_shake_modal()
			await get_tree().create_timer(0.9).timeout
			await _fade_to(1.0)
			_close_modal()
			_start_battle()
			await _fade_to(0.0)
			return
		var text := DataDB.t("treasure.found") % r["gold"]
		if r["potion"]:
			text += "\n" + DataDB.t("treasure.potion")
		_set_modal_text(text, UITheme.GOLD)
		_refresh()
		_continue_button()
		_modal_items(r.get("items", []))))


func _show_event() -> void:
	var ev := run.event_def()
	var body := _modal(DataDB.t(ev["title_key"]), EVENT_ART % ev.get("art", "skull"), DataDB.t(ev["text_key"]))
	var choices: Array = ev.get("choices", [])
	for i in choices.size():
		var b := _button(DataDB.t(choices[i]["label_key"]), "", _on_event_choice.bind(i))
		b.disabled = not run.event_choice_available(i)
		body.add_child(b)


func _on_event_choice(index: int) -> void:
	var r := run.choose_event(index)
	if r.is_empty():
		return
	var changes: Dictionary = r["changes"]
	var color := UITheme.TEXT
	if changes.get("hp", 0) < 0:
		color = Color("ff8a7a")
	elif changes.get("hp", 0) > 0 or changes.get("gold", 0) > 0 or changes.has("potions") or changes.has("atk_percent"):
		color = Color("9dff9a")
	_set_modal_text(DataDB.t(r["text_key"]), color)
	_refresh()
	_continue_button()
	if changes.has("item"):
		_modal_items([changes["item"]])


func _show_rest() -> void:
	var r: Dictionary = run.def.get("rest", {})
	var body := _modal(DataDB.t("rest.title"), EVENT_ART % ROOM_ART["rest"], DataDB.t("rest.text"))
	var heal_pct := roundi(float(r.get("heal_percent", 0.3)) * 100)
	var heal := _button(DataDB.t("rest.heal") % heal_pct, ITEM_ICON % "heart", func() -> void:
		var res := run.rest("heal")
		_set_modal_text(DataDB.t("rest.healed") % res["heal"], Color("9dff9a"))
		_refresh()
		_continue_button())
	heal.disabled = run.player.hp >= run.player.max_hp()
	body.add_child(heal)
	body.add_child(_button(DataDB.t("rest.potion"), ITEM_ICON % "potion", func() -> void:
		run.rest("potion")
		_set_modal_text(DataDB.t("rest.brewed"), Color("9dff9a"))
		_refresh()
		_continue_button()))


func _show_summary() -> void:
	var banked := GameState.apply_run(run)
	if banked.get("first_clear", false):
		await _play_story(run.dungeon_id + "_outro")
		if not banked.get("reward", {}).is_empty():
			await _show_ending(banked["reward"])
	var colors := {"cleared": UITheme.GOLD, "escaped": Color("8fc4ff"), "died": UITheme.HP}
	var art := "chest" if run.outcome == "cleared" else ("campfire" if run.outcome == "escaped" else "skull")
	var hint := DataDB.t("run.%s_hint" % run.outcome)
	if run.outcome == "cleared":
		hint = DataDB.t("run.cleared_hint." + run.dungeon_id)
	var body := _modal(DataDB.t("run." + run.outcome) + ("  ·  " + DataDB.t("run.hard") if run.hard else ""),
			EVENT_ART % art, hint)
	_modal_layer.get_meta("title").add_theme_color_override("font_color", colors[run.outcome])
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 24)
	grid.add_theme_constant_override("v_separation", 6)
	body.add_child(grid)
	var rows := [
		["run.rooms", str(run.history.size())],
		["run.kills", str(run.kills)],
		["run.gold", "+%d" % run.gold_earned],
		["run.xp", "+%d" % run.xp_earned],
		["run.level", str(run.level)],
	]
	if run.gold_lost > 0:
		rows.insert(3, ["run.gold_lost", "-%d" % run.gold_lost])
	if run.scales_earned > 0:
		rows.append(["ui.scales", "+%d" % run.scales_earned])
	for row in rows:
		var k := _label(DataDB.t(row[0]), 26, UITheme.TEXT_MUTED)
		k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(k)
		var v := _label(row[1], 28, UITheme.TEXT)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		grid.add_child(v)
	if run.outcome == "cleared":
		body.add_child(_stars_line(run.stars(), banked.get("new_stars", [])))
	body.add_child(UIKit.label(UITheme.caps(DataDB.t("run.loot")), 24, UITheme.GOLD))
	if run.loot.is_empty():
		body.add_child(_label(DataDB.t("run.no_loot"), 22, UITheme.TEXT_MUTED))
	else:
		var tiles := HFlowContainer.new()
		tiles.add_theme_constant_override("h_separation", 10)
		tiles.add_theme_constant_override("v_separation", 10)
		body.add_child(tiles)
		for item in run.loot.slice(0, 10):
			tiles.add_child(ItemUI.tile(item, 88))
	var salvaged: Dictionary = banked.get("salvaged", {})
	if salvaged.get("count", 0) > 0:
		var note := UIKit.wrapped(DataDB.tf("run.bag_full", {"n": salvaged["count"], "gold": salvaged["gold"]}), 21, UITheme.TEXT_MUTED)
		body.add_child(note)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	body.add_child(row)
	var town := UIKit.primary(_button(DataDB.t("run.to_town"), "", func() -> void:
		await _fade_to(1.0)
		get_tree().change_scene_to_file(TOWN_SCENE)))
	town.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(town)
	var again := _button(DataDB.t("run.again"), ROOM_ICON % "combat", func() -> void:
		await _fade_to(1.0)
		_new_run()
		await _fade_to(0.0))
	again.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(again)


# ---------------------------------------------------------------- map drawing

func _refresh() -> void:
	var p := run.player
	_room_label.text = DataDB.t("map.room") % [mini(run.room_number, run.room_count()), run.room_count()]
	_hp_bar.max_value = p.max_hp()
	_hp_bar.value = p.hp
	_hp_label.text = "%d / %d" % [p.hp, p.max_hp()]
	_xp_bar.max_value = Progression.xp_to_next(run.level)
	_xp_bar.value = run.class_xp
	_level_label.text = "%s  ·  %s" % [DataDB.t("class." + run.class_id), DataDB.t("ui.level") % run.level]
	_potion_label.text = "x%d" % run.potions
	_gold_label.text = str(run.gold_earned)
	_escape_button.disabled = not run.can_escape()
	_escape_button.text = DataDB.t("run.to_town") if run.history.is_empty() else DataDB.t("map.escape")
	_draw_trail()


func _draw_trail() -> void:
	for c in _trail.get_children():
		c.queue_free()
	for i in run.room_count():
		var n := i + 1
		if i > 0:
			var link := ColorRect.new()
			link.custom_minimum_size = Vector2(28, 6)
			link.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			link.color = UITheme.GOLD if n <= run.room_number else Color("4a3a30")
			_trail.add_child(link)
		var pip := PanelContainer.new()
		var st := StyleBoxFlat.new()
		st.set_corner_radius_all(40)
		st.set_border_width_all(4)
		st.bg_color = Color("1b120e")
		st.border_color = UITheme.GOLD if n == run.room_number else Color("5a4636")
		if n == run.room_number:
			st.shadow_color = Color(UITheme.COMBO, 0.5)
			st.shadow_size = 8
		pip.add_theme_stylebox_override("panel", st)
		var icon := TextureRect.new()
		icon.custom_minimum_size = Vector2(62, 62)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		if i < run.history.size():
			icon.texture = load(ROOM_ICON % run.history[i])
		elif n == run.room_count():
			icon.texture = load(ROOM_ICON % "boss")
			icon.modulate = Color(1, 1, 1, 0.45)
		else:
			var q := _label("?", 34, Color("7a6a5a"))
			q.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			q.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			q.custom_minimum_size = Vector2(62, 62)
			pip.add_child(q)
			_trail.add_child(pip)
			continue
		pip.add_child(icon)
		_trail.add_child(pip)


func _show_doors() -> void:
	GameState.save_run()
	for c in _doors.get_children():
		c.queue_free()
	var boss := run.is_boss_room()
	_prompt.text = UITheme.caps(DataDB.t("map.boss_ahead") if boss else DataDB.t("map.choose"))
	for i in run.choices.size():
		var card := _door_card(run.choices[i], i)
		_doors.add_child(card)
		card.modulate.a = 0.0
		var tw := create_tween().set_parallel()
		tw.tween_property(card, "modulate:a", 1.0, 0.3).set_delay(0.12 * i)


func _door_card(room: Dictionary, index: int) -> Control:
	var type: String = room["type"]
	var boss := type == "boss"
	var card := Button.new()
	card.flat = true
	card.custom_minimum_size = Vector2(420 if boss else 320, 560)
	card.add_theme_stylebox_override("hover", StyleBoxEmpty.new())
	card.add_theme_stylebox_override("pressed", StyleBoxEmpty.new())
	card.add_theme_stylebox_override("normal", StyleBoxEmpty.new())
	card.pressed.connect(func() -> void: _on_door_pressed(index, card))

	var v := VBoxContainer.new()
	v.set_anchors_preset(Control.PRESET_FULL_RECT)
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_theme_constant_override("separation", 4)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(v)

	var door_holder := Control.new()
	var door_size := Vector2(300, 400) if boss else Vector2(255, 340)
	door_holder.custom_minimum_size = door_size
	door_holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(door_holder)
	var door := TextureRect.new()
	door.texture = load("res://assets/ui/door_boss.png" if boss else "res://assets/ui/door.png")
	door.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	door.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	door.set_anchors_preset(Control.PRESET_FULL_RECT)
	door.mouse_filter = Control.MOUSE_FILTER_IGNORE
	door_holder.add_child(door)
	if not boss:
		var medal := TextureRect.new()
		medal.texture = load(ROOM_ICON % type)
		medal.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		medal.size = Vector2(112, 112)
		medal.position = Vector2(door_size.x * 0.5 - 56, door_size.y * 0.36)
		medal.mouse_filter = Control.MOUSE_FILTER_IGNORE
		door_holder.add_child(medal)
		var tw := medal.create_tween().set_loops()
		tw.tween_property(medal, "position:y", medal.position.y - 6, 0.8).set_trans(Tween.TRANS_SINE).set_delay(0.3 * index)
		tw.tween_property(medal, "position:y", medal.position.y, 0.8).set_trans(Tween.TRANS_SINE)

	var name_key: String = "enemy." + String(run.def.get("boss", [""])[0]) if boss else "room." + type
	var title := _label(UITheme.caps(DataDB.t(name_key)), 34 if boss else 30, Color("ff8070") if boss else UITheme.GOLD)
	title.add_theme_font_override("font", UITheme.title_font())
	title.add_theme_color_override("font_outline_color", UITheme.INK)
	title.add_theme_constant_override("outline_size", 8)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(title)
	var hint := _label(DataDB.t("room.boss.hint." + run.dungeon_id) if boss else DataDB.t("room.%s.hint" % type), 21, UITheme.TEXT)
	hint.add_theme_color_override("font_outline_color", UITheme.INK)
	hint.add_theme_constant_override("outline_size", 6)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(hint)
	if room.has("enemies"):
		var badge := PanelContainer.new()
		badge.add_theme_stylebox_override("panel", UITheme.badge())
		badge.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		badge.add_child(_label("%s  ·  %s" % [DataDB.t("ui.level") % room["level"],
				DataDB.t("map.enemies") % room["enemies"].size()], 20, UITheme.TEXT_MUTED))
		v.add_child(badge)
	return card


# ---------------------------------------------------------------- modal panels

## Opens a centered panel with a title, optional art and text. Returns the body box
## where buttons go.
func _modal(title: String, art_path: String, text: String) -> VBoxContainer:
	_close_modal()
	_modal_layer.visible = true
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.65)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_modal_layer.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_modal_layer.add_child(center)
	var panel := PanelContainer.new()
	var style := UITheme.skin_panel("wood")
	panel.add_theme_stylebox_override("panel", style)
	panel.custom_minimum_size = Vector2(640, 0)
	center.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 16)
	panel.add_child(v)
	var t := _label(UITheme.caps(title), 42, UITheme.GOLD)
	t.add_theme_font_override("font", UITheme.title_font())
	t.add_theme_color_override("font_outline_color", UITheme.INK)
	t.add_theme_constant_override("outline_size", 8)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(t)
	if art_path != "":
		var art := TextureRect.new()
		art.texture = load(art_path)
		art.custom_minimum_size = Vector2(0, 300)
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		v.add_child(art)
	var body_text := _label(text, 27, UITheme.TEXT)
	body_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body_text.custom_minimum_size.x = 580
	v.add_child(body_text)
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	v.add_child(body)
	_modal_layer.set_meta("title", t)
	_modal_layer.set_meta("text", body_text)
	_modal_layer.set_meta("body", body)
	_modal_layer.set_meta("panel", panel)
	panel.pivot_offset = Vector2(320, 300)
	panel.scale = Vector2(0.85, 0.85)
	panel.modulate.a = 0.0
	var tw := create_tween().set_parallel()
	tw.tween_property(panel, "scale", Vector2.ONE, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(panel, "modulate:a", 1.0, 0.2)
	return body


func _set_modal_text(text: String, color: Color) -> void:
	var l: Label = _modal_layer.get_meta("text")
	l.text = text
	l.add_theme_color_override("font_color", color)
	l.pivot_offset = l.size * 0.5
	l.scale = Vector2(1.15, 1.15)
	create_tween().tween_property(l, "scale", Vector2.ONE, 0.2)


func _clear_modal_buttons() -> void:
	for c in _modal_layer.get_meta("body").get_children():
		c.queue_free()


func _continue_button() -> void:
	_clear_modal_buttons()
	_modal_layer.get_meta("body").add_child(_button(DataDB.t("map.continue"), "", func() -> void:
		if _busy:
			return
		_busy = true
		await _fade_to(1.0)
		_next_room()
		await _fade_to(0.0)
		_busy = false))


func _shake_modal() -> void:
	var panel: Control = _modal_layer.get_meta("panel")
	var tw := create_tween()
	for i in 6:
		tw.tween_property(panel, "position:x", panel.position.x + (12 if i % 2 == 0 else -12), 0.04)
	tw.tween_property(panel, "position:x", panel.position.x, 0.04)


func _close_modal() -> void:
	for c in _modal_layer.get_children():
		c.queue_free()
	_modal_layer.visible = false


func _toast(text: String, color: Color, font_size: int = 32) -> void:
	var l := _label(UITheme.caps(text), font_size, color)
	l.add_theme_font_override("font", UITheme.title_font())
	l.add_theme_color_override("font_outline_color", UITheme.INK)
	l.add_theme_constant_override("outline_size", 10)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast_box.add_child(l)
	l.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(l, "modulate:a", 1.0, 0.25)
	tw.tween_interval(2.2)
	tw.tween_property(l, "modulate:a", 0.0, 0.5)
	tw.tween_callback(l.queue_free)


## Slides found items in under the header, one row per item.
func _loot_toasts(items: Array, scales: int) -> void:
	if scales > 0:
		_toast(DataDB.tf("loot.scales", {"n": scales}), Color("7fd4ff"))
	for i in items.size():
		var card := PanelContainer.new()
		var st := UITheme.badge(Color(0.08, 0.05, 0.07, 0.9))
		st.border_color = ItemUI.color(items[i])
		st.set_border_width_all(3)
		st.set_content_margin_all(8)
		st.content_margin_right = 20
		card.add_theme_stylebox_override("panel", st)
		card.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		card.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 12)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(row)
		row.add_child(ItemUI.tile(items[i], 72))
		var v := VBoxContainer.new()
		v.alignment = BoxContainer.ALIGNMENT_CENTER
		v.add_theme_constant_override("separation", 0)
		v.add_child(UITheme.stage_label(_label(DataDB.t("loot.found"), 20, UITheme.TEXT_MUTED), 20, UITheme.TEXT_MUTED))
		v.add_child(UITheme.stage_label(_label(ItemUI.item_name(items[i]), 30, ItemUI.color(items[i])), 30, ItemUI.color(items[i])))
		row.add_child(v)
		_toast_box.add_child(card)
		card.modulate.a = 0.0
		var tw := create_tween()
		tw.tween_interval(0.35 * i + 0.2)
		tw.tween_property(card, "modulate:a", 1.0, 0.25)
		tw.tween_interval(2.6)
		tw.tween_property(card, "modulate:a", 0.0, 0.5)
		tw.tween_callback(card.queue_free)


## Shows items found in a room inside the open modal, above its buttons.
func _modal_items(items: Array) -> void:
	if items.is_empty():
		return
	var body: VBoxContainer = _modal_layer.get_meta("body")
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	body.add_child(box)
	body.move_child(box, 0)
	for item in items:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 14)
		row.add_child(ItemUI.tile(item, 84))
		var d := ItemUI.details(item)
		d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(d)
		box.add_child(row)


func _fade_to(alpha: float) -> void:
	_fade.visible = true
	var tw := create_tween()
	tw.tween_property(_fade, "color:a", alpha, 0.25)
	await tw.finished
	_fade.visible = alpha > 0.0


# ---------------------------------------------------------------- layout

func _build_ui() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := TextureRect.new()
	bg.texture = load(run.def.get("map_background", "res://assets/backgrounds/rotten_cellar_map.png"))
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	_root = VBoxContainer.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_theme_constant_override("separation", 0)
	add_child(_root)

	# ---- header: dungeon name, room counter and the room trail
	var header := PanelContainer.new()
	var hs := UITheme.skin_panel("header")
	hs.content_margin_top = 18
	hs.content_margin_bottom = 16
	header.add_theme_stylebox_override("panel", hs)
	_root.add_child(header)
	var hv := VBoxContainer.new()
	hv.add_theme_constant_override("separation", 8)
	header.add_child(hv)
	var title_row := HBoxContainer.new()
	hv.add_child(title_row)
	_title = _label(UITheme.caps(DataDB.t(run_def_name())), 36, UITheme.GOLD)
	_title.add_theme_font_override("font", UITheme.title_font())
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_row.add_child(_title)
	_room_label = _label("", 24, UITheme.TEXT_MUTED)
	title_row.add_child(_room_label)
	_trail = HBoxContainer.new()
	_trail.alignment = BoxContainer.ALIGNMENT_CENTER
	_trail.add_theme_constant_override("separation", 0)
	hv.add_child(_trail)

	# ---- player card
	var pc_margin := MarginContainer.new()
	for side in ["left", "right", "top"]:
		pc_margin.add_theme_constant_override("margin_" + side, 18)
	_root.add_child(pc_margin)
	var pc := PanelContainer.new()
	pc.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	pc_margin.add_child(pc)
	var ph := HBoxContainer.new()
	ph.add_theme_constant_override("separation", 14)
	pc.add_child(ph)
	var portrait := TextureRect.new()
	portrait.texture = load(DataDB.data["classes"][GameState.active_class].get("sprite", ""))
	portrait.custom_minimum_size = Vector2(110, 110)
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ph.add_child(portrait)
	var pv := VBoxContainer.new()
	pv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pv.add_theme_constant_override("separation", 6)
	ph.add_child(pv)
	var name_row := HBoxContainer.new()
	pv.add_child(name_row)
	_level_label = _label("", 26, UITheme.TEXT)
	_level_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_row.add_child(_level_label)
	name_row.add_child(_icon(ITEM_ICON % "potion", 36))
	_potion_label = _label("", 26, UITheme.TEXT)
	name_row.add_child(_potion_label)
	var gap := Control.new()
	gap.custom_minimum_size.x = 14
	name_row.add_child(gap)
	name_row.add_child(_icon(ITEM_ICON % "gold", 36))
	_gold_label = _label("", 26, UITheme.GOLD)
	name_row.add_child(_gold_label)
	var hp := _bar(UITheme.HP_PLAYER, 30)
	pv.add_child(hp[0])
	_hp_bar = hp[1]
	_hp_label = hp[2]
	var xp := _bar(Color("7fd4ff"), 14)
	pv.add_child(xp[0])
	_xp_bar = xp[1]
	xp[2].visible = false

	# ---- doors
	var mid := VBoxContainer.new()
	mid.size_flags_vertical = Control.SIZE_EXPAND_FILL
	mid.alignment = BoxContainer.ALIGNMENT_CENTER
	mid.add_theme_constant_override("separation", 10)
	_root.add_child(mid)
	_prompt = _label("", 34, UITheme.TEXT)
	_prompt.add_theme_font_override("font", UITheme.title_font())
	_prompt.add_theme_color_override("font_outline_color", UITheme.INK)
	_prompt.add_theme_constant_override("outline_size", 10)
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mid.add_child(_prompt)
	_doors = HBoxContainer.new()
	_doors.alignment = BoxContainer.ALIGNMENT_CENTER
	_doors.add_theme_constant_override("separation", 30)
	mid.add_child(_doors)

	# ---- bottom bar
	var bottom := MarginContainer.new()
	for side in ["left", "right"]:
		bottom.add_theme_constant_override("margin_" + side, 24)
	bottom.add_theme_constant_override("margin_bottom", 34)
	_root.add_child(bottom)
	_escape_button = _button(DataDB.t("map.escape"), ITEM_ICON % "flee", _on_escape_pressed)
	_escape_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_escape_button.custom_minimum_size = Vector2(220, 80)
	bottom.add_child(_escape_button)

	_toast_box = VBoxContainer.new()
	_toast_box.add_theme_constant_override("separation", 8)
	_toast_box.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_toast_box.position.y = 380
	_toast_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_toast_box)

	_modal_layer = Control.new()
	_modal_layer.set_anchors_preset(Control.PRESET_FULL_RECT)
	_modal_layer.visible = false
	add_child(_modal_layer)

	_fade = ColorRect.new()
	_fade.color = Color(0, 0, 0, 0)
	_fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade.mouse_filter = Control.MOUSE_FILTER_STOP
	_fade.visible = false
	add_child(_fade)


func run_def_name() -> String:
	return run.def.get("name_key", run.dungeon_id)


func _button(text: String, icon_path: String, on_press: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size.y = 84
	b.add_theme_font_size_override("font_size", 28)
	if icon_path != "":
		b.icon = load(icon_path)
		b.add_theme_constant_override("icon_max_width", 44)
	b.pressed.connect(on_press)
	return b


func _icon(path: String, px: int) -> TextureRect:
	var t := TextureRect.new()
	t.texture = load(path)
	t.custom_minimum_size = Vector2(px, px)
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	return t


## Returns [container, bar, label], same look as the battle bars.
func _bar(color: Color, height: int) -> Array:
	var holder := Control.new()
	holder.custom_minimum_size.y = height
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.set_anchors_preset(Control.PRESET_FULL_RECT)
	bar.add_theme_stylebox_override("fill", UITheme.skin_bar_fill_tinted(color))
	holder.add_child(bar)
	var l := UITheme.stage_label(_label("", int(height * 0.7), UITheme.TEXT), int(height * 0.7))
	l.set_anchors_preset(Control.PRESET_FULL_RECT)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	holder.add_child(l)
	return [holder, bar, l]


func _label(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## "Yıldızlar ★ ★ ☆", with stars earned for the first time on this run shown bigger.
func _stars_line(stars: Array, new_stars: Array) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 10)
	h.add_child(_label(DataDB.t("run.stars"), 24, UITheme.TEXT_MUTED))
	for i in stars.size():
		var star := _label("★" if stars[i] else "☆", 44 if new_stars.has(i) else 32,
				UITheme.GOLD if stars[i] else UITheme.TEXT_MUTED)
		h.add_child(star)
		if new_stars.has(i):
			Audio.play("star")
			star.pivot_offset = Vector2(16, 22)
			var tw := star.create_tween().set_loops(3)
			tw.tween_property(star, "scale", Vector2(1.25, 1.25), 0.25)
			tw.tween_property(star, "scale", Vector2.ONE, 0.25)
	if not new_stars.is_empty():
		h.add_child(_label(DataDB.t("run.new_star"), 22, UITheme.GOLD))
	return h


## The end of the story (docs/07): the dragon egg, then the usual summary.
func _show_ending(reward: Dictionary) -> void:
	Audio.music("ending")
	var body := _modal(DataDB.t("ending.title"), EVENT_ART % "dragon_egg", DataDB.t("ending.text"))
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 16)
	body.add_child(row)
	row.add_child(ItemUI.tile(reward, 110))
	var info := VBoxContainer.new()
	info.add_child(UIKit.label(DataDB.t("run.reward"), 22, UITheme.TEXT_MUTED))
	info.add_child(UIKit.label(ItemUI.item_name(reward), 28, ItemUI.color(reward)))
	row.add_child(info)
	var done := [false]
	var go := UIKit.primary(_button(DataDB.t("story.continue"), "", func() -> void: done[0] = true))
	body.add_child(go)
	while not done[0]:
		await get_tree().process_frame

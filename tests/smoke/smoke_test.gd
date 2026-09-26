extends Node
## Smoke test: plays the real game screens end to end, the way a player taps through them,
## and fails on any engine or script error. The unit tests cover the rules; this catches
## screens that break at runtime (a null on entering a dungeon once left the phone on a
## gray screen while every unit test passed).
##
##   godot --headless res://tests/smoke/smoke_test.tscn
##
## For every dungeon it opens each town panel, walks in through the Dungeon Gate, picks
## doors, fights every battle with the skill buttons, answers treasure/event/rest rooms
## and the end-of-run screens, and goes back to town. Enemies are kept at 1 HP and the
## player at full HP so the whole run finishes quickly; the screens still run for real.

const TOWN := "res://src/scenes/town/town.tscn"
const PANELS := ["bag", "smith", "merchant", "inn", "class_master", "settings", "gate"]
const CLASSES := ["warrior", "mage", "rogue"]
## Frames a single step may take before the test calls it stuck.
const STEP_LIMIT := 3000
const SPEED := 8.0


class Catcher extends Logger:
	var errors: Array[String] = []
	var _lock := Mutex.new()

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, script_backtraces: Array[ScriptBacktrace]) -> void:
		if error_type == ERROR_TYPE_WARNING:
			return
		var where := "%s:%d %s" % [file, line, function]
		if not script_backtraces.is_empty() and script_backtraces[0].get_frame_count() > 0:
			var bt := script_backtraces[0]
			where = "%s:%d %s" % [bt.get_frame_file(0), bt.get_frame_line(0), bt.get_frame_function(0)]
		_lock.lock()
		errors.append("%s | %s" % [rationale if rationale != "" else code, where.strip_edges()])
		_lock.unlock()

	func _log_message(_message: String, _error: bool) -> void:
		pass


var _catcher := Catcher.new()
var _driver := false
var _step := ""
var _rooms := {}


func _ready() -> void:
	if _driver:
		_run.call_deferred()
		return
	# the scene tree frees this node on the first scene change, so a copy drives from the root
	var d: Node = get_script().new()
	d._driver = true
	d.name = "SmokeDriver"
	get_tree().root.add_child.call_deferred(d)


func _run() -> void:
	OS.add_logger(_catcher)
	SaveManager.path = "user://smoke_save.json"
	if FileAccess.file_exists(SaveManager.path):
		DirAccess.remove_absolute(SaveManager.path)
	Settings.language = "tr"
	DataDB.load_text("tr")
	var dungeons: Array = DataDB.data["dungeons"].keys()
	for i in dungeons.size():
		var cls: String = CLASSES[i % CLASSES.size()]
		_step = "%s as %s" % [dungeons[i], cls]
		print("smoke: ", _step)
		GameState.profile = _profile(dungeons[i], cls)
		GameState.run = null
		GameState.save()
		if not await _play_dungeon(dungeons[i]):
			break
	_finish()


## A profile standing at `dungeon` with everything before it cleared and every hint seen,
## except on the first dungeon, where the tutorial and story play as for a new player.
func _profile(dungeon: String, cls: String) -> Profile:
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	var p := Profile.new_game(DataDB.data, rng)
	for id in DataDB.data["dungeons"]:
		if id == dungeon:
			break
		p.dungeons[id] = {"runs": 1, "cleared": true, "stars": [true, true, true]}
	if cls != "warrior":
		p.unlock_class(cls)
		p.switch_class(cls)
	p.set_progress(int(DataDB.data["dungeons"][dungeon]["level_max"]), 0)
	return p


func _play_dungeon(dungeon: String) -> bool:
	get_tree().change_scene_to_file(TOWN)
	var town: Node = await _wait_scene("Town")
	if town == null:
		return false
	for kind in PANELS:
		await _dismiss_dialogs()
		town.open_panel(kind)
		await _frames(4)
		if kind != "gate":
			town._close_overlay()
			await _frames(2)
	var gate := _find(town, "GatePanel")
	if gate == null:
		return _fail("the Dungeon Gate panel did not open")
	gate.enter.emit(dungeon, false)
	var map: Node = await _wait_scene("Dungeon")
	if map == null:
		return false
	var run: DungeonRun = map.run
	var steps := 0
	while get_tree().current_scene == map:
		steps += 1
		if steps > STEP_LIMIT or not _catcher.errors.is_empty():
			return _fail("stuck in the dungeon (room %d)" % run.room_number)
		Engine.time_scale = SPEED
		await _dismiss_dialogs()
		if map._busy:
			await _frames(1)
		elif map._battle != null:
			await _battle_turn(map._battle)
		elif map._modal_layer.visible:
			await _press_first_button(map._modal_layer)
		else:
			await _pick_door(map)
	Engine.time_scale = 1.0
	print("smoke:   %s after %d rooms" % [run.outcome, run.history.size()])
	# the summary's "Back to town" button leads here
	return await _wait_scene("Town") != null


func _battle_turn(battle: Node) -> void:
	var engine: CombatEngine = battle.engine
	if engine == null or battle.busy:
		await _frames(1)
		return
	if engine.finished:
		if battle._result_layer.visible:
			battle._on_result_pressed()
		await _frames(2)
		return
	engine.player.hp = engine.player.stats.hp
	for e in engine.alive_enemies():
		e.hp = mini(e.hp, 1)
		e.shield = 0
	for id in engine.player.skills:
		var b: Button = battle._skill_buttons.get(id)
		if b != null and not b.disabled and engine.can_use(id):
			b.pressed.emit()
			await _frames(2)
			return
	battle._defend_button.pressed.emit()
	await _frames(2)


func _pick_door(map: Node) -> void:
	var doors: Array = map._doors.get_children().filter(func(c: Node) -> bool: return not c.is_queued_for_deletion())
	if doors.is_empty():
		await _frames(1)
		return
	# alternate fights with treasure/event/rest rooms, so every kind of room gets opened
	var want_fight: bool = map.run.room_number % 2 == 1
	var pick: int = 0
	for i in map.run.choices.size():
		if (map.run.choices[i]["type"] in ["combat", "elite", "boss"]) == want_fight:
			pick = i
			break
	_rooms[map.run.choices[pick]["type"]] = true
	if pick < doors.size():
		doors[pick].pressed.emit()
	await _frames(2)


func _press_first_button(layer: Node) -> void:
	for b in _buttons(layer):
		b.pressed.emit()
		await _frames(3)
		return
	await _frames(1)


func _buttons(node: Node) -> Array[Button]:
	var out: Array[Button] = []
	for c in node.get_children():
		if c.is_queued_for_deletion():
			continue
		if c is Button and c.is_visible_in_tree() and not c.disabled:
			out.append(c)
		out.append_array(_buttons(c))
	return out


## Story scenes and coach hints wait for a tap; tap through them.
func _dismiss_dialogs() -> void:
	var tapped := false
	for n in get_tree().root.find_children("*", "", true, false):
		if n.is_queued_for_deletion():
			continue
		if n is StoryDialog:
			n._end()
			tapped = true
		elif n is Tutorial:
			n._close()
			tapped = true
	if tapped:
		await _frames(3)


func _wait_scene(name_: String) -> Node:
	for i in STEP_LIMIT:
		var s := get_tree().current_scene
		if s != null and s.name == name_ and s.is_node_ready():
			await _frames(3)
			return s
		if not _catcher.errors.is_empty():
			break
		await _frames(1)
	_fail("the %s screen never opened" % name_)
	return null


func _find(root: Node, class_name_: String) -> Node:
	for n in root.find_children("*", "", true, false):
		var s: Script = n.get_script()
		if s != null and s.get_global_name() == class_name_:
			return n
	return null


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _fail(why: String) -> bool:
	_catcher.errors.append("%s: %s" % [_step, why])
	return false


func _finish() -> void:
	Engine.time_scale = 1.0
	if FileAccess.file_exists(SaveManager.path):
		DirAccess.remove_absolute(SaveManager.path)
	if _catcher.errors.is_empty():
		print("smoke: all screens OK (rooms opened: %s)" % ", ".join(_rooms.keys()))
		get_tree().quit(0)
		return
	for e in _catcher.errors.slice(0, 20):
		printerr("smoke FAIL: ", e)
	get_tree().quit(1)

extends SceneTree
## Headless test runner:
##   godot --headless --import
##   godot --headless -s res://tests/run_tests.gd
## Runs every tests/test_*.gd file and exits with code 1 if anything failed.
## A script error inside a test (e.g. indexing an empty array) aborts that test
## without an assertion failing, so errors are captured through a Logger and
## count as failures too.


class ErrorCapture extends Logger:
	var errors: Array[String] = []
	var _mutex := Mutex.new()

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, _error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
		_mutex.lock()
		errors.append("%s (%s:%d in %s)" % [rationale if rationale != "" else code, file, line, function])
		_mutex.unlock()

	func take() -> Array[String]:
		_mutex.lock()
		var out := errors.duplicate()
		errors.clear()
		_mutex.unlock()
		return out


func _init() -> void:
	var capture := ErrorCapture.new()
	OS.add_logger(capture)
	var total := 0
	var failed: Array[String] = []
	var dir := DirAccess.open("res://tests")
	var files: Array[String] = []
	for f in dir.get_files():
		if f.begins_with("test_") and f.ends_with(".gd") and f != "test_case.gd":
			files.append(f)
	files.sort()
	for f in files:
		var script: GDScript = load("res://tests/" + f)
		if script == null or not script.can_instantiate():
			failed.append("%s: failed to load" % f)
			continue
		for m in script.get_script_method_list():
			var name: String = m["name"]
			if not name.begins_with("test_"):
				continue
			var inst: TestCase = script.new()
			inst._current = "%s::%s" % [f, name]
			capture.take()
			inst.call(name)
			for err in capture.take():
				inst.failures.append("%s: script error: %s" % [inst._current, err])
			total += 1
			if inst.failures.is_empty():
				print("  ok   ", inst._current)
			else:
				print("  FAIL ", inst._current)
				failed.append_array(inst.failures)
	OS.remove_logger(capture)
	print("")
	for msg in failed:
		print("FAIL ", msg)
	print("%d tests, %d failures" % [total, failed.size()])
	quit(1 if not failed.is_empty() or total == 0 else 0)

extends SceneTree
## Headless test runner:
##   godot --headless --import
##   godot --headless -s res://tests/run_tests.gd
## Runs every tests/test_*.gd file and exits with code 1 if anything failed.


func _init() -> void:
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
		for m in script.get_script_method_list():
			var name: String = m["name"]
			if not name.begins_with("test_"):
				continue
			var inst: TestCase = script.new()
			inst._current = "%s::%s" % [f, name]
			inst.call(name)
			total += 1
			if inst.failures.is_empty():
				print("  ok   ", inst._current)
			else:
				print("  FAIL ", inst._current)
				failed.append_array(inst.failures)
	print("")
	for msg in failed:
		print("FAIL ", msg)
	print("%d tests, %d failures" % [total, failed.size()])
	quit(1 if not failed.is_empty() or total == 0 else 0)

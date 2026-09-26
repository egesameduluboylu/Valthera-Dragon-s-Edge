extends Node
## Reads and writes the save file (docs/10 "Kayıt Sistemi"). The file is written to a
## temporary path first and then renamed, so a crash mid-write never breaks the save.

const SAVE_PATH := "user://save.json"

## Tests point this somewhere else so they never touch the real save.
var path: String = SAVE_PATH


func has_save() -> bool:
	return FileAccess.file_exists(path)


## The saved dictionary, or {} when there is no save or it cannot be read.
func load_save() -> Dictionary:
	if not has_save():
		return {}
	var text := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		push_warning("Save file is unreadable, starting a new game: %s" % path)
		return {}
	return parsed


func write_save(d: Dictionary) -> bool:
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_warning("Could not write save: %s" % error_string(FileAccess.get_open_error()))
		return false
	f.store_string(JSON.stringify(d, "\t"))
	f.close()
	var err := DirAccess.rename_absolute(tmp, path)
	if err != OK:
		push_warning("Could not replace save: %s" % error_string(err))
		return false
	return true


func delete_save() -> void:
	if has_save():
		DirAccess.remove_absolute(path)

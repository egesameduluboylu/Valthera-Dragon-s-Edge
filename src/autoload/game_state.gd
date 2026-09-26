extends Node
## Player profile for the current session. Saving comes in M3 (docs/12).

var active_class: String = "warrior"
var class_levels: Dictionary = {"warrior": 1}
## XP collected inside the current level, per class.
var xp: Dictionary = {"warrior": 0}
var gold: int = 0
var runs_cleared: int = 0


func level() -> int:
	return int(class_levels.get(active_class, 1))


func class_xp() -> int:
	return int(xp.get(active_class, 0))


func add_rewards(xp_amount: int, gold_amount: int) -> void:
	var r := Progression.add_xp(level(), class_xp(), xp_amount)
	_set_progress(r["level"], r["xp"])
	gold += gold_amount
	EventBus.xp_gained.emit(active_class, xp_amount)
	EventBus.gold_changed.emit(gold)


## Stores what a finished dungeon run earned: its class level, XP and the gold kept.
func apply_run(run: DungeonRun) -> void:
	_set_progress(run.level, run.class_xp)
	gold += run.gold_earned
	if run.outcome == "cleared":
		runs_cleared += 1
	EventBus.xp_gained.emit(active_class, run.xp_earned)
	EventBus.gold_changed.emit(gold)


func _set_progress(new_level: int, new_xp: int) -> void:
	var old := level()
	class_levels[active_class] = new_level
	xp[active_class] = new_xp
	if new_level > old:
		EventBus.level_up.emit(active_class, new_level)

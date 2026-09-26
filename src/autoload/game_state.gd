extends Node
## Player profile for the current session. Saving comes in M3 (docs/12).

var active_class: String = "warrior"
var class_levels: Dictionary = {"warrior": 1}
var gold: int = 0
var xp: Dictionary = {"warrior": 0}


func add_rewards(xp_amount: int, gold_amount: int) -> void:
	xp[active_class] = int(xp.get(active_class, 0)) + xp_amount
	gold += gold_amount
	EventBus.xp_gained.emit(active_class, xp_amount)
	EventBus.gold_changed.emit(gold)

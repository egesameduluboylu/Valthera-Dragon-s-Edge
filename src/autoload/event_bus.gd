extends Node
## Global signals for things several screens care about.

signal gold_changed(total: int)
signal xp_gained(class_id: String, amount: int)
signal level_up(class_id: String, new_level: int)

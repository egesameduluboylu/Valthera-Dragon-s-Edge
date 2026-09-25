class_name StatusEffect
extends RefCounted
## A status currently on a combatant (see docs/03 "Durum Etkileri").

var id: String
var turns: int = 1
var stacks: int = 1
## Applied during the owner's own turn: survives that turn's end without ticking down.
var fresh: bool = false
## Stun only: the skipped action has already been used up.
var skipped: bool = false
## Damage per tick (per stack for poison), fixed when applied.
var dot_amount: int = 0


func _init(p_id: String, p_turns: int, p_stacks: int = 1) -> void:
	id = p_id
	turns = p_turns
	stacks = p_stacks

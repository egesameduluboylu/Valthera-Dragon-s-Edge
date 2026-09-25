class_name DamageCalc
extends RefCounted
## Damage formula from docs/03 "Hasar Formülü".

const CRIT_MULT := 1.5
const VARIANCE_MIN := 0.9
const VARIANCE_MAX := 1.1


## Returns {"amount": int, "crit": bool, "miss": bool}.
static func roll(attacker: Combatant, defender: Combatant, power: float, element: String,
		status_defs: Dictionary, rng: RandomNumberGenerator, extra_mult: float = 1.0) -> Dictionary:
	if rng.randf() < defender.stats.dodge:
		return {"amount": 0, "crit": false, "miss": true}
	var crit := rng.randf() < attacker.stats.crit
	var variance := rng.randf_range(VARIANCE_MIN, VARIANCE_MAX)
	var amount := compute(attacker.effective_atk(status_defs), power, defender.effective_def(status_defs),
			defender.element_mult(element), CRIT_MULT if crit else 1.0, variance, extra_mult)
	return {"amount": amount, "crit": crit, "miss": false}


## Expected damage with no crit and no variance, used for enemy intent numbers.
static func estimate(attacker: Combatant, defender: Combatant, power: float, element: String,
		status_defs: Dictionary) -> int:
	return compute(attacker.effective_atk(status_defs), power, defender.effective_def(status_defs),
			defender.element_mult(element), 1.0, 1.0, 1.0)


static func compute(atk: float, power: float, def: float, element_mult: float, crit_mult: float,
		variance: float, extra_mult: float) -> int:
	var reduction := 100.0 / (100.0 + maxf(def, 0.0))
	return maxi(1, roundi(atk * power * reduction * element_mult * crit_mult * variance * extra_mult))

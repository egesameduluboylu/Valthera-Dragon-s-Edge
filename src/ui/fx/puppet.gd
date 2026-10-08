class_name Puppet
extends Node2D
## A cut-out character (docs/16): the parts of assets/rigs/<id>/ turned and moved every frame.
## The node's origin is the rig's feet point; scale it to the size wanted on screen.
##
## Idle motion (breathing, swaying hair and capes, flapping wings, bobbing pieces, pulsing
## glows) runs on its own. Actions blend in a pose on top: play("attack"), play("cast"),
## play("hit"), play("defend"), play("die"). Poses are written for a right-facing rig and
## are mirrored for left-facing ones, so "forward" always means toward the opponent.

signal action_finished(action: String)

const RIG_DIR := "res://assets/rigs/%s/"

## Pose angles in degrees by role (or part name); "move" shifts the whole body in canvas pixels.
const POSES := {
	"windup": {"root": -6, "torso": -8, "head": -4, "arm_front_upper": 60, "arm_front_lower": 30,
			"weapon": 10, "arm_back_upper": 20, "arm_back_lower": 10, "leg_front_upper": 10,
			"leg_back_upper": -10, "leg_front": 6, "leg_back": -6, "hair": 12, "cape": 14, "tail": -14,
			"wing_front": 28, "wing_back": -22, "jaw": 14, "move": Vector2(-30, 0)},
	"strike": {"root": 8, "torso": 10, "head": 4, "arm_front_upper": -70, "arm_front_lower": -10,
			"weapon": -10, "arm_back_upper": -15, "leg_front_upper": -14, "leg_back_upper": 14,
			"leg_front": -8, "leg_back": 8, "hair": -16, "cape": -20, "tail": 18, "wing_front": -30,
			"wing_back": 24, "jaw": 24, "move": Vector2(90, 0)},
	"cast": {"root": -3, "torso": -6, "head": -6, "arm_front_upper": -75, "arm_front_lower": -25,
			"weapon": -15, "arm_back_upper": -55, "arm_back_lower": -30, "offhand": -10, "hair": 10,
			"cape": 12, "wing_front": 20, "wing_back": -16, "jaw": 18, "tail": 10, "move": Vector2(-10, -6)},
	"hit": {"root": -10, "torso": -12, "head": -14, "arm_front_upper": 25, "arm_front_lower": 15,
			"arm_back_upper": 20, "hair": 16, "cape": 18, "tail": -12, "wing_front": 18, "wing_back": -10,
			"jaw": 10, "move": Vector2(-40, 0)},
	"defend": {"root": -4, "torso": -6, "head": -3, "arm_back_upper": -50, "arm_back_lower": -40,
			"offhand": -10, "arm_front_upper": 20, "arm_front_lower": -30, "wing_front": 30, "wing_back": 26,
			"move": Vector2(-14, 4)},
}

var rig_id := ""
var rig: Dictionary = {}
## Idle strength: 1 normal, higher when excited (low HP enemies twitch more).
var liveliness := 1.0
var height := 1.0  ## figure height in canvas pixels (feet to the top of the tallest part)
var width := 1.0

var _parts: Array = []        # [{name, role, parent_index, pivot, sprite, rect_pos, phase, chain, blend}]
var _flip := 1.0              # -1 for left-facing rigs
var _t := 0.0
var _pose_a: Dictionary = {}
var _pose_b: Dictionary = {}
var _weight := 0.0            # how much the action pose applies (tweened)
var _blend := 0.0             # 0 = pose a, 1 = pose b (tweened)
var _action_tween: Tween
var _dead := false
var _action := ""


static func has_rig(id: String) -> bool:
	return id != "" and FileAccess.file_exists(RIG_DIR % id + "rig.json")


func _init(id: String = "") -> void:
	if id != "":
		load_rig(id)


func load_rig(id: String) -> bool:
	rig_id = id
	var text := FileAccess.get_file_as_string(RIG_DIR % id + "rig.json")
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		push_error("Puppet: bad rig %s" % id)
		return false
	rig = parsed
	for c in get_children():
		c.queue_free()
	_parts.clear()
	_flip = -1.0 if rig.get("facing", "left") == "left" else 1.0
	var feet := Vector2(rig["feet"][0], rig["feet"][1])
	var index := {}
	var order: Array = rig["parts"].duplicate()
	var top := feet.y
	var left := feet.x
	var right := feet.x
	var chain := {}
	for i in order.size():
		var p: Dictionary = order[i]
		var pivot := Vector2(p["pivot"][0], p["pivot"][1])
		var r: Array = p["rect"]
		if p.get("blend", "normal") != "add":
			top = minf(top, r[1])
			left = minf(left, r[0])
			right = maxf(right, r[0] + r[2])
		var parent_i: int = index.get(p["parent"], -1)
		var role: String = p["role"]
		# links of a tail (or any chain of one role) sway one after another
		var link := 0
		if parent_i >= 0 and _parts[parent_i]["role"] == role:
			link = _parts[parent_i]["chain"] + 1
		index[p["name"]] = i
		_parts.append({"name": p["name"], "role": role, "parent": parent_i, "pivot": pivot,
				"rect_pos": Vector2(r[0], r[1]) - feet, "z": int(p["z"]), "chain": link,
				"phase": float(abs(hash(p["name"])) % 628) / 100.0, "add": p.get("blend", "normal") == "add",
				"sprite": null})
	height = maxf(1.0, feet.y - top)
	width = maxf(1.0, right - left)
	# sprites in draw order; transforms are computed per frame, so nesting is not needed
	var by_z := range(_parts.size())
	by_z.sort_custom(func(a: int, b: int) -> bool: return _parts[a]["z"] < _parts[b]["z"])
	for i in by_z:
		var part: Dictionary = _parts[i]
		var s := Sprite2D.new()
		s.centered = false
		s.texture = load(RIG_DIR % id + rig["parts"][i]["png"])
		if part["add"]:
			var mat := CanvasItemMaterial.new()
			mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
			s.material = mat
		add_child(s)
		part["sprite"] = s
	# pivots relative to the feet
	for part in _parts:
		part["pivot"] = part["pivot"] - feet
	_update()
	return true


## Scale that fits the figure into a box of `size` (screen pixels).
func fit_scale(box: Vector2) -> float:
	return minf(box.y / height, box.x / width)


func _process(delta: float) -> void:
	if _parts.is_empty():
		return
	_t += delta
	_update()


func _angle(part: Dictionary, pose: Dictionary) -> float:
	if pose.has(part["name"]):
		return pose[part["name"]]
	return pose.get(part["role"], 0.0)


func _idle(part: Dictionary) -> Array:
	## [degrees, offset] of the idle motion for one part.
	var t := _t
	var ph: float = part["phase"]
	var k := liveliness
	var breath := sin(t * 1.7)
	match part["role"]:
		"root":
			return [0.8 * breath * k, Vector2(0, -height * 0.006 * (breath + 1.0) * k)]
		"torso":
			return [1.4 * sin(t * 1.7 + 0.3) * k, Vector2.ZERO]
		"head":
			return [2.4 * sin(t * 1.7 + 0.8) * k + 1.0 * sin(t * 0.6 + ph), Vector2.ZERO]
		"jaw":
			return [maxf(0.0, 7.0 * sin(t * 0.9 + ph)) * k, Vector2.ZERO]
		"hair":
			return [6.0 * sin(t * 2.3 + ph) * k, Vector2.ZERO]
		"cape":
			return [(5.0 * sin(t * 1.9 + ph) + 2.5 * sin(t * 3.3 + ph)) * k, Vector2.ZERO]
		"arm_front_upper", "arm_back_upper":
			var s := 1.0 if part["role"] == "arm_front_upper" else -1.0
			return [3.0 * s * sin(t * 1.7 + 0.5) * k, Vector2.ZERO]
		"arm_front_lower", "arm_back_lower":
			return [4.0 * sin(t * 1.7 + 0.9) * k, Vector2.ZERO]
		"weapon", "offhand":
			return [2.5 * sin(t * 1.7 + 1.2) * k, Vector2.ZERO]
		"leg_front_upper", "leg_back_upper", "leg_front", "leg_back":
			return [0.8 * sin(t * 1.7 + ph) * k, Vector2.ZERO]
		"tail":
			return [(7.0 + part["chain"] * 2.0) * sin(t * 2.0 - part["chain"] * 0.7 + ph) * k, Vector2.ZERO]
		"wing_front", "wing_back":
			var amp := 16.0 if rig.get("kind", "") in ["flyer", "dragon"] else 6.0
			var lag := 0.35 if part["role"] == "wing_back" else 0.0
			return [amp * sin(t * 2.6 - lag) * k, Vector2.ZERO]
		"float":
			return [4.0 * sin(t * 1.1 + ph), Vector2(3.0 * sin(t * 0.9 + ph), 12.0 * sin(t * 1.4 + ph))]
	return [0.0, Vector2.ZERO]


func _update() -> void:
	var xforms: Array[Transform2D] = []
	xforms.resize(_parts.size())
	for i in _parts.size():
		var part: Dictionary = _parts[i]
		var idle := _idle(part)
		var deg: float = idle[0]
		var off: Vector2 = idle[1]
		if _weight > 0.0:
			var a := lerpf(_angle(part, _pose_a), _angle(part, _pose_b), _blend)
			deg += a * _weight
			if part["parent"] < 0:
				var ma: Vector2 = _pose_a.get("move", Vector2.ZERO)
				var mb: Vector2 = _pose_b.get("move", Vector2.ZERO)
				off += ma.lerp(mb, _blend) * _weight
		off.x *= _flip
		var pivot: Vector2 = part["pivot"]
		var local := Transform2D(deg_to_rad(deg * _flip), pivot + off) * Transform2D(0.0, -pivot)
		var parent_i: int = part["parent"]
		xforms[i] = (xforms[parent_i] * local) if parent_i >= 0 else local
		var s: Sprite2D = part["sprite"]
		s.transform = xforms[i] * Transform2D(0.0, part["rect_pos"])
		if part["add"] or part["role"] == "fx":
			s.self_modulate = Color(1, 1, 1, 0.7 + 0.3 * sin(_t * 3.1 + part["phase"])) * (1.0 + 0.35 * _weight)
		# breath parts (a dragon's frost or fire breath) show only while it attacks or casts
		if part["name"].begins_with("breath"):
			s.modulate.a = clampf(_weight, 0.0, 1.0) if _action in ["attack", "cast"] else 0.0


## Plays an action pose on top of the idle motion. Returns its length in seconds.
func play(action: String) -> float:
	if _dead:
		return 0.0
	if _action_tween != null and _action_tween.is_valid():
		_action_tween.kill()
	var tw := create_tween()
	_action_tween = tw
	var length := 0.0
	_action = action
	match action:
		"attack":
			_pose_a = POSES["windup"]
			_pose_b = POSES["strike"]
			_blend = 0.0
			tw.tween_method(_set_weight, _weight, 1.0, 0.16).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
			tw.tween_method(_set_blend, 0.0, 1.0, 0.09).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
			tw.tween_interval(0.08)
			tw.tween_method(_set_weight, 1.0, 0.0, 0.3).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
			length = 0.63
		"cast", "defend":
			_pose_a = POSES[action]
			_pose_b = POSES[action]
			tw.tween_method(_set_weight, _weight, 1.0, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_interval(0.2 if action == "cast" else 0.35)
			tw.tween_method(_set_weight, 1.0, 0.0, 0.3).set_trans(Tween.TRANS_SINE)
			length = 0.68 if action == "cast" else 0.83
		"hit":
			_pose_a = POSES["hit"]
			_pose_b = POSES["hit"]
			tw.tween_method(_set_weight, _weight, 1.0, 0.06).set_ease(Tween.EASE_OUT)
			tw.tween_method(_set_weight, 1.0, 0.0, 0.35).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
			length = 0.41
		"die":
			_dead = true
			_pose_a = POSES["hit"]
			_pose_b = POSES["hit"]
			tw.tween_method(_set_weight, _weight, 1.4, 0.25).set_ease(Tween.EASE_OUT)
			tw.parallel().tween_property(self, "liveliness", 0.0, 0.5)
			length = 0.25
	tw.tween_callback(func() -> void: action_finished.emit(action))
	return length


func _set_weight(v: float) -> void:
	_weight = v


func _set_blend(v: float) -> void:
	_blend = v

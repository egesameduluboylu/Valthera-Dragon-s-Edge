class_name BattleFx
extends RefCounted
## One-shot battle effects (docs/16): impact bursts, flashes, slashes and flying spells.
## Colours above 1.0 glow: the battle stage renders in HDR with bloom.

const ELEMENT_COLORS := {
	"physical": Color(2.2, 2.1, 1.9),
	"fire": Color(2.6, 1.2, 0.35),
	"ice": Color(0.9, 1.9, 2.6),
	"lightning": Color(1.9, 1.9, 2.8),
	"shadow": Color(1.6, 0.8, 2.6),
	"poison": Color(0.8, 2.4, 0.6),
	"holy": Color(2.6, 2.3, 1.2),
}

static var _dot: Texture2D


static func color(element: String) -> Color:
	return ELEMENT_COLORS.get(element, ELEMENT_COLORS["physical"])


static func dot() -> Texture2D:
	if _dot == null:
		var g := Gradient.new()
		g.offsets = PackedFloat32Array([0.0, 0.25, 1.0])
		g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.7), Color(1, 1, 1, 0)])
		var t := GradientTexture2D.new()
		t.gradient = g
		t.fill = GradientTexture2D.FILL_RADIAL
		t.fill_from = Vector2(0.5, 0.5)
		t.fill_to = Vector2(1.0, 0.5)
		t.width = 64
		t.height = 64
		_dot = t
	return _dot


static func _add_mat() -> CanvasItemMaterial:
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	return m


## A burst of sparks flying out from `pos`.
static func burst(parent: Node, pos: Vector2, col: Color, amount: int = 26, speed: float = 380.0,
		size: float = 9.0, life: float = 0.55, gravity: float = 400.0) -> void:
	var p := CPUParticles2D.new()
	p.texture = dot()
	p.material = _add_mat()
	p.position = pos
	p.one_shot = true
	p.explosiveness = 0.95
	p.amount = amount
	p.lifetime = life
	p.direction = Vector2.UP
	p.spread = 180.0
	p.initial_velocity_min = speed * 0.35
	p.initial_velocity_max = speed
	p.gravity = Vector2(0, gravity)
	p.damping_min = 80.0
	p.damping_max = 200.0
	p.scale_amount_min = size / 64.0
	p.scale_amount_max = size * 2.2 / 64.0
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 0.6, 1.0])
	ramp.colors = PackedColorArray([col, Color(col, 0.8), Color(col, 0.0)])
	p.color_ramp = ramp
	parent.add_child(p)
	p.emitting = true
	p.finished.connect(p.queue_free)


## A soft round flash that swells and fades.
static func flash(parent: Node, pos: Vector2, col: Color, radius: float = 90.0, time: float = 0.35) -> void:
	var s := Sprite2D.new()
	s.texture = dot()
	s.material = _add_mat()
	s.position = pos
	s.modulate = col
	s.scale = Vector2.ONE * radius / 64.0
	parent.add_child(s)
	var tw := s.create_tween().set_parallel()
	tw.tween_property(s, "scale", Vector2.ONE * radius * 2.4 / 32.0, time).set_ease(Tween.EASE_OUT)
	tw.tween_property(s, "modulate:a", 0.0, time)
	tw.chain().tween_callback(s.queue_free)


## A bright crescent swipe across `pos` (sword and dagger hits).
static func slash(parent: Node, pos: Vector2, col: Color, size: float = 150.0, flip: bool = false) -> void:
	var line := Line2D.new()
	line.material = _add_mat()
	line.width = size * 0.16
	var curve := Curve.new()
	curve.add_point(Vector2(0, 0))
	curve.add_point(Vector2(0.5, 1))
	curve.add_point(Vector2(1, 0))
	line.width_curve = curve
	line.default_color = col
	line.begin_cap_mode = Line2D.LINE_CAP_ROUND
	line.end_cap_mode = Line2D.LINE_CAP_ROUND
	var pts := PackedVector2Array()
	for i in 13:
		var a := lerpf(-2.3, -0.5, i / 12.0)
		pts.append(Vector2(cos(a), sin(a)) * size * 0.5)
	line.points = pts
	line.position = pos + Vector2(0, size * 0.2)
	line.rotation = 0.5 if not flip else PI - 0.5
	line.scale = Vector2(0.6, 0.6)
	parent.add_child(line)
	var tw := line.create_tween().set_parallel()
	tw.tween_property(line, "scale", Vector2(1.15, 1.15), 0.18).set_ease(Tween.EASE_OUT)
	tw.tween_property(line, "rotation", line.rotation + (0.5 if not flip else -0.5), 0.18)
	tw.tween_property(line, "modulate:a", 0.0, 0.22).set_delay(0.08)
	tw.chain().tween_callback(line.queue_free)


## A glowing orb that flies from `from` to `to` with a trail. Returns the flight time.
static func projectile(parent: Node, from: Vector2, to: Vector2, col: Color, time: float = 0.28,
		radius: float = 26.0) -> float:
	var orb := Sprite2D.new()
	orb.texture = dot()
	orb.material = _add_mat()
	orb.modulate = col
	orb.scale = Vector2.ONE * radius / 32.0
	orb.position = from
	parent.add_child(orb)
	var trail := CPUParticles2D.new()
	trail.texture = dot()
	trail.material = _add_mat()
	trail.amount = 40
	trail.lifetime = 0.35
	trail.local_coords = false
	trail.spread = 180.0
	trail.initial_velocity_min = 5.0
	trail.initial_velocity_max = 40.0
	trail.gravity = Vector2.ZERO
	trail.scale_amount_min = radius * 0.5 / 64.0
	trail.scale_amount_max = radius * 1.1 / 64.0
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 1.0])
	ramp.colors = PackedColorArray([Color(col, 0.9), Color(col, 0.0)])
	trail.color_ramp = ramp
	orb.add_child(trail)
	# the orb scale must not shrink the trail
	trail.scale = Vector2.ONE / orb.scale
	var mid := (from + to) * 0.5 + Vector2(0, -80)
	var tw := orb.create_tween()
	tw.tween_method(func(t: float) -> void:
		orb.position = from.lerp(mid, t).lerp(mid.lerp(to, t), t), 0.0, 1.0, time)
	tw.tween_callback(func() -> void:
		trail.emitting = false
		orb.visible = false)
	tw.tween_interval(0.4)
	tw.tween_callback(orb.queue_free)
	return time


## The full hit effect for an element at `pos`.
static func impact(parent: Node, pos: Vector2, element: String, crit: bool = false, melee: bool = false) -> void:
	var col := color(element)
	var k := 1.35 if crit else 1.0
	flash(parent, pos, Color(col, 0.9), 70.0 * k)
	if melee:
		slash(parent, pos, col, 170.0 * k, randf() < 0.5)
	match element:
		"fire":
			burst(parent, pos, col, int(34 * k), 420.0, 10.0, 0.6, -120.0)
		"ice":
			burst(parent, pos, col, int(26 * k), 460.0, 7.0, 0.5, 500.0)
		"lightning":
			burst(parent, pos, col, int(30 * k), 620.0, 5.0, 0.3, 0.0)
		"shadow", "poison":
			burst(parent, pos, col, int(28 * k), 260.0, 12.0, 0.8, -60.0)
		_:
			burst(parent, pos, col, int(18 * k), 520.0, 6.0, 0.35, 600.0)


## A cone of breath from `from` toward `to` (the companion dragon).
static func breath(parent: Node, from: Vector2, to: Vector2, col: Color, time: float = 0.5) -> void:
	var p := CPUParticles2D.new()
	p.texture = dot()
	p.material = _add_mat()
	p.position = from
	p.amount = 90
	p.lifetime = 0.55
	p.one_shot = false
	var dir := (to - from).normalized()
	p.direction = dir
	p.spread = 12.0
	var dist := from.distance_to(to)
	p.initial_velocity_min = dist * 1.2
	p.initial_velocity_max = dist * 1.8
	p.gravity = Vector2.ZERO
	p.scale_amount_min = 12.0 / 64.0
	p.scale_amount_max = 34.0 / 64.0
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.4))
	sc.add_point(Vector2(1, 1.6))
	p.scale_amount_curve = sc
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 0.5, 1.0])
	ramp.colors = PackedColorArray([Color(col, 1.0), Color(col, 0.7), Color(col, 0.0)])
	p.color_ramp = ramp
	parent.add_child(p)
	p.emitting = true
	var tw := p.create_tween()
	tw.tween_interval(time)
	tw.tween_callback(func() -> void: p.emitting = false)
	tw.tween_interval(0.7)
	tw.tween_callback(p.queue_free)

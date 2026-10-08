class_name Backdrop
extends Node2D
## A living background (docs/16): the painted layers of assets/backgrounds/v2/<id>/ (or
## assets/town/v2/) with slow parallax drift, moving light shafts, pulsing light sources and
## particles where the scene's fx.json asks for them (dust, embers, spores, snow, ...).
##
## Layers are 1920 x 1080. The picture is scaled to cover the view and placed so that the
## scene's ground line lands on `ground_line` (view pixels), which keeps the fighters' feet
## on the painted floor on every screen shape.

const W := 1920.0
const H := 1080.0
const LAYERS := ["far", "mid", "near", "rays", "glow"]

var view_size := Vector2(1280, 720)
var ground_line := 520.0
## Multiplies the particle amount (the settings' low effects option can lower it).
var density := 1.0

var _scale := 1.0
var _origin := Vector2.ZERO
var _layers := {}
var _fx: Dictionary = {}
var _t := 0.0
var _dot: Texture2D


## dir: a folder with far/mid/near/rays/glow.png and fx.json; fallback: a single picture used
## when the folder has no layers.
func setup(dir: String, fallback: String, p_view: Vector2, p_ground_line: float) -> void:
	view_size = p_view
	ground_line = p_ground_line
	for c in get_children():
		c.queue_free()
	_layers.clear()
	_fx = {}
	if dir != "" and FileAccess.file_exists(dir.path_join("fx.json")):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("fx.json")))
		if parsed is Dictionary:
			_fx = parsed
	var has_layers := dir != "" and ResourceLoader.exists(dir.path_join("far.png"))
	var ground_y := float(_fx.get("ground_y", 780))
	# a little overscan, so screen shakes and the parallax drift never show an edge
	_scale = maxf((view_size.x + 48.0) / W, (view_size.y + 48.0) / H)
	_origin = Vector2((view_size.x - W * _scale) * 0.5, ground_line - ground_y * _scale)
	_origin.y = clampf(_origin.y, view_size.y + 24.0 - H * _scale, -24.0)
	if has_layers:
		for name in LAYERS:
			var path := dir.path_join(name + ".png")
			if not ResourceLoader.exists(path):
				continue
			var s := Sprite2D.new()
			s.texture = load(path)
			s.centered = false
			s.scale = Vector2(_scale, _scale) * (W / s.texture.get_width())
			s.position = _origin
			if name in ["rays", "glow"]:
				var mat := CanvasItemMaterial.new()
				mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
				s.material = mat
			add_child(s)
			_layers[name] = s
		# particles go between the scenery and the foreground framing
		if _layers.has("near"):
			move_child(_layers["near"], get_child_count() - 1)
	elif fallback != "" and ResourceLoader.exists(fallback):
		var s := Sprite2D.new()
		s.texture = load(fallback)
		s.centered = false
		var tex := s.texture.get_size()
		var k := maxf((view_size.x + 48.0) / tex.x, (view_size.y + 48.0) / tex.y)
		s.scale = Vector2(k, k)
		s.position = (view_size - tex * k) * 0.5
		add_child(s)
		_layers["flat"] = s
		if _fx.is_empty():
			_fx = {"dust": [[0, 200, 1920, 700]]}
	_add_particles()
	if _layers.has("near"):
		move_child(_layers["near"], get_child_count() - 1)


## True when the painted layers were found (not just the fallback picture).
func has_layers() -> bool:
	return _layers.has("far") or _layers.has("mid")


## A point or rect of the painted scene in view pixels.
func to_view(p: Vector2) -> Vector2:
	return _origin + p * _scale


func _process(delta: float) -> void:
	_t += delta
	var drift := sin(_t * 0.13)
	if _layers.has("far"):
		_layers["far"].position = _origin + Vector2(drift * 6.0, 0)
	if _layers.has("mid"):
		_layers["mid"].position = _origin + Vector2(drift * 3.0, 0)
	if _layers.has("near"):
		_layers["near"].position = _origin + Vector2(-drift * 9.0, sin(_t * 0.4) * 2.0)
	if _layers.has("rays"):
		var r: Sprite2D = _layers["rays"]
		r.modulate = Color(1, 1, 1, 0.55 + 0.3 * sin(_t * 0.35) + 0.1 * sin(_t * 1.3))
		r.position = _origin + Vector2(sin(_t * 0.21) * 22.0, 0)
	if _layers.has("glow"):
		var flicker := 0.12 * sin(_t * 7.3) * sin(_t * 3.1 + 1.0) + 0.05 * sin(_t * 17.0)
		var g := 1.15 + 0.25 * sin(_t * 1.9) + flicker
		_layers["glow"].modulate = Color(g, g, g, 1.0)


# ---------------------------------------------------------------- particles

func _soft_dot() -> Texture2D:
	if _dot == null:
		var g := Gradient.new()
		g.offsets = PackedFloat32Array([0.0, 0.35, 1.0])
		g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.55), Color(1, 1, 1, 0)])
		var t := GradientTexture2D.new()
		t.gradient = g
		t.fill = GradientTexture2D.FILL_RADIAL
		t.fill_from = Vector2(0.5, 0.5)
		t.fill_to = Vector2(1.0, 0.5)
		t.width = 32
		t.height = 32
		_dot = t
	return _dot


func _rects(key: String) -> Array:
	var out: Array = []
	for r in _fx.get(key, []):
		if r is Array and r.size() >= 4:
			out.append(Rect2(to_view(Vector2(r[0], r[1])), Vector2(r[2], r[3]) * _scale))
		elif r is Array and r.size() >= 2:
			out.append(Rect2(to_view(Vector2(r[0], r[1])), Vector2.ZERO))
	return out


func _add_particles() -> void:
	for r in _rects("dust"):
		_emitter(r, 26, 9.0, Color(1.0, 0.95, 0.8, 0.35), Vector2(0, -4), 8.0, 2.5, 6.0)
	for r in _rects("embers"):
		_emitter(r, 30, 3.5, Color(2.2, 1.1, 0.35, 1.0), Vector2(0, -60), 30.0, 1.6, 4.0)
	for r in _rects("sparks"):
		_emitter(r, 18, 1.4, Color(2.6, 1.8, 0.7, 1.0), Vector2(0, -120), 70.0, 1.0, 2.5)
	for r in _rects("spores"):
		_emitter(r, 30, 7.0, Color(0.6, 1.6, 1.4, 0.8), Vector2(0, -12), 14.0, 2.0, 5.5)
	for r in _rects("snow"):
		_emitter(r, 60, 7.0, Color(1, 1, 1, 0.85), Vector2(-10, 55), 18.0, 1.5, 4.5)
	for r in _rects("ash"):
		_emitter(r, 36, 8.0, Color(0.55, 0.52, 0.5, 0.7), Vector2(6, 22), 10.0, 1.5, 4.0)
	for r in _rects("leaves"):
		_emitter(r, 10, 9.0, Color(0.95, 0.8, 0.35, 0.8), Vector2(18, 26), 12.0, 3.0, 6.0)
	for r in _rects("drips"):
		_emitter(Rect2(r.position, Vector2(4, 4)), 2, 1.6, Color(0.7, 0.9, 1.0, 0.8), Vector2(0, 260), 0.0, 1.5, 2.5)
	for r in _rects("smoke"):
		_emitter(Rect2(r.position - Vector2(10, 0), Vector2(20, 10)), 8, 6.0, Color(0.45, 0.45, 0.5, 0.35), Vector2(6, -30), 8.0, 14.0, 30.0)
	for r in _rects("torches"):
		_emitter(Rect2(r.position - Vector2(6, 10), Vector2(12, 10)), 10, 1.2, Color(2.4, 1.3, 0.45, 1.0), Vector2(0, -50), 20.0, 1.5, 3.5)
	# scene-wide sparkle of dust in the air, so every scene breathes a little
	if not _fx.has("dust"):
		_emitter(Rect2(Vector2(0, view_size.y * 0.15), Vector2(view_size.x, view_size.y * 0.6)), 14, 10.0,
				Color(1.0, 0.95, 0.85, 0.25), Vector2(0, -3), 6.0, 2.0, 4.5)


func _emitter(area: Rect2, amount: int, life: float, color: Color, velocity: Vector2, spread: float,
		size_min: float, size_max: float) -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.texture = _soft_dot()
	p.amount = maxi(1, roundi(amount * density))
	p.lifetime = life
	p.preprocess = life
	p.randomness = 0.6
	p.position = area.get_center()
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	p.emission_rect_extents = area.size * 0.5
	p.direction = velocity.normalized() if velocity != Vector2.ZERO else Vector2.UP
	p.spread = 25.0
	p.gravity = Vector2.ZERO
	p.initial_velocity_min = velocity.length() * 0.6
	p.initial_velocity_max = velocity.length() * 1.2 + spread
	p.scale_amount_min = size_min / 16.0
	p.scale_amount_max = size_max / 16.0
	var ramp := Gradient.new()
	ramp.offsets = PackedFloat32Array([0.0, 0.2, 0.75, 1.0])
	ramp.colors = PackedColorArray([Color(color, 0.0), color, color, Color(color, 0.0)])
	p.color_ramp = ramp
	p.orbit_velocity_min = -0.02
	p.orbit_velocity_max = 0.02
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD if color.r > 1.0 or color.g > 1.0 else CanvasItemMaterial.BLEND_MODE_MIX
	p.material = mat
	add_child(p)
	return p

extends Node
## Music and sound effects (docs/09), plus the player's settings for them and for
## vibration. Settings live in their own file so wiping a save keeps them.
## Missing audio files are skipped quietly, so the game runs without them.

const SETTINGS_PATH := "user://settings.json"
const SFX_PATH := "res://assets/audio/sfx/%s.wav"
const MUSIC_PATH := "res://assets/audio/music/%s.wav"
const SFX_VOICES := 8
const FADE := 0.6

var music_volume: float = 0.7
var sfx_volume: float = 0.9
var vibration: bool = true

var _players: Array[AudioStreamPlayer] = []
var _next: int = 0
var _music: AudioStreamPlayer
var _music_name: String = ""
var _cache: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in SFX_VOICES:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_players.append(p)
	_music = AudioStreamPlayer.new()
	add_child(_music)
	load_settings()
	EventBus.level_up.connect(func(_c: String, _l: int) -> void: play("level_up", 0.0))


func play(sfx_name: String, pitch_jitter: float = 0.05) -> void:
	var stream := _stream(SFX_PATH % sfx_name)
	if stream == null or sfx_volume <= 0.0:
		return
	var p := _players[_next]
	_next = (_next + 1) % _players.size()
	p.stream = stream
	p.volume_db = linear_to_db(sfx_volume)
	p.pitch_scale = 1.0 + randf_range(-pitch_jitter, pitch_jitter)
	p.play()


## Switches the looping music track with a short crossfade; the same track keeps playing.
func music(track: String) -> void:
	if track == _music_name:
		return
	_music_name = track
	var stream := _stream(MUSIC_PATH % track)
	var tw := create_tween()
	if _music.playing:
		tw.tween_property(_music, "volume_db", -40.0, FADE)
	tw.tween_callback(func() -> void:
		_music.stop()
		if stream == null:
			return
		_music.stream = stream
		_music.volume_db = -40.0
		_music.play())
	tw.tween_property(_music, "volume_db", _music_db(), FADE)


func vibrate(ms: int = 40) -> void:
	if vibration:
		Input.vibrate_handheld(ms)


func set_music_volume(v: float) -> void:
	music_volume = clampf(v, 0.0, 1.0)
	_music.volume_db = _music_db()
	save_settings()


func set_sfx_volume(v: float) -> void:
	sfx_volume = clampf(v, 0.0, 1.0)
	save_settings()


func set_vibration(on: bool) -> void:
	vibration = on
	save_settings()


func load_settings() -> void:
	if not FileAccess.file_exists(SETTINGS_PATH):
		return
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(SETTINGS_PATH))
	if d is Dictionary:
		music_volume = clampf(float(d.get("music", music_volume)), 0.0, 1.0)
		sfx_volume = clampf(float(d.get("sfx", sfx_volume)), 0.0, 1.0)
		vibration = bool(d.get("vibration", vibration))


func save_settings() -> void:
	var f := FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"music": music_volume, "sfx": sfx_volume, "vibration": vibration}))


func _music_db() -> float:
	return linear_to_db(maxf(music_volume, 0.0001))


func _stream(path: String) -> AudioStream:
	if not _cache.has(path):
		_cache[path] = load(path) if ResourceLoader.exists(path) else null
	return _cache[path]

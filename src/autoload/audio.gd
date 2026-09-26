extends Node
## Music and sound effects (docs/09) and vibration, at the volumes in Settings.
## Missing audio files are skipped quietly, so the game runs without them.

const SFX_PATH := "res://assets/audio/sfx/%s.wav"
const MUSIC_PATH := "res://assets/audio/music/%s.wav"
const SFX_VOICES := 8
const FADE := 0.6

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
	Settings.changed.connect(func(key: String) -> void:
		if key == "music":
			_music.volume_db = _music_db())
	EventBus.level_up.connect(func(_c: String, _l: int) -> void: play("level_up", 0.0))


func play(sfx_name: String, pitch_jitter: float = 0.05) -> void:
	var stream := _stream(SFX_PATH % sfx_name)
	if stream == null or Settings.sfx <= 0.0:
		return
	var p := _players[_next]
	_next = (_next + 1) % _players.size()
	p.stream = stream
	p.volume_db = linear_to_db(Settings.sfx)
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
	if Settings.vibration:
		Input.vibrate_handheld(ms)


func _music_db() -> float:
	return linear_to_db(maxf(Settings.music, 0.0001))


func _stream(path: String) -> AudioStream:
	if not _cache.has(path):
		_cache[path] = load(path) if ResourceLoader.exists(path) else null
	return _cache[path]

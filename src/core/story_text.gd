class_name StoryText
extends RefCounted
## Text keys for story.json scenes (docs/07), kept free of autoloads for tests.


## "story.<scene>.<n>" for Nara, "story.<scene>.<speaker>.<n>" for everyone else.
static func line_key(scene_id: String, speaker: String, n: int) -> String:
	if speaker == "nara":
		return "story.%s.%d" % [scene_id, n]
	return "story.%s.%s.%d" % [scene_id, speaker, n]

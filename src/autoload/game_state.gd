extends Node
## The player's profile for this session. The rules live in Profile (src/core); this
## autoload loads it at startup, saves it after every change and tells screens through
## EventBus.

var profile: Profile
var rng := RandomNumberGenerator.new()
## The run in progress, if any. Saved between rooms as profile.run_state.
var run: DungeonRun = null
## The player marketplace: LocalMarket, or SupabaseMarket when data/online.json is
## filled in. Call it with await (docs/13).
var market: Variant = null
## What happened to the player's market listings during the last run, for the town.
var market_news: Dictionary = {}


func _ready() -> void:
	rng.randomize()
	load_game()


var active_class: String:
	get:
		return profile.active_class


func level() -> int:
	return profile.level()


func class_xp() -> int:
	return profile.class_xp()


func load_game() -> void:
	var d := SaveManager.load_save()
	profile = Profile.from_dict(DataDB.data, d) if not d.is_empty() else Profile.new_game(DataDB.data, rng)
	_make_market()
	if d.is_empty():
		save()


func new_game() -> void:
	profile = Profile.new_game(DataDB.data, rng)
	run = null
	_make_market()
	save()
	EventBus.gold_changed.emit(profile.gold)


func save() -> void:
	SaveManager.write_save(profile.to_dict())


## Called after a profile change made through `profile` directly (equip, upgrade, buy...).
func changed() -> void:
	save()
	EventBus.gold_changed.emit(profile.gold)
	EventBus.profile_changed.emit()


## Rewards from a single battle outside a run (the prototype battle scene).
func add_rewards(xp_amount: int, gold_amount: int) -> void:
	var old := level()
	profile.add_xp(xp_amount)
	profile.gold += gold_amount
	EventBus.xp_gained.emit(active_class, xp_amount)
	if level() > old:
		EventBus.level_up.emit(active_class, level())
	changed()


# ---------------------------------------------------------------- dungeon runs

func start_run(dungeon_id: String) -> DungeonRun:
	run = profile.start_run(dungeon_id, rng)
	return run


## A saved unfinished run, or null.
func saved_run() -> DungeonRun:
	if profile.run_state.is_empty():
		return null
	return DungeonRun.from_dict(DataDB.data, profile.run_state)


func resume_run() -> DungeonRun:
	run = saved_run()
	if run == null:
		discard_run()
	return run


## Gives up a saved run as if the player had escaped: loot and gold are kept.
func discard_run() -> void:
	var saved := saved_run()
	profile.run_state = {}
	if saved != null:
		saved.escape()
		apply_run(saved)
	else:
		save()


## Drops a run that never entered a room (back to town from the first doors).
func cancel_run() -> void:
	run = null
	profile.run_state = {}
	save()


## Saves the run between rooms so it survives the app closing.
func save_run() -> void:
	if run == null:
		return
	var d := run.to_dict()
	if not d.is_empty():
		profile.run_state = d
		save()


## Banks a finished run. Returns Profile.apply_run's result (loot added or salvaged).
func apply_run(finished: DungeonRun) -> Dictionary:
	var old := level()
	var result := profile.apply_run(finished, rng)
	run = null
	market_news = market.after_run(rng)
	EventBus.xp_gained.emit(active_class, finished.xp_earned)
	if level() > old:
		EventBus.level_up.emit(active_class, level())
	changed()
	return result


# ---------------------------------------------------------------- market

func online_config() -> Dictionary:
	var cfg := DataLoader.load_json("res://data/online.json")
	if str(cfg.get("supabase_url", "")) == "" or str(cfg.get("supabase_anon_key", "")) == "":
		return {}
	return cfg


func _make_market() -> void:
	if market is Node:
		market.queue_free()
	var cfg := online_config()
	if cfg.is_empty():
		market = LocalMarket.new(profile)
		if profile.market["board"].is_empty():
			market._turn_over_board(rng)
	else:
		market = SupabaseMarket.new(profile, cfg["supabase_url"], cfg["supabase_anon_key"])
		market.save_profile = changed
		add_child(market)

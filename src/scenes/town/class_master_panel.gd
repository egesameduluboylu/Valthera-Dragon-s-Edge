class_name ClassMasterPanel
extends Control
## Yaşlı Kaan, the Class Master (docs/04): learn the other classes once the first
## dungeon is cleared, switch the active class, and pick the 4 skills taken into battle.

signal closed

const SKILL_ICON := 76
const CLASS_ORDER := ["warrior", "mage", "rogue"]

var _content: VBoxContainer
var _npc_holder: VBoxContainer
var _classes: VBoxContainer
var _slots: HBoxContainer
var _skills: VBoxContainer
## Loadout slot the next tapped skill goes into.
var _slot: int = 0
var _line: String = ""


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var parts := UIKit.sheet(DataDB.t("class_master.title"), func() -> void: closed.emit())
	add_child(parts[0])
	_content = parts[1]
	# landscape: the master and the three classes on the left, the battle loadout on the right
	var cols := UIKit.split(_content, 0.48)
	var left: VBoxContainer = cols[0]
	var right: VBoxContainer = cols[1]
	_npc_holder = VBoxContainer.new()
	left.add_child(_npc_holder)
	_classes = UIKit.scroll_list(left, 8)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 12)
	right.add_child(head)
	var loadout_title := UIKit.title(DataDB.t("class_master.loadout"), 28)
	loadout_title.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(loadout_title)
	var hint := UIKit.wrapped(DataDB.t("class_master.loadout_hint"), 19, UITheme.TEXT_MUTED)
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(hint)
	_slots = HBoxContainer.new()
	_slots.add_theme_constant_override("separation", 12)
	_slots.alignment = BoxContainer.ALIGNMENT_CENTER
	right.add_child(_slots)
	_skills = UIKit.scroll_list(right, 8)
	_line = DataDB.t("class_master.line")
	refresh()


func refresh() -> void:
	var p := GameState.profile
	for c in _npc_holder.get_children():
		c.queue_free()
	_npc_holder.add_child(UIKit.npc_row("res://assets/town/npc_class_master.png", DataDB.t("class_master.npc"), _line))
	for c in _classes.get_children():
		c.queue_free()
	for id in CLASS_ORDER:
		_classes.add_child(_class_card(id))
	for c in _slots.get_children():
		c.queue_free()
	var loadout := p.loadout()
	for i in loadout.size():
		_slots.add_child(_slot_button(i, loadout[i]))
	for c in _skills.get_children():
		c.queue_free()
	for id in DataDB.data["skills"]:
		if DataDB.skill(id).get("class", "") == p.active_class:
			_skills.add_child(_skill_row(id, loadout))


# ---------------------------------------------------------------- classes

func _class_card(id: String) -> PanelContainer:
	var p := GameState.profile
	var def: Dictionary = DataDB.data["classes"][id]
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	card.add_child(h)
	var portrait := UIKit.icon(def.get("sprite", ""), 76)
	var block := p.class_unlock_block(id)
	if block == "locked":
		portrait.modulate = Color(0.35, 0.32, 0.35)
	h.add_child(portrait)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 2)
	h.add_child(v)
	var title := DataDB.t("class." + id)
	if p.is_unlocked(id):
		title += "  ·  " + DataDB.t("ui.level") % int(p.classes[id]["level"])
	# name and level with the class resource on the same line, the motto under them
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 10)
	v.add_child(top)
	var name_ := UIKit.label(title, 24, UITheme.GOLD if id == p.active_class else UITheme.TEXT)
	name_.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(name_)
	var res := UIKit.label(DataDB.t("resource." + String(def.get("resource", ""))), 19,
			Color(def.get("resource_color", "#c8412f")))
	res.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	top.add_child(res)
	v.add_child(UIKit.wrapped(DataDB.t("class_master.motto." + id), 18, UITheme.TEXT_MUTED))
	var action: Button
	if id == p.active_class:
		action = UIKit.button(DataDB.t("class_master.active"), "", func() -> void: pass, 22)
		action.disabled = true
	elif p.is_unlocked(id):
		action = UIKit.button(DataDB.t("class_master.switch"), "", _on_switch.bind(id), 22)
	elif block == "":
		action = UIKit.primary(UIKit.button(DataDB.t("class_master.learn"), "", _on_learn.bind(id), 22))
	else:
		action = UIKit.button(DataDB.t("class_master.locked"), "", func() -> void: pass, 18)
		action.disabled = true
	action.custom_minimum_size = Vector2(132, 64)
	action.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(action)
	return card


func _on_learn(id: String) -> void:
	if GameState.profile.unlock_class(id):
		_line = DataDB.tf("class_master.learned", {"class": DataDB.t("class." + id)})
		GameState.changed()
	refresh()


func _on_switch(id: String) -> void:
	if GameState.profile.switch_class(id):
		_slot = 0
		_line = DataDB.tf("class_master.switched", {"class": DataDB.t("class." + id)})
		GameState.changed()
	else:
		_line = DataDB.t("class_master.busy")
	refresh()


# ---------------------------------------------------------------- skills

func _slot_button(i: int, skill_id: String) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(104, 104)
	b.icon = load(DataDB.skill(skill_id).get("icon", ""))
	b.expand_icon = true
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.tooltip_text = DataDB.t(DataDB.skill(skill_id).get("name_key", ""))
	if i == _slot:
		b.add_theme_stylebox_override("normal", UITheme.skin_button("pressed", true))
	b.pressed.connect(func() -> void:
		_slot = i
		refresh())
	return b


func _skill_row(id: String, loadout: Array) -> PanelContainer:
	var p := GameState.profile
	var def := DataDB.skill(id)
	var unlocked := p.unlocked_skills().has(id)
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", UITheme.skin_panel("dark"))
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	card.add_child(h)
	var ic := UIKit.icon(def.get("icon", ""), SKILL_ICON)
	if not unlocked:
		ic.modulate = Color(0.35, 0.32, 0.35)
	h.add_child(ic)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 0)
	h.add_child(v)
	var role: String = def.get("role", "neutral")
	var head := DataDB.t(def.get("name_key", id)) + "  ·  " + DataDB.t("role." + role)
	v.add_child(UIKit.label(head, 22, UITheme.COMBO if role == "finisher" else UITheme.TEXT))
	v.add_child(UIKit.wrapped(DataDB.t(def.get("desc_key", "")), 18, UITheme.TEXT_MUTED))
	var cost := int(def.get("cost", 0))
	var info := DataDB.tf("class_master.cost", {"n": cost, "res": DataDB.t("resource." + p.player().resource_id)}) \
			if cost > 0 else DataDB.t("class_master.free")
	if int(def.get("cooldown", 0)) > 0:
		info += "  ·  " + DataDB.tf("class_master.cooldown", {"n": int(def["cooldown"])})
	v.add_child(UIKit.label(info, 17, UITheme.TEXT_MUTED))
	var b: Button
	if not unlocked:
		b = UIKit.button(DataDB.t("ui.level") % int(def.get("unlock_level", 1)), "", func() -> void: pass, 20)
		b.disabled = true
	elif loadout.has(id):
		b = UIKit.button(DataDB.t("class_master.in_loadout"), "", func() -> void: pass, 20)
		b.disabled = true
	else:
		b = UIKit.button(DataDB.t("class_master.take"), "", _on_take.bind(id), 20)
	b.custom_minimum_size = Vector2(130, 64)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(b)
	return card


func _on_take(id: String) -> void:
	if GameState.profile.set_loadout_slot(_slot, id):
		_slot = (_slot + 1) % Profile.LOADOUT_SIZE
		GameState.changed()
	refresh()

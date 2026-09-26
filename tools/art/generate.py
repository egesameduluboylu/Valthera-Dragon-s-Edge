"""Regenerates every procedural art asset under assets/.

    python3 -m pip install pillow
    python3 tools/art/generate.py            # everything
    python3 tools/art/generate.py sprites    # one group: sprites | backgrounds | icons | scenes | town | skin

backgrounds writes every dungeon's battle background plus the map backgrounds of the later dungeons
(mushroom_cave, frozen_pass, burnt_keep, dragon_lair); the cellar's map stays in the scenes group.

The art is original and generated from code, so there are no third-party licences to track.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

import backgrounds  # noqa: E402
import characters  # noqa: E402
import gear  # noqa: E402
import icons  # noqa: E402
import scenes  # noqa: E402
import town  # noqa: E402
import ui_skin  # noqa: E402


def save(img, rel):
    path = os.path.join(ROOT, "assets", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    print("wrote", os.path.relpath(path, ROOT))


def main(groups):
    if "sprites" in groups:
        for name, fn in characters.SPRITES.items():
            save(fn(), f"sprites/{name}.png")
    if "backgrounds" in groups:
        save(backgrounds.rotten_cellar(), "backgrounds/rotten_cellar.png")
        for k, (battle, dungeon_map) in backgrounds.DUNGEONS.items():
            save(battle(), f"backgrounds/{k}.png")
            save(dungeon_map(), f"backgrounds/{k}_map.png")
    if "icons" in groups:
        for k in icons.SKILL_ICONS:
            save(icons.skill_icon(k), f"icons/skills/{k}.png")
        for k in icons.INTENT_ICONS:
            save(icons.small_icon(k), f"icons/intents/{k}.png")
        for k in icons.STATUS_ICONS:
            save(icons.small_icon(k), f"icons/statuses/{k}.png")
        save(icons.small_icon("target"), "icons/ui/target.png")
        for k in icons.ROOM_ICONS:
            save(icons.room_icon(k), f"icons/rooms/{k}.png")
        for k in icons.ITEM_ICONS:
            save(icons.item_icon(k), f"icons/items/{k}.png")
        for k, fn in gear.GEAR.items():
            save(fn(), f"icons/items/gear/{k}.png")
    if "scenes" in groups:
        save(scenes.cellar_map(), "backgrounds/rotten_cellar_map.png")
        save(scenes.door(), "ui/door.png")
        save(scenes.door(boss=True), "ui/door_boss.png")
        for k in scenes.EVENT_ART:
            save(scenes.event_art(k), f"events/{k}.png")
    if "town" in groups:
        for name, fn in town.TOWN.items():
            save(fn(), f"town/{name}.png")
    if "skin" in groups:
        ui_skin.write_all(save)


if __name__ == "__main__":
    main(sys.argv[1:] or ["sprites", "backgrounds", "icons", "scenes", "town", "skin"])

"""Regenerates every procedural art asset under assets/.

    python3 -m pip install pillow
    python3 tools/art/generate.py            # everything
    python3 tools/art/generate.py sprites    # one group: sprites | backgrounds | icons | scenes | town | skin

backgrounds writes every dungeon's battle background plus the map backgrounds of the later dungeons
(mushroom_cave, frozen_pass, burnt_keep, dragon_lair); the cellar's map stays in the scenes group.

The art is original and generated from code, so there are no third-party licences to track.

The landscape look of 0.8 (docs/16) comes from separate, slower modules, each run on its own:

    python3 tools/art/heroes_v2.py [ids]        # hero rigs (assets/rigs/) + their flat sprites
    python3 tools/art/monsters_d1.py [ids]      # ... monsters_d2 .. monsters_d5, one per dungeon
    python3 tools/art/backgrounds_v2.py [ids]   # layered battle backgrounds (assets/backgrounds/v2/)
    python3 tools/art/town_v2.py                # the painted town (assets/town/v2/)
    python3 tools/art/ui_v2.py [kit|skills]     # the HUD kit (assets/ui/v2/) and skill icons

Their flat sprites win: `sprites` below skips every id that has a rig in assets/rigs/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

import backgrounds  # noqa: E402
import characters  # noqa: E402
import enemies_a  # noqa: E402
import enemies_b  # noqa: E402
import gear  # noqa: E402
import heroes  # noqa: E402
import icons  # noqa: E402
import npcs  # noqa: E402
import scenes  # noqa: E402
import town  # noqa: E402
import ui_skin  # noqa: E402


def save(img, rel):
    path = os.path.join(ROOT, "assets", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    print("wrote", os.path.relpath(path, ROOT))


def sprites():
    """Every character sprite: the 512 px redraws (heroes, enemies_a/b) replace the
    256 px originals in characters.py, which still draws anything not redrawn."""
    out = dict(characters.SPRITES)
    out.update({f"player/{k}": fn for k, fn in heroes.HEROES.items()})
    out.update(enemies_a.SPRITES)
    out.update(enemies_b.SPRITES)
    # ids redrawn as rigs keep the flat picture their rig module wrote
    rigs = os.path.join(ROOT, "assets", "rigs")
    return {k: fn for k, fn in out.items() if not os.path.isdir(os.path.join(rigs, k.split("/")[-1]))}


def main(groups):
    if "sprites" in groups:
        for name, fn in sprites().items():
            save(fn(), f"sprites/{name}.png")
    if "backgrounds" in groups:
        save(backgrounds.rotten_cellar(), "backgrounds/rotten_cellar.png")
        for k, (battle, dungeon_map) in backgrounds.DUNGEONS.items():
            save(battle(), f"backgrounds/{k}.png")
            save(dungeon_map(), f"backgrounds/{k}_map.png")
    if "icons" in groups:
        # skill icons are painted by ui_v2.py (python3 tools/art/ui_v2.py skills)
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
            if not name.startswith("npc_"):
                save(fn(), f"town/{name}.png")
        for name, fn in npcs.NPCS.items():
            save(fn(), f"town/npc_{name}.png")
    if "skin" in groups:
        ui_skin.write_all(save)


if __name__ == "__main__":
    main(sys.argv[1:] or ["sprites", "backgrounds", "icons", "scenes", "town", "skin"])

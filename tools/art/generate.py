"""Regenerates every procedural art asset under assets/.

    python3 -m pip install pillow
    python3 tools/art/generate.py            # everything
    python3 tools/art/generate.py sprites    # one group: sprites | backgrounds | icons

The art is original and generated from code, so there are no third-party licences to track.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

import backgrounds  # noqa: E402
import characters  # noqa: E402
import icons  # noqa: E402


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
    if "icons" in groups:
        for k in icons.SKILL_ICONS:
            save(icons.skill_icon(k), f"icons/skills/{k}.png")
        for k in icons.INTENT_ICONS:
            save(icons.small_icon(k), f"icons/intents/{k}.png")
        for k in icons.STATUS_ICONS:
            save(icons.small_icon(k), f"icons/statuses/{k}.png")
        save(icons.small_icon("target"), "icons/ui/target.png")


if __name__ == "__main__":
    main(sys.argv[1:] or ["sprites", "backgrounds", "icons"])

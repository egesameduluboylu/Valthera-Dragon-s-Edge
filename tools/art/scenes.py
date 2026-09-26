"""Dungeon map art: the hall background, doors, and event/room illustrations."""
import math
import random

from PIL import Image, ImageDraw

import backgrounds
import icons
from painter import Painter, hexc, shade

STONE = hexc("#6e6470")
WOOD = hexc("#8a5a32")
IRON = hexc("#4b4f57")
DARK = hexc("#221820")
BONE = hexc("#ece3c8")
GOLD = hexc("#e7b440")


def cellar_map(seed=11):
    """720 x 1280 background for the dungeon map screen: a tall brick hall."""
    rng = random.Random(seed)
    K = backgrounds.K
    old_h = backgrounds.H
    backgrounds.H = 1280
    try:
        img = Image.new("RGBA", (720 * K, 1280 * K), hexc("#1c1418"))
        d = ImageDraw.Draw(img)
        floor_top = 1010
        backgrounds._brick_wall(d, rng, 0, floor_top, hexc("#4e4654"), hexc("#1d161d"))
        backgrounds._floor(d, rng, floor_top)
        d.rectangle((0, (floor_top - 6) * K, 720 * K, (floor_top + 8) * K), fill=hexc("#150f14"))
        for x, y in ((110, 330), (610, 330), (110, 760), (610, 760)):
            backgrounds._torch(img, x, y)
        # chains hanging from the ceiling
        d = ImageDraw.Draw(img)
        for cx in (240, 480):
            for i in range(9):
                y = i * 22
                d.ellipse(((cx - 7) * K, y * K, (cx + 7) * K, (y + 26) * K), outline=hexc("#3a3a44"), width=4 * K)
        backgrounds._vignette(img)
        return img.resize((720, 1280), Image.LANCZOS)
    finally:
        backgrounds.H = old_h


def door(boss=False):
    """Arched door in a stone frame, 240 x 320."""
    p = Painter(240, 320)
    # stone frame
    p.shape("rect", (8, 110, 232, 316), STONE, radius=6, depth=0.04)
    p.shape("pie", (8, 8, 232, 232), STONE, start=180, end=360, depth=0.04)
    for i in range(7):  # arch stones
        a = math.pi + (i + 0.5) * math.pi / 7
        x, y = 120 + 104 * math.cos(a), 120 + 104 * math.sin(a)
        p.shape("ellipse", (x - 15, y - 13, x + 15, y + 13), shade(STONE, 1.08), line=1.2, depth=0.2)
    # door leaves
    base = hexc("#3a3a44") if boss else WOOD
    m = p.shape("rect", (30, 120, 210, 316), base, radius=2, depth=0.05, line=2)
    p.shape("pie", (30, 30, 210, 210), base, start=180, end=360, depth=0.05, line=2)
    p.flat("rect", (32, 116, 208, 124), base)
    if not boss:
        for x in (74, 118, 162):
            p.shape("line", [(x, 40 if x == 118 else 58), (x, 314)], shade(WOOD, 0.7), width=3, shadow=0, light=0, line=0)
    for y in (150, 260):
        p.shape("rect", (28, y, 212, y + 14), IRON, radius=3, depth=0.3, line=1.2)
        for x in (44, 196):
            p.flat("ellipse", (x - 4, y + 3, x + 4, y + 11), shade(IRON, 1.4))
    # ring handle
    p.shape("ellipse", (150, 196, 178, 226), (0, 0, 0, 0), shadow=0, light=0, line=3, ink=hexc("#c9a040"))
    if boss:
        p.glow((120, 190), 110, hexc("#ff2a3a"), 0.45)
        icons._skull(p, 120, 110, 1.6)
        p.glow((110, 107), 12, hexc("#ff4040"), 1.0)
        p.glow((130, 107), 12, hexc("#ff4040"), 1.0)
        icons._crown(p, 120, 64, 0.9)
    return p.finish(outline=2)


def _card(w=360, h=240):
    return Painter(w, h)


def event_art(kind):
    """Illustrations for event and rest rooms, 360 x 240, on a transparent background."""
    p = _card()
    if kind == "fountain":
        p.glow((180, 120), 130, hexc("#66ffb0"), 0.35)
        p.shape("ellipse", (60, 150, 300, 220), STONE, depth=0.12)
        p.shape("ellipse", (80, 156, 280, 196), hexc("#3cc28a"), light=1.35, depth=0.15, line=1.2)
        p.shape("rect", (164, 70, 196, 170), STONE, radius=6)
        p.shape("ellipse", (126, 50, 234, 96), STONE, depth=0.15)
        p.shape("ellipse", (138, 56, 222, 84), hexc("#3cc28a"), light=1.35, line=1.2)
        for dx in (-34, 0, 34):
            p.shape("line", [(180 + dx * 0.6, 84), (180 + dx * 1.4, 120), (180 + dx * 1.8, 168)],
                    hexc("#8dffd0", 200), width=4, shadow=0, light=0, line=0)
        for x, y in ((110, 178), (240, 170), (200, 186)):
            p.flat("ellipse", (x, y, x + 10, y + 6), hexc("#d8ffee"))
        p.shape("ellipse", (240, 30, 262, 52), hexc("#b0ffda"), light=1.5, line=0)
        p.shape("ellipse", (98, 18, 114, 34), hexc("#b0ffda"), light=1.5, line=0)
    elif kind == "merchant":
        p.glow((250, 110), 70, hexc("#ffc060"), 0.6)
        p.shape("rect", (60, 90, 150, 200), hexc("#7a4a2a"), radius=12)  # backpack
        for y in (110, 150):
            p.shape("rect", (60, y, 150, y + 10), hexc("#4a3020"), radius=3)
        p.shape("poly", [(130, 70), (230, 70), (250, 226), (110, 226)], hexc("#3a5a7a"), depth=0.1)
        p.shape("ellipse", (140, 20, 220, 100), hexc("#3a5a7a"), depth=0.12)
        p.shape("ellipse", (154, 40, 208, 92), DARK, shadow=0, light=0, line=0)
        p.flat("ellipse", (166, 58, 176, 66), hexc("#ffe680"))
        p.flat("ellipse", (186, 58, 196, 66), hexc("#ffe680"))
        p.shape("line", [(230, 120), (254, 96)], hexc("#3a5a7a"), width=16)
        p.shape("line", [(254, 96), (254, 116)], IRON, width=3, shadow=0, light=0, line=0)
        p.shape("rect", (240, 114, 268, 150), hexc("#ffcf6a"), radius=5, light=1.4)
        icons._potion(p, 96, 214, 0.7)
        icons._potion(p, 276, 214, 0.7, hexc("#3a8aff"))
    elif kind == "skull":
        p.glow((180, 100), 110, hexc("#a080ff"), 0.35)
        p.shape("rect", (120, 150, 240, 226), STONE, radius=6, depth=0.1)
        p.shape("rect", (108, 140, 252, 158), shade(STONE, 1.1), radius=4)
        icons._skull(p, 180, 96, 2.4)
        p.glow((166, 94), 14, hexc("#c0a0ff"), 1.0)
        p.glow((194, 94), 14, hexc("#c0a0ff"), 1.0)
        for cx in (90, 270):
            p.shape("rect", (cx - 10, 160, cx + 10, 226), hexc("#efe2c0"), radius=3)
            p.glow((cx, 146), 20, hexc("#ffc060"), 0.8)
            icons._flame(p, cx, 146, 0.45)
    elif kind == "altar":
        p.glow((180, 120), 130, hexc("#ff2040"), 0.4)
        p.shape("rect", (70, 120, 290, 226), STONE, radius=6, depth=0.08)
        p.shape("rect", (56, 104, 304, 128), shade(STONE, 1.1), radius=5)
        for x in (100, 150, 200, 250):
            p.shape("line", [(x, 150), (x + 12, 170), (x, 190)], hexc("#ff4050"), width=4, shadow=0, light=0, line=0)
        p.shape("ellipse", (150, 88, 210, 110), hexc("#8a1020"), light=1.4, line=1.2)
        p.shape("poly", [(180, 20), (196, 60), (180, 92), (164, 60)], hexc("#ff3050"), light=1.5)
        p.glow((180, 56), 34, hexc("#ff6070"), 0.9)
    elif kind == "campfire":
        p.glow((180, 150), 140, hexc("#ffa040"), 0.5)
        for x in (80, 250):  # log seats
            p.shape("rect", (x, 180, x + 60, 210), hexc("#7a4a2a"), radius=14)
            p.shape("ellipse", (x + 44, 180, x + 66, 210), hexc("#c89060"), line=1.2)
        icons._campfire(p, 180, 170, 2.2)
    elif kind == "chest":
        p.glow((180, 140), 120, hexc("#ffd060"), 0.35)
        icons._chest(p, 100, 90, 260, 210)
        for x, y in ((80, 206), (270, 200), (240, 214)):
            p.shape("ellipse", (x, y, x + 22, y + 12), GOLD, line=1.2)
    return p.finish(outline=2)


EVENT_ART = ["fountain", "merchant", "skull", "altar", "campfire", "chest"]

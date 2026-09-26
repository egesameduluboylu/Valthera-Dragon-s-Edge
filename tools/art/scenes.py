"""Dungeon map art: the hall background, doors, and event/room illustrations."""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import backgrounds
import icons
import painter
from painter import Painter, hexc, mix, shade

STONE = hexc("#6e6470")
WOOD = hexc("#8a5a32")
IRON = hexc("#4b4f57")
DARK = hexc("#221820")
BONE = hexc("#ece3c8")
GOLD = hexc("#e7b440")
NOLINE = dict(shadow=0, light=0, line=0)


def cellar_map(seed=11):
    """720 x 1280 background for the dungeon map screen: a tall torch-lit brick hall."""
    rng = random.Random(seed)
    K = backgrounds.K
    MW, MH = 720, 1280
    old = painter.SS
    painter.SS = K
    try:
        img = Image.new("RGBA", (MW * K, MH * K), hexc("#1c1418"))
        d = ImageDraw.Draw(img)
        floor_top = 1010
        backgrounds._brick_wall(d, rng, 0, floor_top, hexc("#524a5a"), hexc("#1d161d"), width=MW)
        backgrounds._floor(d, rng, floor_top, height=MH, width=MW)
        backgrounds._texture(img, "stone", 0.35)
        backgrounds._grime(img, rng, 0, floor_top, 22, width=MW)
        d = ImageDraw.Draw(img)
        d.rectangle((0, (floor_top - 14) * K, MW * K, (floor_top + 6) * K), fill=hexc("#3a3038"))
        d.line((0, (floor_top - 13) * K, MW * K, (floor_top - 13) * K), fill=hexc("#6a5e6a"), width=2 * K)
        d.rectangle((0, (floor_top + 4) * K, MW * K, (floor_top + 14) * K), fill=hexc("#120c12"))
        p = backgrounds._props_painter(img)
        # stone pillars framing the hall
        for x0 in (0, MW - 46):
            pil = p.shape("rect", (x0, 0, x0 + 46, floor_top), hexc("#5e5664"), depth=0.2, tex="stone", line=1.8)
            for y in range(20, floor_top, 64):
                p.stroke([(x0 + 2, y), (x0 + 44, y)], hexc("#2a2230"), 2)
        # chains hanging from the ceiling
        for cx in (240, 480):
            backgrounds.chain(p, cx, 0, 12)
            p.shape("ellipse", (cx - 12, 142, cx + 12, 166), hexc("#4f535c"), depth=0.3, spec=0.5, line=1.4)
        # tattered banners
        for cx, col in ((200, hexc("#6a2a3a")), (520, hexc("#2a3a6a"))):
            p.shape("poly", [(cx - 36, 540), (cx + 36, 540), (cx + 36, 670), (cx + 20, 650), (cx + 4, 676), (cx - 12, 652),
                             (cx - 36, 672)], col, depth=0.14, tex="cloth", tex_amt=0.8)
            p.shape("line", [(cx - 44, 540), (cx + 44, 540)], hexc("#5a3a22"), width=7, depth=0.3, tex="wood")
            icons._skull(p, cx, 596, 0.8)
        backgrounds.cobweb(p, 46, 0, 1, 120)
        backgrounds.cobweb(p, MW - 46, 0, -1, 100)
        # props on the floor
        backgrounds.barrel(p, 30, 924, 70, 96)
        backgrounds.barrel(p, 92, 946, 60, 80)
        backgrounds.crate(p, 600, 940, 86, 76)
        backgrounds.skull(p, 560, 1040, 0.9)
        backgrounds.bones(p, 170, 1060, 0.9)
        backgrounds.puddle(p, 420, 1150, 80, 16)
        for x, y in ((110, 330), (610, 330), (110, 760), (610, 760)):
            backgrounds.torch(p, x, y, 1.0)
        img = p.img
        warm = (255, 170, 90)
        pools = [(x, y - 10, 260, 290, warm, 0.95) for x, y in ((110, 330), (610, 330), (110, 760), (610, 760))]
        pools.append((360, 1120, 420, 200, (150, 140, 150), 0.5))
        img = backgrounds._light(img, (104, 110, 134), pools)
        for x, y in ((110, 330), (610, 330), (110, 760), (610, 760)):
            backgrounds._glow(img, x, y - 20, 170, (255, 150, 60), 95)
            backgrounds._glow(img, x, y - 25, 55, (255, 215, 130), 160)
        backgrounds._vignette(img, 180)
        return img.resize((MW, MH), Image.LANCZOS)
    finally:
        painter.SS = old


def door(boss=False):
    """Arched door in a stone frame, 240 x 320."""
    p = Painter(240, 320, soft=True)
    rng = random.Random(5 if boss else 4)
    # stone frame with bevelled blocks
    p.shape("rect", (8, 110, 232, 316), STONE, radius=6, depth=0.05, tex="stone")
    p.shape("pie", (8, 8, 232, 232), STONE, start=180, end=360, depth=0.05, tex="stone")
    for y in range(120, 316, 32):
        for x0 in (10, 204):
            p.shape("rect", (x0, y, x0 + 26, y + 30), shade(STONE, rng.uniform(0.92, 1.12)), radius=3, depth=0.2,
                    tex="stone", line=1.3)
    for i in range(9):
        a0 = math.pi + i * math.pi / 9 + 0.02
        a1 = math.pi + (i + 1) * math.pi / 9 - 0.02
        r0, r1 = 90, 114
        pts = [(120 + r0 * math.cos(a0), 120 + r0 * math.sin(a0)), (120 + r1 * math.cos(a0), 120 + r1 * math.sin(a0)),
               (120 + r1 * math.cos(a1), 120 + r1 * math.sin(a1)), (120 + r0 * math.cos(a1), 120 + r0 * math.sin(a1))]
        p.shape("poly", pts, shade(STONE, 1.22 if i == 4 else rng.uniform(0.98, 1.12)), depth=0.2, tex="stone",
                line=1.3)
    # door leaves
    base = hexc("#3a3a46") if boss else WOOD
    leaf = p.union([("rect", (30, 120, 210, 316)), ("pie", (30, 30, 210, 210), {"start": 180, "end": 360})])
    p.paint_mask(leaf, base, depth=0.06, line=2, tex="metal" if boss else "wood", tex_amt=0.9 if boss else 1.2)
    if not boss:
        for x in (66, 102, 138, 174):
            p.stroke([(x, 36 if 90 < x < 150 else 52), (x, 314)], shade(WOOD, 0.55), 2.2)
    else:
        for y in range(80, 316, 34):
            p.stroke([(32, y), (208, y)], hexc("#22222a"), 2)
    p.shadow_on(p._mask("rect", (8, 110, 30, 316)), 0.3, 3, 4)
    for y in (150, 260):
        p.shape("rect", (28, y, 212, y + 16), IRON, radius=3, depth=0.3, line=1.3, spec=0.6, tex="metal")
        for x in (42, 80, 160, 198):
            backgrounds_rivet(p, x, y + 8)
    # keyhole plate and ring handle
    p.shape("rect", (144, 196, 176, 238), hexc("#6a5a4a") if not boss else IRON, radius=4, depth=0.3, spec=0.6,
            tex="metal")
    ring = ImageChops.subtract(p._mask("ellipse", (146, 206, 174, 234)), p._mask("ellipse", (151, 211, 169, 229)))
    p.paint_mask(ring, hexc("#d8a83e"), depth=0.3, line=1.1, spec=1.0, rim=0)
    p.shape("ellipse", (156, 199, 164, 207), hexc("#d8a83e"), depth=0.3, line=1.0, spec=0.8, rim=0)
    if boss:
        p.glow((120, 190), 110, hexc("#ff2a3a"), 0.4)
        for x in range(44, 200, 26):  # spikes along the arch
            a = math.pi + (x - 30) / 180 * math.pi
            cx, cy = 120 + 90 * math.cos(a), 120 + 90 * math.sin(a)
            p.shape("poly", [(cx - 5, cy + 4), (cx + 5, cy + 4), (cx, cy + 16)], hexc("#8a8e98"), line=1.0, spec=0.6,
                    rim=0)
        icons._skull(p, 120, 108, 1.6)
        icons._glow_eyes(p, 120, 108, 1.6, hexc("#ff4040"))
        icons._crown(p, 120, 62, 0.9)
    return p.finish(outline=2)


def backgrounds_rivet(p, x, y, r=3):
    p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#8a8e98"), line=0.8, depth=0.4, light=1.6, rim=0, ao=0.4)


def _card(w=360, h=240):
    return Painter(w, h, soft=True)


def event_art(kind):
    """Illustrations for event and rest rooms, 360 x 240, on a transparent background."""
    p = _card()
    if kind == "fountain":
        p.glow((180, 120), 140, hexc("#66ffb0"), 0.35)
        p.shape("ellipse", (54, 146, 306, 224), STONE, depth=0.12, tex="stone")
        for a in range(10, 180, 25):
            x = 180 + 124 * math.cos(math.radians(a))
            y = 185 + 37 * math.sin(math.radians(a))
            p.stroke([(x, y - 6), (x, y + 4)], hexc("#3a3440"), 1.4)
        p.shape("ellipse", (74, 152, 286, 198), hexc("#2aa878"), light=1.35, depth=0.18, line=1.2, gloss=0.5)
        for r in (30, 56, 80):  # ripples
            p.stroke(curve_ellipse(180, 175, r, r * 0.22), hexc("#b0ffe0", 120), 1.2)
        p.shape("rect", (162, 70, 198, 172), STONE, radius=6, tex="stone")
        for y in (90, 120, 150):
            p.stroke([(164, y), (196, y)], hexc("#3a3440"), 1.4)
        p.shape("ellipse", (122, 48, 238, 98), STONE, depth=0.15, tex="stone")
        p.shape("ellipse", (136, 54, 224, 84), hexc("#3cc28a"), light=1.35, line=1.2, gloss=0.6)
        for dx in (-34, 0, 34):
            p.shape("line", [(180 + dx * 0.6, 84), (180 + dx * 1.4, 120), (180 + dx * 1.8, 168)],
                    hexc("#8dffd0", 200), width=4, **NOLINE)
            p.stroke([(180 + dx * 0.6, 86), (180 + dx * 1.4, 120)], hexc("#ffffff", 180), 1.2)
        for x, y in ((110, 178), (240, 170), (200, 186), (150, 166)):
            p.flat("ellipse", (x, y, x + 10, y + 5), hexc("#d8ffee"))
        for x, y, r in ((252, 40, 11), (106, 26, 8), (60, 80, 5), (300, 96, 6)):
            p.glow((x, y), r * 2.6, hexc("#8affcf"), 0.7)
            p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#b0ffda"), light=1.5, line=0, gloss=1.0, rim=0)
        p.shape("ellipse", (58, 200, 90, 222), hexc("#4f7a3a"), depth=0.3, tex="fur", line=1.2)  # moss
    elif kind == "merchant":
        p.glow((250, 110), 80, hexc("#ffc060"), 0.6)
        p.shape("rect", (56, 86, 150, 204), hexc("#7a4a2a"), radius=14, tex="leather")  # backpack
        for y in (108, 150):
            p.shape("rect", (56, y, 150, y + 11), hexc("#4a3020"), radius=3, tex="leather")
            backgrounds_rivet(p, 104, y + 5.5, 3.5)
        p.shape("line", [(70, 86), (80, 60), (130, 60), (140, 86)], hexc("#4a3020"), width=5)
        p.shape("rect", (40, 180, 70, 208), hexc("#9a6a3a"), radius=3, tex="wood")  # rolled goods
        p.shape("poly", [(126, 68), (232, 68), (254, 226), (106, 226)], hexc("#3a5a7a"), depth=0.1, tex="cloth")
        for pts in ([(150, 90), (136, 224)], [(206, 90), (224, 224)], [(180, 110), (180, 224)]):
            p.stroke(pts, shade(hexc("#3a5a7a"), 0.6), 2)
        p.shape("rect", (118, 150, 244, 162), hexc("#6a4428"), radius=3, tex="leather")
        p.shape("ellipse", (170, 148, 186, 164), GOLD, spec=1.0)
        p.shape("ellipse", (138, 16, 222, 102), hexc("#3a5a7a"), depth=0.12, tex="cloth")
        p.shape("poly", [(180, 16), (170, -2), (196, 10)], hexc("#3a5a7a"), line=1.4)
        p.shape("ellipse", (152, 38, 208, 94), hexc("#140c14"), **NOLINE)
        for x in (171, 191):
            p.glow((x, 62), 10, hexc("#ffd060"), 0.9)
            p.flat("ellipse", (x - 5, 58, x + 5, 66), hexc("#ffe680"))
        p.shape("ellipse", (160, 80, 200, 104), hexc("#e8e0d0"), depth=0.3, tex="fur", line=1.2)  # beard
        p.shape("line", [(230, 120), (254, 96)], hexc("#3a5a7a"), width=16, tex="cloth")
        p.shape("line", [(254, 96), (254, 116)], IRON, width=3, **NOLINE)
        p.glow((254, 132), 30, hexc("#ffd070"), 0.8)
        p.shape("poly", [(240, 114), (268, 114), (254, 106)], IRON, line=1.2)
        p.shape("rect", (242, 114, 266, 150), hexc("#ffcf6a"), radius=5, light=1.4, gloss=0.8)
        for x in (242, 266):
            p.stroke([(x, 114), (x, 150)], IRON, 2.2)
        icons._potion(p, 96, 214, 0.7)
        icons._potion(p, 282, 214, 0.7, hexc("#3a8aff"))
        icons._potion(p, 310, 220, 0.5, hexc("#5ad16a"))
        for x, y in ((290, 190), (300, 196)):
            p.shape("ellipse", (x, y, x + 14, y + 8), GOLD, line=1.0, spec=0.8, rim=0)
    elif kind == "skull":
        p.glow((180, 100), 120, hexc("#a080ff"), 0.35)
        p.shape("rect", (116, 150, 244, 228), STONE, radius=6, depth=0.1, tex="stone")
        p.shape("rect", (104, 138, 256, 158), shade(STONE, 1.12), radius=4, tex="stone")
        for x in (140, 180, 220):  # carved runes
            p.stroke([(x - 8, 176), (x, 168), (x + 8, 176), (x, 196)], hexc("#b090ff", 200), 2.2)
            p.glow((x, 182), 14, hexc("#a080ff"), 0.4)
        icons._skull(p, 180, 94, 2.4)
        icons._glow_eyes(p, 180, 94, 2.4, hexc("#c0a0ff"))
        for cx in (84, 276):
            p.shape("rect", (cx - 11, 160, cx + 11, 228), hexc("#efe2c0"), radius=3, tex="bone")
            p.shape("poly", [(cx - 11, 170), (cx - 14, 186), (cx - 9, 184)], hexc("#efe2c0"), line=1.0, rim=0)
            p.shape("rect", (cx - 16, 222, cx + 16, 232), hexc("#8a8e98"), radius=3, spec=0.6)
            p.glow((cx, 146), 26, hexc("#ffc060"), 0.8)
            icons._flame(p, cx, 146, 0.45)
        for x in (40, 320):
            p.shape("ellipse", (x - 14, 214, x + 14, 232), hexc("#d8cfb4"), tex="bone")
    elif kind == "altar":
        p.glow((180, 120), 140, hexc("#ff2040"), 0.4)
        p.shape("rect", (66, 118, 294, 228), STONE, radius=6, depth=0.08, tex="stone")
        p.shape("rect", (52, 102, 308, 128), shade(STONE, 1.12), radius=5, tex="stone")
        for x in (70, 290):
            p.shape("rect", (x - 8, 128, x + 8, 228), shade(STONE, 0.9), radius=3, tex="stone")
        for x in (110, 158, 206, 254):
            p.stroke([(x - 8, 150), (x + 8, 170), (x - 8, 192)], hexc("#ff4050"), 3.2)
            p.glow((x, 170), 16, hexc("#ff3050"), 0.45)
        # blood pool and drips down the front
        p.shape("ellipse", (140, 94, 220, 114), hexc("#8a1020"), light=1.4, line=1.2, gloss=0.6)
        for x, ln in ((150, 24), (196, 34), (210, 16)):
            p.shape("line", [(x, 120), (x, 120 + ln)], hexc("#8a1020"), width=5, depth=0.3, line=1.0, rim=0)
        p.glow((180, 56), 44, hexc("#ff6070"), 0.9)
        p.shape("poly", [(180, 14), (198, 56), (180, 94), (162, 56)], hexc("#ff3050"), light=1.5, spec=1.0, gloss=0.8)
        p.shape("poly", [(180, 14), (198, 56), (180, 56)], hexc("#ff90a0", 150), **NOLINE)
        p.sparkle((170, 36), 7)
        for x, y in ((110, 40), (250, 30), (280, 80), (86, 76)):
            p.glow((x, y), 8, hexc("#ff6070"), 0.8)
    elif kind == "campfire":
        p.glow((180, 150), 150, hexc("#ffa040"), 0.5)
        for a in range(0, 360, 36):  # ring of stones
            x = 180 + 70 * math.cos(math.radians(a))
            y = 196 + 18 * math.sin(math.radians(a))
            if a not in (72, 108):
                p.shape("ellipse", (x - 12, y - 8, x + 12, y + 8), shade(STONE, 1.05), depth=0.25, tex="stone")
        for x in (70, 240):  # log seats
            p.shape("rect", (x, 180, x + 62, 212), hexc("#7a4a2a"), radius=14, tex="wood_h")
            p.shape("ellipse", (x + 46, 180, x + 68, 212), hexc("#c89060"), line=1.2, tex="wood")
            p.stroke(curve_ellipse(x + 57, 196, 5, 9), hexc("#8a5a34"), 1.1)
        icons._campfire(p, 180, 170, 2.2)
        for i in range(6):
            p.flat("ellipse", (168 + i * 5 - 1.5, 80 - i * 9 - 1.5, 168 + i * 5 + 1.5, 80 - i * 9 + 1.5),
                   hexc("#ffd070"))
        # a cooking pot on a stick
        p.shape("line", [(110, 214), (150, 110)], hexc("#5a3a22"), width=5, tex="wood")
    elif kind == "chest":
        p.glow((180, 140), 130, hexc("#ffd060"), 0.4)
        icons._chest(p, 96, 84, 264, 214)
        for x, y in ((74, 206), (270, 200), (240, 214), (290, 214), (60, 220)):
            p.shape("ellipse", (x, y, x + 22, y + 12), GOLD, line=1.2, spec=0.9, rim=0)
        p.shape("poly", [(118, 214), (128, 206), (138, 214), (128, 224)], hexc("#3ad0ff"), line=1.0, gloss=1.0, rim=0)
        p.sparkle((150, 70), 8)
        p.sparkle((226, 58), 6)
    return p.finish(outline=2)


def curve_ellipse(cx, cy, rx, ry, a0=0, a1=360, n=24):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


EVENT_ART = ["fountain", "merchant", "skull", "altar", "campfire", "chest"]

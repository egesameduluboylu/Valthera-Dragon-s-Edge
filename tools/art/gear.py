"""Equipment icons for the bag, smith and merchant (96px, transparent).

The rarity frame is drawn by the UI, so these are just the items themselves.
"""
import math

from PIL import ImageChops

from painter import Painter, hexc, mix, shade

STEEL = hexc("#c9d4de")
IRON = hexc("#9aa6b2")
RUST = hexc("#b0643a")
GOLD = hexc("#e7b440")
BONE = hexc("#ece3c8")
LEATHER = hexc("#9a6433")
DARK = hexc("#221820")
GRIP = hexc("#5a3a22")
RED = hexc("#d6453a")
WHITE = hexc("#ffffff")
NOLINE = dict(shadow=0, light=0, line=0)


def _P():
    return Painter(96, 96, soft=True)


def _ring_mask(p, outer, inner):
    return ImageChops.subtract(p._mask("ellipse", outer), p._mask("ellipse", inner))


def _blade(p, x0, y0, x1, y1, width, color, tip=14, fuller=True, tex="metal"):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy * width / 2, ux * width / 2
    pts = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 + ux * tip, y1 + uy * tip), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
    p.shape("poly", pts, color, depth=0.3, light=1.35, line=1.4, spec=1.0, tex=tex, tex_amt=0.5)
    if fuller:
        p.stroke([(x0 + ux * 6, y0 + uy * 6), (x1 - ux * 6, y1 - uy * 6)], shade(color, 0.72), width * 0.22)
    p.stroke([(x0 - nx * 0.65, y0 - ny * 0.65), (x1 - nx * 0.6, y1 - ny * 0.6), (x1 + ux * tip * 0.9, y1 + uy * tip * 0.9)],
             hexc("#ffffff", 160), max(1.0, width * 0.12))
    return ux, uy, nx, ny


def _hilt(p, x0, y0, ux, uy, nx, ny, guard=GOLD, grip=GRIP, length=20, gem=None):
    p.shape("line", [(x0, y0), (x0 - ux * length, y0 - uy * length)], grip, width=8, line=1.2, tex="leather", rim=0)
    for i in range(4):
        t = 4 + i * (length - 6) / 4
        cx, cy = x0 - ux * t, y0 - uy * t
        p.stroke([(cx - nx * 0.7, cy - ny * 0.7), (cx + nx * 0.7 - ux * 2, cy + ny * 0.7 - uy * 2)], shade(grip, 0.5), 1.2)
    p.shape("line", [(x0 - nx * 2.4, y0 - ny * 2.4), (x0 + nx * 2.4, y0 + ny * 2.4)], guard, width=8, line=1.2,
            spec=0.8, rim=0)
    if gem:
        p.shape("ellipse", (x0 - 3.5, y0 - 3.5, x0 + 3.5, y0 + 3.5), gem, line=1.0, gloss=1.0, rim=0)
    ex, ey = x0 - ux * (length + 4), y0 - uy * (length + 4)
    p.shape("ellipse", (ex - 6, ey - 6, ex + 6, ey + 6), guard, line=1.2, gloss=0.8, rim=0)


def rusty_sword():
    p = _P()
    ux, uy, nx, ny = _blade(p, 34, 62, 72, 24, 12, hexc("#b9a592"))
    for fx, fy, r in ((46, 50, 5), (58, 38, 4), (64, 33, 3), (40, 56, 3), (52, 46, 2)):
        p.flat("ellipse", (fx - r, fy - r * 0.8, fx + r, fy + r * 0.8), mix(RUST, hexc("#6a3a1a"), 0.3)[:3] + (220,))
    _hilt(p, 34, 62, ux, uy, nx, ny, guard=hexc("#8a6a4a"))
    return p.finish(outline=2)


def iron_sword():
    p = _P()
    ux, uy, nx, ny = _blade(p, 34, 62, 74, 22, 12, STEEL)
    _hilt(p, 34, 62, ux, uy, nx, ny, gem=hexc("#3a8ae0"))
    p.sparkle((68, 30), 6)
    return p.finish(outline=2)


def bone_cleaver():
    p = _P()
    p.shape("poly", [(36, 58), (40, 22), (80, 16), (84, 30), (74, 52), (48, 64)], hexc("#b8c2cc"), depth=0.2,
            light=1.3, spec=0.9, tex="metal")
    p.stroke([(76, 30), (70, 50), (48, 62)], hexc("#ffffff", 150), 1.4)
    p.shape("line", [(40, 24), (80, 18)], BONE, width=8, line=1.2, tex="bone")
    for x in (48, 58, 68):
        p.shape("ellipse", (x - 4, 17 - 3 + (80 - x) * 0.1, x + 4, 25 + (80 - x) * 0.1), BONE, line=1, rim=0,
                tex="bone")
    p.shape("line", [(40, 60), (20, 80)], BONE, width=10, line=1.4, tex="bone")
    for t in (0.3, 0.6):
        x, y = 40 - 20 * t, 60 + 20 * t
        p.stroke([(x - 4, y - 4), (x + 4, y + 4)], hexc("#6a3a2a"), 2)
    p.shape("ellipse", (12, 74, 26, 88), BONE, line=1.4, tex="bone")
    p.stroke([(52, 44), (68, 36)], hexc("#8a2a2a"), 3)
    p.flat("ellipse", (60, 42, 64, 48), hexc("#8a2a2a"))
    return p.finish(outline=2)


def _torso(p, color, trim, collar=True, tex="leather"):
    pts = [(24, 18), (38, 14), (48, 22), (58, 14), (72, 18), (80, 40), (70, 44), (68, 82), (28, 82), (26, 44), (16, 40)]
    m = p.shape("poly", pts, color, depth=0.14, tex=tex, tex_amt=0.8)
    p.shape("rect", (28, 74, 68, 84), trim, radius=3, line=1.2, tex="leather")
    if collar:
        p.shape("poly", [(38, 14), (48, 30), (58, 14), (54, 12), (48, 22), (42, 12)], trim, line=1.2, rim=0)
    return m


def leather_armor():
    p = _P()
    _torso(p, LEATHER, hexc("#6b4428"))
    for y in (40, 52, 64):
        p.shape("rect", (32, y - 3, 64, y + 3), shade(LEATHER, 0.85), radius=2, line=1.0, depth=0.3, tex="leather",
                rim=0)
    for x, y in ((36, 46), (60, 46), (36, 58), (60, 58)):
        p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), GOLD, line=0.8, spec=0.8, rim=0)
    for x0, x1 in ((28, 30), (66, 68)):
        for y in range(24, 72, 5):
            p.stroke([(x0 + (x1 - x0) * 0, y), (x0, y + 2.5)], hexc("#e8c898"), 1.0)
    return p.finish(outline=2)


def chain_mail():
    p = _P()
    m = _torso(p, IRON, hexc("#6d7a86"), tex="metal")
    for row in range(9):
        for col in range(9):
            x = 26 + col * 6 + (3 if row % 2 else 0)
            y = 22 + row * 6
            p.shape("chord", (x - 3.4, y - 3.4, x + 3.4, y + 3.4), shade(IRON, 1.15), start=0, end=200, depth=0.35,
                    line=0.6, clip=m, rim=0, ao=0, light=1.4)
    p.shape("rect", (40, 40, 56, 56), hexc("#8a2a2a"), radius=3, line=1.2, tex="cloth")
    p.shape("poly", [(48, 43), (53, 48), (48, 53), (43, 48)], GOLD, line=0.8, spec=1.0, rim=0)
    return p.finish(outline=2)


def leather_cap():
    p = _P()
    p.shape("chord", (16, 20, 80, 84), LEATHER, start=180, end=360, depth=0.16, tex="leather", tex_amt=1.0)
    for x0, x1 in ((22, 36), (74, 60)):
        p.stroke([(48, 22), (x1, 32), (x0, 50)], shade(LEATHER, 0.6), 1.4)
    p.shape("rect", (12, 50, 84, 62), hexc("#6b4428"), radius=4, line=1.4, tex="leather")
    p.shape("line", [(48, 22), (48, 50)], hexc("#6b4428"), width=4, **NOLINE)
    for y in range(26, 50, 5):
        p.stroke([(45, y), (51, y + 2)], hexc("#e8c898"), 1.0)
    for x in (22, 36, 60, 74):
        p.shape("ellipse", (x - 3, 53, x + 3, 59), GOLD, line=0.6, spec=0.8, rim=0)
    return p.finish(outline=2)


def iron_helm():
    p = _P()
    p.shape("chord", (16, 14, 80, 86), IRON, start=180, end=360, depth=0.18, light=1.35, spec=1.0, tex="metal")
    p.shape("rect", (18, 48, 78, 78), IRON, radius=6, depth=0.12, spec=0.7, tex="metal")
    p.flat("rect", (26, 54, 70, 60), DARK, radius=2)
    for x in (30, 38, 58, 66):
        p.flat("ellipse", (x - 1.5, 66, x + 1.5, 69), DARK)
    p.shape("rect", (45, 54, 51, 78), shade(IRON, 0.85), radius=2, line=1, spec=0.6, rim=0)
    p.shape("line", [(48, 14), (48, 48)], shade(IRON, 1.2), width=5, line=1, spec=0.6, rim=0)
    for x, y in ((22, 52), (74, 52), (22, 74), (74, 74)):
        p.shape("ellipse", (x - 2, y - 2, x + 2, y + 2), hexc("#e0e6ee"), line=0.6, rim=0, ao=0)
    p.shape("poly", [(48, 4), (60, 16), (48, 20), (36, 16)], RED, line=1.2, tex="fur")
    return p.finish(outline=2)


def copper_ring():
    p = _P()
    copper = hexc("#d9894a")
    p.paint_mask(_ring_mask(p, (18, 30, 78, 86), (31, 43, 65, 75)), copper, depth=0.2, light=1.4, spec=1.0)
    p.shape("rect", (36, 32, 60, 44), copper, radius=3, line=1.2, spec=0.6, rim=0)
    p.shape("ellipse", (36, 16, 60, 42), hexc("#3fc0a0"), depth=0.25, light=1.5, line=1.4, gloss=1.0)
    for x, y in ((35, 30), (61, 30), (48, 42)):
        p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), copper, line=0.8, rim=0)
    p.sparkle((42, 23), 5)
    return p.finish(outline=2)


def bone_amulet():
    p = _P()
    p.shape("line", [(18, 10), (48, 44), (78, 10)], hexc("#7a5a3a"), width=4, line=0.8, rim=0)
    for x, y in ((28, 21), (68, 21), (38, 32), (58, 32)):
        p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), hexc("#c8b890"), line=0.7, rim=0)
    p.shape("poly", [(48, 36), (68, 54), (48, 90), (28, 54)], BONE, depth=0.18, tex="bone")
    p.shape("ellipse", (38, 50, 58, 70), hexc("#8a2a2a"), light=1.4, line=1.2, gloss=0.6)
    p.flat("ellipse", (42, 55, 47, 60), DARK)
    p.flat("ellipse", (49, 55, 54, 60), DARK)
    return p.finish(outline=2)


def bone_crown():
    p = _P()
    p.glow((48, 50), 44, hexc("#ff9a2a"), 0.55)
    pts = [(14, 70), (14, 32), (30, 50), (48, 22), (66, 50), (82, 32), (82, 70)]
    p.shape("poly", pts, BONE, depth=0.18, light=1.3, tex="bone")
    for x, y in ((14, 30), (48, 20), (82, 30)):
        p.shape("ellipse", (x - 6, y - 6, x + 6, y + 6), BONE, line=1.2, tex="bone", rim=0)
    p.stroke([(40, 40), (44, 48), (40, 56)], shade(BONE, 0.55), 1.2)
    p.shape("rect", (12, 60, 84, 74), hexc("#f1c24a"), radius=3, line=1.4, light=1.35, spec=1.0)
    for x, c in ((30, "#d6453a"), (48, "#7a3ae0"), (66, "#d6453a")):
        p.shape("ellipse", (x - 5, 62, x + 5, 72), hexc(c), light=1.6, line=1, gloss=1.0, rim=0)
    return p.finish(outline=2)


# ------------------------------------------------------------------ unique items

def rat_fang():
    """Fare Dişi Kolye: a big curved yellowed rat fang on a cord with a red bead (epic)."""
    p = _P()
    p.glow((50, 58), 40, hexc("#b060ff"), 0.45)
    cord = hexc("#6a4a3a")
    p.shape("line", [(14, 8), (26, 30), (40, 42)], cord, width=3.5, line=0.8, rim=0, tex="leather")
    p.shape("line", [(82, 8), (70, 30), (56, 42)], cord, width=3.5, line=0.8, rim=0, tex="leather")
    for x, y, c in ((24, 26, "#8a5ae0"), (72, 26, "#8a5ae0")):
        p.shape("ellipse", (x - 4, y - 4, x + 4, y + 4), hexc(c), line=0.9, gloss=1.0, rim=0)
    # wrapped binding at the root of the fang
    p.shape("rect", (38, 36, 60, 50), hexc("#7a5a44"), radius=4, line=1.2, tex="leather")
    for y in (40, 44, 48):
        p.stroke([(38, y - 1), (60, y + 1)], hexc("#3a2a20"), 1.1)
    fang = [(40, 48), (58, 48), (60, 60), (56, 74), (48, 86), (38, 92), (42, 80), (44, 66)]
    p.shape("poly", fang, hexc("#e8d49a"), depth=0.22, light=1.35, spec=0.8, tex="bone", tex_amt=0.8)
    p.stroke([(46, 52), (47, 66), (43, 82)], hexc("#b89a5a"), 1.4)
    p.stroke([(55, 58), (52, 70)], hexc("#fff4d0", 180), 1.4)
    p.shape("ellipse", (41, 26, 57, 42), hexc("#d8303a"), light=1.5, line=1.2, gloss=1.0)
    p.sparkle((64, 70), 5, hexc("#e8c8ff"))
    return p.finish(outline=2)


def spore_cloak():
    """Spor Pelerini: a mossy green-brown hooded cloak with glowing mushroom spots and drifting spores."""
    p = _P()
    cloth = hexc("#5a6a38")
    spore = hexc("#9aff6a")
    p.glow((48, 56), 42, spore, 0.3)
    body = p.shape("poly", [(30, 22), (66, 22), (80, 70), (86, 88), (68, 84), (58, 90), (48, 84), (38, 90), (28, 84),
                            (10, 88), (16, 70)], cloth, depth=0.14, tex="cloth", tex_amt=0.9)
    p.shape("poly", [(40, 30), (56, 30), (60, 84), (36, 84)], hexc("#2a2418"), depth=0.2, line=1.0, rim=0)
    for pts in ([(28, 40), (20, 84)], [(68, 40), (76, 84)]):
        p.stroke(pts, shade(cloth, 0.6), 1.6)
    # hood
    hood = p.shape("ellipse", (26, 6, 70, 46), shade(cloth, 1.08), depth=0.2, tex="cloth")
    p.shape("ellipse", (34, 16, 62, 44), hexc("#1a1410"), line=1.0, rim=0)
    for x in (43, 53):
        p.glow((x, 30), 5, spore, 0.9)
        p.flat("ellipse", (x - 1.8, 28, x + 1.8, 32), hexc("#e8ffd0"))
    # moss clumps and mushroom spots
    for x, y in ((18, 80), (78, 82), (30, 60)):
        p.shape("ellipse", (x - 7, y - 4, x + 7, y + 4), hexc("#7a9a3e"), line=0.9, tex="fur", rim=0)
    for x, y, r in ((24, 56, 5), (72, 60, 4), (66, 42, 3.5), (30, 34, 3)):
        p.glow((x, y), r * 2.6, spore, 0.65)
        p.shape("chord", (x - r * 1.4, y - r, x + r * 1.4, y + r * 1.2), hexc("#c8ff9a"), start=180, end=360,
                line=0.9, rim=0)
        p.shape("rect", (x - r * 0.35, y, x + r * 0.35, y + r * 0.9), hexc("#f1e3c6"), line=0.7, rim=0)
    p.shape("ellipse", (44, 44, 52, 52), hexc("#b89a5a"), line=0.9, spec=0.8, rim=0)  # clasp
    for x, y, r in ((12, 22, 2), (84, 30, 2.4), (86, 54, 1.6), (8, 48, 1.8), (48, 2, 1.6), (78, 12, 1.4)):
        p.glow((x, y), r * 3, spore, 0.8)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8ffd8"))
    return p.finish(outline=2)


def mimic_ring():
    """Taklitçi Dişi Yüzük: a gold ring whose setting is a tiny toothy chest mouth with a gem tongue."""
    p = _P()
    gold = hexc("#f0bf48")
    p.paint_mask(_ring_mask(p, (18, 38, 78, 92), (30, 50, 66, 82)), gold, depth=0.2, light=1.4, spec=1.0,
                 tex="metal", tex_amt=0.4)
    for x in (24, 72):  # little claw prongs
        p.shape("poly", [(x - 4, 44), (x + 4, 44), (x + (4 if x > 48 else -4), 34)], gold, line=1.0, rim=0)
    wood = hexc("#a0652f")
    # tiny chest: base, gaping mouth, lid tilted back
    p.shape("rect", (26, 32, 70, 52), wood, radius=3, tex="wood_h", line=1.3)
    p.shape("rect", (26, 32, 70, 36), gold, radius=1, line=0.9, rim=0)
    p.shape("poly", [(26, 34), (70, 34), (66, 16), (30, 10)], hexc("#5a1624"), depth=0.15, line=1.2, rim=0)
    p.shape("poly", [(28, 12), (68, 18), (72, 6), (34, 0)], wood, tex="wood_h", line=1.3)
    for i in range(5):
        x = 32 + i * 8
        p.shape("poly", [(x, 13 + i * 1.2), (x + 6, 14 + i * 1.2), (x + 3, 21 + i * 1.2)], WHITE, line=0.7, rim=0,
                ao=0)
        p.shape("poly", [(x + 1, 34), (x + 7, 34), (x + 4, 27)], WHITE, line=0.7, rim=0, ao=0)
    # gem tongue lolling out
    p.shape("poly", [(40, 30), (54, 28), (60, 44), (50, 56), (42, 46)], hexc("#e0306a"), light=1.5, spec=1.0,
            line=1.1, gloss=1.0)
    p.stroke([(48, 30), (50, 50)], hexc("#8a1030"), 1.1)
    for x in (40, 58):  # beady eyes on the lid
        p.flat("ellipse", (x - 2.5, 4 + (x - 40) * 0.1, x + 2.5, 9 + (x - 40) * 0.1), hexc("#ffe14a"))
    p.sparkle((56, 40), 5)
    return p.finish(outline=2)


def warden_axe():
    """Bekçi Baltası: a heavy iron bearded axe with rusty bands and a skull pommel."""
    p = _P()
    iron = hexc("#8a949e")
    p.shape("line", [(70, 10), (30, 84)], hexc("#6b4428"), width=8, line=1.3, tex="wood")
    for t in (0.35, 0.5):
        x, y = 70 - 40 * t, 10 + 74 * t
        p.shape("rect", (x - 6, y - 3, x + 6, y + 3), hexc("#9a5a34"), radius=1, line=1.0, tex="metal", rim=0)
    for t in (0.72, 0.8, 0.88):  # grip wrap
        x, y = 70 - 40 * t, 10 + 74 * t
        p.stroke([(x - 5, y - 1), (x + 5, y + 2)], hexc("#2a1a10"), 1.4)
    head = [(66, 14), (44, 8), (18, 10), (10, 34), (16, 58), (30, 64), (32, 44), (60, 34)]
    p.shape("poly", head, iron, depth=0.2, light=1.4, spec=1.0, tex="metal", tex_amt=0.8)
    p.shape("poly", [(18, 10), (10, 34), (16, 58), (30, 64), (18, 36)], hexc("#dfe7ee"), **dict(shadow=0, light=0,
                                                                                                  line=0))
    for x, y, r in ((40, 22, 4), (48, 30, 3), (28, 40, 3.5)):
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#9a5a34", 210))
    p.shape("rect", (58, 8, 76, 36), hexc("#5a4a44"), radius=3, line=1.2, tex="metal")
    for x, y in ((63, 14), (71, 16), (62, 30), (70, 31)):
        p.shape("ellipse", (x - 1.8, y - 1.8, x + 1.8, y + 1.8), hexc("#c8c0b0"), line=0.6, rim=0, ao=0)
    p.sparkle((16, 22), 5)
    # skull pommel
    p.shape("ellipse", (18, 78, 38, 96), BONE, line=1.2, tex="bone")
    p.shape("rect", (22, 88, 34, 96), BONE, radius=2, line=1.0, rim=0)
    p.flat("ellipse", (21, 83, 27, 89), DARK)
    p.flat("ellipse", (29, 83, 35, 89), DARK)
    return p.finish(outline=2)


def kingslayer():
    """Kral Katili: a legendary dark steel greatsword with a red rune line and a crown crossguard."""
    p = _P()
    p.glow((48, 48), 46, hexc("#ff9a2a"), 0.5)
    steel = hexc("#434a58")
    x0, y0, x1, y1 = 30, 66, 78, 16
    ux, uy, nx, ny = _blade(p, x0, y0, x1, y1, 14, steel, tip=14, fuller=False)
    # glowing rune line down the blade
    p.shape("line", [(x0 + ux * 8, y0 + uy * 8), (x1 - ux * 4, y1 - uy * 4)], hexc("#ff3a2a"), width=3, **NOLINE)
    for t in (14, 26, 38, 50):
        x, y = x0 + ux * t, y0 + uy * t
        p.glow((x, y), 6, hexc("#ff4a2a"), 0.7)
        p.stroke([(x - nx * 0.4, y - ny * 0.4), (x + nx * 0.4 + ux * 3, y + ny * 0.4 + uy * 3)], hexc("#ffb080"), 1.2)
    p.stroke([(x0 + ux * 8, y0 + uy * 8), (x1 - ux * 4, y1 - uy * 4)], hexc("#ffd0a0"), 1.0)
    # crown-shaped crossguard
    cx, cy = x0, y0
    gpts = [(cx - nx * 2.8, cy - ny * 2.8), (cx - nx * 2.8 + ux * 8, cy - ny * 2.8 + uy * 8),
            (cx - nx * 1.4 + ux * 3, cy - ny * 1.4 + uy * 3), (cx + ux * 10, cy + uy * 10),
            (cx + nx * 1.4 + ux * 3, cy + ny * 1.4 + uy * 3), (cx + nx * 2.8 + ux * 8, cy + ny * 2.8 + uy * 8),
            (cx + nx * 2.8, cy + ny * 2.8), (cx + nx * 2.8 - ux * 4, cy + ny * 2.8 - uy * 4),
            (cx - nx * 2.8 - ux * 4, cy - ny * 2.8 - uy * 4)]
    p.shape("poly", gpts, hexc("#f1c24a"), depth=0.25, light=1.4, spec=1.0, line=1.3)
    for s in (-2.8, 0, 2.8):
        x, y = cx + nx * s + ux * (8 if s else 10), cy + ny * s + uy * (8 if s else 10)
        p.shape("ellipse", (x - 2.2, y - 2.2, x + 2.2, y + 2.2), hexc("#f1c24a"), line=0.8, gloss=0.8, rim=0)
    p.shape("ellipse", (cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5), hexc("#e02a2a"), line=1.0, gloss=1.0, rim=0)
    # long two-handed grip and pommel
    p.shape("line", [(cx - ux * 4, cy - uy * 4), (cx - ux * 24, cy - uy * 24)], hexc("#2a1a24"), width=8, line=1.2,
            tex="leather", rim=0)
    for i in range(5):
        t = 6 + i * 4
        x, y = cx - ux * t, cy - uy * t
        p.stroke([(x - nx * 0.6, y - ny * 0.6), (x + nx * 0.6 - ux * 2, y + ny * 0.6 - uy * 2)], hexc("#8a2a2a"), 1.2)
    ex, ey = cx - ux * 28, cy - uy * 28
    p.shape("poly", [(ex, ey - 7), (ex + 6, ey), (ex, ey + 7), (ex - 6, ey)], hexc("#f1c24a"), line=1.2, spec=1.0)
    p.shape("ellipse", (ex - 2.5, ey - 2.5, ex + 2.5, ey + 2.5), hexc("#e02a2a"), line=0.7, gloss=1.0, rim=0)
    p.sparkle((72, 24), 6, hexc("#fff0d0"))
    return p.finish(outline=2)


# ------------------------------------------------------------------ mage staffs and rogue daggers

def _legendary_halo(p, center=(48, 48), radius=46, strength=0.5):
    """The warm halo every legendary icon sits in."""
    p.glow(center, radius, hexc("#ff9a2a"), strength)


def _unit(x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _shaft(p, x0, y0, x1, y1, width, color, tex="wood", bands=(), band_color=None, cap=True):
    """A staff shaft from the butt (x0, y0) to the head (x1, y1); bands are fractions along it."""
    ux, uy = _unit(x0, y0, x1, y1)
    nx, ny = -uy * width / 2, ux * width / 2
    p.shape("line", [(x0, y0), (x1, y1)], color, width=width, depth=0.3, light=1.3, line=1.3, tex=tex, tex_amt=1.0)
    p.stroke([(x0 - nx * 0.45 + ux * 3, y0 - ny * 0.45 + uy * 3), (x1 - nx * 0.45 - ux * 3, y1 - ny * 0.45 - uy * 3)],
             shade(color, 1.3), max(1.0, width * 0.14))
    band_color = band_color or hexc("#b88a4a")
    for t in bands:
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        p.shape("line", [(cx - ux * 2.5, cy - uy * 2.5), (cx + ux * 2.5, cy + uy * 2.5)], band_color,
                width=width + 3, depth=0.35, light=1.4, line=1.1, spec=0.8, rim=0, ao=0.2)
    if cap:
        p.shape("line", [(x0, y0), (x0 + ux * 6, y0 + uy * 6)], band_color, width=width + 1.5, depth=0.35,
                light=1.4, line=1.1, spec=0.8, rim=0)
    return ux, uy, nx, ny


def _gem(p, cx, cy, rx, ry, color, glow=None, glow_r=None, facet=True):
    if glow:
        p.glow((cx, cy), glow_r or max(rx, ry) * 2.6, glow, 0.8)
    pts = [(cx, cy - ry), (cx + rx, cy - ry * 0.25), (cx + rx * 0.7, cy + ry * 0.7), (cx, cy + ry),
           (cx - rx * 0.7, cy + ry * 0.7), (cx - rx, cy - ry * 0.25)]
    p.shape("poly", pts, color, depth=0.3, light=1.55, line=1.2, spec=1.0, gloss=0.8, rim=0.4)
    if facet:
        p.flat("poly", [(cx, cy - ry), (cx - rx, cy - ry * 0.25), (cx, cy)], hexc("#ffffff", 110))
        p.stroke([(cx - rx, cy - ry * 0.25), (cx, cy), (cx + rx, cy - ry * 0.25)], hexc("#ffffff", 120), 0.9)
        p.stroke([(cx, cy), (cx, cy + ry)], shade(color, 0.7), 0.9)


def apprentice_staff():
    """Çırak Asası: a plain pale wooden staff with a small blue crystal in a forked top."""
    p = _P()
    wood = hexc("#b07a42")
    ux, uy, nx, ny = _shaft(p, 18, 90, 62, 32, 9, wood, bands=(0.5,), band_color=hexc("#7a5a3a"))
    for t in (0.44, 0.47, 0.53, 0.56):  # leather wrap around the grip
        cx, cy = 18 + 44 * t, 90 - 58 * t
        p.stroke([(cx - nx * 0.9, cy - ny * 0.9), (cx + nx * 0.9 + ux * 1.5, cy + ny * 0.9 + uy * 1.5)],
                 hexc("#5a3a22"), 1.2)
    # forked top: two short prongs cradling the crystal
    for side in (-1, 1):
        p.shape("line", [(60, 34), (60 + side * 9 + 4, 24 - side * 4), (66 + side * 12, 10 - side * 2)], wood,
                width=6, depth=0.3, line=1.2, tex="wood", rim=0)
    _gem(p, 70, 20, 9, 13, hexc("#7ac8ff"), glow=hexc("#8fd8ff"), glow_r=26)
    p.sparkle((76, 10), 5.5)
    return p.finish(outline=2)


def oak_staff():
    """Meşe Asa: a carved dark oak staff whose curling top holds a green gem, with oak leaves."""
    p = _P()
    oak = hexc("#7a5230")
    ux, uy, nx, ny = _shaft(p, 16, 92, 60, 36, 11, oak, bands=(0.28,), band_color=hexc("#c89a4a"))
    for t in (0.4, 0.5, 0.6, 0.7):  # spiral carving
        cx, cy = 16 + 44 * t, 92 - 56 * t
        p.stroke([(cx - nx * 0.9, cy - ny * 0.9), (cx + nx * 0.9 + ux * 4, cy + ny * 0.9 + uy * 4)],
                 shade(oak, 0.5), 1.4)
    # two curling branches around the gem
    left = [(58, 38), (50, 28), (52, 14), (62, 6), (70, 8)]
    right = [(60, 38), (74, 38), (84, 26), (82, 14), (74, 10)]
    for pts in (left, right):
        p.shape("line", pts, oak, width=7, depth=0.3, line=1.2, tex="wood", rim=0)
    _gem(p, 67, 23, 10, 12, hexc("#3ad06a"), glow=hexc("#6aff8a"), glow_r=28)
    for (x, y, a) in ((50, 22, -40), (84, 32, 30), (46, 34, -70)):  # leaves
        c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = [(x + (dx * c - dy * sn), y + (dx * sn + dy * c)) for dx, dy in ((-7, 0), (-2, -4), (7, 0), (-2, 4))]
        p.shape("poly", pts, hexc("#6aa83a"), depth=0.3, light=1.3, line=1.0, rim=0)
        p.stroke([(x - 6 * c, y - 6 * sn), (x + 6 * c, y + 6 * sn)], hexc("#3a6a1a"), 0.9)
    p.sparkle((60, 18), 5)
    return p.finish(outline=2)


def bone_wand():
    """Kemik Değnek: a short knobbly bone wand tipped with a tiny skull with green eyes."""
    p = _P()
    ux, uy, nx, ny = _shaft(p, 22, 82, 58, 44, 10, BONE, tex="bone", bands=(), cap=False)
    for t in (0.0, 0.45):  # knuckle bulges
        cx, cy = 22 + 36 * t, 82 - 38 * t
        p.shape("ellipse", (cx - 7, cy - 7, cx + 7, cy + 7), BONE, depth=0.3, line=1.2, tex="bone", rim=0)
    p.shape("line", [(34, 69), (42, 61)], hexc("#8a2a3a"), width=10, depth=0.3, line=1.1, tex="cloth", rim=0)
    for i in range(3):
        x, y = 35 + i * 3, 68 - i * 3
        p.stroke([(x - 3, y - 4), (x + 4, y + 3)], hexc("#4a1420"), 1.0)
    p.shape("line", [(38, 70), (34, 82), (38, 88)], hexc("#8a2a3a"), width=3, line=0.8, rim=0, tex="cloth")
    # the skull tip
    cx, cy = 64, 34
    p.glow((cx, cy), 26, hexc("#7aff6a"), 0.35)
    p.shape("ellipse", (cx - 14, cy - 14, cx + 14, cy + 10), BONE, depth=0.2, line=1.3, tex="bone")
    p.shape("rect", (cx - 8, cy + 4, cx + 8, cy + 15), BONE, radius=3, line=1.2, tex="bone")
    for dx in (-5.5, 5.5):
        p.flat("ellipse", (cx + dx - 4, cy - 5, cx + dx + 4, cy + 3), DARK)
        p.glow((cx + dx, cy - 1), 6, hexc("#7aff6a"), 0.9)
        p.flat("ellipse", (cx + dx - 1.5, cy - 2.5, cx + dx + 1.5, cy + 0.5), hexc("#d8ffc8"))
    p.flat("poly", [(cx - 1.5, cy + 5), (cx + 1.5, cy + 5), (cx, cy + 8)], DARK)
    for dx in (-3.5, 0, 3.5):
        p.stroke([(cx + dx, cy + 10), (cx + dx, cy + 14)], shade(BONE, 0.5), 0.9)
    return p.finish(outline=2)


def ember_rod():
    """Kor Değneği (epic): a black iron rod with a claw cage holding a glowing ember core."""
    p = _P()
    iron = hexc("#565a66")
    p.glow((62, 30), 36, hexc("#ff7a2a"), 0.55)
    _shaft(p, 16, 92, 56, 42, 10, iron, tex="metal", bands=(0.3, 0.62), band_color=hexc("#8a4a2a"))
    for t in (0.36, 0.45, 0.54):
        cx, cy = 18 + 38 * t, 90 - 48 * t
        p.stroke([(cx - 3, cy - 3), (cx + 4, cy + 3)], hexc("#2a1a1a"), 1.2)
    # ember core
    cx, cy = 64, 30
    p.glow((cx, cy), 22, hexc("#ffb040"), 0.9)
    p.shape("ellipse", (cx - 11, cy - 11, cx + 11, cy + 11), hexc("#ff6a1e"), depth=0.25, light=1.5, line=1.2,
            rim=0, gloss=0.7, ink=hexc("#6a1a08"))
    p.shape("ellipse", (cx - 6, cy - 6, cx + 5, cy + 5), hexc("#ffd24a"), **dict(shadow=0, light=0, line=0))
    p.flat("ellipse", (cx - 3, cy - 3, cx + 2, cy + 2), hexc("#fff8d0"))
    for pts in ([(cx - 8, cy + 2), (cx - 2, cy + 4), (cx + 2, cy + 9)], [(cx + 4, cy - 8), (cx + 7, cy - 1)]):
        p.stroke(pts, hexc("#b8300e"), 1.4)
    # iron claws curling around it
    for pts in ([(56, 42), (48, 32), (52, 18), (60, 16)], [(56, 42), (68, 44), (78, 36), (78, 26)],
                [(56, 42), (60, 30), (70, 20), (76, 18)]):
        p.shape("line", pts, iron, width=4, depth=0.3, line=1.1, spec=0.8, tex="metal", rim=0)
    for x, y in ((60, 16), (78, 26), (76, 18)):
        p.shape("poly", [(x - 2.5, y + 1), (x + 2.5, y + 1), (x + 1, y - 4)], iron, line=0.9, spec=0.6, rim=0)
    for x, y, r in ((80, 12, 1.8), (46, 20, 1.5), (84, 24, 1.3), (70, 6, 1.4)):
        p.glow((x, y), r * 3.5, hexc("#ffb040"), 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffe080"))
    return p.finish(outline=2)


def grave_scepter():
    """Mezar Asası (legendary): a black scepter crowned by a gold-crowned skull in purple flame."""
    p = _P()
    _legendary_halo(p)
    violet = hexc("#b060ff")
    p.glow((60, 26), 34, violet, 0.7)
    _shaft(p, 14, 94, 52, 50, 10, hexc("#2e2838"), tex="metal", bands=(0.25, 0.55, 0.85), band_color=hexc("#e7b440"))
    for t in (0.35, 0.45):
        cx, cy = 16 + 36 * t, 92 - 42 * t
        p.flat("ellipse", (cx - 2, cy - 2, cx + 2, cy + 2), hexc("#b060ff"))
    # purple flame rising behind the skull
    cx, cy = 60, 38
    fl = [(cx - 16, cy - 2), (cx - 20, cy - 18), (cx - 10, cy - 28), (cx - 8, cy - 20), (cx - 2, cy - 38),
          (cx + 6, cy - 26), (cx + 14, cy - 34), (cx + 20, cy - 16), (cx + 16, cy - 2)]
    p.shape("poly", fl, hexc("#8a3ae0"), shadow=0.8, light=1.4, depth=0.2, line=1.2, rim=0, ink=hexc("#2a0a4a"))
    p.shape("poly", [(cx - 10, cy - 4), (cx - 8, cy - 20), (cx, cy - 30), (cx + 8, cy - 20), (cx + 10, cy - 4)],
            hexc("#c890ff"), **dict(shadow=0, light=0, line=0))
    # collar and skull
    p.shape("ellipse", (cx - 12, cy + 12, cx + 12, cy + 20), hexc("#e7b440"), depth=0.3, light=1.4, line=1.1, spec=1.0,
            rim=0)
    p.shape("ellipse", (cx - 13, cy - 12, cx + 13, cy + 10), BONE, depth=0.2, line=1.3, tex="bone")
    p.shape("rect", (cx - 7, cy + 4, cx + 7, cy + 15), BONE, radius=3, line=1.2, tex="bone")
    for dx in (-5, 5):
        p.flat("ellipse", (cx + dx - 3.5, cy - 4, cx + dx + 3.5, cy + 3), DARK)
        p.glow((cx + dx, cy - 0.5), 6, violet, 1.0)
        p.flat("ellipse", (cx + dx - 1.3, cy - 1.8, cx + dx + 1.3, cy + 0.8), hexc("#f0d8ff"))
    p.flat("poly", [(cx - 1.5, cy + 5), (cx + 1.5, cy + 5), (cx, cy + 8)], DARK)
    for dx in (-3, 0, 3):
        p.stroke([(cx + dx, cy + 10), (cx + dx, cy + 14)], shade(BONE, 0.5), 0.9)
    # little gold crown on the skull
    crown = [(cx - 11, cy - 8), (cx - 12, cy - 20), (cx - 5, cy - 13), (cx, cy - 23), (cx + 5, cy - 13), (cx + 12, cy - 20),
             (cx + 11, cy - 8)]
    p.shape("poly", crown, hexc("#f1c24a"), depth=0.25, light=1.45, line=1.2, spec=1.0)
    p.shape("ellipse", (cx - 2.5, cy - 13, cx + 2.5, cy - 8), hexc("#7a3ae0"), line=0.8, gloss=1.0, rim=0)
    for x, y, r in ((30, 20, 1.8), (84, 44, 2.0), (80, 12, 1.6)):
        p.glow((x, y), r * 3.5, violet, 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8d0ff"))
    p.sparkle((74, 20), 6, hexc("#fff0d0"))
    p.sparkle((40, 60), 4, hexc("#fff0d0"))
    return p.finish(outline=2)


def rusty_dagger():
    """Paslı Hançer: a short pitted blade with a plain wooden guard."""
    p = _P()
    ux, uy, nx, ny = _blade(p, 38, 60, 68, 30, 14, hexc("#b9a592"), tip=14)
    for fx, fy, r in ((47, 52, 4.5), (57, 42, 3.5), (63, 36, 2.4), (43, 56, 2.8)):
        p.flat("ellipse", (fx - r, fy - r * 0.8, fx + r, fy + r * 0.8), mix(RUST, hexc("#6a3a1a"), 0.3)[:3] + (220,))
    p.stroke([(64, 39), (67, 35)], hexc("#6a3a1a"), 1.2)  # a nick in the edge
    _hilt(p, 38, 60, ux, uy, nx, ny, guard=hexc("#8a6a4a"), grip=hexc("#6a4a30"), length=18)
    return p.finish(outline=2)


def steel_dagger():
    """Çelik Hançer: a polished steel dagger with a blue pommel stone."""
    p = _P()
    ux, uy, nx, ny = _blade(p, 38, 60, 70, 28, 14, STEEL, tip=15)
    _hilt(p, 38, 60, ux, uy, nx, ny, grip=hexc("#3a2a3a"), length=18, gem=hexc("#3a8ae0"))
    p.sparkle((68, 28), 6)
    return p.finish(outline=2)


def bone_shiv():
    """Kemik Bıçak: a jagged knife carved from bone, handle bound with leather strips."""
    p = _P()
    # serrated bone blade pointing to the upper right
    spine = [(40, 56), (72, 22)]
    blade = [(34, 50), (44, 38), (49, 40), (55, 31), (60, 34), (66, 25), (71, 27), (84, 10), (76, 32), (62, 50),
             (46, 62)]
    p.shape("poly", blade, BONE, depth=0.25, light=1.3, line=1.4, spec=0.5, tex="bone", tex_amt=0.9)
    p.stroke([(42, 54), (58, 40), (74, 24)], shade(BONE, 0.7), 1.3)
    p.stroke([(40, 50), (48, 44)], hexc("#fff8e8", 190), 1.2)
    # handle: a knuckle joint and leather wrap
    p.shape("line", [(40, 58), (22, 76)], shade(BONE, 0.92), width=10, depth=0.3, line=1.2, tex="bone")
    p.shape("ellipse", (12, 72, 28, 88), BONE, depth=0.25, line=1.3, tex="bone")
    for i in range(5):
        x, y = 38 - i * 3.6, 60 + i * 3.6
        p.shape("line", [(x - 5, y - 4), (x + 5, y + 4)], hexc("#7a4a2a"), width=3.2, depth=0.35, line=0.9,
                tex="leather", rim=0, ao=0.2)
    p.shape("line", [(24, 76), (18, 90), (24, 94)], hexc("#7a4a2a"), width=2.5, line=0.8, rim=0, tex="leather")
    p.shape("ellipse", (21, 90, 27, 96), hexc("#8a2a2a"), line=0.8, gloss=0.8, rim=0)
    return p.finish(outline=2)


def wardens_key():
    """Bekçinin Anahtarı (epic): the warden's oversized iron key, its bit ground into a blade."""
    p = _P()
    iron = hexc("#7a828c")
    p.glow((56, 40), 40, hexc("#b060ff"), 0.35)
    # blade-edged shank and point
    ux, uy = _unit(34, 62, 78, 18)
    nx, ny = -uy * 5, ux * 5
    pts = [(34 + nx, 62 + ny), (70 + nx, 26 + ny), (82, 12), (72 - nx * 1.6, 26 - ny * 1.6), (40 - nx * 1.6, 56 - ny * 1.6),
           (34 - nx, 62 - ny)]
    p.shape("poly", pts, iron, depth=0.3, light=1.4, line=1.4, spec=1.0, tex="metal", tex_amt=0.8)
    p.stroke([(38 - nx * 1.3, 58 - ny * 1.3), (72 - nx * 1.3, 24 - ny * 1.3), (81, 13)], hexc("#f0f6ff", 200), 1.4)
    # key bit (teeth) along the back of the shank
    for t, h in ((0.42, 8), (0.52, 5), (0.6, 8)):
        cx, cy = 34 + 44 * t, 62 - 44 * t
        p.shape("poly", [(cx + nx, cy + ny), (cx + nx + ux * 5, cy + ny + uy * 5),
                         (cx + nx * (1 + h / 5) + ux * 5, cy + ny * (1 + h / 5) + uy * 5),
                         (cx + nx * (1 + h / 5), cy + ny * (1 + h / 5))], iron, depth=0.3, line=1.1, spec=0.6,
                tex="metal", rim=0)
    for x, y, r in ((50, 48, 3), (60, 38, 2.2), (44, 52, 2)):
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#9a5a34", 200))
    # collar and the big ring bow
    p.shape("line", [(30, 66), (38, 58)], hexc("#5a6068"), width=12, depth=0.3, line=1.2, spec=0.7, tex="metal", rim=0)
    ring = ImageChops.subtract(p._mask("ellipse", (6, 60, 38, 92)), p._mask("ellipse", (14, 68, 30, 84)))
    p.paint_mask(ring, iron, depth=0.25, light=1.4, spec=1.0, tex="metal", tex_amt=0.8)
    for a in range(0, 360, 60):
        x, y = 22 + 12 * math.cos(math.radians(a)), 76 + 12 * math.sin(math.radians(a))
        p.shape("ellipse", (x - 1.8, y - 1.8, x + 1.8, y + 1.8), hexc("#c8c0b0"), line=0.6, rim=0, ao=0)
    p.shape("ellipse", (18, 72, 26, 80), hexc("#8a4aff"), line=0.9, gloss=1.0, rim=0)
    p.sparkle((76, 20), 5)
    return p.finish(outline=2)


def _bez(p0, p1, p2, p3, n=16):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def _tapered(center, w0, w1=0.0, power=1.0, bulge=0.0):
    """Polygon around a centre line whose width goes from w0 to w1 (bulge widens the middle)."""
    left, right = [], []
    n = len(center) - 1
    for i, (x, y) in enumerate(center):
        a = center[max(0, i - 1)]
        b = center[min(n, i + 1)]
        ux, uy = _unit(a[0], a[1], b[0], b[1])
        t = i / n
        w = (w1 + (w0 - w1) * (1 - t) ** power + bulge * math.sin(math.pi * t)) / 2
        left.append((x - uy * w, y + ux * w))
        right.append((x + uy * w, y - ux * w))
    return left + right[::-1], left, right


def _curve(cx, cy, r, a0, a1, n=12):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def nightfang():
    """Gece Dişi (legendary): a black curved fang dagger with a violet edge glow."""
    p = _P()
    _legendary_halo(p, strength=0.35)
    violet = hexc("#a050ff")
    p.glow((58, 38), 36, violet, 0.8)
    # the fang: wide at the guard, sweeping up and curling to a hooked point
    center = _bez((36, 62), (46, 44), (54, 22), (82, 10), 20)
    poly, left, right = _tapered(center, 21, 0.5, power=1.1)
    p.shape("poly", poly, hexc("#26202e"), depth=0.25, light=1.12, line=1.4, spec=0.5, tex="metal", tex_amt=0.6,
            rim=0.8, ink=hexc("#0e0814"))
    edge = right[2:-1]
    p.stroke(edge, hexc("#c890ff"), 2.0)
    p.stroke(edge, hexc("#ffffff", 190), 0.8)
    p.stroke(center[2:-3], hexc("#5a5070"), 1.2)
    # fang guard, grip, pommel
    p.shape("poly", [(24, 58), (36, 50), (48, 62), (42, 74), (38, 62)], BONE, depth=0.3, line=1.2, tex="bone", rim=0)
    p.shape("line", [(38, 64), (22, 80)], hexc("#1e1824"), width=9, depth=0.3, line=1.2, tex="leather", rim=0)
    for i in range(3):
        x, y = 35 - i * 4.5, 67 + i * 4.5
        p.stroke([(x - 4, y - 3), (x + 4, y + 3)], hexc("#b8b0c8"), 1.1)
    p.shape("ellipse", (12, 76, 26, 90), hexc("#2c2636"), depth=0.3, line=1.2, spec=1.0)
    p.shape("ellipse", (15, 79, 23, 87), violet, line=0.8, gloss=1.0, rim=0)
    p.glow((19, 83), 8, violet, 0.8)
    for x, y, r in ((84, 34, 1.8), (70, 52, 1.5), (60, 8, 1.4), (86, 56, 1.3)):
        p.glow((x, y), r * 3.5, violet, 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8d0ff"))
    p.sparkle((70, 18), 6, hexc("#fff0ff"))
    p.sparkle((44, 44), 3.5, hexc("#fff0ff"))
    return p.finish(outline=2)


# ------------------------------------------------------------------ dungeon uniques

def _cord(p, left, right, color=None, beads=(), width=3.5):
    color = color or hexc("#6a4a3a")
    for pts in (left, right):
        p.shape("line", pts, color, width=width, line=0.8, rim=0, tex="leather")
    for x, y, c in beads:
        p.shape("ellipse", (x - 3.8, y - 3.8, x + 3.8, y + 3.8), c, line=0.9, gloss=1.0, rim=0)


def _heart_mask(p, cx, cy, s):
    return p.union([("ellipse", (cx - 12 * s, cy - 10 * s, cx + 1 * s, cy + 3 * s)),
                    ("ellipse", (cx - 1 * s, cy - 10 * s, cx + 12 * s, cy + 3 * s)),
                    ("poly", [(cx - 11.5 * s, cy - 1 * s), (cx + 11.5 * s, cy - 1 * s), (cx, cy + 13 * s)])])


def sporeheart_amulet():
    """Spor Kalbi (epic): a root-bound bronze amulet around a glowing green spore heart."""
    p = _P()
    spore = hexc("#8aff5a")
    p.glow((48, 58), 40, spore, 0.45)
    _cord(p, [(16, 6), (28, 26), (40, 36)], [(80, 6), (68, 26), (56, 36)],
          beads=((26, 23, hexc("#6ac84a")), (70, 23, hexc("#6ac84a"))))
    ring = ImageChops.subtract(p._mask("ellipse", (22, 32, 74, 84)), p._mask("ellipse", (30, 40, 66, 76)))
    p.paint_mask(ring, hexc("#a8763a"), depth=0.22, light=1.4, spec=0.9, tex="metal", tex_amt=0.6)
    p.shape("ellipse", (30, 40, 66, 76), hexc("#1e2a18"), depth=0.25, line=1.0, rim=0, ao=0)
    p.shape("rect", (42, 28, 54, 38), hexc("#a8763a"), radius=3, line=1.1, spec=0.7, rim=0)
    for pts in ([(24, 60), (18, 70), (20, 80)], [(72, 52), (80, 58), (82, 68)], [(40, 82), (38, 90)]):  # roots
        p.shape("line", pts, hexc("#6a4a2a"), width=3.5, line=0.9, tex="wood", rim=0)
    p.glow((48, 58), 20, spore, 0.9)
    heart = _heart_mask(p, 48, 57, 1.25)
    p.paint_mask(heart, hexc("#5ad13a"), depth=0.25, light=1.55, line=1.2, gloss=1.0, rim=0.4, ink=hexc("#14400c"))
    for x, y, r in ((44, 54, 1.6), (52, 60, 1.3), (48, 64, 1.1), (54, 52, 1.0)):
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#eaffd8"))
    for x, y, r in ((14, 48, 2.0), (84, 44, 2.2), (80, 86, 1.6), (12, 82, 1.8), (48, 94, 1.4)):
        p.glow((x, y), r * 3.2, spore, 0.8)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8ffd8"))
    p.sparkle((60, 48), 4.5, hexc("#eaffd8"))
    return p.finish(outline=2)


def shroom_cap():
    """Mantar Başlık (epic helm): a red white-spotted mushroom cap worn as a helmet."""
    p = _P()
    red = hexc("#d8402a")
    p.glow((48, 50), 42, hexc("#ff7a5a"), 0.3)
    # gills underneath and the leather band
    p.shape("chord", (18, 50, 78, 78), hexc("#efe0c0"), start=0, end=180, depth=0.2, line=1.2)
    for x in range(24, 74, 5):
        p.stroke([(48 + (x - 48) * 0.35, 56), (x, 70)], hexc("#b8a078"), 1.0)
    for x in (32, 64):  # chin straps
        p.shape("line", [(x, 60), (x + (4 if x < 48 else -4), 86)], hexc("#6b4428"), width=4, line=0.9, tex="leather",
                rim=0)
    p.shape("ellipse", (41, 82, 55, 92), GOLD, line=1.0, spec=0.8, rim=0)
    cap = p.shape("chord", (6, 10, 90, 88), red, start=180, end=360, depth=0.18, light=1.35, spec=0.6, gloss=0.4)
    p.shape("rect", (6, 44, 90, 54), shade(red, 0.8), radius=5, depth=0.3, line=1.3, rim=0)
    for x, y, r in ((30, 26, 6.5), (54, 20, 5), (70, 34, 6), (40, 40, 4.5), (18, 40, 4), (80, 44, 3.2), (60, 38, 3)):
        p.shape("ellipse", (x - r, y - r * 0.85, x + r, y + r * 0.85), hexc("#fbf3e4"), depth=0.3, light=1.2, line=0.9,
                rim=0, ao=0, clip=cap)
    p.sparkle((36, 18), 4.5)
    return p.finish(outline=2)


def mother_mantle():
    """Ana Spor Mantosu (legendary armour): a mossy purple mantle sprouting glowing mushrooms."""
    p = _P()
    _legendary_halo(p)
    glow_c = hexc("#6affe0")
    cloth = hexc("#6a3a82")
    p.shape("poly", [(22, 30), (74, 30), (86, 88), (68, 82), (58, 90), (48, 84), (38, 90), (28, 82), (10, 88)], cloth,
            depth=0.14, tex="cloth", tex_amt=0.9)
    p.shape("poly", [(40, 34), (56, 34), (60, 86), (36, 86)], hexc("#2a1a30"), depth=0.2, line=1.0, rim=0)
    for pts in ([(26, 44), (18, 84)], [(70, 44), (78, 84)], [(34, 40), (30, 84)], [(62, 40), (66, 84)]):
        p.stroke(pts, shade(cloth, 0.6), 1.5)
    # broad mossy shoulder cape
    cape = p.shape("ellipse", (8, 16, 88, 50), hexc("#5a7a3a"), depth=0.2, tex="fur", tex_amt=1.0)
    p.shape("ellipse", (34, 18, 62, 34), hexc("#2a1a30"), line=1.0, rim=0, ao=0)  # neck opening
    for x, y in ((14, 46), (28, 50), (68, 50), (82, 46), (48, 50)):
        p.shape("ellipse", (x - 6, y - 4, x + 6, y + 4), hexc("#6a8a44"), line=0.8, tex="fur", rim=0)
    # glowing mushrooms on the shoulders
    for x, y, r, c in ((22, 26, 6, glow_c), (72, 24, 7, hexc("#ff7ad8")), (80, 36, 4.5, glow_c), (14, 36, 4,
                                                                                                  hexc("#ff7ad8")),
                       (60, 22, 3.8, glow_c)):
        p.glow((x, y), r * 2.6, c, 0.75)
        p.shape("rect", (x - r * 0.3, y - 1, x + r * 0.3, y + r * 1.1), hexc("#f1e3c6"), line=0.8, rim=0, ao=0)
        p.shape("chord", (x - r * 1.3, y - r, x + r * 1.3, y + r * 1.1), c, start=180, end=360, light=1.4, line=0.9,
                rim=0, gloss=0.6)
    p.shape("ellipse", (43, 36, 53, 46), hexc("#b060ff"), line=1.0, gloss=1.0, rim=0)  # clasp gem
    for x, y, r in ((6, 60, 1.8), (90, 64, 2.0), (48, 6, 1.6), (86, 14, 1.4)):
        p.glow((x, y), r * 3.2, glow_c, 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e0fff8"))
    p.sparkle((70, 64), 5, hexc("#fff0d0"))
    return p.finish(outline=2)


def frost_ring():
    """Ayaz Yüzüğü (epic): a silver ring set with a cluster of ice crystals."""
    p = _P()
    silver = hexc("#c8d4e0")
    p.glow((48, 36), 38, hexc("#8fdcff"), 0.55)
    p.paint_mask(_ring_mask(p, (18, 36, 78, 92), (30, 48, 66, 80)), silver, depth=0.2, light=1.4, spec=1.0,
                 tex="metal", tex_amt=0.4)
    p.shape("rect", (34, 34, 62, 46), silver, radius=3, line=1.2, spec=0.7, rim=0)
    ice = hexc("#b8ecff")
    ink = hexc("#16305a")
    for pts in ([(40, 40), (30, 22), (34, 16), (44, 36)], [(56, 40), (68, 20), (72, 26), (54, 42)],
                [(42, 42), (44, 12), (48, 4), (54, 12), (56, 42)]):
        p.shape("poly", pts, ice, depth=0.3, light=1.5, line=1.2, spec=1.0, rim=0.5, ink=ink)
    p.flat("poly", [(44, 12), (48, 4), (48, 40), (43, 40)], hexc("#ffffff", 110))
    p.stroke([(48, 6), (49, 38)], hexc("#6ab0e0"), 1.0)
    for x in (32, 64):
        p.stroke([(x, 50), (x - 2, 58)], hexc("#e8f8ff"), 1.4)
    p.sparkle((42, 14), 5)
    p.sparkle((70, 56), 3.5, hexc("#d8f4ff"))
    return p.finish(outline=2)


def yeti_hide():
    """Yeti Postu (epic armour): a shaggy white fur coat with horn toggles and a leather belt."""
    p = _P()
    fur = hexc("#e8e6e2")
    p.glow((48, 50), 42, hexc("#8fdcff"), 0.35)
    outline = [(24, 18), (38, 14), (48, 22), (58, 14), (72, 18), (82, 42), (70, 46), (70, 84), (26, 84), (26, 46),
               (14, 42)]
    items = [("poly", outline)]
    # lumpy tufts all along the edge make the silhouette shaggy
    for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 7))
        for i in range(n):
            t = (i + 0.5) / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            r = 3.6 + (i % 2) * 1.2
            items.append(("ellipse", (x - r, y - r, x + r, y + r)))
    for x in range(28, 72, 6):  # long hem tassels
        items.append(("poly", [(x - 4, 84), (x + 4, 84), (x + 1, 93)]))
    body = p.union(items)
    p.paint_mask(body, fur, depth=0.14, light=1.25, tex="fur", tex_amt=1.4, ink=hexc("#3a4458"))
    rnd = 5
    for i in range(40):  # fur tufts: little curved strands
        rnd = (rnd * 1103515245 + 12345) & 0x7FFFFFFF
        x = 28 + (rnd % 400) / 10
        y = 36 + ((rnd >> 10) % 440) / 10
        p.stroke([(x, y), (x - 1.5, y + 2.5), (x - 0.5, y + 5)], hexc("#98a4bc", 170), 1.0)
    # shaggy fur mantle over the shoulders, with the neck opening
    tufts = [("ellipse", (x - r, y - r, x + r, y + r)) for x, y, r in
             ((22, 26, 9), (32, 20, 10), (48, 18, 11), (64, 20, 10), (74, 26, 9), (40, 30, 9), (56, 30, 9))]
    p.paint_mask(p.union(tufts), shade(fur, 1.05), depth=0.25, light=1.25, tex="fur", tex_amt=1.4,
                 ink=hexc("#3a4458"))
    p.shape("ellipse", (41, 12, 55, 21), hexc("#2a2a38"), line=1.0, rim=0, ao=0)
    p.stroke([(48, 38), (48, 76)], hexc("#9aa4b8"), 1.8)
    for y in (42, 54):  # horn toggles
        p.shape("line", [(42, y), (54, y - 2)], hexc("#c8a878"), width=4.5, depth=0.3, line=1.0, tex="bone", rim=0)
    p.shape("rect", (26, 64, 70, 72), hexc("#6b4428"), radius=2, line=1.1, tex="leather")
    p.shape("rect", (43, 62, 53, 74), hexc("#9aa6b2"), radius=2, line=1.0, spec=0.8, rim=0)
    p.shape("line", [(30, 72), (28, 82)], hexc("#6b4428"), width=3, line=0.8, rim=0)
    p.shape("poly", [(24, 80), (32, 80), (28, 88)], hexc("#8fdcff"), line=0.8, gloss=0.8, rim=0)  # an ice charm
    p.sparkle((32, 22), 4.5, hexc("#e8f8ff"))
    return p.finish(outline=2)


def frostbreath_scale():
    """Ayaz Nefesi Pulu (legendary helm): a helm of pale blue dragon scale with ice crystal horns."""
    p = _P()
    _legendary_halo(p)
    p.glow((48, 44), 40, hexc("#8fdcff"), 0.55)
    scale = hexc("#8cc4e6")
    ice = hexc("#d8f6ff")
    ink = hexc("#16305a")
    # crystal horns sweeping up from the temples
    for s in (-1, 1):
        pts = [(48 + s * 20, 40), (48 + s * 30, 26), (48 + s * 34, 8), (48 + s * 40, 2), (48 + s * 38, 18),
               (48 + s * 32, 36), (48 + s * 26, 48)]
        p.shape("poly", pts, ice, depth=0.3, light=1.5, line=1.3, spec=1.0, rim=0.5, ink=ink)
        p.stroke([(48 + s * 24, 42), (48 + s * 33, 22), (48 + s * 39, 4)], hexc("#ffffff", 200), 1.1)
    dome = p.shape("chord", (18, 16, 78, 88), scale, start=180, end=360, depth=0.18, light=1.35, spec=1.0,
                   tex="metal", tex_amt=0.4, ink=ink)
    cheek = p.shape("rect", (20, 48, 76, 80), scale, radius=8, depth=0.12, spec=0.7, ink=ink)
    both = ImageChops.lighter(dome, cheek)
    for row in range(6):  # overlapping scales
        y = 22 + row * 9
        for col in range(8):
            x = 16 + col * 9 + (4.5 if row % 2 else 0)
            p.shape("chord", (x - 5, y - 4, x + 5, y + 6), shade(scale, 1.1), start=0, end=180, depth=0.35, line=0.7,
                    light=1.4, rim=0, ao=0, clip=both, ink=ink)
    # face opening: a narrow T visor with an icy glint
    p.flat("rect", (30, 54, 66, 60), hexc("#101a2a"), radius=2)
    p.flat("rect", (44, 56, 52, 78), hexc("#101a2a"), radius=2)
    for x in (37, 59):
        p.glow((x, 57), 6, hexc("#8fdcff"), 0.9)
        p.flat("ellipse", (x - 2, 56, x + 2, 58.5), hexc("#e8fbff"))
    p.shape("poly", [(48, 26), (53, 34), (48, 42), (43, 34)], ice, line=1.0, spec=1.0, gloss=0.8, rim=0, ink=ink)
    p.sparkle((30, 30), 5, hexc("#fff0d0"))
    p.sparkle((84, 10), 4, hexc("#e8fbff"))
    return p.finish(outline=2)


def imp_horn():
    """İmp Boynuzu (epic): a curved red imp horn with a gold cap, hanging on a cord, its tip smouldering."""
    p = _P()
    p.glow((56, 66), 38, hexc("#ff7a2a"), 0.45)
    _cord(p, [(14, 6), (28, 22), (44, 34)], [(82, 6), (66, 20), (50, 34)],
          beads=((24, 17, hexc("#ffb040")), (72, 17, hexc("#ffb040"))))
    # the horn: thick at the gold-capped root, sweeping down and curling up to a point
    center = _bez((46, 38), (30, 70), (54, 94), (78, 70), 22)
    poly, left, right = _tapered(center, 20, 1.0, power=1.2)
    p.shape("poly", poly, hexc("#c8302a"), depth=0.28, light=1.45, line=1.4, spec=0.9, tex="bone", tex_amt=0.6,
            ink=hexc("#3a0a0a"))
    for i in range(3, 17, 3):  # ridges
        p.stroke([left[i], right[i]], hexc("#7a1414"), 1.4)
    p.stroke(right[2:-2], hexc("#ff9a8a", 170), 1.2)
    p.shape("line", [left[0], right[0]], GOLD, width=8, depth=0.3, light=1.4, line=1.1, spec=1.0, rim=0)
    p.shape("ellipse", (43, 30, 53, 40), GOLD, line=1.0, spec=0.8, rim=0)
    tx, ty = center[-1]
    p.glow((tx, ty), 14, hexc("#ffb040"), 1.0)
    p.flat("ellipse", (tx - 2.4, ty - 2.4, tx + 2.4, ty + 2.4), hexc("#fff0a0"))
    for x, y, r in ((tx + 4, ty - 10, 1.6), (tx - 6, ty - 12, 1.3), (tx + 8, ty - 20, 1.2)):
        p.glow((x, y), r * 3.5, hexc("#ffb040"), 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffe080"))
    p.sparkle((40, 56), 4.5)
    return p.finish(outline=2)


def flame_knight_helm():
    """Alev Şövalyesi Miğferi (epic helm): a blackened plate helm with a burning plume."""
    p = _P()
    plate = hexc("#46404a")
    p.glow((48, 30), 40, hexc("#ff7a2a"), 0.5)
    # flame plume
    cx, cy = 48, 24
    outer = [(cx - 14, cy + 4), (cx - 18, cy - 8), (cx - 10, cy - 16), (cx - 8, cy - 8), (cx - 2, cy - 24),
             (cx + 6, cy - 10), (cx + 14, cy - 18), (cx + 18, cy - 4), (cx + 14, cy + 4)]
    p.shape("poly", outer, hexc("#ff6a1e"), shadow=0.8, light=1.35, depth=0.2, line=1.3, rim=0, ink=hexc("#6a1a08"))
    p.shape("poly", [(cx - 8, cy + 4), (cx - 6, cy - 8), (cx, cy - 16), (cx + 7, cy - 6), (cx + 8, cy + 4)],
            hexc("#ffc248"), **NOLINE)
    p.shape("poly", [(cx - 3, cy + 4), (cx, cy - 6), (cx + 3, cy + 4)], hexc("#fff4c0"), **NOLINE)
    p.shape("chord", (16, 18, 80, 90), plate, start=180, end=360, depth=0.18, light=1.35, spec=1.0, tex="metal",
            ink=hexc("#120c10"))
    p.shape("rect", (18, 52, 78, 82), plate, radius=6, depth=0.12, spec=0.7, tex="metal", ink=hexc("#120c10"))
    p.shape("rect", (44, 16, 52, 30), hexc("#8a4a2a"), radius=2, line=1.0, spec=0.6, rim=0)  # plume socket
    # ember-hot visor slit and breaths
    p.flat("rect", (24, 56, 72, 63), hexc("#1a0a08"), radius=2)
    p.glow((48, 59), 20, hexc("#ff7a2a"), 0.7)
    p.flat("rect", (28, 58, 68, 61), hexc("#ff9a3a"), radius=1)
    for x in (32, 40, 56, 64):
        p.flat("rect", (x - 1.3, 68, x + 1.3, 76), hexc("#1a0a08"), radius=1)
        p.flat("rect", (x - 0.6, 70, x + 0.6, 74), hexc("#ff7a2a"))
    p.shape("line", [(48, 32), (48, 54)], shade(plate, 1.25), width=5, line=1, spec=0.6, rim=0)
    for x, y in ((22, 56), (74, 56), (22, 78), (74, 78)):
        p.shape("ellipse", (x - 2.2, y - 2.2, x + 2.2, y + 2.2), hexc("#d8904a"), line=0.6, rim=0, ao=0)
    for pts in ([(22, 44), (30, 48)], [(66, 40), (74, 46)]):  # scorch cracks glowing
        p.stroke(pts, hexc("#ff8a3a"), 1.2)
    return p.finish(outline=2)


def priestess_censer():
    """Kor Rahibesi'nin Buhurdanı (legendary): a gold censer on a chain, embers glowing through it."""
    p = _P()
    _legendary_halo(p)
    gold = hexc("#f0bf48")
    # chain
    for i in range(6):
        y = 4 + i * 5
        if i % 2:
            p.shape("rect", (46.5, y - 3, 49.5, y + 3), gold, radius=1.5, line=0.8, spec=0.6, rim=0)
        else:
            ring = ImageChops.subtract(p._mask("ellipse", (44.5, y - 3.5, 51.5, y + 3.5)),
                                       p._mask("ellipse", (46.5, y - 1.8, 49.5, y + 1.8)))
            p.paint_mask(ring, gold, line=0.8, spec=0.6, rim=0)
    # smoke curling up
    for pts in ([(34, 40), (28, 30), (34, 20), (28, 10)], [(62, 40), (70, 30), (64, 20), (70, 8)]):
        p.stroke(pts, hexc("#d8d0e0", 150), 4, soft=1.0)
    p.glow((48, 62), 30, hexc("#ffa040"), 0.8)
    # bowl, pierced dome lid, finial
    p.shape("chord", (24, 44, 72, 88), gold, start=0, end=180, depth=0.2, light=1.4, spec=1.0, tex="metal",
            tex_amt=0.4)
    lid = p.shape("chord", (24, 38, 72, 80), gold, start=180, end=360, depth=0.2, light=1.4, spec=1.0, tex="metal",
                  tex_amt=0.4)
    for x, y in ((34, 52), (42, 46), (54, 46), (62, 52), (48, 54), (38, 58), (58, 58)):
        p.flat("ellipse", (x - 2.4, y - 2.4, x + 2.4, y + 2.4), hexc("#6a1a08"))
        p.flat("ellipse", (x - 1.4, y - 1.4, x + 1.4, y + 1.4), hexc("#ffb040"))
    p.shape("rect", (22, 58, 74, 64), shade(gold, 0.85), radius=3, line=1.1, spec=0.8, rim=0)
    p.shape("ellipse", (42, 30, 54, 42), gold, line=1.1, spec=1.0, gloss=0.8, rim=0)
    p.shape("rect", (40, 84, 56, 90), shade(gold, 0.85), radius=2, line=1.0, spec=0.6, rim=0)  # foot
    p.shape("ellipse", (44, 67, 52, 75), hexc("#d6453a"), line=0.9, gloss=1.0, rim=0)
    # embers spilling out
    for x, y, r in ((20, 70, 1.8), (78, 66, 2.0), (70, 82, 1.5), (26, 84, 1.4), (84, 50, 1.4)):
        p.glow((x, y), r * 3.5, hexc("#ffa040"), 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffe080"))
    p.sparkle((36, 44), 5, hexc("#fff0d0"))
    return p.finish(outline=2)


def whelp_tooth():
    """Yavru Ejder Dişi (epic): a big curved dragon tooth set in gold, on a cord with teal beads."""
    p = _P()
    teal = hexc("#2ab8a8")
    p.glow((48, 60), 40, hexc("#b060ff"), 0.4)
    _cord(p, [(16, 6), (28, 24), (40, 34)], [(80, 6), (68, 24), (56, 34)],
          beads=((26, 20, teal), (70, 20, teal), (34, 29, hexc("#e7b440")), (62, 29, hexc("#e7b440"))))
    tooth = [(36, 42), (60, 42), (62, 54), (58, 68), (50, 82), (40, 94), (42, 78), (38, 60)]
    p.shape("poly", tooth, hexc("#f2ead2"), depth=0.22, light=1.35, spec=1.0, tex="bone", tex_amt=0.7)
    p.stroke([(44, 46), (46, 64), (42, 84)], hexc("#c8b890"), 1.4)
    p.stroke([(56, 50), (54, 66)], hexc("#ffffff", 190), 1.6)
    p.shape("rect", (32, 32, 64, 46), GOLD, radius=4, depth=0.25, light=1.4, spec=1.0, tex="metal", tex_amt=0.4)
    for x in (38, 58):
        p.shape("poly", [(x - 3, 44), (x + 3, 44), (x, 52)], GOLD, line=0.9, spec=0.6, rim=0)
    p.shape("ellipse", (43, 34, 53, 44), teal, line=1.0, gloss=1.0, rim=0)
    p.sparkle((58, 60), 4.5)
    return p.finish(outline=2)


def drake_plate():
    """Ejder Zırhı (epic armour): bronze scale armour with a gold-trimmed collar and a red gem."""
    p = _P()
    bronze = hexc("#b8803a")
    p.glow((48, 50), 42, hexc("#ff9a2a"), 0.3)
    m = _torso(p, bronze, hexc("#7a4a24"), tex="metal")
    for row in range(8):
        for col in range(9):
            x = 24 + col * 6.4 + (3.2 if row % 2 else 0)
            y = 24 + row * 6.6
            p.shape("chord", (x - 4, y - 5, x + 4, y + 5), shade(bronze, 1.12), start=0, end=180, depth=0.35,
                    line=0.7, clip=m, rim=0, ao=0, light=1.45, spec=0.5)
    p.shape("poly", [(38, 14), (48, 26), (58, 14), (64, 18), (48, 34), (32, 18)], GOLD, line=1.2, spec=1.0, rim=0)
    for x in (22, 74):  # pauldrons
        p.shape("ellipse", (x - 12, 16, x + 12, 40), shade(bronze, 1.05), depth=0.25, spec=1.0, tex="metal",
                tex_amt=0.6)
        p.shape("rect", (x - 11, 30, x + 11, 34), GOLD, radius=1.5, line=0.8, spec=0.6, rim=0)
    p.shape("poly", [(48, 40), (55, 48), (48, 56), (41, 48)], hexc("#d8303a"), line=1.1, gloss=1.0, rim=0,
            light=1.5)
    p.sparkle((66, 48), 5)
    return p.finish(outline=2)


def ashwing_heart():
    """Kül Kanat'ın Kalbi (legendary): a glowing ember heart set in a jagged obsidian frame."""
    p = _P()
    _legendary_halo(p)
    obs = hexc("#2c2632")
    # chain loop
    ring = ImageChops.subtract(p._mask("ellipse", (41, 2, 55, 16)), p._mask("ellipse", (44.5, 5.5, 51.5, 12.5)))
    p.paint_mask(ring, GOLD, line=1.0, spec=0.8, rim=0)
    shards = [(48, 12), (58, 22), (72, 16), (70, 32), (84, 42), (72, 54), (76, 72), (60, 72), (48, 92), (36, 72),
              (20, 72), (24, 54), (12, 42), (26, 32), (24, 16), (38, 22)]
    p.shape("poly", shards, obs, depth=0.22, light=1.6, line=1.5, spec=1.0, rim=1.0, ink=hexc("#0a060c"))
    for a, b in (((48, 12), (48, 30)), ((12, 42), (30, 46)), ((84, 42), (66, 46)), ((48, 92), (48, 74))):
        p.stroke([a, b], hexc("#6a5a78"), 1.2)
    p.glow((48, 50), 26, hexc("#ff7a2a"), 1.0)
    heart = _heart_mask(p, 48, 50, 1.55)
    p.paint_mask(heart, hexc("#ff5a1e"), depth=0.25, light=1.6, line=1.3, gloss=0.8, rim=0, ink=hexc("#4a0a04"))
    for pts in ([(38, 42), (44, 48), (42, 56)], [(56, 40), (52, 50), (58, 56)], [(44, 48), (52, 50)],
                [(48, 60), (47, 66)]):
        p.stroke(pts, hexc("#8a1a08"), 1.6)
        p.stroke(pts, hexc("#fff0a0"), 0.6)
    p.glow((46, 46), 10, hexc("#fff0a0"), 0.6)
    for x, y, r in ((16, 24, 1.8), (82, 26, 2.0), (86, 80, 1.6), (12, 84, 1.8), (66, 88, 1.4)):
        p.glow((x, y), r * 3.5, hexc("#ffa040"), 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffe080"))
    p.sparkle((62, 30), 5, hexc("#fff0d0"))
    return p.finish(outline=2)


def dragon_egg():
    """Ejder Yumurtası (legendary): a speckled gold-and-teal egg with a faint glow and a crack."""
    p = _P()
    _legendary_halo(p, strength=0.4)
    _draw_egg(p, 48, 50, 1.0)
    p.sparkle((34, 26), 5.5, hexc("#fff0d0"))
    p.sparkle((70, 66), 3.5, hexc("#e8fff8"))
    return p.finish(outline=2)


def _draw_egg(p, cx, cy, s, glow=True):
    """The dragon egg itself, centred on (cx, cy); s=1 is 44 x 64."""
    gold = hexc("#e8b44a")
    teal = hexc("#2aa89a")
    if glow:
        p.glow((cx, cy), 40 * s, hexc("#6affe0"), 0.4)
    egg = p.union([("ellipse", (cx - 22 * s, cy - 24 * s, cx + 22 * s, cy + 32 * s)),
                   ("ellipse", (cx - 17 * s, cy - 34 * s, cx + 17 * s, cy + 8 * s))])
    p.paint_mask(egg, gold, depth=0.2, light=1.4, spec=1.0, tex="leather", tex_amt=0.5)
    # teal scale-like patches and speckles
    # a teal band of scales round the bottom, then scattered teal flecks above it
    band = ImageChops.multiply(egg, p._mask("ellipse", (cx - 40 * s, cy + 8 * s, cx + 40 * s, cy + 60 * s)))
    p.paint_mask(band, teal, depth=0.25, light=1.35, line=0.9, rim=0, ao=0, ink=hexc("#0e3a36"))
    for row, y in enumerate((12, 18, 24)):
        for i in range(-3, 4):
            x = i * 7 + (3.5 if row % 2 else 0)
            p.shape("chord", (cx + (x - 4) * s, cy + (y - 3) * s, cx + (x + 4) * s, cy + (y + 5) * s),
                    shade(teal, 1.2), start=0, end=180, depth=0.35, line=0.6, light=1.4, rim=0, ao=0, clip=band,
                    ink=hexc("#0e3a36"))
    for x, y, rx, ry in ((-9, -14, 2.6, 2.0), (11, -2, 3, 2.4), (-13, 2, 2.4, 2.6), (8, -22, 2, 1.6),
                         (-2, -4, 2, 1.6), (14, -12, 1.8, 2), (-4, -24, 1.8, 1.5)):
        p.shape("ellipse", (cx + (x - rx) * s, cy + (y - ry) * s, cx + (x + rx) * s, cy + (y + ry) * s), teal,
                depth=0.3, light=1.35, line=0.8, rim=0, ao=0, clip=egg, ink=hexc("#0e3a36"))
    for x, y, r in ((-14, -8, 1.1), (4, -12, 1.0), (14, 4, 1.0), (-6, 2, 0.9), (16, -18, 0.9),
                    (-10, -20, 1.0), (6, 2, 0.9), (-16, 6, 0.8)):
        p.flat("ellipse", (cx + (x - r) * s, cy + (y - r) * s, cx + (x + r) * s, cy + (y + r) * s), hexc("#7a4a1a"))
    # the crack, with light leaking from inside
    crack = [(cx - 2 * s, cy - 33 * s), (cx + 3 * s, cy - 26 * s), (cx - 2 * s, cy - 20 * s), (cx + 6 * s, cy - 14 * s),
             (cx + 3 * s, cy - 8 * s)]
    p.glow((cx + 2 * s, cy - 20 * s), 12 * s, hexc("#fff0a0"), 0.8)
    p.stroke(crack, hexc("#3a1a0a"), 2.0 * s)
    p.stroke(crack, hexc("#fff4c0"), 0.8 * s)
    p.stroke([(cx + 3 * s, cy - 26 * s), (cx + 9 * s, cy - 27 * s)], hexc("#3a1a0a"), 1.4 * s)
    p.stroke([(cx - 12 * s, cy - 16 * s), (cx - 16 * s, cy - 4 * s)], hexc("#ffffff", 170), 2.2 * s)
    return egg


GEAR = {
    "rusty_sword": rusty_sword, "iron_sword": iron_sword, "bone_cleaver": bone_cleaver,
    "leather_armor": leather_armor, "chain_mail": chain_mail,
    "leather_cap": leather_cap, "iron_helm": iron_helm,
    "copper_ring": copper_ring, "bone_amulet": bone_amulet, "bone_crown": bone_crown,
    "rat_fang": rat_fang, "spore_cloak": spore_cloak, "mimic_ring": mimic_ring,
    "warden_axe": warden_axe, "kingslayer": kingslayer,
    # mage staffs
    "apprentice_staff": apprentice_staff, "oak_staff": oak_staff, "bone_wand": bone_wand,
    "ember_rod": ember_rod, "grave_scepter": grave_scepter,
    # rogue daggers
    "rusty_dagger": rusty_dagger, "steel_dagger": steel_dagger, "bone_shiv": bone_shiv,
    "wardens_key": wardens_key, "nightfang": nightfang,
    # dungeon uniques
    "sporeheart_amulet": sporeheart_amulet, "shroom_cap": shroom_cap, "mother_mantle": mother_mantle,
    "frost_ring": frost_ring, "yeti_hide": yeti_hide, "frostbreath_scale": frostbreath_scale,
    "imp_horn": imp_horn, "flame_knight_helm": flame_knight_helm, "priestess_censer": priestess_censer,
    "whelp_tooth": whelp_tooth, "drake_plate": drake_plate, "ashwing_heart": ashwing_heart,
    "dragon_egg": dragon_egg,
}

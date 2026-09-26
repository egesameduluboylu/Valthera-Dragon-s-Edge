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


GEAR = {
    "rusty_sword": rusty_sword, "iron_sword": iron_sword, "bone_cleaver": bone_cleaver,
    "leather_armor": leather_armor, "chain_mail": chain_mail,
    "leather_cap": leather_cap, "iron_helm": iron_helm,
    "copper_ring": copper_ring, "bone_amulet": bone_amulet, "bone_crown": bone_crown,
    "rat_fang": rat_fang, "spore_cloak": spore_cloak, "mimic_ring": mimic_ring,
    "warden_axe": warden_axe, "kingslayer": kingslayer,
}

"""Skill, intent, status, room and item icons (soft Painter look, lit from the top left)."""
import math

from PIL import ImageChops

from painter import Painter, hexc, mix, shade

STEEL = hexc("#c9d4de")
GOLD = hexc("#e7b440")
RED = hexc("#d6453a")
DARK = hexc("#221820")
WHITE = hexc("#ffffff")
WOOD = hexc("#9a6433")
BONE_C = hexc("#ece3c8")
NOLINE = dict(shadow=0, light=0, line=0)


def _P(w, h=None):
    return Painter(w, h or w, soft=True)


def _frame(p, color):
    """Round medallion behind skill and room icons: bronze bezel, domed coloured face."""
    p.shape("ellipse", (3, 3, 93, 93), hexc("#8a6a3a"), depth=0.1, light=1.35, line=2.4, spec=0.7, tex="metal",
            tex_amt=0.5, ao=0)
    p.shape("ellipse", (8, 8, 88, 88), shade(color, 0.45), depth=0.1, line=1.2, rim=0, ao=0)
    face = p.shape("ellipse", (11, 11, 85, 85), color, depth=0.2, light=1.3, line=1.0, tex="stone", tex_amt=0.35,
                   rim=0.35, ao=0)
    # inner shadow under the bezel's top edge
    p.shadow_on(ImageChops.subtract(p._mask("ellipse", (4, 4, 92, 92)), p._mask("ellipse", (12, 16, 84, 90))),
                0.35, 1.0, 2.0)
    for a in (45, 135, 225, 315):  # bezel rivets
        x, y = 48 + 42.5 * math.cos(math.radians(a)), 48 + 42.5 * math.sin(math.radians(a))
        p.shape("ellipse", (x - 2.2, y - 2.2, x + 2.2, y + 2.2), hexc("#f0d890"), line=0.6, depth=0.4, light=1.6,
                rim=0, ao=0)
    return face


def _sword(p, x0, y0, x1, y1, width=8):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy * width / 2, ux * width / 2
    tip = (x1 + ux * 10, y1 + uy * 10)
    m = p.shape("poly", [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), tip, (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)],
                STEEL, depth=0.35, light=1.35, line=1.4, spec=1.0)
    p.stroke([(x0 + ux * 3, y0 + uy * 3), (x1 - ux * 2, y1 - uy * 2)], shade(STEEL, 0.72), max(1.0, width * 0.18))
    p.stroke([(x0 - nx * 0.6, y0 - ny * 0.6), (x1 - nx * 0.5, y1 - ny * 0.5), tip], hexc("#ffffff", 170),
             max(0.8, width * 0.12))
    gx, gy = x0, y0
    p.shape("line", [(gx - nx * 2.3, gy - ny * 2.3), (gx + nx * 2.3, gy + ny * 2.3)], GOLD, width=max(4, width * 0.7),
            line=1.2, spec=0.8, rim=0)
    p.shape("line", [(gx, gy), (gx - ux * 14, gy - uy * 14)], hexc("#6b4428"), width=max(4, width * 0.65), line=1.2,
            tex="leather", rim=0)
    ex, ey = gx - ux * 17, gy - uy * 17
    r = max(2.5, width * 0.45)
    p.shape("ellipse", (ex - r, ey - r, ex + r, ey + r), GOLD, line=1.1, gloss=0.8, rim=0)
    return m


def _shield(p, box, color, crack=False):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    pts = [(x0, y0), (x1, y0), (x1, (y0 + y1) / 2), (cx, y1), (x0, (y0 + y1) / 2)]
    p.shape("poly", pts, color, depth=0.15, line=1.6, spec=0.9, tex="metal", tex_amt=0.5)
    w = x1 - x0
    inset = max(2.5, w * 0.1)
    inner = [(x0 + inset, y0 + inset), (x1 - inset, y0 + inset), (x1 - inset, (y0 + y1) / 2 - 1), (cx, y1 - inset * 1.6),
             (x0 + inset, (y0 + y1) / 2 - 1)]
    p.shape("poly", inner, shade(color, 0.86), depth=0.2, line=0.9, rim=0, ao=0)
    r = max(4, w * 0.16)
    by = y0 + (y1 - y0) * 0.38
    p.shape("ellipse", (cx - r, by - r, cx + r, by + r), GOLD, line=1.2, gloss=0.9, rim=0)
    if crack:
        p.shape("line", [(cx + 4, y0 - 2), (cx - 6, y0 + 16), (cx + 8, y0 + 30), (cx - 2, y1 + 2)],
                DARK, width=4, **NOLINE)
        p.stroke([(cx + 5, y0 - 1), (cx - 5, y0 + 16), (cx + 9, y0 + 30)], hexc("#ffffff", 120), 1.0)


def _skull(p, cx, cy, s=1.0):
    p.shape("ellipse", (cx - 18 * s, cy - 18 * s, cx + 18 * s, cy + 14 * s), BONE_C, line=1.4, tex="bone", tex_amt=0.6)
    p.shape("rect", (cx - 10 * s, cy + 6 * s, cx + 10 * s, cy + 20 * s), BONE_C, radius=4 * s, line=1.4, tex="bone")
    p.flat("ellipse", (cx - 12 * s, cy - 6 * s, cx - 2 * s, cy + 4 * s), DARK)
    p.flat("ellipse", (cx + 2 * s, cy - 6 * s, cx + 12 * s, cy + 4 * s), DARK)
    p.flat("poly", [(cx - 2 * s, cy + 6 * s), (cx + 2 * s, cy + 6 * s), (cx, cy + 10 * s)], DARK)
    if s >= 0.8:
        for dx in (-4.5, 0, 4.5):
            p.stroke([(cx + dx * s, cy + 14 * s), (cx + dx * s, cy + 19 * s)], shade(BONE_C, 0.5), max(0.8, s * 0.9))


def _glow_eyes(p, cx, cy, s, color):
    for dx in (-7, 7):
        x, y = cx + dx * s, cy - 1 * s
        p.glow((x, y), 8 * s, color, 1.0)
        p.flat("ellipse", (x - 2 * s, y - 2 * s, x + 2 * s, y + 2 * s), mix(color, WHITE, 0.6))


def _star(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _drop(p, cx, cy, color, s=1.0):
    m = p.union([("poly", [(cx, cy - 20 * s), (cx - 13 * s, cy + 2 * s), (cx + 13 * s, cy + 2 * s)]),
                 ("ellipse", (cx - 14 * s, cy - 8 * s, cx + 14 * s, cy + 18 * s))])
    p.paint_mask(m, color, line=1.4, depth=0.18, light=1.35, gloss=1.0)


def _flame(p, cx, cy, s=1.0):
    outer = [(cx, cy - 26 * s), (cx + 7 * s, cy - 12 * s), (cx + 14 * s, cy - 16 * s), (cx + 17 * s, cy + 2 * s),
             (cx + 11 * s, cy + 18 * s), (cx - 11 * s, cy + 18 * s), (cx - 17 * s, cy + 2 * s), (cx - 12 * s, cy - 12 * s),
             (cx - 6 * s, cy - 6 * s)]
    p.shape("poly", outer, hexc("#ff6a1e"), line=1.4, shadow=0.8, light=1.3, depth=0.2, rim=0, ink=hexc("#6a1a08"))
    p.shape("poly", [(cx, cy - 12 * s), (cx + 9 * s, cy + 4 * s), (cx + 6 * s, cy + 16 * s), (cx - 6 * s, cy + 16 * s),
                     (cx - 9 * s, cy + 4 * s)], hexc("#ffb838"), **NOLINE)
    p.shape("poly", [(cx, cy - 2 * s), (cx + 5 * s, cy + 8 * s), (cx, cy + 15 * s), (cx - 5 * s, cy + 8 * s)],
            hexc("#fff4b0"), **NOLINE)


# ------------------------------------------------------------------ skills (96px)

def skill_icon(kind):
    p = _P(96)
    if kind == "slash":
        _frame(p, hexc("#3f5f9e"))
        p.shape("line", [(22, 44), (38, 26), (62, 18)], hexc("#bfe0ff", 220), width=6, **NOLINE)
        p.stroke([(24, 42), (40, 26), (60, 20)], WHITE, 2)
        _sword(p, 30, 66, 64, 32)
    elif kind == "shield_break":
        _frame(p, hexc("#6b5b8e"))
        _shield(p, (26, 22, 70, 76), hexc("#8fa0b3"), crack=True)
        for x, y in ((20, 70), (74, 30), (78, 62)):
            p.shape("poly", [(x, y - 4), (x + 5, y), (x, y + 5), (x - 4, y)], hexc("#8fa0b3"), line=1.0, rim=0)
    elif kind == "heavy_strike":
        _frame(p, hexc("#9e4a3a"))
        p.glow((58, 60), 22, hexc("#ffd060"), 0.7)
        p.shape("poly", _star(58, 60, 20, 9, 8), GOLD, line=1.2, light=1.4, spec=0.6)
        _sword(p, 24, 28, 54, 56, width=12)
    elif kind == "execute":
        _frame(p, hexc("#5a2a3a"))
        _skull(p, 48, 46, 1.1)
        _glow_eyes(p, 48, 46, 1.1, hexc("#ff4040"))
        p.shape("line", [(22, 74), (74, 22)], RED, width=6, depth=0.3, line=1.2, rim=0)
    elif kind == "battle_cry":
        _frame(p, hexc("#a8702a"))
        p.shape("poly", [(22, 40), (46, 28), (52, 48), (46, 68), (22, 56)], hexc("#d9b36b"), line=1.4, spec=0.6,
                tex="metal")  # war horn
        p.shape("ellipse", (18, 38, 28, 58), hexc("#8a6a3a"), line=1.2, rim=0)
        for r in (10, 18, 26):
            p.shape("line", [(58, 48 - r), (58 + r * 0.7, 48), (58, 48 + r)], WHITE, width=4, line=1.0, rim=0,
                    ink=hexc("#6a4a1a"))
    elif kind == "rending_cut":
        _frame(p, hexc("#7a2a2a"))
        for i in range(3):
            p.shape("line", [(26 + i * 12, 24), (46 + i * 12, 70)], STEEL, width=5, line=1.1, spec=0.8, rim=0)
        _drop(p, 70, 62, RED, 0.6)
    elif kind == "iron_wall":
        _frame(p, hexc("#4a5a6a"))
        p.shape("rect", (26, 20, 70, 76), hexc("#8fa0b3"), radius=6, line=1.6, spec=1.0, tex="metal")
        p.shape("rect", (32, 26, 64, 70), hexc("#7a8a9c"), radius=4, line=0.9, rim=0, ao=0)
        p.shape("line", [(48, 24), (48, 72)], hexc("#5d6b7a"), width=4, **NOLINE)
        for x, y in ((31, 25), (65, 25), (31, 71), (65, 71)):
            p.shape("ellipse", (x - 2.4, y - 2.4, x + 2.4, y + 2.4), hexc("#dfe6ee"), line=0.6, rim=0, ao=0)
    elif kind == "whirlwind":
        _frame(p, hexc("#3a7a6a"))
        for i, r in enumerate((12, 22, 32)):
            pts = [(48 + r * math.cos(math.radians(a)), 50 + r * 0.8 * math.sin(math.radians(a)))
                   for a in range(160 + i * 30, 380 + i * 30, 15)]
            p.shape("line", pts, hexc("#e8fff8"), width=4.2, line=1.0, ink=hexc("#1f4a40"), rim=0)
    return p.finish(outline=1)


# ------------------------------------------------------------------ intents & statuses (48px)

def _arrow(p, color):
    p.shape("poly", [(24, 3), (43, 24), (31, 24), (31, 45), (17, 45), (17, 24), (5, 24)], color, line=1.4,
            light=1.35, gloss=0.6)


def small_icon(kind):
    p = _P(48)
    if kind == "attack":
        _sword(p, 16, 32, 36, 12, width=7)
    elif kind == "shield":
        _shield(p, (9, 5, 39, 43), hexc("#8fa0b3"))
    elif kind == "buff":
        _arrow(p, hexc("#5ad16a"))
    elif kind in ("debuff", "execute"):
        _skull(p, 24, 22, 0.9)
    elif kind in ("stunned", "stun"):
        p.shape("poly", _star(16, 18, 11, 4.5), GOLD, line=1.2, light=1.45, spec=0.6)
        p.shape("poly", _star(32, 31, 11, 4.5), GOLD, line=1.2, light=1.45, spec=0.6)
    elif kind == "bleed":
        _drop(p, 24, 24, RED, 0.8)
    elif kind == "burn":
        _flame(p, 24, 25, 0.85)
    elif kind == "poison":
        _drop(p, 24, 24, hexc("#6fd13a"), 0.8)
        p.flat("ellipse", (30, 8, 36, 14), hexc("#a8ff7a"))
    elif kind == "freeze":
        for a, b in (((24, 4), (24, 44)), ((7, 14), (41, 34)), ((7, 34), (41, 14))):
            p.shape("line", [a, b], hexc("#9fe3ff"), width=5, line=1.2, spec=0.6, rim=0)
        p.shape("poly", [(24, 17), (31, 24), (24, 31), (17, 24)], WHITE, line=1.0, rim=0)
    elif kind == "armor_break":
        _shield(p, (9, 5, 39, 43), hexc("#8fa0b3"), crack=True)
    elif kind == "strengthened":
        _arrow(p, hexc("#ff9a3a"))
    elif kind == "target":
        p.shape("poly", [(5, 9), (43, 9), (24, 41)], hexc("#ffd24a"), line=1.6, depth=0.25, light=1.4, gloss=0.7)
    elif kind == "shield_status":
        _shield(p, (9, 5, 39, 43), hexc("#7fb2ff"))
    else:
        return item_icon(kind)
    return p.finish(outline=1)


# ------------------------------------------------------------------ rooms (96px) and items (48px)

def _chest(p, x0, y0, x1, y1):
    wood = hexc("#a0652f")
    mid = y0 + (y1 - y0) * 0.42
    p.shape("rect", (x0, mid, x1, y1), wood, radius=4, depth=0.12, tex="wood_h")
    p.shape("chord", (x0, y0, x1, 2 * mid - y0), wood, start=180, end=360, depth=0.12, tex="wood_h")
    w = x1 - x0
    p.stroke([(x0 + 3, mid + (y1 - mid) * 0.5), (x1 - 3, mid + (y1 - mid) * 0.5)], shade(wood, 0.55),
             max(1.0, w * 0.012))
    p.shape("rect", (x0 - 1, mid - 3, x1 + 1, mid + 3), hexc("#6a6e78"), radius=1, line=1.0, spec=0.5, rim=0)
    for fx in (0.16, 0.84):
        x = x0 + w * fx
        bw = max(3, w * 0.035)
        p.shape("rect", (x - bw, y0 - 2, x + bw, y1), GOLD, radius=1, line=1, spec=0.8, rim=0)
    cx = (x0 + x1) / 2
    lw = max(6, w * 0.08)
    p.shape("rect", (cx - lw, mid - lw * 0.8, cx + lw, mid + lw * 1.5), GOLD, radius=2, line=1, spec=1.0, rim=0)
    p.flat("ellipse", (cx - lw * 0.3, mid - lw * 0.1, cx + lw * 0.3, mid + lw * 0.5), DARK)
    p.flat("rect", (cx - lw * 0.12, mid + lw * 0.3, cx + lw * 0.12, mid + lw * 1.0), DARK)


def _campfire(p, cx, cy, s=1.0):
    for a, b in (((cx - 26 * s, cy + 16 * s), (cx + 22 * s, cy + 4 * s)), ((cx - 22 * s, cy + 4 * s), (cx + 26 * s, cy + 16 * s))):
        p.shape("line", [a, b], hexc("#7a4a2a"), width=9 * s, line=1.2, tex="wood_h")
        for e in (a, b):
            r = 4.5 * s
            p.shape("ellipse", (e[0] - r, e[1] - r, e[0] + r, e[1] + r), hexc("#c89060"), line=1.0, rim=0)
    p.glow((cx, cy - 6 * s), 36 * s, hexc("#ffb040"), 0.8)
    _flame(p, cx, cy - 10 * s, 1.05 * s)


def _crown(p, cx, cy, s=1.0):
    pts = [(cx - 30 * s, cy + 14 * s), (cx - 30 * s, cy - 18 * s), (cx - 15 * s, cy - 2 * s), (cx, cy - 24 * s),
           (cx + 15 * s, cy - 2 * s), (cx + 30 * s, cy - 18 * s), (cx + 30 * s, cy + 14 * s)]
    p.shape("poly", pts, hexc("#f1c24a"), depth=0.2, light=1.4, spec=1.0, tex="metal", tex_amt=0.4)
    for x, y in ((cx - 30 * s, cy - 18 * s), (cx, cy - 24 * s), (cx + 30 * s, cy - 18 * s)):
        r = 3.5 * s
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#f1c24a"), line=1.0, gloss=0.8, rim=0)
    p.shape("rect", (cx - 31 * s, cy + 6 * s, cx + 31 * s, cy + 16 * s), hexc("#d49a2a"), radius=2, line=1.2, spec=0.6)
    p.shape("ellipse", (cx - 5 * s, cy + 7 * s, cx + 5 * s, cy + 15 * s), RED, light=1.6, line=1, gloss=1.0, rim=0)
    for dx in (-18, 18):
        p.shape("ellipse", (cx + (dx - 3) * s, cy + 8 * s, cx + (dx + 3) * s, cy + 14 * s), hexc("#3ad0ff"), line=0.8,
                gloss=1.0, rim=0)


def _potion(p, cx, cy, s=1.0, color=None):
    color = color or hexc("#e0303a")
    p.shape("rect", (cx - 5 * s, cy - 20 * s, cx + 5 * s, cy - 8 * s), hexc("#cfe3ea"), radius=2, line=1.2, rim=0)
    p.shape("rect", (cx - 7 * s, cy - 25 * s, cx + 7 * s, cy - 18 * s), hexc("#8a5a34"), radius=2, line=1.2,
            tex="wood", rim=0)
    glass = p.shape("ellipse", (cx - 16 * s, cy - 12 * s, cx + 16 * s, cy + 20 * s), hexc("#dfeef4"), light=1.2,
                    depth=0.15, line=1.3, rim=0)
    liquid = ImageChops.multiply(glass, p._mask("rect", (cx - 20 * s, cy - 3 * s, cx + 20 * s, cy + 24 * s)))
    p.paint_mask(liquid, color, light=1.4, depth=0.25, line=0, rim=0.4, ao=0)
    p.stroke([(cx - 14 * s, cy - 3 * s), (cx + 14 * s, cy - 3 * s)], shade(color, 1.35), max(0.8, 1.4 * s))
    p.flat("ellipse", (cx - 10 * s, cy - 8 * s, cx - 4 * s, cy + 4 * s), hexc("#ffffff", 210))
    p.flat("ellipse", (cx + 5 * s, cy + 10 * s, cx + 9 * s, cy + 14 * s), hexc("#ffffff", 120))


def room_icon(kind):
    p = _P(96)
    colors = {"combat": "#8a3a2e", "elite": "#6a2a7a", "treasure": "#a8702a", "event": "#2e5a8a",
              "rest": "#2e7a4a", "boss": "#4a1a24"}
    _frame(p, hexc(colors[kind]))
    if kind == "combat":
        _sword(p, 26, 70, 62, 30)
        _sword(p, 70, 70, 34, 30)
    elif kind == "elite":
        p.shape("poly", [(28, 42), (12, 14), (40, 30)], BONE_C, line=1.2, tex="bone")
        p.shape("poly", [(68, 42), (84, 14), (56, 30)], BONE_C, line=1.2, tex="bone")
        _skull(p, 48, 50, 1.05)
        _glow_eyes(p, 48, 50, 1.05, hexc("#ffcc33"))
    elif kind == "treasure":
        p.glow((48, 52), 30, hexc("#ffd060"), 0.5)
        _chest(p, 22, 34, 74, 72)
        p.sparkle((66, 34), 5)
    elif kind == "event":
        p.shape("rect", (28, 20, 68, 76), hexc("#f1e2c0"), radius=6, line=1.4, tex="cloth", tex_amt=0.5)
        p.shape("rect", (24, 16, 72, 24), hexc("#d8c49a"), radius=4, line=1.2, rim=0)
        p.shape("rect", (24, 72, 72, 80), hexc("#d8c49a"), radius=4, line=1.2, rim=0)
        p.shape("line", [(40, 38), (44, 30), (54, 30), (57, 38), (48, 46), (48, 54)], hexc("#2e5a8a"), width=6,
                **NOLINE)
        p.flat("ellipse", (44, 59, 52, 67), hexc("#2e5a8a"))
    elif kind == "rest":
        _campfire(p, 48, 54)
    elif kind == "boss":
        p.glow((48, 56), 30, hexc("#ff3040"), 0.5)
        _crown(p, 48, 42, 0.9)
        _skull(p, 48, 64, 0.62)
    return p.finish(outline=1)


def item_icon(kind):
    p = _P(48)
    if kind == "potion":
        _potion(p, 24, 26, 0.95)
    elif kind == "gold":
        p.shape("ellipse", (5, 14, 33, 42), hexc("#d49a2a"), line=1.4, spec=0.6)
        p.shape("ellipse", (14, 6, 42, 34), hexc("#f1c24a"), light=1.4, line=1.4, spec=1.0)
        p.shape("ellipse", (20, 12, 36, 28), hexc("#d49a2a"), shadow=0, light=0, line=1)
        p.shape("poly", [(28, 14), (32, 20), (28, 26), (24, 20)], hexc("#fff0b0"), line=0.8, rim=0)
    elif kind == "heart":
        m = p.union([("ellipse", (5, 7, 26, 29)), ("ellipse", (22, 7, 43, 29)), ("poly", [(6, 22), (42, 22), (24, 43)])])
        p.paint_mask(m, hexc("#e0303a"), line=1.4, light=1.35, depth=0.2, gloss=1.0)
    elif kind == "xp":
        p.glow((24, 25), 22, hexc("#7fd4ff"), 0.5)
        p.shape("poly", _star(24, 25, 21, 9), hexc("#7fd4ff"), light=1.45, line=1.4, spec=0.8)
    elif kind == "summon":
        _skull(p, 20, 24, 0.75)
        p.shape("rect", (32, 12, 38, 34), hexc("#5ad16a"), radius=2, line=1.2, rim=0)
        p.shape("rect", (24, 20, 46, 26), hexc("#5ad16a"), radius=2, line=1.2, rim=0)
    elif kind == "enraged":
        _flame(p, 24, 25, 0.85)
        p.shape("line", [(14, 22), (22, 26)], DARK, width=3, **NOLINE)
        p.shape("line", [(34, 22), (26, 26)], DARK, width=3, **NOLINE)
    elif kind == "scale":
        pts = [(24, 4), (40, 14), (40, 28), (24, 44), (8, 28), (8, 14)]
        p.shape("poly", pts, hexc("#4fb8e8"), depth=0.22, light=1.45, line=1.4, spec=1.0)
        p.shape("line", [(24, 10), (24, 36)], hexc("#2a7aa8"), width=2.5, **NOLINE)
        p.shape("line", [(14, 18), (24, 26), (34, 18)], hexc("#2a7aa8"), width=2, **NOLINE)
        p.flat("ellipse", (13, 11, 19, 17), hexc("#ffffff", 200))
    elif kind == "bag":
        leather = hexc("#a0652f")
        p.shape("ellipse", (6, 16, 42, 46), leather, depth=0.16, tex="leather")
        p.shape("poly", [(20, 19), (28, 19), (35, 5), (13, 5)], shade(leather, 0.9), line=1.2, tex="leather")
        for x in (15, 21, 27, 33):
            p.shape("ellipse", (x - 3, 3, x + 3, 9), shade(leather, 0.9), line=1, rim=0)
        p.shape("line", [(18, 19), (30, 19)], hexc("#e7b440"), width=3, line=0.8, rim=0)
        p.shape("line", [(30, 19), (36, 26)], hexc("#e7b440"), width=2, line=0.6, rim=0)
        p.shape("ellipse", (19, 27, 29, 37), GOLD, light=1.4, line=1, spec=1.0, rim=0)
    elif kind == "flee":
        p.shape("poly", [(40, 24), (22, 8), (22, 18), (8, 18), (8, 30), (22, 30), (22, 40)], hexc("#e7e0d0"), line=1.4,
                light=1.3)
        for y in (20, 28):
            p.stroke([(2, y), (6, y)], hexc("#e7e0d0"), 2)
    return p.finish(outline=1)


ROOM_ICONS = ["combat", "elite", "treasure", "event", "rest", "boss"]
ITEM_ICONS = ["potion", "gold", "heart", "xp", "flee", "scale", "bag"]

SKILL_ICONS = ["slash", "shield_break", "heavy_strike", "execute", "battle_cry", "rending_cut", "iron_wall", "whirlwind"]
INTENT_ICONS = ["attack", "shield", "buff", "debuff", "stunned", "summon"]
STATUS_ICONS = ["bleed", "burn", "poison", "freeze", "stun", "armor_break", "strengthened", "shield_status",
                "enraged"]

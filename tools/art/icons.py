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
    elif kind in CLASS_SKILLS:
        face_color, draw = CLASS_SKILLS[kind]
        face = _frame(p, hexc(face_color))
        draw(p, face)
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
    elif kind == "evasive":
        _status_evasive(p)
    elif kind == "chill":
        _status_chill(p)
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

SKILL_ICONS = ["slash", "shield_break", "heavy_strike", "execute", "battle_cry", "rending_cut", "iron_wall", "whirlwind",
               # mage
               "arcane_bolt", "fireball", "flame_burst", "ice_lance", "mana_shield", "shatter", "chain_lightning", "meteor",
               # rogue
               "stab", "poison_blade", "backstab", "smoke_bomb", "blind", "poison_burst", "blade_rain", "shadow_step"]
INTENT_ICONS = ["attack", "shield", "buff", "debuff", "stunned", "summon"]
STATUS_ICONS = ["bleed", "burn", "poison", "freeze", "stun", "armor_break", "strengthened", "shield_status",
                "enraged", "evasive", "chill"]


# ------------------------------------------------------------------ mage and rogue skills (96px)

def _unit(x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _trail(hx, hy, tx, ty, r, jag=0.0, n=7, taper=1.0):
    """Tapered comet/flame tail: a round head at (hx, hy) narrowing to a point at (tx, ty)."""
    ux, uy = _unit(tx, ty, hx, hy)          # points toward the head
    px, py = -uy, ux
    length = math.hypot(hx - tx, hy - ty)
    left, right = [], []
    for i in range(n + 1):
        t = i / n                             # 0 at head, 1 at tail
        w = r * (1 - t) ** taper
        k = 1 + (jag * (1 if i % 2 else -0.6) if 0 < i < n else 0)
        cx, cy = hx - ux * length * t, hy - uy * length * t
        left.append((cx + px * w * k, cy + py * w * k))
        right.append((cx - px * w * k * (0.85 if i % 2 else 1.1), cy - py * w * k * (0.85 if i % 2 else 1.1)))
    front = [(hx + r * math.cos(a), hy + r * math.sin(a))
             for a in [math.atan2(py, px) - math.pi * j / 8 for j in range(9)]]
    return front + right[1:] + left[-2:0:-1]


def _comet(p, hx, hy, tx, ty, r, layers, jag=0.0, ink=None):
    """Layered comet: `layers` is [(colour, radius factor, tail factor)] from the outside in."""
    for i, (col, rf, tf) in enumerate(layers):
        ex, ey = hx + (tx - hx) * tf, hy + (ty - hy) * tf
        pts = _trail(hx, hy, ex, ey, r * rf, jag=jag if i < 2 else jag * 0.5)
        if i == 0:
            p.shape("poly", pts, col, shadow=0.8, light=1.3, depth=0.22, line=1.3, rim=0, ink=ink or INK_FOR_FX)
        else:
            p.shape("poly", pts, col, **NOLINE)


INK_FOR_FX = hexc("#3a1030")


def _dagger(p, x0, y0, x1, y1, width=8, blade=None, grip=None, guard=None, grip_len=13, pommel=True, tex="metal"):
    """Dagger with its guard at (x0, y0) and the point at (x1, y1). Returns (ux, uy, nx, ny)."""
    blade = blade or STEEL
    grip = grip or hexc("#4a2e20")
    guard = guard or GOLD
    ux, uy = _unit(x0, y0, x1, y1)
    nx, ny = -uy * width / 2, ux * width / 2
    L = math.hypot(x1 - x0, y1 - y0)
    mx, my = x0 + ux * L * 0.62, y0 + uy * L * 0.62
    pts = [(x0 + nx, y0 + ny), (mx + nx * 0.95, my + ny * 0.95), (x1, y1), (mx - nx * 0.95, my - ny * 0.95),
           (x0 - nx, y0 - ny)]
    p.shape("poly", pts, blade, depth=0.35, light=1.35, line=1.3, spec=1.0, tex=tex, tex_amt=0.4)
    p.stroke([(x0 + ux * 3, y0 + uy * 3), (mx + ux * 4, my + uy * 4)], shade(blade, 0.7), max(1.0, width * 0.16))
    p.stroke([(x0 - nx * 0.55, y0 - ny * 0.55), (mx - nx * 0.5, my - ny * 0.5), (x1 - ux * 2, y1 - uy * 2)],
             hexc("#ffffff", 170), max(0.8, width * 0.12))
    p.shape("line", [(x0, y0), (x0 - ux * grip_len, y0 - uy * grip_len)], grip, width=max(3.5, width * 0.6),
            line=1.1, tex="leather", rim=0)
    for i in range(3):
        t = 3 + i * (grip_len - 4) / 3
        cx, cy = x0 - ux * t, y0 - uy * t
        p.stroke([(cx - nx * 0.5, cy - ny * 0.5), (cx + nx * 0.5 - ux * 1.5, cy + ny * 0.5 - uy * 1.5)],
                 shade(grip, 0.5), 1.0)
    p.shape("line", [(x0 - nx * 1.9, y0 - ny * 1.9), (x0 + nx * 1.9, y0 + ny * 1.9)], guard,
            width=max(3.5, width * 0.55), line=1.1, spec=0.8, rim=0)
    if pommel:
        ex, ey = x0 - ux * (grip_len + 2.5), y0 - uy * (grip_len + 2.5)
        r = max(2.4, width * 0.4)
        p.shape("ellipse", (ex - r, ey - r, ex + r, ey + r), guard, line=1.0, gloss=0.8, rim=0)
    return ux, uy, nx, ny


def _puff(p, cx, cy, r, color, seed=1, n=5, alpha_ghost=False):
    """Smoke puff: a union of overlapping balls with soft volume shading."""
    rnd = (seed * 9301 + 49297) % 233280
    items = [("ellipse", (cx - r, cy - r * 0.8, cx + r, cy + r * 0.8))]
    for i in range(n):
        rnd = (rnd * 9301 + 49297) % 233280
        a = 2 * math.pi * i / n + rnd / 233280.0
        rr = r * (0.55 + 0.25 * ((rnd >> 3) % 100) / 100)
        ox, oy = cx + math.cos(a) * r * 0.7, cy + math.sin(a) * r * 0.5
        items.append(("ellipse", (ox - rr, oy - rr, ox + rr, oy + rr)))
    m = p.union(items)
    p.paint_mask(m, color, depth=0.22, light=1.3, shadow=0.7, line=1.1, rim=0.4, ink=shade(color, 0.35))
    return m


def _jag(pts_center, amp, seed=3):
    rnd = seed
    out = []
    for i, (x, y) in enumerate(pts_center):
        rnd = (rnd * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((x + ((rnd % 100) / 100 - 0.5) * amp, y + (((rnd >> 8) % 100) / 100 - 0.5) * amp))
    return out


def _burst(cx, cy, r_out, r_in, n, seed=5):
    pts = []
    rnd = seed
    for i in range(n * 2):
        rnd = (rnd * 1103515245 + 12345) & 0x7FFFFFFF
        r = (r_out if i % 2 == 0 else r_in) * (0.8 + 0.35 * (rnd % 100) / 100)
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _bolt_line(p, pts, core=None, glow=None, width=5.0):
    glow = glow or hexc("#7fb8ff")
    core = core or hexc("#fff6a8")
    for x, y in pts[1:-1:1]:
        p.glow((x, y), width * 3.2, glow, 0.5)
    p.shape("line", pts, core, width=width, line=1.2, depth=0.3, light=1.3, rim=0, ink=hexc("#2a2a6a"))
    p.stroke(pts, hexc("#ffffff"), max(1.0, width * 0.35))


def _crystal(p, pts, color=None, facet=True, line=1.2):
    color = color or hexc("#bfe8ff")
    p.shape("poly", pts, color, depth=0.3, light=1.45, line=line, spec=1.0, rim=0.5, ink=hexc("#1e3a6a"))
    if facet and len(pts) >= 4:
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        light_half = [pts[0], pts[1], (cx, cy)]
        p.flat("poly", light_half, hexc("#ffffff", 90))
        p.stroke([pts[0], (cx, cy), pts[len(pts) // 2]], hexc("#ffffff", 150), 1.0)


# ---- mage

def _sk_arcane_bolt(p, face):
    p.glow((58, 38), 30, hexc("#b060ff"), 0.6)
    _comet(p, 60, 38, 16, 80, 15, [(hexc("#5a1fa0"), 1.0, 1.0), (hexc("#9a4ef0"), 0.72, 0.8),
                                    (hexc("#d8a8ff"), 0.46, 0.55), (hexc("#ffffff"), 0.24, 0.28)], jag=0.12,
           ink=hexc("#1e0838"))
    for x, y, r in ((30, 42, 4), (74, 64, 3.5), (40, 70, 3), (78, 24, 4.5)):
        p.sparkle((x, y), r, hexc("#f0d8ff"))
    p.flat("ellipse", (56, 32, 62, 38), hexc("#ffffff"))


def _sk_fireball(p, face):
    p.glow((56, 46), 32, hexc("#ffa030"), 0.7)
    _comet(p, 58, 46, 12, 64, 17, [(hexc("#e8401a"), 1.0, 1.0), (hexc("#ff8a24"), 0.78, 0.82),
                                    (hexc("#ffcc48"), 0.52, 0.55), (hexc("#fff6c8"), 0.28, 0.25)], jag=0.28,
           ink=hexc("#5a1206"))
    for x, y, r in ((24, 38, 2.2), (30, 72, 1.8), (18, 52, 1.6), (40, 30, 1.6)):
        p.glow((x, y), r * 3, hexc("#ffb040"), 0.8)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffe080"))


def _sk_flame_burst(p, face):
    p.glow((48, 50), 40, hexc("#ff8a24"), 0.8)
    p.shape("poly", _burst(48, 50, 36, 18, 11, seed=4), hexc("#e8401a"), shadow=0.8, light=1.3, depth=0.18,
            line=1.3, rim=0, ink=hexc("#5a1206"), clip=face)
    p.shape("poly", _burst(48, 50, 26, 13, 9, seed=9), hexc("#ff9a2a"), **NOLINE)
    p.shape("poly", _burst(48, 50, 17, 9, 7, seed=2), hexc("#ffd24a"), **NOLINE)
    p.glow((48, 50), 14, hexc("#fffbe0"), 0.95)
    p.flat("ellipse", (42, 44, 54, 56), hexc("#fffbe0"))
    for a in range(20, 360, 60):  # flying embers
        x, y = 48 + 32 * math.cos(math.radians(a)), 50 + 30 * math.sin(math.radians(a))
        _flame(p, x, y, 0.22)


def _sk_ice_lance(p, face):
    p.glow((56, 40), 34, hexc("#8fdcff"), 0.55)
    for x, y, r in ((22, 74, 8), (31, 80, 5), (15, 66, 5)):  # frost mist at the tail
        p.glow((x, y), r * 1.6, hexc("#e8f8ff"), 0.7)
    # the spear: long faceted crystal pointing to the upper right
    ux, uy = _unit(20, 76, 80, 16)
    px, py = -uy, ux
    L = math.hypot(60, 60)
    def at(t, w):
        return (20 + ux * L * t + px * w, 76 + uy * L * t + py * w)
    pts = [at(0, 0), at(0.12, 5), at(0.55, 8.5), at(1.0, 0), at(0.55, -8.5), at(0.12, -5)]
    p.shape("poly", pts, hexc("#a8e4ff"), depth=0.3, light=1.5, line=1.4, spec=1.0, rim=0.6, ink=hexc("#16305a"))
    p.flat("poly", [at(0, 0), at(0.12, 5), at(0.55, 8.5), at(1.0, 0)], hexc("#ffffff", 110))
    p.stroke([at(0.04, 0), at(0.97, 0)], hexc("#5aa8e0"), 1.2)
    p.stroke([at(0.2, 3), at(0.8, 3)], hexc("#ffffff", 200), 1.1)
    for t, side in ((0.3, 1), (0.42, -1), (0.66, 1)):  # frost spurs along the shaft
        x, y = at(t, 7 * side)
        tx, ty = at(t - 0.1, 13 * side)
        p.shape("poly", [(x - ux * 3, y - uy * 3), (tx, ty), (x + ux * 3, y + uy * 3)], hexc("#d8f4ff"),
                line=0.9, rim=0, ao=0, ink=hexc("#16305a"))
    p.sparkle((72, 26), 6)
    p.sparkle((30, 52), 3.5, hexc("#d8f4ff"))


def _sk_mana_shield(p, face):
    p.glow((48, 50), 38, hexc("#4aa8ff"), 0.6)
    bubble = p.shape("ellipse", (18, 20, 78, 80), hexc("#5ab8ff", 120), shadow=0.8, light=1.3, depth=0.25, line=1.4,
                     rim=0, ao=0, ink=hexc("#1a3a8a"))
    ring = ImageChops.subtract(p._mask("ellipse", (18, 20, 78, 80)), p._mask("ellipse", (22, 24, 74, 76)))
    p._fill(ring, hexc("#bfe6ff", 230), solid=False)
    # rune circle inside the bubble
    rr = ImageChops.subtract(p._mask("ellipse", (31, 33, 65, 67)), p._mask("ellipse", (34, 36, 62, 64)))
    p._fill(rr, hexc("#e0f4ff", 220), solid=False)
    for i in range(6):
        a = math.radians(i * 60 - 90)
        x, y = 48 + 17 * math.cos(a), 50 + 17 * math.sin(a)
        p.shape("poly", [(x, y - 3.5), (x + 3, y), (x, y + 3.5), (x - 3, y)], hexc("#ffffff"), line=0.7, rim=0, ao=0,
                ink=hexc("#1a3a8a"))
    p.shape("poly", _star(48, 50, 9, 4, 6), hexc("#ffffff"), light=1.2, line=0.9, rim=0, ao=0, ink=hexc("#1a3a8a"))
    p.glow((48, 50), 12, hexc("#bfe6ff"), 0.8)
    # glassy highlight arc
    arc = [(30 + 16 * math.cos(math.radians(a)) - 0, 40 + 16 * math.sin(math.radians(a))) for a in range(190, 262, 8)]
    p.stroke(arc, hexc("#ffffff", 230), 3.0)
    p.flat("ellipse", (58, 64, 64, 68), hexc("#ffffff", 150))
    p.sparkle((70, 26), 4.5)


def _sk_shatter(p, face):
    p.glow((48, 48), 34, hexc("#8fdcff"), 0.5)
    ice = hexc("#b8e6ff")
    ink = hexc("#16305a")
    # the crystal split in two by a jagged crack, halves drifting apart
    crack = [(44, 18), (50, 32), (42, 44), (52, 56), (46, 70), (50, 80)]
    lpts = [(44 - 5, 18 - 1), (28 - 5, 30 - 1), (28 - 5, 66 - 1), (50 - 5, 80 - 1)] + [(x - 5, y - 1) for x, y in crack[::-1][1:-1]]
    rpts = [(44 + 5, 18 + 1), (64 + 5, 28 + 1), (66 + 5, 64 + 1), (50 + 5, 80 + 1)] + [(x + 5, y + 1) for x, y in crack[::-1][1:-1]]
    p.shape("poly", lpts, ice, depth=0.3, light=1.5, line=1.4, spec=1.0, rim=0.5, ink=ink)
    p.shape("poly", rpts, shade(ice, 0.9), depth=0.3, light=1.4, line=1.4, spec=0.8, rim=0.5, ink=ink)
    p.flat("poly", [(39, 17), (23, 29), (23, 50), (34, 40)], hexc("#ffffff", 110))
    p.stroke([(38, 24), (26, 34)], hexc("#ffffff", 210), 1.2)
    p.stroke([(62, 36), (64, 58)], hexc("#ffffff", 150), 1.1)
    # the crack glows cold white in the gap
    p.stroke([(x, y) for x, y in crack], hexc("#e8fbff"), 2.2)
    p.glow((48, 48), 10, hexc("#ffffff"), 0.6)
    # flying shards
    for (x, y, s, a) in ((17, 24, 7, 20), (79, 22, 7.5, -30), (16, 74, 6, 60), (80, 72, 6.5, -60), (84, 47, 5, 0)):
        c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
        pts = [(x + (dx * c - dy * sn) * s / 5, y + (dx * sn + dy * c) * s / 5) for dx, dy in ((0, -6), (4, 0), (0, 6), (-3, 1))]
        p.shape("poly", pts, hexc("#d8f4ff"), line=1.0, depth=0.3, light=1.5, rim=0, ao=0, ink=ink)
        mx, my = (x - 48) * 0.18, (y - 48) * 0.18
        p.stroke([(x - mx * 1.6, y - my * 1.6), (x - mx * 3.0, y - my * 3.0)], hexc("#ffffff", 150), 1.2)


def _sk_chain_lightning(p, face):
    main = [(18, 20), (30, 30), (26, 36), (40, 44), (50, 48)]
    forks = [[(50, 48), (62, 40), (60, 34), (76, 28)],
             [(50, 48), (60, 56), (56, 62), (72, 72)],
             [(50, 48), (46, 60), (38, 64), (38, 80)]]
    for f in forks:
        _bolt_line(p, f, width=4.6)
    _bolt_line(p, main, width=6.4)
    p.glow((50, 48), 14, hexc("#ffffff"), 0.9)
    for x, y in ((76, 28), (72, 72), (38, 80)):
        p.glow((x, y), 9, hexc("#7fb8ff"), 0.9)
        p.shape("poly", _star(x, y, 6, 2.2, 4), hexc("#fff6a8"), line=0.8, light=1.3, rim=0, ao=0,
                ink=hexc("#2a2a6a"))


def _sk_meteor(p, face):
    p.glow((42, 58), 34, hexc("#ff7a2a"), 0.7)
    _comet(p, 40, 60, 86, 12, 19, [(hexc("#d83a18"), 1.0, 1.0), (hexc("#ff8a24"), 0.78, 0.8),
                                    (hexc("#ffcc48"), 0.5, 0.52)], jag=0.3, ink=hexc("#5a1206"))
    rock = p.union([("ellipse", (26, 46, 54, 74)), ("poly", [(24, 58), (32, 44), (46, 42), (56, 54), (52, 72), (34, 76)])])
    p.paint_mask(rock, hexc("#6a5048"), depth=0.25, light=1.3, line=1.4, tex="stone", tex_amt=0.9, ink=hexc("#2a1210"))
    for pts in ([(32, 52), (38, 58), (36, 66)], [(44, 50), (46, 60), (52, 64)], [(38, 58), (46, 60)]):
        p.stroke(pts, hexc("#ffb040"), 1.8)
        p.stroke(pts, hexc("#fff0a0"), 0.7)
    p.glow((40, 60), 8, hexc("#ffb040"), 0.4)
    for x, y in ((22, 80), (60, 80), (16, 64)):  # debris
        p.shape("ellipse", (x - 2.5, y - 2.5, x + 2.5, y + 2.5), hexc("#6a5048"), line=0.8, rim=0, ao=0)


# ---- rogue

def _sk_stab(p, face):
    for y, x0, x1 in ((40, 14, 34), (50, 12, 30), (60, 18, 36)):  # thrust speed lines
        p.stroke([(x0, y + 12), (x1, y)], hexc("#ffffff", 150), 2.0)
    p.glow((74, 26), 14, hexc("#fff0a0"), 0.8)
    p.shape("poly", _star(74, 26, 11, 4, 6), hexc("#fff4c0"), line=1.0, light=1.3, rim=0, ao=0, ink=hexc("#6a4a1a"))
    _dagger(p, 38, 60, 72, 28, width=10, grip_len=15)


def _sk_poison_blade(p, face):
    green = hexc("#6fd13a")
    p.glow((56, 40), 30, hexc("#8aff5a"), 0.4)
    ux, uy, nx, ny = _dagger(p, 30, 66, 74, 22, width=11, grip_len=14)
    # venom coating the blade and dripping off its lower edge
    coat = [(44 + nx * 0.9, 52 + ny * 0.9), (66 + nx * 0.9, 30 + ny * 0.9), (72, 24), (66 - nx * 0.3, 30 - ny * 0.3),
            (44 - nx * 0.3, 52 - ny * 0.3)]
    p.shape("poly", coat, green, depth=0.3, light=1.4, line=1.0, gloss=0.8, rim=0, ao=0, ink=hexc("#1a4a10"))
    for x, y, ln in ((50, 50, 8), (58, 42, 12), (66, 34, 6)):
        p.shape("line", [(x, y), (x + 1, y + ln)], green, width=3.2, line=0.9, rim=0, ao=0, ink=hexc("#1a4a10"))
        p.shape("ellipse", (x - 2.6 + 1, y + ln - 1, x + 2.6 + 1, y + ln + 4.2), green, line=0.9, gloss=0.8, rim=0,
                ao=0, ink=hexc("#1a4a10"))
    _drop(p, 62, 74, green, 0.34)
    _drop(p, 74, 62, green, 0.26)
    p.flat("ellipse", (46, 70, 50, 74), hexc("#a8ff7a"))


def _silhouette_back(p, cx, top, color, clip=None):
    """A figure seen from behind: hooded head and shoulders."""
    m = p.union([("ellipse", (cx - 11, top, cx + 11, top + 24)),
                 ("poly", [(cx - 7, top + 16), (cx + 7, top + 16), (cx + 9, top + 28), (cx - 9, top + 28)]),
                 ("ellipse", (cx - 30, top + 26, cx + 30, top + 80))])
    if clip is not None:
        m = ImageChops.multiply(m, clip)
    p.paint_mask(m, color, depth=0.14, light=1.25, line=1.3, rim=0.9, ink=hexc("#0e080e"))
    return m


def _sk_backstab(p, face):
    body = _silhouette_back(p, 42, 26, hexc("#2c2436"), clip=face)
    p.stroke([(42, 48), (42, 80)], hexc("#1a141e"), 1.4)
    p.glow((54, 60), 18, hexc("#ffd060"), 0.9)
    p.shape("poly", _star(54, 60, 13, 5, 8), hexc("#ffe070"), line=1.1, light=1.4, rim=0, ao=0, ink=hexc("#6a3a0a"))
    p.flat("ellipse", (51, 57, 57, 63), hexc("#ffffff"))
    _dagger(p, 70, 38, 56, 58, width=9, grip_len=13)
    for x, y in ((62, 70), (66, 64), (58, 74)):
        p.shape("ellipse", (x - 2, y - 2.5, x + 2, y + 2.5), RED, line=0.8, gloss=0.6, rim=0, ao=0)


def _sk_smoke_bomb(p, face):
    grey = hexc("#a8a4b4")
    _puff(p, 30, 66, 13, shade(grey, 0.9), seed=3)
    _puff(p, 66, 68, 12, shade(grey, 0.9), seed=7)
    bomb = p.shape("ellipse", (28, 32, 64, 68), hexc("#3a3a48"), depth=0.22, light=1.45, line=1.5, spec=1.0,
                   tex="metal", tex_amt=0.5, gloss=0.6)
    p.shape("rect", (50, 26, 62, 36), hexc("#6a6a78"), radius=2, line=1.1, spec=0.6, rim=0)
    p.shape("line", [(57, 27), (62, 20), (70, 18), (72, 14)], hexc("#b8905a"), width=3, line=0.9, rim=0, ao=0)
    p.glow((73, 13), 12, hexc("#ffb040"), 0.9)
    p.shape("poly", _star(73, 13, 7, 2.5, 6), hexc("#fff0a0"), line=0.8, rim=0, ao=0, ink=hexc("#6a3a0a"))
    _puff(p, 48, 74, 14, grey, seed=5)
    _puff(p, 22, 50, 8, grey, seed=11, n=4)
    _puff(p, 76, 46, 7, grey, seed=13, n=4)


def _sk_blind(p, face):
    # sand thrown from the lower left toward the eye
    sand = [hexc("#e8c878"), hexc("#d8a850"), hexc("#f4dc98")]
    rnd = 7
    for i in range(34):
        rnd = (rnd * 1103515245 + 12345) & 0x7FFFFFFF
        t = (rnd % 1000) / 1000
        spread = ((rnd >> 10) % 1000 / 1000 - 0.5) * (8 + 26 * t)
        x = 16 + t * 44 + spread * 0.6
        y = 78 - t * 32 + spread
        r = 0.9 + 1.6 * ((rnd >> 20) % 100) / 100
        p.flat("ellipse", (x - r, y - r, x + r, y + r), sand[i % 3])
    # the eye
    eye = ImageChops.multiply(p._mask("ellipse", (22, 26, 82, 64)),
                              ImageChops.multiply(p._mask("ellipse", (18, 6, 86, 70)), p._mask("ellipse", (18, 20, 86, 84))))
    p.paint_mask(eye, hexc("#f4f0e8"), depth=0.25, light=1.2, line=1.5, rim=0, ink=hexc("#2a1a1a"))
    p.shape("ellipse", (41, 33, 63, 55), hexc("#4a8ac8"), depth=0.25, light=1.4, line=1.1, rim=0, ao=0, clip=eye)
    p.flat("ellipse", (47, 39, 57, 49), hexc("#10121a"))
    p.flat("ellipse", (47, 38, 51, 42), hexc("#ffffff", 230))
    for x, y in ((40, 42), (58, 36), (54, 50), (46, 52)):  # grit in the eye
        p.flat("ellipse", (x - 1.3, y - 1.3, x + 1.3, y + 1.3), hexc("#d8a850"))
    # crossed out
    p.shape("line", [(22, 72), (78, 20)], RED, width=6, depth=0.3, line=1.2, rim=0)
    p.shape("ellipse", (60, 60, 66, 70), hexc("#9fe3ff"), line=0.8, gloss=1.0, rim=0, ao=0)  # a tear


def _sk_poison_burst(p, face):
    green = hexc("#5ac23a")
    p.glow((48, 50), 40, hexc("#8aff5a"), 0.6)
    p.shape("poly", _burst(48, 50, 34, 20, 9, seed=11), green, shadow=0.75, light=1.35, depth=0.18, line=1.3,
            rim=0, ink=hexc("#12380c"), clip=face)
    p.shape("poly", _burst(48, 50, 22, 14, 8, seed=6), hexc("#a8f070"), **NOLINE)
    _skull(p, 48, 48, 0.62)
    for x, y, r in ((22, 30, 7), (74, 28, 6), (76, 70, 7.5), (24, 72, 5.5)):  # skull bubbles
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#8ae85a"), depth=0.25, light=1.4, line=1.1, gloss=1.0,
                rim=0, ink=hexc("#12380c"))
        e = r * 0.28
        p.flat("ellipse", (x - r * 0.5 - e, y - e * 0.6, x - r * 0.5 + e, y + e * 1.2), hexc("#12380c"))
        p.flat("ellipse", (x + r * 0.5 - e, y - e * 0.6, x + r * 0.5 + e, y + e * 1.2), hexc("#12380c"))
        p.flat("poly", [(x - 1, y + r * 0.4), (x + 1, y + r * 0.4), (x, y + r * 0.6)], hexc("#12380c"))
    for x, y, r in ((60, 16, 2.5), (14, 50, 2.2), (84, 50, 2), (50, 84, 2.4)):
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#b8ff8a"))


def _sk_blade_rain(p, face):
    for x, top, ln in ((26, 16, 22), (40, 30, 24), (56, 18, 22), (70, 30, 22), (48, 50, 20)):
        p.stroke([(x, top - 8), (x, top + 2)], hexc("#ffffff", 120), 1.6)
        _dagger(p, x, top + 8, x, top + 8 + ln, width=7, grip_len=8)
    for x in (30, 58, 74):  # blades already stuck in the ground
        p.stroke([(x - 6, 80), (x + 6, 80)], hexc("#000000", 90), 2)


def _sk_shadow_step(p, face):
    def figure(ox, oy):
        return p.union([
            ("ellipse", (ox + 8, oy - 2, ox + 26, oy + 18)),                                  # hood
            ("poly", [(ox + 10, oy + 12), (ox + 26, oy + 10), (ox + 26, oy + 34), (ox + 6, oy + 36)]),  # torso
            ("poly", [(ox + 10, oy + 14), (ox - 18, oy + 22), (ox - 14, oy + 32), (ox + 6, oy + 30)]),   # cloak
            ("line", [(ox + 12, oy + 32), (ox + 2, oy + 42), (ox - 10, oy + 46)], {"width": 7}),        # back leg
            ("line", [(ox + 22, oy + 32), (ox + 34, oy + 40), (ox + 34, oy + 50)], {"width": 7}),       # front leg
            ("line", [(ox + 24, oy + 16), (ox + 38, oy + 22)], {"width": 5.5}),                        # arm
        ])
    purple = hexc("#a060ff")
    for i, (dx, a) in enumerate(((-26, 70), (-14, 120))):
        m = ImageChops.multiply(figure(34 + dx, 26), face)
        p._fill(m, purple[:3] + (a,), solid=False)
    for y, x0, x1 in ((40, 12, 30), (52, 10, 26), (64, 14, 30)):
        p.stroke([(x0, y), (x1, y)], hexc("#d8b0ff", 170), 1.8)
    p.glow((56, 50), 26, hexc("#8a3aff"), 0.5)
    body = figure(34, 26)
    p.paint_mask(body, hexc("#231a30"), depth=0.14, light=1.2, line=1.3, rim=1.0, ink=hexc("#0e080e"))
    p.flat("ellipse", (54, 32, 58, 35), hexc("#e0b0ff"))  # eye glint under the hood
    _dagger(p, 72, 48, 82, 40, width=5, grip_len=5, pommel=False)


CLASS_SKILLS = {
    "arcane_bolt": ("#3a2468", _sk_arcane_bolt),
    "fireball": ("#7a2e22", _sk_fireball),
    "flame_burst": ("#5a2220", _sk_flame_burst),
    "ice_lance": ("#2a4a80", _sk_ice_lance),
    "mana_shield": ("#1f3470", _sk_mana_shield),
    "shatter": ("#2a5478", _sk_shatter),
    "chain_lightning": ("#28285e", _sk_chain_lightning),
    "meteor": ("#4a2a3a", _sk_meteor),
    "stab": ("#3e4e62", _sk_stab),
    "poison_blade": ("#2e3e2a", _sk_poison_blade),
    "backstab": ("#8a4a3a", _sk_backstab),
    "smoke_bomb": ("#4a4660", _sk_smoke_bomb),
    "blind": ("#7a6040", _sk_blind),
    "poison_burst": ("#3a2a4a", _sk_poison_burst),
    "blade_rain": ("#3a3e62", _sk_blade_rain),
    "shadow_step": ("#5a4a80", _sk_shadow_step),
}


# ------------------------------------------------------------------ new statuses (48px)

def _status_evasive(p):
    """A figure dodging aside: two see-through afterimages, a solid lilac one and a smoke wisp."""
    def person(ox):
        return p.union([("ellipse", (ox - 7, 5, ox + 7, 19)),
                        ("chord", (ox - 15, 22, ox + 15, 62), {"start": 180, "end": 360})])
    cut = p._mask("rect", (0, 0, 48, 43))
    for ox, a in ((14, 70), (21, 120)):
        p._fill(ImageChops.multiply(person(ox), cut), hexc("#c8b8ff")[:3] + (a,), solid=False)
    p.paint_mask(ImageChops.multiply(person(30), cut), hexc("#8a74c8"), depth=0.2, light=1.35, line=1.3, rim=0.8,
                 ink=hexc("#1e1438"))
    for y, x0 in ((14, 1), (27, 0), (38, 2)):  # speed streaks
        p.stroke([(x0, y), (x0 + 6, y)], hexc("#ffffff", 180), 1.6)
    for x, y, r in ((8, 41, 4.5), (15, 43, 3.5), (4, 36, 2.5)):  # smoke left behind
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#ece6ff", 190), shadow=0.8, light=1.2, line=0,
                rim=0, ao=0)


def _status_chill(p):
    """A small branching snowflake with frosty shiver marks around it."""
    blue = hexc("#bfe8ff")
    ink = hexc("#1e3a6a")
    p.glow((24, 24), 20, hexc("#8fdcff"), 0.5)
    arms = []
    for i in range(6):
        a = math.radians(i * 60 - 90)
        ex, ey = 24 + 15 * math.cos(a), 24 + 15 * math.sin(a)
        arms.append(("line", [(24, 24), (ex, ey)], {"width": 3.4}))
        for t, ln in ((0.55, 5.5), (0.8, 3.5)):
            bx, by = 24 + 15 * t * math.cos(a), 24 + 15 * t * math.sin(a)
            for s in (-1, 1):
                b = a + s * math.radians(50)
                arms.append(("line", [(bx, by), (bx + ln * math.cos(b), by + ln * math.sin(b))], {"width": 2.2}))
    m = p.union(arms)
    p.paint_mask(m, blue, depth=0.4, light=1.4, line=1.0, rim=0, spec=0.6, ink=ink)
    p.shape("ellipse", (20, 20, 28, 28), hexc("#ffffff"), line=0.8, rim=0, ao=0, ink=ink)
    # shiver: little zigzags on both sides
    for sx in (-1, 1):
        x = 24 + sx * 20
        p.stroke([(x, 12), (x + sx * 2.5, 16), (x, 20), (x + sx * 2.5, 24), (x, 28), (x + sx * 2.5, 32), (x, 36)],
                 hexc("#e0f6ff"), 1.6)

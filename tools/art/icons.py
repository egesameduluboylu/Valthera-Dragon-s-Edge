"""Skill, intent and status icons."""
from PIL import Image, ImageDraw

from painter import Painter, hexc, shade

STEEL = hexc("#c9d4de")
GOLD = hexc("#e7b440")
RED = hexc("#d6453a")
DARK = hexc("#221820")
WHITE = hexc("#ffffff")
WOOD = hexc("#9a6433")


def _frame(p, color):
    """Round medallion behind skill icons."""
    p.shape("ellipse", (4, 4, 92, 92), shade(color, 0.55), depth=0.08, line=2.5)
    p.shape("ellipse", (12, 12, 84, 84), color, depth=0.18, line=1.2)


def _sword(p, x0, y0, x1, y1, width=8):
    import math
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    nx, ny = -dy / n * width / 2, dx / n * width / 2
    tip = (x1 + dx / n * 10, y1 + dy / n * 10)
    p.shape("poly", [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), tip, (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)],
            STEEL, depth=0.35, light=1.3, line=1.4)
    gx, gy = x0, y0
    p.shape("line", [(gx - nx * 2.2, gy - ny * 2.2), (gx + nx * 2.2, gy + ny * 2.2)], GOLD, width=6, line=1.2)
    p.shape("line", [(gx, gy), (gx - dx / n * 16, gy - dy / n * 16)], hexc("#6b4428"), width=6, line=1.2)


def _shield(p, box, color, crack=False):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    pts = [(x0, y0), (x1, y0), (x1, (y0 + y1) / 2), (cx, y1), (x0, (y0 + y1) / 2)]
    p.shape("poly", pts, color, depth=0.15, line=1.6)
    p.shape("ellipse", (cx - 7, y0 + 14, cx + 7, y0 + 28), GOLD, line=1.2)
    if crack:
        p.shape("line", [(cx + 4, y0 - 2), (cx - 6, y0 + 16), (cx + 8, y0 + 30), (cx - 2, y1 + 2)],
                DARK, width=4, shadow=0, light=0, line=0)


def _skull(p, cx, cy, s=1.0):
    p.shape("ellipse", (cx - 18 * s, cy - 18 * s, cx + 18 * s, cy + 14 * s), hexc("#ece3c8"), line=1.4)
    p.shape("rect", (cx - 10 * s, cy + 6 * s, cx + 10 * s, cy + 20 * s), hexc("#ece3c8"), radius=4 * s, line=1.4)
    p.flat("ellipse", (cx - 12 * s, cy - 6 * s, cx - 2 * s, cy + 4 * s), DARK)
    p.flat("ellipse", (cx + 2 * s, cy - 6 * s, cx + 12 * s, cy + 4 * s), DARK)


def _star(cx, cy, r_out, r_in, n=5):
    import math
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _drop(p, cx, cy, color, s=1.0):
    p.shape("poly", [(cx, cy - 20 * s), (cx - 13 * s, cy + 2 * s), (cx + 13 * s, cy + 2 * s)], color, line=1.4)
    p.shape("ellipse", (cx - 14 * s, cy - 8 * s, cx + 14 * s, cy + 18 * s), color, line=1.4)


def _flame(p, cx, cy, s=1.0):
    p.shape("poly", [(cx, cy - 24 * s), (cx + 16 * s, cy + 2 * s), (cx + 10 * s, cy + 18 * s), (cx - 10 * s, cy + 18 * s),
                     (cx - 16 * s, cy + 2 * s)], hexc("#ff7a2a"), line=1.4)
    p.shape("poly", [(cx, cy - 8 * s), (cx + 8 * s, cy + 6 * s), (cx, cy + 16 * s), (cx - 8 * s, cy + 6 * s)],
            hexc("#ffd86a"), line=0)


# ------------------------------------------------------------------ skills (96px)

def skill_icon(kind):
    p = Painter(96, 96)
    if kind == "slash":
        _frame(p, hexc("#3f5f9e"))
        _sword(p, 30, 66, 64, 32)
        p.shape("line", [(24, 40), (40, 26), (60, 20)], WHITE, width=4, shadow=0, light=0, line=0)
    elif kind == "shield_break":
        _frame(p, hexc("#6b5b8e"))
        _shield(p, (26, 22, 70, 76), hexc("#8fa0b3"), crack=True)
    elif kind == "heavy_strike":
        _frame(p, hexc("#9e4a3a"))
        p.shape("poly", _star(58, 60, 20, 9, 8), GOLD, line=1.2)
        _sword(p, 24, 28, 54, 56, width=12)
    elif kind == "execute":
        _frame(p, hexc("#5a2a3a"))
        _skull(p, 48, 48, 1.1)
        p.shape("line", [(22, 74), (74, 22)], RED, width=5, shadow=0, light=0, line=0)
    elif kind == "battle_cry":
        _frame(p, hexc("#a8702a"))
        p.shape("poly", [(26, 40), (50, 30), (50, 66), (26, 56)], hexc("#d9b36b"), line=1.4)
        for r in (10, 18):
            p.shape("line", [(56, 48 - r), (56 + r * 0.7, 48), (56, 48 + r)], WHITE, width=4, shadow=0, light=0, line=0)
    elif kind == "rending_cut":
        _frame(p, hexc("#7a2a2a"))
        for i in range(3):
            p.shape("line", [(28 + i * 12, 26), (46 + i * 12, 70)], STEEL, width=5, line=1)
        _drop(p, 68, 62, RED, 0.6)
    elif kind == "iron_wall":
        _frame(p, hexc("#4a5a6a"))
        p.shape("rect", (28, 20, 68, 76), hexc("#8fa0b3"), radius=6, line=1.6)
        p.shape("line", [(48, 24), (48, 72)], hexc("#5d6b7a"), width=4, shadow=0, light=0, line=0)
    elif kind == "whirlwind":
        _frame(p, hexc("#3a7a6a"))
        for r in (12, 22, 32):
            p.shape("line", [(48 - r, 48), (48, 48 - r), (48 + r, 48)], WHITE, width=4, shadow=0, light=0, line=0)
    return p.finish(outline=1)


# ------------------------------------------------------------------ intents & statuses (48px)

def small_icon(kind):
    p = Painter(48, 48)
    if kind == "attack":
        _sword(p, 12, 36, 34, 14, width=7)
    elif kind == "shield":
        _shield(p, (10, 6, 38, 42), hexc("#8fa0b3"))
    elif kind == "buff":
        p.shape("poly", [(24, 4), (42, 24), (31, 24), (31, 44), (17, 44), (17, 24), (6, 24)], hexc("#5ad16a"), line=1.4)
    elif kind in ("debuff", "execute"):
        _skull(p, 24, 22, 0.9)
    elif kind in ("stunned", "stun"):
        p.shape("poly", _star(16, 18, 10, 4), GOLD, line=1.2)
        p.shape("poly", _star(32, 30, 10, 4), GOLD, line=1.2)
    elif kind == "bleed":
        _drop(p, 24, 24, RED, 0.8)
    elif kind == "burn":
        _flame(p, 24, 24, 0.85)
    elif kind == "poison":
        _drop(p, 24, 24, hexc("#6fd13a"), 0.8)
    elif kind == "freeze":
        for a, b in (((24, 4), (24, 44)), ((7, 14), (41, 34)), ((7, 34), (41, 14))):
            p.shape("line", [a, b], hexc("#9fe3ff"), width=5, line=1.2)
    elif kind == "armor_break":
        _shield(p, (10, 6, 38, 42), hexc("#8fa0b3"), crack=True)
    elif kind == "strengthened":
        p.shape("poly", [(24, 4), (42, 24), (31, 24), (31, 44), (17, 44), (17, 24), (6, 24)], hexc("#ff9a3a"), line=1.4)
    elif kind == "target":
        p.shape("poly", [(6, 10), (42, 10), (24, 40)], hexc("#ffd24a"), line=1.6, depth=0.25)
    elif kind == "shield_status":
        _shield(p, (10, 6, 38, 42), hexc("#7fb2ff"))
    else:
        return item_icon(kind)
    return p.finish(outline=1)


# ------------------------------------------------------------------ rooms (96px) and items (48px)

def _chest(p, x0, y0, x1, y1):
    wood = hexc("#a0652f")
    mid = y0 + (y1 - y0) * 0.42
    p.shape("rect", (x0, mid, x1, y1), wood, radius=4, depth=0.12)
    p.shape("chord", (x0, y0, x1, 2 * mid - y0), wood, start=180, end=360, depth=0.12)
    for fx in (0.18, 0.82):
        x = x0 + (x1 - x0) * fx
        p.shape("rect", (x - 3, y0 - 2, x + 3, y1), GOLD, radius=1, line=1)
    cx = (x0 + x1) / 2
    p.shape("rect", (cx - 6, mid - 5, cx + 6, mid + 9), GOLD, radius=2, line=1)


def _campfire(p, cx, cy, s=1.0):
    for a, b in (((cx - 26 * s, cy + 16 * s), (cx + 22 * s, cy + 4 * s)), ((cx - 22 * s, cy + 4 * s), (cx + 26 * s, cy + 16 * s))):
        p.shape("line", [a, b], hexc("#7a4a2a"), width=9 * s, line=1.2)
    p.glow((cx, cy - 6 * s), 34 * s, hexc("#ffb040"), 0.8)
    _flame(p, cx, cy - 10 * s, 1.05 * s)


def _crown(p, cx, cy, s=1.0):
    pts = [(cx - 30 * s, cy + 14 * s), (cx - 30 * s, cy - 18 * s), (cx - 15 * s, cy - 2 * s), (cx, cy - 24 * s),
           (cx + 15 * s, cy - 2 * s), (cx + 30 * s, cy - 18 * s), (cx + 30 * s, cy + 14 * s)]
    p.shape("poly", pts, hexc("#f1c24a"), depth=0.2, light=1.35)
    p.shape("rect", (cx - 31 * s, cy + 6 * s, cx + 31 * s, cy + 16 * s), hexc("#d49a2a"), radius=2, line=1.2)
    p.shape("ellipse", (cx - 5 * s, cy + 7 * s, cx + 5 * s, cy + 15 * s), RED, light=1.6, line=1)


def _potion(p, cx, cy, s=1.0, color=None):
    color = color or hexc("#e0303a")
    p.shape("rect", (cx - 5 * s, cy - 20 * s, cx + 5 * s, cy - 8 * s), hexc("#cfe3ea"), radius=2, line=1.2)
    p.shape("rect", (cx - 7 * s, cy - 24 * s, cx + 7 * s, cy - 18 * s), hexc("#8a5a34"), radius=2, line=1.2)
    p.shape("ellipse", (cx - 16 * s, cy - 12 * s, cx + 16 * s, cy + 20 * s), color, light=1.4, depth=0.2)
    p.flat("ellipse", (cx - 9 * s, cy - 6 * s, cx - 3 * s, cy + 2 * s), hexc("#ffffff", 200))


def room_icon(kind):
    p = Painter(96, 96)
    colors = {"combat": "#8a3a2e", "elite": "#6a2a7a", "treasure": "#a8702a", "event": "#2e5a8a",
              "rest": "#2e7a4a", "boss": "#4a1a24"}
    _frame(p, hexc(colors[kind]))
    if kind == "combat":
        _sword(p, 26, 70, 62, 30)
        _sword(p, 70, 70, 34, 30)
    elif kind == "elite":
        p.shape("poly", [(26, 40), (14, 16), (38, 30)], hexc("#ece3c8"), line=1.2)
        p.shape("poly", [(70, 40), (82, 16), (58, 30)], hexc("#ece3c8"), line=1.2)
        _skull(p, 48, 50, 1.05)
        p.glow((42, 49), 8, hexc("#ffcc33"), 0.9)
        p.glow((54, 49), 8, hexc("#ffcc33"), 0.9)
    elif kind == "treasure":
        _chest(p, 22, 34, 74, 72)
    elif kind == "event":
        p.shape("rect", (28, 20, 68, 76), hexc("#f1e2c0"), radius=6, line=1.4)
        p.shape("line", [(40, 38), (44, 30), (54, 30), (57, 38), (48, 46), (48, 54)], hexc("#2e5a8a"), width=6,
                shadow=0, light=0, line=0)
        p.flat("ellipse", (44, 60, 52, 68), hexc("#2e5a8a"))
    elif kind == "rest":
        _campfire(p, 48, 54)
    elif kind == "boss":
        _crown(p, 48, 44, 0.9)
        _skull(p, 48, 64, 0.62)
    return p.finish(outline=1)


def item_icon(kind):
    p = Painter(48, 48)
    if kind == "potion":
        _potion(p, 24, 26, 0.95)
    elif kind == "gold":
        p.shape("ellipse", (6, 12, 34, 40), hexc("#d49a2a"), line=1.4)
        p.shape("ellipse", (14, 6, 42, 34), hexc("#f1c24a"), light=1.4, line=1.4)
        p.shape("ellipse", (21, 13, 35, 27), hexc("#d49a2a"), shadow=0, light=0, line=1)
    elif kind == "heart":
        p.shape("ellipse", (5, 8, 26, 30), hexc("#e0303a"), line=0, shadow=0)
        p.shape("ellipse", (22, 8, 43, 30), hexc("#e0303a"), line=0, shadow=0)
        p.shape("poly", [(6, 22), (42, 22), (24, 43)], hexc("#e0303a"), line=0, shadow=0)
        p.flat("ellipse", (11, 13, 18, 20), hexc("#ffffff", 200))
    elif kind == "xp":
        p.shape("poly", _star(24, 25, 21, 9), hexc("#7fd4ff"), light=1.4, line=1.4)
    elif kind == "summon":
        _skull(p, 20, 24, 0.75)
        p.shape("rect", (32, 12, 38, 34), hexc("#5ad16a"), radius=2, line=1.2)
        p.shape("rect", (24, 20, 46, 26), hexc("#5ad16a"), radius=2, line=1.2)
    elif kind == "enraged":
        _flame(p, 24, 24, 0.85)
        p.shape("line", [(14, 22), (22, 26)], DARK, width=3, shadow=0, light=0, line=0)
        p.shape("line", [(34, 22), (26, 26)], DARK, width=3, shadow=0, light=0, line=0)
    elif kind == "scale":
        # a dragon scale: rounded shield shape with ridges
        pts = [(24, 4), (40, 14), (40, 28), (24, 44), (8, 28), (8, 14)]
        p.shape("poly", pts, hexc("#4fb8e8"), depth=0.22, light=1.45, line=1.4)
        p.shape("line", [(24, 10), (24, 36)], hexc("#2a7aa8"), width=2.5, shadow=0, light=0, line=0)
        p.shape("line", [(14, 18), (24, 26), (34, 18)], hexc("#2a7aa8"), width=2, shadow=0, light=0, line=0)
        p.flat("ellipse", (13, 11, 19, 17), hexc("#ffffff", 200))
    elif kind == "bag":
        leather = hexc("#a0652f")
        p.shape("ellipse", (6, 16, 42, 46), leather, depth=0.16)
        p.shape("poly", [(20, 19), (28, 19), (35, 5), (13, 5)], shade(leather, 0.9), line=1.2)
        for x in (15, 21, 27, 33):
            p.shape("ellipse", (x - 3, 3, x + 3, 9), shade(leather, 0.9), line=1)
        p.shape("line", [(18, 19), (30, 19)], hexc("#e7b440"), width=3, line=0.8)
        p.shape("line", [(30, 19), (36, 26)], hexc("#e7b440"), width=2, line=0.6)
        p.shape("ellipse", (19, 27, 29, 37), GOLD, light=1.4, line=1)
    elif kind == "flee":
        p.shape("poly", [(40, 24), (22, 8), (22, 18), (8, 18), (8, 30), (22, 30), (22, 40)], hexc("#e7e0d0"), line=1.4)
    return p.finish(outline=1)


ROOM_ICONS = ["combat", "elite", "treasure", "event", "rest", "boss"]
ITEM_ICONS = ["potion", "gold", "heart", "xp", "flee", "scale", "bag"]

SKILL_ICONS = ["slash", "shield_break", "heavy_strike", "execute", "battle_cry", "rending_cut", "iron_wall", "whirlwind"]
INTENT_ICONS = ["attack", "shield", "buff", "debuff", "stunned", "summon"]
STATUS_ICONS = ["bleed", "burn", "poison", "freeze", "stun", "armor_break", "strengthened", "shield_status",
                "enraged"]

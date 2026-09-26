"""Equipment icons for the bag, smith and merchant (96px, transparent).

The rarity frame is drawn by the UI, so these are just the items themselves.
"""
import math

from painter import Painter, hexc, shade

STEEL = hexc("#c9d4de")
IRON = hexc("#9aa6b2")
RUST = hexc("#b0643a")
GOLD = hexc("#e7b440")
BONE = hexc("#ece3c8")
LEATHER = hexc("#9a6433")
DARK = hexc("#221820")
GRIP = hexc("#5a3a22")
RED = hexc("#d6453a")


def _blade(p, x0, y0, x1, y1, width, color, tip=14):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy * width / 2, ux * width / 2
    pts = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 + ux * tip, y1 + uy * tip), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
    p.shape("poly", pts, color, depth=0.3, light=1.3, line=1.4)
    # fuller down the middle
    p.shape("line", [(x0 + ux * 6, y0 + uy * 6), (x1 - ux * 6, y1 - uy * 6)], shade(color, 0.8), width=width * 0.22,
            shadow=0, light=0, line=0)
    return ux, uy, nx, ny


def _hilt(p, x0, y0, ux, uy, nx, ny, guard=GOLD, grip=GRIP, length=20):
    p.shape("line", [(x0, y0), (x0 - ux * length, y0 - uy * length)], grip, width=8, line=1.2)
    p.shape("line", [(x0 - nx * 2.4, y0 - ny * 2.4), (x0 + nx * 2.4, y0 + ny * 2.4)], guard, width=8, line=1.2)
    ex, ey = x0 - ux * (length + 4), y0 - uy * (length + 4)
    p.shape("ellipse", (ex - 6, ey - 6, ex + 6, ey + 6), guard, line=1.2)


def rusty_sword():
    p = Painter(96, 96)
    ux, uy, nx, ny = _blade(p, 34, 62, 72, 24, 12, hexc("#b9a592"))
    for fx, fy, r in ((46, 50, 5), (58, 38, 4), (64, 33, 3), (40, 56, 3)):
        p.flat("ellipse", (fx - r, fy - r, fx + r, fy + r), RUST)
    _hilt(p, 34, 62, ux, uy, nx, ny, guard=hexc("#8a6a4a"))
    return p.finish(outline=2)


def iron_sword():
    p = Painter(96, 96)
    ux, uy, nx, ny = _blade(p, 34, 62, 74, 22, 12, STEEL)
    _hilt(p, 34, 62, ux, uy, nx, ny)
    p.glow((66, 30), 8, hexc("#ffffff"), 0.7)
    return p.finish(outline=2)


def bone_cleaver():
    p = Painter(96, 96)
    # wide chopping blade with a bone spine
    p.shape("poly", [(36, 58), (40, 22), (80, 16), (84, 30), (74, 52), (48, 64)], hexc("#b8c2cc"), depth=0.2, light=1.3)
    p.shape("line", [(40, 24), (80, 18)], BONE, width=8, line=1.2)
    for x in (48, 58, 68):
        p.shape("ellipse", (x - 4, 17 - 3 + (80 - x) * 0.1, x + 4, 25 + (80 - x) * 0.1), BONE, line=1)
    p.shape("line", [(40, 60), (20, 80)], BONE, width=10, line=1.4)
    p.shape("ellipse", (12, 74, 26, 88), BONE, line=1.4)
    p.flat("line", [(52, 44), (68, 36)], hexc("#8a2a2a"), width=3)
    return p.finish(outline=2)


def _torso(p, color, trim, collar=True):
    pts = [(24, 18), (38, 14), (48, 22), (58, 14), (72, 18), (80, 40), (70, 44), (68, 82), (28, 82), (26, 44), (16, 40)]
    p.shape("poly", pts, color, depth=0.14)
    p.shape("rect", (28, 74, 68, 84), trim, radius=3, line=1.2)
    if collar:
        p.shape("poly", [(38, 14), (48, 30), (58, 14), (54, 12), (48, 22), (42, 12)], trim, line=1.2)


def leather_armor():
    p = Painter(96, 96)
    _torso(p, LEATHER, hexc("#6b4428"))
    for y in (40, 52, 64):
        p.shape("line", [(34, y), (62, y)], hexc("#6b4428"), width=3, shadow=0, light=0, line=0)
    for x, y in ((36, 46), (60, 46), (36, 58), (60, 58)):
        p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), GOLD, line=0.8)
    return p.finish(outline=2)


def chain_mail():
    p = Painter(96, 96)
    _torso(p, IRON, hexc("#6d7a86"))
    clip = p.flat("poly", [(26, 20), (70, 20), (68, 72), (28, 72)], (0, 0, 0, 0))
    for row in range(8):
        for col in range(8):
            x = 28 + col * 6 + (3 if row % 2 else 0)
            y = 24 + row * 6
            p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), shade(IRON, 1.15), depth=0.3, line=0.6, clip=clip)
    p.shape("rect", (40, 40, 56, 56), hexc("#8a2a2a"), radius=3, line=1.2)
    p.shape("poly", [(48, 43), (53, 48), (48, 53), (43, 48)], GOLD, line=0.8)
    return p.finish(outline=2)


def leather_cap():
    p = Painter(96, 96)
    p.shape("chord", (16, 20, 80, 84), LEATHER, start=180, end=360, depth=0.16)
    p.shape("rect", (12, 50, 84, 62), hexc("#6b4428"), radius=4, line=1.4)
    p.shape("line", [(48, 22), (48, 50)], hexc("#6b4428"), width=4, shadow=0, light=0, line=0)
    for x in (22, 36, 60, 74):
        p.shape("ellipse", (x - 3, 53, x + 3, 59), GOLD, line=0.6)
    return p.finish(outline=2)


def iron_helm():
    p = Painter(96, 96)
    p.shape("chord", (16, 14, 80, 86), IRON, start=180, end=360, depth=0.18, light=1.3)
    p.shape("rect", (18, 48, 78, 78), IRON, radius=6, depth=0.12)
    p.flat("rect", (26, 54, 70, 60), DARK, radius=2)          # eye slit
    p.shape("rect", (45, 54, 51, 78), shade(IRON, 0.85), radius=2, line=1)  # nose guard
    p.shape("line", [(48, 14), (48, 48)], shade(IRON, 1.2), width=5, shadow=0, light=0, line=1)
    p.shape("poly", [(48, 6), (58, 16), (48, 20), (38, 16)], RED, line=1.2)  # plume tip
    return p.finish(outline=2)


def copper_ring():
    p = Painter(96, 96)
    copper = hexc("#d9894a")
    p.shape("ellipse", (18, 30, 78, 86), copper, depth=0.2, light=1.35)
    p.shape("ellipse", (30, 42, 66, 76), (0, 0, 0, 0), shadow=0, light=0, line=1.4)
    # punch the hole
    hole = p._mask("ellipse", (31, 43, 65, 75))
    from PIL import ImageChops
    a = p.img.getchannel("A")
    p.img.putalpha(ImageChops.subtract(a, hole))
    p.shape("ellipse", (36, 18, 60, 42), hexc("#3fc0a0"), depth=0.25, light=1.5, line=1.4)
    p.glow((44, 26), 6, hexc("#ffffff"), 0.8)
    return p.finish(outline=2)


def bone_amulet():
    p = Painter(96, 96)
    p.shape("line", [(18, 10), (48, 44), (78, 10)], hexc("#7a5a3a"), width=4, line=0.8)
    p.shape("poly", [(48, 36), (68, 54), (48, 90), (28, 54)], BONE, depth=0.18)
    p.shape("ellipse", (38, 50, 58, 70), hexc("#8a2a2a"), light=1.4, line=1.2)
    p.flat("ellipse", (42, 55, 47, 60), DARK)
    p.flat("ellipse", (49, 55, 54, 60), DARK)
    return p.finish(outline=2)


def bone_crown():
    p = Painter(96, 96)
    p.glow((48, 50), 44, hexc("#ff9a2a"), 0.55)
    pts = [(14, 70), (14, 32), (30, 50), (48, 22), (66, 50), (82, 32), (82, 70)]
    p.shape("poly", pts, BONE, depth=0.18, light=1.3)
    for x, y in ((14, 30), (48, 20), (82, 30)):
        p.shape("ellipse", (x - 6, y - 6, x + 6, y + 6), BONE, line=1.2)
    p.shape("rect", (12, 60, 84, 74), hexc("#f1c24a"), radius=3, line=1.4, light=1.35)
    for x, c in ((30, "#d6453a"), (48, "#7a3ae0"), (66, "#d6453a")):
        p.shape("ellipse", (x - 5, 62, x + 5, 72), hexc(c), light=1.6, line=1)
    return p.finish(outline=2)


GEAR = {
    "rusty_sword": rusty_sword, "iron_sword": iron_sword, "bone_cleaver": bone_cleaver,
    "leather_armor": leather_armor, "chain_mail": chain_mail,
    "leather_cap": leather_cap, "iron_helm": iron_helm,
    "copper_ring": copper_ring, "bone_amulet": bone_amulet, "bone_crown": bone_crown,
}

"""Character and enemy sprites. The player faces right, enemies face left.
All coordinates are in final-image pixels (256 x 256; the boss is 384 x 384).

Everything is drawn with the soft Painter look: smooth cel gradients, rim light, contact
shadows, textured materials and colour-tinted ink, lit from the top left.
"""
import math

from painter import Painter, hexc, mix, shade

SIZE = 256

STEEL = hexc("#b9c6d3")
STEEL_DARK = hexc("#6f7f92")
SKIN = hexc("#f2c393")
BLUE = hexc("#3566b8")
RED = hexc("#c63a2f")
GOLD = hexc("#e7b440")
LEATHER = hexc("#7a4a2a")
WOOD = hexc("#9a6433")
BONE = hexc("#ece3c8")
RUST = hexc("#9a5a34")
WHITE = hexc("#ffffff")
DARK = hexc("#221820")
NOLINE = dict(shadow=0, light=0, line=0)


# ------------------------------------------------------------------ helpers

def _painter(w, h=None):
    return Painter(w, h or w, soft=True)


def along(pts, step):
    """Points every `step` pixels along a polyline."""
    out = []
    carry = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        t = carry
        while t <= seg:
            out.append((x0 + (x1 - x0) * t / seg, y0 + (y1 - y0) * t / seg))
            t += step
        carry = t - seg
    return out


def curve(pts, steps=8):
    """Catmull-Rom spline through pts."""
    out = []
    pts = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(2)))
    out.append(pts[-2])
    return out


def stitches(p, pts, color, step=6, length=3.0, width=1.2):
    """Dashed stitch line along a polyline."""
    pts = curve(pts, 6) if len(pts) > 2 else pts
    marks = along(pts, step)
    for (x0, y0), (x1, y1) in zip(marks, marks[1:]):
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1
        p.stroke([(x0, y0), (x0 + dx / n * length, y0 + dy / n * length)], color, width)


def rivet(p, x, y, r=2.2, color=None):
    color = color or hexc("#d4dde6")
    p.shape("ellipse", (x - r, y - r, x + r, y + r), color, line=0.7, depth=0.4, light=1.6, rim=0, ao=0.45)


def rivets(p, pts, r=2.2, color=None):
    for x, y in pts:
        rivet(p, x, y, r, color)


def blade(p, base, tip, width, color, fuller=True, spec=1.0, tex="metal", edge=True):
    """Straight blade from base to tip, with a fuller, a bevel and a glint."""
    (x0, y0), (x1, y1) = base, tip
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy * width / 2, ux * width / 2
    tl = 1.6 * width
    pts = [(x0 + nx, y0 + ny), (x1 - ux * tl + nx * 0.9, y1 - uy * tl + ny * 0.9), (x1, y1),
           (x1 - ux * tl - nx * 0.9, y1 - uy * tl - ny * 0.9), (x0 - nx, y0 - ny)]
    p.shape("poly", pts, color, depth=0.3, light=1.35, line=1.3, spec=spec, tex=tex, tex_amt=0.5)
    if edge:  # bright bevel along the lit edge
        p.stroke([(x0 - nx * 0.7, y0 - ny * 0.7), (x1 - ux * tl - nx * 0.6, y1 - uy * tl - ny * 0.6), (x1, y1)],
                 hexc("#ffffff", 150), max(1.0, width * 0.14))
    if fuller:
        p.stroke([(x0 + ux * 4, y0 + uy * 4), (x1 - ux * tl * 1.2, y1 - uy * tl * 1.2)], shade(color, 0.72),
                 max(1.2, width * 0.2))
    return ux, uy, nx / (width / 2), ny / (width / 2)


def eye(p, cx, cy, rx, ry, iris=hexc("#3a6ab0"), look=(1, 0), brow=None, lid=0.0, skin=SKIN):
    """Cartoon eye: white, iris, pupil, two catchlights, a heavy upper lid line."""
    p.shape("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry), hexc("#fbf8f2"), shadow=0.86, light=0, depth=0.25,
            line=1.1, rim=0, ao=0)
    ix, iy = cx + look[0] * rx * 0.35, cy + look[1] * ry * 0.25 + ry * 0.05
    ir = min(rx, ry) * 0.72
    p.shape("ellipse", (ix - ir, iy - ir * 1.12, ix + ir, iy + ir * 1.12), iris, shadow=0.6, light=1.35, depth=0.3,
            line=0, rim=0, ao=0)
    pr = ir * 0.5
    p.flat("ellipse", (ix - pr, iy - pr * 1.1, ix + pr, iy + pr * 1.1), DARK)
    p.flat("ellipse", (ix - ir * 0.62, iy - ir * 0.75, ix - ir * 0.06, iy - ir * 0.2), WHITE)
    p.flat("ellipse", (ix + ir * 0.25, iy + ir * 0.3, ix + ir * 0.55, iy + ir * 0.6), hexc("#ffffff", 200))
    if lid:
        p.shape("chord", (cx - rx - 1.5, cy - ry - 2, cx + rx + 1.5, cy + ry - (1 - lid) * ry * 2 + 2), skin,
                start=180, end=360, **NOLINE)
    top = cy - ry + lid * ry * 1.6
    p.stroke(curve([(cx - rx - 1, top + ry * 0.35), (cx, top - 0.5), (cx + rx + 1.5, top + ry * 0.25)], 5), DARK, 2.2)


def glow_eye(p, cx, cy, r, color, core=hexc("#fff6c8"), socket=True, strength=0.95):
    if socket:
        p.shape("ellipse", (cx - r, cy - r * 0.9, cx + r, cy + r), hexc("#1a1018"), shadow=0, light=0, line=0, ao=0)
    p.glow((cx, cy), r * 2.6, color, strength)
    p.flat("ellipse", (cx - r * 0.55, cy - r * 0.5, cx + r * 0.55, cy + r * 0.5), mix(color, core, 0.4))
    p.flat("ellipse", (cx - r * 0.28, cy - r * 0.28, cx + r * 0.22, cy + r * 0.22), core)


def teeth(p, pts, color=hexc("#f4ecd4"), line=1.0):
    """Row of pointed teeth; pts are (x, y, w, h, direction) with direction 1 = pointing down."""
    for x, y, w, h, d in pts:
        p.shape("poly", [(x - w / 2, y), (x + w / 2, y), (x + w * 0.08, y + h * d)], color, depth=0.25, light=1.2,
                line=line, rim=0, ao=0.3)


def chain(p, a, b, n, color=hexc("#8a939e"), size=7):
    (x0, y0), (x1, y1) = a, b
    for i in range(n):
        t = i / max(1, n - 1)
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if i % 2:
            p.shape("ellipse", (x - size * 0.3, y - size * 0.55, x + size * 0.3, y + size * 0.55), color, line=1.0,
                    depth=0.3, rim=0, spec=0.6)
        else:
            ring = p.union([("ellipse", (x - size * 0.6, y - size * 0.4, x + size * 0.6, y + size * 0.4))])
            hole = p._mask("ellipse", (x - size * 0.3, y - size * 0.15, x + size * 0.3, y + size * 0.15))
            from PIL import ImageChops
            p.paint_mask(ImageChops.subtract(ring, hole), color, line=1.0, depth=0.3, rim=0, spec=0.6)


# ------------------------------------------------------------------ player

def warrior():
    p = _painter(SIZE)
    steel = hexc("#bfcbd8")
    tabard = hexc("#2f62b8")
    cape = hexc("#b8322c")
    boot = hexc("#6e4127")
    trouser = hexc("#454b62")
    gold = hexc("#f0bb45")

    # ---- cape flowing behind, with a dark lining at the turned hem
    cm = p.union([("poly", curve([(100, 106), (86, 150), (70, 196), (58, 226), (78, 230), (96, 222), (116, 232),
                                  (132, 218), (140, 110)], 6))])
    p.paint_mask(cm, cape, depth=0.12, tex="cloth", tex_amt=0.6)
    p.shape("poly", curve([(58, 226), (70, 214), (80, 222), (78, 230)], 4), shade(cape, 0.5), depth=0.2, rim=0)
    for pts in ([(96, 130), (82, 184), (70, 216)], [(110, 150), (100, 196), (96, 220)]):
        p.stroke(curve(pts, 6), shade(cape, 0.6), 2.2)
    # ---- legs: trousers, knee cops, greaves and boots
    for x in (104, 134):
        p.shape("rect", (x, 176, x + 22, 214), trouser, radius=6, tex="cloth", tex_amt=0.5)
        p.shape("rect", (x - 1, 200, x + 23, 222), steel, radius=5, depth=0.25, spec=0.7, tex="metal", tex_amt=0.4)
        p.shape("ellipse", (x + 1, 190, x + 21, 206), steel, depth=0.3, light=1.35, spec=1.0)
        rivet(p, x + 11, 198, 1.8)
    for x0, x1 in ((96, 130), (130, 166)):
        p.shape("rect", (x0, 212, x1, 236), boot, radius=8, depth=0.2, tex="leather", tex_amt=0.8)
        p.shape("rect", (x0 - 1, 209, x1 - 2, 218), shade(boot, 1.18), radius=4, depth=0.3, tex="leather")
        p.shape("rect", (x0 + 1, 231, x1 + 1, 238), shade(boot, 0.55), radius=3, depth=0.3, rim=0)
    # ---- chain mail skirt under the tabard
    mail = p.shape("rect", (92, 150, 162, 194), hexc("#8d98a6"), radius=10, depth=0.16, tex="metal", tex_amt=0.5)
    for row, y in enumerate(range(156, 196, 5)):
        for x in range(94 + (row % 2) * 3, 162, 6):
            p.shape("chord", (x - 3, y - 3, x + 3, y + 3), hexc("#a9b4c1"), start=0, end=180, line=0.6, light=1.4,
                    shadow=0.7, depth=0.4, rim=0, ao=0, clip=mail)
    # ---- blue tabard with gold trim, split at the hem
    tab = [(96, 108), (158, 108), (158, 184), (150, 198), (130, 190), (124, 190), (104, 198), (96, 184)]
    p.shape("poly", tab, tabard, depth=0.14, tex="cloth", tex_amt=0.7)
    p.stroke([(100, 184), (106, 193), (124, 186)], gold, 2.4)
    p.stroke([(154, 184), (148, 193), (130, 186)], gold, 2.4)
    p.stroke([(127, 150), (127, 188)], shade(tabard, 0.62), 2)
    # emblem: a golden dragon-wing crest with a ruby
    crest = [(127, 118), (142, 124), (138, 140), (127, 150), (116, 140), (112, 124)]
    p.shape("poly", crest, gold, depth=0.22, light=1.4, spec=0.8)
    p.shape("poly", [(127, 124), (135, 128), (133, 138), (127, 144), (121, 138), (119, 128)], hexc("#c63a3a"),
            depth=0.3, light=1.5, line=0.8, gloss=0.9, rim=0)
    # ---- belt with stitches, a buckle and a pouch
    p.shape("rect", (91, 166, 163, 179), hexc("#6a3f24"), radius=4, depth=0.3, tex="leather")
    stitches(p, [(94, 168.5), (160, 168.5)], hexc("#c89a6a"), step=5, length=2.4, width=1)
    stitches(p, [(94, 176.5), (160, 176.5)], hexc("#c89a6a"), step=5, length=2.4, width=1)
    p.shape("rect", (117, 162, 137, 183), gold, radius=3, depth=0.3, light=1.45, spec=1.0)
    p.shape("rect", (122, 167, 132, 178), hexc("#6a3f24"), radius=2, **NOLINE)
    p.stroke([(127, 167), (127, 177)], shade(gold, 0.8), 2)
    p.shape("rect", (140, 172, 156, 190), hexc("#8a5530"), radius=4, depth=0.25, tex="leather")
    p.shape("chord", (139, 168, 157, 182), hexc("#7a4a2a"), start=0, end=180, depth=0.3, line=1.1)
    rivet(p, 148, 178, 1.6, gold)
    # ---- sword: blade, crossguard with a gem, wrapped grip and pommel
    ux, uy, nx, ny = blade(p, (184, 116), (238, 26), 13, hexc("#d8e2ec"))
    gx, gy = 184, 116
    p.shape("line", [(gx - nx * 13, gy - ny * 13), (gx - nx * 4, gy - ny * 4 + 2), (gx + nx * 4, gy + ny * 4 + 2),
                     (gx + nx * 13, gy + ny * 13)], gold, width=6.5, depth=0.35, light=1.4, spec=0.9, rim=0)
    p.shape("ellipse", (gx - 4.5, gy - 2.5, gx + 4.5, gy + 6.5), hexc("#3a8ae0"), line=1.0, gloss=1.0, rim=0)
    grip = [(gx - ux * 3, gy - uy * 3), (gx - ux * 22, gy - uy * 22)]
    p.shape("line", grip, hexc("#5a3320"), width=7, depth=0.3, tex="leather")
    for i in range(4):
        t = 6 + i * 4.5
        cx, cy = gx - ux * t, gy - uy * t
        p.stroke([(cx - nx * 3.4, cy - ny * 3.4), (cx + nx * 3.4 - ux * 2, cy + ny * 3.4 - uy * 2)],
                 hexc("#2a1810"), 1.2)
    px_, py_ = gx - ux * 26, gy - uy * 26
    p.shape("ellipse", (px_ - 5.5, py_ - 5.5, px_ + 5.5, py_ + 5.5), gold, depth=0.3, light=1.45, gloss=0.9)
    # ---- sword arm: sleeve, vambrace and gauntlet around the grip
    p.shape("line", [(158, 118), (170, 140), (182, 128)], tabard, width=15, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(168, 138), (180, 128)], steel, width=13, depth=0.3, spec=0.8, tex="metal", tex_amt=0.4)
    p.shape("ellipse", (170, 111, 192, 131), hexc("#9aa7b6"), depth=0.25, spec=0.7)
    for i, (x, y) in enumerate(((175, 114), (179, 112), (183, 113))):
        p.stroke([(x, y + 6), (x + 5, y + 2)], hexc("#56606e"), 1.2)
    # ---- pauldrons (back then front): dome, lame and rivets
    for box, lame in (((138, 96, 180, 132), (140, 116, 176, 138)), ((74, 98, 122, 138), (76, 120, 118, 144))):
        p.shape("chord", lame, shade(steel, 0.9), start=0, end=180, depth=0.3, spec=0.6)
        p.shape("ellipse", box, steel, depth=0.2, light=1.35, spec=1.0, tex="metal", tex_amt=0.45)
        x0, y0, x1, y1 = box
        p.stroke(curve([(x0 + 5, y0 + (y1 - y0) * 0.62), ((x0 + x1) / 2, y1 - 3), (x1 - 5, y0 + (y1 - y0) * 0.62)], 5),
                 gold, 2.2)
        rivets(p, [(x0 + 9, y0 + 18), ((x0 + x1) / 2, y1 - 8), (x1 - 9, y0 + 18)], 1.8)
    # ---- kite shield held in front: steel rim, red and white field, gold boss
    shield = [(48, 116), (114, 116), (112, 162), (81, 212), (50, 162)]
    rim = p.shape("poly", shield, hexc("#aab6c4"), depth=0.14, spec=0.9, tex="metal", tex_amt=0.5)
    inner = [(55, 122), (107, 122), (105, 160), (81, 202), (57, 160)]
    field = p.shape("poly", inner, hexc("#f2ece0"), depth=0.14, line=1.1, tex="cloth", tex_amt=0.35, rim=0)
    p.shape("rect", (72, 110, 90, 214), hexc("#c63a2f"), clip=field, line=0, depth=0.05, tex="cloth", tex_amt=0.4,
            ao=0, rim=0)
    p.stroke([(72, 122), (72, 188)], hexc("#7a2020"), 1.2)
    p.stroke([(90, 122), (90, 188)], hexc("#7a2020"), 1.2)
    p.shape("ellipse", (70, 142, 92, 164), gold, depth=0.3, light=1.45, spec=1.0)
    p.shape("ellipse", (77, 149, 85, 157), hexc("#3a8ae0"), line=0.8, gloss=1.0, rim=0)
    rivets(p, [(54, 120), (81, 119), (108, 120), (110, 146), (52, 146), (96, 180), (66, 180)], 1.9)
    for pts in (((60, 132), (66, 138)), ((98, 168), (103, 160))):
        p.stroke(list(pts), hexc("#8a8078", 180), 1.0)
    # ---- gorget and head
    p.shape("rect", (104, 98, 152, 114), shade(steel, 0.92), radius=6, depth=0.3, spec=0.6)
    p.shape("ellipse", (88, 24, 172, 108), SKIN, depth=0.12, rim=0.3)
    p.flat("ellipse", (146, 88, 160, 96), hexc("#ff7a6a", 90))  # blush
    p.flat("ellipse", (104, 88, 114, 95), hexc("#ff7a6a", 70))
    # hair tufts peeking out at the back
    p.shape("poly", [(88, 60), (80, 76), (90, 72), (86, 88), (96, 78), (98, 92), (104, 70)], hexc("#7a4a24"),
            depth=0.25, line=1.2)
    # face: two eyes (3/4 view), determined brows, smirk
    eye(p, 112, 76, 5.5, 7, hexc("#3a6ab0"), look=(1, 0))
    eye(p, 148, 76, 7, 8.5, hexc("#3a6ab0"), look=(1, 0))
    p.stroke([(103, 64), (119, 67)], hexc("#5a3418"), 3.2)
    p.stroke([(140, 67), (158, 62)], hexc("#5a3418"), 3.2)
    p.stroke(curve([(138, 97), (147, 99), (156, 94)], 5), hexc("#8a4a3a"), 2.2)
    p.stroke([(157, 93), (159, 91)], hexc("#8a4a3a"), 1.6)
    p.stroke(curve([(160, 80), (166, 87), (160, 90)], 4), shade(SKIN, 0.7), 1.8)  # nose
    # helmet: dome, brow band with rivets, nose guard, cheek guard, crest ridge
    dome = p.shape("chord", (82, 12, 178, 108), steel, start=180, end=360, depth=0.16, light=1.35, spec=1.0,
                   tex="metal", tex_amt=0.5)
    p.shape("line", curve([(90, 50), (118, 16), (150, 14), (172, 44)], 6), shade(steel, 1.12), width=6, depth=0.3,
            spec=0.6, rim=0)
    p.shape("rect", (80, 52, 180, 66), shade(steel, 0.86), radius=5, depth=0.3, spec=0.7)
    rivets(p, [(88, 59), (102, 59), (158, 59), (172, 59)], 2)
    p.shape("poly", [(123, 60), (133, 60), (134, 88), (128, 94), (122, 88)], shade(steel, 0.9), depth=0.3, spec=0.8)
    p.shape("poly", [(80, 60), (98, 60), (100, 92), (90, 100), (80, 86)], shade(steel, 0.95), depth=0.25, spec=0.6)
    rivet(p, 89, 72, 1.8)
    # plume sweeping back
    plume = hexc("#d8433a")
    p.shape("poly", curve([(124, 16), (104, 2), (80, 4), (62, 18), (66, 30), (80, 20), (100, 22), (116, 30)], 5),
            plume, depth=0.2, tex="fur", tex_amt=0.6)
    p.shape("ellipse", (112, 4, 138, 24), plume, depth=0.25)
    p.shape("rect", (118, 16, 132, 24), gold, radius=3, depth=0.3, spec=0.8)
    for pts in ([(112, 10), (92, 8), (74, 16)], [(108, 18), (88, 16), (70, 24)]):
        p.stroke(curve(pts, 4), shade(plume, 0.62), 1.6)
    return p.finish(outline=3, ground_shadow=(56, 224, 200, 248))


def cellar_rat():
    """Mangy, hunched cellar rat with a torn ear and a glowing eye (faces left)."""
    fur = hexc("#8c7468")
    belly = hexc("#c9b5a3")
    pink = hexc("#e48f98")
    p = _painter(SIZE)
    # ---- tail: long segmented curl behind the body
    tail = curve([(196, 192), (224, 190), (242, 168), (240, 140), (226, 124)], 8)
    p.shape("line", tail, pink, width=11, depth=0.3, tex="leather", tex_amt=0.5)
    p.shape("line", tail[-9:], pink, width=7, depth=0.3)
    for x, y in along(tail, 8)[1:-2]:
        p.stroke([(x - 4, y - 2), (x + 4, y + 2)], shade(pink, 0.62), 1.1)
    # ---- far hind foot and far front paw (darker, behind)
    p.shape("ellipse", (178, 200, 214, 222), shade(pink, 0.8), depth=0.3)
    p.shape("ellipse", (118, 204, 146, 222), shade(pink, 0.8), depth=0.3)
    # ---- body with a spiky, mangy back line
    body = p.union([("ellipse", (70, 106, 216, 214)),
                    ("poly", [(84, 126), (96, 98), (104, 118), (116, 92), (124, 112), (138, 90), (146, 110),
                              (160, 94), (166, 114), (182, 102), (186, 122), (202, 114), (200, 134), (214, 132),
                              (212, 150), (170, 150), (100, 150)])])
    p.paint_mask(body, fur, depth=0.12, tex="fur", tex_amt=1.0)
    p.shape("ellipse", (92, 158, 184, 214), belly, depth=0.12, line=0, tex="fur", tex_amt=0.6, rim=0, ao=0.2)
    # mange patch and an old scar with stitches
    p.shape("ellipse", (150, 124, 176, 142), shade(fur, 0.8), **NOLINE)
    p.stroke(curve([(122, 118), (136, 130), (144, 148)], 5), hexc("#d88a8a"), 3)
    for x, y in ((126, 121), (133, 129), (139, 139)):
        p.stroke([(x - 4, y + 3), (x + 4, y - 3)], hexc("#3a2a2a"), 1.3)
    # ---- near hind leg: big haunch and a clawed foot
    p.shape("ellipse", (150, 146, 210, 208), fur, depth=0.14, tex="fur", tex_amt=0.8)
    p.stroke(curve([(160, 160), (170, 178), (184, 190)], 5), shade(fur, 0.7), 1.6)
    p.shape("ellipse", (160, 202, 208, 226), pink, depth=0.25)
    for x in (164, 172, 180):
        p.shape("poly", [(x - 3, 214), (x + 2, 214), (x - 5, 226)], hexc("#f1e6d0"), line=0.8, rim=0, ao=0)
    # ---- front leg reaching forward
    p.shape("line", [(112, 164), (104, 190), (96, 206)], fur, width=18, depth=0.2, tex="fur", tex_amt=0.8)
    p.shape("ellipse", (76, 200, 116, 222), pink, depth=0.25)
    for x in (80, 88, 96):
        p.shape("poly", [(x - 1, 212), (x + 4, 212), (x - 6, 225)], hexc("#f1e6d0"), line=0.8, rim=0, ao=0)
    # ---- head: skull, snout, jaw
    head = p.union([("ellipse", (30, 92, 126, 178)),
                    ("poly", [(46, 110), (6, 136), (4, 148), (22, 160), (60, 164)])])
    p.paint_mask(head, fur, depth=0.12, tex="fur", tex_amt=0.9)
    # cheek fur tufts
    p.shape("poly", [(92, 160), (80, 176), (96, 170), (94, 184), (106, 170), (112, 180), (116, 160)], fur,
            depth=0.2, tex="fur")
    # open snarling mouth with long yellow incisors
    mouth = [(12, 152), (60, 156), (70, 164), (50, 176), (24, 170)]
    p.shape("poly", mouth, hexc("#4a1420"), depth=0.25, line=1.3, rim=0)
    p.shape("ellipse", (28, 164, 54, 176), hexc("#b04058"), **NOLINE)
    teeth(p, [(20, 150, 8, 17, 1), (29, 151, 8, 15, 1)], hexc("#f0da9a"))
    teeth(p, [(40, 173, 5, 7, -1), (48, 172, 5, 7, -1), (56, 169, 5, 6, -1)], hexc("#f4ecd4"))
    p.stroke([(34, 176), (32, 186)], hexc("#bfe6ff", 170), 1.6)  # drool
    p.flat("ellipse", (30, 184, 35, 190), hexc("#bfe6ff", 170))
    # nose with a glint, whiskers
    p.shape("ellipse", (-2, 132, 16, 148), pink, depth=0.3, light=1.35, gloss=1.0)
    for a, b in (((22, 138), (-4, 124)), ((22, 142), (-6, 140)), ((24, 146), (-2, 156)), ((30, 138), (8, 118))):
        p.stroke(curve([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 2), b], 4), hexc("#2a1e24", 200), 1.1)
    # ---- ears: far ear behind, near ear with a torn notch
    p.shape("ellipse", (84, 70, 116, 108), shade(fur, 0.85), depth=0.2)
    ear = p.union([("ellipse", (52, 58, 102, 112))])
    from PIL import ImageChops
    ear = ImageChops.subtract(ear, p._mask("poly", [(58, 62), (72, 76), (64, 58)]))
    p.paint_mask(ear, fur, depth=0.2, tex="fur", tex_amt=0.6)
    inner = ImageChops.subtract(p._mask("ellipse", (62, 68, 94, 104)), p._mask("poly", [(58, 58), (76, 80), (68, 56)]))
    p.paint_mask(inner, pink, depth=0.3, line=0, rim=0)
    # ---- eye: glowing, with a heavy angry brow
    p.glow((58, 124), 26, hexc("#ff3030"), 0.75)
    p.shape("ellipse", (46, 112, 72, 136), hexc("#2a0c10"), **NOLINE)
    p.shape("ellipse", (49, 115, 70, 134), hexc("#e3262c"), shadow=0.6, light=1.5, depth=0.3, line=0, rim=0, ao=0)
    p.flat("ellipse", (55, 119, 64, 131), hexc("#ffb040"))
    p.flat("ellipse", (52, 117, 58, 123), WHITE)
    p.shape("poly", [(40, 108), (80, 116), (78, 122), (44, 115)], shade(fur, 0.6), depth=0.3, line=1.1, rim=0)
    return p.finish(outline=3, ground_shadow=(50, 206, 232, 236))


def bone(p, a, b, width, color=BONE, knob=1.35):
    """Limb bone with knobbly joint ends."""
    p.shape("line", [a, b], color, width=width, depth=0.3, tex="bone", tex_amt=0.6, rim=0.3)
    for x, y in (a, b):
        r = width * knob / 2
        p.shape("ellipse", (x - r, y - r, x + r, y + r), color, depth=0.3, tex="bone", tex_amt=0.5, rim=0)


def skeleton_guard():
    """Rusty-helmed skeleton with a notched sword and a battered round shield (faces left)."""
    p = _painter(SIZE)
    bone_c = hexc("#e9dfc2")
    rust = hexc("#a2603a")
    iron = hexc("#7c8690")
    # ---- raised sword arm (behind the body)
    bone(p, (150, 112), (178, 136), 8, bone_c)
    bone(p, (178, 136), (186, 106), 7, bone_c)
    ux, uy, nx, ny = blade(p, (188, 98), (224, 10), 11, hexc("#b9a898"), fuller=False, spec=0.5, edge=True)
    for t, r in ((30, 4), (52, 3.2), (70, 3.5), (40, 2.4)):  # rust blotches and notches
        x, y = 188 + ux * t, 98 + uy * t
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#9a5a34", 200))
    p.shape("line", [(176, 92), (202, 104)], hexc("#6a4a32"), width=7, depth=0.35, spec=0.4)
    p.shape("line", [(188, 98), (184, 112)], hexc("#4a3226"), width=6, depth=0.3, tex="leather")
    p.shape("ellipse", (177, 96, 197, 116), bone_c, depth=0.3, tex="bone")  # bony fist
    for y in (101, 106, 111):
        p.stroke([(179, y), (186, y + 1)], shade(bone_c, 0.6), 1.1)
    # ---- legs: femur, knee, shin, rusty sabatons
    for x in (106, 138):
        bone(p, (x + 6, 176), (x + 5, 200), 10, bone_c)
        bone(p, (x + 5, 202), (x + 6, 222), 8, bone_c)
        p.shape("ellipse", (x - 3, 194, x + 15, 208), shade(rust, 1.1), depth=0.3, spec=0.5, tex="metal")
        p.shape("rect", (x - 10, 216, x + 20, 236), rust, radius=7, depth=0.25, tex="metal", tex_amt=0.9, spec=0.4)
        rivets(p, [(x - 4, 224), (x + 14, 224)], 1.6, hexc("#c8a080"))
    # ---- tattered loincloth over the pelvis
    rag = hexc("#5b4a6a")
    p.shape("poly", [(100, 164), (156, 164), (158, 186), (148, 196), (140, 188), (130, 200), (118, 188), (108, 198),
                     (98, 184)], rag, depth=0.15, tex="cloth", tex_amt=0.9)
    p.shape("rect", (96, 158, 160, 172), hexc("#5a3a26"), radius=5, depth=0.3, tex="leather")
    p.shape("rect", (121, 157, 135, 173), hexc("#8a8f96"), radius=2, depth=0.3, spec=0.6)
    # ---- spine and curved ribs
    p.shape("rect", (122, 98, 134, 162), bone_c, radius=5, depth=0.25, tex="bone")
    for y in range(102, 160, 9):
        p.stroke([(123, y), (133, y)], shade(bone_c, 0.6), 1.2)
    for i, y in enumerate((106, 120, 134, 146)):
        w = 32 - i * 4
        for side in (-1, 1):
            pts = curve([(128 + side * 4, y), (128 + side * w * 0.8, y - 2), (128 + side * w, y + 8),
                         (128 + side * w * 0.7, y + 13)], 5)
            p.shape("line", pts, bone_c, width=6.5, depth=0.3, tex="bone", tex_amt=0.5, rim=0.3)
    p.shape("line", [(128, 100), (128, 144)], bone_c, width=7, depth=0.3, tex="bone", rim=0)  # sternum
    # collarbones and shoulder knobs
    p.shape("line", [(96, 102), (160, 100)], bone_c, width=7, depth=0.3, tex="bone")
    for x in (98, 158):
        p.shape("ellipse", (x - 9, 94, x + 9, 112), bone_c, depth=0.3, tex="bone")
    # ---- skull with a crack, lower jaw, glowing eyes
    skull = p.union([("ellipse", (84, 22, 168, 100)), ("rect", (98, 80, 150, 104), {"radius": 12})])
    p.paint_mask(skull, bone_c, depth=0.14, tex="bone", tex_amt=0.8)
    p.shape("rect", (98, 96, 148, 116), bone_c, radius=9, depth=0.25, tex="bone")  # jaw
    p.shape("rect", (101, 96, 145, 106), hexc("#2a1a22"), radius=3, **NOLINE)
    for x in range(104, 146, 6):
        p.shape("rect", (x - 2.6, 95, x + 2.6, 102), hexc("#f4ecd4"), radius=1.2, line=0.7, depth=0.3, rim=0, ao=0)
        p.shape("rect", (x - 2.4, 101, x + 2.4, 107), hexc("#e6dcbc"), radius=1.2, line=0.7, depth=0.3, rim=0, ao=0)
    p.shape("poly", [(118, 80), (128, 80), (123, 91)], hexc("#2a1a22"), **NOLINE)  # nose hole
    p.shape("ellipse", (90, 48, 120, 78), hexc("#1a1018"), **NOLINE)
    p.shape("ellipse", (126, 48, 156, 78), hexc("#1a1018"), **NOLINE)
    glow_eye(p, 104, 64, 7, hexc("#ff5a28"), socket=False)
    glow_eye(p, 140, 64, 7, hexc("#ff5a28"), socket=False)
    p.stroke([(144, 30), (138, 42), (146, 50), (140, 58)], hexc("#6a5a48"), 1.6)
    p.stroke([(96, 86), (104, 90)], shade(bone_c, 0.62), 1.3)
    # ---- dented kettle helmet with a rusty brim and rivets
    helm = p.shape("chord", (78, 6, 170, 88), iron, start=180, end=360, depth=0.16, spec=0.7, tex="metal",
                   tex_amt=0.9)
    for x, y, r in ((100, 26, 5), (146, 32, 4), (122, 18, 3.5)):
        p.flat("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7), hexc("#9a5a34", 190))
    p.shape("ellipse", (70, 40, 178, 56), rust, depth=0.3, spec=0.5, tex="metal", tex_amt=0.9)
    rivets(p, [(86, 48), (106, 50), (142, 50), (162, 48)], 1.8, hexc("#c8b8a8"))
    p.stroke([(92, 22), (98, 30), (94, 36)], shade(iron, 0.6), 1.4)  # dent
    # ---- front arm and the battered round shield
    bone(p, (100, 112), (80, 138), 8, bone_c)
    shield = p.shape("ellipse", (22, 102, 102, 198), hexc("#8a5a30"), depth=0.14, tex="wood", tex_amt=1.0)
    for x in (42, 62, 82):  # planks
        p.stroke([(x, 104), (x, 196)], hexc("#4a2e1a", 200), 1.4, )
    rim = p.union([("ellipse", (22, 102, 102, 198))])
    from PIL import ImageChops
    ring = ImageChops.subtract(rim, p._mask("ellipse", (29, 110, 95, 190)))
    p.paint_mask(ring, iron, depth=0.2, spec=0.8, tex="metal", tex_amt=0.8)
    rivets(p, [(62, 106), (62, 194), (26, 150), (98, 150), (36, 120), (88, 120), (36, 180), (88, 180)], 1.7)
    p.shape("ellipse", (48, 136, 76, 164), iron, depth=0.3, light=1.4, spec=1.0, tex="metal")
    rivet(p, 62, 150, 2.6)
    # a big crack and an arrow stub in the shield
    p.stroke([(40, 116), (52, 130), (46, 140), (56, 150)], hexc("#2a1810"), 2.2)
    p.shape("line", [(82, 170), (96, 162)], hexc("#6a4a2a"), width=3, depth=0.3, line=1)
    p.shape("poly", [(96, 158), (104, 158), (100, 166)], hexc("#e0e0e0"), line=0.9, depth=0.3)
    return p.finish(outline=3, ground_shadow=(36, 222, 204, 246))


def mushroom_mage():
    """Mischievous mushroom wizard in a mossy robe with a glowing spore staff (faces left)."""
    cap = hexc("#8a48c4")
    stem = hexc("#f1e3c6")
    robe = hexc("#4f6b3c")
    spore = hexc("#8dff6a")
    p = _painter(SIZE)
    # ---- mossy robe body with a belt and pouches
    p.shape("poly", curve([(96, 116), (170, 116), (184, 170), (196, 226), (160, 232), (130, 226), (96, 232),
                           (66, 226), (80, 170)], 5), robe, depth=0.12, tex="cloth", tex_amt=0.9)
    for pts in ([(110, 150), (100, 196), (96, 226)], [(150, 150), (160, 196), (166, 226)], [(130, 170), (130, 224)]):
        p.stroke(curve(pts, 5), shade(robe, 0.62), 2)
    p.shape("rect", (66, 214, 196, 234), shade(cap, 0.75), radius=8, depth=0.3, tex="cloth")
    stitches(p, [(72, 220), (190, 220)], hexc("#e6c8ff", 200), step=6, length=3)
    for x, y in ((80, 210), (112, 222), (170, 214)):  # moss clumps on the hem
        p.shape("ellipse", (x - 8, y - 5, x + 8, y + 5), hexc("#6f9a3e"), depth=0.3, tex="fur", line=1.0)
    p.shape("rect", (82, 170, 182, 182), hexc("#6a4428"), radius=4, depth=0.3, tex="leather")
    p.shape("ellipse", (122, 168, 138, 184), GOLD, depth=0.3, spec=1.0)
    p.shape("rect", (150, 176, 168, 196), hexc("#8a5a32"), radius=4, depth=0.25, tex="leather")
    p.shape("chord", (149, 172, 169, 186), hexc("#7a4a2a"), start=0, end=180, depth=0.3, line=1.0)
    # little mushrooms sprouting at the feet
    for x, y, s, c in ((188, 232, 1.0, "#e0503a"), (200, 234, 0.7, "#f0a040"), (58, 234, 0.8, "#e0503a")):
        p.shape("rect", (x - 2.5 * s, y - 12 * s, x + 2.5 * s, y), stem, radius=2, line=1.0, depth=0.3)
        p.shape("chord", (x - 9 * s, y - 20 * s, x + 9 * s, y - 4 * s), hexc(c), start=180, end=360, line=1.1)
        p.flat("ellipse", (x - 4 * s, y - 16 * s, x - 1 * s, y - 13 * s), hexc("#fff4e0"))
    # ---- stem face under the cap
    face = p.shape("ellipse", (92, 88, 172, 170), stem, depth=0.14, tex="bone", tex_amt=0.5)
    p.flat("ellipse", (98, 140, 112, 150), hexc("#ff8a9a", 110))
    p.flat("ellipse", (146, 140, 160, 150), hexc("#ff8a9a", 110))
    eye(p, 112, 126, 7, 8.5, hexc("#6a3aa8"), look=(-1, 0.2), lid=0.3, skin=stem)
    eye(p, 146, 126, 6, 7.5, hexc("#6a3aa8"), look=(-1, 0.2), lid=0.3, skin=stem)
    p.stroke([(102, 110), (120, 114)], hexc("#6a4a3a"), 2.6)  # sly brows
    p.stroke([(140, 114), (156, 108)], hexc("#6a4a3a"), 2.6)
    p.shape("chord", (108, 146, 140, 166), hexc("#4a1a2a"), start=0, end=180, depth=0.3, line=1.2, rim=0)
    p.flat("ellipse", (116, 156, 130, 164), hexc("#d06070"))
    p.shape("rect", (126, 153, 132, 158), WHITE, radius=1, line=0.6, rim=0, ao=0)  # snaggle tooth
    # ---- the cap: gills underneath, spotted dome with glowing spots
    p.shape("ellipse", (38, 88, 224, 116), hexc("#d8b8c8"), depth=0.3, rim=0)
    for x in range(48, 220, 7):
        p.stroke([(x, 102), (131 + (x - 131) * 0.6, 110)], hexc("#a88898"), 1.1)
    capm = p.shape("chord", (32, 16, 230, 188), cap, start=180, end=360, depth=0.12, light=1.3, spec=0.3,
                   tex="leather", tex_amt=0.5)
    p.shape("ellipse", (30, 86, 232, 106), shade(cap, 0.72), depth=0.35, rim=0)
    spots = ((66, 40, 98, 64), (122, 26, 158, 52), (180, 50, 206, 72), (100, 68, 120, 84), (44, 70, 62, 86),
             (206, 78, 222, 90), (158, 72, 174, 86))
    for i, box in enumerate(spots):
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        if i % 3 == 0:
            p.glow((cx, cy), (box[2] - box[0]) * 0.9, spore, 0.45)
        p.shape("ellipse", box, hexc("#f4e0ff") if i % 3 else hexc("#d8ffc8"), depth=0.25, line=1.1, light=1.3,
                rim=0, ao=0.2)
    # ---- arm and staff with a glowing spore orb
    p.shape("line", curve([(52, 134), (58, 180), (54, 236)], 6), hexc("#6b4428"), width=8, depth=0.3, tex="wood")
    p.shape("line", curve([(40, 110), (44, 124), (52, 136), (60, 126)], 5), hexc("#6b4428"), width=5, depth=0.3,
            tex="wood")  # twisted crook
    p.shape("line", [(96, 150), (70, 168)], robe, width=16, depth=0.2, tex="cloth")
    p.shape("ellipse", (60, 158, 82, 180), stem, depth=0.25)
    p.stroke([(64, 166), (76, 164)], shade(stem, 0.6), 1.2)
    p.glow((36, 104), 44, spore, 0.8)
    p.shape("ellipse", (18, 86, 54, 122), hexc("#7de35a"), depth=0.25, light=1.5, gloss=1.0, rim=0.2)
    p.flat("ellipse", (28, 96, 44, 112), hexc("#d8ffc0", 170))
    for x, y, r in ((18, 70, 3.5), (58, 80, 2.5), (10, 124, 2.5), (40, 60, 2), (74, 98, 2), (200, 30, 2.5),
                    (226, 60, 2), (12, 96, 2)):
        p.glow((x, y), r * 3.2, spore, 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8ffd8"))
    return p.finish(outline=3, ground_shadow=(46, 222, 214, 246))


def cellar_warden():
    """Elite jailer: hooded brute with chains, a key ring and a huge bearded axe (faces left)."""
    hood = hexc("#452636")
    apron = hexc("#6e4a31")
    skin = hexc("#c9a086")
    iron = hexc("#7d8792")
    p = _painter(SIZE)
    # ---- legs and heavy boots
    for x in (104, 146):
        p.shape("rect", (x, 184, x + 26, 226), hexc("#4a3a3a"), radius=8, tex="cloth", tex_amt=0.8)
        p.shape("rect", (x - 8, 214, x + 32, 240), hexc("#3a2a26"), radius=8, tex="leather", tex_amt=0.8)
        p.shape("rect", (x - 6, 212, x + 30, 220), hexc("#5a4234"), radius=4, depth=0.3, tex="leather")
        rivets(p, [(x - 2, 216), (x + 12, 216), (x + 26, 216)], 1.5, hexc("#a8a8a8"))
    # ---- back arm with a studded bracer
    p.shape("line", [(196, 110), (216, 158), (202, 190)], skin, width=22, depth=0.18, tex="leather", tex_amt=0.4)
    p.shape("rect", (192, 146, 224, 172), hexc("#4a3226"), radius=5, depth=0.25, tex="leather")
    rivets(p, [(200, 152), (216, 152), (200, 166), (216, 166)], 1.6)
    p.shape("ellipse", (190, 180, 216, 204), skin, depth=0.25)
    # ---- hulking torso, hairy belly, stained apron
    p.shape("ellipse", (68, 74, 216, 208), skin, depth=0.1, tex="leather", tex_amt=0.4)
    for x, y in ((104, 110), (120, 118), (100, 126), (170, 112), (182, 124)):
        p.stroke([(x, y), (x - 2, y + 5)], shade(skin, 0.55), 1.1)
    ap = [(92, 120), (192, 120), (204, 214), (84, 214)]
    p.shape("poly", ap, apron, depth=0.12, tex="leather", tex_amt=1.0)
    stitches(p, [(96, 126), (88, 208)], hexc("#c8a078"), step=6)
    stitches(p, [(188, 126), (198, 208)], hexc("#c8a078"), step=6)
    for x, y, r in ((120, 190, 9), (170, 140, 6), (150, 200, 5)):  # dark stains
        p.flat("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7), hexc("#3a1a14", 110))
    p.shape("rect", (78, 158, 208, 176), hexc("#3a2a20"), radius=5, depth=0.3, tex="leather")
    p.shape("rect", (132, 154, 156, 180), hexc("#9aa2aa"), radius=3, depth=0.3, spec=0.9)
    p.shape("rect", (138, 160, 150, 174), hexc("#3a2a20"), radius=2, **NOLINE)
    # key ring hanging from the belt
    from PIL import ImageChops
    ring = ImageChops.subtract(p._mask("ellipse", (164, 170, 192, 198)), p._mask("ellipse", (168, 174, 188, 194)))
    p.paint_mask(ring, GOLD, depth=0.3, line=1.0, spec=0.8, rim=0)
    for x, y, a in ((168, 192, 0), (180, 196, 1), (190, 190, 2)):
        p.shape("rect", (x, y, x + 6, y + 20), GOLD, radius=2, line=1.0, spec=0.7, rim=0)
        p.shape("rect", (x + 3, y + 14, x + 9, y + 18), GOLD, radius=1, line=0.8, rim=0)
        p.shape("ellipse", (x - 2, y - 4, x + 8, y + 5), GOLD, line=1.0, rim=0)
    # chains across the chest
    chain(p, (84, 88), (196, 150), 13, iron, 12)
    # ---- hood with a peak, seam and shadowed face
    hm = p.union([("poly", [(94, 20), (172, 26), (186, 108), (80, 108)]), ("ellipse", (86, 14, 180, 88)),
                  ("poly", [(130, 20), (152, -2), (164, 30)])])
    p.paint_mask(hm, hood, depth=0.1, tex="cloth", tex_amt=1.0)
    stitches(p, [(150, 4), (140, 30), (138, 60)], hexc("#8a6a7a"), step=6)
    p.shape("ellipse", (94, 38, 162, 100), hexc("#1c1018"), depth=0.2, line=1.0, rim=0)
    p.shape("rect", (98, 34, 118, 42), shade(hood, 0.7), radius=2, **NOLINE)
    glow_eye(p, 112, 58, 7, hexc("#ffc02a"), socket=False)
    glow_eye(p, 144, 58, 7, hexc("#ffc02a"), socket=False)
    p.stroke([(100, 48), (122, 54)], hexc("#0c0608"), 3.2)  # scowl
    p.stroke([(134, 54), (156, 48)], hexc("#0c0608"), 3.2)
    p.shape("rect", (108, 78, 150, 90), hexc("#3a1a20"), radius=4, **NOLINE)  # gritted teeth
    for x in range(111, 148, 6):
        p.shape("rect", (x, 79, x + 5, 89), hexc("#e0d4b0"), radius=1, line=0.6, depth=0.3, rim=0, ao=0)
    # ---- the huge bearded axe held in front
    p.shape("line", [(152, 216), (56, 30)], hexc("#6b4428"), width=11, depth=0.3, tex="wood")
    for t in (0.55, 0.62, 0.69):
        x, y = 152 + (56 - 152) * t, 216 + (30 - 216) * t
        p.stroke([(x - 6, y + 2), (x + 6, y - 4)], hexc("#2a1a10"), 1.6)
    head = [(66, 28), (40, 14), (10, 12), (0, 50), (8, 90), (28, 104), (40, 76), (74, 62)]
    p.shape("poly", curve(head, 4), iron, depth=0.2, light=1.35, spec=1.0, tex="metal", tex_amt=0.9)
    p.shape("poly", curve([(10, 12), (0, 50), (8, 90), (28, 104), (16, 60)], 4), hexc("#dfe7ee"), depth=0.3,
            line=0, shadow=0, rim=0, ao=0)
    for x, y, r in ((44, 40, 5), (54, 58, 3.5), (30, 80, 4)):
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#9a5a34", 200))
    p.shape("rect", (50, 24, 80, 68), hexc("#5a4a44"), radius=4, depth=0.3, tex="metal")
    rivets(p, [(58, 34), (70, 38), (60, 56), (72, 58)], 1.7)
    p.sparkle((12, 30), 6)
    # ---- front arm gripping the haft
    p.shape("line", [(92, 108), (70, 148), (104, 150)], skin, width=22, depth=0.18, tex="leather", tex_amt=0.4)
    p.shape("rect", (58, 132, 90, 158), hexc("#4a3226"), radius=5, depth=0.25, tex="leather")
    rivets(p, [(66, 138), (82, 138), (66, 152), (82, 152)], 1.6)
    p.shape("ellipse", (94, 134, 126, 166), skin, depth=0.22)
    for y in (142, 150, 158):
        p.stroke([(98, y), (110, y - 1)], shade(skin, 0.55), 1.4)
    return p.finish(outline=3, ground_shadow=(36, 224, 232, 250))


def mimic():
    """Treasure chest with teeth, a lolling tongue and slit eyes (faces left)."""
    wood = hexc("#a0652f")
    band = hexc("#8a939e")
    gold = hexc("#f0bf48")
    mouth = hexc("#5a1624")
    p = _painter(SIZE)
    # spilled coins and a gem
    for x, y in ((18, 222), (40, 230), (204, 228), (224, 218), (190, 236)):
        p.shape("ellipse", (x, y, x + 20, y + 12), gold, line=1.1, depth=0.3, spec=0.9, rim=0)
        p.stroke([(x + 5, y + 6), (x + 15, y + 6)], shade(gold, 0.7), 1.1)
    p.shape("poly", [(232, 232), (242, 226), (250, 234), (242, 242)], hexc("#3ad0ff"), line=1.0, gloss=1.0, rim=0)
    # ---- base of the chest: planks, iron bands, gold corners, lock
    base = p.shape("rect", (40, 140, 220, 232), wood, radius=10, depth=0.1, tex="wood_h", tex_amt=1.0)
    for y in (170, 200):
        p.stroke([(42, y), (218, y)], shade(wood, 0.55), 1.6)
    for x in (58, 196):
        p.shape("rect", (x - 7, 140, x + 12, 232), band, radius=3, depth=0.2, spec=0.6, tex="metal")
        rivets(p, [(x + 2.5, 156), (x + 2.5, 186), (x + 2.5, 216)], 1.8)
    for x0, x1 in ((40, 62), (198, 220)):
        p.shape("poly", [(x0, 212), (x1, 232), (x0, 232)] if x0 < 100 else [(x1, 212), (x0, 232), (x1, 232)], gold,
                depth=0.3, spec=0.8, line=1.1)
    p.shape("rect", (112, 164, 150, 204), gold, radius=6, depth=0.25, light=1.4, spec=1.0)
    p.shape("ellipse", (125, 174, 137, 186), DARK, **NOLINE)
    p.shape("poly", [(128, 182), (134, 182), (135, 196), (127, 196)], DARK, **NOLINE)
    # ---- open maw inside the lid
    p.shape("poly", [(40, 146), (220, 146), (212, 70), (52, 42)], mouth, depth=0.08, tex="leather", tex_amt=0.6)
    p.stroke(curve([(84, 96), (130, 104), (176, 104)], 6), hexc("#2a0a12", 150), 26, soft=2.5)
    for x, y in ((90, 70), (150, 84)):  # saliva strands
        p.stroke(curve([(x, y), (x + 3, y + 30), (x - 2, y + 56)], 5), hexc("#ffc0d0", 150), 1.4)
    teeth(p, [(48 + i * 21 + 9, 148, 18, -24, 1) for i in range(8)], hexc("#f4ecd4"), 1.2)
    # ---- lid tilted open toward the back, with bands and a gold trim
    lid = [(40, 40), (212, 66), (226, 28), (68, 0)]
    p.shape("poly", lid, wood, depth=0.12, tex="wood_h", tex_amt=1.0)
    p.shape("line", [(40, 40), (212, 66)], gold, width=5, depth=0.3, spec=0.8, rim=0)
    for x0 in (96, 172):
        p.shape("poly", [(x0, 10 + (x0 - 96) * 0.17), (x0 + 22, 13 + (x0 - 96) * 0.17), (x0 + 10, 50 + (x0 - 96) * 0.16),
                         (x0 - 12, 47 + (x0 - 96) * 0.16)], band, depth=0.2, line=1.2, spec=0.7, tex="metal")
    # upper teeth hanging from the lid
    for i in range(7):
        x0 = 52 + i * 23
        y0 = 43 + i * 3.6
        p.shape("poly", [(x0, y0), (x0 + 20, y0 + 3), (x0 + 12, y0 + 32)], hexc("#f4ecd4"), line=1.2, depth=0.25,
                rim=0, ao=0.3)
    # ---- tongue lolling out over the front edge
    tongue = hexc("#e0607a")
    tpts = [(150, 128), (100, 138), (62, 162), (48, 198)]
    p.shape("line", tpts, tongue, width=30, depth=0.2, light=1.35, gloss=0.6, tex="leather", tex_amt=0.5)
    p.stroke(curve([(116, 136), (70, 164), (52, 196)], 6), shade(tongue, 0.62), 3)
    p.flat("ellipse", (40, 206, 50, 222), hexc("#ffb0c4", 200))  # drip
    # ---- eyes on the lid: yellow slits with angry lids
    for cx in (110, 170):
        dy = (cx - 110) * 0.14
        p.glow((cx, 25 + dy), 20, hexc("#ffe040"), 0.45)
        p.shape("ellipse", (cx - 16, 12 + dy, cx + 14, 38 + dy), hexc("#ffe14a"), light=1.5, depth=0.25, rim=0)
        p.flat("rect", (cx - 3, 14 + dy, cx + 3, 36 + dy), DARK, radius=2)
        p.flat("ellipse", (cx - 11, 16 + dy, cx - 5, 22 + dy), WHITE)
        p.shape("poly", [(cx - 18, 8 + dy), (cx + 16, 18 + dy), (cx + 16, 12 + dy), (cx - 18, 4 + dy)], wood,
                depth=0.3, line=1.2, rim=0)
    return p.finish(outline=3, ground_shadow=(24, 222, 240, 250))


BOSS_SIZE = 384


def bone_king():
    """Boss: skeleton king with crown, embroidered royal robe and a necrotic staff (faces left)."""
    robe = hexc("#5b2a86")
    trim = hexc("#f4efe6")
    glow = hexc("#6dffcf")
    gold = hexc("#f1c24a")
    bone_c = hexc("#ece3c8")
    p = _painter(BOSS_SIZE)
    # ---- spectral wisps rising behind
    for x, y, r in ((300, 120, 40), (330, 200, 30), (140, 110, 28)):
        p.glow((x, y), r, glow, 0.25)
    # ---- tattered cape
    cape = [(150, 120), (330, 130), (362, 350), (322, 330), (304, 362), (264, 334), (232, 364), (200, 336), (166, 358)]
    p.shape("poly", cape, shade(robe, 0.72), depth=0.06, tex="cloth", tex_amt=0.5)
    for pts in ([(250, 150), (280, 250), (300, 340)], [(290, 150), (320, 240), (340, 330)]):
        p.stroke(curve(pts, 6), shade(robe, 0.45), 3)
    for x, y in ((316, 318), (262, 322), (206, 326)):  # rips
        p.shape("poly", [(x - 6, y + 8), (x, y - 8), (x + 6, y + 8)], hexc("#1c1024"), **NOLINE)
    # ---- robe body with gold embroidery and a central panel
    p.shape("poly", [(146, 140), (262, 140), (300, 356), (112, 356)], robe, depth=0.08, tex="cloth", tex_amt=0.5)
    p.shape("poly", [(186, 140), (222, 140), (236, 340), (172, 340)], shade(robe, 0.8), depth=0.1, line=1.2,
            tex="cloth", rim=0)
    p.stroke([(186, 142), (172, 338)], gold, 3)
    p.stroke([(222, 142), (236, 338)], gold, 3)
    for y in range(250, 336, 22):  # embroidered diamonds down the panel
        w = 7 + (y - 250) * 0.04
        p.shape("poly", [(204, y - 8), (204 + w, y), (204, y + 8), (204 - w, y)], gold, line=0.9, depth=0.3,
                spec=0.6, rim=0)
    for pts in ([(160, 200), (140, 350)], [(250, 200), (280, 350)]):
        p.stroke(curve(pts, 4), shade(robe, 0.55), 2.5)
    # hem: ermine band with ermine spots
    p.shape("rect", (108, 334, 304, 364), trim, radius=10, depth=0.25, tex="fur", tex_amt=0.8)
    for x in (130, 166, 202, 238, 274):
        p.shape("poly", [(x, 342), (x + 4, 350), (x, 358), (x - 4, 350)], DARK, **NOLINE)
    # ---- ribcage peeking out
    p.shape("poly", [(170, 150), (238, 150), (226, 232), (182, 232)], hexc("#24142e"), line=1.2, rim=0)
    p.shape("rect", (200, 150, 208, 230), bone_c, radius=3, depth=0.3, tex="bone", line=1.0)
    for i, y in enumerate((162, 180, 198, 214)):
        w = 28 - i * 4
        for side in (-1, 1):
            pts = curve([(204 + side * 3, y), (204 + side * w, y + 2), (204 + side * (w - 4), y + 10)], 4)
            p.shape("line", pts, bone_c, width=6, depth=0.3, line=1.1, tex="bone", rim=0)
    p.glow((204, 196), 30, glow, 0.35)  # the soul-light inside
    # ---- ermine collar
    p.shape("ellipse", (124, 116, 288, 172), trim, depth=0.15, tex="fur", tex_amt=0.9)
    for x, y in ((148, 142), (188, 152), (230, 152), (266, 140)):
        p.shape("poly", [(x, y - 5), (x + 4, y + 2), (x, y + 9), (x - 4, y + 2)], DARK, **NOLINE)
    p.shape("ellipse", (196, 146, 214, 164), gold, depth=0.3, spec=1.0)  # clasp
    p.shape("ellipse", (200, 150, 210, 160), hexc("#e0303a"), line=0.8, gloss=1.0, rim=0)
    # ---- back arm: bony hand on the hip
    bone(p, (272, 162), (298, 212), 12, bone_c)
    bone(p, (298, 212), (272, 238), 11, bone_c)
    p.shape("ellipse", (256, 228, 280, 250), bone_c, depth=0.3, tex="bone")
    # ---- skull with cracks, jaw and burning eyes
    skull = p.union([("ellipse", (134, 28, 258, 144)), ("rect", (156, 112, 232, 150), {"radius": 12})])
    p.paint_mask(skull, bone_c, depth=0.13, tex="bone", tex_amt=0.9)
    p.shape("rect", (158, 142, 230, 166), bone_c, radius=10, depth=0.25, tex="bone")
    p.shape("rect", (162, 138, 226, 150), hexc("#2a1a22"), radius=3, **NOLINE)
    for x in range(166, 224, 8):
        p.shape("rect", (x - 3.4, 136, x + 3.4, 145), hexc("#f4ecd4"), radius=1.5, line=0.8, depth=0.3, rim=0, ao=0)
        p.shape("rect", (x - 3.2, 145, x + 3.2, 154), hexc("#e6dcbc"), radius=1.5, line=0.8, depth=0.3, rim=0, ao=0)
    p.shape("poly", [(184, 110), (198, 110), (191, 126)], hexc("#2a1a22"), **NOLINE)
    p.shape("ellipse", (144, 68, 184, 108), hexc("#140c14"), **NOLINE)
    p.shape("ellipse", (196, 68, 236, 108), hexc("#140c14"), **NOLINE)
    glow_eye(p, 165, 88, 10, glow, hexc("#effff8"), socket=False)
    glow_eye(p, 215, 88, 10, glow, hexc("#effff8"), socket=False)
    p.stroke([(140, 60), (180, 74)], hexc("#6a5a48"), 3)  # stern brow ridges
    p.stroke([(240, 60), (200, 74)], hexc("#6a5a48"), 3)
    p.stroke([(186, 46), (196, 60), (188, 70), (194, 80)], hexc("#6a5a48"), 2.2)
    p.stroke([(236, 110), (244, 120), (240, 128)], hexc("#6a5a48"), 1.8)
    # ---- crown with gems
    crown = [(130, 52), (130, 6), (152, 30), (172, 0), (192, 28), (212, 0), (232, 30), (254, 6), (258, 52)]
    p.shape("poly", crown, gold, depth=0.15, light=1.4, spec=1.0, tex="metal", tex_amt=0.5)
    for x, y in ((130, 6), (172, 0), (212, 0), (254, 6)):
        p.shape("ellipse", (x - 5, y - 5, x + 5, y + 5), gold, depth=0.3, gloss=0.9, rim=0)
    p.shape("rect", (128, 38, 260, 56), hexc("#d49a2a"), radius=4, depth=0.3, spec=0.6)
    for x, c in ((148, "#e0303a"), (186, "#3ad0ff"), (224, "#e0303a")):
        p.shape("ellipse", (x, 39, x + 16, 55), hexc(c), light=1.6, line=1.2, gloss=1.0, rim=0)
    p.sparkle((150, 26), 7)
    # ---- necrotic staff with a skull orb and green flame
    p.shape("line", curve([(78, 110), (90, 230), (104, 360)], 6), hexc("#4a3226"), width=12, depth=0.3, tex="wood")
    staff = curve([(78, 110), (90, 230), (104, 360)], 6)
    for i, (x, y) in enumerate(along(staff, 50)[1:4]):
        p.shape("rect", (x - 8, y - 4, x + 8, y + 4), hexc("#e7b440"), radius=2, depth=0.3, line=1.1, spec=0.7, rim=0)
    p.shape("line", [(56, 96), (100, 88)], hexc("#e7b440"), width=7, depth=0.3, spec=0.8)
    p.glow((78, 60), 70, glow, 0.85)
    flame = curve([(52, 60), (54, 30), (64, 12), (68, 26), (78, 0), (88, 22), (96, 8), (104, 32), (106, 60)], 5)
    p.shape("poly", flame, hexc("#5affc0", 210), depth=0.2, light=1.4, line=1.2, ink=hexc("#1f6a50"), rim=0, ao=0)
    p.shape("poly", curve([(64, 60), (68, 36), (78, 18), (88, 36), (94, 60)], 5), hexc("#d8fff0", 220), **NOLINE)
    orb = p.shape("ellipse", (48, 32, 108, 94), hexc("#b9ffe8"), light=1.3, depth=0.14, gloss=0.9, rim=0.2)
    p.shape("ellipse", (58, 54, 74, 70), hexc("#1f5a4a"), **NOLINE)
    p.shape("ellipse", (82, 54, 98, 70), hexc("#1f5a4a"), **NOLINE)
    p.shape("poly", [(76, 72), (80, 72), (78, 78)], hexc("#1f5a4a"), **NOLINE)
    for x in range(64, 94, 6):
        p.stroke([(x, 82), (x, 88)], hexc("#1f5a4a"), 1.6)
    # ---- front arm in a puffed sleeve, bony hand with rings
    p.shape("line", [(150, 170), (116, 214), (96, 190)], robe, width=28, depth=0.18, tex="cloth")
    p.shape("line", [(122, 212), (104, 196)], trim, width=16, depth=0.25, tex="fur", rim=0)
    p.shape("ellipse", (78, 174, 114, 206), bone_c, depth=0.25, tex="bone")
    for i, y in enumerate((180, 190, 200)):
        p.shape("line", [(82, y), (70, y + 4)], bone_c, width=6.5, line=1.2, depth=0.3, rim=0)
        if i != 1:
            p.shape("rect", (76, y - 3.5, 81, y + 4.5), gold, radius=1.5, line=0.8, spec=0.8, rim=0)
    return p.finish(outline=3, ground_shadow=(70, 340, 350, 378))


# ------------------------------------------------------------------ shared helpers for the new sprites

def star_pts(cx, cy, r, inner=0.45, n=5, rot=-90):
    """Points of an n-pointed star."""
    pts = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else r * inner
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def flame(p, cx, base, w, h, lean=0.0, glow=True, colors=("#e8401e", "#ff9a2a", "#ffe98a"), strength=0.7):
    """Layered cartoon flame standing on (cx, base), `w` wide and `h` tall, tip leaning by `lean` * h."""
    if glow:
        p.glow((cx + lean * h * 0.4, base - h * 0.4), max(w, h) * 0.95, hexc(colors[1]), strength)
    for i, (col, s) in enumerate(zip(colors, (1.0, 0.68, 0.38))):
        ww, hh = w * s, h * (0.95 if i == 0 else 0.9 * s + 0.1)
        tip = (cx + lean * h * (0.9 - i * 0.15), base - hh)
        pts = curve([(cx - ww / 2, base - ww * 0.3), (cx - ww * 0.45, base - hh * 0.45),
                     (cx - ww * 0.12 + lean * hh * 0.3, base - hh * 0.72), tip,
                     (cx + ww * 0.28 + lean * hh * 0.4, base - hh * 0.62), (cx + ww * 0.5, base - hh * 0.35),
                     (cx + ww * 0.4, base - ww * 0.05), (cx, base + ww * 0.12), (cx - ww * 0.4, base - ww * 0.05)], 5)
        if i == 0:
            p.shape("poly", pts, hexc(col), depth=0.2, light=1.3, line=1.1, ink=hexc("#7a1a0a"), rim=0, ao=0)
        else:
            p.shape("poly", pts, hexc(col), **NOLINE)


def ember(p, x, y, r, color=hexc("#ff9a2a"), core=hexc("#fff0b0")):
    p.glow((x, y), r * 3.4, color, 0.75)
    p.flat("ellipse", (x - r, y - r, x + r, y + r), core)


def snow(p, x, y, r, color=hexc("#eaf6ff")):
    p.glow((x, y), r * 2.8, hexc("#9ad8ff"), 0.45)
    p.flat("ellipse", (x - r, y - r, x + r, y + r), color)


def puff(p, x, y, r, color, alpha=200, line=1.0, ink=None):
    """Round cloud puff of smoke, spores or frost breath."""
    col = color[:3] + (alpha,)
    p.shape("ellipse", (x - r, y - r * 0.86, x + r, y + r * 0.86), col, shadow=0.86, light=1.15, depth=0.3,
            line=line, ink=ink or shade(color, 0.5)[:3] + (int(alpha * 0.7),), rim=0, ao=0)


def shard(p, cx, cy, w, h, angle=0.0, color=hexc("#bfeaff"), line=1.2, glow=None, facet=True):
    """Pointed crystal (a stretched diamond) centred on (cx, cy), rotated by `angle` degrees."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def rot(x, y):
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)
    pts = [rot(0, -h / 2), rot(w / 2, -h * 0.12), rot(w * 0.3, h / 2), rot(-w * 0.3, h / 2), rot(-w / 2, -h * 0.12)]
    if glow:
        p.glow((cx, cy), max(w, h) * 0.9, glow, 0.45)
    p.shape("poly", pts, color, depth=0.3, light=1.45, line=line, spec=0.9, rim=0, ao=0.25,
            ink=mix(hexc("#1a2a5a"), color, 0.2))
    if facet:
        p.stroke([rot(0, -h / 2 + 1), rot(-w * 0.08, h * 0.1), rot(-w * 0.22, h / 2 - 1)], hexc("#ffffff", 170),
                 max(1.0, w * 0.1))
    return pts


def scale_rows(p, clip, box, color, size=9, line=0.7):
    """Overlapping scale pattern (downward half-discs) clipped to a mask."""
    x0, y0, x1, y1 = box
    for row, y in enumerate(range(int(y0), int(y1) + size, int(size * 0.7))):
        for x in range(int(x0) - size + (row % 2) * size // 2, int(x1) + size, size):
            p.shape("chord", (x - size / 2, y - size / 2, x + size / 2, y + size / 2), color, start=0, end=180,
                    line=line, light=1.35, shadow=0.7, depth=0.4, rim=0, ao=0, clip=clip)


def wing(p, shoulder, tips, membrane, bone_c, width=7, edge=None, glow=None, scallop=0.22):
    """Bat or dragon wing: arm bones from `shoulder` through tips[0] (the wrist) out to the finger tips,
    with a scalloped membrane between the fingers."""
    wrist = tips[0]
    fingers = tips[1:]
    from PIL import ImageChops
    mem = p._mask("poly", [shoulder, wrist, fingers[0]] + [shoulder])
    prev = fingers[0]
    edge_pts = [fingers[0]]
    for f in fingers[1:]:
        mx, my = (prev[0] + f[0]) / 2, (prev[1] + f[1]) / 2
        # scallop: pull the midpoint toward the wrist
        sx = mx + (wrist[0] - mx) * scallop
        sy = my + (wrist[1] - my) * scallop
        edge_pts += [(sx, sy), f]
        prev = f
    last = fingers[-1]
    body = (shoulder[0] + (last[0] - shoulder[0]) * 0.1, shoulder[1] + (last[1] - shoulder[1]) * 0.35)
    poly = [shoulder, wrist] + curve(edge_pts, 5) + [body]
    mem = p._mask("poly", poly)
    p.paint_mask(mem, membrane, depth=0.08, light=1.25, tex="leather", tex_amt=0.5)
    if glow:
        for x, y in along(curve(edge_pts, 5), 9):
            p.glow((x, y), 11, glow, 0.35)
    if edge:
        p.stroke(curve(edge_pts, 5), edge, 2.4)
    # bones
    p.shape("line", [shoulder, wrist], bone_c, width=width, depth=0.3, light=1.3, rim=0.3)
    for f in fingers:
        p.shape("line", [wrist, f], bone_c, width=width * 0.45, depth=0.3, line=1.1, rim=0)
    p.shape("ellipse", (wrist[0] - width * 0.7, wrist[1] - width * 0.7, wrist[0] + width * 0.7, wrist[1] + width * 0.7),
            bone_c, depth=0.3, line=1.1, rim=0)
    p.shape("poly", [(wrist[0] - width * 0.4, wrist[1]), (wrist[0] + width * 0.4, wrist[1]),
                     (wrist[0] - width * 0.6, wrist[1] - width * 1.8)], hexc("#f0e6cc"), line=1.0, rim=0, ao=0)
    return mem


# ------------------------------------------------------------------ player: mage and rogue

def mage():
    """Büyücü: young mage in a starry blue robe and floppy hat, with a fire-crystal staff (faces right)."""
    p = _painter(SIZE)
    robe = hexc("#2c48aa")
    robe_d = hexc("#1f2f78")
    gold = hexc("#f0bb45")
    hair = hexc("#8a4a24")
    fire = hexc("#ff8a2a")
    # ---- short back cape
    cape = curve([(106, 106), (90, 134), (76, 170), (66, 196), (84, 190), (96, 200), (110, 186), (126, 150),
                  (142, 110)], 6)
    p.shape("poly", cape, robe_d, depth=0.12, tex="cloth", tex_amt=0.6)
    p.stroke(curve([(66, 196), (84, 190), (96, 200), (110, 186)], 5), gold, 2.2)
    p.stroke(curve([(100, 128), (86, 164), (78, 186)], 5), shade(robe_d, 0.6), 2)
    # ---- shoes under the hem
    for x0 in (102, 136):
        p.shape("rect", (x0, 222, x0 + 30, 238), hexc("#6e4127"), radius=7, depth=0.25, tex="leather")
        p.shape("ellipse", (x0 + 18, 222, x0 + 34, 236), hexc("#6e4127"), depth=0.3, rim=0)
    # ---- the long robe with gold trim and embroidered stars
    rp = curve([(106, 104), (154, 104), (162, 150), (172, 196), (180, 228), (156, 232), (130, 228), (104, 232),
                (80, 228), (90, 194), (98, 150)], 6)
    rm = p.shape("poly", rp, robe, depth=0.12, tex="cloth", tex_amt=0.7)
    for pts in ([(112, 164), (104, 198), (98, 226)], [(152, 166), (160, 198), (166, 226)]):
        p.stroke(curve(pts, 5), shade(robe, 0.62), 2)
    p.shape("line", curve([(82, 224), (104, 227), (130, 223), (156, 227), (178, 224)], 6), gold, width=5,
            depth=0.35, spec=0.6, rim=0, clip=None)
    p.shape("line", [(136, 112), (138, 224)], gold, width=5, depth=0.35, spec=0.6, rim=0)
    for x, y, r in ((110, 186, 5), (156, 200, 4.5), (120, 212, 3.5), (100, 206, 3), (160, 176, 3), (148, 214, 3)):
        p.shape("poly", star_pts(x, y, r, 0.45), hexc("#ffe28a"), line=0.8, depth=0.3, light=1.4, rim=0, ao=0,
                clip=rm)
    for x, y in ((122, 196), (106, 172), (162, 212), (150, 184)):
        p.flat("ellipse", (x - 1.4, y - 1.4, x + 1.4, y + 1.4), hexc("#cfe0ff"))
    # ---- belt with a buckle, a scroll case and a little book
    p.shape("rect", (96, 148, 164, 160), hexc("#6a3f24"), radius=4, depth=0.3, tex="leather")
    p.shape("ellipse", (128, 146, 144, 162), gold, depth=0.3, light=1.45, spec=1.0)
    p.shape("ellipse", (132, 150, 140, 158), hexc("#e0503a"), line=0.8, gloss=1.0, rim=0)
    p.shape("rect", (98, 156, 116, 178), hexc("#8a3a2a"), radius=3, depth=0.25, tex="leather")
    p.shape("rect", (100, 158, 114, 162), gold, radius=1, line=0.7, rim=0)
    # ---- back arm reaching out, a fire and ice spark dancing over the palm
    p.shape("poly", curve([(108, 108), (92, 118), (72, 140), (64, 152), (80, 158), (96, 140), (116, 124)], 5), robe,
            depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(66, 150), (78, 157)], gold, width=6, depth=0.3, spec=0.5, rim=0)
    p.shape("ellipse", (50, 144, 72, 160), SKIN, depth=0.25)
    for x in (54, 60, 66):
        p.stroke([(x, 146), (x - 1, 142)], shade(SKIN, 0.7), 1.2)
    p.glow((58, 120), 34, fire, 0.6)
    flame(p, 58, 134, 16, 26, lean=-0.1, glow=False)
    p.glow((40, 108), 14, hexc("#7ad8ff"), 0.7)
    for a in range(0, 180, 60):
        r = math.radians(a)
        p.stroke([(40 - 6 * math.cos(r), 108 - 6 * math.sin(r)), (40 + 6 * math.cos(r), 108 + 6 * math.sin(r))],
                 hexc("#eaf8ff"), 1.8)
    p.flat("ellipse", (38, 106, 42, 110), WHITE)
    p.stroke(curve([(72, 102), (60, 96), (46, 100), (40, 108)], 5), hexc("#ffd08a", 150), 1.4)
    p.stroke(curve([(40, 116), (46, 128), (56, 136)], 5), hexc("#bfeaff", 150), 1.4)
    # ---- front sleeve (the hand is drawn over the staff later)
    p.shape("poly", curve([(150, 112), (166, 116), (184, 132), (190, 150), (172, 156), (160, 140), (146, 124)], 5),
            robe, depth=0.2, tex="cloth", tex_amt=0.6)
    # ---- mantle over the shoulders with a gold edge and a clasp
    p.shape("chord", (86, 90, 170, 140), robe_d, start=0, end=180, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("ellipse", (86, 96, 170, 124), robe_d, depth=0.18, tex="cloth", tex_amt=0.6)
    p.stroke(curve([(90, 116), (110, 128), (128, 132), (148, 128), (166, 116)], 5), gold, 2.4)
    p.shape("ellipse", (134, 110, 148, 124), gold, depth=0.3, light=1.45, spec=1.0)
    p.shape("poly", star_pts(141, 117, 4, 0.45), hexc("#fff4c0"), **NOLINE)
    # ---- head: hair at the back, face, fringe
    p.shape("poly", [(94, 64), (84, 86), (94, 82), (90, 100), (102, 90), (104, 104), (112, 80)], hair, depth=0.25,
            line=1.2, tex="fur", tex_amt=0.4)
    p.shape("ellipse", (94, 42, 168, 118), SKIN, depth=0.12, rim=0.3)
    p.flat("ellipse", (146, 96, 160, 104), hexc("#ff7a6a", 90))
    p.flat("ellipse", (104, 96, 114, 103), hexc("#ff7a6a", 70))
    eye(p, 116, 88, 5.5, 7, hexc("#c86a1a"), look=(1, -0.1))
    eye(p, 148, 88, 7, 8.5, hexc("#c86a1a"), look=(1, -0.1))
    p.stroke([(108, 76), (122, 77)], hair, 3)
    p.stroke([(140, 77), (156, 74)], hair, 3)
    p.stroke(curve([(134, 101), (142, 105), (152, 102)], 4), hexc("#7a2a2a"), 2.2)
    p.stroke([(152, 102), (154, 99)], hexc("#7a2a2a"), 1.6)
    p.stroke(curve([(162, 86), (168, 94), (162, 97)], 4), shade(SKIN, 0.7), 1.8)
    p.shape("poly", curve([(96, 66), (110, 60), (130, 60), (152, 60), (166, 66), (158, 76), (148, 70),
                           (140, 78), (130, 70), (120, 78), (112, 70), (100, 78)], 4), hair, depth=0.25,
            line=1.2, tex="fur", tex_amt=0.4)
    # ---- the floppy pointed hat: cone, drooping tip with a star, brim and band
    cone = curve([(96, 58), (112, 36), (124, 18), (138, 8), (148, 24), (158, 44), (166, 58)], 5)
    p.shape("poly", cone, robe, depth=0.14, light=1.3, tex="cloth", tex_amt=0.7)
    tip = curve([(126, 22), (130, 6), (118, 0), (100, 4), (84, 16), (78, 30), (88, 24), (104, 16), (120, 18),
                 (136, 16)], 5)
    p.shape("poly", tip, robe, depth=0.2, tex="cloth", tex_amt=0.7)
    p.shape("ellipse", (72, 28, 88, 44), gold, depth=0.3, light=1.4, gloss=0.8, rim=0)
    p.shape("poly", star_pts(80, 36, 5.5, 0.45), hexc("#fff4b0"), line=0.8, rim=0, ao=0)
    for x, y, r in ((122, 40, 4.5), (146, 30, 3.5), (104, 10, 3)):
        p.shape("poly", star_pts(x, y, r, 0.45), hexc("#ffe28a"), line=0.8, depth=0.3, rim=0, ao=0)
    p.shape("rect", (96, 50, 166, 60), gold, radius=3, depth=0.3, light=1.4, spec=0.8)
    brim = p._mask("ellipse", (70, 54, 190, 76))
    p.shadow_on(brim, strength=0.45, offset=2.5, blur=3)
    p.paint_mask(brim, robe, depth=0.2, light=1.3, tex="cloth", tex_amt=0.6)
    p.stroke(curve([(74, 66), (100, 74), (130, 76), (160, 74), (186, 66)], 5), shade(robe, 0.6), 1.6)
    # ---- staff with a claw head holding a fire crystal
    p.shape("line", curve([(198, 238), (192, 140), (184, 50)], 6), WOOD, width=8, depth=0.3, tex="wood")
    for y in (118, 176):
        x = 198 - (238 - y) * 0.07
        p.shape("rect", (x - 7, y - 3.5, x + 5, y + 3.5), gold, radius=2, depth=0.3, line=1.0, spec=0.7, rim=0)
    p.glow((182, 34), 48, fire, 0.8)
    for pts in ([(184, 52), (170, 44), (168, 26)], [(184, 52), (196, 42), (198, 24)], [(184, 52), (184, 40)]):
        p.shape("line", curve(pts, 4), WOOD, width=5, depth=0.3, line=1.2, rim=0)
    p.shape("poly", [(182, 10), (194, 30), (184, 50), (170, 30)], hexc("#ff9a2a"), depth=0.25, light=1.55,
            line=1.3, ink=hexc("#7a2a0a"), gloss=0.9, rim=0)
    p.shape("poly", [(182, 16), (188, 30), (182, 42), (177, 30)], hexc("#ffe07a"), **NOLINE)
    p.sparkle((176, 20), 6)
    for x, y, r in ((202, 16, 2.2), (164, 12, 1.8), (206, 44, 1.6)):
        ember(p, x, y, r)
    # ---- front arm: wide sleeve with a gold cuff, hand gripping the staff
    p.shape("line", [(172, 154), (190, 146)], gold, width=6, depth=0.3, spec=0.5, rim=0)
    p.shape("ellipse", (180, 128, 202, 150), SKIN, depth=0.25)
    for y in (134, 140, 146):
        p.stroke([(184, y), (196, y - 1)], shade(SKIN, 0.62), 1.3)
    return p.finish(outline=3, ground_shadow=(58, 224, 214, 248))


def rogue():
    """Haydut: lean rogue in a green hooded cloak and leathers, masked, with two daggers (faces right)."""
    p = _painter(SIZE)
    cloak = hexc("#2f6a44")
    cloak_d = hexc("#1f4430")
    leather = hexc("#7a4a2a")
    dark = hexc("#3a3440")
    mask_c = hexc("#2a3a34")
    # ---- cloak billowing behind, ragged hem
    cm = curve([(110, 98), (92, 124), (72, 160), (52, 196), (46, 214), (62, 206), (70, 218), (82, 204), (94, 214),
                (104, 196), (116, 204), (124, 150), (146, 102)], 6)
    p.shape("poly", cm, cloak_d, depth=0.12, tex="cloth", tex_amt=0.7)
    for pts in ([(100, 124), (80, 170), (62, 204)], [(112, 134), (100, 180), (90, 208)]):
        p.stroke(curve(pts, 5), shade(cloak_d, 0.55), 2)
    # ---- legs apart in a low stance, wrapped boots
    p.shape("line", [(114, 170), (104, 198), (100, 222)], dark, width=18, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(140, 170), (156, 196), (164, 220)], dark, width=18, depth=0.2, tex="cloth", tex_amt=0.6)
    for x0, x1, top in ((86, 116, 206), (150, 184, 204)):
        p.shape("rect", (x0 + 4, top, x1 - 4, 232), hexc("#5a3a24"), radius=6, depth=0.25, tex="leather")
        p.shape("rect", (x0, 222, x1 + 4, 238), hexc("#4a2e1c"), radius=7, depth=0.25, tex="leather")
        for y in (210, 216):
            p.stroke([(x0 + 5, y), (x1 - 5, y + 3)], hexc("#c8a078"), 1.6)
    # ---- leather jerkin with panels, a cross strap and stitching
    body = curve([(104, 104), (152, 104), (160, 140), (158, 176), (98, 176), (96, 140)], 5)
    p.shape("poly", body, leather, depth=0.14, tex="leather", tex_amt=0.9)
    stitches(p, [(128, 108), (128, 170)], hexc("#d0a878"), step=5, length=2.4, width=1)
    for y in (132, 148):
        p.stroke([(100, y), (156, y)], shade(leather, 0.6), 1.4)
    p.shape("line", [(106, 108), (152, 168)], hexc("#4a2e1c"), width=7, depth=0.3, tex="leather", rim=0)
    for t in (0.35, 0.55, 0.75):  # throwing knives tucked in the strap
        x, y = 106 + 46 * t, 108 + 60 * t
        p.shape("poly", [(x - 2, y - 2), (x + 3, y - 3), (x + 5, y - 12), (x - 1, y - 12)], STEEL, line=0.9,
                depth=0.3, spec=0.8, rim=0)
    # ---- belt: buckle, pouches and a green poison vial
    p.shape("rect", (94, 164, 162, 176), hexc("#4a2e1c"), radius=4, depth=0.3, tex="leather")
    p.shape("rect", (122, 162, 136, 178), hexc("#b0b8c0"), radius=2, depth=0.3, spec=0.9)
    p.shape("rect", (126, 166, 132, 174), hexc("#4a2e1c"), radius=1, **NOLINE)
    for x0 in (98, 140):
        p.shape("rect", (x0, 172, x0 + 16, 190), hexc("#8a5a32"), radius=4, depth=0.25, tex="leather")
        p.shape("chord", (x0 - 1, 168, x0 + 17, 182), hexc("#6e4127"), start=0, end=180, depth=0.3, line=1.0)
        rivet(p, x0 + 8, 178, 1.4, GOLD)
    p.glow((162, 192), 18, hexc("#6aff5a"), 0.6)
    p.shape("rect", (160, 174, 166, 182), hexc("#a07040"), radius=1, line=0.8, rim=0)
    p.shape("ellipse", (154, 180, 172, 200), hexc("#5ae84a", 230), depth=0.25, light=1.5, gloss=1.0, rim=0,
            ink=hexc("#1a4a1a"))
    p.flat("ellipse", (158, 186, 170, 198), hexc("#b8ff9a", 150))
    # ---- back arm with a reversed-grip dagger
    p.shape("line", [(106, 110), (92, 134), (86, 150)], cloak, width=15, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(92, 136), (86, 150)], leather, width=13, depth=0.3, tex="leather", rim=0)
    blade(p, (78, 160), (58, 206), 9, hexc("#d8e2ec"), fuller=False)
    p.shape("line", [(70, 156), (90, 164)], hexc("#3a3a44"), width=5, depth=0.3, spec=0.6, rim=0)
    p.shape("ellipse", (76, 142, 94, 162), SKIN, depth=0.25)
    p.shape("ellipse", (82, 136, 90, 144), hexc("#3a3a44"), line=1.0, depth=0.3, spec=0.6, rim=0)
    # ---- capelet over the shoulders
    p.shape("ellipse", (88, 94, 168, 132), cloak, depth=0.18, tex="cloth", tex_amt=0.7)
    for x in (104, 122, 140, 156):
        p.stroke([(x, 110), (x - 2, 128)], shade(cloak, 0.6), 1.4)
    # ---- hood and masked face
    hood = p.union([("ellipse", (86, 26, 172, 118)),
                    ("poly", curve([(100, 34), (80, 34), (62, 46), (58, 62), (76, 54), (92, 60)], 4))])
    p.paint_mask(hood, cloak, depth=0.12, tex="cloth", tex_amt=0.8)
    stitches(p, [(64, 54), (86, 42), (110, 32), (130, 28)], hexc("#8ac09a", 180), step=6)
    p.shape("ellipse", (106, 48, 170, 114), hexc("#142018"), depth=0.2, line=1.0, rim=0)
    p.shape("ellipse", (112, 54, 168, 112), SKIN, depth=0.14, rim=0.2)
    p.shadow_on(p._mask("chord", (100, 34, 176, 76), start=180, end=360), strength=0.4, offset=3, blur=3)
    eye(p, 126, 80, 5, 6.5, hexc("#3ac08a"), look=(1, 0))
    eye(p, 152, 80, 6.5, 7.5, hexc("#3ac08a"), look=(1, 0))
    p.stroke([(118, 68), (132, 72)], hexc("#3a2418"), 3)
    p.stroke([(144, 72), (160, 67)], hexc("#3a2418"), 3)
    # dark hair strands falling from the hood edge
    p.shape("poly", [(108, 56), (140, 50), (170, 60), (160, 66), (150, 60), (146, 70), (134, 58), (124, 70),
                     (118, 60), (110, 68)], hexc("#3a2418"), depth=0.25, line=1.1, tex="fur", tex_amt=0.4)
    # face mask over the nose and mouth, with folds
    p.shape("poly", curve([(110, 90), (140, 86), (172, 88), (170, 104), (158, 116), (132, 118), (114, 108)], 5),
            mask_c, depth=0.2, tex="cloth", tex_amt=0.7, clip=None)
    for pts in ([(118, 100), (144, 104), (166, 98)], [(124, 110), (146, 112), (160, 108)]):
        p.stroke(curve(pts, 4), shade(mask_c, 0.55), 1.4)
    p.stroke(curve([(160, 90), (168, 96)], 3), shade(mask_c, 1.4), 1.4)
    # ---- front arm: bracer and a forward dagger
    p.shape("line", [(150, 110), (164, 134), (184, 132)], cloak, width=15, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(166, 136), (182, 132)], leather, width=13, depth=0.3, tex="leather", rim=0)
    stitches(p, [(168, 130), (180, 128)], hexc("#d0a878"), step=4, length=2, width=1)
    blade(p, (194, 124), (238, 82), 10, hexc("#dfe8f0"))
    p.shape("line", [(186, 116), (200, 132)], hexc("#3a3a44"), width=5, depth=0.3, spec=0.6, rim=0)
    p.shape("ellipse", (180, 122, 198, 142), SKIN, depth=0.25)
    for y in (128, 134):
        p.stroke([(182, y), (194, y - 2)], shade(SKIN, 0.62), 1.2)
    p.sparkle((226, 94), 5)
    return p.finish(outline=3, ground_shadow=(46, 222, 210, 248))


def taper(pts, w0, w1, steps=8):
    """Outline polygon of a curve through pts whose width goes from w0 to w1 (tentacles, tails, necks)."""
    c = curve(pts, steps) if len(pts) > 2 else list(pts)
    n = len(c)
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = (w0 + (w1 - w0) * i / max(1, n - 1)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def drop(p, x, y, r, color, line=1.0):
    """Falling teardrop with its tip at the top."""
    p.shape("poly", curve([(x, y - r * 2.2), (x + r * 0.7, y - r * 0.6), (x + r, y + r * 0.2), (x, y + r),
                           (x - r, y + r * 0.2), (x - r * 0.7, y - r * 0.6)], 4) + [(x, y - r * 2.2)], color,
            depth=0.3, light=1.4, line=line, gloss=0.8, rim=0, ao=0)


def bubble(p, x, y, r, color=hexc("#c8ffb0", 110), ink=hexc("#2a8a3a", 200)):
    p.shape("ellipse", (x - r, y - r, x + r, y + r), color, shadow=0, light=0, line=1.0, ink=ink, rim=0, ao=0)
    p.flat("ellipse", (x - r * 0.6, y - r * 0.62, x - r * 0.08, y - r * 0.12), hexc("#ffffff", 220))


# ------------------------------------------------------------------ dungeon 2: Mantar Mağarası

def cave_slime():
    """Translucent green slime with a swallowed bone, bubbles and a dumb happy grin (faces left)."""
    p = _painter(SIZE)
    slime = hexc("#6ad65a")
    ink = hexc("#1f5a2a")
    # ---- acid puddle it sits in
    p.shape("ellipse", (18, 214, 238, 246), hexc("#8ae85a", 210), shadow=0.8, light=1.3, depth=0.3, line=1.2, rim=0,
            ao=0, ink=ink)
    p.glow((128, 160), 116, slime, 0.3)
    # ---- the blob, with a soft-serve curl on top
    body = p.union([("ellipse", (30, 84, 226, 234)), ("rect", (26, 160, 230, 234), {"radius": 36}),
                    ("poly", curve([(96, 96), (112, 64), (128, 46), (144, 40), (150, 52), (140, 58), (150, 76),
                                    (170, 96)], 5))])
    p.paint_mask(body, slime[:3] + (238,), depth=0.1, light=1.3, rim=0.6, gloss=0.9)
    p.flat("ellipse", (70, 136, 210, 228), hexc("#2f9a4a", 70))
    p.flat("ellipse", (90, 150, 190, 214), hexc("#1f7a3a", 50))
    # ---- swallowed bone and a coin, seen through the jelly
    bone(p, (136, 196), (196, 170), 12, hexc("#d8e8b0"))
    p.shape("ellipse", (170, 206, 190, 218), hexc("#e8d060"), line=1.0, depth=0.3, rim=0)
    p.flat("ellipse", (120, 156, 212, 226), hexc("#6ad65a", 110))
    for x, y, r in ((164, 110, 9), (192, 140, 6), (54, 196, 7), (100, 214, 5), (208, 186, 5), (150, 144, 4),
                    (122, 90, 4)):
        bubble(p, x, y, r)
    # glossy highlights
    p.flat("ellipse", (52, 100, 86, 122), hexc("#ffffff", 150))
    p.flat("ellipse", (92, 92, 100, 100), hexc("#ffffff", 170))
    p.flat("ellipse", (124, 54, 132, 62), hexc("#ffffff", 170))
    # ---- goofy face
    eye(p, 76, 128, 13, 15, hexc("#2a6a2a"), look=(-0.7, 0.45), skin=slime)
    eye(p, 122, 120, 10, 12, hexc("#2a6a2a"), look=(0.3, -0.5), skin=slime)
    mouth = p.shape("chord", (52, 140, 140, 198), hexc("#1f5a2a"), start=0, end=180, depth=0.2, line=1.4, rim=0)
    p.shape("ellipse", (78, 174, 122, 204), hexc("#ff7a8a"), **NOLINE, clip=mouth)
    p.shape("rect", (84, 168, 96, 178), WHITE, radius=2, line=0.9, rim=0, ao=0)
    p.flat("ellipse", (52, 160, 64, 170), hexc("#ff8a8a", 90))
    p.flat("ellipse", (126, 150, 138, 160), hexc("#ff8a8a", 70))
    # ---- acid drips and sizzle
    for x, y, r in ((62, 204, 5), (48, 226, 3.5), (200, 214, 4), (226, 206, 3)):
        drop(p, x, y, r, hexc("#b8ff5a", 230))
    for x, y in ((30, 212), (236, 224), (120, 238)):
        bubble(p, x, y, 3)
    return p.finish(outline=3, ground_shadow=(20, 222, 236, 250))


def toxic_toad():
    """Fat purple-green toad with glowing warts, a long tongue and poison drool (faces left)."""
    p = _painter(SIZE)
    purple = hexc("#7a4aa0")
    green = hexc("#7fb84a")
    belly = hexc("#dfe89a")
    wart = hexc("#ffd84a")
    pink = hexc("#f07a9a")
    poison = hexc("#9aff4a")
    # ---- poison puddle and the far hind foot
    p.shape("ellipse", (0, 222, 90, 244), hexc("#8ae84a", 200), shadow=0.8, light=1.3, depth=0.3, line=1.1, rim=0,
            ao=0)
    p.shape("ellipse", (184, 196, 236, 236), shade(purple, 0.8), depth=0.25, tex="leather")
    # ---- body and head as one squat blob
    bm = p.union([("ellipse", (56, 88, 230, 226)), ("ellipse", (18, 94, 150, 202))])
    p.paint_mask(bm, purple, depth=0.1, light=1.28, tex="leather", tex_amt=0.8, gloss=0.3)
    for box in ((150, 104, 196, 136), (190, 140, 222, 172), (96, 96, 128, 118), (120, 136, 150, 156)):
        p.shape("ellipse", box, green, depth=0.3, line=0.9, rim=0, ao=0, clip=bm, tex="leather", tex_amt=0.6)
    p.shape("ellipse", (24, 150, 168, 236), belly, depth=0.2, line=1.0, rim=0, clip=bm, tex="leather", tex_amt=0.5)
    for x in (64, 84, 104, 124):
        p.stroke([(x, 196), (x + 3, 214)], shade(belly, 0.75), 1.4)
    # glowing warts
    for x, y, r in ((136, 100, 6), (172, 96, 5), (204, 120, 6), (160, 128, 4.5), (214, 152, 4.5), (110, 118, 4),
                    (186, 158, 5), (90, 104, 3.5)):
        p.glow((x, y), r * 3.2, wart, 0.55)
        p.shape("ellipse", (x - r, y - r, x + r, y + r), wart, depth=0.3, light=1.5, line=1.0, rim=0, ao=0.2)
        p.flat("ellipse", (x - r * 0.5, y - r * 0.5, x, y), hexc("#fffbe0"))
    # ---- near hind leg: big haunch and a webbed foot
    p.shape("ellipse", (146, 146, 224, 222), purple, depth=0.14, tex="leather", tex_amt=0.8)
    p.shape("ellipse", (170, 160, 200, 184), green, depth=0.3, line=0.9, rim=0, ao=0)
    p.shape("poly", curve([(146, 214), (130, 226), (138, 238), (160, 232), (178, 240), (196, 230), (200, 214)], 4),
            green, depth=0.25, tex="leather")
    # ---- front leg with a webbed hand
    p.shape("line", [(80, 172), (70, 208), (66, 222)], purple, width=20, depth=0.2, tex="leather")
    p.shape("poly", curve([(52, 216), (34, 226), (42, 238), (62, 232), (80, 240), (92, 228), (84, 214)], 4), green,
            depth=0.25, tex="leather")
    # ---- throat sac and wide mouth
    p.shape("ellipse", (46, 164, 106, 200), shade(belly, 1.08), depth=0.2, line=1.1, rim=0, gloss=0.6)
    p.shape("poly", curve([(16, 146), (50, 158), (96, 158), (134, 144), (132, 150), (96, 166), (50, 166),
                           (18, 154)], 5), hexc("#3a1440"), depth=0.3, line=1.2, rim=0)
    p.stroke(curve([(22, 142), (50, 152), (96, 152), (132, 140)], 5), shade(purple, 1.3), 1.6)
    p.flat("ellipse", (26, 124, 32, 130), hexc("#2a1030"))
    p.flat("ellipse", (40, 122, 46, 128), hexc("#2a1030"))
    # long tongue flopping out of the mouth
    p.shape("poly", taper([(40, 158), (18, 170), (6, 190), (16, 208)], 15, 11), pink, depth=0.25, light=1.35,
            gloss=0.6)
    p.shape("ellipse", (4, 196, 34, 222), pink, depth=0.25, light=1.35, gloss=0.8)
    p.stroke(curve([(34, 162), (16, 176), (12, 196)], 4), shade(pink, 0.6), 2)
    # poison drool
    p.shape("line", [(52, 164), (50, 190), (54, 214)], hexc("#9aff4a", 220), width=5, depth=0.3, line=1.0, rim=0)
    drop(p, 56, 222, 4, hexc("#b8ff6a", 230))
    p.glow((52, 200), 26, poison, 0.4)
    # ---- bulging eyes with slit pupils and heavy lids
    for cx, cy, r in ((50, 92, 22), (110, 86, 18)):
        p.shape("ellipse", (cx - r, cy - r, cx + r, cy + r * 0.9), purple, depth=0.2, tex="leather", tex_amt=0.6)
        er = r * 0.72
        p.shape("ellipse", (cx - er, cy - er * 0.9, cx + er, cy + er * 0.8), hexc("#ffcf3a"), light=1.5, depth=0.25,
                line=1.0, rim=0)
        p.flat("rect", (cx - er * 0.8, cy - 2.5, cx + er * 0.5, cy + 2.5), DARK, radius=2)
        p.flat("ellipse", (cx - er * 0.6, cy - er * 0.7, cx - er * 0.2, cy - er * 0.3), WHITE)
        p.shape("chord", (cx - r - 1, cy - r - 2, cx + r + 1, cy + r * 0.4), purple, start=180, end=360, depth=0.3,
                line=1.2, rim=0, tex="leather")
    return p.finish(outline=3, ground_shadow=(14, 218, 240, 248))


def glow_bat():
    """Cave bat with glowing cyan wing membranes, huge ears and fangs (faces left)."""
    p = _painter(SIZE)
    fur = hexc("#3c3558")
    mem = hexc("#23b8c8")
    glowc = hexc("#5affff")
    p.glow((128, 110), 124, glowc, 0.22)
    for sh, pts in (((152, 104), [(198, 56), (252, 38), (248, 98), (222, 138), (172, 142)]),
                    ((106, 106), [(60, 56), (4, 40), (6, 100), (34, 140), (86, 144)])):
        wing(p, sh, pts, mem, fur, width=8, edge=hexc("#aaffff", 220))
    # bioluminescent spots on the membranes
    for x, y, r in ((30, 72, 3.5), (44, 104, 3), (70, 124, 2.5), (20, 92, 2), (220, 70, 3.5), (212, 104, 3),
                    (188, 124, 2.5), (234, 88, 2)):
        p.glow((x, y), r * 4, glowc, 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8ffff"))
    # ---- body, feet and tail stub
    for x in (116, 140):
        p.shape("line", [(x, 158), (x - 2, 172)], shade(fur, 0.8), width=5, depth=0.3, line=1.1, rim=0)
        for dx in (-4, 0, 4):
            p.stroke([(x - 2 + dx, 172), (x - 3 + dx, 178)], hexc("#e8e0d0"), 1.4)
    p.shape("ellipse", (98, 86, 162, 166), fur, depth=0.14, tex="fur", tex_amt=0.9)
    p.shape("ellipse", (110, 112, 152, 162), shade(fur, 1.3), depth=0.2, line=0, tex="fur", rim=0, ao=0)
    for x, y in ((122, 128), (138, 140), (128, 152)):
        p.glow((x, y), 8, glowc, 0.6)
        p.flat("ellipse", (x - 1.8, y - 1.8, x + 1.8, y + 1.8), hexc("#e8ffff"))
    # ---- ears with glowing insides
    for pts, inner in (([(84, 80), (58, 12), (108, 60)], [(86, 70), (66, 24), (100, 60)]),
                       ([(116, 64), (130, 6), (148, 74)], [(122, 62), (130, 20), (142, 68)])):
        p.shape("poly", curve(pts, 3) + [pts[-1]], fur, depth=0.2, tex="fur", tex_amt=0.6)
        p.glow(((inner[0][0] + inner[1][0]) / 2, (inner[0][1] + inner[1][1]) / 2), 18, glowc, 0.5)
        p.shape("poly", inner, hexc("#7af0f0"), depth=0.3, light=1.4, line=0.9, rim=0, ao=0)
    # ---- head: glowing eyes, leaf nose and a fanged grin
    p.shape("ellipse", (76, 58, 150, 128), fur, depth=0.14, tex="fur", tex_amt=0.9)
    p.shape("ellipse", (78, 88, 128, 126), shade(fur, 1.25), depth=0.2, line=0, rim=0, ao=0, tex="fur")
    glow_eye(p, 98, 86, 8, glowc, hexc("#f0ffff"))
    glow_eye(p, 130, 84, 6.5, glowc, hexc("#f0ffff"))
    p.stroke([(86, 72), (106, 80)], hexc("#1a1428"), 3)
    p.stroke([(122, 78), (138, 72)], hexc("#1a1428"), 3)
    p.shape("poly", [(90, 94), (100, 96), (96, 108), (88, 106)], hexc("#c87a9a"), depth=0.3, line=1.0, rim=0)
    p.shape("chord", (80, 100, 124, 126), hexc("#5a1a30"), start=0, end=180, depth=0.25, line=1.2, rim=0)
    teeth(p, [(90, 112, 6, 11, 1), (114, 111, 6, 10, 1)], hexc("#f4f0e0"))
    p.flat("ellipse", (98, 118, 108, 124), hexc("#e06a8a"))
    return p.finish(outline=3, ground_shadow=(76, 226, 184, 246))


def shroom_brute():
    """Elite: hulking mushroom giant with a red spotted cap, mossy arms and a log club (faces left)."""
    p = _painter(SIZE)
    cap = hexc("#d8382e")
    stem = hexc("#efdcbc")
    moss = hexc("#5f9a3a")
    bark = hexc("#7a5030")

    def moss_clump(x, y, w, h):
        p.shape("ellipse", (x - w / 2, y - h / 2, x + w / 2, y + h / 2), moss, depth=0.3, line=1.0, tex="fur",
                tex_amt=0.9, rim=0)
    # ---- back arm hanging, huge fist
    p.shape("line", [(184, 124), (222, 168), (214, 200)], stem, width=32, depth=0.18, tex="bone", tex_amt=0.5)
    for x, y in ((206, 146), (220, 170)):
        moss_clump(x, y, 26, 16)
    p.shape("ellipse", (190, 188, 236, 230), shade(stem, 0.94), depth=0.2, tex="bone")
    for y in (198, 208, 218):
        p.stroke([(196, y), (212, y - 2)], shade(stem, 0.6), 1.6)
    # ---- stumpy root legs
    for x in (82, 132):
        p.shape("rect", (x, 192, x + 42, 234), shade(stem, 0.88), radius=10, depth=0.2, tex="bone")
        for dx in (-4, 12, 30):
            p.shape("poly", [(x + dx, 226), (x + dx + 16, 226), (x + dx + 4, 240)], hexc("#b89a7a"), line=1.0,
                    depth=0.3, rim=0)
    # ---- barrel stem body with a vine belt
    p.shape("ellipse", (56, 94, 204, 222), stem, depth=0.1, tex="bone", tex_amt=0.7)
    for pts in ([(100, 150), (96, 200)], [(160, 150), (166, 200)], [(130, 180), (130, 214)]):
        p.stroke(pts, shade(stem, 0.78), 1.6)
    p.shape("line", curve([(60, 200), (130, 208), (202, 194)], 6), hexc("#3f7a34"), width=8, depth=0.3, rim=0)
    for x, y in ((88, 204), (150, 206), (184, 198)):
        p.shape("ellipse", (x - 8, y - 2, x + 8, y + 10), hexc("#6ab04a"), depth=0.3, line=1.0, rim=0)
    p.glow((170, 212), 16, hexc("#8dff6a"), 0.6)
    p.shape("rect", (167, 204, 173, 218), hexc("#f4ecd8"), radius=2, line=0.9, rim=0)
    p.shape("chord", (160, 196, 180, 212), hexc("#8dff6a"), start=180, end=360, line=1.0, light=1.5, rim=0)
    # ---- grumpy face in the cap's shadow
    glow_eye(p, 102, 144, 7.5, hexc("#ffd23a"))
    glow_eye(p, 150, 142, 6.5, hexc("#ffd23a"))
    p.shape("poly", [(84, 128), (118, 138), (116, 145), (82, 136)], hexc("#6a4a3a"), depth=0.3, line=1.1, rim=0)
    p.shape("poly", [(136, 138), (166, 128), (168, 136), (138, 145)], hexc("#6a4a3a"), depth=0.3, line=1.1, rim=0)
    p.shape("ellipse", (116, 146, 136, 164), shade(stem, 0.92), depth=0.3, line=1.2, rim=0)
    mouth = [(92, 180), (112, 170), (144, 170), (164, 178), (152, 188), (104, 190)]
    p.shape("poly", mouth, hexc("#3a1a1a"), depth=0.25, line=1.3, rim=0)
    teeth(p, [(106, 184, 9, -12, 1), (150, 182, 9, -12, 1)], hexc("#f4ecd4"))
    teeth(p, [(122, 171, 8, 8, 1), (136, 171, 8, 8, 1)], hexc("#f4ecd4"))
    # ---- the cap: gills, spotted dome, moss and tiny sprouts
    p.shape("ellipse", (12, 96, 244, 126), hexc("#e8c8b0"), depth=0.3, rim=0)
    for x in range(22, 240, 7):
        p.stroke([(x, 110), (128 + (x - 128) * 0.7, 120)], hexc("#b8907a"), 1.1)
    capm = p.shape("chord", (10, 2, 246, 214), cap, start=180, end=360, depth=0.12, light=1.3, spec=0.4,
                   tex="leather", tex_amt=0.5)
    p.shape("ellipse", (8, 94, 248, 116), shade(cap, 0.72), depth=0.35, rim=0)
    p.shadow_on(p._mask("ellipse", (12, 96, 244, 126)), strength=0.5, offset=3, blur=4)
    for box in ((40, 44, 76, 70), (104, 14, 150, 40), (178, 34, 214, 60), (84, 66, 106, 84), (26, 78, 44, 92),
                (212, 74, 232, 90), (150, 60, 174, 78), (126, 44, 140, 54)):
        p.shape("ellipse", box, hexc("#fbf2e0"), depth=0.25, line=1.1, light=1.3, rim=0, ao=0.2, clip=capm)
    for x, y, w in ((70, 36, 30), (184, 30, 24)):
        moss_clump(x, y, w, 12)
    for x, y, s in ((86, 30, 1.1), (168, 26, 0.9)):
        p.shape("rect", (x - 2 * s, y - 10 * s, x + 2 * s, y), stem, radius=1, line=0.9, depth=0.3, rim=0)
        p.shape("chord", (x - 7 * s, y - 16 * s, x + 7 * s, y - 4 * s), hexc("#f0a040"), start=180, end=360,
                line=1.0, rim=0)
    # ---- front arm clutching a log club
    club = taper([(84, 238), (60, 150), (36, 52)], 20, 38)
    p.shape("poly", club, bark, depth=0.14, tex="wood", tex_amt=1.0)
    p.shape("ellipse", (16, 36, 56, 60), hexc("#c89a60"), depth=0.25, line=1.3, rim=0)
    for r in (14, 9, 4):
        p.shape("ellipse", (36 - r, 48 - r * 0.6, 36 + r, 48 + r * 0.6), (0, 0, 0, 0), shadow=0, light=0, line=0.9,
                ink=hexc("#7a5030"), rim=0, ao=0)
    p.shape("line", [(46, 100), (22, 88)], bark, width=8, depth=0.3, tex="wood", rim=0)
    p.shape("ellipse", (8, 78, 26, 92), hexc("#6ab04a"), depth=0.3, line=1.0, rim=0)
    for x, y in ((50, 70), (60, 120), (42, 88)):
        p.stroke([(x, y), (x + 3, y + 10)], shade(bark, 0.5), 1.4)
    p.shape("line", [(76, 150), (66, 180), (58, 180)], stem, width=32, depth=0.18, tex="bone", tex_amt=0.5)
    moss_clump(78, 156, 30, 18)
    moss_clump(64, 178, 22, 14)
    p.shape("ellipse", (32, 160, 76, 200), shade(stem, 0.96), depth=0.2, tex="bone")
    for y in (170, 180, 190):
        p.stroke([(38, y), (54, y - 2)], shade(stem, 0.6), 1.6)
    return p.finish(outline=3, ground_shadow=(28, 222, 240, 250))


def spore_mother():
    """Boss: the Spore Mother, a towering sleepy mushroom queen with a glowing crown, vines and a dragon bone
    shard grown into her stem (faces left)."""
    p = _painter(BOSS_SIZE)
    capc = hexc("#8a3ad0")
    glowc = hexc("#d08aff")
    stem = hexc("#f2e6ee")
    vine = hexc("#3f8a4a")
    spore = hexc("#b8ff7a")
    ember_c = hexc("#ffb040")
    p.glow((192, 120), 210, glowc, 0.28)
    # ---- spore clouds drifting behind
    for x, y, r, col in ((40, 200, 34, "#b98ae0"), (350, 190, 30, "#a0d880"), (330, 110, 22, "#c8a0f0"),
                         (30, 120, 20, "#a0d880")):
        p.glow((x, y), r * 1.8, hexc(col), 0.45)
        for dx, dy, k in ((0, 0, 1.0), (r * 0.8, r * 0.3, 0.7), (-r * 0.7, r * 0.4, 0.6), (r * 0.1, -r * 0.6, 0.6)):
            p.shape("ellipse", (x + dx - r * k, y + dy - r * k * 0.8, x + dx + r * k, y + dy + r * k * 0.8),
                    hexc(col, 90), shadow=0.85, light=1.2, depth=0.3, line=0, rim=0, ao=0)
    # ---- vines at the back, curling out
    for pts, w0 in (([(250, 300), (310, 262), (350, 214), (360, 170), (340, 150)], 26),
                    ([(140, 290), (84, 250), (60, 200), (70, 164), (92, 162)], 24)):
        p.shape("poly", taper(pts, w0, 6), shade(vine, 0.8), depth=0.2, tex="leather", tex_amt=0.6)
    # ---- stem body flaring into a root skirt
    body = curve([(150, 130), (236, 130), (246, 220), (262, 290), (300, 350), (270, 366), (192, 370), (110, 366),
                  (82, 350), (120, 290), (138, 220)], 6)
    p.shape("poly", body, stem, depth=0.1, tex="bone", tex_amt=0.5)
    for pts in ([(150, 300), (130, 356)], [(236, 300), (262, 356)], [(192, 320), (192, 364)]):
        p.stroke(pts, shade(stem, 0.8), 2)
    # dragon bone shard grown into the stem, glowing
    p.glow((196, 322), 60, ember_c, 0.75)
    for a, b in (((196, 322), (160, 300)), ((196, 322), (236, 296)), ((196, 322), (224, 350)), ((196, 322),
                                                                                              (166, 350))):
        p.stroke(curve([a, ((a[0] + b[0]) / 2 + 4, (a[1] + b[1]) / 2 - 3), b], 4), hexc("#ffb040", 200), 2.2)
    sh = [(178, 298), (204, 284), (222, 306), (214, 340), (186, 350), (170, 326)]
    p.shape("poly", sh, hexc("#f4e2b0"), depth=0.25, light=1.45, line=1.4, tex="bone", tex_amt=0.8, spec=0.6)
    p.stroke([(186, 304), (196, 318), (192, 332), (204, 342)], hexc("#ff9a2a"), 2.4)
    p.stroke([(204, 294), (208, 312)], hexc("#ff9a2a"), 1.8)
    p.sparkle((206, 300), 7, hexc("#fff0b0"))
    # roots and tiny mushrooms at the base
    for pts in ([(110, 356), (70, 362), (40, 374)], [(280, 356), (320, 364), (350, 376)], [(160, 366), (140, 380)],
                [(236, 366), (256, 380)]):
        p.shape("poly", taper(pts, 16, 4), hexc("#c8b0a0"), depth=0.3, tex="wood", tex_amt=0.5)
    for x, y, s, c in ((64, 368, 1.0, "#5affc8"), (318, 370, 1.2, "#d08aff"), (340, 376, 0.8, "#5affc8")):
        p.glow((x, y - 14 * s), 18 * s, hexc(c), 0.6)
        p.shape("rect", (x - 3 * s, y - 14 * s, x + 3 * s, y), stem, radius=2, line=1.0, depth=0.3, rim=0)
        p.shape("chord", (x - 11 * s, y - 24 * s, x + 11 * s, y - 6 * s), hexc(c), start=180, end=360, line=1.1,
                light=1.5, rim=0)
    # ---- frilled veil ring under the face
    frill = curve([(128, 244), (256, 244), (286, 278), (266, 272), (250, 292), (228, 278), (206, 298), (184, 280),
                   (160, 298), (140, 280), (118, 292), (100, 278)], 5)
    p.shape("poly", frill, hexc("#e6d0ec"), depth=0.18, light=1.3, tex="cloth", tex_amt=0.6)
    for x in (130, 160, 192, 224, 254):
        p.stroke([(x, 252), (x - 4 + (x - 192) * 0.12, 280)], hexc("#b898c8"), 1.8)
    # ---- pale sleepy face
    p.flat("ellipse", (140, 206, 162, 218), hexc("#ff9ab8", 110))
    p.flat("ellipse", (210, 204, 230, 216), hexc("#ff9ab8", 90))
    eye(p, 160, 188, 11, 12, hexc("#8a4ad0"), look=(-1, 0.4), lid=0.6, skin=stem)
    eye(p, 212, 186, 9.5, 10.5, hexc("#8a4ad0"), look=(-1, 0.4), lid=0.6, skin=stem)
    for cx, s in ((160, 11), (212, 9.5)):
        for dx in (-s, -s * 0.4):
            p.stroke([(cx + dx, 186), (cx + dx - 4, 192)], DARK, 1.6)
    p.stroke(curve([(146, 170), (160, 164), (174, 168)], 4), hexc("#9a7aa8"), 2.4)
    p.stroke(curve([(200, 168), (212, 162), (224, 166)], 4), hexc("#9a7aa8"), 2.4)
    p.shape("ellipse", (176, 216, 192, 232), hexc("#6a2a4a"), depth=0.3, line=1.2, rim=0)
    p.flat("ellipse", (180, 224, 188, 230), hexc("#e07a9a"))
    # ---- the cap: gills, glowing dome, scalloped rim, a crown of little glowing mushrooms
    p.shape("ellipse", (26, 120, 358, 166), hexc("#e8c8e8"), depth=0.3, rim=0)
    for x in range(36, 352, 8):
        p.stroke([(x, 136), (192 + (x - 192) * 0.7, 150)], hexc("#b890c0"), 1.2)
    p.shadow_on(p._mask("ellipse", (26, 120, 358, 166)), strength=0.5, offset=4, blur=5)
    capm = p.shape("chord", (22, 40, 362, 248), capc, start=180, end=360, depth=0.12, light=1.3, spec=0.4,
                   tex="leather", tex_amt=0.5, gloss=0.4)
    for i in range(12):
        x = 34 + i * 29
        p.shape("chord", (x - 16, 126, x + 16, 152), shade(capc, 0.82), start=0, end=180, depth=0.3, line=1.2,
                rim=0)
    p.shape("ellipse", (20, 116, 364, 140), shade(capc, 0.72), depth=0.35, rim=0)
    for x, y, r in ((84, 92, 15), (150, 72, 18), (236, 72, 17), (300, 100, 13), (118, 112, 9), (196, 104, 11),
                    (262, 116, 8), (52, 118, 7), (332, 122, 6)):
        p.glow((x, y), r * 2.4, glowc, 0.6)
        p.shape("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#f0d8ff"), depth=0.25, line=1.1, light=1.4,
                rim=0, ao=0.2, clip=capm)
    for x, y, s, c in ((104, 68, 1.0, "#5affc8"), (146, 58, 1.2, "#ffe07a"), (192, 56, 1.4, "#ff9af0"),
                       (238, 58, 1.2, "#ffe07a"), (280, 68, 1.0, "#5affc8")):
        p.glow((x, y - 16 * s), 26 * s, hexc(c), 0.75)
        p.shape("rect", (x - 4 * s, y - 16 * s, x + 4 * s, y + 4), hexc("#f8f0ff"), radius=3, line=1.1, depth=0.3,
                rim=0)
        p.shape("chord", (x - 14 * s, y - 36 * s, x + 14 * s, y - 4 * s), hexc(c), start=180, end=360, line=1.3,
                light=1.5, rim=0, gloss=0.8)
        p.shape("ellipse", (x - 14 * s, y - 24 * s, x + 14 * s, y - 16 * s), shade(hexc(c), 0.8), depth=0.3,
                line=1.0, rim=0)
        p.flat("ellipse", (x - 7 * s, y - 30 * s, x - 2 * s, y - 25 * s), hexc("#ffffff", 220))
    # ---- vines in front: one reaching forward, one coiled on the right
    for pts, w0 in (([(146, 320), (96, 318), (52, 330), (22, 306), (30, 272), (54, 270)], 26),
                    ([(248, 326), (300, 318), (336, 290), (330, 256), (306, 254)], 22)):
        p.shape("poly", taper(pts, w0, 7), vine, depth=0.2, tex="leather", tex_amt=0.6)
        for x, y in along(curve(pts, 6), 26)[1:-1]:
            p.shape("poly", [(x - 3, y - 6), (x + 3, y - 6), (x, y - 14)], hexc("#c8e0a0"), line=0.9, rim=0, ao=0)
    for x, y, a in ((80, 322, 0), (318, 300, 1), (40, 296, 0)):
        p.shape("ellipse", (x - 10, y - 6, x + 10, y + 6), hexc("#6ac04a"), depth=0.3, line=1.1, rim=0)
    # ---- drifting spores
    for x, y, r in ((30, 60, 3), (62, 150, 2.5), (360, 60, 3), (340, 150, 2.5), (100, 230, 2), (300, 230, 2.5),
                    (20, 240, 2), (370, 250, 2), (130, 12, 2), (262, 6, 2), (82, 196, 2), (318, 206, 2)):
        p.glow((x, y), r * 3.4, spore, 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#f0ffe0"))
    return p.finish(outline=3, ground_shadow=(40, 344, 352, 382))


# ------------------------------------------------------------------ dungeon 3: Buzlu Geçit

def snowflake(p, x, y, r, color=hexc("#f4fbff")):
    p.glow((x, y), r * 2.2, hexc("#9ad8ff"), 0.4)
    for a in (0, 60, 120):
        t = math.radians(a)
        p.stroke([(x - r * math.cos(t), y - r * math.sin(t)), (x + r * math.cos(t), y + r * math.sin(t))], color,
                 max(1.0, r * 0.28))


def frost_wolf():
    """White-blue wolf with an icy crystal mane, glowing pale eyes and frosty breath (faces left)."""
    p = _painter(SIZE)
    fur = hexc("#dce8f4")
    fur_d = hexc("#9ab4d0")
    ice = hexc("#bfeaff")
    eyec = hexc("#9af0ff")
    # ---- bushy tail with an icy tip
    tail = [(196, 132), (226, 116), (244, 86), (236, 52)]
    tm = p.union([("poly", taper(tail, 30, 26)), ("ellipse", (216, 40, 248, 76)), ("ellipse", (218, 70, 248, 104))])
    p.paint_mask(tm, fur, depth=0.2, tex="fur", tex_amt=1.0)
    for pts in ([(206, 126), (228, 110), (238, 90)], [(226, 96), (240, 72)]):
        p.stroke(curve(pts, 4), hexc("#b8cce0"), 1.6)
    shard(p, 238, 42, 14, 30, 16, ice, glow=hexc("#7ad8ff"))
    # ---- far legs
    p.shape("line", [(104, 160), (98, 200), (96, 226)], fur_d, width=16, depth=0.2, tex="fur", tex_amt=0.6)
    p.shape("ellipse", (82, 218, 108, 234), shade(fur_d, 0.9), depth=0.3)
    p.shape("line", [(184, 160), (196, 200), (188, 226)], fur_d, width=16, depth=0.2, tex="fur", tex_amt=0.6)
    p.shape("ellipse", (176, 218, 204, 234), shade(fur_d, 0.9), depth=0.3)
    # ---- body with ice shards along the spine
    for x, y, h, a in ((118, 86, 30, -12), (140, 88, 26, 8), (160, 94, 22, 22), (180, 100, 18, 34)):
        shard(p, x, y, h * 0.45, h, a, ice)
    body = p.union([("ellipse", (70, 96, 214, 178)), ("ellipse", (158, 104, 222, 188))])
    p.paint_mask(body, fur, depth=0.12, tex="fur", tex_amt=1.0)
    p.shape("chord", (84, 136, 206, 190), hexc("#f6fbff"), start=0, end=180, line=0, depth=0.2, rim=0, ao=0,
            tex="fur", clip=body)
    p.shape("line", [(116, 120), (140, 116), (164, 124)], fur_d, width=3, **NOLINE)
    # ---- near hind leg
    p.shape("ellipse", (162, 118, 224, 196), fur, depth=0.14, tex="fur", tex_amt=0.9)
    p.shape("line", [(200, 182), (210, 208), (200, 226)], fur, width=18, depth=0.2, tex="fur", tex_amt=0.8)
    p.shape("ellipse", (184, 220, 216, 238), fur, depth=0.25, tex="fur")
    for x in (190, 198, 206):
        p.stroke([(x, 230), (x - 3, 237)], hexc("#3a4a6a"), 1.4)
    # ---- crystal mane around the neck
    mane = p.union([("ellipse", (62, 64, 140, 164)),
                    ("poly", [(64, 150), (74, 176), (86, 160), (96, 184), (106, 162), (122, 176), (126, 150)])])
    p.paint_mask(mane, fur, depth=0.14, tex="fur", tex_amt=1.0)
    for pts in ([(82, 120), (78, 140), (86, 156)], [(104, 128), (104, 150), (112, 164)]):
        p.stroke(curve(pts, 4), fur_d, 1.6)
    for x, y, h, a in ((112, 62, 38, 10), (128, 72, 34, 32), (138, 92, 30, 58), (100, 66, 30, -12),
                       (134, 116, 26, 80), (110, 164, 28, 190), (128, 150, 24, 140)):
        shard(p, x, y, h * 0.42, h, a, ice, glow=hexc("#7ad8ff"))
    # ---- near front leg
    p.shape("line", [(92, 150), (82, 196), (76, 226)], fur, width=20, depth=0.2, tex="fur", tex_amt=0.8)
    p.shape("ellipse", (58, 218, 92, 238), fur, depth=0.25, tex="fur")
    for x in (64, 72, 80):
        p.stroke([(x, 230), (x - 3, 237)], hexc("#3a4a6a"), 1.4)
    # ---- head: ears, snout, open jaw, glowing eye
    p.shape("poly", [(88, 58), (104, 20), (118, 62)], fur_d, depth=0.2, tex="fur")
    p.shape("poly", [(64, 62), (74, 16), (98, 56)], fur, depth=0.2, tex="fur")
    p.shape("poly", [(72, 56), (76, 28), (90, 54)], hexc("#a8c8e8"), depth=0.3, line=0.9, rim=0, ao=0)
    p.shape("poly", [(22, 122), (58, 124), (70, 132), (56, 140), (26, 136)], shade(fur_d, 0.9), depth=0.25,
            tex="fur", tex_amt=0.5)
    p.shape("poly", [(24, 120), (58, 122), (60, 130), (28, 132)], hexc("#3a2040"), **NOLINE)
    teeth(p, [(32, 132, 5, -7, 1), (48, 133, 5, -7, 1)], hexc("#f4f8ff"))
    head = p.union([("ellipse", (36, 50, 116, 124)),
                    ("poly", [(48, 78), (8, 98), (4, 110), (20, 122), (60, 124)])])
    p.paint_mask(head, fur, depth=0.12, tex="fur", tex_amt=0.9)
    teeth(p, [(26, 120, 5, 8, 1), (40, 121, 5, 8, 1), (54, 122, 6, 10, 1)], hexc("#f4f8ff"))
    p.shape("ellipse", (0, 96, 16, 108), hexc("#2a3450"), depth=0.3, line=1.0, gloss=0.8, rim=0)
    p.stroke(curve([(16, 96), (36, 90), (54, 88)], 4), fur_d, 1.6)
    p.shape("poly", [(90, 112), (116, 100), (118, 128), (100, 124), (112, 140), (86, 130)], fur, depth=0.2,
            tex="fur", line=1.2)
    glow_eye(p, 60, 82, 6.5, eyec, hexc("#ffffff"))
    p.shape("poly", [(46, 72), (76, 74), (74, 80), (48, 78)], fur_d, depth=0.3, line=1.0, rim=0)
    # ---- frost breath and falling snow
    for x, y, r in ((12, 146, 10), (28, 158, 8), (6, 170, 12)):
        p.glow((x, y), r * 1.8, hexc("#9ad8ff"), 0.4)
        p.shape("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#e8f6ff", 170), shadow=0.85, light=1.2,
                depth=0.3, line=0.9, ink=hexc("#5a8ab0", 150), rim=0, ao=0)
    for x, y, r in ((30, 180, 2), (150, 40, 2.5), (200, 20, 2), (18, 60, 2), (240, 140, 2)):
        snow(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(40, 222, 232, 248))


def ice_wisp():
    """Floating crystal spirit: a cluster of glowing shards with a face, trailing snow (faces left)."""
    p = _painter(SIZE)
    ice = hexc("#cdeeff")
    deep = hexc("#7ac8f0")
    glowc = hexc("#7ad8ff")
    p.glow((128, 112), 116, glowc, 0.4)
    # ---- snowy tail swirling behind and below
    p.shape("poly", taper([(128, 150), (150, 186), (184, 206), (222, 204), (240, 186)], 46, 4),
            hexc("#d8f0ff", 150), shadow=0.85, light=1.2, depth=0.2, line=1.0, ink=hexc("#5a9ad0", 150), rim=0,
            ao=0)
    for pt in along(curve([(140, 168), (170, 196), (206, 206), (236, 192)], 5), 14):
        snow(p, pt[0], pt[1] + 4, 2.4)
    # ---- back shards
    for x, y, w, h, a in ((82, 100, 30, 76, -34), (174, 96, 30, 76, 34), (100, 56, 20, 46, -16),
                          (158, 52, 20, 46, 18), (128, 168, 26, 52, 180), (98, 152, 18, 36, 215),
                          (160, 152, 18, 36, 145)):
        shard(p, x, y, w, h, a, deep, glow=glowc)
    # ---- the core crystal with a face
    shard(p, 128, 104, 70, 140, 0, ice)
    p.glow((128, 108), 34, hexc("#ffffff"), 0.35)
    for x, y, r in ((112, 106, 7.5), (144, 104, 6.5)):
        p.shape("ellipse", (x - r, y - r * 1.25, x + r, y + r * 1.25), hexc("#1a3a6a"), **NOLINE)
        p.glow((x, y), r * 2, glowc, 0.8)
        p.flat("ellipse", (x - r * 0.6, y - r * 0.8, x + r * 0.5, y + r * 0.7), hexc("#bff4ff"))
        p.flat("ellipse", (x - r * 0.35, y - r * 0.6, x + r * 0.05, y - r * 0.1), WHITE)
    p.stroke([(102, 92), (118, 96)], hexc("#3a6aa0"), 2.4)
    p.stroke([(138, 95), (152, 90)], hexc("#3a6aa0"), 2.4)
    p.shape("ellipse", (120, 124, 132, 136), hexc("#1a3a6a"), depth=0.3, line=1.0, rim=0)
    # ---- orbiting shards and snowflakes
    for x, y, h, a in ((40, 128, 26, -60), (214, 132, 24, 50), (56, 44, 20, -25), (204, 36, 22, 30)):
        shard(p, x, y, h * 0.45, h, a, ice, glow=glowc)
    for x, y, r in ((30, 90, 5), (226, 84, 4.5), (70, 190, 4), (128, 16, 4.5)):
        snowflake(p, x, y, r)
    for x, y, r in ((18, 160, 2), (240, 60, 2), (90, 20, 1.8), (176, 14, 2), (60, 222, 2), (110, 206, 2.2)):
        snow(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(82, 228, 174, 246))


def yeti_cub():
    """Chubby white yeti cub with a blue face, big fists and a grumpy pout (faces left)."""
    p = _painter(SIZE)
    fur = hexc("#eef3f8")
    blue = hexc("#7aa8d8")
    blue_d = hexc("#3a5a8a")
    # ---- feet
    for x0 in (80, 140):
        p.shape("ellipse", (x0, 212, x0 + 46, 240), fur, depth=0.25, tex="fur")
        p.shape("ellipse", (x0 + 4, 226, x0 + 42, 240), blue, depth=0.3, line=1.1, rim=0)
    # ---- back arm and fist
    p.shape("line", [(186, 118), (212, 160), (216, 178)], fur, width=34, depth=0.18, tex="fur", tex_amt=1.0)
    p.shape("ellipse", (192, 160, 244, 210), blue, depth=0.2, tex="leather", tex_amt=0.5)
    for y in (174, 186, 198):
        p.stroke([(198, y), (214, y - 2)], blue_d, 1.8)
    # ---- round furry body and head
    body = p.union([("ellipse", (54, 90, 206, 232)), ("ellipse", (58, 22, 198, 146)),
                    ("poly", [(96, 30), (108, 4), (118, 26), (132, 0), (142, 24), (158, 6), (164, 34)])])
    p.paint_mask(body, fur, depth=0.1, tex="fur", tex_amt=1.1)
    p.shape("ellipse", (88, 150, 176, 224), hexc("#dbe6f2"), line=0, depth=0.2, rim=0, ao=0, tex="fur")
    for pts in ([(70, 170), (66, 196)], [(190, 170), (194, 196)]):
        p.stroke(pts, hexc("#b8c8dc"), 1.6)
    # ---- blue face with a grumpy pout
    p.shape("ellipse", (62, 58, 162, 138), blue, depth=0.14, tex="leather", tex_amt=0.4)
    p.flat("ellipse", (70, 106, 86, 116), hexc("#ff8aa8", 90))
    p.flat("ellipse", (140, 104, 154, 114), hexc("#ff8aa8", 80))
    eye(p, 92, 94, 9, 10, hexc("#2a3a6a"), look=(-1, 0.2), lid=0.38, skin=blue)
    eye(p, 134, 92, 8, 9, hexc("#2a3a6a"), look=(-1, 0.2), lid=0.38, skin=blue)
    p.shape("poly", [(74, 72), (108, 82), (106, 88), (72, 80)], blue_d, depth=0.3, line=1.0, rim=0)
    p.shape("poly", [(120, 82), (150, 72), (152, 80), (122, 88)], blue_d, depth=0.3, line=1.0, rim=0)
    p.shape("ellipse", (104, 100, 120, 110), blue_d, depth=0.3, line=1.0, gloss=0.8, rim=0)
    p.shape("poly", curve([(94, 128), (104, 118), (122, 118), (132, 128), (120, 126), (106, 126)], 4), blue_d,
            depth=0.3, line=1.1, rim=0)
    teeth(p, [(100, 126, 5, -6, 1), (126, 126, 5, -6, 1)], hexc("#f8fbff"), line=0.8)
    # fur fringe over the forehead
    p.shape("poly", curve([(62, 70), (80, 54), (110, 50), (140, 52), (164, 66), (150, 64), (140, 72), (126, 62),
                           (112, 70), (98, 60), (84, 70)], 4), fur, depth=0.25, tex="fur")
    # ---- front arm and big fist
    p.shape("line", [(76, 142), (50, 174), (46, 186)], fur, width=34, depth=0.18, tex="fur", tex_amt=1.0)
    p.shape("ellipse", (14, 170, 68, 222), blue, depth=0.2, tex="leather", tex_amt=0.5)
    for y in (184, 196, 208):
        p.stroke([(20, y), (38, y - 2)], blue_d, 1.8)
    p.shape("ellipse", (46, 176, 68, 196), shade(blue, 1.08), depth=0.3, line=1.0, rim=0)
    # ---- snow
    for x, y, r in ((190, 40, 4.5), (30, 60, 4), (226, 110, 3.5)):
        snowflake(p, x, y, r)
    for x, y, r in ((40, 120, 2), (220, 70, 2.2), (20, 230, 2)):
        snow(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(18, 222, 240, 248))


def ice_troll():
    """Elite: tall blue troll with an icicle beard, frost armour and an ice-crystal club (faces left)."""
    p = _painter(SIZE)
    skin = hexc("#6a9ad0")
    skin_l = hexc("#9ec2e8")
    ice = hexc("#cdf0ff")
    deep = hexc("#8ad0f4")
    fur = hexc("#8a7a66")
    # ---- back arm, long, knuckles near the ground
    p.shape("line", [(184, 84), (216, 140), (224, 186)], skin, width=28, depth=0.18, tex="leather", tex_amt=0.6)
    p.shape("ellipse", (202, 176, 246, 216), skin, depth=0.2, tex="leather")
    for y in (188, 198):
        p.stroke([(208, y), (224, y - 2)], shade(skin, 0.55), 1.6)
    shard(p, 212, 122, 16, 34, 30, ice)
    # ---- legs and big feet
    for x0, x1 in ((96, 88), (150, 158)):
        p.shape("line", [(x0, 176), (x1, 222)], skin, width=32, depth=0.18, tex="leather", tex_amt=0.6)
        p.shape("ellipse", (x1 - 26, 214, x1 + 26, 240), shade(skin, 0.92), depth=0.25, tex="leather")
        for dx in (-18, -6, 6):
            p.shape("ellipse", (x1 + dx - 5, 228, x1 + dx + 5, 238), hexc("#e8f4ff"), line=0.9, rim=0, ao=0)
    # ---- hunched torso and belly
    p.shape("ellipse", (68, 50, 204, 196), skin, depth=0.1, tex="leather", tex_amt=0.7)
    p.shape("ellipse", (92, 110, 176, 190), skin_l, depth=0.18, line=0, rim=0, ao=0, tex="leather", tex_amt=0.5)
    # fur loincloth with a rope belt
    p.shape("poly", [(78, 168), (190, 168), (196, 206), (180, 198), (170, 212), (154, 200), (140, 214), (124, 200),
                     (108, 212), (94, 200), (76, 206)], fur, depth=0.14, tex="fur", tex_amt=1.0)
    p.shape("line", [(76, 170), (192, 168)], hexc("#b8905a"), width=7, depth=0.3, tex="leather", rim=0)
    # ice chest plate lashed on with rope
    plate = [(100, 96), (158, 92), (166, 142), (130, 156), (102, 144)]
    p.glow((132, 122), 40, hexc("#7ad8ff"), 0.35)
    p.shape("poly", plate, deep, depth=0.2, light=1.4, spec=0.9, line=1.3, ink=hexc("#2a4a7a"))
    p.shape("poly", [(112, 102), (150, 98), (140, 126), (116, 132)], ice, depth=0.2, light=1.4, line=0, rim=0, ao=0)
    for a, b in (((112, 102), (116, 132)), ((150, 98), (140, 126)), ((116, 132), (130, 154)), ((140, 126),
                                                                                              (164, 140))):
        p.stroke([a, b], hexc("#e8faff", 200), 1.4)
    for a, b in (((98, 110), (178, 70)), ((164, 134), (196, 110))):
        p.shape("line", [a, b], hexc("#b8905a"), width=5, depth=0.3, line=1.0, rim=0)
    # ---- frost pauldrons: clusters of shards
    for cx, cy, s in ((178, 70, 1.0), (84, 74, 1.1)):
        p.shape("ellipse", (cx - 22 * s, cy - 14 * s, cx + 22 * s, cy + 16 * s), deep, depth=0.25, spec=0.8,
                line=1.3, ink=hexc("#2a4a7a"))
        for dx, h, a in ((-14, 30, -30), (0, 38, 0), (14, 28, 28)):
            shard(p, cx + dx * s, cy - 14 * s, 12 * s, h * s, a, ice)
    # ---- front arm, hand low on the club handle
    p.shape("line", [(86, 96), (62, 136), (66, 164)], skin, width=28, depth=0.18, tex="leather", tex_amt=0.6)
    p.shape("ellipse", (48, 150, 88, 186), skin, depth=0.2, tex="leather")
    for y in (160, 168, 176):
        p.stroke([(52, y), (68, y - 2)], shade(skin, 0.55), 1.6)
    # ---- head: brow ridge, long nose, tusks and icicle beard
    for x, h in ((56, 34), (68, 44), (80, 38), (92, 46), (104, 34), (116, 26)):
        shard(p, x, 104 + h / 2 - 4, 10, h, 180, ice, line=1.0)
    p.shape("poly", [(118, 56), (140, 40), (134, 64)], shade(skin, 0.9), depth=0.25)
    head = p.union([("ellipse", (44, 30, 128, 108))])
    p.paint_mask(head, skin, depth=0.12, tex="leather", tex_amt=0.6)
    hair = p.union([("poly", taper([(x, 40), (x + 12, 22), (x + 30, 12 + i * 4)], 22, 2)) for i, x in
                    enumerate((52, 68, 84, 100, 112))])
    p.paint_mask(hair, hexc("#eef4fa"), depth=0.2, tex="fur", tex_amt=0.9)
    glow_eye(p, 64, 62, 5.5, hexc("#9af0ff"), hexc("#ffffff"))
    glow_eye(p, 94, 60, 5, hexc("#9af0ff"), hexc("#ffffff"))
    p.shape("poly", [(48, 48), (110, 46), (108, 56), (80, 58), (50, 58)], shade(skin, 0.8), depth=0.3, line=1.2,
            rim=0)
    p.shape("poly", curve([(78, 62), (64, 70), (52, 84), (56, 94), (70, 92), (84, 80)], 4), shade(skin, 1.05),
            depth=0.25, gloss=0.4)
    p.shape("poly", [(56, 94), (104, 92), (100, 104), (60, 106)], hexc("#2a2040"), depth=0.3, line=1.1, rim=0)
    teeth(p, [(64, 104, 7, -16, 1), (96, 102, 7, -14, 1)], hexc("#f4f0e0"))
    # ---- front arm dragging the ice-crystal club
    p.shape("poly", taper([(70, 170), (54, 190), (36, 214)], 12, 16), hexc("#6a4428"), depth=0.3, tex="wood")
    p.glow((34, 214), 44, hexc("#7ad8ff"), 0.5)
    p.shape("ellipse", (8, 192, 60, 238), deep, depth=0.2, spec=0.8, line=1.3, ink=hexc("#2a4a7a"))
    for x, y, w, h, a in ((14, 196, 16, 44, -40), (34, 186, 18, 50, -8), (52, 196, 14, 38, 30), (8, 222, 14, 30, -80),
                          (30, 218, 20, 40, 190)):
        shard(p, x, y, w, h, a, ice)
    for x, y, r in ((150, 20, 4.5), (226, 40, 4), (200, 240, 0)):
        if r:
            snowflake(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(6, 222, 246, 250))


def frostbreath():
    """Boss: Soğuk Nefes, a proud young ice dragon with crystal horns, half-open wings and frost breath
    (faces left)."""
    p = _painter(BOSS_SIZE)
    scale = hexc("#bcdcf4")
    scale_d = hexc("#7aa4d0")
    belly = hexc("#eef8ff")
    crystal = hexc("#d8f6ff")
    mem = hexc("#4f8ed8")
    glowc = hexc("#7ad8ff")
    p.glow((210, 170), 190, glowc, 0.2)
    # ---- far wing, raised behind
    wing(p, (238, 176), [(296, 84), (374, 56), (378, 136), (350, 190), (292, 212)], shade(mem, 0.82),
         shade(scale_d, 0.85), width=12, edge=hexc("#e8faff", 200))
    # ---- tail curling around the right, crystal spikes
    tail = [(290, 280), (338, 300), (366, 332), (348, 360), (300, 364), (270, 356)]
    p.shape("poly", taper(tail, 48, 8), scale, depth=0.16, tex="leather", tex_amt=0.6)
    for x, y in along(curve(tail[:4], 6), 24)[:4]:
        shard(p, x + 4, y - 22, 12, 26, 30, crystal)
    shard(p, 262, 356, 16, 34, -110, crystal, glow=glowc)
    # ---- far legs
    p.shape("line", [(276, 284), (290, 330), (282, 350)], shade(scale, 0.8), width=30, depth=0.2, tex="leather")
    p.shape("line", [(184, 270), (192, 330), (198, 350)], shade(scale, 0.8), width=26, depth=0.2, tex="leather")
    p.shape("ellipse", (182, 340, 218, 360), shade(scale, 0.78), depth=0.3)
    # ---- neck with a plated throat and crystal spikes
    neck = [(204, 226), (176, 184), (150, 152), (126, 124)]
    for x, y in along(curve(neck, 6), 24)[:4]:
        shard(p, x + 18, y - 16, 12, 26, 40, crystal)
    p.shape("poly", taper(neck, 70, 46), scale, depth=0.14, tex="leather", tex_amt=0.7)
    for x, y in along(curve(neck, 6), 12)[1:-1]:
        p.stroke([(x - 26, y + 4), (x - 10, y + 16)], hexc("#e6f4ff"), 3)
    # ---- body, spine crystals, belly plates
    for x, y, h, a in ((216, 166, 34, 0), (244, 170, 30, 14), (270, 178, 26, 28), (292, 192, 22, 40)):
        shard(p, x, y, h * 0.45, h, a, crystal)
    bm = p.shape("ellipse", (158, 170, 318, 314), scale, depth=0.12, tex="leather", tex_amt=0.7)
    scale_rows(p, bm, (200, 176, 316, 250), shade(scale, 1.08), size=12)
    p.shape("ellipse", (166, 214, 280, 316), belly, depth=0.16, line=1.2, rim=0, clip=bm, tex="leather",
            tex_amt=0.4)
    for y in range(230, 312, 14):
        p.stroke([(170, y), (270, y + 4)], hexc("#b8d4ec"), 1.6)
    # ---- near hind leg
    p.shape("ellipse", (234, 232, 316, 320), scale, depth=0.14, tex="leather", tex_amt=0.7)
    p.shape("line", [(290, 300), (280, 334), (270, 350)], scale, width=28, depth=0.2, tex="leather")
    p.shape("ellipse", (240, 336, 298, 362), scale, depth=0.25, tex="leather")
    for x in (246, 258, 270):
        p.shape("poly", [(x - 4, 356), (x + 4, 356), (x - 4, 368)], hexc("#f4fbff"), line=0.9, rim=0, ao=0)
    # ---- near wing, half open
    wing(p, (212, 176), [(238, 70), (300, 14), (334, 70), (318, 128), (274, 166)], mem, scale_d, width=14,
         edge=hexc("#f0fcff", 220))
    for x, y in ((290, 60), (300, 104), (262, 118)):
        p.glow((x, y), 12, glowc, 0.4)
    # ---- near front leg with claws
    p.shape("ellipse", (150, 224, 206, 286), scale, depth=0.16, tex="leather", tex_amt=0.7)
    p.shape("line", [(172, 262), (146, 300), (148, 336)], scale, width=28, depth=0.18, tex="leather")
    p.shape("ellipse", (120, 328, 170, 356), scale, depth=0.25, tex="leather")
    for x in (124, 136, 148):
        p.shape("poly", [(x - 4, 350), (x + 4, 350), (x - 6, 364)], hexc("#f4fbff"), line=0.9, rim=0, ao=0)
    # ---- head: crystal horns, snout, open jaw, big eye
    for pts, w, c in (([(138, 80), (170, 52), (204, 38)], 16, shade(crystal, 0.9)),
                      ([(128, 74), (148, 38), (176, 18)], 18, crystal)):
        p.glow(pts[-1], 18, glowc, 0.5)
        p.shape("poly", taper(pts, w, 2), c, depth=0.25, light=1.45, spec=0.9, line=1.3, ink=hexc("#2a4a7a"),
                rim=0)
    p.shape("poly", [(40, 132), (96, 138), (104, 150), (58, 156), (30, 146)], shade(scale, 0.88), depth=0.25,
            tex="leather", tex_amt=0.5)
    p.shape("poly", [(36, 132), (96, 136), (96, 144), (42, 142)], hexc("#2a3060"), **NOLINE)
    teeth(p, [(46, 142, 6, -8, 1), (62, 143, 6, -8, 1), (78, 144, 6, -8, 1)], hexc("#f8fcff"))
    head = p.union([("ellipse", (78, 66, 162, 140)),
                    ("poly", [(96, 84), (46, 100), (24, 114), (28, 130), (62, 134), (104, 136)])])
    p.paint_mask(head, scale, depth=0.12, tex="leather", tex_amt=0.7)
    teeth(p, [(38, 130, 6, 9, 1), (54, 132, 6, 9, 1), (70, 133, 6, 8, 1)], hexc("#f8fcff"))
    for x, y, h, a in ((150, 120, 26, 70), (144, 134, 20, 100)):
        shard(p, x, y, h * 0.45, h, a, crystal)
    p.shape("ellipse", (28, 108, 38, 116), hexc("#2a3a6a"), **NOLINE)
    p.stroke(curve([(40, 104), (70, 94), (98, 90)], 4), shade(scale, 0.7), 2)
    eye(p, 112, 100, 11, 12, hexc("#3ab0f0"), look=(-1, 0), lid=0.28, skin=scale)
    p.shape("poly", [(94, 82), (132, 84), (128, 92), (96, 90)], scale_d, depth=0.3, line=1.1, rim=0)
    # ---- frost breath
    p.glow((20, 170), 60, glowc, 0.7)
    p.shape("poly", curve([(40, 138), (14, 146), (0, 164), (0, 236), (14, 230), (30, 196), (44, 150)], 5),
            hexc("#c8f0ff", 130), **NOLINE)
    for x, y, r in ((30, 150, 12), (16, 170, 16), (40, 176, 10), (8, 196, 14)):
        p.shape("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#e8f8ff", 190), shadow=0.85, light=1.2,
                depth=0.3, line=1.0, ink=hexc("#5a8ab0", 160), rim=0, ao=0)
    for x, y, h, a in ((22, 156, 14, -120), (44, 188, 12, -140), (10, 214, 12, -160)):
        shard(p, x, y, h * 0.5, h, a, crystal)
    for x, y, r in ((60, 40, 5), (340, 250, 4.5), (20, 260, 4), (100, 200, 3.5)):
        snowflake(p, x, y, r)
    for x, y, r in ((30, 90, 2.4), (230, 30, 2), (370, 200, 2), (60, 300, 2.2), (120, 240, 2), (360, 30, 2)):
        snow(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(60, 342, 378, 380))


# ------------------------------------------------------------------ dungeon 4: Yanık Kale

LAVA = hexc("#ff7a1a")


def lava_crack(p, pts, width=2.4, glow=True):
    """Glowing crack of molten light along a polyline."""
    pts = curve(pts, 4) if len(pts) > 2 else pts
    if glow:
        for x, y in along(pts, 7):
            p.glow((x, y), width * 3.2, LAVA, 0.35)
    p.stroke(pts, hexc("#ff9a2a"), width)
    p.stroke(pts, hexc("#fff0b0"), max(0.8, width * 0.4))


def smoke(p, x, y, r, alpha=150, color=hexc("#6a6070")):
    for dx, dy, k in ((0, 0, 1.0), (r * 0.7, -r * 0.5, 0.75), (-r * 0.6, -r * 0.3, 0.65)):
        p.shape("ellipse", (x + dx - r * k, y + dy - r * k * 0.85, x + dx + r * k, y + dy + r * k * 0.85),
                color[:3] + (alpha,), shadow=0.8, light=1.2, depth=0.3, line=0, rim=0, ao=0)


def cultist():
    """Hooded dragon cultist in red and black robes with a dragon-eye pendant and a wavy ritual dagger
    (faces left)."""
    p = _painter(SIZE)
    black = hexc("#2c1c26")
    red = hexc("#a82a2a")
    gold = hexc("#f0bb45")
    eyec = hexc("#ff8a2a")
    p.glow((120, 90), 80, hexc("#ff4a1a"), 0.18)
    # ---- back arm in a wide sleeve, a candle flame on the palm
    p.shape("poly", curve([(160, 104), (184, 128), (202, 150), (196, 164), (176, 156), (156, 134)], 5), black,
            depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(180, 160), (200, 150)], red, width=6, depth=0.3, rim=0)
    p.shape("ellipse", (192, 146, 212, 164), hexc("#d8b8a8"), depth=0.25)
    flame(p, 204, 146, 14, 26, lean=0.1)
    # ---- the robe: black outer robe, red front panel, gold runes on the hem
    p.shape("poly", curve([(98, 96), (164, 96), (180, 160), (198, 232), (128, 238), (58, 232), (80, 160)], 6),
            black, depth=0.12, tex="cloth", tex_amt=0.7)
    p.shape("poly", [(112, 110), (150, 110), (166, 236), (96, 236)], red, depth=0.14, tex="cloth", tex_amt=0.7,
            line=1.2)
    for pts in ([(92, 160), (74, 228)], [(170, 160), (184, 228)], [(130, 150), (130, 232)]):
        p.stroke(pts, shade(black, 0.6) if pts[0][0] != 130 else shade(red, 0.6), 2)
    p.shape("line", curve([(60, 226), (128, 232), (196, 226)], 5), gold, width=4, depth=0.3, spec=0.5, rim=0)
    for x in (80, 104, 152, 176):
        p.stroke([(x - 4, 216), (x, 208), (x + 4, 216), (x, 222), (x - 4, 216)], hexc("#ffcf6a"), 1.4)
    p.shape("rect", (76, 232, 104, 242), DARK, radius=4, depth=0.3, line=1.2)
    p.shape("rect", (140, 232, 170, 242), DARK, radius=4, depth=0.3, line=1.2)
    # rope belt with tassels
    p.shape("line", curve([(82, 164), (130, 172), (178, 164)], 5), hexc("#c8a060"), width=6, depth=0.3, rim=0)
    for x in (96, 106):
        p.shape("line", [(x, 168), (x - 2, 196)], hexc("#c8a060"), width=3.5, depth=0.3, line=1.0, rim=0)
        p.shape("ellipse", (x - 6, 192, x + 2, 204), red, depth=0.3, line=1.0, rim=0)
    # ---- hood with a pointed peak and gold edging; burning eyes in the dark
    hood = p.union([("ellipse", (78, 22, 174, 124)), ("poly", [(130, 30), (178, 2), (166, 52)])])
    p.paint_mask(hood, red, depth=0.12, tex="cloth", tex_amt=0.8)
    p.shape("ellipse", (86, 44, 156, 118), hexc("#120a10"), depth=0.2, line=1.0, rim=0)
    p.stroke(curve([(84, 104), (86, 64), (112, 40), (142, 42), (160, 70), (160, 106)], 6), gold, 2.4)
    glow_eye(p, 104, 80, 6, eyec, socket=False)
    glow_eye(p, 132, 78, 5.2, eyec, socket=False)
    p.stroke([(94, 70), (112, 76)], hexc("#ff6a2a", 160), 1.6)
    p.stroke([(124, 74), (140, 68)], hexc("#ff6a2a", 160), 1.6)
    p.shape("ellipse", (78, 100, 176, 138), black, depth=0.2, tex="cloth", tex_amt=0.6)
    # dragon-eye pendant
    chain(p, (104, 112), (122, 132), 4, hexc("#d8a840"), 6)
    chain(p, (152, 112), (134, 132), 4, hexc("#d8a840"), 6)
    p.glow((128, 144), 26, eyec, 0.6)
    p.shape("ellipse", (112, 128, 144, 160), gold, depth=0.25, light=1.45, spec=1.0)
    p.shape("poly", curve([(116, 144), (128, 134), (140, 144), (128, 154)], 4) + [(116, 144)], hexc("#ffb03a"),
            depth=0.25, light=1.5, line=1.0, rim=0, gloss=0.8)
    p.flat("rect", (126, 136, 130, 152), DARK, radius=2)
    # ---- front arm raising a wavy ritual dagger
    p.shape("poly", curve([(100, 104), (82, 118), (60, 128), (54, 144), (70, 150), (92, 138), (108, 124)], 5), black,
            depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(56, 140), (70, 150)], red, width=6, depth=0.3, rim=0)
    kris = []
    for i in range(9):
        t = i / 8
        x, y = 50 - 34 * t, 128 - 88 * t
        w = 7 * (1 - t * 0.8)
        off = math.sin(i * 1.6) * 4
        kris.append((x + w + off * 0.6, y + w * 0.5 + off * 0.3))
    back = []
    for i in range(9):
        t = i / 8
        x, y = 50 - 34 * t, 128 - 88 * t
        w = 7 * (1 - t * 0.8)
        off = math.sin(i * 1.6) * 4
        back.append((x - w + off * 0.6, y - w * 0.5 + off * 0.3))
    p.shape("poly", kris + [(14, 34)] + back[::-1], hexc("#a8b0b8"), depth=0.3, light=1.35, line=1.3, spec=0.8,
            tex="metal", tex_amt=0.5)
    p.stroke(curve([(46, 118), (38, 98), (32, 76), (22, 50)], 4), hexc("#c83a2a"), 1.6)
    p.shape("line", [(40, 136), (64, 124)], gold, width=6, depth=0.3, spec=0.8, rim=0)
    p.shape("ellipse", (46, 124, 58, 136), hexc("#e0303a"), line=0.9, gloss=1.0, rim=0)
    p.shape("ellipse", (42, 132, 64, 152), hexc("#d8b8a8"), depth=0.25)
    for x, y, r in ((30, 20, 2), (70, 30, 1.6), (200, 110, 2), (220, 190, 1.8), (184, 40, 1.6)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(40, 224, 220, 250))


def fire_imp():
    """Small mischievous imp made of embers, with flaming hair and a pitchfork (faces left)."""
    p = _painter(SIZE)
    skin = hexc("#d8402a")
    belly = hexc("#ff9a4a")
    dark = hexc("#5a1a1a")
    iron = hexc("#4a4448")
    p.glow((120, 120), 110, hexc("#ff6a1a"), 0.22)
    # ---- flaming hair (behind the head)
    for x, base, w, h, lean in ((150, 64, 38, 54, 0.45), (100, 56, 40, 56, 0.2), (128, 52, 52, 78, 0.35)):
        flame(p, x, base, w, h, lean=lean)
    # ---- tail with a spade tip and little wings
    p.shape("poly", taper([(150, 180), (196, 206), (226, 190), (232, 160)], 9, 5), skin, depth=0.3)
    p.shape("poly", [(232, 146), (244, 166), (232, 172), (220, 166)], dark, depth=0.3, light=1.3)
    wing(p, (160, 116), [(196, 84), (240, 70), (238, 104), (212, 124)], hexc("#7a2020"), dark, width=6,
         edge=hexc("#ff8a3a", 200))
    # ---- goat legs with hooves
    for pts, hx in (([(114, 178), (118, 200), (106, 218)], 104), ([(144, 178), (152, 200), (144, 218)], 144)):
        p.shape("line", pts, skin, width=16, depth=0.2)
        p.shape("rect", (hx - 12, 214, hx + 10, 230), hexc("#2a1a1a"), radius=5, depth=0.3, spec=0.6)
    # ---- ember body with glowing cracks
    body = p.shape("ellipse", (92, 106, 168, 196), skin, depth=0.14, tex="stone", tex_amt=0.5)
    p.shape("ellipse", (104, 132, 156, 192), belly, depth=0.2, line=0, rim=0, ao=0, clip=body)
    lava_crack(p, [(110, 120), (118, 138), (112, 156)])
    lava_crack(p, [(156, 126), (148, 146), (156, 168)])
    # ---- back arm raised with a fireball
    p.shape("line", [(160, 128), (184, 120), (192, 100)], skin, width=13, depth=0.2)
    p.shape("ellipse", (182, 90, 202, 110), skin, depth=0.25)
    p.glow((194, 78), 30, hexc("#ffb040"), 0.7)
    p.shape("ellipse", (182, 64, 206, 90), hexc("#ffcf5a"), light=1.5, depth=0.25, line=1.1, ink=hexc("#8a2a0a"),
            gloss=0.8, rim=0)
    flame(p, 194, 72, 18, 26, lean=0.2, glow=False)
    # ---- head: pointed ears, horns, big grin
    for pts in ([(74, 84), (30, 66), (72, 102)], [(160, 82), (196, 60), (164, 102)]):
        p.shape("poly", pts, skin, depth=0.2)
    for pts in ([(92, 50), (84, 28), (72, 20)], [(142, 48), (148, 26), (162, 18)]):
        p.shape("poly", taper(pts, 12, 2), hexc("#3a2a2a"), depth=0.3, spec=0.6)
    p.shape("ellipse", (66, 40, 170, 132), skin, depth=0.12, tex="stone", tex_amt=0.4)
    lava_crack(p, [(150, 56), (144, 70), (152, 84)], 2)
    lava_crack(p, [(80, 60), (88, 72)], 1.8)
    eye(p, 96, 84, 11, 12, hexc("#ffb020"), look=(-1, 0.1), lid=0.25, skin=skin)
    eye(p, 136, 82, 9.5, 10.5, hexc("#ffb020"), look=(-1, 0.1), lid=0.25, skin=skin)
    p.stroke([(80, 66), (108, 72)], dark, 3.2)
    p.stroke([(126, 70), (150, 62)], dark, 3.2)
    mouth = p.shape("poly", curve([(78, 104), (102, 112), (130, 110), (156, 98), (148, 118), (118, 126), (90, 120)],
                                  5), hexc("#3a0a0a"), depth=0.25, line=1.3, rim=0)
    p.shape("ellipse", (104, 112, 134, 128), hexc("#ff7a3a"), **NOLINE, clip=mouth)
    teeth(p, [(92, 110, 7, 8, 1), (108, 112, 7, 8, 1), (124, 111, 7, 8, 1), (140, 106, 7, 8, 1)],
          hexc("#fff4d8"), line=0.9)
    p.flat("ellipse", (74, 96, 86, 106), hexc("#ffcf6a", 90))
    # ---- front arm on the pitchfork
    p.shape("line", [(48, 236), (40, 22)], iron, width=6, depth=0.3, spec=0.6)
    for x0 in (26, 40, 54):
        p.shape("line", [(x0 + (40 - x0) * 0.2, 36), (x0, 10)], iron, width=4.5, depth=0.3, line=1.1, spec=0.6,
                rim=0)
        p.shape("poly", [(x0 - 4, 12), (x0 + 4, 12), (x0, 0)], hexc("#ffb040"), line=1.0, rim=0, ao=0)
        p.glow((x0, 6), 9, LAVA, 0.6)
    p.shape("line", [(24, 38), (58, 36)], iron, width=6, depth=0.3, spec=0.6)
    p.shape("line", [(98, 132), (70, 150), (50, 140)], skin, width=13, depth=0.2)
    p.shape("ellipse", (36, 130, 60, 152), skin, depth=0.25)
    for x, y, r in ((24, 90, 2), (60, 190, 2.2), (206, 150, 1.8), (220, 40, 2), (180, 24, 1.6), (90, 20, 1.8)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(40, 222, 200, 246))


def ember_hound():
    """Charcoal hound with glowing lava cracks, burning eyes and a burning tail (faces left)."""
    p = _painter(SIZE)
    coal = hexc("#3e353c")
    coal_d = hexc("#2a2228")
    eyec = hexc("#ffd23a")
    p.glow((120, 130), 110, hexc("#ff5a1a"), 0.18)
    for x, y, r in ((170, 60, 16), (196, 44, 12), (150, 44, 10)):
        smoke(p, x, y, r, 120)
    # ---- burning tail
    p.shape("poly", taper([(200, 124), (224, 106), (236, 84)], 16, 8), coal, depth=0.25, tex="stone")
    flame(p, 238, 94, 30, 70, lean=0.15, strength=0.8)
    # ---- far legs
    p.shape("line", [(104, 160), (98, 198), (96, 226)], coal_d, width=16, depth=0.2, tex="stone")
    p.shape("line", [(184, 160), (198, 198), (190, 226)], coal_d, width=16, depth=0.2, tex="stone")
    for x in (96, 190):
        p.shape("ellipse", (x - 14, 220, x + 12, 236), coal_d, depth=0.3)
    # ---- body: lean charcoal torso with a spiky smouldering ridge
    ridge = [(92, 72), (104, 58), (114, 76), (128, 62), (138, 84), (152, 72), (160, 94), (176, 86), (180, 104),
             (200, 100), (196, 120), (100, 110)]
    p.shape("poly", ridge, coal_d, depth=0.2, tex="stone")
    for x, y in ((104, 58), (128, 62), (152, 72), (176, 86)):
        ember(p, x, y + 2, 2.2)
    body = p.union([("ellipse", (70, 92, 214, 172)), ("ellipse", (160, 100, 224, 186)),
                    ("ellipse", (58, 84, 134, 176))])
    p.paint_mask(body, coal, depth=0.12, tex="stone", tex_amt=0.9)
    for pts in ([(96, 104), (110, 120), (104, 138), (116, 156)], [(140, 100), (150, 118), (146, 134)],
                [(176, 116), (188, 134), (180, 154), (190, 168)], [(124, 148), (140, 160), (160, 156)]):
        lava_crack(p, pts)
    # ---- near legs with glowing claws
    p.shape("line", [(92, 150), (82, 196), (76, 226)], coal, width=20, depth=0.2, tex="stone")
    p.shape("ellipse", (56, 218, 92, 238), coal, depth=0.25)
    p.shape("line", [(200, 176), (210, 204), (200, 226)], coal, width=18, depth=0.2, tex="stone")
    p.shape("ellipse", (184, 220, 218, 238), coal, depth=0.25)
    for x0 in (60, 188):
        for dx in (0, 8, 16):
            p.stroke([(x0 + dx, 232), (x0 + dx - 4, 240)], hexc("#ffb040"), 2)
    lava_crack(p, [(84, 176), (80, 200), (84, 214)], 2)
    lava_crack(p, [(206, 196), (204, 214)], 2)
    # ---- head: snarling jaw with a molten throat
    p.shape("poly", [(70, 58), (82, 22), (98, 58)], coal_d, depth=0.2, tex="stone")
    p.glow((42, 128), 30, LAVA, 0.6)
    p.shape("poly", [(18, 118), (64, 122), (74, 132), (58, 142), (24, 136)], coal_d, depth=0.25, tex="stone")
    p.shape("poly", [(20, 116), (64, 120), (64, 128), (26, 130)], hexc("#ff7a1a"), **NOLINE)
    p.shape("poly", [(30, 120), (60, 122), (58, 126), (34, 127)], hexc("#ffe07a"), **NOLINE)
    teeth(p, [(30, 130, 5, -7, 1), (46, 131, 5, -7, 1)], hexc("#f4e8d0"))
    head = p.union([("ellipse", (36, 48, 116, 122)), ("poly", [(50, 76), (8, 94), (4, 108), (20, 120), (62, 122)])])
    p.paint_mask(head, coal, depth=0.12, tex="stone", tex_amt=0.9)
    teeth(p, [(24, 118, 5, 8, 1), (38, 119, 5, 8, 1), (54, 120, 6, 10, 1)], hexc("#f4e8d0"))
    p.shape("ellipse", (0, 94, 16, 106), hexc("#1a1418"), depth=0.3, line=1.0, gloss=0.6, rim=0)
    p.shape("poly", [(76, 60), (104, 26), (112, 66)], coal, depth=0.2, tex="stone")
    p.shape("poly", [(84, 58), (102, 36), (106, 62)], hexc("#ff7a1a"), **NOLINE)
    lava_crack(p, [(20, 98), (40, 92), (56, 96)], 1.8)
    lava_crack(p, [(80, 96), (92, 108), (86, 118)], 2)
    glow_eye(p, 62, 80, 6.5, eyec)
    p.shape("poly", [(46, 70), (78, 74), (76, 80), (48, 78)], coal_d, depth=0.3, line=1.0, rim=0)
    for x, y, r in ((20, 60, 2), (130, 30, 2), (230, 30, 1.8), (10, 160, 1.6), (150, 210, 1.8)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(40, 222, 232, 248))


def flame_knight():
    """Elite: knight in blackened plate with a flame plume and a flaming greatsword (faces left)."""
    p = _painter(SIZE)
    plate = hexc("#4a4a58")
    plate_d = hexc("#2e2e3a")
    cloth = hexc("#8a1a1a")
    gold = hexc("#d8a040")
    p.glow((80, 100), 110, hexc("#ff5a1a"), 0.2)
    # ---- flame plume streaming back
    for x, base, w, h, lean in ((160, 50, 30, 38, 1.0), (142, 42, 34, 40, 0.8), (122, 36, 30, 34, 0.55)):
        flame(p, x, base, w, h, lean=lean)
    # ---- burnt cape
    p.shape("poly", [(150, 92), (206, 104), (226, 196), (214, 188), (206, 214), (194, 196), (180, 220), (170, 196),
                     (150, 206)], shade(cloth, 0.7), depth=0.12, tex="cloth", tex_amt=0.8)
    for x, y in ((214, 190), (182, 214)):
        ember(p, x, y, 2)
    # ---- back arm
    p.shape("line", [(176, 106), (192, 140), (176, 162)], plate_d, width=22, depth=0.2, spec=0.6, tex="metal")
    # ---- legs: cuisses, knees, greaves, sabatons
    for x in (98, 140):
        p.shape("rect", (x, 176, x + 26, 222), plate_d, radius=6, depth=0.2, spec=0.6, tex="metal", tex_amt=0.6)
        p.shape("ellipse", (x - 2, 190, x + 28, 210), plate, depth=0.3, light=1.35, spec=1.0)
        p.shape("rect", (x - 10, 216, x + 30, 238), plate_d, radius=8, depth=0.25, spec=0.6, tex="metal")
        rivet(p, x + 13, 200, 2, gold)
    # ---- burnt tabard with a flame sigil and charred hem
    p.shape("poly", [(100, 110), (164, 110), (170, 196), (160, 188), (150, 204), (138, 190), (126, 206), (114, 190),
                     (100, 202), (94, 196)], cloth, depth=0.12, tex="cloth", tex_amt=0.8)
    for x, y in ((106, 196), (146, 200), (160, 190)):
        p.flat("ellipse", (x - 6, y - 4, x + 6, y + 4), hexc("#1a0a0a", 150))
    p.shape("poly", curve([(132, 124), (142, 140), (140, 156), (132, 166), (124, 156), (122, 140)], 4) + [(132, 124)],
            gold, depth=0.25, light=1.4, spec=0.8, line=1.1)
    p.shape("poly", [(132, 138), (137, 150), (132, 160), (127, 150)], hexc("#ff7a1a"), **NOLINE)
    p.shape("rect", (94, 166, 170, 178), hexc("#3a2a24"), radius=4, depth=0.3, tex="leather")
    p.shape("rect", (122, 162, 142, 182), gold, radius=3, depth=0.3, spec=0.9)
    # ---- breastplate with glowing seams
    p.shape("chord", (96, 84, 168, 160), plate, start=180, end=360, depth=0.2, light=1.35, spec=1.0, tex="metal",
            tex_amt=0.5)
    lava_crack(p, [(132, 88), (132, 118)], 1.8)
    # ---- pauldrons with spikes
    for cx, s in ((168, 0.9), (98, 1.1)):
        for dx in (-10, 4):
            p.shape("poly", [(cx + dx * s - 5, 92), (cx + dx * s + 5, 92), (cx + dx * s - 4, 66)], plate_d, depth=0.3,
                    spec=0.8, line=1.2)
        p.shape("ellipse", (cx - 22 * s, 84, cx + 22 * s, 124), plate, depth=0.2, light=1.35, spec=1.0, tex="metal")
        p.stroke(curve([(cx - 18 * s, 110), (cx, 120), (cx + 18 * s, 110)], 4), gold, 2)
    # ---- great helm with a glowing visor slit
    p.shape("rect", (80, 20, 142, 98), plate, radius=24, depth=0.16, light=1.35, spec=1.0, tex="metal",
            tex_amt=0.5)
    p.shape("line", [(110, 22), (110, 96)], plate_d, width=6, depth=0.3, spec=0.6, rim=0)
    p.glow((98, 58), 26, LAVA, 0.7)
    p.shape("rect", (80, 52, 128, 62), hexc("#140a0a"), radius=3, **NOLINE)
    p.shape("rect", (82, 55, 124, 59), hexc("#ffb040"), radius=2, **NOLINE)
    for x, y in ((90, 76), (98, 80), (90, 86), (98, 90)):
        p.flat("ellipse", (x - 2, y - 2, x + 2, y + 2), hexc("#ff7a1a"))
    p.shape("rect", (78, 40, 144, 48), gold, radius=3, depth=0.3, spec=0.8)
    # ---- the flaming greatsword held low in both hands
    for t in (0.3, 0.55, 0.8):
        x, y = 86 + (18 - 86) * t, 150 + (16 - 150) * t
        flame(p, x + 4, y + 2, 34, 46 - t * 10, lean=0.35, strength=0.55)
    p.glow((52, 84), 60, LAVA, 0.5)
    blade(p, (86, 150), (18, 16), 18, hexc("#ff8a4a"), spec=0.8)
    p.stroke([(84, 146), (24, 26)], hexc("#fff0b0"), 3)
    for t in (0.18, 0.45, 0.7, 0.9):
        x, y = 86 + (18 - 86) * t, 150 + (16 - 150) * t
        flame(p, x - 4, y + 4, 16, 22, lean=-0.3, glow=False)
    p.shape("line", [(66, 160), (106, 140)], plate_d, width=8, depth=0.3, spec=0.8, rim=0)
    p.shape("ellipse", (80, 144, 92, 156), hexc("#e0303a"), line=1.0, gloss=1.0, rim=0)
    p.shape("line", [(92, 158), (104, 182)], hexc("#3a2a24"), width=8, depth=0.3, tex="leather", rim=0)
    p.shape("ellipse", (98, 176, 112, 190), gold, depth=0.3, spec=0.9)
    # ---- gauntlets on the grip
    p.shape("line", [(102, 110), (90, 140), (96, 164)], plate_d, width=22, depth=0.2, spec=0.6, tex="metal")
    for y in (158, 170):
        p.shape("ellipse", (86, y - 9, 108, y + 9), plate, depth=0.3, light=1.35, spec=0.9)
    for x, y, r in ((30, 70, 2), (10, 110, 1.8), (60, 20, 2), (200, 60, 1.8), (230, 120, 2)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(30, 222, 236, 250))


def ember_priestess():
    """Boss: Kor Rahibe, a tall priestess in red and gold with a horned ember crown and a burning censer
    (faces left)."""
    p = _painter(BOSS_SIZE)
    robe = hexc("#b02a2a")
    robe_d = hexc("#5a1418")
    gold = hexc("#f0bb45")
    skin = hexc("#ecd6cc")
    hair = hexc("#2a1620")
    p.glow((200, 180), 200, hexc("#ff4a1a"), 0.28)
    # ---- halo ring behind the head
    from PIL import ImageChops
    ring = ImageChops.subtract(p._mask("ellipse", (126, 16, 292, 182)), p._mask("ellipse", (136, 26, 282, 172)))
    p.paint_mask(ring, gold, depth=0.3, line=1.2, spec=0.6, rim=0)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        x, y = 209 + 83 * math.cos(a), 99 + 83 * math.sin(a)
        if y < 150:
            flame(p, x, y + 4, 12, 20, lean=math.cos(a) * 0.3, strength=0.5)
    # ---- long hair flowing behind
    p.shape("poly", curve([(176, 70), (240, 66), (268, 120), (290, 200), (312, 250), (270, 240), (250, 190),
                           (226, 140)], 6), hair, depth=0.12, tex="fur", tex_amt=0.5)
    # ---- back arm raised, palm cradling a fireball
    p.shape("poly", curve([(252, 176), (286, 196), (306, 176), (316, 150), (300, 144), (286, 170), (262, 160)], 5),
            robe, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("ellipse", (298, 132, 322, 154), skin, depth=0.25)
    p.glow((312, 110), 40, hexc("#ffb040"), 0.8)
    p.shape("ellipse", (296, 96, 328, 128), hexc("#ffcf5a"), light=1.5, depth=0.25, line=1.1, ink=hexc("#8a2a0a"),
            gloss=0.8, rim=0)
    flame(p, 312, 108, 26, 40, lean=0.1, glow=False)
    # ---- the robe: flowing outer robe, dark inner panel, flame-cut gold hem
    p.shape("poly", curve([(160, 150), (254, 150), (268, 230), (300, 330), (320, 364), (200, 370), (80, 364),
                           (110, 300), (146, 230)], 6), robe, depth=0.1, tex="cloth", tex_amt=0.7)
    for pts in ([(170, 200), (136, 360)], [(246, 200), (284, 360)], [(154, 240), (116, 350)]):
        p.stroke(pts, shade(robe, 0.62), 2.4)
    p.shape("poly", [(186, 158), (230, 158), (250, 366), (166, 366)], robe_d, depth=0.12, line=1.3, tex="cloth")
    for y in range(230, 356, 30):
        w = 10 + (y - 230) * 0.06
        flame(p, 208, y + 12, w * 1.6, 26, glow=False, colors=("#d88a2a", "#f0bb45", "#fff0b0"))
    p.stroke([(186, 160), (166, 362)], gold, 3.4)
    p.stroke([(230, 160), (250, 362)], gold, 3.4)
    hem = [(80, 364)]
    for i in range(12):
        x = 80 + i * 20
        hem += [(x + 10, 346 - (i % 2) * 6), (x + 20, 364)]
    p.shape("poly", hem + [(320, 364), (320, 374), (80, 374)], gold, depth=0.25, light=1.4, spec=0.6)
    # ---- gold sash with an ember gem
    p.shape("line", curve([(150, 232), (208, 240), (266, 230)], 5), gold, width=12, depth=0.3, spec=0.8)
    p.glow((208, 240), 20, LAVA, 0.6)
    p.shape("ellipse", (198, 230, 218, 250), hexc("#ff7a1a"), line=1.1, light=1.6, gloss=1.0, rim=0)
    # ---- high gold collar / mantle
    p.shape("ellipse", (140, 136, 276, 196), robe_d, depth=0.18, tex="cloth")
    p.stroke(curve([(146, 172), (180, 190), (208, 194), (236, 190), (270, 172)], 5), gold, 3.2)
    for cx in (156, 260):
        p.shape("poly", [(cx - 26, 170), (cx, 138), (cx + 26, 170), (cx, 186)], gold, depth=0.25, light=1.4,
                spec=0.9)
        p.shape("ellipse", (cx - 6, 156, cx + 6, 168), hexc("#ff7a1a"), line=0.9, gloss=1.0, rim=0)
    # ---- face: pale, ember eyes, dark lips
    p.shape("rect", (192, 124, 226, 150), skin, radius=8, depth=0.2)
    p.shape("ellipse", (170, 60, 240, 140), skin, depth=0.12, rim=0.3)
    p.shape("poly", curve([(168, 90), (178, 62), (210, 52), (238, 62), (244, 94), (232, 76), (212, 70), (190, 76),
                           (176, 100)], 5), hair, depth=0.2, tex="fur", tex_amt=0.5)
    for x, r in ((190, 7), (220, 6)):
        p.glow((x, 100), r * 2.6, hexc("#ff7a1a"), 0.6)
        eye(p, x, 100, r, r * 0.9, hexc("#ff8a1a"), look=(-1, 0.1), lid=0.42, skin=skin)
    p.stroke([(180, 86), (198, 90)], hair, 2.4)
    p.stroke([(212, 90), (228, 86)], hair, 2.4)
    p.stroke(curve([(176, 104), (170, 116), (176, 118)], 3), shade(skin, 0.7), 1.6)
    p.shape("poly", curve([(184, 126), (194, 122), (204, 126), (194, 130)], 3) + [(184, 126)], hexc("#5a1a2a"),
            depth=0.3, line=1.0, rim=0)
    p.flat("ellipse", (178, 110, 192, 118), hexc("#ff7a6a", 60))
    # ---- horned ember crown
    for pts in ([(178, 64), (150, 36), (140, 4), (154, 14)], [(236, 62), (262, 30), (270, 0), (256, 14)]):
        p.shape("poly", taper(pts[:3], 24, 3), hexc("#3a2430"), depth=0.25, spec=0.8, tex="stone", tex_amt=0.5)
        p.glow(pts[2], 14, LAVA, 0.8)
        lava_crack(p, [pts[0], pts[1]], 1.6)
    p.shape("poly", [(170, 64), (182, 40), (194, 58), (208, 28), (222, 58), (234, 40), (244, 64), (242, 74),
                     (172, 74)], gold, depth=0.2, light=1.4, spec=1.0, tex="metal", tex_amt=0.4)
    p.glow((208, 56), 18, LAVA, 0.7)
    p.shape("poly", [(208, 44), (215, 56), (208, 68), (201, 56)], hexc("#ff7a1a"), line=1.0, light=1.6, gloss=1.0,
            rim=0)
    # ---- front arm holding the censer chain
    p.shape("poly", curve([(164, 160), (140, 180), (120, 196), (112, 216), (130, 222), (150, 200), (176, 186)], 5),
            robe, depth=0.2, tex="cloth", tex_amt=0.6)
    p.shape("line", [(112, 212), (132, 222)], gold, width=7, depth=0.3, spec=0.7, rim=0)
    chain(p, (104, 214), (80, 286), 9, hexc("#d8a840"), 8)
    p.shape("ellipse", (96, 196, 118, 220), skin, depth=0.25)
    # censer: pierced gold sphere with a lid, fire and smoke
    for x, y, r in ((70, 250, 14), (56, 226, 12), (44, 200, 10), (36, 172, 8)):
        smoke(p, x, y, r, 90, hexc("#b8a8b0"))
    p.glow((80, 312), 50, LAVA, 0.8)
    p.shape("ellipse", (56, 296, 104, 340), gold, depth=0.2, light=1.4, spec=1.0, tex="metal", tex_amt=0.4)
    for x, y in ((68, 312), (80, 318), (92, 312), (74, 328), (86, 328)):
        p.flat("ellipse", (x - 3, y - 3, x + 3, y + 3), hexc("#ffe07a"))
        p.glow((x, y), 8, LAVA, 0.6)
    p.shape("chord", (60, 284, 100, 312), shade(gold, 0.9), start=180, end=360, depth=0.3, spec=0.8)
    p.shape("ellipse", (76, 282, 84, 290), gold, line=1.0, rim=0)
    p.shape("ellipse", (62, 336, 98, 348), shade(gold, 0.8), depth=0.3, line=1.1, rim=0)
    flame(p, 80, 298, 26, 34, lean=-0.2, strength=0.6)
    # ---- floating embers
    for x, y, r in ((40, 60, 2.6), (100, 40, 2.2), (330, 60, 2.4), (350, 220, 2.2), (30, 150, 2), (120, 280, 2),
                    (320, 300, 2.2), (150, 120, 1.8), (280, 250, 1.8), (360, 140, 2), (20, 330, 2)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(50, 350, 350, 382))


# ------------------------------------------------------------------ dungeon 5: Ejder Yuvası

def ash(p, x, y, r, color=hexc("#9a9096")):
    """Drifting flake of ash."""
    p.shape("poly", [(x - r, y - r * 0.4), (x + r * 0.2, y - r * 0.8), (x + r, y + r * 0.2),
                     (x - r * 0.1, y + r * 0.7)],
            color, shadow=0.8, light=1.2, depth=0.3, line=0.8, rim=0, ao=0)


def dragon_guard():
    """Dragon-cult guard in bronze scale armour and a dragon-head helm, with a spear and tower shield
    (faces left)."""
    p = _painter(SIZE)
    obs = hexc("#34303e")
    bronze = hexc("#c08a3a")
    gold = hexc("#f0bb45")
    red = hexc("#a82a2a")
    # ---- spear in the back hand
    p.shape("line", [(200, 246), (196, 30)], hexc("#5a3a26"), width=7, depth=0.3, tex="wood")
    blade(p, (196, 40), (194, 0), 14, hexc("#d8e0e8"))
    p.shape("rect", (188, 36, 204, 46), gold, radius=3, depth=0.3, spec=0.8)
    for dx in (-6, -1, 4):
        p.shape("line", [(196 + dx * 0.4, 46), (196 + dx, 70)], red, width=4, depth=0.3, line=1.0, rim=0)
    # ---- back arm
    p.shape("line", [(170, 102), (188, 132), (196, 140)], obs, width=20, depth=0.2, spec=0.5, tex="metal")
    p.shape("ellipse", (184, 128, 210, 152), obs, depth=0.25, spec=0.7)
    # ---- legs
    for x in (102, 138):
        p.shape("rect", (x, 186, x + 24, 222), obs, radius=6, depth=0.2, spec=0.6, tex="metal")
        p.shape("rect", (x - 6, 216, x + 30, 238), shade(obs, 0.85), radius=8, depth=0.25, spec=0.5)
        p.stroke([(x, 200), (x + 24, 200)], gold, 2)
    # ---- scale armour: hauberk and tassets
    tas = p.shape("poly", [(88, 168), (178, 168), (184, 214), (82, 214)], bronze, depth=0.12, tex="metal",
                  tex_amt=0.5)
    scale_rows(p, tas, (82, 170, 186, 214), shade(bronze, 1.05), size=11)
    torso = p.shape("rect", (90, 94, 176, 176), bronze, radius=16, depth=0.14, tex="metal", tex_amt=0.5)
    scale_rows(p, torso, (90, 96, 176, 176), shade(bronze, 1.05), size=11)
    p.shape("rect", (86, 164, 180, 176), hexc("#4a2e1c"), radius=4, depth=0.3, tex="leather")
    p.shape("rect", (124, 160, 142, 180), gold, radius=3, depth=0.3, spec=0.9)
    # pauldrons shaped like scaled wings
    for cx in (170, 96):
        p.shape("ellipse", (cx - 24, 86, cx + 24, 122), obs, depth=0.2, spec=0.9, tex="metal")
        for i in range(3):
            p.stroke(curve([(cx - 20 + i * 4, 100 + i * 7), (cx, 106 + i * 7), (cx + 20 - i * 4, 100 + i * 7)], 4),
                     gold, 1.6)
    # ---- dragon-head helm: horns, crest, snout visor over a shadowed face
    for pts in ([(134, 34), (160, 18), (184, 20)], [(122, 28), (144, 6), (168, 2)]):
        p.shape("poly", taper(pts, 12, 2), hexc("#efe2c4"), depth=0.25, tex="bone", spec=0.5)
    p.shape("ellipse", (84, 22, 160, 104), obs, depth=0.14, spec=1.0, tex="metal", tex_amt=0.5)
    for x, y in ((150, 30), (158, 46), (160, 64)):
        p.shape("poly", [(x - 4, y), (x + 4, y + 4), (x + 16, y - 4)], gold, depth=0.3, line=1.0, rim=0)
    p.shape("ellipse", (82, 58, 136, 104), hexc("#140c10"), **NOLINE)
    for x, r in ((96, 5), (120, 4.5)):
        eye(p, x, 78, r, r * 0.8, hexc("#e8a020"), look=(-1, 0), lid=0.35, skin=hexc("#b88a6a"))
    p.stroke([(88, 70), (104, 74)], DARK, 2.4)
    p.stroke([(114, 74), (128, 70)], DARK, 2.4)
    snout = [(126, 36), (86, 42), (56, 56), (52, 66), (70, 70), (100, 64), (134, 60)]
    p.shape("poly", snout, obs, depth=0.2, spec=1.0, tex="metal")
    teeth(p, [(62, 68, 5, 8, 1), (74, 68, 5, 8, 1), (86, 66, 5, 8, 1)], hexc("#efe2c4"))
    p.shape("ellipse", (54, 54, 62, 60), hexc("#1a1418"), **NOLINE)
    glow_eye(p, 102, 46, 4.5, hexc("#ff7a1a"), socket=False)
    p.stroke(curve([(60, 58), (90, 48), (122, 44)], 4), gold, 1.8)
    p.shape("poly", [(84, 94), (112, 90), (132, 98), (110, 108), (86, 104)], obs, depth=0.25, spec=0.7)
    # ---- tower shield with a dragon emblem
    sm = p.shape("rect", (14, 84, 96, 234), obs, radius=10, depth=0.1, spec=0.6, tex="metal", tex_amt=0.6)
    from PIL import ImageChops
    rim = ImageChops.subtract(sm, p._mask("rect", (22, 92, 88, 226), radius=6))
    p.paint_mask(rim, gold, depth=0.25, spec=0.9, line=1.2, rim=0)
    rivets(p, [(18, 88), (92, 88), (18, 230), (92, 230), (18, 160), (92, 160)], 2, gold)
    p.glow((55, 150), 30, hexc("#ff7a1a"), 0.3)
    p.shape("poly", [(55, 116), (72, 126), (84, 118), (78, 138), (86, 160), (68, 154), (55, 184), (42, 154),
                     (24, 160), (32, 138), (26, 118), (38, 126)], gold, depth=0.25, light=1.4, spec=0.8, line=1.2)
    p.shape("poly", [(55, 132), (62, 148), (55, 164), (48, 148)], hexc("#ff7a1a"), line=1.0, gloss=1.0, rim=0)
    p.flat("rect", (53, 140, 57, 156), DARK, radius=2)
    for pts in (((30, 196), (44, 210)), ((70, 100), (80, 108))):
        p.stroke(list(pts), hexc("#8a8a9a", 180), 1.2)
    return p.finish(outline=3, ground_shadow=(8, 222, 226, 250))


def whelp():
    """Small red-orange dragon whelp, cute but furious, puffing smoke (faces left)."""
    p = _painter(SIZE)
    red = hexc("#e0502a")
    belly = hexc("#ffc05a")
    mem = hexc("#b83a2a")
    horn = hexc("#f4e2b8")
    # ---- wings (far one smaller)
    wing(p, (148, 112), [(166, 56), (196, 30), (206, 70), (190, 100)], shade(mem, 0.8), shade(red, 0.8), width=7)
    wing(p, (160, 118), [(194, 60), (238, 44), (236, 92), (208, 118)], mem, red, width=8, edge=hexc("#ffb060"))
    # ---- curled tail with a spade tip
    tail = [(170, 200), (214, 218), (240, 200), (238, 170)]
    p.shape("poly", taper(tail, 26, 10), red, depth=0.2, tex="leather", tex_amt=0.6)
    p.shape("poly", [(238, 148), (252, 172), (238, 180), (224, 170)], shade(red, 0.8), depth=0.3, light=1.3)
    # ---- body: pear shape, plated belly, spines
    for x, y in ((150, 100), (164, 116), (176, 136)):
        p.shape("poly", [(x - 6, y + 6), (x + 10, y - 8), (x + 8, y + 12)], belly, line=1.1, depth=0.3, rim=0)
    p.shape("ellipse", (84, 108, 188, 228), red, depth=0.12, tex="leather", tex_amt=0.6)
    p.shape("ellipse", (100, 128, 162, 226), belly, depth=0.18, line=1.2, rim=0, tex="leather", tex_amt=0.4)
    for y in (146, 162, 178, 194, 210):
        p.stroke([(104, y), (158, y + 2)], shade(belly, 0.72), 1.6)
    # ---- hind leg and foot
    p.shape("ellipse", (140, 164, 200, 224), red, depth=0.14, tex="leather", tex_amt=0.6)
    p.shape("ellipse", (122, 212, 176, 236), red, depth=0.25)
    for x in (126, 138, 150):
        p.shape("poly", [(x - 3, 230), (x + 3, 230), (x - 5, 240)], horn, line=0.9, rim=0, ao=0)
    # ---- little arms with claws
    p.shape("line", [(106, 148), (90, 170), (84, 178)], red, width=14, depth=0.2)
    p.shape("ellipse", (72, 170, 94, 188), red, depth=0.25)
    for x in (74, 80, 86):
        p.shape("poly", [(x - 2, 184), (x + 2, 184), (x - 3, 191)], horn, line=0.8, rim=0, ao=0)
    # ---- big head: horns, frills, angry face, smoking nostrils
    for pts in ([(122, 50), (140, 30), (160, 26)], [(104, 46), (116, 20), (134, 10)]):
        p.shape("poly", taper(pts, 12, 2), horn, depth=0.25, tex="bone", spec=0.4)
    p.shape("poly", [(146, 70), (172, 58), (164, 80), (178, 84), (156, 98)], shade(red, 0.85), depth=0.25)
    head = p.union([("ellipse", (54, 36, 162, 136)), ("ellipse", (22, 78, 92, 132))])
    p.paint_mask(head, red, depth=0.12, tex="leather", tex_amt=0.5)
    p.shape("chord", (30, 100, 110, 142), belly, start=0, end=180, depth=0.2, line=1.0, rim=0, clip=head)
    p.flat("ellipse", (98, 106, 114, 116), hexc("#ff8a8a", 110))
    eye(p, 70, 82, 10, 11, hexc("#e8a020"), look=(-1, 0.2), lid=0.3, skin=red)
    eye(p, 110, 80, 9, 10, hexc("#e8a020"), look=(-1, 0.2), lid=0.3, skin=red)
    p.shape("poly", [(54, 62), (86, 72), (84, 78), (52, 70)], shade(red, 0.55), depth=0.3, line=1.0, rim=0)
    p.shape("poly", [(96, 72), (126, 62), (128, 70), (98, 78)], shade(red, 0.55), depth=0.3, line=1.0, rim=0)
    p.stroke(curve([(40, 118), (60, 114), (80, 118)], 4), hexc("#5a1a1a"), 2.6)
    teeth(p, [(70, 117, 5, 7, 1)], hexc("#fff8e8"), line=0.8)
    p.flat("ellipse", (28, 94, 34, 100), hexc("#5a1a1a"))
    p.flat("ellipse", (40, 92, 46, 98), hexc("#5a1a1a"))
    for x, y, r in ((24, 70, 8), (14, 50, 10), (32, 34, 7), (8, 26, 6)):
        smoke(p, x, y, r, 150, hexc("#9a9098"))
    for x, y, r in ((200, 20, 1.8), (60, 210, 1.8), (228, 120, 1.6)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(50, 222, 246, 248))


def ash_wraith():
    """Ghostly figure of ash and smoke with burning eyes, tattered and trailing embers (faces left)."""
    p = _painter(SIZE)
    ashc = hexc("#6a6268")
    ash_l = hexc("#a09298")
    eyec = hexc("#ff8a1a")
    p.glow((120, 110), 110, hexc("#ff6a2a"), 0.14)
    # ---- smoky tendrils trailing below and behind
    for pts, w, a in (([(150, 170), (178, 212), (214, 232), (244, 226)], 28, 120),
                      ([(128, 180), (140, 214), (170, 240)], 24, 150),
                      ([(170, 150), (206, 170), (234, 168)], 22, 110)):
        p.shape("poly", taper(pts, w, 2), ashc[:3] + (a,), shadow=0.8, light=1.2, depth=0.2, line=0, rim=0, ao=0)
    # ---- ragged body
    body = curve([(98, 70), (160, 70), (178, 110), (186, 150), (194, 190), (176, 176), (170, 206), (152, 186),
                  (140, 220), (128, 190), (110, 212), (104, 180), (86, 198), (88, 150), (84, 110)], 5)
    p.shape("poly", body, ashc, depth=0.12, tex="noise", tex_amt=0.9)
    for pts in ([(110, 110), (104, 160), (110, 190)], [(150, 110), (160, 150), (164, 180)]):
        p.stroke(curve(pts, 4), shade(ashc, 0.6), 2)
    for pts in ([(122, 120), (128, 140), (120, 160)], [(146, 150), (150, 166)]):
        lava_crack(p, pts, 1.8)
    # ---- back arm reaching
    p.shape("poly", taper([(168, 96), (196, 118), (214, 108)], 24, 12), ashc, depth=0.2, tex="noise")
    for dx, dy in ((0, -8), (8, -4), (10, 6)):
        p.shape("poly", taper([(212, 108), (224 + dx, 100 + dy)], 5, 1), hexc("#3a3438"), depth=0.3, line=1.0, rim=0)
    # ---- tattered hood and a void face with burning eyes
    hood = p.union([("ellipse", (78, 18, 170, 116)), ("poly", [(140, 26), (176, 10), (160, 46)])])
    p.paint_mask(hood, ash_l, depth=0.12, tex="noise", tex_amt=0.9)
    p.shape("poly", [(80, 96), (90, 120), (100, 104), (110, 124), (118, 106), (128, 122), (136, 104), (150, 118),
                     (166, 96)], ash_l, depth=0.2, tex="noise")
    p.shape("ellipse", (84, 40, 150, 108), hexc("#0e080c"), depth=0.2, line=1.0, rim=0)
    glow_eye(p, 102, 72, 7, eyec, socket=False)
    glow_eye(p, 130, 70, 6, eyec, socket=False)
    p.stroke([(92, 62), (112, 68)], hexc("#ff5a1a", 180), 1.8)
    p.stroke([(122, 66), (140, 60)], hexc("#ff5a1a", 180), 1.8)
    # ---- front arm reaching with ashen claws
    p.shape("poly", taper([(94, 104), (64, 128), (40, 124)], 26, 14), ash_l, depth=0.2, tex="noise")
    p.shape("poly", [(70, 136), (60, 150), (54, 138), (46, 148), (44, 134)], ash_l, depth=0.25)
    for dx, dy in ((-4, -12), (-12, -4), (-10, 8), (-2, 12)):
        p.shape("poly", taper([(40, 124), (28 + dx, 124 + dy)], 6, 1), hexc("#3a3438"), depth=0.3, line=1.0, rim=0)
        ember(p, 28 + dx, 124 + dy, 1.4)
    # ---- ash and embers drifting
    for x, y, r in ((30, 60, 4), (210, 40, 3.5), (60, 190, 3), (230, 130, 3), (180, 20, 3), (20, 210, 3.5)):
        ash(p, x, y, r)
    for x, y, r in ((50, 30, 1.8), (196, 70, 1.8), (90, 230, 1.6), (240, 200, 2), (160, 236, 1.6)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(70, 226, 200, 248))


def elder_drake():
    """Elite: huge wingless bronze drake with heavy horns and old battle scars (faces left)."""
    p = _painter(SIZE)
    bronze = hexc("#b8783a")
    bronze_d = hexc("#7a4a24")
    belly = hexc("#e8c890")
    horn = hexc("#ece0c4")
    scar = hexc("#f0c8a8")
    # ---- tail
    p.shape("poly", taper([(206, 150), (238, 176), (246, 212), (226, 234)], 40, 8), bronze, depth=0.16,
            tex="leather", tex_amt=0.7)
    for x, y in ((230, 164), (244, 190), (242, 214)):
        p.shape("poly", [(x - 4, y - 2), (x + 10, y - 6), (x + 4, y + 8)], bronze_d, line=1.0, depth=0.3, rim=0)
    # ---- far legs
    p.shape("line", [(110, 172), (104, 214), (104, 232)], shade(bronze, 0.75), width=26, depth=0.2, tex="leather")
    p.shape("line", [(190, 170), (208, 208), (204, 232)], shade(bronze, 0.75), width=26, depth=0.2, tex="leather")
    # ---- back spines and body
    for i, x in enumerate(range(96, 214, 16)):
        y = 78 + (x - 150) ** 2 * 0.004
        p.shape("poly", [(x - 8, y + 14), (x + 4, y - 14 + (i % 2) * 4), (x + 10, y + 14)], bronze_d, depth=0.25,
                line=1.2, spec=0.4)
    bm = p.shape("ellipse", (64, 74, 230, 196), bronze, depth=0.12, tex="leather", tex_amt=0.7)
    scale_rows(p, bm, (80, 76, 230, 140), shade(bronze, 1.08), size=13)
    p.shape("chord", (70, 120, 224, 214), belly, start=0, end=180, depth=0.2, line=1.2, rim=0, clip=bm,
            tex="leather", tex_amt=0.4)
    for x in range(96, 212, 14):
        p.stroke([(x, 170), (x + 2, 194)], shade(belly, 0.72), 1.6)
    for pts in ([(150, 96), (176, 118), (168, 142)], [(186, 104), (200, 130)]):
        p.stroke(pts, scar, 3)
        p.stroke(pts, shade(scar, 0.7), 1)
    # ---- near legs with heavy claws
    p.shape("ellipse", (166, 116, 230, 196), bronze, depth=0.14, tex="leather", tex_amt=0.7)
    p.shape("line", [(200, 180), (212, 210), (206, 226)], bronze, width=28, depth=0.2, tex="leather")
    p.shape("ellipse", (182, 218, 226, 240), bronze, depth=0.25)
    p.shape("line", [(98, 150), (86, 196), (84, 222)], bronze, width=30, depth=0.2, tex="leather")
    p.shape("ellipse", (58, 214, 104, 240), bronze, depth=0.25)
    for x0 in (60, 184):
        for dx in (0, 12, 24):
            p.shape("poly", [(x0 + dx - 3, 232), (x0 + dx + 5, 232), (x0 + dx - 5, 244)], horn, line=0.9, rim=0,
                    ao=0)
    # ---- head low and forward, heavy jaw, horns, a scarred eye
    far_horn = [(66, 80), (86, 48), (118, 32), (148, 34)]
    p.shape("poly", taper(far_horn, 20, 3), shade(horn, 0.82), depth=0.2, tex="bone", tex_amt=0.8)
    p.shape("poly", [(10, 128), (70, 132), (84, 146), (60, 156), (20, 150)], shade(bronze, 0.85), depth=0.25,
            tex="leather")
    head = p.union([("poly", curve([(108, 78), (76, 72), (44, 86), (10, 100), (0, 116), (8, 132), (50, 138),
                                    (96, 140), (118, 116)], 5))])
    p.paint_mask(head, bronze, depth=0.12, tex="leather", tex_amt=0.7)
    scale_rows(p, head, (60, 76, 116, 100), shade(bronze, 1.08), size=10)
    p.stroke(curve([(8, 130), (40, 128), (70, 124), (98, 128)], 5), bronze_d, 2)
    near_horn = [(76, 88), (104, 62), (140, 54), (166, 66)]
    p.shape("poly", taper(near_horn, 26, 4), horn, depth=0.2, tex="bone", tex_amt=0.8, spec=0.4)
    for x, y in along(curve(near_horn, 6), 11)[1:-1]:
        p.stroke([(x - 3, y - 9), (x + 3, y + 9)], shade(horn, 0.68), 1.6)
    teeth(p, [(20, 132, 6, 10, 1), (36, 134, 6, 10, 1), (54, 135, 7, -12, 1)], hexc("#f4ecd8"))
    for x in (4, 12):
        p.shape("poly", [(x + 28, 146), (x + 34, 146), (x + 30, 162)], horn, line=0.9, rim=0)
    p.shape("ellipse", (6, 110, 16, 118), hexc("#2a1a14"), **NOLINE)
    glow_eye(p, 62, 100, 6.5, hexc("#ffb020"))
    p.shape("poly", [(38, 86), (58, 80), (84, 86), (80, 96), (60, 92), (42, 96)], bronze_d, depth=0.3, line=1.2,
            rim=0, spec=0.4)
    p.shape("poly", [(4, 102), (20, 96), (30, 104), (14, 110)], bronze_d, depth=0.3, line=1.0, rim=0)
    p.stroke([(52, 82), (66, 104), (76, 118)], scar, 3.2)
    p.stroke([(52, 82), (66, 104), (76, 118)], shade(scar, 0.7), 1)
    p.stroke([(24, 112), (38, 124)], scar, 2.6)
    # chin spikes
    for x in (74, 86, 98):
        p.shape("poly", [(x - 4, 136), (x + 4, 136), (x + 2, 152)], bronze_d, line=1.0, depth=0.3, rim=0)
    return p.finish(outline=3, ground_shadow=(6, 222, 250, 250))


def ashwing():
    """Final boss: Kül Kanat, a huge grey-black dragon with ember-lined wings spread wide, glowing eyes and a
    molten core, ash drifting all around (faces left)."""
    p = _painter(BOSS_SIZE)
    dark = hexc("#4a4552")
    dark_d = hexc("#34303c")
    dark_l = hexc("#6a6272")
    mem = hexc("#3a2232")
    belly = hexc("#7a6660")
    horn = hexc("#221c24")
    bonec = hexc("#d8ccb8")
    ember_c = hexc("#ff8a2a")
    p.glow((200, 190), 220, hexc("#ff4a1a"), 0.26)
    p.glow((200, 100), 170, hexc("#ff7a1a"), 0.12)
    # ---- far wing spread to the right
    wing(p, (238, 178), [(292, 72), (370, 26), (374, 126), (360, 194), (318, 236)], shade(mem, 0.85), dark_d,
         width=15, edge=hexc("#ffb050"), glow=ember_c, scallop=0.26)
    lava_crack(p, [(238, 178), (292, 72)], 1.4, glow=False)
    # ---- tail sweeping around the bottom right with ember spikes
    tail = [(268, 300), (320, 322), (360, 344), (380, 316), (372, 286)]
    for x, y in along(curve(tail, 6), 22)[:6]:
        p.shape("poly", [(x - 7, y - 10), (x + 3, y - 30), (x + 9, y - 10)], horn, depth=0.3, line=1.2, spec=0.5)
        ember(p, x + 3, y - 28, 1.8)
    p.shape("poly", taper(tail, 52, 10), dark, depth=0.14, tex="leather", tex_amt=0.7)
    p.shape("poly", [(366, 290), (384, 262), (380, 296)], horn, depth=0.3, line=1.2)
    # ---- near wing raised up and back behind the head
    wing(p, (196, 170), [(170, 56), (96, 4), (30, 40), (8, 118), (52, 170), (130, 196)], mem, dark_d, width=16,
         edge=hexc("#ffb050"), glow=ember_c, scallop=0.26)
    lava_crack(p, [(196, 170), (170, 56)], 1.4, glow=False)
    # ---- far front leg, hind legs crouched
    p.shape("line", [(236, 270), (238, 322), (230, 352)], dark_d, width=30, depth=0.2, tex="leather")
    p.shape("ellipse", (206, 342, 252, 366), dark_d, depth=0.25)
    p.shape("ellipse", (248, 246, 330, 336), dark, depth=0.14, tex="leather", tex_amt=0.8)
    p.shape("line", [(300, 312), (286, 350), (278, 362)], dark, width=30, depth=0.2, tex="leather")
    p.shape("ellipse", (246, 346, 304, 372), dark, depth=0.25)
    for x in (252, 266, 280):
        p.shape("poly", [(x - 4, 366), (x + 5, 366), (x - 6, 380)], bonec, line=0.9, rim=0, ao=0)
    # ---- neck spines and neck (the torso covers its base)
    neck = [(216, 214), (182, 170), (150, 146), (116, 132)]
    for x, y in along(curve(neck, 6), 20)[:6]:
        p.shape("poly", [(x + 8, y - 22), (x + 30, y - 40), (x + 28, y - 14)], horn, depth=0.3, line=1.2, spec=0.5)
    p.shape("poly", taper(neck, 80, 56), dark, depth=0.14, tex="leather", tex_amt=0.8)
    for x, y in along(curve(neck, 6), 12)[1:-2]:
        p.stroke([(x - 32, y + 6), (x - 14, y + 24)], belly, 3.4)
    # ---- torso with a glowing molten chest
    bm = p.shape("ellipse", (160, 154, 300, 330), dark, depth=0.12, tex="leather", tex_amt=0.8)
    for x, y in ((270, 190), (284, 214), (262, 176), (288, 244)):
        p.shape("poly", [(x - 8, y + 6), (x, y - 6), (x + 8, y + 6)], dark_l, depth=0.3, line=1.0, rim=0)
    p.glow((214, 256), 76, ember_c, 0.6)
    chest = curve([(212, 188), (246, 204), (262, 256), (252, 314), (214, 336), (178, 318), (166, 262), (180, 206)], 6)
    p.shape("poly", chest, belly, depth=0.16, line=1.3, rim=0, clip=bm, tex="stone", tex_amt=0.6)
    for y in range(204, 330, 16):
        w = 40 - abs(y - 262) * 0.3
        p.stroke(curve([(214 - w, y - 2), (214, y + 4), (214 + w, y - 2)], 4), shade(belly, 0.6), 2)
    for pts in ([(214, 196), (204, 228), (218, 258), (208, 292), (220, 318)], [(204, 228), (182, 240)],
                [(218, 258), (242, 270)], [(208, 292), (188, 300)]):
        lava_crack(p, pts, 2.8)
    # ---- near front leg planted, big claws
    p.shape("ellipse", (160, 226, 216, 290), dark, depth=0.14, tex="leather", tex_amt=0.8)
    p.shape("line", [(186, 270), (162, 312), (164, 348)], dark, width=34, depth=0.18, tex="leather")
    p.shape("ellipse", (130, 338, 190, 370), dark, depth=0.25)
    for x in (134, 148, 162):
        p.shape("poly", [(x - 4, 362), (x + 5, 362), (x - 6, 380)], bonec, line=0.9, rim=0, ao=0)
    # ---- head: swept horns, crest, glowing eye, maw full of fire
    for pts, w in (([(136, 96), (178, 64), (222, 52), (248, 60)], 22),
                   ([(126, 88), (148, 50), (170, 22), (190, 10)], 24)):
        p.shape("poly", taper(pts, w, 2), horn, depth=0.25, spec=0.9, tex="stone", tex_amt=0.5)
        p.glow(pts[-1], 16, ember_c, 0.7)
        lava_crack(p, pts[:3], 1.4, glow=False)
    p.glow((44, 160), 52, ember_c, 0.85)
    p.shape("poly", [(22, 150), (96, 154), (112, 172), (70, 184), (26, 170)], shade(dark, 0.9), depth=0.25,
            tex="leather")
    p.shape("poly", [(22, 148), (98, 150), (98, 160), (30, 164)], hexc("#ff7a1a"), **NOLINE)
    p.shape("poly", [(34, 152), (90, 154), (86, 158), (40, 160)], hexc("#ffe07a"), **NOLINE)
    teeth(p, [(34, 162, 7, -10, 1), (52, 164, 7, -10, 1), (70, 165, 7, -10, 1)], hexc("#f4e8d0"))
    head = p.union([("ellipse", (72, 78, 164, 162)),
                    ("poly", [(96, 96), (40, 112), (14, 128), (18, 148), (60, 152), (112, 154)])])
    p.paint_mask(head, dark, depth=0.12, tex="leather", tex_amt=0.8)
    teeth(p, [(26, 146, 6, 10, 1), (42, 148, 7, 11, 1), (60, 149, 7, 10, 1), (78, 150, 6, 9, 1)], hexc("#f4e8d0"))
    for x, y in ((150, 132), (158, 150), (146, 164)):
        p.shape("poly", [(x - 4, y - 6), (x + 22, y), (x - 2, y + 6)], horn, depth=0.3, line=1.1)
    p.shape("ellipse", (22, 124, 32, 132), hexc("#140c10"), **NOLINE)
    p.glow((26, 128), 8, ember_c, 0.5)
    lava_crack(p, [(40, 124), (70, 116), (96, 114)], 1.6)
    p.shape("poly", [(92, 96), (136, 94), (132, 104), (96, 108)], hexc("#1a1418"), **NOLINE)
    p.glow((114, 102), 24, hexc("#ffd040"), 0.85)
    p.shape("poly", [(98, 100), (116, 96), (130, 100), (114, 108)], hexc("#ffcf3a"), light=1.5, line=0.9, rim=0)
    p.flat("rect", (112, 97, 116, 107), DARK, radius=2)
    p.shape("poly", [(88, 88), (140, 84), (136, 94), (92, 96)], dark_l, depth=0.3, line=1.2, rim=0, spec=0.4)
    # ---- ash and embers drifting everywhere
    for x, y, r in ((30, 250, 4), (90, 300, 3.5), (340, 260, 3.5), (250, 30, 3), (60, 214, 3), (360, 350, 3),
                    (210, 20, 2.6), (20, 330, 3), (318, 110, 2.6), (120, 230, 2.6)):
        ash(p, x, y, r)
    for x, y, r in ((60, 270, 2.2), (110, 320, 2), (330, 170, 2), (236, 110, 1.8), (16, 196, 2), (372, 240, 2.2),
                    (96, 206, 1.8), (310, 372, 1.8), (150, 30, 1.6), (270, 16, 1.8)):
        ember(p, x, y, r)
    return p.finish(outline=3, ground_shadow=(40, 346, 380, 382))


SPRITES = {
    "player/warrior": warrior,
    "player/mage": mage,
    "player/rogue": rogue,
    "enemies/cellar_rat": cellar_rat,
    "enemies/skeleton_guard": skeleton_guard,
    "enemies/mushroom_mage": mushroom_mage,
    "enemies/cellar_warden": cellar_warden,
    "enemies/mimic": mimic,
    "enemies/bone_king": bone_king,
    # dungeon 2: Mantar Mağarası
    "enemies/cave_slime": cave_slime,
    "enemies/toxic_toad": toxic_toad,
    "enemies/glow_bat": glow_bat,
    "enemies/shroom_brute": shroom_brute,
    "enemies/spore_mother": spore_mother,
    # dungeon 3: Buzlu Geçit
    "enemies/frost_wolf": frost_wolf,
    "enemies/ice_wisp": ice_wisp,
    "enemies/yeti_cub": yeti_cub,
    "enemies/ice_troll": ice_troll,
    "enemies/frostbreath": frostbreath,
    # dungeon 4: Yanık Kale
    "enemies/cultist": cultist,
    "enemies/fire_imp": fire_imp,
    "enemies/ember_hound": ember_hound,
    "enemies/flame_knight": flame_knight,
    "enemies/ember_priestess": ember_priestess,
    # dungeon 5: Ejder Yuvası
    "enemies/dragon_guard": dragon_guard,
    "enemies/whelp": whelp,
    "enemies/ash_wraith": ash_wraith,
    "enemies/elder_drake": elder_drake,
    "enemies/ashwing": ashwing,
}

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


SPRITES = {
    "player/warrior": warrior,
    "enemies/cellar_rat": cellar_rat,
    "enemies/skeleton_guard": skeleton_guard,
    "enemies/mushroom_mage": mushroom_mage,
    "enemies/cellar_warden": cellar_warden,
    "enemies/mimic": mimic,
    "enemies/bone_king": bone_king,
}

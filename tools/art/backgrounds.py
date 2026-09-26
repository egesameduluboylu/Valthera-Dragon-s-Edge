"""Dungeon backgrounds: walls and floors drawn with ImageDraw at 2x, props with the soft
Painter, then a lighting pass (ambient + torch light pools), texture and a vignette."""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import painter
from painter import Painter, hexc, mix, shade

W, H = 720, 720   # battle stage size
K = 2             # draw scale

INK = (22, 14, 20, 255)
NOLINE = dict(shadow=0, light=0, line=0)


# ------------------------------------------------------------------ raw layers

def _brick_wall(d, rng, top, bottom, base, mortar, width=None, row_h=44):
    """Brick courses with bevels, chips, cracks, moss and grime (in 1x coordinates)."""
    width = width or W
    d.rectangle((0, top * K, width * K, bottom * K), fill=mortar)
    y = top
    row = 0
    while y < bottom:
        x = -rng.randint(0, 60) if row % 2 else -rng.randint(40, 90)
        while x < width:
            w = rng.randint(70, 112)
            c = shade(base, rng.uniform(0.82, 1.1))
            c = mix(c, hexc("#626068"), rng.uniform(0, 0.4))  # some greyer stones
            x0, y0, x1, y1 = (x + 3) * K, (y + 3) * K, (x + w - 3) * K, (y + row_h - 3) * K
            d.rounded_rectangle((x0, y0, x1, y1), radius=7 * K, fill=shade(c, 0.7))
            d.rounded_rectangle((x0, y0, x1 - 3 * K, y1 - 4 * K), radius=7 * K, fill=c)
            # bevel: lit top-left edge, dark lower edge
            d.line((x0 + 7 * K, y0 + 3 * K, x1 - 10 * K, y0 + 3 * K), fill=shade(c, 1.16), width=2 * K)
            d.line((x0 + 3 * K, y0 + 7 * K, x0 + 3 * K, y1 - 10 * K), fill=shade(c, 1.1), width=2 * K)
            if rng.random() < 0.28:  # chipped corner
                cx, cy = (x0, y0) if rng.random() < 0.5 else (x1 - 3 * K, y1 - 4 * K)
                s = rng.randint(4, 9) * K
                sgn = 1 if cx == x0 else -1
                d.polygon([(cx, cy), (cx + sgn * s, cy), (cx, cy + sgn * s)], fill=mortar)
            if rng.random() < 0.16:  # crack
                px, py = rng.uniform(x0 + 10 * K, x1 - 10 * K), y0 + 4 * K
                pts = [(px, py)]
                for _ in range(3):
                    px += rng.uniform(-8, 8) * K
                    py += rng.uniform(6, 11) * K
                    pts.append((px, min(py, y1 - 5 * K)))
                d.line(pts, fill=shade(c, 0.5), width=K + 1)
            if rng.random() < 0.09:  # moss creeping out of the mortar
                mx = x + rng.randint(10, max(11, w - 40))
                for i in range(5):
                    ox = mx + i * 7 + rng.uniform(-3, 3)
                    oy = y + row_h - 6 + rng.uniform(-3, 4)
                    r = rng.uniform(5, 9)
                    d.ellipse(((ox - r) * K, (oy - r * 0.7) * K, (ox + r) * K, (oy + r * 0.7) * K),
                              fill=mix(hexc("#4f6b3a"), hexc("#6f8a44"), rng.random())[:3] + (220,))
            x += w
        y += row_h
        row += 1


def _grime(img, rng, top, bottom, n, width=None):
    """Dark water streaks running down the wall."""
    width = width or W
    layer = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        x = rng.uniform(0, width)
        y = rng.uniform(top, bottom - 120)
        ln = rng.uniform(60, 180)
        wd = rng.uniform(6, 16)
        for i in range(12):
            t = i / 12
            d.line((x * K, (y + ln * t) * K, x * K, (y + ln * (t + 0.1)) * K), fill=int(90 * (1 - t)),
                   width=int(wd * (1 - t * 0.6) * K))
    layer = layer.filter(ImageFilter.GaussianBlur(3 * K))
    dark = Image.new("RGBA", img.size, (20, 26, 18, 255))
    dark.putalpha(layer)
    img.alpha_composite(dark)


def _floor(d, rng, top, height=None, width=None):
    """Flagstones in perspective: rows get taller toward the viewer."""
    height = height or H
    width = width or W
    d.rectangle((0, top * K, width * K, height * K), fill=hexc("#1e161c"))
    y = top
    h = 26
    while y < height:
        x = -rng.randint(0, 80)
        depth = (y - top) / max(1, height - top)
        while x < width:
            w = rng.randint(90, 160) * (0.8 + depth * 0.5)
            c = shade(hexc("#5e4e48"), rng.uniform(0.82, 1.06) * (0.72 + 0.34 * depth))
            c = mix(c, hexc("#4a4a5a"), rng.uniform(0, 0.3))
            x0, y0, x1, y1 = (x + 3) * K, (y + 3) * K, (x + w - 3) * K, (y + h - 3) * K
            d.rounded_rectangle((x0, y0, x1, y1), radius=9 * K, fill=shade(c, 0.66))
            d.rounded_rectangle((x0, y0, x1 - 2 * K, y1 - 3 * K), radius=9 * K, fill=c)
            d.line((x0 + 10 * K, y0 + 3 * K, x1 - 12 * K, y0 + 3 * K), fill=shade(c, 1.14), width=2 * K)
            if rng.random() < 0.2:
                px = rng.uniform(x0 + 12 * K, x1 - 12 * K)
                d.line((px, y0 + 4 * K, px + rng.uniform(-14, 14) * K, y1 - 5 * K), fill=shade(c, 0.5), width=K + 1)
            x += w
        y += h
        h = int(h * 1.2)


def _texture(img, kind="stone", amount=0.55, clip=None):
    """Overlays a painter texture (lights and darks) on the whole image or a mask."""
    t = painter.texture(kind, img.size, ss=K)
    gain = int(255 * amount)
    hi = t.point(lambda v: max(0, min(255, (v - 128) * gain // 128)))
    lo = t.point(lambda v: max(0, min(255, (128 - v) * gain // 128)))
    if clip is not None:
        hi = ImageChops.multiply(hi, clip)
        lo = ImageChops.multiply(lo, clip)
    light = Image.new("RGBA", img.size, (255, 236, 210, 0))
    light.putalpha(hi.point(lambda v: v // 3))
    dark = Image.new("RGBA", img.size, (14, 8, 20, 0))
    dark.putalpha(lo.point(lambda v: v // 2))
    img.alpha_composite(light)
    img.alpha_composite(dark)


def _radial(size, cx, cy, rx, ry, power=1.6):
    """L image: 255 at (cx, cy) falling to 0 at the radii (1x coordinates)."""
    small = Image.new("L", (size[0] // 8, size[1] // 8), 0)
    d = ImageDraw.Draw(small)
    steps = 24
    s = K / 8
    for i in range(steps, 0, -1):
        t = i / steps
        v = int(255 * (1 - t) ** power)
        d.ellipse(((cx - rx * t) * s, (cy - ry * t) * s, (cx + rx * t) * s, (cy + ry * t) * s), fill=v)
    return small.filter(ImageFilter.GaussianBlur(2)).resize(size, Image.BILINEAR)


def _light(img, ambient, pools):
    """Multiplies the scene by a light map: ambient colour plus coloured light pools.

    pools: (cx, cy, rx, ry, color, strength) in 1x coordinates."""
    lm = Image.new("RGB", img.size, ambient)
    for cx, cy, rx, ry, color, strength in pools:
        m = _radial(img.size, cx, cy, rx, ry).point(lambda v: int(v * strength))
        col = Image.new("RGB", img.size, color[:3])
        lm = ImageChops.add(lm, ImageChops.multiply(col, Image.merge("RGB", (m, m, m))))
    rgb = img.convert("RGB")
    lit = ImageChops.multiply(rgb, lm)
    # lights above 128 in the map brighten past the base colour (screen the excess)
    boost = lm.point(lambda v: max(0, (v - 150) * 2))
    lit = ImageChops.screen(lit, ImageChops.multiply(rgb, boost))
    out = lit.convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


def _glow(img, cx, cy, r, color, strength):
    m = _radial(img.size, cx, cy, r, r, 2.0).point(lambda v: v * strength // 255)
    layer = Image.new("RGBA", img.size, color[:3] + (0,))
    layer.putalpha(m)
    img.alpha_composite(layer)


def _vignette(img, strength=200):
    v = Image.new("L", (img.size[0] // 8, img.size[1] // 8), 0)
    d = ImageDraw.Draw(v)
    w, h = v.size
    steps = 40
    for i in range(steps):
        t = i / steps
        d.rectangle((int(w * t / 4), int(h * t / 4), int(w - w * t / 4), int(h - h * t / 4)), fill=int(255 * t))
    v = v.filter(ImageFilter.GaussianBlur(5)).resize(img.size, Image.BILINEAR)
    dark = Image.new("RGBA", img.size, (8, 4, 12, 255))
    dark.putalpha(v.point(lambda a: max(0, strength - int(a * strength / 255 * 1.0))))
    img.alpha_composite(dark)


# ------------------------------------------------------------------ props (soft Painter at K)

def _props_painter(img):
    p = Painter(img.size[0] // K, img.size[1] // K, soft=True)
    p.img = img
    p.solid = Image.new("L", img.size, 0)
    return p


def torch(p, cx, cy, s=1.0):
    """Wall torch in an iron sconce; flame centred just above (cx, cy)."""
    wood = hexc("#5a3a24")
    iron = hexc("#4b4f57")
    p.shape("rect", (cx - 16 * s, cy + 44 * s, cx + 16 * s, cy + 60 * s), iron, radius=3, depth=0.3, spec=0.5,
            tex="metal")
    p.shape("poly", [(cx - 7 * s, cy + 6 * s), (cx + 7 * s, cy + 6 * s), (cx + 4 * s, cy + 58 * s),
                     (cx - 4 * s, cy + 58 * s)], wood, depth=0.3, tex="wood")
    p.shape("poly", [(cx - 18 * s, cy - 4 * s), (cx + 18 * s, cy - 4 * s), (cx + 11 * s, cy + 14 * s),
                     (cx - 11 * s, cy + 14 * s)], iron, depth=0.25, spec=0.6, tex="metal")
    for dx in (-10, 0, 10):
        p.stroke([(cx + dx * s, cy - 2 * s), (cx + dx * 0.7 * s, cy + 12 * s)], hexc("#2a2a30"), 1.4 * s)
    p.glow((cx, cy - 20 * s), 60 * s, hexc("#ffa040"), 0.55)
    outer = [(cx - 16 * s, cy - 4 * s), (cx - 18 * s, cy - 22 * s), (cx - 8 * s, cy - 36 * s), (cx - 6 * s, cy - 26 * s),
             (cx + 2 * s, cy - 56 * s), (cx + 8 * s, cy - 30 * s), (cx + 16 * s, cy - 40 * s), (cx + 18 * s, cy - 18 * s),
             (cx + 16 * s, cy - 4 * s)]
    p.shape("poly", outer, hexc("#ff7a24"), shadow=0.85, light=1.4, depth=0.2, line=1.2, ink=hexc("#8a2a10"), rim=0,
            ao=0)
    p.shape("poly", [(cx - 9 * s, cy - 4 * s), (cx - 8 * s, cy - 20 * s), (cx, cy - 38 * s), (cx + 8 * s, cy - 20 * s),
                     (cx + 9 * s, cy - 4 * s)], hexc("#ffc248"), **NOLINE)
    p.shape("poly", [(cx - 4 * s, cy - 4 * s), (cx, cy - 22 * s), (cx + 4 * s, cy - 4 * s)], hexc("#fff4c0"),
            **NOLINE)
    for i in range(3):  # sparks
        p.flat("ellipse", (cx + (i * 9 - 8) * s - 1.2, cy - (62 + i * 12) * s - 1.2, cx + (i * 9 - 8) * s + 1.2,
                           cy - (62 + i * 12) * s + 1.2), hexc("#ffd070"))


def barrel(p, x, y, w=62, h=84, lid=True):
    wood = hexc("#7a4e2a")
    iron = hexc("#4b4f57")
    body = p.union([("rect", (x, y + 6, x + w, y + h - 6), {"radius": 10}),
                    ("ellipse", (x - 3, y + 10, x + w + 3, y + h - 10))])
    p.paint_mask(body, wood, depth=0.18, tex="wood", tex_amt=1.0)
    for i in range(1, 5):
        sx = x + w * i / 5
        p.stroke([(sx, y + 8), (sx + (sx - x - w / 2) * 0.08, y + h / 2), (sx, y + h - 8)], shade(wood, 0.55), 1.4)
    for yy in (y + 18, y + h - 20):
        p.shape("rect", (x - 2, yy - 4, x + w + 2, yy + 4), iron, radius=3, depth=0.3, spec=0.5, tex="metal")
    if lid:
        p.shape("ellipse", (x + 2, y, x + w - 2, y + 14), shade(wood, 1.08), depth=0.3, tex="wood_h", line=1.4)


def crate(p, x, y, w, h):
    wood = hexc("#8a5e34")
    p.shape("rect", (x, y, x + w, y + h), wood, radius=3, depth=0.14, tex="wood_h", tex_amt=1.0)
    for i in range(1, 3):
        p.stroke([(x + 4, y + h * i / 3), (x + w - 4, y + h * i / 3)], shade(wood, 0.5), 1.5)
    p.shape("line", [(x + 6, y + 6), (x + w - 6, y + h - 6)], shade(wood, 1.08), width=7, depth=0.3, tex="wood")
    for xx in (x, x + w - 8):
        p.shape("rect", (xx, y, xx + 8, y + h), shade(wood, 0.92), radius=2, depth=0.3, tex="wood")


def skull(p, cx, cy, s=1.0, rot=0):
    c = hexc("#d8cfb4")
    p.shape("ellipse", (cx - 16 * s, cy - 15 * s, cx + 16 * s, cy + 12 * s), c, depth=0.2, tex="bone")
    p.shape("rect", (cx - 9 * s, cy + 4 * s, cx + 9 * s, cy + 16 * s), c, radius=3 * s, depth=0.3, tex="bone")
    for dx in (-7, 7):
        p.flat("ellipse", (cx + (dx - 5) * s, cy - 5 * s, cx + (dx + 5) * s, cy + 4 * s), hexc("#1a1018"))
    for dx in (-5, 0, 5):
        p.stroke([(cx + dx * s, cy + 10 * s), (cx + dx * s, cy + 16 * s)], hexc("#3a2a26"), 1.2)


def bones(p, x, y, s=1.0):
    c = hexc("#d8cfb4")
    for (ax, ay), (bx, by) in (((x - 24 * s, y), (x + 18 * s, y - 8 * s)), ((x - 12 * s, y - 12 * s), (x + 22 * s, y + 4 * s))):
        p.shape("line", [(ax, ay), (bx, by)], c, width=6 * s, depth=0.3, line=1.2, tex="bone")
        for ex, ey in ((ax, ay), (bx, by)):
            p.shape("ellipse", (ex - 5 * s, ey - 5 * s, ex + 5 * s, ey + 5 * s), c, depth=0.3, line=1.2, rim=0)


def chain(p, cx, top, n, size=14):
    iron = hexc("#4f535c")
    for i in range(n):
        y = top + i * size * 0.85
        if i % 2:
            p.shape("rect", (cx - 2.5, y - size * 0.5, cx + 2.5, y + size * 0.5), iron, radius=2, line=1.2, depth=0.3,
                    spec=0.5, rim=0)
        else:
            ring = ImageChops.subtract(p._mask("ellipse", (cx - size * 0.4, y - size * 0.55, cx + size * 0.4, y + size * 0.55)),
                                       p._mask("ellipse", (cx - size * 0.18, y - size * 0.32, cx + size * 0.18, y + size * 0.32)))
            p.paint_mask(ring, iron, line=1.2, depth=0.3, spec=0.5, rim=0)


def cobweb(p, sx, sy, flip, size=110):
    col = (226, 226, 236, 110)
    angles = [math.radians(a if flip > 0 else 180 - a) for a in (4, 26, 50, 72, 88)]
    for ang in angles:
        p.stroke([(sx, sy), (sx + size * math.cos(ang), sy + size * math.sin(ang))], col, 1.2)
    for r in (30, 56, 82):
        pts = []
        for i, ang in enumerate(angles):
            rr = r * (0.94 if i % 2 else 1.0)
            pts.append((sx + rr * math.cos(ang), sy + rr * math.sin(ang)))
        for a, b in zip(pts, pts[1:]):
            mid = ((a[0] + b[0]) / 2 - flip * 2, (a[1] + b[1]) / 2 - 3)
            p.stroke([a, mid, b], col, 1.1)


def arch(p, cx, top, w, h, rng):
    """Barred archway into darkness, with bevelled voussoirs."""
    stone = hexc("#6e6470")
    hole = p.union([("rect", (cx - w / 2, top + w / 2, cx + w / 2, top + h)),
                    ("pie", (cx - w / 2, top, cx + w / 2, top + w), {"start": 180, "end": 360})])
    p._fill(hole, hexc("#0e080e"))
    # depth inside the doorway: a faint far wall and a cold draught of light
    p.glow((cx, top + h - 20), w * 0.6, hexc("#5a4a8a"), 0.35)
    for i in range(3):
        yy = top + h - 14 - i * 12
        p.shape("rect", (cx - w / 2 + 10 + i * 8, yy, cx + w / 2 - 10 - i * 8, yy + 12), shade(stone, 0.5 - i * 0.1),
                depth=0.3, line=1.0, rim=0, ao=0, clip=hole)
    ring_r0, ring_r1 = w / 2, w / 2 + 28
    ccx, ccy = cx, top + w / 2
    for i in range(11):
        a0 = math.pi + i * math.pi / 11 + 0.02
        a1 = math.pi + (i + 1) * math.pi / 11 - 0.02
        pts = [(ccx + ring_r0 * math.cos(a0), ccy + ring_r0 * math.sin(a0)),
               (ccx + ring_r1 * math.cos(a0), ccy + ring_r1 * math.sin(a0)),
               (ccx + ring_r1 * math.cos(a1), ccy + ring_r1 * math.sin(a1)),
               (ccx + ring_r0 * math.cos(a1), ccy + ring_r0 * math.sin(a1))]
        p.shape("poly", pts, shade(stone, rng.uniform(0.95, 1.15) if i != 5 else 1.2), depth=0.2, tex="stone",
                line=1.6)
    for y in range(int(ccy), int(top + h), 30):
        for side in (-1, 1):
            x0 = cx + side * (w / 2) if side > 0 else cx - w / 2 - 28
            p.shape("rect", (x0, y, x0 + 28, y + 28), shade(stone, rng.uniform(0.9, 1.1)), radius=3, depth=0.2,
                    tex="stone", line=1.4)
    # iron portcullis
    iron = hexc("#3c3e48")
    for x in range(int(cx - w / 2 + 14), int(cx + w / 2 - 6), 22):
        p.shape("line", [(x, top + 12), (x, top + h)], iron, width=6, depth=0.3, spec=0.5, clip=hole, line=1.2)
    for yy in (top + 70, top + h - 60):
        p.shape("line", [(cx - w / 2, yy), (cx + w / 2, yy)], iron, width=6, depth=0.3, spec=0.5, clip=hole, line=1.2)
    for x in range(int(cx - w / 2 + 14), int(cx + w / 2 - 6), 22):
        for yy in (top + 70, top + h - 60):
            p.shape("ellipse", (x - 4, yy - 4, x + 4, yy + 4), hexc("#5a5e68"), line=1.0, depth=0.3, rim=0, ao=0,
                    clip=hole)
    # glowing eyes lurking in the dark
    for ex in (cx - 12, cx + 8):
        p.glow((ex, top + h - 94), 10, hexc("#ff3a3a"), 0.8)
        p.flat("ellipse", (ex - 2.5, top + h - 96, ex + 2.5, top + h - 92), hexc("#ffb0a0"))


def puddle(p, cx, cy, rx, ry):
    p.shape("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry), hexc("#1a2230", 200), shadow=0, light=0, line=0, ao=0)
    p.shape("ellipse", (cx - rx * 0.7, cy - ry * 0.5, cx + rx * 0.3, cy + ry * 0.1), hexc("#6a7a9a", 90), **dict(
        shadow=0, light=0, line=0, ao=0))
    p.stroke([(cx - rx * 0.4, cy - ry * 0.2), (cx + rx * 0.2, cy - ry * 0.3)], hexc("#c8d8ff", 110), 1.4)


# ------------------------------------------------------------------ scenes

def rotten_cellar(seed=7):
    rng = random.Random(seed)
    old = painter.SS
    painter.SS = K
    try:
        img = Image.new("RGBA", (W * K, H * K), hexc("#1c1418"))
        d = ImageDraw.Draw(img)
        floor_top = 430
        _brick_wall(d, rng, 0, floor_top, hexc("#5c5462"), hexc("#231b23"))
        _floor(d, rng, floor_top)
        wall_clip = Image.new("L", img.size, 0)
        ImageDraw.Draw(wall_clip).rectangle((0, 0, W * K, floor_top * K), fill=255)
        _texture(img, "stone", 0.35)
        _grime(img, rng, 0, floor_top, 14)
        # a stone skirting ledge where the wall meets the floor
        d = ImageDraw.Draw(img)
        d.rectangle((0, (floor_top - 14) * K, W * K, (floor_top + 6) * K), fill=hexc("#3a3038"))
        d.line((0, (floor_top - 13) * K, W * K, (floor_top - 13) * K), fill=hexc("#6a5e6a"), width=2 * K)
        d.rectangle((0, (floor_top + 4) * K, W * K, (floor_top + 14) * K), fill=hexc("#120c12"))
        p = _props_painter(img)
        arch(p, 360, 206, 164, floor_top - 206 - 12, rng)
        for cx in (250, 470):
            chain(p, cx, 0, 10)
            p.shape("ellipse", (cx - 12, 124, cx + 12, 146), hexc("#4f535c"), depth=0.3, spec=0.5, line=1.4)
        cobweb(p, 0, 0, 1, 130)
        cobweb(p, W, 0, -1, 110)
        # props: barrels and a crate on the left, bones and a skull on the right
        barrel(p, 34, 344, 70, 96)
        barrel(p, 98, 364, 62, 84)
        crate(p, 590, 360, 86, 76)
        crate(p, 620, 316, 52, 46)
        skull(p, 560, 452, 0.9)
        bones(p, 610, 466, 1.0)
        bones(p, 110, 470, 0.8)
        puddle(p, 470, 560, 70, 14)
        puddle(p, 200, 640, 50, 10)
        for x, y in ((40, 470), (300, 452), (660, 490)):  # straw tufts
            for i in range(6):
                a = math.radians(rng.uniform(-160, -20))
                p.stroke([(x + i * 3, y), (x + i * 3 + 14 * math.cos(a), y + 10 * math.sin(a))], hexc("#b8964a"), 1.6)
        torch(p, 170, 200, 1.0)
        torch(p, 550, 200, 1.0)
        img = p.img
        warm = (255, 170, 90)
        img = _light(img, (92, 100, 126), [
            (170, 190, 280, 300, warm, 1.0), (550, 190, 280, 300, warm, 1.0),
            (360, 560, 420, 170, (170, 150, 140), 0.6),        # soft fill where the fighters stand
            (360, 330, 110, 130, (90, 80, 160), 0.35),         # cold light from the archway
        ])
        for tx in (170, 550):
            _glow(img, tx, 175, 190, (255, 150, 60), 105)
            _glow(img, tx, 165, 60, (255, 215, 130), 170)
        # darker band behind the top HUD keeps its text readable
        top = Image.new("L", img.size, 0)
        ImageDraw.Draw(top).rectangle((0, 0, W * K, 40 * K), fill=120)
        top = top.filter(ImageFilter.GaussianBlur(40 * K))
        shade_l = Image.new("RGBA", img.size, (10, 6, 14, 255))
        shade_l.putalpha(top)
        img.alpha_composite(shade_l)
        _vignette(img, 190)
        return img.resize((W, H), Image.LANCZOS)
    finally:
        painter.SS = old

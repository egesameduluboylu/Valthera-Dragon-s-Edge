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


# ------------------------------------------------------------------ shared helpers for the later dungeons

def _hud_band(img, height=40, strength=120):
    """Darker band behind the top HUD so its text stays readable (same as the cellar)."""
    top = Image.new("L", img.size, 0)
    ImageDraw.Draw(top).rectangle((0, 0, img.size[0], height * K), fill=strength)
    top = top.filter(ImageFilter.GaussianBlur(40 * K))
    shade_l = Image.new("RGBA", img.size, (10, 6, 14, 255))
    shade_l.putalpha(top)
    img.alpha_composite(shade_l)


def _vgrad(img, y0, y1, c0, c1, x0=0, x1=None):
    """Vertical gradient band (1x coordinates)."""
    d = ImageDraw.Draw(img)
    x1 = img.size[0] / K if x1 is None else x1
    a, b = int(y0 * K), int(y1 * K)
    for y in range(a, b):
        t = (y - a) / max(1, b - a)
        d.line((x0 * K, y, x1 * K, y), fill=mix(c0, c1, t))


def _blob(cx, cy, rx, ry, rng, n=9, jitter=0.18):
    pts = []
    off = rng.uniform(0, math.pi)
    for i in range(n):
        a = off + i * 2 * math.pi / n
        r = 1 + rng.uniform(-jitter, jitter)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return pts


def _S(pts, dx=0, dy=0, k=1.0, c=None):
    """Scale 1x points to the K canvas, optionally shrinking toward c and offsetting."""
    if c is None:
        c = (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    return [((c[0] + (x - c[0]) * k + dx) * K, (c[1] + (y - c[1]) * k + dy) * K) for x, y in pts]


def _bez(p0, p1, p2, p3, n=18):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))
    return out


def _tapered(center, w0, w1=0.0, power=1.0):
    """Polygon around a centre line whose width goes from w0 to w1."""
    left, right = [], []
    n = len(center) - 1
    for i, (x, y) in enumerate(center):
        a, b = center[max(0, i - 1)], center[min(n, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        ux, uy = dx / ln, dy / ln
        w = (w1 + (w0 - w1) * (1 - i / n) ** power) / 2
        left.append((x - uy * w, y + ux * w))
        right.append((x + uy * w, y - ux * w))
    return left + right[::-1]


def _rock_wall(d, rng, top, bottom, base, crack, width=None, size=(60, 120), grey=None):
    """Cave wall of bevelled, irregular boulders (1x coordinates)."""
    width = width or W
    d.rectangle((0, top * K, width * K, bottom * K), fill=crack)
    y = top - 24
    while y < bottom:
        x = -rng.uniform(10, 60)
        rh = rng.uniform(*size) * 0.62
        while x < width + 40:
            w = rng.uniform(*size)
            cx, cy = x + w / 2, y + rh / 2 + rng.uniform(-8, 8)
            pts = _blob(cx, cy, w / 2, rh / 2, rng)
            c = shade(base, rng.uniform(0.78, 1.12))
            if grey:
                c = mix(c, grey, rng.uniform(0, 0.35))
            d.polygon(_S(pts, 3, 4), fill=shade(c, 0.55))
            d.polygon(_S(pts), fill=shade(c, 1.18))
            d.polygon(_S(pts, 1.2, 1.6, 0.93), fill=c)
            if rng.random() < 0.3:  # crack
                px, py = cx + rng.uniform(-w * 0.2, w * 0.2), cy - rh * 0.3
                d.line(_S([(px, py), (px + rng.uniform(-8, 8), py + rh * 0.3), (px + rng.uniform(-10, 10), py + rh * 0.55)]),
                       fill=shade(c, 0.55), width=K + 1)
            x += w * rng.uniform(0.72, 0.9)
        y += rh * 0.78


def _ground(d, rng, top, height, width, base, dark, rows=10, speckle=None):
    """Uneven rocky ground: flattened slabs that grow toward the viewer."""
    d.rectangle((0, top * K, width * K, height * K), fill=dark)
    y = top + 4
    h = 13
    while y < height + 20:
        depth = (y - top) / max(1, height - top)
        x = -rng.uniform(0, 60)
        while x < width + 40:
            w = rng.uniform(70, 150) * (0.7 + depth * 0.8)
            c = shade(base, rng.uniform(0.8, 1.08) * (0.7 + 0.36 * depth))
            pts = _blob(x + w / 2, y + h / 2 + rng.uniform(-h * 0.2, h * 0.2), w / 2, h / 2, rng, n=10, jitter=0.2)
            d.polygon(_S(pts, 2, 3), fill=shade(c, 0.55))
            d.polygon(_S(pts), fill=shade(c, 1.14))
            d.polygon(_S(pts, 1, 1.5, 0.92), fill=c)
            x += w * rng.uniform(0.8, 1.05)
        y += h * 0.8
        h *= 1.16
    if speckle:
        for _ in range(int(width * (height - top) / 400)):
            x, yy = rng.uniform(0, width), rng.uniform(top, height)
            r = rng.uniform(1, 3) * (0.6 + (yy - top) / max(1, height - top))
            d.ellipse(((x - r) * K, (yy - r * 0.6) * K, (x + r) * K, (yy + r * 0.6) * K), fill=speckle)


def _glow_lines(img, lines, color, width, blur, strength=255, core=None):
    """Glowing polylines (lava cracks, magic) added on top after the light pass (1x coordinates)."""
    m = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(m)
    for pts in lines:
        d.line([(x * K, y * K) for x, y in pts], fill=255, width=int(width * K * 3), joint="curve")
    m = m.filter(ImageFilter.GaussianBlur(blur * K)).point(lambda v: v * strength // 255)
    layer = Image.new("RGBA", img.size, color[:3] + (0,))
    layer.putalpha(m)
    img.alpha_composite(layer)
    if core:
        c = Image.new("L", img.size, 0)
        dc = ImageDraw.Draw(c)
        for pts in lines:
            dc.line([(x * K, y * K) for x, y in pts], fill=255, width=max(1, int(width * K)), joint="curve")
        c = c.filter(ImageFilter.GaussianBlur(K * 0.6))
        layer = Image.new("RGBA", img.size, core[:3] + (0,))
        layer.putalpha(c)
        img.alpha_composite(layer)


def _motes(img, rng, n, box, color, rmin=1.0, rmax=2.6, glow=True, core=(255, 255, 240)):
    """Floating particles (spores, embers, snow) with a soft halo, after the light pass."""
    x0, y0, x1, y1 = box
    halo = Image.new("L", img.size, 0)
    dots = Image.new("L", img.size, 0)
    dh, dd = ImageDraw.Draw(halo), ImageDraw.Draw(dots)
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(rmin, rmax)
        a = int(rng.uniform(140, 255))
        if glow:
            dh.ellipse(((x - r * 3.2) * K, (y - r * 3.2) * K, (x + r * 3.2) * K, (y + r * 3.2) * K), fill=a // 2)
        dd.ellipse(((x - r) * K, (y - r) * K, (x + r) * K, (y + r) * K), fill=a)
    if glow:
        halo = halo.filter(ImageFilter.GaussianBlur(3 * K))
        layer = Image.new("RGBA", img.size, color[:3] + (0,))
        layer.putalpha(halo)
        img.alpha_composite(layer)
    layer = Image.new("RGBA", img.size, core[:3] + (0,))
    layer.putalpha(dots.filter(ImageFilter.GaussianBlur(K * 0.4)))
    img.alpha_composite(layer)


def _finish(img, size, hud=True, vignette=190):
    if hud:
        _hud_band(img)
    _vignette(img, vignette)
    return img.resize(size, Image.LANCZOS)


def stalactite(p, x, top, w, ln, color, drip=None):
    pts = [(x - w, top - 4), (x + w, top - 4), (x + w * 0.55, top + ln * 0.45), (x + w * 0.15, top + ln * 0.8),
           (x, top + ln), (x - w * 0.2, top + ln * 0.7), (x - w * 0.6, top + ln * 0.4)]
    p.shape("poly", pts, color, depth=0.25, light=1.25, tex="stone", tex_amt=0.9, line=1.6)
    p.stroke([(x - w * 0.5, top + 4), (x - w * 0.15, top + ln * 0.6)], shade(color, 1.25), 1.6)
    if drip:
        p.shape("ellipse", (x - 2.4, top + ln + 5, x + 2.4, top + ln + 12), drip, light=1.4, line=0.8, gloss=1.0,
                rim=0, ao=0)


# ------------------------------------------------------------------ mushroom cave

def giant_mushroom(p, x, base, stem_h, cap_w, cap_col, spots=True, lean=0.0, stem_col=None):
    stem_col = stem_col or hexc("#d8ccb4")
    top = base - stem_h
    sw = cap_w * 0.1
    center = _bez((x, base + 6), (x - lean * 0.4, base - stem_h * 0.4), (x + lean * 0.6, top + stem_h * 0.3),
                  (x + lean, top + 4))
    stem = _tapered(center, sw * 3.0, sw * 1.7, 0.6)
    p.shape("poly", stem, stem_col, depth=0.22, light=1.2, tex="bone", tex_amt=0.7, line=1.8)
    for t in (0.3, 0.55, 0.8):  # faint glowing veins running up the stem
        i = int(t * (len(center) - 1))
        p.stroke(center[max(0, i - 3):i + 1], mix(cap_col, hexc("#ffffff"), 0.4)[:3] + (120,), 1.6)
    cx = x + lean
    # ring (annulus) just under the gills
    p.shape("chord", (cx - sw * 1.9, top + 6, cx + sw * 1.9, top + 34), shade(stem_col, 1.05), start=0, end=180,
            depth=0.3, line=1.4, rim=0)
    # gills: a glowing disc under the cap with radial lines
    gh = cap_w * 0.09
    p.shape("ellipse", (cx - cap_w * 0.48, top - gh, cx + cap_w * 0.48, top + gh), mix(cap_col, hexc("#ffffff"), 0.2),
            depth=0.3, light=1.3, line=1.6, rim=0)
    for i in range(-9, 10):
        p.stroke([(cx + i * cap_w * 0.012, top + gh * 0.1), (cx + i * cap_w * 0.05, top + gh * 0.85)],
                 shade(cap_col, 0.55), 1.2)
    ch = cap_w * 0.46
    cap = p.shape("chord", (cx - cap_w * 0.53, top - ch, cx + cap_w * 0.53, top + ch), cap_col, start=180,
                  end=360, depth=0.16, light=1.35, spec=0.5, gloss=0.25, line=2.0)
    if spots:
        rng = random.Random(int(x * 7 + base))
        for _ in range(7):
            sx = cx + rng.uniform(-0.38, 0.38) * cap_w
            sy = top - rng.uniform(0.15, 0.8) * ch
            r = rng.uniform(0.04, 0.075) * cap_w
            p.shape("ellipse", (sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), mix(cap_col, hexc("#ffffff"), 0.65),
                    depth=0.3, light=1.2, line=1.0, rim=0, ao=0, clip=cap)
    return cap


def small_mushrooms(p, x, base, rng, n, col, s=1.0):
    for i in range(n):
        mx = x + rng.uniform(-24, 24) * s
        h = rng.uniform(10, 22) * s
        w = rng.uniform(14, 24) * s
        by = base + rng.uniform(-4, 4)
        p.shape("rect", (mx - w * 0.17, by - h, mx + w * 0.17, by + 2), mix(hexc("#e0d4bc"), col, 0.2), radius=2,
                depth=0.3, line=1.2, rim=0)
        p.shape("chord", (mx - w / 2, by - h - w * 0.45, mx + w / 2, by - h + w * 0.2), col, start=180, end=360,
                depth=0.25, light=1.45, line=1.3, gloss=0.5, rim=0)


def dragon_rib(p, x, base, h, bend, width, color):
    """One huge rib bone curving out of the ground: bows out by `bend`, its broken tip curling back."""
    center = _bez((x, base + 10), (x + bend * 0.7, base - h * 0.45), (x + bend * 0.55, base - h * 0.92),
                  (x - bend * 0.25, base - h))
    p.shape("poly", _tapered(center, width, width * 0.45, 0.8), color, depth=0.22, light=1.25, line=1.8, tex="bone",
            tex_amt=0.9, rim=0.4)
    p.stroke(center[3:-3], shade(color, 1.2), max(1.5, width * 0.12))
    tx, ty = center[-1]
    r = width * 0.3
    p.shape("ellipse", (tx - r, ty - r, tx + r, ty + r), color, depth=0.3, line=1.6, tex="bone", rim=0)
    return center


def _mushroom_scene(tall):
    MW, MH = (720, 1280) if tall else (W, H)
    floor_top = 1010 if tall else 430
    rng = random.Random(21 if tall else 20)
    old = painter.SS
    painter.SS = K
    try:
        img = Image.new("RGBA", (MW * K, MH * K), hexc("#141820"))
        d = ImageDraw.Draw(img)
        _rock_wall(d, rng, 0, floor_top, hexc("#3e4458"), hexc("#10121a"), width=MW, size=(70, 140),
                   grey=hexc("#4a3a5a"))
        _ground(d, rng, floor_top, MH, MW, hexc("#3a4046"), hexc("#12141a"), speckle=hexc("#2a3a30"))
        _texture(img, "stone", 0.4)
        # moss carpet where the wall meets the ground
        d = ImageDraw.Draw(img)
        for i in range(int(MW / 14)):
            x = i * 14 + rng.uniform(-6, 6)
            r = rng.uniform(10, 22)
            y = floor_top + rng.uniform(-6, 6)
            d.ellipse(((x - r) * K, (y - r * 0.45) * K, (x + r) * K, (y + r * 0.45) * K),
                      fill=mix(hexc("#2e5a44"), hexc("#3e7a5a"), rng.random()))
        # a tunnel mouth receding into darkness behind the ribs
        tcx, tcy = (MW * 0.55, floor_top - 110) if not tall else (MW * 0.55, 450)
        tun = Image.new("L", img.size, 0)
        td = ImageDraw.Draw(tun)
        for i in range(10):
            t = i / 10
            rx, ry = 150 * (1 - t * 0.7), 120 * (1 - t * 0.6)
            td.polygon(_S(_blob(tcx, tcy + 20 * t, rx, ry, random.Random(i), n=12, jitter=0.08)), fill=int(40 + 21 * i))
        tun = tun.filter(ImageFilter.GaussianBlur(4 * K))
        dark = Image.new("RGBA", img.size, (6, 8, 14, 0))
        dark.putalpha(tun)
        img.alpha_composite(dark)
        p = _props_painter(img)
        bone = hexc("#a8a494")
        # a half-buried dragon ribcage in the background
        if tall:
            ribs = [(300, 580, 330, 90, 34), (400, 580, 300, 80, 30), (490, 580, 250, 66, 26), (566, 580, 190, 50, 22)]
        else:
            ribs = [(240, floor_top + 6, 330, 100, 36), (348, floor_top + 6, 300, 88, 32),
                    (446, floor_top + 6, 250, 72, 28), (530, floor_top + 6, 190, 56, 22)]
        for x0, base, h, bend, wdt in ribs[::-1]:
            dragon_rib(p, x0, base, h, bend, wdt, bone)
        if tall:  # a ledge the ribs rest on
            p.shape("poly", [(230, 584), (720, 570), (720, 630), (260, 624)], hexc("#3a4050"), depth=0.25,
                    tex="stone", line=1.8)
        # stalactites along the ceiling, some dripping
        ceil = [(x, rng.uniform(40, 130 if not tall else 170)) for x in range(20, MW, 58)]
        for x, ln in ceil:
            x += rng.uniform(-14, 14)
            stalactite(p, x, 0, rng.uniform(14, 24), ln, hexc("#5a5e76"), drip=hexc("#8affe0") if rng.random() < 0.4
                       else None)
        # hanging roots with glowing bulbs
        bulbs = []
        for x in ((200, 400, 560) if not tall else (200, 380, 520, 640)):
            ln = rng.uniform(90, 170)
            pts = [(x + math.sin(i * 0.9) * 6, i * ln / 6) for i in range(7)]
            p.stroke(pts, hexc("#2a3a30"), 3.2)
            p.stroke(pts, hexc("#4a6a50"), 1.4)
            for j in (3, 5, 6):
                bx, by = pts[j]
                bulbs.append((bx, by + 4))
                p.shape("ellipse", (bx - 4, by, bx + 4, by + 9), hexc("#8affe0"), light=1.5, line=1.0, gloss=0.8, rim=0,
                        ao=0)
        # giant glowing mushrooms framing the scene
        teal, violet, pink = hexc("#2ec8b8"), hexc("#9a5ae0"), hexc("#d86ab8")
        if tall:
            big = [(96, floor_top + 10, 420, 250, teal, 16), (640, floor_top + 10, 300, 200, violet, -12),
                   (80, 470, 150, 140, violet, 8), (650, 380, 110, 110, teal, -6)]
            for x, y in ((40, 470), (690, 380)):
                p.shape("poly", [(x - 70, y + 4), (x + 90, y - 4), (x + 80, y + 40), (x - 70, y + 50)],
                        hexc("#3a4050"), depth=0.25, tex="stone", line=1.8)
        else:
            big = [(92, floor_top + 12, 290, 220, teal, 14), (650, floor_top + 12, 230, 180, violet, -10)]
        caps = []
        for x, base, sh, cw, col, lean in big:
            giant_mushroom(p, x, base, sh, cw, col, lean=lean, stem_col=mix(hexc("#d8ccb4"), col, 0.18))
            caps.append((x + lean, base - sh - cw * 0.15, cw, col))
        backgrounds_rocks(p, rng, [(x + rng.uniform(-20, 20), floor_top + 14, rng.uniform(18, 28))
                                   for x in ((290, 470) if not tall else (230, 340, 480))], hexc("#4a5064"))
        # a still pool catching the glow
        py = floor_top + (MH - floor_top) * 0.62
        p.shape("ellipse", (MW * 0.3, py - 16, MW * 0.72, py + 16), hexc("#123a3a"), shadow=0, light=0, line=1.2, ao=0,
                rim=0)
        p.shape("ellipse", (MW * 0.34, py - 10, MW * 0.6, py + 2), hexc("#3ad8c8", 80), **NOLINE)
        p.stroke([(MW * 0.38, py - 6), (MW * 0.5, py - 8)], hexc("#c8fff4", 140), 1.6)
        clusters = [(200, floor_top + 16, pink, 1.1), (560, floor_top + 12, teal, 1.0), (40, MH - 50, violet, 1.6),
                    (MW - 50, MH - 80, teal, 1.7), (140, floor_top + 60, teal, 1.2), (MW - 170, floor_top + 50, pink, 1.1)]
        for x, y, col, sc in clusters:
            small_mushrooms(p, x, y, rng, 5, col, sc)
        backgrounds_rocks(p, rng, [(150, MH - 20, 40), (MW - 150, MH - 30, 34)], hexc("#3a4046"))
        img = p.img
        pools = [(cx, cy, cw * 1.4, cw * 1.3, col, 0.9) for cx, cy, cw, col in caps]
        pools += [(MW / 2, floor_top + (MH - floor_top) * 0.5, 420, 220, (120, 160, 170), 0.7)]
        if tall:
            pools += [(MW / 2, 520, 300, 300, (90, 80, 150), 0.35)]
        img = _light(img, (92, 100, 130), pools)
        for x, y, col, sc in clusters:
            _glow(img, x, y - 16 * sc, 40 * sc, col, 120)
        _glow(img, MW / 2, py, MW * 0.25, hexc("#3ad8c8"), 50)
        for bx, by in bulbs:
            _glow(img, bx, by, 16, hexc("#6affe0"), 150)
        for cx, cy, cw, col in caps:
            _glow(img, cx, cy, cw * 0.9, col, 110)
            _glow(img, cx, cy - cw * 0.05, cw * 0.45, mix(col, hexc("#ffffff"), 0.4), 90)
        # glowing spots on the small mushrooms and drips
        for cx, cy, cw, col in caps:  # spores drifting off each cap
            _motes(img, rng, int(cw / 7), (cx - cw * 0.9, cy - cw * 0.6, cx + cw * 0.9, cy + cw * 1.2),
                   mix(col, hexc("#ffffff"), 0.3), 0.8, 2.2)
        _motes(img, rng, 30 if not tall else 60, (0, 60, MW, floor_top + 80), hexc("#6affe0"), 0.7, 1.8)
        return _finish(img, (MW, MH), hud=not tall, vignette=190 if not tall else 180)
    finally:
        painter.SS = old


def backgrounds_rocks(p, rng, rocks, color):
    for x, y, r in rocks:
        p.shape("poly", _blob(x, y - r * 0.4, r, r * 0.6, rng, n=8, jitter=0.15), shade(color, rng.uniform(0.9, 1.1)),
                depth=0.25, light=1.3, tex="stone", line=1.6)


def mushroom_cave():
    return _mushroom_scene(False)


def mushroom_cave_map():
    return _mushroom_scene(True)


# ------------------------------------------------------------------ frozen pass

def _ridge(rng, width, base_y, height, step=(40, 90)):
    pts = [(-30, base_y)]
    x = -30
    up = True
    while x < width + 30:
        x += rng.uniform(*step)
        y = base_y - (rng.uniform(0.55, 1.0) * height if up else rng.uniform(0.15, 0.45) * height)
        pts.append((x, y))
        up = not up
    pts.append((width + 30, base_y))
    return pts


def _mountains(d, rng, width, base_y, height, color, snow, bottom):
    ridge = _ridge(rng, width, base_y, height)
    d.polygon(_S(ridge + [(width + 30, bottom), (-30, bottom)], c=(0, 0)), fill=color)
    # lit left faces and snow caps on each peak
    for i in range(1, len(ridge) - 1):
        px, py = ridge[i]
        if py >= ridge[i - 1][1] or py >= ridge[i + 1][1]:
            continue
        lx, ly = ridge[i - 1]
        rx, ry = ridge[i + 1]
        d.polygon(_S([(px, py), (lx, ly), (px - (px - lx) * 0.2, ly + 30)], c=(0, 0)), fill=shade(color, 1.12))
        t = 0.38
        a = (px + (lx - px) * t, py + (ly - py) * t)
        b = (px + (rx - px) * t, py + (ry - py) * t)
        cap = [(px, py), b]
        for k in range(1, 5):  # ragged lower edge of the snow
            u = k / 5
            cap.append((b[0] + (a[0] - b[0]) * u, b[1] + (a[1] - b[1]) * u + (10 if k % 2 else -2)))
        cap.append(a)
        d.polygon(_S(cap, c=(0, 0)), fill=snow)
        d.polygon(_S([(px, py), a, (px - 2, (py + a[1]) / 2 + 6)], c=(0, 0)), fill=shade(snow, 1.08))
    return ridge


def icicles(p, x0, x1, y, rng, max_len=40, color=None, density=9):
    color = color or hexc("#bfe8f8")
    x = x0
    while x < x1:
        w = rng.uniform(3, 7)
        ln = rng.uniform(0.3, 1.0) * max_len
        p.shape("poly", [(x - w, y - 2), (x + w, y - 2), (x + w * 0.2, y + ln * 0.7), (x, y + ln)], color,
                depth=0.3, light=1.4, line=1.1, spec=0.8, rim=0, ao=0.2, ink=hexc("#26406a"))
        x += rng.uniform(density * 0.6, density * 1.4)


def pine(p, x, base, h, rng, snow=True):
    trunk = hexc("#4a3428")
    green = hexc("#24403e")
    p.shape("rect", (x - h * 0.04, base - h * 0.2, x + h * 0.04, base + 4), trunk, depth=0.3, tex="wood", line=1.4)
    tiers = 4
    for i in range(tiers):
        t = i / tiers
        ty = base - h * 0.15 - h * 0.85 * t
        tw = h * 0.36 * (1 - t * 0.7)
        th = h * 0.36
        pts = [(x - tw, ty), (x - tw * 0.55, ty - th * 0.35), (x - tw * 0.25, ty - th * 0.7), (x, ty - th),
               (x + tw * 0.25, ty - th * 0.7), (x + tw * 0.55, ty - th * 0.35), (x + tw, ty)]
        p.shape("poly", pts, shade(green, 1 + t * 0.1), depth=0.2, light=1.25, line=1.5, tex="fur", tex_amt=0.5)
        if snow:
            sp = [(x - tw * 0.85, ty - th * 0.08), (x - tw * 0.5, ty - th * 0.4), (x, ty - th * 0.98),
                  (x + tw * 0.4, ty - th * 0.5), (x + tw * 0.2, ty - th * 0.36), (x - tw * 0.1, ty - th * 0.5),
                  (x - tw * 0.4, ty - th * 0.2)]
            p.shape("poly", sp, hexc("#eef4ff"), depth=0.3, light=1.2, line=1.0, rim=0, ao=0.2, ink=hexc("#4a5a80"))


def _jagged(pts, rng, amp=10, step=26, closed=False):
    """Subdivides a polyline and nudges the new points, so rock outlines look craggy."""
    out = []
    seq = pts + ([pts[0]] if closed else [])
    for (x0, y0), (x1, y1) in zip(seq, seq[1:]):
        out.append((x0, y0))
        n = int(math.hypot(x1 - x0, y1 - y0) / step)
        for k in range(1, n):
            u = k / n
            out.append((x0 + (x1 - x0) * u + rng.uniform(-amp, amp), y0 + (y1 - y0) * u + rng.uniform(-amp, amp) * 0.7))
    if not closed:
        out.append(seq[-1])
    return out


def snowy_cliff(p, pts, rng, rock=None, snow_depth=18, icicle_edge=None, max_icicle=40):
    rock = rock or hexc("#4e5670")
    base_pts = pts
    pts = _jagged(pts, rng)
    p.shape("poly", pts, rock, depth=0.14, light=1.25, tex="stone", tex_amt=1.0, line=1.8)
    for _ in range(int(len(pts) / 2)):  # rock strata and cracks
        i = rng.randrange(len(pts))
        x, y = pts[i]
        cx = sum(q[0] for q in pts) / len(pts)
        cy = sum(q[1] for q in pts) / len(pts)
        p.stroke([(x, y), (x + (cx - x) * 0.25 + rng.uniform(-8, 8), y + (cy - y) * 0.25 + rng.uniform(4, 16))],
                 shade(rock, 0.62), 1.6)
    # snow blanket along the top edges (segments that face up)
    for (x0, y0), (x1, y1) in zip(base_pts, base_pts[1:]):
        if abs(x1 - x0) < 8 or abs(y1 - y0) > abs(x1 - x0) * 1.2:
            continue
        sd = snow_depth
        band = [(x0, y0 - 4), (x1, y1 - 4)]
        n = max(2, int(abs(x1 - x0) / 16))
        for k in range(n, -1, -1):
            u = k / n
            band.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u + sd * (0.6 + 0.5 * ((k * 37) % 7) / 7)))
        p.shape("poly", band, hexc("#e8f0fc"), depth=0.35, light=1.2, line=1.3, rim=0, ink=hexc("#4a5a80"))
    if icicle_edge:
        x0, x1, y = icicle_edge
        icicles(p, x0, x1, y, rng, max_icicle)


def frozen_fall(p, x0, x1, top, bottom, rng):
    """A frozen waterfall: pale blue ice columns spilling into a bulging ice mound."""
    ice = hexc("#9ed4ec")
    body = [(x0, top), (x1, top), (x1 + 16, bottom - 30), (x1 + 34, bottom), (x0 - 34, bottom), (x0 - 16, bottom - 30)]
    p.shape("poly", body, ice, depth=0.18, light=1.35, line=1.8, spec=0.8, rim=0.4, ink=hexc("#26406a"))
    x = x0 + 4
    while x < x1:
        w = rng.uniform(8, 16)
        p.shape("line", [(x, top + 4), (x + rng.uniform(-3, 3), (top + bottom) / 2), (x + (x - (x0 + x1) / 2) * 0.25,
                                                                                         bottom - 10)],
                shade(ice, rng.uniform(1.0, 1.15)), width=w, depth=0.35, light=1.4, line=0.9, rim=0, ao=0,
                ink=hexc("#3a6a9a"))
        x += w * 0.9
    for i in range(10):
        xx = x0 + (x1 - x0) * rng.random()
        p.stroke([(xx, top + rng.uniform(10, 60)), (xx + rng.uniform(-4, 4), top + rng.uniform(100, bottom - top - 40))],
                 hexc("#ffffff", 150), 1.6)
    p.shape("ellipse", (x0 - 50, bottom - 26, x1 + 50, bottom + 18), shade(ice, 1.08), depth=0.3, light=1.35, line=1.6,
            spec=0.8, rim=0, ink=hexc("#26406a"))


def _frozen_scene(tall):
    MW, MH = (720, 1280) if tall else (W, H)
    floor_top = 1010 if tall else 440
    rng = random.Random(31 if tall else 30)
    old = painter.SS
    painter.SS = K
    try:
        img = Image.new("RGBA", (MW * K, MH * K), hexc("#1a2248"))
        horizon = floor_top - (110 if not tall else 330)
        _vgrad(img, 0, horizon * 0.55, hexc("#141c40"), hexc("#3a3a78"))
        _vgrad(img, horizon * 0.55, horizon, hexc("#3a3a78"), hexc("#d88a8a"))
        _vgrad(img, horizon, floor_top + 2, hexc("#d88a8a"), hexc("#f0b890"))
        d = ImageDraw.Draw(img)
        for _ in range(60 if not tall else 110):  # first stars
            x, y = rng.uniform(0, MW), rng.uniform(0, horizon * 0.5)
            r = rng.uniform(0.5, 1.3)
            d.ellipse(((x - r) * K, (y - r) * K, (x + r) * K, (y + r) * K), fill=(230, 230, 255, 255))
        # the low sun behind the far range
        _glow(img, MW * 0.62, horizon + 10, 260, (255, 190, 150), 170)
        _glow(img, MW * 0.62, horizon + 10, 70, (255, 230, 200), 220)
        d = ImageDraw.Draw(img)
        _mountains(d, rng, MW, horizon + 20, 190 if not tall else 280, hexc("#8a88b8"), hexc("#e8e4f4"), floor_top + 10)
        _mountains(d, rng, MW, horizon + 70, 150 if not tall else 230, hexc("#5a6494"), hexc("#d0dcf0"), floor_top + 10)
        _texture(img, "stone", 0.18)
        # snowy ground: soft drifts that brighten toward the viewer
        _vgrad(img, floor_top - 20, MH, hexc("#a8b8dc"), hexc("#e0e8f8"))
        d = ImageDraw.Draw(img)
        y = floor_top - 10
        h = 18
        while y < MH + 20:
            x = -rng.uniform(0, 80)
            while x < MW + 60:
                w = rng.uniform(140, 260) * (h / 22)
                c = mix(hexc("#b8c8e8"), hexc("#f4f8ff"), min(1, (y - floor_top) / max(1, MH - floor_top) + 0.2))
                d.ellipse(((x) * K, (y + h * 0.35) * K, (x + w) * K, (y + h * 1.25) * K), fill=shade(c, 0.86))
                d.ellipse((x * K, y * K, (x + w) * K, (y + h) * K), fill=c)
                x += w * rng.uniform(0.6, 0.9)
            y += h * 0.7
            h *= 1.14
        for _ in range(26 if not tall else 16):  # wind ripples in the snow
            x = rng.uniform(0, MW)
            yy = rng.uniform(floor_top + 20, MH)
            ln = rng.uniform(30, 90) * (0.6 + (yy - floor_top) / max(1, MH - floor_top))
            d.arc((x * K, yy * K, (x + ln) * K, (yy + ln * 0.18) * K), 200, 340, fill=hexc("#98a8d0"), width=K)
            d.arc((x * K, (yy + 2) * K, (x + ln) * K, (yy + 2 + ln * 0.18) * K), 200, 340, fill=hexc("#ffffff"), width=K)
        _texture(img, "noise", 0.12)
        p = _props_painter(img)
        # the frozen waterfall pouring off a cliff in the back
        if tall:
            fx0, fx1, ftop, fbot = 300, 420, 470, floor_top - 20
            snowy_cliff(p, [(160, floor_top), (180, 520), (240, 440), (300, 420), (420, 420), (480, 450), (560, 520),
                            (580, floor_top)], rng, rock=hexc("#5a6286"), icicle_edge=(250, 290, 440))
        else:
            fx0, fx1, ftop, fbot = 318, 392, 236, floor_top - 6
            snowy_cliff(p, [(210, floor_top), (220, 330), (260, 262), (318, 226), (392, 226), (440, 250), (480, 320),
                            (500, floor_top)], rng, rock=hexc("#5a6286"), icicle_edge=(400, 440, 250))
        frozen_fall(p, fx0, fx1, ftop, fbot, rng)
        # cliffs framing both sides with icicles under their overhangs
        if tall:
            left = [(-20, 0), (120, 0), (140, 180), (100, 300), (160, 420), (130, 640), (180, 760), (150, 900),
                    (200, floor_top + 30), (-20, floor_top + 30)]
            right = [(MW + 20, 0), (600, 0), (580, 200), (620, 340), (560, 480), (600, 700), (540, 840), (560, floor_top + 30),
                     (MW + 20, floor_top + 30)]
            snowy_cliff(p, left, rng, icicle_edge=(100, 160, 300), max_icicle=60)
            snowy_cliff(p, right, rng, icicle_edge=(560, 600, 480), max_icicle=60)
            icicles(p, 130, 180, 760, rng, 50)
            icicles(p, 540, 590, 840, rng, 50)
            for x, b, h in ((60, 700, 180), (660, 560, 150), (90, floor_top + 20, 260), (630, floor_top + 30, 240)):
                pine(p, x, b, h, rng)
        else:
            left = [(-20, 0), (60, 0), (100, 120), (70, 190), (130, 260), (110, 360), (150, floor_top + 24),
                    (-20, floor_top + 24)]
            right = [(MW + 20, 0), (650, 0), (620, 110), (660, 170), (600, 260), (620, 340), (580, floor_top + 24),
                     (MW + 20, floor_top + 24)]
            snowy_cliff(p, left, rng, icicle_edge=(70, 130, 190), max_icicle=50)
            snowy_cliff(p, right, rng, icicle_edge=(600, 660, 170), max_icicle=50)
            pine(p, 70, floor_top + 20, 230, rng)
            pine(p, 655, floor_top + 30, 200, rng)
            pine(p, 150, floor_top + 4, 120, rng)
        # snowy boulders
        for x, y, r in ((200, floor_top + 40, 26), (560, floor_top + 30, 22), (60, MH - 40, 44), (MW - 60, MH - 60, 40)):
            rock = _blob(x, y - r * 0.4, r, r * 0.6, rng, n=8, jitter=0.15)
            p.shape("poly", rock, hexc("#5a6286"), depth=0.25, light=1.3, tex="stone", line=1.6)
            p.shape("chord", (x - r * 0.95, y - r * 1.05, x + r * 0.9, y - r * 0.2), hexc("#eef4ff"), start=180, end=360,
                    depth=0.3, light=1.2, line=1.2, rim=0, ink=hexc("#4a5a80"))
        img = p.img
        pools = [(MW * 0.62, horizon, 420, 260, (255, 170, 140), 0.55),
                 (MW / 2, floor_top + (MH - floor_top) * 0.5, 440, 220, (170, 180, 210), 0.5),
                 ((fx0 + fx1) / 2, (ftop + fbot) / 2, 120, 260, (120, 190, 240), 0.35)]
        img = _light(img, (150, 158, 198), pools)
        _glow(img, (fx0 + fx1) / 2, fbot - 30, 120, (160, 220, 255), 70)
        # wind-blown snow: streaks and flakes
        streaks = Image.new("L", img.size, 0)
        sd = ImageDraw.Draw(streaks)
        for _ in range(90 if not tall else 160):
            x, y = rng.uniform(-40, MW), rng.uniform(0, MH)
            ln = rng.uniform(20, 60)
            sd.line((x * K, y * K, (x + ln) * K, (y + ln * 0.28) * K), fill=int(rng.uniform(60, 140)), width=K)
        streaks = streaks.filter(ImageFilter.GaussianBlur(K * 0.8))
        layer = Image.new("RGBA", img.size, (240, 246, 255, 0))
        layer.putalpha(streaks)
        img.alpha_composite(layer)
        _motes(img, rng, 160 if not tall else 280, (0, 0, MW, MH), hexc("#c8dcff"), 0.8, 2.6, glow=False,
               core=(250, 252, 255))
        return _finish(img, (MW, MH), hud=not tall, vignette=170)
    finally:
        painter.SS = old


def frozen_pass():
    return _frozen_scene(False)


def frozen_pass_map():
    return _frozen_scene(True)


# ------------------------------------------------------------------ burnt keep

def dragon_eye(p, cx, cy, s=1.0, iris=None):
    """The cult's sigil: a slit-pupilled dragon eye inside a ring of flame points."""
    gold = hexc("#e7b440")
    ring = [(cx + (22 if i % 2 == 0 else 15) * s * math.cos(math.pi * i / 8),
             cy + (22 if i % 2 == 0 else 15) * s * math.sin(math.pi * i / 8)) for i in range(16)]
    p.shape("poly", ring, gold, depth=0.25, light=1.35, line=1.3, spec=0.6, rim=0)
    p.shape("ellipse", (cx - 15 * s, cy - 15 * s, cx + 15 * s, cy + 15 * s), hexc("#3a0a0e"), depth=0.3, line=1.2,
            rim=0, ao=0)
    eye = ImageChops.multiply(p._mask("ellipse", (cx - 14 * s, cy - 9 * s, cx + 14 * s, cy + 9 * s)),
                              p._mask("ellipse", (cx - 12 * s, cy - 12 * s, cx + 12 * s, cy + 12 * s)))
    p.paint_mask(eye, iris or hexc("#ffb030"), depth=0.3, light=1.5, line=1.0, rim=0, ao=0)
    p.shape("ellipse", (cx - 2.2 * s, cy - 8 * s, cx + 2.2 * s, cy + 8 * s), hexc("#120406"), **NOLINE)


def cult_banner(p, cx, top, w, h, rng):
    red = hexc("#9a1e22")
    p.shape("line", [(cx - w / 2 - 10, top), (cx + w / 2 + 10, top)], hexc("#2a1c16"), width=7, depth=0.3,
            tex="wood", line=1.4)
    for x in (cx - w / 2 - 12, cx + w / 2 + 12):
        p.shape("ellipse", (x - 5, top - 5, x + 5, top + 5), hexc("#8a6a3a"), depth=0.3, line=1.1, spec=0.6, rim=0)
    pts = [(cx - w / 2, top + 2), (cx + w / 2, top + 2)]
    n = 7
    for k in range(n + 1):  # tattered, burnt lower edge
        u = 1 - k / n
        pts.append((cx - w / 2 + w * u, top + h - rng.uniform(0, h * 0.18) - (h * 0.08 if k % 2 else 0)))
    cloth = p.shape("poly", pts, red, depth=0.12, light=1.25, tex="cloth", tex_amt=0.9, line=1.6)
    for x in (cx - w / 2 + 6, cx + w / 2 - 6):
        p.shape("line", [(x, top + 6), (x, top + h * 0.72)], hexc("#d8a040"), width=3, depth=0.3, line=0.8, rim=0,
                ao=0, clip=cloth)
    for i in range(3):  # folds
        x = cx - w / 2 + w * (i + 1) / 4
        p.stroke([(x, top + 8), (x + rng.uniform(-3, 3), top + h * 0.8)], shade(red, 0.62), 2.0)
    dragon_eye(p, cx, top + h * 0.36, w / 70)
    for _ in range(3):  # scorch holes
        x = cx + rng.uniform(-w * 0.35, w * 0.35)
        y = top + h * rng.uniform(0.55, 0.8)
        r = rng.uniform(4, 8)
        p.shape("poly", _blob(x, y, r, r * 0.8, rng, 7, 0.3), hexc("#1a0a08"), shadow=0, light=0, line=1.2,
                ink=hexc("#ff7a2a"), clip=cloth, ao=0)


def fire_window(p, cx, top, w, h, rng):
    """A tall arched window, its glass gone, with the burning night sky behind it."""
    stone = hexc("#5a4a4a")
    hole = p.union([("rect", (cx - w / 2, top + w / 2, cx + w / 2, top + h)),
                    ("pie", (cx - w / 2, top, cx + w / 2, top + w), {"start": 180, "end": 360})])
    # the burning sky: dark red above, blazing orange low down
    sky = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    sdr = ImageDraw.Draw(sky)
    y0, y1 = int(top * K), int((top + h) * K)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0)
        sdr.line((int((cx - w / 2) * K), y, int((cx + w / 2) * K), y), fill=mix(hexc("#4a1014"), hexc("#ff9a3a"), t ** 1.3))
    sky.putalpha(ImageChops.multiply(sky.getchannel("A"), hole))
    p.img.alpha_composite(sky)
    p.glow((cx, top + h * 0.95), w * 0.8, hexc("#ffd070"), 0.8)
    # far battlements burning against it
    bx = cx - w / 2
    wall = [(bx, top + h), (bx, top + h * 0.7)]
    x = bx
    while x < cx + w / 2:
        wall += [(x, top + h * 0.62), (x + 9, top + h * 0.62), (x + 9, top + h * 0.7), (x + 18, top + h * 0.7)]
        x += 18
    wall += [(cx + w / 2, top + h * 0.7), (cx + w / 2, top + h)]
    p.shape("poly", wall, hexc("#2a0e10"), shadow=0, light=0, line=0, clip=hole, ao=0)
    p.shape("poly", [(cx + w * 0.2, top + h), (cx + w * 0.2, top + h * 0.38), (cx + w * 0.32, top + h * 0.3),
                     (cx + w * 0.44, top + h * 0.38), (cx + w * 0.44, top + h)], hexc("#2a0e10"), shadow=0, light=0,
            line=0, clip=hole, ao=0)
    for fx in (cx - w * 0.3, cx - w * 0.05, cx + w * 0.32):
        fy = top + h * (0.66 if fx < cx + w * 0.2 else 0.32)
        p.shape("poly", [(fx - 10, fy + 4), (fx - 6, fy - 14), (fx - 1, fy - 6), (fx + 3, fy - 22), (fx + 8, fy - 8),
                         (fx + 11, fy + 4)], hexc("#ffb040"), shadow=0, light=0, line=0, clip=hole, ao=0)
    for i in range(3):  # drifting smoke
        y = top + w * 0.25 + i * h * 0.14
        p.glow((cx - w * 0.2 + i * 14, y), w * 0.35, hexc("#2a0a0c"), 0.5)
    # stone mullion and cross bar
    p.shape("rect", (cx - 5, top + 10, cx + 5, top + h), shade(stone, 0.9), radius=2, depth=0.3, tex="stone", line=1.3,
            clip=hole)
    p.shape("rect", (cx - w / 2, top + h * 0.5 - 5, cx + w / 2, top + h * 0.5 + 5), shade(stone, 0.9), radius=2,
            depth=0.3, tex="stone", line=1.3, clip=hole)
    # voussoirs and jambs
    r0, r1 = w / 2, w / 2 + 20
    ccx, ccy = cx, top + w / 2
    for i in range(9):
        a0 = math.pi + i * math.pi / 9 + 0.02
        a1 = math.pi + (i + 1) * math.pi / 9 - 0.02
        pts = [(ccx + r0 * math.cos(a0), ccy + r0 * math.sin(a0)), (ccx + r1 * math.cos(a0), ccy + r1 * math.sin(a0)),
               (ccx + r1 * math.cos(a1), ccy + r1 * math.sin(a1)), (ccx + r0 * math.cos(a1), ccy + r0 * math.sin(a1))]
        p.shape("poly", pts, shade(stone, rng.uniform(0.85, 1.1)), depth=0.2, tex="stone", line=1.5)
    for y in range(int(ccy), int(top + h), 26):
        for x0 in (cx - w / 2 - 20, cx + w / 2):
            p.shape("rect", (x0, y, x0 + 20, y + 24), shade(stone, rng.uniform(0.85, 1.1)), radius=2, depth=0.2,
                    tex="stone", line=1.3)
    p.shape("rect", (cx - w / 2 - 26, top + h - 4, cx + w / 2 + 26, top + h + 12), shade(stone, 1.1), radius=3,
            depth=0.3, tex="stone", line=1.5)
    # broken glass teeth still in the frame
    for x, y, s in ((cx - w / 2 + 4, top + h * 0.3, 1), (cx + w / 2 - 4, top + h * 0.72, -1)):
        p.shape("poly", [(x, y - 10), (x + s * 14, y), (x, y + 6)], hexc("#c8d8e8", 160), shadow=0, light=0, line=1.0,
                ao=0, clip=hole)
    return hole


def charred_beam(p, x0, y0, x1, y1, width):
    p.shape("line", [(x0, y0), (x1, y1)], hexc("#2c1e18"), width=width, depth=0.25, light=1.2, tex="wood_h",
            tex_amt=1.4, line=1.8)
    ux, uy = x1 - x0, y1 - y0
    ln = math.hypot(ux, uy)
    ux, uy = ux / ln, uy / ln
    nx, ny = -uy * width * 0.3, ux * width * 0.3
    pts = []
    for k in range(8):  # charred checks across the grain
        t = (k + 0.5) / 8
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        p.stroke([(x - nx, y - ny), (x + nx * 0.5 + ux * 4, y + ny * 0.5 + uy * 4)], hexc("#120a08"), 1.6)
        pts.append([(x - nx * 0.8, y - ny * 0.8), (x - nx * 0.2 + ux * 3, y - ny * 0.2 + uy * 3)])
    return pts


def rubble(p, x, y, rng, n=6, s=1.0, color=None):
    color = color or hexc("#86706a")
    for _ in range(n):
        rx, ry = x + rng.uniform(-40, 40) * s, y + rng.uniform(-8, 8) * s
        r = rng.uniform(8, 18) * s
        p.shape("poly", _blob(rx, ry - r * 0.4, r, r * 0.7, rng, 6, 0.25), shade(color, rng.uniform(0.8, 1.1)),
                depth=0.25, light=1.3, tex="stone", line=1.4)


def _burnt_scene(tall):
    MW, MH = (720, 1280) if tall else (W, H)
    floor_top = 1010 if tall else 430
    rng = random.Random(41 if tall else 40)
    old = painter.SS
    painter.SS = K
    try:
        img = Image.new("RGBA", (MW * K, MH * K), hexc("#1a1212"))
        d = ImageDraw.Draw(img)
        _brick_wall(d, rng, 0, floor_top, hexc("#5a4644"), hexc("#1c1212"), width=MW)
        _floor(d, rng, floor_top, height=MH, width=MW)
        _texture(img, "stone", 0.35)
        _grime(img, rng, 0, floor_top, 10 if not tall else 18, width=MW)
        # soot: the wall darkens toward the ceiling and above the windows
        soot = Image.new("L", img.size, 0)
        sd = ImageDraw.Draw(soot)
        for y in range(0, int(floor_top * K), 4):
            sd.line((0, y, MW * K, y), fill=int(200 * (1 - y / (floor_top * K)) ** 1.6))
        dark = Image.new("RGBA", img.size, (12, 6, 6, 0))
        dark.putalpha(soot)
        img.alpha_composite(dark)
        d = ImageDraw.Draw(img)
        d.rectangle((0, (floor_top - 14) * K, MW * K, (floor_top + 6) * K), fill=hexc("#3a2c2a"))
        d.line((0, (floor_top - 13) * K, MW * K, (floor_top - 13) * K), fill=hexc("#6a5250"), width=2 * K)
        d.rectangle((0, (floor_top + 4) * K, MW * K, (floor_top + 14) * K), fill=hexc("#120a0a"))
        # ash drifts on the floor
        ash = Image.new("L", img.size, 0)
        ad = ImageDraw.Draw(ash)
        for _ in range(14 if not tall else 10):
            x, y = rng.uniform(0, MW), rng.uniform(floor_top + 20, MH)
            r = rng.uniform(30, 80)
            ad.ellipse(((x - r) * K, (y - r * 0.18) * K, (x + r) * K, (y + r * 0.18) * K), fill=90)
        layer = Image.new("RGBA", img.size, (120, 112, 112, 0))
        layer.putalpha(ash.filter(ImageFilter.GaussianBlur(6 * K)))
        img.alpha_composite(layer)
        p = _props_painter(img)
        windows = [(360, 110, 150, 270)] if not tall else [(360, 330, 170, 330), (160, 640, 110, 240),
                                                          (560, 640, 110, 240)]
        for cx, top, w, h in windows:
            fire_window(p, cx, top, w, h, rng)
        banners = [(170, 120, 80, 210), (550, 120, 80, 210)] if not tall else [(170, 300, 90, 250), (550, 300, 90, 250),
                                                                               (360, 740, 100, 230)]
        for cx, top, w, h in banners:
            cult_banner(p, cx, top, w, h, rng)
        ember_lines = []
        # ceiling beams, one of them fallen
        if tall:
            for y in (40, 150):
                ember_lines += charred_beam(p, -10, y, MW + 10, y + 6, 30)
            ember_lines += charred_beam(p, 40, floor_top - 10, 250, 870, 30)
            ember_lines += charred_beam(p, MW - 30, floor_top - 20, 520, 900, 26)
        else:
            ember_lines += charred_beam(p, -10, 72, MW + 10, 80, 28)
            ember_lines += charred_beam(p, 470, floor_top + 20, 700, 250, 32)
            ember_lines += charred_beam(p, 20, floor_top + 10, 150, 330, 24)
        # rubble, a toppled brazier, bones and scattered embers on the floor
        rubble(p, 620, floor_top + 30, rng, 7)
        rubble(p, 70, floor_top + 24, rng, 6)
        rubble(p, 110, MH - 50, rng, 5, 1.5)
        rubble(p, MW - 90, MH - 70, rng, 5, 1.4)
        skull(p, 250, floor_top + 26, 0.8)
        bones(p, 520, floor_top + 40, 0.9)
        # lava-lit cracks through the floor
        cracks = []
        for sx, sy in ((200, floor_top + 60), (470, floor_top + 110), (330, MH - 90), (90, MH - 200 if tall else MH - 140)):
            pts = [(sx, sy)]
            for _ in range(6):
                sx += rng.uniform(-30, 50)
                sy += rng.uniform(-8, 14)
                pts.append((sx, sy))
            cracks.append(pts)
            b = rng.randrange(1, 5)
            cracks.append([pts[b], (pts[b][0] + rng.uniform(-30, 30), pts[b][1] + rng.uniform(10, 30))])
        dd = ImageDraw.Draw(p.img)
        for pts in cracks:
            dd.line([(x * K, y * K) for x, y in pts], fill=hexc("#120606"), width=int(8 * K), joint="curve")
        img = p.img
        warm = (255, 130, 70)
        pools = [(cx, top + h * 0.6, w * 2.2, h * 1.3, warm, 1.0) for cx, top, w, h in windows]
        pools += [(MW / 2, floor_top + (MH - floor_top) * 0.45, 420, 220, (200, 120, 100), 0.6)]
        for pts in cracks:
            x, y = pts[len(pts) // 2]
            pools.append((x, y, 130, 60, (255, 100, 40), 0.55))
        img = _light(img, (96, 82, 96), pools)
        for cx, top, w, h in windows:
            _glow(img, cx, top + h * 0.55, w * 1.4, (255, 120, 50), 110)
        _glow_lines(img, cracks, (255, 80, 20), 5.0, 10, 200)
        _glow_lines(img, cracks, (255, 120, 40), 2.4, 3, 255, core=(255, 200, 110))
        _glow_lines(img, ember_lines, (255, 110, 40), 1.2, 3, 200, core=(255, 190, 90))
        _motes(img, rng, 70 if not tall else 130, (0, 40, MW, MH), (255, 120, 40), 0.8, 2.2, core=(255, 220, 140))
        return _finish(img, (MW, MH), hud=not tall, vignette=200)
    finally:
        painter.SS = old


def burnt_keep():
    return _burnt_scene(False)


def burnt_keep_map():
    return _burnt_scene(True)


# ------------------------------------------------------------------ dragon lair

GOLD_C = hexc("#e2a834")


def _coin(d, x, y, r, col):
    """One coin drawn straight onto the K canvas (fast, for big hoards)."""
    rim = shade(col, 0.45)
    d.ellipse(((x - r - 0.6) * K, (y - r * 0.55 - 0.6) * K, (x + r + 0.6) * K, (y + r * 0.55 + 0.6) * K), fill=rim)
    d.ellipse(((x - r) * K, (y - r * 0.55) * K, (x + r) * K, (y + r * 0.55) * K), fill=col)
    d.ellipse(((x - r * 0.7) * K, (y - r * 0.4) * K, (x + r * 0.5) * K, (y + r * 0.2) * K), fill=shade(col, 1.25))
    d.ellipse(((x - r * 0.45) * K, (y - r * 0.3) * K, (x + r * 0.15) * K, (y - r * 0.02) * K), fill=shade(col, 1.55))


def gold_pile(p, cx, base, w, h, rng, gems=True, coins=None):
    """A mound of gold coins with loose coins, gems and the odd goblet."""
    mound = p.shape("chord", (cx - w / 2, base - h, cx + w / 2, base + h), hexc("#c88a24"), start=180, end=360,
                    depth=0.14, light=1.4, spec=0.6, tex="metal", tex_amt=0.8, line=1.8)
    d = ImageDraw.Draw(p.img)
    n = coins or int(w * h / 22)
    pts = []
    for _ in range(n):
        a = rng.uniform(math.pi * 1.02, math.pi * 1.98)
        r = math.sqrt(rng.random()) * 0.93
        pts.append((cx + math.cos(a) * w / 2 * r, base + math.sin(a) * h * r))
    for x, y in sorted(pts, key=lambda q: q[1]):  # back to front
        depth = (base - y) / h            # 0 at the base .. 1 at the top
        col = shade(GOLD_C, rng.uniform(0.8, 1.12) * (1.0 + 0.12 * depth))
        _coin(d, x, y, rng.uniform(3.2, 5.2) * (w / 300 + 0.6), col)
    if gems:
        for _ in range(max(2, int(w / 70))):
            a = rng.uniform(math.pi * 1.15, math.pi * 1.85)
            r = rng.uniform(0.3, 0.8)
            x, y = cx + math.cos(a) * w / 2 * r, base + math.sin(a) * h * r
            g = rng.uniform(4, 6.5) * (w / 300 + 0.6)
            col = rng.choice((hexc("#e0303a"), hexc("#2ac0b0"), hexc("#8a4aff"), hexc("#3a8ae0")))
            p.shape("poly", [(x, y - g), (x + g * 0.8, y), (x, y + g * 0.7), (x - g * 0.8, y)], col, light=1.6, line=1.0,
                    gloss=1.0, rim=0, ao=0.2)
    # loose coins spilling onto the floor
    for _ in range(int(w / 7)):
        x = cx + rng.uniform(-w * 0.62, w * 0.62)
        y = base + rng.uniform(-2, 14)
        _coin(d, x, y, rng.uniform(3.4, 5.0), shade(GOLD_C, rng.uniform(0.85, 1.05)))
    return mound


def goblet(p, x, base, s=1.0):
    g = hexc("#e7b440")
    p.shape("ellipse", (x - 10 * s, base - 5 * s, x + 10 * s, base + 3 * s), g, depth=0.3, line=1.2, spec=0.8, rim=0)
    p.shape("rect", (x - 2.5 * s, base - 22 * s, x + 2.5 * s, base - 2 * s), g, depth=0.3, line=1.1, spec=0.8, rim=0)
    p.shape("chord", (x - 12 * s, base - 46 * s, x + 12 * s, base - 16 * s), g, start=0, end=180, depth=0.25,
            light=1.4, line=1.3, spec=1.0)
    p.shape("ellipse", (x - 12 * s, base - 35 * s, x + 12 * s, base - 27 * s), shade(g, 0.6), depth=0.3, line=1.1, rim=0)
    p.shape("ellipse", (x - 3 * s, base - 26 * s, x + 3 * s, base - 20 * s), hexc("#e0303a"), line=0.8, gloss=1.0,
            rim=0)


def obsidian_pillar(p, x, top, bottom, w, rng):
    """A tall faceted obsidian column with a broken top and glassy highlights."""
    face = hexc("#2e2838")
    jag = [(x - w / 2, top + rng.uniform(10, 30)), (x - w * 0.2, top + rng.uniform(-6, 10)), (x + w * 0.05, top + 18),
           (x + w * 0.3, top - rng.uniform(0, 14)), (x + w / 2, top + rng.uniform(6, 24))]
    body = jag + [(x + w / 2, bottom), (x - w / 2, bottom)]
    m = p.shape("poly", body, face, depth=0.12, light=1.7, spec=1.0, line=1.8, rim=1.0, ink=hexc("#06040a"),
                tex="stone", tex_amt=0.4)
    # facet edges and a glassy streak
    for fx, col in ((x - w * 0.18, hexc("#3a3450")), (x + w * 0.22, hexc("#0e0a14"))):
        p.stroke([(fx, top + 24), (fx, bottom - 4)], col, 2.2)
    p.shape("line", [(x - w * 0.34, top + 34), (x - w * 0.3, bottom - 20)], hexc("#8a80b8", 120), width=w * 0.07,
            **NOLINE, clip=m)
    p.stroke([(x - w * 0.36, top + 40), (x - w * 0.33, top + (bottom - top) * 0.5)], hexc("#e0d8ff", 170), 1.6)
    return m


def dragon_skull(p, cx, cy, s, rng):
    """A colossal horned dragon skull in profile, snout to the left, resting on its jaw."""
    bone = hexc("#b0a07e")
    ink = hexc("#2a1a10")
    X = lambda x: cx + x * s  # noqa: E731
    Y = lambda y: cy + y * s  # noqa: E731
    P = lambda pts: [(X(x), Y(y)) for x, y in pts]  # noqa: E731
    # horns sweeping back, the far one first
    for (x0, y0), c1, c2, end, w, col in (((30, -50), (110, -120), (170, -90), (220, -150), 34, shade(bone, 0.78)),
                                          ((50, -36), (140, -80), (210, -40), (260, -110), 44, shade(bone, 0.95))):
        center = _bez((X(x0), Y(y0)), (X(c1[0]), Y(c1[1])), (X(c2[0]), Y(c2[1])), (X(end[0]), Y(end[1])))
        p.shape("poly", _tapered(center, w * s, 2, 1.0), col, depth=0.22, light=1.3, tex="bone", tex_amt=1.0,
                line=2.0, ink=ink)
        for i in range(2, 15, 3):
            (ax, ay), (bx, by) = center[i], center[i + 1]
            ln = math.hypot(bx - ax, by - ay) or 1
            nx, ny = -(by - ay) / ln, (bx - ax) / ln
            ww = w * s * 0.42 * (1 - i / 18)
            p.stroke([(ax - nx * ww, ay - ny * ww), (ax + nx * ww, ay + ny * ww)], shade(col, 0.6), 1.6)
    # lower jaw, slightly open
    p.shape("poly", P([(60, 10), (40, 64), (-60, 62), (-180, 58), (-200, 46), (-60, 36)]), shade(bone, 0.82),
            depth=0.2, tex="bone", tex_amt=0.9, line=2.0, ink=ink)
    for i in range(8):  # lower teeth
        tx = -178 + i * 17
        p.shape("poly", P([(tx - 5, 48), (tx + 5, 48), (tx, 32)]), hexc("#eee4cc"), depth=0.3, line=1.1, rim=0, ao=0.2,
                ink=ink)
    # cranium with a frill of spikes
    for i, (x, y) in enumerate(((-30, -62), (0, -70), (30, -66), (60, -54))):
        p.shape("poly", P([(x - 14, y + 14), (x + 12, y + 12), (x + 14 + i * 3, y - 26 - i * 3)]), shade(bone, 0.9),
                depth=0.3, tex="bone", line=1.6, rim=0, ink=ink)
    p.shape("ellipse", (X(-70), Y(-66), X(84), Y(40)), bone, depth=0.16, light=1.3, tex="bone", tex_amt=1.0, line=2.2,
            ink=ink)
    # upper jaw / snout
    snout = P([(-40, -54), (-150, -26), (-206, -10), (-222, 8), (-210, 30), (-60, 36), (-20, 20)])
    p.shape("poly", snout, shade(bone, 1.04), depth=0.18, light=1.3, tex="bone", tex_amt=1.0, line=2.0, ink=ink)
    for i in range(9):  # upper fangs
        tx = -196 + i * 16
        ln = 26 if i in (1, 7) else 15
        p.shape("poly", P([(tx - 5, 26), (tx + 5, 26), (tx + 1, 26 + ln)]), hexc("#f4ecd8"), depth=0.3, line=1.1,
                rim=0, ao=0.2, ink=ink)
    # nostril, eye socket under a spiked brow, and the fenestra behind it
    p.shape("ellipse", (X(-204), Y(-6), X(-186), Y(6)), DARK_HOLE, shadow=0, light=0, line=1.2, ink=ink)
    p.shape("poly", P([(-74, -34), (-30, -46), (-4, -30), (-16, -8), (-60, -12)]), DARK_HOLE, shadow=0, light=0,
            line=1.6, ink=ink)
    p.shape("poly", P([(-86, -40), (-40, -58), (0, -44), (-6, -38), (-40, -48)]), shade(bone, 1.08), depth=0.3,
            tex="bone", line=1.6, rim=0, ink=ink)
    p.shape("ellipse", (X(14), Y(-26), X(50), Y(6)), DARK_HOLE, shadow=0, light=0, line=1.4, ink=ink)
    p.stroke(P([(-150, -14), (-60, -2), (10, 14)]), shade(bone, 0.6), 2.2)
    for _ in range(5):  # cracks
        x, y = rng.uniform(-160, 60), rng.uniform(-50, 10)
        p.stroke(P([(x, y), (x + rng.uniform(-8, 8), y + 12), (x + rng.uniform(-12, 12), y + 22)]), shade(bone, 0.55),
                 1.4)
    return [(X(-38), Y(-26))]


DARK_HOLE = hexc("#140a0c")


def _lair_scene(tall):
    MW, MH = (720, 1280) if tall else (W, H)
    floor_top = 1010 if tall else 450
    rng = random.Random(51 if tall else 50)
    old = painter.SS
    painter.SS = K
    try:
        img = Image.new("RGBA", (MW * K, MH * K), hexc("#140c10"))
        d = ImageDraw.Draw(img)
        _rock_wall(d, rng, 0, floor_top, hexc("#3a2a30"), hexc("#0e080a"), width=MW, size=(90, 170),
                   grey=hexc("#2a2436"))
        _ground(d, rng, floor_top, MH, MW, hexc("#3a2c2c"), hexc("#100a0a"), speckle=hexc("#6a4a20"))
        _texture(img, "stone", 0.4)
        p = _props_painter(img)
        # a lava fall pouring out of a crack in the back wall into a glowing pool
        lx = MW * 0.3 if not tall else MW * 0.32
        ltop, lbot = (40, floor_top - 40) if not tall else (180, 660)
        center = _bez((lx, ltop), (lx + 14, ltop + (lbot - ltop) * 0.3), (lx - 16, ltop + (lbot - ltop) * 0.7),
                      (lx + 6, lbot))
        p.shape("poly", _jagged([(lx - 30, ltop - 10), (lx + 26, ltop - 20), (lx + 40, ltop + 30), (lx - 36, ltop + 40)],
                                rng, 6, 12, closed=False), hexc("#0e0808"), shadow=0, light=0, line=1.6, ao=0)
        p.shape("poly", _tapered(center[::-1], 76, 30, 1.2)[::-1], hexc("#ff6a1a"), shadow=0.85, light=1.4, depth=0.2,
                line=1.6, rim=0, ink=hexc("#4a0a04"))
        lava_lines = []
        for k in (-0.3, 0, 0.28):
            pts = [(x + k * (30 + 46 * i / len(center)), y) for i, (x, y) in enumerate(center)]
            p.stroke(pts, hexc("#ffd060"), 2.6)
            lava_lines.append(pts)
        for i in range(6):  # dark crust drifting in the flow
            x, y = center[3 + i * 2]
            p.shape("ellipse", (x - 8 + (i % 2) * 10, y - 4, x + 2 + (i % 2) * 10, y + 4), hexc("#6a1a0a"), **NOLINE)
        p.shape("ellipse", (lx - 90, lbot - 16, lx + 90, lbot + 20), hexc("#ff7a24"), shadow=0.85, light=1.4, depth=0.25,
                line=1.6, rim=0, ink=hexc("#4a0a04"))
        p.shape("ellipse", (lx - 50, lbot - 8, lx + 40, lbot + 8), hexc("#ffd060"), **NOLINE)
        # obsidian pillars and the skull on its hoard
        if tall:
            pillars = [(70, 120, floor_top + 20, 90), (650, 180, floor_top + 20, 84), (560, 480, 720, 56)]
            p.shape("poly", _jagged([(100, 700), (620, 700), (640, 760), (80, 760)], rng, 6, 30, closed=False),
                    hexc("#2e2228"), depth=0.25, tex="stone", line=1.8)
        else:
            pillars = [(60, 40, floor_top + 30, 90), (660, 60, floor_top + 30, 84)]
        for x, top, bottom, w in pillars:
            obsidian_pillar(p, x, top, bottom, w, rng)
        if tall:
            gold_pile(p, MW * 0.56, 700, 440, 110, rng)
            eyes = dragon_skull(p, MW * 0.58, 610, 0.95, rng)
        else:
            gold_pile(p, MW * 0.58, floor_top + 8, 480, 120, rng)
            eyes = dragon_skull(p, MW * 0.6, floor_top - 108, 1.05, rng)
        # foreground hoards
        piles = [(110, floor_top + 60, 240, 90), (MW - 110, floor_top + 50, 220, 80)]
        if tall:
            piles = [(120, floor_top + 50, 260, 110), (MW - 120, floor_top + 40, 240, 100), (150, 700, 180, 60),
                     (MW - 150, 700, 170, 56)]
        for x, b, w, h in piles:
            gold_pile(p, x, b, w, h, rng)
        goblet(p, piles[0][0] + 40, piles[0][1] - piles[0][3] * 0.55, 1.1)
        backgrounds_rocks(p, rng, [(70, MH - 30, 50), (MW - 70, MH - 20, 44)], hexc("#2e2228"))
        for x in (170, 560):
            p.shape("ellipse", (x - 6, MH - 90, x + 6, MH - 84), GOLD_C, depth=0.3, light=1.5, line=0.9, spec=0.8,
                    rim=0)
        # lava channels through the floor
        channels = []
        for sx, sy, ln in ((160, floor_top + 130, 200), (470, floor_top + 190, 220), (260, MH - 60, 260)):
            channels.append(_bez((sx, sy), (sx + ln * 0.3, sy - 24), (sx + ln * 0.6, sy + 30), (sx + ln, sy + 6), 16))
        for pts in channels:  # molten channels with a dark crust along their banks
            p.shape("line", pts, hexc("#1a0808"), width=20, shadow=0, light=0, line=0, ao=0.3)
            p.shape("line", pts, hexc("#ff6a1a"), width=11, shadow=0.8, light=1.4, depth=0.3, line=1.4, rim=0, ao=0,
                    ink=hexc("#3a0804"))
            for i in range(2, len(pts) - 2, 3):
                x, y = pts[i]
                p.shape("ellipse", (x - 5, y - 2, x + 4, y + 2), hexc("#5a1408"), **NOLINE)
        img = p.img
        pools = [(sx, sy + 20, 200, 160, (255, 170, 110), 0.6) for sx, sy in (eyes[0],)]
        pools += [(lx, (ltop + lbot) / 2, 240, (lbot - ltop) * 0.9, (255, 110, 40), 0.9),
                 (MW / 2, floor_top + (MH - floor_top) * 0.45, 440, 220, (230, 150, 100), 0.7)]
        pools += [(x, b - h * 0.5, w, h * 1.6, (255, 200, 110), 0.5) for x, b, w, h in piles]
        for pts in channels:
            x, y = pts[len(pts) // 2]
            pools.append((x, y, 160, 70, (255, 100, 40), 0.6))
        img = _light(img, (86, 70, 86), pools)
        _glow(img, lx, (ltop + lbot) / 2, 160, (255, 120, 40), 100)
        _glow(img, lx, lbot, 110, (255, 150, 60), 120)
        _glow_lines(img, lava_lines, (255, 170, 70), 2.0, 5, 150)
        _glow_lines(img, channels, (255, 90, 20), 6.0, 12, 170)
        _glow_lines(img, channels, (255, 190, 80), 1.2, 1.5, 200)
        for ex, ey in eyes:
            _glow(img, ex, ey, 28, (255, 90, 30), 120)
        _motes(img, rng, 80 if not tall else 150, (0, 40, MW, MH), (255, 120, 40), 0.8, 2.4, core=(255, 220, 140))
        return _finish(img, (MW, MH), hud=not tall, vignette=200)
    finally:
        painter.SS = old


def dragon_lair():
    return _lair_scene(False)


def dragon_lair_map():
    return _lair_scene(True)


# dungeon id -> (battle background, map background)
DUNGEONS = {
    "mushroom_cave": (mushroom_cave, mushroom_cave_map),
    "frozen_pass": (frozen_pass, frozen_pass_map),
    "burnt_keep": (burnt_keep, burnt_keep_map),
    "dragon_lair": (dragon_lair, dragon_lair_map),
}

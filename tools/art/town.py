"""Town hub art for Kıvılcımköy: the dusk background, building sprites and NPC busts.

The background is 720 x 1280 and opaque. Buildings are transparent sprites sized to the
rects the town screen places them at (see RECTS). Portraits are 256 x 256 busts.
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import icons
import painter
from painter import INK, Painter, _shift, hexc, shade

BW, BH = 720, 1280

# Where the town screen puts each building sprite on the 720 x 1280 background.
RECTS = {
    "gate": (210, 250, 300, 310),
    "smith": (20, 560, 320, 300),
    "merchant": (380, 560, 320, 300),
    "class_master": (20, 880, 320, 240),
    "inn": (380, 880, 320, 240),
}

STONE = hexc("#8d8494")
STONE_L = hexc("#aaa0ae")
ROCK = hexc("#7e7064")
WOOD = hexc("#8a5a32")
WOOD_L = hexc("#b07a45")
WOOD_D = hexc("#5e3b22")
IRON = hexc("#4b4f57")
STEEL = hexc("#c9d4de")
GOLD = hexc("#e7b440")
DARK = hexc("#221820")
VOID = hexc("#140c16")
WHITE = hexc("#ffffff")
GRASS = hexc("#6fa044")
LEAF = hexc("#4f8a3a")
WARM = hexc("#ffd36a")
FIRE = hexc("#ff8a2a")
PURPLE = hexc("#7b3fb0")
SKIN = hexc("#f2c393")
NOLINE = dict(shadow=0, light=0, line=0)


# ------------------------------------------------------------------ painter helpers

class TPainter(Painter):
    """Painter that does its per-shape work only inside each shape's bounding box.

    Same look as Painter, but the 720 x 1280 background has hundreds of shapes and full-canvas
    compositing made it very slow. It also tracks which pixels belong to solid shapes, so the
    silhouette outline in finish() skips soft glows (which would otherwise get a dark ink halo),
    and glow that reaches the sprite border fades out instead of being cut off.
    """

    def __init__(self, width, height):
        super().__init__(width, height)
        self.solid = Image.new("L", self.img.size, 0)

    def _paste(self, layer, x, y):
        w, h = self.img.size
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + layer.size[0]), min(h, y + layer.size[1])
        if x1 <= x0 or y1 <= y0:
            return
        part = layer.crop((x0 - x, y0 - y, x1 - x, y1 - y))
        self.img.paste(Image.alpha_composite(self.img.crop((x0, y0, x1, y1)), part), (x0, y0))

    def _fill(self, mask, color, origin=(0, 0)):
        bbox = mask.getbbox()
        if bbox is None:
            return
        m = mask.crop(bbox)
        solid = Image.new("RGBA", m.size, color)
        layer = Image.new("RGBA", m.size, (0, 0, 0, 0))
        layer.paste(solid, (0, 0), m)
        x, y = bbox[0] + origin[0], bbox[1] + origin[1]
        self._paste(layer, x, y)
        if color[3] > 0:
            box = (x, y, x + m.size[0], y + m.size[1])
            self.solid.paste(ImageChops.lighter(self.solid.crop(box), m), box[:2])

    def _paint(self, m, color, shadow=0.72, light=1.22, depth=0.14, line=1.6, ink=INK):
        bbox = m.getbbox()
        if bbox is None:
            return
        S = painter.SS
        size = min(bbox[2] - bbox[0], bbox[3] - bbox[1])
        k = max(1, int(size * depth))
        r = max(1, int(line * S))
        pad = k + r + 4
        w, h = self.img.size
        box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(w, bbox[2] + pad), min(h, bbox[3] + pad))
        c = m.crop(box)
        o = box[:2]
        self._fill(c, color, o)
        if shadow:
            self._fill(ImageChops.subtract(c, _shift(c, -k, -k)), shade(color, shadow), o)
        if light:
            self._fill(ImageChops.subtract(c, _shift(c, k // 2, k // 2)), shade(color, light), o)
        if line:
            self._fill(ImageChops.subtract(c, c.filter(ImageFilter.MinFilter(r * 2 + 1))), ink, o)

    def shape(self, kind, pts, color, shadow=0.72, light=1.22, depth=0.14, line=1.6, ink=INK, clip=None, **kw):
        m = self._mask(kind, pts, **kw)
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        self._paint(m, color, shadow, light, depth, line, ink)
        return m

    def finish(self, outline=2, outline_color=INK, ground_shadow=None, edge_fade=16):
        w, h = self.w, self.h
        out = self.img.resize((w, h), Image.LANCZOS)
        solid = self.solid.resize((w, h), Image.LANCZOS)
        if edge_fade:
            ramp = Image.new("L", (w, h), 255)
            d = ImageDraw.Draw(ramp)
            for i in range(edge_fade):
                d.rectangle((i, i, w - 1 - i, h - 1 - i), outline=int(255 * (i / edge_fade) ** 1.5))
            a = out.getchannel("A")
            a_solid = ImageChops.multiply(a, solid)
            a_glow = ImageChops.multiply(ImageChops.subtract(a, a_solid), ramp)
            out.putalpha(ImageChops.add(a_solid, a_glow))
        if outline:
            grown = solid.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(outline * 2 + 1))
            sil = Image.new("RGBA", out.size, outline_color)
            sil.putalpha(grown)
            out = Image.alpha_composite(sil, out)
        if ground_shadow:
            base = Image.new("RGBA", out.size, (0, 0, 0, 0))
            ImageDraw.Draw(base).ellipse(ground_shadow, fill=(0, 0, 0, 90))
            out = Image.alpha_composite(base.filter(ImageFilter.GaussianBlur(3)), out)
        return out

    def glow(self, center, radius, color, strength=0.8):
        S = painter.SS
        cx, cy = center[0] * S, center[1] * S
        blur = radius * S / 8
        half = int(radius * S + blur * 3 + 2)
        layer = Image.new("RGBA", (half * 2, half * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        steps = 12
        for i in range(steps, 0, -1):
            t = i / steps
            a = int(255 * strength * (1 - t) ** 1.6)
            rr = radius * t * S
            d.ellipse((half - rr, half - rr, half + rr, half + rr), fill=color[:3] + (a,))
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        self._paste(layer, int(cx) - half, int(cy) - half)


def _S():
    return painter.SS


def union(p, items):
    """Union mask of several (kind, pts[, kw]) primitives."""
    m = Image.new("L", p.img.size, 0)
    for it in items:
        kind, pts = it[0], it[1]
        kw = it[2] if len(it) > 2 else {}
        m = ImageChops.lighter(m, p._mask(kind, pts, **kw))
    return m


def paint(p, m, color, shadow=0.72, light=1.22, depth=0.14, line=1.6, ink=INK, clip=None):
    """TPainter.shape for an arbitrary mask (e.g. a union of blobs)."""
    if clip is not None:
        m = ImageChops.multiply(m, clip)
    p._paint(m, color, shadow, light, depth, line, ink)
    return m


def outline(p, m, width=1.6, ink=INK):
    p._paint(m, (0, 0, 0, 0), shadow=0, light=0, depth=0, line=width, ink=ink)


def pattern(p, clip, draw_fn):
    """Draws with raw ImageDraw (in final-pixel coords via the passed scale) clipped to a mask."""
    layer = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), _S())
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), clip))
    p.img = Image.alpha_composite(p.img, layer)


def tint(p, clip, color, top, bottom, a0, a1):
    """Vertical alpha gradient of one color, clipped to a mask (for dusk shading)."""
    S = _S()
    grad = Image.new("L", (1, p.img.size[1]), 0)
    for y in range(p.img.size[1]):
        t = min(1, max(0, (y / S - top) / max(1, bottom - top)))
        grad.putpixel((0, y), int(a0 + (a1 - a0) * t))
    grad = grad.resize(p.img.size)
    layer = Image.new("RGBA", p.img.size, color[:3] + (255,))
    layer.putalpha(ImageChops.multiply(grad, clip))
    p.img = Image.alpha_composite(p.img, layer)


def bricks(p, clip, box, color, rng, bh=14, bw=(22, 34), mortar=None, jitter=0.1, ink=None):
    x0, y0, x1, y1 = box
    mortar = mortar or shade(color, 0.55)
    ink = ink or shade(color, 0.42)

    def draw(d, S):
        d.rectangle((x0 * S, y0 * S, x1 * S, y1 * S), fill=mortar)
        y, row = y0, 0
        while y < y1:
            x = x0 - rng.randint(0, bw[0]) - (bw[0] // 2 if row % 2 else 0)
            while x < x1:
                w = rng.randint(*bw)
                c = shade(color, rng.uniform(1 - jitter, 1 + jitter))
                d.rounded_rectangle(((x + 1.2) * S, (y + 1.2) * S, (x + w - 1.2) * S, (y + bh - 1.2) * S),
                                    radius=3 * S, fill=c, outline=ink, width=max(1, int(0.9 * S)))
                d.line(((x + 4) * S, (y + 3) * S, (x + w - 5) * S, (y + 3) * S), fill=shade(c, 1.15),
                       width=max(1, int(1.2 * S)))
                x += w
            y += bh
            row += 1

    pattern(p, clip, draw)


def shingles(p, clip, box, color, rng, rows=10, tile=16):
    x0, y0, x1, y1 = box
    ink = shade(color, 0.45)

    def draw(d, S):
        rh = (y1 - y0) / rows
        for r in range(rows):
            y = y0 + r * rh
            off = 0 if r % 2 else tile / 2
            x = x0 - off
            while x < x1:
                c = shade(color, rng.uniform(0.9, 1.08))
                d.rounded_rectangle((x * S, y * S, (x + tile) * S, (y + rh + 3) * S), radius=4 * S, fill=c,
                                    outline=ink, width=max(1, int(1.0 * S)))
                d.line(((x + 3) * S, (y + rh) * S, (x + tile - 3) * S, (y + rh) * S), fill=shade(c, 0.75),
                       width=max(1, int(1.6 * S)))
                x += tile

    pattern(p, clip, draw)


def planks(p, clip, box, color, rng, width=14, vertical=True):
    x0, y0, x1, y1 = box
    ink = shade(color, 0.5)

    def draw(d, S):
        if vertical:
            x = x0
            while x < x1:
                c = shade(color, rng.uniform(0.9, 1.08))
                d.rectangle((x * S, y0 * S, (x + width) * S, y1 * S), fill=c, outline=ink, width=max(1, int(S)))
                d.line(((x + 3) * S, y0 * S, (x + 3) * S, y1 * S), fill=shade(c, 1.12), width=max(1, int(S)))
                x += width
        else:
            y = y0
            while y < y1:
                c = shade(color, rng.uniform(0.9, 1.08))
                d.rectangle((x0 * S, y * S, x1 * S, (y + width) * S), fill=c, outline=ink, width=max(1, int(S)))
                d.line((x0 * S, (y + 3) * S, x1 * S, (y + 3) * S), fill=shade(c, 1.12), width=max(1, int(S)))
                y += width

    pattern(p, clip, draw)


def line(p, pts, color, width, **kw):
    kw.setdefault("shadow", 0)
    kw.setdefault("light", 0)
    kw.setdefault("line", 0)
    return p.shape("line", pts, color, width=width, **kw)


def torch(p, cx, cy, s=1.0, glow=True):
    """Wall torch: flame centred at (cx, cy)."""
    if glow:
        p.glow((cx, cy), 64 * s, hexc("#ffae50"), 0.9)
        p.glow((cx, cy - 4 * s), 30 * s, hexc("#ffd080"), 0.7)
    p.shape("rect", (cx - 4 * s, cy + 8 * s, cx + 4 * s, cy + 38 * s), WOOD_D, radius=2 * s, line=1.2)
    p.shape("poly", [(cx - 9 * s, cy + 2 * s), (cx + 9 * s, cy + 2 * s), (cx + 5 * s, cy + 14 * s),
                     (cx - 5 * s, cy + 14 * s)], IRON, line=1.2)
    p.shape("rect", (cx - 3 * s, cy + 26 * s, cx + 14 * s, cy + 31 * s), IRON, radius=1, line=1)
    icons._flame(p, cx, cy - 6 * s, 0.62 * s)
    p.glow((cx, cy - 6 * s), 14 * s, hexc("#fff0a0"), 0.6)


def lantern(p, cx, cy, s=1.0, glow=True):
    """Hanging lantern body centred on (cx, cy)."""
    if glow:
        p.glow((cx, cy), 60 * s, hexc("#ffc060"), 0.7)
    p.shape("poly", [(cx - 11 * s, cy - 12 * s), (cx + 11 * s, cy - 12 * s), (cx, cy - 22 * s)], IRON, line=1.2)
    p.shape("rect", (cx - 9 * s, cy - 12 * s, cx + 9 * s, cy + 12 * s), WARM, radius=3 * s, light=1.45, depth=0.2,
            line=1.3)
    p.flat("ellipse", (cx - 4 * s, cy - 6 * s, cx + 4 * s, cy + 6 * s), hexc("#fff6c8"))
    for dx in (-9, 9):
        line(p, [(cx + dx * s, cy - 12 * s), (cx + dx * s, cy + 12 * s)], IRON, 2.4 * s)
    p.shape("rect", (cx - 12 * s, cy + 10 * s, cx + 12 * s, cy + 15 * s), IRON, radius=2, line=1.2)


def smoke(p, puffs, alpha=210):
    col = hexc("#cfc4cf", alpha)
    for cx, cy, r in puffs:
        p.shape("ellipse", (cx - r, cy - r, cx + r, cy + r), col, shadow=0.82, light=1.15, depth=0.2, line=1.1,
                ink=hexc("#5a4a60", 170))


def glowing_window(p, box, arched=False, bars=True, glow=True):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if glow:
        p.glow((cx, cy), max(x1 - x0, y1 - y0) * 1.1, hexc("#ffb850"), 0.55)
    p.shape("rect", (x0 - 4, y0 - 4, x1 + 4, y1 + 4), WOOD_D, radius=3, line=1.4, depth=0.2)
    if arched:
        w = x1 - x0
        m = union(p, [("rect", (x0, y0 + w / 2, x1, y1)), ("ellipse", (x0, y0, x1, y0 + w))])
        paint(p, m, WARM, shadow=0.85, light=1.4, depth=0.18, line=1.2)
    else:
        p.shape("rect", box, WARM, shadow=0.85, light=1.4, depth=0.18, line=1.2)
    p.flat("ellipse", (cx - (x1 - x0) * 0.3, cy - (y1 - y0) * 0.3, cx + (x1 - x0) * 0.3, cy + (y1 - y0) * 0.3),
           hexc("#fff4c0", 170))
    if bars:
        line(p, [(cx, y0), (cx, y1)], WOOD_D, 3)
        line(p, [(x0, cy), (x1, cy)], WOOD_D, 3)


def ground_shadow(p, box, alpha=110):
    x0, y0, x1, y1 = box
    S = _S()
    layer = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((x0 * S, y0 * S, x1 * S, y1 * S), fill=(20, 10, 24, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(4 * S))
    p.img = Image.alpha_composite(p.img, layer)


def tuft(p, x, y, s=1.0, color=GRASS):
    pts = [(x - 10 * s, y), (x - 8 * s, y - 10 * s), (x - 4 * s, y - 4 * s), (x, y - 14 * s), (x + 4 * s, y - 4 * s),
           (x + 9 * s, y - 11 * s), (x + 10 * s, y)]
    p.shape("poly", pts, color, depth=0.3, line=1.1)


# ------------------------------------------------------------------ background

def _sky(p):
    stops = [(0, "#1a1534"), (150, "#2f2150"), (250, "#5b2f66"), (330, "#a84866"), (400, "#e2704f"),
             (470, "#f7a24c"), (560, "#ffcf70")]
    S = _S()
    d = ImageDraw.Draw(p.img)
    cols = [(y, hexc(c)) for y, c in stops]
    for py in range(p.img.size[1]):
        y = py / S
        for (ya, ca), (yb, cb) in zip(cols, cols[1:]):
            if y <= yb:
                t = max(0, (y - ya) / (yb - ya))
                c = tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3)) + (255,)
                break
        else:
            c = cols[-1][1]
        d.line((0, py, p.img.size[0], py), fill=c)


def _stars(p, rng):
    S = _S()
    layer = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(70):
        x, y = rng.uniform(8, BW - 8), rng.uniform(8, 250)
        a = int(230 * (1 - y / 270))
        r = rng.choice((0.9, 1.2, 1.2, 1.6))
        d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=(255, 244, 220, a))
    for x, y, r in ((96, 60, 7), (590, 44, 8), (430, 110, 5), (250, 150, 5), (660, 190, 5), (40, 200, 4)):
        a = int(255 * (1 - y / 300))
        pts = []
        for i in range(8):
            rr = r if i % 2 == 0 else r * 0.28
            ang = i * math.pi / 4
            pts.append(((x + rr * math.cos(ang)) * S, (y + rr * math.sin(ang)) * S))
        d.polygon(pts, fill=(255, 246, 214, a))
    p.img = Image.alpha_composite(p.img, layer.filter(ImageFilter.GaussianBlur(S * 0.4)))


def _cloud(p, cx, cy, w, h, color, ink):
    parts = [("ellipse", (cx - w * 0.5, cy - h * 0.2, cx - w * 0.1, cy + h * 0.5)),
             ("ellipse", (cx - w * 0.3, cy - h * 0.55, cx + w * 0.1, cy + h * 0.45)),
             ("ellipse", (cx - w * 0.05, cy - h * 0.75, cx + w * 0.32, cy + h * 0.4)),
             ("ellipse", (cx + w * 0.15, cy - h * 0.3, cx + w * 0.5, cy + h * 0.5)),
             ("rect", (cx - w * 0.42, cy, cx + w * 0.42, cy + h * 0.5), {"radius": h * 0.25})]
    m = union(p, parts)
    paint(p, m, color, shadow=0.86, light=1.18, depth=0.22, line=1.2, ink=ink)
    # sunset light catches the underside
    p._fill(ImageChops.subtract(m, _shift(m, 0, -int(h * 0.22 * _S()))), shade(hexc("#ffb27a"), 1.0))
    outline(p, m, 1.2, ink)


def _tree(p, x, y, s=1.0, color=LEAF, dark=False):
    """Round cartoon tree standing at (x, y)."""
    trunk = hexc("#6b4428") if not dark else hexc("#3e2a2a")
    p.shape("poly", [(x - 7 * s, y), (x - 5 * s, y - 40 * s), (x + 5 * s, y - 40 * s), (x + 8 * s, y)], trunk,
            depth=0.3, line=1.4)
    parts = [("ellipse", (x - 34 * s, y - 70 * s, x + 2 * s, y - 34 * s)),
             ("ellipse", (x - 6 * s, y - 72 * s, x + 34 * s, y - 32 * s)),
             ("ellipse", (x - 26 * s, y - 100 * s, x + 24 * s, y - 52 * s)),
             ("ellipse", (x - 20 * s, y - 60 * s, x + 20 * s, y - 28 * s))]
    m = union(p, parts)
    paint(p, m, color, depth=0.16, line=1.6)
    for dx, dy in ((-14, -80), (8, -62), (-20, -52)):
        p.flat("ellipse", ((x + dx * s) - 5 * s, (y + dy * s) - 3 * s, (x + dx * s) + 5 * s, (y + dy * s) + 3 * s),
               shade(color, 1.3))


def _pine(p, x, y, s, color):
    for i in range(3):
        yy = y - 16 * s - i * 16 * s
        w = (22 - i * 5) * s
        p.shape("poly", [(x - w, yy + 10 * s), (x, yy - 22 * s), (x + w, yy + 10 * s)], color, depth=0.2, line=1.0,
                ink=shade(color, 0.5))
    p.shape("rect", (x - 3 * s, y - 8 * s, x + 3 * s, y), hexc("#3e2a2a"), line=0, shadow=0, light=0)


def _bush(p, x, y, s=1.0, color=LEAF, flowers=None):
    parts = [("ellipse", (x - 24 * s, y - 22 * s, x + 2 * s, y + 2 * s)),
             ("ellipse", (x - 10 * s, y - 30 * s, x + 16 * s, y)),
             ("ellipse", (x + 2 * s, y - 20 * s, x + 26 * s, y + 2 * s))]
    paint(p, union(p, parts), color, depth=0.2, line=1.4)
    if flowers:
        for dx, dy in ((-12, -14), (4, -22), (14, -9), (-2, -8)):
            p.shape("ellipse", (x + (dx - 3) * s, y + (dy - 3) * s, x + (dx + 3) * s, y + (dy + 3) * s), flowers,
                    line=0.8, depth=0.3)


def _fence(p, x0, y0, x1, y1, posts=4):
    col = hexc("#9a6a3c")
    for dy in (8, 20):
        p.shape("line", [(x0, y0 - 28 + dy), (x1, y1 - 28 + dy)], col, width=5, depth=0.35, line=1.2)
    for i in range(posts):
        t = i / (posts - 1)
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        p.shape("poly", [(x - 4, y), (x - 4, y - 30), (x, y - 35), (x + 4, y - 30), (x + 4, y)], col, depth=0.3,
                line=1.2)


def _lamp_post(p, x, y, s=1.0):
    """Street lantern standing at (x, y)."""
    p.glow((x, y - 62 * s), 70 * s, hexc("#ffbe60"), 0.65)
    p.shape("rect", (x - 3 * s, y - 60 * s, x + 3 * s, y), hexc("#3a3440"), radius=2, depth=0.3, line=1.2)
    p.shape("rect", (x - 7 * s, y - 6 * s, x + 7 * s, y + 2 * s), hexc("#3a3440"), radius=2, line=1.2)
    lantern(p, x, y - 64 * s, 0.75 * s, glow=False)
    p.glow((x, y - 64 * s), 18 * s, hexc("#fff0b0"), 0.7)


def _well(p, x, y, s=1.0):
    """Stone well whose base sits on (x, y)."""
    p.shape("line", [(x - 26 * s, y - 34 * s), (x - 26 * s, y - 84 * s)], WOOD, width=6 * s, depth=0.3, line=1.2)
    p.shape("line", [(x + 26 * s, y - 34 * s), (x + 26 * s, y - 84 * s)], WOOD, width=6 * s, depth=0.3, line=1.2)
    p.shape("poly", [(x - 38 * s, y - 76 * s), (x, y - 102 * s), (x + 38 * s, y - 76 * s), (x + 32 * s, y - 70 * s),
                     (x - 32 * s, y - 70 * s)], hexc("#a8473a"), depth=0.2, line=1.4)
    line(p, [(x - 26 * s, y - 72 * s), (x + 26 * s, y - 72 * s)], WOOD_D, 4 * s)
    line(p, [(x + 4 * s, y - 72 * s), (x + 4 * s, y - 50 * s)], hexc("#c8b690"), 1.5 * s)
    p.shape("rect", (x - 3 * s, y - 52 * s, x + 11 * s, y - 40 * s), WOOD, radius=2, line=1.1)
    m = union(p, [("rect", (x - 32 * s, y - 34 * s, x + 32 * s, y - 6 * s)),
                  ("ellipse", (x - 32 * s, y - 16 * s, x + 32 * s, y + 2 * s))])
    paint(p, m, STONE, depth=0.1, line=1.4)
    rng = random.Random(4)
    bricks(p, m, (x - 34 * s, y - 34 * s, x + 34 * s, y + 4 * s), STONE, rng, bh=9 * s, bw=(int(12 * s), int(18 * s)))
    outline(p, m, 1.4)
    p.shape("ellipse", (x - 34 * s, y - 42 * s, x + 34 * s, y - 26 * s), STONE_L, depth=0.2, line=1.4)
    p.shape("ellipse", (x - 26 * s, y - 39 * s, x + 26 * s, y - 29 * s), hexc("#1f2a3a"), **NOLINE)


def _cobbles(p, clip, rng):
    base = hexc("#c2a07a")
    ink = hexc("#5a4030")

    def draw(d, S):
        y = 540
        while y < BH + 10:
            t = (y - 540) / (BH - 540)
            h = 7 + 9 * t
            x = -rng.uniform(0, 20)
            while x < BW:
                w = h * rng.uniform(1.2, 1.9)
                c = shade(base, rng.uniform(0.82, 1.08))
                d.rounded_rectangle(((x + 1) * S, (y + 1) * S, (x + w - 1) * S, (y + h - 1) * S), radius=h * 0.4 * S,
                                    fill=c, outline=ink, width=max(1, int(0.9 * S)))
                d.line(((x + 3) * S, (y + 2.5) * S, (x + w - 4) * S, (y + 2.5) * S), fill=shade(c, 1.15),
                       width=max(1, int(1.1 * S)))
                x += w
            y += h

    pattern(p, clip, draw)


def _path_poly(center, widths):
    left, right = [], []
    n = len(center)
    for i, ((x, y), w) in enumerate(zip(center, widths)):
        a = center[max(0, i - 1)]
        b = center[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    return left + right[::-1]


def _catmull(pts, steps=8):
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


def _vignette(img):
    w, h = img.size
    v = Image.new("L", (w // 4, h // 4), 0)
    d = ImageDraw.Draw(v)
    steps = 30
    for i in range(steps):
        t = i / steps
        mx, my = w / 4 * 0.5 * t * 0.55, h / 4 * 0.5 * t * 0.5
        d.ellipse((mx - w / 16, my - h / 16, w / 4 - mx + w / 16, h / 4 - my + h / 16), fill=int(255 * t))
    v = v.filter(ImageFilter.GaussianBlur(10)).resize((w, h), Image.BILINEAR)
    dark = Image.new("RGBA", (w, h), (18, 8, 26, 255))
    dark.putalpha(v.point(lambda a: int(150 * (1 - a / 255) ** 1.6)))
    img.alpha_composite(dark)


def background(seed=5):
    rng = random.Random(seed)
    old = painter.SS
    painter.SS = 2
    try:
        p = TPainter(BW, BH)
        _sky(p)
        _stars(p, rng)
        # setting sun behind the far peaks, on the left (matches the top-left cel light)
        p.glow((150, 380), 260, hexc("#ffcf80"), 0.55)
        p.shape("ellipse", (92, 322, 208, 438), hexc("#ffe39a"), shadow=0, light=0, line=0)
        p.glow((150, 380), 90, hexc("#fff4c8"), 0.5)
        # clouds
        ink_c = hexc("#6a3a66")
        _cloud(p, 540, 238, 190, 46, hexc("#d98aa0"), ink_c)
        _cloud(p, 250, 282, 150, 34, hexc("#e89a96"), ink_c)
        _cloud(p, 640, 318, 110, 26, hexc("#f0a890"), ink_c)
        _cloud(p, 70, 196, 120, 30, hexc("#b77aa0"), ink_c)
        # far mountains
        far = [(-10, 420), (40, 360), (90, 330), (140, 368), (212, 282), (268, 330), (320, 300), (372, 350),
               (440, 262), (520, 336), (580, 298), (640, 340), (700, 286), (730, 310), (730, 600), (-10, 600)]
        m = p.shape("poly", far, hexc("#7a5690"), shadow=0.8, light=1.12, depth=0.05, line=1.2, ink=hexc("#3e2a58"))
        tint(p, m, hexc("#ff9a70"), 300, 460, 0, 90)
        for peak, lft, rgt in (((212, 282), (192, 306), (232, 304)), ((440, 262), (414, 292), (462, 290)),
                               ((700, 286), (680, 306), (716, 300)), ((320, 300), (306, 316), (334, 314))):
            snow = [lft, peak, rgt, (rgt[0] - 6, rgt[1] + 4), (peak[0] + 2, rgt[1] - 2), (lft[0] + 8, lft[1] + 6)]
            p.shape("poly", snow, hexc("#f4c8d8"), shadow=0.85, light=1.1, depth=0.2, line=1.0, ink=hexc("#3e2a58"))
        # rolling mid hills with pines
        mid = union(p, [("ellipse", (-120, 380, 260, 640)), ("ellipse", (160, 400, 520, 640)),
                        ("ellipse", (420, 370, 860, 640))])
        paint(p, mid, hexc("#4d5a7a"), shadow=0.82, light=1.12, depth=0.04, line=1.2, ink=hexc("#2c2a48"))
        for x, y, s in ((30, 452, 0.8), (60, 446, 1.0), (96, 460, 0.8), (560, 438, 0.9), (600, 430, 1.1),
                        (640, 440, 0.9), (690, 432, 1.0), (250, 456, 0.7), (470, 452, 0.75)):
            _pine(p, x, y, s, hexc("#34485e"))
        near = union(p, [("ellipse", (-160, 450, 300, 700)), ("ellipse", (420, 440, 900, 700))])
        paint(p, near, hexc("#4f7a4e"), shadow=0.8, light=1.15, depth=0.04, line=1.4, ink=hexc("#23302a"))
        tint(p, near, hexc("#ff9a60"), 450, 540, 60, 0)
        for x, y, s in ((24, 506, 0.9), (694, 498, 1.0), (660, 510, 0.8)):
            _pine(p, x, y, s, hexc("#2f5a3e"))
        # the big village hill
        hill = union(p, [("ellipse", (-70, 300, 790, 1340)), ("rect", (-20, 700, 740, 1300))])
        paint(p, hill, GRASS, shadow=0.85, light=1.1, depth=0.02, line=2.0)
        tint(p, hill, hexc("#ffc070"), 300, 420, 80, 0)
        tint(p, hill, hexc("#1f3a2a"), 700, 1280, 0, 120)
        # grass texture
        S = painter.SS

        def grass(d, S):
            for _ in range(900):
                x, y = rng.uniform(0, BW), rng.uniform(310, BH)
                k = 0.6 + 0.6 * (y - 300) / 980
                c = shade(GRASS, rng.uniform(0.62, 0.8))
                d.line(((x - 3 * k) * S, y * S, (x - 1 * k) * S, (y - 6 * k) * S), fill=c, width=max(1, int(1.4 * S)))
                d.line(((x + 1 * k) * S, y * S, (x + 3 * k) * S, (y - 7 * k) * S), fill=c, width=max(1, int(1.4 * S)))
            for _ in range(160):
                x, y = rng.uniform(0, BW), rng.uniform(330, BH)
                r = rng.uniform(1.4, 2.4)
                c = rng.choice((hexc("#ffe27a"), hexc("#ffffff"), hexc("#ff9ab8"), hexc("#b8a0ff")))
                d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=c)

        pattern(p, hill, grass)
        # paths: main road from the bottom to the gate, then branches to each door
        main = _catmull([(360, 1300), (352, 1150), (366, 1000), (356, 860), (362, 700), (360, 548)])
        widths = [52 + 88 * ((y - 548) / (1300 - 548)) ** 1.2 for _, y in main]
        pm = p._mask("poly", _path_poly(main, widths))
        for pts in ([(352, 925), (290, 890), (220, 872), (170, 862)],
                    [(364, 915), (430, 888), (500, 870), (548, 862)],
                    [(352, 1180), (280, 1140), (200, 1124), (170, 1122)],
                    [(356, 1172), (440, 1140), (520, 1124), (560, 1122)],
                    [(360, 560), (300, 552), (260, 548)], [(360, 560), (420, 552), (460, 548)]):
            pm = ImageChops.lighter(pm, p._mask("line", _catmull(pts), width=44))
        # plaza in front of the gate
        pm = ImageChops.lighter(pm, p._mask("ellipse", (250, 530, 470, 590)))
        paint(p, pm, hexc("#9a7650"), shadow=0.8, light=1.1, depth=0.02, line=0)
        _cobbles(p, pm.filter(ImageFilter.MinFilter(2 * S + 1)), rng)
        tint(p, pm, hexc("#1f1a2a"), 700, 1280, 0, 70)
        outline(p, pm, 1.8, hexc("#3a2a22"))
        # scenery (kept around the building spots)
        _tree(p, 40, 548, 1.0, hexc("#4a8038"))
        _tree(p, 694, 540, 1.1, hexc("#4f8a3a"))
        _tree(p, 160, 470, 0.7, hexc("#548e3c"))
        _tree(p, 575, 462, 0.75, hexc("#4f8a3a"))
        _well(p, 108, 548, 0.9)
        _bush(p, 206, 548, 0.9, hexc("#4f8a3a"), hexc("#ff8ab0"))
        _bush(p, 526, 548, 0.9, hexc("#548e3c"), hexc("#ffe27a"))
        _fence(p, 232, 494, 196, 520, 3)
        _fence(p, 488, 494, 526, 520, 3)
        for x, y in ((334, 664), (388, 664)):
            _lamp_post(p, x, y, 0.95)
        for _ in range(14):  # fireflies
            x, y = rng.uniform(20, 700), rng.uniform(470, 1110)
            p.glow((x, y), 9, hexc("#fff08a"), 0.9)
            p.flat("ellipse", (x - 1.5, y - 1.5, x + 1.5, y + 1.5), hexc("#fffbe0"))
        _fence(p, 4, 872, 60, 872, 3)
        _fence(p, 660, 872, 716, 872, 3)
        for x, y in ((330, 870), (392, 870), (318, 1140), (404, 1140)):
            _lamp_post(p, x, y, 1.0)
        _bush(p, 26, 1134, 1.0, hexc("#4a7a38"), hexc("#ff8ab0"))
        _bush(p, 696, 1136, 1.0, hexc("#4a7a38"), hexc("#ffe27a"))
        for x, y, s in ((250, 624, 0.8), (470, 640, 0.8), (300, 760, 0.9), (430, 800, 0.9), (260, 1060, 1.0),
                        (470, 1040, 1.0), (140, 1240, 1.2), (600, 1250, 1.2), (60, 700, 0.8), (680, 720, 0.8)):
            tuft(p, x, y, s, shade(GRASS, 0.9))
        img = p.finish(outline=0)
    finally:
        painter.SS = old
    _vignette(img)
    return img.convert("RGB")


# ------------------------------------------------------------------ buildings

def gate():
    p = TPainter(300, 310)
    rng = random.Random(3)
    # rocky outcrop the stair is cut into, with a grassy cap
    mound = union(p, [("ellipse", (14, 34, 286, 300)), ("ellipse", (8, 136, 124, 306)), ("ellipse", (176, 136, 292, 306)),
                      ("rect", (24, 200, 276, 306), {"radius": 16})])
    paint(p, mound, ROCK, depth=0.06, line=2)
    cap = p._mask("poly", [(0, 0), (300, 0), (300, 96), (262, 104), (240, 90), (214, 108), (180, 86), (150, 100),
                           (120, 84), (92, 106), (62, 90), (40, 110), (0, 100)])
    paint(p, mound, GRASS, depth=0.12, line=1.6, clip=cap)
    tint(p, ImageChops.multiply(mound, cap), hexc("#ffc070"), 30, 80, 90, 0)
    for box in ((22, 160, 92, 230), (210, 150, 282, 222), (26, 222, 100, 296), (200, 216, 280, 296),
                (44, 108, 110, 162), (192, 104, 258, 158)):
        p.shape("ellipse", box, shade(ROCK, rng.uniform(0.92, 1.1)), depth=0.16, line=1.4)
    # arch frame
    frame = union(p, [("pie", (54, 44, 246, 236), {"start": 180, "end": 360}), ("rect", (54, 140, 246, 300))])
    paint(p, frame, STONE, depth=0.05, line=2)
    bricks(p, frame, (54, 44, 246, 300), STONE, rng, bh=16, bw=(26, 38))
    outline(p, frame, 2)
    cx, cy = 150, 140
    for i in range(9):
        a0 = math.pi + i * math.pi / 9 + 0.02
        a1 = math.pi + (i + 1) * math.pi / 9 - 0.02
        r0, r1 = 62, 96
        pts = [(cx + r0 * math.cos(a0), cy + r0 * math.sin(a0)), (cx + r1 * math.cos(a0), cy + r1 * math.sin(a0)),
               (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1)), (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1))]
        p.shape("poly", pts, shade(STONE_L, 1.0 if i != 4 else 1.08), depth=0.18, line=1.4)
    # keystone with a carved skull
    p.shape("poly", [(134, 30), (166, 30), (160, 80), (140, 80)], STONE_L, depth=0.2, line=1.6)
    icons._skull(p, 150, 52, 0.55)
    # jamb stones
    for y in range(140, 300, 26):
        for x0, x1 in ((58, 88), (212, 242)):
            p.shape("rect", (x0 - (4 if (y // 26) % 2 else 0), y, x1 + (0 if (y // 26) % 2 else 4), y + 24),
                    STONE_L, radius=3, depth=0.2, line=1.3)
    # dark opening with stairs leading down
    hole = union(p, [("pie", (88, 78, 212, 202), {"start": 180, "end": 360}), ("rect", (88, 140, 212, 300))])
    p._fill(hole, VOID)
    p.glow((150, 196), 46, hexc("#8a50ff"), 0.35)
    y = 300
    for i in range(8):
        h = 18 - i * 1.6
        inset = 4 + i * 5
        col = shade(STONE, 0.95 * 0.8 ** i)
        p.shape("rect", (88 + inset, y - h, 212 - inset, y), col, depth=0.25, light=1.25, line=1.0,
                clip=hole)
        y -= h
    # torchlight on the lowest steps
    p.glow((150, 300), 60, hexc("#ff9a40"), 0.35)
    # half-raised portcullis
    grid = hexc("#3f4148")
    for x in range(96, 212, 16):
        p.shape("line", [(x, 80), (x, 160)], grid, width=5, depth=0.3, line=1.1, clip=hole)
        p.shape("poly", [(x - 4, 158), (x + 4, 158), (x, 172)], grid, depth=0.3, line=1.1, clip=hole)
    for yy in (112, 144):
        p.shape("line", [(88, yy), (212, yy)], grid, width=5, depth=0.3, line=1.1, clip=hole)
    outline(p, hole, 2)
    # cobweb in the upper corner of the arch
    web = hexc("#e8e4f0", 170)
    ax, ay = 98, 118
    for ang in (-80, -55, -30, -5):
        a = math.radians(ang)
        line(p, [(ax, ay), (ax + 40 * math.cos(a), ay + 40 * math.sin(a))], web, 1.0)
    for r in (14, 26, 38):
        pts = [(ax + r * math.cos(math.radians(a)), ay + r * math.sin(math.radians(a))) for a in range(-80, 0, 12)]
        line(p, pts, web, 1.0)
    # threshold and ivy
    p.shape("rect", (68, 292, 232, 306), STONE_L, radius=4, depth=0.3, line=1.4)
    ivy = [(238, 100), (230, 130), (240, 160), (232, 196), (240, 230)]
    line(p, _catmull(ivy), hexc("#3a6a2a"), 2.5)
    for i, (x, yy) in enumerate(_catmull(ivy, 3)[::2]):
        dx = 7 if i % 2 else -7
        p.shape("ellipse", (x + dx - 6, yy - 4, x + dx + 6, yy + 5), hexc("#5a9a3a"), depth=0.3, line=1.0)
    # torches
    torch(p, 30, 150, 1.0)
    torch(p, 270, 150, 1.0)
    # a little skull and bones by the door, grass at the foot
    p.shape("line", [(24, 300), (48, 292)], hexc("#ece3c8"), width=5, depth=0.3, line=1.1)
    icons._skull(p, 44, 286, 0.42)
    for x, s in ((82, 0.8), (226, 0.9), (262, 0.7), (18, 0.7)):
        tuft(p, x, 304, s)
    out = p.finish(outline=2, ground_shadow=(14, 290, 286, 310))
    return out


def smith():
    p = TPainter(320, 300)
    rng = random.Random(8)
    # chimney and smoke
    smoke(p, [(76, 34, 14), (94, 22, 13), (116, 16, 10), (134, 14, 7)])
    ch = p.shape("rect", (56, 44, 94, 130), STONE, depth=0.1, line=1.6)
    bricks(p, ch, (56, 44, 94, 130), STONE, rng, bh=11, bw=(14, 20))
    outline(p, ch, 1.6)
    p.shape("rect", (50, 40, 100, 52), STONE_L, radius=3, depth=0.3, line=1.4)
    p.glow((75, 40), 16, hexc("#ff9a40"), 0.5)
    # side wall (depth to the right)
    side = p.shape("poly", [(280, 132), (304, 118), (304, 276), (280, 292)], shade(STONE, 0.7), depth=0.08,
                   line=1.6)
    bricks(p, side, (280, 110, 306, 294), shade(STONE, 0.72), rng, bh=14, bw=(12, 18))
    outline(p, side, 1.6)
    # front stone wall
    wall = p.shape("rect", (24, 132, 282, 292), STONE, depth=0.04, line=1.8)
    bricks(p, wall, (24, 132, 282, 292), STONE, rng, bh=16, bw=(24, 36))
    outline(p, wall, 1.8)
    # roof with timber gable band
    p.shape("rect", (22, 120, 284, 138), WOOD, radius=2, depth=0.3, line=1.5)
    roof = p.shape("poly", [(8, 126), (312, 126), (304, 112), (266, 58), (58, 58), (16, 112)], hexc("#9a4632"),
                   depth=0.06, line=1.8)
    shingles(p, roof, (8, 58, 312, 126), hexc("#a84c36"), rng, rows=5, tile=22)
    tint(p, roof, hexc("#ffb070"), 58, 126, 60, 0)
    outline(p, roof, 1.8)
    p.shape("rect", (54, 52, 270, 62), WOOD_D, radius=3, depth=0.3, line=1.4)
    # open front with the forge inside
    hole = p.shape("rect", (122, 170, 262, 292), hexc("#241418"), shadow=0, light=0, line=1.6)
    p.glow((170, 250), 120, hexc("#ff8a2a"), 0.75)
    p.shape("poly", [(134, 172), (208, 172), (194, 212), (148, 212)], hexc("#4a3a40"), depth=0.2, line=1.3,
            clip=hole)
    hearth = p.shape("rect", (138, 210, 204, 292), hexc("#8a4a3a"), depth=0.1, line=1.4)
    bricks(p, hearth, (138, 210, 204, 292), hexc("#9a5040"), rng, bh=10, bw=(14, 20))
    outline(p, hearth, 1.4)
    p.shape("rect", (148, 232, 194, 260), hexc("#ff7a20"), shadow=0.8, light=1.5, depth=0.25, line=1.3)
    for x in (156, 168, 182):
        p.flat("ellipse", (x - 5, 246, x + 5, 256), hexc("#ffe07a"))
    icons._flame(p, 171, 236, 0.55)
    p.glow((171, 244), 30, hexc("#fff0a0"), 0.6)
    # tools hanging on the back wall, rim-lit by the fire
    for x in (220, 236, 250):
        line(p, [(x, 180), (x, 214)], hexc("#6b4428"), 3.5)
    p.shape("rect", (214, 206, 228, 216), IRON, radius=2, line=1.1)
    p.shape("line", [(236, 214), (232, 226), (240, 226)], IRON, width=3, line=1.0)
    p.shape("ellipse", (245, 208, 256, 222), IRON, line=1.1)
    # lintel beam and corner posts
    p.shape("rect", (114, 160, 270, 176), WOOD, radius=2, depth=0.3, line=1.5)
    for x in (114, 256):
        p.shape("rect", (x, 170, x + 14, 294), WOOD, radius=2, depth=0.25, line=1.5)
    # hanging sign with an anvil
    line(p, [(70, 150), (112, 150)], IRON, 3)
    for x in (76, 104):
        line(p, [(x, 150), (x, 160)], IRON, 1.6)
    p.shape("rect", (70, 158, 110, 184), WOOD_L, radius=4, depth=0.2, line=1.4)
    p.shape("poly", [(78, 166), (104, 166), (100, 172), (94, 172), (96, 178), (84, 178), (86, 172), (80, 170)],
            IRON, depth=0.2, line=1.0)
    # sword rack against the wall
    for x in (34, 108):
        p.shape("rect", (x, 206, x + 8, 294), WOOD, radius=2, depth=0.3, line=1.2)
    p.shape("rect", (32, 266, 118, 276), WOOD, radius=2, depth=0.3, line=1.2)
    for x, c in ((52, STEEL), (72, hexc("#e0e6ee")), (92, hexc("#b9c6d3"))):
        p.shape("poly", [(x - 4, 214), (x + 4, 214), (x + 4, 280), (x, 288), (x - 4, 280)], c, depth=0.35,
                light=1.3, line=1.2)
        p.shape("line", [(x - 10, 214), (x + 10, 214)], GOLD, width=5, line=1.1)
        p.shape("line", [(x, 212), (x, 198)], hexc("#5a3a22"), width=5, line=1.1)
        p.shape("ellipse", (x - 4, 192, x + 4, 200), GOLD, line=1.0)
    p.shape("rect", (30, 222, 120, 230), WOOD, radius=2, depth=0.3, line=1.2)
    # water barrel with steam
    p.shape("rect", (270, 244, 312, 296), WOOD, radius=9, depth=0.15, line=1.5)
    for y in (254, 284):
        line(p, [(271, y), (311, y)], IRON, 3.5)
    p.shape("ellipse", (272, 240, 310, 252), hexc("#3a6a8a"), depth=0.3, light=1.3, line=1.3)
    smoke(p, [(284, 228, 7), (296, 216, 6)], alpha=150)
    # anvil on a block with a hammer leaning on it
    p.shape("rect", (178, 262, 224, 296), WOOD_D, radius=3, depth=0.2, line=1.4)
    p.shape("rect", (186, 250, 216, 264), IRON, radius=2, depth=0.2, line=1.3)
    p.shape("poly", [(150, 236), (240, 236), (240, 250), (176, 252), (164, 246)], hexc("#5c616b"), depth=0.25,
            light=1.3, line=1.5)
    line(p, [(168, 239), (236, 239)], hexc("#9aa3ad"), 2)
    p.shape("line", [(244, 294), (232, 254)], hexc("#6b4428"), width=6, line=1.2)
    p.shape("poly", [(220, 244), (242, 238), (246, 252), (224, 258)], IRON, depth=0.3, line=1.2)
    for x, s in ((18, 0.8), (140, 0.7), (300, 0.7)):
        tuft(p, x, 298, s)
    return p.finish(outline=2, ground_shadow=(6, 280, 316, 300))


def merchant():
    p = TPainter(320, 300)
    rng = random.Random(12)
    gold = hexc("#f0c24a")
    # back of the wagon with shelves
    back = p.shape("rect", (36, 92, 284, 222), WOOD_D, depth=0.05, line=1.6)
    planks(p, back, (36, 92, 284, 222), WOOD_D, rng, width=16)
    outline(p, back, 1.6)
    p.glow((250, 160), 90, hexc("#ffc060"), 0.45)
    colors = ["#e0303a", "#3a8aff", "#3ad07a", "#b05aff", "#ffcf3a", "#ff7ab0", "#3ad0d0", "#e0303a"]
    for shelf_y in (160, 206):
        p.shape("rect", (40, shelf_y, 280, shelf_y + 8), WOOD_L, radius=2, depth=0.3, line=1.2)
        x = 58
        i = 0
        while x < 270:
            c = hexc(colors[(i + shelf_y) % len(colors)])
            kind = (i + shelf_y // 10) % 3
            if kind == 0:
                icons._potion(p, x, shelf_y - 14, 0.55, c)
                x += 26
            elif kind == 1:  # tall bottle
                p.shape("rect", (x - 3, shelf_y - 36, x + 3, shelf_y - 26), hexc("#cfe3ea"), radius=2, line=1.0)
                p.shape("rect", (x - 8, shelf_y - 28, x + 8, shelf_y), c, radius=4, light=1.45, depth=0.25, line=1.2)
                p.flat("rect", (x - 5, shelf_y - 24, x - 2, shelf_y - 6), hexc("#ffffff", 170), radius=1)
                p.shape("rect", (x - 4, shelf_y - 40, x + 4, shelf_y - 35), hexc("#8a5a34"), radius=1, line=1.0)
                x += 22
            else:  # little jar
                p.shape("rect", (x - 9, shelf_y - 18, x + 9, shelf_y), c, radius=5, light=1.45, depth=0.25, line=1.2)
                p.shape("rect", (x - 10, shelf_y - 22, x + 10, shelf_y - 16), hexc("#d8c8a0"), radius=2, line=1.0)
                x += 24
            i += 1
    # poles
    for x in (24, 284):
        p.shape("rect", (x, 72, x + 12, 294), WOOD, radius=3, depth=0.3, line=1.5)
    # striped canopy fanning out from the ridge
    canopy = p._mask("poly", [(34, 38), (286, 38), (314, 104), (6, 104)])
    n = 8
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        pts = [(34 + 252 * t0, 38), (34 + 252 * t1, 38), (6 + 308 * t1, 104), (6 + 308 * t0, 104)]
        col = PURPLE if i % 2 == 0 else gold
        p.shape("poly", pts, col, depth=0.1, light=1.18, line=0, clip=canopy)
    tint(p, canopy, hexc("#1a0f2a"), 38, 104, 0, 60)
    outline(p, canopy, 1.8)
    # scalloped valance
    w = 308 / n
    for i in range(n):
        x0 = 6 + i * w
        col = PURPLE if i % 2 == 0 else gold
        p.shape("pie", (x0, 92, x0 + w, 124), col, start=0, end=180, depth=0.2, line=1.5)
    p.shape("rect", (4, 99, 316, 109), hexc("#5a2a86"), radius=3, depth=0.3, line=1.5)
    p.shape("rect", (28, 32, 292, 42), hexc("#5a2a86"), radius=4, depth=0.3, line=1.5)
    # sign with a coin above the canopy
    for x in (136, 184):
        line(p, [(x, 34), (x, 26)], IRON, 2.5)
    p.shape("rect", (110, 3, 210, 29), WOOD_L, radius=6, depth=0.15, line=1.6)
    p.shape("ellipse", (147, 3, 173, 29), gold, light=1.35, depth=0.2, line=1.4)
    p.shape("ellipse", (153, 9, 167, 23), shade(gold, 0.85), shadow=0, light=0, line=1.0)
    p.shape("poly", [(160, 11), (164, 16), (160, 21), (156, 16)], hexc("#fff0b0"), line=0.8)
    for x in (128, 192):
        p.flat("ellipse", (x - 3, 13, x + 3, 19), hexc("#fff0b0", 200))
    # hanging lantern
    line(p, [(252, 110), (252, 124)], IRON, 2.2)
    lantern(p, 252, 142, 0.85)
    # counter with a purple cloth
    counter = p.shape("rect", (18, 216, 302, 282), WOOD, depth=0.06, line=1.6)
    planks(p, counter, (18, 216, 302, 282), WOOD, rng, width=13, vertical=False)
    outline(p, counter, 1.6)
    p.shape("rect", (12, 208, 308, 222), WOOD_L, radius=3, depth=0.3, line=1.5)
    cloth = [(92, 214), (228, 214), (224, 250), (208, 242), (192, 252), (176, 242), (160, 252), (144, 242),
             (128, 252), (112, 242), (96, 250)]
    p.shape("poly", cloth, PURPLE, depth=0.2, line=1.4)
    line(p, [(94, 222), (226, 222)], gold, 3)
    # coins and a scale on the counter
    for x, y in ((236, 204), (248, 206), (242, 200)):
        p.shape("ellipse", (x - 7, y - 3, x + 7, y + 4), gold, line=1.0, depth=0.3)
    # wagon wheels
    for cx in (92, 228):
        p.shape("ellipse", (cx - 26, 250, cx + 26, 298), WOOD, depth=0.12, line=1.6)
        p.shape("ellipse", (cx - 19, 257, cx + 19, 291), hexc("#3a2418"), **NOLINE)
        for a in range(0, 180, 45):
            r = math.radians(a)
            line(p, [(cx - 20 * math.cos(r), 274 - 17 * math.sin(r)), (cx + 20 * math.cos(r), 274 + 17 * math.sin(r))],
                 WOOD_L, 4)
        p.shape("ellipse", (cx - 6, 268, cx + 6, 280), IRON, line=1.1)
    # crates and a sack
    c1 = p.shape("rect", (4, 238, 58, 294), WOOD_L, radius=3, depth=0.15, line=1.5)
    line(p, [(8, 242), (54, 290)], WOOD, 4)
    line(p, [(54, 242), (8, 290)], WOOD, 4)
    p.shape("rect", (4, 238, 58, 294), (0, 0, 0, 0), radius=3, shadow=0, light=0, line=1.5)
    p.shape("rect", (10, 202, 52, 240), WOOD_L, radius=3, depth=0.15, line=1.4)
    for x, y in ((18, 196), (30, 192), (42, 197), (24, 202), (38, 202)):
        p.shape("ellipse", (x - 7, y - 7, x + 7, y + 7), hexc("#e0303a"), light=1.4, line=1.1)
    p.shape("ellipse", (262, 246, 314, 298), hexc("#c8a06a"), depth=0.15, line=1.5)
    p.shape("poly", [(278, 250), (298, 250), (304, 234), (272, 234)], hexc("#c8a06a"), depth=0.2, line=1.3)
    line(p, [(276, 250), (300, 250)], hexc("#7a5a3a"), 3)
    return p.finish(outline=2, ground_shadow=(4, 282, 316, 300))


def _banner(p, x0, y0, x1, y1, color, symbol):
    cx = (x0 + x1) / 2
    p.shape("poly", [(x0, y0), (x1, y0), (x1, y1), (cx, y1 - 14), (x0, y1)], color, depth=0.14, line=1.5)
    line(p, [(x0 + 3, y0 + 6), (x1 - 3, y0 + 6)], GOLD, 2.5)
    cy = (y0 + y1) / 2 - 4
    if symbol == "sword":
        p.shape("poly", [(cx - 3, cy - 18), (cx + 3, cy - 18), (cx + 3, cy + 10), (cx - 3, cy + 10)], STEEL,
                light=1.3, line=1.1)
        p.shape("poly", [(cx - 3, cy - 18), (cx, cy - 24), (cx + 3, cy - 18)], STEEL, line=1.1)
        line(p, [(cx - 9, cy + 10), (cx + 9, cy + 10)], GOLD, 4, line=1.0)
        p.shape("line", [(cx, cy + 12), (cx, cy + 20)], hexc("#5a3a22"), width=4, line=1.0)
    elif symbol == "staff":
        p.shape("line", [(cx - 6, cy + 20), (cx + 4, cy - 10)], WOOD_L, width=4, line=1.0)
        p.glow((cx + 5, cy - 14), 12, hexc("#8ae0ff"), 0.9)
        p.shape("ellipse", (cx - 1, cy - 20, cx + 11, cy - 8), hexc("#8ae0ff"), light=1.5, line=1.1)
    elif symbol == "dagger":
        p.shape("poly", [(cx - 3, cy - 12), (cx, cy - 20), (cx + 3, cy - 12), (cx + 3, cy + 6), (cx - 3, cy + 6)],
                STEEL, light=1.3, line=1.1)
        line(p, [(cx - 7, cy + 6), (cx + 7, cy + 6)], GOLD, 3.5, line=1.0)
        p.shape("line", [(cx, cy + 8), (cx, cy + 16)], hexc("#3a2a3a"), width=4, line=1.0)


def class_master():
    p = TPainter(320, 240)
    rng = random.Random(21)
    # side banner poles
    for x, bx0, bx1, col, sym in ((34, 40, 88, hexc("#c63a2f"), "sword"), (282, 232, 280, hexc("#3566b8"), "staff")):
        p.shape("rect", (x - 3, 56, x + 3, 234), WOOD, radius=2, depth=0.3, line=1.3)
        p.shape("ellipse", (x - 6, 48, x + 6, 60), GOLD, light=1.4, line=1.2)
        line(p, [(min(x, bx0) - 2, 66), (max(x, bx1) + 2, 66)], WOOD, 4, line=1.1)
        _banner(p, bx0, 66, bx1, 150, col, sym)
    # the tower
    body = p.shape("rect", (98, 76, 222, 226), STONE, depth=0.1, line=1.8)
    bricks(p, body, (98, 76, 222, 226), STONE, rng, bh=15, bw=(22, 32))
    tint(p, body, hexc("#1a1024"), 70, 226, 0, 40)
    # round-tower shading: darker right third, light left edge
    rshade = p._mask("rect", (182, 70, 222, 230))
    p._fill(ImageChops.multiply(body, rshade), hexc("#1a1024", 70))
    lshade = p._mask("rect", (98, 70, 110, 230))
    p._fill(ImageChops.multiply(body, lshade), hexc("#ffe0c0", 50))
    outline(p, body, 1.8)
    p.shape("rect", (90, 212, 230, 234), STONE_L, radius=4, depth=0.25, line=1.5)
    # conical slate roof with a pennant
    line(p, [(160, 30), (160, 8)], WOOD_D, 3, line=1.0)
    p.shape("poly", [(160, 8), (186, 14), (160, 22)], hexc("#e7b440"), depth=0.2, line=1.1)
    roof = p.shape("poly", [(84, 90), (236, 90), (160, 22)], hexc("#4a5f94"), depth=0.08, line=1.8)
    shingles(p, roof, (84, 22, 236, 92), hexc("#56699e"), rng, rows=5, tile=18)
    outline(p, roof, 1.8)
    p.shape("rect", (86, 84, 234, 96), hexc("#3a4a78"), radius=3, depth=0.3, line=1.4)
    p.shape("ellipse", (154, 20, 166, 32), GOLD, light=1.4, line=1.1)
    # window, green banner, door
    glowing_window(p, (146, 104, 174, 128), arched=True)
    _banner(p, 140, 136, 180, 188, hexc("#3a9a4a"), "dagger")
    for x in (138, 182):
        p.shape("ellipse", (x - 4, 132, x + 4, 140), GOLD, line=1.0)
    door = union(p, [("rect", (138, 206, 182, 226)), ("ellipse", (138, 192, 182, 220))])
    paint(p, door, WOOD, depth=0.12, line=1.5)
    line(p, [(160, 194), (160, 224)], WOOD_D, 2)
    p.shape("ellipse", (170, 210, 176, 216), GOLD, line=0.8)
    # training dummy and weapon barrel
    p.shape("line", [(60, 232), (60, 170)], WOOD, width=6, depth=0.3, line=1.2)
    p.shape("line", [(40, 188), (80, 188)], WOOD, width=5, depth=0.3, line=1.2)
    p.shape("ellipse", (46, 176, 74, 224), hexc("#d8b878"), depth=0.15, line=1.4)
    line(p, [(48, 200), (72, 200)], hexc("#8a6a3a"), 2)
    p.shape("ellipse", (50, 150, 70, 172), hexc("#d8b878"), depth=0.2, line=1.3)
    p.shape("ellipse", (54, 188, 66, 200), hexc("#c63a2f"), line=1.0)
    p.shape("ellipse", (57, 191, 63, 197), WHITE, **NOLINE)
    p.shape("rect", (242, 198, 276, 234), WOOD, radius=8, depth=0.15, line=1.4)
    line(p, [(243, 206), (275, 206)], IRON, 3)
    line(p, [(243, 226), (275, 226)], IRON, 3)
    for x, top in ((250, 164), (262, 170), (270, 176)):
        line(p, [(x, 198), (x - 2, top)], WOOD_L, 4, line=1.0)
    p.shape("poly", [(246, 170), (252, 156), (256, 172)], STEEL, line=1.0)
    p.glow((261, 168), 8, hexc("#8ae0ff"), 0.9)
    for x, s in ((20, 0.8), (110, 0.7), (228, 0.7), (304, 0.8)):
        tuft(p, x, 238, s)
    return p.finish(outline=2, ground_shadow=(14, 222, 306, 240))


def inn():
    p = TPainter(320, 240)
    rng = random.Random(33)
    plaster = hexc("#f0dcb4")
    beam = hexc("#5e3b22")
    # chimney
    smoke(p, [(254, 24, 8), (266, 14, 7), (280, 8, 5)], alpha=180)
    ch = p.shape("rect", (238, 36, 266, 72), STONE, depth=0.15, line=1.5)
    bricks(p, ch, (238, 36, 266, 72), STONE, rng, bh=10, bw=(10, 16))
    outline(p, ch, 1.5)
    p.shape("rect", (234, 32, 270, 40), STONE_L, radius=2, line=1.3)
    # walls with timber framing
    wall = p.shape("rect", (46, 96, 298, 230), plaster, depth=0.04, line=1.8)
    tint(p, wall, hexc("#ff9a50"), 96, 230, 30, 0)
    for x in (46, 110, 232, 290):
        p.shape("rect", (x, 96, x + 8, 230), beam, radius=1, depth=0.25, line=1.2)
    for a, b in (((54, 100), (110, 130)), ((290, 100), (240, 130))):
        line(p, [a, b], beam, 6, line=1.1)
    p.shape("rect", (44, 124, 300, 132), beam, radius=1, depth=0.25, line=1.2)
    outline(p, wall, 1.8)
    # roof with a dormer
    roof = p.shape("poly", [(24, 102), (312, 102), (272, 32), (70, 32)], hexc("#c0553a"), depth=0.05, line=1.8)
    shingles(p, roof, (22, 32, 314, 102), hexc("#c85a3c"), rng, rows=5, tile=20)
    tint(p, roof, hexc("#ffc080"), 32, 102, 70, 0)
    outline(p, roof, 1.8)
    p.shape("rect", (66, 28, 280, 38), hexc("#8a3a2a"), radius=3, depth=0.3, line=1.4)
    p.shape("rect", (140, 48, 184, 88), plaster, depth=0.15, line=1.5)
    p.shape("poly", [(130, 54), (194, 54), (162, 26)], hexc("#a84632"), depth=0.15, line=1.5)
    glowing_window(p, (150, 58, 174, 82))
    # glowing windows with flower boxes
    for x0 in (62, 244):
        glowing_window(p, (x0, 142, x0 + 40, 182))
        p.shape("rect", (x0 - 6, 184, x0 + 46, 196), WOOD, radius=2, depth=0.3, line=1.3)
        for i in range(5):
            fx = x0 - 2 + i * 10
            p.shape("ellipse", (fx, 176, fx + 10, 186), hexc("#e0405a" if i % 2 else "#ffcf3a"), line=0.9)
    # door with warm light
    p.glow((172, 200), 60, hexc("#ffb850"), 0.5)
    door = union(p, [("rect", (148, 170, 196, 230)), ("ellipse", (148, 146, 196, 194))])
    paint(p, door, WOOD, depth=0.1, line=1.6)
    planks(p, door, (148, 146, 196, 230), WOOD, rng, width=12)
    outline(p, door, 1.6)
    p.shape("ellipse", (162, 158, 182, 176), WARM, light=1.4, line=1.2)
    p.shape("ellipse", (186, 196, 192, 202), GOLD, line=0.8)
    p.shape("rect", (140, 226, 204, 236), STONE_L, radius=3, depth=0.3, line=1.3)
    # hanging sign with a mug on a bracket out of the left corner
    p.shape("line", [(52, 110), (6, 110)], IRON, width=4, depth=0.3, line=1.2)
    p.shape("line", [(46, 110), (30, 124)], IRON, width=3, line=1.0)
    for x in (12, 42):
        line(p, [(x, 110), (x, 122)], IRON, 1.6)
    p.shape("rect", (4, 120, 52, 166), WOOD_L, radius=5, depth=0.18, line=1.6)
    p.shape("rect", (14, 134, 36, 160), GOLD, radius=3, light=1.35, depth=0.2, line=1.3)
    p.shape("ellipse", (32, 138, 46, 154), (0, 0, 0, 0), shadow=0, light=0, line=2.4, ink=INK)
    m = union(p, [("ellipse", (11, 126, 23, 138)), ("ellipse", (19, 124, 31, 136)), ("ellipse", (27, 127, 39, 139))])
    paint(p, m, WHITE, shadow=0.85, light=0, depth=0.2, line=1.2)
    for x in (20, 30):
        line(p, [(x, 140), (x, 156)], shade(GOLD, 0.75), 2)
    # barrels and a bench
    for x0 in (206, 226):
        p.shape("rect", (x0, 200, x0 + 22, 232), WOOD, radius=6, depth=0.15, line=1.3)
        line(p, [(x0 + 1, 208), (x0 + 21, 208)], IRON, 2.5)
        line(p, [(x0 + 1, 224), (x0 + 21, 224)], IRON, 2.5)
    p.shape("rect", (70, 212, 130, 220), WOOD_L, radius=2, depth=0.3, line=1.2)
    for x in (76, 120):
        p.shape("rect", (x, 218, x + 6, 232), WOOD, radius=1, line=1.1)
    lantern(p, 134, 144, 0.6)
    for x, s in ((40, 0.8), (304, 0.7), (212, 0.6)):
        tuft(p, x, 238, s)
    return p.finish(outline=2, ground_shadow=(10, 222, 316, 240))


# ------------------------------------------------------------------ NPC busts (256 x 256, facing front-left)

def _eye(p, x, y, r=7, lid=None, lid_color=SKIN):
    p.shape("ellipse", (x - r, y - r * 1.2, x + r, y + r * 1.2), DARK, **NOLINE)
    p.flat("ellipse", (x - r * 0.55, y - r * 0.8, x - r * 0.05, y - r * 0.2), WHITE)
    if lid:
        p.shape("chord", (x - r - 2, y - r * 1.2 - 3, x + r + 2, y + r * 1.2 + 3 - (1 - lid) * r * 2.4),
                lid_color, start=180, end=360, shadow=0, light=0, line=0)
        line(p, [(x - r - 2, y - r * 1.2 + lid * r * 2.4 - 3), (x + r + 2, y - r * 1.2 + lid * r * 2.4 - 3)], DARK, 2.4)


def npc_smith():
    p = TPainter(256, 256)
    skin = hexc("#e2a47a")
    grey = hexc("#c4c0bc")
    shirt = hexc("#8a3a2a")
    apron = hexc("#7a4a2a")
    # hammer head behind the left shoulder
    p.shape("poly", [(10, 118), (54, 96), (70, 128), (26, 150)], hexc("#5c616b"), depth=0.25, light=1.3, line=1.8)
    p.shape("poly", [(10, 118), (20, 113), (36, 145), (26, 150)], hexc("#8e96a2"), shadow=0, light=0, line=1.2)
    # torso
    p.shape("ellipse", (14, 170, 242, 360), shirt, depth=0.08, line=2)
    p.shape("rect", (98, 140, 158, 190), skin, radius=10, depth=0.2)
    ap = p.shape("poly", [(62, 196), (194, 196), (212, 256), (44, 256)], apron, depth=0.08, line=1.8)
    line(p, [(66, 200), (190, 200)], shade(apron, 1.25), 2)
    line(p, [(72, 198), (96, 168)], apron, 7, line=1.4)
    line(p, [(184, 198), (160, 168)], apron, 7, line=1.4)
    p.shape("rect", (110, 226, 146, 250), shade(apron, 0.8), radius=3, depth=0.2, line=1.3)
    for x, y in ((80, 222), (170, 236)):
        p.flat("ellipse", (x - 6, y - 4, x + 6, y + 4), hexc("#2a1a18", 120))
    # head (bald), ear on the right
    p.shape("ellipse", (176, 84, 202, 122), skin, depth=0.2)
    p.shape("ellipse", (182, 92, 196, 114), shade(skin, 0.8), **NOLINE)
    p.shape("ellipse", (70, 30, 190, 154), skin, depth=0.12)
    p.flat("ellipse", (92, 40, 128, 62), hexc("#ffffff", 150))
    p.flat("ellipse", (132, 44, 144, 52), hexc("#ffffff", 110))
    p.flat("ellipse", (150, 70, 160, 78), hexc("#2a1a18", 70))
    # eyes, bushy brows
    _eye(p, 104, 99, 7)
    _eye(p, 141, 99, 7)
    brows = []
    for cx, f in ((103, -1), (143, 1)):
        brows += [("ellipse", (cx + f * 4 - 9, 80, cx + f * 4 + 9, 94)), ("ellipse", (cx - 9, 76, cx + 9, 90)),
                  ("ellipse", (cx - f * 6 - 8, 78, cx - f * 6 + 8, 90)), ("ellipse", (cx + f * 12 - 7, 84, cx + f * 12 + 7, 96))]
    paint(p, union(p, brows), grey, depth=0.25, line=1.3)
    # beard
    beard = union(p, [("ellipse", (66, 104, 190, 220)), ("ellipse", (58, 88, 100, 180)), ("ellipse", (156, 88, 192, 170)),
                      ("poly", [(84, 196), (170, 196), (128, 244)])])
    edge = _catmull([(54, 92), (74, 96), (90, 110), (106, 118), (128, 114), (150, 118), (166, 110), (182, 96),
                     (200, 92)], 6)
    beard = ImageChops.subtract(beard, p._mask("poly", [(54, 20), (200, 20)] + edge[::-1]))
    paint(p, beard, grey, depth=0.1, line=1.8)
    for pts in ([(100, 150), (96, 180), (104, 206)], [(128, 160), (128, 200), (126, 228)], [(154, 150), (158, 180),
                                                                                               (150, 204)]):
        line(p, _catmull(pts), shade(grey, 0.72), 2.2)
    # mustache and nose
    m = union(p, [("ellipse", (86, 120, 124, 142)), ("ellipse", (118, 120, 158, 142))])
    paint(p, m, shade(grey, 1.12), depth=0.22, line=1.4)
    p.shape("ellipse", (106, 98, 134, 126), shade(skin, 0.95), depth=0.25, line=1.5)
    p.flat("ellipse", (112, 104, 120, 112), hexc("#ffffff", 120))
    p.flat("ellipse", (84, 108, 98, 118), hexc("#ff6a5a", 90))
    p.flat("ellipse", (146, 108, 160, 118), hexc("#ff6a5a", 90))
    # hand on the hammer handle (resting on the shoulder)
    p.shape("line", [(96, 250), (40, 126)], hexc("#6b4428"), width=11, depth=0.3, line=1.6)
    p.shape("ellipse", (64, 196, 104, 234), skin, depth=0.18)
    for y in (204, 214, 224):
        line(p, [(70, y), (84, y - 2)], shade(skin, 0.6), 1.8)
    # other hand cupped at the ear ("Eh? Speak up!")
    arm = union(p, [("poly", [(210, 256), (252, 256), (234, 136), (204, 140)]), ("ellipse", (204, 168, 246, 238))])
    paint(p, arm, skin, depth=0.14)
    for x, y in ((218, 186), (228, 196), (220, 206), (232, 212)):
        line(p, [(x, y), (x + 4, y - 5)], shade(skin, 0.55), 1.4)
    p.shape("poly", [(206, 232), (252, 228), (254, 252), (206, 254)], shade(shirt, 1.12), depth=0.25, line=1.4)
    p.shape("ellipse", (192, 76, 232, 144), skin, depth=0.18)
    for y in (88, 100, 112):
        line(p, [(200, y), (214, y - 2)], shade(skin, 0.6), 1.8)
    for (x0, y0), (x1, y1) in (((234, 74), (243, 68)), ((236, 92), (246, 92)), ((234, 110), (243, 116))):
        line(p, [(x0, y0), (x1, y1)], hexc("#fff0c0"), 2.4, line=1.0)
    return p.finish(outline=2)


def npc_merchant():
    p = TPainter(256, 256)
    skin = hexc("#f4c8a0")
    hair = hexc("#8a3424")
    dress = hexc("#6a2f96")
    gold = hexc("#f0c24a")
    # hair mass behind
    hm = union(p, [("ellipse", (58, 60, 200, 200)), ("ellipse", (46, 120, 100, 226)), ("ellipse", (158, 118, 214, 222)),
                   ("ellipse", (40, 170, 90, 236)), ("ellipse", (170, 170, 220, 238))])
    paint(p, hm, hair, depth=0.1, line=1.8)
    # shoulders, dress and neckline
    p.shape("ellipse", (22, 186, 234, 370), dress, depth=0.08, line=2)
    p.shape("rect", (108, 150, 150, 206), skin, radius=10, depth=0.2)
    p.shape("poly", [(92, 196), (166, 196), (129, 242)], skin, depth=0.15, line=1.4)
    line(p, [(88, 194), (129, 244), (170, 194)], gold, 5, line=1.2)
    line(p, _catmull([(104, 202), (129, 222), (154, 202)]), gold, 2.4)
    p.shape("poly", [(129, 218), (136, 226), (129, 236), (122, 226)], hexc("#3ad0a0"), light=1.5, line=1.1)
    # face
    p.shape("ellipse", (82, 78, 178, 178), skin, depth=0.1)
    p.flat("ellipse", (90, 136, 108, 148), hexc("#ff7a8a", 100))
    p.flat("ellipse", (146, 136, 164, 148), hexc("#ff7a8a", 100))
    # sly half-lidded eyes with lashes and eyeshadow
    for x in (108, 146):
        _eye(p, x, 124, 7, lid=0.45, lid_color=hexc("#b07ad0"))
        line(p, [(x + 7, 118), (x + 12, 114)], DARK, 2)
    line(p, _catmull([(96, 108), (106, 104), (118, 108)]), hair, 3)
    line(p, _catmull([(136, 104), (148, 98), (160, 104)]), hair, 3)
    # nose and smirk
    line(p, [(126, 128), (122, 144), (128, 146)], shade(skin, 0.7), 2.2)
    p.shape("poly", [(112, 158), (130, 162), (148, 152), (144, 160), (130, 168), (114, 162)], hexc("#c8404a"),
            depth=0.3, line=1.3)
    p.flat("ellipse", (154, 150, 158, 154), DARK)
    # earrings
    for x in (82, 176):
        ring = ImageChops.subtract(p._mask("ellipse", (x - 10, 140, x + 10, 168)),
                                   p._mask("ellipse", (x - 6, 144, x + 6, 164)))
        paint(p, ring, gold, depth=0.3, line=1.1)
        p.shape("ellipse", (x - 4, 134, x + 4, 142), gold, line=1.0)
    # big purple hat with feathers
    feathers = [([(152, 66), (176, 20), (206, 4), (220, 12), (196, 40), (168, 72)], hexc("#ff7ab0")),
                ([(158, 70), (200, 40), (238, 36), (240, 48), (206, 58), (170, 76)], hexc("#ffcf4a")),
                ([(146, 64), (156, 26), (176, 8), (182, 18), (168, 44), (158, 70)], hexc("#5ad0e0"))]
    for pts, col in feathers:
        p.shape("poly", _catmull(pts, 4), col, depth=0.2, light=1.25, line=1.4)
        line(p, _catmull([pts[0], pts[2]], 4), shade(col, 0.7), 1.6)
    p.shape("ellipse", (14, 64, 242, 112), PURPLE, depth=0.1, line=2)
    p.shape("chord", (66, 14, 188, 118), shade(PURPLE, 0.9), start=180, end=360, depth=0.12, line=2)
    p.shape("rect", (66, 60, 188, 76), gold, radius=3, depth=0.25, line=1.4)
    p.shape("ellipse", (144, 56, 162, 80), hexc("#3ad0a0"), light=1.6, line=1.2)
    # hand raising a potion
    p.glow((56, 150), 50, hexc("#6aff9a"), 0.6)
    p.shape("line", [(78, 256), (58, 196)], dress, width=30, depth=0.15, line=1.8)
    icons._potion(p, 56, 158, 1.5, hexc("#3ad07a"))
    p.shape("ellipse", (38, 172, 76, 204), skin, depth=0.2)
    line(p, [(46, 182), (70, 180)], shade(skin, 0.65), 1.8)
    line(p, [(46, 192), (70, 190)], shade(skin, 0.65), 1.8)
    for x, y, r in ((24, 124, 6), (90, 118, 4), (30, 184, 4)):
        p.shape("poly", icons._star(x, y, r, r * 0.35, 4), hexc("#fff6b0"), line=0.8, depth=0.2)
    return p.finish(outline=2)


def npc_keeper():
    p = TPainter(256, 256)
    skin = hexc("#e8b48a")
    cloak = hexc("#7a6a58")
    cap = hexc("#6a8a6a")
    white = hexc("#e6e2dc")
    # broom over the right shoulder, bristles up
    p.shape("line", [(150, 256), (220, 60)], WOOD_L, width=8, depth=0.3, line=1.4)
    p.shape("poly", [(206, 68), (224, 74), (248, 16), (236, 8), (214, 14), (202, 38)], hexc("#d8b860"), depth=0.2,
            line=1.6)
    line(p, [(203, 64), (226, 72)], hexc("#a0503a"), 4, line=1.0)
    for a, b in (((212, 58), (220, 18)), ((218, 62), (232, 14)), ((224, 66), (242, 18))):
        line(p, [a, b], hexc("#b0903a"), 1.6)
    # patched cloak
    body = p.shape("ellipse", (18, 176, 238, 380), cloak, depth=0.08, line=2)
    for box, col in (((50, 212, 82, 240), "#8a5a8a"), ((166, 222, 196, 250), "#5a7a8a"), ((120, 238, 146, 256),
                                                                                           "#a07a3a")):
        p.shape("rect", box, hexc(col), radius=2, depth=0.2, line=1.2, clip=body)
        x0, y0, x1, y1 = box
        for i in range(4):
            t = (i + 0.5) / 4
            line(p, [(x0 + (x1 - x0) * t, y0 - 2), (x0 + (x1 - x0) * t, y0 + 3)], hexc("#e8dcc0"), 1.2)
    hood = union(p, [("ellipse", (58, 150, 198, 206))])
    paint(p, hood, shade(cloak, 0.85), depth=0.18, line=1.6)
    p.shape("rect", (106, 140, 150, 186), skin, radius=10, depth=0.2)
    # face
    p.shape("ellipse", (178, 100, 198, 130), skin, depth=0.2)
    p.shape("ellipse", (74, 56, 186, 172), skin, depth=0.1)
    for x in (104, 142):
        _eye(p, x, 112, 6, lid=0.62)
        line(p, _catmull([(x - 8, 126), (x, 130), (x + 8, 126)]), shade(skin, 0.7), 1.6)
    line(p, [(92, 96), (114, 100)], white, 4, line=1.0)
    line(p, [(132, 100), (154, 96)], white, 4, line=1.0)
    # stubble
    rng = random.Random(2)
    for _ in range(40):
        x, y = rng.uniform(92, 164), rng.uniform(136, 164)
        if ((x - 128) / 40) ** 2 + ((y - 118) / 52) ** 2 < 1:
            p.flat("ellipse", (x - 0.8, y - 0.8, x + 0.8, y + 0.8), hexc("#8a7a70", 170))
    # droopy mustache, yawn, big red nose
    p.shape("ellipse", (118, 146, 132, 160), hexc("#5a2030"), depth=0.25, line=1.3)
    m = union(p, [("poly", [(124, 132), (98, 140), (86, 164), (96, 160), (108, 148), (124, 144)]),
                  ("poly", [(124, 132), (150, 140), (160, 166), (150, 160), (140, 148), (124, 144)])])
    paint(p, m, white, depth=0.25, line=1.3)
    p.shape("ellipse", (108, 112, 138, 140), hexc("#e0786a"), light=1.3, depth=0.25, line=1.4)
    p.flat("ellipse", (114, 118, 122, 124), hexc("#ffffff", 150))
    # floppy nightcap with a pom-pom
    capm = union(p, [("chord", (68, 30, 190, 120), {"start": 180, "end": 360}),
                     ("poly", [(96, 42), (168, 36), (210, 60), (226, 108), (208, 104), (190, 72)])])
    paint(p, capm, cap, depth=0.12, line=1.8)
    p.shape("rect", (64, 66, 192, 84), shade(cap, 1.25), radius=8, depth=0.3, line=1.5)
    p.shape("ellipse", (208, 98, 234, 124), white, depth=0.25, line=1.4)
    # Zzz
    for x, y, s in ((36, 44, 1.0), (54, 24, 0.7)):
        line(p, [(x, y), (x + 14 * s, y), (x, y + 14 * s), (x + 14 * s, y + 14 * s)], hexc("#d8e8ff"), 3.2 * s,
             line=1.0)
    # lantern in the left hand
    p.shape("line", [(70, 256), (58, 206)], cloak, width=30, depth=0.15, line=1.8)
    p.shape("ellipse", (44, 190, 76, 218), skin, depth=0.2)
    line(p, [(58, 196), (58, 172)], IRON, 2.4)
    lantern(p, 58, 160, 1.0)
    # dust puffs
    for x, y, r in ((30, 232, 10), (46, 246, 8), (210, 228, 9), (224, 244, 7)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#c8b8a0", 170), shadow=0.85, light=1.1, depth=0.25,
                line=1.0, ink=hexc("#6a5a4a", 150))
    return p.finish(outline=2)


TOWN = {
    "background": background,
    "gate": gate,
    "smith": smith,
    "merchant": merchant,
    "class_master": class_master,
    "inn": inn,
    "npc_smith": npc_smith,
    "npc_merchant": npc_merchant,
    "npc_keeper": npc_keeper,
}

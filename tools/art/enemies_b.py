"""Enemy sprites for the last two dungeons, redrawn at twice the old resolution.

    python3 tools/art/enemies_b.py                 # all ten
    python3 tools/art/enemies_b.py whelp ashwing   # just these

Yanık Kale (Burnt Keep): cultist, fire_imp, ember_hound, flame_knight (elite), ember_priestess (boss).
Ejder Yuvası (Dragon Lair): dragon_guard, whelp, ash_wraith, elder_drake (elite), ashwing (final boss).

Regular enemies and elites are 512 x 512, the two bosses 768 x 768; everything faces left, toward the
player. Each sprite is designed on the old grid (256, or 384 for bosses) and painted with the soft Painter
at 8x supersampling, so the result is the old sprite size doubled with every shading band, texture and ink
line scaled with it (the silhouette outline comes out about 5-6 px at 512). The supersampling factor is only
raised while one of these sprites is being painted, so importing this module next to the other generators
changes nothing for them.
"""
import functools
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

import painter as _pm  # noqa: E402
from characters import (DARK, NOLINE, WHITE, along, chain, curve, ember, flame, scale_rows,  # noqa: E402
                        taper, teeth)
from painter import Painter, hexc, light_tone, mix, shade  # noqa: E402

UP = 2      # output pixels per design pixel
HSS = 8     # supersampling while painting these sprites (canvas pixels per design pixel)
SIZE = 256  # design grid of a regular enemy or elite (output 512)
BOSS = 384  # design grid of a boss (output 768)

LAVA = hexc("#ff7a1a")
LAVA_HOT = hexc("#ffd25a")
LAVA_CORE = hexc("#fff4c8")
CHAR = hexc("#1e1014")
EMBER_RIM = hexc("#ff8a3a")
GOLD = hexc("#f0b848")
GOLD_D = hexc("#a8702a")


# ------------------------------------------------------------------ canvas

def sprite(fn):
    """Runs a sprite function with the painter's supersampling raised to HSS (and puts it back after)."""
    @functools.wraps(fn)
    def run():
        old = _pm.SS
        _pm.SS = HSS
        try:
            return fn()
        finally:
            _pm.SS = old
    return run


def canvas(size, fit=None):
    """A soft Painter of the design size. fit=(k, dx, dy) returns an Xf view instead that scales the whole
    drawing by k about the bottom centre and moves it by (dx, dy), to keep wings, flames and tails inside."""
    p = Painter(size, size, soft=True)
    if fit:
        k, dx, dy = fit
        return Xf.about(p, (size / 2, size), k, dx, dy)
    return p


def done(p, outline=2.8, ground=None, fade=None):
    """Finishes at UP x the design size, with the house two-layer ground shadow (scaled up to match).
    fade=(y0, y1, a1) fades the sprite out from full opacity at y0 to a1 at y1 (a ghost dissolving into smoke)."""
    p, mp, _k = _base(p)
    p.w, p.h = p.w * UP, p.h * UP
    out = p.finish(outline=outline)
    if fade:
        y0, y1, a1 = fade
        y0, y1 = mp(0, y0)[1], mp(0, y1)[1]
        col = Image.new("L", (1, out.size[1]))
        col.putdata([int(255 * (1 - (1 - a1) * max(0.0, min(1.0, (y / UP - y0) / (y1 - y0)))))
                     for y in range(out.size[1])])
        out.putalpha(ImageChops.multiply(out.getchannel("A"), col.resize(out.size)))
    if ground:
        x0, y0, x1, y1 = [v * UP for v in mp(*ground[:2]) + mp(*ground[2:])]
        base = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(base).ellipse((x0, y0, x1, y1), fill=(12, 6, 18, 74))
        base = base.filter(ImageFilter.GaussianBlur(5 * UP))
        core = Image.new("RGBA", out.size, (0, 0, 0, 0))
        cw, ch = (x1 - x0) * 0.2, (y1 - y0) * 0.22
        ImageDraw.Draw(core).ellipse((x0 + cw, y0 + ch, x1 - cw, y1 - ch), fill=(12, 6, 18, 116))
        base = Image.alpha_composite(base, core.filter(ImageFilter.GaussianBlur(3 * UP)))
        out = Image.alpha_composite(base, out)
    return out


class Xf:
    """Stands in for a Painter but maps coordinates through (x, y) -> (ox + x * k, oy + y * k), so a part (a
    head, a whole creature) can be moved or scaled without rewriting its numbers. Ink weights stay as given."""

    def __init__(self, p, ox=0.0, oy=0.0, k=1.0):
        self.p, self.ox, self.oy, self.k = p, ox, oy, k

    @classmethod
    def about(cls, p, pivot, k=1.0, dx=0.0, dy=0.0):
        """Scale by k about `pivot`, then move by (dx, dy)."""
        return cls(p, pivot[0] * (1 - k) + dx, pivot[1] * (1 - k) + dy, k)

    def __getattr__(self, name):
        return getattr(self.p, name)

    def pt(self, x, y):
        return (self.ox + x * self.k, self.oy + y * self.k)

    def _pts(self, pts):
        if isinstance(pts[0], (tuple, list)):
            return [self.pt(x, y) for x, y in pts]
        out = []
        for i in range(0, len(pts), 2):
            out += list(self.pt(pts[i], pts[i + 1]))
        return out

    def _kw(self, kw):
        kw = dict(kw)
        for key in ("width", "radius"):
            if key in kw:
                kw[key] = kw[key] * self.k
        return kw

    def _mask(self, kind, pts, **kw):
        return self.p._mask(kind, self._pts(pts), **self._kw(kw))

    def shape(self, kind, pts, color, **kw):
        return self.p.shape(kind, self._pts(pts), color, **self._kw(kw))

    def flat(self, kind, pts, color, **kw):
        return self.p.flat(kind, self._pts(pts), color, **self._kw(kw))

    def union(self, items):
        return self.p.union([(it[0], self._pts(it[1])) + ((self._kw(it[2]),) if len(it) > 2 else ()) for it in items])

    def stroke(self, pts, color, width, soft=0.0):
        return self.p.stroke(self._pts(pts), color, max(0.6, width * self.k), soft)

    def glow(self, center, radius, color, strength=0.8):
        return self.p.glow(self.pt(*center), radius * self.k, color, strength)


def _base(p):
    """(painter, mapping) for a Painter or an Xf view of one."""
    if isinstance(p, Xf):
        b, mp, k = _base(p.p)
        return b, (lambda x, y: mp(*p.pt(x, y))), k * p.k
    return p, (lambda x, y: (x, y)), 1.0


# ------------------------------------------------------------------ geometry

def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def taperw(pts, widths, steps=8):
    """Outline polygon of a smooth curve through pts whose width follows `widths` (one per point), for limbs,
    necks and tails with real bulges and thin joints."""
    c = curve(pts, steps) if len(pts) > 2 else [lerp(pts[0], pts[1], i / steps) for i in range(steps + 1)]
    n = len(c)
    left, right = [], []
    segs = len(pts) - 1
    for i, (x, y) in enumerate(c):
        a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        u = i / max(1, n - 1) * segs
        j = min(segs - 1, int(u))
        f = u - j
        f = f * f * (3 - 2 * f)
        w = (widths[j] + (widths[j + 1] - widths[j]) * f) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def rot_pts(pts, cx, cy, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def ellipse_pts(cx, cy, rx, ry, n=36, rot=0.0):
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return rot_pts(pts, cx, cy, rot) if rot else pts


# ------------------------------------------------------------------ mask helpers

def _crop(p, m, pad=0):
    return p._crop(m, int(pad * _pm.SS) + 2)


def _scale(mask, amount):
    if amount >= 1:
        return mask
    k = max(0, int(255 * amount))
    return mask.point(lambda v: v * k // 255)


def fill_clip(p, m, color, clip=None, blur=0.0, solid=False):
    """Composites `color` through mask m (optionally blurred and kept inside `clip`)."""
    c, box = _crop(p, m, blur * 3 + 1)
    if c is None:
        return
    if blur:
        c = c.filter(ImageFilter.GaussianBlur(blur * _pm.SS))
    if clip is not None:
        c = ImageChops.multiply(c, clip.crop(box))
    p._fill(c, color, box[:2], solid=solid)


def soft_line(p, pts, color, width, blur=1.0, clip=None):
    """A soft painted line (fold shadows, sheens, veins), optionally kept inside `clip`."""
    m = p._mask("line", curve(pts, 5) if len(pts) > 2 else pts, width=width)
    fill_clip(p, m, color, clip, blur)


def tline(p, pts, w0, w1, color, clip=None, blur=0.0):
    """Tapered flat stroke (no ink): cracks, veins, hair strands, glints."""
    m = p._mask("poly", taper(pts, w0, w1, 6))
    fill_clip(p, m, color, clip, blur)
    return m


def rim(p, m, color, d=(1.0, 0.4), width=2.6, strength=0.85, blur=0.9, inset=1.4):
    """Directional rim/bounce light along the edge of mask m facing direction d (e.g. the warm glow of the
    fire behind, on the right and underside)."""
    c, box = _crop(p, m, width * 2 + 4)
    if c is None:
        return
    s = _pm.SS
    inner = _pm._erode(c, int(inset * s)) if inset else c
    sh = _pm._shift(inner, int(-d[0] * width * s), int(-d[1] * width * s))
    band = ImageChops.multiply(inner, ImageChops.invert(sh))
    band = ImageChops.multiply(_pm._blur(band, blur * s), inner)
    p._fill(_scale(band, strength), color, box[:2], solid=False)


def vgrad(p, m, color, y0, y1, a0=0.0, a1=1.0, x_axis=False):
    """Gradient wash of `color` inside m, alpha a0 at y0 to a1 at y1 (or along x)."""
    c, box = _crop(p, m, 1)
    if c is None:
        return
    _, mp, _k = _base(p)
    if x_axis:
        y0, y1 = mp(y0, 0)[0], mp(y1, 0)[0]
    else:
        y0, y1 = mp(0, y0)[1], mp(0, y1)[1]
    s = _pm.SS
    w, h = c.size
    g = Image.new("L", (w, h))
    px = list(range(w)) if x_axis else list(range(h))
    vals = []
    for i in px:
        v = ((box[0] + i) / s if x_axis else (box[1] + i) / s)
        t = 0 if y1 == y0 else (v - y0) / (y1 - y0)
        t = max(0.0, min(1.0, t))
        vals.append(int(255 * (a0 + (a1 - a0) * t)))
    if x_axis:
        row = Image.new("L", (w, 1))
        row.putdata(vals)
        g = row.resize((w, h))
    else:
        col = Image.new("L", (1, h))
        col.putdata(vals)
        g = col.resize((w, h))
    p._fill(ImageChops.multiply(g, c), color, box[:2], solid=False)


def spot(p, m, color, center, radius, strength=1.0, clip=True):
    """Soft radial light (or shadow) painted inside m only."""
    cx, cy = center
    g = p._mask("ellipse", (cx - radius, cy - radius, cx + radius, cy + radius))
    c, box = _crop(p, g, radius * 0.5)
    c = c.filter(ImageFilter.GaussianBlur(radius * 0.35 * _pm.SS))
    if clip:
        c = ImageChops.multiply(c, m.crop(box))
    p._fill(_scale(c, strength), color, box[:2], solid=False)


def sub(a, b):
    return ImageChops.subtract(a, b)


def inter(a, b):
    return ImageChops.multiply(a, b)


# ------------------------------------------------------------------ fx

def lava_vein(p, pts, width=2.4, clip=None, glow=0.4, char=True, taper_to=0.35):
    """Glowing crack of molten light: a charred rim, an orange body, a white-hot core, tapered at the end."""
    c = curve(pts, 4) if len(pts) > 2 else pts
    if glow:
        for x, y in along(c, 6):
            p.glow((x, y), width * 3.4, LAVA, glow)
    if char:
        tline(p, c, width * 2.0, width * 0.9, CHAR[:3] + (150,), clip, blur=0.5)
    tline(p, c, width, width * taper_to, hexc("#ff8a24"), clip)
    tline(p, c, width * 0.45, width * taper_to * 0.4, LAVA_CORE, clip)


def smoke_puff(p, x, y, r, color=hexc("#5a5058"), alpha=190, ink=True):
    """Cartoon smoke puff: three overlapping soft balls with a lighter top and a thin tinted ink line."""
    m = p.union([("ellipse", (x - r, y - r * 0.82, x + r, y + r * 0.82)),
                 ("ellipse", (x + r * 0.2, y - r * 1.25, x + r * 1.35, y - r * 0.1)),
                 ("ellipse", (x - r * 1.2, y - r * 0.9, x - r * 0.05, y + r * 0.2))])
    col = color[:3] + (alpha,)
    p.paint_mask(m, col, shadow=0.8, light=1.25, depth=0.35, line=0.8 if ink else 0,
                 ink=shade(color, 0.55)[:3] + (int(alpha * 0.6),), rim=0, ao=0)
    return m


def haze(p, center, rx, ry, color, strength=0.3):
    """Big smooth background glow (a blurred ellipse painted at low resolution and scaled up, so it has none
    of the rings a stepped radial glow shows at this size)."""
    s = _pm.SS
    W, H = p.img.size
    lw, lh = W // s, H // s
    m = Image.new("L", (lw, lh), 0)
    _, mp, kk = _base(p)
    cx, cy = mp(*center)
    rx, ry = rx * kk, ry * kk
    ImageDraw.Draw(m).ellipse((cx - rx * 0.6, cy - ry * 0.6, cx + rx * 0.6, cy + ry * 0.6), fill=int(255 * strength))
    m = m.filter(ImageFilter.GaussianBlur(max(rx, ry) * 0.38))
    win = Image.new("L", (lw, lh), 0)
    ImageDraw.Draw(win).rectangle((lw * 0.09, lh * 0.09, lw * 0.91, lh * 0.91), fill=255)
    win = win.filter(ImageFilter.GaussianBlur(lw * 0.05))
    m = ImageChops.multiply(m, win).resize((W, H), Image.BILINEAR)
    p._fill(m, color, solid=False)


def wisp(p, pts, r, color, strength=0.5):
    """Soft rising smoke: overlapping radial glows along a path, shrinking and fading toward the end."""
    c = along(curve(pts, 6), max(2.0, r * 0.35))
    n = len(c)
    for i, (x, y) in enumerate(c):
        t = i / max(1, n - 1)
        p.glow((x, y), r * (1 - t * 0.45), color, strength * (1 - t * 0.7) * 0.5)


def ash_flake(p, x, y, r, color=hexc("#a89ca2")):
    p.shape("poly", [(x - r, y - r * 0.4), (x + r * 0.2, y - r * 0.8), (x + r, y + r * 0.2), (x - r * 0.1, y + r * 0.7)],
            color, shadow=0.75, light=1.25, depth=0.3, line=0.7, rim=0, ao=0)


def embers(p, spots):
    for x, y, r in spots:
        ember(p, x, y, r)


def claw(p, x, y, length, angle, color=hexc("#efe4cc"), width=None, line=1.0):
    """Curved pointed claw growing from (x, y) along `angle` (degrees), hooking downward."""
    w = width or length * 0.42
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    hook = 0.28 * length
    pts = [(x + nx * w / 2, y + ny * w / 2),
           (x + ux * length * 0.55 + nx * w * 0.36 + 0 * hook, y + uy * length * 0.55 + ny * w * 0.36 + hook * 0.35),
           (x + ux * length, y + uy * length + hook),
           (x + ux * length * 0.5 - nx * w * 0.12, y + uy * length * 0.5 - ny * w * 0.12 + hook * 0.2),
           (x - nx * w / 2, y - ny * w / 2)]
    p.shape("poly", curve(pts, 4), color, depth=0.3, light=1.35, line=line, rim=0, ao=0.25, spec=0.5)


def horn(p, pts, w0, w1, color, rings=0, ring_c=None, spec=0.7, tex="bone", line=1.6, glow_tip=None, light=1.35):
    """Tapered horn with optional growth rings."""
    m = p.shape("poly", taper(pts, w0, w1, 8), color, depth=0.22, light=light, spec=spec, tex=tex, tex_amt=0.6,
                line=line, rim=0.15)
    if rings:
        c = curve(pts, 8)
        n = len(c)
        rc = ring_c or shade(color, 0.7)
        for k in range(1, rings + 1):
            i = int(n * k / (rings + 1.5))
            (x0, y0), (x1, y1) = c[max(0, i - 1)], c[min(n - 1, i + 1)]
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1
            nx, ny = -dy / ln, dx / ln
            w = (w0 + (w1 - w0) * i / (n - 1)) / 2
            x, y = c[i]
            soft_line(p, [(x + nx * w, y + ny * w), (x + dx / ln * w * 0.3, y + dy / ln * w * 0.3),
                          (x - nx * w, y - ny * w)], rc, max(0.8, w * 0.22), 0.25, m)
    if glow_tip:
        p.glow(pts[-1], w0 * 0.9, glow_tip, 0.7)
    return m


def angry_eye(p, cx, cy, rx, ry, iris, inner=1, slant=0.55, pupil="slit", sclera=hexc("#fff6e0"), look=-0.35,
              glow=None, brow=None, brow_w=3.0, line=1.2):
    """Menacing cartoon eye: the top is cut by a lid slanting down toward the face's centre (`inner` 1 = the
    inner corner is on the right, -1 = left), a big glossy iris with a slit or round pupil, catchlights,
    and a heavy brow stroke along the lid."""
    ex = ellipse_pts(cx, cy, rx, ry, 40)
    # lid line: higher at the outer corner, lower at the inner corner
    hi, lo = cy - ry * 1.05, cy - ry * (1.05 - slant * 1.4)
    xa, xb = cx - rx * 1.4, cx + rx * 1.4
    ya, yb = (hi, lo) if inner > 0 else (lo, hi)
    cut = p._mask("poly", [(xa, ya), (xb, yb), (xb, cy + ry * 2), (xa, cy + ry * 2)])
    em = inter(p._mask("poly", ex), cut)
    if glow:
        p.glow((cx, cy), max(rx, ry) * 2.6, glow, 0.7)
    p.paint_mask(em, sclera, shadow=0.8, light=0, depth=0.25, line=line, rim=0, ao=0)
    ix, iy = cx + look * rx * 0.55, cy + ry * 0.08
    ir = min(rx, ry) * 0.78
    p.shape("ellipse", (ix - ir, iy - ir * 1.08, ix + ir, iy + ir * 1.08), iris, shadow=0.55, light=1.5, depth=0.3,
            line=0.8, ink=shade(iris, 0.4), rim=0, ao=0, clip=em)
    p.shape("chord", (ix - ir * 0.8, iy - ir * 0.2, ix + ir * 0.8, iy + ir * 0.95), shade(iris, 1.4), start=0,
            end=180, clip=em, **NOLINE)
    if pupil == "slit":
        pm = p._mask("poly", curve([(ix, iy - ir * 0.95), (ix + ir * 0.26, iy), (ix, iy + ir * 0.95),
                                    (ix - ir * 0.26, iy)], 4))
    else:
        pr = ir * 0.46
        pm = p._mask("ellipse", (ix - pr, iy - pr, ix + pr, iy + pr))
    fill_clip(p, pm, DARK, em)
    fill_clip(p, p._mask("ellipse", (ix - ir * 0.72, iy - ir * 0.7, ix - ir * 0.18, iy - ir * 0.2)), WHITE, em)
    fill_clip(p, p._mask("ellipse", (ix + ir * 0.22, iy + ir * 0.3, ix + ir * 0.5, iy + ir * 0.56)),
              hexc("#ffffff", 190), em)
    if brow is not None:
        ext = rx * 0.35
        bx0, bx1 = cx - rx - ext, cx + rx + ext
        t = (ext) / (2 * rx + 2 * ext)
        by0 = ya + (yb - ya) * (0.5 - (rx + ext) / (xb - xa))
        by1 = ya + (yb - ya) * (0.5 + (rx + ext) / (xb - xa))
        m = p._mask("poly", taper([(bx0, by0 - 0.6), ((bx0 + bx1) / 2, (by0 + by1) / 2 - brow_w * 0.25),
                                   (bx1, by1 - 0.6)], brow_w * (0.7 if inner > 0 else 1.2),
                                  brow_w * (1.2 if inner > 0 else 0.7), 6))
        p.paint_mask(m, brow, shadow=0.7, light=1.2, depth=0.3, line=0.9, rim=0, ao=0.3)
        del t
    return em


def ember_eye(p, cx, cy, r, color=hexc("#ffb02a"), slant=0.5, inner=1, core=LAVA_CORE, strength=0.9):
    """Burning eye in a dark face: a slanted almond of fire with a white-hot centre."""
    p.glow((cx, cy), r * 3.0, color, strength)
    pts = ellipse_pts(cx, cy, r * 1.25, r * 0.8, 32)
    hi, lo = cy - r * 0.8, cy - r * 0.8 + r * slant * 1.2
    xa, xb = cx - r * 2, cx + r * 2
    ya, yb = (hi, lo) if inner > 0 else (lo, hi)
    cut = p._mask("poly", [(xa, ya), (xb, yb), (xb, cy + r * 2), (xa, cy + r * 2)])
    em = inter(p._mask("poly", pts), cut)
    fill_clip(p, em, color)
    fill_clip(p, p._mask("ellipse", (cx - r * 0.75, cy - r * 0.3, cx + r * 0.75, cy + r * 0.62)), mix(color, core, 0.5),
              em, blur=0.3)
    fill_clip(p, p._mask("ellipse", (cx - r * 0.38, cy - r * 0.05, cx + r * 0.38, cy + r * 0.45)), core, em, blur=0.2)
    return em


def spark(p, x, y, r, color=hexc("#ff9a2a"), core=hexc("#fff0b0")):
    """Floating ember: a glow and a hot core, with no ink (so it never gets a dark ring)."""
    p.glow((x, y), r * 3.4, color, 0.75)
    fill_clip(p, p._mask("ellipse", (x - r, y - r, x + r, y + r)), core)


def sparks(p, spots):
    for x, y, r in spots:
        spark(p, x, y, r)


def leg(p, joints, widths, color, extra=(), line=1.6, depth=0.14, **opts):
    """A whole limb as one painted shape: a tapered curve through the joints (thick muscle, thin joints),
    merged with any extra primitives (a thigh or shoulder ellipse)."""
    m = p.union([("poly", taperw(joints, widths))] + list(extra))
    return p.paint_mask(m, color, depth=depth, line=line, **opts)


def paw(p, cx, cy, w, color, claw_c, toes=3, line=1.5, tex=None, tex_amt=0.5):
    """Round paw planted on the ground at (cx, cy) with toe bumps and hooked claws pointing left."""
    h = w * 0.42
    items = [("ellipse", (cx - w * 0.5, cy - h, cx + w * 0.5, cy + h * 0.25))]
    for i in range(toes):
        tx = cx - w * 0.5 + w * (i + 0.5) / toes - w * 0.08
        items.append(("ellipse", (tx - w * 0.2, cy - h * 0.55, tx + w * 0.2, cy + h * 0.3)))
    m = p.paint_mask(p.union(items), color, depth=0.3, line=line, tex=tex, tex_amt=tex_amt)
    for i in range(toes):
        tx = cx - w * 0.5 + w * (i + 0.5) / toes - w * 0.08
        soft_line(p, [(tx + w * 0.16, cy - h * 0.5), (tx + w * 0.2, cy + h * 0.2)], shade(color, 0.5)[:3] + (180,),
                  0.9, 0.2, m)
        claw(p, tx - w * 0.14, cy + h * 0.05, w * 0.26, 175, claw_c, line=0.9)
    return m


def tufts(p, arc, step, h, direction, color, glow_every=0, seed=1, tex=None, line=1.4):
    """Jagged spikes of fur or charred hide standing along `arc`, leaning along `direction`."""
    rng = random.Random(seed)
    dx, dy = direction
    pts = along(curve(arc, 8), step)
    for i, (x, y) in enumerate(pts):
        hh = h * rng.uniform(0.75, 1.1) * (0.7 + 0.3 * math.sin(math.pi * (i + 0.5) / len(pts)))
        w = step * 1.25
        tip = (x + dx * hh, y + dy * hh)
        nx, ny = -dy, dx
        base0 = (x - nx * w / 2 - dx * 3, y - ny * w / 2 - dy * 3)
        base1 = (x + nx * w / 2 - dx * 3, y + ny * w / 2 - dy * 3)
        mid = lerp(lerp(base0, base1, 0.5), tip, 0.55)
        bend = (mid[0] + nx * w * 0.18, mid[1] + ny * w * 0.18)
        shape = curve([base0, bend, tip], 4) + [tip] + curve([tip, lerp(lerp(base1, tip, 0.5), bend, 0.2), base1], 4)
        opts = dict(tex) if tex else {}
        p.shape("poly", shape, color, depth=0.3, light=1.3, line=line, rim=0, ao=0.25, **opts)
        if glow_every and i % glow_every == 0:
            p.glow(tip, 5.5, LAVA, 0.65)
            tline(p, [lerp(tip, lerp(base0, base1, 0.5), 0.35), tip], 2.6, 0.6, LAVA_HOT)


# ------------------------------------------------------------------ dungeon 4: Yanık Kale (Burnt Keep)

@sprite
def ember_hound():
    """Charcoal hellhound about to pounce: shoulders high and head low, a mane of smouldering spikes, deep
    chest with ribs glowing through the cracked hide, digitigrade legs, a snarling jaw full of molten light
    and a burning tail."""
    p = canvas(SIZE, fit=(0.93, 4, 0))
    coal = hexc("#554a53")
    far = hexc("#2f282f")
    mane = hexc("#2a2329")
    claw_c = hexc("#1c1618")
    tex = dict(tex="stone", tex_amt=0.55)
    haze(p, (128, 150), 128, 128, hexc("#ff5a1a"), 0.22)
    # ---- smoke curling off the mane
    wisp(p, [(150, 70), (160, 50), (176, 38), (170, 20), (184, 6)], 16, hexc("#7a6e76"), 0.55)
    wisp(p, [(184, 84), (196, 62), (210, 50), (206, 30)], 12, hexc("#7a6e76"), 0.45)
    # ---- burning tail
    tail = [(210, 108), (228, 98), (238, 80), (236, 60)]
    tm = p.shape("poly", taperw(tail, [22, 15, 11, 8]), coal, depth=0.25, line=1.5, **tex)
    lava_vein(p, [(222, 102), (232, 90), (235, 76)], 1.5, tm, glow=0.25)
    flame(p, 236, 72, 34, 78, lean=-0.12, strength=0.85)
    # ---- far legs
    ff = leg(p, [(128, 128), (128, 168), (124, 206), (116, 228)], [30, 20, 13, 13], far, **tex)
    lava_vein(p, [(129, 176), (126, 196), (124, 210)], 1.3, ff, glow=0.2)
    paw(p, 116, 231, 24, far, claw_c)
    fh = leg(p, [(176, 124), (176, 164), (190, 196), (184, 228)], [36, 22, 13, 13], far, **tex)
    lava_vein(p, [(178, 170), (186, 190)], 1.3, fh, glow=0.2)
    paw(p, 184, 231, 24, far, claw_c)
    # ---- mane: back layer of spikes
    mane_arc = [(70, 84), (92, 70), (120, 66), (148, 76), (170, 90)]
    for x, y, h, ln in ((96, 70, 34, 0.55), (122, 66, 40, 0.7), (146, 76, 34, 0.8), (166, 90, 26, 0.9)):
        flame(p, x, y, 18, h, lean=ln, strength=0.45)
    tufts(p, mane_arc, 11, 34, (0.62, -0.78), mane, glow_every=2, seed=3)
    # ---- torso: deep chest, tucked waist, strong haunch
    torso = p.union([("ellipse", (64, 76, 154, 182)),
                     ("poly", curve([(110, 74), (156, 84), (206, 96), (224, 120), (212, 156), (180, 146), (158, 150),
                                     (124, 180)], 6)),
                     ("ellipse", (164, 94, 228, 160))])
    p.paint_mask(torso, coal, depth=0.12, line=1.6, **tex)
    vgrad(p, torso, hexc("#9a4020"), 120, 186, 0.0, 0.38)
    rim(p, torso, EMBER_RIM, (0.3, 1.0), 2.6, 0.8)
    for i, (x0, y0) in enumerate(((112, 112), (124, 110), (136, 112), (148, 116))):
        lava_vein(p, [(x0, y0), (x0 + 7, y0 + 20), (x0 + 3, y0 + 40 - i * 6)], 2.1 - i * 0.2, torso, glow=0.3)
    # ---- near hind leg: thigh, hock, long foot
    thigh = leg(p, [(196, 130), (196, 168), (222, 198), (216, 228)], [56, 26, 15, 14], coal,
                extra=[("ellipse", (168, 100, 230, 172))], **tex)
    rim(p, thigh, EMBER_RIM, (0.8, 0.8), 2.4, 0.75)
    lava_vein(p, [(186, 116), (200, 134), (194, 152), (204, 166)], 2.0, thigh, glow=0.3)
    lava_vein(p, [(214, 196), (218, 214)], 1.4, thigh, glow=0.2)
    paw(p, 212, 232, 30, coal, claw_c)
    # ---- neck
    neck = p.paint_mask(p._mask("poly", curve([(66, 84), (104, 70), (122, 104), (108, 148), (76, 150), (52, 120)], 6)),
                        coal, depth=0.14, line=1.6, **tex)
    lava_vein(p, [(82, 96), (92, 112), (86, 132)], 1.6, neck, glow=0.25)
    # ---- near front leg braced forward
    fl = leg(p, [(108, 110), (104, 164), (86, 204), (72, 228)], [44, 24, 15, 15], coal,
             extra=[("ellipse", (84, 100, 132, 170))], **tex)
    rim(p, fl, EMBER_RIM, (0.9, 0.6), 2.2, 0.7)
    lava_vein(p, [(102, 116), (112, 134), (104, 154)], 2.0, fl, glow=0.3)
    lava_vein(p, [(94, 184), (84, 206)], 1.4, fl, glow=0.2)
    paw(p, 68, 232, 32, coal, claw_c)
    # ---- mane: front layer over the neck and shoulders
    tufts(p, [(80, 80), (100, 72), (122, 72), (140, 82)], 10, 24, (0.66, -0.75), coal, glow_every=2, seed=7, tex=tex)
    # ---- head: jaw dropped open over a molten throat, fangs, ears pinned back
    p.shape("poly", curve([(84, 82), (106, 66), (132, 58), (112, 86)], 4), far, depth=0.3, light=1.25, line=1.4)
    p.shape("poly", curve([(72, 122), (46, 138), (18, 150), (8, 146), (24, 134), (50, 122)], 5), far, depth=0.25,
            line=1.5, **tex)
    mouth = p._mask("poly", curve([(74, 114), (40, 124), (12, 138), (22, 144), (52, 136), (74, 128)], 5))
    p.glow((42, 132), 30, LAVA, 0.9)
    fill_clip(p, mouth, hexc("#ff7a1a"))
    fill_clip(p, p._mask("ellipse", (22, 124, 72, 138)), LAVA_HOT, mouth, blur=1.5)
    teeth(p, [(22, 143, 4.5, -7, 1), (34, 140, 4.5, -8, 1), (48, 136, 5, -10, 1)], hexc("#f4e8d0"), line=0.9)
    head = p.union([("ellipse", (38, 70, 104, 126)),
                    ("poly", curve([(58, 82), (30, 92), (6, 104), (0, 114), (8, 124), (44, 124), (72, 118)], 5))])
    p.paint_mask(head, coal, depth=0.12, line=1.6, **tex)
    rim(p, head, EMBER_RIM, (0.2, 1.0), 2.0, 0.75)
    teeth(p, [(14, 123, 4.5, 8, 1), (28, 123, 4.5, 9, 1), (44, 122, 5.5, 13, 1), (58, 120, 4, 7, 1)],
          hexc("#f4e8d0"), line=0.9)
    lava_vein(p, [(46, 140), (48, 150), (46, 160)], 1.8, None, glow=0.4, char=False)
    spark(p, 46, 162, 2.6)
    p.shape("ellipse", (-1, 103, 13, 113), hexc("#161014"), depth=0.3, line=1.0, gloss=0.8, rim=0)
    for i in range(3):
        soft_line(p, [(24 + i * 7, 96 + i * 1.5), (28 + i * 7, 104 + i), (26 + i * 7, 110)], hexc("#140c10", 170),
                  1.4, 0.3, head)
    lava_vein(p, [(62, 106), (78, 102), (94, 108)], 1.4, head, glow=0.2)
    ember_eye(p, 60, 94, 7.6, hexc("#ffc02a"), slant=0.6, inner=-1)
    p.shape("poly", curve([(42, 84), (62, 84), (84, 76), (82, 85), (62, 90), (44, 90)], 4), mane,
            depth=0.3, light=1.3, line=1.2, rim=0, ao=0.4)
    p.shape("poly", curve([(82, 80), (106, 66), (136, 58), (114, 84), (92, 92)], 4), coal, depth=0.3, light=1.3,
            line=1.5, **tex)
    p.shape("poly", curve([(92, 80), (112, 70), (126, 64), (110, 80)], 4), hexc("#c8401a"), **NOLINE)
    sparks(p, [(22, 60, 2.2), (132, 36, 2.0), (248, 130, 1.8), (10, 176, 1.8), (150, 214, 2.0), (100, 24, 1.6)])
    return done(p, 2.8, (34, 224, 240, 248))


@sprite
def cultist():
    """Hooded dragon cultist creeping forward: a peaked red hood over a face of shadow with burning eyes and
    a sly grin, a ragged black mantle, a dragon-eye pendant, a wavy ritual dagger raised in one bony hand
    and a blessing flame hovering over the other."""
    p = canvas(SIZE)
    black = hexc("#33222e")
    black_d = hexc("#241820")
    red = hexc("#b0302c")
    red_d = hexc("#7a1c20")
    gold = GOLD
    skin = hexc("#d6bcb4")
    eyec = hexc("#ffa02a")
    cloth = dict(tex="cloth", tex_amt=0.6)
    haze(p, (128, 110), 110, 110, hexc("#ff4a1a"), 0.2)
    # ---- back arm: wide sleeve reaching out, palm up under a hovering flame
    sl = p.shape("poly", curve([(158, 104), (184, 120), (206, 136), (214, 150), (206, 162), (184, 158), (164, 144),
                                (150, 124)], 5), black_d, depth=0.2, line=1.6, **cloth)
    rim(p, sl, EMBER_RIM, (0.6, 1.0), 2.2, 0.6)
    p.shape("poly", curve([(206, 140), (216, 150), (210, 162), (200, 158)], 4), red_d, depth=0.3, line=1.2, rim=0)
    hand = p.union([("ellipse", (200, 136, 222, 152)), ("poly", [(218, 140), (232, 136), (234, 142), (220, 148)])])
    p.paint_mask(hand, skin, depth=0.3, line=1.3, rim=0)
    for x in (206, 212, 218):
        claw(p, x, 137, 5, -100, hexc("#3a2a2e"), line=0.8)
    p.glow((214, 112), 34, hexc("#ffb040"), 0.6)
    flame(p, 214, 130, 22, 38, lean=0.1, strength=0.6)
    spark(p, 204, 104, 1.6)
    spark(p, 226, 116, 1.4)
    # ---- the robe: black outer robe flaring to a ragged hem, red inner panel, runes glowing on the hem
    hem = [(212, 234), (200, 226), (190, 238), (176, 228), (162, 240), (146, 230), (128, 240), (110, 230),
           (94, 240), (78, 228), (62, 238), (46, 230)]
    robe = p.shape("poly", curve([(96, 104), (162, 104), (178, 150), (200, 200)], 6) + hem +
                   curve([(58, 196), (78, 150), (96, 104)], 6), black, depth=0.12, line=1.6, **cloth)
    vgrad(p, robe, hexc("#6a1a1a"), 170, 240, 0.0, 0.45)
    rim(p, robe, EMBER_RIM, (1.0, 0.3), 2.4, 0.75)
    for pts in ([(86, 150), (72, 196), (62, 232)], [(170, 150), (186, 196), (196, 230)],
                [(104, 170), (98, 232)], [(156, 170), (164, 230)]):
        soft_line(p, pts, black_d[:3] + (220,), 3.0, 1.2, robe)
    for pts in ([(80, 160), (68, 206)], [(176, 160), (190, 206)]):
        soft_line(p, pts, shade(black, 1.5)[:3] + (120,), 2.0, 1.2, robe)
    panel = p.shape("poly", curve([(114, 110), (144, 110), (156, 170), (164, 236)], 5) +
                    [(150, 230), (136, 240), (122, 230), (106, 238)] + curve([(98, 236), (104, 170), (114, 110)], 5),
                    red, depth=0.14, line=1.4, clip=robe, **cloth)
    vgrad(p, panel, red_d, 140, 236, 0.0, 0.6)
    for pts in ([(130, 150), (128, 232)], [(118, 176), (112, 230)], [(144, 176), (150, 230)]):
        soft_line(p, pts, red_d[:3] + (230,), 2.6, 1.0, panel)
    p.stroke(curve([(114, 110), (106, 170), (98, 236)], 5), gold, 2.2)
    p.stroke(curve([(144, 110), (156, 170), (164, 236)], 5), gold, 2.2)
    for x, y in ((70, 218), (92, 222), (170, 222), (192, 216)):
        p.glow((x, y), 9, LAVA, 0.55)
        ring = sub(p._mask("ellipse", (x - 5, y - 3.4, x + 5, y + 3.4)), p._mask("ellipse", (x - 3.6, y - 2, x + 3.6, y + 2)))
        fill_clip(p, ring, LAVA_HOT, robe)
        fill_clip(p, p._mask("poly", [(x, y - 2.6), (x + 1, y), (x, y + 2.6), (x - 1, y)]), LAVA_HOT, robe)
    # boots
    for x0 in (96, 140):
        p.shape("poly", curve([(x0 + 18, 232), (x0 + 16, 242), (x0 - 10, 244), (x0 - 12, 238), (x0 - 2, 232)], 4),
                hexc("#2a1a18"), depth=0.3, line=1.4, spec=0.5, tex="leather", tex_amt=0.5)
    # rope belt with tassels
    p.shape("poly", taper(curve([(84, 158), (130, 166), (176, 156)], 5), 6, 6), hexc("#c89a58"), depth=0.35,
            line=1.3, rim=0, tex="wood_h", tex_amt=0.4)
    for x in (100, 110):
        p.shape("line", [(x, 164), (x - 3, 194)], hexc("#c89a58"), width=3.2, depth=0.3, line=1.0, rim=0)
        p.shape("poly", curve([(x - 3, 190), (x + 3, 196), (x + 2, 208), (x - 8, 208), (x - 8, 196)], 3), red,
                depth=0.3, line=1.1, rim=0)
    # ---- mantle over the shoulders: ragged black cape with gold trim
    mant = [(76, 104), (98, 92), (160, 92), (182, 106)]
    mant_hem = [(188, 138), (176, 134), (168, 146), (152, 138), (140, 150), (126, 140), (112, 150), (98, 138),
                (86, 146), (74, 134), (68, 138)]
    mm = p.shape("poly", curve(mant, 5) + mant_hem, black, depth=0.16, line=1.6, **cloth)
    rim(p, mm, EMBER_RIM, (0.8, 0.8), 2.2, 0.6)
    p.stroke(curve([(70, 134), (98, 136), (128, 138), (158, 136), (186, 134)], 5), gold[:3] + (0,), 0.1)
    for pts in ([(96, 108), (88, 136)], [(162, 108), (172, 132)]):
        soft_line(p, pts, black_d[:3] + (220,), 2.6, 1.0, mm)
    # dragon-eye pendant on gold chains
    chain(p, (110, 116), (124, 136), 4, hexc("#d8a840"), 5.5)
    chain(p, (148, 116), (136, 136), 4, hexc("#d8a840"), 5.5)
    p.glow((130, 148), 26, eyec, 0.65)
    pend = p.shape("poly", curve([(130, 132), (144, 142), (140, 158), (130, 164), (120, 158), (116, 142)], 4) +
                   [(130, 132)], gold, depth=0.25, light=1.45, spec=1.0, line=1.3, tex="metal", tex_amt=0.4)
    em = p.shape("poly", curve([(120, 148), (130, 140), (140, 148), (130, 156)], 4) + [(120, 148)], hexc("#ff9a2a"),
                 depth=0.25, light=1.5, line=1.0, rim=0, gloss=0.8)
    fill_clip(p, p._mask("poly", [(130, 141), (132, 148), (130, 155), (128, 148)]), DARK, em)
    del pend
    # ---- hood: peaked and drooping back, gold-edged, a face of shadow with burning eyes and a sly grin
    hood = p.union([("ellipse", (78, 24, 168, 124)),
                    ("poly", curve([(116, 28), (146, 12), (176, 6), (202, 12), (180, 20), (164, 34), (160, 58)], 4))])
    p.paint_mask(hood, red, depth=0.12, line=1.7, tex="cloth", tex_amt=0.7)
    rim(p, hood, EMBER_RIM, (1.0, 0.5), 2.2, 0.6)
    soft_line(p, [(150, 34), (156, 60), (160, 90)], red_d[:3] + (220,), 3.0, 1.4, hood)
    soft_line(p, [(96, 36), (112, 30), (132, 30)], light_tone(red, 1.4)[:3] + (140,), 3.0, 1.4, hood)
    p.stroke(curve([(150, 16), (176, 9), (198, 12)], 4), gold, 1.8)
    face = p.shape("ellipse", (84, 44, 152, 118), hexc("#120a10"), depth=0.2, light=0, line=1.2, rim=0, ao=0)
    spot(p, face, hexc("#5a1a14"), (112, 104), 30, 0.5)
    p.stroke(curve([(84, 104), (86, 66), (106, 44), (132, 42), (150, 60), (154, 104)], 6), gold, 2.4)
    ember_eye(p, 102, 80, 6.5, eyec, slant=0.7, inner=1)
    ember_eye(p, 132, 78, 5.8, eyec, slant=0.7, inner=-1)
    grin = p._mask("poly", curve([(98, 96), (112, 102), (128, 102), (140, 94), (134, 104), (116, 110), (102, 104)], 4))
    p.glow((118, 102), 14, hexc("#ff6a1a"), 0.35)
    fill_clip(p, grin, hexc("#3a0c0c"))
    for i in range(6):
        x = 102 + i * 6.4
        y = 100 + math.sin((i + 0.5) / 6 * math.pi) * 3.2
        fill_clip(p, p._mask("poly", [(x - 2.6, y - 1.4), (x + 2.6, y - 1.4), (x, y + 3.6)]), hexc("#f4e2c8"), grin)
    # hood rim casting a shadow over the forehead
    p.shape("poly", curve([(80, 112), (78, 64), (98, 36), (130, 32), (156, 50), (164, 90), (162, 116), (158, 70),
                           (140, 46), (114, 44), (94, 58), (86, 90)], 5), red, depth=0.25, line=1.4, rim=0,
            tex="cloth", tex_amt=0.5)
    # ---- front arm raising the wavy ritual dagger
    sleeve = p.shape("poly", curve([(102, 104), (82, 102), (62, 98), (50, 108), (52, 126), (66, 146), (84, 150),
                                    (100, 134)], 5), black, depth=0.2, line=1.6, **cloth)
    rim(p, sleeve, EMBER_RIM, (0.6, 1.0), 2.0, 0.55)
    soft_line(p, [(90, 108), (74, 124), (70, 142)], black_d[:3] + (220,), 2.6, 1.0, sleeve)
    p.shape("poly", curve([(56, 102), (46, 108), (50, 122), (60, 118)], 4), red_d, depth=0.3, line=1.2, rim=0)
    kris(p, (48, 98), (26, 24), 7.5, hexc("#b8bec8"))
    p.shape("line", [(38, 104), (60, 92)], gold, width=5.5, depth=0.3, spec=0.8, line=1.3, rim=0)
    p.shape("ellipse", (44, 91, 54, 101), hexc("#e0303a"), line=1.0, gloss=1.0, rim=0)
    p.shape("line", [(50, 100), (56, 116)], hexc("#3a2418"), width=5, depth=0.3, line=1.2, rim=0, tex="leather")
    p.shape("ellipse", (51, 114, 61, 122), gold, depth=0.3, spec=0.9, line=1.0, rim=0)
    fist = p.union([("ellipse", (42, 100, 62, 116))])
    p.paint_mask(fist, skin, depth=0.3, line=1.3, rim=0)
    for i in range(3):
        soft_line(p, [(45 + i * 5, 103), (47 + i * 5, 112)], shade(skin, 0.6)[:3] + (200,), 1.1, 0.2, fist)
    sparks(p, [(20, 60, 2.0), (70, 30, 1.6), (232, 90, 1.8), (228, 190, 1.8), (186, 70, 1.6), (26, 160, 1.6)])
    return done(p, 2.8, (40, 226, 222, 250))


def kris(p, base, tip, width, color):
    """Wavy ritual dagger from base to tip with a glowing blood-red rune channel."""
    (x0, y0), (x1, y1) = base, tip
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy, ux
    left, right, mid = [], [], []
    steps = 14
    for i in range(steps + 1):
        t = i / steps
        w = width / 2 * (1 - t ** 1.6 * 0.92)
        off = math.sin(t * math.pi * 3.2) * width * 0.42 * (1 - t * 0.6)
        cx, cy = x0 + dx * t + nx * off, y0 + dy * t + ny * off
        left.append((cx + nx * w, cy + ny * w))
        right.append((cx - nx * w, cy - ny * w))
        mid.append((cx, cy))
    m = p.shape("poly", left + [(x1 + ux * 2, y1 + uy * 2)] + right[::-1], color, depth=0.3, light=1.4, line=1.3,
                spec=1.0, tex="metal", tex_amt=0.5)
    p.glow(lerp(base, tip, 0.45), n * 0.35, hexc("#ff3a2a"), 0.3)
    tline(p, mid[1:-3], width * 0.22, width * 0.08, hexc("#ff4a3a"), m)
    tline(p, [(a[0] * 0.6 + b[0] * 0.4, a[1] * 0.6 + b[1] * 0.4) for a, b in zip(left, mid)][1:-3], width * 0.12,
          width * 0.04, hexc("#ffffff", 170), m)
    return m


@sprite
def fire_imp():
    """Mischievous imp of living embers hopping forward on goat legs: a big grinning head with a crown of
    flame, horns and bat ears, a molten pot belly, a spade tail and little bat wings, jabbing a red-hot
    pitchfork and holding a fireball behind its back."""
    p = canvas(SIZE, fit=(0.91, 0, 2))
    skin = hexc("#e2482a")
    skin_d = hexc("#a82a22")
    dark = hexc("#4a1616")
    belly = hexc("#ffb04a")
    iron = hexc("#4a4248")
    horn_c = hexc("#3a2626")
    hoof = hexc("#241618")
    rough = dict(tex="stone", tex_amt=0.35)
    haze(p, (120, 120), 116, 116, hexc("#ff6a1a"), 0.24)
    # ---- flaming hair, streaming back
    for x, base, w, h, lean in ((150, 66, 34, 52, 0.75), (130, 52, 40, 70, 0.55), (106, 48, 40, 66, 0.35),
                                (86, 56, 30, 44, 0.2)):
        flame(p, x, base, w, h, lean=lean, strength=0.55)
    # ---- back arm with a fireball, bat wings, tail
    wing_mem = hexc("#7a1e1e")
    bat_wing(p, (150, 136), (180, 110), [(204, 76), (238, 92), (236, 124), (212, 138)], wing_mem, dark, 5.5,
             edge=hexc("#ff9a3a"))
    tail = [(150, 186), (184, 212), (220, 210), (238, 184), (236, 160)]
    tm = p.shape("poly", taperw(tail, [14, 11, 8, 6, 5]), skin_d, depth=0.3, line=1.4, **rough)
    spade = p.shape("poly", curve([(237, 152), (246, 160), (252, 148), (244, 136), (237, 122), (230, 136), (222, 148),
                                   (228, 160), (237, 152)], 4), dark, depth=0.3, light=1.35, line=1.4, spec=0.5, rim=0)
    rim(p, spade, EMBER_RIM, (1, 0.5), 1.6, 0.8)
    del tm
    arm = leg(p, [(152, 142), (176, 130), (188, 106)], [14, 10, 9], skin_d, **rough)
    del arm
    p.glow((192, 84), 34, hexc("#ffb040"), 0.8)
    p.shape("ellipse", (178, 68, 206, 96), hexc("#ffcf5a"), light=1.5, depth=0.25, line=1.2, ink=hexc("#8a2a0a"),
            gloss=0.9, rim=0)
    flame(p, 192, 80, 22, 34, lean=0.25, glow=False)
    hand = p.shape("ellipse", (180, 94, 198, 110), skin_d, depth=0.3, line=1.3, rim=0)
    for x in (182, 188, 194):
        claw(p, x, 96, 5, -80, hexc("#2a1616"), line=0.8)
    del hand
    # ---- far leg kicked back (goat leg: thigh, backward hock, hoof)
    fl = leg(p, [(146, 182), (160, 200), (178, 196), (192, 204)], [22, 12, 9, 9], skin_d, **rough)
    p.shape("poly", curve([(188, 196), (200, 198), (204, 212), (190, 214)], 3) + [(188, 196)], hoof, depth=0.3,
            line=1.3, spec=0.6, rim=0)
    del fl
    # ---- near leg planted: shaggy dark thigh, bent hock, hoof
    nl = leg(p, [(120, 184), (102, 206), (118, 222), (110, 234)], [26, 13, 9, 9], skin, **rough)
    rim(p, nl, EMBER_RIM, (0.8, 0.8), 1.8, 0.6)
    p.shape("poly", curve([(102, 232), (120, 230), (122, 242), (98, 242)], 3) + [(102, 232)], hoof, depth=0.3,
            line=1.3, spec=0.6, rim=0)
    p.stroke([(111, 232), (110, 242)], hexc("#0a0608"), 1.2)
    # ---- body: small torso with a molten pot belly and glowing cracks
    body = p.shape("ellipse", (100, 126, 160, 196), skin, depth=0.14, line=1.6, **rough)
    p.glow((128, 172), 30, LAVA, 0.5)
    bl = p.shape("ellipse", (106, 146, 152, 196), belly, depth=0.2, light=1.4, line=1.2, rim=0, clip=body)
    vgrad(p, bl, hexc("#ff7a1a"), 150, 196, 0.2, 0.7)
    spot(p, bl, LAVA_HOT, (128, 170), 12, 0.6)
    lava_vein(p, [(112, 134), (120, 146), (114, 158)], 1.6, body, glow=0.2)
    lava_vein(p, [(152, 146), (146, 160), (150, 174)], 1.6, body, glow=0.2)
    fill_clip(p, p._mask("ellipse", (124, 172, 130, 178)), hexc("#b84a1a"), bl)
    # ---- the pitchfork, held across the body and jabbing up and forward
    base, head_ = (82, 240), (32, 58)
    dx, dy = head_[0] - base[0], head_[1] - base[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy, ux
    p.shape("poly", taper([base, head_], 5.5, 5.0, 2), iron, depth=0.35, light=1.4, spec=0.8, line=1.3, rim=0,
            tex="metal", tex_amt=0.5)
    cross = [(head_[0] + nx * 21 + ux * 4, head_[1] + ny * 21 + uy * 4), head_,
             (head_[0] - nx * 21 + ux * 4, head_[1] - ny * 21 + uy * 4)]
    p.shape("poly", taper(cross, 6, 6, 4), iron, depth=0.35, light=1.4, spec=0.8, line=1.4, rim=0)
    for k in (-1, 0, 1):
        s0 = (head_[0] + nx * 19 * k + ux * 4 * abs(k), head_[1] + ny * 19 * k + uy * 4 * abs(k))
        ln = 34 if k == 0 else 28
        tip = (s0[0] + ux * ln, s0[1] + uy * ln)
        p.shape("poly", taper([s0, lerp(s0, tip, 0.8)], 5.6, 4.0, 2), iron, depth=0.35, light=1.4, spec=0.8,
                line=1.2, rim=0)
        hot = lerp(s0, tip, 0.55)
        p.glow(tip, 11, LAVA, 0.75)
        p.shape("poly", [(hot[0] + nx * 3.2, hot[1] + ny * 3.2), tip, (hot[0] - nx * 3.2, hot[1] - ny * 3.2)],
                hexc("#ffb040"), depth=0.3, light=1.5, line=1.0, rim=0, ao=0)
    # ---- near arm gripping the shaft
    leg(p, [(114, 142), (86, 160), (60, 146)], [15, 10, 9], skin, **rough)
    fist = p.shape("ellipse", (42, 132, 64, 152), skin, depth=0.3, line=1.4, rim=0)
    for i in range(3):
        soft_line(p, [(46 + i * 5, 135), (48 + i * 5, 146)], skin_d[:3] + (220,), 1.2, 0.2, fist)
    # ---- head: bat ears, little horns, big grinning face
    p.shape("poly", curve([(66, 80), (40, 60), (30, 50), (46, 78), (62, 96)], 4), skin_d, depth=0.3, line=1.4, **rough)
    ear = p.shape("poly", curve([(138, 70), (170, 58), (206, 50), (184, 72), (170, 92), (144, 104)], 4), skin,
                  depth=0.25, line=1.5, **rough)
    p.shape("poly", curve([(146, 76), (176, 64), (194, 58), (176, 76), (148, 96)], 4), hexc("#8a1e1e"), clip=ear,
            **NOLINE)
    for pts in ([(86, 52), (80, 32), (66, 20), (62, 26)], [(120, 46), (126, 24), (142, 10), (144, 18)]):
        horn(p, pts[:3], 12, 2.5, horn_c, rings=2, spec=0.7, tex="stone", line=1.4)
        p.glow(pts[2], 7, LAVA, 0.55)
    head = p.shape("ellipse", (54, 40, 154, 132), skin, depth=0.12, line=1.7, **rough)
    rim(p, head, EMBER_RIM, (0.9, 0.7), 2.4, 0.7)
    spot(p, head, light_tone(skin, 1.3), (84, 62), 22, 0.45)
    lava_vein(p, [(140, 70), (134, 84), (142, 98)], 1.6, head, glow=0.2)
    lava_vein(p, [(96, 46), (102, 58)], 1.4, head, glow=0.2)
    # cheeks glowing
    for x, y, r in ((66, 104, 8), (124, 104, 10)):
        spot(p, head, hexc("#ffb050"), (x, y), r, 0.55)
    # eyes: yellow, slit pupils, wicked brows
    angry_eye(p, 76, 82, 10.5, 12, hexc("#ffcc2a"), inner=1, slant=0.45, sclera=hexc("#fff1c0"), look=-0.4,
              brow=dark, brow_w=4.4)
    angry_eye(p, 112, 80, 13, 14, hexc("#ffcc2a"), inner=-1, slant=0.45, sclera=hexc("#fff1c0"), look=-0.4,
              brow=dark, brow_w=5)
    p.shape("poly", curve([(68, 84), (56, 94), (46, 100), (58, 102), (68, 98)], 4), skin, depth=0.3, line=1.3,
            rim=0, **rough)
    # big sly grin with fangs
    mouth = p.shape("poly", curve([(58, 104), (78, 112), (104, 114), (130, 106), (138, 98), (136, 110),
                                   (122, 124), (98, 128), (74, 122)], 5), hexc("#3a0a0a"), depth=0.25, line=1.5,
                    rim=0, ao=0)
    p.shape("ellipse", (82, 116, 118, 136), hexc("#ff6a4a"), depth=0.3, light=1.3, clip=mouth, **dict(line=0))
    teeth(p, [(66, 107, 6, 7, 1), (80, 112, 6, 8, 1), (120, 110, 6, 8, 1), (130, 104, 5, 7, 1)],
          hexc("#fff4d8"), line=0.9)
    teeth(p, [(94, 115, 6, 11, 1), (108, 114, 6, 11, 1)], hexc("#fff4d8"), line=0.9)
    p.stroke(curve([(134, 96), (140, 98), (142, 104)], 3), dark, 2.0)
    sparks(p, [(22, 100, 2.0), (60, 190, 2.2), (216, 150, 1.8), (224, 36, 2.0), (176, 20, 1.6), (40, 20, 1.8),
               (160, 230, 1.6)])
    return done(p, 2.8, (60, 224, 212, 248))


def bat_wing(p, shoulder, wrist, fingers, membrane, bone_c, width, edge=None):
    """Small bat wing: an arm to the wrist, finger bones fanning out and a scalloped membrane between them."""
    edge_pts = [fingers[0]]
    for f0, f1 in zip(fingers, fingers[1:]):
        mx, my = (f0[0] + f1[0]) / 2, (f0[1] + f1[1]) / 2
        edge_pts += [(mx + (wrist[0] - mx) * 0.26, my + (wrist[1] - my) * 0.26), f1]
    mem = p._mask("poly", [shoulder, wrist] + curve(edge_pts, 5) + [lerp(shoulder, fingers[-1], 0.4)])
    p.paint_mask(mem, membrane, depth=0.1, light=1.3, line=1.4, tex="leather", tex_amt=0.5)
    for f in fingers[1:]:
        soft_line(p, [wrist, f], shade(membrane, 0.6)[:3] + (140,), width * 1.2, 1.2, mem)
    if edge:
        p.stroke(curve(edge_pts, 5), edge, 1.8)
    p.shape("poly", taper([shoulder, wrist], width * 1.2, width * 0.9, 2), bone_c, depth=0.3, line=1.2, rim=0)
    for f in fingers:
        p.shape("poly", taper([wrist, f], width * 0.6, width * 0.2, 2), bone_c, depth=0.3, line=1.0, rim=0)
    claw(p, wrist[0], wrist[1], width * 1.3, -110, hexc("#2a1616"), line=0.8)
    return mem


def plate(p, m, color, rim_c=EMBER_RIM, rim_d=(0.7, 0.9), rim_s=0.7, streak=None, line=1.6, depth=0.16,
          light=1.4, spec=1.0, tex_amt=0.45):
    """Blackened steel plate: metal texture, a cool specular edge, a warm bounce light from the fire below and
    an optional bright highlight streak along `streak`."""
    p.paint_mask(m, color, depth=depth, light=light, spec=spec, tex="metal", tex_amt=tex_amt, line=line)
    if rim_c:
        rim(p, m, rim_c, rim_d, 2.2, rim_s)
    if streak:
        soft_line(p, streak, hexc("#ffffff", 150), 2.0, 0.7, m)
    return m


@sprite
def flame_knight():
    """Elite: a hulking knight in blackened plate split by glowing seams, planted in a wide stance with a
    burning greatsword raised in both gauntlets; a great helm with a molten visor slit, swept horns and a
    streaming flame plume, spiked pauldrons and a scorched cape."""
    p = canvas(SIZE, fit=(0.94, 2, 0))
    steel = hexc("#474552")
    steel_d = hexc("#2e2c38")
    steel_l = hexc("#5c5a68")
    cloth = hexc("#8e1c1c")
    gold = hexc("#d8a040")
    haze(p, (90, 110), 120, 120, hexc("#ff5a1a"), 0.24)
    # ---- flame plume streaming back off the helm
    for x, base, w, h, lean in ((178, 56, 30, 40, 1.3), (160, 44, 36, 48, 1.1), (140, 34, 36, 50, 0.85),
                                (122, 30, 30, 42, 0.6)):
        flame(p, x, base, w, h, lean=lean, strength=0.5)
    # ---- scorched cape billowing behind
    cape = [(146, 92), (190, 98), (214, 140), (236, 206), (226, 200), (222, 222), (210, 208), (200, 230), (190, 212),
            (176, 228), (168, 204), (150, 200)]
    cm = p.shape("poly", curve(cape[:4], 5) + cape[4:], shade(cloth, 0.62), depth=0.12, line=1.6, tex="cloth",
                 tex_amt=0.7)
    vgrad(p, cm, hexc("#1a0a0a"), 170, 230, 0.0, 0.6)
    for pts in ([(170, 110), (190, 160), (200, 210)], [(190, 110), (214, 170), (222, 204)]):
        soft_line(p, pts, hexc("#3a0a0a", 200), 3.0, 1.2, cm)
    for x, y in ((226, 204), (210, 212), (190, 214), (176, 226)):
        spark(p, x, y + 2, 1.8)
    # ---- far arm reaching to the hilt
    fa = p.union([("poly", taperw([(164, 110), (150, 146), (96, 172)], [30, 22, 18]))])
    plate(p, fa, steel_d, rim_s=0.5)
    # ---- legs in a wide stance: far leg back, near leg forward
    for hip, knee, foot, c in (((142, 176), (160, 206), (172, 232), steel_d), ((106, 178), (90, 206), (80, 232), steel)):
        lm = p.union([("poly", taperw([hip, knee, foot], [30, 22, 18]))])
        plate(p, lm, c, streak=[lerp(hip, knee, 0.2), lerp(hip, knee, 0.8)] if c == steel else None)
        lava_vein(p, [lerp(knee, foot, 0.2), lerp(knee, foot, 0.7)], 1.4, lm, glow=0.2)
        kx, ky = knee
        km = p._mask("ellipse", (kx - 14, ky - 12, kx + 14, ky + 12))
        plate(p, km, steel_l if c == steel else steel_d, rim_s=0.5)
        p.shape("poly", [(kx - 5, ky - 4), (kx - 18, ky - 2), (kx - 5, ky + 5)], steel_d, depth=0.3, spec=0.8, line=1.2,
                rim=0)
        fx, fy = foot
        sm = p._mask("poly", curve([(fx + 16, fy - 10), (fx + 14, fy + 8), (fx - 22, fy + 8), (fx - 20, fy - 2),
                                    (fx - 4, fy - 10)], 4))
        plate(p, sm, c, rim_s=0.5)
        p.stroke([(fx - 6, fy - 8), (fx - 8, fy + 7)], gold, 1.6)
    # ---- tabard hanging between the legs, burnt hem, flame sigil
    tab = p.shape("poly", [(104, 168), (150, 168), (154, 214), (146, 208), (140, 222), (132, 210), (124, 224),
                           (116, 208), (108, 218), (102, 206)], cloth, depth=0.14, line=1.5, tex="cloth", tex_amt=0.7)
    vgrad(p, tab, hexc("#200808"), 190, 224, 0.0, 0.75)
    for pts in ([(116, 176), (114, 206)], [(140, 176), (142, 204)]):
        soft_line(p, pts, hexc("#4a0a0a", 200), 2.4, 1.0, tab)
    sig = p.shape("poly", curve([(127, 174), (135, 186), (133, 198), (127, 204), (121, 198), (119, 186)], 4) +
                  [(127, 174)], gold, depth=0.25, light=1.45, spec=0.8, line=1.1)
    fill_clip(p, p._mask("poly", [(127, 184), (131, 193), (127, 200), (123, 193)]), hexc("#ff7a1a"), sig)
    # ---- faulds: layered plates over the hips
    for i, (y0, y1) in enumerate(((176, 192), (164, 180))):
        fm = p._mask("poly", curve([(92, y0 - 4), (128, y0), (166, y0 - 6)], 4) +
                     curve([(168, y1 + 4), (128, y1 + 8), (90, y1 + 2)], 4))
        plate(p, fm, steel_d if i == 0 else steel, rim_s=0.5)
        rivets_row = [(100 + k * 14, y1 + 2 + (1 if k in (1, 2) else 0)) for k in range(5)]
        for x, y in rivets_row:
            p.shape("ellipse", (x - 1.8, y - 1.8, x + 1.8, y + 1.8), gold, line=0.7, depth=0.4, light=1.6, rim=0, ao=0.4)
    # ---- breastplate: sculpted, a glowing seam down the middle and a flame sigil on the chest
    chest = p._mask("poly", curve([(96, 96), (126, 88), (160, 96), (168, 124), (160, 160), (128, 170), (96, 162),
                                   (88, 128), (96, 96)], 6))
    plate(p, chest, steel, streak=[(102, 104), (106, 130), (112, 150)])
    for pts in ([(128, 94), (130, 128), (128, 166)], [(98, 136), (126, 142), (158, 136)]):
        lava_vein(p, pts, 1.8, chest, glow=0.3)
    p.glow((130, 118), 22, LAVA, 0.5)
    em = p.shape("poly", curve([(130, 100), (140, 114), (138, 126), (130, 132), (122, 126), (120, 114)], 4) +
                 [(130, 100)], gold, depth=0.25, light=1.45, spec=0.9, line=1.2)
    fill_clip(p, p._mask("poly", curve([(130, 108), (135, 118), (130, 128), (125, 118)], 3)), LAVA_HOT, em)
    # belt
    p.shape("poly", taper(curve([(92, 162), (128, 170), (164, 160)], 4), 9, 9), hexc("#3a2620"), depth=0.3,
            line=1.3, tex="leather", tex_amt=0.5)
    p.shape("rect", (120, 160, 136, 174), gold, radius=3, depth=0.3, spec=0.9, line=1.2)
    # ---- far pauldron (behind the helm)
    pauldron(p, 166, 102, 24, steel_d, steel_d, gold)
    for x, h in ((158, 22), (172, 26)):
        p.shape("poly", [(x - 5, 88), (x + 5, 88), (x + 2, 88 - h)], steel_d, depth=0.3, spec=0.8, line=1.3, rim=0)
        p.glow((x + 2, 88 - h), 5, LAVA, 0.5)
    # ---- the great helm: horns, T-visor glowing, breath holes, gold crown band
    for pts, w in (([(132, 44), (150, 26), (172, 20), (184, 26)], 12), ([(90, 44), (78, 22), (68, 12), (56, 12)], 12)):
        horn(p, pts, w, 2.4, hexc("#26222c"), rings=3, spec=0.8, tex="stone", line=1.5)
    helm = p._mask("poly", curve([(84, 70), (84, 40), (100, 24), (122, 22), (140, 32), (146, 56), (144, 88), (120, 98),
                                  (92, 94), (84, 70)], 6))
    plate(p, helm, steel, streak=[(96, 36), (92, 52), (92, 70)])
    p.shape("poly", taper([(114, 22), (112, 60), (110, 96)], 7, 5, 3), steel_l, depth=0.3, spec=0.9, line=1.2, rim=0,
            clip=helm)
    p.glow((104, 60), 28, LAVA, 0.8)
    slit = p._mask("poly", [(84, 54), (132, 52), (132, 62), (116, 63), (114, 84), (106, 84), (104, 64), (84, 64)])
    fill_clip(p, slit, hexc("#1a0808"), helm)
    fill_clip(p, p._mask("poly", [(86, 56), (130, 55), (130, 59), (112, 60), (110, 80), (108, 60), (86, 61)]),
              hexc("#ffb040"), helm)
    fill_clip(p, p._mask("poly", [(90, 57), (126, 56.4), (126, 58), (90, 59)]), LAVA_CORE, helm)
    for x, y in ((124, 72), (130, 72), (124, 80), (130, 80), (127, 88)):
        fill_clip(p, p._mask("ellipse", (x - 1.8, y - 1.8, x + 1.8, y + 1.8)), hexc("#ff8a2a"), helm)
    band = p._mask("poly", curve([(84, 44), (112, 40), (144, 44)], 4) + curve([(145, 51), (112, 47), (84, 51)], 4))
    p.paint_mask(inter(band, helm), gold, depth=0.3, light=1.45, spec=0.9, line=1.1, rim=0)
    # ---- the burning greatsword, raised in both hands
    guard, tip = (60, 146), (16, 16)
    for i in range(8):
        t = 0.12 + i * 0.105
        x, y = lerp(guard, tip, t)
        flame(p, x + 7, y + 10, 24 - t * 8, 36 - t * 14 + 6 * (i % 2), lean=0.45, strength=0.4)
    p.glow(lerp(guard, tip, 0.5), 56, LAVA, 0.5)
    bl = greatblade(p, guard, tip, 15, hexc("#6a6470"))
    lava_vein(p, [lerp(guard, tip, 0.05), lerp(guard, tip, 0.9)], 3.0, bl, glow=0.0, char=False, taper_to=0.2)
    for t in (0.3, 0.62):
        x, y = lerp(guard, tip, t)
        flame(p, x + 3, y + 4, 10, 16, lean=0.4, glow=False)
    # crossguard, grip, pommel
    dx, dy = tip[0] - guard[0], tip[1] - guard[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy, ux
    cg = [(guard[0] + nx * 22 - ux * 2, guard[1] + ny * 22 - uy * 2), guard,
          (guard[0] - nx * 22 - ux * 2, guard[1] - ny * 22 - uy * 2)]
    p.shape("poly", taperw(cg, [6, 9, 6], 4), steel_d, depth=0.3, spec=0.9, line=1.4, rim=0)
    for q in (cg[0], cg[2]):
        p.shape("ellipse", (q[0] - 4.5, q[1] - 4.5, q[0] + 4.5, q[1] + 4.5), gold, depth=0.3, spec=0.9, line=1.1, rim=0)
    p.shape("ellipse", (guard[0] - 5, guard[1] - 5, guard[0] + 5, guard[1] + 5), hexc("#e0302a"), line=1.0, gloss=1.0,
            rim=0)
    grip_end = (guard[0] - ux * 44, guard[1] - uy * 44)
    p.shape("poly", taper([guard, grip_end], 7, 7, 2), hexc("#3a2418"), depth=0.3, line=1.2, rim=0, tex="leather")
    p.shape("ellipse", (grip_end[0] - 6, grip_end[1] - 6, grip_end[0] + 6, grip_end[1] + 6), gold, depth=0.3,
            spec=0.9, line=1.2, rim=0)
    # ---- near arm and gauntlets on the grip
    na = p.union([("poly", taperw([(100, 108), (92, 140), (78, 164)], [30, 24, 20]))])
    plate(p, na, steel, streak=[(92, 112), (86, 140)])
    for q in (lerp(guard, grip_end, 0.3), lerp(guard, grip_end, 0.72)):
        gm = p._mask("poly", ellipse_pts(q[0], q[1], 11, 9, 24, rot=-60))
        plate(p, gm, steel_l, rim_s=0.5)
        for k in (-1, 0, 1):
            soft_line(p, [(q[0] - 6, q[1] + k * 4 - 1), (q[0] + 2, q[1] + k * 4 + 3)], hexc("#141018", 200), 1.1, 0.2,
                      gm)
    # ---- near pauldron: layered and spiked
    for x, y, h in ((76, 94, 22), (90, 88, 28), (106, 88, 22)):
        p.shape("poly", [(x - 6, y), (x + 6, y), (x - 3, y - h)], steel_d, depth=0.3, spec=0.8, line=1.4, rim=0)
        p.glow((x - 3, y - h), 6, LAVA, 0.55)
        fill_clip(p, p._mask("poly", [(x - 4.5, y - h * 0.5), (x - 3, y - h), (x - 1.5, y - h * 0.5)]), LAVA_HOT)
    pauldron(p, 92, 108, 27, steel, steel_l, gold)
    sparks(p, [(30, 80, 2.0), (10, 120, 1.8), (60, 26, 2.0), (200, 40, 1.8), (236, 120, 2.0), (46, 200, 1.8),
               (220, 70, 1.6)])
    return done(p, 2.8, (34, 222, 244, 250))


def pauldron(p, cx, cy, r, color, lame_c, trim):
    """Rounded shoulder plate over two curved lames, spikes along the top and a gold trim."""
    for k in (2, 1):
        y = cy + r * 0.34 * k
        rr = r * (1 - 0.1 * k)
        lm = sub(p._mask("ellipse", (cx - rr * 1.05, y - rr * 0.7, cx + rr * 1.0, y + rr * 0.62)),
                 p._mask("ellipse", (cx - rr * 1.3, y - rr * 1.4, cx + rr * 1.3, y + rr * 0.1)))
        plate(p, lm, lame_c, rim_s=0.5, line=1.4)
        p.shape("ellipse", (cx - rr * 0.9, y + rr * 0.34, cx - rr * 0.9 + 3.6, y + rr * 0.34 + 3.6), trim, line=0.7,
                depth=0.4, light=1.6, rim=0, ao=0.4)
    dome = p._mask("ellipse", (cx - r * 1.1, cy - r * 0.9, cx + r * 1.05, cy + r * 0.72))
    plate(p, dome, color, streak=[(cx - r * 0.75, cy - r * 0.05), (cx - r * 0.45, cy - r * 0.55),
                                  (cx + r * 0.05, cy - r * 0.72)])
    tline(p, [(cx - r * 1.02, cy + r * 0.2), (cx - r * 0.3, cy + r * 0.62), (cx + r * 0.5, cy + r * 0.6),
              (cx + r * 0.98, cy + r * 0.25)], 2.4, 2.4, trim, dome)
    return dome


def greatblade(p, guard, tip, width, color):
    """Broad greatsword blade, heated dark red, with a bevel line and a bright edge."""
    (x0, y0), (x1, y1) = guard, tip
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy * width / 2, ux * width / 2
    tl = 1.4 * width
    pts = [(x0 + nx, y0 + ny), (x1 - ux * tl + nx * 0.95, y1 - uy * tl + ny * 0.95), (x1, y1),
           (x1 - ux * tl - nx * 0.95, y1 - uy * tl - ny * 0.95), (x0 - nx, y0 - ny)]
    m = p.shape("poly", pts, color, depth=0.3, light=1.35, line=1.5, spec=1.0, tex="metal", tex_amt=0.5)
    vgrad(p, m, hexc("#ff5a1a"), y0, y1, 0.45, 0.1)
    tline(p, [(x0 - nx * 0.75, y0 - ny * 0.75), (x1 - ux * tl - nx * 0.7, y1 - uy * tl - ny * 0.7), (x1, y1)], 1.8,
          0.8, hexc("#fff2c8", 220), m)
    return m


def almond_eye(p, cx, cy, rx, ry, iris, skin, side=1, lid=0.38, glow=None, line_c=hexc("#1a0c14")):
    """Elegant half-lidded eye: an almond white under a heavy lid, a glowing iris, a thick upper lash line
    flicking out at the outer corner (`side` 1 = outer corner on the right)."""
    top = [(cx - rx, cy + ry * 0.1), (cx - rx * 0.4, cy - ry * 0.95), (cx + rx * 0.5, cy - ry * 0.9),
           (cx + rx, cy - ry * 0.05)]
    bot = [(cx + rx, cy - ry * 0.05), (cx + rx * 0.3, cy + ry * 0.8), (cx - rx * 0.5, cy + ry * 0.75),
           (cx - rx, cy + ry * 0.1)]
    if side < 0:
        top = [(2 * cx - x, y) for x, y in top][::-1]
        bot = [(2 * cx - x, y) for x, y in bot][::-1]
    em = p._mask("poly", curve(top, 5) + curve(bot, 5))
    p.paint_mask(em, hexc("#fbf2ea"), shadow=0.8, light=0, depth=0.3, line=0, rim=0, ao=0)
    if glow:
        p.glow((cx - rx * 0.15, cy + ry * 0.1), rx * 1.8, glow, 0.55)
    ix, iy = cx - rx * 0.2, cy + ry * 0.08
    ir = ry * 0.82
    fill_clip(p, p._mask("ellipse", (ix - ir, iy - ir, ix + ir, iy + ir)), iris, em)
    fill_clip(p, p._mask("ellipse", (ix - ir * 0.8, iy - ir * 0.1, ix + ir * 0.8, iy + ir * 0.95)),
              light_tone(iris, 1.45), em, blur=0.3)
    fill_clip(p, p._mask("poly", curve([(ix, iy - ir * 0.8), (ix + ir * 0.2, iy), (ix, iy + ir * 0.8),
                                        (ix - ir * 0.2, iy)], 3)), DARK, em)
    fill_clip(p, p._mask("ellipse", (ix - ir * 0.7, iy - ir * 0.6, ix - ir * 0.2, iy - ir * 0.15)), WHITE, em)
    # heavy lid over the top of the eye
    lid_m = p._mask("poly", [(cx - rx * 1.3, cy - ry * 2), (cx + rx * 1.3, cy - ry * 2),
                             (cx + rx * 1.3, cy - ry * 0.95 + ry * lid * 2.0), (cx - rx * 1.3, cy - ry * 0.95 + ry * lid * 1.6)])
    fill_clip(p, lid_m, skin, em)
    lid_y0 = cy - ry * 0.95 + ry * lid * 1.6
    lid_y1 = cy - ry * 0.95 + ry * lid * 2.0
    outer = (cx + rx * 1.35 * side, (lid_y1 if side > 0 else lid_y0) - ry * 0.55)
    lash = [(cx - rx * side * 1.02, (lid_y0 if side > 0 else lid_y1) + ry * 0.2), (cx, (lid_y0 + lid_y1) / 2 - 0.3),
            (cx + rx * side * 0.95, (lid_y1 if side > 0 else lid_y0) + ry * 0.05), outer]
    tline(p, lash, ry * 0.35, ry * 0.5, line_c)
    tline(p, lash[2:], ry * 0.5, ry * 0.12, line_c)
    soft_line(p, curve(bot, 4)[1:-1], line_c[:3] + (150,), ry * 0.14, 0.2)
    return em


@sprite
def ember_priestess():
    """Boss: Kor Rahibe, a tall high priestess of the dragon cult. A ring of fire burns behind her; she wears
    a horned obsidian crown with an ember gem, long raven hair lit red by the flames, a high flared collar and
    a flowing crimson and gold robe. One hand raises a fireball, the other swings a burning censer on a chain;
    her face is pale and proud, with ember eyes and a cruel little smile."""
    p = canvas(BOSS, fit=(0.95, 0, 0))
    robe = hexc("#b0282a")
    robe_d = hexc("#5e1218")
    robe_l = hexc("#d8443a")
    gold = hexc("#f0b848")
    skin = hexc("#f0dcd2")
    hair = hexc("#2a1624")
    obs = hexc("#2a2230")
    cl = dict(tex="cloth", tex_amt=0.55)
    haze(p, (210, 200), 200, 200, hexc("#ff4a1a"), 0.3)
    # ---- halo: a gold ring crowned by flames
    ring = sub(p._mask("ellipse", (132, 18, 316, 202)), p._mask("ellipse", (144, 30, 304, 190)))
    haze(p, (224, 110), 110, 110, hexc("#ff8a2a"), 0.3)
    for i in range(15):
        a = math.radians(-180 + i * (180 / 14))
        x, y = 224 + 92 * math.cos(a), 110 + 92 * math.sin(a)
        flame(p, x, y + 4, 16, 26 + 8 * math.sin(i * 1.7) ** 2, lean=math.cos(a) * 0.35, strength=0.4)
    p.paint_mask(ring, gold, depth=0.3, light=1.45, line=1.6, spec=0.8, rim=0, tex="metal", tex_amt=0.4)
    for i in range(8):
        a = math.radians(-180 + i * (180 / 7))
        x, y = 224 + 92 * math.cos(a), 110 + 92 * math.sin(a)
        p.shape("ellipse", (x - 5, y - 5, x + 5, y + 5), hexc("#ff7a1a"), line=1.0, light=1.6, gloss=1.0, rim=0)
    # ---- long hair flowing behind
    hb = p.shape("poly", curve([(186, 76), (236, 60), (270, 92), (286, 150), (300, 214), (326, 280), (344, 318),
                                (310, 306), (296, 328), (274, 280), (256, 214), (244, 170), (226, 130)], 6), hair,
                 depth=0.12, line=1.8, tex="fur", tex_amt=0.35)
    for pts in ([(252, 90), (274, 150), (290, 220), (316, 290)], [(240, 110), (262, 170), (276, 240), (298, 300)]):
        soft_line(p, pts, hexc("#8a2a2a", 170), 3.0, 1.4, hb)
    rim(p, hb, hexc("#ff6a3a"), (1, 0.3), 3.0, 0.8)
    # ---- far arm raised, a fireball blazing over the palm
    sleeve_b = p.shape("poly", curve([(252, 176), (282, 170), (300, 150), (312, 124), (324, 132), (326, 170), (316, 204),
                                      (292, 216), (262, 204)], 5), robe_d, depth=0.18, line=1.8, **cl)
    rim(p, sleeve_b, EMBER_RIM, (1, 0.6), 2.6, 0.7)
    fa = p.shape("poly", taperw([(304, 150), (314, 124), (320, 110)], [14, 11, 10]), skin, depth=0.3, line=1.5,
                 rim=0)
    del fa
    p.glow((326, 72), 64, hexc("#ffb040"), 0.85)
    p.shape("ellipse", (302, 48, 350, 96), hexc("#ffcf5a"), light=1.5, depth=0.25, line=1.5, ink=hexc("#8a2a0a"),
            gloss=0.9, rim=0)
    flame(p, 326, 76, 40, 64, lean=0.1, glow=False)
    hand = p.union([("ellipse", (310, 100, 330, 118))])
    p.paint_mask(hand, skin, depth=0.3, line=1.4, rim=0)
    for x, a in ((312, -120), (318, -100), (324, -80), (329, -60)):
        tline(p, [(x, 104), (x + math.cos(math.radians(a)) * 8, 104 + math.sin(math.radians(a)) * 8)], 3.4, 2.2, skin)
        claw(p, x + math.cos(math.radians(a)) * 8, 104 + math.sin(math.radians(a)) * 8, 4, a, hexc("#3a1018"), line=0.8)
    # ---- the robe: flowing skirt with a train, a dark front panel embroidered with flames, gold hem
    hem = []
    for i in range(14):
        x = 92 + i * 17
        hem += [(x, 362 - (i % 2) * 3), (x + 8.5, 368)]
    skirt = p.shape("poly", curve([(176, 226), (246, 226), (270, 286), (316, 344), (352, 364)], 6) + [(346, 372)] +
                    hem[::-1] + curve([(88, 364), (132, 300), (160, 250), (176, 226)], 6), robe, depth=0.1, line=1.8,
                    **cl)
    vgrad(p, skirt, robe_d, 240, 370, 0.0, 0.55)
    rim(p, skirt, EMBER_RIM, (1, 0.4), 3.0, 0.8)
    for pts in ([(170, 250), (140, 310), (120, 360)], [(252, 250), (284, 310), (316, 356)],
                [(160, 280), (140, 362)], [(262, 290), (292, 362)]):
        soft_line(p, pts, robe_d[:3] + (220,), 5.0, 2.2, skirt)
    for pts in ([(150, 290), (126, 350)], [(270, 296), (300, 352)], [(176, 300), (164, 360)]):
        soft_line(p, pts, robe_l[:3] + (130,), 3.4, 2.0, skirt)
    panel = p.shape("poly", curve([(192, 232), (230, 232), (246, 300), (256, 366)], 5) +
                    curve([(166, 366), (178, 300), (192, 232)], 5), robe_d, depth=0.12, line=1.5, clip=skirt, **cl)
    for k, y in enumerate(range(262, 364, 26)):
        w = 12 + k * 3
        flame(p, 212 + k * 1.5, y + 16, w * 1.5, 24, glow=False, colors=("#b8702a", "#f0b848", "#fff0b0"))
    p.stroke(curve([(192, 232), (178, 300), (166, 366)], 5), gold, 3.4)
    p.stroke(curve([(230, 232), (246, 300), (256, 366)], 5), gold, 3.4)
    hem_band = p._mask("poly", hem + [(346, 372), (352, 364), (352, 378), (86, 378), (88, 364)])
    p.paint_mask(inter(hem_band, p._mask("rect", (0, 350, 384, 384))), gold, depth=0.25, light=1.45, spec=0.7,
                 line=1.4, rim=0, tex="metal", tex_amt=0.3)
    # ---- bodice and sash
    bod = p._mask("poly", curve([(176, 170), (250, 170), (246, 206), (242, 236), (180, 236), (176, 206), (176, 170)], 5))
    p.paint_mask(bod, robe, depth=0.14, line=1.7, **cl)
    for pts in ([(196, 180), (200, 230)], [(230, 180), (226, 230)]):
        soft_line(p, pts, robe_d[:3] + (200,), 3.0, 1.5, bod)
    sash = p._mask("poly", taper(curve([(168, 228), (212, 238), (256, 226)], 5), 14, 14))
    p.paint_mask(sash, gold, depth=0.3, light=1.45, spec=0.9, line=1.4, tex="metal", tex_amt=0.4)
    for pts in ([(206, 240), (196, 280), (190, 300)], [(218, 240), (226, 276), (232, 304)]):
        p.shape("poly", taper(pts, 10, 6), gold, depth=0.3, light=1.4, spec=0.7, line=1.3, rim=0)
    p.glow((212, 236), 26, LAVA, 0.7)
    gem = p.shape("poly", curve([(212, 222), (224, 236), (212, 252), (200, 236)], 3) + [(212, 222)], hexc("#ff7a1a"),
                  line=1.3, light=1.6, gloss=1.0, rim=0, depth=0.3)
    fill_clip(p, p._mask("poly", [(212, 228), (216, 236), (212, 246), (208, 236)]), LAVA_CORE, gem, blur=0.4)
    # ---- high flared collar framing the head: dark red fan with gold spines and trim
    fan = []
    for i in range(9):
        a = math.radians(-172 + i * (164 / 8))
        rr = 70 if i % 2 == 0 else 58
        fan.append((214 + rr * math.cos(a), 176 + rr * 0.95 * math.sin(a)))
    col = p.shape("poly", [(160, 184)] + curve(fan, 3) + [(268, 184), (214, 196)], robe_d, depth=0.16, line=1.8, **cl)
    for i in range(0, 9, 2):
        a = math.radians(-172 + i * (164 / 8))
        tline(p, [(214 + 20 * math.cos(a), 176 + 20 * math.sin(a)), (214 + 66 * math.cos(a), 176 + 63 * math.sin(a))],
              3.4, 1.4, gold, col)
    p.stroke(curve(fan, 3), gold, 2.4)
    rim(p, col, EMBER_RIM, (0.6, -0.8), 2.6, 0.6)
    # ---- mantle: gold scale shoulders with ember gems
    mant = p._mask("poly", curve([(158, 196), (180, 172), (214, 166), (248, 172), (270, 196), (252, 206), (214, 200),
                                  (176, 206), (158, 196)], 5))
    p.paint_mask(mant, gold, depth=0.25, light=1.45, spec=0.9, line=1.6, tex="metal", tex_amt=0.4)
    scale_rows(p, mant, (156, 172, 272, 206), shade(gold, 1.08), size=11, line=0.8)
    for cx in (172, 256):
        p.glow((cx, 194), 12, LAVA, 0.6)
        p.shape("ellipse", (cx - 6, 188, cx + 6, 200), hexc("#ff7a1a"), line=1.1, light=1.6, gloss=1.0, rim=0)
    # ---- neck and face
    p.shape("poly", curve([(200, 140), (222, 140), (226, 172), (206, 176), (198, 160)], 4), skin, depth=0.25,
            line=1.5, rim=0)
    spot(p, p._mask("rect", (196, 140, 230, 178)), hexc("#c89a9a"), (218, 150), 14, 0.6)
    face = p._mask("poly", curve([(214, 74), (236, 80), (244, 100), (242, 124), (230, 140), (214, 150), (204, 152),
                                  (196, 144), (190, 130), (187, 112), (190, 92), (200, 78), (214, 74)], 6))
    p.paint_mask(face, skin, depth=0.12, light=1.2, line=1.7, rim=0.3)
    spot(p, face, hexc("#ff9a8a"), (230, 124), 11, 0.4)
    spot(p, face, hexc("#ff9a8a"), (194, 124), 6, 0.3)
    spot(p, face, hexc("#b88a96"), (238, 108), 12, 0.35)
    rim(p, face, hexc("#ffb080"), (1, 0.5), 2.2, 0.6)
    # nose and a cruel little smile
    soft_line(p, [(197, 110), (193, 120), (195, 124)], hexc("#b88a8a", 220), 1.6, 0.4, face)
    fill_clip(p, p._mask("ellipse", (193, 122, 199, 126)), hexc("#9a6a6a", 200), face, blur=0.3)
    lips = p.shape("poly", curve([(198, 136), (205, 134), (212, 135), (220, 131), (216, 138), (206, 141),
                                  (199, 139)], 4), hexc("#8a1a30"), depth=0.3, light=1.45, line=1.0, rim=0, gloss=0.5)
    del lips
    soft_line(p, [(198, 137), (207, 137), (221, 131)], hexc("#2a0a14"), 1.1, 0.1)
    soft_line(p, [(221, 131), (224, 128)], hexc("#2a0a14"), 1.0, 0.1)
    # eyes: ember irises under heavy lids, sharp arched brows
    almond_eye(p, 224, 108, 11, 7.5, hexc("#ff9a1a"), skin, side=1, glow=hexc("#ff7a1a"))
    almond_eye(p, 196, 108, 7.5, 6.5, hexc("#ff9a1a"), skin, side=-1, glow=hexc("#ff7a1a"))
    tline(p, [(212, 98), (224, 92), (238, 94)], 2.2, 3.4, hair)
    tline(p, [(202, 96), (194, 94), (186, 98)], 2.6, 1.4, hair)
    # ---- hair framing the face and the crown
    fringe = p.shape("poly", curve([(182, 104), (184, 76), (206, 62), (236, 62), (252, 82), (254, 112), (246, 146),
                                    (240, 110), (232, 84), (214, 80), (198, 86), (188, 104)], 5), hair, depth=0.2,
                     line=1.7, tex="fur", tex_amt=0.35)
    soft_line(p, [(196, 72), (222, 66), (244, 78)], hexc("#a04a5a", 140), 3.0, 1.4, fringe)
    rim(p, fringe, hexc("#ff6a3a"), (1, 0.4), 2.4, 0.7)
    lock = p.shape("poly", curve([(244, 118), (252, 150), (248, 186), (258, 214), (244, 200), (238, 160), (240, 128)],
                                 4), hair, depth=0.2, line=1.6, tex="fur", tex_amt=0.35)
    rim(p, lock, hexc("#ff6a3a"), (1, 0.3), 2.2, 0.7)
    for pts, w in (([(236, 68), (256, 38), (282, 14), (300, 8)], 18), ([(198, 66), (188, 38), (176, 18), (164, 10)], 14)):
        horn(p, pts, w, 3, obs, rings=4, spec=0.9, tex="stone", line=1.7)
        p.glow(pts[-1], 12, LAVA, 0.8)
        lava_vein(p, pts[:3], 1.6, None, glow=0.0)
    tiara = p._mask("poly", [(184, 76), (196, 62), (204, 72), (214, 46), (224, 72), (234, 60), (246, 78), (244, 86),
                             (186, 86)])
    p.paint_mask(tiara, gold, depth=0.2, light=1.5, spec=1.0, line=1.6, tex="metal", tex_amt=0.35)
    p.glow((214, 70), 22, LAVA, 0.8)
    tg = p.shape("poly", curve([(214, 58), (221, 70), (214, 82), (207, 70)], 3) + [(214, 58)], hexc("#ff7a1a"),
                 line=1.2, light=1.6, gloss=1.0, rim=0, depth=0.3)
    fill_clip(p, p._mask("poly", [(214, 63), (217, 70), (214, 77), (211, 70)]), LAVA_CORE, tg, blur=0.3)
    # ---- near arm reaching forward with the censer chain
    sleeve = p.shape("poly", curve([(178, 186), (152, 206), (128, 222), (110, 232), (100, 262), (112, 292), (130, 290),
                                    (138, 256), (160, 238), (188, 222)], 5), robe, depth=0.16, line=1.8, **cl)
    vgrad(p, sleeve, robe_d, 230, 292, 0.0, 0.5)
    soft_line(p, [(150, 214), (124, 246), (118, 284)], robe_d[:3] + (220,), 4.0, 2.0, sleeve)
    rim(p, sleeve, EMBER_RIM, (0.6, 1.0), 2.6, 0.6)
    cuff = p._mask("poly", taper([(122, 222), (108, 244)], 12, 14, 2))
    p.paint_mask(cuff, gold, depth=0.3, light=1.45, spec=0.8, line=1.3, rim=0)
    chain(p, (98, 244), (80, 300), 8, hexc("#d8a840"), 8)
    hand = p.union([("ellipse", (90, 228, 112, 250)), ("poly", [(94, 234), (84, 240), (86, 248), (98, 246)])])
    p.paint_mask(hand, skin, depth=0.3, line=1.5, rim=0)
    for i in range(3):
        soft_line(p, [(92 + i * 5, 238), (94 + i * 5, 248)], hexc("#b08888", 200), 1.2, 0.2, hand)
    # ---- the censer: pierced gold dragon-egg with fire and smoke
    wisp(p, [(72, 290), (60, 260), (48, 236), (44, 206), (30, 180)], 20, hexc("#8a7c84"), 0.55)
    for x, y, r in ((62, 266, 12), (48, 236, 10), (40, 208, 8)):
        smoke_puff(p, x, y, r, hexc("#c8bcc2"), 120)
    p.glow((80, 322), 60, LAVA, 0.85)
    cen = p.shape("ellipse", (56, 300, 104, 346), gold, depth=0.2, light=1.45, spec=1.0, line=1.8, tex="metal",
                  tex_amt=0.4)
    for x, y in ((68, 318), (80, 324), (92, 318), (74, 334), (86, 334), (80, 310)):
        p.glow((x, y), 8, LAVA, 0.6)
        fill_clip(p, p._mask("ellipse", (x - 3.2, y - 3.6, x + 3.2, y + 3.6)), hexc("#3a1008"), cen)
        fill_clip(p, p._mask("ellipse", (x - 2.2, y - 2.4, x + 2.2, y + 2.4)), LAVA_HOT, cen)
    p.shape("chord", (60, 288, 100, 316), shade(gold, 0.92), start=180, end=360, depth=0.3, light=1.4, spec=0.8,
            line=1.5)
    p.shape("ellipse", (75, 282, 85, 292), gold, line=1.2, rim=0, spec=0.8)
    p.shape("ellipse", (64, 342, 96, 354), shade(gold, 0.8), depth=0.3, line=1.4, rim=0)
    flame(p, 80, 300, 30, 40, lean=-0.25, strength=0.6)
    # ---- floating embers
    sparks(p, [(40, 60, 2.6), (104, 40, 2.2), (344, 150, 2.4), (360, 230, 2.2), (30, 150, 2.0), (130, 330, 2.0),
               (340, 280, 2.2), (150, 120, 1.8), (282, 250, 1.8), (366, 120, 2.0), (20, 330, 2.0), (120, 180, 1.8)])
    return done(p, 3.0, (60, 350, 360, 382))


@sprite
def dragon_guard():
    """Dragon-cult guard braced behind a tower shield, spear levelled over its rim: a helm shaped like a
    dragon's head with the wearer's eyes burning in the shadow of its jaws, bronze scale armour, obsidian
    plates with gold trim and a red tabard."""
    p = canvas(SIZE, fit=(0.95, 3, 0))
    obs = hexc("#3a3646")
    obs_d = hexc("#26222e")
    obs_l = hexc("#524c60")
    bronze = hexc("#c48a3c")
    gold = GOLD
    red = hexc("#a82a2a")
    bone = hexc("#efe2c4")
    haze(p, (130, 120), 110, 110, hexc("#ff6a1a"), 0.16)
    # ---- far leg, then the near leg
    for hip, knee, foot, c in (((150, 178), (160, 206), (170, 232), obs_d), ((118, 178), (112, 206), (106, 232), obs)):
        lm = p.union([("poly", taperw([hip, knee, foot], [28, 20, 17]))])
        plate(p, lm, c, rim_s=0.5)
        kx, ky = knee
        plate(p, p._mask("ellipse", (kx - 12, ky - 10, kx + 12, ky + 10)), obs_l if c == obs else obs_d, rim_s=0.4)
        fx, fy = foot
        plate(p, p._mask("poly", curve([(fx + 14, fy - 10), (fx + 13, fy + 8), (fx - 20, fy + 8), (fx - 18, fy - 2),
                                        (fx - 2, fy - 10)], 4)), c, rim_s=0.4)
        p.stroke([(fx - 4, fy - 8), (fx - 6, fy + 7)], gold, 1.5)
    # ---- back arm gripping the spear
    ba = p.union([("poly", taperw([(174, 104), (192, 124), (184, 136)], [26, 20, 16]))])
    plate(p, ba, obs_d, rim_s=0.5)
    # ---- tabard and scale skirt
    tab = p.shape("poly", [(112, 168), (160, 168), (164, 214), (152, 208), (146, 222), (136, 210), (126, 222),
                           (118, 208), (108, 214)], red, depth=0.14, line=1.5, tex="cloth", tex_amt=0.6)
    vgrad(p, tab, hexc("#3a0a0a"), 190, 222, 0.0, 0.6)
    skirt = p._mask("poly", curve([(96, 166), (136, 170), (176, 164)], 4) + [(182, 196), (160, 190), (136, 196),
                                                                             (112, 190), (92, 196)])
    p.paint_mask(skirt, bronze, depth=0.14, line=1.5, spec=0.8, tex="metal", tex_amt=0.5)
    scale_rows(p, skirt, (90, 166, 184, 198), shade(bronze, 1.06), size=10, line=0.8)
    rim(p, skirt, EMBER_RIM, (0.6, 1), 2.0, 0.6)
    # ---- torso: bronze scale hauberk, belt
    torso = p._mask("poly", curve([(100, 100), (136, 92), (172, 100), (180, 134), (174, 170), (136, 176), (98, 170),
                                   (94, 134), (100, 100)], 6))
    p.paint_mask(torso, bronze, depth=0.14, line=1.6, spec=0.8, tex="metal", tex_amt=0.5)
    scale_rows(p, torso, (92, 96, 182, 172), shade(bronze, 1.06), size=10, line=0.8)
    spot(p, torso, hexc("#fff0c0"), (116, 118), 16, 0.3)
    rim(p, torso, EMBER_RIM, (0.9, 0.7), 2.4, 0.7)
    p.shape("poly", taper(curve([(94, 164), (136, 172), (178, 162)], 4), 9, 9), hexc("#3a2418"), depth=0.3,
            line=1.3, tex="leather", tex_amt=0.5)
    p.shape("rect", (128, 160, 146, 176), gold, radius=3, depth=0.3, spec=0.9, line=1.2)
    # ---- far pauldron
    pauldron(p, 168, 104, 22, obs_d, obs_d, gold)
    # ---- dragon-head helm: horns and crest behind, skull cap, glowing eyes in the shadow, snout visor
    for pts, w in (([(146, 44), (170, 30), (196, 28), (210, 36)], 11), ([(138, 36), (156, 14), (178, 4), (194, 4)], 12)):
        horn(p, pts, w, 2.2, bone, rings=3, spec=0.5, tex="bone", line=1.5)
    for i, (x, y) in enumerate(((150, 50), (156, 64), (158, 80))):
        p.shape("poly", curve([(x - 4, y - 5), (x + 14 - i * 2, y - 12 + i * 3), (x + 22 - i * 3, y - 2 + i * 2),
                               (x + 2, y + 6)], 3), red, depth=0.3, light=1.3, line=1.2, rim=0)
    cap = p._mask("poly", curve([(96, 62), (100, 38), (122, 24), (146, 28), (160, 48), (162, 76), (152, 98), (126, 104),
                                 (102, 96), (96, 62)], 6))
    plate(p, cap, obs, streak=[(106, 42), (118, 32), (134, 30)])
    face = p._mask("poly", curve([(96, 66), (130, 62), (144, 74), (140, 96), (120, 104), (100, 98), (94, 80)], 5))
    fill_clip(p, face, hexc("#120a10"), cap)
    spot(p, face, hexc("#5a2a14"), (118, 94), 14, 0.5)
    ember_eye(p, 108, 76, 4.6, hexc("#ffa02a"), slant=0.7, inner=1)
    ember_eye(p, 130, 75, 4.2, hexc("#ffa02a"), slant=0.7, inner=-1)
    # cheek guards shaped like the dragon's lower jaw, with teeth
    jaw = p._mask("poly", curve([(152, 70), (148, 96), (126, 110), (98, 110), (86, 100), (100, 98), (124, 98),
                                 (140, 88), (146, 70)], 5))
    plate(p, jaw, obs_l, rim_s=0.6)
    teeth(p, [(96, 99, 4, -6, 1), (106, 99, 4, -7, 1), (116, 98, 4, -6, 1)], bone, line=0.9)
    # snout visor over the brow: a dragon's muzzle with a brow ridge, nostrils and hanging fangs
    snout = p._mask("poly", curve([(152, 44), (136, 30), (116, 28), (102, 38), (84, 42), (66, 46), (54, 48), (48, 56),
                                   (52, 66), (66, 70), (86, 68), (104, 66), (134, 62), (152, 60)], 5))
    plate(p, snout, obs, streak=[(62, 52), (84, 45), (104, 40)])
    teeth(p, [(58, 69, 5, 9, 1), (70, 70, 5, 10, 1), (82, 69, 5, 9, 1), (96, 67, 4.5, 7, 1), (108, 66, 4, 6, 1)],
          bone, line=0.9)
    p.shape("poly", curve([(48, 54), (54, 46), (62, 46), (58, 54)], 3) + [(48, 54)], obs_l, depth=0.3, line=1.1, rim=0,
            clip=snout)
    fill_clip(p, p._mask("ellipse", (51, 52, 59, 57)), hexc("#120a10"), snout)
    brow_r = p._mask("poly", curve([(96, 44), (110, 32), (132, 28), (148, 36), (132, 40), (112, 44)], 4))
    plate(p, brow_r, obs_l, rim_s=0.4, line=1.2)
    p.glow((114, 50), 9, LAVA, 0.7)
    fill_clip(p, p._mask("poly", curve([(104, 50), (114, 45), (126, 49), (114, 54)], 3)), LAVA_HOT, snout)
    fill_clip(p, p._mask("poly", [(114, 45.5), (115.6, 49.5), (114, 53.5), (112.4, 49.5)]), DARK, snout)
    p.stroke(curve([(52, 62), (80, 64), (110, 60), (150, 56)], 4), gold, 1.6)
    for x, y in ((84, 45), (132, 32)):
        p.shape("poly", [(x - 4, y + 2), (x + 3, y - 9), (x + 5, y + 2)], bone, depth=0.3, line=1.0, rim=0)
    for x, y in ((74, 60), (96, 58), (124, 55)):
        p.shape("ellipse", (x - 2, y - 2, x + 2, y + 2), gold, line=0.8, depth=0.4, light=1.6, rim=0, ao=0.4)
    # ---- the spear, levelled forward over the shield
    butt, tip = (238, 162), (8, 44)
    p.shape("poly", taper([butt, tip], 6, 5.2, 2), hexc("#6a4228"), depth=0.35, light=1.35, line=1.3, rim=0,
            tex="wood", tex_amt=0.6)
    dx, dy = tip[0] - butt[0], tip[1] - butt[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    head0 = (tip[0] - ux * 30, tip[1] - uy * 30)
    p.glow(tip, 10, hexc("#ffd8a0"), 0.35)
    leaf(p, head0, (tip[0] + ux * 6, tip[1] + uy * 6), 12, hexc("#d8dfe8"))
    p.shape("poly", taper([lerp(head0, butt, 0.0), (head0[0] - ux * 8, head0[1] - uy * 8)], 9, 9, 2), gold, depth=0.3,
            spec=0.9, line=1.2, rim=0)
    for k in (-1, 0, 1):
        a = (head0[0] - ux * 6, head0[1] - uy * 6)
        p.shape("poly", taper([a, (a[0] + k * 4 + 2, a[1] + 22)], 3.4, 2.0, 2), red, depth=0.3, line=1.0, rim=0)
    # back gauntlet on the shaft
    q = lerp(butt, tip, 0.26)
    gm = p._mask("poly", ellipse_pts(q[0], q[1], 10, 8, 24, rot=-26))
    plate(p, gm, obs_l, rim_s=0.5)
    # ---- the tower shield
    sh = p._mask("poly", curve([(10, 96), (52, 84), (98, 96), (100, 170), (92, 216), (54, 240), (16, 216), (8, 170),
                                (10, 96)], 6))
    plate(p, sh, obs, streak=[(20, 104), (18, 150), (22, 196)], rim_s=0.8)
    inner = p._mask("poly", curve([(18, 104), (52, 94), (90, 104), (92, 168), (86, 208), (54, 230), (22, 208),
                                   (16, 168), (18, 104)], 6))
    rim_band = sub(sh, inner)
    p.paint_mask(rim_band, gold, depth=0.3, light=1.45, spec=0.9, line=1.2, rim=0, tex="metal", tex_amt=0.4)
    for x, y in ((14, 104), (52, 90), (94, 104), (96, 168), (12, 168), (54, 234), (88, 212), (20, 212)):
        p.shape("ellipse", (x - 2.8, y - 2.8, x + 2.8, y + 2.8), shade(gold, 1.1), line=0.8, depth=0.4, light=1.6,
                rim=0, ao=0.4)
    # emblem: a gold sunburst round a slit dragon eye
    ex, ey = 53, 160
    p.glow((ex, ey), 30, LAVA, 0.35)
    sun = []
    for i in range(16):
        a = math.radians(-90 + i * 22.5)
        r = 30 if i % 2 == 0 else 17
        sun.append((ex + r * math.cos(a), ey + r * math.sin(a)))
    p.shape("poly", sun, gold, depth=0.25, light=1.45, spec=0.8, line=1.3, tex="metal", tex_amt=0.3)
    eye_m = p.shape("poly", curve([(ex - 15, ey), (ex, ey - 10), (ex + 15, ey), (ex, ey + 10)], 4) + [(ex - 15, ey)],
                    hexc("#ff8a1a"), depth=0.3, light=1.5, line=1.3, rim=0, gloss=0.7)
    fill_clip(p, p._mask("ellipse", (ex - 7, ey - 7, ex + 7, ey + 7)), LAVA_HOT, eye_m, blur=0.8)
    fill_clip(p, p._mask("poly", curve([(ex, ey - 9), (ex + 2.6, ey), (ex, ey + 9), (ex - 2.6, ey)], 3)), DARK, eye_m)
    for pts in ([(26, 120), (40, 132)], [(72, 196), (84, 204)], [(30, 190), (36, 206)], [(78, 112), (70, 122)]):
        soft_line(p, pts, hexc("#9a96a8", 170), 1.1, 0.2, inner)
    sparks(p, [(40, 30, 1.8), (230, 60, 2.0), (220, 210, 1.8), (120, 230, 1.6), (180, 20, 1.6)])
    return done(p, 2.8, (6, 224, 226, 250))


def leaf(p, base, tip, width, color):
    """Leaf-shaped spear head with a raised midrib and a bright edge."""
    (x0, y0), (x1, y1) = base, tip
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy, ux
    w = width / 2
    pts = curve([(x0, y0), (x0 + dx * 0.35 + nx * w, y0 + dy * 0.35 + ny * w), (x1, y1),
                 (x0 + dx * 0.35 - nx * w, y0 + dy * 0.35 - ny * w), (x0, y0)], 5)
    m = p.shape("poly", pts, color, depth=0.3, light=1.4, spec=1.0, line=1.3, tex="metal", tex_amt=0.4)
    tline(p, [(x0 + ux * 3, y0 + uy * 3), (x1 - ux * 3, y1 - uy * 3)], 1.8, 0.6, shade(color, 0.7), m)
    tline(p, [(x0 + dx * 0.35 - nx * w * 0.8, y0 + dy * 0.35 - ny * w * 0.8), (x1, y1)], 1.2, 0.5,
          hexc("#ffffff", 200), m)
    return m


def talons(p, wrist, angle, color, k=1.0, curl=1):
    """Skeletal clawed hand: a narrow palm and four long jointed fingers fanning out along `angle` (degrees),
    each ending in an ember-hot talon."""
    a0 = math.radians(angle)
    ux, uy = math.cos(a0), math.sin(a0)
    wx, wy = wrist
    palm_c = (wx + ux * 7 * k, wy + uy * 7 * k)
    p.shape("poly", ellipse_pts(palm_c[0], palm_c[1], 8 * k, 6 * k, 20, rot=angle), color, depth=0.3, line=1.3,
            rim=0, tex="stone", tex_amt=0.4)
    for i, spread in enumerate((-48, -18, 10, 38)):
        a = math.radians(angle + spread)
        base = (palm_c[0] + math.cos(a) * 5 * k, palm_c[1] + math.sin(a) * 5 * k)
        ln = (17 if i in (1, 2) else 13) * k
        knuckle = (base[0] + math.cos(a) * ln * 0.55, base[1] + math.sin(a) * ln * 0.55)
        b = a + math.radians(28 * curl)
        tip = (knuckle[0] + math.cos(b) * ln * 0.6, knuckle[1] + math.sin(b) * ln * 0.6)
        p.shape("poly", taperw([base, knuckle, tip], [3.6 * k, 2.8 * k, 0.6]), color, depth=0.3, light=1.3,
                line=1.0, rim=0)
        p.glow(tip, 5 * k, LAVA, 0.6)
        tline(p, [lerp(knuckle, tip, 0.45), tip], 1.8 * k, 0.4, LAVA_HOT)


def dragon_wing(p, shoulder, elbow, wrist, fingers, membrane, bone_c, width=8.0, attach=None, scallop=0.24,
                edge=None, edge_glow=None, veins=True, thumb_c=hexc("#2a2226"), tears=(), line=1.6, inner_glow=None):
    """Dragon wing: a bent arm (shoulder, elbow, wrist), finger bones bowing out from the wrist and a
    scalloped membrane between them ending at `attach` on the body. The membrane sags between the fingers
    (a soft shadow along each bone, a sheen in each panel), with optional veins, a glowing trailing edge and
    ragged tears."""
    attach = attach or lerp(shoulder, fingers[-1], 0.22)
    edge_pts = [fingers[0]]
    prev = fingers[0]
    for f in fingers[1:]:
        mx, my = (prev[0] + f[0]) / 2, (prev[1] + f[1]) / 2
        edge_pts += [(mx + (wrist[0] - mx) * scallop, my + (wrist[1] - my) * scallop), f]
        prev = f
    last = fingers[-1]
    lx, ly = (last[0] + attach[0]) / 2, (last[1] + attach[1]) / 2
    tail_edge = [last, (lx + (wrist[0] - lx) * scallop * 0.7, ly + (wrist[1] - ly) * scallop * 0.7), attach]
    outline = curve(edge_pts, 6) + curve(tail_edge, 6)[1:]
    mem = p._mask("poly", [elbow, wrist] + outline + [shoulder])
    for t in tears:  # ragged notches bitten out of the trailing edge
        mem = sub(mem, p._mask("poly", t))
    p.paint_mask(mem, membrane, depth=0.07, light=1.25, tex="leather", tex_amt=0.45, line=line)
    if inner_glow:
        wide = sub(mem, _pm._erode(mem, int(inner_glow[1] * _pm.SS)))
        fill_clip(p, wide, inner_glow[0], mem, blur=inner_glow[1] * 0.45)
    if edge_glow:
        band = sub(mem, _pm._erode(mem, int(3.2 * _pm.SS)))
        fill_clip(p, band, edge_glow, None, blur=1.2)
        for x, y in along(outline, 12):
            p.glow((x, y), 9, edge_glow, 0.3)
    dark = shade(membrane, 0.55)[:3] + (150,)
    for f in fingers + [attach]:
        soft_line(p, [wrist, f], dark, width * 1.3, 2.4, mem)
    for f0, f1 in zip(fingers, fingers[1:]):
        mx, my = (wrist[0] + (f0[0] + f1[0]) / 2) / 2, (wrist[1] + (f0[1] + f1[1]) / 2) / 2
        soft_line(p, [lerp((mx, my), wrist, 0.3), lerp((mx, my), ((f0[0] + f1[0]) / 2, (f0[1] + f1[1]) / 2), 0.4)],
                  light_tone(membrane, 1.4)[:3] + (70,), width * 1.2, 3.0, mem)
        if veins:
            a = lerp(wrist, f0, 0.45)
            b = lerp(wrist, f1, 0.5)
            c = lerp(lerp(f0, f1, 0.5), wrist, 0.15)
            soft_line(p, [a, lerp(a, c, 0.5), c], shade(membrane, 0.7)[:3] + (150,), 0.9, 0.2, mem)
            soft_line(p, [b, lerp(b, c, 0.6)], shade(membrane, 0.7)[:3] + (130,), 0.8, 0.2, mem)
    if edge:
        p.stroke(outline, edge, 1.6)

    def bow(a, b, k=0.07):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = b[0] - a[0], b[1] - a[1]
        return curve([a, (mx - dy * k, my + dx * k), b], 5)
    for f in fingers:
        p.shape("poly", taper(bow(wrist, f), width * 0.62, width * 0.2, 1), bone_c, depth=0.3, light=1.3, line=1.2,
                rim=0)
    p.shape("poly", taperw([shoulder, elbow], [width * 1.5, width * 1.0]), bone_c, depth=0.3, light=1.3, rim=0.3,
            line=line)
    p.shape("poly", taperw([elbow, wrist], [width * 1.05, width * 0.8]), bone_c, depth=0.3, light=1.3, rim=0.3,
            line=line)
    for (x, y), r in ((elbow, width * 0.62), (wrist, width * 0.58)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), bone_c, depth=0.3, line=1.2, rim=0)
    dx, dy = wrist[0] - elbow[0], wrist[1] - elbow[1]
    ang = math.degrees(math.atan2(dy, dx))
    claw(p, wrist[0], wrist[1], width * 1.5, ang - 20, thumb_c, width=width * 0.6, line=1.0)
    return mem


@sprite
def whelp():
    """Enemy whelp: a scrappy crimson dragonling reared up to look bigger, wings flared wide, one claw raised to
    swipe, jaws open in a snarl with fire in its throat, slit-pupil eyes under a heavy brow and smoke puffing
    from its nostrils. Charcoal horns, spikes and claws, dark back stripes and an angular head keep it far
    from the player's round, friendly companion."""
    p = canvas(SIZE, fit=(0.92, 0, 0))
    body = hexc("#c9331f")
    body_d = hexc("#8a1c18")
    back_c = hexc("#5a1418")
    belly = hexc("#f2963a")
    mem = hexc("#9c2a26")
    horn_c = hexc("#2c2228")
    claw_c = hexc("#1e1618")
    sk = dict(tex="leather", tex_amt=0.5)
    haze(p, (134, 130), 104, 100, hexc("#ff5a1a"), 0.2)
    # ---- far wing, flared up and forward behind the head
    dragon_wing(p, (140, 116), (124, 74), (98, 40), [(66, 10), (34, 26), (22, 60), (40, 90)], shade(mem, 0.72),
                shade(body_d, 0.8), width=6.5, attach=(130, 112), edge_glow=hexc("#ff7a2a", 170), thumb_c=horn_c)
    # ---- near wing, flared up and back
    dragon_wing(p, (164, 126), (192, 92), (184, 48), [(156, 8), (204, 2), (240, 28), (250, 72), (228, 110)],
                mem, body_d, width=8, attach=(176, 140), edge_glow=hexc("#ff8a2a", 200), thumb_c=horn_c)
    # ---- tail curling round to the right, barbed tip, spikes along the top
    tail = [(180, 214), (212, 226), (238, 216), (248, 190), (240, 166)]
    for x, y in along(curve(tail, 8), 11)[1:8]:
        p.shape("poly", [(x - 5, y - 3), (x + 6, y - 11), (x + 5, y + 3)], horn_c, depth=0.3, line=1.1, rim=0)
    tm = p.shape("poly", taperw(tail, [28, 22, 16, 11, 8]), body, depth=0.2, line=1.6, **sk)
    rim(p, tm, EMBER_RIM, (0.6, 1), 2.0, 0.6)
    p.shape("poly", curve([(240, 168), (249, 170), (251, 154), (244, 136), (234, 152), (232, 168)], 4) + [(240, 168)],
            horn_c, depth=0.3, light=1.3, line=1.3, spec=0.6, rim=0)
    for sx in (-1, 1):
        p.shape("poly", [(241 + sx * 4, 162), (241 + sx * 14, 158), (241 + sx * 6, 168)], horn_c, depth=0.3,
                line=1.1, rim=0)
    # ---- far foot, far arm raised behind
    paw(p, 118, 234, 28, body_d, claw_c, tex="leather")
    fa = leg(p, [(128, 128), (114, 110), (100, 96)], [18, 13, 11], body_d, **sk)
    del fa
    for a in (-150, -120, -95):
        r = math.radians(a)
        claw(p, 100 + 4 * math.cos(r), 96 + 4 * math.sin(r), 9, a, claw_c, line=0.9)
    p.shape("ellipse", (92, 88, 108, 104), body_d, depth=0.3, line=1.3, rim=0)
    # ---- back spikes, then the upright pear-shaped body
    for i, (x, y) in enumerate(along(curve([(136, 106), (162, 118), (180, 146), (190, 180)], 8), 11)[1:]):
        hh = 15 - i * 1.3
        p.shape("poly", [(x - 5, y - 4), (x + hh, y - hh * 0.35), (x + 1, y + 7)], horn_c, depth=0.3, light=1.25,
                line=1.3, spec=0.5, rim=0)
    torso = [(114, 110), (148, 104), (176, 124), (192, 162), (194, 200), (180, 226), (146, 234), (116, 226),
             (100, 196), (98, 156), (104, 126), (114, 110)]
    bm = p._mask("poly", curve(torso, 6))
    p.paint_mask(bm, body, depth=0.12, line=1.7, **sk)
    fill_clip(p, p._mask("ellipse", (150, 100, 210, 230)), back_c[:3] + (170,), bm, blur=5)
    for y in range(126, 214, 15):
        x = 176 + (y - 126) * 0.12
        tline(p, [(x + 12, y - 2), (x - 6, y + 4)], 6, 1, back_c, bm, blur=0.6)
    rim(p, bm, EMBER_RIM, (0.9, 0.6), 2.6, 0.75)
    spot(p, bm, light_tone(body, 1.3), (126, 138), 16, 0.35)
    bl = inter(p._mask("poly", taperw([(118, 112), (112, 150), (116, 190), (136, 230)], [22, 34, 40, 40])), bm)
    p.paint_mask(bl, belly, depth=0.2, line=1.3, rim=0, **sk)
    for y in range(124, 232, 10):
        soft_line(p, [(98, y - 2), (120, y + 3), (150, y + 1)], shade(belly, 0.6)[:3] + (220,), 1.5, 0.2, bl)
    # ---- near haunch and foot
    hl = leg(p, [(166, 206), (158, 228), (150, 234)], [30, 20, 18], body,
             extra=[("poly", curve([(146, 178), (178, 168), (200, 188), (198, 220), (172, 232), (148, 222),
                                    (146, 178)], 5))], **sk)
    rim(p, hl, EMBER_RIM, (0.8, 0.8), 2.2, 0.7)
    spot(p, hl, light_tone(body, 1.3), (166, 184), 12, 0.45)
    paw(p, 150, 234, 32, body, claw_c, tex="leather")
    # ---- head: big and angular, horns swept back, jaws open
    for pts, w in (([(90, 60), (112, 40), (138, 32), (156, 36)], 12), ([(76, 54), (84, 28), (100, 10), (116, 6)], 13)):
        horn(p, pts, w, 2.2, horn_c, rings=3, spec=0.6, tex="stone", line=1.4, light=1.2)
        p.glow(pts[-1], 6, LAVA, 0.55)
    for x, y, a in ((102, 108), (106, 94), (104, 80))[:0]:
        pass
    for x, y, a in ((100, 106, 30), (106, 92, 8), (104, 78, -14)):
        r = math.radians(a)
        p.shape("poly", [(x - 4, y - 5), (x + 17 * math.cos(r), y + 17 * math.sin(r)), (x - 3, y + 6)], mem, depth=0.3,
                light=1.3, line=1.2, rim=0)
    p.shape("poly", curve([(84, 116), (56, 130), (30, 138), (18, 132), (32, 122), (62, 114)], 4), body_d, depth=0.25,
            line=1.5, **sk)
    mouth = p._mask("poly", curve([(86, 106), (52, 112), (24, 122), (28, 130), (58, 126), (86, 116)], 4))
    p.glow((48, 120), 22, LAVA, 0.75)
    fill_clip(p, mouth, hexc("#ff6a1a"))
    fill_clip(p, p._mask("ellipse", (30, 114, 72, 126)), LAVA_HOT, mouth, blur=1.0)
    teeth(p, [(32, 131, 3.8, -6, 1), (46, 128, 3.8, -7, 1), (60, 125, 3.6, -6, 1)], hexc("#fff4e0"), line=0.8)
    head = p.union([("ellipse", (40, 48, 116, 120)),
                    ("poly", curve([(60, 64), (30, 74), (10, 86), (2, 98), (10, 111), (42, 113), (76, 111)], 5))])
    p.paint_mask(head, body, depth=0.12, line=1.7, **sk)
    rim(p, head, EMBER_RIM, (0.3, 1), 2.0, 0.6)
    spot(p, head, light_tone(body, 1.35), (68, 68), 15, 0.45)
    fill_clip(p, p._mask("poly", curve([(88, 52), (114, 68), (114, 102), (98, 74)], 4)), back_c[:3] + (180,), head,
              blur=1.5)
    teeth(p, [(16, 110, 3.8, 7, 1), (28, 111, 4, 8, 1), (42, 111, 4.4, 10, 1), (58, 110, 3.8, 7, 1)],
          hexc("#fff4e0"), line=0.8)
    p.shape("poly", curve([(8, 88), (20, 82), (36, 82), (26, 89)], 3) + [(8, 88)], body_d, depth=0.3, line=1.1, rim=0,
            clip=head)
    for x, y in ((13, 91), (24, 88)):
        fill_clip(p, p._mask("ellipse", (x - 2.6, y - 1.7, x + 2.6, y + 1.7)), hexc("#2a0a0a"), head)
    for i in range(3):
        soft_line(p, [(36 + i * 6, 92 + i), (40 + i * 6, 100 + i), (38 + i * 6, 104)], body_d[:3] + (200,), 1.4, 0.3,
                  head)
    angry_eye(p, 70, 82, 12, 12.5, hexc("#ff8a1a"), inner=-1, slant=0.62, sclera=hexc("#ffe27a"), look=-0.3,
              glow=hexc("#ffb040"))
    p.shape("poly", curve([(48, 74), (66, 66), (86, 68), (100, 56), (98, 70), (78, 78), (52, 80)], 4), body_d,
            depth=0.3, light=1.3, line=1.3, rim=0, ao=0.4)
    # ---- near arm raised to swipe, claws out
    na = leg(p, [(118, 140), (96, 160), (74, 146)], [22, 15, 13], body, **sk)
    rim(p, na, EMBER_RIM, (0.4, 1), 1.8, 0.6)
    p.shape("ellipse", (62, 132, 84, 154), body, depth=0.3, line=1.4, rim=0, **sk)
    for a in (-160, -130, -100):
        r = math.radians(a)
        claw(p, 70 + 7 * math.cos(r), 142 + 7 * math.sin(r), 10, a - 8, claw_c, line=0.9)
    # ---- smoke puffing from the nostrils, a flicker of fire at the lips
    for x, y, r, a in ((10, 72, 6, 200), (6, 54, 7.5, 180), (16, 36, 6.5, 160), (8, 18, 5, 140)):
        smoke_puff(p, x, y, r, hexc("#b4aab0"), a)
    flame(p, 24, 130, 12, 18, lean=-0.6, strength=0.5)
    sparks(p, [(214, 120, 1.8), (60, 196, 1.6), (246, 226, 1.8), (36, 170, 1.6), (130, 8, 1.6), (84, 226, 1.6)])
    return done(p, 2.8, (70, 222, 240, 248))


@sprite
def ash_wraith():
    """A spectre of ash and smoke lunging forward: a ragged hood over a void with burning eyes and a jagged
    glowing maw, cracked ashen skin with an ember heart showing through the ribs, long charred arms ending in
    ember-tipped talons, and a body that frays into tattered strips and curling smoke."""
    p = canvas(SIZE, fit=(0.96, 2, 0))
    ashc = hexc("#7c7278")
    ash_l = hexc("#aaa0a4")
    ash_d = hexc("#4c4449")
    char = hexc("#2c2428")
    eyec = hexc("#ffa02a")
    haze(p, (120, 120), 112, 112, hexc("#ff6a2a"), 0.16)
    # ---- smoke curling behind and below
    wisp(p, [(150, 170), (190, 200), (226, 214), (246, 196), (238, 174)], 22, hexc("#8a8088"), 0.55)
    wisp(p, [(130, 190), (150, 222), (190, 240)], 18, hexc("#8a8088"), 0.45)
    # ---- tattered strips streaming back (translucent at the ends)
    for pts, w, a in (([(150, 150), (184, 170), (222, 176), (250, 162)], 18, 140),
                      ([(140, 176), (170, 206), (206, 236), (240, 244)], 18, 160)):
        m = p.shape("poly", taperw(pts, [w] + [w * 0.8] * (len(pts) - 2) + [1.5]), ashc[:3] + (a,), depth=0.2,
                    line=1.2, ink=ash_d[:3] + (a,), rim=0, ao=0, tex="noise", tex_amt=0.5)
        lava_vein(p, pts[:2] + [lerp(pts[1], pts[2], 0.5)], 1.2, m, glow=0.15)
    # ---- far arm raised, talons spread
    fa = leg(p, [(154, 112), (184, 100), (202, 78)], [18, 11, 8], char, tex="stone", tex_amt=0.5)
    lava_vein(p, [(170, 108), (184, 100), (196, 88)], 1.2, fa, glow=0.2)
    talons(p, (204, 74), -70, char, 1.0, 1)
    # ---- body: ragged robe of ash narrowing into a curling tail of smoke
    torso = p._mask("poly", curve([(84, 104), (122, 94), (160, 104), (174, 140), (168, 176), (144, 194), (112, 188),
                                   (96, 162), (86, 130), (84, 104)], 6))
    tailm = p._mask("poly", taperw([(122, 168), (148, 204), (188, 222), (226, 214), (244, 190), (236, 172)],
                                   [52, 42, 30, 18, 8, 2]))
    body = ImageChops.lighter(torso, tailm)
    for x0, y0, ln in ((136, 206, 26), (160, 218, 24), (186, 226, 20), (212, 222, 16)):
        body = ImageChops.lighter(body, p._mask("poly", taperw([(x0 - 6, y0 - 6), (x0 + 4, y0 + ln * 0.5),
                                                                (x0 + 12, y0 + ln)], [12, 7, 1])))
    p.paint_mask(body, ashc, depth=0.12, line=1.6, tex="noise", tex_amt=0.8)
    vgrad(p, body, hexc("#2a1a1a"), 160, 240, 0.0, 0.5)
    rim(p, body, EMBER_RIM, (1, 0.5), 2.4, 0.7)
    for pts in ([(104, 120), (100, 156), (112, 184)], [(150, 118), (160, 150), (152, 182)],
                [(140, 196), (180, 214), (222, 208)]):
        soft_line(p, pts, ash_d[:3] + (200,), 2.6, 1.2, body)
    soft_line(p, [(150, 186), (190, 204), (230, 196)], ash_l[:3] + (120,), 2.4, 1.2, body)
    lava_vein(p, [(168, 208), (196, 214), (220, 206)], 1.4, body, glow=0.2)
    # ember heart glowing through cracked ribs
    p.glow((128, 140), 30, LAVA, 0.75)
    chest = p._mask("ellipse", (106, 116, 152, 166))
    fill_clip(p, chest, hexc("#3a1a14", 200), body, blur=2.5)
    for i, y in enumerate((126, 136, 146, 156)):
        w = 18 - abs(i - 1.5) * 2
        lava_vein(p, [(128 - w, y + 4), (122, y), (134, y), (128 + w, y + 4)], 2.2, body, glow=0.2)
    lava_vein(p, [(128, 118), (128, 162)], 2.4, body, glow=0.3)
    spot(p, body, LAVA_HOT, (128, 140), 8, 0.9)
    # ---- ragged hood: void face, burning eyes, glowing jagged maw
    hood = p.union([("ellipse", (68, 22, 148, 114)),
                    ("poly", curve([(118, 28), (150, 16), (182, 20), (168, 30), (176, 38), (158, 40), (150, 62)], 4))])
    p.paint_mask(hood, ash_l, depth=0.12, line=1.7, tex="noise", tex_amt=0.8)
    rim(p, hood, EMBER_RIM, (1, 0.6), 2.2, 0.6)
    soft_line(p, [(130, 30), (142, 56), (146, 90)], ash_d[:3] + (200,), 3.0, 1.4, hood)
    face = p.shape("poly", curve([(76, 104), (74, 64), (92, 42), (120, 40), (140, 58), (142, 100), (120, 112),
                                  (96, 112), (76, 104)], 5), hexc("#0e080c"), depth=0.2, light=0, line=1.2, rim=0, ao=0)
    spot(p, face, hexc("#4a1a10"), (108, 100), 24, 0.6)
    ember_eye(p, 94, 72, 7.2, eyec, slant=0.75, inner=1)
    ember_eye(p, 124, 70, 6.4, eyec, slant=0.75, inner=-1)
    maw = p._mask("poly", [(92, 90), (98, 94), (104, 90), (110, 95), (116, 90), (122, 94), (128, 89), (126, 100),
                           (120, 104), (114, 99), (108, 105), (102, 99), (96, 102)])
    p.glow((110, 96), 16, LAVA, 0.6)
    fill_clip(p, maw, hexc("#ff8a2a"), face)
    fill_clip(p, p._mask("ellipse", (100, 93, 120, 100)), LAVA_CORE, maw, blur=0.6)
    # tattered hood edge hanging over the brow and shoulders
    p.shape("poly", curve([(70, 110), (68, 60), (90, 34), (124, 32), (148, 52), (152, 96), (160, 118)], 5) +
            [(150, 124), (146, 112), (140, 124), (138, 104), (144, 88), (138, 56), (120, 42), (94, 44), (80, 62),
             (80, 100), (84, 122), (76, 116), (72, 128)], ash_l, depth=0.25, line=1.5, rim=0, tex="noise", tex_amt=0.7)
    for x, y in ((84, 122), (150, 124)):
        spark(p, x, y + 2, 1.4)
    # ---- near arm lunging forward with ember talons
    na = leg(p, [(96, 112), (70, 136), (40, 128)], [24, 14, 10], ash_l, tex="noise", tex_amt=0.7)
    rim(p, na, EMBER_RIM, (0.4, 1), 2.0, 0.6)
    p.shape("poly", curve([(92, 112), (80, 140), (66, 150), (70, 136)], 3) + [(92, 112)], ashc, depth=0.25, line=1.3,
            rim=0, tex="noise", tex_amt=0.6)
    lava_vein(p, [(84, 124), (70, 134), (54, 132)], 1.4, na, glow=0.2)
    talons(p, (40, 128), 180, char, 1.25, -1)
    # ---- choking ash drifting, embers
    for x, y, r in ((30, 60, 4), (212, 40, 3.5), (60, 190, 3), (234, 130, 3), (184, 16, 3), (20, 206, 3.5),
                    (90, 226, 3)):
        ash_flake(p, x, y, r)
    sparks(p, [(50, 30, 1.8), (196, 56, 1.8), (96, 236, 1.6), (240, 210, 2.0), (170, 240, 1.6), (14, 150, 1.6)])
    return done(p, 2.8, (72, 228, 200, 248), fade=(186, 246, 0.25))


def soft_scales(p, clip, box, color, size=10, strength=0.55, seed=1):
    """Painterly overlapping scales: each a soft lit top and a thin shaded lower rim, with no hard ink, so the
    scaling reads as texture rather than a pattern."""
    _, mp, kk = _base(p)
    (x0, y0), (x1, y1) = mp(box[0], box[1]), mp(box[2], box[3])
    size = max(3, int(round(size * kk)))
    rng = random.Random(seed)
    hi = light_tone(color, 1.3)[:3] + (int(150 * strength),)
    lo = shade(color, 0.55)[:3] + (int(220 * strength),)
    hm = Image.new("L", p.img.size, 0)
    lm = Image.new("L", p.img.size, 0)
    dh, dl = ImageDraw.Draw(hm), ImageDraw.Draw(lm)
    S = _pm.SS
    for row, y in enumerate(range(int(y0), int(y1) + size, int(size * 0.62))):
        for x in range(int(x0) - size + (row % 2) * size // 2, int(x1) + size, size):
            jx, jy = rng.uniform(-1, 1) * size * 0.08, rng.uniform(-1, 1) * size * 0.08
            cx, cy = x + jx, y + jy
            r = size * 0.55
            dl.arc(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), 20, 160, fill=255, width=int(S * 1.1))
            dh.pieslice(((cx - r * 0.7) * S, (cy - r * 0.95) * S, (cx + r * 0.5) * S, (cy + r * 0.35) * S), 180, 360,
                        fill=255)
    c, bx = _crop(p, clip, 1)
    hmc = hm.crop(bx).filter(ImageFilter.GaussianBlur(S * size * 0.08))
    lmc = lm.crop(bx).filter(ImageFilter.GaussianBlur(S * 0.3))
    p._fill(ImageChops.multiply(hmc, c), hi, bx[:2], solid=False)
    p._fill(ImageChops.multiply(lmc, c), lo, bx[:2], solid=False)


def scute(p, x, y, w, h, color, edge_c, angle=0.0):
    """Armoured back plate: a ridged pentagon standing on (x, y), leaning by `angle` degrees."""
    pts = [(x - w / 2, y), (x - w * 0.42, y - h * 0.55), (x + w * 0.05, y - h), (x + w * 0.46, y - h * 0.5),
           (x + w / 2, y)]
    pts = rot_pts(pts, x, y, angle)
    m = p.shape("poly", pts, color, depth=0.3, light=1.4, spec=0.8, line=1.4, rim=0, ao=0.3, tex="metal",
                tex_amt=0.5)
    band = sub(m, _pm._erode(m, int(2.2 * _pm.SS)))
    fill_clip(p, band, edge_c[:3] + (170,), m, blur=0.4)
    ridge = rot_pts([(x - w * 0.02, y - h * 0.08), (x + w * 0.04, y - h * 0.9)], x, y, angle)
    tline(p, ridge, 2.2, 0.8, light_tone(color, 1.4)[:3] + (200,), m)
    return m


@sprite
def elder_drake():
    """Elite: a huge wingless bronze drake, ancient and scarred, head lowered to charge. Spiral ram horns and a
    battering brow, a crocodile jaw with fire in the throat and a beard of bone spikes, bronze hide with a
    metallic sheen and green patina, armoured back plates (one still holding a broken spear), braced pillar
    legs with great claws and a spiked club of a tail."""
    p = canvas(SIZE, fit=(0.93, -1, 0))
    bronze = hexc("#c8823a")
    far = hexc("#7e4c26")
    dark = hexc("#5e3418")
    belly = hexc("#ecca8e")
    horn_c = hexc("#efe2c2")
    verd = hexc("#4aa890")
    scar = hexc("#f4cdb2")
    claw_c = hexc("#2a1e18")
    sk = dict(tex="leather", tex_amt=0.55)
    haze(p, (130, 140), 120, 110, hexc("#ff7a2a"), 0.14)
    # ---- tail sweeping round behind, ending in a spiked club
    tail = [(214, 150), (240, 172), (248, 204), (234, 226)]
    p.shape("poly", taperw(tail, [42, 30, 22, 18]), far, depth=0.18, line=1.6, **sk)
    club = p._mask("ellipse", (212, 212, 244, 238))
    p.paint_mask(club, dark, depth=0.25, spec=0.8, line=1.5, tex="metal", tex_amt=0.5)
    for a in (-150, -100, -40, 10, 60):
        r = math.radians(a)
        cx, cy = 228 + 14 * math.cos(r), 225 + 10 * math.sin(r)
        tip = (228 + 26 * math.cos(r), 225 + 20 * math.sin(r))
        p.shape("poly", [(cx - math.sin(r) * 4, cy + math.cos(r) * 4), tip, (cx + math.sin(r) * 4, cy - math.cos(r) * 4)],
                horn_c, depth=0.3, light=1.35, line=1.2, rim=0, spec=0.5)
    # ---- far legs
    leg(p, [(122, 176), (118, 208), (114, 230)], [34, 26, 24], far, **sk)
    paw(p, 114, 233, 32, far, claw_c, tex="leather")
    leg(p, [(200, 170), (208, 206), (202, 230)], [36, 26, 24], far, **sk)
    paw(p, 202, 233, 32, far, claw_c, tex="leather")
    # ---- armoured back plates, one with a broken spear in it
    arc = [(92, 84), (124, 70), (160, 72), (196, 86), (224, 112)]
    for i, (x, y) in enumerate(along(curve(arc, 8), 21)):
        hh = 30 - abs(i - 2) * 3
        scute(p, x, y + 9, 26, hh, bronze, verd, angle=(i - 2) * 13)
    p.shape("poly", taper([(172, 62), (208, 18)], 4.4, 4.0, 2), hexc("#6a4a30"), depth=0.35, line=1.2, rim=0,
            tex="wood", tex_amt=0.6)
    for d in ((-4, -3), (0, -6), (4, -2)):
        tline(p, [(206, 20), (208 + d[0], 18 + d[1])], 2.4, 0.6, hexc("#8a6a48"))
    # ---- body: shoulders humped high, sloping to the hips
    torso = [(70, 106), (100, 80), (142, 72), (186, 82), (218, 104), (234, 138), (230, 172), (210, 194), (170, 202),
             (122, 204), (86, 190), (66, 162), (62, 130), (70, 106)]
    bm = p._mask("poly", curve(torso, 6))
    p.paint_mask(bm, bronze, depth=0.12, line=1.8, spec=0.6, **sk)
    soft_scales(p, bm, (60, 74, 236, 160), bronze, 11, 0.6, seed=1)
    for x, y, r in ((150, 96, 16), (196, 110, 12), (112, 100, 10)):
        spot(p, bm, verd, (x, y), r, 0.35)
    spot(p, bm, hexc("#ffe2a0"), (120, 94), 22, 0.35)
    vgrad(p, bm, hexc("#3a1a0a"), 130, 204, 0.0, 0.4)
    rim(p, bm, EMBER_RIM, (0.4, 1), 2.4, 0.6)
    bl = p._mask("poly", curve([(70, 150), (110, 178), (160, 186), (216, 174)], 5) +
                 curve([(222, 190), (170, 212), (110, 212), (70, 186)], 5))
    bl = inter(bl, bm)
    p.paint_mask(bl, belly, depth=0.2, line=1.3, rim=0, **sk)
    for x in range(88, 222, 12):
        soft_line(p, [(x, 168 + (x - 150) ** 2 * 0.0012), (x + 2, 212)], shade(belly, 0.6)[:3] + (220,), 1.6, 0.2, bl)
    for pts2 in ([(152, 100), (176, 120), (168, 146)], [(190, 108), (206, 132)], [(128, 106), (138, 124)]):
        tline(p, pts2, 4.0, 2.0, scar, bm)
        tline(p, pts2, 1.4, 0.8, shade(scar, 0.6), bm)
    # ---- near hind leg: huge thigh, pillar shin
    thigh = [(170, 118), (206, 110), (234, 130), (238, 168), (222, 190), (192, 192), (172, 172), (168, 140), (170, 118)]
    hl = leg(p, [(210, 176), (212, 206), (212, 230)], [40, 30, 28], bronze, extra=[("poly", curve(thigh, 5))], **sk)
    soft_scales(p, hl, (166, 110, 240, 176), bronze, 10, 0.6, seed=2)
    spot(p, hl, hexc("#ffe2a0"), (196, 126), 16, 0.4)
    vgrad(p, hl, hexc("#3a1a0a"), 190, 232, 0.0, 0.4)
    rim(p, hl, EMBER_RIM, (0.9, 0.6), 2.4, 0.7)
    paw(p, 212, 234, 40, bronze, claw_c, tex="leather")
    # ---- neck and the near front leg, braced forward
    neck = p.paint_mask(p._mask("poly", curve([(62, 112), (100, 92), (126, 118), (118, 168), (84, 176), (56, 152)], 5)),
                        bronze, depth=0.14, line=1.7, **sk)
    soft_scales(p, neck, (54, 92, 128, 150), bronze, 10, 0.55, seed=3)
    p.shape("poly", curve([(58, 150), (82, 164), (108, 170), (86, 178), (60, 166)], 4), belly, depth=0.2, line=1.2,
            rim=0, clip=neck, **sk)
    for pts2 in ([(62, 156), (82, 164)], [(70, 168), (92, 172)]):
        lava_vein(p, pts2, 1.6, neck, glow=0.3)
    fl = leg(p, [(104, 156), (88, 196), (74, 230)], [44, 30, 28], bronze,
             extra=[("poly", curve([(78, 130), (112, 122), (132, 146), (126, 184), (100, 192), (80, 172), (78, 130)], 5))],
             **sk)
    soft_scales(p, fl, (76, 122, 134, 170), bronze, 10, 0.55, seed=4)
    spot(p, fl, hexc("#ffe2a0"), (98, 136), 14, 0.4)
    vgrad(p, fl, hexc("#3a1a0a"), 190, 232, 0.0, 0.4)
    rim(p, fl, EMBER_RIM, (0.9, 0.7), 2.2, 0.6)
    paw(p, 70, 234, 42, bronze, claw_c, tex="leather")
    # ---- head: lowered to charge, heavy and ancient
    hd = Xf.about(p, (80, 130), 1.06, 9, 2)
    horn(hd, [(92, 102), (112, 82), (136, 74), (150, 90), (140, 112), (122, 114)], 20, 5, shade(horn_c, 0.78),
         rings=6, spec=0.4)
    hd.shape("poly", curve([(90, 150), (58, 164), (22, 168), (6, 160), (26, 150), (62, 146)], 5), far, depth=0.22,
             line=1.6, **sk)
    mouth = hd._mask("poly", curve([(92, 140), (56, 146), (14, 150), (18, 158), (58, 158), (92, 150)], 5))
    hd.glow((44, 152), 26, LAVA, 0.85)
    fill_clip(hd, mouth, hexc("#ff6a1a"))
    fill_clip(hd, hd._mask("ellipse", (18, 146, 76, 156)), LAVA_HOT, mouth, blur=1.2)
    teeth(hd, [(22, 160, 4.5, -7, 1), (36, 158, 4.5, -8, 1), (52, 157, 5, -9, 1), (68, 155, 4.5, -7, 1)],
          hexc("#f6eed8"), line=0.9)
    # beard of bone spikes under the chin
    for x, ln in ((34, 14), (48, 20), (62, 24), (76, 20), (88, 14)):
        hd.shape("poly", taper([(x, 164), (x + 3, 164 + ln * 0.6), (x + 1, 164 + ln)], 6, 1.2, 3), horn_c, depth=0.3,
                 light=1.3, line=1.1, rim=0)
    head = hd.union([("ellipse", (40, 88, 116, 150)),
                     ("poly", curve([(60, 98), (30, 106), (8, 116), (0, 130), (6, 144), (48, 148), (92, 146)], 5))])
    hd.paint_mask(head, bronze, depth=0.12, line=1.8, spec=0.5, **sk)
    soft_scales(hd, head, (38, 88, 118, 124), bronze, 8, 0.6, seed=5)
    spot(hd, head, hexc("#ffe2a0"), (60, 112), 16, 0.4)
    spot(hd, head, verd, (100, 104), 10, 0.3)
    rim(hd, head, EMBER_RIM, (0.2, 1), 2.0, 0.6)
    teeth(hd, [(12, 144, 4.2, 8, 1), (24, 145, 4.5, 9, 1), (38, 146, 5, 13, 1), (54, 146, 4.5, 9, 1),
               (70, 145, 4, 7, 1)], hexc("#f6eed8"), line=0.9)
    for x, y in ((8, 128), (18, 124)):
        fill_clip(hd, hd._mask("ellipse", (x - 2.6, y - 1.8, x + 2.6, y + 1.8)), hexc("#2a120a"), head)
    wisp(hd, [(8, 122), (0, 108), (6, 92)], 7, hexc("#8a7c7a"), 0.5)
    brow = hd._mask("poly", curve([(34, 110), (54, 98), (88, 94), (104, 102), (86, 112), (56, 116), (36, 118)], 4))
    hd.paint_mask(brow, dark, depth=0.3, light=1.4, spec=0.8, line=1.4, rim=0, tex="metal", tex_amt=0.5)
    for x, y, hh in ((40, 110, 18), (56, 102, 22)):
        horn(hd, [(x + 4, y), (x - 4, y - hh * 0.6), (x - 14, y - hh)], 10, 2, horn_c, rings=2, spec=0.5, line=1.3)
    angry_eye(hd, 74, 124, 8, 8, hexc("#ffb020"), inner=-1, slant=0.55, sclera=hexc("#ffe9a0"), look=-0.3,
              glow=hexc("#ffb040"))
    tline(hd, [(62, 108), (74, 122), (86, 138)], 3.8, 2.2, scar, head)
    tline(hd, [(62, 108), (74, 122), (86, 138)], 1.2, 0.6, shade(scar, 0.55), head)
    # near ram horn curling round beside the head
    horn(hd, [(96, 100), (114, 80), (140, 76), (152, 96), (138, 118), (118, 116), (112, 102)], 26, 6, horn_c, rings=7,
         spec=0.6)
    sparks(p, [(20, 70, 1.8), (150, 30, 1.8), (244, 110, 1.8), (30, 200, 1.6), (150, 226, 1.6)])
    return done(p, 2.8, (6, 222, 250, 250))


EGG_GOLD = hexc("#e8b44a")
EGG_TEAL = hexc("#2aa89a")
EGG_INK = hexc("#0e3a36")


def egg(p, cx, cy, s, tilt=0.0, ash_dust=0.35):
    """One of the last dragon eggs (the same gold and teal as the companion's egg), dusted with ash."""
    m = p._mask("poly", ellipse_pts(cx, cy + 3 * s, 22 * s, 29 * s, 40, rot=tilt))
    m = ImageChops.lighter(m, p._mask("poly", ellipse_pts(cx + math.sin(math.radians(tilt)) * 10 * s,
                                                          cy - 8 * s, 17 * s, 24 * s, 40, rot=tilt)))
    p.paint_mask(m, EGG_GOLD, depth=0.2, light=1.4, spec=1.0, tex="leather", tex_amt=0.5, line=1.6)
    band = inter(m, p._mask("poly", rot_pts([(cx - 40 * s, cy + 12 * s), (cx + 40 * s, cy + 12 * s),
                                             (cx + 40 * s, cy + 60 * s), (cx - 40 * s, cy + 60 * s)], cx, cy, tilt)))
    p.paint_mask(band, EGG_TEAL, depth=0.25, light=1.35, line=1.0, rim=0, ao=0, ink=EGG_INK)
    for fx, fy, r in ((-8, -12, 3), (9, -2, 3.4), (-12, 2, 2.6), (6, -20, 2.2), (14, -12, 2.0)):
        x, y = rot_pts([(cx + fx * s, cy + fy * s)], cx, cy, tilt)[0]
        p.shape("ellipse", (x - r * s, y - r * s * 0.8, x + r * s, y + r * s * 0.8), EGG_TEAL, depth=0.3, light=1.35,
                line=0.8, rim=0, ao=0, clip=m, ink=EGG_INK)
    x0, y0 = rot_pts([(cx - 11 * s, cy - 18 * s)], cx, cy, tilt)[0]
    x1, y1 = rot_pts([(cx - 15 * s, cy - 4 * s)], cx, cy, tilt)[0]
    soft_line(p, [(x0, y0), (x1, y1)], hexc("#ffffff", 190), 2.4 * s, 0.4, m)
    if ash_dust:
        vgrad(p, m, hexc("#6a6068"), cy - 30 * s, cy + 30 * s, ash_dust, 0.0)
    return m


@sprite
def ashwing():
    """Final boss: Kül Kanat, the last great dragon. A huge ash-grey dragon rearing up with both wings spread,
    their membranes lit from within and edged with embers; a crown of obsidian horns, a proud head held high
    with molten gold eyes and fire behind its teeth, belly plates glowing over a molten core, one claw raised
    against the player. Its tail curls protectively around the last dragon eggs."""
    p = canvas(BOSS, fit=(0.92, 0, -6))
    ash_c = hexc("#443e4c")
    ash_d = hexc("#302b37")
    ash_far = hexc("#26222c")
    ash_l = hexc("#8a8290")
    plate_c = hexc("#8a7466")
    mem = hexc("#4a2632")
    mem_far = hexc("#381c28")
    horn_c = hexc("#221c26")
    bone_c = hexc("#3e3846")
    claw_c = hexc("#1a1418")
    glow_c = hexc("#ff8a2a")
    sk = dict(tex="leather", tex_amt=0.6)
    haze(p, (210, 200), 170, 165, hexc("#ff4a1a"), 0.3)
    haze(p, (120, 100), 100, 90, hexc("#ff8a3a"), 0.16)
    # ---- far wing, spread up and back to the right
    dragon_wing(p, (262, 176), (302, 120), (318, 48), [(296, 4), (348, 8), (380, 56), (382, 128), (354, 188)],
                mem_far, ash_far, width=12, attach=(290, 212), edge_glow=hexc("#ff7a2a", 200), thumb_c=horn_c,
                inner_glow=(hexc("#c83a1a", 120), 16),
                tears=[[(374, 96), (386, 100), (380, 108)], [(362, 160), (374, 158), (370, 170)]])
    # ---- near wing, spread up and forward behind the head (rising from behind the shoulders)
    dragon_wing(p, (224, 176), (200, 100), (152, 34), [(104, 2), (46, 16), (10, 68), (6, 140), (48, 198)],
                mem, bone_c, width=14, attach=(188, 208), edge_glow=hexc("#ff8a2a", 220), thumb_c=horn_c,
                inner_glow=(hexc("#d8461a", 140), 18), tears=[[(2, 100), (16, 104), (6, 112)]])
    # ---- tail: behind the eggs, sweeping round the bottom right with ember spikes
    tail = [(318, 296), (354, 312), (374, 338), (362, 362), (312, 368), (248, 368), (198, 362)]
    for x, y in along(curve(tail, 8), 20)[1:9]:
        p.shape("poly", [(x - 7, y - 8), (x + 5, y - 28), (x + 9, y - 6)], horn_c, depth=0.3, line=1.4, spec=0.6)
        spark(p, x + 5, y - 26, 1.8)
    tm = p.shape("poly", taperw(tail, [54, 44, 34, 26, 20, 14, 7]), ash_c, depth=0.14, line=1.8, **sk)
    soft_scales(p, tm, (190, 290, 384, 384), ash_c, 11, 0.5, seed=5)
    vgrad(p, tm, ash_far, 330, 384, 0.0, 0.4)
    rim(p, tm, EMBER_RIM, (0.2, 1), 3.0, 0.7)
    lava_vein(p, [(326, 304), (354, 322), (368, 344)], 2.0, tm, glow=0.2)
    # ---- far hind leg
    leg(p, [(320, 280), (348, 318), (352, 352)], [40, 26, 22], ash_far, **sk)
    paw(p, 358, 360, 36, ash_far, claw_c, tex="leather")
    # ---- raised far claw, talons spread toward the player (emerging from behind the chest)
    rl = leg(p, [(192, 208), (166, 250), (130, 246), (106, 234)], [42, 28, 20, 17], ash_d, **sk)
    soft_scales(p, rl, (100, 200, 200, 262), ash_d, 9, 0.5, seed=11)
    spot(p, rl, ash_l, (176, 222), 12, 0.35)
    rim(p, rl, EMBER_RIM, (0.4, 1), 2.2, 0.6)
    lava_vein(p, [(176, 244), (150, 250), (126, 244)], 1.4, rl, glow=0.2)
    p.shape("poly", [(168, 256), (160, 270), (176, 260)], horn_c, depth=0.3, line=1.1, rim=0)
    for a, ln in ((-150, 26), (-178, 30), (160, 28), (132, 22)):
        r = math.radians(a)
        base = (106 + 5 * math.cos(r), 236 + 5 * math.sin(r))
        knuckle = (base[0] + ln * 0.5 * math.cos(r), base[1] + ln * 0.5 * math.sin(r))
        tipd = r + math.radians(-30)
        p.shape("poly", taperw([base, knuckle], [9, 6.5]), ash_d, depth=0.3, line=1.3, rim=0)
        claw(p, knuckle[0], knuckle[1], ln * 0.6, math.degrees(tipd) - 8, hexc("#e8dcc8"), width=6, line=1.1)
    p.shape("ellipse", (94, 226, 116, 246), ash_d, depth=0.3, line=1.4, rim=0, **sk)
    # ---- spines along the neck and back
    neck = [(216, 210), (186, 172), (166, 134), (150, 104)]
    for i, (x, y) in enumerate(along(curve(neck, 8), 16)[:8]):
        hh = 30 - i * 2
        p.shape("poly", [(x + 10, y - 22), (x + 30 + hh * 0.3, y - 22 - hh), (x + 28, y - 4)], horn_c, depth=0.3,
                light=1.3, line=1.4, spec=0.6)
        p.glow((x + 30 + hh * 0.3, y - 22 - hh), 6, LAVA, 0.5)
    for i, (x, y) in enumerate(((244, 170), (270, 178), (296, 196), (318, 222), (332, 252))):
        hh = 26 - i * 2
        p.shape("poly", [(x - 8, y + 6), (x + hh * 0.6, y - hh), (x + 9, y + 9)], horn_c, depth=0.3, light=1.3,
                line=1.4, spec=0.6)
        p.glow((x + hh * 0.6, y - hh), 5, LAVA, 0.45)
    # ---- neck
    nm = p.shape("poly", taperw(neck, [88, 74, 62, 56]), ash_c, depth=0.14, line=1.8, **sk)
    soft_scales(p, nm, (120, 90, 256, 230), ash_c, 10, 0.5, seed=6)
    spot(p, nm, ash_l, (176, 130), 18, 0.4)
    rim(p, nm, hexc("#ff9a5a"), (0.6, -0.8), 2.4, 0.5)
    # ---- torso: one flowing outline, deep chest raised high, belly and haunch
    torso = [(196, 176), (234, 164), (272, 174), (306, 198), (330, 236), (340, 276), (328, 310), (298, 324),
             (256, 322), (222, 312), (190, 292), (166, 262), (156, 226), (166, 196), (196, 176)]
    bm = p._mask("poly", curve(torso, 6))
    p.paint_mask(bm, ash_c, depth=0.12, line=1.9, **sk)
    soft_scales(p, bm, (150, 160, 344, 290), ash_c, 12, 0.55, seed=7)
    vgrad(p, bm, ash_far, 250, 324, 0.0, 0.6)
    vgrad(p, bm, ash_far, 240, 344, 0.0, 0.35, x_axis=True)
    spot(p, bm, ash_l, (228, 186), 34, 0.5)
    rim(p, bm, EMBER_RIM, (0.6, 1), 3.2, 0.75)
    body_all = ImageChops.lighter(bm, nm)
    # ---- belly plates from throat to belly, molten light between them over the chest
    p.glow((178, 240), 64, glow_c, 0.5)
    vent = [(128, 118), (150, 146), (170, 184), (176, 226), (182, 266), (196, 296), (214, 312)]
    vm = inter(p._mask("poly", taperw(vent, [22, 30, 38, 44, 44, 34, 14])), body_all)
    p.paint_mask(vm, plate_c, depth=0.16, light=1.3, line=1.4, rim=0, tex="stone", tex_amt=0.55)
    vc = curve(vent, 8)
    for x, y in along(vc, 12)[1:]:
        j = min(range(len(vc)), key=lambda k: (vc[k][0] - x) ** 2 + (vc[k][1] - y) ** 2)
        (ax, ay), (bx, by) = vc[max(0, j - 1)], vc[min(len(vc) - 1, j + 1)]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = 26
        seg = [(x + nx * w, y + ny * w), (x + dx / ln * 3, y + dy / ln * 3), (x - nx * w, y - ny * w)]
        if 176 < y < 300:
            lava_vein(p, seg, 2.4 if 206 < y < 276 else 1.6, vm, glow=0.15)
        else:
            soft_line(p, seg, shade(plate_c, 0.5)[:3] + (220,), 1.6, 0.3, vm)
    spot(p, vm, LAVA_HOT, (176, 240), 22, 0.45)
    lava_vein(p, [(236, 196), (250, 222), (244, 250)], 2.0, bm, glow=0.2)
    # ---- the last eggs, nestled in the curl of the tail
    p.glow((248, 352), 50, hexc("#ffc060"), 0.45)
    egg(p, 280, 352, 0.68, tilt=14, ash_dust=0.5)
    egg(p, 218, 356, 0.6, tilt=-12, ash_dust=0.5)
    egg(p, 248, 352, 0.8, tilt=-2, ash_dust=0.5)
    # ---- near hind leg: crouched, a big muscled thigh, the hock raised, a clawed foot
    thigh = [(266, 238), (300, 226), (334, 240), (348, 274), (340, 306), (318, 320), (290, 318), (270, 300),
             (262, 270), (266, 238)]
    hl = leg(p, [(312, 292), (340, 328), (336, 354)], [42, 26, 24], ash_c, extra=[("poly", curve(thigh, 5))], **sk)
    soft_scales(p, hl, (260, 224, 350, 300), ash_c, 11, 0.5, seed=8)
    vgrad(p, hl, ash_far, 300, 360, 0.0, 0.5)
    spot(p, hl, ash_l, (290, 244), 20, 0.5)
    rim(p, hl, EMBER_RIM, (0.9, 0.6), 3.0, 0.7)
    lava_vein(p, [(282, 256), (302, 274), (296, 298)], 2.0, hl, glow=0.2)
    p.shape("poly", [(340, 322), (358, 318), (344, 334)], horn_c, depth=0.3, line=1.2, rim=0, spec=0.5)
    paw(p, 336, 362, 44, ash_c, claw_c, tex="leather")
    # ---- near front leg planted before the eggs
    fl = leg(p, [(220, 250), (200, 296), (178, 334), (166, 356)], [54, 36, 28, 26], ash_c,
             extra=[("ellipse", (198, 214, 252, 292))], **sk)
    soft_scales(p, fl, (196, 214, 254, 292), ash_c, 11, 0.5, seed=9)
    vgrad(p, fl, ash_far, 290, 360, 0.0, 0.5)
    spot(p, fl, ash_l, (218, 232), 16, 0.5)
    rim(p, fl, EMBER_RIM, (0.9, 0.7), 2.6, 0.7)
    lava_vein(p, [(204, 292), (188, 320)], 1.6, fl, glow=0.2)
    p.shape("poly", [(196, 300), (184, 292), (192, 312)], horn_c, depth=0.3, line=1.1, rim=0)
    paw(p, 160, 362, 50, ash_c, claw_c, tex="leather")
    hd = Xf.about(p, (100, 110), 1.06, 8, -16)
    # ---- head: crown of horns, noble skull, long snout, jaws parted over fire
    for pts, w in (([(132, 96), (168, 70), (208, 56), (240, 60)], 22), ([(136, 112), (174, 102), (208, 104),
                                                                          (230, 114)], 16)):
        hm = horn(hd, pts, w, 2.6, hexc("#221c28"), rings=5, spec=0.6, tex="stone", line=1.7, light=1.15)
        lava_vein(hd, curve(pts, 4)[:9], 1.8, hm, glow=0.12)
        hd.glow(pts[-1], 12, glow_c, 0.7)
    # webbed frill behind the jaw, ember-lit at the edge
    frill = curve([(138, 104), (170, 110), (160, 118), (180, 128), (164, 134), (176, 148), (150, 146), (134, 140)], 3)
    fm = hd.shape("poly", frill, mem, depth=0.25, light=1.35, line=1.4, rim=0, tex="leather", tex_amt=0.4)
    rim(hd, fm, hexc("#ff8a2a"), (1, 0.2), 1.8, 0.9, inset=0.8)
    for q in ((170, 110), (180, 128), (176, 148)):
        hd.shape("poly", taper([(140, 124), q], 4.2, 1.2, 2), bone_c, depth=0.3, line=1.0, rim=0)
    hd.glow((66, 150), 40, glow_c, 0.9)
    jaw = hd.shape("poly", curve([(136, 138), (104, 150), (60, 160), (28, 156), (36, 146), (74, 142), (112, 136)], 5),
                  ash_d, depth=0.22, line=1.7, **sk)
    rim(hd, jaw, EMBER_RIM, (0.2, 1), 2.2, 0.7)
    mouth = hd._mask("poly", curve([(128, 130), (86, 138), (36, 142), (38, 150), (84, 152), (126, 144)], 5))
    fill_clip(hd, mouth, hexc("#ff6a1a"))
    fill_clip(hd, hd._mask("ellipse", (40, 138, 110, 152)), LAVA_HOT, mouth, blur=1.6)
    teeth(hd, [(44, 152, 5.5, -9, 1), (60, 152, 5.5, -10, 1), (78, 150, 6, -11, 1), (96, 148, 5.5, -9, 1)],
          hexc("#f4ead6"), line=1.0)
    head = hd.union([("ellipse", (82, 76, 154, 140)),
                    ("poly", curve([(104, 86), (70, 96), (38, 108), (20, 118), (22, 132), (60, 138), (110, 134),
                                    (136, 128)], 5))])
    hd.paint_mask(head, ash_c, depth=0.12, line=1.9, **sk)
    soft_scales(hd, head, (80, 76, 156, 120), ash_c, 8, 0.5, seed=10)
    spot(hd, head, ash_l, (104, 92), 18, 0.45)
    spot(hd, head, ash_l, (60, 104), 16, 0.35)
    soft_line(hd, [(118, 116), (130, 124), (136, 134)], ash_far[:3] + (170,), 3.0, 1.2, head)
    soft_line(hd, [(86, 112), (104, 120), (124, 122)], ash_far[:3] + (120,), 2.4, 1.2, head)
    rim(hd, head, EMBER_RIM, (0.3, 1), 2.4, 0.8)
    teeth(hd, [(30, 131, 5, 9, 1), (44, 133, 5.5, 10, 1), (60, 134, 6, 14, 1), (78, 134, 5.5, 10, 1), (96, 132, 5, 8, 1)],
          hexc("#f4ead6"), line=1.0)
    # snout ridge scales, nostril with a curl of smoke
    for x, y in along(curve([(30, 112), (60, 100), (92, 90)], 5), 11):
        hd.shape("chord", (x - 5, y - 4, x + 5, y + 4), ash_l, start=180, end=360, depth=0.3, light=1.35, line=1.0,
                rim=0, ao=0, clip=head)
    fill_clip(hd, hd._mask("ellipse", (24, 116, 34, 122)), hexc("#140c10"), head)
    hd.glow((29, 119), 6, glow_c, 0.5)
    wisp(hd, [(22, 112), (14, 94), (20, 74), (10, 56)], 9, hexc("#8a8088"), 0.6)
    lava_vein(hd, [(48, 124), (78, 118), (106, 122), (130, 116)], 1.6, head, glow=0.2)
    # molten gold eye under a heavy brow
    angry_eye(hd, 110, 104, 12.5, 10.5, hexc("#ffb81a"), inner=-1, slant=0.6, sclera=hexc("#fff0a8"), look=-0.35,
              glow=hexc("#ffc040"))
    brow = hd._mask("poly", curve([(88, 96), (104, 90), (126, 90), (144, 80), (140, 94), (124, 100), (100, 102),
                                  (86, 102)], 4))
    hd.paint_mask(brow, ash_d, depth=0.3, light=1.4, spec=0.6, line=1.4, rim=0, ao=0.45, tex="stone", tex_amt=0.5)
    for x, y in ((98, 92), (112, 88), (126, 86)):
        hd.shape("poly", [(x - 4, y + 2), (x + 8, y - 10), (x + 5, y + 3)], horn_c, depth=0.3, line=1.1, rim=0)
    # ---- ash and embers drifting everywhere
    for x, y, r in ((30, 250, 4), (70, 300, 3.5), (350, 250, 3.5), (250, 20, 3), (60, 200, 3), (370, 330, 3),
                    (210, 24, 2.6), (20, 330, 3), (330, 110, 2.6), (130, 330, 2.6), (106, 290, 3)):
        ash_flake(p, x, y, r)
    sparks(p, [(60, 270, 2.2), (110, 320, 2.0), (334, 176, 2.0), (236, 120, 1.8), (16, 196, 2.0), (372, 240, 2.2),
               (96, 196, 1.8), (150, 26, 1.6), (270, 16, 1.8), (40, 40, 1.8)])
    return done(p, 3.1, (40, 350, 380, 382))


SPRITES = {
    "enemies/cultist": cultist,
    "enemies/fire_imp": fire_imp,
    "enemies/ember_hound": ember_hound,
    "enemies/flame_knight": flame_knight,
    "enemies/ember_priestess": ember_priestess,
    "enemies/dragon_guard": dragon_guard,
    "enemies/whelp": whelp,
    "enemies/ash_wraith": ash_wraith,
    "enemies/elder_drake": elder_drake,
    "enemies/ashwing": ashwing,
}


def save(img, rel):
    path = os.path.join(ROOT, "assets", "sprites", rel + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    print("wrote", os.path.relpath(path, ROOT))


def main(names=None):
    for key, fn in SPRITES.items():
        if names and key.split("/")[-1] not in names:
            continue
        save(fn(), key)


if __name__ == "__main__":
    main(sys.argv[1:])

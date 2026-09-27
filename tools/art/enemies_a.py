"""Enemy sprites for the first three dungeons, redrawn at double resolution (docs/art: m7).

    python3 tools/art/enemies_a.py            # all 16
    python3 tools/art/enemies_a.py mimic ...  # only these

writes assets/sprites/enemies/<id>.png: regular enemies and elites at 512 x 512, the bosses (bone_king,
spore_mother, frostbreath) at 768 x 768. Every enemy faces left, toward the player.

Each sprite is designed on the old grid (256, or 384 for bosses) and painted through `Pen`, which scales
coordinates, widths and ink weights by two. `HiPainter` is the soft Painter with its fixed pixel sizes (rim
light, contact shadow, glints, texture grain, ground-shadow blur) scaled up to match, so the look is the
house style, just crisper.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

import painter as _pm  # noqa: E402
from characters import (DARK, NOLINE, WHITE, along, curve, drop, scale_rows, shard, snow,  # noqa: E402
                        snowflake, stitches, taper, teeth)
from painter import (INK, RIM, SS, Painter, _blur, _erode, _scale, _shift, hexc, ink_for,  # noqa: E402
                     light_tone, mix, shade, shadow_tone, texture)

REG, BOSS = 512, 768
LINE = 1.6  # default ink weight on the design grid


# ------------------------------------------------------------------ painter at 2x

class HiPainter(Painter):
    """Soft Painter whose fixed pixel constants are multiplied by `u` (the upscale factor)."""

    def __init__(self, w, h, u, rim_color=None, tex_scale=1.0):
        super().__init__(w, h, soft=True)
        self.u = u
        self.rim_color = rim_color or RIM
        self.tex_scale = tex_scale

    def _texture(self, c, box, kind, amount, color):
        t = texture(kind, self.img.size, int(SS * self.u * self.tex_scale)).crop(box)
        gain = amount * 0.8
        hi = t.point(lambda v: max(0, min(255, int((v - 128) * gain))))
        lo = t.point(lambda v: max(0, min(255, int((128 - v) * gain))))
        self._fill(ImageChops.multiply(hi, c), light_tone(color, 1.35), box[:2], solid=False)
        self._fill(ImageChops.multiply(lo, c), shadow_tone(color, 0.62), box[:2], solid=False)

    def _paint_soft(self, m, color, shadow, light, depth, line, ink, size, k, tex=None, tex_amt=1.0, spec=0.0,
                    rim=None, ao=None, gloss=0.0):
        u = self.u
        U = SS * u
        r = max(1, int(line * SS))
        pad = int(k * 2.5 + 8 * U)
        c, box = self._crop(m, pad)
        o = box[:2]
        transparent = color[3] == 0
        decorative = not shadow and not light
        ao = (0.32 if not decorative and not transparent else 0.0) if ao is None else ao
        if ao and size > 3 * U:
            off = max(1, int(min(k * 0.35, 3 * U) + U * 0.6))
            sh = _blur(_shift(c, off, off), max(U, min(k * 0.6, 5 * U)))
            under = self.img.crop(box).getchannel("A")
            sh = ImageChops.multiply(ImageChops.subtract(sh, c), under)
            self._fill(_scale(sh, ao), (18, 10, 30, 255), o, solid=False)
        if not transparent:
            self._fill(c, color, o)
        if tex and not transparent:
            self._texture(c, box, tex, tex_amt, color)
        if shadow and not transparent:
            feather = max(1, k * 0.2)
            core = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, -k, -k), feather)))
            self._fill(core, shadow_tone(color, shadow), o, solid=False)
            k2 = int(k * 2.2) + 1
            broad = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, -k2, -k2), k2 * 0.8)))
            self._fill(_scale(broad, 0.5), shadow_tone(color, (1 + shadow) / 2), o, solid=False)
        if light and not transparent:
            kh = max(1, k // 2)
            hl = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, kh, kh), max(1, kh * 0.45))))
            self._fill(_scale(hl, 0.9), light_tone(color, light), o, solid=False)
            if size > 10 * U:
                k3 = int(k * 1.6) + 1
                bloom = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, k3, k3), k3 * 0.9)))
                self._fill(_scale(bloom, 0.28), light_tone(color, (1 + light) / 2), o, solid=False)
        rim = (0.5 if shadow and size > 12 * U else 0.0) if rim is None else rim
        inner = _erode(c, r) if (line or rim or spec) else c
        if rim and not transparent:
            rr = max(1, int(U * 1.3))
            band = ImageChops.subtract(inner, _shift(inner, -rr, -rr))
            self._fill(_scale(_blur(band, U * 0.4), rim), mix(light_tone(color, 1.4), self.rim_color, 0.55), o,
                       solid=False)
        if spec and not transparent:
            s = max(1, int(min(k * 0.6, 3 * U)))
            band = ImageChops.subtract(inner, _shift(inner, s, s))
            bx0, by0, bx1, by1 = c.getbbox() or (0, 0, 1, 1)
            fall = Image.new("L", c.size, 0)
            fd = ImageDraw.Draw(fall)
            cx = bx0 + (bx1 - bx0) * 0.3
            cy = by0 + (by1 - by0) * 0.3
            rx, ry = (bx1 - bx0) * 0.55, (by1 - by0) * 0.55
            fd.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
            fall = _blur(fall, max(rx, ry) * 0.35)
            band = ImageChops.multiply(_blur(band, U * 0.5), fall)
            self._fill(_scale(band, min(1.0, spec)), (255, 255, 255, 255), o, solid=False)
        if gloss and not transparent:
            bx0, by0, bx1, by1 = c.getbbox() or (0, 0, 1, 1)
            bw, bh = bx1 - bx0, by1 - by0
            g = Image.new("L", c.size, 0)
            ImageDraw.Draw(g).ellipse((bx0 + bw * 0.2, by0 + bh * 0.14, bx0 + bw * 0.46, by0 + bh * 0.34), fill=255)
            g = ImageChops.multiply(_blur(g, U * 0.6), inner)
            self._fill(_scale(g, min(1.0, gloss)), (255, 255, 255, 255), o, solid=False)
        if line:
            if ink == INK and not transparent:
                ink = ink_for(color)
            thin = _erode(c, max(1, int(r * 0.75)))
            d = max(1, int(r * 0.7))
            e = ImageChops.darker(thin, _shift(thin, -d, -d))
            self._fill(ImageChops.subtract(c, e), ink, o, solid=True)

    # ---- extra effects (pixel coordinates; Pen maps the grid onto them)
    def glow_clip(self, center, radius, color, strength, clip):
        """A soft radial glow that stays inside `clip` (light inside a translucent body)."""
        cx, cy = center[0] * SS, center[1] * SS
        blur = radius * SS / 6
        half = int(radius * SS + blur * 3 + 2)
        layer = Image.new("RGBA", (half * 2, half * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for i in range(14, 0, -1):
            t = i / 14
            a = int(255 * strength * (1 - t) ** 1.3)
            rr = radius * t * SS
            d.ellipse((half - rr, half - rr, half + rr, half + rr), fill=color[:3] + (a,))
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        x, y = int(cx) - half, int(cy) - half
        full = Image.new("L", self.img.size, 0)
        full.paste(layer.getchannel("A"), (x, y))
        a = ImageChops.multiply(full, clip)
        self._fill(a, color[:3] + (255,), (0, 0), solid=False)

    def vgrad(self, mask, top, bottom, y0, y1, strength=1.0):
        """Vertical colour ramp from `top` (at y0) to `bottom` (at y1) inside `mask`, blended by strength."""
        y0, y1 = int(y0 * SS), int(y1 * SS)
        w, h = self.img.size
        ramp = Image.linear_gradient("L").resize((1, max(1, y1 - y0)))
        g = Image.new("L", (1, h), 0)
        g.paste(ramp, (0, max(0, y0)) if y0 >= 0 else (0, 0))
        g.paste(255, (0, max(0, y1), 1, h))
        g = g.resize((w, h))
        a = _scale(mask, strength)
        self._fill(ImageChops.multiply(ImageChops.invert(g), a), top, (0, 0), solid=False)
        self._fill(ImageChops.multiply(g, a), bottom, (0, 0), solid=False)

    def mist(self, box, color, alpha=120, blur=6.0):
        """A blurred ellipse of mist or spore haze (not part of the silhouette)."""
        m = self._mask("ellipse", box)
        c, bb = self._crop(m, int(blur * SS * 3) + 2)
        self._fill(_scale(_blur(c, blur * SS), alpha / 255), color[:3] + (255,), bb[:2], solid=False)

    def finish(self, outline=6, outline_color=INK, ground_shadow=None, grade=None):
        u = self.u
        big = self._grade(self.img, 1.0)
        out = big.resize((self.w, self.h), Image.LANCZOS)
        if outline:
            solid = ImageChops.darker(self.solid, big.getchannel("A")).point(lambda v: 255 if v > 90 else 0)
            grown = _pm._dilate(solid, outline * SS).resize((self.w, self.h), Image.LANCZOS)
            sil = Image.new("RGBA", out.size, outline_color)
            sil.putalpha(grown)
            out = Image.alpha_composite(sil, out)
        if ground_shadow:
            x0, y0, x1, y1 = ground_shadow
            base = Image.new("RGBA", out.size, (0, 0, 0, 0))
            ImageDraw.Draw(base).ellipse((x0, y0, x1, y1), fill=(12, 6, 18, 70))
            base = base.filter(ImageFilter.GaussianBlur(5 * u))
            core = Image.new("RGBA", out.size, (0, 0, 0, 0))
            cw, ch = (x1 - x0) * 0.2, (y1 - y0) * 0.22
            ImageDraw.Draw(core).ellipse((x0 + cw, y0 + ch, x1 - cw, y1 - ch), fill=(12, 6, 18, 110))
            base = Image.alpha_composite(base, core.filter(ImageFilter.GaussianBlur(3 * u)))
            out = Image.alpha_composite(base, out)
        return out


class Pen:
    """Maps a design grid onto a HiPainter: coordinates, widths, radii and ink weights all scale by k."""

    def __init__(self, grid, px, rim=None, tex_scale=1.0, fit=None, rot=None):
        """fit=(s, cx, ground) shrinks or grows the design by s about (cx, ground), to fit it on the canvas;
        rot=(degrees, cx, cy) turns it about (cx, cy) first (ellipses and rects then become polygons)."""
        self.k = px / grid
        self.grid = grid
        self.p = HiPainter(px, px, self.k, rim, tex_scale)
        s, cx, gy = fit or (1.0, 0, 0)
        self.s, self.ox, self.oy = s, cx - cx * s, gy - gy * s
        self.rot = None
        if rot and rot[0]:
            a = math.radians(rot[0])
            self.rot = (math.cos(a), math.sin(a), rot[1], rot[2])

    # -- mapping
    def pt(self, x, y):
        if self.rot:
            c, sn, rx, ry = self.rot
            x, y = rx + (x - rx) * c - (y - ry) * sn, ry + (x - rx) * sn + (y - ry) * c
        return ((self.ox + x * self.s) * self.k, (self.oy + y * self.s) * self.k)

    def _conv(self, kind, pts, kw):
        """Under rotation, boxes (ellipse, rect, chord, pie) are turned into polygons in grid space."""
        if not self.rot or kind not in ("ellipse", "rect", "chord", "pie"):
            return kind, pts, kw
        kw = dict(kw)
        x0, y0, x1, y1 = pts
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        if kind == "ellipse":
            return "poly", ell_pts(cx, cy, rx, ry, step=6), kw
        if kind == "rect":
            r = min(kw.pop("radius", 0), rx, ry)
            out = []
            for (qx, qy), a0 in (((x1 - r, y0 + r), 270), ((x1 - r, y1 - r), 0), ((x0 + r, y1 - r), 90),
                                 ((x0 + r, y0 + r), 180)):
                out += ell_pts(qx, qy, r, r, a0, a0 + 90, step=15) if r > 0 else [(qx, qy)]
            return "poly", out, kw
        a0, a1 = kw.pop("start"), kw.pop("end")
        arc = ell_pts(cx, cy, rx, ry, a0, a1, step=6)
        return "poly", arc + ([(cx, cy)] if kind == "pie" else []), kw

    def _pts(self, pts):
        if isinstance(pts[0], (tuple, list)):
            return [self.pt(x, y) for x, y in pts]
        out = []
        for i in range(0, len(pts), 2):
            out += list(self.pt(pts[i], pts[i + 1]))
        return out

    def _kw(self, kw, line=True):
        kw = dict(kw)
        for key in ("width", "radius"):
            if key in kw:
                kw[key] = kw[key] * self.k * self.s
        if line:
            kw["line"] = kw.get("line", LINE) * self.k
        return kw

    # -- painter api
    def shape(self, kind, pts, color, **kw):
        kind, pts, kw = self._conv(kind, pts, kw)
        return self.p.shape(kind, self._pts(pts), color, **self._kw(kw))

    def flat(self, kind, pts, color, **kw):
        kind, pts, kw = self._conv(kind, pts, kw)
        return self.p.flat(kind, self._pts(pts), color, **self._kw(kw, line=False))

    def _mask(self, kind, pts, **kw):
        kind, pts, kw = self._conv(kind, pts, kw)
        return self.p._mask(kind, self._pts(pts), **self._kw(kw, line=False))

    def union(self, items):
        out = []
        for it in items:
            kind, pts, kw = self._conv(it[0], it[1], it[2] if len(it) > 2 else {})
            out.append((kind, self._pts(pts), self._kw(kw, line=False)))
        return self.p.union(out)

    def paint_mask(self, m, color, **kw):
        return self.p.paint_mask(m, color, **self._kw(kw))

    def stroke(self, pts, color, width, soft=0.0):
        return self.p.stroke(self._pts(pts), color, max(0.8, width * self.k * self.s), soft * self.k * self.s)

    def glow(self, center, radius, color, strength=0.8):
        return self.p.glow(self.pt(*center), radius * self.k * self.s, color, strength)

    def sparkle(self, center, r, color=WHITE, glow=True):
        return self.p.sparkle(self.pt(*center), r * self.k * self.s, color, glow)

    def tex(self, mask, kind, amount=1.0, color=(128, 128, 128, 255)):
        return self.p.tex(mask, kind, amount, color)

    def shadow_on(self, mask, strength=0.35, offset=2.0, blur=3.0, color=(18, 10, 30, 255)):
        return self.p.shadow_on(mask, strength, offset * self.k * self.s, blur * self.k * self.s, color)

    # -- extras
    def glow_clip(self, center, radius, color, strength, clip):
        return self.p.glow_clip(self.pt(*center), radius * self.k * self.s, color, strength, clip)

    def vgrad(self, mask, top, bottom, y0, y1, strength=1.0):
        return self.p.vgrad(mask, top, bottom, self.pt(0, y0)[1], self.pt(0, y1)[1], strength)

    def mist(self, box, color, alpha=120, blur=6.0):
        x0, y0, x1, y1 = box
        cx, cy = self.pt((x0 + x1) / 2, (y0 + y1) / 2)
        hw, hh = (x1 - x0) / 2 * self.k * self.s, (y1 - y0) / 2 * self.k * self.s
        return self.p.mist((cx - hw, cy - hh, cx + hw, cy + hh), color, alpha, blur * self.k * self.s)

    def fill_mask(self, m, color, solid=False):
        self.p._fill(m, color, (0, 0), solid=solid)

    def finish(self, ground_shadow, outline=None):
        x0, y0, x1, y1 = ground_shadow
        k, sc = self.k, self.s
        gs = ((self.ox + x0 * sc) * k, (self.oy + y0 * sc) * k, (self.ox + x1 * sc) * k, (self.oy + y1 * sc) * k)
        return self.p.finish(outline=outline or (6 if self.p.w <= 512 else 7), ground_shadow=gs)


def sub(a, b):
    return ImageChops.subtract(a, b)


def mul(a, b):
    return ImageChops.multiply(a, b)


def add(a, b):
    return ImageChops.lighter(a, b)


# ------------------------------------------------------------------ shared drawing helpers (grid units)

def norm(dx, dy):
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def tufts(path, amp, step, side=1, lean=0.45, jitter=0.25, seed=1):
    """A zigzag band of fur tufts along `path`: a polygon whose inner edge follows the path pulled in by half
    the amplitude and whose outer edge spikes out by `amp` (side 1 = left of the direction of travel), each
    spike leaning back along the path by `lean`."""
    rng = random.Random(seed)
    pts = along(curve(path, 8) if len(path) > 2 else path, step)
    if len(pts) < 2:
        return None
    outer, inner = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        tx, ty = norm(b[0] - a[0], b[1] - a[1])
        nx, ny = ty * side, -tx * side
        inner.append((x - nx * amp * 0.5, y - ny * amp * 0.5))
        outer.append((x, y))
        if i < len(pts) - 1:
            nxt = pts[i + 1]
            mx, my = (x + nxt[0]) / 2, (y + nxt[1]) / 2
            h = amp * (1 + rng.uniform(-jitter, jitter))
            outer.append((mx + nx * h + tx * h * lean, my + ny * h + ty * h * lean))
    return outer + inner[::-1]


def limb_poly(pts, widths, steps=6):
    """Outline of a limb through pts with a width at every control point (bulging muscles, slim joints)."""
    c = curve(pts, steps)
    n = len(c)
    seg = len(pts) - 1
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
        tx, ty = norm(b[0] - a[0], b[1] - a[1])
        f = i / max(1, n - 1) * seg
        j = min(seg - 1, int(f))
        t = f - j
        t = t * t * (3 - 2 * t)
        w = (widths[j] + (widths[j + 1] - widths[j]) * t) / 2
        left.append((x - ty * w, y + tx * w))
        right.append((x + ty * w, y - tx * w))
    return left + right[::-1]


def claw(p, x, y, length, angle, width=None, color=hexc("#f4ecd8"), line=1.0):
    """A curved claw rooted at (x, y), pointing along `angle` (degrees, 90 = down), hooking downward."""
    width = width or length * 0.5
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    tip = (x + ux * length + nx * length * 0.25, y + uy * length + ny * length * 0.25)
    pts = curve([(x + nx * width / 2, y + ny * width / 2),
                 (x + ux * length * 0.6 + nx * width * 0.45, y + uy * length * 0.6 + ny * width * 0.45), tip,
                 (x + ux * length * 0.5 - nx * width * 0.05, y + uy * length * 0.5 - ny * width * 0.05),
                 (x - nx * width / 2, y - ny * width / 2)], 4)
    p.shape("poly", pts, color, depth=0.35, light=1.35, line=line, rim=0, ao=0.25, spec=0.5)


def fang(p, x, y, w, h, color=hexc("#fbf6e6"), d=1, curl=0.0, line=1.0):
    """A curved fang hanging from (x, y) (d=1 down, -1 up)."""
    pts = curve([(x - w / 2, y), (x - w * 0.35 + curl * h * 0.3, y + h * 0.55 * d), (x + curl * h * 0.5, y + h * d),
                 (x + w * 0.2 + curl * h * 0.3, y + h * 0.5 * d), (x + w / 2, y)], 4)
    p.shape("poly", pts, color, depth=0.3, light=1.3, line=line, rim=0, ao=0.2, spec=0.3)


def mean_eye(p, cx, cy, rx, ry, iris, skin, brow_tilt=0.35, lid=0.3, look=(-0.5, 0.1), pupil="round",
             brow=None, line=1.2, glow=None):
    """An angry cartoon eye facing left: a white, a big iris, a pupil and a catchlight, with a heavy upper lid
    sliding down toward the inner (right) corner so it scowls, and an optional brow above."""
    if glow:
        p.glow((cx, cy), max(rx, ry) * 2.2, glow, 0.55)
    white = p.shape("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry), hexc("#fbf6ea"), shadow=0.82, light=0,
                    depth=0.25, line=line, rim=0, ao=0.25)
    ix, iy = cx + look[0] * rx * 0.4, cy + look[1] * ry * 0.4
    ir = min(rx, ry) * 0.78
    p.shape("ellipse", (ix - ir, iy - ir * 1.08, ix + ir, iy + ir * 1.08), iris, shadow=0.55, light=1.5, depth=0.3,
            line=line * 0.7, ink=shade(iris, 0.35), rim=0, ao=0, clip=white)
    if pupil == "slit":
        p.flat("ellipse", (ix - ir * 0.22, iy - ir * 0.95, ix + ir * 0.22, iy + ir * 0.95), DARK)
    else:
        pr = ir * 0.48
        p.flat("ellipse", (ix - pr, iy - pr * 1.08, ix + pr, iy + pr * 1.08), DARK)
    p.flat("ellipse", (ix - ir * 0.62, iy - ir * 0.72, ix - ir * 0.12, iy - ir * 0.22), WHITE)
    p.flat("ellipse", (ix + ir * 0.22, iy + ir * 0.3, ix + ir * 0.48, iy + ir * 0.56), hexc("#ffffff", 190))
    # the scowling lid: a slanted chord of skin over the top of the eye, lower at the inner (right) side
    if lid:
        top_l = cy - ry - 2
        drop_l = ry * 2 * lid
        lp = [(cx - rx - 2, top_l), (cx + rx + 2, top_l), (cx + rx + 2, cy - ry + drop_l * (1 + brow_tilt)),
              (cx - rx - 2, cy - ry + drop_l * (1 - brow_tilt))]
        lm = mul(p._mask("poly", lp), white)
        p.paint_mask(lm, skin, depth=0.3, light=1.1, line=0, rim=0, ao=0)
        p.stroke([(cx - rx - 1, cy - ry + drop_l * (1 - brow_tilt)), (cx + rx + 1, cy - ry + drop_l * (1 + brow_tilt))],
                 DARK, line * 1.7)
    if brow:
        bc, bw = brow
        p.shape("poly", [(cx - rx * 1.25, cy - ry * (1.35 - brow_tilt * 0.3)), (cx + rx * 1.2, cy - ry * (0.95 - brow_tilt)),
                         (cx + rx * 1.1, cy - ry * (0.95 - brow_tilt) - bw), (cx - rx * 1.2, cy - ry * (1.35 - brow_tilt * 0.3) - bw * 1.2)],
                bc, depth=0.35, line=line * 0.9, rim=0, ao=0.25)
    return white


def glowing_eye(p, cx, cy, rx, ry, color, core=hexc("#fff8d8"), socket=hexc("#150c14"), strength=0.9,
                slant=0.35, lidc=None):
    """A glowing eye in a dark socket, with a slanted scowl cut across its top (inner corner lower)."""
    if socket:
        p.shape("ellipse", (cx - rx * 1.25, cy - ry * 1.2, cx + rx * 1.25, cy + ry * 1.25), socket, **NOLINE)
    p.glow((cx, cy), max(rx, ry) * 2.8, color, strength)
    e = p._mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    if slant:
        e = sub(e, p._mask("poly", [(cx - rx * 2, cy - ry * 2), (cx + rx * 2, cy - ry * 2),
                                     (cx + rx * 2, cy - ry * (0.25 - slant * 1.2)), (cx - rx * 2, cy - ry * (1.0 + slant * 0.2))]))
    p.fill_mask(e, mix(color, core, 0.25))
    p.fill_mask(mul(e, p._mask("ellipse", (cx - rx * 0.6, cy - ry * 0.45, cx + rx * 0.45, cy + ry * 0.55))), core)
    return e


def ell_pts(cx, cy, rx, ry, a0=0, a1=360, rot=0.0, step=6):
    """Points along an ellipse arc from a0 to a1 degrees, the whole ellipse rotated by `rot` degrees."""
    r = math.radians(rot)
    cr, sr = math.cos(r), math.sin(r)
    out = []
    n = max(2, int(abs(a1 - a0) / step) + 1)
    for i in range(n):
        t = math.radians(a0 + (a1 - a0) * i / (n - 1))
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return out


def bone_mask(p, a, b, w, knob=1.45):
    """Mask of a limb bone from a to b: a waisted shaft with a double knuckle (two condyles) at each end."""
    (x0, y0), (x1, y1) = a, b
    ux, uy = norm(x1 - x0, y1 - y0)
    nx, ny = -uy, ux
    L = math.hypot(x1 - x0, y1 - y0)
    shaft = limb_poly([a, (x0 + ux * L * 0.5, y0 + uy * L * 0.5), b], [w * 1.05, w * 0.72, w * 1.05], 4)
    items = [("poly", shaft)]
    r = w * knob * 0.36
    for (x, y), s in ((a, 1), (b, -1)):
        for side in (-1, 1):
            cx, cy = x + nx * side * w * 0.3 + ux * s * r * 0.2, y + ny * side * w * 0.3 + uy * s * r * 0.2
            items.append(("ellipse", (cx - r, cy - r, cx + r, cy + r)))
    return p.union(items)


def limb_bone(p, a, b, w, color, **kw):
    m = bone_mask(p, a, b, w)
    kw.setdefault("tex", "bone")
    kw.setdefault("tex_amt", 0.6)
    p.paint_mask(m, color, depth=kw.pop("depth", 0.3), light=kw.pop("light", 1.3), rim=kw.pop("rim", 0.35), **kw)
    return m


def bony_hand(p, wrist, angle, s, color, fingers=4, curl=0.6):
    """A skeletal hand: a knobbly palm at `wrist` and jointed finger bones fanning along `angle` (degrees),
    curling by `curl`."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    px, py = wrist[0] + ux * s * 0.5, wrist[1] + uy * s * 0.5
    p.shape("ellipse", (px - s * 0.55, py - s * 0.5, px + s * 0.55, py + s * 0.5), color, depth=0.3, tex="bone",
            tex_amt=0.5, rim=0)
    for i in range(fingers):
        off = (i - (fingers - 1) / 2) * s * 0.34
        bx, by = px + ux * s * 0.4 + nx * off, py + uy * s * 0.4 + ny * off
        c1 = (bx + ux * s * 0.45, by + uy * s * 0.45)
        c2 = (c1[0] + (ux * (1 - curl) + nx * curl * 0.2 - ux * 0) * s * 0.35 + (-uy if curl else 0) * 0,
              c1[1] + (uy * (1 - curl) + curl * 0.9) * s * 0.35)
        for q0, q1, w in (((bx, by), c1, s * 0.2), (c1, c2, s * 0.17)):
            p.shape("line", [q0, q1], color, width=w, depth=0.3, line=0.9, rim=0, ao=0.2)


def mist_puffs(p, puffs, color, alpha=110):
    for x, y, r in puffs:
        p.mist((x - r, y - r * 0.7, x + r, y + r * 0.7), color, alpha, r * 0.35)


def spores(p, pts, color, core=hexc("#f4ffe8")):
    for x, y, r in pts:
        p.glow((x, y), r * 3.6, color, 0.75)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), core)


def ring_mask(p, box, t):
    x0, y0, x1, y1 = box
    return sub(p._mask("ellipse", box), p._mask("ellipse", (x0 + t, y0 + t, x1 - t, y1 - t)))


# ------------------------------------------------------------------ dungeon 1: Rotten Cellar

def rat_hand(p, x, y, angle, s, color, claw_c):
    """A rat's clawed hand at (x, y): a small palm and four thin fingers with long hooked claws along `angle`."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    p.shape("ellipse", (x - s * 0.45, y - s * 0.4, x + s * 0.45, y + s * 0.4), color, depth=0.3, light=1.3)
    for i in range(4):
        off = (i - 1.5) * s * 0.26
        bx, by = x + ux * s * 0.3 + nx * off, y + uy * s * 0.3 + ny * off
        tx, ty = bx + ux * s * 0.55 + nx * off * 0.3, by + uy * s * 0.55 + ny * off * 0.3
        p.shape("poly", taper([(bx, by), (tx, ty)], s * 0.2, s * 0.15), color, depth=0.3, line=0.9, rim=0, ao=0.2)
        claw(p, tx, ty, s * 0.45, angle + 25, s * 0.16, claw_c, 0.8)


def cellar_rat():
    """A mangy cellar rat reared up on its hind legs, hunched and hissing: clawed hands raised, a spiky back, a torn
    ear, one glowing red eye under a heavy brow, yellow buck teeth, a stitched scar and a long ringed tail
    (faces left)."""
    fur = hexc("#8c7468")
    fur_d = hexc("#5e4a46")
    belly = hexc("#c9b5a3")
    pink = hexc("#e48f98")
    claw_c = hexc("#f1e6d0")
    FL = 1.4
    p = Pen(256, REG, fit=(0.92, 162, 238))
    # ---- the tail: long, tapered, ringed, curling up behind
    tail = [(186, 214), (220, 222), (244, 200), (246, 164), (230, 136), (232, 112)]
    p.shape("poly", taper(tail, 15, 3, 10), pink, depth=0.3, light=1.3, tex="leather", tex_amt=0.5, spec=0.3)
    for x, y in along(curve(tail, 10), 7)[1:-3]:
        p.stroke([(x - 4, y - 1), (x + 4, y + 1)], shade(pink, 0.62), 1.0)
    # ---- far arm raised high, claws out
    far = shade(fur, 0.74)
    p.shape("poly", limb_poly([(112, 110), (74, 76), (42, 50)], [22, 15, 12]), far, depth=0.25, tex="fur",
            tex_amt=0.6, line=FL)
    rat_hand(p, 36, 44, -140, 18, shade(pink, 0.82), shade(claw_c, 0.85))
    # ---- far foot
    p.shape("poly", curve([(176, 226), (150, 228), (130, 232), (128, 238), (178, 238)], 4), shade(pink, 0.78),
            depth=0.3)
    # ---- the body reared up: pear-shaped, leaning forward, a mangy spiky back
    back = [(112, 84), (146, 96), (176, 122), (194, 158), (200, 196)]
    body = p.union([("ellipse", (110, 118, 204, 228)), ("ellipse", (92, 80, 164, 170)),
                    ("poly", tufts(back, 13, 13, side=1, lean=0.35, seed=3))])
    p.paint_mask(body, fur, depth=0.12, tex="fur", tex_amt=0.9, line=FL)
    p.vgrad(body, fur_d[:3] + (120,), fur[:3] + (0,), 84, 150)
    belly_m = mul(p._mask("poly", curve([(104, 130), (126, 118), (150, 150), (164, 200), (150, 226), (120, 224),
                                         (104, 180)], 4)), body)
    p.paint_mask(belly_m, belly, depth=0.2, line=0, tex="fur", tex_amt=0.6, rim=0, ao=0)
    for y in (160, 176, 192):
        p.stroke(curve([(118, y), (132, y + 3), (146, y)], 3), shade(belly, 0.8), 1.1)
    # mange and an old stitched scar
    p.shape("ellipse", (170, 140, 192, 158), hexc("#c89088"), depth=0.35, line=1.0, rim=0, ao=0, clip=body,
            tex="leather", tex_amt=0.5)
    p.stroke(curve([(146, 102), (156, 118), (160, 136)], 5), hexc("#d88a8a"), 3.2)
    for x, y in ((147, 105), (153, 114), (158, 124), (160, 134)):
        p.stroke([(x - 4, y + 2), (x + 4, y - 2)], hexc("#3a2a2a"), 1.2)
    # ---- near hind leg: a big haunch and a long flat foot with clawed toes
    p.shape("ellipse", (150, 160, 216, 226), fur, depth=0.16, tex="fur", tex_amt=0.8, line=FL)
    p.stroke(curve([(160, 176), (168, 196), (184, 210)], 5), shade(fur, 0.62), 1.4)
    foot = p.shape("poly", curve([(202, 216), (180, 222), (148, 226), (134, 230), (136, 238), (206, 238),
                                  (214, 228)], 4), pink, depth=0.28, light=1.3, tex="leather", tex_amt=0.4)
    for x in (150, 160, 170):
        p.stroke([(x, 228), (x + 2, 236)], shade(pink, 0.66), 1.0)
    for x in (136, 144, 152):
        claw(p, x, 234, 8, 160, 3.4, claw_c, 0.9)
    # ---- the head thrust forward, hissing
    p.shape("ellipse", (92, 30, 122, 66), shade(fur, 0.8), depth=0.2, tex="fur", tex_amt=0.5, line=FL)  # far ear
    p.shape("ellipse", (98, 38, 116, 62), shade(pink, 0.75), depth=0.3, line=0, rim=0, ao=0)
    mouth = p.shape("poly", curve([(64, 104), (40, 104), (16, 106), (12, 120), (26, 138), (54, 138), (72, 120)], 4),
                    hexc("#4a1420"), depth=0.25, line=1.3, rim=0)
    p.shape("ellipse", (26, 118, 62, 142), hexc("#b04058"), depth=0.3, line=0, rim=0, ao=0, clip=mouth)
    p.shape("poly", taper([(58, 128), (40, 130), (30, 124)], 9, 5), hexc("#d05a78"), depth=0.3, line=0.9, rim=0)
    for x, y in ((29, 135), (35, 134)):
        p.shape("rect", (x - 2.6, y - 11, x + 2.6, y + 2), hexc("#ecca7e"), radius=2, depth=0.3, light=1.3, line=0.9,
                rim=0, ao=0.3)
    p.shape("poly", curve([(80, 118), (56, 132), (34, 136), (22, 134), (22, 142), (38, 150), (66, 146), (84, 130)], 4),
            shade(fur, 0.92), depth=0.25, tex="fur", tex_amt=0.6, line=FL)
    head = p.union([("ellipse", (40, 44, 128, 122)),
                    ("poly", curve([(60, 54), (34, 66), (10, 84), (2, 96), (10, 106), (36, 108), (66, 112)], 5)),
                    ("poly", tufts([(126, 84), (124, 102), (116, 116)], 9, 10, side=1, lean=0.3, seed=5))])
    p.paint_mask(head, fur, depth=0.12, tex="fur", tex_amt=0.85, line=FL)
    p.shape("ellipse", (60, 82, 112, 126), shade(belly, 0.96), depth=0.2, line=0, rim=0, ao=0, clip=head,
            tex="fur", tex_amt=0.5)
    for x, w, h in ((17, 8.5, 18), (26, 8.5, 16)):
        p.shape("rect", (x - w / 2, 102, x + w / 2, 102 + h), hexc("#f0d28a"), radius=2.5, depth=0.3, light=1.35,
                line=1.0, rim=0, ao=0.3, spec=0.5)
    for x in (44, 52, 60):
        fang(p, x, 106, 5, 6, hexc("#f4ecd4"), line=0.8)
    p.stroke(curve([(66, 108), (72, 102), (76, 94)], 3), shade(fur, 0.55), 1.6)
    for pts in ([(26, 92), (34, 90)], [(30, 98), (40, 96)]):
        p.stroke(pts, shade(fur, 0.6), 1.2)  # snout wrinkles
    p.shape("poly", taper([(44, 138), (43, 148), (45, 156)], 5, 2), hexc("#cfeaff", 190), depth=0.3, light=1.3,
            line=0.9, rim=0, ao=0)
    drop(p, 45, 163, 3.4, hexc("#cfeaff", 210), line=0.9)
    p.shape("ellipse", (-3, 84, 15, 100), pink, depth=0.3, light=1.35, gloss=1.0)
    for a2, b2 in (((22, 92), (-10, 74)), ((22, 96), (-12, 92)), ((26, 100), (-8, 110)), ((32, 88), (8, 64))):
        p.stroke(curve([a2, ((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2 - 3), b2], 4), hexc("#2a1e24", 210), 1.0)
    ear = sub(p._mask("ellipse", (52, 2, 108, 64)), p._mask("poly", [(56, 12), (76, 30), (68, 4)]))
    p.paint_mask(ear, fur, depth=0.2, tex="fur", tex_amt=0.5, line=FL)
    inner = sub(p._mask("ellipse", (62, 14, 100, 58)), p._mask("poly", [(56, 6), (80, 34), (72, 2)]))
    p.paint_mask(inner, pink, depth=0.35, light=1.2, line=0, rim=0, ao=0)
    p.stroke(curve([(72, 50), (82, 38), (90, 30)], 3), shade(pink, 0.66), 1.2)
    glowing_eye(p, 62, 76, 11, 10, hexc("#ff3a2a"), hexc("#ffd070"), socket=hexc("#2a0c10"), slant=0.3)
    p.shape("poly", curve([(36, 60), (60, 62), (88, 74)], 3) + [(86, 80), (60, 70), (38, 67)], fur_d,
            depth=0.3, line=1.1, rim=0, tex="fur", tex_amt=0.5)
    # ---- near arm reaching for the player, claws spread
    p.shape("poly", limb_poly([(122, 136), (102, 166), (76, 178)], [26, 17, 13]), fur, depth=0.2, tex="fur",
            tex_amt=0.7, line=FL)
    p.shape("poly", tufts([(122, 152), (110, 170), (92, 182)], 6, 7, side=-1, lean=0.3, seed=6), fur, depth=0.3,
            tex="fur", line=1.1, rim=0)
    rat_hand(p, 70, 180, 172, 20, pink, claw_c)
    return p.finish(ground_shadow=(44, 222, 236, 250))



def skeleton_guard():
    """A skeleton soldier lunging forward behind a battered round shield, a notched rusty sword cocked back over
    its head, jaw dropped in a silent battle cry, soul-fire streaming from its eye sockets, a dented kettle
    helmet, a rusty pauldron and a tattered purple cloak (faces left)."""
    p = Pen(256, REG)
    bone_c = hexc("#e9dfc2")
    bone_d = shade(bone_c, 0.8)
    rust = hexc("#a2603a")
    iron = hexc("#7c8690")
    rag = hexc("#5b4a6a")
    soul = hexc("#ff6a28")
    leath = hexc("#5a3a26")
    # ---- tattered cloak streaming back from the shoulders
    cloak = curve([(110, 92), (152, 94), (190, 112), (232, 140), (244, 160), (228, 158), (234, 176), (214, 168),
                   (212, 186), (194, 170), (184, 184), (174, 160), (160, 146), (140, 130)], 4)
    cm = p.shape("poly", cloak, rag, depth=0.12, tex="cloth", tex_amt=0.9)
    for pts in ([(160, 108), (196, 140), (206, 166)], [(176, 112), (214, 140), (226, 158)]):
        p.stroke(curve(pts, 4), shade(rag, 0.62), 1.8)
    p.vgrad(cm, hexc("#000000", 0), hexc("#1a1024", 120), 110, 186)
    # ---- the sword arm cocked back: upper arm, forearm, fist, a notched rusty blade
    limb_bone(p, (142, 102), (172, 82), 8.5, bone_d)
    limb_bone(p, (172, 82), (168, 52), 7.5, bone_d)
    blade_c = hexc("#b9a898")
    b0, b1 = (174, 36), (222, 4)
    ux, uy = norm(b1[0] - b0[0], b1[1] - b0[1])
    nx, ny = -uy, ux
    w = 6.5
    bl = p._mask("poly", [(b0[0] + nx * w, b0[1] + ny * w), (b1[0] - ux * 14 + nx * w * 0.9, b1[1] - uy * 14 + ny * w * 0.9),
                          b1, (b1[0] - ux * 14 - nx * w * 0.9, b1[1] - uy * 14 - ny * w * 0.9),
                          (b0[0] - nx * w, b0[1] - ny * w)])
    for t, d in ((18, 3.5), (32, 2.6), (44, 3.2)):
        x, y = b0[0] + ux * t + nx * w, b0[1] + uy * t + ny * w
        bl = sub(bl, p._mask("poly", [(x - ux * d, y - uy * d), (x + ux * d, y + uy * d), (x - nx * d * 1.1, y - ny * d * 1.1)]))
    p.paint_mask(bl, blade_c, depth=0.3, light=1.35, spec=0.9, tex="metal", tex_amt=0.6)
    p.stroke([b0, (b1[0] - ux * 18, b1[1] - uy * 18)], shade(blade_c, 0.7), 1.6)
    p.stroke([(b0[0] - nx * w * 0.6, b0[1] - ny * w * 0.6), (b1[0] - ux * 14 - nx * w * 0.5, b1[1] - uy * 14 - ny * w * 0.5)],
             hexc("#ffffff", 150), 1.2)
    for t, r in ((24, 3.4), (46, 2.6), (8, 2.4)):
        x, y = b0[0] + ux * t, b0[1] + uy * t
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#8a4a28", 170))
    p.shape("poly", taper([(162, 30), (186, 44)], 7, 7), hexc("#6a4a32"), depth=0.35, spec=0.5, tex="metal")
    p.shape("poly", taper([(172, 38), (166, 54)], 6, 6), hexc("#4a3226"), depth=0.3, tex="leather")
    p.shape("ellipse", (160, 52, 172, 62), hexc("#8a6a4a"), depth=0.3, spec=0.5)
    p.shape("ellipse", (158, 36, 180, 54), bone_c, depth=0.3, tex="bone")
    for y in (40, 45, 50):
        p.stroke([(160, y), (168, y + 1)], shade(bone_c, 0.6), 1.1)
    # ---- back leg stretched out behind: femur, knee, shin, a rusty sabaton pushing off
    limb_bone(p, (146, 168), (170, 194), 9, bone_d)
    limb_bone(p, (170, 194), (190, 220), 7.5, bone_d)
    p.shape("ellipse", (162, 186, 180, 202), shade(rust, 0.95), depth=0.3, spec=0.5, tex="metal")
    p.shape("poly", curve([(196, 216), (200, 230), (196, 238), (164, 238), (166, 228), (180, 220)], 4),
            shade(rust, 0.85), depth=0.25, tex="metal", tex_amt=0.8, spec=0.4)
    # ---- the spine and a soul-fire glowing inside the ribcage, ribs in front
    cage = p._mask("poly", ell_pts(122, 122, 26, 24, rot=-14))
    p.fill_mask(_scale(cage, 0.6), hexc("#1c1020"))
    p.glow((122, 126), 26, soul, 0.6)
    for i, t in enumerate([j / 8 for j in range(9)]):
        x, y = 138 - 22 * t ** 1.3, 158 - 60 * t
        p.shape("rect", (x - 5, y - 3.2, x + 5, y + 3.2), bone_d, radius=2.5, depth=0.3, line=1.0, tex="bone", rim=0)
    for i, (y, x0) in enumerate(((106, 116), (118, 118), (129, 120), (139, 123))):
        wd = 28 - i * 3
        for side, kk in ((-1, 1.0), (1, 0.72)):
            pts = curve([(x0 + side * 3, y - 2), (x0 + side * wd * 0.7 * kk, y - 5), (x0 + side * wd * kk, y + 5),
                         (x0 + side * wd * 0.8 * kk, y + 13)], 5)
            p.shape("poly", taper(pts, 7, 3.4), bone_c if side < 0 else bone_d, depth=0.3, line=1.2,
                    tex="bone", tex_amt=0.5, rim=0.3)
    p.shape("poly", taper([(114, 100), (116, 122), (118, 140)], 9, 6), bone_c, depth=0.3, tex="bone", rim=0)
    p.shape("poly", taper([(92, 100), (118, 96), (146, 98)], 7, 6), bone_c, depth=0.3, tex="bone")
    # a leather strap across the chest
    p.shape("poly", taper([(98, 104), (124, 124), (150, 150)], 6, 6), leath, depth=0.3, tex="leather", rim=0)
    p.shape("rect", (118, 116, 128, 128), hexc("#a8a8a8"), radius=2, depth=0.3, spec=0.8, line=1.0)
    # ---- pelvis, belt and a ragged loincloth
    pel = p.union([("ellipse", (116, 150, 160, 176)), ("ellipse", (110, 154, 134, 174)),
                   ("ellipse", (142, 154, 166, 174))])
    p.paint_mask(pel, bone_c, depth=0.25, tex="bone", tex_amt=0.6)
    p.shape("poly", curve([(106, 162), (164, 160), (168, 186), (158, 198), (150, 186), (140, 202), (128, 188),
                           (116, 200), (108, 186), (102, 180)], 3), rag, depth=0.16, tex="cloth", tex_amt=0.9)
    p.shape("poly", taper([(102, 162), (136, 166), (168, 160)], 9, 9), leath, depth=0.3, tex="leather")
    p.shape("rect", (128, 159, 142, 172), hexc("#8a8f96"), radius=2, depth=0.3, spec=0.8, line=1.1)
    # ---- front leg bent forward into the lunge
    limb_bone(p, (126, 172), (104, 196), 10, bone_c)
    limb_bone(p, (104, 196), (98, 222), 8, bone_c)
    p.shape("ellipse", (95, 188, 115, 204), rust, depth=0.3, spec=0.6, tex="metal")
    p.shape("poly", curve([(108, 216), (88, 216), (70, 226), (66, 238), (110, 238), (112, 228)], 4), rust,
            depth=0.25, tex="metal", tex_amt=0.8, spec=0.5)
    for x in (80, 100):
        stud(p, x, 231, 1.8, hexc("#c8a080"))
    # ---- rusty pauldron on the sword shoulder
    pd = p.shape("poly", ell_pts(144, 96, 20, 13, 170, 370, rot=10), rust, depth=0.25, spec=0.7, tex="metal",
                 tex_amt=0.9)
    p.shape("poly", ell_pts(145, 102, 19, 7, 160, 380, rot=10), shade(rust, 0.85), depth=0.3, spec=0.5, tex="metal")
    for x, y in ((132, 94), (146, 88), (158, 96)):
        stud(p, x, y, 1.7, hexc("#d8b898"))
    # ---- soul-fire streaming back from the eye sockets
    trail = p.shape("poly", taper([(100, 58), (130, 50), (156, 50), (182, 40)], 20, 2, 8), hexc("#ff8a3a", 210),
                    shadow=0, light=0, line=1.0, ink=hexc("#8a2a0a", 180), rim=0, ao=0)
    p.glow((140, 46), 30, soul, 0.6)
    p.shape("poly", taper([(104, 58), (130, 51), (158, 50)], 9, 1.5, 8), hexc("#ffe08a", 230), **NOLINE)
    # ---- skull thrust forward: cranium, cheekbone, sockets, a jaw dropped open in a battle cry
    jaw = p.shape("poly", curve([(72, 96), (66, 110), (76, 122), (102, 120), (114, 106), (114, 90)], 4), bone_c,
                  depth=0.25, tex="bone", tex_amt=0.6)
    p.shape("poly", curve([(70, 84), (100, 86), (112, 88), (106, 106), (80, 110), (70, 98)], 3), hexc("#2a1a22"),
            **NOLINE)
    p.glow((90, 98), 10, soul, 0.4)
    for x in range(76, 106, 6):
        p.shape("rect", (x + 1, 105 - (x - 76) * 0.12, x + 5.4, 111 - (x - 76) * 0.12), hexc("#e6dcbc"), radius=1.4,
                line=0.7, depth=0.3, rim=0, ao=0)
    skull = p.union([("ellipse", (62, 22, 130, 88)), ("poly", curve([(66, 56), (58, 72), (64, 86), (76, 88),
                                                                     (108, 88), (122, 76)], 4))])
    p.paint_mask(skull, bone_c, depth=0.14, tex="bone", tex_amt=0.8)
    for x in range(70, 106, 6):
        p.shape("rect", (x, 83, x + 5, 89.5), hexc("#f4ecd4"), radius=1.4, line=0.7, depth=0.3, rim=0, ao=0)
    p.shape("poly", [(78, 70), (86, 70), (84, 80), (80, 80)], hexc("#2a1a22"), **NOLINE)
    for (x, y, rx, ry) in ((76, 58, 12, 11), (104, 56, 10, 10.5)):
        p.shape("ellipse", (x - rx, y - ry, x + rx, y + ry), hexc("#1a1018"), depth=0.3, line=1.2, rim=0, ao=0)
    glowing_eye(p, 77, 59, 5.8, 5.2, soul, socket=None, slant=0.45)
    glowing_eye(p, 104, 57, 4.8, 4.4, soul, socket=None, slant=0.45)
    p.shape("poly", [(62, 44), (90, 50), (88, 54), (64, 51)], shade(bone_c, 0.86), depth=0.3, line=1.0, rim=0)
    p.shape("poly", [(94, 50), (118, 44), (118, 49), (96, 54)], shade(bone_c, 0.86), depth=0.3, line=1.0, rim=0)
    p.stroke([(118, 30), (114, 40), (122, 46), (116, 56)], hexc("#6a5a48"), 1.5)
    p.stroke(curve([(112, 70), (120, 66), (126, 70)], 3), shade(bone_c, 0.6), 1.3)
    # ---- dented kettle helmet tipped down over the brow
    iron_m = p._mask("poly", ell_pts(98, 40, 40, 36, 180, 360, rot=-14))
    p.paint_mask(iron_m, iron, depth=0.16, spec=0.8, tex="metal", tex_amt=0.9)
    for x, y, r in ((80, 24, 5), (116, 16, 4), (98, 10, 3), (126, 28, 3)):
        p.flat("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7), hexc("#9a5a34", 190))
    p.stroke([(78, 14), (84, 22), (80, 28)], shade(iron, 0.6), 1.4)
    brim = p.shape("poly", ell_pts(98, 42, 56, 9, 0, 360, rot=-14), rust, depth=0.3, spec=0.6, tex="metal",
                   tex_amt=0.9)
    for x, y in ((52, 54), (74, 48), (120, 36), (142, 30)):
        stud(p, x, y, 1.7, hexc("#c8b8a8"))
    p.shadow_on(brim, 0.35, 2, 3)
    # ---- shield arm and the battered round shield thrust forward
    limb_bone(p, (98, 104), (84, 130), 8, bone_c)
    bite = p._mask("poly", curve([(4, 160), (20, 166), (16, 174), (24, 182), (12, 190), (2, 186)], 3))
    shm = sub(p._mask("poly", ell_pts(50, 144, 36, 50, rot=8)), bite)
    p.paint_mask(shm, hexc("#8a5a30"), depth=0.14, tex="wood", tex_amt=1.0)
    for x in (30, 50, 70):
        p.stroke([(x + 6, 96), (x - 6, 192)], hexc("#4a2e1a", 200), 1.4)
    ring = sub(sub(p._mask("poly", ell_pts(50, 144, 36, 50, rot=8)), p._mask("poly", ell_pts(50, 144, 29, 43, rot=8))),
               bite)
    p.paint_mask(ring, iron, depth=0.25, spec=0.9, tex="metal", tex_amt=0.8)
    for a in (0, 45, 90, 225, 270, 315):
        t = math.radians(a)
        x, y = 50 + 32.5 * math.cos(t), 144 + 46.5 * math.sin(t)
        x, y = 50 + (x - 50) * math.cos(math.radians(8)) - (y - 144) * math.sin(math.radians(8)), \
            144 + (x - 50) * math.sin(math.radians(8)) + (y - 144) * math.cos(math.radians(8))
        stud(p, x, y, 1.8, hexc("#d4dde6"))
    p.shape("ellipse", (36, 126, 66, 162), iron, depth=0.3, light=1.45, spec=1.0, tex="metal")
    p.shape("ellipse", (46, 138, 56, 150), hexc("#c8d0d8"), depth=0.3, light=1.5, line=0.9, rim=0)
    for x, y, r in ((26, 170, 6), (70, 110, 5), (64, 180, 4)):
        p.flat("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7), hexc("#6a3a1e", 150))
    p.stroke([(32, 108), (44, 122), (38, 132), (48, 144)], hexc("#2a1810"), 2.0)
    p.stroke([(80, 166), (72, 176)], hexc("#2a1810"), 1.6)
    for i, y in enumerate((130, 137, 144)):
        p.shape("line", [(88, y), (82, y + 2)], bone_c, width=4.5, depth=0.3, line=1.0, rim=0, ao=0.3)
    return p.finish(ground_shadow=(40, 226, 216, 248))


def chain_links(p, pts, size, color, step=None):
    """A hanging chain along a curve: alternating flat rings and edge-on links."""
    c = curve(pts, 8) if len(pts) > 2 else pts
    step = step or size * 0.9
    marks = along(c, step)
    for i, (x, y) in enumerate(marks):
        j = min(i + 1, len(marks) - 1)
        a = math.degrees(math.atan2(marks[j][1] - marks[max(0, j - 1)][1], marks[j][0] - marks[max(0, j - 1)][0]))
        if i % 2:
            pts2 = ell_pts(x, y, size * 0.62, size * 0.2, rot=a)
            p.shape("poly", pts2, shade(color, 0.85), depth=0.3, line=1.0, rim=0, spec=0.6)
        else:
            o = p._mask("poly", ell_pts(x, y, size * 0.62, size * 0.42, rot=a))
            h = p._mask("poly", ell_pts(x, y, size * 0.34, size * 0.14, rot=a))
            p.paint_mask(sub(o, h), color, depth=0.3, line=1.0, rim=0, spec=0.7, tex="metal", tex_amt=0.5)


def stud(p, x, y, r=2.2, color=hexc("#c8ccd2")):
    p.shape("ellipse", (x - r, y - r, x + r, y + r), color, line=0.7, depth=0.4, light=1.6, rim=0, ao=0.45,
            spec=0.6)


def cellar_warden():
    """Elite: the hooded jailer, a hulking brute in a leather apron with a spiked pauldron, chains, a key ring
    and a huge bearded axe held across his body, eyes burning in the dark of the hood (faces left)."""
    hood = hexc("#452636")
    apron = hexc("#6e4a31")
    skin = hexc("#c9a086")
    iron = hexc("#7d8792")
    trou = hexc("#4a3a3a")
    boot = hexc("#3a2a26")
    leath = hexc("#4a3226")
    gold = hexc("#e7b440")
    p = Pen(256, REG, fit=(0.92, 150, 240))
    # ---- legs planted wide, heavy boots with iron toe caps
    for (hip, knee, ank), bx in ((((118, 178), (108, 204), (104, 222)), 84), (((170, 178), (182, 204), (184, 222)), 164)):
        p.shape("poly", limb_poly([hip, knee, ank], [34, 26, 22]), trou, depth=0.18, tex="cloth", tex_amt=0.8)
        p.shape("poly", curve([(bx + 10, 212), (bx + 36, 212), (bx + 40, 230), (bx + 38, 240), (bx - 6, 240),
                                (bx - 6, 230), (bx + 4, 222)], 4), boot, depth=0.22, tex="leather", tex_amt=0.8)
        p.shape("poly", curve([(bx - 6, 228), (bx + 6, 224), (bx + 12, 232), (bx + 10, 240), (bx - 6, 240)], 3), iron,
                depth=0.3, spec=0.8, tex="metal", line=1.1)
        p.shape("rect", (bx + 6, 208, bx + 40, 216), hexc("#5a4234"), radius=3, depth=0.3, tex="leather")
    # ---- back upper arm (behind the torso)
    p.shape("poly", limb_poly([(196, 90), (220, 124), (224, 150)], [42, 34, 30]), skin, depth=0.16, tex="leather",
            tex_amt=0.4)
    # ---- hulking torso with a hairy gut
    torso = p.union([("ellipse", (70, 70, 226, 206)), ("ellipse", (90, 58, 206, 150))])
    p.paint_mask(torso, skin, depth=0.1, tex="leather", tex_amt=0.4)
    for x, y in ((108, 116), (120, 124), (100, 132), (176, 112), (186, 126), (170, 132)):
        p.stroke([(x, y), (x - 2, y + 5)], shade(skin, 0.52), 1.0)
    p.stroke(curve([(116, 100), (142, 110), (170, 100)], 4), shade(skin, 0.68), 1.6)  # pecs
    # ---- leather apron with stitching, stains and a heavy belt
    ap = curve([(88, 122), (196, 120), (208, 176), (212, 216), (152, 222), (82, 216), (80, 176)], 4)
    apm = p.shape("poly", ap, apron, depth=0.12, tex="leather", tex_amt=1.0)
    for pts in ([(92, 128), (84, 210)], [(192, 126), (204, 210)]):
        p.stroke(pts, hexc("#c8a078", 220), 1.2)
    for x, y, r in ((122, 196, 11), (178, 148, 7), (152, 206, 6), (104, 150, 5)):
        p.flat("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7), hexc("#3a1210", 120))
    p.flat("ellipse", (116, 190, 124, 196), hexc("#5a1a14", 150))
    p.shape("poly", taper([(76, 160), (144, 166), (214, 158)], 16, 16), hexc("#3a2a20"), depth=0.3,
            tex="leather", tex_amt=0.8)
    for x in (92, 112, 176, 196):
        stud(p, x, 162 + (0 if x < 150 else -3), 2.0)
    p.shape("rect", (134, 156, 156, 176), hexc("#9aa2aa"), radius=3, depth=0.3, spec=1.0, tex="metal")
    p.shape("rect", (139, 161, 151, 171), hexc("#3a2a20"), radius=2, **NOLINE)
    # key ring hanging from the belt
    p.paint_mask(ring_mask(p, (100, 168, 124, 192), 3.4), gold, depth=0.3, line=1.0, spec=0.9, rim=0)
    for x, y, a in ((100, 184, -18), (112, 190, 4), (124, 184, 24)):
        ux, uy = math.sin(math.radians(a)), math.cos(math.radians(a))
        p.shape("line", [(x, y), (x - ux * 18, y + uy * 18)], gold, width=4.2, line=1.0, spec=0.7, rim=0, depth=0.3)
        ex, ey = x - ux * 16, y + uy * 16
        p.shape("rect", (ex - 1, ey - 2, ex + 6, ey + 3), gold, radius=1, line=0.8, rim=0, depth=0.3)
        p.shape("ellipse", (x - 4.5, y - 5, x + 4.5, y + 4), gold, line=1.0, rim=0, depth=0.3, spec=0.6)
    # ---- back forearm in a studded bracer, coming round in front of the apron to the lower haft
    p.shape("poly", limb_poly([(222, 140), (212, 166), (184, 180), (166, 182)], [32, 28, 24, 22]), skin,
            depth=0.16, tex="leather", tex_amt=0.4)
    p.shape("poly", limb_poly([(218, 150), (208, 168), (188, 178)], [32, 30, 27]), leath, depth=0.25,
            tex="leather", tex_amt=0.8)
    for x, y in ((214, 154), (206, 166), (196, 174), (218, 164)):
        stud(p, x, y, 1.8)
    # ---- chains slung across the chest
    chain_links(p, [(84, 96), (130, 132), (206, 148)], 11, iron)
    chain_links(p, [(206, 96), (170, 116), (132, 150)], 9, shade(iron, 0.9))
    # ---- hood and capelet, peak flopping back, a shadowed face with burning eyes and gritted teeth
    cap = p.union([("poly", curve([(80, 70), (104, 52), (164, 50), (212, 70), (220, 100), (196, 112), (170, 96),
                                   (140, 108), (112, 98), (84, 112), (68, 98)], 4)),
                   ("ellipse", (94, 8, 178, 94)),
                   ("poly", curve([(150, 16), (176, 2), (196, 12), (178, 30)], 3))])
    p.paint_mask(cap, hood, depth=0.1, tex="cloth", tex_amt=1.0)
    for pts in ([(186, 8), (168, 26), (160, 60)], [(96, 80), (90, 100)], [(200, 80), (206, 102)]):
        p.stroke(curve(pts, 4), shade(hood, 0.6), 1.6)
    stitches(p, [(180, 10), (166, 30), (158, 60)], hexc("#8a6a7a"))
    face = p.shape("poly", curve([(104, 40), (140, 34), (160, 48), (164, 76), (150, 96), (116, 98), (100, 80)], 5),
                   hexc("#1c1018"), depth=0.25, line=1.2, rim=0)
    p.shadow_on(face, 0.4, 1.5, 3)
    glowing_eye(p, 118, 60, 7.5, 5.5, hexc("#ffc02a"), socket=None, slant=0.45)
    glowing_eye(p, 146, 58, 6.5, 5, hexc("#ffc02a"), socket=None, slant=0.45)
    p.shape("poly", [(106, 46), (130, 56), (128, 60), (104, 52)], shade(hood, 0.7), line=0.9, depth=0.3, rim=0)
    p.shape("poly", [(134, 55), (160, 44), (160, 50), (136, 60)], shade(hood, 0.7), line=0.9, depth=0.3, rim=0)
    chin = p.shape("poly", curve([(108, 76), (132, 70), (158, 74), (160, 90), (150, 100), (118, 102), (106, 92)], 4),
                   hexc("#7a5a4c"), depth=0.25, line=1.1, rim=0, tex="leather", tex_amt=0.6, clip=face)
    p.vgrad(chin, hexc("#1c1018", 200), hexc("#1c1018", 0), 70, 90)
    for x, y in ((120, 96), (128, 98), (138, 97), (146, 94), (116, 90), (152, 88)):
        p.flat("ellipse", (x - 0.8, y - 0.8, x + 0.8, y + 0.8), hexc("#2a1a18"))
    m = p.shape("poly", curve([(114, 82), (134, 80), (154, 80), (150, 90), (132, 92), (116, 90)], 3),
                hexc("#3a1018"), depth=0.3, line=1.1, rim=0)
    for x, y, h in ((119, 82, 5), (126, 81.5, 4.5), (133, 81, 5.5), (140, 81, 4), (147, 81, 5)):
        p.shape("rect", (x - 3, y - 0.5, x + 3, y + h), hexc("#e0d4b0"), radius=1, line=0.6, depth=0.3, rim=0,
                ao=0, clip=m)
    for x, h in ((122, 6), (144, 7)):
        p.shape("poly", [(x - 3, 91), (x + 3, 91), (x + 0.5, 91 - h)], hexc("#efe4c0"), line=0.7, depth=0.3,
                rim=0, ao=0)
    p.stroke([(152, 76), (158, 92)], hexc("#b06a5a"), 1.4)  # old scar
    # ---- spiked iron pauldron on the near shoulder
    pad = p.shape("poly", ell_pts(88, 90, 30, 20, 160, 380, rot=-12), iron, depth=0.2, spec=1.0, tex="metal",
                  tex_amt=0.9)
    p.shape("poly", ell_pts(88, 100, 28, 12, 150, 390, rot=-12), shade(iron, 0.85), depth=0.3, spec=0.7,
            tex="metal", tex_amt=0.9)
    for x, y, a in ((68, 82, -150), (84, 72, -110), (104, 74, -70)):
        ta = math.radians(a)
        tip = (x + math.cos(ta) * 16, y + math.sin(ta) * 16)
        n2 = (-math.sin(ta) * 4.5, math.cos(ta) * 4.5)
        p.shape("poly", [(x + n2[0], y + n2[1]), tip, (x - n2[0], y - n2[1])], hexc("#aab4be"), depth=0.35,
                light=1.5, spec=1.0, line=1.1, rim=0)
    for x, y in ((74, 94), (90, 96), (106, 92)):
        stud(p, x, y, 2.0)
    # ---- the huge bearded axe held across the body
    A, B = (60, 30), (176, 220)
    p.shape("poly", taper([A, B], 11, 12), hexc("#6b4428"), depth=0.3, tex="wood", tex_amt=1.0)
    for t in (0.2, 0.26, 0.32):
        x, y = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t
        p.stroke([(x - 6, y + 3), (x + 6, y - 3)], hexc("#2a1a10"), 1.6)
    p.shape("ellipse", (170, 214, 184, 228), iron, depth=0.3, spec=0.8)
    head_pts = curve([(70, 24), (46, 10), (18, 0), (4, 30), (2, 66), (12, 98), (30, 110), (36, 86), (48, 70),
                      (76, 62)], 5)
    ax = p.shape("poly", head_pts, iron, depth=0.2, light=1.35, spec=1.0, tex="metal", tex_amt=0.9)
    edge = p._mask("poly", curve([(18, 0), (4, 30), (2, 66), (12, 98), (30, 110), (20, 92), (14, 60), (18, 26),
                                  (26, 6)], 5))
    p.paint_mask(mul(edge, ax), hexc("#e4ecf2"), depth=0.3, light=1.3, line=0, shadow=0, rim=0, ao=0, spec=1.0)
    for x, y, r in ((44, 40, 6), (52, 58, 4), (30, 86, 4.5), (60, 30, 3)):
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#8a4a28", 190))
    p.shape("poly", curve([(52, 18), (80, 26), (82, 66), (54, 66)], 2), hexc("#5a4a44"), depth=0.3, tex="metal")
    for x, y in ((60, 28), (74, 32), (60, 58), (74, 60)):
        stud(p, x, y, 1.8)
    p.sparkle((10, 40), 6)
    # ---- the back hand wrapped round the lower haft, a broken manacle on the wrist
    p.shape("ellipse", (144, 166, 176, 196), skin, depth=0.22, tex="leather", tex_amt=0.3)
    for y in (174, 181, 188):
        p.stroke([(147, y), (160, y - 2)], shade(skin, 0.55), 1.3)
    # ---- near arm: huge forearm with a studded bracer, fist on the upper haft
    p.shape("poly", limb_poly([(84, 104), (64, 138), (80, 150), (100, 132)], [36, 30, 28, 26]), skin, depth=0.16,
            tex="leather", tex_amt=0.4)
    p.shape("poly", limb_poly([(66, 128), (72, 146), (88, 146)], [28, 28, 26]), leath, depth=0.25, tex="leather",
            tex_amt=0.8)
    for x, y in ((64, 134), (74, 148), (84, 140)):
        stud(p, x, y, 1.8)
    p.paint_mask(ring_mask(p, (60, 118, 80, 132), 3.5), iron, depth=0.3, spec=0.8, line=1.0)
    chain_links(p, [(64, 130), (52, 148), (48, 168)], 7, iron)
    fist = p.shape("ellipse", (92, 110, 126, 140), skin, depth=0.22, tex="leather", tex_amt=0.3)
    for y in (118, 125, 132):
        p.stroke([(96, y), (112, y - 2)], shade(skin, 0.55), 1.4)
    p.stroke(curve([(116, 114), (122, 120), (120, 130)], 3), shade(skin, 0.6), 1.3)
    return p.finish(ground_shadow=(40, 226, 236, 250))


def qpt(q, u, v):
    """Bilinear point in quad q = (top-left, top-right, bottom-right, bottom-left) at (u across, v down)."""
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = q
    tx, ty = ax + (bx - ax) * u, ay + (by - ay) * u
    bx2, by2 = dx + (cx - dx) * u, dy + (cy - dy) * u
    return (tx + (bx2 - tx) * v, ty + (by2 - ty) * v)


def qpoly(q, u0, v0, u1, v1):
    return [qpt(q, u0, v0), qpt(q, u1, v0), qpt(q, u1, v1), qpt(q, u0, v1)]


def coin(p, x, y, r, gold, tilt=0.45):
    p.shape("ellipse", (x - r, y - r * tilt, x + r, y + r * tilt), gold, depth=0.3, light=1.45, spec=0.9, line=1.0,
            rim=0, ao=0.3)
    p.shape("ellipse", (x - r * 0.6, y - r * tilt * 0.6, x + r * 0.6, y + r * tilt * 0.6), shade(gold, 0.86),
            depth=0.3, light=1.3, line=0.6, rim=0, ao=0)


def mimic():
    """A treasure chest that is really a mouth: the lid gapes open on rows of fangs, a long drooling tongue
    lolls over the lock, and two yellow slit eyes glare from the lid (faces left)."""
    wood = hexc("#a0652f")
    wood_d = hexc("#7a4822")
    band = hexc("#8a939e")
    gold = hexc("#f0bf48")
    maw = hexc("#5a1624")
    gum = hexc("#b0405a")
    tooth = hexc("#f4ecd4")
    p = Pen(256, REG, fit=(0.9, 128, 240))
    # ---- coins and a gem spilled on the floor
    for x, y, r in ((18, 232, 9), (38, 240, 8), (206, 238, 9), (228, 228, 8), (190, 246, 7), (58, 246, 6)):
        coin(p, x, y, r, gold)
    p.shape("poly", [(236, 238), (246, 230), (254, 238), (246, 248)], hexc("#3ad0ff"), line=1.0, gloss=1.0, rim=0,
            spec=0.8)
    # ---- gnarled wooden claws poking out under the corners
    for x, y, a in ((40, 220, 130), (150, 228, 70), (210, 204, 55)):
        claw(p, x, y, 22, a, 12, hexc("#6a4428"), 1.3)
    # ---- the base: a box seen three-quarter, front toward the player
    front = ((30, 136), (158, 146), (156, 232), (34, 224))
    side = ((158, 146), (220, 124), (218, 208), (156, 232))
    p.shape("poly", list(side), wood_d, depth=0.12, tex="wood_h", tex_amt=1.0)
    for v in (0.33, 0.66):
        p.stroke([qpt(side, 0, v), qpt(side, 1, v)], shade(wood_d, 0.55), 1.4)
    fm = p.shape("poly", list(front), wood, depth=0.1, tex="wood_h", tex_amt=1.0)
    for v in (0.34, 0.67):
        p.stroke([qpt(front, 0, v), qpt(front, 1, v)], shade(wood, 0.55), 1.6)
    for q, us in ((front, (0.1, 0.84)), (side, (0.55,))):
        for u in us:
            p.shape("poly", qpoly(q, u - 0.06, 0, u + 0.06, 1), band, depth=0.2, spec=0.7, tex="metal", tex_amt=0.8,
                    line=1.2)
            for v in (0.15, 0.5, 0.85):
                x, y = qpt(q, u, v)
                stud(p, x, y, 1.9, hexc("#d4dde6"))
    for pts in ([qpt(front, 0, 0.78), qpt(front, 0.16, 1), qpt(front, 0, 1)],
                [qpt(side, 1, 0.75), qpt(side, 1, 1), qpt(side, 0.72, 1)]):
        p.shape("poly", pts, gold, depth=0.3, spec=0.8, line=1.1, rim=0)
    # the lock plate
    lock = qpoly(front, 0.47, 0.2, 0.67, 0.62)
    p.shape("poly", curve(lock + [lock[0]], 2), gold, depth=0.25, light=1.45, spec=1.0, line=1.3)
    lx, ly = qpt(front, 0.57, 0.36)
    p.shape("ellipse", (lx - 5, ly - 5, lx + 5, ly + 5), DARK, **NOLINE)
    p.shape("poly", [(lx - 2.5, ly + 2), (lx + 2.5, ly + 2), (lx + 3.5, ly + 14), (lx - 3.5, ly + 14)], DARK, **NOLINE)
    # ---- the open mouth: dark throat between the base and the raised lid
    inside = [(30, 136), (158, 146), (220, 124), (214, 70), (182, 52), (44, 66)]
    im = p.shape("poly", inside, maw, depth=0.1, tex="leather", tex_amt=0.6, line=1.2)
    p.glow_clip((126, 104), 70, hexc("#140408"), 0.9, im)
    p.mist((100, 84, 150, 116), hexc("#000000"), 200, 5)  # the throat
    # gums along both jaws
    p.shape("poly", taper([(30, 134), (96, 140), (158, 144), (220, 122)], 12, 9), gum, depth=0.3, light=1.3,
            line=1.1, rim=0, gloss=0.4)
    p.shape("poly", taper([(44, 68), (116, 60), (182, 54), (214, 72)], 12, 9), gum, depth=0.3, light=1.3, line=1.1,
            rim=0)
    # saliva strands across the gape
    for x0, x1 in ((70, 74), (132, 128), (176, 184)):
        p.stroke(curve([(x0, 66), ((x0 + x1) / 2 + 4, 104), (x1, 140)], 5), hexc("#ffd0dc", 140), 1.4)
    # lower teeth pointing up (front and side edges)
    for i in range(7):
        u = 0.06 + i * 0.145
        x, y = qpt(front, u, 0)
        h = 20 if i % 2 == 0 else 15
        fang(p, x, y - 1, 13, -h, tooth, curl=0.1)
    for u in (0.3, 0.72):
        x, y = qpt(side, u, 0)
        fang(p, x, y - 1, 10, -14, shade(tooth, 0.9))
    # ---- the lid, flung open: its front face with bands and eyes, side face behind
    lf = ((50, 2), (178, -4), (182, 52), (44, 66))
    ls = ((178, -4), (234, 16), (236, 60), (182, 52))
    p.shape("poly", list(ls), wood_d, depth=0.14, tex="wood_h", tex_amt=1.0)
    lm = p.shape("poly", curve([lf[3], (40, 30), (52, 4), (114, -6), (178, -4), (184, 26), lf[2]], 4) + [lf[3]], wood,
                 depth=0.12, tex="wood_h", tex_amt=1.0)
    p.shape("poly", taper([(44, 66), (112, 60), (182, 52)], 7, 7), gold, depth=0.3, spec=0.9, line=1.1, rim=0)
    for u in (0.1, 0.84):
        pts = qpoly(lf, u - 0.06, 0.02, u + 0.06, 0.93)
        p.shape("poly", pts, band, depth=0.2, spec=0.7, tex="metal", tex_amt=0.8, line=1.2, clip=lm)
        for v in (0.25, 0.7):
            x, y = qpt(lf, u, v)
            stud(p, x, y, 1.9, hexc("#d4dde6"))
    p.shape("poly", qpoly(ls, 0.5, 0.02, 0.62, 0.9), band, depth=0.2, spec=0.7, tex="metal", tex_amt=0.8, line=1.2)
    # upper fangs hanging from the lid's front edge
    for i in range(6):
        u = 0.08 + i * 0.17
        x, y = qpt(lf, u, 1)
        h = 26 if i in (1, 4) else 18
        fang(p, x, y + 3, 14 if h > 20 else 12, h, tooth, curl=-0.1)
    for u in (0.3, 0.75):
        x, y = qpt(ls, u, 1)
        fang(p, x, y + 2, 10, 15, shade(tooth, 0.9))
    # ---- the eyes: glaring yellow slits under angry wooden brows
    for u, r in ((0.33, 15), (0.7, 13)):
        cx, cy = qpt(lf, u, 0.45)
        p.glow((cx, cy), r * 1.7, hexc("#ffe040"), 0.45)
        e = p.shape("ellipse", (cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), hexc("#ffe14a"), light=1.5,
                    depth=0.28, rim=0, line=1.3, ink=hexc("#3a1a08"))
        p.shape("ellipse", (cx - r * 0.72, cy - r * 0.6, cx + r * 0.6, cy + r * 0.7), hexc("#ff9a1a"), **NOLINE,
                clip=e)
        p.flat("ellipse", (cx - r * 0.2 - 3, cy - r * 0.72, cx - r * 0.2 + 3, cy + r * 0.72), DARK)
        p.flat("ellipse", (cx - r * 0.62, cy - r * 0.5, cx - r * 0.3, cy - r * 0.18), WHITE)
        p.shape("poly", [(cx - r - 4, cy - r * 1.05), (cx + r + 3, cy - r * 0.25), (cx + r + 3, cy - r * 0.8),
                         (cx - r - 4, cy - r * 1.55)], wood_d, depth=0.3, line=1.2, rim=0, tex="wood_h")
    # ---- the tongue lolling over the front edge, curling past the lock
    tongue = hexc("#e0607a")
    tp = [(128, 118), (96, 128), (66, 146), (50, 172), (54, 198), (70, 206)]
    tm = p.union([("poly", limb_poly(tp, [34, 32, 30, 27, 22, 16])), ("ellipse", (54, 192, 80, 214))])
    p.paint_mask(tm, tongue, depth=0.2, light=1.35, gloss=0.6, tex="leather", tex_amt=0.5, spec=0.4)
    p.stroke(curve([(116, 124), (80, 140), (60, 170), (62, 196)], 6), shade(tongue, 0.62), 2.6)
    drop(p, 70, 216, 4, hexc("#ffc0d0", 220), line=0.9)
    p.shape("poly", taper([(58, 204), (56, 214), (58, 224)], 4, 1.5), hexc("#ffc0d0", 200), depth=0.3, line=0.8,
            rim=0, ao=0)
    # a coin still stuck on the tongue
    coin(p, 94, 132, 7, gold, 0.5)
    p.sparkle((60, 10), 5)
    return p.finish(ground_shadow=(18, 214, 244, 252))


def ermine(p, box_or_mask, spots, fur=hexc("#f4efe6")):
    """White ermine fur with black tail tips."""
    m = box_or_mask if isinstance(box_or_mask, Image.Image) else p._mask("ellipse", box_or_mask)
    p.paint_mask(m, fur, depth=0.16, tex="fur", tex_amt=0.9)
    for x, y in spots:
        p.shape("poly", curve([(x, y - 6), (x + 3.5, y + 1), (x, y + 8), (x - 3.5, y + 1)], 3) + [(x, y - 6)],
                hexc("#1c1420"), depth=0.3, light=1.4, line=0, rim=0, ao=0, clip=m)
    return m


def ghost_flame(p, cx, base, w, h, lean=0.0, strength=0.8, colors=("#2ad8a0", "#6dffcf", "#e8fff6")):
    """A necrotic green flame (the house flame shape in ghostly colours)."""
    p.glow((cx + lean * h * 0.4, base - h * 0.4), max(w, h) * 1.0, hexc(colors[1]), strength)
    for i, (col, sc) in enumerate(zip(colors, (1.0, 0.66, 0.36))):
        ww, hh = w * sc, h * (0.95 if i == 0 else 0.9 * sc + 0.1)
        tip = (cx + lean * h * (0.9 - i * 0.15), base - hh)
        pts = curve([(cx - ww / 2, base - ww * 0.3), (cx - ww * 0.5, base - hh * 0.4), (cx - ww * 0.2 + lean * hh * 0.2, base - hh * 0.62),
                     (cx - ww * 0.28 + lean * hh * 0.5, base - hh * 0.86), tip,
                     (cx + ww * 0.3 + lean * hh * 0.4, base - hh * 0.6), (cx + ww * 0.52, base - hh * 0.3),
                     (cx + ww * 0.4, base - ww * 0.05), (cx, base + ww * 0.12), (cx - ww * 0.4, base - ww * 0.05)], 5)
        if i == 0:
            p.shape("poly", pts, hexc(col, 225), depth=0.2, light=1.3, line=1.1, ink=hexc("#0e5a44"), rim=0, ao=0)
        else:
            p.shape("poly", pts, hexc(col, 235), **NOLINE)


def bone_king():
    """Boss: the Bone King, a towering crowned skeleton in a purple royal robe and ermine mantle behind a high
    standing collar, raising a skull-topped staff of green soul-fire and conjuring more in his other hand
    (faces left)."""
    robe = hexc("#5b2a86")
    robe_d = hexc("#3e1a60")
    trim = hexc("#f4efe6")
    glowc = hexc("#6dffcf")
    gold = hexc("#f1c24a")
    bone_c = hexc("#ece3c8")
    ruby, sapph = hexc("#e0303a"), hexc("#3ad0ff")
    p = Pen(384, BOSS, rim=hexc("#a8ffe0"), fit=(0.88, 196, 372))
    # ---- soul-light behind him
    p.glow((200, 170), 190, glowc, 0.22)
    # ---- the tattered cape sweeping back
    cape = curve([(176, 150), (286, 146), (330, 220), (366, 330), (372, 366), (346, 352), (330, 372), (304, 352),
                  (282, 372), (258, 356), (236, 370), (220, 300)], 5)
    cm = p.shape("poly", cape, robe_d, depth=0.08, tex="cloth", tex_amt=0.6)
    for pts in ([(262, 170), (290, 260), (304, 350)], [(292, 170), (330, 260), (348, 340)], [(240, 200), (250, 300),
                                                                                                 (262, 356)]):
        p.stroke(curve(pts, 6), shade(robe_d, 0.55), 3.2)
    p.vgrad(cm, hexc("#000000", 0), hexc("#12081c", 150), 250, 370)
    # ---- the back arm raised, conjuring soul-fire in an open bony hand
    p.shape("poly", limb_poly([(262, 168), (300, 170), (318, 142)], [40, 34, 28]), robe, depth=0.16, tex="cloth",
            tex_amt=0.6)
    p.shape("poly", limb_poly([(296, 156), (322, 144)], [34, 30]), trim, depth=0.22, tex="fur", tex_amt=0.8)
    limb_bone(p, (318, 140), (330, 116), 9, bone_c)
    p.shape("ellipse", (320, 96, 346, 118), bone_c, depth=0.3, tex="bone", rim=0)
    for x0, y0, x1, y1 in ((322, 100, 314, 84), (330, 96, 328, 78), (338, 96, 342, 80), (344, 104, 354, 94)):
        p.shape("line", [(x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2 + 1), (x1, y1)], bone_c, width=5, depth=0.3,
                line=1.1, rim=0)
    ghost_flame(p, 334, 94, 40, 72, lean=0.1, strength=0.85)
    # ---- the robe to the ground: embroidered panel, ermine hem
    rb = p.shape("poly", curve([(142, 150), (262, 150), (282, 250), (306, 362), (200, 370), (96, 362), (122, 250)],
                               4), robe, depth=0.08, tex="cloth", tex_amt=0.6)
    for pts in ([(150, 220), (122, 356)], [(260, 220), (286, 356)], [(172, 260), (160, 356)]):
        p.stroke(curve(pts, 4), shade(robe, 0.6), 2.6)
    panel = [(184, 150), (226, 150), (242, 350), (168, 350)]
    pm = p.shape("poly", panel, shade(robe, 0.78), depth=0.1, line=1.2, tex="cloth", rim=0)
    p.stroke([(184, 152), (168, 348)], gold, 3.4)
    p.stroke([(226, 152), (242, 348)], gold, 3.4)
    for y in range(248, 340, 24):
        w = 9 + (y - 248) * 0.05
        p.shape("poly", [(205, y - 10), (205 + w, y), (205, y + 10), (205 - w, y)], gold, line=1.0, depth=0.3, spec=0.7,
                rim=0)
        p.shape("ellipse", (202, y - 3, 208, y + 3), ruby, line=0.6, gloss=1.0, rim=0, depth=0.3)
    for i in range(7):  # a faint damask of little crowns
        for j in range(4):
            x, y = 132 + i * 24 + (12 if j % 2 else 0), 236 + j * 30
            if 164 < x < 246:
                continue
            p.shape("poly", [(x - 5, y + 3), (x - 5, y - 3), (x - 2, y), (x, y - 5), (x + 2, y), (x + 5, y - 3), (x + 5, y + 3)],
                    shade(robe, 1.18), **NOLINE, clip=rb)
    p.vgrad(rb, hexc("#000000", 0), hexc("#12081c", 120), 260, 370)
    hem = p.union([("poly", curve([(94, 344), (200, 352), (308, 344), (312, 372), (200, 380), (90, 372)], 4))])
    ermine(p, hem, [(114, 362), (150, 366), (186, 368), (222, 368), (258, 366), (292, 362)])
    # ---- the ribcage showing through the parted robe, soul-fire inside
    cav = p.shape("poly", curve([(176, 160), (234, 160), (230, 214), (206, 236), (180, 214)], 4), hexc("#1c1024"),
                  line=1.2, rim=0, depth=0.2)
    p.glow_clip((205, 200), 40, glowc, 0.8, cav)
    p.shape("rect", (201, 160, 210, 236), bone_c, radius=3, depth=0.3, tex="bone", line=1.1)
    for i, y in enumerate((172, 188, 203, 217)):
        w = 26 - i * 3
        for side in (-1, 1):
            pts = curve([(205 + side * 3, y), (205 + side * w, y + 1), (205 + side * (w - 5), y + 11)], 4)
            p.shape("poly", taper(pts, 7, 3.5), bone_c, depth=0.3, line=1.1, tex="bone", rim=0)
    # ---- ermine mantle over the shoulders and a jewelled clasp
    mant = p.union([("ellipse", (120, 118, 292, 190)), ("poly", curve([(128, 150), (206, 196), (286, 150)], 4))])
    ermine(p, mant, [(142, 150), (170, 170), (206, 180), (242, 170), (272, 150), (156, 132), (258, 132), (206, 160)])
    p.shape("ellipse", (193, 170, 219, 196), gold, depth=0.3, spec=1.0, light=1.45)
    p.shape("ellipse", (199, 176, 213, 190), ruby, line=0.9, gloss=1.0, rim=0, depth=0.3, light=1.5)
    # gold pauldrons on the mantle
    for cx, cy, rot in ((146, 136, -14), (266, 138, 14)):
        pts = ell_pts(cx, cy, 34, 20, 180, 360, rot=rot) + ell_pts(cx, cy + 6, 34, 10, 0, 180, rot=rot)
        p.shape("poly", pts, gold, depth=0.25, light=1.45, spec=1.0, tex="metal", tex_amt=0.5)
        for dx in (-18, 0, 18):
            a = math.radians(rot)
            bx, by = cx + dx * math.cos(a), cy - 16 + dx * math.sin(a) + abs(dx) * 0.15
            p.shape("poly", [(bx - 5, by + 4), (bx + dx * 0.25, by - 16), (bx + 5, by + 4)], hexc("#fff0c0"),
                    depth=0.3, light=1.4, spec=1.0, line=1.1, rim=0)
        p.shape("ellipse", (cx - 5, cy - 6, cx + 5, cy + 4), sapph, line=0.8, gloss=1.0, rim=0, depth=0.3)
    # ---- the high standing collar behind the head
    col = curve([(130, 120), (116, 60), (132, 40), (150, 84), (176, 60), (206, 70), (236, 60), (262, 84), (280, 40),
                 (296, 60), (282, 120)], 5)
    colm = p.shape("poly", col, shade(robe, 0.9), depth=0.12, tex="cloth", tex_amt=0.5)
    p.shape("poly", curve([(142, 118), (132, 74), (150, 96), (178, 76), (206, 84), (234, 76), (262, 96), (280, 74),
                           (270, 118)], 5), hexc("#2a1240"), depth=0.2, line=0, rim=0, ao=0, clip=colm)
    p.stroke(curve([(130, 120), (116, 60), (132, 40), (150, 84), (176, 60), (206, 70), (236, 60), (262, 84), (280, 40),
                    (296, 60), (282, 120)], 5), gold, 3)
    # ---- skull: a big cracked dome, sharp cheekbones, deep sockets with green eyes, a narrow grinning jaw
    skull = p.union([("ellipse", (136, 22, 250, 134)),
                     ("poly", curve([(142, 96), (150, 122), (166, 146), (220, 146), (236, 122), (244, 96)], 4))])
    p.paint_mask(skull, bone_c, depth=0.13, tex="bone", tex_amt=0.9)
    jaw = p.shape("poly", curve([(160, 146), (164, 166), (180, 180), (206, 180), (222, 166), (226, 146)], 4), bone_c,
                  depth=0.25, tex="bone", tex_amt=0.7)
    p.shape("poly", curve([(162, 140), (178, 146), (193, 147), (208, 146), (224, 140), (222, 154), (193, 160),
                           (164, 154)], 3), hexc("#1c1018"), **NOLINE)
    for i, x in enumerate(range(168, 220, 7)):
        dy = -abs(x - 193) * 0.12
        p.shape("rect", (x - 3, 136 + dy, x + 3, 146 + dy * 0.4), hexc("#f4ecd4"), radius=1.4, line=0.8, depth=0.3,
                rim=0, ao=0)
        p.shape("rect", (x - 2.8, 152 + dy * 0.2, x + 2.8, 160), hexc("#e6dcbc"), radius=1.4, line=0.8, depth=0.3,
                rim=0, ao=0)
    p.stroke(curve([(172, 170), (193, 176), (214, 170)], 3), shade(bone_c, 0.66), 1.4)
    p.shape("poly", curve([(186, 106), (194, 106), (198, 120), (190, 128), (182, 120)], 3), hexc("#1c1018"), **NOLINE)
    for x, y, rx, ry in ((166, 88, 21, 19), (218, 86, 19, 18)):
        p.shape("ellipse", (x - rx, y - ry, x + rx, y + ry), hexc("#120a12"), depth=0.3, line=1.4, rim=0, ao=0.2)
    glowing_eye(p, 168, 90, 9, 8, glowc, hexc("#effff8"), socket=None, slant=0.45)
    glowing_eye(p, 218, 88, 8, 7.5, glowc, hexc("#effff8"), socket=None, slant=0.45)
    p.shape("poly", [(138, 64), (186, 76), (184, 84), (140, 74)], shade(bone_c, 0.85), depth=0.3, line=1.2, rim=0)
    p.shape("poly", [(248, 62), (200, 76), (202, 84), (248, 72)], shade(bone_c, 0.85), depth=0.3, line=1.2, rim=0)
    p.stroke([(206, 40), (214, 54), (206, 64), (212, 74)], hexc("#6a5a48"), 2.2)
    p.stroke([(238, 106), (246, 116), (240, 124)], hexc("#6a5a48"), 1.8)
    for pts in ([(146, 112), (160, 122), (164, 132)], [(240, 112), (226, 122), (222, 132)]):
        p.stroke(curve(pts, 3), shade(bone_c, 0.62), 1.6)
    # ---- the crown: tall spiked band with pearls and gems
    crown = [(132, 58), (130, 8), (152, 34), (168, -2), (186, 30), (200, -12), (214, 30), (232, -2), (248, 34),
             (262, 8), (258, 58)]
    cr = p.shape("poly", crown, gold, depth=0.15, light=1.45, spec=1.0, tex="metal", tex_amt=0.5)
    for x, y in ((130, 8), (168, -2), (200, -12), (232, -2), (262, 8)):
        p.shape("ellipse", (x - 6, y - 6, x + 6, y + 6), hexc("#fbf4e4"), depth=0.3, gloss=1.0, rim=0, line=1.1)
    p.shape("poly", curve([(126, 44), (194, 52), (264, 44), (264, 64), (194, 72), (126, 64)], 3), hexc("#d49a2a"),
            depth=0.3, spec=0.7, tex="metal", tex_amt=0.5)
    for x, y, c, r in ((150, 56, ruby, 7), (194, 62, sapph, 9), (238, 56, ruby, 7)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), c, light=1.6, line=1.2, gloss=1.0, rim=0, depth=0.3)
    for x, y in ((170, 60), (216, 60)):
        p.shape("ellipse", (x - 2.5, y - 2.5, x + 2.5, y + 2.5), hexc("#fbf4e4"), line=0.7, gloss=1.0, rim=0)
    p.sparkle((158, 22), 9)
    p.sparkle((250, 40), 6)
    # ---- the staff: dark wood bound in gold, a horned skull orb burning with soul-fire
    staff = curve([(76, 120), (86, 240), (96, 372)], 6)
    p.shape("poly", taper(staff, 13, 11), hexc("#4a3226"), depth=0.3, tex="wood", tex_amt=1.0)
    for x, y in along(staff, 58)[1:4]:
        p.shape("rect", (x - 9, y - 5, x + 9, y + 5), gold, radius=2, depth=0.3, line=1.1, spec=0.8, rim=0)
    ghost_flame(p, 74, 72, 70, 110, lean=-0.1, strength=0.9)
    for pts in ([(62, 116), (40, 96), (36, 66)], [(88, 116), (110, 96), (114, 66)]):  # horns cradling the orb
        p.shape("poly", taper(pts, 12, 2), gold, depth=0.3, light=1.45, spec=1.0, line=1.2)
    orb = p.shape("poly", curve([(46, 84), (52, 58), (76, 50), (100, 58), (104, 84), (96, 104), (88, 116), (62, 116),
                                 (54, 104)], 4), hexc("#c9ffec"), light=1.35, depth=0.14, gloss=0.9, rim=0.2)
    p.glow_clip((75, 90), 40, glowc, 0.6, orb)
    for x in (62, 88):
        p.shape("ellipse", (x - 9, 76, x + 9, 94), hexc("#1f5a4a"), **NOLINE)
        p.flat("ellipse", (x - 3, 82, x + 3, 88), hexc("#e8fff6"))
    p.shape("poly", [(72, 96), (78, 96), (75, 104)], hexc("#1f5a4a"), **NOLINE)
    for x in range(62, 92, 6):
        p.stroke([(x, 106), (x, 114)], hexc("#1f5a4a"), 1.8)
    # ---- the near arm in a puffed sleeve, ringed bony fingers round the staff
    p.shape("poly", limb_poly([(150, 170), (122, 206), (98, 210)], [48, 40, 30]), robe, depth=0.16, tex="cloth",
            tex_amt=0.6)
    p.shape("poly", limb_poly([(118, 196), (104, 210)], [36, 34]), trim, depth=0.22, tex="fur", tex_amt=0.8)
    p.shape("ellipse", (74, 194, 104, 222), bone_c, depth=0.25, tex="bone")
    for i, y in enumerate((198, 206, 214)):
        p.shape("line", [(80, y), (68, y + 3), (72, y + 8)], bone_c, width=6.5, line=1.2, depth=0.3, rim=0)
        if i != 1:
            p.shape("rect", (74, y - 3, 80, y + 5), gold, radius=1.5, line=0.8, spec=0.9, rim=0)
    p.shape("ellipse", (75, 204, 81, 210), ruby, line=0.6, gloss=1.0, rim=0)
    # ---- drifting soul motes
    for x, y, r in ((40, 170, 3), (120, 30, 2.4), (300, 40, 3), (350, 190, 2.4), (30, 280, 2.6), (360, 260, 2.2),
                    (130, 280, 2), (280, 110, 2)):
        p.glow((x, y), r * 3.4, glowc, 0.8)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8fff6"))
    return p.finish(ground_shadow=(70, 350, 380, 384))


# ------------------------------------------------------------------ dungeon 2: Mushroom Cave

CAVE_RIM = hexc("#a8ffe8")


def cap_spots(p, clip, spots, glowc, fill=hexc("#f4e0ff"), glow_every=2, strength=0.5):
    for i, (x, y, rx, ry) in enumerate(spots):
        if glow_every and i % glow_every == 0:
            p.glow((x, y), max(rx, ry) * 2.0, glowc, strength)
        p.shape("ellipse", (x - rx, y - ry, x + rx, y + ry), fill, depth=0.28, line=1.1, light=1.35, rim=0, ao=0.2,
                clip=clip)


def gills(p, cx, cy, rx, ry, color, n=26, rot=0.0):
    """The gill-lined underside of a cap: a flat ellipse with radial lines converging on the stem."""
    m = p.shape("poly", ell_pts(cx, cy, rx, ry, rot=rot), color, depth=0.3, rim=0, line=1.3)
    for i in range(n):
        t = math.pi * (0.02 + 0.96 * i / (n - 1))
        x0, y0 = cx - rx * math.cos(t) * 0.96, cy + ry * math.sin(t) * 0.3
        p.stroke([(x0, y0), (cx + (x0 - cx) * 0.35, cy + ry * 0.75)], shade(color, 0.72), 1.1)
    return m


def little_shroom(p, x, y, s, capc, stem=hexc("#f1e3c6"), glow=None, lean=0.0):
    if glow:
        p.glow((x + lean * 10 * s, y - 16 * s), 20 * s, glow, 0.6)
    p.shape("poly", taper([(x, y), (x + lean * 6 * s, y - 14 * s)], 6 * s, 4.5 * s), stem, depth=0.3, line=1.0, rim=0)
    cx, cy = x + lean * 8 * s, y - 14 * s
    m = p.shape("poly", ell_pts(cx, cy, 11 * s, 10 * s, 180, 360, rot=lean * 20) + [(cx + 11 * s, cy + 1)], capc,
                depth=0.25, light=1.45, line=1.1, rim=0, gloss=0.6)
    p.flat("ellipse", (cx - 5 * s, cy - 7 * s, cx - 1 * s, cy - 4 * s), hexc("#fff4e0", 220))
    return m


def mushroom_mage():
    """A mischievous mushroom wizard: a tall drooping purple cap with glowing spots, a sly stem face above a
    stringy white gill-beard, a mossy robe, a gnarled staff topped with a glowing spore pod, and a handful of
    glowing spores ready to throw (faces left)."""
    cap = hexc("#8a48c4")
    stem = hexc("#f1e3c6")
    robe = hexc("#4f6b3c")
    moss = hexc("#76a844")
    spore = hexc("#8dff6a")
    wood = hexc("#6b4428")
    p = Pen(256, REG, rim=CAVE_RIM, fit=(0.95, 140, 240))
    p.glow((120, 140), 120, hexc("#8a48c4"), 0.12)
    # ---- the staff behind, gnarled, with a crook holding a glowing spore pod
    st = [(208, 238), (214, 170), (210, 110), (218, 60), (212, 36)]
    p.shape("poly", limb_poly(st, [9, 10, 9, 10, 8]), wood, depth=0.3, tex="wood", tex_amt=1.0)
    for x, y in ((212, 150), (214, 96)):
        p.shape("ellipse", (x - 6, y - 4, x + 6, y + 4), shade(wood, 1.1), depth=0.3, line=1.0, rim=0, tex="wood")
    p.shape("poly", taper([(212, 40), (226, 26), (236, 36), (228, 50)], 7, 4), wood, depth=0.3, tex="wood")
    p.glow((224, 28), 36, spore, 0.85)
    pod = p.shape("ellipse", (206, 8, 242, 44), hexc("#7de35a"), depth=0.25, light=1.5, gloss=1.0, rim=0.2)
    p.glow_clip((224, 28), 16, hexc("#e8ffd0"), 0.8, pod)
    for x, y in ((214, 20), (230, 16), (236, 30), (218, 36)):
        p.flat("ellipse", (x - 2, y - 2, x + 2, y + 2), hexc("#f4ffe8"))
    for pts in ([(208, 42), (200, 30)], [(236, 40), (244, 30)]):  # little tendrils holding the pod
        p.shape("poly", taper(pts, 4, 1.5), shade(wood, 1.1), depth=0.3, line=0.9, rim=0)
    # ---- robe: mossy, belted, with a hem of moss clumps and root toes peeking out
    for x in (104, 150):
        p.shape("poly", curve([(x, 224), (x - 22, 230), (x - 26, 238), (x + 10, 238), (x + 14, 228)], 4),
                hexc("#8a6a4a"), depth=0.25, tex="wood", tex_amt=0.6)
    rb = p.shape("poly", curve([(104, 118), (160, 116), (176, 160), (196, 228), (160, 234), (128, 228), (96, 234),
                                (62, 228), (84, 164)], 5), robe, depth=0.12, tex="cloth", tex_amt=0.9)
    for pts in ([(112, 150), (100, 200), (94, 228)], [(152, 150), (164, 200), (170, 228)]):
        p.stroke(curve(pts, 5), shade(robe, 0.6), 2)
    for x, y, w in ((74, 226, 22), (108, 230, 20), (150, 230, 22), (184, 224, 20), (130, 232, 14)):
        p.shape("ellipse", (x - w / 2, y - w * 0.32, x + w / 2, y + w * 0.32), moss, depth=0.3, tex="fur", line=1.1,
                tex_amt=0.9, rim=0)
    p.shape("poly", taper([(82, 174), (130, 180), (182, 172)], 12, 12), hexc("#6a4428"), depth=0.3, tex="leather")
    p.shape("ellipse", (122, 170, 138, 188), hexc("#e7b440"), depth=0.3, spec=1.0, line=1.1)
    for x, c in ((156, "#ff6ad0"), (168, "#6ae0ff")):  # little potion vials on the belt
        p.shape("rect", (x - 1.6, 180, x + 1.6, 184), hexc("#c8b8a8"), radius=1, line=0.8, rim=0)
        p.shape("ellipse", (x - 5, 183, x + 5, 195), hexc(c, 220), depth=0.3, light=1.5, gloss=1.0, line=1.0, rim=0)
    p.shape("rect", (92, 178, 110, 198), hexc("#8a5a32"), radius=4, depth=0.25, tex="leather")
    p.shape("chord", (91, 174, 111, 188), hexc("#7a4a2a"), start=0, end=180, depth=0.3, line=1.0)
    # leafy collar
    for a in range(-60, 241, 30):
        t = math.radians(a)
        x, y = 132 + 38 * math.cos(t), 128 + 12 * math.sin(t)
        pts = [(x - 7, y), (x + math.cos(t) * 12, y + 10 + math.sin(t) * 4), (x + 7, y)]
        p.shape("poly", curve([pts[0], ((pts[0][0] + pts[1][0]) / 2 - 3, (pts[0][1] + pts[1][1]) / 2), pts[1],
                               ((pts[2][0] + pts[1][0]) / 2 + 3, (pts[2][1] + pts[1][1]) / 2), pts[2]], 3),
                moss, depth=0.3, line=1.0, rim=0, tex="leather", tex_amt=0.4)
    # ---- back arm gripping the staff
    p.shape("poly", limb_poly([(168, 134), (192, 150), (204, 150)], [22, 18, 16]), shade(robe, 0.92), depth=0.2,
            tex="cloth", tex_amt=0.8)
    p.shape("ellipse", (200, 140, 222, 162), stem, depth=0.25, tex="bone", tex_amt=0.4)
    for y in (146, 152, 158):
        p.stroke([(203, y), (214, y - 1)], shade(stem, 0.6), 1.1)
    # ---- the face on the stem, a stringy white gill-beard below it
    beard = p.union([("poly", curve([(96, 150), (112, 186), (126, 214), (136, 190), (150, 204), (158, 176),
                                     (166, 148)], 4))])
    p.paint_mask(beard, hexc("#f4eef8"), depth=0.16, tex="fur", tex_amt=0.8)
    for pts in ([(112, 160), (118, 190)], [(130, 160), (128, 204)], [(146, 160), (148, 190)], [(156, 158), (156, 176)]):
        p.stroke(curve(pts, 3), hexc("#c8b8d8"), 1.3)
    face = p.shape("ellipse", (92, 92, 168, 168), stem, depth=0.14, tex="bone", tex_amt=0.5)
    p.flat("ellipse", (96, 138, 110, 148), hexc("#ff8a9a", 110))
    p.flat("ellipse", (146, 136, 160, 146), hexc("#ff8a9a", 100))
    mean_eye(p, 112, 124, 8.5, 9.5, hexc("#6a3aa8"), stem, brow_tilt=-0.1, lid=0.42, look=(-0.7, 0.2))
    mean_eye(p, 146, 122, 7.5, 8.5, hexc("#6a3aa8"), stem, brow_tilt=0.35, lid=0.3, look=(-0.7, 0.2))
    p.shape("poly", [(98, 106), (122, 104), (122, 109), (99, 111)], hexc("#7a5a4a"), depth=0.3, line=1.0, rim=0)
    p.shape("poly", [(136, 106), (158, 98), (160, 103), (138, 111)], hexc("#7a5a4a"), depth=0.3, line=1.0, rim=0)
    sm = p.shape("poly", curve([(106, 146), (122, 152), (140, 150), (152, 140), (146, 156), (128, 162), (110, 156)], 4),
                 hexc("#4a1a2a"), depth=0.3, line=1.2, rim=0)
    p.shape("ellipse", (116, 150, 136, 164), hexc("#d06070"), **NOLINE, clip=sm)
    p.shape("rect", (138, 145, 143, 151), WHITE, radius=1, line=0.6, rim=0, ao=0)
    p.shape("ellipse", (120, 128, 132, 142), shade(stem, 0.95), depth=0.3, line=1.0, rim=0)  # button nose
    # ---- the tall drooping cap: gills, then the dome, whose tip flops back over the staff
    gills(p, 128, 100, 84, 13, hexc("#d8b8c8"), rot=-4)
    p.shadow_on(p._mask("ellipse", (44, 92, 212, 112)), 0.5, 3, 4)
    capm = p.shape("poly", curve([(40, 104), (52, 72), (78, 44), (110, 22), (150, 6), (186, 4), (206, 18),
                                  (194, 30), (178, 40), (190, 64), (206, 84), (216, 98), (196, 106), (128, 110),
                                  (60, 110)], 5), cap, depth=0.12, light=1.3, spec=0.3, tex="leather", tex_amt=0.5)
    p.shape("poly", ell_pts(128, 102, 90, 10, rot=-4), shade(cap, 0.72), depth=0.35, rim=0, line=1.3)
    cap_spots(p, capm, ((74, 76, 13, 10), (116, 48, 15, 12), (160, 60, 12, 10), (100, 88, 8, 6), (182, 86, 10, 8),
                        (150, 24, 8, 6), (56, 96, 6, 5), (140, 90, 7, 5)), spore,
              fill=hexc("#f4e0ff"), glow_every=3)
    p.glow((196, 14), 12, spore, 0.6)
    p.shape("ellipse", (188, 4, 206, 22), hexc("#d8ffc8"), depth=0.25, light=1.4, line=1.1, rim=0)  # cap-tip bobble
    # ---- the front arm thrust forward, a ball of glowing spores in the palm
    p.shape("poly", limb_poly([(98, 138), (74, 156), (58, 158)], [24, 20, 22]), shade(robe, 1.05), depth=0.2,
            tex="cloth", tex_amt=0.8)
    p.shape("poly", limb_poly([(70, 150), (58, 156)], [24, 26]), moss, depth=0.3, tex="fur", tex_amt=0.8)
    hand = p.shape("poly", curve([(56, 150), (40, 148), (30, 152), (32, 160), (46, 164), (58, 164)], 4), stem,
                   depth=0.25, tex="bone", tex_amt=0.4)
    for x in (36, 42):
        p.shape("poly", taper([(x, 150), (x - 3, 140)], 5, 3.5), stem, depth=0.3, line=1.0, rim=0)
    p.glow((36, 126), 40, spore, 0.85)
    ball = p.shape("ellipse", (22, 112, 50, 140), hexc("#b8ff8a", 200), depth=0.25, light=1.5, line=1.1,
                   ink=hexc("#2a8a3a"), rim=0, gloss=0.9)
    p.glow_clip((36, 126), 12, hexc("#ffffff"), 0.7, ball)
    for x, y, r in ((12, 110, 3), (20, 94, 2.4), (8, 132, 2.2), (46, 98, 2), (4, 100, 1.8), (30, 84, 1.8),
                    (60, 118, 1.8), (200, 110, 2), (236, 70, 2), (180, 16, 1.8), (30, 190, 2)):
        p.glow((x, y), r * 3.4, spore, 0.75)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8ffd8"))
    # ---- little mushrooms at the feet
    little_shroom(p, 44, 238, 1.0, hexc("#e0503a"))
    little_shroom(p, 56, 240, 0.7, hexc("#f0a040"), lean=0.4)
    little_shroom(p, 222, 240, 0.85, hexc("#5affc8"), glow=hexc("#5affc8"), lean=-0.3)
    return p.finish(ground_shadow=(40, 224, 236, 250))


def cave_slime():
    """A big translucent green slime lurching forward with its soft-serve tip, a swallowed skull, bone and coin
    floating inside, bubbles rising, acid dripping and a dopey, drooling grin (faces left)."""
    slime = hexc("#6ad65a")
    deep = hexc("#1f7a3a")
    ink = hexc("#1f5a2a")
    p = Pen(256, REG, rim=hexc("#e0ffc8"), fit=(0.93, 124, 244))
    # ---- the acid puddle it sits in
    pud = p.shape("poly", curve([(12, 230), (40, 220), (120, 222), (210, 218), (246, 228), (236, 244), (160, 250),
                                 (60, 250), (16, 242)], 4), hexc("#8ae85a", 200), shadow=0.8, light=1.3, depth=0.3,
                  line=1.2, rim=0, ao=0, ink=ink)
    p.glow((128, 170), 120, slime, 0.28)
    # ---- what it swallowed (drawn first, seen through the jelly)
    p.shape("poly", taper([(146, 204), (196, 176)], 11, 11), hexc("#e8e0c0"), depth=0.3, line=1.2, rim=0)
    for x, y in ((146, 204), (196, 176)):
        for dx, dy in ((-3, -4), (3, 4)):
            p.shape("ellipse", (x + dx - 7, y + dy - 7, x + dx + 7, y + dy + 7), hexc("#e8e0c0"), depth=0.3, line=1.2,
                    rim=0)
    sk = p.union([("ellipse", (160, 110, 206, 150)), ("rect", (168, 136, 198, 158), {"radius": 5})])
    p.paint_mask(sk, hexc("#ece4c8"), depth=0.2, line=1.3, rim=0, tex="bone", tex_amt=0.6)
    for x, y in ((174, 132), (192, 132)):
        p.shape("ellipse", (x - 6, y - 6, x + 6, y + 6), hexc("#2a2020"), **NOLINE)
    for x in range(172, 198, 5):
        p.stroke([(x, 150), (x, 157)], hexc("#6a6050"), 1.1)
    p.shape("ellipse", (100, 196, 124, 210), hexc("#e8c040"), depth=0.3, light=1.5, spec=1.0, line=1.2, rim=0)
    p.shape("poly", [(206, 206), (214, 200), (222, 206), (214, 214)], hexc("#e04a8a"), line=1.1, gloss=1.0, rim=0,
            depth=0.3)
    # a rusty sword some adventurer lost in it: the blade is inside, the hilt pokes out top-right
    steel = hexc("#aab4bc")
    p.shape("poly", taper([(236, 104), (204, 170), (198, 184)], 13, 2), shade(steel, 0.72), depth=0.25, light=1.4,
            spec=0.8, line=1.5, rim=0, tex="metal", tex_amt=0.5)
    p.stroke([(234, 110), (204, 172)], hexc("#dfe8ee"), 1.4)
    for x, y, r in ((222, 132, 4), (212, 152, 3.2), (206, 166, 2.6)):
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#9a5a2a", 200))  # rust
    # ---- the blob: translucent jelly with a curled tip leaning toward the player
    body = p.union([("ellipse", (26, 88, 232, 238)), ("rect", (22, 168, 236, 236), {"radius": 34}),
                    ("poly", curve([(40, 196), (22, 204), (8, 214), (4, 226), (14, 232), (40, 232)], 4)),
                    ("poly", curve([(160, 96), (140, 64), (116, 44), (90, 34), (68, 38), (62, 48), (78, 50),
                                    (100, 58), (112, 76), (96, 104)], 5))])
    p.paint_mask(body, slime[:3] + (168,), depth=0.1, light=1.3, rim=0.8, line=1.8, ink=ink)
    p.vgrad(body, hexc("#000000", 0), deep[:3] + (120,), 110, 236)
    p.glow_clip((150, 250), 110, hexc("#d8ff8a"), 0.55, body)  # light scattering up from the base
    p.glow_clip((70, 110), 60, hexc("#f0ffe0"), 0.35, body)
    # bubbles
    for x, y, r in ((150, 86, 7), (206, 150, 5), (54, 196, 6), (86, 214, 4), (220, 196, 4), (138, 170, 3.5),
                    (124, 62, 3.5), (182, 196, 3), (40, 170, 3)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#d8ffb8", 90), shadow=0, light=0, line=0.9,
                ink=hexc("#2a8a3a", 190), rim=0, ao=0)
        p.flat("ellipse", (x - r * 0.6, y - r * 0.62, x - r * 0.08, y - r * 0.12), hexc("#ffffff", 220))
    # glossy highlights along the top-left
    hl = p._mask("poly", curve([(44, 132), (52, 112), (70, 98), (88, 94), (76, 106), (62, 122), (52, 140)], 4))
    p.fill_mask(_blur(hl, 2 * SS), hexc("#ffffff", 210))
    for x, y, r in ((96, 44, 4), (78, 42, 2.6), (40, 152, 3), (206, 110, 4)):
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffffff", 200))
    # the sword's hilt sticking out of the jelly
    p.shape("poly", taper([(238, 100), (228, 122)], 12, 12), steel, depth=0.25, light=1.4, spec=0.8, line=1.2, rim=0)
    p.shape("poly", taper([(250, 72), (240, 96)], 9, 9), hexc("#6a3e24"), depth=0.25, tex="wood", tex_amt=0.6,
            line=1.2)
    for t in (0.3, 0.7):
        x, y = 250 - 10 * t, 72 + 24 * t
        p.stroke([(x - 4, y - 1), (x + 4, y + 1)], hexc("#3a2214"), 1.0)
    p.shape("poly", taper([(222, 90), (256, 106)], 8, 8), hexc("#b08a3a"), depth=0.25, light=1.4, spec=0.9, line=1.2,
            rim=0, tex="metal", tex_amt=0.4)
    p.shape("ellipse", (245, 60, 259, 74), hexc("#c8a040"), depth=0.3, light=1.5, spec=1.0, line=1.1, rim=0)
    # ---- the dopey face
    mean_eye(p, 76, 128, 16, 18, hexc("#2a7a2a"), slime, brow_tilt=0.0, lid=0.0, look=(-0.6, 0.35))
    mean_eye(p, 122, 120, 12, 14, hexc("#2a7a2a"), slime, brow_tilt=0.0, lid=0.0, look=(-0.2, -0.4))
    for x0, y0, x1, y1 in ((56, 98, 92, 108), (108, 104, 136, 92)):
        p.stroke(curve([(x0, y0), ((x0 + x1) / 2, min(y0, y1) - 3), (x1, y1)], 3), ink, 3.0)
    mouth = p.shape("poly", curve([(46, 150), (80, 158), (118, 156), (144, 144), (140, 166), (118, 190), (86, 196),
                                   (58, 182)], 5), hexc("#1f4a24"), depth=0.25, line=1.5, rim=0, ink=ink)
    p.shape("ellipse", (70, 170, 124, 206), hexc("#ff7a8a"), depth=0.3, light=1.3, line=0, rim=0, ao=0, clip=mouth)
    p.stroke(curve([(96, 176), (98, 190)], 2), hexc("#c04a5a"), 1.4)
    p.shape("rect", (84, 154, 97, 167), WHITE, radius=2.5, line=1.0, rim=0, ao=0, depth=0.3)
    p.shape("rect", (110, 153, 120, 163), WHITE, radius=2.5, line=1.0, rim=0, ao=0, depth=0.3)
    p.flat("ellipse", (46, 150, 62, 162), hexc("#ff8a8a", 90))
    p.flat("ellipse", (132, 140, 146, 152), hexc("#ff8a8a", 70))
    p.shape("poly", taper([(60, 186), (58, 200), (60, 212)], 7, 2), hexc("#b8ff5a", 220), depth=0.3, light=1.3,
            line=1.0, ink=ink, rim=0, ao=0)  # drool
    # ---- acid drips and sizzling bubbles
    for x, y, r in ((40, 214, 4.5), (60, 222, 4), (204, 216, 4), (226, 206, 3.2)):
        drop(p, x, y, r, hexc("#b8ff5a", 230))
    for x, y, r in ((28, 236, 3), (238, 234, 2.6), (130, 242, 3), (176, 244, 2.4), (90, 244, 2)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#d8ffb8", 120), shadow=0, light=0, line=0.9, ink=ink,
                rim=0, ao=0)
    for x, y, r in ((20, 196, 2), (240, 176, 2), (180, 40, 2), (40, 70, 1.8)):
        p.glow((x, y), r * 3.4, hexc("#b8ff5a"), 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#f0ffe0"))
    return p.finish(ground_shadow=(14, 222, 244, 252))


def toad_hand(p, x, y, color, s=1.0, far=False, pad=None):
    """Splayed toad fingers on the ground ending in round pads, spread around (x, y)."""
    pad = pad or shade(color, 1.15)
    for a in (-160, -125, -90, -55) if not far else (-150, -110, -70):
        t = math.radians(a)
        tip = (x + math.cos(t) * 13 * s, y + 5 * s + math.sin(t) * -2 * s)
        tip = (x + math.cos(t) * 14 * s, y + abs(math.sin(t)) * 3 * s)
        p.shape("poly", taper([(x, y - 3 * s), ((x + tip[0]) / 2, y - 2 * s), tip], 7 * s, 4.5 * s), color,
                depth=0.3, line=1.0, rim=0, tex="leather", tex_amt=0.4)
        p.shape("ellipse", (tip[0] - 3.4 * s, tip[1] - 3 * s, tip[0] + 3.4 * s, tip[1] + 3 * s), pad, depth=0.3,
                light=1.35, line=0.9, rim=0, ao=0)


def toxic_toad():
    """A fat, grumpy poison toad: purple warty hide with green blotches and glowing yellow warts, oozing glands
    behind its bulging slit-pupilled eyes, a glowing poison throat sac and a long sticky tongue (faces left)."""
    purple = hexc("#7a4aa0")
    green = hexc("#7fb84a")
    belly = hexc("#dfe89a")
    wart = hexc("#ffd84a")
    pink = hexc("#f07a9a")
    poison = hexc("#9aff4a")
    p = Pen(256, REG, rim=CAVE_RIM, fit=(0.92, 140, 240))
    # ---- poison puddle, the far hind foot and the far front leg
    p.shape("poly", curve([(4, 228), (40, 222), (90, 226), (96, 238), (50, 246), (6, 240)], 4), hexc("#8ae84a", 190),
            shadow=0.8, light=1.3, depth=0.3, line=1.1, rim=0, ao=0, ink=hexc("#2a6a1a"))
    fp = shade(purple, 0.72)
    p.shape("poly", curve([(214, 206), (236, 214), (240, 228), (206, 232), (184, 226)], 4), fp, depth=0.25,
            tex="leather", tex_amt=0.6)
    p.shape("poly", limb_poly([(120, 176), (116, 204), (110, 222)], [22, 14, 12]), fp, depth=0.2, tex="leather",
            tex_amt=0.6)
    toad_hand(p, 110, 226, fp, 0.9, far=True)
    # ---- body and head as one squat, lumpy mass
    bm = p.union([("ellipse", (62, 76, 236, 228)), ("ellipse", (14, 92, 150, 196)),
                  ("ellipse", (100, 70, 200, 140))])
    p.paint_mask(bm, purple, depth=0.1, light=1.28, tex="leather", tex_amt=0.9, gloss=0.25)
    for box in ((150, 96, 200, 130), (190, 136, 226, 170), (94, 96, 124, 114), (128, 132, 160, 152),
                (206, 104, 230, 124), (60, 128, 86, 144)):
        p.shape("poly", curve(ell_pts((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2,
                                      (box[3] - box[1]) / 2, step=40), 3), green, depth=0.3, line=1.0, rim=0, ao=0,
                clip=bm, tex="leather", tex_amt=0.7)
    bel = p.shape("ellipse", (30, 158, 176, 240), belly, depth=0.2, line=1.1, rim=0, clip=bm, tex="leather",
                  tex_amt=0.6)
    for x in (70, 90, 110, 130, 150):
        p.stroke([(x, 200), (x + 3, 220)], shade(belly, 0.76), 1.3)
    # glowing warts
    for x, y, r in ((136, 88, 6), (170, 84, 5), (206, 100, 6), (160, 124, 4.5), (222, 146, 4.5), (112, 108, 4),
                    (184, 150, 5), (92, 88, 3.5), (200, 124, 3.5), (146, 150, 3.5), (224, 178, 4)):
        p.glow((x, y), r * 3.0, wart, 0.5)
        p.shape("ellipse", (x - r, y - r, x + r, y + r), wart, depth=0.3, light=1.5, line=1.0, rim=0, ao=0.2)
        p.flat("ellipse", (x - r * 0.5, y - r * 0.5, x, y), hexc("#fffbe0"))
    # oozing poison glands behind the eyes
    for x, y, rx, ry in ((132, 104, 16, 10), (96, 98, 11, 7)):
        p.glow((x, y), rx * 1.8, poison, 0.55)
        g = p.shape("ellipse", (x - rx, y - ry, x + rx, y + ry), hexc("#b8f06a"), depth=0.3, light=1.45, line=1.1,
                    rim=0, gloss=0.8, ink=hexc("#2a6a1a"))
        for dx, dy in ((-rx * 0.45, 0.2), (0, -0.3), (rx * 0.45, 0.25)):
            p.glow((x + dx, y + dy * ry), 3, hexc("#f0ffb0"), 0.8)
            p.flat("ellipse", (x + dx - 1.3, y + dy * ry - 1.3, x + dx + 1.3, y + dy * ry + 1.3), hexc("#f8ffe0"))
    drop(p, 140, 124, 3.2, hexc("#b8ff6a", 235), line=0.9)
    # ---- near hind leg: a big folded thigh and a long webbed foot flat on the ground
    thigh = p.shape("poly", curve([(158, 150), (190, 136), (226, 150), (236, 186), (226, 214), (196, 222),
                                   (166, 206), (154, 178)], 5), purple, depth=0.14, tex="leather", tex_amt=0.9)
    p.shape("ellipse", (184, 158, 214, 182), green, depth=0.3, line=0.9, rim=0, ao=0, clip=thigh, tex="leather")
    p.stroke(curve([(170, 196), (196, 210), (220, 204)], 4), shade(purple, 0.6), 1.5)
    foot = p.shape("poly", curve([(206, 212), (178, 222), (150, 224), (132, 222), (126, 232), (136, 238), (168, 238),
                                  (206, 234), (222, 222)], 4), green, depth=0.25, tex="leather", tex_amt=0.6)
    for x in (134, 146, 158):
        p.shape("ellipse", (x - 5, 230, x + 5, 239), shade(green, 1.15), depth=0.3, light=1.35, line=0.9, rim=0,
                ao=0)
    p.stroke(curve([(140, 226), (160, 226), (180, 222)], 3), shade(green, 0.66), 1.2)
    # ---- the glowing poison throat sac
    p.glow((66, 184), 46, poison, 0.65)
    sac = p.shape("ellipse", (28, 152, 104, 214), hexc("#a8f070", 225), depth=0.2, light=1.4, line=1.5,
                  ink=hexc("#2a6a1a"), rim=0.4, gloss=0.9)
    p.glow_clip((64, 194), 30, hexc("#f0ffd0"), 0.7, sac)
    for pts in ([(44, 176), (52, 200)], [(66, 168), (68, 206)], [(88, 172), (84, 200)]):
        p.stroke(curve(pts, 3), hexc("#7ac84a", 170), 1.3)
    # ---- wide grumpy mouth, the tongue flicking out of the front
    p.shape("poly", curve([(14, 136), (40, 146), (80, 148), (112, 146), (130, 158), (126, 164), (108, 156), (80, 160),
                           (40, 158), (16, 148)], 5), hexc("#3a1440"), depth=0.3, line=1.3, rim=0)
    p.stroke(curve([(20, 132), (44, 142), (84, 144), (112, 142), (132, 154)], 5), shade(purple, 1.3), 1.8)
    tongue = [(30, 152), (10, 164), (-2, 186), (6, 206), (22, 208)]
    tm = p.union([("poly", limb_poly(tongue, [13, 12, 11, 12, 10])), ("ellipse", (6, 194, 34, 218))])
    p.paint_mask(tm, pink, depth=0.25, light=1.35, gloss=0.7, tex="leather", tex_amt=0.4)
    p.stroke(curve([(26, 156), (8, 170), (2, 188)], 4), shade(pink, 0.6), 1.8)
    for x, y in ((24, 212), (32, 214)):
        p.shape("poly", taper([(x, y), (x - 1, y + 7)], 3, 1), hexc("#ffc0d0", 220), depth=0.3, line=0.8, rim=0, ao=0)
    # nostrils
    p.flat("ellipse", (22, 118, 28, 124), hexc("#2a1030"))
    p.flat("ellipse", (34, 114, 40, 120), hexc("#2a1030"))
    # ---- near front leg: a bent arm and splayed fingers
    arm = p.union([("ellipse", (82, 158, 124, 200)), ("poly", limb_poly([(104, 184), (88, 204), (76, 222)],
                                                                            [26, 18, 15]))])
    p.paint_mask(arm, purple, depth=0.16, tex="leather", tex_amt=0.8)
    p.shape("ellipse", (92, 168, 112, 184), green, depth=0.3, line=0.9, rim=0, ao=0, clip=arm, tex="leather")
    toad_hand(p, 74, 224, green)
    # poison drool from the corner of the mouth
    p.shape("poly", taper([(126, 162), (124, 176), (128, 188)], 6, 3), hexc("#9aff4a", 230), depth=0.3, line=1.0,
            rim=0, ink=hexc("#2a6a1a"))
    drop(p, 128, 196, 4, hexc("#b8ff6a", 235), line=0.9)
    # ---- bulging eyes: the far one behind, the near one big, gold with a horizontal slit, lids scowling
    for cx, cy, r, far in ((104, 76, 18, True), (54, 84, 24, False)):
        col = shade(purple, 0.85) if far else purple
        p.shape("ellipse", (cx - r, cy - r, cx + r, cy + r * 0.92), col, depth=0.2, tex="leather", tex_amt=0.6)
        er = r * 0.74
        e = p.shape("ellipse", (cx - er, cy - er * 0.92, cx + er, cy + er * 0.86), hexc("#ffcf3a"), light=1.5,
                    depth=0.25, line=1.1, rim=0)
        p.shape("ellipse", (cx - er * 0.8, cy - er * 0.3, cx + er * 0.7, cy + er * 0.9), hexc("#ff9a1a"), **NOLINE,
                clip=e)
        p.flat("ellipse", (cx - er * 0.95, cy - er * 0.2, cx + er * 0.55, cy + er * 0.22), DARK)
        p.flat("ellipse", (cx - er * 0.6, cy - er * 0.7, cx - er * 0.2, cy - er * 0.35), WHITE)
        lid = [(cx - r - 2, cy - r - 4), (cx + r + 2, cy - r - 4), (cx + r + 2, cy + r * 0.1), (cx - r - 2, cy - r * 0.5)]
        p.shape("poly", lid, col, depth=0.3, line=1.2, rim=0, tex="leather",
                clip=p._mask("ellipse", (cx - r, cy - r, cx + r, cy + r * 0.92)))
        p.stroke([(cx - r * 0.9, cy - r * 0.46), (cx + r * 0.9, cy + r * 0.06)], DARK, 2.0)
    # ---- rising poison bubbles
    for x, y, r in ((30, 100, 3.5), (12, 72, 2.6), (150, 50, 2.8), (180, 60, 2), (240, 120, 2.2), (70, 40, 2)):
        p.glow((x, y), r * 3.2, poison, 0.6)
        p.shape("ellipse", (x - r, y - r, x + r, y + r), hexc("#d0ff8a", 170), shadow=0, light=0, line=0.9,
                ink=hexc("#3a8a2a", 200), rim=0, ao=0)
        p.flat("ellipse", (x - r * 0.6, y - r * 0.6, x - r * 0.1, y - r * 0.2), hexc("#ffffff", 230))
    return p.finish(ground_shadow=(14, 220, 246, 250))


def membrane_wing(p, shoulder, elbow, wrist, fingers, attach, mem, bone_c, width=7, scallop=0.26, edge=None,
                  veins=None, alpha=240, thumb=hexc("#f0e6cc")):
    """A bat or dragon wing: arm bones shoulder-elbow-wrist, finger bones fanning from the wrist, a scalloped
    membrane between the fingers that ends at `attach` on the body, optional glowing veins and edge."""
    edge_pts = [fingers[0]]
    prev = fingers[0]
    for f in fingers[1:] + [attach]:
        mx, my = (prev[0] + f[0]) / 2, (prev[1] + f[1]) / 2
        k = scallop if f is not attach else scallop * 0.8
        edge_pts += [(mx + (wrist[0] - mx) * k, my + (wrist[1] - my) * k), f]
        prev = f
    outline = [shoulder, elbow, wrist] + curve(edge_pts, 6) + [shoulder]
    m = p._mask("poly", outline)
    p.paint_mask(m, mem[:3] + (alpha,), depth=0.08, light=1.25, tex="leather", tex_amt=0.45)
    for f in fingers:  # the membrane sags between the bones: shade along each bone
        mx, my = (wrist[0] + f[0]) / 2, (wrist[1] + f[1]) / 2
        p.stroke([wrist, f], shade(mem, 0.62)[:3] + (90,), width * 1.6, soft=2.0)
    if veins:
        for f0, f1 in zip(fingers, fingers[1:] + [attach]):
            mx, my = (f0[0] + f1[0]) / 2, (f0[1] + f1[1]) / 2
            pts = curve([wrist, ((wrist[0] + mx) / 2 + 3, (wrist[1] + my) / 2 - 2), (mx, my)], 5)
            p.stroke(pts[: int(len(pts) * 0.8)], veins[:3] + (150,), 1.6, soft=0.6)
    if edge:
        p.stroke(curve(edge_pts, 6), edge, 2.0)
    for f in fingers:
        p.shape("poly", taper([wrist, f], width * 0.6, width * 0.22), bone_c, depth=0.3, line=1.1, rim=0, ao=0.2)
    p.shape("poly", limb_poly([shoulder, elbow], [width * 1.4, width * 1.0]), bone_c, depth=0.3, light=1.3, rim=0.3)
    p.shape("poly", limb_poly([elbow, wrist], [width * 1.0, width * 0.8]), bone_c, depth=0.3, light=1.3, rim=0.3)
    for (x, y), r in ((elbow, width * 0.62), (wrist, width * 0.6)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), bone_c, depth=0.3, line=1.1, rim=0)
    ux, uy = norm(wrist[0] - elbow[0], wrist[1] - elbow[1])
    claw(p, wrist[0] + ux * width * 0.3, wrist[1] + uy * width * 0.3 - width * 0.3,
         width * 1.4, math.degrees(math.atan2(uy, ux)) - 50, width * 0.7, thumb, 1.0)
    return m


def glow_bat():
    """A cave bat swooping in with glowing cyan wings, huge glowing ears, burning cyan eyes, a leaf nose and
    bared fangs, bioluminescent spots on its fluffy chest (faces left)."""
    fur = hexc("#3c3558")
    fur_l = hexc("#5a5078")
    mem = hexc("#23b8c8")
    glowc = hexc("#5affff")
    bone_c = hexc("#4a4270")
    p = Pen(256, REG, rim=hexc("#9affff"), rot=(-12, 128, 110), fit=(0.86, 142, 120))
    p.glow((128, 110), 128, glowc, 0.2)
    # ---- far wing, spread up and back
    membrane_wing(p, (150, 106), (188, 104), (214, 84), [(254, 58), (254, 118), (238, 160), (200, 172)], (156, 146),
                  shade(mem, 0.78), shade(bone_c, 0.9), width=7, edge=hexc("#aaffff", 200), veins=glowc)
    # ---- dangling feet and the tail membrane
    p.shape("poly", curve([(120, 150), (146, 150), (152, 170), (136, 176), (118, 170)], 4), shade(mem, 0.7)[:3] + (230,),
            depth=0.2, light=1.2, line=1.2, rim=0)
    for x in (122, 144):
        p.shape("poly", taper([(x, 152), (x - 1, 170)], 7, 5), fur, depth=0.3, line=1.1, rim=0)
        for dx in (-4, 0, 4):
            claw(p, x - 1 + dx, 170, 6, 100, 2.6, hexc("#e8e0d0"), 0.8)
    # ---- the round furry body with a fluffy glowing chest
    body = p.union([("ellipse", (98, 84, 166, 160)),
                    ("poly", tufts([(160, 110), (164, 136), (152, 158)], 8, 9, side=1, lean=0.3, seed=7))])
    p.paint_mask(body, fur, depth=0.14, tex="fur", tex_amt=0.9)
    chest = p.union([("ellipse", (106, 108, 152, 162)),
                     ("poly", tufts([(108, 150), (128, 164), (150, 152)], 7, 8, side=-1, lean=0.2, seed=9))])
    p.paint_mask(mul(chest, _pm._dilate(body, 1)), fur_l, depth=0.2, line=0, tex="fur", tex_amt=0.8, rim=0, ao=0)
    for x, y in ((120, 126), (136, 138), (126, 150), (142, 120)):
        p.glow((x, y), 8, glowc, 0.7)
        p.flat("ellipse", (x - 1.8, y - 1.8, x + 1.8, y + 1.8), hexc("#e8ffff"))
    # ---- near wing, swept down and forward
    membrane_wing(p, (106, 102), (74, 70), (54, 34), [(4, 4), (0, 60), (12, 104), (48, 134)], (104, 142), mem,
                  bone_c, width=8, edge=hexc("#c8ffff", 230), veins=glowc)
    for x, y, r in ((22, 40, 3.5), (26, 80, 3), (50, 110, 2.5), (12, 60, 2), (62, 84, 2.2), (228, 100, 3),
                    (230, 134, 2.5), (204, 150, 2)):
        p.glow((x, y), r * 4, glowc, 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#e8ffff"))
    # ---- huge ears with glowing insides
    for pts, inner, c in (([(116, 64), (132, 6), (152, 70)], [(122, 62), (132, 20), (146, 66)], shade(fur, 0.85)),
                          ([(80, 76), (54, 16), (110, 58)], [(84, 68), (62, 28), (102, 58)], fur)):
        p.shape("poly", curve([pts[0], ((pts[0][0] + pts[1][0]) / 2 - 6, (pts[0][1] + pts[1][1]) / 2), pts[1],
                               ((pts[2][0] + pts[1][0]) / 2 + 4, (pts[2][1] + pts[1][1]) / 2), pts[2]], 4), c,
                depth=0.2, tex="fur", tex_amt=0.6)
        cx, cy = sum(q[0] for q in inner) / 3, sum(q[1] for q in inner) / 3
        p.glow((cx, cy), 18, glowc, 0.55)
        im = p.shape("poly", curve([inner[0], inner[1], inner[2]], 3) + [inner[0]], hexc("#7af0f0"), depth=0.3,
                     light=1.45, line=0.9, rim=0, ao=0)
        for t in (0.35, 0.6):
            a = (inner[0][0] + (inner[1][0] - inner[0][0]) * t, inner[0][1] + (inner[1][1] - inner[0][1]) * t)
            b = (inner[2][0] + (inner[1][0] - inner[2][0]) * t, inner[2][1] + (inner[1][1] - inner[2][1]) * t)
            p.stroke([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 3), b], hexc("#2a8a9a", 160), 1.1)
    # ---- the head: fuzzy, a pale muzzle, glowing eyes, leaf nose, fanged snarl
    head = p.union([("ellipse", (72, 54, 150, 128)),
                    ("poly", tufts([(146, 80), (150, 104), (140, 124)], 7, 8, side=1, lean=0.3, seed=11)),
                    ("poly", tufts([(84, 60), (110, 50), (136, 58)], 6, 8, side=1, lean=0.4, seed=12))])
    p.paint_mask(head, fur, depth=0.14, tex="fur", tex_amt=0.9)
    p.shape("ellipse", (74, 88, 126, 128), fur_l, depth=0.2, line=0, rim=0, ao=0, tex="fur", clip=head)
    glowing_eye(p, 96, 84, 8, 7, glowc, hexc("#f0ffff"), socket=hexc("#150c20"), slant=0.4)
    glowing_eye(p, 128, 82, 6.5, 6, glowc, hexc("#f0ffff"), socket=hexc("#150c20"), slant=0.4)
    p.shape("poly", [(82, 70), (108, 78), (106, 83), (82, 76)], hexc("#1a1428"), depth=0.3, line=0.9, rim=0)
    p.shape("poly", [(118, 76), (140, 68), (140, 73), (120, 81)], hexc("#1a1428"), depth=0.3, line=0.9, rim=0)
    mouth = p.shape("poly", curve([(74, 104), (96, 108), (120, 104), (118, 120), (104, 134), (86, 132), (76, 118)],
                                  4), hexc("#4a1028"), depth=0.25, line=1.2, rim=0)
    p.shape("ellipse", (84, 118, 112, 136), hexc("#e06a8a"), depth=0.3, light=1.3, line=0, rim=0, ao=0, clip=mouth)
    fang(p, 82, 106, 6, 13, hexc("#f4f0e0"), line=0.9)
    fang(p, 112, 105, 6, 12, hexc("#f4f0e0"), line=0.9)
    fang(p, 88, 130, 4.5, -7, hexc("#f4f0e0"), line=0.8)
    fang(p, 106, 130, 4.5, -7, hexc("#f4f0e0"), line=0.8)
    p.shape("poly", curve([(88, 90), (94, 86), (102, 90), (100, 100), (94, 104), (88, 100)], 3) + [(88, 90)],
            hexc("#a85a7a"), depth=0.3, line=1.0, rim=0, gloss=0.5)
    for x in (91, 98):
        p.flat("ellipse", (x - 1.4, 97, x + 1.4, 100), hexc("#3a1020"))
    return p.finish(ground_shadow=(84, 226, 184, 244))


def fist(p, cx, cy, r, color, facing=-1, tex="bone", knuckles=4):
    """A big clenched fist: a round mass with finger rolls and a thumb over them (facing -1 = knuckles left)."""
    m = p.shape("ellipse", (cx - r, cy - r * 0.9, cx + r, cy + r * 0.9), color, depth=0.22, tex=tex, tex_amt=0.5)
    for i in range(knuckles):
        y = cy - r * 0.55 + i * r * 1.1 / max(1, knuckles - 1)
        x0 = cx + facing * r * 0.95
        p.shape("ellipse", (x0 - r * 0.32, y - r * 0.26, x0 + r * 0.32, y + r * 0.26), shade(color, 1.03), depth=0.3,
                line=1.0, rim=0, ao=0.2, tex=tex, tex_amt=0.4)
    p.shape("poly", ell_pts(cx + facing * r * 0.3, cy - r * 0.4, r * 0.5, r * 0.24, rot=20 * facing), shade(color, 1.05),
            depth=0.3, line=1.0, rim=0, ao=0.3, tex=tex, tex_amt=0.4)
    return m


def bracket_fungus(p, x, y, w, color, flip=1):
    """A shelf fungus growing out of a surface at (x, y), `w` wide, with growth rings."""
    pts = curve([(x - w / 2, y), (x - w * 0.45, y - w * 0.22), (x, y - w * 0.3), (x + w * 0.45, y - w * 0.2),
                 (x + w / 2, y + w * 0.02), (x, y + w * 0.12)], 4)
    m = p.shape("poly", pts, color, depth=0.3, light=1.35, line=1.1, rim=0, tex="wood_h", tex_amt=0.5)
    for k in (0.7, 0.45):
        p.stroke(curve([(x - w / 2 * k, y - w * 0.02), (x, y - w * 0.3 * k), (x + w / 2 * k, y - w * 0.02)], 3),
                 shade(color, 0.7), 1.1)
    p.stroke(curve([(x - w / 2, y + 0.5), (x, y + w * 0.12), (x + w / 2, y + 0.5)], 3), hexc("#fff0d8"), 1.4)
    return m


def shroom_brute():
    """Elite: a hulking toadstool giant, its cracked red cap pulled low over glowing eyes and a snaggle-toothed
    scowl, fibrous arms thick with moss and shelf fungus, a nail-studded root club in its fist (faces left)."""
    cap = hexc("#d8382e")
    stem = hexc("#efdcbc")
    moss = hexc("#5f9a3a")
    bark = hexc("#7a5030")
    shelf = hexc("#d89a4a")
    spore = hexc("#ffe08a")
    p = Pen(256, REG, rim=CAVE_RIM, fit=(0.94, 128, 240))

    def moss_clump(x, y, w, h, clip=None):
        m = p._mask("poly", tufts([(x - w / 2, y + h * 0.2), (x, y - h / 2), (x + w / 2, y + h * 0.2)], h * 0.5, 5,
                                  side=1, lean=0.2, seed=int(x + y)))
        m = add(m, p._mask("ellipse", (x - w / 2, y - h / 2, x + w / 2, y + h / 2)))
        p.paint_mask(m if clip is None else mul(m, clip), moss, depth=0.3, line=1.0, tex="fur", tex_amt=0.9, rim=0)
    # ---- back arm hanging, huge fist near the ground
    p.shape("poly", limb_poly([(188, 118), (226, 146), (232, 176)], [44, 34, 32]), shade(stem, 0.9), depth=0.16,
            tex="bone", tex_amt=0.6)
    for pts in ([(200, 126), (222, 158)], [(212, 122), (234, 150)]):
        p.stroke(pts, shade(stem, 0.66), 1.2)
    moss_clump(218, 136, 30, 16)
    fist(p, 230, 192, 20, shade(stem, 0.9), facing=-1)
    # ---- stumpy root legs with root toes
    for x in (78, 138):
        p.shape("poly", limb_poly([(x + 22, 180), (x + 20, 208), (x + 18, 226)], [40, 34, 40]), shade(stem, 0.86),
                depth=0.2, tex="bone", tex_amt=0.6)
        p.stroke([(x + 12, 196), (x + 10, 216)], shade(stem, 0.66), 1.2)
        for dx, a in ((-2, 150), (12, 115), (28, 80), (40, 40)):
            p.shape("poly", taper([(x + dx + 2, 224), (x + dx + math.cos(math.radians(a)) * 14, 232 + 2),
                                   (x + dx + math.cos(math.radians(a)) * 20, 238)], 9, 3), hexc("#b89a7a"),
                    depth=0.3, line=1.1, rim=0, tex="wood", tex_amt=0.5)
    # ---- barrel stem body, fibres, a vine belt with a glowing lantern mushroom
    body = p.shape("poly", curve([(64, 110), (196, 108), (214, 150), (204, 190), (130, 202), (58, 192), (48, 150)],
                                 5), stem, depth=0.1, tex="bone", tex_amt=0.7)
    for pts in ([(92, 150), (86, 190)], [(166, 150), (174, 188)], [(130, 176), (130, 198)]):
        p.stroke(pts, shade(stem, 0.78), 1.4)
    p.shape("poly", taper(curve([(54, 180), (130, 190), (208, 176)], 6), 9, 9), hexc("#3f7a34"), depth=0.3, rim=0,
            tex="leather", tex_amt=0.6)
    for x, y in ((80, 186), (150, 190), (190, 182)):
        p.shape("poly", curve([(x - 9, y), (x, y - 4), (x + 9, y), (x, y + 9)], 3) + [(x - 9, y)], hexc("#6ab04a"),
                depth=0.3, line=1.0, rim=0)
    p.glow((170, 198), 18, hexc("#8dff6a"), 0.7)
    p.shape("rect", (167, 190, 173, 206), hexc("#f4ecd8"), radius=2, line=0.9, rim=0)
    p.shape("chord", (158, 180, 182, 198), hexc("#8dff6a"), start=180, end=360, line=1.0, light=1.5, rim=0, gloss=0.8)
    # ---- the face in the cap's shadow: glowing eyes, bark brows, lumpy nose, a snaggle-toothed scowl
    face_sh = p._mask("ellipse", (54, 96, 206, 150))
    p.fill_mask(mul(_blur(face_sh, 6 * SS), body), hexc("#3a2418", 150))
    glowing_eye(p, 104, 140, 8.5, 6.5, hexc("#ffd23a"), socket=hexc("#2a1a14"), slant=0.5)
    glowing_eye(p, 154, 138, 7.5, 6, hexc("#ffd23a"), socket=hexc("#2a1a14"), slant=0.5)
    p.shape("poly", [(84, 124), (122, 136), (120, 143), (82, 132)], hexc("#6a4a3a"), depth=0.3, line=1.1, rim=0,
            tex="wood", tex_amt=0.8)
    p.shape("poly", [(136, 136), (172, 122), (174, 130), (138, 143)], hexc("#6a4a3a"), depth=0.3, line=1.1, rim=0,
            tex="wood", tex_amt=0.8)
    p.shape("poly", curve([(124, 142), (116, 156), (120, 166), (134, 166), (138, 154)], 3) + [(124, 142)],
            shade(stem, 0.92), depth=0.3, line=1.2, rim=0, tex="bone", tex_amt=0.5)
    mouth = p.shape("poly", curve([(90, 184), (110, 172), (146, 172), (170, 180), (158, 192), (106, 194)], 4),
                    hexc("#3a1a1a"), depth=0.25, line=1.3, rim=0)
    p.shape("ellipse", (112, 184, 150, 198), hexc("#8a3a3a"), **NOLINE, clip=mouth)
    fang(p, 104, 190, 10, -15, hexc("#f4ecd4"))
    fang(p, 154, 188, 10, -14, hexc("#f4ecd4"))
    for x in (122, 132, 142):
        fang(p, x, 173, 7, 7 if x != 132 else 9, hexc("#f4ecd4"), line=0.9)
    # ---- the cap: gills, the cracked red dome with a bite out of it, white warts, moss and sprouts
    gills(p, 128, 108, 118, 16, hexc("#e8c8b0"), n=34)
    p.shadow_on(p._mask("ellipse", (10, 94, 246, 124)), strength=0.5, offset=3, blur=4)
    dome = sub(p._mask("poly", ell_pts(128, 110, 120, 106, 180, 360) + [(248, 112), (8, 112)]),
               p._mask("poly", curve([(200, 20), (214, 34), (206, 44), (222, 52), (236, 50)], 3) + [(250, 0)]))
    capm = p.paint_mask(dome, cap, depth=0.12, light=1.3, spec=0.4, tex="leather", tex_amt=0.5)
    p.shape("poly", ell_pts(128, 108, 122, 12), shade(cap, 0.72), depth=0.35, rim=0, line=1.4)
    for x, y, rx, ry in ((58, 58, 18, 13), (126, 28, 22, 14), (190, 64, 18, 12), (94, 82, 11, 8), (34, 88, 9, 7),
                         (222, 88, 10, 7), (160, 82, 12, 8), (134, 62, 7, 5), (88, 36, 8, 6)):
        pts = curve(ell_pts(x, y, rx, ry, step=45), 3)
        p.shape("poly", pts, hexc("#fbf2e0"), depth=0.3, line=1.1, light=1.3, rim=0, ao=0.25, clip=capm,
                tex="bone", tex_amt=0.4)
    for pts in ([(150, 24), (160, 44), (154, 56), (164, 70)], [(66, 90), (74, 100)]):
        p.stroke(pts, shade(cap, 0.45), 2.0)
    moss_clump(70, 30, 30, 12, clip=None)
    moss_clump(178, 30, 26, 10, clip=None)
    for x, y, s in ((84, 24, 1.0), (170, 22, 0.8)):
        little_shroom(p, x, y, s, hexc("#f0a040"))
    # ---- shelf fungus on the shoulder
    bracket_fungus(p, 196, 118, 30, shelf)
    bracket_fungus(p, 214, 132, 22, shade(shelf, 0.9))
    # ---- the club: a gnarled root log studded with nails, gripped in the front fist
    club = limb_poly([(84, 232), (66, 172), (50, 130), (42, 96), (30, 48)], [16, 20, 30, 26, 38])
    cm = p.shape("poly", club, bark, depth=0.14, tex="wood", tex_amt=1.0)
    p.shape("poly", ell_pts(30, 48, 19, 9, rot=-18), hexc("#c89a60"), depth=0.25, line=1.3, rim=0)
    for r in (13, 8, 3.5):
        p.shape("poly", ell_pts(30, 48, r, r * 0.46, rot=-18), (0, 0, 0, 0), shadow=0, light=0, line=0.8,
                ink=hexc("#7a5030"), rim=0, ao=0)
    for x, y, a in ((20, 70, 200), (52, 64, -20), (18, 100, 190), (56, 96, -10), (36, 84, 250)):
        t = math.radians(a)
        p.shape("poly", taper([(x, y), (x + math.cos(t) * 12, y + math.sin(t) * 12)], 4, 1.2), hexc("#9aa2aa"),
                depth=0.3, light=1.5, spec=1.0, line=1.0, rim=0)
        p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), hexc("#6a727a"), line=0.8, rim=0, spec=0.6, depth=0.3)
    for x, y in ((50, 130), (64, 176), (40, 116)):
        p.stroke([(x, y), (x + 3, y + 12)], shade(bark, 0.5), 1.4)
    little_shroom(p, 62, 150, 0.6, hexc("#5affc8"), glow=hexc("#5affc8"), lean=-0.6)
    # ---- front arm, thick and mossy, fist round the club
    p.shape("poly", limb_poly([(84, 124), (54, 150), (58, 170)], [44, 34, 30]), stem, depth=0.16, tex="bone",
            tex_amt=0.6)
    for pts in ([(70, 128), (56, 150)], [(84, 136), (68, 160)]):
        p.stroke(pts, shade(stem, 0.7), 1.2)
    moss_clump(80, 128, 34, 18)
    moss_clump(58, 150, 22, 12)
    fist(p, 60, 172, 19, shade(stem, 0.97), facing=-1)
    # ---- spores puffing off the cap
    for x, y, r in ((20, 20, 2.6), (240, 30, 2.4), (110, 6, 2), (6, 130, 2), (250, 150, 2), (200, 8, 1.8)):
        p.glow((x, y), r * 3.4, spore, 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#fff8e0"))
    return p.finish(ground_shadow=(28, 222, 244, 250))


def leaf(p, x, y, length, angle, color, width=0.42):
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    w = length * width
    tip = (x + ux * length, y + uy * length)
    pts = curve([(x, y), (x + ux * length * 0.4 + nx * w / 2, y + uy * length * 0.4 + ny * w / 2), tip,
                 (x + ux * length * 0.45 - nx * w / 2, y + uy * length * 0.45 - ny * w / 2), (x, y)], 4)
    p.shape("poly", pts, color, depth=0.3, light=1.35, line=1.0, rim=0, ao=0.2)
    p.stroke([(x, y), (x + ux * length * 0.8, y + uy * length * 0.8)], shade(color, 0.7), 1.0)


def vine(p, pts, w0, w1, color, leaves=(), thorn=None):
    p.shape("poly", taper(pts, w0, w1), color, depth=0.2, light=1.3, tex="leather", tex_amt=0.6)
    c = curve(pts, 8)
    for i, (t, side, ln) in enumerate(leaves):
        j = min(len(c) - 2, int(t * (len(c) - 1)))
        (x0, y0), (x1, y1) = c[j], c[j + 1]
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) + 70 * side
        leaf(p, x0, y0, ln, ang, shade(color, 1.3))


def spore_mother():
    """Boss: the Spore Mother, a towering mushroom queen in a gown of gills and ruffles, a glowing bell cap
    crowned with little luminous mushrooms and veiled in glowing threads, a smug half-lidded smile, a dragon
    bone shard burning amber in her breast, vines for arms and spores pouring from her open hand (faces left)."""
    capc = hexc("#8a3ad0")
    glowc = hexc("#d08aff")
    stem = hexc("#f2e6ee")
    vinec = hexc("#3f8a4a")
    spore = hexc("#b8ff7a")
    amber = hexc("#ffb040")
    gown = hexc("#e6d0ec")
    p = Pen(384, BOSS, rim=hexc("#e8c8ff"), fit=(0.93, 192, 372))
    p.glow((192, 140), 220, glowc, 0.24)
    # ---- spore clouds drifting behind
    for x, y, r, col in ((40, 210, 36, "#b98ae0"), (348, 200, 32, "#a0d880"), (330, 110, 24, "#c8a0f0"),
                         (36, 120, 22, "#a0d880")):
        p.glow((x, y), r * 1.6, hexc(col), 0.4)
        for dx, dy, k in ((0, 0, 1.0), (r * 0.8, r * 0.3, 0.7), (-r * 0.7, r * 0.4, 0.6), (r * 0.1, -r * 0.6, 0.6)):
            p.mist((x + dx - r * k, y + dy - r * k * 0.8, x + dx + r * k, y + dy + r * k * 0.8), hexc(col), 120, 3)
    # ---- the back vine arm holding a tall vine sceptre with a glowing bulb
    vine(p, [(310, 372), (318, 300), (306, 230), (318, 160), (312, 118)], 12, 9, shade(vinec, 0.9),
         leaves=((0.25, 1, 18), (0.5, -1, 16), (0.75, 1, 14)))
    p.glow((312, 104), 40, spore, 0.8)
    bulb = p.shape("ellipse", (296, 84, 328, 122), hexc("#c8ff8a"), depth=0.25, light=1.5, gloss=1.0, line=1.3,
                   ink=hexc("#2a6a2a"))
    p.glow_clip((312, 104), 14, hexc("#ffffff"), 0.7, bulb)
    for a in (-60, -20, 20, 60):
        t = math.radians(a - 90)
        p.shape("poly", taper([(312, 120), (312 + math.cos(t) * 22, 104 + math.sin(t) * 26)], 5, 1.5),
                shade(vinec, 1.2), depth=0.3, line=1.0, rim=0)
    vine(p, [(236, 236), (272, 250), (300, 236), (312, 214)], 20, 12, vinec, leaves=((0.4, -1, 14),))
    for i, (x, y) in enumerate(((304, 206), (314, 204), (322, 210))):
        p.shape("poly", taper([(x, y + 6), (x + 4, y - 6), (x + 8, y - 12)], 6, 3), vinec, depth=0.3, line=1.0,
                rim=0)
    # ---- the gown: a stem that flares into ruffled gill skirts and roots
    for pts in ([(96, 350), (60, 360), (26, 374)], [(290, 350), (326, 362), (360, 376)], [(150, 364), (130, 380)],
                [(240, 364), (258, 380)]):
        p.shape("poly", taper(pts, 18, 4), hexc("#c8b0a0"), depth=0.3, tex="wood", tex_amt=0.5)
    skirt = curve([(158, 240), (230, 240), (250, 290), (288, 336), (318, 364), (192, 374), (66, 364), (96, 336),
                   (134, 290)], 6)
    sk = p.shape("poly", skirt, gown, depth=0.1, tex="cloth", tex_amt=0.5)
    for x0, x1 in ((170, 110), (182, 150), (194, 192), (206, 236), (218, 276)):
        p.stroke(curve([(x0, 246), ((x0 + x1) / 2, 310), (x1, 368)], 4), hexc("#b898c8"), 2.0)
    p.vgrad(sk, hexc("#000000", 0), hexc("#5a2a8a", 210), 250, 372)
    # scalloped ruffle tiers
    for y, x0, x1, n in ((300, 116, 270, 7), (340, 84, 302, 9)):
        pts = []
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            pts += [(x, y + 2 + abs(x - 192) * 0.08)]
        edge = []
        for a, b in zip(pts, pts[1:]):
            edge += [a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 12)]
        edge.append(pts[-1])
        band = [(x0 + 6, y - 14 + abs(x0 - 192) * 0.06)] + curve(edge, 4) + [(x1 - 6, y - 14 + abs(x1 - 192) * 0.06)]
        p.shape("poly", band, mix(gown, hexc("#8a5ab8"), (y - 290) / 70), depth=0.2, light=1.3, tex="cloth",
                tex_amt=0.5, clip=_pm._dilate(sk, 12 * SS))
    for x, y, r in ((96, 354, 4), (130, 360, 3.5), (166, 364, 4.5), (222, 364, 4), (258, 360, 3.5), (292, 354, 4),
                    (116, 318, 3), (150, 322, 3.5), (236, 322, 3.5), (270, 316, 3)):
        p.glow((x, y), r * 3.4, glowc, 0.7)
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#f8e8ff"))
    # ---- the dragon bone shard grown into her breast, burning amber
    p.glow((196, 272), 60, amber, 0.85)
    for a, b in (((196, 272), (156, 256)), ((196, 272), (240, 254)), ((196, 272), (230, 300)), ((196, 272), (160, 300))):
        p.stroke(curve([a, ((a[0] + b[0]) / 2 + 4, (a[1] + b[1]) / 2 - 3), b], 4), hexc("#ffb040", 210), 2.6)
    sh = [(176, 252), (208, 236), (228, 262), (218, 298), (186, 306), (168, 280)]
    p.shape("poly", sh, hexc("#f4e2b0"), depth=0.25, light=1.45, line=1.4, tex="bone", tex_amt=0.8, spec=0.6)
    p.stroke([(188, 260), (198, 272), (194, 284), (206, 294)], hexc("#ff9a2a"), 2.6)
    p.stroke([(206, 250), (210, 266)], hexc("#ff9a2a"), 2.0)
    p.sparkle((208, 254), 9, hexc("#fff0b0"))
    # ---- ruffled veil collar under the face
    frill = []
    for i in range(13):
        a = math.radians(180 + i * 15)
        r = 70 if i % 2 == 0 else 58
        frill.append((196 + r * math.cos(a) * 1.0, 214 + 22 + r * 0.42 * math.sin(a) * -1 + (8 if i % 2 else 0)))
    col = p.shape("poly", curve([(126, 222), (196, 206), (266, 222)] + frill[::-1][1:-1], 3), shade(gown, 1.02),
                  depth=0.16, light=1.3, tex="cloth", tex_amt=0.6)
    for x in (148, 172, 196, 220, 244):
        p.stroke([(x, 220), (x + (x - 196) * 0.25, 244)], hexc("#b898c8"), 1.8)
    # ---- the front vine arm reaching toward the player, spores pouring from the open hand
    vine(p, [(160, 234), (122, 250), (94, 236), (74, 214)], 22, 14, vinec, leaves=((0.3, 1, 16), (0.65, -1, 14)))
    hand = p.shape("ellipse", (56, 196, 86, 222), shade(vinec, 1.15), depth=0.25, tex="leather", tex_amt=0.5)
    for a, ln in ((-150, 18), (-120, 20), (-90, 18), (-60, 14)):
        t = math.radians(a)
        p.shape("poly", taper([(68, 206), (68 + math.cos(t) * ln, 206 + math.sin(t) * ln),
                               (68 + math.cos(t - 0.4) * ln * 1.3, 206 + math.sin(t - 0.4) * ln * 1.3)], 7, 2.5),
                shade(vinec, 1.15), depth=0.3, line=1.1, rim=0)
    p.glow((56, 176), 50, spore, 0.8)
    for x, y, r in ((52, 170, 16), (32, 152, 12), (72, 150, 10), (20, 180, 10), (40, 128, 8)):
        p.shape("ellipse", (x - r, y - r * 0.86, x + r, y + r * 0.86), hexc("#d8ffb0", 170), shadow=0.85, light=1.25,
                depth=0.3, line=1.1, ink=hexc("#4a9a3a", 170), rim=0, ao=0)
    # ---- the pale face: a sly, sleepy queen
    face = p.shape("ellipse", (150, 136, 244, 226), stem, depth=0.14, tex="bone", tex_amt=0.4)
    p.flat("ellipse", (154, 190, 176, 202), hexc("#ff9ab8", 120))
    p.flat("ellipse", (216, 188, 236, 200), hexc("#ff9ab8", 100))
    for cx, cy, rx, ry in ((174, 176, 12, 12), (220, 174, 10, 10.5)):
        mean_eye(p, cx, cy, rx, ry, hexc("#9a4ae0"), stem, brow_tilt=-0.15, lid=0.5, look=(-0.8, 0.35),
                 glow=hexc("#d08aff"))
        for dx in (-rx - 1, -rx * 0.5):  # long lashes flicking out at the outer corner
            p.stroke([(cx + dx, cy - ry * 0.1), (cx + dx - 5, cy - ry * 0.4)], DARK, 1.6)
    p.stroke(curve([(160, 156), (174, 150), (188, 154)], 4), hexc("#9a7aa8"), 2.4)
    p.stroke(curve([(208, 152), (220, 146), (232, 150)], 4), hexc("#9a7aa8"), 2.4)
    lips = p.shape("poly", curve([(178, 204), (190, 206), (200, 204), (212, 198), (206, 210), (192, 214), (182, 210)],
                                 3), hexc("#8a2a6a"), depth=0.3, light=1.4, line=1.1, rim=0, gloss=0.6)
    p.stroke(curve([(178, 205), (192, 208), (212, 199)], 3), hexc("#3a0a2a"), 1.3)
    p.stroke(curve([(184, 188), (190, 192), (196, 190)], 2), shade(stem, 0.7), 1.4)  # nose tip
    # ---- the bell cap: gills, the glowing dome with a scalloped rim, veil threads, a crown of glowing shrooms
    gills(p, 196, 138, 168, 20, hexc("#e8c8e8"), n=40)
    p.shadow_on(p._mask("ellipse", (28, 122, 364, 156)), strength=0.55, offset=4, blur=6)
    cap_pts = curve([(24, 146), (40, 118), (80, 80), (110, 54), (150, 34), (196, 28), (242, 34), (282, 54),
                     (312, 80), (352, 118), (368, 146)], 6)
    capm = p.shape("poly", cap_pts, capc, depth=0.12, light=1.3, spec=0.4, tex="leather", tex_amt=0.5, gloss=0.35)
    p.glow_clip((196, 90), 110, hexc("#c070ff"), 0.35, capm)
    for i in range(12):
        x = 38 + i * 29
        p.shape("chord", (x - 17, 132, x + 17, 160), shade(capc, 0.82), start=0, end=180, depth=0.3, line=1.2, rim=0)
    p.shape("poly", ell_pts(196, 140, 176, 12), shade(capc, 0.7), depth=0.35, rim=0, line=1.3)
    cap_spots(p, capm, ((84, 104, 15, 11), (140, 70, 18, 13), (236, 64, 17, 12), (300, 100, 13, 10),
                        (116, 118, 9, 6), (196, 104, 11, 8), (264, 118, 8, 6), (56, 128, 7, 5), (332, 128, 6, 5),
                        (190, 48, 9, 6)), glowc, fill=hexc("#f4e0ff"), glow_every=1, strength=0.6)
    # glowing threads hanging from the rim
    for i, x in enumerate(range(44, 356, 22)):
        ln = 18 + (i * 37) % 40
        y0 = 150 + abs(x - 196) * 0.02
        if 150 < x < 244:
            continue
        p.stroke([(x, y0), (x + 1, y0 + ln)], hexc("#e8b8ff", 170), 1.4)
        p.glow((x + 1, y0 + ln + 3), 7, glowc, 0.8)
        p.flat("ellipse", (x - 2.2, y0 + ln, x + 4.2, y0 + ln + 6), hexc("#fbeaff"))
    # crown of little glowing mushrooms
    for x, y, sc, c in ((122, 58, 1.0, "#5affc8"), (156, 40, 1.2, "#ffe07a"), (196, 32, 1.45, "#ff9af0"),
                        (236, 40, 1.2, "#ffe07a"), (270, 58, 1.0, "#5affc8")):
        cc = hexc(c)
        p.glow((x, y - 20 * sc), 28 * sc, cc, 0.75)
        p.shape("poly", taper([(x, y + 4), (x, y - 16 * sc)], 8 * sc, 6 * sc), hexc("#f8f0ff"), depth=0.3, line=1.1,
                rim=0)
        m = p.shape("poly", ell_pts(x, y - 18 * sc, 15 * sc, 16 * sc, 180, 360) + [(x + 15 * sc, y - 16 * sc)], cc,
                    depth=0.25, light=1.5, line=1.3, rim=0, gloss=0.8)
        p.shape("poly", ell_pts(x, y - 17 * sc, 15 * sc, 4 * sc), shade(cc, 0.75), depth=0.3, line=1.0, rim=0)
        p.flat("ellipse", (x - 7 * sc, y - 30 * sc, x - 2 * sc, y - 25 * sc), hexc("#ffffff", 220))
    # ---- drifting spores
    for x, y, r in ((24, 60, 3), (70, 30, 2.4), (360, 50, 3), (344, 160, 2.5), (100, 240, 2.2), (300, 290, 2.5),
                    (20, 250, 2.2), (370, 250, 2), (130, 10, 2), (262, 6, 2), (60, 300, 2), (330, 330, 2.2)):
        p.glow((x, y), r * 3.4, spore, 0.7)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#f0ffe0"))
    return p.finish(ground_shadow=(40, 350, 350, 384))


# ------------------------------------------------------------------ dungeon 3: Frozen Pass

FROST_RIM = hexc("#cfeeff")


def paw(p, x, y, w, color, claw_c=hexc("#3a4a6a"), toes=3, far=False):
    """A wolf-like paw planted on the ground at (x, y) (bottom centre), toes toward the left."""
    m = p.shape("poly", curve([(x + w * 0.5, y - w * 0.5), (x + w * 0.45, y), (x - w * 0.55, y), (x - w * 0.6, y - w * 0.3),
                               (x - w * 0.2, y - w * 0.55)], 4), color, depth=0.25, tex="fur", tex_amt=0.5)
    for i in range(toes - 1):
        tx = x - w * 0.5 + (i + 1) * w * 0.9 / toes
        p.stroke([(tx, y - w * 0.28), (tx, y - 1)], shade(color, 0.7), 1.0)
    for i in range(toes):
        tx = x - w * 0.58 + i * w * 0.34
        claw(p, tx, y - w * 0.12, w * 0.32, 150, w * 0.16, claw_c, 0.8)
    return m


def frost_wolf():
    """A lean frost wolf stalking in with its head low and a paw raised: a mane of glowing ice crystals, a ridge of
    them down its back, pinned ears, a snarling muzzle full of fangs, a pale glowing eye and frost smoking from
    its jaws (faces left)."""
    fur = hexc("#dce8f4")
    fur_d = hexc("#9ab4d0")
    far_c = hexc("#a8bcd4")
    ice = hexc("#bfeaff")
    glowc = hexc("#7ad8ff")
    eyec = hexc("#9af0ff")
    FL = 1.3  # ink weight for fur masses
    p = Pen(256, REG, rim=FROST_RIM, fit=(0.93, 136, 238))
    # ---- far legs (shaded blue, behind): a planted foreleg and a hind leg
    p.shape("poly", limb_poly([(118, 150), (122, 186), (122, 214), (118, 228)], [26, 15, 11, 12]), far_c, depth=0.2,
            tex="fur", tex_amt=0.6, line=FL)
    paw(p, 116, 236, 20, far_c)
    p.shape("poly", limb_poly([(194, 140), (188, 178), (214, 202), (214, 226)], [30, 17, 11, 11]), far_c, depth=0.2,
            tex="fur", tex_amt=0.6, line=FL)
    paw(p, 212, 236, 18, far_c)
    # ---- the bushy tail sweeping up behind, an ice crystal at its tip
    tail = [(212, 108), (232, 92), (242, 66), (236, 42)]
    tm = p.union([("poly", limb_poly(tail, [22, 30, 28, 14])),
                  ("poly", tufts([(220, 112), (242, 94), (252, 66), (244, 40)], 7, 12, side=-1, lean=0.3, seed=21)),
                  ("poly", tufts([(208, 100), (224, 84), (230, 60)], 6, 12, side=1, lean=0.3, seed=22))])
    p.paint_mask(tm, fur, depth=0.2, tex="fur", tex_amt=1.0, line=FL)
    p.vgrad(tm, fur_d[:3] + (140,), fur[:3] + (0,), 40, 110)
    shard(p, 236, 28, 14, 30, 6, ice, glow=glowc)
    # ---- the body: deep chest, tucked waist, strong hindquarters, a blue-grey saddle
    body = p.union([("ellipse", (58, 92, 144, 180)), ("ellipse", (150, 82, 224, 158)),
                    ("poly", curve([(100, 98), (190, 86), (196, 146), (160, 154), (130, 170), (100, 176)], 4)),
                    ("poly", tufts([(70, 172), (98, 184), (126, 174)], 6, 10, side=-1, lean=0.3, seed=23))])
    p.paint_mask(body, fur, depth=0.12, tex="fur", tex_amt=1.0, line=FL)
    p.vgrad(body, fur_d[:3] + (210,), fur[:3] + (0,), 84, 132)
    p.fill_mask(mul(_blur(p._mask("ellipse", (70, 146, 170, 200)), 5 * SS), body), hexc("#f6fbff", 200))
    for pts in ([(118, 108), (140, 116), (160, 110)], [(126, 132), (146, 140)]):
        p.stroke(curve(pts, 3), shade(fur_d, 0.9), 1.2)
    # ---- ice crystals growing along the spine
    for x, y, h, a in ((200, 88, 18, 34), (182, 84, 22, 22), (162, 84, 26, 10), (140, 86, 28, -2)):
        shard(p, x, y - h * 0.3, h * 0.42, h, a, ice, glow=glowc if h > 24 else None)
    # ---- near hind leg: thigh, a sharp hock, a long rear foot
    thigh = p.union([("poly", curve([(166, 108), (196, 92), (224, 112), (220, 150), (200, 170), (176, 166),
                                     (162, 140)], 4)),
                     ("poly", limb_poly([(196, 148), (182, 186), (206, 208), (204, 228)], [40, 18, 13, 13]))])
    p.paint_mask(thigh, fur, depth=0.14, tex="fur", tex_amt=0.9, line=FL)
    p.stroke(curve([(170, 114), (168, 146), (180, 168)], 4), shade(fur_d, 0.95), 1.3)
    p.shape("poly", tufts([(208, 196), (218, 204), (214, 216)], 5, 7, side=1, lean=0.2, seed=24), fur, depth=0.3,
            tex="fur", line=1.1, rim=0)
    paw(p, 200, 236, 22, fur)
    # ---- the crystal mane: glowing shards fanning from the neck, behind the ruff
    for x, y, h, a in ((118, 52, 42, 16), (138, 70, 38, 42), (150, 98, 34, 68), (100, 48, 34, -6),
                       (148, 126, 28, 96)):
        shard(p, x, y, h * 0.4, h, a, ice, glow=glowc)
    # ---- the ruff: a thick collar of fur around the neck and shoulder
    ruff = p.union([("ellipse", (54, 70, 136, 166)),
                    ("poly", tufts([(126, 76), (138, 110), (134, 148), (118, 166)], 9, 12, side=1, lean=0.4, seed=25)),
                    ("poly", tufts([(60, 150), (80, 172), (106, 172)], 8, 11, side=-1, lean=0.3, seed=26))])
    p.paint_mask(ruff, fur, depth=0.14, tex="fur", tex_amt=1.0, line=FL)
    p.vgrad(ruff, fur_d[:3] + (120,), fur[:3] + (0,), 70, 110)
    for pts in ([(100, 110), (104, 132), (112, 150)], [(118, 100), (124, 124), (126, 140)], [(86, 140), (92, 156)]):
        p.stroke(curve(pts, 3), shade(fur_d, 0.95), 1.3)
    for x, y, h, a in ((126, 150, 22, 150), (104, 164, 20, 190)):  # a couple of shards poking through the ruff
        shard(p, x, y, h * 0.42, h, a, ice)
    # ---- near front leg raised mid-stride: elbow back, wrist bent, paw curled
    p.shape("poly", limb_poly([(92, 140), (92, 172), (72, 190), (58, 200)], [34, 20, 14, 14]), fur, depth=0.2,
            tex="fur", tex_amt=0.8, line=FL)
    p.shape("poly", tufts([(98, 164), (102, 176), (96, 186)], 5, 6, side=1, lean=0.2, seed=27), fur, depth=0.3,
            tex="fur", line=1.1, rim=0)
    pw = p.shape("poly", curve([(64, 194), (50, 196), (40, 204), (44, 212), (58, 212), (66, 204)], 4), fur,
                 depth=0.25, tex="fur", tex_amt=0.5, line=FL)
    for x in (42, 48, 54):
        claw(p, x, 210, 7, 110, 3.4, hexc("#3a4a6a"), 0.8)
    # ---- the head, low and forward: pinned ears, long muzzle, snarling open jaws
    p.shape("poly", curve([(88, 64), (116, 50), (108, 76)], 3) + [(88, 64)], fur_d, depth=0.2, tex="fur", line=FL)
    mouth = p.shape("poly", curve([(64, 126), (40, 128), (14, 128), (12, 142), (38, 146), (64, 138)], 4),
                    hexc("#3a2040"), depth=0.25, line=1.1, rim=0)
    p.shape("ellipse", (22, 134, 56, 148), hexc("#c05a78"), **NOLINE, clip=mouth)
    lower = p.shape("poly", curve([(70, 134), (44, 144), (20, 146), (10, 150), (18, 158), (48, 158), (72, 148)], 4),
                    shade(fur, 0.9), depth=0.25, tex="fur", tex_amt=0.5, line=FL)
    for x, h in ((20, -11), (32, -7), (46, -7)):
        fang(p, x, 147, 5, h, hexc("#f4f8ff"), line=0.8)
    head = p.union([("ellipse", (36, 72, 112, 132)),
                    ("poly", curve([(54, 94), (28, 102), (8, 112), (2, 120), (10, 128), (40, 128), (66, 126)], 4)),
                    ("poly", tufts([(106, 90), (112, 108), (104, 126)], 6, 8, side=1, lean=0.3, seed=28))])
    p.paint_mask(head, fur, depth=0.12, tex="fur", tex_amt=0.9, line=FL)
    p.vgrad(head, fur_d[:3] + (160,), fur[:3] + (0,), 72, 104)
    fang(p, 20, 126, 6, 14, hexc("#f4f8ff"), line=0.9)
    fang(p, 44, 127, 5, 9, hexc("#f4f8ff"), line=0.8)
    for x in (30, 37, 54):
        fang(p, x, 127, 3.6, 5, hexc("#f4f8ff"), line=0.7)
    p.shape("ellipse", (-2, 106, 16, 120), hexc("#2a3450"), depth=0.3, line=1.0, gloss=1.0, rim=0)
    for pts in ([(20, 104), (30, 100), (40, 102)], [(24, 110), (34, 106), (44, 108)], [(28, 116), (38, 112)]):
        p.stroke(curve(pts, 3), shade(fur_d, 0.85), 1.4)  # snarl wrinkles
    p.stroke(curve([(62, 118), (72, 124), (86, 124)], 3), shade(fur_d, 0.9), 1.3)
    p.shape("poly", curve([(66, 74), (92, 46), (104, 76)], 3) + [(66, 74)], fur, depth=0.2, tex="fur", line=FL)
    p.shape("poly", [(76, 72), (92, 54), (98, 72)], hexc("#a8c8e8"), depth=0.3, line=0.9, rim=0, ao=0)
    glowing_eye(p, 62, 94, 7.5, 5.5, eyec, hexc("#ffffff"), socket=hexc("#1a2a4a"), slant=0.5)
    p.shape("poly", [(46, 82), (80, 88), (78, 94), (48, 88)], fur_d, depth=0.3, line=1.0, rim=0, tex="fur")
    # ---- frost breath curling out of the jaws, snow
    p.glow((14, 160), 30, hexc("#9ad8ff"), 0.4)
    mist_puffs(p, ((10, 152, 14), (26, 166, 12), (6, 178, 14), (20, 190, 10)), hexc("#e8f6ff"), 150)
    for x, y, r in ((16, 156, 7), (6, 172, 8), (24, 180, 5)):
        p.shape("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#f0faff", 160), shadow=0.88, light=1.2,
                depth=0.3, line=0.9, ink=hexc("#5a8ab0", 140), rim=0, ao=0)
    for x, y, r in ((40, 222, 2), (150, 40, 2.5), (200, 20, 2), (18, 60, 2), (250, 150, 2)):
        snow(p, x, y, r)
    snowflake(p, 170, 24, 4.5)
    return p.finish(ground_shadow=(40, 224, 244, 248))


def gem(p, outline, center, color, light=1.45, dark=0.72, line=1.4, ink=hexc("#1a3a6a"), alpha=255, glow=None):
    """A faceted crystal: the outline polygon split into triangular facets around `center`, each tinted by how
    it faces the top-left light, with bright edges along the ridges."""
    m = p.shape("poly", outline, color[:3] + (alpha,), depth=0.2, light=light, line=line, ink=ink, rim=0.4, spec=0.8)
    cx, cy = center
    n = len(outline)
    for i in range(n):
        a, b = outline[i], outline[(i + 1) % n]
        mx, my = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy
        d = (-mx - my) / (math.hypot(mx, my) or 1)  # +1 facing the top-left light
        tone = mix(color, hexc("#ffffff"), 0.75) if d > 0 else mix(color, hexc("#2a64c0"), 0.7)
        p.shape("poly", [center, a, b], tone[:3] + (int(150 * abs(d) * (1 if d > 0 else (1 - dark) * 2.4)) + 20,),
                **NOLINE, clip=m)
    for q in outline:
        p.stroke([center, q], hexc("#ffffff", 120), 1.0)
    if glow:
        p.glow_clip(center, max(abs(q[0] - cx) for q in outline) * 0.9, glow, 0.6, m)
    return m


def ice_wisp():
    """A floating ice spirit: a faceted crystal body with a glowing heart and an impish scowl, a crown of shards
    fanned out behind, orbiting splinters and a swirling tail of frost and snow (faces left)."""
    ice = hexc("#cdeeff")
    deep = hexc("#7ac8f0")
    glowc = hexc("#7ad8ff")
    p = Pen(256, REG, rim=FROST_RIM)
    p.glow((128, 108), 118, glowc, 0.38)
    # ---- the swirling tail: three wisps of frost curling away behind and below, snow glittering in them
    for pts, w0, al in (([(138, 150), (160, 190), (196, 214), (232, 206), (244, 184), (230, 172)], 44, 150),
                        ([(126, 160), (136, 196), (160, 226), (190, 238), (208, 230)], 30, 120),
                        ([(150, 146), (184, 166), (214, 164), (230, 146)], 26, 110)):
        tm = p.shape("poly", taper(pts, w0, 2, 10), hexc("#c4e8ff", al), shadow=0.85, light=1.2, depth=0.2, line=1.1,
                     ink=hexc("#5a9ad0", 150), rim=0, ao=0)
        p.glow_clip(pts[0], 50, glowc, 0.55, tm)
        p.stroke(curve(pts, 8)[:-6], hexc("#ffffff", 140), w0 * 0.18, soft=1.0)
    mist_puffs(p, ((170, 214, 20), (126, 190, 16), (214, 214, 14)), hexc("#cfeaff"), 110)
    for x, y, r in ((170, 200, 2.2), (206, 214, 2), (232, 190, 2.4), (150, 220, 1.8), (196, 172, 1.8), (222, 160, 2)):
        snow(p, x, y, r)
    # ---- the crown of shards fanned out behind
    for a, h, w, c in ((-150, 44, 18, deep), (-120, 54, 20, ice), (-90, 64, 22, ice), (-60, 54, 20, ice),
                       (-30, 44, 18, deep), (-176, 34, 14, shade(deep, 0.9)), (-4, 34, 14, shade(deep, 0.9)),
                       (150, 30, 14, shade(deep, 0.85)), (30, 30, 14, shade(deep, 0.85))):
        t = math.radians(a)
        cx, cy = 124 + math.cos(t) * (h * 0.5 + 34), 102 + math.sin(t) * (h * 0.5 + 34)
        shard(p, cx, cy, w, h, a + 90, c, glow=glowc if h > 70 else None)
    # ---- the crystal body with a glowing heart
    outline = [(124, 34), (158, 58), (168, 108), (152, 150), (124, 170), (94, 150), (80, 108), (92, 58)]
    body = gem(p, outline, (118, 100), hexc("#9ad4fa"), light=1.35, dark=0.62)
    p.glow_clip((122, 112), 46, glowc, 0.5, body)
    p.glow_clip((122, 116), 22, hexc("#f0fdff"), 0.6, body)
    # ---- the face: glowing slanted eyes, a crooked grin with a chipped tooth
    for x, y, rx, ry, sl in ((106, 98, 8.5, 9, 0.45), (138, 96, 7.5, 8, 0.45)):
        e = p._mask("ellipse", (x - rx, y - ry, x + rx, y + ry))
        e = sub(e, p._mask("poly", [(x - rx * 2, y - ry * 2), (x + rx * 2, y - ry * 2),
                                     (x + rx * 2, y - ry * (0.2 - sl)), (x - rx * 2, y - ry * (1.0 + sl * 0.3))]))
        p.paint_mask(e, hexc("#123060"), **NOLINE)
        p.glow((x - 1, y + 1), rx * 2.2, glowc, 0.85)
        p.fill_mask(mul(e, p._mask("ellipse", (x - rx * 0.7, y - ry * 0.4, x + rx * 0.3, y + ry * 0.7))),
                    hexc("#d8fbff"))
        p.flat("ellipse", (x - rx * 0.55, y - ry * 0.05, x - rx * 0.15, y + ry * 0.35), WHITE)
    m = p.shape("poly", curve([(100, 124), (114, 130), (130, 130), (144, 120), (140, 134), (122, 142), (106, 136)], 4),
                hexc("#123060"), depth=0.3, line=1.1, rim=0, ink=hexc("#0a1a3a"))
    p.glow_clip((122, 136), 10, glowc, 0.7, m)
    fang(p, 112, 128, 5, 6, hexc("#f4fbff"), line=0.8)
    fang(p, 132, 128, 5, 7, hexc("#f4fbff"), line=0.8)
    # ---- orbiting splinters, snowflakes and frost sparkles
    for x, y, h, a in ((34, 124, 26, -60), (220, 130, 24, 50), (52, 42, 20, -25), (206, 36, 22, 30), (70, 176, 16, -130)):
        shard(p, x, y, h * 0.45, h, a, ice, glow=glowc)
    for x, y, r in ((24, 84, 5.5), (234, 82, 5), (92, 214, 4.5), (128, 10, 4.5)):
        snowflake(p, x, y, r)
    for x, y, r in ((18, 160, 2), (244, 60, 2), (90, 18, 1.8), (176, 12, 2), (40, 214, 2), (240, 230, 2.2)):
        snow(p, x, y, r)
    p.sparkle((150, 52), 7)
    p.sparkle((96, 150), 5)
    return p.finish(ground_shadow=(84, 230, 172, 246))


def fur_blob(p, box, amp, step, seed, side=1):
    """Tufts all around an ellipse, for shaggy silhouettes."""
    x0, y0, x1, y1 = box
    pts = ell_pts((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, 0, 360, step=4)
    return tufts(pts, amp, step, side=side, lean=0.35, seed=seed)


def yeti_cub():
    """A chubby, shaggy yeti cub in a sulk: a blue face with a grumpy pout and two tiny fangs, big blue fists and
    feet, and a hefty snowball hoisted over its head, ready to throw (faces left)."""
    fur = hexc("#eef3f8")
    fur_s = hexc("#c4d4e8")
    blue = hexc("#7aa8d8")
    blue_d = hexc("#3a5a8a")
    FL = 1.3
    p = Pen(256, REG, rim=FROST_RIM, fit=(0.94, 128, 240))
    # ---- back arm and fist, low at its side
    p.shape("poly", limb_poly([(188, 118), (220, 150), (226, 172)], [42, 36, 32]), shade(fur, 0.9), depth=0.18,
            tex="fur", tex_amt=1.0, line=FL)
    fist(p, 228, 186, 21, blue, facing=-1, tex="leather")
    # ---- big blue feet
    for x0 in (74, 142):
        p.shape("poly", curve([(x0 + 48, 226), (x0 + 44, 240), (x0 - 4, 240), (x0 - 6, 226), (x0 + 20, 214)], 4),
                blue, depth=0.25, tex="leather", tex_amt=0.5)
        for dx in (4, 14, 24):
            p.shape("ellipse", (x0 + dx - 5, 232, x0 + dx + 5, 241), hexc("#e8f4ff"), line=0.9, rim=0, ao=0,
                    depth=0.3)
    # ---- the round shaggy body and head
    body = p.union([("ellipse", (54, 92, 206, 230)), ("ellipse", (60, 22, 196, 144)),
                    ("poly", fur_blob(p, (54, 92, 206, 230), 9, 12, 31)),
                    ("poly", fur_blob(p, (60, 22, 196, 144), 8, 12, 32)),
                    ("poly", [(98, 34), (106, 2), (120, 26), (134, -2), (146, 24), (164, 6), (168, 36)])])
    p.paint_mask(body, fur, depth=0.1, tex="fur", tex_amt=1.1, line=FL)
    p.vgrad(body, hexc("#ffffff", 0), fur_s[:3] + (150,), 150, 236)
    belly = mul(p._mask("ellipse", (88, 148, 178, 226)), body)
    p.paint_mask(belly, hexc("#dde8f4"), line=0, depth=0.2, rim=0, ao=0, tex="fur", tex_amt=0.8)
    for pts in ([(70, 172), (66, 196)], [(188, 172), (194, 196)], [(110, 170), (106, 190)], [(150, 176), (156, 194)]):
        p.stroke(pts, hexc("#b8c8dc"), 1.4)
    # ---- the blue face with a grumpy pout
    face = p.shape("poly", curve(ell_pts(110, 98, 50, 40, step=30), 3), blue, depth=0.14, tex="leather", tex_amt=0.4)
    p.flat("ellipse", (66, 104, 82, 114), hexc("#ff8aa8", 90))
    p.flat("ellipse", (138, 104, 152, 114), hexc("#ff8aa8", 80))
    mean_eye(p, 90, 94, 9, 10, hexc("#2a3a6a"), blue, brow_tilt=0.4, lid=0.34, look=(-0.8, 0.2))
    mean_eye(p, 132, 92, 8, 9, hexc("#2a3a6a"), blue, brow_tilt=0.4, lid=0.34, look=(-0.8, 0.2))
    p.shape("poly", [(72, 76), (106, 84), (104, 90), (70, 82)], blue_d, depth=0.3, line=1.0, rim=0)
    p.shape("poly", [(120, 84), (150, 74), (152, 81), (122, 90)], blue_d, depth=0.3, line=1.0, rim=0)
    p.shape("ellipse", (102, 100, 118, 111), blue_d, depth=0.3, line=1.0, gloss=0.9, rim=0)
    pout = p.shape("poly", curve([(94, 130), (102, 120), (122, 120), (130, 130), (120, 127), (104, 127)], 4), blue_d,
                   depth=0.3, line=1.1, rim=0)
    fang(p, 102, 127, 5, -6, hexc("#f8fbff"), line=0.8)
    fang(p, 122, 127, 5, -6, hexc("#f8fbff"), line=0.8)
    p.shape("poly", curve([(104, 131), (112, 134), (120, 131), (112, 136)], 2), shade(blue, 1.15), **NOLINE)
    # fringe of fur over the forehead
    p.shape("poly", curve([(60, 72), (76, 52), (108, 46), (140, 48), (166, 62), (152, 60), (144, 70), (128, 58),
                           (116, 68), (100, 56), (86, 68), (72, 62)], 4), fur, depth=0.25, tex="fur", line=FL)
    # ---- the front arm hoisting a big snowball overhead
    arm = p.union([("poly", limb_poly([(76, 146), (46, 116), (46, 84)], [40, 34, 30])),
                   ("ellipse", (58, 128, 98, 166)),
                   ("poly", tufts([(62, 150), (36, 122), (32, 96)], 6, 10, side=-1, lean=0.3, seed=33))])
    p.paint_mask(arm, fur, depth=0.18, tex="fur", tex_amt=1.0, line=FL)
    ball = p.union([("ellipse", (8, 4, 76, 70)), ("ellipse", (44, 2, 70, 26))])
    p.paint_mask(ball, hexc("#f4faff"), depth=0.18, light=1.2, tex="stone", tex_amt=0.35, line=1.4,
                 ink=hexc("#4a6a9a"))
    for x, y, r in ((30, 20, 4), (56, 44, 3), (40, 36, 2.6), (62, 18, 2.6)):
        p.flat("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), hexc("#c8dcf0"))
    fist(p, 46, 72, 16, blue, facing=-1, tex="leather")
    # ---- falling snow
    for x, y, r in ((200, 40, 4.5), (232, 100, 4), (16, 120, 3.5)):
        snowflake(p, x, y, r)
    for x, y, r in ((30, 150, 2), (220, 70, 2.2), (20, 230, 2), (100, 10, 2)):
        snow(p, x, y, r)
    return p.finish(ground_shadow=(40, 224, 244, 250))


def ice_troll():
    """Elite: a hulking, hunched ice troll hauling a crystal-headed club up behind its shoulder: blue hide, a mane
    of white hair, a hooked nose, tusks and an icicle beard, an ice breastplate lashed on with rope, crystal
    pauldrons and knuckles that drag in the snow (faces left)."""
    skin = hexc("#6a9ad0")
    skin_l = hexc("#9ec2e8")
    skin_d = shade(skin, 0.78)
    ice = hexc("#cdf0ff")
    deep = hexc("#8ad0f4")
    fur = hexc("#8a7a66")
    rope = hexc("#b8905a")
    glowc = hexc("#7ad8ff")
    hair = hexc("#eef4fa")
    p = Pen(256, REG, rim=FROST_RIM, fit=(0.9, 124, 240))
    # ---- the club raised behind: a wooden haft and a head of ice crystals
    p.shape("poly", limb_poly([(222, 116), (214, 70), (202, 34)], [12, 11, 10]), hexc("#6a4428"), depth=0.3,
            tex="wood", tex_amt=1.0)
    for y in (94, 102):
        p.stroke([(212, y), (226, y - 3)], rope, 2.2)
    p.glow((198, 26), 46, glowc, 0.55)
    head = p.shape("ellipse", (176, 6, 222, 48), deep, depth=0.2, spec=0.8, line=1.4, ink=hexc("#2a4a7a"),
                   tex="stone", tex_amt=0.3)
    for x, y, w, h, a in ((178, 14, 14, 34, -60), (196, 2, 16, 40, -10), (216, 10, 14, 34, 40), (224, 34, 12, 26, 90),
                          (176, 40, 12, 26, -110), (200, 22, 12, 22, 0)):
        shard(p, x, y, w, h, a, ice)
    # ---- back arm hoisting it
    p.shape("poly", limb_poly([(186, 80), (226, 112), (228, 88)], [38, 30, 26]), skin_d, depth=0.16, tex="leather",
            tex_amt=0.6)
    fist(p, 224, 84, 15, skin_d, facing=-1, tex="leather")
    # ---- bowed legs and big clawed feet
    for (hip, knee, ank), fx in ((((104, 176), (92, 204), (98, 224)), 96), (((160, 176), (174, 204), (166, 224)), 166)):
        p.shape("poly", limb_poly([hip, knee, ank], [38, 30, 26]), skin_d if fx > 120 else skin, depth=0.18,
                tex="leather", tex_amt=0.6)
        p.shape("poly", curve([(fx + 18, 222), (fx + 16, 238), (fx - 28, 240), (fx - 30, 230), (fx - 10, 218)], 4),
                shade(skin, 0.9), depth=0.25, tex="leather", tex_amt=0.6)
        for dx in (-26, -16, -6):
            claw(p, fx + dx, 236, 7, 170, 5, hexc("#e8f4ff"), 0.9)
    # ---- the hunched torso and pale belly
    torso = p.union([("ellipse", (66, 56, 212, 200)), ("ellipse", (120, 40, 206, 120))])
    p.paint_mask(torso, skin, depth=0.1, tex="leather", tex_amt=0.7)
    p.shape("ellipse", (90, 116, 176, 196), skin_l, depth=0.18, line=0, rim=0, ao=0, tex="leather", tex_amt=0.5,
            clip=torso)
    for x, y in ((150, 60), (170, 70), (130, 50)):  # frost-rimed patches of hair on the back
        p.shape("poly", tufts([(x - 10, y + 4), (x, y - 4), (x + 10, y + 2)], 6, 5, side=1, seed=int(x)), hair,
                depth=0.3, line=1.0, rim=0, tex="fur")
    # fur loincloth with a rope belt
    p.shape("poly", curve([(76, 170), (190, 168), (196, 206), (180, 198), (170, 212), (154, 200), (140, 214),
                           (124, 200), (108, 212), (94, 200), (74, 206)], 3), fur, depth=0.14, tex="fur",
            tex_amt=1.0)
    p.shape("poly", taper([(72, 172), (132, 176), (194, 168)], 7, 7), rope, depth=0.3, tex="leather", rim=0)
    p.shape("poly", taper([(122, 176), (116, 196)], 5, 4), rope, depth=0.3, rim=0, line=1.1)
    # ice breastplate lashed on with rope
    for a, b in (((96, 110), (190, 70)), ((160, 140), (204, 118))):
        p.shape("poly", taper([a, b], 5, 5), rope, depth=0.3, line=1.0, rim=0)
    plate = [(100, 94), (160, 88), (170, 140), (134, 158), (104, 146)]
    p.glow((134, 122), 42, glowc, 0.4)
    gem(p, plate, (128, 112), hexc("#a6dcff"), line=1.4, ink=hexc("#2a4a7a"))
    p.glow_clip((130, 118), 20, hexc("#ffffff"), 0.5, p._mask("poly", plate))
    # ---- crystal pauldrons
    for cx, cy, s in ((180, 62, 1.0), (86, 72, 1.1)):
        p.shape("poly", ell_pts(cx, cy, 24 * s, 16 * s), deep, depth=0.25, spec=0.8, line=1.3, ink=hexc("#2a4a7a"))
        for dx, h, a in ((-15, 30, -34), (0, 40, -4), (15, 30, 26)):
            shard(p, cx + dx * s, cy - 14 * s, 12 * s, h * s, a, ice, glow=glowc if h > 35 else None)
    # ---- the front arm hanging long, knuckles dragging in the snow
    p.shape("poly", limb_poly([(86, 84), (60, 124), (52, 168), (50, 190)], [36, 30, 28, 26]), skin, depth=0.16,
            tex="leather", tex_amt=0.6)
    p.stroke(curve([(62, 118), (58, 132)], 2), skin_d, 1.4)
    p.shape("poly", limb_poly([(58, 136), (54, 160)], [32, 31]), hexc("#5a4a3a"), depth=0.3, line=1.1, tex="leather",
            rim=0)
    for y in (142, 154):
        p.stroke([(42, y), (70, y + 2)], rope, 1.8)
    hand = p.shape("poly", curve([(64, 184), (66, 206), (54, 222), (30, 224), (28, 206), (36, 186)], 4), skin,
                   depth=0.22, tex="leather", tex_amt=0.5)
    for x, y in ((34, 222), (44, 224), (54, 222)):
        claw(p, x, y, 7, 120, 5, hexc("#e8f4ff"), 0.9)
    for y in (196, 206):
        p.stroke([(36, y), (50, y - 2)], skin_d, 1.4)
    # ---- head: shaggy white mane, heavy brow, hooked nose, tusks and an icicle beard
    mane = p.union([("ellipse", (56, 18, 128, 62)), ("ellipse", (98, 24, 158, 72)), ("ellipse", (128, 44, 176, 88)),
                    ("poly", tufts([(56, 40), (70, 24), (96, 16), (126, 22), (152, 36), (172, 60), (180, 84)], 11, 12,
                                   side=1, lean=0.55, seed=41))])
    p.paint_mask(mane, hair, depth=0.16, tex="fur", tex_amt=1.0, line=1.3)
    for pts in ([(80, 30), (110, 32), (140, 44)], [(96, 26), (128, 36), (156, 56)]):
        p.stroke(curve(pts, 4), hexc("#b8cce0"), 1.3)
    for x, h in ((50, 34), (60, 44), (72, 38), (84, 46), (96, 34), (108, 24)):
        shard(p, x, 102 + h / 2 - 4, 10, h, 180, ice, line=1.0)
    head = p.shape("ellipse", (40, 34, 122, 110), skin, depth=0.12, tex="leather", tex_amt=0.6)
    p.shape("poly", [(118, 56), (136, 46), (128, 70)], shade(skin, 0.9), depth=0.25)  # pointed ear
    fringe = p.union([("ellipse", (50, 30, 104, 50)),
                      ("poly", tufts([(104, 42), (80, 50), (54, 46)], 7, 8, side=1, lean=0.3, seed=43))])
    p.paint_mask(fringe, hair, depth=0.2, tex="fur", tex_amt=0.9, line=1.2, rim=0)
    glowing_eye(p, 64, 64, 6, 4.5, hexc("#9af0ff"), hexc("#ffffff"), socket=hexc("#1a2a4a"), slant=0.45)
    glowing_eye(p, 94, 62, 5.5, 4.2, hexc("#9af0ff"), hexc("#ffffff"), socket=hexc("#1a2a4a"), slant=0.45)
    p.shape("poly", curve([(44, 54), (80, 48), (112, 50), (112, 58), (80, 58), (46, 62)], 3), skin_d, depth=0.3,
            line=1.2, rim=0, tex="leather")
    p.shape("poly", curve([(80, 62), (64, 72), (46, 86), (42, 96), (54, 98), (70, 92), (84, 80)], 4),
            shade(skin, 1.05), depth=0.25, gloss=0.4, tex="leather", tex_amt=0.4)
    p.shape("poly", curve([(52, 98), (78, 96), (104, 94), (100, 104), (60, 108)], 3), hexc("#2a2040"), depth=0.3,
            line=1.1, rim=0)
    fang(p, 62, 106, 8, -18, hexc("#f4f0e0"), curl=-0.1)
    fang(p, 96, 102, 8, -15, hexc("#f4f0e0"), curl=0.1)
    # ---- frost mist around the feet, snow
    mist_puffs(p, ((40, 232, 26), (110, 238, 22), (200, 236, 26)), hexc("#e8f6ff"), 110)
    for x, y, r in ((150, 16, 4.5), (240, 150, 4), (20, 140, 3.5)):
        snowflake(p, x, y, r)
    for x, y, r in ((24, 40, 2), (250, 60, 2), (130, 8, 2)):
        snow(p, x, y, r)
    return p.finish(ground_shadow=(8, 222, 246, 250))


def plates(p, clip, pts, width, color, step=12):
    """Belly or throat plates: bands across a curve, clipped to a body mask."""
    c = curve(pts, 8)
    marks = along(c, step)
    for i, (x, y) in enumerate(marks[1:], 1):
        a, b = marks[i - 1], (x, y)
        tx, ty = norm(b[0] - a[0], b[1] - a[1])
        nx, ny = -ty, tx
        p.stroke([(x - nx * width, y - ny * width), (x + tx * 2, y + ty * 2), (x + nx * width, y + ny * width)],
                 shade(color, 0.74), 1.5)


def dragon_wing(p, shoulder, elbow, wrist, fingers, membrane, bone_c, width=10, edge=None, scallop=0.24,
                attach=None, thumb=None, frost=()):
    """A dragon wing (after companion.dragon_wing): a bent arm, bowed finger bones fanning back from the wrist and
    a scalloped membrane between them, with shading that dips along each bone and a sheen in every panel."""
    attach = attach or (shoulder[0] - (shoulder[0] - fingers[-1][0]) * 0.25, shoulder[1] + 6)
    edge_pts = [fingers[0]]
    prev = fingers[0]
    for f in fingers[1:]:
        mx, my = (prev[0] + f[0]) / 2, (prev[1] + f[1]) / 2
        edge_pts += [(mx + (wrist[0] - mx) * scallop, my + (wrist[1] - my) * scallop), f]
        prev = f
    last = fingers[-1]
    lx, ly = (last[0] + attach[0]) / 2, (last[1] + attach[1]) / 2
    tail_edge = [last, (lx + (wrist[0] - lx) * scallop * 0.8, ly + (wrist[1] - ly) * scallop * 0.8), attach]
    mem = p._mask("poly", [elbow, wrist] + curve(edge_pts, 6) + curve(tail_edge, 6)[1:] + [shoulder])
    p.paint_mask(mem, membrane, depth=0.08, light=1.25, tex="leather", tex_amt=0.4)
    for f in fingers + [attach]:
        p.fill_mask(mul(_blur(p._mask("line", [wrist, f], width=width * 1.1), 2.2 * p.k * SS),
                        mem), shade(membrane, 0.6)[:3] + (130,))
    for f0, f1 in zip(fingers, fingers[1:]):
        mx, my = (wrist[0] + (f0[0] + f1[0]) / 2) / 2, (wrist[1] + (f0[1] + f1[1]) / 2) / 2
        g = p._mask("line", [(mx + (wrist[0] - mx) * 0.3, my + (wrist[1] - my) * 0.3), (mx, my)], width=width * 0.9)
        p.fill_mask(mul(_blur(g, 2.6 * p.k * SS), mem), light_tone(membrane, 1.35)[:3] + (90,))
    for x, y, r in frost:
        snowflake(p, x, y, r, hexc("#e8faff"))
    if edge:
        p.stroke(curve(edge_pts, 6) + curve(tail_edge, 6)[1:], edge, 2.0)

    def bow(a, b, k=0.08):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = b[0] - a[0], b[1] - a[1]
        return curve([a, (mx + dy * k, my - dx * k), b], 5)
    for f in fingers:
        p.shape("poly", taper(bow(wrist, f), width * 0.55, width * 0.2, 1), bone_c, depth=0.3, line=1.1, rim=0)
    p.shape("poly", taper([shoulder, elbow], width * 1.3, width * 0.9, 1), bone_c, depth=0.3, light=1.3, rim=0.3)
    p.shape("poly", taper([elbow, wrist], width * 0.95, width * 0.7, 1), bone_c, depth=0.3, light=1.3, rim=0.3)
    for (x, y), r in ((elbow, width * 0.56), (wrist, width * 0.54)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), bone_c, depth=0.3, line=1.1, rim=0)
    ux, uy = norm(wrist[0] - elbow[0], wrist[1] - elbow[1])
    if thumb:
        shard(p, wrist[0] + ux * width * 0.8, wrist[1] + uy * width * 0.8, width * 0.8, width * 2.0,
              math.degrees(math.atan2(uy, ux)) + 90, thumb, line=1.0)
    return mem


def dlimb(p, color, upper, top, knee, foot, w0, w1, pawbox, claw_c, claw_x, claw_y, claw_s=4.4):
    """A dragon leg as one shape (a thigh or shoulder ellipse merged with a tapered shin), a round paw and claws
    pointing left."""
    items = [("poly", taper([top, knee, foot], w0, w1, 6))]
    if upper:
        items.append(("ellipse", upper))
    m = p.paint_mask(p.union(items), color, depth=0.14, tex="leather", tex_amt=0.5)
    p.shape("ellipse", pawbox, color, depth=0.25, tex="leather", tex_amt=0.4)
    for x in claw_x:
        claw(p, x, claw_y, claw_s * 1.5, 165, claw_s, claw_c, 0.9)
    return m


def frostbreath():
    """Boss: Frostbreath, a proud pale-blue frost dragon with its chest out and head held high, breathing a cone of
    glittering frost down at the player: crystal horns swept back, wings spread wide, crystal spines along its
    neck and tail, and a cold, narrow-eyed glare (faces left)."""
    scale = hexc("#bcdcf4")
    scale_d = hexc("#7aa4d0")
    far = shade(scale, 0.8)
    belly = hexc("#eef8ff")
    crystal = hexc("#d8f6ff")
    mem = hexc("#4f8ed8")
    glowc = hexc("#7ad8ff")
    claw_c = hexc("#f4fbff")
    p = Pen(256, BOSS, rim=FROST_RIM, fit=(0.84, 176, 250))
    p.glow((140, 120), 150, glowc, 0.2)
    # ---- far wing, spread up behind the shoulders
    dragon_wing(p, (108, 126), (84, 86), (100, 26), [(124, 0), (150, 10), (160, 52), (142, 98)],
                shade(mem, 0.78), far, width=10, thumb=crystal)
    # ---- the tail sweeping back and curling up, crystal spines and a crystal tip
    tail = [(176, 196), (212, 222), (238, 224), (250, 204), (242, 186)]
    for x, y in along(curve(tail, 8), 16)[1:4]:
        shard(p, x + 2, y - 16, 10, 20, 36, crystal)
    p.shape("poly", taper(tail, 46, 11, 10), scale, depth=0.18, tex="leather", tex_amt=0.5)
    plates(p, None, [(184, 206), (212, 228), (236, 228)], 6, scale, step=10)
    shard(p, 238, 176, 12, 26, -20, crystal, glow=glowc)
    # ---- far legs
    claw_f = shade(claw_c, 0.88)
    dlimb(p, far, None, (148, 200), (150, 226), (152, 236), 30, 20, (134, 228, 170, 248), claw_f, (138, 145), 244, 3.8)
    p.shape("poly", taper([(76, 170), (54, 196), (48, 224)], 30, 20, 6), far, depth=0.18, tex="leather",
            tex_amt=0.5)
    p.shape("ellipse", (30, 216, 64, 236), far, depth=0.25, tex="leather", tex_amt=0.4)
    for x in (32, 40, 48):
        claw(p, x, 232, 5.5, 165, 3.6, claw_f, 0.9)
    # ---- crystal spines down the neck, the neck, the body (a deep chest held high)
    neck = [(96, 166), (78, 124), (66, 92), (60, 72)]
    for x, y in along(curve(neck, 8), 12)[2:9]:
        shard(p, x + 30, y + 2, 10, 24, 62, crystal, glow=glowc)
    p.shape("poly", taper(neck, 64, 42), scale, depth=0.16, tex="leather", tex_amt=0.5)
    for x, y, h, a in ((116, 118, 26, 14), (136, 120, 24, 26), (156, 128, 22, 38), (174, 142, 20, 50)):
        shard(p, x, y, h * 0.42, h, a, crystal, glow=glowc if h > 24 else None)
    bm = p.union([("ellipse", (106, 150, 202, 226)), ("ellipse", (50, 112, 158, 210))])
    p.paint_mask(bm, scale, depth=0.12, tex="leather", tex_amt=0.5)
    scale_rows(p, bm, (50, 112, 200, 146), shade(scale, 1.06), size=11, line=0.55)
    p.shape("ellipse", (42, 170, 160, 252), belly, depth=0.2, line=1.2, rim=0, clip=bm, tex="leather", tex_amt=0.35)
    for x in range(60, 146, 12):
        p.stroke([(x + 2, 184 + abs(x - 102) * 0.2), (x, 208 - abs(x - 102) * 0.05)], shade(belly, 0.76), 1.6)
    p.shape("poly", taper([(78, 172), (64, 134), (54, 104), (50, 86)], 28, 16), belly, depth=0.2, line=1.1, rim=0,
            tex="leather", tex_amt=0.3)
    for x, y in along(curve([(74, 164), (60, 130), (52, 102)], 5), 9)[1:]:
        p.stroke([(x + 8, y - 3), (x - 8, y + 2)], shade(belly, 0.76), 1.5)
    # ---- near wing, spread wide and high
    dragon_wing(p, (138, 144), (118, 98), (152, 36), [(204, 4), (242, 32), (254, 84), (240, 128), (196, 148)],
                mem, scale, width=12, edge=hexc("#effbff"), thumb=crystal,
                frost=((200, 46, 4), (226, 80, 3.5), (182, 96, 3.5), (224, 118, 3)))
    # ---- near hind leg and near front leg
    dlimb(p, scale, (134, 152, 208, 224), (174, 210), (180, 232), (178, 240), 32, 22, (152, 230, 204, 250), claw_c,
          (158, 166, 174), 246, 4.2)
    p.stroke(curve([(150, 170), (148, 190), (160, 208)], 4), scale_d, 1.4)
    shard(p, 202, 196, 9, 20, 70, crystal)
    dlimb(p, scale, (62, 146, 110, 200), (86, 186), (82, 220), (84, 234), 32, 22, (60, 228, 106, 250), claw_c,
          (64, 72, 80), 246, 4.2)
    shard(p, 104, 188, 9, 20, 80, crystal)
    # ---- head: frill, crystal horns swept back, cranium and a long muzzle, open jaws
    p.shape("poly", curve([(78, 62), (106, 50), (94, 66), (110, 76), (94, 84), (104, 94), (78, 90)], 3),
            shade(mem, 0.95), depth=0.3, light=1.3, line=1.2, rim=0)
    for pts, w, c in (([(74, 44), (92, 24), (112, 14), (130, 14)], 13, shade(crystal, 0.86)),
                      ([(54, 40), (66, 18), (84, 6), (106, 4)], 15, crystal)):
        p.glow(pts[-1], 12, glowc, 0.5)
        p.shape("poly", taper(pts, w, 1.5), c, depth=0.25, light=1.45, spec=0.9, line=1.2, ink=hexc("#2a4a7a"), rim=0)
    mouth = p.shape("poly", curve([(64, 72), (36, 78), (8, 84), (10, 104), (40, 98), (66, 88)], 4), hexc("#2a3060"),
                    **NOLINE)
    p.glow_clip((30, 90), 24, glowc, 0.9, mouth)
    jaw = p.shape("poly", curve([(64, 84), (40, 96), (16, 108), (6, 106), (10, 116), (40, 110), (68, 96)], 4),
                  shade(scale, 0.9), depth=0.25, tex="leather", tex_amt=0.5)
    for x, h in ((14, -7), (24, -7), (34, -6), (44, -5)):
        fang(p, x, 108 - (x - 14) * 0.3, 4, h, hexc("#f8fcff"), line=0.8)
    head = p.union([("ellipse", (40, 30, 94, 86)), ("rect", (4, 50, 62, 82), {"radius": 16}),
                    ("ellipse", (22, 44, 50, 62))])
    p.paint_mask(head, scale, depth=0.12, tex="leather", tex_amt=0.45)
    p.shape("chord", (2, 68, 74, 92), belly, start=0, end=180, depth=0.2, line=1.1, rim=0, clip=head)
    for x, h in ((10, 8), (19, 7), (28, 7), (38, 6)):
        fang(p, x, 80, 4.4, h, hexc("#f8fcff"), line=0.8)
    for x, y, h, a in ((82, 76, 16, 10), (78, 86, 13, 30)):  # cheek spikes
        shard(p, x, y, h * 0.42, h, a + 90, crystal)
    p.stroke(curve([(20, 52), (12, 54), (6, 60)], 3), shade(scale, 0.72), 1.6)
    for x, y in ((13, 58), (7, 57)):
        p.flat("ellipse", (x - 1.8, y - 1.4, x + 1.8, y + 1.4), hexc("#2a3a6a"))
    mean_eye(p, 44, 60, 8.5, 7.5, hexc("#3ab0f0"), scale, brow_tilt=0.55, lid=0.32, look=(-0.9, 0.15),
             pupil="slit", glow=glowc, line=1.0)
    p.shape("poly", curve([(26, 48), (46, 46), (70, 56)], 3) + [(68, 62), (46, 53), (28, 55)], scale_d, depth=0.3,
            line=1.0, rim=0, tex="leather")
    for x, y, h, a in ((36, 46, 9, -70), (50, 46, 11, -60), (64, 50, 10, -45)):  # a crystal brow
        shard(p, x, y, h * 0.45, h, a + 90, crystal)
    # ---- the frost breath: a glowing cone of freezing mist streaming down-left, full of splinters and glints
    mouth_pt = (10, 92)
    cone = p._mask("poly", curve([(12, 86), (-6, 96), (-27, 108), (-31, 170), (-25, 226), (-6, 214), (8, 150),
                                  (16, 100)], 5))
    p.glow((0, 150), 60, glowc, 0.7)
    p.fill_mask(_scale(_blur(cone, 4 * p.k * SS), 0.62), hexc("#d8f4ff"))
    p.p.glow_clip(p.pt(*mouth_pt), 120 * p.k * p.s, hexc("#ffffff"), 0.7, _blur(cone, 3 * p.k * SS))
    for ex, ey in ((-27, 118), (-27, 150), (-25, 184), (-19, 212), (-5, 200), (-12, 136)):
        p.stroke(curve([mouth_pt, ((mouth_pt[0] + ex) / 2 + 3, (mouth_pt[1] + ey) / 2 - 4), (ex, ey)], 5),
                 hexc("#ffffff", 150), 2.4, soft=1.2)
    mist_puffs(p, ((-2, 120, 14), (-15, 160, 20), (-6, 196, 16), (-22, 132, 14)), hexc("#f4fcff"), 150)
    for x, y, h, a in ((-1, 112, 12, -120), (-10, 146, 13, -140), (-19, 180, 12, -160), (-4, 176, 10, -150),
                       (-21, 120, 10, -110), (-12, 206, 10, -170)):
        shard(p, x, y, h * 0.46, h, a, crystal, glow=glowc)
    for x, y, r in ((-7, 130, 5), (-17, 196, 4), (0, 160, 3.5), (-24, 150, 4)):
        p.sparkle((x, y), r)
    for x, y, r in ((-5, 104, 1.8), (-12, 174, 1.6), (4, 190, 1.8), (-25, 200, 1.6)):
        snow(p, x, y, r)
    # ---- frost mist round the feet, falling snow
    mist_puffs(p, ((60, 244, 20), (170, 246, 22), (230, 240, 16)), hexc("#e8f6ff"), 100)
    for x, y, r in ((160, 6, 4), (36, 206, 3.5), (250, 150, 3), (116, 60, 3)):
        snowflake(p, x, y, r)
    for x, y, r in ((20, 20, 1.8), (140, 8, 1.6), (250, 20, 1.8), (6, 200, 1.6), (120, 236, 1.6)):
        snow(p, x, y, r)
    img = p.finish(ground_shadow=(26, 230, 250, 256))
    # let the breath mist fade out before the canvas edge instead of being cut off
    a = img.getchannel("A")
    ramp = Image.linear_gradient("L").rotate(90).resize((48, img.height))
    a.paste(ImageChops.multiply(a.crop((0, 0, 48, img.height)), ramp), (0, 0))
    img.putalpha(a)
    return img


# ------------------------------------------------------------------ registry

SPRITES = {
    "enemies/cellar_rat": cellar_rat,
    "enemies/skeleton_guard": skeleton_guard,
    "enemies/cellar_warden": cellar_warden,
    "enemies/mimic": mimic,
    "enemies/bone_king": bone_king,
    "enemies/mushroom_mage": mushroom_mage,
    "enemies/cave_slime": cave_slime,
    "enemies/toxic_toad": toxic_toad,
    "enemies/glow_bat": glow_bat,
    "enemies/shroom_brute": shroom_brute,
    "enemies/spore_mother": spore_mother,
    "enemies/frost_wolf": frost_wolf,
    "enemies/ice_wisp": ice_wisp,
    "enemies/yeti_cub": yeti_cub,
    "enemies/ice_troll": ice_troll,
    "enemies/frostbreath": frostbreath,
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
    main(sys.argv[1:] or None)

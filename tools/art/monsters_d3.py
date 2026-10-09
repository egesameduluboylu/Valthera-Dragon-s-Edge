"""Dungeon 3 (the Frozen Pass) monsters as animated cut-out rigs, painted semi-realistic style (m8).

    python3 tools/art/monsters_d3.py                 # all five
    python3 tools/art/monsters_d3.py frost_wolf ...  # only these

writes assets/rigs/<id>/ (part PNGs + rig.json, see rig.py) and the flat menu picture
assets/sprites/enemies/<id>.png (512 px; the boss 768 px wide). Every monster faces left.

    frost_wolf   beast    1024 x 1024  wolf with a glowing ice-crystal mane, four legs, jaw, tail chain
    ice_wisp     floater  1024 x 1024  faceted ice spirit, crown of shards, trailing wisps, orbiting shards
    yeti_cub     humanoid 1024 x 1024  shaggy young yeti winding up a snowball throw
    ice_troll    humanoid 1024 x 1024  elite: hulking troll in ice armour with a crystal club
    frostbreath  dragon   1920 x 1344  boss: frost dragon, wings, jaw, tail chain, frost breath fx

Painting model: every part is painted at 2x (SS) in a local buffer around it and downscaled with LANCZOS.
Shapes are soft masks; `paint` lights them from a height field (a blurred mask, so every mass reads as a
rounded volume) with a warm key light from the upper left, a cool fill, a strong ice-blue rim light on the
far (right) edge, a thin colour-matched line that fades where the light hits, brush grain and fur strokes.
Crystals are `gem`s: flat facets with normals from a raised apex, so they catch light facet by facet,
with a white-cyan glowing core, bright ridges and a halo.
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rig  # noqa: E402

SS = 2
F32 = np.float32


def _n3(x, y, z):
    n = math.sqrt(x * x + y * y + z * z)
    return np.array([x / n, y / n, z / n], F32)


LIGHT = _n3(-0.58, -0.70, 0.62)      # warm key from the upper left
FILLD = _n3(0.70, 0.35, 0.45)        # cool fill from the right / below
RIMD = _n3(0.92, -0.25, -0.30)       # rim from behind on the right
HALF = _n3(LIGHT[0], LIGHT[1], LIGHT[2] + 1.0)

WARM = np.array([1.0, 0.95, 0.86], F32)
COOLF = np.array([0.36, 0.52, 0.86], F32)
RIMC = np.array([0.72, 0.93, 1.0], F32)
HAZE = np.array([0.62, 0.72, 0.86], F32)


def C(h):
    """'#rrggbb' -> float rgb."""
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ blurs and noise

def _box(a, k, axis):
    if k < 1:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (k + 1, k)
    c = np.cumsum(np.pad(a, pad).astype(np.float64), axis=axis)
    if axis == 0:
        out = c[2 * k + 1:2 * k + 1 + n] - c[:n]
    else:
        out = c[:, 2 * k + 1:2 * k + 1 + n] - c[:, :n]
    return (out / (2 * k + 1)).astype(F32)


def blur(a, sigma):
    """Gaussian-ish blur (three box passes) of a float array (h, w) or (h, w, c); zero outside."""
    if sigma < 0.6:
        return a
    if sigma > 9:
        f = int(sigma / 4.5)
        h, w = a.shape[:2]
        hp, wp = (h + f - 1) // f * f, (w + f - 1) // f * f
        pad = [(0, hp - h), (0, wp - w)] + [(0, 0)] * (a.ndim - 2)
        small = np.pad(a, pad).reshape((hp // f, f, wp // f, f) + a.shape[2:]).mean(axis=(1, 3))
        small = blur(small, sigma / f)
        if a.ndim == 2:
            big = np.asarray(Image.fromarray(small.astype(F32)).resize((wp, hp), Image.BICUBIC))
        else:
            big = np.stack([np.asarray(Image.fromarray(small[..., i].astype(F32)).resize((wp, hp), Image.BICUBIC))
                            for i in range(a.shape[2])], -1)
        big = big[:h, :w].astype(F32)
        k = max(1, f // 2)
        return _box(_box(big, k, 0), k, 1)
    k = max(1, int(round((math.sqrt(4 * sigma * sigma / 3 + 1) - 1) / 2)))
    out = a.astype(F32)
    for _ in range(3):
        out = _box(_box(out, k, 0), k, 1)
    return out


def vnoise(h, w, cell, rng):
    """Smooth value noise in 0..1 with feature size `cell` pixels."""
    cell = max(1.0, cell)
    gh, gw = int(h / cell) + 4, int(w / cell) + 4
    small = rng.random((gh, gw)).astype(F32)
    big = np.asarray(Image.fromarray(small).resize((int(gw * cell), int(gh * cell)), Image.BICUBIC))
    return np.clip(big[int(cell):int(cell) + h, int(cell):int(cell) + w], 0, 1).astype(F32)


def fbm(h, w, cell, rng, octaves=3):
    out = np.zeros((h, w), F32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        out += vnoise(h, w, cell, rng) * amp
        tot += amp
        amp *= 0.5
        cell /= 2.0
    return out / tot


# ------------------------------------------------------------------ geometry helpers

def catmull(pts, closed=False, n=10):
    """Centripetal-ish Catmull-Rom through pts; returns a list of (x, y)."""
    P = [np.array(p, np.float64) for p in pts]
    if len(P) < 3:
        if len(P) == 2:
            return [tuple(P[0] + (P[1] - P[0]) * t) for t in np.linspace(0, 1, n + 1)]
        return [tuple(p) for p in P]
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    if not closed:
        out.append(tuple(P[-2]))
    return out


def rot(p, c, deg):
    r = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


def along(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# ------------------------------------------------------------------ part buffer

class Part:
    """A part painted at SS x in a local window `box` (canvas coords) of a canvas cw x ch.
    Colour is stored premultiplied."""

    def __init__(self, canvas, box, seed=1):
        cw, ch = canvas
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(cw, x1), min(ch, y1)
        self.canvas = (cw, ch)
        self.ox, self.oy = x0, y0
        self.W, self.H = (x1 - x0) * SS, (y1 - y0) * SS
        self.c = np.zeros((self.H, self.W, 3), F32)
        self.a = np.zeros((self.H, self.W), F32)
        self.rng = np.random.default_rng(seed)
        self.pyr = random.Random(seed)
        self._grid = None

    # -- coordinates
    def L(self, p):
        return ((p[0] - self.ox) * SS, (p[1] - self.oy) * SS)

    def grid(self):
        """Canvas coordinates of every local pixel (X, Y)."""
        if self._grid is None:
            ys = self.oy + (np.arange(self.H, dtype=F32) + 0.5) / SS
            xs = self.ox + (np.arange(self.W, dtype=F32) + 0.5) / SS
            self._grid = np.meshgrid(xs, ys)
        return self._grid

    def _img(self):
        return Image.new("L", (self.W, self.H), 0)

    def _arr(self, im, aa=0.7):
        if aa:
            im = im.filter(ImageFilter.GaussianBlur(aa))
        return np.asarray(im, dtype=F32) / 255.0

    # -- masks
    def poly(self, pts, aa=0.7):
        im = self._img()
        ImageDraw.Draw(im).polygon([self.L(p) for p in pts], fill=255)
        return self._arr(im, aa)

    def shape(self, pts, n=8, aa=0.7):
        """Closed smooth shape through control points."""
        return self.poly(catmull(pts, closed=True, n=n), aa)

    def ellipse(self, c, rx, ry, ang=0.0, aa=0.7):
        pts = [rot((c[0] + rx * math.cos(t), c[1] + ry * math.sin(t)), c, ang)
               for t in np.linspace(0, 2 * math.pi, 72, endpoint=False)]
        return self.poly(pts, aa)

    def tube(self, pts, radii, aa=0.7, n=12):
        """A limb: spline through pts with radius interpolated along it (union of dense discs)."""
        path = catmull(pts, closed=False, n=n)
        rs = np.interp(np.linspace(0, 1, len(path)), np.linspace(0, 1, len(radii)), radii)
        im = self._img()
        d = ImageDraw.Draw(im)
        prev = None
        for (x, y), r in zip(path, rs):
            X, Y = self.L((x, y))
            R = r * SS
            if prev is not None:
                px, py, pr = prev
                dist = math.hypot(X - px, Y - py)
                steps = max(1, int(dist / max(1.0, min(R, pr) * 0.3)))
                for s in range(1, steps + 1):
                    t = s / steps
                    cx, cy, cr = px + (X - px) * t, py + (Y - py) * t, pr + (R - pr) * t
                    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=255)
            else:
                d.ellipse([X - R, Y - R, X + R, Y + R], fill=255)
            prev = (X, Y, R)
        return self._arr(im, aa)

    def stroke_mask(self, pts, w0, w1, n=10, aa=0.7):
        return self.tube(pts, [w0 / 2.0, w1 / 2.0], aa=aa, n=n)

    def tri(self, a, b, c, aa=0.5):
        return self.poly([a, b, c], aa)

    # -- fur, tufts and texture
    def tufts(self, m, spacing=10, length=22, width=9, flow=(0.0, 1.0), lean=0.55, seed=0, jitter=0.4,
              where=None):
        """Adds small pointed fur tufts along the edge of mask m; returns the union mask."""
        rng = random.Random(seed)
        e = blur(m, 1.5 * SS)
        gy, gx = np.gradient(e)
        edge = (m > 0.45) & (m < 0.8)
        ys, xs = np.nonzero(edge)
        if len(xs) == 0:
            return m
        want = int(len(xs) / (spacing * SS) / 2.2) + 1
        idx = [rng.randrange(len(xs)) for _ in range(want)]
        im = self._img()
        d = ImageDraw.Draw(im)
        fx, fy = flow
        for i in idx:
            y, x = ys[i], xs[i]
            X, Y = self.ox + x / SS, self.oy + y / SS
            if where is not None and not where(X, Y):
                continue
            ox, oy = -gx[y, x], -gy[y, x]
            n = math.hypot(ox, oy) + 1e-6
            ox, oy = ox / n, oy / n
            dx, dy = ox * (1 - lean) + fx * lean, oy * (1 - lean) + fy * lean
            dn = math.hypot(dx, dy) + 1e-6
            dx, dy = dx / dn, dy / dn
            L = length * (1 - jitter + 2 * jitter * rng.random()) * SS
            W = width * (0.7 + 0.6 * rng.random()) * SS
            px, py = -dy, dx
            bx, by = x - dx * W * 0.8, y - dy * W * 0.8
            bend = (rng.random() - 0.5) * 0.7
            tip = (x + dx * L + px * L * bend, y + dy * L + py * L * bend)
            ml = (x + dx * L * 0.45 + px * (W * 0.42 + L * bend * 0.35), y + dy * L * 0.45 + py * (W * 0.42 + L * bend * 0.35))
            mr = (x + dx * L * 0.45 - px * (W * 0.30 - L * bend * 0.35), y + dy * L * 0.45 - py * (W * 0.30 - L * bend * 0.35))
            outline = catmull([(bx + px * W / 2, by + py * W / 2), ml, tip, mr, (bx - px * W / 2, by - py * W / 2)],
                              closed=False, n=5)
            d.polygon(outline, fill=255)
        t = self._arr(im, 0.6)
        return np.maximum(m, t)

    def fur(self, m, flow, length=16, density=1.0, width=1.6, seed=0, soft=0.3, contrast=1.0):
        """Fur strokes following the angle field flow(X, Y) (degrees, canvas coords): returns a -1..1 map."""
        rng = random.Random(seed)
        ys, xs = np.nonzero(m > 0.3)
        if len(xs) == 0:
            return np.zeros_like(m)
        n = int(len(xs) / (SS * SS) / (length * width * 0.9) * density * 18)
        im = Image.new("L", (self.W, self.H), 128)
        d = ImageDraw.Draw(im)
        for _ in range(n):
            i = rng.randrange(len(xs))
            x, y = xs[i], ys[i]
            X, Y = self.ox + x / SS, self.oy + y / SS
            ang = math.radians(flow(X, Y) + rng.uniform(-14, 14))
            L = length * rng.uniform(0.55, 1.25) * SS
            bend = rng.uniform(-0.25, 0.25)
            dx, dy = math.cos(ang), math.sin(ang)
            mx, my = x + dx * L * 0.5 - dy * L * bend * 0.3, y + dy * L * 0.5 + dx * L * bend * 0.3
            ex, ey = x + dx * L, y + dy * L
            v = rng.random()
            col = int(128 + 110 * (v - 0.45) * 2.0)
            col = max(0, min(255, col))
            w = max(1, int(round(width * SS * rng.uniform(0.7, 1.3))))
            d.line([(x, y), (mx, my), (ex, ey)], fill=col, width=w)
        out = (np.asarray(im.filter(ImageFilter.GaussianBlur(max(0.5, soft * SS))), dtype=F32) - 128) / 128.0
        out = np.clip(out * contrast, -1, 1)
        return out * (m > 0.02)

    # -- painting
    def _paint(self, m, ramp, r=20, bump=None, bk=0.0, cmod=None, cm=0.0, spec=0.0, shin=30, rim=0.9, rimc=None,
              line=1.0, lw=1.0, cast=0.35, castoff=(5, 7), castr=8, fill=0.22, grain=0.05, emis=None, lift=0.0,
              ramp_shift=None, flat=0.0, ink=None, opacity=1.0, hm=None):
        """Paints mask m (0..1) with lighting.
        ramp: [(t, rgb)] colour ramp from deepest shadow (0) to highlight (1).
        r: height-field radius (canvas px) - how round the mass is. bump/bk: extra height detail.
        cmod/cm: a -1..1 map that shifts the ramp position (fur strokes, mottling).
        ramp_shift: an array added to the ramp position (e.g. belly lighter)."""
        if m.max() <= 0.01:
            return
        R = max(1.0, r * SS)
        h = blur(m if hm is None else hm, R * 0.55)
        if bump is not None and bk:
            h = h + bump * bk * 0.02
        gy, gx = np.gradient(h)
        k = R * 1.7
        nx, ny, nz = -gx * k, -gy * k, np.ones_like(h)
        if flat:
            nz = nz + flat
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx * inv, ny * inv, nz * inv
        d = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
        t = np.clip((d + 0.2) / 1.3, 0, 1)
        if cmod is not None and cm:
            t = t + cmod * cm
        if ramp_shift is not None:
            t = t + ramp_shift
        if grain:
            t = t + (vnoise(self.H, self.W, 3.0 * SS, self.rng) - 0.5) * grain
        t = np.clip(t + lift, 0, 1)
        col = ramp_eval(ramp, t)
        key = np.clip(d, 0, 1) ** 3
        col = col + np.array([0.09, 0.05, -0.03], F32)[None, None, :] * key[..., None]
        f = np.clip(nx * FILLD[0] + ny * FILLD[1] + nz * FILLD[2], 0, 1)
        col = col + (COOLF * fill)[None, None, :] * f[..., None] * 0.6
        if spec:
            s = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** shin * spec
            col = col + WARM[None, None, :] * s[..., None]
        if rim:
            rd = np.clip(nx * RIMD[0] + ny * RIMD[1] + nz * RIMD[2], 0, 1)
            rv = smooth(0.05, 0.55, rd) * rim
            rc = RIMC if rimc is None else rimc
            col = col + rc[None, None, :] * rv[..., None] * 0.85
        if emis is not None:
            col = col + emis
        if line:
            e = blur(m, lw * 1.25 * SS)
            band = m * np.clip((0.86 - e) / 0.34, 0, 1)
            inkc = ramp_eval(ramp, np.zeros(1, F32))[0] * 0.42 if ink is None else ink
            ia = band * line * (1 - 0.8 * np.clip(d, 0, 1) ** 0.8) * 0.9
            col = col * (1 - ia[..., None]) + inkc[None, None, :] * ia[..., None]
        col = np.clip(col, 0, 1.2)
        if cast:
            self.cast(m, cast, castoff, castr)
        mm = (m * opacity)[..., None]
        self.c[...] = col * mm + self.c * (1 - mm)
        self.a[...] = m * opacity + self.a * (1 - m * opacity)

    def _cast(self, m, amount=0.35, off=(5, 7), r=8):
        """Soft cool shadow of mask m onto what is already painted (occlusion between masses)."""
        dx, dy = int(off[0] * SS), int(off[1] * SS)
        sh = np.zeros_like(m)
        H, W = m.shape
        sy0, sy1 = max(0, -dy), min(H, H - dy)
        sx0, sx1 = max(0, -dx), min(W, W - dx)
        sh[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] = m[sy0:sy1, sx0:sx1]
        sh = blur(np.maximum(sh, blur(m, r * SS * 0.5) * 0.6), r * SS) * (1 - m) * amount
        tint = np.array([0.55, 0.62, 0.9], F32)
        self.c *= (1 - sh[..., None] * (1 - tint[None, None, :]))

    def fill(self, m, rgb, alpha=1.0):
        mm = (m * alpha)[..., None]
        self.c[...] = np.asarray(rgb, F32)[None, None, :] * mm + self.c * (1 - mm)
        self.a[...] = m * alpha + self.a * (1 - m * alpha)

    def over_color(self, m, rgb, alpha=1.0):
        """Recolours already painted pixels inside m (keeps alpha)."""
        mm = (m * alpha)[..., None] * self.a[..., None]
        self.c[...] = np.asarray(rgb, F32)[None, None, :] * mm + self.c * (1 - mm)

    def shade(self, m, rgb, amount):
        """Multiplies painted pixels in m toward rgb (glazes: shadows, occlusion)."""
        k = (m * amount)[..., None]
        self.c[...] = self.c * (1 - k) + self.c * np.asarray(rgb, F32)[None, None, :] * k

    def light(self, m, rgb, amount):
        """Screen-adds light onto painted pixels in m (reflected light, glow spill)."""
        k = (m * amount)[..., None] * self.a[..., None]
        col = np.asarray(rgb, F32)[None, None, :]
        self.c[...] = self.c + col * k * (1 - np.clip(self.c, 0, 1))

    def _glow(self, m, rgb, sigma, amount=1.0, core=None):
        """A glow: blurred m screen-added; also spreads outside the painted area as translucent light."""
        g = blur(m, sigma * SS) * amount
        if core is not None:
            g = np.maximum(g, m * core)
        g = np.clip(g, 0, 1)
        col = np.asarray(rgb, F32)[None, None, :]
        self.c[...] = self.c + col * g[..., None] * (1 - np.clip(self.c, 0, 1))
        self.a[...] = self.a + g * (1 - self.a)

    def haze(self, amount, rgb=None):
        rgb = HAZE if rgb is None else np.asarray(rgb, F32)
        self.c[...] = self.c * (1 - amount) + rgb[None, None, :] * self.a[..., None] * amount

    def line(self, pts, w, rgb, alpha=1.0, n=8, w1=None):
        m = self.tube(pts, [w / 2.0, (w if w1 is None else w1) / 2.0], n=n, aa=0.6)
        mm = (m * alpha)[..., None] * self.a[..., None]
        self.c[...] = np.asarray(rgb, F32)[None, None, :] * mm + self.c * (1 - mm)

    def clip_to(self, m):
        self.c *= m[..., None]
        self.a *= m

    def erase(self, m):
        self.c *= (1 - m)[..., None]
        self.a *= (1 - m)

    # -- crystals
    def _gem(self, outline, apex, height=1.0, ramp=None, glowc=None, ridge=0.8, edge=1.0, seed=0,
             core=0.35, alpha=1.0, cast=0.3, base=None, **_):
        """Facets of a crystal (see gem)."""
        ramp = ramp or ICE
        glowc = GLOWC if glowc is None else glowc
        ax, ay = apex
        n = len(outline)
        size = max(math.hypot(p[0] - ax, p[1] - ay) for p in outline)
        Hh = size * height
        full = self.poly(outline, aa=0.6)
        if cast:
            self._cast(full, cast, (4, 6), 6)
        col = np.zeros((self.H, self.W, 3), F32)
        rng = random.Random(seed)
        X, Y = self.grid()
        for i in range(n):
            p1, p2 = outline[i], outline[(i + 1) % n]
            u = np.array([p1[0] - ax, p1[1] - ay, -Hh])
            v = np.array([p2[0] - ax, p2[1] - ay, -Hh])
            nn = np.cross(u, v)
            if nn[2] < 0:
                nn = -nn
            nn = nn / (np.linalg.norm(nn) + 1e-9)
            d = float(nn @ LIGHT)
            t = np.clip((d + 0.1) / 1.1, 0, 1) * 0.84 + rng.uniform(-0.08, 0.08)
            tri = self.poly([apex, p1, p2], aa=0.0)
            sl = self._slices(tri, 1)
            if sl is None:
                continue
            tri = tri[sl]
            Xs, Ys = X[sl], Y[sl]
            ex, ey = (p1[0] + p2[0]) / 2 - ax, (p1[1] + p2[1]) / 2 - ay
            el = ex * ex + ey * ey + 1e-6
            g = np.clip(((Xs - ax) * ex + (Ys - ay) * ey) / el, 0, 1)
            tt = np.clip(t + (0.45 - g) * 0.3, 0, 1)
            fc = ramp_eval(ramp, tt)
            s = max(0.0, float(nn @ HALF)) ** 90 * 0.45
            rd = max(0.0, float(nn @ RIMD))
            fc = fc + s + RIMC * float(smooth(0.0, 0.6, np.array(rd))) * 0.45
            c = col[sl]
            c[...] = c * (1 - tri[..., None]) + fc * tri[..., None]
        hard = self.poly(outline, aa=0.0)
        # deeper, more saturated toward the base (thickness of the ice)
        if base is not None:
            bx, by = base
            dist = np.sqrt((X - bx) ** 2 + (Y - by) ** 2) / (size * 1.6)
            k = np.clip(1.15 - dist, 0, 1) ** 1.3 * 0.6
            deep = ramp_eval(ramp, np.full(1, 0.12, F32))[0]
            col = col * (1 - k[..., None]) + deep * k[..., None]
        # light trapped inside
        if core:
            gm = blur(hard, size * SS * 0.2)
            inner = np.clip(gm * 1.5 - 0.45, 0, 1) * core
            col = col + glowc[None, None, :] * inner[..., None]
        # ridges from the apex to every corner and a few fracture planes
        im = self._img()
        dr = ImageDraw.Draw(im)
        if ridge:
            for p in outline:
                dr.line([self.L(apex), self.L(p)], fill=int(255 * ridge), width=max(1, int(1.1 * SS)))
        for _ in range(rng.randint(1, 3)):
            q1 = outline[rng.randrange(n)]
            t1, t2 = rng.uniform(0.15, 0.5), rng.uniform(0.5, 0.9)
            a1 = (ax + (q1[0] - ax) * t1 + rng.uniform(-3, 3), ay + (q1[1] - ay) * t1)
            q2 = outline[rng.randrange(n)]
            a2 = (ax + (q2[0] - ax) * t2, ay + (q2[1] - ay) * t2 + rng.uniform(-3, 3))
            dr.line([self.L(a1), self.L(a2)], fill=110, width=max(1, int(0.8 * SS)))
        rm = self._arr(im, 0.7) * hard
        col = col * (1 - rm[..., None] * 0.75) + np.array([0.88, 1.0, 1.0], F32)[None, None, :] * rm[..., None] * 0.75
        # thin outer edge: dark on the shadow side, bright on the lit side
        if edge:
            e = blur(full, 1.1 * SS)
            band = full * np.clip((0.86 - e) / 0.34, 0, 1)
            gy, gx = np.gradient(blur(full, 2 * SS))
            gl = np.sqrt(gx * gx + gy * gy) + 1e-6
            lit = np.clip((gx * LIGHT[0] + gy * LIGHT[1]) / gl, -1, 1)  # inward normal toward light
            dark = ramp_eval(ramp, np.zeros(1, F32))[0] * 0.55
            brightc = np.array([0.92, 1.0, 1.0], F32)
            lk = np.clip(-lit * 1.4, 0, 1)[..., None]
            ec = dark * (1 - lk) + brightc * lk
            ea = (band * edge * 0.92)[..., None]
            col = col * (1 - ea) + ec * ea
        m = full * alpha
        col = np.clip(col, 0, 1.2)
        self.c[...] = col * m[..., None] + self.c * (1 - m[..., None])
        self.a[...] = m + self.a * (1 - m)

    def shard(self, base, tip, w, glow=0.0, ramp=None, seed=0, lean=0.12, shoulder=0.68, **kw):
        """A single pointed ice shard from base to tip (hexagonal prism seen 3/4)."""
        bx, by = base
        tx, ty = tip
        L = math.hypot(tx - bx, ty - by)
        ux, uy = (tx - bx) / L, (ty - by) / L
        vx, vy = -uy, ux
        hw = w / 2.0
        s = shoulder
        pts = [(bx + vx * hw * 0.8, by + vy * hw * 0.8),
               (bx + ux * L * s + vx * hw, by + uy * L * s + vy * hw),
               (tx, ty),
               (bx + ux * L * s - vx * hw, by + uy * L * s - vy * hw),
               (bx - vx * hw * 0.8, by - vy * hw * 0.8),
               (bx - ux * hw * 0.4, by - uy * hw * 0.4)]
        ap = (bx + ux * L * 0.62 + vx * hw * lean * 2, by + uy * L * 0.62 + vy * hw * lean * 2)
        kw.setdefault("base", base)
        self.gem(pts, ap, height=0.35, ramp=ramp, glow=glow, seed=seed, **kw)

    def _sparkle(self, c, size, amount=1.0):
        """A small four-point star glint."""
        if size < 1.5:
            return
        im = self._img()
        d = ImageDraw.Draw(im)
        x, y = self.L(c)
        s = size * SS
        w = max(1.0, s * 0.12)
        d.polygon([(x - s, y), (x, y - w), (x + s, y), (x, y + w)], fill=255)
        d.polygon([(x, y - s * 0.8), (x - w, y), (x, y + s * 0.8), (x + w, y)], fill=255)
        m = self._arr(im, 0.9) * amount
        self.glow(m, np.array([1.0, 1.0, 1.0], F32), size * 0.25, 0.5, core=1.0)

    # -- windows: operations run on a view around the shape only (fast on big parts)
    def view(self, ys, xs):
        q = Part.__new__(Part)
        q.canvas = self.canvas
        q.ox = self.ox + xs.start / SS
        q.oy = self.oy + ys.start / SS
        q.c = self.c[ys, xs]
        q.a = self.a[ys, xs]
        q.H, q.W = q.a.shape
        q.rng = self.rng
        q.pyr = self.pyr
        q._grid = None
        return q

    def _slices(self, m, margin):
        rows = np.nonzero(m.max(axis=1) > 0.004)[0]
        cols = np.nonzero(m.max(axis=0) > 0.004)[0]
        if len(rows) == 0:
            return None
        mg = int(margin * SS)
        y0 = max(0, (rows[0] - mg) // SS * SS)
        x0 = max(0, (cols[0] - mg) // SS * SS)
        y1 = min(self.H, rows[-1] + 1 + mg)
        x1 = min(self.W, cols[-1] + 1 + mg)
        return slice(y0, y1), slice(x0, x1)

    def _box_slices(self, box):
        x0, y0, x1, y1 = box
        X0 = max(0, int((x0 - self.ox) * SS) // SS * SS)
        Y0 = max(0, int((y0 - self.oy) * SS) // SS * SS)
        X1 = min(self.W, int((x1 - self.ox) * SS) + 1)
        Y1 = min(self.H, int((y1 - self.oy) * SS) + 1)
        return slice(Y0, max(Y0 + 2, Y1)), slice(X0, max(X0 + 2, X1))

    @staticmethod
    def _cut(v, sl):
        if isinstance(v, np.ndarray) and v.ndim >= 2:
            return v[sl[0], sl[1]]
        return v

    def paint(self, m, ramp, r=20, **kw):
        margin = max(r * 1.2, kw.get("castr", 8) * 3 + 12) + 6
        sl = self._slices(m, margin)
        if sl is None:
            return
        kw = {k: self._cut(v, sl) for k, v in kw.items()}
        self.view(*sl)._paint(m[sl[0], sl[1]], ramp, r=r, **kw)

    def cast(self, m, amount=0.35, off=(5, 7), r=8):
        sl = self._slices(m, r * 3 + max(abs(off[0]), abs(off[1])) + 8)
        if sl is None:
            return
        self.view(*sl)._cast(m[sl[0], sl[1]], amount, off, r)

    def glow(self, m, rgb, sigma, amount=1.0, core=None):
        sl = self._slices(m, sigma * 3.2 + 4)
        if sl is None:
            return
        self.view(*sl)._glow(m[sl[0], sl[1]], rgb, sigma, amount, core)

    def gem(self, outline, apex, height=1.0, glow=0.0, glowc=None, spark=True, **kw):
        """A faceted crystal: triangles from a raised apex to each outline edge, flat shaded, with a glowing
        core, bright ridges, fracture planes, a colour-matched edge and (glow > 0) a halo."""
        xs = [p[0] for p in outline] + [apex[0]]
        ys = [p[1] for p in outline] + [apex[1]]
        mg = 24
        sl = self._box_slices((min(xs) - mg, min(ys) - mg, max(xs) + mg, max(ys) + mg))
        self.view(*sl)._gem(outline, apex, height=height, glowc=glowc, **kw)
        size = max(max(xs) - min(xs), max(ys) - min(ys))
        if glow:
            self.glow(self.poly(outline, aa=0.0), GLOWC if glowc is None else glowc, max(3, size * 0.3),
                      glow * 0.5)
        if spark:
            k = random.Random(kw.get("seed", 0)).randrange(len(outline))
            p = outline[k]
            self.sparkle((apex[0] + (p[0] - apex[0]) * 0.55, apex[1] + (p[1] - apex[1]) * 0.55), size * 0.1, 0.7)

    def sparkle(self, c, size, amount=1.0):
        mg = size * 1.5 + 8
        sl = self._box_slices((c[0] - mg, c[1] - mg, c[0] + mg, c[1] + mg))
        self.view(*sl)._sparkle(c, size, amount)

    # -- output
    def image(self):
        """Full-canvas RGBA (PIL) of this part."""
        a = np.clip(self.a, 0, 1)
        rgb = np.where(a[..., None] > 1e-4, self.c / np.maximum(a[..., None], 1e-4), 0)
        arr = np.dstack([np.clip(rgb, 0, 1), a])
        im = Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBA")
        im = im.convert("RGBa").resize((self.W // SS, self.H // SS), Image.LANCZOS).convert("RGBA")
        out = Image.new("RGBA", self.canvas, (0, 0, 0, 0))
        out.paste(im, (self.ox, self.oy))
        edge = np.asarray(im)[..., 3]
        touch = []
        if self.ox > 0 and edge[:, 0].max() > 8:
            touch.append("left")
        if self.oy > 0 and edge[0, :].max() > 8:
            touch.append("top")
        if self.ox + im.size[0] < self.canvas[0] and edge[:, -1].max() > 8:
            touch.append("right")
        if self.oy + im.size[1] < self.canvas[1] and edge[-1, :].max() > 8:
            touch.append("bottom")
        if touch:
            print("   warning: part at", (self.ox, self.oy, self.ox + im.size[0], self.oy + im.size[1]), "touches its box on", touch, file=sys.stderr)
        return out


_LUT = {}


def ramp_eval(ramp, t):
    key = id(ramp)
    lut = _LUT.get(key)
    if lut is None or lut[0] is not ramp:
        pos = np.array([p for p, _ in ramp], F32)
        cols = np.array([c for _, c in ramp], F32)
        xs = np.linspace(0, 1, 1024)
        lut = (ramp, np.stack([np.interp(xs, pos, cols[:, i]) for i in range(3)], -1).astype(F32))
        _LUT[key] = lut
    idx = np.clip((np.asarray(t, F32) * 1023 + 0.5), 0, 1023).astype(np.int32)
    return lut[1][idx]


def _ramp_eval_slow(ramp, t):
    pos = np.array([p for p, _ in ramp], F32)
    cols = np.array([c for _, c in ramp], F32)
    shp = np.shape(t)
    tf = np.asarray(t, F32).ravel()
    out = np.stack([np.interp(tf, pos, cols[:, i]) for i in range(3)], -1)
    return out.reshape(shp + (3,)).astype(F32)


def mk_ramp(*hexes):
    """Evenly spaced ramp from shadow to highlight."""
    n = len(hexes)
    return [(i / (n - 1), C(h)) for i, h in enumerate(hexes)]


# ------------------------------------------------------------------ materials (ramps: deep shadow .. highlight)

ICE = mk_ramp("#0a1c46", "#12428a", "#2478c4", "#4fb4ea", "#a6eaff", "#ffffff")
ICE_DEEP = mk_ramp("#0c2148", "#173f7a", "#2a6cb0", "#56a8e0", "#a8e4ff", "#f0fdff")
FUR_W = mk_ramp("#1c254c", "#3a4a7a", "#687ea8", "#9db2ce", "#d0ddea", "#f8faff")
FUR_G = mk_ramp("#222a52", "#3e4e7c", "#6479a4", "#93a8c8", "#c3d2e4", "#eef2f6")
SKIN_B = mk_ramp("#141c3a", "#27365e", "#3e5582", "#5d7aa6", "#8aa6c6", "#cfe0ee")
SKIN_T = mk_ramp("#16203e", "#2a3c64", "#44628c", "#6a8cb2", "#9ab8d2", "#dceaf4")
HORN = mk_ramp("#2a2a40", "#4c4a62", "#7c7890", "#aeaabb", "#dcd8e0", "#fffaf2")
LEATHER = mk_ramp("#1c1418", "#34242a", "#523a36", "#765646", "#9c7a60", "#d0b494")
WOOD = mk_ramp("#1a1210", "#33221a", "#523826", "#765236", "#9c7550", "#caa27a")
MOUTH = mk_ramp("#1a0612", "#3a0e22", "#6a1c34", "#9a3448", "#c86070", "#f0a8b0")
TEETH = mk_ramp("#5a6278", "#8a94aa", "#b8c2d4", "#dce4ee", "#f4f8fc", "#ffffff")
SCALE = mk_ramp("#16264e", "#27477e", "#4574ac", "#78a8d4", "#b6daf0", "#f2fcff")
BELLY = mk_ramp("#2a3860", "#4c6690", "#7896bc", "#a8c4de", "#d4e6f2", "#fbffff")
MEMB = mk_ramp("#0e2450", "#1a3f7c", "#2d64a8", "#4a92cc", "#86c6ea", "#d0f2ff")
EYE_GLOW = C("#8ff4ff")
GLOWC = C("#7fe6ff")
WHITE = np.array([1, 1, 1], F32)


def fx_part(canvas, box, seed=1):
    return Part(canvas, box, seed)


def save_rig(rb, flat_size, rid):
    rb.save(flat=f"sprites/enemies/{rid}.png", flat_size=flat_size)


SCRATCH = "/tmp/claude-0/-home-claude-valthera-dragon-s-edge/9d7e6e94-5ed4-51a7-95df-cdb7958efe3b/scratchpad/m8"


# ------------------------------------------------------------------ shared helpers for the builders

def feather(P, m, p0, p1):
    """Fades mask m out toward p0 (0 at p0, 1 at p1): a soft joint edge that hides under the parent."""
    X, Y = P.grid()
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L2 = dx * dx + dy * dy
    t = np.clip(((X - p0[0]) * dx + (Y - p0[1]) * dy) / L2, 0, 1)
    return m * smooth(0.0, 1.0, t)


def furpaint(P, m, ramp, flow, r=40, lock=36, lockw=6, fine=0.45, cm=0.12, seed=0, bump=0.0, **kw):
    """Fur: soft clumped locks (value shifts + a little relief) and fine strands, following flow(X, Y)."""
    big = P.fur(m, flow, length=lock * 1.3, density=0.9, width=lockw, seed=seed, soft=1.3, contrast=1.3)
    fn = P.fur(m, flow, length=lock * 0.55, density=0.5, width=1.0, seed=seed + 11, soft=0.4) if fine else 0
    P.paint(m, ramp, r=r, bump=blur(big, 3) if bump else None, bk=bump, cmod=big + fn * fine, cm=cm,
            grain=0.02, **kw)


def lin(P, p0, p1):
    """0..1 ramp across the part from p0 to p1 (canvas points)."""
    X, Y = P.grid()
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    return np.clip(((X - p0[0]) * dx + (Y - p0[1]) * dy) / (dx * dx + dy * dy), 0, 1)


def radial(P, c, r):
    X, Y = P.grid()
    return np.clip(1 - np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2) / r, 0, 1)


def glow_eye(P, c, rx, ry, ang=0.0, col=None, pupil=True):
    """A glowing slit eye: white-cyan core, saturated iris, halo."""
    col = EYE_GLOW if col is None else col
    m = P.ellipse(c, rx, ry, ang)
    P.fill(P.ellipse(c, rx * 1.25, ry * 1.5, ang) * 0.6, C("#0a1430"), 0.8)
    P.fill(m, C("#06102a"))
    inner = P.ellipse((c[0] + rx * 0.05, c[1] + ry * 0.05), rx * 0.74, ry * 0.62, ang)
    P.fill(inner, C("#1aa6e0"))
    P.fill(P.ellipse((c[0], c[1]), rx * 0.6, ry * 0.5, ang), col * 0.95)
    core = P.ellipse((c[0] - rx * 0.12, c[1]), rx * 0.34, ry * 0.3, ang)
    P.fill(core, np.array([0.92, 1.0, 1.0], F32))
    if pupil:
        pm = P.ellipse((c[0] - rx * 0.05, c[1]), rx * 0.12, ry * 0.62, ang)
        P.fill(pm, C("#0e3a66"), 0.85)
    P.glow(m, col, max(rx, ry) * 0.8, 0.9)


def claws(P, pts, ramp=None, size=10):
    for (x, y, a) in pts:
        tip = (x + math.cos(math.radians(a)) * size, y + math.sin(math.radians(a)) * size)
        m = P.stroke_mask([(x, y), along((x, y), tip, 0.6), tip], size * 0.55, 0.8)
        P.paint(m, ramp or HORN, r=3, rim=0.5, cast=0.2, castr=3, lw=0.7)


def fx_glow(canvas, pts_masks, col, sigma, amount=1.0, box=None, core=0.0, seed=1):
    """An additive glow part: masks are painted into a Part and blurred."""
    P = Part(canvas, box, seed)
    for m_fn in pts_masks:
        m = m_fn(P)
        g = np.clip(blur(m, sigma * SS) * amount + m * core, 0, 1)
        P.c[...] = P.c + col[None, None, :] * g[..., None] * (1 - P.a[..., None])
        P.a[...] = P.a + g * (1 - P.a)
    return P


# ------------------------------------------------------------------ frost wolf

def shard_at(P, base, ang, L, w, **kw):
    tip = (base[0] + L * math.cos(math.radians(ang)), base[1] + L * math.sin(math.radians(ang)))
    P.shard(base, tip, w, **kw)


def build_frost_wolf():
    rid = "frost_wolf"
    CV = (1024, 1024)
    rb = rig.RigBuilder(rid, CV, feet=(545, 962), facing="left", kind="beast")
    FUR = FUR_W
    SADDLE = FUR_G
    FAR = mk_ramp("#1a2248", "#34436e", "#566c96", "#7e94b8", "#a8bad4", "#d0dcea")

    def vshift(P, y0, y1, top=0.06, bot=-0.16):
        return top + (bot - top) * lin(P, (0, y0), (0, y1))

    def leg(hip, knee, ankle, paw, radii, ramp, far, fore, seed, mass):
        box = (min(hip[0], knee[0], ankle[0]) - 130, hip[1] - 150, max(hip[0], knee[0], ankle[0]) + 130,
               ankle[1] + 60)
        U = Part(CV, box, seed)
        m = U.tube([(hip[0], hip[1] - 40), hip, knee, ankle], radii[:4])
        m = np.maximum(m, U.ellipse(*mass))
        if not far:
            m = feather(U, m, (hip[0], hip[1] - 70), (hip[0], hip[1] + 5))
        m = U.tufts(m, spacing=7, length=13, width=11, flow=(0.3, 1), lean=0.7, seed=seed,
                    where=lambda X, Y: Y > hip[1] + 40)
        furpaint(U, m, ramp, lambda X, Y: 95 if fore else 75, r=radii[1] * 1.1, lock=30, lockw=5, seed=seed,
                 line=0.8 if far else 0.0, ramp_shift=vshift(U, hip[1], ankle[1], 0.04, -0.12))
        if not far:
            e = blur(m, 1.4 * SS)
            band = m * np.clip((0.86 - e) / 0.34, 0, 1) * lin(U, (hip[0], hip[1] - 10), (hip[0], hip[1] + 90))
            U.shade(band, C("#1a2448"), 0.65)
        else:
            U.haze(0.2)
        box2 = (min(ankle[0], paw[0]) - 90, ankle[1] - 60, max(ankle[0], paw[0]) + 90, paw[1] + 30)
        Lp = Part(CV, box2, seed + 1)
        m2 = Lp.tube([ankle, along(ankle, paw, 0.6), (paw[0] + 6, paw[1] - 22)], [radii[3], radii[4], radii[4]])
        pw = Lp.shape([(paw[0] - 42, paw[1] - 6), (paw[0] - 30, paw[1] - 30), (paw[0] + 10, paw[1] - 38),
                       (paw[0] + 30, paw[1] - 22), (paw[0] + 28, paw[1] - 2), (paw[0] - 10, paw[1] + 2)])
        m2 = np.maximum(m2, pw)
        m2 = Lp.tufts(m2, spacing=8, length=10, width=9, flow=(0.2, 1), lean=0.7, seed=seed + 3,
                      where=lambda X, Y: Y < paw[1] - 30)
        furpaint(Lp, m2, ramp, lambda X, Y: 90, r=radii[4], lock=20, lockw=4, seed=seed + 1,
                 line=0.9, ramp_shift=-0.06)
        for k in range(3):
            toe = Lp.ellipse((paw[0] - 34 + k * 17, paw[1] - 8), 11, 10)
            Lp.paint(toe, ramp, r=8, cast=0.25, castr=4, lw=0.8)
        claws(Lp, [(paw[0] - 44 + k * 17, paw[1] - 4, 160 - k * 8) for k in range(3)], size=12)
        if far:
            Lp.haze(0.2)
        return U, Lp

    far_fore = leg((465, 575), (478, 700), (488, 862), (482, 956), [52, 42, 30, 22, 20], FAR, True, True, 10,
                   ((470, 590), 50, 80, -10))
    far_hind = leg((780, 575), (760, 700), (838, 835), (832, 952), [60, 46, 28, 20, 19], FAR, True, False, 20,
                   ((770, 600), 70, 90, 20))

    # ---------------- tail chain: a bushy brush curling up, crystals at the tip
    T1 = Part(CV, (660, 250, 960, 600), 30)
    m = T1.tube([(760, 500), (800, 460), (835, 405), (850, 350)], [34, 44, 50, 52])
    m = T1.tufts(m, spacing=5, length=26, width=16, flow=(0.5, -0.5), lean=0.55, seed=31)
    furpaint(T1, m, SADDLE, lambda X, Y: -60, r=44, lock=34, lockw=6, seed=31)
    T2 = Part(CV, (700, 30, 1000, 500), 32)
    m = T2.tube([(850, 400), (858, 330), (850, 265), (826, 205)], [52, 54, 44, 24])
    m = T2.tufts(m, spacing=5, length=28, width=16, flow=(0.1, -1), lean=0.55, seed=33)
    furpaint(T2, m, FUR, lambda X, Y: -95 + (Y - 300) * 0.12, r=44, lock=34, lockw=6, seed=33,
             ramp_shift=0.03)
    for i, (b, a, L, w) in enumerate([((840, 232), -78, 120, 36), ((818, 226), -112, 96, 30),
                                      ((856, 244), -48, 88, 26), ((828, 240), -95, 60, 22)]):
        shard_at(T2, b, a, L, w, glow=0.8, seed=40 + i)

    # ---------------- body
    B = Part(CV, (200, 280, 900, 790), 50)
    body = B.shape([(300, 470), (350, 432), (430, 412), (540, 428), (640, 432), (740, 420), (800, 445),
                    (830, 510), (815, 590), (775, 650), (705, 668), (630, 640), (560, 648), (480, 700),
                    (400, 722), (330, 690), (292, 600)], n=10)
    body = B.tufts(body, spacing=5, length=20, width=13, flow=(0.3, 1), lean=0.65, seed=51,
                   where=lambda X, Y: Y > 560)
    flow_body = lambda X, Y: 12 + np.clip((Y - 470) * 0.3, -20, 70)
    furpaint(B, body, FUR, flow_body, r=110, lock=44, lockw=7, seed=51, ramp_shift=vshift(B, 440, 720))
    sad = B.shape([(340, 440), (460, 410), (600, 428), (740, 418), (810, 450), (800, 520), (720, 505),
                   (620, 515), (520, 525), (410, 505)], n=10)
    sad = blur(B.tufts(sad, spacing=6, length=24, width=14, flow=(0.2, 1), lean=0.7, seed=52), 4 * SS) * body
    furpaint(B, sad, SADDLE, flow_body, r=110, lock=40, lockw=6, seed=52, cast=0.0, line=0.0, hm=body,
             ramp_shift=vshift(B, 440, 720))
    ruff = B.shape([(296, 480), (350, 452), (395, 520), (415, 620), (392, 718), (330, 700), (290, 620)])
    ruff = B.tufts(ruff, spacing=4, length=28, width=15, flow=(-0.2, 1), lean=0.6, seed=53)
    furpaint(B, ruff, FUR, lambda X, Y: 100, r=70, lock=36, lockw=6, seed=53, ramp_shift=0.04, cast=0.25)
    B.shade(blur(B.ellipse((560, 668), 190, 36), 16 * SS) * B.a, C("#4c5a90"), 0.4)
    for i, (b, a, L, w) in enumerate([((735, 432), -24, 46, 18), ((690, 436), -28, 60, 22),
                                      ((640, 438), -32, 76, 26)]):
        shard_at(B, b, a, L, w, glow=0.6, seed=55 + i)

    near_fore = leg((392, 585), (378, 705), (352, 865), (326, 960), [58, 46, 32, 24, 22], FUR, False, True, 60,
                    ((395, 590), 62, 98, -12))
    near_hind = leg((735, 560), (700, 700), (780, 835), (765, 958), [70, 52, 30, 22, 21], FUR, False, False, 70,
                    ((725, 590), 88, 108, 25))

    # ---------------- crystal mane: two clusters of hackles sweeping back from the neck and withers
    def mane(seed, box, shards, ruffpts):
        M = Part(CV, box, seed)
        for i, (b, a, L, w) in enumerate(shards):
            shard_at(M, b, a, L, w, glow=0.9, seed=seed + i, cast=0.3)
        rm = M.shape(ruffpts)
        rm = M.tufts(rm, spacing=4, length=22, width=13, flow=(0.6, -0.4), lean=0.5, seed=seed + 50,
                     where=lambda X, Y: Y < 470)
        rm = blur(rm, 2 * SS)
        furpaint(M, rm, FUR, lambda X, Y: -15, r=34, lock=30, lockw=5, seed=seed + 50, line=0.0, cast=0.15,
                 ramp_shift=vshift(M, 420, 500, 0.06, -0.06))
        return M

    mane_a = mane(80, (320, 60, 800, 540), [
        ((520, 448), -38, 150, 44), ((560, 450), -30, 105, 34), ((470, 440), -56, 215, 58),
        ((425, 445), -70, 240, 62), ((395, 452), -88, 170, 44), ((455, 455), -46, 170, 46)],
        [(400, 468), (450, 438), (540, 432), (600, 445), (580, 470), (470, 478)])
    mane_b = mane(90, (170, 150, 480, 590), [
        ((340, 470), -58, 150, 42), ((305, 478), -80, 175, 48), ((285, 492), -104, 120, 38),
        ((360, 468), -40, 110, 34)],
        [(270, 505), (300, 462), (370, 450), (410, 478), (390, 515), (310, 525)])

    # ---------------- head, jaw, mouth
    H = Part(CV, (30, 300, 400, 650), 100)
    ear_f = H.shape([(226, 422), (256, 352), (278, 346), (272, 420)], n=6)
    furpaint(H, ear_f, FAR, lambda X, Y: -70, r=12, lock=14, lockw=3, seed=101)
    skull = H.shape([(150, 452), (205, 420), (265, 414), (322, 442), (348, 500), (332, 560), (282, 592),
                     (230, 578), (200, 548), (160, 522)], n=10)
    muzzle = H.shape([(205, 443), (150, 460), (100, 486), (70, 506), (68, 528), (100, 540), (160, 546),
                      (218, 553), (232, 500)], n=8)
    head = np.maximum(skull, muzzle)
    cheek = H.shape([(250, 518), (300, 502), (348, 518), (352, 592), (302, 618), (255, 592)])
    cheek = H.tufts(cheek, spacing=4, length=28, width=14, flow=(0.5, 0.6), lean=0.7, seed=102)
    head = np.maximum(head, cheek)
    furpaint(H, head, FUR, lambda X, Y: 8 if X < 220 else 35, r=44, lock=22, lockw=4, seed=103)
    top = blur(H.shape([(92, 490), (150, 458), (210, 428), (272, 420), (322, 446), (300, 472), (232, 470),
                        (170, 488), (110, 506)], n=8), 3 * SS) * head
    furpaint(H, top, SADDLE, lambda X, Y: 5, r=44, lock=20, lockw=4, seed=104, cast=0.0, line=0.0, hm=head)
    for a, b in [((118, 494), (134, 508)), ((138, 486), (156, 502)), ((158, 480), (176, 496))]:
        H.line([a, along(a, b, 0.5), b], 2.6, C("#26325c"), 0.75)
    ear = H.shape([(262, 432), (298, 358), (330, 336), (324, 400), (302, 446)], n=6)
    furpaint(H, ear, FUR, lambda X, Y: -60, r=14, lock=16, lockw=3, seed=105, cast=0.35)
    inner = H.shape([(282, 425), (306, 372), (320, 360), (314, 405), (298, 430)], n=6) * ear
    H.paint(inner, SADDLE, r=6, lift=-0.25, line=0, cast=0)
    nose = H.shape([(58, 506), (76, 492), (98, 496), (100, 516), (82, 527), (62, 521)], n=6)
    H.paint(nose, mk_ramp("#05070f", "#0c1224", "#1c2640", "#34405e", "#6c7a98", "#c8d4ea"), r=8, spec=0.9,
            shin=40)
    lip = H.stroke_mask([(70, 530), (110, 541), (160, 548), (218, 557)], 9, 6)
    LIP = mk_ramp("#0a0c1c", "#161a30", "#262c48", "#3a4262", "#566080", "#8090b0")
    H.paint(lip, LIP, r=4, line=0, cast=0.1)
    for (x, y, L) in [(90, 537, 30), (182, 552, 22), (128, 544, 12), (150, 547, 10)]:
        f = H.poly([(x - 5, y - 2), (x + 5, y - 2), (x + 1, y + L)])
        H.paint(f, TEETH, r=3, spec=0.6, cast=0.15, castr=3, lw=0.6)
    brow = H.stroke_mask([(165, 452), (205, 443), (245, 455)], 13, 6)
    H.paint(brow, SADDLE, r=8, lift=-0.22, line=0.4, cast=0.35)
    glow_eye(H, (208, 468), 21, 9, -14)
    H.sparkle((198, 465), 11, 0.8)

    Mo = Part(CV, (50, 480, 300, 660), 110)
    mouth = Mo.shape([(72, 528), (160, 545), (228, 553), (252, 578), (236, 598), (150, 594), (88, 578)])
    Mo.paint(mouth, MOUTH, r=20, lift=-0.25, line=0, cast=0)
    Mo.shade(radial(Mo, (225, 575), 90), C("#200814"), 0.6)

    J = Part(CV, (40, 480, 330, 680), 120)
    tongue = J.shape([(95, 570), (140, 564), (200, 566), (218, 584), (160, 590), (100, 586)])
    J.paint(tongue, MOUTH, r=12, lift=0.1, spec=0.4, line=0.3, cast=0)
    jaw = J.shape([(255, 556), (212, 568), (150, 575), (100, 574), (80, 582), (96, 598), (150, 606),
                   (215, 606), (270, 592)], n=8)
    jaw = J.tufts(jaw, spacing=5, length=16, width=10, flow=(0.4, 1), lean=0.6, seed=121,
                  where=lambda X, Y: Y > 598)
    for (x, y, L) in [(104, 578, 22), (165, 577, 16), (135, 578, 9)]:
        f = J.poly([(x - 5, y + 3), (x + 5, y + 3), (x + 1, y - L)])
        J.paint(f, TEETH, r=3, spec=0.6, cast=0.1, castr=3, lw=0.6)
    furpaint(J, jaw, FUR, lambda X, Y: 20, r=16, lock=16, lockw=3, seed=122, cast=0.2, ramp_shift=-0.05)
    J.paint(J.stroke_mask([(84, 582), (150, 578), (220, 572)], 5, 3) * jaw, LIP, r=3, line=0, cast=0)

    # ---------------- fx
    fx_eye = fx_glow(CV, [lambda P: P.ellipse((208, 468), 16, 7, -14)], EYE_GLOW, 12, 0.9,
                     box=(110, 400, 310, 540))
    fx_mane = fx_glow(CV, [lambda P: P.poly([(400, 460), (440, 220), (480, 250), (600, 360), (640, 420),
                                             (560, 450)]),
                           lambda P: P.poly([(280, 490), (270, 360), (330, 330), (420, 390), (390, 470)])],
                      GLOWC, 34, 0.35, box=(150, 0, 850, 650))
    br = Part(CV, (0, 470, 240, 700), 130)
    rng = random.Random(7)
    for k in range(14):
        cx, cy = 70 - k * 4 + rng.uniform(-18, 18), 575 + rng.uniform(-40, 50)
        m = br.ellipse((cx, cy), rng.uniform(14, 30), rng.uniform(8, 18), rng.uniform(-30, 30))
        br.glow(m, C("#bfefff"), 10, 0.25)

    add = rb.add
    add("body", B.image(), "", "root", (570, 560), 10)
    add("far_fore_upper", far_fore[0].image(), "body", "leg_back_upper", (465, 585), 2)
    add("far_fore_lower", far_fore[1].image(), "far_fore_upper", "leg_back_lower", (488, 862), 1)
    add("far_hind_upper", far_hind[0].image(), "body", "leg_back_upper", (780, 580), 2)
    add("far_hind_lower", far_hind[1].image(), "far_hind_upper", "leg_back_lower", (838, 835), 1)
    add("tail_1", T1.image(), "body", "tail", (770, 490), 5)
    add("tail_2", T2.image(), "tail_1", "tail", (850, 385), 6)
    add("mane_back", mane_a.image(), "body", "hair", (470, 455), 12)
    add("near_hind_upper", near_hind[0].image(), "body", "leg_front_upper", (735, 570), 14)
    add("near_hind_lower", near_hind[1].image(), "near_hind_upper", "leg_front_lower", (780, 835), 13)
    add("near_fore_upper", near_fore[0].image(), "body", "leg_front_upper", (392, 595), 16)
    add("near_fore_lower", near_fore[1].image(), "near_fore_upper", "leg_front_lower", (352, 865), 15)
    add("mane_neck", mane_b.image(), "body", "hair", (330, 480), 18)
    add("head", H.image(), "body", "head", (310, 490), 21)
    add("mouth", Mo.image(), "head", "extra", (230, 560), 19)
    add("jaw", J.image(), "head", "jaw", (245, 565), 20)
    add("eye_glow", fx_eye.image(), "head", "fx", (208, 468), 30, blend="add")
    add("mane_glow", fx_mane.image(), "mane_back", "fx", (470, 455), 29, blend="add")
    add("breath", br.image(), "head", "fx", (100, 570), 31, blend="add")
    return rb, 512


# ------------------------------------------------------------------ ice wisp

def ribbon(P, pts, radii, ramp, opacity=0.8, glow=0.6, seed=0, fade_in=0.0, fade_out=0.0):
    """A trailing wisp of frozen light: translucent tapered ribbon with inner streaks and a glow.
    fade_in / fade_out: fraction of the length over which it fades (for soft overlapping joints)."""
    m = blur(P.tube(pts, radii, n=16), 1.5 * SS)
    t = lin(P, pts[0], pts[-1])
    op = np.ones_like(m) * opacity
    if fade_in:
        op = op * smooth(0.0, fade_in, t)
    if fade_out:
        op = op * (1 - smooth(1 - fade_out, 1.0, t))
    op = op * (1 - 0.55 * t)
    P.paint(m, ramp, r=max(radii) * 0.8, line=0.0, cast=0.0, rim=1.0, opacity=op, grain=0.04)
    m = m * op / max(opacity, 1e-3)
    path = catmull(pts, n=16)
    rng = random.Random(seed)
    for k in range(3):
        off = rng.uniform(-0.5, 0.5)
        sp = []
        for i, (x, y) in enumerate(path):
            j = min(len(path) - 1, i + 1)
            dx, dy = path[j][0] - path[max(0, i - 1)][0], path[j][1] - path[max(0, i - 1)][1]
            dn = math.hypot(dx, dy) + 1e-6
            r = float(np.interp(i / (len(path) - 1), np.linspace(0, 1, len(radii)), radii))
            sp.append((x - dy / dn * r * off, y + dx / dn * r * off))
        sm = P.tube(sp[::2], [3.0, 1.0], n=6) * m
        P.light(sm, C("#e8fbff"), 0.6)
    if glow:
        P.glow(m, GLOWC, max(radii) * 0.6, glow * 0.4)


def build_ice_wisp():
    rid = "ice_wisp"
    CV = (1024, 1024)
    rb = rig.RigBuilder(rid, CV, feet=(512, 966), facing="left", kind="floater")
    cx, cy = 492, 425
    WISP = mk_ramp("#1a4a8c", "#2c74be", "#4ea6e0", "#86d2f4", "#c6f0ff", "#ffffff")

    # crown of shards radiating behind the core
    Cr = Part(CV, (80, 20, 950, 800), 5)
    crown = [(-90, 250, 64), (-122, 225, 56), (-58, 230, 56), (-152, 190, 48), (-28, 200, 50), (178, 165, 44),
             (4, 175, 46), (150, 120, 36), (30, 130, 38)]
    for i, (a, L, w) in enumerate(crown):
        ra = math.radians(a)
        b = (cx + math.cos(ra) * 90, cy + math.sin(ra) * 110)
        t = (cx + math.cos(ra) * (90 + L), cy + math.sin(ra) * (110 + L))
        Cr.shard(b, t, w, glow=0.7, seed=200 + i, cast=0.0, ramp=ICE_DEEP)

    # wisps (tail chains)
    def wisp(seed, box1, pts1, r1, box2, pts2, r2):
        A = Part(CV, box1, seed)
        ribbon(A, pts1, r1, WISP, seed=seed, opacity=0.85, fade_out=0.25)
        Bp = Part(CV, box2, seed + 1)
        ribbon(Bp, [along(pts2[0], pts2[1], -0.6)] + pts2, [r2[0]] + r2, WISP, seed=seed + 1, opacity=0.6,
               fade_in=0.35)
        return A, Bp

    wa = wisp(300, (380, 480, 680, 820), [(495, 560), (505, 640), (535, 720), (560, 770)], [58, 44, 34, 28],
              (440, 680, 800, 960), [(555, 755), (590, 820), (650, 870), (715, 880)], [28, 20, 12, 4])
    wb = wisp(310, (280, 470, 560, 800), [(455, 540), (425, 620), (412, 700), (420, 760)], [44, 36, 28, 22],
              (280, 690, 620, 960), [(420, 745), (432, 810), (470, 870), (530, 905)], [22, 16, 10, 3])
    wc = wisp(320, (480, 450, 800, 760), [(545, 530), (590, 590), (645, 630), (690, 650)], [44, 34, 26, 22],
              (600, 520, 980, 760), [(680, 648), (740, 660), (800, 640), (840, 600)], [22, 16, 10, 3])

    # the core: a faceted crystal body with a face
    B = Part(CV, (250, 150, 750, 720), 10)
    outline = [(500, 232), (430, 285), (392, 350), (380, 440), (418, 530), (478, 606), (500, 612), (560, 545),
               (606, 450), (604, 350), (566, 280)]
    B.gem(outline, (470, 415), height=0.55, ramp=ICE_DEEP, core=0.55, glow=0.0, seed=11, cast=0.0)
    # depth: the lower right of the body sinks into deep blue, the upper left stays bright
    core_m = B.poly(outline)
    B.shade(core_m * smooth(0.35, 1.0, lin(B, (400, 280), (600, 600))), C("#12306a"), 0.75)
    # heart light inside
    B.glow(B.ellipse((480, 470), 50, 70), C("#bff8ff"), 30, 0.55)
    # smaller crystals jutting from the body
    for i, (bb, tp, w) in enumerate([((420, 520), (360, 575), 36), ((575, 500), (640, 560), 32),
                                     ((560, 300), (610, 250), 30)]):
        B.shard(bb, tp, w, glow=0.5, seed=30 + i, ramp=ICE_DEEP)
    # face: dark frost sockets, glowing slit eyes, a jagged crack of a mouth with light inside
    NAVY = C("#061634")
    for eye in ([(410, 378), (464, 396), (456, 410), (418, 398)], [(494, 396), (548, 374), (542, 392), (500, 410)]):
        so = blur(B.poly([(x, y + (-10 if i < 2 else 8)) for i, (x, y) in enumerate(eye)]), 4 * SS)
        B.shade(np.clip(so * 1.8, 0, 1), NAVY, 0.9)
        em = B.poly(eye)
        B.fill(em, C("#9ef6ff"))
        B.fill(B.poly([along(eye[0], eye[2], 0.3), along(eye[1], eye[3], 0.3), along(eye[1], eye[3], 0.65),
                       along(eye[0], eye[2], 0.65)]), WHITE)
        B.glow(em, EYE_GLOW, 10, 0.8)
    grin = [(424, 466), (446, 478), (458, 470), (472, 486), (486, 474), (500, 488), (514, 476), (540, 468),
            (528, 492), (508, 504), (486, 500), (466, 506), (444, 496)]
    B.shade(blur(B.poly(grin), 5 * SS) * 1.5, NAVY, 0.9)
    gm = B.poly(grin)
    B.fill(gm, C("#0a2a5a"))
    B.fill(B.poly([(440, 484), (470, 494), (500, 494), (526, 482), (506, 498), (470, 500)]), C("#8ef0ff"))
    B.glow(gm, EYE_GLOW, 9, 0.6)
    B.sparkle((430, 300), 22, 1.0)
    B.sparkle((575, 520), 12, 0.8)

    # orbiting shards (floats)
    floats = []
    for i, (c, a, L, w) in enumerate([((265, 300), -60, 110, 40), ((735, 290), -120, 120, 42),
                                      ((770, 520), -150, 90, 34), ((240, 560), -20, 90, 32),
                                      ((640, 150), -100, 80, 28)]):
        F = Part(CV, (c[0] - 120, c[1] - 120, c[0] + 120, c[1] + 120), 400 + i)
        ra = math.radians(a)
        b = (c[0] - math.cos(ra) * L / 2, c[1] - math.sin(ra) * L / 2)
        t = (c[0] + math.cos(ra) * L / 2, c[1] + math.sin(ra) * L / 2)
        F.shard(b, t, w, glow=1.0, seed=410 + i, cast=0.0, shoulder=0.55)
        floats.append((c, F))

    # fx: heart and aura
    fx = fx_glow(CV, [lambda P: P.ellipse((485, 440), 90, 140)], GLOWC, 60, 0.5, box=(120, 50, 880, 850))
    fx_eyes = fx_glow(CV, [lambda P: P.poly([(412, 382), (462, 392), (458, 414), (420, 408)]),
                           lambda P: P.poly([(494, 392), (544, 378), (540, 402), (498, 414)])],
                      EYE_GLOW, 10, 1.0, box=(350, 320, 620, 480))

    add = rb.add
    add("core", B.image(), "", "root", (cx, cy), 10)
    add("crown", Cr.image(), "core", "hair", (cx, cy), 4)
    for tag, (A, Bp), piv1, piv2 in (("a", wa, (495, 565), (556, 760)), ("b", wb, (455, 545), (420, 750)),
                                      ("c", wc, (545, 535), (684, 650))):
        add(f"wisp_{tag}_1", A.image(), "core", "tail", piv1, 6)
        add(f"wisp_{tag}_2", Bp.image(), f"wisp_{tag}_1", "tail", piv2, 7)
    for i, (c, F) in enumerate(floats):
        add(f"shard_{i + 1}", F.image(), "core", "float", c, 12 if i in (0, 3) else 3)
    add("aura", fx.image(), "core", "fx", (cx, cy), 1, blend="add")
    add("eye_glow", fx_eyes.image(), "core", "fx", (480, 400), 20, blend="add")
    return rb, 512


# ------------------------------------------------------------------ yeti cub

SNOW = mk_ramp("#34447a", "#6478ae", "#a2b8da", "#d4e2f2", "#f2f7fc", "#ffffff")


def hand_mask(P, wrist, palm_c, palm_r, fingers, thumb, fw=16):
    m = P.tube([wrist, palm_c], [palm_r * 0.75, palm_r])
    for f in fingers:
        m = np.maximum(m, P.tube(f, [fw * 0.55, fw * 0.5, fw * 0.42]))
    if thumb:
        m = np.maximum(m, P.tube(thumb, [fw * 0.6, fw * 0.45]))
    return m


def build_yeti_cub():
    rid = "yeti_cub"
    CV = (1024, 1024)
    rb = rig.RigBuilder(rid, CV, feet=(520, 966), facing="left", kind="humanoid")
    FUR = FUR_W
    SKIN = SKIN_B
    FARF = mk_ramp("#161e40", "#2e3c68", "#52668e", "#7c90b4", "#a6b8d2", "#ccd8e8")
    down = lambda X, Y: 92
    NAVY = C("#0a1430")

    def vshift(P, y0, y1, top=0.05, bot=-0.14):
        return top + (bot - top) * lin(P, (0, y0), (0, y1))

    # ---------------- back (far) arm reaching forward
    BAU = Part(CV, (250, 330, 520, 640), 10)
    m = BAU.tube([(440, 420), (410, 470), (360, 540)], [56, 50, 44])
    m = BAU.tufts(m, spacing=5, length=22, width=13, flow=(0.2, 1), lean=0.7, seed=11)
    furpaint(BAU, m, FARF, down, r=40, lock=30, lockw=5, seed=11)
    BAL = Part(CV, (200, 440, 440, 720), 12)
    m = BAL.tube([(372, 525), (335, 580), (312, 615)], [42, 38, 34])
    m = BAL.tufts(m, spacing=5, length=20, width=12, flow=(0.3, 1), lean=0.7, seed=12)
    furpaint(BAL, m, FARF, lambda X, Y: 110, r=34, lock=26, lockw=5, seed=12)
    fist = hand_mask(BAL, (318, 615), (296, 650), 36, [[(282, 640), (262, 660), (270, 684)],
                                                         [(296, 652), (276, 676), (288, 694)]],
                     [(320, 640), (300, 670)], 20)
    BAL.paint(fist, SKIN, r=22, lift=-0.08, cast=0.3)
    BAL.haze(0.12)

    # ---------------- back leg
    BLU = Part(CV, (460, 580, 720, 960), 20)
    m = BLU.tube([(560, 700), (585, 780), (598, 860)], [66, 60, 52])
    m = BLU.tufts(m, spacing=5, length=20, width=13, flow=(0.2, 1), lean=0.7, seed=21)
    furpaint(BLU, m, FARF, down, r=44, lock=30, lockw=5, seed=21)
    BLL = Part(CV, (500, 750, 740, 1010), 22)
    m = BLL.tube([(596, 830), (604, 900), (608, 935)], [50, 46, 44])
    foot = BLL.shape([(560, 962), (575, 925), (630, 920), (668, 940), (672, 966), (610, 972)])
    m = BLL.tufts(m, spacing=5, length=18, width=12, flow=(0, 1), lean=0.7, seed=22)
    BLL.paint(foot, SKIN, r=16, lift=-0.1)
    furpaint(BLL, m, FARF, down, r=36, lock=24, lockw=5, seed=22)

    # ---------------- hips (root) and torso
    Hp = Part(CV, (330, 600, 720, 880), 30)
    m = Hp.shape([(400, 690), (520, 665), (640, 690), (655, 760), (600, 800), (450, 802), (395, 760)])
    m = Hp.tufts(m, spacing=5, length=26, width=15, flow=(0, 1), lean=0.7, seed=31, where=lambda X, Y: Y > 760)
    furpaint(Hp, m, FUR, down, r=70, lock=34, lockw=6, seed=31, ramp_shift=vshift(Hp, 660, 830, 0.0, -0.08))

    T = Part(CV, (270, 280, 790, 860), 40)
    tor = T.shape([(420, 380), (520, 355), (620, 390), (672, 480), (690, 590), (668, 700), (610, 770),
                   (520, 790), (420, 770), (365, 690), (350, 580), (366, 470)], n=10)
    tor = T.tufts(tor, spacing=4, length=30, width=17, flow=(0, 1), lean=0.65, seed=41,
                  where=lambda X, Y: Y > 470)
    furpaint(T, tor, FUR, lambda X, Y: 90 + (X - 520) * 0.12, r=150, lock=46, lockw=7, seed=41,
             ramp_shift=vshift(T, 380, 790))
    # a paler chest where the key light falls, occlusion under the arms and at the flanks
    T.light(tor * radial(T, (470, 520), 190), C("#fff4e4"), 0.12)
    T.shade(tor * smooth(0.55, 1.0, lin(T, (430, 500), (680, 640))), C("#26346a"), 0.35)

    # ---------------- front leg
    FLU = Part(CV, (330, 620, 600, 960), 50)
    m = FLU.tube([(465, 700), (452, 790), (440, 860)], [70, 62, 54])
    m = feather(FLU, m, (465, 680), (465, 740))
    m = FLU.tufts(m, spacing=5, length=22, width=14, flow=(0, 1), lean=0.7, seed=51, where=lambda X, Y: Y > 740)
    furpaint(FLU, m, FUR, down, r=48, lock=30, lockw=5, seed=51, line=0.6, ramp_shift=vshift(FLU, 700, 900))
    FLL = Part(CV, (290, 750, 560, 1010), 52)
    m = FLL.tube([(440, 830), (436, 900), (436, 935)], [52, 48, 46])
    foot = FLL.shape([(338, 960), (350, 922), (410, 915), (470, 930), (480, 964), (400, 974)])
    FLL.paint(foot, SKIN, r=18, lift=-0.04)
    for k in range(4):
        toe = FLL.ellipse((350 + k * 22, 958), 13, 11)
        FLL.paint(toe, SKIN, r=8, cast=0.2, castr=3)
    m = FLL.tufts(m, spacing=5, length=20, width=12, flow=(0, 1), lean=0.7, seed=53)
    furpaint(FLL, m, FUR, down, r=38, lock=24, lockw=5, seed=53, ramp_shift=-0.06)

    # ---------------- head
    Hd = Part(CV, (270, 120, 660, 470), 60)
    hm = Hd.shape([(360, 230), (400, 180), (470, 160), (545, 180), (590, 240), (600, 320), (570, 390),
                   (500, 420), (410, 410), (350, 360), (340, 290)], n=10)
    hm = Hd.tufts(hm, spacing=3, length=24, width=16, flow=(0.3, 0.4), lean=0.5, seed=61)
    furpaint(Hd, hm, FUR, lambda X, Y: -60 + (X - 470) * 0.3 if Y < 260 else 100 + (X - 470) * 0.2, r=90,
             lock=34, lockw=6, seed=61, ramp_shift=vshift(Hd, 180, 420, 0.06, -0.06))
    face = Hd.shape([(362, 272), (400, 252), (452, 250), (494, 262), (506, 312), (494, 356), (456, 384),
                     (404, 382), (366, 350), (354, 306)], n=8)
    Hd.paint(face, SKIN, r=44, spec=0.2, shin=16, cast=0.45, castr=10, line=0.7, lift=-0.06)
    # the muzzle: a paler, protruding snout
    muz = Hd.shape([(372, 330), (404, 312), (452, 314), (484, 332), (480, 368), (446, 386), (400, 384),
                    (370, 362)], n=8)
    Hd.paint(muz, SKIN, r=26, spec=0.25, shin=18, lift=0.12, cast=0.3, castr=6, line=0.4)
    # eyes deep under a heavy brow
    for c, rx, ry in (((400, 294), 10, 8), ((458, 296), 13, 10)):
        Hd.shade(blur(Hd.ellipse(c, rx + 10, ry + 8), 4 * SS), C("#0a1230"), 0.7)
        Hd.fill(Hd.ellipse(c, rx, ry), C("#0a0e1c"))
        Hd.fill(Hd.ellipse((c[0] - 1, c[1] + 1), rx * 0.8, ry * 0.8), C("#56c8f2"))
        Hd.fill(Hd.ellipse((c[0] - 1, c[1] + 1), rx * 0.45, ry * 0.5), C("#b8f4ff"))
        Hd.fill(Hd.ellipse((c[0] - 2, c[1] + 2), rx * 0.25, ry * 0.4), C("#0a1a38"))
        Hd.fill(Hd.ellipse((c[0] - 4, c[1] - 2), rx * 0.2, ry * 0.2), WHITE)
        Hd.glow(Hd.ellipse(c, rx * 0.7, ry * 0.7), EYE_GLOW, 5, 0.3)
    brow = Hd.stroke_mask([(366, 280), (402, 270), (432, 284), (462, 272), (506, 282)], 22, 16)
    Hd.paint(brow * face, SKIN, r=12, lift=0.04, line=0, cast=0.5, castr=5, castoff=(1, 6))
    nose = Hd.shape([(404, 318), (426, 310), (450, 316), (450, 332), (428, 338), (406, 332)], n=6)
    Hd.paint(nose, SKIN, r=9, lift=-0.28, spec=0.6, shin=30, cast=0.3, castr=4)
    for c in ((418, 330), (440, 330)):
        Hd.fill(Hd.ellipse(c, 5, 3), C("#0a0e1c"), 0.8)
    mouth = Hd.shape([(394, 356), (430, 352), (470, 350), (464, 366), (430, 374), (400, 368)], n=6)
    Hd.paint(mouth, MOUTH, r=6, lift=-0.3, line=0.8, cast=0)
    for (x, L) in ((404, 10), (458, 12)):
        f = Hd.poly([(x - 5, 368), (x + 5, 367), (x + 1, 367 - L)])
        Hd.paint(f, TEETH, r=3, cast=0.1, castr=2, lw=0.5)
    # shaggy fringe over the brow and cheek tufts
    fr = Hd.shape([(362, 246), (420, 222), (480, 222), (526, 246), (500, 258), (450, 248), (400, 258)])
    fr = Hd.tufts(fr, spacing=3, length=20, width=12, flow=(-0.1, 1), lean=0.85, seed=62,
                  where=lambda X, Y: Y > 240)
    furpaint(Hd, fr, FUR, lambda X, Y: 100, r=30, lock=20, lockw=4, seed=62, cast=0.5, castr=6, line=0.0,
             lift=0.08)
    ck = Hd.shape([(496, 300), (525, 290), (540, 340), (520, 395), (490, 380)])
    ck = Hd.tufts(ck, spacing=3, length=22, width=12, flow=(-0.4, 0.6), lean=0.6, seed=63)
    furpaint(Hd, ck, FUR, lambda X, Y: 120, r=20, lock=20, lockw=4, seed=63, cast=0.35, line=0.3)

    # ---------------- snowball (weapon) held high in the throwing hand
    Sb = Part(CV, (540, 30, 780, 260), 70)
    ball = Sb.ellipse((650, 140), 66, 64)
    lumps = fbm(Sb.H, Sb.W, 14 * SS, Sb.rng)
    ball = np.maximum(ball, Sb.ellipse((604, 110), 26, 22)) * 1.0
    Sb.paint(ball, SNOW, r=60, bump=blur(lumps, 3 * SS), bk=12, cmod=lumps - 0.5, cm=0.1, spec=0.2, shin=10, grain=0.05)
    for k in range(5):
        Sb.sparkle((620 + k * 13, 100 + (k * 23) % 60), 6 + k % 3 * 3, 0.7)

    # ---------------- front arm (throwing): upper and lower with the hand
    FAU = Part(CV, (500, 200, 800, 560), 80)
    m = FAU.tube([(585, 460), (620, 400), (670, 340), (700, 300)], [66, 62, 54, 48])
    m = feather(FAU, m, (560, 490), (600, 440))
    m = FAU.tufts(m, spacing=4, length=26, width=14, flow=(0.5, 1), lean=0.65, seed=81,
                  where=lambda X, Y: X > 600)
    furpaint(FAU, m, FUR, lambda X, Y: 60, r=50, lock=32, lockw=6, seed=81, line=0.6)
    FAL = Part(CV, (560, 90, 800, 420), 82)
    m = FAL.tube([(700, 320), (690, 260), (672, 218)], [48, 44, 40])
    m = FAL.tufts(m, spacing=4, length=24, width=13, flow=(0.7, 0.5), lean=0.6, seed=83)
    furpaint(FAL, m, FUR, lambda X, Y: 30, r=40, lock=28, lockw=5, seed=83)
    hand = hand_mask(FAL, (675, 225), (668, 196), 36, [[(690, 196), (716, 170), (712, 138)],
                                                         [(676, 188), (700, 156), (694, 124)]],
                     [(646, 205), (620, 190)], 22)
    FAL.paint(hand, SKIN, r=22, cast=0.35, castr=6)

    # ---------------- assemble
    add = rb.add
    add("hips", Hp.image(), "", "root", (520, 740), 8)
    add("torso", T.image(), "hips", "torso", (520, 720), 10)
    add("arm_back_upper", BAU.image(), "torso", "arm_back_upper", (440, 425), 3)
    add("arm_back_lower", BAL.image(), "arm_back_upper", "arm_back_lower", (368, 530), 2)
    add("leg_back_upper", BLU.image(), "hips", "leg_back_upper", (560, 710), 5)
    add("leg_back_lower", BLL.image(), "leg_back_upper", "leg_back_lower", (597, 845), 4)
    add("leg_front_upper", FLU.image(), "hips", "leg_front_upper", (465, 715), 13)
    add("leg_front_lower", FLL.image(), "leg_front_upper", "leg_front_lower", (440, 845), 12)
    add("head", Hd.image(), "torso", "head", (480, 390), 16)
    add("arm_front_upper", FAU.image(), "torso", "arm_front_upper", (590, 455), 19)
    add("arm_front_lower", FAL.image(), "arm_front_upper", "arm_front_lower", (698, 315), 18)
    add("snowball", Sb.image(), "arm_front_lower", "weapon", (668, 190), 17)
    return rb, 512


# ------------------------------------------------------------------ ice troll

def frost_patches(P, m, seed, amount=0.35):
    """Pale frost crusted onto skin: mottled light glaze plus tiny sparkling points."""
    n = fbm(P.H, P.W, 7 * SS, np.random.default_rng(seed), octaves=3)
    k = smooth(0.6, 0.78, n) * m * (0.4 + 0.6 * smooth(0.3, 0.7, fbm(P.H, P.W, 40 * SS, np.random.default_rng(seed + 1))))
    P.light(k, C("#dff4ff"), amount * 0.6)


def ice_plate(P, pts, apex, seed, glow=0.3, height=0.35):
    """Armour of ice: a low faceted slab split in two ridged halves, with a bright bevel."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    rng = random.Random(seed)
    jag = []
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        jag.append(p)
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        k = rng.uniform(1.05, 1.28) if rng.random() < 0.6 else rng.uniform(0.9, 1.0)
        jag.append((cx + (mx - cx) * k, cy + (my - cy) * k))
    pts = jag
    ap = (apex[0] * 0.5 + cx * 0.5 - 6, apex[1] * 0.5 + cy * 0.5 - 6)
    P.gem(pts, ap, height=height * 0.45, ramp=ICE_DEEP, glow=glow, seed=seed, core=0.3, cast=0.5, ridge=0.35)
    P.sparkle((cx - 12, cy - 14), 10, 0.8)


def build_ice_troll():
    rid = "ice_troll"
    CV = (1024, 1024)
    rb = rig.RigBuilder(rid, CV, feet=(515, 966), facing="left", kind="humanoid")
    SKIN = mk_ramp("#0c1430", "#1c2c56", "#324a7e", "#4e6c9c", "#7898bc", "#c0d8ec")
    FARS = mk_ramp("#0e1430", "#1e2a4c", "#34466e", "#50648e", "#7288aa", "#a8bcd2")
    HAIR = FUR_W

    # ---------------- far arm (left, hanging, big fist with an ice bracer)
    AU = Part(CV, (200, 300, 480, 620), 10)
    m = AU.tube([(400, 380), (360, 450), (315, 530)], [70, 60, 52])
    AU.paint(m, FARS, r=50, spec=0.15, shin=12)
    frost_patches(AU, m, 11, 0.2)
    AU.haze(0.1)
    AL = Part(CV, (160, 440, 420, 760), 12)
    m = AL.tube([(318, 520), (295, 590), (282, 650)], [54, 56, 50])
    AL.paint(m, FARS, r=44, spec=0.15, shin=12)
    fist = AL.shape([(230, 650), (262, 628), (318, 630), (338, 668), (322, 718), (270, 728), (234, 704)])
    AL.paint(fist, FARS, r=34, spec=0.2, shin=14, cast=0.4)
    for k in range(4):
        fm = AL.ellipse((246 + k * 21, 700 + k * 3), 13, 18, 10)
        AL.paint(fm, FARS, r=10, spec=0.2, cast=0.35, castr=4, lw=0.8)
    ice_plate(AL, [(250, 560), (300, 540), (345, 575), (338, 640), (285, 660), (248, 628)], (296, 596), 13)
    AL.haze(0.1)

    # ---------------- far leg
    LU = Part(CV, (330, 600, 560, 940), 20)
    m = LU.tube([(450, 700), (438, 780), (425, 850)], [72, 64, 56])
    LU.paint(m, FARS, r=50, spec=0.1)
    LL = Part(CV, (280, 740, 540, 1010), 22)
    m = LL.tube([(426, 830), (418, 900), (414, 930)], [56, 50, 48])
    foot = LL.shape([(318, 964), (332, 922), (400, 910), (460, 924), (470, 964), (390, 974)])
    m = np.maximum(m, foot)
    LL.paint(m, FARS, r=40, spec=0.1)
    for k in range(3):
        claws(LL, [(330 + k * 24, 958, 170)], ramp=HORN, size=12)

    # ---------------- hips and loincloth
    Hp = Part(CV, (360, 620, 700, 820), 30)
    m = Hp.shape([(390, 660), (520, 640), (660, 660), (670, 740), (600, 780), (430, 780), (380, 740)])
    Hp.paint(m, SKIN, r=60)
    Lc = Part(CV, (360, 640, 720, 920), 32)
    cloth = Lc.shape([(400, 680), (520, 670), (650, 680), (640, 760), (620, 860), (575, 830), (540, 880),
                      (505, 830), (470, 872), (440, 800), (410, 760)], n=8)
    cloth = Lc.tufts(cloth, spacing=5, length=20, width=12, flow=(0, 1), lean=0.8, seed=33,
                     where=lambda X, Y: Y > 780)
    furpaint(Lc, cloth, mk_ramp("#1a1a2c", "#2e3048", "#4c5070", "#747c9c", "#a4acc4", "#d8def0"),
             lambda X, Y: 90, r=40, lock=30, lockw=5, seed=33, cast=0.3)
    belt = Lc.shape([(392, 672), (520, 656), (660, 672), (662, 712), (520, 700), (394, 716)])
    Lc.paint(belt, LEATHER, r=12, spec=0.25, cast=0.35)
    ice_plate(Lc, [(495, 672), (530, 660), (560, 680), (548, 712), (510, 716)], (526, 690), 34, glow=0.5)

    # ---------------- torso: a hulking hunched mass with an ice breastplate
    T = Part(CV, (260, 160, 780, 780), 40)
    tor = T.shape([(360, 330), (430, 250), (540, 220), (640, 250), (700, 330), (710, 450), (680, 580),
                   (640, 680), (540, 720), (430, 710), (370, 640), (340, 520), (335, 410)], n=10)
    T.paint(tor, SKIN, r=140, spec=0.18, shin=10, ramp_shift=-0.02)
    # musculature: pecs, belly, a shadow under the chest
    T.shade(blur(T.stroke_mask([(360, 470), (450, 500), (560, 480)], 14, 10), 5 * SS) * tor, C("#101a38"), 0.45)
    T.light(tor * radial(T, (430, 360), 150), C("#fff0dc"), 0.12)
    T.shade(tor * smooth(0.5, 1.0, lin(T, (420, 420), (690, 640))), C("#0e1a40"), 0.4)
    frost_patches(T, tor, 41, 0.28)
    # breastplate of ice over the chest (two plates), strap across
    # muscle separations: pec line, a belly fold, the ribs
    for pts, w in (([(470, 350), (455, 420), (430, 470)], 10), ([(420, 600), (500, 620), (590, 600)], 12),
                   ([(600, 380), (640, 420), (660, 470)], 12)):
        mm = blur(T.stroke_mask(pts, w, w * 0.6), 4 * SS) * tor
        T.shade(mm, C("#0c1638"), 0.5)
    ice_plate(T, [(360, 380), (420, 340), (500, 350), (520, 420), (480, 500), (400, 510), (352, 460)],
              (440, 420), 42, glow=0.35)
    ice_plate(T, [(500, 440), (560, 420), (610, 450), (600, 530), (540, 560), (490, 520)], (548, 480), 43,
              glow=0.3)
    # white mane down the back of the neck
    mane = T.shape([(560, 225), (650, 240), (720, 320), (720, 420), (680, 380), (620, 300), (560, 270)])
    mane = T.tufts(mane, spacing=4, length=30, width=15, flow=(0.3, 1), lean=0.6, seed=44)
    furpaint(T, mane, HAIR, lambda X, Y: 70, r=40, lock=36, lockw=6, seed=44, cast=0.4)

    # ---------------- near leg
    NU = Part(CV, (470, 640, 740, 920), 50)
    m = NU.tube([(590, 700), (605, 780), (612, 850)], [80, 70, 60])
    m = feather(NU, m, (590, 660), (590, 730))
    NU.paint(m, SKIN, r=56, spec=0.12, line=0.6)
    frost_patches(NU, m, 51, 0.2)
    NL = Part(CV, (470, 740, 740, 1010), 52)
    m = NL.tube([(612, 830), (606, 900), (602, 930)], [62, 56, 54])
    foot = NL.shape([(500, 966), (515, 920), (590, 908), (660, 920), (672, 964), (580, 976)])
    m = np.maximum(m, foot)
    NL.paint(m, SKIN, r=44, spec=0.12)
    ice_plate(NL, [(560, 820), (612, 800), (662, 822), (660, 880), (610, 895), (562, 876)], (610, 848), 53)
    claws(NL, [(512 + k * 26, 958, 170) for k in range(3)], ramp=HORN, size=14)

    # ---------------- head: jutting forward, long nose, tusks, icicle beard, glowing eyes
    Hd = Part(CV, (230, 130, 680, 500), 60)
    hm = Hd.shape([(350, 250), (410, 205), (490, 200), (548, 238), (560, 310), (530, 380), (470, 410),
                   (400, 405), (350, 370), (330, 310)], n=10)
    Hd.paint(hm, SKIN, r=60, spec=0.2, shin=12)
    frost_patches(Hd, hm, 61, 0.25)
    # heavy brow
    brow = Hd.stroke_mask([(340, 280), (400, 262), (450, 270), (500, 262)], 30, 22)
    Hd.paint(brow, SKIN, r=16, lift=0.05, cast=0.55, castr=7, castoff=(1, 8), line=0.4)
    for c, rx in (((372, 298), 13), ((446, 300), 16)):
        glow_eye(Hd, c, rx, rx * 0.5, -8)
    # long drooping nose
    nose = Hd.shape([(384, 292), (408, 296), (410, 340), (392, 392), (340, 420), (296, 418), (286, 396),
                     (318, 372), (358, 336)], n=8)
    Hd.paint(nose, SKIN, r=24, spec=0.3, shin=14, cast=0.5, castr=8, lift=0.03)
    # mouth, tusks
    Hd.paint(Hd.stroke_mask([(350, 402), (410, 410), (470, 398)], 10, 8), MOUTH, r=4, lift=-0.3, cast=0)
    for base, tip in (((372, 408), (350, 360)), ((452, 402), (440, 350))):
        tm = Hd.stroke_mask([base, along(base, tip, 0.6), tip], 18, 2)
        Hd.paint(tm, HORN, r=8, spec=0.5, cast=0.35, castr=5)
    # white hair and icicle beard
    hair = Hd.shape([(420, 210), (500, 190), (570, 220), (600, 290), (570, 300), (520, 250), (450, 235)])
    hair = Hd.tufts(hair, spacing=3, length=40, width=16, flow=(0.8, 0.2), lean=0.7, seed=62)
    furpaint(Hd, hair, HAIR, lambda X, Y: 20, r=30, lock=30, lockw=5, seed=62, cast=0.4)
    for i, (bx, L) in enumerate([(360, 50), (385, 70), (410, 86), (435, 72), (460, 54), (485, 40)]):
        Hd.shard((bx, 408), (bx - 6, 408 + L), 20, glow=0.4, seed=64 + i, shoulder=0.35, spark=False)
    # ear
    ear = Hd.shape([(540, 290), (600, 262), (590, 300), (556, 330)])
    Hd.paint(ear, SKIN, r=12, cast=0.4)

    # ---------------- the crystal club, dragged along the ground
    Cl = Part(CV, (40, 560, 620, 1010), 70)
    handle = Cl.stroke_mask([(540, 660), (450, 730), (330, 810), (250, 858)], 30, 40)
    Cl.paint(handle, WOOD, r=12, spec=0.2, cast=0.3)
    for k in range(4):
        a = along((505, 686), (430, 742), k / 3)
        Cl.paint(Cl.ellipse(a, 22, 9, 55), LEATHER, r=6, cast=0.3, castr=3)
    cx, cy = 225, 865
    shards = [(-150, 150, 66), (-110, 140, 62), (-190, 120, 54), (-70, 110, 50), (160, 100, 48),
              (-130, 95, 56), (-165, 80, 50), (190, 70, 40)]
    for i, (a, L, w) in enumerate(shards):
        ra = math.radians(a)
        Cl.shard((cx + math.cos(ra) * 20, cy + math.sin(ra) * 20), (cx + math.cos(ra) * L, cy + math.sin(ra) * L),
                 w, glow=0.9, seed=71 + i, ramp=ICE_DEEP)
    Cl.gem([(170, 840), (222, 808), (282, 830), (292, 890), (240, 930), (180, 912)], (218, 856), height=0.5,
           ramp=ICE, glow=1.0, seed=79)

    # ---------------- near arm holding the club
    NAU = Part(CV, (500, 150, 790, 640), 80)
    m = NAU.tube([(630, 360), (640, 420), (625, 490), (600, 555)], [82, 80, 66, 56])
    m = feather(NAU, m, (650, 300), (640, 380))
    NAU.paint(m, SKIN, r=60, spec=0.15, line=0.6)
    frost_patches(NAU, m, 81, 0.22)
    ice_plate(NAU, [(575, 300), (640, 260), (715, 290), (730, 380), (690, 430), (620, 420), (580, 370)],
              (655, 345), 82, glow=0.35, height=0.5)
    for i, (b, t, w) in enumerate([((640, 290), (660, 220), 34), ((680, 300), (730, 240), 30),
                                   ((610, 300), (600, 245), 26)]):
        NAU.shard(b, t, w, glow=0.6, seed=85 + i, ramp=ICE_DEEP)
    NAL = Part(CV, (420, 480, 700, 740), 83)
    m = NAL.tube([(600, 540), (570, 600), (530, 650)], [58, 54, 48])
    NAL.paint(m, SKIN, r=44, spec=0.15)
    hand = NAL.shape([(470, 640), (505, 610), (556, 620), (570, 670), (540, 712), (486, 708), (462, 680)])
    NAL.paint(hand, SKIN, r=30, spec=0.2, cast=0.45)
    for k in range(4):
        fm = NAL.ellipse((480 + k * 20, 690 - k * 4), 13, 20, 10)
        NAL.paint(fm, SKIN, r=10, spec=0.2, cast=0.35, castr=4, lw=0.8)
    ice_plate(NAL, [(560, 560), (610, 548), (636, 590), (610, 640), (565, 640), (548, 600)], (592, 594), 84)

    fx_eyes = fx_glow(CV, [lambda P: P.ellipse((372, 298), 12, 6, -8), lambda P: P.ellipse((446, 300), 15, 7, -8)],
                      EYE_GLOW, 10, 1.0, box=(300, 240, 520, 360))
    fx_club = fx_glow(CV, [lambda P: P.ellipse((200, 830), 110, 90)], GLOWC, 40, 0.45, box=(0, 560, 520, 1024))

    add = rb.add
    add("hips", Hp.image(), "", "root", (520, 720), 8)
    add("torso", T.image(), "hips", "torso", (520, 700), 10)
    add("loincloth", Lc.image(), "hips", "cape", (520, 690), 12)
    add("arm_back_upper", AU.image(), "torso", "arm_back_upper", (400, 390), 3)
    add("arm_back_lower", AL.image(), "arm_back_upper", "arm_back_lower", (318, 525), 2)
    add("leg_back_upper", LU.image(), "hips", "leg_back_upper", (450, 710), 5)
    add("leg_back_lower", LL.image(), "leg_back_upper", "leg_back_lower", (426, 840), 4)
    add("leg_front_upper", NU.image(), "hips", "leg_front_upper", (590, 710), 14)
    add("leg_front_lower", NL.image(), "leg_front_upper", "leg_front_lower", (612, 840), 13)
    add("head", Hd.image(), "torso", "head", (470, 360), 16)
    add("arm_front_upper", NAU.image(), "torso", "arm_front_upper", (635, 370), 20)
    add("arm_front_lower", NAL.image(), "arm_front_upper", "arm_front_lower", (600, 548), 19)
    add("club", Cl.image(), "arm_front_lower", "weapon", (515, 675), 18)
    add("club_glow", fx_club.image(), "club", "fx", (220, 850), 17, blend="add")
    add("eye_glow", fx_eyes.image(), "head", "fx", (410, 300), 22, blend="add")
    return rb, 512


# ------------------------------------------------------------------ frostbreath (boss)

def scale_map(P, size, ang=0.0, seed=0):
    """-1..1 map of overlapping scales: staggered rows, each scale lit along its top and creased along its
    rounded lower edge, with a little per-scale value variation. ang turns the rows (degrees)."""
    X, Y = P.grid()
    r = math.radians(ang)
    u = X * math.cos(r) + Y * math.sin(r)
    v = -X * math.sin(r) + Y * math.cos(r)
    sy = size * 0.6
    row = np.floor(v / sy)
    uu = u / size + 0.5 * (row % 2)
    col = np.floor(uu)
    fu = uu - col - 0.5
    fv = v / sy - row
    edge = fv + (2 * fu) ** 2 * 0.45
    crease = smooth(0.78, 1.05, edge)
    h = np.sin(row * 12.9898 + col * 78.233 + seed * 3.17) * 43758.5453
    var = (h - np.floor(h) - 0.5) * 0.5
    out = (0.35 - 0.6 * fv + var) * (1 - crease) - crease * 0.6
    return np.clip(out, -1, 1).astype(F32)


def scalepaint(P, m, ramp, r, size, ang=0.0, seed=0, cm=0.07, bk=0.45, frost=0.2, **kw):
    """Scaled hide: lit as one rounded mass, with a scale relief and rime of frost."""
    sm = scale_map(P, size, ang, seed)
    sm = sm * (0.55 + 0.45 * fbm(P.H, P.W, size * 3 * SS, np.random.default_rng(seed + 3), 2))
    if 'cmod' not in kw:
        kw['cmod'] = sm + (fbm(P.H, P.W, size * 5 * SS, np.random.default_rng(seed + 5), 2) - 0.5) * 1.2
    kw.setdefault("spec", 0.22)
    kw.setdefault("shin", 16)
    P.paint(m, ramp, r=r, bump=sm, bk=bk, cm=cm, grain=0.03, **kw)
    if frost:
        frost_patches(P, m, seed + 7, frost)


def scallop(a, b, toward, sag, n=8):
    """Points from a (excluded) to b bowing toward `toward` (the loose edge of a wing membrane)."""
    pts = []
    for i in range(1, n + 1):
        t = i / n
        x, y = along(a, b, t)
        s = math.sin(math.pi * t) * sag
        pts.append((x + (toward[0] - x) * s, y + (toward[1] - y) * s))
    return pts


def side_points(pts, radii, side, k=1.0, n=10):
    """Points on one side (+1 right of travel, -1 left) of a tube path, k * radius off the centre line,
    with the outward unit normal: [(x, y, nx, ny, r)]."""
    path = catmull(pts, n=n)
    rs = np.interp(np.linspace(0, 1, len(path)), np.linspace(0, 1, len(radii)), radii)
    out = []
    for i, (x, y) in enumerate(path):
        a, b = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        dn = math.hypot(dx, dy) + 1e-6
        nx, ny = -dy / dn * side, dx / dn * side
        out.append((x + nx * rs[i] * k, y + ny * rs[i] * k, nx, ny, float(rs[i])))
    return out


def build_frostbreath():
    rid = "frostbreath"
    CV = (1792, 1344)
    OFF = 64  # drawn on 1792 x 1344, rigged on 1920 x 1344 so swinging wings, tail and breath stay on canvas
    rb = rig.RigBuilder(rid, (CV[0] + 2 * OFF, CV[1]), feet=(950 + OFF, 1262), facing="left", kind="dragon")
    SC = SCALE
    FARS = mk_ramp("#0e1a3e", "#1c3260", "#345486", "#567cac", "#80a4c8", "#b0cae2")
    BEL = BELLY
    MEMF = mk_ramp("#0a1838", "#122c58", "#204c84", "#386ea8", "#5e96c8", "#9cc8e8")
    CLAW = mk_ramp("#3a4a6a", "#6a7c9c", "#9eb0c8", "#cad8e8", "#eef6fc", "#ffffff")
    MOUTH_C = mk_ramp("#0a0a22", "#18164a", "#2c2a6e", "#46509a", "#6a88c6", "#a8d8f4")
    GROUND = 1262

    def spines(P, pts, radii, side, picks, seed, lean=-35, scale=1.0, glow=0.7, kofs=0.72):
        """Crystal spines standing out of one side of a tube path, raked back by `lean` degrees."""
        sp = side_points(pts, radii, side, kofs, n=12)
        for i, (j, L, w) in enumerate(picks):
            x, y, nx, ny, r = sp[min(len(sp) - 1, int(j * (len(sp) - 1)))]
            a = math.degrees(math.atan2(ny, nx)) + lean
            shard_at(P, (x, y), a, L * scale, w * scale, glow=glow, seed=seed + i, ramp=ICE_DEEP, cast=0.3)

    def belly_plates(P, m, pts, radii, side, seed, ramp=BEL, step=30, k0=0.15, wk=0.75):
        """The pale ridged throat / belly band along one side of a tube."""
        sp = side_points(pts, radii, side, k0, n=12)
        cen = [(x, y) for x, y, *_ in sp]
        rr = [r * wk for *_, r in sp]
        band = P.tube(cen[::2], rr[::2], n=4) * m
        band = blur(band, 2 * SS) * m
        P.paint(band, ramp, r=max(radii) * 0.8, hm=m, line=0.0, cast=0.0, spec=0.25, shin=14,
                ramp_shift=-0.02, grain=0.03)
        acc = 0.0
        prev = None
        for x, y, nx, ny, r in side_points(pts, radii, side, k0, n=30):
            if prev is not None:
                acc += math.hypot(x - prev[0], y - prev[1])
            prev = (x, y)
            if acc >= step:
                acc = 0.0
                a = (x - nx * r * 0.55 + ny * 4, y - ny * r * 0.55 - nx * 4)
                b = (x + nx * r * 0.9, y + ny * r * 0.9)
                c = along(a, b, 0.5)
                c = (c[0] - ny * 6 * side, c[1] + nx * 6 * side)
                ln = P.stroke_mask([a, c, b], 4.5, 3.0) * band
                P.shade(blur(ln, 1.0 * SS), C("#3a4a7a"), 0.55)
                hl = P.stroke_mask([(a[0] - ny * 5, a[1] + nx * 5), (c[0] - ny * 5, c[1] + nx * 5),
                                    (b[0] - ny * 5, b[1] + nx * 5)], 3, 2) * band
                P.light(blur(hl, 1.2 * SS), C("#f4fbff"), 0.25)

    # ---------------- wings
    def wing(seed, box, root, elbow, wrist, tips, trail, mramp, bramp, far):
        P = Part(CV, box, seed)
        out = [root, elbow, wrist, tips[0]]
        for a, b in zip(tips, tips[1:]):
            out += scallop(a, b, wrist, 0.2)
        tr = [tips[-1]] + trail + [root]
        for a, b in zip(tr, tr[1:]):
            out += scallop(a, b, elbow, 0.1)
        mem = P.poly(out, aa=0.8)
        bones = P.tube([root, elbow, wrist], [28, 20, 16])
        for t in tips:
            bones = np.maximum(bones, P.stroke_mask([wrist, along(wrist, t, 0.5), t], 22, 6))
        near_bone = blur(bones, 22 * SS)
        rng = random.Random(seed)
        X, Y = P.grid()
        cx = sum(p[0] for p in out) / len(out)
        cy = sum(p[1] for p in out) / len(out)
        glowin = smooth(0.0, 1.0, lin(P, wrist, (cx + (cx - wrist[0]) * 0.6, cy + (cy - wrist[1]) * 0.6)))
        P.paint(mem, mramp, r=46, hm=np.clip(mem - near_bone * 0.8, 0, 1), cmod=fbm(P.H, P.W, 40 * SS,
                np.random.default_rng(seed)) - 0.5, cm=0.18, ramp_shift=0.1 * glowin - 0.04, rim=0.7, spec=0.15,
                shin=20, cast=0.0, line=0.9, lw=1.2)
        # light through the thin membrane, brighter between the bones
        P.light(mem * glowin * (1 - np.clip(near_bone * 2, 0, 1)), C("#7fd4ff"), 0.22)
        # veins branching from the fingers
        vm = np.zeros_like(mem)
        for t in tips:
            for k in range(4):
                s = rng.uniform(0.25, 0.85)
                a = along(wrist, t, s)
                dx, dy = t[0] - wrist[0], t[1] - wrist[1]
                dn = math.hypot(dx, dy)
                side = rng.choice((-1, 1))
                L = rng.uniform(50, 110)
                px, py = -dy / dn * side, dx / dn * side
                b = (a[0] + px * L + dx / dn * L * 0.35, a[1] + py * L + dy / dn * L * 0.35)
                c = (a[0] + px * L * 0.5 + dx / dn * L * 0.05, a[1] + py * L * 0.5 + dy / dn * L * 0.05)
                vm = np.maximum(vm, P.stroke_mask([a, c, b], 4, 1))
        vm = vm * mem
        P.shade(blur(vm, 0.8 * SS), C("#1a3060"), 0.5)
        P.light(blur(vm, 0.6 * SS) * glowin, C("#bdf0ff"), 0.18)
        # rime along the free edge
        e = blur(mem, 3 * SS)
        band = mem * np.clip((0.9 - e) / 0.4, 0, 1) * (1 - np.clip(bones * 3, 0, 1))
        P.light(band, C("#e6f8ff"), 0.45)
        # bones
        arm = P.tube([root, elbow, wrist], [28, 20, 16])
        scalepaint(P, arm, bramp, 24, 12, 60, seed + 1, cm=0.06, bk=0.3, frost=0.15, spec=0.35, cast=0.4, castr=10)
        for i, t in enumerate(tips):
            f = P.stroke_mask([wrist, along(wrist, t, 0.45), t], 20, 6)
            P.paint(f, bramp, r=10, spec=0.4, shin=20, cast=0.35, castr=8, lw=0.9)
            shard_at(P, t, math.degrees(math.atan2(t[1] - wrist[1], t[0] - wrist[0])), 34 + 6 * (i % 2), 13,
                     glow=0.6, seed=seed + 20 + i, ramp=ICE_DEEP, spark=False)
        for c, rr in ((elbow, 24), (wrist, 22)):
            P.paint(P.ellipse(c, rr, rr * 0.86), bramp, r=16, spec=0.45, shin=20, cast=0.4, castr=8)
        # the thumb: a crystal claw on the wrist, pointing forward
        ux, uy = wrist[0] - elbow[0], wrist[1] - elbow[1]
        a = math.degrees(math.atan2(uy, ux)) - 70
        shard_at(P, wrist, a, 90, 30, glow=0.9, seed=seed + 40, ramp=ICE_DEEP)
        if far:
            P.haze(0.22, C("#5a74a8"))
        return P

    WB = wing(10, (600, 0, 1300, 800), (960, 690), (890, 500), (790, 230),
              [(870, 70), (1000, 50), (1130, 130), (1200, 330)], [(1110, 520), (1040, 640)], MEMF, FARS, True)
    WF = wing(20, (840, 40, 1760, 880), (930, 720), (1090, 530), (1040, 220),
              [(1250, 150), (1510, 230), (1640, 440), (1570, 660)], [(1390, 730), (1200, 770)], MEMB, SC, False)

    # ---------------- legs: (hip/shoulder, joint, joint, foot) in two parts each
    def foot_part(P, ankle, foot, ramp, seed, r_ank):
        toes = []
        fx, fy = foot
        m = P.tube([ankle, along(ankle, foot, 0.6), (fx + 16, fy - 26)], [r_ank, r_ank * 0.85, r_ank * 0.8])
        pad = P.shape([(fx - 70, fy - 6), (fx - 52, fy - 40), (fx + 6, fy - 52), (fx + 44, fy - 34), (fx + 42, fy - 2),
                       (fx - 20, fy + 4)])
        m = np.maximum(m, pad)
        scalepaint(P, m, ramp, r_ank * 0.9, 14, 90, seed, cm=0.08, bk=0.5, frost=0.25, lw=1.0)
        for k in range(3):
            tc = (fx - 58 + k * 26, fy - 12 + k * 2)
            tm = P.ellipse(tc, 20, 15, -10)
            scalepaint(P, tm, ramp, 10, 8, 0, seed + k, cm=0.05, bk=0.2, frost=0.2, cast=0.3, castr=4, lw=0.8)
            toes.append(tc)
        claws(P, [(x - 16, y + 4, 168 - 8 * i) for i, (x, y) in enumerate(toes)], ramp=CLAW, size=26)
        claws(P, [(fx + 34, fy - 6, 10)], ramp=CLAW, size=16)

    def leg(seed, top, knee, ankle, foot, radii, mass, ramp, far, near_feather=True, spikes=()):
        x0 = min(top[0], knee[0], ankle[0]) - 190
        x1 = max(top[0], knee[0], ankle[0]) + 190
        U = Part(CV, (x0, top[1] - mass[2] - 40, x1, knee[1] + radii[1] + 50), seed)
        m = U.tube([(top[0], top[1] - 30), top, knee], [radii[0], radii[0], radii[1]])
        m = np.maximum(m, U.ellipse(*mass))
        if near_feather and not far:
            m = feather(U, m, (top[0], top[1] - mass[2] * 0.75), (top[0], top[1] - mass[2] * 0.15))
        scalepaint(U, m, ramp, radii[0] * 1.1, 22, 20, seed, line=0.7 if far else 0.4)
        for i, (b, a, L, w) in enumerate(spikes):
            shard_at(U, b, a, L, w, glow=0.5, seed=seed + 50 + i, ramp=ICE_DEEP)
        if far:
            U.haze(0.2, C("#4e68a0"))
        Lw = Part(CV, (min(knee[0], ankle[0], foot[0]) - 140, knee[1] - 100, max(knee[0], ankle[0], foot[0]) + 120,
                       foot[1] + 30), seed + 1)
        m2 = Lw.tube([knee, along(knee, ankle, 0.5), ankle], [radii[1] * 0.92, radii[2] * 1.05, radii[2]])
        scalepaint(Lw, m2, ramp, radii[2], 16, 80, seed + 1, frost=0.25)
        foot_part(Lw, ankle, foot, ramp, seed + 2, radii[2] * 0.95)
        if far:
            Lw.haze(0.2, C("#4e68a0"))
        return U, Lw

    far_hind = leg(30, (1300, 880), (1262, 1045), (1330, 1160), (1296, GROUND - 8), [92, 66, 46],
                   ((1300, 920), 120, 130, 12), FARS, True)
    far_fore = leg(40, (880, 880), (892, 1040), (862, 1190), (830, GROUND - 8), [62, 52, 42],
                   ((880, 900), 72, 96, 0), FARS, True)

    # ---------------- tail chain, sweeping back along the ground and curling up to a crystal tip
    tail_pts1 = [(1250, 880), (1345, 935), (1450, 985)]
    tail_r1 = [130, 116, 92]
    T1 = Part(CV, (1110, 680, 1620, 1180), 50)
    m = T1.tube(tail_pts1, tail_r1)
    m = feather(T1, m, (1200, 840), (1290, 905))
    scalepaint(T1, m, SC, 90, 24, 35, 50, line=0.5)
    belly_plates(T1, m, tail_pts1, tail_r1, 1, 51, step=34, k0=0.55, wk=0.5)
    spines(T1, tail_pts1, tail_r1, -1, [(0.35, 96, 34), (0.65, 84, 30), (0.92, 70, 26)], 52, lean=25)
    tail_pts2 = [(1420, 970), (1530, 1010), (1640, 1010)]
    tail_r2 = [94, 76, 60]
    T2 = Part(CV, (1300, 820, 1780, 1180), 60)
    m = T2.tube(tail_pts2, tail_r2)
    scalepaint(T2, m, SC, 70, 20, 25, 60, line=0.6)
    belly_plates(T2, m, tail_pts2, tail_r2, 1, 61, step=28, k0=0.55, wk=0.5)
    spines(T2, tail_pts2, tail_r2, -1, [(0.3, 66, 26), (0.62, 58, 23), (0.92, 50, 20)], 62, lean=25)
    tail_pts3 = [(1610, 1012), (1680, 985), (1716, 920), (1712, 850)]
    tail_r3 = [62, 50, 34, 18]
    T3 = Part(CV, (1490, 640, 1792, 1120), 70)
    m = T3.tube(tail_pts3, tail_r3)
    scalepaint(T3, m, SC, 46, 16, -40, 70, line=0.7)
    spines(T3, tail_pts3, tail_r3, -1, [(0.2, 44, 18), (0.5, 38, 16)], 72, lean=20)
    for i, (a, L, w) in enumerate([(-92, 120, 40), (-118, 86, 30), (-66, 80, 28), (-140, 52, 20)]):
        shard_at(T3, (1712, 865), a, L, w, glow=1.0, seed=75 + i, ramp=ICE_DEEP)

    # ---------------- body: deep chest held high, haunch, pale belly
    B = Part(CV, (560, 560, 1460, 1130), 80)
    body = B.shape([(640, 860), (670, 760), (760, 690), (880, 660), (1020, 690), (1160, 730), (1290, 790),
                    (1360, 880), (1340, 990), (1250, 1050), (1110, 1060), (990, 1040), (880, 1060), (760, 1045),
                    (670, 980)], n=10)
    scalepaint(B, body, SC, 150, 30, 15, 80, ramp_shift=0.04 - 0.1 * lin(B, (0, 680), (0, 1060)))
    belly = B.shape([(650, 880), (720, 900), (850, 960), (1000, 990), (1150, 1010), (1260, 1030), (1220, 1070),
                     (1080, 1080), (920, 1080), (780, 1060), (680, 1000)], n=10)
    belly = blur(belly, 6 * SS) * body
    B.paint(belly, BEL, r=110, hm=body, line=0.0, cast=0.0, spec=0.2, ramp_shift=-0.05, grain=0.03)
    for i in range(9):
        x = 700 + i * 62
        a = (x, 880 + i * 14)
        b = (x + 24, 1080)
        ln = B.stroke_mask([a, along(a, b, 0.5), b], 5, 3) * belly
        B.shade(blur(ln, 1.2 * SS), C("#40507e"), 0.5)
    # haunch muscle and shadow under the wing
    B.light(body * radial(B, (1150, 860), 200) ** 1.5, C("#e8f4ff"), 0.12)
    B.shade(body * blur(B.ellipse((960, 730), 220, 60, 8), 30 * SS), C("#16224c"), 0.35)
    B.shade(body * smooth(0.55, 1.0, lin(B, (1000, 800), (1000, 1070))), C("#18265a"), 0.3)
    spines(B, [(880, 690), (1060, 700), (1200, 750), (1300, 820)], [40, 40, 40, 40], -1,
           [(0.6, 70, 30), (0.78, 82, 32), (0.95, 72, 28)], 85, lean=35, kofs=0.0)

    near_hind = leg(90, (1170, 900), (1100, 1070), (1215, 1168), (1170, GROUND), [112, 80, 54],
                    ((1175, 920), 150, 160, 15), SC, False,
                    spikes=[((1250, 860), -40, 60, 24), ((1270, 900), -20, 48, 20)])
    near_fore = leg(100, (770, 880), (745, 1040), (712, 1195), (672, GROUND), [72, 60, 48],
                    ((775, 905), 80, 112, -6), SC, False,
                    spikes=[((830, 860), -60, 52, 22)])

    # ---------------- neck: a long arc up and forward, pale ridged throat, crystal spines on the crest
    neck_pts = [(850, 810), (750, 700), (665, 600), (612, 515), (585, 440)]
    neck_r = [138, 120, 102, 88, 80]
    N = Part(CV, (380, 240, 1050, 1000), 110)
    nm = N.tube(neck_pts, neck_r)
    nm = feather(N, nm, (930, 900), (830, 790))
    scalepaint(N, nm, SC, 90, 20, -50, 110, ramp_shift=0.03)
    belly_plates(N, nm, neck_pts, neck_r, 1, 111, step=30, k0=-0.55, wk=0.5)
    N.shade(nm * blur(N.ellipse((560, 460), 70, 50), 20 * SS), C("#16224c"), 0.4)
    spines(N, neck_pts, neck_r, 1, [(0.12, 92, 34), (0.3, 110, 38), (0.48, 104, 36), (0.65, 92, 32),
                                    (0.82, 74, 28)], 115, lean=12, kofs=0.62)

    # ---------------- head: wedge skull, swept crystal horns, glaring eye, open jaws
    H = Part(CV, (180, 150, 820, 600), 130)
    # far horn, half hidden behind the crown
    hm = H.tube([(548, 372), (590, 318), (636, 276), (686, 250)], [22, 16, 9, 2])
    H.paint(hm, ICE_DEEP, r=12, spec=0.8, shin=40, cast=0.2, lw=0.9, lift=-0.15)
    frill = H.poly([(590, 440)] + scallop((590, 440), (720, 410), (640, 470), 0.0, 2)
                   + scallop((720, 410), (700, 470), (640, 470), 0.25, 6)
                   + scallop((700, 470), (740, 520), (640, 470), 0.0, 2)
                   + scallop((740, 520), (610, 530), (640, 470), 0.25, 6))
    H.paint(frill, MEMB, r=20, spec=0.2, cast=0.2, line=0.9)
    for a, b in (((600, 460), (720, 412)), ((605, 490), (738, 518))):
        H.paint(H.stroke_mask([a, along(a, b, 0.5), b], 12, 3), SC, r=6, spec=0.4, cast=0.3)
    skull = H.shape([(242, 470), (238, 446), (262, 426), (320, 408), (392, 392), (452, 366), (520, 344),
                     (590, 352), (636, 395), (648, 448), (624, 498), (560, 512), (480, 496), (400, 486),
                     (320, 482)], n=10)
    scalepaint(H, skull, SC, 50, 15, -14, 132, ramp_shift=0.03)
    # snout ridge highlight and cheek shadow
    H.light(skull * blur(H.stroke_mask([(270, 432), (360, 404), (450, 378)], 30, 20), 8 * SS), C("#fff4e0"), 0.18)
    H.shade(skull * blur(H.ellipse((560, 470), 60, 34), 14 * SS), C("#14204a"), 0.35)
    # upper lip line and nostril
    H.paint(H.stroke_mask([(246, 470), (320, 480), (400, 484), (480, 492), (540, 500)], 7, 4) * skull,
            mk_ramp("#0a1028", "#16204a", "#24346a", "#38508a", "#5070a8", "#7898c8"), r=4, line=0, cast=0)
    nos = H.ellipse((268, 438), 14, 7, -20)
    H.paint(nos, mk_ramp("#04060e", "#0a1024", "#162040", "#24345e", "#3a4c7a", "#6a80a8"), r=5, line=0, cast=0)
    H.light(H.ellipse((272, 432), 10, 3, -20), C("#cfe8ff"), 0.4)
    # upper teeth
    for i, (x, L) in enumerate([(258, 30), (292, 22), (322, 26), (356, 20), (390, 22), (428, 18), (466, 16)]):
        y = 470 + (x - 250) * 0.11
        f = H.poly([(x - 7, y - 3), (x + 7, y - 3), (x + 1, y + L)])
        H.paint(f, TEETH, r=3, spec=0.6, cast=0.2, castr=3, lw=0.6)
    # brow ridge with crystal crest, and the eye beneath it
    brow = H.stroke_mask([(400, 404), (450, 382), (510, 374), (560, 384)], 26, 14)
    scalepaint(H, brow, SC, 12, 10, -10, 133, lift=0.04, cast=0.55, castr=8, castoff=(2, 9), line=0.4)
    glow_eye(H, (470, 410), 26, 10, -12)
    H.sparkle((460, 405), 13, 0.8)
    for i, (b, a, L, w) in enumerate([((452, 384), -150, 40, 16), ((496, 374), -160, 56, 20),
                                      ((540, 378), -168, 64, 22)]):
        shard_at(H, b, a + 150, L, w, glow=0.6, seed=140 + i, ramp=ICE_DEEP)
    # near horn: a long crystal horn sweeping back from the crown
    hp = [(560, 400), (614, 356), (676, 318), (742, 300)]
    hm = H.tube(hp, [28, 22, 13, 3])
    H.paint(hm, ICE_DEEP, r=14, spec=0.9, shin=40, cast=0.4, castr=10, lw=0.9)
    H.light(hm * blur(H.tube(hp, [10, 8, 5, 1]), 3 * SS), C("#c8f6ff"), 0.5)
    for k in range(5):
        p = catmull(hp, n=6)[3 + k * 3]
        H.shade(H.ellipse(p, 3, 18 - k * 2, 40) * hm, C("#1a3a74"), 0.4)
    H.glow(hm, GLOWC, 10, 0.3)
    # cheek and chin crystal spikes
    for i, (b, a, L, w) in enumerate([((628, 470), 20, 70, 24), ((612, 500), 45, 54, 20)]):
        shard_at(H, b, a, L, w, glow=0.6, seed=150 + i, ramp=ICE_DEEP)

    Mo = Part(CV, (220, 440, 640, 640), 160)
    mouth = Mo.shape([(246, 468), (400, 482), (548, 498), (580, 530), (520, 560), (400, 572), (300, 574),
                      (262, 540)], n=8)
    Mo.paint(mouth, MOUTH_C, r=24, lift=-0.2, line=0, cast=0)
    Mo.paint(Mo.shape([(300, 556), (380, 540), (470, 534), (520, 548), (440, 566), (330, 570)]) * mouth,
             MOUTH, r=12, lift=0.05, spec=0.35, line=0.3, cast=0)
    Mo.glow(radial(Mo, (420, 520), 120) * mouth, GLOWC, 18, 0.9, core=0.5)

    J = Part(CV, (230, 450, 680, 680), 170)
    jaw = J.shape([(600, 500), (586, 552), (520, 586), (420, 604), (330, 604), (282, 588), (278, 566),
                   (330, 556), (420, 544), (500, 528), (560, 498)], n=8)
    for i, (x, L) in enumerate([(296, 26), (336, 18), (372, 22), (410, 16), (448, 18), (486, 14)]):
        y = 562 - (x - 290) * 0.1
        f = J.poly([(x - 7, y + 4), (x + 7, y + 4), (x + 1, y - L)])
        J.paint(f, TEETH, r=3, spec=0.6, cast=0.15, castr=3, lw=0.6)
    scalepaint(J, jaw, SC, 24, 12, -8, 171, ramp_shift=-0.03)
    J.paint(blur(J.shape([(290, 584), (400, 590), (520, 572), (580, 548), (560, 580), (440, 604),
                          (330, 604)]), 3 * SS) * jaw, BEL, r=16, hm=jaw, line=0, cast=0, ramp_shift=-0.06)
    for i, (b, a, L, w) in enumerate([((420, 600), 75, 46, 18), ((470, 594), 65, 56, 20),
                                      ((520, 582), 55, 48, 18)]):
        shard_at(J, b, a, L, w, glow=0.5, seed=175 + i, ramp=ICE_DEEP)

    # ---------------- breath: an additive glowing cone and a translucent mist with splinters of ice
    M = (262, 515)
    bpts = [M, (236, 640), (214, 800), (200, 960), (196, 1060)]
    brad = [14, 46, 88, 120, 132]
    BR = Part(CV, (0, 430, 470, 1300), 180)
    cone = blur(BR.tube(bpts, brad, n=10), 10 * SS)
    t = lin(BR, M, bpts[-1])
    fade = (1 - smooth(0.55, 1.0, t))
    core = blur(BR.tube(bpts[:4], [8, 20, 34, 30], n=10), 6 * SS) * (1 - smooth(0.3, 0.9, t))
    g = np.clip(cone * fade * 0.55 + core * 0.9, 0, 1)
    colr = (GLOWC[None, None, :] * (1 - core[..., None]) + np.array([0.9, 1.0, 1.0], F32) * core[..., None])
    BR.c[...] = colr * g[..., None]
    BR.a[...] = g
    BR.glow(radial(BR, M, 60), C("#dffcff"), 12, 0.9)

    MI = Part(CV, (0, 430, 470, 1300), 190)
    rng = random.Random(191)
    mist = np.zeros((MI.H, MI.W), F32)
    path = catmull(bpts, n=10)
    for k in range(40):
        s = rng.uniform(0.05, 1.0)
        cpt = path[int(s * (len(path) - 1))]
        rr = float(np.interp(s, np.linspace(0, 1, len(brad)), brad))
        c = (cpt[0] + rng.uniform(-0.75, 0.75) * rr, cpt[1] + rng.uniform(-0.3, 0.3) * rr)
        mist = np.maximum(mist, MI.ellipse(c, rr * rng.uniform(0.12, 0.25), rr * rng.uniform(0.4, 0.8),
                                           rng.uniform(-12, 12)) * rng.uniform(0.3, 1.0))
    streak = fbm(MI.H, MI.W, 14 * SS, np.random.default_rng(192), 3)
    cone_m = blur(MI.tube(bpts, brad, n=10), 8 * SS)
    mist = np.clip(blur(mist, 10 * SS) * 1.4 + cone_m * 0.35, 0, 1) * (0.5 + streak)
    mist = np.clip(mist, 0, 1) * (1 - smooth(0.55, 1.0, lin(MI, M, bpts[-1]))) * cone_m
    MI.paint(np.clip(mist, 0, 1), mk_ramp("#6a8cc0", "#90b0d8", "#b8d4ec", "#dcefff", "#f2fbff", "#ffffff"),
             r=40, line=0.0, cast=0.0, rim=0.5, opacity=0.5, grain=0.05)
    for i in range(16):
        s = rng.uniform(0.12, 0.8)
        path = catmull(bpts, n=10)
        cpt = path[int(s * (len(path) - 1))]
        rr = float(np.interp(s, np.linspace(0, 1, len(brad)), brad))
        b = (cpt[0] + rng.uniform(-0.75, 0.75) * rr, cpt[1] + rng.uniform(-0.3, 0.3) * rr)
        L = rng.uniform(18, 40) * (1.2 - s * 0.4)
        shard_at(MI, b, rng.uniform(95, 130), L, L * 0.38, glow=0.8, seed=200 + i, ramp=ICE, cast=0.0,
                 spark=(i % 3 == 0))
    for i in range(8):
        s = rng.uniform(0.15, 0.7)
        path = catmull(bpts, n=10)
        cpt = path[int(s * (len(path) - 1))]
        MI.sparkle((cpt[0] + rng.uniform(-50, 50), cpt[1] + rng.uniform(-30, 30)), rng.uniform(8, 16), 0.9)

    # ---------------- glow layers and floating shards
    fx_eye = fx_glow(CV, [lambda P: P.ellipse((470, 410), 22, 8, -12)], EYE_GLOW, 14, 1.0, box=(380, 340, 570, 480))
    fx_crest = fx_glow(CV, [lambda P: P.tube([(900, 640), (790, 560), (700, 470), (640, 370)], [60, 60, 50, 40]),
                            lambda P: P.tube([(560, 400), (676, 318), (742, 300)], [26, 16, 6])],
                       GLOWC, 30, 0.3, box=(480, 180, 1060, 760))
    fx_tail = fx_glow(CV, [lambda P: P.ellipse((1712, 800), 50, 80)], GLOWC, 30, 0.5, box=(1560, 600, 1792, 980))

    def floater(seed, c, shards):
        P = Part(CV, (c[0] - 120, c[1] - 120, c[0] + 120, c[1] + 120), seed)
        for i, (a, L, w) in enumerate(shards):
            ra = math.radians(a)
            b = (c[0] - math.cos(ra) * L * 0.35, c[1] - math.sin(ra) * L * 0.35)
            shard_at(P, b, a, L, w, glow=0.9, seed=seed + i, ramp=ICE_DEEP, cast=0.0)
        return P

    F1 = floater(300, (330, 250), [(-80, 90, 32), (-140, 56, 22), (-30, 50, 20)])
    F2 = floater(310, (1530, 760), [(-100, 80, 30), (-50, 52, 20)])
    F3 = floater(320, (500, 1160), [(-110, 64, 24), (-60, 44, 18)])

    def add(name, img, parent, role, pivot, z, blend="normal"):
        big = Image.new("RGBA", rb.canvas, (0, 0, 0, 0))
        big.paste(img, (OFF, 0))
        rb.add(name, big, parent, role, (pivot[0] + OFF, pivot[1]), z, blend)

    add("body", B.image(), "", "root", (1000, 880), 10)
    add("wing_back", WB.image(), "body", "wing_back", (980, 700), 2)
    add("leg_back_upper", far_hind[0].image(), "body", "leg_back_upper", (1300, 880), 4)
    add("leg_back_lower", far_hind[1].image(), "leg_back_upper", "leg_back_lower", (1262, 1045), 3)
    add("arm_back_upper", far_fore[0].image(), "body", "arm_back_upper", (880, 880), 6)
    add("arm_back_lower", far_fore[1].image(), "arm_back_upper", "arm_back_lower", (892, 1040), 5)
    add("tail_1", T1.image(), "body", "tail", (1270, 895), 9)
    add("tail_2", T2.image(), "tail_1", "tail", (1440, 978), 8)
    add("tail_3", T3.image(), "tail_2", "tail", (1625, 1010), 7)
    add("neck", N.image(), "body", "torso", (840, 800), 14)
    add("wing_front", WF.image(), "body", "wing_front", (930, 720), 15)
    add("leg_front_upper", near_hind[0].image(), "body", "leg_front_upper", (1170, 900), 17)
    add("leg_front_lower", near_hind[1].image(), "leg_front_upper", "leg_front_lower", (1100, 1070), 16)
    add("arm_front_upper", near_fore[0].image(), "body", "arm_front_upper", (770, 880), 20)
    add("arm_front_lower", near_fore[1].image(), "arm_front_upper", "arm_front_lower", (745, 1040), 19)
    add("head", H.image(), "neck", "head", (590, 450), 24)
    add("mouth", Mo.image(), "head", "extra", (540, 500), 21)
    add("jaw", J.image(), "head", "jaw", (575, 505), 22)
    add("breath_mist", MI.image(), "head", "extra", M, 26)
    add("breath", BR.image(), "head", "fx", M, 40, blend="add")
    add("eye_glow", fx_eye.image(), "head", "fx", (470, 410), 41, blend="add")
    add("crest_glow", fx_crest.image(), "neck", "fx", (840, 800), 39, blend="add")
    add("tail_glow", fx_tail.image(), "tail_3", "fx", (1712, 850), 38, blend="add")
    add("shard_1", F1.image(), "body", "float", (330, 250), 42)
    add("shard_2", F2.image(), "body", "float", (1530, 760), 43)
    add("shard_3", F3.image(), "body", "float", (500, 1160), 44)
    return rb, 768


RIGS = {
    "frost_wolf": build_frost_wolf,
    "ice_wisp": build_ice_wisp,
    "yeti_cub": build_yeti_cub,
    "ice_troll": build_ice_troll,
    "frostbreath": build_frostbreath,
}


def main(ids):
    import time
    for rid in ids or list(RIGS):
        t = time.time()
        rb, flat = RIGS[rid]()
        save_rig(rb, flat, rid)
        os.makedirs(SCRATCH, exist_ok=True)
        rig.pose_sheet(rid, os.path.join(SCRATCH, f"pose_{rid}.png"))
        print(f"{rid}: {time.time() - t:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])

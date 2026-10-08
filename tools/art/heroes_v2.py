"""Heroes and the companion dragon as painted cut-out rigs (M8 landscape style).

    python3 tools/art/heroes_v2.py                 # everything
    python3 tools/art/heroes_v2.py warrior mage    # only these rig ids (or "eggs")

Rigs: warrior, mage, rogue (canvas 1024, facing right, kind humanoid; flats to
sprites/player/<id>.png at 512) and companion_<fire|frost|venom>_<hatchling|young|adult>
(canvas 768, facing right, kind dragon; flats to sprites/companion/<element>_<stage>.png at 512).
"eggs" redraws sprites/companion/egg_nest.png and egg_nest_cracked.png (512, flat images).

The look is painted semi-realistic anime (see the M8 brief): every part is painted at 2x from
soft masks. Each region of a part gets a height field (a blurred mask plus painted bumps such as
cloth folds and plate ridges), normals from that height field, and a material:

    skin / cloth / leather / hair  soft wrapped diffuse ramp, cool shadows, warm lights, rim light
    metal / gold                   reflection of a sky / horizon / ground environment plus sharp
                                   speculars, which is what makes plate armour read as polished
    glow                           bright core, saturated halo (the fx parts add the pulsing glow)

Key light is warm from the upper left, fill is cool, and a strong rim light sits on the far (right)
edge. Lines are thin, colour-matched and fade where the light hits.
"""
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

import rig  # noqa: E402

SS = 2          # paint scale (design px -> paint px)
MS = 2          # extra supersampling of mask edges
F32 = np.float32

LIGHT = np.array([-0.52, -0.66, 0.54], F32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], F32)
HALF /= np.linalg.norm(HALF)
RIMDIR = np.array([0.92, -0.25, 0.0], F32)
RIMDIR /= np.linalg.norm(RIMDIR)


# ------------------------------------------------------------------ colours

def C(h):
    """'#rrggbb' -> float rgb in 0..1."""
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


def mixc(a, b, t):
    return np.asarray(a, F32) * (1 - t) + np.asarray(b, F32) * t


COOL = C("#3a3f7a")
WARM = C("#ffe6be")
RIMC = C("#dfeaff")


# ------------------------------------------------------------------ numpy image helpers

def _box(a, r, axis):
    if r < 1:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=F32)
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(a, sigma):
    """Gaussian-like blur (three box passes) of a 2-D or 3-D (h, w, c) float array; zero outside."""
    if sigma < 0.4:
        return a
    a = a.astype(F32, copy=False)
    if sigma > 24 and min(a.shape[:2]) > 64:  # large radii: blur at a quarter size
        k = 4
        h, w = a.shape[:2]
        hs, ws = (h + k - 1) // k, (w + k - 1) // k
        pad = [(0, hs * k - h), (0, ws * k - w)] + [(0, 0)] * (a.ndim - 2)
        small = np.pad(a, pad).reshape((hs, k, ws, k) + a.shape[2:]).mean(axis=(1, 3))
        small = blur(small, sigma / k)
        big = np.repeat(np.repeat(small, k, axis=0), k, axis=1)[:h, :w]
        return blur(big, 1.2)
    r = max(1, int(round(math.sqrt(12 * sigma * sigma / 3 + 1) / 2)))
    for _ in range(3):
        a = _box(a, r, 0)
        a = _box(a, r, 1)
    return a


def shift(a, dx, dy):
    """Moves a 2-D array by whole pixels, filling with zeros."""
    dx, dy = int(round(dx)), int(round(dy))
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = a[ys0:ys1, xs0:xs1]
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


_NOISE = {}


def vnoise(h, w, cell, seed, aniso=1.0, angle=0.0):
    """Smooth value noise in 0..1 with cells of `cell` px (stretched by aniso along `angle` degrees)."""
    key = (h, w, round(cell, 2), seed, round(aniso, 2), round(angle, 1))
    if key in _NOISE:
        return _NOISE[key]
    rng = np.random.default_rng(seed)
    diag = int(math.hypot(h, w)) + 4 if angle else max(h, w)
    cy, cx = cell, cell * aniso
    sh, sw = int(diag / cy) + 4, int(diag / cx) + 4
    small = rng.random((sh, sw)).astype(F32)
    im = Image.fromarray(small, "F").resize((int(sw * cx), int(sh * cy)), Image.BICUBIC)
    if angle:
        im = im.rotate(angle, resample=Image.BILINEAR)
    W, H = im.size
    x0, y0 = (W - w) // 2, (H - h) // 2
    out = np.asarray(im, F32)[y0:y0 + h, x0:x0 + w]
    out = np.clip(out, 0, 1)
    if len(_NOISE) > 64:
        _NOISE.clear()
    _NOISE[key] = out
    return out


# ------------------------------------------------------------------ geometry

def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def catmull(pts, closed=False, n=10):
    """Smooth curve through the points (Catmull-Rom)."""
    pts = [tuple(map(float, p)) for p in pts]
    if len(pts) < 3:
        return pts
    P = pts + pts[:3] if closed else [pts[0]] + pts + [pts[-1]]
    out = []
    segs = len(pts) if closed else len(pts) - 1
    for i in range(segs):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def resample(pts, step):
    """Points every `step` px along a polyline, with the running fraction 0..1."""
    d = [0.0]
    for a, b in zip(pts, pts[1:]):
        d.append(d[-1] + math.dist(a, b))
    total = d[-1] or 1.0
    n = max(2, int(total / step) + 1)
    out, j = [], 0
    for i in range(n):
        s = total * i / (n - 1)
        while j < len(d) - 2 and d[j + 1] < s:
            j += 1
        seg = (d[j + 1] - d[j]) or 1.0
        t = (s - d[j]) / seg
        out.append((lerp(pts[j], pts[j + 1], t), s / total))
    return out


def rot(pts, c, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


def ell_pts(c, rx, ry, deg=0, n=48, a0=0, a1=360):
    pts = [(c[0] + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
            c[1] + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + (0 if a1 - a0 >= 360 else 1))]
    return rot(pts, c, deg) if deg else pts


def unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L


def tube_outline(pts, widths, n=8):
    """Closed outline of a tapered stroke through pts (smoothed) with full widths per point."""
    cur = catmull(pts, n=n) if len(pts) > 2 else list(pts)
    m = len(cur)
    ws = np.interp(np.linspace(0, 1, m), np.linspace(0, 1, len(widths)), widths)
    left, right = [], []
    for i, p in enumerate(cur):
        a = cur[max(0, i - 1)]
        b = cur[min(m - 1, i + 1)]
        ux, uy = unit(a, b)
        nx, ny = -uy, ux
        h = ws[i] / 2
        left.append((p[0] + nx * h, p[1] + ny * h))
        right.append((p[0] - nx * h, p[1] - ny * h))
    return left + right[::-1]


# ------------------------------------------------------------------ part canvas

GRADE = None   # (y0, y1, amount): scene light falls off toward the ground


class Warp:
    """Turns a design about `pivot` by `deg` (clockwise on screen, so + leans a figure forward to the
    right) and then moves the pivot to `to`. Used to lean an upright upper body into a stance."""

    def __init__(self, deg=0.0, pivot=(0, 0), to=None):
        self.a = math.radians(deg)
        self.p = pivot
        self.t = to or pivot

    def fwd(self, x, y):
        ca, sa = math.cos(self.a), math.sin(self.a)
        dx, dy = x - self.p[0], y - self.p[1]
        return (self.t[0] + dx * ca - dy * sa, self.t[1] + dx * sa + dy * ca)

    def inv(self, X, Y):
        ca, sa = math.cos(self.a), math.sin(self.a)
        dx, dy = X - self.t[0], Y - self.t[1]
        return (self.p[0] + dx * ca + dy * sa, self.p[1] - dx * sa + dy * ca)


class Part:
    """A painted part: straight rgb + alpha at SS x over a box of the design canvas (design px)."""

    def __init__(self, box, seed=1, xf=None):
        """box is in canvas px. xf: optional Warp (design -> canvas) applied to everything drawn."""
        self.xf = xf
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        self.ox, self.oy = x0, y0
        self.W, self.H = (x1 - x0) * SS, (y1 - y0) * SS
        self.rgb = np.zeros((self.H, self.W, 3), F32)
        self.a = np.zeros((self.H, self.W), F32)
        self.seed = seed

    # ---- coordinates
    def L(self, p):
        return ((p[0] - self.ox) * SS, (p[1] - self.oy) * SS)

    def grid(self):
        if not hasattr(self, "_grid"):
            ys, xs = np.mgrid[0:self.H, 0:self.W].astype(F32)
            X, Y = xs / SS + self.ox, ys / SS + self.oy
            self._grid = self.xf.inv(X, Y) if self.xf else (X, Y)
        return self._grid

    # ---- masks (float 0..1 arrays at paint scale)
    def _draw(self, pts_list, kind="poly", extra=None):
        k = SS * MS
        if self.xf:
            pts_list = [[self.xf.fwd(*p) for p in pts] for pts in pts_list]
        allp = [p for pts in pts_list for p in pts]
        xs = [(p[0] - self.ox) * k for p in allp]
        ys = [(p[1] - self.oy) * k for p in allp]
        pad = 4 + (extra or 0) * k
        bx0 = max(0, int(min(xs) - pad) // MS * MS)
        by0 = max(0, int(min(ys) - pad) // MS * MS)
        bx1 = min(self.W * MS, (int(max(xs) + pad) // MS + 1) * MS)
        by1 = min(self.H * MS, (int(max(ys) + pad) // MS + 1) * MS)
        out = np.zeros((self.H, self.W), F32)
        if bx1 <= bx0 or by1 <= by0:
            return out
        im = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        d = ImageDraw.Draw(im)
        for pts in pts_list:
            q = [((p[0] - self.ox) * k - bx0, (p[1] - self.oy) * k - by0) for p in pts]
            if kind == "poly":
                if len(q) >= 3:
                    d.polygon(q, fill=255)
            elif kind == "line":
                d.line(q, fill=255, width=max(1, int(extra * k)), joint="curve")
        small = np.asarray(im.reduce(MS), F32) / 255.0
        out[by0 // MS:by0 // MS + small.shape[0], bx0 // MS:bx0 // MS + small.shape[1]] = small
        return out

    def poly(self, pts, smooth=False, n=8):
        if smooth:
            pts = catmull(pts, closed=True, n=n)
        return self._draw([pts])

    def polys(self, list_of_pts):
        return self._draw(list_of_pts)

    def ellipse(self, c, rx, ry, deg=0):
        return self._draw([ell_pts(c, rx, ry, deg, n=64)])

    def tube(self, pts, widths, n=8, caps=True):
        """Tapered stroke through the points; widths (full) are spread along it. Round end caps."""
        if isinstance(widths, (int, float)):
            widths = [widths, widths]
        shapes = [tube_outline(pts, widths, n)]
        if caps:
            cur = catmull(pts, n=n) if len(pts) > 2 else list(pts)
            for p, w in ((cur[0], widths[0]), (cur[-1], widths[-1])):
                if w > 1.5:
                    shapes.append(ell_pts(p, w / 2, w / 2, n=24))
        return self._draw(shapes)

    def line(self, pts, width, smooth=True):
        if smooth and len(pts) > 2:
            pts = catmull(pts, n=8)
        return self._draw([pts], kind="line", extra=width)

    # ---- painting
    def over(self, rgb, m):
        """Composites colour (array or rgb triple) with coverage m over the part."""
        m = np.clip(m, 0, 1)[..., None]
        self.rgb = self.rgb * (1 - m) + np.asarray(rgb, F32) * m
        self.a = self.a + m[..., 0] * (1 - self.a)

    def tint(self, rgb, m):
        """Paints colour over existing paint only (does not add coverage)."""
        m = np.clip(m, 0, 1)[..., None]
        self.rgb = self.rgb * (1 - m) + np.asarray(rgb, F32) * m

    def mult(self, rgb, m):
        m = np.clip(m, 0, 1)[..., None]
        self.rgb = self.rgb * (1 - m + m * np.asarray(rgb, F32))

    def add(self, rgb, m):
        m = np.clip(m, 0, None)[..., None]
        self.rgb = self.rgb + np.asarray(rgb, F32) * m

    def cast(self, m, dx=4, dy=6, soft=5, strength=0.5, color=None):
        """Soft shadow of mask m onto what is already painted (offset down-right, away from the light)."""
        s = blur(shift(m, dx * SS, dy * SS), soft * SS) * strength * self.a * (1 - m)
        col = color if color is not None else C("#1c1830")
        self.rgb = self.rgb * (1 - s[..., None]) + (self.rgb * col * 1.6) * s[..., None]

    def paint(self, m, mat, bump=None, round_=None, depth=None, line=None, cast=None, spec=None, rim=None, hgt=None, **kw):
        """Shades mask m with a material and composites it. bump: extra height (paint px units, 0..~1)."""
        mat = dict(mat)
        mat.update(kw)
        if round_ is not None:
            mat["round"] = round_
        if depth is not None:
            mat["depth"] = depth
        if spec is not None:
            mat["spec"] = spec
        if rim is not None:
            mat["rim"] = rim
        if line is not None:
            mat["line"] = line
        if cast is None:
            cast = mat.get("cast", 0.35)
        if cast:
            self.cast(m, strength=cast, dx=mat.get("cast_dx", 3), dy=mat.get("cast_dy", 5), soft=mat.get("cast_soft", 4))
        rgb = shade(self, m, mat, bump, hgt)
        self.over(rgb, m)
        lw = mat.get("line", 1.0)
        if lw:
            self.edge_line(m, mat, lw)
        return rgb

    def edge_line(self, m, mat, width):
        """Thin colour-matched dark line inside the edge of m that fades where the light hits."""
        w = width * SS
        b = blur(m, w * 0.9)
        e = m * smoothstep(0.66, 0.42, b)
        gy, gx = np.gradient(blur(m, w * 2.5))
        g = np.sqrt(gx * gx + gy * gy) + 1e-6
        facing = (-gx / g) * LIGHT[0] + (-gy / g) * LIGHT[1]   # outward normal . light
        facing = facing / np.linalg.norm(LIGHT[:2])
        fade = np.clip(1.0 - np.clip(facing, 0, 1) * 0.85, 0.12, 1)
        base = mat.get("line_c")
        if base is None:
            base = mixc(np.asarray(mat["c"], F32) * 0.28, COOL * 0.35, 0.35)
        self.tint(base, e * fade * mat.get("line_a", 0.85))

    def glow(self, c, r, color, strength=1.0, core=None, core_r=None):
        """Soft halo painted with coverage (so it also shows in the flat)."""
        X, Y = self.grid()
        d = np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2) / r
        m = np.exp(-d * d * 2.2) * strength
        self.over(color, m)
        if core is not None:
            cr = core_r or r * 0.25
            d2 = np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2) / cr
            self.over(core, np.exp(-d2 * d2 * 2.0))

    def finish(self, line=1.9, line_c=None, rim=0.0):
        """Silhouette line, then the downscaled full-canvas RGBA layer."""
        if line:
            w = line * SS
            b = blur(self.a, w * 0.8)
            e = self.a * smoothstep(0.7, 0.4, b)
            gy, gx = np.gradient(blur(self.a, w * 3))
            g = np.sqrt(gx * gx + gy * gy) + 1e-6
            facing = ((-gx / g) * LIGHT[0] + (-gy / g) * LIGHT[1]) / np.linalg.norm(LIGHT[:2])
            fade = np.clip(1.0 - np.clip(facing, 0, 1) * 0.8, 0.2, 1)
            dark = self.rgb * 0.32 + COOL * 0.08 if line_c is None else np.asarray(line_c, F32)
            m = (e * fade * 0.9)[..., None]
            self.rgb = self.rgb * (1 - m) + dark * m
        return self.image()

    def image(self):
        if GRADE:
            y0, y1, amt = GRADE
            ys = (np.arange(self.H, dtype=F32) / SS + self.oy)[:, None, None]
            g = smoothstep(y0, y1, ys)
            self.rgb = self.rgb * (1 - g * amt) + (self.rgb * COOL * 1.4) * (g * amt * 0.35)
        rgb = np.clip(self.rgb, 0, 1)
        a = np.clip(self.a, 0, 1)
        arr = np.dstack([rgb * a[..., None], a])  # premultiplied for clean resampling
        chans = [Image.fromarray(arr[..., i].astype(F32), "F").resize((self.W // SS, self.H // SS), Image.LANCZOS)
                 for i in range(4)]
        out = np.dstack([np.asarray(c, F32) for c in chans])
        al = np.clip(out[..., 3], 0, 1)
        col = np.where(al[..., None] > 1e-4, out[..., :3] / np.maximum(al[..., None], 1e-4), 0)
        rgba = np.dstack([np.clip(col, 0, 1), al])
        return Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA"), (self.ox, self.oy)


def layer(canvas, *parts_images):
    """Full-canvas RGBA from one or more (image, offset) pairs."""
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    for img, (ox, oy) in parts_images:
        tmp = Image.new("RGBA", canvas, (0, 0, 0, 0))
        tmp.paste(img, (ox, oy))
        out.alpha_composite(tmp)
    return out


# ------------------------------------------------------------------ shading

def mat(c, kind="matte", **kw):
    m = {"c": C(c) if isinstance(c, str) else np.asarray(c, F32), "kind": kind}
    defaults = {
        "skin":    dict(round=30, depth=2.2, spec=0.10, shin=18, rim=0.55, wrap=0.55, sss=0.35, tex=0.03, line=0.8),
        "cloth":   dict(round=20, depth=2.2, spec=0.05, shin=8, rim=0.5, wrap=0.35, tex=0.07, line=1.0),
        "leather": dict(round=14, depth=2.6, spec=0.28, shin=22, rim=0.5, wrap=0.3, tex=0.10, line=1.0),
        "hair":    dict(round=12, depth=2.6, spec=0.0, shin=30, rim=0.7, wrap=0.35, tex=0.05, line=0.9),
        "matte":   dict(round=16, depth=2.4, spec=0.10, shin=14, rim=0.5, wrap=0.35, tex=0.06, line=1.0),
        "metal":   dict(round=22, depth=3.4, spec=1.0, shin=70, rim=0.8, tex=0.04, line=1.0),
        "gold":    dict(round=5, depth=3.0, spec=1.0, shin=50, rim=0.6, tex=0.03, line=0.8),
        "gem":     dict(round=6, depth=4.0, spec=1.2, shin=90, rim=0.4, wrap=0.2, tex=0.0, line=0.8),
        "glow":    dict(round=6, depth=1.0, spec=0.0, shin=10, rim=0.0, wrap=1.0, tex=0.0, line=0.0, cast=0),
        "scale":   dict(round=16, depth=2.6, spec=0.35, shin=26, rim=0.65, wrap=0.35, tex=0.06, line=1.0),
    }[kind]
    m.update(defaults)
    m.update(kw)
    return m


def normals(p, m, mat_, bump, hgt=None):
    R = mat_["round"] * SS
    h = (blur(m, R) * 0.65 + blur(m, R * 0.3) * 0.35) * R * mat_["depth"]
    if hgt is not None:
        h = h * mat_.get("edge_k", 0.5) + hgt
    if bump is not None:
        h = h + bump * SS * 6.0
    gy, gx = np.gradient(h)
    nz = np.ones_like(gx)
    n = np.sqrt(gx * gx + gy * gy + 1)
    return -gx / n, -gy / n, nz / n


def env_metal(nx, ny, nz, tint, dark, noise):
    """Environment reflection for polished metal: bright sky above, dark horizon band, warm ground."""
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
    t = ry + (noise - 0.5) * 0.35 + rx * 0.18  # -1 up .. +1 down
    stops = [(-1.0, C("#e6e1d8")), (-0.72, C("#b9bcc2")), (-0.42, C("#8c929c")), (-0.12, C("#5f6571")),
             (0.1, dark), (0.38, dark * 0.85), (0.62, C("#5e4d3e")), (1.0, C("#8a7058"))]
    out = np.zeros(t.shape + (3,), F32)
    tc = np.clip(t, -1, 1)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        w = np.clip((tc - t0) / (t1 - t0), 0, 1)[..., None]
        sel = ((tc >= t0) & (tc <= t1))[..., None]
        out = np.where(sel, c0 * (1 - w) + c1 * w, out)
    return out * tint


def shade(p, m, mat_, bump=None, hgt=None):
    """Colour for mask m under the scene lighting (see module docstring)."""
    nx, ny, nz = normals(p, m, mat_, bump, hgt)
    base = mat_["c"]
    kind = mat_["kind"]
    seed = p.seed + int(base.sum() * 1000) % 997
    grain = vnoise(p.H, p.W, 1.6 * SS, seed) - 0.5
    mottle = vnoise(p.H, p.W, 14 * SS, seed + 1) - 0.5
    ndl = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
    ndh = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1)
    rimv = np.clip(nx * RIMDIR[0] + ny * RIMDIR[1], 0, 1) * np.clip(1 - nz, 0, 1) ** 0.8
    if kind in ("metal", "gold"):
        dark = mat_.get("band", base * 0.12 + C("#10131c"))
        tint = base / max(1e-3, float(base.mean())) * (0.95 if kind == "metal" else 1.0)
        if kind == "gold":
            tint = base * 1.45
        env = env_metal(nx, ny, nz, tint, dark, vnoise(p.H, p.W, 22 * SS, seed + 2, aniso=3.0, angle=-35))
        diff = np.clip(ndl * 0.5 + 0.5, 0, 1)[..., None]
        col = env * (0.55 + 0.6 * diff)
        spec = ndh ** mat_["shin"] * mat_["spec"]
        spec2 = ndh ** (mat_["shin"] * 0.18) * mat_["spec"] * 0.22
        col = col + (spec * 1.5 + spec2)[..., None] * C("#fff3de")
        col = col + (rimv ** 1.5 * mat_["rim"])[..., None] * mixc(RIMC, base, 0.2) * 0.9
        col = col * (1 + (grain * mat_["tex"] + mottle * mat_["tex"])[..., None])
        return np.clip(col, 0, 1.2)
    if kind == "glow":
        core = mat_.get("core", C("#ffffff"))
        h = blur(m, mat_["round"] * SS)
        t = np.clip(h * 1.6 - 0.3, 0, 1)[..., None]
        return base * (1 - t) + core * t
    wrap = mat_.get("wrap", 0.35)
    d = np.clip((ndl + wrap) / (1 + wrap), 0, 1)
    d = d * (1 + (mottle * 0.25 + grain * 0.6) * mat_["tex"] * 2.2)
    shadow = mixc(base * mat_.get("shadow_k", 0.42), COOL * 0.55, mat_.get("cool", 0.28))
    if kind == "skin":
        shadow = mixc(base * 0.62, C("#a24a52"), 0.35)
    lightc = mixc(base * 1.12, WARM, mat_.get("warm", 0.22))
    dd = d[..., None]
    # three-tone ramp: shadow -> base -> light, with a soft terminator
    t1 = smoothstep(0.08, 0.55, dd)
    t2 = smoothstep(0.55, 1.0, dd)
    col = shadow * (1 - t1) + base * t1
    col = col * (1 - t2) + lightc * t2
    if kind == "skin":
        # warm subsurface glow on the terminator
        term = np.exp(-((d - 0.32) / 0.14) ** 2)[..., None] * mat_["sss"]
        col = col + term * C("#ff7a5a") * 0.18
    if mat_["spec"]:
        s = ndh ** mat_["shin"] * mat_["spec"]
        col = col + s[..., None] * mixc(WARM, base, 0.2)
    col = col + (rimv ** 1.3 * mat_["rim"])[..., None] * mixc(RIMC, base, mat_.get("rim_tint", 0.35)) * 0.8
    # cool bounce from below
    bounce = np.clip(ny, 0, 1) * np.clip(1 - nz, 0, 1) * 0.25
    col = col + bounce[..., None] * mixc(C("#4a5f8a"), base, 0.4) * 0.35
    return np.clip(col, 0, 1.2)


# ------------------------------------------------------------------ bump helpers (height strokes)

def dome(p, c, rx, ry, deg=0.0, k=1.0):
    """Ellipsoid height field (paint px) centred at c: the form of a breastplate, pauldron or skull."""
    X, Y = p.grid()
    a = math.radians(deg)
    dx, dy = X - c[0], Y - c[1]
    u = (dx * math.cos(a) + dy * math.sin(a)) / rx
    v = (-dx * math.sin(a) + dy * math.cos(a)) / ry
    return np.sqrt(np.clip(1 - u * u - v * v, 0.0025, 1)) * min(rx, ry) * SS * k


def cyl(p, a, b, r, k=1.0):
    """Cylinder height field (paint px) around the axis a-b with radius r: limbs, greaves, vambraces."""
    X, Y = p.grid()
    ux, uy = unit(a, b)
    d = (-(X - a[0]) * uy + (Y - a[1]) * ux) / r
    return np.sqrt(np.clip(1 - d * d, 0.0025, 1)) * r * SS * k


def fold(p, pts, width, depth=1.0, soft=None, smooth=True):
    """A soft ridge (depth>0) or crease (depth<0) as a height stroke, in paint px units."""
    m = p.line(pts, width, smooth=smooth)
    return blur(m, (soft or width * 0.6) * SS) * depth


# ------------------------------------------------------------------ small painted details

def trim(p, pts, width, c="#d9a743", smooth=True, **kw):
    """Gold (or other metal) piping along a path."""
    m = p.line(pts, width, smooth=smooth)
    p.paint(m, mat(c, "gold", round=max(1.5, width * 0.45)), cast=0.25, line=0.6, **kw)
    return m


def gem(p, c, r, color, glow=0.0):
    col = C(color)
    m = p.ellipse(c, r, r)
    p.paint(m, mat(color, "gem", round=r * 0.7), cast=0.3, line=0.7)
    X, Y = p.grid()
    d = np.sqrt((X - c[0] + r * 0.2) ** 2 + (Y - c[1] - r * 0.25) ** 2) / r
    p.tint(np.clip(col * 1.8 + 0.2, 0, 1), m * np.exp(-d * d * 2.5) * 0.7)
    p.tint(C("#ffffff"), p.ellipse((c[0] - r * 0.35, c[1] - r * 0.35), r * 0.28, r * 0.22) * 0.9)
    if glow:
        p.glow(c, r * 3, col, strength=glow * 0.5)


def rivet(p, c, r=2.6, color="#dfe3ea"):
    p.paint(p.ellipse(c, r, r), mat(color, "metal", round=r), cast=0.35, line=0.5)


def lock(p, root, mid, tip, w, bend=0.0):
    """One tapered hair lock (a mask)."""
    return p.tube([root, mid, tip], [w, w * 0.72, w * 0.3, 0.6])


def hair_mass(p, base_masks, locks, base, light, sheen=None, rim=0.9, cast=0.5, round_=18, streaks=2,
              line_a=0.7, cast_onto=True, depth=2.2):
    """Paints hair as one mass (so it keeps the head's volume) and carves it into locks with ridges,
    dark separations and light strand streaks. locks: list of (points, width). sheen: (cx, cy, rx, ry)
    ellipse along which the glossy band runs."""
    masks = [p.tube(pts, [w, w * 0.78, w * 0.42, 0.8]) for pts, w in locks]
    total = np.zeros((p.H, p.W), F32)
    for m in list(base_masks) + masks:
        total = np.maximum(total, m)
    if cast_onto:
        p.cast(total, dx=2, dy=5, soft=4, strength=cast)
    bump = np.zeros_like(total)
    for m in masks:
        bump = np.maximum(bump, blur(m, 2.2 * SS) * 0.9)
    hm = mat(base, "hair", rim=rim, round=round_, depth=depth, line_a=line_a)
    p.paint(total, hm, bump=bump, cast=0.0)
    X, Y = p.grid()
    lc = C(light)
    if sheen is not None:
        cx, cy, rx, ry = sheen
        d = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
        band = np.exp(-((d - 1.0) / 0.16) ** 2) * total
    else:
        band = np.zeros_like(total)
    # lock separations (a dark line on each lock's edge where it lies over other hair) and streaks
    dk = mixc(C(base) * 0.3, COOL * 0.3, 0.3)
    for (pts, w), m in zip(locks, masks):
        e = m * smoothstep(0.62, 0.35, blur(m, 1.2 * SS))
        p.tint(dk, e * 0.55)
        cur = catmull(pts, n=8)
        for k in range(streaks):
            off = (k - (streaks - 1) / 2) * w * 0.28
            q = []
            for i, pt in enumerate(cur):
                a = cur[max(0, i - 1)]
                b = cur[min(len(cur) - 1, i + 1)]
                ux, uy = unit(a, b)
                q.append((pt[0] - uy * off, pt[1] + ux * off))
            q = q[1:int(len(q) * 0.85)]
            if len(q) < 2:
                continue
            st = p.tube(q, [0.3, max(1.0, w * 0.1), 0.3])
            p.tint(lc, st * m * np.clip(0.18 + band * 0.9, 0, 1))
    if sheen is not None:
        streak = vnoise(p.H, p.W, 1.5 * SS, 77, aniso=0.25)
        p.tint(lc, band * np.clip(0.2 + streak * 1.0, 0, 1) * 0.55)
    return total


# ------------------------------------------------------------------ anime face

def anime_eye(p, c, w, h, iris, look=0.2, lid="#2a1612", far=False, glowc=None, lash=1.0, female=False, glow_iris=0.0):
    """Big anime eye centred at c (w x h design px), iris colours (dark, light). The near eye of a face
    turned right has its outer corner on the left; the far eye on the right."""
    x, y = c
    sx = 1 if far else -1

    def P(dx, dy):
        return (x + sx * dx * w, y + dy * h)
    if far:
        top = [P(-0.5, -0.02), P(-0.2, -0.45), P(0.2, -0.46), P(0.5, -0.1)]
        bot = [P(0.45, 0.2), P(0.1, 0.44), P(-0.3, 0.38)]
    else:
        # inner corner (right) round and a little low, outer corner (left) sharp and lifted
        top = [P(-0.5, 0.12), P(-0.3, -0.32), P(0.05, -0.5), P(0.36, -0.4), P(0.54, -0.08)]
        bot = [P(0.52, 0.12), P(0.22, 0.42), P(-0.2, 0.46), P(-0.44, 0.3)]
    white = p.poly(top + bot, smooth=True, n=6)
    p.over(C("#fbf7f4"), white)
    X, Y = p.grid()
    p.tint(C("#b9aab8"), white * np.clip(1 - (Y - (y - h * 0.5)) / (h * 0.55), 0, 1) * 0.8)
    ix = x + w * (look if not far else look * 0.8)
    irw, irh = (w * 0.34 if not far else w * 0.42), h * 0.54
    ir = p.ellipse((ix, y + h * 0.04), irw, irh) * white
    dk, lt = C(iris[0]), C(iris[1])
    t = np.clip((Y - (y - irh)) / (2 * irh), 0, 1)[..., None]
    col = dk * (1 - t) ** 1.2 + lt * (1 - (1 - t) ** 1.2)
    p.over(col, ir)
    ring = ir * smoothstep(0.5, 0.95, np.sqrt(((X - ix) / irw) ** 2 + ((Y - y - h * 0.04) / irh) ** 2))
    p.tint(dk * 0.5, ring * 0.8)
    ang = np.arctan2(Y - y, X - ix)
    stri = (np.sin(ang * 23) * 0.5 + 0.5) * ir * 0.18
    p.tint(np.clip(lt * 1.4, 0, 1), stri * np.clip(t[..., 0] * 1.5 - 0.3, 0, 1))
    pu = p.ellipse((ix + w * 0.02, y + h * 0.02), irw * 0.42, irh * 0.5) * white
    p.over(dk * 0.35, pu * 0.9)
    p.tint(np.clip(lt * 1.35 + 0.1, 0, 1), ir * np.exp(-(((X - ix) / (irw * 0.7)) ** 2 + ((Y - y - h * 0.3) / (irh * 0.35)) ** 2)) * 0.8)
    if glow_iris:
        p.tint(np.clip(lt * 1.6 + 0.25, 0, 1), ir * glow_iris)
    p.tint(dk * 0.4, ir * np.clip(1 - (Y - (y - h * 0.5)) / (h * 0.35), 0, 1) * 0.85)
    lidc = C(lid)
    th = 3.4 * lash if not far else 2.8 * lash
    tl = catmull(top, n=8)
    if far:
        up = p.tube(tl, [th * 0.45, th * 0.9, th * 1.2, th * 1.3])
        up = np.maximum(up, p.tube([top[-1], P(0.64, -0.04)], [th, 0.5]))
    else:
        up = p.tube(tl, [th * 1.35, th * 1.3, th * 1.1, th * 0.8, th * 0.45])
        flick = p.tube([top[0], P(-0.66, 0.0 if not female else -0.12)], [th * 1.2, 0.5])
        up = np.maximum(up, flick)
        if female:
            up = np.maximum(up, p.tube([P(-0.4, -0.2), P(-0.62, -0.36)], [th * 0.8, 0.4]))
    p.over(lidc, up)
    lw = catmull(bot, n=6)
    lo = p.tube(lw[len(lw) // 3:] if not far else lw[:max(2, len(lw) * 2 // 3)], [0.4, 1.1, 1.4])
    p.over(mixc(lidc, C("#c07a6a"), 0.45), lo * 0.8)
    if not far:
        cr = p.tube([P(-0.34, -0.62), P(0.05, -0.76), P(0.4, -0.62)], [0.4, 1.2, 0.4])
        p.over(mixc(lidc, C("#c08070"), 0.55), cr * 0.55)
    p.over(C("#ffffff"), p.ellipse((ix - irw * 0.35, y - irh * 0.35), irw * 0.36, irh * 0.26, -20))
    p.over(C("#ffffff"), p.ellipse((ix + irw * 0.4, y + irh * 0.45), irw * 0.15, irh * 0.12) * 0.85)
    if glowc:
        p.glow((ix, y), w * 0.9, C(glowc), strength=0.18)


def brow(p, a, b, c, w=3.6, arch=-2.0):
    m = p.tube([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + arch), b], [w * 0.6, w, w * 0.35])
    p.over(C(c), m * 0.95)


def face_skin(p, F, skin, female=False):
    """Paints the 3/4 face (facing right) in head frame F; returns the face mask."""
    if female:
        pts = [F(-36, -34), F(-44, 4), F(-40, 30), F(-22, 50), F(4, 64), F(24, 72), F(34, 71),
               F(44, 60), F(49, 51), F(51, 46), F(54.5, 39), F(53, 33), F(53, 22), F(55, 8),
               F(53, -12), F(44, -40), F(10, -56), F(-22, -52)]
    else:
        pts = [F(-36, -34), F(-44, 4), F(-42, 28), F(-30, 46), F(0, 60), F(24, 70), F(35, 69),
               F(45, 58), F(50, 50), F(52, 46), F(56, 38), F(54.5, 32), F(54, 22), F(56, 8),
               F(54, -12), F(44, -40), F(10, -56), F(-22, -52)]
    m = p.poly(pts, smooth=True, n=8)
    # bump: cheek, brow ridge, nose, chin
    bump = fold(p, [F(50, 24), F(54.5, 35)], 5, 0.9) + fold(p, [F(8, 4), F(50, 3)], 8, 0.4)
    bump = bump + blur(p.ellipse(F(28, 38), 16, 12), 8 * SS) * 0.7 + blur(p.ellipse(F(33, 66), 9, 6), 4 * SS) * 0.5
    bump = bump - blur(p.ellipse(F(24, 14), 18, 9), 6 * SS) * 0.5  # eye sockets
    p.paint(m, mat(skin, "skin", round=30, depth=1.5, line=0.9), bump=bump, cast=0.0)
    # jaw shadow (the face turns away from the light below the cheekbone)
    p.tint(C("#c98a7a"), m * blur(p.poly([F(-44, 20), F(-20, 30), F(10, 50), F(30, 60), F(26, 80), F(-30, 60)]), 7 * SS) * 0.35)
    # blush and warm cheek
    p.tint(C("#f08f84"), m * blur(p.ellipse(F(28, 34), 12, 6), 5 * SS) * (0.35 if female else 0.14))
    p.tint(C("#f08f84"), m * blur(p.ellipse(F(51, 34), 4, 4), 3 * SS) * 0.22)
    return m


def nose_mouth(p, F, female=False, frown=0.0):
    # nose: a shadow under the tip and a soft highlight on the bridge
    p.tint(C("#b9705f"), p.tube([F(51, 31), F(54, 37), F(51, 39.5)], [0.6, 1.9, 0.6]) * 0.75)
    p.tint(C("#fff1e6"), blur(p.tube([F(54, 18), F(56.5, 32)], [1.0, 2.0]), 1.0 * SS) * 0.6)
    # mouth
    if female:
        p.over(C("#9a4a48"), p.tube([F(41, 51.5), F(46, 52.2), F(50, 51.2)], [0.6, 1.8, 0.6]) * 0.85)
        p.tint(C("#f2a39a"), blur(p.ellipse(F(45, 56), 4, 1.6), 1.2 * SS) * 0.5)
    else:
        p.over(C("#7d3c34"), p.tube([F(39, 52 + frown), F(45, 51.4), F(50, 52 - frown * 0.4)], [0.6, 1.8, 0.6]) * 0.8)
        p.tint(C("#d98d7e"), blur(p.ellipse(F(45, 56.5), 3.5, 1.4), 1.2 * SS) * 0.45)


def ear(p, F, skin):
    m = p.poly([F(-36, 8), F(-26, 6), F(-22, 20), F(-26, 36), F(-34, 34), F(-38, 20)], smooth=True)
    p.paint(m, mat(skin, "skin", round=6), cast=0.3, line=0.9,
            bump=fold(p, [F(-31, 14), F(-29, 26)], 3, -0.8))
    return m


# ------------------------------------------------------------------ shape helpers

def arc_band(c, r0, r1, a0, a1, sy=1.0, deg=0.0, n=24):
    """Crescent band between radii r0 and r1 from angle a0 to a1 (degrees), squashed by sy, turned by deg."""
    outer = [(c[0] + r1 * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
              c[1] + r1 * sy * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    inner = [(c[0] + r0 * math.cos(math.radians(a1 - (a1 - a0) * i / n)),
              c[1] + r0 * sy * math.sin(math.radians(a1 - (a1 - a0) * i / n))) for i in range(n + 1)]
    pts = outer + inner
    return rot(pts, c, deg) if deg else pts


def along(a, b, t, off=0.0):
    """Point at fraction t from a to b, pushed `off` px to the left of the direction a->b."""
    ux, uy = unit(a, b)
    x, y = lerp(a, b, t)
    return (x + uy * off, y - ux * off)


def quad(a, b, wa, wb):
    """Four-point band from a to b with widths wa, wb."""
    ux, uy = unit(a, b)
    nx, ny = -uy, ux
    return [(a[0] + nx * wa / 2, a[1] + ny * wa / 2), (b[0] + nx * wb / 2, b[1] + ny * wb / 2),
            (b[0] - nx * wb / 2, b[1] - ny * wb / 2), (a[0] - nx * wa / 2, a[1] - ny * wa / 2)]


def griffin(c, s, deg=0.0):
    """Heraldic griffin rampant facing right (eagle head and wings, lion hindquarters): polygons."""
    def T(pts):
        q = [(c[0] + x * s, c[1] + y * s) for x, y in pts]
        return rot(q, c, deg) if deg else q
    polys = []
    # raised wing: a fan of pointed feathers behind the body
    for i in range(6):
        ang = math.radians(196 + i * 15)
        r = 0.86 - abs(i - 2.5) * 0.06
        base = (-0.02 - i * 0.02, -0.18 + i * 0.01)
        tip = (base[0] + math.cos(ang) * r, base[1] + math.sin(ang) * r)
        polys.append(T(tube_outline([base, lerp(base, tip, 0.55), tip], [0.2, 0.15, 0.02], n=4)))
    polys.append(T(tube_outline([(0.04, -0.12), (-0.2, -0.3), (-0.4, -0.52)], [0.24, 0.2, 0.12], n=4)))
    polys.append(T(tube_outline([(0.12, -0.12), (0.0, 0.14), (-0.12, 0.36)], [0.34, 0.34, 0.3], n=6)))  # body
    polys.append(T(tube_outline([(0.1, -0.12), (0.2, -0.34), (0.25, -0.46)], [0.24, 0.18, 0.15], n=4)))  # neck
    polys.append(T(ell_pts((0.27, -0.5), 0.12, 0.11, n=20)))                                          # head
    polys.append(T([(0.34, -0.58), (0.52, -0.54), (0.56, -0.44), (0.5, -0.38), (0.47, -0.45), (0.36, -0.43)]))  # beak
    polys.append(T([(0.2, -0.56), (0.1, -0.76), (0.28, -0.6)]))                                        # ear tuft
    limbs = (([(0.12, -0.1), (0.3, -0.12), (0.42, -0.3), (0.5, -0.32)], [0.1, 0.08, 0.06, 0.04]),      # talons up
             ([(0.08, 0.04), (0.3, 0.08), (0.44, -0.02), (0.54, -0.02)], [0.1, 0.08, 0.06, 0.04]),
             ([(-0.04, 0.3), (0.16, 0.5), (0.08, 0.78), (0.24, 0.84)], [0.18, 0.12, 0.08, 0.06]),    # hind legs
             ([(-0.16, 0.36), (-0.22, 0.62), (-0.14, 0.86), (-0.02, 0.9)], [0.16, 0.1, 0.07, 0.06]),
             ([(-0.2, 0.36), (-0.48, 0.44), (-0.58, 0.2), (-0.48, 0.02)], [0.07, 0.06, 0.05, 0.04]))  # tail
    for pts, w in limbs:
        polys.append(T(tube_outline(pts, w, n=6)))
    polys.append(T(ell_pts((-0.48, 0.0), 0.06, 0.1, n=12)))
    return polys


def emblem(p, polys, c="#e2b659", clip=None, emboss=True):
    """Embroidered / inlaid gold emblem."""
    m = p.polys(polys)
    if clip is not None:
        m = m * clip
    p.paint(m, mat(c, "gold", round=2.0), cast=0.35, line=0.6)
    return m


def fist(p, wrist, u, grip_u, size, glove="#35302f", plate="#c3c9d2", trim_c="#d4a64a", knuckle_side=1):
    """A gauntleted fist at the end of a forearm direction u, wrapped around a grip running along grip_u."""
    wx, wy = wrist
    hc = (wx + u[0] * size * 0.55, wy + u[1] * size * 0.55)
    # palm block
    body = p.poly(rot([(hc[0] - size * 0.55, hc[1] - size * 0.42), (hc[0] + size * 0.5, hc[1] - size * 0.5),
                       (hc[0] + size * 0.62, hc[1] + size * 0.4), (hc[0] - size * 0.5, hc[1] + size * 0.48)],
                      hc, math.degrees(math.atan2(u[1], u[0]))), smooth=True, n=6)
    p.paint(body, mat(glove, "leather", round=size * 0.4), cast=0.4)
    # curled fingers: a row of knuckle rolls across the grip, on the far end of the fist
    gx, gy = grip_u
    fc = (hc[0] + u[0] * size * 0.32, hc[1] + u[1] * size * 0.32)
    fingers = []
    for i in range(4):
        t = (i - 1.5) * size * 0.25
        cc = (fc[0] + gx * t, fc[1] + gy * t)
        fingers.append(p.ellipse(cc, size * 0.2, size * 0.17, math.degrees(math.atan2(u[1], u[0]))))
    for fm in fingers:
        p.paint(fm, mat(glove, "leather", round=size * 0.16), cast=0.35, line=0.8)
    # plate over the back of the hand
    bp = p.poly(rot([(hc[0] - size * 0.5, hc[1] - size * 0.36), (hc[0] + size * 0.2, hc[1] - size * 0.42),
                     (hc[0] + size * 0.28, hc[1] + size * 0.26), (hc[0] - size * 0.46, hc[1] + size * 0.34)],
                    hc, math.degrees(math.atan2(u[1], u[0]))), smooth=True, n=5)
    p.paint(bp, mat(plate, "metal", round=size * 0.3), cast=0.4)
    trim(p, rot([(hc[0] - size * 0.5, hc[1] - size * 0.36), (hc[0] - size * 0.46, hc[1] + size * 0.34)],
                hc, math.degrees(math.atan2(u[1], u[0]))), 2.4, c=trim_c)
    return hc


def sword(p, hand, d, blade_len=300, blade_w=26, grip=34, pommel_c="#d4a64a", blade_c="#d9dee6", gem_c="#3f7fe0"):
    """Longsword held at `hand`, blade along unit d."""
    nx, ny = -d[1], d[0]
    pom = (hand[0] - d[0] * grip, hand[1] - d[1] * grip)
    guard = (hand[0] + d[0] * 22, hand[1] + d[1] * 22)
    tip = (guard[0] + d[0] * blade_len, guard[1] + d[1] * blade_len)
    # blade: two bevels split by the fuller line; the upper bevel faces the sky, the lower the ground
    w0, w1 = blade_w / 2, blade_w * 0.4
    pre = (guard[0] + d[0] * (blade_len - blade_w * 1.6), guard[1] + d[1] * (blade_len - blade_w * 1.6))
    up = [(guard[0] - nx * w0, guard[1] - ny * w0), (pre[0] - nx * w1, pre[1] - ny * w1), tip,
          (pre[0], pre[1]), (guard[0], guard[1])]
    lo = [(guard[0], guard[1]), (pre[0], pre[1]), tip, (pre[0] + nx * w1, pre[1] + ny * w1),
          (guard[0] + nx * w0, guard[1] + ny * w0)]
    mu, ml = p.poly(up), p.poly(lo)
    blade = np.maximum(mu, ml)
    p.cast(blade, strength=0.3)
    X, Y = p.grid()
    t = ((X - guard[0]) * d[0] + (Y - guard[1]) * d[1]) / blade_len
    streak = vnoise(p.H, p.W, 30 * SS, 5, aniso=4.0, angle=-math.degrees(math.atan2(d[1], d[0])))
    top = mixc(C("#fdf8ee"), C("#a9b6c8"), np.clip(t * 0.9 + (streak - 0.5) * 0.9, 0, 1)[..., None])
    bot = mixc(C("#6d7686"), C("#39404f"), np.clip(t * 0.7 + (streak - 0.5) * 0.6, 0, 1)[..., None])
    p.over(top, mu)
    p.over(bot, ml)
    # fuller (a dark groove near the base) and a sharp edge light
    fl = p.tube([along(guard, tip, 0.02), along(guard, tip, 0.62)], [5, 3.5])
    p.tint(C("#56627a"), fl * 0.8)
    p.tint(C("#ffffff"), p.tube([along(guard, tip, 0.03), along(guard, tip, 0.66)], [1.2, 0.8]) * 0.6)
    edge = p.line([(guard[0] - nx * (w0 - 1), guard[1] - ny * (w0 - 1)), (pre[0] - nx * (w1 - 1), pre[1] - ny * (w1 - 1)), tip], 1.6, smooth=False)
    p.tint(C("#ffffff"), edge * 0.9)
    p.edge_line(blade, {"c": C("#6d7686")}, 1.0)
    # grip, guard, pommel
    gm = p.tube([pom, guard], [11, 12])
    p.paint(gm, mat("#3b2517", "leather", round=4), bump=sum(fold(p, [along(pom, guard, k / 7, -6), along(pom, guard, k / 7 + 0.05, 6)], 1.4, -0.6) for k in range(1, 7)))
    gl = 40
    cg = [(guard[0] + nx * gl - d[0] * 6, guard[1] + ny * gl - d[1] * 6), (guard[0] + nx * gl * 0.4, guard[1] + ny * gl * 0.4),
          guard, (guard[0] - nx * gl * 0.4, guard[1] - ny * gl * 0.4), (guard[0] - nx * gl - d[0] * 6, guard[1] - ny * gl - d[1] * 6)]
    p.paint(p.tube(cg, [7, 10, 13, 10, 7]), mat(pommel_c, "gold", round=4), cast=0.45)
    for e in (cg[0], cg[-1]):
        p.paint(p.ellipse(e, 6, 6), mat(pommel_c, "gold", round=4), cast=0.3)
    # a small langet on the blade
    p.paint(p.poly([(guard[0] - nx * 9, guard[1] - ny * 9), (guard[0] + d[0] * 20, guard[1] + d[1] * 20),
                    (guard[0] + nx * 9, guard[1] + ny * 9)]), mat(pommel_c, "gold", round=3), cast=0.3)
    gem(p, guard, 5, gem_c)
    p.paint(p.ellipse(pom, 10, 10), mat(pommel_c, "gold", round=6), cast=0.4)
    gem(p, pom, 4.5, gem_c)
    return tip


# ------------------------------------------------------------------ warrior

HERO = (1024, 1024)
SILVER = "#c4cad3"
GOLD = "#d6a84c"
ROYAL = "#1f2e7c"
SKIN = "#f4d3ba"


def plate(p, pts, c=SILVER, smooth=True, round_=None, bump=None, cast=0.4, hgt=None, **kw):
    m = p.poly(pts, smooth=smooth)
    mt = mat(c, "metal")
    if round_:
        mt["round"] = round_
    if hgt is not None:
        mt["round"] = min(mt["round"], 7)
    p.paint(m, mt, bump=bump, cast=cast, hgt=hgt, **kw)
    return m


def cloth(p, pts, c, folds=(), smooth=True, round_=None, cast=0.35, **kw):
    """Cloth region with folds: list of (points, width, depth)."""
    m = p.poly(pts, smooth=smooth) if not isinstance(pts, np.ndarray) else pts
    b = None
    for f in folds:
        fb = fold(p, f[0], f[1], f[2])
        b = fb if b is None else b + fb
    mt = mat(c, "cloth")
    if round_:
        mt["round"] = round_
    p.paint(m, mt, bump=b, cast=cast, **kw)
    return m


U = Warp(14, (520, 470), (475, 500))     # the upper body is drawn upright and leaned into the lunge
UR = Warp(6, (520, 470), (475, 500))     # the hips and the hanging tabard lean less
HS = 1.2                                 # head scale
WHX, WHY = 520, 160
HEAD_PIVOT = (528, 240)
HAIR_C, HAIR_L = "#4a2a1a", "#d89c5c"


def WF(x, y):
    return (WHX + x * HS, WHY + y * HS)


def warrior_head():
    F = WF
    p = Part((WHX - 110, WHY - 118, WHX + 96, WHY + 110), seed=11)
    mass = p.poly([F(-36, -34), F(-44, 4), F(-40, 40), F(-50, 52), F(-62, 20), F(-62, -20), F(-40, -54), F(0, -64), F(40, -50)], smooth=True)
    hair_mass(p, [mass], [([F(-34, 20), F(-50, 44), F(-52, 64)], 18), ([F(-26, 30), F(-36, 54), F(-34, 72)], 14)], HAIR_C, HAIR_L, round_=16)
    face_skin(p, F, SKIN)
    ear(p, F, SKIN)
    anime_eye(p, F(20, 15), 27 * HS, 15 * HS, ("#182652", "#6a9edc"))
    anime_eye(p, F(48.5, 13.5), 11.5 * HS, 14 * HS, ("#182652", "#6a9edc"), far=True)
    brow(p, F(33, 0), F(3, -7), "#3a2115", w=4.4, arch=-1.2)
    brow(p, F(42, 0), F(56, -6), "#3a2115", w=3.2, arch=-0.6)
    nose_mouth(p, F)
    cap = p.poly([F(58, -22), F(50, -50), F(20, -66), F(-20, -64), F(-54, -40), F(-62, -5), F(-52, 34), F(-40, 54),
                  F(-32, 36), F(-34, 14), F(-24, 4), F(-18, -14), F(10, -24), F(40, -28)], smooth=True)
    fr = [([F(24, -52), F(44, -28), F(52, 4)], 22), ([F(10, -56), F(24, -26), F(30, 9)], 22),
          ([F(-4, -56), F(8, -26), F(12, 2)], 20), ([F(36, -48), F(58, -30), F(70, -10)], 16),
          ([F(-22, -30), F(-26, 4), F(-20, 36)], 18), ([F(-14, -60), F(14, -76), F(44, -72)], 24),
          ([F(10, -60), F(42, -62), F(64, -44)], 20), ([F(-30, -52), F(-12, -76), F(10, -84)], 20),
          ([F(30, -52), F(40, -34), F(40, -6)], 12), ([F(-8, -42), F(-4, -14), F(-8, 12)], 12),
          ([F(-40, -42), F(-42, -10), F(-46, 22)], 16), ([F(44, -40), F(60, -16), F(58, 12)], 12)]
    hair_mass(p, [cap], fr, HAIR_C, HAIR_L, sheen=(F(0, -14)[0], F(0, -14)[1], 60, 50))
    return p.finish(line=1.6)


def warrior_hair():
    """The swept-back tufts behind the head (role hair: they sway)."""
    F = WF
    p = Part((WHX - 150, WHY - 116, WHX + 20, WHY + 100), seed=12)
    back = [([F(-20, -44), F(-62, -44), F(-100, -32)], 30), ([F(-30, -18), F(-72, -10), F(-104, 4)], 26),
            ([F(-34, 10), F(-66, 26), F(-92, 44)], 24), ([F(-30, 30), F(-50, 52), F(-62, 72)], 20),
            ([F(-5, -54), F(-40, -70), F(-80, -70)], 24), ([F(-24, 0), F(-60, 8), F(-84, 26)], 18)]
    base = p.ellipse(F(-26, -8), 32, 44)
    hair_mass(p, [base], back, HAIR_C, HAIR_L, round_=14, sheen=(F(-24, -8)[0], F(-24, -8)[1], 60, 50))
    return p.finish(line=1.6)


def warrior_torso():
    p = Part((380, 200, 680, 560), seed=13, xf=U)
    p.paint(p.tube([(508, 196), (512, 262)], [36, 42]), mat(SKIN, "skin", round=14), cast=0)
    p.tint(C("#b9776a"), p.tube([(508, 196), (512, 250)], [42, 42]) * 0.45)
    body = [(450, 268), (486, 250), (540, 250), (586, 268), (602, 312), (598, 372), (578, 440), (556, 476), (482, 478),
            (462, 440), (446, 352), (442, 290)]
    cloth(p, body, "#22306e", folds=[([(456, 300), (464, 420)], 10, -1.6), ([(588, 300), (584, 420)], 8, -1.2)])
    col = [(464, 250), (474, 212), (492, 200), (512, 212), (536, 230), (554, 250), (560, 270), (530, 280), (496, 280), (466, 272)]
    cloth(p, col, ROYAL, folds=[([(486, 212), (486, 274)], 5, 1.6), ([(528, 234), (538, 274)], 5, 1.6)])
    trim(p, [(466, 256), (474, 214), (492, 202), (512, 214), (536, 232), (552, 250), (558, 270)], 3.0)
    bp = [(462, 276), (500, 268), (546, 270), (588, 290), (598, 336), (592, 392), (572, 424), (484, 428), (464, 394),
          (456, 330), (454, 294)]
    ridge = fold(p, [(546, 272), (562, 330), (556, 424)], 8, 1.8)
    plate(p, bp, bump=ridge * 0.5, hgt=dome(p, (532, 340), 90, 118, k=0.9) + dome(p, (574, 330), 30, 60, k=0.4))
    trim(p, [(460, 280), (500, 272), (546, 274), (588, 292)], 3.2)
    trim(p, [(546, 274), (562, 330), (556, 424)], 2.0)
    trim(p, [(464, 396), (484, 426), (530, 429), (572, 424)], 3.0)
    for i, (y0, y1) in enumerate(((422, 448), (444, 472))):
        lame = [(470 + i * 3, y0), (576 - i * 3, y0 - 4), (570 - i * 3, y1 - 6), (474 + i * 3, y1)]
        plate(p, lame, hgt=cyl(p, (524, 380), (524, 500), 70, k=0.9) + cyl(p, (470, (y0 + y1) / 2), (576, (y0 + y1) / 2 - 3), 14, k=0.5))
        trim(p, [(474 + i * 3, y1 - 1), (570 - i * 3, y1 - 7)], 2.2)
    p.paint(p.ellipse((570, 304), 11, 11), mat(GOLD, "gold", round=6), cast=0.45)
    gem(p, (570, 304), 6.0, "#3b78e6")
    return p.finish(line=1.8)


def warrior_root():
    p = Part((360, 440, 640, 760), seed=14, xf=UR)
    skirt = [(462, 452), (584, 450), (610, 540), (586, 572), (520, 580), (446, 574), (432, 530)]
    cloth(p, skirt, "#243170", folds=[([(476, 470), (454, 566)], 9, -2.0), ([(512, 470), (506, 576)], 9, -2.0),
                                      ([(560, 466), (590, 562)], 9, -2.0), ([(494, 470), (480, 574)], 8, 1.6)])
    trim(p, [(432, 532), (446, 574), (520, 580), (586, 572), (610, 540)], 2.6)
    tab = [(516, 462), (562, 458), (572, 560), (578, 668), (546, 700), (512, 672), (508, 560)]
    tm = cloth(p, tab, ROYAL, folds=[([(526, 480), (522, 660)], 7, -1.8), ([(550, 480), (562, 660)], 8, 1.8)], round_=10)
    trim(p, [(512, 470), (508, 560), (512, 672), (546, 700), (578, 668), (572, 560), (564, 466)], 3.0)
    emblem(p, griffin((543, 606), 28), clip=tm)
    front = [(546, 464), (590, 458), (612, 512), (598, 534), (560, 532)]
    plate(p, front, hgt=cyl(p, (570, 440), (580, 600), 40, k=0.9))
    trim(p, [(560, 532), (598, 534), (612, 512)], 2.6)
    back = [(462, 466), (506, 466), (504, 526), (472, 534), (446, 518)]
    plate(p, back, hgt=cyl(p, (478, 440), (470, 600), 38, k=0.9))
    trim(p, [(446, 518), (472, 534), (504, 526)], 2.6)
    belt = [(458, 446), (588, 440), (592, 470), (460, 476)]
    p.paint(p.poly(belt, smooth=False), mat("#5b3a24", "leather", round=6), cast=0.5,
            bump=fold(p, [(460, 452), (590, 446)], 2, 0.6) + fold(p, [(460, 470), (590, 464)], 2, 0.6))
    p.paint(p.poly([(540, 441), (568, 440), (569, 473), (541, 474)], smooth=False), mat(GOLD, "gold", round=4), cast=0.5)
    p.paint(p.poly([(546, 448), (563, 447), (563, 466), (547, 467)], smooth=False), mat("#4a2e1c", "leather", round=3), cast=0)
    for x in (480, 508, 582):
        rivet(p, (x, 458), 2.4, GOLD)
    return p.finish(line=1.8)


def warrior_cape():
    p = Part((110, 240, 580, 760), seed=15)
    outer = [(560, 282), (530, 270), (484, 272), (430, 290), (360, 318), (282, 360), (210, 424), (160, 492),
             (140, 552), (170, 604), (230, 650), (300, 688), (370, 712), (430, 716), (470, 690), (490, 620),
             (512, 500), (534, 400), (556, 320)]
    folds = [([(470, 300), (350, 450), (260, 640)], 18, -2.4), ([(440, 296), (300, 400), (190, 520)], 12, 2.0),
             ([(490, 320), (420, 490), (370, 700)], 16, 2.0), ([(510, 340), (470, 520), (440, 700)], 14, -2.0),
             ([(430, 320), (320, 490), (300, 670)], 16, 2.2), ([(450, 300), (360, 340), (230, 430)], 10, -1.6)]
    m = cloth(p, outer, "#1a2769", folds=folds, round_=30, cast=0)
    lining = p.poly([(140, 552), (170, 604), (230, 650), (300, 688), (370, 712), (430, 716), (432, 698), (370, 694),
                     (304, 670), (238, 632), (180, 586), (152, 546)], smooth=True)
    cloth(p, lining, "#3a4c98", round_=6, cast=0.3)
    trim(p, [(142, 550), (172, 602), (230, 648), (300, 686), (370, 710), (430, 714), (468, 692)], 3.4)
    trim(p, [(210, 426), (160, 492), (142, 550)], 3.0)
    em = p.polys(griffin((300, 500), 64, deg=-10))
    ring = np.clip(p.ellipse((300, 500), 82, 82) - p.ellipse((300, 500), 77, 77), 0, 1)
    emb = np.clip(np.maximum(em, ring) * m, 0, 1)
    p.paint(emb, mat("#c99c46", "gold", round=2.5, spec=0.6), cast=0.25, line=0.5)
    p.mult(C("#5a6aa4"), m * blur(p.poly([(530, 270), (570, 320), (520, 520), (470, 440)]), 20 * SS) * 0.7)
    return p.finish(line=1.8)


def pauldron(p, c, s, deg, back=False):
    """Layered shoulder guard centred at c."""
    lames = [(1.00, 0.95, 36), (0.84, 0.78, 44), (0.7, 0.62, 58)] if not back else [(1.0, 0.9, 36), (0.82, 0.7, 48)]
    for k0, k1, dy in reversed(lames):
        pts = arc_band((c[0], c[1] - dy * s * 0.2), 30 * s * k1, 44 * s * k0, 20, 175, sy=0.9, deg=deg)
        pts = [(x, y + dy * s * 0.55) for x, y in pts]
        plate(p, pts, cast=0.45, hgt=dome(p, (c[0], c[1] + dy * s * 0.3), 50 * s, 44 * s, k=0.9))
        edge = arc_band((c[0], c[1] - dy * s * 0.2), 42 * s * k0, 44 * s * k0, 25, 170, sy=0.9, deg=deg)
        trim(p, [(x, y + dy * s * 0.55) for x, y in edge[:len(edge) // 2]], 2.4 * s)
    top = ell_pts(c, 44 * s, 36 * s, deg=deg, n=40)
    plate(p, top, cast=0.5, hgt=dome(p, (c[0] - 6 * s, c[1] - 6 * s), 50 * s, 42 * s, deg=deg, k=1.0))
    trim(p, ell_pts(c, 43 * s, 35 * s, deg=deg, n=40, a0=-10, a1=190), 3.0 * s)
    if not back:
        p.paint(p.ellipse((c[0] + 4 * s, c[1] + 2 * s), 11 * s, 11 * s), mat(GOLD, "gold", round=6), cast=0.5)
        gem(p, (c[0] + 4 * s, c[1] + 2 * s), 6 * s, "#3b78e6")


SWORD_D = (math.cos(math.radians(26)), math.sin(math.radians(26)))


def warrior_arm(front=True):
    """(upper, lower) parts of an armoured arm, drawn in canvas px."""
    if front:
        sh, el, wr = U.fwd(574, 292), (608, 432), (688, 474)
        seed, s, pd = 20, 1.0, 0.9
        grip_u = (-SWORD_D[1] * 0.2 + 0.25, -0.97)
    else:
        sh, el, wr = U.fwd(466, 296), (418, 402), (372, 464)
        seed, s, pd = 30, 0.9, 0.78
        grip_u = (0.97, 0.25)
    box_u = (min(sh[0], el[0]) - 70, sh[1] - 70, max(sh[0], el[0]) + 70, el[1] + 50)
    box_l = (min(el[0], wr[0]) - 60, el[1] - 50, max(el[0], wr[0]) + 70, wr[1] + 70)
    pu = Part(box_u, seed=seed)
    pu.paint(pu.tube([sh, el], [48 * s, 40 * s]), mat("#22306e", "cloth", round=14), cast=0)
    plate(pu, quad(along(sh, el, 0.35), along(sh, el, 0.9), 44 * s, 38 * s), hgt=cyl(pu, sh, el, 25 * s))
    trim(pu, [along(sh, el, 0.9, 19 * s), along(sh, el, 0.9, -19 * s)], 2.2)
    ang = math.degrees(math.atan2(el[1] - sh[1], el[0] - sh[0]))
    fan = [(el[0] - 10 * s, el[1] - 8 * s), (el[0] - 30 * s, el[1] + 2 * s), (el[0] - 14 * s, el[1] + 16 * s)]
    plate(pu, rot(fan, el, ang - 70), round_=6)
    plate(pu, ell_pts(el, 24 * s, 20 * s, deg=ang, n=30), hgt=dome(pu, el, 26 * s, 22 * s, deg=ang))
    pu.paint(pu.ellipse((el[0] + 3, el[1]), 5 * s, 5 * s), mat(GOLD, "gold", round=3), cast=0.4)
    pauldron(pu, (sh[0] + (2 if front else -2), sh[1] - 6), pd, -24 if front else 20, back=not front)
    upper = pu.finish(line=1.8)
    pl = Part(box_l, seed=seed + 1)
    u = unit(el, wr)
    pl.paint(pl.tube([along(el, wr, -0.16), wr], [40 * s, 34 * s]), mat("#22306e", "cloth", round=12), cast=0)
    vb = quad(along(el, wr, 0.2), along(el, wr, 1.0), 40 * s, 38 * s)
    plate(pl, vb, hgt=cyl(pl, el, wr, 23 * s) + cyl(pl, along(el, wr, 0.3, 6), along(el, wr, 0.9, 6), 6, k=0.4))
    trim(pl, [along(el, wr, 1.0, 20 * s), along(el, wr, 1.0, -20 * s)], 3.0)
    trim(pl, [along(el, wr, 0.2, 19 * s), along(el, wr, 0.2, -19 * s)], 2.2)
    hc = fist(pl, wr, u, grip_u, 34 * s, plate=SILVER)
    lower = pl.finish(line=1.8)
    return upper, lower, sh, el, wr, hc


def warrior_leg(front=True):
    if front:
        hip, knee, ank = (505, 566), (622, 724), (642, 904)
        toe, heel = (738, 969), (614, 972)
        seed = 40
    else:
        hip, knee, ank = (440, 572), (352, 746), (256, 902)
        toe, heel = (306, 971), (210, 950)
        seed = 50
    box_u = (min(hip[0], knee[0]) - 80, hip[1] - 90, max(hip[0], knee[0]) + 80, knee[1] + 60)
    box_l = (min(heel[0], knee[0]) - 60, knee[1] - 60, max(toe[0], knee[0]) + 30, 1000)
    pu = Part(box_u, seed=seed)
    top = (hip[0] + 6, hip[1] - 50)
    pu.paint(pu.tube([top, along(top, knee, 0.5), knee], [86, 74, 56]), mat("#2a2d40", "cloth", round=18), cast=0,
             bump=fold(pu, [along(top, knee, 0.2, -20), along(top, knee, 0.8, -14)], 8, -1.6)
             + fold(pu, [along(top, knee, 0.5, 10), along(top, knee, 0.9, -6)], 6, -1.2))
    cu = [along(top, knee, 0.46, 34), along(top, knee, 0.42, 4), along(top, knee, 0.9, -8), along(top, knee, 0.92, 22),
          along(top, knee, 0.7, 34)]
    plate(pu, cu, hgt=cyl(pu, along(top, knee, 0, 14), along(top, knee, 1, 8), 30))
    trim(pu, [along(top, knee, 0.7, 34), along(top, knee, 0.46, 34), along(top, knee, 0.42, 4)], 2.4)
    ang = math.degrees(math.atan2(knee[1] - top[1], knee[0] - top[0])) - 90
    wing = [(knee[0] + 14, knee[1] - 16), (knee[0] + 40, knee[1] - 4), (knee[0] + 22, knee[1] + 18)]
    plate(pu, rot(wing, knee, ang * 0.5), round_=6)
    plate(pu, ell_pts((knee[0] + 2, knee[1] + 2), 29, 25, deg=ang, n=36),
          hgt=dome(pu, (knee[0] - 2, knee[1]), 31, 27, deg=ang) + dome(pu, knee, 12, 10, k=0.6))
    trim(pu, ell_pts((knee[0] + 2, knee[1] + 2), 28, 24, deg=ang, n=36, a0=200, a1=340), 2.4)
    pu.paint(pu.ellipse(knee, 5, 5), mat(GOLD, "gold", round=3), cast=0.4)
    upper = pu.finish(line=1.8)
    pl = Part(box_l, seed=seed + 1)
    kt = (knee[0], knee[1] - 24)
    calf = along(kt, ank, 0.35, -8)
    pl.paint(pl.tube([kt, calf, ank], [54, 60, 40]), mat("#2a2d40", "cloth", round=14), cast=0)
    gr = [along(kt, ank, 0.12, 28), along(kt, ank, 0.4, 30), along(kt, ank, 0.98, 22), along(kt, ank, 0.98, -10),
          along(kt, ank, 0.4, -14), along(kt, ank, 0.12, -12)]
    plate(pl, gr, hgt=cyl(pl, along(kt, ank, 0, 8), along(kt, ank, 1, 6), 30) + cyl(pl, along(kt, ank, 0.2, 12), along(kt, ank, 0.95, 8), 7, k=0.5))
    trim(pl, [along(kt, ank, 0.14, -12), along(kt, ank, 0.14, 28)], 2.4)
    trim(pl, [along(kt, ank, 0.14, 28), along(kt, ank, 0.4, 30), along(kt, ank, 0.97, 22)], 1.8)
    foot = [(ank[0] - 26, ank[1] - 14), (ank[0] + 22, ank[1] - 18), (ank[0] + 44, ank[1] + 24), (toe[0] - 10, toe[1] - 24),
            (toe[0] + 2, toe[1] - 6), toe, (heel[0] + 4, heel[1]), (heel[0] - 2, heel[1] - 30)]
    plate(pl, foot, hgt=dome(pl, ((ank[0] + toe[0]) / 2, ank[1] + 40), (toe[0] - heel[0]) * 0.6, 50, k=0.8),
          bump=fold(pl, [(ank[0] + 30, ank[1] + 16), (ank[0] + 14, ank[1] + 50)], 4, -1.4)
          + fold(pl, [(ank[0] + 50, ank[1] + 30), (ank[0] + 34, ank[1] + 60)], 4, -1.4))
    sole = [(heel[0], heel[1] - 8), (toe[0], toe[1] - 8), toe, (heel[0] + 2, heel[1])]
    pl.paint(pl.poly(sole, smooth=False), mat("#3a2a20", "leather", round=3), cast=0)
    trim(pl, [(ank[0] - 26, ank[1] - 12), (ank[0] + 22, ank[1] - 16)], 2.4)
    lower = pl.finish(line=1.8)
    return upper, lower, hip, knee, ank


def warrior_sword(hand):
    d = SWORD_D
    box = (560, 380, 1024, 680)
    p = Part(box, seed=60)
    tip = sword(p, hand, d, blade_len=292, blade_w=28)
    img = p.finish(line=1.2)
    fx = Part(box, seed=61)
    X, Y = fx.grid()
    g = (tip[0] - d[0] * 80, tip[1] - d[1] * 80)
    dd = np.sqrt((X - g[0]) ** 2 + (Y - g[1]) ** 2)
    star = np.exp(-dd / 5) + np.exp(-np.abs(Y - g[1]) / 1.4) * np.exp(-np.abs(X - g[0]) / 36) * 0.8 \
        + np.exp(-np.abs(X - g[0]) / 1.4) * np.exp(-np.abs(Y - g[1]) / 26) * 0.8
    fx.over(C("#fff8e8"), np.clip(star, 0, 1))
    return img, fx.image(), d


def build_rig(rig_id, canvas, feet, kind, parts, flat, flat_size=512):
    """parts: list of (name, (img, off), parent, role, pivot, z[, blend])."""
    rb = rig.RigBuilder(rig_id, canvas, feet=feet, facing="right", kind=kind)
    for entry in parts:
        name, io, parent, role, pivot, z = entry[:6]
        blend = entry[6] if len(entry) > 6 else "normal"
        rb.add(name, layer(canvas, io), parent=parent, role=role, pivot=pivot, z=z, blend=blend)
    rb.save(flat=flat, flat_size=flat_size)
    return rb


def warrior():
    global GRADE
    GRADE = (520, 990, 0.3)
    t = time.time()
    fu, fl, fsh, fel, fwr, fhc = warrior_arm(True)
    bu, bl, bsh, bel, bwr, bhc = warrior_arm(False)
    lfu, lfl, fhip, fknee, _ = warrior_leg(True)
    lbu, lbl, bhip, bknee, _ = warrior_leg(False)
    sw, swfx, d = warrior_sword(fhc)
    parts = [
        ("hips", warrior_root(), "", "root", UR.fwd(520, 480), 12),
        ("torso", warrior_torso(), "hips", "torso", U.fwd(522, 456), 11),
        ("cape", warrior_cape(), "torso", "cape", (520, 292), 1),
        ("head", warrior_head(), "torso", "head", HEAD_PIVOT, 18),
        ("hair", warrior_hair(), "head", "hair", WF(-24, -10), 16),
        ("arm_back_upper", bu, "torso", "arm_back_upper", bsh, 4),
        ("arm_back_lower", bl, "arm_back_upper", "arm_back_lower", bel, 3),
        ("arm_front_upper", fu, "torso", "arm_front_upper", fsh, 21),
        ("arm_front_lower", fl, "arm_front_upper", "arm_front_lower", fel, 20),
        ("sword", sw, "arm_front_lower", "weapon", fhc, 19),
        ("sword_glint", swfx, "sword", "fx", fhc, 23, "add"),
        ("leg_back_upper", lbu, "hips", "leg_back_upper", bhip, 6),
        ("leg_back_lower", lbl, "leg_back_upper", "leg_back_lower", bknee, 5),
        ("leg_front_upper", lfu, "hips", "leg_front_upper", fhip, 9),
        ("leg_front_lower", lfl, "leg_front_upper", "leg_front_lower", fknee, 8),
    ]
    build_rig("warrior", HERO, (470, 972), "humanoid", parts, "sprites/player/warrior.png")
    print(f"warrior {time.time() - t:.1f}s")


RIGS = {
    "warrior": warrior,
}


def main(argv):
    ids = argv or list(RIGS)
    for rid in ids:
        RIGS[rid]()


if __name__ == "__main__":
    main(sys.argv[1:])

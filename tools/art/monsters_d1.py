"""Dungeon 1 (the Rotten Cellar) monsters as painted cut-out rigs (docs/art: m8 "like the reference, alive").

    python3 tools/art/monsters_d1.py                 # all five
    python3 tools/art/monsters_d1.py mimic bone_king # only these

Writes assets/rigs/<id>/ (part PNGs + rig.json, see rig.py) and the still picture the menus use,
assets/sprites/enemies/<id>.png (512 px; the boss 768 px). Every monster faces left.

The look is painted and semi-realistic rather than cel-shaded, so this module carries its own small
renderer instead of painter.py:

* A part is painted at 2x on float buffers: albedo, coverage, surface slope (a normal map), gloss,
  emission, ambient occlusion and an ink amount.
* Every shape "inflates" (its coverage is blurred into a rounded dome), so shading comes from real
  normals: a warm key light from the upper left, a cool hemispheric fill, a strong rim on the far
  (right) edge, Blinn specular on metal, bone and wet things, and coloured point lights that spill
  from glowing things (soul fire, lamps) onto nearby surfaces.
* Surface detail (folds, cracks, fur strands, wood grain, scratches) is mostly slope, so it catches
  the light instead of being drawn on; curvature darkens the creases and lifts the ridges.
* Shapes cast soft contact shadows onto what they are painted over; the ink line is thin,
  colour-matched and fades where the key light hits.
* Glows (eyes, flames, soul fire) are painted as emission in the part and get an extra additive "fx"
  part (blend "add") that the game pulses; the flat picture includes them.
"""
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

import rig  # noqa: E402

SS = 2          # supersampling of every part
F32 = np.float32


# =============================================================== small maths

def hx(s):
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def _box1(a, r, axis):
    r = int(r)
    if r < 1:
        return a
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=F32)
    n = 2 * r + 1
    if axis == 0:
        return (c[n:] - c[:-n]) / n
    return (c[:, n:] - c[:, :-n]) / n


def box(a, r):
    return _box1(_box1(a, r, 0), r, 1)


def gblur(a, sigma):
    """Near-Gaussian blur: three box passes (zero outside the array)."""
    if sigma < 0.4:
        return a
    w = math.sqrt(4 * sigma * sigma + 1)
    r = max(1, int(round((w - 1) / 2)))
    for _ in range(3):
        a = box(a, r)
    return a


def shift(a, dx, dy):
    dx, dy = int(round(dx)), int(round(dy))
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = a[ys0:ys1, xs0:xs1]
    return out


# =============================================================== geometry (canvas coordinates)

def cr(pts, closed=False, n=10):
    """Catmull-Rom spline through pts."""
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
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def ell(cx, cy, rx, ry, rot=0.0, a0=0.0, a1=360.0, n=72):
    r = math.radians(rot)
    cs, sn = math.cos(r), math.sin(r)
    out = []
    for i in range(n + 1):
        t = math.radians(a0 + (a1 - a0) * i / n)
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * cs - y * sn, cy + x * sn + y * cs))
    return out


def plen(path):
    return sum(math.dist(path[i], path[i + 1]) for i in range(len(path) - 1))


def at(path, t):
    """Point and unit tangent at fraction t of a polyline's length."""
    total = plen(path)
    d = t * total
    for i in range(len(path) - 1):
        seg = math.dist(path[i], path[i + 1])
        if d <= seg or i == len(path) - 2:
            u = 0 if seg == 0 else min(1.0, d / seg)
            x = path[i][0] + (path[i + 1][0] - path[i][0]) * u
            y = path[i][1] + (path[i + 1][1] - path[i][1]) * u
            tx, ty = path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]
            L = math.hypot(tx, ty) or 1
            return (x, y), (tx / L, ty / L)
        d -= seg
    return path[-1], (1, 0)


def taper(path, w0, w1=None, smooth=True, n=8):
    """Polygon of a stroke along path whose width goes w0 -> w1 (or follows a list of widths)."""
    pts = cr(path, n=n) if smooth and len(path) > 2 else [tuple(map(float, p)) for p in path]
    m = len(pts)
    if isinstance(w0, (list, tuple)):
        ws = w0
        wl = [ws[min(len(ws) - 1, int(i * (len(ws) - 1) / max(1, m - 1)))] for i in range(m)]
        # interpolate properly
        wl = []
        for i in range(m):
            f = i * (len(ws) - 1) / max(1, m - 1)
            k = min(len(ws) - 2, int(f))
            wl.append(ws[k] + (ws[k + 1] - ws[k]) * (f - k))
    else:
        w1 = w0 if w1 is None else w1
        wl = [w0 + (w1 - w0) * i / max(1, m - 1) for i in range(m)]
    left, right = [], []
    for i in range(m):
        a = pts[max(0, i - 1)]
        b = pts[min(m - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        h = wl[i] / 2
        left.append((pts[i][0] + nx * h, pts[i][1] + ny * h))
        right.append((pts[i][0] - nx * h, pts[i][1] - ny * h))
    return left + right[::-1]


def rot_pts(pts, cx, cy, deg):
    r = math.radians(deg)
    cs, sn = math.cos(r), math.sin(r)
    return [(cx + (x - cx) * cs - (y - cy) * sn, cy + (x - cx) * sn + (y - cy) * cs) for x, y in pts]


def quad(q, u, v):
    """Bilinear point in quad q = (top-left, top-right, bottom-right, bottom-left)."""
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = q
    tx, ty = ax + (bx - ax) * u, ay + (by - ay) * u
    bx2, by2 = dx + (cx - dx) * u, dy + (cy - dy) * u
    return (tx + (bx2 - tx) * v, ty + (by2 - ty) * v)


def qsub(q, u0, v0, u1, v1):
    return [quad(q, u0, v0), quad(q, u1, v0), quad(q, u1, v1), quad(q, u0, v1)]


# =============================================================== masks (supersampled, windowed)

class M:
    """A coverage mask: float array a (0..1) whose top-left sits at (x, y) in supersampled pixels."""
    __slots__ = ("a", "x", "y")

    def __init__(self, a, x, y):
        self.a = a.astype(F32, copy=False)
        self.x, self.y = int(x), int(y)

    @property
    def box(self):
        return (self.x, self.y, self.x + self.a.shape[1], self.y + self.a.shape[0])

    def crop(self, b):
        x0, y0, x1, y1 = b
        out = np.zeros((y1 - y0, x1 - x0), F32)
        sx0, sy0, sx1, sy1 = self.box
        ix0, iy0, ix1, iy1 = max(x0, sx0), max(y0, sy0), min(x1, sx1), min(y1, sy1)
        if ix1 > ix0 and iy1 > iy0:
            out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] = self.a[iy0 - sy0:iy1 - sy0, ix0 - sx0:ix1 - sx0]
        return out

    def __or__(self, o):
        b = _ubox(self.box, o.box)
        return M(np.maximum(self.crop(b), o.crop(b)), b[0], b[1])

    def __sub__(self, o):
        return M(self.a * (1 - o.crop(self.box)), self.x, self.y)

    def __and__(self, o):
        return M(self.a * o.crop(self.box), self.x, self.y)

    def __mul__(self, k):
        return M(self.a * k, self.x, self.y)

    def padded(self, r):
        r = int(r)
        x0, y0, x1, y1 = self.box
        b = (x0 - r, y0 - r, x1 + r, y1 + r)
        return M(self.crop(b), b[0], b[1])

    def blur(self, s):
        """s in canvas px."""
        m = self.padded(int(s * SS * 3) + 2)
        return M(gblur(m.a, s * SS), m.x, m.y)

    def grow(self, d):
        """Dilate (d > 0) or erode (d < 0) by d canvas px."""
        r = int(abs(d) * SS) + 3
        m = self.padded(r + 2)
        sd = (box(m.a, r) - 0.5) * (2 * r + 1)
        return M(clamp01(sd + d * SS + 0.5), m.x, m.y)

    def shift(self, dx, dy):
        return M(self.a, self.x + dx * SS, self.y + dy * SS)

    def inv_in(self, b):
        return M(1 - self.crop(b), b[0], b[1])

    def area(self):
        return float(self.a.sum())


def _ubox(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _raster(polys, soft=0.6):
    """Masks one or more polygons (canvas coordinates)."""
    allp = [p for poly in polys for p in poly]
    xs = [p[0] * SS for p in allp]
    ys = [p[1] * SS for p in allp]
    x0, y0 = int(math.floor(min(xs))) - 3, int(math.floor(min(ys))) - 3
    x1, y1 = int(math.ceil(max(xs))) + 4, int(math.ceil(max(ys))) + 4
    im = Image.new("L", (x1 - x0, y1 - y0), 0)
    d = ImageDraw.Draw(im)
    for poly in polys:
        d.polygon([(x * SS - x0, y * SS - y0) for x, y in poly], fill=255)
    a = np.asarray(im, F32) / 255.0
    if soft:
        a = gblur(a, soft)
    return M(a, x0, y0)


def poly(pts, smooth=False, n=8):
    return _raster([cr(pts, closed=True, n=n) if smooth else pts])


def ellipse(cx, cy, rx, ry, rot=0.0):
    return _raster([ell(cx, cy, rx, ry, rot, n=max(24, int((rx + ry) * 0.6)))])


def circle(cx, cy, r):
    return ellipse(cx, cy, r, r)


def tube(path, w0, w1=None, smooth=True, caps=True):
    """A stroke with rounded ends."""
    pts = cr(path, n=8) if smooth and len(path) > 2 else path
    polys = [taper(pts, w0, w1, smooth=False)]
    if caps:
        ws = w0 if isinstance(w0, (list, tuple)) else [w0, w0 if w1 is None else w1]
        polys.append(ell(pts[0][0], pts[0][1], ws[0] / 2, ws[0] / 2, n=32))
        polys.append(ell(pts[-1][0], pts[-1][1], ws[-1] / 2, ws[-1] / 2, n=32))
    return _raster(polys)


def union(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = out | m
    return out


def inner_dist(a):
    """Approximate distance (supersampled px) from each covered pixel to the mask edge: an octagonal
    erosion count on a low-res copy, smoothed and scaled back up."""
    h, w = a.shape
    f = max(1, int(min(h, w) / 70))
    sw, sh = max(3, w // f), max(3, h // f)
    small = np.asarray(Image.fromarray(a, "F").resize((sw, sh), Image.BILINEAR), F32)
    cur = small > 0.5
    d = np.zeros(small.shape, F32)
    i = 0
    while cur.any() and i < 600:
        d += cur
        n = cur.copy()
        n[1:, :] &= cur[:-1, :]
        n[:-1, :] &= cur[1:, :]
        n[:, 1:] &= cur[:, :-1]
        n[:, :-1] &= cur[:, 1:]
        n[0, :] = n[-1, :] = False
        n[:, 0] = n[:, -1] = False
        if i % 2:
            n[1:, 1:] &= cur[:-1, :-1]
            n[:-1, :-1] &= cur[1:, 1:]
            n[1:, :-1] &= cur[:-1, 1:]
            n[:-1, 1:] &= cur[1:, :-1]
        cur = n
        i += 1
    d = np.maximum(d - 0.5, 0)
    d = gblur(d, 0.8)
    big = np.asarray(Image.fromarray(d, "F").resize((sw * f, sh * f), Image.BICUBIC), F32) * f
    out = np.zeros((h, w), F32)
    out[:min(h, sh * f), :min(w, sw * f)] = big[:h, :w]
    if f > 1:
        out = gblur(out, f * 0.5)
    return np.maximum(out, 0) * np.minimum(1, a * 1.5)


# =============================================================== noise

_NOISE = {}


def _fbm(shape, cells, seed, weights=None):
    rng = np.random.default_rng(seed)
    h, w = shape
    out = np.zeros(shape, F32)
    tot = 0
    for i, c in enumerate(cells):
        wgt = weights[i] if weights else 1.0 / (1 + i * 0.6)
        g = rng.random((max(2, h // c + 3), max(2, w // c + 3))).astype(F32)
        im = Image.fromarray(g, "F").resize(((g.shape[1]) * c, (g.shape[0]) * c), Image.BICUBIC)
        a = np.asarray(im, F32)
        ox, oy = rng.integers(0, c), rng.integers(0, c)
        out += wgt * a[oy:oy + h, ox:ox + w]
        tot += wgt
    out /= tot
    lo, hi = np.percentile(out[::7, ::7], (1, 99))
    return clamp01((out - lo) / (hi - lo + 1e-6))


def noise(kind, shape):
    """Cached full-canvas noise fields (supersampled size)."""
    key = (kind, shape)
    if key in _NOISE:
        return _NOISE[key]
    h, w = shape
    if kind == "fbm":        # soft blotches
        f = _fbm(shape, [160, 80, 40, 20, 10], 11)
    elif kind == "grain":    # brush grain
        f = _fbm(shape, [8, 4, 2], 12, [0.5, 1.0, 0.8])
    elif kind == "pits":     # stone / bone pitting
        f = _fbm(shape, [48, 20, 8, 4], 13, [1.0, 0.9, 0.8, 0.6])
    elif kind == "large":
        f = _fbm(shape, [400, 200, 100], 14)
    elif kind == "ridge":    # cracks / veins
        f = _fbm(shape, [120, 60, 30, 14], 15)
        f = 1 - np.abs(f - 0.5) * 2
        f = f ** 6
    elif kind.startswith("streak"):  # streak<angle>: anisotropic strands (fur, grain, brushed metal)
        ang = int(kind[6:])
        n = int(math.hypot(h, w)) + 8
        rng = np.random.default_rng(16 + ang)
        acc = np.zeros((n, n), F32)
        for cx, cy, wt in ((3, 90, 1.0), (2, 40, 0.8), (1, 16, 0.5)):
            g = rng.random((n // cy + 3, n // cx + 3)).astype(F32)
            im = Image.fromarray(g, "F").resize((g.shape[1] * cx, g.shape[0] * cy), Image.BICUBIC)
            acc += wt * np.asarray(im, F32)[:n, :n]
        im = Image.fromarray(acc, "F").rotate(-ang + 90, resample=Image.BILINEAR)
        a = np.asarray(im, F32)
        oy, ox = (n - h) // 2, (n - w) // 2
        f = a[oy:oy + h, ox:ox + w]
        lo, hi = np.percentile(f[::7, ::7], (1, 99))
        f = clamp01((f - lo) / (hi - lo + 1e-6))
    else:
        raise ValueError(kind)
    _NOISE[key] = f.astype(F32)
    return _NOISE[key]


def kuwahara(col, r):
    """Painterly smoothing: each pixel takes the mean of the calmest of four quadrant windows."""
    lum = col.mean(-1)
    h = r // 2 + 1
    best = None
    bvar = None
    for dx, dy in ((-h, -h), (h, -h), (-h, h), (h, h)):
        mu = np.stack([shift(box(col[..., i], h), -dx, -dy) for i in range(3)], -1)
        ml = shift(box(lum, h), -dx, -dy)
        m2 = shift(box(lum * lum, h), -dx, -dy)
        var = m2 - ml * ml
        if best is None:
            best, bvar = mu, var
        else:
            sel = var < bvar
            best = np.where(sel[..., None], mu, best)
            bvar = np.where(sel, var, bvar)
    return best


# =============================================================== the renderer

class Look:
    """Lighting shared by every part of one rig."""

    def __init__(self, key=(1.0, 0.9, 0.76), key_dir=(-0.62, -0.72, 0.62), sky=(0.34, 0.38, 0.5),
                 ground=(0.16, 0.12, 0.13), rim=(0.55, 0.78, 1.0), rim_k=1.0, lights=(), line=(0.10, 0.07, 0.09),
                 haze=(0.10, 0.11, 0.16), falloff=None):
        L = np.array(key_dir, F32)
        self.key_dir = L / np.linalg.norm(L)
        self.key = np.array(key, F32)
        self.sky, self.ground = np.array(sky, F32), np.array(ground, F32)
        self.rim, self.rim_k = np.array(rim, F32), rim_k
        self.lights = list(lights)    # (x, y, z, (r, g, b), radius, strength) in canvas px
        self.line = np.array(line, F32)
        self.haze = np.array(haze, F32)
        self.falloff = falloff  # (cx, cy, radius, k): the figure darkens away from the key light


class Part:
    """One rig part, painted at SS x on float buffers the size of the canvas (touched lazily)."""

    def __init__(self, W, H, look, depth=0.0, lights=()):
        self.W, self.H = W, H
        self.w, self.h = W * SS, H * SS
        self.look = look
        self.depth = depth
        self.lights = list(lights)
        z = lambda *c: np.zeros((self.h, self.w) + c, F32)  # noqa: E731
        self.C = z(3)
        self.A = z()
        self.NX, self.NY = z(), z()
        self.S = z()      # specular strength
        self.G = z()      # glossiness 0..1
        self.E = z(3)     # emission
        self.O = z()      # occlusion (0 = none)
        self.L = z()      # ink amount
        self.MT = z()     # metalness (reflects a dim room: bright above, dark horizon band)
        self.U = z()      # "unlit" (0 = fully lit, 1 = pure albedo) for glowing things
        self.bb = None
        self.sss = 0.0       # terminator warmth (skin, fur, cloth)
        self.paint_r = 0     # painterly smoothing radius (supersampled px), 0 = off

    # ------------------------------------------------ helpers
    def _win(self, m, margin):
        x0, y0, x1, y1 = m.box
        r = int(margin)
        b = (max(0, x0 - r), max(0, y0 - r), min(self.w, x1 + r), min(self.h, y1 + r))
        if b[2] <= b[0] or b[3] <= b[1]:
            return None
        return b

    def _touch(self, b):
        self.bb = b if self.bb is None else _ubox(self.bb, b)

    def _colarr(self, col, b, a, grad, tex, tex_amt, var, seed_off):
        x0, y0, x1, y1 = b
        hh, ww = y1 - y0, x1 - x0
        col = np.asarray(col, F32)
        if grad is not None:
            # grad = (col2, (xa, ya), (xb, yb)): linear ramp in canvas coordinates
            c2, pa, pb = grad
            ys, xs = np.mgrid[y0:y1, x0:x1].astype(F32) / SS
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            t = clamp01(((xs - pa[0]) * dx + (ys - pa[1]) * dy) / (dx * dx + dy * dy + 1e-6))
            t = t * t * (3 - 2 * t)
            arr = col[None, None, :] * (1 - t[..., None]) + np.asarray(c2, F32)[None, None, :] * t[..., None]
        else:
            arr = np.broadcast_to(col, (hh, ww, 3)).copy()
        if var:
            f = noise("large", (self.h, self.w))[y0:y1, x0:x1]
            g = noise("fbm", (self.h, self.w))[y0:y1, x0:x1]
            arr = arr * (1 + var * np.stack([f - 0.5, (g - 0.5) * 0.6, (0.5 - f) * 0.8], -1) * 1.2)
        if tex:
            t = noise(tex, (self.h, self.w))[y0:y1, x0:x1]
            arr = arr * (1 + tex_amt * (t[..., None] - 0.5) * 1.6)
        return np.clip(arr, 0, 1.5)

    # ------------------------------------------------ painting
    def paint(self, m, col, mode="over", bulge=0.55, rnd=None, tex=None, tex_amt=0.25, bump=0.0, bump_tex=None,
              spec=0.12, gloss=0.25, emit=None, unlit=0.0, line=0.55, lw=1.6, shadow=0.4, sh_off=(5, 7), sh_blur=6,
              op=1.0, grad=None, var=0.12, clip=None, flat=0.0, metal=0.0):
        """Paints mask m.
        mode "over": a new object on top (replaces the surface slope, casts a contact shadow, gets a line);
        "on": a raised/sunk detail on the surface below (clipped to it, slopes add up);
        "tint": colour only; "bump": slope only (folds, dents, cracks).
        bulge: how round (negative sinks); rnd: roundness radius in canvas px (auto from thickness)."""
        if m is None:
            return None
        if clip is not None:
            m = m & clip
        rnd_given = rnd is not None
        margin = int((abs(sh_off[0]) + abs(sh_off[1]) + sh_blur * 3) * SS if shadow else 0) + 6
        b = self._win(m, margin)
        if b is None:
            return m
        x0, y0, x1, y1 = b
        sl = (slice(y0, y1), slice(x0, x1))
        raw = m.crop(b)
        a = raw * op
        if mode in ("on", "tint", "bump"):
            a = a * self.A[sl]
        if a.max() <= 0.002:
            return m
        self._touch(b)
        a3 = a[..., None]
        if mode != "bump":
            arr = self._colarr(col, b, a, grad, tex, tex_amt, var, 0)
            self.C[sl] = self.C[sl] * (1 - a3) + arr * a3
            em = np.zeros(3, F32) if emit is None else np.asarray(emit, F32)
            self.E[sl] = self.E[sl] * (1 - a3) + em[None, None, :] * a3
            self.U[sl] = self.U[sl] * (1 - a) + unlit * a
        if mode == "tint":
            return m
        # slope of this shape's dome (plus bump texture)
        hgt = None
        if bulge:
            d = inner_dist(raw)
            R = rnd * SS if rnd_given else max(float(d.max()), 1.0)
            t = clamp01(d / R)
            hgt = np.sqrt(clamp01(1 - (1 - t) ** 2)) * (R * bulge)
        if bump and (bump_tex or tex):
            t = noise(bump_tex or tex, (self.h, self.w))[sl]
            hb = (t - 0.5) * bump * SS * 3 * (raw if mode == "over" else 1)
            hgt = hb if hgt is None else hgt + hb
        if hgt is not None:
            gy, gx = np.gradient(hgt)
        else:
            gx = gy = np.zeros_like(a)
        if mode == "over":
            if shadow:
                s = gblur(shift(raw, sh_off[0] * SS, sh_off[1] * SS), sh_blur * SS)
                self.O[sl] = np.maximum(self.O[sl], shadow * s * self.A[sl]) * (1 - a) + 0 * a
            else:
                self.O[sl] = self.O[sl] * (1 - a)
            self.NX[sl] = self.NX[sl] * (1 - a) + gx * a
            self.NY[sl] = self.NY[sl] * (1 - a) + gy * a
            self.A[sl] = self.A[sl] + a * (1 - self.A[sl])
            self.S[sl] = self.S[sl] * (1 - a) + spec * a
            self.G[sl] = self.G[sl] * (1 - a) + gloss * a
            self.MT[sl] = self.MT[sl] * (1 - a) + metal * a
            if line:
                R = max(2, int(lw * SS * 2))
                sd = (box(raw, R) - 0.5) * (2 * R + 1)
                e = clamp01(1 - sd / (lw * SS)) * a
                self.L[sl] = self.L[sl] * (1 - a) + e * line
            else:
                self.L[sl] = self.L[sl] * (1 - a)
        else:  # on / bump
            self.NX[sl] += gx * a
            self.NY[sl] += gy * a
            if mode == "on":
                self.S[sl] = self.S[sl] * (1 - a) + spec * a
                self.G[sl] = self.G[sl] * (1 - a) + gloss * a
                self.MT[sl] = self.MT[sl] * (1 - a) + metal * a
                if shadow:
                    s = gblur(shift(raw, sh_off[0] * SS * 0.5, sh_off[1] * SS * 0.5), sh_blur * SS * 0.5)
                    self.O[sl] = np.maximum(self.O[sl] * (1 - a), shadow * s * (1 - raw) * self.A[sl])
                else:
                    self.O[sl] = self.O[sl] * (1 - a)
                if line:
                    R = max(2, int(lw * SS * 2))
                    sd = (box(raw, R) - 0.5) * (2 * R + 1)
                    e = clamp01(1 - sd / (lw * SS)) * a
                    self.L[sl] = np.maximum(self.L[sl] * (1 - a), e * line)
                else:
                    self.L[sl] = self.L[sl] * (1 - a)
        return m

    def fold(self, path, w, depth=0.8, w1=None, clip=None):
        """A crease (depth > 0 sinks, < 0 raises a ridge) along path."""
        m = tube(path, w, w1 if w1 is not None else w * 0.3)
        return self.paint(m, None, mode="bump", bulge=-depth, clip=clip)

    def occlude(self, m, k=0.5):
        """Extra soft darkening (ambient occlusion) under m."""
        b = self._win(m, 4)
        if b is None:
            return
        sl = (slice(b[1], b[3]), slice(b[0], b[2]))
        self.O[sl] = np.maximum(self.O[sl], m.crop(b) * k * self.A[sl])

    def glow_on(self, m, col, k=1.0):
        """Adds emission inside m (lava cracks, lit runes, glowing eyes)."""
        b = self._win(m, 2)
        if b is None:
            return
        sl = (slice(b[1], b[3]), slice(b[0], b[2]))
        a = m.crop(b)[..., None] * self.A[sl][..., None]
        self.E[sl] = self.E[sl] + np.asarray(col, F32)[None, None, :] * a * k
        self._touch(b)

    def strokes(self, region, angle, length, width, n, cols, seed=1, jitter=25, bump=0.4, alpha=0.8,
                curl=0.0, taper_to=0.15, flow=None):
        """Short tapered paint strokes scattered in region (fur, hair, straw): colours in cols."""
        rng = random.Random(seed)
        x0, y0, x1, y1 = region.box
        ys, xs = np.nonzero(region.a > 0.5)
        if len(xs) == 0:
            return
        layers = [Image.new("L", (x1 - x0, y1 - y0), 0) for _ in cols]
        draws = [ImageDraw.Draw(im) for im in layers]
        for _ in range(n):
            i = rng.randrange(len(xs))
            px, py = (xs[i] + x0) / SS, (ys[i] + y0) / SS
            ang = flow(px, py) if flow else angle
            ang = math.radians(ang + rng.uniform(-jitter, jitter))
            L = length * rng.uniform(0.6, 1.2)
            c1 = curl * rng.uniform(0.3, 1.0) * L
            p0 = (px, py)
            p2 = (px + math.cos(ang) * L, py + math.sin(ang) * L)
            p1 = ((p0[0] + p2[0]) / 2 - math.sin(ang) * c1, (p0[1] + p2[1]) / 2 + math.cos(ang) * c1)
            pts = taper([p0, p1, p2], width * rng.uniform(0.7, 1.2), width * taper_to, n=4)
            k = rng.randrange(len(cols))
            draws[k].polygon([(x * SS - x0, y * SS - y0) for x, y in pts], fill=255)
        for im, col in zip(layers, cols):
            a = gblur(np.asarray(im, F32) / 255.0, 0.6) * region.a
            mm = M(a, x0, y0)
            self.paint(mm, col, mode="on", bulge=bump, rnd=width * 0.6, line=0, shadow=0, op=alpha, var=0,
                       spec=0.05)

    def fringe(self, m, col, angle, n, length, width, seed=1, outward=0.3, flow=None, bulge=0.5, jitter=18,
               band=(0.25, 0.75), line=0.0):
        """Tufts of fur/hair/rags breaking the silhouette of m: strokes start inside the edge and point
        outward, bent toward the flow angle."""
        rng = random.Random(seed)
        mb = m.blur(3)
        a = mb.a
        gy, gx = np.gradient(a)
        ys, xs = np.nonzero((a > band[0]) & (a < band[1]))
        if len(xs) == 0:
            return
        x0, y0, x1, y1 = mb.box
        pad = int((length + width) * SS) + 4
        im = Image.new("L", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 0)
        d = ImageDraw.Draw(im)
        for _ in range(n):
            i = rng.randrange(len(xs))
            px, py = (xs[i] + x0) / SS, (ys[i] + y0) / SS
            ox, oy = -gx[ys[i], xs[i]], -gy[ys[i], xs[i]]
            L0 = math.hypot(ox, oy) or 1
            ox, oy = ox / L0, oy / L0
            fa = math.radians((flow(px, py) if flow else angle) + rng.uniform(-jitter, jitter))
            fx, fy = math.cos(fa), math.sin(fa)
            dx, dy = ox * outward + fx * (1 - outward), oy * outward + fy * (1 - outward)
            L1 = math.hypot(dx, dy) or 1
            dx, dy = dx / L1, dy / L1
            L = length * rng.uniform(0.55, 1.25)
            p0 = (px - dx * L * 0.35, py - dy * L * 0.35)
            p2 = (px + dx * L, py + dy * L)
            p1 = ((p0[0] + p2[0]) / 2 + fx * L * 0.12, (p0[1] + p2[1]) / 2 + fy * L * 0.12)
            pts = taper([p0, p1, p2], width * rng.uniform(0.7, 1.25), 0.3, n=4)
            d.polygon([(x * SS - x0 + pad, y * SS - y0 + pad) for x, y in pts], fill=255)
        arr = gblur(np.asarray(im, F32) / 255.0, 0.6)
        self.paint(M(arr, x0 - pad, y0 - pad), col, bulge=bulge, line=line, lw=1.0, shadow=0, var=0.15,
                   tex="fbm", tex_amt=0.3)

    # ------------------------------------------------ rendering
    def render(self, sil=0.75, sil_w=1.5, grain=0.035, fade=()):
        """Lights the part and returns a full-canvas RGBA image at canvas size. fade: ((x0, y0), (x1, y1))
        pairs; coverage fades from 1 at the first point to 0 at the second (hides seams at joints)."""
        out = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        if self.bb is None:
            return out
        x0, y0, x1, y1 = self.bb
        x0, y0 = (x0 // (2 * SS)) * 2 * SS, (y0 // (2 * SS)) * 2 * SS
        x1 = min(self.w, x1 + (-x1) % (2 * SS))
        y1 = min(self.h, y1 + (-y1) % (2 * SS))
        sl = (slice(y0, y1), slice(x0, x1))
        A = self.A[sl]
        C = self.C[sl]
        lk = self.look
        # normals from slopes (softened a touch so the 2x noise does not sparkle)
        nx = -gblur(self.NX[sl], 0.8)
        ny = -gblur(self.NY[sl], 0.8)
        nz = np.ones_like(nx)
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx * inv, ny * inv, nz * inv
        # curvature: creases darken, ridges catch light
        div = np.gradient(self.NX[sl], axis=1) + np.gradient(self.NY[sl], axis=0)
        div = gblur(div, 1.5)
        cav = clamp01(div * 0.9)
        ridge = clamp01(-div * 0.7)
        # key light, half-Lambert wrap so shadows stay painterly
        kd = lk.key_dir
        ndl = nx * kd[0] + ny * kd[1] + nz * kd[2]
        t = clamp01((ndl + 0.12) / 0.75)
        diff = t * t * (3 - 2 * t)
        # warm, saturated band along the terminator (light scattering in skin, fur and cloth)
        term = np.exp(-((ndl - 0.02) / 0.16) ** 2) * self.sss
        occ = 1 - clamp01(self.O[sl] + cav * 0.55)
        # hemispheric fill
        up = clamp01(0.5 - ny * 0.5)
        amb = lk.ground[None, None, :] * (1 - up[..., None]) + lk.sky[None, None, :] * up[..., None]
        light = (lk.key[None, None, :] * (diff * occ)[..., None] + amb * (0.45 + 0.55 * occ)[..., None]
                 + np.array([0.35, 0.08, 0.02], F32)[None, None, :] * (term * occ)[..., None])
        # point lights (glows spilling onto surfaces)
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(F32) / SS
        for (px, py, pz, pc, pr, pk) in lk.lights + self.lights:
            dx, dy = px - xs, py - ys
            d = np.sqrt(dx * dx + dy * dy + pz * pz) + 1e-3
            ndp = clamp01((nx * dx + ny * dy + nz * pz) / d * 0.8 + 0.2)
            att = pk / (1 + (d / pr) ** 2)
            light = light + np.asarray(pc, F32)[None, None, :] * (ndp * att)[..., None]
        # ridges catch a little extra light
        light = light * (1 + ridge * 0.35)[..., None]
        if lk.falloff:
            fcx, fcy, frad, fk = lk.falloff
            dxy = -kd[:2] / (np.linalg.norm(kd[:2]) + 1e-6)
            pr = np.clip(((xs - fcx) * dxy[0] + (ys - fcy) * dxy[1]) / frad, -0.6, 1.0)
            light = light * (1 - fk * pr)[..., None]
        U = self.U[sl][..., None]
        col = C * (light * (1 - U) + U)
        # specular (Blinn, key light) plus a broad sheen
        hv = kd + np.array([0, 0, 1], F32)
        hv = hv / np.linalg.norm(hv)
        ndh = clamp01(nx * hv[0] + ny * hv[1] + nz * hv[2])
        G = self.G[sl]
        shin = 6 + G * 110
        spec = self.S[sl] * (ndh ** shin) * (0.4 + G * 1.6) * occ
        col = col + lk.key[None, None, :] * spec[..., None]
        MT = self.MT[sl]
        if MT.max() > 0:
            t = clamp01(-ny * 0.85 - nx * 0.35 + 0.1)
            band = np.exp(-((t - 0.28) / 0.12) ** 2)
            env = 0.12 + 1.25 * t ** 1.6 - 0.1 * band
            env = env[..., None] * (lk.key[None, None, :] * 0.55 + lk.sky[None, None, :] * 1.2)
            env = env + lk.ground[None, None, :] * clamp01(ny)[..., None] * 1.5
            mcol = env * (0.3 + C * 1.3) * (0.55 + 0.45 * occ)[..., None] + lk.key * spec[..., None] * 1.5
            col = col * (1 - MT[..., None]) + mcol * MT[..., None]
        # rim light on the far (right) edge
        rimf = clamp01(nx * 0.95 - ny * 0.3) * clamp01(1 - nz) ** 2.2 * 1.8
        rimf = rimf * (1 - 0.6 * clamp01(self.O[sl]))
        col = col + lk.rim[None, None, :] * (rimf * lk.rim_k * (0.8 + self.S[sl] * 0.8))[..., None]
        if self.paint_r:
            col = kuwahara(col, self.paint_r)
        # emission
        col = col + self.E[sl]
        # depth haze for far parts
        if self.depth:
            col = col * (1 - self.depth * 0.45) + lk.haze[None, None, :] * self.depth * 0.45
        # silhouette line from coverage, merged with the painted lines
        R = max(2, int(sil_w * SS * 2))
        sd = (box(A, R) - 0.5) * (2 * R + 1)
        es = clamp01(1 - sd / (sil_w * SS)) * (A > 0.02)
        Lm = np.maximum(self.L[sl], es * sil)
        col = np.maximum(col, 0)
        lit = clamp01(diff * occ)
        dk = Lm * (0.85 - 0.6 * lit) * (1 - clamp01(self.E[sl].max(-1) * 2))
        dark = col ** 1.35 * 0.32 + lk.line[None, None, :] * 0.25
        col = col * (1 - dk[..., None]) + dark * dk[..., None]
        # brush grain
        if grain:
            g = noise("grain", (self.h, self.w))[sl]
            col = col * (1 + (g[..., None] - 0.5) * grain * 2)
        # soft shoulder instead of hard clipping
        col = np.where(col < 0.82, col, 0.82 + 0.18 * (1 - np.exp(-(col - 0.82) / 0.18)))
        col = clamp01(col)
        for (fa, fb) in fade:
            dx, dy = fb[0] - fa[0], fb[1] - fa[1]
            t = clamp01(((xs - fa[0]) * dx + (ys - fa[1]) * dy) / (dx * dx + dy * dy + 1e-6))
            A = A * (1 - t * t * (3 - 2 * t))
        rgba = np.concatenate([col * A[..., None], A[..., None]], -1)  # premultiplied
        im = Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBa")
        im = im.resize(((x1 - x0) // SS, (y1 - y0) // SS), Image.LANCZOS).convert("RGBA")
        out.paste(im, (x0 // SS, y0 // SS))
        return out

    def free(self):
        for k in ("C", "A", "NX", "NY", "S", "G", "E", "O", "L", "U", "MT"):
            setattr(self, k, None)


class FX:
    """Additive glow layer at canvas size: accumulates light, then encodes it as RGBA (rgb = hue, a = strength)."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.L = np.zeros((H, W, 3), F32)

    def glow(self, x, y, r, col, k=1.0, core=None, squash=1.0):
        x0, y0 = max(0, int(x - r * 2.6)), max(0, int(y - r * 2.6 * squash))
        x1, y1 = min(self.W, int(x + r * 2.6) + 1), min(self.H, int(y + r * 2.6 * squash) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(F32)
        d2 = ((xs - x) / r) ** 2 + ((ys - y) / (r * squash)) ** 2
        f = np.exp(-d2 * 1.6) * k + np.exp(-d2 * 0.35) * k * 0.18
        self.L[y0:y1, x0:x1] += np.asarray(col, F32)[None, None, :] * f[..., None]
        if core is not None:
            fc = np.exp(-d2 * 9) * k
            self.L[y0:y1, x0:x1] += np.asarray(core, F32)[None, None, :] * fc[..., None]

    def mask_glow(self, m, col, blur=6.0, k=1.0):
        """Glow shaped like mask m (supersampled): blurred at two radii."""
        mm = m.blur(blur)
        a = mm.a
        x0, y0 = mm.x, mm.y
        # downsample to canvas px
        h, w = a.shape
        h2, w2 = h // SS, w // SS
        a = a[:h2 * SS, :w2 * SS].reshape(h2, SS, w2, SS).mean((1, 3))
        cx0, cy0 = x0 // SS, y0 // SS
        X0, Y0 = max(0, cx0), max(0, cy0)
        X1, Y1 = min(self.W, cx0 + w2), min(self.H, cy0 + h2)
        if X1 <= X0 or Y1 <= Y0:
            return
        a = a[Y0 - cy0:Y1 - cy0, X0 - cx0:X1 - cx0]
        self.L[Y0:Y1, X0:X1] += np.asarray(col, F32)[None, None, :] * (a * k)[..., None]

    def image(self):
        Lm = self.L
        a = clamp01(Lm.max(-1))
        rgb = np.where(a[..., None] > 1e-4, clamp01(Lm / np.maximum(a[..., None], 1e-4)), 0)
        rgba = np.concatenate([rgb, a[..., None]], -1)
        return Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")


# =============================================================== rig assembly

CASTERS = {"root", "torso", "head", "extra", "cape"}


class Rig:
    """Collects rendered parts and writes the rig plus the flat picture (fx composited additively)."""

    def __init__(self, rid, size, feet, kind, look):
        self.id = rid
        self.W = self.H = size
        self.look = look
        self.rb = rig.RigBuilder(rid, (size, size), feet=feet, facing="left", kind=kind)
        self.imgs = []

    def part(self, depth=0.0, lights=()):
        return Part(self.W, self.H, self.look, depth=depth, lights=lights)

    def fx(self):
        return FX(self.W, self.H)

    def add(self, name, part, parent, role, pivot, z, **kw):
        img = part.render(**kw) if isinstance(part, Part) else part
        if isinstance(part, Part):
            part.free()
        elif isinstance(part, FX):
            img = part.image()
        blend = "add" if role == "fx" else "normal"
        self.rb.add(name, img, parent=parent, role=role, pivot=pivot, z=z, blend=blend)
        self.imgs.append((z, blend, img))

    def flat(self):
        out = np.zeros((self.H, self.W, 4), F32)
        for z, blend, img in sorted(self.imgs, key=lambda t: t[0]):
            a = np.asarray(img, F32) / 255.0
            if blend == "add":
                add = a[..., :3] * a[..., 3:4]
                out[..., :3] += add
                out[..., 3] = clamp01(out[..., 3] + a[..., 3] * 0.9)
            else:
                al = a[..., 3:4]
                out[..., :3] = out[..., :3] * (1 - al) + a[..., :3] * al
                out[..., 3:4] = out[..., 3:4] + al * (1 - out[..., 3:4])
        al = clamp01(out[..., 3:4])
        pre = np.minimum(clamp01(out[..., :3]), al)
        rgba = np.concatenate([pre, al], -1)
        im = Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBa")
        return im

    def cast_shadows(self, off=(9, 13), blur=9.0, k=0.5, contact=0.28):
        """Bakes the soft shadow every part throws (in the rest pose) onto the parts beneath it."""
        parts = [pp for pp in self.rb.parts if pp["blend"] != "add"]
        alphas = {pp["name"]: np.asarray(pp["img"], F32)[..., 3] / 255.0 for pp in parts}
        for pp in parts:
            occ = None
            for q in parts:
                if q["z"] > pp["z"] and q["role"] in CASTERS:
                    occ = alphas[q["name"]] if occ is None else np.maximum(occ, alphas[q["name"]])
            if occ is None:
                continue
            s = gblur(shift(occ, off[0], off[1]), blur) * k + gblur(occ, 2.5) * contact
            s = clamp01(s)
            a = np.asarray(pp["img"], F32) / 255.0
            tint = np.array([0.82, 0.86, 1.0], F32)
            f = 1 - s[..., None] * (1 - (1 - tint) * 0.0)
            a[..., :3] = a[..., :3] * f * (1 - s[..., None] * (1 - tint) * 0.6)
            img = Image.fromarray((clamp01(a) * 255 + 0.5).astype(np.uint8), "RGBA")
            pp["img"] = img
        self.imgs = [(pp["z"], pp["blend"], pp["img"]) for pp in self.rb.parts]

    def save(self, flat_size=512):
        self.cast_shadows()
        self.rb.save()
        im = self.flat()
        im = im.resize((flat_size, flat_size), Image.LANCZOS).convert("RGBA")
        path = os.path.join(ROOT, "assets", "sprites", "enemies", self.id + ".png")
        im.save(path, optimize=True)
        print("wrote", os.path.relpath(path, ROOT))


# =============================================================== shared creature helpers

COOLT = hx("#2c2a4e")
WARMT = hx("#fff0d0")


def sh(col, k):
    """k < 1 darkens toward a cool tone, k > 1 lightens toward a warm one."""
    col = np.asarray(col, F32)
    if k <= 1:
        return col * k * (1 - (1 - k) * 0.35) + COOLT * (1 - k) * 0.35
    return col + (WARMT - col) * min(1.0, k - 1)


def claw(p, base, ang, L, w, col, curl=0.35, tip=None, spec=0.55):
    """A curved, tapering claw from base along angle (degrees), hooking toward +normal by curl."""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    p1 = (base[0] + ux * L * 0.5 + nx * curl * L * 0.18, base[1] + uy * L * 0.5 + ny * curl * L * 0.18)
    p2 = (base[0] + ux * L + nx * curl * L * 0.55, base[1] + uy * L + ny * curl * L * 0.55)
    m = poly(taper([base, p1, p2], w, w * 0.08))
    p.paint(m, col, grad=(tip if tip is not None else sh(col, 1.25), base, p2), spec=spec, gloss=0.55, line=0.5,
            lw=1.2, shadow=0.35, sh_off=(3, 4), sh_blur=3, var=0)
    return m


def fang(p, base, ang, L, w, col, curl=0.15, spec=0.6):
    """A conical tooth: wide root at base, point along angle."""
    return claw(p, base, ang, L, w, col, curl=curl, tip=sh(col, 1.15), spec=spec)


def fur(p, m, base, angle, n, seed, length=34, width=7.5, dark=0.7, light=1.25, alpha=0.6, flow=None,
        jitter=22, curl=0.25, bump=0.8):
    """Strands of fur in m: a dark and a light set so the shading breaks up into tufts."""
    p.strokes(m, angle, length, width, n, [sh(base, dark), sh(base, light), sh(base, 0.9)], seed=seed,
              jitter=jitter, alpha=alpha, flow=flow, curl=curl, bump=bump)


def tufts(path, amp, step, side=1, lean=0.4, seed=1, jit=0.3):
    """Jagged spiky tufts along path (a polygon strip closed back along the path)."""
    rng = random.Random(seed)
    c = cr(path, n=12)
    total = plen(c)
    k = max(2, int(total / step))
    out = []
    for i in range(k + 1):
        t = i / k
        (x, y), (tx, ty) = at(c, t)
        nx, ny = -ty * side, tx * side
        if i % 2 == 0:
            out.append((x, y))
        else:
            h = amp * rng.uniform(1 - jit, 1 + jit)
            out.append((x + nx * h + tx * h * lean, y + ny * h + ty * h * lean))
    return out + [at(c, 1)[0]] + list(reversed([at(c, i / 10)[0] for i in range(11)]))


def glow_eye(p, cx, cy, rx, ry, col, core, rot=0.0, socket=None, k=1.0):
    """A glowing eye: dark socket, bright emissive iris and a white-hot core."""
    if socket is not None:
        p.paint(ellipse(cx, cy, rx * 1.35, ry * 1.4, rot), socket, mode="on", bulge=-0.5, line=0.4, shadow=0)
    e = ellipse(cx, cy, rx, ry, rot)
    p.paint(e, sh(col, 0.6), mode="on", bulge=0.6, spec=0.9, gloss=0.9, emit=np.asarray(col) * 0.9 * k,
            unlit=0.7, line=0.3, shadow=0)
    p.glow_on(ellipse(cx - rx * 0.1, cy, rx * 0.62, ry * 0.62, rot), np.asarray(col) * 0.6, k)
    p.glow_on(ellipse(cx - rx * 0.15, cy - ry * 0.05, rx * 0.3, ry * 0.3, rot), np.asarray(core) * 0.9, k)
    return e


def chain(p, path, size, col, step=None, spec=0.8):
    """A hanging iron chain: alternating open rings and edge-on links along path."""
    c = cr(path, n=16) if len(path) > 2 else path
    step = step or size * 0.95
    total = plen(c)
    n = max(2, int(total / step))
    for i in range(n + 1):
        (x, y), (tx, ty) = at(c, i / n)
        a = math.degrees(math.atan2(ty, tx))
        if i % 2:
            m = ellipse(x, y, size * 0.6, size * 0.2, a)
            p.paint(m, sh(col, 0.85), spec=spec, gloss=0.6, line=0.6, lw=1.2, shadow=0.35, sh_off=(3, 4),
                    sh_blur=3, var=0)
        else:
            m = ellipse(x, y, size * 0.62, size * 0.4, a) - ellipse(x, y, size * 0.34, size * 0.15, a)
            p.paint(m, col, spec=spec, gloss=0.6, line=0.6, lw=1.2, shadow=0.35, sh_off=(3, 4), sh_blur=3,
                    tex="pits", tex_amt=0.3, var=0)


def rivet(p, x, y, r, col, spec=0.9, metal=0.8):
    p.paint(circle(x, y, r), col, mode="on", bulge=0.9, spec=spec, gloss=0.7, line=0.5, lw=1.0, shadow=0.4,
            sh_off=(2, 3), sh_blur=2, var=0, metal=metal)


def rust_on(p, m, amount=0.5, seed_col=hx("#6a3a1e")):
    """Blotchy rust over a metal area."""
    b = m.box
    f = noise("fbm", (p.h, p.w))[b[1]:b[3], b[0]:b[2]]
    g = noise("pits", (p.h, p.w))[b[1]:b[3], b[0]:b[2]]
    r = clamp01((f * 0.7 + g * 0.5 - (1.05 - amount * 0.6)) * 2.2) * m.a * 0.85
    p.paint(M(r, b[0], b[1]), seed_col, mode="on", bulge=0.0, tex="pits", tex_amt=0.8, bump=0.5, spec=0.05,
            gloss=0.1, line=0, shadow=0)


# =============================================================== cellar rat

CELLAR = dict(key=(1.55, 1.36, 1.1), sky=(0.2, 0.25, 0.36), ground=(0.11, 0.08, 0.08), rim=(0.55, 0.85, 1.0),
              rim_k=1.3)


def rat_hand(p, wrist, ang, s, skin, claw_c, spread=1.0, fingers=4):
    """A rat's clawed hand from the wrist along ang: a narrow palm, long knuckled fingers, hooked claws."""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    palm_c = (wrist[0] + ux * s * 0.45, wrist[1] + uy * s * 0.45)
    p.paint(ellipse(palm_c[0], palm_c[1], s * 0.62, s * 0.42, ang), skin, spec=0.25, gloss=0.35, tex="pits",
            tex_amt=0.2, bump=0.3)
    for i in range(fingers):
        off = (i - (fingers - 1) / 2) * s * 0.3 * spread
        fa = ang + (i - (fingers - 1) / 2) * 16 * spread
        fr = math.radians(fa)
        b0 = (palm_c[0] + ux * s * 0.3 + nx * off, palm_c[1] + uy * s * 0.3 + ny * off)
        k1 = (b0[0] + math.cos(fr) * s * 0.45, b0[1] + math.sin(fr) * s * 0.45)
        k2 = (k1[0] + math.cos(fr + 0.35) * s * 0.35, k1[1] + math.sin(fr + 0.35) * s * 0.35)
        p.paint(tube([b0, k1, k2], s * 0.2, s * 0.15), skin, spec=0.25, gloss=0.35, line=0.5, shadow=0.3,
                sh_off=(2, 3), sh_blur=2)
        for kx, ky in (k1,):
            p.fold([(kx - nx * s * 0.07, ky - ny * s * 0.07), (kx + nx * s * 0.07, ky + ny * s * 0.07)], 3, 0.6)
        claw(p, k2, math.degrees(fr + 0.6), s * 0.6, s * 0.16, claw_c, curl=0.5)


def cellar_rat():
    """A giant diseased cellar rat reared up on its haunches, hunched and hissing: yellow chisel teeth bared,
    one red eye burning under a scarred brow, a torn ear, hackles raised along a mangy back, ribs showing
    through raw sores, an old stitched scar, clawed hands raised and reaching, and a long scaly ringed tail
    (faces left)."""
    EYE = (300, 392)
    look = Look(**CELLAR, lights=[(EYE[0] - 8, EYE[1], 24, (1.0, 0.22, 0.08), 44, 1.2)],
                falloff=(560, 620, 420, 0.38))
    R = Rig("cellar_rat", 1024, (560, 968), "beast", look)
    fur_c = hx("#6c5f57")
    fur_d = hx("#3a302e")
    belly = hx("#9c8b7c")
    skin = hx("#b47a76")
    claw_c = hx("#bca27a")
    tooth = hx("#cdb58a")
    sore = hx("#5e1618")
    pus = hx("#b4ae4c")
    red = np.array([1.0, 0.2, 0.06], F32)

    def furry(p, m, seed, angle=70, n=1200, flow=None, base=fur_c, length=30, width=6.5, bulge=0.8, edge=1.0):
        p.sss = 0.6
        p.paint(m, base, tex="fbm", tex_amt=0.45, var=0.2, bump=0.3, bump_tex="pits", spec=0.1, gloss=0.25,
                bulge=bulge)
        p.strokes(m, angle, length * 1.8, width * 2.2, n // 6, [sh(base, 0.72), sh(base, 1.12)], seed=seed + 100,
                  jitter=14, alpha=0.5, flow=flow, curl=0.2, bump=1.2)
        fur(p, m, base, angle, n, seed, flow=flow, length=length, width=width, bump=1.4)
        if edge:
            p.fringe(m, sh(base, 0.85), angle, int(n * 0.16 * edge), length * 0.5, width * 0.9, seed=seed + 7,
                     flow=flow, jitter=30)
        return m

    def sores(p, pts, seed, clip=None):
        rng = random.Random(seed)
        for x, y, r in pts:
            p.paint(ellipse(x, y, r * 1.6, r * 1.25, rng.uniform(0, 180)), sh(skin, 0.8), mode="on", bulge=0.3,
                    tex="pits", tex_amt=0.6, spec=0.3, gloss=0.5, line=0.2, shadow=0, clip=clip)
            p.paint(ellipse(x, y, r, r * 0.8, rng.uniform(0, 180)), sore, mode="on", bulge=-0.5, tex="pits",
                    tex_amt=0.7, bump=0.7, spec=0.8, gloss=0.75, line=0.4, shadow=0, clip=clip)
            p.paint(ellipse(x - r * 0.35, y - r * 0.25, r * 0.32, r * 0.26), pus, mode="on", bulge=0.9, spec=0.9,
                    gloss=0.8, line=0, shadow=0, clip=clip)

    def hand(p, wrist, ang, s, spread=1.0, col=skin):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        pc = (wrist[0] + ux * s * 0.4, wrist[1] + uy * s * 0.4)
        p.sss = 0.8
        p.paint(ellipse(pc[0], pc[1], s * 0.55, s * 0.36, ang), col, tex="pits", tex_amt=0.35, bump=0.5,
                spec=0.3, gloss=0.4, line=0.45)
        for i in range(4):
            k = i - 1.5
            fa = math.radians(ang + k * 17 * spread)
            b0 = (pc[0] + ux * s * 0.3 + nx * k * s * 0.24 * spread, pc[1] + uy * s * 0.3 + ny * k * s * 0.24 * spread)
            L1 = s * (0.5 - abs(k) * 0.06)
            k1 = (b0[0] + math.cos(fa) * L1, b0[1] + math.sin(fa) * L1)
            fb = fa + 0.45
            k2 = (k1[0] + math.cos(fb) * s * 0.34, k1[1] + math.sin(fb) * s * 0.34)
            p.paint(tube([b0, k1, k2], s * 0.16, s * 0.11), col, tex="pits", tex_amt=0.3, bump=0.4, spec=0.3,
                    gloss=0.4, line=0.45, shadow=0.35, sh_off=(3, 4), sh_blur=3)
            p.paint(circle(k1[0], k1[1], s * 0.1), sh(col, 1.05), mode="on", bulge=0.8, line=0, shadow=0)
            claw(p, k2, math.degrees(fb + 0.5), s * 0.5, s * 0.13, claw_c, curl=0.55, tip=hx("#efe2c4"))

    # ================= hips (root): haunches and belly
    p = R.part()
    hips = poly([(470, 640), (560, 612), (684, 636), (772, 700), (806, 790), (794, 882), (744, 932), (640, 948),
                 (556, 934), (498, 884), (458, 790)], smooth=True)
    furry(p, hips, 11, flow=lambda x, y: 80 + (x - 620) * 0.08, n=1700)
    bel = poly([(452, 650), (500, 640), (540, 720), (580, 820), (580, 920), (520, 930), (470, 850)], smooth=True)
    p.paint(bel & hips, belly, mode="tint", op=0.8, grad=(sh(belly, 0.8), (500, 650), (540, 930)))
    fur(p, bel & hips, belly, 95, 380, 12, alpha=0.5)
    mange = ellipse(730, 780, 44, 32, 60)
    p.paint(mange & hips, sh(skin, 0.85), mode="on", bulge=0.1, tex="pits", tex_amt=0.5, bump=0.6, line=0.3)
    sores(p, [(726, 770, 10), (742, 800, 7)], 1)
    R.add("hips", p, "", "root", (630, 800), 10)

    # ================= chest (torso): hunched shoulders, hackles, ribs through the mange, a stitched scar
    p = R.part()
    back = [(468, 420), (540, 382), (612, 384), (690, 440), (748, 540), (780, 660)]
    chest = union(poly([(470, 440), (530, 396), (604, 386), (684, 440), (748, 540), (778, 650), (772, 764),
                        (700, 796), (600, 796), (500, 744), (440, 660), (420, 560), (434, 482)], smooth=True),
                  poly(tufts(back, 30, 20, side=-1, lean=0.5, seed=5)))
    furry(p, chest, 21, flow=lambda x, y: 55 + (x - 480) * 0.1, n=2400)
    hack = poly(tufts(back, 30, 20, side=-1, lean=0.5, seed=5)) | tube(back, 44)
    p.paint(hack & chest, fur_d, mode="tint", op=0.75)
    fur(p, hack & chest, fur_d, -35, 600, 22, length=34, width=6, dark=0.6, light=1.35, alpha=0.7)
    p.fringe(hack, fur_d, -40, 260, 24, 7, seed=23, outward=0.5, jitter=30)
    # vertebrae bumps along the spine
    front = poly([(440, 470), (410, 560), (424, 660), (480, 730), (520, 716), (484, 620), (474, 500)], smooth=True)
    p.paint(front & chest, belly, mode="tint", op=0.75, grad=(sh(belly, 1.05), (440, 480), (480, 730)))
    fur(p, front & chest, belly, 100, 420, 24, alpha=0.5)
    # a mangy flank with the ribs showing through, and weeping sores
    mg = poly([(600, 560), (680, 540), (730, 600), (720, 690), (650, 710), (596, 660)], smooth=True)
    mgs = mg.blur(8)
    p.paint(mgs & chest, sh(skin, 0.62), mode="tint", op=0.85, tex="pits", tex_amt=0.6)
    for i in range(4):
        y = 584 + i * 30
        p.fold([(610, y + 8), (652, y - 4), (706, y + 4 + i * 4)], 12, -0.7, clip=mgs)
        p.fold([(614, y + 20), (656, y + 10), (708, y + 18 + i * 4)], 6, 0.6, clip=mgs)
    p.fringe(mg, fur_c, 60, 90, 16, 7, seed=25, outward=-0.6, band=(0.35, 0.65))
    sores(p, [(632, 600, 10), (690, 650, 8), (660, 690, 6)], 2, clip=chest)
    scar = [(528, 430), (556, 480), (568, 540)]
    p.paint(tube(scar, 14, 9), sh(skin, 0.95), mode="on", bulge=0.9, spec=0.35, gloss=0.5, line=0.3)
    c = cr(scar, n=8)
    for i in range(1, 6):
        (x, y), (tx, ty) = at(c, i / 6)
        p.paint(tube([(x - ty * 15 - tx * 3, y + tx * 15 - ty * 3), (x + ty * 15 + tx * 3, y - tx * 15 + ty * 3)], 3.4),
                hx("#1e1414"), mode="on", bulge=0.6, line=0, shadow=0.4, sh_off=(1, 2), sh_blur=1.5)
    R.add("chest", p, "hips", "torso", (620, 720), 12, fade=[((600, 740), (604, 800))])

    # ================= head
    p = R.part()
    far_ear = ellipse(482, 312, 42, 58, 24)
    p.paint(far_ear, sh(fur_c, 0.8), tex="fbm", tex_amt=0.3)
    p.paint(ellipse(478, 318, 28, 42, 24), sh(skin, 0.45), mode="on", bulge=-0.4, line=0.3, shadow=0)
    head = poly([(506, 440), (490, 380), (448, 340), (382, 318), (312, 326), (248, 354), (192, 394), (150, 428),
                 (122, 452), (110, 472), (124, 490), (170, 494), (240, 498), (320, 508), (400, 522), (462, 518),
                 (504, 486)], smooth=True)
    furry(p, head, 31, angle=6, n=1700, length=22, width=5, edge=0.8)
    ruff = poly(tufts([(446, 460), (410, 510), (350, 524)], 16, 14, side=1, seed=7)) | ellipse(390, 470, 64, 44)
    p.paint(ruff & head, sh(fur_c, 1.05), mode="on", bulge=0.6, tex="fbm", tex_amt=0.4, line=0.2, shadow=0.3)
    fur(p, ruff & head, sh(fur_c, 1.05), 70, 300, 32, length=20, width=5)
    muz = poly([(116, 460), (200, 410), (276, 430), (300, 496), (190, 496), (120, 486)], smooth=True)
    p.paint(muz & head, sh(skin, 0.8), mode="tint", op=0.3)
    for i, (x, y) in enumerate(((200, 408), (222, 396), (246, 386), (268, 380))):
        p.fold([(x - 12, y - 16), (x, y), (x + 5, y + 18)], 8, 1.2, clip=head)
    nose = ellipse(124, 462, 22, 16, -24)
    p.paint(nose, skin, grad=(sh(skin, 0.6), (120, 448), (130, 478)), spec=1.0, gloss=0.85, line=0.5, shadow=0.3)
    p.paint(ellipse(116, 470, 6, 4, -30), hx("#1e0e10"), mode="on", bulge=-0.6, line=0, shadow=0)
    # a heavy scarred brow over the burning eye
    p.paint(ellipse(306, 372, 46, 16, -16), fur_d, mode="on", bulge=0.8, tex="fbm", tex_amt=0.4, line=0.3,
            shadow=0.5, sh_off=(3, 6), sh_blur=4)
    glow_eye(p, EYE[0], EYE[1], 15, 11, red, (1.0, 0.85, 0.5), rot=-14, socket=hx("#140606"))
    p.paint(poly([(276, 378), (330, 372), (326, 386), (280, 388)], smooth=True), fur_d, mode="on", bulge=0.5,
            op=0.9, line=0.2, shadow=0.45, sh_off=(0, 3), sh_blur=3)
    p.paint(tube([(262, 336), (296, 372), (318, 430)], 7, 5), sh(skin, 0.95), mode="on", bulge=1.0, line=0.3)
    rng = random.Random(4)
    for i in range(16):
        x, y = 176 + rng.uniform(0, 56), 440 + rng.uniform(0, 36)
        p.paint(circle(x, y, 2.4), fur_d, mode="on", bulge=-0.7, line=0, shadow=0)
    gum = poly([(138, 484), (220, 492), (300, 504), (306, 520), (230, 514), (152, 502)], smooth=True)
    p.paint(gum, hx("#86323c"), spec=0.8, gloss=0.75, line=0.4, shadow=0.25)
    p.fold([(136, 486), (220, 493), (312, 506)], 8, -0.9)
    for x0, lean in ((146, 5), (164, 7)):
        m = poly(taper([(x0, 486), (x0 + lean * 0.6, 522), (x0 + lean, 560)], 17, 13, n=6))
        p.paint(m, tooth, grad=(hx("#6a4418"), (x0, 488), (x0, 540)), spec=0.8, gloss=0.65, tex="pits",
                tex_amt=0.35, line=0.55, lw=1.3, shadow=0.4)
        p.paint(tube([(x0 - 5, 496), (x0 - 4 + lean, 552)], 3.2, 2), hx("#fff2cc"), mode="on", bulge=0.4, op=0.6,
                line=0, shadow=0)
    for i, (sx, sy, ex, ey, cy) in enumerate(((204, 440), (210, 450), (208, 460), (218, 468), (196, 446),
                                              (232, 456), (224, 446)) and ((204, 440, 44, 364, -40),
                                                                           (210, 450, 30, 418, -12),
                                                                           (208, 460, 40, 470, 6),
                                                                           (218, 468, 66, 524, 24),
                                                                           (196, 446, 70, 332, -60),
                                                                           (232, 456, 120, 560, 40),
                                                                           (224, 446, 92, 384, -30))):
        mid = ((sx + ex) / 2, (sy + ey) / 2 + cy * 0.5)
        col = hx("#1e1816") if i % 3 else hx("#bcb0a0")
        p.paint(poly(taper([(sx, sy), mid, (ex, ey)], 3.0, 0.4)), col, bulge=0.4, line=0, shadow=0.2,
                sh_off=(2, 3), sh_blur=2, spec=0.4, gloss=0.5)
    R.add("head", p, "chest", "head", (474, 474), 20, fade=[((486, 460), (526, 470))])

    # ================= jaw: lower jaw with the mouth interior tucked under the head
    p = R.part()
    maw = poly([(444, 512), (412, 454), (300, 468), (212, 480), (144, 486), (144, 514), (176, 548), (270, 538),
                (372, 530)], smooth=True)
    p.paint(maw, hx("#300a10"), grad=(hx("#0e0206"), (220, 500), (400, 490)), spec=0.7, gloss=0.65, line=0.3)
    p.paint(ellipse(268, 522, 76, 17, -5), hx("#a04252"), mode="on", bulge=0.7, spec=0.95, gloss=0.8, line=0.3,
            shadow=0.45)
    p.fold([(206, 522), (268, 520), (326, 522)], 5, 0.9)
    jaw = poly([(434, 508), (412, 546), (332, 568), (252, 580), (192, 580), (164, 566), (174, 548), (236, 540),
                (318, 530), (390, 518)], smooth=True)
    furry(p, jaw, 41, angle=8, n=500, length=16, width=4, edge=0.7)
    p.paint(poly([(176, 564), (256, 574), (340, 562), (330, 580), (250, 588), (186, 582)], smooth=True) & jaw,
            sh(belly, 0.9), mode="tint", op=0.7)
    p.paint(poly([(176, 546), (236, 540), (318, 530), (316, 540), (238, 550), (182, 556)], smooth=True),
            hx("#7a2a38"), mode="on", bulge=0.5, spec=0.8, gloss=0.75, line=0.3, shadow=0)
    for x0 in (190, 206):
        fang(p, (x0, 560), -97, 46, 13, tooth, curl=-0.2)
    p.paint(poly(taper([(212, 576), (217, 614), (220, 654)], 5, 3)), hx("#d0e0d8"), op=0.7, spec=1.0, gloss=0.9,
            line=0.25, shadow=0)
    p.paint(ellipse(221, 662, 7, 9), hx("#d0e0d8"), op=0.85, spec=1.0, gloss=0.9, line=0.3, shadow=0)
    R.add("jaw", p, "head", "jaw", (398, 512), 18)

    # ================= ear (twitches)
    p = R.part()
    p.sss = 0.4
    ear = (ellipse(398, 262, 58, 84, -20) | tube([(410, 312), (430, 360)], 68, 60)) - poly(
        [(338, 214), (380, 236), (368, 196), (356, 180)])
    ear = ear - circle(430, 206, 7)
    p.paint(ear, sh(fur_c, 0.95), tex="fbm", tex_amt=0.3, bulge=0.5)
    inner = ellipse(394, 268, 42, 66, -20) - poly([(338, 214), (386, 240), (370, 194)])
    p.paint(inner, hx("#7a4a4c"), grad=(hx("#3e2226"), (390, 210), (410, 330)), mode="on", bulge=-0.4,
            emit=(0.05, 0.008, 0.008), spec=0.3, gloss=0.4, line=0.3, shadow=0)
    for pts in ([(400, 320), (386, 270), (368, 230)], [(400, 320), (406, 272), (404, 220)], [(386, 270), (362, 264)]):
        p.paint(tube(pts, 3, 1.2), hx("#6a1a22"), mode="on", bulge=0.5, line=0, shadow=0, clip=inner)
    p.fringe(ear - inner, sh(fur_c, 0.9), -110, 60, 12, 6, seed=33, outward=0.7)
    R.add("ear", p, "head", "hair", (424, 342), 22, fade=[((420, 334), (432, 370))])

    # ================= far arm, raised high with claws spread (behind the head)
    p = R.part(depth=0.3)
    furry(p, tube([(540, 486), (486, 440), (430, 402)], 72, 54), 51, angle=215, n=500)
    R.add("arm_back_upper", p, "chest", "arm_back_upper", (540, 486), 6)
    p = R.part(depth=0.3)
    furry(p, tube([(430, 402), (350, 350), (272, 300)], 54, 34), 52, angle=212, n=420)
    hand(p, (272, 300), -140, 72, spread=1.3, col=sh(skin, 0.9))
    R.add("arm_back_lower", p, "arm_back_upper", "arm_back_lower", (430, 402), 7)

    # ================= far hind leg (mostly hidden)
    p = R.part(depth=0.3)
    furry(p, ellipse(722, 840, 76, 64) | tube([(726, 812), (700, 890)], 92, 62), 61, n=300)
    R.add("leg_back_upper", p, "hips", "leg_back_upper", (726, 812), 4)
    p = R.part(depth=0.3)
    furry(p, tube([(700, 890), (776, 942)], 58, 38), 62, n=200)
    foot = poly([(796, 934), (762, 950), (700, 954), (658, 952), (640, 962), (652, 972), (720, 974), (796, 972),
                 (810, 956)], smooth=True)
    p.paint(foot, sh(skin, 0.9), tex="pits", tex_amt=0.5, bump=0.6, spec=0.3, gloss=0.4)
    for i, y in enumerate((956, 966)):
        claw(p, (652, y), 172 + i * 6, 28, 7, claw_c, curl=-0.4)
    R.add("leg_back_lower", p, "leg_back_upper", "leg_back_lower", (700, 890), 5)

    # ================= tail
    def tail_seg(path, w0, w1, seed):
        p = R.part()
        p.sss = 0.8
        m = tube(path, w0, w1)
        p.paint(m, sh(skin, 0.92), grad=(sh(skin, 0.66), path[0], path[-1]), tex="pits", tex_amt=0.45, bump=0.5,
                spec=0.4, gloss=0.45, var=0.12)
        c = cr(path, n=10)
        L = plen(c)
        k = max(2, int(L / 10))
        for i in range(k + 1):
            (x, y), (tx, ty) = at(c, i / k)
            w = (w0 + (w1 - w0) * i / k) * 0.56
            p.fold([(x - ty * w + tx * 3, y + tx * w + ty * 3), (x, y), (x + ty * w + tx * 3, y - tx * w + ty * 3)],
                   3.0, 1.1, clip=m)
        rng = random.Random(seed)
        for i in range(k // 2 + 1):
            (x, y), (tx, ty) = at(c, rng.random())
            s = rng.choice((-1, 1))
            w = (w0 + w1) * 0.24
            p.paint(poly(taper([(x - ty * w * s * 0.7, y + tx * w * s * 0.7),
                                (x - ty * (w + 10) * s + tx * 7, y + tx * (w + 10) * s + ty * 7)], 2.0, 0.4)),
                    sh(fur_d, 0.9), bulge=0.3, line=0, shadow=0)
        return p

    R.add("tail_1", tail_seg([(740, 876), (800, 926), (872, 944)], 50, 34, 1), "hips", "tail", (752, 884), 3)
    R.add("tail_2", tail_seg([(872, 944), (926, 924), (952, 864)], 34, 22, 2), "tail_1", "tail", (872, 944), 2)
    R.add("tail_3", tail_seg([(952, 864), (948, 800), (918, 758), (880, 746)], 22, 5, 3), "tail_2", "tail",
          (952, 864), 1)

    # ================= near hind leg: haunch, shin and a long clawed foot
    p = R.part()
    thigh = poly([(600, 722), (700, 740), (744, 820), (724, 892), (640, 918), (566, 908), (526, 872), (544, 800)],
                 smooth=True)
    furry(p, thigh, 71, flow=lambda x, y: 105 + (x - 620) * 0.25, n=1100)
    p.fold([(560, 896), (600, 910), (650, 912)], 12, 0.8, clip=thigh)
    R.add("leg_front_upper", p, "hips", "leg_front_upper", (650, 800), 26, fade=[((660, 790), (716, 726))])
    p = R.part()
    furry(p, tube([(560, 884), (626, 946)], 70, 44), 72, n=300)
    foot = poly([(650, 932), (612, 948), (530, 952), (462, 950), (430, 956), (440, 972), (520, 976), (640, 974),
                 (662, 956)], smooth=True)
    p.sss = 0.8
    p.paint(foot, skin, tex="pits", tex_amt=0.5, bump=0.7, spec=0.3, gloss=0.4)
    for x in range(474, 640, 15):
        p.fold([(x, 950), (x + 3, 972)], 4, 0.7, clip=foot)
    for i, (x, y) in enumerate(((452, 950), (446, 960), (454, 970))):
        p.paint(tube([(x + 26, y), (x, y + 2)], 15, 12), skin, spec=0.3, gloss=0.4, line=0.4, shadow=0.3,
                sh_off=(2, 3), sh_blur=2)
        claw(p, (x + 2, y + 2), 172 + i * 6, 34, 9, claw_c, curl=-0.45, tip=hx("#efe2c4"))
    R.add("leg_front_lower", p, "leg_front_upper", "leg_front_lower", (560, 884), 25)

    # ================= near arm reaching for the hero
    p = R.part()
    furry(p, tube([(500, 566), (478, 630), (456, 692)], 82, 60), 81, angle=100, n=600)
    R.add("arm_front_upper", p, "chest", "arm_front_upper", (500, 566), 30, fade=[((496, 566), (506, 520))])
    p = R.part()
    m = tube([(456, 692), (394, 704), (334, 704)], 58, 36)
    furry(p, m, 82, angle=182, n=450)
    hand(p, (334, 704), 176, 80, spread=1.1)
    R.add("arm_front_lower", p, "arm_front_upper", "arm_front_lower", (456, 692), 31)

    # ================= fx: the burning eye
    fx = R.fx()
    fx.glow(EYE[0] - 4, EYE[1], 24, (1.0, 0.16, 0.04), 0.9, core=(1.0, 0.7, 0.3))
    fx.glow(EYE[0] - 4, EYE[1], 60, (0.8, 0.08, 0.02), 0.25)
    R.add("eye_glow", fx, "head", "fx", EYE, 40)
    return R


# =============================================================== skeleton guard

BONE = hx("#a39474")


def bone(p, a, b, w, col=BONE, knob=1.3, knobs=(True, True), **kw):
    """A long bone from a to b: a shaft that narrows in the middle and rounded knuckles at both ends."""
    m = tube([a, ((a[0] * 2 + b[0]) / 3, (a[1] * 2 + b[1]) / 3), ((a[0] + b[0] * 2) / 3, (a[1] + b[1] * 2) / 3), b],
             [w * 1.1, w * 0.82, w * 0.82, w * 1.1])
    for on, c in zip(knobs, (a, b)):
        if on:
            m = m | circle(c[0], c[1], w * knob * 0.5)
    kw.setdefault("tex", "pits")
    kw.setdefault("tex_amt", 0.45)
    kw.setdefault("bump", 0.5)
    kw.setdefault("spec", 0.3)
    kw.setdefault("gloss", 0.35)
    p.paint(m, col, **kw)
    # a hairline crack and grime in the grooves
    dx, dy = b[0] - a[0], b[1] - a[1]
    p.fold([(a[0] + dx * 0.35, a[1] + dy * 0.35), (a[0] + dx * 0.5 + dy * 0.03, a[1] + dy * 0.5 - dx * 0.03)], 2.5, 0.8,
           clip=m)
    return m


def grime(p, m, col=hx("#4a3a28"), k=0.55):
    """Dirt settling in the lower, shadowed half of a shape."""
    x0, y0, x1, y1 = m.box
    b = m.box
    f = noise("fbm", (p.h, p.w))[y0:y1, x0:x1]
    ys = np.linspace(0, 1, y1 - y0, dtype=F32)[:, None]
    a = clamp01((f * 0.8 + ys * 0.7 - 0.75) * 3) * m.a * k
    p.paint(M(a, x0, y0), col, mode="tint")


def skeleton_guard():
    """A skeleton soldier in a lunge behind a battered round shield, a notched rusty sword held back at the
    shoulder, jaw dropped in a silent battle cry, soul-fire burning in the eye sockets and inside the ribcage,
    a dented kettle helmet, a rusty pauldron and a tattered purple cloak (faces left)."""
    soul = np.array([1.0, 0.42, 0.12], F32)
    core = np.array([1.0, 0.9, 0.62], F32)
    RIB = (520, 520)
    EYES = [(404, 300), (462, 296)]
    look = Look(**CELLAR, lights=[(RIB[0], RIB[1], 18, (1.0, 0.45, 0.14), 90, 1.6),
                                  (430, 300, 20, (1.0, 0.45, 0.14), 50, 1.0)],
                falloff=(520, 560, 420, 0.32))
    R = Rig("skeleton_guard", 1024, (560, 968), "humanoid", look)
    iron = hx("#6c737c")
    rust = hx("#6e4a34")
    rag = hx("#4a3a5c")
    leath = hx("#4e3424")
    bone_d = sh(BONE, 0.82)

    # ================= pelvis (root): hip bones, belt, ragged loincloth
    p = R.part()
    p.sss = 0.3
    rag_m = poly([(452, 596), (612, 590), (628, 660), (620, 720), (600, 700), (588, 752), (566, 716), (540, 770),
                  (520, 722), (494, 760), (480, 712), (456, 736), (446, 680)], smooth=False).blur(1.2)
    p.paint(rag_m, rag, tex="fbm", tex_amt=0.5, var=0.15, bulge=0.35)
    for x in (480, 520, 560, 596):
        p.fold([(x, 610), (x - 6, 680), (x - 10, 730)], 12, 0.9, clip=rag_m)
    pel = union(ellipse(530, 596, 66, 40), ellipse(488, 604, 36, 30, -20), ellipse(574, 602, 38, 30, 20))
    p.paint(pel, BONE, tex="pits", tex_amt=0.45, bump=0.5, spec=0.3, gloss=0.35)
    p.paint(ellipse(530, 606, 22, 16), hx("#1c1214"), mode="on", bulge=-0.8, line=0.3, shadow=0)
    grime(p, pel)
    belt = tube([(446, 590), (530, 598), (618, 586)], 26)
    p.paint(belt, leath, tex="fbm", tex_amt=0.5, bump=0.4, spec=0.2)
    p.paint(poly([(510, 580), (548, 582), (548, 612), (510, 612)]), iron, metal=0.8, spec=0.9, gloss=0.6, tex="pits",
            tex_amt=0.4)
    p.paint(poly([(518, 588), (540, 588), (540, 605), (518, 605)]), hx("#1e1814"), mode="on", bulge=-0.5, line=0.2)
    rust_on(p, poly([(510, 580), (548, 582), (548, 612), (510, 612)]), 0.7)
    R.add("pelvis", p, "", "root", (530, 600), 10)

    # ================= torso: spine, ribcage lit from within, collarbones, strap, rusty pauldron
    p = R.part()
    p.sss = 0.2
    spine = [(530, 600), (538, 520), (528, 450), (504, 392)]
    c = cr(spine, n=10)
    for i in range(12):
        (x, y), (tx, ty) = at(c, i / 11)
        p.paint(ellipse(x, y, 17, 12, math.degrees(math.atan2(ty, tx)) + 90), bone_d, tex="pits", tex_amt=0.4,
                bump=0.4, spec=0.25, line=0.5, shadow=0.35, sh_off=(2, 4), sh_blur=3)
    for i, (y, w) in enumerate(((440, 92), (470, 96), (500, 96), (530, 90), (558, 78))):
        for side in (1, -1):
            k = 1.0 if side < 0 else 0.8
            x0 = 532 - i * 2
            pts = [(x0 + side * 4, y - 6), (x0 + side * w * 0.6 * k, y - 16), (x0 + side * w * k, y + 8),
                   (x0 + side * w * 0.8 * k, y + 34)]
            p.paint(poly(taper(pts, 16, 7)), BONE if side < 0 else bone_d, tex="pits", tex_amt=0.4, bump=0.4,
                    spec=0.3, gloss=0.35, line=0.55, shadow=0.4, sh_off=(3, 5), sh_blur=4)
    p.paint(tube([(506, 424), (514, 486), (520, 540)], 20, 14), BONE, tex="pits", tex_amt=0.4, spec=0.3)
    for a, b in (((420, 414), (510, 426)), ((520, 424), (600, 408))):
        bone(p, a, b, 17, BONE if a[0] < 500 else bone_d, knob=1.1)
    strap = tube([(446, 420), (520, 500), (600, 590)], 20)
    p.paint(strap, leath, tex="fbm", tex_amt=0.5, bump=0.4, spec=0.2, shadow=0.45)
    p.paint(poly([(506, 478), (532, 478), (532, 506), (506, 506)]), hx("#9a9aa0"), metal=0.9, spec=1.0, gloss=0.7)
    # pauldron on the sword shoulder
    pd = poly(ell(590, 412, 64, 40, 12, 180, 360) + ell(590, 420, 64, 16, 12, 0, 180))
    p.paint(pd, iron, metal=0.85, spec=0.9, gloss=0.55, tex="pits", tex_amt=0.4, bump=0.4, shadow=0.5, sh_off=(4, 8))
    p.paint(poly(ell(592, 426, 60, 22, 12, 170, 370) + ell(592, 432, 60, 10, 12, 10, 170)), sh(iron, 0.9),
            spec=0.9, gloss=0.55, tex="pits", tex_amt=0.4, shadow=0.4)
    rust_on(p, pd, 0.8)
    for x, y in ((546, 404), (590, 380), (632, 402)):
        rivet(p, x, y, 5, hx("#b0a090"))
    p.fold([(560, 392), (580, 402), (574, 414)], 5, 1.2, clip=pd)  # a dent
    R.add("torso", p, "pelvis", "torso", (530, 596), 12)
    fx = R.fx()
    fx.glow(RIB[0] + 6, RIB[1] + 10, 46, soul * 0.9, 0.7, core=core * 0.5)
    fx.glow(RIB[0] + 6, RIB[1], 120, soul * 0.5, 0.22)
    R.add("rib_fire", fx, "torso", "fx", RIB, 13)
    # the soul fire itself sits inside the ribcage (behind the ribs, in front of the spine)
    p = R.part()
    cav = ellipse(RIB[0] + 4, RIB[1] - 4, 84, 96, -8)
    p.paint(cav, hx("#1c1012"), bulge=-0.4, line=0, shadow=0)
    fl = poly([(492, 566), (498, 520), (512, 486), (524, 500), (532, 462), (544, 500), (556, 488), (560, 530),
               (566, 566), (530, 580)], smooth=True).blur(3)
    p.paint(fl, soul * 0.5, emit=soul * 0.8, unlit=1.0, bulge=0.2, line=0, shadow=0, mode="on")
    p.glow_on(fl.grow(-10).blur(6), core * 0.9)
    R.add("rib_core", p, "torso", "extra", RIB, 11)

    # ================= cape: tattered cloak streaming back from the shoulders
    p = R.part(depth=0.2)
    p.sss = 0.5
    cape = poly([(540, 390), (640, 392), (740, 440), (860, 520), (930, 600), (900, 596), (918, 650), (868, 626),
                 (872, 690), (826, 646), (812, 720), (770, 660), (740, 700), (712, 610), (650, 520), (570, 460)],
                smooth=False).blur(1.5)
    p.paint(cape, rag, grad=(sh(rag, 0.6), (600, 400), (880, 680)), tex="fbm", tex_amt=0.5, var=0.15, bulge=0.3)
    for pts in ([(620, 420), (720, 520), (790, 640)], [(660, 410), (780, 500), (870, 600)],
                [(600, 440), (680, 540), (730, 640)]):
        p.fold(pts, 22, 1.0, clip=cape)
        p.fold([(x + 20, y - 8) for x, y in pts], 14, -0.6, clip=cape)
    for i in range(10):
        rng = random.Random(i)
        x, y = rng.uniform(640, 900), rng.uniform(470, 660)
        p.paint(circle(x, y, rng.uniform(4, 9)), hx("#000000"), mode="tint", op=0.0)
    R.add("cape", p, "torso", "cape", (590, 410), 2)

    # ================= head and jaw
    p = R.part()
    p.sss = 0.25
    skull = union(ellipse(446, 292, 84, 80), poly([(374, 300), (366, 340), (384, 366), (470, 368), (510, 330)],
                                                  smooth=True))
    p.paint(skull, BONE, tex="pits", tex_amt=0.5, bump=0.6, spec=0.3, gloss=0.4)
    grime(p, skull, k=0.45)
    p.paint(ellipse(492, 318, 30, 36, -10), sh(BONE, 0.85), mode="on", bulge=0.5, line=0.3)  # cheekbone
    for (x, y), (rx, ry) in zip(EYES, ((26, 24), (21, 22))):
        p.paint(ellipse(x, y, rx, ry, -10), hx("#140a0a"), mode="on", bulge=-1.0, line=0.5, shadow=0)
        glow_eye(p, x, y + 2, rx * 0.42, ry * 0.36, soul, core, rot=-10)
    p.paint(poly([(420, 330), (436, 330), (432, 352), (422, 352)], smooth=True), hx("#140a0a"), mode="on",
            bulge=-0.8, line=0.4, shadow=0)
    for i, x in enumerate(range(392, 474, 12)):
        p.paint(poly([(x, 356), (x + 10, 356), (x + 9, 374), (x + 1, 374)], smooth=True), sh(BONE, 1.05),
                bulge=0.6, line=0.5, lw=1.2, shadow=0.3, sh_off=(1, 3), sh_blur=2, spec=0.4)
    p.fold([(474, 250), (466, 272), (478, 290), (470, 310)], 3, 1.0, clip=skull)
    # dented kettle helmet tipped over the brow
    hel = poly(ell(452, 262, 92, 86, -8, 180, 360))
    p.paint(hel, iron, metal=0.85, spec=0.9, gloss=0.55, tex="pits", tex_amt=0.4, bump=0.5, shadow=0.55, sh_off=(3, 10),
            sh_blur=6)
    rust_on(p, hel, 0.65)
    p.fold([(400, 200), (418, 214), (410, 230)], 10, 1.4, clip=hel)
    brim = ellipse(452, 262, 150, 24, -8)
    p.paint(brim, sh(iron, 0.9), grad=(sh(iron, 1.1), (300, 250), (600, 250)), metal=0.85, spec=0.9, gloss=0.55, tex="pits",
            tex_amt=0.4, bump=0.4, bulge=0.4, shadow=0.6, sh_off=(4, 12), sh_blur=8)
    rust_on(p, brim, 0.6)
    for x in (330, 392, 516, 574):
        rivet(p, x, 262 + (452 - x) * 0.14, 5, hx("#b0a090"))
    R.add("head", p, "torso", "head", (500, 386), 25)
    p = R.part()
    p.sss = 0.25
    jmaw = poly([(386, 364), (480, 364), (500, 380), (470, 420), (400, 422)], smooth=True)
    p.paint(jmaw, hx("#120808"), bulge=0.2, line=0.3)
    jaw = poly([(504, 350), (500, 392), (470, 428), (410, 440), (380, 426), (386, 408), (420, 412), (468, 396),
                (482, 362)], smooth=True)
    p.paint(jaw, BONE, tex="pits", tex_amt=0.5, bump=0.5, spec=0.3, gloss=0.4)
    grime(p, jaw)
    for x in range(392, 470, 12):
        p.paint(poly([(x + 1, 396 - (x - 392) * 0.12), (x + 10, 396 - (x - 392) * 0.12), (x + 9, 410),
                      (x + 2, 412)], smooth=True), sh(BONE, 0.98), bulge=0.6, line=0.5, lw=1.2, shadow=0.25,
                sh_off=(1, 3), sh_blur=2)
    R.add("jaw", p, "head", "jaw", (494, 360), 24)
    fx = R.fx()
    for (x, y), r in zip(EYES, (22, 18)):
        fx.glow(x, y + 2, r, soul, 1.0, core=core)
    # soul-fire streaming back from the sockets
    trail = poly(taper([(410, 300), (470, 286), (540, 280), (600, 262)], 26, 2))
    fx.mask_glow(trail, soul * 0.8, blur=5, k=0.9)
    fx.mask_glow(poly(taper([(414, 300), (480, 288), (540, 282)], 10, 1)), core * 0.8, blur=2, k=0.8)
    R.add("eye_fire", fx, "head", "fx", EYES[0], 26)

    # ================= legs: the front leg bent into the lunge, the back leg pushing off
    def leg(prefix, hip, knee, ankle, toe, heel, zu, zl, depth, col):
        p = R.part(depth=depth)
        bone(p, hip, knee, 30, col)
        p.paint(ellipse(knee[0], knee[1], 26, 20, 20), sh(rust, 0.9), spec=0.7, gloss=0.5, tex="pits", tex_amt=0.5,
                bump=0.5)  # rusty knee cop
        rust_on(p, ellipse(knee[0], knee[1], 26, 20, 20), 0.6)
        R.add(prefix + "_upper", p, "pelvis", prefix + "_upper", hip, zu)
        p = R.part(depth=depth)
        bone(p, knee, ankle, 24, col)
        bone(p, (knee[0] + 10, knee[1] + 10), (ankle[0] + 10, ankle[1] - 4), 10, sh(col, 0.85), knobs=(False, False))
        sab = poly([(ankle[0] + 26, ankle[1] - 10), heel, (toe[0] + 10, toe[1]), (toe[0] - 6, toe[1] - 8),
                    (toe[0] + 8, toe[1] - 30), (ankle[0] - 20, ankle[1] - 20)], smooth=True)
        p.paint(sab, rust, metal=0.5, spec=0.6, gloss=0.45, tex="pits", tex_amt=0.3, bump=0.3, shadow=0.4)
        rust_on(p, sab, 0.8)
        for f in (0.35, 0.6):
            x = heel[0] + (toe[0] - heel[0]) * f
            p.fold([(x, toe[1] - 30), (x - 4, toe[1] - 2)], 5, 0.9, clip=sab)
        rivet(p, ankle[0], ankle[1] - 6, 6, hx("#b8a088"))
        R.add(prefix + "_lower", p, prefix + "_upper", prefix + "_lower", knee, zl)

    leg("leg_back", (566, 616), (676, 760), (790, 910), (740, 968), (842, 964), 4, 5, 0.3, bone_d)
    leg("leg_front", (500, 616), (404, 764), (384, 920), (290, 968), (420, 966), 20, 21, 0.0, BONE)

    # ================= shield arm (far) and the battered round shield
    p = R.part(depth=0.3)
    bone(p, (470, 420), (408, 520), 24, bone_d)
    R.add("arm_back_upper", p, "torso", "arm_back_upper", (470, 420), 6)
    p = R.part(depth=0.3)
    bone(p, (408, 520), (326, 556), 20, bone_d)
    p.paint(ellipse(318, 558, 26, 20, 20), bone_d, tex="pits", tex_amt=0.4)
    R.add("arm_back_lower", p, "arm_back_upper", "arm_back_lower", (408, 520), 7)
    p = R.part()
    SC, SR = (300, 566), 158
    bite = poly([(150, 640), (186, 650), (172, 672), (196, 700), (160, 716), (130, 700)])
    disc = ellipse(SC[0], SC[1], SR * 0.9, SR, 8) - bite
    p.paint(disc, hx("#5e3e26"), tex="streak90", tex_amt=0.4, bump=0.6, bulge=0.25, spec=0.15, gloss=0.2,
            var=0.2, shadow=0.55, sh_off=(8, 14), sh_blur=10)
    for dx in (-80, -30, 20, 70):
        p.fold([(SC[0] + dx + 10, SC[1] - 170), (SC[0] + dx - 10, SC[1] + 170)], 5, 1.0, clip=disc)
    grime(p, disc, hx("#2a1c12"), 0.6)
    ring = disc - ellipse(SC[0], SC[1], SR * 0.9 - 22, SR - 22, 8)
    p.paint(ring, iron, metal=0.9, spec=1.0, gloss=0.6, tex="pits", tex_amt=0.4, bump=0.5, bulge=0.6, shadow=0.5,
            sh_off=(3, 6), sh_blur=4)
    rust_on(p, ring, 0.6)
    for a in range(0, 360, 36):
        t = math.radians(a)
        x, y = SC[0] + (SR * 0.9 - 11) * math.cos(t), SC[1] + (SR - 11) * math.sin(t)
        if not (150 < x < 200 and 630 < y < 720):
            rivet(p, x, y, 5, hx("#c0b0a0"))
    boss = ellipse(SC[0] - 6, SC[1] - 6, 48, 52, 8)
    p.paint(boss, iron, metal=0.95, spec=1.0, gloss=0.7, tex="pits", tex_amt=0.3, bulge=0.9, shadow=0.6, sh_off=(5, 9),
            sh_blur=6)
    rust_on(p, boss, 0.45)
    p.fold([(214, 450), (240, 486), (230, 520), (252, 560)], 5, 1.4, clip=disc)  # a split in the planks
    for x, y in ((230, 470), (360, 640), (402, 500)):
        p.paint(ellipse(x, y, 16, 10, 30), None, mode="bump", bulge=-0.9, clip=disc)  # sword notches
    R.add("shield", p, "arm_back_lower", "offhand", (322, 558), 30)

    # ================= sword arm (near), fist gripping a notched rusty blade held back at the shoulder
    p = R.part()
    bone(p, (574, 420), (648, 530), 26)
    R.add("arm_front_upper", p, "torso", "arm_front_upper", (574, 420), 32)
    p = R.part()
    bone(p, (648, 530), (626, 430), 22)
    bone(p, (656, 522), (636, 436), 9, bone_d, knobs=(False, False))
    fist = ellipse(620, 414, 30, 26, -20)
    p.paint(fist, BONE, tex="pits", tex_amt=0.4, bump=0.4, spec=0.3)
    for i in range(4):
        p.fold([(598, 398 + i * 9), (640, 404 + i * 9)], 4, 0.9, clip=fist)
    R.add("arm_front_lower", p, "arm_front_upper", "arm_front_lower", (648, 530), 34)
    p = R.part()
    G = (622, 408)
    tip = (744, 120)
    ux, uy = tip[0] - G[0], tip[1] - G[1]
    L = math.hypot(ux, uy)
    ux, uy = ux / L, uy / L
    nx, ny = -uy, ux
    b0 = (G[0] + ux * 44, G[1] + uy * 44)
    w = 17
    blade = poly([(b0[0] + nx * w, b0[1] + ny * w), (tip[0] - ux * 40 + nx * w * 0.8, tip[1] - uy * 40 + ny * w * 0.8),
                  tip, (tip[0] - ux * 40 - nx * w * 0.8, tip[1] - uy * 40 - ny * w * 0.8),
                  (b0[0] - nx * w, b0[1] - ny * w)])
    for t, d in ((70, 8), (130, 6), (190, 7)):
        x, y = b0[0] + ux * t + nx * w, b0[1] + uy * t + ny * w
        blade = blade - poly([(x - ux * d, y - uy * d), (x + ux * d, y + uy * d), (x - nx * d, y - ny * d)])
    p.paint(blade, hx("#9aa0a4"), grad=(hx("#c8ccd0"), (b0[0] - nx * w, b0[1]), (b0[0] + nx * w, b0[1])),
            spec=1.2, gloss=0.75, tex="streak60", tex_amt=0.35, bump=0.3, bulge=0.3, shadow=0)
    p.paint(poly([(b0[0] + nx * 3, b0[1] + ny * 3), (tip[0] - ux * 30, tip[1] - uy * 30),
                  (b0[0] - nx * 3, b0[1] - ny * 3)]), None, mode="bump", bulge=0.8)  # fuller ridge
    rust_on(p, blade, 0.55)
    guard = tube([(G[0] + ux * 40 + nx * 44, G[1] + uy * 40 + ny * 44), (G[0] + ux * 40 - nx * 44,
                                                                          G[1] + uy * 40 - ny * 44)], 16)
    p.paint(guard, hx("#6a4a32"), metal=0.6, spec=0.8, gloss=0.5, tex="pits", tex_amt=0.5)
    rust_on(p, guard, 0.5)
    p.paint(tube([(G[0] - ux * 36, G[1] - uy * 36), (G[0] + ux * 36, G[1] + uy * 36)], 16), leath, tex="fbm",
            tex_amt=0.5)
    p.paint(circle(G[0] - ux * 44, G[1] - uy * 44, 13), hx("#7a5a3a"), metal=0.7, spec=0.9, gloss=0.6)
    R.add("sword", p, "arm_front_lower", "weapon", G, 33)
    return R


# =============================================================== main

RIGS = {
    "cellar_rat": cellar_rat,
    "skeleton_guard": skeleton_guard,
}
BOSSES = {"bone_king"}
SHEETS = os.path.join("/tmp", "claude-0", "monsters_d1")


def build(rid, sheet_dir=None):
    t = time.time()
    R = RIGS[rid]()
    R.save(flat_size=768 if rid in BOSSES else 512)
    if sheet_dir:
        os.makedirs(sheet_dir, exist_ok=True)
        rig.pose_sheet(rid, os.path.join(sheet_dir, f"rig_{rid}.png"))
    print(f"{rid}: {time.time() - t:.1f}s")


def main(ids=None, sheet_dir=None):
    for rid in ids or list(RIGS):
        build(rid, sheet_dir)
        _NOISE.clear()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sheet = next((a[8:] for a in sys.argv[1:] if a.startswith("--sheet=")), None)
    main(args or None, sheet)

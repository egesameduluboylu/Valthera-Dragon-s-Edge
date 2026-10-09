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


# =============================================================== cellar warden

def cloth(p, m, col, folds=(), seed=1, grad=None, bulge=0.45, tex_amt=0.45, var=0.15, **kw):
    """Heavy, worn cloth: blotchy weave, soft dome and creases along the given paths (path, width)."""
    kw.setdefault("spec", 0.08)
    kw.setdefault("gloss", 0.2)
    p.paint(m, col, tex="fbm", tex_amt=tex_amt, var=var, bump=0.25, bump_tex="grain", bulge=bulge, grad=grad,
            **kw)
    for path, w in folds:
        p.fold(path, w, 1.0, clip=m)
        p.fold([(x + w * 0.55, y - w * 0.2) for x, y in path], w * 0.6, -0.55, clip=m)
    return m


def leather(p, m, col, grad=None, bulge=0.5, **kw):
    kw.setdefault("spec", 0.35)
    kw.setdefault("gloss", 0.45)
    p.paint(m, col, tex="pits", tex_amt=0.4, var=0.18, bump=0.35, bulge=bulge, grad=grad, **kw)
    return m


def iron_p(p, m, col, rust=0.5, bulge=0.6, **kw):
    kw.setdefault("spec", 0.95)
    kw.setdefault("gloss", 0.6)
    kw.setdefault("metal", 0.85)
    p.paint(m, col, tex="pits", tex_amt=0.4, bump=0.45, bulge=bulge, var=0.1, **kw)
    if rust:
        rust_on(p, m, rust)
    return m


def stitches(p, path, col, every=14, w=10):
    c = cr(path, n=8)
    k = max(2, int(plen(c) / every))
    for i in range(k + 1):
        (x, y), (tx, ty) = at(c, i / k)
        p.paint(tube([(x - ty * w * 0.5 - tx * 2, y + tx * w * 0.5 - ty * 2),
                      (x + ty * w * 0.5 + tx * 2, y - tx * w * 0.5 + ty * 2)], 2.6), col, mode="on", bulge=0.6,
                line=0, shadow=0.35, sh_off=(1, 2), sh_blur=1.2)


def fist(p, c, ang, s, skin, knuckle=True):
    """A clenched fist seen from the knuckle side: a blocky mass with four knuckle ridges and a thumb."""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    m = poly(cr([(c[0] - ux * s * 0.5 - nx * s * 0.55, c[1] - uy * s * 0.5 - ny * s * 0.55),
                 (c[0] + ux * s * 0.55 - nx * s * 0.5, c[1] + uy * s * 0.55 - ny * s * 0.5),
                 (c[0] + ux * s * 0.62 + nx * s * 0.45, c[1] + uy * s * 0.62 + ny * s * 0.45),
                 (c[0] - ux * s * 0.45 + nx * s * 0.6, c[1] - uy * s * 0.45 + ny * s * 0.6)], closed=True, n=8))
    p.sss = max(p.sss, 0.6)
    p.paint(m, skin, tex="pits", tex_amt=0.3, bump=0.3, spec=0.3, gloss=0.4, bulge=0.6)
    if knuckle:
        for i in range(4):
            k = (i - 1.5) / 1.5
            q = (c[0] + ux * s * 0.42 + nx * k * s * 0.42, c[1] + uy * s * 0.42 + ny * k * s * 0.42)
            p.paint(ellipse(q[0], q[1], s * 0.16, s * 0.13, ang), sh(skin, 1.08), mode="on", bulge=0.9, line=0.25,
                    shadow=0.3, sh_off=(1, 2), sh_blur=1.5, spec=0.35, gloss=0.4)
            if i < 3:
                q2 = (c[0] + ux * s * 0.15 + nx * (k + 0.33) * s * 0.42, c[1] + uy * s * 0.15 + ny * (k + 0.33) * s * 0.42)
                p.fold([(q2[0] + ux * s * 0.3, q2[1] + uy * s * 0.3), q2], 3, 0.9, clip=m)
    th = (c[0] - ux * s * 0.1 - nx * s * 0.55, c[1] - uy * s * 0.1 - ny * s * 0.55)
    p.paint(tube([th, (th[0] + ux * s * 0.45 - nx * s * 0.05, th[1] + uy * s * 0.45 - ny * s * 0.05)], s * 0.3, s * 0.24),
            sh(skin, 1.02), spec=0.3, gloss=0.4, line=0.4, shadow=0.35, sh_off=(2, 3), sh_blur=2)
    return m


def cellar_warden():
    """Elite: the Cellar Warden, a hulking hooded jailer. A deep maroon executioner's hood with a drooping
    peak hides all but a stubbled, scarred jaw and a crooked grimace; two amber eyes burn in the dark. A
    stained linen shirt strains over the gut under a leather apron and a crossing iron chain, a spiked
    pauldron sits on the axe shoulder, a ring of iron and brass keys hangs at the belt. He hefts a huge
    bearded axe back over his shoulder and swings a length of chain with an open shackle in the other fist
    (faces left)."""
    amber = np.array([1.0, 0.6, 0.12], F32)
    core = np.array([1.0, 0.93, 0.62], F32)
    EYES = [(384, 262), (434, 256)]
    look = Look(**CELLAR, lights=[(410, 268, 34, (1.0, 0.5, 0.14), 34, 0.9)], falloff=(520, 600, 440, 0.34))
    R = Rig("cellar_warden", 1024, (520, 968), "humanoid", look)
    hood_c = hx("#42201e")
    shirt = hx("#7a6a56")
    leath = hx("#5a3c26")
    apron_c = hx("#6a4630")
    skin = hx("#9a6c5c")
    iron = hx("#6a7078")
    trous = hx("#3e3432")
    boot = hx("#3a2a20")
    brass = hx("#b8893a")
    wood = hx("#5a3a22")

    # ================= hips (root): trousers seat
    p = R.part()
    hips = poly([(370, 624), (520, 612), (646, 626), (668, 700), (650, 770), (520, 784), (384, 772), (356, 700)],
                smooth=True)
    cloth(p, hips, trous, folds=[([(420, 700), (460, 760)], 12), ([(600, 690), (580, 760)], 12)], seed=1)
    R.add("hips", p, "", "root", (512, 690), 10)

    # ================= torso: barrel chest and gut in a stained shirt, apron bib, crossing chain, hood cowl
    p = R.part()
    p.sss = 0.4
    body = union(poly([(344, 380), (420, 336), (520, 330), (610, 346), (660, 400), (676, 480), (668, 560),
                       (650, 640), (600, 668), (420, 670), (374, 630), (350, 560), (336, 470)], smooth=True),
                 ellipse(386, 404, 58, 52), ellipse(612, 404, 62, 54))
    cloth(p, body, shirt, grad=(sh(shirt, 1.05), (400, 360), (640, 660)),
          folds=[([(380, 470), (420, 520), (440, 600)], 16), ([(470, 380), (500, 430), (520, 470)], 12),
                 ([(640, 470), (620, 540), (630, 620)], 16), ([(560, 600), (600, 640)], 12)], seed=2)
    p.paint(ellipse(520, 600, 150, 76) & body, None, mode="bump", bulge=0.5)   # the gut
    stain = poly([(560, 500), (650, 520), (660, 600), (600, 640), (560, 590)], smooth=True).blur(10)
    p.paint(stain & body, hx("#4a3824"), mode="tint", op=0.5, tex="fbm", tex_amt=0.6)
    # apron bib and its neck strap
    bib = poly([(436, 452), (586, 446), (606, 560), (612, 668), (420, 672), (424, 560)], smooth=True)
    leather(p, bib, apron_c, grad=(sh(apron_c, 1.1), (440, 450), (600, 670)), shadow=0.5, sh_off=(4, 7))
    stitches(p, [(446, 462), (436, 560), (432, 660)], hx("#2a1c12"))
    stitches(p, [(576, 458), (596, 560), (600, 660)], hx("#2a1c12"))
    for x, y in ((448, 462), (574, 456)):
        rivet(p, x, y, 6, hx("#9a8a70"))
    for pts in ([(446, 456), (430, 400), (452, 350)], [(574, 450), (580, 396), (556, 350)]):
        leather(p, tube(pts, 18), leath, shadow=0.45, sh_off=(2, 5))
    blood = poly([(470, 560), (520, 548), (548, 590), (530, 640), (490, 630)], smooth=True).blur(6)
    p.paint(blood & bib, hx("#3a1410"), mode="on", bulge=0.1, spec=0.7, gloss=0.7, line=0, shadow=0, op=0.7)
    # a heavy iron chain slung from the axe shoulder across to the far hip
    chain(p, [(624, 372), (560, 440), (480, 540), (396, 640)], 30, iron)
    # the hood's cowl draped over the shoulders
    cowl = poly([(350, 372), (400, 334), (470, 322), (560, 324), (620, 346), (636, 384), (592, 410), (520, 400),
                 (460, 410), (396, 420)], smooth=True)
    cloth(p, cowl, hood_c, folds=[([(420, 340), (430, 400)], 14), ([(560, 336), (580, 396)], 14)], seed=3,
          shadow=0.55, sh_off=(4, 10), sh_blur=8)
    p.fringe(cowl, sh(hood_c, 0.85), 95, 70, 14, 7, seed=5, outward=0.6, band=(0.3, 0.6))
    R.add("torso", p, "hips", "torso", (512, 660), 12)

    # ================= cape: the cowl's long ragged back flap
    p = R.part(depth=0.2)
    p.sss = 0.5
    cape = poly([(560, 330), (640, 350), (700, 420), (734, 520), (752, 630), (720, 610), (726, 676), (690, 640),
                 (680, 700), (652, 640), (628, 520), (590, 420)], smooth=False).blur(1.5)
    cloth(p, cape, sh(hood_c, 0.85), grad=(sh(hood_c, 0.9), (600, 350), (720, 680)),
          folds=[([(640, 380), (690, 500), (710, 620)], 20), ([(610, 400), (650, 520), (670, 640)], 16)], seed=4)
    R.add("cape", p, "torso", "cape", (600, 370), 2)

    # ================= legs: heavy trousers and iron-capped boots in a wide stance
    def leg(prefix, hip, knee, ankle, toe_x, zu, zl, depth, col):
        p = R.part(depth=depth)
        m = tube([hip, ((hip[0] + knee[0]) / 2 + 6, (hip[1] + knee[1]) / 2), knee], 104, 82)
        cloth(p, m, col, folds=[([(hip[0] - 10, hip[1] + 40), (knee[0] + 14, knee[1] - 20)], 10),
                                ([(knee[0] - 30, knee[1] - 10), (knee[0] + 20, knee[1] + 6)], 10)], seed=hip[0])
        R.add(prefix + "_upper", p, "hips", prefix + "_upper", hip, zu)
        p = R.part(depth=depth)
        m = tube([knee, ankle], 80, 66)
        cloth(p, m, col, folds=[([(knee[0] - 20, knee[1] + 30), (ankle[0] + 10, ankle[1] - 30)], 9)], seed=knee[0])
        bt = poly([(ankle[0] - 40, ankle[1] - 52), (ankle[0] + 38, ankle[1] - 56), (ankle[0] + 46, ankle[1] + 12),
                   (ankle[0] + 50, 966), (toe_x + 6, 970), (toe_x - 6, 950), (toe_x + 20, ankle[1] + 14),
                   (ankle[0] - 44, ankle[1] + 2)], smooth=True)
        leather(p, bt, boot, grad=(sh(boot, 1.15), (ankle[0], ankle[1] - 50), (ankle[0], 970)), shadow=0.5)
        p.fold([(ankle[0] - 40, ankle[1] - 20), (ankle[0] + 40, ankle[1] - 24)], 8, 0.9, clip=bt)
        p.fold([(ankle[0] - 30, ankle[1] + 4), (ankle[0] + 10, ankle[1] + 8)], 6, 0.9, clip=bt)
        cap = poly([(toe_x - 6, 950), (toe_x + 6, 970), (toe_x + 64, 970), (toe_x + 58, 930), (toe_x + 20, 932)],
                   smooth=True)
        iron_p(p, cap & bt.grow(2), iron, rust=0.6)
        leather(p, tube([(ankle[0] - 44, ankle[1] - 40), (ankle[0] + 44, ankle[1] - 44)], 14), leath, line=0.4)
        rivet(p, ankle[0] + 2, ankle[1] - 42, 6, hx("#9a8a70"))
        p.paint(tube([(toe_x - 4, 968), (ankle[0] + 50, 968)], 8), hx("#1e1410"), spec=0.1, line=0.3, shadow=0)
        R.add(prefix + "_lower", p, prefix + "_upper", prefix + "_lower", knee, zl)

    leg("leg_back", (588, 716), (640, 842), (654, 920), 594, 3, 4, 0.3, sh(trous, 0.92))
    leg("leg_front", (448, 716), (412, 842), (402, 920), 318, 18, 19, 0.0, trous)

    # ================= apron skirt and belt (extra on the hips, over the thighs)
    p = R.part()
    ap = poly([(394, 640), (512, 650), (620, 640), (636, 740), (648, 860), (610, 876), (574, 862), (530, 884),
               (480, 866), (440, 880), (400, 862), (384, 770)], smooth=True)
    leather(p, ap, apron_c, grad=(sh(apron_c, 1.08), (400, 650), (620, 880)), bulge=0.3, shadow=0.55,
            sh_off=(5, 10), sh_blur=8)
    for pts, w in (([(440, 680), (430, 780), (436, 870)], 14), ([(520, 690), (526, 790), (530, 880)], 16),
                   ([(590, 680), (606, 780), (612, 862)], 14)):
        p.fold(pts, w, 1.0, clip=ap)
        p.fold([(x + 14, y) for x, y in pts], 9, -0.6, clip=ap)
    p.paint(poly([(470, 720), (560, 730), (580, 820), (500, 840), (460, 790)], smooth=True).blur(8) & ap,
            hx("#341410"), mode="on", bulge=0.0, spec=0.75, gloss=0.75, op=0.65, line=0, shadow=0)
    grime(p, ap, hx("#2a1a10"), 0.55)
    stitches(p, [(404, 858), (480, 862), (560, 860), (640, 852)], hx("#2a1c12"), every=16)
    belt = tube([(366, 650), (512, 668), (662, 650)], 40)
    leather(p, belt, leath, shadow=0.5, sh_off=(3, 7))
    stitches(p, [(372, 638), (512, 654), (656, 638)], hx("#d0b080"), every=18, w=4)
    bk = poly([(474, 640), (520, 642), (522, 694), (474, 692)], smooth=False)
    iron_p(p, bk, iron, rust=0.4)
    p.paint(poly([(484, 652), (512, 652), (512, 684), (484, 684)]), hx("#2a1c14"), mode="on", bulge=-0.5, line=0.3)
    p.paint(tube([(492, 668), (532, 666)], 7), sh(iron, 1.1), spec=1.0, gloss=0.6, metal=0.8, line=0.4, shadow=0.3)
    for x in (400, 440, 580, 622):
        rivet(p, x, 654 + abs(x - 512) * -0.1, 5, hx("#9a8a70"))
    R.add("apron", p, "hips", "extra", (512, 660), 22)

    # ================= key ring jingling at the hip
    p = R.part()
    RC = (404, 712)
    ring = ellipse(RC[0], RC[1], 30, 26, 10) - ellipse(RC[0], RC[1], 22, 18, 10)
    iron_p(p, tube([(400, 660), (404, 690)], 9), leath, rust=0, metal=0, spec=0.3)
    keys = [(-30, 76, iron), (-12, 92, brass), (8, 84, iron), (26, 70, brass), (-44, 60, brass)]
    for ang, L, col in keys:
        a = math.radians(90 + ang)
        b0 = (RC[0] + math.cos(a) * 24, RC[1] + math.sin(a) * 22)
        e = (b0[0] + math.cos(a) * L, b0[1] + math.sin(a) * L)
        bow = ellipse(b0[0] + math.cos(a) * 10, b0[1] + math.sin(a) * 10, 11, 9, ang) - \
            ellipse(b0[0] + math.cos(a) * 10, b0[1] + math.sin(a) * 10, 5, 4, ang)
        shaft = tube([(b0[0] + math.cos(a) * 18, b0[1] + math.sin(a) * 18), e], 7, 6)
        bit = poly([(e[0] - math.sin(a) * 2, e[1] + math.cos(a) * 2),
                    (e[0] - math.sin(a) * 16, e[1] + math.cos(a) * 16),
                    (e[0] - math.sin(a) * 16 - math.cos(a) * 16, e[1] + math.cos(a) * 16 - math.sin(a) * 16),
                    (e[0] - math.cos(a) * 18, e[1] - math.sin(a) * 18)])
        iron_p(p, bow | shaft | bit, col, rust=0.35 if col is iron else 0.0, line=0.6, lw=1.2, shadow=0.45,
               sh_off=(3, 5), sh_blur=3)
    iron_p(p, ring, sh(iron, 1.05), rust=0.3, shadow=0.45, sh_off=(3, 5), sh_blur=3)
    R.add("keys", p, "hips", "hair", (402, 668), 24)

    # ================= far arm, low and forward, swinging a chain with an open shackle
    p = R.part(depth=0.25)
    p.sss = 0.4
    cloth(p, tube([(384, 404), (346, 470), (318, 528)], 96, 80), sh(shirt, 0.9),
          folds=[([(380, 440), (340, 500)], 10)], seed=6)
    R.add("arm_back_upper", p, "torso", "arm_back_upper", (384, 404), 6)
    p = R.part(depth=0.25)
    p.sss = 0.6
    fa = tube([(318, 528), (304, 580), (294, 624)], 74, 62)
    p.paint(fa, skin, tex="pits", tex_amt=0.3, bump=0.3, spec=0.25, gloss=0.35, bulge=0.6)
    fur(p, fa, sh(skin, 0.7), 100, 120, 61, length=10, width=2.4, alpha=0.4, bump=0.3)
    br = tube([(312, 552), (298, 612)], 80, 72, caps=False)
    leather(p, br, leath, shadow=0.45)
    for t in (0.25, 0.75):
        p.fold([(270, 552 + t * 60), (344, 560 + t * 60)], 5, 0.9, clip=br)
    fist(p, (294, 650), 100, 56, skin)
    R.add("arm_back_lower", p, "arm_back_upper", "arm_back_lower", (318, 528), 8)
    p = R.part()
    chain(p, [(292, 664), (284, 724), (270, 786), (276, 820)], 26, iron)
    sh_m = (ellipse(280, 858, 40, 30, -10) - ellipse(280, 858, 26, 17, -10)) - poly([(236, 862), (262, 850), (250, 900)])
    iron_p(p, sh_m, iron, rust=0.6, shadow=0.45)
    iron_p(p, ellipse(318, 846, 14, 10, -10), sh(iron, 0.9), rust=0.5)
    R.add("shackle", p, "arm_back_lower", "offhand", (294, 650), 7)

    # ================= head: the hood, the dark face opening, burning eyes and a scarred, stubbled jaw
    p = R.part()
    p.sss = 0.5
    hood = poly([(346, 330), (330, 260), (346, 196), (392, 148), (460, 128), (526, 146), (566, 196), (580, 262),
                 (570, 330), (540, 378), (470, 392), (396, 384)], smooth=True)
    cloth(p, hood, hood_c, grad=(sh(hood_c, 1.15), (380, 150), (560, 380)),
          folds=[([(470, 150), (520, 220), (548, 320)], 18), ([(420, 156), (500, 196)], 12),
                 ([(540, 200), (556, 300)], 12)], seed=7, shadow=0.5)
    stitches(p, [(470, 132), (520, 170), (556, 230)], hx("#2a1414"), every=13, w=9)
    opening = ellipse(406, 274, 66, 86, -12)
    p.paint(opening, hx("#120808"), grad=(hx("#241010"), (380, 200), (410, 340)), mode="on", bulge=-0.6,
            line=0.4, shadow=0, spec=0.05)
    lip = opening.grow(7) - opening.grow(-3)
    cloth(p, lip & hood, sh(hood_c, 1.12), bulge=0.9, rnd=6, mode="on", line=0.3, shadow=0.5, sh_off=(4, 6),
          sh_blur=4)
    # brow shadow, eyes
    for (x, y), (rx, ry) in zip(EYES, ((15, 9), (13, 8))):
        glow_eye(p, x, y, rx * 0.8, ry * 0.65, amber, core, rot=-8, socket=hx("#0a0404"))
    p.paint(poly([(352, 238), (456, 226), (452, 244), (356, 254)], smooth=True), hx("#1a0c0a"), mode="on",
            bulge=0.6, line=0, shadow=0.5, sh_off=(0, 4), sh_blur=3, op=0.95)
    # the jaw lit from below by the eyes
    jaw = poly([(364, 312), (410, 308), (452, 310), (458, 332), (440, 356), (404, 362), (372, 352), (360, 334)],
               smooth=True)
    p.sss = 0.7
    p.paint(jaw, sh(skin, 0.42), grad=(sh(skin, 0.6), (400, 300), (400, 368)), mode="on", tex="pits",
            tex_amt=0.5, bump=0.5, bulge=0.7, spec=0.25, gloss=0.4, line=0.4, shadow=0.4)
    rng = random.Random(9)
    for i in range(110):
        x, y = rng.uniform(358, 460), rng.uniform(316, 364)
        if jaw.crop((int(x * SS), int(y * SS), int(x * SS) + 1, int(y * SS) + 1))[0, 0] > 0.5:
            p.paint(circle(x, y, 1.3), hx("#1a100c"), mode="on", bulge=0, line=0, shadow=0, op=0.8)
    mouth = poly([(370, 326), (410, 322), (448, 318), (446, 334), (410, 340), (376, 340)], smooth=True)
    p.paint(mouth, hx("#160606"), mode="on", bulge=-0.7, line=0.4, shadow=0)
    for i, x in enumerate((380, 394, 410, 426, 438)):
        h = (10, 7, 11, 6, 9)[i]
        p.paint(poly([(x, 324 - i * 1), (x + 10, 323 - i * 1), (x + 9, 324 + h), (x + 2, 325 + h)], smooth=True),
                hx("#8e7a56"), mode="on", bulge=0.6, line=0.4, lw=1.0, shadow=0.3, sh_off=(1, 2), sh_blur=1,
                spec=0.5, gloss=0.5)
    p.paint(tube([(426, 300), (434, 334), (444, 362)], 5, 3), sh(skin, 0.95), mode="on", bulge=1.0, line=0.3)
    R.add("head", p, "torso", "head", (462, 372), 25)
    # hood peak flopping behind
    p = R.part()
    p.sss = 0.5
    tip = tube([(512, 164), (566, 176), (606, 222), (624, 290), (616, 336)], [70, 56, 36, 20, 8])
    cloth(p, tip, sh(hood_c, 0.95), grad=(sh(hood_c, 1.1), (520, 160), (616, 330)),
          folds=[([(540, 172), (590, 220), (606, 280)], 10)], seed=8, shadow=0.5)
    R.add("hood_tip", p, "head", "hair", (520, 176), 24)

    # ================= near arm hefting the axe back over the shoulder
    p = R.part()
    p.sss = 0.4
    cloth(p, tube([(604, 404), (650, 476), (684, 540)], 100, 84), shirt, folds=[([(610, 440), (660, 520)], 12)],
          seed=9)
    pd = poly(ell(616, 396, 70, 54, 20, 180, 360) + ell(616, 404, 70, 22, 20, 0, 180))
    for i, (sx, sy, a) in enumerate(((566, 360, -120), (612, 342, -95), (660, 356, -60))):
        r = math.radians(a)
        spk = poly([(sx - math.sin(r) * 14, sy + math.cos(r) * 14), (sx + math.cos(r) * 52, sy + math.sin(r) * 52),
                    (sx + math.sin(r) * 14, sy - math.cos(r) * 14)])
        iron_p(p, spk, sh(iron, 1.05), rust=0.5, shadow=0.4, bulge=0.8)
    iron_p(p, pd, iron, rust=0.7, shadow=0.55, sh_off=(4, 9), sh_blur=6)
    iron_p(p, poly(ell(618, 418, 64, 22, 20, 160, 380) + ell(618, 424, 64, 9, 20, 20, 160)), sh(iron, 0.9),
           rust=0.6, shadow=0.4)
    for x, y in ((566, 380), (612, 362), (660, 384)):
        rivet(p, x, y, 5, hx("#b0a090"))
    R.add("arm_front_upper", p, "torso", "arm_front_upper", (604, 404), 32)
    p = R.part()
    p.sss = 0.6
    fa = tube([(684, 540), (676, 490), (660, 446)], 82, 68)
    p.paint(fa, skin, tex="pits", tex_amt=0.3, bump=0.3, spec=0.25, gloss=0.35, bulge=0.6)
    fur(p, fa, sh(skin, 0.7), -100, 120, 62, length=10, width=2.4, alpha=0.4, bump=0.3)
    br = tube([(682, 520), (670, 470)], 88, 80, caps=False)
    leather(p, br, leath, shadow=0.45)
    stitches(p, [(642, 500), (722, 492)], hx("#d0b080"), every=14, w=4)
    fist(p, (656, 432), -80, 60, skin)
    R.add("arm_front_lower", p, "arm_front_upper", "arm_front_lower", (684, 540), 34)

    # ================= the axe
    p = R.part()
    G = (656, 432)
    T = (708, 92)
    ux, uy = T[0] - G[0], T[1] - G[1]
    L = math.hypot(ux, uy)
    ux, uy = ux / L, uy / L
    nx, ny = uy, -ux                       # toward the hero (left)

    def hp(s, d):
        return (G[0] + ux * s + nx * d, G[1] + uy * s + ny * d)

    haft = tube([hp(-176, 0), hp(370, 0)], 20, 18)
    p.paint(haft, wood, grad=(sh(wood, 1.2), hp(-176, -10), hp(-176, 10)), tex="streak80", tex_amt=0.5, bump=0.4,
            spec=0.25, gloss=0.35, bulge=0.7, shadow=0)
    for s0 in (-60, 60):
        wrap = tube([hp(s0 - 22, 0), hp(s0 + 22, 0)], 24, caps=False)
        leather(p, wrap, leath, line=0.4, shadow=0.3)
        for i in range(5):
            p.fold([hp(s0 - 18 + i * 9, -12), hp(s0 - 14 + i * 9, 12)], 3, 0.9, clip=wrap)
    iron_p(p, circle(*hp(-182, 0), 16), iron, rust=0.5)
    edge = cr([hp(392, 196), hp(320, 232), hp(236, 232), hp(130, 196)], n=10)
    inner = cr([hp(130, 196), hp(170, 128), hp(200, 60), hp(212, 0)], n=8)
    blade = poly([hp(326, -8), hp(360, 70)] + edge + inner[1:] + [hp(214, -8)])
    iron_p(p, blade, hx("#7a8088"), rust=0.45, bulge=0.25, rnd=30, shadow=0.5, sh_off=(6, 10), sh_blur=8,
           spec=1.1, gloss=0.7)
    p.paint(blade.grow(-10), None, mode="bump", bulge=0.25)
    bev = blade - blade.shift(int(round(-nx * 18)), int(round(-ny * 18)))
    p.paint(bev, hx("#c4cad0"), mode="on", bulge=0.5, rnd=6, spec=1.3, gloss=0.85, metal=0.9, line=0.25, shadow=0,
            tex="streak0", tex_amt=0.3)
    for (s, d) in ((320, 226), (262, 232), (180, 206)):
        x, y = hp(s, d)
        p.paint(poly([(x + nx * 4, y + ny * 4), (x - nx * 16 + ux * 7, y - ny * 16 + uy * 7),
                      (x - nx * 16 - ux * 7, y - ny * 16 - uy * 7)]), None, mode="bump", bulge=-0.9, clip=blade)
    p.paint(poly(cr([hp(300, 40), hp(270, 120), hp(236, 140), hp(220, 90)], closed=True)).blur(6) & blade,
            hx("#3a1410"), mode="on", bulge=0.05, spec=0.6, gloss=0.6, op=0.55, line=0, shadow=0)
    socket = poly([hp(206, -26), hp(330, -24), hp(334, 26), hp(204, 24)], smooth=False)
    iron_p(p, socket, iron, rust=0.6, shadow=0.5)
    spike = poly([hp(290, -20), hp(268, -86), hp(246, -20)])
    iron_p(p, spike, sh(iron, 1.05), rust=0.4)
    for s in (220, 262, 312):
        rivet(p, *hp(s, 0), 6, hx("#b0a090"))
    iron_p(p, poly([hp(366, -12), hp(400, 0), hp(366, 12)]), iron, rust=0.4)
    R.add("axe", p, "arm_front_lower", "weapon", G, 33)

    # ================= fx: burning eyes
    fx = R.fx()
    for (x, y), r in zip(EYES, (18, 15)):
        fx.glow(x, y, r, amber, 0.95, core=core)
    fx.glow(410, 262, 70, amber * 0.6, 0.22)
    R.add("eye_glow", fx, "head", "fx", (410, 262), 40)
    return R


# =============================================================== mimic

def planks(p, q, col, rows, seed, tex="streak0", grad=None, shade=(1.0, 1.0), **kw):
    """A wooden face (quad q) made of `rows` planks: grain, per-plank tint, sunk seams and worn edges."""
    m = poly(q)
    p.paint(m, col, tex=tex, tex_amt=0.55, bump=0.55, bump_tex=tex, var=0.2, bulge=0.12, rnd=40, spec=0.18,
            gloss=0.3, grad=grad, **kw)
    rng = random.Random(seed)
    for i in range(rows):
        v0, v1 = i / rows, (i + 1) / rows
        pm = poly(qsub(q, 0, v0, 1, v1))
        p.paint(pm.grow(-2), sh(col, rng.uniform(0.82, 1.12)), mode="tint", op=0.45, tex=tex, tex_amt=0.6)
        p.paint(pm.grow(-3), None, mode="bump", bulge=0.35, rnd=8)
        if i:
            p.fold([quad(q, 0, v0), quad(q, 1, v0)], 6, 1.0, clip=m)
    for k in range(5):           # knots and gouges
        u, v = rng.uniform(0.15, 0.85), rng.uniform(0.1, 0.9)
        x, y = quad(q, u, v)
        p.paint(ellipse(x, y, rng.uniform(6, 11), rng.uniform(3, 6), rng.uniform(-10, 10)), sh(col, 0.5),
                mode="on", bulge=-0.6, line=0.3, shadow=0, clip=m)
    grime(p, m, hx("#22160c"), 0.5)
    return m


def gold_p(p, m, col=hx("#c8952e"), **kw):
    kw.setdefault("bulge", 0.6)
    p.paint(m, col, metal=0.9, spec=1.1, gloss=0.7, tex="pits", tex_amt=0.3, bump=0.3, var=0.08, **kw)
    return m


def mimic():
    """A treasure chest that is really a mouth. The domed lid (its upper jaw) gapes on a wet red maw ringed
    with yellowed fangs, a gold glint of bait deep in the throat; two slit-pupilled yellow eyes glare from
    the lid front under carved, scowling brows. Iron-banded oak planks, gold corner fittings and a gold
    lock plate; a long glistening tongue lolls out over the rim to the floor, drool strings from the fangs,
    and four gnarled clawed legs grip the ground under the box (faces left)."""
    yel = np.array([1.0, 0.78, 0.15], F32)
    core = np.array([1.0, 0.96, 0.7], F32)
    hot = np.array([1.0, 0.3, 0.08], F32)
    L = [(248, 290), (570, 276), (592, 392), (230, 412)]       # lid front panel
    F = [(236, 592), (590, 612), (586, 906), (246, 884)]        # box front
    S = [(590, 612), (742, 542), (738, 832), (586, 906)]        # box side (away from the light)
    E1, E2 = quad(L, 0.28, 0.5), quad(L, 0.68, 0.47)
    look = Look(**CELLAR, lights=[(E1[0], E1[1], 30, (1.0, 0.7, 0.15), 50, 0.9),
                                  (E2[0], E2[1], 30, (1.0, 0.7, 0.15), 50, 0.9),
                                  (450, 530, 30, (1.0, 0.3, 0.1), 120, 1.0)], falloff=(480, 600, 460, 0.3))
    R = Rig("mimic", 1024, (490, 968), "beast", look)
    wood = hx("#634028")
    iron = hx("#5c626a")
    flesh = hx("#7a1a26")
    gum = hx("#9a3444")
    tooth = hx("#d8c69a")
    tong = hx("#b45664")
    legc = hx("#3e2c2a")
    claw_c = hx("#c2ac84")

    # ================= legs (behind the box)
    def leg(name, role, path, w0, w1, depth, z, foot_ang):
        p = R.part(depth=depth)
        p.sss = 0.5
        m = tube(path, w0, w1)
        p.paint(m, legc, grad=(sh(legc, 0.7), path[0], path[-1]), tex="pits", tex_amt=0.5, bump=0.6, spec=0.45,
                gloss=0.5, bulge=0.7)
        c = cr(path, n=8)
        for t in (0.3, 0.45, 0.62, 0.78):
            (x, y), (tx, ty) = at(c, t)
            w = (w0 + (w1 - w0) * t) * 0.5
            p.fold([(x - ty * w, y + tx * w), (x + tx * 4, y + ty * 4), (x + ty * w, y - tx * w)], 4, 0.9, clip=m)
        fx_, fy = path[-1]
        for k in (-1, 0, 1):
            claw(p, (fx_ + k * w1 * 0.32, fy + 2), foot_ang + k * 28, w1 * 1.1, w1 * 0.36, claw_c, curl=0.4,
                 tip=hx("#efe4c8"))
        R.add(name, p, "body", role, path[0], z)

    # ================= body (root): the maw, the box, the rim of gums and the lower fangs
    p = R.part()
    gape = poly([(250, 598), (252, 478), (420, 452), (600, 440), (744, 532), (742, 566), (590, 618)], smooth=False).blur(1)
    p.paint(gape, flesh, grad=(hx("#2a0408"), (430, 470), (430, 600)), spec=0.7, gloss=0.6, bulge=-0.4,
            tex="fbm", tex_amt=0.4, line=0.4)
    throat = ellipse(470, 520, 150, 52, -6).blur(18)
    p.paint(throat, hx("#060102"), mode="tint", op=0.9)
    for i in range(5):
        x = 300 + i * 80
        p.fold([(x, 470), (x + 30, 540), (x + 20, 600)], 12, -0.7, clip=gape)
    rng = random.Random(3)
    for i in range(7):   # bait: coins glinting in the throat
        x, y = 420 + rng.uniform(-60, 80), 524 + rng.uniform(-14, 18)
        gold_p(p, ellipse(x, y, 13, 6, rng.uniform(-20, 20)), mode="on", emit=(0.25, 0.14, 0.02), line=0.3,
               shadow=0.3, sh_off=(1, 2), sh_blur=1.5)
    planks(p, S, sh(wood, 0.7), 4, 2, grad=(sh(wood, 0.62), (600, 700), (740, 700)), shadow=0)
    planks(p, F, wood, 4, 1, grad=(sh(wood, 1.12), (240, 600), (580, 900)), shadow=0)
    front = poly(F)
    p.fold([F[1], F[2]], 10, -0.8)                      # the front-side corner edge catches light
    for u0, u1 in ((0.07, 0.15), (0.85, 0.93)):
        iron_p(p, poly(qsub(F, u0, -0.01, u1, 1.01)), iron, rust=0.55, bulge=0.5, shadow=0.45, sh_off=(3, 5),
               sh_blur=4)
        for v in (0.12, 0.38, 0.62, 0.88):
            rivet(p, *quad(F, (u0 + u1) / 2, v), 5, hx("#a8a098"))
    for u0, u1 in ((0.12, 0.22), (0.78, 0.88)):
        iron_p(p, poly(qsub(S, u0, -0.01, u1, 1.01)), sh(iron, 0.8), rust=0.55, bulge=0.5, shadow=0.4)
    iron_p(p, poly(qsub(F, -0.01, 0.9, 1.0, 1.01)), sh(iron, 0.95), rust=0.6, shadow=0.4)
    iron_p(p, poly(qsub(S, 0, 0.9, 1.01, 1.01)), sh(iron, 0.75), rust=0.6, shadow=0)
    for c, pts in (("bl", [quad(F, 0, 0.78), quad(F, 0, 1.0), quad(F, 0.16, 1.0)]),
                   ("br", [quad(F, 1, 0.78), quad(F, 1, 1.0), quad(F, 0.84, 1.0)]),
                   ("tl", [quad(F, 0, 0.0), quad(F, 0.15, 0.0), quad(F, 0, 0.2)]),
                   ("tr", [quad(F, 1, 0.0), quad(F, 0.85, 0.0), quad(F, 1, 0.2)])):
        gold_p(p, poly(pts).grow(3), shadow=0.45, sh_off=(3, 5), sh_blur=3)
        x = sum(q[0] for q in pts) / 3
        y = sum(q[1] for q in pts) / 3
        rivet(p, x, y, 5, hx("#e8c870"))
    # lock plate
    lc = quad(F, 0.56, 0.38)
    plate = poly([(lc[0] - 34, lc[1] - 48), (lc[0] + 34, lc[1] - 46), (lc[0] + 36, lc[1] + 22), (lc[0], lc[1] + 56),
                  (lc[0] - 36, lc[1] + 20)], smooth=True)
    gold_p(p, plate, shadow=0.55, sh_off=(4, 7), sh_blur=5)
    p.paint(plate - plate.grow(-7), None, mode="bump", bulge=0.8, rnd=4)
    kh = circle(lc[0], lc[1] - 6, 9) | poly([(lc[0] - 6, lc[1]), (lc[0] + 6, lc[1]), (lc[0] + 9, lc[1] + 28),
                                             (lc[0] - 9, lc[1] + 28)])
    p.paint(kh, hx("#0c0606"), mode="on", bulge=-0.8, line=0.3, shadow=0)
    # gums over the rim, then the lower fangs
    rim = tube([(250, 596), (414, 604), (592, 614), (668, 578), (744, 540)], 30, 22)
    p.paint(rim, gum, grad=(sh(gum, 1.15), (240, 590), (740, 540)), spec=0.85, gloss=0.75, tex="fbm", tex_amt=0.4,
            bulge=0.8, shadow=0.45, sh_off=(2, 8), sh_blur=6)
    rng = random.Random(7)
    rimc = cr([(240, 590), (414, 600), (588, 606), (668, 574), (738, 540)], n=10)
    for i in range(15):
        t = 0.03 + i * 0.066
        (x, y), _ = at(rimc, t)
        far = t > 0.68
        Lt = rng.uniform(34, 58) * (0.65 if far else 1.0) * (1.25 if i in (2, 7) else 1.0)
        fang(p, (x, y + 4), -90 + rng.uniform(-14, 14), Lt, Lt * 0.36, sh(tooth, 0.8 if far else 1.0),
             curl=rng.uniform(-0.25, 0.25))
    R.add("body", p, "", "root", (490, 760), 10)
    leg("leg_bl", "leg_back", [(430, 840), (446, 900), (456, 952)], 44, 30, 0.3, 3, 160)
    leg("leg_br", "leg_front", [(700, 800), (778, 858), (796, 948)], 46, 30, 0.3, 4, 150)
    leg("leg_fr", "leg_back", [(560, 876), (606, 908), (616, 958)], 64, 42, 0.0, 6, 160)
    leg("leg_fl", "leg_front", [(300, 856), (226, 890), (200, 958)], 66, 42, 0.0, 7, 170)

    # ================= lid (jaw): domed planks, iron bands, the eyes, the roof of the mouth and upper fangs
    p = R.part()
    cap = poly([(570, 276), (636, 256), (704, 290), (746, 366), (754, 470), (742, 540), (592, 392)], smooth=True)
    roof = poly([(244, 410), (592, 390), (744, 538), (700, 556), (560, 498), (262, 466)], smooth=True)
    p.paint(roof, flesh, grad=(hx("#3a0810"), (400, 410), (400, 470)), spec=0.75, gloss=0.65, tex="fbm",
            tex_amt=0.4, bulge=0.4, line=0.4)
    for i in range(6):
        x = 270 + i * 60
        p.fold([(x, 420), (x + 40, 470)], 9, -0.8, clip=roof)
    dome = poly([(248, 292), (280, 238), (350, 208), (440, 200), (526, 212), (570, 278)], smooth=True)
    p.paint(cap, sh(wood, 0.62), tex="streak60", tex_amt=0.5, bump=0.5, var=0.2, bulge=0.4, spec=0.15, gloss=0.3)
    grime(p, cap, hx("#22160c"), 0.5)
    for k in (0.33, 0.66):
        p.fold([(570 + k * 80, 276 - k * 10), (592 + k * 150, 392 + k * 140)], 6, 1.0, clip=cap)
    p.paint(dome, sh(wood, 1.05), tex="streak0", tex_amt=0.55, bump=0.55, var=0.2, bulge=0.7, spec=0.2, gloss=0.35)
    for y in (236, 260):
        p.fold([(262, y + 26), (400, y - 18), (560, y + 26)], 6, 1.0, clip=dome)
    lid = planks(p, L, wood, 2, 5, grad=(sh(wood, 1.15), (250, 250), (590, 400)), shadow=0)
    # scowling carved brows over the eyes
    for (x, y), s in ((E1, 1), (E2, -1)):
        p.paint(poly(taper([(x - 40 * s, y - 40), (x, y - 30), (x + 34 * s, y - 16)], 22, 10)), sh(wood, 0.85),
                mode="on", bulge=0.9, line=0.4, shadow=0.55, sh_off=(2, 6), sh_blur=4, tex="streak0", tex_amt=0.4)
        p.paint(ellipse(x, y, 40, 28, -6 * s), hx("#140806"), mode="on", bulge=-0.7, line=0.4, shadow=0)
        glow_eye(p, x, y, 30, 20, yel, core, rot=-6 * s)
        p.paint(ellipse(x - 2, y, 5, 18), hx("#0a0402"), mode="on", bulge=0.2, line=0, shadow=0, unlit=1.0)
        p.paint(ellipse(x - 12, y - 8, 5, 4), hx("#fffbe8"), mode="on", bulge=0.3, line=0, shadow=0,
                emit=(0.6, 0.6, 0.5), unlit=1.0)
        p.paint((ellipse(x, y, 40, 28, -6 * s) - ellipse(x, y, 31, 21, -6 * s)), hx("#4a1e0c"), mode="on",
                bulge=-0.3, line=0, shadow=0, emit=(0.12, 0.05, 0.0))
    for u0, u1 in ((0.05, 0.13), (0.87, 0.95)):
        band = poly(qsub(L, u0, -0.02, u1, 1.0))
        x0, y0 = quad(L, (u0 + u1) / 2, 0)
        band = band | tube([(x0, y0 + 6), (x0 + (6 if u0 < 0.5 else -6), y0 - 40),
                            (x0 + (40 if u0 < 0.5 else -20), y0 - 70)], 26)
        iron_p(p, band & (lid | dome).grow(1), iron, rust=0.55, shadow=0.45, sh_off=(3, 5), sh_blur=4)
        for v in (0.25, 0.75):
            rivet(p, *quad(L, (u0 + u1) / 2, v), 5, hx("#a8a098"))
    lip = tube([(228, 412), (410, 402), (594, 392)], 20)
    gold_p(p, lip, shadow=0.5, sh_off=(2, 6), sh_blur=4)
    for x in (300, 410, 520):
        rivet(p, x, 408 - (x - 228) * 0.054, 5, hx("#f0d080"))
    rng = random.Random(11)
    lipc = cr([(240, 420), (410, 410), (588, 400), (660, 452), (730, 520)], n=10)
    for i in range(14):
        t = 0.03 + i * 0.071
        (x, y), _ = at(lipc, t)
        far = t > 0.72
        Lt = rng.uniform(44, 74) * (0.6 if far else 1.0) * (1.3 if i in (1, 6, 10) else 1.0)
        fang(p, (x, y - 2), 90 + rng.uniform(-12, 12), Lt, Lt * 0.34, sh(tooth, 0.8 if far else 1.0),
             curl=rng.uniform(-0.25, 0.25))
    R.add("lid", p, "body", "jaw", (722, 534), 20)

    # ================= drool stringing from the upper fangs
    p = R.part()
    for path, w in (([(296, 470), (292, 540), (300, 600)], 5), ([(512, 456), (518, 500), (514, 528)], 4)):
        p.paint(tube(path, w, w * 0.6), hx("#c8d4c8"), op=0.7, spec=1.2, gloss=0.9, line=0.2, shadow=0, bulge=0.9)
        x, y = path[-1]
        p.paint(ellipse(x, y + 6, w * 1.6, w * 2.1), hx("#d8e4d8"), op=0.85, spec=1.3, gloss=0.9, line=0.3,
                shadow=0, bulge=0.9)
    R.add("drool", p, "lid", "hair", (300, 470), 21)

    # ================= tongue lolling over the rim to the floor
    def tongue_seg(path, ws, tip=False):
        p = R.part()
        p.sss = 0.9
        m = tube(path, ws)
        p.paint(m, tong, grad=(sh(tong, 0.7), path[0], path[-1]), tex="fbm", tex_amt=0.3, bump=0.4, spec=0.95,
                gloss=0.8, bulge=0.8, var=0.15, shadow=0.55, sh_off=(4, 10), sh_blur=8)
        p.fold(path, 7, 0.9, clip=m)
        rng = random.Random(len(path))
        c = cr(path, n=8)
        for i in range(10):
            (x, y), (tx, ty) = at(c, rng.random())
            o = rng.uniform(-0.3, 0.3) * ws[0]
            p.paint(circle(x - ty * o, y + tx * o, rng.uniform(2.0, 3.0)), sh(tong, 1.03), mode="on", bulge=0.9,
                    line=0, shadow=0.2, sh_off=(1, 1), sh_blur=1, spec=0.9, gloss=0.8)
        if tip:
            x, y = path[-1]
            p.paint(tube([(x - 6, y + 8), (x - 4, y + 40)], 5, 3), hx("#d8c8c8"), op=0.7, spec=1.2, gloss=0.9,
                    line=0.2, shadow=0)
            p.paint(ellipse(x - 4, y + 46, 7, 9), hx("#e4d8d8"), op=0.85, spec=1.3, gloss=0.9, line=0.3, shadow=0)
        return p

    R.add("tongue_1", tongue_seg([(460, 556), (390, 586), (322, 628), (276, 690)], [70, 66, 62, 60]), "body",
          "tail", (452, 560), 24)
    R.add("tongue_2", tongue_seg([(276, 690), (242, 758), (238, 820), (262, 854), (298, 842)], [60, 54, 46, 34, 20],
                                 tip=True), "tongue_1", "tail", (276, 690), 25)

    # ================= fx: eyes and the hungry glow of the throat
    fx = R.fx()
    for (x, y) in (E1, E2):
        fx.glow(x, y, 26, yel, 0.9, core=core)
        fx.glow(x, y, 60, yel * 0.6, 0.2)
    R.add("eye_glow", fx, "lid", "fx", E1, 40)
    fx = R.fx()
    fx.glow(470, 524, 90, hot, 0.35, squash=0.45)
    fx.glow(440, 524, 36, (1.0, 0.75, 0.3), 0.4, squash=0.5)
    R.add("maw_glow", fx, "body", "fx", (470, 524), 11)
    return R


# =============================================================== bone king (boss)

ERMINE = hx("#e6e0d4")


def ermine(p, m, seed, n=14, spot=11):
    """White ermine fur over m: soft dome, fur strokes and black tail tips."""
    p.sss = max(p.sss, 0.5)
    p.paint(m, ERMINE, tex="fbm", tex_amt=0.25, var=0.06, bulge=0.8, spec=0.08, gloss=0.2,
            grad=(sh(ERMINE, 1.04), (m.box[0] / SS, m.box[1] / SS), (m.box[0] / SS, m.box[3] / SS)))
    fur(p, m, ERMINE, 90, int(m.area() / (SS * SS) / 40) + 40, seed, length=16, width=4.5, dark=0.78, light=1.08,
        alpha=0.55, bump=0.8)
    p.fringe(m, sh(ERMINE, 0.92), 90, int(math.sqrt(m.area()) / SS * 1.4), 12, 5, seed=seed + 1, outward=0.8,
             jitter=40)
    rng = random.Random(seed)
    ys, xs = np.nonzero(m.a > 0.9)
    if len(xs) == 0:
        return
    for _ in range(n):
        i = rng.randrange(len(xs))
        x, y = (xs[i] + m.x) / SS, (ys[i] + m.y) / SS
        p.paint(poly(taper([(x, y - spot), (x + rng.uniform(-3, 3), y), (x, y + spot * 1.2)], spot * 0.8, 1)),
                hx("#16120e"), mode="on", bulge=0.5, line=0, shadow=0.2, sh_off=(1, 2), sh_blur=1.5, spec=0.3)


def robe(p, m, col, folds, seed, grad=None, **kw):
    """Heavy royal velvet: deep folds, a soft sheen on the ridges."""
    p.sss = max(p.sss, 0.45)
    kw.setdefault("spec", 0.14)
    kw.setdefault("gloss", 0.25)
    p.paint(m, col, tex="fbm", tex_amt=0.35, var=0.12, bump=0.2, bump_tex="grain", bulge=0.35, grad=grad, **kw)
    for path, w in folds:
        p.fold(path, w, 1.1, clip=m)
        p.fold([(x + w * 0.7, y) for x, y in path], w * 0.7, -0.8, clip=m)
    return m


def gem(p, x, y, r, col, rot=0.0):
    m = ellipse(x, y, r, r * 1.2, rot)
    gold_p(p, m.grow(4), mode="on", line=0.5, shadow=0.4, sh_off=(2, 3), sh_blur=2)
    p.paint(m, sh(col, 0.6), mode="on", bulge=1.0, spec=1.4, gloss=0.95, line=0.3, shadow=0,
            emit=np.asarray(col) * 0.12, grad=(sh(col, 1.2), (x - r, y - r), (x + r, y + r)))
    p.paint(ellipse(x - r * 0.35, y - r * 0.45, r * 0.25, r * 0.2), hx("#ffffff"), mode="on", bulge=0.5, line=0,
            shadow=0, unlit=1.0)


def ghost_flame(fx, base, h, w, col, core, seed, lean=0.0):
    """A ghost-fire flame drawn into an FX layer: tongues licking up from base, white-green core."""
    rng = random.Random(seed)
    bx, by = base
    tongues = []
    for i in range(5):
        o = (i - 2) / 2 * w * 0.42
        hh = h * rng.uniform(0.55, 1.0) * (1.0 if i == 2 else 0.8)
        tongues.append(poly(taper([(bx + o, by), (bx + o * 0.8 + lean * hh * 0.4 + rng.uniform(-8, 8), by - hh * 0.5),
                                   (bx + o * 0.4 + lean * hh + rng.uniform(-14, 14), by - hh)],
                                  w * (0.55 if i == 2 else 0.4), 1.0, n=8)))
    body = union(ellipse(bx, by - h * 0.12, w * 0.5, h * 0.22), *tongues)
    fx.mask_glow(body, col, blur=10, k=0.55)
    fx.mask_glow(body, col, blur=3, k=0.75)
    fx.mask_glow(body.grow(-w * 0.12), core, blur=4, k=0.75)
    fx.glow(bx, by - h * 0.18, w * 0.42, core, 0.7)
    fx.glow(bx, by - h * 0.3, h * 0.7, col * 0.5, 0.22)


def bone_king():
    """Boss: the Bone King. A towering crowned skeleton in a royal purple robe with gold trim and an ermine
    mantle and hem, ghost-green fire burning in his eye sockets and inside the ribcage behind a jewelled
    medallion. His gold crown, set with rubies and sapphires, sits bent and askew. His near hand grips a tall
    staff topped with a horned skull that blazes with ghost-green flame; the far hand reaches toward the hero
    with a second flame in its claws. A heavy purple cape lined with crimson sweeps behind him, and soul
    wisps drift around him (faces left)."""
    ghost = np.array([0.32, 1.0, 0.62], F32)
    gcore = np.array([0.86, 1.0, 0.92], F32)
    HEAD = (700, 400)
    EYES = [(656, 400), (734, 396)]
    STAFF_F = (1016, 196)
    HAND_F = (352, 640)
    look = Look(key=(1.45, 1.3, 1.08), sky=(0.2, 0.24, 0.36), ground=(0.1, 0.08, 0.09), rim=(0.5, 1.0, 0.75),
                rim_k=1.25,
                lights=[(STAFF_F[0], STAFF_F[1] + 40, 40, (0.3, 1.0, 0.55), 170, 1.5),
                        (HAND_F[0], HAND_F[1] + 20, 40, (0.3, 1.0, 0.55), 150, 1.4),
                        (700, 405, 30, (0.3, 1.0, 0.55), 60, 0.55),
                        (720, 760, 26, (0.3, 1.0, 0.55), 110, 1.0)],
                falloff=(760, 900, 640, 0.3))
    R = Rig("bone_king", 1536, (760, 1458), "humanoid", look)
    purple = hx("#2e1848")
    purple_d = hx("#1e102e")
    crimson = hx("#6a1420")
    gold = hx("#c8952e")
    boneK = hx("#b0a27e")
    bone_d = sh(boneK, 0.8)
    red = hx("#c0142a")
    blue = hx("#1a6ad8")

    # ================= root: the robe at the hips and the gold sash
    p = R.part()
    hips = poly([(596, 880), (760, 868), (918, 884), (950, 980), (960, 1080), (580, 1080), (572, 980)], smooth=True)
    robe(p, hips, purple, [([(680, 900), (660, 1060)], 18), ([(860, 900), (880, 1060)], 18)], 1,
         grad=(sh(purple, 1.1), (600, 880), (950, 1080)))
    R.add("hips", p, "", "root", (760, 960), 10, fade=[((760, 1010), (760, 1078))])

    # ================= legs: robe panels swing from the hips; bony feet in gold sabatons below the hem
    def leg(prefix, hip, panel, hem, knee, ankle, toe, heel, zu, zl, depth, col):
        p = R.part(depth=depth)
        m = poly(panel, smooth=True)
        robe(p, m, col, [([(hip[0] + d, hip[1] + 60), (hip[0] + d * 1.6, hem[0][1] - 40)], 22)
                         for d in (-80, -20, 50)], hip[0], grad=(sh(col, 1.1), (hip[0], hip[1]), (hip[0], hem[0][1])))
        ermine(p, tube(hem, 60), hip[0] + 3, n=9)
        trim = tube([(hem[0][0] + 6, hem[0][1] - 40), (hem[-1][0] - 6, hem[-1][1] - 40)], 12) & m
        gold_p(p, trim, shadow=0.35, sh_off=(2, 4), sh_blur=3)
        R.add(prefix + "_upper", p, "hips", prefix + "_upper", hip, zu)
        p = R.part(depth=depth)
        bone(p, knee, ankle, 34, bone_d)
        sab = poly([(ankle[0] - 34, ankle[1] - 26), (ankle[0] + 34, ankle[1] - 30), heel, (toe[0] + 8, toe[1] + 2),
                    (toe[0] - 10, toe[1] - 6), (toe[0] + 30, toe[1] - 40)], smooth=True)
        gold_p(p, sab, sh(gold, 0.85), shadow=0.5, sh_off=(4, 6), sh_blur=4)
        for f in (0.3, 0.55, 0.8):
            x = heel[0] + (toe[0] - heel[0]) * f
            p.fold([(x, toe[1] - 40 + f * 10), (x - 4, toe[1])], 6, 1.0, clip=sab)
        R.add(prefix + "_lower", p, prefix + "_upper", prefix + "_lower", knee, zl)

    leg("leg_back", (850, 960),
        [(740, 900), (920, 890), (980, 1080), (1050, 1260), (1080, 1400), (900, 1418), (770, 1412), (760, 1100)],
        [(780, 1400), (930, 1412), (1072, 1396)], (880, 1220), (904, 1400), (840, 1456), (950, 1458),
        4, 3, 0.25, purple_d)
    leg("leg_front", (680, 960),
        [(600, 900), (790, 896), (810, 1100), (820, 1300), (800, 1420), (640, 1430), (480, 1410), (520, 1250),
         (570, 1080)], [(482, 1404), (640, 1424), (806, 1414)], (650, 1220), (632, 1404), (540, 1456),
        (680, 1458), 9, 8, 0.0, purple)

    # ================= torso: velvet robe, the ribcage in the open neckline burning green, gold sash, mantle
    p = R.part()
    tor = union(poly([(566, 640), (640, 590), (760, 578), (880, 592), (946, 650), (956, 760), (940, 900),
                      (760, 920), (580, 906), (566, 780)], smooth=True))
    robe(p, tor, purple, [([(620, 700), (640, 800), (620, 900)], 22), ([(900, 700), (880, 800), (900, 900)], 22)],
         2, grad=(sh(purple, 1.15), (600, 620), (940, 900)))
    neck = poly([(660, 600), (840, 600), (790, 760), (760, 860), (730, 760)], smooth=True)
    p.paint(neck, hx("#140a12"), mode="on", bulge=-0.6, line=0.4, shadow=0)
    p.paint(ellipse(752, 720, 70, 100).blur(14) & neck, ghost * 0.3, mode="on", bulge=0, line=0, shadow=0,
            emit=ghost * 0.35, unlit=0.6, op=0.8)
    for i in range(5):
        y = 640 + i * 34
        for side in (-1, 1):
            w = 92 - i * 10
            pts = [(758 + side * 6, y), (758 + side * w * 0.55, y - 12), (758 + side * w, y + 14)]
            p.paint(poly(taper(pts, 15, 8)) & neck.grow(4), boneK if side < 0 else bone_d, tex="pits",
                    tex_amt=0.4, bump=0.4, spec=0.3, gloss=0.35, line=0.55, shadow=0.45, sh_off=(3, 5), sh_blur=4)
    p.paint(tube([(756, 620), (758, 700), (760, 790)], 22, 16), boneK, tex="pits", tex_amt=0.4, spec=0.3,
            shadow=0.4)
    for side in (-1, 1):   # gold trim down the neckline
        pts = [(760 + side * 96, 598), (760 + side * 42, 720), (762, 870)]
        gold_p(p, tube(pts, 18) & tor, shadow=0.45, sh_off=(3, 5), sh_blur=3)
    sash = tube([(574, 880), (760, 900), (948, 878)], 50)
    gold_p(p, sash & tor.grow(10), sh(gold, 0.9), bulge=0.5, shadow=0.5, sh_off=(4, 9), sh_blur=6)
    for x in range(600, 940, 34):
        p.fold([(x, 864), (x + 6, 906)], 5, 0.8, clip=sash)
    gem(p, 760, 896, 18, red)
    # gold chain and medallion
    chain(p, [(650, 640), (700, 720), (760, 760), (822, 720), (870, 640)], 16, gold, spec=1.0)
    med = circle(760, 790, 40)
    gold_p(p, med, shadow=0.55, sh_off=(4, 8), sh_blur=5)
    p.paint(med - med.grow(-8), None, mode="bump", bulge=0.8, rnd=4)
    gem(p, 760, 790, 20, hx("#22b070"))
    p.glow_on(circle(756, 786, 10), ghost * 0.6)
    R.add("torso", p, "hips", "torso", (760, 900), 12)

    # mantle: ermine collar and gold pauldrons over the shoulders
    p = R.part()
    man = poly([(546, 640), (600, 586), (700, 560), (820, 560), (920, 586), (976, 650), (948, 700), (880, 680),
                (820, 640), (700, 640), (630, 690), (566, 700)], smooth=True)
    ermine(p, man, 41, n=16, spot=13)
    for (cx, cy, rot, s) in ((600, 640, -18, -1), (924, 646, 16, 1)):
        pd = poly(ell(cx, cy, 86, 58, rot, 180, 360) + ell(cx, cy + 6, 86, 24, rot, 0, 180))
        for k in (-1, 0, 1):
            a = math.radians(-90 + k * 32 + s * 10)
            bx, by = cx + k * 44, cy - 34 + abs(k) * 10
            spk = poly([(bx - 14, by + 6), (bx + math.cos(a) * 62, by + math.sin(a) * 62), (bx + 14, by + 6)])
            gold_p(p, spk, shadow=0.4, sh_off=(2, 5), sh_blur=3)
        gold_p(p, pd, shadow=0.55, sh_off=(4, 10), sh_blur=8)
        p.paint(pd - pd.grow(-10), None, mode="bump", bulge=0.8, rnd=5)
        gem(p, cx, cy - 6, 15, blue if s < 0 else red)
    R.add("mantle", p, "torso", "extra", (760, 640), 28)

    # ================= cape: purple velvet lined with crimson, sweeping back
    p = R.part(depth=0.15)
    cp = poly([(640, 600), (900, 600), (1010, 680), (1110, 840), (1190, 1060), (1240, 1300), (1250, 1400),
               (1120, 1410), (980, 1400), (900, 1260), (860, 1000), (760, 760)], smooth=True)
    robe(p, cp, purple_d, [([(940, 700), (1040, 900), (1110, 1200)], 34), ([(900, 760), (960, 1000), (1000, 1300)], 30),
                           ([(1000, 680), (1120, 900), (1200, 1250)], 26)], 3,
         grad=(sh(purple, 0.9), (800, 620), (1200, 1380)))
    lining = poly([(1160, 980), (1236, 1240), (1250, 1400), (1190, 1404), (1170, 1200)], smooth=True)
    robe(p, lining & cp, crimson, [([(1190, 1060), (1220, 1300)], 18)], 4, mode="on", line=0.3)
    ermine(p, tube([(980, 1396), (1120, 1406), (1246, 1396)], 50) & cp.grow(8), 43, n=8)
    R.add("cape", p, "torso", "cape", (860, 620), 2)

    # ================= far arm reaching toward the hero, a ghost flame in its claws
    p = R.part(depth=0.15)
    slv = poly([(560, 620), (640, 660), (600, 760), (520, 800), (470, 790), (500, 700)], smooth=True)
    robe(p, slv, purple, [([(580, 660), (520, 770)], 18)], 5, grad=(sh(purple, 1.1), (560, 620), (500, 800)))
    R.add("arm_back_upper", p, "torso", "arm_back_upper", (596, 650), 6)
    p = R.part(depth=0.15)
    cuff = poly([(540, 740), (520, 840), (460, 860), (420, 830), (440, 760), (500, 730)], smooth=True)
    bone(p, (490, 780), (380, 700), 26, boneK)
    bone(p, (492, 792), (388, 716), 12, bone_d, knobs=(False, False))
    robe(p, cuff, purple, [([(500, 760), (470, 840)], 14)], 6)
    ermine(p, tube([(424, 770), (448, 850)], 34) & cuff.grow(10), 45, n=4, spot=9)
    # claw hand, palm up, fingers curled around the flame
    hc = (370, 690)
    p.paint(ellipse(hc[0], hc[1], 34, 22, -20), boneK, tex="pits", tex_amt=0.4, bump=0.4, spec=0.3)
    for i, (a, Lf) in enumerate(((-150, 52), (-125, 60), (-100, 58), (-75, 50), (-40, 40))):
        r = math.radians(a)
        k1 = (hc[0] + math.cos(r) * 26, hc[1] + math.sin(r) * 16)
        k2 = (k1[0] + math.cos(r) * Lf * 0.55, k1[1] + math.sin(r) * Lf * 0.55)
        k3 = (k2[0] + math.cos(r + 0.7) * Lf * 0.45, k2[1] + math.sin(r + 0.7) * Lf * 0.45)
        bone(p, k1, k2, 11, boneK, knob=1.2, line=0.5, shadow=0.35, sh_off=(2, 3), sh_blur=2)
        bone(p, k2, k3, 9, boneK, knob=1.2, knobs=(True, False), line=0.5, shadow=0.35, sh_off=(2, 3), sh_blur=2)
        claw(p, k3, math.degrees(r + 1.0), 18, 7, hx("#3a3026"), curl=0.3)
    R.add("arm_back_lower", p, "arm_back_upper", "arm_back_lower", (500, 770), 7)
    fx = R.fx()
    ghost_flame(fx, (HAND_F[0], HAND_F[1] + 40), 150, 76, ghost, gcore, 5, lean=0.1)
    R.add("hand_flame", fx, "arm_back_lower", "fx", HAND_F, 8)

    # ================= head: skull, sockets of ghost fire, jaw, the bent crown
    p = R.part()
    p.sss = 0.25
    skull = union(ellipse(HEAD[0] + 6, HEAD[1] - 30, 104, 100),
                  poly([(604, 410), (612, 470), (640, 506), (760, 508), (796, 470), (808, 410)], smooth=True))
    p.paint(skull, boneK, tex="pits", tex_amt=0.5, bump=0.6, spec=0.35, gloss=0.45)
    grime(p, skull, hx("#4a3a28"), 0.45)
    p.paint(ellipse(778, 440, 34, 40, -10), sh(boneK, 0.88), mode="on", bulge=0.5, line=0.3)
    p.fold([(740, 300), (726, 330), (744, 352), (732, 380)], 4, 1.0, clip=skull)
    p.fold([(610, 350), (650, 372)], 6, 0.8, clip=skull)
    for (x, y), (rx, ry) in zip(EYES, ((34, 30), (29, 28))):
        p.paint(ellipse(x, y, rx, ry, -12), hx("#0a0a08"), mode="on", bulge=-1.0, line=0.5, shadow=0)
        glow_eye(p, x, y + 2, rx * 0.4, ry * 0.36, ghost, gcore, rot=-10)
    p.paint(poly(taper([(626, 362), (660, 352), (690, 368)], 14, 6)), sh(boneK, 1.05), mode="on", bulge=0.9,
            line=0.4, shadow=0.5, sh_off=(0, 5), sh_blur=3)       # scowling brow ridge
    p.paint(poly(taper([(712, 364), (740, 352), (770, 362)], 12, 6)), sh(boneK, 1.0), mode="on", bulge=0.9,
            line=0.4, shadow=0.5, sh_off=(0, 5), sh_blur=3)
    for s_ in (-1, 1):
        p.paint(poly([(694, 440), (694 + s_ * 13, 462), (694 + s_ * 3, 470)]).blur(1), hx("#0e0a08"), mode="on",
                bulge=-0.8, line=0.4, shadow=0)
    p.paint(ellipse(626, 450, 26, 34, 10), sh(boneK, 0.92), mode="on", bulge=0.5, line=0.25)
    for x in range(630, 760, 15):
        p.paint(poly([(x, 486), (x + 13, 486), (x + 12, 510), (x + 1, 510)], smooth=True), sh(boneK, 1.05),
                bulge=0.6, line=0.5, lw=1.2, shadow=0.3, sh_off=(1, 3), sh_blur=2, spec=0.45, gloss=0.5)
    R.add("head", p, "torso", "head", (740, 580), 30)
    p = R.part()
    p.sss = 0.25
    jm = poly([(630, 506), (770, 504), (790, 520), (760, 560), (650, 566)], smooth=True)
    p.paint(jm, hx("#0c0606"), bulge=0.2, line=0.3)
    jaw = poly([(808, 470), (800, 530), (760, 576), (680, 590), (626, 576), (628, 552), (680, 556), (752, 540),
                (782, 480)], smooth=True)
    p.paint(jaw, boneK, tex="pits", tex_amt=0.5, bump=0.5, spec=0.3, gloss=0.4)
    grime(p, jaw)
    for x in range(636, 756, 15):
        y = 540 - (x - 636) * 0.06
        p.paint(poly([(x + 1, y), (x + 13, y), (x + 12, y + 22), (x + 2, y + 22)], smooth=True), sh(boneK, 0.98),
                bulge=0.6, line=0.5, lw=1.2, shadow=0.25, sh_off=(1, 3), sh_blur=2)
    R.add("jaw", p, "head", "jaw", (790, 486), 29)
    # the crown: gold band, five points tipped with pearls, rubies and sapphires; bent and tipped askew
    p = R.part()
    CR = (698, 300)
    rot = -9
    band = poly(rot_pts([(590, 284), (806, 284), (802, 336), (594, 336)], *CR, rot))
    pts = []
    for i in range(5):
        x = 600 + i * 50
        h = 92 if i % 2 == 0 else 70
        if i == 3:
            h = 60
        pts.append((x, 290, h, -14 if i == 3 else 0))
    points = []
    for x, y, h, bend in pts:
        tri = [(x - 22, y), (x + 22, y), (x + bend * 0.5, y - h * 0.6), (x + bend, y - h)]
        tri = [tri[0], tri[2], tri[3], tri[2], tri[1]]
        m = poly(rot_pts([(x - 24, y), (x + bend * 0.4 - 10, y - h * 0.6), (x + bend, y - h),
                          (x + bend * 0.4 + 10, y - h * 0.6), (x + 24, y)], *CR, rot))
        points.append((m, rot_pts([(x + bend, y - h)], *CR, rot)[0]))
    for m, tip in points:
        gold_p(p, m, shadow=0.45, sh_off=(3, 6), sh_blur=4)
        p.paint(m.grow(-6), None, mode="bump", bulge=0.5)
    gold_p(p, band, shadow=0.55, sh_off=(4, 10), sh_blur=6)
    p.paint(band - band.grow(-7), None, mode="bump", bulge=0.9, rnd=4)
    p.fold(rot_pts([(752, 286), (748, 336)], *CR, rot), 6, 1.2, clip=band)   # the dent
    for m, (tx, ty) in points:
        p.paint(circle(tx, ty, 10), hx("#ece6dc"), spec=1.2, gloss=0.9, line=0.4, shadow=0.4, sh_off=(2, 3),
                sh_blur=2, bulge=1.0)
    for i, x in enumerate((622, 670, 726, 776)):
        c = rot_pts([(x, 310)], *CR, rot)[0]
        gem(p, c[0], c[1], 11 if i % 2 else 13, red if i % 2 == 0 else blue)
    R.add("crown", p, "head", "hair", (700, 330), 31)
    fx = R.fx()
    for (x, y), r in zip(EYES, (26, 22)):
        fx.glow(x, y + 2, r, ghost, 1.0, core=gcore)
    trail = poly(taper([(660, 398), (720, 384), (800, 376), (880, 350)], 30, 2))
    fx.mask_glow(trail, ghost * 0.7, blur=6, k=0.8)
    fx.mask_glow(poly(taper([(664, 398), (736, 386), (800, 378)], 12, 1)), gcore * 0.7, blur=2, k=0.7)
    R.add("eye_fire", fx, "head", "fx", EYES[0], 32)
    fx = R.fx()
    fx.glow(756, 730, 70, ghost * 0.8, 0.5, core=gcore * 0.3)
    fx.glow(760, 790, 26, ghost, 0.6)
    R.add("rib_fire", fx, "torso", "fx", (756, 730), 13)

    # ================= near arm and the skull staff
    p = R.part()
    slv = poly([(840, 610), (946, 640), (1010, 760), (1030, 860), (960, 880), (900, 790), (850, 700)], smooth=True)
    robe(p, slv, purple, [([(900, 660), (980, 820)], 20), ([(870, 700), (930, 840)], 14)], 7,
         grad=(sh(purple, 1.05), (860, 620), (1000, 880)))
    gold_p(p, tube([(966, 876), (1030, 856)], 14) & slv.grow(6), shadow=0.4)
    R.add("arm_front_upper", p, "torso", "arm_front_upper", (900, 650), 34)
    p = R.part()
    bone(p, (990, 830), (1038, 740), 28, boneK)
    bone(p, (1004, 834), (1050, 748), 12, bone_d, knobs=(False, False))
    ermine(p, poly([(940, 820), (1040, 800), (1060, 860), (960, 890)], smooth=True), 47, n=5, spot=9)
    G = (1036, 720)
    fist(p, G, -90, 64, boneK, knuckle=True)
    for i in range(4):
        p.fold([(1010, 694 + i * 14), (1062, 698 + i * 14)], 4, 0.9)
    R.add("arm_front_lower", p, "arm_front_upper", "arm_front_lower", (990, 830), 36)
    p = R.part()
    top, bot = (1018, 330), (1058, 1450)
    shaft = tube([top, ((top[0] + bot[0]) / 2, (top[1] + bot[1]) / 2), bot], 26, 22)
    wood = hx("#3a2618")
    p.paint(shaft, wood, grad=(sh(wood, 1.4), (1006, 700), (1032, 700)), tex="streak88", tex_amt=0.5, bump=0.5,
            spec=0.3, gloss=0.4, bulge=0.7, shadow=0)
    for t in (0.06, 0.32, 0.58, 0.97):
        x, y = top[0] + (bot[0] - top[0]) * t, top[1] + (bot[1] - top[1]) * t
        gold_p(p, tube([(x, y - 12), (x, y + 12)], 34, caps=False), shadow=0.35)
    # horned skull at the top of the staff
    SK = (1016, 300)
    for s in (-1, 1):
        horn = poly(taper([(SK[0] + s * 36, SK[1] - 10), (SK[0] + s * 84, SK[1] - 40), (SK[0] + s * 92, SK[1] - 110),
                           (SK[0] + s * 70, SK[1] - 150)], 30, 3, n=8))
        gold_p(p, horn, sh(gold, 0.95), shadow=0.45, sh_off=(3, 6), sh_blur=4)
        for k in range(4):
            p.fold([(SK[0] + s * (50 + k * 10), SK[1] - 20 - k * 26), (SK[0] + s * (66 + k * 8), SK[1] - 30 - k * 26)],
                   4, 0.9, clip=horn)
    sk = union(ellipse(SK[0], SK[1] - 6, 52, 50), poly([(970, 300), (976, 340), (1000, 360), (1036, 360),
                                                         (1060, 336), (1062, 300)], smooth=True))
    p.paint(sk, sh(boneK, 1.02), tex="pits", tex_amt=0.5, bump=0.5, spec=0.4, gloss=0.5)
    grime(p, sk, k=0.4)
    for x, y in ((996, 300), (1036, 300)):
        p.paint(ellipse(x, y, 15, 14), hx("#0a0a08"), mode="on", bulge=-1.0, line=0.4, shadow=0)
        glow_eye(p, x, y + 2, 6, 5, ghost, gcore)
    p.paint(poly([(1010, 320), (1022, 320), (1018, 336), (1014, 336)]), hx("#0e0a08"), mode="on", bulge=-0.8,
            line=0.3, shadow=0)
    for x in range(990, 1044, 9):
        p.paint(poly([(x, 342), (x + 8, 342), (x + 7, 356), (x + 1, 356)], smooth=True), sh(boneK, 1.05), bulge=0.5,
                line=0.45, lw=1.0, shadow=0.25, sh_off=(1, 2), sh_blur=1.5)
    R.add("staff", p, "arm_front_lower", "weapon", G, 35)
    fx = R.fx()
    ghost_flame(fx, (SK[0], SK[1] - 34), 230, 100, ghost, gcore, 9, lean=-0.1)
    for x, y in ((996, 302), (1036, 302)):
        fx.glow(x, y, 12, ghost, 0.9, core=gcore)
    R.add("staff_flame", fx, "staff", "fx", STAFF_F, 37)

    # ================= floating soul wisps
    for i, (x, y, r) in enumerate(((432, 470, 18), (1220, 600, 15), (330, 1010, 14), (1290, 900, 12))):
        p = R.part()
        m = poly(taper([(x, y + r), (x + r * 0.2, y - r * 0.4), (x - r * 0.3, y - r * 2.4)], r * 1.6, 1, n=8)) | \
            circle(x, y + r * 0.3, r)
        p.paint(m, ghost * 0.6, emit=ghost * 0.7, unlit=1.0, bulge=0.4, line=0, shadow=0, op=0.85)
        p.glow_on(circle(x, y + r * 0.3, r * 0.55).blur(3), gcore * 0.9)
        R.add(f"wisp_{i + 1}", p, "hips", "float", (x, y), 45 + i)
        fx = R.fx()
        fx.glow(x, y, r * 2.2, ghost, 0.55, core=gcore * 0.6)
        R.add(f"wisp_{i + 1}_glow", fx, f"wisp_{i + 1}", "fx", (x, y), 50 + i)
    return R


# =============================================================== main

RIGS = {
    "cellar_rat": cellar_rat,
    "skeleton_guard": skeleton_guard,
    "cellar_warden": cellar_warden,
    "mimic": mimic,
    "bone_king": bone_king,
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

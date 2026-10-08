#!/usr/bin/env python3
"""Landscape battle backgrounds, v2 ("like the reference, alive").

Painted 1920 x 1080 scenes built with numpy: fbm noise, bump-lit masses, perspective floors,
atmospheric haze and additive light. Every dungeon is split into layers the game animates:

    far.png   opaque   sky / cave depths / distant scenery          (slowest parallax)
    mid.png   RGBA     main scenery and the fighting ground          (medium parallax)
    rays.png  RGBA     additive light shafts and glow washes         (blend ADD, drift + pulse)
    glow.png  RGBA     additive light sources only (fire, lava, ...) (blend ADD, flicker)
    near.png  RGBA     dark blurred foreground framing               (fastest parallax)
    fx.json            particle emitters in 1920 x 1080 px

Draw order: far, mid, rays (add), glow (add), near. The additive layers are stored as
rgb = hue, alpha = strength, so Godot's ADD blend (dst + src.rgb * src.a) reproduces them.
A flattened preview <id>.jpg is written next to the folders.

Usage (from the repo root):  python3 tools/art/backgrounds_v2.py [ids...]
"""
import json
import math
import os
import sys
import time
import zlib

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "assets", "backgrounds", "v2")
W, H = 1920, 1080
SS = 2                 # mask supersampling
GROUND_Y = 780
F32 = np.float32
LIGHT = np.array([-0.55, -0.62, 0.56], F32)   # key light from the upper left
LIGHT /= np.linalg.norm(LIGHT)

YY, XX = np.mgrid[0:H, 0:W].astype(F32)


# ============================================================== basic maths

def C(h, k=1.0):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32) * k


def lerp(a, b, t):
    return a + (b - a) * t


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ramp(t, stops):
    """Map a scalar field to colour. stops: [(pos, colour), ...] with rising pos."""
    pos = [p for p, _ in stops]
    out = np.empty(np.shape(t) + (3,), F32)
    for c in range(3):
        out[..., c] = np.interp(t, pos, [col[c] for _, col in stops])
    return out


def _rs(a, size, method=Image.BICUBIC):
    return np.asarray(Image.fromarray(np.ascontiguousarray(a, F32), "F").resize(size, method))


def resize(a, size, method=Image.BICUBIC):
    if a.ndim == 2:
        return _rs(a, size, method)
    return np.stack([_rs(a[..., c], size, method) for c in range(a.shape[2])], -1)


def _box(a, r, axis):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=F32)
    n = a.shape[axis]
    hi = [slice(None)] * a.ndim
    lo = [slice(None)] * a.ndim
    hi[axis] = slice(2 * r + 1, 2 * r + 1 + n)
    lo[axis] = slice(0, n)
    return (c[tuple(hi)] - c[tuple(lo)]) / (2 * r + 1)


def blur(a, s):
    """Gaussian-like blur (3 box passes), downsampling for big radii."""
    if s < 0.4:
        return a
    h, w = a.shape[:2]
    f = 1
    while s / f > 5 and min(h, w) // (f * 2) >= 4:
        f *= 2
    if f > 1:
        small = resize(a, (max(1, w // f), max(1, h // f)), Image.BOX)
        return resize(blur(small, s / f), (w, h), Image.BILINEAR)
    r = max(1, int(round(s)))
    for _ in range(3):
        a = _box(_box(a, r, 0), r, 1)
    return a


# ============================================================== noise

class Noise:
    """Cached full-canvas fbm fields, standardised to mean 0 / std 1."""

    def __init__(self, seed):
        self.seed = seed
        self.cache = {}

    def __call__(self, scale, octaves=4, key=0, sx=1.0, sy=1.0, gain=0.5):
        k = (float(scale), octaves, key, float(sx), float(sy), float(gain))
        if k in self.cache:
            return self.cache[k]
        rng = np.random.default_rng(zlib.crc32(repr((self.seed,) + k).encode()))
        tot = np.zeros((H, W), F32)
        amp = 1.0
        for o in range(octaves):
            cs = scale / 2 ** o
            cx, cy = max(1.0, cs * sx), max(1.0, cs * sy)
            gw, gh = int(W / cx) + 3, int(H / cy) + 3
            g = rng.random((gh, gw)).astype(F32)
            up = _rs(g, (int(gw * cx), int(gh * cy)))
            ox = int(rng.integers(0, max(1, up.shape[1] - W)))
            oy = int(rng.integers(0, max(1, up.shape[0] - H)))
            tot += up[oy:oy + H, ox:ox + W] * amp
            amp *= gain
        tot -= tot.mean()
        tot /= tot.std() + 1e-6
        self.cache[k] = tot
        return tot

    def noise(self, *a, **kw):
        return self(*a, **kw)


# ============================================================== masks

class Mask:
    """Soft coverage mask limited to a bounding box."""
    __slots__ = ("a", "x0", "y0")

    def __init__(self, a, x0=0, y0=0):
        self.a = a.astype(F32, copy=False)
        self.x0, self.y0 = int(x0), int(y0)

    @property
    def sl(self):
        return (slice(self.y0, self.y0 + self.a.shape[0]), slice(self.x0, self.x0 + self.a.shape[1]))

    @property
    def X(self):
        return XX[self.sl]

    @property
    def Y(self):
        return YY[self.sl]

    def full(self):
        out = np.zeros((H, W), F32)
        out[self.sl] = self.a
        return out

    def k(self, f):
        return Mask(self.a * f, self.x0, self.y0)

    def crop(self, full):
        """Slice a full-canvas array to this mask's box."""
        return full[self.sl]

    def grow(self, pad):
        """Same mask on a box enlarged by pad px (for blurs that spill out)."""
        x0, y0 = max(0, self.x0 - pad), max(0, self.y0 - pad)
        x1 = min(W, self.x0 + self.a.shape[1] + pad)
        y1 = min(H, self.y0 + self.a.shape[0] + pad)
        out = np.zeros((y1 - y0, x1 - x0), F32)
        out[self.y0 - y0:self.y0 - y0 + self.a.shape[0], self.x0 - x0:self.x0 - x0 + self.a.shape[1]] = self.a
        return Mask(out, x0, y0)

    def blurred(self, s):
        m = self.grow(int(s * 3) + 2)
        return Mask(blur(m.a, s), m.x0, m.y0)


def full_mask(a=None):
    return Mask(np.ones((H, W), F32) if a is None else a)


def draw_mask(bbox, fn, feather=0.0):
    """fn(draw, T, s): T maps a list of canvas points to supersampled local points."""
    pad = int(feather * 3) + 3
    x0 = max(0, int(math.floor(bbox[0])) - pad)
    y0 = max(0, int(math.floor(bbox[1])) - pad)
    x1 = min(W, int(math.ceil(bbox[2])) + pad)
    y1 = min(H, int(math.ceil(bbox[3])) + pad)
    if x1 <= x0 or y1 <= y0:
        return Mask(np.zeros((1, 1), F32), 0, 0)
    img = Image.new("L", ((x1 - x0) * SS, (y1 - y0) * SS), 0)
    d = ImageDraw.Draw(img)

    def T(pts):
        return [((x - x0) * SS, (y - y0) * SS) for x, y in pts]

    fn(d, T, SS)
    a = np.asarray(img.reduce(SS), F32) / 255.0
    if feather > 0:
        a = blur(a, feather)
    return Mask(a, x0, y0)


def _bbox(pts, extra=0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) - extra, min(ys) - extra, max(xs) + extra, max(ys) + extra)


def poly(pts, feather=0.0):
    return draw_mask(_bbox(pts), lambda d, T, s: d.polygon(T(pts), fill=255), feather)


def polys(list_pts, feather=0.0):
    allp = [p for pts in list_pts for p in pts]

    def fn(d, T, s):
        for pts in list_pts:
            if len(pts) > 2:
                d.polygon(T(pts), fill=255)
    return draw_mask(_bbox(allp), fn, feather)


def ellipse(cx, cy, rx, ry, feather=0.0):
    def fn(d, T, s):
        (a, b), = T([(cx - rx, cy - ry)])
        (c, e), = T([(cx + rx, cy + ry)])
        d.ellipse((a, b, c, e), fill=255)
    return draw_mask((cx - rx, cy - ry, cx + rx, cy + ry), fn, feather)


def stroke(pts, width, feather=0.0, taper=None):
    """Polyline with round joints; taper=(w0, w1) varies the width along it."""
    def fn(d, T, s):
        tp = T(pts)
        n = len(tp)
        for i in range(n - 1):
            w = width if taper is None else lerp(taper[0], taper[1], i / max(1, n - 2))
            d.line([tp[i], tp[i + 1]], fill=255, width=max(1, int(w * s)))
            r = w * s / 2
            d.ellipse((tp[i][0] - r, tp[i][1] - r, tp[i][0] + r, tp[i][1] + r), fill=255)
        r = (width if taper is None else taper[1]) * s / 2
        d.ellipse((tp[-1][0] - r, tp[-1][1] - r, tp[-1][0] + r, tp[-1][1] + r), fill=255)
    return draw_mask(_bbox(pts, width), fn, feather)


def blob_pts(cx, cy, rx, ry, rng, rough=0.18, n=36, rot=0.0, flat_bottom=None):
    """Irregular closed outline (rocks, bushes, clouds)."""
    ph = rng.uniform(0, 6.28, 4)
    pts = []
    for i in range(n):
        t = i / n * 2 * math.pi
        r = 1 + rough * (0.55 * math.sin(2 * t + ph[0]) + 0.3 * math.sin(3 * t + ph[1])
                         + 0.2 * math.sin(5 * t + ph[2]) + 0.12 * math.sin(9 * t + ph[3]))
        r *= 1 + rng.uniform(-rough, rough) * 0.25
        x = math.cos(t) * rx * r
        y = math.sin(t) * ry * r
        x, y = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        if flat_bottom is not None:
            y = min(y, flat_bottom - cy)
        pts.append((cx + x, cy + y))
    return pts


def ridge(rng, x0, x1, y, amp, steps=7, rough=0.55, peaks=None):
    """Midpoint-displacement skyline from x0 to x1 around height y. Returns [(x, y)]."""
    n = 2 ** steps
    ys = np.zeros(n + 1)
    ys[0] = rng.uniform(-amp, amp) * 0.5
    ys[-1] = rng.uniform(-amp, amp) * 0.5
    step, a = n, amp
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            ys[i] = (ys[i - half] + ys[i + half]) / 2 + rng.uniform(-a, a)
        step = half
        a *= rough
    xs = np.linspace(x0, x1, n + 1)
    if peaks:
        for px, py, pw in peaks:
            ys += (py - y) * np.exp(-((xs - px) / pw) ** 2) * 1.0
    return [(float(x), float(y + v)) for x, v in zip(xs, ys)]


def edge_noise(m, noise, amount=0.6, sharp=3.0, s=2.0):
    """Roughen a mask's edge with a noise field (painterly broken edges)."""
    g = m.grow(int(s * 3) + 3)
    b = blur(g.a, s)
    a = np.clip((b - 0.5 + g.crop(noise) * amount * 0.25) * sharp + 0.5, 0, 1)
    return Mask(a * np.clip(b * 4, 0, 1), g.x0, g.y0)


# ============================================================== layers

def _field(col, m):
    if callable(col):
        col = col(m)
    col = np.asarray(col, F32)
    if col.ndim == 3 and col.shape[:2] == (H, W) and m.a.shape != (H, W):
        col = col[m.sl]
    return col


class Layer:
    """Premultiplied RGBA float canvas."""

    def __init__(self, opaque_col=None):
        self.rgb = np.zeros((H, W, 3), F32)
        self.a = np.zeros((H, W), F32)
        if opaque_col is not None:
            self.rgb[:] = opaque_col
            self.a[:] = 1

    def paint(self, m, col, alpha=1.0):
        sl = m.sl
        a = np.clip(m.a * alpha, 0, 1)
        c = _field(col, m)
        a3 = a[..., None]
        self.rgb[sl] = c * a3 + self.rgb[sl] * (1 - a3)
        self.a[sl] = a + self.a[sl] * (1 - a)

    def light(self, m, col, k=1.0):
        """Add light onto what is already painted (scaled by coverage)."""
        sl = m.sl
        c = _field(col, m)
        self.rgb[sl] += c * (m.a * k)[..., None] * self.a[sl][..., None]

    def mult(self, m, col, k=1.0):
        """Multiply painted colour toward col (shadow / tint)."""
        sl = m.sl
        c = _field(col, m)
        t = np.clip(m.a * k, 0, 1)[..., None]
        self.rgb[sl] *= (1 - t) + c * t

    def haze(self, m, col, k=1.0):
        """Push painted colour toward a haze colour (keeps coverage)."""
        sl = m.sl
        c = _field(col, m)
        t = np.clip(m.a * k, 0, 1)[..., None]
        self.rgb[sl] = self.rgb[sl] * (1 - t) + c * self.a[sl][..., None] * t

    def erase(self, m, k=1.0):
        sl = m.sl
        t = np.clip(m.a * k, 0, 1)
        self.rgb[sl] *= (1 - t)[..., None]
        self.a[sl] *= 1 - t

    def over(self, other):
        a = other.a[..., None]
        self.rgb = other.rgb + self.rgb * (1 - a)
        self.a = other.a + self.a * (1 - other.a)

    def blur_all(self, s):
        self.rgb = blur(self.rgb, s)
        self.a = blur(self.a, s)

    def image(self, opaque=False):
        a = np.clip(self.a, 0, 1)
        rgb = self.rgb / np.maximum(a, 1e-4)[..., None]
        rgb = np.clip(rgb, 0, 1)
        if opaque:
            return Image.fromarray((rgb * 255 + 0.5).astype(np.uint8), "RGB")
        out = np.dstack([rgb, a])
        return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


class Light:
    """Additive light layer."""

    def __init__(self):
        self.L = np.zeros((H, W, 3), F32)

    def add(self, m, col, k=1.0):
        c = _field(col, m)
        self.L[m.sl] += c * (m.a * k)[..., None]

    def image(self):
        L = np.maximum(self.L, 0)
        a = np.clip(L.max(axis=2), 0, 1)
        rgb = np.clip(L / np.maximum(a, 1e-4)[..., None], 0, 1)
        out = np.dstack([rgb, a])
        return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def radial(cx, cy, rx, ry=None, power=2.0, box=None):
    """Soft radial falloff mask (1 at centre, 0 at radius)."""
    ry = ry or rx
    x0 = max(0, int(cx - rx)) if box is None else box[0]
    y0 = max(0, int(cy - ry)) if box is None else box[1]
    x1 = min(W, int(cx + rx) + 1) if box is None else box[2]
    y1 = min(H, int(cy + ry) + 1) if box is None else box[3]
    if x1 <= x0 or y1 <= y0:
        return Mask(np.zeros((1, 1), F32))
    X = XX[y0:y1, x0:x1]
    Y = YY[y0:y1, x0:x1]
    d = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
    return Mask(np.clip(1 - d, 0, 1) ** power, x0, y0)


def gauss(cx, cy, sx, sy=None):
    sy = sy or sx
    x0, x1 = max(0, int(cx - sx * 3)), min(W, int(cx + sx * 3) + 1)
    y0, y1 = max(0, int(cy - sy * 3)), min(H, int(cy + sy * 3) + 1)
    if x1 <= x0 or y1 <= y0:
        return Mask(np.zeros((1, 1), F32))
    X = XX[y0:y1, x0:x1]
    Y = YY[y0:y1, x0:x1]
    return Mask(np.exp(-0.5 * (((X - cx) / sx) ** 2 + ((Y - cy) / sy) ** 2)), x0, y0)


def vgrad(stops, y0=0, y1=H):
    """Full-canvas vertical colour gradient; stops positions in 0..1 of y0..y1."""
    t = (YY[:, :1] - y0) / (y1 - y0)
    col = ramp(t[:, 0], stops)
    return np.broadcast_to(col[:, None, :], (H, W, 3)).copy()


# ============================================================== shading helpers

def bump_normal(h, strength=1.0):
    gy, gx = np.gradient(h)
    nx, ny = -gx * strength, -gy * strength
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
    return nx * inv, ny * inv, inv


def lambert(n, L=LIGHT):
    return np.clip(n[0] * L[0] + n[1] * L[1] + n[2] * L[2], 0, 1)


def form_light(m, noise=None, bulge=18.0, form=1.0, rough=0.0, strength=6.0, L=LIGHT):
    """Lambert light of a mask read as a rounded mass (+ optional noise relief). Returns
    (lit, normal) in the mask's box."""
    g = m
    h = blur(g.a, bulge) * bulge * form
    if noise is not None and rough:
        h = h + g.crop(noise) * rough
    n = bump_normal(h, strength / max(1.0, bulge) * 1.0)
    return lambert(n, L), n


def voronoi(X, Y, pts, sy=1.0):
    """Nearest / second-nearest seed distances and the nearest seed's index."""
    d1 = np.full(X.shape, 1e9, F32)
    d2 = np.full(X.shape, 1e9, F32)
    idx = np.zeros(X.shape, np.int32)
    for i, (px, py) in enumerate(pts):
        d = (X - px) ** 2 + ((Y - py) * sy) ** 2
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        idx = np.where(closer, i, idx)
        d1 = np.where(closer, d, d1)
    return np.sqrt(d1), np.sqrt(d2), idx


def rock_col(sc, m, dark, mid, lite, bulge=None, form=1.0, rough=1.0, nscale=40, key=1,
             cell=55, sy=1.0, tilt=0.25, var=None, L=LIGHT, spec=None, ao=0.5, crack=0.35,
             grain=0.03, rng=None, up_bias=0.15):
    """Painterly chiselled rock for a mask: the mass reads as one rounded form lit from the
    upper left, broken into flat planes (voronoi facets with random tilts) separated by
    dark cracks, with noise relief, per-plane colour variation and fine grain.
    Returns (rgb, normal) in the mask's box."""
    rng = rng if rng is not None else np.random.default_rng(key * 7 + 1)
    X, Y = m.X, m.Y
    hgt, wid = m.a.shape
    # seeds on a jittered grid (denser rows when sy > 1 gives tall planes)
    pts = []
    for gy in np.arange(m.y0 - cell * 0.5, m.y0 + hgt + cell, cell * sy):
        for gx in np.arange(m.x0 - cell * 0.5, m.x0 + wid + cell, cell):
            pts.append((gx + rng.uniform(-0.45, 0.45) * cell, gy + rng.uniform(-0.45, 0.45) * cell * sy))
    d1, d2, idx = voronoi(X, Y, pts, 1.0 / sy)
    tx = rng.normal(0, tilt, len(pts)).astype(F32)
    ty = (rng.normal(0, tilt, len(pts)) - up_bias).astype(F32)
    tv = rng.uniform(0.9, 1.1, len(pts)).astype(F32)
    if bulge is None:
        bulge = max(4.0, min(0.22 * min(hgt, wid), 120.0))
    hf = blur(m.a, bulge) * bulge * 3.0 * form
    gy_, gx_ = np.gradient(hf)
    nz_ = sc.noise(nscale, 3, key=key, gain=0.45)
    ny2, nx2 = np.gradient(m.crop(nz_))
    k = nscale * 0.07 * rough
    nx = -gx_ + tx[idx] + (-nx2 * k)
    ny = -gy_ + ty[idx] + (-ny2 * k)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
    n = (nx * inv, ny * inv, inv)
    lit = lambert(n, L)
    occ = np.clip(blur(m.a, max(2.0, bulge * 0.6)) * 1.8, 0, 1) ** ao
    t = np.clip((lit - 0.1) * 1.25 * occ, 0, 1) * tv[idx]
    col = ramp(t, [(0, dark), (0.3, lerp(dark, mid, 0.6)), (0.6, mid), (0.95, lite)])
    if var is not None:
        v = m.crop(sc.noise(cell * 4, 3, key=key + 7))
        col = lerp(col, np.asarray(var, F32), (np.clip(v * 0.6, 0, 1) * 0.5)[..., None])
    if crack:
        cr = 1 - sstep(0.5, 3.5, d2 - d1)
        col = col * (1 - cr * crack * 0.55)[..., None]
        # thin lit lip on the upper-left edge of each crack
        lip = sstep(2.5, 4.0, d2 - d1) * (1 - sstep(4.0, 6.5, d2 - d1))
        col = col + (lip * np.clip(-ny, 0, 1) * 0.06)[..., None]
    if grain:
        g = m.crop(sc.noise(2.5, 2, key=key + 3, sx=2.0))
        col = col * (1 + g[..., None] * grain)
    if spec is not None:
        col = col + np.asarray(spec, F32) * (lit ** 10)[..., None]
    return col, n


def pick(rng, a, b):
    return float(rng.uniform(a, b))


# ============================================================== shared props

def pine(lay, sc, rng, x, base, height, width, dark, lite, snow=None, snowsh=None, haze=None,
         hk=0.0, lean=0.0, key=0):
    """Snowy fir: ragged tiers drawn bottom-up, each overlapping the one below; needle
    texture, lit left flank, clumped snow on the upper edges."""
    top = base - height
    n = max(4, int(height / max(14.0, width * 0.3)))
    tiers = []
    for i in range(n):
        f = (i + 1) / n
        ty = top + height * 0.88 * (i / n) ** 1.08
        th = height * 0.88 / n * 2.0
        hw = width / 2 * (0.1 + 0.9 * f ** 0.85) * pick(rng, 0.85, 1.1)
        cx = x + lean * (1 - f) * height * 0.1
        sag = pick(rng, 0.0, 0.25)
        pts = [(cx + pick(rng, -2, 2), ty)]
        for j in range(1, 6):
            u = j / 5
            pts.append((cx + hw * u * pick(rng, 0.92, 1.08), ty + th * (u ** 1.3 * (1 - sag) + sag * u)))
        k = max(4, int(hw / 6))
        for j in range(k, -1, -1):  # ragged bottom edge right -> left
            px = cx - hw + 2 * hw * j / k
            py = ty + th * (0.72 + 0.28 * abs(px - cx) / hw) + (j % 2) * th * 0.14 * pick(rng, 0.4, 1.2)
            pts.append((px, py))
        for j in range(5, 0, -1):
            u = j / 5
            pts.append((cx - hw * u * pick(rng, 0.92, 1.08), ty + th * (u ** 1.3 * (1 - sag) + sag * u)))
        tiers.append((pts, cx, ty, th, hw))
    trunk = poly([(x - width * 0.04, base - height * 0.35), (x + width * 0.04, base - height * 0.35),
                  (x + width * 0.06, base + 4), (x - width * 0.06, base + 4)])
    tt = np.clip((trunk.X - (x - width * 0.06)) / (width * 0.12), 0, 1)
    lay.paint(trunk, ramp(tt, [(0, lerp(dark, C("#6a5a4a"), 0.6)), (0.5, dark * 0.6), (1, dark * 0.4)]))
    needle = sc.noise(6, 2, key=key + 5, sx=0.7, sy=1.3)
    clump = sc.noise(11, 3, key=key + 6)
    for pts, cx, ty, th, hw in reversed(tiers):
        m = edge_noise(poly(pts), needle, 1.1, sharp=3.0, s=1.2)
        X, Y = m.X, m.Y
        t = np.clip(0.55 - (X - cx) / (hw * 2.0), 0, 1)
        t = np.clip(t + m.crop(clump) * 0.12, 0, 1)
        col = ramp(t, [(0, dark * 0.6), (0.45, dark), (0.8, lerp(dark, lite, 0.7)), (1, lite)])
        col = col * (0.6 + 0.4 * sstep(ty, ty + th * 0.5, Y))[..., None]
        col = col * (1 + m.crop(needle)[..., None] * 0.1)
        lay.paint(m, col)
        if snow is not None:
            sh = int(max(2, th * 0.3))
            below = np.zeros_like(m.a)
            below[sh:] = m.a[:-sh]
            band = np.clip(m.a - below, 0, 1)
            band = band * sstep(0.0, 0.5, m.crop(clump) + 0.1) * sstep(0.05, 0.35, np.abs(X - cx) / hw + 0.1)
            scol = ramp(t, [(0, snowsh), (0.5, lerp(snowsh, snow, 0.55)), (0.85, snow), (1, snow)])
            lay.paint(Mask(band, m.x0, m.y0), scol, 0.95)
    if haze is not None and hk > 0:
        box = _bbox([p for t in tiers for p in t[0]], 4)
        hm = draw_mask(box, lambda d, T, s: [d.polygon(T(t[0]), fill=255) for t in tiers])
        lay.haze(hm, haze, hk)


def fir_spray(x0, y0, x1, y1, rng, size=1.0, droop=0.0, density=1.0):
    """Mask of a fir branch seen from below/side: main twig with side twigs full of needles."""
    L = math.hypot(x1 - x0, y1 - y0)
    segs = []
    n = int(L / 12 * density) + 2
    main = []
    for i in range(n + 1):
        t = i / n
        main.append((lerp(x0, x1, t), lerp(y0, y1, t) + droop * math.sin(t * math.pi) + droop * t * 0.5))
    for i in range(n):
        t = i / n
        bx, by = main[i]
        ang = math.atan2(main[i + 1][1] - by, main[i + 1][0] - bx)
        for side in (-1, 1):
            tl = 70 * size * (1 - 0.65 * t) * pick(rng, 0.6, 1.1)
            ta = ang + side * pick(rng, 0.7, 1.1)
            tx, ty = bx + math.cos(ta) * tl, by + math.sin(ta) * tl + tl * 0.25
            segs.append(((bx, by), (tx, ty), 2.2 * size))
            k = int(tl / 5)
            for j in range(1, k):
                u = j / k
                px, py = lerp(bx, tx, u), lerp(by, ty, u)
                nl = 16 * size * (1 - 0.5 * u) * pick(rng, 0.7, 1.2)
                for s2 in (-1, 1):
                    na = ta + s2 * 0.75 + pick(rng, -0.2, 0.2)
                    segs.append(((px, py), (px + math.cos(na) * nl, py + math.sin(na) * nl + nl * 0.3), 1.6 * size))
    allp = [p for sgm in segs for p in sgm[:2]] + main

    def fn(d, T, s):
        tm = T(main)
        d.line(tm, fill=255, width=int(7 * size * s))
        for a, b, w in segs:
            d.line(T([a, b]), fill=255, width=max(1, int(w * s)))
    return draw_mask(_bbox(allp, 4), fn)


def pine_row(lay, rng, xs, base, hmin, hmax, col, jitter=10):
    """Distant forest edge: many simple fir silhouettes as one mask."""
    shapes = []
    for x in xs:
        h = pick(rng, hmin, hmax)
        w = h * pick(rng, 0.28, 0.4)
        b = base + pick(rng, -jitter, jitter)
        pts = [(x, b - h)]
        k = 5
        for i in range(1, k + 1):
            f = i / k
            pts.insert(0, (x - w / 2 * f * pick(rng, 0.8, 1.1), b - h + h * f * 0.95))
            pts.append((x + w / 2 * f * pick(rng, 0.8, 1.1), b - h + h * f * 0.95))
            if i < k:
                pts.insert(0, (x - w / 2 * f * 0.55, b - h + h * f * 0.98))
                pts.append((x + w / 2 * f * 0.55, b - h + h * f * 0.98))
        pts = [(x - w * 0.5, b + 30)] + pts + [(x + w * 0.5, b + 30)]
        shapes.append(pts)
    m = polys(shapes)
    lay.paint(m, col)
    return m


def save_layers(sid, far, mid, near, rays, glow, fx):
    d = os.path.join(OUT, sid)
    os.makedirs(d, exist_ok=True)
    imgs = {
        "far": far.image(opaque=True),
        "mid": mid.image(),
        "near": near.image(),
        "rays": rays.image(),
        "glow": glow.image(),
    }
    for k, im in imgs.items():
        im.save(os.path.join(d, k + ".png"), optimize=False, compress_level=6)
    fx = dict(fx)
    fx.setdefault("ground_y", GROUND_Y)
    fx["size"] = [W, H]
    fx["layers"] = {"far": "far.png", "mid": "mid.png", "rays": "rays.png (add)",
                    "glow": "glow.png (add)", "near": "near.png"}
    with open(os.path.join(d, "fx.json"), "w") as f:
        json.dump(fx, f, indent=1)
    flat = flatten(imgs)
    flat.save(os.path.join(OUT, sid + ".jpg"), quality=90)
    return imgs, flat


def flatten(imgs, rays_k=1.0, glow_k=1.0):
    def f(im):
        return np.asarray(im, F32) / 255.0
    base = f(imgs["far"])[..., :3]
    for k in ("mid",):
        a = f(imgs[k])
        base = a[..., :3] * a[..., 3:] + base * (1 - a[..., 3:])
    for k, kk in (("rays", rays_k), ("glow", glow_k)):
        a = f(imgs[k])
        base = base + a[..., :3] * a[..., 3:] * kk
    a = f(imgs["near"])
    base = a[..., :3] * a[..., 3:] + base * (1 - a[..., 3:])
    return Image.fromarray((np.clip(base, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


# ============================================================== atmosphere helpers

class Polar:
    """Angle / distance fields around a point, for fans of light shafts."""

    def __init__(self, sx, sy):
        dx, dy = XX - sx, YY - sy
        self.r = np.sqrt(dx * dx + dy * dy)
        self.ang = np.degrees(np.arctan2(dy, dx))


def god_rays(lt, sc, src, rays, col, length=1400, start=40, dust=0.3, key=90, P=None):
    """rays: [(angle_deg, half_width_deg, strength)]. Angle 90 points straight down.
    Returns the intensity field."""
    P = P or Polar(*src)
    acc = np.zeros((H, W), F32)
    for ang, wd, k in rays:
        d = (P.ang - ang + 180) % 360 - 180
        acc += np.exp(-(d / wd) ** 2) * k
    fade = sstep(0, start, P.r) * (1 - sstep(length * 0.3, length, P.r))
    n = sc.noise(170, 3, key=key)
    acc = acc * fade * np.clip(1 + n * dust, 0.3, 1.8)
    lt.add(full_mask(acc), col)
    return acc


def spark(lt, x, y, r, col, k=1.0, cross=True):
    """Bright glint: soft core, halo and optional 4-point flare."""
    lt.add(gauss(x, y, r * 0.35), np.array([1, 1, 1], F32), k * 1.2)
    lt.add(gauss(x, y, r), col, k * 0.5)
    if cross:
        lt.add(gauss(x, y, r * 3.5, r * 0.18), col, k * 0.45)
        lt.add(gauss(x, y, r * 0.18, r * 3.5), col, k * 0.45)


def flame(mid, glow, sc, x, y, h, w, key=0, k=1.0, base_col=None):
    """Torch/candle flame: soft teardrop in mid, hot core + halo in glow."""
    rng = np.random.default_rng(key + 77)
    n = 24
    # build explicit teardrop outline
    pts = []
    for i in range(n + 1):
        u = i / n                        # 0 bottom -> 1 tip
        half = w * 0.5 * math.sin(math.pi * min(1, u * 1.6 + 0.1)) ** 0.8 * (1 - u) ** 0.6
        wob = math.sin(u * 7 + key) * w * 0.08 * u
        pts.append((x + half + wob, y - u * h))
    for i in range(n, -1, -1):
        u = i / n
        half = w * 0.5 * math.sin(math.pi * min(1, u * 1.6 + 0.1)) ** 0.8 * (1 - u) ** 0.6
        wob = math.sin(u * 7 + key) * w * 0.08 * u
        pts.append((x - half + wob, y - u * h))
    m = poly(pts, feather=1.2)
    col = ramp(np.clip((y - m.Y) / h, 0, 1), [(0, C("#ffd27a")), (0.5, C("#ff9a2e")), (1, C("#d4461a"))])
    mid.paint(m, col, 0.95)
    core = poly([(x + (px - x) * 0.5, y - (y - py) * 0.62) for px, py in pts], feather=2)
    glow.add(core, C("#fff4d0"), 1.3 * k)
    glow.add(m.blurred(3), C("#ffb040"), 0.9 * k)
    glow.add(gauss(x, y - h * 0.35, w * 1.2, h * 0.7), C("#ff8a24"), 0.4 * k)
    glow.add(gauss(x, y - h * 0.3, w * 3.5, h * 1.8), C("#ff7a1e"), 0.12 * k)


def sample(field, u, v):
    """Bilinear lookup of a full-canvas field at float coords (wraps around)."""
    u = np.mod(u, W - 1)
    v = np.mod(v, H - 1)
    x0 = u.astype(np.int32)
    y0 = v.astype(np.int32)
    fx = u - x0
    fy = v - y0
    a = field[y0, x0] * (1 - fx) + field[y0, x0 + 1] * fx
    b = field[y0 + 1, x0] * (1 - fx) + field[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def mountain(lay, sc, pts, bottom, rock, rock_lit, snow, snow_sh, haze, hk, snow_depth=160,
             key=0, mist=0.5, scale=60, contrast=1.0):
    """Snowy mountain range from a ridge line. Ridged noise is sheared along the fall line
    of each flank, so spurs run down and away from the peaks; sun-facing sides are lit,
    snow sits on the gentler lit faces and rock shows in the shadowed gullies."""
    outline = [(pts[0][0], bottom)] + pts + [(pts[-1][0], bottom)]
    m = poly(outline)
    X, Y = m.X, m.Y
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    top = np.interp(X[0], xs, ys)
    sm = blur(top[None, :].repeat(3, 0), 18)[1]
    slope = np.gradient(sm)
    shear = np.clip(-slope * 1.6, -1.2, 1.2)[None, :]
    depth = Y - top[None, :]
    rid = sc.noise(scale, 4, key=key, sx=1.0, sy=1.0, gain=0.5)
    u = X + shear * depth
    v = depth * 0.45 + 300
    r1 = sample(rid, u, v)
    r2 = sample(rid, u * 2.1 + 500, v * 2.1)
    ridged = (1 - np.abs(r1)) + 0.45 * (1 - np.abs(r2))
    gxr = np.gradient(ridged, axis=1) * scale * 0.5
    lit_x = sstep(-0.25, 0.25, -slope)[None, :]
    lit = np.clip((lit_x * 0.7 + 0.15 + gxr * 0.55 * contrast) * sstep(-5, 30, depth) + (1 - sstep(-5, 30, depth)) * lit_x, 0, 1)
    sn = 1.3 - depth / snow_depth + (lit - 0.45) * 0.9 + ridged * 0.25
    sn = sstep(0.45, 0.62, sn)
    rc = ramp(lit, [(0, rock), (0.6, lerp(rock, rock_lit, 0.6)), (1, rock_lit)])
    scl = ramp(lit, [(0, snow_sh), (0.45, lerp(snow_sh, snow, 0.35)), (0.62, snow), (1, snow)])
    col = lerp(rc, scl, sn[..., None])
    col = col * (1 + m.crop(sc.noise(3, 2, key=key + 2))[..., None] * 0.02)
    hz = np.clip(hk + (1 - hk) * mist * sstep(0, (bottom - ys.min()), depth), 0, 1)
    col = lerp(col, np.asarray(haze, F32), hz[..., None])
    lay.paint(m, col)
    return m


def castle(lay, x, base, s, wall_sh, wall_lit, roof_sh, roof_lit, win=None, haze=None, hk=0.0, rng=None):
    """Distant castle: curtain wall, round towers with conical roofs and a tall keep, each
    lit from the left; optional lit windows (win colour)."""
    rng = rng or np.random.default_rng(3)
    parts = []   # (kind, cx, top, w, rh)
    parts.append(("wall", x, base - 52 * s, 190 * s, 0))
    for cx, top, w, rh in ((x - 88, 95, 24, 38), (x + 92, 88, 22, 34), (x - 50, 118, 20, 40),
                           (x + 30, 128, 28, 50), (x - 16, 158, 42, 66), (x + 60, 180, 15, 48)):
        parts.append(("tower", x + (cx - x) * s, base - top * s, w * s, rh * s))
    shapes = []
    for kind, cx, top, w, rh in parts:
        body = [(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, base), (cx - w / 2, base)]
        m = poly(body)
        t = np.clip((m.X - (cx - w / 2)) / w, 0, 1)
        col = ramp(t, [(0, wall_lit), (0.35, lerp(wall_lit, wall_sh, 0.4)), (0.7, wall_sh), (1, wall_sh * 0.85)])
        col = col * (0.85 + 0.15 * sstep(base, top, m.Y))[..., None]
        lay.paint(m, col)
        shapes.append(body)
        # crenellations
        k = max(2, int(w / (7 * s)))
        cren = []
        for i in range(k):
            if i % 2 == 0:
                cx0 = cx - w / 2 + w * i / k
                cren.append([(cx0, top - 5 * s), (cx0 + w / k, top - 5 * s), (cx0 + w / k, top + 1), (cx0, top + 1)])
        if kind == "wall" or rh < 36 * s:
            lay.paint(polys(cren), lerp(wall_lit, wall_sh, 0.5))
        if kind == "tower":
            roof = [(cx - w * 0.64, top + 3), (cx + pick(rng, -1, 1), top - rh), (cx + w * 0.64, top + 3)]
            rm = poly(roof)
            t = np.clip((rm.X - (cx - w * 0.64)) / (w * 1.28), 0, 1)
            lay.paint(rm, ramp(t, [(0, roof_lit), (0.45, lerp(roof_lit, roof_sh, 0.5)), (0.55, roof_sh), (1, roof_sh * 0.8)]))
            shapes.append(roof)
            lay.paint(stroke([(cx, top - rh), (cx, top - rh - 9 * s)], 1.3 * s), roof_sh * 0.8)
            # windows
            for wy in np.arange(top + 14 * s, base - 10 * s, 26 * s):
                wm = poly([(cx - 2.2 * s, wy), (cx + 2.2 * s, wy), (cx + 2.2 * s, wy + 8 * s), (cx - 2.2 * s, wy + 8 * s)])
                lay.paint(wm, win if (win is not None and rng.random() < 0.6) else wall_sh * 0.55)
    if haze is not None and hk > 0:
        lay.haze(polys(shapes), haze, hk)


# ============================================================== architecture helpers

def hash2(i, j, k=0):
    v = np.sin(i * 12.9898 + j * 78.233 + k * 37.719) * 43758.5453
    return v - np.floor(v)


FOCAL = 1500.0


def blocks_uv(sc, m, u, v, bw, bh, fpu, fpv, stops, mortar, key=0, lw=0.035, bond=0.5, bevel=0.1,
              jitter=0.25):
    """Stone blocks in world coordinates u (across) / v (along), fpu/fpv = world size of a
    pixel, for antialiased joints that fade out in the distance. Returns (rgb, rnd, joint)."""
    rv = v / bh + m.crop(sc.noise(40, 3, key=key + 1)) * jitter * 0.1
    ri = np.floor(rv)
    cu = u / bw + bond * (ri % 2) + m.crop(sc.noise(50, 3, key=key + 2)) * jitter * 0.08
    ci = np.floor(cu)
    fu, fv = cu - ci, rv - ri
    du = np.minimum(fu, 1 - fu) * bw
    dv = np.minimum(fv, 1 - fv) * bh
    mu = 1 - sstep(lw - fpu, lw + fpu, du)
    mv = 1 - sstep(lw - fpv, lw + fpv, dv)
    joint = np.maximum(mu, mv)
    far_fade = np.clip(np.maximum(sstep(0.03, 0.3, fpv / bh), sstep(0.03, 0.3, fpu / bw)), 0, 1)
    joint = joint * (1 - far_fade * 0.85)
    rnd = hash2(ri, ci, key)
    t = np.clip(rnd + m.crop(sc.noise(18, 3, key=key + 3)) * 0.12, 0, 1)
    t = lerp(t, 0.5, far_fade)
    col = ramp(t, stops)
    bev = sstep(0.0, bevel, fv) * (1 - sstep(1 - bevel, 1.0, fv)) * sstep(0.0, bevel, fu) * (1 - sstep(1 - bevel * 0.5, 1.0, fu))
    col = col * (1 + (bev - 0.7) * 0.22 * (1 - far_fade))[..., None]
    col = lerp(col, np.asarray(mortar, F32), joint[..., None])
    col = col * (1 + m.crop(sc.noise(3, 2, key=key + 4))[..., None] * 0.035)
    return col, rnd, joint


def floor_persp(sc, m, horizon, cx, tile_w, tile_d, stops, mortar, key=0, F=FOCAL, cam=1.0, **kw):
    """Perspective flagstone floor (world units: camera height = cam). Returns (rgb, Z, rnd, joint)."""
    dy = np.maximum(m.Y - horizon, 0.5)
    Z = F * cam / dy
    xw = (m.X - cx) * Z / F
    fpv = Z / dy
    fpu = Z / F
    col, rnd, joint = blocks_uv(sc, m, xw, Z, tile_w, tile_d, fpu, fpv, stops, mortar, key=key, **kw)
    return col, Z, rnd, joint


def wall_persp(sc, m, horizon, cx, xwall, bw, bh, stops, mortar, key=0, F=FOCAL, cam=1.0, **kw):
    """Side wall receding to the vanishing point (plane x = xwall). Returns (rgb, Z, rnd, joint)."""
    dx = m.X - cx
    dx = np.where(np.abs(dx) < 0.5, 0.5 * np.sign(xwall), dx)
    Z = np.clip(xwall * F / dx, 0.1, 1e4)
    yw = (horizon - m.Y) * Z / F + cam
    fpu = Z / np.abs(dx)
    fpv = Z / F
    col, rnd, joint = blocks_uv(sc, m, yw, Z, bh, bw, fpv, fpu, stops, mortar, key=key, **kw)
    return col, Z, rnd, joint


def P(Z, xw, yw, horizon, cx, F=FOCAL, cam=1.0):
    """Project a world point (x across, y height above the floor, depth Z) to the screen."""
    return (cx + xw * F / Z, horizon - (yw - cam) * F / Z)


def ashlar(m, x0, y0, bw, bh, stops, mortar, lw=2.0, key=0, sc=None, bond=0.5):
    """Frontal stone blocks in screen space. Returns rgb and the block random value."""
    X, Y = m.X, m.Y
    rv = (Y - y0) / bh
    ri = np.floor(rv)
    cu = (X - x0) / bw + bond * (ri % 2)
    if sc is not None:
        cu = cu + m.crop(sc.noise(30, 2, key=key + 5)) * 0.03
    ci = np.floor(cu)
    fu, fv = cu - ci, rv - ri
    du = np.minimum(fu, 1 - fu) * bw
    dv = np.minimum(fv, 1 - fv) * bh
    mort = np.maximum(1 - sstep(lw * 0.5, lw * 0.5 + 1.2, du), 1 - sstep(lw * 0.5, lw * 0.5 + 1.2, dv))
    rnd = hash2(ri, ci, key)
    t = rnd
    if sc is not None:
        t = np.clip(t + m.crop(sc.noise(14, 3, key=key + 6)) * 0.15, 0, 1)
    col = ramp(t, stops)
    lt_ = (1 - sstep(0, 4, fu * bw)) + (1 - sstep(0, 4, fv * bh))
    dk_ = (1 - sstep(0, 5, (1 - fu) * bw)) + (1 - sstep(0, 5, (1 - fv) * bh))
    col = col * (1 + np.clip(lt_, 0, 1)[..., None] * 0.18 - np.clip(dk_, 0, 1)[..., None] * 0.28)
    col = lerp(col, np.asarray(mortar, F32), mort[..., None])
    if sc is not None:
        col = col * (1 + m.crop(sc.noise(2.5, 2, key=key + 7))[..., None] * 0.04)
    return col, rnd


def arch_pts(cx, spring_y, half_w, pointed=0.25, n=28):
    """Intrados of a (pointed) arch from the left springing point over to the right one."""
    d = pointed * half_w
    R = half_w + d
    top = spring_y - math.sqrt(max(R * R - d * d, 1))
    a_end = math.atan2(spring_y - top, -d)
    pts = []
    for i in range(n + 1):
        a = math.pi - (math.pi - a_end) * i / n
        pts.append((cx + d + math.cos(a) * R, spring_y - math.sin(a) * R))
    right = [(2 * cx - x, y) for x, y in pts[::-1]]
    return pts + right[1:]


def cyl_shade(m, x0, x1, dark, mid, lite, hl=0.3, spec=None, spec_k=0.0):
    """Shade across a vertical cylinder spanning x0..x1, lit from the left."""
    t = np.clip((m.X - x0) / max(1.0, x1 - x0), 0, 1)
    v = np.clip(np.cos((t - hl) * math.pi * 0.9), 0, 1)
    col = ramp(v, [(0, dark), (0.55, mid), (1, lite)])
    if spec is not None:
        col = col + np.asarray(spec, F32) * (np.exp(-((t - hl + 0.08) / 0.05) ** 2) * spec_k)[..., None]
    return col


def barrel_up(lay, sc, x, base, w, h, wood, band, key=0, light=1.0, top_col=None):
    """Upright barrel: bulging staves, iron hoops, cylinder shading, lid ellipse."""
    pts_l, pts_r = [], []
    for i in range(21):
        u = i / 20
        bul = 1 + 0.1 * math.sin(u * math.pi)
        yy = base - u * h
        pts_l.append((x - w / 2 * bul, yy))
        pts_r.append((x + w / 2 * bul, yy))
    m = poly(pts_l + pts_r[::-1])
    col = cyl_shade(m, x - w * 0.55, x + w * 0.55, wood * 0.3, wood, lerp(wood, C("#ffe0b0"), 0.35))
    stv = np.abs(np.sin((m.X - x) / (w * 0.55) * math.pi * 4.5 + key))
    col = col * (1 - (1 - sstep(0.0, 0.12, stv)) * 0.35)[..., None]
    col = col * (1 + m.crop(sc.noise(4, 2, key=key + 11, sx=0.2, sy=3))[..., None] * 0.08)
    lay.paint(m, col * light)
    for hy in (0.12, 0.3, 0.7, 0.88):
        yy = base - hy * h
        bul = 1 + 0.1 * math.sin(hy * math.pi)
        bm = poly([(x - w / 2 * bul - 1, yy - h * 0.03), (x + w / 2 * bul + 1, yy - h * 0.03),
                   (x + w / 2 * bul + 1, yy + h * 0.03), (x - w / 2 * bul - 1, yy + h * 0.03)])
        lay.paint(bm, cyl_shade(bm, x - w * 0.55, x + w * 0.55, band * 0.3, band, lerp(band, C("#ffffff"), 0.5)) * light)
    top = ellipse(x, base - h, w / 2 * 0.98, w * 0.12)
    lay.paint(top, (top_col if top_col is not None else wood * 0.8) * light)
    return m


def barrel_side(lay, sc, cx, cy, r, wood, band, key=0, light=1.0):
    """Barrel lying on its side, round end toward the viewer: rings, hoop, bung."""
    m = ellipse(cx, cy, r, r * 1.02)
    d = np.sqrt((m.X - cx) ** 2 + (m.Y - cy) ** 2) / r
    ang = np.arctan2(m.Y - cy, m.X - cx)
    rings = np.sin(d * 26 + np.sin(ang * 3 + key) * 0.4) * 0.5 + 0.5
    lit = np.clip(0.55 - ((m.X - cx) * 0.6 + (m.Y - cy) * 0.8) / r * 0.35, 0, 1)
    col = ramp(lit * (0.85 + rings * 0.15), [(0, wood * 0.3), (0.5, wood * 0.8), (1, lerp(wood, C("#ffe2b8"), 0.3))])
    planks = np.abs(np.sin((m.X - cx) / r * math.pi * 3 + key))
    col = col * (1 - (1 - sstep(0.0, 0.08, planks)) * 0.35 * (d < 0.86))[..., None]
    hoop = sstep(0.84, 0.88, d)
    hcol = ramp(np.clip(lit + np.cos(ang + 2.4) * 0.25, 0, 1), [(0, band * 0.3), (0.6, band), (1, lerp(band, C("#ffffff"), 0.55))])
    col = lerp(col, hcol, hoop[..., None])
    rim = sstep(0.95, 1.0, d)
    col = col * (1 - rim * 0.5)[..., None]
    lay.paint(m, col * light)
    lay.paint(ellipse(cx + r * 0.05, cy + r * 0.45, r * 0.07, r * 0.07), wood * 0.2 * light)


def chain(lay, x0, y0, x1, y1, sag, link, col, width=2.2):
    """Hanging chain of alternating links along a sagging curve."""
    L = math.hypot(x1 - x0, y1 - y0) + sag
    n = max(3, int(L / (link * 0.8)))
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((lerp(x0, x1, t), lerp(y0, y1, t) + sag * 4 * t * (1 - t)))
    rings, bars = [], []
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        (rings if i % 2 == 0 else bars).append((mx, my))

    def fn(d, T, s):
        for mx, my in rings:
            (a, b), = T([(mx - link * 0.3, my - link * 0.58)])
            (c, e), = T([(mx + link * 0.3, my + link * 0.58)])
            d.ellipse((a, b, c, e), outline=255, width=max(1, int(width * s)))
        for mx, my in bars:
            d.line(T([(mx, my - link * 0.5), (mx, my + link * 0.5)]), fill=255, width=max(1, int(width * 1.3 * s)))
    lay.paint(draw_mask(_bbox(pts, link), fn), col)


def cobweb(lay, cx, cy, r, a0, a1, col, alpha=0.5, rng=None):
    """Corner cobweb: radial threads and sagging spiral strands."""
    rng = rng or np.random.default_rng(1)
    spokes = [a0 + (a1 - a0) * i / 7 + pick(rng, -0.06, 0.06) for i in range(8)]
    segs = []
    for a in spokes:
        segs.append([(cx, cy), (cx + math.cos(a) * r, cy + math.sin(a) * r)])
    for k in range(1, 9):
        rr = r * k / 9 * pick(rng, 0.95, 1.05)
        for i in range(len(spokes) - 1):
            pa, pb = spokes[i], spokes[i + 1]
            ax, ay = cx + math.cos(pa) * rr, cy + math.sin(pa) * rr
            bx, by = cx + math.cos(pb) * rr, cy + math.sin(pb) * rr
            mx = (ax + bx) / 2 - ((ax + bx) / 2 - cx) * 0.1
            my = (ay + by) / 2 - ((ay + by) / 2 - cy) * 0.1
            segs.append([(ax, ay), (mx, my), (bx, by)])

    def fn(d, T, s):
        for sg in segs:
            d.line(T(sg), fill=255, width=max(1, int(1.1 * s)))
    m = draw_mask((cx - r, cy - r, cx + r, cy + r), fn)
    lay.paint(m, col, alpha)


def torch(mid, glow, sc, x, y, s=1.0, key=0, k=1.0):
    """Wall torch: iron bracket, wrapped stick, flame (mid) and its glow (glow)."""
    iron = C("#2a2426")
    mid.paint(stroke([(x - 16 * s, y + 46 * s), (x - 2 * s, y + 36 * s), (x - 2 * s, y + 10 * s)], 4 * s), iron)
    stick = poly([(x - 5 * s, y - 4 * s), (x + 5 * s, y - 4 * s), (x + 3.5 * s, y + 62 * s), (x - 3.5 * s, y + 62 * s)])
    mid.paint(stick, cyl_shade(stick, x - 5 * s, x + 5 * s, C("#2a160c"), C("#6b4526"), C("#b0773e")))
    mid.paint(poly([(x - 11 * s, y + 24 * s), (x + 11 * s, y + 24 * s), (x + 8 * s, y + 34 * s), (x - 8 * s, y + 34 * s)]),
              C("#3a3234"))
    wrap = poly([(x - 9 * s, y - 14 * s), (x + 9 * s, y - 14 * s), (x + 7 * s, y + 8 * s), (x - 7 * s, y + 8 * s)])
    mid.paint(wrap, cyl_shade(wrap, x - 9 * s, x + 9 * s, C("#2a1a10"), C("#5a3a22"), C("#ffb050")))
    flame(mid, glow, sc, x, y - 8 * s, 62 * s, 28 * s, key=key, k=k)


# ============================================================== FROZEN PASS

def snow_on(col, n, noise, lit_col, sh_col, k=1.0, up=0.18):
    """Blend snow onto upward-facing parts of a bump-lit mass."""
    sm = sstep(up - 0.06, up + 0.06, -blur(n[1], 1.5) + blur(noise, 2) * 0.05) * k
    sc_ = ramp(np.clip(lambert(n) * 1.25, 0, 1), [(0, sh_col), (0.6, lerp(sh_col, lit_col, 0.7)), (1, lit_col)])
    return lerp(col, sc_, sm[..., None])


def frozen_pass(seed=31):
    rng = np.random.default_rng(seed)
    sc = Noise(seed)
    sun = (800, 150)
    far, mid, near, rays, glow = Layer(), Layer(), Layer(), Light(), Light()

    # ---------------- far: sky, sun, clouds, mountain ranges, castle crag
    sky = vgrad([(0, C("#2f5b9e")), (0.3, C("#5f8cc6")), (0.62, C("#aac2dc")),
                 (0.85, C("#e8dccb")), (1.0, C("#f2d7b4"))], 0, 620)
    far.paint(full_mask(), sky)
    far.light(radial(*sun, 1000, 620, power=2.4), C("#ffd9a8"), 0.2)
    far.light(radial(*sun, 260, power=2.2), C("#fff0cc"), 0.22)
    cn = sc.noise(300, 5, key=11, sx=3.4, gain=0.5) + sc.noise(70, 3, key=12, sx=2.2) * 0.3
    band = sstep(40, 200, YY) * (1 - sstep(330, 470, YY))
    dens = np.clip((cn - 0.25) * 0.8, 0, 1) * band
    ch = blur(dens, 8)
    gyc = np.gradient(ch, axis=0) + np.gradient(ch, axis=1) * 0.5
    cloud_col = lerp(C("#9fb1d4"), C("#fff1dc"), np.clip(0.45 - gyc * 40, 0, 1)[..., None])
    cloud_col = lerp(cloud_col, C("#ffe2b8"), radial(*sun, 650).full()[..., None] * 0.7)
    far.paint(full_mask(dens * 0.8), cloud_col)

    haze_far = C("#bccbe4")
    r1 = ridge(rng, -40, 1960, 350, 60, rough=0.55,
               peaks=[(230, 240, 160), (1010, 200, 150), (1570, 190, 200), (1860, 290, 110)])
    mountain(far, sc, r1, 720, C("#56658f"), C("#a7aec6"), C("#fff6ea"), C("#8a9dc9"), haze_far, 0.3,
             snow_depth=230, key=21, mist=0.8, scale=70)
    r2 = ridge(rng, -40, 1960, 450, 55, rough=0.55,
               peaks=[(60, 320, 150), (640, 380, 120), (1400, 340, 170)])
    mountain(far, sc, r2, 740, C("#2c3a60"), C("#8a92ae"), C("#fff3e4"), C("#687db4"), haze_far, 0.12,
             snow_depth=150, key=22, mist=0.8, scale=60)
    # castle crag (centre right) with the fortress on top
    crag = [(900, 660), (940, 540), (985, 450), (1030, 392), (1080, 360), (1150, 350), (1240, 356),
            (1300, 380), (1345, 425), (1400, 480), (1455, 560), (1500, 660)]
    cm2 = edge_noise(poly(crag), sc.noise(14, 3, key=24), 1.4)
    col, n = rock_col(sc, cm2, C("#2c3857"), C("#62708f"), C("#e2d7cc"), nscale=60, key=23,
                      var=C("#6f6680"), cell=45, sy=2.0, tilt=0.35)
    col = snow_on(col, n, cm2.crop(sc.noise(24, 3, key=25)), C("#fff6ec"), C("#8a9dc8"), 0.8, up=0.4)
    far.paint(cm2, col)
    castle(far, 1195, 362, 0.92, C("#55648e"), C("#f0d8c0"), C("#34406a"), C("#8d8fb4"), haze=haze_far, hk=0.22, rng=rng)
    far.haze(cm2, haze_far, 0.22)
    # hazy far forest lines + valley mist
    pine_row(far, rng, np.arange(-20, 1960, 15) + rng.uniform(-6, 6, 132), 604, 36, 80, C("#7a8db2"))
    pine_row(far, rng, np.arange(-10, 1960, 21) + rng.uniform(-8, 8, 94), 632, 60, 115, C("#526890"))
    far.haze(full_mask(sstep(540, 650, YY) * (1 - sstep(650, 700, YY)) * 0.45), C("#dbe2ee"))

    # ---------------- mid: frozen falls, cliffs, pines, the snowfield
    for fx0, fw, ftop in ((1170, 60, 395), (1322, 32, 440)):
        left, right = [(fx0 - fw * 0.45, ftop)], [(fx0 + fw * 0.45, ftop)]
        for i in range(1, 9):
            yy = ftop + (648 - ftop) * i / 8
            spread = fw * (0.45 + 0.65 * (i / 8) ** 1.6)
            left.append((fx0 - spread + pick(rng, -3, 3), yy))
            right.append((fx0 + spread + pick(rng, -3, 3), yy))
        wm = poly(left + right[::-1])
        st = wm.crop(sc.noise(10, 3, key=31, sx=0.3, sy=5, gain=0.45))
        gx = np.gradient(st, axis=1) * 6
        t = np.clip(0.5 + gx * 0.35 + st * 0.1 - (wm.X - fx0) / (fw * 2.5), 0, 1)
        icec = ramp(t, [(0, C("#35609c")), (0.35, C("#6fa6d8")), (0.7, C("#c8e8fb")), (1, C("#ffffff"))])
        mid.paint(wm, icec, 0.97)
        mid.haze(wm, haze_far, 0.22)
        glow.add(wm.k(np.clip(t - 0.65, 0, 1)), C("#bfe8ff"), 0.4)
        mid.paint(poly(blob_pts(fx0, 650, fw * 1.5, 26, rng, 0.25), feather=1.5), C("#dce8f6"))
    # right cliff wall
    rc = [(1920, 0), (1590, 0), (1620, 90), (1570, 190), (1600, 300), (1545, 420), (1585, 520),
          (1520, 610), (1490, 670), (1920, 710)]
    m = edge_noise(poly(rc), sc.noise(16, 3, key=41), 1.5)
    col, n = rock_col(sc, m, C("#141a2c"), C("#34405e"), C("#9aa0b8"), bulge=90, nscale=80, key=42,
                      var=C("#404a64"), cell=70, sy=2.4, tilt=0.35)
    col = snow_on(col, n, m.crop(sc.noise(30, 3, key=43)), C("#e9ecf5"), C("#6e82b4"), 0.9, up=0.42)
    mid.paint(m, col)
    mid.mult(m.k(sstep(700, 0, m.Y) * 0.25), C("#3a4670"))
    # left cliff wall
    lc = [(0, 0), (300, 0), (270, 90), (330, 200), (300, 330), (370, 440), (350, 560), (430, 650),
          (0, 700)]
    m = edge_noise(poly(lc), sc.noise(16, 3, key=44), 1.5)
    col, n = rock_col(sc, m, C("#171d30"), C("#3c4868"), C("#d2c4bc"), bulge=90, nscale=80, key=45,
                      var=C("#4a5068"), cell=70, sy=2.4, tilt=0.35)
    col = snow_on(col, n, m.crop(sc.noise(30, 3, key=46)), C("#fff3e6"), C("#7488ba"), 0.9, up=0.42)
    mid.paint(m, col)
    mid.light(radial(380, 330, 200, 420), C("#ffc890"), 0.22)

    # snowfield
    gl = [(0, 648)] + [(x, 640 + 8 * math.sin(x / 210) + 5 * math.sin(x / 67)) for x in range(0, 1961, 40)] + [(1920, 1080), (0, 1080)]
    gm = poly(gl)
    Y, X = gm.Y, gm.X
    dz = np.clip((Y - 630) / 450, 0, 1)                       # 0 far .. 1 near
    hgt = gm.crop(sc.noise(170, 4, key=51, sx=4.0, gain=0.45)) * (3 + dz * 16)
    hgt += gm.crop(sc.noise(40, 3, key=52, sx=3.0, gain=0.45)) * (0.6 + dz * 4)
    gyh, gxh = np.gradient(hgt)
    lit = np.clip(0.56 - (gxh * 0.5 + gyh * 0.9) * 1.1, 0, 1)
    base = ramp(lit, [(0, C("#5a6ca4")), (0.35, C("#95a6d0")), (0.6, C("#d3d8e8")), (0.85, C("#f6efe6")), (1, C("#fff8ee"))])
    base = lerp(base, C("#d3dcec"), ((1 - dz) ** 4 * 0.7)[..., None])
    mid.paint(gm, base)
    # trodden path across the fighting ground
    pc = 776 + 14 * np.sin(X / 330 + 0.6) + 6 * np.sin(X / 90)
    pw = 46 + 14 * np.sin(X / 250)
    pn = gm.crop(sc.noise(16, 3, key=53))
    pth = sstep(1.0, 0.5, np.abs(Y - pc) / pw + pn * 0.15) * gm.a * sstep(640, 700, Y)
    pcol = lerp(C("#9aa6c6"), C("#e6dcd4"), np.clip(lit * 1.1 - 0.1, 0, 1)[..., None])
    mid.paint(Mask(pth, gm.x0, gm.y0), pcol, 0.5)
    # long blue tree shadows reaching over the snow
    shp = []
    for sx0, sw in ((90, 110), (290, 80), (440, 50), (1630, 70), (1830, 100)):
        shp.append([(sx0 - sw * 0.5, 690), (sx0 + sw * 0.5, 690), (sx0 + 380 + sw * 1.5, 1080),
                    (sx0 + 260 - sw, 1080)])
    mid.mult(polys(shp, feather=22), C("#7f93cf"), 0.35)
    # sunlit fighting ground, cool shade toward the viewer and the edges
    mid.light(gauss(860, 770, 650, 100), C("#ffe2bc"), 0.12)
    mid.mult(full_mask(sstep(840, 1080, YY) * 0.75), C("#4a5c98"))
    mid.mult(full_mask((sstep(700, 0, XX) + sstep(1300, 1920, XX)) * sstep(680, 1080, YY) * 0.3), C("#5a6ea8"))

    # rocks poking through the snow
    for bx, by, br in ((700, 706, 34), (1250, 676, 22), (560, 678, 18), (1560, 716, 50), (1720, 770, 66), (170, 790, 44)):
        bm = edge_noise(poly(blob_pts(bx, by, br * 1.35, br * 0.8, rng, 0.25, flat_bottom=by + br * 0.4)),
                        sc.noise(8, 2, key=62), 1.0)
        col, n = rock_col(sc, bm, C("#1c2236"), C("#4a5470"), C("#cabcb4"), nscale=br * 0.8, key=60 + int(bx) % 13, cell=br * 0.7)
        col = snow_on(col, n, bm.crop(sc.noise(8, 2, key=61)), C("#fff6ee"), C("#8a9dc8"), 1.0, up=0.12)
        mid.mult(ellipse(bx + br * 0.6, by + br * 0.35, br * 2.0, br * 0.28, feather=6), C("#7082b8"), 0.6)
        mid.paint(bm, col)
    # dry grass tufts
    for i in range(70):
        gx0 = pick(rng, 0, 1920)
        if 600 < gx0 < 1450 and rng.random() < 0.85:
            continue
        gy0 = pick(rng, 690, 880)
        sz = 0.6 + (gy0 - 640) / 300
        for j in range(7):
            a2 = pick(rng, -0.7, 0.7)
            ln = pick(rng, 10, 26) * sz
            m = stroke([(gx0 + j * 2.2, gy0), (gx0 + j * 2.2 + math.sin(a2) * ln * 0.6, gy0 - math.cos(a2) * ln * 0.6),
                        (gx0 + j * 2.2 + math.sin(a2) * ln, gy0 - math.cos(a2) * ln)], 1.5, taper=(2.2 * sz, 0.6))
            mid.paint(m, lerp(C("#6e5234"), C("#e2bd7e"), pick(rng, 0, 1)))

    # snowy pines, back to front
    pdark, plite = C("#0f2430"), C("#3f6a60")
    snow_c, snow_s = C("#fff8ee"), C("#8ea2cf")
    k = 100
    for px, pb, ph, pw_, hk in ((500, 652, 110, 44, 0.5), (1395, 650, 120, 48, 0.5), (560, 655, 150, 60, 0.45),
                                (1510, 660, 170, 64, 0.42), (625, 660, 200, 74, 0.4), (1450, 656, 220, 80, 0.38)):
        k += 7
        pine(mid, sc, rng, px, pb, ph, pw_, pdark, plite, snow_c, snow_s, haze=C("#a9bbdb"), hk=hk, key=k)
    for px, pb, ph, pw_ in ((1640, 706, 540, 200), (440, 676, 330, 130), (300, 696, 580, 210),
                            (1830, 726, 860, 300), (100, 740, 940, 320)):
        k += 7
        pine(mid, sc, rng, px, pb, ph, pw_, pdark, plite, snow_c, snow_s, haze=C("#8ea2cf"), hk=0.05, key=k)

    # ---------------- near: dark blurred framing
    nd = C("#0b151d")
    for (cx, cy, rx, ry) in ((40, 1040, 280, 150), (300, 1085, 190, 70), (1880, 1030, 270, 170),
                             (1640, 1085, 200, 70)):
        bm = edge_noise(poly(blob_pts(cx, cy, rx, ry, rng, 0.25)), sc.noise(10, 2, key=71), 1.0)
        col, n = rock_col(sc, bm, C("#070c14"), C("#18223a"), C("#3c4a6a"), nscale=60, key=70, cell=rx * 0.5)
        col = snow_on(col, n, bm.crop(sc.noise(9, 2, key=72)), C("#8796ba"), C("#2c3860"), 0.9, up=0.5)
        near.paint(bm, col)
    for x0, y0, x1, y1, sz, dr in ((-60, 60, 560, 140, 1.25, 60), (-60, 250, 330, 330, 1.0, 40),
                                   (1990, 40, 1420, 100, 1.25, 50), (1990, 230, 1690, 300, 0.9, 30),
                                   (-60, 980, 420, 890, 0.9, -20), (1990, 970, 1580, 900, 0.9, -20)):
        bm = fir_spray(x0, y0, x1, y1, rng, sz, dr)
        near.paint(bm, lerp(nd, C("#1f3a40"), pick(rng, 0.2, 0.5)))
        sn = Mask(np.clip(bm.a - np.roll(bm.a, 6, 0), 0, 1) * 0.8, bm.x0, bm.y0)
        near.paint(sn, C("#7f90b8"))
    near.blur_all(4.0)

    # ---------------- rays and glow
    god_rays(rays, sc, sun, [(22, 4, 0.08), (36, 5, 0.12), (50, 3.5, 0.14), (63, 6, 0.13),
                             (78, 4, 0.12), (92, 5, 0.1), (108, 4, 0.08), (125, 6, 0.06)],
             C("#ffe6bc"), length=1250, start=90, dust=0.45)
    rays.add(radial(*sun, 600, power=2.6), C("#fff0d0"), 0.08)
    rays.add(gauss(880, 760, 520, 90), C("#ffe6c0"), 0.07)
    glow.add(gauss(*sun, 22), C("#ffffff"), 1.5)
    glow.add(gauss(*sun, 60), C("#fff0c8"), 0.45)
    glow.add(gauss(*sun, 160), C("#ffd9a0"), 0.18)
    for _ in range(24):
        spark(glow, pick(rng, 560, 1480), pick(rng, 700, 830), pick(rng, 2, 4.5), C("#dff4ff"), pick(rng, 0.3, 0.7), cross=rng.random() < 0.35)
    for _ in range(9):
        spark(glow, pick(rng, 1150, 1195), pick(rng, 420, 630), pick(rng, 2, 3.5), C("#dff4ff"), 0.6)

    fx = {
        "snow": [[0, -40, 1920, 1120]],
        "sparkles": [[1135, 395, 75, 250], [1305, 440, 35, 205], [560, 700, 920, 130]],
        "mist": [[1080, 610, 330, 60], [0, 600, 1920, 60]],
        "sun": [sun[0], sun[1]],
        "ground_y": GROUND_Y,
        "wind": [-0.35, 1.0],
    }
    return far, mid, near, rays, glow, fx


# ============================================================== ROTTEN CELLAR

def crate(lay, sc, x, base, w, h, d, wood, key=0, light=1.0):
    """Wooden crate seen slightly from above-left: front, top and side faces with planks."""
    front = poly([(x, base - h), (x + w, base - h), (x + w, base), (x, base)])
    t = np.clip((front.Y - (base - h)) / h, 0, 1)
    col = lerp(wood * 1.0, wood * 0.7, t[..., None])
    pl = np.abs(np.sin((front.Y - base) / h * math.pi * 3))
    col = col * (1 - (1 - sstep(0, 0.1, pl)) * 0.4)[..., None]
    col = col * (1 + front.crop(sc.noise(5, 2, key=key, sx=4, sy=0.3))[..., None] * 0.08)
    lay.paint(front, col * light)
    # cross brace
    lay.paint(stroke([(x + 6, base - 6), (x + w - 6, base - h + 6)], w * 0.08), wood * 0.85 * light)
    lay.paint(stroke([(x + 3, base - h + 3), (x + w - 3, base - h + 3), (x + w - 3, base - 3), (x + 3, base - 3), (x + 3, base - h + 3)], w * 0.06),
              wood * 0.6 * light)
    top = poly([(x, base - h), (x + d * 0.6, base - h - d * 0.4), (x + w + d * 0.6, base - h - d * 0.4), (x + w, base - h)])
    lay.paint(top, lerp(wood, C("#ffe6c0"), 0.25) * light)
    side = poly([(x + w, base - h), (x + w + d * 0.6, base - h - d * 0.4), (x + w + d * 0.6, base - d * 0.4), (x + w, base)])
    lay.paint(side, wood * 0.45 * light)


def skull(lay, x, y, s, bone, light=1.0):
    m = ellipse(x, y, 13 * s, 11 * s)
    col = lerp(bone, bone * 0.45, np.clip((m.X - x + m.Y - y) / (20 * s) + 0.5, 0, 1)[..., None])
    lay.paint(m, col * light)
    lay.paint(poly([(x - 7 * s, y + 4 * s), (x + 7 * s, y + 4 * s), (x + 5 * s, y + 14 * s), (x - 5 * s, y + 14 * s)]), bone * 0.7 * light)
    for ex in (-5, 5):
        lay.paint(ellipse(x + ex * s, y + 2 * s, 3.6 * s, 3.2 * s), C("#140e0c"))
    lay.paint(ellipse(x, y + 8 * s, 1.5 * s, 2 * s), C("#140e0c"))


def bone(lay, x0, y0, x1, y1, w, col):
    lay.paint(stroke([(x0, y0), (x1, y1)], w), col)
    for (x, y) in ((x0, y0), (x1, y1)):
        dx, dy = (y1 - y0), -(x1 - x0)
        L = math.hypot(dx, dy) or 1
        dx, dy = dx / L * w * 0.5, dy / L * w * 0.5
        lay.paint(ellipse(x + dx, y + dy, w * 0.75, w * 0.75), col)
        lay.paint(ellipse(x - dx, y - dy, w * 0.75, w * 0.75), col)


def rotten_cellar(seed=11):
    rng = np.random.default_rng(seed)
    sc = Noise(seed)
    HOR, CX = 470.0, 960.0
    far, mid, near, rays, glow = Layer(C("#121815")), Layer(), Layer(), Light(), Light()
    stone = [(0, C("#262a25")), (0.35, C("#3b4038")), (0.7, C("#4f5347")), (1, C("#636153"))]
    mortar = C("#141612")
    fog = C("#16201c")

    def pp(Z, xw, yw):
        return P(Z, xw, yw, HOR, CX)

    # ---------------- far: corridor beyond the arch, ending at a gate with a sickly glow
    CW, CH = 1.25, 2.0            # corridor half width, spring height
    Z0, Z1 = 9.0, 40.0
    # end wall with the gate opening
    end = poly([pp(Z1, -CW - 0.2, 0), pp(Z1, CW + 0.2, 0), pp(Z1, CW + 0.2, 3.4), pp(Z1, -CW - 0.2, 3.4)])
    far.paint(end, fog * 1.1)
    gx0, gy0 = pp(Z1, -0.8, 0)
    gx1, gy1 = pp(Z1, 0.8, 1.9)
    gate_open = poly([(gx0, gy0)] + arch_pts(CX, gy1, (gx1 - gx0) / 2, 0.2) + [(gx1, gy0)])
    far.paint(gate_open, C("#6f9a4a"))
    far.light(gauss(CX, (gy0 + gy1) / 2, 40, 50), C("#d8ff9a"), 0.5)
    # corridor floor and walls
    cf = poly([pp(Z0, -CW, 0), pp(Z0, CW, 0), pp(Z1, CW, 0), pp(Z1, -CW, 0)])
    col, Z, _, _ = floor_persp(sc, cf, HOR, CX, 0.45, 0.6, stone, mortar, key=1)
    far.paint(cf, col)
    for sgn in (-1, 1):
        wm = poly([pp(Z0, sgn * CW, 0), pp(Z1, sgn * CW, 0), pp(Z1, sgn * CW, CH + 1.4), pp(Z0, sgn * CW, CH + 1.4)])
        col, Zw, _, _ = wall_persp(sc, wm, HOR, CX, sgn * CW, 0.7, 0.35, stone, mortar, key=2 + sgn)
        col = col * (0.55 if sgn > 0 else 0.75)
        far.paint(wm, col)
        far.haze(wm, fog, 1)
        far.paint(wm, col, 1)
        far.haze(wm.k(np.clip(1 - np.exp(-(Zw - Z0) / 11.0), 0, 1)), fog, 1)
    far.haze(cf.k(np.clip(1 - np.exp(-(Z - Z0) / 11.0), 0, 1)), fog, 1)
    # vault ceiling of the corridor
    cc = poly([pp(Z0, -CW, CH + 1.4), pp(Z1, -CW, CH + 1.4), pp(Z1, CW, CH + 1.4), pp(Z0, CW, CH + 1.4)])
    far.paint(cc, fog * 0.8)
    # portcullis
    bars = []
    for i in range(9):
        bx = lerp(gx0, gx1, i / 8)
        bars.append([(bx - 1.6, gy1 - (gx1 - gx0) * 0.55), (bx + 1.6, gy1 - (gx1 - gx0) * 0.55), (bx + 1.6, gy0), (bx - 1.6, gy0)])
    for j in range(5):
        by = lerp(gy1 - 20, gy0, j / 4)
        bars.append([(gx0, by - 1.3), (gx1, by - 1.3), (gx1, by + 1.3), (gx0, by + 1.3)])
    far.paint(polys(bars), C("#1b1c18"))
    # arch ribs receding, far to near, each fogged by depth
    for Zk in (36.0, 30.0, 25.0, 20.5, 16.5, 13.0, 10.2):
        s = FOCAL / Zk
        xl, yb = pp(Zk, -CW, 0)
        xr, _ = pp(Zk, CW, 0)
        _, ys = pp(Zk, 0, CH)
        th = 0.28 * s
        outer = arch_pts(CX, ys, (xr - xl) / 2 + th, 0.2)
        inner = arch_pts(CX, ys, (xr - xl) / 2, 0.2)
        ring = poly(outer + inner[::-1])
        pil = polys([[(xl - th, ys), (xl, ys), (xl, yb), (xl - th, yb)], [(xr, ys), (xr + th, ys), (xr + th, yb), (xr, yb)]])
        for m in (ring, pil):
            t = np.clip((m.X - (xl - th)) / (xr - xl + 2 * th), 0, 1)
            c = ramp(t, [(0, C("#6a6a58")), (0.5, C("#4a4c42")), (1, C("#2a2c26"))])
            c = c * (1 + m.crop(sc.noise(6, 2, key=5))[..., None] * 0.06)
            far.paint(m, c)
            far.haze(m, fog, float(1 - math.exp(-(Zk - Z0 + 1.5) / 11.0)))
    # torches along the corridor (tiny, far) and the light they throw
    for Zk in (27.0, 18.0):
        for sgn in (-1, 1):
            tx, ty = pp(Zk, sgn * (CW - 0.02), 1.6)
            sz = FOCAL / Zk / 170
            flame(far, glow, sc, tx, ty, 55 * sz, 24 * sz, key=int(Zk) + sgn, k=0.8)
            far.light(gauss(tx, ty, 60 * sz * 3, 90 * sz * 3), C("#ff9a40"), 0.15)

    # back wall of the hall with the great arch
    s9 = FOCAL / Z0
    bx0, bx1 = pp(Z0, -3.6, 0)[0], pp(Z0, 3.6, 0)[0]
    by_floor = pp(Z0, 0, 0)[1]
    xl, _ = pp(Z0, -CW, 0)
    xr, _ = pp(Z0, CW, 0)
    _, ysp = pp(Z0, 0, CH)
    opening = [(xl, by_floor)] + arch_pts(CX, ysp, (xr - xl) / 2, 0.2) + [(xr, by_floor)]
    bw_m = poly([(bx0 - 2, -10), (bx1 + 2, -10), (bx1 + 2, by_floor), (bx0 - 2, by_floor)])
    op_m = poly(opening)
    hole = np.zeros_like(bw_m.a)
    hole_full = op_m.full()[bw_m.sl]
    bw_m = Mask(bw_m.a * (1 - hole_full), bw_m.x0, bw_m.y0)
    col, _ = ashlar(bw_m, bx0, by_floor, 0.8 * s9, 0.4 * s9, stone, mortar, lw=3, key=6, sc=sc)
    far.paint(bw_m, col)
    # voussoirs round the opening
    th = 0.32 * s9
    outer = arch_pts(CX, ysp, (xr - xl) / 2 + th, 0.2)
    inner = arch_pts(CX, ysp, (xr - xl) / 2, 0.2)
    ring = poly(outer + inner[::-1] + [(xl - th, ysp)])
    jamb = polys([[(xl - th, ysp), (xl, ysp), (xl, by_floor), (xl - th, by_floor)],
                  [(xr, ysp), (xr + th, ysp), (xr + th, by_floor), (xr, by_floor)]])
    ang = np.arctan2(ring.Y - ysp, ring.X - CX)
    vj = np.abs(np.sin(ang * 9.5))
    rc = ramp(np.clip(0.6 - (ring.X - CX) / (xr - xl) * 0.5, 0, 1), [(0, C("#3a3c33")), (1, C("#7a7563"))])
    rc = rc * (1 - (1 - sstep(0, 0.08, vj)) * 0.6)[..., None]
    far.paint(ring, rc)
    col, _ = ashlar(jamb, xl - th, by_floor, th, 0.35 * s9, [(0, C("#4a4a3e")), (1, C("#6a6654"))], mortar, lw=3, key=7, sc=sc)
    far.paint(jamb, col)
    # inner reveal (thickness of the wall) on the right side of the opening, in shadow
    far.paint(poly([(xr - 0.18 * s9, ysp), (xr, ysp), (xr, by_floor), (xr - 0.12 * s9, by_floor - 4)]), C("#1a1d19"), 0.9)
    # side walls of the hall
    for sgn in (-1, 1):
        xe = 0 if sgn < 0 else W
        Ze = abs(3.6 * FOCAL / (xe - CX))
        fy = pp(Ze, 0, 0)[1]
        xb = bx0 if sgn < 0 else bx1
        wm = poly([(xe, -10), (xb, -10), (xb, by_floor), (xe, fy)])
        col, Zw, _, _ = wall_persp(sc, wm, HOR, CX, sgn * 3.6, 0.9, 0.42, stone, mortar, key=8 + sgn)
        far.paint(wm, col * 0.8)
    # wall grime: dark damp streaks and moss creeping up from the floor
    streak = np.clip(sc.noise(40, 3, key=12, sx=0.35, sy=3.0) - 0.4, 0, 2) * 0.4
    walls = np.clip(bw_m.full() + ((XX < bx0) | (XX > bx1)) * (YY < 760), 0, 1)
    far.mult(full_mask(blur(np.clip(streak, 0, 0.6), 2) * sstep(-10, 400, YY) * walls), C("#0d140f"))
    moss = np.clip(sc.noise(22, 4, key=13) * 0.6 + sstep(460, 640, YY) * 1.2 - 0.9, 0, 1) * walls
    far.paint(full_mask(moss * 0.55), C("#3d5230"))
    # light falls off away from the torches: darker high up and toward the sides
    far.mult(full_mask(walls * np.clip(sstep(420, 0, YY) * 0.45 + (sstep(700, 200, XX) + sstep(1220, 1720, XX)) * 0.35, 0, 0.7)), C("#0a0d0b"))
    # barred windows (grates) high on the back wall, bright daylight behind
    wins = [(560, 150, 150, 120, 1.0), (1370, 160, 120, 96, 0.6)]
    for wx, wy, ww, wh, wk in wins:
        wpts = [(wx - ww / 2, wy + wh / 2)] + arch_pts(wx, wy - wh * 0.1, ww / 2, 0.0, 16) + [(wx + ww / 2, wy + wh / 2)]
        frame = poly([(x + (x - wx) * 0.18, y + (y - wy) * 0.18) for x, y in wpts])
        far.paint(frame, C("#2b2d27"))
        wmk = poly(wpts)
        far.paint(wmk, lerp(C("#7f9a88"), C("#f4f4dc"), sstep(wy + wh / 2, wy - wh / 2, wmk.Y)[..., None] * wk))
        glow.add(wmk.k(0.35 * wk), C("#fdf6d8"), 1.0)
        glow.add(gauss(wx, wy, ww * 0.9, wh * 0.8), C("#e8f0c8"), 0.12 * wk)
        grid = []
        for i in range(1, 5):
            bxx = wx - ww / 2 + ww * i / 5
            grid.append([(bxx - 3.5, wy - wh), (bxx + 3.5, wy - wh), (bxx + 3.5, wy + wh / 2), (bxx - 3.5, wy + wh / 2)])
        for j in (0.0, 0.45):
            byy = wy - wh * 0.2 + wh * j
            grid.append([(wx - ww / 2, byy - 3), (wx + ww / 2, byy - 3), (wx + ww / 2, byy + 3), (wx - ww / 2, byy + 3)])
        gm = polys(grid)
        far.paint(Mask(gm.a * np.clip(wmk.full()[gm.sl] * 3, 0, 1), gm.x0, gm.y0), C("#161713"))
        # light spills on the wall around the window
        far.light(gauss(wx, wy + wh * 0.8, ww * 1.3, wh * 1.2), C("#c8d6b0"), 0.08 * wk)
    # torches on the back wall flanking the arch
    for tx in (xl - th - 70, xr + th + 70):
        torch(far, glow, sc, tx, 360, 0.9, key=int(tx))
        far.light(gauss(tx, 370, 110, 150), C("#ff9540"), 0.22)
        far.light(gauss(tx, 380, 280, 260), C("#ff8030"), 0.1)
    far.mult(full_mask(sstep(300, -20, YY) * 0.6), C("#0a0d0b"))

    # ---------------- mid: floor, great pillars, barrels, crates, bones
    fl = poly([(0, pp(abs(3.6 * FOCAL / CX), 0, 0)[1]), (bx0, by_floor), (bx1, by_floor), (W, pp(abs(3.6 * FOCAL / CX), 0, 0)[1]), (W, H), (0, H)])
    fstone = [(0, C("#22261f")), (0.4, C("#33372e")), (0.75, C("#43463a")), (1, C("#525142"))]
    col, Zf, rnd, joint = floor_persp(sc, fl, HOR, CX, 0.6, 0.6, fstone, mortar, key=20, lw=0.012)
    mid.paint(fl, col)
    # wet patches: darker, glossy
    wet = sstep(0.55, 0.9, fl.crop(sc.noise(120, 4, key=21, sx=2.5)))
    mid.mult(Mask(wet * fl.a, fl.x0, fl.y0), C("#3a4a44"), 0.55)
    # light on the floor: daylight pool from the grate, torch pools, dark toward the edges
    mid.light(gauss(900, 775, 170, 60), C("#e6efcf"), 0.35)
    mid.light(gauss(880, 765, 480, 120), C("#c8d6b0"), 0.12)
    for tx in (xl - th - 70, xr + th + 70):
        mid.light(gauss(tx, by_floor + 30, 260, 60), C("#ff9a48"), 0.14)
    mid.light(gauss(CX, by_floor + 10, 160, 25), C("#b8e08a"), 0.12)
    mid.mult(full_mask(np.clip(sstep(820, 1080, YY) * 0.7 + (sstep(700, 0, XX) + sstep(1220, 1920, XX)) * 0.45, 0, 0.85)), C("#0c100e"))

    # hanging chains from the unseen vault
    for cx0, ln in ((720, 230), (1235, 180), (1105, 120)):
        chain(mid, cx0, -20, cx0 + 4, ln, 6, 16, C("#2a2a26"), 2.4)
    # barrel stack (right) and upright barrels (left)
    wood, band = C("#6b4a2c"), C("#4a4a48")
    base_y = pp(6.4, 0, 0)[1]
    r = 0.34 * FOCAL / 6.4
    r = 0.27 * FOCAL / 6.4
    for row, n in enumerate((3, 2)):
        for i in range(n):
            bxc = 1440 + i * r * 2.02 + row * r
            byc = base_y - r - row * r * 1.75
            barrel_side(mid, sc, bxc, byc, r, wood * pick(rng, 0.75, 0.95), band, key=row * 3 + i, light=0.55)
    mid.paint(ellipse(1540, base_y + 4, 330, 16, feather=8), C("#050605"), 0.5)
    base2 = pp(6.0, 0, 0)[1]
    for bxx, hh, sh in ((430, 150, 1.0), (535, 138, 0.9), (485, 120, 0.8)):
        barrel_up(mid, sc, bxx, base2 + (8 if sh < 0.85 else 0), hh * 0.68, hh, wood * sh, band, key=int(bxx), light=0.6)
    crate(mid, sc, 1330, base_y + 6, 92, 80, 60, C("#6a4e30"), key=3, light=0.6)
    crate(mid, sc, 340, base2 + 14, 80, 70, 50, C("#5e4428"), key=4, light=0.55)
    # torchlight on the props
    mid.light(gauss(xr + th + 70, 420, 320, 260), C("#ff9a48"), 0.1)
    mid.light(gauss(xl - th - 70, 420, 320, 260), C("#ff9a48"), 0.1)
    # bones and skulls on the floor
    bonec = C("#cfc4a4")
    skull(mid, 720, 720, 1.1, bonec, 0.8)
    bone(mid, 690, 740, 745, 752, 5, bonec * 0.75)
    skull(mid, 1245, 735, 1.0, bonec, 0.7)
    bone(mid, 1180, 760, 1230, 748, 5, bonec * 0.7)
    bone(mid, 600, 800, 640, 790, 6, bonec * 0.6)

    # great pillars left and right (nearest scenery, frame the fight)
    for sgn in (-1, 1):
        Zp = 3.8
        pxc, pbase = pp(Zp, sgn * 1.95, 0)
        pw = 0.62 * FOCAL / Zp
        x0, x1 = pxc - pw / 2, pxc + pw / 2
        shaft = poly([(x0, -20), (x1, -20), (x1, pbase), (x0, pbase)])
        c, _ = ashlar(shaft, x0, pbase, pw * 0.5, pw * 0.3, stone, mortar, lw=3, key=30 + sgn, sc=sc, bond=0.5)
        shade = cyl_shade(shaft, x0, x1, C("#1c1e19"), C("#5a5a4a"), C("#a09478"), hl=0.25 if sgn < 0 else 0.75)
        c = c * (shade / C("#6a6858") * 0.8)
        mid.paint(shaft, c)
        # plinth
        pl = poly([(x0 - 22, pbase - 70), (x1 + 22, pbase - 70), (x1 + 30, pbase + 6), (x0 - 30, pbase + 6)])
        mid.paint(pl, cyl_shade(pl, x0 - 30, x1 + 30, C("#22241f"), C("#5e5c4c"), C("#a79e80"), hl=0.3 if sgn < 0 else 0.7))
        mid.paint(poly([(x0 - 22, pbase - 74), (x1 + 22, pbase - 74), (x1 + 22, pbase - 62), (x0 - 22, pbase - 62)]), C("#7b7662") * 0.8)
        # moss and damp at the foot, torch on the inner face
        mm = Mask(np.clip(shaft.crop(sc.noise(16, 3, key=33)) * 0.5 + sstep(pbase - 260, pbase, shaft.Y) - 0.6, 0, 1), shaft.x0, shaft.y0)
        mid.paint(mm, C("#40582e"), 0.6)
        tx = x1 + 18 if sgn < 0 else x0 - 18
        torch(mid, glow, sc, tx, 300, 1.1, key=40 + sgn)
        mid.light(shaft.k(np.exp(-((shaft.X - tx) / 80) ** 2 - ((shaft.Y - 310) / 220) ** 2)), C("#ff9a48"), 0.35)
        mid.paint(ellipse(pxc, pbase + 4, pw * 0.9, 14, feather=6), C("#050605"), 0.5)
    # cobwebs between pillar and wall
    cobweb(mid, 0, 0, 220, 0.0, math.pi / 2, C("#b8b8a8"), 0.35, rng)
    cobweb(mid, W, 0, 200, math.pi / 2, math.pi, C("#b8b8a8"), 0.3, rng)

    # ---------------- near: dark blurred framing
    nd = C("#07090a")
    barrel_up(near, sc, 60, 1130, 300, 420, C("#2a1c12"), C("#1c1c1c"), key=91, light=0.7)
    for (cx0, cy0, rx, ry) in ((1780, 1060, 240, 110), (1570, 1090, 150, 60), (1900, 960, 90, 120)):
        bm = poly(blob_pts(cx0, cy0, rx, ry, rng, 0.3))
        c, _ = rock_col(sc, bm, C("#050706"), C("#15191a"), C("#34332c"), key=92, cell=rx * 0.5)
        near.paint(bm, c)
    chain(near, 120, -30, 170, 330, 20, 30, C("#0e0f0e"), 5)
    chain(near, 250, -30, 200, 220, 10, 30, C("#0e0f0e"), 5)
    chain(near, 1780, -30, 1720, 280, 15, 30, C("#0e0f0e"), 5)
    near.blur_all(4.0)

    # ---------------- rays and glow
    for wx, wy, ww, wh, wk in wins:
        a0 = 64 if wx < CX else 112
        god_rays(rays, sc, (wx, wy), [(a0 - 3, 2.2, 0.17 * wk), (a0, 2.8, 0.24 * wk), (a0 + 3.5, 2.0, 0.15 * wk), (a0 - 6, 1.6, 0.08 * wk)],
                 C("#e8f2cc"), length=900, start=40, dust=0.6, key=95 + int(wk * 10))
    rays.add(gauss(900, 770, 240, 60), C("#e8f2cc"), 0.1)
    for tx, ty in ((xl - th - 70, 360), (xr + th + 70, 360)):
        rays.add(gauss(tx, ty, 150, 150), C("#ff9540"), 0.08)
    rays.add(gauss(CX, (gy0 + gy1) / 2, 90, 90), C("#b8f080"), 0.15)
    for sgn in (-1, 1):
        pxc, _ = pp(3.8, sgn * 1.95, 0)
        pw = 0.62 * FOCAL / 3.8
        tx = pxc + pw / 2 + 18 if sgn < 0 else pxc - pw / 2 - 18
        rays.add(gauss(tx, 290, 200, 200), C("#ff9040"), 0.08)
        # reflections of the torches in the wet floor
        glow.add(gauss(tx, 880, 12, 60), C("#ff9a48"), 0.25)
    glow.add(gauss(CX, (gy0 + gy1) / 2, 30, 36), C("#e8ffc0"), 0.7)

    torches = [[round(xl - th - 70), 352], [round(xr + th + 70), 352]]
    for sgn in (-1, 1):
        pxc, _ = pp(3.8, sgn * 1.95, 0)
        pw = 0.62 * FOCAL / 3.8
        torches.append([round(pxc + pw / 2 + 18 if sgn < 0 else pxc - pw / 2 - 18), 292])
    fx = {
        "dust": [[520, 150, 420, 620], [1250, 170, 200, 500]],
        "drips": [[700, 60], [1010, 40], [1180, 95], [1450, 60], [860, 30]],
        "torches": torches,
        "embers": [[t[0] - 20, t[1] - 90, 40, 70] for t in torches],
        "motes": [[CX - 60, 380, 120, 180]],
        "ground_y": GROUND_Y,
    }
    return far, mid, near, rays, glow, fx


# ============================================================== MUSHROOM CAVE

def mushroom(lay, glow, sc, rng, x, base, h, rx, ry, sw, cap, cap_dk, spot, gill, stem,
             lean=0.0, gk=1.0, key=0, haze=None, hk=0.0, spots=14, light=None):
    """Giant bioluminescent mushroom: curved stem with skirt, glowing gills seen from below,
    domed cap with glowing spots and rim. Colour goes to lay, emission to glow."""
    tx = x + lean * h
    cy = base - h
    sl, sr = [], []
    for i in range(25):
        u = i / 24
        cxu = x + (tx - x) * (u ** 1.6)
        wu = sw * (1.35 - 0.5 * u + 0.6 * max(0, 0.15 - u) / 0.15 * 0.5)
        yy = base - u * h
        sl.append((cxu - wu / 2, yy))
        sr.append((cxu + wu / 2, yy))
    sm = poly(sl + sr[::-1])
    t = np.clip((sm.X - (sm.X.min() if False else (np.interp(sm.Y[:, :1], [cy, base], [tx, x]) - sw * 0.7))) / (sw * 1.4), 0, 1)
    scol = ramp(np.clip(np.cos((t - 0.35) * math.pi * 0.9), 0, 1), [(0, stem * 0.3), (0.6, stem * 0.75), (1, stem)])
    scol = scol * (1 + sm.crop(sc.noise(5, 2, key=key + 1, sx=0.3, sy=3))[..., None] * 0.08)
    # gill light falls down the stem top
    scol = scol + (gill * 0.55 * sstep(cy + h * 0.45, cy, sm.Y)[..., None])
    lay.paint(sm, scol)
    # skirt
    sy_ = cy + h * 0.2
    sk = poly(blob_pts(x + (tx - x) * 0.8 ** 1.6, sy_, sw * 1.1, sw * 0.28, rng, 0.15))
    lay.paint(sk, lerp(stem * 0.6, gill * 0.8, 0.35))
    # underside with gills
    um = ellipse(tx, cy, rx * 0.96, ry * 0.26)
    ang = np.arctan2((um.Y - cy) / (ry * 0.26), (um.X - tx) / rx)
    d = np.sqrt(((um.X - tx) / rx) ** 2 + ((um.Y - cy) / (ry * 0.26)) ** 2)
    gl = np.abs(np.sin(ang * 60))
    gcol = lerp(gill * 0.35, gill, (sstep(0.2, 1.0, d) * (0.6 + 0.4 * gl))[..., None])
    lay.paint(um, gcol)
    glow.add(um.k(sstep(0.3, 1.0, d) * (0.4 + 0.6 * gl)), gill, 0.45 * gk)
    # cap dome
    pts = []
    for i in range(41):
        a = math.pi * i / 40
        rr = 1 + 0.03 * math.sin(a * 5 + key)
        pts.append((tx + math.cos(a) * rx * rr, cy - math.sin(a) ** 0.85 * ry * rr))
    for i in range(1, 20):
        a = math.pi * i / 20
        pts.append((tx - math.cos(a) * rx, cy + math.sin(a) * ry * 0.12))
    cm = poly(pts)
    nx = (cm.X - tx) / rx
    ny = (cm.Y - cy) / ry
    nz = np.sqrt(np.clip(1 - nx * nx - np.clip(ny, -1, 0) ** 2, 0, 1))
    top = np.clip(-ny * 0.6 + nz * 0.45 - nx * 0.25, 0, 1)
    col = ramp(top, [(0, cap_dk * 0.6), (0.5, cap_dk), (1, cap)])
    rim = sstep(0.55, 1.0, np.sqrt(nx * nx + np.clip(ny, -1, 0) ** 2))
    col = lerp(col, lerp(cap, spot, 0.5), (rim * 0.6)[..., None])
    col = col * (1 + cm.crop(sc.noise(8, 3, key=key + 2))[..., None] * 0.07)
    lay.paint(cm, col)
    glow.add(cm.k(rim ** 2 * 0.6), spot, 0.35 * gk)
    # spots
    sp = []
    for i in range(spots):
        a = pick(rng, 0.12, 0.88) * math.pi
        rr = pick(rng, 0.15, 0.92)
        px = tx + math.cos(a) * rx * rr
        py = cy - math.sin(a) ** 0.85 * ry * rr * 0.95
        fs = math.sqrt(max(0.05, 1 - rr * rr))
        sz = pick(rng, 0.05, 0.11) * rx
        sp.append(blob_pts(px, py, sz * (0.6 + 0.4 * fs), sz * 0.55 * (0.5 + 0.5 * fs), rng, 0.2, n=14))
    spm = polys(sp, feather=0.8)
    spm = Mask(spm.a * cm.full()[spm.sl], spm.x0, spm.y0)
    lay.paint(spm, lerp(spot, C("#ffffff"), 0.25))
    glow.add(spm, spot, 0.9 * gk)
    glow.add(spm.blurred(6), spot, 0.5 * gk)
    # halo and light spill
    glow.add(gauss(tx, cy, rx * 1.3, ry * 1.4), gill, 0.12 * gk)
    if haze is not None and hk > 0:
        for m in (sm, cm, um):
            lay.haze(m, haze, hk)
    return cm


def mush_cluster(lay, glow, sc, rng, x, base, n, size, cap, cap_dk, spot, gill, stem, gk=1.0, key=0, haze=None, hk=0.0):
    for i in range(n):
        h = size * pick(rng, 0.4, 1.0)
        mushroom(lay, glow, sc, rng, x + pick(rng, -size * 0.9, size * 0.9), base + pick(rng, -size * 0.1, size * 0.15), h,
                 h * pick(rng, 0.45, 0.7), h * pick(rng, 0.22, 0.32), h * 0.16, cap, cap_dk, spot, gill, stem,
                 lean=pick(rng, -0.25, 0.25), gk=gk, key=key + i, spots=5, haze=haze, hk=hk)


def stalactite(lay, sc, x, top, length, w, dark, mid_, lite, key=0, up=False):
    pts = []
    n = 10
    for i in range(n + 1):
        u = i / n
        ww = w * (1 - u) ** 1.3
        pts.append((x - ww / 2 + math.sin(u * 5 + key) * w * 0.05, top + (length * u if not up else -length * u)))
    for i in range(n, -1, -1):
        u = i / n
        ww = w * (1 - u) ** 1.3
        pts.append((x + ww / 2 + math.sin(u * 5 + key) * w * 0.05, top + (length * u if not up else -length * u)))
    m = poly(pts)
    col = cyl_shade(m, x - w / 2, x + w / 2, dark, mid_, lite)
    col = col * (1 + m.crop(sc.noise(6, 2, key=key, sx=0.4, sy=2))[..., None] * 0.1)
    lay.paint(m, col)
    return m


def mushroom_cave(seed=23):
    rng = np.random.default_rng(seed)
    sc = Noise(seed)
    far, mid, near, rays, glow = Layer(), Layer(), Layer(), Light(), Light()
    teal, teal_dk, teal_sp, teal_g = C("#2f8f96"), C("#123a4a"), C("#8ffcff"), C("#4fe8d8")
    vio, vio_dk, vio_sp, vio_g = C("#7a4ab8"), C("#2a1650"), C("#f0a8ff"), C("#c070ff")
    stemc = C("#c9c3dc")
    haze = C("#253a66")
    hole = (820, -40)

    # ---------------- far: cavern depths
    far.paint(full_mask(), vgrad([(0, C("#070a18")), (0.35, C("#0e1834")), (0.62, C("#1d3358")), (0.75, C("#2a4a70")), (1, C("#0c1426"))], 0, H))
    far.light(gauss(900, 560, 700, 160), C("#2a6a8a"), 0.35)
    # moonlit opening high in the vault
    far.light(gauss(hole[0], 30, 170, 90), C("#9ccfff"), 0.35)
    # distant cave wall rows, lighter and bluer with distance
    for i, (y0, amp, col, hkk) in enumerate(((430, 150, C("#1a2a4c"), 0.55), (500, 120, C("#142240"), 0.35), (560, 90, C("#0f1a34"), 0.2))):
        rp = ridge(rng, -40, 1960, y0, amp, rough=0.6, peaks=[(pick(rng, 200, 600), y0 - amp * 1.5, 150), (pick(rng, 1300, 1700), y0 - amp * 1.4, 180)])
        m = poly([(-40, 700)] + rp + [(1960, 700)])
        c, _ = rock_col(sc, m, col * 0.6, col, lerp(col, C("#4a8aa8"), 0.5), key=200 + i, cell=90, sy=2.0, bulge=60)
        far.paint(m, c)
        far.haze(m, haze, hkk)
        # distant glowing mushrooms along each row
        for j in range(5 + i * 2):
            mx = pick(rng, 80, 1840)
            mh = pick(rng, 40, 90) * (1 + i * 0.5)
            yb = np.interp(mx, [p[0] for p in rp], [p[1] for p in rp]) + pick(rng, 30, 90)
            use_t = rng.random() < 0.55
            mushroom(far, glow, sc, rng, mx, yb, mh, mh * 0.55, mh * 0.25, mh * 0.12,
                     teal if use_t else vio, teal_dk if use_t else vio_dk, teal_sp if use_t else vio_sp,
                     teal_g if use_t else vio_g, stemc * 0.6, gk=0.35 + i * 0.15, key=300 + i * 10 + j, spots=4,
                     haze=haze, hk=0.55 - i * 0.15)
    # far lake glow at the horizon
    lake = ellipse(980, 628, 520, 26, feather=4)
    far.paint(lake, C("#3fb0c0"))
    far.light(lake.k(1), C("#8ff0ff"), 0.25)
    far.haze(full_mask(sstep(480, 620, YY) * (1 - sstep(640, 700, YY)) * 0.5), C("#2f5a80"))
    # the vault ceiling with stalactites
    ceil = poly([(-20, -20), (1940, -20), (1940, 120)] + [(x, 90 + 50 * math.sin(x / 190) + 25 * math.sin(x / 57)) for x in range(1920, -21, -40)])
    c, _ = rock_col(sc, ceil, C("#05070f"), C("#111a30"), C("#2a3e60"), key=210, cell=80, bulge=40)
    hm = ellipse(hole[0], 0, 150, 70, feather=6)
    far.paint(ceil, c)
    far.erase(hm, 0.0)
    far.paint(hm, C("#6f9ccc"))
    far.light(hm, C("#cfe8ff"), 0.4)
    for i in range(26):
        sx0 = pick(rng, 0, 1920)
        if abs(sx0 - hole[0]) < 150:
            continue
        stalactite(far, sc, sx0, 60 + 40 * math.sin(sx0 / 190), pick(rng, 60, 200), pick(rng, 20, 50),
                   C("#070a14"), C("#16223c"), C("#2f4a6a"), key=i)

    # ---------------- mid: cave walls, floor, pools, giant mushrooms
    # floor
    fl = poly([(0, 640)] + [(x, 636 + 10 * math.sin(x / 150)) for x in range(0, 1961, 40)] + [(1920, 1080), (0, 1080)])
    X, Y = fl.X, fl.Y
    dz = np.clip((Y - 630) / 450, 0, 1)
    hgt = fl.crop(sc.noise(120, 4, key=40, sx=3.0, gain=0.5)) * (3 + dz * 14) + fl.crop(sc.noise(25, 3, key=41, sx=2.5)) * (0.6 + dz * 3)
    gyh, gxh = np.gradient(hgt)
    lit = np.clip(0.45 - gyh * 1.2 + gxh * 0.2, 0, 1)
    moss = sstep(-0.2, 0.6, fl.crop(sc.noise(60, 4, key=42, sx=2.0)))
    rockc = ramp(lit, [(0, C("#0a0e1a")), (0.5, C("#1c2640")), (1, C("#3a4a68"))])
    mossc = ramp(lit, [(0, C("#0c2224")), (0.5, C("#16423e")), (1, C("#2e7a66"))])
    col = lerp(rockc, mossc, moss[..., None])
    col = lerp(col, C("#1f3a5c"), ((1 - dz) ** 3 * 0.6)[..., None])
    mid.paint(fl, col)
    # glowing moss specks
    speck = np.clip(fl.crop(sc.noise(4, 1, key=43)) - 2.0, 0, 1) * moss * sstep(640, 700, Y)
    glow.add(Mask(speck, fl.x0, fl.y0), teal_g, 0.8)
    # pools
    for (px, py, prx, pry, pc) in ((960, 700, 190, 24, teal_g), (1520, 850, 260, 40, vio_g), (380, 870, 200, 34, teal_g)):
        pm = poly(blob_pts(px, py, prx, pry, rng, 0.18, n=40), feather=1.5)
        d = np.sqrt(((pm.X - px) / prx) ** 2 + ((pm.Y - py) / pry) ** 2)
        pcol = lerp(pc * 0.25, pc * 0.8, sstep(1.0, 0.2, d)[..., None])
        mid.paint(pm, pcol)
        mid.paint(Mask(pm.a * sstep(0.75, 0.98, d), pm.x0, pm.y0), lerp(pc, C("#ffffff"), 0.4), 0.6)
        glow.add(pm.k(sstep(1.0, 0.3, d)), pc, 0.35)
        mid.light(gauss(px, py, prx * 1.6, pry * 4), pc, 0.12)
    # cave walls left and right
    for sgn in (-1, 1):
        xe = 0 if sgn < 0 else W
        pts = [(xe, -20)]
        for i in range(12):
            u = i / 11
            yy = -20 + u * 800
            xx = xe - sgn * (170 + 90 * math.sin(u * 5 + sgn) + 50 * pick(rng, -1, 1) + 60 * u)
            pts.append((xx, yy))
        pts.append((xe, 820))
        m = edge_noise(poly(pts), sc.noise(14, 3, key=50 + sgn), 1.2)
        c, n = rock_col(sc, m, C("#04060c"), C("#141c30"), C("#3a4e70"), key=51 + sgn, cell=70, sy=2.2, bulge=70)
        mid.paint(m, c)
    # stalagmites
    for sx0, sb, sl_, sw_ in ((150, 800, 260, 70), (1800, 810, 300, 80), (560, 668, 90, 26), (1330, 664, 120, 30), (1100, 650, 60, 18)):
        stalactite(mid, sc, sx0, sb, sl_, sw_, C("#060912"), C("#1a2640"), C("#3e5878"), key=sx0, up=True)
    # giant mushrooms: far pair then the two framing giants
    mushroom(mid, glow, sc, rng, 700, 662, 190, 95, 42, 26, vio, vio_dk, vio_sp, vio_g, stemc * 0.8, lean=-0.1, gk=0.8, key=1, haze=haze, hk=0.25)
    mushroom(mid, glow, sc, rng, 1240, 660, 280, 135, 56, 34, teal, teal_dk, teal_sp, teal_g, stemc * 0.8, lean=0.08, gk=0.8, key=2, haze=haze, hk=0.22)
    mushroom(mid, glow, sc, rng, 1690, 760, 560, 300, 112, 72, vio, vio_dk, vio_sp, vio_g, stemc, lean=-0.12, gk=1.0, key=3)
    mushroom(mid, glow, sc, rng, 260, 770, 620, 330, 124, 80, teal, teal_dk, teal_sp, teal_g, stemc, lean=0.1, gk=1.0, key=4)
    # small clusters at the feet of the giants and along the floor edge
    mush_cluster(mid, glow, sc, rng, 450, 770, 5, 60, teal, teal_dk, teal_sp, teal_g, stemc, key=20)
    mush_cluster(mid, glow, sc, rng, 1500, 775, 5, 64, vio, vio_dk, vio_sp, vio_g, stemc, key=30)
    mush_cluster(mid, glow, sc, rng, 860, 668, 4, 26, teal, teal_dk, teal_sp, teal_g, stemc, key=40, haze=haze, hk=0.3)
    mush_cluster(mid, glow, sc, rng, 1400, 672, 4, 30, vio, vio_dk, vio_sp, vio_g, stemc, key=50, haze=haze, hk=0.3)
    # light spill from the giants onto the floor, darkness toward the viewer
    mid.light(gauss(300, 780, 380, 80), teal_g, 0.14)
    mid.light(gauss(1650, 780, 360, 80), vio_g, 0.14)
    mid.light(gauss(940, 770, 260, 60), C("#bfe6ff"), 0.14)
    mid.mult(full_mask(sstep(840, 1080, YY) * 0.6), C("#05070e"))
    # hanging roots with glowing bulbs from the vault
    for rx0, ln in ((560, 260), (1080, 180), (1390, 300), (1180, 120)):
        pts = [(rx0 + math.sin(i * 0.7) * 6, -10 + ln * i / 10) for i in range(11)]
        mid.paint(stroke(pts, 3, taper=(6, 2)), C("#1a2034"))
        for k in range(3):
            by = ln * pick(rng, 0.4, 1.0)
            bm = ellipse(rx0 + math.sin(by / ln * 7) * 6, by, 5, 7)
            mid.paint(bm, lerp(teal_sp, C("#ffffff"), 0.3))
            glow.add(gauss(rx0, by, 10, 12), teal_g, 0.6)

    # ---------------- near: dark framing
    nd = C("#04050b")
    for (cx0, cy0, rx_, ry_) in ((60, 1040, 280, 140), (1860, 1030, 260, 160), (300, 1090, 180, 60), (1600, 1095, 200, 60)):
        bm = poly(blob_pts(cx0, cy0, rx_, ry_, rng, 0.25))
        c, _ = rock_col(sc, bm, C("#020305"), C("#0a0f1a"), C("#1c2a40"), key=60, cell=rx_ * 0.5)
        near.paint(bm, c)
    mushroom(near, glow, sc, rng, 120, 1080, 260, 170, 60, 40, teal * 0.4, teal_dk * 0.5, teal_sp, teal_g * 0.5, stemc * 0.25,
             lean=0.15, gk=0.35, key=70, spots=8)
    mushroom(near, glow, sc, rng, 1800, 1100, 200, 150, 52, 34, vio * 0.4, vio_dk * 0.5, vio_sp, vio_g * 0.5, stemc * 0.25,
             lean=-0.2, gk=0.35, key=71, spots=7)
    for x0, ln in ((40, 360), (110, 240), (1850, 320), (1760, 200), (230, 150)):
        pts = [(x0 + math.sin(i * 0.9) * 10, -10 + ln * i / 10) for i in range(11)]
        near.paint(stroke(pts, 9, taper=(14, 4)), nd)
    near.blur_all(4.0)

    # ---------------- rays and glow
    god_rays(rays, sc, hole, [(70, 3.0, 0.2), (76, 2.2, 0.26), (82, 3.5, 0.2), (88, 2.0, 0.14), (64, 2.0, 0.1)],
             C("#bfe2ff"), length=1000, start=60, dust=0.5)
    rays.add(gauss(950, 770, 240, 50), C("#bfe2ff"), 0.1)
    rays.add(gauss(260, 170, 420, 200), teal_g, 0.12)
    rays.add(gauss(1690, 220, 380, 180), vio_g, 0.12)
    rays.add(gauss(960, 690, 260, 60), teal_g, 0.1)

    fx = {
        "spores": [[40, 150, 600, 620], [1300, 180, 600, 600], [600, 450, 700, 300]],
        "drips": [[330, 150], [520, 170], [1130, 130], [1450, 160], [1620, 120]],
        "motes": [[820, 60, 260, 700]],
        "fireflies": [[300, 600, 1300, 220]],
        "ground_y": GROUND_Y,
    }
    return far, mid, near, rays, glow, fx


SCENES = {
    "rotten_cellar": rotten_cellar,
    "mushroom_cave": mushroom_cave,
    "frozen_pass": frozen_pass,
}


def main(ids):
    ids = ids or list(SCENES)
    for sid in ids:
        t = time.time()
        layers = SCENES[sid]()
        save_layers(sid, *layers)
        print(f"{sid}: {time.time() - t:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])

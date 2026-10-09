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


# ============================================================== fire / smoke / cloth helpers

FIRE_STOPS = [(0, C("#4a0a04")), (0.22, C("#a8200a")), (0.45, C("#ec5a10")), (0.68, C("#ffa030")),
              (0.86, C("#ffd878")), (1, C("#fff6d8"))]
LAVA_STOPS = [(0, C("#1c0605")), (0.25, C("#5a1006")), (0.45, C("#c0300a")), (0.62, C("#f06a12")),
              (0.8, C("#ffb03a")), (0.93, C("#ffe48a")), (1, C("#fff8e0"))]


def box(x0, y0, x1, y1):
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    if x1 <= x0 or y1 <= y0:
        return Mask(np.zeros((1, 1), F32))
    return Mask(np.ones((y1 - y0, x1 - x0), F32), x0, y0)


def fire(lay, glow, sc, x, base, w, h, key=0, k=1.0, lean=0.0, alpha=0.95, halo=1.0):
    """Blaze of flame tongues rising from a base line, cut from tall stretched noise fields
    inside a tapering envelope: dark red licks, orange body, white-yellow core.
    Colour goes to lay, emission to glow."""
    m = box(x - w * 0.8 - abs(lean) * h, base - h * 1.35, x + w * 0.8 + abs(lean) * h, base + 10)
    if m.a.shape == (1, 1):
        return
    X, Y = m.X, m.Y
    cls = 14 if w < 70 else (28 if w < 200 else 56)
    nA = m.crop(sc.noise(cls * 0.8, 3, key=600, sx=0.45, sy=2.2))
    nB = m.crop(sc.noise(cls * 1.6, 2, key=601, sx=0.8, sy=2.0))
    nC = m.crop(sc.noise(cls * 0.35, 2, key=602, sx=0.6, sy=1.4))
    v = (base - Y) / h
    vc = np.clip(v, 0, 1.4)
    u = (X - x) / (w * 0.5) - lean * vc + nB * 0.28 * vc
    u = u / np.clip(1.0 - 0.55 * vc, 0.25, 1)
    env = np.clip(1 - u * u, 0, 1)
    turb = np.tanh(nA * 0.7) * (0.15 + 0.55 * vc) + nC * 0.06
    heat = env ** 0.6 * (1.05 - vc * 0.95 + turb) - 0.06
    heat = heat * sstep(base + 10, base - 6 + nC * 6, Y) * (1 - sstep(0.95, 1.3, v))
    a = sstep(0.0, 0.18, heat)
    t = np.clip(heat * 1.15, 0, 1)
    lay.paint(Mask(a, m.x0, m.y0), ramp(t, FIRE_STOPS), alpha)
    glow.add(Mask(a * sstep(0.45, 1.0, t), m.x0, m.y0), C("#ffc86a"), 0.7 * k)
    glow.add(Mask(a * t, m.x0, m.y0), C("#ff5a14"), 0.22 * k)
    if halo:
        glow.add(gauss(x, base - h * 0.4, w * 0.9, h * 0.75), C("#ff5a14"), 0.16 * k * halo)


def smoke_field(sc, key, y0, y1, sx=1.8):
    d = sc.noise(260, 5, key=key, sx=sx, gain=0.55) + sc.noise(60, 3, key=key + 1, sx=1.3) * 0.35
    return d


def lit_smoke(lay, sc, dens, under, top, mid_col, k_under=1.0):
    """Paint a smoke density field lit from below by fire (orange undersides, dark crowns)."""
    b = blur(dens, 6)
    g = np.gradient(b, axis=0)
    und = np.clip(-g * 60 * k_under + 0.15, 0, 1)
    col = lerp(lerp(top, mid_col, np.clip(b * 1.5, 0, 1)[..., None]), under, und[..., None])
    lay.paint(full_mask(dens), col)


def banner(lay, glow, sc, rng, x, top, w, h, key=0, light=1.0, burn=0.0, rod=True):
    """Red cult banner: rod with finials, swallow-tailed cloth with folds, gold trim and
    the spiked-sun eye sigil; burn > 0 chars the hem and sets a fire on it."""
    hw = w / 2
    pts = [(x - hw, top), (x + hw, top)]
    for i in range(1, 9):
        u = i / 8
        pts.append((x + hw + math.sin(u * 3 + key) * w * 0.03, top + h * u))
    tail = h * 0.86
    pts += [(x + hw * 0.1, top + tail), (x, top + tail - h * 0.06), (x - hw * 0.1, top + tail)]
    for i in range(8, 0, -1):
        u = i / 8
        pts.append((x - hw + math.sin(u * 3 + key + 1) * w * 0.03, top + h * u))
    if burn:
        # ragged burnt hem
        for i in range(len(pts)):
            px, py = pts[i]
            if py > top + h * 0.7:
                pts[i] = (px, py - pick(rng, 0, h * 0.12 * burn))
    m = edge_noise(poly(pts), sc.noise(5, 2, key=key + 3), 0.8, s=1.0)
    X, Y = m.X, m.Y
    ph = m.crop(sc.noise(30, 2, key=key + 4)) * 0.6
    f = np.sin((X - x) / w * math.pi * 3.4 + ph + (Y - top) / h * 0.8)
    shade = np.clip(0.62 + 0.3 * f - (X - x) / w * 0.35, 0.15, 1.15)
    shade = shade * (0.8 + 0.2 * sstep(top + h, top, Y))
    cloth = ramp(np.clip(shade, 0, 1), [(0, C("#2a0406")), (0.4, C("#7a0e10")), (0.75, C("#b8201a")), (1, C("#ec5038"))])
    edge = np.maximum(sstep(hw - 9, hw - 5, np.abs(X - x)) * (1 - sstep(hw - 2, hw, np.abs(X - x))),
                      sstep(top + 6, top + 9, Y) * (1 - sstep(top + 14, top + 17, Y)))
    gold = ramp(np.clip(shade, 0, 1), [(0, C("#3a2408")), (0.6, C("#b0802a")), (1, C("#ffe08a"))])
    cloth = lerp(cloth, gold, edge[..., None])
    cloth = cloth * (1 + m.crop(sc.noise(2.5, 2, key=key + 5, sx=0.3, sy=2))[..., None] * 0.06)
    lay.paint(m, cloth * light)
    Sf = np.zeros((H, W), F32)
    Sf[m.sl] = shade
    # sigil: spiked sun, dark disc, burning eye
    sx, sy, r = x, top + h * 0.36, w * 0.33
    sun_pts = []
    for i in range(24):
        a = i / 24 * 2 * math.pi
        rr = r if i % 2 == 0 else r * 0.68
        sun_pts.append((sx + math.cos(a) * rr, sy + math.sin(a) * rr))
    for pm, col in ((poly(sun_pts, 0.6), C("#d8a440")), (ellipse(sx, sy, r * 0.58, r * 0.58, 0.6), C("#3a0608")),
                    (ellipse(sx, sy, r * 0.48, r * 0.24, 0.6), C("#ffcc4a")),
                    (ellipse(sx, sy, r * 0.09, r * 0.22, 0.5), C("#1a0204"))):
        pm = Mask(pm.a * m.full()[pm.sl], pm.x0, pm.y0)
        lay.paint(pm, col * np.clip(Sf[pm.sl] + 0.25, 0.3, 1.2)[..., None] * light)
    glow.add(ellipse(sx, sy, r * 0.48, r * 0.24, 2), C("#ffb040"), 0.25 * light)
    if rod:
        lay.paint(stroke([(x - hw - 14, top - 2), (x + hw + 14, top - 2)], 7), C("#2a1c14"))
        for ex in (x - hw - 16, x + hw + 16):
            lay.paint(ellipse(ex, top - 2, 7, 7), C("#8a6a30") * light)
    if burn:
        char = Mask(m.a * sstep(top + h * 0.55, top + h * 0.85, Y), m.x0, m.y0)
        lay.mult(char, C("#140404"), 0.85)
        glow.add(Mask(m.a * np.exp(-((Y - (top + h * 0.8)) / 10) ** 2) * sstep(0.2, 0.8, m.crop(sc.noise(6, 2, key=key + 8)) + 0.5), m.x0, m.y0),
                 C("#ff7a20"), 0.8)
        fire(lay, glow, sc, x - hw * 0.4, top + h * 0.8, w * 0.6, h * 0.35, key=key, k=0.9 * burn)
    return m


def rubble(lay, sc, rng, cx, base, w, h, n, dark, mid_, lite, key=0, light=1.0):
    """Heap of broken stone blocks, back to front."""
    for i in range(n):
        u = rng.uniform(-1, 1)
        bx = cx + u * w * 0.5
        top = base - h * (1 - u * u) * pick(rng, 0.5, 1.0)
        r = pick(rng, 0.08, 0.2) * w * (0.6 + 0.4 * (1 - abs(u)))
        r = min(r, h * 0.6 + 8)
        by = min(base - r * 0.3, top + r * 0.6 + i / n * h * 0.4)
        bm = edge_noise(poly(blob_pts(bx, by, r * pick(rng, 1.0, 1.5), r * pick(rng, 0.6, 0.9), rng, 0.3, n=10,
                                       rot=pick(rng, -0.4, 0.4))), sc.noise(8, 2, key=key + 1), 0.8)
        col, _ = rock_col(sc, bm, dark, mid_, lite, nscale=max(8, r * 0.7), key=key + i % 5, cell=max(10, r * 0.7), crack=0.5)
        lay.paint(bm, col * light)


def beam(lay, sc, x0, y0, x1, y1, w, dark, mid_, lite, key=0, char=0.7, broken=True):
    """Squared timber beam with charred, cracked surface; lit along its upper edge."""
    ang = math.atan2(y1 - y0, x1 - x0)
    nx, ny = -math.sin(ang) * w / 2, math.cos(ang) * w / 2
    end = [(x1 + nx, y1 + ny), (x1 - nx, y1 - ny)]
    if broken:
        L = math.hypot(x1 - x0, y1 - y0)
        dx, dy = (x1 - x0) / L, (y1 - y0) / L
        end = [(x1 + nx + dx * w * 0.2, y1 + ny + dy * w * 0.2), (x1 + nx * 0.3 - dx * w * 0.3, y1 + ny * 0.3 - dy * w * 0.3),
               (x1 - nx * 0.2 + dx * w * 0.5, y1 - ny * 0.2 + dy * w * 0.5), (x1 - nx - dx * w * 0.15, y1 - ny - dy * w * 0.15)]
    pts = [(x0 + nx, y0 + ny)] + end + [(x0 - nx, y0 - ny)]
    m = poly(pts)
    X, Y = m.X, m.Y
    # across-beam coordinate: -1 (upper/left edge) .. 1
    s = ((X - x0) * -math.sin(ang) + (Y - y0) * math.cos(ang)) / (w / 2)
    t = np.clip(0.75 - s * 0.45 + (s < -0.55) * 0.25, 0, 1)
    col = ramp(t, [(0, dark), (0.55, mid_), (1, lite)])
    al = (X - x0) * math.cos(ang) + (Y - y0) * math.sin(ang)
    gr = np.sin(al / 9.0 + m.crop(sc.noise(20, 2, key=key + 1)) * 2.0)
    col = col * (1 + gr[..., None] * 0.06)
    # alligator char checks
    ck = m.crop(sc.noise(7, 2, key=key + 2, sx=1.6, sy=0.6))
    col = col * (1 - (sstep(0.9, 1.4, np.abs(ck)) * char * 0.6))[..., None]
    lay.paint(m, col)
    return m, s


def ember_cracks(m, sc, key, thick=0.97):
    """Thin glowing crack network from ridged noise."""
    n = m.crop(sc.noise(70, 3, key=key, sx=1.6, gain=0.45))
    r = 1 - np.abs(n) * 0.5
    return sstep(thick, 0.995, r)


def cells(u, v, key=0, jit=0.8):
    """Jittered-grid voronoi in unit cells (3x3 search): nearest / second distance and a
    random value per nearest cell."""
    iu, iv = np.floor(u), np.floor(v)
    d1 = np.full(u.shape, 9.0, F32)
    d2 = np.full(u.shape, 9.0, F32)
    rid = np.zeros(u.shape, F32)
    for du in (-1, 0, 1):
        for dv in (-1, 0, 1):
            cu, cv = iu + du, iv + dv
            px = cu + 0.5 + (hash2(cu, cv, key) - 0.5) * jit
            py = cv + 0.5 + (hash2(cv, cu, key + 5) - 0.5) * jit
            d = np.sqrt((u - px) ** 2 + (v - py) ** 2)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            rid = np.where(closer, hash2(cu, cv, key + 11), rid)
            d1 = np.where(closer, d, d1)
    return d1, d2, rid


# ============================================================== BURNT KEEP

def burnt_keep(seed=41):
    rng = np.random.default_rng(seed)
    sc = Noise(seed)
    HOR, CX = 480.0, 960.0
    Z0, HW = 10.0, 4.6
    far, mid, near, rays, glow = Layer(), Layer(), Layer(), Light(), Light()
    stone = [(0, C("#22160f")), (0.35, C("#38261c")), (0.7, C("#503526")), (1, C("#684534"))]
    mortar = C("#0e0806")
    soot = C("#0a0504")

    def pp(Z, xw, yw):
        return P(Z, xw, yw, HOR, CX)

    # ---------------- far: burning sky, smoke, the outer keep ablaze
    sky = vgrad([(0, C("#140708")), (0.3, C("#3a1210")), (0.6, C("#8a2a14")), (0.82, C("#e0661e")), (1, C("#ffb050"))], 0, 600)
    far.paint(full_mask(), sky)
    far.light(gauss(980, 560, 520, 160), C("#ffb040"), 0.35)
    dens = smoke_field(sc, 700, 0, 600)
    dens = np.clip((dens + 0.2) * 0.75, 0, 1) * (1 - sstep(380, 560, YY) * 0.85)
    lit_smoke(far, sc, dens * 0.9, C("#ff8a30"), C("#140a0a"), C("#4a2420"))
    # distant curtain wall and towers of the keep, burning
    wall2 = ridge(rng, 600, 1400, 520, 6, steps=5)
    far.paint(poly([(600, 600)] + [(x, y) for x, y in wall2] + [(1400, 600)]), C("#2a1210"))
    castle(far, 990, 560, 1.05, C("#1c0c0c"), C("#5a2418"), C("#120808"), C("#3a1a14"), win=C("#ffb050"), rng=rng)
    for fx_, fy_, fw, fh in ((905, 470, 18, 34), (1042, 398, 16, 36), (1085, 520, 34, 46), (840, 545, 44, 40), (1150, 480, 16, 30)):
        fire(far, glow, sc, fx_, fy_, fw, fh, key=int(fx_), k=0.6)
    dens2 = np.clip(sc.noise(90, 4, key=710, sx=0.5, sy=1.6) * 0.5 + 0.2, 0, 1) * gauss(1020, 300, 120, 260).full()
    lit_smoke(far, sc, dens2 * 0.85, C("#ff7a28"), C("#1a0c0c"), C("#3a1c18"))
    far.haze(full_mask(sstep(420, 600, YY) * 0.25), C("#ff9a48"))

    # back wall of the hall, its top and centre torn open
    bx0, bx1 = pp(Z0, -HW, 0)[0], pp(Z0, HW, 0)[0]
    by_floor = pp(Z0, 0, 0)[1]
    top_edge = [(x, y) for x, y in ridge(rng, bx0 - 4, bx1 + 4, 70, 40, steps=6, rough=0.6)]
    breach = [(700, -40), (735, 110), (705, 190), (752, 290), (790, 372), (812, 452), (850, 520), (905, 556),
              (1010, 562), (1090, 530), (1140, 470), (1185, 392), (1172, 300), (1222, 205), (1200, 100), (1240, -40)]
    wpts = [(bx0 - 2, by_floor)] + top_edge + [(bx1 + 2, by_floor)]
    bw_m = poly(wpts)
    holef = edge_noise(poly(breach), sc.noise(12, 3, key=720), 0.7, sharp=4.0, s=2.0).full()
    bw_m = Mask(bw_m.a * (1 - holef[bw_m.sl]), bw_m.x0, bw_m.y0)
    s9 = FOCAL / Z0
    col, _ = ashlar(bw_m, bx0, by_floor, 0.8 * s9, 0.38 * s9, stone, mortar, lw=3, key=6, sc=sc)
    far.paint(bw_m, col)
    # broken edge: lit by the fire beyond, sooty face
    rimf = np.clip(blur(holef, 12) * 2.5, 0, 1) * (1 - holef)
    far.mult(Mask(bw_m.a * sstep(420, 60, bw_m.Y), bw_m.x0, bw_m.y0), soot, 0.55)
    far.light(full_mask(rimf * sstep(80, 560, YY)), C("#ff7a30"), 0.45)
    # pointed windows glowing with the fire outside
    wins = [(505, 445, 62, 255), (1420, 445, 62, 255)]
    for wx, sill, hw_, spring in wins:
        outer = [(wx - hw_ - 18, sill + 8)] + arch_pts(wx, spring, hw_ + 18, 0.35) + [(wx + hw_ + 18, sill + 8)]
        fr = poly(outer)
        far.paint(fr, ramp(np.clip(0.7 - (fr.X - wx) / (hw_ * 4), 0, 1), [(0, C("#2a1a12")), (1, C("#6a4632"))]))
        op = [(wx - hw_, sill)] + arch_pts(wx, spring, hw_, 0.35) + [(wx + hw_, sill)]
        om = poly(op)
        far.paint(om, ramp(sstep(sill, spring - hw_, om.Y), [(0, C("#ffcf70")), (0.5, C("#f06a1e")), (1, C("#7a1a0e"))]))
        glow.add(om.k(sstep(spring - hw_, sill, om.Y)), C("#ffb050"), 0.45)
        # mullion and tracery
        bars = [[(wx - 4, spring - hw_ * 0.6), (wx + 4, spring - hw_ * 0.6), (wx + 4, sill), (wx - 4, sill)],
                [(wx - hw_, spring + 50), (wx + hw_, spring + 50), (wx + hw_, spring + 56), (wx - hw_, spring + 56)]]
        bm = polys(bars)
        far.paint(Mask(bm.a * om.full()[bm.sl], bm.x0, bm.y0), C("#1a0c08"))
        far.light(gauss(wx, sill + 40, hw_ * 2.2, 90), C("#ff9a48"), 0.18)
        far.light(gauss(wx, spring, hw_ * 3, 220), C("#ff7a2a"), 0.08)
    # side walls of the hall
    for sgn in (-1, 1):
        xe = 0 if sgn < 0 else W
        Ze = abs(HW * FOCAL / (xe - CX))
        fy = pp(Ze, 0, 0)[1]
        xb = bx0 if sgn < 0 else bx1
        wm = poly([(xe, -10), (xb, -10), (xb, by_floor), (xe, fy)])
        col, Zw, _, _ = wall_persp(sc, wm, HOR, CX, sgn * HW, 0.9, 0.42, stone, mortar, key=8 + sgn)
        far.paint(wm, col * (0.8 if sgn < 0 else 0.62))
    # banners on the back wall corners
    banner(far, glow, sc, rng, bx0 + 85, 200, 96, 330, key=11, light=0.85)
    banner(far, glow, sc, rng, bx1 - 85, 200, 96, 330, key=12, light=0.75, burn=1.0)
    # soot streaks, firelight from below, darkness high up
    walls = np.clip(bw_m.full() + ((XX < bx0) | (XX > bx1)) * (YY < 760), 0, 1)
    streak = np.clip(sc.noise(36, 3, key=730, sx=0.35, sy=3.0) - 0.3, 0, 2) * 0.45
    far.mult(full_mask(blur(np.clip(streak, 0, 0.7), 2) * sstep(640, 100, YY) * walls), soot)
    far.light(full_mask(walls * gauss(960, 620, 520, 200).full()), C("#ff7a2a"), 0.14)
    far.mult(full_mask(walls * np.clip(sstep(330, -20, YY) * 0.55 + (sstep(500, 0, XX) + sstep(1420, 1920, XX)) * 0.3, 0, 0.75)), soot)
    # rubble filling the base of the breach
    rubble(far, sc, rng, 965, 640, 520, 110, 26, C("#1a0e0a"), C("#4a2c20"), C("#b07050"), key=740)
    far.light(gauss(965, 560, 260, 70), C("#ff9a48"), 0.3)
    fire(far, glow, sc, 905, 590, 120, 120, key=21, k=0.9)
    fire(far, glow, sc, 1065, 585, 90, 150, key=22, k=0.9)

    # ---------------- mid: floor, pillars, fallen beams, rafters
    Ze = abs(HW * FOCAL / CX)
    fl = poly([(0, pp(Ze, 0, 0)[1]), (bx0, by_floor), (bx1, by_floor), (W, pp(Ze, 0, 0)[1]), (W, H), (0, H)])
    fstone = [(0, C("#150e0b")), (0.4, C("#241914")), (0.75, C("#33241b")), (1, C("#463024"))]
    col, Zf, rnd, joint = floor_persp(sc, fl, HOR, CX, 0.62, 0.62, fstone, mortar, key=50, lw=0.012)
    mid.paint(fl, col)
    # ash drifts and soot on the floor
    ash = sstep(0.3, 1.2, fl.crop(sc.noise(90, 4, key=51, sx=2.8)))
    mid.paint(Mask(ash * fl.a * 0.55, fl.x0, fl.y0), C("#5a4a44"))
    # glowing cracks / embers in the floor, away from the fighting ground
    cr = ember_cracks(fl, sc, 52, thick=0.985) * sstep(0.4, 1.2, fl.crop(sc.noise(160, 3, key=53)))
    cr = cr * (1 - np.exp(-((fl.X - 920) / 620) ** 2) * np.exp(-((fl.Y - 770) / 110) ** 2)) * sstep(640, 700, fl.Y)
    mid.paint(Mask(cr * fl.a, fl.x0, fl.y0), C("#ff8a2a"), 0.9)
    glow.add(Mask(cr * fl.a, fl.x0, fl.y0), C("#ff7a24"), 0.7)
    glow.add(Mask(blur(cr, 4) * fl.a, fl.x0, fl.y0), C("#ff5a14"), 0.6)
    # firelight: a warm pool from the breach, flicker spots, dark toward the viewer
    mid.light(gauss(940, 765, 560, 100), C("#ffa050"), 0.2)
    mid.light(gauss(960, 680, 300, 50), C("#ffb060"), 0.16)
    mid.mult(full_mask(np.clip(sstep(830, 1080, YY) * 0.72 + (sstep(500, 0, XX) + sstep(1420, 1920, XX)) * 0.4 * sstep(600, 1080, YY), 0, 0.85)), C("#0c0605"))

    # fallen roof beam leaning into the breach (back, right) and one lying on the left
    wood_dk, wood_md, wood_lt = C("#0e0806"), C("#2e1a10"), C("#6a4028")
    bm, s = beam(mid, sc, 1560, 120, 1170, 668, 46, wood_dk, wood_md * 0.7, wood_lt * 0.6, key=60)
    glow.add(Mask(bm.a * sstep(0.3, 0.95, s) * sstep(0.5, 1.4, bm.crop(sc.noise(9, 2, key=61)) + 0.3), bm.x0, bm.y0), C("#ff6a1a"), 0.9)
    fire(mid, glow, sc, 1290, 520, 70, 120, key=62, lean=-0.4, k=1.0)
    fire(mid, glow, sc, 1215, 650, 110, 140, key=63, k=1.1)
    mid.paint(ellipse(1210, 672, 120, 12, feather=8), soot, 0.6)
    bm, s = beam(mid, sc, 260, 676, 680, 652, 40, wood_dk, wood_md, wood_lt, key=64)
    glow.add(Mask(bm.a * sstep(0.2, 0.9, s) * sstep(0.4, 1.3, bm.crop(sc.noise(9, 2, key=65)) + 0.3), bm.x0, bm.y0), C("#ff6a1a"), 0.8)
    fire(mid, glow, sc, 600, 660, 120, 150, key=66, k=1.0)
    fire(mid, glow, sc, 430, 668, 70, 70, key=67, k=0.8)
    mid.light(gauss(600, 680, 260, 70), C("#ff8a3a"), 0.25)
    mid.light(gauss(1215, 690, 300, 70), C("#ff8a3a"), 0.25)
    rubble(mid, sc, rng, 300, 708, 300, 70, 14, C("#140a08"), C("#3a2418"), C("#9a6248"), key=68, light=0.95)
    rubble(mid, sc, rng, 1640, 712, 340, 80, 16, C("#140a08"), C("#3a2418"), C("#9a6248"), key=69, light=0.9)
    # scattered stones, a dropped shield and a broken spear
    for sx_, sy_, sr in ((760, 735, 10), (1130, 742, 12), (690, 805, 8), (1340, 820, 14), (1500, 760, 9), (540, 760, 11)):
        sm_ = poly(blob_pts(sx_, sy_, sr * 1.4, sr * 0.8, rng, 0.3, n=10))
        c, _ = rock_col(sc, sm_, C("#120a08"), C("#3a2418"), C("#a06a4c"), key=70, cell=sr)
        mid.paint(ellipse(sx_ + sr * 0.6, sy_ + sr * 0.6, sr * 1.8, sr * 0.4, feather=3), soot, 0.5)
        mid.paint(sm_, c)
    sh = ellipse(1460, 700, 36, 15)
    mid.paint(sh, ramp(np.clip(0.7 - (sh.X - 1460) / 60 - (sh.Y - 700) / 30, 0, 1), [(0, C("#3a0a0a")), (0.6, C("#8a1a14")), (1, C("#e0a060"))]))
    mid.paint(ellipse(1460, 700, 8, 4), C("#c8a050"))
    mid.paint(stroke([(470, 724), (600, 708)], 4), C("#3a2414"))
    mid.paint(poly([(600, 704), (622, 704), (604, 712)]), C("#8a8078"))

    # great pillars at the screen edges, with banners
    for sgn in (-1, 1):
        Zp = 4.0
        pxc, pbase = pp(Zp, sgn * 2.6, 0)
        pw = 0.72 * FOCAL / Zp
        x0, x1 = pxc - pw / 2, pxc + pw / 2
        shaft = poly([(x0, -20), (x1, -20), (x1, pbase), (x0, pbase)])
        c, _ = ashlar(shaft, x0, pbase, pw * 0.5, pw * 0.3, stone, mortar, lw=3, key=80 + sgn, sc=sc)
        shade = cyl_shade(shaft, x0, x1, C("#120a08"), C("#4a3226"), C("#b07050"), hl=0.25 if sgn < 0 else 0.75)
        c = c * (shade / C("#5a3a2a") * 0.75)
        mid.paint(shaft, c)
        mid.mult(shaft.k(sstep(500, 0, shaft.Y) * 0.55), soot)
        inner = x1 if sgn < 0 else x0
        mid.light(shaft.k(np.exp(-((shaft.X - inner) / 40) ** 2) * sstep(100, 600, shaft.Y)), C("#ff8a3a"), 0.22)
    banner(mid, glow, sc, rng, 72, 150, 118, 430, key=13, light=0.8, burn=0.0)
    banner(mid, glow, sc, rng, W - 72, 120, 118, 400, key=14, light=0.7, burn=1.0)

    # charred rafters left of the collapsed roof
    for (a, b, c_, d, w_) in ((-30, 60, 640, 8, 44), (1960, 30, 1340, 0, 40), (-30, 200, 300, 120, 30), (1960, 170, 1700, 120, 30)):
        bm, s = beam(mid, sc, a, b, c_, d, w_, wood_dk, wood_md * 0.8, wood_lt * 0.7, key=90 + a % 7)
        glow.add(Mask(bm.a * np.exp(-((bm.X - c_) / 40) ** 2), bm.x0, bm.y0), C("#ff6a1a"), 0.8)
        fire(mid, glow, sc, c_ - (20 if a < 0 else -20), d + 18, 50, 70, key=91 + a % 7, k=0.9, halo=0.6)
    for cx0, ln in ((380, 300), (1530, 240)):
        chain(mid, cx0, 40, cx0 + 6, ln, 4, 18, C("#1e1412"), 2.6)

    # ---------------- near: dark blurred framing (charred timber, rubble, a torn banner)
    nd = C("#060302")
    beam(near, sc, -80, 1000, 420, 1120, 90, nd, C("#1a0e08"), C("#3a2014"), key=100, broken=False)
    for (cx0, cy0, rx_, ry_) in ((1790, 1050, 250, 120), (1580, 1095, 160, 60), (1900, 940, 90, 140), (70, 1090, 200, 80)):
        bm = edge_noise(poly(blob_pts(cx0, cy0, rx_, ry_, rng, 0.3)), sc.noise(10, 2, key=101), 1.0)
        c, _ = rock_col(sc, bm, C("#040202"), C("#140a08"), C("#3a2218"), key=102, cell=rx_ * 0.5)
        near.paint(bm, c)
    near.light(gauss(1760, 950, 260, 40), C("#ff6a20"), 0.12)
    banner(near, glow, sc, rng, 1830, -60, 150, 330, key=15, light=0.3, rod=False)
    near.blur_all(4.0)

    # ---------------- rays and glow washes
    god_rays(rays, sc, (975, -160), [(70, 2.5, 0.12), (78, 3.5, 0.2), (86, 2.2, 0.16), (94, 3.0, 0.18), (102, 2.4, 0.12), (110, 2.0, 0.08)],
             C("#ffb060"), length=1150, start=260, dust=0.6, key=97)
    for wx, sill, hw_, spring in wins:
        a0 = 62 if wx < CX else 118
        god_rays(rays, sc, (wx, spring + 60), [(a0, 3.0, 0.1), (a0 + (5 if wx < CX else -5), 2.0, 0.07)],
                 C("#ff9a50"), length=650, start=70, dust=0.6, key=98 + int(wx) % 5)
    rays.add(gauss(960, 560, 380, 160), C("#ff8a3a"), 0.12)
    rays.add(gauss(940, 770, 520, 90), C("#ffa060"), 0.08)
    rays.add(full_mask(dens * sstep(560, 100, YY) * 0.25), C("#ff6a20"), 0.35)
    for _ in range(40):
        spark(glow, pick(rng, 200, 1720), pick(rng, 80, 640), pick(rng, 1.5, 3.2), C("#ffb050"), pick(rng, 0.3, 0.8), cross=False)

    fx = {
        "embers": [[820, 420, 300, 200], [1150, 420, 180, 260], [520, 520, 180, 160], [0, 80, 1920, 600]],
        "ash": [[0, -40, 1920, 1120]],
        "smoke": [[760, 0, 440, 560], [1150, 420, 160, 200], [520, 520, 160, 150]],
        "sparks": [[1180, 600, 80, 60], [560, 610, 90, 50]],
        "fires": [[905, 590], [1065, 585], [1290, 520], [1215, 650], [600, 660], [430, 668], [640, 26], [1360, 18]],
        "ground_y": GROUND_Y,
        "wind": [0.25, -1.0],
    }
    return far, mid, near, rays, glow, fx


# ============================================================== DRAGON LAIR

def lava(lay, glow, sc, m, key=0, k=1.0, sx=4.0, sy=0.6, hot=0.0, scale=34):
    """Molten rock: flowing bright channels between dark crust plates; colour + emission."""
    n1 = m.crop(sc.noise(scale, 4, key=key, sx=sx, sy=sy, gain=0.5))
    n2 = m.crop(sc.noise(scale * 0.3, 3, key=key + 1, sx=sx * 0.6, sy=sy))
    flow = n1 + n2 * 0.45
    t = 0.3 + sstep(0.5, -0.7, flow) * 0.6 + np.exp(-((flow - 0.42) / 0.07) ** 2) * 0.3 + hot
    t = np.clip(t + n2 * 0.04, 0, 1)
    lay.paint(m, ramp(t, LAVA_STOPS))
    glow.add(m.k(sstep(0.5, 1.0, t)), C("#ffb040"), 0.8 * k)
    glow.add(m.k(t), C("#ff4a10"), 0.15 * k)
    return t


def lava_fall(lay, glow, sc, x, top, bot, w0, w1, key=0, k=1.0):
    left, right = [], []
    for i in range(13):
        u = i / 12
        cx = x + math.sin(u * 2.4 + key) * w0 * 0.12
        ww = lerp(w0, w1, u ** 1.5) / 2
        yy = lerp(top, bot, u)
        left.append((cx - ww, yy))
        right.append((cx + ww, yy))
    m = poly(left + right[::-1], feather=1.0)
    st = m.crop(sc.noise(12, 3, key=key, sx=0.22, sy=7, gain=0.5))
    ww = np.interp(m.Y[:, 0], [p[1] for p in left], [(r[0] - l[0]) / 2 for l, r in zip(left, right)])[:, None]
    u = np.abs(m.X - x) / np.maximum(ww, 1)
    t = np.clip(0.95 - u ** 2 * 0.55 + st * 0.12 - sstep(0.6, 1.0, st) * 0.25, 0, 1)
    lay.paint(m, ramp(t, LAVA_STOPS))
    glow.add(m.k(sstep(0.55, 1.0, t)), C("#ffd070"), 1.0 * k)
    glow.add(m.k(t), C("#ff5a14"), 0.2 * k)
    glow.add(gauss(x, (top + bot) / 2, w1 * 1.2, (bot - top) * 0.55), C("#ff5a14"), 0.1 * k)
    return m


def coins(m, cell, key=0):
    """Pile-of-coins texture: overlapping jittered discs from three offset grids.
    Returns (coverage of the top disc, its top-left lit term)."""
    X, Y = m.X, m.Y
    best = np.zeros_like(X)
    hl = np.zeros_like(X)
    cy_ = cell * 0.6
    for g, (ox, oy) in enumerate(((0, 0), (0.5, 0.5), (0.27, 0.8))):
        gx = X / cell + ox
        gy = Y / cy_ + oy
        ix, iy = np.floor(gx), np.floor(gy)
        jx = hash2(ix, iy, key + g) * 0.4 - 0.2
        jy = hash2(iy, ix, key + g + 9) * 0.4 - 0.2
        dx = gx - ix - 0.5 - jx
        dy = gy - iy - 0.5 - jy
        d = np.sqrt(dx * dx + dy * dy)
        disc = sstep(0.46, 0.38, d)
        sh = np.clip(0.55 - dx * 1.2 - dy * 1.2, 0, 1) * disc + sstep(0.3, 0.4, d) * disc * 0.35
        newv = disc * (0.85 + 0.15 * hash2(ix, iy, key + g + 3))
        take = newv > best * 0.9
        best = np.where(take, newv, best)
        hl = np.where(take, sh, hl)
    return best, hl


def hoard(lay, glow, sc, rng, cx, base, rx, ry, cell=8, key=0, light=1.0, glints=24, rim=None):
    """Mound of gold coins with gems, lit from the upper left and from the lava (rim)."""
    lay.paint(ellipse(cx + rx * 0.05, base + 2, rx * 1.05, 12, feather=8), C("#080304"), 0.6 * lay.a[int(min(H - 1, base + 4)), int(min(W - 1, max(0, cx)))])
    m = edge_noise(poly(blob_pts(cx, base + ry * 0.05, rx, ry, rng, 0.08, n=48, flat_bottom=base)), sc.noise(5, 2, key=key), 0.6, s=1.2)
    X, Y = m.X, m.Y
    dx = (X - cx) / rx
    dy = np.minimum((Y - base) / ry, 0)
    bn = m.crop(sc.noise(28, 3, key=key + 1))
    nx, ny = dx * 1.2 + bn * 0.12, dy * 1.2 + bn * 0.08
    nz = np.sqrt(np.clip(1 - dx * dx - dy * dy, 0.03, 1))
    inv = 1 / np.sqrt(nx * nx + ny * ny + nz * nz)
    n = (nx * inv, ny * inv, nz * inv)
    lit = lambert(n)
    cov, hl = coins(m, cell, key=key)
    t = np.clip((lit * 1.1 - 0.05) * (0.5 + 0.5 * cov) + hl * 0.3 * lit, 0, 1)
    t = t * (0.55 + 0.45 * sstep(base + 4, base - ry * 0.4, Y))
    col = ramp(t, [(0, C("#2a1404")), (0.3, C("#7a4a0e")), (0.55, C("#c88a1e")), (0.78, C("#f2c24a")), (1, C("#fff2b0"))])
    col = col * (1 - (1 - cov) * 0.45)[..., None]
    lay.paint(m, col * light)
    if rim is not None:
        lay.light(m.k(np.clip(n[2] - 0.2, 0, 1) * sstep(base - ry * 0.5, base, Y) * cov), rim, 0.3)
    glow.add(m.k(sstep(0.82, 1.0, t) * cov), C("#ffe08a"), 0.35 * light)
    # gems
    for i in range(int(rx * ry / 2500)):
        a = pick(rng, 0.15, 0.85) * math.pi
        rr = pick(rng, 0.1, 0.9)
        gx_, gy_ = cx + math.cos(a) * rx * rr, base - math.sin(a) * ry * rr * 0.95
        gs = pick(rng, 4, 8) * cell / 8
        gc = [C("#e0203a"), C("#20c060"), C("#3a70ff"), C("#b040ff")][int(rng.integers(0, 4))]
        gm = poly([(gx_, gy_ - gs), (gx_ + gs * 0.8, gy_), (gx_, gy_ + gs * 0.7), (gx_ - gs * 0.8, gy_)])
        lay.paint(gm, ramp(np.clip(0.6 - (gm.X - gx_ + gm.Y - gy_) / (gs * 1.5), 0, 1), [(0, gc * 0.3), (0.6, gc), (1, lerp(gc, C("#ffffff"), 0.7))]) * light)
        glow.add(gauss(gx_ - gs * 0.2, gy_ - gs * 0.3, gs * 0.35), lerp(gc, C("#ffffff"), 0.5), 0.6 * light)
    for _ in range(glints):
        a = pick(rng, 0.2, 0.8) * math.pi
        rr = pick(rng, 0.2, 0.85)
        spark(glow, cx + math.cos(a) * rx * rr, base - math.sin(a) * ry * rr * 0.9, pick(rng, 1.5, 3.2) * cell / 8,
              C("#ffe8a0"), pick(rng, 0.4, 0.9) * light, cross=rng.random() < 0.4)
    return m


def dragon_skull(lay, glow, sc, x, y, s, key=0, light=1.0):
    """Huge horned dragon skull in profile facing right; bone shading, dark sockets, teeth."""
    def T(pts):
        return [(x + px * s, y + py * s) for px, py in pts]
    bone_d, bone_m, bone_l = C("#1c100a"), C("#6e5440"), C("#dcbc92")
    # horns (behind)
    for pts, w0 in (([(30, -50), (-40, -120), (-140, -160), (-230, -150), (-290, -110)], 34),
                    ([(70, -62), (20, -150), (-50, -215), (-130, -240)], 24)):
        m = stroke(T(pts), 10 * s, taper=(w0 * s, 4 * s))
        t = np.clip(0.6 - (m.Y - y) / (300 * s) * 0.0 + m.crop(sc.noise(10, 2, key=key + 1)) * 0.1, 0, 1)
        lay.paint(m, ramp(t, [(0, bone_d), (0.6, bone_m * 0.8), (1, bone_l * 0.8)]) * light)
        rid = np.abs(np.sin((m.X + m.Y) / (6 * s)))
        lay.mult(m.k((1 - sstep(0, 0.3, rid)) * 0.18), bone_d)
    skull_pts = [(0, -40), (30, -70), (80, -80), (130, -66), (170, -46), (240, -38), (310, -30), (345, -20), (355, -4),
                 (342, 10), (250, 14), (170, 20), (110, 32), (60, 42), (20, 36), (-12, 10)]
    jaw_pts = [(80, 40), (170, 26), (250, 22), (325, 20), (334, 30), (300, 42), (200, 56), (120, 66), (70, 62)]
    occ = polys([T(jaw_pts), T(skull_pts)])
    glow.L[occ.sl] *= (1 - occ.a)[..., None]
    for pts in (jaw_pts, skull_pts):
        m = poly(T(pts))
        col, n = rock_col(sc, m, bone_d, bone_m, bone_l, cell=40 * s, nscale=20 * s, key=key + 3, crack=0.25, tilt=0.15)
        lay.paint(m, col * light)
    # sockets and openings
    for ex, ey, rx, ry in ((125, -30, 28, 19), (52, -18, 20, 26), (330, -12, 9, 6), (210, -10, 40, 9)):
        om = ellipse(x + ex * s, y + ey * s, rx * s, ry * s, feather=1.5)
        lay.paint(om, C("#0e0604"))
        lay.paint(Mask(om.a * (1 - sstep(-0.2, 0.6, (om.Y - (y + ey * s)) / (ry * s))) * 0.0, om.x0, om.y0), bone_d)
    glow.add(gauss(x + 125 * s, y - 24 * s, 7 * s, 4 * s), C("#ff6a20"), 0.25 * light)
    # teeth
    tp = []
    for i in range(10):
        tx = 175 + i * 16
        tl = 18 if i % 3 == 0 else 11
        tp.append([(tx - 5, 14 - i * 0.4), (tx + 5, 14 - i * 0.4), (tx + 1, 14 + tl)])
        tp.append([(tx + 3, 26 - i * 0.4), (tx + 12, 26 - i * 0.4), (tx + 8, 26 - tl * 0.8)])
    m = polys([T(p) for p in tp], feather=0.6)
    lay.paint(m, ramp(np.clip((m.Y - y) / (40 * s) + 0.5, 0, 1), [(0, bone_l), (1, bone_m)]) * light)
    # brow spikes
    for bx_, by_, bh in ((100, -78, 34), (140, -64, 26), (175, -48, 18)):
        lay.paint(poly(T([(bx_ - 12, by_ + 6), (bx_ - 18, by_ - bh), (bx_ + 10, by_ + 4)])), bone_m * 0.8 * light)


def ribcage(lay, sc, rng, x0, y0, x1, y1, n, ground, light=1.0):
    """Spine arching from (x0, y0) up to (x1, y1) with ribs curving down to the ground."""
    bone_d, bone_m, bone_l = C("#1a0e08"), C("#5e4434"), C("#c8a47c")
    spine = []
    for i in range(25):
        u = i / 24
        spine.append((lerp(x0, x1, u), lerp(y0, y1, u) - math.sin(u * math.pi) * 60))
    for i in range(n):
        u = 0.12 + 0.8 * i / (n - 1)
        sx, sy = spine[int(u * 24)]
        L = ground - sy
        pts = []
        for j in range(12):
            v = j / 11
            pts.append((sx - 70 * math.sin(v * math.pi * 0.9) - v * 30 + 40 * v * v, sy + L * v * (0.98 + 0.02 * u)))
        m = stroke(pts, 18, taper=(30 * (1.1 - u * 0.4), 9))
        t = np.clip(0.8 - (m.X - sx + 70) / 90, 0, 1)
        lay.paint(m, ramp(t, [(0, bone_d), (0.5, bone_m), (1, bone_l)]) * light)
    m = stroke(spine, 16, taper=(30, 14))
    lay.paint(m, ramp(np.clip(0.6 - (m.Y - m.Y.min()) / 40, 0, 1), [(0, bone_d), (0.5, bone_m), (1, bone_l)]) * light)
    for i in range(0, 25, 2):
        vx, vy = spine[i]
        lay.paint(poly([(vx - 6, vy - 6), (vx - 14, vy - 34), (vx + 4, vy - 4)]), bone_m * 0.75 * light)


def dragon_lair(seed=53):
    rng = np.random.default_rng(seed)
    sc = Noise(seed)
    far, mid, near, rays, glow = Layer(), Layer(), Layer(), Light(), Light()
    fall = (1190, 30)
    haze = C("#3a0e08")
    basalt = (C("#08040a"), C("#241418"), C("#5a3a34"))

    # ---------------- far: cavern depths, distant walls, the great lava fall, lake
    far.paint(full_mask(), vgrad([(0, C("#070205")), (0.3, C("#140508")), (0.5, C("#2e0c0a")), (0.57, C("#5a1a0a")),
                                  (0.62, C("#3a1008")), (1, C("#0e0303"))], 0, H))
    far.light(gauss(fall[0], 420, 420, 300), C("#ff5a1a"), 0.18)
    for i, (y0, amp, col, hkk) in enumerate(((380, 160, C("#2a1214"), 0.45), (470, 120, C("#1e0c10"), 0.3), (540, 80, C("#140709"), 0.15))):
        rp = ridge(rng, -40, 1960, y0, amp, rough=0.6,
                   peaks=[(pick(rng, 150, 550), y0 - amp * 1.6, 160), (pick(rng, 1500, 1800), y0 - amp * 1.5, 190)])
        m = poly([(-40, 680)] + rp + [(1960, 680)])
        c, n = rock_col(sc, m, col * 0.4, col, lerp(col, C("#c86a48"), 0.35), key=800 + i, cell=90 - i * 15, sy=2.2, bulge=60)
        far.paint(m, c)
        # rim of lava light on the ridges facing the fall
        far.light(m.k(np.exp(-((m.X - fall[0]) / 600) ** 2) * sstep(0.0, 0.5, n[0]) * 0.8), C("#ff7a30"), 0.25)
        far.haze(m, haze, hkk)
        if i == 0:
            rp0 = rp
        if i == 1:
            # thin side falls spilling from the first ledge, behind the nearer one
            for lx, w0, w1, kk, ky in ((560, 16, 34, 0.5, 810), (1660, 12, 26, 0.4, 811)):
                ly = float(np.interp(lx, [p[0] for p in rp0], [p[1] for p in rp0])) + 12
                lava_fall(far, glow, sc, lx, ly, 612, w0, w1, key=ky, k=kk)
                far.light(gauss(lx, ly, 40, 14), C("#ff8a3a"), 0.4)
    # the vault ceiling with stalactites, open crack above the fall
    ceil = poly([(-20, -20), (1940, -20), (1940, 140)] + [(x, 110 + 55 * math.sin(x / 210) + 25 * math.sin(x / 61)) for x in range(1920, -21, -40)])
    c, n = rock_col(sc, ceil, C("#040204"), C("#1a0c0e"), C("#4a2a26"), key=820, cell=80, bulge=40)
    far.paint(ceil, c)
    far.light(ceil.k(gauss(fall[0], 120, 360, 90).full()[ceil.sl]), C("#ff6a20"), 0.45)
    for i in range(28):
        sx0 = pick(rng, 0, 1920)
        if abs(sx0 - fall[0]) < 110:
            continue
        stalactite(far, sc, sx0, 80 + 50 * math.sin(sx0 / 210), pick(rng, 60, 220), pick(rng, 20, 56),
                   C("#060204"), C("#1e0c0e"), C("#5a2c22"), key=i + 30)
    # cleft and the great lava fall
    far.paint(poly([(fall[0] - 70, -10), (fall[0] + 80, -10), (fall[0] + 40, 120), (fall[0] - 30, 130)], feather=3), C("#2a0804"))
    lava_fall(far, glow, sc, fall[0], 20, 612, 96, 190, key=830, k=1.0)
    # lava lake at the foot of the fall
    lake = poly(blob_pts(1080, 618, 600, 26, rng, 0.08, n=48), feather=2)
    lava(far, glow, sc, lake, key=840, k=0.5, sx=6.0, sy=0.5, hot=0.0, scale=40)
    # steam and heat haze at the foot of the fall
    st = np.clip(sc.noise(70, 4, key=845, sx=1.6, sy=0.8) * 0.5 + 0.5, 0, 1)
    far.paint(full_mask(st * gauss(fall[0], 560, 260, 70).full() * 0.7), C("#ff9a60"))
    far.haze(full_mask(sstep(480, 600, YY) * (1 - sstep(600, 680, YY)) * 0.35), C("#a03a14"))

    # ---------------- mid: lava river, ground, cave walls, hoards, bones
    # river behind the fighting ground
    top_b = [(x, 646 + 8 * math.sin(x / 170 + 1) + 5 * math.sin(x / 53)) for x in range(-40, 1961, 40)]
    bot_b = [(x, 694 + 10 * math.sin(x / 210) + 6 * math.sin(x / 47 + 2)) for x in range(1960, -41, -40)]
    rv = poly(top_b + bot_b, feather=1.0)
    lava(mid, glow, sc, rv, key=850, k=1.0, sx=7.0, sy=0.4, hot=0.08, scale=36)
    # bank in the distance behind the river (dark rock shelf the lake light skims)
    bank = edge_noise(poly([(-40, 640)] + [(x, y - 4 + 6 * math.sin(x / 90)) for x, y in top_b] + [(1960, 640), (1960, 628), (-40, 628)]), sc.noise(8, 2, key=851), 1.0)
    # ground
    gl = [(x, y - 6) for x, y in bot_b[::-1]]
    fl = poly(gl + [(1960, H), (-40, H)])
    X, Y = fl.X, fl.Y
    dz = np.clip((Y - 680) / 400, 0, 1)
    hgt = fl.crop(sc.noise(130, 4, key=860, sx=3.0, gain=0.5)) * (3 + dz * 15) + fl.crop(sc.noise(22, 3, key=861, sx=2.5)) * (0.6 + dz * 3)
    gyh, gxh = np.gradient(hgt)
    HZ = 560.0
    Zg = FOCAL / np.maximum(Y - HZ, 1.0)
    ug = (X - 960) * Zg / FOCAL / 0.55 + fl.crop(sc.noise(60, 2, key=865)) * 0.08
    vg = Zg / 0.42
    d1, d2, rid = cells(ug, vg, key=866)
    fpx = Zg / FOCAL / 0.55 * 1.5                     # cell units per pixel
    edge = 1 - sstep(0.02, 0.06 + fpx, d2 - d1)
    tilt = (hash2(rid * 97.0, 1.0) - 0.5) * 0.5
    lit = np.clip(0.42 - gyh * 0.5 + gxh * 0.15 + tilt * 0.6 + (rid - 0.5) * 0.25, 0, 1)
    lit = lit * (1 - edge * 0.75)
    col = ramp(lit, [(0, C("#060204")), (0.4, C("#1a0c0c")), (0.7, C("#342016")), (1, C("#5a3828"))])
    ashf = sstep(0.2, 1.0, fl.crop(sc.noise(70, 3, key=862, sx=2.4)))
    col = lerp(col, ramp(lit, [(0, C("#2a201e")), (1, C("#6a5a52"))]), (ashf * 0.4)[..., None])
    mid.paint(fl, col)
    # lip of the bank: hot, bright edge where the rock meets the lava
    lip = Mask(fl.a * np.exp(-np.clip(Y - (np.interp(X[0], [p[0] for p in gl], [p[1] for p in gl]))[None, :], 0, 200) / 14.0), fl.x0, fl.y0)
    mid.light(lip, C("#ff7a30"), 0.5)
    # glowing cracks except where the fighters stand
    cr = np.maximum(ember_cracks(fl, sc, 863, thick=0.99), edge * sstep(0.75, 1.0, rid) * 0.8)
    cr = cr * sstep(700, 740, Y) * sstep(0.2, 1.0, fl.crop(sc.noise(160, 3, key=864)))
    cr = cr * (1 - np.exp(-((X - 920) / 560) ** 2) * np.exp(-((Y - 775) / 80) ** 2))
    mid.paint(Mask(cr * fl.a, fl.x0, fl.y0), C("#ff9a3a"), 0.9)
    glow.add(Mask(cr * fl.a, fl.x0, fl.y0), C("#ff8a2a"), 0.8)
    glow.add(Mask(blur(cr, 5) * fl.a, fl.x0, fl.y0), C("#ff4a10"), 0.7)
    # warm light from the river, darkness toward the viewer
    mid.light(gauss(940, 715, 900, 60), C("#ff7a30"), 0.3)
    mid.light(gauss(920, 775, 560, 90), C("#ffa060"), 0.16)
    mid.mult(full_mask(sstep(830, 1080, YY) * 0.7), C("#080304"))
    mid.paint(bank, ramp(np.clip((bank.Y - 628) / 20, 0, 1), [(0, C("#0c0406")), (1, C("#3a1810"))]))

    # cave walls left and right, rim-lit by lava
    for sgn in (-1, 1):
        xe = 0 if sgn < 0 else W
        pts = [(xe, -20)]
        for i in range(12):
            u = i / 11
            yy = -20 + u * 760
            xx = xe - sgn * (150 + 80 * math.sin(u * 5 + sgn * 2) + 40 * pick(rng, -1, 1) + 40 * u)
            pts.append((xx, yy))
        pts.append((xe, 760))
        m = edge_noise(poly(pts), sc.noise(14, 3, key=870 + sgn), 0.7, sharp=4.0)
        c, n = rock_col(sc, m, basalt[0], basalt[1], basalt[2], key=871 + sgn, cell=60, sy=2.6, bulge=70, tilt=0.3)
        mid.paint(m, c)
        mid.light(m.k(np.clip(n[0] * sgn * -1, 0, 1) * sstep(200, 700, m.Y)), C("#ff6a24"), 0.5)
    # stalagmites
    for sx0, sb, sl_, sw_ in ((560, 652, 120, 30), (1360, 650, 150, 34), (840, 642, 60, 16)):
        stalactite(mid, sc, sx0, sb, sl_, sw_, C("#06020a"), C("#2a1416"), C("#7a4030"), key=sx0, up=True)

    # bones: ribcage (right, behind the hoard) and the skull on the left hoard
    ribcage(mid, sc, rng, 1380, 640, 1980, 330, 8, 702, light=0.85)
    mid.light(gauss(1650, 600, 300, 160), C("#ff7a30"), 0.18)
    hoard(mid, glow, sc, rng, 1700, 712, 320, 120, cell=9, key=880, rim=C("#ff7a30"))
    hoard(mid, glow, sc, rng, 1430, 710, 120, 62, cell=7, key=881, rim=C("#ff7a30"), glints=8)
    hoard(mid, glow, sc, rng, 220, 712, 340, 150, cell=9, key=882, rim=C("#ff7a30"))
    hoard(mid, glow, sc, rng, 560, 710, 110, 58, cell=7, key=883, rim=C("#ff7a30"), glints=8)
    dragon_skull(mid, glow, sc, 110, 585, 1.08, key=890)
    mid.light(gauss(330, 600, 200, 60), C("#ff8a40"), 0.12)
    # spilled coins at the edges of the ground
    for _ in range(46):
        side = rng.random() < 0.5
        cx_ = pick(rng, 0, 660) if side else pick(rng, 1300, 1920)
        cy_ = 708 + abs(rng.normal(0, 18))
        r = 3.0 + (cy_ - 700) / 200 * 3
        cm = ellipse(cx_, cy_, r, r * 0.55)
        mid.paint(cm, ramp(np.clip(0.7 - (cm.X - cx_) / r * 0.4 - (cm.Y - cy_) / r, 0, 1), [(0, C("#6a3a08")), (0.6, C("#d8a030")), (1, C("#fff0a0"))]))
    # a sword stuck in the left hoard, a goblet on the right one
    mid.paint(poly([(468, 520), (478, 520), (481, 612), (465, 612)]), ramp(np.clip(np.arange(1) + 0, 0, 1), [(0, C("#b8b8c0")), (1, C("#b8b8c0"))]))
    blade = poly([(466, 540), (480, 540), (478, 640), (472, 662), (466, 640)])
    mid.paint(blade, ramp(np.clip((blade.X - 466) / 14, 0, 1), [(0, C("#e8eef8")), (0.5, C("#8a909c")), (1, C("#3a3c44"))]))
    mid.paint(stroke([(450, 538), (496, 538)], 7), C("#b08a30"))
    mid.paint(stroke([(473, 500), (473, 534)], 7), C("#3a2014"))
    mid.paint(ellipse(473, 496, 7, 7), C("#e0b040"))
    glow.add(gauss(470, 600, 3, 40), C("#ffe0c0"), 0.4)
    gob = poly([(1580, 560), (1612, 560), (1604, 584), (1598, 590), (1600, 604), (1612, 610), (1580, 610), (1592, 604), (1594, 590), (1588, 584)])
    mid.paint(gob, ramp(np.clip(0.8 - (gob.X - 1580) / 34, 0, 1), [(0, C("#5a3608")), (0.6, C("#d8a030")), (1, C("#fff0a0"))]))
    spark(glow, 1590, 566, 4, C("#ffe8a0"), 0.8)

    # ---------------- near: dark rocks and stalactites, lava-rimmed
    for (cx0, cy0, rx_, ry_) in ((60, 1040, 300, 150), (1860, 1030, 280, 170), (330, 1095, 190, 60), (1610, 1095, 210, 60)):
        bm = edge_noise(poly(blob_pts(cx0, cy0, rx_, ry_, rng, 0.28)), sc.noise(10, 2, key=900), 1.0)
        c, n = rock_col(sc, bm, C("#030103"), C("#0e0608"), C("#2a1410"), key=901, cell=rx_ * 0.45)
        near.paint(bm, c)
        near.light(bm.k(np.clip(-n[1], 0, 1) * np.exp(-((bm.Y - (cy0 - ry_)) / 25) ** 2)), C("#ff5a1a"), 0.18)
    for x0, ln, w_ in ((40, 260, 120), (190, 150, 70), (1850, 300, 130), (1700, 140, 60)):
        stalactite(near, sc, x0, -20, ln, w_, C("#030103"), C("#120608"), C("#3a1a14"), key=x0)
    near.blur_all(4.0)

    # ---------------- rays and glow washes
    rays.add(gauss(fall[0], 340, 200, 340), C("#ff6a20"), 0.12)
    rays.add(gauss(fall[0], 600, 420, 70), C("#ff8a3a"), 0.12)
    rays.add(gauss(940, 680, 900, 40), C("#ff7a30"), 0.12)
    rays.add(gauss(940, 770, 600, 90), C("#ffa060"), 0.05)
    # rising heat columns
    hc = np.clip(sc.noise(160, 3, key=910, sx=0.5, sy=2.0) * 0.5 + 0.3, 0, 1) * sstep(700, 250, YY) * sstep(0, 300, YY)
    rays.add(full_mask(hc * (gauss(fall[0], 400, 420, 380).full() + gauss(560, 450, 360, 280).full() * 0.6)), C("#ff5a1a"), 0.12)
    for _ in range(30):
        spark(glow, pick(rng, 100, 1820), pick(rng, 120, 640), pick(rng, 1.5, 3.0), C("#ff9a40"), pick(rng, 0.3, 0.7), cross=False)

    fx = {
        "embers": [[0, 600, 1920, 110], [fall[0] - 140, 480, 280, 160], [0, 100, 1920, 600]],
        "ash": [[0, -40, 1920, 1120]],
        "sparks": [[fall[0] - 120, 560, 240, 70], [460, 560, 200, 50]],
        "smoke": [[fall[0] - 200, 470, 400, 160], [0, 600, 1920, 80]],
        "bubbles": [[0, 655, 1920, 30], [400, 600, 1300, 25]],
        "lava_fall": [fall[0] - 60, 20, 120, 590],
        "glints": [[0, 560, 560, 150], [1380, 580, 540, 130]],
        "ground_y": GROUND_Y,
        "wind": [0.0, -1.0],
    }
    return far, mid, near, rays, glow, fx


SCENES = {
    "rotten_cellar": rotten_cellar,
    "mushroom_cave": mushroom_cave,
    "frozen_pass": frozen_pass,
    "burnt_keep": burnt_keep,
    "dragon_lair": dragon_lair,
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

"""Kıvılcımköy, landscape edition (M8 style): the painted town scene and the six NPC busts.

    python3 tools/art/town_v2.py            # everything
    python3 tools/art/town_v2.py town       # the town layers, hotspots, fx and the preview
    python3 tools/art/town_v2.py npcs       # the six portraits (or: npcs nara smith ...)

Town (1920 x 1080, drawn at 2x and downsampled) goes to assets/town/v2/:

    far.png     opaque golden-hour sky, clouds and the distant mountains
    town.png    the village on its hillside with the Dungeon Gate in the cliff (sky transparent)
    near.png    foreground framing foliage at the edges (transparent elsewhere)
    rays.png    sun rays, meant to be drawn with additive blending
    glow.png    windows, torches, lanterns and the forge, additive and pulsed by the game
    hotspots.json  tap rects and name-plate anchors of the gate and the four buildings
    fx.json        particle emitters (chimney smoke, forge sparks, falling leaves, birds)

and a flattened preview to assets/town/v2.jpg. The game keeps a HUD over y < 110 and a button bar
over y > 930, so every building sits between the two.

NPCs are 768 x 768 transparent busts in the semi-realistic anime style (3/4 view facing right,
warm key light from the upper left, cool fill and a soft rim light), written over
assets/town/npc_<id>.png.

Everything is painted from code with numpy: shapes are local masks (only their bounding box is
touched), shaded from a blurred height field of the mask (so any silhouette gets soft volume),
broken up with coherent value noise, and composited premultiplied.
"""
import json
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "assets", "town", "v2")
SCRATCH = "/tmp/claude-0/-home-claude-valthera-dragon-s-edge/9d7e6e94-5ed4-51a7-95df-cdb7958efe3b/scratchpad/m8"

W, H = 1920, 1080
LIGHT = np.array([-0.62, -0.62, 0.48], np.float32)
LIGHT /= np.linalg.norm(LIGHT)


# =================================================================== colour

def C(h, *more):
    """Hex colour to a float RGB triple (0..1)."""
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def lerp(a, b, t):
    """Blend colours (triples or HxWx3 fields) by a scalar or an HxW weight."""
    if isinstance(t, np.ndarray) and t.ndim >= 1:
        rgb = (np.ndim(a) >= 1 and np.shape(a)[-1] == 3) or (np.ndim(b) >= 1 and np.shape(b)[-1] == 3)
        if rgb and t.shape[-1] not in (1, 3):
            t = t[..., None]
    return a + (b - a) * t


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# =================================================================== blur / noise

def box1(a, r, axis):
    if r < 1:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    cs = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float32)
    hi = np.take(cs, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(cs, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def gblur(a, sigma):
    """Gaussian-ish blur (three box passes) of a float array (2D or HxWxC)."""
    if sigma < 0.4:
        return a
    w = math.sqrt(12 * sigma * sigma / 3 + 1)
    r = max(1, int(round((w - 1) / 2)))
    out = a.astype(np.float32)
    for _ in range(3):
        out = box1(out, r, 0)
        out = box1(out, r, 1)
    return out


def pil_blur(a, sigma):
    """Fast blur for masks via Pillow (8-bit precision, fine for alpha)."""
    if sigma < 0.4:
        return a
    im = Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(sigma)), np.float32) / 255.0


def value_noise(h, w, cell, rng):
    sh, sw = int(h / cell) + 3, int(w / cell) + 3
    small = Image.fromarray(rng.random((sh, sw)).astype(np.float32), "F")
    big = small.resize((int(sw * cell), int(sh * cell)), Image.BICUBIC)
    a = np.asarray(big, np.float32)
    o = int(cell)
    return a[o:o + h, o:o + w]


def fbm(h, w, cell, octaves, seed, gain=0.5):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        if cell < 1.2:
            break
        out += value_noise(h, w, cell, rng) * amp
        tot += amp
        amp *= gain
        cell /= 2.0
    return out / tot


# =================================================================== masks

class Mask:
    """A local alpha mask: float array `a` whose top-left sits at canvas pixel (x, y)."""
    __slots__ = ("a", "x", "y", "cv")

    def __init__(self, cv, a, x, y):
        self.cv, self.a, self.x, self.y = cv, a, int(x), int(y)

    @property
    def box(self):
        return (self.x, self.y, self.x + self.a.shape[1], self.y + self.a.shape[0])

    def at(self, box):
        """This mask resampled into another box (zero outside)."""
        x0, y0, x1, y1 = box
        out = np.zeros((y1 - y0, x1 - x0), np.float32)
        sx0, sy0, sx1, sy1 = self.box
        ix0, iy0, ix1, iy1 = max(x0, sx0), max(y0, sy0), min(x1, sx1), min(y1, sy1)
        if ix1 > ix0 and iy1 > iy0:
            out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] = self.a[iy0 - sy0:iy1 - sy0, ix0 - sx0:ix1 - sx0]
        return out

    def copy(self, a=None):
        return Mask(self.cv, self.a.copy() if a is None else a, self.x, self.y)

    def __or__(self, o):
        if o is None:
            return self
        b0, b1 = self.box, o.box
        box = (min(b0[0], b1[0]), min(b0[1], b1[1]), max(b0[2], b1[2]), max(b0[3], b1[3]))
        return Mask(self.cv, np.maximum(self.at(box), o.at(box)), box[0], box[1])

    def __and__(self, o):
        return self.copy(self.a * o.at(self.box))

    def __sub__(self, o):
        return self.copy(self.a * (1 - o.at(self.box)))

    def __mul__(self, k):
        return self.copy(self.a * k)

    def grow(self, pad):
        pad = int(pad)
        return Mask(self.cv, np.pad(self.a, pad), self.x - pad, self.y - pad)

    def blur(self, r, precise=False):
        """Blur by r final-image pixels (the mask grows to hold the spread)."""
        s = r * self.cv.ss
        g = self.grow(s * 2.2 + 2)
        g.a = gblur(g.a, s) if precise else pil_blur(g.a, s)
        return g

    def shift(self, dx, dy):
        return Mask(self.cv, self.a, self.x + int(dx * self.cv.ss), self.y + int(dy * self.cv.ss))

    def grid(self):
        """Final-image coordinates (X, Y) of this mask's pixels."""
        s = self.cv.ss
        ys = (np.arange(self.a.shape[0], dtype=np.float32) + self.y + 0.5) / s
        xs = (np.arange(self.a.shape[1], dtype=np.float32) + self.x + 0.5) / s
        return np.meshgrid(xs, ys)

    def bbox_final(self):
        ys, xs = np.nonzero(self.a > 0.02)
        if len(xs) == 0:
            return None
        s = self.cv.ss
        return ((xs.min() + self.x) / s, (ys.min() + self.y) / s, (xs.max() + self.x) / s, (ys.max() + self.y) / s)

    def noise(self, kind="m"):
        return self.cv.noise(kind, self.box)

    def edge(self, width):
        """Inner band of the given width along the silhouette (soft)."""
        b = self.blur(width * 0.6)
        inner = np.clip((b.at(self.box) - 0.5) * 2.2, 0, 1)
        return self.copy(np.clip(self.a - inner, 0, 1))

    def lambert(self, r, light=None, flat=1.0, precise=True):
        """Soft volume: Lambert term (-1..1) of the height field blur(mask, r)."""
        s = self.cv.ss
        pad = int(r * s * 2.2) + 2
        g = np.pad(self.a, pad)
        hf = gblur(g, r * s) if precise else pil_blur(g, r * s)
        gy, gx = np.gradient(hf)
        k = r * s * 1.6 / max(flat, 1e-3)
        nx, ny = -gx * k, -gy * k
        nz = np.ones_like(nx)
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        L = LIGHT if light is None else light
        d = (nx * L[0] + ny * L[1] + nz * L[2]) * inv
        return d[pad:-pad, pad:-pad]


# =================================================================== canvas

class Canvas:
    """Premultiplied float RGBA canvas; coordinates in final pixels, stored at ss x."""

    def __init__(self, w, h, ss=2, seed=1):
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.px = np.zeros((self.H, self.W, 4), np.float32)
        self.seed = seed
        self._noise = {}

    # ---------------------------------------------------------- noise fields
    def noise(self, kind, box):
        if kind not in self._noise:
            s = self.ss
            spec = {"f": (2.5 * s, 3), "m": (14 * s, 4), "c": (60 * s, 4), "g": (1.0 * s, 1),
                    "s": (6 * s, 3)}[kind]
            if kind == "g":
                rng = np.random.default_rng(self.seed + 7)
                self._noise[kind] = rng.random((self.H, self.W), dtype=np.float32)
            else:
                self._noise[kind] = fbm(self.H, self.W, spec[0], spec[1], self.seed + ord(kind))
        x0, y0, x1, y1 = box
        n = self._noise[kind]
        out = np.full((y1 - y0, x1 - x0), 0.5, np.float32)
        ix0, iy0, ix1, iy1 = max(0, x0), max(0, y0), min(self.W, x1), min(self.H, y1)
        if ix1 > ix0 and iy1 > iy0:
            out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] = n[iy0:iy1, ix0:ix1]
        return out

    # ---------------------------------------------------------- mask makers
    def _draw(self, bbox, fn, blur=0.0, pad=2):
        s = self.ss
        x0 = int(math.floor(bbox[0] * s)) - pad
        y0 = int(math.floor(bbox[1] * s)) - pad
        x1 = int(math.ceil(bbox[2] * s)) + pad
        y1 = int(math.ceil(bbox[3] * s)) + pad
        im = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 0)
        fn(ImageDraw.Draw(im), lambda px, py: ((px * s - x0), (py * s - y0)))
        m = Mask(self, np.asarray(im, np.float32) / 255.0, x0, y0)
        return m.blur(blur) if blur else m

    def poly(self, pts, blur=0.0):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return self._draw((min(xs), min(ys), max(xs), max(ys)),
                          lambda d, T: d.polygon([T(x, y) for x, y in pts], fill=255), blur)

    def ellipse(self, cx, cy, rx, ry, blur=0.0):
        return self._draw((cx - rx, cy - ry, cx + rx, cy + ry),
                          lambda d, T: d.ellipse(T(cx - rx, cy - ry) + T(cx + rx, cy + ry), fill=255), blur)

    def rect(self, x0, y0, x1, y1, blur=0.0, radius=0):
        s = self.ss
        return self._draw((x0, y0, x1, y1), lambda d, T: d.rounded_rectangle(
            T(x0, y0) + T(x1, y1), radius=radius * s, fill=255), blur)

    def line(self, pts, width, blur=0.0):
        pad = width
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        s = self.ss

        def fn(d, T):
            P = [T(x, y) for x, y in pts]
            d.line(P, fill=255, width=max(1, int(round(width * s))), joint="curve")
            r = width * s / 2
            for (x, y) in (P[0], P[-1]):
                d.ellipse((x - r, y - r, x + r, y + r), fill=255)

        return self._draw((min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad), fn, blur)

    def taper(self, pts, w0, w1, blur=0.0, wm=None):
        """A stroke whose width goes w0 -> (wm) -> w1 along the polyline (drawn as a polygon)."""
        pts = [np.array(p, np.float32) for p in pts]
        n = len(pts)
        left, right = [], []
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]
            b = pts[min(n - 1, i + 1)]
            d = b - a
            ln = float(np.hypot(*d)) or 1.0
            nx, ny = -d[1] / ln, d[0] / ln
            t = i / max(1, n - 1)
            if wm is None:
                w = w0 + (w1 - w0) * t
            else:
                w = (w0 + (wm - w0) * t * 2) if t < 0.5 else (wm + (w1 - wm) * (t - 0.5) * 2)
            left.append((p[0] + nx * w / 2, p[1] + ny * w / 2))
            right.append((p[0] - nx * w / 2, p[1] - ny * w / 2))
        return self.poly(left + right[::-1], blur)

    def custom(self, bbox, fn, blur=0.0):
        """fn(draw, T) where T maps final coords to mask coords (T(x, y) -> (mx, my))."""
        return self._draw(bbox, fn, blur)

    def dabs(self, items, blur=0.0):
        """Union of many ellipses: items = [(cx, cy, rx, ry)] (a leafy clump, a cloud...)."""
        xs0 = min(c - rx for c, _, rx, _ in items)
        ys0 = min(c - ry for _, c, _, ry in items)
        xs1 = max(c + rx for c, _, rx, _ in items)
        ys1 = max(c + ry for _, c, _, ry in items)

        def fn(d, T):
            for cx, cy, rx, ry in items:
                d.ellipse(T(cx - rx, cy - ry) + T(cx + rx, cy + ry), fill=255)

        return self._draw((xs0, ys0, xs1, ys1), fn, blur)

    def full(self):
        return Mask(self, np.ones((self.H, self.W), np.float32), 0, 0)

    # ---------------------------------------------------------- painting
    def _region(self, m):
        x0, y0, x1, y1 = m.box
        ix0, iy0, ix1, iy1 = max(0, x0), max(0, y0), min(self.W, x1), min(self.H, y1)
        if ix1 <= ix0 or iy1 <= iy0:
            return None
        return (ix0, iy0, ix1, iy1), (slice(iy0 - y0, iy1 - y0), slice(ix0 - x0, ix1 - x0))

    def fill(self, m, col, alpha=1.0, mode="over"):
        """Paints colour `col` (RGB triple or a field shaped like the mask) through mask m.

        modes: over, atop (keeps the canvas alpha; only paints on what is there), add (light),
        behind (only where the canvas is still transparent), erase."""
        r = self._region(m)
        if r is None:
            return
        (x0, y0, x1, y1), (sy, sx) = r
        a = m.a[sy, sx]
        if isinstance(alpha, np.ndarray):
            a = a * alpha[sy, sx]
        elif alpha != 1.0:
            a = a * alpha
        dst = self.px[y0:y1, x0:x1]
        col = np.asarray(col, np.float32)
        if col.ndim == 3:
            col = col[sy, sx]
        if mode == "over":
            dst[..., :3] = col * a[..., None] + dst[..., :3] * (1 - a[..., None])
            dst[..., 3] = a + dst[..., 3] * (1 - a)
        elif mode == "atop":
            a = a * dst[..., 3]
            dst[..., :3] = col * a[..., None] + dst[..., :3] * (1 - a[..., None])
        elif mode == "add":  # light onto what is painted (premultiplied, so scaled by coverage)
            dst[..., :3] += col * a[..., None] * dst[..., 3:4]
        elif mode == "addfree":  # additive light that also creates coverage (for glow layers)
            dst[..., :3] += col * a[..., None]
            dst[..., 3] = np.maximum(dst[..., 3], np.clip(a * col.max(axis=-1) if col.ndim == 3 else a * col.max(), 0, 1))
        elif mode == "behind":
            da = dst[..., 3]
            k = a * (1 - da)
            dst[..., :3] += col * k[..., None]
            dst[..., 3] = da + k
        elif mode == "mul":  # multiply colour (on premultiplied rgb)
            dst[..., :3] *= (1 - a[..., None]) + col * a[..., None]
        elif mode == "erase":
            dst *= (1 - a[..., None])

    def alpha_of(self, m):
        """Canvas alpha inside the mask's box."""
        x0, y0, x1, y1 = m.box
        out = np.zeros(m.a.shape, np.float32)
        r = self._region(m)
        if r is None:
            return out
        (ix0, iy0, ix1, iy1), (sy, sx) = r
        out[sy, sx] = self.px[iy0:iy1, ix0:ix1, 3]
        return out

    def composite(self, other, alpha=1.0):
        """Canvas `other` (same size) over this one."""
        a = other.px[..., 3:4] * alpha
        self.px[..., :3] = other.px[..., :3] * alpha + self.px[..., :3] * (1 - a)
        self.px[..., 3:4] = a + self.px[..., 3:4] * (1 - a)

    def image(self, size=None):
        """Downsampled straight-alpha RGBA image."""
        px = self.px
        a = np.clip(px[..., 3], 0, 1)
        rgb = np.clip(px[..., :3], 0, 1)
        # downsample premultiplied (correct edges), then un-premultiply
        pre = np.concatenate([rgb, a[..., None]], axis=-1)
        chans = []
        tw, th = size or (self.w, self.h)
        for i in range(4):
            im = Image.fromarray(pre[..., i], "F").resize((tw, th), Image.LANCZOS)
            chans.append(np.asarray(im, np.float32))
        pre = np.stack(chans, axis=-1)
        a = np.clip(pre[..., 3], 0, 1)
        rgb = np.where(a[..., None] > 1e-4, pre[..., :3] / np.maximum(a[..., None], 1e-4), 0)
        out = np.concatenate([np.clip(rgb, 0, 1), a[..., None]], axis=-1)
        return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


# =================================================================== generic painted solids

def solid(cv, m, lit, dark, r=6.0, mid=None, tex="m", tex_amt=0.10, rim=None, rim_w=2.0, flat=1.0,
          alpha=1.0, mode="over", ramp=(-0.35, 0.75), grain=0.035, light=None):
    """Paints mask m as a softly lit volume: dark -> (mid) -> lit by the Lambert term, broken up
    by coherent value noise, with an optional rim light hugging the silhouette on the far side."""
    lam = m.lambert(r, flat=flat, light=light)
    t = sstep(ramp[0], ramp[1], lam)
    if tex:
        n = m.noise(tex) - 0.5
        t = np.clip(t + n * tex_amt * 4, 0, 1)
    if mid is not None:
        col = np.where((t < 0.5)[..., None], lerp(dark, mid, t * 2), lerp(mid, lit, (t - 0.5) * 2))
    else:
        col = lerp(dark, lit, t)
    if grain:
        g = (m.noise("f") - 0.5) * grain * 2
        col = col + g[..., None]
    cv.fill(m, col, alpha, mode)
    if rim is not None:
        rim_line(cv, m, rim, rim_w)
    return lam


def rim_line(cv, m, col, width=2.0, strength=0.9, side=(1, 1)):
    """Light hugging the silhouette on the side away from the key light (bottom right)."""
    s = cv.ss
    sh = m.shift(-side[0] * width, -side[1] * width)
    band = np.clip(m.a - sh.at(m.box), 0, 1)
    band = pil_blur(band, 0.5 * s) * m.a
    cv.fill(m.copy(band), col, strength, "over")


def glow(cv, cx, cy, r, col, strength=1.0, mode="add", core=0.0):
    """Radial light: a smooth falloff (and an optional hot core)."""
    s = cv.ss
    m = cv.ellipse(cx, cy, r, r)
    X, Y = m.grid()
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / r
    f = np.clip(1 - d, 0, 1) ** 2.2 * strength
    if core:
        f = f + np.clip(1 - d * 4, 0, 1) ** 1.5 * core
    m.a = f.astype(np.float32)
    cv.fill(m, col, 1.0, mode)
    return m


def shadow(cv, m, dx=0, dy=0, blur=6, strength=0.45, col=None):
    """Soft shadow of mask m onto what is already painted (atop)."""
    col = C("#2a1d2e") if col is None else col
    sh = m.shift(dx, dy).blur(blur)
    cv.fill(sh, col, strength, "atop")


def catmull(pts, steps=8, closed=False):
    """Smooth Catmull-Rom curve through the points."""
    P = [np.array(p, np.float32) for p in pts]
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(steps):
            t = k / steps
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((float(q[0]), float(q[1])))
    if not closed:
        out.append(tuple(map(float, P[-2])))
    return out


def ridge(x0, x1, y, amp, rough, rng, n=9):
    """Midpoint-displacement ridgeline from x0 to x1 around height y."""
    pts = [(x0, y + rng.uniform(-amp, amp) * 0.3), (x1, y + rng.uniform(-amp, amp) * 0.3)]
    a = amp
    for _ in range(n):
        new = [pts[0]]
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            new.append(((xa + xb) / 2, (ya + yb) / 2 + rng.uniform(-a, a)))
            new.append((xb, yb))
        pts = new
        a *= rough
    return pts


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    print("  wrote", os.path.relpath(path, ROOT), img.size)


# =================================================================== the town: palette and layout

SUN = (330.0, 245.0)          # the low sun, upper left
SKY_TOP = C("#5d86b4")
SKY_MID = C("#a9bfcc")
SKY_WARM = C("#f4d59c")
SKY_SUN = C("#fff3cf")
HAZE = C("#f1d8b0")

# tap rects (x, y, w, h) and name-plate anchors, filled in by the painters below
HOT = {}


def haze_amount(y, top, bottom, a0, a1):
    return a0 + (a1 - a0) * np.clip((y - top) / (bottom - top), 0, 1)


def sky(cv):
    m = cv.full()
    X, Y = m.grid()
    t = np.clip(Y / 760.0, 0, 1)
    col = lerp(SKY_TOP, SKY_MID, sstep(0.0, 0.55, t))
    col = lerp(col, SKY_WARM, sstep(0.35, 1.0, t))
    d = np.sqrt((X - SUN[0]) ** 2 + ((Y - SUN[1]) * 1.25) ** 2)
    col = lerp(col, SKY_WARM, np.clip(1 - d / 1100, 0, 1) ** 1.6 * 0.8)
    col = lerp(col, SKY_SUN, np.clip(1 - d / 520, 0, 1) ** 2.0)
    col = col + (m.noise("c") - 0.5)[..., None] * 0.035
    cv.fill(m, col)
    # sun disc and halo
    glow(cv, SUN[0], SUN[1], 360, C("#ffe7b0"), 0.55)
    glow(cv, SUN[0], SUN[1], 120, C("#fff6dc"), 0.9, core=1.0)
    sun = cv.ellipse(SUN[0], SUN[1], 34, 34, blur=2)
    cv.fill(sun, C("#fffdf4"))


def cloud(cv, cx, cy, w, h, rng, lit=None, dark=None, alpha=1.0, flat=1.0, puffs=26):
    """A soft cumulus: a blurred body with billows along its top, lit from the sun's side, with
    a glowing silver lining toward the sun and cool lavender undersides."""
    lit = C("#fff0cc") if lit is None else lit
    dark = C("#b39cb4") if dark is None else dark
    items = []
    for i in range(puffs):
        u = rng.uniform(-1, 1)
        top = 1 - abs(u) ** 1.4
        r = rng.uniform(0.2, 0.42) * h * (0.5 + top * 0.9)
        items.append((cx + u * w / 2, cy + h * 0.2 - rng.uniform(0, 1) * top * h * 0.6, r * rng.uniform(1.1, 1.8), r))
    for i in range(5):
        items.append((cx + rng.uniform(-0.4, 0.4) * w, cy + h * 0.2, w * rng.uniform(0.18, 0.3), h * 0.22))
    m = cv.dabs(items)
    X, Y = m.grid()
    m.a *= sstep(cy + h * 0.5, cy + h * 0.15, Y)
    m = m.blur(h * 0.05)
    lx = (SUN[0] - cx)
    light = np.array([np.sign(lx) * 0.7, -0.5, 0.5], np.float32)
    light /= np.linalg.norm(light)
    lam = m.lambert(h * 0.22, light=light, flat=flat)
    X, Y = m.grid()
    t = sstep(-0.3, 0.9, lam) + (m.noise("m") - 0.5) * 0.5
    t = np.clip(t - sstep(cy - h * 0.1, cy + h * 0.45, Y) * 0.4, 0, 1)
    col = lerp(dark, lit, t)
    dsun = np.hypot(X - SUN[0], Y - SUN[1])
    col = lerp(col, C("#fff6dc"), np.clip(1 - dsun / 700, 0, 1)[..., None] * 0.5)
    edge = np.clip(1 - m.a * 1.6, 0, 1) * m.a * 3
    col = lerp(col, C("#fff4d0"), np.clip(edge, 0, 1)[..., None] * 0.6)
    cv.fill(m, col, alpha)


def mountain_range(cv, pts, base_y, lit, dark, haze_col, haze, rng, snow=None, facet=0.6, stria=22.0):
    """Ridgeline pts (left to right) filled down to base_y; faces that turn left toward the sun
    are lit, gullies run down the slopes, and the whole range is veiled by haze toward its base."""
    poly = pts + [(pts[-1][0], base_y), (pts[0][0], base_y)]
    m = cv.poly(poly)
    X, Y = m.grid()
    xs = np.array([p[0] for p in pts], np.float32)
    ys = np.array([p[1] for p in pts], np.float32)
    ridge_y = np.interp(X, xs, ys)
    # slope of the ridge, smoothed; negative dy/dx = rising to the right = faces the sun
    xx = np.linspace(xs[0], xs[-1], 800)
    yy = np.interp(xx, xs, ys)
    sl = np.gradient(yy, xx)
    k = 9
    sl = np.convolve(np.pad(sl, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    depth = np.clip((Y - ridge_y), 0, None)
    n = m.noise("c") - 0.5
    nm = m.noise("m") - 0.5
    # gullies: sample the slope a little to the side as we go down, wobbling with noise
    off = depth * (0.35 + n * 0.9) + nm * stria * 2
    s = np.interp(X - off, xx, sl)
    t = sstep(0.5, -0.9, s * facet * 2.2)
    t = np.clip(t + nm * 0.5 + (m.noise("s") - 0.5) * 0.35, 0, 1)
    col = lerp(dark, lit, t)
    if snow is not None:
        sn = sstep(60, 15, depth + nm * 50) * sstep(0.2, 0.6, 1 - (Y - ys.min()) / 260)
        col = lerp(col, lerp(snow * 0.8, snow, t), sn[..., None])
    hz = np.clip(haze[0] + (haze[1] - haze[0]) * np.clip((Y - ridge_y) / max(1, base_y - ys.min()), 0, 1), 0, 1)
    col = lerp(col, haze_col, hz)
    cv.fill(m, col)
    return m


def far_layer(seed=11):
    cv = Canvas(W, H, 2, seed)
    rng = random.Random(seed)
    sky(cv)
    # high wisps and cloud banks
    # thin high streaks
    for cx, cy, w, h, a in [(1350, 130, 900, 16, 0.35), (700, 170, 700, 12, 0.3), (1600, 210, 600, 14, 0.3)]:
        sm = cv.ellipse(cx, cy, w / 2, h, blur=h * 0.8)
        cv.fill(sm, C("#fff2d8"), a)
    for cx, cy, w, h, a in [(1520, 190, 560, 100, 0.85), (1200, 150, 360, 70, 0.7), (760, 230, 380, 70, 0.7),
                            (1780, 330, 460, 140, 0.95), (90, 170, 360, 80, 0.6), (560, 340, 480, 90, 0.75),
                            (1360, 380, 640, 150, 0.95)]:
        cloud(cv, cx, cy, w, h, rng, alpha=a, puffs=34)
    # farthest range: pale, snow capped
    r1 = ridge(-40, 1960, 360, 150, 0.52, rng)
    r1 = [(x, y + 60 * math.sin(x / 300.0) - (80 if 1200 < x < 1700 else 0) * math.sin((x - 1200) / 500 * math.pi)) for x, y in r1]
    mountain_range(cv, r1, 760, C("#e8cfb4"), C("#8d93b0"), C("#e6d2bb"), (0.42, 0.85), rng, snow=C("#fbf1e4"))
    # middle range
    r2 = ridge(-40, 1960, 470, 120, 0.55, rng)
    r2 = [(x, y + 40 * math.sin(x / 210.0 + 1)) for x, y in r2]
    mountain_range(cv, r2, 780, C("#d9ac7f"), C("#6c7291"), C("#dcc3a8"), (0.25, 0.8), rng)
    # distant castle on a crag at the right (echoes the reference's far castle)
    castle(cv, 1640, 452, 1.0)
    # forested far hills
    r3 = ridge(-40, 1960, 560, 45, 0.6, rng, n=10)
    fh = mountain_range(cv, r3, 800, C("#9aa56e"), C("#4f6a62"), C("#d2c4a6"), (0.35, 0.7), rng, facet=0.3)
    treeline(cv, r3, rng, C("#6f8a60"), C("#3f5a55"), C("#d6c6a2"), 0.45, size=9)
    # low haze band
    m = cv.rect(0, 420, W, H)
    X, Y = m.grid()
    cv.fill(m, HAZE, sstep(430, 720, Y) * 0.55)
    return cv


def castle(cv, x, y, s):
    """A small, hazed castle silhouette with warm lit left faces."""
    lit, dark, haze = C("#e4c7a4"), C("#8e8aa3"), C("#e2cdb5")
    parts = [(-40, -40, 80, 60), (-70, -20, 30, 40), (40, -30, 26, 50), (-12, -110, 24, 80), (-58, -70, 18, 50),
             (44, -80, 16, 50)]
    for dx, dy, w, h in parts:
        x0, y0 = x + dx * s, y + dy * s
        m = cv.rect(x0, y0, x0 + w * s, y0 + h * s)
        X, Y = m.grid()
        col = lerp(dark, lit, sstep(x0 + w * s * 0.55, x0 + w * s * 0.35, X))
        cv.fill(m, lerp(col, haze, 0.45))
        # conical roof
        rm = cv.poly([(x0 - 3 * s, y0), (x0 + w * s / 2, y0 - h * s * 0.6), (x0 + w * s + 3 * s, y0)])
        X, Y = rm.grid()
        rc = lerp(C("#6e6a92"), C("#c9a28e"), sstep(x0 + w * s * 0.6, x0 + w * s * 0.3, X))
        cv.fill(rm, lerp(rc, haze, 0.4))
    # cliff under it
    cm = cv.poly([(x - 110 * s, y + 60 * s), (x - 80 * s, y + 10), (x + 70 * s, y + 5), (x + 120 * s, y + 70 * s)])
    cv.fill(cm, lerp(C("#9b8f9c"), haze, 0.45))


def treeline(cv, pts, rng, lit, dark, haze, hz, size=10, density=1.0, jitter=6):
    """A band of small conifer/broadleaf crowns along a ridgeline (far forest)."""
    items_lit, items = [], []
    x = pts[0][0]
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    while x < pts[-1][0]:
        y = float(np.interp(x, xs, ys)) + rng.uniform(-2, jitter)
        r = size * rng.uniform(0.7, 1.3)
        items.append((x, y, r * 0.8, r))
        x += r * rng.uniform(0.7, 1.1) / density
    m = cv.dabs(items)
    solid(cv, m, lerp(lit, haze, hz), lerp(dark, haze, hz), r=size * 0.6, tex="s", tex_amt=0.12)
    return m


# =================================================================== lighting model for the village

AMB = C("#6f7aa0")        # cool sky fill
SUNC = C("#ffd49a")       # warm low sun
RIMC = C("#ffe2a8")


def lit(albedo, ndl, occl=1.0, amb=0.85, sun=1.25):
    """albedo * (cool ambient + warm sun * max(ndl, 0) * occlusion)."""
    if isinstance(ndl, np.ndarray):
        ndl = np.clip(ndl, 0, None)[..., None]
        if isinstance(occl, np.ndarray):
            occl = occl[..., None]
    else:
        ndl = max(ndl, 0.0)
    return albedo * (AMB * amb + SUNC * sun * ndl * occl)


def aniso_noise(h, w, cx, cy, seed, octaves=3):
    """Value noise with separate cell sizes along x and y (streaks, strata, grain)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        sh, sw = int(h / cy) + 3, int(w / cx) + 3
        small = Image.fromarray(rng.random((sh, sw)).astype(np.float32), "F")
        big = np.asarray(small.resize((int(sw * cx), int(sh * cy)), Image.BICUBIC), np.float32)
        out += big[int(cy):int(cy) + h, int(cx):int(cx) + w] * amp
        tot += amp
        amp *= 0.5
        cx, cy = max(1.5, cx / 2), max(1.5, cy / 2)
    return out / tot


def height_ndl(hf, k, light=None):
    gy, gx = np.gradient(hf)
    nx, ny = -gx * k, -gy * k
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
    L = LIGHT if light is None else light
    return (nx * L[0] + ny * L[1] + L[2]) * inv


def rock_height(cv, m, big=(140, 220), small=(50, 70), dome_r=40.0, seed=3, warp=40.0, w_big=0.35,
                w_small=0.1, w_dome=2.0):
    """Height field of chunky rock inside mask m: the silhouette's soft dome plus Voronoi chunks
    (domain-warped plateaus with bevelled borders and a random tilt each). Returns (hf, crack, dome)."""
    s = cv.ss
    X, Y = m.grid()
    h, w = m.a.shape
    wx = (aniso_noise(h, w, 40 * s, 40 * s, seed + 7, 3) - 0.5) * warp
    wy = (aniso_noise(h, w, 40 * s, 40 * s, seed + 8, 3) - 0.5) * warp

    def chunks(cw, ch, sd, cap, tilt):
        U = (X + wx) / cw * 20
        V = (Y + wy) / ch * 20
        d1, d2, idc, px, py = worley(U, V, 20.0, sd, True)
        e = np.minimum(d2 - d1, cap) / cap
        h2 = np.modf(idc * 7.31)[0]
        plane = ((U - px) * (idc - 0.5) * tilt + (V - py) * (h2 - 0.5) * tilt) / 20
        return np.sqrt(e) + plane, d2 - d1

    pad = int(dome_r * s * 2.2) + 2
    dome = gblur(np.pad(m.a, pad), dome_r * s)[pad:-pad, pad:-pad]
    c1, e1 = chunks(big[0], big[1], seed, 6.0, 0.7)
    hf = dome * w_dome + c1 * w_big
    crack = sstep(0.9, 0.0, e1)
    if small:
        c2, e2 = chunks(small[0], small[1], seed + 1, 3.0, 0.5)
        hf = hf + c2 * w_small
        crack = np.maximum(crack, sstep(0.5, 0.0, e2) * 0.35)
    hf = hf + (m.noise("m") - 0.5) * 0.04
    return hf, crack, dome


def rock(cv, m, albedo=None, dark_albedo=None, seed=3, k=45.0, moss=0.0, moss_col=None, haze=0.0,
         haze_col=None, big=(140, 220), small=(50, 70), dome_r=40.0, w_big=0.35, w_small=0.1, sun=1.2,
         crack_k=0.6):
    """Chunky rock lit by the low sun: warm lit planes, cool shadow planes, dark cracks and moss
    on the upward-facing ledges."""
    s = cv.ss
    albedo = C("#c9b098") if albedo is None else albedo
    dark_albedo = C("#80727c") if dark_albedo is None else dark_albedo
    hf, crack, dome = rock_height(cv, m, big, small, dome_r, seed, w_big=w_big, w_small=w_small)
    ndl = height_ndl(hf, k * s)
    n = m.noise("m")
    base = lerp(dark_albedo, albedo, np.clip(n * 1.5 - 0.25, 0, 1))
    occ = np.clip(0.45 + dome * 0.7, 0, 1)
    col = lit(base, ndl * sun, occ)
    if moss:
        gy = np.gradient(hf, axis=0) * k * s
        up = sstep(0.05, 0.6, -gy)
        mc = C("#7f9a45") if moss_col is None else moss_col
        mm = np.clip(up * moss * (m.noise("s") * 1.8 - 0.5), 0, 1)
        col = lerp(col, lit(mc, ndl + 0.25, occ), mm)
    col = lerp(col, col * C("#4a3c56") * 1.2, crack * crack_k)
    col = col + (m.noise("f") - 0.5)[..., None] * 0.06
    if haze:
        col = lerp(col, HAZE if haze_col is None else haze_col, haze)
    cv.fill(m, col)
    return ndl


class Face:
    """A flat wall or roof plane in oblique projection: screen point = o + a*u + b*v (u, v in 0..1).
    wu, wv are its size in world units (pattern density)."""

    def __init__(self, cv, o, a, b, wu, wv, ndl):
        self.cv = cv
        self.o = np.array(o, np.float32)
        self.a = np.array(a, np.float32)
        self.b = np.array(b, np.float32)
        self.wu, self.wv, self.ndl = wu, wv, ndl
        M = np.array([[self.a[0], self.b[0]], [self.a[1], self.b[1]]], np.float32)
        self.inv = np.linalg.inv(M)

    def pt(self, u, v):
        p = self.o + self.a * u + self.b * v
        return (float(p[0]), float(p[1]))

    def quad(self, u0, v0, u1, v1):
        return [self.pt(u0, v0), self.pt(u1, v0), self.pt(u1, v1), self.pt(u0, v1)]

    def mask(self, u0=0.0, v0=0.0, u1=1.0, v1=1.0, blur=0.0):
        return self.cv.poly(self.quad(u0, v0, u1, v1), blur)

    def uv(self, m):
        X, Y = m.grid()
        dx, dy = X - self.o[0], Y - self.o[1]
        u = self.inv[0, 0] * dx + self.inv[0, 1] * dy
        v = self.inv[1, 0] * dx + self.inv[1, 1] * dy
        return u, v


def _hash(a, b, seed=0):
    x = (a.astype(np.int64) * 374761393 + b.astype(np.int64) * 668265263 + (seed * 2654435761 & 0xFFFFFFF)) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((x ^ (x >> 16)) & 0xFFFF).astype(np.float32) / 65535.0


def stone_blocks(U, V, bh=9.0, bw=16.0, seed=1, mortar=0.09, round_=0.18):
    """Coursed stone: returns (tone 0..1 per block, bevel -1..1 lighting term, mortar 0..1)."""
    row = np.floor(V / bh)
    fy = V / bh - row
    off = _hash(row, row * 0 + 7, seed) * bw
    wrow = bw * (0.75 + 0.5 * _hash(row, row * 0 + 3, seed))
    col = np.floor((U + off) / wrow)
    fx = (U + off) / wrow - col
    tone = _hash(row, col, seed)
    # bevel: lit top-left edges, dark bottom-right edges (rounded blocks)
    ex = np.minimum(fx, 1 - fx) * wrow
    ey = np.minimum(fy, 1 - fy) * bh
    e = np.minimum(ex, ey)
    edge = sstep(round_ * bh, 0.0, e)
    lightside = np.where(fx < 0.5, 1.0, -1.0) * (ex < ey) + np.where(fy < 0.5, 1.0, -1.0) * (ey <= ex)
    bevel = edge * lightside
    mor = sstep(mortar * bh * 1.2, mortar * bh * 0.4, e)
    return tone, bevel, mor


def paint_stone_face(cv, face, m, albedo, seed=1, bh=9, bw=16, occl=None, dirt=0.25, extra_ndl=0.0):
    u, v = face.uv(m)
    U, V = u * face.wu, v * face.wv
    tone, bevel, mor = stone_blocks(U, V, bh, bw, seed)
    n = m.noise("m") - 0.5
    alb = albedo * (0.82 + tone[..., None] * 0.3 + n[..., None] * 0.25)
    ndl = face.ndl + bevel * 0.35 + extra_ndl
    occ = 1.0 if occl is None else occl
    col = lit(alb, ndl, occ)
    col = lerp(col, lit(albedo * 0.45, face.ndl * 0.3, 1.0), mor * 0.85)
    # grime toward the ground
    col = lerp(col, col * 0.62, np.clip(sstep(0.55, 1.0, v) * dirt * (1 + n * 2), 0, 1))
    col = col + (m.noise("f") - 0.5)[..., None] * 0.04
    cv.fill(m, col)


def paint_plaster(cv, face, m, albedo, occl=None, dirt=0.3, stain=0.25):
    u, v = face.uv(m)
    n = m.noise("m") - 0.5
    nc = m.noise("c") - 0.5
    alb = albedo * (0.95 + n[..., None] * 0.18 + nc[..., None] * stain)
    col = lit(alb, face.ndl + n * 0.1, 1.0 if occl is None else occl)
    col = lerp(col, col * 0.7, np.clip(sstep(0.6, 1.0, v) * dirt * (1 + n * 3), 0, 1))
    col = col + (m.noise("f") - 0.5)[..., None] * 0.035
    cv.fill(m, col)


def paint_planks(cv, face, m, albedo, width=5.0, vertical=True, seed=2, occl=None, gap=0.12):
    u, v = face.uv(m)
    U, V = u * face.wu, v * face.wv
    A, B = (U, V) if vertical else (V, U)
    k = np.floor(A / width)
    f = A / width - k
    tone = _hash(k, k * 0 + 5, seed)
    h, w = m.a.shape
    s = cv.ss
    grain = aniso_noise(h, w, 2 * s, 30 * s, seed, 3) if vertical else aniso_noise(h, w, 30 * s, 2 * s, seed, 3)
    alb = albedo * (0.8 + tone[..., None] * 0.35 + (grain[..., None] - 0.5) * 0.35)
    bev = sstep(0.25, 0.0, f) * 0.3 - sstep(0.75, 1.0, f) * 0.35
    col = lit(alb, face.ndl + bev, 1.0 if occl is None else occl)
    gapm = sstep(gap, gap * 0.3, np.minimum(f, 1 - f))
    col = lerp(col, col * 0.35, gapm)
    cv.fill(m, col)


def paint_tiles(cv, face, m, albedo, rows=10, per=1.0, seed=4, scallop=True, occl=None, moss=0.0):
    """Roof tiles/shingles in rows along v (v=0 at the ridge)."""
    u, v = face.uv(m)
    U, V = u * face.wu, v * face.wv
    th = face.wv / rows
    row = np.floor(V / th)
    fy = V / th - row
    tw = th * 1.3 * per
    off = (row % 2) * tw * 0.5
    colx = np.floor((U + off) / tw)
    fx = (U + off) / tw - colx
    tone = _hash(row, colx, seed)
    if scallop:
        curve = 0.78 + 0.22 * np.sqrt(np.clip(1 - (2 * fx - 1) ** 2, 0, 1))
    else:
        curve = np.full_like(fx, 0.92)
    inside = fy < curve
    shade_t = np.where(inside, fy / curve, 1.0)
    ndl = face.ndl + (0.25 - shade_t * 0.55) + (0.5 - np.abs(fx - 0.5)) * 0.15
    n = m.noise("m") - 0.5
    alb = albedo * (0.8 + tone[..., None] * 0.35 + n[..., None] * 0.2)
    if moss:
        mm = np.clip((m.noise("c") - 0.45) * 3 * moss, 0, 1)
        alb = lerp(alb, C("#6e7f3c"), mm * 0.6)
    col = lit(alb, ndl, 1.0 if occl is None else occl)
    col = np.where(inside[..., None], col, col * 0.35)
    col = col + (m.noise("f") - 0.5)[..., None] * 0.04
    cv.fill(m, col)


# =================================================================== fire, light, small helpers

def flame_pts(x, y, w, h, lean=0.0, wob=0.0, n=14):
    """Teardrop flame outline with its base centred at (x, y)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        a = math.pi * t
        # right side going up, then left side coming down
        yy = y - h * t
        ww = w * 0.5 * math.sin(math.pi * min(1.0, (1 - t) ** 0.8 + 0.02)) * (1 - t) ** 0.35
        pts.append((x + ww + lean * h * t * t + wob * math.sin(t * 9) * w * 0.1, yy))
    for i in range(n, -1, -1):
        t = i / n
        yy = y - h * t
        ww = w * 0.5 * math.sin(math.pi * min(1.0, (1 - t) ** 0.8 + 0.02)) * (1 - t) ** 0.35
        pts.append((x - ww + lean * h * t * t - wob * math.sin(t * 7 + 1) * w * 0.1, yy))
    return pts


def flame(cv, gl, x, y, s=1.0, lean=0.08, spill=90, spill_k=0.55, seed=None):
    """A painted fire: a few licking tongues (deep red rim, orange body, yellow, white-hot core)
    with its glow in `gl` and warm light spilled onto what is around it."""
    rng = random.Random(seed if seed is not None else int(x * 7 + y * 13))
    tongues = [(0, 1.0, 1.0, lean)]
    for _ in range(4):
        tongues.append((rng.uniform(-0.3, 0.3), rng.uniform(0.45, 0.8), rng.uniform(0.35, 0.55), lean + rng.uniform(-0.25, 0.25)))
    for w, h, col, bl, a in [(30, 64, C("#c8321a"), 2.0, 0.85), (25, 54, C("#ff7a1e"), 1.4, 1.0),
                             (17, 38, C("#ffc43a"), 1.0, 1.0), (9, 20, C("#fff6d0"), 0.8, 1.0)]:
        m = None
        for dx, hk, wk, ln in tongues:
            if w < 12 and hk < 0.9:
                continue
            mm = cv.poly(flame_pts(x + dx * w * s, y, w * wk * s * (1.6 if hk < 1 else 1), h * hk * s, ln, 1.0))
            m = mm if m is None else m | mm
        cv.fill(m.blur(bl * s), col, a)
    if gl is not None:
        glow(gl, x, y - 24 * s, 100 * s * spill_k * 1.8, C("#ff8a2a"), 0.5, mode="addfree")
        glow(gl, x, y - 22 * s, 30 * s, C("#fff0c0"), 0.8, mode="addfree", core=0.5)
    if spill:
        glow(cv, x, y - 18 * s, spill * s, C("#ff9d48"), spill_k, mode="add")


def lantern(cv, gl, x, y, s=1.0, post=None):
    """Hanging iron lantern with a warm pane; glow into gl."""
    iron = C("#2e2830")
    top = cv.poly([(x - 9 * s, y - 12 * s), (x + 9 * s, y - 12 * s), (x + 4 * s, y - 20 * s), (x - 4 * s, y - 20 * s)])
    cv.fill(top, lit(iron, 0.5))
    body = cv.rect(x - 8 * s, y - 12 * s, x + 8 * s, y + 10 * s, radius=2 * s)
    cv.fill(body, lit(iron, 0.3))
    pane = cv.rect(x - 5.5 * s, y - 9 * s, x + 5.5 * s, y + 7 * s)
    X, Y = pane.grid()
    cv.fill(pane, lerp(C("#fff3c0"), C("#ffb24a"), sstep(y - 8 * s, y + 7 * s, Y)))
    cv.fill(cv.rect(x - 0.8 * s, y - 9 * s, x + 0.8 * s, y + 7 * s), iron, 0.8)
    cv.fill(cv.rect(x - 10 * s, y + 9 * s, x + 10 * s, y + 13 * s, radius=1), lit(iron, 0.4))
    glow(cv, x, y, 60 * s, C("#ffb259"), 0.35, mode="add")
    if gl is not None:
        glow(gl, x, y, 70 * s, C("#ffa84a"), 0.5, mode="addfree")
        glow(gl, x, y, 16 * s, C("#fff2c8"), 0.9, mode="addfree")


def window(cv, gl, pts, arched=False, bars=2, frame=None, s=1.0, warm=1.0, glow_r=None):
    """A lit window: pts = quad (tl, tr, br, bl) on its wall; warm interior gradient + mullions."""
    frame = C("#3a2a22") if frame is None else frame
    (x0, y0), (x1, _), (x2, y2), (x3, _) = pts
    cx = (x0 + x1 + x2 + x3) / 4
    ww = (x1 - x0)
    if arched:
        r = ww / 2
        arch = [(x0 + r - r * math.cos(math.pi * i / 12), y0 - r * math.sin(math.pi * i / 12) * 0.9) for i in range(13)]
        outline = arch + [pts[2], pts[3]]
    else:
        outline = list(pts)
    fm = cv.poly(outline)
    big = cv.poly([(px + (px - cx) * 0.18, py + (py - (y0 + y2) / 2) * 0.12) for px, py in outline])
    cv.fill(big, lit(frame, 0.35))
    m = cv.poly(outline)
    X, Y = m.grid()
    top = min(p[1] for p in outline)
    cxw = (x0 + x1) / 2
    d = np.sqrt(((X - cxw) / max(4, ww * 0.6)) ** 2 + ((Y - (top + y2) / 2) / max(4, (y2 - top) * 0.6)) ** 2)
    glowc = lerp(C("#ffe2a0"), C("#b8561e"), sstep(0.1, 1.2, d))
    cv.fill(m, glowc * warm + C("#3a2020") * (1 - warm))
    # mullions
    if bars:
        for i in range(1, bars):
            t = i / bars
            xa = x0 + (x1 - x0) * t
            xb = x3 + (x2 - x3) * t
            cv.fill(cv.line([(xa, top), (xb, y2)], 1.6 * s), frame, 0.9)
        ym = (top + y2) / 2 + (y2 - top) * 0.08
        cv.fill(cv.line([(x0, ym), (x1, ym)], 1.6 * s), frame, 0.9)
    # sill
    cv.fill(cv.poly([(x3 - 3 * s, y2), (x2 + 3 * s, y2), (x2 + 2 * s, y2 + 4 * s), (x3 - 2 * s, y2 + 4 * s)]),
            lit(C("#9c8a78"), 0.6))
    if gl is not None:
        r = glow_r or max(ww, y2 - top) * 1.1
        gm = cv.poly(outline)
        gl.fill(gm.blur(2), C("#ffb860"), 0.45, "addfree")
        glow(gl, cx, (top + y2) / 2, r, C("#ff9c40"), 0.22 * warm, mode="addfree")


def smoke_wisp(cv, x, y, s=1.0, alpha=0.5, rng=None):
    rng = rng or random.Random(1)
    items = []
    for i in range(9):
        t = i / 8
        items.append((x + math.sin(t * 3.2) * 18 * s * t + 30 * s * t, y - 150 * s * t, (8 + 26 * t) * s, (8 + 22 * t) * s))
    m = cv.dabs(items, blur=6 * s)
    X, Y = m.grid()
    a = sstep(y - 160 * s, y - 20 * s, Y) * alpha
    cv.fill(m, lerp(C("#b8aab0"), C("#efe0cc"), sstep(x + 30 * s, x - 10 * s, X)), a)


# =================================================================== foliage

LEAF_DARK = C("#1c3129")
LEAF_MID = C("#3f6b35")
LEAF_LIT = C("#9fb84e")
LEAF_HI = C("#f2e08c")


def leaf_clump(cv, cx, cy, R, rng, bias=0.0, pal=None, leaf=None, hz=0.0, haze_col=None, rim=0.6, n=None):
    """One clump of leaves: a dense dab cluster, soft-lit from the upper left, with bright leaf
    dabs on its lit top and a golden rim on its far edge. bias (-1..1) shifts it darker/lighter."""
    dark, mid, lt, hi = pal or (LEAF_DARK, LEAF_MID, LEAF_LIT, LEAF_HI)
    leaf = leaf or max(2.5, R * 0.2)
    items = [(cx, cy + R * 0.1, R * 0.8, R * 0.7)]
    n = n or int(14 + (R / leaf) ** 2 * 0.9)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        d = R * math.sqrt(rng.uniform(0.15, 1.0))
        lx, ly = cx + math.cos(a) * d, cy + math.sin(a) * d * 0.85
        rr = leaf * rng.uniform(0.6, 1.25)
        items.append((lx, ly, rr, rr * rng.uniform(0.6, 0.95)))
    m = cv.dabs(items)
    lam = m.lambert(R * 0.45, precise=False)
    t = sstep(-0.3, 0.85, lam) + bias * 0.35 + (m.noise("s") - 0.5) * 0.5
    t = np.clip(t, 0, 1)
    col = np.where((t < 0.5)[..., None], lerp(dark, mid, t * 2), lerp(mid, lt, (t - 0.5) * 2))
    if hz:
        col = lerp(col, HAZE if haze_col is None else haze_col, hz)
    cv.fill(m, col)
    # sunlit leaf dabs on the upper left
    if bias > -0.6:
        k = int(n * 0.35)
        dab = []
        for _ in range(k):
            a = rng.uniform(math.pi * 0.9, math.pi * 1.75)
            d = R * rng.uniform(0.35, 0.95)
            rr = leaf * rng.uniform(0.35, 0.7)
            dab.append((cx + math.cos(a) * d, cy + math.sin(a) * d * 0.85, rr, rr * 0.7))
        dm = cv.dabs(dab)
        cc = lerp(lt, hi, 0.35 + 0.3 * max(0, bias))
        if hz:
            cc = lerp(cc, HAZE if haze_col is None else haze_col, hz)
        cv.fill(dm & m, cc, 0.75)
    if rim:
        rim_line(cv, m, lerp(C("#ffd98a"), LEAF_LIT, 0.3), max(1.2, leaf * 0.35), rim * 0.8, side=(1, 0.3))
    return m


def canopy(cv, cx, cy, rx, ry, rng, clump=None, pal=None, hz=0.0, haze_col=None, density=1.0, leaf=None):
    """A tree crown built back to front from leaf clumps."""
    clump = clump or max(14, min(rx, ry) * 0.36)
    pts = []
    k = int((rx * ry) / (clump * clump) * 2.2 * density) + 5
    for _ in range(k):
        a = rng.uniform(0, 2 * math.pi)
        d = math.sqrt(rng.uniform(0, 1))
        pts.append((cx + math.cos(a) * d * rx, cy + math.sin(a) * d * ry))
    # back (lower right, darker) first, front/upper left (brighter) last
    pts.sort(key=lambda p: (p[1] - cy) / ry * 0.4 + (p[0] - cx) / rx * 0.35 - math.hypot(p[0] - cx, p[1] - cy) / max(rx, ry) * 0.2, reverse=True)
    mask = None
    for i, (x, y) in enumerate(pts):
        pos = -((y - cy) / ry) * 0.55 - ((x - cx) / rx) * 0.35
        bias = pos * 0.8 + (i / len(pts) - 0.5) * 0.7
        m = leaf_clump(cv, x, y, clump * rng.uniform(0.8, 1.2), rng, bias, pal, leaf, hz, haze_col)
        mask = m if mask is None else (mask | m)
    return mask


def trunk(cv, pts, w0, w1, col=None, hz=0.0):
    col = C("#5a4032") if col is None else col
    m = cv.taper(pts, w0, w1)
    lam = m.lambert(max(2, w0 * 0.35))
    h, w = m.a.shape
    bark = aniso_noise(h, w, 2.5 * cv.ss, 16 * cv.ss, 9, 3)
    c = lit(col * (0.75 + bark[..., None] * 0.5), lam * 1.2)
    if hz:
        c = lerp(c, HAZE, hz)
    cv.fill(m, c)
    rim_line(cv, m, C("#ffcf8a"), 1.5, 0.5, side=(-1, 0))
    return m


def tree(cv, x, y, s, rng, pal=None, hz=0.0, lean=0.0, crown=(1.0, 1.0), trunk_col=None):
    """A broadleaf tree standing at (x, y) (its base), about 260*s tall."""
    h = 260 * s
    trunk(cv, [(x, y), (x + lean * 20 * s, y - h * 0.35), (x + lean * 40 * s, y - h * 0.62)], 22 * s, 8 * s,
          trunk_col, hz)
    # a couple of limbs
    for dx, dy in [(-50, -0.72), (48, -0.68)]:
        trunk(cv, [(x + lean * 30 * s, y - h * 0.48), (x + dx * s * 0.6, y + h * dy * 0.95), (x + dx * s, y + h * dy)],
              7 * s, 3 * s, trunk_col, hz)
    return canopy(cv, x + lean * 40 * s, y - h * 0.66, 110 * s * crown[0], 92 * s * crown[1], rng, pal=pal, hz=hz)


def conifer(cv, x, y, s, rng, hz=0.0, pal=None):
    dark, mid, lt, hi = pal or (C("#17302a"), C("#2e5a3b"), C("#7d9c4a"), C("#e0d488"))
    h = 230 * s
    trunk(cv, [(x, y), (x, y - h * 0.3)], 9 * s, 6 * s, hz=hz)
    tiers = 7
    for i in range(tiers):
        t = i / (tiers - 1)
        ty = y - h * (0.18 + 0.78 * t)
        tw = (1 - t) * 70 * s + 12 * s
        pts = [(x - tw, ty + 30 * s * (1 - t * 0.4))]
        for k in range(1, 8):
            u = k / 8
            pts.append((x - tw + 2 * tw * u, ty + 30 * s * (1 - t * 0.4) + rng.uniform(-6, 8) * s * (1 - t)))
        pts += [(x + tw, ty + 30 * s * (1 - t * 0.4)), (x + tw * 0.2, ty - 40 * s), (x, ty - 48 * s),
                (x - tw * 0.2, ty - 40 * s)]
        m = cv.poly(pts)
        X, Y = m.grid()
        tt = np.clip(sstep(x + tw * 0.6, x - tw * 0.8, X) * 0.9 + (m.noise("s") - 0.5) * 0.6 - sstep(ty, ty + 30 * s, Y) * 0.3, 0, 1)
        col = np.where((tt < 0.5)[..., None], lerp(dark, mid, tt * 2), lerp(mid, lt, (tt - 0.5) * 2))
        if hz:
            col = lerp(col, HAZE, hz)
        cv.fill(m, col)
        rim_line(cv, m, C("#ffd98a"), 1.5, 0.45, side=(1, 0.2))


def bush(cv, x, y, w, h, rng, pal=None, flowers=None, hz=0.0):
    m = None
    k = max(3, int(w / 26))
    for i in range(k):
        t = (i + 0.5) / k
        bx = x - w / 2 + w * t + rng.uniform(-6, 6)
        by = y - h * 0.45 - math.sin(t * math.pi) * h * 0.25
        r = h * 0.5 * rng.uniform(0.8, 1.1)
        mm = leaf_clump(cv, bx, by, r, rng, bias=(0.3 - t * 0.6), pal=pal, hz=hz)
        m = mm if m is None else m | mm
    if flowers is not None:
        fl = []
        for _ in range(int(w / 6)):
            fl.append((x + rng.uniform(-w / 2, w / 2) * 0.9, y - rng.uniform(0.2, 0.95) * h, 2.4, 2.2))
        fm = cv.dabs(fl) & m
        cv.fill(fm, flowers)
        cv.fill(cv.dabs([(a - 0.7, b - 0.7, 1.0, 1.0) for a, b, _, _ in fl]) & m, lerp(flowers, C("#ffffff"), 0.6), 0.8)
    return m


def grass_tufts(cv, x0, y0, x1, y1, n, rng, h=14, col=None, lit_col=None, hz=0.0):
    """Blades of grass as thin tapered strokes (foreground detail)."""
    col = C("#3e6a2c") if col is None else col
    lit_col = C("#b8c85a") if lit_col is None else lit_col
    for _ in range(n):
        x = rng.uniform(x0, x1)
        y = rng.uniform(y0, y1)
        k = rng.randint(3, 6)
        for j in range(k):
            ang = rng.uniform(-0.5, 0.5)
            hh = h * rng.uniform(0.6, 1.2)
            tip = (x + j * 1.5 + math.sin(ang) * hh, y - math.cos(ang) * hh)
            mid = (x + j * 1.5 + math.sin(ang) * hh * 0.4, y - math.cos(ang) * hh * 0.55)
            m = cv.taper([(x + j * 1.5, y), mid, tip], 2.4, 0.3)
            c = lerp(col, lit_col, rng.uniform(0.1, 0.9))
            if hz:
                c = lerp(c, HAZE, hz)
            cv.fill(m, c, 0.95)


# =================================================================== terrain

GRASS_LIT = C("#b9c45a")
GRASS_MID = C("#6f9a3c")
GRASS_DARK = C("#2f5431")
DIRT = C("#b08a62")


def cliff_outline(rng):
    """The mountain the Dungeon Gate is cut into (centre), with its shoulders."""
    top = [(440, 720), (500, 600), (545, 540), (590, 505), (630, 440), (672, 402), (700, 340), (742, 300),
           (780, 262), (812, 200), (846, 172), (872, 128), (905, 96), (930, 104), (956, 80), (990, 118),
           (1022, 142), (1052, 136), (1084, 170), (1118, 196), (1150, 242), (1186, 262), (1222, 318),
           (1262, 352), (1300, 420), (1348, 470), (1400, 530), (1450, 590), (1500, 720)]
    out = []
    for (xa, ya), (xb, yb) in zip(top, top[1:]):
        out.append((xa, ya))
        for k in range(1, 3):
            t = k / 3
            out.append((xa + (xb - xa) * t + rng.uniform(-5, 5), ya + (yb - ya) * t + rng.uniform(-7, 7)))
    out.append(top[-1])
    return out


def back_hills(cv, rng):
    """Grassy hills and far woods left and right of the mountain, behind the buildings."""
    for side in (-1, 1):
        if side < 0:
            pts = [(-20, 452), (140, 430), (300, 446), (440, 486), (560, 540), (640, 610)]
        else:
            pts = [(1280, 610), (1370, 530), (1500, 478), (1640, 448), (1800, 432), (1940, 446)]
        pts = catmull(pts, 10)
        poly = pts + [(pts[-1][0], 800), (pts[0][0], 800)]
        m = cv.poly(poly)
        X, Y = m.grid()
        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        ry = np.interp(X, xs, ys)
        t = np.clip(sstep(ry + 70, ry, Y) * 0.6 + (m.noise("c") - 0.5) * 0.6, 0, 1)
        col = lerp(C("#6c8a4c"), C("#c3c574"), t)
        cv.fill(m, lerp(col, HAZE, 0.4))
        # woods along the crest: rows of leafy clumps, hazier at the back
        for row, (dy, size, hz) in enumerate([(0, 15, 0.42), (22, 19, 0.3), (46, 23, 0.2)]):
            x = pts[0][0]
            while x < pts[-1][0]:
                y = float(np.interp(x, xs, ys)) + dy + rng.uniform(-4, 8)
                r = size * rng.uniform(0.7, 1.35)
                leaf_clump(cv, x, y, r, rng, bias=rng.uniform(-0.4, 0.3), hz=hz, rim=0.4, n=18)
                x += r * rng.uniform(1.0, 1.6)


def cliff(cv, rng):
    out = cliff_outline(rng)
    poly = out + [(1500, 780), (440, 780)]
    m = cv.poly(poly)
    X, Y = m.grid()
    rock(cv, m, albedo=C("#b4ab98"), dark_albedo=C("#6c6c78"), seed=21, k=42, moss=1.7, dome_r=60,
         big=(150, 240), small=(55, 80), w_big=0.38, w_small=0.08)
    # the upper cliff sits in warm air; big light planes: sunlit left flank, shadowed right flank
    cv.fill(m, HAZE, sstep(560, 90, Y) * 0.3, "atop")
    fx = (X - 960) / 540
    cv.fill(m, C("#ffc98a"), np.clip(-fx, 0, 1) ** 1.2 * 0.2, "atop")
    cv.fill(m, C("#3c3858"), np.clip(fx, 0, 1) ** 1.1 * 0.34, "atop")
    rim_line(cv, m, C("#ffe6b0"), 3, 0.9, side=(1, 1))
    return m


def cliff_greenery(cv, rng):
    """Ledges of grass, bushes and hanging ivy on the mountain."""
    for (lx, ly, lw) in [(575, 540, 110), (672, 430, 80), (760, 322, 50), (1180, 300, 60), (1270, 400, 90),
                         (1360, 505, 130), (850, 215, 36), (1080, 200, 40)]:
        for i in range(max(2, int(lw / 30))):
            x = lx - lw / 2 + (i + 0.5) * lw / max(2, int(lw / 30))
            leaf_clump(cv, x + rng.uniform(-6, 6), ly + rng.uniform(-4, 4), rng.uniform(12, 20), rng,
                       bias=0.2 - (x - 960) / 900, hz=0.12, rim=0.6, n=22)
    # ivy curtains over the rock
    for (x, y, ln) in [(700, 350, 120), (735, 320, 90), (1210, 320, 140), (1245, 350, 100), (640, 450, 80),
                       (1300, 430, 90)]:
        pts = [(x, y)]
        for k in range(8):
            pts.append((pts[-1][0] + rng.uniform(-4, 4), pts[-1][1] + ln / 8))
        items = []
        for (px, py) in pts:
            for _ in range(3):
                items.append((px + rng.uniform(-8, 8), py + rng.uniform(-6, 6), rng.uniform(4, 7), rng.uniform(3, 5)))
        im = cv.dabs(items)
        lam = im.lambert(4, precise=False)
        cv.fill(im, lerp(C("#29452e"), C("#8fae4a"), sstep(-0.3, 0.9, lam + (im.noise("s") - 0.5))))


def ground(cv, rng):
    """The green hillside the village stands on (everything below the mountain's foot)."""
    top = catmull([(-20, 548), (200, 530), (420, 548), (600, 596), (760, 614), (960, 610), (1160, 614),
                   (1330, 600), (1520, 552), (1720, 532), (1940, 540)], 12)
    m = cv.poly(top + [(1940, 1090), (-20, 1090)])
    X, Y = m.grid()
    h, w = m.a.shape
    s = cv.ss
    broad = aniso_noise(h, w, 260 * s, 60 * s, 31, 3)       # rolling swells across the slope
    patch = aniso_noise(h, w, 90 * s, 30 * s, 32, 3)        # sun patches
    blades = aniso_noise(h, w, 1.4 * s, 6 * s, 33, 2)
    t = 0.5 + (broad - 0.5) * 1.3 + (patch - 0.5) * 0.7
    t = t + (blades - 0.5) * (0.15 + sstep(620, 1050, Y) * 0.45)
    t = np.clip(t, 0, 1)
    col = np.where((t < 0.5)[..., None], lerp(GRASS_DARK, GRASS_MID, t * 2), lerp(GRASS_MID, GRASS_LIT, (t - 0.5) * 2))
    col = lerp(col, HAZE, sstep(760, 560, Y) * 0.35)
    col = lerp(col, col * C("#93a2c6"), sstep(880, 1080, Y) * 0.3)
    cv.fill(m, col)
    return m


def worley(U, V, cell, seed, centers=False):
    """Distance to nearest / second nearest jittered point (cobbles, flagstones, rock chunks)."""
    gx, gy = np.floor(U / cell), np.floor(V / cell)
    d1 = np.full(U.shape, 1e9, np.float32)
    d2 = np.full(U.shape, 1e9, np.float32)
    idc = np.zeros(U.shape, np.float32)
    nx = np.zeros(U.shape, np.float32) if centers else None
    ny = np.zeros(U.shape, np.float32) if centers else None
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = gx + ox, gy + oy
            px = (cx + 0.1 + 0.8 * _hash(cx, cy, seed)) * cell
            py = (cy + 0.1 + 0.8 * _hash(cx + 17, cy + 5, seed + 9)) * cell
            d = np.hypot(U - px, V - py)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            idc = np.where(closer, _hash(cx + 3, cy + 11, seed + 3), idc)
            if centers:
                nx = np.where(closer, px, nx)
                ny = np.where(closer, py, ny)
            d1 = np.where(closer, d, d1)
    if centers:
        return d1, d2, idc, nx, ny
    return d1, d2, idc


def cobbles(cv, m, cell=9.0, seed=5, albedo=None, persp=True, squash=0.6):
    """Cobblestones: rounded domes with their own tone each, lit from the upper left, dark joints."""
    albedo = C("#b3a088") if albedo is None else albedo
    X, Y = m.grid()
    sc = np.clip(0.55 + (Y - 560) / 520 * 0.75, 0.4, 1.4) if persp else 1.0
    U = (X - 960) / sc + 960
    V = Y / squash
    d1, d2, idc, px, py = worley(U, V, cell, seed, True)
    e = d2 - d1
    gap = sstep(1.6, 0.4, e)
    r = np.maximum(d1, 1e-3)
    slope = sstep(cell * 0.15, cell * 0.55, d1) * 0.7
    ndl = 0.5 + ((U - px) * LIGHT[0] + (V - py) * LIGHT[1]) / r * slope * 0.8
    alb = albedo * (0.8 + idc[..., None] * 0.3 + (m.noise("m")[..., None] - 0.5) * 0.35)
    # worn dirt and moss creeping into the joints
    alb = lerp(alb, C("#8a7a52"), np.clip((m.noise("c") - 0.45) * 2.5, 0, 0.6))
    col = lit(alb, ndl)
    col = lerp(col, col * C("#5a4a50") * 0.8, gap * 0.8)
    col = col + (m.noise("f") - 0.5)[..., None] * 0.05
    cv.fill(m, col)


def path(cv, pts, widths, rng, stone=True, seed=5, edge_grass=True):
    """A cobbled or dirt path along a centre line with widths per point."""
    c = catmull(pts, 10)
    ws = np.interp(np.linspace(0, 1, len(c)), np.linspace(0, 1, len(widths)), widths)
    left, right = [], []
    for i, p in enumerate(c):
        a = c[max(0, i - 1)]
        b = c[min(len(c) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        wob = rng.uniform(-0.04, 0.04) * ws[i]
        left.append((p[0] + nx * (ws[i] / 2 + wob), p[1] + ny * (ws[i] / 2 + wob)))
        right.append((p[0] - nx * (ws[i] / 2 - wob), p[1] - ny * (ws[i] / 2 - wob)))
    m = cv.poly(left + right[::-1]).blur(1.5)
    # dirt shoulder
    sh = m.blur(5)
    cv.fill(sh, lit(DIRT * 0.9, 0.5), 0.8)
    if stone:
        cobbles(cv, m, seed=seed)
    else:
        X, Y = m.grid()
        cv.fill(m, lit(DIRT * (0.85 + (m.noise("m")[..., None] - 0.5) * 0.4), 0.6))
    return m


# =================================================================== the Dungeon Gate

GATE_STONE = C("#948678")
GATE_DARK = C("#8a7a74")


def stone_piece(cv, pts, albedo, rng, r=4.0, ndl_base=0.45, rim=True, tex=0.25):
    """One dressed stone (voussoir, cap, step...) with soft bevelled volume and speckle."""
    m = cv.poly(pts)
    lam = m.lambert(r)
    tone = rng.uniform(0.86, 1.1)
    n = m.noise("m") - 0.5
    col = lit(albedo * tone * (1 + n[..., None] * tex), ndl_base + lam * 0.6)
    col = col + (m.noise("f") - 0.5)[..., None] * 0.07
    cv.fill(m, col)
    if rim:
        rim_line(cv, m, C("#ffe1ae"), 1.4, 0.35, side=(1, 1))
    return m


def sconce_torch(cv, gl, x, y, s=1.0):
    iron = C("#2b2428")
    cv.fill(cv.rect(x - 7 * s, y + 20 * s, x + 7 * s, y + 34 * s, radius=2), lit(iron, 0.4))
    cv.fill(cv.line([(x, y + 26 * s), (x - 2 * s, y + 4 * s)], 5 * s), lit(C("#5a3a22"), 0.5))
    bowl = cv.poly([(x - 12 * s, y - 2 * s), (x + 12 * s, y - 2 * s), (x + 7 * s, y + 9 * s), (x - 7 * s, y + 9 * s)])
    cv.fill(bowl, lit(iron, 0.55))
    rim_line(cv, bowl, C("#ffb060"), 1.5, 0.8, side=(0, -1))
    flame(cv, gl, x - 1 * s, y, 0.9 * s, lean=0.05, spill=120 * s, spill_k=0.3)


def brazier(cv, gl, x, y, s=1.0, rng=None):
    """Stone pedestal with an iron fire bowl, standing on (x, y)."""
    rng = rng or random.Random(3)
    stone_piece(cv, [(x - 22 * s, y), (x + 22 * s, y), (x + 18 * s, y - 12 * s), (x - 18 * s, y - 12 * s)],
                GATE_STONE * 0.9, rng)
    stone_piece(cv, [(x - 13 * s, y - 12 * s), (x + 13 * s, y - 12 * s), (x + 11 * s, y - 58 * s),
                     (x - 11 * s, y - 58 * s)], GATE_STONE, rng, r=5)
    stone_piece(cv, [(x - 20 * s, y - 58 * s), (x + 20 * s, y - 58 * s), (x + 17 * s, y - 68 * s),
                     (x - 17 * s, y - 68 * s)], GATE_STONE * 0.95, rng)
    iron = C("#2d2629")
    bowl = cv.poly([(x - 30 * s, y - 88 * s)] + [(x + 30 * s * math.cos(math.pi * i / 10), y - 88 * s + 20 * s * math.sin(math.pi * i / 10)) for i in range(11)])
    lam = bowl.lambert(6)
    cv.fill(bowl, lit(iron, 0.3 + lam * 0.5))
    rim_line(cv, bowl, C("#ffae55"), 2, 0.9, side=(0, -1))
    cv.fill(cv.rect(x - 32 * s, y - 92 * s, x + 32 * s, y - 86 * s, radius=3), lit(C("#4a3b36"), 0.6))
    # embers heaped in the bowl
    emb = cv.ellipse(x, y - 90 * s, 27 * s, 6 * s)
    cv.fill(emb, C("#ffb040"))
    for _ in range(6):
        cv.fill(cv.ellipse(x + rng.uniform(-22, 22) * s, y - 91 * s, 4 * s, 2.5 * s), C("#fff0b0"))
    flame(cv, gl, x - 8 * s, y - 88 * s, 1.15 * s, lean=0.06, spill=0)
    flame(cv, gl, x + 9 * s, y - 88 * s, 0.95 * s, lean=0.1, spill=0)
    flame(cv, gl, x, y - 90 * s, 1.5 * s, lean=0.04, spill=180 * s, spill_k=0.3)


def dragon_keystone(cv, gl, x, y, s=1.0, rng=None):
    """A carved dragon skull keystone with ember eyes, hanging over the arch at (x, y)."""
    rng = rng or random.Random(9)
    st = GATE_STONE * 1.02
    # horns sweeping back
    for sd in (-1, 1):
        hm = cv.taper([(x + sd * 26 * s, y - 20 * s), (x + sd * 50 * s, y - 42 * s), (x + sd * 62 * s, y - 70 * s),
                       (x + sd * 56 * s, y - 88 * s)], 18 * s, 2 * s)
        lam = hm.lambert(5)
        cv.fill(hm, lit(st * 0.92, 0.4 + lam * 0.7))
        rim_line(cv, hm, C("#ffe1ae"), 1.2, 0.5)
    # skull
    pts = [(x - 40 * s, y - 32 * s), (x - 20 * s, y - 46 * s), (x + 20 * s, y - 46 * s), (x + 40 * s, y - 32 * s),
           (x + 38 * s, y + 4 * s), (x + 22 * s, y + 30 * s), (x + 12 * s, y + 52 * s), (x - 12 * s, y + 52 * s),
           (x - 22 * s, y + 30 * s), (x - 38 * s, y + 4 * s)]
    m = cv.poly(catmull(pts, 4, closed=True))
    lam = m.lambert(12)
    n = m.noise("m") - 0.5
    cv.fill(m, lit(st * (1 + n[..., None] * 0.2), 0.35 + lam * 0.8))
    # brow ridge, eye sockets, nostrils, fangs
    for sd in (-1, 1):
        sock = cv.poly([(x + sd * 8 * s, y - 8 * s), (x + sd * 30 * s, y - 18 * s), (x + sd * 30 * s, y - 2 * s),
                        (x + sd * 14 * s, y + 4 * s)], blur=0.8)
        cv.fill(sock, C("#1a1016"))
        glow(cv, x + sd * 21 * s, y - 7 * s, 9 * s, C("#ff5a1e"), 1.0, mode="over")
        cv.fill(cv.ellipse(x + sd * 21 * s, y - 7 * s, 4.5 * s, 2.6 * s), C("#fff0a0"))
        glow(gl, x + sd * 21 * s, y - 7 * s, 26 * s, C("#ff6a20"), 0.9, mode="addfree", core=0.8)
        brow = cv.taper([(x + sd * 6 * s, y - 12 * s), (x + sd * 22 * s, y - 24 * s), (x + sd * 38 * s, y - 20 * s)], 7 * s, 3 * s)
        cv.fill(brow, lit(st * 1.1, 0.9))
        cv.fill(cv.ellipse(x + sd * 6 * s, y + 34 * s, 3 * s, 4 * s), C("#241820"))
        fang = cv.poly([(x + sd * 10 * s, y + 46 * s), (x + sd * 16 * s, y + 46 * s), (x + sd * 12 * s, y + 66 * s)])
        cv.fill(fang, lit(C("#e8dcc4"), 0.8))
    rim_line(cv, m, C("#ffe1ae"), 1.6, 0.5)
    return m


def gate(cv, gl, rng):
    cx = 960
    base = 562          # threshold of the arch
    # recess shadow on the rock around the gate
    rec = cv.poly([(770, 590), (770, 250), (820, 205), (1100, 205), (1150, 250), (1150, 590)]).blur(18)
    cv.fill(rec, C("#2a2030"), 0.55, "atop")
    # ---- interior darkness with steps going down into the mountain
    op_l, op_r, spring, R = 872, 1048, 404, 88
    arch = [(op_l, base)] + [(cx - R * math.cos(math.pi * i / 24), spring - R * math.sin(math.pi * i / 24))
                             for i in range(25)] + [(op_r, base)]
    hole = cv.poly(arch)
    X, Y = hole.grid()
    dx = np.abs(X - cx) / R
    depth = np.clip(1 - dx, 0, 1) * sstep(base + 10, spring - 60, Y)
    col = lerp(C("#4a2c22"), C("#0b0610"), np.clip(depth * 1.5 + 0.2, 0, 1))
    cv.fill(hole, col)
    # descending steps inside, fading into the dark
    for i in range(6):
        y0 = base - 18 - i * 17
        w = 150 - i * 16
        stp = cv.rect(cx - w / 2, y0, cx + w / 2, y0 + 7)
        cv.fill(stp, lerp(C("#8a5a3c"), C("#140c14"), i / 5.5), 0.9)
    # a far ember glow deep inside
    glow(cv, cx, base - 120, 70, C("#b0301a"), 0.35, mode="over")
    glow(gl, cx, base - 120, 90, C("#ff4a1a"), 0.28, mode="addfree")
    # raised portcullis teeth at the top of the opening
    iron = C("#2c262a")
    for i in range(9):
        xx = op_l + 12 + i * (op_r - op_l - 24) / 8
        top = spring - math.sqrt(max(0, R * R - (xx - cx) ** 2)) + 4
        bar = cv.rect(xx - 3.5, top, xx + 3.5, spring - 36 + (i % 2) * 4)
        cv.fill(bar, lit(iron, 0.35))
        cv.fill(cv.poly([(xx - 5, spring - 36 + (i % 2) * 4), (xx + 5, spring - 36 + (i % 2) * 4),
                         (xx, spring - 22 + (i % 2) * 4)]), lit(iron, 0.5))
        rim_line(cv, bar, C("#ff9a50"), 1.2, 0.5, side=(1, 0))
    for yy in (spring - 70, spring - 46):
        cv.fill(cv.rect(op_l + 6, yy, op_r - 6, yy + 5) & hole, lit(iron, 0.35))
    # inner jambs (the thickness of the wall), lit by the torches
    for sd in (-1, 1):
        xj = op_l if sd < 0 else op_r
        jamb = cv.poly([(xj, base), (xj, spring), (xj - sd * 16, spring + 6), (xj - sd * 16, base - 4)])
        X, Y = jamb.grid()
        cv.fill(jamb, lerp(C("#8c6448"), C("#3a2630"), sstep(spring, base, Y) * 0.5 + 0.2))
    # ---- pillars (dressed stone)
    for x0, x1 in ((798, op_l), (op_r, 1122)):
        f = Face(cv, (x0, 318), (x1 - x0, 0), (0, base - 318), 30, 100, 0.5)
        m = f.mask()
        paint_stone_face(cv, f, m, GATE_STONE, seed=int(x0), bh=12, bw=18, dirt=0.4)
        # plinth and capital
        stone_piece(cv, [(x0 - 10, base + 2), (x1 + 10, base + 2), (x1 + 8, base - 30), (x0 - 8, base - 30)],
                    GATE_STONE * 0.92, rng, r=5)
        stone_piece(cv, [(x0 - 12, 330), (x1 + 12, 330), (x1 + 8, 312), (x0 - 8, 312)], GATE_STONE, rng, r=4)
    # ---- the arch ring of voussoirs
    n = 13
    r0, r1 = R, R + 42
    for i in range(n):
        a0 = math.pi * i / n
        a1 = math.pi * (i + 1) / n
        pts = []
        for a in np.linspace(a0, a1, 5):
            pts.append((cx - r1 * math.cos(a), spring - r1 * math.sin(a)))
        for a in np.linspace(a1, a0, 5):
            pts.append((cx - r0 * math.cos(a), spring - r0 * math.sin(a)))
        if i == n // 2:
            continue
        stone_piece(cv, pts, GATE_STONE * (0.95 if i % 2 else 1.02), rng, r=5, ndl_base=0.45)
    # spandrels and the entablature
    for sd in (-1, 1):
        pts = [(cx + sd * (R + 42), spring), (cx + sd * 162, spring), (cx + sd * 162, 262)]
        for a in np.linspace(math.pi / 2, 0, 12):
            pts.append((cx + sd * (R + 42) * math.cos(a), spring - (R + 42) * math.sin(a)))
        f = Face(cv, (cx - 162, 262), (324, 0), (0, spring - 262), 110, 45, 0.5)
        m = cv.poly(pts)
        paint_stone_face(cv, f, m, GATE_STONE * 0.93, seed=7 + sd, bh=12, bw=20, dirt=0.0)
    ent = Face(cv, (780, 222), (360, 0), (0, 44), 120, 15, 0.55)
    m = ent.mask()
    paint_stone_face(cv, ent, m, GATE_STONE * 1.05, seed=31, bh=15, bw=34, dirt=0.0)
    stone_piece(cv, [(770, 268), (1150, 268), (1146, 280), (774, 280)], GATE_STONE * 0.85, rng, r=3)
    stone_piece(cv, [(772, 224), (1148, 224), (1140, 210), (780, 210)], GATE_STONE * 1.08, rng, r=3)
    # glowing rune band on the entablature
    for i in range(15):
        rx = 812 + i * 21.5
        if abs(rx - cx) < 50:
            continue
        pts = [(rx - 5, 236), (rx + 5, 236), (rx + (rng.uniform(-5, 5)), 252), (rx - 4, 246)]
        rm = cv.line(pts[:rng.randint(2, 4)], 2.2)
        cv.fill(rm, C("#ffc070"))
        gl.fill(rm.blur(1.0), C("#ff9a40"), 1.0, "addfree")
        gl.fill(rm.blur(5.0), C("#ff7a2a"), 0.6, "addfree")
    # crest: stepped stones and horn-like spires on the corners
    for sd in (-1, 1):
        xs = cx + sd * 175
        spire = [(xs - 20, 212), (xs + 20, 212), (xs + 8, 150), (xs + sd * 6, 120), (xs - 8, 150)]
        stone_piece(cv, spire, GATE_STONE * 0.98, rng, r=6)
    dragon_keystone(cv, gl, cx, 296, 1.0, rng)
    # ivy over the corners of the gate
    for (x, y, ln, sd) in [(790, 214, 140, -1), (1130, 214, 170, 1), (840, 214, 60, -1), (1085, 214, 80, 1)]:
        items = []
        px, py = x, y
        for k in range(int(ln / 7)):
            px += rng.uniform(-3, 3) + sd * 0.4
            py += 7
            for _ in range(2):
                items.append((px + rng.uniform(-9, 9), py + rng.uniform(-5, 5), rng.uniform(4, 7), rng.uniform(3, 5)))
        for _ in range(14):
            items.append((x + rng.uniform(-40, 40), y + rng.uniform(-8, 10), rng.uniform(6, 10), rng.uniform(4, 7)))
        im = cv.dabs(items)
        lam = im.lambert(4, precise=False)
        cv.fill(im, lerp(C("#243e2b"), C("#a7bf55"), sstep(-0.3, 0.9, lam + (im.noise("s") - 0.5) * 0.8)))
    # ---- steps down to the plaza
    for i in range(4):
        y0 = base + i * 14
        w = 350 + i * 34
        top = cv.poly([(cx - w / 2, y0), (cx + w / 2, y0), (cx + w / 2 + 10, y0 + 6), (cx - w / 2 - 10, y0 + 6)])
        f = Face(cv, (cx - w / 2 - 10, y0), (w + 20, 0), (0, 6), 120, 3, 0.75)
        paint_stone_face(cv, f, top, GATE_STONE * 1.05, seed=40 + i, bh=30, bw=26, dirt=0)
        rs = cv.rect(cx - w / 2 - 10, y0 + 6, cx + w / 2 + 10, y0 + 14)
        f = Face(cv, (cx - w / 2 - 10, y0 + 6), (w + 20, 0), (0, 8), 120, 8, 0.25)
        paint_stone_face(cv, f, rs, GATE_STONE * 0.85, seed=50 + i, bh=9, bw=24, dirt=0)
    sconce_torch(cv, gl, 835, 400)
    sconce_torch(cv, gl, 1085, 400)
    brazier(cv, gl, 770, 614, 1.0, rng)
    brazier(cv, gl, 1150, 614, 1.0, rng)
    HOT["gate"] = {"rect": [790, 118, 340, 500], "label": [960, 640]}


# =================================================================== building kit

WOOD = C("#7a5234")
WOOD_D = C("#4e3322")
PLASTER = C("#e8d6b4")
SLATE = C("#56617a")
TERRACOTTA = C("#b85a3a")
STONE_W = C("#a39486")
IRON = C("#2f2a2e")


def beam(cv, p0, p1, w, ndl, col=None, rim=False):
    col = WOOD_D if col is None else col
    m = cv.line([p0, p1], w)
    h, ww = m.a.shape
    grain = m.noise("s")
    cv.fill(m, lit(col * (0.8 + grain[..., None] * 0.4), ndl))
    if rim:
        rim_line(cv, m, C("#ffd7a0"), 1.0, 0.4, side=(-1, -1))
    return m


class House:
    """Oblique box with a gable roof.

    front face: x0..x1 at ground g, wall height wh. D = depth vector (dx, dy) for the visible side
    (dx > 0: the right side shows; dx < 0: the left side shows). ridge='depth' puts the gable on the
    front (ridge runs back along D); ridge='front' puts the ridge parallel to the front (gable on the side)."""

    def __init__(self, cv, x0, x1, g, wh, D, rh, ov=12, ridge="depth", sun_side=None):
        self.cv, self.x0, self.x1, self.g, self.wh, self.D, self.rh, self.ov, self.ridge = cv, x0, x1, g, wh, D, rh, ov, ridge
        D = np.array(D, np.float32)
        top = g - wh
        self.front = Face(cv, (x0, top), (x1 - x0, 0), (0, wh), (x1 - x0) / 4, wh / 4, 0.45)
        side_ndl = 0.0 if D[0] > 0 else 0.75
        if D[0] > 0:
            self.side = Face(cv, (x1, top), D, (0, wh), abs(D[0]) * 2.2 / 4, wh / 4, side_ndl)
        else:
            self.side = Face(cv, (x0 + D[0], top + D[1]), -D, (0, wh), abs(D[0]) * 2.2 / 4, wh / 4, side_ndl)
        self.top = top

    def walls(self, paint_front, paint_side):
        paint_side(self.side, self.side.mask())
        paint_front(self.front, self.front.mask())

    def gable_roof(self, paint_gable, paint_roof, trim=None):
        """ridge along D: gable triangle on the front face, the roof slope on the D side visible."""
        cv, D, ov = self.cv, np.array(self.D, np.float32), self.ov
        x0, x1, top, rh = self.x0, self.x1, self.top, self.rh
        xm = (x0 + x1) / 2
        apex = np.array((xm, top - rh), np.float32)
        el = np.array((x0 - ov, top + ov * 0.55), np.float32)
        er = np.array((x1 + ov, top + ov * 0.55), np.float32)
        near, far = (er, el) if D[0] > 0 else (el, er)
        Dx = D * (1 + ov / max(1.0, float(np.hypot(*D))))
        front_off = -D / max(1.0, float(np.hypot(*D))) * ov * 0.6
        # far slope (a sliver behind the gable)
        fr = Face(cv, apex + front_off, Dx, far - apex, float(np.hypot(*D)) / 3, rh / 3, 0.75 if D[0] > 0 else 0.25)
        paint_roof(fr, fr.mask())
        # gable triangle (front wall material)
        gm = cv.poly([(x0, top + 1), (x1, top + 1), (xm, top - rh + 3)])
        gf = Face(cv, (x0, top - rh), (x1 - x0, 0), (0, rh), (x1 - x0) / 4, rh / 4, self.front.ndl)
        paint_gable(gf, gm)
        shadow(cv, gm.shift(0, 0), 0, 6, 5, 0.5)
        # near slope
        nr = Face(cv, apex + front_off, Dx, near - apex, float(np.hypot(*D)) / 3, rh / 3, 0.2 if D[0] > 0 else 0.8)
        paint_roof(nr, nr.mask())
        self.roof_near, self.roof_far, self.apex = nr, fr, apex
        # bargeboards along the gable
        tc = WOOD_D if trim is None else trim
        for e in (el, er):
            m = cv.line([tuple(apex + front_off), tuple(e + front_off * 0.2)], 7)
            cv.fill(m, lit(tc, 0.5))
            rim_line(cv, m, C("#ffdca0"), 1.2, 0.5, side=(0, -1))
        return nr

    def side_gable_roof(self, paint_gable, paint_roof, depth_frac=0.5, trim=None):
        """ridge parallel to the front: roof front slope over the front wall, gable on the D side."""
        cv, D, ov = self.cv, np.array(self.D, np.float32), self.ov
        x0, x1, top, rh = self.x0, self.x1, self.top, self.rh
        half = D * depth_frac
        ridge_off = half + np.array((0, -rh), np.float32)
        if D[0] > 0:
            g0, g1 = np.array((x1, top)), np.array((x1, top)) + D
        else:
            g0, g1 = np.array((x0, top)), np.array((x0, top)) + D
        apex = g0 + ridge_off
        # back slope (a sliver behind the gable) and the gable on the side
        back_eave = g1 + np.array((0, ov * 0.6)) + (g1 - g0) / max(1.0, float(np.hypot(*(g1 - g0)))) * ov
        bk = Face(cv, apex, np.array((x1 - x0 + ov, 0), np.float32), back_eave - apex, (x1 - x0) / 3, rh / 2.4, 0.3)
        paint_roof(bk, bk.mask())
        gm = cv.poly([tuple(g0), tuple(g1), tuple(apex)])
        paint_gable(self.side, gm)
        shadow(cv, gm, 0, 5, 5, 0.5)
        tc0 = WOOD_D if trim is None else trim
        m = cv.line([tuple(apex), tuple(back_eave)], 7)
        cv.fill(m, lit(tc0, 0.6))
        rim_line(cv, m, C("#ffdca0"), 1.2, 0.5, side=(0, -1))
        # front slope
        o = np.array((x0 - ov, top + ov * 0.6), np.float32) + np.array((-ov * 0.0, 0))
        a = np.array((x1 - x0 + 2 * ov, 0), np.float32)
        b = ridge_off - np.array((0, ov * 0.6))
        fr = Face(cv, o + b, a, -b, (x1 - x0) / 3, rh / 2.4, 0.55)
        m = fr.mask()
        paint_roof(fr, m)
        tc = WOOD_D if trim is None else trim
        m2 = cv.line([fr.pt(0, 1), fr.pt(1, 1)], 6)
        cv.fill(m2, lit(tc, 0.35))
        m3 = cv.line([fr.pt(0, 0), fr.pt(1, 0)], 7)
        cv.fill(m3, lit(tc, 0.7))
        rim_line(cv, m3, C("#ffdca0"), 1.5, 0.7, side=(0, -1))
        self.roof_front = fr
        return fr


def chimney(cv, x, y_base, y_top, w, D, rng, smoke=True):
    """Stone chimney: front + side face, a cap, standing with its foot hidden in the roof."""
    Dn = np.array(D, np.float32) * (w * 0.6 / max(1.0, float(np.hypot(*D))))
    f = Face(cv, (x, y_top), (w, 0), (0, y_base - y_top), w / 4, (y_base - y_top) / 4, 0.55)
    if Dn[0] > 0:
        sf = Face(cv, (x + w, y_top), Dn, (0, y_base - y_top), 4, (y_base - y_top) / 4, 0.05)
    else:
        sf = Face(cv, (x + Dn[0], y_top + Dn[1]), -Dn, (0, y_base - y_top), 4, (y_base - y_top) / 4, 0.8)
    paint_stone_face(cv, sf, sf.mask(), STONE_W, seed=77, bh=6, bw=9)
    paint_stone_face(cv, f, f.mask(), STONE_W, seed=78, bh=6, bw=9)
    cap = cv.poly([(x - 4, y_top), (x + w + 4, y_top), (x + w + 4 + Dn[0], y_top + Dn[1]), (x - 4 + Dn[0], y_top + Dn[1])])
    cv.fill(cap, lit(STONE_W * 0.7, 0.6))
    top = cv.poly([(x + 2, y_top - 1), (x + w - 2, y_top - 1), (x + w - 2 + Dn[0] * 0.8, y_top + Dn[1] * 0.8), (x + 2 + Dn[0] * 0.8, y_top + Dn[1] * 0.8)])
    cv.fill(top, C("#1c1418"))
    return (x + w / 2 + Dn[0] / 2, y_top + Dn[1] / 2)


def roof_tiles(albedo, rows=9, per=1.0, scallop=True, moss=0.0):
    def fn(face, m):
        paint_tiles(face.cv, face, m, albedo, rows=rows, per=per, scallop=scallop, moss=moss)
    return fn


def stone_wall(albedo, bh=9, bw=15, seed=1, dirt=0.3):
    def fn(face, m):
        paint_stone_face(face.cv, face, m, albedo, seed=seed, bh=bh, bw=bw, dirt=dirt)
    return fn


def plaster_wall(albedo):
    def fn(face, m):
        paint_plaster(face.cv, face, m, albedo)
    return fn


def plank_wall(albedo, width=5.0, vertical=True):
    def fn(face, m):
        paint_planks(face.cv, face, m, albedo, width=width, vertical=vertical)
    return fn


def timber_frame(cv, face, rows, cols, w=6.0, diag=True, col=None):
    """Dark timber posts and rails over a plaster face."""
    ndl = face.ndl
    for i in range(cols + 1):
        u = i / cols
        beam(cv, face.pt(u, 0), face.pt(u, 1), w, ndl, col)
    for j in range(rows + 1):
        v = j / rows
        beam(cv, face.pt(0, v), face.pt(1, v), w, ndl, col)
    if diag:
        for i in range(cols):
            u0, u1 = i / cols, (i + 1) / cols
            if i % 2 == 0:
                beam(cv, face.pt(u0, 1 / rows if rows > 1 else 1), face.pt(u1, 0), w * 0.8, ndl, col)


def ground_shadow(cv, pts, blur=10, strength=0.5):
    m = cv.poly(pts).blur(blur)
    cv.fill(m, C("#1f2a33"), strength, "atop")


def door(cv, face, u0, u1, v0, arched=True, col=None, gl=None, open_=0.0):
    col = WOOD if col is None else col
    (xa, ya), (xb, yb) = face.pt(u0, v0), face.pt(u1, v0)
    (xc, yc), (xd, yd) = face.pt(u1, 1), face.pt(u0, 1)
    pts = [(xa, ya), (xb, yb), (xc, yc), (xd, yd)]
    if arched:
        r = (xb - xa) / 2
        arch = [((xa + xb) / 2 - r * math.cos(math.pi * i / 12), (ya + yb) / 2 - r * 0.8 * math.sin(math.pi * i / 12))
                for i in range(13)]
        pts = arch + [(xc, yc), (xd, yd)]
    frame = cv.poly([(x + (x - (xa + xb) / 2) * 0.16, y - (4 if y < yc - 5 else 0)) for x, y in pts])
    cv.fill(frame, lit(STONE_W * 0.8, face.ndl + 0.1))
    m = cv.poly(pts)
    X, Y = m.grid()
    k = np.floor((X - xa) / max(1, (xb - xa)) * 4)
    cv.fill(m, lit(col * (0.85 + _hash(k, k, 3)[..., None] * 0.3), face.ndl * 0.7))
    for i in range(1, 4):
        x = xa + (xb - xa) * i / 4
        cv.fill(cv.line([(x, min(p[1] for p in pts) + 4), (x, yc)], 1.4), C("#2a1a12"), 0.7)
    for yy in (ya + (yc - ya) * 0.25, ya + (yc - ya) * 0.75):
        cv.fill(cv.line([(xa + 3, yy), (xb - 3, yy)], 3.5), lit(IRON, 0.5))
    cv.fill(cv.ellipse(xa + (xb - xa) * 0.78, (ya + yc) / 2, 2.5, 2.5), C("#d6b060"))
    shadow(cv, m, 0, 0, 3, 0.25)
    return m


# =================================================================== props

def barrel(cv, x, y, s=1.0, water=False, lid=True):
    """Upright barrel standing on (x, y)."""
    w, h = 26 * s, 40 * s
    pts = [(x - w * 0.86, y), (x - w, y - h * 0.5), (x - w * 0.86, y - h), (x + w * 0.86, y - h), (x + w, y - h * 0.5),
           (x + w * 0.86, y)]
    m = cv.poly(catmull(pts, 4, closed=False) + [(x + w * 0.86, y), (x - w * 0.86, y)])
    X, Y = m.grid()
    k = np.floor((X - x + w) / (w / 3.5))
    lam = m.lambert(w * 0.5)
    col = lit(WOOD * (0.85 + _hash(k, k, 1)[..., None] * 0.3), 0.25 + lam * 0.9)
    cv.fill(m, col)
    for yy in (y - h * 0.18, y - h * 0.82):
        hoop = cv.rect(x - w * 0.97, yy - 2.5 * s, x + w * 0.97, yy + 2.5 * s) & m
        cv.fill(hoop, lit(IRON, 0.3 + 0.4))
    top = cv.ellipse(x, y - h, w * 0.86, w * 0.3)
    cv.fill(top, lit(WOOD * 0.9, 0.8) if not water else C("#6f8ea8"))
    if water:
        cv.fill(cv.ellipse(x - w * 0.3, y - h - 1, w * 0.3, w * 0.08), C("#dfeaf0"), 0.8)
    rim_line(cv, m, C("#ffd49a"), 1.4, 0.5, side=(-1, 0))
    shadow_ground(cv, x + 10 * s, y, w * 1.4, 6 * s)
    return m


def shadow_ground(cv, x, y, rx, ry, strength=0.45):
    m = cv.ellipse(x, y, rx, ry, blur=ry * 0.8)
    cv.fill(m, C("#1c2430"), strength, "atop")


def crate(cv, x, y, s=1.0, D=(10, -6)):
    w, h = 34 * s, 28 * s
    f = Face(cv, (x - w / 2, y - h), (w, 0), (0, h), 8, 7, 0.5)
    Dv = np.array(D, np.float32) * s
    if Dv[0] > 0:
        sf = Face(cv, (x + w / 2, y - h), Dv, (0, h), 3, 7, 0.1)
    else:
        sf = Face(cv, (x - w / 2 + Dv[0], y - h + Dv[1]), -Dv, (0, h), 3, 7, 0.8)
    top = cv.poly([(x - w / 2, y - h), (x + w / 2, y - h), (x + w / 2 + Dv[0], y - h + Dv[1]), (x - w / 2 + Dv[0], y - h + Dv[1])])
    paint_planks(cv, sf, sf.mask(), WOOD * 1.1, 2.0, False)
    paint_planks(cv, f, f.mask(), WOOD * 1.1, 2.2, False)
    cv.fill(top, lit(WOOD * 1.15, 0.85))
    for p0, p1 in [((0, 0), (1, 1)), ((0, 0), (0, 1)), ((1, 0), (1, 1)), ((0, 0), (1, 0)), ((0, 1), (1, 1))]:
        beam(cv, f.pt(*p0), f.pt(*p1), 3.5 * s, 0.45, WOOD * 0.8)
    shadow_ground(cv, x + 8 * s, y, w * 0.8, 5 * s)


def anvil(cv, x, y, s=1.0):
    """Anvil on a stump; (x, y) is the stump's foot."""
    st = cv.poly([(x - 20 * s, y), (x + 20 * s, y), (x + 16 * s, y - 30 * s), (x - 16 * s, y - 30 * s)])
    lam = st.lambert(6)
    cv.fill(st, lit(WOOD * 0.9, 0.3 + lam * 0.6))
    cv.fill(cv.ellipse(x, y - 30 * s, 16 * s, 5 * s), lit(C("#c09a6a"), 0.7))
    body = cv.poly([(x - 34 * s, y - 50 * s), (x + 24 * s, y - 50 * s), (x + 42 * s, y - 46 * s), (x + 24 * s, y - 40 * s),
                    (x + 12 * s, y - 40 * s), (x + 8 * s, y - 32 * s), (x + 14 * s, y - 28 * s), (x - 14 * s, y - 28 * s),
                    (x - 8 * s, y - 32 * s), (x - 12 * s, y - 40 * s), (x - 26 * s, y - 42 * s)])
    lam = body.lambert(4)
    cv.fill(body, lit(C("#3a3a44"), 0.25 + lam * 0.8))
    face = cv.rect(x - 32 * s, y - 52 * s, x + 26 * s, y - 48 * s)
    cv.fill(face, C("#c9d0d8"))
    rim_line(cv, body, C("#ffb070"), 1.6, 0.9, side=(1, 0))
    # a glowing blade resting on it
    bl = cv.taper([(x - 20 * s, y - 55 * s), (x + 20 * s, y - 56 * s)], 5 * s, 2 * s)
    cv.fill(bl, C("#ffb040"))
    return body


def sword_rack(cv, x, y, s=1.0, n=4):
    """A wooden rack with swords leaning in it; (x, y) its foot left."""
    for i in range(n):
        bx = x + i * 13 * s
        blade = cv.taper([(bx, y - 4 * s), (bx + 4 * s, y - 70 * s)], 6 * s, 2 * s)
        cv.fill(blade, lit(C("#c4ccd6"), 0.3 + 0.1 * i))
        rim_line(cv, blade, C("#fff4d8"), 1.0, 0.7, side=(-1, 0))
        cv.fill(cv.line([(bx - 6 * s, y - 70 * s), (bx + 12 * s, y - 72 * s)], 3.5 * s), lit(C("#c8a040"), 0.6))
        cv.fill(cv.line([(bx + 3 * s, y - 72 * s), (bx + 4 * s, y - 88 * s)], 3.5 * s), lit(WOOD_D, 0.4))
        cv.fill(cv.ellipse(bx + 4 * s, y - 90 * s, 3.2 * s, 3.2 * s), lit(C("#d0a848"), 0.7))
    beam(cv, (x - 8 * s, y - 30 * s), (x + (n * 13 + 4) * s, y - 32 * s), 5 * s, 0.5, WOOD)
    beam(cv, (x - 6 * s, y), (x - 6 * s, y - 36 * s), 5 * s, 0.4, WOOD)
    beam(cv, (x + (n * 13 + 2) * s, y), (x + (n * 13 + 2) * s, y - 38 * s), 5 * s, 0.4, WOOD)


def smithy(cv, gl, rng, fx):
    g = 700
    hs = House(cv, 72, 292, g, 170, (118, -50), 120, ov=14)
    ground_shadow(cv, [(292, g), (410, g - 50), (520, g - 20), (470, g + 30), (300, g + 16)], 12, 0.45)
    hs.walls(stone_wall(C("#9f9084"), 8, 14, seed=3), stone_wall(C("#9f9084"), 8, 14, seed=4))
    # the forge mouth on the front wall
    f = hs.front
    (ax, ay), (bx, by) = f.pt(0.16, 0.34), f.pt(0.84, 0.34)
    r = (bx - ax) / 2
    arch = [((ax + bx) / 2 - r * math.cos(math.pi * i / 16), ay - r * 0.55 * math.sin(math.pi * i / 16)) for i in range(17)]
    mouth = arch + [f.pt(0.84, 1.0), f.pt(0.16, 1.0)]
    frame = cv.poly([(x + (x - (ax + bx) / 2) * 0.12, y - 8) for x, y in arch] + [(bx + 12, g), (ax - 12, g)])
    stone_piece(cv, [(x, y) for x, y in cv_pts(frame_poly(arch, ax, bx, g))], C("#8f8176"), rng, r=4)
    m = cv.poly(mouth)
    X, Y = m.grid()
    cx = (ax + bx) / 2
    d = np.sqrt(((X - cx) / (r * 1.1)) ** 2 + ((Y - (g - 30)) / 70) ** 2)
    col = lerp(C("#ff9a40"), C("#2a1410"), sstep(0.0, 0.95, d))
    cv.fill(m, col)
    # hearth, coals and the hood inside
    hearth = cv.rect(cx - 55, g - 42, cx + 55, g)
    lam = hearth.lambert(6)
    cv.fill(hearth, lit(C("#6a5a54"), 0.2 + lam * 0.4) + C("#ff7a2a") * 0.35)
    coals = cv.ellipse(cx, g - 44, 50, 9)
    cv.fill(coals, C("#ff9a30"))
    for _ in range(14):
        cv.fill(cv.ellipse(cx + rng.uniform(-44, 44), g - 45 + rng.uniform(-3, 3), 4, 2.5), C("#fff2b0"))
    flame(cv, gl, cx - 12, g - 44, 1.0, lean=0.05, spill=0)
    flame(cv, gl, cx + 16, g - 44, 0.8, lean=0.1, spill=0)
    hood = cv.poly([(cx - 62, g - 118), (cx + 62, g - 118), (cx + 30, ay - r * 0.5 + 6), (cx - 30, ay - r * 0.5 + 6)])
    cv.fill(hood & m, lit(C("#4a3e3c"), 0.2) + C("#ff8a3a") * 0.15)
    gl.fill(m.blur(2), C("#ff9040"), 0.22, "addfree")
    glow(gl, cx, g - 50, 170, C("#ff7a28"), 0.38, mode="addfree")
    glow(gl, cx, g - 46, 60, C("#fff0c0"), 0.5, mode="addfree")
    glow(cv, cx, g - 20, 220, C("#ff8a3a"), 0.25, mode="add")
    fx.setdefault("sparks", []).append([int(cx - 50), int(g - 110), 100, 70])
    # side window
    window(cv, gl, hs.side.quad(0.3, 0.3, 0.62, 0.6), bars=2)
    hs.gable_roof(stone_wall(C("#9f9084"), 8, 14, seed=5), roof_tiles(SLATE, rows=10, per=0.8, scallop=False, moss=0.6))
    # a round vent in the gable
    vx, vy = (hs.x0 + hs.x1) / 2, hs.top - 48
    cv.fill(cv.ellipse(vx, vy, 17, 17), lit(C("#8f8176"), 0.6))
    cv.fill(cv.ellipse(vx, vy, 12, 12), C("#2a1810"))
    glow(cv, vx, vy, 12, C("#ff8a3a"), 0.6, mode="over")
    # chimney on the near slope, smoking
    top = chimney(cv, 244, 392, 300, 40, (118, -50), rng)
    fx.setdefault("smoke", []).append([int(top[0]), int(top[1] - 4)])
    # the yard: anvil, quench barrel, sword rack, coal
    sword_rack(cv, 318, 712, 0.95)
    anvil(cv, 130, 742, 1.0)
    barrel(cv, 255, 740, 0.9, water=True)
    barrel(cv, 40, 716, 0.85)
    coal = cv.dabs([(420 + rng.uniform(-24, 24), 718 + rng.uniform(-6, 2), rng.uniform(5, 9), rng.uniform(4, 6)) for _ in range(26)])
    lam = coal.lambert(4)
    cv.fill(coal, lit(C("#2a2528"), 0.2 + lam * 0.6))
    HOT["smith"] = {"rect": [20, 288, 418, 470], "label": [236, 772]}


def frame_poly(arch, ax, bx, g):
    cx = (ax + bx) / 2
    outer = [(cx + (x - cx) * 1.2, y - 12) for x, y in arch]
    inner = list(reversed(arch))
    return outer + [(bx + 14, g), (bx, g)] + inner + [(ax, g), (ax - 14, g)]


def cv_pts(p):
    return p


def emblem(cv, kind, x, y, s, col):
    """Class emblems for the banners: sword, staff, daggers."""
    parts = []
    if kind == "sword":
        parts.append(cv.taper([(x, y + 26 * s), (x, y - 30 * s)], 7 * s, 1.5 * s))
        parts.append(cv.line([(x - 12 * s, y + 14 * s), (x + 12 * s, y + 14 * s)], 3.5 * s))
        parts.append(cv.line([(x, y + 16 * s), (x, y + 30 * s)], 3.5 * s))
        parts.append(cv.ellipse(x, y + 33 * s, 3.5 * s, 3.5 * s))
    elif kind == "staff":
        parts.append(cv.line([(x - 2 * s, y + 32 * s), (x + 2 * s, y - 14 * s)], 3.5 * s))
        parts.append(cv.ellipse(x + 2 * s, y - 22 * s, 8 * s, 8 * s))
        for a in range(0, 360, 60):
            r = math.radians(a)
            parts.append(cv.line([(x + 2 * s + math.cos(r) * 11 * s, y - 22 * s + math.sin(r) * 11 * s),
                                  (x + 2 * s + math.cos(r) * 15 * s, y - 22 * s + math.sin(r) * 15 * s)], 2 * s))
    else:
        for sd in (-1, 1):
            parts.append(cv.taper([(x - sd * 12 * s, y + 22 * s), (x + sd * 12 * s, y - 22 * s)], 5 * s, 1 * s))
            parts.append(cv.line([(x - sd * 14 * s - 5 * s, y + 12 * s), (x - sd * 5 * s, y + 18 * s)], 3 * s))
    m = parts[0]
    for p in parts[1:]:
        m = m | p
    return m


def banner(cv, gl, x, top, w, h, cloth, kind, rng):
    """A hanging cloth banner with a gold emblem, soft folds and a swallow-tail hem."""
    pts = [(x - w / 2, top), (x + w / 2, top), (x + w / 2 + 2, top + h), (x, top + h - 18), (x - w / 2 - 2, top + h)]
    m = cv.poly(pts)
    X, Y = m.grid()
    folds = np.sin((X - x) / w * 9.0 + (Y - top) / h * 1.5) * 0.5 + 0.5
    ndl = 0.25 + folds * 0.45 + sstep(x + w / 2, x - w / 2, X) * 0.2
    col = lit(cloth * (0.9 + (m.noise("m")[..., None] - 0.5) * 0.2), ndl)
    cv.fill(m, col)
    # gold trim
    trim = cv.rect(x - w / 2, top + h * 0.06, x + w / 2, top + h * 0.1) | cv.line([(x - w / 2 + 3, top + 6), (x - w / 2 + 3, top + h - 4)], 2.5) | cv.line([(x + w / 2 - 3, top + 6), (x + w / 2 - 1, top + h - 4)], 2.5)
    cv.fill(trim & m, lit(C("#e0b050"), 0.7))
    em = emblem(cv, kind, x, top + h * 0.5, w / 60, C("#f0c860"))
    cv.fill(em, lit(C("#f0c050"), 0.9))
    rim_line(cv, em, C("#fff4c0"), 0.8, 0.8, side=(-1, -1))
    rim_line(cv, m, C("#ffd8a0"), 1.4, 0.5, side=(-1, 0))
    # pole
    beam(cv, (x - w / 2 - 8, top), (x + w / 2 + 8, top), 5, 0.6, C("#6a4a2a"))
    for sd in (-1, 1):
        cv.fill(cv.ellipse(x + sd * (w / 2 + 9), top, 4.5, 4.5), lit(C("#d4a848"), 0.8))
    return m


def column(cv, x, top, bottom, w, rng, albedo=None):
    albedo = STONE_W * 1.08 if albedo is None else albedo
    m = cv.rect(x - w / 2, top, x + w / 2, bottom)
    X, Y = m.grid()
    u = (X - (x - w / 2)) / w
    ndl = 0.9 - u * 0.9 + np.sin(u * math.pi * 6) * 0.08
    cv.fill(m, lit(albedo * (0.95 + (m.noise("m")[..., None] - 0.5) * 0.2), ndl))
    stone_piece(cv, [(x - w / 2 - 6, top), (x + w / 2 + 6, top), (x + w / 2 + 4, top + 10), (x - w / 2 - 4, top + 10)], albedo, rng, r=3)
    stone_piece(cv, [(x - w / 2 - 7, bottom), (x + w / 2 + 7, bottom), (x + w / 2 + 5, bottom - 12), (x - w / 2 - 5, bottom - 12)], albedo * 0.95, rng, r=3)


def training_dummy(cv, x, y, s=1.0):
    beam(cv, (x, y), (x, y - 70 * s), 6 * s, 0.5, WOOD)
    beam(cv, (x - 26 * s, y - 52 * s), (x + 26 * s, y - 54 * s), 5 * s, 0.5, WOOD)
    body = cv.ellipse(x, y - 50 * s, 17 * s, 22 * s)
    lam = body.lambert(7)
    cv.fill(body, lit(C("#c8a060"), 0.3 + lam * 0.7))
    for yy in (-60, -44):
        cv.fill(cv.line([(x - 16 * s, y + yy * s), (x + 16 * s, y + (yy + 2) * s)], 2 * s) & body, lit(C("#6a4a2a"), 0.4))
    head = cv.ellipse(x, y - 82 * s, 11 * s, 12 * s)
    lam = head.lambert(5)
    cv.fill(head, lit(C("#d0aa6a"), 0.3 + lam * 0.7))
    cv.fill(cv.poly([(x - 16 * s, y - 88 * s), (x + 16 * s, y - 88 * s), (x + 8 * s, y - 100 * s), (x - 8 * s, y - 100 * s)]),
            lit(C("#8a8f99"), 0.6))
    rim_line(cv, body, C("#ffd8a0"), 1.2, 0.6, side=(1, 0))
    shadow_ground(cv, x + 12 * s, y, 26 * s, 5 * s)


def class_master(cv, gl, rng, fx):
    g = 872
    hs = House(cv, 470, 706, g, 176, (86, -37), 110, ov=14)
    ground_shadow(cv, [(706, g), (792, g - 37), (880, g - 10), (820, g + 26), (700, g + 16)], 12, 0.45)
    hs.walls(stone_wall(C("#aa9c8e"), 9, 16, seed=11), stone_wall(C("#aa9c8e"), 9, 16, seed=12))
    f = hs.front
    # foundation plinth
    stone_piece(cv, [(466, g + 4), (710, g + 4), (710, g - 12), (466, g - 12)], C("#8e8276"), rng, r=3)
    # tall windows on the side, a great door in front
    window(cv, gl, hs.side.quad(0.25, 0.22, 0.6, 0.55), bars=2)
    door(cv, f, 0.38, 0.62, 0.48)
    hs.gable_roof(stone_wall(C("#aa9c8e"), 9, 16, seed=13), roof_tiles(C("#4d6a96"), rows=11, per=0.8, scallop=True))
    # pediment emblem: a round shield with crossed blades
    cx = (hs.x0 + hs.x1) / 2
    sh = cv.ellipse(cx, hs.top - 40, 24, 24)
    lam = sh.lambert(6)
    cv.fill(sh, lit(C("#c89a3a"), 0.3 + lam * 0.8))
    cv.fill(cv.ellipse(cx, hs.top - 40, 17, 17), lit(C("#7a2a26"), 0.5))
    cv.fill(emblem(cv, "daggers", cx, hs.top - 40, 0.6, None), lit(C("#f0d080"), 0.9))
    # portico: two columns and a cornice over the door
    cornice = [(cx - 76, hs.top + 70), (cx + 76, hs.top + 70), (cx + 70, hs.top + 84), (cx - 70, hs.top + 84)]
    for xx in (cx - 62, cx + 62):
        column(cv, xx, hs.top + 84, g - 12, 18, rng)
    stone_piece(cv, cornice, STONE_W * 1.05, rng, r=3)
    # three class banners: sword, staff, daggers
    banner(cv, gl, hs.x0 + 30, hs.top + 16, 40, 118, C("#a8262a"), "sword", rng)
    banner(cv, gl, hs.x1 - 30, hs.top + 16, 40, 118, C("#2a4aa0"), "staff", rng)
    sf = hs.side
    p0, p1 = sf.pt(0.72, 0.1), sf.pt(0.72, 0.1)
    banner(cv, gl, p0[0], p0[1] + 4, 30, 100, C("#2f7a3a"), "daggers", rng)
    lantern(cv, gl, cx - 90, hs.top + 104, 0.9)
    lantern(cv, gl, cx + 90, hs.top + 104, 0.9)
    training_dummy(cv, 748, 900, 0.9)
    HOT["class_master"] = {"rect": [444, 525, 342, 370], "label": [612, 904]}


def awning(cv, x0, x1, y0, depth, drop, c1, c2, stripes=8, scallop=True):
    """A striped cloth awning sloping out from a wall: top edge at y0, front edge lower by `drop`."""
    pts = [(x0, y0), (x1, y0), (x1 + depth * 0.2, y0 + drop), (x0 - depth * 0.2, y0 + drop)]
    m = cv.poly(pts)
    X, Y = m.grid()
    t = (Y - y0) / drop
    xl = x0 - depth * 0.2 * t
    xr = x1 + depth * 0.2 * t
    u = (X - xl) / np.maximum(1, xr - xl)
    k = np.floor(u * stripes)
    col = np.where((k % 2 == 0)[..., None], c1, c2)
    ndl = 0.45 + t * 0.35 + np.sin(u * stripes * math.pi) * 0.08
    cv.fill(m, lit(col * (0.95 + (m.noise("m")[..., None] - 0.5) * 0.15), ndl))
    # scalloped valance
    items = []
    n = stripes * 2
    for i in range(n):
        u0 = (i + 0.5) / n
        xx = (x0 - depth * 0.2) + (x1 - x0 + depth * 0.4) * u0
        items.append((xx, y0 + drop, (x1 - x0 + depth * 0.4) / n / 2 + 0.5, 9))
    val = cv.dabs(items) | cv.rect(x0 - depth * 0.2, y0 + drop - 6, x1 + depth * 0.2, y0 + drop)
    X, Y = val.grid()
    u = (X - (x0 - depth * 0.2)) / (x1 - x0 + depth * 0.4)
    k = np.floor(u * stripes)
    col = np.where((k % 2 == 0)[..., None], c1, c2)
    cv.fill(val, lit(col, 0.3))
    rim_line(cv, m, C("#ffe0b0"), 1.5, 0.6, side=(0, -1))
    return m


def potions(cv, gl, x0, x1, y, rng, rows=1, big=1.0):
    cols = [C("#3ad06a"), C("#e2463a"), C("#4a8aff"), C("#c05ae0"), C("#ffc23a"), C("#40d8d0")]
    x = x0
    while x < x1:
        c = rng.choice(cols)
        h = rng.uniform(14, 22) * big
        w = h * rng.uniform(0.45, 0.6)
        body = cv.ellipse(x, y - w * 0.6, w * 0.6, w * 0.6) | cv.rect(x - w * 0.18, y - h, x + w * 0.18, y - w)
        cv.fill(body, c * 0.55)
        liq = cv.ellipse(x, y - w * 0.5, w * 0.52, w * 0.45)
        cv.fill(liq, c)
        cv.fill(cv.ellipse(x - w * 0.22, y - w * 0.8, w * 0.12, w * 0.2), C("#ffffff"), 0.85)
        cv.fill(cv.rect(x - w * 0.2, y - h - 3, x + w * 0.2, y - h + 1), lit(C("#8a5a30"), 0.7))
        glow(gl, x, y - w * 0.5, w * 1.6, c, 0.5, mode="addfree")
        x += w * 1.35 + rng.uniform(0, 3)


def hanging_sign(cv, gl, x, y, s, draw_icon, bg=None):
    """A wooden sign hanging from an iron bracket; draw_icon(cx, cy, s) paints the emblem."""
    beam(cv, (x - 4, y - 30 * s), (x + 50 * s, y - 30 * s), 4 * s, 0.5, IRON)
    for dx in (12, 38):
        cv.fill(cv.line([(x + dx * s, y - 30 * s), (x + dx * s, y - 20 * s)], 1.6), lit(IRON, 0.5))
    board = cv.rect(x + 2 * s, y - 20 * s, x + 48 * s, y + 20 * s, radius=5 * s)
    lam = board.lambert(5)
    cv.fill(board, lit((WOOD * 1.1) if bg is None else bg, 0.35 + lam * 0.6))
    rim_line(cv, board, C("#ffe0a0"), 1.4, 0.6, side=(-1, -1))
    draw_icon(x + 25 * s, y, s)


def merchant(cv, gl, rng, fx):
    g = 872
    hs = House(cv, 1214, 1452, g, 184, (-86, -37), 112, ov=14)
    ground_shadow(cv, [(1452, g), (1520, g - 8), (1560, g + 20), (1450, g + 26)], 10, 0.4)
    def front_wall(face, m):
        paint_plaster(cv, face, m, PLASTER)
    hs.walls(front_wall, front_wall)
    f, sd = hs.front, hs.side
    # stone ground floor course
    for face in (sd, f):
        m = face.mask(0, 0.62, 1, 1)
        paint_stone_face(cv, face, m, C("#a89888"), seed=21, bh=8, bw=13, dirt=0.3)
    timber_frame(cv, sd, 2, 3, 6)
    timber_frame(cv, f, 2, 4, 6)
    # upper windows with flower boxes
    for face, u0, u1 in ((f, 0.14, 0.36), (f, 0.64, 0.86), (sd, 0.3, 0.7)):
        window(cv, gl, face.quad(u0, 0.12, u1, 0.4), bars=2)
        bx = face.quad(u0 - 0.02, 0.4, u1 + 0.02, 0.46)
        cv.fill(cv.poly(bx), lit(WOOD, 0.5))
        fl = [(bx[0][0] + (bx[1][0] - bx[0][0]) * rng.random(), bx[0][1] - rng.uniform(0, 7), 3.2, 3) for _ in range(14)]
        leaves = cv.dabs([(a, b + 2, 5, 3.5) for a, b, _, _ in fl])
        cv.fill(leaves, lit(C("#4a7a34"), 0.6))
        cv.fill(cv.dabs(fl), rng.choice([C("#ff6a8a"), C("#ffd24a"), C("#e05ad0")]))
    # shop counter under the awning, potions everywhere
    (sx0, sy0), (sx1, _) = f.pt(0.06, 0.6), f.pt(0.94, 0.6)
    shop = cv.rect(sx0, sy0, sx1, g - 30)
    cv.fill(shop, C("#3a2420"))
    glow(cv, (sx0 + sx1) / 2, sy0 + 30, 110, C("#ffb060"), 0.5, mode="add")
    gl.fill(shop.blur(3), C("#ffb060"), 0.25, "addfree")
    for yy in (sy0 + 18, sy0 + 40):
        beam(cv, (sx0 + 4, yy), (sx1 - 4, yy), 3.5, 0.5, WOOD)
        potions(cv, gl, sx0 + 12, sx1 - 12, yy - 1, rng, big=0.8)
    counter = Face(cv, (sx0 - 6, g - 34), (sx1 - sx0 + 12, 0), (0, 34), 40, 8, 0.45)
    paint_planks(cv, counter, counter.mask(), WOOD * 1.05, 2.2, True)
    beam(cv, (sx0 - 8, g - 34), (sx1 + 8, g - 34), 6, 0.8, WOOD * 1.1)
    potions(cv, gl, sx0 + 8, sx1 - 8, g - 37, rng, big=1.15)
    awning(cv, sx0 - 10, sx1 + 10, sy0 - 26, 60, 40, C("#7a3aa8"), C("#f0c24a"), stripes=9)
    hs.gable_roof(front_wall, roof_tiles(TERRACOTTA, rows=10, per=0.9, scallop=True, moss=0.3))
    gx, gy = (hs.x0 + hs.x1) / 2, hs.top - 38
    window(cv, gl, [(gx - 14, gy - 8), (gx + 14, gy - 8), (gx + 14, gy + 20), (gx - 14, gy + 20)], arched=True, bars=1)

    def potion_icon(x, y, s):
        b = cv.ellipse(x, y + 4 * s, 11 * s, 11 * s) | cv.rect(x - 4 * s, y - 14 * s, x + 4 * s, y)
        cv.fill(b, C("#2f9a4a"))
        cv.fill(cv.ellipse(x, y + 6 * s, 9 * s, 7 * s), C("#5af07a"))
        cv.fill(cv.ellipse(x - 4 * s, y + 1 * s, 2 * s, 3 * s), C("#ffffff"), 0.8)
        glow(gl, x, y + 4 * s, 22 * s, C("#40ff80"), 0.5, mode="addfree")

    hanging_sign(cv, gl, hs.x1 + 2, hs.top + 44, 1.0, potion_icon)
    # wares outside
    crate(cv, 1490, 900, 1.0, (-10, -6))
    crate(cv, 1478, 872, 0.8, (-10, -6))
    barrel(cv, 1180, 896, 0.8)
    potions(cv, gl, 1462, 1510, 873, rng, big=0.9)
    HOT["merchant"] = {"rect": [1134, 525, 374, 370], "label": [1330, 904]}


def market_stall(cv, gl, x, g, w, c1, c2, goods, rng):
    """A small market stall: posts, a striped canopy and a table of goods; (x, g) is its front-left foot."""
    h = 74
    for xx in (x + 4, x + w - 4):
        beam(cv, (xx, g), (xx, g - h), 5, 0.45, WOOD)
    table = Face(cv, (x - 4, g - 30), (w + 8, 0), (0, 30), 30, 8, 0.45)
    paint_planks(cv, table, table.mask(), WOOD, 2.5, True)
    top = cv.poly([(x - 8, g - 34), (x + w + 8, g - 34), (x + w + 2, g - 28), (x - 2, g - 28)])
    cv.fill(top, lit(WOOD * 1.2, 0.8))
    if goods == "apples":
        items = [(x + 10 + rng.uniform(0, w - 20), g - 38 - rng.uniform(0, 6), 5, 5) for _ in range(int(w / 5))]
        m = cv.dabs(items)
        lam = m.lambert(3)
        cv.fill(m, lit(C("#d8382a"), 0.4 + lam * 0.6))
        cv.fill(cv.dabs([(a - 1.6, b - 1.6, 1.3, 1.3) for a, b, _, _ in items]), C("#ffe0c0"), 0.8)
    elif goods == "gear":
        for i in range(int(w / 22)):
            xx = x + 14 + i * 22
            sh = cv.ellipse(xx, g - 48, 10, 13)
            lam = sh.lambert(4)
            cv.fill(sh, lit(rng.choice([C("#8a95a8"), C("#b08a4a"), C("#7a4a3a")]), 0.3 + lam * 0.8))
            rim_line(cv, sh, C("#fff0d0"), 1, 0.7, side=(-1, -1))
    elif goods == "scrolls":
        for i in range(int(w / 12)):
            xx = x + 8 + i * 12
            m = cv.rect(xx - 4, g - 46 - (i % 3) * 3, xx + 4, g - 34, radius=3)
            cv.fill(m, lit(C("#efe0bc"), 0.7))
            cv.fill(cv.rect(xx - 4.5, g - 42, xx + 4.5, g - 40), C("#b8302a"))
    awning(cv, x - 6, x + w + 6, g - h - 22, 30, 26, c1, c2, stripes=6)


def notice_board(cv, x, g, rng):
    for xx in (x - 40, x + 40):
        beam(cv, (xx, g), (xx, g - 110), 7, 0.45, WOOD)
    board = Face(cv, (x - 46, g - 104), (92, 0), (0, 60), 24, 16, 0.5)
    paint_planks(cv, board, board.mask(), WOOD * 1.1, 3, False)
    roofm = cv.poly([(x - 56, g - 102), (x, g - 128), (x + 56, g - 102), (x + 50, g - 98), (x, g - 120), (x - 50, g - 98)])
    cv.fill(roofm, lit(WOOD_D, 0.6))
    for i in range(6):
        px, py = x - 36 + (i % 3) * 26 + rng.uniform(-3, 3), g - 96 + (i // 3) * 26 + rng.uniform(-3, 3)
        m = cv.poly([(px - 9, py), (px + 10, py - 1), (px + 11, py + 20), (px - 8, py + 21)])
        cv.fill(m, lit(C("#f2e6c8") * rng.uniform(0.85, 1.0), 0.8))
        for k in range(3):
            cv.fill(cv.line([(px - 5, py + 5 + k * 5), (px + 6, py + 5 + k * 5)], 1.0), C("#6a5a4a"), 0.6)
        cv.fill(cv.ellipse(px, py + 2, 2, 2), C("#c0302a"))


def inn(cv, gl, rng, fx):
    g = 708
    hs = House(cv, 1592, 1894, g, 214, (-92, -40), 122, ov=16, ridge="front")
    ground_shadow(cv, [(1500, g - 40), (1592, g), (1592, g + 24), (1470, g + 10)], 10, 0.3)

    def wall(face, m):
        paint_plaster(cv, face, m, C("#eedcb8"))
    hs.walls(wall, wall)
    f, sd = hs.front, hs.side
    for face in (sd, f):
        m = face.mask(0, 0.55, 1, 1)
        paint_stone_face(cv, face, m, C("#a49482"), seed=31, bh=9, bw=15, dirt=0.35)
    timber_frame(cv, f, 1, 6, 6, diag=True)
    beam(cv, f.pt(0, 0.55), f.pt(1, 0.55), 9, 0.6, WOOD_D)
    beam(cv, sd.pt(0, 0.55), sd.pt(1, 0.55), 9, 0.8, WOOD_D)
    timber_frame(cv, Face(cv, sd.pt(0, 0), sd.a, sd.b * 0.55, 4, 4, sd.ndl), 1, 2, 6, diag=True)
    # upper windows
    for i in range(3):
        u0 = 0.08 + i * 0.32
        window(cv, gl, f.quad(u0 + 0.03, 0.12, u0 + 0.17, 0.42), bars=2)
    window(cv, gl, sd.quad(0.3, 0.12, 0.7, 0.42), bars=2)
    # ground floor: big bay window, the door with lanterns
    window(cv, gl, f.quad(0.06, 0.66, 0.34, 0.9), bars=3)
    window(cv, gl, f.quad(0.72, 0.66, 0.94, 0.9), bars=2)
    window(cv, gl, sd.quad(0.25, 0.66, 0.7, 0.9), bars=2)
    dm = door(cv, f, 0.43, 0.61, 0.6, arched=True)
    lantern(cv, gl, f.pt(0.39, 0.62)[0], f.pt(0.39, 0.62)[1], 0.9)
    lantern(cv, gl, f.pt(0.65, 0.62)[0], f.pt(0.65, 0.62)[1], 0.9)
    # warm light spilling from the door crack
    gx, gy = f.pt(0.52, 0.95)
    glow(gl, gx, gy, 50, C("#ffae50"), 0.4, mode="addfree")
    hs.side_gable_roof(wall, roof_tiles(C("#b4553a"), rows=9, per=0.9, scallop=True, moss=0.4))
    # dormer window on the roof
    fr = hs.roof_front
    for u in (0.3, 0.72):
        p = fr.pt(u, 0.55)
        dm_ = cv.poly([(p[0] - 28, p[1] + 26), (p[0] + 28, p[1] + 26), (p[0] + 28, p[1] - 8), (p[0], p[1] - 34), (p[0] - 28, p[1] - 8)])
        df = Face(cv, (p[0] - 28, p[1] - 34), (56, 0), (0, 60), 14, 15, 0.5)
        paint_plaster(cv, df, dm_, C("#eedcb8"))
        window(cv, gl, [(p[0] - 13, p[1] - 4), (p[0] + 13, p[1] - 4), (p[0] + 13, p[1] + 20), (p[0] - 13, p[1] + 20)], bars=2)
        rf = cv.poly([(p[0] - 36, p[1] - 4), (p[0], p[1] - 40), (p[0] + 36, p[1] - 4), (p[0] + 30, p[1] + 2), (p[0], p[1] - 30), (p[0] - 30, p[1] + 2)])
        cv.fill(rf, lit(C("#9a4630"), 0.6))
        rim_line(cv, rf, C("#ffdca0"), 1.4, 0.7, side=(0, -1))
    top = chimney(cv, 1800, 420, 318, 38, (-92, -40), rng)
    fx.setdefault("smoke", []).append([int(top[0]), int(top[1] - 4)])

    def tankard_icon(x, y, s):
        b = cv.rect(x - 9 * s, y - 10 * s, x + 7 * s, y + 13 * s, radius=2 * s)
        lam = b.lambert(4)
        cv.fill(b, lit(C("#c89040"), 0.3 + lam * 0.8))
        foam = cv.dabs([(x - 6 * s, y - 11 * s, 5 * s, 4 * s), (x, y - 13 * s, 6 * s, 5 * s), (x + 5 * s, y - 11 * s, 4 * s, 4 * s)])
        cv.fill(foam, lit(C("#fff6e0"), 0.9))
        hd = cv.line([(x + 7 * s, y - 5 * s), (x + 14 * s, y - 3 * s), (x + 14 * s, y + 6 * s), (x + 7 * s, y + 8 * s)], 3 * s)
        cv.fill(hd, lit(C("#8a6030"), 0.6))

    sgx, sgy = f.pt(0.0, 0.5)
    hanging_sign(cv, gl, sgx - 52, sgy, 1.1, tankard_icon)
    # the adventurers' market in front
    notice_board(cv, 1540, 760, rng)
    market_stall(cv, gl, 1612, 796, 100, C("#b8322c"), C("#f0e2c4"), "apples", rng)
    market_stall(cv, gl, 1774, 796, 110, C("#2c5aa8"), C("#f0e2c4"), "gear", rng)
    barrel(cv, 1880, 806, 0.8)
    crate(cv, 1744, 806, 0.8, (-8, -5))
    HOT["inn"] = {"rect": [1512, 290, 404, 520], "label": [1716, 826]}


# =================================================================== scene assembly

def cast_shadow(cv, b, g, k=0.34, shear=1.1, strength=0.55, blur=5.0):
    """Projects the silhouette of building canvas b onto the ground of cv: the low sun behind the
    village throws it toward the viewer and to the right (flipped at ground line g, squashed by k)."""
    s = cv.ss
    A = b.px[..., 3]
    rows = np.nonzero(A.max(axis=1) > 0.05)[0]
    cols = np.nonzero(A.max(axis=0) > 0.05)[0]
    if len(rows) == 0:
        return
    G = int(g * s)
    y0 = rows[0]
    x0, x1 = cols[0], cols[-1] + 1
    hmax = G - y0
    n = int(hmax * k)
    extra = int(hmax * shear) + 2
    out = np.zeros((n, x1 - x0 + extra), np.float32)
    yo = np.arange(n)
    src = (G - yo / k).astype(int)
    src = np.clip(src, 0, A.shape[0] - 1)
    heights = (G - src)
    for i in range(n):
        dx = int(heights[i] * shear * 0.25)
        row = A[src[i], x0:x1]
        out[i, dx:dx + (x1 - x0)] = np.maximum(out[i, dx:dx + (x1 - x0)], row)
    # fade with distance from the base
    fade = np.linspace(1.0, 0.35, n)[:, None]
    m = Mask(cv, out * fade, x0, G - 2)
    cv.fill(m.blur(blur), C("#1d2638"), strength, "atop")


def building(cv, fn, gl, rng, fx, g, shadow_k=0.34, strength=0.55):
    b = Canvas(cv.w, cv.h, cv.ss, cv.seed)
    b._noise = cv._noise
    fn(b, gl, rng, fx)
    cast_shadow(cv, b, g, k=shadow_k, strength=strength)
    cv.composite(b)
    del b


def lamp_post(cv, gl, x, y, s=1.0):
    beam(cv, (x, y), (x, y - 96 * s), 6 * s, 0.4, IRON)
    cv.fill(cv.rect(x - 7 * s, y - 8 * s, x + 7 * s, y, radius=2), lit(IRON, 0.4))
    beam(cv, (x, y - 92 * s), (x + 20 * s, y - 94 * s), 3.5 * s, 0.5, IRON)
    cv.fill(cv.line([(x + 18 * s, y - 94 * s), (x + 18 * s, y - 86 * s)], 1.5), lit(IRON, 0.5))
    lantern(cv, gl, x + 18 * s, y - 72 * s, 0.9 * s)
    shadow_ground(cv, x + 6 * s, y, 12 * s, 3 * s)


def fence(cv, pts, rng, h=30, post_every=34):
    """Wooden rail fence along a polyline (posts + two rails)."""
    c = catmull(pts, 6)
    xs = np.array([p[0] for p in c])
    ys = np.array([p[1] for p in c])
    x = xs[0]
    posts = []
    while x <= xs[-1]:
        posts.append((x, float(np.interp(x, xs, ys))))
        x += post_every
    for (xa, ya), (xb, yb) in zip(posts, posts[1:]):
        for f in (0.35, 0.72):
            beam(cv, (xa, ya - h * f), (xb, yb - h * f), 4.5, 0.55, C("#8a6440"))
    for (px, py) in posts:
        m = cv.taper([(px, py + 2), (px, py - h - 4)], 7, 6)
        cv.fill(m, lit(C("#7a5634") * rng.uniform(0.85, 1.1), 0.45))
        rim_line(cv, m, C("#ffd8a0"), 1.2, 0.6, side=(-1, 0))
        shadow_ground(cv, px + 6, py, 8, 2.5, 0.35)


def flowers(cv, x0, y0, x1, y1, n, rng, cols=None, size=2.6):
    cols = cols or [C("#ffd24a"), C("#ff7aa0"), C("#ffffff"), C("#b67aff"), C("#ff5a4a")]
    for c in cols:
        items = []
        for _ in range(n // len(cols)):
            items.append((rng.uniform(x0, x1), rng.uniform(y0, y1), size * rng.uniform(0.7, 1.3), size * rng.uniform(0.6, 1.0)))
        if not items:
            continue
        m = cv.dabs(items)
        cv.fill(m, lit(c, 0.7))
        cv.fill(cv.dabs([(a - s * 0.3, b - s * 0.3, s * 0.45, s * 0.4) for a, b, s, _ in items]), lerp(c, C("#ffffff"), 0.6), 0.8)


def plaza_and_paths(cv, rng):
    # side paths (dirt) to the doors
    for pts, ws in [([(830, 700), (600, 712), (330, 716), (182, 722)], [70, 60, 56, 60]),
                    ([(1090, 700), (1330, 716), (1560, 722), (1740, 724)], [70, 60, 56, 60]),
                    ([(900, 880), (760, 890), (600, 884)], [60, 54, 56]),
                    ([(1020, 880), (1160, 890), (1330, 884)], [60, 54, 56])]:
        path(cv, pts, ws, rng, stone=False)
    # the plaza before the gate steps and the winding main road
    pl = cv.ellipse(960, 664, 300, 64).blur(2)
    cv.fill(pl.blur(5), lit(DIRT * 0.9, 0.5), 0.8)
    cobbles(cv, pl, seed=8)
    path(cv, [(930, 1090), (952, 980), (985, 860), (962, 760), (960, 660)], [250, 215, 190, 180, 200], rng, seed=6)


def town_layer(seed=4):
    t0 = time.time()
    cv = Canvas(W, H, 2, 5)
    gl = Canvas(W, H, 2, 6)
    rng = random.Random(seed)
    fx = {}
    back_hills(cv, rng)
    # woods behind the village, at the sides of the mountain
    for x, y, s, lean in [(1450, 560, 0.62, 0.1), (1370, 590, 0.55, -0.1)]:
        tree(cv, x, y, s, rng, hz=0.18, lean=lean)
    for x, y, s in [(560, 560, 0.5), (620, 590, 0.45), (1320, 580, 0.5)]:
        conifer(cv, x, y, s, rng, hz=0.22)
    cliff(cv, rng)
    cliff_greenery(cv, rng)
    for x, y, s, lean in [(650, 620, 0.62, -0.2), (1270, 624, 0.66, 0.2), (80, 560, 1.0, 0.1), (1880, 552, 1.0, -0.1),
                          (470, 610, 0.72, 0.1), (1500, 600, 0.6, 0.0)]:
        tree(cv, x, y, s, rng, hz=0.08, lean=lean)
    print("  backdrop %.1fs" % (time.time() - t0))
    ground(cv, rng)
    plaza_and_paths(cv, rng)
    # bushes at the foot of the mountain
    for x, y, w, h in [(700, 640, 120, 50), (1230, 640, 130, 50), (590, 650, 90, 44), (1340, 650, 100, 44)]:
        bush(cv, x, y, w, h, rng, flowers=C("#ffd24a") if x < 900 else C("#ff8ab0"))
    gate(cv, gl, rng)
    print("  gate %.1fs" % (time.time() - t0))
    building(cv, smithy, gl, rng, fx, 700)
    building(cv, inn, gl, rng, fx, 708)
    print("  back row %.1fs" % (time.time() - t0))
    # hedges and flowers between the rows
    for x, y, w, h, fl in [(440, 760, 120, 46, C("#ff7aa0")), (40, 780, 140, 50, C("#ffd24a")), (1500, 820, 90, 40, None),
                           (300, 790, 110, 42, C("#ffffff")), (1880, 830, 110, 46, C("#ff5a4a"))]:
        bush(cv, x, y, w, h, rng, flowers=fl)
    flowers(cv, 20, 770, 420, 840, 90, rng)
    flowers(cv, 1560, 830, 1900, 880, 60, rng)
    building(cv, class_master, gl, rng, fx, 872)
    building(cv, merchant, gl, rng, fx, 872)
    print("  front row %.1fs" % (time.time() - t0))
    for x, y in [(862, 780), (1066, 780), (842, 930), (1092, 930)]:
        lamp_post(cv, gl, x, y, 1.0)
    fence(cv, [(20, 900), (200, 910), (380, 920)], rng)
    fence(cv, [(1560, 925), (1740, 912), (1910, 905)], rng)
    for x, y, w, h, fl in [(130, 960, 180, 70, C("#ffd24a")), (1780, 960, 190, 70, C("#ff8ab0")), (760, 990, 120, 60, C("#ffffff")),
                           (1170, 996, 130, 60, C("#b67aff"))]:
        bush(cv, x, y, w, h, rng, flowers=fl)
    flowers(cv, 0, 930, 780, 1080, 160, rng, size=3.4)
    flowers(cv, 1140, 930, 1920, 1080, 160, rng, size=3.4)
    grass_tufts(cv, 0, 940, 820, 1080, 70, rng, h=22)
    grass_tufts(cv, 1100, 940, 1920, 1080, 70, rng, h=22)
    grass_tufts(cv, 0, 700, 1920, 930, 60, rng, h=14)
    print("  foreground %.1fs" % (time.time() - t0))
    grade(cv)
    fx.setdefault("sparks", [])
    return cv, gl, fx


def grade(cv):
    """Golden-hour grade over the village: the low sun's haze bleeding over everything near it,
    the foreground sinking into cool shade, and a soft darkening toward the lower corners."""
    m = cv.full()
    X, Y = m.grid()
    d = np.hypot(X - SUN[0], (Y - SUN[1]) * 1.3)
    warm = np.clip(1 - d / 1300, 0, 1) ** 2
    cv.fill(m, C("#ffcf8a"), warm * 0.22, "atop")
    shade_amt = sstep(820, 1080, Y) * 0.32 + (np.hypot((X - 960) / 1100, (Y - 560) / 620) - 0.75).clip(0, 1) * 0.5
    cv.fill(m, C("#2a3050"), np.clip(shade_amt, 0, 0.55), "atop")
    haze = sstep(700, 420, Y) * 0.12
    cv.fill(m, HAZE, haze, "atop")


# =================================================================== light shafts

def rays_layer(seed=21):
    """Additive golden-hour shafts fanning down-right from the low sun, a soft bloom around it and
    a warm wash on the near meadow. Stored as rgb = hue, alpha = strength (blend ADD)."""
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xs - SUN[0], ys - SUN[1]
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.degrees(np.arctan2(dy, dx))
    acc = np.zeros((H, W), np.float32)
    # a fan of shafts between 5 and 75 degrees below the horizontal (pointing into the village)
    for a, wd, k in [(8, 3.0, 0.45), (15, 2.0, 0.6), (21, 4.5, 0.5), (29, 2.2, 0.7), (36, 5.5, 0.45),
                     (44, 2.5, 0.65), (52, 4.0, 0.5), (60, 2.0, 0.55), (68, 5.0, 0.35), (-2, 6.0, 0.3)]:
        d = (ang - a + 180) % 360 - 180
        acc += np.exp(-(d / wd) ** 2) * k
    fade = sstep(60, 260, r) * (1 - sstep(500, 1700, r))
    n = fbm(H, W, 150, 3, seed)
    acc = acc * fade * np.clip(0.55 + n * 0.9, 0.2, 1.6)
    # bloom around the sun and a wash over the plaza and the meadow
    bloom = np.clip(1 - r / 480, 0, 1) ** 2.4 * 0.3
    wash = np.exp(-(((xs - 760) / 900) ** 2 + ((ys - 760) / 260) ** 2)) * 0.07
    strength = np.clip(acc * 0.24 + bloom + wash, 0, 1)
    col = np.empty((H, W, 3), np.float32)
    warm = np.clip(r / 1500, 0, 1)[..., None]
    col[:] = lerp(C("#fff2cc"), C("#ffb866"), warm)
    out = np.concatenate([col, strength[..., None]], axis=-1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


# =================================================================== foreground framing

NEAR_PAL = (C("#0e1a16"), C("#22402a"), C("#5f7f34"), C("#d9d07a"))


def near_layer(seed=31):
    """Out-of-focus framing leaves: a branch hanging into the top-left corner across the sun (its
    leaves backlit and glowing at the edges), a smaller one at the top right, and ferns and tall
    grass in both bottom corners under the button bar. Everything else stays transparent."""
    cv = Canvas(W, H, 2, seed)
    rng = random.Random(seed)
    dark, mid, lt, hi = NEAR_PAL
    # --- top-left branch across the sun
    br = trunk(cv, [(-30, 40), (120, 62), (260, 70), (380, 58)], 26, 6, C("#2a2026"))
    trunk(cv, [(140, 64), (210, 110), (250, 150)], 9, 3, C("#2a2026"))
    clumps = [(30, 10, 70, -0.4), (110, 40, 60, -0.2), (200, 30, 52, 0.0), (300, 54, 46, 0.2),
              (240, 130, 40, 0.1), (370, 50, 30, 0.3), (60, 100, 54, -0.3), (-10, 150, 60, -0.5),
              (170, 90, 44, 0.0)]
    # smaller clumps filling the gaps, and drooping tips along the twigs
    for (x0, y0, x1, y1, k) in [(-20, 0, 380, 90, 14), (120, 80, 260, 170, 6), (-30, 120, 80, 230, 5)]:
        for _ in range(k):
            clumps.append((rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(18, 32), rng.uniform(-0.4, 0.3)))
    clumps.sort(key=lambda c: -c[2])
    for (x, y, R, b) in clumps:
        leaf_clump(cv, x, y, R, rng, bias=b, pal=NEAR_PAL, leaf=max(4.0, R * 0.2), rim=1.0)
    # --- top-right: a smaller sprig
    trunk(cv, [(1960, 30), (1840, 46), (1760, 40)], 18, 5, C("#2a2026"))
    for (x, y, R, b) in [(1930, 20, 64, -0.5), (1860, 52, 50, -0.3), (1790, 36, 38, -0.1), (1905, 110, 46, -0.5)]:
        leaf_clump(cv, x, y, R, rng, bias=b, pal=NEAR_PAL, leaf=R * 0.22, rim=0.7)
    # --- bottom corners: ferns and tall grass
    def fern(x, y, length, angle, s=1.0):
        pts = []
        for i in range(9):
            t = i / 8
            a = math.radians(angle) + t * 0.9 * (1 if angle > -90 else -1)
            pts.append((x + math.cos(math.radians(angle)) * length * t + t * t * length * 0.25 * (1 if angle > -90 else -1),
                        y + math.sin(math.radians(angle)) * length * t + t * t * length * 0.45))
        cv.fill(cv.line(pts, 2.5 * s), lit(C("#2a3a22"), 0.3))
        items = []
        for i in range(1, len(pts) - 1):
            t = i / (len(pts) - 1)
            (xa, ya), (xb, yb) = pts[i - 1], pts[i + 1]
            ddx, ddy = xb - xa, yb - ya
            ln = math.hypot(ddx, ddy) or 1
            nx, ny = -ddy / ln, ddx / ln
            lw = (1 - t) * 34 * s + 6
            for sd in (-1, 1):
                for k in range(3):
                    u = (k + 0.5) / 3
                    px = xa + ddx * u * 0.5 + nx * sd * lw * 0.6
                    py = ya + ddy * u * 0.5 + ny * sd * lw * 0.6 + lw * 0.2
                    items.append((px, py, lw * 0.55, lw * 0.22))
        m = cv.dabs(items)
        lam = m.lambert(10, precise=False)
        t = np.clip(sstep(-0.3, 0.9, lam) * 0.8 + (m.noise("s") - 0.5) * 0.5, 0, 1)
        cv.fill(m, np.where((t < 0.5)[..., None], lerp(dark, mid, t * 2), lerp(mid, lt * 0.8, (t - 0.5) * 2)))
        rim_line(cv, m, C("#e8d080"), 1.6, 0.5, side=(1, 0.3))
    for (x, y, l, a, s) in [(-20, 1100, 330, -60, 1.1), (40, 1110, 280, -38, 1.0), (120, 1120, 220, -75, 0.9),
                            (-30, 1000, 260, -20, 1.0)]:
        fern(x, y, l, a, s)
    for (x, y, l, a, s) in [(1940, 1100, 320, -120, 1.1), (1880, 1115, 260, -140, 1.0), (1800, 1120, 200, -100, 0.9),
                            (1950, 1010, 250, -160, 1.0)]:
        fern(x, y, l, a, s)
    for (x, y, R, b) in [(-10, 1060, 90, -0.6), (90, 1080, 70, -0.4), (1930, 1060, 90, -0.6), (1830, 1085, 70, -0.5),
                         (180, 1100, 60, -0.3), (1740, 1100, 60, -0.4)]:
        leaf_clump(cv, x, y, R, rng, bias=b, pal=NEAR_PAL, leaf=R * 0.2, rim=0.8)
    for (x0, x1) in ((0, 300), (1640, 1920)):
        grass_tufts(cv, x0, 1040, x1, 1090, 26, rng, h=70, col=C("#13241a"), lit_col=C("#6f8a3a"))
    # depth of field: the framing is out of focus
    px = cv.px
    for c in range(4):
        px[..., c] = gblur(px[..., c], 3.0 * cv.ss)
    # a slight cool-dark grade, they are in shadow against the sunlit village
    a = px[..., 3:4]
    px[..., :3] = px[..., :3] * 0.82 + a * C("#0e1420") * 0.06
    return cv


# =================================================================== write the town

def compose(far, town, rays, glow_im, near):
    def f(im):
        return np.asarray(im, np.float32) / 255.0
    base = f(far)[..., :3]
    a = f(town)
    base = a[..., :3] * a[..., 3:] + base * (1 - a[..., 3:])
    for im in (rays, glow_im):
        a = f(im)
        base = base + a[..., :3] * a[..., 3:]
    a = f(near)
    base = a[..., :3] * a[..., 3:] + base * (1 - a[..., 3:])
    return Image.fromarray((np.clip(base, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def make_town():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    print("far")
    cv = far_layer()
    far = cv.image().convert("RGB")
    del cv
    save(far, os.path.join(OUT, "far.png"))
    print("town (%.0fs)" % (time.time() - t0))
    HOT.clear()
    cv, gl, fx = town_layer()
    town = cv.image()
    del cv
    glow_im = gl.image()
    del gl
    save(town, os.path.join(OUT, "town.png"))
    save(glow_im, os.path.join(OUT, "glow.png"))
    print("rays and near (%.0fs)" % (time.time() - t0))
    rays = rays_layer()
    save(rays, os.path.join(OUT, "rays.png"))
    cv = near_layer()
    near = cv.image()
    del cv
    save(near, os.path.join(OUT, "near.png"))
    hot = {k: HOT[k] for k in ("gate", "smith", "merchant", "class_master", "inn")}
    with open(os.path.join(OUT, "hotspots.json"), "w") as f:
        json.dump(hot, f, indent=1)
    fx = dict(fx)
    fx["leaves"] = [[0, 120, 520, 560], [1380, 160, 540, 520], [0, 0, 420, 260]]
    fx["birds"] = True
    fx["torches"] = [[834, 380], [1084, 380], [770, 500], [1150, 500]]
    fx["embers"] = [[814, 300, 40, 70], [1064, 300, 40, 70], [745, 420, 50, 80], [1125, 420, 50, 80]]
    fx["sun"] = [int(SUN[0]), int(SUN[1])]
    fx["size"] = [W, H]
    fx["layers"] = {"far": "far.png", "town": "town.png", "rays": "rays.png (add)",
                    "glow": "glow.png (add, pulse)", "near": "near.png"}
    with open(os.path.join(OUT, "fx.json"), "w") as f:
        json.dump(fx, f, indent=1)
    print("  wrote hotspots.json, fx.json")
    flat = compose(far, town, rays, glow_im, near)
    flat.save(os.path.join(ROOT, "assets", "town", "v2.jpg"), quality=90)
    print("  wrote assets/town/v2.jpg  (%.0fs)" % (time.time() - t0))
    return flat


# =================================================================== NPC busts
#
# The busts reuse the painted-part kit of the hero rigs (tools/art/heroes_v2.py: Part masks at 2x,
# the skin / cloth / hair / metal materials, anime eyes and hair masses) so the town people match
# the heroes. One Part covers the whole 768 x 768 canvas. Faces are built in a head frame F(x, y)
# (the hero head units, scaled by k) turned three quarters to the right.

NPC_IDS = ["nara", "smith", "merchant", "innkeeper", "keeper", "class_master"]
BUST = 768


def _hv():
    sys.path.insert(0, HERE)
    import heroes_v2 as hv
    hv.GRADE = None
    if not getattr(hv.Part, "_cropped", False):
        hv.Part.paint = _cropped_paint(hv, hv.Part.paint)
        hv.Part._cropped = True
    return hv


def _cropped_paint(hv, orig):
    """Part.paint restricted to the mask's bounding box (plus room for its cast shadow). The
    result is the same (blurs of a mask that is zero outside the box are exact) but a small
    part on a full bust canvas paints many times faster."""
    def paint(self, m, mat_, bump=None, hgt=None, **kw):
        ys = np.nonzero(m.max(axis=1) > 1e-3)[0]
        xs = np.nonzero(m.max(axis=0) > 1e-3)[0]
        if len(xs) == 0:
            return None
        md = dict(mat_)
        md.update(kw)
        pad = int(hv.SS * (max(abs(md.get("cast_dx", 3)), abs(md.get("cast_dy", 5))) + md.get("cast_soft", 4) * 3.5)) + 8
        y0, y1 = max(0, ys[0] - pad), min(self.H, ys[-1] + 1 + pad)
        x0, x1 = max(0, xs[0] - pad), min(self.W, xs[-1] + 1 + pad)
        q = object.__new__(hv.Part)
        q.xf, q.seed = self.xf, self.seed
        q.ox, q.oy = self.ox + x0 / hv.SS, self.oy + y0 / hv.SS
        q.W, q.H = x1 - x0, y1 - y0
        q.rgb = self.rgb[y0:y1, x0:x1].copy()
        q.a = self.a[y0:y1, x0:x1].copy()
        crop = lambda a: a[y0:y1, x0:x1] if isinstance(a, np.ndarray) and a.ndim >= 2 else a
        r = orig(q, m[y0:y1, x0:x1], mat_, bump=crop(bump), hgt=crop(hgt), **kw)
        self.rgb[y0:y1, x0:x1] = q.rgb
        self.a[y0:y1, x0:x1] = q.a
        return r
    return paint


def head_frame(hx, hy, k):
    return lambda x, y: (hx + x * k, hy + y * k)


def b_face(hv, p, F, k, skin, female=False, pts=None, age=0.0, blush=None):
    """Three-quarter face (facing right): soft skull/cheek/brow volume, jaw shade, warm cheeks.
    age (0..1) adds the sag and lines of an old face."""
    if pts is None:
        if female:
            pts = [(-36, -34), (-44, 4), (-40, 30), (-22, 50), (4, 64), (24, 72), (34, 71), (44, 60), (49, 51),
                   (51, 46), (54.5, 39), (53, 33), (53, 22), (55, 8), (53, -12), (44, -40), (10, -56), (-22, -52)]
        else:
            pts = [(-36, -34), (-44, 4), (-42, 28), (-30, 46), (0, 60), (24, 70), (35, 69), (45, 58), (50, 50),
                   (52, 46), (56, 38), (54.5, 32), (54, 22), (56, 8), (54, -12), (44, -40), (10, -56), (-22, -52)]
    m = p.poly([F(x, y) for x, y in pts], smooth=True, n=8)
    bump = hv.fold(p, [F(50, 24), F(54.5, 35)], 5 * k, 0.9) + hv.fold(p, [F(8, 4), F(50, 3)], 8 * k, 0.4)
    bump = bump + hv.blur(p.ellipse(F(28, 38), 16 * k, 12 * k), 8 * k * hv.SS) * 0.7
    bump = bump + hv.blur(p.ellipse(F(33, 66), 9 * k, 6 * k), 4 * k * hv.SS) * 0.5
    bump = bump - hv.blur(p.ellipse(F(24, 14), 18 * k, 9 * k), 6 * k * hv.SS) * 0.5
    if age:
        bump = bump + hv.fold(p, [F(38, 30), F(34, 44), F(30, 52)], 3 * k, 0.5 * age)    # cheek / nasolabial
        bump = bump - hv.fold(p, [F(40, 31), F(36, 45)], 1.4 * k, 0.7 * age)
        bump = bump - hv.blur(p.ellipse(F(22, 24), 12 * k, 4 * k), 2.5 * k * hv.SS) * 0.4 * age  # eye bags
    p.paint(m, hv.mat(skin, "skin", round=30 * k, depth=1.5, line=0.9), bump=bump * k, cast=0.0)
    jaw = hv.blur(p.poly([F(-44, 20), F(-20, 30), F(10, 50), F(30, 60), F(26, 80), F(-30, 60)]), 7 * k * hv.SS)
    p.tint(hv.C("#c98a7a"), m * jaw * 0.35)
    p.tint(hv.C("#f08f84"), m * hv.blur(p.ellipse(F(28, 36), 12 * k, 6 * k), 5 * k * hv.SS) * (blush if blush is not None else (0.35 if female else 0.14)))
    p.tint(hv.C("#f08f84"), m * hv.blur(p.ellipse(F(51, 34), 4 * k, 4 * k), 3 * k * hv.SS) * 0.22)
    if age:
        ln = hv.C("#9a5a4e")
        for pts_, w in [([F(-2, 16), F(-8, 20)], 1.0), ([F(-2, 21), F(-7, 27)], 0.9), ([F(0, 11), F(-6, 12)], 0.8),
                        ([F(10, 26), F(26, 29), F(36, 27)], 0.9)]:
            p.tint(ln, p.tube(pts_, [0.4, w * k, 0.4]) * 0.35 * age)
        for yy in (-24, -18, -30):
            p.tint(ln, p.tube([F(16, yy), F(32, yy - 1.5), F(48, yy + 0.5)], [0.4, 0.9 * k, 0.4]) * 0.28 * age)
    return m


def b_nose_mouth(hv, p, F, k, female=False, frown=0.0, smile=0.0, big=0.0, lips="#9a4a48", nose_c="#b9705f"):
    if big:
        nm = p.poly([F(48, 12), F(56, 18), F(60 + big * 6, 33), F(58 + big * 4, 39), F(52, 40)], smooth=True)
        p.paint(nm, hv.mat("#e9b39a", "skin", round=5 * k, depth=1.4, line=0.7), cast=0.25)
        p.tint(hv.C("#ffe8d8"), hv.blur(p.ellipse(F(56 + big * 3, 31), 2.5 * k, 2 * k), 1.5 * k) * 0.6)
        p.tint(hv.C(nose_c), p.tube([F(50, 38), F(55, 40.5)], [0.6, 1.6 * k, 0.6]) * 0.6)
    p.tint(hv.C(nose_c), p.tube([F(51, 31), F(54, 37), F(51, 39.5)], [0.6, 1.9 * k, 0.6]) * 0.75)
    p.tint(hv.C("#fff1e6"), hv.blur(p.tube([F(54, 18), F(56.5, 32)], [1.0 * k, 2.0 * k]), 1.0 * k * hv.SS) * 0.5)
    y = 52 - smile * 1.5
    pts = [F(39, y + frown - smile * 2.5), F(45, y + smile * 1.0), F(50, y - frown * 0.4 - smile * 2.0)]
    if female:
        p.over(hv.C(lips), p.tube(pts, [0.6, 1.8 * k, 0.6]) * 0.85)
        p.tint(hv.C("#f2a39a"), hv.blur(p.ellipse(F(45, 56), 4 * k, 1.6 * k), 1.2 * k * hv.SS) * 0.55)
    else:
        p.over(hv.C("#7d3c34"), p.tube(pts, [0.6, 1.6 * k, 0.6]) * 0.8)
        p.tint(hv.C("#d98d7e"), hv.blur(p.ellipse(F(45, 56.5), 3.5 * k, 1.4 * k), 1.2 * k * hv.SS) * 0.45)


def b_ear(hv, p, F, k, skin, big=1.0):
    pts = [(-36, 8), (-26, 6), (-22, 20), (-26, 36), (-34, 34), (-38, 20)]
    c = F(-30, 21)
    m = p.poly([(c[0] + (F(x, y)[0] - c[0]) * big, c[1] + (F(x, y)[1] - c[1]) * big) for x, y in pts], smooth=True)
    p.paint(m, hv.mat(skin, "skin", round=6 * k), cast=0.3, line=0.9,
            bump=hv.fold(p, [F(-31, 14), F(-29, 26)], 3 * k, -0.8) * k)
    return m


def b_brow(hv, p, a, b, col, w, arch=-2.0, bushy=0):
    m = p.tube([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + arch), b], [w * 0.6, w, w * 0.35])
    if bushy:
        p.paint(m, hv.mat(col, "hair", round=w * 0.5, line=0.6), cast=0.3)
        p.tint(hv.C("#ffffff"), hv.blur(p.tube([a, b], [w * 0.1, w * 0.3]), 1.5) * 0.25)
    else:
        p.over(hv.C(col), m * 0.95)


def b_closed_eye(hv, p, c, w, h, col="#3a2318", happy=False, lash=3.0):
    """A closed eye: a downward arc (sleeping) or an upward one (laughing)."""
    x, y = c
    if happy:
        pts = [(x - w * 0.5, y + h * 0.15), (x, y - h * 0.35), (x + w * 0.45, y + h * 0.1)]
    else:
        pts = [(x - w * 0.5, y - h * 0.05), (x, y + h * 0.3), (x + w * 0.45, y)]
    p.over(hv.C(col), p.tube(pts, [lash * 0.4, lash, lash * 0.3]))


def b_skin_tube(hv, p, pts, widths, skin, round_=10, cast=0.35, bump=None):
    m = p.tube(pts, widths)
    p.paint(m, hv.mat(skin, "skin", round=round_, depth=1.8), cast=cast, bump=bump)
    return m


def b_hand(hv, p, c, s, skin, ang=0.0, fingers_over=True):
    """A hand gripping something at c (size s): back of the hand plus four curled fingers stacked
    across the grip and a thumb; ang turns it (degrees, 0 = fingers pointing right)."""
    def R(pts):
        return hv.rot(pts, c, ang)
    palm = p.poly(R([(c[0] - s * 0.55, c[1] - s * 0.45), (c[0] + s * 0.25, c[1] - s * 0.55), (c[0] + s * 0.4, c[1] + s * 0.45),
                     (c[0] - s * 0.5, c[1] + s * 0.55)]), smooth=True, n=6)
    p.paint(palm, hv.mat(skin, "skin", round=s * 0.45, depth=1.6), cast=0.35)
    for i in range(4):
        yy = c[1] - s * 0.42 + i * s * 0.29
        f = R([(c[0] + s * 0.1, yy), (c[0] + s * 0.55, yy + s * 0.02), (c[0] + s * 0.62, yy + s * 0.16)])
        m = p.tube(f, [s * 0.3, s * 0.3, s * 0.24])
        p.paint(m, hv.mat(skin, "skin", round=s * 0.14, depth=1.6), cast=0.3, line=0.8)
    th = R([(c[0] - s * 0.35, c[1] - s * 0.3), (c[0] + s * 0.05, c[1] - s * 0.62), (c[0] + s * 0.32, c[1] - s * 0.66)])
    m = p.tube(th, [s * 0.36, s * 0.3, s * 0.24])
    p.paint(m, hv.mat(skin, "skin", round=s * 0.15, depth=1.6), cast=0.3, line=0.8)
    p.tint(hv.C("#fff4ea"), m * hv.blur(p.ellipse(R([(c[0] + s * 0.28, c[1] - s * 0.68)])[0], s * 0.08, s * 0.05), 2) * 0.6)


def b_glow(p, c, r, col, strength=0.6):
    """Additive light (brightens what is painted, adds a faint halo coverage)."""
    X, Y = p.grid()
    d = np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2) / r
    f = np.exp(-d * d * 2.2) * strength
    col = np.asarray(col, np.float32)
    p.rgb = p.rgb + col * f[..., None] * p.a[..., None]
    halo = f * 0.55
    p.rgb = (p.rgb * p.a[..., None] + col * halo[..., None] * (1 - p.a[..., None])) / np.maximum(p.a + halo * (1 - p.a), 1e-4)[..., None]
    p.a = p.a + halo * (1 - p.a)


def bust_finish(hv, p):
    img, _ = p.finish(line=1.5)
    return img


def dragon_scale(hv, p, c, s=1.0):
    """A big dragon scale, point down: crimson to ember, a raised keel, glowing gold veins and a
    hot heart, like the scale of the companion's fire dragon."""
    x, y = c
    pts = [(x + 4 * s, y - 80 * s), (x + 30 * s, y - 40 * s), (x + 48 * s, y + 6 * s), (x + 40 * s, y + 40 * s),
           (x, y + 60 * s), (x - 38 * s, y + 42 * s), (x - 48 * s, y + 4 * s), (x - 26 * s, y - 40 * s)]
    m = p.poly(pts, smooth=True, n=6)
    keel = hv.fold(p, [(x + 3 * s, y - 72 * s), (x, y + 10 * s), (x - 1 * s, y + 52 * s)], 16 * s, 1.0)
    ribs = sum(hv.fold(p, [(x, y - 10 * s + i * 18 * s), (x + sd * 40 * s, y - 34 * s + i * 22 * s)], 5 * s, 0.35)
               for i in range(3) for sd in (-1, 1))
    p.paint(m, hv.mat("#b8341c", "scale", round=12 * s, spec=0.8, shin=46), cast=0.35, line=0.9, bump=keel + ribs)
    X, Y = p.grid()
    d = np.sqrt(((X - x) / (40 * s)) ** 2 + ((Y - y) / (56 * s)) ** 2)
    p.tint(hv.C("#ff8a2a"), m * np.clip(1 - d, 0, 1) ** 0.7 * 0.7)
    p.tint(hv.C("#ffd060"), m * np.clip(1 - d * 1.6, 0, 1) * 0.8)
    p.tint(hv.C("#fff6d8"), m * np.clip(1 - d * 3.2, 0, 1) * 0.9)
    rng = random.Random(5)
    for i in range(7):
        a = -math.pi / 2 + (i - 3) * 0.5
        pts_ = [(x, y)]
        px, py = x, y
        for j in range(4):
            px += math.cos(a) * 12 * s + rng.uniform(-4, 4) * s
            py += math.sin(a) * 14 * s + rng.uniform(-4, 4) * s + 6 * s
            pts_.append((px, py))
        v = p.tube(pts_, [2.6 * s, 1.8 * s, 0.6]) * m
        p.over(hv.C("#ffe27a"), v * 0.85)
    # dark rim and a hot edge light
    p.tint(hv.C("#4a0e0c"), m * hv.smoothstep(0.75, 0.35, hv.blur(m, 4 * s * hv.SS)) * 0.6)
    p.tint(hv.C("#ffd9a0"), p.tube([(x - 44 * s, y + 4 * s), (x - 26 * s, y - 38 * s), (x + 2 * s, y - 76 * s)], [0.6, 2.4 * s, 0.6]) * m * 0.8)
    return m


# ------------------------------------------------------------------ Nara, the young scholar

def npc_nara(hv):
    p = hv.Part((0, 0, BUST, BUST), seed=101)
    k = 2.15
    F = head_frame(352, 268, k)
    SKIN_N = "#f3c8ac"
    HAIR, HAIR_L = "#a8461f", "#ffb36a"
    # --- hair behind the head: back mass and the bun
    back = p.poly([F(-30, -50), F(-62, -20), F(-66, 30), F(-50, 64), F(-26, 56), F(-20, -10)], smooth=True)
    hv.hair_mass(p, [back], [([F(-40, 0), F(-58, 30), F(-50, 62)], 22 * k), ([F(-30, 10), F(-44, 40), F(-38, 66)], 16 * k)],
                 HAIR, HAIR_L, round_=14 * k, cast_onto=False)
    bun = p.ellipse(F(-34, -62), 30 * k, 26 * k)
    locks = [([F(-60, -60), F(-46, -84), F(-20, -80)], 16 * k), ([F(-58, -48), F(-30, -40), F(-8, -58)], 14 * k),
             ([F(-50, -82), F(-22, -88), F(-8, -66)], 14 * k)]
    hv.hair_mass(p, [bun], locks, HAIR, HAIR_L, round_=14 * k, sheen=(F(-34, -62)[0], F(-34, -62)[1], 24 * k, 20 * k), cast_onto=False)
    # a pencil through the bun
    pc = p.tube([F(-72, -40), F(-2, -96)], [4.5 * k, 4.5 * k])
    p.paint(pc, hv.mat("#e3b23c", "matte", round=2 * k), cast=0.4)
    tip = p.poly([F(-2, -96) , F(5, -104), F(1, -94)], smooth=False)
    p.paint(p.tube([F(-2, -96), F(6, -104)], [4.5 * k, 0.8]), hv.mat("#e8c9a0", "matte", round=2), cast=0)
    # --- body: green scholar's coat, white blouse and collar
    def B(pts, dy=-56):
        return [(x, y + dy) for x, y in pts]
    coat = p.poly(B([(30, 826), (60, 680), (130, 590), (250, 532), (330, 520), (420, 528), (520, 562), (610, 630), (680, 740), (700, 826)]),
                  smooth=True, n=6)
    hv.cloth(p, coat, "#2f6b52", folds=[(B([(170, 640), (210, 740), (220, 826)]), 12, -0.8), (B([(510, 640), (530, 760)]), 10, -0.7),
                                         (B([(110, 680), (90, 826)]), 8, -0.6)], round_=30)
    neck = b_skin_tube(hv, p, [F(12, 48), (362, 490)], [62 * k * 0.55, 80], SKIN_N, round_=22, cast=0.0)
    blouse = p.poly(B([(285, 522), (432, 522), (402, 640), (362, 690), (322, 640)]), smooth=True, n=4)
    hv.cloth(p, blouse, "#f3eee4", round_=12)
    for pts in (B([(282, 514), (340, 562), (300, 602), (240, 550)]), B([(438, 514), (382, 562), (430, 598), (478, 550)])):
        hv.cloth(p, p.poly(pts, smooth=True, n=4), "#fbf8f0", round_=8)
    for pts in (B([(250, 532), (320, 640), (330, 826), (220, 826), (200, 600)]), B([(470, 532), (400, 640), (395, 826), (520, 826), (540, 610)])):
        hv.cloth(p, p.poly(pts, smooth=True, n=4), "#2a5d47", round_=16)
    hv.trim(p, B([(250, 534), (318, 640), (328, 826)]), 4.0)
    hv.trim(p, B([(470, 534), (402, 640), (396, 826)]), 4.0)
    hv.gem(p, (362, 506), 9, "#3fb88a")
    strap = p.tube(B([(150, 600), (330, 730), (470, 830)]), [26, 26])
    p.paint(strap, hv.mat("#7a4a2a", "leather", round=6), cast=0.5)
    hv.trim(p, B([(158, 592), (340, 722), (480, 822)]), 1.6, c="#d9a743")
    p.paint(p.poly(B([(246, 654), (282, 682), (262, 708), (226, 680)])), hv.mat("#d4a64a", "gold", round=3), cast=0.3)
    # the chin's shadow on the neck
    p.tint(hv.C("#9a5a5a"), neck * hv.blur(p.poly([F(-30, 40), F(10, 62), F(40, 74), F(44, 86), F(-10, 92)], smooth=True), 8 * hv.SS) * 0.6)
    # --- head
    b_ear(hv, p, F, k, SKIN_N)
    b_face(hv, p, F, k, SKIN_N, female=True)
    # freckles
    rng = random.Random(7)
    fr = np.zeros((p.H, p.W), np.float32)
    for _ in range(26):
        x, y = rng.uniform(14, 50), rng.uniform(26, 38)
        if 46 < x and y > 34:
            continue
        fr = np.maximum(fr, p.ellipse(F(x, y), rng.uniform(0.5, 0.9) * k, rng.uniform(0.45, 0.8) * k) * rng.uniform(0.5, 1))
    p.tint(hv.C("#b8603e"), fr * 0.45)
    hv.anime_eye(p, F(20, 15), 27 * k, 15.5 * k, ("#1d4a2a", "#6cc46a"), look=0.22, lash=1.8, female=True)
    hv.anime_eye(p, F(48.5, 13.5), 11.5 * k, 14.5 * k, ("#1d4a2a", "#6cc46a"), look=0.2, far=True, lash=1.6, female=True)
    b_brow(hv, p, F(34, -5), F(4, -5), "#8a3a1c", 2.4 * k, arch=-2.6 * k)
    b_brow(hv, p, F(42, -5), F(55, -7), "#8a3a1c", 1.9 * k, arch=-0.8 * k)
    b_nose_mouth(hv, p, F, k, female=True, smile=0.6, lips="#a8504a")
    # --- round glasses
    for (cx, cy, rx, ry, w) in [(20, 16, 19, 15, 2.2), (49, 15, 8.5, 14, 1.8)]:
        X, Y = p.grid()
        c = F(cx, cy)
        d = np.sqrt(((X - c[0]) / (rx * k)) ** 2 + ((Y - c[1]) / (ry * k)) ** 2)
        lens = np.clip((1 - d) * 40, 0, 1)
        p.tint(hv.C("#dff3ff"), lens * 0.08)
        g = lens * np.exp(-(((X - c[0] + rx * k * 0.3) * 0.8 + (Y - c[1] + ry * k * 0.3)) / (rx * k * 0.25)) ** 2)
        p.tint(hv.C("#ffffff"), g * 0.35)
        ring = np.clip(1 - np.abs(d - 1) * (rx * k) / (w * k * 0.5), 0, 1)
        p.paint(ring, hv.mat("#b8862e", "gold", round=1.5 * k), cast=0.35, line=0.4)
    hv.trim(p, [F(37, 14), F(42, 11.5), F(41, 14)], 1.8 * k, c="#b8862e")
    hv.trim(p, [F(1, 13), F(-18, 12), F(-28, 14)], 1.8 * k, c="#b8862e")
    # --- front hair: bangs and the locks framing the face
    cap = p.poly([F(58, -20), F(50, -50), F(20, -64), F(-20, -62), F(-50, -40), F(-56, -4), F(-46, 30), F(-36, 34),
                  F(-30, 10), F(-22, -6), F(-12, -16), F(16, -26), F(40, -28)], smooth=True)
    fr_locks = [([F(40, -50), F(52, -26), F(56, -8)], 18 * k), ([F(20, -58), F(32, -30), F(36, -6)], 20 * k),
                ([F(4, -58), F(12, -32), F(8, -12)], 18 * k), ([F(-14, -58), F(-14, -30), F(-20, -4)], 18 * k),
                ([F(-36, -46), F(-44, -10), F(-40, 30)], 16 * k), ([F(-6, -64), F(26, -66), F(52, -46)], 18 * k),
                ([F(52, -36), F(62, -6), F(58, 30), F(54, 54)], 9 * k), ([F(-26, -10), F(-32, 30), F(-24, 66)], 12 * k)]
    hv.hair_mass(p, [cap], fr_locks, HAIR, HAIR_L, sheen=(F(0, -20)[0], F(0, -20)[1], 54 * k, 44 * k), round_=12 * k)
    # --- the raised hand with the glowing dragon scale
    sleeve = p.poly([(468, 770), (492, 690), (548, 628), (622, 640), (652, 770)], smooth=True, n=5)
    hv.cloth(p, sleeve, "#2f6b52", folds=[([(540, 690), (560, 770)], 8, -0.6)], round_=20)
    cuff = p.poly([(536, 640), (594, 600), (634, 640), (574, 676)], smooth=True, n=4)
    hv.cloth(p, cuff, "#f3eee4", round_=8)
    b_skin_tube(hv, p, [(588, 630), (590, 590), (588, 560)], [48, 44, 42], SKIN_N, round_=12)
    hv.cloth(p, cuff, "#f3eee4", round_=8)
    dragon_scale(hv, p, (596, 470), 1.0)
    b_hand(hv, p, (590, 548), 54, SKIN_N, ang=-78)
    b_glow(p, (596, 456), 130, hv.C("#ff9a30"), 0.45)
    b_glow(p, (596, 456), 40, hv.C("#fff0c0"), 0.35)
    for (x, y, r) in [(660, 380, 10), (532, 404, 6), (676, 500, 6), (560, 340, 5)]:
        st = np.maximum(p.tube([(x - r, y), (x + r, y)], [0.5, 2.4, 0.5]), p.tube([(x, y - r), (x, y + r)], [0.5, 2.4, 0.5]))
        p.over(hv.C("#fff2c0"), st)
    return bust_finish(hv, p)


# ------------------------------------------------------------------ shared pieces for the old men

BALD = [(-36, 40), (-50, 20), (-60, -6), (-56, -40), (-30, -64), (8, -69), (40, -55), (54, -24), (56, 8), (54, 22),
        (54.5, 32), (56, 38), (52, 46), (50, 50), (45, 58), (35, 69), (24, 70), (0, 60), (-30, 46)]
ROUND = [(-36, 40), (-50, 20), (-60, -6), (-56, -40), (-30, -64), (8, -69), (40, -55), (54, -24), (57, 8), (57, 22),
         (58, 34), (60, 40), (58, 50), (56, 58), (48, 68), (34, 77), (16, 78), (-10, 70), (-30, 54)]


def b_torso(hv, p, pts, col, folds=(), round_=30, dy=0):
    m = p.poly([(x, y + dy) for x, y in pts], smooth=True, n=6)
    hv.cloth(p, m, col, folds=[([(x, y + dy) for x, y in f[0]], f[1], f[2]) for f in folds], round_=round_)
    return m


def b_beard(hv, p, F, k, outline, locks, col, light, sheen=None, line_a=0.6):
    """A beard as a hair mass: outline polygon (head units) and its locks [(pts, width)]."""
    base = p.poly([F(x, y) for x, y in outline], smooth=True, n=8)
    lk = [([F(x, y) for x, y in pts], w * k) for pts, w in locks]
    sh = None
    if sheen:
        c = F(sheen[0], sheen[1])
        sh = (c[0], c[1], sheen[2] * k, sheen[3] * k)
    return hv.hair_mass(p, [base], lk, col, light, sheen=sh, round_=10 * k, streaks=3, line_a=line_a, cast=0.55)


def beard_locks(x0, x1, y0, y1, n, sway=0.0, w=14, rng=None, curl=6.0):
    """n downward locks spread from x0..x1 starting near y0 and ending near y1 (head units)."""
    rng = rng or random.Random(3)
    out = []
    for i in range(n):
        t = (i + 0.5) / n
        x = x0 + (x1 - x0) * t
        ya = y0 + rng.uniform(-4, 4) + abs(t - 0.5) * 10
        yb = y1 - abs(t - 0.5) ** 1.6 * (y1 - y0) * 0.9 + rng.uniform(-6, 6)
        xm = x + sway * 0.5 + rng.uniform(-curl, curl)
        xb = x + sway + (t - 0.5) * 10 + rng.uniform(-curl, curl)
        out.append(([(x, ya), (xm, (ya + yb) / 2), (xb, yb)], w * rng.uniform(0.8, 1.15)))
    return out


def b_moustache(hv, p, F, k, col, light, curl=0.0, size=1.0):
    near = [(46, 43), (36, 46), (24, 50 + 2 * size), (12, 50 + 2 * size)]
    far = [(49, 43), (55, 46), (60, 50)]
    if curl:
        near += [(4 - 4 * curl, 46), (2 - 2 * curl, 38 - 4 * curl), (8, 36 - 2 * curl)]
        far += [(63, 46 - 2 * curl), (62, 42 - 3 * curl)]
    m1 = p.tube([F(x, y) for x, y in near], [6 * k * size, 9 * k * size, 7 * k * size, 4 * k, 2.5 * k, 1.5 * k])
    m2 = p.tube([F(x, y) for x, y in far], [6 * k * size, 5 * k * size, 2.5 * k, 1.5 * k])
    hv.hair_mass(p, [m1, m2], [([F(x, y) for x, y in near], 7 * k * size)], col, light, round_=4 * k, streaks=3, cast=0.5)


def b_old_eye(hv, p, F, k, iris, near=(20, 16), far=(48.5, 14), h=10.5, lid_skin="#d9a586", lash=1.3, look=0.22):
    """Smaller, deeper-set old eyes with a heavy upper lid."""
    hv.anime_eye(p, F(*near), 24 * k, h * k, iris, look=look, lash=lash)
    hv.anime_eye(p, F(*far), 10 * k, h * 0.95 * k, iris, look=look, far=True, lash=lash * 0.9)
    for (cx, cy, w) in ((near[0], near[1], 24), (far[0], far[1], 10)):
        lid = p.poly([F(cx - w * 0.6, cy - h * 0.55), F(cx + w * 0.55, cy - h * 0.6), F(cx + w * 0.5, cy - h * 0.9),
                      F(cx - w * 0.55, cy - h * 1.1)], smooth=True)
        p.paint(lid, hv.mat(lid_skin, "skin", round=3 * k), cast=0.35, line=0.5)


def b_open_mouth(hv, p, F, k, w=1.0, h=1.0):
    """A laughing open mouth with teeth and tongue."""
    pts = [F(36, 52), F(44, 50 - 1 * h), F(52, 51), F(50, 56 + 4 * h), F(43, 60 + 5 * h), F(37, 57 + 3 * h)]
    m = p.poly(pts, smooth=True, n=6)
    p.over(hv.C("#5a1a1e"), m)
    p.over(hv.C("#d8606a"), p.ellipse(F(44, 58 + 3 * h), 6 * k * w, 3 * k * h) * m)
    p.over(hv.C("#fbf4ec"), p.poly([F(37, 52), F(44, 50.5 - h), F(51, 51.5), F(49, 54), F(38, 54.5)], smooth=True) * m * 0.95)
    return m


def b_lantern(hv, p, c, s, gl=True):
    x, y = c
    iron = "#2d2830"
    p.paint(p.tube([(x - 14 * s, y - 52 * s), (x, y - 72 * s), (x + 14 * s, y - 52 * s)], [3 * s, 3 * s, 3 * s]),
            hv.mat(iron, "metal", round=2), cast=0.3, line=0.5)
    p.paint(p.poly([(x - 26 * s, y - 34 * s), (x + 26 * s, y - 34 * s), (x + 14 * s, y - 52 * s), (x - 14 * s, y - 52 * s)]),
            hv.mat(iron, "metal", round=6 * s), cast=0.3)
    pane = p.poly([(x - 20 * s, y - 34 * s), (x + 20 * s, y - 34 * s), (x + 18 * s, y + 30 * s), (x - 18 * s, y + 30 * s)])
    X, Y = p.grid()
    d = np.sqrt(((X - x) / (20 * s)) ** 2 + ((Y - y) / (34 * s)) ** 2)
    p.over(hv.mixc(hv.C("#fff6d0"), hv.C("#e07a20"), np.clip(d, 0, 1)[..., None]), pane)
    fl = p.poly(flame_pts(x, y + 14 * s, 14 * s, 34 * s, 0.05, 0.5))
    p.over(hv.C("#fffbe8"), hv.blur(fl, 2 * s) * 0.9)
    for xx in (x - 20 * s, x, x + 20 * s):
        p.paint(p.tube([(xx, y - 34 * s), (xx * 0.98 + x * 0.02, y + 30 * s)], [4 * s, 4 * s]), hv.mat(iron, "metal", round=2), cast=0.2, line=0.4)
    p.paint(p.poly([(x - 26 * s, y + 30 * s), (x + 26 * s, y + 30 * s), (x + 22 * s, y + 42 * s), (x - 22 * s, y + 42 * s)]),
            hv.mat(iron, "metal", round=5 * s), cast=0.3)
    if gl:
        b_glow(p, (x, y), 170 * s, hv.C("#ffa040"), 0.5)
        b_glow(p, (x, y), 50 * s, hv.C("#fff2c8"), 0.45)


# ------------------------------------------------------------------ Usta Örs, the smith

def npc_smith(hv):
    p = hv.Part((0, 0, BUST, BUST), seed=202)
    k = 2.2
    F = head_frame(360, 250, k)
    SK = "#d99a76"
    GREY, GREY_L = "#8d8a8c", "#f4f0ea"
    # body: broad shoulders, a dark red work shirt, leather apron with straps
    b_torso(hv, p, [(0, 770), (10, 600), (90, 500), (230, 450), (360, 438), (480, 450), (600, 500), (690, 600), (730, 770)],
            "#7a2a22", folds=[([(140, 520), (170, 640), (160, 770)], 14, -0.8), ([(560, 540), (590, 680)], 12, -0.7)])
    apron = p.poly([(170, 770), (190, 560), (260, 520), (480, 520), (560, 560), (580, 770)], smooth=True, n=5)
    hv.cloth(p, apron, "#6a4126", folds=[([(300, 600), (290, 770)], 10, -0.6), ([(450, 600), (470, 770)], 10, -0.6)], round_=26)
    p.paint(p.tube([(130, 470), (220, 600)], [30, 30]), hv.mat("#4e2e1a", "leather", round=6), cast=0.4)
    p.paint(p.tube([(560, 470), (510, 600)], [26, 26]), hv.mat("#4e2e1a", "leather", round=6), cast=0.4)
    for c in ((214, 590), (514, 590)):
        p.paint(p.ellipse(c, 12, 12), hv.mat("#b8862e", "gold", round=4), cast=0.3)
    # soot smudges on the apron
    p.tint(hv.C("#2a1a14"), apron * hv.blur(p.ellipse((380, 700), 60, 30), 20) * 0.35)
    # neck
    b_skin_tube(hv, p, [F(10, 50), (360, 470)], [70 * k * 0.6, 120], SK, round_=26, cast=0.0)
    # head: bald dome
    b_face(hv, p, F, k, SK, pts=BALD, age=1.0, blush=0.25)
    p.tint(hv.C("#fff3e0"), p.poly([F(x, y) for x, y in BALD], smooth=True) * hv.blur(p.ellipse(F(4, -46), 20 * k, 12 * k), 10 * hv.SS) * 0.55)
    # grey fringe around the back of the head
    fringe = p.poly([F(-28, -10), F(-50, -24), F(-62, -2), F(-56, 30), F(-38, 44), F(-30, 26)], smooth=True)
    hv.hair_mass(p, [fringe], [([F(-46, -20), F(-60, 4), F(-50, 36)], 14 * k), ([F(-34, -12), F(-46, 14), F(-40, 40)], 12 * k)],
                 GREY, GREY_L, round_=8 * k, cast=0.4)
    b_ear(hv, p, F, k, SK, big=1.2)
    b_old_eye(hv, p, F, k, ("#26384a", "#7aa6c8"), lid_skin=SK, look=0.18)
    b_brow(hv, p, F(36, -2), F(0, -6), "#cfcac4", 5.4 * k, arch=-3 * k, bushy=1)
    b_brow(hv, p, F(42, -2), F(57, -6), "#cfcac4", 3.8 * k, arch=-1 * k, bushy=1)
    b_nose_mouth(hv, p, F, k, big=1.0, frown=0.5)
    # the huge beard, over the chest
    outline = [(-34, 10), (-38, 40), (-30, 76), (-14, 116), (8, 150), (36, 166), (66, 150), (84, 112), (82, 74), (70, 52),
               (58, 44), (50, 50), (40, 54), (24, 56), (6, 48), (-10, 34), (-20, 14), (-26, 6)]
    lk = beard_locks(-30, 78, 40, 160, 12, sway=4, w=20, rng=random.Random(11), curl=8)
    lk += [([(-30, 12), (-34, 40), (-24, 70)], 14), ([(70, 50), (80, 80), (74, 112)], 14), ([(-20, 30), (-20, 70), (-6, 110)], 16)]
    b_beard(hv, p, F, k, outline, lk, GREY, GREY_L, sheen=(24, 70, 40, 46))
    b_moustache(hv, p, F, k, GREY, GREY_L, size=1.25)
    # the forge hammer, held up beside him
    hw = (616, 600)
    b_skin_tube(hv, p, [(680, 790), (650, 700), (620, 620)], [120, 104, 80], SK, round_=30)
    hd = (650, 268)
    p.paint(p.tube([(hw[0] - 4, hw[1] + 60), hd], [26, 24]), hv.mat("#6a4428", "leather", round=6, spec=0.1), cast=0.45)
    hh = hv.rot([(hd[0] - 92, hd[1] - 44), (hd[0] + 80, hd[1] - 44), (hd[0] + 92, hd[1] - 32), (hd[0] + 92, hd[1] + 32),
                 (hd[0] + 80, hd[1] + 44), (hd[0] - 92, hd[1] + 44)], hd, 8)
    p.paint(p.poly(hh), hv.mat("#8a8e98", "metal", round=14), cast=0.5)
    hv.trim(p, hv.rot([(hd[0] - 40, hd[1] - 44), (hd[0] - 40, hd[1] + 44)], hd, 8), 8, c="#5a5e68")
    hv.trim(p, hv.rot([(hd[0] + 40, hd[1] - 44), (hd[0] + 40, hd[1] + 44)], hd, 8), 8, c="#5a5e68")
    p.tint(hv.C("#ff9a50"), p.poly(hh) * hv.blur(p.ellipse((hd[0] - 70, hd[1] + 40), 40, 20), 14) * 0.5)
    b_hand(hv, p, hw, 78, SK, ang=-8)
    # forge glow from below right
    b_glow(p, (700, 760), 360, hv.C("#ff7a2a"), 0.22)
    return bust_finish(hv, p)


# ------------------------------------------------------------------ Madam Pırıl, the merchant

def potion(hv, p, c, s, liquid="#3fcf5a", glow_c="#7dff7a"):
    """A round-bellied flask with a cork and a glowing liquid."""
    x, y = c
    body = p.ellipse((x, y + 10 * s), 42 * s, 44 * s)
    neck = p.poly([(x - 13 * s, y - 30 * s), (x + 13 * s, y - 30 * s), (x + 13 * s, y - 68 * s), (x - 13 * s, y - 68 * s)])
    glass = np.maximum(body, neck)
    p.cast(glass, strength=0.35)
    p.over(hv.C("#2a5a40"), glass * 0.35)
    liq = body * (p.grid()[1] > y - 8 * s)
    X, Y = p.grid()
    d = np.sqrt(((X - x) / (42 * s)) ** 2 + ((Y - y - 20 * s) / (36 * s)) ** 2)
    p.over(hv.mixc(hv.C(glow_c) * 1.0 + 0.15, hv.C(liquid) * 0.55, np.clip(d, 0, 1)[..., None]), liq)
    p.tint(hv.C("#eaffd8"), liq * np.exp(-(((Y - (y - 8 * s)) / (3 * s)) ** 2)) * 0.8)
    for (bx, by, r) in [(x - 10 * s, y + 20 * s, 4), (x + 14 * s, y + 2 * s, 3), (x + 2 * s, y + 34 * s, 2.5)]:
        p.over(hv.C("#eaffe0"), p.ellipse((bx, by), r * s, r * s) * 0.7)
    p.tint(hv.C("#ffffff"), glass * hv.blur(p.tube([(x - 30 * s, y - 4 * s), (x - 24 * s, y - 22 * s), (x - 10 * s, y - 32 * s)], [2, 6 * s, 2]), 2) * 0.8)
    p.tint(hv.C("#ffffff"), p.ellipse((x + 24 * s, y + 30 * s), 4 * s, 7 * s) * 0.5)
    p.edge_line(glass, {"c": hv.C("#2a6a48")}, 1.0)
    rim = p.tube([(x - 16 * s, y - 66 * s), (x + 16 * s, y - 66 * s)], [6 * s, 6 * s])
    p.paint(rim, hv.mat("#c8e0d0", "metal", round=2), cast=0.2, line=0.4)
    cork = p.poly([(x - 11 * s, y - 68 * s), (x + 11 * s, y - 68 * s), (x + 13 * s, y - 88 * s), (x - 13 * s, y - 88 * s)])
    p.paint(cork, hv.mat("#b07a48", "matte", round=5 * s), cast=0.3)
    b_glow(p, (x, y + 16 * s), 150 * s, hv.C(glow_c), 0.45)
    b_glow(p, (x, y + 16 * s), 40 * s, hv.C("#eaffd0"), 0.3)


def npc_merchant(hv):
    p = hv.Part((0, 0, BUST, BUST), seed=303)
    k = 2.1
    F = head_frame(356, 300, k)
    SK = "#f2c4a6"
    HAIR, HAIR_L = "#7a2a1c", "#e2804e"
    # long auburn waves behind
    back = p.poly([F(-30, -44), F(-70, -10), F(-80, 60), F(-70, 120), F(-30, 130), F(-10, 60), F(-16, -10)], smooth=True)
    lk = [([F(-50, -10), F(-74, 40), F(-62, 90), F(-74, 128)], 22), ([F(-36, 0), F(-52, 50), F(-38, 96), F(-46, 132)], 20),
          ([F(-60, -20), F(-82, 20), F(-80, 70), F(-90, 110)], 16)]
    hv.hair_mass(p, [back], [(l, w * k) for l, w in lk], HAIR, HAIR_L, round_=14 * k, cast_onto=False,
                 sheen=(F(-50, 40)[0], F(-50, 40)[1], 30 * k, 60 * k))
    # body: purple gown with a gold-trimmed bodice and a lace collar
    b_torso(hv, p, [(20, 770), (50, 640), (130, 560), (250, 520), (340, 512), (440, 520), (560, 560), (660, 650), (700, 770)],
            "#5a2a7a", folds=[([(150, 600), (190, 700), (180, 770)], 12, -0.8), ([(540, 600), (560, 720)], 10, -0.6)])
    b_skin_tube(hv, p, [F(10, 50), (350, 520)], [60 * k * 0.5, 74], SK, round_=20, cast=0.0)
    dec = p.poly([(270, 520), (430, 520), (400, 600), (350, 630), (300, 600)], smooth=True, n=4)
    p.paint(dec, hv.mat(SK, "skin", round=22), cast=0.0)
    lace = p.poly([(250, 512), (300, 600), (350, 636), (400, 600), (450, 512), (470, 530), (410, 640), (350, 670), (290, 640), (230, 530)], smooth=True, n=4)
    hv.cloth(p, lace, "#efe6f2", round_=6)
    hv.trim(p, [(240, 530), (296, 640), (350, 668), (408, 640), (466, 530)], 4.5)
    # necklace with an emerald
    hv.trim(p, [(296, 540), (350, 590), (404, 540)], 2.6)
    hv.gem(p, (350, 596), 10, "#2fbf7a")
    bod = p.poly([(280, 680), (350, 690), (420, 680), (430, 770), (270, 770)], smooth=True, n=4)
    hv.cloth(p, bod, "#4a1e66", round_=12)
    for yy in (700, 730, 760):
        hv.trim(p, [(322, yy - 8), (378, yy + 8)], 2.4)
        hv.trim(p, [(322, yy + 8), (378, yy - 8)], 2.4)
    p.tint(hv.C("#c8862e"), p.tube([(150, 560), (110, 770)], [6, 6]) * 0.0)
    # head
    b_face(hv, p, F, k, SK, female=True, blush=0.3)
    hv.anime_eye(p, F(20, 16), 26 * k, 12 * k, ("#2a1438", "#a070d8"), look=0.3, lash=2.0, female=True)
    hv.anime_eye(p, F(48.5, 14.5), 11 * k, 11.5 * k, ("#2a1438", "#a070d8"), look=0.3, far=True, lash=1.7, female=True)
    # half-lowered lids: the sly look
    for (cx, cy, w, h) in ((20, 16, 26, 12), (48.5, 14.5, 11, 11.5)):
        lid = p.poly([F(cx - w * 0.62, cy - h * 0.1), F(cx + w * 0.58, cy - h * 0.25), F(cx + w * 0.5, cy - h * 0.9),
                      F(cx - w * 0.6, cy - h * 0.9)], smooth=True)
        p.paint(lid, hv.mat("#c88aa8", "skin", round=3 * k), cast=0.4, line=0.4)
        p.over(hv.C("#2a1020"), p.tube([F(cx - w * 0.66, cy - h * 0.02), F(cx, cy - h * 0.22), F(cx + w * 0.56, cy - h * 0.2)],
                                       [3.0 * k, 2.4 * k, 1.0 * k]))
    b_brow(hv, p, F(34, -6), F(4, -11), "#5a1a14", 2.2 * k, arch=-3.4 * k)
    b_brow(hv, p, F(42, -6), F(56, -12), "#5a1a14", 1.8 * k, arch=-1.2 * k)
    b_nose_mouth(hv, p, F, k, female=True, smile=0.0, lips="#a83048")
    # a sly smirk: the far corner lifted
    p.over(hv.C("#8a2038"), p.tube([F(39, 52.5), F(45, 52), F(51, 49)], [0.6, 2.2 * k, 0.8]) * 0.9)
    p.over(hv.C("#c84a60"), hv.blur(p.ellipse(F(45, 55.5), 4 * k, 1.8 * k), 2) * 0.6)
    # beauty mark
    p.over(hv.C("#4a1a1a"), p.ellipse(F(52, 44), 1.1 * k, 1.1 * k))
    # front hair: side-parted waves
    cap = p.poly([F(58, -22), F(48, -50), F(18, -62), F(-22, -60), F(-50, -38), F(-56, 0), F(-44, 40), F(-30, 30),
                  F(-26, 4), F(-10, -16), F(20, -28), F(44, -30)], smooth=True)
    fr = [([F(-10, -58), F(26, -50), F(54, -24), F(60, 0)], 18), ([F(-20, -50), F(10, -36), F(30, -20)], 16),
          ([F(-36, -40), F(-40, -6), F(-30, 30), F(-38, 60)], 16), ([F(56, -20), F(66, 20), F(60, 60), F(68, 96)], 12),
          ([F(-50, -30), F(-56, 10), F(-50, 50), F(-56, 90)], 14)]
    hv.hair_mass(p, [cap], [(l, w * k) for l, w in fr], HAIR, HAIR_L, sheen=(F(4, -24)[0], F(4, -24)[1], 50 * k, 40 * k), round_=12 * k)
    # gold hoop earring (near ear sits under the hair; the hoop hangs below it)
    X, Y = p.grid()
    hc = F(-28, 50)
    d = np.sqrt(((X - hc[0]) / (11 * k)) ** 2 + ((Y - hc[1]) / (13 * k)) ** 2)
    hoop = np.clip(1 - np.abs(d - 1) * 11 * k / (1.6 * k), 0, 1)
    p.paint(hoop, hv.mat("#e0b050", "gold", round=1.5 * k), cast=0.4, line=0.4)
    # the big purple hat with feathers
    brim_c = F(2, -50)
    for (pts, col, w) in [([F(-40, -64), F(-90, -96), F(-150, -110), F(-180, -100)], "#2fa8a0", 30),
                          ([F(-30, -70), F(-70, -116), F(-120, -150), F(-150, -150)], "#e070a8", 26),
                          ([F(-20, -74), F(-50, -126), F(-80, -168), F(-104, -176)], "#f2d36a", 20)]:
        fm = p.tube(pts, [w * k * 0.6, w * k, w * k * 0.7, 2])
        p.paint(fm, hv.mat(col, "cloth", round=6 * k, rim=0.8), cast=0.4, line=0.6)
        for j in range(14):
            t = j / 13
            a = pts[0]
            b = pts[-1]
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            p.tint(hv.C("#ffffff") if j % 2 else hv.C(col) * 0.6, p.tube([(px, py), (px + 8 * k, py + 10 * k)], [0.6, 1.2 * k, 0.4]) * fm * 0.4)
    brim = p.poly(hv.rot(hv.ell_pts(brim_c, 120 * k * 0.95, 26 * k), brim_c, -8), smooth=False)
    p.paint(brim, hv.mat("#5c2a86", "cloth", round=10 * k), cast=0.55, line=1.0)
    crown = p.poly([F(-46, -60), F(-40, -104), F(-6, -124), F(36, -114), F(52, -76), F(48, -58)], smooth=True)
    p.paint(crown, hv.mat("#6a3296", "cloth", round=14 * k), cast=0.4)
    band = p.tube([F(-46, -66), F(0, -62), F(50, -68)], [10 * k, 11 * k, 10 * k], caps=False) * crown
    p.paint(band, hv.mat("#d9a743", "gold", round=3 * k), cast=0.3)
    hv.gem(p, F(14, -64), 6 * k, "#2fbf7a")
    # the potion, raised
    b_torso(hv, p, [(480, 770), (500, 690), (560, 640), (626, 650), (660, 770)], "#5a2a7a", round_=20)
    cuff = p.poly([(540, 652), (600, 612), (640, 652), (580, 688)], smooth=True, n=4)
    b_skin_tube(hv, p, [(592, 640), (596, 580)], [44, 40], SK, round_=12)
    hv.cloth(p, cuff, "#efe6f2", round_=6)
    potion(hv, p, (604, 470), 1.05)
    b_hand(hv, p, (598, 560), 50, SK, ang=-80)
    for (x, y, r) in [(680, 400, 8), (530, 420, 5), (690, 520, 5)]:
        st = np.maximum(p.tube([(x - r, y), (x + r, y)], [0.5, 2.2, 0.5]), p.tube([(x, y - r), (x, y + r)], [0.5, 2.2, 0.5]))
        p.over(hv.C("#e8ffd8"), st)
    return bust_finish(hv, p)


# ------------------------------------------------------------------ Hancı Bulut, the innkeeper

def tankard(hv, p, c, s):
    x, y = c
    body = p.poly([(x - 46 * s, y - 50 * s), (x + 46 * s, y - 50 * s), (x + 42 * s, y + 60 * s), (x - 42 * s, y + 60 * s)])
    staves = sum(hv.fold(p, [(x + d * s, y - 48 * s), (x + d * 0.92 * s, y + 58 * s)], 3 * s, -0.5) for d in (-30, -12, 6, 24))
    p.paint(body, hv.mat("#8a5a30", "matte", round=16 * s), bump=staves, cast=0.45)
    handle = p.tube([(x + 44 * s, y - 30 * s), (x + 80 * s, y - 20 * s), (x + 82 * s, y + 24 * s), (x + 42 * s, y + 36 * s)], [16 * s, 16 * s, 16 * s, 16 * s])
    p.paint(handle * (1 - body), hv.mat("#7a4e2a", "matte", round=6 * s), cast=0.3)
    for yy in (-36, 44):
        band = p.poly([(x - 47 * s, y + (yy - 7) * s), (x + 47 * s, y + (yy - 7) * s), (x + 46 * s, y + (yy + 7) * s), (x - 46 * s, y + (yy + 7) * s)])
        p.paint(band, hv.mat("#9aa0a8", "metal", round=4 * s), cast=0.3)
    foam = p.dabs if False else None
    items = [(x - 40 * s, y - 56 * s, 20 * s), (x - 14 * s, y - 64 * s, 24 * s), (x + 16 * s, y - 62 * s, 22 * s), (x + 40 * s, y - 54 * s, 18 * s),
             (x + 2 * s, y - 78 * s, 20 * s), (x - 26 * s, y - 74 * s, 14 * s), (x + 50 * s, y - 40 * s, 10 * s)]
    fm = np.zeros((p.H, p.W), np.float32)
    for (fx_, fy, r) in items:
        fm = np.maximum(fm, p.ellipse((fx_, fy), r, r * 0.85))
    drip = p.tube([(x + 30 * s, y - 50 * s), (x + 34 * s, y - 20 * s)], [14 * s, 9 * s])
    fm = np.maximum(fm, drip)
    p.paint(fm, hv.mat("#fbf5e6", "cloth", round=8 * s, rim=0.8), cast=0.4, line=0.5)


def npc_innkeeper(hv):
    p = hv.Part((0, 0, BUST, BUST), seed=404)
    k = 2.2
    F = head_frame(352, 268, k)
    SK = "#f0b894"
    HAIR, HAIR_L = "#5a3420", "#c88a5a"
    # round body: white shirt, green vest, a striped apron bib
    b_torso(hv, p, [(0, 770), (10, 620), (80, 520), (220, 470), (350, 460), (480, 470), (610, 520), (690, 620), (720, 770)],
            "#f1ebe0", folds=[([(120, 560), (140, 680)], 12, -0.7), ([(590, 560), (600, 700)], 12, -0.7)], round_=40)
    for pts in ([(100, 770), (110, 560), (220, 490), (300, 500), (290, 770)], [(410, 770), (400, 500), (480, 490), (600, 560), (630, 770)]):
        b_torso(hv, p, pts, "#2f6a3a", round_=26)
    for yy in (580, 640, 700):
        hv.gem(p, (420, yy), 8, "#d9a743")
    b_skin_tube(hv, p, [F(10, 56), (350, 480)], [64 * k * 0.6, 110], SK, round_=26, cast=0.0)
    collar = p.poly([(250, 470), (350, 540), (450, 470), (470, 500), (350, 570), (230, 500)], smooth=True, n=3)
    hv.cloth(p, collar, "#fbf8f2", round_=8)
    # head: round, bald on top with brown sides
    b_face(hv, p, F, k, SK, pts=ROUND, age=0.4, blush=0.55)
    p.tint(hv.C("#fff2e6"), p.poly([F(x, y) for x, y in ROUND], smooth=True) * hv.blur(p.ellipse(F(4, -48), 20 * k, 10 * k), 10 * hv.SS) * 0.55)
    sides = p.poly([F(-24, -20), F(-52, -34), F(-64, -2), F(-58, 36), F(-40, 52), F(-30, 30)], smooth=True)
    hv.hair_mass(p, [sides], [([F(-44, -28), F(-62, 6), F(-50, 44)], 14 * k), ([F(-30, -20), F(-44, 10), F(-38, 46)], 12 * k)],
                 HAIR, HAIR_L, round_=8 * k, cast=0.4)
    b_ear(hv, p, F, k, SK, big=1.1)
    b_closed_eye(hv, p, F(21, 17), 22 * k, 10 * k, "#3a1e14", happy=True, lash=3.6 * k)
    b_closed_eye(hv, p, F(49, 15.5), 9 * k, 9 * k, "#3a1e14", happy=True, lash=3.0 * k)
    b_brow(hv, p, F(34, 0), F(4, -6), HAIR, 3.6 * k, arch=-3.2 * k, bushy=1)
    b_brow(hv, p, F(42, 0), F(57, -5), HAIR, 2.8 * k, arch=-1.2 * k, bushy=1)
    b_nose_mouth(hv, p, F, k, big=1.4, nose_c="#c0605a")
    p.tint(hv.C("#ff7a6a"), p.poly([F(x, y) for x, y in ROUND], smooth=True) * hv.blur(p.ellipse(F(58, 30), 5 * k, 5 * k), 6) * 0.35)
    b_open_mouth(hv, p, F, k, w=1.1, h=1.3)
    b_moustache(hv, p, F, k, HAIR, HAIR_L, curl=1.0, size=1.15)
    # the foaming tankard
    b_torso(hv, p, [(470, 770), (500, 680), (560, 630), (630, 640), (670, 770)], "#f1ebe0", round_=24)
    b_skin_tube(hv, p, [(590, 650), (590, 590)], [62, 56], SK, round_=14)
    tankard(hv, p, (580, 470), 1.15)
    b_hand(hv, p, (548, 540), 62, SK, ang=-4)
    return bust_finish(hv, p)


# ------------------------------------------------------------------ Bekçi Tozlu, the gate keeper

def npc_keeper(hv):
    p = hv.Part((0, 0, BUST, BUST), seed=505)
    k = 2.15
    F = head_frame(350, 300, k)
    SK = "#e8b294"
    GREY, GREY_L = "#8f8c8a", "#efeae2"
    # body: patched brown coat, a thick mustard scarf
    b_torso(hv, p, [(10, 770), (30, 640), (110, 550), (240, 510), (350, 500), (460, 510), (590, 550), (680, 640), (710, 770)],
            "#6a5440", folds=[([(140, 580), (170, 700)], 12, -0.8), ([(560, 580), (580, 720)], 12, -0.7), ([(330, 640), (340, 770)], 10, -0.5)])
    for (x, y, c) in [(170, 680, "#5a3a6a"), (520, 700, "#a07a3a")]:
        pm = p.poly([(x - 30, y - 26), (x + 30, y - 28), (x + 32, y + 26), (x - 28, y + 28)], smooth=True, n=2)
        hv.cloth(p, pm, c, round_=8)
        for t in range(10):
            a = t / 10 * 2 * math.pi
            p.over(hv.C("#e8d8b0"), p.ellipse((x + math.cos(a) * 30, y + math.sin(a) * 27), 1.6, 3.4) * 0.8)
    b_skin_tube(hv, p, [F(10, 50), (350, 500)], [60 * k * 0.6, 90], SK, round_=22, cast=0.0)
    scarf = p.poly([(220, 500), (300, 470), (420, 476), (490, 510), (470, 560), (350, 580), (240, 556)], smooth=True, n=5)
    hv.cloth(p, scarf, "#c89a2a", folds=[([(260, 520), (460, 530)], 10, -0.7), ([(250, 540), (450, 554)], 8, -0.5)], round_=14)
    tail = p.poly([(420, 540), (470, 540), (480, 700), (430, 706)], smooth=True, n=3)
    hv.cloth(p, tail, "#c89a2a", round_=10)
    for yy in (640, 670):
        p.tint(hv.C("#a8401c"), p.tube([(424, yy), (478, yy - 2)], [6, 6]) * tail * 0.8)
    # the key ring on a cord
    hv.trim(p, [(300, 570), (290, 640), (300, 690)], 2.5, c="#6a5a3a")
    X, Y = p.grid()
    rc = (300, 708)
    d = np.sqrt(((X - rc[0]) / 20) ** 2 + ((Y - rc[1]) / 20) ** 2)
    p.paint(np.clip(1 - np.abs(d - 1) * 20 / 3.0, 0, 1), hv.mat("#9a8a6a", "metal", round=2), cast=0.4, line=0.4)
    for (ang, ln) in ((-20, 70), (10, 60), (40, 52)):
        a = math.radians(90 + ang)
        b0 = (rc[0] + math.cos(a) * 20, rc[1] + math.sin(a) * 20)
        b1 = (b0[0] + math.cos(a) * ln, b0[1] + math.sin(a) * ln)
        key = np.maximum(p.ellipse(b0, 9, 9), p.tube([b0, b1], [5, 5]))
        key = np.maximum(key, p.tube([b1, (b1[0] + math.cos(a + 1.57) * 12, b1[1] + math.sin(a + 1.57) * 12)], [5, 5]))
        p.paint(key, hv.mat("#c9a24a", "gold", round=2), cast=0.4, line=0.5)
    # head
    b_face(hv, p, F, k, SK, age=1.0, blush=0.3)
    side = p.poly([F(-26, -6), F(-48, -14), F(-56, 14), F(-46, 46), F(-30, 40)], smooth=True)
    hv.hair_mass(p, [side], [([F(-40, -10), F(-54, 20), F(-44, 46)], 12 * k)], GREY, GREY_L, round_=8 * k, cast=0.4)
    b_ear(hv, p, F, k, SK, big=1.15)
    b_closed_eye(hv, p, F(21, 18), 22 * k, 10 * k, "#4a2a20", lash=3.2 * k)
    b_closed_eye(hv, p, F(49, 16.5), 9 * k, 9 * k, "#4a2a20", lash=2.6 * k)
    for (cx, cy, w) in ((21, 18, 22), (49, 16.5, 9)):
        p.tint(hv.C("#b07a6a"), p.tube([F(cx - w * 0.45, cy + 4), F(cx, cy + 6.5), F(cx + w * 0.4, cy + 4)], [0.5, 1.6 * k, 0.5]) * 0.5)
    b_brow(hv, p, F(34, 2), F(4, 4), "#d8d2ca", 4.4 * k, arch=-2.2 * k, bushy=1)
    b_brow(hv, p, F(42, 2), F(56, 4), "#d8d2ca", 3.2 * k, arch=-1.0 * k, bushy=1)
    b_nose_mouth(hv, p, F, k, big=1.2, nose_c="#c0505a")
    p.tint(hv.C("#ff6a5a"), hv.blur(p.ellipse(F(57, 32), 6 * k, 5 * k), 6) * 0.55)
    b_moustache(hv, p, F, k, GREY, GREY_L, size=1.05)
    # a soft open mouth (snoring) under the moustache
    p.over(hv.C("#5a2028"), p.ellipse(F(44, 58), 3.2 * k, 2.6 * k) * 0.9)
    # stubble
    rng = random.Random(9)
    st = np.zeros((p.H, p.W), np.float32)
    for _ in range(160):
        x, y = rng.uniform(-10, 52), rng.uniform(44, 70)
        st = np.maximum(st, p.ellipse(F(x, y), 0.5 * k, 0.5 * k))
    face_m = p.poly([F(x, y) for x, y in [(-36, -34), (-44, 4), (-42, 28), (-30, 46), (0, 60), (24, 70), (35, 69), (45, 58),
                                           (50, 50), (52, 46), (56, 38), (54.5, 32), (54, 22), (56, 8), (54, -12)]], smooth=True)
    p.tint(hv.C("#8a7a74"), st * face_m * 0.5)
    # the long green nightcap, flopping over to the back with a pompom
    cap = p.poly([F(56, -20), F(52, -52), F(24, -70), F(-20, -70), F(-50, -50), F(-58, -14), F(-40, -6), F(-10, -26), F(30, -30)], smooth=True)
    hv.cloth(p, cap, "#3a7a3a", folds=[([F(-30, -50), F(20, -40)], 6 * k, -0.5)], round_=14 * k)
    tip = p.tube([F(-20, -66), F(-60, -80), F(-96, -60), F(-112, -20), F(-108, 14)], [60 * k * 0.9, 40 * k, 28 * k, 18 * k, 10 * k])
    hv.cloth(p, tip, "#3a7a3a", folds=[([F(-50, -70), F(-96, -40)], 4 * k, -0.6)], round_=10 * k)
    cuffm = p.tube([F(-56, -12), F(-30, -20), F(10, -30), F(58, -22)], [12 * k, 14 * k, 14 * k, 12 * k])
    hv.cloth(p, cuffm, "#f2ece0", round_=5 * k)
    pom = p.ellipse(F(-108, 22), 14 * k, 14 * k)
    p.paint(pom, hv.mat("#f6f2ea", "cloth", round=7 * k), cast=0.4)
    # the lantern, held up
    b_torso(hv, p, [(470, 770), (500, 690), (556, 640), (620, 650), (650, 770)], "#6a5440", round_=20)
    b_skin_tube(hv, p, [(586, 650), (588, 590)], [54, 48], SK, round_=14)
    b_lantern(hv, p, (596, 430), 1.25)
    b_hand(hv, p, (586, 538), 52, SK, ang=-86)
    # snore bubble
    bub = p.ellipse(F(70, 46), 9 * k, 8 * k)
    p.over(hv.C("#d8f0ff"), bub * 0.35)
    p.tint(hv.C("#ffffff"), p.ellipse(F(67, 43), 2.5 * k, 2 * k) * 0.8)
    p.edge_line(bub, {"c": hv.C("#7ab0d0")}, 0.8)
    return bust_finish(hv, p)


# ------------------------------------------------------------------ Yaşlı Kaan, the class master

def npc_class_master(hv):
    p = hv.Part((0, 0, BUST, BUST), seed=606)
    k = 2.15
    F = head_frame(352, 262, k)
    SK = "#d8a080"
    GREY, GREY_L = "#8c8a8e", "#f2eee8"
    # crimson tunic, a leather baldric, and plate pauldrons
    b_torso(hv, p, [(0, 770), (10, 610), (90, 510), (230, 466), (352, 456), (470, 466), (600, 510), (690, 610), (720, 770)],
            "#7e1f22", folds=[([(330, 560), (340, 770)], 12, -0.7), ([(240, 560), (230, 770)], 10, -0.6)])
    b_skin_tube(hv, p, [F(10, 50), (352, 470)], [66 * k * 0.6, 100], SK, round_=24, cast=0.0)
    # breastplate
    bp = p.poly([(200, 560), (352, 520), (500, 560), (520, 770), (190, 770)], smooth=True, n=4)
    hv.plate(p, [(200, 560), (352, 520), (500, 560), (520, 770), (190, 770)], c="#b8bec8", round_=40,
             bump=hv.fold(p, [(352, 530), (352, 770)], 26, 0.8))
    hv.trim(p, [(200, 562), (352, 522), (500, 562)], 6)
    hv.gem(p, (352, 600), 12, "#c03030")
    # pauldrons
    for (c, sx, sy, deg) in [((150, 540), 130, 90, -18), ((560, 545), 100, 76, 16)]:
        for j, (dy, sc) in enumerate(((44, 0.86), (22, 0.93), (0, 1.0))):
            pts = hv.ell_pts((c[0], c[1] + dy), sx * sc, sy * sc, deg, n=40, a0=180, a1=360)
            pts += [(c[0] + sx * sc * 0.9, c[1] + dy + 26), (c[0] - sx * sc * 0.9, c[1] + dy + 26)]
            hv.plate(p, pts, c="#aeb5c0", round_=22)
            hv.trim(p, hv.ell_pts((c[0], c[1] + dy + 6), sx * sc * 0.97, sy * sc * 0.97, deg, n=30, a0=196, a1=344), 4)
    strap = p.tube([(120, 470), (360, 640), (560, 770)], [34, 34])
    p.paint(strap * (1 - 0), hv.mat("#4e2e1a", "leather", round=8), cast=0.5)
    hv.trim(p, [(126, 462), (366, 630), (568, 760)], 1.8, c="#d9a743")
    p.paint(p.ellipse((330, 618), 18, 18), hv.mat("#d9a743", "gold", round=5), cast=0.4)
    # sword hilt over the shoulder
    hv.plate(p, [(600, 330), (620, 316), (700, 430), (684, 444)], c="#b8bec8", round_=4)
    p.paint(p.tube([(614, 300), (575, 240)], [16, 16]), hv.mat("#3b2517", "leather", round=4), cast=0.4)
    p.paint(p.tube([(560, 350), (680, 290)], [12, 12]), hv.mat("#d6a84c", "gold", round=4), cast=0.4)
    p.paint(p.ellipse((570, 232), 13, 13), hv.mat("#d6a84c", "gold", round=6), cast=0.4)
    # head
    b_face(hv, p, F, k, SK, age=1.0, blush=0.15)
    b_ear(hv, p, F, k, SK, big=1.1)
    # grey hair pulled back into the topknot
    hair = p.poly([F(58, -24), F(52, -50), F(22, -66), F(-22, -64), F(-54, -40), F(-60, 0), F(-48, 30), F(-36, 26),
                   F(-30, 4), F(-24, -14), F(10, -30), F(44, -32)], smooth=True)
    hv.hair_mass(p, [hair], [([F(50, -30), F(20, -56), F(-20, -62)], 14 * k), ([F(40, -24), F(0, -46), F(-40, -50)], 14 * k),
                             ([F(-10, -24), F(-40, -30), F(-56, -4)], 12 * k), ([F(54, -18), F(10, -34), F(-30, -10)], 10 * k)],
                 GREY, GREY_L, sheen=(F(0, -30)[0], F(0, -30)[1], 50 * k, 30 * k), round_=12 * k)
    knot = p.ellipse(F(-16, -82), 18 * k, 16 * k)
    hv.hair_mass(p, [knot], [([F(-30, -80), F(-16, -98), F(2, -84)], 12 * k)], GREY, GREY_L, round_=8 * k)
    p.paint(p.tube([F(-26, -66), F(-6, -68)], [7 * k, 7 * k]), hv.mat("#7e1f22", "cloth", round=3 * k), cast=0.3)
    # the good (far) eye, stern
    hv.anime_eye(p, F(48.5, 14.5), 10 * k, 10 * k, ("#3a2a18", "#a08050"), look=0.2, far=True, lash=1.3)
    lid = p.poly([F(43, 7), F(54, 5), F(54, 9), F(43, 10)], smooth=True)
    p.paint(lid, hv.mat(SK, "skin", round=3 * k), cast=0.3, line=0.4)
    # eyepatch over the near eye and its strap
    hv.trim(p, [F(56, -8), F(30, 2), F(-10, 4), F(-36, 14)], 3 * k, c="#2a2224")
    patch = p.poly([F(6, 4), F(34, 2), F(36, 18), F(22, 30), F(8, 24)], smooth=True)
    p.paint(patch, hv.mat("#2a2224", "leather", round=6 * k, spec=0.35), cast=0.5, line=0.8)
    # scar across the brow and cheek
    p.tint(hv.C("#a85a50"), p.tube([F(26, -16), F(20, -4)], [0.6, 2.2 * k, 0.6]) * 0.7)
    p.tint(hv.C("#a85a50"), p.tube([F(18, 32), F(12, 42)], [0.6, 2.0 * k, 0.6]) * 0.7)
    b_brow(hv, p, F(34, -4), F(4, -6), "#d0cac2", 4.6 * k, arch=-1.0 * k, bushy=1)
    b_brow(hv, p, F(42, -2), F(57, -10), "#d0cac2", 3.6 * k, arch=-0.2 * k, bushy=1)
    b_nose_mouth(hv, p, F, k, big=0.6, frown=1.2)
    # braided beard
    outline = [(-30, 26), (-22, 54), (0, 72), (26, 86), (52, 80), (62, 60), (58, 46), (48, 52), (30, 58), (6, 50), (-14, 30)]
    lk = beard_locks(-20, 60, 44, 84, 8, sway=2, w=12, rng=random.Random(4), curl=4)
    b_beard(hv, p, F, k, outline, lk, GREY, GREY_L)
    b_moustache(hv, p, F, k, GREY, GREY_L, size=1.0)
    for i in range(6):
        y = 84 + i * 15
        x = 30 + (i % 2) * 2 - i * 1.2
        seg = p.ellipse(F(x, y), 9 * k * (1 - i * 0.07), 9 * k * 0.95)
        p.paint(seg, hv.mat(GREY, "hair", round=4 * k), cast=0.4, line=0.8)
        p.tint(hv.C(GREY_L), p.tube([F(x - 6, y - 4), F(x + 4, y + 3)], [0.5, 1.6 * k, 0.5]) * seg * 0.6)
    p.paint(p.tube([F(22, 168), F(36, 168)], [6 * k, 6 * k]), hv.mat("#d6a84c", "gold", round=2 * k), cast=0.4)
    p.paint(p.tube([F(24, 106), F(36, 106)], [5 * k, 5 * k]), hv.mat("#d6a84c", "gold", round=2 * k), cast=0.4)
    return bust_finish(hv, p)


NPCS = {"nara": npc_nara, "smith": npc_smith, "merchant": npc_merchant, "innkeeper": npc_innkeeper,
        "keeper": npc_keeper, "class_master": npc_class_master}


def make_npcs(ids=None):
    hv = _hv()
    for nid in ids or NPC_IDS:
        t = time.time()
        img = NPCS[nid](hv)
        save(img, os.path.join(ROOT, "assets", "town", "npc_%s.png" % nid))
        print("  %s %.1fs" % (nid, time.time() - t))


if __name__ == "__main__":
    # python3 tools/art/town_v2.py   -> the painted town layers in assets/town/v2/
    # (make_npcs() holds unfinished bust drafts; the game keeps the npcs.py portraits)
    make_town()

"""Burnt Keep (dungeon 4) monsters as painted cut-out rigs (M8 style).

    python3 tools/art/monsters_d4.py                      # all five
    python3 tools/art/monsters_d4.py cultist fire_imp     # just these

cultist, fire_imp, ember_hound, flame_knight (elite) on a 1024 canvas, ember_priestess (boss) on 1536.
Everything faces left. Each rig goes to assets/rigs/<id>/ (see rig.py) and its still picture to
assets/sprites/enemies/<id>.png (512, the boss 768).

Look: painted semi-realistic key art. Every shape is shaded from a height field made by blurring its own
mask (so it gets rounded form, warm key light from the upper left, a cool core shadow and a fiery rim light
on the far edge), then grain, brush strokes and detail are painted on top. Flames are procedural tongues
(a noise-warped teardrop mapped through a fire ramp) drawn on their own "hair" parts so the game can sway
them, with their glow on separate additive "fx" parts. Everything is painted at 2x and downscaled.
"""
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

import rig as rigmod  # noqa: E402

SS = 2  # supersampling: canvas pixels per design pixel


# ================================================================== colour helpers

def C(h):
    """'#rrggbb' -> float rgb array 0..1."""
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def mixc(a, b, t):
    return np.asarray(a, np.float32) * (1 - t) + np.asarray(b, np.float32) * t


def lighten(c, t):
    return mixc(c, (1.0, 1.0, 1.0), t)


def darken(c, t):
    return np.asarray(c, np.float32) * (1 - t)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


COOL = C("#2a1c48")        # shadows lean toward this
WARM = C("#fff0d0")        # key light leans toward this
RIM_FIRE = C("#ff8a3c")    # fiery rim light on the far edge
BOUNCE = C("#ff5a1c")      # ember bounce light from below
LIGHT = np.array([-0.52, -0.66, 0.54], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)

FIRE_RAMP = [(0.00, C("#5a0a06")), (0.18, C("#a51c0c")), (0.36, C("#e2461a")), (0.55, C("#ff8c24")),
             (0.72, C("#ffc24a")), (0.86, C("#ffe89a")), (1.00, C("#fffbea"))]
BLUE_RAMP = [(0.00, C("#1a0a40")), (0.3, C("#3a2aa0")), (0.55, C("#6a7aff")), (0.8, C("#bfe4ff")),
             (1.0, C("#ffffff"))]


def ramp(v, stops):
    """Maps an array of 0..1 values through colour stops -> (..., 3)."""
    v = np.clip(v, 0.0, 1.0)
    out = np.zeros(v.shape + (3,), np.float32)
    xs = [s[0] for s in stops]
    for ch in range(3):
        out[..., ch] = np.interp(v, xs, [s[1][ch] for s in stops])
    return out


# ================================================================== geometry helpers

def spline(pts, n=10, closed=False):
    """Catmull-Rom through the points."""
    pts = [tuple(p) for p in pts]
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
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    if not closed:
        out.append(pts[-1])
    return out


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def rot(p, c, deg):
    r = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


def polar(c, ang, r):
    a = math.radians(ang)
    return (c[0] + math.cos(a) * r, c[1] + math.sin(a) * r)


def jag(p0, p1, rough=0.25, depth=4, seed=1):
    """Jagged crack path from p0 to p1 by midpoint displacement."""
    rng = random.Random(seed)
    pts = [p0, p1]
    for _ in range(depth):
        new = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy)
            off = rng.uniform(-rough, rough) * ln
            m = ((a[0] + b[0]) / 2 - dy / (ln + 1e-6) * off, (a[1] + b[1]) / 2 + dx / (ln + 1e-6) * off)
            new += [m, b]
        pts = new
    return pts


def path_len(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def resample(pts, step):
    """Points every `step` design px along a polyline (keeps the ends)."""
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        d = step - carry
        while d <= ln:
            out.append(lerp2(a, b, d / ln))
            d += step
        carry = ln - (d - step)
    if out[-1] != pts[-1]:
        out.append(pts[-1])
    return out


# ================================================================== noise

_NOISE = {}


def noise(shape, cell, seed=0, aniso=1.0):
    """Smooth value noise 0..1, float32, of `shape` (h, w) with cells of `cell` px (x cell*aniso)."""
    key = (shape, cell, seed, aniso)
    if key in _NOISE:
        return _NOISE[key]
    h, w = shape
    rng = np.random.default_rng(seed)
    cw, ch = max(1.0, cell * aniso), max(1.0, cell)
    sw, sh = int(w / cw) + 3, int(h / ch) + 3
    small = Image.fromarray((rng.random((sh, sw)) * 255).astype(np.uint8), "L")
    big = small.resize((int(sw * cw), int(sh * ch)), Image.BICUBIC)
    arr = np.asarray(big, np.float32)[int(ch):int(ch) + h, int(cw):int(cw) + w] / 255.0
    if arr.shape != (h, w):
        arr = np.pad(arr, ((0, h - arr.shape[0]), (0, w - arr.shape[1])), mode="edge")
    _NOISE[key] = arr
    return arr


def fbm(shape, cell, seed=0, octaves=3, aniso=1.0):
    key = ("fbm", shape, cell, seed, octaves, aniso)
    if key in _NOISE:
        return _NOISE[key]
    tot, amp, acc = 0.0, 1.0, np.zeros(shape, np.float32)
    for o in range(octaves):
        acc += amp * noise(shape, max(1.0, cell / (2 ** o)), seed + o * 17, aniso)
        tot += amp
        amp *= 0.5
    acc /= tot
    _NOISE[key] = acc
    return acc


def brush_tex(h, w):
    """Painterly stroke texture: stretched noise at two diagonal angles, 0..1."""
    key = ("brush", h, w)
    if key in _NOISE:
        return _NOISE[key]
    acc = np.zeros((h, w), np.float32)
    for ang, seed in ((35, 21), (-50, 22)):
        side = int(math.hypot(h, w)) + 4
        n = noise((side, side), 5.0 * SS, seed, aniso=7.0)
        img = Image.fromarray(n, "F").rotate(ang, resample=Image.BILINEAR)
        ox, oy = (side - w) // 2, (side - h) // 2
        acc += np.asarray(img, np.float32)[oy:oy + h, ox:ox + w]
    acc = (acc - acc.min()) / max(1e-5, acc.max() - acc.min())
    _NOISE[key] = acc
    return acc


def _sample(tex, x, y):
    """Bilinear, wrapping lookup of a 2D texture at float coords."""
    h, w = tex.shape
    x = np.mod(x, w - 1)
    y = np.mod(y, h - 1)
    x0 = np.minimum(x.astype(np.int32), w - 2)
    y0 = np.minimum(y.astype(np.int32), h - 2)
    fx, fy = np.clip(x - x0, 0, 1), np.clip(y - y0, 0, 1)
    a = tex[y0, x0] * (1 - fx) + tex[y0, x0 + 1] * fx
    b = tex[y0 + 1, x0] * (1 - fx) + tex[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def _blur(img_l, r):
    if r < 0.4:
        return img_l
    return img_l.filter(ImageFilter.GaussianBlur(r))


def _box1(a, r, axis):
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float32)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def fblur(a, sigma, direct=False):
    """Float Gaussian blur (three box passes; big radii run on a downsampled copy)."""
    if sigma < 0.5:
        return a
    h, w = a.shape
    f = 1 if direct else max(1, int(sigma / 5))
    if f > 1:
        small = Image.fromarray(a.astype(np.float32), "F").resize((max(1, w // f), max(1, h // f)), Image.BOX)
        b = fblur(np.asarray(small, np.float32), sigma / f)
        up = np.asarray(Image.fromarray(b, "F").resize((w, h), Image.BILINEAR), np.float32)
        return fblur(up, f * 0.9, direct=True)
    wi = math.sqrt(12 * sigma * sigma / 3 + 1)
    r = max(1, int((wi - 1) / 2 + 0.5))
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box1(_box1(out, r, 0), r, 1)
    return out


# ================================================================== masks (full canvas, supersampled "L")

class Masks:
    """Mask factory for one canvas. All coordinates are design pixels; masks are SS times larger."""

    def __init__(self, size):
        self.W, self.H = size[0] * SS, size[1] * SS

    def new(self):
        return Image.new("L", (self.W, self.H), 0)

    @staticmethod
    def _s(pts):
        return [(x * SS, y * SS) for x, y in pts]

    def poly(self, pts, smooth_n=0):
        if smooth_n:
            pts = spline(pts, smooth_n, closed=True)
        m = self.new()
        ImageDraw.Draw(m).polygon(self._s(pts), fill=255)
        return m

    def blob(self, pts, n=10):
        return self.poly(pts, smooth_n=n)

    def ell(self, cx, cy, rx, ry, rot_deg=0.0):
        if rot_deg == 0:
            m = self.new()
            ImageDraw.Draw(m).ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS], fill=255)
            return m
        pts = [rot((cx + rx * math.cos(t), cy + ry * math.sin(t)), (cx, cy), rot_deg)
               for t in np.linspace(0, 2 * math.pi, 72, endpoint=False)]
        return self.poly(pts)

    def circle(self, cx, cy, r):
        return self.ell(cx, cy, r, r)

    def limb(self, pts, widths, n=8, cap=True):
        """Tapered capsule along a (splined) path; widths are full widths at each control point."""
        if len(pts) > 2:
            path = spline(pts, n)
        else:
            path = [lerp2(pts[0], pts[1], t) for t in np.linspace(0, 1, 12)]
        # widths follow the arc length through the control widths
        cum = [0.0]
        for a, b in zip(path, path[1:]):
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        tot = max(cum[-1], 1e-6)
        ws = list(np.interp(np.array(cum) / tot, np.linspace(0, 1, len(widths)), widths))
        left, right = [], []
        for i, p in enumerate(path):
            a = path[max(0, i - 1)]
            b = path[min(len(path) - 1, i + 1)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) + 1e-6
            nx, ny = -dy / ln, dx / ln
            r = ws[i] / 2
            left.append((p[0] + nx * r, p[1] + ny * r))
            right.append((p[0] - nx * r, p[1] - ny * r))
        m = self.new()
        d = ImageDraw.Draw(m)
        d.polygon(self._s(left + right[::-1]), fill=255)
        if cap:
            for i in (0, len(path) - 1):
                r = ws[i] / 2 * SS
                x, y = path[i][0] * SS, path[i][1] * SS
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return m

    def line(self, pts, w, n=6):
        return self.limb(pts, [w] * len(pts), n=n)

    @staticmethod
    def union(*ms):
        out = ms[0]
        for m in ms[1:]:
            out = ImageChops.lighter(out, m)
        return out

    @staticmethod
    def sub(a, b):
        return ImageChops.subtract(a, b)

    @staticmethod
    def inter(a, b):
        return ImageChops.multiply(a, b)

    @staticmethod
    def grow(m, r):
        """Dilate by about r design px (soft)."""
        rr = r * SS
        b = m.filter(ImageFilter.GaussianBlur(rr / 2))
        return b.point(lambda v: 0 if v < 4 else min(255, (v - 4) * 8))

    @staticmethod
    def shrink(m, r):
        rr = r * SS
        b = m.filter(ImageFilter.GaussianBlur(rr / 2))
        return b.point(lambda v: 0 if v < 230 else min(255, (v - 230) * 10))


# ================================================================== paint layer

def _bbox(m, pad, W, H):
    bb = m.getbbox()
    if bb is None:
        return None
    return (max(0, bb[0] - pad), max(0, bb[1] - pad), min(W, bb[2] + pad), min(H, bb[3] + pad))


class Layer:
    """One full-canvas RGBA part, painted supersampled. Straight alpha, float math on crops."""

    def __init__(self, size):
        self.size = size
        self.W, self.H = size[0] * SS, size[1] * SS
        self.img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.M = Masks(size)

    # ---------------------------------------------------------- low level
    def _get(self, box):
        return np.asarray(self.img.crop(box), np.float32) / 255.0

    def _put(self, box, arr):
        arr = np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8)
        self.img.paste(Image.fromarray(arr, "RGBA"), box[:2])

    def _over(self, box, rgb, a):
        """Normal composite of rgb (h,w,3) with alpha a (h,w) into the crop."""
        d = self._get(box)
        da = d[..., 3]
        oa = a + da * (1 - a)
        safe = np.where(oa > 1e-5, oa, 1.0)
        orgb = (rgb * a[..., None] + d[..., :3] * (da * (1 - a))[..., None]) / safe[..., None]
        d[..., :3] = orgb
        d[..., 3] = oa
        self._put(box, d)

    def _atop(self, box, rgb, a):
        """Paint only over what is already there (alpha unchanged)."""
        d = self._get(box)
        d[..., :3] = d[..., :3] * (1 - a[..., None]) + rgb * a[..., None]
        self._put(box, d)

    def _add(self, box, rgb, a):
        """Additive light onto existing pixels (clamped)."""
        d = self._get(box)
        d[..., :3] = np.clip(d[..., :3] + rgb * a[..., None], 0, 1)
        self._put(box, d)

    def alpha(self):
        return self.img.getchannel("A")

    # ---------------------------------------------------------- basic fills
    def fill(self, m, color, alpha=1.0, blur=0.0, mode="over"):
        box = _bbox(m, int(blur * SS * 3) + 2, self.W, self.H)
        if box is None:
            return
        mc = m.crop(box)
        if blur:
            mc = _blur(mc, blur * SS)
        a = np.asarray(mc, np.float32) / 255.0 * alpha
        rgb = np.broadcast_to(np.asarray(color, np.float32), a.shape + (3,))
        {"over": self._over, "atop": self._atop, "add": self._add}[mode](box, rgb, a)

    def brush(self, pts, width, color, alpha=1.0, blur=0.6, clip=None, taper=(1.0, 1.0), mode="atop", n=6):
        """Soft painted stroke (folds, highlights, strands). taper = (start, end) width factors."""
        if len(pts) < 2:
            return
        if taper == (1.0, 1.0):
            m = self.M.line(pts, width, n=n)
        else:
            ws = list(np.linspace(width * taper[0], width * taper[1], len(pts)))
            m = self.M.limb(pts, ws, n=n)
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        self.fill(m, color, alpha, blur, mode)

    def grad(self, clip, p0, p1, color, a0=0.0, a1=1.0, mode="atop"):
        """Linear gradient of `color` from alpha a0 at p0 to a1 at p1, inside clip."""
        box = _bbox(clip, 2, self.W, self.H)
        if box is None:
            return
        x0, y0, x1, y1 = box
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        ax, ay = p0[0] * SS, p0[1] * SS
        bx, by = p1[0] * SS, p1[1] * SS
        dx, dy = bx - ax, by - ay
        t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / (dx * dx + dy * dy + 1e-6), 0, 1)
        a = (a0 + (a1 - a0) * t) * np.asarray(clip.crop(box), np.float32) / 255.0
        rgb = np.broadcast_to(np.asarray(color, np.float32), a.shape + (3,))
        {"over": self._over, "atop": self._atop, "add": self._add}[mode](box, rgb, a)

    def radial(self, center, r, color, strength=1.0, clip=None, mode="atop", power=1.6):
        """Radial falloff of colour (glow, spill light, AO spot)."""
        cx, cy, rr = center[0] * SS, center[1] * SS, r * SS
        box = (max(0, int(cx - rr)), max(0, int(cy - rr)), min(self.W, int(cx + rr) + 1), min(self.H, int(cy + rr) + 1))
        if box[2] <= box[0] or box[3] <= box[1]:
            return
        ys, xs = np.mgrid[box[1]:box[3], box[0]:box[2]].astype(np.float32)
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / rr
        a = np.clip(1 - d, 0, 1) ** power * strength
        if clip is not None:
            a = a * np.asarray(clip.crop(box), np.float32) / 255.0
        rgb = np.broadcast_to(np.asarray(color, np.float32), a.shape + (3,))
        {"over": self._over, "atop": self._atop, "add": self._add}[mode](box, rgb, np.clip(a, 0, 1))

    def shadow(self, m, strength=0.45, offset=(3, 4), blur=5, color=None):
        """Soft shadow cast by mask m onto what is painted (outside m)."""
        color = C("#140a18") if color is None else color
        sh = ImageChops.offset(m, int(offset[0] * SS), int(offset[1] * SS))
        sh = _blur(sh, blur * SS)
        sh = ImageChops.subtract(sh, m)
        sh = ImageChops.multiply(sh, self.alpha())
        self.fill(sh, color, strength, mode="atop")

    def ao(self, m, strength=0.5, r=6, color=None):
        """Darkens the inside of m near its border (occlusion where it tucks under something)."""
        color = C("#140a18") if color is None else color
        inner = ImageChops.subtract(m, _blur(Masks.shrink(m, r * 0.4), r * SS * 0.8))
        self.fill(ImageChops.multiply(inner, self.alpha()), color, strength, blur=r * 0.3, mode="atop")

    # ---------------------------------------------------------- the painter
    def paint(self, m, base, round_=None, bulge=4.0, wrap=0.25, shadow=0.22, cool=0.35, light=0.38,
              rim=0.55, rim_c=None, bounce=0.3, spec=0.0, gloss=24.0, spec_c=None, metal=0.0,
              env=None, tex=0.10, tex_cell=3.0, grain=0.06, streak=0.0, line=1.0, line_c=None,
              far=0.0, vgrad=0.15, soft=0.7, mode="over", clip=None, form=0.3, brush=0.07):
        """Paints mask m as a lit, rounded form.

        base      mid-tone colour (rgb 0..1)
        round_    form radius in design px (how far the edge falloff reaches); default ~30% of the thin side
        shadow    darkness of the core shadow (fraction of base); cool = how much it leans to COOL
        light     how far the lit side goes toward WARM
        rim       far-edge (right) fiery rim light; bounce = warm light from below
        spec      specular strength (gloss = exponent); metal 0..1 mixes in an environment reflection
        tex       mottled texture amount, grain = fine noise, streak = vertical brush streaks
        line      thin colour-matched contour that fades where the light hits
        far       0..1 pushes the part back (darker, cooler, hazier)
        """
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        bb = m.getbbox()
        if bb is None:
            return m
        bw, bh = (bb[2] - bb[0]) / SS, (bb[3] - bb[1]) / SS
        r = round_ if round_ is not None else max(3.0, 0.42 * min(bw, bh))
        pad = int(r * SS * 2.2) + 6
        box = _bbox(m, pad, self.W, self.H)
        mc = m.crop(box)
        if soft:
            mc = _blur(mc, soft)
        A = np.asarray(mc, np.float32) / 255.0
        rs = r * SS
        h1 = fblur(A, rs * 0.55)
        h2 = fblur(A, rs * 0.18)
        Hf = 0.72 * h1 + 0.28 * h2
        gy, gx = np.gradient(Hf)
        k = rs * bulge
        nx, ny, nz = -gx * k, -gy * k, np.ones_like(gx)
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx * inv, ny * inv, nz * inv
        diff = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
        v = np.clip((diff + wrap) / (1 + wrap), 0, 1)
        # the whole figure is lit from the top left: lower parts a touch darker
        ys = np.arange(box[1], box[3], dtype=np.float32)[:, None] / self.H
        v = v - vgrad * np.clip((ys - 0.35) / 0.65, 0, 1)
        mid = (LIGHT[2] + wrap) / (1 + wrap)
        if form:
            # broad turn of the form: the side toward the key light is lighter across the whole shape
            xs = np.arange(box[0], box[2], dtype=np.float32)[None, :]
            bx0, by0, bx1, by1 = bb
            tx = (xs - bx0) / max(1.0, bx1 - bx0)
            ty = (ys * self.H - by0) / max(1.0, by1 - by0)
            v = v + form * (0.5 - np.clip(0.62 * tx + 0.38 * ty, 0, 1)) * smooth(0.0, 0.3, Hf)
        if brush:
            v = v + brush * (brush_tex(self.H, self.W)[box[1]:box[3], box[0]:box[2]] - 0.5)
        if tex:
            v = v + tex * (fbm((self.H, self.W), tex_cell * SS * 4, 3)[box[1]:box[3], box[0]:box[2]] - 0.5)
        if grain:
            v = v + grain * (noise((self.H, self.W), SS * 0.9, 7)[box[1]:box[3], box[0]:box[2]] - 0.5)
        if streak:
            v = v + streak * (noise((self.H, self.W), SS * 1.4, 11, aniso=0.08)[box[1]:box[3], box[0]:box[2]] - 0.5)
        base = np.asarray(base, np.float32)
        dark = mixc(darken(base, 1 - shadow), COOL, cool)
        lit = np.clip(base * (1 + light * 0.9) + WARM * light * 0.16 + 0.03 * light, 0, 1)
        t_lo = np.clip(v / mid, 0, 1)[..., None]
        t_hi = np.clip((v - mid) / (1 - mid), 0, 1)[..., None]
        col = np.where((v < mid)[..., None], dark + (base - dark) * (t_lo ** 0.9), base + (lit - base) * t_hi)
        if metal:
            env = env or [(0.0, C("#f4e6d0")), (0.35, C("#8a8490")), (0.52, C("#1a161e")), (0.7, C("#3a2226")),
                          (1.0, C("#ff7a2a"))]
            refl = ramp(ny * 0.5 + 0.5 + 0.18 * (nx), env)
            col = col * (1 - metal) + refl * metal * (0.55 + 0.45 * v[..., None] / max(mid, 1e-3))
        if rim:
            rim_c = RIM_FIRE if rim_c is None else rim_c
            rv = smooth(0.2, 0.7, nx) * smooth(0.45, 0.85, 1 - nz) * rim
            col = col + (np.asarray(rim_c) - col) * rv[..., None]
        if bounce:
            bv = smooth(0.1, 0.8, ny) * smooth(0.0, 0.5, 1 - nz) * bounce
            col = col + BOUNCE * bv[..., None] * 0.6
        if spec:
            sd = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1)
            sv = sd ** gloss * spec
            spec_c = WARM if spec_c is None else spec_c
            col = col + (np.asarray(spec_c) - col) * np.clip(sv, 0, 1)[..., None]
        if far:
            haze = mixc(darken(base, 0.55), COOL, 0.5)
            col = col * (1 - far) + haze * far
        col = np.clip(col, 0, 1)
        if line:
            er = mc.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MinFilter(3))
            edge = np.clip(A - np.asarray(_blur(er, 0.8), np.float32) / 255.0, 0, 1)
            lc = mixc(darken(base, 0.8), COOL, 0.4) if line_c is None else line_c
            la = edge * line * (1 - 0.8 * smooth(0.45, 0.85, v))
            col = col + (lc - col) * la[..., None]
        if mode == "atop":
            self._atop(box, col, A)
        else:
            self._over(box, col, A)
        return m

    # ---------------------------------------------------------- fire
    def flame(self, base, tip, width, seed=1, bend=0.0, turb=0.6, hot=1.0, alpha=1.0, stops=None, breakup=0.6):
        """One flame tongue from base (round bottom) to tip. width = full width at the widest point.
        turb sways the tongue like a licking flame; breakup tears wisps off near the tip."""
        stops = FIRE_RAMP if stops is None else stops
        bx, by = base[0] * SS, base[1] * SS
        tx, ty = tip[0] * SS, tip[1] * SS
        L = math.hypot(tx - bx, ty - by) + 1e-6
        W = width * SS / 2
        ax, ay = (tx - bx) / L, (ty - by) / L
        px, py = -ay, ax
        ext = W * (1.6 + turb * 1.4) + abs(bend) * L
        xs_ = [bx - ax * W * 1.2 + px * ext, bx - ax * W * 1.2 - px * ext, tx + px * ext, tx - px * ext]
        ys_ = [by - ay * W * 1.2 + py * ext, by - ay * W * 1.2 - py * ext, ty + py * ext, ty - py * ext]
        box = (max(0, int(min(xs_))), max(0, int(min(ys_))), min(self.W, int(max(xs_)) + 1),
               min(self.H, int(max(ys_)) + 1))
        if box[2] <= box[0] or box[3] <= box[1]:
            return
        ys, xs = np.mgrid[box[1]:box[3], box[0]:box[2]].astype(np.float32)
        u = ((xs - bx) * ax + (ys - by) * ay) / L
        v = ((xs - bx) * px + (ys - by) * py) / W
        uc = np.clip(u, 0, 1)
        rng = np.random.default_rng(seed)
        sway = np.zeros_like(u)
        for f, a in ((0.55, 0.9), (1.2, 0.45), (2.3, 0.22)):
            sway += a * np.sin(2 * math.pi * f * uc * (L / (W * 5)) ** 0.5 + rng.uniform(0, 6.3))
        v2 = v - bend * uc ** 2 * (L / W) + turb * uc ** 1.3 * sway
        nsrc = fbm((512, 512), 20, 5, 3)
        ox, oy = rng.uniform(0, 500), rng.uniform(0, 500)
        asp = (L / W) ** 0.5
        rag = _sample(nsrc, v * 7 + ox, u * 9 * asp + oy) - 0.5
        v2 = v2 + rag * 0.9 * turb * uc
        wprof = np.where(u < 0.2, np.sqrt(np.clip(1 - ((0.2 - u) / 0.26) ** 2, 0, 1)),
                         np.clip((1 - u) / 0.8, 0, 1) ** 1.15)
        inside = np.where(wprof > 1e-3, 1 - np.abs(v2) / np.maximum(wprof, 1e-3), -1)
        brk = _sample(nsrc, v * 12 + ox * 1.7, u * 16 * asp + oy * 1.3)
        inside = inside - smooth(0.3, 0.9, uc) * np.clip(brk - 0.3, 0, 1) * 2.4 * breakup
        edge_a = smooth(-0.04, 0.16, inside)
        heat = np.clip(inside, 0, 1) ** 0.8 * (1.02 - 0.85 * uc ** 0.9) * hot + rag * 0.4
        heat = np.clip(heat + 0.16 * (1 - uc) ** 2 * hot, 0, 1)
        rgb = ramp(heat, stops)
        a = edge_a * np.clip(0.45 + heat * 1.3, 0, 1) * alpha
        # thin red haze just outside the tongue
        a = np.maximum(a, smooth(-0.35, 0.0, inside) * 0.18 * alpha * (1 - uc))
        self._over(box, rgb, np.clip(a, 0, 1))

    def fire(self, base, tip, width, seed=1, bend=0.0, tongues=3, spread=0.45, turb=0.6, hot=1.0, alpha=1.0,
             stops=None):
        """A cluster of tongues: a back row of darker side licks and a hot main tongue in front."""
        rng = random.Random(seed)
        L = math.hypot(tip[0] - base[0], tip[1] - base[1])
        ang = math.degrees(math.atan2(tip[1] - base[1], tip[0] - base[0]))
        for i in range(tongues):
            side = (-1) ** i * (1 + i // 2)
            off = side * width * spread * 0.45
            nb = polar(base, ang + 90, off)
            ln = L * rng.uniform(0.45, 0.75)
            nt = polar(nb, ang + side * rng.uniform(6, 16), ln)
            self.flame(nb, nt, width * rng.uniform(0.45, 0.65), seed * 31 + i, bend + side * 0.05, turb, hot * 0.8,
                       alpha * 0.95, stops)
        self.flame(base, tip, width, seed * 7 + 3, bend, turb, hot, alpha, stops)

    # ---------------------------------------------------------- lava seams
    def seam(self, pts, width, clip=None, glow=1.0, core=True, seed=1, spill=1.0, n=4):
        """Glowing crack: charred lips, orange channel, white-hot core, light spilling onto the surface."""
        clip = self.alpha() if clip is None else clip
        base_w = width
        if spill:
            self.brush(pts, base_w * 7, C("#ff5a14"), 0.28 * glow * spill, blur=base_w * 3.0, clip=clip, n=n)
        self.brush(pts, base_w * 2.1, C("#1a0806"), 0.75, blur=0.8, clip=clip, taper=(0.5, 0.3), n=n)
        self.brush(pts, base_w * 1.25, C("#d8360e"), 1.0, blur=0.5, clip=clip, taper=(0.55, 0.25), n=n)
        self.brush(pts, base_w * 0.8, C("#ff9a2a"), 1.0, blur=0.4, clip=clip, taper=(0.6, 0.2), n=n)
        if core:
            self.brush(pts, base_w * 0.35, C("#fff2c0"), 0.95, blur=0.3, clip=clip, taper=(0.7, 0.15), n=n)

    def spark(self, x, y, r, color=None, core=None):
        color = C("#ff9a2a") if color is None else color
        core = C("#fff4c8") if core is None else core
        self.radial((x, y), r * 3.2, color, 0.55, mode="over", power=2.2)
        self.fill(self.M.circle(x, y, r * 0.6), core, 1.0, blur=0.4, mode="over")


# ================================================================== rig wrapper

class Rig:
    """Collects painted parts and writes the rig, its flat picture and fx-aware preview."""

    def __init__(self, rid, size, feet, kind="humanoid", flat_size=512):
        self.id = rid
        self.size = (size, size) if isinstance(size, int) else tuple(size)
        self.rb = rigmod.RigBuilder(rid, self.size, feet, facing="left", kind=kind)
        self.flat_size = flat_size
        self.M = Masks(self.size)
        self.pending = []
        self.nocast = set()

    def layer(self):
        return Layer(self.size)

    def add(self, name, layer, parent, role, pivot, z, blend="normal", cast=True):
        """Queues a part; parents may be added later (save() orders them). cast=False: no contact shadow
        (flames and other glowing parts)."""
        if not cast:
            self.nocast.add(name)
        img = layer.img.resize(self.size, Image.LANCZOS) if SS != 1 else layer.img
        self.pending.append((name, img, parent, role, pivot, z, blend))
        layer.img = None

    def occlude(self, strength=0.42, blur=7, offset=(3, 6), soft_roles=("arm_front_upper", "arm_front_lower",
                                                                         "weapon", "offhand", "arm_back_upper",
                                                                         "arm_back_lower", "wing_front", "tail")):
        """Bakes a soft contact shadow of every part onto the parts under it (at rest), so the cut-out pieces
        sit in one space. Glowing parts (role fx/hair flames in self.nocast) cast none; parts that swing far
        (arms, weapons) cast a weaker, wider one so it never reads as a ghost when they move."""
        parts = list(self.pending)
        W, H = self.size
        casters = []
        for t in parts:
            name, img, parent, role, pivot, z, blend = t
            if blend == "add" or name in self.nocast:
                continue
            a = img.getchannel("A")
            k = 0.45 if role in soft_roles else 1.0
            casters.append((z, name, a, k))
        out = []
        for t in parts:
            name, img, parent, role, pivot, z, blend = t
            if blend == "add" or name in self.nocast:
                out.append(t)
                continue
            hard = Image.new("L", (W, H), 0)
            soft = Image.new("L", (W, H), 0)
            for cz, cname, ca, k in casters:
                if cz > z and cname != name:
                    if k >= 1:
                        hard = ImageChops.lighter(hard, ca)
                    else:
                        soft = ImageChops.lighter(soft, ca)
            sh = ImageChops.offset(hard, offset[0], offset[1]).filter(ImageFilter.GaussianBlur(blur))
            sh2 = ImageChops.offset(soft, offset[0], offset[1]).filter(ImageFilter.GaussianBlur(blur * 2))
            sh = ImageChops.lighter(sh, sh2.point(lambda v: v * 45 // 100))
            if sh.getbbox() is None:
                out.append(t)
                continue
            arr = np.asarray(img, np.float32) / 255.0
            d = np.asarray(sh, np.float32)[..., None] / 255.0 * strength
            arr[..., :3] = arr[..., :3] * (1 - d) + C("#12081a") * d
            img = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
            out.append((name, img, parent, role, pivot, z, blend))
        self.pending = out

    def grade(self, warm=0.10, cool=0.22):
        """One light over the whole figure: warmer and brighter toward the upper left, cooler and darker toward
        the lower right and the feet (applied to every part at its rest position)."""
        W, H = self.size
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.clip((xs / W) * 0.45 + (ys / H) * 0.75 - 0.35, 0, 1)
        out = []
        for t in self.pending:
            name, img, parent, role, pivot, z, blend = t
            if blend == "add" or name in self.nocast:
                out.append(t)
                continue
            bb = img.getbbox()
            if bb is None:
                out.append(t)
                continue
            x0, y0, x1, y1 = bb
            arr = np.asarray(img.crop(bb), np.float32) / 255.0
            dd = d[y0:y1, x0:x1, None]
            rgb = arr[..., :3]
            rgb = rgb * (1 + warm * (1 - dd) * np.array([1.0, 0.85, 0.6], np.float32))
            rgb = rgb * (1 - cool * dd) + COOL * (cool * 0.35 * dd)
            arr[..., :3] = np.clip(rgb, 0, 1)
            img = img.copy()
            img.paste(Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBA"), (x0, y0))
            out.append((name, img, parent, role, pivot, z, blend))
        self.pending = out

    def _commit(self):
        self.grade()
        self.occlude()
        todo, done = list(self.pending), set()
        while todo:
            ready = [t for t in todo if t[2] == "" or t[2] in done]
            if not ready:
                raise ValueError(f"{self.id}: unknown parents {[(t[0], t[2]) for t in todo]}")
            for t in ready:
                self.rb.add(*t)
                done.add(t[0])
                todo.remove(t)
        self.pending = []

    def flat(self):
        """Normal parts composited, fx parts added on top as light (like the game draws them)."""
        out = Image.new("RGBA", self.size, (0, 0, 0, 0))
        for p in sorted(self.rb.parts, key=lambda p: p["z"]):
            if p["blend"] == "add":
                out = add_light(out, p["img"])
            else:
                out.alpha_composite(p["img"])
        return out

    def save(self):
        self._commit()
        self.rb.save(flat=None)
        img = self.flat()
        if self.flat_size and img.size[0] != self.flat_size:
            img = img.resize((self.flat_size, int(self.flat_size * img.size[1] / img.size[0])), Image.LANCZOS)
        path = os.path.join(ROOT, "assets", "sprites", "enemies", self.id + ".png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path, optimize=True)
        print("wrote", os.path.relpath(path, ROOT))


def add_light(dst, src):
    """Additive blend of src (rgb * a) onto dst; where dst is transparent the glow shows as a soft halo."""
    d = np.asarray(dst, np.float32) / 255.0
    s = np.asarray(src, np.float32) / 255.0
    sa = s[..., 3:4]
    light = s[..., :3] * sa
    da = d[..., 3:4]
    rgb_on = np.clip(d[..., :3] + light, 0, 1)
    # outside the figure: premultiplied glow over transparency
    oa = np.clip(da + sa * (1 - da), 0, 1)
    rgb = (rgb_on * da + s[..., :3] * sa * (1 - da)) / np.maximum(oa, 1e-5)
    out = np.concatenate([np.clip(rgb, 0, 1), oa], axis=-1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def glow_layer(L, spots, clip=None):
    """Fills an fx layer with radial glows: spots = [(x, y, r, colour, strength), ...]."""
    for x, y, r, col, st in spots:
        L.radial((x, y), r, col, st, mode="over", power=1.8)
    return L


# ================================================================== shared anatomy helpers

def limb(L, pts, widths, color, n=8, **kw):
    """Paints a tapered limb and returns its mask."""
    m = L.M.limb(pts, widths, n=n)
    L.paint(m, color, **kw)
    return m


def fold(L, clip, pts, width, dark=True, alpha=0.45, blur=None, color=None):
    """A cloth fold: a soft dark valley with a lit ridge beside it (up-left of it)."""
    blur = width * 0.7 if blur is None else blur
    col = (C("#12060e") if dark else C("#ffe6c8")) if color is None else color
    if dark:
        L.brush([(x - width * 0.35, y - width * 0.35) for x, y in pts], width * 0.7, C("#ffe0c0"), alpha * 0.22,
                blur=blur, clip=clip, taper=(0.2, 1.0))
    L.brush(pts, width, col, alpha, blur=blur, clip=clip, taper=(0.15, 1.0))


def drape(L, clip, focus, freq=9.0, amp=0.5, seed=1, r0=20, r1=160, dark=None, lit=None, warp=0.6):
    """Hanging cloth folds radiating from `focus` (a belt, a shoulder): alternating shadowed valleys and lit
    ridges whose phase follows the angle around the focus, fading in from r0 to r1 design px."""
    dark = C("#12040c") if dark is None else dark
    lit = C("#ffd0b0") if lit is None else lit
    box = _bbox(clip, 2, L.W, L.H)
    if box is None:
        return
    ys, xs = np.mgrid[box[1]:box[3], box[0]:box[2]].astype(np.float32)
    fx, fy = focus[0] * SS, focus[1] * SS
    ang = np.arctan2(xs - fx, ys - fy)
    dist = np.sqrt((xs - fx) ** 2 + (ys - fy) ** 2) / SS
    rng = np.random.default_rng(seed)
    nz = noise((L.H, L.W), 90 * SS, seed + 3)[box[1]:box[3], box[0]:box[2]]
    ph = ang * freq * 2 + warp * 3 * (nz - 0.5) + rng.uniform(0, 6)
    f = np.sin(ph) + 0.3 * np.sin(2 * ph + 1.3)
    k = smooth(r0, r1, dist) * np.asarray(clip.crop(box), np.float32) / 255.0 * amp
    dv = smooth(0.1, -0.9, f) * k
    lv = smooth(0.4, 1.1, f) * k * 0.5
    L._atop(box, np.broadcast_to(dark, dv.shape + (3,)), np.clip(dv * 0.6, 0, 1))
    L._atop(box, np.broadcast_to(lit, lv.shape + (3,)), np.clip(lv * 0.4, 0, 1))


def fingers(L, root, ang, lengths, width, color, spread=14, curl=0.0, **kw):
    """Fingers fanned from a knuckle line; returns the union mask."""
    ms = []
    n = len(lengths)
    for i, ln in enumerate(lengths):
        a = ang + (i - (n - 1) / 2) * spread
        base = polar(root, ang + 90, (i - (n - 1) / 2) * width * 0.95)
        mid = polar(base, a, ln * 0.55)
        tip = polar(mid, a + curl, ln * 0.5)
        ms.append(L.M.limb([base, mid, tip], [width, width * 0.92, width * 0.72], n=4))
    m = Masks.union(*ms)
    L.paint(m, color, round_=width * 0.5, **kw)
    return m


def eye_glow(L, x, y, r, color=None, slant=0.0):
    """Burning eye: almond of fire with a white-hot core."""
    color = C("#ff8a1e") if color is None else color
    L.radial((x, y), r * 3.5, color, 0.55, mode="over", power=2.0)
    m = L.M.ell(x, y, r * 1.25, r * 0.6, slant)
    L.fill(m, mixc(color, C("#fff0a0"), 0.4), 1.0, blur=0.5, mode="over")
    L.fill(L.M.ell(x, y, r * 0.6, r * 0.3, slant), C("#fffbe8"), 1.0, blur=0.4, mode="over")


def fx_glow(R, spots):
    """A new additive fx layer with radial glows [(x, y, r, colour, strength)]."""
    F = R.layer()
    for x, y, r, col, st in spots:
        F.radial((x, y), r, col, st, mode="over", power=1.7)
    return F


# ================================================================== cultist

ROBE = C("#8a1a1e")
ROBE_D = C("#4e0c14")
LINING = C("#20121a")
GOLD = C("#d9a24a")
GOLD_D = C("#8a5a22")
ASH_SKIN = C("#c09080")
LEATHER = C("#3e2a22")
CLOTH_D = C("#2a2028")


def flame_sigil(L, cx, cy, size, clip=None, glow=1.0):
    """The cult's mark: a gold three-tongued flame around a burning eye."""
    k = size / 30.0
    def P(pts):
        return [(cx + x * k, cy + y * k) for x, y in pts]
    outer = P([(0, -30), (8, -14), (18, -22), (16, -2), (22, 10), (10, 22), (0, 26), (-10, 22), (-22, 10), (-16, -2),
               (-18, -22), (-8, -14)])
    m = L.M.blob(outer, n=5)
    inner = L.M.blob(P([(0, -14), (6, 0), (10, 12), (0, 18), (-10, 12), (-6, 0)]), n=5)
    ring = Masks.sub(m, inner)
    if clip is not None:
        ring = Masks.inter(ring, clip)
    L.shadow(ring, 0.6, (2, 3), 2)
    L.paint(ring, GOLD, round_=3 * k, spec=1.0, metal=0.5, gloss=12, line=0.6)
    L.fill(L.M.ell(cx, cy + 6 * k, 6 * k, 4 * k), C("#ff9a2a"), glow, blur=0.6 * k, mode="over")
    L.fill(L.M.ell(cx, cy + 6 * k, 3 * k, 2 * k), C("#fff2c0"), glow, blur=0.4, mode="over")


def gold_trim(L, pts, w, clip=None):
    L.brush(pts, w + 2.5, C("#2a1206"), 0.7, blur=0.8, clip=clip)
    L.brush(pts, w, GOLD, 1.0, blur=0.5, clip=clip)
    L.brush([(x - w * 0.18, y - w * 0.18) for x, y in pts], w * 0.35, C("#fff0c0"), 0.8, blur=0.5, clip=clip)


def boot(L, knee, ankle, toe, heel, color=LEATHER, top_w=56, far=0.0):
    """Shin with a wrapped leather boot; returns the mask."""
    M = L.M
    shin = M.limb([knee, lerp2(knee, ankle, 0.5), ankle], [top_w, top_w * 0.86, top_w * 0.7])
    foot = M.blob([lerp2(ankle, heel, 0.2), (heel[0], heel[1] - 30), heel, (toe[0] + 14, toe[1]), (toe[0], toe[1] - 8),
                   (toe[0] + 10, toe[1] - 26), (ankle[0] - 22, ankle[1] + 6)], n=8)
    m = Masks.union(shin, foot)
    L.paint(m, color, round_=18, tex=0.14, spec=0.25, gloss=16, far=far)
    # sole and toe cap
    L.brush([(toe[0] + 4, toe[1] - 3), (heel[0], heel[1] - 3)], 7, C("#140c0c"), 0.9, blur=0.6, clip=m)
    # wraps up the shin
    for i in range(5):
        t = 0.52 + i * 0.1
        c = lerp2(knee, ankle, t)
        w = top_w * (0.9 - 0.2 * t)
        L.brush([(c[0] - w * 0.55, c[1] - 6), (c[0] + w * 0.55, c[1] + 6)], 5, C("#140a0a"), 0.6, blur=1.0, clip=m)
        L.brush([(c[0] - w * 0.55, c[1] - 9), (c[0] + w * 0.1, c[1] - 4)], 3, C("#a07860"), 0.35 * (1 - far), blur=0.8,
                clip=m)
    return m


def tatter(pts, depth=18, seed=1, step=22):
    """Ragged cloth hem along a polyline: irregular points and tears (depth along +y-ish normal)."""
    rng = random.Random(seed)
    path = resample(spline(pts, 6), step)
    out = []
    for i, (x, y) in enumerate(path):
        a = path[max(0, i - 1)]
        b = path[min(len(path) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) + 1e-6
        nx, ny = dy / ln, -dx / ln  # right-hand normal (downward for a left-to-right hem ... flipped below)
        if ny < 0:
            nx, ny = -nx, -ny
        d = rng.uniform(-0.25, 1.0) * depth if i % 2 else rng.uniform(-0.3, 0.2) * depth
        out.append((x + nx * d, y + ny * d))
    return out


def ember_edge(L, hem, clip, w=5, seed=1, glow=1.0):
    """Burning hem: a glowing ember line with hot spots along a tattered edge."""
    rng = random.Random(seed)
    L.brush(hem, w * 2.2, C("#200604"), 0.7, blur=w * 0.6, clip=clip)
    L.brush(hem, w, C("#ff7a24"), 0.85 * glow, blur=w * 0.35, clip=Masks.grow(clip, 1.5))
    for x, y in hem[::2]:
        if rng.random() < 0.6:
            L.radial((x, y), w * 5, C("#ff5a14"), 0.45 * glow, clip=clip)
            L.fill(L.M.circle(x, y, w * 0.35), C("#ffe8a0"), 0.9 * glow, blur=0.6, mode="atop")


def cultist():
    R = Rig("cultist", 1024, feet=(512, 972), kind="humanoid")
    M = R.M
    RB = C("#9e2428")      # robe red
    RBD = C("#5a1018")     # darker robe
    TUN = C("#221a20")     # black under-tunic
    FIRE = (738, 418)      # the flame in the palm (light source)

    def firelight(L, clip, r=300, st=0.4):
        L.radial(FIRE, r, C("#ff6a1a"), st, clip=clip)

    # ---------------- robe back (cape): long tattered tail of the robe behind the legs
    L = R.layer()
    hem = tatter([(470, 926), (540, 942), (620, 948), (700, 940), (770, 926), (812, 912)], 28, seed=3)
    m = M.poly([(456, 530), (570, 522), (646, 580), (720, 690), (780, 810), (814, 910)] + hem[::-1] +
               [(470, 800), (456, 660)])
    L.paint(m, RBD, round_=70, far=0.3, tex=0.12, rim=0.7)
    drape(L, m, (540, 420), freq=8, amp=0.9, seed=2, r0=100, r1=260)
    for pts in [[(560, 580), (600, 760), (640, 930)], [(630, 610), (700, 760), (760, 915)],
                [(510, 620), (520, 780), (530, 930)], [(590, 700), (640, 820), (700, 935)],
                [(680, 700), (740, 830), (790, 915)]]:
        fold(L, m, spline(pts, 6), 18, alpha=0.6)
    firelight(L, m, 330, 0.35)
    ember_edge(L, hem, m, 5, seed=4)
    R.add("robe_back", L, "hips", "cape", (560, 552), 10)

    # ---------------- back leg (stretched back)
    L = R.layer()
    th = limb(L, [(556, 556), (590, 650), (620, 752)], [96, 84, 66], TUN, far=0.3, tex=0.1)
    fold(L, th, spline([(575, 620), (600, 690), (612, 740)], 4), 9, alpha=0.45)
    R.add("leg_back_upper", L, "hips", "leg_back_upper", (560, 585), 22)
    L = R.layer()
    boot(L, (620, 736), (660, 915), (608, 968), (696, 962), far=0.3, top_w=64)
    R.add("leg_back_lower", L, "leg_back_upper", "leg_back_lower", (618, 748), 20)

    # ---------------- back arm (raised palm with the ritual flame)
    L = R.layer()
    up = limb(L, [(580, 318), (620, 380), (652, 434)], [90, 82, 68], RBD, far=0.25, tex=0.12)
    fold(L, up, spline([(598, 350), (626, 400), (644, 428)], 4), 10, alpha=0.45)
    firelight(L, up, 200, 0.45)
    R.add("arm_back_upper", L, "torso", "arm_back_upper", (582, 340), 30)
    L = R.layer()
    L.paint(M.limb([(700, 430), (724, 424)], [32, 30]), ASH_SKIN, far=0.1, round_=10)
    hand = M.blob([(704, 412), (730, 404), (762, 408), (776, 424), (748, 438), (712, 440)], n=6)
    L.paint(hand, ASH_SKIN, rim=0.9)
    fingers(L, (768, 414), -74, [27, 32, 30, 24], 9.5, ASH_SKIN, spread=11, curl=-30, rim=0.9)
    fingers(L, (716, 412), -110, [26], 11, ASH_SKIN, rim=0.9)  # thumb
    sl = M.blob([(630, 404), (676, 406), (716, 420), (738, 456), (726, 530), (700, 556), (686, 516), (664, 476),
                 (632, 462)], n=8)
    L.paint(sl, RB, far=0.2, tex=0.12, round_=30)
    drape(L, sl, (640, 380), freq=9, amp=0.8, seed=7, r0=30, r1=120)
    lin = M.blob([(716, 424), (740, 456), (728, 530), (708, 546), (718, 490), (704, 446)], n=6)
    L.paint(lin, LINING, far=0.2, round_=8)
    fold(L, sl, spline([(652, 426), (684, 470), (700, 530)], 5), 11, alpha=0.55)
    gold_trim(L, spline([(714, 422), (740, 458), (726, 530)], 5), 4.5, clip=M.grow(sl, 1))
    L.radial((744, 398), 70, C("#ffc050"), 0.8, clip=L.alpha())
    firelight(L, L.alpha(), 170, 0.55)
    R.add("arm_back_lower", L, "arm_back_upper", "arm_back_lower", (652, 434), 32)
    L = R.layer()
    L.fire((742, 416), (728, 228), 80, seed=4, tongues=4, bend=-0.04, turb=0.75)
    L.flame((742, 418), (750, 320), 38, seed=9, hot=1.25, turb=0.45)
    R.add("palm_flame", L, "arm_back_lower", "hair", (742, 420), 34, cast=False)

    # ---------------- front leg (bent, stepping forward)
    L = R.layer()
    th = limb(L, [(482, 556), (446, 650), (418, 748)], [100, 86, 68], TUN, tex=0.1)
    fold(L, th, spline([(470, 620), (446, 690), (428, 735)], 4), 9, alpha=0.45)
    fold(L, th, spline([(500, 650), (470, 720)], 3), 7, alpha=0.35)
    R.add("leg_front_upper", L, "hips", "leg_front_upper", (486, 585), 42)
    L = R.layer()
    boot(L, (418, 730), (404, 925), (334, 968), (434, 966), top_w=66)
    R.add("leg_front_lower", L, "leg_front_upper", "leg_front_lower", (418, 745), 40)

    # ---------------- hips: belt, the split skirt of the robe and hanging strips
    L = R.layer()
    hem_f = tatter([(384, 742), (428, 752), (478, 744)], 20, seed=7, step=15)
    hem_b = tatter([(540, 738), (596, 752), (648, 744), (690, 730)], 20, seed=8, step=15)
    sk = M.poly([(446, 526), (600, 520), (636, 600), (690, 730)] + hem_b[::-1] + [(516, 640)] + hem_f[::-1] +
                [(392, 690), (418, 600)])
    L.paint(sk, RB, round_=46, tex=0.12)
    drape(L, sk, (515, 420), freq=9, amp=0.85, seed=5, r0=110, r1=230)
    for pts in [[(460, 575), (436, 650), (418, 738)], [(586, 575), (616, 660), (650, 745)],
                [(496, 575), (480, 650), (462, 742)], [(548, 580), (566, 660), (580, 745)],
                [(612, 600), (650, 680), (680, 730)]]:
        fold(L, sk, spline(pts, 5), 14, alpha=0.6)
    L.grad(sk, (500, 600), (500, 750), C("#1a0610"), 0.0, 0.6)
    firelight(L, sk, 330, 0.35)
    ember_edge(L, hem_f, sk, 4.5, seed=9)
    ember_edge(L, hem_b, sk, 4.5, seed=10)
    tab_hem = tatter([(470, 752), (500, 760), (530, 752)], 14, seed=13, step=12)
    tab = M.poly([(474, 560), (530, 560), (536, 700)] + tab_hem[::-1] + [(466, 700)])
    L.shadow(tab, 0.6, (4, 7), 7)
    L.paint(tab, C("#221820"), round_=16, tex=0.12, light=0.4)
    drape(L, tab, (502, 480), freq=14, amp=0.6, seed=14, r0=60, r1=160, lit=C("#8a7a90"))
    gold_trim(L, spline([(476, 566), (470, 700), (470, 752)], 4), 3.5, clip=tab)
    gold_trim(L, spline([(528, 566), (534, 700), (530, 752)], 4), 3.5, clip=tab)
    flame_sigil(L, 502, 640, 30, clip=tab)
    ember_edge(L, tab_hem, tab, 3.5, seed=15)
    belt = M.blob([(440, 518), (604, 512), (608, 560), (440, 566)], n=4)
    L.shadow(belt, 0.6, (0, 7), 7)
    L.paint(belt, LEATHER, round_=12, spec=0.35, tex=0.2)
    L.brush([(444, 526), (604, 520)], 2, C("#b08868"), 0.45, blur=0.6, clip=belt)
    L.brush([(444, 558), (604, 552)], 2, C("#140a08"), 0.6, blur=0.6, clip=belt)
    buckle = M.blob([(486, 518), (528, 516), (530, 564), (488, 566)], n=4)
    L.paint(buckle, GOLD, round_=8, spec=0.9, metal=0.45, gloss=18)
    L.paint(M.ell(508, 541, 10, 12), C("#1a0808"), round_=4)
    L.fill(M.ell(508, 541, 5, 7), C("#ff8a2a"), 1.0, blur=0.6, mode="over")
    R.add("hips", L, "", "root", (520, 560), 50)

    # ---------------- torso: robe chest over a black tunic, harness and mantle
    L = R.layer()
    ch = M.blob([(452, 548), (600, 546), (614, 460), (624, 360), (600, 310), (520, 292), (452, 306), (424, 360),
                 (432, 460)], n=8)
    L.paint(ch, RB, tex=0.12)
    drape(L, ch, (520, 250), freq=9, amp=0.7, seed=11, r0=80, r1=200)
    tun = M.poly(spline([(482, 300), (520, 300), (528, 400), (526, 548), (486, 548), (476, 420)], 5))
    L.paint(tun, TUN, round_=20, tex=0.1, clip=ch, mode="atop")
    gold_trim(L, spline([(482, 300), (478, 420), (488, 548)], 5), 5, clip=ch)
    gold_trim(L, spline([(522, 300), (528, 420), (526, 548)], 5), 5, clip=ch)
    fold(L, ch, spline([(456, 400), (452, 480), (462, 540)], 5), 13, alpha=0.55)
    fold(L, ch, spline([(572, 420), (584, 490), (580, 545)], 5), 14, alpha=0.55)
    strap = M.limb(spline([(440, 372), (500, 438), (566, 500), (604, 540)], 6), [22])
    strap = Masks.inter(strap, ch)
    L.shadow(strap, 0.5, (2, 5), 4)
    L.paint(strap, LEATHER, round_=6, tex=0.2, spec=0.35)
    L.brush(spline([(440, 364), (500, 430), (566, 492), (608, 532)], 6), 2, C("#b08868"), 0.45, blur=0.5, clip=strap)
    ring = Masks.sub(M.circle(530, 468, 17), M.circle(530, 468, 10))
    L.paint(ring, GOLD, round_=4, spec=1.0, metal=0.5, gloss=16)
    mh = tatter([(410, 420), (468, 452), (530, 442), (592, 454), (640, 426)], 22, seed=21, step=17)
    mt = M.poly([(414, 360), (444, 308), (520, 286), (602, 298), (638, 350)] + mh[::-1])
    L.shadow(mt, 0.6, (2, 9), 9)
    L.paint(mt, RBD, round_=44, tex=0.14, light=0.38)
    drape(L, mt, (520, 230), freq=10, amp=0.8, seed=6, r0=70, r1=170)
    for a, b in [((462, 320), (452, 444)), ((538, 314), (542, 444)), ((598, 320), (616, 440)),
                 ((500, 318), (494, 448))]:
        fold(L, mt, spline([a, lerp2(a, b, 0.5), b], 4), 12, alpha=0.6)
    firelight(L, mt, 280, 0.45)
    ember_edge(L, mh, mt, 4, seed=22, glow=0.8)
    L.brush(spline([(478, 326), (486, 400), (494, 452)], 5), 2.5, C("#2a1206"), 0.9, blur=0.4)
    L.brush(spline([(524, 322), (508, 400), (496, 452)], 5), 2.5, C("#2a1206"), 0.9, blur=0.4)
    tal = M.blob([(495, 446), (515, 472), (509, 504), (495, 516), (481, 504), (475, 472)], n=6)
    L.shadow(tal, 0.6, (3, 5), 4)
    L.paint(tal, GOLD, round_=8, spec=1.0, metal=0.5, gloss=14)
    L.paint(M.ell(495, 484, 9, 6), C("#1a0808"), round_=3, line=0)
    L.fill(M.ell(495, 484, 5, 5), C("#ff9a2a"), 1.0, blur=0.5, mode="over")
    L.fill(M.ell(495, 484, 2.4, 2.4), C("#fff2c0"), 1.0, blur=0.3, mode="over")
    firelight(L, ch, 300, 0.3)
    R.add("torso", L, "hips", "torso", (520, 540), 60)

    # ---------------- hood tip (droops behind and sways)
    L = R.layer()
    tip = M.blob([(512, 150), (560, 120), (620, 100), (676, 104), (712, 132), (720, 170), (700, 160), (672, 134),
                  (628, 140), (592, 180), (540, 204)], n=8)
    L.paint(tip, RB, round_=26, tex=0.12, light=0.4)
    fold(L, tip, spline([(556, 160), (610, 128), (668, 124), (704, 150)], 5), 10, alpha=0.55)
    firelight(L, tip, 280, 0.35)
    R.add("hood_tip", L, "head", "hair", (552, 168), 66)

    # ---------------- head: hood, shadowed face, burning eyes
    L = R.layer()
    hood = M.blob([(404, 212), (416, 160), (456, 124), (524, 114), (580, 140), (606, 200), (610, 266), (598, 326),
                   (546, 352), (466, 350), (424, 322), (406, 266)], n=8)
    L.paint(hood, RB, tex=0.12, light=0.42)
    drape(L, hood, (500, 40), freq=8, amp=0.55, seed=10, r0=120, r1=260)
    face_o = M.blob([(412, 210), (436, 178), (482, 170), (510, 198), (516, 252), (500, 306), (462, 326), (426, 306),
                     (412, 262)], n=8)
    L.fill(face_o, C("#080305"), 1.0, blur=0.8)
    face = M.blob([(420, 226), (456, 204), (494, 212), (502, 252), (490, 294), (462, 314), (434, 302), (420, 264)], n=8)
    L.paint(face, C("#4a302e"), light=0.2, rim=0.3, line=0, soft=8, mode="atop")
    L.grad(face, (460, 204), (460, 310), C("#070203"), 1.0, 0.35)
    # nose, cruel mouth, gaunt cheek and war paint, lit from below by the fire
    L.brush(spline([(430, 258), (424, 270), (434, 276)], 3), 2.5, C("#1a0a0c"), 0.6, blur=0.6, clip=face)
    L.brush(spline([(436, 292), (454, 291), (474, 294)], 4), 3, C("#1c080a"), 0.9, blur=0.5, clip=face)
    L.brush(spline([(438, 300), (456, 304), (474, 298)], 4), 3, C("#d0a090"), 0.35, blur=1.0, clip=face)
    L.brush(spline([(484, 250), (488, 276), (478, 298)], 4), 4, C("#1a0a0c"), 0.35, blur=2, clip=face)
    for x in (446, 480):
        L.brush([(x, 246), (x - 2, 270)], 3, C("#c01810"), 0.55, blur=0.8, clip=face)
    L.radial((480, 310), 50, C("#ff7a3a"), 0.35, clip=face)
    lip = spline([(404, 266), (408, 212), (432, 176), (482, 164), (518, 192), (524, 254), (508, 312), (470, 334)], 6)
    L.brush(lip, 15, RBD, 1.0, blur=1.4, clip=hood)
    L.brush([(x - 3, y - 3) for x, y in lip[:len(lip) // 2]], 4, C("#f07a64"), 0.5, blur=1.2, clip=hood)
    fold(L, hood, spline([(542, 160), (566, 250), (562, 336)], 5), 14, alpha=0.55)
    fold(L, hood, spline([(500, 140), (530, 182)], 3), 9, alpha=0.4)
    L.grad(hood, (520, 260), (570, 350), C("#12040a"), 0.0, 0.5)
    firelight(L, hood, 330, 0.45)
    eye_glow(L, 440, 234, 7, slant=6)
    eye_glow(L, 476, 238, 9, slant=4)
    R.add("head", L, "torso", "head", (500, 318), 70)

    # ---------------- kris dagger (weapon)
    L = R.layer()
    ctl = [(334, 478), (312, 446), (300, 414), (270, 392), (256, 360), (228, 338), (200, 316)]
    blade = M.limb(ctl, [40, 38, 36, 33, 28, 18, 2], n=5)
    L.paint(blade, C("#9a96a4"), round_=8, metal=0.9, spec=1.0, gloss=24, rim=0.35, line=0.9)
    spine_ = spline(ctl, 5)
    L.brush(spine_, 3, C("#2a2430"), 0.6, blur=0.8, clip=blade, taper=(1, 0.3))
    L.brush([(x - 6, y + 3) for x, y in spine_], 4, C("#ff5a14"), 0.9, blur=1.2, clip=blade, taper=(1, 0.4))
    L.brush([(x - 6, y + 3) for x, y in spine_], 1.5, C("#fff0c0"), 0.9, blur=0.4, clip=blade, taper=(1, 0.3))
    guard = M.limb(spline([(302, 492), (328, 478), (352, 462), (364, 440)], 4), [14, 15, 13, 8])
    L.paint(guard, GOLD, round_=5, spec=0.9, metal=0.5)
    grip = M.limb([(336, 486), (344, 514), (350, 540)], [16, 15, 14])
    L.paint(grip, C("#3a1a14"), round_=5)
    L.paint(M.circle(352, 548, 11), GOLD, round_=5, spec=0.9, metal=0.5)
    L.fill(M.circle(352, 548, 4.5), C("#ff7a24"), 1.0, blur=0.4, mode="over")
    R.add("dagger", L, "arm_front_lower", "weapon", (340, 505), 78)

    # ---------------- front arm (under the hood's drape)
    L = R.layer()
    up = limb(L, [(446, 330), (420, 396), (394, 458)], [96, 88, 72], RB, tex=0.12)
    drape(L, up, (450, 290), freq=10, amp=0.6, seed=9, r0=40, r1=140)
    fold(L, up, spline([(446, 366), (428, 410), (408, 450)], 4), 12, alpha=0.55)
    R.add("arm_front_upper", L, "torso", "arm_front_upper", (444, 352), 67)
    L = R.layer()
    hand = M.blob([(316, 480), (342, 464), (370, 476), (372, 508), (350, 524), (320, 516)], n=6)
    L.paint(hand, ASH_SKIN, round_=14, rim=0.6)
    for i in range(3):
        y = 482 + i * 11
        L.brush([(320, y + 2), (344, y - 2)], 4, C("#4a2a28"), 0.55, blur=0.8, clip=hand)
    L.paint(M.limb([(328, 472), (314, 490), (322, 506)], [15, 14, 12]), ASH_SKIN, round_=6)
    sl = M.blob([(372, 420), (428, 440), (430, 494), (404, 546), (378, 558), (352, 548), (340, 506), (356, 466)], n=8)
    L.paint(sl, RB, tex=0.12, round_=36)
    drape(L, sl, (420, 400), freq=9, amp=0.8, seed=8, r0=30, r1=120)
    fold(L, sl, spline([(404, 452), (386, 500), (378, 548)], 4), 12, alpha=0.55)
    fold(L, sl, spline([(426, 466), (416, 520)], 3), 10, alpha=0.45)
    cuff = spline([(340, 504), (350, 532), (378, 554)], 6)
    L.brush(cuff, 13, LINING, 1.0, blur=0.8, clip=sl)
    gold_trim(L, [(p[0] + 6, p[1] - 8) for p in cuff], 4.5, clip=sl)
    for i in range(5):
        c = lerp2((384, 466), (426, 488), i / 4)
        L.brush([(c[0], c[1] - 4), (c[0] + 3, c[1] + 4)], 2.4, C("#ffb040"), 0.95, blur=0.4, clip=sl)
    L.shadow(sl, 0.5, (-3, 5), 5)
    R.add("arm_front_lower", L, "arm_front_upper", "arm_front_lower", (396, 458), 82)

    # ---------------- fx
    R.add("eyes_fx", fx_glow(R, [(440, 234, 34, C("#ff7a1a"), 0.55), (476, 238, 40, C("#ff7a1a"), 0.6)]),
          "head", "fx", (460, 236), 95, "add")
    R.add("flame_fx", fx_glow(R, [(738, 350, 190, C("#ff5a14"), 0.45), (740, 396, 80, C("#ffc050"), 0.5)]),
          "arm_back_lower", "fx", (742, 420), 96, "add")
    R.add("talisman_fx", fx_glow(R, [(495, 484, 26, C("#ff7a1a"), 0.55), (508, 541, 22, C("#ff7a1a"), 0.4)]),
          "torso", "fx", (495, 484), 94, "add")
    R.add("dagger_fx", fx_glow(R, [(270, 400, 80, C("#ff5a14"), 0.3)]), "dagger", "fx", (340, 505), 93, "add")
    return R


# ================================================================== fire imp

IMP = C("#c2381c")
IMP_D = C("#5a1410")
CHAR = C("#241414")
HORN = C("#2a1c1a")
IRON = C("#3a3438")


def burnt(L, clip, p0, p1, amt=0.85):
    """Skin charring toward the extremities: gradient to charcoal from p0 (clean) to p1 (black)."""
    L.grad(clip, p0, p1, CHAR, 0.0, amt)


def skin_cracks(L, clip, paths, w=3.0, glow=1.0):
    for i, (a, b) in enumerate(paths):
        L.seam(jag(a, b, 0.28, 4, seed=i * 7 + int(a[0])), w, clip=clip, glow=glow, n=3)


def bat_wing(L, root, bones, membrane_c, bone_c, far=0.0, seed=1, vein=True):
    """Bat wing: arm bones from root to wrist, finger bones fanning out; the membrane is scalloped between the
    finger tips and back to the body. bones = [elbow, wrist, tip1, tip2, tip3, ...] (tips top to bottom);
    the last point closes the membrane at the body."""
    M = L.M
    elbow, wrist = bones[0], bones[1]
    tips = bones[2:-1]
    tail = bones[-1]
    outline = [root, elbow, wrist, tips[0]]
    for a, b in zip(tips, tips[1:] + [tail]):
        mid = lerp2(a, b, 0.5)
        # scallop: pull the edge toward the wrist
        pull = lerp2(mid, wrist, 0.28)
        outline += [pull, b]
    mem = M.poly(spline(outline, 5, closed=True))
    L.paint(mem, membrane_c, round_=40, far=far, tex=0.2, tex_cell=4, rim=0.6, light=0.3, bulge=2.5)
    # thin, backlit membrane: warm translucency toward the edges
    L.grad(mem, wrist, tips[len(tips) // 2], C("#ff5a1a"), 0.0, 0.28 * (1 - far * 0.5))
    rng = random.Random(seed)
    if vein:
        for t in tips:
            for k in range(2):
                a = lerp2(wrist, t, rng.uniform(0.2, 0.5))
                b = lerp2(a, lerp2(t, tail, rng.uniform(0.1, 0.3)), rng.uniform(0.4, 0.7))
                L.brush(jag(a, b, 0.15, 3, seed=rng.randint(0, 999)), 2.2, C("#ff7a2a"), 0.55, blur=0.8, clip=mem)
    for t in tips:
        L.brush(spline([wrist, lerp2(wrist, t, 0.5), t], 4), 3.5, C("#1a0a0a"), 0.35, blur=3, clip=mem)
    arm = Masks.union(M.limb([root, elbow], [34, 22]), M.limb([elbow, wrist], [22, 15]))
    L.paint(arm, bone_c, round_=10, far=far, spec=0.3, rim=0.7)
    for t in tips:
        fb = M.limb([wrist, lerp2(wrist, t, 0.55), t], [12, 8, 3])
        L.paint(fb, bone_c, round_=4, far=far, rim=0.6, line=0.6)
    L.paint(M.circle(wrist[0], wrist[1], 12), bone_c, round_=6, far=far, spec=0.4)
    claw = M.limb([wrist, polar(wrist, -100, 22), polar(wrist, -80, 36)], [9, 6, 1])
    L.paint(claw, C("#e8d8c0"), round_=3, far=far, spec=0.7)
    return mem


def fire_imp():
    R = Rig("fire_imp", 1024, feet=(512, 972), kind="humanoid")
    M = R.M
    BALL = (706, 452)
    F = (362, 508)                     # fist on the pitchfork shaft
    DIR = (-0.616, -0.788)             # shaft direction (toward the tines)

    def fl(L, clip, r=260, st=0.45):
        L.radial(BALL, r, C("#ff6a1a"), st, clip=clip)

    def muscle(L, clip, pts, w, alpha=0.45):
        """Muscle separation: a soft shadow line with a lit edge above-left."""
        L.brush([(x - w * 0.5, y - w * 0.5) for x, y in pts], w * 0.8, C("#ff9a70"), alpha * 0.45, blur=w * 0.6,
                clip=clip, taper=(0.2, 0.2))
        L.brush(pts, w, IMP_D, alpha, blur=w * 0.6, clip=clip, taper=(0.2, 0.3))

    # ---------------- wings
    L = R.layer()
    bat_wing(L, (566, 446), [(664, 330), (736, 196), (646, 104), (806, 142), (888, 252), (870, 376), (600, 560)],
             C("#4a1a1a"), C("#3a1c1c"), far=0.35, seed=2)
    R.add("wing_back", L, "torso", "wing_back", (566, 446), 5)
    L = R.layer()
    bat_wing(L, (530, 452), [(600, 350), (650, 228), (566, 146), (712, 184), (782, 290), (760, 404), (548, 560)],
             C("#6a2420"), C("#4a2222"), seed=3)
    R.add("wing_front", L, "torso", "wing_front", (534, 452), 18)

    # ---------------- tail (three links)
    segs = [[(560, 610), (620, 690), (686, 740)], [(676, 736), (744, 760), (796, 726)],
            [(790, 732), (834, 684), (852, 622)]]
    widths = [[34, 26, 20], [21, 17, 14], [15, 12, 9]]
    for i, (pts, ws) in enumerate(zip(segs, widths)):
        L = R.layer()
        m = limb(L, pts, ws, IMP, rim=0.8, tex=0.1)
        burnt(L, m, pts[0], (860, 600), 0.5 + 0.1 * i)
        if i == 2:
            head = M.poly(spline([(852, 536), (888, 590), (868, 606), (882, 644), (852, 628), (826, 646), (838, 606),
                                  (818, 590)], 3, closed=True))
            L.paint(head, CHAR, round_=10, spec=0.6, rim=0.9)
            L.seam([(852, 552), (852, 622)], 3, clip=head, n=2)
        R.add(f"tail_{i + 1}", L, "hips" if i == 0 else f"tail_{i}", "tail", pts[0], 8 - i)

    # ---------------- back arm with the fireball
    L = R.layer()
    up = limb(L, [(552, 462), (574, 500), (590, 540), (606, 572)], [52, 50, 42, 34], IMP, far=0.3, tex=0.08)
    fl(L, up, 200, 0.5)
    R.add("arm_back_upper", L, "torso", "arm_back_upper", (552, 474), 12)
    L = R.layer()
    fa = limb(L, [(604, 570), (636, 552), (660, 524), (680, 494)], [36, 36, 30, 26], IMP, far=0.2, tex=0.08)
    burnt(L, fa, (626, 556), (680, 494), 0.85)
    hand = M.blob([(668, 506), (678, 482), (698, 480), (704, 498), (688, 516)], n=5)
    L.paint(hand, CHAR, far=0.1, spec=0.3, rim=0.8)
    fingers(L, (698, 488), -62, [28, 32, 30, 24], 7, CHAR, spread=17, curl=-32, spec=0.3, rim=0.8)
    fl(L, L.alpha(), 120, 0.7)
    R.add("arm_back_lower", L, "arm_back_upper", "arm_back_lower", (604, 570), 13)
    L = R.layer()
    L.radial(BALL, 64, C("#ff5a14"), 0.6, mode="over")
    L.fire((BALL[0], BALL[1] + 30), (BALL[0] - 8, BALL[1] - 120), 74, seed=21, tongues=3, turb=0.8)
    L.fill(M.circle(BALL[0], BALL[1] + 4, 26), C("#fff0b0"), 0.9, blur=8, mode="over")
    L.fill(M.circle(BALL[0], BALL[1] + 4, 14), C("#ffffff"), 0.9, blur=5, mode="over")
    R.add("fireball", L, "arm_back_lower", "hair", (BALL[0], BALL[1] + 30), 14, cast=False)

    # ---------------- back leg (digitigrade)
    L = R.layer()
    th = limb(L, [(560, 606), (580, 650), (596, 700), (606, 748)], [74, 76, 62, 46], IMP, far=0.3, tex=0.08)
    R.add("leg_back_upper", L, "hips", "leg_back_upper", (560, 625), 16)
    L = R.layer()
    sh = limb(L, [(604, 736), (626, 780), (640, 836), (642, 884)], [46, 44, 32, 26], IMP, far=0.3, tex=0.08)
    foot = M.blob([(626, 866), (658, 880), (644, 940), (626, 966), (574, 970), (580, 948), (614, 930)], n=6)
    L.paint(foot, CHAR, far=0.3, spec=0.3)
    burnt(L, sh, (624, 800), (642, 900), 0.85)
    for x in (576, 596, 616):
        L.paint(M.limb([(x + 6, 956), (x - 8, 968), (x - 16, 972)], [9, 6, 2]), C("#d8c8b0"), round_=3, far=0.3)
    R.add("leg_back_lower", L, "leg_back_upper", "leg_back_lower", (604, 748), 15)

    # ---------------- hips with a tattered loincloth
    L = R.layer()
    pel = M.blob([(478, 572), (576, 568), (594, 620), (566, 660), (502, 664), (474, 630)], n=6)
    L.paint(pel, IMP, tex=0.08)
    lc_hem = tatter([(470, 704), (512, 720), (560, 708)], 16, seed=31, step=12)
    lc = M.poly([(472, 612), (580, 610), (570, 684)] + lc_hem[::-1] + [(474, 684)])
    L.shadow(lc, 0.6, (3, 6), 6)
    L.paint(lc, C("#2a1c1c"), round_=16, tex=0.18, light=0.35)
    drape(L, lc, (520, 560), freq=12, amp=0.7, seed=32, r0=40, r1=110, lit=C("#8a6a60"))
    ember_edge(L, lc_hem, lc, 3.5, seed=33)
    rope = M.limb(spline([(468, 612), (520, 624), (586, 612)], 5), [12])
    L.paint(rope, C("#6a4a2a"), round_=5, tex=0.2)
    for i in range(9):
        c = lerp2((472, 614), (582, 614), i / 8)
        L.brush([(c[0] - 4, c[1] - 5), (c[0] + 4, c[1] + 5)], 2, C("#2a1a0a"), 0.6, blur=0.5, clip=rope)
    L.paint(M.ell(494, 634, 9, 12), C("#d8c8b0"), round_=5, spec=0.5)  # little bone charm
    R.add("hips", L, "", "root", (520, 625), 30)

    # ---------------- front leg
    L = R.layer()
    th = limb(L, [(494, 606), (480, 646), (460, 700), (440, 748)], [80, 84, 66, 50], IMP, tex=0.08)
    muscle(L, th, spline([(500, 650), (478, 700), (456, 736)], 3), 6)
    skin_cracks(L, th, [((486, 640), (462, 700))], 2.4)
    R.add("leg_front_upper", L, "hips", "leg_front_upper", (492, 628), 34)
    L = R.layer()
    sh = limb(L, [(440, 736), (466, 780), (478, 836), (474, 884)], [52, 50, 34, 28], IMP, tex=0.08)
    muscle(L, sh, spline([(470, 770), (480, 810)], 3), 5, 0.35)
    burnt(L, sh, (456, 800), (474, 900), 0.9)
    foot = M.blob([(456, 866), (490, 878), (472, 940), (454, 966), (390, 970), (398, 946), (440, 930)], n=6)
    L.paint(foot, CHAR, spec=0.35, rim=0.6)
    for x in (392, 414, 436):
        L.paint(M.limb([(x + 8, 956), (x - 8, 968), (x - 18, 972)], [10, 7, 2]), C("#e8d8c0"), round_=3, spec=0.6)
    R.add("leg_front_lower", L, "leg_front_upper", "leg_front_lower", (440, 748), 33)

    # ---------------- torso: hunched, wiry, ribs and a furnace glowing through the belly
    L = R.layer()
    ch = M.blob([(472, 424), (446, 446), (428, 480), (436, 520), (454, 560), (476, 598), (500, 630), (560, 630),
                 (576, 594), (592, 530), (596, 474), (578, 440), (530, 418)], n=8)
    L.paint(ch, IMP_D, tex=0.1, light=0.5)
    FORM = dict(mode="atop", line=0.25, soft=2.5, tex=0.08)
    back = M.blob([(530, 424), (580, 442), (596, 480), (590, 540), (572, 600), (548, 620), (540, 540), (534, 470)], n=8)
    L.paint(back, IMP, clip=ch, **FORM)
    cage = M.blob([(470, 500), (520, 492), (560, 510), (570, 560), (548, 600), (500, 602), (470, 570), (458, 530)],
                  n=8)
    L.paint(cage, IMP, clip=ch, **FORM)
    for k in range(4):
        y = 522 + k * 17
        L.brush(spline([(476 + k * 3, y - 6), (510, y + 4), (552, y - 2)], 4), 4, IMP_D, 0.5, blur=2.2, clip=cage)
        L.brush(spline([(478 + k * 3, y - 11), (510, y - 2), (548, y - 8)], 4), 3, C("#ff9a70"), 0.3, blur=1.6,
                clip=cage)
    belly = M.blob([(482, 578), (520, 568), (556, 584), (560, 616), (528, 634), (494, 628)], n=6)
    L.paint(belly, C("#e0602a"), clip=ch, **FORM)
    L.radial((520, 600), 46, C("#ffc050"), 0.7, clip=belly)
    L.radial((520, 604), 22, C("#fff0b0"), 0.45, clip=belly)
    pec = M.blob([(448, 452), (486, 440), (522, 452), (528, 486), (504, 510), (464, 512), (440, 494)], n=8)
    L.paint(pec, IMP, clip=ch, **FORM)
    L.shadow(pec, 0.45, (2, 6), 5)
    clav = spline([(452, 446), (484, 438), (520, 440)], 4)
    L.brush(clav, 5, C("#ffa080"), 0.5, blur=1.6, clip=ch)
    L.brush([(x + 1, y + 6) for x, y in clav], 5, IMP_D, 0.4, blur=2, clip=ch)
    skin_cracks(L, ch, [((538, 450), (560, 520)), ((486, 612), (552, 612)), ((446, 470), (470, 540))], 2.6)
    fl(L, ch, 260, 0.45)
    R.add("torso", L, "hips", "torso", (520, 610), 40)

    # ---------------- flame hair (three tongues that flicker)
    for i, (b, t, w, sd) in enumerate([((466, 262), (540, 116), 74, 41), ((428, 258), (446, 104), 66, 42),
                                       ((496, 292), (604, 186), 58, 43)]):
        L = R.layer()
        L.fire(b, t, w, seed=sd, tongues=3, turb=0.85, bend=-0.08 if i != 1 else 0.05)
        R.add(f"flame_hair_{i + 1}", L, "head", "hair", b, 47 + i, cast=False)

    # ---------------- head: angular skull, long ears, glowing maw
    L = R.layer()
    ear = M.poly(spline([(480, 318), (540, 280), (626, 236), (580, 304), (532, 352), (492, 358)], 4, closed=True))
    L.paint(ear, IMP, rim=0.9, tex=0.1)
    L.paint(M.poly(spline([(498, 328), (560, 290), (602, 262), (552, 318), (506, 346)], 4, closed=True)), IMP_D,
            round_=8, light=0.2, mode="atop", line=0)
    skull = M.blob([(366, 296), (386, 262), (432, 246), (482, 256), (506, 296), (506, 344), (488, 380), (456, 404),
                    (414, 424), (378, 426), (358, 404), (352, 366), (356, 330)], n=8)
    L.paint(skull, IMP, tex=0.1, light=0.42)
    HF = dict(mode="atop", line=0, soft=3, tex=0.06, clip=skull)
    L.paint(M.blob([(410, 254), (470, 250), (500, 290), (494, 330), (452, 318), (410, 300), (380, 290)], n=6),
            C("#d44a24"), **HF)                                         # cranium dome
    L.paint(M.blob([(430, 338), (470, 330), (492, 352), (476, 382), (440, 376)], n=6), C("#d04424"), **HF)  # cheek
    L.paint(M.blob([(370, 400), (420, 404), (470, 380), (482, 396), (446, 420), (400, 430), (366, 420)], n=6),
            C("#b8341a"), **HF)                                         # jaw
    fe = M.poly(spline([(378, 296), (334, 244), (362, 310)], 3, closed=True))
    L.paint(Masks.sub(fe, skull), IMP, far=0.35, round_=6)
    # structure: heavy brow, sunken temple, cheekbone, jaw
    L.brush(spline([(360, 316), (392, 300), (430, 304), (462, 318)], 4), 16, IMP_D, 0.6, blur=5, clip=skull)
    L.brush(spline([(364, 298), (394, 286), (434, 290)], 4), 6, C("#ffa080"), 0.5, blur=2, clip=skull)
    L.brush(spline([(446, 356), (470, 344), (490, 350)], 3), 10, IMP_D, 0.45, blur=5, clip=skull)
    L.brush(spline([(440, 344), (462, 336)], 2), 4, C("#ff9a70"), 0.45, blur=2, clip=skull)
    L.brush(spline([(470, 380), (440, 410), (400, 424)], 3), 8, IMP_D, 0.4, blur=4, clip=skull)
    nose = M.poly(spline([(378, 320), (354, 356), (360, 364), (374, 362), (386, 348)], 3, closed=True))
    L.paint(nose, IMP, round_=8, light=0.5, line=0.6)
    L.fill(M.ell(366, 360, 4, 2.5, -20), C("#2a0604"), 0.8, blur=0.6, mode="atop")
    # grin: dark glowing maw with needle teeth
    mouth = M.poly(spline([(362, 380), (394, 390), (432, 390), (468, 366), (458, 394), (424, 412), (386, 410),
                           (366, 398)], 4, closed=True))
    L.fill(mouth, C("#2a0604"), 1.0, blur=0.6)
    L.radial((410, 402), 36, C("#ff7a1a"), 0.85, clip=mouth)
    for i in range(7):
        x = 368 + i * 13
        yt = 383 + i * 0.6 - (6 if i == 6 else 0)
        L.fill(M.poly([(x, yt - 2), (x + 9, yt - 2), (x + 4.5, yt + 12)]), C("#f4e8d0"), 1.0, blur=0.4, mode="over")
    for i in range(6):
        x = 376 + i * 13
        yb = 408 - abs(i - 2.5) * 1.6
        L.fill(M.poly([(x, yb + 2), (x + 9, yb + 2), (x + 4.5, yb - 10)]), C("#e8d8c0"), 1.0, blur=0.4, mode="over")
    L.brush(spline([(458, 374), (472, 362), (480, 346)], 3), 3, IMP_D, 0.6, blur=1, clip=skull)
    L.brush(spline([(376, 418), (406, 426), (440, 418)], 4), 4, C("#ffa080"), 0.35, blur=2, clip=skull)
    # narrow burning eyes under the brow
    for (ex, ey, r, sl) in ((382, 328, 10, -14), (428, 332, 14, -10)):
        L.fill(M.ell(ex, ey, r * 1.4, r * 0.62, sl), C("#1a0604"), 1.0, blur=0.8)
        L.fill(M.ell(ex, ey + 1, r * 1.15, r * 0.48, sl), C("#ffb020"), 1.0, blur=0.6, mode="over")
        L.fill(M.ell(ex, ey + 1, r * 0.7, r * 0.3, sl), C("#fff6c0"), 1.0, blur=0.6, mode="over")
        L.fill(M.ell(ex - 3, ey + 1, r * 0.16, r * 0.45), C("#1a0604"), 0.9, blur=0.4, mode="over")
    skin_cracks(L, skull, [((472, 276), (492, 330)), ((446, 400), (482, 376))], 2.2)
    for pts, ws, far in (([(454, 266), (488, 212), (538, 180), (572, 186)], [32, 24, 12, 2], 0.35),
                         ([(412, 260), (428, 198), (470, 156), (512, 146)], [36, 27, 14, 2], 0.0)):
        hm = M.limb(pts, ws, n=6)
        L.paint(hm, HORN, round_=10, spec=0.8, gloss=14, far=far, tex=0.2)
        for k in range(4):
            c = lerp2(pts[0], pts[2], 0.15 + k * 0.2)
            L.brush([polar(c, 20, 14), polar(c, 200, 14)], 2, C("#0a0404"), 0.5, blur=0.6, clip=hm)
    L.radial(BALL, 380, C("#ff6a1a"), 0.3, clip=L.alpha())
    R.add("head", L, "torso", "head", (470, 420), 50)

    # ---------------- pitchfork
    L = R.layer()
    top = (F[0] + DIR[0] * 236, F[1] + DIR[1] * 236)
    butt = (F[0] - DIR[0] * 330, F[1] - DIR[1] * 330)
    shaft = M.limb([butt, top], [19, 17])
    L.paint(shaft, C("#3a2a24"), round_=7, spec=0.4, tex=0.3, streak=0.2)
    ang = math.degrees(math.atan2(DIR[1], DIR[0]))
    cross = M.limb([polar(top, ang + 90, 56), polar(top, ang + 90, 22), top, polar(top, ang - 90, 22),
                    polar(top, ang - 90, 56)], [16, 18, 24, 18, 16], n=4)
    socket = M.limb([polar(top, ang + 180, 40), top], [22, 26])
    tips = []
    tines = []
    for off, ln in ((-54, 130), (0, 160), (54, 130)):
        b = polar(top, ang + 90, off)
        mid = polar(b, ang - off * 0.1, ln * 0.6)
        tip = polar(mid, ang - off * 0.22, ln * 0.4)
        tips.append(tip)
        tines.append(M.limb([b, mid, tip], [17, 13, 1], n=5))
        barb = M.poly([polar(tip, ang + 180, 26), polar(tip, ang + 180 + (30 if off >= 0 else -30), 34),
                       polar(tip, ang + 180, 44)])
        tines.append(barb)
    tm = Masks.union(cross, socket, *tines)
    L.paint(tm, IRON, round_=7, metal=0.75, spec=0.9, gloss=20, tex=0.25)
    for tip in tips:
        L.radial(tip, 80, C("#ff4a10"), 0.9, clip=tm, power=1.2)
        L.radial(tip, 38, C("#ffd070"), 0.95, clip=tm, power=1.2)
    L.paint(M.circle(butt[0], butt[1], 13), IRON, round_=6, metal=0.6, spec=0.8)
    R.add("pitchfork", L, "arm_front_lower", "weapon", F, 58)

    # ---------------- front arm gripping the pitchfork
    L = R.layer()
    up = limb(L, [(460, 440), (452, 480), (438, 520), (420, 556)], [60, 62, 50, 42], IMP, tex=0.08)
    delt = M.blob([(446, 428), (478, 430), (484, 464), (470, 496), (446, 488), (436, 458)], n=6)
    L.paint(delt, C("#d04424"), mode="atop", line=0.2, soft=2.5, clip=up)
    L.shadow(delt, 0.4, (2, 5), 4)
    muscle(L, up, spline([(468, 470), (452, 510), (434, 540)], 3), 6, 0.45)
    skin_cracks(L, up, [((462, 462), (444, 520))], 2.4)
    R.add("arm_front_upper", L, "torso", "arm_front_upper", (462, 460), 60)
    L = R.layer()
    fa = limb(L, [(420, 552), (398, 540), (380, 526), (366, 514)], [44, 42, 34, 30], IMP, tex=0.08)
    muscle(L, fa, spline([(414, 540), (390, 526)], 2), 5, 0.4)
    burnt(L, fa, (420, 552), (366, 512), 0.85)
    fist = M.blob([(340, 492), (362, 478), (388, 490), (388, 522), (366, 534), (342, 526)], n=6)
    L.paint(fist, CHAR, spec=0.35, rim=0.6)
    for i in range(3):
        L.brush([(344 + i * 3, 500 + i * 9), (370 + i * 3, 492 + i * 9)], 3, C("#0a0404"), 0.7, blur=0.6, clip=fist)
        L.paint(M.limb([(344 + i * 3, 500 + i * 9), (334 + i * 3, 510 + i * 9), (340 + i * 3, 518 + i * 9)],
                       [8, 6, 2]), C("#e8d8c0"), round_=2, spec=0.5)
    L.paint(M.limb([(372, 484), (356, 476), (344, 482)], [12, 10, 7]), CHAR, round_=4, spec=0.3)  # thumb
    R.add("arm_front_lower", L, "arm_front_upper", "arm_front_lower", (422, 556), 62)

    # ---------------- fx
    R.add("eyes_fx", fx_glow(R, [(382, 328, 30, C("#ffb020"), 0.45), (428, 332, 36, C("#ffb020"), 0.5),
                                 (410, 400, 40, C("#ff5a14"), 0.4)]), "head", "fx", (410, 340), 95, "add")
    R.add("hair_fx", fx_glow(R, [(480, 200, 170, C("#ff5a14"), 0.4)]), "head", "fx", (466, 262), 94, "add")
    R.add("fireball_fx", fx_glow(R, [(BALL[0], BALL[1], 150, C("#ff5a14"), 0.55),
                                     (BALL[0], BALL[1] + 4, 60, C("#ffd070"), 0.6)]),
          "arm_back_lower", "fx", BALL, 96, "add")
    R.add("belly_fx", fx_glow(R, [(514, 572, 60, C("#ff8a2a"), 0.3)]), "torso", "fx", (514, 572), 93, "add")
    R.add("fork_fx", fx_glow(R, [(tips[1][0], tips[1][1] + 20, 120, C("#ff5a14"), 0.4)]), "pitchfork", "fx", F, 92,
          "add")
    return R



# ================================================================== ember hound

HIDE = C("#2e2426")
HIDE_D = C("#161012")
CLAW = C("#d8c8b4")


def fur_strokes(L, clip, n, length, ang, seed, color, alpha=0.4, w=2.2, jitter=18, blur=0.7):
    """Many short painted hair strokes inside clip (all drawn into one mask, then filled atop)."""
    rng = np.random.default_rng(seed)
    small = np.asarray(clip.resize((clip.size[0] // 8, clip.size[1] // 8), Image.BOX), np.uint8)
    ys, xs = np.nonzero(small > 200)
    if len(xs) == 0:
        return
    m = L.M.new()
    d = ImageDraw.Draw(m)
    for i in rng.integers(0, len(xs), n):
        x, y = (xs[i] * 8 + rng.uniform(0, 8)) / SS, (ys[i] * 8 + rng.uniform(0, 8)) / SS
        a = math.radians(ang + rng.uniform(-jitter, jitter))
        ln = length * rng.uniform(0.6, 1.3)
        d.line([(x * SS, y * SS), ((x + math.cos(a) * ln) * SS, (y + math.sin(a) * ln) * SS)], fill=255,
               width=max(1, int(w * SS)))
    L.fill(Masks.inter(m, clip), color, alpha, blur=blur, mode="atop")


def paw(L, ankle, ground, width, color, far=0.0, claw_c=CLAW):
    """Heavy paw seen from the side with toes to the left (the hound faces left); returns the mask."""
    M = L.M
    ax, ay = ankle
    w = width
    toes = [M.ell(ax - w * 0.62 + i * w * 0.36, ground - w * 0.26, w * 0.27, w * 0.27) for i in range(3)]
    pad = M.blob([(ax - w * 0.45, ay), (ax + w * 0.45, ay), (ax + w * 0.55, ground - w * 0.5),
                  (ax + w * 0.42, ground - 2), (ax - w * 0.6, ground - 2), (ax - w * 0.8, ground - w * 0.4)], n=6)
    m = Masks.union(pad, *toes)
    L.paint(m, color, round_=w * 0.3, far=far, tex=0.14, rim=0.6, bounce=0.5)
    for i in range(1, 3):
        x = ax - w * 0.62 + (i - 0.5) * w * 0.36
        L.brush([(x + 2, ground - w * 0.5), (x, ground - 3)], 3, C("#0a0606"), 0.6, blur=1.2, clip=m)
    for i in range(3):
        x = ax - w * 0.62 + i * w * 0.36 - w * 0.2
        c = M.limb([(x + 8, ground - w * 0.28), (x - 4, ground - 8), (x - 12, ground + 1)], [10, 7, 1.5], n=4)
        L.paint(c, claw_c, round_=3, far=far, spec=0.7, line=0.5)
    return m


def scale_layer(L, c, k):
    """Scales everything painted on L by k about design point c (to resize a finished part)."""
    cx, cy = c[0] * SS, c[1] * SS
    L.img = L.img.transform(L.img.size, Image.AFFINE, (1 / k, 0, cx * (1 - 1 / k), 0, 1 / k, cy * (1 - 1 / k)),
                            resample=Image.BICUBIC)


def fade_top(L, y0, y1):
    """Fades the part's alpha in from y0 to y1 (design px) so its top melts into the parent under it."""
    a = np.asarray(L.img.getchannel("A"), np.float32)
    ys = np.arange(L.H, dtype=np.float32)[:, None] / SS
    a = a * smooth(y0, y1, ys)
    L.img.putalpha(Image.fromarray(a.astype(np.uint8), "L"))


def spikes(M, pts, depth, seed=1, step=16, side=1):
    """A band of spiky fur tufts along a path (on its left side for side=1): union it with a shape so the
    shape's edge turns into tufts."""
    rng = random.Random(seed)
    path = resample(spline(pts, 6), step)
    outer = []
    for i, (x, y) in enumerate(path):
        a = path[max(0, i - 1)]
        b = path[min(len(path) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) + 1e-6
        nx, ny = dy / ln * side, -dx / ln * side
        d = depth * (rng.uniform(0.7, 1.15) if i % 2 else rng.uniform(0.0, 0.25))
        sk = rng.uniform(-0.4, 0.4) * step
        outer.append((x + nx * d + dx / ln * sk, y + ny * d + dy / ln * sk))
    inner = [(x - (o[0] - x) * 0.3, y - (o[1] - y) * 0.3) for (x, y), o in zip(path, outer)]
    return M.poly(inner + outer[::-1])


def ember_hound():
    R = Rig("ember_hound", 1024, feet=(590, 970), kind="beast")
    M = R.M
    G = 968  # ground
    HK, HC = 1.16, (432, 492)  # the head group is painted at 1 and scaled up about the neck

    def hs(p):
        return (HC[0] + (p[0] - HC[0]) * HK, HC[1] + (p[1] - HC[1]) * HK)

    def head_part(name, L, parent, role, pivot, z, **kw):
        scale_layer(L, HC, HK)
        R.add(name, L, parent, role, hs(pivot), z, **kw)

    def mane_light(L, clip, st=0.4):
        L.radial((540, 300), 330, C("#ff6a1a"), st, clip=clip)

    def hide(L, m, far=0.0, fur_ang=60, n=260, seed=1, **kw):
        kw.setdefault("rim", 0.8)
        L.paint(m, HIDE, far=far, tex=0.16, streak=0.06, bounce=0.55, **kw)
        fur_strokes(L, m, n, 14, fur_ang, seed, HIDE_D, 0.5 * (1 - far * 0.5))
        fur_strokes(L, m, n // 2, 12, fur_ang, seed + 1, C("#9a746a"), 0.22 * (1 - far), w=1.6)

    def seams(L, clip, paths, w=3.6, glow=1.0):
        for i, (a, b) in enumerate(paths):
            L.seam(jag(a, b, 0.16, 3, seed=i * 13 + int(a[1])), w, clip=clip, glow=glow, n=3)

    # ---------------- far legs (pushed back into the haze): far fore planted back, far hind reaching back
    L = R.layer()
    up = Masks.union(M.limb([(536, 520), (546, 620), (552, 712)], [140, 104, 66]),
                     M.blob([(490, 470), (590, 470), (600, 560), (550, 610), (496, 570)], n=6))
    hide(L, up, far=0.4, fur_ang=95, n=140, seed=3, line=0.3, rim=0.3)
    fade_top(L, 455, 520)
    R.add("far_fore_upper", L, "body", "leg_back_upper", (536, 540), 2)
    L = R.layer()
    lo = limb(L, [(552, 700), (560, 810), (566, 905)], [66, 52, 44], HIDE, far=0.4, tex=0.16, rim=0.6, round_=18)
    fur_strokes(L, lo, 80, 14, 100, 4, HIDE_D, 0.35)
    paw(L, (566, 905), G - 4, 52, HIDE, far=0.4)
    seams(L, lo, [((556, 740), (564, 870))], 4, 0.6)
    R.add("far_fore_lower", L, "far_fore_upper", "leg_back_lower", (552, 712), 1)
    L = R.layer()
    up = Masks.union(M.limb([(784, 480), (770, 600), (740, 700)], [170, 130, 74]),
                     M.blob([(720, 430), (830, 420), (856, 500), (826, 600), (760, 620), (720, 560)], n=6))
    hide(L, up, far=0.4, fur_ang=100, n=140, seed=5, line=0.3, rim=0.3)
    fade_top(L, 415, 480)
    R.add("far_hind_upper", L, "body", "leg_back_upper", (782, 520), 2)
    L = R.layer()
    lo = Masks.union(M.limb([(740, 690), (810, 790), (856, 846)], [72, 54, 46]), M.limb([(856, 842), (858, 905)], [46, 44]))
    hide(L, lo, far=0.4, fur_ang=110, n=80, seed=6, round_=18)
    paw(L, (858, 905), G - 4, 52, HIDE, far=0.4)
    seams(L, lo, [((756, 716), (846, 836))], 4, 0.6)
    R.add("far_hind_lower", L, "far_hind_upper", "leg_back_lower", (742, 700), 1)

    # ---------------- tail with a burning tip (curled up over the rump)
    L = R.layer()
    t1 = limb(L, [(800, 470), (846, 416), (858, 356)], [60, 42, 32], HIDE, tex=0.16, rim=0.85)
    fur_strokes(L, t1, 90, 14, -60, 7, HIDE_D, 0.45)
    seams(L, t1, [((814, 458), (852, 384))], 4)
    mane_light(L, t1, 0.3)
    R.add("tail_1", L, "body", "tail", (806, 474), 5)
    L = R.layer()
    t2 = limb(L, [(856, 366), (848, 306), (826, 254)], [32, 25, 18], HIDE, tex=0.16, rim=0.9)
    L.grad(t2, (852, 340), (828, 258), C("#ff5a14"), 0.0, 0.85)
    L.grad(t2, (840, 296), (826, 254), C("#ffd070"), 0.0, 0.8)
    R.add("tail_2", L, "tail_1", "tail", (856, 368), 6)
    L = R.layer()
    L.fire((826, 276), (836, 118), 80, seed=61, tongues=4, bend=0.05, turb=0.8)
    L.flame((826, 272), (830, 182), 36, seed=62, hot=1.25, turb=0.4)
    R.add("tail_flame", L, "tail_2", "hair", (826, 276), 7, cast=False)

    # ---------------- flame mane along the neck and back (rooted behind the body's edge)
    manes = [("mane_neck", [((400, 436), (452, 226), 92), ((440, 414), (520, 210), 100), ((372, 460), (392, 296), 64)]),
             ("mane_shoulder", [((490, 398), (580, 206), 104), ((540, 398), (622, 238), 92)]),
             ("mane_back", [((594, 404), (676, 268), 80), ((644, 414), (716, 304), 68), ((694, 416), (750, 334), 54)])]
    for k, (name, flames) in enumerate(manes):
        L = R.layer()
        for j, (b, t, w) in enumerate(flames):
            L.fire(b, t, w, seed=70 + k * 10 + j, tongues=3, turb=0.85, bend=0.05)
        R.add(name, L, "body", "hair", flames[0][0], 7 + k, cast=False)

    # ---------------- body: deep chest, tucked waist, molten fissures
    L = R.layer()
    body = Masks.union(
        M.blob([(372, 452), (420, 400), (486, 374), (570, 386), (650, 414), (730, 430), (796, 446), (830, 494),
                (822, 566), (786, 620), (730, 636), (670, 606), (610, 592), (560, 630), (500, 690), (440, 686),
                (392, 624)], n=8),
        M.limb([(486, 470), (424, 452), (384, 456)], [170, 160, 140]),
        spikes(M, [(376, 470), (384, 560), (420, 640), (480, 694)], 34, seed=12, side=-1),
        spikes(M, [(500, 692), (560, 640), (620, 600)], 18, seed=13, side=-1))
    hide(L, body, fur_ang=70, n=480, seed=11, round_=80)
    L.paint(M.blob([(388, 480), (450, 456), (520, 520), (510, 640), (460, 690), (404, 630)], n=8), HIDE,
            mode="atop", clip=body, line=0.0, soft=6, tex=0.16, rim=0.6, bounce=0.6)
    for k in range(4):
        x = 540 + k * 32
        L.brush(spline([(x, 470), (x + 12, 560), (x + 2, 640 - k * 8)], 4), 10, HIDE_D, 0.5, blur=5, clip=body)
        L.brush(spline([(x - 8, 470), (x + 2, 556), (x - 8, 632 - k * 8)], 4), 5, C("#8a6058"), 0.25, blur=3, clip=body)
    fur_strokes(L, M.blob([(380, 500), (450, 480), (500, 580), (470, 700), (400, 640)], n=6), 160, 24, 105, 12,
                C("#a07a70"), 0.28, w=2)
    L.seam(spline([(376, 440), (430, 412), (500, 392), (580, 400), (660, 414), (720, 414)], 5), 6, clip=body, n=4)
    seams(L, body, [((566, 430), (596, 610)), ((650, 430), (676, 600)), ((420, 500), (452, 650)),
                    ((760, 450), (800, 570))], 9.0)
    mane_light(L, body, 0.5)
    L.grad(body, (600, 560), (600, 700), C("#ff4a10"), 0.0, 0.3)
    R.add("body", L, "", "root", (600, 540), 10)

    # ---------------- near hind leg (coiled, hock well back)
    L = R.layer()
    up = Masks.union(M.limb([(730, 480), (712, 600), (680, 696)], [170, 130, 76]),
                     M.blob([(668, 446), (772, 430), (806, 500), (780, 600), (712, 630), (670, 560)], n=6),
                     spikes(M, [(800, 500), (790, 580), (760, 640), (730, 680)], 26, seed=23, side=-1))
    hide(L, up, fur_ang=100, n=260, seed=21, round_=56, line=0.3, rim=0.35)
    L.brush(spline([(770, 490), (750, 580), (712, 662)], 4), 14, HIDE_D, 0.5, blur=7, clip=up)
    seams(L, up, [((706, 500), (726, 640))], 8)
    mane_light(L, up, 0.35)
    fade_top(L, 425, 490)
    R.add("near_hind_upper", L, "body", "leg_front_upper", (726, 520), 14)
    L = R.layer()
    lo = Masks.union(M.limb([(680, 686), (744, 784), (792, 846)], [78, 58, 48]), M.limb([(792, 842), (784, 905)], [48, 46]))
    hide(L, lo, fur_ang=110, n=140, seed=22, round_=20)
    paw(L, (784, 905), G, 56, HIDE)
    seams(L, lo, [((700, 712), (780, 830))], 6)
    R.add("near_hind_lower", L, "near_hind_upper", "leg_front_lower", (682, 696), 13)

    # ---------------- near fore leg (braced forward)
    L = R.layer()
    up = Masks.union(M.limb([(470, 520), (478, 620), (488, 706)], [150, 112, 74]),
                     M.blob([(420, 470), (514, 462), (532, 560), (500, 620), (430, 590)], n=6),
                     spikes(M, [(520, 600), (524, 660), (516, 712)], 22, seed=33, side=-1))
    hide(L, up, fur_ang=100, n=260, seed=31, round_=46, line=0.3, rim=0.35)
    L.brush(spline([(510, 520), (510, 620), (500, 690)], 4), 12, HIDE_D, 0.5, blur=6, clip=up)
    seams(L, up, [((456, 560), (480, 680))], 8)
    mane_light(L, up, 0.35)
    fade_top(L, 455, 520)
    R.add("near_fore_upper", L, "body", "leg_front_upper", (470, 540), 16)
    L = R.layer()
    lo = limb(L, [(488, 696), (462, 800), (430, 905)], [72, 56, 46], HIDE, tex=0.16, rim=0.75, round_=20, bounce=0.5)
    fur_strokes(L, lo, 140, 14, 110, 32, HIDE_D, 0.5)
    paw(L, (430, 905), G, 58, HIDE)
    seams(L, lo, [((480, 730), (446, 870))], 6)
    R.add("near_fore_lower", L, "near_fore_upper", "leg_front_lower", (488, 706), 15)

    # ---------------- crest flames on the head (rooted behind the skull)
    L = R.layer()
    for j, (b, t, w) in enumerate([((340, 404), (376, 220), 70), ((300, 400), (318, 268), 54),
                                   ((382, 420), (456, 296), 64)]):
        L.fire(b, t, w, seed=90 + j, tongues=3, turb=0.85, bend=0.06)
    head_part("mane_head", L, "head", "hair", (340, 404), 19, cast=False)

    # ---------------- molten throat (seen between the jaws)
    L = R.layer()
    mo = M.blob([(372, 488), (300, 488), (220, 490), (176, 496), (182, 548), (250, 540), (330, 526), (376, 512)], n=6)
    L.fill(mo, C("#3a0806"), 1.0, blur=0.6)
    L.radial((300, 512), 90, C("#ff5a14"), 0.95, clip=mo)
    L.radial((320, 510), 44, C("#ffd070"), 0.9, clip=mo)
    tongue = M.blob([(330, 520), (270, 522), (214, 534), (200, 546), (240, 548), (310, 536)], n=5)
    L.paint(tongue, C("#c83a1a"), round_=8, rim=0.3, light=0.6, line=0.3)
    head_part("mouth", L, "head", "extra", (330, 505), 20)

    # ---------------- lower jaw (hangs open)
    L = R.layer()
    jaw = M.blob([(378, 498), (300, 512), (240, 528), (196, 548), (182, 566), (200, 578), (262, 566), (336, 546),
                  (388, 526)], n=8)
    L.paint(jaw, HIDE, round_=16, tex=0.16, rim=0.6, bounce=0.7)
    fur_strokes(L, jaw, 70, 12, 170, 41, HIDE_D, 0.45)
    for i in range(6):
        x = 200 + i * 24
        yb = 548 - i * 6.4
        h = 22 if i == 0 else 12
        L.fill(M.poly([(x - 5, yb + 2), (x + 5, yb + 2), (x - 1, yb - h)]), C("#f0e2c8"), 1.0, blur=0.4, mode="over")
    L.radial((260, 530), 80, C("#ff6a1a"), 0.5, clip=jaw)
    L.seam(jag((240, 552), (350, 528), 0.15, 3, seed=42), 2.6, clip=jaw, n=3)
    L.fill(M.limb([(214, 568), (212, 592), (214, 606)], [7, 5, 8]), C("#ffa030"), 1.0, blur=0.5, mode="over")
    L.fill(M.circle(214, 606, 3), C("#fff2c0"), 1.0, blur=0.4, mode="over")
    head_part("jaw", L, "head", "jaw", (366, 505), 21)

    # ---------------- head
    L = R.layer()
    ear_f = M.poly(spline([(424, 420), (418, 392), (450, 360), (522, 336), (480, 380), (456, 418)], 4, closed=True))
    L.paint(ear_f, HIDE, round_=14, far=0.35, rim=0.9, tex=0.16)
    ear = M.poly(spline([(392, 420), (386, 386), (416, 352), (496, 322), (448, 372), (426, 418)], 4, closed=True))
    L.paint(ear, HIDE, round_=14, rim=0.9, tex=0.16)
    L.paint(M.poly(spline([(400, 404), (398, 384), (424, 362), (470, 340), (434, 378), (416, 404)], 4, closed=True)),
            C("#5a1a12"), round_=6, light=0.3, mode="atop", line=0)
    skull = M.blob([(426, 444), (400, 398), (340, 380), (288, 388), (246, 410), (206, 432), (170, 446), (148, 462),
                    (150, 484), (178, 494), (232, 492), (292, 496), (350, 510), (406, 516), (434, 480)], n=8)
    L.paint(skull, HIDE, tex=0.16, rim=0.6, light=0.45, round_=40, bounce=0.5)
    HF = dict(mode="atop", line=0, soft=4, tex=0.1, clip=skull)
    L.paint(M.blob([(300, 392), (360, 386), (404, 420), (394, 462), (340, 472), (300, 440)], n=6), C("#423032"), **HF)
    L.paint(M.blob([(176, 450), (250, 420), (300, 430), (290, 470), (220, 486), (170, 480)], n=6), C("#3e2e30"), **HF)
    fur_strokes(L, skull, 180, 12, 15, 51, HIDE_D, 0.45)
    fur_strokes(L, skull, 90, 10, 15, 52, C("#9a746a"), 0.25, w=1.5)
    fur_strokes(L, M.blob([(330, 440), (410, 430), (430, 500), (380, 520), (330, 500)], n=6), 70, 20, 30, 53,
                C("#a07a70"), 0.3, w=2)
    L.brush(spline([(232, 422), (264, 408), (304, 414)], 4), 14, HIDE_D, 0.65, blur=3, clip=skull)
    L.brush(spline([(232, 412), (262, 400), (302, 404)], 4), 4, C("#a07a70"), 0.5, blur=1.5, clip=skull)
    for k in range(3):
        x = 196 + k * 18
        L.brush(spline([(x, 446 - k * 3), (x + 8, 458), (x + 4, 472)], 3), 3, C("#0c0606"), 0.6, blur=0.8, clip=skull)
    nose = M.blob([(144, 458), (164, 450), (176, 462), (168, 478), (148, 478)], n=5)
    L.paint(nose, C("#141012"), round_=8, spec=0.9, gloss=20, line=0.4)
    L.fill(M.ell(150, 470, 4, 3), C("#000000"), 0.8, blur=0.5, mode="atop")
    for i in range(7):
        x = 176 + i * 24
        h = 26 if i in (0, 5) else 13
        L.fill(M.poly([(x - 6, 488), (x + 6, 488), (x + 1, 488 + h)]), C("#f4e8d0"), 1.0, blur=0.4, mode="over")
    L.brush(spline([(176, 492), (260, 494), (350, 508)], 4), 4, C("#1a0606"), 0.7, blur=0.8, clip=skull)
    seams(L, skull, [((300, 446), (384, 480)), ((330, 398), (392, 440))], 5.0)
    L.radial((262, 430), 70, C("#ff7a1a"), 0.5, clip=skull)
    eye_glow(L, 264, 430, 10, slant=-14)
    mane_light(L, skull, 0.4)
    head_part("head", L, "body", "head", (410, 478), 22)

    # ---------------- fx
    head_part("eyes_fx", fx_glow(R, [(264, 430, 44, C("#ff8a1e"), 0.6)]), "head", "fx", (264, 430), 30, blend="add")
    head_part("maw_fx", fx_glow(R, [(290, 516, 90, C("#ff5a14"), 0.45), (214, 602, 22, C("#ffb040"), 0.5)]),
              "jaw", "fx", (366, 505), 31, blend="add")
    R.add("mane_fx", fx_glow(R, [(520, 310, 240, C("#ff5a14"), 0.4), (380, 320, 140, C("#ff6a1a"), 0.3)]),
          "body", "fx", (520, 400), 29, "add")
    R.add("tail_fx", fx_glow(R, [(830, 200, 140, C("#ff5a14"), 0.45)]), "tail_2", "fx", (826, 276), 28, "add")
    return R


# ================================================================== flame knight

STEEL = C("#2c2a32")
KN_ENV = [(0.0, C("#d8d0c8")), (0.22, C("#5a5560")), (0.42, C("#141218")), (0.66, C("#1c1418")), (0.86, C("#7a2a12")),
          (1.0, C("#ff8a3a"))]
CAPE = C("#7a141a")


def steel(L, m, r=None, far=0.0, base=STEEL, **kw):
    """Blackened, fire-lit plate armour."""
    kw.setdefault("rim", 0.8)
    kw.setdefault("spec", 1.0)
    L.paint(m, base, round_=r, metal=0.72, gloss=26, tex=0.07, light=0.5, far=far, env=KN_ENV, bounce=0.45, **kw)
    return m


def rivets(L, pts, r=4.5, far=0.0):
    for x, y in pts:
        L.paint(L.M.circle(x, y, r), GOLD_D, round_=r, spec=1.0, metal=0.5, gloss=12, line=0.4, far=far, rim=0.3)


def lames(L, clip, y0, y1, n, slope=0.0, x0=0, x1=1024):
    """Overlapping plate bands: a dark gap with a lit lip under it, n bands from y0 to y1."""
    for k in range(1, n):
        y = y0 + (y1 - y0) * k / n
        pts = [(x0, y + slope * (x0 - 512)), (x1, y + slope * (x1 - 512))]
        L.brush(pts, 5, C("#0a0608"), 0.85, blur=1.0, clip=clip)
        L.brush([(x, yy + 4) for x, yy in pts], 3, C("#ff7a2a"), 0.55, blur=1.0, clip=clip)
        L.brush([(x, yy - 6) for x, yy in pts], 6, C("#0a0608"), 0.35, blur=3, clip=clip)


def knee_cop(L, c, r, far=0.0):
    M = L.M
    cx, cy = c
    m = M.blob([(cx - r, cy), (cx - r * 0.6, cy - r * 0.8), (cx, cy - r), (cx + r * 0.7, cy - r * 0.7), (cx + r, cy),
                (cx + r * 0.6, cy + r * 0.8), (cx, cy + r), (cx - r * 0.7, cy + r * 0.7)], n=6)
    fin = M.poly([(cx - r * 0.5, cy - r * 0.2), (cx - r * 1.55, cy - r * 0.05), (cx - r * 0.5, cy + r * 0.45)])
    steel(L, Masks.union(m, fin), r * 0.6, far=far)
    L.paint(M.circle(cx, cy, r * 0.32), GOLD_D, round_=r * 0.3, spec=1.0, metal=0.5, far=far, line=0.5)
    return m


def flame_knight():
    R = Rig("flame_knight", 1024, feet=(512, 972), kind="humanoid")
    M = R.M
    F = (352, 556)                    # sword fist
    DIR = (-0.36, -0.933)             # blade direction
    GUARD = (F[0] + DIR[0] * 46, F[1] + DIR[1] * 46)
    TIP = (F[0] + DIR[0] * 520, F[1] + DIR[1] * 520)
    POM = (F[0] - DIR[0] * 104, F[1] - DIR[1] * 104)

    def blade_at(t):
        return lerp2(GUARD, TIP, t)

    def swordlight(L, clip, st=0.35):
        L.radial(blade_at(0.4), 330, C("#ff6a1a"), st * 0.6, clip=clip)

    HK, HC = 0.8, (486, 300)  # the helm is painted large and scaled down about the neck

    def hs(p):
        return (HC[0] + (p[0] - HC[0]) * HK, HC[1] + (p[1] - HC[1]) * HK)

    # ---------------- cape
    L = R.layer()
    hem = tatter([(430, 892), (520, 912), (620, 920), (720, 904), (800, 870), (846, 836)], 30, seed=101)
    cm = M.poly(spline([(452, 300), (600, 296), (660, 360), (726, 500), (790, 660), (846, 836)], 6) + hem[::-1] +
                [(420, 760), (436, 520)])
    L.paint(cm, CAPE, round_=80, far=0.3, tex=0.12, rim=0.75)
    drape(L, cm, (560, 220), freq=8, amp=0.9, seed=102, r0=110, r1=330)
    for pts in [[(560, 360), (610, 600), (650, 900)], [(620, 380), (700, 620), (760, 880)], [(500, 420), (510, 650), (520, 900)]]:
        fold(L, cm, spline(pts, 6), 20, alpha=0.6)
    swordlight(L, cm, 0.25)
    ember_edge(L, hem, cm, 5, seed=103)
    R.add("cape", L, "torso", "cape", (528, 318), 2)

    # ---------------- back leg
    L = R.layer()
    th = M.limb([(556, 580), (582, 660), (602, 744)], [104, 94, 76])
    L.paint(th, C("#2a262c"), round_=30, far=0.35, tex=0.25, tex_cell=1.2)  # mail
    cu = M.blob([(530, 600), (600, 590), (630, 680), (620, 736), (580, 740), (556, 670)], n=6)
    steel(L, cu, 24, far=0.35)
    lames(L, cu, 600, 740, 3, x0=520, x1=640)
    R.add("leg_back_upper", L, "hips", "leg_back_upper", (560, 600), 10)
    L = R.layer()
    gr = M.limb([(604, 744), (618, 830), (630, 912)], [76, 66, 58])
    steel(L, gr, 24, far=0.35)
    sab = M.blob([(604, 900), (656, 900), (676, 940), (674, 968), (560, 968), (556, 948), (590, 926)], n=6)
    steel(L, sab, 16, far=0.35)
    lames(L, sab, 905, 965, 3, slope=-0.25, x0=550, x1=680)
    knee_cop(L, (604, 746), 40, far=0.35)
    R.add("leg_back_lower", L, "leg_back_upper", "leg_back_lower", (604, 748), 9)

    # ---------------- back arm (fist low by the hip)
    L = R.layer()
    ua = M.limb([(596, 340), (614, 400), (626, 462)], [84, 74, 64])
    steel(L, ua, 24, far=0.3)
    lames(L, ua, 360, 460, 3, slope=-0.2, x0=570, x1=660)
    pd = M.blob([(560, 300), (612, 290), (660, 320), (676, 380), (650, 410), (600, 400), (566, 360)], n=8)
    L.shadow(pd, 0.6, (2, 8), 8)
    steel(L, pd, 34, far=0.3)
    lames(L, pd, 300, 410, 3, slope=0.25, x0=550, x1=690)
    for sx, sy in ((600, 300), (632, 304)):
        L.paint(M.poly([(sx - 12, sy + 8), (sx + 2, sy - 52), (sx + 14, sy + 8)]), STEEL, round_=8, metal=0.7, spec=1.0,
                far=0.3, env=KN_ENV)
    R.add("arm_back_upper", L, "torso", "arm_back_upper", (596, 346), 12)
    L = R.layer()
    va = M.limb([(626, 460), (636, 520), (640, 560)], [64, 60, 54])
    steel(L, va, 22, far=0.25)
    knee_cop(L, (626, 462), 32, far=0.25)
    fist = M.blob([(612, 556), (660, 552), (672, 590), (656, 616), (620, 614), (606, 588)], n=6)
    steel(L, fist, 16, far=0.25)
    for i in range(3):
        L.brush([(614, 572 + i * 13), (664, 570 + i * 13)], 3, C("#0a0608"), 0.7, blur=0.8, clip=fist)
    R.add("arm_back_lower", L, "arm_back_upper", "arm_back_lower", (626, 462), 13)

    # ---------------- front leg (stepping forward)
    L = R.layer()
    th = M.limb([(476, 580), (450, 660), (424, 742)], [108, 96, 78])
    L.paint(th, C("#2a262c"), round_=30, tex=0.25, tex_cell=1.2)
    cu = M.blob([(440, 590), (510, 596), (500, 680), (466, 740), (420, 734), (420, 660)], n=6)
    steel(L, cu, 26)
    lames(L, cu, 600, 740, 3, x0=400, x1=530)
    R.add("leg_front_upper", L, "hips", "leg_front_upper", (474, 600), 24)
    L = R.layer()
    gr = M.limb([(424, 744), (410, 830), (402, 912)], [80, 70, 60])
    steel(L, gr, 26)
    L.brush(spline([(410, 770), (398, 840), (392, 900)], 4), 4, C("#fff0d8"), 0.35, blur=1.5, clip=gr)
    sab = M.blob([(378, 900), (430, 900), (446, 936), (442, 968), (328, 968), (322, 950), (354, 928)], n=6)
    steel(L, sab, 16)
    lames(L, sab, 904, 966, 3, slope=-0.25, x0=320, x1=450)
    knee_cop(L, (424, 746), 42)
    R.add("leg_front_lower", L, "leg_front_upper", "leg_front_lower", (424, 748), 23)

    # ---------------- hips: faulds, mail skirt, tabard with a burning hem
    L = R.layer()
    mail = M.blob([(412, 540), (612, 540), (630, 640), (590, 664), (430, 664), (398, 630)], n=6)
    L.paint(mail, C("#3a3640"), round_=30, tex=0.35, tex_cell=1.0, spec=0.5, gloss=8)
    tab_hem = tatter([(462, 780), (510, 792), (562, 778)], 18, seed=111, step=13)
    tab = M.poly([(468, 560), (558, 560), (566, 700)] + tab_hem[::-1] + [(458, 700)])
    L.shadow(tab, 0.6, (3, 8), 7)
    L.paint(tab, CAPE, round_=20, tex=0.12, light=0.4)
    drape(L, tab, (512, 470), freq=12, amp=0.7, seed=112, r0=70, r1=200)
    gold_trim(L, spline([(470, 566), (462, 700), (462, 780)], 4), 4, clip=tab)
    gold_trim(L, spline([(556, 566), (564, 700), (562, 780)], 4), 4, clip=tab)
    flame_sigil(L, 512, 680, 26, clip=tab)
    ember_edge(L, tab_hem, tab, 4, seed=113)
    fa = M.blob([(424, 506), (604, 506), (622, 556), (608, 600), (420, 600), (406, 556)], n=6)
    L.shadow(fa, 0.6, (0, 8), 8)
    steel(L, fa, 30)
    lames(L, fa, 506, 604, 3, slope=0.04, x0=380, x1=640)
    belt = M.blob([(426, 500), (600, 500), (604, 530), (424, 532)], n=4)
    L.paint(belt, LEATHER, round_=10, spec=0.4, tex=0.2)
    buckle = M.blob([(490, 496), (534, 496), (536, 536), (490, 536)], n=4)
    L.paint(buckle, GOLD, round_=8, spec=1.0, metal=0.5, gloss=18)
    L.fill(M.ell(512, 516, 7, 9), C("#ff8a2a"), 1.0, blur=0.5, mode="over")
    swordlight(L, L.alpha(), 0.3)
    R.add("hips", L, "", "root", (512, 560), 26)

    # ---------------- torso: breastplate with a molten heart
    L = R.layer()
    gor = M.blob([(430, 286), (530, 276), (566, 300), (552, 340), (440, 344), (420, 316)], n=6)
    ch = M.blob([(396, 330), (430, 296), (520, 284), (600, 296), (634, 340), (620, 420), (588, 500), (560, 522),
                 (450, 524), (420, 500), (400, 420)], n=8)
    steel(L, ch, 60)
    # 3/4 ridge down the front, plackart overlap and a lit flank
    L.brush(spline([(476, 300), (466, 400), (470, 510)], 5), 10, C("#0c0a10"), 0.5, blur=4, clip=ch)
    L.brush(spline([(468, 300), (458, 400), (462, 510)], 5), 4, C("#fff0d8"), 0.55, blur=1.6, clip=ch)
    pl = M.blob([(410, 456), (520, 440), (606, 462), (590, 524), (424, 526)], n=6)
    L.shadow(pl, 0.6, (0, -6), 6)
    steel(L, pl, 30, mode="atop", clip=ch)
    L.brush(spline([(412, 456), (520, 440), (606, 462)], 5), 4, C("#ff7a2a"), 0.6, blur=1.2, clip=ch)
    gold_trim(L, spline([(410, 350), (440, 312), (520, 300), (596, 312), (622, 352)], 5), 5, clip=ch)
    # molten heart: a cracked ember sigil set in the chest
    L.seam(jag((480, 350), (488, 430), 0.2, 3, seed=121), 6, clip=ch)
    L.seam(jag((452, 380), (520, 392), 0.2, 3, seed=122), 5, clip=ch)
    gem = M.blob([(484, 372), (500, 388), (486, 410), (470, 390)], n=4)
    L.paint(gem, C("#ff7a1a"), round_=6, spec=1.0, light=0.8, rim=0.0, line=0.6)
    L.fill(M.ell(484, 388, 5, 7), C("#fff2c0"), 1.0, blur=0.6, mode="over")
    L.shadow(gor, 0.6, (0, 8), 7)
    steel(L, gor, 20)
    lames(L, gor, 280, 344, 2, x0=410, x1=570)
    rivets(L, [(426, 362), (606, 362), (418, 450), (608, 456)])
    swordlight(L, ch, 0.35)
    R.add("torso", L, "hips", "torso", (512, 512), 30)

    # ---------------- plume of fire on the helm crest
    L = R.layer()
    for j, (b, t, w) in enumerate([((482, 128), (578, 22), 84), ((508, 124), (640, 52), 78), ((530, 134), (680, 110), 62)]):
        L.fire(b, t, w, seed=130 + j, tongues=3, turb=0.85, bend=0.07)
    scale_layer(L, HC, HK)
    R.add("plume", L, "head", "hair", hs((496, 130)), 34, cast=False)

    # ---------------- head: horned great helm with a burning visor slit
    L = R.layer()
    for pts, ws, far in (([(530, 156), (574, 112), (596, 64), (584, 28)], [34, 26, 14, 2], 0.35),
                         ([(440, 160), (398, 120), (378, 72), (394, 32)], [38, 30, 16, 2], 0.0)):
        hm = M.limb(pts, ws, n=6)
        L.paint(hm, C("#241a18"), round_=10, spec=0.8, gloss=14, far=far, tex=0.2, rim=0.8)
        for k in range(4):
            c = lerp2(pts[0], pts[2], 0.15 + k * 0.2)
            L.brush([polar(c, 20, 14), polar(c, 200, 14)], 2.5, C("#0a0404"), 0.5, blur=0.6, clip=hm)
        L.grad(hm, pts[1], pts[3], C("#ff7a2a"), 0.0, 0.7)
    helm = M.blob([(400, 196), (404, 150), (432, 122), (484, 110), (534, 120), (560, 150), (566, 204), (560, 262),
                   (540, 298), (480, 310), (420, 300), (402, 262)], n=8)
    steel(L, helm, 46)
    side = M.blob([(490, 120), (536, 122), (562, 152), (568, 206), (560, 264), (540, 298), (494, 306), (500, 210)], n=8)
    steel(L, side, 30, mode="atop", clip=helm, base=darken(STEEL, 0.2), line=0.0)
    L.brush(spline([(484, 112), (480, 200), (486, 304)], 5), 9, C("#0a080c"), 0.6, blur=3, clip=helm)
    L.brush(spline([(474, 114), (470, 200), (476, 302)], 5), 3, C("#fff0d8"), 0.6, blur=1.2, clip=helm)
    band = M.limb([(400, 206), (500, 214), (566, 208)], [34, 34, 30])
    L.shadow(Masks.inter(band, helm), 0.5, (0, 5), 4)
    steel(L, Masks.inter(band, helm), 12, mode="atop", clip=helm)
    gold_trim(L, spline([(402, 190), (500, 198), (566, 192)], 4), 3.5, clip=helm)
    gold_trim(L, spline([(402, 224), (500, 232), (566, 226)], 4), 3.5, clip=helm)
    slit = M.limb([(406, 206), (446, 208), (478, 212)], [9, 10, 8])
    L.fill(slit, C("#120404"), 1.0, blur=0.5)
    L.radial((446, 210), 70, C("#ff6a1a"), 0.6, clip=helm)
    L.fill(M.limb([(410, 207), (446, 209), (474, 212)], [5, 6, 4]), C("#ffb040"), 1.0, blur=0.6, mode="over")
    L.fill(M.limb([(420, 208), (446, 209), (466, 211)], [2.4, 3, 2]), C("#fffbe8"), 1.0, blur=0.4, mode="over")
    for i in range(3):
        for j in range(3):
            x, y = 432 + i * 15, 252 + j * 14
            L.fill(M.circle(x, y, 3.6), C("#120404"), 1.0, blur=0.4, mode="atop")
            L.fill(M.circle(x, y, 1.8), C("#ff9a2a"), 0.9, blur=0.4, mode="atop")
    rivets(L, [(412, 270), (548, 270), (420, 160), (546, 160)], 4)
    swordlight(L, helm, 0.35)
    scale_layer(L, HC, HK)
    R.add("head", L, "torso", "head", (486, 300), 36)

    # ---------------- burning greatsword
    L = R.layer()
    perp = (-DIR[1], DIR[0])
    ang = math.degrees(math.atan2(DIR[1], DIR[0]))
    blade = M.limb([GUARD, blade_at(0.5), blade_at(0.88), TIP], [80, 72, 58, 2], n=4)
    steel(L, blade, 12, spec=1.2, rim=0.5, base=C("#6a6672"))
    L.brush([lerp2(GUARD, TIP, 0.02), lerp2(GUARD, TIP, 0.95)], 26, C("#e8e0dc"), 0.25, blur=6, clip=blade,
            taper=(1, 0.3))
    L.brush([GUARD, blade_at(0.86)], 12, C("#240604"), 0.9, blur=1.0, clip=blade, taper=(1, 0.5))
    L.brush([GUARD, blade_at(0.86)], 8, C("#ff6a1a"), 1.0, blur=1.2, clip=blade, taper=(1, 0.4))
    L.brush([GUARD, blade_at(0.84)], 3, C("#fff2c0"), 1.0, blur=0.6, clip=blade, taper=(1, 0.3))
    for side in (1, -1):
        e0 = (GUARD[0] + perp[0] * 34 * side, GUARD[1] + perp[1] * 34 * side)
        e1 = (TIP[0] + perp[0] * 2 * side, TIP[1] + perp[1] * 2 * side)
        L.brush([e0, lerp2(e0, e1, 0.9)], 5, C("#ff8a3a"), 0.6, blur=2, clip=blade)
    L.grad(blade, blade_at(0.2), TIP, C("#ff5a14"), 0.0, 0.45)
    quil = M.limb([polar(GUARD, ang + 90, 88), polar(GUARD, ang + 70, 40), GUARD, polar(GUARD, ang - 70, 40),
                   polar(GUARD, ang - 90, 88)], [10, 22, 30, 22, 10], n=4)
    tips_ = [polar(polar(GUARD, ang + 90, 88), ang + 20, 26), polar(polar(GUARD, ang - 90, 88), ang - 20, 26)]
    quil = Masks.union(quil, M.limb([polar(GUARD, ang + 90, 84), tips_[0]], [12, 2]),
                       M.limb([polar(GUARD, ang - 90, 84), tips_[1]], [12, 2]))
    L.shadow(quil, 0.6, (2, 6), 5)
    steel(L, quil, 10)
    L.paint(M.circle(GUARD[0], GUARD[1], 14), GOLD, round_=8, spec=1.0, metal=0.5)
    L.fill(M.circle(GUARD[0], GUARD[1], 6), C("#ff8a2a"), 1.0, blur=0.6, mode="over")
    grip = M.limb([GUARD, F, POM], [24, 22, 20])
    L.paint(grip, C("#2a1610"), round_=8, tex=0.3)
    for k in range(7):
        c = lerp2(GUARD, POM, 0.1 + k * 0.12)
        L.brush([polar(c, ang + 60, 13), polar(c, ang - 120, 13)], 3, C("#0a0404"), 0.7, blur=0.6, clip=grip)
    L.paint(M.circle(POM[0], POM[1], 18), STEEL, round_=10, metal=0.7, spec=1.0, env=KN_ENV)
    L.fill(M.circle(POM[0], POM[1], 7), C("#ff8a2a"), 1.0, blur=0.6, mode="over")
    R.add("greatsword", L, "arm_front_lower", "weapon", F, 40)
    # flames licking up off the blade (two layers that flicker separately)
    for k, ts in enumerate([(0.1, 0.36, 0.62, 0.86), (0.22, 0.48, 0.74)]):
        L = R.layer()
        for j, t in enumerate(ts):
            b = polar(blade_at(t), ang + 90, 22)
            w = 70 - t * 30
            L.fire(b, (b[0] + 56 - t * 24, b[1] - 120 + t * 40), w, seed=140 + k * 10 + j,
                   tongues=3, turb=0.85, bend=0.06, alpha=0.9)
        R.add(f"blade_flame_{k + 1}", L, "greatsword", "hair", blade_at(0.4), 41 + k, cast=False)

    # ---------------- front arm with the great pauldron
    L = R.layer()
    ua = M.limb([(434, 340), (414, 400), (396, 458)], [92, 80, 70])
    steel(L, ua, 26)
    lames(L, ua, 360, 456, 3, slope=0.25, x0=360, x1=460)
    pd = M.blob([(368, 340), (390, 306), (440, 296), (484, 312), (494, 356), (476, 402), (420, 412), (372, 390)], n=8)
    L.shadow(pd, 0.6, (2, 10), 10)
    steel(L, pd, 40)
    lames(L, pd, 306, 412, 3, slope=-0.3, x0=360, x1=510)
    gold_trim(L, spline([(376, 384), (420, 410), (480, 400)], 4), 4.5, clip=pd)
    for sx, sy, h in ((384, 322, 46), (408, 308, 54), (434, 302, 40)):
        sp = M.poly([(sx - 13, sy + 10), (sx - 2, sy - h), (sx + 13, sy + 10)])
        L.paint(sp, STEEL, round_=8, metal=0.7, spec=1.0, env=KN_ENV, rim=0.8)
        L.grad(sp, (sx, sy), (sx - 2, sy - h), C("#ff7a2a"), 0.0, 0.6)
    swordlight(L, L.alpha(), 0.4)
    R.add("arm_front_upper", L, "torso", "arm_front_upper", (436, 352), 44)
    L = R.layer()
    va = M.limb([(396, 456), (376, 504), (364, 540)], [72, 64, 58])
    steel(L, va, 24)
    L.brush(spline([(384, 470), (370, 510), (360, 534)], 3), 4, C("#fff0d8"), 0.4, blur=1.5, clip=va)
    fist = M.blob([(326, 536), (360, 520), (392, 532), (394, 570), (370, 588), (330, 580)], n=6)
    steel(L, fist, 16)
    for i in range(3):
        L.brush([(330 + i * 2, 546 + i * 12), (380 + i * 2, 540 + i * 12)], 3, C("#0a0608"), 0.7, blur=0.8, clip=fist)
    L.paint(M.limb([(372, 530), (350, 522), (336, 532)], [16, 14, 10]), STEEL, round_=6, metal=0.7, spec=1.0, env=KN_ENV)
    knee_cop(L, (396, 458), 34)
    swordlight(L, L.alpha(), 0.45)
    R.add("arm_front_lower", L, "arm_front_upper", "arm_front_lower", (396, 460), 46)

    # ---------------- fx
    Fx = fx_glow(R, [(446, 210, 70, C("#ff7a1a"), 0.55), (446, 210, 26, C("#ffd070"), 0.5)])
    scale_layer(Fx, HC, HK)
    R.add("visor_fx", Fx, "head", "fx", hs((446, 210)), 95, "add")
    R.add("heart_fx", fx_glow(R, [(484, 390, 60, C("#ff6a1a"), 0.5)]), "torso", "fx", (484, 390), 94, "add")
    R.add("sword_fx", fx_glow(R, [(blade_at(0.4)[0] + 30, blade_at(0.4)[1] - 30, 260, C("#ff5a14"), 0.4),
                                  (blade_at(0.75)[0] + 30, blade_at(0.75)[1] - 30, 160, C("#ff7a1a"), 0.35)]),
          "greatsword", "fx", F, 96, "add")
    Fx = fx_glow(R, [(570, 80, 160, C("#ff5a14"), 0.4)])
    scale_layer(Fx, HC, HK)
    R.add("plume_fx", Fx, "head", "fx", hs((496, 130)), 93, "add")
    return R


RIGS = {
    "cultist": cultist,
    "fire_imp": fire_imp,
    "ember_hound": ember_hound,
    "flame_knight": flame_knight,
}


def main(ids=None):
    for rid in ids or list(RIGS):
        t = time.time()
        RIGS[rid]().save()
        _NOISE.clear()
        print("  %s %.1fs" % (rid, time.time() - t))


if __name__ == "__main__":
    main(sys.argv[1:] or None)

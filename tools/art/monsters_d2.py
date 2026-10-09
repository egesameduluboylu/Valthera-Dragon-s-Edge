"""Dungeon 2 (the Mushroom Cave) monsters as painted cut-out rigs (M8 style).

    python3 tools/art/monsters_d2.py                        # all six
    python3 tools/art/monsters_d2.py cave_slime glow_bat    # just these

mushroom_mage, cave_slime, toxic_toad, glow_bat, shroom_brute (elite) and spore_mother (boss). Every
monster faces left. Each part is painted on its own full-canvas layer by a small numpy painter: shapes
become masks, masks become height fields, the height fields are lit (warm key light from the upper
left, cool violet fill, a bioluminescent cyan-green rim on the far edge, speculars on wet and glossy
surfaces, brush-noise texture) at 2x and downscaled with LANCZOS. Glowing things (spots, eyes, spores,
the relic) get a near-white core, a saturated halo and light spill onto their own part; the halos that
should pulse are separate "fx" parts with blend "add".

Rigs go to assets/rigs/<id>/ (see rig.py) and the still pictures to assets/sprites/enemies/<id>.png
(512 px, the boss 768 px).
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

import rig as rigmod  # noqa: E402

SS = 2  # working pixels per canvas pixel
F32 = np.float32


# ------------------------------------------------------------------ colour and math helpers

def col(c):
    """'#rrggbb' or an (r, g, b) 0..255 tuple or a float array -> float rgb 0..1."""
    if isinstance(c, np.ndarray):
        return c.astype(F32)
    if isinstance(c, str):
        h = c.lstrip("#")
        return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)
    return np.array(c[:3], F32) / 255.0


def mixc(a, b, t):
    a, b = col(a), col(b)
    return a + (b - a) * t


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def n3(x, y, z):
    v = np.array([x, y, z], F32)
    return v / np.linalg.norm(v)


KEY = n3(-0.55, -0.74, 0.46)          # warm key light from the upper left, toward the viewer
KEY_C = np.array([1.0, 0.93, 0.82], F32)
FILL = n3(0.62, 0.40, 0.45)           # cool violet bounce from the lower right
FILL_C = np.array([0.26, 0.22, 0.46], F32)
HALF = n3(KEY[0], KEY[1], KEY[2] + 1.0)
CAVE_RIM = "#6dffd6"                  # bioluminescent cyan-green rim light from the cave behind


def _box(a, r, axis):
    if r < 1:
        return a
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=F32)
    if axis == 0:
        return (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
    return (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)


def _small_blur(a, s, passes=4):
    r = max(1, int(round((math.sqrt(12 * s * s / passes + 1) - 1) / 2)))
    for _ in range(passes):
        a = _box(_box(a, r, 0), r, 1)
    return a


def fblur(a, s):
    """Smooth Gaussian-like blur of a float array, sigma s pixels (large sigmas work on a reduced copy)."""
    if s < 0.6:
        return a
    if s <= 6 or min(a.shape) < 16:
        return _small_blur(a, s)
    f = max(1, int(s / 3.0))
    h, w = a.shape
    sw, sh = max(2, w // f), max(2, h // f)
    small = np.asarray(Image.fromarray(a.astype(F32), "F").resize((sw, sh), Image.BOX), F32)
    small = _small_blur(small, s * sw / w)
    return np.asarray(Image.fromarray(small, "F").resize((w, h), Image.BICUBIC), F32)


def crspline(pts, n=10, closed=False):
    """Catmull-Rom spline through pts."""
    P = [np.array(p, float) for p in pts]
    if len(P) < 3:
        return [tuple(p) for p in P]
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    if not closed:
        out.append(tuple(P[-2]))
    return out


def rot(pts, c, deg):
    a = math.radians(deg)
    cs, sn = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * cs - (y - c[1]) * sn, c[1] + (x - c[0]) * sn + (y - c[1]) * cs) for x, y in pts]


def ell_pts(cx, cy, rx, ry, rotd=0.0, a0=0.0, a1=360.0, n=72):
    pts = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
           for a in np.linspace(a0, a1, n, endpoint=(a1 - a0) < 360)]
    return rot(pts, (cx, cy), rotd) if rotd else pts


def lerp_pt(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# ------------------------------------------------------------------ canvas, masks, noise

class Canvas:
    """The working canvas of one rig: size, masks at SS x, shared noise fields."""

    def __init__(self, W, H, seed=7):
        self.W, self.H = W, H
        self.w, self.h = W * SS, H * SS
        self.seed = seed
        self._noise = {}
        self.xf = (1.0, 0.0, 0.0)  # (scale, ox, oy): design coordinates scale about (ox, oy)

    def P(self, x, y):
        s, ox, oy = self.xf
        return ox + (x - ox) * s, oy + (y - oy) * s

    @property
    def s(self):
        return self.xf[0]

    # ---- masks (PIL "L" at working size; coordinates in canvas pixels)
    def blank(self):
        return Image.new("L", (self.w, self.h), 0)

    def poly(self, pts, smooth_n=0):
        if smooth_n:
            pts = crspline(pts, smooth_n, closed=True)
        m = self.blank()
        ImageDraw.Draw(m).polygon([(px * SS, py * SS) for px, py in (self.P(x, y) for x, y in pts)], fill=255)
        return m

    def ell(self, cx, cy, rx, ry, rotd=0.0):
        return self.poly(ell_pts(cx, cy, rx, ry, rotd, n=96))

    def limb(self, pts, radii, n=12, m=None):
        """A tapered tube along a smooth path through pts with radius radii[i] at pts[i] (round ends)."""
        m = m or self.blank()
        d = ImageDraw.Draw(m)
        if isinstance(radii, (int, float)):
            radii = [radii] * len(pts)
        path = crspline(pts, n) if len(pts) > 2 else [lerp_pt(pts[0], pts[1], t) for t in np.linspace(0, 1, n)]
        seg = len(pts) - 1
        # radius along the path by parameter
        rs = []
        for i in range(len(path)):
            u = i / max(1, len(path) - 1) * seg
            j = min(int(u), seg - 1)
            f = u - j
            rs.append((radii[j] + (radii[j + 1] - radii[j]) * f) * self.s)
        path = [self.P(x, y) for x, y in path]
        prev = None
        for (x, y), r in zip(path, rs):
            if prev is not None:
                px, py, pr = prev
                dist = math.hypot(x - px, y - py)
                steps = max(1, int(dist / max(0.6, min(r, pr) * 0.18)))
                for k in range(1, steps + 1):
                    t = k / steps
                    cx, cy, rr = px + (x - px) * t, py + (y - py) * t, pr + (r - pr) * t
                    d.ellipse(((cx - rr) * SS, (cy - rr) * SS, (cx + rr) * SS, (cy + rr) * SS), fill=255)
            else:
                d.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=255)
            prev = (x, y, r)
        return m

    # ---- noise fields (float, roughly zero mean, unit std), cached per canvas
    def noise(self, kind):
        if kind in self._noise:
            return self._noise[kind]
        rng = np.random.default_rng(self.seed * 31 + len(self._noise))
        w, h = self.w, self.h

        def vn(scale, aspect=1.0):
            sw, sh = max(2, int(w / (scale * aspect))), max(2, int(h / scale))
            small = rng.standard_normal((sh, sw)).astype(F32)
            return np.asarray(Image.fromarray(small, "F").resize((w, h), Image.BICUBIC), F32)

        if kind == "grain":
            a = fblur(rng.standard_normal((h, w)).astype(F32), 0.8)
        elif kind == "mottle":
            a = vn(16 * SS) + 0.5 * vn(7 * SS) + 0.2 * vn(3 * SS)
        elif kind == "large":
            a = vn(60 * SS) + 0.5 * vn(28 * SS)
        elif kind == "hstreak":
            a = vn(3 * SS, aspect=10) + 0.5 * vn(1.5 * SS, aspect=8)
        elif kind == "vstreak":
            a = (vn(3 * SS, aspect=10) + 0.5 * vn(1.5 * SS, aspect=8)).T.copy() if w == h else vn(3 * SS, 0.1)
        elif kind == "cells":
            # bubbly / warty cells: thresholded blobs
            a = vn(5 * SS) + 0.4 * vn(2.5 * SS)
        else:
            raise KeyError(kind)
        a = (a - a.mean()) / (a.std() + 1e-6)
        self._noise[kind] = a.astype(F32)
        return self._noise[kind]


def U(*ms):
    out = ms[0].copy()
    for m in ms[1:]:
        out = Image.fromarray(np.maximum(np.asarray(out), np.asarray(m)))
    return out


def SUB(a, b):
    return Image.fromarray(np.clip(np.asarray(a).astype(np.int16) - np.asarray(b), 0, 255).astype(np.uint8))


def AND(a, b):
    return Image.fromarray((np.asarray(a).astype(np.uint16) * np.asarray(b) // 255).astype(np.uint8))


def bbox(m, pad, w, h):
    b = m.getbbox() if isinstance(m, Image.Image) else None
    if b is None:
        return None
    x0, y0, x1, y1 = b
    return max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)


def mcrop(m, box):
    x0, y0, x1, y1 = box
    return np.asarray(m.crop(box), F32) / 255.0


# ------------------------------------------------------------------ layer painter

class Layer:
    """One part being painted: premultiplied float RGB + alpha at working size."""

    def __init__(self, cv):
        self.cv = cv
        self.rgb = np.zeros((cv.h, cv.w, 3), F32)
        self.a = np.zeros((cv.h, cv.w), F32)

    def _box(self, m, pad=6):
        return bbox(m, pad, self.cv.w, self.cv.h)

    def _over(self, box, c, al):
        x0, y0, x1, y1 = box
        A = self.a[y0:y1, x0:x1]
        R = self.rgb[y0:y1, x0:x1]
        R *= (1 - al)[..., None]
        R += c * al[..., None]
        A *= (1 - al)
        A += al

    # ---------------------------------------------------------- volumetric paint
    def paint(self, m, base, dark=None, lite=None, rimc=CAVE_RIM, rim=0.75, spec=0.15, shin=18, tex=0.10,
              grain="mottle", var=None, line=1.0, lw=2.0, round_=1.0, size=None, wrap=0.45, alpha=1.0,
              clip=None, fres=None, ao=0.25, flat=0.0, tilt=(0.0, 0.0), emit=None, hmap=None, ramp=0.35):
        """Paints mask m as a lit, rounded form. base/dark/lite: mid, shadow and light colours. rim: far-edge
        rim light strength. spec/shin: specular. tex: brush-noise amount; var=(colour, amount) paints a
        large-scale colour variation. line: thin colour-matched contour that fades where lit (lw canvas px).
        size: half-thickness override (canvas px). fres=(colour, amount): all-round edge glow
        (translucency). ao: darkening toward the lower mask edge. tilt: bend all normals (x, y).
        emit=(colour, amount): self-lit (less shading). hmap: extra height detail array (same box)."""
        box = self._box(m, 8)
        if box is None:
            return None
        x0, y0, x1, y1 = box
        a = mcrop(m, box)
        if clip is not None:
            a = a * mcrop(clip, box)
        area = a.sum()
        if area < 4:
            return None
        cv = self.cv
        base = col(base)
        dark = col(dark) if dark is not None else np.clip(base * 0.30 + col("#1c1030") * 0.45, 0, 1)
        lite = col(lite) if lite is not None else np.clip(base * 1.28 + KEY_C * 0.16, 0, 1)
        if size is None:
            gy, gx = np.gradient(a)
            per = np.hypot(gx, gy).sum() + 1e-3
            R = area / per
        else:
            R = size * SS * cv.s
        s1 = max(1.0, R)
        h = (fblur(a, s1 * 0.4) + fblur(a, s1 * 0.9) + fblur(a, s1 * 1.8)) / 3.0
        hm = float(h[a > 0.5].max()) if (a > 0.5).any() else 1.0
        u = np.clip((h - 0.26) / max(1e-3, hm - 0.26), 0, 1)
        z = np.sqrt(np.clip(1 - (1 - u) ** 2, 0, 1)) * round_ + u * (1 - round_)
        H = z * R * 1.15
        if hmap is not None:
            H = H + hmap
        gy, gx = np.gradient(H)
        nx, ny = -gx + tilt[0], -gy + tilt[1]
        nz = np.ones_like(nx) * (1.0 + flat * 3)
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx * inv, ny * inv, nz * inv
        k = 1.0
        d = nx * KEY[0] + ny * KEY[1] + nz * KEY[2]
        v = np.clip((d + wrap) / (1 + wrap), 0, 1)
        if ramp:
            # large-scale value design: the form falls off from the lit upper left to the lower right
            ys, xs = np.nonzero(a > 0.5)
            if len(xs):
                lx, ly = -KEY[0], -KEY[1]
                ln = math.hypot(lx, ly)
                lx, ly = lx / ln, ly / ln
                pr = xs * lx + ys * ly
                p0, p1 = pr.min(), pr.max()
                yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(F32)
                t = ((xx * lx + yy * ly) - (p0 + p1) / 2) / max(1.0, p1 - p0)
                v = np.clip(v - ramp * t, 0, 1)
        cv = self.cv
        if tex:
            t = cv.noise(grain)[y0:y1, x0:x1] * 0.75 + cv.noise("large")[y0:y1, x0:x1] * 0.4
            v = np.clip(v + tex * 0.3 * t, 0, 1)
        if ao:
            bottom = np.clip(ny, 0, 1) * (1 - nz)
            v = v * (1 - ao * smooth(0.0, 0.6, bottom))
        lo = smooth(0.0, 0.55, v)[..., None]
        hi = smooth(0.55, 1.0, v)[..., None]
        c = dark + (base - dark) * lo
        c = c + (lite - c) * hi
        if var is not None:
            vc, va = var
            f = smooth(-0.6, 1.2, cv.noise("large")[y0:y1, x0:x1])[..., None] * va
            c = c + (col(vc) - c) * f * (0.4 + 0.6 * lo)
        if tex:
            c = c * (1 + tex * 0.18 * cv.noise("grain")[y0:y1, x0:x1][..., None])
        fl = np.clip(nx * FILL[0] + ny * FILL[1] + nz * FILL[2], 0, 1) ** 2
        c = c + FILL_C * (fl * 0.22 * (1 - v))[..., None]
        if emit is not None:
            ec, ea = emit
            c = c + (col(ec) - c) * ea
        if spec:
            sh = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** shin
            c = c + np.array([1.0, 0.97, 0.9], F32) * (sh * spec)[..., None]
        edge = 1 - nz
        if rim:
            r = smooth(0.25, 0.85, edge) * np.clip(nx * 0.95 - ny * 0.25 + 0.05, 0, 1)
            c = c + col(rimc) * (r * rim)[..., None]
        if fres is not None:
            fc, fa = fres
            c = c + col(fc) * (smooth(0.2, 0.9, edge) * fa)[..., None]
        al = a * alpha
        if line:
            lwp = lw * SS
            inner = np.clip((fblur(a, lwp * 0.6) - 0.3) / 0.55, 0, 1)
            e = np.clip(a - inner, 0, 1)
            lc = dark * 0.5
            la = e * line * (1 - 0.85 * smooth(0.35, 0.9, v))
            c = c + (lc - c) * la[..., None]
        c = np.clip(c, 0, 1.5)
        self._over(box, c, al)
        return box

    # ---------------------------------------------------------- flat fills and blends
    def fill(self, m, c, alpha=1.0, mode="over", soft=0.0, clip=None, grad=None):
        """Flat colour through mask m. mode over | add | screen | mul. soft: blur (canvas px). clip: a mask
        or 'self' (only where this layer is already painted). grad=(c2, (x0,y0), (x1,y1)) linear ramp."""
        pad = int(soft * SS * 3) + 4
        box = self._box(m, pad)
        if box is None:
            return
        x0, y0, x1, y1 = box
        a = mcrop(m, box)
        if soft:
            a = fblur(a, soft * SS)
        if clip is not None:
            a = a * (self.a[y0:y1, x0:x1] if isinstance(clip, str) else mcrop(clip, box))
        a = a * alpha
        c = col(c)
        if grad is not None:
            c2, p0, p1 = grad
            p0, p1 = self.cv.P(*p0), self.cv.P(*p1)
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(F32)
            dx, dy = (p1[0] - p0[0]) * SS, (p1[1] - p0[1]) * SS
            t = np.clip(((xx - p0[0] * SS) * dx + (yy - p0[1] * SS) * dy) / (dx * dx + dy * dy + 1e-6), 0, 1)
            c = c + (col(c2) - c) * t[..., None]
        self.blend(box, c, a, mode)

    def blend(self, box, c, a, mode):
        x0, y0, x1, y1 = box
        if mode == "over":
            self._over(box, c, a)
            return
        R = self.rgb[y0:y1, x0:x1]
        A = self.a[y0:y1, x0:x1]
        if mode == "add":
            R += c * (a * A)[..., None]
        elif mode == "screen":
            cc = c * a[..., None] if np.ndim(c) == 1 else c * a[..., None]
            R += (A[..., None] - R) * cc
        elif mode == "mul":
            R *= 1 - (1 - c) * a[..., None]
        np.minimum(R, A[..., None] * 1.0, out=R)

    def glow(self, cx, cy, r, c, amt=1.0, mode="spill", clip=None, core=None):
        """Radial light. mode 'spill': adds light onto what is already painted; 'halo': paints a soft
        light with its own alpha (for fx layers); core=(colour, radius frac) adds a bright centre."""
        cv = self.cv
        cx, cy = cv.P(cx, cy)
        R = r * SS * cv.s
        x0, y0 = max(0, int(cx * SS - R * 2.2)), max(0, int(cy * SS - R * 2.2))
        x1, y1 = min(cv.w, int(cx * SS + R * 2.2)), min(cv.h, int(cy * SS + R * 2.2))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(F32)
        d2 = ((xx - cx * SS) ** 2 + (yy - cy * SS) ** 2) / (R * R)
        f = np.exp(-d2 * 2.2) * 0.75 + np.exp(-d2 * 7.0) * 0.25
        if clip is not None:
            f = f * mcrop(clip, (x0, y0, x1, y1))
        box = (x0, y0, x1, y1)
        cc = col(c)
        if mode == "spill":
            self.blend(box, cc, f * amt, "add")
        else:
            al = np.clip(f * amt, 0, 1)
            self._over(box, cc, al)
        if core is not None:
            c2, fr = core
            g = np.exp(-d2 / (fr * fr) * 2.5)
            if mode == "spill":
                self.blend(box, col(c2), g * amt, "add")
            else:
                self._over(box, col(c2), np.clip(g * amt, 0, 1))

    def stroke(self, pts, w0, w1=None, c="#000000", alpha=1.0, soft=0.5, clip=None, mode="over", n=10):
        """A tapered painted stroke (width w0 -> w1 canvas px)."""
        w1 = w0 if w1 is None else w1
        rs = [w0 / 2 + (w1 / 2 - w0 / 2) * i / max(1, len(pts) - 1) for i in range(len(pts))]
        m = self.cv.limb(pts, rs, n=n)
        self.fill(m, c, alpha=alpha, soft=soft, clip=clip, mode=mode)
        return m

    def shadow(self, m, dx=4, dy=8, blur=10, amt=0.45, c="#12081e", clip="self"):
        """A soft cast shadow of mask m (offset) darkening what is painted."""
        dx, dy, blur = dx * self.cv.s, dy * self.cv.s, blur * self.cv.s
        pad = int(blur * SS * 3 + max(abs(dx), abs(dy)) * SS) + 4
        box = self._box(m, pad)
        if box is None:
            return
        x0, y0, x1, y1 = box
        a = mcrop(m, box)
        sx, sy = int(dx * SS), int(dy * SS)
        a = np.roll(np.roll(a, sy, 0), sx, 1)
        a = fblur(a, blur * SS)
        if clip == "self":
            a = a * self.a[y0:y1, x0:x1]
        elif clip is not None:
            a = a * mcrop(clip, box)
        R = self.rgb[y0:y1, x0:x1]
        R *= (1 - a * amt)[..., None]
        R += col(c) * (a * amt * self.a[y0:y1, x0:x1])[..., None] * 0.5

    def fade(self, m, soft=12):
        """Multiplies this layer's alpha by mask m (softened) - feathered joints and tips."""
        a = fblur(np.asarray(m, F32) / 255.0, soft * SS) if soft else np.asarray(m, F32) / 255.0
        self.a *= a
        self.rgb *= a[..., None]

    def cut(self, m, soft=0.6):
        a = fblur(np.asarray(m, F32) / 255.0, soft * SS)
        self.a *= 1 - a
        self.rgb *= (1 - a)[..., None]

    def soften(self, s):
        """Blurs the whole layer (things seen through jelly or haze)."""
        b = self._box(self.mask(), int(s * SS * 3) + 4)
        if b is None:
            return
        x0, y0, x1, y1 = b
        self.a[y0:y1, x0:x1] = fblur(self.a[y0:y1, x0:x1], s * SS)
        for i in range(3):
            self.rgb[y0:y1, x0:x1, i] = fblur(self.rgb[y0:y1, x0:x1, i], s * SS)

    def tint(self, c, amt):
        """Mixes every painted pixel toward colour c (keeps alpha)."""
        self.rgb += (col(c)[None, None, :] * self.a[..., None] - self.rgb) * amt

    def mask(self):
        return Image.fromarray((np.clip(self.a, 0, 1) * 255).astype(np.uint8))

    def image(self):
        """Downscaled canvas-size RGBA image."""
        a = np.clip(self.a, 0, 1)
        rgb = np.clip(np.minimum(self.rgb, a[..., None]), 0, 1)
        arr = np.dstack([rgb, a[..., None]])
        im = Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBa")
        im = im.resize((self.cv.W, self.cv.H), Image.LANCZOS).convert("RGBA")
        return im


# ------------------------------------------------------------------ rig assembly

class Rig:
    def __init__(self, rid, size, feet, kind, flat_size, seed=7):
        self.cv = Canvas(size[0], size[1], seed)
        self.rb = rigmod.RigBuilder(rid, size, feet=feet, facing="left", kind=kind)
        self.rid, self.flat_size = rid, flat_size

    def layer(self):
        return Layer(self.cv)

    def add(self, name, L, parent, role, pivot, z, blend="normal"):
        img = L.image() if isinstance(L, Layer) else L
        pivot = self.cv.P(*pivot)
        self.rb.add(name, img, parent, role, pivot, z, blend)

    def save(self):
        self.rb.save(flat=f"sprites/enemies/{self.rid}.png", flat_size=self.flat_size)


# ------------------------------------------------------------------ shared details

def eye(L, cv, cx, cy, rx, ry, iris, rotd=0.0, pupil="slit", glow=1.0, lid=None, look=(-0.25, 0.0),
        core="#fffbe0", sclera=None):
    """A glowing monster eye: dark socket, luminous iris with a bright core, a dark pupil, a wet glint."""
    ic = col(iris)
    sock = cv.ell(cx, cy, rx * 1.18, ry * 1.25, rotd)
    L.fill(sock, mixc("#0a0612", iris, 0.12), soft=1.2)
    ball = cv.ell(cx, cy, rx, ry, rotd)
    if sclera:
        L.paint(ball, sclera, rim=0, spec=0.3, line=0.6, tex=0.02)
    else:
        L.paint(ball, ic * 0.75, dark=ic * 0.25, lite=mixc(ic, core, 0.6), rim=0, spec=0.0, line=0.5, tex=0.03,
                emit=(ic, 0.25 * glow))
    ix, iy = cx + look[0] * rx, cy + look[1] * ry
    L.glow(ix, iy, max(rx, ry) * 0.85, mixc(iris, core, 0.5), 0.9 * glow, clip=ball)
    L.glow(ix, iy, max(rx, ry) * 0.35, core, 0.7 * glow, clip=ball)
    if pupil == "slit":
        pm = cv.ell(ix, iy, rx * 0.16, ry * 0.78, rotd)
    elif pupil == "hslit":
        pm = cv.ell(ix, iy, rx * 0.62, ry * 0.2, rotd)
    elif pupil == "round":
        pm = cv.ell(ix, iy, rx * 0.34, rx * 0.34)
    else:
        pm = None
    if pm is not None:
        L.fill(AND(pm, ball), "#07030a", soft=0.4)
    if lid:
        # heavy upper lid: a band cutting the top of the eye (angle lid degrees)
        lm = cv.poly(rot([(cx - rx * 1.6, cy - ry * 2.2), (cx + rx * 1.6, cy - ry * 2.2),
                          (cx + rx * 1.6, cy - ry * lid[1]), (cx - rx * 1.6, cy - ry * lid[1])], (cx, cy),
                         lid[0] + rotd))
        L.fill(AND(lm, sock), mixc("#0a0612", iris, 0.08), soft=0.8)
    L.fill(cv.ell(cx - rx * 0.35, cy - ry * 0.42, rx * 0.2, ry * 0.14, rotd - 20), "#ffffff", alpha=0.85, soft=0.5)
    return ball


def spore_dots(L, cv, pts, c, core="#f6ffe8", halo=True):
    """Floating glowing spores: a bright core and a soft coloured halo each."""
    for x, y, r in pts:
        if halo:
            L.glow(x, y, r * 4.0, c, 0.55, mode="halo")
        L.fill(cv.ell(x, y, r, r), mixc(c, core, 0.5), soft=r * 0.25)
        L.fill(cv.ell(x - r * 0.15, y - r * 0.15, r * 0.5, r * 0.5), core, soft=r * 0.2)


def glow_spots(L, cv, spots, c, core="#fbfff0", clip=None, amt=1.0, fill=None):
    """Bioluminescent spots on a surface: light spilling onto the surface around each, a raised pale spot
    that glows from within, a near-white core."""
    for x, y, rx, ry, *rr in spots:
        L.glow(x, y, max(rx, ry) * 3.2, c, 0.5 * amt, clip=clip)
    for x, y, rx, ry, *rr in spots:
        rd = rr[0] if rr else 0.0
        m = cv.ell(x, y, rx, ry, rd)
        if clip is not None:
            m = AND(m, clip)
        L.paint(m, fill or mixc(c, "#ffffff", 0.25), dark=mixc(c, "#0a1a2a", 0.45), lite=core, rim=0, spec=0.3,
                line=0.4, tex=0.04, emit=(mixc(c, core, 0.3), 0.45 * amt), size=max(rx, ry) * 0.6)
        L.glow(x - rx * 0.1, y - ry * 0.1, max(rx, ry) * 0.8, core, 0.8 * amt, clip=m)


def fx_glows(rig, name, parent, glows, z, pivot=None):
    """An additive glow part: glows = [(x, y, r, colour, amount)]."""
    L = rig.layer()
    for x, y, r, c, a in glows:
        L.glow(x, y, r, c, a, mode="halo")
    px, py = pivot or (glows[0][0], glows[0][1])
    rig.add(name, L, parent, "fx", (px, py), z, blend="add")


def fibers(L, cv, m, n, direction, length, c, alpha=0.35, width=1.2, seed=1, bend=0.0):
    """Hair-thin strokes along a direction inside mask m (bark, stem fibres, fur)."""
    rng = np.random.default_rng(seed)
    b = m.getbbox()
    if b is None:
        return
    x0, y0, x1, y1 = [v / SS for v in b]
    dx, dy = direction
    arr = np.asarray(m)
    out = cv.blank()
    d = ImageDraw.Draw(out)
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if arr[min(cv.h - 1, int(y * SS)), min(cv.w - 1, int(x * SS))] < 128:
            continue
        ln = length * cv.s * rng.uniform(0.5, 1.2)
        pts = []
        for t in np.linspace(0, 1, 6):
            pts.append(((x + dx * ln * t + bend * ln * t * t * dy) * SS, (y + dy * ln * t - bend * ln * t * t * dx) * SS))
        d.line(pts, fill=int(255 * rng.uniform(0.5, 1.0)), width=max(1, int(width * SS)))
    L.fill(AND(out, m), c, alpha=alpha, soft=0.3)


def jelly_highlights(L, cv, strokes, dots, clip=None):
    """Wet highlights: soft white streaks along the lit side plus a few sharp glints."""
    for pts, w0, w1, a in strokes:
        L.stroke(pts, w0, w1, "#f4fff0", alpha=a, soft=w0 * 0.25, clip=clip)
    for x, y, r, a in dots:
        L.fill(cv.ell(x, y, r, r * 0.8), "#ffffff", alpha=a, soft=r * 0.3, clip=clip)


# ================================================================== cave slime

def cave_slime():
    """A great translucent acid slime heaving itself forward: a curled tip leaning at the player, a skull,
    a thigh bone, coins and a lost adventurer's sword floating in its glowing gut, two sunken yellow eyes
    and a wide maw strung with slime."""
    R = Rig("cave_slime", (1024, 1024), feet=(512, 972), kind="blob", flat_size=512, seed=21)
    cv = R.cv
    gel, deep, lime = "#2c9a46", "#04241a", "#c4ff78"
    body_pts = [(96, 966), (92, 900), (120, 800), (182, 700), (262, 612), (352, 544), (452, 496), (560, 476),
                (662, 490), (762, 544), (852, 632), (912, 744), (938, 860), (940, 966), (760, 978), (520, 980),
                (280, 978)]
    body = cv.poly(body_pts, smooth_n=14)

    def shrink(f, cx=520, cy=760, dx=0, dy=0):
        return cv.poly([(p[0] * f + cx * (1 - f) + dx, p[1] * f + cy * (1 - f) + dy) for p in body_pts], 14)

    # ---- root: acid puddle + the gel volume + bubbles deep inside
    L = R.layer()
    pud = cv.poly([(70, 962), (160, 944), (360, 946), (560, 942), (760, 946), (930, 942), (972, 962),
                   (950, 986), (760, 996), (500, 998), (260, 994), (84, 986)], smooth_n=10)
    L.paint(pud, "#2f9a40", dark="#0a2e1c", lite="#caff90", alpha=0.88, flat=1.2, spec=0.7, shin=30, rim=0.4,
            line=0.6, tex=0.08)
    L.glow(520, 962, 380, "#9aff5a", 0.35, clip=pud)
    L.paint(body, gel, dark=deep, lite=lime, alpha=0.95, spec=0.0, rim=0.2, line=0.8, lw=2.4, tex=0.14,
            var=("#0f7a62", 0.55), wrap=0.35)
    # the gut glows from inside (light scattering in the gel); the far side sinks into shadow
    L.glow(560, 790, 340, "#a6ff4a", 0.6, clip=body)
    L.glow(560, 770, 160, "#f0ffb0", 0.35, clip=body)
    L.glow(820, 560, 260, "#02140e", 0.0, clip=body)
    L.fill(SUB(body, shrink(0.84)), "#03201a", alpha=0.45, soft=30, clip=body)
    L.fill(cv.poly([(560, 460), (960, 700), (960, 980), (700, 980)]), "#04180f", alpha=0.35, soft=60, clip=body)
    # cellular structure in the gel
    cells = cv.noise("cells")
    cm = Image.fromarray((np.clip((cells - 1.0) * 3, 0, 1) * 255).astype(np.uint8))
    L.fill(AND(cm, shrink(0.9)), "#d8ff9a", alpha=0.10, soft=1.5)
    cm = Image.fromarray((np.clip((-cells - 1.3) * 3, 0, 1) * 255).astype(np.uint8))
    L.fill(AND(cm, shrink(0.9)), "#06301c", alpha=0.18, soft=2)
    # bubbles
    rng = np.random.default_rng(3)
    bm = np.asarray(shrink(0.9))
    for _ in range(34):
        x, y = rng.uniform(200, 860), rng.uniform(540, 930)
        if bm[int(y * SS), int(x * SS)] < 200:
            continue
        r = rng.uniform(4, 15)
        ring = SUB(cv.ell(x, y, r, r), cv.ell(x + r * 0.12, y + r * 0.12, r * 0.74, r * 0.74))
        L.fill(ring, "#e6ffc0", alpha=0.32, soft=0.8)
        L.fill(cv.ell(x - r * 0.35, y - r * 0.35, r * 0.26, r * 0.2), "#ffffff", alpha=0.6, soft=0.6)
    R.add("body", L, "", "root", (520, 940), 10)

    def submerge(L, depth=0.35):
        L.fill(body, "#1a7a3c", alpha=depth, clip="self")
        L.glow(560, 790, 300, "#b6ff5a", 0.25, clip=body)

    # ---- things it swallowed (floating inside), a little soft and green through the gel
    L = R.layer()
    sx, sy = 646, 682
    cran = cv.ell(sx + 12, sy - 14, 62, 54, -14)
    face = cv.poly([(sx - 58, sy - 6), (sx - 20, sy - 2), (sx + 22, sy + 16), (sx + 16, sy + 52), (sx - 8, sy + 70),
                    (sx - 44, sy + 70), (sx - 66, sy + 40)], 8)
    skull = U(cran, face)
    L.paint(skull, "#cfc59a", dark="#3c3a24", lite="#fff4d0", rim=0.2, spec=0.15, tex=0.3, grain="mottle",
            var=("#8a9a58", 0.6), line=1.0)
    L.paint(cv.ell(sx + 20, sy + 26, 18, 12, -30), "#bdb48a", dark="#4a4630", rim=0, line=0, tex=0.2)  # cheekbone
    for ex, ey, rx, ry in ((sx - 18, sy + 8, 18, 16), (sx - 58, sy + 6, 9, 15)):
        m = cv.ell(ex, ey, rx, ry, -10)
        L.paint(m, "#1e1c10", dark="#050503", lite="#3a3820", rim=0, line=0.6, tex=0.05, round_=0.4)
        L.glow(ex, ey + 4, rx * 0.8, "#8aff3a", 0.25, clip=m)
    L.paint(cv.poly([(sx - 42, sy + 24), (sx - 32, sy + 24), (sx - 36, sy + 44), (sx - 44, sy + 40)], 4), "#1e1c10",
            rim=0, line=0, tex=0)
    for i in range(6):
        tx = sx - 56 + i * 11
        L.paint(cv.poly([(tx, sy + 60), (tx + 9, sy + 60), (tx + 8, sy + 74 - (i % 2) * 3), (tx + 1, sy + 75)]),
                "#e6ddb4", dark="#5a5436", rim=0, line=0.8, tex=0.1)
    L.stroke([(sx + 10, sy - 64), (sx + 22, sy - 40), (sx + 14, sy - 22), (sx + 30, sy - 4)], 2.2, 1, "#3a3420",
             alpha=0.7, soft=0.4)
    L.fill(cv.ell(sx + 40, sy - 30, 26, 16, -20), "#6a8a30", alpha=0.45, soft=8, clip="self")  # dissolving
    submerge(L, 0.3)
    L.soften(0.7)
    R.add("skull", L, "body", "float", (sx, sy), 14)
    # thigh bone, a rib, coins
    L = R.layer()
    bone = cv.limb([(420, 884), (566, 830)], [12, 12])
    for bx, by in ((420, 884), (566, 830)):
        bone = U(bone, cv.ell(bx - 6, by - 10, 17, 15), cv.ell(bx + 6, by + 10, 17, 15))
    L.paint(bone, "#d4caa0", dark="#46442a", lite="#fff6d6", rim=0.2, tex=0.26, var=("#98a462", 0.5), line=0.9)
    rib = cv.limb([(600, 880), (640, 850), (690, 846), (730, 866)], [9, 8, 7, 5])
    L.paint(rib, "#cfc49a", dark="#46442a", lite="#fff2d0", rim=0.2, tex=0.2, line=0.8)
    for x, y, rr in ((300, 902, -10), (336, 914, 12), (760, 884, -20), (704, 920, 5), (470, 934, 0)):
        c = cv.ell(x, y, 17, 8, rr)
        L.paint(c, "#e2aa2e", dark="#5a3a08", lite="#fff2a8", rim=0.2, spec=1.0, shin=30, line=0.7, tex=0.06,
                flat=0.6)
    submerge(L, 0.3)
    L.soften(0.8)
    R.add("bones", L, "body", "float", (520, 870), 13)
    # the sword: blade inside, hilt sticking out of the top right
    L = R.layer()
    a0, a1 = (700, 830), (842, 470)
    blade = cv.poly([(a0[0] - 6, a0[1] + 30), (a0[0] - 16, a0[1] - 6), (a1[0] - 22, a1[1] + 6),
                     (a1[0] + 18, a1[1] + 20), (a0[0] + 16, a0[1] + 2)], 0)
    L.paint(blade, "#9aa8b0", dark="#2a343c", lite="#f0f8ff", rim=0.5, spec=1.2, shin=40, tex=0.14,
            grain="vstreak", line=1.0, size=10)
    L.stroke([(a0[0] + 2, a0[1] + 10), (a1[0] - 2, a1[1] + 14)], 2.5, 2, "#1c262c", alpha=0.5)
    for x, y, r in ((748, 700, 13), (790, 600, 10), (722, 770, 11), (770, 650, 6)):
        L.fill(cv.ell(x, y, r, r * 0.7, 20), "#8a4418", alpha=0.65, soft=3, clip="self")  # rust
    guard = cv.limb([(804, 452), (882, 488)], [11, 11])
    L.paint(guard, "#a8843a", dark="#3a2408", lite="#ffe8a0", spec=0.9, shin=25, rim=0.6, line=1.0, tex=0.12)
    grip = cv.limb([(850, 460), (880, 386)], [11, 10])
    L.paint(grip, "#5a3420", dark="#1a0a04", lite="#a07048", rim=0.6, tex=0.3, grain="hstreak", line=1.0)
    for t in np.linspace(0.1, 0.9, 5):
        p = lerp_pt((850, 460), (880, 386), t)
        L.stroke([(p[0] - 11, p[1] - 3), (p[0] + 11, p[1] + 5)], 2.2, 2.2, "#1a0c06", alpha=0.6)
    L.paint(cv.ell(884, 376, 15, 15), "#a8843a", dark="#3a2408", lite="#ffe8a0", spec=1.0, shin=25, rim=0.6)
    L.fill(body, "#1a7a3c", alpha=0.4, clip="self")
    # goo dripping off the cross-guard
    goo = U(cv.limb([(812, 462), (814, 500), (812, 528)], [9, 5, 3]), cv.ell(812, 540, 9, 12))
    L.paint(goo, "#4ad05a", dark=deep, lite="#eaffb0", alpha=0.9, spec=0.9, shin=30, rim=0.8, line=0.7, tex=0.04)
    L.fill(cv.ell(809, 535, 3, 4), "#ffffff", alpha=0.9, soft=0.8)
    R.add("sword", L, "body", "float", (760, 640), 12)

    # ---- the front membrane: tinted, fresnel-dense edge, wet highlights
    L = R.layer()
    L.paint(body, "#4ac85a", dark="#0e5a2c", lite="#e0ffb0", alpha=0.3, spec=0.0, rim=0.0, line=0, tex=0.06)
    L.fill(SUB(body, shrink(0.9)), "#0e5a2c", alpha=0.6, soft=20, clip=body)
    L.fill(SUB(body, shrink(1.0, dx=-16, dy=8)), CAVE_RIM, alpha=0.8, soft=5, clip=body)
    L.fill(SUB(body, shrink(1.0, dx=12, dy=14)), "#eaffc8", alpha=0.5, soft=4, clip=body)
    jelly_highlights(L, cv, [([(166, 770), (216, 672), (298, 592), (382, 540)], 18, 5, 0.6),
                             ([(600, 500), (680, 512), (744, 544)], 10, 3, 0.5),
                             ([(126, 890), (132, 820)], 8, 3, 0.35)],
                     [(214, 690, 10, 0.95), (398, 534, 6, 0.9), (702, 516, 5, 0.8), (884, 704, 5, 0.5)], clip=body)
    L.fill(SUB(body, shrink(0.995)), "#062a18", alpha=0.75, soft=0.8)
    R.add("membrane", L, "body", "extra", (520, 940), 20)

    # ---- the curled tip (sways)
    L = R.layer()
    tip = cv.limb([(560, 600), (562, 470), (540, 360), (486, 270), (420, 232), (378, 250)],
                  [128, 104, 76, 50, 28, 12], n=16)
    L.paint(tip, gel, dark=deep, lite=lime, alpha=0.94, spec=0.7, shin=28, rim=1.0, line=0.9, lw=2.4,
            tex=0.12, var=("#0f7a62", 0.5), fres=("#0a4a2a", 0.35), wrap=0.35)
    L.glow(560, 580, 180, "#b6ff5a", 0.45, clip=tip)
    jelly_highlights(L, cv, [([(478, 520), (486, 430), (476, 350), (440, 294)], 14, 4, 0.55)],
                     [(470, 300, 6, 0.9), (505, 470, 5, 0.8)], clip=tip)
    L.fade(cv.poly([(0, 0), (1024, 0), (1024, 524), (0, 524)]), soft=22)
    R.add("tip", L, "body", "hair", (556, 540), 22)
    L = R.layer()
    d = U(cv.limb([(386, 256), (381, 300), (379, 340)], [11, 6, 4]), cv.ell(379, 352, 12, 15))
    L.paint(d, "#44cc58", dark=deep, lite="#eaffb0", alpha=0.9, spec=0.9, shin=30, rim=0.7, line=0.8, tex=0.04)
    L.glow(379, 356, 16, "#c8ff6a", 0.5, clip=d)
    L.fill(cv.ell(374, 346, 3.5, 4.5), "#ffffff", alpha=0.9, soft=0.8)
    R.add("drip_tip", L, "tip", "float", (384, 262), 23)

    # ---- the face: sunken glowing eyes and a gaping, stringy maw
    L = R.layer()
    for x, y, r in ((316, 650, 50), (446, 626, 46)):
        L.fill(cv.ell(x, y + 4, r * 1.3, r * 1.1), "#03200f", alpha=0.6, soft=18)
    eye(L, cv, 316, 652, 34, 27, "#e8ff3a", rotd=8, pupil="slit", glow=1.2, lid=(16, 0.1), look=(-0.3, 0.1))
    eye(L, cv, 446, 628, 31, 25, "#e8ff3a", rotd=-6, pupil="slit", glow=1.2, lid=(-14, 0.1), look=(-0.3, 0.1))
    upper = [(232, 752), (262, 728), (300, 718), (330, 732), (352, 716), (392, 724), (420, 710), (462, 718),
             (500, 728), (544, 752)]
    lower = [(520, 774), (488, 800), (440, 820), (388, 828), (336, 822), (292, 806), (256, 784)]
    mouth = cv.poly(upper + lower, 8)
    L.paint(mouth, "#0a2014", dark="#010805", lite="#1c4a28", rim=0, spec=0, line=1.4, tex=0.12, round_=0.5)
    L.glow(396, 800, 120, "#7aff2a", 0.6, clip=mouth)
    L.glow(400, 806, 46, "#eaffa0", 0.45, clip=mouth)
    # gel stalactites off the upper lip
    for x, y, w, h in ((300, 722, 12, 26), (352, 720, 10, 20), (420, 714, 14, 30), (476, 722, 10, 22)):
        f = cv.poly([(x - w, y - 4), (x + w, y - 4), (x + 2, y + h), (x - 1, y + h)], 4)
        L.paint(f, "#5ad060", dark="#0e4a26", lite="#eaffc0", alpha=0.85, rim=0, spec=0.6, line=0.5, tex=0.05)
    # stretched strings across the maw (thick at the lips, thin in the middle)
    for pts in (([(282, 736), (296, 772), (292, 808)]), ([(372, 722), (380, 770), (362, 824)]),
                ([(446, 718), (436, 764), (452, 812)]), ([(506, 736), (500, 770), (490, 794)])):
        m = cv.limb(pts, [5, 1.6, 5])
        L.fill(m, "#8ae070", alpha=0.85, soft=0.8)
        L.stroke([(p[0] - 1.5, p[1]) for p in pts], 1.4, 1.0, "#f0ffd0", alpha=0.6, soft=0.4)
    L.stroke(upper, 7, 4, "#c8ff90", alpha=0.6, soft=2)
    L.stroke(list(reversed(lower)), 6, 3, "#06301a", alpha=0.7, soft=2)
    # brow furrows in the gel above the eyes (menace)
    L.stroke([(258, 604), (310, 596), (362, 614)], 9, 3, "#062e16", alpha=0.5, soft=4)
    L.stroke([(398, 592), (450, 578), (498, 594)], 9, 3, "#062e16", alpha=0.5, soft=4)
    L.stroke([(262, 598), (312, 590), (358, 606)], 3, 1, "#d8ffa0", alpha=0.35, soft=1.5)
    R.add("face", L, "body", "head", (390, 720), 30)
    fx_glows(R, "eye_glow", "face", [(310, 650, 70, "#d8ff3a", 0.5), (440, 626, 64, "#d8ff3a", 0.5),
                                     (396, 790, 90, "#8aff3a", 0.35)], 31)

    # ---- drips (wobble on their own): drool off the lip, runs down the belly
    L = R.layer()
    d = U(cv.limb([(384, 818), (388, 862), (385, 902)], [10, 4, 3]), cv.ell(385, 916, 11, 14))
    L.paint(d, "#4ad05a", dark=deep, lite="#eaffb0", alpha=0.9, spec=0.9, shin=30, rim=0.8, line=0.7, tex=0.04)
    L.glow(385, 918, 16, "#c8ff6a", 0.5, clip=d)
    L.fill(cv.ell(381, 910, 3.5, 4.5), "#ffffff", alpha=0.9, soft=0.8)
    R.add("drool", L, "face", "float", (384, 820), 32)
    for i, (pts, rr, bulb) in enumerate((([(172, 730), (162, 800), (157, 856)], [10, 20, 19], (157, 868, 23, 25)),
                                         ([(866, 680), (882, 744), (891, 796)], [9, 17, 16], (892, 808, 19, 22)))):
        L = R.layer()
        d = U(cv.limb(pts, rr), cv.ell(*bulb))
        L.paint(d, "#52d25e", dark=deep, lite="#eaffb0", alpha=0.85, spec=0.9, shin=30, rim=0.6, line=0.6,
                tex=0.05)
        L.glow(bulb[0], bulb[1] + 4, bulb[2] * 1.4, "#c8ff6a", 0.4, clip=d)
        L.fill(cv.ell(bulb[0] - bulb[2] * 0.35, bulb[1] - bulb[3] * 0.3, bulb[2] * 0.25, bulb[3] * 0.25),
               "#ffffff", alpha=0.9, soft=1)
        L.fade(cv.poly([(0, pts[0][1] + 10), (1024, pts[0][1] + 10), (1024, 1024), (0, 1024)]), soft=10)
        R.add(f"run_{i + 1}", L, "body", "float", pts[0], 24)
    fx_glows(R, "core_glow", "body", [(560, 780, 300, "#9aff4a", 0.28), (646, 690, 110, "#d8ff8a", 0.2)], 25)
    R.save()
    return R


# ================================================================== shared cloth / fungus helpers

def folds(L, cv, m, lines, dark, lite, w=7, alpha=0.55):
    """Cloth folds inside mask m: each fold is a dark crease with a lit ridge beside it (light from the
    upper left, so the ridge sits to the left)."""
    for pts in lines:
        L.stroke(pts, w, w * 0.3, dark, alpha=alpha, soft=w * 0.45, clip=m)
        L.stroke([(x - w * 0.9, y - w * 0.2) for x, y in pts], w * 0.7, w * 0.2, lite, alpha=alpha * 0.55,
                 soft=w * 0.5, clip=m)


def ragged(pts, amp, step, seed=1, down=True):
    """Resamples an open edge and pushes it into ragged, torn points (for hems and cap rims)."""
    rng = np.random.default_rng(seed)
    path = crspline(pts, 12)
    out = []
    acc = 0.0
    for i in range(len(path) - 1):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        acc += seg
        if acc >= step:
            acc = 0.0
            k = rng.uniform(0.35, 1.0) * amp * (1 if len(out) % 2 == 0 else -0.35)
            out.append((x1, y1 + k if down else y1))
    return [path[0]] + out + [path[-1]]


def gill_fan(L, cv, cx, cy, pts_edge, c, alpha=0.5, w=2.4, clip=None):
    """Radial gill lines from a cap's rim edge toward the stem point (cx, cy)."""
    for x, y in pts_edge:
        L.stroke([(x, y), lerp_pt((x, y), (cx, cy), 0.55), lerp_pt((x, y), (cx, cy), 0.8)], w, w * 0.4, c,
                 alpha=alpha, soft=0.6, clip=clip)


def hand(L, cv, wrist, ang, size, skin, dark, lite, fingers=4, curl=0.5, spread=0.35, knuckle=True, claws=None):
    """A gnarled hand: palm blob plus tapered, jointed fingers fanning from wrist along angle (degrees)."""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    px, py = wrist[0] + ux * size * 0.45, wrist[1] + uy * size * 0.45
    palm = U(cv.ell(px, py, size * 0.52, size * 0.4, ang), cv.limb([wrist, (px, py)], [size * 0.3, size * 0.4]))
    ms = [palm]
    for i in range(fingers):
        fa = a + (i - (fingers - 1) / 2) * spread
        bx, by = px + math.cos(fa) * size * 0.4, py + math.sin(fa) * size * 0.4
        l1 = size * (0.55 if i not in (0, fingers - 1) else 0.45)
        mx, my = bx + math.cos(fa) * l1, by + math.sin(fa) * l1
        fb = fa + curl
        tx, ty = mx + math.cos(fb) * l1 * 0.8, my + math.sin(fb) * l1 * 0.8
        ms.append(cv.limb([(bx, by), (mx, my), (tx, ty)], [size * 0.12, size * 0.1, size * 0.055]))
        if claws:
            ex, ey = tx + math.cos(fb + curl * 0.5) * size * 0.2, ty + math.sin(fb + curl * 0.5) * size * 0.2
            ms.append(cv.limb([(tx, ty), (ex, ey)], [size * 0.05, size * 0.012]))
    m = U(*ms)
    L.paint(m, skin, dark=dark, lite=lite, rim=0.6, spec=0.1, tex=0.18, line=1.0, lw=1.6)
    return m


def fist(L, cv, cx, cy, rx, ry, rotd, skin, dark, lite, fingers=4, grip_dir=90):
    """A hand closed around a shaft: an oval fist with finger creases across it and a thumb on top."""
    m = cv.ell(cx, cy, rx, ry, rotd)
    L.paint(m, skin, dark=dark, lite=lite, rim=0.7, spec=0.1, tex=0.2, line=1.0, lw=1.6)
    a = math.radians(rotd)
    ux, uy = math.cos(a), math.sin(a)
    for i in range(1, fingers):
        t = -1 + 2 * i / fingers
        x, y = cx + ux * rx * t, cy + uy * rx * t
        L.stroke([(x - uy * ry * 0.2, y + ux * ry * 0.2), (x - uy * ry * 0.95, y + ux * ry * 0.95)], 3, 1.5,
                 dark, alpha=0.6, soft=0.8, clip=m)
    th = cv.limb([(cx - ux * rx * 0.7 + uy * ry * 0.6, cy - uy * rx * 0.7 - ux * ry * 0.6),
                  (cx + ux * rx * 0.1 + uy * ry * 0.9, cy + uy * rx * 0.1 - ux * ry * 0.9)], [ry * 0.32, ry * 0.26])
    L.paint(th, skin, dark=dark, lite=lite, rim=0.5, tex=0.2, line=1.0, lw=1.4)
    return U(m, th)


# ================================================================== mushroom mage

def mushroom_mage():
    """A hunched fungal hedge-wizard: a tall drooping violet cap freckled with glowing spots, gills that
    light his gaunt, sly face from above, a stringy hyphae beard, a moss-green robe rotting into mycelium
    at the hem, a gnarled root staff with a spore pod in its crook and a cluster of glowing spores held
    out toward the player."""
    R = Rig("mushroom_mage", (1024, 1024), feet=(512, 972), kind="humanoid", flat_size=512, seed=11)
    cv = R.cv
    capc, capd, capl = "#7a3cc0", "#1c0a36", "#c79cff"
    spot = "#6effd0"
    robe, robed, robel = "#3c5a36", "#0c1810", "#90b070"
    skin, skind, skinl = "#d0b690", "#3a2420", "#fff0d0"
    wood, woodd, woodl = "#6a4a30", "#1c0e08", "#b08a60"
    spore = "#9dff5a"

    # ---- staff (offhand, held by the back hand)
    L = R.layer()
    shaft = cv.limb([(790, 958), (798, 820), (786, 650), (802, 470), (794, 320), (804, 230), (826, 180),
                     (822, 138), (794, 120), (768, 132), (764, 158)], [11, 13, 12, 14, 12, 12, 11, 10, 9, 8, 7], n=14)
    stf = U(shaft, cv.ell(794, 730, 19, 13), cv.ell(800, 430, 17, 12), cv.ell(798, 280, 15, 11))
    L.paint(stf, wood, dark=woodd, lite=woodl, rim=0.8, spec=0.1, tex=0.25, grain="vstreak", line=1.0,
            var=("#3a4a2a", 0.4))
    fibers(L, cv, stf, 90, (0.03, -1), 40, "#1a0c06", alpha=0.35, width=1.2, seed=4)
    for y in (730, 430, 280):
        L.stroke([(784, y - 6), (796, y + 2), (808, y - 4)], 3, 2, "#140804", alpha=0.6, soft=0.8)
    L.paint(cv.ell(802, 560, 18, 7, -8), "#6a8a3a", dark="#1a2a10", lite="#c8e088", rim=0.3, line=0.6, tex=0.3)
    L.paint(cv.ell(784, 350, 14, 6, 10), "#6a8a3a", dark="#1a2a10", lite="#c8e088", rim=0.3, line=0.6, tex=0.3)
    pod = U(cv.ell(786, 186, 25, 29), cv.limb([(784, 136), (786, 160)], [4, 5]))
    L.paint(pod, "#8ae860", dark="#1a4a1a", lite="#f4ffd8", rim=0.4, spec=0.9, shin=24, tex=0.08, line=0.9,
            emit=("#b8ff7a", 0.4))
    L.glow(782, 190, 30, "#f6ffe0", 0.9, clip=pod)
    for t in np.linspace(-0.8, 0.8, 5):
        L.stroke([(786 + t * 22, 160), (786 + t * 28, 186), (786 + t * 20, 212)], 2, 1, "#2a7a2a", alpha=0.45,
                 clip=pod)
    L.glow(786, 188, 80, spore, 0.55, clip=stf)
    R_staff = L

    # ---- back arm (behind the body) holding the staff
    L = R.layer()
    up = cv.limb([(612, 560), (654, 604), (686, 646)], [44, 40, 36])
    L.paint(up, "#34502e", dark=robed, lite=robel, rim=1.0, tex=0.15, grain="vstreak", line=1.0)
    folds(L, cv, up, [[(628, 580), (664, 630)], [(646, 572), (684, 618)]], robed, robel, w=6)
    back_up = L
    L = R.layer()
    fore = cv.limb([(686, 646), (730, 640), (770, 632)], [34, 30, 24])
    cuff = cv.poly([(716, 606), (786, 600), (796, 664), (758, 704), (712, 684)], 6)
    L.paint(U(fore, cuff), "#34502e", dark=robed, lite=robel, rim=1.0, tex=0.15, grain="vstreak", line=1.0)
    folds(L, cv, cuff, [[(736, 626), (744, 690)], [(766, 622), (772, 676)]], robed, robel, w=5)
    L.fill(cv.ell(780, 636, 20, 24), "#0a140c", alpha=0.6, soft=4, clip=cuff)
    fist(L, cv, 794, 636, 30, 22, 90, skin, skind, skinl)
    back_lo = L

    # ---- legs: shins wrapped in rags, knobbly root feet
    legs = {}
    for side, hip, knee, ankle, toe in (("back", (580, 770), (590, 872), (594, 938), (560, 962)),
                                        ("front", (450, 770), (428, 874), (410, 940), (360, 966))):
        L = R.layer()
        m = cv.limb([hip, knee], [36, 30])
        L.paint(m, robe if side == "front" else "#34502e", dark=robed, lite=robel, rim=0.6, tex=0.15, line=1.0)
        legs[side + "_up"] = L
        L = R.layer()
        shin = cv.limb([knee, ankle], [25, 20])
        L.paint(shin, "#7a6a4c", dark="#1e1610", lite="#d0c098", rim=0.8, tex=0.2, grain="hstreak", line=1.0)
        for t in np.linspace(0.12, 0.8, 5):
            x, y = lerp_pt(knee, ankle, t)
            L.stroke([(x - 26, y - 7), (x + 26, y + 5)], 5, 5, "#3a2c1e", alpha=0.6, soft=1.2, clip=shin)
            L.stroke([(x - 26, y - 12), (x + 26, y)], 3, 3, "#c8b890", alpha=0.35, soft=1.2, clip=shin)
        ax, ay = ankle
        foot = U(cv.ell(ax, ay + 4, 24, 20), cv.limb([(ax, ay + 6), (toe[0] + 10, toe[1] - 6)], [20, 14]))
        for dx, dy, ln in ((0, 0, 30), (6, 8, 26), (18, 10, 16)):
            foot = U(foot, cv.limb([(toe[0] + 14 + dx, toe[1] - 8 + dy * 0.5),
                                    (toe[0] - ln * 0.6 + dx, toe[1] - 2 + dy * 0.6),
                                    (toe[0] - ln + dx, toe[1] + 2 + dy * 0.4)], [10, 6, 2]))
        foot = U(foot, cv.limb([(ax + 18, ay + 12), (ax + 40, ay + 22), (ax + 54, ay + 24)], [7, 3, 1]))
        L.paint(foot, "#7a6448", dark="#1a120c", lite="#d8c098", rim=0.9, tex=0.25, grain="hstreak",
                line=1.0, var=("#4a4a30", 0.4))
        fibers(L, cv, foot, 24, (-1, 0.15), 30, "#2a1c10", alpha=0.4, width=1.2, seed=9)
        legs[side + "_lo"] = L

    # ---- robe skirt (root)
    L = R.layer()
    hem = ragged([(288, 930), (350, 944), (430, 936), (510, 946), (590, 934), (660, 940), (734, 918)], 26, 22,
                 seed=5)
    skirt = cv.poly([(408, 676), (636, 676), (680, 776), (734, 918)] + list(reversed(hem))[1:-1] +
                    [(288, 930), (350, 790)], 0)
    skirt = U(skirt, cv.ell(522, 706, 124, 46))
    L.paint(skirt, robe, dark=robed, lite=robel, rim=1.0, tex=0.15, grain="vstreak", line=1.0,
            var=("#2a4a44", 0.45), wrap=0.35)
    folds(L, cv, skirt, [[(470, 716), (436, 820), (400, 930)], [(522, 716), (514, 830), (504, 936)],
                         [(578, 716), (600, 820), (630, 926)], [(430, 706), (384, 810), (340, 920)],
                         [(624, 706), (668, 810), (700, 910)], [(500, 760), (476, 870)], [(556, 760), (566, 880)]],
          robed, robel, w=14, alpha=0.75)
    L.glow(300, 700, 220, spore, 0.18, clip=skirt)
    trim = cv.limb([(292, 900), (360, 912), (440, 906), (520, 914), (600, 904), (680, 908), (730, 890)], 12)
    L.paint(AND(trim, skirt), "#6a5a2a", dark="#1a1408", lite="#d8c080", rim=0.4, spec=0.3, tex=0.2, line=0.6,
            size=6)
    for i, x in enumerate(range(310, 720, 34)):
        y = 906 + 4 * math.sin(i)
        L.stroke([(x - 8, y), (x, y - 6), (x + 8, y)], 2.4, 2.4, "#bfff7a", alpha=0.7, soft=0.6, clip=trim)
    L.fill(cv.poly([(280, 870), (740, 860), (740, 960), (280, 960)]), "#b8b090", alpha=0.22, soft=24, clip=skirt)
    L.fill(cv.poly([(280, 890), (740, 880), (740, 960), (280, 960)]), "#0a1208", alpha=0.25, soft=12, clip=skirt)
    rng = np.random.default_rng(8)
    for _ in range(70):
        x = rng.uniform(300, 724)
        y = rng.uniform(904, 934)
        L.stroke([(x, y), (x + rng.uniform(-8, 8), y + rng.uniform(14, 34))], 1.6, 0.6, "#f0ecd8", alpha=0.55,
                 soft=0.4)
    for x, y in ((330, 944), (420, 952), (520, 956), (620, 948), (700, 930)):
        L.glow(x, y, 6, "#d8fff0", 0.9, mode="halo")
    for x, y, s in ((336, 922, 1.0), (360, 932, 0.7), (672, 910, 0.9), (700, 916, 0.6)):
        st = cv.limb([(x, y), (x - 2 * s, y - 22 * s)], [5 * s, 4 * s])
        L.paint(st, "#e8e0c8", dark="#4a4030", rim=0, line=0.6, tex=0.1)
        cp = cv.poly(ell_pts(x - 2 * s, y - 24 * s, 16 * s, 12 * s, 0, 180, 360, 24), 0)
        L.paint(cp, "#8a4ad0", dark=capd, lite="#e0c0ff", rim=0.4, spec=0.5, line=0.6, tex=0.05)
        L.glow(x - 2 * s, y - 26 * s, 26 * s, "#c080ff", 0.6, clip=cp)
    R_skirt = L

    # ---- torso: robe body, mossy mantle, belt with pouch and glowing vials
    L = R.layer()
    chest = cv.poly([(438, 540), (530, 520), (616, 534), (656, 590), (656, 680), (642, 744), (408, 748),
                     (396, 670), (400, 590)], 10)
    L.paint(chest, robe, dark=robed, lite=robel, rim=1.0, tex=0.15, grain="vstreak", line=1.0,
            var=("#2a4a44", 0.4))
    folds(L, cv, chest, [[(480, 600), (466, 670), (462, 730)], [(566, 590), (584, 660), (592, 730)],
                         [(520, 620), (522, 730)]], robed, robel, w=9)
    mantle = cv.poly(ragged([(392, 596), (444, 626), (512, 640), (580, 632), (660, 596)], 22, 18, seed=3)
                     + [(648, 536), (570, 506), (490, 504), (414, 526)], 0)
    L.paint(mantle, "#587a36", dark="#121c0a", lite="#c8e080", rim=1.0, tex=0.22, grain="cells", line=1.0,
            var=("#7a8a3a", 0.5))
    for x, y, r in ((430, 560, 26), (480, 590, 30), (540, 596, 28), (600, 580, 26), (640, 560, 20),
                    (470, 530, 22), (560, 530, 24)):
        L.paint(AND(cv.ell(x, y, r, r * 0.8), mantle), "#618438", dark="#121c0a", lite="#d0e890", rim=0.6,
                tex=0.2, grain="cells", line=0.4, size=r * 0.5)
    L.glow(560, 560, 60, "#c8ff8a", 0.15, clip=mantle)
    belt = cv.poly([(402, 716), (650, 712), (652, 742), (404, 748)], 0)
    L.paint(belt, "#4a3020", dark="#140804", lite="#9a7050", rim=0.6, spec=0.3, tex=0.2, grain="hstreak",
            line=1.0)
    buckle = U(cv.ell(500, 730, 18, 20))
    L.paint(buckle, "#8a7a4a", dark="#2a1c08", lite="#fff0b0", spec=1.0, shin=30, rim=0.4, line=1.0, tex=0.1)
    L.fill(cv.ell(500, 730, 8, 10), "#2a1c08", alpha=0.9)
    pouch = cv.poly([(572, 738), (626, 734), (634, 796), (604, 814), (572, 800)], 6)
    L.paint(pouch, "#5a3a24", dark="#1a0c04", lite="#a07a50", rim=0.6, tex=0.2, line=1.0)
    L.stroke([(572, 758), (632, 754)], 3, 3, "#1a0c04", alpha=0.6)
    for x, y, c in ((432, 782, "#9dff5a"), (458, 790, "#c080ff")):
        L.stroke([(x, 746), (x, y - 26)], 2, 2, "#2a1c10", alpha=0.9)
        v = U(cv.ell(x, y, 12, 17), cv.limb([(x, y - 28), (x, y - 14)], [5, 5]))
        L.paint(v, c, dark=mixc(c, "#000000", 0.7), lite="#ffffff", rim=0.3, spec=1.0, shin=30, line=0.8,
                tex=0.04, emit=(c, 0.35))
        L.glow(x, y + 4, 15, "#ffffff", 0.7, clip=v)
        L.paint(cv.ell(x, y - 30, 6, 4), "#6a4a30", rim=0, line=0.5)
    # the head and beard darken the chest below them
    L.shadow(cv.poly([(380, 540), (520, 540), (500, 720), (430, 740)], 6), dx=6, dy=10, blur=14, amt=0.35)
    R_torso = L

    # ---- head: gaunt fungal face under the cap, the cap with gills
    L = R.layer()
    face = cv.poly([(470, 356), (526, 380), (540, 440), (530, 500), (500, 546), (452, 566), (414, 556),
                    (388, 526), (372, 500), (356, 480), (374, 452), (390, 410), (420, 370)], 10)
    neck = cv.limb([(496, 500), (506, 560)], [40, 40])
    L.paint(U(face, neck), skin, dark=skind, lite=skinl, rim=0.8, spec=0.15, tex=0.2, grain="mottle",
            line=1.1, var=("#a0928a", 0.5))
    # ear-like gill frills at the side of the head
    frill = cv.poly([(512, 420), (556, 400), (570, 440), (552, 480), (520, 470)], 6)
    L.paint(frill, "#b8a8a0", dark=skind, lite=skinl, rim=0.9, tex=0.2, line=1.0)
    for i in range(5):
        L.stroke([(520, 430 + i * 8), (560, 414 + i * 12)], 2, 1, skind, alpha=0.4, clip=frill)
    L.fill(cv.ell(486, 492, 34, 28), skind, alpha=0.3, soft=12, clip=face)  # hollow cheek
    for pts in ([(474, 456), (500, 478), (498, 512)], [(410, 530), (440, 540), (474, 530)],
                [(520, 450), (526, 486)], [(430, 548), (460, 552)]):
        L.stroke(pts, 3, 1, skind, alpha=0.45, soft=1.0, clip=face)
    nose = cv.poly([(410, 434), (398, 456), (366, 494), (350, 508), (360, 516), (388, 510), (412, 494),
                    (420, 470)], 6)
    L.paint(nose, skin, dark=skind, lite=skinl, rim=0.3, spec=0.25, tex=0.2, line=1.1)
    L.fill(cv.ell(384, 508, 8, 5), skind, alpha=0.6, soft=2)
    grin = cv.poly([(388, 524), (420, 532), (458, 526), (482, 510), (470, 532), (432, 546), (398, 540)], 6)
    L.paint(grin, "#2a1010", dark="#080204", lite="#5a2020", rim=0, line=0.8, tex=0.05)
    for x in range(402, 466, 9):
        L.fill(cv.poly([(x, 527), (x + 6, 527), (x + 3, 537)]), "#e8e0c8", alpha=0.95)
    L.stroke([(470, 530), (490, 506)], 3, 1, skind, alpha=0.5)
    eye(L, cv, 460, 448, 20, 12, "#9dff5a", rotd=-10, pupil="slit", glow=1.3, lid=(-14, 0.1), look=(-0.35, 0.1))
    eye(L, cv, 404, 442, 12, 9, "#9dff5a", rotd=-6, pupil="slit", glow=1.1, lid=(-8, 0.1), look=(-0.35, 0.1))
    L.stroke([(436, 426), (462, 420), (488, 432)], 6, 2, skind, alpha=0.65, soft=1.4)
    L.stroke([(390, 424), (414, 422)], 5, 2, skind, alpha=0.65, soft=1.4)
    # cap gills underneath
    gm = cv.poly(ell_pts(500, 372, 238, 42, 0, 0, 180, 40) + [(262, 368), (738, 358)], 0)
    L.paint(gm, "#c4a4bc", dark="#3a2040", lite="#ffe8ff", rim=0, line=1.0, tex=0.12, emit=("#e0a0ff", 0.15))
    gill_fan(L, cv, 504, 450, [(274 + i * 18.5, 372 + 30 * math.sin(math.pi * i / 25)) for i in range(26)],
             "#5a3060", alpha=0.6, w=3, clip=gm)
    L.glow(500, 392, 150, "#e8b0ff", 0.4, clip=gm)
    capm = cv.poly([(256, 378), (272, 336), (320, 270), (380, 206), (446, 162), (510, 140), (566, 136),
                    (612, 160), (650, 208), (694, 268), (730, 332), (752, 362), (706, 376), (620, 374),
                    (500, 382), (380, 386), (300, 386)], 10)
    capm = U(capm, cv.limb([(556, 200), (566, 160), (582, 120)], [60, 56, 46]))
    L.paint(capm, capc, dark=capd, lite=capl, rim=1.0, spec=0.4, shin=14, tex=0.14, grain="mottle",
            var=("#b04a8a", 0.4), line=1.2, wrap=0.4)
    L.fill(cv.poly([(250, 330), (760, 320), (760, 400), (250, 400)]), capd, alpha=0.35, soft=18, clip=capm)
    L.stroke([(262, 376), (380, 382), (500, 378), (620, 370), (748, 358)], 5, 3, "#e0b8ff", alpha=0.4, soft=2,
             clip=capm)
    fibers(L, cv, capm, 80, (0.35, 1), 60, "#2a1050", alpha=0.25, width=1.4, seed=6)
    glow_spots(L, cv, [(334, 316, 17, 12, -35), (420, 244, 22, 15, -25), (508, 190, 15, 11, -10),
                       (548, 290, 26, 17), (646, 262, 17, 12, 25), (690, 330, 11, 8, 30), (440, 334, 13, 9),
                       (584, 190, 10, 7), (380, 366, 9, 6), (610, 352, 10, 6), (486, 256, 8, 6),
                       (300, 358, 7, 5), (704, 296, 7, 5)], spot, clip=capm)
    L.fill(cv.poly([(330, 370), (560, 370), (560, 440), (330, 440)]), "#1a0a2a", alpha=0.45, soft=14, clip=face)
    L.glow(450, 396, 80, "#d890ff", 0.3, clip=face)
    L.glow(360, 560, 110, spore, 0.35, clip=face)  # up-light from the spore cluster
    R_head = L

    # ---- cap tip (droops back; sways)
    L = R.layer()
    tip = cv.limb([(560, 176), (578, 120), (620, 84), (676, 80), (716, 108), (734, 156), (730, 206)],
                  [62, 46, 34, 26, 18, 10, 4], n=14)
    L.paint(tip, capc, dark=capd, lite=capl, rim=1.0, spec=0.4, shin=14, tex=0.14, var=("#b04a8a", 0.4),
            line=1.2)
    glow_spots(L, cv, [(596, 110, 12, 9, -20), (666, 92, 10, 7, 10), (718, 150, 7, 5, 60)], spot, clip=tip)
    L.fade(cv.poly([(0, 0), (1024, 0), (1024, 150), (0, 150)]), soft=14)
    R_tip = L

    # ---- the hyphae beard (sways)
    L = R.layer()
    beard = cv.poly([(396, 540), (430, 556), (480, 548), (504, 520), (512, 580), (494, 646), (470, 704),
                     (452, 676), (434, 720), (416, 680), (398, 700), (388, 640), (384, 580)], 10)
    L.paint(beard, "#e0d8c4", dark="#4a4038", lite="#ffffff", rim=0.9, tex=0.2, grain="vstreak", line=0.8)
    rng = np.random.default_rng(12)
    for _ in range(50):
        x0 = rng.uniform(390, 505)
        y0 = rng.uniform(540, 570)
        ln = rng.uniform(80, 170)
        pts = [(x0, y0), (x0 + rng.uniform(-8, 8), y0 + ln * 0.5), (x0 + rng.uniform(-16, 12), y0 + ln)]
        L.stroke(pts, rng.uniform(1.5, 3), 0.6, str(rng.choice(["#ffffff", "#7a7060", "#f4f0e0"])), alpha=0.6,
                 soft=0.5, clip=beard)
    for x, y in ((470, 700), (434, 716), (398, 696), (452, 672)):
        L.glow(x, y, 9, "#c8ffe0", 0.9, mode="halo")
    R_beard = L

    # ---- front arm: sleeve, bell cuff, gnarled hand held out palm up
    L = R.layer()
    up = cv.limb([(452, 580), (404, 620), (360, 656)], [46, 42, 38])
    L.paint(up, robe, dark=robed, lite=robel, rim=1.0, tex=0.15, grain="vstreak", line=1.0, var=("#2a4a44", 0.4))
    folds(L, cv, up, [[(440, 600), (388, 644)], [(458, 614), (404, 664)]], robed, robel, w=6)
    front_up = L
    L = R.layer()
    fore = cv.limb([(360, 656), (320, 648), (282, 632)], [36, 30, 22])
    cuff = cv.poly([(266, 602), (318, 604), (344, 640), (340, 722), (300, 744), (278, 700), (254, 652)], 8)
    L.paint(U(fore, cuff), robe, dark=robed, lite=robel, rim=1.0, tex=0.15, grain="vstreak", line=1.0)
    folds(L, cv, cuff, [[(312, 626), (306, 720)], [(286, 636), (280, 690)]], robed, robel, w=5)
    L.fill(cv.ell(268, 636, 24, 22), "#0a140c", alpha=0.6, soft=4, clip=cuff)
    hm = hand(L, cv, (272, 628), -150, 46, skin, skind, skinl, fingers=4, curl=0.9, spread=0.3)
    L.glow(236, 590, 70, spore, 0.6, clip=hm)
    L.glow(300, 610, 90, spore, 0.25, clip=cuff)
    front_lo = L

    # ---- the spore cluster in his palm (the "weapon")
    L = R.layer()
    L.glow(232, 556, 80, spore, 0.45, mode="halo")
    for x, y, r in ((232, 556, 26), (206, 536, 15), (260, 532, 13), (224, 518, 10), (256, 568, 11),
                    (200, 568, 9), (242, 500, 7)):
        m = cv.ell(x, y, r, r)
        L.paint(m, "#7ae04a", dark="#1a4a10", lite="#f4ffd8", rim=0.3, spec=0.8, shin=20, line=0.7, tex=0.08,
                emit=("#b8ff7a", 0.5))
        L.glow(x - r * 0.2, y - r * 0.2, r * 0.9, "#f8ffe8", 0.8, clip=m)
    spore_dots(L, cv, [(180, 510, 3.5), (272, 486, 3), (160, 556, 3), (292, 536, 2.5), (216, 468, 2.5),
                       (250, 456, 2)], spore)
    R_orb = L

    # ---- assemble
    R.add("robe", R_skirt, "", "root", (522, 720), 12)
    R.add("leg_back_upper", legs["back_up"], "robe", "leg_back_upper", (580, 770), 6)
    R.add("leg_back_lower", legs["back_lo"], "leg_back_upper", "leg_back_lower", (590, 872), 7)
    R.add("leg_front_upper", legs["front_up"], "robe", "leg_front_upper", (450, 770), 8)
    R.add("leg_front_lower", legs["front_lo"], "leg_front_upper", "leg_front_lower", (428, 874), 9)
    R.add("torso", R_torso, "robe", "torso", (522, 720), 14)
    R.add("arm_back_upper", back_up, "torso", "arm_back_upper", (612, 560), 4)
    R.add("arm_back_lower", back_lo, "arm_back_upper", "arm_back_lower", (686, 646), 5)
    R.add("staff", R_staff, "arm_back_lower", "offhand", (788, 636), 3)
    R.add("staff_glow", _fx([(786, 188, 110, spore, 0.55), (786, 188, 40, "#f4ffe0", 0.5)], cv), "staff", "fx",
          (786, 188), 26, blend="add")
    R.add("head", R_head, "torso", "head", (502, 540), 16)
    R.add("cap_tip", R_tip, "head", "hair", (566, 180), 17)
    R.add("beard", R_beard, "head", "hair", (450, 550), 23)
    R.add("arm_front_upper", front_up, "torso", "arm_front_upper", (452, 580), 20)
    R.add("arm_front_lower", front_lo, "arm_front_upper", "arm_front_lower", (360, 656), 21)
    R.add("spores", R_orb, "arm_front_lower", "weapon", (250, 610), 22)
    R.add("spores_glow", _fx([(232, 546, 120, spore, 0.45), (232, 550, 40, "#f8ffe8", 0.5)], cv), "spores", "fx",
          (232, 546), 27, blend="add")
    R.add("cap_glow", _fx([(420, 244, 60, spot, 0.3), (548, 290, 70, spot, 0.3), (334, 316, 50, spot, 0.25),
                           (646, 262, 50, spot, 0.25), (500, 400, 150, "#c080ff", 0.2)], cv), "head", "fx",
          (502, 300), 25, blend="add")
    R.save()
    return R


# ================================================================== toxic toad

def wart_map(L, m, n=160, rmin=4.0, rmax=16.0, height=0.8, seed=1, pad=8):
    """A height map (working pixels, for Layer.paint hmap) of n round warts scattered inside mask m."""
    cv = L.cv
    box = L._box(m, pad)
    x0, y0, x1, y1 = box
    a = mcrop(m, box)
    H = np.zeros_like(a)
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(a > 0.6)
    if not len(xs):
        return H
    idx = rng.choice(len(xs), size=min(n, len(xs)), replace=False)
    for i in idx:
        r = rng.uniform(rmin, rmax) ** 1.0 * SS * cv.s
        if rng.random() < 0.6:
            r *= 0.55
        cx, cy = xs[i], ys[i]
        w = int(r * 2.2) + 1
        ya, yb, xa, xb = max(0, cy - w), min(H.shape[0], cy + w), max(0, cx - w), min(H.shape[1], cx + w)
        yy, xx = np.mgrid[ya:yb, xa:xb].astype(F32)
        d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)
        H[ya:yb, xa:xb] = np.maximum(H[ya:yb, xa:xb], np.exp(-d2 * 1.6) * r * height)
    return H


def paint_warty(L, cv, m, base, dark, lite, n=160, rmin=4, rmax=16, seed=1, **kw):
    kw.setdefault("tex", 0.14)
    return L.paint(m, base, dark=dark, lite=lite, hmap=wart_map(L, m, n, rmin, rmax, seed=seed), **kw)


def toxic_toad():
    """A bloated cave toad the size of a cart: bruise-purple warty hide, green poison glands and warts that
    glow, heavy-lidded amber eyes with bar pupils, a wide slimy mouth and a glowing venom sac swelling under
    its throat; stubby webbed hands planted in front, a great folded hind leg."""
    R = Rig("toxic_toad", (1024, 1024), feet=(540, 966), kind="beast", flat_size=512, seed=31)
    cv = R.cv
    cv.xf = (1.1, 540, 966)
    hide, hided, hidel = "#6a3a90", "#140620", "#c89ae8"
    belly, bellyd, bellyl = "#a0a878", "#22241a", "#eef4c8"
    poison = "#7dff3a"
    amber = "#ffa01a"

    # ---- far legs (behind the body)
    L = R.layer()
    far_foot = U(cv.poly([(830, 930), (900, 922), (962, 942), (984, 958), (950, 968), (900, 966), (840, 962)], 8),
                 cv.limb([(866, 890), (878, 944)], [34, 26]))
    paint_warty(L, cv, far_foot, "#4a285e", hided, "#9a70c0", n=30, rim=1.0, line=1.0, seed=2)
    for x in (944, 970):
        L.fill(cv.ell(x, 962, 8, 5), "#c8ff8a", alpha=0.5, soft=2, clip=far_foot)
    far_hind = L
    L = R.layer()
    arm = cv.limb([(420, 770), (380, 850), (348, 924)], [50, 40, 32])
    webs = [cv.ell(346, 936, 32, 18)]
    for ang, ln in ((192, 52), (168, 58), (144, 50)):
        t = math.radians(ang)
        tip = (346 + math.cos(t) * ln, 948 + math.sin(t) * ln * 0.25)
        webs += [cv.limb([(346, 940), tip], [12, 8]), cv.ell(tip[0], tip[1], 10, 7)]
    far_m = U(arm, *webs)
    paint_warty(L, cv, far_m, "#52306a", hided, "#a07ac8", n=40, rim=0.9, line=1.0, seed=3)
    L.fill(far_m, "#0c0414", alpha=0.25, clip="self")
    far_fore = L

    # ---- body (root): squat pear, hump behind the head
    L = R.layer()
    body = cv.poly([(470, 470), (560, 410), (670, 386), (780, 404), (870, 470), (930, 580), (946, 700),
                    (922, 820), (862, 902), (740, 946), (580, 950), (470, 912), (410, 830), (396, 700),
                    (410, 570)], 12)
    paint_warty(L, cv, body, hide, hided, hidel, n=260, rmin=5, rmax=20, rim=1.1, spec=0.4, shin=16, line=1.2,
                var=("#8a3a6a", 0.45), wrap=0.35, seed=4)
    bm = AND(cv.poly([(396, 690), (490, 720), (580, 820), (640, 950), (470, 930), (400, 840)], 10), body)
    L.paint(bm, belly, dark=bellyd, lite=bellyl, rim=0.2, spec=0.3, tex=0.15, line=0, var=("#b0a060", 0.4),
            hmap=wart_map(L, bm, 40, 3, 8, 0.5, seed=5))
    rng = np.random.default_rng(4)
    for _ in range(16):
        x, y = rng.uniform(540, 920), rng.uniform(430, 800)
        L.fill(AND(cv.ell(x, y, rng.uniform(24, 54), rng.uniform(16, 34), rng.uniform(0, 180)), body), "#240c36",
               alpha=0.4, soft=8)
    glow_spots(L, cv, [(620, 460, 15, 12), (700, 426, 11, 9), (790, 470, 17, 13), (866, 560, 13, 10),
                       (730, 540, 19, 14), (650, 600, 12, 10), (830, 650, 15, 12), (906, 700, 9, 8),
                       (580, 530, 10, 8), (770, 730, 11, 9), (890, 800, 9, 7), (640, 400, 8, 6)], poison,
               clip=body)
    L.stroke([(500, 470), (580, 416), (680, 394)], 12, 3, "#f0e0ff", alpha=0.35, soft=4, clip=body)
    body_L = L

    # ---- near hind leg: huge folded thigh + long webbed foot
    L = R.layer()
    shank = cv.limb([(860, 876), (800, 930), (726, 948)], [48, 38, 30])
    toes = []
    for dy, ln in ((-14, 150), (-2, 176), (8, 160), (14, 116)):
        tip = (730 - ln, 958 + dy)
        toes += [cv.limb([(730, 950), (730 - ln * 0.55, 954 + dy * 0.6), tip], [18, 12, 8]),
                 cv.ell(tip[0], tip[1], 12, 9)]
    web = cv.poly([(724, 934), (580, 942), (566, 962), (620, 972), (724, 968)], 6)
    foot = U(shank, web, *toes)
    paint_warty(L, cv, foot, "#5e3280", hided, "#b08ad8", n=60, rmin=3, rmax=10, rim=1.0, spec=0.3, line=1.1,
                seed=6)
    L.fill(web, "#c080a0", alpha=0.25, clip="self")
    for dy, ln in ((-14, 150), (-2, 176), (8, 160), (14, 116)):
        L.fill(cv.ell(730 - ln, 958 + dy, 7, 5), "#d8ff9a", alpha=0.55, soft=2)
    hind_lo = L
    L = R.layer()
    thigh = cv.poly([(650, 700), (730, 650), (830, 656), (908, 730), (926, 822), (886, 894), (800, 906),
                     (700, 866), (648, 790)], 12)
    paint_warty(L, cv, thigh, hide, hided, hidel, n=90, rmin=5, rmax=18, rim=1.2, spec=0.4, line=1.2,
                var=("#8a3a6a", 0.4), seed=7)
    for a0 in (0, 1, 2):
        L.stroke([(710 + a0 * 52, 690 + a0 * 10), (750 + a0 * 52, 810 + a0 * 10)], 18, 8, "#200a30", alpha=0.35,
                 soft=7, clip=thigh)
    glow_spots(L, cv, [(770, 720, 14, 11), (860, 770, 11, 9), (730, 810, 10, 8)], poison, clip=thigh)
    L.stroke([(670, 720), (750, 672), (840, 680)], 10, 3, "#f0e0ff", alpha=0.3, soft=3, clip=thigh)
    hind_up = L

    # ---- head: broad skull, bulging eyes, glowing parotoid gland, mouth interior behind the jaw
    L = R.layer()
    head = cv.poly([(140, 566), (160, 510), (220, 446), (300, 396), (390, 368), (480, 372), (556, 410),
                    (596, 470), (590, 560), (548, 616), (480, 634), (380, 626), (270, 610), (170, 590)], 12)
    mouth_in = cv.poly([(150, 584), (280, 610), (480, 632), (520, 666), (450, 710), (300, 716), (200, 670)], 8)
    L.paint(mouth_in, "#7a2440", dark="#140208", lite="#d06080", rim=0, spec=0.3, line=0.6, tex=0.1)
    tongue = cv.poly([(220, 640), (330, 630), (430, 646), (450, 684), (360, 700), (250, 684)], 8)
    L.paint(tongue, "#c85070", dark="#3a0a1a", lite="#ffb0c0", rim=0, spec=0.8, shin=24, line=0.6, tex=0.1)
    L.glow(440, 666, 60, poison, 0.3, clip=mouth_in)
    paint_warty(L, cv, head, hide, hided, hidel, n=110, rmin=4, rmax=13, rim=1.0, spec=0.5, shin=18, line=1.2,
                var=("#8a3a6a", 0.35), seed=8)
    L.paint(AND(cv.poly([(140, 566), (230, 560), (380, 600), (500, 626), (480, 634), (270, 610), (170, 590)], 6),
                head), "#8a6a9a", dark=hided, lite="#e0c8f0", rim=0, line=0, tex=0.1)
    L.fill(cv.ell(186, 520, 10, 6, -30), "#12061a", alpha=0.85, soft=1)
    L.stroke([(146, 574), (270, 608), (380, 622), (490, 634), (556, 612)], 8, 4, "#1a0620", alpha=0.85, soft=1.2)
    L.stroke([(152, 566), (272, 598), (380, 612), (480, 622)], 3, 2, "#f0d8ff", alpha=0.5, soft=1)
    # parotoid gland: lumpy, glowing
    gland = cv.limb([(486, 410), (544, 432), (600, 468), (632, 506)], [30, 36, 32, 20])
    L.paint(gland, "#5ac83a", dark="#0e3a10", lite="#eaffc0", rim=0.5, spec=0.7, shin=20, line=1.0, tex=0.15,
            emit=("#8aff4a", 0.35), hmap=wart_map(L, gland, 30, 5, 12, 0.9, seed=9))
    for x, y in ((506, 414), (544, 432), (584, 452), (616, 484), (560, 456)):
        L.glow(x, y, 18, "#f4ffd8", 0.8, clip=gland)
        L.fill(cv.ell(x, y, 4, 3), "#10300c", alpha=0.7, soft=0.6)
    L.glow(570, 460, 100, poison, 0.45, clip=head)
    for cx, cy, rx, ry, er in ((290, 392, 46, 40, 0.8), (414, 370, 68, 58, 1.0)):
        dome = cv.ell(cx, cy, rx, ry)
        paint_warty(L, cv, dome, hide, hided, hidel, n=16, rmin=3, rmax=7, rim=1.0, spec=0.5, line=1.1, seed=10)
        eye(L, cv, cx - rx * 0.12, cy + ry * 0.04, rx * 0.68, ry * 0.6, amber, pupil="hslit", glow=0.9 * er,
            lid=(8, -0.02), look=(-0.2, 0.1), core="#fff4c0")
        L.stroke([(cx - rx * 0.82, cy - ry * 0.1), (cx - rx * 0.1, cy - ry * 0.3), (cx + rx * 0.64, cy - ry * 0.06)],
                 7 * er, 3, "#12061c", alpha=0.75, soft=1.5, clip=dome)
        L.stroke([(cx - rx * 0.7, cy - ry * 0.5), (cx, cy - ry * 0.74)], 5 * er, 2, "#f0e0ff", alpha=0.45, soft=2,
                 clip=dome)
    head_L = L

    # ---- jaw
    L = R.layer()
    jaw = cv.poly([(146, 578), (270, 610), (380, 624), (490, 636), (540, 624), (552, 654), (500, 694),
                   (380, 712), (262, 700), (180, 650)], 10)
    paint_warty(L, cv, jaw, "#7a4a98", hided, "#d8b8f0", n=30, rmin=3, rmax=8, rim=0.7, spec=0.45, line=1.1,
                seed=11)
    L.paint(AND(cv.poly([(160, 630), (300, 660), (520, 670), (500, 712), (240, 712)], 6), jaw), belly,
            dark=bellyd, lite=bellyl, rim=0, line=0, tex=0.1)
    L.stroke([(150, 580), (270, 612), (380, 626), (500, 638)], 4, 2, "#e8d0ff", alpha=0.45, soft=1)
    jaw_L = L

    # ---- the venom sac under the throat
    L = R.layer()
    sac = cv.ell(310, 744, 128, 88, -6)
    L.paint(sac, "#9adf4a", dark="#1e4a14", lite="#f4ffc8", alpha=0.95, rim=0.6, spec=1.0, shin=30, line=1.0,
            tex=0.08, emit=("#b8ff6a", 0.25), fres=("#3a8a1a", 0.4))
    L.glow(312, 756, 120, "#caff6a", 0.6, clip=sac)
    L.glow(300, 760, 50, "#fbffe0", 0.6, clip=sac)
    for pts in ([(212, 740), (300, 728), (392, 740)], [(206, 784), (306, 784), (406, 772)],
                [(246, 694), (316, 684), (396, 694)]):
        L.stroke(pts, 3, 2, "#3a7a1a", alpha=0.45, soft=1.2, clip=sac)
    L.stroke([(222, 704), (264, 678), (318, 670)], 10, 3, "#ffffff", alpha=0.6, soft=2, clip=sac)
    sac_L = L

    # ---- near foreleg: stubby, with a broad webbed hand
    L = R.layer()
    arm = cv.limb([(540, 740), (510, 830), (480, 912)], [64, 50, 38])
    fingers = [cv.ell(478, 934, 40, 24)]
    tips = []
    for ang, ln in ((194, 70), (170, 78), (146, 70), (122, 54)):
        t = math.radians(ang)
        tip = (478 + math.cos(t) * ln, 952 + math.sin(t) * ln * 0.2)
        tips.append(tip)
        fingers += [cv.limb([(478, 940), lerp_pt((478, 944), tip, 0.6), tip], [15, 11, 8]),
                    cv.ell(tip[0], tip[1], 12, 9)]
    fore = U(arm, *fingers)
    paint_warty(L, cv, fore, hide, hided, hidel, n=50, rmin=4, rmax=12, rim=1.1, spec=0.35, line=1.1,
                var=("#8a3a6a", 0.3), seed=12)
    for x, y in tips:
        L.fill(cv.ell(x, y, 8, 5), "#e0ffb0", alpha=0.5, soft=2)
    L.stroke([(520, 760), (496, 850)], 10, 3, "#f0e0ff", alpha=0.3, soft=3, clip=fore)
    fore_near = L

    # ---- venom drips
    drips = []
    for pts, bulb in (([(622, 498), (626, 544), (624, 578)], (624, 590, 11, 14)),
                      ([(170, 640), (166, 690), (164, 730)], (164, 742, 11, 14))):
        L = R.layer()
        d = U(cv.limb(pts, [9, 5, 3]), cv.ell(*bulb))
        L.paint(d, "#8aff4a", dark="#1a5a10", lite="#fbffe0", alpha=0.92, spec=0.9, shin=30, rim=0.4, line=0.7,
                tex=0.03, emit=("#b8ff6a", 0.4))
        L.fill(cv.ell(bulb[0] - 3, bulb[1] - 4, 3, 4), "#ffffff", alpha=0.9, soft=0.6)
        drips.append((L, pts[0]))

    R.add("body", body_L, "", "root", (660, 820), 10)
    R.add("leg_back_far", far_hind, "body", "leg_back", (866, 900), 2)
    R.add("leg_front_far", far_fore, "body", "leg_front", (420, 770), 3)
    R.add("leg_back_upper", hind_up, "body", "leg_back_upper", (720, 740), 14)
    R.add("leg_back_lower", hind_lo, "leg_back_upper", "leg_back_lower", (858, 876), 13)
    R.add("head", head_L, "body", "head", (560, 580), 16)
    R.add("jaw", jaw_L, "head", "jaw", (540, 630), 18)
    R.add("venom_sac", sac_L, "jaw", "extra", (360, 680), 15)
    R.add("leg_front", fore_near, "body", "leg_front", (540, 740), 20)
    R.add("drip_gland", drips[0][0], "head", "float", drips[0][1], 17)
    R.add("drip_lip", drips[1][0], "jaw", "float", drips[1][1], 19)
    R.add("sac_glow", _fx([(310, 750, 180, "#b8ff4a", 0.45), (310, 756, 60, "#f4ffd0", 0.4)], cv), "venom_sac",
          "fx", (310, 750), 21, blend="add")
    R.add("gland_glow", _fx([(566, 450, 120, poison, 0.4), (720, 540, 150, poison, 0.12),
                             (400, 376, 50, amber, 0.2)], cv), "head", "fx", (566, 450), 22, blend="add")
    R.save()
    return R


def _fx(glows, cv):
    L = Layer(cv)
    for x, y, r, c, a in glows:
        L.glow(x, y, r, c, a, mode="halo")
    return L


# ================================================================== glow bat

def tufted(pts, amp, step, seed=1, closed=True, lean=0.0):
    """Resamples a (closed) outline and turns it into fur: every other point is pushed outward by a random
    amount (spiky tufts); lean slides the tips along the edge so the fur seems combed one way."""
    rng = np.random.default_rng(seed)
    path = crspline(pts, 14, closed=closed)
    cx = sum(p[0] for p in path) / len(path)
    cy = sum(p[1] for p in path) / len(path)
    out, acc, k = [], 0.0, 0
    n = len(path)
    for i in range(n - (0 if closed else 1)):
        (x0, y0), (x1, y1) = path[i], path[(i + 1) % n]
        seg = math.hypot(x1 - x0, y1 - y0)
        acc += seg
        if acc < step:
            continue
        acc = 0.0
        tx, ty = (x1 - x0) / (seg + 1e-6), (y1 - y0) / (seg + 1e-6)
        nx, ny = ty, -tx
        if (x1 - cx) * nx + (y1 - cy) * ny < 0:
            nx, ny = -nx, -ny
        if k % 2 == 0:
            a = rng.uniform(0.45, 1.0) * amp
            out.append((x1 + nx * a + tx * a * lean, y1 + ny * a + ty * a * lean))
        else:
            a = rng.uniform(0.1, 0.35) * amp
            out.append((x1 - nx * a, y1 - ny * a))
        k += 1
    return out


def fur_strokes(L, cv, m, n, c, flow, length=26, width=2.0, alpha=0.5, seed=1, clip=True):
    """Short hair strokes starting inside mask m; flow(x, y) -> direction (dx, dy). clip=False lets them
    overhang the edge so the silhouette turns hairy."""
    rng = np.random.default_rng(seed)
    b = m.getbbox()
    if b is None:
        return
    arr = np.asarray(m)
    x0, y0, x1, y1 = [v / SS for v in b]
    out = cv.blank()
    d = ImageDraw.Draw(out)
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if arr[min(cv.h - 1, int(y * SS)), min(cv.w - 1, int(x * SS))] < 128:
            continue
        dx, dy = flow(x, y)
        ln = length * rng.uniform(0.5, 1.2)
        bend = rng.uniform(-0.25, 0.25)
        pts = []
        for t in np.linspace(0, 1, 5):
            px = x + dx * ln * t - dy * ln * bend * t * t
            py = y + dy * ln * t + dx * ln * bend * t * t
            pts.append((px * SS, py * SS))
        d.line(pts, fill=int(255 * rng.uniform(0.5, 1.0)), width=max(1, int(width * SS)))
    L.fill(AND(out, m) if clip else out, c, alpha=alpha, soft=0.4)


def fur_edge(L, cv, m, c, dark, n=500, length=16, seed=1, flow=None):
    """Hairs sticking out over the edge of mask m (only those starting near the edge), combed along flow."""
    a = np.asarray(m, F32) / 255.0
    ring = np.clip(a - np.asarray(cv.blank(), F32), 0, 1)
    inner = fblur(a, 6 * SS)
    ring = Image.fromarray((np.clip((a - inner) * 4, 0, 1) * (a > 0.5) * 255).astype(np.uint8))
    flow = flow or (lambda x, y: (0.2, 1.0))
    fur_strokes(L, cv, ring, n, dark, flow, length, 2.2, 0.75, seed=seed, clip=False)
    fur_strokes(L, cv, ring, n // 2, c, flow, length * 0.8, 1.6, 0.6, seed=seed + 1, clip=False)


def bat_wing(R, S, E, W, tips, root, mem, memd, meml, bone, boned, bonel, vein, seed=1, glow=1.0):
    """A bat wing on its own layer. S shoulder, E elbow, W wrist, tips: finger tips from the leading edge
    back, root: points where the membrane meets the body (from the last finger back toward S).
    Returns (layer, membrane mask, vein mask for an fx glow)."""
    cv = R.cv
    L = R.layer()
    # membrane outline: leading edge along the arm, scalloped trailing edge between finger tips
    out = [S, lerp_pt(S, E, 0.5), E, W, tips[0]]
    seq = list(tips) + [root[0]]
    for a, b in zip(seq[:-1], seq[1:]):
        mid = lerp_pt(a, b, 0.5)
        pull = 0.2 if b is not root[0] else 0.14
        mid = lerp_pt(mid, W, pull)
        q1 = lerp_pt(lerp_pt(a, b, 0.25), W, pull * 0.7)
        q3 = lerp_pt(lerp_pt(a, b, 0.75), W, pull * 0.7)
        out += [q1, mid, q3, b]
    out += list(root[1:])
    memm = cv.poly(out, 0)
    memm = U(memm, cv.poly(crspline(out[4:] + [W], 6, closed=True), 0))
    memm = U(memm, cv.ell(S[0], S[1], 46, 46))
    L.paint(memm, mem, dark=memd, lite=meml, alpha=0.93, rim=0.5, spec=0.35, shin=22, tex=0.2, grain="mottle",
            line=0.9, lw=2.0, round_=0.25, flat=0.4, wrap=0.5, var=("#3a2a6a", 0.4))
    # light shining through the thin membrane near the trailing edge (backlit by the cave glow)
    for a, b in zip(seq[:-1], seq[1:]):
        mid = lerp_pt(lerp_pt(a, b, 0.5), W, 0.26)
        L.glow(mid[0], mid[1], math.hypot(b[0] - a[0], b[1] - a[1]) * 0.42, "#2a8aa0", 0.35 * glow, clip=memm)
    # wrinkles: fine creases running from bones to the trailing edge
    rng = np.random.default_rng(seed)
    for a, b in zip(tips[:-1], tips[1:]):
        for t in np.linspace(0.2, 0.85, 5):
            p0 = lerp_pt(W, a, t)
            p1 = lerp_pt(W, b, t * rng.uniform(0.85, 1.05))
            m = lerp_pt(lerp_pt(p0, p1, 0.5), W, -0.06)
            L.stroke([p0, m, p1], 2.2, 1.2, memd, alpha=0.28, soft=1.0, clip=memm)
    # glowing veins: a net between neighbouring fingers plus branches off the arm
    vm = cv.blank()
    vd = ImageDraw.Draw(vm)
    vlines = []
    for a, b in zip(tips[:-1] + [tips[-1]], tips[1:] + [root[0]]):
        for t in (0.4, 0.74):
            p0 = lerp_pt(W, a, t + rng.uniform(-0.05, 0.05))
            p1 = lerp_pt(W, b, t + rng.uniform(-0.05, 0.05)) if b is not root[0] else lerp_pt(root[0], root[-1], 0.3 + t * 0.4)
            mid = lerp_pt(lerp_pt(p0, p1, 0.5), W, -0.1 - rng.uniform(0, 0.08))
            path = crspline([p0, mid, p1], 8)
            vlines.append(path)
            # twigs off each vein toward the edge
            for u in (0.3, 0.7):
                q = path[int(u * (len(path) - 1))]
                e = lerp_pt(q, lerp_pt(a, b, 0.5), rng.uniform(0.25, 0.45))
                vlines.append([q, lerp_pt(q, e, 0.5), e])
    for t in tips:
        # a main vein running beside each finger bone, forking toward the trailing edge
        nrm = (-(t[1] - W[1]), t[0] - W[0])
        ln = math.hypot(*nrm) + 1e-6
        nrm = (nrm[0] / ln, nrm[1] / ln)
        off = 12
        pts = [(W[0] + nrm[0] * off, W[1] + nrm[1] * off)]
        for u in (0.35, 0.65, 0.9):
            q = lerp_pt(W, t, u)
            pts.append((q[0] + nrm[0] * off * (1 + u) + rng.uniform(-4, 4), q[1] + nrm[1] * off * (1 + u)))
        vlines.append(crspline(pts, 8))
        for u in (0.3, 0.55, 0.8):
            q = lerp_pt(W, t, u)
            q = (q[0] + nrm[0] * off * (1 + u), q[1] + nrm[1] * off * (1 + u))
            e = (q[0] + nrm[0] * 55 * (1.2 - u) + (t[0] - W[0]) * 0.12, q[1] + nrm[1] * 55 * (1.2 - u) + (t[1] - W[1]) * 0.12)
            vlines.append(crspline([q, lerp_pt(q, e, 0.5), e], 6))
    for i in range(3):
        p0 = lerp_pt(S, E, 0.3 + i * 0.25)
        e = lerp_pt(p0, root[min(len(root) - 1, 1 + i)], 0.45)
        vlines.append(crspline([p0, lerp_pt(lerp_pt(p0, e, 0.5), W, -0.08), e], 8))
    for path in vlines:
        L.stroke(path, 7, 3, vein, alpha=0.3 * glow, soft=3, clip=memm, mode="add")
        L.stroke(path, 2.6, 1.0, mixc(vein, "#ffffff", 0.55), alpha=0.95 * glow, soft=0.5, clip=memm, mode="add")
        vd.line([(px * SS, py * SS) for px, py in (cv.P(x, y) for x, y in path)], fill=255, width=int(3 * SS))
    for path in vlines[::3]:
        x, y = path[len(path) // 2]
        L.glow(x, y, 10, "#e8ffff", 0.9 * glow, clip=memm)
    # bones: upper arm, forearm, fingers, knuckles; a hooked thumb at the wrist
    arm = U(cv.limb([S, E], [26, 17]), cv.limb([E, W], [16, 11]), cv.ell(E[0], E[1], 19, 17), cv.ell(W[0], W[1], 15, 13))
    fingers = []
    for t in tips:
        k = lerp_pt(W, t, 0.48)
        fingers.append(U(cv.limb([W, k], [9, 6]), cv.limb([k, t], [6, 2.2]), cv.ell(k[0], k[1], 8, 7)))
    bones = U(arm, *fingers)
    L.paint(bones, bone, dark=boned, lite=bonel, rim=0.8, spec=0.35, shin=18, tex=0.18, line=1.0, lw=1.8)
    for t in tips:
        k = lerp_pt(W, t, 0.48)
        L.glow(k[0], k[1], 9, vein, 0.6 * glow, clip=bones)
    ang = math.atan2(W[1] - E[1], W[0] - E[0])
    th0 = (W[0] + math.cos(ang) * 14, W[1] + math.sin(ang) * 14)
    th1 = (th0[0] + math.cos(ang - 0.9) * 26, th0[1] + math.sin(ang - 0.9) * 26)
    th2 = (th1[0] + math.cos(ang - 2.2) * 12, th1[1] + math.sin(ang - 2.2) * 12)
    claw = cv.limb([th0, th1, th2], [6, 4, 1.2])
    L.paint(claw, "#e6dcc8", dark="#3a2c28", lite="#ffffff", rim=0.4, spec=0.9, shin=30, line=1.0, tex=0.05)
    # fur over the shoulder and along the upper arm
    furm = cv.poly(tufted(ell_pts(S[0] + (E[0] - S[0]) * 0.3, S[1] + (E[1] - S[1]) * 0.3, 52, 28,
                                  math.degrees(math.atan2(E[1] - S[1], E[0] - S[0]))), 5, 7, seed=seed + 3), 0)
    return L, memm, vm, furm


def glow_bat():
    """A big cave bat diving in at the player: a deep indigo fur coat, glassy teal wing membranes laced
    with glowing cyan veins, huge ears lit from inside, burning cyan eyes over a wrinkled leaf nose, a
    snarling fanged mouth, glowing photophores in its chest ruff, hooked feet hanging under it."""
    R = Rig("glow_bat", (1024, 1024), feet=(512, 972), kind="flyer", flat_size=512, seed=41)
    cv = R.cv
    cv.xf = (1.0, 512, 972)
    fur, furd, furl = "#3e3462", "#0c0818", "#8a7ab8"
    ruff, ruffl = "#5e5288", "#c4b8ec"
    mem, memd, meml = "#1e5266", "#06101c", "#6ad0dc"
    bone, boned, bonel = "#4a3e6a", "#100a1c", "#a898d0"
    vein = "#4af4ff"
    skin, skind, skinl = "#8a5a7e", "#200a1a", "#e8b0cc"

    # ---- far wing (behind everything, raised up and forward over the head)
    Lw, memm, vm, furm = bat_wing(R, (470, 430), (392, 330), (330, 228),
                                  [(236, 96), (120, 150), (66, 288), (130, 420)], [(350, 520), (420, 520), (470, 470)],
                                  "#18485c", memd, "#5ab8c8", "#3e3460", boned, "#8a7ab8", vein, seed=3, glow=0.8)
    Lw.paint(furm, fur, dark=furd, lite=furl, rim=0.5, tex=0.25, line=0.8)
    Lw.tint("#0a0c22", 0.22)
    wing_back = Lw
    fxL = R.layer()
    fxL.fill(vm, vein, alpha=0.35, soft=7, clip=memm)
    wing_back_fx = fxL

    # ---- near wing (in front of the body, swept up and back)
    Lw, memm, vm, furm = bat_wing(R, (586, 440), (690, 356), (764, 238),
                                  [(870, 92), (960, 230), (952, 400), (852, 540)], [(700, 610), (640, 600), (600, 540)],
                                  mem, memd, meml, bone, boned, bonel, vein, seed=5)
    Lw.paint(furm, fur, dark=furd, lite=furl, rim=0.9, tex=0.25, line=0.8)
    fur_strokes(Lw, cv, furm, 120, furl, lambda x, y: (0.8, -0.6), length=18, width=1.6, alpha=0.35, seed=7)
    wing_front = Lw
    fxL = R.layer()
    fxL.fill(vm, vein, alpha=0.4, soft=7, clip=memm)
    wing_front_fx = fxL

    # ---- body (root): furry torso, pale chest ruff with photophores
    L = R.layer()
    body = cv.poly(tufted(ell_pts(530, 520, 104, 148, -18), 6, 7, seed=2, lean=0.3), 0)
    L.paint(body, fur, dark=furd, lite=furl, rim=1.0, spec=0.15, tex=0.3, grain="mottle", line=1.0,
            var=("#2a2a5a", 0.4), wrap=0.4)
    fur_strokes(L, cv, body, 380, furd, lambda x, y: (0.25, 1.0), length=28, width=2.0, alpha=0.45, seed=3)
    fur_strokes(L, cv, body, 260, furl, lambda x, y: (0.25, 1.0), length=22, width=1.4, alpha=0.3, seed=4)
    ruffm = AND(cv.poly(tufted([(430, 420), (520, 400), (580, 470), (590, 580), (550, 660), (480, 640),
                                (440, 560)], 7, 8, seed=6), 0), body)
    L.paint(ruffm, ruff, dark=furd, lite=ruffl, rim=0.4, tex=0.3, line=0.5, wrap=0.4)
    fur_strokes(L, cv, ruffm, 260, ruffl, lambda x, y: (0.1, 1.0), length=20, width=1.4, alpha=0.4, seed=8)
    fur_strokes(L, cv, ruffm, 200, furd, lambda x, y: (0.1, 1.0), length=22, width=1.6, alpha=0.35, seed=9)
    glow_spots(L, cv, [(488, 470, 9, 8), (530, 520, 11, 9), (476, 548, 8, 7), (540, 596, 9, 8),
                       (506, 628, 6, 5), (564, 460, 6, 5)], vein, clip=ruffm)
    fur_edge(L, cv, body, furl, furd, n=700, length=18, seed=21)
    L.glow(380, 400, 200, vein, 0.12, clip=body)  # spill from the eyes and the far wing
    L.fill(cv.poly([(560, 380), (700, 500), (660, 700), (520, 700)]), "#06040e", alpha=0.3, soft=40, clip=body)
    body_L = L

    # ---- tail stub with a little tail membrane between the legs
    L = R.layer()
    tm = cv.poly([(560, 600), (640, 610), (680, 700), (650, 760), (600, 740), (560, 680)], 8)
    L.paint(tm, "#1a4a5c", dark=memd, lite="#4aa8b8", alpha=0.9, rim=0.5, spec=0.3, tex=0.2, line=0.9, flat=0.5)
    tail = cv.limb([(590, 620), (640, 690), (660, 762)], [10, 6, 2.5])
    L.paint(tail, bone, dark=boned, lite=bonel, rim=0.6, tex=0.15, line=1.0)
    L.stroke([(600, 650), (640, 700), (650, 740)], 6, 2, vein, alpha=0.3, soft=3, clip=tm, mode="add")
    L.stroke([(600, 650), (640, 700), (650, 740)], 2, 1, "#c8ffff", alpha=0.8, soft=0.5, clip=tm, mode="add")
    tail_L = L

    # ---- hind legs hanging down, hooked toes
    legs = []
    for hip, knee, ankle, sh in (((560, 630), (560, 700), (542, 760), 1.0), ((604, 618), (618, 688), (612, 748), 0.8)):
        L = R.layer()
        thigh = U(cv.limb([hip, knee], [22, 13]), cv.limb([knee, ankle], [12, 9]))
        L.paint(thigh, "#3a2e58", dark=furd, lite=furl, rim=0.8, tex=0.25, line=1.0)
        fur_strokes(L, cv, cv.limb([hip, knee], [22, 13]), 60, furl, lambda x, y: (0.1, 1), 14, 1.4, 0.3, seed=11)
        foot = cv.ell(ankle[0], ankle[1] + 6, 15, 11)
        L.paint(foot, skin, dark=skind, lite=skinl, rim=0.5, tex=0.15, line=1.0)
        for i, dx in enumerate((-10, 1, 12)):
            t0 = (ankle[0] + dx, ankle[1] + 12)
            t1 = (t0[0] - 8, t0[1] + 16)
            t2 = (t1[0] + 2, t1[1] + 12)
            t3 = (t2[0] + 10, t2[1] + 4)
            c = cv.limb([t0, t1, t2, t3], [5, 3.6, 2.4, 0.8])
            L.paint(c, "#b8aa9a", dark="#2a1c20", lite="#fff4e8", rim=0.3, spec=0.8, shin=30, line=1.0, tex=0.05)
        if sh < 1:
            L.tint("#0a0818", 0.25)
        legs.append(L)

    # ---- ears (sway): huge, ribbed, lit from inside
    ears = []
    for base0, tip, base1, inner_c, dim in (((356, 326), (318, 118), (430, 296), (366, 236), 0.8),
                                            ((436, 296), (566, 104), (530, 352), (494, 236), 1.0)):
        L = R.layer()

        def bulge(a, b, k):
            m = lerp_pt(a, b, 0.5)
            dx, dy = b[0] - a[0], b[1] - a[1]
            return (m[0] - dy * k, m[1] + dx * k)
        outer = cv.poly(crspline([base0, bulge(base0, tip, -0.2), lerp_pt(base0, tip, 0.85), tip,
                                  lerp_pt(base1, tip, 0.85), bulge(tip, base1, -0.24), base1,
                                  lerp_pt(base0, base1, 0.5)], 10, closed=True), 0)
        outer = U(outer, cv.ell((base0[0] + base1[0]) / 2, (base0[1] + base1[1]) / 2 + 20, 46, 40))
        L.paint(outer, fur, dark=furd, lite=furl, rim=1.0, spec=0.2, tex=0.25, line=1.0)
        inner = cv.poly(crspline([lerp_pt(base0, base1, 0.2), lerp_pt(bulge(base0, tip, -0.2), inner_c, 0.25),
                                  lerp_pt(tip, inner_c, 0.18), lerp_pt(bulge(tip, base1, -0.24), inner_c, 0.3),
                                  lerp_pt(base0, base1, 0.85), (inner_c[0], inner_c[1] + 70)], 10, closed=True), 0)
        inner = AND(inner, outer)
        L.paint(inner, "#5a3e70", dark=skind, lite="#a888c8", rim=0, spec=0.4, shin=18, tex=0.15, line=0.8)
        L.glow(inner_c[0], inner_c[1] + 30, 90, "#3ad8f0", 0.6 * dim, clip=inner)
        L.glow(inner_c[0], inner_c[1] + 40, 40, "#c8ffff", 0.3 * dim, clip=inner)
        for t in (0.3, 0.48, 0.64, 0.78):
            a = lerp_pt(base0, tip, t)
            b = lerp_pt(base1, tip, t)
            m = lerp_pt(lerp_pt(a, b, 0.5), (inner_c[0], inner_c[1] + 200), 0.08)
            L.stroke([a, m, b], 5, 2, skind, alpha=0.3, soft=2.5, clip=inner)
            L.stroke([(a[0], a[1] - 5), (m[0], m[1] - 5), (b[0], b[1] - 5)], 3, 1, "#c8ffff", alpha=0.15, soft=2,
                     clip=inner)
        fur_edge(L, cv, SUB(outer, cv.ell(inner_c[0], inner_c[1] + 90, 60, 60)), furl, furd, n=160, length=10,
                 seed=30 + int(dim * 10), flow=lambda x, y: (0.4, -1.0))
        if dim < 1:
            L.tint("#0a0c22", 0.15)
        ears.append(L)

    # ---- head: furry skull, muzzle, leaf nose, glowing eyes, mouth interior with upper fangs
    L = R.layer()
    skull = cv.poly(tufted(ell_pts(424, 372, 96, 84, -8), 5, 7, seed=12, lean=0.3), 0)
    neck = cv.ell(486, 430, 70, 60)
    head = U(skull, neck)
    L.paint(head, fur, dark=furd, lite=furl, rim=1.0, spec=0.15, tex=0.3, line=1.0, var=("#2a2a5a", 0.4))
    fur_strokes(L, cv, head, 260, furd, lambda x, y: ((x - 440) / 120 + 0.3, (y - 360) / 120), 18, 1.6, 0.4, seed=13)
    fur_strokes(L, cv, head, 160, furl, lambda x, y: ((x - 440) / 120 + 0.3, (y - 360) / 120), 14, 1.2, 0.3,
                seed=14)
    fur_edge(L, cv, skull, furl, furd, n=500, length=14, seed=22,
             flow=lambda x, y: ((x - 424) / 100 + 0.3, (y - 372) / 100))
    mouth = cv.poly([(300, 404), (330, 396), (372, 404), (420, 414), (444, 430), (420, 452), (370, 462),
                     (322, 452), (300, 430)], 8)
    L.paint(mouth, "#5a1430", dark="#12020a", lite="#b04060", rim=0, spec=0.2, line=1.0, tex=0.1)
    L.paint(cv.ell(376, 452, 32, 11), "#a04060", dark="#3a0a1a", lite="#e88aa0", rim=0, spec=0.7, shin=24,
            line=0.4, tex=0.08)  # tongue
    muzzle = cv.ell(352, 392, 62, 36, -6)
    L.paint(muzzle, "#5a4a72", dark=furd, lite="#b0a0d0", rim=0.5, spec=0.3, tex=0.25, line=0.9)
    fur_strokes(L, cv, muzzle, 80, furd, lambda x, y: (1, -0.2), 12, 1.2, 0.35, seed=15)
    # upper lip and fangs hanging into the mouth
    lip = cv.poly([(296, 400), (330, 410), (380, 414), (430, 420), (440, 432), (380, 428), (330, 424), (300, 416)], 6)
    L.paint(lip, "#5a3654", dark=skind, lite="#b088a8", rim=0, spec=0.5, shin=20, line=0.8, tex=0.1)
    for x, ln, w in ((318, 40, 9), (402, 34, 8)):
        f = cv.poly([(x - w, 414), (x + w, 416), (x + 1, 414 + ln), (x - 2, 414 + ln - 2)], 4)
        L.paint(f, "#ece4d0", dark="#5a4a3a", lite="#ffffff", rim=0, spec=1.0, shin=30, line=0.9, tex=0.05)
    for x in range(334, 396, 10):
        L.paint(cv.poly([(x - 4, 420), (x + 4, 420), (x, 432)]), "#e0d8c4", dark="#5a4a3a", rim=0, line=0.6, tex=0)
    # leaf nose: a spear-shaped fleshy noseleaf and a horseshoe around the nostrils
    leaf = cv.poly([(330, 344), (342, 358), (342, 372), (336, 386), (320, 386), (316, 372), (320, 356)], 8)
    L.paint(leaf, "#4a3458", dark=skind, lite="#a080b0", rim=0.6, spec=0.45, shin=18, tex=0.2, line=1.0)
    L.stroke([(330, 312), (330, 350), (328, 376)], 3, 1.5, skind, alpha=0.6, soft=0.8, clip=leaf)
    for i in range(3):
        L.stroke([(318, 356 + i * 9), (329, 361 + i * 9), (340, 356 + i * 9)], 2, 1, skind, alpha=0.4, clip=leaf)
    shoe = cv.poly([(300, 392), (316, 380), (340, 382), (356, 394), (340, 404), (312, 404)], 6)
    L.paint(shoe, "#4a3050", dark=skind, lite="#a07898", rim=0.3, spec=0.5, shin=20, tex=0.15, line=1.0)
    for x in (318, 338):
        L.fill(cv.ell(x, 394, 5, 3, 25), "#1a0410", alpha=0.9, soft=0.8)
    # snarl creases
    for pts in ([(350, 352), (372, 366), (390, 360)], [(356, 374), (382, 382), (404, 376)]):
        L.stroke(pts, 4, 1.5, furd, alpha=0.6, soft=1)
    # eyes: far (small, near the snout) and near, deep sockets, angry brows
    eye(L, cv, 372, 342, 15, 11, vein, rotd=-6, pupil="slit", glow=1.3, lid=(-24, -0.25), look=(-0.35, 0.15),
        core="#f0ffff")
    eye(L, cv, 438, 336, 21, 15, vein, rotd=8, pupil="slit", glow=1.4, lid=(20, -0.25), look=(-0.35, 0.15),
        core="#f0ffff")
    L.stroke([(350, 326), (372, 328), (392, 342)], 7, 2, furd, alpha=0.8, soft=1.4)
    L.stroke([(410, 340), (436, 322), (470, 318)], 8, 2, furd, alpha=0.8, soft=1.4)
    L.glow(400, 330, 90, vein, 0.25, clip=head)
    L.fill(cv.poly([(470, 300), (580, 360), (560, 500), (460, 480)]), "#06040e", alpha=0.3, soft=30, clip=head)
    head_L = L

    # ---- jaw: lower lip, lower fangs
    L = R.layer()
    jaw = cv.poly([(302, 446), (340, 456), (380, 460), (430, 446), (452, 440), (460, 470), (420, 494), (370, 500),
                   (330, 488), (300, 466)], 8)
    L.paint(jaw, "#4a3e66", dark=furd, lite="#a898c8", rim=0.5, spec=0.2, tex=0.25, line=1.0)
    fur_strokes(L, cv, jaw, 80, furd, lambda x, y: (0.6, 0.8), 12, 1.2, 0.4, seed=16)
    lip = cv.poly([(302, 446), (340, 456), (380, 460), (430, 446), (436, 454), (380, 470), (336, 466), (304, 456)], 6)
    L.paint(lip, "#5a3654", dark=skind, lite="#b088a8", rim=0, spec=0.5, shin=20, line=0.8, tex=0.1)
    for x, ln, w in ((330, 26, 7), (392, 22, 6)):
        f = cv.poly([(x - w, 458), (x + w, 456), (x + 1, 458 - ln), (x - 2, 458 - ln + 2)], 4)
        L.paint(f, "#ece4d0", dark="#5a4a3a", lite="#ffffff", rim=0, spec=1.0, shin=30, line=0.9, tex=0.05)
    jaw_L = L

    # ---- floating motes of glow-dust shed from the wings
    motes = []
    for i, pts in enumerate(([(236, 560, 4.0), (200, 620, 2.6), (268, 640, 2.2)],
                             [(820, 640, 3.6), (880, 700, 2.4), (770, 720, 2.6)],
                             [(130, 480, 3.0), (90, 540, 2.0)])):
        L = R.layer()
        spore_dots(L, cv, pts, vein, core="#f0ffff")
        motes.append((L, pts[0][:2]))

    # ---- assemble
    R.add("body", body_L, "", "root", (530, 520), 10)
    R.add("wing_back", wing_back, "body", "wing_back", (470, 430), 2)
    R.add("wing_back_glow", wing_back_fx, "wing_back", "fx", (470, 430), 3, blend="add")
    R.add("tail", tail_L, "body", "tail", (590, 620), 5)
    R.add("leg_back", legs[1], "body", "leg_back", (604, 618), 6)
    R.add("leg_front", legs[0], "body", "leg_front", (560, 630), 8)
    R.add("head", head_L, "body", "head", (486, 440), 20)
    R.add("ear_back", ears[0], "head", "hair", (395, 300), 4)
    R.add("jaw", jaw_L, "head", "jaw", (440, 446), 21)
    R.add("ear_front", ears[1], "head", "hair", (470, 310), 19)
    R.add("wing_front", wing_front, "body", "wing_front", (586, 440), 16)
    R.add("wing_front_glow", wing_front_fx, "wing_front", "fx", (586, 440), 17, blend="add")
    R.add("eye_glow", _fx([(372, 340, 46, vein, 0.5), (438, 334, 56, vein, 0.55)], cv), "head", "fx", (420, 340), 24,
          blend="add")
    for i, (L, p) in enumerate(motes):
        R.add(f"mote_{i + 1}", L, "body", "float", p, 26 + i)
    R.save()
    return R


# ================================================================== shroom brute

def moss_clump(L, cv, x, y, w, h, seed=1, clip=None, c="#4f8a34", glow=None):
    """A cushion of moss: a lumpy mound with hairy edges and a few glowing sporophyte tips."""
    rng = np.random.default_rng(seed)
    blobs = [cv.ell(x, y, w * 0.36, h * 0.36)]
    for _ in range(int(w / 9) + 4):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.2, 0.42)
        bx, by = x + math.cos(a) * w * rr, y + math.sin(a) * h * rr
        r = rng.uniform(0.12, 0.2) * w
        blobs.append(cv.ell(bx, by, r, r * rng.uniform(0.6, 0.9)))
    m = U(*blobs)
    if clip is not None:
        m = AND(m, clip)
    L.shadow(m, dx=3, dy=6, blur=5, amt=0.35)
    L.paint(m, c, dark="#0c1a08", lite="#b8d878", rim=0.5, spec=0.08, tex=0.45, grain="cells", line=0.5,
            var=("#6a7a30", 0.5), size=h * 0.3, hmap=wart_map(L, m, int(w / 3), 2, 5, 0.9, seed=seed))
    fur_edge(L, cv, m, "#a8c868", "#24401a", n=int(w * 2.5), length=max(5, h * 0.18), seed=seed,
             flow=lambda a, b: ((a - x) / w, -0.6))
    if glow:
        rng = np.random.default_rng(seed)
        for _ in range(max(2, int(w / 25))):
            gx, gy = x + rng.uniform(-w * 0.4, w * 0.4), y - h * rng.uniform(0.2, 0.5)
            L.stroke([(gx, gy + 10), (gx + rng.uniform(-3, 3), gy - 4)], 1.6, 1, "#a0c060", alpha=0.8)
            L.glow(gx, gy - 5, 6, glow, 0.9, mode="halo")
            L.fill(cv.ell(gx, gy - 5, 2.2, 2.2), "#fffff0", alpha=0.95)
    return m


def shelf_fungus(L, cv, x, y, w, seed=1, flip=1, c="#c88a3a"):
    """A bracket fungus jutting from a surface: a few stacked shelves with growth bands and a pale lip."""
    rng = np.random.default_rng(seed)
    for k in range(3):
        ww = w * (1 - k * 0.25)
        yy = y + k * w * 0.22
        xx = x + flip * k * w * 0.06
        pts = [(xx - flip * ww * 0.1, yy - ww * 0.08), (xx + flip * ww * 0.45, yy - ww * 0.18),
               (xx + flip * ww * 0.9, yy - ww * 0.02), (xx + flip * ww * 0.75, yy + ww * 0.12),
               (xx + flip * ww * 0.2, yy + ww * 0.1)]
        m = cv.poly(pts, 8)
        L.paint(m, mixc(c, "#5a3010", k * 0.15), dark="#2a1404", lite="#ffd8a0", rim=0.6, spec=0.3, tex=0.25,
                line=1.0, size=ww * 0.12, flat=0.3)
        for b in (0.35, 0.6, 0.82):
            L.stroke([lerp_pt(pts[0], pts[1], 1 - b * 0.4), lerp_pt(pts[0], pts[2], b),
                      lerp_pt(pts[4], pts[3], b)], 2.2, 1.4, "#5a2c0c", alpha=0.45, soft=0.8, clip=m)
        L.stroke([pts[2], pts[3], pts[4]], 3, 2, "#fff0c8", alpha=0.7, soft=0.8, clip=m)


def shroom_brute():
    """Elite: a hulking amanita giant. A cracked blood-red cap studded with white warts, moss and little
    mushrooms, pulled low over burning amber eyes and a snaggle-toothed scowl; a torn ring hanging round
    its neck like a collar; a fibrous barrel of a stem body with shelf fungus and glowing lichen; arms like
    trunks; a knotted root club studded with rusty nails; amber light leaking from the cracks and gills."""
    R = Rig("shroom_brute", (1024, 1024), feet=(512, 972), kind="humanoid", flat_size=512, seed=51)
    cv = R.cv
    cv.xf = (0.93, 520, 972)
    capc, capd, capl = "#c02a22", "#2a0406", "#ff8a64"
    stem, stemd, steml = "#d8c6a4", "#2e2018", "#fff6e0"
    wood, woodd, woodl = "#6a4a30", "#1a0c06", "#b48a5c"
    amber = "#ffb436"
    lichen = "#d8ff6a"

    # ---- back arm (behind the body), hanging, a huge root-fingered hand
    L = R.layer()
    up = cv.limb([(640, 560), (700, 610), (728, 670)], [66, 58, 52])
    L.paint(up, "#c4b090", dark=stemd, lite=steml, rim=1.0, spec=0.1, tex=0.25, grain="vstreak", line=1.0)
    fibers(L, cv, up, 120, (0.4, 1), 50, "#3a2a1c", alpha=0.35, width=1.4, seed=2)
    moss_clump(L, cv, 662, 552, 90, 40, seed=3, clip=up)
    L.tint("#0a0818", 0.12)
    back_up = L
    L = R.layer()
    fore = cv.limb([(728, 670), (742, 730), (746, 790)], [52, 52, 46])
    L.paint(fore, "#c4b090", dark=stemd, lite=steml, rim=1.0, spec=0.1, tex=0.25, grain="vstreak", line=1.0)
    fibers(L, cv, fore, 100, (0.05, 1), 50, "#3a2a1c", alpha=0.35, width=1.4, seed=4)
    hm = hand(L, cv, (746, 800), 96, 66, "#c4b090", stemd, steml, fingers=4, curl=0.7, spread=0.32, claws=True)
    fibers(L, cv, hm, 40, (0, 1), 26, "#3a2a1c", alpha=0.3, width=1.2, seed=5)
    L.tint("#0a0818", 0.12)
    back_lo = L

    # ---- root legs
    legs = {}
    for side, hip, knee, ankle in (("back", (606, 846), (624, 902), (632, 944)),
                                   ("front", (446, 846), (424, 902), (410, 944))):
        L = R.layer()
        m = cv.limb([hip, knee], [52, 44])
        L.paint(m, stem, dark=stemd, lite=steml, rim=0.8, tex=0.25, grain="vstreak", line=1.0)
        fibers(L, cv, m, 60, (0, 1), 40, "#3a2a1c", alpha=0.35, width=1.4, seed=6)
        if side == "back":
            L.tint("#0a0818", 0.2)
        legs[side + "_up"] = L
        L = R.layer()
        shin = cv.limb([knee, ankle], [42, 40])
        ax, ay = ankle
        roots = [shin, cv.ell(ax, ay + 6, 50, 26)]
        for dx, ln, cr in ((-1, 70, 12), (-0.6, 64, 10), (0.1, 40, 9), (0.7, 54, 10), (1, 40, 8)):
            tip = (ax + dx * ln, 972 + abs(dx) * 4)
            roots.append(cv.limb([(ax + dx * 20, ay + 10), lerp_pt((ax + dx * 20, ay + 10), tip, 0.5), tip],
                                 [cr * 1.4, cr, cr * 0.3]))
        foot = U(*roots)
        L.paint(foot, "#b8a280", dark=stemd, lite=steml, rim=0.8, tex=0.3, grain="vstreak", line=1.0,
                var=("#6a5a3a", 0.5))
        fibers(L, cv, foot, 80, (0, 1), 30, "#3a2a1c", alpha=0.35, width=1.3, seed=7)
        L.fill(cv.poly([(ax - 90, 950), (ax + 90, 950), (ax + 90, 990), (ax - 90, 990)]), "#3a2a18", alpha=0.45,
               soft=10, clip="self")  # soil
        if side == "back":
            L.tint("#0a0818", 0.2)
        legs[side + "_lo"] = L

    # ---- hips: the torn volva cup at the base of the stem
    L = R.layer()
    volva = cv.poly(ragged([(330, 820), (420, 790), (520, 784), (620, 790), (712, 822)], 18, 20, seed=8, down=False)
                    + [(700, 880), (620, 904), (520, 910), (420, 904), (340, 880)], 6)
    L.paint(volva, "#c8b48e", dark=stemd, lite=steml, rim=0.8, spec=0.15, tex=0.3, grain="mottle", line=1.0,
            var=("#8a7a5a", 0.5))
    folds(L, cv, volva, [[(400, 820), (390, 880)], [(470, 812), (468, 896)], [(560, 812), (566, 898)],
                         [(640, 820), (650, 884)]], stemd, steml, w=10, alpha=0.5)
    L.fill(cv.poly([(320, 870), (720, 870), (720, 920), (320, 920)]), "#3a2a18", alpha=0.4, soft=12, clip=volva)
    moss_clump(L, cv, 380, 880, 110, 34, seed=9, clip=volva)
    moss_clump(L, cv, 670, 870, 80, 30, seed=10, clip=volva)
    hips = L

    # ---- torso: the fibrous stem barrel
    L = R.layer()
    tor = cv.poly([(408, 470), (630, 470), (690, 540), (712, 660), (690, 780), (620, 846), (430, 846),
                   (358, 782), (336, 660), (352, 540)], 10)
    L.paint(tor, stem, dark=stemd, lite=steml, rim=1.0, spec=0.12, tex=0.28, grain="vstreak", line=1.1,
            var=("#a89060", 0.45), wrap=0.4)
    fibers(L, cv, tor, 420, (0.02, 1), 70, "#3a2a1c", alpha=0.32, width=1.5, seed=11, bend=0.1)
    fibers(L, cv, tor, 200, (0.02, 1), 50, "#fff8e8", alpha=0.25, width=1.2, seed=12)
    # gnarled chest plates of fibre, split and peeling
    for pts in ([(420, 560), (430, 660), (418, 760)], [(520, 540), (512, 680), (520, 800)],
                [(612, 560), (626, 690), (612, 790)]):
        L.stroke(pts, 8, 3, stemd, alpha=0.5, soft=2.5, clip=tor)
        L.stroke([(x - 6, y) for x, y in pts], 4, 2, steml, alpha=0.35, soft=2, clip=tor)
    L.stroke([(470, 640), (500, 690), (486, 740), (506, 780)], 5, 2, "#1a0c08", alpha=0.75, soft=0.8, clip=tor)
    L.glow(496, 710, 40, amber, 0.35, clip=tor)  # a wound that glows from inside
    shelf_fungus(L, cv, 684, 668, 96, seed=13, flip=1, c="#b07434")
    moss_clump(L, cv, 400, 520, 130, 50, seed=15, clip=tor, glow=lichen)
    moss_clump(L, cv, 640, 800, 100, 40, seed=16, clip=tor)
    glow_spots(L, cv, [(560, 600, 8, 6), (580, 620, 5, 4), (420, 700, 6, 5), (650, 700, 5, 4), (600, 760, 7, 5)],
               lichen, clip=tor, amt=0.8)
    L.shadow(cv.poly([(380, 540), (660, 540), (690, 610), (360, 610)], 6), dx=0, dy=16, blur=18, amt=0.45)
    torso = L

    # ---- the ring (annulus) hanging round the neck like a ragged collar
    L = R.layer()
    hem = ragged([(356, 606), (430, 622), (520, 630), (610, 622), (690, 600)], 16, 16, seed=17)
    ring = cv.poly([(404, 552), (470, 546), (580, 546), (646, 554), (690, 600)] + list(reversed(hem))[1:-1] +
                   [(356, 606)], 6)
    L.paint(ring, "#e8dcc0", dark="#3a2c20", lite="#ffffff", rim=0.9, spec=0.2, tex=0.2, grain="vstreak", line=1.0,
            alpha=0.97, wrap=0.4)
    folds(L, cv, ring, [[(420, 566), (410, 606)], [(476, 562), (472, 618)], [(540, 562), (544, 622)],
                        [(604, 562), (616, 612)], [(650, 566), (662, 598)]], "#3a2c20", "#ffffff", w=7, alpha=0.6)
    moss_clump(L, cv, 630, 570, 56, 22, seed=18, clip=ring)
    ring_L = L

    # ---- head: the face on the upper stem and the great cap
    L = R.layer()
    face = cv.poly([(404, 360), (636, 360), (652, 440), (640, 520), (600, 548), (440, 548), (396, 516), (386, 440)], 10)
    L.paint(face, stem, dark=stemd, lite=steml, rim=0.8, spec=0.12, tex=0.28, grain="vstreak", line=1.0,
            var=("#a89060", 0.4))
    fibers(L, cv, face, 160, (0.0, 1), 40, "#3a2a1c", alpha=0.3, width=1.3, seed=19)
    # brow: a heavy fibrous ridge under the cap
    brow = cv.poly([(392, 404), (450, 396), (520, 404), (590, 398), (640, 410), (630, 438), (560, 432), (500, 446),
                    (440, 436), (396, 432)], 8)
    L.paint(brow, "#c8b490", dark=stemd, lite=steml, rim=0.4, tex=0.3, grain="vstreak", line=1.0)
    # sockets and eyes: deep, burning amber
    for ex, ey, rx, ry, rd in ((440, 452, 18, 12, 12), (530, 456, 24, 15, -10)):
        L.fill(cv.ell(ex, ey, rx * 1.6, ry * 1.6, rd), "#140804", alpha=0.75, soft=6)
        eye(L, cv, ex, ey, rx, ry, amber, rotd=rd, pupil="slit", glow=1.4, lid=(rd, -0.1), look=(-0.35, 0.1),
            core="#fff2c0")
    L.stroke([(410, 436), (442, 446), (470, 458)], 8, 3, "#1a0c06", alpha=0.75, soft=1.5)
    L.stroke([(498, 460), (530, 440), (570, 438)], 9, 3, "#1a0c06", alpha=0.75, soft=1.5)
    # lumpy nose
    nose = cv.poly([(470, 462), (488, 470), (494, 494), (480, 506), (456, 506), (446, 490)], 8)
    L.paint(nose, "#ccb894", dark=stemd, lite=steml, rim=0.3, spec=0.25, tex=0.3, line=1.0)
    L.fill(cv.ell(462, 502, 6, 3), "#1a0c06", alpha=0.7, soft=1)
    # snarling mouth with snaggle teeth
    mouth = cv.poly([(412, 514), (450, 520), (500, 518), (560, 512), (596, 506), (586, 528), (540, 542), (480, 546),
                     (430, 540)], 8)
    L.paint(mouth, "#2a0c0a", dark="#060202", lite="#5a2018", rim=0, spec=0, line=1.0, tex=0.1, round_=0.5)
    L.glow(500, 532, 60, amber, 0.35, clip=mouth)
    for x, y0, y1, w in ((428, 516, 534, 7), (462, 520, 532, 6), (520, 518, 540, 8), (572, 510, 526, 6)):
        f = cv.poly([(x - w, y0 - 3), (x + w, y0 - 2), (x + 2, y1), (x - 2, y1 - 1)], 4)
        L.paint(f, "#e0d4a8", dark="#4a3a20", lite="#fffbe8", rim=0, spec=0.7, shin=24, line=0.9, tex=0.15)
    for x, y0, y1, w in ((444, 544, 518, 7), (492, 546, 504, 9), (556, 538, 520, 6)):  # lower tusks
        f = cv.poly([(x - w, y0 + 2), (x + w, y0 + 2), (x + 2, y1), (x - 2, y1 + 1)], 4)
        L.paint(f, "#e8dcb0", dark="#4a3a20", lite="#fffbe8", rim=0.2, spec=0.8, shin=24, line=0.9, tex=0.15)
    L.stroke([(406, 512), (420, 524)], 4, 2, stemd, alpha=0.6)
    L.stroke([(600, 502), (590, 520)], 4, 2, stemd, alpha=0.6)
    # cap: underside gills glowing amber, then the dome
    under = cv.poly(ell_pts(514, 386, 304, 44, 0, 0, 180, 40) + [(210, 380), (818, 380)], 0)
    L.paint(under, "#e8c8a0", dark="#4a2814", lite="#fff4d8", rim=0, line=1.0, tex=0.15, emit=("#ffb860", 0.15))
    gill_fan(L, cv, 514, 470, [(222 + i * 19.5, 386 + 34 * math.sin(math.pi * i / 30)) for i in range(31)],
             "#6a3818", alpha=0.6, w=3, clip=under)
    L.glow(518, 404, 220, amber, 0.4, clip=under)
    capm = cv.poly([(204, 394), (212, 330), (256, 252), (324, 180), (412, 128), (510, 108), (606, 116), (692, 152),
                    (762, 214), (806, 292), (824, 360), (818, 394), (750, 392), (640, 388), (520, 392),
                    (400, 394), (284, 400)], 10)
    L.paint(capm, capc, dark=capd, lite=capl, rim=1.0, spec=0.55, shin=18, tex=0.16, grain="mottle",
            var=("#e8582a", 0.45), line=1.2, wrap=0.4)
    L.fill(cv.poly([(190, 340), (850, 330), (850, 410), (190, 410)]), capd, alpha=0.4, soft=18, clip=capm)
    L.stroke([(204, 388), (360, 394), (520, 390), (680, 388), (840, 390)], 6, 4, "#ffb090", alpha=0.35, soft=2,
             clip=capm)
    # a deep crack, glowing from inside
    crack = [(560, 112), (548, 160), (572, 196), (552, 240), (566, 286), (548, 318)]
    L.stroke(crack, 9, 3, "#1a0204", alpha=0.95, soft=0.8, clip=capm)
    L.stroke(crack, 3.4, 1.2, "#ffd27a", alpha=0.95, soft=0.6, clip=capm)
    L.glow(560, 220, 60, amber, 0.5, clip=capm)
    L.stroke([(566, 196), (600, 214), (626, 210)], 5, 1.5, "#1a0204", alpha=0.8, soft=0.6, clip=capm)
    # white warts: raised, flaky patches
    rng = np.random.default_rng(20)
    warts = [(270, 300, 30, 20, -30), (360, 220, 38, 24, -24), (470, 160, 30, 18, -8), (640, 170, 34, 20, 14),
             (730, 250, 28, 18, 30), (790, 330, 20, 13, 40), (460, 280, 46, 28, -4), (620, 290, 36, 22, 8),
             (330, 340, 22, 14, -10), (540, 350, 24, 12, 0), (700, 350, 22, 12, 10), (240, 360, 14, 9, -20),
             (400, 360, 16, 9, 0), (590, 228, 14, 9, 0)]
    for x, y, rx, ry, rd in warts:
        pts = [(x + math.cos(a) * rx * rng.uniform(0.75, 1.1), y + math.sin(a) * ry * rng.uniform(0.75, 1.1))
               for a in np.linspace(0, 2 * math.pi, 9, endpoint=False)]
        m = AND(cv.poly(rot(pts, (x, y), rd), 6), capm)
        L.shadow(m, dx=4, dy=6, blur=4, amt=0.4)
        L.paint(m, "#efe6d4", dark="#6a5a50", lite="#ffffff", rim=0.4, spec=0.3, tex=0.4, grain="cells", line=0.8,
                size=min(rx, ry) * 0.5)
    moss_clump(L, cv, 330, 196, 90, 34, seed=21, clip=U(capm, cv.ell(330, 180, 60, 30)), glow=lichen)
    moss_clump(L, cv, 700, 186, 70, 26, seed=22, clip=U(capm, cv.ell(700, 172, 50, 26)))
    L.glow(520, 450, 140, amber, 0.18, clip=face)
    L.fill(cv.poly([(380, 380), (660, 380), (660, 420), (380, 420)]), "#1a0a04", alpha=0.45, soft=14, clip=face)
    neck = cv.limb([(520, 520), (520, 560)], [92, 92])
    L.paint(SUB(neck, face), stem, dark=stemd, lite=steml, rim=0.6, tex=0.25, grain="vstreak", line=0.8)
    head = L

    # ---- little mushrooms sprouting from the cap (sway)
    L = R.layer()
    for x, y, s, ang in ((420, 132, 1.0, -14), (452, 124, 0.7, 6), (760, 230, 0.8, 30)):
        top = (x + math.sin(math.radians(ang)) * 52 * s, y - math.cos(math.radians(ang)) * 52 * s)
        st = cv.limb([(x, y + 14), lerp_pt((x, y), top, 0.5), top], [7 * s, 6 * s, 5 * s])
        L.paint(st, "#f0e4cc", dark="#4a3a2a", lite="#ffffff", rim=0.6, line=0.8, tex=0.15)
        cp = cv.poly(rot(ell_pts(top[0], top[1], 26 * s, 18 * s, 0, 180, 360, 24), top, ang), 0)
        L.paint(cp, "#e8902a", dark="#4a1a04", lite="#ffe0a0", rim=0.7, spec=0.6, shin=20, line=0.8, tex=0.1)
        L.glow(top[0], top[1] + 2, 30 * s, amber, 0.6, clip=cp)
        L.fill(cv.ell(top[0] - 6 * s, top[1] - 8 * s, 4 * s, 3 * s), "#fff8e0", alpha=0.8)
    crown = L

    # ---- front arm: trunk-thick, mossy, fist wrapped round the club
    L = R.layer()
    up = cv.limb([(426, 604), (380, 650), (342, 698)], [62, 58, 54])
    L.paint(up, stem, dark=stemd, lite=steml, rim=1.0, spec=0.12, tex=0.28, grain="vstreak", line=1.1,
            var=("#a89060", 0.4))
    fibers(L, cv, up, 140, (-0.5, 1), 50, "#3a2a1c", alpha=0.35, width=1.4, seed=23)
    moss_clump(L, cv, 410, 594, 90, 40, seed=24, clip=up, glow=lichen)
    front_up = L
    L = R.layer()
    fore = cv.limb([(342, 698), (310, 740), (284, 774)], [54, 58, 52])
    L.paint(fore, stem, dark=stemd, lite=steml, rim=1.0, spec=0.12, tex=0.28, grain="vstreak", line=1.1,
            var=("#a89060", 0.4))
    fibers(L, cv, fore, 100, (-0.4, 1), 40, "#3a2a1c", alpha=0.35, width=1.4, seed=25)
    shelf_fungus(L, cv, 330, 720, 56, seed=26, flip=1, c="#b07434")
    fm = fist(L, cv, 262, 790, 54, 46, 70, "#d4c09c", stemd, steml)
    fibers(L, cv, fm, 40, (0, 1), 26, "#3a2a1c", alpha=0.3, width=1.2, seed=27)
    front_lo = L

    # ---- the root club
    L = R.layer()
    h0, h1 = (300, 892), (176, 480)
    shaft = cv.limb([h0, lerp_pt(h0, h1, 0.35), lerp_pt(h0, h1, 0.7), h1], [20, 22, 28, 36])
    knot = U(cv.ell(160, 440, 70, 84, -20), cv.ell(198, 400, 46, 50), cv.ell(128, 486, 44, 40),
             cv.ell(150, 372, 36, 34), cv.ell(206, 470, 30, 34), cv.ell(110, 420, 34, 40))
    club = U(shaft, knot)
    L.paint(club, wood, dark=woodd, lite=woodl, rim=0.9, spec=0.15, tex=0.3, grain="vstreak", line=1.1,
            var=("#4a4a2a", 0.4), hmap=wart_map(L, club, 50, 8, 22, 0.6, seed=31))
    fibers(L, cv, club, 160, (0.3, -1), 60, "#1a0c06", alpha=0.4, width=1.4, seed=28, bend=0.2)
    for x, y, r in ((140, 450, 14), (190, 410, 10), (230, 640, 8)):
        L.paint(cv.ell(x, y, r, r * 0.8), "#3a2414", dark=woodd, lite="#8a6a4a", rim=0.2, line=0.8, tex=0.2,
                round_=0.4)
    # rootlets trailing from the knot
    for pts in ([(110, 500), (84, 540), (90, 580)], [(196, 470), (226, 520), (222, 556)],
                [(120, 380), (90, 350), (80, 316)]):
        rm = cv.limb(pts, [7, 4, 1.5])
        L.paint(rm, "#5a3c26", dark=woodd, lite=woodl, rim=0.6, tex=0.2, line=0.9)
    # rusty nails driven through the knot
    for (x, y), ang in (((112, 420), 200), ((150, 362), 250), ((214, 380), 300), ((96, 470), 170),
                        ((196, 452), 330), ((140, 520), 140), ((176, 330), 270)):
        a = math.radians(ang)
        tip = (x + math.cos(a) * 42, y + math.sin(a) * 42)
        nail = cv.limb([(x, y), tip], [5.5, 2])
        L.paint(nail, "#7a7a80", dark="#1a1a20", lite="#e8f0ff", rim=0.5, spec=1.2, shin=40, line=1.0, tex=0.1)
        L.fill(cv.ell(x, y, 9, 9), "#3a3438", alpha=0.95, soft=0.5)
        L.fill(cv.ell(x - 2, y - 2, 4, 4), "#a8a8b0", alpha=0.8, soft=0.5)
        L.fill(cv.ell(x + math.cos(a) * 14, y + math.sin(a) * 14, 7, 5, ang), "#8a3a10", alpha=0.5, soft=3,
               clip=nail)
    moss_clump(L, cv, 170, 360, 80, 30, seed=29, clip=U(knot, cv.ell(170, 344, 50, 24)))
    L.glow(160, 440, 140, amber, 0.12, clip=club)
    club_L = L

    # ---- floating spores
    sp = []
    for i, pts in enumerate(([(250, 140, 4), (296, 104, 3), (210, 196, 2.5)],
                             [(842, 210, 4), (880, 280, 3), (820, 150, 2.6)],
                             [(110, 260, 3.4), (70, 330, 2.4)])):
        L = R.layer()
        spore_dots(L, cv, pts, amber, core="#fff6d8")
        sp.append((L, pts[0][:2]))

    # ---- assemble
    R.add("hips", hips, "", "root", (520, 846), 8)
    R.add("leg_back_upper", legs["back_up"], "hips", "leg_back_upper", (606, 846), 5)
    R.add("leg_back_lower", legs["back_lo"], "leg_back_upper", "leg_back_lower", (624, 902), 6)
    R.add("leg_front_upper", legs["front_up"], "hips", "leg_front_upper", (446, 846), 9)
    R.add("leg_front_lower", legs["front_lo"], "leg_front_upper", "leg_front_lower", (424, 902), 10)
    R.add("torso", torso, "hips", "torso", (520, 820), 12)
    R.add("arm_back_upper", back_up, "torso", "arm_back_upper", (640, 560), 3)
    R.add("arm_back_lower", back_lo, "arm_back_upper", "arm_back_lower", (728, 670), 4)
    R.add("head", head, "torso", "head", (520, 540), 16)
    R.add("cap_sprouts", crown, "head", "hair", (520, 160), 17)
    R.add("ring", ring_L, "torso", "extra", (520, 560), 18)
    R.add("arm_front_upper", front_up, "torso", "arm_front_upper", (426, 604), 20)
    R.add("arm_front_lower", front_lo, "arm_front_upper", "arm_front_lower", (342, 698), 22)
    R.add("club", club_L, "arm_front_lower", "weapon", (262, 790), 21)
    R.add("glow", _fx([(486, 452, 50, amber, 0.4), (530, 456, 60, amber, 0.45), (518, 420, 200, amber, 0.14),
                       (560, 220, 70, amber, 0.25)], cv), "head", "fx", (520, 420), 26, blend="add")
    R.add("lichen_glow", _fx([(400, 500, 70, lichen, 0.2), (580, 620, 50, lichen, 0.18)], cv), "torso", "fx",
          (500, 560), 25, blend="add")
    for i, (L, p) in enumerate(sp):
        R.add(f"spore_{i + 1}", L, "head", "float", p, 28 + i)
    R.save()
    return R


# ================================================================== spore mother (boss)

def vine(L, cv, pts, radii, c="#3f8a4a", d="#0a1e10", l="#b8f08a", seed=1, thorns=6, leaves=3, twist=True):
    """A living vine limb: a twisted green tube with spiral grooves, thorns and a few leaves."""
    m = cv.limb(pts, radii)
    L.paint(m, c, dark=d, lite=l, rim=0.9, spec=0.35, shin=18, tex=0.2, grain="vstreak", line=1.0,
            var=("#5a7a2a", 0.4))
    path = crspline(pts, 12)
    rng = np.random.default_rng(seed)
    if twist:
        # a second strand wrapping round the main one
        k = len(path)
        strand = []
        for i, (x, y) in enumerate(path):
            j = min(k - 2, i)
            dx, dy = path[j + 1][0] - path[j][0], path[j + 1][1] - path[j][1]
            ln = math.hypot(dx, dy) + 1e-6
            u = i / max(1, k - 1)
            r = (radii[0] + (radii[-1] - radii[0]) * u) * 0.7
            s = math.sin(u * 7 * math.pi)
            strand.append((x - dy / ln * r * s, y + dx / ln * r * s))
        for i in range(0, len(strand) - 3, 3):
            seg = strand[i:i + 4]
            L.stroke(seg, 6, 5, d, alpha=0.45, soft=1.2, clip=m)
            L.stroke([(x - 2, y - 2) for x, y in seg], 3, 2, l, alpha=0.35, soft=1, clip=m)
    for _ in range(thorns):
        i = int(rng.uniform(0.1, 0.9) * (len(path) - 2))
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) + 1e-6
        side = 1 if rng.random() < 0.5 else -1
        u = i / max(1, len(path) - 1)
        r = radii[0] + (radii[-1] - radii[0]) * u
        bx, by = x0 - dy / ln * r * side * 0.9, y0 + dx / ln * r * side * 0.9
        tx, ty = bx - dy / ln * 18 * side + dx / ln * 10, by + dx / ln * 18 * side + dy / ln * 10
        L.paint(cv.limb([(bx, by), (tx, ty)], [4.5, 0.8]), "#c8d0a0", dark="#2a3018", lite="#ffffff", rim=0.2,
                spec=0.8, shin=30, line=0.8, tex=0.05)
    for _ in range(leaves):
        i = int(rng.uniform(0.2, 0.85) * (len(path) - 2))
        x, y = path[i]
        ang = rng.uniform(0, 360)
        a = math.radians(ang)
        tip = (x + math.cos(a) * 46, y + math.sin(a) * 46)
        mid = lerp_pt((x, y), tip, 0.5)
        pts2 = [(x, y), (mid[0] - math.sin(a) * 15, mid[1] + math.cos(a) * 15), tip,
                (mid[0] + math.sin(a) * 15, mid[1] - math.cos(a) * 15)]
        lm = cv.poly(pts2, 6)
        L.paint(lm, "#4a9a4a", dark="#0a2a10", lite="#d8ffa0", rim=0.6, spec=0.4, shin=20, tex=0.15, line=0.9,
                size=8)
        L.stroke([(x, y), tip], 1.8, 0.8, "#1a4a1a", alpha=0.6, clip=lm)
    return m


def spore_cloud(L, cv, cx, cy, w, h, c, seed=1, alpha=0.5, dots=14):
    """A drifting cloud of glowing spores: overlapping soft puffs with a brighter heart and specks."""
    rng = np.random.default_rng(seed)
    puffs = []
    for _ in range(9):
        px, py = cx + rng.uniform(-0.38, 0.38) * w, cy + rng.uniform(-0.3, 0.3) * h
        r = rng.uniform(0.18, 0.3) * w
        puffs.append(cv.ell(px, py, r, r * rng.uniform(0.6, 0.9)))
    m = U(*puffs)
    L.fill(m, mixc(c, "#1a3a2a", 0.5), alpha=alpha * 0.4, soft=w * 0.1)
    L.fill(m, c, alpha=alpha * 0.3, soft=w * 0.16)
    L.glow(cx, cy, w * 0.35, mixc(c, "#ffffff", 0.3), alpha * 0.7, mode="halo")
    # brighter, denser cores in a few puffs
    for _ in range(4):
        px, py = cx + rng.uniform(-0.3, 0.3) * w, cy + rng.uniform(-0.25, 0.2) * h
        L.glow(px, py, rng.uniform(0.1, 0.18) * w, mixc(c, "#ffffff", 0.35), alpha * 0.35, mode="halo")
    pts = [(cx + rng.uniform(-0.55, 0.55) * w, cy + rng.uniform(-0.5, 0.5) * h, rng.uniform(1.6, 4.2))
           for _ in range(dots)]
    spore_dots(L, cv, pts, c, core="#f8ffe8")


def spore_mother():
    """Boss: the Spore Mother, a towering mushroom queen. A great violet bell cap ringed with glowing spots,
    crowned with little luminous toadstools and hung with a veil of glowing threads; a pale, beautiful,
    eerie face with half-lidded green eyes and a knowing smile; a high gill ruff; the dragon-bone relic
    burning amber in her breast with light cracking out through her bodice; living vine arms, one open hand
    pouring spores, the other raising a thorned tendril sceptre; a gown of glowing gill-ruffles whose hem
    melts into mycelium; spore clouds drifting round her."""
    R = Rig("spore_mother", (1536, 1536), feet=(768, 1458), kind="humanoid", flat_size=768, seed=61)
    cv = R.cv
    cv.xf = (1.38, -161.6, -306.8)  # authored in 1024 design units; design (512, 972) -> feet (768, 1458)
    capc, capd, capl = "#7a34c4", "#16062c", "#d6a8ff"
    gown, gownd, gownl = "#57268a", "#10041c", "#c49af0"
    glowc = "#d890ff"
    skin, skind, skinl = "#e6dcea", "#3a2444", "#ffffff"
    spore = "#b8ff7a"
    amber = "#ffb040"
    vinec, vined, vinel = "#3f8a4a", "#0a1e10", "#b8f08a"

    # ---- gown (root): three tiers of ruffled gill-flounces, glowing hems, mycelium at the foot
    L = R.layer()
    rng = np.random.default_rng(4)
    tiers = [((300, 960), (740, 960), 700, 52), ((330, 820), (700, 820), 600, 40), ((370, 690), (650, 690), 480, 30)]
    skirt = cv.poly([(452, 560), (572, 560), (640, 700), (720, 840), (790, 960), (240, 960), (300, 840), (380, 700)],
                    8)
    L.paint(skirt, gown, dark=gownd, lite=gownl, rim=1.0, spec=0.2, tex=0.18, grain="vstreak", line=1.0,
            var=("#7a2a7a", 0.4), wrap=0.4)
    hems = []
    for k, (a, b, wy, amp) in enumerate(tiers):
        x0, x1 = a[0] - 40 + k * 6, b[0] + 40 - k * 6
        y = a[1]
        hem_pts = [(x0 + (x1 - x0) * i / 16, y + 8 * math.sin(i * 1.3 + k) + (rng.uniform(8, 20) if i % 2 else 0)
                    - 18 * math.sin(math.pi * i / 16) * (k == 0)) for i in range(17)]
        top = y - (130 if k else 150)
        tier = cv.poly([(x0 + 60 + k * 10, top), (x1 - 60 - k * 10, top)] + list(reversed(hem_pts)), 6)
        tier = U(tier, cv.poly(crspline(hem_pts + [(x0 + 40, y - 20)], 6), 0))
        L.shadow(tier, dx=0, dy=16, blur=16, amt=0.5)
        L.paint(tier, mixc(gown, "#7a3aa8", 0.15 * k), dark=gownd, lite=gownl, rim=1.0, spec=0.25, shin=16,
                tex=0.16, grain="vstreak", line=1.0, var=("#7a2a7a", 0.4), wrap=0.4)
        # gill pleats fanning down each tier
        n = 22 - k * 4
        for i in range(n + 1):
            u = i / n
            p0 = (x0 + 60 + k * 10 + (x1 - x0 - 120 - k * 20) * u, top + 6)
            p1 = hem_pts[min(16, int(round(u * 16)))]
            L.stroke([p0, lerp_pt(p0, p1, 0.6), p1], 4, 2, gownd, alpha=0.55, soft=1.2, clip=tier)
            L.stroke([(p0[0] - 5, p0[1]), (lerp_pt(p0, p1, 0.6)[0] - 5, lerp_pt(p0, p1, 0.6)[1]),
                      (p1[0] - 5, p1[1] - 4)], 2, 1, gownl, alpha=0.3, soft=1, clip=tier)
        # glowing hem
        L.stroke(hem_pts, 7, 7, glowc, alpha=0.75, soft=2.5, clip=tier)
        L.stroke([(x, yy - 3) for x, yy in hem_pts], 2.4, 2.4, "#fbeaff", alpha=0.9, soft=0.8, clip=tier)
        L.glow((x0 + x1) / 2, y - 20, (x1 - x0) * 0.45, glowc, 0.18, clip=tier)
        L.fill(cv.poly([(x1 - 160, top), (x1 + 40, top), (x1 + 40, y + 40), (x1 - 100, y + 40)]), gownd, alpha=0.35,
               soft=40, clip=tier)
        hems.append(hem_pts)
    # glowing spore-dots embroidered on the flounces
    rng = np.random.default_rng(5)
    dots = []
    for k, hp in enumerate(hems):
        for i in range(1, 16):
            if rng.random() < 0.55:
                continue
            x, y = hp[i]
            r = rng.uniform(2.5, 6.5)
            dots.append((x + rng.uniform(-14, 14), y - rng.uniform(18, 110), r, r * 0.8))
    glow_spots(L, cv, [d + (0,) for d in dots], "#7affd8", clip=L.mask(), amt=0.7)
    # mycelium hem: pale threads spreading over the ground, tiny glowing toadstools
    for i in range(70):
        x = rng.uniform(250, 790)
        y = 958 + rng.uniform(-4, 8)
        ex = x + rng.uniform(-70, 70)
        L.stroke([(x, y), ((x + ex) / 2, y + rng.uniform(4, 10)), (ex, y + rng.uniform(8, 16))], 2.0, 0.6,
                 "#ece4f4", alpha=0.6, soft=0.4)
    for x, s in ((262, 1.0), (300, 0.7), (738, 0.9), (774, 0.6), (520, 0.5)):
        y = 966
        st = cv.limb([(x, y), (x - 2 * s, y - 26 * s)], [5 * s, 4 * s])
        L.paint(st, "#f0e8f0", dark="#4a3a4a", rim=0, line=0.6, tex=0.1)
        cp = cv.poly(ell_pts(x - 2 * s, y - 28 * s, 17 * s, 12 * s, 0, 180, 360, 24), 0)
        L.paint(cp, "#9a5ae0", dark=capd, lite="#f0d8ff", rim=0.4, spec=0.5, line=0.6, tex=0.05)
        L.glow(x - 2 * s, y - 30 * s, 26 * s, glowc, 0.7, clip=cp)
    L.glow(512, 960, 300, glowc, 0.08, clip=skirt)
    R.add("gown", L, "", "root", (512, 940), 10)
    del L

    # ---- train behind (cape): a long trailing back panel
    L = R.layer()
    train = cv.poly([(560, 590), (650, 610), (760, 720), (860, 860), (930, 966), (800, 972), (680, 940),
                     (600, 800)], 10)
    L.paint(train, "#3e1a66", dark=gownd, lite="#9a70d0", rim=1.0, spec=0.2, tex=0.18, grain="vstreak", line=1.0,
            var=("#6a2a6a", 0.4))
    for i in range(7):
        u = i / 6
        p0 = lerp_pt((600, 620), (640, 640), u)
        p1 = lerp_pt((700, 950), (920, 962), u)
        L.stroke([p0, lerp_pt(p0, p1, 0.5), p1], 4, 2, gownd, alpha=0.5, soft=1.5, clip=train)
    L.stroke([(700, 950), (800, 970), (926, 964)], 6, 6, glowc, alpha=0.6, soft=2.5, clip=train)
    L.tint("#0a0418", 0.15)
    R.add("train", L, "gown", "cape", (600, 620), 4)

    # ---- torso: pale body, gill corset, high gill ruff, the relic
    L = R.layer()
    body = cv.poly([(470, 400), (556, 400), (590, 440), (594, 500), (566, 560), (560, 610), (464, 610), (458, 560),
                    (430, 500), (436, 440)], 10)
    L.paint(body, skin, dark=skind, lite=skinl, rim=0.9, spec=0.2, tex=0.12, line=1.0, var=("#c8b0d8", 0.4))
    corset = cv.poly([(440, 470), (512, 500), (588, 470), (572, 540), (560, 612), (464, 612), (452, 540)], 8)
    L.paint(corset, gown, dark=gownd, lite=gownl, rim=1.0, spec=0.35, shin=18, tex=0.15, grain="vstreak", line=1.0)
    for i in range(9):
        x = 456 + i * 13
        L.stroke([(x, 490 + abs(i - 4) * 3), (x + (512 - x) * 0.1, 606)], 3, 2, gownd, alpha=0.55, soft=1, clip=corset)
        L.stroke([(x - 3, 492 + abs(i - 4) * 3), (x - 3 + (512 - x) * 0.1, 600)], 1.6, 1, gownl, alpha=0.35,
                 clip=corset)
    L.stroke([(440, 470), (512, 500), (588, 470)], 4, 4, glowc, alpha=0.7, soft=1.5, clip=corset)
    # collarbones
    L.stroke([(468, 432), (494, 440)], 3, 1, skind, alpha=0.35, soft=1, clip=body)
    L.stroke([(530, 440), (556, 432)], 3, 1, skind, alpha=0.35, soft=1, clip=body)
    # the relic: a dragon-bone shard set in her breast, light cracking out through skin and bodice
    shard = cv.poly([(496, 444), (514, 430), (528, 452), (522, 494), (506, 508), (494, 482)], 4)
    for ang, ln in ((200, 60), (240, 52), (300, 56), (340, 60), (100, 70), (70, 66), (130, 50)):
        a = math.radians(ang)
        p0 = (510 + math.cos(a) * 16, 470 + math.sin(a) * 20)
        p1 = (510 + math.cos(a) * ln, 470 + math.sin(a) * ln)
        mid = lerp_pt(p0, p1, 0.5)
        mid = (mid[0] + math.sin(a) * 6, mid[1] - math.cos(a) * 6)
        L.stroke([p0, mid, p1], 4, 1, "#ff8a20", alpha=0.7, soft=1.2, clip=body)
        L.stroke([p0, mid, p1], 1.6, 0.6, "#fff0c0", alpha=0.9, soft=0.4, clip=body)
    L.glow(510, 470, 90, amber, 0.55, clip=body)
    L.fill(cv.ell(510, 470, 30, 40), "#2a0c04", alpha=0.8, soft=4)
    L.paint(shard, "#f4e0b0", dark="#7a4010", lite="#ffffff", rim=0, spec=0.6, shin=24, line=1.0, tex=0.2,
            emit=("#ffc860", 0.45))
    L.glow(510, 468, 30, "#fff8e0", 1.0, clip=shard)
    L.stroke([(508, 440), (514, 470), (508, 498)], 2, 1, "#a05a10", alpha=0.6, clip=shard)
    # the gill ruff rising behind the neck
    ruff = cv.poly(ell_pts(518, 400, 120, 64, 0, 180, 360, 30) + [(638, 410), (398, 410)], 0)
    ruff = SUB(ruff, cv.ell(512, 420, 40, 30))
    L.paint(ruff, "#e8c8f4", dark="#4a2060", lite="#ffffff", rim=0.6, spec=0.2, tex=0.12, line=1.0,
            emit=(glowc, 0.12), size=20)
    gill_fan(L, cv, 518, 420, [(400 + i * 10, 400 - 62 * math.sin(math.pi * i / 24)) for i in range(25)],
             "#7a3a9a", alpha=0.55, w=2.6, clip=ruff)
    edge = [(400 + i * 10, 400 - 62 * math.sin(math.pi * i / 24)) for i in range(25)]
    L.stroke(edge, 5, 5, glowc, alpha=0.7, soft=2, clip=ruff)
    L.stroke(edge, 2, 2, "#ffffff", alpha=0.7, soft=0.6, clip=ruff)
    R.add("torso", L, "gown", "torso", (512, 600), 14)
    del L

    # ---- back arm (vine) raised, holding the thorn sceptre
    L = R.layer()
    vine(L, cv, [(578, 452), (640, 440), (700, 420)], [26, 22, 20], vinec, vined, vinel, seed=7, thorns=3, leaves=1)
    L.tint("#060a14", 0.15)
    R.add("arm_back_upper", L, "torso", "arm_back_upper", (578, 452), 6)

    L = R.layer()
    vine(L, cv, [(700, 420), (750, 396), (790, 366)], [20, 17, 15], vinec, vined, vinel, seed=8, thorns=2, leaves=1)
    # tendril fingers wrapped round the sceptre
    for dy in (-14, 0, 14):
        L.stroke([(786, 368 + dy), (816, 364 + dy), (826, 378 + dy), (810, 386 + dy)], 9, 5, vinec, alpha=1.0,
                 soft=0.5)
    L.paint(L.mask(), vinec, dark=vined, lite=vinel, rim=0.8, spec=0.3, tex=0.15, line=0.9, size=10)
    L.tint("#060a14", 0.15)
    R.add("arm_back_lower", L, "arm_back_upper", "arm_back_lower", (700, 420), 8)

    L = R.layer()
    sc = vine(L, cv, [(810, 600), (808, 480), (802, 360), (806, 250), (834, 186), (878, 176), (896, 210),
                      (874, 236), (850, 226)], [10, 12, 12, 11, 9, 7, 5, 3.5, 2.5], vinec, vined, vinel, seed=9,
              thorns=8, leaves=2, twist=False)
    bud = cv.ell(842, 270, 26, 34, 10)
    L.paint(bud, "#c890f0", dark=capd, lite="#ffffff", rim=0.4, spec=0.8, shin=24, line=1.0, tex=0.06,
            emit=(glowc, 0.4))
    L.glow(842, 270, 40, "#ffffff", 0.8, clip=bud)
    for a in (-40, 0, 40):
        L.paint(cv.poly(rot([(842, 304), (826, 270), (842, 242), (858, 270)], (842, 304), a), 4), "#3f8a4a",
                dark=vined, lite=vinel, rim=0.4, line=0.8, tex=0.1)
    L.tint("#060a14", 0.1)
    R.add("sceptre", L, "arm_back_lower", "offhand", (806, 374), 5)
    R.add("sceptre_glow", _fx([(842, 270, 90, glowc, 0.5), (842, 270, 30, "#ffffff", 0.4)], cv), "sceptre", "fx",
          (842, 270), 28, blend="add")

    # ---- head: pale eerie face, half-lidded eyes, the bell cap with glowing spots, gills underneath
    L = R.layer()
    neck = cv.limb([(500, 380), (506, 424)], [26, 30])
    face = cv.poly([(452, 256), (520, 256), (548, 290), (550, 330), (536, 364), (506, 392), (474, 404), (452, 402),
                    (438, 388), (430, 366), (424, 348), (418, 336), (424, 322), (424, 296), (432, 270)], 10)
    hair = cv.poly([(430, 262), (540, 258), (560, 300), (556, 350), (540, 330), (530, 290), (470, 276), (436, 290)], 8)
    L.paint(U(neck, face), skin, dark=skind, lite=skinl, rim=0.8, spec=0.25, tex=0.1, line=1.0,
            var=("#c8b0d8", 0.4))
    L.fill(cv.ell(500, 352, 30, 26), "#c890c8", alpha=0.25, soft=10, clip=face)  # flush on the cheek
    L.fill(cv.ell(540, 330, 30, 60), skind, alpha=0.25, soft=14, clip=face)  # far cheek turns away
    # hair of fine pale hyphae framing the face
    L.paint(hair, "#d8c8f0", dark="#4a2a6a", lite="#ffffff", rim=0.8, spec=0.3, tex=0.2, grain="vstreak", line=0.9)
    fibers(L, cv, hair, 60, (0.3, 1), 30, "#6a4a90", alpha=0.4, width=1.2, seed=31)
    # eyes: half-lidded, glowing green, long dark lashes
    eye(L, cv, 470, 318, 20, 11, spore, rotd=-6, pupil="slit", glow=1.3, lid=(-6, -0.05), look=(-0.4, 0.15),
        core="#f8ffe0", sclera=None)
    eye(L, cv, 432, 316, 11, 9, spore, rotd=-4, pupil="slit", glow=1.1, lid=(-4, -0.05), look=(-0.4, 0.15),
        core="#f8ffe0")
    L.stroke([(446, 314), (470, 308), (494, 316)], 4, 2, "#1a0820", alpha=0.95, soft=0.6)  # lash line
    L.stroke([(488, 314), (500, 306)], 3, 1, "#1a0820", alpha=0.9, soft=0.5)
    L.stroke([(424, 314), (440, 312)], 3, 1.5, "#1a0820", alpha=0.9, soft=0.5)
    L.stroke([(446, 294), (476, 286), (500, 294)], 4, 1.5, "#4a2060", alpha=0.7, soft=0.8)  # brows
    L.stroke([(422, 296), (436, 292)], 3, 1.5, "#4a2060", alpha=0.7, soft=0.8)
    # nose and smug smile
    L.stroke([(428, 324), (420, 348), (430, 354)], 3, 1.5, skind, alpha=0.45, soft=1)
    lips = cv.poly([(430, 370), (452, 366), (476, 362), (486, 356), (480, 370), (456, 380), (436, 380)], 6)
    L.paint(lips, "#6a2a6a", dark="#1a0420", lite="#d080c8", rim=0, spec=0.6, shin=26, line=0.8, tex=0.05)
    L.stroke([(432, 371), (456, 370), (482, 360)], 2, 1.2, "#1a0420", alpha=0.85, soft=0.5)
    L.stroke([(482, 360), (490, 352)], 2, 1, skind, alpha=0.5, soft=0.6)
    # faint glowing gill-lines on the temple
    for i in range(4):
        L.stroke([(520, 280 + i * 12), (536, 290 + i * 12)], 2, 1, glowc, alpha=0.5, soft=0.8, clip=face)
    # cap underside: gills glowing violet-white
    gm = cv.poly(ell_pts(512, 268, 262, 26, 0, 0, 180, 40) + [(250, 264), (774, 264)], 0)
    L.paint(gm, "#e0c0f0", dark="#4a2060", lite="#ffffff", rim=0, line=1.0, tex=0.1, emit=(glowc, 0.3))
    gill_fan(L, cv, 512, 330, [(256 + i * 18, 268 + 18 * math.sin(math.pi * i / 28)) for i in range(29)],
             "#6a2a8a", alpha=0.55, w=3, clip=gm)
    L.glow(512, 290, 200, glowc, 0.4, clip=gm)
    # the bell cap
    capm = cv.poly([(246, 276), (276, 236), (330, 196), (372, 150), (404, 96), (452, 62), (512, 50), (572, 62),
                    (620, 96), (652, 150), (694, 196), (748, 236), (778, 276), (700, 286), (600, 280), (512, 284),
                    (420, 282), (320, 286)], 10)
    L.paint(capm, capc, dark=capd, lite=capl, rim=1.0, spec=0.5, shin=16, tex=0.14, grain="mottle",
            var=("#b04aa0", 0.4), line=1.2, wrap=0.4)
    L.fill(cv.poly([(240, 240), (790, 240), (790, 300), (240, 300)]), capd, alpha=0.35, soft=14, clip=capm)
    fibers(L, cv, capm, 120, (0.2, 1), 50, "#2a0a4a", alpha=0.25, width=1.4, seed=10)
    # glowing rings and spots
    for i in range(13):  # faint glowing ribs running down the bell
        a = -150 + i * 10
        top = (512 + math.cos(math.radians(a + 60)) * 40, 70)
        bot = (270 + i * 41, 268)
        L.stroke([top, lerp_pt(top, bot, 0.6), bot], 4, 6, glowc, alpha=0.18, soft=3, clip=capm)
    glow_spots(L, cv, [(330, 250, 13, 8), (420, 214, 16, 10), (512, 224, 18, 11), (604, 214, 16, 10),
                       (694, 250, 13, 8), (440, 140, 12, 8), (512, 120, 14, 9), (584, 140, 12, 8),
                       (380, 260, 8, 5), (650, 262, 8, 5), (470, 90, 8, 6), (556, 90, 8, 6)], "#7affd8", clip=capm)
    L.stroke([(270, 270), (400, 276), (512, 278), (640, 274), (770, 270)], 5, 3, "#f0d0ff", alpha=0.45, soft=2,
             clip=capm)
    L.fill(cv.poly([(410, 280), (560, 280), (560, 330), (410, 330)]), "#2a0a3a", alpha=0.35, soft=12, clip=face)
    L.glow(470, 300, 70, glowc, 0.25, clip=face)
    L.glow(470, 420, 80, amber, 0.2, clip=U(face, neck))  # relic light from below
    R.add("head", L, "torso", "head", (504, 410), 18)
    del L

    # ---- crown of little luminous toadstools (sway)
    L = R.layer()
    for x, y, s, ang, c in ((450, 74, 0.9, -22, "#6affd0"), (500, 56, 1.1, -4, "#ffd06a"), (548, 60, 1.0, 10,
                                                                                          "#ff8ad8"),
                            (594, 84, 0.85, 24, "#6affd0"), (412, 108, 0.7, -34, "#ff8ad8")):
        a = math.radians(ang)
        top = (x + math.sin(a) * 38 * s, y - math.cos(a) * 38 * s)
        st = cv.limb([(x, y + 20), lerp_pt((x, y), top, 0.5), top], [9 * s, 7 * s, 6 * s])
        L.paint(st, "#f0e4f4", dark="#4a3a4a", lite="#ffffff", rim=0.5, line=0.8, tex=0.1)
        cp = cv.poly(rot(ell_pts(top[0], top[1] + 4 * s, 32 * s, 26 * s, 0, 180, 360, 24) +
                         [(top[0] + 30 * s, top[1] + 6 * s), (top[0] - 30 * s, top[1] + 6 * s)], top, ang), 0)
        L.paint(cp, mixc(c, "#4a2a6a", 0.25), dark=capd, lite="#ffffff", rim=0.4, spec=0.7, shin=24, line=0.8,
                tex=0.06, emit=(c, 0.35))
        L.glow(top[0], top[1] - 4, 26 * s, "#ffffff", 0.6, clip=cp)
        L.glow(top[0], top[1], 50 * s, c, 0.5, mode="halo")
    R.add("crown", L, "head", "hair", (512, 70), 19)

    # ---- veil: curtains of glowing threads hanging from the cap rim (sway)
    for name, xs, y0, y1, piv, z in (("veil_front", (256, 360), 274, 520, (310, 278), 24),
                                     ("veil_back", (660, 772), 274, 600, (716, 278), 12)):
        L = R.layer()
        rng = np.random.default_rng(len(name) * 7)
        for i in range(13):
            x = xs[0] + (xs[1] - xs[0]) * i / 12 + rng.uniform(-4, 4)
            y = y0 + abs(x - (xs[0] + xs[1]) / 2) * -0.05 + rng.uniform(0, 8)
            ln = (y1 - y0) * rng.uniform(0.35, 1.0)
            sway = rng.uniform(-12, 12)
            pts = [(x, y), (x + sway * 0.4, y + ln * 0.5), (x + sway, y + ln)]
            L.stroke(pts, 4, 1.5, glowc, alpha=0.2, soft=2)
            L.stroke(pts, 1.3, 0.5, "#f4e0ff", alpha=0.65, soft=0.4)
            for t in (0.5, 1.0):
                if rng.random() < (0.3 if t < 1 else 0.8):
                    px, py = crspline(pts, 6)[int(t * (len(crspline(pts, 6)) - 1))]
                    r = rng.uniform(2.2, 4.2) * (1.3 if t == 1.0 else 1)
                    L.glow(px, py, r * 3, glowc, 0.5, mode="halo")
                    L.fill(cv.ell(px, py, r, r * 1.2), "#fbefff", alpha=0.95, soft=0.4)
        R.add(name, L, "head", "hair", piv, z)

    # ---- front arm: vine reaching out, open hand of tendrils, spores rising from the palm
    L = R.layer()
    vine(L, cv, [(452, 452), (410, 490), (370, 520)], [28, 24, 22], vinec, vined, vinel, seed=11, thorns=3, leaves=1)
    R.add("arm_front_upper", L, "torso", "arm_front_upper", (452, 452), 20)
    L = R.layer()
    vine(L, cv, [(370, 520), (330, 530), (292, 516)], [22, 19, 16], vinec, vined, vinel, seed=12, thorns=2, leaves=1)
    palm = cv.ell(276, 506, 26, 18, -20)
    fingers = [palm]
    for ang, ln, curl in ((-150, 58, 0.6), (-125, 64, 0.5), (-100, 58, 0.5), (-75, 46, 0.6), (170, 40, -0.6)):
        a = math.radians(ang)
        p0 = (276 + math.cos(a) * 14, 506 + math.sin(a) * 10)
        p1 = (p0[0] + math.cos(a) * ln * 0.6, p0[1] + math.sin(a) * ln * 0.6)
        p2 = (p1[0] + math.cos(a + curl) * ln * 0.45, p1[1] + math.sin(a + curl) * ln * 0.45)
        p3 = (p2[0] + math.cos(a + curl * 2.2) * ln * 0.25, p2[1] + math.sin(a + curl * 2.2) * ln * 0.25)
        fingers.append(cv.limb([p0, p1, p2, p3], [8, 6, 4, 1.5]))
    hm = U(*fingers)
    L.paint(hm, vinec, dark=vined, lite=vinel, rim=0.8, spec=0.35, shin=18, tex=0.15, line=1.0)
    L.glow(270, 470, 70, spore, 0.6, clip=hm)
    R.add("arm_front_lower", L, "arm_front_upper", "arm_front_lower", (370, 520), 21)
    L = R.layer()
    L.glow(266, 440, 80, spore, 0.4, mode="halo")
    rng = np.random.default_rng(13)
    pts = []
    for i in range(46):
        t = i / 45
        a = t * 5 * math.pi
        x = 270 + math.sin(a) * (12 + 50 * t) + rng.uniform(-8, 8)
        y = 480 - t * 250 + rng.uniform(-8, 8)
        pts.append((x, y, rng.uniform(1.6, 4.6) * (1.2 - t * 0.5)))
    spore_dots(L, cv, pts, spore)
    L.stroke(crspline([(270, 480), (290, 420), (246, 360), (280, 300), (250, 240)], 10), 18, 4, spore, alpha=0.18,
             soft=8)
    R.add("spore_stream", L, "arm_front_lower", "weapon", (276, 500), 23)

    # ---- spore clouds drifting round her (float)
    for i, (cx, cy, w, h) in enumerate(((150, 620, 230, 150), (930, 470, 170, 120), (170, 330, 150, 100),
                                        (890, 780, 190, 120))):
        L = R.layer()
        spore_cloud(L, cv, cx, cy, w, h, spore, seed=20 + i, alpha=0.55)
        R.add(f"spore_cloud_{i + 1}", L, "gown", "float", (cx, cy), 30 + i)

    # ---- additive glows
    R.add("relic_glow", _fx([(510, 470, 140, amber, 0.55), (510, 470, 46, "#fff4d0", 0.6)], cv), "torso", "fx",
          (510, 470), 26, blend="add")
    R.add("cap_glow", _fx([(512, 290, 260, glowc, 0.22), (512, 224, 60, "#7affd8", 0.2), (470, 318, 40, spore, 0.3)],
                          cv), "head", "fx", (512, 260), 27, blend="add")
    R.add("gown_glow", _fx([(512, 960, 300, glowc, 0.14), (512, 820, 220, glowc, 0.12), (300, 960, 60, glowc, 0.2),
                            (740, 960, 60, glowc, 0.2)], cv), "gown", "fx", (512, 900), 25, blend="add")
    R.add("hand_glow", _fx([(270, 470, 110, spore, 0.4)], cv), "arm_front_lower", "fx", (276, 500), 29, blend="add")
    R.save()
    return R


# ================================================================== driver

RIGS = {
    "mushroom_mage": mushroom_mage,
    "cave_slime": cave_slime,
    "toxic_toad": toxic_toad,
    "glow_bat": glow_bat,
    "shroom_brute": shroom_brute,
    "spore_mother": spore_mother,
}

SCRATCH = os.environ.get("D2_SHEET_DIR", "")


def main(ids=None):
    ids = ids or list(RIGS)
    for rid in ids:
        t = time.time()
        RIGS[rid]()
        print(f"{rid}: {time.time() - t:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])

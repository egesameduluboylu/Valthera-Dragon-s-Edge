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


# ================================================================== driver

RIGS = {
    "mushroom_mage": mushroom_mage,
    "cave_slime": cave_slime,
    "toxic_toad": toxic_toad,
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

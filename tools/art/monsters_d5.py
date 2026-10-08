"""Dungeon 5 (the Dragon Lair) monsters as painted cut-out rigs (M8 style).

    python3 tools/art/monsters_d5.py                     # all five
    python3 tools/art/monsters_d5.py whelp ashwing       # just these

dragon_guard, whelp, ash_wraith, elder_drake (elite) and ashwing (final boss). Every monster faces
left. Each part is painted on its own layer with a small numpy "painter": shapes become masks, masks
become height fields, and the height fields are lit (warm key from the upper left, cool fill, hot
ember rim from behind on the far edge, specular for metal and wet scales) at 2x and downscaled.
Rigs go to assets/rigs/<id>/ (see rig.py) and the still pictures to assets/sprites/enemies/<id>.png.
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

SS = int(os.environ.get("D5_SS", "2"))   # working pixels per canvas pixel (1 = fast preview)
MSS = 2         # extra supersampling for mask edges

# ------------------------------------------------------------------ colour helpers


def C(h, a=1.0):
    """'#rrggbb' -> float rgb array 0..1."""
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def norm3(x, y, z):
    v = np.array([x, y, z], np.float32)
    return v / np.linalg.norm(v)


KEY = norm3(-0.55, -0.72, 0.52)      # warm key light, upper left, toward the viewer
KEY_C = np.array([1.0, 0.92, 0.80], np.float32)
FILL = norm3(0.55, 0.35, 0.55)       # cool fill from the lower right
FILL_C = np.array([0.30, 0.34, 0.52], np.float32)
AMB_C = np.array([0.20, 0.18, 0.26], np.float32)
RIM_DIR = np.array([0.92, -0.38], np.float32)   # the rim sits on the far (right) edge
RIM_C = np.array([1.0, 0.52, 0.20], np.float32)  # ember light from the lair behind
UNDER = norm3(0.15, 1.0, 0.25)       # lava bounce from the floor
UNDER_C = np.array([0.55, 0.20, 0.06], np.float32)


# ------------------------------------------------------------------ numpy image helpers

def _box(a, r, axis):
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode="edge")
    c = np.cumsum(p, axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a, r):
    """Approximate gaussian blur of a 2-D float array (sigma about r)."""
    if r < 0.6:
        return a
    h, w = a.shape
    if r > 6:
        f = r / 4.0
        sw, sh = max(2, int(round(w / f))), max(2, int(round(h / f)))
        small = np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((sw, sh), Image.BILINEAR))
        small = blur(small, 4)
        return np.asarray(Image.fromarray(small, "F").resize((w, h), Image.BICUBIC)).astype(np.float32)
    br = max(1, int(round(r * 0.9)))
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box(_box(out, br, 0), br, 1)
    return out


def dist(m, r):
    """Smooth distance (working px) from each inside pixel to the mask edge, good up to about r."""
    h, w = m.shape
    f = max(1.0, r / 36.0)
    sw, sh = max(4, int(round(w / f))), max(4, int(round(h / f)))
    small = np.asarray(Image.fromarray(m.astype(np.float32), "F").resize((sw, sh), Image.BILINEAR))
    d = np.where(small > 0.5, 1e6, 0.0).astype(np.float32)
    d = np.where((small > 0.5) & (small < 0.999), small - 0.5, d)
    d = np.pad(d, 1, constant_values=0)
    s2 = math.sqrt(2)
    lim = int(r / f) + 3
    for _ in range(lim):
        c = d[1:-1, 1:-1]
        n = np.minimum.reduce([c, d[:-2, 1:-1] + 1, d[2:, 1:-1] + 1, d[1:-1, :-2] + 1, d[1:-1, 2:] + 1,
                               d[:-2, :-2] + s2, d[:-2, 2:] + s2, d[2:, :-2] + s2, d[2:, 2:] + s2])
        if np.array_equal(n, c):
            break
        d[1:-1, 1:-1] = n
    d = np.minimum(d[1:-1, 1:-1], lim) * f
    out = np.asarray(Image.fromarray(d.astype(np.float32), "F").resize((w, h), Image.BICUBIC)).astype(np.float32)
    out = blur(np.maximum(out, 0), f * 1.3 + 1.0)
    return out * (m > 0.01)


def noise(h, w, scale, seed=0, octaves=4, persist=0.55):
    """Fractal value noise in 0..1, feature size about `scale` pixels."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    s = float(scale)
    for _ in range(octaves):
        gw, gh = max(2, int(w / s) + 3), max(2, int(h / s) + 3)
        g = rng.random((gh, gw)).astype(np.float32)
        big = Image.fromarray(g, "F").resize((int(gw * s), int(gh * s)), Image.BICUBIC)
        ox, oy = int(rng.integers(0, max(1, int(s)))), int(rng.integers(0, max(1, int(s))))
        arr = np.asarray(big)[oy:oy + h, ox:ox + w]
        if arr.shape != (h, w):
            arr = np.pad(arr, ((0, h - arr.shape[0]), (0, w - arr.shape[1])), mode="edge")
        out += arr * amp
        tot += amp
        amp *= persist
        s = max(2.0, s / 2.0)
    return np.clip(out / tot, 0, 1)


# ------------------------------------------------------------------ geometry

def catmull(pts, closed=False, n=10):
    """Catmull-Rom spline through pts."""
    pts = [tuple(map(float, p)) for p in pts]
    if len(pts) < 3:
        if len(pts) == 2 and not closed:
            (x0, y0), (x1, y1) = pts
            return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
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


def resample(path, n):
    """n+1 evenly spaced points along a polyline, with cumulative lengths."""
    p = np.array(path, np.float64)
    d = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0], np.cumsum(d)])
    t = np.linspace(0, s[-1], n + 1)
    x = np.interp(t, s, p[:, 0])
    y = np.interp(t, s, p[:, 1])
    return list(zip(x, y)), t


def tube_poly(ctrl, widths, n=60, smooth_path=True):
    """Outline polygon of a stroke along a spline whose width runs through `widths` (full widths)."""
    path = catmull(ctrl, n=12) if smooth_path and len(ctrl) > 2 else catmull(ctrl, n=12)
    pts, t = resample(path, n)
    L = t[-1] or 1
    wk = np.interp(t / L, np.linspace(0, 1, len(widths)), widths)
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        hw = wk[i] / 2
        left.append((x + nx * hw, y + ny * hw))
        right.append((x - nx * hw, y - ny * hw))
    return left + right[::-1], pts, wk


def rot(pts, c, deg):
    r = math.radians(deg)
    cs, sn = math.cos(r), math.sin(r)
    return [(c[0] + (x - c[0]) * cs - (y - c[1]) * sn, c[1] + (x - c[0]) * sn + (y - c[1]) * cs) for x, y in pts]


def ellipse_pts(cx, cy, rx, ry, ang=0, n=48):
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return rot(pts, (cx, cy), ang) if ang else pts


# ------------------------------------------------------------------ the layer painter

class Layer:
    """A part being painted: premultiplied float RGBA over a box of the rig canvas, at SS x resolution.
    Every coordinate given to its methods is in canvas pixels."""

    def __init__(self, canvas, box=None):
        W, H = canvas
        if box is None:
            box = (0, 0, W, H)
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        self.canvas = canvas
        self.x0, self.y0 = max(0, x0), max(0, y0)
        self.x1, self.y1 = min(W, x1), min(H, y1)
        self.w = (self.x1 - self.x0) * SS
        self.h = (self.y1 - self.y0) * SS
        self.rgb = np.zeros((self.h, self.w, 3), np.float32)   # premultiplied
        self.a = np.zeros((self.h, self.w), np.float32)
        self._grid = None

    # -- coordinates
    def P(self, x, y):
        return ((x - self.x0) * SS, (y - self.y0) * SS)

    def grid(self):
        if self._grid is None:
            yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
            self._grid = (xx / SS + self.x0, yy / SS + self.y0)
        return self._grid

    # -- masks
    def _raster(self, draw_fn, bbox):
        """Rasterises a shape at MSS x the working resolution inside its own bbox and returns a full mask."""
        m = np.zeros((self.h, self.w), np.float32)
        bx0, by0, bx1, by1 = bbox
        X0 = max(0, int(math.floor((bx0 - self.x0) * SS)) - 2)
        Y0 = max(0, int(math.floor((by0 - self.y0) * SS)) - 2)
        X1 = min(self.w, int(math.ceil((bx1 - self.x0) * SS)) + 2)
        Y1 = min(self.h, int(math.ceil((by1 - self.y0) * SS)) + 2)
        if X1 <= X0 or Y1 <= Y0:
            return m
        img = Image.new("L", ((X1 - X0) * MSS, (Y1 - Y0) * MSS), 0)
        d = ImageDraw.Draw(img)

        def T(x, y):
            return (((x - self.x0) * SS - X0) * MSS, ((y - self.y0) * SS - Y0) * MSS)
        draw_fn(d, T)
        img = img.reduce(MSS) if MSS > 1 else img
        m[Y0:Y1, X0:X1] = np.asarray(img, np.float32)[:Y1 - Y0, :X1 - X0] / 255.0
        return m

    def poly(self, pts):
        pts = list(pts)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return self._raster(lambda d, T: d.polygon([T(*p) for p in pts], fill=255), (min(xs), min(ys), max(xs), max(ys)))

    def blob(self, ctrl, n=10):
        return self.poly(catmull(ctrl, closed=True, n=n))

    def ellipse(self, cx, cy, rx, ry, ang=0):
        return self.poly(ellipse_pts(cx, cy, rx, ry, ang, n=max(24, int((rx + ry) * 0.8))))

    def tube(self, ctrl, widths, caps=True, n=None):
        n = n or max(24, int(sum(math.hypot(ctrl[i + 1][0] - ctrl[i][0], ctrl[i + 1][1] - ctrl[i][1])
                                 for i in range(len(ctrl) - 1)) / 4))
        outline, pts, wk = tube_poly(ctrl, widths, n=n)
        m = self.poly(outline)
        if caps:
            for (x, y), w in ((pts[0], wk[0]), (pts[-1], wk[-1])):
                if w > 1.5:
                    m = np.maximum(m, self.ellipse(x, y, w / 2, w / 2))
        return m

    def line(self, pts, width):
        pts = list(pts)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        pad = width

        def fn(d, T):
            q = [T(*p) for p in pts]
            d.line(q, fill=255, width=max(1, int(round(width * SS * MSS))), joint="curve")
        return self._raster(fn, (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad))

    # -- shading
    @staticmethod
    def height(m, r, profile="round"):
        """Height field (in working pixels) of a mask: rounded like a tube over about r working pixels in
        from the edge (from a distance field), flat-topped beyond that."""
        t = np.clip(dist(m, r) / r, 0, 1)
        if profile == "round":
            h = np.sqrt(np.clip(1 - (1 - t) ** 2, 0, 1))
        elif profile == "flat":
            h = t ** 0.5
        else:
            h = t
        return h * r * np.clip(m * 1.5, 0, 1)

    def normals(self, h):
        gy, gx = np.gradient(h)
        nz = np.ones_like(h)
        ln = np.sqrt(gx * gx + gy * gy + 1.0)
        return -gx / ln, -gy / ln, nz / ln

    def paint(self, m, color, r=None, bump=None, rough=0.45, spec=0.25, shin=18, metal=0.0, rim=1.0, line=1.0,
              tex=0.12, tex_scale=6, seed=1, clip=None, alpha=1.0, h=None, emissive=None, sss=0.0, rimc=None,
              shadow=None, light=None, keyk=1.0, amb=1.0, env=None, line_c=None, top=None, under=1.0, r2=None, k2=0.3):
        """Lights a mask. color: albedo (rgb 0..1) or an HxWx3 array. r: rounding radius in canvas px.
        bump: extra height (working px). metal: 0..1 (strong reflections). emissive: HxWx3 added light."""
        if clip is not None:
            m = m * clip
        if m.max() <= 0:
            return m
        ys, xs = np.nonzero(m > 0.001)
        pad = int((r or 20) * SS * 1.5) + 8
        Y0, Y1 = max(0, ys.min() - pad), min(self.h, ys.max() + pad + 1)
        X0, X1 = max(0, xs.min() - pad), min(self.w, xs.max() + pad + 1)
        mm = m[Y0:Y1, X0:X1]
        if r is None:
            r = 20
        if h is None:
            hh = self.height(mm, r * SS)
            if r2:
                hh = hh + self.height(mm, r2 * SS) * k2
        else:
            hh = h[Y0:Y1, X0:X1]
        n0x, n0y, n0z = self.normals(hh)          # the big form
        if bump is not None:
            hb = hh + bump[Y0:Y1, X0:X1] * np.clip(hh / (0.35 * r * SS + 1e-3), 0, 1)
            nx, ny, nz = self.normals(hb)          # the form with its surface detail
        else:
            nx, ny, nz = n0x, n0y, n0z
        # brush-like noise perturbs the light a little, like painted strokes
        if tex:
            nzz = noise(Y1 - Y0, X1 - X0, tex_scale * SS, seed=seed, octaves=3)
            nx = nx + (nzz - 0.5) * tex * 0.8
            ny = ny + (noise(Y1 - Y0, X1 - X0, tex_scale * SS * 1.3, seed=seed + 7, octaves=3) - 0.5) * tex * 0.8
        dk0 = n0x * KEY[0] + n0y * KEY[1] + n0z * KEY[2]
        dk = nx * KEY[0] + ny * KEY[1] + nz * KEY[2]
        base = smooth(-0.2, 0.62, dk0)
        # detail shows in the light and melts away in the shadow, as a painter would render it
        diff = np.clip(base + (dk - dk0) * 1.3 * np.sqrt(base + 0.05), 0, 1.2) * keyk
        df = np.clip(n0x * FILL[0] + n0y * FILL[1] + n0z * FILL[2], 0, 1)
        alb = color if np.ndim(color) == 1 else color[Y0:Y1, X0:X1]
        alb = np.broadcast_to(alb, mm.shape + (3,)).astype(np.float32)
        if top is not None:  # dust or sheen that settles on up-facing surfaces
            tc, tk = top
            nn = noise(Y1 - Y0, X1 - X0, 9 * SS, seed=seed + 11, octaves=3)
            k = np.clip(-ny * 2.2 - 0.15, 0, 1) * smooth(0.35, 0.75, nn) * tk
            alb = lerp(alb, np.asarray(tc, np.float32), k[..., None])
        du = np.clip(n0x * UNDER[0] + n0y * UNDER[1] + n0z * UNDER[2], 0, 1) ** 1.5
        lit = (AMB_C * amb + FILL_C * df[..., None]) + KEY_C * diff[..., None] * 1.05 + UNDER_C * du[..., None] * under
        if shadow is not None:  # tint shadows toward a colour
            lit = lit + (1 - diff[..., None]) * np.asarray(shadow, np.float32) * 0.25
        col = alb * lit
        if tex:
            col = col * (1 + (nzz[..., None] - 0.5) * tex * 0.9)
        # metal: environment reflection by normal direction (warm cave light above, dark ember floor below)
        if metal > 0:
            e_up = np.array([1.0, 0.86, 0.66], np.float32) if env is None else np.asarray(env[0], np.float32)
            e_dn = np.array([0.20, 0.10, 0.07], np.float32) if env is None else np.asarray(env[1], np.float32)
            t = np.clip(-ny * 1.6 - nx * 0.5 + 0.35, 0, 1)
            t = smooth(0.3, 0.7, t)
            refl = lerp(e_dn, e_up, t[..., None]) * alb * 1.4
            col = lerp(col, refl, metal * 0.55)
        # specular: the key, and an ember glint from the floor below
        hv = KEY + np.array([0, 0, 1], np.float32)
        hv = hv / np.linalg.norm(hv)
        sp = np.clip(nx * hv[0] + ny * hv[1] + nz * hv[2], 0, 1) ** shin
        col = col + sp[..., None] * spec * KEY_C * (1.0 if metal == 0 else lerp(1.0, 1.3, metal))
        hu = UNDER + np.array([0, 0, 1], np.float32)
        hu = hu / np.linalg.norm(hu)
        su = np.clip(nx * hu[0] + ny * hu[1] + nz * hu[2], 0, 1) ** shin
        col = col + su[..., None] * spec * under * UNDER_C * 1.6
        # rim on the far edge
        if rim:
            edge = smooth(0.35, 0.85, 1 - n0z)
            side = np.clip(n0x * RIM_DIR[0] + n0y * RIM_DIR[1], 0, 1)
            rc = RIM_C if rimc is None else np.asarray(rimc, np.float32)
            col = col + (edge * side * rim * 1.1)[..., None] * rc
        if sss:
            col = col + (np.clip(1 - diff, 0, 1) * sss)[..., None] * alb * 0.6
        if emissive is not None:
            col = col + emissive[Y0:Y1, X0:X1]
        if light is not None:
            col = col + light[Y0:Y1, X0:X1]
        # a thin colour-matched line that fades on the lit side
        if line:
            lw = 1.1 * SS * line
            inner = np.clip((blur(mm, lw * 0.6) - 0.5) * 2.2, 0, 1)
            band = np.clip(mm - inner, 0, 1)
            lc = alb * 0.22 if line_c is None else np.asarray(line_c, np.float32)
            k = band * (1 - 0.8 * np.clip(diff, 0, 1)) * 0.85
            col = lerp(col, lc, k[..., None])
        col = np.clip(col, 0, 1.4)
        self._over(col, mm * alpha, X0, Y0)
        return m

    def _over(self, col, a, X0=0, Y0=0):
        h, w = a.shape
        sl = (slice(Y0, Y0 + h), slice(X0, X0 + w))
        A = self.a[sl]
        self.rgb[sl] = np.minimum(col, 1.0) * a[..., None] + self.rgb[sl] * (1 - a[..., None])
        self.a[sl] = a + A * (1 - a)

    def flat(self, m, color, alpha=1.0, clip=None):
        """Plain colour (rgb or HxWx3) over the layer."""
        if clip is not None:
            m = m * clip
        col = np.broadcast_to(np.asarray(color, np.float32), m.shape + (3,)) if np.ndim(color) == 1 else color
        self._over(col, m * alpha)

    def tint(self, m, color, k, mode="mul"):
        """Changes existing colour inside m: mode mul (darken toward colour) or screen (lighten)."""
        c = np.asarray(color, np.float32)
        k = (m * k)[..., None]
        if mode == "mul":
            self.rgb = self.rgb * (1 - k) + self.rgb * c * k
        elif mode == "screen":
            self.rgb = self.rgb + (self.a[..., None] * c - self.rgb * c) * k
        else:  # replace colour, keep alpha
            self.rgb = self.rgb * (1 - k) + self.a[..., None] * c * k

    def add_light(self, amount, color, clip_alpha=True, extend=0.0):
        """Adds light (glow) HxW amount x colour. With extend > 0 the glow also spills past the silhouette
        as a translucent halo."""
        c = np.asarray(color, np.float32)
        if clip_alpha:
            self.rgb = self.rgb + (amount * self.a)[..., None] * c
        if extend:
            halo = np.clip(amount * extend, 0, 1) * (1 - self.a)
            self.rgb = self.rgb + halo[..., None] * c
            self.a = self.a + halo
        self.rgb = np.minimum(self.rgb, self.a[..., None])

    def radial(self, cx, cy, r, power=2.0):
        xx, yy = self.grid()
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
        return np.clip(1 - d, 0, 1) ** power

    def glow(self, cx, cy, r, color, k=1.0, extend=0.6, power=2.0):
        self.add_light(self.radial(cx, cy, r, power) * k, color, extend=extend)

    def ao(self, m, k=0.5, r=6, dx=2, dy=4, color=(0.08, 0.04, 0.06)):
        """Soft shadow cast by a shape (m, drawn afterward) onto what is already painted."""
        s = blur(np.roll(np.roll(m, int(dy * SS), 0), int(dx * SS), 1), r * SS)
        s = s * (1 - m) * k
        self.rgb = self.rgb * (1 - s[..., None]) + (self.a * s)[..., None] * np.asarray(color, np.float32)

    def feather(self, p0, direction, start, width):
        """Fades the layer out toward p0: alpha x smoothstep of the distance along `direction` (degrees)
        from p0, over [start, start + width] canvas px. Used where a child part lies over its parent."""
        xx, yy = self.grid()
        r = math.radians(direction)
        d = (xx - p0[0]) * math.cos(r) + (yy - p0[1]) * math.sin(r)
        k = smooth(start, start + width, d)
        self.rgb *= k[..., None]
        self.a *= k

    # -- output
    def image(self):
        """Full-canvas RGBA at canvas resolution."""
        a = np.clip(self.a, 0, 1)
        rgb = np.clip(self.rgb, 0, 1)
        arr = np.dstack([rgb, a[..., None]])
        im = Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBa")
        im = im.resize((self.x1 - self.x0, self.y1 - self.y0), Image.LANCZOS).convert("RGBA")
        out = Image.new("RGBA", self.canvas, (0, 0, 0, 0))
        out.paste(im, (self.x0, self.y0))
        return out

    def merge(self, other):
        """Draws another layer (same box) over this one."""
        self._over_pm(other.rgb, other.a)

    def _over_pm(self, prgb, a):
        self.rgb = prgb + self.rgb * (1 - a[..., None])
        self.a = a + self.a * (1 - a)


# ------------------------------------------------------------------ surface bumps (height in working px)

def _sub(L, m, pad=4):
    """Slices of the layer covering mask m (plus pad working px) and the canvas coords there."""
    if m is None:
        xx, yy = L.grid()
        return (slice(0, L.h), slice(0, L.w)), xx, yy
    ys, xs = np.nonzero(m > 0.001)
    if len(ys) == 0:
        return (slice(0, 1), slice(0, 1)), L.grid()[0][:1, :1], L.grid()[1][:1, :1]
    Y0, Y1 = max(0, ys.min() - pad), min(L.h, ys.max() + pad + 1)
    X0, X1 = max(0, xs.min() - pad), min(L.w, xs.max() + pad + 1)
    yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
    return (slice(Y0, Y1), slice(X0, X1)), xx / SS + L.x0, yy / SS + L.y0


def _full(L, sl, arr):
    out = np.zeros((L.h, L.w), np.float32)
    out[sl] = arr
    return out


def cells(L, size, angle=0.0, stretch=1.0, seed=3, jitter=0.8, m=None):
    """Jittered Voronoi cells: returns (edge distance f2 - f1 in cell units, local offset along `angle`
    from the cell centre, per-cell random value 0..1), computed inside mask m's box."""
    sl, xx, yy = _sub(L, m)
    r = math.radians(angle)
    cs, sn = math.cos(r), math.sin(r)
    u = (xx * cs + yy * sn) / (size * stretch)
    v = (-xx * sn + yy * cs) / size
    iu, iv = np.floor(u), np.floor(v)
    f1 = np.full(u.shape, 9.0, np.float32)
    f2 = np.full(u.shape, 9.0, np.float32)
    off = np.zeros_like(u)
    rid = np.zeros_like(u)

    def hsh(a, b, k):
        x = np.sin(a * 127.1 + b * 311.7 + k * 74.7 + seed * 13.13) * 43758.5453
        return x - np.floor(x)
    for du in (-1, 0, 1):
        for dv in (-1, 0, 1):
            cu, cv = iu + du, iv + dv
            px = cu + 0.5 + (hsh(cu, cv, 1) - 0.5) * jitter
            py = cv + 0.5 + (hsh(cu, cv, 2) - 0.5) * jitter + (cu % 2) * 0.0
            dx, dy = u - px, v - py
            d = np.sqrt(dx * dx + dy * dy)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            off = np.where(closer, dx, off)
            rid = np.where(closer, hsh(cu, cv, 3), rid)
            f1 = np.where(closer, d, f1)
    return _full(L, sl, f2 - f1), _full(L, sl, off), _full(L, sl, rid)


def scales_bump(L, size, angle=0, depth=1.0, stretch=1.0, seed=3, overlap=1.1, m=None):
    """Organic overlapping scales about `size` canvas px across; `angle` is the direction the scale tips
    point (degrees, 0 = right, 90 = down). Returns (height in working px, per-scale random 0..1)."""
    e, off, rid = cells(L, size, angle, stretch, seed, m=m)
    dome = np.clip(e / 0.22, 0, 1) ** 0.4
    lean = np.clip(0.5 + off * overlap, 0, 1)        # each scale rises toward its tip
    return dome * (0.35 + 0.65 * lean) * size * SS * 0.13 * depth, rid


def path_coords(L, path, n=80, m=None):
    """For each pixel (inside mask m's box): distance along the path (s) and signed distance from it (u)."""
    sl, xx, yy = _sub(L, m)
    pts, t = resample(catmull(path, n=12), n)
    P = np.array(pts, np.float32)
    best = np.full(xx.shape, 1e12, np.float32)
    s = np.zeros_like(xx)
    u = np.zeros_like(xx)
    for i in range(len(P)):
        j = min(i + 1, len(P) - 1)
        k = max(i - 1, 0)
        tx, ty = P[j, 0] - P[k, 0], P[j, 1] - P[k, 1]
        ln = math.hypot(tx, ty) or 1
        dx, dy = xx - P[i, 0], yy - P[i, 1]
        d = dx * dx + dy * dy
        upd = d < best
        best = np.where(upd, d, best)
        s = np.where(upd, t[i], s)
        u = np.where(upd, (dx * (-ty) + dy * tx) / ln, u)
    return _full(L, sl, s), _full(L, sl, u)


# ------------------------------------------------------------------ rig assembly

class Rig:
    """Collects parts in any order (parents are sorted first on save)."""

    def __init__(self, rid, canvas, feet, kind, flat_size=512):
        self.id, self.canvas, self.feet, self.kind, self.flat_size = rid, canvas, feet, kind, flat_size
        self.parts = []

    def add(self, name, layer, parent, role, pivot, z, blend="normal"):
        if isinstance(layer, Layer):
            a = layer.a
            W, H = self.canvas
            sides = [("top", a[0], layer.y0 > 0), ("bottom", a[-1], layer.y1 < H),
                     ("left", a[:, 0], layer.x0 > 0), ("right", a[:, -1], layer.x1 < W)]
            cut = [n for n, e, inner in sides if inner and e.max() > 0.04]
            if cut:
                print(f"  ! {self.id}/{name}: layer box {layer.x0, layer.y0, layer.x1, layer.y1} cuts {cut}")
        img = layer if isinstance(layer, Image.Image) else layer.image()
        self.parts.append(dict(name=name, img=img, parent=parent, role=role, pivot=pivot, z=z, blend=blend))

    def get(self, name):
        return next(p for p in self.parts if p["name"] == name)

    def contact_shadow(self, name, onto, k=0.45, r=10, dx=3, dy=8):
        """Bakes a soft shadow of part `name` onto the parts listed in `onto` into `name`'s own layer
        (under its pixels), so it moves with the part."""
        p = self.get(name)
        a = np.asarray(p["img"].getchannel("A"), np.float32) / 255
        under = np.zeros_like(a)
        for o in onto:
            under = np.maximum(under, np.asarray(self.get(o)["img"].getchannel("A"), np.float32) / 255)
        sh = np.roll(np.roll(a, int(dy), 0), int(dx), 1)
        sh = blur(sh, r) * under * (1 - a) * k
        arr = np.asarray(p["img"], np.float32) / 255
        out_a = arr[..., 3] + sh * (1 - arr[..., 3])
        rgb = arr[..., :3] * arr[..., 3:4] + np.array([0.05, 0.02, 0.03]) * (sh * (1 - arr[..., 3]))[..., None]
        rgb = rgb / np.maximum(out_a, 1e-4)[..., None]
        p["img"] = Image.fromarray((np.dstack([rgb, out_a]) * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA")

    def save(self, sheet_dir=None):
        rb = rigmod.RigBuilder(self.id, self.canvas, feet=self.feet, facing="left", kind=self.kind)
        done = set([""])
        todo = list(self.parts)
        while todo:
            nxt = [p for p in todo if p["parent"] in done]
            assert nxt, [p["name"] for p in todo]
            for p in nxt:
                rb.add(p["name"], p["img"], p["parent"], p["role"], p["pivot"], p["z"], p["blend"])
                done.add(p["name"])
            todo = [p for p in todo if p["name"] not in done]
        self.rb = rb
        rb.save(flat=f"sprites/enemies/{self.id}.png", flat_size=self.flat_size)
        if sheet_dir:
            rigmod.pose_sheet(self.id, os.path.join(sheet_dir, f"pose_{self.id}.png"),
                              scale=0.4 if self.canvas[0] <= 1100 else 0.25)


# ------------------------------------------------------------------ shared painting bits

def ramp(t, stops):
    t = np.clip(t, 0, 1)
    xs = [s[0] for s in stops]
    out = np.zeros(np.shape(t) + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(t, xs, [s[1][c] for s in stops])
    return out


FIRE = [(0.0, (0.16, 0.02, 0.02)), (0.25, (0.60, 0.07, 0.02)), (0.5, (1.0, 0.34, 0.04)),
        (0.72, (1.0, 0.64, 0.16)), (0.9, (1.0, 0.90, 0.55)), (1.0, (1.0, 0.98, 0.90))]


def fire(t):
    return ramp(t, FIRE)


class Frame:
    """Local design coordinates (u forward, v down, in units of `s` canvas px) placed at `o`, turned by
    `ang` degrees; flip=True makes +u point left (monsters face left)."""

    def __init__(self, o, s, ang=0.0, flip=True):
        self.o, self.s = o, s
        r = math.radians(ang)
        self.cs, self.sn = math.cos(r), math.sin(r)
        self.fx = -1 if flip else 1

    def __call__(self, u, v):
        x, y = self.fx * u * self.s, v * self.s
        return (self.o[0] + x * self.cs - y * self.sn, self.o[1] + x * self.sn + y * self.cs)

    def P(self, pts):
        return [self(u, v) for u, v in pts]


def bbox(pts, pad=0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def skin(L, m, base, r, size, angle=90, seed=1, var=0.14, depth=1.0, stretch=1.0, spec=0.32, shin=14, **kw):
    """Scaly hide: organic overlapping scales with per-scale colour variation."""
    if m.max() <= 0:
        return m
    bump, rid = scales_bump(L, size, angle, depth, stretch, seed, m=m)
    col = np.asarray(base, np.float32) * (1 + (rid - 0.5) * var)[..., None]
    return L.paint(m, col, r=r, bump=bump, spec=spec, shin=shin, seed=seed, **kw)


def spike(L, base, tip, w, color, seed=1, glow=None, spec=0.55, r=None, lean=0.25, line=0.8):
    """A curved horn-like spike from the middle of its base (width w) to tip."""
    bx, by = base
    tx, ty = tip
    dx, dy = tx - bx, ty - by
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln, dx / ln
    mid = (bx + dx * 0.55 + nx * ln * lean * 0.3, by + dy * 0.55 + ny * ln * lean * 0.3)
    m = L.tube([base, mid, tip], [w, w * 0.55, 0.0], caps=False)
    m = np.maximum(m, L.ellipse(bx, by, w * 0.5, w * 0.5))
    L.paint(m, color, r=r or w * 0.45, spec=spec, shin=26, seed=seed, tex=0.06, line=line)
    if glow is not None:
        L.glow(tx, ty, w * 0.9, glow, 0.9, extend=0.3)
    return m


def horn(L, ctrl, w, color, seed=1, rings=0.0, tipc=None, spec=0.7, widths=None):
    """A long tapering horn along a spline, with optional growth rings and a tip colour."""
    widths = widths or [w, w * 0.82, w * 0.55, w * 0.28, 0.0]
    m = L.tube(ctrl, widths, caps=False)
    m = np.maximum(m, L.ellipse(ctrl[0][0], ctrl[0][1], w * 0.5, w * 0.5))
    bump = None
    col = np.asarray(color, np.float32)
    if rings or tipc is not None:
        s, u = path_coords(L, ctrl, n=40, m=m)
        total = max(1.0, float(s.max()))
        if rings:
            bump = (np.sin(s / (w * 0.22) * 2 * math.pi) * 0.5 + 0.5) ** 3 * w * SS * 0.05 * rings
        if tipc is not None:
            col = lerp(col, np.asarray(tipc, np.float32), smooth(0.5, 1.0, s / total)[..., None])
    L.paint(m, col, r=w * 0.5, bump=bump, spec=spec, shin=30, seed=seed, tex=0.05)
    return m


def tooth(L, base, direction, length, w, color=(0.93, 0.86, 0.72), curve=0.15, spec=0.6, line=0.7):
    r = math.radians(direction)
    tip = (base[0] + math.cos(r) * length, base[1] + math.sin(r) * length)
    nx, ny = -math.sin(r), math.cos(r)
    mid = (base[0] + math.cos(r) * length * 0.5 + nx * length * curve,
           base[1] + math.sin(r) * length * 0.5 + ny * length * curve)
    m = L.tube([base, mid, tip], [w, w * 0.6, 0], caps=False)
    L.paint(m, np.asarray(color, np.float32), r=w * 0.5, spec=spec, shin=24, tex=0.04, line=line, rim=0.6)
    return m


def claw(L, base, direction, length, w, color=(0.10, 0.08, 0.09), curl=0.35, spec=0.9):
    return tooth(L, base, direction, length, w, color=color, curve=curl, spec=spec, line=0.9)


def scallop(a, b, toward, depth, n=10):
    """Points along a curve from a to b bowed toward point `toward` by depth x |ab|."""
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    tx, ty = toward[0] - mx, toward[1] - my
    tl = math.hypot(tx, ty) or 1
    tx, ty = tx / tl, ty / tl
    return [(a[0] + (b[0] - a[0]) * i / n + tx * math.sin(math.pi * i / n) * depth * ln,
             a[1] + (b[1] - a[1]) * i / n + ty * math.sin(math.pi * i / n) * depth * ln) for i in range(n + 1)]


def embers(L, box, n, seed, size=(1.5, 4.5), color=(1.0, 0.55, 0.15), k=1.0):
    """Tiny glowing sparks inside box (canvas px)."""
    rng = np.random.default_rng(seed)
    for _ in range(n):
        x, y = rng.uniform(box[0], box[2]), rng.uniform(box[1], box[3])
        r = rng.uniform(*size)
        m = L.ellipse(x, y, r, r * rng.uniform(0.6, 1.0), rng.uniform(0, 180))
        L.flat(m, fire(np.full(m.shape, rng.uniform(0.75, 1.0)))[..., :3] if False else np.array(
            [1.0, rng.uniform(0.7, 0.95), rng.uniform(0.35, 0.6)], np.float32), alpha=rng.uniform(0.7, 1.0) * k)
        L.glow(x, y, r * 4, np.asarray(color, np.float32), 0.5 * k, extend=0.5)


def wing(L, shoulder, elbow, wrist, tips, back, mem_c, bone_c, seed=1, bone_w=46, glow=1.0, far=False,
         tears=(), thumb=True, depth=0.16, veins=3, edge_c=(1.0, 0.55, 0.16)):
    """A bat wing: arm shoulder-elbow-wrist, fingers from the wrist to each tip, membrane scalloped between
    the tips and back to the body at `back`. The membrane is dark leather, backlit by ember light
    (translucent toward its trailing edge, which smoulders), with veins branching off the fingers."""
    outline = [shoulder, elbow, wrist]
    chain = [tips[0]] + list(tips[1:]) + [back]
    outline.append(tips[0])
    for a, b in zip(chain[:-1], chain[1:]):
        outline += scallop(a, b, wrist, depth if b is not back else depth * 0.6, n=16)[1:]
    outline.append(shoulder)
    mem = L.poly(outline)
    for t in tears:  # ragged holes and notches
        mem = mem * (1 - L.blob(t, n=6))
    arm = np.maximum(L.tube([shoulder, elbow], [bone_w * 1.3, bone_w * 0.95]),
                     L.tube([elbow, wrist], [bone_w * 0.95, bone_w * 0.7]))
    bones = arm.copy()
    fingers = []
    for i, t in enumerate(tips):
        dx, dy = t[0] - wrist[0], t[1] - wrist[1]
        ln = math.hypot(dx, dy) or 1
        bend = 0.035 if i else 0.015
        mid = ((wrist[0] + t[0]) / 2 - dy * bend, (wrist[1] + t[1]) / 2 + dx * bend)
        fw = bone_w * (0.55 if i == 0 else 0.4)
        f = L.tube([wrist, mid, t], [fw, fw * 0.62, fw * 0.22])
        fingers.append((f, mid, t))
        bones = np.maximum(bones, f)
    # veins: dark branching lines from the fingers out toward the trailing edge
    rng = np.random.default_rng(seed)
    vein = np.zeros_like(mem)
    for (f, mid, t) in fingers[1:] + fingers[:1]:
        for j in range(veins):
            k = 0.3 + 0.55 * (j + 0.5) / veins
            px = wrist[0] + (t[0] - wrist[0]) * k
            py = wrist[1] + (t[1] - wrist[1]) * k
            for side in (-1, 1):
                dx, dy = t[0] - wrist[0], t[1] - wrist[1]
                ln = math.hypot(dx, dy) or 1
                nx, ny = -dy / ln * side, dx / ln * side
                L1 = ln * rng.uniform(0.2, 0.34)
                pts = [(px, py)]
                cx, cy = px, py
                for q in range(4):
                    cx += (nx * 0.75 + dx / ln * 0.55) * L1 / 4 + rng.normal(0, L1 * 0.025)
                    cy += (ny * 0.75 + dy / ln * 0.55) * L1 / 4 + rng.normal(0, L1 * 0.025)
                    pts.append((cx, cy))
                vein = np.maximum(vein, L.tube(catmull(pts, n=6), [bone_w * 0.12, bone_w * 0.08, bone_w * 0.02], caps=False) * 0.8)
    vein *= mem
    # membrane: sags between the bones, translucent, lit from behind by the lair's fire
    ed = dist(mem, 120 * SS) / SS
    sag = blur(bones, 30 * SS) * 24 * SS
    nz = noise(L.h, L.w, 50 * SS, seed=seed, octaves=4)
    wr = noise(L.h, L.w, 10 * SS, seed=seed + 5, octaves=3)
    back_t = np.clip(1 - ed / 130.0, 0, 1) ** 2.2 * (0.6 + 0.4 * nz) * glow
    near_bone = blur(bones, 18 * SS)
    back_t = back_t * (1 - 0.7 * np.clip(near_bone * 1.5, 0, 1)) * (1 - vein * 0.85)
    emis = fire(0.1 + back_t * 0.65) * (back_t * (0.6 if far else 0.8))[..., None] + fire(0.2)[None, None] * 0.12 * nz[..., None]
    col = np.asarray(mem_c, np.float32) * (0.9 + 0.2 * nz)[..., None] * (1 - vein * 0.5)[..., None]
    L.paint(mem, col, r=10, bump=sag + (wr - 0.5) * 3 * SS - vein * 3 * SS, spec=0.25, shin=12, tex=0.05,
            emissive=emis, rim=0.3, line=0.6, seed=seed, keyk=0.6, under=1.2)
    # smouldering trailing edge
    edge = np.clip(1 - ed / 4.0, 0, 1) * mem * (1 - np.clip(blur(bones, 4 * SS) * 2, 0, 1))
    hot = edge * (0.5 + 0.5 * noise(L.h, L.w, 14 * SS, seed=seed + 9, octaves=2)) * glow
    L.add_light(hot * 1.5, np.asarray(edge_c, np.float32), extend=0.9)
    L.add_light(blur(hot, 7 * SS) * 1.1, np.array([1.0, 0.3, 0.06], np.float32), extend=0.7)
    # the bones
    bc = np.asarray(bone_c, np.float32)
    L.ao(bones, 0.45, 6, 3, 6)
    for f, mid, t in fingers:
        L.paint(f, bc, r=bone_w * 0.28, spec=0.5, shin=22, seed=seed + 2, tex=0.08, line=0.8, top=(bc * 2.2, 0.5))
    skin(L, arm, bc, bone_w * 0.6, 9, angle=0, seed=seed + 4, spec=0.45, top=(bc * 2.2, 0.5))
    for p in (elbow, wrist):
        L.paint(L.ellipse(p[0], p[1], bone_w * 0.5, bone_w * 0.44), bc * 1.08, r=bone_w * 0.4, spec=0.5, shin=20,
                seed=seed + 5, top=(bc * 2.2, 0.5))
    if thumb:
        dx, dy = wrist[0] - elbow[0], wrist[1] - elbow[1]
        a = math.degrees(math.atan2(dy, dx))
        claw(L, (wrist[0] + dx * 0.04, wrist[1] + dy * 0.04), a - 40, bone_w * 1.3, bone_w * 0.45, curl=0.35)
    for f, mid, t in fingers[1:]:
        dx, dy = t[0] - mid[0], t[1] - mid[1]
        claw(L, (t[0] - dx * 0.03, t[1] - dy * 0.03), math.degrees(math.atan2(dy, dx)) + 15, bone_w * 0.5,
             bone_w * 0.22, curl=0.3)
    return mem, bones


# ------------------------------------------------------------------ limbs and tails

def limb(L, ctrl, widths, color, seed, size=13, angle=90, **kw):
    m = L.tube(ctrl, widths)
    skin(L, m, color, max(widths) * 0.5, size, angle=angle, seed=seed, **kw)
    return m


def foot(L, ankle, tips, color, w, seed, claw_c=(0.09, 0.07, 0.08), claw_k=1.0, **kw):
    """Toes from the ankle to each tip (thick knuckled tubes), a claw hooking down from each."""
    for i, t in enumerate(tips):
        mid = ((ankle[0] * 0.45 + t[0] * 0.55), (ankle[1] * 0.45 + t[1] * 0.55) - w * 0.12)
        m = L.tube([ankle, mid, t], [w, w * 0.62, w * 0.48])
        skin(L, m, color * (1.0 - 0.06 * i), w * 0.35, 8, angle=0, seed=seed + i, **kw)
        dx, dy = t[0] - mid[0], t[1] - mid[1]
        a = math.degrees(math.atan2(dy, dx))
        claw(L, (t[0] - dx * 0.08, t[1] - dy * 0.08), a + (25 if dx < 0 else -25) * (1 if dy >= -5 else 0.4),
             w * 0.9 * claw_k, w * 0.42 * claw_k, curl=0.35 if dx < 0 else -0.35)


def tail_chain(R, prefix, ctrl, widths, n, parent, z0, color, seed, spikes=None, layer_pad=120, tip=None,
               glow_seams=False, scale=15, top=None):
    """A tail cut into n segments (prefix_1 ... prefix_n, role tail). Each segment starts a little before
    its joint (a rounded cap under the previous one). spikes: list of (s0, s1) arc-length ranges on which to
    raise spikes on the upper side. Returns the joint points."""
    path = catmull(ctrl, n=16)
    pts, t = resample(path, 400)
    total = t[-1]
    wk = np.interp(t / total, np.linspace(0, 1, len(widths)), widths)
    cuts = [0] + [int(400 * k / n) for k in range(1, n)] + [400]
    joints = []
    prev = parent
    for k in range(n):
        a, b = cuts[k], cuts[k + 1]
        ov = 0 if k == 0 else int(min(a, 400 * 0.6 * wk[a] / total * 1.0))
        sub = pts[a - ov:b + 1]
        sw = list(wk[a - ov:b + 1])
        box = bbox(sub, max(sw) * 0.5 + layer_pad)
        L = Layer(R.canvas, box)
        # spikes along the ridge of this segment
        if spikes:
            for (s0, s1, cnt, hmax) in spikes:
                for j in range(cnt):
                    ss = s0 + (s1 - s0) * (j + 0.5) / cnt
                    i = int(np.searchsorted(t, ss))
                    if not (a <= i < b):
                        continue
                    x, y = pts[i]
                    x2, y2 = pts[min(399, i + 3)]
                    dx, dy = x2 - x, y2 - y
                    ln = math.hypot(dx, dy) or 1
                    nx, ny = dy / ln, -dx / ln   # left normal = the upper side for a tail running right
                    if ny > 0:
                        nx, ny = -nx, -ny
                    hw = wk[i] * 0.5
                    h = hmax * (1 - 0.5 * ss / total)
                    base = (x + nx * hw * 0.7, y + ny * hw * 0.7)
                    tipp = (base[0] + nx * h + dx / ln * h * 0.7, base[1] + ny * h + dy / ln * h * 0.7)
                    spike(L, base, tipp, max(10, wk[i] * 0.32), HORN, seed=seed + j, lean=0.3)
        if k == n - 1 and tip:
            tip(L, pts, wk)
        m = L.tube(sub, sw)
        skin(L, m, color, max(sw) * 0.5, scale, angle=0, seed=seed + k * 7, rim=1.3, top=top)
        name = f"{prefix}_{k + 1}"
        joint = pts[a]
        joints.append(joint)
        R.add(name, L, prev, "tail", joint, z0 - k)
        prev = name
    return joints



# ------------------------------------------------------------------ Ashwing (final boss)

AW = (1920, 1440)
ASH = C("#2e2a2c")
ASH_D = C("#1f1c20")
ASH_DUST = C("#8c8480")
PLATE = C("#3c2e2b")
MEM = C("#3a1618")
MEM_D = C("#2c1216")
HORN = C("#17141b")
BONE_TEETH = (0.95, 0.88, 0.74)
EMBER = np.array([1.0, 0.45, 0.1], np.float32)

AW_HEAD = [(-0.1, -0.02), (-0.04, -0.17), (0.08, -0.25), (0.22, -0.29), (0.34, -0.268), (0.44, -0.195),
           (0.58, -0.162), (0.76, -0.148), (0.9, -0.134), (0.99, -0.095), (1.03, -0.035), (1.0, 0.028),
           (0.84, 0.052), (0.62, 0.062), (0.44, 0.072), (0.32, 0.095), (0.24, 0.17), (0.1, 0.22), (-0.02, 0.2),
           (-0.11, 0.1)]
AW_MOUTH_UP = [(0.3, 0.09), (0.44, 0.072), (0.62, 0.062), (0.84, 0.052), (0.99, 0.03)]
AW_JAW = [(0.08, 0.12), (0.28, 0.1), (0.5, 0.09), (0.7, 0.08), (0.86, 0.074), (0.955, 0.088), (0.945, 0.14),
          (0.8, 0.172), (0.6, 0.2), (0.4, 0.228), (0.22, 0.235), (0.05, 0.19)]
AW_JAW_UP = [(0.28, 0.1), (0.5, 0.09), (0.7, 0.08), (0.86, 0.074), (0.955, 0.088)]
AW_HINGE = (0.2, 0.14)
AW_OPEN = 20


def aw_frame():
    return Frame((705, 452), 440, -16)


def _dir(F, u, v, du, dv):
    a, b = F(u, v), F(u + du, v + dv)
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def fx_window(G, feather=40):
    """Fades an fx layer to nothing at its box edges."""
    xx, yy = G.grid()
    k = (smooth(G.x0, G.x0 + feather, xx) * smooth(G.x1, G.x1 - feather, xx) *
         smooth(G.y0, G.y0 + feather, yy) * smooth(G.y1, G.y1 - feather, yy))
    G.rgb *= k[..., None]
    G.a *= k


def aw_head():
    F = aw_frame()
    s = F.s
    L = Layer(AW, fbox(F, 1.12, -0.85, -0.85, 0.45, 30))
    # far horn and the frill spikes behind the skull
    horn(L, F.P([(0.16, -0.22), (0.04, -0.46), (-0.18, -0.66), (-0.44, -0.74)]), 0.09 * s, HORN * 0.75, seed=21,
         rings=1.0, tipc=C("#4a1c14"))
    for (u0, v0), (u1, v1), w in (((0.04, 0.16), (-0.26, 0.3), 0.075), ((-0.02, 0.05), (-0.32, 0.1), 0.08),
                                  ((0.0, -0.07), (-0.28, -0.14), 0.075), ((0.14, 0.2), (-0.04, 0.38), 0.06),
                                  ((0.24, 0.2), (0.12, 0.36), 0.045)):
        spike(L, F(u0, v0), F(u1, v1), w * s, HORN * 1.2, seed=22, lean=-0.3)
    # skull and upper jaw
    m = L.blob(F.P(AW_HEAD), n=8)
    skin(L, m, ASH, 0.16 * s, 10, angle=_dir(F, 0, 0, -1, 0.2), seed=23, top=(ASH_DUST, 0.6), rim=1.3, spec=0.4)
    # snout ridge scutes, the brow ridge and the cheek plate
    for i, u in enumerate(np.linspace(0.55, 0.92, 6)):
        pm = L.ellipse(*F(u, -0.125 - 0.005 * i), 0.042 * s, 0.022 * s, -16)
        L.ao(pm * m, 0.4, 3, 1, 3)
        L.paint(pm * m, ASH * 1.3, r=0.02 * s, spec=0.6, shin=22, seed=24 + i, line=0.6, top=(ASH_DUST, 0.6))
    brow = L.tube(F.P([(0.1, -0.22), (0.27, -0.245), (0.4, -0.215), (0.51, -0.16)]),
                  [0.085 * s, 0.08 * s, 0.06 * s, 0.02 * s])
    L.ao(brow, 0.6, 8, 0, 7)
    skin(L, brow, ASH * 1.2, 0.04 * s, 9, angle=0, seed=25, top=(ASH_DUST, 0.75), spec=0.5)
    for (u0, v0), (u1, v1) in (((0.16, -0.26), (-0.02, -0.37)), ((0.27, -0.265), (0.12, -0.38)),
                               ((0.36, -0.24), (0.26, -0.33))):
        spike(L, F(u0, v0), F(u1, v1), 0.045 * s, HORN, seed=26, lean=-0.4)
    ck = L.blob(F.P([(0.02, 0.03), (0.2, 0.0), (0.3, 0.07), (0.25, 0.15), (0.1, 0.19), (-0.02, 0.12)]), n=3)
    L.ao(ck, 0.45, 6, 2, 5)
    skin(L, ck, ASH * 1.1, 0.025 * s, 13, angle=160, seed=27, top=(ASH_DUST, 0.55), spec=0.5, r2=0.1 * s, k2=0.4)
    # the eye: molten gold under the brow, a slit pupil, light spilling onto the scales
    ex, ey = F(0.385, -0.15)
    L.paint(L.ellipse(ex, ey, 0.078 * s, 0.045 * s, -20), C("#120a0c"), r=0.02 * s, rim=0, spec=0.0, line=0.5)
    eye = L.poly(F.P([(0.325, -0.145), (0.365, -0.18), (0.425, -0.185), (0.462, -0.155), (0.425, -0.13),
                      (0.365, -0.126)]))
    rr = L.radial(*F(0.4, -0.155), 0.075 * s, power=1.0)
    L.flat(eye, fire(0.6 + 0.4 * rr))
    pup = L.poly(F.P([(0.398, -0.184), (0.407, -0.156), (0.398, -0.127), (0.389, -0.156)]))
    L.flat(pup, np.array([0.15, 0.03, 0.0], np.float32), alpha=0.92)
    L.glow(ex, ey, 0.1 * s, np.array([1.0, 0.5, 0.1], np.float32), 0.8, extend=0.0)
    L.glow(*F(0.37, -0.165), 0.018 * s, np.array([1.0, 1.0, 0.9], np.float32), 0.9, extend=0.0)
    # nostril breathing smoke-light
    nx_, ny_ = F(0.935, -0.075)
    L.paint(L.ellipse(nx_, ny_, 0.032 * s, 0.014 * s, -34), C("#0c0708"), r=0.01 * s, rim=0, line=0.3)
    L.glow(nx_, ny_, 0.05 * s, EMBER, 0.8, extend=0.2)
    # near horns: a great swept obsidian horn, ringed, its tip still ember-red; a shorter one below
    horn(L, F.P([(0.02, -0.08), (-0.14, -0.2), (-0.36, -0.24)]), 0.075 * s, HORN, seed=29, rings=1.0,
         tipc=C("#3a1812"))
    horn(L, F.P([(0.12, -0.19), (-0.06, -0.37), (-0.32, -0.5), (-0.64, -0.47)]), 0.125 * s, HORN, seed=28,
         rings=1.2, tipc=C("#5a2014"))
    # upper teeth, fangs at the front
    for u in np.linspace(0.36, 0.96, 13):
        edge_v = np.interp(u, [0.3, 0.44, 0.62, 0.84, 0.99], [0.09, 0.072, 0.062, 0.052, 0.03])
        fang = abs(u - 0.86) < 0.03 or abs(u - 0.51) < 0.03
        ln = (0.09 if fang else 0.045) * s
        tooth(L, F(u, edge_v - 0.014), _dir(F, u, edge_v, 0.02, 1), ln, (0.028 if fang else 0.018) * s,
              BONE_TEETH, curve=-0.12)
    # fire light from the mouth on the underside of the upper jaw
    L.add_light(L.radial(*F(0.45, 0.14), 0.36 * s, 1.6) * 0.8 * m, EMBER)
    return L, F


def aw_jaw(open_deg=AW_OPEN, extra=24):
    """Lower jaw with the inside of the mouth on the same layer (drawn first): the mouth wedge reaches up
    under the upper jaw, so opening the jaw further still shows throat, not a hole."""
    F = aw_frame()
    s = F.s
    hinge = F(*AW_HINGE)
    L = Layer(AW, fbox(F, 1.15, -0.4, -0.15, 0.65, 30))

    def J(pts, extra_deg=0):
        return rot(F.P(pts), hinge, -open_deg + extra_deg)
    head_m = L.blob(F.P(AW_HEAD), n=8)
    lip = J(AW_JAW_UP)
    wedge = L.blob([hinge] + F.P(AW_MOUTH_UP) + lip[::-1], n=3)
    closed = J(AW_JAW_UP, extra)
    wedge = np.maximum(wedge, L.blob([hinge] + closed + lip[::-1], n=3) * head_m)
    wedge = np.maximum(wedge, L.blob(F.P([(0.14, 0.08), (0.3, 0.06), (0.3, 0.16), (0.14, 0.18)]), n=3))
    t = L.radial(*F(0.26, 0.14), 0.62 * s, power=1.0)
    L.flat(wedge, fire(0.08 + 0.92 * t ** 1.4))
    tg = L.tube(J([(0.2, 0.15), (0.45, 0.13), (0.68, 0.115)], -4), [0.085 * s, 0.07 * s, 0.03 * s])
    L.paint(tg * wedge, C("#6a1a18"), r=0.03 * s, spec=0.7, shin=20, rim=0.2, line=0.4,
            light=fire(0.3 + 0.5 * t) * 0.8)
    nz = noise(L.h, L.w, 16 * SS, seed=41, octaves=3)
    fl = np.clip(t * 1.4 + (nz - 0.5) * 0.9 - 0.3, 0, 1) * wedge
    L.add_light(fl * 1.1, np.array([1.0, 0.85, 0.5], np.float32))
    # the jaw itself
    m = L.blob(J(AW_JAW), n=8)
    L.ao(m, 0.5, 6, 0, -4)
    skin(L, m, ASH, 0.07 * s, 10, angle=_dir(F, 0, 0, -1, 0), seed=31, top=(ASH_DUST, 0.35), spec=0.4)
    for u in (0.3, 0.5, 0.68):
        v = np.interp(u, [0.22, 0.6, 0.945], [0.235, 0.2, 0.14])
        b = J([(u, v - 0.012)])[0]
        tp = J([(u - 0.11, v + 0.085)])[0]
        spike(L, b, tp, 0.04 * s, HORN, seed=32, lean=0.3)
    for u in np.linspace(0.33, 0.92, 11):
        v = np.interp(u, [0.28, 0.5, 0.7, 0.86, 0.955], [0.1, 0.09, 0.08, 0.074, 0.088])
        fang = abs(u - 0.8) < 0.03
        b = J([(u, v + 0.014)])[0]
        a = _dir(F, u, v, 0, -1) - open_deg
        tooth(L, b, a, (0.08 if fang else 0.042) * s, (0.026 if fang else 0.017) * s, BONE_TEETH, curve=0.1)
    L.add_light(L.radial(*J([(0.45, 0.1)])[0], 0.36 * s, 1.5) * 0.9 * np.maximum(m, 0), EMBER)
    return L, hinge


def plates(L, m, path, halfw, size, seed, heat=None, glow=1.0, color=PLATE, r=50):
    """Overlapping belly plates across a band along `path` (inside m), their seams glowing with inner fire.
    halfw: half width of the band (number or (s positions, widths)). heat(s) -> 0..1 how hot each seam is."""
    s, u = path_coords(L, path, m=m)
    if isinstance(halfw, tuple):
        hw = np.interp(s, *halfw)
    else:
        hw = halfw
    band = smooth(hw + 6, hw - 14, np.abs(u)) * m
    f = (s / size) % 1.0
    # each plate bulges and its lower edge laps over the next
    prof = np.clip(np.minimum(f / 0.1, (1 - f) / 0.9), 0, 1) ** 0.7
    across = np.sqrt(np.clip(1 - (u / np.maximum(hw, 1)) ** 2, 0, 1))
    seam = np.exp(-(np.minimum(f, 1 - f) / 0.06) ** 2) * smooth(1.0, 0.7, np.abs(u) / np.maximum(hw, 1))
    ht = heat(s) if heat else 1.0
    em = fire(0.35 + 0.65 * seam * ht) * (seam * ht * glow * 1.4)[..., None]
    L.ao(band, 0.35, 6, 0, 3)
    L.paint(band, color * (0.85 + 0.25 * prof)[..., None], r=r, bump=(prof * 8 + across * 10) * SS, spec=0.55,
            shin=18, seed=seed, emissive=em, line=0.5, top=(color * 2.0, 0.3))
    L.add_light(blur(seam * ht * band, 12 * SS) * 0.8 * glow, EMBER)
    return band


def aw_neck():
    L = Layer(AW, (560, 330, 1260, 1030))
    ctrl = [(1100, 940), (1045, 780), (975, 630), (880, 505), (775, 445), (690, 440)]
    widths = [300, 240, 195, 172, 165, 160]
    crest = [(1170, 800), (1110, 670), (1035, 545), (930, 440), (820, 385), (760, 380)]
    pts, _ = resample(catmull(crest, n=10), 8)
    for i, (x, y) in enumerate(pts[1:]):
        h = 112 - i * 8
        spike(L, (x - 14, y + 20), (x + h * 0.8, y - h * 0.5), 54 - i * 3, HORN, seed=50 + i, lean=0.35,
              glow=EMBER if i % 2 == 0 else None)
    m = L.tube(ctrl, widths)
    skin(L, m, ASH, 100, 15, angle=60, seed=51, top=(ASH_DUST, 0.6), rim=1.4, spec=0.4)
    throat = [(1010, 980), (962, 820), (900, 680), (812, 565), (722, 520)]
    plates(L, m, throat, (np.array([0, 300, 560]), np.array([100, 88, 74])), 58, 52,
           heat=lambda s: smooth(150, 520, s) * 0.9 + 0.1)
    L.feather((1100, 940), -112, 20, 120)
    return L


def aw_body():
    L = Layer(AW, (860, 600, 1640, 1300))
    back = [(1190, 690), (1330, 745), (1445, 835), (1530, 955)]
    pts, _ = resample(catmull(back, n=10), 5)
    for i, (x, y) in enumerate(pts):
        h = 100 - i * 8
        spike(L, (x - 10, y + 22), (x + h * 0.85, y - h * 0.55), 56 - i * 4, HORN, seed=60 + i, lean=0.35,
              glow=EMBER if i % 2 else None)
    body = [(1010, 690), (1160, 672), (1310, 728), (1450, 828), (1545, 958), (1565, 1090), (1500, 1190),
            (1360, 1228), (1200, 1210), (1060, 1145), (962, 1035), (918, 905), (942, 772)]
    m = L.blob(body)
    skin(L, m, ASH, 70, 20, angle=40, seed=61, top=(ASH_DUST, 0.6), rim=1.4, spec=0.4, r2=330, k2=0.4)
    belly = [(932, 790), (950, 960), (1030, 1100), (1170, 1185), (1330, 1218)]
    plates(L, m, belly, (np.array([0, 300, 700]), np.array([105, 130, 90])), 68, 62,
           heat=lambda s: smooth(0, 200, s) * smooth(780, 450, s))
    for seed, path in ((63, [(1250, 890), (1296, 955), (1286, 1035), (1305, 1080)]),
                       (64, [(1405, 950), (1432, 1022), (1420, 1080)])):
        c = L.tube(catmull(path, n=8), [7, 5, 2], caps=False)
        L.flat(c * m, np.array([1.0, 0.7, 0.3], np.float32))
        L.add_light(blur(c, 9 * SS) * m * 0.9, EMBER)
    return L


def aw_tail_tip(L, pts, wk):
    """An obsidian blade at the end of the tail, its edge glowing."""
    x, y = pts[-1]
    x0, y0 = pts[-14]
    a = math.degrees(math.atan2(y - y0, x - x0))
    blade = rot([(x - 14, y - 42), (x + 55, y - 16), (x + 118, y), (x + 55, y + 18), (x - 14, y + 40),
                 (x + 8, y)], (x, y), a)
    m = L.blob(blade, n=4)
    L.paint(m, HORN, r=16, spec=0.9, shin=34, seed=77, tex=0.05)
    ed = np.clip(1 - dist(m, 10 * SS) / (3.5 * SS), 0, 1) * m
    L.add_light(ed * 1.0, EMBER, extend=0.6)


def LB(canvas, pts, pad):
    return Layer(canvas, bbox(pts, pad))


def fbox(F, u0, v0, u1, v1, pad=0):
    return bbox(F.P([(u0, v0), (u1, v0), (u0, v1), (u1, v1)]), pad)


def float_embers(R, parent, spots, seed, z=60, n=7, spread=60):
    """Little clusters of drifting sparks (role float) around the creature."""
    for i, (x, y) in enumerate(spots):
        L = LB(R.canvas, [(x, y)], spread + 30)
        embers(L, (x - spread, y - spread, x + spread, y + spread), n, seed + i, size=(2.0, 5.0))
        R.add(f"ember_{i + 1}", L, parent, "float", (x, y), z + i)


def build_ashwing(sheet_dir=None):
    R = Rig("ashwing", AW, feet=(1180, 1392), kind="dragon", flat_size=768)

    R.add("body", aw_body(), "", "root", (1260, 1180), 20)

    # far wing, up and back to the right
    L = Layer(AW, (1120, 20, 1910, 880))
    wing(L, (1215, 730), (1365, 430), (1545, 175), [(1795, 72), (1855, 330), (1745, 545), (1548, 665)],
         (1375, 790), MEM_D, ASH_D, seed=81, bone_w=42, far=True, glow=0.9,
         tears=[[(1848, 250), (1878, 262), (1856, 282)]])
    R.add("wing_back", L, "body", "wing_back", (1215, 730), 2)

    tail_chain(R, "tail", [(1440, 1060), (1600, 1112), (1725, 1072), (1800, 972), (1812, 862), (1768, 772)],
               [200, 150, 105, 70, 42, 22], 4, "body", 10, ASH, 90,
               spikes=[(60, 700, 9, 58)], tip=aw_tail_tip, top=(ASH_DUST, 0.5))

    # far hind leg
    pts = [(1480, 1060), (1525, 1180), (1505, 1255)]
    L = LB(AW, pts, 110)
    limb(L, pts, [165, 135, 100], ASH_D, 101, keyk=0.8)
    R.add("leg_back_upper", L, "body", "leg_back_upper", (1480, 1070), 8)
    pts = [(1505, 1250), (1560, 1322), (1515, 1375)]
    L = LB(AW, pts + [(1420, 1400)], 90)
    foot(L, (1510, 1372), [(1428, 1394), (1455, 1400), (1490, 1403)], ASH_D, 34, 104, keyk=0.8)
    limb(L, pts, [100, 72, 66], ASH_D, 102, keyk=0.8)
    R.add("leg_back_lower", L, "leg_back_upper", "leg_back_lower", (1505, 1250), 7)

    # far foreleg, planted
    pts = [(1125, 845), (1088, 990), (1035, 1130)]
    L = LB(AW, pts, 130)
    limb(L, pts, [200, 165, 125], ASH_D, 111, keyk=0.8)
    R.add("arm_back_upper", L, "body", "arm_back_upper", (1120, 860), 12)
    pts = [(1035, 1130), (1003, 1250), (978, 1360)]
    L = LB(AW, pts + [(870, 1400)], 90)
    foot(L, (975, 1362), [(872, 1390), (900, 1400), (940, 1404)], ASH_D, 40, 114, keyk=0.8)
    limb(L, pts, [125, 98, 88], ASH_D, 112, keyk=0.8)
    R.add("arm_back_lower", L, "arm_back_upper", "arm_back_lower", (1035, 1130), 11)

    # near wing, up and forward over the head
    L = Layer(AW, (250, 30, 1270, 820))
    wing(L, (1050, 760), (1190, 470), (935, 190), [(330, 95), (340, 350), (600, 440), (840, 510)], (1000, 690),
         MEM, ASH, seed=82, bone_w=50, glow=1.0, tears=[[(333, 250), (360, 262), (336, 278)],
                                                        [(700, 462), (714, 432), (728, 468)]])
    R.add("wing_front", L, "body", "wing_front", (1050, 760), 24)

    R.add("neck", aw_neck(), "body", "torso", (1085, 890), 26)
    F = aw_frame()
    head, _ = aw_head()
    R.add("head", head, "neck", "head", F(0.0, 0.0), 30)
    jaw, hinge = aw_jaw()
    R.add("jaw", jaw, "head", "jaw", hinge, 29)

    # near hind leg: big thigh over the haunch, knee forward, hock back, foot planted
    pts = [(1270, 1225), (1345, 1310), (1305, 1372)]
    L = LB(AW, pts + [(1170, 1400)], 90)
    foot(L, (1300, 1368), [(1172, 1390), (1204, 1400), (1250, 1404)], ASH, 46, 124, claw_k=1.2)
    limb(L, pts, [140, 96, 84], ASH, 122, top=(ASH_DUST, 0.4))
    leg_lower = L
    th_pts = [(1228, 992), (1380, 948), (1502, 1030), (1504, 1170), (1425, 1262), (1330, 1288), (1252, 1262),
              (1204, 1150)]
    L = LB(AW, th_pts, 60)
    th = L.blob(th_pts)
    skin(L, th, ASH, 60, 17, angle=60, seed=121, top=(ASH_DUST, 0.6), rim=1.4, spec=0.4, r2=220, k2=0.45)
    spike(L, (1282, 1240), (1232, 1292), 40, HORN, seed=123)
    R.add("leg_front_upper", L, "body", "leg_front_upper", (1365, 1080), 32)
    R.add("leg_front_lower", leg_lower, "leg_front_upper", "leg_front_lower", (1275, 1230), 31)

    # near foreleg raised, talons spread at the hero
    fa = [(935, 998), (858, 982), (790, 966), (752, 985), (758, 1040), (842, 1082), (940, 1110)]
    L = LB(AW, fa + [(600, 910), (690, 1120)], 50)
    hand = (770, 1005)
    foot(L, hand, [(645, 915), (612, 982), (632, 1055), (698, 1100)], ASH, 46, 134, claw_k=1.5)
    m = L.blob(fa)
    skin(L, m, ASH, 45, 12, angle=180, seed=132, top=(ASH_DUST, 0.5), rim=1.3, spec=0.45, r2=120, k2=0.3)
    for i, x in enumerate((905, 862, 820)):   # scutes along the top of the forearm
        y = 994 - (905 - x) * 0.2
        pm = L.ellipse(x, y + 4, 26, 15, -12)
        L.ao(pm, 0.4, 3, 1, 3)
        L.paint(pm * m, ASH * 1.3, r=12, spec=0.6, shin=22, seed=137 + i, line=0.6, top=(ASH_DUST, 0.6))
        spike(L, (x + 6, y - 4), (x + 34, y - 44 + i * 6), 22, HORN, seed=135 + i)
    R.add("arm_front_lower", L, "arm_front_upper", "arm_front_lower", (925, 1050), 35)
    ua = [(1012, 742), (1085, 790), (1070, 905), (1012, 1000), (962, 1085), (905, 1100), (880, 1030), (905, 930),
          (935, 830)]
    L = LB(AW, ua + [(1000, 1130)], 50)
    m = L.blob(ua)
    skin(L, m, ASH, 55, 16, angle=110, seed=131, top=(ASH_DUST, 0.6), rim=1.4, spec=0.4, r2=170, k2=0.4)
    spike(L, (930, 1080), (985, 1128), 44, HORN, seed=136)
    R.add("arm_front_upper", L, "body", "arm_front_upper", (1005, 860), 36)

    # fx: molten glows that pulse (additive)
    G = Layer(AW, fbox(F, 1.2, -0.3, -0.2, 0.75, 20))
    G.add_light(G.radial(*F(0.4, 0.16), 0.42 * F.s, 2.0) * 0.55, EMBER, clip_alpha=False, extend=0.8)
    fx_window(G)
    R.add("mouth_glow", G, "jaw", "fx", hinge, 50, blend="add")
    ex, ey = F(0.39, -0.155)
    G = Layer(AW, (ex - 90, ey - 90, ex + 90, ey + 90))
    G.add_light(G.radial(ex, ey, 0.14 * F.s, 2.0) * 0.8, np.array([1.0, 0.7, 0.2], np.float32), clip_alpha=False,
                extend=1.0)
    fx_window(G, 20)
    R.add("eye_glow", G, "head", "fx", (ex, ey), 51, blend="add")
    G = Layer(AW, (760, 640, 1480, 1340))
    s, u = path_coords(G, [(932, 790), (950, 960), (1030, 1100), (1170, 1185), (1330, 1218)])
    k = smooth(140, 30, np.abs(u)) * smooth(0, 200, s) * smooth(780, 450, s)
    G.add_light(k * 0.35, EMBER, clip_alpha=False, extend=1.0)
    fx_window(G)
    R.add("belly_glow", G, "body", "fx", (1260, 1180), 49, blend="add")

    float_embers(R, "body", [(420, 700), (1600, 700), (560, 1150), (1700, 1250)], 900)

    R.save(sheet_dir)
    return R



# ------------------------------------------------------------------ main

RIGS = {
    "ashwing": build_ashwing,
}

SHEET = os.environ.get("D5_SHEETS", "/tmp/claude-0/-home-claude-valthera-dragon-s-edge/"
                       "9d7e6e94-5ed4-51a7-95df-cdb7958efe3b/scratchpad/m8/d5")

if __name__ == "__main__":
    ids = sys.argv[1:] or list(RIGS)
    os.makedirs(SHEET, exist_ok=True)
    for rid in ids:
        t0 = time.time()
        RIGS[rid](SHEET)
        print(rid, f"{time.time() - t0:.1f}s")

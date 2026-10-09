#!/usr/bin/env python3
"""Valthera M8 UI kit v2 and painted skill icons (landscape 1280 x 720 design, drawn at 2x).

Usage:  python3 tools/art/ui_v2.py [kit|skills|sheet|all]     (default: all)

kit     -> assets/ui/v2/*.png   (dark slate + gold filigree HUD pieces, buttons, bars, menu icons)
skills  -> assets/icons/skills/<id>.png  (24 painted 256 x 256 skill icons, no frame)
sheet   -> contact sheet with a 1280 x 720 battle HUD mock-up (scratchpad m8/ui_sheet.png)

Everything is painted with numpy: shapes come from analytic signed distance fields or PIL masks,
metal is lit with a height field (bevels, tube shading, specular) from the upper left, surfaces get
multi-octave noise, and glows are added in premultiplied space so they survive on transparency.
Each piece is rendered at SS x its file size and downscaled with LANCZOS.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "assets", "ui", "v2")
SKILL_OUT = os.path.join(ROOT, "assets", "icons", "skills")
SCRATCH = "/tmp/claude-0/-home-claude-valthera-dragon-s-edge/9d7e6e94-5ed4-51a7-95df-cdb7958efe3b/scratchpad/m8"
SHEET = os.path.join(SCRATCH, "ui_sheet.png")
FONT = os.path.join(ROOT, "assets", "fonts", "Cinzel.ttf")
SS = 2

# 9-slice margins (left, top, right, bottom) in file pixels, reported and used by the mock-up.
MARGINS = {
    "hud_bar.png": (104, 72, 104, 24),
    "panel.png": (72, 72, 72, 72),
    "panel_parchment.png": (72, 72, 72, 72),
    "nameplate.png": (112, 44, 52, 44),
    "bar_frame.png": (20, 16, 20, 16),
    "bar_fill_hp.png": (6, 0, 6, 0),
    "bar_fill_mana.png": (6, 0, 6, 0),
    "bar_fill_rage.png": (6, 0, 6, 0),
    "bar_fill_energy.png": (6, 0, 6, 0),
    "bar_fill_enemy.png": (6, 0, 6, 0),
    "bar_fill_xp.png": (6, 0, 6, 0),
    "bar_back.png": (10, 10, 10, 10),
    "ribbon_button.png": (150, 50, 150, 50),
    "ribbon_button_pressed.png": (150, 50, 150, 50),
    "ribbon_button_disabled.png": (150, 50, 150, 50),
    "button.png": (36, 36, 36, 36),
    "button_pressed.png": (36, 36, 36, 36),
    "button_disabled.png": (36, 36, 36, 36),
    "button_gold.png": (36, 36, 36, 36),
    "button_gold_pressed.png": (36, 36, 36, 36),
    "tab.png": (30, 30, 30, 14),
    "tab_active.png": (30, 30, 30, 14),
    "turn_badge.png": (60, 30, 60, 30),
}


# ----------------------------------------------------------------------------------------------
# numeric helpers
# ----------------------------------------------------------------------------------------------

def _box(a, r, axis):
    if r < 1:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def gblur(a, sigma):
    """Gaussian-ish blur (3 box passes) in render pixels; works on 2D or HxWxC float arrays."""
    if sigma <= 0.3:
        return a.astype(np.float32)
    w = math.sqrt(12 * sigma * sigma / 3 + 1)
    r = max(1, int(round((w - 1) / 2)))
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box(out, r, 0)
        out = _box(out, r, 1)
    return out


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(stops, v):
    """stops: list of (pos, (r,g,b)); v: array -> HxWx3."""
    pos = [s[0] for s in stops]
    out = np.empty(v.shape + (3,), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(v, pos, [s[1][ch] for s in stops])
    return out


def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


GOLD = [(0.0, hx("#1c1206")), (0.18, hx("#4a3212")), (0.36, hx("#7d5a24")), (0.52, hx("#b38a3e")),
        (0.66, hx("#d9b262")), (0.8, hx("#f1d68f")), (0.92, hx("#fff0c4")), (1.0, hx("#ffffff"))]
GOLD_DIM = [(0.0, hx("#120c05")), (0.2, hx("#34240f")), (0.45, hx("#5e4520")), (0.65, hx("#8a6c38")),
            (0.85, hx("#b89a5c")), (1.0, hx("#e0cc98"))]
GOLD_HOT = [(0.0, hx("#3a2204")), (0.2, hx("#7a4d0e")), (0.4, hx("#c08a22")), (0.58, hx("#f0c044")),
            (0.74, hx("#ffe07a")), (0.88, hx("#fff4c0")), (1.0, hx("#ffffff"))]
IRON = [(0.0, hx("#07080a")), (0.25, hx("#15181c")), (0.45, hx("#262a30")), (0.62, hx("#3b4048")),
        (0.8, hx("#5d636c")), (0.92, hx("#8a9098")), (1.0, hx("#c8ccd2"))]
STEEL = [(0.0, hx("#101418")), (0.2, hx("#2a323a")), (0.4, hx("#56606a")), (0.6, hx("#8f99a3")),
         (0.78, hx("#c6ced6")), (0.9, hx("#eef2f6")), (1.0, hx("#ffffff"))]
GREY_GOLD = [(0.0, hx("#0c0c0c")), (0.25, hx("#262524")), (0.5, hx("#4c4a46")), (0.7, hx("#76726a")),
             (0.88, hx("#a29d92")), (1.0, hx("#cfcac0"))]

LIGHT = np.array([-0.52, -0.68, 0.52], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)


def fbm(h, w, scale, octaves=4, seed=0, persist=0.55):
    """Multi-octave value noise, roughly -1..1, feature size `scale` render px."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot, sc = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        gh, gw = max(2, int(h / sc) + 3), max(2, int(w / sc) + 3)
        g = rng.standard_normal((gh, gw)).astype(np.float32)
        im = Image.fromarray(g, "F").resize((int(gw * sc), int(gh * sc)), Image.BICUBIC)
        arr = np.asarray(im)
        oy, ox = rng.integers(0, max(1, arr.shape[0] - h)), rng.integers(0, max(1, arr.shape[1] - w))
        out += amp * arr[oy:oy + h, ox:ox + w]
        tot += amp
        amp *= persist
        sc = max(1.0, sc / 2)
    return out / tot


# ----------------------------------------------------------------------------------------------
# canvas
# ----------------------------------------------------------------------------------------------

class Canvas:
    """Premultiplied RGBA float canvas. Coordinates in file pixels; rendered at `ss` x."""

    def __init__(self, w, h, ss=SS):
        self.W, self.H, self.k = w, h, ss
        self.w, self.h = int(w * ss), int(h * ss)
        self.P = np.zeros((self.h, self.w, 3), np.float32)
        self.A = np.zeros((self.h, self.w), np.float32)
        ys = (np.arange(self.h, dtype=np.float32) + 0.5) / ss
        xs = (np.arange(self.w, dtype=np.float32) + 0.5) / ss
        self.X, self.Y = np.meshgrid(xs, ys)

    # ---- masks
    def fill(self, sd):
        return np.clip(0.5 - sd * self.k, 0, 1).astype(np.float32)

    def draw(self, fn):
        im = Image.new("L", (self.w, self.h), 0)
        d = ImageDraw.Draw(im)
        fn(d, self.k)
        return np.asarray(im, np.float32) / 255.0

    def poly(self, pts):
        k = self.k
        return self.draw(lambda d, _: d.polygon([(x * k, y * k) for x, y in pts], fill=255))

    def ellipse(self, box):
        k = self.k
        return self.draw(lambda d, _: d.ellipse([box[0] * k, box[1] * k, box[2] * k, box[3] * k], fill=255))

    def circle(self, cx, cy, r):
        return self.fill(np.hypot(self.X - cx, self.Y - cy) - r)

    def blur(self, a, sigma):
        return gblur(a, sigma * self.k)

    # ---- sdfs (file px)
    def sd_rrect(self, x0, y0, x1, y1, r):
        cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        qx = np.abs(self.X - cx) - hw + r
        qy = np.abs(self.Y - cy) - hh + r
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r

    def sd_chamfer(self, x0, y0, x1, y1, cut, r=0.0):
        """Rectangle with 45-degree chamfered corners (octagon), optionally rounded by r."""
        cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
        qx, qy = np.abs(self.X - cx), np.abs(self.Y - cy)
        d_box = np.maximum(qx - hw, qy - hh)
        d_cut = (qx + qy - (hw + hh - cut + r * 0.0)) / math.sqrt(2)
        return np.maximum(d_box, d_cut) - r

    def sd_circle(self, cx, cy, r):
        return np.hypot(self.X - cx, self.Y - cy) - r

    # ---- compositing
    def over(self, rgb, alpha):
        alpha = np.clip(alpha, 0, 1).astype(np.float32)
        rgb = np.asarray(rgb, np.float32)
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, 1, 3)
        self.P = rgb * alpha[..., None] + self.P * (1 - alpha[..., None])
        self.A = alpha + self.A * (1 - alpha)

    def under(self, rgb, alpha):
        alpha = np.clip(alpha, 0, 1).astype(np.float32)
        rgb = np.asarray(rgb, np.float32)
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, 1, 3)
        inv = 1 - self.A
        self.P = self.P + rgb * (alpha * inv)[..., None]
        self.A = self.A + alpha * inv

    def add(self, rgb, amount):
        """Additive light (also raises alpha so glows show on transparent pixels)."""
        rgb = np.asarray(rgb, np.float32)
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, 1, 3)
        amt = np.clip(amount, 0, None).astype(np.float32)
        glow = rgb * amt[..., None]
        self.P = self.P + glow
        self.A = np.clip(self.A + np.clip(glow.max(axis=2), 0, 1) * (1 - self.A), 0, 1)
        self.P = np.minimum(self.P, self.A[..., None] * 1.0 + 0.0)  # keep premultiplied valid

    def screen_on(self, rgb, amount):
        """Screen-blend light onto existing pixels only (alpha unchanged)."""
        rgb = np.asarray(rgb, np.float32)
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, 1, 3)
        a = self.A[..., None]
        s = np.clip(rgb * np.clip(amount, 0, 1)[..., None], 0, 1)
        straight = np.where(a > 1e-4, self.P / np.maximum(a, 1e-4), 0)
        straight = 1 - (1 - straight) * (1 - s)
        self.P = straight * a

    def mul(self, factor, mask=None):
        f = np.asarray(factor, np.float32)
        if f.ndim == 2:
            f = f[..., None]
        if mask is not None:
            f = 1 + (f - 1) * mask[..., None]
        self.P = self.P * f

    def cut(self, mask):
        """Erase where mask = 1."""
        keep = 1 - np.clip(mask, 0, 1)
        self.P *= keep[..., None]
        self.A *= keep

    def clip_to(self, mask):
        self.P *= mask[..., None]
        self.A *= mask

    def shadow(self, mask, dx=2, dy=3, sigma=3, opacity=0.6, color=(0, 0, 0)):
        sh = self.blur(self.shift(mask, dx, dy), sigma) * opacity
        self.over(np.array(color, np.float32), sh)

    def shift(self, a, dx, dy):
        dx, dy = int(round(dx * self.k)), int(round(dy * self.k))
        out = np.zeros_like(a)
        h, w = a.shape[:2]
        ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
        xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
        out[yd, xd] = a[ys, xs]
        return out

    def image(self):
        """Downscale (LANCZOS, premultiplied) and return an 8-bit RGBA PIL image at file size."""
        chans = []
        for arr in (self.P[..., 0], self.P[..., 1], self.P[..., 2], self.A):
            im = Image.fromarray(np.ascontiguousarray(arr, np.float32), "F")
            if self.k != 1:
                im = im.resize((self.W, self.H), Image.LANCZOS)
            chans.append(np.asarray(im))
        a = np.clip(chans[3], 0, 1)
        rgb = np.stack(chans[:3], -1)
        rgb = np.where(a[..., None] > 1e-4, rgb / np.maximum(a[..., None], 1e-4), 0)
        out = np.dstack([np.clip(rgb, 0, 1), a])
        return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


# ----------------------------------------------------------------------------------------------
# lighting / materials
# ----------------------------------------------------------------------------------------------

def normals(c, height):
    """height in file px -> unit normals (nx, ny, nz)."""
    gy, gx = np.gradient(height)
    gx *= c.k
    gy *= c.k
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1)
    return -gx * nz, -gy * nz, nz


def light(c, height, power=24, spec_amt=1.0, amb=0.32):
    nx, ny, nz = normals(c, height)
    d = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
    diff = np.clip(d, 0, 1)
    h = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1)
    spec = (h ** power) * spec_amt
    # soft "sky" reflection: surfaces facing up read lighter (metal feel)
    sky = np.clip(-ny, 0, 1) * 0.25
    return amb + (1 - amb) * diff + sky, spec, (nx, ny, nz)


def metal(c, mask, height, stops=GOLD, power=30, spec=0.9, sheen=None, tex=0.0, seed=1, scale=1.0,
          amb=0.3):
    """Shade a metal region. Returns rgb array (straight colour) for use with over()."""
    v, sp, _ = light(c, height, power, spec, amb)
    v = v * 0.78 * scale
    if sheen is not None:
        v = v + sheen
    if tex:
        v = v + tex * fbm(c.h, c.w, 3 * c.k, 3, seed)
    rgb = ramp(stops, np.clip(v, 0, 1))
    rgb = rgb + sp[..., None] * np.array([1.0, 0.95, 0.82], np.float32)
    return np.clip(rgb, 0, 1)


def emboss(c, mask, radius, depth):
    """Rounded 'tube' height field from a mask (for strokes and filigree)."""
    return c.blur(mask, radius) * mask * depth


def gold_shape(c, mask, radius=2.0, depth=3.0, stops=GOLD, outline=0.85, shadow=0.55, sdx=1.5, sdy=2.5,
               ssig=2.5, power=28, spec=0.9, tex=0.05, seed=3, sheen=None, line_col=(0.1, 0.06, 0.02),
               line_w=1.0):
    """Paint an embossed metal shape with drop shadow and a thin dark colour-matched outline."""
    if shadow:
        c.shadow(mask, sdx, sdy, ssig, shadow)
    if outline:
        ol = np.clip(c.blur(mask, line_w * 0.8) * 2.6, 0, 1)
        c.over(np.array(line_col, np.float32), ol * outline)
    h = emboss(c, mask, radius, depth)
    rgb = metal(c, mask, h, stops, power, spec, sheen=sheen, tex=tex, seed=seed)
    c.over(rgb, mask)
    return h


def bevel_sd(sd, width, depth, profile="round"):
    """Height from a signed distance (negative inside): rises over `width` px from the edge."""
    t = np.clip(-sd / width, 0, 1)
    if profile == "round":
        return np.sqrt(1 - (1 - t) ** 2) * depth
    if profile == "flat":
        return smooth(0, 1, t) * depth
    return t * depth


# ----------------------------------------------------------------------------------------------
# paths / filigree
# ----------------------------------------------------------------------------------------------

def scroll_path(x, y, heading, length, curl, n=140, power=2.4, bend=0.0):
    """Curve starting at (x,y) heading `heading` deg, gently bending by `bend` deg along the
    length and curling `curl` deg into a spiral near the end (Euler-spiral like)."""
    th = math.radians(heading)
    ds = length / n
    a = math.radians(curl) * (power + 1) / length
    b = math.radians(bend) / length
    pts = [(x, y)]
    for i in range(n):
        t = (i + 0.5) / n
        th += (a * t ** power + b) * ds
        x += math.cos(th) * ds
        y += math.sin(th) * ds
        pts.append((x, y))
    return pts


def stroke_mask(c, pts, w0, w1=None, prof=None, cap=True):
    """Variable-width stroke along pts. prof(t)->width multiplier."""
    if w1 is None:
        w1 = w0
    k = c.k
    n = len(pts)
    widths = []
    for i in range(n):
        t = i / (n - 1)
        w = w0 + (w1 - w0) * t
        if prof:
            w *= prof(t)
        widths.append(max(0.0, w))
    norms = []
    for i in range(n):
        p0 = pts[max(0, i - 1)]
        p1 = pts[min(n - 1, i + 1)]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy) or 1
        norms.append((-dy / L, dx / L))

    def fn(d, _):
        for i in range(n - 1):
            (xa, ya), (xb, yb) = pts[i], pts[i + 1]
            na, nb = norms[i], norms[i + 1]
            wa, wb = widths[i] / 2, widths[i + 1] / 2
            quad = [(xa + na[0] * wa, ya + na[1] * wa), (xb + nb[0] * wb, yb + nb[1] * wb),
                    (xb - nb[0] * wb, yb - nb[1] * wb), (xa - na[0] * wa, ya - na[1] * wa)]
            d.polygon([(qx * k, qy * k) for qx, qy in quad], fill=255)
        if cap:
            for i in (0, n - 1):
                r = widths[i] / 2 * k
                if r > 0.3:
                    x, y = pts[i][0] * k, pts[i][1] * k
                    d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return c.draw(fn)


def scroll(c, x, y, heading, length, curl, w0, w1=None, knob=0.0, bend=0.0, power=2.4, prof=None):
    pts = scroll_path(x, y, heading, length, curl, bend=bend, power=power)
    m = stroke_mask(c, pts, w0, w1 if w1 is not None else w0 * 0.35, prof)
    if knob:
        ex, ey = pts[-1]
        m = np.maximum(m, c.circle(ex, ey, knob))
    return m


def leaf(c, x, y, heading, length, width, bend=0.0, curl=0.0):
    pts = scroll_path(x, y, heading, length, curl, n=60, bend=bend)
    return stroke_mask(c, pts, width, width, prof=lambda t: (math.sin(math.pi * min(1, t * 1.05)) ** 0.7)
                       * (1 - 0.35 * t), cap=False)


def spike(c, x, y, heading, length, width):
    """Tapered thorn from (x,y) outward."""
    pts = scroll_path(x, y, heading, length, 0, n=30)
    return stroke_mask(c, pts, width, 0.2, cap=False)


def diamond(c, cx, cy, rx, ry):
    return c.poly([(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)])


def mirror4(m):
    return np.maximum(np.maximum(m, m[:, ::-1]), np.maximum(m[::-1, :], m[::-1, ::-1]))


def mirror_x(m):
    return np.maximum(m, m[:, ::-1])


def mirror_y(m):
    return np.maximum(m, m[::-1, :])


# ----------------------------------------------------------------------------------------------
# surfaces
# ----------------------------------------------------------------------------------------------

def slate(c, base=(0.112, 0.114, 0.12), seed=11, crack=True, light_grad=True, amount=1.0):
    """Dark painted slate/iron surface colour (straight rgb HxWx3)."""
    n1 = fbm(c.h, c.w, 70 * c.k, 4, seed)
    n2 = fbm(c.h, c.w, 10 * c.k, 3, seed + 1)
    rng = np.random.default_rng(seed + 2)
    grain = gblur(rng.standard_normal((c.h, c.w)).astype(np.float32), 0.6 * c.k)
    v = 1 + amount * (0.2 * n1 + 0.1 * n2 + 0.12 * grain)
    tint = smooth(-0.3, 0.6, fbm(c.h, c.w, 110 * c.k, 2, seed + 3))
    col = np.array(base, np.float32)
    cool = col * np.array([0.95, 1.0, 1.07], np.float32)
    warm = col * np.array([1.07, 1.01, 0.94], np.float32)
    rgb = cool[None, None] * tint[..., None] + warm[None, None] * (1 - tint[..., None])
    rgb = rgb * v[..., None]
    if light_grad:
        g = 1.14 - 0.28 * np.clip((c.X / c.W) * 0.4 + (c.Y / c.H) * 0.6, 0, 1)
        rgb = rgb * g[..., None]
    if crack:
        cm, hm = cracks(c, seed + 5, count=max(2, int(c.W * c.H / 60000)))
        rgb = rgb * (1 - 0.55 * cm[..., None]) + 0.05 * hm[..., None]
    return np.clip(rgb, 0, 1)


def cracks(c, seed, count=4):
    rng = np.random.default_rng(seed)
    k = c.k

    def fn(d, _):
        for _ in range(count):
            x, y = rng.uniform(0, c.W), rng.uniform(0, c.H)
            ang = rng.uniform(0, 2 * math.pi)
            for _seg in range(rng.integers(6, 16)):
                ang += rng.normal(0, 0.5)
                L = rng.uniform(4, 16)
                nx, ny = x + math.cos(ang) * L, y + math.sin(ang) * L
                d.line([(x * k, y * k), (nx * k, ny * k)], fill=int(rng.uniform(120, 255)), width=max(1, int(k)))
                if rng.random() < 0.15:
                    bx, by, ba = nx, ny, ang + rng.choice([-1, 1]) * rng.uniform(0.6, 1.2)
                    for _b in range(rng.integers(2, 5)):
                        ex, ey = bx + math.cos(ba) * 7, by + math.sin(ba) * 7
                        d.line([(bx * k, by * k), (ex * k, ey * k)], fill=110, width=max(1, int(k * 0.7)))
                        bx, by, ba = ex, ey, ba + rng.normal(0, 0.5)
                x, y = nx, ny
    m = c.draw(fn)
    m = gblur(m, 0.5 * k)
    hl = c.shift(m, 0, 1) * (1 - m)
    return m, hl


def parchment(c, seed=21):
    n1 = fbm(c.h, c.w, 60 * c.k, 4, seed)
    n2 = fbm(c.h, c.w, 8 * c.k, 3, seed + 1)
    rng = np.random.default_rng(seed)
    fib = gblur(rng.standard_normal((c.h, c.w)).astype(np.float32), 0.7 * c.k)
    base = np.array(hx("#e6d3a8"), np.float32)
    dark = np.array(hx("#b08a55"), np.float32)
    t = np.clip(0.35 + 0.5 * n1 + 0.15 * n2, 0, 1)
    rgb = base[None, None] * (1 - t[..., None] * 0.55) + dark[None, None] * (t[..., None] * 0.55)
    rgb = rgb * (1 + 0.05 * fib)[..., None]
    # stains
    st = smooth(0.35, 0.7, fbm(c.h, c.w, 40 * c.k, 3, seed + 7))
    rgb = rgb * (1 - 0.12 * st[..., None])
    return np.clip(rgb, 0, 1)


def inner_shadow(c, mask, sigma, opacity, dx=0, dy=2, color=(0, 0, 0)):
    inv = c.shift(1 - mask, dx, dy)
    sh = c.blur(inv, sigma) * mask * opacity
    c.over(np.array(color, np.float32), sh)


def text(c, s, cx, cy, size, fill=(1, 1, 1), weight=b"Bold", anchor="mm", shadow=True):
    """Draw text into the canvas (used only for the contact sheet mock-up)."""
    f = ImageFont.truetype(FONT, int(size * c.k))
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    k = c.k
    m = c.draw(lambda d, _: d.text((cx * k, cy * k), s, font=f, anchor=anchor, fill=255))
    if shadow:
        c.shadow(m, 1, 2, 1.5, 0.9)
    c.over(np.array(fill, np.float32), m)


# ----------------------------------------------------------------------------------------------
# kit building blocks
# ----------------------------------------------------------------------------------------------

def band(c, sd, inset, width, depth=2.0, stops=GOLD, power=30, spec=0.9, tex=0.04, seed=5, paint=True,
         amb=0.3, sheen=None):
    """Tube-shaded band that runs parallel to a shape edge (sd), `inset` px inside it."""
    hw = width / 2
    dc = np.abs(sd + inset + hw)
    m = c.fill(dc - hw)
    h = np.sqrt(np.clip(1 - (dc / hw) ** 2, 0, 1)) * depth
    if paint:
        rgb = metal(c, m, h, stops, power, spec, tex=tex, seed=seed, amb=amb, sheen=sheen)
        c.over(rgb, m)
    return m, h


def corner_ornament(c, s=1.0, ox=0.0, oy=0.0, gem=(0.55, 0.08, 0.06), spikes=True, scrolls=True):
    """Top-left corner filigree mask (plus gem mask) around corner point (ox, oy), scale s."""
    def P(x, y):
        return ox + x * s, oy + y * s
    m = np.zeros((c.h, c.w), np.float32)
    if scrolls:
        m = np.maximum(m, scroll(c, *P(26, 13), -4, 58 * s, 340, 5.6 * s, 1.6 * s, knob=2.2 * s, power=3.2))
        m = np.maximum(m, scroll(c, *P(40, 15), 35, 26 * s, -260, 3.6 * s, 1.2 * s, knob=1.8 * s, power=2.6))
        m = np.maximum(m, leaf(c, *P(30, 16), 70, 18 * s, 5 * s, bend=-30))
    m = np.maximum(m, leaf(c, *P(26, 26), 45, 34 * s, 9 * s))
    if spikes:
        m = np.maximum(m, spike(c, *P(14, 14), 225, 13 * s, 7 * s))
    m = np.maximum(m, m.T) if c.w == c.h and ox == oy else m
    d = diamond(c, *P(20, 20), 11 * s, 11 * s)
    m = np.maximum(m, d)
    g = diamond(c, *P(20, 20), 5.5 * s, 5.5 * s)
    return m, g


def paint_gem(c, gm, color, glow=0.0):
    """Faceted cabochon gem inside mask gm."""
    h = emboss(c, gm, 1.5, 2.0)
    v, sp, (nx, ny, nz) = light(c, h, 40, 1.2)
    col = np.array(color, np.float32)
    rgb = col[None, None] * (0.35 + 0.9 * v[..., None]) + sp[..., None]
    c.over(np.clip(rgb, 0, 1), gm)
    if glow:
        c.add(col, c.blur(gm, 3) * glow)


def dark_body(c, sd, seed=11, base=(0.112, 0.114, 0.12), crack=True, ishadow=0.7, shadow=0.55, amount=1.0):
    body = c.fill(sd)
    if shadow:
        c.shadow(body, 0, 4, 6, shadow)
    c.over(slate(c, base, seed, crack, amount=amount), body)
    if ishadow:
        inner_shadow(c, body, 8, ishadow, 0, 3)
    return body


# ----------------------------------------------------------------------------------------------
# kit pieces
# ----------------------------------------------------------------------------------------------

def make_panel(parch=False):
    W = 512
    c = Canvas(W, W)
    sd = c.sd_rrect(6, 6, W - 6, W - 6, 20)
    if parch:
        body = c.fill(sd)
        c.shadow(body, 0, 4, 6, 0.55)
        rgb = parchment(c, 21)
        # burnt / aged edge
        edge = np.clip(1 + sd / 34, 0, 1) ** 2
        rgb = rgb * (1 - 0.45 * edge[..., None]) + np.array(hx("#5a3514"))[None, None] * 0.12 * edge[..., None]
        c.over(rgb, body)
        inner_shadow(c, body, 6, 0.45, 0, 2, color=(0.2, 0.1, 0.02))
        rim_stops, gold_stops = IRON, GOLD
        iron_base = (0.16, 0.12, 0.09)
    else:
        body = dark_body(c, sd, seed=13)
        rim_stops, gold_stops = IRON, GOLD
        iron_base = None
    # outer iron rim + gold edges
    m, _ = band(c, sd, 0, 11, 3.0, rim_stops, 18, 0.5, tex=0.08, seed=4)
    band(c, sd, 0.5, 3.2, 1.6, gold_stops, 30, 0.8)
    band(c, sd, 10, 3.6, 1.8, gold_stops, 30, 0.9)
    band(c, sd, 20, 1.4, 0.8, GOLD_DIM if not parch else [(0, hx("#3a2410")), (1, hx("#8a6030"))], 20, 0.3)
    orn, gem = corner_ornament(c, 1.15, 0, 0)
    orn = mirror4(orn)
    gem = mirror4(gem)
    gold_shape(c, orn, 1.8, 3.2)
    paint_gem(c, gem, (0.62, 0.06, 0.05) if not parch else (0.1, 0.35, 0.55))
    return c.image()


def make_hud_bar():
    W, H = 1920, 260
    c = Canvas(W, H)
    top = 36
    sd = np.maximum(top - c.Y, c.Y - (H + 50))  # full-width slab from y=top
    body = c.fill(sd)
    c.over(np.array((0, 0, 0), np.float32), c.blur(c.shift(body, 0, -4), 6) * 0.6)
    rgb = slate(c, (0.108, 0.11, 0.116), 31, True)
    # darker toward bottom, a hint of warm light under the trim
    g = 1.05 - 0.25 * np.clip((c.Y - top) / (H - top), 0, 1)
    rgb = rgb * g[..., None]
    c.over(rgb, body)
    inner_shadow(c, body, 10, 0.8, 0, 6)
    # trim: iron lip + bright gold line + thin gold line
    sdt = top - c.Y  # negative below top
    band(c, sdt, 0, 16, 3.8, IRON, 18, 0.5, tex=0.08, seed=7)
    band(c, sdt, 0.3, 5.0, 2.4, GOLD, 30, 1.0)
    band(c, sdt, 12.5, 4.6, 2.2, GOLD, 30, 0.9)
    band(c, sdt, 24, 1.8, 0.9, GOLD_DIM, 20, 0.4)
    # ornate ends (inside the 96 px margins): strap-end plate with scrolls rising above the trim
    m = np.zeros((c.h, c.w), np.float32)
    m = np.maximum(m, leaf(c, 36, top + 8, 0, 56, 11))
    m = np.maximum(m, scroll(c, 40, top - 2, 285, 50, 320, 7, 2.0, knob=3.0, power=2.4))
    m = np.maximum(m, scroll(c, 40, top + 18, 75, 50, -320, 7, 2.0, knob=3.0, power=2.4))
    m = np.maximum(m, leaf(c, 18, top - 2, 280, 24, 7, bend=-20))
    m = np.maximum(m, leaf(c, 18, top + 18, 80, 24, 7, bend=20))
    m = np.maximum(m, diamond(c, 30, top + 8, 13, 17))
    gm = diamond(c, 30, top + 8, 6, 8.5)
    m = mirror_x(m)
    gm = mirror_x(gm)
    gold_shape(c, m, 2.0, 3.6)
    paint_gem(c, gm, (0.62, 0.06, 0.05))
    # faint bottom edge
    c.mul(1 - 0.35 * smooth(H - 14, H, c.Y))
    return c.image()


def make_nameplate():
    W, H = 640, 160
    c = Canvas(W, H)
    y0, y1 = 26, 134
    cy = (y0 + y1) / 2
    # body: 45-degree pointed left end, rounded right end
    xl = 64
    xp = xl - 8
    sd = np.maximum(c.sd_rrect(xl - 40, y0, W - 10, y1, 14), (np.abs(c.Y - cy) - (c.X - xp)) / math.sqrt(2))
    body = dark_body(c, sd, seed=41)
    band(c, sd, 0, 9, 2.6, IRON, 18, 0.5, tex=0.08)
    band(c, sd, 0.5, 3.2, 1.6, GOLD, 30, 0.9)
    band(c, sd, 8.5, 3.0, 1.5, GOLD, 30, 0.9)
    # left flourish
    m = np.zeros((c.h, c.w), np.float32)
    h = (y1 - y0) / 2
    m = np.maximum(m, scroll(c, xp + h - 4, y0 + 2, 200, 56, -300, 7, 2, knob=3, power=2.4))
    m = np.maximum(m, scroll(c, xp + h - 4, y1 - 2, 160, 56, 300, 7, 2, knob=3, power=2.4))
    m = np.maximum(m, spike(c, xp + 4, cy, 180, 42, 11))
    m = np.maximum(m, diamond(c, xp + 26, cy, 13, 17))
    m = np.maximum(m, leaf(c, xp + h + 2, y0 + 2, 10, 36, 7, bend=-10))
    m = np.maximum(m, leaf(c, xp + h + 2, y1 - 2, -10, 36, 7, bend=10))
    gm = diamond(c, xp + 26, cy, 6, 8.5)
    # right corner accents
    for yy, sgn in ((y0, 1), (y1, -1)):
        m = np.maximum(m, scroll(c, W - 22, yy + 3 * sgn, 180, 30, 180 * sgn, 4.5, 1.6, knob=1.8))
        m = np.maximum(m, c.circle(W - 16, yy + 2 * sgn, 4))
    gold_shape(c, m, 1.8, 3.2)
    paint_gem(c, gm, (0.62, 0.06, 0.05))
    return c.image()


def ring_ornaments(c, cx, cy, R, s):
    m = np.zeros((c.h, c.w), np.float32)
    top = cy - R
    m = np.maximum(m, diamond(c, cx, top - 6 * s, 10 * s, 16 * s))
    for sg in (-1, 1):
        # finial scrolls sweeping along the ring, curling outward
        m = np.maximum(m, scroll(c, cx + sg * 6 * s, top - 2 * s, 270 + sg * 100, 46 * s, -sg * 320, 6 * s,
                                 1.6 * s, knob=2.4 * s, power=2.2, bend=sg * 30))
        m = np.maximum(m, leaf(c, cx + sg * 8 * s, top - 8 * s, 270 + sg * 40, 18 * s, 6 * s, bend=sg * 20))
        # side clasps
        sx = cx + sg * R
        m = np.maximum(m, diamond(c, sx + sg * 4 * s, cy, 8 * s, 13 * s))
        m = np.maximum(m, scroll(c, sx + sg * 2 * s, cy - 12 * s, 270 - sg * 20, 20 * s, -sg * 200, 4 * s, 1.3 * s,
                                 knob=1.8 * s))
        m = np.maximum(m, scroll(c, sx + sg * 2 * s, cy + 12 * s, 90 + sg * 20, 20 * s, sg * 200, 4 * s, 1.3 * s,
                                 knob=1.8 * s))
        # bottom flourish
        m = np.maximum(m, scroll(c, cx + sg * 5 * s, cy + R + 2 * s, 90 - sg * 100, 40 * s, sg * 300, 5.5 * s,
                                 1.5 * s, knob=2.2 * s, power=2.2, bend=-sg * 30))
    m = np.maximum(m, diamond(c, cx, cy + R + 5 * s, 7 * s, 11 * s))
    return m


def make_portrait_frame(size):
    c = Canvas(size, size)
    s = size / 320.0
    cx = cy = size / 2
    R_in, R_out = 114 * s, 137 * s
    sdo = c.sd_circle(cx, cy, R_out)
    ring = c.fill(np.maximum(sdo, R_in - np.hypot(c.X - cx, c.Y - cy)))
    c.shadow(ring, 0, 3 * s, 5 * s, 0.6)
    # inner shadow cast onto the portrait (drawn as translucent dark inside the hole)
    rr = np.hypot(c.X - cx, c.Y - cy)
    ish = smooth(R_in - 16 * s, R_in, rr) * (rr < R_in + 1) * 0.55
    c.over(np.zeros(3, np.float32), ish)
    # iron ring body
    band(c, sdo, 0, R_out - R_in, 5 * s, IRON, 16, 0.4, tex=0.1, seed=9)
    band(c, sdo, 0.5 * s, 7 * s, 3.2 * s, GOLD, 30, 1.0)
    band(c, sdo, (R_out - R_in) - 6.5 * s, 6 * s, 3 * s, GOLD, 30, 1.0)
    band(c, sdo, (R_out - R_in) / 2 - 1 * s, 2 * s, 1 * s, GOLD_DIM, 20, 0.4)
    # little beads around the middle of the ring
    beads = np.zeros((c.h, c.w), np.float32)
    rm = (R_in + R_out) / 2
    for i in range(24):
        a = 2 * math.pi * i / 24 + math.pi / 24
        beads = np.maximum(beads, c.circle(cx + math.cos(a) * rm, cy + math.sin(a) * rm, 2.2 * s))
    gold_shape(c, beads, 1.2 * s, 1.5 * s, shadow=0.4, sdx=0.5, sdy=1, ssig=1)
    orn = ring_ornaments(c, cx, cy, R_out, s)
    gold_shape(c, orn, 1.8 * s, 3.2 * s, sdx=1.2 * s, sdy=2 * s, ssig=2 * s)
    gm = np.maximum(diamond(c, cx, cy - R_out - 6 * s, 4.8 * s, 8 * s), diamond(c, cx, cy + R_out + 5 * s, 3.2 * s, 5 * s))
    paint_gem(c, gm, (0.62, 0.06, 0.05))
    return c.image()


def make_level_badge():
    S = 96
    c = Canvas(S, S)
    cx = cy = S / 2
    sd = c.sd_circle(cx, cy, 44)
    disc = c.fill(sd)
    c.shadow(disc, 0, 2, 3, 0.7)
    rr = np.hypot(c.X - cx + 8, c.Y - cy + 10) / 44
    face = np.array(hx("#1d2129"))[None, None] * (1.25 - 0.6 * np.clip(rr, 0, 1))[..., None]
    face = face * (1 + 0.1 * fbm(c.h, c.w, 8 * c.k, 3, 5))[..., None]
    c.over(face, disc)
    inner_shadow(c, c.fill(sd + 7), 4, 0.8, 0, 2)
    band(c, sd, 0, 8, 3.2, GOLD, 30, 1.0)
    band(c, sd, 10, 1.6, 0.8, GOLD_DIM, 20, 0.4)
    return c.image()


def make_bar_frame():
    W, H = 256, 48
    c = Canvas(W, H)
    sd = c.sd_rrect(2, 3, W - 2, H - 3, 9)
    hole = c.fill(sd + 7)
    c.shadow(c.fill(sd) * (1 - hole), 0, 2, 2, 0.6)
    band(c, sd, 0, 7.5, 2.4, IRON, 18, 0.4, seed=4)
    band(c, sd, 0.2, 3.0, 1.5, GOLD, 30, 1.0)
    band(c, sd, 5.2, 2.4, 1.2, GOLD, 30, 0.8)
    # inner lip shadow falling onto the fill
    inner_shadow(c, hole, 2.5, 0.0, 0, 2)
    lip = hole * (1 - c.shift(hole, 0, 3)) * 0.5
    c.over(np.zeros(3, np.float32), c.blur(lip, 1.2))
    # end rivets (inside margins)
    m = np.zeros((c.h, c.w), np.float32)
    for x in (6.5, W - 6.5):
        m = np.maximum(m, diamond(c, x, H / 2, 4, 7))
    gold_shape(c, m, 1.0, 1.6, shadow=0.4, sdx=0.5, sdy=1, ssig=1)
    return c.image()


def make_bar_fill(color, glow=(1, 1, 1), seed=1, back=False):
    W, H = 256, 40
    c = Canvas(W, H)
    col = np.array(color, np.float32)
    t = c.Y / H
    if back:
        rgb = np.array(hx("#0b0d11"))[None, None] * np.ones((c.h, c.w, 1), np.float32)
        rgb = rgb * (1 + 0.15 * fbm(c.h, c.w, 6 * c.k, 3, seed))[..., None]
        c.over(rgb, np.ones((c.h, c.w), np.float32))
        box = c.fill(c.sd_rrect(0, 0, W, H, 4))
        inner_shadow(c, box, 4, 0.95, 0, 4)
        c.over(np.array((0.3, 0.33, 0.4), np.float32), smooth(H - 3, H - 1, c.Y) * (1 - smooth(H - 1, H, c.Y)) * 0.35)
        return c.image()
    # vertical value profile: dark bottom, saturated middle, glossy top band
    v = 0.55 + 0.55 * (1 - t) - 0.25 * smooth(0.6, 1.0, t)
    rgb = col[None, None] * v[..., None]
    # horizontal gradient: a touch darker at the left, hotter at the right
    hgr = 0.86 + 0.2 * (c.X / W)
    rgb = rgb * hgr[..., None]
    # hot core line
    core = np.exp(-((t - 0.52) / 0.18) ** 2) * 0.25
    rgb = rgb + (col * 0.5 + np.array(glow, np.float32) * 0.5)[None, None] * core[..., None]
    # faint horizontal streak texture (stretch friendly)
    streak = fbm(c.h, 4, 2 * c.k, 2, seed)[:, :1]
    rgb = rgb * (1 + 0.07 * streak)[..., None]
    # gloss band on the top 40 %
    gloss = smooth(0.06, 0.12, t) * (1 - smooth(0.2, 0.45, t)) * 0.45
    rgb = rgb + (np.array((1, 1, 1), np.float32) * gloss[..., None])
    top = (1 - smooth(0.0, 0.06, t)) * 0.35
    rgb = rgb * (1 - top[..., None]) + top[..., None] * 0.2
    bot = smooth(0.88, 1.0, t)
    rgb = rgb * (1 - 0.5 * bot[..., None])
    c.over(np.clip(rgb, 0, 1), np.ones((c.h, c.w), np.float32))
    return c.image()


def slot_frame(c, state="normal"):
    S = c.W
    o = 10.0
    sd = c.sd_rrect(o, o, S - o, S - o, 12)
    inner = c.fill(sd + 13)
    if state == "active":
        glow_m = c.fill(sd) * (1 - inner)
        c.add(np.array((1.0, 0.72, 0.2), np.float32), c.blur(glow_m, 7) * 1.25)
        c.add(np.array((1.0, 0.85, 0.4), np.float32), c.blur(glow_m, 2.5) * 0.5)
    ring = c.fill(sd) * (1 - inner)
    c.shadow(ring, 0, 2, 3, 0.55 if state != "active" else 0.2)
    gs, irs = {"normal": (GOLD, IRON), "active": (GOLD_HOT, GOLD), "disabled": (GREY_GOLD, IRON)}[state]
    # inset shadow on the icon area (seats the icon)
    rr = -sd - 13
    vign = (1 - smooth(0, 16, rr)) * inner * 0.6
    if state == "disabled":
        c.over(np.array((0.03, 0.03, 0.04), np.float32), inner * 0.6)
    c.over(np.zeros(3, np.float32), vign)
    band(c, sd, 0, 13, 3.2, irs, 18 if state != "active" else 30, 0.5, tex=0.08, seed=8,
         amb=0.3 if state != "active" else 0.15, sheen=None if state != "active" else -0.12)
    band(c, sd, 0.2, 3.4, 1.7, gs, 30, 1.0)
    band(c, sd, 10.2, 3.2, 1.6, gs, 30, 1.0)
    # gold corner brackets
    m = np.zeros((c.h, c.w), np.float32)
    L = 38
    m = np.maximum(m, c.poly([(o - 2, o + 6), (o + 6, o - 2), (o + L, o - 2), (o + L + 6, o + 3.5), (o + L, o + 9),
                              (o + 13, o + 9), (o + 9, o + 13), (o + 9, o + L), (o + 3.5, o + L + 6),
                              (o - 2, o + L)]))
    m = mirror4(m)
    gold_shape(c, m, 1.6, 2.6, gs, shadow=0.5 if state != "active" else 0.15, sdx=1, sdy=1.5, ssig=1.5,
               line_col=(0.08, 0.05, 0.02))
    gm = np.zeros((c.h, c.w), np.float32)
    gm = mirror4(np.maximum(gm, diamond(c, o + 4.5, o + 4.5, 3, 3)))
    if state == "active":
        c.add(np.array((1.0, 0.8, 0.35), np.float32), c.blur(inner * (1 - c.fill(sd + 20)), 3) * 0.6)
    if state == "disabled":
        pass
    return c


def make_skill_slot(state):
    c = Canvas(180, 180)
    slot_frame(c, state)
    return c.image()


def make_slot_number():
    W, H = 56, 46
    c = Canvas(W, H)
    sd = c.sd_rrect(3, 3, W - 3, H - 3, 8)
    body = c.fill(sd)
    c.shadow(body, 0, 2, 2, 0.7)
    face = np.array(hx("#171a20"))[None, None] * (1.25 - 0.5 * (c.Y / H))[..., None]
    c.over(face, body)
    inner_shadow(c, c.fill(sd + 3), 2, 0.6, 0, 1.5)
    band(c, sd, 0, 3.2, 1.4, GOLD_DIM, 26, 0.8)
    band(c, sd, 0, 1.6, 0.8, GOLD, 26, 0.7)
    return c.image()


def ribbon_ends(c, W, H, cy, x_plate, y0, y1):
    m = np.zeros((c.h, c.w), np.float32)
    xp = x_plate
    # bracket hugging the chamfered plate end
    br = [(xp + 26, y0 - 5), (xp + 12, y0 - 5), (xp - 7, y0 + 14), (xp - 7, y1 - 14), (xp + 12, y1 + 5),
          (xp + 26, y1 + 5)]
    m = np.maximum(m, stroke_mask(c, br, 7, 7))
    kx = xp - 20
    # big scrolls curling outward above and below, and a smaller inner pair
    m = np.maximum(m, scroll(c, kx + 4, cy - 10, 235, 84, 320, 10, 2.6, knob=4.2, power=2.8, bend=20))
    m = np.maximum(m, scroll(c, kx + 4, cy + 10, 125, 84, -320, 10, 2.6, knob=4.2, power=2.8, bend=-20))
    m = np.maximum(m, leaf(c, kx - 8, cy - 8, 205, 34, 8, bend=15))
    m = np.maximum(m, leaf(c, kx - 8, cy + 8, 155, 34, 8, bend=-15))
    m = np.maximum(m, spike(c, kx - 12, cy, 180, 44, 11))
    m = np.maximum(m, leaf(c, xp + 4, y0 - 2, 250, 26, 8, bend=-25))
    m = np.maximum(m, leaf(c, xp + 4, y1 + 2, 110, 26, 8, bend=25))
    m = np.maximum(m, diamond(c, kx, cy, 15, 21))
    gm = diamond(c, kx, cy, 7.5, 11.5)
    return m, gm


def make_ribbon(state="normal"):
    W, H = 720, 150
    c = Canvas(W, H)
    dy = 3 if state == "pressed" else 0
    cy = H / 2 + dy
    xp = 124
    y0, y1 = 24 + dy, 126 + dy
    sd = c.sd_chamfer(xp, y0, W - xp, y1, 18, 3)
    body = c.fill(sd)
    c.shadow(body, 0, 5 - dy, 7, 0.6)
    red = {"normal": hx("#a3161a"), "pressed": hx("#6e0c10"), "disabled": hx("#4d3a38")}[state]
    gstops = {"normal": GOLD, "pressed": GOLD_DIM, "disabled": GREY_GOLD}[state]
    # crimson field: domed, grained, glossy top
    sdi = sd + 12
    field = c.fill(sdi)
    t = (c.Y - y0) / (y1 - y0)
    col = np.array(red, np.float32)
    v = 1.25 - 0.55 * t
    rgb = col[None, None] * v[..., None]
    rgb = rgb * (1 + 0.12 * fbm(c.h, c.w, 30 * c.k, 4, 51) + 0.05 * fbm(c.h, c.w, 3 * c.k, 2, 52))[..., None]
    # painterly darker edges
    e = smooth(0, 22, -sdi)
    rgb = rgb * (0.55 + 0.45 * e)[..., None]
    c.over(np.clip(rgb, 0, 1), body)
    if state != "disabled":
        gloss = (1 - smooth(0.05, 0.42, t)) * smooth(0.0, 0.08, t) * field * (0.22 if state == "normal" else 0.08)
        c.screen_on(np.array((1.0, 0.75, 0.7), np.float32), gloss)
    if state == "pressed":
        inner_shadow(c, field, 8, 0.8, 0, 5)
    else:
        inner_shadow(c, field, 5, 0.55, 0, 2)
    # frame: iron + gold edges + inner gold line
    band(c, sd, 0, 12, 3.2, IRON, 18, 0.5, tex=0.08)
    band(c, sd, 0.3, 3.6, 1.8, gstops, 30, 1.0)
    band(c, sd, 11, 3.2, 1.6, gstops, 30, 1.0)
    band(c, sd, 18, 1.4, 0.7, gstops, 24, 0.6)
    m, gm = ribbon_ends(c, W, H, cy, xp, y0, y1)
    m = mirror_x(m)
    gm = mirror_x(gm)
    gold_shape(c, m, 2.2, 4.0, gstops, shadow=0.6, sdx=2, sdy=3 - dy, ssig=3)
    if state == "disabled":
        paint_gem(c, gm, (0.3, 0.3, 0.3))
    else:
        paint_gem(c, gm, (0.75, 0.08, 0.05) if state == "normal" else (0.45, 0.05, 0.03),
                  glow=0.35 if state == "normal" else 0)
    return c.image()


def make_button(state="normal", gold=False):
    W, H = 256, 96
    c = Canvas(W, H)
    dy = 2 if state == "pressed" else 0
    sd = c.sd_rrect(5, 5 + dy, W - 5, H - 7 + dy, 14)
    body = c.fill(sd)
    c.shadow(body, 0, 3 - dy, 3, 0.65)
    t = (c.Y - 5) / (H - 12)
    if gold:
        face_h = bevel_sd(sd + 4, 10, 4, "round")
        sheen = 0.18 * (1 - t) - 0.08 + 0.05 * fbm(c.h, c.w, 40 * c.k, 3, 61)
        brushed = fbm(c.h, 8, 1.5 * c.k, 2, 62)[:, :1] * 0.04
        rgb = metal(c, body, face_h, GOLD if state == "normal" else GOLD_DIM, 26, 0.7, sheen=sheen + brushed,
                    amb=0.4, scale=1.05)
        c.over(rgb, body)
        if state == "pressed":
            inner_shadow(c, c.fill(sd + 4), 5, 0.6, 0, 3, (0.2, 0.1, 0))
        band(c, sd, 0, 4, 1.8, [(0, hx("#1a0f04")), (0.5, hx("#5a3a12")), (1, hx("#b0823a"))], 20, 0.6)
        band(c, sd, 6, 1.4, 0.6, [(0, hx("#6a4818")), (1, hx("#fff2c0"))], 20, 0.5)
        return c.image()
    base = {"normal": (0.16, 0.175, 0.2), "pressed": (0.1, 0.11, 0.13), "disabled": (0.14, 0.14, 0.14)}[state]
    gs = {"normal": GOLD, "pressed": GOLD_DIM, "disabled": GREY_GOLD}[state]
    rgb = slate(c, base, 71, False, False, amount=0.6)
    v = (1.2 - 0.45 * t) if state != "pressed" else (0.85 + 0.25 * t)
    rgb = rgb * v[..., None]
    c.over(rgb, body)
    fh = bevel_sd(sd + 4, 6, 2.5, "round")
    vv, sp, _ = light(c, fh, 20, 0.35)
    c.screen_on(np.array((0.6, 0.65, 0.75), np.float32), (vv - 0.7).clip(0, 1) * c.fill(sd + 4) * 0.4)
    if state == "pressed":
        inner_shadow(c, c.fill(sd + 4), 6, 0.85, 0, 4)
    else:
        c.screen_on(np.array((0.5, 0.55, 0.6), np.float32), (1 - smooth(0.05, 0.4, t)) * c.fill(sd + 5) * 0.12)
    band(c, sd, 0, 4.2, 1.9, gs, 30, 1.0 if state == "normal" else 0.4)
    band(c, sd, 7, 1.3, 0.6, GOLD_DIM if state != "disabled" else GREY_GOLD, 20, 0.3)
    # tiny corner studs (in the fixed margins)
    m = np.zeros((c.h, c.w), np.float32)
    for x, y in ((16, 16 + dy), (W - 16, 16 + dy), (16, H - 18 + dy), (W - 16, H - 18 + dy)):
        m = np.maximum(m, diamond(c, x, y, 3.2, 3.2))
    gold_shape(c, m, 1.0, 1.5, gs, shadow=0.4, sdx=0.5, sdy=1, ssig=1)
    return c.image()


def round_base(c, state="normal", face=(0.13, 0.14, 0.17), gs=GOLD, rim=12.0):
    S = c.W
    cx = cy = S / 2
    dy = 2 if state == "pressed" else 0
    R = S / 2 - 6
    sd = c.sd_circle(cx, cy + dy, R)
    disc = c.fill(sd)
    c.shadow(disc, 0, 3 - dy, 4, 0.7)
    rr = np.hypot(c.X - cx + R * 0.25, c.Y - cy - dy + R * 0.35) / R
    fcol = np.array(face, np.float32)
    shade = (1.35 - 0.75 * np.clip(rr, 0, 1.3)) if state != "pressed" else (0.8 - 0.3 * np.clip(rr, 0, 1.3))
    rgb = fcol[None, None] * shade[..., None] * (1 + 0.12 * fbm(c.h, c.w, 10 * c.k, 3, 81))[..., None]
    c.over(np.clip(rgb, 0, 1), disc)
    inner_shadow(c, c.fill(sd + rim), 5 * S / 180, 0.9 if state == "pressed" else 0.7, 0, 3 * S / 180)
    band(c, sd, 0, rim, 3.4 * S / 180, IRON, 18, 0.4, tex=0.08)
    band(c, sd, 0.3, 4.4 * S / 180, 2.0 * S / 180, gs, 30, 1.0)
    band(c, sd, rim - 3.6 * S / 180, 3.4 * S / 180, 1.6 * S / 180, gs, 30, 1.0)
    return sd, dy


def make_round_button(state="normal"):
    c = Canvas(180, 180)
    round_base(c, state, gs=GOLD if state == "normal" else GOLD_DIM, rim=14)
    return c.image()


def make_close(state="normal"):
    S = 112
    c = Canvas(S, S)
    sd, dy = round_base(c, state, face=(0.45, 0.06, 0.06), gs=GOLD if state == "normal" else GOLD_DIM, rim=10)
    cx, cy = S / 2, S / 2 + dy
    L, w = 21, 10
    m = np.maximum(stroke_mask(c, [(cx - L, cy - L), (cx + L, cy + L)], w, w),
                   stroke_mask(c, [(cx - L, cy + L), (cx + L, cy - L)], w, w))
    gold_shape(c, m, 2.2, 3.2, GOLD if state == "normal" else GOLD_DIM, shadow=0.7, sdx=1, sdy=2, ssig=1.5)
    return c.image()


def make_divider():
    W, H = 1200, 40
    c = Canvas(W, H)
    cy = H / 2
    m = np.zeros((c.h, c.w), np.float32)
    # tapered main lines from the centre ornament to the ends
    xs = np.linspace(W / 2 - 40, 8, 80)
    pts = [(x, cy) for x in xs]
    m = np.maximum(m, stroke_mask(c, pts, 5, 0.6))
    pts2 = [(x, cy + 7) for x in np.linspace(W / 2 - 70, 120, 60)]
    m = np.maximum(m, stroke_mask(c, pts2, 1.8, 0.3))
    pts3 = [(x, cy - 7) for x in np.linspace(W / 2 - 70, 120, 60)]
    m = np.maximum(m, stroke_mask(c, pts3, 1.8, 0.3))
    # centre ornament (left half)
    m = np.maximum(m, scroll(c, W / 2 - 16, cy - 3, 190, 34, 250, 5, 1.6, knob=2.2))
    m = np.maximum(m, scroll(c, W / 2 - 16, cy + 3, 170, 34, -250, 5, 1.6, knob=2.2))
    m = np.maximum(m, leaf(c, W / 2 - 50, cy, 180, 30, 7))
    for x in (W / 2 - 95, W / 2 - 180):
        m = np.maximum(m, diamond(c, x, cy, 5, 5))
    m = mirror_x(m)
    m = np.maximum(m, diamond(c, W / 2, cy, 12, 16))
    gold_shape(c, m, 1.4, 2.4, shadow=0.55, sdx=1, sdy=2, ssig=2)
    paint_gem(c, diamond(c, W / 2, cy, 5.5, 8), (0.62, 0.06, 0.05))
    return c.image()


def make_tab(active=False):
    W, H = 240, 88
    c = Canvas(W, H)
    x0, y0 = 4, 6
    sd = c.sd_rrect(x0, y0, W - x0, H + 30, 16)
    body = c.fill(sd)
    c.shadow(body, 0, -1, 3, 0.4)
    base = (0.17, 0.18, 0.21) if active else (0.085, 0.09, 0.1)
    rgb = slate(c, base, 91 + active, False, False, amount=0.7)
    t = (c.Y - y0) / (H - y0)
    rgb = rgb * (1.2 - 0.35 * t if active else 1.0 - 0.2 * t)[..., None]
    c.over(rgb, body)
    inner_shadow(c, body, 5, 0.4 if active else 0.7, 0, 3)
    gs = GOLD if active else GOLD_DIM
    band(c, sd, 0, 4.2, 1.9, gs, 30, 1.0 if active else 0.4)
    band(c, sd, 7, 1.3, 0.6, GOLD_DIM, 20, 0.3)
    if active:
        glow = (1 - smooth(0, 10, c.Y - y0 - 4)) * c.fill(sd + 6) * (1 - smooth(0.3, 0.5, np.abs(c.X / W - 0.5)))
        c.add(np.array((1.0, 0.8, 0.4), np.float32), glow * 0.35)
    # bottom: fade into the panel line
    c.mul(1 - 0.3 * smooth(H - 10, H, c.Y))
    return c.image()


def make_turn_badge():
    W, H = 280, 88
    c = Canvas(W, H)
    cy = H / 2
    y0, y1 = 16, H - 16
    xl, xr = 44, W - 44
    # hexagonal plate with pointed ends
    sd_rect = np.maximum(np.abs(c.Y - cy) - (y1 - y0) / 2, np.abs(c.X - W / 2) - (W / 2 - 22))
    point = (np.abs(c.Y - cy) + (np.abs(c.X - W / 2) - (W / 2 - 22 - (y1 - y0) / 2 * 0.9)) * 0.9) / 1.35 - (
        y1 - y0) / 2 / 1.35
    sd = np.maximum(sd_rect, point)
    body = dark_body(c, sd, seed=101, crack=False)
    band(c, sd, 0, 8, 2.4, IRON, 18, 0.5)
    band(c, sd, 0.3, 3.0, 1.5, GOLD, 30, 1.0)
    band(c, sd, 7, 2.4, 1.2, GOLD, 30, 0.9)
    m = np.zeros((c.h, c.w), np.float32)
    m = np.maximum(m, scroll(c, xl - 2, y0 + 2, 205, 30, -230, 4.5, 1.5, knob=2))
    m = np.maximum(m, scroll(c, xl - 2, y1 - 2, 155, 30, 230, 4.5, 1.5, knob=2))
    m = np.maximum(m, spike(c, 16, cy, 180, 14, 7))
    m = np.maximum(m, diamond(c, 26, cy, 7, 9))
    m = mirror_x(m)
    gold_shape(c, m, 1.4, 2.4, shadow=0.5, sdx=1, sdy=2, ssig=2)
    paint_gem(c, mirror_x(diamond(c, 26, cy, 3.2, 4.5)), (0.62, 0.06, 0.05))
    return c.image()


# ----------------------------------------------------------------------------------------------
# painting helpers for icons
# ----------------------------------------------------------------------------------------------

def paint(c, mask, base, radius=6.0, depth=6.0, spec=0.35, power=18, tex=0.06, tex_scale=4.0, rim=0.25,
          rim_col=(0.6, 0.75, 1.0), line=0.8, line_w=1.2, seed=1, light_col=None, shadow_hue=(0.55, 0.5, 0.8),
          height=None, flat=0.0, ao=0.25, cast=0.0):
    """Soft painterly shading of a mask: dome height from blur, warm key light upper-left,
    cool shadow hue, rim light on the far (lower-right) edge, spec, texture, thin dark line."""
    base = np.asarray(base, np.float32)
    if cast:
        c.shadow(mask, 2, 3, 3, cast)
    if line:
        ol = np.clip(c.blur(mask, line_w * 0.7) * 2.6, 0, 1)
        c.over(np.clip(base * 0.18, 0, 1), ol * line * (1 - mask))
    h = height if height is not None else emboss(c, mask, radius, depth)
    v, sp, (nx, ny, nz) = light(c, h, power, spec, 0.0)
    v = np.clip(v * (1 - flat) + 0.62 * flat, 0, 1.3)
    if tex:
        v = v * (1 + tex * fbm(c.h, c.w, tex_scale * c.k, 3, seed))
    dark = base * np.array(shadow_hue, np.float32) * 0.35
    lite = np.clip(base * 1.25 + (np.array(light_col, np.float32) if light_col is not None else
                                  np.array((0.12, 0.09, 0.04), np.float32)), 0, 1)
    t = v[..., None]
    col = np.where(t < 0.6, dark + (base - dark) * np.clip(t / 0.6, 0, 1),
                   base + (lite - base) * np.clip((t - 0.6) / 0.5, 0, 1))
    if ao:
        occl = 1 - ao * (1 - np.clip(c.blur(mask, radius * 0.8), 0, 1))
        col = col * occl[..., None]
    if rim:
        r = np.clip(nx * 0.7 + ny * 0.55, 0, 1) ** 1.5 * rim
        col = col + np.array(rim_col, np.float32) * r[..., None]
    col = col + sp[..., None] * np.array((1, 0.97, 0.9), np.float32)
    c.over(np.clip(col, 0, 1), mask)
    return h


def glow(c, mask, color, sigma, amt):
    c.add(np.array(color, np.float32), c.blur(mask, sigma) * amt)


def icon_bg(c, inner, outer, seed=1, rays=0, ray_col=None, center=(0.5, 0.5)):
    """Dark vignette background for skill icons (full opaque square)."""
    cx, cy = center[0] * c.W, center[1] * c.H
    r = np.hypot(c.X - cx, c.Y - cy) / (c.W * 0.72)
    t = np.clip(r, 0, 1) ** 1.2
    inner, outer = np.array(inner, np.float32), np.array(outer, np.float32)
    rgb = inner[None, None] * (1 - t[..., None]) + outer[None, None] * t[..., None]
    n = fbm(c.h, c.w, 40 * c.k, 4, seed)
    rgb = rgb * (1 + 0.28 * n)[..., None]
    if rays:
        ang = np.arctan2(c.Y - cy, c.X - cx)
        rr = (0.5 + 0.5 * np.sin(ang * rays + 1.3)) ** 6 * (1 - np.clip(r, 0, 1)) ** 1.5
        rgb = rgb + np.array(ray_col or inner, np.float32) * rr[..., None] * 0.5
    corner = np.clip((np.abs(c.X / c.W - 0.5) + np.abs(c.Y / c.H - 0.5)) - 0.55, 0, 1) * 1.6
    rgb = rgb * (1 - corner)[..., None]
    c.over(np.clip(rgb, 0, 1), np.ones((c.h, c.w), np.float32))


def seg_poly(p0, p1, w0, w1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    return [(p0[0] + nx * w0 / 2, p0[1] + ny * w0 / 2), (p1[0] + nx * w1 / 2, p1[1] + ny * w1 / 2),
            (p1[0] - nx * w1 / 2, p1[1] - ny * w1 / 2), (p0[0] - nx * w0 / 2, p0[1] - ny * w0 / 2)]


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def sword(c, p0, p1, w=26, steel=STEEL, glow_col=None, guard_col=GOLD, grip_len=0.3, guard_w=2.6,
          pommel=True, edge_glow=0.0, tip_frac=0.22, curve=0.0):
    """Painted sword from hilt point p0 (guard) to tip p1: two-tone blade halves (lit/unlit along
    the ridge), fuller line, gold guard, leather grip, pommel. Returns blade mask."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    tb = lerp2(p0, p1, 1 - tip_frac)
    half = w / 2
    left = [(p0[0] + nx * half, p0[1] + ny * half), (tb[0] + nx * half * 0.92, tb[1] + ny * half * 0.92), p1,
            tb, p0]
    right = [(p0[0] - nx * half, p0[1] - ny * half), (tb[0] - nx * half * 0.92, tb[1] - ny * half * 0.92), p1,
             tb, p0]
    ml, mr = c.poly(left), c.poly(right)
    blade = np.maximum(ml, mr)
    c.shadow(blade, 3, 4, 4, 0.55)
    ol = np.clip(c.blur(blade, 1.0) * 2.6, 0, 1)
    c.over(np.array((0.05, 0.06, 0.08), np.float32), ol * 0.9)
    # which half faces the light?
    lit_first = (nx * LIGHT[0] + ny * LIGHT[1]) < 0
    t = np.clip(((c.X - p0[0]) * ux + (c.Y - p0[1]) * uy) / L, 0, 1)
    shine = 0.5 + 0.3 * np.sin(t * 5.0 + 0.6)
    for m, lit in ((ml, not lit_first), (mr, lit_first)):
        v = (0.72 if lit else 0.36) + 0.18 * shine - 0.1 * t
        v = v + 0.04 * fbm(c.h, c.w, 6 * c.k, 2, 5)
        c.over(ramp(steel, np.clip(v, 0, 1)), m)
    # bright edge + ridge
    c.over(np.array((1, 1, 1), np.float32),
           stroke_mask(c, [lerp2(p0, p1, 0.02), p1], 1.6, 0.6) * 0.7)
    edge = stroke_mask(c, [(p0[0] + nx * half * 0.95 * (1 if lit_first else -1),
                            p0[1] + ny * half * 0.95 * (1 if lit_first else -1)),
                           (tb[0] + nx * half * 0.87 * (1 if lit_first else -1),
                            tb[1] + ny * half * 0.87 * (1 if lit_first else -1)), p1], 2.0, 1.0)
    c.over(np.array((1, 1, 1), np.float32), edge * blade * 0.85)
    if glow_col is not None and edge_glow:
        glow(c, blade, glow_col, 8, edge_glow)
    # guard
    g0 = (p0[0] + nx * w * guard_w / 2, p0[1] + ny * w * guard_w / 2)
    g1 = (p0[0] - nx * w * guard_w / 2, p0[1] - ny * w * guard_w / 2)
    gm = stroke_mask(c, [g0, (p0[0] - ux * 3, p0[1] - uy * 3), g1], w * 0.42, w * 0.42)
    gold_shape(c, gm, 2.5, 4, guard_col, shadow=0.5, line_w=1.2)
    # grip + pommel
    gl = L * grip_len
    q0 = (p0[0] - ux * w * 0.3, p0[1] - uy * w * 0.3)
    q1 = (p0[0] - ux * gl, p0[1] - uy * gl)
    grip = c.poly(seg_poly(q0, q1, w * 0.46, w * 0.42))
    paint(c, grip, hx("#5a3520"), 3, 4, spec=0.2, tex=0.2, tex_scale=2, rim=0.1)
    for i in range(1, 5):
        a = lerp2(q0, q1, i / 5)
        c.over(np.array((0.12, 0.07, 0.04), np.float32),
               stroke_mask(c, [(a[0] + nx * w * 0.22, a[1] + ny * w * 0.22), (a[0] - nx * w * 0.22 - ux * 3,
                                                                                a[1] - ny * w * 0.22 - uy * 3)],
                           1.4, 1.4) * grip)
    if pommel:
        pc = (q1[0] - ux * w * 0.28, q1[1] - uy * w * 0.28)
        pm = c.circle(pc[0], pc[1], w * 0.36)
        gold_shape(c, pm, 3, 4, guard_col, shadow=0.4)
    return blade


def fire_ramp(v):
    return ramp([(0.0, (0.0, 0.0, 0.0)), (0.2, hx("#5a0a02")), (0.4, hx("#c02a06")), (0.58, hx("#f06a10")),
                 (0.74, hx("#ffb030")), (0.88, hx("#ffe890")), (1.0, (1.0, 1.0, 0.94))], v)


def aniso_noise(c, sx, sy, angle, seed, octaves=3):
    """Noise stretched along `angle` (deg): sx along, sy across (file px)."""
    D = int(math.hypot(c.w, c.h)) + 8
    rng = np.random.default_rng(seed)
    out = np.zeros((D, D), np.float32)
    amp, tot = 1.0, 0
    for o in range(octaves):
        gx, gy = max(2, int(D / (sx * c.k)) + 3), max(2, int(D / (sy * c.k)) + 3)
        g = rng.standard_normal((gy, gx)).astype(np.float32)
        arr = np.asarray(Image.fromarray(g, "F").resize((D, D), Image.BICUBIC))
        out += amp * arr
        tot += amp
        amp *= 0.5
        sx, sy = sx / 2, sy / 2
    out /= tot
    im = Image.fromarray(out, "F").rotate(-angle, Image.BILINEAR)
    arr = np.asarray(im)
    oy, ox = (D - c.h) // 2, (D - c.w) // 2
    return arr[oy:oy + c.h, ox:ox + c.w]


def fire(c, env, angle=-90, seed=1, amt=1.0, streak=(40, 9), core=1.0):
    """Paint flames from an envelope field (0..1): streaky noise along `angle`, fire colour ramp,
    over + additive glow."""
    n = aniso_noise(c, streak[0], streak[1], angle, seed)
    n2 = aniso_noise(c, streak[0] * 0.5, streak[1] * 0.5, angle, seed + 1)
    f = np.clip(env * (0.75 + 0.55 * n + 0.3 * n2) * amt, 0, 1.2)
    f = np.clip(f * core, 0, 1)
    col = fire_ramp(f)
    a = smooth(0.12, 0.45, f)
    c.over(col, a)
    c.add(np.array((1.0, 0.45, 0.1), np.float32), c.blur(f, 10) * 0.55 * amt)
    return f


def bolt_path(p0, p1, seed, jag=0.22, depth=6):
    rng = np.random.default_rng(seed)
    pts = [p0, p1]
    for d in range(depth):
        new = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            nx, ny = -(b[1] - a[1]) / (L or 1), (b[0] - a[0]) / (L or 1)
            off = rng.normal(0, jag) * L
            new += [(mx + nx * off, my + ny * off), b]
        pts = new
    return pts


def lightning(c, p0, p1, seed, width=5.0, col=(0.55, 0.75, 1.0), branches=3, jag=0.2):
    rng = np.random.default_rng(seed + 100)
    paths = [(bolt_path(p0, p1, seed, jag), width)]
    for i in range(branches):
        main = paths[0][0]
        j = rng.integers(len(main) // 5, len(main) * 3 // 4)
        a = main[j]
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0]) + rng.choice([-1, 1]) * rng.uniform(0.4, 0.9)
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) * rng.uniform(0.2, 0.4)
        b = (a[0] + math.cos(ang) * L, a[1] + math.sin(ang) * L)
        paths.append((bolt_path(a, b, seed + i + 7, jag, 5), width * 0.55))
    m = np.zeros((c.h, c.w), np.float32)
    for pts, w in paths:
        m = np.maximum(m, stroke_mask(c, pts, w, w * 0.4))
    glow(c, m, col, 14, 1.1)
    glow(c, m, col, 5, 1.2)
    c.over(np.array((0.92, 0.97, 1.0), np.float32), m)
    return m


def sparks(c, n, cx, cy, rad, col, seed, size=(1.5, 3.5), spread=1.0, streak=0.0, angle=None):
    rng = np.random.default_rng(seed)
    m = np.zeros((c.h, c.w), np.float32)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi) if angle is None else math.radians(angle) + rng.normal(0, 0.5)
        d = rng.uniform(0.2, 1.0) ** 0.7 * rad * spread
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        r = rng.uniform(*size)
        if streak:
            m = np.maximum(m, stroke_mask(c, [(x, y), (x + math.cos(a) * streak * r, y + math.sin(a) * streak * r)],
                                          r, 0.2) * rng.uniform(0.5, 1))
        else:
            m = np.maximum(m, c.circle(x, y, r) * rng.uniform(0.5, 1))
    glow(c, m, col, 3, 1.2)
    c.add(np.array((1, 1, 1), np.float32), m * 0.9)
    return m


def swirl_arms(c, cx, cy, R, arms, turns, width, col, seed=1, ccw=False, amt=1.0, core=True, inner=0.12):
    """Luminous spiral arms (vortex)."""
    m = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(seed)
    for i in range(arms):
        a0 = 2 * math.pi * i / arms + rng.uniform(-0.2, 0.2)
        pts = []
        for j in range(120):
            t = j / 119
            r = R * (inner + (1 - inner) * t)
            a = a0 + (1 if not ccw else -1) * turns * 2 * math.pi * (1 - t) * 0.5 + t * 0.4
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        m = np.maximum(m, stroke_mask(c, pts, width * 0.3, width, prof=lambda t: math.sin(math.pi * t) ** 0.6 + 0.15)
                       * rng.uniform(0.7, 1.0))
    glow(c, m, col, 10, 0.9 * amt)
    c.add(np.array(col, np.float32), m * 0.9 * amt)
    c.add(np.array((1, 1, 1), np.float32), np.clip(m - 0.4, 0, 1) * 0.8 * amt)
    if core:
        cm = c.circle(cx, cy, R * 0.16)
        glow(c, cm, col, R * 0.25, 1.4 * amt)
        c.add(np.array((1, 1, 1), np.float32), c.blur(cm, R * 0.06) * 1.2 * amt)
    return m


def facet_poly(c, pts, center, base, light_bias=0.0, edge=0.7, gl=None):
    """Faceted crystal: triangles from center to each edge, each with its own value from its normal."""
    base = np.asarray(base, np.float32)
    n = len(pts)
    full = c.poly(pts)
    c.shadow(full, 2, 3, 3, 0.5)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        tri = c.poly([center, a, b])
        mx, my = (a[0] + b[0]) / 2 - center[0], (a[1] + b[1]) / 2 - center[1]
        L = math.hypot(mx, my) or 1
        d = -(mx / L * LIGHT[0] + my / L * LIGHT[1])
        v = 0.55 + 0.45 * d + light_bias + 0.08 * math.sin(i * 2.3)
        col = np.clip(base * (0.35 + 0.9 * v) + max(0, v - 0.8) * 0.8, 0, 1)
        grad = 1 + 0.15 * (1 - np.clip(np.hypot(c.X - center[0], c.Y - center[1]) / 60, 0, 1))
        c.over(np.clip(col[None, None] * grad[..., None], 0, 1), tri)
    lines = np.zeros((c.h, c.w), np.float32)
    for i in range(n):
        lines = np.maximum(lines, stroke_mask(c, [center, pts[i]], 1.0, 0.6))
        lines = np.maximum(lines, stroke_mask(c, [pts[i], pts[(i + 1) % n]], 1.2, 1.2))
    c.over(np.array((1, 1, 1), np.float32), lines * full * edge)
    if gl is not None:
        glow(c, full, gl, 10, 0.6)
    return full


def figure(c, cx, cy, s=1.0, lean=0.0, arm=0.0):
    """Hooded cloaked figure silhouette mask (standing, ~140*s tall, head top at cy)."""
    def P(x, y):
        return cx + (x + lean * (y / 140)) * s, cy + y * s
    hood = c.poly([P(-18, 12), P(-12, -2), P(0, -6), P(12, -2), P(19, 12), P(22, 30), P(-22, 30)])
    head = c.ellipse([P(-16, -2)[0], P(0, -2)[1], P(16, 0)[0], P(0, 34)[1]])
    body = c.poly([P(-24, 28), P(24, 28), P(36, 70), P(46, 140), P(20, 128), P(0, 140), P(-20, 128), P(-48, 140),
                   P(-38, 70)])
    arms = c.poly([P(22, 34), P(48 + arm, 60 - arm), P(58 + arm * 1.4, 84 - arm * 1.5), P(46 + arm, 86 - arm),
                   P(36, 62)])
    arms2 = c.poly([P(-22, 34), P(-46, 62), P(-54, 88), P(-42, 88), P(-34, 64)])
    return np.maximum.reduce([hood, head, body, arms, arms2])


# ----------------------------------------------------------------------------------------------
# menu / item icons (256 x 256, transparent, painted objects)
# ----------------------------------------------------------------------------------------------

LEATHER = hx("#8c5a30")


def dashes(c, pts, dash=5.0, gap=4.0, w=1.6):
    """Dashed stitch line along a polyline."""
    segs, acc, on = [], 0.0, True
    cur = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        pos = 0.0
        while pos < L:
            lim = dash if on else gap
            step = min(lim - acc, L - pos)
            pos += step
            acc += step
            p = lerp2(a, b, pos / L if L else 0)
            if on:
                cur.append(p)
            if acc >= lim - 1e-6:
                if on:
                    segs.append(cur)
                on = not on
                acc = 0.0
                cur = [p]
    m = np.zeros((c.h, c.w), np.float32)
    for sgm in segs:
        if len(sgm) >= 2:
            m = np.maximum(m, stroke_mask(c, sgm, w, w))
    return m


def rrect_pts(x0, y0, x1, y1, r, n=8):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def icon_bag():
    c = Canvas(256, 256)
    body = c.fill(c.sd_rrect(56, 74, 200, 228, 36))
    c.shadow(body, 3, 5, 5, 0.6)
    # handle loop
    loop = stroke_mask(c, scroll_path(98, 84, 270, 90, 0, bend=180), 13, 13)
    paint(c, loop, shade3(LEATHER, 0.7), 3, 4, spec=0.3, tex=0.2, tex_scale=2)
    paint(c, body, LEATHER, 14, 14, spec=0.25, tex=0.22, tex_scale=3, seed=3)
    pocket = c.fill(c.sd_rrect(78, 162, 178, 218, 18))
    paint(c, pocket, shade3(LEATHER, 1.08), 8, 6, spec=0.25, tex=0.2, tex_scale=3, seed=4, cast=0.4)
    c.over(np.array(hx("#f0d8a8"), np.float32), dashes(c, rrect_pts(84, 168, 172, 212, 13), 5, 4, 1.8) * 0.75)
    # flap
    flap_sd = c.sd_rrect(58, 76, 198, 150, 34)
    flap = c.fill(np.maximum(flap_sd, 0 * flap_sd))
    paint(c, flap, shade3(LEATHER, 1.15), 10, 8, spec=0.3, tex=0.22, tex_scale=3, seed=5, cast=0.55)
    c.over(np.array(hx("#f0d8a8"), np.float32), dashes(c, rrect_pts(66, 84, 190, 142, 26), 5, 4, 1.8) * 0.75)
    # strap + buckle
    strap = c.fill(c.sd_rrect(116, 118, 140, 204, 4))
    paint(c, strap, shade3(LEATHER, 0.6), 4, 4, spec=0.2, tex=0.2, tex_scale=2, seed=6, cast=0.45)
    bk_o = c.fill(c.sd_rrect(106, 136, 150, 170, 6))
    bk_i = c.fill(c.sd_rrect(114, 144, 142, 162, 3))
    gold_shape(c, bk_o * (1 - bk_i), 2, 3, GOLD, shadow=0.5)
    pin = stroke_mask(c, [(128, 140), (128, 166)], 3.2, 3.2)
    gold_shape(c, pin, 1.2, 2, GOLD, shadow=0.3)
    return c.image()


def shade3(col, f):
    return tuple(min(1.0, x * f) for x in col)


def icon_quests():
    c = Canvas(256, 256)
    sheet = c.poly([(72, 60), (184, 60), (184, 198), (72, 198)])
    c.shadow(sheet, 3, 5, 5, 0.55)
    pr = parchment(c, 33)
    c.over(pr * (1.05 - 0.2 * smooth(60, 200, c.Y))[..., None], sheet)
    inner_shadow(c, sheet, 6, 0.35, 0, 0, (0.3, 0.18, 0.05))
    rng = np.random.default_rng(4)
    lines = np.zeros((c.h, c.w), np.float32)
    for i, y in enumerate(range(88, 176, 13)):
        x1 = 170 - rng.uniform(0, 30) if i % 3 == 2 else 168
        pts = [(86 + t * (x1 - 86), y + math.sin(t * 17 + i) * 1.2) for t in np.linspace(0, 1, 30)]
        lines = np.maximum(lines, stroke_mask(c, pts, 2.6, 2.6))
    c.over(np.array(hx("#5a3a1c"), np.float32), lines * 0.7)
    for y0 in (40, 184):
        roll = c.fill(c.sd_rrect(60, y0, 196, y0 + 30, 15))
        h = np.sqrt(np.clip(1 - ((c.Y - (y0 + 15)) / 15) ** 2, 0, 1)) * 10 * roll
        paint(c, roll, hx("#dcc38e"), height=h, spec=0.2, tex=0.12, tex_scale=3, seed=y0, cast=0.5)
        for ex in (60, 196):
            end = c.ellipse((ex - 6, y0, ex + 6, y0 + 30))
            paint(c, end, hx("#9c7a48"), 3, 3, spec=0.1, tex=0.1)
            c.over(np.array(hx("#5a3e1c"), np.float32), stroke_mask(c, scroll_path(ex, y0 + 15, 270, 18, 500, power=1.2), 1.4, 1.0) * end)
    # wax seal with ribbon tails
    for dx, a in ((-8, 100), (8, 80)):
        tail = c.poly(seg_poly((176 + dx * 0.3, 196), (176 + dx * 2.2, 238), 14, 12))
        paint(c, tail, hx("#8a1414"), 4, 3, spec=0.3, tex=0.1, cast=0.3)
    ang = np.arctan2(c.Y - 188, c.X - 176)
    rr = np.hypot(c.X - 176, c.Y - 188)
    seal = c.fill(rr - (25 + 2.2 * np.sin(ang * 9) + 1.2 * np.sin(ang * 23 + 1)))
    paint(c, seal, hx("#b01c1c"), 6, 8, spec=0.9, power=40, tex=0.08, cast=0.6)
    ring = c.fill(np.abs(rr - 14) - 2)
    c.over(np.array(hx("#6a0a0a"), np.float32), ring * 0.7)
    star = c.poly([(176 + math.cos(math.radians(-90 + i * 36)) * (9 if i % 2 == 0 else 4),
                    188 + math.sin(math.radians(-90 + i * 36)) * (9 if i % 2 == 0 else 4)) for i in range(10)])
    c.over(np.array(hx("#e04040"), np.float32), star * 0.8)
    return c.image()


def compass_star(c, cx, cy, R, r2, w, w2, stops=GOLD, red=True, rot=0.0):
    m_all = np.zeros((c.h, c.w), np.float32)
    parts = []
    for i in range(8):
        a = math.radians(rot - 90 + i * 45)
        L, ww = (R, w) if i % 2 == 0 else (r2, w2)
        tip = (cx + math.cos(a) * L, cy + math.sin(a) * L)
        s1 = (cx + math.cos(a + math.pi / 2) * ww, cy + math.sin(a + math.pi / 2) * ww)
        s2 = (cx + math.cos(a - math.pi / 2) * ww, cy + math.sin(a - math.pi / 2) * ww)
        parts.append((i, a, [ (cx, cy), s1, tip], [(cx, cy), tip, s2]))
    # diagonals first (behind)
    order = [p for p in parts if p[0] % 2 == 1] + [p for p in parts if p[0] % 2 == 0]
    for i, a, h1, h2 in order:
        m1, m2 = c.poly(h1), c.poly(h2)
        m = np.maximum(m1, m2)
        c.shadow(m, 2, 3, 3, 0.45)
        ol = np.clip(c.blur(m, 0.9) * 2.6, 0, 1)
        c.over(np.array((0.1, 0.06, 0.02), np.float32), ol * 0.8 * (1 - m))
        for mm, sgn in ((m1, 1), (m2, -1)):
            na = a + sgn * math.pi / 2
            d = -(math.cos(na) * LIGHT[0] + math.sin(na) * LIGHT[1])
            v = 0.5 + 0.35 * d
            t = np.clip(np.hypot(c.X - cx, c.Y - cy) / R, 0, 1)
            vv = v + 0.12 * (1 - t) + 0.03 * fbm(c.h, c.w, 5 * c.k, 2, i)
            st = stops
            if red and i == 0:
                st = [(0, hx("#2a0404")), (0.4, hx("#8a1010")), (0.7, hx("#e03a2a")), (1, hx("#ffb0a0"))]
            c.over(ramp(st, np.clip(vv, 0, 1)), mm)
        m_all = np.maximum(m_all, m)
    return m_all


def icon_map():
    c = Canvas(256, 256)
    cx = cy = 128
    ring = c.fill(np.abs(np.hypot(c.X - cx, c.Y - cy) - 70) - 5)
    gold_shape(c, ring, 2, 3, GOLD, shadow=0.5)
    ticks = np.zeros((c.h, c.w), np.float32)
    for i in range(16):
        a = math.radians(i * 22.5)
        ticks = np.maximum(ticks, c.circle(cx + math.cos(a) * 70, cy + math.sin(a) * 70, 2.6))
    c.over(np.array(hx("#fff0c0"), np.float32), ticks * 0.8)
    compass_star(c, cx, cy, 112, 70, 20, 13)
    hub = c.circle(cx, cy, 14)
    gold_shape(c, hub, 3, 4, GOLD, shadow=0.5)
    paint_gem(c, c.circle(cx, cy, 7), (0.75, 0.1, 0.06))
    return c.image()


def gear_mask(c, cx, cy, Rout, Rin, teeth, hole, rot=0.0, soft=0.06):
    ang = np.arctan2(c.Y - cy, c.X - cx) - math.radians(rot)
    t = (ang * teeth / (2 * math.pi)) % 1.0
    prof = np.clip((0.32 - np.abs(t - 0.5)) / soft, 0, 1)
    redge = Rin + (Rout - Rin) * prof
    rr = np.hypot(c.X - cx, c.Y - cy)
    return c.fill(rr - redge) * c.fill(hole - rr)


BRONZE = [(0.0, hx("#150c05")), (0.2, hx("#3e2812")), (0.42, hx("#6e4a24")), (0.6, hx("#a07440")),
          (0.76, hx("#cfa468")), (0.9, hx("#f0d6a0")), (1.0, hx("#fff6e0"))]


def icon_settings():
    c = Canvas(256, 256)
    cx = cy = 128
    g = gear_mask(c, cx, cy, 104, 80, 10, 30, rot=9)
    c.shadow(g, 3, 5, 5, 0.6)
    ol = np.clip(c.blur(g, 1.0) * 2.6, 0, 1)
    c.over(np.array((0.08, 0.05, 0.02), np.float32), ol * 0.9 * (1 - g))
    rr = np.hypot(c.X - cx, c.Y - cy)
    h = emboss(c, g, 5, 6) + 3 * smooth(48, 60, rr) * (1 - smooth(60, 66, rr)) * 0
    groove = c.fill(np.abs(rr - 58) - 3)
    h = h - groove * 2.5
    rgb = metal(c, g, h, BRONZE, 26, 0.9, tex=0.05, seed=4, sheen=0.08 * (1 - rr / 110))
    c.over(rgb, g)
    inner = c.fill(np.abs(rr - 38) - 4) * g
    c.over(np.array((0, 0, 0), np.float32), c.blur(inner, 2) * 0.25)
    return c.image()


def icon_potion():
    c = Canvas(256, 256)
    cx = 128
    body = c.circle(cx, 164, 66)
    neck = c.fill(c.sd_rrect(106, 60, 150, 120, 6))
    glass = np.maximum(body, neck)
    c.shadow(glass, 3, 6, 6, 0.6)
    # dark glass back
    c.over(np.array((0.08, 0.04, 0.07), np.float32), glass * 0.85)
    # liquid with wavy surface
    surf = 128 + 3 * np.sin(c.X / 9.0)
    liq = body * smooth(surf - 0.5, surf + 0.5, c.Y) * c.fill(np.hypot(c.X - cx, c.Y - 164) - 60)
    rr = np.hypot(c.X - cx + 8, c.Y - 176) / 60
    lcol = ramp([(0, hx("#ffd0c0")), (0.25, hx("#ff4a3a")), (0.6, hx("#c0101c")), (1, hx("#4a0210"))],
                np.clip(rr, 0, 1))
    c.over(lcol, liq)
    bub = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(3)
    for _ in range(9):
        x, y, r = rng.uniform(96, 160), rng.uniform(140, 210), rng.uniform(2, 5)
        bub = np.maximum(bub, c.fill(np.abs(np.hypot(c.X - x, c.Y - y) - r) - 0.8))
    c.add(np.array((1, 0.7, 0.6), np.float32), bub * liq * 0.7)
    glow(c, liq, (1.0, 0.2, 0.12), 14, 0.55)
    c.over(np.array((1, 0.6, 0.55), np.float32), c.fill(np.abs(c.Y - surf) - 1.2) * body * 0.6)
    # glass rim + highlights
    edge = np.clip(glass - c.blur(glass, 3) * 0.9, 0, 1)
    c.over(np.array((0.8, 0.85, 0.95), np.float32), c.blur(edge, 1) * 0.7)
    hl = stroke_mask(c, scroll_path(84, 186, 268, 70, 50, bend=0), 9, 3)
    c.add(np.array((1, 1, 1), np.float32), c.blur(hl, 1.5) * body * 0.75)
    c.add(np.array((1, 1, 1), np.float32), c.fill(c.sd_rrect(114, 70, 120, 112, 3)) * 0.5)
    c.add(np.array((1, 0.6, 0.5), np.float32), c.blur(stroke_mask(c, scroll_path(186, 170, 100, 40, 0, bend=60), 4, 2), 2) * 0.5)
    lip = c.fill(c.sd_rrect(100, 56, 156, 70, 7))
    gold_shape(c, lip, 3, 4, GOLD, shadow=0.4)
    cork = c.fill(c.sd_rrect(110, 26, 146, 60, 6))
    paint(c, cork, hx("#b07a44"), 6, 6, spec=0.15, tex=0.35, tex_scale=2, seed=8, cast=0.4)
    return c.image()


def heater_pts(x0, y0, x1, y1, n=28, straight=0.38):
    cx, hw = (x0 + x1) / 2, (x1 - x0) / 2
    right = []
    for i in range(n + 1):
        t = i / n
        y = y0 + (y1 - y0) * t
        if t <= straight:
            off = hw
        else:
            u = (t - straight) / (1 - straight)
            off = hw * math.sqrt(max(0.0, 1 - u ** 1.6))
        right.append((cx + off, y))
    left = [(2 * cx - x, y) for x, y in reversed(right)]
    return [(x0, y0 - 0.01)] + right + left[1:]


def shield_icon(c, x0, y0, x1, y1, field=hx("#1e3f8a"), rim=STEEL, emblem=True, crack=False, glow_col=None):
    outer = c.poly(heater_pts(x0, y0, x1, y1))
    w = x1 - x0
    b = w * 0.09
    inner = c.poly(heater_pts(x0 + b, y0 + b, x1 - b, y1 - b * 1.8))
    c.shadow(outer, 3, 6, 6, 0.6)
    ol = np.clip(c.blur(outer, 1.0) * 2.6, 0, 1)
    c.over(np.array((0.04, 0.05, 0.07), np.float32), ol * 0.9 * (1 - outer))
    h = emboss(c, outer, w * 0.05, w * 0.06) + emboss(c, inner, w * 0.12, w * 0.08)
    rgb = metal(c, outer, h, rim, 30, 1.0, tex=0.05)
    c.over(rgb, outer)
    fh = emboss(c, inner, w * 0.18, w * 0.12)
    v, sp, _ = light(c, fh, 20, 0.6, 0.1)
    fcol = np.array(field, np.float32)
    col = fcol[None, None] * (0.35 + 0.95 * v[..., None]) + sp[..., None] * 0.9
    col = col * (1 + 0.08 * fbm(c.h, c.w, 6 * c.k, 3, 9))[..., None]
    c.over(np.clip(col, 0, 1), inner)
    inner_shadow(c, inner, 3, 0.5, 1, 2)
    if emblem:
        cx = (x0 + x1) / 2
        cy = y0 + (y1 - y0) * 0.42
        s = w / 140
        em = np.maximum(c.poly(seg_poly((cx, cy - 44 * s), (cx, cy + 50 * s), 16 * s, 12 * s)),
                        c.poly(seg_poly((cx - 38 * s, cy - 8 * s), (cx + 38 * s, cy - 8 * s), 14 * s, 14 * s)))
        em = np.maximum(em, diamond(c, cx, cy - 8 * s, 16 * s, 16 * s))
        gold_shape(c, em, 2.5 * s, 4 * s, GOLD, shadow=0.5)
    if glow_col is not None:
        glow(c, outer, glow_col, 12, 0.5)
    return outer


def icon_defend():
    c = Canvas(256, 256)
    shield_icon(c, 52, 34, 204, 232)
    return c.image()


def icon_flee():
    c = Canvas(256, 256)
    # speed streaks
    st = np.zeros((c.h, c.w), np.float32)
    for y, x0, L in ((120, 14, 70), (150, 6, 80), (180, 20, 64), (205, 30, 50)):
        st = np.maximum(st, stroke_mask(c, [(x0, y), (x0 + L, y)], 1.0, 7))
    c.add(np.array((0.75, 0.9, 1.0), np.float32), c.blur(st, 1) * 0.8)
    boot = c.poly([(104, 52), (160, 52), (158, 150), (206, 176), (214, 206), (210, 214), (92, 214), (96, 170)])
    c.shadow(boot, 3, 5, 5, 0.6)
    paint(c, boot, hx("#7a4a26"), 14, 12, spec=0.35, tex=0.2, tex_scale=3, seed=2)
    sole = c.poly([(90, 206), (212, 206), (216, 214), (212, 226), (92, 226), (88, 214)])
    paint(c, sole, hx("#3a2616"), 3, 3, spec=0.2, tex=0.1, cast=0.4)
    cuff = c.fill(c.sd_rrect(98, 44, 166, 70, 8))
    paint(c, cuff, hx("#a06a3a"), 5, 5, spec=0.3, tex=0.2, tex_scale=2, cast=0.5)
    c.over(np.array(hx("#f0d8a8"), np.float32), dashes(c, [(106, 78), (106, 150), (150, 174), (200, 186)], 5, 4, 1.8) * 0.7)
    # wing: feathers sweeping back from the ankle
    wing = np.zeros((c.h, c.w), np.float32)
    for i, (ang, L, w) in enumerate(((205, 86, 22), (190, 96, 22), (175, 88, 20), (160, 70, 18))):
        wing = np.maximum(wing, leaf(c, 112, 100 + i * 4, ang, L, w, bend=-(25 + i * 6)))
    paint(c, wing, hx("#f4efe4"), 5, 5, spec=0.5, tex=0.06, rim=0.3, rim_col=(0.6, 0.8, 1.0), cast=0.5, seed=5)
    ln = np.zeros((c.h, c.w), np.float32)
    for i, (ang, L) in enumerate(((205, 70), (190, 80), (175, 72))):
        ln = np.maximum(ln, stroke_mask(c, scroll_path(112, 102 + i * 4, ang, L, 0, bend=-(25 + i * 6)), 1.3, 0.5))
    c.over(np.array(hx("#9aa0b0"), np.float32), ln * 0.8)
    gm = c.circle(116, 104, 9)
    gold_shape(c, gm, 2, 3, GOLD, shadow=0.4)
    return c.image()


def icon_dragon():
    c = Canvas(256, 256)
    red = hx("#b3231a")
    # horns behind the head
    horns = np.maximum(stroke_mask(c, scroll_path(98, 92, 205, 92, -40, bend=-20), 22, 2),
                       stroke_mask(c, scroll_path(120, 84, 225, 84, -30, bend=-30), 18, 2))
    paint(c, horns, hx("#e6d2a0"), 5, 5, spec=0.4, tex=0.15, tex_scale=2, cast=0.5, rim=0.2)
    head = c.poly([(58, 118), (84, 92), (128, 80), (170, 92), (212, 114), (226, 124), (224, 138), (176, 142),
                   (138, 148), (180, 158), (206, 164), (198, 178), (150, 190), (118, 206), (112, 246), (40, 246),
                   (44, 190), (50, 150)])
    # neck frills / spikes along the back of the neck
    fr = np.zeros((c.h, c.w), np.float32)
    for i, (x, y) in enumerate(((52, 140), (44, 170), (40, 200), (38, 228))):
        fr = np.maximum(fr, spike(c, x + 6, y, 200 - i * 6, 28, 16))
    paint(c, fr, hx("#7a1510"), 4, 4, spec=0.3, tex=0.1, cast=0.4)
    c.shadow(head, 3, 5, 6, 0.6)
    paint(c, head, red, 16, 14, spec=0.45, power=22, tex=0.28, tex_scale=2.2, seed=7, rim=0.35,
          rim_col=(1.0, 0.6, 0.3))
    # jaw underside + belly plates
    belly = c.poly([(120, 204), (150, 190), (198, 178), (206, 166), (176, 160), (140, 150), (112, 170), (104, 246),
                    (118, 246)])
    paint(c, belly * head, hx("#e09a48"), 8, 6, spec=0.3, tex=0.15, line=0, cast=0)
    for y in (196, 214, 232):
        c.over(np.array(hx("#8a4a1a"), np.float32), stroke_mask(c, [(106, y), (124, y - 8)], 1.8, 1.8) * head * 0.7)
    # mouth line + teeth
    mouth = stroke_mask(c, [(224, 138), (176, 144), (140, 150)], 3.2, 2)
    c.over(np.array((0.15, 0.02, 0.02), np.float32), mouth)
    teeth = np.zeros((c.h, c.w), np.float32)
    for x in (212, 196, 180, 164):
        teeth = np.maximum(teeth, c.poly([(x - 4, 140), (x + 4, 140), (x, 152)]))
    paint(c, teeth, hx("#f6f0e0"), 1.5, 2, spec=0.5, line=0.5, cast=0)
    # brow ridge + eye
    brow = leaf(c, 136, 98, 10, 44, 12, bend=15)
    paint(c, brow, hx("#8a1812"), 4, 5, spec=0.4, tex=0.1, cast=0.4)
    eye = c.poly([(150, 108), (162, 103), (176, 108), (162, 114)])
    c.over(np.array(hx("#ffcc40"), np.float32), eye)
    c.over(np.array((0.1, 0.02, 0), np.float32), c.fill(np.abs(c.X - 162) - 1.6) * eye)
    glow(c, eye, (1.0, 0.7, 0.2), 6, 1.0)
    # nostril + scale texture hints
    c.over(np.array((0.2, 0.03, 0.02), np.float32), c.ellipse((208, 116, 216, 121)))
    sc = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(5)
    for _ in range(40):
        x, y = rng.uniform(60, 180), rng.uniform(100, 200)
        sc = np.maximum(sc, stroke_mask(c, scroll_path(x, y, 60, 9, 120), 1.5, 1.0))
    c.over(np.array((0.35, 0.05, 0.03), np.float32), sc * head * (1 - belly) * 0.6)
    return c.image()


def coin(c, cx, cy, r, tilt=1.0, thick=6):
    """Gold coin, tilt = vertical squash (1 = face on)."""
    ry = r * tilt
    edge = np.maximum(c.ellipse((cx - r, cy - ry + thick, cx + r, cy + ry + thick)),
                      c.fill(np.maximum(np.abs(c.X - cx) - r, np.maximum(cy - c.Y, c.Y - cy - thick))))
    c.shadow(edge, 2, 3, 3, 0.5)
    side = metal(c, edge, np.zeros((c.h, c.w), np.float32), GOLD, sheen=-0.1 + 0.25 * (1 - np.abs(c.X - cx) / r))
    c.over(side, edge)
    # milled edge
    c.over(np.array((0.3, 0.18, 0.04), np.float32),
           edge * (0.5 + 0.5 * np.sin(c.X * 2.2)) * 0.35)
    face = c.ellipse((cx - r, cy - ry, cx + r, cy + ry))
    rr = np.hypot((c.X - cx) / r, (c.Y - cy) / ry)
    h = (smooth(0.78, 0.86, rr) * (1 - smooth(0.9, 1.0, rr))) * 3 + (1 - smooth(0.0, 0.8, rr)) * 1.5
    c.over(metal(c, face, h, GOLD, 30, 0.9, sheen=0.1 * (1 - rr)), face)
    return face


def icon_gold():
    c = Canvas(256, 256)
    for i in range(5):
        coin(c, 100, 196 - i * 16, 58, 0.36, 12)
    for i in range(3):
        coin(c, 178, 206 - i * 16, 48, 0.36, 12)
    cx, cy, r = 150, 118, 58
    f = coin(c, cx, cy, r, 1.0, 0)
    star = c.poly([(cx + math.cos(math.radians(-90 + i * 36)) * (30 if i % 2 == 0 else 13),
                    cy + math.sin(math.radians(-90 + i * 36)) * (30 if i % 2 == 0 else 13)) for i in range(10)])
    gold_shape(c, star, 3, 4, GOLD, shadow=0.35, sdx=1, sdy=1.5, ssig=1.5)
    sparks(c, 1, 116, 84, 1, (1, 0.9, 0.6), 3, size=(5, 5))
    return c.image()


def icon_gem():
    c = Canvas(256, 256)
    cx = 128
    base = np.array(hx("#b42ee0"), np.float32)
    tops = [(62, 100), (92, 62), (164, 62), (194, 100)]
    girdle_y = 100
    table = [(104, 70), (152, 70)]
    bottom = (cx, 222)
    full = c.poly([(62, 100), (92, 62), (164, 62), (194, 100), bottom])
    c.shadow(full, 3, 6, 6, 0.6)
    ol = np.clip(c.blur(full, 1.0) * 2.6, 0, 1)
    c.over(np.array((0.1, 0.02, 0.14), np.float32), ol * (1 - full))
    facets = [
        ([(92, 62), (164, 62), (152, 74), (104, 74)], 1.05),   # table
        ([(62, 100), (92, 62), (104, 74), (96, 100)], 0.95),
        ([(104, 74), (152, 74), (160, 100), (96, 100)], 0.85),
        ([(152, 74), (164, 62), (194, 100), (160, 100)], 0.55),
        ([(62, 100), (96, 100), bottom], 0.62),
        ([(96, 100), (128, 100), bottom], 0.8),
        ([(128, 100), (160, 100), bottom], 0.45),
        ([(160, 100), (194, 100), bottom], 0.3),
    ]
    for pts, v in facets:
        m = c.poly(pts)
        ys = np.clip((c.Y - 60) / 160, 0, 1)
        col = base[None, None] * (0.3 + 0.9 * v - 0.25 * ys)[..., None] + max(0, v - 0.85) * 0.9
        c.over(np.clip(col, 0, 1), m)
    lines = np.zeros((c.h, c.w), np.float32)
    for a, b in (((62, 100), (194, 100)), ((104, 74), (152, 74)), ((92, 62), (104, 74)), ((164, 62), (152, 74)),
                 ((104, 74), (96, 100)), ((152, 74), (160, 100)), ((96, 100), bottom), ((128, 100), bottom),
                 ((160, 100), bottom)):
        lines = np.maximum(lines, stroke_mask(c, [a, b], 1.4, 1.4))
    c.over(np.array((1, 0.85, 1), np.float32), lines * full * 0.6)
    glow(c, full, (0.8, 0.3, 1.0), 12, 0.35)
    sparks(c, 1, 102, 66, 1, (1, 0.9, 1), 3, size=(6, 6))
    star = np.zeros((c.h, c.w), np.float32)
    for a in (0, 90):
        star = np.maximum(star, stroke_mask(c, [(100 - 16 * math.cos(math.radians(a)), 68 - 16 * math.sin(math.radians(a))),
                                               (100 + 16 * math.cos(math.radians(a)), 68 + 16 * math.sin(math.radians(a)))],
                                            2.4, 2.4, prof=lambda t: math.sin(math.pi * t)))
    c.add(np.array((1, 1, 1), np.float32), star)
    return c.image()


MENU_ICONS = {
    "icon_bag.png": icon_bag, "icon_quests.png": icon_quests, "icon_map.png": icon_map,
    "icon_settings.png": icon_settings, "icon_potion.png": icon_potion, "icon_defend.png": icon_defend,
    "icon_flee.png": icon_flee, "icon_dragon.png": icon_dragon, "icon_gold.png": icon_gold, "icon_gem.png": icon_gem,
}


# ----------------------------------------------------------------------------------------------
# skill icons (256 x 256, opaque, dark vignette + luminous central motif, no frame)
# ----------------------------------------------------------------------------------------------

def rot_pts(pts, cx, cy, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def arc_pts(cx, cy, r, a0, a1, n=60):
    return [(cx + math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))) * r,
             cy + math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1))) * r) for i in range(n)]


def slash_arc(c, cx, cy, r, a0, a1, width, col, core=(1, 1, 0.9), amt=1.0):
    pts = arc_pts(cx, cy, r, a0, a1, 90)
    m = stroke_mask(c, pts, 0.5, 0.5, prof=lambda t: width * math.sin(math.pi * t) ** 0.8 + 0.3, cap=False)
    glow(c, m, col, 12, 1.0 * amt)
    c.add(np.array(col, np.float32), m * 0.9 * amt)
    inner = stroke_mask(c, pts, 0.3, 0.3, prof=lambda t: width * 0.45 * math.sin(math.pi * t) ** 1.2, cap=False)
    c.add(np.array(core, np.float32), c.blur(inner, 0.8) * 1.2 * amt)
    return m


def dagger(c, p0, p1, w=20, glow_col=None, edge_glow=0.0, steel=STEEL, guard=GOLD):
    return sword(c, p0, p1, w, steel, glow_col, guard, grip_len=0.36, guard_w=2.2, edge_glow=edge_glow,
                 tip_frac=0.35)


def skull(c, cx, cy, s, col=hx("#e8dcc0"), glow_col=None):
    cran = c.ellipse((cx - 34 * s, cy - 36 * s, cx + 34 * s, cy + 26 * s))
    jaw = c.fill(c.sd_rrect(cx - 20 * s, cy + 8 * s, cx + 20 * s, cy + 40 * s, 8 * s))
    m = np.maximum(cran, jaw)
    paint(c, m, col, 8 * s, 8 * s, spec=0.3, tex=0.12, cast=0.5)
    holes = np.maximum(c.ellipse((cx - 24 * s, cy - 8 * s, cx - 6 * s, cy + 10 * s)),
                       c.ellipse((cx + 6 * s, cy - 8 * s, cx + 24 * s, cy + 10 * s)))
    holes = np.maximum(holes, c.poly([(cx, cy + 12 * s), (cx - 5 * s, cy + 22 * s), (cx + 5 * s, cy + 22 * s)]))
    c.over(np.array((0.06, 0.02, 0.02), np.float32), holes)
    for i in range(-2, 3):
        c.over(np.array((0.2, 0.15, 0.1), np.float32),
               c.fill(np.abs(c.X - (cx + i * 7 * s)) - 1.0 * s) * c.fill(c.sd_rrect(cx - 18 * s, cy + 28 * s, cx + 18 * s, cy + 38 * s, 2)))
    if glow_col is not None:
        eyes = np.maximum(c.circle(cx - 15 * s, cy + 1 * s, 4 * s), c.circle(cx + 15 * s, cy + 1 * s, 4 * s))
        glow(c, eyes, glow_col, 5, 2.0)
        c.add(np.array((1, 1, 1), np.float32), eyes * 0.8)
    return m


def puffs(c, blobs, col, seed=1, alpha=0.95, rim_col=None, radius=12):
    m = np.zeros((c.h, c.w), np.float32)
    for x, y, r in blobs:
        m = np.maximum(m, c.circle(x, y, r))
    n = fbm(c.h, c.w, 12 * c.k, 3, seed)
    m = smooth(0.35, 0.65, c.blur(m, 4) + 0.18 * n)
    h = c.blur(m, radius) * m * 18
    v, sp, (nx, ny, nz) = light(c, h, 10, 0.1, 0.15)
    col = np.array(col, np.float32)
    rgb = col[None, None] * (0.45 + 0.8 * v[..., None])
    if rim_col is not None:
        rr = np.clip(nx * 0.7 + ny * 0.6, 0, 1) ** 2
        rgb = rgb + np.array(rim_col, np.float32) * rr[..., None] * 0.6
    c.over(np.clip(rgb, 0, 1), m * alpha)
    return m


def sk_slash():
    c = Canvas(256, 256)
    icon_bg(c, (0.62, 0.2, 0.05), (0.07, 0.015, 0.01), 1, rays=7, ray_col=(1, 0.5, 0.15))
    slash_arc(c, 250, 250, 190, 190, 272, 22, (1.0, 0.45, 0.08))
    streaks = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(2)
    for _ in range(10):
        o = rng.uniform(-40, 40)
        streaks = np.maximum(streaks, stroke_mask(c, [(60 + o, 200 + o * 0.2), (200 + o * 0.3, 60 + o)], 0.3, 2.4) * rng.uniform(0.3, 0.8))
    c.add(np.array((1, 0.7, 0.3), np.float32), c.blur(streaks, 0.8) * 0.8)
    sword(c, (78, 178), (214, 42), 26, glow_col=(1, 0.6, 0.2), edge_glow=0.4)
    sparks(c, 26, 200, 60, 50, (1, 0.6, 0.2), 4, size=(1, 2.6), streak=4)
    return c


def sk_stab():
    c = Canvas(256, 256)
    icon_bg(c, (0.12, 0.34, 0.4), (0.02, 0.04, 0.06), 3, rays=9, ray_col=(0.5, 0.9, 1.0), center=(0.72, 0.28))
    sp = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(4)
    for i in range(9):
        o = rng.uniform(-36, 36)
        x0 = rng.uniform(10, 60)
        sp = np.maximum(sp, stroke_mask(c, [(x0 + o * 0.7, 246 - x0 + o * 0.7), (120 + o * 0.7, 136 + o * 0.7)], 0.3, 3) * rng.uniform(0.4, 0.9))
    c.add(np.array((0.6, 0.95, 1.0), np.float32), c.blur(sp, 1) * 0.8)
    dagger(c, (92, 164), (196, 60), 24, glow_col=(0.5, 0.9, 1.0), edge_glow=0.35)
    # glint star at the tip
    st = np.zeros((c.h, c.w), np.float32)
    for a, L in ((0, 44), (90, 44), (45, 20), (135, 20)):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        st = np.maximum(st, stroke_mask(c, [(200 - ca * L, 56 - sa * L), (200 + ca * L, 56 + sa * L)], 5, 5,
                                        prof=lambda t: math.sin(math.pi * t) ** 2))
    glow(c, st, (0.6, 0.95, 1.0), 6, 1.2)
    c.add(np.array((1, 1, 1), np.float32), st)
    return c


def crack_path(p0, p1, seed, jag=0.18):
    return bolt_path(p0, p1, seed, jag, 4)


def sk_shield_break():
    c = Canvas(256, 256)
    icon_bg(c, (0.5, 0.16, 0.05), (0.06, 0.02, 0.01), 5, rays=8, ray_col=(1, 0.6, 0.2))
    # impact flash behind
    fl = c.circle(128, 110, 30)
    glow(c, fl, (1, 0.6, 0.2), 30, 1.3)
    cx = 128
    pts = crack_path((cx + 6, 34), (cx - 4, 232), 7, 0.12)
    left_poly = [(0, 0)] + [(x, y) for x, y in pts] + [(0, 256)]
    lm = c.poly([(p[0], p[1]) for p in left_poly])
    # draw shield twice (two halves pushed apart & rotated)
    for side, dx, rot in ((0, -12, -8), (1, 12, 8)):
        sub = Canvas(256, 256)
        shield_icon(sub, 58, 38, 198, 226, field=hx("#7a1a14"), rim=STEEL)
        half = lm if side == 0 else 1 - lm
        sub.clip_to(half)
        im = sub.image().rotate(-rot, Image.BICUBIC, center=(128, 200)).transform(
            (256, 256), Image.AFFINE, (1, 0, -dx, 0, 1, 0), Image.BICUBIC)
        arr = np.asarray(im.resize((c.w, c.h), Image.LANCZOS), np.float32) / 255
        c.over(arr[..., :3], arr[..., 3])
    # glowing fissure
    crack = stroke_mask(c, pts, 6, 3)
    glow(c, crack, (1, 0.55, 0.15), 10, 1.4)
    c.add(np.array((1, 0.95, 0.7), np.float32), crack * 0.9)
    sparks(c, 18, 128, 120, 90, (1, 0.6, 0.2), 9, size=(1.2, 3.4), streak=3)
    rng = np.random.default_rng(12)
    shards = np.zeros((c.h, c.w), np.float32)
    for _ in range(6):
        x, y = rng.uniform(40, 216), rng.uniform(40, 200)
        a = rng.uniform(0, 360)
        shards = np.maximum(shards, c.poly(rot_pts([(x - 6, y - 3), (x + 7, y - 5), (x + 2, y + 6)], x, y, a)))
    paint(c, shards, hx("#b8c2cc"), 1.5, 2, spec=0.8, line=0.6, cast=0.4)
    return c


def sk_heavy_strike():
    c = Canvas(256, 256)
    icon_bg(c, (0.55, 0.32, 0.06), (0.07, 0.035, 0.01), 7, rays=10, ray_col=(1, 0.75, 0.3), center=(0.5, 0.78))
    # shockwave arcs + ground cracks
    for r, a in ((70, 1.0), (100, 0.6), (128, 0.35)):
        m = stroke_mask(c, arc_pts(128, 214, r, 190, 350, 80), 0.3, 0.3,
                        prof=lambda t: 7 * math.sin(math.pi * t) + 0.3, cap=False)
        m = m * np.clip(1 - np.abs(c.Y - 214) / 150, 0, 1)
        glow(c, m, (1, 0.7, 0.25), 6, 0.8 * a)
        c.add(np.array((1, 0.85, 0.5), np.float32), m * 0.6 * a)
    for i, ang in enumerate((200, 230, 270, 310, 340)):
        pts = crack_path((128, 214), (128 + math.cos(math.radians(ang + 180)) * 90,
                                      214 + abs(math.sin(math.radians(ang))) * 30), 20 + i, 0.15)
        cm = stroke_mask(c, pts, 4, 1)
        glow(c, cm, (1, 0.5, 0.1), 5, 1.0)
        c.add(np.array((1, 0.9, 0.6), np.float32), cm * 0.8)
    # hammer, swinging down (head low right, handle up left)
    ang = -38
    hx0, hy0 = 128, 150
    head = c.poly(rot_pts([(hx0 - 62, hy0 - 30), (hx0 + 62, hy0 - 30), (hx0 + 70, hy0 - 20), (hx0 + 70, hy0 + 20),
                           (hx0 + 62, hy0 + 30), (hx0 - 62, hy0 + 30), (hx0 - 70, hy0 + 20),
                           (hx0 - 70, hy0 - 20)], hx0, hy0, ang))
    handle = c.poly(rot_pts(seg_poly((hx0, hy0), (hx0, hy0 - 150), 16, 13), hx0, hy0, ang))
    paint(c, handle, hx("#6a4222"), 4, 5, spec=0.25, tex=0.25, tex_scale=2, cast=0.5)
    gold_shape(c, head, 6, 9, STEEL, shadow=0.6, sdx=3, sdy=4, ssig=4, power=24, spec=1.0, tex=0.06)
    bands = np.zeros((c.h, c.w), np.float32)
    for dx in (-44, 44):
        bands = np.maximum(bands, c.poly(rot_pts([(hx0 + dx - 6, hy0 - 31), (hx0 + dx + 6, hy0 - 31),
                                                   (hx0 + dx + 6, hy0 + 31), (hx0 + dx - 6, hy0 + 31)], hx0, hy0, ang)))
    gold_shape(c, bands * head, 2, 3, GOLD, shadow=0.3)
    motion = np.zeros((c.h, c.w), np.float32)
    for i in range(5):
        motion = np.maximum(motion, stroke_mask(c, arc_pts(40, 250, 150 + i * 14, 285, 330, 40), 0.3, 3.5) * (0.9 - i * 0.12))
    c.add(np.array((1, 0.9, 0.7), np.float32), c.blur(motion, 1) * 0.5)
    return c


def sk_battle_cry():
    c = Canvas(256, 256)
    icon_bg(c, (0.6, 0.08, 0.04), (0.07, 0.01, 0.01), 9, rays=12, ray_col=(1, 0.35, 0.1), center=(0.62, 0.4))
    pts = scroll_path(40, 222, -20, 172, 0, bend=-70)
    bx, by = pts[-1]
    # sound waves from the bell
    for i, r in enumerate((40, 68, 96, 124)):
        m = stroke_mask(c, arc_pts(bx, by, r, -90, 30, 60), 0.3, 0.3,
                        prof=lambda t: 7 * math.sin(math.pi * t) ** 0.8 + 0.3, cap=False)
        glow(c, m, (1, 0.5, 0.15), 6, 1.0 - i * 0.18)
        c.add(np.array((1, 0.85, 0.5), np.float32), m * (0.8 - i * 0.15))
    # war horn: curved tapering tube from mouthpiece (lower left) to bell (upper right)
    horn = stroke_mask(c, pts, 12, 62, cap=False)
    paint(c, horn, hx("#eadcb8"), 10, 12, spec=0.5, power=26, tex=0.12, tex_scale=3, cast=0.6, rim=0.35,
          rim_col=(1, 0.5, 0.2))
    ends = pts[-1]
    mouth = c.ellipse((ends[0] - 15, ends[1] - 31, ends[0] + 15, ends[1] + 31))
    mouth = np.asarray(Image.fromarray((mouth * 255).astype(np.uint8)).rotate(
        -math.degrees(math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0])) + 0,
        Image.BICUBIC, center=(ends[0] * c.k, ends[1] * c.k)), np.float32) / 255
    c.over(np.array((0.18, 0.08, 0.04), np.float32), mouth)
    glow(c, mouth, (1, 0.5, 0.15), 8, 0.9)
    bands = np.zeros((c.h, c.w), np.float32)
    for t in (0.18, 0.5, 0.82):
        i = int(t * (len(pts) - 1))
        a, b = pts[i - 1], pts[i + 1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        w = (12 + 50 * t) / 2 + 3
        p = pts[i]
        bands = np.maximum(bands, stroke_mask(c, [(p[0] + nx * w, p[1] + ny * w), (p[0] - nx * w, p[1] - ny * w)], 8, 8))
    gold_shape(c, bands, 2, 3, GOLD, shadow=0.4)
    return c


def sk_rending_cut():
    c = Canvas(256, 256)
    icon_bg(c, (0.45, 0.03, 0.05), (0.05, 0.0, 0.01), 11)
    for i in range(3):
        o = (i - 1) * 40
        pts = scroll_path(70 + o, 40 - o * 0.2, 62, 200, 0, bend=-25)
        m = stroke_mask(c, pts, 0.5, 0.5, prof=lambda t: 22 * math.sin(math.pi * t) ** 0.7 + 0.3, cap=False)
        glow(c, m, (1, 0.12, 0.1), 10, 1.1)
        c.over(np.array((0.75, 0.04, 0.05), np.float32), m)
        inner = stroke_mask(c, pts, 0.3, 0.3, prof=lambda t: 8 * math.sin(math.pi * t) ** 1.2, cap=False)
        c.add(np.array((1, 0.7, 0.6), np.float32), c.blur(inner, 1) * 1.1)
    rng = np.random.default_rng(3)
    drops = np.zeros((c.h, c.w), np.float32)
    for _ in range(14):
        x, y, r = rng.uniform(40, 220), rng.uniform(60, 230), rng.uniform(2.5, 6)
        drops = np.maximum(drops, np.maximum(c.circle(x, y, r), c.poly([(x - r * 0.9, y - r * 0.3), (x + r * 0.9, y - r * 0.3), (x - r * 0.8, y - r * 3)])))
    paint(c, drops, hx("#b01018"), 2, 3, spec=1.0, power=40, line=0.5, cast=0.4)
    return c


def sk_execute():
    c = Canvas(256, 256)
    icon_bg(c, (0.4, 0.02, 0.03), (0.03, 0.0, 0.0), 13, rays=6, ray_col=(1, 0.1, 0.1), center=(0.5, 0.35))
    skull(c, 128, 194, 0.8, col=hx("#b8a890"), glow_col=(1, 0.15, 0.1))
    # executioner's axe
    handle = c.poly(seg_poly((150, 20), (104, 236), 13, 15))
    paint(c, handle, hx("#4a2c18"), 4, 5, spec=0.25, tex=0.3, tex_scale=2, cast=0.6)
    blade = c.poly([(136, 44), (160, 36), (200, 28), (226, 60), (230, 112), (214, 150), (176, 130), (132, 112)])
    edge = np.maximum(stroke_mask(c, [(200, 28), (226, 60), (230, 112), (214, 150)], 12, 8) * blade, 0)
    c.shadow(blade, 3, 4, 4, 0.7)
    ol = np.clip(c.blur(blade, 1.0) * 2.6, 0, 1)
    c.over(np.array((0.04, 0.03, 0.03), np.float32), ol * (1 - blade))
    inner = c.poly([(136, 44), (160, 36), (192, 38), (204, 66), (206, 114), (196, 134), (176, 130), (132, 112)]) * blade
    bevel = blade * (1 - inner)
    tt = np.clip((c.Y - 30) / 120, 0, 1)
    c.over(ramp(STEEL, np.clip(0.34 + 0.12 * (1 - tt) + 0.06 * fbm(c.h, c.w, 8 * c.k, 3, 3), 0, 1)), inner)
    c.over(ramp(STEEL, np.clip(0.95 - 0.35 * tt, 0, 1)), bevel)
    c.over(np.array((1.0, 0.2, 0.12), np.float32), inner * smooth(60, 150, c.Y) * 0.25)
    glow(c, edge, (1, 0.1, 0.05), 8, 1.3)
    c.add(np.array((1, 0.4, 0.3), np.float32), edge * 0.8)
    rivets = np.maximum(c.circle(146, 64, 5), c.circle(140, 96, 5))
    gold_shape(c, rivets, 1.5, 2, GOLD, shadow=0.4)
    drips = np.zeros((c.h, c.w), np.float32)
    for x, L in ((214, 22), (200, 12)):
        drips = np.maximum(drips, stroke_mask(c, [(x, 144 - (x - 200)), (x - 2, 144 - (x - 200) + L)], 5, 3))
    paint(c, drips * (1 - blade), hx("#a00a10"), 2, 2, spec=0.9, line=0, cast=0)
    return c


def sk_iron_wall():
    c = Canvas(256, 256)
    icon_bg(c, (0.2, 0.34, 0.55), (0.02, 0.04, 0.08), 15, rays=14, ray_col=(0.6, 0.85, 1.0))
    aura = c.poly(heater_pts(34, 18, 222, 246))
    glow(c, aura, (0.4, 0.7, 1.0), 16, 1.0)
    sh = shield_icon(c, 50, 30, 206, 236, field=hx("#5c6874"), rim=GOLD)
    # rivet rows and a horizontal iron band
    band_m = c.fill(np.abs(c.Y - 118) - 9) * c.poly(heater_pts(62, 42, 194, 222))
    gold_shape(c, band_m, 2, 3, STEEL, shadow=0.4)
    rv = np.zeros((c.h, c.w), np.float32)
    for x in range(78, 190, 22):
        rv = np.maximum(rv, c.circle(x, 118, 3.2))
    gold_shape(c, rv, 1, 1.6, GOLD, shadow=0.3)
    sparks(c, 12, 128, 128, 120, (0.6, 0.85, 1.0), 16, size=(1, 2.5))
    return c


def sk_whirlwind():
    c = Canvas(256, 256)
    icon_bg(c, (0.14, 0.34, 0.38), (0.02, 0.05, 0.06), 17)
    swirl_arms(c, 128, 128, 116, 5, 1.1, 20, (0.55, 0.95, 1.0), seed=4, core=False, inner=0.25)
    sword(c, (86, 170), (212, 44), 22, glow_col=(0.6, 0.95, 1.0), edge_glow=0.3)
    sword(c, (170, 86), (44, 212), 22, glow_col=(0.6, 0.95, 1.0), edge_glow=0.3)
    swirl_arms(c, 128, 128, 116, 3, 1.1, 12, (0.7, 1.0, 1.0), seed=9, core=False, inner=0.45, amt=0.6)
    return c


def sk_arcane_bolt():
    c = Canvas(256, 256)
    icon_bg(c, (0.32, 0.08, 0.5), (0.03, 0.0, 0.06), 19, rays=8, ray_col=(0.8, 0.4, 1.0), center=(0.62, 0.38))
    # rune circle
    ring = c.fill(np.abs(np.hypot(c.X - 160, c.Y - 98) - 70) - 1.6)
    glyphs = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(5)
    for i in range(12):
        a = math.radians(i * 30)
        x, y = 160 + math.cos(a) * 82, 98 + math.sin(a) * 82
        glyphs = np.maximum(glyphs, stroke_mask(c, [(x - 4, y - 5), (x + rng.uniform(-4, 4), y), (x + 4, y + 5)], 1.8, 1.8))
    c.add(np.array((0.8, 0.5, 1.0), np.float32), (ring + glyphs) * 0.6)
    glow(c, ring, (0.7, 0.3, 1.0), 4, 0.6)
    # trail to lower left
    tr = stroke_mask(c, [(160, 98), (40, 218)], 58, 4, cap=False)
    tr = tr * (0.5 + 0.5 * aniso_noise(c, 50, 6, 135, 3))
    c.add(np.array((0.6, 0.2, 1.0), np.float32), c.blur(tr, 3) * 1.2)
    swirl_arms(c, 160, 98, 52, 4, 1.4, 12, (0.85, 0.45, 1.0), seed=3)
    orb = c.circle(160, 98, 26)
    glow(c, orb, (0.8, 0.4, 1.0), 16, 1.2)
    c.add(np.array((1, 0.9, 1.0), np.float32), c.blur(orb, 6) * 1.2)
    sparks(c, 20, 100, 160, 70, (0.8, 0.5, 1.0), 6, size=(1, 2.6))
    return c


def sk_fireball():
    c = Canvas(256, 256)
    icon_bg(c, (0.5, 0.08, 0.02), (0.05, 0.01, 0.0), 21)
    hxp, hyp = 166, 92
    d = np.hypot(c.X - hxp, c.Y - hyp)
    # comet envelope: head + trail toward lower-left
    ux, uy = -1 / math.sqrt(2), 1 / math.sqrt(2)
    along = (c.X - hxp) * ux + (c.Y - hyp) * uy
    across = np.abs(-(c.X - hxp) * uy + (c.Y - hyp) * ux)
    trail = np.clip(1 - along / 190, 0, 1) * (along > 0) * np.clip(1 - across / (46 * np.clip(1 - along / 210, 0.05, 1)), 0, 1)
    head = np.clip(1 - d / 50, 0, 1) ** 0.7
    env = np.clip(np.maximum(head * 1.2, trail ** 0.8 * 0.95), 0, 1.2)
    fire(c, env, angle=135, seed=4, streak=(46, 8))
    core = np.clip(1 - d / 28, 0, 1)
    c.add(np.array((1, 0.95, 0.7), np.float32), core ** 0.8 * 1.3)
    glow(c, c.circle(hxp, hyp, 30), (1, 0.5, 0.1), 26, 0.8)
    sparks(c, 28, 110, 150, 90, (1, 0.6, 0.15), 8, size=(1, 2.8), angle=135, streak=3)
    return c


def sk_flame_burst():
    c = Canvas(256, 256)
    icon_bg(c, (0.6, 0.2, 0.02), (0.06, 0.01, 0.0), 23, rays=16, ray_col=(1, 0.6, 0.2))
    cx, cy = 128, 136
    d = np.hypot(c.X - cx, c.Y - cy)
    ang = np.arctan2(c.Y - cy, c.X - cx)
    spikes = 0.62 + 0.38 * np.abs(np.sin(ang * 5 + 0.4)) ** 3 + 0.15 * np.sin(ang * 13)
    env = np.clip(1 - d / (110 * spikes), 0, 1) ** 0.7
    n = fbm(c.h, c.w, 16 * c.k, 4, 5)
    f = np.clip(env * (0.8 + 0.5 * n) * 1.2, 0, 1)
    col = fire_ramp(f)
    c.over(col, smooth(0.1, 0.4, f))
    c.add(np.array((1, 0.45, 0.1), np.float32), c.blur(f, 12) * 0.6)
    c.add(np.array((1, 0.95, 0.75), np.float32), np.clip(1 - d / 40, 0, 1) ** 1.2 * 1.3)
    # flame tongues radiating
    tong = np.zeros((c.h, c.w), np.float32)
    rng = np.random.default_rng(7)
    for i in range(10):
        a = i * 36 + rng.uniform(-10, 10)
        tong = np.maximum(tong, stroke_mask(c, scroll_path(cx, cy, a, 118, rng.uniform(-40, 40)), 16, 0.5) * rng.uniform(0.5, 0.9))
    fire(c, c.blur(tong, 3) * 0.9, angle=0, seed=8, streak=(14, 14), amt=0.8)
    sparks(c, 30, cx, cy, 120, (1, 0.7, 0.2), 9, size=(1, 2.8), streak=3)
    return c


def sk_ice_lance():
    c = Canvas(256, 256)
    icon_bg(c, (0.1, 0.3, 0.55), (0.01, 0.03, 0.07), 25, rays=10, ray_col=(0.6, 0.9, 1.0), center=(0.75, 0.25))
    # frost trail
    tr = stroke_mask(c, [(210, 46), (30, 226)], 40, 4, cap=False) * (0.5 + 0.5 * aniso_noise(c, 40, 5, 135, 2))
    c.add(np.array((0.4, 0.75, 1.0), np.float32), c.blur(tr, 3) * 0.7)
    # lance: long hexagonal crystal
    p0, p1 = (44, 212), (216, 40)
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    nx, ny = -uy, ux

    def P(t, o):
        return (p0[0] + ux * t + nx * o, p0[1] + uy * t + ny * o)
    outline = [P(0, 0), P(18, 13), P(L - 60, 16), P(L, 0), P(L - 60, -16), P(18, -13)]
    facet_poly(c, outline, P(L * 0.55, 3), np.array(hx("#8fd8ff")), light_bias=0.05, edge=0.8, gl=(0.4, 0.8, 1.0))
    ridge = stroke_mask(c, [P(4, 0), P(L - 4, 0)], 2.4, 1)
    c.add(np.array((1, 1, 1), np.float32), ridge * 0.7)
    # small side shards near the base
    for o, t, a in ((22, 40, 40), (-22, 60, -35), (18, 90, 50)):
        b = P(t, o * 0.6)
        tip = (b[0] + math.cos(math.atan2(uy, ux) + math.radians(a)) * 30, b[1] + math.sin(math.atan2(uy, ux) + math.radians(a)) * 30)
        sm = c.poly(seg_poly(b, tip, 10, 0.5))
        paint(c, sm, hx("#9edcff"), 2, 3, spec=0.9, power=30, line=0.6, cast=0.3, rim=0.5, rim_col=(0.8, 0.95, 1.0))
    tipg = c.circle(*P(L - 6, 0), 6)
    glow(c, tipg, (0.7, 0.95, 1.0), 10, 1.4)
    c.add(np.array((1, 1, 1), np.float32), c.blur(tipg, 2) * 1.2)
    sparks(c, 26, 128, 128, 120, (0.7, 0.95, 1.0), 12, size=(1, 2.4))
    return c


def sk_mana_shield():
    c = Canvas(256, 256)
    icon_bg(c, (0.05, 0.16, 0.45), (0.01, 0.02, 0.07), 27)
    cx, cy, R = 128, 130, 96
    d = np.hypot(c.X - cx, c.Y - cy)
    bub = c.fill(d - R)
    # fresnel bubble
    fres = np.clip(d / R, 0, 1) ** 4 * bub
    c.add(np.array((0.3, 0.6, 1.0), np.float32), fres * 1.1 + bub * 0.12)
    # hex lattice on the bubble
    s = 22.0
    X, Y = (c.X - cx) / s, (c.Y - cy) / s
    q = X * 2 / 3
    r = (-X / 3 + Y / math.sqrt(3))

    def hexdist(q, r):
        x, z = q, r
        y = -x - z
        rx, ry, rz = np.round(x), np.round(y), np.round(z)
        dx, dy, dz = np.abs(rx - x), np.abs(ry - y), np.abs(rz - z)
        return np.maximum(np.maximum(dx, dy), dz)
    hd = hexdist(q, r)
    lat = smooth(0.40, 0.5, hd) * bub * (0.3 + 0.7 * np.clip(d / R, 0, 1) ** 2)
    c.add(np.array((0.5, 0.8, 1.0), np.float32), lat * 0.8)
    rim_m = c.fill(np.abs(d - R) - 2.5)
    glow(c, rim_m, (0.3, 0.65, 1.0), 8, 1.3)
    c.add(np.array((0.8, 0.95, 1.0), np.float32), rim_m)
    # rune ring inside + core
    ring = c.fill(np.abs(d - 48) - 1.8)
    tick = ring * 0
    for i in range(16):
        a = math.radians(i * 22.5)
        tick = np.maximum(tick, stroke_mask(c, [(cx + math.cos(a) * 42, cy + math.sin(a) * 42), (cx + math.cos(a) * 54, cy + math.sin(a) * 54)], 2, 2))
    c.add(np.array((0.6, 0.85, 1.0), np.float32), (ring + tick * 0.8))
    glow(c, ring, (0.3, 0.6, 1.0), 5, 0.6)
    compass_star(c, cx, cy, 36, 20, 8, 5, stops=[(0, hx("#08204a")), (0.5, hx("#3a8ae0")), (0.8, hx("#a8dcff")), (1, (1, 1, 1))], red=False)
    glow(c, c.circle(cx, cy, 10), (0.5, 0.8, 1.0), 10, 1.0)
    # specular highlight on the bubble
    hl = stroke_mask(c, arc_pts(cx, cy, R - 14, 200, 250, 30), 3, 3, prof=lambda t: math.sin(math.pi * t) * 3)
    c.add(np.array((1, 1, 1), np.float32), c.blur(hl, 1.5) * 0.8)
    return c


def sk_shatter():
    c = Canvas(256, 256)
    icon_bg(c, (0.2, 0.45, 0.65), (0.01, 0.04, 0.08), 29, rays=12, ray_col=(0.7, 0.95, 1.0))
    cx, cy = 128, 132
    glow(c, c.circle(cx, cy, 40), (0.6, 0.9, 1.0), 30, 1.1)
    rng = np.random.default_rng(9)
    # shards flying out
    for i in range(11):
        a = math.radians(i * 32.7 + rng.uniform(-8, 8))
        d = rng.uniform(62, 104)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        L = rng.uniform(16, 28)
        pts = rot_pts([(x - L, y), (x - L * 0.2, y - L * 0.35), (x + L * 0.8, y), (x - L * 0.1, y + L * 0.3)], x, y,
                      math.degrees(a))
        facet_poly(c, pts, (x, y), np.array(hx("#a8e4ff")), edge=0.6)
        tr = stroke_mask(c, [(cx + math.cos(a) * (d - 34), cy + math.sin(a) * (d - 34)), (x, y)], 0.5, 5)
        c.add(np.array((0.6, 0.9, 1.0), np.float32), c.blur(tr, 1.5) * 0.6)
    # central crystal cluster
    core = [(cx, cy - 58), (cx + 30, cy - 18), (cx + 26, cy + 34), (cx, cy + 56), (cx - 28, cy + 30),
            (cx - 32, cy - 20)]
    facet_poly(c, core, (cx - 4, cy - 6), np.array(hx("#bdeeff")), light_bias=0.05, edge=0.9, gl=(0.5, 0.85, 1.0))
    cr = np.zeros((c.h, c.w), np.float32)
    for i, ang in enumerate((20, 110, 200, 290)):
        cr = np.maximum(cr, stroke_mask(c, crack_path((cx - 2, cy - 4), (cx + math.cos(math.radians(ang)) * 44, cy + math.sin(math.radians(ang)) * 50), 40 + i, 0.2), 2.4, 0.8))
    c.over(np.array((0.1, 0.3, 0.5), np.float32), cr * c.poly(core) * 0.7)
    c.add(np.array((1, 1, 1), np.float32), c.shift(cr, 0.8, 0.8) * c.poly(core) * 0.6)
    sparks(c, 26, cx, cy, 120, (0.7, 0.95, 1.0), 10, size=(1, 2.4))
    return c


def sk_chain_lightning():
    c = Canvas(256, 256)
    icon_bg(c, (0.16, 0.14, 0.45), (0.01, 0.01, 0.06), 31, rays=10, ray_col=(0.6, 0.7, 1.0), center=(0.5, 0.2))
    nodes = [(128, 30), (70, 124), (196, 150), (104, 228)]
    col = (0.55, 0.7, 1.0)
    for i, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
        lightning(c, a, b, 50 + i * 3, 8.5 - i * 1.2, col, branches=2, jag=0.18)
    for (x, y) in nodes[1:]:
        o = c.circle(x, y, 9)
        glow(c, o, (0.6, 0.8, 1.0), 12, 1.6)
        c.add(np.array((1, 1, 1), np.float32), c.blur(o, 2))
    top = c.circle(128, 30, 12)
    glow(c, top, (1, 0.95, 0.6), 16, 1.5)
    sparks(c, 24, 128, 128, 120, (0.7, 0.8, 1.0), 13, size=(1, 2.2))
    return c


def sk_meteor():
    c = Canvas(256, 256)
    icon_bg(c, (0.35, 0.08, 0.2), (0.03, 0.01, 0.04), 33)
    stars = sparks(c, 30, 128, 128, 180, (0.9, 0.8, 1.0), 5, size=(0.6, 1.4))
    rx, ry = 146, 146
    ux, uy = -1 / math.sqrt(2), -1 / math.sqrt(2)
    along = (c.X - rx) * ux + (c.Y - ry) * uy
    across = np.abs(-(c.X - rx) * uy + (c.Y - ry) * ux)
    trail = np.clip(1 - along / 200, 0, 1) * (along > -10) * np.clip(1 - across / (70 * np.clip(1 - along / 230, 0.05, 1)), 0, 1)
    fire(c, trail ** 0.8 * 1.2, angle=-135, seed=6, streak=(50, 9))
    glow(c, c.circle(rx, ry, 56), (1, 0.4, 0.1), 30, 0.9)
    # rock with lava cracks
    ang = np.arctan2(c.Y - ry, c.X - rx)
    rr = np.hypot(c.X - rx, c.Y - ry)
    rock = c.fill(rr - (54 + 6 * np.sin(ang * 5 + 1) + 3 * np.sin(ang * 11)))
    paint(c, rock, hx("#5a4038"), 12, 14, spec=0.3, tex=0.35, tex_scale=3, seed=4, rim=0.9, rim_col=(1.0, 0.5, 0.1))
    lava = np.zeros((c.h, c.w), np.float32)
    for i, a in enumerate((30, 150, 250, 330)):
        lava = np.maximum(lava, stroke_mask(c, crack_path((rx - 4, ry - 2), (rx + math.cos(math.radians(a)) * 50, ry + math.sin(math.radians(a)) * 50), 70 + i, 0.2), 3.6, 1.2))
    lava *= rock
    glow(c, lava, (1, 0.45, 0.05), 4, 1.2)
    c.add(np.array((1, 0.85, 0.4), np.float32), lava)
    # hot leading edge (lower right)
    lead = rock * np.clip(((c.X - rx) + (c.Y - ry)) / 60, 0, 1)
    c.add(np.array((1, 0.55, 0.15), np.float32), lead * 0.6)
    sparks(c, 24, 110, 110, 90, (1, 0.6, 0.2), 7, size=(1, 2.6), angle=-135, streak=3)
    return c


def sk_poison_blade():
    c = Canvas(256, 256)
    icon_bg(c, (0.12, 0.38, 0.08), (0.01, 0.04, 0.01), 35, rays=8, ray_col=(0.5, 1.0, 0.3))
    gsteel = [(0.0, hx("#0a1a08")), (0.25, hx("#244a1c")), (0.45, hx("#4f8a3a")), (0.62, hx("#8fd46a")),
              (0.8, hx("#c8f5a8")), (1.0, (1, 1, 1))]
    bl = dagger(c, (170, 70), (60, 214), 30, glow_col=(0.4, 1.0, 0.2), edge_glow=0.8, steel=gsteel)
    # drips from the blade
    drips = np.zeros((c.h, c.w), np.float32)
    for x, y, L in ((104, 150, 38), (86, 176, 30), (126, 124, 26)):
        drips = np.maximum(drips, stroke_mask(c, [(x, y), (x + 1, y + L)], 5, 3))
        drips = np.maximum(drips, c.circle(x + 1, y + L + 6, 5.5))
    paint(c, drips, hx("#5ce02a"), 2.5, 3, spec=1.0, power=40, line=0.6, cast=0, rim=0.4, rim_col=(0.8, 1, 0.5))
    glow(c, drips, (0.4, 1.0, 0.2), 6, 0.7)
    rng = np.random.default_rng(3)
    bub = np.zeros((c.h, c.w), np.float32)
    for _ in range(10):
        x, y, r = rng.uniform(40, 220), rng.uniform(40, 220), rng.uniform(3, 7)
        bub = np.maximum(bub, c.fill(np.abs(np.hypot(c.X - x, c.Y - y) - r) - 1))
    c.add(np.array((0.5, 1.0, 0.4), np.float32), bub * 0.6)
    return c


def sk_backstab():
    c = Canvas(256, 256)
    icon_bg(c, (0.3, 0.1, 0.5), (0.03, 0.01, 0.06), 37, rays=14, ray_col=(0.7, 0.5, 1.0), center=(0.5, 0.42))
    f = figure(c, 116, 44, 1.25, lean=0, arm=0)
    glow(c, f, (0.6, 0.4, 1.0), 10, 1.0)
    h = emboss(c, f, 8, 6)
    v, sp, (nx, ny, nz) = light(c, h, 12, 0.1, 0.2)
    base = np.array(hx("#1a1030"), np.float32)
    rim = np.clip(nx * 0.5 - ny * 0.6, 0, 1) ** 2
    c.over(np.clip(base[None, None] * (0.6 + 0.8 * v[..., None]) + np.array((0.6, 0.4, 1.0)) * rim[..., None] * 0.7, 0, 1), f)
    eyes = np.maximum(c.circle(109, 72, 2.6), c.circle(123, 72, 2.6))
    glow(c, eyes, (1, 0.3, 0.3), 4, 2.0)
    c.add(np.array((1, 0.8, 0.8), np.float32), eyes)
    # raised dagger in the near hand, pointing down
    dagger(c, (196, 138), (220, 40), 22, glow_col=(1, 0.3, 0.4), edge_glow=0.7)
    return c


def sk_smoke_bomb():
    c = Canvas(256, 256)
    icon_bg(c, (0.25, 0.22, 0.35), (0.03, 0.03, 0.05), 39)
    puffs(c, [(60, 190, 40), (110, 210, 44), (170, 204, 42), (206, 170, 34), (40, 140, 30), (80, 110, 26),
              (200, 110, 26)], (0.36, 0.33, 0.44), 4, 0.88, rim_col=(0.75, 0.6, 1.0))
    bomb = c.circle(120, 134, 50)
    paint(c, bomb, hx("#2a2a34"), 16, 18, spec=0.9, power=30, tex=0.1, rim=0.5, rim_col=(0.7, 0.6, 1.0), cast=0.6)
    cap = c.fill(c.sd_rrect(136, 76, 164, 96, 4))
    cap = np.asarray(Image.fromarray((cap * 255).astype(np.uint8)).rotate(-40, Image.BICUBIC, center=(150 * c.k, 86 * c.k)), np.float32) / 255
    gold_shape(c, cap, 2, 3, BRONZE, shadow=0.4)
    fuse = stroke_mask(c, scroll_path(158, 78, -60, 40, -50), 4, 3)
    paint(c, fuse, hx("#c8a060"), 2, 2, spec=0.2, line=0.5, cast=0.3)
    sp = c.circle(186, 44, 7)
    glow(c, sp, (1, 0.7, 0.2), 12, 2.0)
    c.add(np.array((1, 1, 0.8), np.float32), c.blur(sp, 1.5) * 1.3)
    sparks(c, 16, 186, 44, 26, (1, 0.7, 0.2), 3, size=(1, 2), streak=3)
    puffs(c, [(40, 232, 30), (216, 232, 30), (128, 244, 30)], (0.4, 0.37, 0.48), 6, 0.85, rim_col=(0.75, 0.6, 1.0))
    return c


def sk_blind():
    c = Canvas(256, 256)
    icon_bg(c, (0.5, 0.42, 0.15), (0.05, 0.04, 0.02), 41, rays=16, ray_col=(1, 0.95, 0.6))
    cx, cy = 128, 132
    eye = c.poly([(cx - 96 + 0 * i, cy) for i in range(1)] + arc_pts(cx, cy + 70, 110, 230, 310, 30) +
                 arc_pts(cx, cy - 70, 110, 50, 130, 30))
    c.shadow(eye, 2, 4, 4, 0.6)
    c.over(np.array(hx("#f2ece0"), np.float32) * (1 - 0.35 * np.clip(np.hypot(c.X - cx, c.Y - cy) / 90, 0, 1))[..., None], eye)
    iris = c.circle(cx, cy, 30) * eye
    ir = np.hypot(c.X - cx, c.Y - cy) / 30
    icol = ramp([(0, hx("#101010")), (0.35, hx("#101010")), (0.4, hx("#3a6a9a")), (0.8, hx("#8ac0e8")), (1, hx("#1a2a40"))], np.clip(ir, 0, 1))
    c.over(icol, iris)
    inner_shadow(c, eye, 6, 0.6, 0, 6)
    lid = stroke_mask(c, arc_pts(cx, cy + 70, 110, 232, 308, 30), 5, 5)
    c.over(np.array((0.15, 0.08, 0.04), np.float32), lid)
    # blinding flash
    fl = np.zeros((c.h, c.w), np.float32)
    for a, L in ((0, 120), (90, 110), (45, 60), (135, 60), (22, 40), (68, 40), (112, 40), (158, 40)):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        fl = np.maximum(fl, stroke_mask(c, [(cx + 26 - ca * L, cy - 20 - sa * L), (cx + 26 + ca * L, cy - 20 + sa * L)], 8, 8,
                                        prof=lambda t: math.sin(math.pi * t) ** 2))
    glow(c, fl, (1, 0.9, 0.5), 10, 1.2)
    c.add(np.array((1, 1, 0.95), np.float32), fl * 1.2)
    glow(c, c.circle(cx + 26, cy - 20, 10), (1, 1, 0.8), 18, 2.0)
    return c


def sk_poison_burst():
    c = Canvas(256, 256)
    icon_bg(c, (0.16, 0.42, 0.06), (0.01, 0.04, 0.0), 43, rays=14, ray_col=(0.6, 1.0, 0.3))
    cx, cy = 128, 134
    rng = np.random.default_rng(5)
    blobs = [(cx, cy, 52)] + [(cx + math.cos(a) * 48, cy + math.sin(a) * 48, rng.uniform(22, 30)) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
    splash = np.zeros((c.h, c.w), np.float32)
    for x, y, r in blobs:
        splash = np.maximum(splash, c.circle(x, y, r))
    for i in range(12):
        a = math.radians(i * 30 + rng.uniform(-10, 10))
        L = rng.uniform(90, 118)
        splash = np.maximum(splash, stroke_mask(c, [(cx, cy), (cx + math.cos(a) * L, cy + math.sin(a) * L)], 22, 3))
        splash = np.maximum(splash, c.circle(cx + math.cos(a) * (L + 10), cy + math.sin(a) * (L + 10), rng.uniform(4, 8)))
    splash = smooth(0.4, 0.6, c.blur(splash, 2))
    glow(c, splash, (0.4, 1.0, 0.15), 12, 0.8)
    paint(c, splash, hx("#58d020"), 10, 12, spec=0.9, power=30, tex=0.1, rim=0.5, rim_col=(0.8, 1, 0.4), line=0.7)
    core = np.clip(1 - np.hypot(c.X - cx, c.Y - cy) / 50, 0, 1)
    c.add(np.array((0.8, 1.0, 0.5), np.float32), core ** 1.2 * 0.8)
    skull(c, cx, cy - 4, 0.62, col=hx("#1e3a10"), glow_col=(0.7, 1.0, 0.3))
    bub = np.zeros((c.h, c.w), np.float32)
    for _ in range(12):
        x, y, r = rng.uniform(30, 226), rng.uniform(30, 226), rng.uniform(3, 8)
        bub = np.maximum(bub, c.fill(np.abs(np.hypot(c.X - x, c.Y - y) - r) - 1.1))
    c.add(np.array((0.7, 1.0, 0.5), np.float32), bub * 0.7)
    return c


def sk_blade_rain():
    c = Canvas(256, 256)
    icon_bg(c, (0.2, 0.2, 0.45), (0.02, 0.02, 0.06), 45, rays=10, ray_col=(0.6, 0.7, 1.0), center=(0.5, 0.0))
    rng = np.random.default_rng(8)
    pos = [(70, 70, 0.7), (190, 64, 0.72), (130, 108, 0.95), (60, 170, 0.85), (200, 170, 0.8), (135, 205, 1.0)]
    for x, y, s in pos:
        ang = math.radians(100)
        L = 110 * s
        tip = (x + math.cos(ang) * L * 0.5, y + math.sin(ang) * L * 0.5)
        hilt = (x - math.cos(ang) * L * 0.5, y - math.sin(ang) * L * 0.5)
        tr = stroke_mask(c, [(hilt[0] - math.cos(ang) * 60, hilt[1] - math.sin(ang) * 60), hilt], 0.5, 14 * s)
        c.add(np.array((0.5, 0.65, 1.0), np.float32), c.blur(tr, 3) * 0.6)
        sword(c, hilt, tip, 16 * s, glow_col=(0.6, 0.75, 1.0), edge_glow=0.5, grip_len=0.22, guard_w=2.4)
    sparks(c, 20, 128, 128, 120, (0.7, 0.8, 1.0), 12, size=(1, 2.2))
    return c


def sk_shadow_step():
    c = Canvas(256, 256)
    icon_bg(c, (0.26, 0.06, 0.42), (0.02, 0.0, 0.05), 47)
    swirl_arms(c, 88, 150, 80, 4, 1.2, 14, (0.6, 0.25, 1.0), seed=6, amt=0.8)
    for i, (x, a) in enumerate(((50, 0.25), (86, 0.45), (122, 0.7))):
        f = figure(c, x, 50, 1.2, lean=-26, arm=20)
        glow(c, f, (0.6, 0.3, 1.0), 8, 0.4 * a)
        c.over(np.array((0.3, 0.12, 0.55), np.float32), f * a * 0.6)
    f = figure(c, 162, 48, 1.22, lean=-30, arm=24)
    glow(c, f, (0.7, 0.4, 1.0), 10, 1.0)
    h = emboss(c, f, 8, 6)
    v, sp, (nx, ny, nz) = light(c, h, 12, 0.1, 0.2)
    rim = np.clip(nx * 0.8 + ny * 0.2, 0, 1) ** 2
    c.over(np.clip(np.array(hx("#160c26"))[None, None] * (0.6 + 0.8 * v[..., None]) + np.array((0.7, 0.45, 1.0)) * rim[..., None] * 0.8, 0, 1), f)
    eyes = np.maximum(c.circle(158, 76, 2.4), c.circle(170, 76, 2.4))
    glow(c, eyes, (0.8, 0.5, 1.0), 4, 2.0)
    c.add(np.array((1, 0.9, 1.0), np.float32), eyes)
    sparks(c, 24, 100, 140, 110, (0.7, 0.4, 1.0), 14, size=(1, 2.4), angle=180, streak=4)
    return c


SKILLS = {
    "arcane_bolt": sk_arcane_bolt, "backstab": sk_backstab, "battle_cry": sk_battle_cry, "blade_rain": sk_blade_rain,
    "blind": sk_blind, "chain_lightning": sk_chain_lightning, "execute": sk_execute, "fireball": sk_fireball,
    "flame_burst": sk_flame_burst, "heavy_strike": sk_heavy_strike, "ice_lance": sk_ice_lance,
    "iron_wall": sk_iron_wall, "mana_shield": sk_mana_shield, "meteor": sk_meteor, "poison_blade": sk_poison_blade,
    "poison_burst": sk_poison_burst, "rending_cut": sk_rending_cut, "shadow_step": sk_shadow_step,
    "shatter": sk_shatter, "shield_break": sk_shield_break, "slash": sk_slash, "smoke_bomb": sk_smoke_bomb,
    "stab": sk_stab, "whirlwind": sk_whirlwind,
}


def finish_icon(c):
    """Clamp and give the square a very subtle inner edge darkening so it seats in the slot."""
    edge = np.minimum(np.minimum(c.X, c.W - c.X), np.minimum(c.Y, c.H - c.Y))
    c.mul(0.75 + 0.25 * smooth(0, 14, edge))
    img = c.image()
    return img.convert("RGB").convert("RGBA")


# ----------------------------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------------------------

BAR_COLORS = {
    "bar_fill_hp.png": ((0.86, 0.14, 0.11), (1.0, 0.75, 0.6)),
    "bar_fill_mana.png": ((0.13, 0.48, 0.95), (0.7, 0.95, 1.0)),
    "bar_fill_rage.png": ((0.95, 0.36, 0.07), (1.0, 0.85, 0.5)),
    "bar_fill_energy.png": ((0.97, 0.78, 0.14), (1.0, 1.0, 0.75)),
    "bar_fill_enemy.png": ((0.56, 0.04, 0.06), (1.0, 0.45, 0.35)),
    "bar_fill_xp.png": ((0.93, 0.66, 0.18), (1.0, 0.95, 0.7)),
}


def kit_jobs():
    jobs = {
        "hud_bar.png": make_hud_bar,
        "panel.png": lambda: make_panel(False),
        "panel_parchment.png": lambda: make_panel(True),
        "nameplate.png": make_nameplate,
        "portrait_frame.png": lambda: make_portrait_frame(320),
        "portrait_frame_small.png": lambda: make_portrait_frame(200),
        "level_badge.png": make_level_badge,
        "bar_frame.png": make_bar_frame,
        "bar_back.png": lambda: make_bar_fill((0, 0, 0), back=True),
        "skill_slot.png": lambda: make_skill_slot("normal"),
        "skill_slot_active.png": lambda: make_skill_slot("active"),
        "skill_slot_disabled.png": lambda: make_skill_slot("disabled"),
        "slot_number.png": make_slot_number,
        "ribbon_button.png": lambda: make_ribbon("normal"),
        "ribbon_button_pressed.png": lambda: make_ribbon("pressed"),
        "ribbon_button_disabled.png": lambda: make_ribbon("disabled"),
        "button.png": lambda: make_button("normal"),
        "button_pressed.png": lambda: make_button("pressed"),
        "button_disabled.png": lambda: make_button("disabled"),
        "button_gold.png": lambda: make_button("normal", True),
        "button_gold_pressed.png": lambda: make_button("pressed", True),
        "round_button.png": lambda: make_round_button("normal"),
        "round_button_pressed.png": lambda: make_round_button("pressed"),
        "close.png": lambda: make_close("normal"),
        "close_pressed.png": lambda: make_close("pressed"),
        "divider.png": make_divider,
        "tab.png": lambda: make_tab(False),
        "tab_active.png": lambda: make_tab(True),
        "turn_badge.png": make_turn_badge,
    }
    for i, (name, (col, gl)) in enumerate(BAR_COLORS.items()):
        jobs[name] = (lambda col=col, gl=gl, i=i: make_bar_fill(col, gl, seed=10 + i))
    jobs.update(MENU_ICONS)
    return jobs


def build_kit():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in kit_jobs().items():
        img = fn()
        img.save(os.path.join(OUT, name), optimize=True)
        print("  %-28s %4d x %-4d" % (name, img.size[0], img.size[1]))


def build_skills():
    os.makedirs(SKILL_OUT, exist_ok=True)
    for sid, fn in SKILLS.items():
        img = finish_icon(fn())
        img.save(os.path.join(SKILL_OUT, sid + ".png"), optimize=True)
        print("  %-20s %d x %d" % (sid + ".png", img.size[0], img.size[1]))


# ----------------------------------------------------------------------------------------------
# contact sheet with a battle HUD mock-up
# ----------------------------------------------------------------------------------------------

def _load(name):
    return Image.open(os.path.join(OUT, name)).convert("RGBA")


def nine(img, w, h, margins):
    """Godot-style 9-slice stretch (for the mock-up)."""
    l, t, r, b = margins
    W, H = img.size
    w, h = max(w, l + r), max(h, t + b)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xs = [(0, l, 0, l), (l, W - r, l, w - r), (W - r, W, w - r, w)]
    ys = [(0, t, 0, t), (t, H - b, t, h - b), (H - b, H, h - b, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            piece = img.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS)
            out.alpha_composite(piece, (dx0, dy0))
    return out


def _font(size, weight=b"Bold"):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def _text(img, xy, s, size, fill=(245, 232, 200), anchor="mm", weight=b"Bold", stroke=2):
    d = ImageDraw.Draw(img)
    d.text(xy, s, font=_font(size, weight), fill=fill, anchor=anchor, stroke_width=stroke,
           stroke_fill=(20, 12, 6))


def _fake_portrait(size, kind="hero"):
    """Simple painted placeholder portrait disc for the mock-up only."""
    c = Canvas(size, size, 1)
    cx = cy = size / 2
    if kind == "hero":
        icon_bg(c, (0.35, 0.42, 0.55), (0.08, 0.1, 0.16), 3)
        body = c.ellipse((cx - size * 0.42, cy + size * 0.12, cx + size * 0.42, cy + size * 0.9))
        paint(c, body, hx("#2a3a70"), 8, 8, spec=0.3, line=0)
        head = c.ellipse((cx - size * 0.18, cy - size * 0.28, cx + size * 0.18, cy + size * 0.16))
        paint(c, head, hx("#e8c0a0"), 8, 8, spec=0.2, line=0)
        hair = c.ellipse((cx - size * 0.22, cy - size * 0.36, cx + size * 0.2, cy - size * 0.04))
        paint(c, hair * (c.Y < cy - size * 0.1), hx("#6a4020"), 6, 6, spec=0.3, line=0)
    else:
        icon_bg(c, (0.6, 0.2, 0.04), (0.1, 0.02, 0.0), 5)
        rock = c.ellipse((cx - size * 0.36, cy - size * 0.3, cx + size * 0.36, cy + size * 0.44))
        paint(c, rock, hx("#4a3a34"), 10, 10, spec=0.2, tex=0.4, rim=0.8, rim_col=(1, 0.4, 0.1), line=0)
        eye = c.circle(cx + size * 0.05, cy - size * 0.02, size * 0.05)
        glow(c, eye, (1, 0.6, 0.1), 6, 2)
    return c.image()


def _circle_mask(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse((img.size[0] / 2 - r, img.size[1] / 2 - r, img.size[0] / 2 + r, img.size[1] / 2 + r),
                              fill=255)
    out = img.copy()
    out.putalpha(m)
    return out


def _bar(scene, x, y, w, h, fill, frac, label):
    back = nine(_load("bar_back.png"), w - 8, h - 8, MARGINS["bar_back.png"])
    scene.alpha_composite(back, (x + 4, y + 4))
    fw = int((w - 8) * frac)
    if fw > 0:
        f = nine(_load(fill), w - 8, h - 8, MARGINS[fill]).crop((0, 0, fw, h - 8))
        scene.alpha_composite(f, (x + 4, y + 4))
    fr = nine(_load("bar_frame.png"), w, h, MARGINS["bar_frame.png"])
    scene.alpha_composite(fr, (x, y))
    if label:
        _text(scene, (x + w / 2, y + h / 2), label, int(h * 0.55), stroke=2)


def mock_hud():
    """1280 x 720 battle screen mock-up built from the kit pieces at design scale (x0.5 of 2x art)."""
    S = 2  # draw the mock-up at 2x (2560 x 1440) then downscale to 1280 x 720
    W, H = 1280 * S, 720 * S
    scene = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    bg = None
    for cand in ("v2/frozen_pass.jpg", "v2/rotten_cellar.jpg", "burnt_keep.png", "frozen_pass.png"):
        pth = os.path.join(ROOT, "assets", "backgrounds", cand)
        if os.path.isfile(pth):
            bg = pth
            break
    if bg:
        im = Image.open(bg).convert("RGBA")
        sc = max(W / im.size[0], H / im.size[1])
        im = im.resize((int(im.size[0] * sc) + 1, int(im.size[1] * sc) + 1), Image.LANCZOS)
        scene.alpha_composite(im.crop((0, 0, W, H)))
    else:
        g = Image.linear_gradient("L").resize((W, H))
        scene = Image.merge("RGBA", (g.point(lambda v: 40 + v // 5), g.point(lambda v: 60 + v // 6),
                                     g.point(lambda v: 40 + v // 8), Image.new("L", (W, H), 255)))
    # HUD bar: design y 560..720 (160 px) -> art height 320 @2x? The art is 260 px for 173 design px.
    hud_h = 175 * S
    hud = nine(_load("hud_bar.png"), W, int(260 * hud_h / 173 / 1.5 * 1.0), MARGINS["hud_bar.png"])
    hud = hud.resize((W, hud_h), Image.LANCZOS)
    y_hud = H - hud_h
    scene.alpha_composite(hud, (0, y_hud))

    k = S / 2.0  # 2x art -> design px * S
    for (x0, x1) in ((432, 866), (878, 1272)):
        sp = nine(_load("panel.png"), int((x1 - x0) * 2), int(128 * 2), MARGINS["panel.png"])
        scene.alpha_composite(sp.resize((int((x1 - x0) * S), int(128 * S)), Image.LANCZOS),
                              (int(x0 * S), y_hud + int(40 * S)))
    # --- player section: panel + portrait + bars
    pan = nine(_load("panel.png"), int(640), int(250), MARGINS["panel.png"])
    pan = pan.resize((int(640 * k * 0.95), int(250 * k * 0.95)), Image.LANCZOS)
    scene.alpha_composite(pan, (int(120 * S), y_hud + int(26 * S)))
    port = _fake_portrait(236, "hero")
    port = _circle_mask(port, 118)
    pf = _load("portrait_frame.png")
    px, py = int(8 * S), H - int(176 * S)
    ps = int(160 * S)
    scene.alpha_composite(port.resize((int(ps * 236 / 320), int(ps * 236 / 320)), Image.LANCZOS),
                          (px + int(ps * 42 / 320), py + int(ps * 42 / 320)))
    scene.alpha_composite(pf.resize((ps, ps), Image.LANCZOS), (px, py))
    lb = _load("level_badge.png").resize((int(46 * S), int(46 * S)), Image.LANCZOS)
    scene.alpha_composite(lb, (px + int(6 * S), py + int(112 * S)))
    _text(scene, (px + int(29 * S), py + int(135 * S)), "15", int(22 * S))
    _bar(scene, int(170 * S), y_hud + int(44 * S), int(250 * S), int(28 * S), "bar_fill_hp.png", 1.0, "320 / 320")
    _bar(scene, int(170 * S), y_hud + int(76 * S), int(250 * S), int(28 * S), "bar_fill_mana.png", 0.8, "120 / 150")
    _bar(scene, int(170 * S), y_hud + int(110 * S), int(250 * S), int(14 * S), "bar_fill_xp.png", 0.45, "")
    # --- centre: attack ribbon + skill slots
    rb = nine(_load("ribbon_button.png"), 720, 150, MARGINS["ribbon_button.png"])
    rw, rh = int(330 * S), int(69 * S)
    rx, ry = int((444 + (5 * 70 + 66) / 2) * S) - rw // 2, y_hud - int(24 * S)
    scene.alpha_composite(rb.resize((rw, rh), Image.LANCZOS), (rx, ry))
    _text(scene, (rx + rw // 2 + int(14 * S), ry + rh // 2), "Attack", int(30 * S), fill=(255, 238, 200))
    ids = ["slash", "shield_break", "iron_wall", "battle_cry", "fireball", "shadow_step"]
    slot = _load("skill_slot.png")
    slot_a = _load("skill_slot_active.png")
    slot_d = _load("skill_slot_disabled.png")
    num = _load("slot_number.png")
    ss = int(66 * S)
    for i, sid in enumerate(ids):
        x = int(444 * S) + i * int(70 * S)
        y = y_hud + int(58 * S)
        ic = Image.open(os.path.join(SKILL_OUT, sid + ".png")).convert("RGBA")
        isz = int(ss * 144 / 180)
        scene.alpha_composite(ic.resize((isz, isz), Image.LANCZOS), (x + (ss - isz) // 2, y + (ss - isz) // 2))
        fr = slot_a if i == 3 else (slot_d if i == 5 else slot)
        scene.alpha_composite(fr.resize((ss, ss), Image.LANCZOS), (x, y))
        nb = num.resize((int(24 * S), int(20 * S)), Image.LANCZOS)
        nx, ny = x + ss // 2 - nb.size[0] // 2, y + ss - int(12 * S)
        scene.alpha_composite(nb, (nx, ny))
        _text(scene, (nx + nb.size[0] // 2, ny + nb.size[1] // 2), str(i + 1), int(14 * S), stroke=1)
    # --- secondary buttons (Defend / Potion)
    for j, (lab, icn) in enumerate((("Defend", "icon_defend.png"), ("Potion", "icon_potion.png"))):
        b = nine(_load("button.png"), 256, 96, MARGINS["button.png"]).resize((int(118 * S), int(44 * S)), Image.LANCZOS)
        bx, by = int(170 * S) + j * int(126 * S), y_hud + int(130 * S)
        scene.alpha_composite(b, (bx, by))
        ic = _load(icn).resize((int(32 * S), int(32 * S)), Image.LANCZOS)
        scene.alpha_composite(ic, (bx + int(10 * S), by + int(6 * S)))
        _text(scene, (bx + int(72 * S), by + int(22 * S)), lab, int(16 * S))
    # --- right: menu buttons
    menu = [("Inventory", "icon_bag.png"), ("Quests", "icon_quests.png"), ("Map", "icon_map.png"),
            ("Options", "icon_settings.png")]
    rbn = _load("round_button.png")
    for i, (lab, icn) in enumerate(menu):
        d = int(66 * S)
        x = int(900 * S) + i * int(92 * S)
        y = y_hud + int(56 * S)
        scene.alpha_composite(rbn.resize((d, d), Image.LANCZOS), (x, y))
        ic = _load(icn).resize((int(d * 0.66), int(d * 0.66)), Image.LANCZOS)
        scene.alpha_composite(ic, (x + int(d * 0.17), y + int(d * 0.17)))
        _text(scene, (x + d // 2, y + d + int(14 * S)), lab, int(16 * S))
    # --- enemy nameplate (top right of the HUD), tucked under the enemy portrait
    es = int(112 * S)
    ex, ey = W - es - int(10 * S), y_hud - int(92 * S)
    npl = nine(_load("nameplate.png"), 640, 160, MARGINS["nameplate.png"])
    nw, nh = int(330 * S), int(80 * S)
    nx, ny = ex + int(40 * S) - nw, ey + es // 2 - nh // 2 - int(4 * S)
    scene.alpha_composite(npl.resize((nw, nh), Image.LANCZOS), (nx, ny))
    _text(scene, (nx + nw - int(66 * S), ny + int(24 * S)), "Magma Sentinel", int(17 * S), anchor="rm")
    _bar(scene, nx + int(60 * S), ny + int(36 * S), nw - int(118 * S), int(22 * S), "bar_fill_enemy.png", 0.72,
         "864 / 1,200")
    hole = int(es * 114 / 320)
    ep = _circle_mask(_fake_portrait(240, "enemy"), 120).resize((hole * 2 + 4, hole * 2 + 4), Image.LANCZOS)
    scene.alpha_composite(ep, (ex + es // 2 - hole - 2, ey + es // 2 - hole - 2))
    scene.alpha_composite(_load("portrait_frame_small.png").resize((es, es), Image.LANCZOS), (ex, ey))
    elb = _load("level_badge.png").resize((int(36 * S), int(36 * S)), Image.LANCZOS)
    scene.alpha_composite(elb, (ex + es - int(34 * S), ey + es - int(38 * S)))
    _text(scene, (ex + es - int(16 * S), ey + es - int(20 * S)), "18", int(17 * S))
    # --- turn badge (top centre)
    tb = nine(_load("turn_badge.png"), 280, 88, MARGINS["turn_badge.png"]).resize((int(150 * S), int(46 * S)), Image.LANCZOS)
    scene.alpha_composite(tb, (W // 2 - tb.size[0] // 2, int(14 * S)))
    _text(scene, (W // 2, int(37 * S)), "Turn 3", int(18 * S))
    return scene.resize((1280, 720), Image.LANCZOS)


def build_sheet():
    jobs = [n for n in kit_jobs()]
    W = 2000
    sheet = Image.new("RGBA", (W, 5200), (34, 36, 40, 255))
    d = ImageDraw.Draw(sheet)
    f = _font(22)
    fs = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "Nunito.ttf"), 15)
    sheet.alpha_composite(mock_hud(), (20, 50))
    d.text((20, 14), "Battle HUD mock-up (1280 x 720) assembled from assets/ui/v2", font=f, fill=(240, 220, 170))
    # skill icons
    y = 800
    d.text((1320, 14), "Skill icons (256 px; shown at 96 and 48)", font=f,
           fill=(240, 220, 170))
    for i, sid in enumerate(sorted(SKILLS)):
        im = Image.open(os.path.join(SKILL_OUT, sid + ".png")).convert("RGBA")
        x0, y0 = 1320 + (i % 4) * 166, 50 + (i // 4) * 124
        sheet.alpha_composite(im.resize((96, 96), Image.LANCZOS), (x0, y0))
        sheet.alpha_composite(im.resize((48, 48), Image.LANCZOS), (x0 + 100, y0 + 48))
        d.text((x0, y0 + 98), sid, font=fs, fill=(200, 200, 200))
    # every kit piece
    x, y, rowh = 20, 800, 0
    d.text((20, 774), "Kit pieces (assets/ui/v2) on a mid-grey checker; 9-slice margins L,T,R,B", font=f,
           fill=(240, 220, 170))
    for name in jobs:
        im = _load(name)
        scale = 1.0
        if im.size[0] > 900:
            scale = 900 / im.size[0]
        if name.startswith("icon_"):
            scale = 0.5
        tw, th = int(im.size[0] * scale), int(im.size[1] * scale)
        if x + tw > W - 20:
            x, y, rowh = 20, y + rowh + 40, 0
        chk = Image.new("RGBA", (tw, th), (70, 72, 76, 255))
        cd = ImageDraw.Draw(chk)
        for yy in range(0, th, 16):
            for xx in range(0, tw, 16):
                if (xx // 16 + yy // 16) % 2:
                    cd.rectangle((xx, yy, xx + 15, yy + 15), fill=(84, 86, 90, 255))
        chk.alpha_composite(im.resize((tw, th), Image.LANCZOS))
        sheet.alpha_composite(chk, (x, y))
        lab = "%s %dx%d" % (name, im.size[0], im.size[1])
        if name in MARGINS:
            lab += "  9s %s" % (",".join(str(v) for v in MARGINS[name]))
            l_, t_, r_, b_ = [int(v * scale) for v in MARGINS[name]]
            for gx in (x + l_, x + tw - r_):
                d.line((gx, y, gx, y + th), fill=(0, 255, 200, 255), width=1)
            for gy in (y + t_, y + th - b_):
                d.line((x, gy, x + tw, gy), fill=(0, 255, 200, 255), width=1)
        d.text((x, y + th + 4), lab, font=fs, fill=(210, 210, 210))
        x += max(tw, int(d.textlength(lab, font=fs))) + 24
        rowh = max(rowh, th)
    y += rowh + 60
    # 9-slice stretch demos
    d.text((20, y), "9-slice stretch tests", font=f, fill=(240, 220, 170))
    y += 36
    demo = [("panel.png", 760, 300), ("panel_parchment.png", 400, 300), ("nameplate.png", 900, 130),
            ("ribbon_button.png", 1000, 150), ("button.png", 420, 80), ("button_gold.png", 300, 110),
            ("tab_active.png", 320, 80), ("tab.png", 180, 80), ("turn_badge.png", 400, 88)]
    x, rowh = 20, 0
    for name, w, h in demo:
        im = nine(_load(name), w, h, MARGINS[name])
        if x + w > W - 20:
            x, y, rowh = 20, y + rowh + 20, 0
        sheet.alpha_composite(im, (x, y))
        x += w + 20
        rowh = max(rowh, h)
    y += rowh + 20
    bx = 20
    for name in BAR_COLORS:
        _bar(sheet, bx, y, 300, 44, name, 0.7, name[9:-4])
        bx += 320
    y += 70
    sheet = sheet.crop((0, 0, W, y))
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    sheet.convert("RGB").save(SHEET)
    print("  sheet ->", SHEET, sheet.size)


def main(argv):
    what = argv[1] if len(argv) > 1 else "all"
    if what in ("kit", "all"):
        print("kit ->", OUT)
        build_kit()
    if what in ("skills", "all"):
        print("skills ->", SKILL_OUT)
        build_skills()
    if what in ("sheet", "all"):
        build_sheet()
    if what not in ("kit", "skills", "sheet", "all"):
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

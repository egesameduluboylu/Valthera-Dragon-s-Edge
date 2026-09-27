"""Town NPC portraits: head-and-shoulders busts of the six people of Kıvılcımköy.

    python3 tools/art/npcs.py            # all six
    python3 tools/art/npcs.py nara smith # just these

writes assets/town/npc_{nara,smith,merchant,innkeeper,keeper,class_master}.png (512 x 512, transparent).

The busts are shown at 120-160 px in the town panels and the tutorial bubble and at up to 360 px in story
dialogs, so they are built for both: big, simple silhouettes and strong value contrast in the face, with
the fine work (catchlights, hair strands, stitching, glints) layered on top. Everyone turns three-quarters
to the right, toward the speech bubble that sits right of the portrait, and the light comes from the top
left as in all the other art.

Faces share one construction (see the "face kit" below): almond eyes with a heavy lash line, a two-tone
iris, a pupil and two catchlights; tapered brows; a nose made of a shadow plane and a lit tip; lips with
volume; and hair built from shaped, individually shaded locks with a sheen band.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

from PIL import Image, ImageChops, ImageDraw  # noqa: E402

from characters import curve, taper  # noqa: E402
from painter import (INK, RIM, SS, Painter, _blur, _dilate, _erode, _scale, _shift, hexc, ink_for,  # noqa: E402
                     light_tone, mix, shade, shadow_tone, texture)

SIZE = 512
U = 2.0            # this canvas is twice the size of the 256 px sprites; fixed pixel effects scale by this
LW = 2.6           # interior ink weight
OUTLINE = 5.5      # silhouette outline
NOLINE = dict(shadow=0, light=0, line=0)
WHITE = hexc("#ffffff")
DARK = hexc("#23161c")
EYE_WHITE = hexc("#fbf6ee")
GOLD = hexc("#f0bf48")
GOLD_D = hexc("#a8701c")
STEEL = hexc("#c4cfda")
IRON = hexc("#4c525c")
LEATHER = hexc("#7a4a2a")
WOOD = hexc("#9a6433")
BLUSH = hexc("#ff6f6a")


# ------------------------------------------------------------------ painter

class NPainter(Painter):
    """The soft Painter at 512 px: default ink weights, textures, rim light, contact shadows and glints are
    scaled up so the busts match the look of the 256 px sprites, and finish() fades glows at the border."""

    def __init__(self):
        super().__init__(SIZE, SIZE, soft=True)

    def shape(self, kind, pts, color, shadow=0.72, light=1.22, depth=0.14, line=LW, ink=INK, clip=None, **kw):
        return super().shape(kind, pts, color, shadow, light, depth, line, ink, clip, **kw)

    def paint_mask(self, m, color, shadow=0.72, light=1.22, depth=0.14, line=LW, ink=INK, clip=None, **opts):
        return super().paint_mask(m, color, shadow, light, depth, line, ink, clip, **opts)

    def _texture(self, c, box, kind, amount, color):
        t = texture(kind, self.img.size, int(SS * U)).crop(box)
        gain = amount * 0.8
        hi = t.point(lambda v: max(0, min(255, int((v - 128) * gain))))
        lo = t.point(lambda v: max(0, min(255, int((128 - v) * gain))))
        self._fill(ImageChops.multiply(hi, c), light_tone(color, 1.35), box[:2], solid=False)
        self._fill(ImageChops.multiply(lo, c), shadow_tone(color, 0.62), box[:2], solid=False)

    def _paint_soft(self, m, color, shadow, light, depth, line, ink, size, k, tex=None, tex_amt=1.0, spec=0.0,
                    rim=None, ao=None, gloss=0.0):
        # Painter._paint_soft with its fixed pixel sizes multiplied by U.
        r = max(1, int(line * SS))
        pad = int(k * 2.5 + 8 * SS * U)
        c, box = self._crop(m, pad)
        o = box[:2]
        transparent = color[3] == 0
        decorative = not shadow and not light
        ao = (0.32 if not decorative and not transparent else 0.0) if ao is None else ao
        if ao and size > 3 * SS * U:
            off = max(1, int(min(k * 0.35, 3 * SS * U) + SS * U * 0.6))
            sh = _blur(_shift(c, off, off), max(SS * U, min(k * 0.6, 5 * SS * U)))
            under = self.img.crop(box).getchannel("A")
            sh = ImageChops.multiply(ImageChops.subtract(sh, c), under)
            self._fill(_scale(sh, ao), (18, 10, 30, 255), o, solid=False)
        if not transparent:
            self._fill(c, color, o)
        if tex and not transparent:
            self._texture(c, box, tex, tex_amt, color)
        if shadow and not transparent:
            feather = max(1, k * 0.2)
            core = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, -k, -k), feather)))
            self._fill(core, shadow_tone(color, shadow), o, solid=False)
            k2 = int(k * 2.2) + 1
            broad = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, -k2, -k2), k2 * 0.8)))
            self._fill(_scale(broad, 0.5), shadow_tone(color, (1 + shadow) / 2), o, solid=False)
        if light and not transparent:
            kh = max(1, k // 2)
            hl = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, kh, kh), max(1, kh * 0.45))))
            self._fill(_scale(hl, 0.9), light_tone(color, light), o, solid=False)
            if size > 10 * SS * U:
                k3 = int(k * 1.6) + 1
                bloom = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, k3, k3), k3 * 0.9)))
                self._fill(_scale(bloom, 0.28), light_tone(color, (1 + light) / 2), o, solid=False)
        rim = (0.5 if shadow and size > 12 * SS * U else 0.0) if rim is None else rim
        inner = _erode(c, r) if (line or rim or spec) else c
        if rim and not transparent:
            rr = max(1, int(SS * 1.3 * U))
            band = ImageChops.subtract(inner, _shift(inner, -rr, -rr))
            self._fill(_scale(_blur(band, SS * 0.4 * U), rim), mix(light_tone(color, 1.4), RIM, 0.5), o,
                       solid=False)
        if spec and not transparent:
            s = max(1, int(min(k * 0.6, 3 * SS * U)))
            band = ImageChops.subtract(inner, _shift(inner, s, s))
            bx0, by0, bx1, by1 = c.getbbox() or (0, 0, 1, 1)
            fall = Image.new("L", c.size, 0)
            cx = bx0 + (bx1 - bx0) * 0.3
            cy = by0 + (by1 - by0) * 0.3
            rx, ry = (bx1 - bx0) * 0.55, (by1 - by0) * 0.55
            ImageDraw.Draw(fall).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
            fall = _blur(fall, max(rx, ry) * 0.35)
            band = ImageChops.multiply(_blur(band, SS * 0.5 * U), fall)
            self._fill(_scale(band, min(1.0, spec)), (255, 255, 255, 255), o, solid=False)
        if gloss and not transparent:
            bx0, by0, bx1, by1 = c.getbbox() or (0, 0, 1, 1)
            bw, bh = bx1 - bx0, by1 - by0
            g = Image.new("L", c.size, 0)
            ImageDraw.Draw(g).ellipse((bx0 + bw * 0.2, by0 + bh * 0.14, bx0 + bw * 0.46, by0 + bh * 0.34), fill=255)
            g = ImageChops.multiply(_blur(g, SS * 0.6 * U), inner)
            self._fill(_scale(g, min(1.0, gloss)), (255, 255, 255, 255), o, solid=False)
        if line:
            if ink == INK and not transparent:
                ink = ink_for(color)
            thin = _erode(c, max(1, int(r * 0.75)))
            d = max(1, int(r * 0.7))
            e = ImageChops.darker(thin, _shift(thin, -d, -d))
            self._fill(ImageChops.subtract(c, e), ink, o, solid=True)

    def finish(self, outline=OUTLINE, edge_fade=24, backlight=(255, 232, 196), back_alpha=120):
        big = self._grade(self.img, 0.8)
        out = big.resize((self.w, self.h), Image.LANCZOS)
        solid_big = ImageChops.darker(self.solid, big.getchannel("A"))
        solid = solid_big.resize((self.w, self.h), Image.LANCZOS)
        if backlight:  # a thin warm back light along the right-hand edges of the silhouette
            sm = solid.point(lambda v: 255 if v > 128 else 0)
            band = ImageChops.subtract(sm, _shift(sm, -5, 3))
            band = inter(_blur(band, 1.6), sm)
            band = band.crop((0, 0, self.w, self.h - 6)).resize((self.w, self.h - 6))
            full = Image.new("L", (self.w, self.h), 0)
            full.paste(band, (0, 0))
            layer = Image.new("RGBA", out.size, backlight + (0,))
            layer.putalpha(_scale(full, back_alpha / 255))
            out = Image.alpha_composite(out, layer)
        if edge_fade:  # glows that reach the border fade out instead of stopping at a hard edge
            ramp = Image.new("L", (self.w, self.h), 255)
            d = ImageDraw.Draw(ramp)
            for i in range(edge_fade):
                d.rectangle((i, i, self.w - 1 - i, self.h - 1 - i), outline=int(255 * (i / edge_fade) ** 1.5))
            a = out.getchannel("A")
            a_solid = ImageChops.multiply(a, solid)
            a_glow = ImageChops.multiply(ImageChops.subtract(a, a_solid), ramp)
            out.putalpha(ImageChops.add(a_solid, a_glow))
        if outline:
            grown = _dilate(solid_big.point(lambda v: 255 if v > 90 else 0), outline * SS)
            sil = Image.new("RGBA", out.size, INK)
            sil.putalpha(grown.resize((self.w, self.h), Image.LANCZOS))
            out = Image.alpha_composite(sil, out)
        return out


# ------------------------------------------------------------------ geometry

def closed(pts, steps=8):
    """Closed Catmull-Rom spline through pts."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k])
                                    * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(2)))
    return out


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def rot(pts, center, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = center
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def ring(cx, cy, rx, ry, n=48, a0=0, a1=360):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def union(p, *masks):
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def minus(a, b):
    return ImageChops.subtract(a, b)


def inter(a, b):
    return ImageChops.multiply(a, b)


# ------------------------------------------------------------------ painting inside a surface

def wash(p, clip, kind, pts, color, blur=6.0, **kw):
    """A soft-edged tone (shadow, blush, sheen) painted inside `clip` only."""
    m = p._mask(kind, pts, **kw)
    m = _blur(m, blur * SS)
    p._fill(inter(m, clip), color, solid=False)


def soft_stroke(p, pts, color, width, blur, clip=None):
    """A blurred line, optionally kept inside `clip` (folds, strands, creases)."""
    m = p._mask("line", pts, width=width)
    if blur:
        m = _blur(m, blur * SS)
    if clip is not None:
        m = inter(m, clip)
    p._fill(m, color, solid=False)


def line(p, pts, color, width, clip=None):
    """A crisp line (ink details), optionally clipped."""
    m = p._mask("line", pts, width=width)
    if clip is not None:
        m = inter(m, clip)
    p._fill(m, color, solid=False)


def tline(p, pts, color, w0, w1, steps=6, clip=None):
    """A tapered crisp line (lash lines, creases, strands) as a filled polygon."""
    m = p._mask("poly", taper(pts, w0, w1, steps))
    if clip is not None:
        m = inter(m, clip)
    p._fill(m, color, solid=False)


def ttaper(pts, w0, wm, w1, steps=8):
    """taper() that swells in the middle: width w0 -> wm -> w1."""
    c = curve(pts, steps) if len(pts) > 2 else list(pts)
    n = len(c)
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        t = i / max(1, n - 1)
        w = (w0 + (wm - w0) * (t / 0.5) if t < 0.5 else wm + (w1 - wm) * ((t - 0.5) / 0.5)) / 2
        w = w * (1 - 0.15 * math.sin(t * math.pi) ** 8)
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def sheen(p, clip, pts, width=10, alpha=150, color=None, blur=2.5):
    """A light band along a curve inside a glossy surface (hair sheen, leather, silk)."""
    color = color or WHITE
    soft_stroke(p, curve(pts, 6), color[:3] + (alpha,), width, blur, clip)


def glint(p, x, y, r, alpha=235):
    p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffffff", alpha))


def star4(cx, cy, r, inner=0.22, rot_deg=0):
    pts = []
    for i in range(8):
        rr = r if i % 2 == 0 else r * inner
        a = math.radians(rot_deg + i * 45 - 90)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def twinkle(p, x, y, r, color=hexc("#fff6c0")):
    p.glow((x, y), r * 1.8, color, 0.5)
    p.shape("poly", star4(x, y, r, 0.26), color, shadow=0, light=0, depth=0.2, line=1.6, ink=hexc("#8a5a1a"),
            rim=0, ao=0)


# ------------------------------------------------------------------ face kit

def cast(p, m, dx=8, dy=18, blur=10, strength=0.4, color=(40, 14, 34, 255)):
    """Soft shadow that the shape `m` (not yet painted) will cast onto what is already painted under it."""
    sh = _blur(_shift(m, int(dx * SS), int(dy * SS)), blur * SS)
    sh = inter(sh, p.img.getchannel("A"))
    sh = minus(sh, m)
    p._fill(_scale(sh, strength), color, solid=False)


def head_shape(p, pts, skin):
    """The face/skull silhouette: it casts a soft shadow down onto the neck and chest, then is painted with
    soft form shading and a rim light."""
    m = p._mask("poly", closed(pts, 8))
    cast(p, m)
    return p.paint_mask(m, skin, shadow=0.8, light=1.2, depth=0.1, rim=0.4)


def skin_shade(p, face, skin, cx, cy, w, h, turn=1):
    """Form shading on a face: a warm shadow down the far side and under the jaw, a lit plane on the near
    cheek and forehead. (cx, cy) is the centre of the face, `turn` 1 = looking right."""
    sh = mix(shade(skin, 0.78), hexc("#c0506a"), 0.22)
    wash(p, face, "ellipse", (cx + turn * w * 0.34 - w * 0.2, cy - h * 0.55, cx + turn * w * 0.34 + w * 0.5,
                              cy + h * 0.6), sh[:3] + (150,), blur=w * 0.035)
    wash(p, face, "ellipse", (cx - w * 0.55, cy + h * 0.34, cx + w * 0.55, cy + h * 0.9), sh[:3] + (70,),
         blur=w * 0.05)
    wash(p, face, "ellipse", (cx - turn * w * 0.1 - w * 0.34, cy - h * 0.46, cx - turn * w * 0.1 + w * 0.2,
                              cy + h * 0.06), light_tone(skin, 1.25)[:3] + (90,), blur=w * 0.05)


def blush(p, clip, x, y, rx, ry, alpha=95, color=BLUSH):
    wash(p, clip, "ellipse", (x - rx, y - ry, x + rx, y + ry), color[:3] + (alpha,), blur=rx * 0.28)


def almond(cx, cy, w, h, side=1, tilt=0.0, top=1.0, bottom=1.0):
    """Eye opening: a high arched upper lid and a flatter lower lid; `side` 1 puts the outer corner right."""
    s = side
    inner = (cx - s * w * 0.5, cy + h * 0.12)
    outer = (cx + s * w * 0.5, cy - h * 0.08 - tilt)
    up = [inner, (cx - s * w * 0.3, cy - h * 0.42 * top), (cx + s * w * 0.06, cy - h * 0.56 * top),
          (cx + s * w * 0.36, cy - h * 0.4 * top), outer]
    lo = [outer, (cx + s * w * 0.28, cy + h * 0.36 * bottom), (cx - s * w * 0.06, cy + h * 0.46 * bottom),
          (cx - s * w * 0.36, cy + h * 0.34 * bottom), inner]
    upper = curve(up, 6)
    lower = curve(lo, 6)
    return upper, lower


def eye(p, cx, cy, w, h, iris, skin, side=1, look=(0.18, 0.02), lid=0.0, lash=None, lashes=0, tilt=0.0,
        crease=True, lower=0.55, iris_r=0.34, pupil=0.48, lid_color=None, bags=False, flick=1.0):
    """A cartoon eye: almond opening, eye white with the upper lid's shadow, a two-tone iris with a dark rim,
    a pupil and two catchlights, a heavy tapered lash line with a flick at the outer corner, a lid crease
    and a soft lower lid. `lid` 0..1 lowers a skin-coloured upper lid (sleepy, sly). `lashes` adds that
    many flicked lashes at the outer corner."""
    lash = lash if lash is not None else w * 0.1
    upper, lower_c = almond(cx, cy, w, h, side, tilt)
    opening = p._mask("poly", upper + lower_c[1:])
    # eye white with a cool shadow under the upper lid
    p.paint_mask(opening, EYE_WHITE, shadow=0, light=0, line=0, rim=0, ao=0)
    wash(p, opening, "ellipse", (cx - w * 0.7, cy - h * 1.2, cx + w * 0.7, cy - h * 0.05),
         hexc("#9a8fb8", 150), blur=h * 0.06)
    wash(p, opening, "ellipse", (cx + side * w * 0.2 - w * 0.3, cy - h * 0.5, cx + side * w * 0.2 + w * 0.5,
                                 cy + h * 0.6), hexc("#c8b8c8", 90), blur=h * 0.08)
    # iris
    ir = w * iris_r
    ix, iy = cx + look[0] * w, cy + look[1] * h
    iris_m = inter(p._mask("ellipse", (ix - ir, iy - ir * 1.08, ix + ir, iy + ir * 1.08)), opening)
    p._fill(iris_m, shade(iris, 0.72))
    wash(p, iris_m, "ellipse", (ix - ir * 0.8, iy - ir * 0.1, ix + ir * 0.8, iy + ir * 1.2),
         light_tone(iris, 1.45)[:3] + (230,), blur=ir * 0.12)
    wash(p, iris_m, "ellipse", (ix - ir * 1.2, iy - ir * 1.4, ix + ir * 1.2, iy - ir * 0.25),
         shade(iris, 0.4)[:3] + (200,), blur=ir * 0.1)
    rim_m = minus(iris_m, p._mask("ellipse", (ix - ir * 0.82, iy - ir * 0.9, ix + ir * 0.82, iy + ir * 0.9)))
    p._fill(rim_m, shade(iris, 0.35)[:3] + (220,), solid=False)
    pr = ir * pupil
    p._fill(inter(p._mask("ellipse", (ix - pr, iy - pr * 1.05, ix + pr, iy + pr * 1.05)), opening), DARK,
            solid=False)
    # catchlights (kept inside the opening)
    p._fill(inter(p._mask("ellipse", (ix - ir * 0.72, iy - ir * 0.78, ix - ir * 0.08, iy - ir * 0.14)), opening),
            WHITE, solid=False)
    p._fill(inter(p._mask("ellipse", (ix + ir * 0.22, iy + ir * 0.26, ix + ir * 0.52, iy + ir * 0.56)), opening),
            hexc("#ffffff", 210), solid=False)
    # sleepy / sly lid: skin comes down over the top of the eye
    if lid:
        lid_color = lid_color or skin
        drop_y = h * 1.05 * lid
        lid_edge = [(x, y + drop_y * (1 - abs((x - cx) / (w * 0.62)) ** 2.2)) for x, y in upper]
        le = sorted(lid_edge)
        lm = inter(p._mask("poly", [(le[0][0] - w, le[0][1]), (le[0][0] - w, cy - h * 2), (le[-1][0] + w, cy - h * 2),
                                    (le[-1][0] + w, le[-1][1])] + le[::-1]), opening)
        p.paint_mask(lm, lid_color, shadow=0.78, light=1.1, depth=0.3, line=0, rim=0, ao=0)
        upper = lid_edge
    # lash line: thick, tapered toward the inner corner, with a flick outside
    tline(p, upper, DARK, lash * 0.35, lash * 1.25)
    ox, oy = upper[-1]
    if flick:
        f_pts = [(ox - side * w * 0.04, oy + h * 0.02), (ox + side * w * 0.1 * flick, oy - h * 0.12 * flick),
                 (ox + side * w * 0.17 * flick, oy - h * 0.2 * flick)]
        tline(p, f_pts, DARK, lash, 0.3)
    for i in range(lashes):
        t = 0.62 + i * 0.14
        bx, by = upper[min(len(upper) - 1, int(len(upper) * t))]
        tline(p, [(bx, by), (bx + side * w * 0.08, by - h * 0.22), (bx + side * w * 0.16, by - h * 0.3)], DARK,
              lash * 0.55, 0.5)
    # crease above the lid and a soft lower lid
    if crease:
        cr = [(x, y - h * 0.3 - h * 0.1 * math.sin(math.pi * i / max(1, len(upper) - 1)))
              for i, (x, y) in enumerate(upper)]
        n = len(cr)
        tline(p, cr[int(n * 0.25):int(n * 0.9)], shade(skin, 0.62)[:3] + (190,), lash * 0.2, lash * 0.45)
    if lower:
        n = len(lower_c)
        seg = lower_c[int(n * 0.12):int(n * 0.8)]
        tline(p, seg, shade(skin, 0.55)[:3] + (int(230 * lower),), lash * 0.45, lash * 0.2)
    if bags:
        seg = [(x, y + h * 0.28) for x, y in lower_c[int(len(lower_c) * 0.15):int(len(lower_c) * 0.85)]]
        tline(p, seg, shade(skin, 0.62)[:3] + (200,), lash * 0.2, lash * 0.35)
    return opening


def happy_eye(p, cx, cy, w, h, skin, side=1, lash=None):
    """Eye squeezed shut with joy: an upturned arc and a cheek crease below."""
    lash = lash or w * 0.13
    arc = curve([(cx - w * 0.5, cy + h * 0.2), (cx, cy - h * 0.35), (cx + w * 0.5, cy + h * 0.2)], 8)
    tline(p, arc if side > 0 else arc[::-1], DARK, lash * 0.6, lash * 1.2)
    ox, oy = arc[-1] if side > 0 else arc[0]
    tline(p, [(ox, oy), (ox + side * w * 0.12, oy - h * 0.02)], DARK, lash, lash * 0.3)
    low = curve([(cx - w * 0.36, cy + h * 0.5), (cx, cy + h * 0.36), (cx + w * 0.36, cy + h * 0.5)], 6)
    tline(p, low, shade(skin, 0.6)[:3] + (200,), lash * 0.25, lash * 0.25)


def brow(p, pts, w0, w1, color, wm=None):
    """Tapered eyebrow along pts (from inner end to outer end)."""
    poly = ttaper(pts, w0, wm or (w0 + w1) * 0.62, w1) if wm else taper(pts, w0, w1, 8)
    return p.shape("poly", poly, color, shadow=0.7, light=1.3, depth=0.35, line=LW * 0.7, rim=0, ao=0.25)


def bushy_brow(p, x0, y0, x1, y1, color, thick=18, arch=-8, droop=6, locks=4):
    """A big hairy brow: a rounded tuft at the inner end (x0, y0) from which pointed locks fan out toward
    the outer end, the upper ones flicking up and the lower ones drooping by `droop`."""
    L = math.hypot(x1 - x0, y1 - y0)
    ang = math.atan2(y1 - y0, x1 - x0)
    fan = [(-0.34, 0.78), (-0.12, 1.02), (0.06, 1.06), (0.26, 0.86)][:locks]
    lk = []
    for da, fl in fan:
        a = ang + da * (1 if x1 > x0 else -1)
        tip = (x0 + math.cos(a) * L * fl, y0 + math.sin(a) * L * fl + droop * max(0, da + 0.1) * 3)
        mid = (x0 + math.cos(a) * L * fl * 0.5, y0 + math.sin(a) * L * fl * 0.5 + arch * (1 - abs(da)))
        lk.append(([(x0, y0), mid, tip], thick * 0.62, thick * 0.5))
    r = thick * 0.45
    base = p._mask("ellipse", (x0 - r, y0 - r * 0.9, x0 + r, y0 + r * 0.9))
    return hair_mass(p, lk, color, base=base, shadow=0.64, light=1.3, depth=0.3, sheen_alpha=150, gap_alpha=170,
                     line_c=shade(color, 0.45), rim=0, sheen_t=(0.15, 0.55))


def nose_34(p, face, skin, bridge, tip, r, side=1, nostril=True, ink_alpha=200, ball=True):
    """Three-quarter nose: a shadow plane on the far side of the bridge, a round lit tip, a nostril and a
    short ink stroke that shapes the far wing."""
    bx, by = bridge
    tx, ty = tip
    plane = [(bx + side * r * 0.1, by), (bx + side * r * 0.6, by + (ty - by) * 0.5), (tx + side * r * 0.95, ty + r * 0.2),
             (tx + side * r * 0.2, ty + r * 1.0), (tx - side * r * 0.1, ty + r * 0.2),
             (bx - side * r * 0.25, by + (ty - by) * 0.4)]
    wash(p, face, "poly", closed(plane, 6), mix(shade(skin, 0.72), hexc("#b0406a"), 0.2)[:3] + (150,), blur=r * 0.22)
    tipm = None
    if ball:
        tipm = p.shape("ellipse", (tx - r, ty - r * 0.85, tx + r, ty + r * 0.85), skin, shadow=0.84, light=1.25,
                       depth=0.3, line=0, rim=0, ao=0.12)
    else:
        wash(p, face, "ellipse", (tx - r * 0.7, ty - r * 0.6, tx + r * 0.5, ty + r * 0.4),
             light_tone(skin, 1.3)[:3] + (120,), blur=r * 0.2)
    glint(p, tx - r * 0.35, ty - r * 0.35, r * 0.24, 200)
    # ink: the far wing and the underside
    under = curve([(tx - side * r * 1.0, ty + r * 0.35), (tx - side * r * 0.3, ty + r * 0.95),
                   (tx + side * r * 0.5, ty + r * 0.85), (tx + side * r * 1.05, ty + r * 0.2)], 6)
    tline(p, under, shade(skin, 0.42)[:3] + (ink_alpha,), r * 0.12, r * 0.28)
    if nostril:
        nx = tx - side * r * 0.25
        p.flat("ellipse", (nx - r * 0.28, ty + r * 0.42, nx + r * 0.28, ty + r * 0.72), shade(skin, 0.4)[:3] + (220,))
    return tipm


def ball_nose(p, cx, cy, rx, ry, skin, color=None, side=1):
    """Big bulbous cartoon nose (old men, the innkeeper)."""
    color = color or skin
    m = p.shape("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry), color, shadow=0.74, light=1.3, depth=0.28,
                line=LW, rim=0.3, ao=0.4)
    glint(p, cx - rx * 0.35, cy - ry * 0.38, rx * 0.2, 220)
    p.flat("ellipse", (cx - rx * 0.1, cy - ry * 0.1, cx + rx * 0.05, cy + ry * 0.0), hexc("#ffffff", 0))
    for sx in (-1, 1):
        x = cx + sx * rx * 0.5 + side * rx * 0.1
        p.flat("ellipse", (x - rx * 0.16, cy + ry * 0.55, x + rx * 0.16, cy + ry * 0.8),
               shade(color, 0.35)[:3] + (200 if sx == side else 150,))
    return m


def ear(p, cx, cy, w, h, skin, side=-1):
    """An ear seen from the front-side; `side` -1 = on the left of the face."""
    s = side
    pts = closed([(cx - s * w * 0.3, cy - h * 0.45), (cx + s * w * 0.25, cy - h * 0.5), (cx + s * w * 0.5, cy - h * 0.1),
                  (cx + s * w * 0.3, cy + h * 0.35), (cx + s * w * 0.0, cy + h * 0.5), (cx - s * w * 0.35, cy + h * 0.2)],
                 6)
    m = p.shape("poly", pts, skin, shadow=0.76, light=1.2, depth=0.25, rim=0, ao=0.2)
    fold = curve([(cx - s * w * 0.05, cy - h * 0.3), (cx + s * w * 0.25, cy - h * 0.2), (cx + s * w * 0.2, cy + h * 0.15),
                  (cx - s * w * 0.02, cy + h * 0.25)], 6)
    tline(p, fold, shade(skin, 0.55)[:3] + (220,), w * 0.1, w * 0.06, clip=m)
    wash(p, m, "ellipse", (cx - w * 0.2, cy - h * 0.2, cx + w * 0.2, cy + h * 0.2), shade(skin, 0.7)[:3] + (120,),
         blur=w * 0.08)
    return m


def open_mouth(p, face, skin, outline_pts, lips=hexc("#c8505a"), tongue=True, teeth=True, lower_lip=True,
               inner=hexc("#5a1a26"), teeth_h=0.28):
    """Open mouth from a closed outline: dark inside, upper teeth, a tongue, and a lit lower lip."""
    pts = closed(outline_pts, 8)
    m = p.shape("poly", pts, inner, shadow=0.7, light=0, depth=0.3, line=LW * 0.9, ink=DARK, rim=0, ao=0)
    bx0, by0, bx1, by1 = [v / SS for v in m.getbbox()]
    if teeth:
        t = p._mask("rect", (bx0 - 4, by0 - 4, bx1 + 4, by0 + (by1 - by0) * teeth_h), radius=2)
        tm = inter(t, _erode(m, SS * 0.8))
        p._fill(tm, hexc("#fffaf2"), solid=False)
        wash(p, tm, "rect", (bx0, by0 - 10, bx1, by0 + (by1 - by0) * 0.1), hexc("#b8a8b8", 160), blur=2)
    if tongue:
        tx = (bx0 + bx1) / 2 + (bx1 - bx0) * 0.06
        tw = (bx1 - bx0) * 0.34
        tm = inter(p._mask("ellipse", (tx - tw, by1 - (by1 - by0) * 0.42, tx + tw, by1 + (by1 - by0) * 0.3)),
                   _erode(m, SS))
        p._fill(tm, hexc("#e86a7a"), solid=False)
        wash(p, tm, "ellipse", (tx - tw * 0.6, by1 - (by1 - by0) * 0.35, tx + tw * 0.1, by1 - (by1 - by0) * 0.15),
             hexc("#ffb0b8", 170), blur=2)
    if lower_lip:
        lip = curve([(bx0 + (bx1 - bx0) * 0.22, by1 + 3.5), (bx0 + (bx1 - bx0) * 0.5, by1 + 5.5),
                     (bx0 + (bx1 - bx0) * 0.78, by1 + 3.5)], 6)
        tline(p, lip, light_tone(lips, 1.3)[:3] + (150,), 2.0, 2.0)
    return m


def tint(p, m, color, alpha):
    """Tints an already painted mask (warm skin, coloured light from a glowing prop)."""
    p._fill(_scale(m, alpha / 255), color[:3] + (255,), solid=False)


def light_from(p, m, center, radius, color, alpha=110):
    """Coloured light from a glowing prop falling on the painted mask `m`, fading with distance."""
    cx, cy = center
    g = Image.new("L", p.img.size, 0)
    ImageDraw.Draw(g).ellipse(((cx - radius) * SS, (cy - radius) * SS, (cx + radius) * SS, (cy + radius) * SS),
                              fill=255)
    g = _blur(g, radius * SS * 0.45)
    p._fill(_scale(inter(g, m), alpha / 255), color[:3] + (255,), solid=False)


def capsule(x0, y0, x1, y1, n=10):
    """Stadium outline (a rounded bar) filling the box, as a polygon (so it can be rotated)."""
    r = min(x1 - x0, y1 - y0) / 2
    pts = []
    if x1 - x0 >= y1 - y0:
        for i in range(n + 1):
            a = math.pi / 2 + math.pi * i / n
            pts.append((x0 + r + r * math.cos(a), (y0 + y1) / 2 + r * math.sin(a)))
        for i in range(n + 1):
            a = -math.pi / 2 + math.pi * i / n
            pts.append((x1 - r + r * math.cos(a), (y0 + y1) / 2 + r * math.sin(a)))
    else:
        for i in range(n + 1):
            a = math.pi + math.pi * i / n
            pts.append(((x0 + x1) / 2 + r * math.cos(a), y0 + r + r * math.sin(a)))
        for i in range(n + 1):
            a = math.pi * i / n
            pts.append(((x0 + x1) / 2 + r * math.cos(a), y1 - r + r * math.sin(a)))
    return pts


def hand_grip(p, cx, cy, w, h, skin, angle=0.0, thumb=True, flip=False, knuckle_c=None):
    """A fist closed around something upright: the back of the hand and wrist on the left, four curled
    fingers stacked on the right (index on top, each a little shorter), knuckle creases, and the thumb
    wrapped across the top with its nail. (cx, cy) is the centre; `angle` tilts it, `flip` mirrors it."""
    c = (cx, cy)
    s = -1 if flip else 1

    def T(pts):
        return rot([(cx + (x - cx) * s, y) for x, y in pts], c, angle)
    back = closed([(cx - w * 0.52, cy - h * 0.3), (cx - w * 0.2, cy - h * 0.5), (cx + w * 0.2, cy - h * 0.46),
                   (cx + w * 0.3, cy + h * 0.2), (cx + w * 0.1, cy + h * 0.56), (cx - w * 0.4, cy + h * 0.6),
                   (cx - w * 0.6, cy + h * 0.15)], 6)
    m = p.shape("poly", T(back), skin, shadow=0.8, light=1.18, depth=0.22, rim=0.3)
    crease = shade(skin, 0.5)[:3] + (200,)
    rows = [(0.27, 0.56), (0.26, 0.6), (0.24, 0.55), (0.21, 0.44)]
    y = cy - h * 0.44
    boxes = []
    for fh, fl in rows:
        boxes.append((cx - w * 0.2, y, cx + w * fl, y + h * fh))
        y += h * fh * 0.92
    parts = []
    for bx in boxes[::-1]:
        fm = p.shape("poly", T(capsule(*bx)), skin, shadow=0.8, light=1.18, depth=0.3, line=LW * 0.8, rim=0, ao=0.35)
        x0, y0, x1, y1 = bx
        jx = x1 - (y1 - y0) * 0.75
        tline(p, T(curve([(jx + 2, y0 + (y1 - y0) * 0.25), (jx - 1, (y0 + y1) / 2), (jx + 2, y1 - (y1 - y0) * 0.25)],
                         4)), crease, 1.4, 1.4, clip=fm)
        wash(p, fm, "poly", T([(x0, y1 - (y1 - y0) * 0.3), (x1, y1 - (y1 - y0) * 0.3), (x1, y1), (x0, y1)]),
             shade(skin, 0.65)[:3] + (90,), blur=2)
        parts.append(fm)
    wash(p, m, "poly", T(ring(cx - w * 0.3, cy + h * 0.15, w * 0.2, h * 0.25, 24)), light_tone(skin, 1.3)[:3] + (60,),
         3)
    if thumb:  # the thumb wraps across the front of the index and middle fingers
        tpts = [(cx - w * 0.5, cy - h * 0.28), (cx - w * 0.14, cy - h * 0.2), (cx + w * 0.2, cy - h * 0.06)]
        tm = p.shape("poly", T(taper(curve(tpts, 5), w * 0.36, w * 0.27, 1)), skin, shadow=0.8, light=1.2,
                     depth=0.3, line=LW * 0.85, rim=0, ao=0.45)
        parts.append(tm)
        nx, ny = cx + w * 0.12, cy - h * 0.09
        p.shape("poly", T(closed([(nx - w * 0.07, ny - h * 0.07), (nx + w * 0.08, ny - h * 0.06),
                                  (nx + w * 0.08, ny + h * 0.04), (nx - w * 0.06, ny + h * 0.05)], 4)),
                light_tone(skin, 1.25), shadow=0.85, light=1.2, depth=0.3, line=LW * 0.5, rim=0, ao=0)
        tline(p, T([(cx - w * 0.22, cy - h * 0.3), (cx - w * 0.2, cy - h * 0.12)]), crease, 1.4, 1.4, clip=tm)
    allm = m
    for mm in parts:
        allm = union(p, allm, mm)
    tint(p, allm, hexc("#ff7a50"), 26)
    return allm


def open_hand(p, cx, cy, s, skin, angle=0.0, flip=False, curl=0.0, spread=1.0, back=True):
    """An open hand with the fingers up (before rotation): the palm, four fingers with rounded tips fanned a
    little and the thumb out to the side, painted as one shape; then finger joints, and either palm lines
    or (back=True) knuckles. `s` is the palm width; `curl` bends the tips over (cupping); `flip` mirrors it
    so the thumb is on the right."""
    c = (cx, cy)
    f = -1 if flip else 1

    def T(pts):
        return rot([(cx + (x - cx) * f, y) for x, y in pts], c, angle)
    palm = closed([(cx - s * 0.46, cy - s * 0.36), (cx + s * 0.48, cy - s * 0.4), (cx + s * 0.52, cy + s * 0.2),
                   (cx + s * 0.3, cy + s * 0.62), (cx - s * 0.3, cy + s * 0.64), (cx - s * 0.5, cy + s * 0.2)], 6)
    m = p._mask("poly", T(palm))
    fingers = [(-0.33, 0.72, -10), (-0.11, 0.84, -3), (0.11, 0.78, 4), (0.33, 0.6, 12)]
    fw = s * 0.25
    lines = []
    for fx, fl, fa in fingers:
        x0 = cx + fx * s * spread
        base = (x0, cy - s * 0.25)
        dx = math.sin(math.radians(fa)) * fl * s
        mid = (x0 + dx * 0.5 + curl * s * 0.05, cy - s * 0.25 - fl * s * 0.52)
        tip = (x0 + dx + curl * s * 0.22, cy - s * 0.25 - fl * s * (1 - curl * 0.18))
        m = union(p, m, p._mask("poly", T(taper(curve([base, mid, tip], 5), fw, fw * 0.86, 1))))
        r = fw * 0.43
        tx, ty = T([tip])[0]
        m = union(p, m, p._mask("ellipse", (tx - r, ty - r, tx + r, ty + r)))
        lines.append((base, mid, tip))
    th = [(cx - s * 0.36, cy + s * 0.34), (cx - s * 0.7, cy + s * 0.06), (cx - s * 0.84, cy - s * 0.26)]
    m = union(p, m, p._mask("poly", T(taper(curve(th, 5), s * 0.34, s * 0.25, 1))))
    tx, ty = T([th[-1]])[0]
    m = union(p, m, p._mask("ellipse", (tx - s * 0.12, ty - s * 0.12, tx + s * 0.12, ty + s * 0.12)))
    p.paint_mask(m, skin, shadow=0.8, light=1.18, depth=0.14, rim=0.3, ao=0.35)
    tint(p, m, hexc("#ff7a50"), 26)
    crease = shade(skin, 0.52)[:3] + (190,)
    for i, (base, mid, tip) in enumerate(lines):
        for t in (0.4, 0.7):
            jx, jy = lerp(base, tip, t)
            tline(p, T([(jx - fw * 0.28, jy + 1), (jx + fw * 0.28, jy - 1)]), crease, 1.8, 1.2, clip=m)
        if i < 3:  # the cleft between this finger and the next, running a little into the palm
            nb = lines[i + 1][0]
            gx = (base[0] + nb[0]) / 2
            tline(p, T([(gx, base[1] - s * 0.1), (gx, base[1] + s * 0.06)]), shade(skin, 0.4)[:3] + (220,), 2.2, 0.8,
                  clip=m)
        if back:
            wash(p, m, "poly", T(ring(base[0], base[1] + s * 0.04, fw * 0.4, fw * 0.3, 12)),
                 light_tone(skin, 1.35)[:3] + (130,), 1.5)
    if back:
        for fx in (-0.2, 0.0, 0.2):
            x = cx + fx * s
            tline(p, T([(x, cy - s * 0.12), (x - fx * s * 0.2, cy + s * 0.35)]), shade(skin, 0.7)[:3] + (90,), 2.0,
                  1.0, clip=m)
    else:
        tline(p, T(curve([(cx + s * 0.46, cy - s * 0.14), (cx + s * 0.1, cy - s * 0.12), (cx - s * 0.22, cy - s * 0.22)],
                         5)), crease, 1.4, 2.4, clip=m)
        tline(p, T(curve([(cx - s * 0.24, cy - s * 0.12), (cx - s * 0.22, cy + s * 0.2), (cx - s * 0.08, cy + s * 0.48)],
                         5)), crease, 2.4, 1.2, clip=m)
        wash(p, m, "poly", T(ring(cx + s * 0.12, cy + s * 0.18, s * 0.26, s * 0.22, 16)), shade(skin, 0.8)[:3] + (80,),
             4)
    return m


def fold(p, clip, pts, color, width=8, blur=3.0, hi=None, hi_off=(-4, -3), hi_alpha=110):
    """A cloth fold: a soft shadow crease with an optional lit ridge next to it."""
    soft_stroke(p, curve(pts, 6), color[:3] + (color[3] if len(color) > 3 else 150,), width, blur, clip)
    if hi:
        dx, dy = hi_off
        soft_stroke(p, curve([(x + dx, y + dy) for x, y in pts], 6), hi[:3] + (hi_alpha,), width * 0.55, blur * 0.8,
                    clip)


def stitch_line(p, pts, color, step=9, length=5, width=1.8, clip=None):
    c = curve(pts, 8)
    acc = 0.0
    out = []
    for (x0, y0), (x1, y1) in zip(c, c[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        t = acc
        while t < seg:
            out.append((x0 + (x1 - x0) * t / seg, y0 + (y1 - y0) * t / seg, (x1 - x0) / seg, (y1 - y0) / seg))
            t += step
        acc = t - seg
    for x, y, dx, dy in out:
        line(p, [(x, y), (x + dx * length, y + dy * length)], color, width, clip)


def gem(p, cx, cy, r, color, ry=None):
    ry = ry or r
    m = p.shape("ellipse", (cx - r, cy - ry, cx + r, cy + ry), color, shadow=0.5, light=1.6, depth=0.35,
                line=LW * 0.8, ink=shade(color, 0.3), rim=0, ao=0.3, gloss=0.9)
    p.flat("poly", [(cx - r * 0.1, cy + ry * 0.2), (cx + r * 0.55, cy + ry * 0.05), (cx + r * 0.3, cy + ry * 0.6)],
           light_tone(color, 1.5)[:3] + (140,))
    return m


def lock_poly(lk):
    """Polygon of one hair lock (pts, width[, root width[, tip width]]): it swells from the root to its
    widest point a third of the way along, then comes to a point."""
    pts, wm = lk[0], lk[1]
    w0 = lk[2] if len(lk) > 2 else wm * 0.8
    w1 = lk[3] if len(lk) > 3 else 1.0
    c = curve(pts, 10) if len(pts) > 2 else list(pts)
    n = len(c)
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        t = i / max(1, n - 1)
        if t < 0.35:
            w = w0 + (wm - w0) * math.sin(t / 0.35 * math.pi / 2)
        else:
            u = (t - 0.35) / 0.65
            w = w1 + (wm - w1) * (1 - u ** 1.6)
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    # a rounded cap at the root, so a lock never ends in a hard cut
    (x, y), (bx, by) = c[0], c[min(1, n - 1)]
    tx, ty = bx - x, by - y
    ln = math.hypot(tx, ty) or 1
    tx, ty = tx / ln, ty / ln
    cap = []
    for k in range(1, 8):
        a = math.pi * k / 8
        # sweep from the right side, round the back of the root, to the left side
        vx = -tx * math.sin(a) + (ty * math.cos(a))
        vy = -ty * math.sin(a) + (-tx * math.cos(a))
        cap.append((x + vx * w0 / 2, y + vy * w0 / 2))
    return left + right[::-1] + cap


def hair_mass(p, locks, color, base=None, clip=None, shadow=0.66, light=1.3, depth=0.16, sheen_c=None,
              sheen_t=(0.18, 0.5), sheen_alpha=150, line_c=None, gap_alpha=140, ink=None, rim=0.4, tex_amt=0.0):
    """Hair drawn as one shaded mass made of pointed locks: the union is painted once (so light falls over
    the whole shape), then each lock gets a dark parting line down one edge, a soft shadow where it tucks
    under its neighbour and a sheen stroke, which together read as a highlight band across the hair.
    `base` is an extra mask (e.g. the skull cap) merged into the mass."""
    polys = [lock_poly(lk) for lk in locks]
    m = base if base is not None else Image.new("L", p.img.size, 0)
    for poly in polys:
        m = union(p, m, p._mask("poly", poly))
    if clip is not None:
        m = inter(m, clip)
    p.paint_mask(m, color, shadow=shadow, light=light, depth=depth, line=LW, ink=ink or INK, rim=rim, ao=0.35,
                 tex="fur" if tex_amt else None, tex_amt=tex_amt)
    dark = line_c or mix(shade(color, 0.42), hexc("#3a0a2a"), 0.2)
    sc = sheen_c or light_tone(color, 1.6)
    for lk in locks:
        c = curve(lk[0], 10)
        n = len(c)
        wm = lk[1]
        # parting line along the lock's right-hand edge (as seen going root -> tip)
        edge = []
        for i in range(int(n * 0.08), n):
            x, y = c[i]
            a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1
            t = i / max(1, n - 1)
            off = wm * 0.36 * (1 - t ** 1.4)
            edge.append((x - (-dy / ln) * off, y - (dx / ln) * off))
        if len(edge) > 2:
            tline(p, edge, dark[:3] + (gap_alpha,), max(1.6, wm * 0.03), 0.6, clip=m)
            soft_stroke(p, edge[: int(len(edge) * 0.7)], shade(color, 0.6)[:3] + (70,), wm * 0.22, wm * 0.08, m)
        # sheen on the upper part of the lock
        seg = c[int(n * sheen_t[0]):int(n * sheen_t[1])]
        if sheen_alpha and len(seg) > 1:
            tline(p, seg, sc[:3] + (sheen_alpha,), max(2, wm * 0.2), 0.8, clip=m)
    return m


def strands(p, clip, flows, color, width=1.8, alpha=150):
    for pts in flows:
        c = curve(pts, 6)
        tline(p, c, color[:3] + (alpha,), width, width * 0.25, clip=clip)


# ------------------------------------------------------------------ characters

def nara():
    """Nara, the young dragonologist: copper hair in a messy bun with a pencil through it, big green eyes
    behind round glasses, freckles and an excited open smile, holding up a glowing dragon scale."""
    p = NPainter()
    rng = random.Random(11)
    skin = hexc("#f7cfa8")
    hair = hexc("#c9582c")
    blouse = hexc("#f4ede0")
    vest = hexc("#2f7a68")
    strap = hexc("#8a5230")
    scale_c = hexc("#ff9e3a")
    iris = hexc("#3aa66a")
    frame = hexc("#7a4a24")

    # ---- long hair behind the head and shoulders, ending in wavy points
    hair_mass(p, [
        ([(196, 110), (160, 180), (150, 270), (136, 350), (122, 392)], 70, 60),
        ([(226, 100), (196, 200), (190, 300), (176, 380)], 60, 50),
        ([(320, 100), (360, 180), (376, 270), (388, 350), (404, 386)], 72, 60),
        ([(300, 100), (340, 200), (344, 300), (356, 376)], 60, 50),
        ([(262, 90), (262, 200), (262, 330)], 150, 150, 40),
    ], shade(hair, 0.78), sheen_alpha=70, depth=0.1)

    # ---- the messy bun with a pencil stuck through it
    bun = p.shape("ellipse", (188, 18, 292, 106), hair, shadow=0.66, light=1.3, depth=0.2, rim=0.4)
    for pts in ([(214, 50), (246, 34), (276, 56)], [(206, 70), (236, 50), (272, 70), (262, 92)],
                [(222, 88), (246, 72), (270, 80)]):
        tline(p, curve(pts, 6), mix(shade(hair, 0.42), hexc("#3a0a2a"), 0.2)[:3] + (170,), 3.0, 0.8, clip=bun)
    sheen(p, bun, [(212, 58), (226, 42), (248, 36)], 8, 170, light_tone(hair, 1.6))
    hair_mass(p, [([(286, 84), (304, 90), (310, 104), (300, 110)], 11, 9),
                  ([(196, 76), (180, 84), (178, 98)], 10, 8)], hair, sheen_alpha=0, depth=0.3)
    pencil = taper([(318, 20), (192, 104)], 13, 13, 2)
    p.shape("poly", pencil, hexc("#f2c23a"), shadow=0.7, light=1.35, depth=0.35, line=LW * 0.9, rim=0)
    line(p, [(314, 26), (196, 104)], hexc("#fff0a0", 170), 3)
    p.shape("poly", [(318, 20), (334, 10), (328, 28)], hexc("#f0cfa0"), depth=0.3, line=LW * 0.8, rim=0)
    p.shape("poly", taper([(204, 96), (190, 105)], 13, 13, 2), hexc("#e87a8a"), depth=0.3, line=LW * 0.8, rim=0)
    line(p, [(206, 92), (212, 88)], hexc("#c8c4c0"), 6)
    for pts in ([(236, 96), (240, 70), (226, 60)], [(258, 94), (254, 72)]):
        tline(p, curve(pts, 6), mix(shade(hair, 0.42), hexc("#3a0a2a"), 0.2)[:3] + (170,), 3.0, 0.8, clip=bun)

    # ---- body: blouse, vest, satchel strap
    torso = closed([(208, 330), (300, 330), (352, 356), (420, 380), (470, 420), (500, 512), (20, 512), (40, 430),
                    (90, 384), (160, 356)], 8)
    body = p.shape("poly", torso, vest, shadow=0.72, light=1.2, depth=0.1, tex="cloth", tex_amt=0.5)
    fold(p, body, [(110, 420), (130, 470), (126, 512)], shade(vest, 0.55), 10, 4, light_tone(vest, 1.4))
    fold(p, body, [(400, 420), (386, 470), (392, 512)], shade(vest, 0.55), 10, 4, light_tone(vest, 1.4))
    # blouse V and collar
    neck = p.shape("poly", closed([(222, 290), (292, 290), (300, 350), (256, 372), (214, 350)], 6), skin,
                   shadow=0.7, light=1.1, depth=0.2, rim=0)
    wash(p, neck, "ellipse", (200, 270, 330, 330), mix(shade(skin, 0.7), hexc("#a04060"), 0.2)[:3] + (190,), blur=6)
    vneck = closed([(206, 344), (256, 420), (308, 344), (330, 360), (300, 512), (212, 512), (184, 360)], 6)
    bl = p.shape("poly", vneck, blouse, shadow=0.8, light=1.1, depth=0.12, tex="cloth", tex_amt=0.35)
    p.shape("poly", [(256, 420), (226, 512), (286, 512)], shade(blouse, 0.9), **NOLINE, clip=bl)
    for side in (-1, 1):  # collar points
        c = [(256, 382), (256 + side * 58, 336), (256 + side * 70, 350), (256 + side * 30, 414)]
        p.shape("poly", closed(c, 4), blouse, shadow=0.78, light=1.15, depth=0.3, tex="cloth", tex_amt=0.3)
    # vest fronts over the blouse
    for side in (-1, 1):
        vf = [(256 + side * 38, 512), (256 + side * 30, 440), (256 + side * 70, 360), (256 + side * 150, 380),
              (256 + side * 190, 512)]
        m = p.shape("poly", vf, vest, shadow=0.72, light=1.22, depth=0.12, tex="cloth", tex_amt=0.5, clip=body)
        line(p, [(256 + side * 30, 440), (256 + side * 70, 360)], light_tone(vest, 1.35)[:3] + (180,), 3, m)
    for y in (452, 484):
        p.shape("ellipse", (286, y - 7, 300, y + 7), GOLD, shadow=0.6, light=1.5, depth=0.35, line=LW * 0.7,
                spec=0.9, rim=0)
    # satchel strap across the chest, from the right shoulder down to the left hip
    sp = [(360, 356), (300, 420), (200, 512)]
    sm = p.shape("poly", taper(sp, 34, 38, 6), strap, shadow=0.68, light=1.3, depth=0.25, tex="leather",
                 tex_amt=0.6, clip=body, spec=0.3)
    stitch_line(p, [(x - 12, y - 10) for x, y in sp], hexc("#e8c898", 200), clip=sm)
    stitch_line(p, [(x + 12, y + 10) for x, y in sp], hexc("#e8c898", 200), clip=sm)
    p.shape("rect", (310, 392, 344, 424), GOLD, radius=4, shadow=0.6, light=1.5, depth=0.3, line=LW * 0.8, spec=0.9)
    p.shape("rect", (318, 400, 336, 416), shade(strap, 0.7), radius=2, **NOLINE)
    # satchel peeking in at the bottom right, scrolls poking out
    for x, col, top in ((400, "#f3e4bf", 400), (426, "#e8d0a0", 386), (452, "#f3e4bf", 404)):
        p.shape("rect", (x - 13, top, x + 13, top + 80), hexc(col), radius=10, shadow=0.75, depth=0.25, rim=0,
                tex="cloth", tex_amt=0.3)
        p.shape("ellipse", (x - 13, top - 8, x + 13, top + 12), shade(hexc(col), 0.82), depth=0.3, line=LW * 0.8)
        p.flat("ellipse", (x - 5, top - 2, x + 5, top + 5), hexc("#8a6a4a", 150))
    p.shape("poly", closed([(360, 452), (500, 440), (512, 512), (352, 512)], 3), strap, shadow=0.7,
                  light=1.25, depth=0.14, tex="leather", tex_amt=0.7)
    flap = p.shape("poly", closed([(356, 440), (504, 430), (496, 474), (430, 484), (362, 478)], 4),
                   shade(strap, 1.12), shadow=0.7, light=1.3, depth=0.25, tex="leather", tex_amt=0.6, spec=0.3)
    stitch_line(p, [(368, 470), (430, 476), (490, 466)], hexc("#e8c898", 200), clip=flap)
    p.shape("rect", (418, 462, 444, 492), GOLD, radius=4, shadow=0.6, light=1.5, depth=0.3, line=LW * 0.8, spec=0.9)

    # ---- head
    cx, cy = 262, 212
    face_pts = [(176, 170), (200, 112), (262, 92), (330, 112), (356, 170), (356, 222), (340, 272), (306, 314),
                (270, 330), (232, 318), (196, 284), (176, 236)]
    face = head_shape(p, face_pts, skin)
    skin_shade(p, face, skin, cx, cy, 190, 230)
    ear(p, 180, 222, 30, 46, skin, -1)
    # hair shadow on the forehead
    wash(p, face, "poly", closed([(170, 100), (360, 100), (360, 176), (300, 160), (250, 180), (200, 170)], 6),
         mix(shade(skin, 0.7), hexc("#a04040"), 0.3)[:3] + (170,), blur=5)
    # cheeks and freckles
    blush(p, face, 214, 262, 26, 15, 110)
    blush(p, face, 330, 258, 20, 14, 100)
    for _ in range(26):
        side = rng.choice((0, 1))
        x = rng.uniform(196, 238) if side == 0 else rng.uniform(310, 340)
        y = rng.uniform(244, 266)
        r = rng.uniform(1.4, 2.4)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#c0703c", 190))
    for _ in range(8):
        x, y = rng.uniform(264, 296), rng.uniform(236, 250)
        p.flat("ellipse", (x - 1.4, y - 1.4, x + 1.4, y + 1.4), hexc("#c0703c", 170))
    # eyes: wide open with excitement
    eye(p, 228, 214, 52, 46, iris, skin, side=-1, look=(0.12, 0.02), lash=5.5, lashes=2, lower=0.5)
    eye(p, 318, 212, 42, 44, iris, skin, side=1, look=(0.12, 0.02), lash=5.0, lashes=2, lower=0.5)
    brow(p, [(212, 174), (228, 166), (250, 170)], 7, 4, shade(hair, 0.75))
    brow(p, [(300, 170), (318, 164), (340, 172)], 7, 4, shade(hair, 0.75))
    # nose and mouth
    nose_34(p, face, skin, (288, 214), (290, 244), 11, side=1, ball=False)
    mouth = [(238, 272), (270, 270), (304, 266), (300, 290), (276, 306), (252, 298)]
    open_mouth(p, face, skin, mouth, teeth_h=0.3)
    tline(p, [(232, 270), (238, 272)], shade(skin, 0.45), 3, 1.5)
    tline(p, [(304, 266), (311, 260)], shade(skin, 0.45), 3, 1.5)
    # round glasses
    for (gx, gy, rx, ry) in ((228, 216, 40, 38), (318, 214, 32, 36)):
        rim_m = minus(p._mask("ellipse", (gx - rx, gy - ry, gx + rx, gy + ry)),
                      p._mask("ellipse", (gx - rx + 7, gy - ry + 7, gx + rx - 7, gy + ry - 7)))
        lens = p._mask("ellipse", (gx - rx + 5, gy - ry + 5, gx + rx - 5, gy + ry - 5))
        p._fill(lens, hexc("#d8f0ff", 40), solid=False)
        soft_stroke(p, [(gx - rx * 0.55, gy - ry * 0.1), (gx - rx * 0.1, gy - ry * 0.6)], hexc("#ffffff", 150),
                    7, 0.8, lens)
        soft_stroke(p, [(gx - rx * 0.3, gy + ry * 0.2), (gx + rx * 0.05, gy - ry * 0.25)], hexc("#ffffff", 110),
                    4, 0.8, lens)
        p.paint_mask(rim_m, frame, shadow=0.6, light=1.6, depth=0.4, line=LW * 0.8, rim=0, ao=0.4, spec=0.6)
    p.shape("poly", taper([(266, 212), (276, 206), (288, 210)], 6, 6, 4), frame, depth=0.4, light=1.5,
            line=LW * 0.7, rim=0)
    p.shape("poly", taper([(190, 208), (172, 204)], 6, 5, 2), frame, depth=0.4, line=LW * 0.7, rim=0)

    # ---- skull cap, bangs swept from a side parting, and long locks framing the face
    cap = p._mask("poly", closed([(176, 190), (178, 128), (212, 90), (262, 74), (320, 82), (358, 112), (372, 160),
                                  (368, 200), (340, 130), (262, 120), (200, 140)], 8))
    hair_mass(p, [
        ([(286, 84), (252, 106), (222, 142), (204, 176)], 46, 30),
        ([(270, 84), (232, 100), (200, 130), (184, 170)], 40, 30),
        ([(292, 88), (286, 118), (270, 150), (254, 170)], 36, 26),
        ([(300, 88), (320, 116), (330, 146), (326, 168)], 34, 26),
        ([(312, 90), (346, 114), (364, 150), (368, 188)], 32, 24),
        ([(196, 118), (176, 176), (168, 244), (174, 318), (186, 350)], 40, 30),
        ([(354, 124), (374, 190), (372, 262), (360, 320), (340, 350)], 36, 28),
        ([(282, 80), (272, 52), (296, 34)], 14, 12),
    ], hair, base=cap, sheen_t=(0.1, 0.45))
    sheen(p, cap, [(206, 112), (240, 96), (284, 92)], 10, 110, light_tone(hair, 1.6))

    # ---- raised forearm (sleeve rolled to the elbow) holding up a glowing dragon scale
    p.glow((104, 190), 120, scale_c, 0.55)
    sleeve = p.shape("poly", closed([(14, 512), (20, 452), (60, 430), (120, 440), (140, 470), (136, 512)], 6),
                     blouse, shadow=0.74, light=1.15, depth=0.16, tex="cloth", tex_amt=0.35)
    fold(p, sleeve, [(40, 470), (70, 490), (80, 512)], shade(blouse, 0.66), 7, 2.5)
    fold(p, sleeve, [(100, 470), (110, 500)], shade(blouse, 0.66), 6, 2.5)
    fore = p.shape("poly", taper([(84, 452), (96, 390), (108, 336)], 50, 40, 6), skin, shadow=0.76, light=1.2,
                   depth=0.2, rim=0.35)
    tint(p, fore, hexc("#ff7a50"), 26)
    wash(p, fore, "poly", [(100, 450), (140, 440), (130, 330), (110, 330)], shade(skin, 0.75)[:3] + (110,), blur=5)
    cuff = p.shape("poly", closed(capsule(40, 426, 136, 460), 1), shade(blouse, 0.96), shadow=0.72, light=1.2,
                   depth=0.3, tex="cloth", tex_amt=0.3)
    fold(p, cuff, [(60, 444), (118, 440)], shade(blouse, 0.7), 4, 1.5)
    sc = closed([(104, 272), (144, 226), (152, 176), (136, 140), (104, 128), (72, 140), (56, 176), (64, 226)], 6)
    p.shape("poly", sc, scale_c, shadow=0.6, light=1.5, depth=0.18, line=LW * 1.1, ink=hexc("#6a1a0a"),
            spec=1.0, rim=0)
    inner = [(104 + (x - 104) * 0.74, 196 + (y - 196) * 0.74) for x, y in sc]
    im = p.shape("poly", inner, hexc("#ffc85a"), shadow=0.7, light=1.5, depth=0.3, line=0, rim=0, ao=0)
    for k in (0.9, 0.72, 0.54):  # growth ridges following the rounded top
        arc = [(104 + (x - 104) * k, 150 + (y - 150) * k) for x, y in sc if y < 200]
        tline(p, curve(sorted(arc)[1:-1], 4), hexc("#e0661a", 150), 3.2, 3.2, clip=im)
    tline(p, [(104, 146), (104, 262)], hexc("#fff4c0", 190), 5, 2, clip=im)
    sheen(p, im, [(76, 186), (84, 156), (106, 142)], 9, 210, hexc("#fffbe0"))
    p.sparkle((136, 150), 12)
    hm = hand_grip(p, 110, 314, 64, 76, skin, angle=-6)
    light_from(p, union(p, hm, fore, cuff), (104, 200), 170, scale_c, 110)
    light_from(p, face, (104, 200), 200, scale_c, 55)
    for x, y, r in ((40, 110, 11), (170, 120, 8), (160, 290, 7), (30, 260, 7)):
        twinkle(p, x, y, r)
    return p.finish()


def smith():
    """Usta Örs, the blacksmith: a burly bald man with a huge grey beard, a ruddy bulb of a nose and a smear
    of soot on his head, in a leather apron with rolled sleeves. He is hard of hearing, so he cups his ear
    with one hand ("NE?") while the other holds his forge hammer upright."""
    p = NPainter()
    skin = hexc("#e2a27a")
    beard = hexc("#d8d2ce")
    beard_ink = hexc("#5e5866")
    shirt = hexc("#8e3328")
    apron = hexc("#70442a")
    strap = hexc("#4e2e1c")
    iron = hexc("#565c68")
    handle_c = hexc("#8a5a32")

    # ---- torso: shirt with the apron over it
    torso = closed([(170, 300), (330, 300), (430, 338), (486, 390), (508, 512), (4, 512), (22, 400), (70, 340)], 8)
    body = p.shape("poly", torso, shirt, shadow=0.7, light=1.2, depth=0.1, tex="cloth", tex_amt=0.6)
    fold(p, body, [(60, 400), (80, 460), (74, 512)], shade(shirt, 0.55), 10, 4, light_tone(shirt, 1.3))
    fold(p, body, [(470, 420), (462, 480)], shade(shirt, 0.55), 10, 4, light_tone(shirt, 1.3))
    ap = p.shape("poly", closed([(140, 360), (370, 360), (392, 512), (118, 512)], 2), apron, shadow=0.68, light=1.25,
                 depth=0.12, tex="leather", tex_amt=0.9, spec=0.2)
    stitch_line(p, [(150, 372), (130, 512)], hexc("#d8b890", 190), clip=ap)
    stitch_line(p, [(360, 372), (380, 512)], hexc("#d8b890", 190), clip=ap)
    for x0, x1 in ((150, 176), (360, 334)):  # shoulder straps
        p.shape("poly", taper([(x0, 372), ((x0 + x1) / 2 + (x0 - x1) * 0.6, 336), (x1 + (x1 - x0) * 1.5, 304)],
                              30, 28, 6), strap, shadow=0.66, light=1.3, depth=0.3, tex="leather", tex_amt=0.8)
    for x in (152, 358):
        p.shape("ellipse", (x - 10, 364, x + 10, 384), GOLD, shadow=0.55, light=1.6, depth=0.35, line=LW * 0.8,
                spec=1.0, rim=0)
    for x, y, r in ((200, 470, 14), (320, 450, 10), (262, 496, 8)):  # scorch marks
        wash(p, ap, "ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6), hexc("#2a1810", 120), blur=3)

    # ---- the hammer, held upright in front of the right shoulder
    p.shape("poly", taper([(430, 512), (430, 300), (428, 150)], 26, 24, 4), handle_c, shadow=0.66, light=1.3,
            depth=0.3, tex="wood", tex_amt=0.8, rim=0)
    for y in (240, 262, 284):  # leather wrap under the head
        p.shape("poly", taper([(414, y + 6), (444, y - 4)], 12, 12, 2), strap, shadow=0.7, light=1.3, depth=0.4,
                line=LW * 0.8, rim=0, tex="leather", tex_amt=0.6)
    head = closed([(360, 108), (470, 100), (492, 112), (494, 196), (470, 206), (362, 200), (348, 186),
                   (348, 120)], 3)
    h = p.shape("poly", head, iron, shadow=0.6, light=1.4, depth=0.18, tex="metal", tex_amt=0.9, spec=0.8,
                ink=hexc("#1a1c24"))
    p.shape("poly", closed([(470, 100), (492, 112), (494, 196), (470, 206)], 2), hexc("#c8d2dc"), shadow=0.6,
            light=1.5, depth=0.3, tex="metal", tex_amt=0.6, spec=1.0, ink=hexc("#1a1c24"))
    p.shape("rect", (410, 196, 450, 224), shade(iron, 0.9), radius=4, shadow=0.6, light=1.4, depth=0.3, spec=0.6)
    for x in (372, 392):
        p.shape("ellipse", (x - 5, 145, x + 5, 155), hexc("#9aa4b0"), depth=0.4, light=1.6, line=LW * 0.6, rim=0,
                ao=0.4)
    sheen(p, h, [(366, 118), (440, 112)], 6, 170)
    p.glow((488, 160), 34, hexc("#ff9a3a"), 0.4)

    # ---- far forearm and the fist on the handle
    fa = p.shape("poly", closed([(390, 512), (398, 460), (404, 420), (452, 414), (470, 460), (486, 512)], 6), skin,
                 shadow=0.76, light=1.2, depth=0.18, rim=0.35)
    tint(p, fa, hexc("#ff7a50"), 30)
    strands(p, fa, [[(420, 470), (424, 440)], [(446, 480), (446, 450)], [(430, 500), (434, 474)]],
            shade(skin, 0.55), 1.4, 140)
    sl = p.shape("poly", closed(capsule(372, 478, 500, 520), 1), shade(shirt, 1.1), shadow=0.7, light=1.25,
                 depth=0.3, tex="cloth", tex_amt=0.6)
    fold(p, sl, [(390, 496), (480, 492)], shade(shirt, 0.6), 5, 1.5)
    p.shape("poly", taper([(430, 440), (430, 360)], 26, 26, 2), handle_c, shadow=0.66, light=1.3, depth=0.3,
            tex="wood", tex_amt=0.8, rim=0)
    hand_grip(p, 434, 400, 76, 86, skin, angle=2, flip=True)

    # ---- head: bald, with the near ear
    cx, cy = 256, 196
    skull = [(150, 180), (160, 112), (204, 70), (262, 58), (322, 72), (362, 118), (372, 176), (364, 232),
             (344, 282), (300, 318), (240, 320), (190, 292), (160, 246)]
    face = head_shape(p, skull, skin)
    skin_shade(p, face, skin, cx, cy, 220, 250)
    wash(p, face, "ellipse", (190, 70, 262, 116), hexc("#fff2e0", 170), blur=5)  # shine on the scalp
    glint(p, 214, 90, 7, 220)
    for i, y in enumerate((124, 136)):  # brow wrinkles
        tline(p, curve([(236 + i * 4, y + 6), (270, y), (306, y + 2)], 6), shade(skin, 0.6)[:3] + (160,), 1.2, 2.4,
              clip=face)
    # ---- eyes: the near one squinting, the far one wide under a high brow
    eye(p, 222, 198, 38, 24, hexc("#4a6ab0"), skin, side=-1, look=(0.16, 0.06), lid=0.4, lash=5.5, lower=0.7,
        bags=True, flick=0.3)
    eye(p, 312, 190, 36, 34, hexc("#4a6ab0"), skin, side=1, look=(0.1, 0.04), lash=5.5, lower=0.6, bags=True,
        flick=0.3)
    bushy_brow(p, 250, 178, 182, 164, beard, thick=26, arch=-4, droop=10)
    bushy_brow(p, 288, 150, 352, 148, beard, thick=26, arch=-16, droop=8)
    blush(p, face, 212, 236, 26, 14, 90)
    blush(p, face, 340, 230, 18, 12, 80)

    # ---- beard: sideburns and a big mass of pointed locks falling from the cheeks
    beard_locks = [
        ([(168, 168), (164, 240), (170, 320), (186, 400)], 40, 30),
        ([(186, 214), (170, 290), (178, 360), (196, 420)], 56, 40),
        ([(214, 250), (204, 330), (218, 404), (230, 454)], 60, 50),
        ([(256, 262), (254, 350), (262, 432), (272, 480)], 64, 56),
        ([(300, 258), (312, 340), (308, 412), (298, 462)], 62, 52),
        ([(342, 226), (360, 290), (356, 360), (338, 420)], 54, 42),
        ([(234, 270), (228, 360), (242, 444)], 40, 36),
        ([(282, 268), (290, 360), (286, 444)], 40, 36),
    ]
    hair_mass(p, beard_locks, beard, shadow=0.62, light=1.25, depth=0.12, sheen_alpha=110, gap_alpha=170,
              line_c=beard_ink)
    open_mouth(p, face, skin, [(256, 256), (286, 252), (318, 256), (314, 290), (290, 304), (262, 294)],
               teeth_h=0.26)
    moust = [([(282, 236), (250, 244), (220, 262), (196, 292)], 36, 30),
             ([(288, 236), (318, 244), (342, 262), (354, 290)], 34, 28)]
    hair_mass(p, moust, shade(beard, 1.06), shadow=0.62, light=1.3, depth=0.25, sheen_alpha=150, gap_alpha=170,
              line_c=beard_ink)
    ball_nose(p, 288, 222, 26, 22, mix(skin, hexc("#e0605a"), 0.25))

    # ---- near forearm raised, the hand cupped behind the ear
    fore = closed([(40, 512), (38, 450), (54, 380), (80, 312), (96, 250), (134, 240), (146, 320), (156, 400),
                   (152, 460), (150, 512)], 8)
    arm = p.shape("poly", fore, skin, shadow=0.76, light=1.22, depth=0.16, rim=0.4)
    tint(p, arm, hexc("#ff7a50"), 30)
    wash(p, arm, "poly", [(112, 512), (190, 512), (160, 260), (126, 260)], shade(skin, 0.68)[:3] + (150,), blur=10)
    wash(p, arm, "ellipse", (44, 380, 84, 480), light_tone(skin, 1.3)[:3] + (110,), blur=10)
    wash(p, arm, "ellipse", (70, 300, 100, 360), light_tone(skin, 1.3)[:3] + (80,), blur=8)
    strands(p, arm, [[(60, 470), (70, 420), (80, 390)], [(92, 380), (100, 340)], [(46, 440), (54, 408)],
                     [(110, 420), (116, 380)], [(80, 330), (90, 300)]], shade(skin, 0.55), 1.5, 140)
    sleeve = p.shape("poly", closed([(8, 520), (14, 452), (42, 416), (100, 406), (158, 420), (178, 470),
                                     (180, 520)], 6), shade(shirt, 1.0), shadow=0.7, light=1.25, depth=0.2,
                     tex="cloth", tex_amt=0.6)
    fold(p, sleeve, [(50, 450), (70, 490), (64, 520)], shade(shirt, 0.55), 8, 3, light_tone(shirt, 1.3))
    fold(p, sleeve, [(130, 440), (146, 500)], shade(shirt, 0.55), 7, 3)
    sl = p.shape("poly", closed(rot(capsule(30, 388, 170, 434), (100, 411), -5), 1), shade(shirt, 1.12), shadow=0.7,
                 light=1.25, depth=0.3, tex="cloth", tex_amt=0.6)
    fold(p, sl, [(46, 416), (100, 406), (154, 404)], shade(shirt, 0.6), 5, 2)
    open_hand(p, 118, 210, 66, skin, angle=14, curl=0.7, spread=0.95)
    ear(p, 158, 206, 40, 60, skin, -1)
    wash(p, face, "ellipse", (150, 170, 190, 250), shade(skin, 0.6)[:3] + (0,), blur=4)
    return p.finish()


def potion(p, cx, cy, r, liquid, glass=hexc("#dff4ff", 90), glow=True):
    """Round-bellied potion flask with a cork: glass outline, glowing liquid with a meniscus and bubbles,
    and a bright reflection."""
    if glow:
        p.glow((cx, cy), r * 2.6, liquid, 0.55)
    p.shape("rect", (cx - r * 0.3, cy - r * 1.55, cx + r * 0.3, cy - r * 0.6), glass, shadow=0.8, light=1.3,
                   depth=0.3, line=LW, ink=hexc("#2a3a4a"), rim=0, ao=0)
    p.shape("rect", (cx - r * 0.4, cy - r * 1.62, cx + r * 0.4, cy - r * 1.4), hexc("#e8f6ff", 170),
                  radius=r * 0.08, shadow=0.8, light=1.3, depth=0.3, line=LW * 0.8, ink=hexc("#2a3a4a"), rim=0, ao=0)
    p.shape("rect", (cx - r * 0.26, cy - r * 1.95, cx + r * 0.26, cy - r * 1.45), hexc("#b07a4a"), radius=r * 0.08,
            shadow=0.66, light=1.3, depth=0.3, line=LW * 0.8, tex="wood", tex_amt=0.6, rim=0)
    body = p._mask("ellipse", (cx - r, cy - r, cx + r, cy + r))
    p._fill(body, glass, solid=True)
    liq = inter(p._mask("rect", (cx - r, cy - r * 0.25, cx + r, cy + r)), _erode(body, SS * 2.5))
    p.paint_mask(liq, liquid, shadow=0.6, light=1.5, depth=0.25, line=0, rim=0, ao=0)
    wash(p, liq, "ellipse", (cx - r * 0.5, cy - r * 0.1, cx + r * 0.9, cy + r * 0.9), light_tone(liquid, 1.5)[:3] + (150,),
         blur=r * 0.2)
    p._fill(inter(p._mask("ellipse", (cx - r * 0.95, cy - r * 0.34, cx + r * 0.95, cy - r * 0.14)), body),
            light_tone(liquid, 1.6)[:3] + (220,), solid=False)
    for bx, by, br in ((0.3, 0.3, 0.09), (-0.2, 0.55, 0.07), (0.45, 0.62, 0.05), (0.05, 0.1, 0.05)):
        x, y = cx + bx * r, cy + by * r
        p.shape("ellipse", (x - br * r, y - br * r, x + br * r, y + br * r), light_tone(liquid, 1.7)[:3] + (200,),
                shadow=0, light=0, line=1.2, ink=shade(liquid, 0.5), rim=0, ao=0)
    p.paint_mask(body, (0, 0, 0, 0), shadow=0, light=0, line=LW * 1.1, ink=hexc("#23303c"), rim=0, ao=0)
    soft_stroke(p, curve([(cx - r * 0.7, cy + r * 0.2), (cx - r * 0.72, cy - r * 0.3), (cx - r * 0.4, cy - r * 0.7)], 6),
                hexc("#ffffff", 220), r * 0.16, 0.6, body)
    glint(p, cx + r * 0.5, cy - r * 0.45, r * 0.08, 220)
    return body


def merchant():
    """Madam Pırıl, the merchant: glamorous and theatrical, with a huge purple feathered hat, auburn waves,
    violet eyeshadow over a sly half-lidded look, a knowing smirk, gold hoops and rings, showing off a
    glowing green potion."""
    p = NPainter()
    skin = hexc("#f6caa2")
    hair = hexc("#9a3a26")
    dress = hexc("#6e2f9e")
    hat = hexc("#7a3cb4")
    trim = GOLD
    teal = hexc("#2ec8a6")
    lips = hexc("#c8344a")
    shadow_c = hexc("#a870d8")

    # ---- hair behind: full auburn waves down to the shoulders
    hair_mass(p, [
        ([(186, 150), (150, 220), (160, 290), (128, 360), (140, 400)], 70, 60),
        ([(214, 150), (184, 250), (198, 320), (180, 390)], 60, 50),
        ([(330, 150), (372, 220), (362, 290), (390, 360), (380, 400)], 70, 60),
        ([(310, 150), (340, 250), (326, 320), (344, 390)], 60, 50),
        ([(260, 140), (260, 260), (262, 360)], 170, 170, 60),
    ], shade(hair, 0.8), sheen_alpha=80, depth=0.1)

    # ---- body: dress with puffed shoulders, lace at the neckline, gold trim
    torso = closed([(214, 330), (300, 330), (360, 352), (440, 372), (492, 420), (510, 512), (2, 512), (20, 420),
                    (76, 372), (152, 352)], 8)
    body = p.shape("poly", torso, dress, shadow=0.7, light=1.25, depth=0.1, tex="cloth", tex_amt=0.5, spec=0.15)
    for side in (-1, 1):  # puffed shoulders
        cxs = 256 + side * 170
        pm = p.shape("ellipse", (cxs - 90, 350, cxs + 90, 450), shade(dress, 1.05), shadow=0.66, light=1.3,
                     depth=0.16, tex="cloth", tex_amt=0.5, spec=0.3, clip=body)
        for k in (-1, 1):
            fold(p, pm, [(cxs + k * 30, 362), (cxs + k * 44, 410), (cxs + k * 50, 450)], shade(dress, 0.6), 7, 4)
        p.shape("poly", taper(curve([(cxs - side * 90, 440), (cxs, 452), (cxs + side * 86, 430)], 6), 10, 10, 1), trim,
                shadow=0.6, light=1.5, depth=0.4, line=LW * 0.7, spec=0.8, rim=0, clip=body)
    neck = p.shape("poly", closed([(226, 296), (292, 296), (300, 356), (258, 372), (216, 354)], 6), skin,
                   shadow=0.72, light=1.1, depth=0.2, rim=0)
    wash(p, neck, "ellipse", (200, 270, 330, 336), mix(shade(skin, 0.7), hexc("#a04060"), 0.2)[:3] + (190,), blur=6)
    chest = p.shape("poly", closed([(196, 356), (256, 344), (318, 356), (296, 420), (256, 446), (216, 420)], 6), skin,
                    shadow=0.8, light=1.15, depth=0.16, rim=0)
    wash(p, chest, "ellipse", (220, 330, 300, 380), shade(skin, 0.72)[:3] + (120,), blur=6)
    # lace ruffle along the neckline, then the gold trim
    lace = [(186, 350), (220, 424), (256, 452), (292, 424), (328, 350)]
    for (x0, y0), (x1, y1) in zip(lace, lace[1:]):
        for t in (0.0, 0.33, 0.66):
            x, y = lerp((x0, y0), (x1, y1), t)
            p.shape("ellipse", (x - 13, y - 10, x + 13, y + 12), hexc("#f6efe4"), shadow=0.8, light=1.1, depth=0.3,
                    line=LW * 0.7, rim=0, ao=0.2)
    p.shape("poly", taper(curve(lace, 6), 12, 12, 1), trim, shadow=0.6, light=1.5, depth=0.35, line=LW * 0.8, spec=0.8,
            rim=0)
    # a laced bodice panel below the neckline
    bod = p.shape("poly", closed([(222, 446), (256, 458), (290, 446), (300, 512), (212, 512)], 2), shade(dress, 0.8),
                  shadow=0.66, light=1.25, depth=0.2, tex="cloth", tex_amt=0.5, spec=0.2)
    for i, y in enumerate((466, 486, 506)):
        for sx in (-1, 1):
            p.shape("ellipse", (256 + sx * 22 - 4, y - 4, 256 + sx * 22 + 4, y + 4), trim, shadow=0.6, light=1.5,
                    depth=0.4, line=1.4, rim=0, ao=0.3)
        if i < 2:
            for sx in (-1, 1):
                tline(p, [(256 + sx * 22, y), (256 - sx * 22, y + 20)], trim, 3.4, 3.4, clip=bod)
    # necklace with a teal pendant
    nk = curve([(222, 350), (256, 384), (292, 350)], 8)
    for x, y in nk[::3]:
        p.shape("ellipse", (x - 4, y - 4, x + 4, y + 4), trim, shadow=0.6, light=1.6, depth=0.4, line=1.4, rim=0,
                ao=0.3)
    p.shape("poly", closed([(256, 380), (272, 398), (256, 424), (240, 398)], 3), trim, shadow=0.6, light=1.5,
            depth=0.35, line=LW * 0.8, spec=0.8)
    gem(p, 256, 400, 10, teal, 13)

    # ---- face
    cx, cy = 262, 222
    face_pts = [(184, 180), (204, 128), (262, 110), (326, 126), (352, 176), (352, 226), (336, 274), (304, 312),
                (272, 326), (238, 314), (204, 282), (186, 236)]
    face = head_shape(p, face_pts, skin)
    skin_shade(p, face, skin, cx, cy, 180, 220)
    blush(p, face, 218, 262, 26, 14, 100, hexc("#ff5a7a"))
    blush(p, face, 330, 256, 18, 12, 90, hexc("#ff5a7a"))
    # eyes: sly, half-lidded, violet shadow, long lashes
    for ex, ey, w, h, side in ((228, 214, 48, 38, -1), (316, 210, 40, 36, 1)):
        wash(p, face, "ellipse", (ex - w * 0.7, ey - h * 1.2, ex + w * 0.7, ey + h * 0.1), shadow_c[:3] + (170,),
             blur=6)
    eye(p, 228, 216, 48, 38, hexc("#7a4ac8"), skin, side=-1, look=(0.2, 0.1), lid=0.42, lash=6, lashes=3,
        lid_color=mix(skin, shadow_c, 0.45), lower=0.5)
    eye(p, 316, 212, 40, 36, hexc("#7a4ac8"), skin, side=1, look=(0.2, 0.1), lid=0.42, lash=6, lashes=3,
        lid_color=mix(skin, shadow_c, 0.45), lower=0.5)
    brow(p, [(212, 180), (228, 170), (254, 174)], 6, 3, shade(hair, 0.6))
    brow(p, [(298, 166), (318, 154), (344, 162)], 6, 3, shade(hair, 0.6))  # the far brow arched high
    nose_34(p, face, skin, (292, 214), (294, 248), 10, side=1, ball=False)
    # smirk: closed red lips lifted at the far corner
    up = curve([(246, 282), (262, 276), (276, 279), (290, 274), (312, 266)], 6)
    lo = curve([(312, 266), (298, 286), (274, 294), (254, 290), (246, 282)], 6)
    p.shape("poly", up + lo[1:], lips, shadow=0.66, light=1.35, depth=0.3, line=LW * 0.9, ink=hexc("#5a1020"),
                 rim=0, ao=0.2, gloss=0.5)
    tline(p, curve([(248, 283), (266, 283), (290, 278), (312, 266)], 6), hexc("#5a1020"), 2.0, 3.0)
    tline(p, [(312, 266), (318, 260)], shade(skin, 0.5), 3, 1)
    glint(p, 270, 288, 3, 200)
    p.shape("ellipse", (322, 276, 330, 284), hexc("#4a2020"), **NOLINE)  # beauty mark

    # ---- front hair: side-swept waves framing the face (the hat covers the crown)
    hair_mass(p, [
        ([(300, 118), (254, 128), (214, 160), (198, 196)], 50, 40),
        ([(260, 116), (222, 130), (192, 166), (182, 210)], 40, 30),
        ([(326, 124), (348, 160), (356, 196)], 34, 30),
        ([(190, 160), (172, 220), (186, 280), (166, 340), (178, 380)], 44, 36),
        ([(354, 170), (372, 230), (358, 290), (374, 340), (360, 376)], 40, 32),
    ], hair, sheen_t=(0.1, 0.4))
    # gold hoop earring on the near ear (under the hair)
    hoop = minus(p._mask("ellipse", (170, 250, 206, 300)), p._mask("ellipse", (177, 257, 199, 293)))
    p.paint_mask(hoop, trim, shadow=0.55, light=1.6, depth=0.4, line=LW * 0.7, spec=1.0, rim=0)

    # ---- the hat: three big feathers, a wide tilted brim, the tall crown on it, a gold band and a teal gem
    for pts, col, w in (([(318, 106), (378, 52), (450, 18), (500, 20)], hexc("#ff76b0"), 44),
                        ([(326, 110), (400, 76), (470, 70), (508, 88)], hexc("#ffd040"), 38),
                        ([(310, 104), (344, 44), (392, 10), (430, 4)], hexc("#46d0e0"), 36)):
        fm = p.shape("poly", lock_poly((pts, w, w * 0.3, 2)), col, shadow=0.66, light=1.3, depth=0.25, rim=0.3)
        c = curve(pts, 8)
        tline(p, c, shade(col, 0.55), 3.0, 1.0, clip=fm)
        for i in range(3, len(c) - 3, 3):  # barbs
            x, y = c[i]
            a, b = c[i - 1], c[i + 1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy) or 1
            for sgn in (-1, 1):
                tline(p, [(x, y), (x + (-dy / n * sgn) * w * 0.4 + dx / n * 8, y + (dx / n * sgn) * w * 0.4 + dy / n * 8)],
                      shade(col, 0.72)[:3] + (150,), 1.6, 0.6, clip=fm)
        sheen(p, fm, c[1:len(c) // 2], 5, 160)
    brim_pts = rot(ring(256, 138, 236, 46, 64), (256, 138), -5)
    bm = p.shape("poly", brim_pts, hat, shadow=0.6, light=1.35, depth=0.2, tex="cloth", tex_amt=0.5, spec=0.25)
    p.shadow_on(bm, 0.45, 6, 6)  # brim shadow over the face and hair
    wash(p, bm, "ellipse", (150, 112, 370, 160), shade(hat, 0.5)[:3] + (170,), blur=8)  # the crown's shadow
    sheen(p, bm, [(50, 150), (120, 128), (200, 114)], 7, 110)
    sheen(p, bm, [(300, 172), (400, 160), (470, 130)], 5, 70)
    crown = closed([(176, 136), (182, 64), (222, 28), (286, 20), (336, 38), (352, 84), (350, 126), (262, 142)], 8)
    cm = p.shape("poly", crown, hat, shadow=0.64, light=1.3, depth=0.14, tex="cloth", tex_amt=0.5, spec=0.2)
    fold(p, cm, [(252, 30), (244, 70), (250, 110)], shade(hat, 0.55), 10, 4, light_tone(hat, 1.4))
    fold(p, cm, [(210, 50), (200, 100)], shade(hat, 0.6), 8, 4)
    p.shape("poly", closed([(178, 104), (262, 110), (350, 96), (350, 124), (262, 140), (178, 134)], 4), trim,
            shadow=0.6, light=1.5, depth=0.3, line=LW * 0.9, spec=0.9)
    gem(p, 316, 116, 15, teal, 17)

    # ---- raised hand showing off the potion: a long sleeve with a lace cuff, rings on the fingers
    sleeve = p.shape("poly", closed([(4, 512), (20, 450), (62, 380), (92, 348), (142, 352), (150, 420),
                                     (156, 512)], 6), shade(dress, 1.05), shadow=0.7, light=1.25, depth=0.16,
                     tex="cloth", tex_amt=0.5, spec=0.2)
    fold(p, sleeve, [(60, 420), (76, 470), (70, 512)], shade(dress, 0.55), 8, 3, light_tone(dress, 1.4))
    fold(p, sleeve, [(112, 380), (124, 440)], shade(dress, 0.55), 7, 3)
    for i in range(6):
        x = 82 + i * 12
        p.shape("ellipse", (x - 10, 336 + abs(i - 2.5) * 2, x + 10, 360 + abs(i - 2.5) * 2), hexc("#f6efe4"),
                shadow=0.8, light=1.1, depth=0.3, line=LW * 0.7, rim=0, ao=0.2)
    p.shape("poly", taper([(78, 358), (150, 356)], 10, 10, 2), trim, shadow=0.6, light=1.5, depth=0.4,
            line=LW * 0.7, spec=0.8, rim=0)
    potion(p, 108, 232, 50, hexc("#3ee07a"))
    hm = hand_grip(p, 114, 312, 62, 72, skin, angle=-6)
    light_from(p, hm, (108, 240), 110, hexc("#3ee07a"), 32)
    light_from(p, face, (108, 240), 180, hexc("#5aff9a"), 30)
    for y in (296, 316):
        p.shape("poly", taper([(126, y - 2), (150, y - 4)], 6, 6, 2), trim, shadow=0.6, light=1.6, depth=0.4,
                line=LW * 0.6, spec=1.0, rim=0)
    for x, y, r in ((40, 170, 11), (170, 190, 8), (30, 300, 8), (470, 260, 9)):
        twinkle(p, x, y, r)
    return p.finish()


def stripes(p, clip, xs, y0, y1, width, color, bow=0.0, cx=256):
    """Vertical stripes across a garment, bowing outward away from x = cx to follow the body's roundness."""
    m = Image.new("L", p.img.size, 0)
    for x in xs:
        k = (x - cx) / 256.0
        pts = curve([(x, y0), (x + k * bow, (y0 + y1) / 2), (x + k * bow * 1.6, y1)], 6)
        m = union(p, m, p._mask("poly", taper(pts, width, width * 1.15, 6)))
    m = inter(m, clip)
    p._fill(m, color, solid=False)
    return m


def mug(p, x0, y0, x1, y1, wood=hexc("#b07a45")):
    """Wooden tankard with iron hoops, a handle on the right and froth spilling over the top."""
    w, h = x1 - x0, y1 - y0
    hm = minus(p._mask("poly", closed([(x1 - 6, y0 + h * 0.18), (x1 + w * 0.42, y0 + h * 0.2), (x1 + w * 0.44, y0 + h * 0.75),
                                       (x1 - 6, y0 + h * 0.8)], 5)),
               p._mask("poly", closed([(x1 + 2, y0 + h * 0.32), (x1 + w * 0.26, y0 + h * 0.34),
                                       (x1 + w * 0.26, y0 + h * 0.62), (x1 + 2, y0 + h * 0.64)], 5)))
    p.paint_mask(hm, wood, shadow=0.64, light=1.3, depth=0.3, tex="wood", tex_amt=0.8, rim=0)
    body = p.shape("poly", closed([(x0, y0), (x1, y0), (x1 + 2, y1 - 8), (x1 - 8, y1), (x0 + 8, y1),
                                   (x0 - 2, y1 - 8)], 3), wood, shadow=0.62, light=1.3, depth=0.2, tex="wood",
                   tex_amt=1.0, rim=0.4)
    for i in range(1, 5):
        x = x0 + w * i / 5
        line(p, [(x, y0 + 4), (x + (i - 2.5) * 1.2, y1 - 4)], shade(wood, 0.55)[:3] + (200,), 2.2, body)
    for y in (y0 + h * 0.2, y1 - h * 0.18):
        p.shape("rect", (x0 - 5, y - 8, x1 + 5, y + 8), IRON, radius=3, shadow=0.6, light=1.45, depth=0.35,
                spec=0.8, tex="metal", tex_amt=0.5)
        for x in (x0 + w * 0.2, x0 + w * 0.5, x0 + w * 0.8):
            p.shape("ellipse", (x - 3, y - 3, x + 3, y + 3), hexc("#9aa4b0"), depth=0.4, light=1.6, line=1.2, rim=0,
                    ao=0.3)
    # froth: a lumpy cap spilling down one side
    froth = closed([(x0 - 10, y0 + 6), (x0 - 4, y0 - 22), (x0 + w * 0.25, y0 - 38), (x0 + w * 0.55, y0 - 44),
                    (x0 + w * 0.85, y0 - 30), (x1 + 12, y0 - 8), (x1 + 8, y0 + 12), (x1 - w * 0.1, y0 + 30),
                    (x1 - w * 0.2, y0 + 12), (x0 + w * 0.5, y0 + 14), (x0 + w * 0.2, y0 + 10)], 6)
    fm = p.shape("poly", froth, hexc("#fffaf0"), shadow=0.84, light=1.1, depth=0.24, rim=0, ao=0.35)
    for bx, by, br in ((0.15, -0.1, 12), (0.45, -0.22, 15), (0.78, -0.12, 11), (0.3, 0.05, 8), (0.62, 0.02, 9)):
        x, y = x0 + bx * w, y0 + by * h
        wash(p, fm, "ellipse", (x - br, y - br, x + br, y + br), hexc("#e8dcc8", 150), blur=2)
        wash(p, fm, "ellipse", (x - br * 0.8, y - br * 0.9, x + br * 0.4, y + br * 0.1), hexc("#ffffff", 230), blur=2)
    for x, y, r in ((0.2, -0.22, 4), (0.5, -0.34, 5), (0.82, -0.2, 3)):
        glint(p, x0 + x * w, y0 + y * h, r, 240)
    return body


def innkeeper():
    """Hancı Bulut, the innkeeper and market host at the Han: round and jolly, bald on top with curly tufts
    over his ears, a big curled moustache, rosy cheeks and a laugh that squeezes his eyes shut, raising a
    frothy tankard, a towel over his shoulder."""
    p = NPainter()
    skin = hexc("#f2b48c")
    hair = hexc("#6e3c22")
    shirt = hexc("#f2e8d6")
    stripe = hexc("#c04a3a")
    apron = hexc("#f7f3ea")
    vest = hexc("#3e6a4a")

    # ---- a big round body: striped shirt, green waistcoat, white apron
    torso = closed([(180, 300), (340, 300), (440, 330), (500, 390), (512, 512), (0, 512), (14, 390), (80, 330)], 8)
    body = p.shape("poly", torso, shirt, shadow=0.74, light=1.15, depth=0.1, tex="cloth", tex_amt=0.5)
    stripes(p, body, range(-40, 560, 34), 290, 520, 12, stripe[:3] + (230,), bow=60)
    fold(p, body, [(60, 400), (74, 460), (70, 512)], shade(shirt, 0.6), 10, 4)
    fold(p, body, [(452, 400), (444, 470)], shade(shirt, 0.6), 10, 4)
    for side in (-1, 1):
        vp = [(256 + side * 30, 512), (256 + side * 50, 380), (256 + side * 90, 334), (256 + side * 190, 352),
              (256 + side * 230, 512)]
        vm = p.shape("poly", closed(vp, 4), vest, shadow=0.68, light=1.25, depth=0.14, tex="cloth", tex_amt=0.6,
                     clip=body)
        line(p, [(256 + side * 50, 380), (256 + side * 90, 334)], light_tone(vest, 1.4)[:3] + (180,), 3, vm)
    for x0, x1 in ((206, 232), (306, 280)):  # apron straps up round the neck
        p.shape("poly", taper([(x0, 400), (x1, 330)], 16, 14, 2), apron, shadow=0.76, light=1.12, depth=0.3,
                tex="cloth", tex_amt=0.4, rim=0)
    ap = p.shape("poly", closed([(196, 390), (316, 390), (336, 512), (176, 512)], 2), apron, shadow=0.76,
                 light=1.12, depth=0.14, tex="cloth", tex_amt=0.5)
    fold(p, ap, [(222, 400), (214, 512)], shade(apron, 0.72), 7, 3)
    fold(p, ap, [(292, 400), (300, 512)], shade(apron, 0.72), 7, 3)
    pk = p.shape("rect", (224, 440, 288, 490), shade(apron, 0.95), radius=6, shadow=0.76, light=1.1, depth=0.2,
                 tex="cloth", tex_amt=0.4)
    stitch_line(p, [(228, 448), (284, 448)], hexc("#b8b0a0", 200), clip=pk)
    p.shape("poly", taper([(272, 446), (282, 416)], 8, 6, 2), hexc("#e8b84a"), depth=0.4, line=LW * 0.7, rim=0)
    for x, y in ((206, 478), (310, 500)):
        wash(p, ap, "ellipse", (x - 12, y - 7, x + 12, y + 7), hexc("#c8a078", 110), blur=2)  # ale stains
    # towel over the far shoulder
    tw = p.shape("poly", closed([(330, 326), (392, 318), (436, 336), (456, 380), (470, 512), (404, 512), (398, 400),
                                 (372, 356)], 6), hexc("#f6f3ee"), shadow=0.74, light=1.12, depth=0.16, tex="cloth",
                 tex_amt=0.7)
    for y in (446, 466):
        tline(p, [(398, y), (466, y - 4)], hexc("#3a7ac8"), 8, 8, clip=tw)
    fold(p, tw, [(380, 340), (420, 380), (430, 440)], shade(hexc("#f6f3ee"), 0.7), 8, 3)
    for x in range(410, 470, 9):  # fringe
        tline(p, [(x, 508), (x + 1, 520)], hexc("#e8e2d8"), 3, 2)

    # ---- head: round, bald on top
    cx, cy = 262, 206
    head = [(150, 190), (160, 120), (204, 76), (262, 62), (324, 76), (366, 122), (376, 186), (370, 244),
            (350, 292), (308, 326), (256, 334), (204, 320), (168, 280)]
    face = head_shape(p, head, skin)
    skin_shade(p, face, skin, cx, cy, 226, 270)
    wash(p, face, "ellipse", (198, 78, 262, 118), hexc("#fff2e0", 170), blur=5)
    glint(p, 220, 94, 7, 220)
    tline(p, curve([(214, 318), (256, 330), (310, 318)], 6), shade(skin, 0.6)[:3] + (180,), 2.2, 2.2, clip=face)
    ear(p, 158, 214, 38, 56, skin, -1)
    # curly brown tufts over the ears
    hair_mass(p, [([(186, 132), (162, 146), (152, 170), (160, 190)], 30, 26),
                  ([(180, 150), (156, 172), (152, 196), (166, 208)], 28, 24),
                  ([(176, 176), (160, 204), (166, 228)], 22, 20),
                  ([(354, 128), (372, 148), (378, 172), (370, 190)], 26, 22),
                  ([(362, 150), (378, 176), (374, 200)], 22, 18)], hair, sheen_alpha=120, depth=0.3)

    # ---- laughing face
    happy_eye(p, 222, 198, 46, 30, skin, side=-1, lash=6)
    happy_eye(p, 316, 194, 40, 28, skin, side=1, lash=6)
    brow(p, [(198, 164), (220, 150), (246, 156)], 10, 5, hair, wm=12)
    brow(p, [(298, 150), (320, 140), (344, 150)], 10, 5, hair, wm=12)
    blush(p, face, 212, 244, 34, 22, 130, hexc("#ff5a5a"))
    blush(p, face, 344, 238, 22, 18, 120, hexc("#ff5a5a"))
    open_mouth(p, face, skin, [(240, 262), (284, 256), (330, 258), (322, 294), (290, 318), (256, 306)], teeth_h=0.24)
    moust = [([(286, 242), (254, 250), (222, 256), (196, 244), (190, 222), (204, 214)], 32, 28, 6),
             ([(292, 242), (322, 250), (352, 248), (372, 230), (370, 208), (356, 204)], 30, 26, 6)]
    hair_mass(p, moust, hair, shadow=0.62, light=1.35, depth=0.3, sheen_alpha=170)
    ball_nose(p, 290, 224, 27, 23, mix(skin, hexc("#e8706a"), 0.3))

    # ---- raised arm with the tankard: striped sleeve rolled up to the forearm
    sl = p.shape("poly", closed([(14, 512), (30, 440), (70, 376), (112, 340), (170, 350), (172, 430),
                                 (176, 512)], 6), shirt, shadow=0.72, light=1.15, depth=0.16, tex="cloth", tex_amt=0.5)
    stripes(p, sl, range(-20, 220, 30), 330, 520, 10, stripe[:3] + (230,), bow=-40, cx=90)
    fold(p, sl, [(60, 430), (80, 480), (74, 512)], shade(shirt, 0.6), 8, 3)
    fold(p, sl, [(140, 380), (150, 440)], shade(shirt, 0.6), 7, 3)
    p.shape("poly", taper([(122, 340), (136, 290)], 44, 40, 2), skin, shadow=0.74, light=1.2, depth=0.3, rim=0.3)
    cuff = p.shape("poly", closed(rot(capsule(96, 324, 184, 360), (140, 342), -8), 1), shirt, shadow=0.72,
                   light=1.2, depth=0.3, tex="cloth", tex_amt=0.5)
    stripes(p, cuff, range(90, 200, 22), 310, 370, 8, stripe[:3] + (230,), cx=140)
    fold(p, cuff, [(106, 348), (176, 334)], shade(shirt, 0.6), 4, 1.5)
    mug(p, 26, 188, 124, 300)
    hand_grip(p, 150, 272, 60, 74, skin, angle=4, flip=False)
    return p.finish()


def lantern(p, cx, top, s=1.0, lit=True):
    """Hanging iron lantern: a ring on top, a cap, four glowing panes between bars and a base."""
    col = hexc("#3e424c")
    if lit:
        p.glow((cx, top + 70 * s), 150 * s, hexc("#ffb040"), 0.55)
    ringm = minus(p._mask("ellipse", (cx - 14 * s, top - 6 * s, cx + 14 * s, top + 22 * s)),
                  p._mask("ellipse", (cx - 8 * s, top, cx + 8 * s, top + 16 * s)))
    p.paint_mask(ringm, col, shadow=0.6, light=1.5, depth=0.4, spec=0.7, rim=0)
    p.shape("poly", closed([(cx - 12 * s, top + 16 * s), (cx + 12 * s, top + 16 * s), (cx + 38 * s, top + 38 * s),
                            (cx - 38 * s, top + 38 * s)], 2), col, shadow=0.6, light=1.5, depth=0.3, spec=0.7,
            tex="metal", tex_amt=0.6)
    glass = p.shape("rect", (cx - 32 * s, top + 38 * s, cx + 32 * s, top + 108 * s), hexc("#ffcf6a"), radius=4 * s,
                    shadow=0.8, light=1.3, depth=0.2, rim=0, ink=hexc("#5a3a10"))
    wash(p, glass, "ellipse", (cx - 22 * s, top + 50 * s, cx + 22 * s, top + 100 * s), hexc("#fff8d8", 255), blur=8 * s)
    # the flame
    fl = closed([(cx, top + 52 * s), (cx + 9 * s, top + 74 * s), (cx + 7 * s, top + 88 * s), (cx, top + 92 * s),
                 (cx - 7 * s, top + 88 * s), (cx - 9 * s, top + 74 * s)], 5)
    p.shape("poly", fl, hexc("#ff9a2a"), shadow=0.8, light=1.5, depth=0.3, line=0, rim=0, ao=0)
    p.shape("ellipse", (cx - 4 * s, top + 74 * s, cx + 4 * s, top + 88 * s), hexc("#fffbe0"), **NOLINE)
    for x in (cx - 32 * s, cx, cx + 32 * s):
        p.shape("rect", (x - 5 * s, top + 36 * s, x + 5 * s, top + 110 * s), col, radius=2 * s, shadow=0.6,
                light=1.5, depth=0.35, line=LW * 0.8, spec=0.6, rim=0)
    p.shape("rect", (cx - 40 * s, top + 106 * s, cx + 40 * s, top + 122 * s), col, radius=4 * s, shadow=0.6,
            light=1.5, depth=0.3, spec=0.6, tex="metal", tex_amt=0.5)
    soft_stroke(p, [(cx - 24 * s, top + 46 * s), (cx - 24 * s, top + 98 * s)], hexc("#ffffff", 160), 5 * s, 1, glass)


def zzz(p, x, y, s, color=hexc("#cfe2ff")):
    pts = [(x, y), (x + 22 * s, y), (x, y + 24 * s), (x + 22 * s, y + 24 * s)]
    p.shape("poly", taper(pts, 8 * s, 8 * s, 1), color, shadow=0.8, light=1.3, depth=0.3, line=LW * 0.8,
            ink=hexc("#3a4a7a"), rim=0, ao=0)


def keeper():
    """Bekçi Tozlu, the dungeon gate keeper: a sleepy, grumpy old man in a floppy green nightcap and a
    patched cloak, heavy-lidded and mid-yawn under a droopy white moustache and a red nose, with his
    lantern held up in one hand and a broom over his shoulder."""
    p = NPainter()
    rng = random.Random(4)
    skin = hexc("#e8b28a")
    cloak = hexc("#7c6a56")
    cap = hexc("#5e8a5a")
    white = hexc("#e8e4de")
    white_ink = hexc("#6a6470")
    straw = hexc("#dcb862")

    # ---- broom over the far shoulder, bristles up
    p.shape("poly", taper([(330, 512), (470, 90)], 16, 14, 2), hexc("#b07a45"), shadow=0.66, light=1.3,
            depth=0.35, tex="wood", tex_amt=0.8, rim=0)
    straw_locks = []
    for i in range(7):
        t = (i - 3) / 3
        straw_locks.append(([(466 + t * 8, 100), (468 + t * 20, 56), (470 + t * 34, 12 + abs(t) * 10)], 18, 14, 3))
    hair_mass(p, straw_locks, straw, shadow=0.62, light=1.3, depth=0.2, sheen_alpha=120, line_c=hexc("#8a6a2a"),
              tex_amt=0.5)
    for y, w in ((92, 34), (76, 40)):
        p.shape("poly", taper([(466 - w / 2, y + 4), (466 + w / 2, y - 2)], 9, 9, 2), hexc("#b04a3a"), shadow=0.6,
                light=1.4, depth=0.4, line=LW * 0.8, rim=0)

    # ---- patched cloak with a bunched hood round the neck
    torso = closed([(180, 310), (340, 310), (430, 336), (494, 390), (512, 512), (0, 512), (16, 390), (80, 336)], 8)
    body = p.shape("poly", torso, cloak, shadow=0.68, light=1.2, depth=0.1, tex="cloth", tex_amt=0.9)
    for pts in ([(70, 400), (90, 460), (84, 512)], [(440, 400), (430, 470), (436, 512)], [(256, 420), (250, 512)],
                [(170, 430), (180, 512)], [(346, 430), (336, 512)]):
        fold(p, body, pts, shade(cloak, 0.55), 10, 4, light_tone(cloak, 1.3))
    for box, col in (((190, 440, 240, 486), "#8a5a8a"), ((336, 400, 386, 446), "#5a7a8a"), ((420, 452, 470, 500),
                                                                                           "#a07a3a")):
        x0, y0, x1, y1 = box
        p.shape("poly", closed([(x0, y0), (x1, y0 + 3), (x1 - 2, y1), (x0 + 2, y1 - 2)], 1), hexc(col),
                     shadow=0.66, light=1.25, depth=0.25, tex="cloth", tex_amt=0.8, clip=body)
        stitch_line(p, [(x0 + 4, y0 + 4), (x1 - 4, y0 + 6), (x1 - 5, y1 - 4), (x0 + 5, y1 - 5), (x0 + 4, y0 + 4)],
                    hexc("#efe2c4", 220), step=8, length=5, width=2.0)
    # the big iron key to the dungeon gate, on a cord round his neck
    cord_l = curve([(226, 372), (240, 408), (262, 428)], 6)
    cord_r = curve([(296, 372), (286, 406), (268, 428)], 6)
    kc = hexc("#7a7f8a")
    bow = minus(p._mask("ellipse", (244, 420, 290, 462)), p._mask("ellipse", (256, 432, 278, 450)))
    p.paint_mask(bow, kc, shadow=0.55, light=1.5, depth=0.35, spec=0.8, tex="metal", tex_amt=0.6, rim=0)
    p.shape("rect", (260, 460, 274, 512), kc, radius=3, shadow=0.55, light=1.5, depth=0.35, spec=0.8, rim=0)
    for y in (482, 498):
        p.shape("rect", (272, y, 292, y + 10), kc, radius=2, shadow=0.55, light=1.5, depth=0.35, spec=0.6, rim=0)

    # a thick knitted scarf wound round the neck, one end hanging down
    scarf_c = hexc("#d69a38")
    end = p.shape("poly", closed([(318, 360), (362, 356), (372, 480), (366, 500), (324, 500), (320, 480)], 3),
                  scarf_c, shadow=0.66, light=1.25, depth=0.2, tex="cloth", tex_amt=1.0)
    for y in (410, 440):
        tline(p, [(318, y), (372, y - 2)], hexc("#b0443a"), 12, 12, clip=end)
    for x in range(328, 368, 8):
        tline(p, [(x, 498), (x + 1, 516)], scarf_c, 4, 3)
    sc = p.shape("poly", closed([(146, 322), (256, 300), (370, 318), (396, 352), (344, 384), (256, 372), (168, 386),
                                 (122, 354)], 8), scarf_c, shadow=0.66, light=1.25, depth=0.2, tex="cloth",
                 tex_amt=1.0)
    for x in range(140, 390, 12):  # knit ribs
        k = (x - 256) / 140
        tline(p, [(x, 320 + 12 * k * k), (x + 2 * k, 372 + 6 * k * k)], shade(scarf_c, 0.7)[:3] + (120,), 2.4, 2.4,
              clip=sc)
    fold(p, sc, [(150, 350), (256, 344), (380, 346)], shade(scarf_c, 0.5), 10, 4)
    for cc in (cord_l, cord_r):
        p.shape("poly", taper(cc, 5, 5, 1), hexc("#8a6a4a"), shadow=0.7, light=1.3, depth=0.4, line=LW * 0.6, rim=0)

    # ---- head
    cx, cy = 256, 218
    head = [(158, 190), (170, 130), (212, 96), (262, 88), (320, 98), (356, 134), (366, 192), (362, 250),
            (342, 296), (300, 328), (254, 336), (206, 320), (172, 280)]
    face = head_shape(p, head, skin)
    skin_shade(p, face, skin, cx, cy, 208, 250)
    ear(p, 164, 222, 36, 54, skin, -1)
    # grey stubble on the jaw
    for _ in range(90):
        x, y = rng.uniform(186, 350), rng.uniform(262, 330)
        if ((x - 262) / 96) ** 2 + ((y - 236) / 96) ** 2 < 1:
            p.flat("ellipse", (x - 1.2, y - 1.2, x + 1.2, y + 1.2), hexc("#8a7a72", 150))
    # wrinkles
    for y in (150, 162):
        tline(p, curve([(232, y + 4), (268, y), (310, y + 4)], 6), shade(skin, 0.62)[:3] + (150,), 1.2, 2.2,
              clip=face)
    # sleepy, baggy eyes (the far one nearly shut)
    eye(p, 222, 214, 42, 30, hexc("#6a8a5a"), skin, side=-1, look=(0.1, 0.12), lid=0.62, lash=5.5, lower=0.7,
        bags=True, flick=0.2)
    eye(p, 314, 210, 38, 28, hexc("#6a8a5a"), skin, side=1, look=(0.1, 0.12), lid=0.75, lash=5.5, lower=0.7,
        bags=True, flick=0.2)
    for ex, ey, w in ((222, 214, 42), (314, 210, 38)):  # heavy bags under the eyes
        wash(p, face, "ellipse", (ex - w * 0.5, ey + 8, ex + w * 0.5, ey + 26), hexc("#9a6a8a", 70), blur=4)
    bushy_brow(p, 244, 190, 186, 190, white, thick=22, arch=-6, droop=12)
    bushy_brow(p, 294, 184, 350, 186, white, thick=22, arch=-6, droop=12)
    blush(p, face, 214, 256, 22, 12, 70)
    # yawning mouth under a droopy walrus moustache
    open_mouth(p, face, skin, [(262, 284), (286, 278), (306, 286), (304, 316), (284, 328), (264, 318)], teeth=False,
               lower_lip=False)
    moust = [([(284, 250), (254, 258), (230, 282), (218, 318)], 42, 34),
             ([(290, 250), (318, 258), (336, 282), (344, 316)], 40, 32),
             ([(286, 252), (270, 272), (262, 296)], 30, 26)]
    hair_mass(p, moust, white, shadow=0.62, light=1.25, depth=0.25, sheen_alpha=140, gap_alpha=170,
              line_c=white_ink)
    ball_nose(p, 290, 236, 28, 24, hexc("#e8786a"))

    # ---- floppy nightcap: a rolled band, the crown, and a long tail flopping over with a pom-pom
    capm = closed([(160, 160), (170, 108), (210, 70), (262, 56), (322, 64), (372, 90), (410, 128), (430, 170),
                   (436, 214), (420, 224), (400, 176), (370, 150), (356, 160)], 8)
    cm = p.shape("poly", capm, cap, shadow=0.64, light=1.3, depth=0.14, tex="cloth", tex_amt=0.9)
    for pts in ([(262, 64), (300, 110), (320, 150)], [(360, 90), (380, 130), (396, 170)], [(220, 80), (230, 130)]):
        fold(p, cm, pts, shade(cap, 0.5), 10, 4, light_tone(cap, 1.4))
    band = closed([(150, 172), (160, 140), (256, 124), (352, 138), (370, 168), (360, 186), (256, 170), (158, 190)], 6)
    bm = p.shape("poly", band, shade(cap, 1.2), shadow=0.66, light=1.25, depth=0.3, tex="cloth", tex_amt=0.9)
    p.shadow_on(bm, 0.35, 5, 5)
    for x in range(176, 360, 16):
        line(p, [(x, 150 - (x - 256) ** 2 / 1600 + 2), (x + 3, 172 - (x - 256) ** 2 / 1800)],
             shade(cap, 0.8)[:3] + (150,), 2.2, bm)
    p.shape("ellipse", (404, 204, 456, 256), white, shadow=0.7, light=1.2, depth=0.25, tex="fur", tex_amt=1.0)
    zzz(p, 60, 110, 1.3)
    zzz(p, 100, 64, 1.0)
    zzz(p, 132, 30, 0.75)

    # ---- lantern held up in the near hand
    sl = p.shape("poly", closed([(10, 512), (18, 440), (54, 380), (96, 350), (150, 360), (158, 440), (160, 512)], 6),
                 cloak, shadow=0.68, light=1.2, depth=0.16, tex="cloth", tex_amt=0.9)
    fold(p, sl, [(60, 420), (80, 470), (74, 512)], shade(cloak, 0.55), 8, 3)
    stitch_line(p, [(70, 360), (140, 380)], hexc("#efe2c4", 200))
    lantern(p, 100, 180, 1.1)
    hm = hand_grip(p, 104, 336, 60, 70, skin, angle=-4)
    light_from(p, union(p, hm, sl), (100, 270), 120, hexc("#ffb040"), 80)
    # warm lantern light on the face
    wash(p, face, "ellipse", (140, 190, 250, 320), hexc("#ffb050", 70), blur=20)
    return p.finish()


def braid(p, top, bottom, w0, w1, color, ink=None, tie=None):
    """A thick braid: alternating overlapping lobes from `top` down to `bottom`, narrowing, with an
    optional tie near the end and a tuft below it."""
    (x0, y0), (x1, y1) = top, bottom
    n = 7
    for i in range(n):
        t = i / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        w = w0 + (w1 - w0) * t
        side = -1 if i % 2 == 0 else 1
        seg = (y1 - y0) / n
        lobe = closed([(x - side * w * 0.52, y - seg * 0.1), (x + side * w * 0.1, y - seg * 0.2),
                       (x + side * w * 0.5, y + seg * 0.5), (x + side * w * 0.2, y + seg * 1.2),
                       (x - side * w * 0.4, y + seg * 0.9)], 6)
        m = p.shape("poly", lobe, color if side < 0 else shade(color, 0.92), shadow=0.62, light=1.3, depth=0.3,
                    line=LW * 0.9, ink=ink or INK, rim=0.3, ao=0.4)
        tline(p, curve([(x - side * w * 0.3, y + seg * 0.1), (x + side * w * 0.05, y + seg * 0.5),
                        (x + side * w * 0.1, y + seg * 0.95)], 6), shade(color, 0.55)[:3] + (150,), 2.0, 0.8, clip=m)
        sheen(p, m, [(x - side * w * 0.2, y), (x + side * w * 0.15, y + seg * 0.5)], 4, 150)
    if tie:
        p.shape("rect", (x1 - w1 * 0.55, y1 - 4, x1 + w1 * 0.55, y1 + 14), tie, radius=4, shadow=0.6, light=1.4,
                depth=0.35, spec=0.5)
        hair_mass(p, [([(x1 - 6, y1 + 12), (x1 - 12, y1 + 40)], w1 * 0.7, w1 * 0.6),
                      ([(x1 + 6, y1 + 12), (x1 + 10, y1 + 40)], w1 * 0.7, w1 * 0.6)], color, sheen_alpha=100,
                  line_c=ink)


def class_master():
    """Yaşlı Kaan, the old weapons master: grey hair in a topknot, a leather eyepatch with a scar running
    through it, a kind crinkled eye under a bushy brow, a long braided beard, a red wrap-over coat with a
    leather baldric and a steel pauldron, a crystal staff and a sword on his back, and a hand raised in
    greeting."""
    p = NPainter()
    skin = hexc("#d99c74")
    grey = hexc("#d4cfca")
    grey_ink = hexc("#5e5866")
    gi = hexc("#8a2e2a")
    strap = hexc("#5a3620")
    steel = hexc("#aeb8c4")
    crystal = hexc("#5ad0ff")

    # ---- weapons on his back: the crystal staff (left) and the sword hilt (right)
    p.shape("poly", taper([(160, 512), (40, 60)], 20, 18, 2), hexc("#9a6a3a"), shadow=0.64, light=1.3,
            depth=0.35, tex="wood", tex_amt=0.9, rim=0)
    for t in (0.35, 0.45):
        x, y = lerp((160, 512), (40, 60), t)
        p.shape("poly", taper([(x - 14, y + 4), (x + 14, y - 4)], 12, 12, 2), strap, depth=0.4, line=LW * 0.8,
                rim=0, tex="leather", tex_amt=0.6)
    p.glow((34, 34), 70, crystal, 0.6)
    p.shape("poly", closed([(24, 58), (54, 64), (58, 80), (22, 76)], 2), GOLD, shadow=0.6, light=1.5, depth=0.35,
            spec=0.9)
    for dx in (-14, 14):
        p.shape("poly", taper([(38 + dx * 0.4, 64), (38 + dx, 40), (38 + dx * 0.8, 22)], 8, 4, 4), GOLD, shadow=0.6,
                light=1.5, depth=0.4, line=LW * 0.8, spec=0.8, rim=0)
    p.shape("poly", [(38, 0), (54, 30), (38, 62), (22, 30)], crystal, shadow=0.55, light=1.6, depth=0.3,
            ink=hexc("#1a4a7a"), gloss=0.9, rim=0)
    p.flat("poly", [(38, 4), (46, 30), (38, 50)], hexc("#e0f8ff", 170))
    p.sparkle((52, 14), 10)
    # sword: crossguard and wrapped grip over the far shoulder
    p.shape("poly", taper([(404, 206), (446, 78)], 18, 16, 2), hexc("#3a2418"), shadow=0.66, light=1.3,
            depth=0.35, tex="leather", tex_amt=0.8, rim=0)
    for t in (0.15, 0.32, 0.49, 0.66, 0.83):
        x, y = lerp((404, 206), (446, 78), t)
        tline(p, [(x - 9, y - 2), (x + 9, y + 5)], hexc("#a07850", 220), 2.4, 2.4)
    p.shape("ellipse", (434, 52, 464, 82), GOLD, shadow=0.55, light=1.6, depth=0.35, spec=1.0)
    p.shape("poly", taper(curve([(356, 180), (372, 198), (402, 212), (434, 222), (452, 238)], 6), 12, 14, 1), GOLD,
            shadow=0.55, light=1.6, depth=0.35, spec=1.0)
    p.shape("ellipse", (390, 196, 416, 222), GOLD, shadow=0.55, light=1.6, depth=0.35, spec=1.0)
    gem(p, 403, 209, 6, hexc("#d03a3a"))

    # ---- body: red wrap-over coat, cream under-collar, pauldron and baldric
    torso = closed([(180, 300), (340, 300), (430, 330), (492, 390), (512, 512), (0, 512), (18, 390), (82, 330)], 8)
    body = p.shape("poly", torso, gi, shadow=0.68, light=1.25, depth=0.1, tex="cloth", tex_amt=0.8)
    fold(p, body, [(440, 400), (430, 470), (436, 512)], shade(gi, 0.55), 10, 4, light_tone(gi, 1.3))
    fold(p, body, [(320, 430), (330, 512)], shade(gi, 0.55), 10, 4, light_tone(gi, 1.3))
    p.shape("poly", closed([(206, 318), (236, 318), (290, 430), (320, 512), (270, 512), (240, 440)], 3),
            hexc("#ece0cc"), shadow=0.72, light=1.15, depth=0.3, tex="cloth", tex_amt=0.5)
    p.shape("poly", closed([(314, 318), (284, 318), (250, 400), (236, 440), (256, 460), (280, 400)], 3),
            hexc("#ece0cc"), shadow=0.72, light=1.15, depth=0.3, tex="cloth", tex_amt=0.5)
    bd = p.shape("poly", taper([(360, 330), (260, 440), (190, 512)], 42, 44, 6), strap, shadow=0.64, light=1.3,
                 depth=0.25, tex="leather", tex_amt=0.9, spec=0.3, clip=body)
    stitch_line(p, [(348, 322), (248, 432), (178, 506)], hexc("#d8b890", 190), clip=bd)
    stitch_line(p, [(372, 340), (272, 450), (202, 518)], hexc("#d8b890", 190), clip=bd)
    p.shape("rect", (264, 404, 304, 444), GOLD, radius=6, shadow=0.55, light=1.6, depth=0.3, spec=1.0)
    p.shape("rect", (274, 414, 294, 434), strap, radius=3, **NOLINE)
    # steel pauldron on the near shoulder: a domed cap over two curved lames
    edge = [(26, 424), (64, 400), (116, 390), (166, 396), (200, 414)]
    for k, dy in ((2, 58), (1, 30)):
        up = [(x + (k * 4 if x < 100 else -k * 6), y + dy) for x, y in edge]
        lo = [(x, y + 34) for x, y in up]
        m = p.shape("poly", closed(up + lo[::-1], 4), shade(steel, 0.9 - k * 0.04), shadow=0.55, light=1.45,
                    depth=0.25, tex="metal", tex_amt=0.8, spec=0.8, ink=hexc("#232833"))
        sheen(p, m, [(up[1][0], up[1][1] + 8), (up[3][0], up[3][1] + 8)], 5, 150)
    dome = p.shape("poly", closed([(20, 430), (34, 376), (80, 340), (140, 330), (190, 346), (206, 396)] +
                                  [(166, 404), (116, 398), (64, 408)], 6), steel, shadow=0.55, light=1.45,
                   depth=0.18, tex="metal", tex_amt=0.8, spec=1.0, ink=hexc("#232833"))
    sheen(p, dome, [(50, 380), (90, 350), (140, 342)], 8, 190)
    tline(p, curve([(30, 418), (64, 400), (116, 390), (166, 396), (198, 392)], 6), GOLD, 5, 5, clip=dome)
    for x, y in ((56, 392), (110, 364), (168, 376)):
        p.shape("ellipse", (x - 6, y - 6, x + 6, y + 6), GOLD, shadow=0.55, light=1.6, depth=0.4, line=LW * 0.6,
                rim=0, ao=0.3)

    # ---- head
    cx, cy = 256, 210
    head = [(160, 184), (170, 126), (210, 88), (262, 80), (318, 90), (354, 128), (364, 186), (360, 244),
            (342, 290), (300, 324), (252, 332), (206, 316), (174, 276)]
    face = head_shape(p, head, skin)
    skin_shade(p, face, skin, cx, cy, 204, 250)
    ear(p, 166, 214, 36, 56, skin, -1)
    for y in (146, 158):
        tline(p, curve([(246, y + 4), (280, y), (318, y + 4)], 6), shade(skin, 0.6)[:3] + (150,), 1.2, 2.2,
              clip=face)
    # grey hair swept back into a topknot
    hair_mass(p, [
        ([(330, 120), (290, 96), (240, 92), (196, 110)], 44, 40, 20),
        ([(350, 150), (330, 100), (280, 80), (222, 84)], 40, 36, 18),
        ([(300, 120), (250, 108), (200, 128), (176, 160)], 34, 30, 16),
        ([(260, 88), (220, 84), (184, 110), (168, 150)], 34, 30, 14),
    ], grey, shadow=0.62, light=1.25, depth=0.2, sheen_alpha=130, line_c=grey_ink, sheen_t=(0.2, 0.6))
    p.shape("ellipse", (182, 40, 244, 96), grey, shadow=0.62, light=1.25, depth=0.25, ink=grey_ink)
    tline(p, curve([(192, 60), (212, 50), (236, 60)], 6), grey_ink[:3] + (170,), 2.5, 0.8)
    p.shape("rect", (196, 82, 234, 98), hexc("#b02a2a"), radius=4, shadow=0.6, light=1.4, depth=0.35, spec=0.4)

    # ---- the far eye: kind and crinkled
    eye(p, 312, 206, 38, 30, hexc("#8a6a3a"), skin, side=1, look=(0.14, 0.04), lid=0.3, lash=5.5, lower=0.9,
        bags=True, flick=0.2)
    for i in range(3):  # crow's feet
        tline(p, [(338, 202 + i * 8), (352, 196 + i * 10)], shade(skin, 0.55)[:3] + (170,), 1.8, 0.8, clip=face)
    bushy_brow(p, 292, 182, 350, 180, grey, thick=22, arch=-8, droop=10)
    # eyepatch with its strap, and the scar through it
    tline(p, curve([(196, 186), (250, 150), (320, 118), (352, 116)], 6), hexc("#2a1a14"), 6, 5)
    tline(p, [(160, 214), (200, 208)], hexc("#2a1a14"), 6, 6)
    patch = closed([(196, 196), (224, 184), (250, 194), (252, 222), (230, 238), (202, 226)], 6)
    pm = p.shape("poly", patch, hexc("#3a2418"), shadow=0.6, light=1.4, depth=0.3, tex="leather", tex_amt=0.8,
                 spec=0.4, ink=hexc("#140a08"))
    stitch_line(p, [(204, 200), (224, 192), (244, 199), (245, 218), (229, 230), (207, 222), (204, 200)],
                hexc("#a07850", 220), step=8, length=4, width=1.8, clip=pm)
    for a, b in (((212, 150), (220, 184)), ((236, 238), (246, 272))):
        tline(p, [a, b], hexc("#b8645a"), 5, 3)
        tline(p, [(a[0] + 1, a[1]), (b[0] + 1, b[1])], hexc("#f0a090", 150), 1.4, 1)
    for x, y in ((210, 164), (240, 254)):
        tline(p, [(x - 6, y + 3), (x + 6, y - 3)], hexc("#7a3a30"), 1.6, 1.6)
    bushy_brow(p, 246, 172, 190, 170, grey, thick=20, arch=-8, droop=6)
    nose_34(p, face, skin, (288, 206), (294, 246), 14, side=1)
    blush(p, face, 330, 246, 18, 12, 80)

    # ---- beard: grey mass from the cheeks down into a long braid, and a gentle smile under the moustache
    hair_mass(p, [
        ([(184, 238), (186, 286), (210, 334), (240, 360)], 36, 26),
        ([(350, 210), (346, 280), (318, 334), (284, 360)], 40, 30),
        ([(214, 290), (230, 344), (262, 372)], 44, 36),
        ([(310, 286), (296, 344), (266, 372)], 44, 36),
        ([(262, 300), (262, 350), (262, 380)], 60, 60),
    ], grey, shadow=0.62, light=1.25, depth=0.14, sheen_alpha=110, line_c=grey_ink)
    open_mouth(p, face, skin, [(252, 282), (280, 290), (312, 278), (304, 296), (282, 306), (262, 298)], tongue=False,
               teeth_h=0.45, lower_lip=False)
    braid(p, (262, 372), (262, 500), 56, 36, grey, ink=grey_ink, tie=hexc("#b02a2a"))
    hair_mass(p, [([(284, 262), (254, 268), (230, 286), (218, 318)], 32, 28),
                  ([(292, 262), (316, 268), (334, 286), (340, 312)], 30, 26)], shade(grey, 1.05), shadow=0.62,
              light=1.3, depth=0.25, sheen_alpha=150, line_c=grey_ink)

    # ---- the far hand raised in greeting, knuckles bandaged
    fa = p.shape("poly", closed([(372, 512), (384, 440), (410, 380), (452, 372), (470, 430), (480, 512)], 6), gi,
                 shadow=0.68, light=1.25, depth=0.16, tex="cloth", tex_amt=0.8)
    fold(p, fa, [(400, 430), (420, 480), (414, 512)], shade(gi, 0.55), 8, 3)
    p.shape("poly", closed(capsule(398, 360, 478, 392), 1), hexc("#ece0cc"), shadow=0.72, light=1.15, depth=0.3,
            tex="cloth", tex_amt=0.5)
    open_hand(p, 440, 322, 66, skin, angle=6, curl=0.0, spread=1.0, back=False)
    for y in (300, 312):
        tline(p, [(412, y), (470, y - 4)], hexc("#efe6d6", 235), 7, 7)
    return p.finish()


# ------------------------------------------------------------------ main

NPCS = {
    "nara": nara,
    "smith": smith,
    "merchant": merchant,
    "innkeeper": innkeeper,
    "keeper": keeper,
    "class_master": class_master,
}


def main(names=None):
    names = names or list(NPCS)
    out_dir = os.path.join(ROOT, "assets", "town")
    for n in names:
        img = NPCS[n]()
        path = os.path.join(out_dir, "npc_%s.png" % n)
        img.save(path)
        print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main(sys.argv[1:] or None)

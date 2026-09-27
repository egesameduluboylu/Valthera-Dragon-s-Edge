"""Player hero sprites, drawn at 512 x 512 (they are shown at ~270 logical px, so 256 was too soft).

    python3 tools/art/heroes.py

writes assets/sprites/player/{warrior,mage,rogue}.png. The heroes face right, toward the enemies,
in a heroic-chibi build (head about a third of the height) and a ready-for-battle stance: weight on
the front leg, a slight three-quarter turn, tapered limbs and hands that actually grip their weapons.

Same soft Painter look as the rest of the game (cel gradients, rim light, contact shadows,
tinted ink, light from the top left), with a few extras for the bigger canvas: tapered tubes for
limbs, metal with a painted sheen and a reflected rim light, soft cloth folds, and faces with
almond eyes, catchlights and determined brows.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

from characters import DARK, NOLINE, SKIN, WHITE, along, curve, flame, star_pts  # noqa: E402
from painter import SS, Painter, _blur, _erode, _shift, hexc, light_tone, mix, shade  # noqa: E402
from painter import shadow_tone as shadow_tone_  # noqa: E402

SIZE = 512
LINE = 2.6      # ink weight of the main shapes (final pixels)
FINE = 1.7      # ink weight of small details
OUTLINE = 4     # silhouette outline added by finish()


# ------------------------------------------------------------------ painter tuned for 512 px

class HeroPainter(Painter):
    """Soft painter whose default ink is weighted for a 512 px sprite. Each hero is designed on a 512 grid;
    `k`, `dx` and `dy` then fit the design to the frame (scale about the ground point (256, 484), then shift)
    without redrawing it. Ink weights and blur radii stay in final pixels."""

    def __init__(self, size=SIZE, k=1.0, dx=0.0, dy=0.0):
        super().__init__(size, size, soft=True)
        self.k, self.dx, self.dy = k, dx, dy
        self.rot = None  # (pivot x, pivot y, degrees): tilts a part of the design, e.g. the head

    def tilt(self, pivot=None, angle=0.0):
        """Rotates everything drawn from now on about `pivot` (clockwise on screen); tilt() turns it off."""
        self.rot = (pivot[0], pivot[1], math.radians(angle)) if pivot and angle else None

    def pt(self, x, y):
        if self.rot:
            cx, cy, a = self.rot
            ca, sa = math.cos(a), math.sin(a)
            x, y = cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca
        return (256 + (x - 256) * self.k + self.dx, 484 + (y - 484) * self.k + self.dy)

    def _s(self, points):
        if isinstance(points[0], (tuple, list)):
            return [(a * SS, b * SS) for a, b in (self.pt(x, y) for x, y in points)]
        out = []
        for i in range(0, len(points), 2):
            a, b = self.pt(points[i], points[i + 1])
            out += [a * SS, b * SS]
        return out

    def _mask(self, kind, pts, **kw):
        kw = dict(kw)
        for key in ("width", "radius"):
            if key in kw:
                kw[key] = kw[key] * self.k
        return super()._mask(kind, pts, **kw)

    def glow(self, center, radius, color, strength=0.8):
        return super().glow(self.pt(*center), radius * self.k, color, strength)

    def ground_box(self, cx, w, y=482, h=30):
        x0, y0 = self.pt(cx - w / 2, y - h / 2)
        x1, y1 = self.pt(cx + w / 2, y + h / 2)
        return (x0, y0, x1, y1)

    def shape(self, kind, pts, color, shadow=0.72, light=1.22, depth=0.14, line=LINE, **kw):
        return super().shape(kind, pts, color, shadow=shadow, light=light, depth=depth, line=line, **kw)

    def paint_mask(self, m, color, shadow=0.72, light=1.22, depth=0.14, line=LINE, **kw):
        return super().paint_mask(m, color, shadow=shadow, light=light, depth=depth, line=line, **kw)


# ------------------------------------------------------------------ geometry helpers

def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def tube_pts(pts, widths, steps=8):
    """Outline of a smooth curve through `pts` whose width follows `widths` (one per control point)."""
    c = curve(pts, steps) if len(pts) > 2 else [lerp(pts[0], pts[1], i / steps) for i in range(steps + 1)]
    n = len(c)
    segs = max(1, len(pts) - 1)
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a, b = c[max(0, i - 1)], c[min(n - 1, i + 1)]
        ux, uy = unit(a, b)
        f = i / max(1, n - 1) * segs
        k = min(segs - 1, int(f))
        w = widths[k] + (widths[k + 1] - widths[k]) * (f - k)
        left.append((x - uy * w / 2, y + ux * w / 2))
        right.append((x + uy * w / 2, y - ux * w / 2))
    return left + right[::-1]


def tube_mask(p, pts, widths, caps=True, steps=8):
    """Mask of a tapered limb with round ends."""
    items = [("poly", tube_pts(pts, widths, steps))]
    if caps:
        for (x, y), w in ((pts[0], widths[0]), (pts[-1], widths[-1])):
            items.append(("ellipse", (x - w / 2, y - w / 2, x + w / 2, y + w / 2)))
    return p.union(items)


def rot_pts(pts, center, angle):
    """Rotates points about `center` by `angle` degrees (clockwise on screen for positive angles)."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = center
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def ellipse_pts(cx, cy, rx, ry, n=48, a0=0, a1=360):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


# ------------------------------------------------------------------ painting helpers

def soft(p, pts, color, width, blur, clip=None):
    """Blurred stroke, optionally kept inside `clip` (folds, sheens, painted shading)."""
    m = p._mask("line", pts, width=width)
    m = m.filter(ImageFilter.GaussianBlur(max(0.5, blur * SS)))
    if clip is not None:
        m = ImageChops.multiply(m, clip)
    p._fill(m, color, solid=False)


def fold(p, pts, clip, color, width=5.0, blur=2.2, lit=None):
    """Cloth fold: a soft shadow valley with a thin lit ridge just above-left of it."""
    pts = curve(pts, 6) if len(pts) > 2 else pts
    soft(p, pts, shade(color, 0.55)[:3] + (150,), width, blur, clip)
    if lit is not False:
        lit = lit or light_tone(color, 1.35)[:3] + (90,)
        soft(p, [(x - width * 0.55, y - width * 0.35) for x, y in pts], lit, width * 0.5, blur * 0.8, clip)


def _dilate_mask(m, r):
    return m.filter(ImageFilter.MaxFilter(int(r * SS) * 2 + 1))


def edge_light(p, mask, color, dx=1, dy=1, width=4.0, blur=1.6, inset=2.2):
    """Soft band of light along the mask's edge that faces (dx, dy): a reflected rim light."""
    inner = _erode(mask, int(inset * SS))
    o = int(width * SS)
    band = ImageChops.subtract(inner, _shift(inner, int(-dx * o), int(-dy * o)))
    band = ImageChops.multiply(_blur(band, blur * SS), inner)
    p._fill(band, color, solid=False)


def sheen(p, mask, pts, color=hexc("#ffffff", 200), width=6.0, blur=1.8):
    """Painted specular streak on polished metal, clipped to the surface."""
    soft(p, curve(pts, 6) if len(pts) > 2 else pts, color, width, blur, _erode(mask, int(2.4 * SS)))


def metal(p, mask, color, reflect=hexc("#ffd7b0", 150), sheen_pts=None, sheen_w=6.0, spec=1.0, depth=0.16,
          tex_amt=0.45, line=LINE, horizon=1.0, **kw):
    """Polished plate: soft shading, metal texture, a glint, a painted sheen and a warm reflected rim."""
    p.paint_mask(mask, color, depth=depth, light=1.38, spec=spec, tex="metal", tex_amt=tex_amt, line=line, **kw)
    if horizon:
        # a darker soft band of reflected ground below the middle: what makes plate read as polished
        bb = mask.getbbox()
        if bb:
            x0, y0, x1, y1 = bb
            hgt = y1 - y0
            band = Image.new("L", mask.size, 0)
            ImageDraw.Draw(band).rectangle((x0, y0 + hgt * 0.56, x1, y0 + hgt * 0.74), fill=255)
            band = ImageChops.multiply(_blur(band, hgt * 0.07 + SS), _erode(mask, int(1.5 * SS)))
            p._fill(band, shadow_tone_(color, 0.62)[:3] + (int(120 * horizon),), solid=False)
    if reflect:
        edge_light(p, mask, reflect, 1, 1, width=3.6, blur=1.4)
    if sheen_pts:
        sheen(p, mask, sheen_pts, width=sheen_w)
    return mask


def spill(p, center, radius, color, strength=0.35):
    """Coloured light from a glowing object falling on the parts of the hero already painted around it."""
    cx, cy = p.pt(*center)
    r = radius * p.k * SS
    x0, y0 = int(cx * SS - r), int(cy * SS - r)
    size = int(r * 2)
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    for i in range(12, 0, -1):
        t = i / 12
        d.ellipse((r - r * t, r - r * t, r + r * t, r + r * t), fill=int(255 * strength * (1 - t) ** 1.3))
    m = m.filter(ImageFilter.GaussianBlur(r / 10))
    full = Image.new("L", p.img.size, 0)
    full.paste(m, (x0, y0))
    full = ImageChops.multiply(full, ImageChops.darker(p.solid, p.img.getchannel("A")))
    p._fill(full, color[:3] + (255,), solid=False)


def mote(p, x, y, r, color, core=hexc("#ffffff")):
    """Floating spark: a glow and a bright core, no outline."""
    p.glow((x, y), r * 4, color, 0.75)
    p._fill(p._mask("ellipse", (x - r, y - r, x + r, y + r)), mix(core, color, 0.25), solid=False)


def hero_rim(p, color=hexc("#fff0d8"), strength=150, width=3.2, fade=(330, 492, 80)):
    """Finishing light for a hero: the legs fall off gently into a cool shade toward the ground (keeping the
    eye on the face), and a thin back light runs along the right-facing silhouette edges, which lifts the
    figure off any background (the key light stays top left)."""
    sil = ImageChops.darker(p.solid, p.img.getchannel("A")).point(lambda v: 255 if v > 120 else 0)
    if fade:
        y0, y1, amt = fade
        t0, t1 = int(p.pt(0, y0)[1] * SS), int(p.pt(0, y1)[1] * SS)
        g = Image.new("L", p.img.size, 0)
        g.paste(Image.linear_gradient("L").resize((p.img.size[0], max(1, t1 - t0))).point(lambda v: v * amt // 255),
                (0, t0))
        g.paste(Image.new("L", (p.img.size[0], max(0, p.img.size[1] - t1)), amt), (0, t1))
        p._fill(ImageChops.multiply(g, sil), hexc("#2a1e4a"), solid=False)
    edge_light(p, sil, color[:3] + (strength,), dx=1, dy=-0.25, width=width, blur=1.2, inset=2.6)


def rivet(p, x, y, r=3.4, color=hexc("#e2e8ee")):
    p.shape("ellipse", (x - r, y - r, x + r, y + r), color, line=1.1, depth=0.45, light=1.6, rim=0, ao=0.5)
    p.flat("ellipse", (x - r * 0.55, y - r * 0.55, x - r * 0.05, y - r * 0.05), hexc("#ffffff", 220))


def stitch_line(p, pts, color, step=8.0, length=4.0, width=1.6):
    pts = curve(pts, 6) if len(pts) > 2 else pts
    total = []
    acc = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        t = acc
        while t < seg:
            total.append(((x0 + (x1 - x0) * t / seg, y0 + (y1 - y0) * t / seg), unit((x0, y0), (x1, y1))))
            t += step
        acc = t - seg
    for (x, y), (ux, uy) in total:
        p.stroke([(x, y), (x + ux * length, y + uy * length)], color, width)


def gem(p, cx, cy, r, color, line=1.6):
    p.glow((cx, cy), r * 2.2, color, 0.35)
    p.shape("ellipse", (cx - r, cy - r, cx + r, cy + r), color, depth=0.35, light=1.5, line=line, gloss=1.0, rim=0,
            ink=shade(color, 0.3))
    p.flat("ellipse", (cx - r * 0.55, cy - r * 0.6, cx - r * 0.1, cy - r * 0.2), hexc("#ffffff", 235))


def hero_eye(p, cx, cy, rx, ry, iris, look=0.3, inner=1, tilt=0.42, lash=3.2, skin=SKIN):
    """Determined almond eye: the lid cuts down toward the inner corner (inner = +1 when the nose is to the
    right). Big glossy iris, pupil, two catchlights, a heavy lid line with a flick at the outer corner."""
    white = p._mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    outer_x, inner_x = cx - inner * (rx + 2), cx + inner * (rx + 2)
    top_o, top_i = cy - ry * 0.98, cy - ry * (1 - tilt)
    cut = p._mask("poly", [(outer_x, top_o), (inner_x, top_i), (inner_x, cy + ry + 4), (outer_x, cy + ry + 4)])
    white = ImageChops.multiply(white, cut)
    p.paint_mask(white, hexc("#fbf8f2"), shadow=0.84, light=0, depth=0.3, line=1.3, rim=0, ao=0)
    ix, iy = cx + inner * rx * look, cy + ry * 0.12
    irx, iry = rx * 0.64, ry * 0.8
    p.shape("ellipse", (ix - irx, iy - iry, ix + irx, iy + iry), iris, shadow=0.5, light=1.3, depth=0.3, line=1.1,
            ink=shade(iris, 0.3), rim=0, ao=0, clip=white)
    p.shape("chord", (ix - irx * 0.78, iy - iry * 0.2, ix + irx * 0.78, iy + iry * 0.9), light_tone(iris, 1.5),
            start=0, end=180, clip=white, **NOLINE)
    pr = irx * 0.46
    p.shape("ellipse", (ix - pr, iy - pr * 1.2, ix + pr, iy + pr * 1.2), DARK, clip=white, **NOLINE)
    # lid shadow across the top of the eyeball
    lid = p._mask("line", [(outer_x, top_o), (inner_x, top_i)], width=ry * 0.5)
    p.shadow_on(lid, strength=0.35, offset=1.5, blur=2.5)
    p.flat("ellipse", (ix - irx * 0.75, iy - iry * 0.72, ix - irx * 0.05, iy - iry * 0.1), WHITE)
    p.flat("ellipse", (ix + irx * 0.18, iy + iry * 0.3, ix + irx * 0.5, iy + iry * 0.6), hexc("#ffffff", 210))
    # heavy upper lid with an outer flick, a light lower lid
    p.stroke([(outer_x - inner * 1, top_o + 1.5), lerp((outer_x, top_o), (inner_x, top_i), 0.5),
              (inner_x, top_i + 1)], DARK, lash)
    p.stroke([(outer_x, top_o + 1.5), (outer_x - inner * lash * 2.2, top_o - lash * 0.9)], DARK, lash * 0.85)
    p.stroke(curve([(cx - rx * 0.6, cy + ry * 0.98), (cx, cy + ry * 1.06), (cx + rx * 0.6, cy + ry * 0.96)], 4),
             shade(skin, 0.62)[:3] + (180,), 1.5)
    return white


def face_mask(p, box, chin=1.0):
    """Round chibi face with a small chin pushed toward the lower right (three-quarter view facing right)."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = x0 + w * 0.64, y0 + h * 0.84
    return p.union([("ellipse", box),
                    ("ellipse", (cx - w * 0.22 * chin, cy - h * 0.16 * chin, cx + w * 0.2 * chin,
                                 cy + h * 0.15 * chin))])


def brow(p, a, b, color, w0=6.0, w1=3.0):
    """Tapered brow from a (thick, inner end) to b (thin, outer end)."""
    p.shape("poly", tube_pts([a, lerp(a, b, 0.5), b], [w0, (w0 + w1) / 2 * 1.05, w1], 4), color, line=0, depth=0.3,
            light=1.2, rim=0, ao=0)


def fist(p, c, u, color, size=17.0, line=LINE, tex=None, side=1, thumb=True, crease=None):
    """A hand wrapped around a grip that runs along unit vector u through c. One rounded mitten shape with
    knuckle bumps along the curled fingers and creases between them, and the thumb lying over the grip.
    `side` flips which side of the grip the fingers curl toward."""
    ux, uy = u
    nx, ny = -uy * side, ux * side
    cx, cy = c
    L, W = size, size * 0.9
    bx, by = cx + nx * W * 0.25, cy + ny * W * 0.25
    items = [("poly", tube_pts([(bx - ux * L * 0.62, by - uy * L * 0.62), (bx + ux * L * 0.62, by + uy * L * 0.62)],
                               [W * 1.75, W * 1.75], 2)),
             ("ellipse", (bx - ux * L * 0.62 - W * 0.875, by - uy * L * 0.62 - W * 0.875,
                          bx - ux * L * 0.62 + W * 0.875, by - uy * L * 0.62 + W * 0.875)),
             ("ellipse", (bx + ux * L * 0.62 - W * 0.875, by + uy * L * 0.62 - W * 0.875,
                          bx + ux * L * 0.62 + W * 0.875, by + uy * L * 0.62 + W * 0.875))]
    knuckles = []
    for t in (-0.72, -0.24, 0.24, 0.72):
        kx, ky = bx + ux * L * t + nx * W * 0.62, by + uy * L * t + ny * W * 0.62
        r = L * 0.3
        knuckles.append((kx, ky))
        items.append(("ellipse", (kx - r, ky - r, kx + r, ky + r)))
    m = p.union(items)
    p.paint_mask(m, color, depth=0.28, light=1.3, line=line, rim=0.4, tex=tex, tex_amt=0.5)
    k = crease or shade(color, 0.55)[:3] + (220,)
    for t in (-0.48, 0.0, 0.48):
        x0, y0 = bx + ux * L * t + nx * W * 0.95, by + uy * L * t + ny * W * 0.95
        p.stroke([(x0, y0), (x0 - nx * W * 0.62, y0 - ny * W * 0.62)], k, 1.8)
    # soft shade under the finger row, light on the knuckles
    soft(p, [(bx - ux * L * 0.7 + nx * W * 0.1, by - uy * L * 0.7 + ny * W * 0.1),
             (bx + ux * L * 0.7 + nx * W * 0.1, by + uy * L * 0.7 + ny * W * 0.1)], shade(color, 0.7)[:3] + (90,),
         W * 0.35, 1.5, _erode(m, SS * 2))
    if thumb:
        tx, ty = cx - nx * W * 0.45, cy - ny * W * 0.45
        a = (tx - ux * L * 0.55, ty - uy * L * 0.55)
        b = (tx + ux * L * 0.5 + nx * W * 0.25, ty + uy * L * 0.5 + ny * W * 0.25)
        tm = p.union([("poly", tube_pts([a, b], [W * 0.72, W * 0.6], 2)),
                      ("ellipse", (b[0] - W * 0.3, b[1] - W * 0.3, b[0] + W * 0.3, b[1] + W * 0.3))])
        p.paint_mask(tm, shade(color, 1.04), depth=0.35, light=1.35, line=1.8, rim=0, ao=0.45, tex=tex, tex_amt=0.4)
    return m


def blade(p, base, tip, width, color=hexc("#dfe7ef"), fuller=True, line=LINE):
    """Longsword blade: bevelled edges, a fuller, a bright edge and a glint near the tip."""
    ux, uy = unit(base, tip)
    nx, ny = -uy, ux
    hw = width / 2
    tl = width * 1.4
    x0, y0 = base
    x1, y1 = tip
    pts = [(x0 + nx * hw, y0 + ny * hw), (x1 - ux * tl + nx * hw * 0.92, y1 - uy * tl + ny * hw * 0.92), (x1, y1),
           (x1 - ux * tl - nx * hw * 0.92, y1 - uy * tl - ny * hw * 0.92), (x0 - nx * hw, y0 - ny * hw)]
    m = p._mask("poly", pts)
    # two bevel faces: the lit half and the shaded half
    p.paint_mask(m, color, depth=0.28, light=1.35, line=line, spec=1.0, tex="metal", tex_amt=0.35, rim=0.3)
    half = p._mask("poly", [(x0, y0), (x1, y1), (x1 - ux * tl - nx * hw, y1 - uy * tl - ny * hw),
                            (x0 - nx * hw * 1.2, y0 - ny * hw * 1.2)])
    side = 1 if (nx + ny) > 0 else -1  # which half faces away from the top-left light
    if side < 0:
        half = ImageChops.subtract(m, half)
    p._fill(ImageChops.multiply(_blur(half, SS * 0.8), _erode(m, SS * 2)), shade(color, 0.8)[:3] + (150,),
            solid=False)
    if fuller:
        a = (x0 + ux * 10, y0 + uy * 10)
        b = (x1 - ux * tl * 1.6, y1 - uy * tl * 1.6)
        p.stroke([a, b], shade(color, 0.66), width * 0.18)
        p.stroke([(a[0] - nx * width * 0.12, a[1] - ny * width * 0.12), (b[0] - nx * width * 0.12,
                                                                          b[1] - ny * width * 0.12)],
                 hexc("#ffffff", 150), width * 0.07)
    # bright cutting edge on the lit side
    e = -side
    p.stroke([(x0 + e * nx * hw * 0.78, y0 + e * ny * hw * 0.78),
              (x1 - ux * tl + e * nx * hw * 0.7, y1 - uy * tl + e * ny * hw * 0.7), (x1, y1)],
             hexc("#ffffff", 190), max(1.4, width * 0.09))
    return m, (ux, uy), (nx, ny)


# ------------------------------------------------------------------ warrior

def warrior():
    """Savaşçı: knight in silver plate with a red plume, red tabard with blue and gold, kite shield raised,
    longsword angled forward (faces right)."""
    p = HeroPainter(k=0.94, dx=-30, dy=0)
    steel = hexc("#c6d1dd")
    steel_d = hexc("#8995a8")
    red = hexc("#c8352d")
    red_d = hexc("#9a2327")
    blue = hexc("#2f5fb8")
    gold = hexc("#f2bd48")
    boot = hexc("#6a3e24")
    under = hexc("#3e4258")
    ink_red = hexc("#4a0e12")

    # ---- cape sweeping back behind the knight
    cape = curve([(236, 228), (196, 262), (150, 318), (118, 380), (92, 440), (112, 452), (132, 442), (156, 466),
                  (186, 450), (214, 466), (236, 444), (256, 380), (292, 240)], 7)
    cm = p._mask("poly", cape)
    p.paint_mask(cm, red_d, depth=0.1, tex="cloth", tex_amt=0.5, ink=ink_red)
    # the turned-back lining at the hem
    lin = p._mask("poly", curve([(92, 440), (104, 424), (124, 430), (132, 442), (112, 452)], 5))
    p.paint_mask(lin, blue, depth=0.25, rim=0, line=FINE)
    for pts in ([(222, 262), (170, 340), (128, 430)], [(240, 280), (196, 370), (160, 452)],
                [(252, 300), (228, 380), (214, 456)]):
        fold(p, pts, cm, red_d, width=8, blur=3.2)

    def armored_leg(hip, knee, ankle, toe_dir=1, heel=None):
        """Thigh in padded cloth, a steel knee cop, a greave and a leather boot with a steel toe cap."""
        thigh = tube_mask(p, [hip, lerp(hip, knee, 0.5), knee], [66, 58, 50])
        p.paint_mask(thigh, under, depth=0.2, tex="cloth", tex_amt=0.5)
        fold(p, [lerp(hip, knee, 0.25), lerp(hip, knee, 0.7)], thigh, under, width=6, blur=2)
        kx, ky = knee
        ax, ay = ankle
        greave = tube_mask(p, [(kx, ky + 6), lerp((kx, ky + 6), ankle, 0.5), ankle], [48, 46, 40])
        metal(p, greave, steel, sheen_pts=[(kx - 12, ky + 16), (ax - 12, ay - 8)], sheen_w=5)
        p.stroke([(kx + 2, ky + 20), lerp((kx + 2, ky + 20), (ax + 2, ay), 0.9)], shade(steel_d, 0.9), 2)
        # boot
        bx = ax - 30
        foot = p._mask("poly", curve([(bx, ay - 8), (ax + 8, ay - 16), (ax + 34, ay - 8), (ax + 58, ay + 8),
                                      (ax + 66, ay + 32), (bx - 4, ay + 34), (bx - 8, ay + 12)], 5))
        p.paint_mask(foot, boot, depth=0.22, tex="leather", tex_amt=0.8)
        toe = p._mask("poly", curve([(ax + 18, ay - 8), (ax + 40, ay - 4), (ax + 60, ay + 10), (ax + 66, ay + 32),
                                     (ax + 22, ay + 32), (ax + 14, ay + 10)], 5))
        metal(p, toe, shade(steel, 0.86), sheen_pts=[(ax + 28, ay + 2), (ax + 48, ay + 10)], sheen_w=4)
        p.shape("rect", (bx - 8, ay + 26, ax + 68, ay + 38), shade(boot, 0.5), radius=5, depth=0.3, rim=0)
        p.shape("poly", curve([(ax - 30, ay - 14), (ax + 26, ay - 18), (ax + 30, ay - 4), (ax - 30, ay)],
                              3) + [(ax - 30, ay - 14)], shade(boot, 1.15), depth=0.3, tex="leather", tex_amt=0.8)
        stitch_line(p, [(ax - 26, ay - 6), (ax + 26, ay - 10)], hexc("#c89a6a"), step=7, length=3.5, width=1.3)
        # knee cop with a fan wing
        cop = p._mask("poly", curve([(kx - 22, ky - 4), (kx - 4, ky - 20), (kx + 20, ky - 12), (kx + 24, ky + 6),
                                     (kx + 6, ky + 20), (kx - 16, ky + 14), (kx - 22, ky - 4)], 5))
        metal(p, cop, steel, sheen_pts=[(kx - 12, ky - 4), (kx - 2, ky - 13)], sheen_w=4)
        p.shape("poly", [(kx - 6, ky + 2), (kx + 2, ky - 14), (kx + 12, ky + 2), (kx + 2, ky + 8)],
                shade(steel, 0.9), depth=0.3, spec=0.8, line=FINE)
        rivet(p, kx + 2, ky + 2, 3.2)

    # ---- legs: the front (far) one bent and carrying the weight, the back one braced
    armored_leg((292, 330), (336, 384), (350, 448))
    armored_leg((232, 334), (208, 384), (182, 448))

    # ---- mail skirt at the hips
    mail = p._mask("poly", curve([(212, 300), (314, 298), (326, 350), (310, 376), (262, 370), (216, 378),
                                  (202, 350)], 5))
    p.paint_mask(mail, hexc("#8e99a8"), depth=0.14, tex="metal", tex_amt=0.5)
    for row, y in enumerate(range(306, 384, 7)):
        for x in range(200 + (row % 2) * 4, 330, 8):
            p.shape("chord", (x - 4.5, y - 4.5, x + 4.5, y + 4.5), hexc("#b3bdca"), start=0, end=180, line=0.9,
                    light=1.45, shadow=0.66, depth=0.4, rim=0, ao=0, clip=mail)
    edge_light(p, mail, hexc("#ffd7b0", 110), width=3)

    # ---- torso: padded gambeson, then the tabard (chest piece plus a front flap between the legs)
    torso = p._mask("poly", curve([(212, 236), (306, 232), (320, 270), (316, 316), (300, 332), (224, 334),
                                   (208, 312), (204, 270)], 5))
    p.paint_mask(torso, under, depth=0.16, tex="cloth", tex_amt=0.5)
    tab = p.union([("poly", curve([(218, 244), (304, 240), (312, 290), (316, 334), (262, 340), (210, 338),
                                   (210, 290)], 5)),
                   ("poly", curve([(240, 330), (300, 328), (304, 370), (298, 410), (272, 398), (246, 410),
                                   (238, 370)], 4))])
    p.paint_mask(tab, red, depth=0.12, tex="cloth", tex_amt=0.6, ink=ink_red)
    # blue border and gold trim around the flap
    flap_in = p._mask("poly", curve([(252, 334), (290, 332), (292, 370), (288, 392), (272, 384), (256, 392),
                                     (250, 370)], 4))
    border = ImageChops.multiply(ImageChops.subtract(tab, flap_in),
                                 p._mask("poly", [(200, 334), (330, 330), (330, 420), (200, 420)]))
    p.paint_mask(border, blue, depth=0.2, line=0, rim=0, tex="cloth", tex_amt=0.5, ao=0)
    p.stroke(curve([(252, 336), (252, 370), (256, 392), (272, 384), (288, 392), (292, 370), (290, 334)], 4),
             gold, 3.2)
    p.stroke(curve([(240, 372), (246, 410), (272, 398), (298, 410), (304, 372)], 4), gold, 4.5)
    fold(p, [(292, 262), (300, 300), (298, 328)], tab, red, width=7, blur=2.6)
    fold(p, [(270, 346), (272, 390)], tab, red, width=5, blur=1.8)
    p.shape("poly", star_pts(271, 364, 9, 0.45), gold, line=1.4, depth=0.3, light=1.45, rim=0, ao=0)
    # gold dragon-wing crest with a ruby
    crest = curve([(272, 256), (296, 262), (300, 276), (292, 294), (274, 312), (256, 294), (248, 276), (252, 262)], 3)
    cr = p.shape("poly", crest, gold, depth=0.25, light=1.45, spec=0.9, line=FINE)
    edge_light(p, cr, hexc("#fff3c0", 160), width=2.5)
    p.shape("poly", [(273, 266), (288, 272), (284, 288), (273, 300), (262, 288), (258, 272)], hexc("#d23a3a"),
            depth=0.35, light=1.5, line=1.3, gloss=1.0, rim=0)
    for s in (-1, 1):
        p.stroke(curve([(273 + s * 30, 262), (273 + s * 42, 256), (273 + s * 48, 268)], 3), gold, 3)
    # belt with a gold buckle and a pouch
    p.shape("poly", curve([(206, 318), (262, 312), (318, 308), (320, 326), (262, 330), (208, 336)], 4),
                   hexc("#5e3820"), depth=0.35, tex="leather", tex_amt=0.8)
    stitch_line(p, [(212, 322), (262, 317), (314, 313)], hexc("#c89a6a"), step=7, length=3.5, width=1.3)
    stitch_line(p, [(212, 332), (262, 327), (314, 322)], hexc("#c89a6a"), step=7, length=3.5, width=1.3)
    p.shape("rect", (274, 308, 300, 334), gold, radius=4, depth=0.3, light=1.5, spec=1.0, line=FINE)
    p.shape("rect", (281, 315, 293, 327), hexc("#5e3820"), radius=2, **NOLINE)
    p.stroke([(287, 315), (287, 327)], shade(gold, 0.8), 3)
    p.shape("rect", (300, 322, 326, 350), hexc("#80502c"), radius=5, depth=0.25, tex="leather")
    p.shape("chord", (298, 316, 328, 338), hexc("#6a4024"), start=0, end=180, depth=0.3, line=FINE)
    rivet(p, 313, 330, 2.6, gold)

    # ---- sword arm (far side): arm reaches forward, fist around the grip, blade raised at the foe
    hand = (382, 262)
    u = unit((0, 0), (0.5, -0.866))
    upper = tube_mask(p, [(304, 254), (326, 280), (344, 298)], [46, 40, 34])
    p.paint_mask(upper, hexc("#8e99a8"), depth=0.2, tex="metal", tex_amt=0.5)
    for row, y in enumerate(range(262, 306, 7)):
        for x in range(296 + (row % 2) * 4, 356, 8):
            p.shape("chord", (x - 4.5, y - 4.5, x + 4.5, y + 4.5), hexc("#b3bdca"), start=0, end=180, line=0.9,
                    light=1.45, shadow=0.66, depth=0.4, rim=0, ao=0, clip=upper)
    fore = tube_mask(p, [(346, 298), (360, 290), (372, 278)], [34, 34, 32])
    metal(p, fore, steel, sheen_pts=[(350, 290), (364, 280)], sheen_w=4.5)
    # flared gauntlet cuff
    cuff = p._mask("poly", curve(rot_pts([(354, 262), (372, 258), (384, 286), (360, 298), (350, 290)],
                                         (368, 278), -10) + [rot_pts([(354, 262)], (368, 278), -10)[0]], 3))
    metal(p, cuff, shade(steel, 1.02), sheen_pts=[(358, 270), (368, 264)], sheen_w=3.5)
    p.stroke(rot_pts([(356, 266), (380, 286)], (368, 278), -10), gold, 3)
    # fan-shaped couter on the elbow
    couter = p._mask("poly", curve([(326, 286), (342, 272), (360, 284), (356, 304), (338, 314), (324, 302),
                                    (326, 286)], 4))
    metal(p, couter, steel, sheen_pts=[(332, 288), (344, 280)], sheen_w=3.5)
    p.shape("poly", [(334, 294), (346, 278), (352, 298), (342, 304)], shade(steel, 0.92), depth=0.3, spec=0.8,
            line=FINE)
    rivet(p, 343, 294, 3)
    # grip, pommel, blade, crossguard, then the gauntlet over the grip
    g0 = (hand[0] - u[0] * 30, hand[1] - u[1] * 30)
    g1 = (hand[0] + u[0] * 22, hand[1] + u[1] * 22)
    p.shape("line", [g0, g1], hexc("#4a2a1a"), width=12, depth=0.35, tex="leather", tex_amt=0.8, line=FINE)
    pm = (hand[0] - u[0] * 38, hand[1] - u[1] * 38)
    p.shape("ellipse", (pm[0] - 10, pm[1] - 10, pm[0] + 10, pm[1] + 10), gold, depth=0.3, light=1.5, gloss=0.9,
            line=FINE)
    tip = (hand[0] + u[0] * 240, hand[1] + u[1] * 240)
    base = (hand[0] + u[0] * 30, hand[1] + u[1] * 30)
    blade(p, base, tip, 30)
    nx, ny = -u[1], u[0]
    gx, gy = hand[0] + u[0] * 29, hand[1] + u[1] * 29
    guard = curve([(gx - nx * 34 - u[0] * 8, gy - ny * 34 - u[1] * 8), (gx - nx * 14, gy - ny * 14),
                   (gx + nx * 14, gy + ny * 14), (gx + nx * 34 - u[0] * 8, gy + ny * 34 - u[1] * 8)], 5)
    p.shape("line", guard, gold, width=11, depth=0.35, light=1.45, spec=1.0, line=FINE, rim=0)
    gem(p, gx, gy, 7.5, hexc("#3a8ae0"), line=1.3)
    fm = fist(p, hand, u, steel, size=22)
    sheen(p, fm, [(hand[0] - 14, hand[1] - 2), (hand[0] - 4, hand[1] - 14)], width=4)
    edge_light(p, fm, hexc("#ffd7b0", 150), width=3)

    # ---- far pauldron
    fp = p._mask("ellipse", (282, 222, 338, 272))
    metal(p, fp, steel, sheen_pts=[(292, 238), (306, 228), (322, 232)], sheen_w=5)
    p.stroke(curve([(288, 256), (310, 268), (334, 256)], 4), gold, 3.5)
    rivet(p, 310, 258, 3)

    # ---- gorget and head
    gor = p._mask("poly", curve([(222, 216), (298, 212), (306, 244), (262, 254), (216, 246)], 4))
    metal(p, gor, shade(steel, 0.95), sheen_pts=[(232, 226), (262, 222)], sheen_w=4)
    p.stroke(curve([(222, 234), (262, 240), (302, 232)], 4), shade(steel_d, 0.8), 2)
    p.tilt((266, 236), 4)  # head dipped toward the foe
    p.paint_mask(face_mask(p, (206, 96, 336, 228)), SKIN, depth=0.12, rim=0.25)
    # cheeks and jaw toward the viewer
    p.flat("ellipse", (240, 198, 264, 210), hexc("#ff7a6a", 60))
    # brown fringe under the helmet brow
    hair = hexc("#7a4424")
    p.shape("poly", curve([(214, 146), (240, 138), (270, 140), (300, 138), (326, 146), (318, 160), (304, 150),
                           (296, 162), (282, 150), (268, 160), (254, 150), (240, 162), (228, 152)], 3),
            hair, depth=0.3, line=FINE, tex="fur", tex_amt=0.4)
    hero_eye(p, 264, 184, 13, 16, hexc("#3a6ab8"), look=0.32, inner=1)
    hero_eye(p, 310, 183, 10, 15, hexc("#3a6ab8"), look=0.3, inner=-1)
    brow(p, (282, 170), (248, 160), hexc("#5a3018"), 7, 3.5)
    brow(p, (298, 170), (320, 160), hexc("#5a3018"), 6, 3)
    # small nose pointing toward the foe, and a set, confident mouth
    soft(p, [(318, 204), (325, 203)], shade(SKIN, 0.55)[:3] + (190,), 3, 0.7)
    p.stroke(curve([(294, 216), (304, 218.5), (313, 215)], 3), hexc("#5a2018"), 3)
    p.stroke([(313, 215), (316, 211.5)], hexc("#5a2018"), 2.2)
    p.stroke(curve([(298, 225), (306, 225)], 2), shade(SKIN, 0.75)[:3] + (170,), 2.2)
    # helmet: dome, crest ridge, brow band, cheek guard wrapping the back of the head
    dome = p._mask("chord", (196, 64, 346, 236), start=180, end=360)
    metal(p, dome, steel, sheen_pts=[(222, 128), (238, 94), (270, 78)], sheen_w=8, depth=0.16)
    p.shape("line", curve([(206, 124), (238, 80), (286, 70), (330, 100)], 6), shade(steel, 1.08), width=10,
            depth=0.3, spec=0.8, rim=0, line=FINE)
    guard = p._mask("poly", curve([(196, 142), (234, 140), (240, 170), (236, 206), (222, 226), (202, 214),
                                   (194, 180)], 4))
    p.shadow_on(guard, strength=0.3, offset=3, blur=3)
    metal(p, guard, shade(steel, 0.96), sheen_pts=[(206, 160), (208, 196)], sheen_w=5)
    p.stroke(curve([(230, 150), (232, 186), (222, 214)], 4), gold, 3)
    rivet(p, 214, 186, 3.6)
    brow_band = p._mask("poly", curve([(192, 132), (270, 124), (348, 132), (346, 150), (270, 144), (196, 154)], 4))
    p.shadow_on(brow_band, strength=0.4, offset=3, blur=3)
    metal(p, brow_band, shade(steel, 0.9), sheen_pts=[(206, 136), (260, 130)], sheen_w=3.5)
    for x in (208, 236, 322, 338):
        rivet(p, x, 139 + (0 if x < 300 else 1), 3)
    # red plume: layered feathers streaming back from a gold holder
    plume = hexc("#d8443a")
    feathers = (
        ([(286, 74), (254, 52), (206, 50), (166, 66), (140, 92)], [22, 30, 30, 22, 6], shade(plume, 0.8)),
        ([(286, 70), (258, 40), (214, 30), (170, 40), (140, 62)], [22, 32, 32, 22, 6], plume),
        ([(286, 64), (270, 34), (238, 18), (200, 18), (174, 30)], [20, 26, 24, 16, 5], light_tone(plume, 1.12)),
    )
    for pts, ws, col in feathers:
        fm_ = p._mask("poly", tube_pts(pts, ws, 8))
        p.paint_mask(fm_, col, depth=0.2, tex="fur", tex_amt=0.5, ink=ink_red)
        fold(p, pts[1:-1], fm_, col, width=4, blur=1.4)
        # barbs: little notches along the lower edge of each feather
        c = curve(pts, 8)
        for t in (0.35, 0.5, 0.65, 0.8):
            k_ = int(t * (len(c) - 1))
            (x0, y0), (x1, y1) = c[k_], c[min(len(c) - 1, k_ + 1)]
            ux_, uy_ = unit((x0, y0), (x1, y1))
            w_ = ws[min(len(ws) - 1, int(t * (len(ws) - 1)))] * 0.45
            p.stroke([(x0 - uy_ * w_ * 0.2, y0 + ux_ * w_ * 0.2), (x0 - uy_ * w_ + ux_ * 6, y0 + ux_ * w_ + uy_ * 6)],
                     shade(col, 0.5)[:3] + (200,), 2)
    top = p.shape("ellipse", (260, 38, 302, 80), plume, depth=0.25, tex="fur", tex_amt=0.5, ink=ink_red)
    fold(p, [(266, 52), (288, 44)], top, plume, width=4, blur=1.5)
    p.shape("rect", (264, 64, 296, 84), gold, radius=4, depth=0.3, light=1.5, spec=1.0, line=FINE)

    p.tilt()

    # ---- near pauldron: layered lames
    lame = p._mask("chord", (168, 236, 244, 296), start=0, end=180)
    metal(p, lame, shade(steel, 0.9))
    dome_p = p._mask("ellipse", (164, 214, 250, 276))
    metal(p, dome_p, steel, sheen_pts=[(178, 236), (196, 222), (224, 220)], sheen_w=6)
    p.stroke(curve([(172, 254), (206, 272), (244, 256)], 5), gold, 4)
    rivet(p, 206, 262, 3.4)
    rivet(p, 180, 246, 3)
    rivet(p, 234, 244, 3)

    # ---- kite shield raised on the near arm
    shield_pts = rot_pts(curve([(120, 252), (180, 240), (240, 252), (238, 322), (216, 378), (180, 420),
                                (144, 378), (122, 322)], 6) + [(120, 252)], (180, 320), -6)
    sm = p._mask("poly", shield_pts)
    p.shadow_on(sm, strength=0.35, offset=6, blur=5)
    metal(p, sm, hexc("#b8c4d2"), sheen_pts=None, depth=0.12)
    inner = p._mask("poly", rot_pts(curve([(132, 262), (180, 252), (228, 262), (226, 320), (206, 370), (180, 404),
                                           (154, 370), (134, 320)], 6) + [(132, 262)], (180, 320), -6))
    p.paint_mask(inner, hexc("#f1ebe0"), depth=0.14, line=FINE, tex="cloth", tex_amt=0.3, rim=0)
    pale = p._mask("poly", rot_pts([(162, 240), (198, 240), (198, 430), (162, 430)], (180, 320), -6))
    pale = ImageChops.multiply(pale, inner)
    p.paint_mask(pale, red, depth=0.1, line=1.3, tex="cloth", tex_amt=0.4, rim=0, ao=0, ink=ink_red)
    # curved-surface shading across the field and a broad sheen
    soft(p, rot_pts([(214, 270), (216, 330), (190, 396)], (180, 320), -6), hexc("#3a2a4a", 70), 22, 7, inner)
    soft(p, rot_pts([(146, 276), (148, 330)], (180, 320), -6), hexc("#ffffff", 120), 12, 5, inner)
    boss_c = rot_pts([(180, 318)], (180, 320), -6)[0]
    bx, by = boss_c
    b = p.shape("ellipse", (bx - 26, by - 26, bx + 26, by + 26), gold, depth=0.3, light=1.5, spec=1.0,
                tex="metal", tex_amt=0.3)
    edge_light(p, b, hexc("#fff0c0", 170), width=3)
    p.shape("ellipse", (bx - 15, by - 15, bx + 15, by + 15), shade(gold, 1.1), depth=0.35, light=1.5, line=FINE,
            rim=0)
    gem(p, bx, by, 8.5, hexc("#3a8ae0"), line=1.3)
    sheen(p, sm, rot_pts([(128, 270), (130, 320), (150, 378)], (180, 320), -6), width=4)
    edge_light(p, sm, hexc("#ffcfa8", 150), width=3.5)
    for x, y in ((128, 262), (180, 250), (232, 262), (232, 318), (128, 318), (206, 372), (154, 372), (180, 410)):
        rivet(p, *rot_pts([(x, y)], (180, 320), -6)[0], r=3.6)
    for pts in (((140, 290), (150, 300)), ((214, 350), (206, 360)), ((196, 290), (204, 284))):
        p.stroke(rot_pts(list(pts), (180, 320), -6), hexc("#8a8078", 170), 1.4)

    # ---- glints
    p.sparkle(lerp(base, tip, 0.8), 13)
    p.sparkle((226, 86), 9)
    p.sparkle((bx - 10, by - 12), 7)
    hero_rim(p)
    return p.finish(outline=OUTLINE, ground_shadow=p.ground_box(272, 320, 482, 30))


# ------------------------------------------------------------------ mage

def open_hand(p, c, color, size=16.0, line=LINE, flip=1):
    """Open hand, palm up and cupped, fingers fanning upward as if holding something above it (flip=-1 puts
    the fingers on the left). Painted as one shape with creases between the fingers."""
    cx, cy = c
    s = size
    f = flip
    items = [("ellipse", (cx - s * 0.9, cy - s * 0.55, cx + s * 0.9, cy + s * 0.62))]
    fingers = []
    for bx, by, dx, dy, ln in ((0.72, -0.05, 0.85, -0.55, 0.72), (0.42, -0.35, 0.5, -0.87, 0.88),
                               (0.08, -0.45, 0.15, -0.99, 0.9), (-0.26, -0.42, -0.12, -0.99, 0.78)):
        base = (cx + f * s * bx, cy + s * by)
        tip = (base[0] + f * s * dx * ln, base[1] + s * dy * ln)
        mid = lerp(base, tip, 0.55)
        mid = (mid[0] + f * s * 0.06, mid[1])
        fingers.append((base, tip))
        items.append(("poly", tube_pts([base, mid, tip], [s * 0.38, s * 0.35, s * 0.31], 4)))
        items.append(("ellipse", (tip[0] - s * 0.155, tip[1] - s * 0.155, tip[0] + s * 0.155, tip[1] + s * 0.155)))
    m = p.union(items)
    p.paint_mask(m, color, depth=0.28, light=1.3, line=line, rim=0.35)
    for (b0, t0), (b1, t1) in zip(fingers, fingers[1:]):
        a = lerp(lerp(b0, t0, 0.2), lerp(b1, t1, 0.2), 0.5)
        b = lerp(lerp(b0, t0, 0.62), lerp(b1, t1, 0.62), 0.5)
        p.stroke([a, b], shade(color, 0.58)[:3] + (200,), 1.6)
    p.stroke(curve([(cx + f * s * 0.55, cy + s * 0.2), (cx, cy + s * 0.05), (cx - f * s * 0.45, cy + s * 0.12)], 3),
             shade(color, 0.62)[:3] + (170,), 1.6)
    tb = (cx - f * s * 0.62, cy - s * 0.02)
    tt = (tb[0] - f * s * 0.3, tb[1] - s * 0.72)
    tm = p.union([("poly", tube_pts([tb, lerp(tb, tt, 0.5), tt], [s * 0.5, s * 0.42, s * 0.34], 3)),
                  ("ellipse", (tt[0] - s * 0.17, tt[1] - s * 0.17, tt[0] + s * 0.17, tt[1] + s * 0.17))])
    p.paint_mask(tm, shade(color, 1.03), depth=0.35, light=1.3, line=1.8, rim=0, ao=0.4)
    return m


def arcane_orb(p, c, r, core=hexc("#f4f0ff"), mid=hexc("#9a7aff"), outer=hexc("#4ab8ff")):
    """Small spell: a bright orb inside a tilted rune ring, with sparks spiralling out of it."""
    cx, cy = c
    p.glow(c, r * 3.4, outer, 0.55)
    p.glow(c, r * 2.0, mid, 0.7)
    # rune ring (an ellipse seen at an angle) with tick marks
    ring = ellipse_pts(cx, cy + r * 0.35, r * 1.9, r * 0.62, 40)
    p.stroke(ring, outer[:3] + (150,), 4.5, soft=1.5)
    p.stroke(ring, hexc("#e8f6ff", 220), 1.6)
    for i in range(12):
        a = math.radians(i * 30 + 8)
        x, y = cx + r * 1.9 * math.cos(a), cy + r * 0.35 + r * 0.62 * math.sin(a)
        p.stroke([(x, y - 2.2), (x, y + 2.2)], hexc("#ffffff", 200), 1.4)
    p.shape("ellipse", (cx - r, cy - r, cx + r, cy + r), mid[:3] + (235,), shadow=0, light=0, line=1.6,
            ink=shade(mid, 0.45)[:3] + (220,), rim=0, ao=0)
    p.glow(c, r * 0.9, core, 0.9)
    p.flat("ellipse", (cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), core)
    p.flat("ellipse", (cx - r * 0.55, cy - r * 0.62, cx - r * 0.05, cy - r * 0.2), WHITE)
    # spiral wisps
    for k0 in (0, 180):
        pts = []
        for i in range(14):
            a = math.radians(k0 + i * 22)
            rr = r * (1.1 + i * 0.09)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * 0.9 - i * 1.2))
        p.stroke(pts, mid[:3] + (140,), 3.2, soft=0.8)
        p.stroke(pts, hexc("#ffffff", 190), 1.3)
    for x, y, rr in ((cx - r * 1.6, cy - r * 1.4, 4), (cx + r * 1.5, cy - r * 1.8, 5),
                     (cx + r * 0.2, cy - r * 2.6, 3.5)):
        p.sparkle((x, y), rr * 1.6, hexc("#f0f4ff"))


def bell_sleeve(p, shoulder, elbow, wrist, color, trim, ink, hang=1, w=38):
    """Wide magic-robe sleeve: upper arm down to the elbow, the forearm rising to the wrist, and the bell of
    cloth hanging below the forearm. `hang` is the side the bell's tip swings to (+1 right, -1 left)."""
    ux, uy = unit(elbow, wrist)
    nx, ny = -uy, ux
    if ny < 0:
        nx, ny = -nx, -ny   # n points down, toward the hanging side
    open_top = (wrist[0] - nx * w * 0.55, wrist[1] - ny * w * 0.55)
    open_bot = (wrist[0] + nx * w * 1.25 + ux * 4, wrist[1] + ny * w * 1.25 + uy * 4)
    tip = (lerp(elbow, wrist, 0.55)[0] + nx * w * 1.45, lerp(elbow, wrist, 0.55)[1] + ny * w * 1.45)
    bell = [(elbow[0] - nx * w * 0.45, elbow[1] - ny * w * 0.45), open_top, lerp(open_top, open_bot, 0.5), open_bot,
            tip, (elbow[0] + nx * w * 0.5, elbow[1] + ny * w * 0.5)]
    m = ImageChops.lighter(tube_mask(p, [shoulder, lerp(shoulder, elbow, 0.5), elbow], [w * 1.1, w * 1.0, w * 0.95]),
                           p._mask("poly", curve(bell + [bell[0]], 4)))
    p.paint_mask(m, color, depth=0.16, tex="cloth", tex_amt=0.6, ink=ink)
    fold(p, [lerp(shoulder, elbow, 0.3), elbow, lerp(elbow, tip, 0.8)], m, color, width=6, blur=2.4)
    fold(p, [lerp(elbow, wrist, 0.3), lerp(lerp(elbow, wrist, 0.7), open_bot, 0.5)], m, color, width=5, blur=2)
    # gold cuff around the opening
    ca, cb = lerp(open_top, wrist, -0.05), lerp(open_bot, wrist, 0.02)
    cuff = p._mask("poly", tube_pts([ca, lerp(ca, cb, 0.5), cb], [12, 13, 12], 3))
    p.paint_mask(cuff, trim, depth=0.3, light=1.45, spec=0.7, line=1.8, rim=0)
    # dark inside of the sleeve showing at the opening
    return m


def mage():
    """Büyücü: young mage in a starry blue robe with gold trim and a pointed hat, a fire-crystal staff in one
    hand and an arcane spell in the other (faces right)."""
    p = HeroPainter(k=0.95, dx=-12, dy=0)
    robe = hexc("#2d4db0")
    robe_d = hexc("#1e2f7c")
    under = hexc("#cdd8f2")
    gold = hexc("#f2bd48")
    hair = hexc("#8a4624")
    boot = hexc("#6a3e24")
    fire = hexc("#ff8a2a")
    ink_b = hexc("#10163e")

    # ---- boots peeking out under the hem
    for pts in ([(186, 458), (224, 452), (246, 462), (254, 484), (184, 486)],
                [(322, 454), (356, 448), (384, 458), (404, 474), (404, 486), (320, 486)]):
        m = p._mask("poly", curve(pts + [pts[0]], 4))
        p.paint_mask(m, boot, depth=0.25, tex="leather", tex_amt=0.8)
    p.shape("rect", (182, 478, 256, 488), shade(boot, 0.55), radius=4, depth=0.3, rim=0)
    p.shape("rect", (318, 478, 406, 488), shade(boot, 0.55), radius=4, depth=0.3, rim=0)
    p.shape("ellipse", (378, 460, 392, 474), gold, depth=0.3, light=1.5, line=1.3, rim=0)

    # ---- the robe: A-line, hem blown back into waves, lining showing where it turns
    robe_pts = curve([(224, 268), (302, 266), (318, 300), (330, 350), (348, 400), (370, 436), (386, 462),
                      (360, 468), (334, 460), (304, 472), (272, 462), (240, 474), (208, 462), (176, 472),
                      (144, 460), (112, 468), (98, 456), (126, 430), (158, 392), (184, 346), (204, 300)], 6)
    rm = p._mask("poly", robe_pts)
    p.paint_mask(rm, robe, depth=0.1, tex="cloth", tex_amt=0.6, ink=ink_b)
    # under-robe showing in the front opening
    opening = ImageChops.multiply(rm, p._mask("poly", curve([(298, 326), (318, 380), (348, 440), (372, 476),
                                                             (300, 476), (292, 400), (292, 326)], 4)))
    p.paint_mask(opening, under, depth=0.16, line=1.6, tex="cloth", tex_amt=0.5, rim=0)
    for pts in ([(306, 360), (318, 420), (330, 468)], [(296, 380), (302, 468)]):
        fold(p, pts, opening, under, width=5, blur=2)
    # folds fanning from the waist to the hem valleys
    for pts in ([(232, 330), (206, 400), (176, 468)], [(250, 340), (244, 410), (240, 470)],
                [(274, 340), (276, 410), (272, 460)], [(214, 326), (170, 400), (140, 456)],
                [(318, 360), (344, 420), (360, 464)]):
        fold(p, pts, rm, robe, width=9, blur=3.4)
    # arcane glow creeping up from the hem
    soft(p, [(110, 470), (200, 468), (300, 470), (380, 466)], hexc("#7ab8ff", 70), 30, 9, rm)
    # gold trim: hem band and the opening edge, with runes stitched along the hem
    hem = [(100, 458), (112, 466), (144, 458), (176, 470), (208, 460), (240, 472), (272, 460), (304, 470),
           (334, 458), (360, 466), (384, 460)]
    p.shape("line", curve(hem, 5), gold, width=8, depth=0.35, light=1.45, spec=0.7, rim=0, line=1.8)
    p.shape("line", curve([(294, 324), (296, 400), (300, 470)], 5), gold, width=7, depth=0.35, light=1.45,
            spec=0.7, rim=0, line=1.8)
    p.shape("line", curve([(300, 326), (322, 390), (352, 444), (374, 470)], 5), gold, width=6, depth=0.35,
            light=1.45, spec=0.7, rim=0, line=1.8)
    for x, y, r in ((214, 400, 9), (256, 430, 7), (170, 432, 6), (236, 370, 5), (182, 374, 5), (326, 420, 5),
                    (270, 392, 4.5), (150, 452, 4)):
        p.shape("poly", star_pts(x, y, r, 0.45), hexc("#ffe28a"), line=1.2, depth=0.3, light=1.45, rim=0, ao=0,
                clip=rm)
    for x, y in ((226, 440), (196, 420), (284, 420), (160, 412), (248, 392), (206, 352)):
        mote(p, x, y, 2, hexc("#9ad0ff"))
    # a band of glowing arcane embroidery following the hem: diamonds and dots
    outer = ImageChops.subtract(rm, _dilate_mask(opening, 3))
    for i, (x, y) in enumerate(along(curve(hem, 6), 21)[1:]):
        y -= 17
        if outer.getpixel((int(p.pt(x, y)[0] * SS), int(p.pt(x, y)[1] * SS))) < 128:
            continue
        p.glow((x, y), 10, hexc("#6ab8ff"), 0.4)
        if i % 2 == 0:
            p.shape("poly", [(x, y - 6), (x + 4.5, y), (x, y + 6), (x - 4.5, y)], hexc("#bfe8ff"), line=1.2,
                    depth=0.3, light=1.4, rim=0, ao=0, ink=hexc("#1a3a8a"))
        else:
            p._fill(p._mask("ellipse", (x - 2.2, y - 2.2, x + 2.2, y + 2.2)), hexc("#e8f6ff"), solid=False)

    # ---- sash: belt with a round gold buckle, a tassel and a little spellbook
    p.shape("poly", curve([(202, 318), (262, 322), (322, 316), (324, 336), (262, 342), (200, 338)], 4),
                   hexc("#6a3f24"), depth=0.35, tex="leather", tex_amt=0.8)
    stitch_line(p, [(206, 324), (262, 328), (318, 322)], hexc("#c89a6a"), step=7, length=3.5, width=1.3)
    p.shape("ellipse", (276, 314, 304, 342), gold, depth=0.3, light=1.5, spec=1.0, line=1.8)
    gem(p, 290, 328, 6.5, hexc("#e0503a"), line=1.2)
    p.shape("line", curve([(224, 338), (220, 362), (224, 382)], 4), gold, width=4, depth=0.3, rim=0, line=1.4)
    p.shape("poly", curve([(214, 380), (234, 380), (238, 404), (210, 404)], 3) + [(214, 380)], gold, depth=0.3,
            light=1.4, line=1.5, rim=0)
    for x in (216, 222, 228, 234):
        p.stroke([(x, 386), (x - 1, 402)], shade(gold, 0.65), 1.3)
    p.shape("rect", (236, 334, 266, 370), hexc("#8a2f2a"), radius=4, depth=0.25, tex="leather",
                   tex_amt=0.8)
    p.shape("rect", (240, 338, 262, 366), shade(hexc("#8a2f2a"), 1.1), radius=3, **NOLINE)
    p.shape("poly", star_pts(251, 352, 7, 0.45), gold, line=1.1, depth=0.3, rim=0, ao=0)
    p.shape("rect", (262, 334, 268, 370), hexc("#f4ecd8"), radius=2, line=1.2, depth=0.3, rim=0)

    # ---- staff (far hand): gnarled wood, gold ferrules, a claw head clutching the fire crystal
    s0, s1 = (384, 484), (430, 108)
    su = unit(s0, s1)
    staff = [s0, lerp(s0, s1, 0.33), lerp(s0, s1, 0.66), s1]
    p.shape("poly", tube_pts(staff, [11, 12, 13, 14], 6), hexc("#9a6433"), depth=0.3, tex="wood", tex_amt=0.9,
            line=2.2)
    for t in (0.28, 0.62):
        x, y = lerp(s0, s1, t)
        p.shape("rect", (x - 10, y - 6, x + 10, y + 6), gold, radius=3, depth=0.3, spec=0.8, line=1.6, rim=0)
    cx_, cy_ = 430, 72
    p.glow((cx_, cy_), 104, fire, 0.66)
    p.glow((cx_, cy_), 48, hexc("#ffd07a"), 0.8)
    for pts in ([(426, 112), (404, 98), (398, 70), (404, 52)], [(426, 112), (450, 96), (458, 70), (452, 50)],
                [(426, 112), (428, 94)]):
        p.shape("poly", tube_pts(pts, [12, 10, 8, 5][:len(pts)], 4), hexc("#8a5a2e"), depth=0.3, tex="wood",
                line=2.0, rim=0)
    crys = [(430, 24), (452, 56), (446, 92), (430, 108), (414, 92), (408, 56)]
    cm = p.shape("poly", crys, hexc("#ff9a2a"), depth=0.25, light=1.55, line=2.2, ink=hexc("#7a2a0a"), gloss=0.9,
                 rim=0)
    p.shape("poly", [(430, 34), (444, 58), (430, 98), (418, 58)], hexc("#ffc45a"), clip=cm, **NOLINE)
    flame(p, 430, 90, 22, 44, lean=0.05, glow=False)
    p.stroke([(430, 26), (418, 58), (430, 104)], hexc("#fff3c0", 200), 2)
    p.stroke([(410, 58), (452, 58)], hexc("#b8401a", 160), 1.6)
    p.sparkle((418, 44), 12)
    for x, y, r in ((466, 38, 3.2), (394, 30, 2.6), (474, 92, 2.6), (446, 132, 2.2), (398, 118, 2)):
        mote(p, x, y, r, fire, hexc("#fff0b0"))
    # prong tips over the crystal
    for pts in ([(398, 70), (404, 52), (414, 46)], [(458, 70), (452, 50), (444, 44)]):
        p.shape("poly", tube_pts(pts, [8, 5, 3], 4), hexc("#8a5a2e"), depth=0.3, line=1.6, rim=0)

    # ---- far arm: bell sleeve reaching to the staff
    bell_sleeve(p, (306, 290), (346, 334), (396, 298), robe, gold, ink_b, hang=1)
    fist(p, lerp(s0, s1, 0.52), su, SKIN, size=15, side=-1, line=2.2)

    # ---- mantle over the shoulders, gold edge, star clasp
    mant = p._mask("poly", curve([(202, 276), (230, 258), (270, 254), (310, 262), (330, 286), (318, 312),
                                  (296, 306), (272, 318), (248, 306), (224, 316), (204, 302)], 5))
    p.paint_mask(mant, robe_d, depth=0.18, tex="cloth", tex_amt=0.6, ink=ink_b)
    p.stroke(curve([(204, 302), (224, 314), (248, 304), (272, 316), (296, 304), (318, 310)], 5), gold, 4)
    fold(p, [(240, 272), (246, 300)], mant, robe_d, width=5, blur=2)
    fold(p, [(292, 272), (300, 298)], mant, robe_d, width=5, blur=2)
    p.shape("ellipse", (282, 272, 308, 298), gold, depth=0.3, light=1.5, spec=1.0, line=1.8)
    p.shape("poly", star_pts(295, 285, 8, 0.45), hexc("#fff4c0"), line=1.0, rim=0, ao=0)

    # ---- head: hair behind, face, fringe
    p.tilt((274, 272), 3)
    back_hair = p._mask("poly", curve([(214, 196), (200, 240), (206, 272), (224, 262), (230, 286), (244, 262),
                                       (246, 230)], 4))
    p.paint_mask(back_hair, hair, depth=0.25, tex="fur", tex_amt=0.4)
    fold(p, [(214, 220), (212, 262)], back_hair, hair, width=3, blur=1)
    p.paint_mask(face_mask(p, (212, 148, 334, 268)), SKIN, depth=0.12, rim=0.25)
    p.flat("ellipse", (240, 232, 264, 244), hexc("#ff7a6a", 60))
    p.flat("ellipse", (316, 230, 330, 240), hexc("#ff7a6a", 45))
    hero_eye(p, 266, 220, 13, 16, hexc("#d0701c"), look=0.32, inner=1, tilt=0.36)
    hero_eye(p, 311, 219, 10, 15, hexc("#d0701c"), look=0.3, inner=-1, tilt=0.36)
    brow(p, (282, 202), (250, 194), hair, 6.5, 3.2)
    brow(p, (298, 202), (320, 194), hair, 5.5, 2.8)
    soft(p, [(324, 228), (327, 236)], shade(SKIN, 0.7)[:3] + (130,), 4, 1.2)
    p.stroke([(318, 238), (326, 237)], shade(SKIN, 0.55), 2.6)
    # a confident little smile
    p.stroke(curve([(290, 249), (302, 253), (314, 250), (318, 245)], 4), hexc("#6a2420"), 3.2)
    p.stroke(curve([(298, 259), (306, 259)], 2), shade(SKIN, 0.75)[:3] + (170,), 2.2)
    # hair locks by the ear and the fringe under the brim
    p.shape("poly", curve([(214, 172), (236, 170), (242, 200), (232, 230), (222, 214), (214, 232), (208, 200)], 4)
            + [(214, 172)], hair, depth=0.25, tex="fur", tex_amt=0.4, line=2.0)
    fringe = curve([(216, 176), (246, 164), (284, 164), (322, 168), (336, 186), (326, 196), (318, 184),
                    (306, 198), (296, 180), (282, 196), (270, 178), (256, 194), (246, 178), (232, 190)], 3)
    fr = p.shape("poly", fringe + [fringe[0]], hair, depth=0.3, tex="fur", tex_amt=0.4, line=2.0)
    fold(p, [(256, 170), (262, 186)], fr, hair, width=3, blur=1)
    fold(p, [(296, 170), (302, 184)], fr, hair, width=3, blur=1)

    # ---- the pointed hat: cone with its tip flopping back, band with a gem, broad tilted brim
    cone = curve([(214, 164), (230, 124), (254, 90), (282, 60), (308, 50), (322, 72), (324, 110), (334, 164)], 6)
    hm = p._mask("poly", cone)
    p.paint_mask(hm, robe, depth=0.14, light=1.3, tex="cloth", tex_amt=0.6, ink=ink_b)
    tip = p._mask("poly", tube_pts([(304, 64), (286, 40), (250, 28), (212, 36), (186, 58), (178, 80)],
                                   [44, 36, 28, 20, 14, 10], 6))
    p.paint_mask(tip, robe, depth=0.2, light=1.3, tex="cloth", tex_amt=0.6, ink=ink_b)
    fold(p, [(290, 46), (252, 38), (214, 48)], tip, robe, width=6, blur=2.4)
    fold(p, [(262, 100), (246, 150)], hm, robe, width=8, blur=3)
    fold(p, [(310, 80), (318, 150)], hm, robe, width=7, blur=3)
    p.shape("line", [(178, 80), (176, 92)], gold, width=3, rim=0, line=1.2)
    p.shape("poly", star_pts(176, 104, 14, 0.46, rot=-80), gold, depth=0.3, light=1.5, spec=0.9, line=1.8,
                    rim=0)
    p.glow((176, 104), 20, hexc("#ffe28a"), 0.35)
    for x, y, r in ((270, 104, 7), (300, 86, 5), (240, 44, 5), (292, 132, 4.5)):
        p.shape("poly", star_pts(x, y, r, 0.45), hexc("#ffe28a"), line=1.2, depth=0.3, rim=0, ao=0,
                clip=ImageChops.lighter(hm, tip))
    # crescent moon on the cone
    moon = ImageChops.subtract(p._mask("ellipse", (240, 118, 266, 144)), p._mask("ellipse", (246, 114, 272, 140)))
    p.paint_mask(moon, hexc("#ffe28a"), depth=0.3, light=1.4, line=1.2, rim=0, ao=0)
    p.shape("poly", curve([(214, 152), (274, 146), (334, 152), (336, 170), (274, 166), (212, 172)], 4),
                   gold, depth=0.3, light=1.45, spec=0.8, line=1.8)
    gem(p, 300, 158, 7, hexc("#3a8ae0"), line=1.2)
    brim = p._mask("poly", rot_pts(ellipse_pts(270, 168, 116, 19, 60), (270, 168), -5))
    p.shadow_on(brim, strength=0.45, offset=4, blur=4)
    p.paint_mask(brim, robe_d, depth=0.24, light=1.35, tex="cloth", tex_amt=0.6, ink=ink_b)
    p.stroke(rot_pts(curve([(160, 176), (220, 188), (270, 191), (330, 186), (382, 170)], 5), (270, 172), -5),
             gold, 3.5)
    sheen(p, brim, rot_pts([(180, 166), (230, 158), (280, 156)], (270, 172), -5), hexc("#b8d0ff", 120), width=6)
    # re-cut the band over the brim's back edge
    p.shape("poly", curve([(214, 152), (274, 146), (334, 152), (334, 160), (274, 156), (214, 160)], 4),
            gold, depth=0.3, light=1.45, spec=0.8, line=0, rim=0, ao=0)

    p.tilt()

    # ---- near arm held out to the side, palm up under a spell
    bell_sleeve(p, (222, 290), (184, 336), (150, 300), robe, gold, ink_b, hang=-1)
    open_hand(p, (136, 290), SKIN, size=18, flip=-1, line=2.2)
    # light from the spell and the crystal falling on the mage
    spill(p, (128, 240), 130, hexc("#8ab8ff"), 0.3)
    spill(p, (430, 70), 190, hexc("#ffa040"), 0.4)
    arcane_orb(p, (128, 238), 19)
    for x, y, r in ((82, 400, 3), (72, 320, 2.4), (460, 250, 2.4)):
        mote(p, x, y, r, hexc("#7ab8ff"))
    hero_rim(p)
    return p.finish(outline=OUTLINE, ground_shadow=p.ground_box(262, 330, 482, 30))


# ------------------------------------------------------------------ rogue

def dagger(p, hand, u, length, width=18, guard_c=hexc("#4a4452"), blade_c=hexc("#dfe8f0"), grip_c=hexc("#3a2418"),
           reverse=False):
    """Dagger held at `hand`, blade pointing along u (away from the fist). Returns the blade's tip."""
    nx, ny = -u[1], u[0]
    b0 = (hand[0] + u[0] * 22, hand[1] + u[1] * 22)
    tip = (hand[0] + u[0] * (22 + length), hand[1] + u[1] * (22 + length))
    g0 = (hand[0] - u[0] * 24, hand[1] - u[1] * 24)
    p.shape("line", [g0, b0], grip_c, width=10, depth=0.35, tex="leather", tex_amt=0.8, line=1.8)
    pm = (hand[0] - u[0] * 27, hand[1] - u[1] * 27)
    p.shape("ellipse", (pm[0] - 7, pm[1] - 7, pm[0] + 7, pm[1] + 7), guard_c, depth=0.3, light=1.5, spec=0.9,
            line=1.8, rim=0)
    # slightly curved, leaf-shaped blade
    L = length
    pts = [(b0[0] + nx * width * 0.42, b0[1] + ny * width * 0.42),
           (b0[0] + u[0] * L * 0.45 + nx * width * 0.55, b0[1] + u[1] * L * 0.45 + ny * width * 0.55),
           (b0[0] + u[0] * L * 0.8 + nx * width * 0.3, b0[1] + u[1] * L * 0.8 + ny * width * 0.3), tip,
           (b0[0] + u[0] * L * 0.7 - nx * width * 0.42, b0[1] + u[1] * L * 0.7 - ny * width * 0.42),
           (b0[0] - nx * width * 0.42, b0[1] - ny * width * 0.42)]
    m = p._mask("poly", curve(pts, 5))
    p.paint_mask(m, blade_c, depth=0.3, light=1.4, spec=1.0, tex="metal", tex_amt=0.35, rim=0.3)
    ridge = [(b0[0] + u[0] * 6, b0[1] + u[1] * 6), (b0[0] + u[0] * L * 0.75 + nx * width * 0.06,
                                                   b0[1] + u[1] * L * 0.75 + ny * width * 0.06), tip]
    half = p._mask("poly", ridge + [(b0[0] - nx * width, b0[1] - ny * width)])
    p._fill(ImageChops.multiply(_blur(half, SS), _erode(m, SS * 2)), shade(blade_c, 0.78)[:3] + (140,),
            solid=False)
    p.stroke(ridge, hexc("#ffffff", 170), 1.6)
    edge_light(p, m, hexc("#c8ffd0", 120), width=2.5)
    gx, gy = b0
    guard = [(gx - nx * 20 - u[0] * 3, gy - ny * 20 - u[1] * 3), (gx - nx * 8, gy - ny * 8),
             (gx + nx * 8, gy + ny * 8), (gx + nx * 20 - u[0] * 3, gy + ny * 20 - u[1] * 3)]
    p.shape("line", curve(guard, 4), guard_c, width=8, depth=0.35, light=1.5, spec=0.9, line=1.8, rim=0)
    return tip


def knee_guard(p, c, color, stitch):
    """Hardened-leather knee guard: a shield-like cup with a stitched rim and a steel stud."""
    kx, ky = c
    m = p._mask("poly", curve([(kx - 20, ky - 10), (kx - 2, ky - 22), (kx + 18, ky - 14), (kx + 22, ky + 6),
                               (kx + 4, ky + 22), (kx - 16, ky + 14), (kx - 20, ky - 10)], 5))
    p.paint_mask(m, shade(color, 1.08), depth=0.3, light=1.35, tex="leather", tex_amt=0.8)
    stitch_line(p, [(kx - 14, ky - 8), (kx - 2, ky - 16), (kx + 14, ky - 10), (kx + 16, ky + 4)], stitch, step=6,
                length=3, width=1.2)
    edge_light(p, m, hexc("#ffd9a8", 110), width=2.5)
    rivet(p, kx + 1, ky + 2, 3.4, hexc("#c8ccd4"))


def rogue():
    """Haydut: nimble rogue in a green hood and scarf mask, leather armour, a dagger in each hand and a poison
    vial on the belt, crouched low with the cloak swept back (faces right)."""
    p = HeroPainter(k=1.1, dx=-14, dy=0)
    cloak = hexc("#2f7048")
    cloak_d = hexc("#1f4a32")
    lining = hexc("#5a8a3a")
    leather = hexc("#7e4c2a")
    leather_d = hexc("#4e2e1a")
    cloth = hexc("#3c3646")
    tunic = hexc("#3f6a4c")
    mask_c = hexc("#2c4038")
    hair = hexc("#3a2418")
    stitch = hexc("#d8b080")
    ink_g = hexc("#0e2418")
    poison = hexc("#5ae84a")

    # ---- cloak swept back in the wind, ragged points, lighter lining where it turns
    cp = curve([(248, 246), (206, 250), (166, 262), (128, 280), (96, 300), (82, 318), (106, 320), (90, 350),
                (118, 346), (108, 382), (138, 368), (136, 404), (162, 382), (172, 414), (192, 384), (210, 404),
                (222, 360), (246, 330)], 5)
    cm = p._mask("poly", cp)
    p.paint_mask(cm, cloak_d, depth=0.1, tex="cloth", tex_amt=0.6, ink=ink_g)
    lin = p._mask("poly", curve([(82, 318), (102, 306), (128, 300), (120, 316), (106, 320)], 4))
    p.paint_mask(lin, lining, depth=0.25, line=1.8, rim=0, tex="cloth", tex_amt=0.5, ink=ink_g)
    for pts in ([(226, 262), (160, 290), (100, 318)], [(230, 280), (170, 320), (120, 346)],
                [(234, 300), (190, 346), (140, 384)], [(236, 316), (206, 360), (176, 400)]):
        fold(p, pts, cm, cloak_d, width=8, blur=3)
    # scarf tails fluttering behind the neck
    for pts, ws in (([(262, 246), (222, 222), (186, 214), (150, 196)], [30, 30, 24, 4]),
                    ([(262, 254), (226, 250), (196, 262), (166, 256)], [26, 24, 18, 4])):
        sm = p._mask("poly", tube_pts(pts, ws, 6))
        p.paint_mask(sm, mask_c, depth=0.2, tex="cloth", tex_amt=0.6, line=2.2)
        fold(p, pts[1:], sm, mask_c, width=4, blur=1.4)

    # ---- front (far) leg: bent forward, weight on it
    thigh = tube_mask(p, [(298, 338), (326, 364), (350, 388)], [54, 48, 40])
    p.paint_mask(thigh, cloth, depth=0.2, tex="cloth", tex_amt=0.5)
    fold(p, [(310, 356), (334, 372)], thigh, cloth, width=5, blur=1.8)
    shin = tube_mask(p, [(350, 388), (356, 420), (358, 450)], [38, 34, 30])
    p.paint_mask(shin, leather, depth=0.22, tex="leather", tex_amt=0.8)
    for y in (402, 418, 434):
        p.stroke([(338, y), (374, y + 6)], stitch, 2.2)
    foot = p._mask("poly", curve([(336, 446), (366, 440), (394, 454), (414, 470), (414, 486), (334, 486),
                                  (332, 462)], 5))
    p.paint_mask(foot, leather_d, depth=0.22, tex="leather", tex_amt=0.8)
    p.shape("poly", curve([(330, 400), (372, 392), (378, 412), (334, 420)], 3) + [(330, 400)],
                    shade(leather, 1.1), depth=0.3, tex="leather", tex_amt=0.8)
    stitch_line(p, [(336, 410), (372, 403)], stitch, step=6, length=3, width=1.3)
    p.shape("rect", (330, 478, 416, 488), shade(leather_d, 0.6), radius=4, depth=0.3, rim=0)
    knee_guard(p, (349, 379), leather, stitch)

    # ---- back (near) leg: knee dropped low, on the ball of the foot
    thigh = tube_mask(p, [(244, 346), (220, 380), (196, 414)], [58, 50, 42])
    p.paint_mask(thigh, cloth, depth=0.2, tex="cloth", tex_amt=0.5)
    shin = tube_mask(p, [(194, 414), (176, 436), (156, 452)], [40, 36, 30])
    p.paint_mask(shin, leather, depth=0.22, tex="leather", tex_amt=0.8)
    for x in (166, 180, 194):
        p.stroke([(x, 426 - (x - 166) * 0.6), (x + 12, 444 - (x - 166) * 0.6)], stitch, 2.2)
    foot = p._mask("poly", curve([(140, 446), (164, 440), (188, 460), (214, 474), (216, 486), (160, 486),
                                  (134, 466)], 5))
    p.paint_mask(foot, leather_d, depth=0.22, tex="leather", tex_amt=0.8)
    p.shape("rect", (156, 478, 218, 488), shade(leather_d, 0.6), radius=4, depth=0.3, rim=0)
    knee_guard(p, (196, 414), leather, stitch)

    # ---- torso: leather jerkin leaning into the stance
    torso = p._mask("poly", curve([(236, 244), (312, 238), (330, 276), (334, 326), (320, 352), (244, 356),
                                   (226, 324), (226, 280)], 5))
    p.paint_mask(torso, leather, depth=0.14, tex="leather", tex_amt=0.9)
    # panels with stitched seams
    for pts in ([(282, 246), (286, 300), (282, 348)], [(250, 290), (318, 286)], [(246, 316), (324, 314)]):
        p.stroke(curve(pts, 4), shade(leather, 0.6), 2)
    for pts in ([(288, 250), (292, 300), (288, 344)], [(250, 296), (318, 292)], [(246, 322), (324, 320)]):
        stitch_line(p, pts, stitch, step=7, length=3.5, width=1.3)
    edge_light(p, torso, hexc("#ffd9a8", 120), width=3)
    # cross strap with throwing knives
    p.shape("poly", tube_pts([(244, 252), (286, 296), (326, 340)], [16, 16, 16], 3), leather_d, depth=0.3,
                    tex="leather", tex_amt=0.8)
    stitch_line(p, [(246, 248), (286, 290), (322, 332)], stitch, step=7, length=3, width=1.2)
    for t in (0.3, 0.52, 0.74):
        x, y = lerp((244, 252), (326, 340), t)
        p.shape("poly", [(x - 4, y - 2), (x + 4, y - 4), (x + 8, y - 26), (x + 2, y - 30), (x - 2, y - 24)],
                hexc("#d8e0e8"), line=1.6, depth=0.3, light=1.4, spec=0.9, rim=0)
        p.shape("rect", (x - 5, y - 4, x + 5, y + 4), hexc("#2a2230"), radius=2, line=1.4, depth=0.3, rim=0)
    # belt, pouches and the poison vial
    p.shape("poly", curve([(226, 332), (280, 334), (334, 326), (336, 346), (280, 352), (226, 350)], 4), leather_d,
            depth=0.35, tex="leather", tex_amt=0.8)
    stitch_line(p, [(230, 337), (280, 339), (330, 332)], stitch, step=7, length=3.5, width=1.2)
    p.shape("rect", (268, 328, 292, 354), hexc("#b4bcc6"), radius=3, depth=0.3, light=1.5, spec=1.0, line=1.8)
    p.shape("rect", (274, 334, 286, 348), leather_d, radius=2, **NOLINE)
    for x0 in (234,):
        p.shape("rect", (x0, 344, x0 + 28, 376), hexc("#8a5a32"), radius=5, depth=0.25, tex="leather")
        p.shape("chord", (x0 - 2, 336, x0 + 30, 362), leather, start=0, end=180, depth=0.3, line=1.8)
        rivet(p, x0 + 14, 352, 2.6, hexc("#f0bb45"))
    vx, vy = 322, 368
    p.glow((vx, vy), 36, poison, 0.55)
    p.shape("rect", (vx - 5, vy - 26, vx + 5, vy - 14), hexc("#a07040"), radius=2, line=1.4, depth=0.3, rim=0)
    p.shape("rect", (vx - 7, vy - 16, vx + 7, vy - 10), hexc("#b8c0c8"), radius=2, line=1.4, depth=0.3, rim=0)
    vm = p.shape("ellipse", (vx - 16, vy - 14, vx + 16, vy + 18), hexc("#3ac83a", 235), depth=0.25, light=1.5,
                 line=2.0, ink=hexc("#0e3a14"), rim=0, ao=0.2)
    p.shape("chord", (vx - 15, vy - 6, vx + 15, vy + 17), poison, start=-10, end=190, clip=vm, **NOLINE)
    spill(p, (vx, vy), 70, poison, 0.35)
    p.flat("ellipse", (vx - 10, vy - 9, vx - 3, vy - 1), hexc("#ffffff", 220))
    for bx, by, r in ((vx + 4, vy + 4, 2.4), (vx - 3, vy + 9, 1.8), (vx + 7, vy - 2, 1.5)):
        p.flat("ellipse", (bx - r, by - r, bx + r, by + r), hexc("#d8ffc8", 200))
    p.stroke(curve([(vx, vy + 18), (vx + 2, vy + 26)], 2), hexc("#8aff6a", 200), 3)

    # ---- front (far) arm: bracer, dagger thrust forward
    hand = (380, 296)
    u = unit((0, 0), (0.86, -0.51))
    upper = tube_mask(p, [(310, 262), (330, 290), (346, 304)], [40, 36, 32])
    p.paint_mask(upper, tunic, depth=0.2, tex="cloth", tex_amt=0.5)
    fold(p, [(318, 276), (336, 296)], upper, tunic, width=4, blur=1.5)
    fore = tube_mask(p, [(344, 304), (358, 302), (372, 298)], [32, 32, 30])
    p.paint_mask(fore, leather, depth=0.25, tex="leather", tex_amt=0.9)
    for x in (350, 362):
        p.stroke([(x, 288), (x + 4, 314)], leather_d, 2.2)
    stitch_line(p, [(344, 292), (370, 288)], stitch, step=6, length=3, width=1.2)
    tip = dagger(p, hand, u, 80, width=18)
    fist(p, hand, u, SKIN, size=15, side=1, line=2.2)
    p.sparkle(lerp(hand, tip, 0.85), 10)

    # ---- hood: pointed tip trailing back, capelet over the shoulders (the head tilts into the lunge)
    capelet = p._mask("poly", curve([(214, 236), (256, 222), (314, 226), (334, 250), (320, 280), (292, 272),
                                     (268, 288), (244, 274), (222, 284), (208, 262)], 5))
    p.paint_mask(capelet, cloak, depth=0.16, tex="cloth", tex_amt=0.7, ink=ink_g)
    for pts in ([(244, 244), (244, 272)], [(282, 240), (286, 268)], [(312, 246), (314, 268)]):
        fold(p, pts, capelet, cloak, width=5, blur=2)
    p.tilt((286, 250), 5)
    hood = p.union([("ellipse", (196, 80, 370, 254)),
                    ("poly", curve([(236, 96), (190, 80), (146, 86), (118, 106), (160, 110), (196, 132),
                                    (212, 160)], 5))])
    p.paint_mask(hood, cloak, depth=0.12, tex="cloth", tex_amt=0.7, ink=ink_g)
    for pts in ([(222, 110), (176, 98), (140, 100)], [(214, 140), (206, 190), (214, 230)],
                [(248, 100), (232, 140)]):
        fold(p, pts, hood, cloak, width=7, blur=2.6)
    stitch_line(p, [(128, 104), (170, 90), (220, 88), (262, 88)], hexc("#9ad0a8", 170), step=9, length=4.5,
                width=1.5)
    # dark opening, then the face inside it
    opening = p._mask("poly", rot_pts(ellipse_pts(292, 176, 58, 64, 60), (292, 176), -12))
    p.paint_mask(opening, hexc("#12201a"), depth=0.2, line=1.8, rim=0, shadow=0.8, light=0)
    fm_ = ImageChops.multiply(face_mask(p, (254, 118, 350, 236), chin=0.9), _erode(opening, 2 * SS))
    p.paint_mask(fm_, SKIN, depth=0.12, rim=0.2)
    p.stroke(curve(rot_pts(ellipse_pts(292, 176, 60, 66, 30, 150, 300), (292, 176), -12), 6), shade(cloak, 1.25),
             5)
    # hair falling from under the hood
    p.shape("poly", curve([(244, 132), (276, 118), (318, 120), (348, 136), (338, 146), (328, 138), (322, 156),
                           (310, 138), (298, 156), (288, 138), (274, 154), (264, 138), (252, 158)], 3)
            + [(244, 132)], hair, depth=0.3, tex="fur", tex_amt=0.4, line=2.0)
    # the hood's rim throws the upper face into shadow, fading out just above the eyes
    top, bot = p.pt(292, 112)[1] * SS, p.pt(292, 176)[1] * SS
    grad = Image.linear_gradient("L").resize((p.img.size[0], max(1, int(bot - top))))
    shade_m = Image.new("L", p.img.size, 255)
    shade_m.paste(ImageChops.invert(grad), (0, int(top)))
    shade_m.paste(Image.new("L", (p.img.size[0], p.img.size[1] - int(bot)), 0), (0, int(bot)))
    p._fill(ImageChops.multiply(shade_m.point(lambda v: v * 190 // 255), _erode(opening, 2 * SS)),
            hexc("#0e1a22"), solid=False)
    hero_eye(p, 284, 178, 12, 13, hexc("#2ab080"), look=0.35, inner=1, tilt=0.5)
    hero_eye(p, 326, 177, 9, 12, hexc("#2ab080"), look=0.3, inner=-1, tilt=0.5)
    brow(p, (300, 166), (266, 152), hair, 7, 3.2)
    brow(p, (314, 166), (338, 156), hair, 6, 2.8)
    # scarf mask over the nose and mouth, wrapping into the neck
    mk = p._mask("poly", curve([(236, 200), (268, 204), (300, 200), (326, 194), (342, 186), (356, 196),
                                (360, 208), (354, 222), (340, 240), (300, 252), (262, 248), (238, 232)], 5))
    mk = ImageChops.multiply(mk, _dilate_mask(opening, 7))
    p.shadow_on(mk, strength=0.3, offset=3, blur=3)
    p.paint_mask(mk, mask_c, depth=0.18, tex="cloth", tex_amt=0.6, line=2.2)
    # the cloth tents over the nose: a lit ridge and folds pulling down from it
    soft(p, [(338, 190), (348, 196), (354, 208)], light_tone(mask_c, 1.6)[:3] + (170,), 5, 1.2, mk)
    fold(p, [(340, 196), (318, 214), (282, 222), (250, 214)], mk, mask_c, width=5, blur=1.8)
    fold(p, [(346, 212), (324, 232), (290, 240), (262, 234)], mk, mask_c, width=4, blur=1.6)
    soft(p, [(244, 204), (300, 204), (334, 194)], light_tone(mask_c, 1.4)[:3] + (110,), 3, 0.8, mk)

    p.tilt()

    # ---- back (near) arm: trailing low, a reverse-grip dagger
    hand = (170, 338)
    upper = tube_mask(p, [(238, 272), (218, 300), (200, 322)], [42, 38, 34])
    p.paint_mask(upper, tunic, depth=0.2, tex="cloth", tex_amt=0.5)
    fold(p, [(230, 286), (212, 310)], upper, tunic, width=4, blur=1.5)
    # layered leather spaulder on the near shoulder
    for box, col in (((210, 278, 254, 312), shade(leather, 0.92)), ((214, 258, 262, 300), leather)):
        sp = p._mask("poly", rot_pts(curve([(box[0], box[1] + 14), ((box[0] + box[2]) / 2, box[1]),
                                            (box[2], box[1] + 12), (box[2] - 4, box[3] - 6),
                                            ((box[0] + box[2]) / 2, box[3]), (box[0] + 2, box[3] - 8),
                                            (box[0], box[1] + 14)], 4), (236, 284), -28))
        p.paint_mask(sp, col, depth=0.25, light=1.35, tex="leather", tex_amt=0.8)
        edge_light(p, sp, hexc("#ffd9a8", 110), width=2.5)
    stitch_line(p, rot_pts([(220, 290), (238, 296), (256, 290)], (236, 284), -28), stitch, step=6, length=3,
                width=1.2)
    rivet(p, *rot_pts([(238, 276)], (236, 284), -28)[0], r=3.2, color=hexc("#c8ccd4"))
    fore = tube_mask(p, [(202, 322), (188, 332), (176, 338)], [34, 32, 30])
    p.paint_mask(fore, leather, depth=0.25, tex="leather", tex_amt=0.9)
    for x in (184, 196):
        p.stroke([(x - 8, 320), (x + 2, 346)], leather_d, 2.2)
    du = unit((0, 0), (-0.5, 0.866))
    dagger(p, hand, du, 72, width=16)
    fist(p, hand, (-du[0], -du[1]), SKIN, size=15, side=-1, line=2.2)
    p.sparkle((150, 392), 8)
    hero_rim(p)
    return p.finish(outline=OUTLINE, ground_shadow=p.ground_box(270, 320, 482, 30))


# ------------------------------------------------------------------ output

def save(img, name):
    path = os.path.join(ROOT, "assets", "sprites", "player", name + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    print("wrote", os.path.relpath(path, ROOT))


HEROES = {"warrior": warrior, "mage": mage, "rogue": rogue}


def main():
    for name, fn in HEROES.items():
        save(fn(), name)


if __name__ == "__main__":
    main()

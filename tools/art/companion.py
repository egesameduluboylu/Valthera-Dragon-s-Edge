"""Companion dragon sprites (docs/15): the player's pet dragon in three bloodlines and three growth stages,
plus the nest the egg hatches in.

    python3 tools/art/companion.py

writes assets/sprites/companion/{fire,frost,venom}_{hatchling,young,adult}.png and egg_nest.png /
egg_nest_cracked.png (all 256 x 256). The companion fights beside the player, so unlike the enemies it
faces right. Each stage is one body design; the bloodlines recolour it and add their own details (ember
sparks, ice crystals, glowing venom spots and drips).
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

from PIL import ImageChops, ImageFilter  # noqa: E402

from characters import (DARK, NOLINE, WHITE, _painter, along, curve, drop, ember, flame,  # noqa: E402
                        scale_rows, shard, snow, snowflake, taper, wing)
from painter import SS, hexc, light_tone, shade  # noqa: E402

SIZE = 256

# the egg's own colours, reused for the bits of shell the hatchling still wears
EGG_GOLD = hexc("#e8b44a")
EGG_TEAL = hexc("#2aa89a")
EGG_INK = hexc("#0e3a36")

PALETTES = {
    "fire": dict(
        body=hexc("#e8582c"), belly=hexc("#ffc65a"), mem=hexc("#c8382c"), edge=hexc("#ffb45a"),
        horn=hexc("#ffe2a0"), spike=hexc("#ffc24a"), iris=hexc("#36b85a"), claw=hexc("#fff0d0"),
        mouth=hexc("#6a1a1e"), glow=hexc("#ff8a2a"), blush=hexc("#ff7a8a", 120)),
    "frost": dict(
        body=hexc("#a6cff0"), belly=hexc("#f2faff"), mem=hexc("#5a98e0"), edge=hexc("#effbff"),
        horn=hexc("#d2f4ff"), spike=hexc("#c4efff"), iris=hexc("#2a7ee0"), claw=hexc("#ffffff"),
        mouth=hexc("#2a3a6a"), glow=hexc("#7ad8ff"), blush=hexc("#ff9ab8", 110)),
    "venom": dict(
        body=hexc("#62b04c"), belly=hexc("#e2f0a2"), mem=hexc("#8448b8"), edge=hexc("#d4a8ff"),
        horn=hexc("#b784e8"), spike=hexc("#8a4ac4"), iris=hexc("#a64ae0"), claw=hexc("#f4f0e0"),
        mouth=hexc("#3a1440"), glow=hexc("#b8ff4a"), blush=hexc("#ffa0d8", 130)),
}
ELEMENTS = ("fire", "frost", "venom")
STAGES = ("hatchling", "young", "adult")


# ------------------------------------------------------------------ scaled drawing

class Scaled:
    """Stands in for a Painter but maps every coordinate through (x, y) -> (ox + x * k, oy + y * k), so a
    stage can be designed on a roomy grid and fitted to its share of the canvas. Ink line weights stay as
    they are, so every stage has the same crisp outline."""

    def __init__(self, p, k, ox, oy):
        self.p, self.k, self.ox, self.oy = p, k, ox, oy

    def pt(self, x, y):
        return (self.ox + x * self.k, self.oy + y * self.k)

    def _pts(self, kind, pts):
        if isinstance(pts[0], (tuple, list)):
            return [self.pt(x, y) for x, y in pts]
        out = []
        for i in range(0, len(pts), 2):
            out += list(self.pt(pts[i], pts[i + 1]))
        return out

    def _kw(self, kw):
        kw = dict(kw)
        for key in ("width", "radius"):
            if key in kw:
                kw[key] = kw[key] * self.k
        return kw

    def shape(self, kind, pts, color, **kw):
        return self.p.shape(kind, self._pts(kind, pts), color, **self._kw(kw))

    def flat(self, kind, pts, color, **kw):
        return self.p.flat(kind, self._pts(kind, pts), color, **self._kw(kw))

    def _mask(self, kind, pts, **kw):
        return self.p._mask(kind, self._pts(kind, pts), **self._kw(kw))

    def union(self, items):
        return self.p.union([(it[0], self._pts(it[0], it[1])) + ((self._kw(it[2]),) if len(it) > 2 else ())
                             for it in items])

    def paint_mask(self, m, color, **kw):
        return self.p.paint_mask(m, color, **kw)

    def stroke(self, pts, color, width, soft=0.0):
        return self.p.stroke(self._pts("line", pts), color, max(0.8, width * self.k), soft)

    def glow(self, center, radius, color, strength=0.8):
        return self.p.glow(self.pt(*center), radius * self.k, color, strength)

    def sparkle(self, center, r, color=WHITE, glow=True):
        return self.p.sparkle(self.pt(*center), r * self.k, color, glow)

    def tex(self, mask, kind, amount=1.0, color=(128, 128, 128, 255)):
        return self.p.tex(mask, kind, amount, color)

    def shadow_on(self, mask, strength=0.35, offset=2.0, blur=3.0, color=(18, 10, 30, 255)):
        return self.p.shadow_on(mask, strength, offset * self.k, blur * self.k, color)


def fitted(k, cx=128, ground=244):
    """A painter plus a Scaled view of it that maps the design grid (centre x 128, ground y 244) to scale k."""
    p = _painter(SIZE)
    return p, Scaled(p, k, cx - cx * k, ground - ground * k)


# ------------------------------------------------------------------ shared parts

def cute_eye(p, cx, cy, rx, ry, iris, look=(0.3, -0.12), lash=2.0, side=1):
    """Big friendly cartoon eye: a tall white, a large glossy iris, a round pupil and two bright catchlights,
    with a lid line hugging the top that flicks up at the outer corner (`side` 1 = right, -1 = left).
    No brows, nothing angry."""
    white = p.shape("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry), hexc("#fdfbf6"), shadow=0.84, light=0,
                    depth=0.22, line=1.1, rim=0, ao=0.2)
    ix, iy = cx + look[0] * rx * 0.5, cy + look[1] * ry * 0.5 + ry * 0.06
    irx, iry = rx * 0.74, ry * 0.76
    p.shape("ellipse", (ix - irx, iy - iry, ix + irx, iy + iry), iris, shadow=0.55, light=1.5, depth=0.28,
            line=0.9, ink=shade(iris, 0.35), rim=0, ao=0, clip=white)
    # a lighter crescent toward the bottom of the iris, as if light shines through it
    p.shape("chord", (ix - irx * 0.8, iy - iry * 0.3, ix + irx * 0.8, iy + iry * 0.92), shade(iris, 1.45),
            start=0, end=180, clip=white, **NOLINE)
    pr = irx * 0.5
    p.flat("ellipse", (ix - pr, iy - pr * 1.12, ix + pr, iy + pr * 1.12), DARK)
    p.flat("ellipse", (ix - irx * 0.72, iy - iry * 0.78, ix - irx * 0.02, iy - iry * 0.08), WHITE)
    p.flat("ellipse", (ix + irx * 0.2, iy + iry * 0.28, ix + irx * 0.52, iy + iry * 0.58), hexc("#ffffff", 210))
    # upper lid: along the top of the eye, thickest in the middle, with a little upward flick outside
    t0, t1 = (200, 338) if side > 0 else (202, 340)
    arc = [(cx + (rx + 0.2) * math.cos(math.radians(t)), cy + (ry + 0.2) * math.sin(math.radians(t)))
           for t in range(t0, t1 + 1, 8)]
    p.stroke(arc, DARK, lash)
    p.stroke(arc[3:-3], DARK, lash * 1.35)
    ex, ey = arc[-1] if side > 0 else arc[0]
    p.stroke([(ex, ey), (ex + side * lash * 1.8, ey - lash * 1.3)], DARK, lash * 0.85)
    return white


def soft_line(p, pts, color, width, blur, clip):
    """A blurred line kept inside `clip` (shading painted onto a surface, never spilling past its edge)."""
    base = p.p if isinstance(p, Scaled) else p
    m = p._mask("line", pts, width=width)
    m = ImageChops.multiply(m.filter(ImageFilter.GaussianBlur(blur * SS * (p.k if isinstance(p, Scaled) else 1))),
                            clip)
    base._fill(m, color, solid=False)


def dragon_wing(p, shoulder, elbow, wrist, fingers, membrane, bone_c, width=10, edge=None, scallop=0.24,
                attach=None, thumb=None):
    """Dragon wing with a bent arm (shoulder, elbow, wrist), gently bowed finger bones fanning out from the wrist
    and a scalloped membrane between them, ending at `attach` on the body."""
    attach = attach or (shoulder[0] - (shoulder[0] - fingers[-1][0]) * 0.25, shoulder[1] + 6)
    edge_pts = [fingers[0]]
    prev = fingers[0]
    for f in fingers[1:]:
        mx, my = (prev[0] + f[0]) / 2, (prev[1] + f[1]) / 2
        edge_pts += [(mx + (wrist[0] - mx) * scallop, my + (wrist[1] - my) * scallop), f]
        prev = f
    last = fingers[-1]
    lx, ly = (last[0] + attach[0]) / 2, (last[1] + attach[1]) / 2
    tail_edge = [last, (lx + (wrist[0] - lx) * scallop * 0.8, ly + (wrist[1] - ly) * scallop * 0.8), attach]
    mem = p._mask("poly", [elbow, wrist] + curve(edge_pts, 6) + curve(tail_edge, 6)[1:] + [shoulder])
    p.paint_mask(mem, membrane, depth=0.08, light=1.25, tex="leather", tex_amt=0.45)
    # the membrane dips between the fingers: a soft shadow along each bone, a sheen in each panel
    shadow_c = shade(membrane, 0.62)[:3] + (120,)
    for f in fingers + [attach]:
        soft_line(p, [wrist, f], shadow_c, width * 1.1, 2.2, mem)
    for f0, f1 in zip(fingers, fingers[1:]):
        mx, my = (wrist[0] + (f0[0] + f1[0]) / 2) / 2, (wrist[1] + (f0[1] + f1[1]) / 2) / 2
        soft_line(p, [(mx + (wrist[0] - mx) * 0.3, my + (wrist[1] - my) * 0.3), (mx, my)],
                  light_tone(membrane, 1.35)[:3] + (80,), width * 0.9, 2.6, mem)
    if edge:
        p.stroke(curve(edge_pts, 6) + curve(tail_edge, 6)[1:], edge, 2.2)

    def bow(a, b, k=0.08):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = b[0] - a[0], b[1] - a[1]
        return curve([a, (mx - dy * k, my + dx * k), b], 5)
    for f in fingers:
        p.shape("poly", taper(bow(wrist, f), width * 0.55, width * 0.22, 1), bone_c, depth=0.3, line=1.1, rim=0)
    p.shape("poly", taper([shoulder, elbow], width * 1.25, width * 0.9, 1), bone_c, depth=0.3, light=1.3, rim=0.3)
    p.shape("poly", taper([elbow, wrist], width * 0.95, width * 0.7, 1), bone_c, depth=0.3, light=1.3, rim=0.3)
    for (x, y), r in ((elbow, width * 0.55), (wrist, width * 0.52)):
        p.shape("ellipse", (x - r, y - r, x + r, y + r), bone_c, depth=0.3, line=1.1, rim=0)
    # the thumb claw on the wrist
    dx, dy = wrist[0] - elbow[0], wrist[1] - elbow[1]
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    if thumb:  # a crystal instead of a claw
        shard(p, wrist[0] + ux * width * 0.8, wrist[1] + uy * width * 0.8, width * 0.8, width * 2.0,
              math.degrees(math.atan2(uy, ux)) + 90, thumb, line=1.0)
        return mem
    p.shape("poly", [(wrist[0] - uy * width * 0.3, wrist[1] + ux * width * 0.3),
                     (wrist[0] + uy * width * 0.3, wrist[1] - ux * width * 0.3),
                     (wrist[0] + ux * width * 1.4 - uy * width * 0.2, wrist[1] + uy * width * 1.4 + ux * width * 0.2)],
            hexc("#fff4dc"), line=1.0, rim=0, ao=0)
    return mem


def neck_spikes(p, el, pal, pts, w, step, h, side=1, skip=1, count=4, lean=-0.5, drips=()):
    """Spikes along the back edge of a tapered neck or tail (side 1 = left of the direction of travel)."""
    c = curve(pts, 8)
    marks = along(c, step)[skip:skip + count]
    for k, (x, y) in enumerate(marks):
        i = min(range(len(c)), key=lambda j: (c[j][0] - x) ** 2 + (c[j][1] - y) ** 2)
        a, b = c[max(0, i - 1)], c[min(len(c) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = dy / n * side, -dx / n * side
        t = i / max(1, len(c) - 1)
        half = (w[0] + (w[1] - w[0]) * t) / 2 - 3
        ang = math.degrees(math.atan2(ny + dy / n * lean, nx + dx / n * lean))
        spike(p, el, pal, x + nx * half, y + ny * half, h, ang, drip=k in drips)


def claws(p, pts, color, size=4.0):
    """Little rounded toe claws; pts are (x, y) of each claw's base, pointing down-right."""
    for x, y in pts:
        p.shape("poly", curve([(x - size * 0.6, y), (x + size * 0.6, y), (x + size * 0.5, y + size * 0.9),
                               (x + size * 0.1, y + size * 1.3)], 3) + [(x - size * 0.5, y + size * 0.4)], color,
                depth=0.3, light=1.3, line=0.9, rim=0, ao=0.2)


def spike(p, el, pal, x, y, h, angle, w=None, drip=False):
    """One back or tail spike standing on (x, y), pointing along `angle` (degrees, 0 = right, -90 = up)."""
    w = w or h * 0.62
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    if el == "frost":
        shard(p, x + ux * h * 0.42, y + uy * h * 0.42, w * 0.8, h, angle + 90, pal["spike"], line=1.1)
        return
    tip = (x + ux * h, y + uy * h)
    pts = curve([(x + nx * w / 2, y + ny * w / 2), (x + ux * h * 0.45 + nx * w * 0.3, y + uy * h * 0.45 + ny * w * 0.3),
                 tip, (x + ux * h * 0.4 - nx * w * 0.16, y + uy * h * 0.4 - ny * w * 0.16),
                 (x - nx * w / 2, y - ny * w / 2)], 4)
    p.shape("poly", pts, pal["spike"], depth=0.3, light=1.35, line=1.1, rim=0, ao=0.25, spec=0.4)
    if el == "venom":
        p.glow(tip, h * 0.55, pal["glow"], 0.55)
        p.flat("ellipse", (tip[0] - h * 0.1 - 0.6, tip[1] - h * 0.1 - 0.6, tip[0] + h * 0.1 + 0.6,
                           tip[1] + h * 0.1 + 0.6), hexc("#e8ffb0"))
        if drip:
            drop(p, tip[0] - 1, tip[1] + h * 0.55, max(2.0, h * 0.15), hexc("#b8ff6a", 235), line=0.9)


def horn(p, pal, pts, w, el, far=False):
    col = shade(pal["horn"], 0.86) if far else pal["horn"]
    if el == "frost":
        p.glow(pts[-1], w * 1.1, pal["glow"], 0.45)
        p.shape("poly", taper(pts, w, 1.5), col, depth=0.25, light=1.45, spec=0.9, line=1.2, ink=hexc("#2a4a7a"),
                rim=0)
        return
    p.shape("poly", taper(pts, w, 1.5), col, depth=0.25, light=1.3, spec=0.5, tex="bone", tex_amt=0.6)
    for x, y in along(curve(pts, 6), w * 0.55)[1:-1]:
        p.stroke([(x - w * 0.18, y - w * 0.22), (x + w * 0.18, y + w * 0.22)], shade(col, 0.72), 1.2)


def venom_spots(p, pal, spots, clip):
    for x, y, r in spots:
        p.glow((x, y), r * 2.6, pal["glow"], 0.45)
        p.shape("ellipse", (x - r, y - r * 0.85, x + r, y + r * 0.85), hexc("#c4ff5a"), depth=0.3, light=1.45,
                line=0.9, ink=hexc("#2a6a1a"), rim=0, ao=0, clip=clip)
        p.flat("ellipse", (x - r * 0.5, y - r * 0.5, x - r * 0.05, y - r * 0.1), hexc("#f4ffd8"))


def frost_marks(p, pal, marks):
    """Pale frost swirls on the scales."""
    for pts in marks:
        p.stroke(curve(pts, 4), hexc("#ffffff", 190), 2.2)


def fx(p, el, spots):
    """Floating element sparkles: embers, snowflakes, or glowing venom bubbles and falling drips;
    spots are (x, y, r)."""
    for i, (x, y, r) in enumerate(spots):
        if el == "fire":
            ember(p, x, y, r)
        elif el == "frost":
            if i % 2:
                snow(p, x, y, r)
            else:
                snowflake(p, x, y, r * 2.4)
        elif i % 2:
            p.glow((x, y), r * 3.4, hexc("#9aff4a"), 0.5)
            drop(p, x, y, r * 1.35, hexc("#b8ff6a", 240), line=0.9)
        else:
            p.glow((x, y), r * 3.2, hexc("#9aff4a"), 0.55)
            p.shape("ellipse", (x - r * 1.3, y - r * 1.3, x + r * 1.3, y + r * 1.3), hexc("#d0ff8a", 170),
                    shadow=0, light=0, line=0.9, ink=hexc("#3a8a2a", 200), rim=0, ao=0)
            p.flat("ellipse", (x - r * 0.8, y - r * 0.8, x - r * 0.1, y - r * 0.2), hexc("#ffffff", 230))


def tail_tip(p, el, pal, x, y, s, angle):
    """Tail tip: a little flame (fire), a crystal (frost) or a dripping barb (venom), pointing along `angle`."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    if el == "frost":
        shard(p, x + ux * s * 0.7, y + uy * s * 0.7, s * 0.9, s * 2.0, angle + 90, pal["spike"], glow=pal["glow"])
        return
    if el == "fire":  # a little flame burning on the tip of the tail
        flame(p, x + ux * s * 0.2, y + uy * s * 0.2 + s * 0.5, s * 1.9, s * 3.4, lean=-0.15, strength=0.6)
        return
    s *= 1.3
    col = pal["spike"]
    pts = [(x - ux * s * 0.2, y - uy * s * 0.2), (x + nx * s * 0.8 + ux * s * 0.3, y + ny * s * 0.8 + uy * s * 0.3),
           (x + ux * s * 1.6, y + uy * s * 1.6), (x - nx * s * 0.8 + ux * s * 0.3, y - ny * s * 0.8 + uy * s * 0.3)]
    p.shape("poly", pts, col, depth=0.3, light=1.35, line=1.2, rim=0, spec=0.4)
    tip = pts[2]
    p.glow(tip, s * 1.1, pal["glow"], 0.6)
    p.flat("ellipse", (tip[0] - 1.6, tip[1] - 1.6, tip[0] + 1.6, tip[1] + 1.6), hexc("#e8ffb0"))
    cx, cy = max((pts[1], pts[3]), key=lambda q: q[1])  # a venom drip hanging from the lower barb
    drop(p, cx, cy + s * 0.95, max(2.2, s * 0.24), hexc("#b8ff6a", 235), line=0.9)


def _egg_flecks(p, clip, flecks):
    for x, y, r in flecks:
        p.shape("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8), EGG_TEAL, depth=0.3, light=1.35, line=0.8,
                rim=0, ao=0, clip=clip, ink=EGG_INK)


def shell_piece(p, pts, fleck=None):
    """A broken shard of eggshell lying on the ground: gold outside, the pale inner edge along its top."""
    m = p.shape("poly", pts, EGG_GOLD, depth=0.3, light=1.4, spec=0.8, tex="leather", tex_amt=0.5, line=1.3)
    p.stroke(pts[:3], hexc("#fff4d6"), 1.8)
    if fleck:
        _egg_flecks(p, m, [fleck])
    return m


def eggshell_cap(p, cx, cy, w, h, tilt=-14):
    """Top of the eggshell perched on the hatchling's head like a little helmet, zigzag rim below."""
    a = math.radians(tilt)
    ca, sa = math.cos(a), math.sin(a)

    def rot(x, y):
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)
    dome = [rot(w / 2 * math.cos(math.radians(t)) * (1 - 0.1 * math.sin(math.radians(t)) ** 4),
                -h * math.sin(math.radians(t))) for t in range(0, 181, 8)]
    n = 7
    zig = [rot(-w / 2 + w * i / n, h * (0.2 if i % 2 else 0.0) + (h * 0.06 if i == 3 else 0)) for i in range(n + 1)]
    # the inside of the shell shows as a pale sliver under the zigzag
    inner = [rot(-w / 2 + w * i / n, h * (0.2 if i % 2 else 0.0) + h * 0.14) for i in range(n + 1)]
    p.shape("poly", zig + inner[::-1], hexc("#fff2cf"), depth=0.3, light=1.2, line=1.2, rim=0, ao=0.3)
    m = p.shape("poly", dome + zig, EGG_GOLD, depth=0.22, light=1.4, spec=0.9, tex="leather", tex_amt=0.5,
                line=1.5)
    fl = []
    for fx_, fy, r in ((-0.24, -0.5, 0.075), (0.14, -0.74, 0.06), (0.3, -0.34, 0.055), (-0.04, -0.3, 0.05),
                       (-0.36, -0.2, 0.04)):
        x, y = rot(fx_ * w, fy * h)
        fl.append((x, y, r * w))
    _egg_flecks(p, m, fl)
    for fx_, fy in ((0.02, -0.55), (0.26, -0.62), (-0.12, -0.84)):
        x, y = rot(fx_ * w, fy * h)
        p.flat("ellipse", (x - 1.1, y - 1.1, x + 1.1, y + 1.1), hexc("#7a4a1a"))
    x0, y0 = rot(-w * 0.26, -h * 0.8)
    x1, y1 = rot(-w * 0.38, -h * 0.42)
    p.stroke([(x0, y0), (x1, y1)], hexc("#ffffff", 180), 2.6)
    return m


# ------------------------------------------------------------------ stages

def happy_mouth(p, pal, pts_top, pts_bottom, tongue, fang=None):
    """Open smile: a dark mouth between the two curves, a pink tongue, and optionally a tiny fang."""
    m = p.shape("poly", curve(pts_top, 5) + curve(pts_bottom[::-1], 5), pal["mouth"], depth=0.3, line=1.3,
                rim=0, ao=0)
    tx, ty, tr = tongue
    p.shape("ellipse", (tx - tr, ty - tr * 0.6, tx + tr, ty + tr * 0.9), hexc("#ff7f96"), depth=0.3, light=1.3,
            line=0, rim=0, ao=0, clip=m)
    if fang:
        x, y, s = fang
        p.shape("poly", [(x - s * 0.5, y), (x + s * 0.5, y), (x, y + s * 1.2)], hexc("#fffaf0"), depth=0.25,
                light=1.2, line=0.8, rim=0, ao=0)
    return m


def hatchling(el):
    """Tiny round hatchling with a big head, stubby wings and the top of its eggshell still on its head."""
    pal = PALETTES[el]
    body = pal["body"]
    base, p = fitted(0.86, 132)
    p.glow((140, 170), 100, pal["glow"], {"fire": 0.16, "frost": 0.2, "venom": 0.13}[el])
    # ---- far wing, far foot, tail
    wing(p, (110, 168), [(88, 140), (66, 126), (58, 148), (74, 166)], shade(pal["mem"], 0.8), shade(body, 0.8),
         width=6, scallop=0.25)
    p.shape("ellipse", (140, 222, 174, 242), shade(body, 0.8), depth=0.25, tex="leather", tex_amt=0.5)
    claws(p, [(160, 236), (167, 236)], pal["claw"], 3.4)
    tail = [(100, 222), (72, 232), (50, 224), (42, 206)]
    p.shape("poly", taper(tail, 28, 10), body, depth=0.2, tex="leather", tex_amt=0.5)
    tail_tip(p, el, pal, 42, 206, 8, -100)
    # ---- back spikes then the round body
    for t in (198, 220, 242):
        a = math.radians(t)
        spike(p, el, pal, 122 + 44 * math.cos(a), 198 + 40 * math.sin(a), 13, t, drip=t == 198)
    bm = p.shape("ellipse", (76, 156, 170, 240), body, depth=0.14, tex="leather", tex_amt=0.5)
    p.shape("ellipse", (110, 176, 172, 240), pal["belly"], depth=0.18, line=1.2, rim=0, clip=bm, tex="leather",
            tex_amt=0.35)
    for y in (198, 210, 222):
        p.stroke(curve([(118, y), (140, y + 3), (166, y)], 4), shade(pal["belly"], 0.76), 1.5)
    if el == "venom":
        venom_spots(p, pal, [(90, 198, 5), (98, 216, 4), (86, 180, 3.5)], bm)
    elif el == "frost":
        frost_marks(p, pal, [[(86, 190), (94, 200), (90, 212)]])
    # ---- near wing: small and stubby
    wing(p, (114, 178), [(92, 150), (66, 140), (62, 164), (80, 180)], pal["mem"], body, width=7,
         edge=pal["edge"], scallop=0.25)
    # ---- near foot and a little paw raised at the chest
    p.shape("ellipse", (98, 220, 142, 244), body, depth=0.25, tex="leather", tex_amt=0.5)
    claws(p, [(124, 238), (131, 238), (138, 237)], pal["claw"], 3.6)
    p.shape("ellipse", (146, 196, 170, 214), body, depth=0.3, tex="leather", tex_amt=0.4)
    claws(p, [(162, 206), (167, 203)], pal["claw"], 3.0)
    # ---- head: ear frill, cranium and muzzle, cheeks, big eyes, happy open smile
    p.shape("poly", curve([(112, 126), (82, 112), (92, 132), (78, 146), (108, 152)], 3), shade(pal["mem"], 0.95),
            depth=0.3, light=1.3, line=1.2, rim=0)
    head = p.union([("ellipse", (98, 100, 196, 192)), ("ellipse", (154, 134, 220, 186))])
    p.paint_mask(head, body, depth=0.12, tex="leather", tex_amt=0.45, rim=0.4)
    p.shape("chord", (130, 154, 222, 204), pal["belly"], start=0, end=180, depth=0.2, line=1.1, rim=0, clip=head)
    if el == "venom":
        venom_spots(p, pal, [(110, 138, 4), (116, 160, 3), (104, 122, 3)], head)
    elif el == "frost":
        frost_marks(p, pal, [[(106, 134), (114, 144), (110, 156)]])
    horn(p, pal, [(122, 116), (108, 102), (98, 98)], 10, el, far=True)
    eggshell_cap(p, 138, 110, 70, 34, tilt=-16)
    cute_eye(p, 176, 139, 14, 18, pal["iris"])
    cute_eye(p, 138, 139, 12, 16.5, pal["iris"], side=-1)
    p.flat("ellipse", (184, 160, 200, 168), pal["blush"])
    p.flat("ellipse", (118, 158, 132, 166), pal["blush"])
    happy_mouth(p, pal, [(170, 170), (190, 174), (214, 166)], [(170, 170), (184, 186), (202, 184), (214, 166)],
                (192, 184, 9))
    for x, y in ((206, 150), (214, 147)):
        p.flat("ellipse", (x - 2, y - 1.6, x + 2, y + 1.6), shade(pal["mouth"], 0.9))
    # ---- bits of shell on the ground
    shell_piece(p, [(58, 236), (64, 226), (74, 230), (82, 224), (86, 238), (72, 243)], (72, 236, 2.6))
    shell_piece(p, [(186, 240), (190, 231), (199, 235), (206, 230), (208, 242)])
    fx(p, el, [(212, 102, 2.4), (60, 104, 2.2), (228, 204, 2.0), (34, 160, 2.0), (196, 76, 1.8)])
    return base.finish(outline=3, ground_shadow=(64, 228, 208, 250))


def limb(p, color, upper, top, knee, foot, w0, w1, paw, claw_c, claw_x, claw_y, claw_s=3.8, tex_amt=0.5):
    """A whole leg as one shape: the thigh or shoulder (an ellipse box) merged with a tapered shin, then a round
    paw with little claws. `upper` may be None for a plain leg."""
    items = [("poly", taper([top, knee, foot], w0, w1, 6))]
    if upper:
        items.append(("ellipse", upper))
    m = p.paint_mask(p.union(items), color, depth=0.14, tex="leather", tex_amt=tex_amt)
    p.shape("ellipse", paw, color, depth=0.25, tex="leather", tex_amt=tex_amt * 0.8)
    claws(p, [(x, claw_y) for x in claw_x], claw_c, claw_s)
    return m


def young(el):
    """Young dragon on all fours: longer neck, proper half-raised wings, small horns, still big-eyed."""
    pal = PALETTES[el]
    body = pal["body"]
    far = shade(body, 0.8)
    base, p = fitted(0.9, 124)
    p.glow((130, 140), 130, pal["glow"], {"fire": 0.15, "frost": 0.18, "venom": 0.12}[el])
    # ---- far wing peeking over the back
    dragon_wing(p, (128, 146), (140, 110), (116, 70), [(86, 38), (60, 60), (66, 98), (94, 128)],
                shade(pal["mem"], 0.8), far, width=8)
    # ---- tail sweeping back with spikes along the top
    tail = [(80, 190), (48, 210), (22, 206), (8, 184)]
    neck_spikes(p, el, pal, tail, (36, 10), 15, 13, side=-1, skip=1, count=3, lean=0.4)
    p.shape("poly", taper(tail, 36, 10), body, depth=0.18, tex="leather", tex_amt=0.5)
    tail_tip(p, el, pal, 8, 184, 9, -100)
    # ---- far legs
    claw_f = shade(pal["claw"], 0.9)
    limb(p, far, None, (104, 196), (104, 220), (100, 232), 26, 18, (84, 224, 116, 244), claw_f, (104, 110), 239, 3.4)
    limb(p, far, None, (178, 182), (186, 212), (190, 228), 24, 18, (176, 220, 208, 240), claw_f, (198, 204), 235,
         3.4)
    # ---- neck spikes, neck, body (a pear shape: chest raised, rump low)
    neck = [(150, 172), (168, 138), (182, 112), (190, 98)]
    neck_spikes(p, el, pal, neck, (56, 40), 12, 17, skip=3, count=3, drips=(1,))
    p.shape("poly", taper(neck, 56, 40), body, depth=0.16, tex="leather", tex_amt=0.5)
    bm = p.union([("ellipse", (62, 150, 150, 218)), ("ellipse", (104, 128, 192, 210))])
    p.paint_mask(bm, body, depth=0.12, tex="leather", tex_amt=0.5)
    scale_rows(p, bm, (70, 128, 190, 168), shade(body, 1.07), size=11, line=0.6)
    p.shape("ellipse", (98, 172, 204, 240), pal["belly"], depth=0.2, line=1.2, rim=0, clip=bm, tex="leather",
            tex_amt=0.35)
    for x in range(114, 180, 12):
        p.stroke([(x - 2, 186 + abs(x - 150) * 0.2), (x, 206 - abs(x - 150) * 0.05)], shade(pal["belly"], 0.76), 1.5)
    # throat plates up the front of the neck
    p.shape("poly", taper([(170, 176), (182, 146), (194, 120), (200, 106)], 22, 14), pal["belly"], depth=0.2,
            line=1.1, rim=0, tex="leather", tex_amt=0.3)
    for x, y in along(curve([(174, 168), (186, 142), (196, 120)], 5), 9)[1:]:
        p.stroke([(x - 7, y - 3), (x + 7, y + 2)], shade(pal["belly"], 0.76), 1.4)
    if el == "venom":
        venom_spots(p, pal, [(150, 150, 4), (168, 142, 3.5)], bm)
    # ---- near wing, half raised
    dragon_wing(p, (112, 160), (126, 122), (96, 78), [(52, 46), (22, 82), (26, 122), (60, 148)], pal["mem"],
                body, width=10, edge=pal["edge"], thumb=pal["spike"] if el == "frost" else None)
    # ---- near hind leg (big haunch) and near front leg
    haunch = limb(p, body, (54, 156, 120, 216), (84, 204), (78, 224), (80, 234), 28, 20, (60, 226, 106, 246),
                  pal["claw"], (88, 95, 102), 241)
    if el == "venom":
        venom_spots(p, pal, [(74, 176, 5), (92, 170, 3.5), (66, 196, 3.5)], haunch)
    elif el == "frost":
        frost_marks(p, pal, [[(66, 180), (76, 170), (92, 168)]])
    limb(p, body, (146, 158, 184, 198), (164, 186), (168, 214), (166, 230), 28, 20, (146, 224, 186, 246),
         pal["claw"], (170, 177, 184), 241)
    # ---- head: frill, horns, cranium and muzzle, big friendly eyes, grin
    p.shape("poly", curve([(170, 84), (146, 76), (156, 90), (146, 102), (168, 106)], 3), shade(pal["mem"], 0.95),
            depth=0.3, light=1.3, line=1.2, rim=0)
    horn(p, pal, [(178, 70), (164, 50), (146, 42)], 12, el, far=True)
    head = p.union([("ellipse", (156, 52, 228, 122)), ("ellipse", (190, 80, 248, 122))])
    p.paint_mask(head, body, depth=0.12, tex="leather", tex_amt=0.45, rim=0.4)
    p.shape("chord", (170, 98, 250, 136), pal["belly"], start=0, end=180, depth=0.2, line=1.1, rim=0, clip=head)
    horn(p, pal, [(198, 64), (188, 44), (172, 30)], 13, el)
    cute_eye(p, 214, 86, 11, 14, pal["iris"], lash=1.9)
    cute_eye(p, 182, 86, 9.5, 13, pal["iris"], lash=1.9, side=-1)
    p.flat("ellipse", (216, 102, 230, 108), pal["blush"])
    p.flat("ellipse", (166, 100, 178, 106), pal["blush"])
    happy_mouth(p, pal, [(208, 112), (226, 114), (246, 106)], [(208, 112), (220, 124), (238, 120), (246, 106)],
                (227, 122, 7), fang=(238, 111, 3.5))
    for x, y in ((238, 94), (245, 92)):
        p.flat("ellipse", (x - 1.8, y - 1.4, x + 1.8, y + 1.4), shade(pal["mouth"], 0.9))
    fx(p, el, [(236, 40, 2.4), (20, 60, 2.2), (240, 170, 2.0), (26, 140, 1.8), (130, 30, 1.8), (222, 216, 1.8)])
    return base.finish(outline=3, ground_shadow=(36, 226, 228, 252))


def adult(el):
    """Grown dragon: noble and strong, wings spread wide, long horns, head held high and one forepaw raised,
    still with a kind face."""
    pal = PALETTES[el]
    body = pal["body"]
    far = shade(body, 0.8)
    base, p = fitted(0.96, 175, 250)
    p.glow((128, 120), 150, pal["glow"], {"fire": 0.16, "frost": 0.2, "venom": 0.13}[el])
    # ---- far wing, spread up behind the shoulders
    dragon_wing(p, (148, 126), (174, 88), (160, 30), [(136, 4), (110, 16), (102, 56), (120, 100)],
                shade(pal["mem"], 0.8), far, width=10)
    # ---- tail sweeping back and curling up at the end
    tail = [(80, 198), (46, 222), (22, 222), (12, 202), (20, 186)]
    neck_spikes(p, el, pal, tail, (44, 12), 16, 15, side=-1, skip=1, count=2, lean=0.4)
    p.shape("poly", taper(tail, 44, 11), body, depth=0.18, tex="leather", tex_amt=0.5)
    tail_tip(p, el, pal, 21, 186, 10, -70)
    # ---- far legs: hind planted, front raised and curled
    claw_f = shade(pal["claw"], 0.9)
    limb(p, far, None, (108, 200), (108, 226), (104, 236), 30, 20, (86, 228, 122, 248), claw_f, (108, 115), 243, 3.8)
    p.shape("poly", taper([(184, 170), (208, 184), (220, 204)], 28, 20, 6), far, depth=0.18, tex="leather",
            tex_amt=0.5)
    p.shape("ellipse", (206, 196, 234, 218), far, depth=0.25, tex="leather", tex_amt=0.4)
    claws(p, [(218, 214), (225, 213), (231, 210)], claw_f, 3.4)
    # ---- neck spikes, neck, body (deep chest held high)
    neck = [(160, 164), (178, 124), (190, 94), (196, 74)]
    neck_spikes(p, el, pal, neck, (62, 42), 13, 19, skip=3, count=5, drips=(1,))
    p.shape("poly", taper(neck, 62, 42), body, depth=0.16, tex="leather", tex_amt=0.5)
    bm = p.union([("ellipse", (56, 150, 150, 224)), ("ellipse", (100, 114, 204, 208))])
    p.paint_mask(bm, body, depth=0.12, tex="leather", tex_amt=0.5)
    scale_rows(p, bm, (60, 114, 204, 146), shade(body, 1.05), size=11, line=0.55)
    p.shape("ellipse", (96, 170, 212, 250), pal["belly"], depth=0.2, line=1.2, rim=0, clip=bm, tex="leather",
            tex_amt=0.35)
    for x in range(112, 196, 12):
        p.stroke([(x - 2, 184 + abs(x - 154) * 0.2), (x, 206 - abs(x - 154) * 0.05)], shade(pal["belly"], 0.76),
                 1.6)
    p.shape("poly", taper([(178, 172), (192, 134), (202, 104), (206, 86)], 28, 16), pal["belly"], depth=0.2,
            line=1.1, rim=0, tex="leather", tex_amt=0.3)
    for x, y in along(curve([(182, 164), (196, 130), (204, 102)], 5), 9)[1:]:
        p.stroke([(x - 8, y - 3), (x + 8, y + 2)], shade(pal["belly"], 0.76), 1.5)
    if el == "venom":
        venom_spots(p, pal, [(156, 136, 4.5), (174, 126, 3.5), (140, 128, 3.5)], bm)
    # ---- near wing, spread wide and high
    dragon_wing(p, (118, 144), (138, 98), (104, 38), [(52, 6), (14, 34), (4, 86), (18, 128), (62, 148)],
                pal["mem"], body, width=12, edge=pal["edge"], thumb=pal["spike"] if el == "frost" else None)
    # ---- near hind leg and near front leg
    haunch = limb(p, body, (48, 152, 122, 224), (82, 210), (76, 232), (78, 240), 32, 22, (52, 230, 104, 250),
                  pal["claw"], (86, 94, 102), 245, 4.2)
    if el == "venom":
        venom_spots(p, pal, [(66, 174, 5.5), (86, 166, 4), (58, 196, 4), (102, 182, 3)], haunch)
    elif el == "frost":
        frost_marks(p, pal, [[(58, 178), (70, 166), (88, 164)], [(54, 198), (58, 208)]])
    limb(p, body, (146, 146, 194, 200), (170, 186), (174, 220), (172, 234), 32, 22, (150, 228, 196, 250),
         pal["claw"], (178, 186, 194), 245, 4.2)
    # ---- head: frill, horns, cranium and a longer muzzle, jaw spikes, kind eyes, confident smile
    p.shape("poly", curve([(178, 62), (150, 50), (162, 66), (146, 76), (162, 84), (152, 94), (178, 90)], 3),
            shade(pal["mem"], 0.95), depth=0.3, light=1.3, line=1.2, rim=0)
    horn(p, pal, [(182, 44), (166, 24), (146, 14), (128, 14)], 14, el, far=True)
    head = p.union([("ellipse", (170, 30, 226, 88)), ("rect", (194, 50, 252, 88), {"radius": 18}),
                    ("ellipse", (206, 44, 234, 62))])
    p.paint_mask(head, body, depth=0.12, tex="leather", tex_amt=0.45, rim=0.4)
    p.shape("chord", (178, 72, 254, 102), pal["belly"], start=0, end=180, depth=0.2, line=1.1, rim=0, clip=head)
    horn(p, pal, [(202, 40), (190, 18), (172, 6), (152, 4)], 16, el)
    for x, y, h, a in ((176, 78, 15, 168), (180, 88, 12, 156)):
        spike(p, el, pal, x, y, h, a)
    p.stroke(curve([(236, 52), (244, 54), (250, 60)], 3), shade(body, 0.72), 1.6)  # nostril ridge
    cute_eye(p, 216, 60, 8.5, 11, pal["iris"], lash=1.8)
    cute_eye(p, 190, 60, 7.5, 10, pal["iris"], lash=1.8, side=-1)
    p.flat("ellipse", (220, 74, 232, 79), pal["blush"])
    # a warm closed smile with one fang peeking out
    p.stroke(curve([(214, 80), (224, 84.5), (238, 83), (250, 76)], 5), pal["mouth"], 2.2)
    p.stroke(curve([(212, 77), (214, 80), (213, 83)], 3), pal["mouth"], 1.6)
    p.shape("poly", [(236, 83), (241, 82.5), (238.5, 89)], hexc("#fffaf0"), depth=0.25, light=1.2, line=0.8, rim=0,
            ao=0)
    for x, y in ((243, 60), (249, 59)):
        p.flat("ellipse", (x - 1.8, y - 1.4, x + 1.8, y + 1.4), shade(pal["mouth"], 0.9))
    fx(p, el, [(238, 20, 2.4), (246, 140, 2.2), (236, 230, 1.8), (34, 160, 1.8), (80, 6, 1.6)])
    return base.finish(outline=3, ground_shadow=(28, 228, 238, 254))


STAGE_FN = {"hatchling": hatchling, "young": young, "adult": adult}


# ------------------------------------------------------------------ nest

def draw_egg(p, cx, cy, s):
    """The dragon egg (same look as the Ejder Yumurtası item, gear._draw_egg) without its crack, centred on
    (cx, cy); s=1 is 44 x 64."""
    egg = p.union([("ellipse", (cx - 22 * s, cy - 24 * s, cx + 22 * s, cy + 32 * s)),
                   ("ellipse", (cx - 17 * s, cy - 34 * s, cx + 17 * s, cy + 8 * s))])
    p.paint_mask(egg, EGG_GOLD, depth=0.2, light=1.4, spec=1.0, tex="leather", tex_amt=0.5)
    band = ImageChops.multiply(egg, p._mask("ellipse", (cx - 40 * s, cy + 8 * s, cx + 40 * s, cy + 60 * s)))
    p.paint_mask(band, EGG_TEAL, depth=0.25, light=1.35, line=0.9, rim=0, ao=0, ink=EGG_INK)
    for row, y in enumerate((12, 18, 24)):
        for i in range(-3, 4):
            x = i * 7 + (3.5 if row % 2 else 0)
            p.shape("chord", (cx + (x - 4) * s, cy + (y - 3) * s, cx + (x + 4) * s, cy + (y + 5) * s),
                    shade(EGG_TEAL, 1.2), start=0, end=180, depth=0.35, line=0.6, light=1.4, rim=0, ao=0, clip=band,
                    ink=EGG_INK)
    for x, y, rx, ry in ((-9, -14, 2.6, 2.0), (11, -2, 3, 2.4), (-13, 2, 2.4, 2.6), (8, -22, 2, 1.6),
                         (-2, -4, 2, 1.6), (14, -12, 1.8, 2), (-4, -24, 1.8, 1.5)):
        p.shape("ellipse", (cx + (x - rx) * s, cy + (y - ry) * s, cx + (x + rx) * s, cy + (y + ry) * s), EGG_TEAL,
                depth=0.3, light=1.35, line=0.8, rim=0, ao=0, clip=egg, ink=EGG_INK)
    for x, y, r in ((-14, -8, 1.1), (4, -12, 1.0), (14, 4, 1.0), (-6, 2, 0.9), (16, -18, 0.9),
                    (-10, -20, 1.0), (6, 2, 0.9), (-16, 6, 0.8)):
        p.flat("ellipse", (cx + (x - r) * s, cy + (y - r) * s, cx + (x + r) * s, cy + (y + r) * s), hexc("#7a4a1a"))
    p.stroke([(cx - 12 * s, cy - 16 * s), (cx - 16 * s, cy - 4 * s)], hexc("#ffffff", 170), 2.2 * s)
    return egg


def glowing_crack(p, pts, width=2.6, glow=True):
    """A crack in the shell with warm light leaking out of it."""
    pts = curve(pts, 3) if len(pts) > 2 else pts
    if glow:
        for x, y in along(pts, 6):
            p.glow((x, y), width * 4.2, hexc("#ffc850"), 0.42)
    p.stroke(pts, hexc("#3a1a0a"), width)
    p.stroke(pts, hexc("#ffe890"), width * 0.52)
    p.stroke(pts, hexc("#fffbe6"), max(0.8, width * 0.22))


def _straw(p, rng, clip_box, cx, cy, rx, ry, a0, a1, n, jitter, colors, length=(20, 38), spread=0.45,
           width=(1.5, 2.3)):
    """Straw strands laid roughly along an elliptical ring, each with a darker edge so it reads as a stalk."""
    x0, y0, x1, y1 = clip_box
    for _ in range(n):
        a = rng.uniform(a0, a1)
        x = cx + rx * math.cos(a) + rng.uniform(-jitter, jitter)
        y = cy + ry * math.sin(a) + rng.uniform(-jitter * 0.7, jitter * 0.7)
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        t = math.atan2(ry * math.cos(a), -rx * math.sin(a)) + rng.uniform(-spread, spread)
        ln = rng.uniform(*length)
        dx, dy = math.cos(t) * ln / 2, math.sin(t) * ln / 2
        bend = rng.uniform(-2.5, 2.5)
        pts = curve([(x - dx, y - dy), (x - dy * 0.1 * bend, y + dx * 0.1 * bend), (x + dx, y + dy)], 4)
        w = rng.uniform(*width)
        col = rng.choice(colors)
        p.stroke(pts, shade(col, 0.5)[:3] + (220,), w + 1.4)
        p.stroke(pts, col, w)
        p.stroke(pts[:len(pts) // 2 + 1], shade(col, 1.25), max(0.8, w * 0.35))


def egg_nest(cracked=False):
    """The dragon egg resting in a straw nest with a warm glow; `cracked` adds glowing cracks for the moment
    it is ready to hatch."""
    rng = random.Random(21)
    p = _painter(SIZE)
    straw = hexc("#d9a64c")
    cols = [hexc("#f6d98a"), hexc("#ecc064"), hexc("#dca54a"), hexc("#c48a36"), hexc("#fbe6a6"), hexc("#e2b056")]
    p.glow((128, 140), 128, hexc("#ffa040"), 0.52 if cracked else 0.42)
    p.glow((128, 120), 78, hexc("#fff0b0"), 0.55 if cracked else 0.35)
    cx = 128
    # ---- back half of the nest: a lumpy ring of straw behind the egg
    back = p.union([("ellipse", (cx - 104, 160, cx + 104, 214))] +
                   [("ellipse", (cx + 96 * math.cos(a) - 17, 184 + 22 * math.sin(a) - 15,
                                 cx + 96 * math.cos(a) + 17, 184 + 22 * math.sin(a) + 15))
                    for a in [math.pi + i * math.pi / 10 for i in range(11)]])
    p.paint_mask(back, shade(straw, 0.8), depth=0.2, tex="wood_h", tex_amt=0.9, line=1.8)
    _straw(p, rng, (0, 0, 256, 200), cx, 180, 94, 20, math.pi * 1.0, math.pi * 2.0, 90, 9,
           [shade(c, 0.85) for c in cols])
    # the hollow, lit warmly from the egg
    p.shape("ellipse", (cx - 80, 176, cx + 80, 206), hexc("#7a4a22"), depth=0.35, light=1.2, line=1.2, rim=0, ao=0,
            tex="wood_h", tex_amt=0.9)
    p.glow((cx, 190), 64, hexc("#ffb050"), 0.6)
    # ---- the egg
    ex, ey, es = 128, 130, 2.0
    draw_egg(p, ex, ey, es)
    p.glow((ex, ey + 60), 44, hexc("#ffcf70"), 0.35)
    if cracked:
        p.glow((ex + 2, ey - 34), 58, hexc("#fff0a0"), 0.45)
        glowing_crack(p, [(ex - 32, ey - 24), (ex - 22, ey - 32), (ex - 13, ey - 21), (ex - 2, ey - 35),
                          (ex + 8, ey - 23), (ex + 19, ey - 36), (ex + 29, ey - 26), (ex + 37, ey - 32)], 4.2)
        glowing_crack(p, [(ex - 2, ey - 35), (ex + 3, ey - 50), (ex - 5, ey - 62)], 3.2)
        glowing_crack(p, [(ex + 8, ey - 23), (ex + 4, ey - 8), (ex + 12, ey + 4)], 3.2)
        glowing_crack(p, [(ex - 22, ey - 32), (ex - 26, ey - 46)], 2.6)
        glowing_crack(p, [(ex + 29, ey - 26), (ex + 33, ey - 12)], 2.6)
        glowing_crack(p, [(ex - 13, ey - 21), (ex - 22, ey - 6)], 2.4)
    # ---- front half of the nest, overlapping the egg's base
    front = ImageChops.subtract(
        p.union([("ellipse", (cx - 112, 176, cx + 112, 240))] +
                [("ellipse", (cx + 104 * math.cos(a) - 18, 214 + 20 * math.sin(a) - 14,
                              cx + 104 * math.cos(a) + 18, 214 + 20 * math.sin(a) + 14))
                 for a in [i * math.pi / 10 for i in range(11)]]),
        p._mask("ellipse", (cx - 82, 142, cx + 82, 186)))
    p.paint_mask(front, straw, depth=0.2, light=1.25, tex="wood_h", tex_amt=0.9, line=1.8)
    _straw(p, rng, (0, 170, 256, 256), cx, 196, 92, 6, math.pi * -0.1, math.pi * 1.1, 70, 6,
           [shade(c, 0.92) for c in cols], spread=0.3)
    _straw(p, rng, (0, 170, 256, 256), cx, 214, 102, 16, math.pi * 0.0, math.pi * 1.0, 170, 12, cols)
    _straw(p, rng, (0, 170, 256, 256), cx, 204, 98, 10, math.pi * -0.05, math.pi * 1.05, 60, 8, cols, spread=0.8)
    # stalks poking out of the rim
    for x, y, a, ln in ((24, 204, 205, 22), (230, 200, -25, 24), (52, 234, 160, 18), (204, 236, 20, 20),
                        (62, 186, 235, 16), (192, 184, 300, 16), (130, 238, 95, 12)):
        t = math.radians(a)
        pts = [(x, y), (x + math.cos(t) * ln, y + math.sin(t) * ln)]
        p.stroke(pts, shade(straw, 0.5), 3.4)
        p.stroke(pts, hexc("#f2d27a"), 2.0)
    if cracked:
        for pts in ([(210, 244), (216, 237), (224, 241), (220, 248)], [(34, 244), (40, 237), (48, 242), (42, 248)]):
            p.shape("poly", pts, EGG_GOLD, depth=0.3, light=1.4, spec=0.8, line=1.2, rim=0)
    # ---- warm motes and glints
    for x, y, r in ((52, 70, 2.2), (206, 58, 2.6), (36, 136, 1.8), (222, 128, 2.0), (170, 24, 1.6), (86, 30, 1.6)):
        p.glow((x, y), r * 4, hexc("#ffb040"), 0.9)
        p.flat("ellipse", (x - r, y - r, x + r, y + r), hexc("#ffe8a0"))
    p.sparkle((102, 78), 8)
    p.sparkle((164, 156), 5)
    if cracked:
        p.sparkle((150, 52), 9, hexc("#fff6d0"))
        p.sparkle((82, 110), 6, hexc("#fff6d0"))
        p.sparkle((178, 96), 5, hexc("#fff6d0"))
    return p.finish(outline=3, ground_shadow=(14, 226, 242, 254))


def save(img, rel):
    path = os.path.join(ROOT, "assets", "sprites", "companion", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    print("wrote", os.path.relpath(path, ROOT))


def main():
    for el in ELEMENTS:
        for st in STAGES:
            save(STAGE_FN[st](el), f"{el}_{st}.png")
    save(egg_nest(False), "egg_nest.png")
    save(egg_nest(True), "egg_nest_cracked.png")


if __name__ == "__main__":
    main()

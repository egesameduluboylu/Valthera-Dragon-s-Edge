"""Textured UI skin: 9-slice PNGs for buttons, panels, bars and item frames.

    python3 tools/art/ui_skin.py            # writes assets/ui/skin/*.png
    python3 tools/art/generate.py skin      # same, as a generate.py group

Every stretchable texture is laid out as <margin> + <one plain tile> + <margin>. All
ornament (corner caps, flourishes, rivets, gems) lives inside the margins and the
middle is periodic, so Godot can stretch or tile it without smearing the detail.
The margins used here are mirrored in src/ui/ui_theme.gd (SKIN table): change both.

Shapes are drawn supersampled (painter.SS) and downscaled, like the rest of tools/art.
"""
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

from painter import SS, hexc  # noqa: E402

INK = hexc("1c1418")
GOLD_HI = hexc("fff2c2")
GOLD_L = hexc("f3cf78")
GOLD = hexc("d9a84e")
GOLD_D = hexc("8a6428")
GOLD_INK = hexc("3a2410")
TAU = math.tau


# ------------------------------------------------------------------ small helpers
def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def pnoise(w, h, cx, cy, seed):
    """Smooth value noise, exactly periodic with period (w, h). Returns an "L" image."""
    rng = random.Random(seed)
    small = Image.new("L", (cx, cy))
    small.putdata([rng.randrange(256) for _ in range(cx * cy)])
    big = Image.new("L", (cx * 3, cy * 3))
    for i in range(3):
        for j in range(3):
            big.paste(small, (i * cx, j * cy))
    return big.resize((w * 3, h * 3), Image.BICUBIC).crop((w, h, 2 * w, 2 * h))


def shifted(mask, dx, dy):
    out = Image.new("L", mask.size, 0)
    out.paste(mask, (int(dx), int(dy)))
    return out


def grow(mask, px):
    """Dilates (px > 0) or erodes (px < 0) a supersampled mask by px final pixels."""
    n = int(round(abs(px) * SS))
    f = ImageFilter.MaxFilter if px > 0 else ImageFilter.MinFilter
    while n > 0:
        step = min(n, 4)
        mask = mask.filter(f(step * 2 + 1))
        n -= step
    return mask


def tile_to(tile, size, origin):
    """Repeats `tile` over an image of `size`, with a tile corner at `origin`."""
    out = Image.new(tile.mode, size)
    tw, th = tile.size
    ox, oy = origin[0] % tw - tw, origin[1] % th - th
    for x in range(ox, size[0], tw):
        for y in range(oy, size[1], th):
            out.paste(tile, (x, y))
    return out


def vgrad(size, stops):
    """Vertical gradient image; stops = [(t, color), ...] with t in 0..1."""
    w, h = size
    col = []
    for y in range(h):
        t = y / max(1, h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                col.append(mix(c0, c1, (t - t0) / max(1e-6, t1 - t0)))
                break
        else:
            col.append(stops[-1][1])
    img = Image.new("RGBA", (1, h))
    img.putdata(col)
    return img.resize((w, h), Image.NEAREST)


def wood_tile(tw, th, dark, mid, light, seed, rings=3, streak=1.0):
    """Periodic wood with horizontal grain, returned at supersampled size."""
    w, h = tw * 2, th * 2
    warp = pnoise(w, h, 2, max(2, th // 18), seed).tobytes()
    fine = pnoise(w, h, 3, max(3, th // 3), seed + 1).tobytes()
    fine2 = pnoise(w, h, 5, max(4, int(th / 1.5)), seed + 2).tobytes()
    fine3 = pnoise(w, h, 9, max(8, th), seed + 4).tobytes()
    blot = pnoise(w, h, 3, 3, seed + 3).tobytes()
    deep = mix(dark, (0, 0, 0, 255), 0.35)
    px = []
    for i in range(w * h):
        y = i // w
        t = y / h * rings + (warp[i] / 255 - 0.5) * 1.8
        s = math.sin(t * TAU)
        line = max(0.0, s) ** 14
        v = (0.4 * fine[i] + 0.25 * fine2[i] + 0.22 * fine3[i]) / 255 * streak + 0.22 * blot[i] / 255 \
            + 0.12 * (0.5 - 0.5 * s)
        v = max(0.0, min(1.0, (v - 0.25) * 1.25))
        c = mix(dark, mid, v * 2) if v < 0.5 else mix(mid, light, (v - 0.5) * 2)
        px.append(mix(c, deep, line * 0.45))
    img = Image.new("RGBA", (w, h))
    img.putdata(px)
    return img.resize((tw * SS, th * SS), Image.BICUBIC)


def speckle_tile(tw, th, dark, light, seed, cells=6):
    """Periodic mottled texture (leather, paper, stone)."""
    w, h = tw * 2, th * 2
    a = pnoise(w, h, cells, cells, seed).tobytes()
    b = pnoise(w, h, cells * 3, cells * 3, seed + 1).tobytes()
    rng = random.Random(seed)
    px = []
    for i in range(w * h):
        v = 0.6 * a[i] / 255 + 0.4 * b[i] / 255 + rng.uniform(-0.06, 0.06)
        px.append(mix(dark, light, (v - 0.2) * 1.6))
    img = Image.new("RGBA", (w, h))
    img.putdata(px)
    return img.resize((tw * SS, th * SS), Image.BICUBIC)


# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.size = (w * SS, h * SS)
        self.img = Image.new("RGBA", self.size, (0, 0, 0, 0))

    def mask(self):
        return Image.new("L", self.size, 0)

    def rr(self, box, r, g=0.0):
        m = self.mask()
        x0, y0, x1, y1 = box
        ImageDraw.Draw(m).rounded_rectangle(
            [(x0 - g) * SS, (y0 - g) * SS, (x1 + g) * SS - 1, (y1 + g) * SS - 1],
            radius=max(0.0, r + g) * SS, fill=255)
        return m

    def ellipse(self, cx, cy, rx, ry=None, g=0.0):
        ry = rx if ry is None else ry
        m = self.mask()
        ImageDraw.Draw(m).ellipse([(cx - rx - g) * SS, (cy - ry - g) * SS, (cx + rx + g) * SS,
                                   (cy + ry + g) * SS], fill=255)
        return m

    def lines(self, polylines, width, g=0.0):
        m = self.mask()
        d = ImageDraw.Draw(m)
        wd = (width + 2 * g) * SS
        for pts in polylines:
            sp = [(x * SS, y * SS) for x, y in pts]
            d.line(sp, fill=255, width=max(1, int(round(wd))), joint="curve")
            r = wd / 2
            for x, y in (sp[0], sp[-1]):
                d.ellipse((x - r, y - r, x + r, y + r), fill=255)
        return m

    def poly(self, pts, g=0.0):
        m = self.mask()
        d = ImageDraw.Draw(m)
        sp = [(x * SS, y * SS) for x, y in pts]
        d.polygon(sp, fill=255)
        if g > 0:
            d.line(sp + sp[:1], fill=255, width=int(round(2 * g * SS)), joint="curve")
        return m

    def paint(self, mask, src, alpha=1.0):
        if isinstance(src, tuple):
            src = Image.new("RGBA", self.size, src)
        a = ImageChops.multiply(src.getchannel("A"), mask)
        if alpha < 1.0:
            a = a.point(lambda v: int(v * alpha))
        layer = src.copy()
        layer.putalpha(a)
        self.img = Image.alpha_composite(self.img, layer)

    def emboss(self, mask, k, light, dark, vertical_only=False):
        """Lit crescent on the top-left edge, shaded crescent on the bottom-right edge.
        vertical_only lights only top/bottom edges (for bands that tile horizontally)."""
        k = max(1, int(round(k * SS)))
        kx = 0 if vertical_only else k
        if light:
            self.paint(ImageChops.subtract(mask, shifted(mask, kx, k)), light)
        if dark:
            self.paint(ImageChops.subtract(mask, shifted(mask, -kx, -k)), dark)

    def soft(self, mask, blur, color, dx=0, dy=0):
        m = shifted(mask, dx * SS, dy * SS).filter(ImageFilter.GaussianBlur(blur * SS))
        self.paint(m, color)

    def metal(self, mask, pal, outline=1.2, k=1.0, top=None, bottom=None, vertical_only=False):
        """Embossed metal (gold by default) with a dark outline."""
        hi, mid, lo, ink = pal
        if outline:
            self.paint(grow(mask, outline), ink)
        box = mask.getbbox()
        if box is None:
            return
        y0, y1 = (top if top is not None else box[1] / SS), (bottom if bottom is not None else box[3] / SS)
        g = Image.new("RGBA", self.size, (0, 0, 0, 0))
        span = max(1, int((y1 - y0) * SS))
        g.paste(vgrad((self.size[0], span), [(0, mix(mid, hi, 0.55)), (0.5, mid), (1, lo)]), (0, int(y0 * SS)))
        self.paint(mask, mid)
        self.paint(mask, g)
        self.emboss(mask, k, hi, mix(lo, ink, 0.4), vertical_only)

    def finish(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


GOLD_PAL = (GOLD_HI, GOLD, GOLD_D, GOLD_INK)
BRASS_PAL = (hexc("ffe6a0"), hexc("c9953f"), hexc("7a5220"), GOLD_INK)
DULL_PAL = (hexc("b9ada0"), hexc("7d7066"), hexc("4a403a"), INK)


def rivet(c, x, y, r, pal=GOLD_PAL):
    c.paint(c.ellipse(x, y + 0.5, r + 1.3), (0, 0, 0, 90))
    c.metal(c.ellipse(x, y, r), pal, outline=0.9, k=max(0.6, r * 0.35))
    c.paint(c.ellipse(x - r * 0.35, y - r * 0.35, r * 0.32), (255, 255, 240, 220))


def spiral(cx, cy, r0, r1, a0, turns, n=40, cw=True):
    """Points of an Archimedean spiral from radius r0 to r1 (for scroll curls)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        a = a0 + (1 if cw else -1) * turns * TAU * t
        r = r0 + (r1 - r0) * t
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def mirror4(c, draw_tl):
    """Runs draw_tl(canvas) on a fresh layer and stamps it into all four corners."""
    layer = Canvas(c.w, c.h)
    draw_tl(layer)
    tl = layer.img
    for fx, fy in ((False, False), (True, False), (False, True), (True, True)):
        im = tl
        if fx:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        if fy:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        c.img = Image.alpha_composite(c.img, im)


# ------------------------------------------------------------------ buttons
BTN_W, BTN_H = 112, 80
BTN_M = (26, 16, 26, 24)  # left, top, right, bottom (texture margins)

BTN_WOOD = {
    "normal": (hexc("3b2519"), hexc("5c3d29"), hexc("7a5439")),
    "hover": (hexc("48301f"), hexc("6e4a31"), hexc("8e6545")),
    "pressed": (hexc("2c1c13"), hexc("47301f"), hexc("5e412c")),
}
BTN_GOLD = {
    "normal": (hexc("d69533"), hexc("84480f")),
    "hover": (hexc("e8a843"), hexc("9a5a18")),
    "pressed": (hexc("ad7228"), hexc("6a3a0c")),
}


def button(state="normal", primary=False):
    w, h = BTN_W, BTN_H
    c = Canvas(w, h)
    pressed = state == "pressed"
    body_box = (2, 2, w - 2, h - 2)
    face_box = (2, 6, w - 2, h - 2) if pressed else (2, 2, w - 2, h - 8)
    body = c.rr(body_box, 14)
    face = c.rr(face_box, 13)
    # ink outline + soft drop shadow
    c.soft(body, 1.5, (0, 0, 0, 110), 0, 1.5)
    c.paint(c.rr(body_box, 14, 1.8), INK)
    # the lip: darker wood/metal edge seen below (or above when pressed)
    lip = hexc("6e4515") if primary else hexc("1f130d")
    c.paint(body, lip)
    c.paint(ImageChops.subtract(body, shifted(body, 0, -3 * SS)), mix(lip, (0, 0, 0, 255), 0.35))
    # the plank face
    if primary:
        top, bot = BTN_GOLD["pressed" if pressed else state]
        c.paint(face, vgrad(c.size, [(0, top), (0.55, mix(top, bot, 0.55)), (1, bot)]))
        mid_w = w - BTN_M[0] - BTN_M[2]
        g = tile_to(wood_tile(mid_w, h, hexc("6a3a0c"), hexc("a86a22"), hexc("e0aa52"), 11, rings=4), c.size,
                    (BTN_M[0] * SS, 0))
        c.paint(face, g, alpha=0.32)
    else:
        dark, mid, light = BTN_WOOD[state]
        # the middle columns tile horizontally in Godot, so the grain repeats with that period
        mid_w = w - BTN_M[0] - BTN_M[2]
        c.paint(face, tile_to(wood_tile(mid_w, h, dark, mid, light, 3, rings=3), c.size, (BTN_M[0] * SS, 0)))
    # carved groove running round the plank, a lit edge under it
    groove = ImageChops.subtract(c.rr(face_box, 9, -5), c.rr(face_box, 8, -6.2))
    c.paint(shifted(groove, 0, SS), (255, 230, 180, 45 if not primary else 70))
    c.paint(groove, (40, 20, 5, 150 if not primary else 110))
    # gloss: soft light on the upper half, a crisp highlight line on the top edge
    gl = Image.new("RGBA", c.size, (0, 0, 0, 0))
    fy0, fy1 = face_box[1], face_box[3]
    span = int((fy1 - fy0) * 0.55 * SS)
    gl.paste(vgrad((c.size[0], span), [(0, (255, 240, 210, 70 if not primary else 70)), (1, (255, 240, 210, 0))]),
             (0, int(fy0 * SS)))
    c.paint(grow(face, -1.5), gl)
    c.emboss(face, 1.6, (255, 236, 196, 150 if not primary else 190), (0, 0, 0, 90))
    if pressed:
        # inner shadow along the top: the plank sits down in its frame
        sh = ImageChops.subtract(face, shifted(face, 0, 4 * SS)).filter(ImageFilter.GaussianBlur(1.5 * SS))
        c.paint(ImageChops.multiply(sh, face), (0, 0, 0, 150))
    # brass corner caps with rivets
    pal = GOLD_PAL if primary else BRASS_PAL
    if state == "hover":
        pal = (GOLD_HI, hexc("e2b45a"), hexc("94692a"), GOLD_INK)
    x0, y0, x1, y1 = face_box

    def caps(layer):
        f = layer.rr(face_box, 13)
        corner = layer.rr((x0, y0, x0 + 20, y0 + 15), 0)
        cap = ImageChops.subtract(ImageChops.multiply(f, corner), layer.rr(face_box, 6, -5.5))
        # arrow-cut arm ends
        cap = ImageChops.subtract(cap, layer.poly([(x0 + 16, y0 + 6), (x0 + 21, y0 + 6), (x0 + 21, y0 - 1), (x0 + 19, y0 - 1)]))
        cap = ImageChops.subtract(cap, layer.poly([(x0 + 6, y0 + 12), (x0 + 6, y0 + 16), (x0 - 1, y0 + 16), (x0 - 1, y0 + 14)]))
        layer.metal(cap, pal, outline=1.1, k=0.9, top=y0, bottom=y0 + 7)
        rivet(layer, x0 + 7.6, y0 + 7.4, 2.3, pal)

    layer = Canvas(w, h)
    caps(layer)
    tl = layer.img
    # the top caps are drawn for the face, the bottom ones are re-anchored to the face bottom
    top_pair = Image.alpha_composite(tl, tl.transpose(Image.FLIP_LEFT_RIGHT))
    c.img = Image.alpha_composite(c.img, top_pair)
    bottom_pair = top_pair.transpose(Image.FLIP_TOP_BOTTOM)
    # FLIP maps y -> h - y; the face bottom must land on y1 (not on h - y0)
    dy = int(round((y1 - (h - y0)) * SS))
    c.img = Image.alpha_composite(c.img, shifted_rgba(bottom_pair, 0, dy))
    return c.finish()


def shifted_rgba(img, dx, dy):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


def disabled(img):
    """Desaturated, dimmed copy of a finished texture."""
    r, g, b, a = img.split()
    grey = Image.merge("RGB", (r, g, b)).convert("L").convert("RGB")
    rgb = Image.blend(Image.merge("RGB", (r, g, b)), grey, 0.8)
    rgb = rgb.point(lambda v: int(v * 0.62 + 10))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


# ------------------------------------------------------------------ close medallion
def close_button(state="normal", glyph="x"):
    """Round gold button with an X (close) or a cog (settings)."""
    s = 80
    c = Canvas(s, s)
    cx, cy, r = 40, 39, 34
    c.soft(c.ellipse(cx, cy, r), 2.5, (0, 0, 0, 140), 0, 2.5)
    pal = GOLD_PAL if state != "pressed" else BRASS_PAL
    if state == "hover":
        pal = (hexc("fffbe0"), hexc("f0c461"), hexc("9c7230"), GOLD_INK)
    ring = c.ellipse(cx, cy, r)
    c.metal(ring, pal, outline=1.8, k=1.6)
    # little studs around the ring
    for i in range(8):
        a = TAU * i / 8 + TAU / 16
        rivet(c, cx + math.cos(a) * (r - 3.6), cy + math.sin(a) * (r - 3.6), 1.6, pal)
    inner = c.ellipse(cx, cy, r - 8)
    c.paint(c.ellipse(cx, cy, r - 7), GOLD_INK)
    disc_top, disc_bot = (hexc("7a2a20"), hexc("2c0d0b")) if state != "hover" else (hexc("913428"), hexc("3a120e"))
    if state == "pressed":
        disc_top, disc_bot = hexc("4e1a14"), hexc("1e0808")
    c.paint(inner, vgrad(c.size, [(0, disc_top), (0.35, disc_top), (1, disc_bot)]))
    c.paint(ImageChops.subtract(inner, shifted(inner, 0, 3 * SS)).filter(ImageFilter.GaussianBlur(SS)), (0, 0, 0, 150))
    off = 1 if state == "pressed" else 0
    if glyph == "gear":
        # a cog: 8 teeth around a ring with a hole
        pts = []
        for i in range(16):
            a0 = TAU * i / 16 - TAU / 64
            a1 = TAU * i / 16 + TAU / 64
            rr_ = 17 if i % 2 == 0 else 12.5
            pts += [(cx + math.cos(a0) * rr_, cy + off + math.sin(a0) * rr_),
                    (cx + math.cos(a1) * rr_, cy + off + math.sin(a1) * rr_)]
        cog = ImageChops.subtract(c.poly(pts), c.ellipse(cx, cy + off, 5.5))
        c.paint(grow(cog, 1.6), INK)
        x = cog
    else:
        # the X
        d = 11
        arms = [[(cx - d, cy - d + off), (cx + d, cy + d + off)], [(cx + d, cy - d + off), (cx - d, cy + d + off)]]
        c.paint(c.lines(arms, 6.5, 1.6), INK)
        x = c.lines(arms, 6.5)
    c.paint(x, hexc("f6ead2"))
    c.paint(ImageChops.subtract(x, shifted(x, 0, -2 * SS)), hexc("c9b48f"))
    c.paint(ImageChops.subtract(x, shifted(x, 0, 2 * SS)), (255, 255, 255, 255))
    # glossy dome highlight
    hl = ImageChops.multiply(c.ellipse(cx - 4, cy - 12, r - 14, r - 22), inner)
    c.paint(hl.filter(ImageFilter.GaussianBlur(2 * SS)), (255, 255, 255, 45))
    return c.finish()


def knob():
    """Slider grabber: a small gold stud with a ruby dome."""
    s = 48
    c = Canvas(s, s)
    cx, cy = 24, 23
    c.soft(c.ellipse(cx, cy, 19), 2.0, (0, 0, 0, 150), 0, 2)
    c.metal(c.ellipse(cx, cy, 19), GOLD_PAL, outline=1.6, k=1.4)
    gem = c.ellipse(cx, cy, 11)
    c.paint(grow(gem, 1.2), GOLD_INK)
    c.paint(gem, vgrad(c.size, [(0, hexc("e0564a")), (0.5, hexc("a8261e")), (1, hexc("4a0c0a"))]))
    hl = ImageChops.multiply(c.ellipse(cx - 3, cy - 5, 6, 4), gem)
    c.paint(hl.filter(ImageFilter.GaussianBlur(SS)), (255, 255, 255, 150))
    return c.finish()


# ------------------------------------------------------------------ panels
PANEL_WOOD = {"m": 64, "tile": 192, "pad": 8}
PANEL_PARCH = {"m": 26, "tile": 96, "pad": 5}
PANEL_DARK = {"m": 20, "tile": 64, "pad": 0}


def panel_wood():
    m, t, p = PANEL_WOOD["m"], PANEL_WOOD["tile"], PANEL_WOOD["pad"]
    s = 2 * m + t
    c = Canvas(s, s)
    body_box = (p, p, s - p, s - p)
    body = c.rr(body_box, 16)
    c.soft(body, 4, (0, 0, 0, 150), 0, 3)
    c.paint(c.rr(body_box, 16, 2), INK)
    # outer molding: a darker wood frame
    frame_wood = tile_to(wood_tile(t, t, hexc("150d09"), hexc("281a12"), hexc("3a271b"), 21, rings=2), c.size, (m * SS, m * SS))
    c.paint(body, frame_wood)
    c.emboss(body, 1.5, (255, 225, 170, 60), (0, 0, 0, 120))
    # the main field
    field_box = (p + 13, p + 13, s - p - 13, s - p - 13)
    field = c.rr(field_box, 7)
    c.paint(c.rr(field_box, 7, 1.2), hexc("0e0806"))
    main_wood = tile_to(wood_tile(t, t, hexc("22160f"), hexc("2f2018"), hexc("3e2a1e"), 5, rings=4), c.size, (m * SS, m * SS))
    c.paint(field, main_wood)
    # inner shadow inside the field so it reads as sunk into the frame
    ring = ImageChops.subtract(field, grow(field, -3)).filter(ImageFilter.GaussianBlur(3 * SS))
    c.paint(ImageChops.multiply(ring, field), (0, 0, 0, 140))
    # gold-leaf double border: a bold outer band and a thin inner line
    outer = ImageChops.subtract(c.rr(body_box, 13, -4), c.rr(body_box, 10, -7))
    c.metal(outer, GOLD_PAL, outline=0.9, k=0.8)
    inner = ImageChops.subtract(c.rr(body_box, 7, -10.2), c.rr(body_box, 6, -11.6))
    c.metal(inner, GOLD_PAL, outline=0.6, k=0.5)

    def flourish(L):
        o = p + 5.5  # the outer gold band
        k = 1.25  # ornament scale; everything must stay inside the margin (x, y < m)

        def P(x, y):
            return (o + x * k, o + y * k)

        # corner plate: a rounded diamond sitting over the corner of the double border
        plate = L.poly([P(-1, 9), P(9, -1), P(19, 9), P(9, 19)], g=1.2)
        plate = ImageChops.add(plate, L.ellipse(*P(9, 9), 7.5 * k))
        L.metal(plate, GOLD_PAL, outline=1.2, k=1.0)
        # red gem in the plate
        gx, gy = P(9, 9)
        L.paint(L.ellipse(gx, gy, 4.4 * k), GOLD_INK)
        gem = L.ellipse(gx, gy, 3.6 * k)
        L.paint(gem, hexc("b3202a"))
        L.paint(ImageChops.subtract(gem, shifted(gem, SS, SS)), hexc("ff8a7a"))
        L.paint(L.ellipse(gx - 1.2, gy - 1.2, 1.3), (255, 255, 255, 230))
        # scroll curls along both edges: a stem hugging the outer band that rolls into
        # a spiral, and a leaf curling back toward the corner
        curls = []
        for flip in (False, True):
            stem = [P(16, 2.4), P(24, 2.0), P(30, 3.2)]
            roll = [P(x, y) for x, y in spiral(30.5, 8.4, 5.2, 1.2, -math.pi / 2, 0.9, cw=True)]
            leaf = [P(17, 7.5), P(20, 11.5), P(24.5, 13.0)]
            for pts in (stem + roll, leaf):
                curls.append([(o + (y - o), o + (x - o)) for x, y in pts] if flip else pts)
        L.metal(L.lines(curls, 2.8), GOLD_PAL, outline=1.0, k=0.7)
        for q in (P(25.5, 13.2), P(13.2, 25.5)):
            L.metal(L.ellipse(q[0], q[1], 2.2), GOLD_PAL, outline=0.9, k=0.6)
        L.metal(L.ellipse(*P(18.5, 18.5), 2.0), GOLD_PAL, outline=0.9, k=0.6)

    mirror4(c, flourish)
    return c.finish()


def panel_parchment():
    m, t, p = PANEL_PARCH["m"], PANEL_PARCH["tile"], PANEL_PARCH["pad"]
    s = 2 * m + t
    c = Canvas(s, s)
    body_box = (p, p, s - p, s - p)
    # torn edge: threshold a softened rect plus periodic noise (period = tile, so edges tile)
    base = c.rr(body_box, 10, -1.5).filter(ImageFilter.GaussianBlur(2.2 * SS))
    n = tile_to(pnoise(t * SS, t * SS, 14, 14, 41), c.size, (m * SS, m * SS))
    n2 = tile_to(pnoise(t * SS, t * SS, 40, 40, 42), c.size, (m * SS, m * SS))
    shape = ImageChops.add(ImageChops.subtract(base, n.point(lambda v: int(v * 0.35))), n2.point(lambda v: int(v * 0.12)))
    shape = shape.point(lambda v: 255 if v > 60 else 0).filter(ImageFilter.GaussianBlur(SS * 0.35))
    c.soft(shape, 2.5, (40, 20, 5, 120), 0, 2)
    c.paint(grow(shape, 1.0), hexc("4a2c16"))
    paper = tile_to(speckle_tile(t, t, hexc("e6d2a8"), hexc("f6e8c8"), 43, cells=4), c.size, (m * SS, m * SS))
    c.paint(shape, paper)
    # burn: browning toward the edge, soft and irregular
    inner = grow(shape, -2).filter(ImageFilter.GaussianBlur(5 * SS))
    burn = ImageChops.subtract(shape, inner)
    burn = ImageChops.add(burn, ImageChops.multiply(burn, n))
    c.paint(burn, hexc("a0662a"), alpha=0.9)
    c.paint(ImageChops.subtract(shape, grow(shape, -1.2)), hexc("5a3316"), alpha=0.8)
    # faint ruled lines of an old page would stretch badly, so only fibres: keep middle plain
    return c.finish()


def panel_dark():
    m, t = PANEL_DARK["m"], PANEL_DARK["tile"]
    s = 2 * m + t
    c = Canvas(s, s)
    box = (1, 1, s - 1, s - 2)
    body = c.rr(box, 12)
    # lit lip under the inset (the surface it is carved into)
    c.paint(c.rr((1, 2, s - 1, s - 1), 12), (255, 214, 150, 50))
    c.paint(body, hexc("0b0706"))
    leather = tile_to(speckle_tile(t, t, hexc("140c09"), hexc("241711"), 51, cells=4), c.size, (m * SS, m * SS))
    field = grow(body, -1.6)
    c.paint(field, leather)
    # inset shadow, heavier at the top
    ring = ImageChops.subtract(field, shifted(grow(field, -2), 0, 3 * SS)).filter(ImageFilter.GaussianBlur(2.5 * SS))
    c.paint(ImageChops.multiply(ring, field), (0, 0, 0, 190))
    # thin tarnished gold line with tiny corner studs
    line = ImageChops.subtract(c.rr(box, 9, -4), c.rr(box, 8, -5.2))
    c.paint(line, GOLD_D, alpha=0.85)

    def studs(L):
        rivet(L, 9.5, 9.5, 1.9, BRASS_PAL)

    mirror4(c, studs)
    return c.finish()


BAR_STRIP = {"tile": 128, "body": 64, "edge": 8, "trim": 12, "shadow": 8}


def strip(side="header"):
    """Wood bar spanning the screen width, gold trim on its inner edge (bottom for the
    header, top for the footer) and a soft shadow cast past it. Tiles horizontally; the
    middle band tiles vertically."""
    t, bh, e, tr, sh = (BAR_STRIP[k] for k in ("tile", "body", "edge", "trim", "shadow"))
    h = e + bh + tr + sh
    c = Canvas(t, h)
    head = side == "header"
    # vertical layout, top to bottom
    if head:
        edge_y, body_y, trim_y, shadow_y = 0, e, e + bh, e + bh + tr
    else:
        shadow_y, trim_y, body_y, edge_y = 0, sh, sh + tr, sh + tr + bh
    wood = tile_to(wood_tile(t, bh, hexc("1d130e"), hexc("2f2018"), hexc("43301f"), 61, rings=2), c.size,
                   (0, body_y * SS))
    wood_top = 0 if head else trim_y
    c.paint(c.rr((-4, wood_top, t + 4, wood_top + e + bh + tr), 0), wood)
    # molded trim band on the inner edge: dark groove, wood moulding, gold line at the rim
    y = trim_y
    c.paint(c.rr((-4, y, t + 4, y + tr), 0), hexc("140c08"))
    if head:
        mould, gold_y, ink_y, lit_y = (y + 1, y + tr - 4.5), (y + tr - 4.5, y + tr - 1), (y + tr - 1, y + tr), y
    else:
        mould, gold_y, ink_y, lit_y = (y + 4.5, y + tr - 1), (y + 1, y + 4.5), (y, y + 1), y + tr - 1
    c.paint(c.rr((-4, mould[0], t + 4, mould[1]), 0), vgrad(c.size, [(0, hexc("3a271a")), (1, hexc("241810"))]))
    c.metal(c.rr((-4, gold_y[0], t + 4, gold_y[1]), 0), GOLD_PAL, outline=0, k=0.7, vertical_only=True)
    c.paint(c.rr((-4, ink_y[0], t + 4, ink_y[1]), 0), INK)
    c.paint(c.rr((-4, lit_y, t + 4, lit_y + 1), 0), (255, 220, 160, 40))
    # studs along the moulding, two per tile so they repeat evenly
    for x in (t / 4, 3 * t / 4):
        rivet(c, x, (mould[0] + mould[1]) / 2, 1.8, BRASS_PAL)
    # outer edge: a thin dark line and a light bevel
    oy = 0 if head else h - 2.4
    c.paint(c.rr((-4, oy, t + 4, oy + 2.4), 0), (0, 0, 0, 150))
    c.paint(c.rr((-4, oy + (1.2 if head else 0), t + 4, oy + (2.4 if head else 1.2)), 0), (255, 220, 170, 35))
    # soft shadow cast past the trim
    stops = [(0, (0, 0, 0, 150)), (1, (0, 0, 0, 0))] if head else [(0, (0, 0, 0, 0)), (1, (0, 0, 0, 150))]
    shade = Image.new("RGBA", c.size, (0, 0, 0, 0))
    shade.paste(vgrad((c.size[0], sh * SS), stops), (0, shadow_y * SS))
    c.paint(c.rr((-4, shadow_y, t + 4, shadow_y + sh), 0), shade)
    return c.finish()


# ------------------------------------------------------------------ bars
BAR_W, BAR_H = 32, 20
BAR_M = (8, 6, 8, 6)
BAR_COLORS = {
    "hp": ("ff7a66", "d8413a", "7a1614"),
    "player": ("9cf07e", "4fbf5a", "1c6a2a"),
    "xp": ("b8ecff", "4aa8e8", "1a4f8a"),
    "rage": ("ffc46a", "f08a24", "8a3a08"),
    "gold": ("fff0a0", "ffc93a", "8a5a10"),
    "white": ("ffffff", "d8d8d8", "8a8a8a"),
}


def bar_bg():
    c = Canvas(BAR_W, BAR_H)
    box = (0.5, 0.5, BAR_W - 0.5, BAR_H - 0.5)
    c.paint(c.rr(box, 7), (255, 214, 150, 70))  # lit rim below the groove
    groove = c.rr((0.5, 0.5, BAR_W - 0.5, BAR_H - 1.3), 6.5)
    c.paint(groove, INK)
    inner = c.rr((1.6, 1.6, BAR_W - 1.6, BAR_H - 2.4), 5.5)
    c.paint(inner, vgrad(c.size, [(0, hexc("080406")), (0.5, hexc("160d10")), (1, hexc("22161a"))]))
    top = ImageChops.subtract(inner, shifted(inner, 0, 2 * SS)).filter(ImageFilter.GaussianBlur(0.6 * SS))
    c.paint(ImageChops.multiply(top, inner), (0, 0, 0, 200))
    return c.finish()


def bar_fill(name):
    hi, mid, lo = (hexc(v) for v in BAR_COLORS[name])
    c = Canvas(BAR_W, BAR_H)
    box = (2, 2, BAR_W - 2, BAR_H - 3)
    f = c.rr(box, 5)
    c.paint(f, vgrad(c.size, [(0, hi), (0.18, hi), (0.5, mid), (0.82, mix(mid, lo, 0.6)), (1, lo)]))
    # glossy upper band and a crisp shine line
    shine = c.rr((4.5, 3.4, BAR_W - 4.5, 5.0), 1)
    c.paint(shine, (255, 255, 255, 200))
    c.paint(ImageChops.subtract(f, shifted(f, 0, -1.2 * SS)), mix(lo, (0, 0, 0, 255), 0.4))
    c.paint(ImageChops.subtract(f, grow(f, -0.8)), mix(lo, (0, 0, 0, 255), 0.2), alpha=0.8)
    return c.finish()


# ------------------------------------------------------------------ item tiles
TILE = 128
TILE_STYLE = {
    "common": {"pal": (hexc("d6d0c8"), hexc("8f8880"), hexc("4e4843"), INK), "well": hexc("24201d")},
    "rare": {"pal": (hexc("d8ecff"), hexc("4f8fe0"), hexc("1f4686"), hexc("0c1a33")), "well": hexc("0f1c30")},
    "epic": {"pal": (hexc("f0d8ff"), hexc("9b56e0"), hexc("4a1d86"), hexc("1c0b30")), "well": hexc("1e1030")},
    "legendary": {"pal": (hexc("fff4b8"), hexc("f0a232"), hexc("98480e"), hexc("3a1a04")), "well": hexc("2e1606")},
    "empty": {"pal": (hexc("6a5646"), hexc("3e3128"), hexc("241a14"), INK), "well": hexc("140d0b")},
}


def tile_frame(rarity, filled=False):
    st = TILE_STYLE[rarity]
    pal = st["pal"]
    c = Canvas(TILE, TILE)
    o = 7  # room for the glow
    outer_box = (o, o, TILE - o, TILE - o)
    band = 11
    inner_box = (o + band, o + band, TILE - o - band, TILE - o - band)
    outer = c.rr(outer_box, 15)
    inner = c.rr(inner_box, 6)
    if rarity == "legendary":
        c.soft(outer, 5, hexc("ff9a2a", 230))
        c.soft(outer, 2.5, hexc("ffd070", 200))
    elif rarity == "epic":
        c.soft(outer, 4, hexc("b86bff", 170))
    else:
        c.soft(outer, 2.5, (0, 0, 0, 140), 0, 2)
    if filled:
        well = c.rr(inner_box, 6, 1)
        rim = mix(st["well"], (0, 0, 0, 255), 0.55)
        c.paint(well, rim)
        glow = c.ellipse(TILE / 2, TILE / 2 - 4, 40, 40).filter(ImageFilter.GaussianBlur(12 * SS))
        c.paint(ImageChops.multiply(glow, well), mix(st["well"], pal[1], 0.25))
    ring = ImageChops.subtract(outer, inner)
    if rarity == "common":
        stone = tile_to(speckle_tile(64, 64, hexc("6e6760"), hexc("aaa39a"), 71, cells=6), c.size, (0, 0))
        c.paint(grow(ring, 1.6), INK)
        c.paint(ring, stone)
        c.emboss(ring, 1.5, (255, 255, 255, 110), (0, 0, 0, 120))
        # mortar joints: fixed notches on each side (corners stay whole)
        for a in (0.36, 0.64):
            x = o + (TILE - 2 * o) * a
            for seg in ([(x, o), (x, o + band)], [(x, TILE - o - band), (x, TILE - o)],
                        [(o, x), (o + band, x)], [(TILE - o - band, x), (TILE - o, x)]):
                c.paint(ImageChops.multiply(c.lines([seg], 1.1), ring), (30, 26, 24, 200))
    else:
        c.metal(ring, pal, outline=1.6, k=1.2, top=o, bottom=TILE - o)
        # a second, finer bevel line inside the band
        line = ImageChops.subtract(c.rr(outer_box, 11, -4), c.rr(outer_box, 10, -5))
        c.paint(line, mix(pal[2], pal[3], 0.3), alpha=0.7)
    # dark inner lip around the icon well
    c.paint(ImageChops.subtract(c.rr(inner_box, 6, 1.2), inner), mix(pal[3], (0, 0, 0, 255), 0.4))
    if filled:
        sh = ImageChops.subtract(inner, shifted(grow(inner, -1), 0, 4 * SS)).filter(ImageFilter.GaussianBlur(2 * SS))
        c.paint(ImageChops.multiply(sh, inner), (0, 0, 0, 170))

    def corner(L):
        x, y = o + 5.5, o + 5.5
        if rarity == "rare":
            rivet(L, x + 0.5, y + 0.5, 2.8, pal)
        elif rarity == "epic":
            gem = L.poly([(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)], g=0.5)
            L.paint(grow(gem, 1.4), hexc("1c0b30"))
            L.paint(gem, hexc("c050ff"))
            L.paint(L.poly([(x, y - 6), (x + 6, y), (x, y)]), hexc("f2b8ff"))
            L.paint(L.poly([(x - 6, y), (x, y + 6), (x, y)]), hexc("6a1ea8"))
            L.paint(L.ellipse(x - 1.5, y - 2.2, 1.1), (255, 255, 255, 240))
        elif rarity == "legendary":
            leaf = L.poly([(x - 3.5, y + 3.5), (x - 1, y - 6), (x + 3, y - 2), (x + 6, y - 1), (x + 3.5, y + 3.5)], g=0.6)
            leaf = ImageChops.add(leaf, L.ellipse(x + 0.5, y + 0.5, 5.2))
            L.metal(leaf, (hexc("fffbe0"), hexc("ffc54a"), hexc("b0600e"), hexc("3a1a04")), outline=1.2, k=0.9)
            L.paint(L.ellipse(x + 0.5, y + 0.5, 2.6), hexc("3a1a04"))
            gem = L.ellipse(x + 0.5, y + 0.5, 2.0)
            L.paint(gem, hexc("ff5a1a"))
            L.paint(L.ellipse(x, y, 0.8), (255, 255, 230, 240))
        elif rarity == "common":
            chip = L.poly([(o + 1, o + 13), (o + 4, o + 9), (o + 9, o + 4), (o + 13, o + 1), (o + 7, o + 7)])
            L.paint(ImageChops.multiply(chip, ring), (255, 255, 255, 40))

    if rarity != "empty":
        mirror4(c, corner)
    if not filled:
        # punch the icon well out so glow/shadow never tints what sits under the frame
        hole = grow(inner, -0.5).point(lambda v: 255 - v)
        c.img.putalpha(ImageChops.multiply(c.img.getchannel("A"), hole))
    return c.finish()


# ------------------------------------------------------------------ divider
DIV_W, DIV_H = 360, 24


def divider():
    c = Canvas(DIV_W, DIV_H)
    cx, cy = DIV_W / 2, DIV_H / 2
    line = c.rr((4, cy - 1.2, DIV_W - 4, cy + 1.2), 1)
    fade = Image.new("L", c.size, 0)
    col = []
    for x in range(c.size[0]):
        u = abs(x / SS - cx) / (cx - 4)
        col.append(int(255 * max(0.0, min(1.0, (1 - u) / 0.45))))
    row = Image.new("L", (c.size[0], 1))
    row.putdata(col)
    fade = row.resize(c.size, Image.NEAREST)
    lm = ImageChops.multiply(line, fade)
    c.paint(ImageChops.multiply(grow(line, 1.0), fade), GOLD_INK)
    c.paint(lm, GOLD)
    c.paint(ImageChops.multiply(c.rr((4, cy - 1.2, DIV_W - 4, cy - 0.3), 0), fade), GOLD_HI)
    # centre ornament: a diamond with two curls and small dots
    curls = []
    for s in (-1, 1):
        sp = spiral(cx + s * 13, cy - 1.5, 3.8, 1.0, math.pi / 2 if s < 0 else math.pi / 2, 0.8, cw=(s > 0))
        curls.append([(cx + s * 5, cy)] + sp)
    c.metal(c.lines(curls, 1.8), GOLD_PAL, outline=0.8, k=0.5)
    for s in (-1, 1):
        c.metal(c.ellipse(cx + s * 22, cy, 1.8), GOLD_PAL, outline=0.8, k=0.5)
    gem = c.poly([(cx, cy - 7), (cx + 6, cy), (cx, cy + 7), (cx - 6, cy)], g=0.5)
    c.metal(gem, GOLD_PAL, outline=1.0, k=0.8)
    c.paint(c.poly([(cx, cy - 3.5), (cx + 3, cy), (cx, cy + 3.5), (cx - 3, cy)]), hexc("b3202a"))
    c.paint(c.ellipse(cx - 0.8, cy - 1.2, 0.8), (255, 220, 210, 230))
    return c.finish()


# ------------------------------------------------------------------ entry point
def all_textures():
    out = {}
    for st in ("normal", "hover", "pressed"):
        out[f"button_{st}"] = button(st)
        out[f"button_primary_{st}"] = button(st, primary=True)
    out["button_disabled"] = disabled(button("normal"))
    for st in ("normal", "hover", "pressed"):
        out[f"close_{st}"] = close_button(st)
        out[f"gear_{st}"] = close_button(st, "gear")
    out["knob"] = knob()
    out["panel_wood"] = panel_wood()
    out["panel_parchment"] = panel_parchment()
    out["panel_dark"] = panel_dark()
    out["header"] = strip("header")
    out["footer"] = strip("footer")
    out["bar_bg"] = bar_bg()
    for k in BAR_COLORS:
        out[f"bar_{k}"] = bar_fill(k)
    for r in TILE_STYLE:
        out[f"tile_{r}"] = tile_frame(r)
        out[f"tile_{r}_filled"] = tile_frame(r, filled=True)
    d = divider()
    out["divider"] = d
    out["divider_left"] = d.crop((0, 0, DIV_W // 2 - 26, DIV_H))
    out["divider_center"] = d.crop((DIV_W // 2 - 26, 0, DIV_W // 2 + 26, DIV_H))
    out["divider_right"] = d.crop((DIV_W // 2 + 26, 0, DIV_W, DIV_H))
    return out


def write_all(save=None):
    for name, img in all_textures().items():
        if save:
            save(img, f"ui/skin/{name}.png")
        else:
            path = os.path.join(ROOT, "assets", "ui", "skin", f"{name}.png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.save(path, optimize=True)
            print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    write_all()

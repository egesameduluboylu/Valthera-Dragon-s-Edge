"""Small cartoon painter on top of Pillow.

Shapes are drawn supersampled, each with automatic shading and an ink outline. The
finished image is downsampled and gets a thick silhouette outline, which gives the
DragonFable-like "flash cartoon" look without hand-drawn assets.

Two looks share one API:

* classic (the default, ``Painter(w, h)``): flat two-tone cel shading, a darker crescent
  away from the light and a lighter one toward it, black ink.
* soft (``Painter(w, h, soft=True)``): the same cel crescents, but feathered into smooth
  gradients with hue-shifted tones (cool shadows, warm lights), a thin rim light on the
  shadow side, a soft contact shadow (ambient occlusion) onto whatever the shape is drawn
  over, colour-tinted ink that is heavier on the shadow side, optional surface textures
  (``tex="stone" | "wood" | "cloth" | "leather" | "metal" | "fur" | "bone" | "noise"``)
  and specular glints (``spec=1``). ``finish()`` then adds an anti-aliased silhouette
  outline that ignores soft glows, and a two-layer ground shadow.

The light comes from the top left everywhere. All drawing is limited to each shape's
bounding box, so large canvases stay fast.
"""
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 4  # supersampling factor
INK = (28, 20, 26, 255)
COOL = (46, 30, 86)      # hue the soft shadows lean toward
WARM = (255, 246, 214)   # hue the soft highlights lean toward
RIM = (210, 226, 255)    # rim light on the shadow side


def hexc(value, alpha=255):
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def shade(color, factor):
    """factor < 1 darkens, > 1 lightens toward white."""
    r, g, b, a = color
    if factor <= 1:
        return (int(r * factor), int(g * factor), int(b * factor), a)
    t = factor - 1
    return (int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t), a)


def mix(c1, c2, t):
    """Linear blend of two colours (alpha taken from c1 unless c2 has one)."""
    a = c1[3] if len(c1) > 3 else 255
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (a,)


def shadow_tone(color, factor):
    """Darker tone that leans cool, so shadows stay colourful instead of going muddy."""
    d = shade(color, factor)
    return mix(d, COOL, min(0.45, (1 - factor) * 0.55))


def light_tone(color, factor):
    """Lighter tone that leans warm."""
    if factor <= 1:
        return color
    t = factor - 1
    return mix(color, WARM, min(1.0, t * 1.05))


def ink_for(color):
    """Ink tinted by the fill, which reads softer than pure black on light surfaces."""
    return mix(INK, shade(color, 0.3), 0.32)


def _shift(mask, dx, dy):
    out = Image.new("L", mask.size, 0)
    out.paste(mask, (dx, dy))
    return out


def _blur(mask, radius):
    if radius < 0.5:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(radius))


def _erode(mask, r):
    """Round, anti-aliased erosion by ~r pixels (fast: a blur and a threshold)."""
    if r < 1:
        return mask
    b = mask.filter(ImageFilter.GaussianBlur(r / 2.0))
    return b.point(lambda v: 0 if v < 236 else min(255, (v - 236) * 14))


def _dilate(mask, r):
    if r < 1:
        return mask
    b = mask.filter(ImageFilter.GaussianBlur(r / 2.0))
    return b.point(lambda v: 0 if v < 3 else min(255, (v - 3) * 14))


def _scale(mask, amount):
    if amount >= 1:
        return mask
    k = max(0, int(255 * amount))
    return mask.point(lambda v: v * k // 255)


# ------------------------------------------------------------------ textures

_TEX = {}


def _value_noise(w, h, cx, cy, rng):
    """Smooth value noise with cells of cx x cy pixels."""
    sw, sh = max(2, int(w / cx) + 3), max(2, int(h / cy) + 3)
    small = Image.new("L", (sw, sh))
    small.putdata([rng.randint(0, 255) for _ in range(sw * sh)])
    big = small.resize((int(sw * cx), int(sh * cy)), Image.BICUBIC)
    return big.crop((int(cx), int(cy), int(cx) + w, int(cy) + h))


def _blend(a, b, t):
    return Image.blend(a, b, t)


def texture(kind, size, ss=None):
    """Grey texture (128 = neutral) covering `size`, cached per kind and size."""
    ss = ss or SS
    key = (kind, size, ss)
    if key in _TEX:
        return _TEX[key]
    w, h = size
    rng = random.Random(hash(kind) & 0xFFFF)
    rng = random.Random(sum(ord(ch) * (i + 1) for i, ch in enumerate(kind)))
    if kind == "wood" or kind == "wood_h":
        vert = kind == "wood"
        a = _value_noise(w, h, ss * 1.6, ss * 36, rng) if vert else _value_noise(w, h, ss * 36, ss * 1.6, rng)
        b = _value_noise(w, h, ss * 5, ss * 60, rng) if vert else _value_noise(w, h, ss * 60, ss * 5, rng)
        t = _blend(a, b, 0.5)
        t = t.point(lambda v: 128 + int((v - 128) * 2.2) if 0 <= 128 + (v - 128) * 2.2 <= 255 else (0 if v < 128 else 255))
        # a few knots / grain lines
        d = ImageDraw.Draw(t)
        for _ in range(int(w * h / (ss * ss * 2600)) + 1):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            ln = rng.uniform(10, 40) * ss
            if vert:
                d.line((x, y, x + rng.uniform(-2, 2) * ss, y + ln), fill=40, width=max(1, int(ss * 0.55)))
            else:
                d.line((x, y, x + ln, y + rng.uniform(-2, 2) * ss), fill=40, width=max(1, int(ss * 0.55)))
    elif kind == "stone":
        a = _value_noise(w, h, ss * 7, ss * 7, rng)
        b = _value_noise(w, h, ss * 2.2, ss * 2.2, rng)
        c = _value_noise(w, h, ss * 0.9, ss * 0.9, rng)
        t = _blend(_blend(a, b, 0.4), c, 0.35)
        t = t.point(lambda v: max(0, min(255, 128 + int((v - 128) * 2.4))))
        d = ImageDraw.Draw(t)
        for _ in range(int(w * h / (ss * ss * 60))):  # pits and speckles
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            r = rng.uniform(0.4, 0.9) * ss
            d.ellipse((x - r, y - r, x + r, y + r), fill=rng.choice((30, 50, 230)))
    elif kind == "leather":
        a = _value_noise(w, h, ss * 5, ss * 5, rng)
        c = _value_noise(w, h, ss * 0.8, ss * 0.8, rng)
        t = _blend(a, c, 0.45)
        t = t.point(lambda v: max(0, min(255, 128 + int((v - 128) * 2.2))))
    elif kind == "cloth":
        a = _value_noise(w, h, ss * 9, ss * 9, rng)
        t = a.point(lambda v: max(0, min(255, 128 + int((v - 128) * 0.7))))
        d = ImageDraw.Draw(t)
        step = ss * 2
        for i in range(-h, w, step):  # fine diagonal weave
            d.line((i, 0, i + h, h), fill=150, width=max(1, ss // 2))
        for i in range(0, w + h, step * 2):
            d.line((i, 0, i - h, h), fill=110, width=max(1, ss // 3))
    elif kind == "metal":
        a = _value_noise(w, h, ss * 30, ss * 1.2, rng)
        b = _value_noise(w, h, ss * 12, ss * 12, rng)
        t = _blend(a, b, 0.4)
        t = t.point(lambda v: max(0, min(255, 128 + int((v - 128) * 1.2))))
        d = ImageDraw.Draw(t)
        for _ in range(int(w * h / (ss * ss * 400))):  # nicks and scratches
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            ln = rng.uniform(2, 6) * ss
            d.line((x, y, x + ln, y + rng.uniform(-1, 1) * ss), fill=rng.choice((60, 220)), width=max(1, ss // 3))
    elif kind == "fur":
        t = _value_noise(w, h, ss * 8, ss * 8, rng).point(lambda v: 128 + (v - 128) // 2)
        d = ImageDraw.Draw(t)
        for _ in range(int(w * h / (ss * ss * 5))):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            ln = rng.uniform(2.5, 5) * ss
            dx = rng.uniform(-0.6, 0.3) * ln
            d.line((x, y, x + dx, y + ln), fill=rng.choice((50, 70, 200, 215)), width=max(1, int(ss * 0.45)))
    elif kind == "bone":
        a = _value_noise(w, h, ss * 6, ss * 6, rng)
        c = _value_noise(w, h, ss * 1.2, ss * 1.2, rng)
        t = _blend(a, c, 0.3).point(lambda v: max(0, min(255, 128 + int((v - 128) * 1.8))))
        d = ImageDraw.Draw(t)
        for _ in range(int(w * h / (ss * ss * 120))):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            r = rng.uniform(0.3, 0.7) * ss
            d.ellipse((x - r, y - r, x + r, y + r), fill=45)
    else:  # "noise": fine grain
        a = _value_noise(w, h, ss * 1.2, ss * 1.2, rng)
        b = _value_noise(w, h, ss * 6, ss * 6, rng)
        t = _blend(a, b, 0.4).point(lambda v: max(0, min(255, 128 + int((v - 128) * 2.0))))
    t = t.filter(ImageFilter.GaussianBlur(ss * 0.25))
    _TEX[key] = t
    return t


# ------------------------------------------------------------------ painter

class Painter:
    def __init__(self, width, height, soft=False):
        self.w, self.h = width, height
        self.soft = soft
        self.img = Image.new("RGBA", (width * SS, height * SS), (0, 0, 0, 0))
        # pixels that belong to solid shapes (not glows), used for the silhouette outline
        self.solid = Image.new("L", self.img.size, 0)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _s(points):
        if isinstance(points[0], (tuple, list)):
            return [(x * SS, y * SS) for x, y in points]
        return [v * SS for v in points]

    def _mask(self, kind, pts, **kw):
        m = Image.new("L", self.img.size, 0)
        d = ImageDraw.Draw(m)
        if kind == "ellipse":
            d.ellipse(self._s(pts), fill=255)
        elif kind == "rect":
            d.rounded_rectangle(self._s(pts), radius=kw.get("radius", 0) * SS, fill=255)
        elif kind == "poly":
            d.polygon(self._s(pts), fill=255)
        elif kind == "chord":
            d.chord(self._s(pts), kw["start"], kw["end"], fill=255)
        elif kind == "pie":
            d.pieslice(self._s(pts), kw["start"], kw["end"], fill=255)
        elif kind == "line":
            d.line(self._s(pts), fill=255, width=int(kw["width"] * SS), joint="curve")
            r = kw["width"] * SS / 2
            for x, y in self._s(pts)[:: max(1, len(pts) - 1)]:
                d.ellipse((x - r, y - r, x + r, y + r), fill=255)
        return m

    def _paste(self, layer, x, y):
        w, h = self.img.size
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + layer.size[0]), min(h, y + layer.size[1])
        if x1 <= x0 or y1 <= y0:
            return
        part = layer.crop((x0 - x, y0 - y, x1 - x, y1 - y))
        self.img.paste(Image.alpha_composite(self.img.crop((x0, y0, x1, y1)), part), (x0, y0))

    def _fill(self, mask, color, origin=(0, 0), solid=True):
        """Composites `color` through `mask` (whose top-left sits at `origin`)."""
        bbox = mask.getbbox()
        if bbox is None:
            return
        m = mask.crop(bbox)
        layer = Image.new("RGBA", m.size, color[:3] + (0,))
        if color[3] >= 255:
            layer.putalpha(m)
        else:
            layer.putalpha(m.point(lambda v: v * color[3] // 255))
        x, y = bbox[0] + origin[0], bbox[1] + origin[1]
        self._paste(layer, x, y)
        if solid and color[3] > 0:
            box = (x, y, x + m.size[0], y + m.size[1])
            self.solid.paste(ImageChops.lighter(self.solid.crop(box), m), box[:2])

    def _crop(self, m, pad):
        bbox = m.getbbox()
        if bbox is None:
            return None, None
        w, h = self.img.size
        box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(w, bbox[2] + pad), min(h, bbox[3] + pad))
        return m.crop(box), box

    def _texture(self, c, box, kind, amount, color):
        t = texture(kind, self.img.size).crop(box)
        gain = amount * 0.8
        hi = t.point(lambda v: max(0, min(255, int((v - 128) * gain))))
        lo = t.point(lambda v: max(0, min(255, int((128 - v) * gain))))
        self._fill(ImageChops.multiply(hi, c), light_tone(color, 1.35), box[:2], solid=False)
        self._fill(ImageChops.multiply(lo, c), shadow_tone(color, 0.62), box[:2], solid=False)

    def _paint(self, m, color, shadow=0.72, light=1.22, depth=0.14, line=1.6, ink=INK, **opts):
        """Fills mask `m` (full-canvas) with shading and ink, working only around its bbox."""
        bbox = m.getbbox()
        if bbox is None:
            return
        size = min(bbox[2] - bbox[0], bbox[3] - bbox[1])
        k = max(1, int(size * depth))
        r = max(1, int(line * SS))
        if not self.soft:
            c, box = self._crop(m, k + r + 4)
            o = box[:2]
            self._fill(c, color, o)
            if shadow:
                self._fill(ImageChops.subtract(c, _shift(c, -k, -k)), shade(color, shadow), o)
            if light:
                self._fill(ImageChops.subtract(c, _shift(c, k // 2, k // 2)), shade(color, light), o)
            if line:
                self._fill(ImageChops.subtract(c, c.filter(ImageFilter.MinFilter(r * 2 + 1))), ink, o)
            return
        self._paint_soft(m, color, shadow, light, depth, line, ink, size, k, **opts)

    def _paint_soft(self, m, color, shadow, light, depth, line, ink, size, k, tex=None, tex_amt=1.0, spec=0.0,
                    rim=None, ao=None, gloss=0.0):
        r = max(1, int(line * SS))
        pad = int(k * 2.5 + 8 * SS)
        c, box = self._crop(m, pad)
        o = box[:2]
        transparent = color[3] == 0
        decorative = not shadow and not light
        # contact shadow onto what is already painted underneath
        ao = (0.32 if not decorative and not transparent else 0.0) if ao is None else ao
        if ao and size > 3 * SS:
            off = max(1, int(min(k * 0.35, 3 * SS) + SS * 0.6))
            sh = _blur(_shift(c, off, off), max(SS, min(k * 0.6, 5 * SS)))
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
            # broad soft falloff (form shading) reaching further into the shape
            k2 = int(k * 2.2) + 1
            broad = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, -k2, -k2), k2 * 0.8)))
            self._fill(_scale(broad, 0.5), shadow_tone(color, (1 + shadow) / 2), o, solid=False)
        if light and not transparent:
            kh = max(1, k // 2)
            hl = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, kh, kh), max(1, kh * 0.45))))
            self._fill(_scale(hl, 0.9), light_tone(color, light), o, solid=False)
            if size > 10 * SS:
                k3 = int(k * 1.6) + 1
                bloom = ImageChops.multiply(c, ImageChops.invert(_blur(_shift(c, k3, k3), k3 * 0.9)))
                self._fill(_scale(bloom, 0.28), light_tone(color, (1 + light) / 2), o, solid=False)
        rim = (0.5 if shadow and size > 12 * SS else 0.0) if rim is None else rim
        inner = _erode(c, r) if (line or rim or spec) else c
        if rim and not transparent:
            rr = max(1, int(SS * 1.3))
            band = ImageChops.subtract(inner, _shift(inner, -rr, -rr))
            self._fill(_scale(_blur(band, SS * 0.4), rim), mix(light_tone(color, 1.4), RIM, 0.5), o, solid=False)
        if spec and not transparent:
            s = max(1, int(min(k * 0.6, 3 * SS)))
            band = ImageChops.subtract(inner, _shift(inner, s, s))
            # fade the band toward the lower right so it reads as a glint, not an outline
            bx0, by0, bx1, by1 = c.getbbox() or (0, 0, 1, 1)
            fall = Image.new("L", c.size, 0)
            fd = ImageDraw.Draw(fall)
            cx = bx0 + (bx1 - bx0) * 0.3
            cy = by0 + (by1 - by0) * 0.3
            rx, ry = (bx1 - bx0) * 0.55, (by1 - by0) * 0.55
            fd.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
            fall = _blur(fall, max(rx, ry) * 0.35)
            band = ImageChops.multiply(_blur(band, SS * 0.5), fall)
            self._fill(_scale(band, min(1.0, spec)), (255, 255, 255, 255), o, solid=False)
        if gloss and not transparent:
            bx0, by0, bx1, by1 = c.getbbox() or (0, 0, 1, 1)
            bw, bh = bx1 - bx0, by1 - by0
            g = Image.new("L", c.size, 0)
            ImageDraw.Draw(g).ellipse((bx0 + bw * 0.2, by0 + bh * 0.14, bx0 + bw * 0.46, by0 + bh * 0.34), fill=255)
            g = ImageChops.multiply(_blur(g, SS * 0.6), inner)
            self._fill(_scale(g, min(1.0, gloss)), (255, 255, 255, 255), o, solid=False)
        if line:
            if ink == INK and not transparent:
                ink = ink_for(color)
            thin = _erode(c, max(1, int(r * 0.75)))
            d = max(1, int(r * 0.7))
            e = ImageChops.darker(thin, _shift(thin, -d, -d))
            self._fill(ImageChops.subtract(c, e), ink, o, solid=not transparent or True)

    # ------------------------------------------------------------ public api
    def shape(self, kind, pts, color, shadow=0.72, light=1.22, depth=0.14, line=1.6,
              ink=INK, clip=None, **kw):
        """Fills a shape with shading and an ink outline.

        depth is the shading crescent size as a fraction of the shape's smaller side.
        clip optionally restricts drawing to another mask (e.g. a pattern on a shield).
        Soft-mode extras (ignored by the classic look): tex, tex_amt, spec, rim, ao, gloss.
        """
        opts = {k2: kw.pop(k2) for k2 in ("tex", "tex_amt", "spec", "rim", "ao", "gloss") if k2 in kw}
        m = self._mask(kind, pts, **kw)
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        self._paint(m, color, shadow, light, depth, line, ink, **opts)
        return m

    def paint_mask(self, m, color, shadow=0.72, light=1.22, depth=0.14, line=1.6, ink=INK, clip=None, **opts):
        """shape() for an arbitrary mask (e.g. a union of primitives)."""
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        self._paint(m, color, shadow, light, depth, line, ink, **opts)
        return m

    def union(self, items):
        """Union mask of several (kind, pts[, kw]) primitives."""
        m = Image.new("L", self.img.size, 0)
        for it in items:
            kw = it[2] if len(it) > 2 else {}
            m = ImageChops.lighter(m, self._mask(it[0], it[1], **kw))
        return m

    def flat(self, kind, pts, color, **kw):
        m = self._mask(kind, pts, **kw)
        self._fill(m, color)
        return m

    def stroke(self, pts, color, width, soft=0.0):
        """Plain line with no shading or ink (details: stitches, cracks, fur strands)."""
        m = self._mask("line", pts, width=width)
        if soft:
            c, box = self._crop(m, int(soft * SS * 3) + 2)
            self._fill(_blur(c, soft * SS), color, box[:2], solid=False)
        else:
            self._fill(m, color, solid=False)
        return m

    def tex(self, mask, kind, amount=1.0, color=(128, 128, 128, 255)):
        """Adds a surface texture to an already painted mask."""
        c, box = self._crop(mask, 2)
        if c is not None:
            self._texture(c, box, kind, amount, color)

    def sparkle(self, center, r, color=(255, 255, 255, 255), glow=True):
        """Four-point star glint (for polished metal, gems and magic)."""
        cx, cy = center
        if glow:
            self.glow(center, r * 1.6, color, 0.6)
        pts = []
        for i in range(8):
            rr = r if i % 2 == 0 else r * 0.18
            import math
            a = i * math.pi / 4
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self._fill(self._mask("poly", pts), color, solid=False)

    def glow(self, center, radius, color, strength=0.8):
        """Soft radial glow (for torches, orbs, eyes)."""
        cx, cy = center[0] * SS, center[1] * SS
        blur = radius * SS / 8
        half = int(radius * SS + blur * 3 + 2)
        layer = Image.new("RGBA", (half * 2, half * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        steps = 12
        for i in range(steps, 0, -1):
            t = i / steps
            a = int(255 * strength * (1 - t) ** 1.6)
            rr = radius * t * SS
            d.ellipse((half - rr, half - rr, half + rr, half + rr), fill=color[:3] + (a,))
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        self._paste(layer, int(cx) - half, int(cy) - half)

    def shadow_on(self, mask, strength=0.35, offset=2.0, blur=3.0, color=(18, 10, 30, 255)):
        """Soft shadow cast by `mask` onto what is already painted (e.g. a hat brim on a face)."""
        c, box = self._crop(mask, int((offset + blur * 3) * SS) + 2)
        if c is None:
            return
        o = int(offset * SS)
        sh = _blur(_shift(c, o, o), blur * SS)
        sh = ImageChops.multiply(sh, self.img.crop(box).getchannel("A"))
        self._fill(_scale(sh, strength), color, box[:2], solid=False)

    def finish(self, outline=2, outline_color=INK, ground_shadow=None, grade=None):
        if not self.soft:
            out = self.img.resize((self.w, self.h), Image.LANCZOS)
            if outline:
                alpha = out.getchannel("A").point(lambda v: 255 if v > 40 else 0)
                grown = alpha.filter(ImageFilter.MaxFilter(outline * 2 + 1))
                sil = Image.new("RGBA", out.size, outline_color)
                sil.putalpha(grown)
                out = Image.alpha_composite(sil, out)
            if ground_shadow:
                x0, y0, x1, y1 = ground_shadow
                base = Image.new("RGBA", out.size, (0, 0, 0, 0))
                ImageDraw.Draw(base).ellipse((x0, y0, x1, y1), fill=(0, 0, 0, 90))
                base = base.filter(ImageFilter.GaussianBlur(3))
                out = Image.alpha_composite(base, out)
            return out
        big = self.img
        if grade is None or grade:
            big = self._grade(big, grade if isinstance(grade, float) else 1.0)
        out = big.resize((self.w, self.h), Image.LANCZOS)
        if outline:
            solid = ImageChops.darker(self.solid, big.getchannel("A")).point(lambda v: 255 if v > 90 else 0)
            grown = _dilate(solid, outline * SS).resize((self.w, self.h), Image.LANCZOS)
            sil = Image.new("RGBA", out.size, outline_color)
            sil.putalpha(grown)
            out = Image.alpha_composite(sil, out)
        if ground_shadow:
            x0, y0, x1, y1 = ground_shadow
            base = Image.new("RGBA", out.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(base)
            d.ellipse((x0, y0, x1, y1), fill=(12, 6, 18, 70))
            base = base.filter(ImageFilter.GaussianBlur(5))
            core = Image.new("RGBA", out.size, (0, 0, 0, 0))
            cw, ch = (x1 - x0) * 0.2, (y1 - y0) * 0.22
            ImageDraw.Draw(core).ellipse((x0 + cw, y0 + ch, x1 - cw, y1 - ch), fill=(12, 6, 18, 110))
            base = Image.alpha_composite(base, core.filter(ImageFilter.GaussianBlur(3)))
            out = Image.alpha_composite(base, out)
        return out

    def _grade(self, img, amount):
        """Whole-sprite light: a warm wash from the top left and a cool one toward the bottom right."""
        w, h = img.size
        g = Image.linear_gradient("L").resize((w, h))            # 0 at top .. 255 at bottom
        gx = Image.linear_gradient("L").rotate(90).resize((w, h))  # 255 at left .. 0 at right
        diag = ImageChops.add(g.point(lambda v: v // 2), ImageChops.invert(gx).point(lambda v: v // 2))
        alpha = ImageChops.darker(img.getchannel("A"), self.solid)
        cool = ImageChops.multiply(diag.point(lambda v: max(0, v - 120) * int(48 * amount) // 135), alpha)
        warm = ImageChops.multiply(ImageChops.invert(diag).point(lambda v: max(0, v - 130) * int(50 * amount) // 125),
                                   alpha)
        out = img.copy()
        layer = Image.new("RGBA", (w, h), COOL + (0,))
        layer.putalpha(cool)
        out = Image.alpha_composite(out, layer)
        layer = Image.new("RGBA", (w, h), (255, 236, 200, 0))
        layer.putalpha(warm)
        return Image.alpha_composite(out, layer)

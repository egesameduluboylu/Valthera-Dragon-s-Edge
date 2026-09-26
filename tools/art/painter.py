"""Small cartoon painter on top of Pillow.

Shapes are drawn supersampled, each with automatic cel shading (a darker crescent
away from the light, a lighter one toward it) and an ink outline. The finished
image is downsampled and gets a thick silhouette outline, which gives the
DragonFable-like "flash cartoon" look without hand-drawn assets.
"""
from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 4  # supersampling factor
INK = (28, 20, 26, 255)


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


def _shift(mask, dx, dy):
    out = Image.new("L", mask.size, 0)
    out.paste(mask, (dx, dy))
    return out


class Painter:
    def __init__(self, width, height):
        self.w, self.h = width, height
        self.img = Image.new("RGBA", (width * SS, height * SS), (0, 0, 0, 0))

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

    # ------------------------------------------------------------ public api
    def shape(self, kind, pts, color, shadow=0.72, light=1.22, depth=0.14, line=1.6,
              ink=INK, clip=None, **kw):
        """Fills a shape with cel shading and an ink outline.

        depth is the shading crescent size as a fraction of the shape's smaller side.
        clip optionally restricts drawing to another mask (e.g. a pattern on a shield).
        """
        m = self._mask(kind, pts, **kw)
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        bbox = m.getbbox()
        if bbox is None:
            return m
        size = min(bbox[2] - bbox[0], bbox[3] - bbox[1])
        k = max(1, int(size * depth))
        self._fill(m, color)
        if shadow:
            self._fill(ImageChops.subtract(m, _shift(m, -k, -k)), shade(color, shadow))
        if light:
            hl = ImageChops.subtract(m, _shift(m, k // 2, k // 2))
            self._fill(hl, shade(color, light))
        if line:
            r = max(1, int(line * SS))
            edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(r * 2 + 1)))
            self._fill(edge, ink)
        return m

    def flat(self, kind, pts, color, **kw):
        m = self._mask(kind, pts, **kw)
        self._fill(m, color)
        return m

    def glow(self, center, radius, color, strength=0.8):
        """Soft radial glow (for torches, orbs, eyes)."""
        cx, cy = center
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        steps = 12
        for i in range(steps, 0, -1):
            t = i / steps
            a = int(255 * strength * (1 - t) ** 1.6)
            r = radius * t * SS
            d.ellipse((cx * SS - r, cy * SS - r, cx * SS + r, cy * SS + r), fill=color[:3] + (a,))
        layer = layer.filter(ImageFilter.GaussianBlur(radius * SS / 8))
        self.img = Image.alpha_composite(self.img, layer)

    def _fill(self, mask, color):
        solid = Image.new("RGBA", self.img.size, color)
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        layer.paste(solid, (0, 0), mask)
        self.img = Image.alpha_composite(self.img, layer)

    def finish(self, outline=2, outline_color=INK, ground_shadow=None):
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

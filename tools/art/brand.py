"""App icon and boot splash, composed from the game's own art.

    python3 tools/art/brand.py        # writes assets/brand/*.png

icon.png (512) is the project icon; icon_192.png and the adaptive layers
(432, foreground + background) are the Android launcher icons. splash.png
(720x1280) is shown while the game boots.
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
A = lambda *p: os.path.join(ROOT, "assets", *p)  # noqa: E731
OUT = A("brand")

GOLD = (217, 168, 78)
GOLD_HI = (255, 242, 194)
GOLD_D = (138, 100, 40)
INK = (28, 20, 24)


def radial(size, inner, outer, center=(0.5, 0.45)):
    w, h = size
    img = Image.new("RGB", size, outer)
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    cx, cy = w * center[0], h * center[1]
    r = max(w, h) * 0.75
    steps = 60
    for i in range(steps):
        t = i / steps
        rr = r * (1 - t)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=int(255 * t))
    img.paste(Image.new("RGB", size, inner), (0, 0), mask.filter(ImageFilter.GaussianBlur(w / 30)))
    return img


def dragon(px):
    """Ashwing's head and wings, cropped from the boss sprite."""
    sp = Image.open(A("sprites", "enemies", "ashwing.png")).convert("RGBA")
    crop = sp.crop((10, 20, 340, 350))
    return crop.resize((px, px), Image.LANCZOS)


def embers(img, n, seed, area):
    import random
    rnd = random.Random(seed)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    x0, y0, x1, y1 = area
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.uniform(1.5, 4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, rnd.randint(120, 190), 60, rnd.randint(120, 230)))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(1)))
    img.alpha_composite(glow)


def icon_background(s):
    bg = radial((s, s), (122, 38, 20), (22, 10, 12)).convert("RGBA")
    embers(bg, s // 12, 3, (0, 0, s, s))
    return bg


def icon_foreground(s, pad):
    fg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = dragon(s - 2 * pad)
    shadow = Image.new("RGBA", fg.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), (pad, pad + s // 60), d)
    fg.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s / 80)))
    fg.alpha_composite(d, (pad, pad))
    return fg


def framed_icon(s):
    """Rounded square with a gold frame, for the store and the project icon."""
    img = icon_background(s)
    img.alpha_composite(icon_foreground(s, s // 12))
    ss = 4
    m = Image.new("L", (s * ss, s * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, s * ss - 1, s * ss - 1], radius=s * ss // 5, fill=255)
    m = m.resize((s, s), Image.LANCZOS)
    frame = Image.new("RGBA", (s * ss, s * ss), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    w = s * ss // 28
    fd.rounded_rectangle([w // 2, w // 2, s * ss - w // 2, s * ss - w // 2], radius=s * ss // 5 - w // 2,
                         outline=GOLD_D + (255,), width=w)
    fd.rounded_rectangle([w, w, s * ss - w, s * ss - w], radius=s * ss // 5 - w, outline=GOLD + (255,), width=w // 2)
    img.alpha_composite(frame.resize((s, s), Image.LANCZOS))
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, (0, 0), m)
    return out


def title_text(img, text, y, size, font):
    f = ImageFont.truetype(font, size)
    d = ImageDraw.Draw(img)
    w = d.textlength(text, font=f)
    x = (img.width - w) / 2
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), text, font=f, fill=(255, 140, 40, 200))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    d.text((x, y + 4), text, font=f, fill=INK + (255,), stroke_width=6, stroke_fill=INK + (255,))
    d.text((x, y), text, font=f, fill=GOLD_HI + (255,), stroke_width=3, stroke_fill=GOLD_D + (255,))


def splash():
    w, h = 720, 1280
    img = radial((w, h), (96, 30, 18), (14, 8, 10), (0.5, 0.42)).convert("RGBA")
    embers(img, 140, 11, (0, 0, w, h))
    d = dragon(560)
    img.alpha_composite(d, ((w - 560) // 2, 250))
    title_text(img, "VALTHERA", 820, 104, A("fonts", "Cinzel.ttf"))
    title_text(img, "DRAGON'S EDGE", 950, 52, A("fonts", "Cinzel.ttf"))
    return img.convert("RGB")


def main():
    os.makedirs(OUT, exist_ok=True)
    icon = framed_icon(512)
    icon.save(os.path.join(OUT, "icon.png"), optimize=True)
    icon.resize((192, 192), Image.LANCZOS).save(os.path.join(OUT, "icon_192.png"), optimize=True)
    # adaptive: the launcher masks to a circle or squircle, so the dragon keeps a safe margin
    icon_background(432).convert("RGB").save(os.path.join(OUT, "icon_background_432.png"), optimize=True)
    icon_foreground(432, 96).save(os.path.join(OUT, "icon_foreground_432.png"), optimize=True)
    splash().save(os.path.join(OUT, "splash.png"), optimize=True)
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            print("wrote", os.path.join("assets", "brand", f))


if __name__ == "__main__":
    main()

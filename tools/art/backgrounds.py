"""Dungeon backgrounds drawn directly with ImageDraw at 2x, then downscaled."""
import random

from PIL import Image, ImageDraw, ImageFilter

from painter import hexc, shade

W, H = 720, 720   # battle stage size
K = 2             # draw scale


def _brick_wall(d, rng, top, bottom, base, mortar):
    d.rectangle((0, top * K, W * K, bottom * K), fill=mortar)
    row_h = 44
    y = top
    row = 0
    while y < bottom:
        x = -rng.randint(0, 60) if row % 2 else -rng.randint(40, 90)
        while x < W:
            w = rng.randint(70, 110)
            c = shade(base, rng.uniform(0.8, 1.12))
            d.rounded_rectangle(((x + 3) * K, (y + 3) * K, (x + w - 3) * K, (y + row_h - 3) * K),
                                radius=6 * K, fill=c)
            # top highlight and bottom shadow on each brick
            d.line(((x + 8) * K, (y + 6) * K, (x + w - 10) * K, (y + 6) * K), fill=shade(c, 1.12), width=2 * K)
            d.line(((x + 6) * K, (y + row_h - 6) * K, (x + w - 6) * K, (y + row_h - 6) * K), fill=shade(c, 0.78), width=3 * K)
            if rng.random() < 0.07:  # moss creeping out of the mortar
                mx = x + rng.randint(10, max(11, w - 40))
                d.ellipse((mx * K, (y + row_h - 8) * K, (mx + 36) * K, (y + row_h + 4) * K), fill=hexc("#4f6b3a", 170))
            x += w
        y += row_h
        row += 1


def _floor(d, rng, top):
    d.rectangle((0, top * K, W * K, H * K), fill=hexc("#241c22"))
    y = top
    h = 30
    while y < H:
        x = -rng.randint(0, 80)
        while x < W:
            w = rng.randint(90, 150)
            c = shade(hexc("#5a4a44"), rng.uniform(0.8, 1.05) * (0.7 + 0.35 * (y - top) / (H - top)))
            d.rounded_rectangle(((x + 3) * K, (y + 3) * K, (x + w - 3) * K, (y + h - 3) * K), radius=8 * K, fill=c)
            d.line(((x + 10) * K, (y + 6) * K, (x + w - 12) * K, (y + 6) * K), fill=shade(c, 1.1), width=2 * K)
            x += w
        y += h
        h = int(h * 1.18)


def _torch(img, cx, cy):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    for i in range(30, 0, -1):
        r = i * 9 * K
        a = int(140 * (1 - i / 30) ** 1.4)
        g.ellipse((cx * K - r, cy * K - r, cx * K + r, cy * K + r), fill=(255, 170, 70, a))
    glow = glow.filter(ImageFilter.GaussianBlur(12 * K))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(((cx - 7) * K, (cy + 4) * K, (cx + 7) * K, (cy + 58) * K), radius=4 * K,
                        fill=hexc("#4a3020"), outline=hexc("#1c1418"), width=2 * K)
    d.rounded_rectangle(((cx - 16) * K, (cy - 2) * K, (cx + 16) * K, (cy + 12) * K), radius=4 * K,
                        fill=hexc("#6b6f75"), outline=hexc("#1c1418"), width=2 * K)
    d.polygon([((cx - 14) * K, cy * K), (cx * K, (cy - 46) * K), ((cx + 14) * K, cy * K)], fill=hexc("#ff8a2a"))
    d.polygon([((cx - 8) * K, cy * K), (cx * K, (cy - 30) * K), ((cx + 8) * K, cy * K)], fill=hexc("#ffd86a"))


def _arch(d, cx, top, w, h):
    d.rectangle(((cx - w // 2) * K, (top + w // 2) * K, (cx + w // 2) * K, (top + h) * K), fill=hexc("#120c12"))
    d.pieslice(((cx - w // 2) * K, top * K, (cx + w // 2) * K, (top + w) * K), 180, 360, fill=hexc("#120c12"))
    for i in range(9):  # arch stones
        import math
        a = math.pi + i * math.pi / 8
        r0, r1 = w / 2, w / 2 + 26
        cy = top + w / 2
        pts = [(cx + r0 * math.cos(a - 0.17), cy + r0 * math.sin(a - 0.17)),
               (cx + r1 * math.cos(a - 0.17), cy + r1 * math.sin(a - 0.17)),
               (cx + r1 * math.cos(a + 0.17), cy + r1 * math.sin(a + 0.17)),
               (cx + r0 * math.cos(a + 0.17), cy + r0 * math.sin(a + 0.17))]
        d.polygon([(x * K, y * K) for x, y in pts], fill=hexc("#6e6470"), outline=hexc("#1c1418"), width=2 * K)
    # iron bars
    for x in range(cx - w // 2 + 16, cx + w // 2 - 8, 24):
        d.line((x * K, (top + 20) * K, x * K, (top + h) * K), fill=hexc("#3a3a44"), width=5 * K)


def _vignette(img):
    v = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(v)
    w, h = img.size
    steps = 40
    for i in range(steps):
        t = i / steps
        d.rectangle((int(w * t / 4), int(h * t / 4), int(w - w * t / 4), int(h - h * t / 4)),
                    fill=int(255 * t))
    v = v.filter(ImageFilter.GaussianBlur(40 * K))
    dark = Image.new("RGBA", img.size, (8, 4, 10, 255))
    dark.putalpha(v.point(lambda a: 200 - int(a * 0.78)))
    img.alpha_composite(dark)


def rotten_cellar(seed=7):
    rng = random.Random(seed)
    img = Image.new("RGBA", (W * K, H * K), hexc("#1c1418"))
    d = ImageDraw.Draw(img)
    floor_top = 430
    _brick_wall(d, rng, 0, floor_top, hexc("#5c5462"), hexc("#231b23"))
    _arch(d, 360, 190, 170, floor_top - 190)
    _floor(d, rng, floor_top)
    # dark band where wall meets floor
    d.rectangle((0, (floor_top - 6) * K, W * K, (floor_top + 8) * K), fill=hexc("#150f14"))
    # barrels
    for bx, by in ((40, 356), (96, 372)):
        d.rounded_rectangle((bx * K, by * K, (bx + 62) * K, (by + 84) * K), radius=18 * K,
                            fill=hexc("#7a4e2a"), outline=hexc("#1c1418"), width=3 * K)
        for yy in (by + 18, by + 64):
            d.line((bx * K, yy * K, (bx + 62) * K, yy * K), fill=hexc("#4b4f57"), width=6 * K)
    _torch(img, 170, 190)
    _torch(img, 550, 190)
    d = ImageDraw.Draw(img)
    # cobwebs
    for sx, sy, fx in ((0, 0, 1), (W, 0, -1)):
        for r in (40, 70, 100):
            d.arc(((sx - r) * K, (sy - r) * K, (sx + r) * K, (sy + r) * K),
                  0 if fx > 0 else 90, 90 if fx > 0 else 180, fill=(220, 220, 230, 90), width=K)
        for a in range(0, 100, 25):
            import math
            ang = math.radians(a if fx > 0 else 180 - a)
            d.line((sx * K, sy * K, (sx + 110 * math.cos(ang)) * K, (sy + 110 * math.sin(ang)) * K),
                   fill=(220, 220, 230, 90), width=K)
    _vignette(img)
    return img.resize((W, H), Image.LANCZOS)

"""Character and enemy sprites. The player faces right, enemies face left.
All coordinates are in final-image pixels (256 x 256)."""
from painter import Painter, hexc, shade

SIZE = 256

STEEL = hexc("#b9c6d3")
STEEL_DARK = hexc("#6f7f92")
SKIN = hexc("#f2c393")
BLUE = hexc("#3566b8")
RED = hexc("#c63a2f")
GOLD = hexc("#e7b440")
LEATHER = hexc("#7a4a2a")
WOOD = hexc("#9a6433")
BONE = hexc("#ece3c8")
RUST = hexc("#9a5a34")
WHITE = hexc("#ffffff")
DARK = hexc("#221820")


def warrior():
    p = Painter(SIZE, SIZE)
    # cape behind the body
    p.shape("poly", [(96, 108), (74, 214), (112, 222), (140, 110)], shade(RED, 0.8))
    # legs and boots
    p.shape("rect", (104, 176, 126, 224), STEEL_DARK, radius=6)
    p.shape("rect", (132, 176, 154, 224), STEEL_DARK, radius=6)
    p.shape("rect", (96, 210, 128, 234), LEATHER, radius=7)
    p.shape("rect", (130, 210, 164, 234), LEATHER, radius=7)
    # torso
    p.shape("rect", (92, 108, 162, 188), BLUE, radius=20)
    p.shape("poly", [(114, 122), (140, 122), (127, 146)], GOLD, depth=0.2)
    p.shape("rect", (92, 166, 162, 180), LEATHER, radius=4, depth=0.3)
    p.shape("rect", (118, 163, 136, 183), GOLD, radius=3, depth=0.3)
    # sword arm, blade and guard
    p.shape("poly", [(170, 126), (182, 118), (236, 36), (226, 30)], STEEL, depth=0.35, light=1.35)
    p.shape("line", [(162, 108), (192, 136)], GOLD, width=9)
    p.shape("ellipse", (156, 138, 170, 152), GOLD)
    p.shape("ellipse", (148, 112, 178, 146), BLUE)
    p.shape("ellipse", (164, 114, 186, 136), SKIN)
    # shoulder pads
    p.shape("ellipse", (78, 100, 118, 134), STEEL)
    p.shape("ellipse", (138, 100, 176, 132), STEEL)
    # kite shield (held in front)
    shield = [(52, 118), (110, 118), (108, 160), (81, 206), (54, 160)]
    m = p.shape("poly", shield, WHITE)
    p.shape("rect", (72, 110, 90, 212), RED, clip=m, line=0, depth=0.05)
    p.shape("poly", shield, (0, 0, 0, 0), shadow=0, light=0, line=2.2)
    p.shape("ellipse", (73, 144, 89, 160), GOLD)
    # head
    p.shape("ellipse", (88, 22, 172, 106), SKIN, depth=0.12)
    p.shape("chord", (82, 14, 178, 110), STEEL, start=180, end=360)
    p.shape("rect", (82, 56, 178, 68), STEEL_DARK, radius=4, depth=0.2)
    p.shape("rect", (122, 60, 134, 92), STEEL_DARK, radius=3)  # nose guard
    p.shape("poly", [(118, 18), (98, 2), (84, 34), (106, 30)], RED)  # plume
    p.shape("ellipse", (104, 4, 140, 26), RED)
    # face (looking right)
    p.shape("ellipse", (144, 70, 156, 86), DARK, shadow=0, light=0, line=0)
    p.flat("ellipse", (148, 72, 152, 77), WHITE)
    p.shape("line", [(142, 66), (158, 64)], DARK, width=3, shadow=0, light=0, line=0)
    p.shape("line", [(146, 94), (156, 93)], shade(SKIN, 0.55), width=3, shadow=0, light=0, line=0)
    return p.finish(ground_shadow=(60, 226, 196, 248))


def cellar_rat():
    fur = hexc("#8a7a6e")
    pink = hexc("#e79aa0")
    p = Painter(SIZE, SIZE)
    p.shape("line", [(196, 196), (226, 188), (240, 160), (232, 132)], pink, width=10, depth=0.3)
    p.shape("ellipse", (70, 112, 212, 216), fur)
    p.shape("ellipse", (92, 160, 180, 214), shade(fur, 1.35), line=0, depth=0.1)
    p.shape("ellipse", (170, 200, 200, 222), pink)
    p.shape("ellipse", (96, 200, 128, 222), pink)
    p.shape("ellipse", (58, 64, 104, 118), fur)
    p.shape("ellipse", (68, 74, 96, 108), pink, line=0)
    p.shape("ellipse", (28, 98, 124, 176), fur)
    p.shape("poly", [(40, 118), (6, 142), (40, 162)], fur)
    p.shape("ellipse", (0, 134, 18, 150), pink)
    p.shape("rect", (30, 156, 38, 170), WHITE, radius=2, line=1)
    p.shape("rect", (40, 156, 48, 168), WHITE, radius=2, line=1)
    p.glow((62, 124), 18, hexc("#ff3b3b"), 0.7)
    p.shape("ellipse", (54, 116, 72, 134), hexc("#e0282c"), light=1.6)
    p.flat("ellipse", (57, 119, 62, 124), WHITE)
    for y0, y1 in ((136, 128), (144, 146)):
        p.shape("line", [(24, y0), (0, y1)], DARK, width=1.5, shadow=0, light=0, line=0)
    return p.finish(ground_shadow=(50, 206, 230, 234))


def skeleton_guard():
    p = Painter(SIZE, SIZE)
    # legs
    for x in (104, 134):
        p.shape("rect", (x, 170, x + 12, 226), BONE, radius=5)
        p.shape("ellipse", (x - 4, 190, x + 16, 206), BONE)
        p.shape("rect", (x - 10, 218, x + 18, 234), RUST, radius=6)
    # pelvis and spine
    p.shape("rect", (98, 160, 156, 180), BONE, radius=9)
    p.shape("rect", (121, 100, 133, 168), BONE, radius=5)
    for i, y in enumerate((108, 124, 140)):
        w = 30 - i * 3
        p.shape("rect", (127 - w, y, 127 + w, y + 9), BONE, radius=5)
    # back arm with sword (raised)
    p.shape("line", [(150, 112), (180, 134), (184, 104)], BONE, width=9)
    p.shape("poly", [(178, 100), (190, 102), (226, 14), (214, 8)], RUST, depth=0.3, light=1.3)
    p.shape("line", [(168, 96), (204, 108)], hexc("#5a4632"), width=8)
    p.shape("ellipse", (176, 96, 194, 114), BONE)
    # skull and helmet
    p.shape("ellipse", (86, 22, 166, 100), BONE, depth=0.12)
    p.shape("rect", (100, 84, 150, 112), BONE, radius=10)
    for x in (108, 118, 128, 138):
        p.shape("line", [(x, 94), (x, 110)], DARK, width=2, shadow=0, light=0, line=0)
    p.shape("ellipse", (94, 50, 118, 76), DARK, shadow=0, light=0, line=0)
    p.shape("ellipse", (126, 50, 150, 76), DARK, shadow=0, light=0, line=0)
    p.glow((106, 63), 14, hexc("#ff5030"), 0.9)
    p.glow((138, 63), 14, hexc("#ff5030"), 0.9)
    p.flat("ellipse", (102, 59, 110, 67), hexc("#ffd060"))
    p.flat("ellipse", (134, 59, 142, 67), hexc("#ffd060"))
    p.shape("poly", [(118, 80), (126, 80), (122, 88)], DARK, shadow=0, light=0, line=0)
    p.shape("chord", (80, 12, 172, 96), hexc("#707a82"), start=180, end=360)
    p.shape("rect", (78, 46, 174, 56), RUST, radius=3)
    # front arm with round shield
    p.shape("line", [(104, 114), (78, 140)], BONE, width=9)
    p.shape("ellipse", (24, 104, 100, 196), WOOD)
    p.shape("ellipse", (24, 104, 100, 196), (0, 0, 0, 0), shadow=0, light=0, line=4, ink=hexc("#4a4f55"))
    p.shape("ellipse", (52, 138, 72, 158), hexc("#8a939b"))
    p.shape("line", [(42, 120), (58, 134), (50, 146)], DARK, width=2, shadow=0, light=0, line=0)
    return p.finish(ground_shadow=(40, 222, 200, 246))


def mushroom_mage():
    cap = hexc("#8a4bc2")
    stem = hexc("#f1e3c6")
    p = Painter(SIZE, SIZE)
    # robe-like stem body
    p.shape("poly", [(92, 120), (170, 120), (190, 228), (72, 228)], stem)
    p.shape("rect", (72, 214, 190, 232), shade(cap, 0.8), radius=6)
    # arms
    p.shape("line", [(92, 160), (48, 170)], stem, width=12)
    # face
    p.shape("ellipse", (98, 146, 114, 164), DARK, shadow=0, light=0, line=0)
    p.shape("ellipse", (128, 146, 144, 164), DARK, shadow=0, light=0, line=0)
    p.flat("ellipse", (101, 149, 106, 154), WHITE)
    p.flat("ellipse", (131, 149, 136, 154), WHITE)
    p.shape("chord", (108, 168, 134, 186), DARK, start=0, end=180, shadow=0, light=0, line=0)
    # cap
    p.shape("chord", (36, 24, 226, 170), cap, start=180, end=360, depth=0.1)
    p.shape("rect", (40, 92, 222, 108), shade(cap, 0.7), radius=8)
    for box in ((70, 42, 98, 66), (126, 32, 158, 58), (182, 56, 204, 78), (104, 70, 122, 86)):
        p.shape("ellipse", box, hexc("#f0d8ff"), line=1.2)
    # staff and orb, held in front
    p.shape("line", [(30, 136), (44, 234)], hexc("#6b4428"), width=9)
    p.glow((28, 118), 34, hexc("#7dff6a"), 0.85)
    p.shape("ellipse", (10, 100, 46, 136), hexc("#7de35a"), light=1.5)
    p.shape("ellipse", (26, 158, 48, 180), stem)
    return p.finish(ground_shadow=(50, 222, 210, 246))


def cellar_warden():
    """Elite jailer: hooded brute with a huge axe (faces left)."""
    hood = hexc("#3b2230")
    apron = hexc("#6b4a33")
    skin = hexc("#c9a58a")
    iron = hexc("#7d8792")
    p = Painter(SIZE, SIZE)
    # legs and boots
    for x in (104, 146):
        p.shape("rect", (x, 186, x + 26, 228), hexc("#4a3a36"), radius=8)
        p.shape("rect", (x - 8, 216, x + 32, 240), hexc("#2f2422"), radius=8)
    # back arm
    p.shape("line", [(196, 112), (214, 160), (200, 190)], skin, width=22)
    p.shape("rect", (192, 150, 222, 170), iron, radius=5)
    # hulking torso and belly
    p.shape("ellipse", (70, 76, 214, 208), skin, depth=0.1)
    p.shape("poly", [(92, 122), (192, 122), (200, 214), (84, 214)], apron, depth=0.12)
    p.shape("rect", (80, 160, 206, 176), hexc("#3a2a20"), radius=5, depth=0.3)
    p.shape("rect", (132, 157, 154, 179), GOLD, radius=3, depth=0.3)
    # key ring on the belt
    p.shape("ellipse", (164, 170, 190, 196), (0, 0, 0, 0), shadow=0, light=0, line=2.5, ink=GOLD)
    for dx, dy in ((170, 190), (182, 192)):
        p.shape("rect", (dx, dy, dx + 6, dy + 18), GOLD, radius=2, line=1)
    # chains across the chest
    for i in range(9):
        x = 84 + i * 13
        y = 90 + i * 8
        p.shape("ellipse", (x, y, x + 16, y + 11), iron, line=1.2, depth=0.3)
    # hood and eyes
    p.shape("poly", [(96, 20), (170, 26), (182, 104), (84, 104)], hood, depth=0.1)
    p.shape("ellipse", (90, 16, 176, 86), hood, depth=0.1)
    p.shape("poly", [(134, 20), (150, 0), (160, 30)], hood)
    p.shape("ellipse", (98, 48, 122, 64), DARK, shadow=0, light=0, line=0)
    p.shape("ellipse", (130, 48, 154, 64), DARK, shadow=0, light=0, line=0)
    p.glow((110, 56), 14, hexc("#ffcc33"), 0.9)
    p.glow((142, 56), 14, hexc("#ffcc33"), 0.9)
    p.flat("ellipse", (105, 52, 115, 60), hexc("#ffe680"))
    p.flat("ellipse", (137, 52, 147, 60), hexc("#ffe680"))
    # huge axe held in front
    p.shape("line", [(150, 214), (58, 34)], hexc("#6b4428"), width=10)
    p.shape("poly", [(64, 36), (14, 18), (4, 66), (26, 98), (78, 66)], iron, depth=0.25, light=1.35)
    p.shape("poly", [(14, 18), (4, 66), (26, 98), (20, 60)], shade(STEEL, 1.2), line=0, shadow=0)
    p.shape("line", [(60, 44), (74, 62)], hexc("#2f2422"), width=8)
    # front arm gripping the haft
    p.shape("line", [(92, 110), (72, 150), (104, 150)], skin, width=22)
    p.shape("rect", (60, 136, 90, 156), iron, radius=5)
    p.shape("ellipse", (96, 138, 124, 164), skin)
    return p.finish(ground_shadow=(40, 224, 230, 250))


def mimic():
    """Treasure chest with teeth (faces left)."""
    wood = hexc("#a0652f")
    band = hexc("#e2ae3c")
    mouth = hexc("#5a1624")
    p = Painter(SIZE, SIZE)
    # spilled coins
    for x, y in ((20, 222), (44, 230), (204, 228), (226, 220)):
        p.shape("ellipse", (x, y, x + 20, y + 12), band, line=1.2)
    # base of the chest
    p.shape("rect", (40, 140, 220, 232), wood, radius=10, depth=0.1)
    for x in (58, 196):
        p.shape("rect", (x - 6, 140, x + 12, 232), band, radius=3, depth=0.2)
    p.shape("rect", (116, 170, 146, 200), band, radius=5)
    p.flat("ellipse", (126, 178, 136, 188), DARK)
    # open mouth (inside the lid)
    p.shape("poly", [(40, 146), (220, 146), (212, 70), (52, 42)], mouth, depth=0.08)
    # lower teeth
    for i in range(8):
        x = 48 + i * 21
        p.shape("poly", [(x, 148), (x + 18, 148), (x + 9, 124)], WHITE, line=1.2, depth=0.2)
    # lid, tilted open toward the back
    p.shape("poly", [(40, 40), (212, 66), (226, 28), (68, 0)], wood, depth=0.12)
    p.shape("poly", [(96, 10), (118, 13), (106, 50), (84, 47)], band, depth=0.2, line=1.2)
    p.shape("poly", [(172, 23), (192, 26), (184, 62), (162, 59)], band, depth=0.2, line=1.2)
    # upper teeth hanging from the lid
    for i in range(7):
        x0 = 52 + i * 23
        y0 = 43 + i * 3.6
        p.shape("poly", [(x0, y0), (x0 + 20, y0 + 3), (x0 + 12, y0 + 30)], WHITE, line=1.2, depth=0.2)
    # tongue lolling out over the front edge
    tongue = hexc("#e0607a")
    p.shape("line", [(150, 128), (100, 138), (62, 162), (48, 196)], tongue, width=30, depth=0.2, light=1.3)
    p.shape("line", [(116, 136), (70, 164), (52, 196)], shade(tongue, 0.7), width=3, shadow=0, light=0, line=0)
    # eyes on the lid
    for cx in (110, 170):
        p.shape("ellipse", (cx - 16, 12 + (cx - 110) * 0.14, cx + 14, 38 + (cx - 110) * 0.14), hexc("#ffe14a"),
                light=1.4)
        p.flat("rect", (cx - 3, 14 + (cx - 110) * 0.14, cx + 3, 36 + (cx - 110) * 0.14), DARK, radius=2)
    return p.finish(ground_shadow=(28, 222, 236, 250))


BOSS_SIZE = 384


def bone_king():
    """Boss: skeleton king with crown, royal robe and a necrotic staff (faces left)."""
    robe = hexc("#5b2a86")
    trim = hexc("#f4efe6")
    glow = hexc("#6dffcf")
    p = Painter(BOSS_SIZE, BOSS_SIZE)
    # tattered cape
    p.shape("poly", [(150, 120), (330, 130), (360, 350), (320, 330), (300, 360), (262, 334), (230, 362),
                     (200, 336), (166, 358)], shade(robe, 0.75), depth=0.06)
    # robe body
    p.shape("poly", [(146, 140), (262, 140), (300, 356), (112, 356)], robe, depth=0.08)
    p.shape("rect", (110, 336, 302, 362), trim, radius=10, depth=0.25)
    for x in (140, 186, 232, 276):
        p.flat("ellipse", (x, 344, x + 8, 354), DARK)
    p.shape("rect", (196, 140, 212, 340), hexc("#e7b440"), radius=4, depth=0.25)
    # ribcage peeking out of the robe
    p.shape("poly", [(170, 150), (238, 150), (226, 226), (182, 226)], hexc("#2a1838"), line=1.2)
    for i, y in enumerate((162, 180, 198)):
        w = 26 - i * 4
        p.shape("rect", (204 - w, y, 204 + w, y + 8), BONE, radius=4, line=1.2)
    # ermine collar
    p.shape("ellipse", (126, 118, 286, 170), trim, depth=0.15)
    for x, y in ((150, 140), (190, 150), (232, 150), (266, 138)):
        p.flat("ellipse", (x, y, x + 7, y + 10), DARK)
    # back arm (bony hand on hip)
    p.shape("line", [(270, 160), (298, 214), (270, 238)], BONE, width=12)
    # skull
    p.shape("ellipse", (136, 30, 256, 142), BONE, depth=0.12)
    p.shape("rect", (156, 116, 232, 150), BONE, radius=12)
    for x in (168, 182, 196, 210):
        p.shape("line", [(x, 128), (x, 148)], DARK, width=3, shadow=0, light=0, line=0)
    p.shape("ellipse", (148, 70, 182, 104), DARK, shadow=0, light=0, line=0)
    p.shape("ellipse", (196, 70, 230, 104), DARK, shadow=0, light=0, line=0)
    p.glow((165, 87), 22, glow, 0.95)
    p.glow((213, 87), 22, glow, 0.95)
    p.flat("ellipse", (158, 81, 170, 93), hexc("#d8fff2"))
    p.flat("ellipse", (206, 81, 218, 93), hexc("#d8fff2"))
    p.shape("poly", [(184, 108), (196, 108), (190, 120)], DARK, shadow=0, light=0, line=0)
    p.shape("line", [(186, 44), (196, 60), (188, 70)], shade(BONE, 0.6), width=2.5, shadow=0, light=0, line=0)
    # crown
    crown = [(132, 50), (132, 6), (152, 28), (172, 0), (192, 26), (212, 0), (232, 28), (252, 6), (256, 50)]
    p.shape("poly", crown, hexc("#f1c24a"), depth=0.15, light=1.35)
    p.shape("rect", (130, 38, 258, 54), hexc("#d49a2a"), radius=4, depth=0.3)
    for x, c in ((150, "#e0303a"), (186, "#3ad0ff"), (222, "#e0303a")):
        p.shape("ellipse", (x, 40, x + 14, 52), hexc(c), light=1.6, line=1.2)
    # staff held in front, with a glowing skull orb
    p.shape("line", [(78, 110), (104, 360)], hexc("#4a3226"), width=12)
    p.shape("line", [(60, 96), (98, 90)], hexc("#e7b440"), width=6)
    p.glow((78, 64), 60, glow, 0.9)
    p.shape("ellipse", (50, 34, 106, 94), hexc("#b9ffe8"), light=1.3, depth=0.1)
    p.flat("ellipse", (62, 56, 74, 68), hexc("#1f5a4a"))
    p.flat("ellipse", (82, 56, 94, 68), hexc("#1f5a4a"))
    # front arm holding the staff
    p.shape("line", [(150, 170), (116, 214), (96, 190)], robe, width=26)
    p.shape("ellipse", (80, 176, 114, 206), BONE)
    for y in (180, 190, 200):
        p.shape("line", [(80, y), (72, y + 4)], BONE, width=6, line=1.2)
    return p.finish(outline=3, ground_shadow=(70, 340, 350, 378))


SPRITES = {
    "player/warrior": warrior,
    "enemies/cellar_rat": cellar_rat,
    "enemies/skeleton_guard": skeleton_guard,
    "enemies/mushroom_mage": mushroom_mage,
    "enemies/cellar_warden": cellar_warden,
    "enemies/mimic": mimic,
    "enemies/bone_king": bone_king,
}

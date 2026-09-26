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


SPRITES = {
    "player/warrior": warrior,
    "enemies/cellar_rat": cellar_rat,
    "enemies/skeleton_guard": skeleton_guard,
    "enemies/mushroom_mage": mushroom_mage,
}

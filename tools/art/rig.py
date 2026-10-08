"""Cut-out rigs: characters drawn as separate parts that the game moves (docs/16).

A rig is a folder assets/rigs/<id>/ with one PNG per part and rig.json:

    {
      "id": "warrior",
      "canvas": [1024, 1024],        # the design canvas every coordinate below refers to
      "feet": [512, 972],            # ground contact point (centre between the feet)
      "facing": "right",             # heroes face right, enemies face left
      "kind": "humanoid",            # humanoid | beast | blob | flyer | floater | dragon | serpent
      "parts": [
        {"name": "torso", "png": "torso.png", "parent": "hips", "role": "torso",
         "pivot": [510, 600], "rect": [400, 380, 230, 260], "z": 10, "blend": "normal"},
        ...
      ]
    }

rect is where the part's PNG sits on the canvas, so drawing every part at its rect in z order
rebuilds the flat picture. pivot is the joint the part turns around (canvas pixels); a part
follows its parent's movement. The game animates parts by role:

    root        body anchor (hips, main body mass); everything hangs off it
    torso head jaw
    hair        secondary sway: plume, hood tip, ponytail, mane, tentacle, flame crest
    cape        cloth that waves behind the body
    arm_front_upper arm_front_lower weapon       (front = nearer the camera)
    arm_back_upper  arm_back_lower  offhand      (shield, orb, second dagger)
    leg_front_upper leg_front_lower leg_back_upper leg_back_lower (or leg_front / leg_back)
    tail        (a chain tail_1 -> tail_2 -> ... all with role "tail")
    wing_front wing_back
    float       pieces that hover and bob on their own (floating rocks, orbiting shards)
    extra       static detail that just follows its parent
    fx          glow drawn additively (blend "add"); pulses

Usage from a generator:

    rb = RigBuilder("warrior", (1024, 1024), feet=(512, 972), facing="right", kind="humanoid")
    rb.add("hips", hips_img, parent="", role="root", pivot=(512, 610), z=5)
    rb.add("torso", torso_img, parent="hips", role="torso", pivot=(512, 600), z=10)
    ...
    rb.save(flat="sprites/player/warrior.png")

Each image passed to add() is a full-canvas RGBA layer holding only that part. Parts must overlap
their parent around the joint (a rounded cap under the parent), so a turn of +-25 degrees never
opens a gap. `python3 tools/art/rig.py <id>` writes a pose sheet to check exactly that.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
RIGS = os.path.join(ROOT, "assets", "rigs")

ROLES = {
    "root", "torso", "head", "jaw", "hair", "cape",
    "arm_front_upper", "arm_front_lower", "weapon", "arm_back_upper", "arm_back_lower", "offhand",
    "leg_front_upper", "leg_front_lower", "leg_back_upper", "leg_back_lower", "leg_front", "leg_back",
    "tail", "wing_front", "wing_back", "float", "extra", "fx",
}
KINDS = {"humanoid", "beast", "blob", "flyer", "floater", "dragon", "serpent"}


class RigBuilder:
    def __init__(self, rig_id, canvas, feet, facing="left", kind="humanoid", out_root=RIGS):
        assert facing in ("left", "right")
        assert kind in KINDS, kind
        self.id = rig_id
        self.canvas = tuple(canvas)
        self.feet = tuple(feet)
        self.facing = facing
        self.kind = kind
        self.dir = os.path.join(out_root, rig_id)
        self.parts = []

    def add(self, name, img, parent, role, pivot, z, blend="normal"):
        assert role in ROLES, role
        assert img.size == self.canvas, (name, img.size)
        assert not any(p["name"] == name for p in self.parts), name
        assert parent == "" or any(p["name"] == parent for p in self.parts), f"{name}: add parent {parent} first"
        self.parts.append({"name": name, "img": img.convert("RGBA"), "parent": parent, "role": role,
                           "pivot": [int(round(pivot[0])), int(round(pivot[1]))], "z": int(z), "blend": blend})

    def flat(self):
        out = Image.new("RGBA", self.canvas, (0, 0, 0, 0))
        for p in sorted(self.parts, key=lambda p: p["z"]):
            if p["blend"] == "add":
                continue
            out.alpha_composite(p["img"])
        return out

    def save(self, flat=None, flat_size=512):
        """Writes the part PNGs and rig.json; with `flat` ("sprites/player/warrior.png") also the
        still picture (downscaled to flat_size) that menus and icons use."""
        os.makedirs(self.dir, exist_ok=True)
        for f in os.listdir(self.dir):
            if f.endswith(".png") or f.endswith(".png.import"):
                os.remove(os.path.join(self.dir, f))
        entries = []
        for p in self.parts:
            box = p["img"].getbbox()
            if box is None:
                raise ValueError(f"{self.id}: part {p['name']} is empty")
            x0, y0, x1, y1 = box
            x0, y0 = max(0, x0 - 2), max(0, y0 - 2)
            x1, y1 = min(self.canvas[0], x1 + 2), min(self.canvas[1], y1 + 2)
            p["img"].crop((x0, y0, x1, y1)).save(os.path.join(self.dir, p["name"] + ".png"), optimize=True)
            entries.append({"name": p["name"], "png": p["name"] + ".png", "parent": p["parent"],
                            "role": p["role"], "pivot": p["pivot"], "rect": [x0, y0, x1 - x0, y1 - y0],
                            "z": p["z"], "blend": p["blend"]})
        rig = {"id": self.id, "canvas": list(self.canvas), "feet": list(self.feet), "facing": self.facing,
               "kind": self.kind, "parts": entries}
        with open(os.path.join(self.dir, "rig.json"), "w") as fh:
            json.dump(rig, fh, indent=1)
        print("wrote", os.path.relpath(os.path.join(self.dir, "rig.json"), ROOT), f"({len(entries)} parts)")
        if flat:
            img = self.flat()
            if flat_size and img.size[0] != flat_size:
                img = img.resize((flat_size, int(flat_size * img.size[1] / img.size[0])), Image.LANCZOS)
            path = os.path.join(ROOT, "assets", flat)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.save(path, optimize=True)
            print("wrote", os.path.relpath(path, ROOT))
        return rig


# ---------------------------------------------------------------- previews

def load(rig_id, root=None):
    d = os.path.join(root or RIGS, rig_id)
    with open(os.path.join(d, "rig.json")) as fh:
        rig = json.load(fh)
    for p in rig["parts"]:
        p["img"] = Image.open(os.path.join(d, p["png"])).convert("RGBA")
    return rig


def _mat_mul(a, b):
    return (a[0] * b[0] + a[1] * b[3], a[0] * b[1] + a[1] * b[4], a[0] * b[2] + a[1] * b[5] + a[2],
            a[3] * b[0] + a[4] * b[3], a[3] * b[1] + a[4] * b[4], a[3] * b[2] + a[4] * b[5] + a[5])


def _about(pivot, deg, dx=0.0, dy=0.0, sx=1.0, sy=1.0):
    """Affine (a,b,c,d,e,f) mapping x' = a x + b y + c: scale and turn about pivot, then move."""
    r = math.radians(deg)
    cs, sn = math.cos(r), math.sin(r)
    px, py = pivot
    a, b, d, e = cs * sx, -sn * sy, sn * sx, cs * sy
    return (a, b, px - a * px - b * py + dx, d, e, py - d * px - e * py + dy)


def _inverse(m):
    a, b, c, d, e, f = m
    det = a * e - b * d
    ia, ib, id_, ie = e / det, -b / det, -d / det, a / det
    return (ia, ib, -(ia * c + ib * f), id_, ie, -(id_ * c + ie * f))


def pose(rig, angles=None, moves=None, scale=0.5, bg=None):
    """Renders the rig with some parts turned. angles: {part or role: degrees}; moves: {part: (dx, dy)}.
    Angles are for a right-facing rig; they are mirrored for left-facing ones."""
    angles, moves = angles or {}, moves or {}
    flip = -1 if rig["facing"] == "left" else 1
    w, h = rig["canvas"]
    out = Image.new("RGBA", (int(w * scale), int(h * scale)), bg or (0, 0, 0, 0))
    mats = {}
    for p in rig["parts"]:
        ang = angles.get(p["name"], angles.get(p["role"], 0.0)) * flip
        dx, dy = moves.get(p["name"], moves.get(p["role"], (0, 0)))
        local = _about(p["pivot"], ang, dx * flip, dy)
        parent = mats.get(p["parent"], (1, 0, 0, 0, 1, 0))
        mats[p["name"]] = _mat_mul(parent, local)
    view = (scale, 0, 0, 0, scale, 0)
    for p in sorted(rig["parts"], key=lambda p: p["z"]):
        x, y, pw, ph = p["rect"]
        place = (1, 0, x, 0, 1, y)
        m = _mat_mul(view, _mat_mul(mats[p["name"]], place))
        layer = p["img"].transform(out.size, Image.AFFINE, _inverse(m), resample=Image.BICUBIC)
        if p["blend"] == "add":
            glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
            glow.alpha_composite(layer)
            out = Image.alpha_composite(out, glow)
        else:
            out.alpha_composite(layer)
    return out


POSES = {
    "rest": {},
    "breathe in": {"torso": -2, "head": 3, "arm_front_upper": -4, "arm_back_upper": 4, "hair": -8,
                   "cape": 8, "tail": 10, "wing_front": -12, "wing_back": 10, "jaw": 0},
    "wind-up": {"root": -6, "torso": -8, "head": -4, "arm_front_upper": 60, "arm_front_lower": 30,
                "weapon": 10, "arm_back_upper": 20, "leg_front_upper": 10, "leg_back_upper": -10,
                "hair": 12, "cape": 14, "tail": -18, "wing_front": 25, "wing_back": -20, "jaw": 12},
    "strike": {"root": 8, "torso": 10, "head": 4, "arm_front_upper": -70, "arm_front_lower": -10,
               "weapon": -10, "arm_back_upper": -15, "leg_front_upper": -14, "leg_back_upper": 14,
               "hair": -14, "cape": -18, "tail": 20, "wing_front": -25, "wing_back": 22, "jaw": 20},
    "hit": {"root": -10, "torso": -12, "head": -14, "arm_front_upper": 25, "arm_back_upper": 20,
            "hair": 16, "cape": 18, "tail": -12, "wing_front": 18, "jaw": 8},
}


def pose_sheet(rig_id, out_png, scale=0.4, root=None):
    """Every test pose side by side over a mid-grey backdrop, so joint gaps and loose parts show."""
    rig = load(rig_id, root or RIGS)
    tiles = []
    for name, angles in POSES.items():
        img = pose(rig, angles, scale=scale, bg=(92, 92, 104, 255))
        d = ImageDraw.Draw(img)
        d.text((8, 6), name, fill=(255, 255, 255, 255))
        fx, fy = rig["feet"]
        d.ellipse([fx * scale - 4, fy * scale - 4, fx * scale + 4, fy * scale + 4], outline=(255, 80, 80, 255))
        tiles.append(img)
    w, h = tiles[0].size
    sheet = Image.new("RGBA", (w * len(tiles), h), (0, 0, 0, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * w, 0))
    sheet.save(out_png)
    return out_png


if __name__ == "__main__":
    for rid in sys.argv[1:]:
        print(pose_sheet(rid, os.path.join("/tmp", f"rig_{rid}.png")))

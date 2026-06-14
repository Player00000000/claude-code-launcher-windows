"""
make_sprites.py — Generate Summer sprite sheet from Pom.png.
Run: py.exe make_sprites.py  (Windows)  or  python3 make_sprites.py  (WSL)
Output: static/summer.png  (15 frames × 64×64, one row = 960×64 RGBA)
"""
import os
from PIL import Image, ImageDraw

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC        = os.path.join(SCRIPT_DIR, "Pom_64x64.png")
OUT        = os.path.join(SCRIPT_DIR, "static", "summer.png")

FRAME_W, FRAME_H = 64, 64


def load_base():
    """Load Pom_64x64.png — already 64×64 RGBA with transparent background."""
    return Image.open(SRC).convert("RGBA")


def shift_body(base, dy=0, dx=0):
    """Shift entire image by dx,dy pixels (blank fills transparent)."""
    out = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    out.paste(base, (dx, dy))
    return out


def shift_legs(base, dx=0):
    """Shift bottom 18px of image horizontally (leg movement)."""
    out = base.copy()
    legs_y = FRAME_H - 18
    legs   = base.crop((0, legs_y, FRAME_W, FRAME_H))
    # blank the legs area
    draw   = ImageDraw.Draw(out)
    draw.rectangle([0, legs_y, FRAME_W - 1, FRAME_H - 1], fill=(0, 0, 0, 0))
    # paste shifted (clip within bounds)
    out.paste(legs, (dx, legs_y))
    return out


def squish_legs(base, scale_h=0.5):
    """Compress bottom 20px vertically (sitting pose)."""
    out      = base.copy()
    legs_y   = FRAME_H - 20
    legs     = base.crop((0, legs_y, FRAME_W, FRAME_H))
    new_h    = max(1, int(20 * scale_h))
    legs_sm  = legs.resize((FRAME_W, new_h), Image.NEAREST)
    draw     = ImageDraw.Draw(out)
    draw.rectangle([0, legs_y, FRAME_W - 1, FRAME_H - 1], fill=(0, 0, 0, 0))
    paste_y  = FRAME_H - new_h
    out.paste(legs_sm, (0, paste_y))
    return out


def sleeping(base):
    """Rotate 90° CW, fit into 64×64."""
    rot = base.rotate(-90, expand=False)
    return rot


def add_zzz(img):
    """Draw white 'z' pixels top-right."""
    out  = img.copy()
    draw = ImageDraw.Draw(out)
    # small z dots: top-right corner
    for dot in [(56, 4), (58, 6), (54, 8)]:
        draw.point(dot, fill=(255, 255, 255, 220))
    return out


def brighten_mouth(base, extra_width=0):
    """Brighten mouth region to simulate barking open mouth."""
    out  = base.copy()
    draw = ImageDraw.Draw(out)
    x1   = 24 - extra_width
    x2   = 40 + extra_width
    y1, y2 = 36, 42
    # semi-transparent pink overlay
    overlay = Image.new("RGBA", (x2 - x1, y2 - y1), (255, 140, 140, 120))
    out.paste(overlay, (x1, y1), overlay)
    return out


def make_sheet(frames):
    sheet = Image.new("RGBA", (FRAME_W * len(frames), FRAME_H), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * FRAME_W, 0))
    return sheet


if __name__ == "__main__":
    base = load_base()

    frames = [
        # WALK 1-4
        shift_legs(base,  0),
        shift_legs(base, +2),
        shift_legs(base,  0),
        shift_legs(base, -2),
        # IDLE 1-2
        base,
        shift_body(base, dy=-1),
        # SIT 1-2
        squish_legs(base, 0.50),
        squish_legs(base, 0.65),
        # SLEEP 1-2
        sleeping(base),
        add_zzz(sleeping(base)),
        # JUMP 1-3
        shift_body(base, dy=-4),
        shift_body(base, dy=-8),
        shift_body(base, dy=-4),
        # BARK 1-2
        brighten_mouth(base, 0),
        brighten_mouth(base, 2),
    ]

    sheet = make_sheet(frames)
    sheet.save(OUT)
    print(f"Saved {OUT}  ({len(frames)} frames, {sheet.width}×{sheet.height})")

"""
make_sprites.py — Generate Summer sprite sheet.
Run: py.exe make_sprites.py  (Windows)  or  python3 make_sprites.py  (WSL)
Output: static/summer.png  (15 frames × 64×64, one row = 960×64 RGBA)

Source: ChatGPT Image Jun 14, 2026, 08_59_16 AM.png  (4×3 grid, 12 frames)
Fallback: Pom_64x64.png
"""
import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_SHEET  = os.path.join(SCRIPT_DIR, "ChatGPT Image Jun 14, 2026, 08_59_16 AM.png")
SRC_SINGLE = os.path.join(SCRIPT_DIR, "Pom_64x64.png")
OUT        = os.path.join(SCRIPT_DIR, "static", "summer.png")

FRAME_W, FRAME_H = 64, 64

# Detected frame bounding boxes in source sprite sheet (x1, y1, x2, y2)
GRID = [
    # Row 1 — walk frames
    (175, 146, 452, 395),   # walk_a
    (462, 146, 735, 395),   # walk_b
    (760, 146, 1019, 395),  # walk_c
    (1039, 146, 1310, 395), # walk_d
    # Row 2 — sit + sleep
    (175, 446, 452, 661),   # sit_a
    (462, 446, 735, 661),   # sit_b
    (760, 446, 1019, 661),  # sleep_a
    (1039, 446, 1310, 661), # sleep_b
    # Row 3 — jump + bark
    (175, 700, 452, 894),   # jump_a
    (462, 700, 735, 894),   # jump_b
    (760, 700, 1019, 894),  # bark_a
    (1039, 700, 1310, 894), # bark_b
]

# 15-frame layout: walk(4) idle(2) sit(2) sleep(2) jump(3) bark(2)
# Maps to GRID indices above (12 frames, some reused)
FRAME_MAP = [
    0, 1, 2, 3,   # walk:  walk_a walk_b walk_c walk_d
    0, 1,          # idle:  reuse walk_a walk_b (slight movement)
    4, 5,          # sit:   sit_a sit_b
    6, 7,          # sleep: sleep_a sleep_b
    8, 9, 8,       # jump:  jump_a jump_b jump_a (bounce)
    10, 11,        # bark:  bark_a bark_b
]


def cut_frame(sheet, box):
    """Crop box from sheet, resize to 64×64 LANCZOS, return RGBA."""
    cropped = sheet.crop(box)
    return cropped.resize((FRAME_W, FRAME_H), Image.LANCZOS)


def make_sheet(frames):
    sheet = Image.new("RGBA", (FRAME_W * len(frames), FRAME_H), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * FRAME_W, 0), f)
    return sheet


if __name__ == "__main__":
    if os.path.exists(SRC_SHEET):
        print(f"Using: {os.path.basename(SRC_SHEET)}")
        source = Image.open(SRC_SHEET).convert("RGBA")
        grid_frames = [cut_frame(source, box) for box in GRID]
        # Walk frames (0-3) face left — flip so pom faces right by default
        for i in range(4):
            grid_frames[i] = grid_frames[i].transpose(Image.FLIP_LEFT_RIGHT)
        frames = [grid_frames[i] for i in FRAME_MAP]
    else:
        print(f"Sheet not found, falling back to {os.path.basename(SRC_SINGLE)}")
        from PIL import ImageDraw
        base = Image.open(SRC_SINGLE).convert("RGBA").transpose(Image.FLIP_LEFT_RIGHT)

        def shift_body(b, dy=0, dx=0):
            out = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
            out.paste(b, (dx, dy))
            return out

        def shift_legs(b, dx=0):
            out = b.copy()
            ly = FRAME_H - 18
            legs = b.crop((0, ly, FRAME_W, FRAME_H))
            ImageDraw.Draw(out).rectangle([0, ly, FRAME_W-1, FRAME_H-1], fill=(0,0,0,0))
            out.paste(legs, (dx, ly))
            return out

        def squish_legs(b, sh=0.5):
            out = b.copy()
            ly = FRAME_H - 20
            legs = b.crop((0, ly, FRAME_W, FRAME_H))
            nh = max(1, int(20 * sh))
            legs_sm = legs.resize((FRAME_W, nh), Image.NEAREST)
            ImageDraw.Draw(out).rectangle([0, ly, FRAME_W-1, FRAME_H-1], fill=(0,0,0,0))
            out.paste(legs_sm, (0, FRAME_H - nh))
            return out

        def sleeping(b):
            return b.rotate(-90, expand=False)

        def add_zzz(img):
            out = img.copy()
            draw = ImageDraw.Draw(out)
            for dot in [(56, 4), (58, 6), (54, 8)]:
                draw.point(dot, fill=(255, 255, 255, 220))
            return out

        def bark(b, extra=0):
            out = b.copy()
            overlay = Image.new("RGBA", (16 + extra*2, 6), (255, 140, 140, 120))
            out.paste(overlay, (24 - extra, 36), overlay)
            return out

        frames = [
            shift_legs(base, 0), shift_legs(base, 2),
            shift_legs(base, 0), shift_legs(base, -2),
            base, shift_body(base, dy=-1),
            squish_legs(base, 0.50), squish_legs(base, 0.65),
            sleeping(base), add_zzz(sleeping(base)),
            shift_body(base, dy=-4), shift_body(base, dy=-8), shift_body(base, dy=-4),
            bark(base, 0), bark(base, 2),
        ]

    sheet = make_sheet(frames)
    sheet.save(OUT)
    print(f"Saved {OUT}  ({len(frames)} frames, {sheet.width}×{sheet.height})")

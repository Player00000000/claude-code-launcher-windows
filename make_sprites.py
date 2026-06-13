"""
make_sprites.py — Generate Summer the pomeranian sprite sheet.
Run once: py.exe make_sprites.py
Outputs: static/summer.png (15 frames, 16x16 each, one row = 240x16)
Scaled to 48x48 via CSS image-rendering:pixelated.
"""
import os
from PIL import Image

# Palette
O = (232, 146, 58)   # orange fur
C = (245, 215, 160)  # cream belly/face
D = (58, 42, 26)     # dark outline
P = (255, 180, 180)  # pink tongue/nose
W = (255, 255, 255)  # white highlight eyes
B = (40, 40, 80)     # dark eye
_ = (0, 0, 0, 0)     # transparent

def px(row_strings, palette):
    """Convert list of 16 strings (16 chars) to a 16x16 RGBA image."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(row_strings):
        for x, ch in enumerate(row):
            if ch in palette:
                img.putpixel((x, y), palette[ch] + ((255,) if len(palette[ch]) == 3 else ()))
    return img

# Character mapping
pal = {
    'O': O + (255,),
    'C': C + (255,),
    'D': D + (255,),
    'P': P + (255,),
    'W': W + (255,),
    'B': B + (255,),
    '.': (0, 0, 0, 0),
}

# Helper to pad rows to 16 chars
def r(s): return s.ljust(16, '.')

# ── Frame definitions (16 rows of 16 chars each) ──

WALK1 = [
    r('....DDDDD.......'),
    r('...DOOOOOD......'),
    r('..DOOOOOODD.....'),
    r('.DOOOCCOOOOD....'),
    r('.DOOOCCOOODD....'),
    r('.DOOOOOOOOOD....'),
    r('..DOOOOOOOD.....'),
    r('...DOOOOOD......'),
    r('....DOOOD.......'),
    r('...DOOOOOD......'),
    r('..DOOOOOOOD.....'),
    r('.DOOOOOOOOOD....'),
    r('.DO......OOD....'),
    r('..D......DD.....'),
    r('...DDDD.........'),
    r('................'),
]

WALK2 = [
    r('....DDDDD.......'),
    r('...DOOOOOD......'),
    r('..DOOOOOODD.....'),
    r('.DOOOCCOOOOD....'),
    r('.DOOOCCOOODD....'),
    r('.DOOOOOOOOOD....'),
    r('..DOOOOOOOD.....'),
    r('...DOOOOOD......'),
    r('....DOOOD.......'),
    r('...DOOOOOD......'),
    r'..DOOOOOOOD.....',
    r'.DOOOOOOOOOOD...',
    r'.DO.....OOOOD...',
    r'..DD....DDDD....',
    r'................',
    r'................',
]

WALK3 = [
    r('....DDDDD.......'),
    r('...DOOOOOD......'),
    r'..DOOOOOODD.....',
    r'.DOOOCCOOOOD....',
    r'.DOOOCCOOODD....',
    r'.DOOOOOOOOOD....',
    r'..DOOOOOOOD.....',
    r'...DOOOOOD......',
    r'....DOOOD.......',
    r'..DDOOOOODD.....',
    r'.DOOOOOOOOOD....',
    r'.DO.....OOOD....',
    r'..D.....DOOD....',
    r'...DDDDDDD......',
    r'................',
    r'................',
]

WALK4 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOCCOOOOD....',
    r'.DOOOCCOOODD....',
    r'.DOOOOOOOOOD....',
    r'..DOOOOOOOD.....',
    r'...DOOOOOD......',
    r'....DOOOD.......',
    r'...DOOOOOD......',
    r'..DOOOOOOOOD....',
    r'.DOOOOOOOOOD....',
    r'.DOO....OOOD....',
    r'..DDDDDDDDD.....',
    r'................',
    r'................',
]

IDLE1 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOCPOOOOD...',
    r'..DOOOOOOOD.....',
    r'...DOOOOOD......',
    r'....DOOOD.......',
    r'...DOOOOOOD.....',
    r'..DOOOOOOOOOD...',
    r'.DOO......OOOD..',
    r'.DD........DDD..',
    r'................',
    r'................',
    r'................',
]

IDLE2 = [
    r'......DDDDD.....',
    r'.....DOOOOOD....',
    r'....DOOOOOODD...',
    r'...DOOOWBOOOOD..',
    r'...DOOOWBOOODD..',
    r'...DOOOOCPOOOOD.',
    r'....DOOOOOOOD...',
    r'.....DOOOOOD....',
    r'......DOOOD.....',
    r'.....DOOOOOOD...',
    r'....DOOOOOOOOOD.',
    r'...DOO......OOOD',
    r'...DD........DDD',
    r'................',
    r'................',
    r'................',
]

SIT1 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOCPOOOOD...',
    r'..DOOOOOOOD.....',
    r'..DOOOOOOOD.....',
    r'.DDOOOOOOODD....',
    r'.DOOOOOOOOOD....',
    r'.DOOOOOOOOOD....',
    r'.DOOOOOOOOOD....',
    r'.DDDDDDDDDDD....',
    r'................',
    r'................',
    r'................',
]

SIT2 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOD.....',
    r'.DOOOWBOODD.....',
    r'.DOOOOCPOOOD....',
    r'..DOOOOOOOD.....',
    r'..DOOOOOOOD.....',
    r'.DDOOOOOOODD....',
    r'.DOOOOOOOOOOD...',
    r'.DOOOOOOOOOOD...',
    r'.DOOOOOOOOOOD...',
    r'.DDDDDDDDDDDD...',
    r'................',
    r'................',
    r'................',
]

SLEEP1 = [
    r'................',
    r'................',
    r'................',
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOOOOD....',
    r'.DOOOOOOOOOOD...',
    r'.DOOOOOOOOODD...',
    r'.DOOOOOOOOOOD...',
    r'.DDDDDDDDDDD....',
    r'..DDDDDDDDD.....',
    r'..DO....DOOD....',
    r'..DO....DOOD....',
    r'..DDDDDDDDD.....',
    r'................',
    r'................',
]

SLEEP2 = [
    r'.....D.....D....',
    r'....D.D...D.D...',
    r'...D...D.D...D..',
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOOOOD....',
    r'.DOOOOOOOOOOD...',
    r'.DOOOOOOOOODD...',
    r'.DOOOOOOOOOOD...',
    r'.DDDDDDDDDDD....',
    r'..DDDDDDDDD.....',
    r'..DO....DOOD....',
    r'..DO....DOOD....',
    r'..DDDDDDDDD.....',
    r'................',
    r'................',
]

JUMP1 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOCPOOOOD...',
    r'..DOOOOOOOD.....',
    r'...DOOOOOD......',
    r'..DOOOOOOOOD....',
    r'.DOOO....OOOD...',
    r'.DOO......OOD...',
    r'.DD........DD...',
    r'................',
    r'................',
    r'................',
    r'................',
]

JUMP2 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOCPOOOOD...',
    r'..DOOOOOOOOD....',
    r'..DOOOOOOOD.....',
    r'.DOOOOOOOOOD....',
    r'DOO......OOOD...',
    r'DO........OOD...',
    r'DD........DDD...',
    r'................',
    r'................',
    r'................',
    r'................',
]

JUMP3 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOCPOOOOD...',
    r'..DOOOOOOOD.....',
    r'...DOOOOOD......',
    r'....DOOOD.......',
    r'...DOOOOOOD.....',
    r'..DOOOOOOOOOD...',
    r'.DOO......OOOD..',
    r'.DD........DDD..',
    r'................',
    r'................',
    r'................',
]

BARK1 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOPPOOOD....',
    r'..DOOPPPOOD.....',
    r'...DOOOOOD......',
    r'....DOOOD.......',
    r'...DOOOOOOD.....',
    r'..DOOOOOOOOOD...',
    r'.DOO......OOOD..',
    r'.DD........DDD..',
    r'................',
    r'................',
    r'................',
]

BARK2 = [
    r'....DDDDD.......',
    r'...DOOOOOD......',
    r'..DOOOOOODD.....',
    r'.DOOOWBOOOOD....',
    r'.DOOOWBOOODD....',
    r'.DOOOOPP.OOD....',
    r'..DOOOPPPD......',
    r'...DOOOOOD......',
    r'....DOOOD.......',
    r'...DOOOOOOD.....',
    r'..DOOOOOOOOOD...',
    r'.DOO......OOOD..',
    r'.DD........DDD..',
    r'................',
    r'................',
    r'................',
]

FRAMES = [
    WALK1, WALK2, WALK3, WALK4,
    IDLE1, IDLE2,
    SIT1,  SIT2,
    SLEEP1, SLEEP2,
    JUMP1, JUMP2, JUMP3,
    BARK1, BARK2,
]

FRAME_COUNT = len(FRAMES)
FRAME_W, FRAME_H = 16, 16

sheet = Image.new("RGBA", (FRAME_W * FRAME_COUNT, FRAME_H), (0, 0, 0, 0))
for i, frame in enumerate(FRAMES):
    frame_img = px(frame, pal)
    sheet.paste(frame_img, (i * FRAME_W, 0))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "summer.png")
sheet.save(out)
print(f"Saved {out} ({FRAME_COUNT} frames, {FRAME_W * FRAME_COUNT}x{FRAME_H})")

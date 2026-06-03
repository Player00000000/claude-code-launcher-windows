from PIL import Image

BG    = (13,  13,  20,  255)
FRAME = (124, 124, 255, 255)
DARK  = (26,  26,  46,  255)
WHITE = (224, 224, 240, 255)
PINK  = (255, 124, 245, 255)

def make_base():
    img = Image.new("RGBA", (32, 32), BG)
    px  = img.load()

    # purple pixel border
    for x in range(32):
        for y in range(32):
            if x in (0,1,30,31) or y in (0,1,30,31):
                px[x,y] = FRAME

    # inner dark panel
    for x in range(3, 29):
        for y in range(3, 29):
            px[x,y] = DARK

    # title bar
    for x in range(3, 29):
        for y in range(3, 8):
            px[x,y] = FRAME

    # 3 traffic-light dots in title bar
    for dx, col in [(5,(255,107,107,255)), (9,(255,230,109,255)), (13,(168,224,99,255))]:
        for ox in range(2):
            for oy in range(2):
                px[dx+ox, 4+oy] = col

    # play triangle pointing right, centered in content area (y=9..28, x=3..28)
    # apex at x=19, rows from y=11..21
    triangle = [
        (11, 11), (11, 12), (11, 13), (11, 14), (11, 15),
        (11, 16), (11, 17), (11, 18), (11, 19), (11, 20),
        (12, 12), (12, 13), (12, 14), (12, 15), (12, 16),
        (12, 17), (12, 18), (12, 19),
        (13, 13), (13, 14), (13, 15), (13, 16), (13, 17), (13, 18),
        (14, 14), (14, 15), (14, 16), (14, 17),
        (15, 15), (15, 16),
        (16, 15), (16, 16),
        (17, 14), (17, 15), (17, 16), (17, 17),
        (18, 13), (18, 14), (18, 15), (18, 16), (18, 17), (18, 18),
        (19, 12), (19, 13), (19, 14), (19, 15), (19, 16), (19, 17), (19, 18), (19, 19),
        (20, 11), (20, 12), (20, 13), (20, 14), (20, 15),
        (20, 16), (20, 17), (20, 18), (20, 19), (20, 20),
    ]
    for (x, y) in triangle:
        if 3 <= x < 29 and 8 <= y < 29:
            px[x, y] = WHITE

    # pink "> _" hint at bottom
    for x, y in [(8,24),(8,25),(8,26),(9,23),(9,26),(10,22),(10,26),(11,23),(11,26),(12,24),(12,25),(12,26)]:
        if 3 <= x < 29 and 8 <= y < 29:
            px[x, y] = PINK
    for x in range(15, 20):
        px[x, 26] = PINK

    return img

out_path = "/mnt/d/Claude Code/launcher/icon.ico"
base = make_base()
s16  = base.resize((16,16),   Image.NEAREST)
s32  = base
s48  = base.resize((48,48),   Image.NEAREST)
s256 = base.resize((256,256), Image.NEAREST)

s256.save(out_path, format="ICO",
          sizes=[(256,256),(48,48),(32,32),(16,16)],
          append_images=[s48, s32, s16])

import os
print(f"icon.ico  {os.path.getsize(out_path):,} bytes")

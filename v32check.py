"""v32check.py -- read the poke experiment's answer.

Patterns were written into the 5 glyph tiles as row-interleaved bytes (my
writer's layout).  Two candidate readings of those 16 bytes:

  rowint: byte[y*2]=plane0 row y, byte[y*2+1]=plane1 row y
  planar: bytes 0-7 = plane0 rows 0-7, bytes 8-15 = plane1 rows 0-7

For each test tile the two readings predict a different ink mask over the
8 screen rows of the cell's top half.  Compare with what is really on screen.
"""
from PIL import Image

HW = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"

TESTS = {
    0x9C: [0xFF, 0x00, 0x00, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    0xE6: [0x00, 0x00, 0x00, 0x00, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    0x04: [0xFF] * 8 + [0] * 8,
    0x3E: [0] * 8 + [0xFF] * 8,
    0x68: [0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
           0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF],
}

# screen cells: our 5 glyphs sat at col 5..9 of the message row (y 183..198)
CELLS = [(5, 0x9C), (6, 0xE6), (7, 0x04), (8, 0x3E), (9, 0x68)]


def mask_rowint(b):
    """rows of (p0,p1) as my writer intends"""
    out = []
    for y in range(8):
        out.append((b[y * 2], b[y * 2 + 1]))
    return out


def mask_planar(b):
    out = []
    for y in range(8):
        out.append((b[y], b[y + 8]))
    return out


def predict(b, reader):
    r = []
    for p0, p1 in reader(b):
        r.append(1 if (p0 | p1) else 0)
    return r


def cell_ink(im, col, row=0):
    px = im.load()
    x0, y0 = 24 + col * 8, 183 + row * 16
    out = []
    for y in range(8):
        n = 0
        for x in range(8):
            if px[x0 + x, y0 + y] > 96:
                n += 1
        out.append(1 if n else 0)
    return out


B = Image.open(HW + "/v32a_B_f1396.png").convert("L")
C = Image.open(HW + "/v32a_C_f1396.png").convert("L")

# sanity: the two runs must differ only where the poke landed
diff = []
for y in range(224):
    for x in range(256):
        if abs(B.getpixel((x, y)) - C.getpixel((x, y))) > 40:
            diff.append((x, y))
if diff:
    xs = [p[0] for p in diff]
    ys = [p[1] for p in diff]
    print("B vs C: %d differing pixels, bbox x %d..%d y %d..%d"
          % (len(diff), min(xs), max(xs), min(ys), max(ys)))
else:
    print("B vs C: identical (poke had no effect!)")

print()
print("cell  tile  screen ink mask   rowint predicted   planar predicted   verdict")
for col, tile in CELLS:
    b = TESTS[tile]
    scr = cell_ink(C, col) + cell_ink(C, col, 1)
    ri = predict(b, mask_rowint)
    pl = predict(b, mask_planar)
    if scr[:8] == ri:
        v = "ROWA"
    elif scr[:8] == pl:
        v = "PLANAR"
    else:
        v = "?"
    print("%4d  %02X   %s      %s       %s      %s"
          % (col, tile, "".join(map(str, scr[:8])), "".join(map(str, ri)),
             "".join(map(str, pl)), v))

print()
print("bottom halves (untouched tiles) for reference:")
for col, _ in CELLS:
    print("  col %d bottom ink mask %s" % (col, "".join(map(str, cell_ink(C, col, 1)))))
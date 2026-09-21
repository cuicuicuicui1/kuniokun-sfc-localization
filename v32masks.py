"""v32masks.py -- unambiguous per-cell ink masks, B vs C.

Prints, for each message cell column, the 8-row ink mask of the top half
(y 183..190) and of the partner half (y 191..198), as 8-char binary strings.
Ink = any pixel brighter than 96 in that row; dim = 48..96.
"""
from PIL import Image

HW = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
B = Image.open(HW + "/v32a_B_f1396.png").convert("L").load()
C = Image.open(HW + "/v32a_C_f1396.png").convert("L").load()


def masks(px, col, y0):
    x0 = 24 + col * 8
    ink = dim = ""
    for y in range(8):
        hi = lo = 0
        for x in range(8):
            v = px[x0 + x, y0 + y]
            if v > 96:
                hi += 1
            elif v > 48:
                lo += 1
        ink += "1" if hi else "0"
        dim += "1" if lo else "0"
    return ink, dim


print("   col    B_top     C_top   |  B_bot     C_bot     | B_dim_top C_dim_top")
for col in range(13):
    bt, bd = masks(B, col, 183)
    ct, cd = masks(C, col, 183)
    bb, _ = masks(B, col, 191)
    cb, _ = masks(C, col, 191)
    mark = "  <== poked" if col in (5, 6, 7, 8, 9) else ""
    print("   %2d   %s  %s  |  %s  %s  |  %s   %s%s"
          % (col, bt, ct, bb, cb, bd, cd, mark))

print()
print("predictions for the poked tiles (top half ink mask, 8 rows):")
PRED = {
    0x9C: ([0xFF, 0x00, 0x00, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 5),
    0xE6: ([0x00, 0x00, 0x00, 0x00, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 6),
    0x04: ([0xFF] * 8 + [0] * 8, 7),
    0x3E: ([0] * 8 + [0xFF] * 8, 8),
    0x68: ([0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
            0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF], 9),
}
for tile, (b, col) in sorted(PRED.items()):
    ri = "".join("1" if (b[y * 2] | b[y * 2 + 1]) else "0" for y in range(8))
    pl = "".join("1" if (b[y] | b[y + 8]) else "0" for y in range(8))
    print("   tile %02X (col %d): rowint %s   planar %s" % (tile, col, ri, pl))
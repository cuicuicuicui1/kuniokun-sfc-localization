"""v32cells.py -- per-cell pixel grids for the poke experiment, B vs C.

Message row cells: cell col c occupies x = 24 + c*8 .. +7.
An 8x16 character = top tile at y 183..190 and its partner tile at y 191..198.
"""
from PIL import Image

HW = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
B = Image.open(HW + "/v32a_B_f1396.png").convert("L").load()
C = Image.open(HW + "/v32a_C_f1396.png").convert("L").load()


def sym(v):
    return "#" if v > 160 else ("+" if v > 96 else ("." if v > 48 else " "))


def grid(px, col, y0):
    x0 = 24 + col * 8
    return ["".join(sym(px[x0 + x, y0 + y]) for x in range(8)) for y in range(8)]


print("cell  band   B(no poke)      C(poked)      changed?")
for col, name in [(5, "猪 9C"), (6, "肉 E6"), (7, "包 04"), (8, "一 3E"), (9, "个 68")]:
    for label, y0 in (("top", 183), ("bot", 191)):
        gb, gc = grid(B, col, y0), grid(C, col, y0)
        chg = sum(1 for a, b in zip("".join(gb), "".join(gc)) if a != b)
        print("  %d %-6s %s  %s  %d px" % (col, name + " " + label, gb[0], gc[0], chg))
        for i in range(1, 8):
            print("           %s  %s" % (gb[i], gc[i]))
        print()

print("full message row, cols 0..12, top half y183..190, C(poked):")
for y in range(183, 191):
    row = ""
    for col in range(13):
        row += "".join(sym(C[24 + col * 8 + x, y]) for x in range(8)) + "|"
    print("  %d %s" % (y, row))
print()
print("full message row, cols 0..12, top half y183..190, B(no poke):")
for y in range(183, 191):
    row = ""
    for col in range(13):
        row += "".join(sym(B[24 + col * 8 + x, y]) for x in range(8)) + "|"
    print("  %d %s" % (y, row))
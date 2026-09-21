"""v32dump.py -- print the poke window's raw pixels from B (no poke) and C (poked).
"""
from PIL import Image

HW = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
B = Image.open(HW + "/v32a_B_f1396.png").convert("L")
C = Image.open(HW + "/v32a_C_f1396.png").convert("L")
pb, pg = B.load(), C.load()

X0, X1, Y0, Y1 = 60, 108, 180, 200

def show(px, label):
    print("== %s ==  (x %d..%d, y %d..%d)" % (label, X0, X1 - 1, Y0, Y1 - 1))
    print("     " + "".join(str((X0 + i) // 10 % 10) if (X0 + i) % 10 == 0 else " "
                            for i in range(X1 - X0)))
    print("     " + "".join(str((X0 + i) % 10) for i in range(X1 - X0)))
    for y in range(Y0, Y1):
        row = ""
        for x in range(X0, X1):
            v = px[x, y]
            row += "#" if v > 160 else ("+" if v > 96 else ("." if v > 48 else " "))
        print("%4d %s" % (y, row))
    print()

show(pb, "B (no poke)")
show(pg, "C (poked)")

print("distinct gray values in C window:",
      sorted(set(pg[x, y] for y in range(Y0, Y1) for x in range(X0, X1))))
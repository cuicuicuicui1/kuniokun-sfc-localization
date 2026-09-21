"""userbox.py -- full programmatic read of the user's screenshot.

Rebuilds a native-resolution game image from the supplied window capture
(geometry: origin 177.1,50.75, scale 2.634), then reports, for every cell of
the dialogue box, the light/dim ink masks of the top half (y=183+16*row) and
its partner half (y=191+16*row), and identifies each lit cell against
  * my glyph pool (row-interleaved reading) -> (page,slot) -> character
  * the original font tiles                     -> Japanese code
Also prints a coarse overview of the whole frame so the scene is described
in text rather than by eye.
"""
import json
import os
from PIL import Image

BASE = "C:/Users/<user>/.zcode/workspace/default/sfc-recon"
HW = BASE + "/hw"
USER_SHOT = ("C:/Users/<user>/.zcode/cli/image-cache/"
             "sess_2d6e90fa-48ba-457c-9ffa-65d2cb3a2d7a/"
             "image-29129c7e5361e3776ae9e09dd4a1ea0f.png")

# window geometry of the game image inside the capture
OX, OY, S = 177.125, 50.750, 2.634

im = Image.open(USER_SHOT).convert("RGB")
W, H = 256, 224
nat = Image.new("L", (W, H))
px_src = im.load()
px_dst = nat.load()
for y in range(H):
    for x in range(W):
        sx, sy = OX + (x + 0.5) * S, OY + (y + 0.5) * S
        ix, iy = int(sx), int(sy)
        if 0 <= ix < im.width - 1 and 0 <= iy < im.height - 1:
            fx, fy = sx - ix, sy - iy
            v = (px_src[ix, iy][1] * (1 - fx) * (1 - fy)
                 + px_src[ix + 1, iy][1] * fx * (1 - fy)
                 + px_src[ix, iy + 1][1] * (1 - fx) * fy
                 + px_src[ix + 1, iy + 1][1] * fx * fy)
        else:
            v = 0
        px_dst[x, y] = int(v)
nat.save(HW + "/userbox_native.png")

# ---- tables from my build -------------------------------------------------
rom = open(BASE + "/kuniokun_cn.smc", "rb").read()
orig = open(BASE + "/dl/roms/kuniokun__SF8127.smc", "rb").read()


def rom_off(bank, off):
    return (bank & 0x7F) * 0x8000 + (off & 0x7FFF) + (0x10000 if off & 0x8000 else 0)


slots = [rom[0x01E900 + i] for i in range(86)]
slot_of = {}
for i, t in enumerate(slots):
    slot_of[t] = i
    slot_of[t + 1] = i
pool_chars = json.load(open(BASE + "/cn_page_map.json")) if os.path.exists(BASE + "/cn_page_map.json") else None


def pool_bytes(page, slot):
    off = 0x108000 + page * 0x8000 + slot * 32
    return rom[off:off + 32]


FONT = 0x0F8000


def font_tile(code):
    return orig[FONT + code * 16:FONT + code * 16 + 16]


FA = orig[0x01FA9E:0x01FA9E + 256]
FB = orig[0x01FB9E:0x01FB9E + 256]


def bits16(b):
    """16 bytes -> list of 8 rows, each 8 chars '0..3' of colour indices (row-interleaved)."""
    rows = []
    for y in range(8):
        p0, p1 = b[y * 2], b[y * 2 + 1]
        rows.append("".join(str(((p1 >> (7 - x)) & 1) * 2 + ((p0 >> (7 - x)) & 1))
                            for x in range(8)))
    return rows


def ink_rows(b):
    return "".join("1" if (b[y * 2] | b[y * 2 + 1]) else "0" for y in range(8))


def cell_masks(col, row):
    """observed ink mask of the top half and partner half of a text cell"""
    x0 = 24 + col * 8
    out = []
    for y0 in (183 + row * 16, 191 + row * 16):
        s = ""
        for y in range(8):
            s += "1" if any(px_dst[x0 + x, y0 + y] > 96 for x in range(8)) else "0"
        out.append(s)
    return out


# ---- screen overview ------------------------------------------------------
print("=== whole-frame overview (2x2 blocks, '#' bright, '+' mid, '.' dim, ' ' black) ===")
for by in range(0, H, 4):
    line = ""
    for bx in range(0, W, 4):
        vals = [px_dst[bx + dx, by + dy] for dx in range(4) for dy in range(4)]
        m = sum(vals) / 16.0
        line += "#" if m > 150 else ("+" if m > 80 else ("." if m > 30 else " "))
    print("%3d %s" % (by, line))

print()
print("=== dialogue box cells ===")
print("row col  top      bot      best pool match            best font match")
for row in range(3):
    for col in range(16):
        top, bot = cell_masks(col, row)
        if top == "00000000" and bot == "00000000":
            continue
        best = None
        for page in range(12):
            for s in range(86):
                b = pool_bytes(page, s)
                if ink_rows(b[:16]) == top and ink_rows(b[16:]) == bot:
                    best = ("POOL p%d s%d" % (page, s))
                    break
            if best:
                break
        bf = None
        for code in range(256):
            if ink_rows(font_tile(FB[code])) == top and ink_rows(font_tile(FA[code])) == bot:
                bf = "code %02X" % code
                break
        print("%3d %3d  %s  %s  %-24s %s" % (row, col, top, bot, best or "-", bf or "-"))
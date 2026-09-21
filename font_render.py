#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_render.py -- render the 8x8 2bpp font at ROM offset 0x0F8000 of
kuniokun__SF8127.smc (LoROM, 初代熱血硬派くにおくん, Technos 1992).

Two interpretations are rendered:
  * "row"     : row-interleaved. For row y: plane0 = tb[y*2], plane1 = tb[y*2+1]
  * "planar"  : standard SNES planar 2bpp. plane0 = tb[0..7], plane1 = tb[8..15]

Outputs PNG contact sheets + ASCII art + a starter font_map.tsv.

Use FORWARD SLASH paths (Git Bash heredoc eats backslashes).
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

ROM_PATH  = "dl/roms/kuniokun__SF8127.smc"
FONT_OFF  = 0x0F8000
N_TILES   = 256
TILE_BYTES = 16

OUTDIR = "."

# ---------------------------------------------------------------- load
with open(ROM_PATH, "rb") as f:
    rom = f.read()
assert len(rom) == 1048576, "unexpected ROM size %d" % len(rom)
font = rom[FONT_OFF:FONT_OFF + N_TILES * TILE_BYTES]
assert len(font) == N_TILES * TILE_BYTES

def tile(idx):
    return font[idx * TILE_BYTES:(idx + 1) * TILE_BYTES]

# ---------------------------------------------------------------- pixel decode
def rows_row(tb):
    """row-interleaved: returns list of 8 rows, each 8 ints 0..3"""
    out = []
    for y in range(8):
        p0 = tb[y * 2]
        p1 = tb[y * 2 + 1]
        out.append([((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                    for x in range(8)])
    return out

def rows_planar(tb):
    """standard snes planar: plane0 = tb[0..7], plane1 = tb[8..15]"""
    out = []
    for y in range(8):
        p0 = tb[y]
        p1 = tb[y + 8]
        out.append([((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                    for x in range(8)])
    return out

MODES = {"row": rows_row, "planar": rows_planar}

CH_ASCII = {0: " ", 1: ".", 2: "o", 3: "#"}

def ascii_art(tb, mode="row"):
    rows = MODES[mode](tb)
    return "\n".join("".join(CH_ASCII[v] for v in r) for r in rows)

# ---------------------------------------------------------------- PNG helpers
PAL = {
    0: (255, 255, 255),   # background white
    1: (0, 0, 0),         # left stroke  -> black
    2: (0, 0, 0),         # right stroke -> black
    3: (220, 0, 0),       # color 3 -> red (flag anomalies)
}

def _load_font(size):
    for p in ("C:/Windows/Fonts/arial.ttf",
              "C:/Windows/Fonts/segoeui.ttf",
              "C:/Windows/Fonts/consola.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def render_range(start, end, per_row, scale, path, mode="row",
                 label_h=14, gap=2, label_font_size=None):
    """Render tiles [start, end) inclusive-exclusive into a contact sheet."""
    n = end - start
    nrows = (n + per_row - 1) // per_row
    tsize = 8 * scale
    lf = _load_font(label_font_size or max(10, scale + 4))
    cell_w = tsize + gap
    cell_h = tsize + label_h + gap
    W = per_row * cell_w + gap
    H = nrows * cell_h + gap
    img = Image.new("RGB", (W, H), (200, 200, 200))
    d = ImageDraw.Draw(img)
    for i, idx in enumerate(range(start, end)):
        r = i // per_row
        c = i % per_row
        x0 = gap + c * cell_w
        y0 = gap + r * cell_h
        # label
        d.text((x0, y0), "0x%02X" % idx, fill=(0, 0, 90), font=lf)
        # tile pixels
        ty = y0 + label_h
        rows = MODES[mode](tile(idx))
        for yy in range(8):
            for xx in range(8):
                col = PAL[rows[yy][xx]]
                d.rectangle([x0 + xx * scale, ty + yy * scale,
                             x0 + (xx + 1) * scale - 1,
                             ty + (yy + 1) * scale - 1], fill=col)
    img.save(path)
    return path

def render_big(start, end, per_row, scale, path, mode="row"):
    """Larger cells for legibility (kana)."""
    return render_range(start, end, per_row, scale, path, mode=mode,
                        label_h=max(16, scale + 6), gap=3,
                        label_font_size=max(12, scale + 2))

# ---------------------------------------------------------------- font map
# Gojuuon strings used by the kana blocks (verified visually, see report).
HIRA_GOJUUON = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"  # 46
KATA_GOJUUON = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワ"  # 44 (ア-ワ)

# Tiles 0x02-0x06 are NOT the ASCII chars '"' '#' '$' '%' '&' : the game
# replaced those positions with custom UI symbols (see report).
ASCII_SYMBOL = {
    0x02: "sym:filled-square",
    0x03: "sym:down-triangle",
    0x04: "sym:right-triangle",
    0x05: "sym:cross",
    0x06: "sym:misc",
}

def build_map():
    m = {}
    m[0x00] = (" ", "high")                      # space (blank tile)
    for i in range(0x01, 0x3E):                  # 0x01-0x3D = ASCII 0x21-0x5D
        if i in ASCII_SYMBOL:
            m[i] = (ASCII_SYMBOL[i], "low")
        else:
            m[i] = (chr(0x20 + i), "high")
    m[0x3E] = ("bar-top", "high")                # horizontal bar (top half)
    m[0x3F] = ("bar-bottom", "high")             # horizontal bar (bottom half)
    for i in range(0x40, 0x71):                  # 0x40-0x70 = graphic/texture tiles
        m[i] = ("graphic", "high")
    m[0x63] = ("sym:diamond", "med")             # ◆-like solid diamond
    m[0x64] = ("sym:square-outline", "med")      # □-like
    m[0x65] = ("sym:square-filled", "med")       # ■-like
    m[0x70] = ("graphic:filled", "high")         # solid square (== tile 0x49)
    for i in range(0x71, 0x9F):                  # 0x71-0x9E = hiragana あ-ん
        m[i] = (HIRA_GOJUUON[i - 0x71], "high")
    m[0x9F] = ("unknown", "low")
    m[0xA0] = ("ー", "high")                     # katakana prolonged sound mark
    for i in range(0xA1, 0xCD):                  # 0xA1-0xCC = katakana ア-ワ
        m[i] = (KATA_GOJUUON[i - 0xA1], "high")
    m[0xCD] = ("ン", "med")                      # 2-stroke glyph; gojuuon would put ヲ here
    m[0xCE] = ("unknown", "low")
    m[0xCF] = ("unknown", "low")
    m[0xD0] = (" ", "high")                      # blank tile
    for i in range(0xD1, 0xE0):
        m[i] = ("unknown", "low")
    for i in range(0xE0, 0x100):                 # 0xE0-0xFF = graphic tiles (red bars)
        m[i] = ("graphic", "high")
    return m

def write_font_map(path):
    m = build_map()
    with open(path, "w", encoding="utf-8") as f:
        f.write("tile\tchar\tconfidence\n")
        for i in range(256):
            ch, conf = m.get(i, ("unknown", "low"))
            f.write("0x%02X\t%s\t%s\n" % (i, ch, conf))
    return path

# ---------------------------------------------------------------- run
if __name__ == "__main__":
    made = []

    # four quadrants, 8 tiles/row, scale 8, row-interleaved
    for (a, b, name) in [(0x00, 0x40, "font_tiles_00_3F.png"),
                         (0x40, 0x80, "font_tiles_40_7F.png"),
                         (0x80, 0xC0, "font_tiles_80_BF.png"),
                         (0xC0, 0x100, "font_tiles_C0_FF.png")]:
        made.append(render_range(a, b, 8, 8, os.path.join(OUTDIR, name)))

    # control: same regions under standard planar interpretation
    for (a, b, name) in [(0x00, 0x40, "ctl_planar_00_3F.png"),
                         (0x60, 0xE0, "ctl_planar_60_DF.png")]:
        made.append(render_range(a, b, 8, 8, os.path.join(OUTDIR, name),
                                 mode="planar"))
    # control: full font region under standard planar interpretation
    made.append(render_range(0x00, 0x100, 16, 6,
                             os.path.join(OUTDIR, "ctl_planar_00_FF.png"),
                             mode="planar"))

    # kana region tall image, larger scale
    made.append(render_big(0x60, 0xE0, 8, 12,
                           os.path.join(OUTDIR, "font_kana_60_DF.png")))
    # halves for readability
    made.append(render_big(0x60, 0xA0, 8, 14,
                           os.path.join(OUTDIR, "font_kana_60_9F.png")))
    made.append(render_big(0xA0, 0xE0, 8, 14,
                           os.path.join(OUTDIR, "font_kana_A0_DF.png")))
    # control halves
    made.append(render_big(0x60, 0xA0, 8, 14,
                           os.path.join(OUTDIR, "ctl_planar_60_9F.png"),
                           mode="planar"))
    made.append(render_big(0xA0, 0xE0, 8, 14,
                           os.path.join(OUTDIR, "ctl_planar_A0_DF.png"),
                           mode="planar"))

    for m in made:
        print("wrote", m)

    # ascii art dumps
    with open(os.path.join(OUTDIR, "font_ascii_row.txt"), "w", encoding="utf-8") as f:
        for i in range(N_TILES):
            f.write("tile 0x%02X\n" % i)
            f.write(ascii_art(tile(i), "row") + "\n\n")
    with open(os.path.join(OUTDIR, "font_ascii_planar.txt"), "w", encoding="utf-8") as f:
        for i in range(N_TILES):
            f.write("tile 0x%02X\n" % i)
            f.write(ascii_art(tile(i), "planar") + "\n\n")
    print("wrote font_ascii_row.txt font_ascii_planar.txt")

    # quick blank / nonblank stats
    blanks = []
    for i in range(N_TILES):
        if all(v == 0 for r in rows_row(tile(i)) for v in r):
            blanks.append(i)
    print("blank tiles (row):", " ".join("0x%02X" % i for i in blanks))

    # tile-index -> character map
    print("wrote", write_font_map(os.path.join(OUTDIR, "font_map.tsv")))

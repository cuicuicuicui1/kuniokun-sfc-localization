"""Reconstruct a SNES BG layer from a VRAM/CGRAM dump and locate a BG's tile source.

Given a BizHawk dump (64KB VRAM + 512B CGRAM) and the matching screenshot, this
tries every plausible (BGMODE, BGxSC, BGxyNBA) combination, renders the layer,
and reports which settings reproduce what is on screen.  Then it tells us which
VRAM word range the winning layer reads, so the same tiles can be found in the ROM.

    python titlescreen.py <frame-tag> [--shot PNG]
"""
import os
import sys

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(BASE, 'hw')


def load_dump(tag):
    vram = open(os.path.join(HW, tag + '_vram64.bin'), 'rb').read()
    cgram = open(os.path.join(HW, tag + '_cgram.bin'), 'rb').read()
    assert len(vram) == 0x10000, len(vram)
    return vram, cgram


def palette(cgram, pal):
    cols = []
    for i in range(16):
        lo = cgram[pal * 32 + i * 2]
        hi = cgram[pal * 32 + i * 2 + 1]
        w = lo | (hi << 8)
        cols.append(((w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31))
    return cols


def decode_tile(vram, charbase, idx, bpp, pal, cgram, flipx=False, flipy=False):
    """Return an 8x8 list of RGB tuples."""
    addr = charbase + idx * (bpp * 8)
    cols = palette(cgram, pal)
    rows = []
    for y in range(8):
        planes = []
        for p in range(bpp):
            a = addr + p * 16 + y * 2
            planes.append((vram[a] << 8) | vram[a + 1])
        row = []
        for x in range(8):
            bit = 7 - x
            v = 0
            for p in range(bpp):
                v |= ((planes[p] >> bit) & 1) << p
            row.append(cols[v])
        rows.append(row)
    if flipx:
        rows = [list(reversed(r)) for r in rows]
    if flipy:
        rows = list(reversed(rows))
    return rows


BPP = {0: 2, 1: 4, 2: 4, 3: 8, 4: 8, 5: 4, 6: 4, 7: 8}


def render_bg(vram, cgram, mode, sc, nba, width=256, height=224, bg=1):
    """Render one BG layer to a PIL image, or None if the settings are impossible."""
    bpp = BPP.get(mode)
    if bpp is None:
        return None, None
    mapbase = (sc & 0xFC) << 8
    size = sc & 3
    if bg in (1, 2):
        charbase = ((nba & 0x0F) if bg == 1 else (nba >> 4)) << 13
        if mode == 0:
            charbase = (((nba & 0x0F) if bg == 1 else (nba >> 4)) << 13)
    else:
        charbase = (((nba & 0x0F) if bg == 3 else (nba >> 4)) << 13)
    if mode == 0:
        bpp = 2
    img = Image.new('RGB', (width, height))
    px = img.load()
    used = set()
    for ty in range(0, height, 8):
        for tx in range(0, width, 8):
            cx, cy = tx // 8, ty // 8
            # 32x32 tilemaps, optionally 64x64
            mx = (cx // 32) if size in (1, 3) else 0
            my = (cy // 32) if size in (2, 3) else 0
            off = mapbase + ((my * 32 + mx) * 32 * 32 + (cy % 32) * 32 + (cx % 32)) * 2
            w = vram[off & 0xFFFF] | (vram[(off + 1) & 0xFFFF] << 8)
            idx = w & 0x3FF
            pal = (w >> 10) & 7
            fx, fy = bool(w & 0x4000), bool(w & 0x8000)
            used.add(idx)
            tile = decode_tile(vram, charbase, idx, bpp, pal, cgram, fx, fy)
            for y in range(8):
                for x in range(8):
                    px[tx + x, ty + y] = tile[y][x]
    return img, (charbase, mapbase, bpp, used)


def diff(a, b):
    pa, pb = a.load(), b.load()
    n = 0
    for y in range(a.height):
        for x in range(a.width):
            if pa[x, y] != pb[x, y]:
                n += 1
    return n


def main():
    tag = sys.argv[1]
    vram, cgram = load_dump(tag)
    shot_path = None
    for i, a in enumerate(sys.argv):
        if a == '--shot':
            shot_path = sys.argv[i + 1]
    if shot_path is None:
        cand = os.path.join(HW, tag.replace('_vram64', '') + '.png')
        shot_path = cand if os.path.exists(cand) else None
    ref = None
    if shot_path and os.path.exists(shot_path):
        ref = Image.open(shot_path).convert('RGB')
        if ref.size != (256, 224):
            ref = ref.resize((256, 224), Image.NEAREST)
    print('tag', tag, 'shot', shot_path, 'ref', ref.size if ref else None)

    results = []
    for mode in (0, 1, 2, 3, 4, 5):
        for bg, sc, nba in ((1, 0x07, 0x0A), (2, 0x08, 0x0A), (3, 0x09, 0x0B), (4, 0x09, 0x0B)):
            pass
    # brute force over the real register space instead of guessing
    for mode in (0, 1, 2, 3, 4, 5):
        for bg in (1, 2, 3, 4):
            for sc in range(0, 0x100, 4):
                for nba in range(0, 0x100, 1):
                    img, meta = render_bg(vram, cgram, mode, sc, nba, bg=bg)
                    if img is None or meta is None:
                        continue
                    d = diff(img, ref) if ref else 0
                    results.append((d, mode, bg, sc, nba, meta))
    results.sort(key=lambda r: r[0])
    for d, mode, bg, sc, nba, meta in results[:12]:
        charbase, mapbase, bpp, used = meta
        print('diff=%6d mode=%d BG%d sc=%02X nba=%02X char=%04X map=%04X bpp=%d tiles=%d min=%d max=%d'
              % (d, mode, bg, sc, nba, charbase, mapbase, bpp, len(used), min(used), max(used)))


if __name__ == '__main__':
    main()
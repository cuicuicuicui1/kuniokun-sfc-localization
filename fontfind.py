"""Find an uncompressed 8x8 2bpp font in a SNES ROM by DENSITY ENRICHMENT.

Why this metric and not the obvious ones:
  plane0==plane1 equality, non-blank ratio, unique-tile count and "first row is
  blank" are ALL satisfied by ordinary graphics blocks just as well as by fonts.
  Using them lands you on a tileset. The one thing that separates a font from
  graphics is CONCENTRATION: a font is a run of hundreds of glyph tiles, while
  graphics are either sparse or made of tiles that repeat row-by-row.

Usage:
    python -u fontfind.py <rom> [bpp] [tile_start_hex] [ntiles]

    bpp           16 (2bpp) or 32 (4bpp); default 16
    tile_start_hex  render an ASCII view starting at this offset
    ntiles          how many tiles to render (default 16, 16 per line)
"""
import sys

CELL = 8


def trows2(t):
    """Decode one 8x8 2bpp tile into 8 tuples of 8 pixel values."""
    out = []
    for y in range(CELL):
        p0, p1 = t[y * 2], t[y * 2 + 1]
        out.append(tuple(((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                         for x in range(CELL)))
    return out


def trows4(t):
    """Decode one 8x8 4bpp tile (row-interleaved plane pairs)."""
    out = []
    for y in range(CELL):
        p0, p1 = t[y * 2], t[y * 2 + 1]
        p2, p3 = t[16 + y * 2], t[16 + y * 2 + 1]
        out.append(tuple(((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                         | (((p2 >> (7 - x)) & 1) << 2) | (((p3 >> (7 - x)) & 1) << 3)
                         for x in range(CELL)))
    return out


def glyphlike(rows, ink_lo=0.04, ink_hi=0.45, min_distinct_rows=3):
    """A glyph tile: sane ink amount AND rows that are not all identical.

    The row-variety test is what rejects the solid bars and striped tiles that
    dominate graphics blocks -- a constant byte renders as a full-height bar.
    """
    ink = sum(1 for r in rows for v in r if v) / (CELL * CELL)
    if not (ink_lo <= ink <= ink_hi):
        return False
    return len(set(rows)) >= min_distinct_rows


def ascii_view(body, off, bpp, ntiles):
    dec = trows4 if bpp == 32 else trows2
    per_line = 16
    for base in range(0, ntiles, per_line):
        print('--- 0x%06X ---' % (off + base * bpp))
        grid = [dec(body[off + (base + c) * bpp:off + (base + c) * bpp + bpp])
                for c in range(min(per_line, ntiles - base))]
        for y in range(CELL):
            print(' '.join(''.join('#' if v else '.' for v in t[y]) for t in grid))


def scan(body, bpp):
    dec = trows4 if bpp == 32 else trows2
    nt = len(body) // bpp
    flags = [glyphlike(dec(body[i * bpp:i * bpp + bpp])) for i in range(nt)]

    win = 256                                    # one 4K page at 2bpp
    page = win * bpp
    scores = []
    for i in range(0, nt - win, 4):
        scores.append((sum(flags[i:i + win]), i * bpp))
    scores.sort(key=lambda x: -x[0])
    mean = sum(s for s, _ in scores) / max(1, len(scores))
    return scores, mean, sum(flags), nt


def main():
    rom = sys.argv[1]
    bpp = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    body = open(rom, 'rb').read()
    if len(body) % 32768 == 512:                 # strip copier header
        body = body[512:]

    scores, mean, total, nt = scan(body, bpp)
    print('%s  %d B  %dbpp' % (rom, len(body), bpp // 8))
    print('glyph-like tiles: %d / %d' % (total, nt))
    print('mean per 256-tile window: %.1f' % mean)
    print('top candidate windows (enrichment vs mean):')
    shown = []
    for s, off in scores:
        if any(abs(off - p) < 0x2000 for p in shown):
            continue
        shown.append(off)
        print('   0x%06X  %d/256  (%.1fx mean)' % (off, s, s / mean if mean else 0))
        if len(shown) >= 6:
            break

    if len(sys.argv) > 3:
        off = int(sys.argv[3], 16)
        ntiles = int(sys.argv[4]) if len(sys.argv) > 4 else 16
        print()
        ascii_view(body, off, bpp, ntiles)


if __name__ == '__main__':
    main()
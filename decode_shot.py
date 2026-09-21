"""Decode what is actually on screen in an emulator screenshot, cell by cell.

Normalises any window screenshot down to the SNES 256x224 picture, cuts the
engine's own character grid (x = 24 + col*8, y = 183 + row*16 for the message
window) and matches every lit cell against
  * the Chinese glyph pool written by cnbuild5 (exact bit match => char + page/slot)
  * the original Japanese font (FB[code] over FA[code], codes 0..255)
so we learn whether the screen shows Chinese glyphs, original Japanese glyphs,
or something else -- without anyone reading pixels by eye.

Self-test: hw/v29a_f01390.png was already proven pixel-exact, so it must decode to
the five pool cells of 猪肉包一个 plus the two kana of the speaker name.
"""
import sys, json, os
import cnbuild5 as cb
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
PATCHED = os.path.join(BASE, 'kuniokun_cn.smc')
ORIG = os.path.join(BASE, 'dl/roms/kuniokun__SF8127.smc')
TEXT_X0, TEXT_Y0 = 24, 183          # top left of message-window cell (col 0, row 0)


def mask_from_pool32(b):
    """32 bytes (two 8x8 row-interleaved 2bpp tiles) -> 16x8 lit mask (top then bottom)."""
    rows = []
    for t in (0, 16):
        for y in range(8):
            p0, p1 = b[t + y * 2], b[t + y * 2 + 1]
            rows.append([1 if ((p0 >> (7 - x)) & 1) or ((p1 >> (7 - x)) & 1) else 0
                         for x in range(8)])
    return rows


def as_bits(rows):
    return bytes(sum(rows, []))


def load_tables():
    patched = open(PATCHED, 'rb').read()
    orig = open(ORIG, 'rb').read()
    slots = []
    i = 0
    while i < 200:
        v = patched[cb.B3_SLOTPAIR + i]
        if v == 0 and i > 0:
            break
        slots.append(v)
        i += 1
    pages = json.load(open(os.path.join(BASE, 'cn_build_params.json')))['pages']
    pool_blob, pool_label = {}, {}
    for page in range(pages):
        for s in range(len(slots)):
            off = cb.POOL_ROM + page * 0x8000 + s * 32
            blob = patched[off:off + 32]
            if blob == b'\x00' * 32:
                continue
            pool_blob[bytes(blob)] = (page, s)
            pool_label[as_bits(mask_from_pool32(bytes(blob)))] = (page, s)
    char_of = {}
    text = json.load(open(os.path.join(BASE, 'cn_translation.json')))
    chars = set()
    for v in text.values():
        if isinstance(v, str):
            chars.update(v)
    for ch in sorted(chars):
        if ch in cb.KEEP1 or ch == '\n':
            continue
        try:
            g = cb.glyph32(ch)
        except Exception:
            continue
        if bytes(g) in pool_blob:
            char_of[pool_blob[bytes(g)]] = ch
    fa = orig[0x01FA9E:0x01FA9E + 256]
    fb = orig[0x01FB9E:0x01FB9E + 256]
    orig_label = {}
    for code in range(256):
        t0 = 0x0F8000 + fb[code] * 16
        t1 = 0x0F8000 + fa[code] * 16
        bits = as_bits(mask_from_pool32(bytes(orig[t0:t0 + 16] + orig[t1:t1 + 16])))
        orig_label.setdefault(bits, code)
    return slots, pages, pool_label, char_of, orig_label


def game_area(im):
    """The game picture is the region bounded by black letterbox columns/rows.
    The window's gray title/menu bars are not black, so they cannot be picked."""
    g = im.convert('L')
    w, h = g.size
    px = g.load()
    band = range(int(h * 0.25), int(h * 0.75))
    col_black = [sum(1 for y in band if px[x, y] < 16) / float(len(band)) for x in range(w)]
    isbar = [c > 0.95 for c in col_black]
    # largest run of non-bar columns
    best = (0, -1)
    x = 0
    while x < w:
        if not isbar[x]:
            s = x
            while x < w and not isbar[x]:
                x += 1
            if x - 1 - s > best[1] - best[0]:
                best = (s, x - 1)
        else:
            x += 1
    x0, x1 = best
    row_black = [sum(1 for x in range(x0, x1 + 1) if px[x, y] < 16) / float(x1 - x0 + 1)
                 for y in range(h)]
    besty = (0, -1)
    y = 0
    while y < h:
        if row_black[y] <= 0.95:
            s = y
            while y < h and row_black[y] <= 0.95:
                y += 1
            if y - 1 - s > besty[1] - besty[0]:
                besty = (s, y - 1)
        else:
            y += 1
    return x0, besty[0], x1, besty[1]


def normalise(path):
    """-> 256x224 8-bit image of the game picture (identity for native shots)."""
    im = Image.open(path).convert('L')
    if im.size == (256, 224):
        return im, (0, 0, 255, 223)
    box = game_area(im)
    crop = im.crop((box[0], box[1], box[2] + 1, box[3] + 1))
    return crop.resize((256, 224), Image.BOX), box


def cell_mask(im, col, row, thresh=96):
    px = im.load()
    rows = []
    for y in range(16):
        line = []
        for x in range(8):
            v = px[TEXT_X0 + col * 8 + x, TEXT_Y0 + row * 16 + y]
            line.append(1 if v > thresh else 0)
        rows.append(line)
    return rows


def show(masks, caption, cols=None):
    print(caption)
    for y in range(16):
        line = ''
        for m in masks:
            line += ''.join('#' if v else '.' for v in m[y]) + ' '
        print('   ' + line)


def decode(path, tabs, rowlimit=3):
    pool_label, char_of, orig_label = tabs
    im, box = normalise(path)
    print('=' * 78)
    print('%s  game area=%s' % (os.path.basename(path), box))
    cells = {}
    for row in range(rowlimit):
        for col in range(26):
            m = cell_mask(im, col, row)
            if sum(sum(r) for r in m) < 5:
                continue
            bits = as_bits(m)
            p = pool_label.get(bits)
            o = orig_label.get(bits)
            cells[(col, row)] = (m, p, o)
            if p is not None:
                tag = 'POOL (%d,%02X) = %s' % (p[0], p[1], char_of.get(p, '?'))
            elif o is not None:
                tag = 'ORIGINAL FONT code $%02X' % o
            else:
                tag = 'neither (len %d)' % sum(sum(r) for r in m)
            print('  col=%2d row=%d  %s' % (col, row, tag))
    return im, cells


def main():
    slots, pages, pool_label, char_of, orig_label = load_tables()
    print('slots=%d pages=%d poolGlyphs=%d mappedChars=%d'
          % (len(slots), pages, len(pool_label), len(char_of)))
    tabs = (pool_label, char_of, orig_label)
    out = []
    for path in sys.argv[1:]:
        out.append(decode(path, tabs))
    if len(out) == 2:
        (ia, a), (ib, b) = out
        print('=' * 78)
        print('--- scene check: picture above the message window (rows 0..179) ---')
        import itertools
        diff = sum(1 for y in range(0, 180) for x in range(0, 256)
                   if abs(ia.load()[x, y] - ib.load()[x, y]) > 64)
        print('  differing pixels above the box: %d of %d' % (diff, 180 * 256))
        print('--- cell by cell ---')
        for key in sorted(set(a) | set(b)):
            ma, mb = a.get(key), b.get(key)
            la = ('POOL %s' % (ma[1],)) if ma and ma[1] else (
                ('ORIG $%02X' % ma[2]) if ma and ma[2] is not None else ('-' if not ma else 'neither'))
            lb = ('POOL %s' % (mb[1],)) if mb and mb[1] else (
                ('ORIG $%02X' % mb[2]) if mb and mb[2] is not None else ('-' if not mb else 'neither'))
            same = (ma is not None and mb is not None and ma[0] == mb[0])
            print('  %s  first=%-16s second=%-16s %s'
                  % (key, la, lb, 'SAME' if same else 'DIFFERENT'))
            if ma and mb and not same:
                show([ma[0], mb[0]], '      first -- second')


if __name__ == '__main__':
    main()